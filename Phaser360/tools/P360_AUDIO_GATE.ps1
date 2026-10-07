param(
    [ValidateSet("Audit","PreAudio","BoundedSpeaker","Audio","Restore")]
    [string]$Mode = "Audit",
    [string]$FirmwarePath = "",
    [string]$SessionPath = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ExpectedHwIdPrefix = "CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198"
$ExpectedBusPrefix = "PCI\VEN_8086&DEV_3198"
$ExpectedAmpPrefix = "ACPI\MX98357A"
$ExpectedFirmwareBytes = 246528
$ExpectedFirmwareSha256 = "f68694b6197250016a9c5ffb46fa8adaa599a32db95aa19a0ecf5bd4ed1c62ab"
$TelemetryPath = "HKLM:\SYSTEM\CurrentControlSet\Services\P360SofAudio\Parameters"
$ProofRoot = Join-Path $env:ProgramData "P360AudioGate"
$ProofPath = Join-Path $ProofRoot "preaudio-proof.json"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageInfoPath = Join-Path $PackageRoot "PACKAGE_INFO.json"
$LogPath = $null
$Session = $null
$State = $null

function Write-RunLog([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"), $Message
    Write-Host $line
    if ($script:LogPath) {
        Add-Content -LiteralPath $script:LogPath -Value $line -Encoding UTF8
    }
}

function Save-State {
    if ($script:State -and $script:Session) {
        $script:State | ConvertTo-Json -Depth 6 |
            Set-Content -LiteralPath (Join-Path $script:Session "STATE.json") -Encoding UTF8
    }
}

function Invoke-Tool {
    param(
        [Parameter(Mandatory=$true)][string]$Exe,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    Write-RunLog ("RUN: {0} {1}" -f $Exe, ($Arguments -join " "))
    $output = & $Exe @Arguments 2>&1 | Out-String
    $code = $LASTEXITCODE
    if ($output.Trim().Length -gt 0) {
        Write-RunLog $output.Trim()
    }
    if ($code -ne 0 -and -not $AllowFailure) {
        throw "$Exe failed with exit code $code"
    }
    return [pscustomobject]@{ ExitCode=$code; Output=$output }
}

function Assert-Administrator {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Administrator privileges are required."
    }
}

function Get-TargetDevice {
    $targets = @(Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -and $_.PNPDeviceID.StartsWith($ExpectedHwIdPrefix,[StringComparison]::OrdinalIgnoreCase)
    })
    if ($targets.Count -ne 1) {
        throw "Expected exactly one Phaser360 CSAUDIO ADSP target; found $($targets.Count)."
    }
    return $targets[0]
}

function Get-BusDevice {
    $targets = @(Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -and $_.PNPDeviceID.StartsWith($ExpectedBusPrefix,[StringComparison]::OrdinalIgnoreCase)
    })
    if ($targets.Count -lt 1) {
        throw "Intel 8086:3198 audio bus target was not found."
    }
    $bus = $targets | Where-Object { $_.Service -eq "SklHDAudBus" } | Select-Object -First 1
    if (-not $bus) {
        throw "8086:3198 exists but is not bound to SklHDAudBus."
    }
    if ([int]$bus.ConfigManagerErrorCode -ne 0) {
        throw "SklHDAudBus is not healthy; ConfigManagerErrorCode=$($bus.ConfigManagerErrorCode)."
    }
    return $bus
}

function Get-AmpDevice {
    $targets = @(Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -and $_.PNPDeviceID.StartsWith($ExpectedAmpPrefix,[StringComparison]::OrdinalIgnoreCase)
    })
    if ($targets.Count -lt 1) {
        throw "MAX98357A ACPI device was not found."
    }
    $amp = $targets | Select-Object -First 1
    if ([int]$amp.ConfigManagerErrorCode -ne 0) {
        throw "MAX98357A is not healthy; ConfigManagerErrorCode=$($amp.ConfigManagerErrorCode), Service=$($amp.Service)."
    }
    if (-not $amp.Service) {
        throw "MAX98357A is present but has no bound driver service."
    }
    return $amp
}

function Get-SignedDriverOrNull([string]$InstanceId) {
    return (Get-CimInstance Win32_PnPSignedDriver | Where-Object {
        $_.DeviceID -eq $InstanceId
    } | Select-Object -First 1)
}

function Get-SignedDriver([string]$InstanceId) {
    $driver = Get-SignedDriverOrNull $InstanceId
    if (-not $driver) {
        throw "No signed-driver record found for $InstanceId."
    }
    return $driver
}

function Assert-TestSigning {
    $result = Invoke-Tool -Exe "bcdedit.exe" -Arguments @("/enum","{current}")
    $text = $result.Output
    if ($text -notmatch "(?im)^\s*testsigning\s+(Yes|On|Da|1)\s*$") {
        throw "Windows TestSigning is not ON. Runner will not modify BCD and will not reboot."
    }

    try {
        $secureBoot = Confirm-SecureBootUEFI
        if ($secureBoot -eq $true) {
            throw "Secure Boot is enabled; refusing test-signed kernel package."
        }
    } catch [System.PlatformNotSupportedException] {
        # Legacy BIOS / unsupported query: TestSigning result remains authoritative.
    } catch {
        if ($_.Exception.Message -match "not supported|Cmdlet not supported") {
            # Ignore unsupported firmware query.
        } else {
            throw
        }
    }
}

