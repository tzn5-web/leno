param(
    [ValidateSet("Audio","Restore")]
    [string]$Mode = "Audio",
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
    if ($RunMode -eq "FinalSpeaker") {
        return Join-Path $PackageRoot "final"
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
    } elseif ($RunMode -eq "BoundedSpeaker") {
        [string]$Info.BoundedSysSha256
    } else {
        [string]$Info.FinalSpeakerSysSha256
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

    foreach ($store in @("Root","TrustedPublisher")) {
        $path="Cert:\LocalMachine\$store\$Thumbprint"
        if (Test-Path -LiteralPath $path) {
            throw "Test certificate cleanup verification failed: $path still exists."
        }
    }
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
        if (-not (Test-Path -LiteralPath $dest -PathType Leaf)) {
            throw "Firmware restore verification failed: original destination is missing."
        }
        $want=(Get-FileHash -LiteralPath $script:State.FirmwareBackup -Algorithm SHA256).Hash
        $have=(Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
        if ($have -ne $want) {
            throw "Firmware restore verification failed: restored hash differs from original backup."
        }
    } else {
        Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $dest) {
            throw "Firmware restore verification failed: temporary P360 firmware still exists."
        }
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

function Get-PnpPropertyData([string]$InstanceId,[string]$KeyName) {
    try {
        $p=Get-PnpDeviceProperty -InstanceId $InstanceId -KeyName $KeyName -ErrorAction Stop
        if ($p -and $null -ne $p.Data) { return [string]$p.Data }
    } catch { return $null }
    return $null
}

function Get-LiveDriverIdentityOrNull([string]$InstanceId) {
    $inf=Get-PnpPropertyData $InstanceId "DEVPKEY_Device_DriverInfPath"
    if (-not $inf) { return $null }
    return [pscustomobject]@{
        InfName = $inf
        DriverVersion = (Get-PnpPropertyData $InstanceId "DEVPKEY_Device_DriverVersion")
        DriverProviderName = (Get-PnpPropertyData $InstanceId "DEVPKEY_Device_DriverProvider")
        Source = "PnPProperty"
    }
}

function Get-BoundDriverOrNull([string]$InstanceId) {
    $live=Get-LiveDriverIdentityOrNull $InstanceId
    if ($live) { return $live }
    $wmi=Get-SignedDriverOrNull $InstanceId
    if ($wmi) {
        $wmi | Add-Member -NotePropertyName Source -NotePropertyValue "Win32_PnPSignedDriver" -Force
    }
    return $wmi
}

function Get-TargetByIdOrNull([string]$InstanceId) {
    return (Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -eq $InstanceId
    } | Select-Object -First 1)
}

function Get-DeviceProblemStatusHex([string]$InstanceId) {
    try {
        $property=Get-PnpDeviceProperty -InstanceId $InstanceId -KeyName "DEVPKEY_Device_ProblemStatus" -ErrorAction Stop
        if ($property -and $null -ne $property.Data) {
            $raw=[int64]$property.Data
            return ("0x{0:X8}" -f [uint32]($raw -band 0xFFFFFFFFL))
        }
    } catch {
        return "<unavailable>"
    }
    return "<unavailable>"
}

function Get-PrepareStepName([uint32]$Step) {
    switch ($Step) {
        0  { return "NONE" }
        1  { return "HOST_BEGIN" }
        2  { return "BUS_QUERY_INTERFACE" }
        3  { return "BUS_ABI_VALIDATE" }
        4  { return "BUS_GET_RESOURCES" }
        5  { return "BUS_RESOURCE_VALIDATE" }
        6  { return "PCI_IDENTITY" }
        7  { return "NHLT_PARSE" }
        8  { return "STATE_RESOURCES_OK" }
        9  { return "BOOT_ADAPTER_INIT" }
        10 { return "RUNTIME_CREATE" }
        11 { return "CSAUDIO_OPEN" }
        12 { return "PREPARE_COMPLETE" }
        default { return "UNKNOWN_$Step" }
    }
}

function Get-TargetDiagnosticText([string]$InstanceId) {
    $dev=Get-TargetByIdOrNull $InstanceId
    $drv=Get-BoundDriverOrNull $InstanceId
    if (-not $dev) {
        return "device=<missing>"
    }
    return ("service={0}, cmcode={1}, status={2}, problemStatus={3}, inf={4}, provider={5}, version={6}, driverSource={7}" -f
        [string]$dev.Service,
        [int]$dev.ConfigManagerErrorCode,
        [string]$dev.Status,
        (Get-DeviceProblemStatusHex $InstanceId),
        $(if ($drv) {[string]$drv.InfName} else {"<none>"}),
        $(if ($drv) {[string]$drv.DriverProviderName} else {"<none>"}),
        $(if ($drv) {[string]$drv.DriverVersion} else {"<none>"}),
        $(if ($drv -and $drv.PSObject.Properties["Source"]) {[string]$drv.Source} else {"<unknown>"}))
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
                    Write-RunLog ("TARGET_REENUM_BOUND SERVICE={0} VERSION={1} INF={2} CODE={3} STATUS={4} PROBLEMSTATUS={5}" -f
                        [string]$device.Service,
                        [string]$driver.DriverVersion,
                        [string]$driver.InfName,
                        [int]$device.ConfigManagerErrorCode,
                        [string]$device.Status,
                        (Get-DeviceProblemStatusHex $InstanceId))

                    if ([int]$device.ConfigManagerErrorCode -eq 0) {
                        Write-RunLog "TARGET_REENUM_BIND=PASS HEALTHY=YES"
                        return $device
                    }

                    # One bounded user-mode repair attempt is allowed in PRE-AUDIO.
                    # It never touches the parent bus and cannot reach speaker code.
                    Write-RunLog ("TARGET_START_REPAIR=BEGIN CODE={0}" -f [int]$device.ConfigManagerErrorCode)
                    $null=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/enable-device",$InstanceId) -AllowFailure
                    $null=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/restart-device",$InstanceId) -AllowFailure
                    $null=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure

                    $repairDeadline=(Get-Date).AddSeconds(8)
                    do {
                        Start-Sleep -Milliseconds 500
                        $device=Get-TargetByIdOrNull $InstanceId
                        if ($device -and
                            [int]$device.ConfigManagerErrorCode -eq 0 -and
                            (Test-BoundDriver $InstanceId $ExpectedVersion $ExpectedProvider $ExpectedService)) {
                            Write-RunLog "TARGET_START_REPAIR=PASS"
                            Write-RunLog "TARGET_REENUM_BIND=PASS HEALTHY=YES AFTER_REPAIR=YES"
                            return $device
                        }
                    } while ((Get-Date) -lt $repairDeadline)

                    $t=Get-Telemetry
                    $prepareText=if ($t) {
                        "{0}({1}) detail={2} prepareNtStatus=0x{3:X8}({4}) failure={5} lastNtStatus=0x{6:X8}({7})" -f
                            (Get-PrepareStepName $t.PrepareStep),$t.PrepareStep,
                            (Get-PrepareDetailText $t.PrepareStep $t.PrepareDetail),
                            $t.PrepareNtStatus,(Get-NtStatusName $t.PrepareNtStatus),
                            $t.FailureReason,$t.LastNtStatus,(Get-NtStatusName $t.LastNtStatus)
                    } else {
                        "<no telemetry>"
                    }
                    throw ("P360SofAudio bound but device start failed after one repair attempt. {0}; telemetry={1}" -f
                        (Get-TargetDiagnosticText $InstanceId),$prepareText)
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

function Test-IsReservedGateVersion([string]$Version) {
    return $Version -in @("2.0.100.1","2.0.101.1","2.0.200.1","2.0.201.1","2.0.301.1","2.0.302.1")
}

function Assert-NoStaleTestPackage {
    $stale = @(Get-P360StoreEntries | Where-Object {
        (Test-IsReservedGateVersion ([string]$_.Version))
    })
    if ($stale.Count -gt 0) {
        $names = ($stale | ForEach-Object { "$($_.Driver):$($_.Version)" }) -join ", "
        throw "Stale Phaser360 test package exists in Driver Store: $names. Run -Mode Restore before continuing."
    }
}

function Assert-SafeBaselineBeforeNewTest([string]$InstanceId) {
    $device=Get-TargetByIdOrNull $InstanceId
    $driver=Get-BoundDriverOrNull $InstanceId

    if (-not $device) {
        throw "ADSP target is missing before test."
    }
    if ([int]$device.ConfigManagerErrorCode -ne 0) {
        throw "ADSP baseline is not healthy; code=$($device.ConfigManagerErrorCode)."
    }
    if ([string]$device.Service -ne "P360AdspProbe") {
        throw "ADSP baseline service is '$($device.Service)', expected P360AdspProbe."
    }
    if (-not $driver) {
        throw "ADSP baseline has no signed-driver record."
    }
    if ([string]$driver.DriverProviderName -ne "PHASER360 Project" -or
        [string]$driver.DriverVersion -ne "1.1.0.0") {
        throw ("ADSP baseline mismatch: provider={0}, version={1}; expected PHASER360 Project 1.1.0.0." -f
            [string]$driver.DriverProviderName,[string]$driver.DriverVersion)
    }

    $stale=@(Get-P360StoreEntries | Where-Object {
        (Test-IsReservedGateVersion ([string]$_.Version))
    })
    if ($stale.Count -ne 0) {
        $names=($stale | ForEach-Object { "$($_.Driver):$($_.Version)" }) -join ", "
        throw "Stale Phaser360 test packages remain in Driver Store: $names."
    }

    Write-RunLog ("BASELINE_VERIFIED=PASS SERVICE={0} VERSION={1} INF={2}" -f
        [string]$device.Service,[string]$driver.DriverVersion,[string]$driver.InfName)
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
    $prepareStep=0
    $prepareDetail=0
    $prepareNtStatus=0
    if ($p.PSObject.Properties["PrepareStep"]) {
        $prepareStep=[uint32]$p.PrepareStep
    }
    if ($p.PSObject.Properties["PrepareDetail"]) {
        $prepareDetail=[uint32]$p.PrepareDetail
    }
    if ($p.PSObject.Properties["PrepareNtStatus"]) {
        $prepareNtStatus=[uint32]$p.PrepareNtStatus
    }
    return [pscustomobject]@{
        BuildFlags = [uint32]$p.BuildFlags
        Stage = [uint32]$p.Stage
        BootEpoch = [uint64]$p.BootEpoch
        FirmwareError = $fwSigned
        ReplyBytes = [uint32]$p.ReplyBytes
        FailureReason = [uint32]$p.FailureReason
        LastNtStatus = [uint32]$p.LastNtStatus
        PrepareStep = $prepareStep
        PrepareDetail = $prepareDetail
        PrepareNtStatus = $prepareNtStatus
    }
}

function Get-PrepareDetailText([uint32]$Step,[uint32]$Detail) {
    if ($Detail -eq 0) { return "none" }
    if ($Step -eq 3) {
        $pairs=@(@(1,"INTERFACE.Size"),@(2,"INTERFACE.Version"),@(4,"CtlrDevId"),@(8,"Context"),
            @(16,"GetResources"),@(32,"SetDSPPowerState"),@(64,"RegisterInterrupt"),
            @(128,"UnregisterInterrupt"),@(256,"GetRenderStream"),@(512,"GetCaptureStream"),
            @(1024,"FreeStream"),@(2048,"PrepareDSP"),@(4096,"CleanupDSP"),
            @(8192,"TriggerDSP"),@(16384,"StreamPosition"))
        $bad=@(); foreach($p in $pairs){if(($Detail-band[uint32]$p[0])-ne 0){$bad+=$p[1]}}
        return "ABI_BAD=" + ($bad -join ",")
    }
    if ($Step -eq 5) {
        $pairs=@(@(1,"HDA.Base"),@(2,"HDA.Len<0x4000"),@(4,"DSP.Base"),@(8,"DSP.Len<0xA2000"),
            @(16,"PPCAP"),@(32,"NHLT.ptr"),@(64,"NHLT.size"),@(128,"PCI.GetBusData"),@(256,"PCI.SetBusData"))
        $bad=@(); foreach($p in $pairs){if(($Detail-band[uint32]$p[0])-ne 0){$bad+=$p[1]}}
        return "RESOURCE_BAD=" + ($bad -join ",")
    }
    if ($Step -eq 6) {
        if (($Detail-band 0x40000000)-ne 0) { return ("PCI_READ_SHORT@0x{0:X}" -f ($Detail-band 0xffff)) }
        if (($Detail-band 0x20000000)-ne 0) { return ("PCI_VALIDATE_RC=-{0}" -f ($Detail-band 0xffff)) }
        if (($Detail-band 0x10000000)-ne 0) {
            $cmd=$Detail-band 0xffff
            return ("PCI_COMMAND=0x{0:X4} MEMORY={1} BUS_MASTER={2}" -f $cmd,[bool]($cmd-band 2),[bool]($cmd-band 4))
        }
        return ("PCI_COMMAND=0x{0:X4}" -f ($Detail-band 0xffff))
    }
    if ($Step -eq 7) {
        return ("NHLT_LEN={0} DMIC={1} SSP1_RENDER={2} SSP2_RENDER={3} SSP2_CAPTURE={4}" -f
            ($Detail-band 0xffff),[bool]($Detail-band 0x10000),[bool]($Detail-band 0x20000),
            [bool]($Detail-band 0x40000),[bool]($Detail-band 0x80000))
    }
    if ($Step -eq 10) {
        switch ($Detail) {
            1 { return "WDF_SPINLOCK_CREATE" }
            2 { return "WDF_DPC_CREATE" }
            3 { return "RUNTIME_CREATE_COMPLETE" }
            default { return ("RUNTIME_DETAIL=0x{0:X8}" -f $Detail) }
        }
    }
    return ("0x{0:X8}" -f $Detail)
}

function Get-NtStatusName([uint32]$Status) {
    switch ($Status) {
        0x00000000 { return "STATUS_SUCCESS" }
        0xC0200210 { return "STATUS_WDF_SYNCHRONIZATION_SCOPE_INVALID" }
        0xC0200211 { return "STATUS_WDF_EXECUTION_LEVEL_INVALID" }
        0xC0200212 { return "STATUS_WDF_PARENT_NOT_SPECIFIED" }
        0xC000000D { return "STATUS_INVALID_PARAMETER" }
        0xC000009A { return "STATUS_INSUFFICIENT_RESOURCES" }
        default { return ("NTSTATUS_0x{0:X8}" -f $Status) }
    }
}

function Format-TelemetryDiagnosis([object]$Telemetry,[string]$InstanceId) {
    $deviceText=Get-TargetDiagnosticText $InstanceId
    if (-not $Telemetry) {
        return "telemetry=<missing>; $deviceText"
    }
    return ("stage={0}, flags={1}, bootEpoch={2}, prepare={3}({4}), detail={5}, prepareNtStatus=0x{6:X8}({7}), failure={8}, lastNtStatus=0x{9:X8}({10}), fwError={11}, replyBytes={12}; {13}" -f
        $Telemetry.Stage,$Telemetry.BuildFlags,$Telemetry.BootEpoch,
        (Get-PrepareStepName $Telemetry.PrepareStep),$Telemetry.PrepareStep,
        (Get-PrepareDetailText $Telemetry.PrepareStep $Telemetry.PrepareDetail),
        $Telemetry.PrepareNtStatus,(Get-NtStatusName $Telemetry.PrepareNtStatus),
        $Telemetry.FailureReason,$Telemetry.LastNtStatus,(Get-NtStatusName $Telemetry.LastNtStatus),
        $Telemetry.FirmwareError,$Telemetry.ReplyBytes,$deviceText)
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
                throw ("Driver reported failure: {0}" -f (Format-TelemetryDiagnosis $t $script:State.TargetInstanceId))
            }
            if ($t.Stage -ge $MinimumStage) {
                return $t
            }
        }
    } while ((Get-Date) -lt $deadline)
    if ($t) {
        throw ("Telemetry timeout: expected stage >= {0}; {1}" -f
            $MinimumStage,(Format-TelemetryDiagnosis $t $script:State.TargetInstanceId))
    }
    throw ("Telemetry key was never created; {0}" -f
        (Get-TargetDiagnosticText $script:State.TargetInstanceId))
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

    # First remove the exact ADSP devnode. This prevents a stale selected
    # package from surviving only in the existing devnode after Driver Store
    # cleanup.
    $device=Get-TargetByIdOrNull $InstanceId
    if ($device) {
        $remove=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/remove-device",$InstanceId) -AllowFailure
        if ($remove.ExitCode -ne 0) {
            $script:State | Add-Member -NotePropertyName RebootRequired -NotePropertyValue $true -Force
            Save-State
            throw "Restore could not remove exact ADSP child; exit=$($remove.ExitCode). A Windows restart is required before another audio-gate run."
        }

        $deadline=(Get-Date).AddSeconds(8)
        do {
            Start-Sleep -Milliseconds 250
            if (-not (Get-TargetByIdOrNull $InstanceId)) {
                break
            }
        } while ((Get-Date) -lt $deadline)

        if (Get-TargetByIdOrNull $InstanceId) {
            $script:State | Add-Member -NotePropertyName RebootRequired -NotePropertyValue $true -Force
            Save-State
            throw "Restore could not prove ADSP child removal. A Windows restart is required before another audio-gate run."
        }
    }

    # Remove every reserved hardware-gate package. Do not use /uninstall here:
    # the devnode is already gone, so Driver Store cleanup cannot leave the
    # test image active.
    foreach ($entry in @(Get-P360StoreEntries | Where-Object {
        (Test-IsReservedGateVersion ([string]$_.Version))
    })) {
        if ($entry.Driver) {
            $delete=Invoke-Tool -Exe "pnputil.exe" -Arguments @(
                "/delete-driver",[string]$entry.Driver,"/force") -AllowFailure
            Write-RunLog ("RESTORE_DELETE_TEST_PACKAGE={0} EXIT={1}" -f
                [string]$entry.Driver,$delete.ExitCode)
        }
    }

    $script:State.TestInfName = ""
    $script:State.TestDriverVersion = ""
    Save-State

    if ([bool]$script:State.OriginalHadDriver) {
        if (-not $script:State.OriginalExportedInf -or
            -not (Test-Path -LiteralPath $script:State.OriginalExportedInf)) {
            throw "Original driver backup is missing."
        }

        # Stage the exported baseline only. A fresh scan below selects it for
        # the newly-created ADSP devnode.
        $restoreAdd=Invoke-Tool -Exe "pnputil.exe" -Arguments @(
            "/add-driver",
            [string]$script:State.OriginalExportedInf) -AllowFailure
        Write-RunLog "RESTORE_STAGE_BASELINE_EXIT=$($restoreAdd.ExitCode)"

        $scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure
        if ($scan.ExitCode -ne 0) {
            $script:State | Add-Member -NotePropertyName RebootRequired -NotePropertyValue $true -Force
            Save-State
            throw "Restore PnP scan failed with exit code $($scan.ExitCode). A Windows restart is required before another audio-gate run."
        }

        $deadline=(Get-Date).AddSeconds(20)
        do {
            Start-Sleep -Milliseconds 500
            $dev=Get-TargetByIdOrNull $InstanceId
            $driver=Get-BoundDriverOrNull $InstanceId
            if ($dev -and $driver -and
                [string]$dev.Service -eq [string]$script:State.OriginalService -and
                [string]$driver.DriverVersion -eq [string]$script:State.OriginalDriverVersion -and
                [string]$driver.DriverProviderName -eq [string]$script:State.OriginalProvider) {

                if ([int]$dev.ConfigManagerErrorCode -ne [int]$script:State.OriginalProblemCode) {
                    $enable=Invoke-Tool -Exe "pnputil.exe" -Arguments @(
                        "/enable-device",$InstanceId) -AllowFailure
                    Write-RunLog "RESTORE_ENABLE_EXIT=$($enable.ExitCode)"
                    Start-Sleep -Milliseconds 750
                    $dev=Get-TargetByIdOrNull $InstanceId
                }

                if ($dev -and
                    [int]$dev.ConfigManagerErrorCode -eq [int]$script:State.OriginalProblemCode) {
                    Write-RunLog ("RESTORE_BOUND_BASELINE=PASS SERVICE={0} CODE={1} VERSION={2} INF={3}" -f
                        [string]$dev.Service,
                        [int]$dev.ConfigManagerErrorCode,
                        [string]$driver.DriverVersion,
                        [string]$driver.InfName)
                    Assert-NoStaleTestPackage
                    $script:State.RestoreVerified = $true
                    $script:State | Add-Member -NotePropertyName RebootRequired -NotePropertyValue $false -Force
                    Save-State
                    return
                }
            }
        } while ((Get-Date) -lt $deadline)

        $dev=Get-TargetByIdOrNull $InstanceId
        $driver=Get-BoundDriverOrNull $InstanceId
        $script:State | Add-Member -NotePropertyName RebootRequired -NotePropertyValue $true -Force
        Save-State
        throw ("Baseline restore did not bind after fresh child re-enumeration. service={0}, code={1}, inf={2}, provider={3}, version={4}. A Windows restart is required before another audio-gate run." -f
            $(if ($dev) {[string]$dev.Service} else {"<missing>"}),
            $(if ($dev) {[int]$dev.ConfigManagerErrorCode} else {-1}),
            $(if ($driver) {[string]$driver.InfName} else {"<none>"}),
            $(if ($driver) {[string]$driver.DriverProviderName} else {"<none>"}),
            $(if ($driver) {[string]$driver.DriverVersion} else {"<none>"}))
    }

    # Originally-unbound baseline.
    $scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure
    if ($scan.ExitCode -ne 0) {
        throw "Restore PnP scan failed with exit code $($scan.ExitCode)."
    }

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

    Assert-NoStaleTestPackage
    Write-RunLog ("RESTORE_UNBOUND_BASELINE=PASS CODE={0}" -f
        [int]$dev.ConfigManagerErrorCode)
    $script:State.RestoreVerified = $true
    $script:State | Add-Member -NotePropertyName RebootRequired -NotePropertyValue $false -Force
    Save-State
}