function New-RunSession([string]$RunMode) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $root = Join-Path $desktop "P360_AUDIO_SAFE"
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $path = Join-Path $root ("P360_{0}_{1}" -f $RunMode.ToUpperInvariant(),$stamp)
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    $script:Session = $path
    $script:LogPath = Join-Path $path "RUN.log"
    return $path
}

function Test-FirmwareFile([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -ne $ExpectedFirmwareBytes) {
        return $false
    }
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    return $hash -eq $ExpectedFirmwareSha256
}

function Resolve-Firmware([string]$Requested) {
    if ($Requested) {
        $resolved = (Resolve-Path -LiteralPath $Requested).Path
        if ([IO.Path]::GetExtension($resolved) -ieq ".zip") {
            return Extract-FirmwareFromZip $resolved
        }
        if (-not (Test-FirmwareFile $resolved)) {
            throw "Firmware supplied by -FirmwarePath does not match exact f686 size/hash."
        }
        return $resolved
    }

    $knownFirmware = @(
        "D:\PHASER360_WORK\continuation_20261005\v10_17R_original\firmware\sof-apl.ri",
        "D:\PHASER360_WORK\continuation_20261005\v10_17R2_local\firmware\sof-apl.ri",
        "D:\PHASER360_WORK\v10_8C_local_build_audit\firmware\sof-apl.ri"
    )
    foreach ($candidate in $knownFirmware) {
        if (Test-FirmwareFile $candidate) {
            Write-RunLog "FIRMWARE_AUTO_FOUND=$candidate"
            return $candidate
        }
    }

    $roots = @(
        $PackageRoot,
        (Split-Path -Parent $PackageRoot),
        [Environment]::GetFolderPath("Desktop"),
        (Join-Path $env:USERPROFILE "Downloads"),
        "D:\PHASER360_WORK"
    ) | Select-Object -Unique

    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        foreach ($name in @("p360-f686.ri","sof-apl.ri")) {
            $hits = @(Get-ChildItem -LiteralPath $root -Filter $name -File -Recurse -ErrorAction SilentlyContinue)
            foreach ($hit in $hits) {
                if (Test-FirmwareFile $hit.FullName) {
                    return $hit.FullName
                }
            }
        }
    }

    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        $zips = @(Get-ChildItem -LiteralPath $root -Filter "PHASER360*v10_11B*.zip" -File -Recurse -ErrorAction SilentlyContinue)
        foreach ($zip in $zips) {
            try {
                $fw = Extract-FirmwareFromZip $zip.FullName
                if ($fw) { return $fw }
            } catch {
                Write-RunLog "Ignoring non-matching firmware archive: $($zip.FullName)"
            }
        }
    }

    throw "Exact f686 firmware was not found. Supply -FirmwarePath to p360-f686.ri, sof-apl.ri, or the audited v10.11B ZIP."
}

function Extract-FirmwareFromZip([string]$ZipPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $entry = $zip.Entries | Where-Object {
            $_.FullName -match "(?i)(^|/)(firmware/)?(sof-apl|p360-f686)\.ri$"
        } | Select-Object -First 1
        if (-not $entry) {
            throw "No candidate firmware entry in $ZipPath."
        }
        if (-not $script:Session) {
            New-RunSession "FW"
        }
        $out = Join-Path $script:Session "firmware-from-archive.ri"
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$out,$true)
        if (-not (Test-FirmwareFile $out)) {
            Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue
            throw "Firmware inside ZIP does not match exact f686 identity."
        }
        return $out
    } finally {
        $zip.Dispose()
    }
}

function Read-PackageInfo {
    if (-not (Test-Path -LiteralPath $PackageInfoPath -PathType Leaf)) {
        throw "PACKAGE_INFO.json is missing from the gate package."
    }
    return (Get-Content -LiteralPath $PackageInfoPath -Raw | ConvertFrom-Json)
}

function Get-PackageFolder([string]$RunMode) {
    if ($RunMode -eq "PreAudio") {
        return Join-Path $PackageRoot "preaudio"
    }
    if ($RunMode -eq "BoundedSpeaker") {
        return Join-Path $PackageRoot "bounded"
    }
    throw "No driver package for mode $RunMode."
}

function Assert-Package([string]$RunMode,$Info) {
    $folder = Get-PackageFolder $RunMode
    foreach ($name in @("P360SofAudio.inf","P360SofAudio.cat","P360SofAudio.sys")) {
        if (-not (Test-Path -LiteralPath (Join-Path $folder $name) -PathType Leaf)) {
            throw "Signed package file missing: $folder\$name"
        }
    }
    $sysHash = (Get-FileHash -LiteralPath (Join-Path $folder "P360SofAudio.sys") -Algorithm SHA256).Hash.ToLowerInvariant()
    $want = if ($RunMode -eq "PreAudio") {
        [string]$Info.PreAudioSysSha256
    } else {
        [string]$Info.BoundedSysSha256
    }
    if ($sysHash -ne $want.ToLowerInvariant()) {
        throw "$RunMode SYS hash mismatch: $sysHash != $want"
    }
    return $folder
}

function Import-TestCertificate($Info) {
    $cer = Join-Path $PackageRoot "cert\P360_TEST.cer"
    if (-not (Test-Path -LiteralPath $cer -PathType Leaf)) {
        throw "P360_TEST.cer is missing."
    }
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cer)
    $thumb = $cert.Thumbprint.ToUpperInvariant()
    if ($Info.CertificateThumbprint -and
        $thumb -ne ([string]$Info.CertificateThumbprint).ToUpperInvariant()) {
        throw "Test certificate thumbprint mismatch."
    }

    Invoke-Tool -Exe "certutil.exe" -Arguments @("-addstore","-f","Root",$cer) | Out-Null
    Invoke-Tool -Exe "certutil.exe" -Arguments @("-addstore","-f","TrustedPublisher",$cer) | Out-Null
    $script:State.CertificateThumbprint = $thumb
    Save-State
    return $thumb
}

function Remove-TestCertificate([string]$Thumbprint) {
    if (-not $Thumbprint) { return }
    Invoke-Tool -Exe "certutil.exe" -Arguments @("-delstore","Root",$Thumbprint) -AllowFailure | Out-Null
    Invoke-Tool -Exe "certutil.exe" -Arguments @("-delstore","TrustedPublisher",$Thumbprint) -AllowFailure | Out-Null
}

function Assert-CatalogSignature([string]$Folder) {
    $cat = Join-Path $Folder "P360SofAudio.cat"
    $sig = Get-AuthenticodeSignature -LiteralPath $cat
    if ($sig.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
        throw "Catalog signature is not valid after certificate import: $($sig.Status)"
    }
}

function Backup-OriginalDriver([string]$InstanceId) {
    $device = Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -eq $InstanceId
    } | Select-Object -First 1
    if (-not $device) {
        throw "Target disappeared before baseline capture."
    }

    $script:State.OriginalProblemCode = [int]$device.ConfigManagerErrorCode
    $script:State.OriginalService = [string]$device.Service
    $script:State.OriginalName = [string]$device.Name

    $driver = Get-SignedDriverOrNull $InstanceId
    if (-not $driver) {
        $script:State.OriginalHadDriver = $false
        $script:State.OriginalInfName = ""
        $script:State.OriginalDriverVersion = ""
        $script:State.OriginalProvider = ""
        $script:State.OriginalExportedInf = ""
        Save-State
        Write-RunLog ("ORIGINAL_DRIVER=UNBOUND CODE={0} SERVICE={1}" -f
            $script:State.OriginalProblemCode,$script:State.OriginalService)
        return
    }

    $inf = [string]$driver.InfName
    if ($inf -notmatch "(?i)^oem\d+\.inf$") {
        throw "Current driver '$inf' is not exportable as an OEM package; refusing destructive swap."
    }

    $backup = Join-Path $script:Session "original-driver"
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    Invoke-Tool -Exe "pnputil.exe" -Arguments @("/export-driver",$inf,$backup) | Out-Null

    $exportedInf = Get-ChildItem -LiteralPath $backup -Filter "*.inf" -File -Recurse | Select-Object -First 1
    if (-not $exportedInf) {
        throw "Original driver export did not produce an INF."
    }

    $script:State.OriginalHadDriver = $true
    $script:State.OriginalInfName = $inf
    $script:State.OriginalDriverVersion = [string]$driver.DriverVersion
    $script:State.OriginalProvider = [string]$driver.DriverProviderName
    $script:State.OriginalExportedInf = $exportedInf.FullName
    Save-State
    Write-RunLog ("ORIGINAL_DRIVER=BOUND INF={0} VERSION={1} PROVIDER={2}" -f
        $script:State.OriginalInfName,
        $script:State.OriginalDriverVersion,
        $script:State.OriginalProvider)
}

function Install-Firmware([string]$Firmware) {
    $dir = Join-Path $env:SystemRoot "System32\drivers\P360"
    $dest = Join-Path $dir "p360-f686.ri"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null

    if (Test-Path -LiteralPath $dest) {
        $backup = Join-Path $script:Session "original-p360-firmware.ri"
        Copy-Item -LiteralPath $dest -Destination $backup -Force
        $script:State.FirmwareHadOriginal = $true
        $script:State.FirmwareBackup = $backup
    } else {
        $script:State.FirmwareHadOriginal = $false
        $script:State.FirmwareBackup = ""
    }
    $script:State.FirmwareDestination = $dest
    Save-State

    Copy-Item -LiteralPath $Firmware -Destination $dest -Force
    if (-not (Test-FirmwareFile $dest)) {
        throw "Firmware identity changed after copy to system driver directory."
    }
}

function Restore-Firmware {
    if (-not $script:State -or -not $script:State.FirmwareDestination) { return }
    $dest = [string]$script:State.FirmwareDestination
    if ([bool]$script:State.FirmwareHadOriginal) {
        if (-not (Test-Path -LiteralPath $script:State.FirmwareBackup)) {
            throw "Original firmware backup is missing."
        }
        Copy-Item -LiteralPath $script:State.FirmwareBackup -Destination $dest -Force
    } else {
        Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
    }
}

function Get-InfVersion([string]$InfPath) {
    $text = Get-Content -LiteralPath $InfPath -Raw
    $match = [regex]::Match($text,"(?im)^\s*DriverVer\s*=\s*[^,]+,\s*([0-9.]+)\s*$")
    if (-not $match.Success) {
        throw "Cannot parse DriverVer from $InfPath."
    }
    return $match.Groups[1].Value
}

function Restart-Target([string]$InstanceId) {
    $res = Invoke-Tool -Exe "pnputil.exe" -Arguments @("/restart-device",$InstanceId) -AllowFailure
    if ($res.ExitCode -ne 0) {
        Write-RunLog "PNP_RESTART_EXIT=$($res.ExitCode) -- verifying postcondition instead of trusting pnputil exit code"
    }
    return $res
}