function Find-RecoverableSession([string]$InstanceId) {
    $root=Join-Path ([Environment]::GetFolderPath("Desktop")) "P360_AUDIO_SAFE"
    if (-not (Test-Path -LiteralPath $root)) {
        return $null
    }

    foreach ($dir in @(Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)) {
        $statePath=Join-Path $dir.FullName "STATE.json"
        if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
            continue
        }
        try {
            $candidate=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        } catch {
            continue
        }

        if ([string]$candidate.TargetInstanceId -ne $InstanceId) {
            continue
        }
        if (-not [bool]$candidate.OriginalHadDriver) {
            continue
        }
        if ([string]$candidate.OriginalService -ne "P360AdspProbe" -or
            [string]$candidate.OriginalDriverVersion -ne "1.1.0.0" -or
            [string]$candidate.OriginalProvider -ne "PHASER360 Project") {
            continue
        }
        if (-not $candidate.OriginalExportedInf -or
            -not (Test-Path -LiteralPath ([string]$candidate.OriginalExportedInf) -PathType Leaf)) {
            continue
        }

        return [pscustomobject]@{
            Session=$dir.FullName
            State=$candidate
        }
    }

    return $null
}

function Current-BaselineNeedsRecovery([string]$InstanceId) {
    $device=Get-TargetByIdOrNull $InstanceId
    $driver=Get-BoundDriverOrNull $InstanceId
    $stale=@(Get-P360StoreEntries | Where-Object {
        (Test-IsReservedGateVersion ([string]$_.Version))
    })

    if ($stale.Count -gt 0) { return $true }
    if ($device -and [string]$device.Service -eq "P360SofAudio") { return $true }
    if ($driver -and
        (Test-IsReservedGateVersion ([string]$driver.DriverVersion))) { return $true }

    return $false
}