function Get-BoundDriverOrNull([string]$InstanceId) {
    return Get-SignedDriverOrNull $InstanceId
}

function Get-TargetByIdOrNull([string]$InstanceId) {
    return (Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -eq $InstanceId
    } | Select-Object -First 1)
}

function Test-BoundDriver(
    [string]$InstanceId,
    [string]$Version,
    [string]$Provider,
    [string]$Service
) {
    $device=Get-TargetByIdOrNull $InstanceId
    if (-not $device) {
        return $false
    }
    if ([string]$device.Service -ne $Service) {
        return $false
    }

    $driver=Get-BoundDriverOrNull $InstanceId
    if (-not $driver) {
        return $false
    }

    return (
        [string]$driver.DriverVersion -eq $Version -and
        [string]$driver.DriverProviderName -eq $Provider)
}

function Clear-TestTelemetry {
    if (Test-Path $TelemetryPath) {
        Remove-Item -Path $TelemetryPath -Recurse -Force -ErrorAction Stop
        Write-RunLog "STALE_TELEMETRY_CLEARED=YES"
    } else {
        Write-RunLog "STALE_TELEMETRY_CLEARED=NOT_PRESENT"
    }
}

function Remove-And-RescanTarget(
    [string]$InstanceId,
    [string]$ExpectedVersion,
    [string]$ExpectedProvider,
    [string]$ExpectedService,
    [int]$Seconds=20
) {
    Write-RunLog "TARGET_REENUM_BEGIN=$InstanceId"

    $remove=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/remove-device",$InstanceId) -AllowFailure
    if ($remove.ExitCode -ne 0) {
        throw "Exact ADSP child removal failed with exit code $($remove.ExitCode). No parent device was touched."
    }

    $deadline=(Get-Date).AddSeconds(8)
    do {
        Start-Sleep -Milliseconds 250
        if (-not (Get-TargetByIdOrNull $InstanceId)) {
            break
        }
    } while ((Get-Date) -lt $deadline)

    if (Get-TargetByIdOrNull $InstanceId) {
        throw "Exact ADSP child did not disappear after remove-device."
    }

    $scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure
    if ($scan.ExitCode -ne 0) {
        throw "PnP rescan failed with exit code $($scan.ExitCode)."
    }

    $deadline=(Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Milliseconds 500
        $device=Get-TargetByIdOrNull $InstanceId
        if ($device) {
            if ([string]$device.Service -eq $ExpectedService) {
                $driver=Get-BoundDriverOrNull $InstanceId
                if ($driver -and
                    [string]$driver.DriverVersion -eq $ExpectedVersion -and
                    [string]$driver.DriverProviderName -eq $ExpectedProvider) {
                    Write-RunLog ("TARGET_REENUM_BIND=PASS SERVICE={0} VERSION={1} INF={2}" -f
                        [string]$device.Service,
                        [string]$driver.DriverVersion,
                        [string]$driver.InfName)
                    return $device
                }
            }
        }
    } while ((Get-Date) -lt $deadline)

    $device=Get-TargetByIdOrNull $InstanceId
    $driver=Get-BoundDriverOrNull $InstanceId
    if ($device -and $driver) {
        throw ("Target re-enumerated with wrong binding: service={0}, inf={1}, provider={2}, version={3}." -f
            [string]$device.Service,
            [string]$driver.InfName,
            [string]$driver.DriverProviderName,
            [string]$driver.DriverVersion)
    }
    if ($device) {
        throw ("Target re-enumerated without expected driver: service={0}, code={1}." -f
            [string]$device.Service,
            [int]$device.ConfigManagerErrorCode)
    }
    throw "Target did not re-enumerate after exact child removal/rescan."
}

function Wait-TargetPresent([string]$InstanceId,[int]$Seconds=12) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Milliseconds 500
        $dev = Get-CimInstance Win32_PnPEntity | Where-Object {
            $_.PNPDeviceID -eq $InstanceId
        } | Select-Object -First 1
        if ($dev) {
            return $dev
        }
    } while ((Get-Date) -lt $deadline)
    throw "Target did not reappear within $Seconds seconds."
}

function Wait-TargetHealthy([string]$InstanceId,[int]$Seconds=12) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Milliseconds 500
        $dev = Get-CimInstance Win32_PnPEntity | Where-Object {
            $_.PNPDeviceID -eq $InstanceId
        } | Select-Object -First 1
        if ($dev -and [int]$dev.ConfigManagerErrorCode -eq 0) {
            return $dev
        }
    } while ((Get-Date) -lt $deadline)
    throw "Target did not return healthy within $Seconds seconds."
}

function Get-P360StoreEntries {
    return @(Get-WindowsDriver -Online -All | Where-Object {
        [string]$_.ProviderName -eq "PHASER360 Project"
    })
}

function Assert-NoStaleTestPackage {
    $stale = @(Get-P360StoreEntries | Where-Object {
        ([string]$_.Version -eq "2.0.100.1") -or
        ([string]$_.Version -eq "2.0.200.1")
    })
    if ($stale.Count -gt 0) {
        $names = ($stale | ForEach-Object { "$($_.Driver):$($_.Version)" }) -join ", "
        throw "Stale Phaser360 test package exists in Driver Store: $names. Run -Mode Restore before continuing."
    }
}

function Assert-SafeBaselineBeforeNewTest([string]$InstanceId) {
    $driver=Get-BoundDriverOrNull $InstanceId
    $device=Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -eq $InstanceId
    } | Select-Object -First 1

    if ($driver) {
        $version=[string]$driver.DriverVersion
        if ($version -eq "2.0.100.1" -or $version -eq "2.0.200.1") {
            throw "A Phaser360 test driver is still bound (version=$version). Run RESTORE_LAST_SESSION.cmd before any new audio test."
        }
    }

    if ($device -and [string]$device.Service -eq "P360SofAudio") {
        throw "P360SofAudio is still the active service. Run RESTORE_LAST_SESSION.cmd before any new audio test."
    }
}

function Install-TestPackage([string]$RunMode,$Info,[string]$InstanceId) {
    $folder = Assert-Package $RunMode $Info
    Assert-CatalogSignature $folder

    $inf = Join-Path $folder "P360SofAudio.inf"
    $wantVersion = Get-InfVersion $inf
    Assert-NoStaleTestPackage

    Clear-TestTelemetry

    $addResult = Invoke-Tool -Exe "pnputil.exe" -Arguments @("/add-driver",$inf) -AllowFailure

    $store = @(Get-P360StoreEntries | Where-Object {
        [string]$_.Version -eq $wantVersion
    })
    if ($store.Count -eq 1) {
        $script:State.TestInfName = [string]$store[0].Driver
        $script:State.TestDriverVersion = $wantVersion
        Save-State
    }

    if ($store.Count -ne 1) {
        throw "Could not identify exactly one staged $RunMode package in Driver Store."
    }
    if ($addResult.ExitCode -ne 0) {
        throw "Driver staging failed with exit code $($addResult.ExitCode)."
    }
    if ($addResult.Output -match "(?i)reboot is needed|restart is needed") {
        throw "Driver staging unexpectedly requested a reboot; refusing hardware execution."
    }

    Remove-And-RescanTarget $InstanceId $wantVersion "PHASER360 Project" "P360SofAudio" | Out-Null

    if (-not (Test-BoundDriver $InstanceId $wantVersion "PHASER360 Project" "P360SofAudio")) {
        throw "Freshly re-enumerated target is not bound to the requested P360SofAudio package."
    }
}

function Get-Telemetry {
    if (-not (Test-Path $TelemetryPath)) {
        return $null
    }
    $p = Get-ItemProperty -Path $TelemetryPath
    $fwRaw = [uint32]$p.FirmwareError
    $fwSigned = [BitConverter]::ToInt32([BitConverter]::GetBytes($fwRaw),0)
    return [pscustomobject]@{
        BuildFlags = [uint32]$p.BuildFlags
        Stage = [uint32]$p.Stage
        BootEpoch = [uint64]$p.BootEpoch
        FirmwareError = $fwSigned
        ReplyBytes = [uint32]$p.ReplyBytes
        FailureReason = [uint32]$p.FailureReason
        LastNtStatus = [uint32]$p.LastNtStatus
    }
}

function Wait-Telemetry {
    param(
        [uint32]$ExpectedFlags,
        [uint32]$MinimumStage,
        [int]$Seconds=12
    )
    $deadline=(Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Milliseconds 250
        $t=Get-Telemetry
        if ($t) {
            if ($t.BuildFlags -ne $ExpectedFlags) {
                throw "Loaded driver build flags mismatch: $($t.BuildFlags) != $ExpectedFlags."
            }
            if ($t.FailureReason -ne 0 -or $t.LastNtStatus -ne 0) {
                throw ("Driver reported failure: stage={0}, reason={1}, ntstatus=0x{2:X8}" -f $t.Stage,$t.FailureReason,$t.LastNtStatus)
            }
            if ($t.Stage -ge $MinimumStage) {
                return $t
            }
        }
    } while ((Get-Date) -lt $deadline)
    if ($t) {
        throw "Telemetry timeout: stage=$($t.Stage), expected >= $MinimumStage."
    }
    throw "Telemetry key was never created."
}

function Disable-TargetAndProveStop([string]$InstanceId,[uint32]$ExpectedFlags) {
    Invoke-Tool -Exe "pnputil.exe" -Arguments @("/disable-device",$InstanceId) | Out-Null
    $deadline=(Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 250
        $t=Get-Telemetry
        if ($t -and $t.BuildFlags -eq $ExpectedFlags -and $t.Stage -eq 120) {
            $script:State.StopProved = $true
            Save-State
            return $t
        }
    } while ((Get-Date) -lt $deadline)
    throw "D0 STOP was not proved by telemetry after device disable."
}