function Schedule-AudioResumeAfterManualReboot {
    $launcher=Join-Path $PackageRoot "START_AUDIO_TEST.cmd"
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
        return
    }

    $runOnce="HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce"
    New-Item -Path $runOnce -Force | Out-Null
    $command='cmd.exe /c ""{0}""' -f $launcher
    New-ItemProperty -Path $runOnce -Name "P360AudioGateResume" -Value $command -PropertyType String -Force | Out-Null
    Write-RunLog "RESUME_AFTER_REBOOT_SCHEDULED=YES"
}

function Recover-PreviousBaselineIfNeeded([string]$InstanceId) {
    if (-not (Current-BaselineNeedsRecovery $InstanceId)) {
        return
    }

    Write-RunLog "PREVIOUS_TEST_STATE_DETECTED=YES"
    $candidate=Find-RecoverableSession $InstanceId
    if (-not $candidate) {
        throw "Test binding is present but no valid saved P360AdspProbe 1.1.0.0 baseline was found."
    }

    $savedSession=$script:Session
    $savedLog=$script:LogPath
    $savedState=$script:State

    $script:Session=[string]$candidate.Session
    $script:LogPath=Join-Path $script:Session "AUTO_RECOVERY.log"
    $script:State=$candidate.State

    try {
        Write-RunLog "AUTO_BASELINE_RECOVERY=BEGIN"
        Restore-OriginalDriver $InstanceId
        Restore-Firmware
        Remove-TestCertificate ([string]$script:State.CertificateThumbprint)
        Write-RunLog "AUTO_BASELINE_RECOVERY=PASS"
    } catch {
        $needsReboot=$false
        if ($script:State.PSObject.Properties["RebootRequired"]) {
            $needsReboot=[bool]$script:State.RebootRequired
        }
        if ($needsReboot) {
            Schedule-AudioResumeAfterManualReboot
            Write-RunLog "AUTO_BASELINE_RECOVERY=REBOOT_REQUIRED"
        }
        throw
    } finally {
        $script:Session=$savedSession
        $script:LogPath=$savedLog
        $script:State=$savedState
    }

    Assert-SafeBaselineBeforeNewTest $InstanceId
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

function Get-StateBool([string]$Name) {
    if ($script:State -and $script:State.PSObject.Properties[$Name]) {
        return [bool]$script:State.$Name
    }
    return $false
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
        PreAudioPassed=(Get-StateBool "PreAudioPassed")
        PreAudioStopProved=(Get-StateBool "PreAudioStopProved")
        SpeakerAttempted=(Get-StateBool "SpeakerAttempted")
        SpeakerPassed=(Get-StateBool "SpeakerPassed")
        SpeakerStopProved=(Get-StateBool "SpeakerStopProved")
        RestoreVerified=$script:State.RestoreVerified
        LastError=$(if ($script:State.PSObject.Properties["LastError"]) {[string]$script:State.LastError} else {""})
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

# The one-click Audio transaction first repairs any incomplete previous test.
$preTarget=Get-TargetDevice
$preTargetId=[string]$preTarget.PNPDeviceID
try {
    Recover-PreviousBaselineIfNeeded $preTargetId
} catch {
    Write-Host ("BASELINE_RECOVERY=FAIL {0}" -f $_.Exception.Message)
    if ($_.Exception.Message -match "(?i)restart is required|reboot") {
        Write-Host "MANUAL_WINDOWS_RESTART_REQUIRED=YES"
        Write-Host "The launcher has been scheduled to resume after the next normal Windows restart."
        exit 10
    }
    exit 2
}

New-RunSession "Audio" | Out-Null
Write-RunLog "PHASER360 AUDIO ONE-SHOT"
Write-RunLog "MODE=Audio"
Write-RunLog "DIRECT_FINAL_SPEAKER_TEST=YES"
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
    PreAudioPassed=$false
    PreAudioStopProved=$false
    SpeakerAttempted=$false
    SpeakerPassed=$false
    SpeakerStopProved=$false
    LastError=""
}
Save-State

Write-RunLog "TARGET=$targetId"
Write-RunLog ("TARGET_NAME={0} CODE={1} SERVICE={2}" -f
    [string]$target.Name,
    [int]$target.ConfigManagerErrorCode,
    [string]$target.Service)
Write-RunLog "BUS=$($bus.PNPDeviceID) SERVICE=$($bus.Service)"

Assert-TestSigning
Assert-SafeBaselineBeforeNewTest $targetId

$firmware=Resolve-Firmware $FirmwarePath
Write-RunLog "FIRMWARE=$firmware"
Write-RunLog "FIRMWARE_SHA256=$ExpectedFirmwareSha256"

$finalFolder=Assert-Package "FinalSpeaker" $info
Write-RunLog "PACKAGE_HEAD=$($info.HeadSha)"

$telemetry=$null
$success=$false

try {
    Backup-OriginalDriver $targetId
    Install-Firmware $firmware
    Import-TestCertificate $info | Out-Null

    # Final proof is Windows PCM, not a DSP-generated Tone path:
    # WinMM -> Windows Audio Engine -> WaveRT -> CoolStar HDA DMA ->
    # SOF HOST -> SSP1 -> MAX98357A.
    $amp=Get-AmpDevice
    Write-RunLog "AMP=$($amp.PNPDeviceID) SERVICE=$($amp.Service)"
    Write-RunLog "FINAL_SPEAKER_PHASE=BEGIN"
    $script:State.SpeakerAttempted=$true
    Save-State

    Install-TestPackage "FinalSpeaker" $info $targetId

    # Final HOST build flags:
    # runtime(1) + IPC(2) + HOST topology(4) + internal speaker(8) +
    # speaker endpoint(32) = 47. The driver must reach AUDIO_CORE before any
    # user-mode PCM is submitted.
    $telemetry=Wait-Telemetry -ExpectedFlags 47 -MinimumStage 70 -Seconds 25
    if ($telemetry.BootEpoch -lt 1 -or $telemetry.Stage -lt 70) {
        throw "Final HOST driver did not reach fresh AUDIO_CORE."
    }
    Write-RunLog "FINAL_HOST_AUDIO_CORE=PASS"

    $waveTest=Join-Path $PackageRoot "P360_WAVERT_TEST.exe"
    if (-not (Test-Path -LiteralPath $waveTest -PathType Leaf)) {
        throw "P360_WAVERT_TEST.exe is missing from the final package."
    }

    # Endpoint publication can lag the PnP start slightly. Retry only the
    # explicit 'no unique PHASER360 waveOut endpoint yet' condition (exit 20).
    # Any format/open/write failure is final and is not retried.
    $deadline=(Get-Date).AddSeconds(10)
    $waveResult=$null
    do {
        $waveResult=Invoke-Tool -Exe $waveTest -Arguments @() -AllowFailure
        if ($waveResult.ExitCode -eq 0) { break }
        if ($waveResult.ExitCode -ne 20) {
            throw "WaveRT physical playback test failed with exit code $($waveResult.ExitCode)."
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    if (-not $waveResult -or $waveResult.ExitCode -ne 0 -or
        $waveResult.Output -notmatch "(?im)^TEST=PASS\s*$") {
        throw "PHASER360 WaveRT endpoint did not complete the bounded Windows PCM test."
    }

    # Stream STOP is generated by waveOutClose/reset. Prove that the kernel
    # path reached MAX mute -> SOF STOP -> HDA STOP.
    $telemetry=Wait-Telemetry -ExpectedFlags 47 -MinimumStage 120 -Seconds 5
    if ($telemetry.Stage -ne 120) {
        throw "WaveRT playback completed but kernel STOP/mute was not proved."
    }

    $script:State.SpeakerPassed=$true
    Save-State
    Write-RunLog "FINAL_WAVERT_2000MS_MAX_0P5PCT=PASS"

    $null=Disable-TargetAndProveStop $targetId 47
    $script:State.SpeakerStopProved=$true
    Save-State
    Write-RunLog "FINAL_SPEAKER_STOP_MUTE=PASS"

    $success=$true
} catch {
    $script:State.LastError=[string]$_.Exception.Message
    Save-State
    $telemetry=Get-Telemetry
    Write-RunLog ("FAIL_DIAGNOSTIC={0}" -f
        (Format-TelemetryDiagnosis $telemetry $targetId))
    Write-RunLog "TEST=FAIL $($_.Exception.Message)"
} finally {
    try {
        Restore-OriginalDriver $targetId
        Write-RunLog "FINAL_DRIVER_RESTORE=PASS"
    } catch {
        Write-RunLog "FINAL_DRIVER_RESTORE=FAIL $($_.Exception.Message)"
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

    try {
        Assert-SafeBaselineBeforeNewTest $targetId
        Write-RunLog ("FINAL_BASELINE_DIAGNOSTIC={0}" -f (Get-TargetDiagnosticText $targetId))
        Write-RunLog "FINAL_RESIDUAL_STATE=PASS"
    } catch {
        Write-RunLog "FINAL_RESIDUAL_STATE=FAIL $($_.Exception.Message)"
        $success=$false
    }
}

if ($success) {
    if (-not $script:State.SpeakerAttempted -or
        -not $script:State.SpeakerPassed -or
        -not $script:State.SpeakerStopProved -or
        -not $script:State.RestoreVerified) {
        Write-RunLog "FINAL_GATE=FAIL incomplete proof vector"
        $success=$false
    }
}

if ($success) {
    Write-RunLog "AUDIO_GATE=PASS"
} else {
    Write-RunLog "AUDIO_GATE=FAIL"
}

Write-Report $(if ($success) {"PASS"} else {"FAIL"}) $telemetry
Write-RunLog "RESULT_DIR=$Session"

if ($success) { exit 0 }
exit 2