function Restore-OriginalDriver([string]$InstanceId) {
    if (-not $script:State) { return }

    if ($script:State.TestInfName) {
        Invoke-Tool -Exe "pnputil.exe" -Arguments @("/delete-driver",[string]$script:State.TestInfName,"/uninstall","/force") -AllowFailure | Out-Null
        $script:State.TestInfName = ""
        Save-State
    }

    # Remove any still-staged test package even if TestInfName was cleared by
    # a prior interrupted rollback.
    foreach ($entry in @(Get-P360StoreEntries | Where-Object {
        ([string]$_.Version -eq "2.0.100.1") -or
        ([string]$_.Version -eq "2.0.200.1")
    })) {
        if ($entry.Driver) {
            Invoke-Tool -Exe "pnputil.exe" -Arguments @(
                "/delete-driver",[string]$entry.Driver,"/uninstall","/force") -AllowFailure | Out-Null
        }
    }

    Invoke-Tool -Exe "pnputil.exe" -Arguments @("/enable-device",$InstanceId) -AllowFailure | Out-Null

    if ([bool]$script:State.OriginalHadDriver) {
        if (-not $script:State.OriginalExportedInf -or
            -not (Test-Path -LiteralPath $script:State.OriginalExportedInf)) {
            throw "Original driver backup is missing."
        }

        $restoreAdd=Invoke-Tool -Exe "pnputil.exe" -Arguments @(
            "/add-driver",
            [string]$script:State.OriginalExportedInf,
            "/install") -AllowFailure
        if ($restoreAdd.ExitCode -ne 0) {
            Write-RunLog "RESTORE_PNPUTIL_ADD_EXIT=$($restoreAdd.ExitCode) -- verifying actual binding"
        }

        $null=Restart-Target $InstanceId
        Start-Sleep -Milliseconds 750

        if (-not (Test-BoundDriver $InstanceId ([string]$script:State.OriginalDriverVersion) ([string]$script:State.OriginalProvider))) {
            Write-RunLog "RESTORE_RESTART_NOT_ENOUGH=YES; trying remove/scan re-enumeration"
            $remove=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/remove-device",$InstanceId) -AllowFailure
            Write-RunLog "RESTORE_REMOVE_DEVICE_EXIT=$($remove.ExitCode)"
            Start-Sleep -Milliseconds 750
            Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure | Out-Null

            $deadline=(Get-Date).AddSeconds(20)
            do {
                Start-Sleep -Milliseconds 500
                if (Test-BoundDriver $InstanceId ([string]$script:State.OriginalDriverVersion) ([string]$script:State.OriginalProvider)) {
                    Write-RunLog "RESTORE_REENUM_BIND=PASS"
                    break
                }
            } while ((Get-Date) -lt $deadline)
        }

        if (-not (Test-BoundDriver $InstanceId ([string]$script:State.OriginalDriverVersion) ([string]$script:State.OriginalProvider))) {
            $current=Get-BoundDriverOrNull $InstanceId
            $currentText=if ($current) {
                "INF=$($current.InfName) VERSION=$($current.DriverVersion) PROVIDER=$($current.DriverProviderName)"
            } else {
                "UNBOUND"
            }
            $script:State | Add-Member -NotePropertyName RebootRequired -NotePropertyValue $true -Force
            Save-State
            throw "Baseline restore requires one manual Windows reboot. Current=$currentText. Test packages are removed; original package remains staged."
        }

        Wait-TargetHealthy $InstanceId | Out-Null

        $driver=Get-SignedDriver $InstanceId
        if ([string]$driver.DriverVersion -ne [string]$script:State.OriginalDriverVersion) {
            throw "Restore verification failed: current driver version $($driver.DriverVersion), expected $($script:State.OriginalDriverVersion)."
        }
        if ([string]$driver.DriverProviderName -ne [string]$script:State.OriginalProvider) {
            throw "Restore verification failed: current provider $($driver.DriverProviderName), expected $($script:State.OriginalProvider)."
        }
        Write-RunLog "RESTORE_BOUND_BASELINE=PASS"
    } else {
        # The original DSP may legitimately be an unbound Code 28 child.
        # Removing our test package must return it to that exact baseline;
        # healthy Code 0 is NOT required in this branch.
        Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure | Out-Null
        $dev=Wait-TargetPresent $InstanceId

        $driver=Get-SignedDriverOrNull $InstanceId
        if ($driver) {
            throw ("Restore verification failed: originally-unbound target acquired driver INF={0}, provider={1}, version={2}." -f
                $driver.InfName,$driver.DriverProviderName,$driver.DriverVersion)
        }

        if ([int]$dev.ConfigManagerErrorCode -ne [int]$script:State.OriginalProblemCode) {
            throw ("Restore verification failed: originally-unbound target problem code is {0}, expected {1}." -f
                [int]$dev.ConfigManagerErrorCode,[int]$script:State.OriginalProblemCode)
        }

        if ([string]$dev.Service -ne [string]$script:State.OriginalService) {
            throw ("Restore verification failed: originally-unbound target service is '{0}', expected '{1}'." -f
                [string]$dev.Service,[string]$script:State.OriginalService)
        }

        Write-RunLog ("RESTORE_UNBOUND_BASELINE=PASS CODE={0}" -f
            [int]$dev.ConfigManagerErrorCode)
    }

    $script:State.RestoreVerified = $true
    Save-State
}

function Assert-PreAudioProof($Info,[string]$InstanceId,[string]$Firmware,[string]$PreAudioSys) {
    if (-not (Test-Path -LiteralPath $ProofPath -PathType Leaf)) {
        throw "No PRE-AUDIO PASS proof exists. Run -Mode PreAudio first."
    }
    $proof=Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
    $age=(Get-Date).ToUniversalTime() - [DateTime]::Parse([string]$proof.TimestampUtc).ToUniversalTime()
    if ($age.TotalDays -gt 7) {
        throw "PRE-AUDIO proof is older than 7 days; rerun PreAudio."
    }
    $fwHash=(Get-FileHash -LiteralPath $Firmware -Algorithm SHA256).Hash.ToLowerInvariant()
    $preHash=(Get-FileHash -LiteralPath $PreAudioSys -Algorithm SHA256).Hash.ToLowerInvariant()
    foreach ($check in @(
        @([string]$proof.TargetInstanceId,$InstanceId,"target"),
        @(([string]$proof.FirmwareSha256).ToLowerInvariant(),$fwHash,"firmware"),
        @(([string]$proof.PreAudioSysSha256).ToLowerInvariant(),$preHash,"pre-audio image"),
        @([string]$proof.HeadSha,[string]$Info.HeadSha,"build commit")
    )) {
        if ($check[0] -ne $check[1]) {
            throw "PRE-AUDIO proof mismatch for $($check[2])."
        }
    }
    if (-not [bool]$proof.Stopped -or [int]$proof.FirmwareError -ne -22 -or [int]$proof.ReplyBytes -ne 12) {
        throw "PRE-AUDIO proof is incomplete."
    }
}

function Write-PreAudioProof($Info,[string]$InstanceId,[string]$Firmware,[string]$PreAudioSys,$Telemetry) {
    New-Item -ItemType Directory -Path $ProofRoot -Force | Out-Null
    $proof=[ordered]@{
        TimestampUtc=(Get-Date).ToUniversalTime().ToString("o")
        HeadSha=[string]$Info.HeadSha
        TargetInstanceId=$InstanceId
        FirmwareSha256=(Get-FileHash -LiteralPath $Firmware -Algorithm SHA256).Hash.ToLowerInvariant()
        PreAudioSysSha256=(Get-FileHash -LiteralPath $PreAudioSys -Algorithm SHA256).Hash.ToLowerInvariant()
        FirmwareError=[int]$Telemetry.FirmwareError
        ReplyBytes=[int]$Telemetry.ReplyBytes
        Stopped=$true
    }
    $proof | ConvertTo-Json | Set-Content -LiteralPath $ProofPath -Encoding UTF8
}

function Load-RestoreState([string]$RequestedSession) {
    if ($RequestedSession) {
        $path=(Resolve-Path -LiteralPath $RequestedSession).Path
    } else {
        $root=Join-Path ([Environment]::GetFolderPath("Desktop")) "P360_AUDIO_SAFE"
        $candidate=Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Where-Object { Test-Path (Join-Path $_.FullName "STATE.json") } |
            Select-Object -First 1
        if (-not $candidate) {
            throw "No previous P360 session with STATE.json was found."
        }
        $path=$candidate.FullName
    }
    $script:Session=$path
    $script:LogPath=Join-Path $path "RESTORE.log"
    $script:State=Get-Content -LiteralPath (Join-Path $path "STATE.json") -Raw | ConvertFrom-Json
}

function Write-Report([string]$Result,[object]$Telemetry) {
    $report=[ordered]@{
        Mode=$Mode
        Result=$Result
        Session=$script:Session
        TargetInstanceId=$script:State.TargetInstanceId
        OriginalHadDriver=$script:State.OriginalHadDriver
        OriginalProblemCode=$script:State.OriginalProblemCode
        OriginalService=$script:State.OriginalService
        OriginalInfName=$script:State.OriginalInfName
        OriginalDriverVersion=$script:State.OriginalDriverVersion
        RestoreVerified=$script:State.RestoreVerified
        StopProved=$script:State.StopProved
        Telemetry=$Telemetry
    }
    $report | ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath (Join-Path $script:Session "RESULT.json") -Encoding UTF8
}

Assert-Administrator

if ($Mode -eq "Restore") {
    Load-RestoreState $SessionPath
    $targetId=[string]$script:State.TargetInstanceId
    try {
        Restore-OriginalDriver $targetId
        Restore-Firmware
        Remove-TestCertificate ([string]$script:State.CertificateThumbprint)
        Write-RunLog "RESTORE=PASS"
        exit 0
    } catch {
        Write-RunLog "RESTORE=FAIL $($_.Exception.Message)"
        exit 2
    }
}

New-RunSession $Mode | Out-Null
Write-RunLog "PHASER360 AUDIO GATE"
Write-RunLog "MODE=$Mode"
Write-RunLog "NO_AUTO_REBOOT=YES"

$info=Read-PackageInfo
$target=Get-TargetDevice
$bus=Get-BusDevice
$targetId=[string]$target.PNPDeviceID

$script:State=[pscustomobject]@{
    TargetInstanceId=$targetId
    OriginalHadDriver=$false
    OriginalProblemCode=[int]$target.ConfigManagerErrorCode
    OriginalService=[string]$target.Service
    OriginalName=[string]$target.Name
    OriginalInfName=""
    OriginalDriverVersion=""
    OriginalProvider=""
    OriginalExportedInf=""
    TestInfName=""
    TestDriverVersion=""
    CertificateThumbprint=""
    FirmwareHadOriginal=$false
    FirmwareBackup=""
    FirmwareDestination=""
    StopProved=$false
    RestoreVerified=$false
}
Save-State

Write-RunLog "TARGET=$targetId"
Write-RunLog ("TARGET_NAME={0} CODE={1} SERVICE={2}" -f
    [string]$target.Name,
    [int]$target.ConfigManagerErrorCode,
    [string]$target.Service)
Write-RunLog "BUS=$($bus.PNPDeviceID) SERVICE=$($bus.Service)"
Assert-TestSigning

$firmware=Resolve-Firmware $FirmwarePath
Write-RunLog "FIRMWARE=$firmware"
Write-RunLog "FIRMWARE_SHA256=$ExpectedFirmwareSha256"

$preFolder=Assert-Package "PreAudio" $info
$boundedFolder=Assert-Package "BoundedSpeaker" $info
Write-RunLog "PACKAGE_HEAD=$($info.HeadSha)"

if ($Mode -eq "Audit") {
    $amp = Get-AmpDevice
    Write-RunLog "AMP=$($amp.PNPDeviceID) SERVICE=$($amp.Service)"
    Write-RunLog "AUDIT=PASS"
    Write-Report "PASS" $null
    exit 0
}

if ($Mode -eq "PreAudio" -or $Mode -eq "BoundedSpeaker" -or $Mode -eq "Audio") {
    Assert-SafeBaselineBeforeNewTest $targetId
}
if ($Mode -eq "BoundedSpeaker" -or $Mode -eq "Audio") {
    $amp=Get-AmpDevice
    Write-RunLog "AMP=$($amp.PNPDeviceID) SERVICE=$($amp.Service)"
}
if ($Mode -eq "BoundedSpeaker") {
    Assert-PreAudioProof $info $targetId $firmware (Join-Path $preFolder "P360SofAudio.sys")
    Write-RunLog "PREAUDIO_PROOF=PASS"
}

$telemetry=$null
$success=$false
try {
    Backup-OriginalDriver $targetId
    Install-Firmware $firmware
    Import-TestCertificate $info | Out-Null

    if ($Mode -eq "PreAudio" -or $Mode -eq "Audio") {
        Install-TestPackage "PreAudio" $info $targetId
        $telemetry=Wait-Telemetry -ExpectedFlags 3 -MinimumStage 50
        if ($telemetry.FirmwareError -ne -22 -or $telemetry.ReplyBytes -ne 12) {
            throw "IPC3 proof reply mismatch: error=$($telemetry.FirmwareError), bytes=$($telemetry.ReplyBytes)."
        }
        Write-RunLog "FW_READY_IRQ_IPC_PROOF=PASS"
        $stopTelemetry=Disable-TargetAndProveStop $targetId 3
        Write-RunLog "PREAUDIO_STOP_PROOF=PASS"

        if ($Mode -eq "PreAudio") {
            $success=$true
        } else {
            Write-PreAudioProof $info $targetId $firmware (Join-Path $preFolder "P360SofAudio.sys") $telemetry
            Write-RunLog "PREAUDIO_GATE=PASS"
            Write-RunLog "AUDIO_PHASE_SWITCH=BEGIN"

            Restore-OriginalDriver $targetId
            Write-RunLog "PREAUDIO_DRIVER_RESTORE=PASS"
            $script:State.RestoreVerified=$false
            $script:State.StopProved=$false
            Save-State

            Install-TestPackage "BoundedSpeaker" $info $targetId
            $telemetry=Wait-Telemetry -ExpectedFlags 31 -MinimumStage 110
            if ($telemetry.Stage -ne 110) {
                throw "Bounded tone did not terminate at TONE_COMPLETE."
            }
            Write-RunLog "BOUNDED_TONE_250MS=PASS"
            $stopTelemetry=Disable-TargetAndProveStop $targetId 31
            Write-RunLog "AUDIO_STOP_PROOF=PASS"
            $success=$true
        }
    } elseif ($Mode -eq "BoundedSpeaker") {
        Install-TestPackage "BoundedSpeaker" $info $targetId
        $telemetry=Wait-Telemetry -ExpectedFlags 31 -MinimumStage 110
        if ($telemetry.Stage -ne 110) {
            throw "Bounded tone did not terminate at TONE_COMPLETE."
        }
        Write-RunLog "BOUNDED_TONE_250MS=PASS"
        $stopTelemetry=Disable-TargetAndProveStop $targetId 31
        Write-RunLog "STOP_PROOF=PASS"
        $success=$true
    }
} catch {
    Write-RunLog "TEST=FAIL $($_.Exception.Message)"
} finally {
    try {
        Restore-OriginalDriver $targetId
        Write-RunLog "DRIVER_RESTORE=PASS"
    } catch {
        Write-RunLog "DRIVER_RESTORE=FAIL $($_.Exception.Message)"
        $success=$false
    }
    try {
        Restore-Firmware
        Write-RunLog "FIRMWARE_RESTORE=PASS"
    } catch {
        Write-RunLog "FIRMWARE_RESTORE=FAIL $($_.Exception.Message)"
        $success=$false
    }
    try {
        Remove-TestCertificate ([string]$script:State.CertificateThumbprint)
        Write-RunLog "CERT_CLEANUP=PASS"
    } catch {
        Write-RunLog "CERT_CLEANUP=FAIL $($_.Exception.Message)"
        $success=$false
    }
}

if ($success -and $Mode -eq "PreAudio") {
    Write-PreAudioProof $info $targetId $firmware (Join-Path $preFolder "P360SofAudio.sys") $telemetry
    Write-RunLog "PREAUDIO_GATE=PASS"
}
if ($success -and $Mode -eq "BoundedSpeaker") {
    Write-RunLog "SPEAKER_GATE=PASS"
}
if ($success -and $Mode -eq "Audio") {
    Write-RunLog "AUDIO_GATE=PASS"
}

Write-Report $(if ($success) {"PASS"} else {"FAIL"}) $telemetry
Write-RunLog "RESULT_DIR=$Session"

if ($success) { exit 0 }
exit 2
