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
$SafeAmpServiceName = "P360Max98357Safe"
$SafeAmpProviderName = "PHASER360 Project"
$SafeAmpDriverVersion = "2.0.0.0"
$ExpectedFirmwareBytes = 246528
$ExpectedFirmwareSha256 = "f68694b6197250016a9c5ffb46fa8adaa599a32db95aa19a0ecf5bd4ed1c62ab"
$TelemetryPath = "HKLM:\SYSTEM\CurrentControlSet\Services\P360SofAudio\Parameters"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageInfoPath = Join-Path $PackageRoot "PACKAGE_INFO.json"
$LogPath = $null
$Session = $null
$State = $null
$ResumeState = $null
$MaxCoreRepairRounds = 6
$MaxEndpointRepairRounds = 4
$MaxPhysicalRepairRounds = 3

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
    if ($targets.Count -ne 1) {
        throw "Expected exactly one MAX98357A ACPI device; found $($targets.Count)."
    }
    $amp = $targets[0]
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
    $result = Invoke-Tool -Exe "bcdedit.exe" -Arguments @("/enum","{current}") -AllowFailure
    if ($result.ExitCode -ne 0) {
        throw "Cannot read current BCD TestSigning state."
    }

    if ($result.Output -notmatch "(?im)^\s*testsigning\s+(Yes|On|Da|1)\s*$") {
        Write-RunLog "TESTSIGNING_REPAIR=BEGIN"
        $set = Invoke-Tool -Exe "bcdedit.exe" -Arguments @("/set","testsigning","on") -AllowFailure
        if ($set.ExitCode -ne 0) {
            throw "Windows TestSigning is OFF and automatic BCD repair failed."
        }
        if ($script:State) {
            $script:State.NeedsManualRestart=$true
            $script:State.LastRepairClass="TESTSIGNING"
            $script:State.LastRepairAction="BCD_TESTSIGNING_ON"
            Save-State
        }
        Schedule-AudioResumeAfterManualReboot
        Write-RunLog "TESTSIGNING_REPAIR=PASS RESTART_REQUIRED=YES"
        throw "TESTSIGNING_REPAIRED_RESTART_REQUIRED"
    }

    try {
        $secureBoot = Confirm-SecureBootUEFI
        if ($secureBoot -eq $true) {
            throw "SECURE_BOOT_BLOCKS_TEST_SIGNED_DRIVER"
        }
    } catch [System.PlatformNotSupportedException] {
    } catch {
        if ($_.Exception.Message -notmatch "not supported|Cmdlet not supported") {
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

    $bundledDir = Join-Path $PackageRoot "firmware"
    $bundledFirmware = Join-Path $bundledDir "p360-f686.ri"
    if (Test-Path -LiteralPath $bundledFirmware -PathType Leaf) {
        if (-not (Test-FirmwareFile $bundledFirmware)) {
            throw "Bundled firmware exists but does not match exact f686 size/hash."
        }
        Write-RunLog "FIRMWARE_BUNDLED=PASS PATH=$bundledFirmware"
        return $bundledFirmware
    }
    if (Test-Path -LiteralPath $bundledDir -PathType Container) {
        throw "Self-contained package firmware directory exists but p360-f686.ri is missing."
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

function Assert-SafeAmpPackage($Info) {
    $folder=Join-Path $PackageRoot "amp"
    foreach ($name in @("P360Max98357Safe.inf","P360Max98357Safe.cat","P360Max98357Safe.sys")) {
        if (-not (Test-Path -LiteralPath (Join-Path $folder $name) -PathType Leaf)) {
            throw "Signed safe-amp package file missing: $folder\$name"
        }
    }

    if (-not $Info.SafeAmpSysSha256 -or
        -not $Info.SafeAmpDriverVersion -or
        -not $Info.SafeAmpProvider -or
        -not $Info.SafeAmpService) {
        throw "PACKAGE_INFO.json is missing safe MAX98357A identity."
    }

    $sysHash=(Get-FileHash -LiteralPath (Join-Path $folder "P360Max98357Safe.sys") -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sysHash -ne ([string]$Info.SafeAmpSysSha256).ToLowerInvariant()) {
        throw "Safe MAX98357A SYS hash mismatch."
    }

    $infVersion=Get-InfVersion (Join-Path $folder "P360Max98357Safe.inf")
    if ($infVersion -ne [string]$Info.SafeAmpDriverVersion) {
        throw "Safe MAX98357A INF version mismatch: $infVersion != $($Info.SafeAmpDriverVersion)"
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

    # Persist the identity before the first mutation so rollback can remove a
    # partially imported certificate if the second store operation fails.
    $script:State.CertificateThumbprint = $thumb
    Save-State
    Invoke-Tool -Exe "certutil.exe" -Arguments @("-addstore","-f","Root",$cer) | Out-Null
    Invoke-Tool -Exe "certutil.exe" -Arguments @("-addstore","-f","TrustedPublisher",$cer) | Out-Null
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

function Assert-CatalogSignatureFile([string]$CatalogPath) {
    $sig = Get-AuthenticodeSignature -LiteralPath $CatalogPath
    if ($sig.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
        throw "Catalog signature is not valid after certificate import: $CatalogPath status=$($sig.Status)"
    }
}

function Assert-CatalogSignature([string]$Folder) {
    Assert-CatalogSignatureFile (Join-Path $Folder "P360SofAudio.cat")
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
        $script:State.AdspBackupComplete = $true
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
    $script:State.AdspBackupComplete = $true
    Save-State
    Write-RunLog ("ORIGINAL_DRIVER=BOUND INF={0} VERSION={1} PROVIDER={2}" -f
        $script:State.OriginalInfName,
        $script:State.OriginalDriverVersion,
        $script:State.OriginalProvider)
}

function Backup-OriginalAmpDriver([string]$InstanceId) {
    $amp=Get-AmpDevice
    if ([string]$amp.PNPDeviceID -ne $InstanceId) {
        throw "MAX98357A instance changed before baseline capture."
    }

    $driver=Get-SignedDriverOrNull $InstanceId
    if (-not $driver) {
        throw "MAX98357A baseline has no signed-driver record."
    }

    $inf=[string]$driver.InfName
    if ($inf -notmatch "(?i)^oem\d+\.inf$") {
        throw "Current MAX98357A driver '$inf' is not exportable; refusing replacement."
    }

    $backup=Join-Path $script:Session "original-amp-driver"
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    Invoke-Tool -Exe "pnputil.exe" -Arguments @("/export-driver",$inf,$backup) | Out-Null
    $exportedInf=Get-ChildItem -LiteralPath $backup -Filter "*.inf" -File -Recurse | Select-Object -First 1
    if (-not $exportedInf) {
        throw "Original MAX98357A driver export did not produce an INF."
    }

    $script:State.AmpInstanceId=$InstanceId
    $script:State.AmpOriginalService=[string]$amp.Service
    $script:State.AmpOriginalProblemCode=[int]$amp.ConfigManagerErrorCode
    $script:State.AmpOriginalInfName=$inf
    $script:State.AmpOriginalDriverVersion=[string]$driver.DriverVersion
    $script:State.AmpOriginalProvider=[string]$driver.DriverProviderName
    $script:State.AmpOriginalExportedInf=$exportedInf.FullName
    $script:State.AmpBackupComplete=$true
    $script:State.AmpRestoreVerified=$false
    Save-State

    Write-RunLog ("AMP_ORIGINAL=BOUND INF={0} SERVICE={1} VERSION={2} PROVIDER={3}" -f
        $script:State.AmpOriginalInfName,
        $script:State.AmpOriginalService,
        $script:State.AmpOriginalDriverVersion,
        $script:State.AmpOriginalProvider)
}

function Wait-AmpBinding(
    [string]$InstanceId,
    [string]$Version,
    [string]$Provider,
    [string]$Service,
    [int]$Seconds=15
) {
    $deadline=(Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Milliseconds 500
        $dev=Get-TargetByIdOrNull $InstanceId
        $drv=Get-BoundDriverOrNull $InstanceId
        if ($dev -and $drv -and
            [int]$dev.ConfigManagerErrorCode -eq 0 -and
            [string]$dev.Service -eq $Service -and
            [string]$drv.DriverVersion -eq $Version -and
            [string]$drv.DriverProviderName -eq $Provider) {
            return [pscustomobject]@{ Device=$dev; Driver=$drv }
        }
    } while ((Get-Date) -lt $deadline)
    return $null
}

function Get-SafeAmpStoreEntries($Info) {
    return @(Get-WindowsDriver -Online -All | Where-Object {
        [string]$_.ProviderName -eq [string]$Info.SafeAmpProvider -and
        [string]$_.Version -eq [string]$Info.SafeAmpDriverVersion
    })
}

function Install-SafeAmpPackage($Info,[string]$InstanceId) {
    $folder=Assert-SafeAmpPackage $Info
    Assert-CatalogSignatureFile (Join-Path $folder "P360Max98357Safe.cat")

    $inf=Join-Path $folder "P360Max98357Safe.inf"
    $version=[string]$Info.SafeAmpDriverVersion
    $provider=[string]$Info.SafeAmpProvider
    $service=[string]$Info.SafeAmpService

    $existing=Get-TargetByIdOrNull $InstanceId
    $existingDriver=Get-BoundDriverOrNull $InstanceId
    if ($existing -and $existingDriver -and
        [int]$existing.ConfigManagerErrorCode -eq 0 -and
        [string]$existing.Service -eq $service -and
        [string]$existingDriver.DriverVersion -eq $version -and
        [string]$existingDriver.DriverProviderName -eq $provider) {
        $script:State.SafeAmpInfName=[string]$existingDriver.InfName
        $script:State.SafeAmpInstalled=$true
        $script:State.AmpDisabledByRunner=$false
        Save-State
        Write-RunLog ("AMP_SAFE_REUSE=PASS SERVICE={0} VERSION={1} PROVIDER={2} INF={3}" -f
            [string]$existing.Service,
            [string]$existingDriver.DriverVersion,
            [string]$existingDriver.DriverProviderName,
            [string]$existingDriver.InfName)
        return
    }

    $disable=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/disable-device",$InstanceId) -AllowFailure
    if ($disable.ExitCode -ne 0) {
        throw "Could not disable MAX98357A before safe-driver transition."
    }
    $script:State.AmpDisabledByRunner=$true
    Save-State

    $add=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/add-driver",$inf) -AllowFailure
    if ($add.ExitCode -ne 0) {
        throw "Safe MAX98357A staging failed with exit code $($add.ExitCode)."
    }
    if ($add.Output -match "(?i)reboot is needed|restart is needed") {
        throw "Safe MAX98357A staging requested reboot; refusing audio execution."
    }

    # PowerShell functions enumerate array output. Force an array at the
    # call site so a single DISM driver record still has a Count property.
    $store=@(Get-SafeAmpStoreEntries $Info)
    if ($store.Count -ne 1 -or -not $store[0].Driver) {
        throw "Could not identify exactly one staged safe MAX98357A package."
    }
    $script:State.SafeAmpInfName=[string]$store[0].Driver
    Save-State

    # Old CoolStar is already in D0Exit (SDMODE low). Remove only the exact
    # amplifier devnode, then let a clean scan select the pinned newer package.
    $remove=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/remove-device",$InstanceId) -AllowFailure
    if ($remove.ExitCode -ne 0) {
        throw "Exact MAX98357A devnode removal failed."
    }

    $deadline=(Get-Date).AddSeconds(8)
    do {
        Start-Sleep -Milliseconds 250
        if (-not (Get-TargetByIdOrNull $InstanceId)) { break }
    } while ((Get-Date) -lt $deadline)
    if (Get-TargetByIdOrNull $InstanceId) {
        throw "MAX98357A devnode did not disappear after exact removal."
    }

    $scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure
    if ($scan.ExitCode -ne 0) {
        throw "PnP rescan failed while selecting safe MAX98357A."
    }

    $bound=Wait-AmpBinding $InstanceId $version $provider $service 15
    if (-not $bound) {
        throw "MAX98357A did not bind to the pinned fail-closed driver."
    }

    $script:State.SafeAmpInstalled=$true
    $script:State.AmpDisabledByRunner=$false
    Save-State

    Write-RunLog ("AMP_SAFE_BIND=PASS SERVICE={0} VERSION={1} PROVIDER={2} INF={3}" -f
        [string]$bound.Device.Service,
        [string]$bound.Driver.DriverVersion,
        [string]$bound.Driver.DriverProviderName,
        [string]$bound.Driver.InfName)
}

function Restore-OriginalAmpDriver {
    if (-not $script:State) { return }
    if ($script:State.PSObject.Properties["AmpBackupComplete"] -and
        -not [bool]$script:State.AmpBackupComplete) {
        Write-RunLog "RESTORE_AMP_SKIPPED=backup_not_complete"
        return
    }
    if (-not $script:State.PSObject.Properties["AmpInstanceId"] -or
        -not [string]$script:State.AmpInstanceId) {
        return
    }

    $instance=[string]$script:State.AmpInstanceId

    # D0Exit of either safe MAX or upstream CoolStar drives SDMODE low.
    $null=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/disable-device",$instance) -AllowFailure

    $dev=Get-TargetByIdOrNull $instance
    if ($dev) {
        $remove=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/remove-device",$instance) -AllowFailure
        if ($remove.ExitCode -ne 0) {
            throw "Could not remove exact MAX98357A devnode during restore."
        }
        $deadline=(Get-Date).AddSeconds(8)
        do {
            Start-Sleep -Milliseconds 250
            if (-not (Get-TargetByIdOrNull $instance)) { break }
        } while ((Get-Date) -lt $deadline)
        if (Get-TargetByIdOrNull $instance) {
            throw "MAX98357A devnode did not disappear during restore."
        }
    }

    # Normally SafeAmpInfName is persisted immediately after staging. If a
    # previous runner failed between pnputil /add-driver and Save-State, recover
    # the staged PHASER360 amp INF from Driver Store instead of leaving it able
    # to win the next PnP rank selection.
    $safeInfNames=@()
    if ($script:State.PSObject.Properties["SafeAmpInfName"] -and
        [string]$script:State.SafeAmpInfName) {
        $safeInfNames+=([string]$script:State.SafeAmpInfName)
    }
    $safeInfNames+=@(Get-WindowsDriver -Online -All | Where-Object {
        [string]$_.ProviderName -eq $SafeAmpProviderName -and
        [string]$_.Version -eq $SafeAmpDriverVersion
    } | ForEach-Object { [string]$_.Driver })
    $safeInfNames=@($safeInfNames | Where-Object {
        $_ -and $_ -match "(?i)^oem\d+\.inf$"
    } | Select-Object -Unique)

    foreach ($safeInf in $safeInfNames) {
        $delete=Invoke-Tool -Exe "pnputil.exe" -Arguments @(
            "/delete-driver",
            $safeInf,
            "/force") -AllowFailure
        Write-RunLog "AMP_SAFE_DELETE_INF=$safeInf EXIT=$($delete.ExitCode)"
    }

    if (-not $script:State.AmpOriginalExportedInf -or
        -not (Test-Path -LiteralPath ([string]$script:State.AmpOriginalExportedInf) -PathType Leaf)) {
        throw "Original MAX98357A driver backup is missing."
    }

    $restore=Invoke-Tool -Exe "pnputil.exe" -Arguments @(
        "/add-driver",
        [string]$script:State.AmpOriginalExportedInf) -AllowFailure
    if ($restore.ExitCode -ne 0) {
        throw "Original MAX98357A staging failed with exit code $($restore.ExitCode)."
    }
    Write-RunLog "AMP_RESTORE_STAGE_EXIT=$($restore.ExitCode)"

    $scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure
    if ($scan.ExitCode -ne 0) {
        throw "MAX98357A baseline rescan failed."
    }

    $bound=Wait-AmpBinding $instance ([string]$script:State.AmpOriginalDriverVersion) ([string]$script:State.AmpOriginalProvider) ([string]$script:State.AmpOriginalService) 15
    if (-not $bound) {
        throw "Original MAX98357A driver was not restored exactly."
    }

    $script:State.SafeAmpInstalled=$false
    $script:State.AmpDisabledByRunner=$false
    $script:State.AmpRestoreVerified=$true
    Save-State

    Write-RunLog ("AMP_RESTORE=PASS SERVICE={0} VERSION={1} PROVIDER={2}" -f
        [string]$bound.Device.Service,
        [string]$bound.Driver.DriverVersion,
        [string]$bound.Driver.DriverProviderName)
}

function Install-Firmware([string]$Firmware) {
    $dir = Join-Path $env:SystemRoot "System32\drivers\P360"
    $dest = Join-Path $dir "p360-f686.ri"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null

    if ($script:State.PSObject.Properties["ResumedRepairState"] -and
        [bool]$script:State.ResumedRepairState -and
        $script:State.PSObject.Properties["FirmwareDestination"] -and
        [string]$script:State.FirmwareDestination) {
        $dest=[string]$script:State.FirmwareDestination
        Copy-Item -LiteralPath $Firmware -Destination $dest -Force
        if (-not (Test-FirmwareFile $dest)) {
            throw "Firmware repair copy did not preserve exact f686 identity."
        }
        Write-RunLog "FIRMWARE_REPAIR_IN_PLACE=PASS"
        return
    }

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
    return $Version -in @(
        "2.0.100.1","2.0.101.1",
        "2.0.200.1","2.0.201.1",
        "2.0.301.1","2.0.302.1",
        "3.0.100.1"
    )
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
    $amp=Get-AmpDevice
    $ampDriver=Get-BoundDriverOrNull ([string]$amp.PNPDeviceID)

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

    if (-not $ampDriver) {
        throw "MAX98357A baseline has no signed-driver record."
    }
    if ([string]$amp.Service -eq $SafeAmpServiceName -or
        ([string]$ampDriver.DriverProviderName -eq $SafeAmpProviderName -and
         [string]$ampDriver.DriverVersion -eq $SafeAmpDriverVersion)) {
        throw "Fail-closed MAX98357A test driver is still active from a previous run."
    }

    $staleAmp=@(Get-WindowsDriver -Online -All | Where-Object {
        [string]$_.ProviderName -eq $SafeAmpProviderName -and
        [string]$_.Version -eq $SafeAmpDriverVersion
    })
    if ($staleAmp.Count -ne 0) {
        throw "Stale fail-closed MAX98357A package remains in Driver Store."
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

    $live=Get-TargetByIdOrNull $InstanceId
    $liveDriver=Get-BoundDriverOrNull $InstanceId
    if ($live -and $liveDriver -and
        [string]$live.Service -eq "P360SofAudio" -and
        [string]$liveDriver.DriverVersion -eq $wantVersion -and
        [string]$liveDriver.DriverProviderName -eq "PHASER360 Project") {
        $script:State.TestInfName=[string]$liveDriver.InfName
        $script:State.TestDriverVersion=$wantVersion
        Save-State
        Clear-TestTelemetry
        Write-RunLog ("FINAL_PACKAGE_REUSE=BEGIN VERSION={0} INF={1}" -f
            $wantVersion,[string]$liveDriver.InfName)
        Restart-Target $InstanceId | Out-Null
        Wait-TargetHealthy $InstanceId 15 | Out-Null
        if (-not (Test-BoundDriver $InstanceId $wantVersion "PHASER360 Project" "P360SofAudio")) {
            throw "Existing final package did not survive repair restart."
        }
        Write-RunLog "FINAL_PACKAGE_REUSE=PASS"
        return
    }

    $reserved=@(Get-P360StoreEntries | Where-Object {
        (Test-IsReservedGateVersion ([string]$_.Version))
    })
    $matching=@($reserved | Where-Object {
        [string]$_.Version -eq $wantVersion
    })
    $foreign=@($reserved | Where-Object {
        [string]$_.Version -ne $wantVersion
    })

    if ($foreign.Count -gt 0) {
        foreach ($entry in $foreign) {
            if ($entry.Driver) {
                $delete=Invoke-Tool -Exe "pnputil.exe" -Arguments @(
                    "/delete-driver",[string]$entry.Driver,"/force") -AllowFailure
                Write-RunLog ("AUTO_CLEAN_OLD_GATE_PACKAGE={0} VERSION={1} EXIT={2}" -f
                    [string]$entry.Driver,[string]$entry.Version,$delete.ExitCode)
            }
        }
    }

    Clear-TestTelemetry

    if ($matching.Count -eq 1 -and
        $script:State.PSObject.Properties["ResumedRepairState"] -and
        [bool]$script:State.ResumedRepairState) {
        $script:State.TestInfName=[string]$matching[0].Driver
        $script:State.TestDriverVersion=$wantVersion
        Save-State
        Write-RunLog ("FINAL_STAGED_PACKAGE_REUSE=YES VERSION={0} INF={1}" -f
            $wantVersion,[string]$matching[0].Driver)
        Remove-And-RescanTarget $InstanceId $wantVersion "PHASER360 Project" "P360SofAudio" | Out-Null
        return
    }

    if ($matching.Count -gt 1) {
        throw "More than one matching final P360 package exists in Driver Store."
    }

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
        $script:State.NeedsManualRestart=$true
        Save-State
        Schedule-AudioResumeAfterManualReboot
        throw "FINAL_DRIVER_STAGING_RESTART_REQUIRED"
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

function Get-FailureReasonName([uint32]$Reason) {
    switch ($Reason) {
        0  { return "NONE" }
        1  { return "IDENTITY" }
        2  { return "RESOURCES" }
        3  { return "NHLT" }
        4  { return "FIRMWARE" }
        5  { return "FW_READY" }
        6  { return "IRQ" }
        7  { return "IPC" }
        8  { return "TOPOLOGY" }
        9  { return "STREAM" }
        10 { return "CODEC" }
        11 { return "SPEAKER_GUARD" }
        default { return "UNKNOWN_$Reason" }
    }
}

function Get-FailureFingerprint([object]$Telemetry,[string]$ErrorText) {
    if ($Telemetry) {
        return ("stage={0};reason={1};status={2};prep={3};prepstatus={4};fw={5}" -f
            [uint32]$Telemetry.Stage,
            [uint32]$Telemetry.FailureReason,
            [uint32]$Telemetry.LastNtStatus,
            [uint32]$Telemetry.PrepareStep,
            [uint32]$Telemetry.PrepareNtStatus,
            [int]$Telemetry.FirmwareError)
    }
    return "no-telemetry;" + $ErrorText
}

function Add-RepairHistory([string]$Class,[string]$Action,[string]$Result,[string]$Detail) {
    $entry=[ordered]@{
        Time=(Get-Date).ToString("o")
        Class=$Class
        Action=$Action
        Result=$Result
        Detail=$Detail
    }
    $history=@()
    if ($script:State.PSObject.Properties["RepairHistory"] -and $script:State.RepairHistory) {
        $history=@($script:State.RepairHistory)
    }
    $history += [pscustomobject]$entry
    $script:State.RepairHistory=$history
    $script:State.LastRepairClass=$Class
    $script:State.LastRepairAction=$Action
    Save-State
    Write-RunLog ("REPAIR class={0} action={1} result={2} detail={3}" -f
        $Class,$Action,$Result,$Detail)
}

function Classify-CoreFailure([object]$Telemetry,[string]$ErrorText) {
    if ($ErrorText -match "(?i)SECURE_BOOT") {
        return [pscustomobject]@{ Class="SECURE_BOOT"; Action="MANUAL_FIRMWARE_SETTING"; Auto=$false }
    }
    if ($ErrorText -match "(?i)RESTART_REQUIRED|reboot is needed|restart is needed") {
        return [pscustomobject]@{ Class="RESTART_REQUIRED"; Action="MANUAL_RESTART_RESUME"; Auto=$false }
    }
    if ($ErrorText -match "(?i)hash mismatch|identity changed|signature|catalog|package.*missing") {
        return [pscustomobject]@{ Class="PACKAGE_INTEGRITY"; Action="STOP_BAD_PACKAGE"; Auto=$false }
    }

    if ($Telemetry) {
        $reason=[uint32]$Telemetry.FailureReason
        $prepare=[uint32]$Telemetry.PrepareStep
        if ($prepare -ge 2 -and $prepare -le 7) {
            return [pscustomobject]@{ Class="BUS_RESOURCE_CONTRACT"; Action="RESTART_AUDIO_BUS_AND_ADSP"; Auto=$true }
        }
        if ($prepare -eq 11) {
            return [pscustomobject]@{ Class="CSAUDIO_LINK"; Action="RESTART_SAFE_AMP_AND_ADSP"; Auto=$true }
        }
        switch ($reason) {
            1 { return [pscustomobject]@{ Class="IDENTITY"; Action="RESTART_AUDIO_BUS_AND_ADSP"; Auto=$true } }
            2 { return [pscustomobject]@{ Class="RESOURCES"; Action="RESTART_AUDIO_BUS_AND_ADSP"; Auto=$true } }
            3 { return [pscustomobject]@{ Class="NHLT"; Action="RESTART_AUDIO_BUS_AND_ADSP"; Auto=$true } }
            4 { return [pscustomobject]@{ Class="FIRMWARE"; Action="RECOPY_FIRMWARE_AND_RESTART_ADSP"; Auto=$true } }
            5 { return [pscustomobject]@{ Class="FW_READY"; Action="RECOPY_FIRMWARE_AND_RESTART_ADSP"; Auto=$true } }
            6 { return [pscustomobject]@{ Class="IRQ"; Action="RESTART_ADSP"; Auto=$true } }
            7 { return [pscustomobject]@{ Class="IPC"; Action="RESTART_ADSP"; Auto=$true } }
            8 { return [pscustomobject]@{ Class="TOPOLOGY"; Action="RESTART_ADSP"; Auto=$true } }
            9 { return [pscustomobject]@{ Class="STREAM"; Action="QUIESCE_AND_RESTART_ADSP"; Auto=$true } }
            10 { return [pscustomobject]@{ Class="CODEC"; Action="RESTART_SAFE_AMP_AND_ADSP"; Auto=$true } }
            11 { return [pscustomobject]@{ Class="SPEAKER_GUARD"; Action="FORCE_QUIESCE"; Auto=$true } }
        }
    }

    if ($ErrorText -match "(?i)binding|re-enumerat|device start|Target did not|PnP|telemetry key was never") {
        return [pscustomobject]@{ Class="PNP_BINDING"; Action="REBIND_FINAL_ADSP"; Auto=$true }
    }

    return [pscustomobject]@{ Class="UNKNOWN"; Action="RESTART_ADSP"; Auto=$true }
}

function Repair-PinnedFirmware([string]$Firmware) {
    if (-not (Test-FirmwareFile $Firmware)) {
        throw "Pinned repair firmware failed exact f686 validation."
    }
    $dest=[string]$script:State.FirmwareDestination
    if (-not $dest) {
        $dest=Join-Path $env:SystemRoot "System32\drivers\P360\p360-f686.ri"
        $script:State.FirmwareDestination=$dest
        Save-State
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
    Copy-Item -LiteralPath $Firmware -Destination $dest -Force
    if (-not (Test-FirmwareFile $dest)) {
        throw "Pinned firmware repair copy could not be verified."
    }
    Write-RunLog "AUTO_REPAIR_FIRMWARE=PASS"
}

function Restart-AudioBusSafely([string]$BusInstanceId) {
    if ($script:State.PhysicalCommitted) {
        throw "Parent audio bus restart is forbidden until physical stream ownership is quiesced."
    }
    $r=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/restart-device",$BusInstanceId) -AllowFailure
    if ($r.ExitCode -ne 0) {
        throw "Intel audio bus restart failed with exit code $($r.ExitCode)."
    }
    $scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure
    if ($scan.ExitCode -ne 0) {
        throw "PnP rescan failed after audio bus restart."
    }
    Start-Sleep -Milliseconds 700
    Get-BusDevice | Out-Null
    Write-RunLog "AUTO_REPAIR_AUDIO_BUS=PASS"
}

function Restart-SafeAmpForRepair([string]$AmpInstanceId,$Info) {
    if ($script:State.PhysicalCommitted) {
        throw "MAX restart requires quiesced physical ownership first."
    }
    $r=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/restart-device",$AmpInstanceId) -AllowFailure
    if ($r.ExitCode -ne 0) {
        throw "Safe MAX98357A restart failed with exit code $($r.ExitCode)."
    }
    $bound=Wait-AmpBinding $AmpInstanceId ([string]$Info.SafeAmpDriverVersion) ([string]$Info.SafeAmpProvider) ([string]$Info.SafeAmpService) 12
    if (-not $bound) {
        throw "Safe MAX98357A did not return healthy after restart."
    }
    Write-RunLog "AUTO_REPAIR_SAFE_AMP=PASS"
}

function Rebind-FinalAdsp([string]$InstanceId,$Info) {
    $folder=Assert-Package "FinalSpeaker" $Info
    $version=Get-InfVersion (Join-Path $folder "P360SofAudio.inf")
    Clear-TestTelemetry
    Remove-And-RescanTarget $InstanceId $version "PHASER360 Project" "P360SofAudio" | Out-Null
    Write-RunLog "AUTO_REPAIR_FINAL_ADSP_REBIND=PASS"
}

function Ensure-PhysicalQuiesced([string]$InstanceId,[string]$AmpInstanceId,$Info) {
    try {
        $t=Wait-Telemetry -ExpectedFlags 47 -MinimumStage 120 -Seconds 4
        if ($t.Stage -eq 120) {
            Write-RunLog "QUIESCE=PASS SOURCE=KERNEL_STOP_TELEMETRY"
            $script:State.PhysicalCommitted=$false
            Save-State
            return $true
        }
    } catch {
        Write-RunLog "QUIESCE_TELEMETRY_NOT_PROVED=$($_.Exception.Message)"
    }

    $ampDisable=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/disable-device",$AmpInstanceId) -AllowFailure
    if ($ampDisable.ExitCode -ne 0) {
        $script:State.HardStop=$true
        Save-State
        Add-RepairHistory "PHYSICAL_SAFETY" "FORCE_MAX_MUTE" "HARD_STOP" "MAX98357A D0Exit/mute could not be proved."
        return $false
    }
    $script:State.AmpDisabledByRunner=$true
    Save-State
    Write-RunLog "FORCED_MAX_MUTE=PASS"

    $adspDisable=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/disable-device",$InstanceId) -AllowFailure
    if ($adspDisable.ExitCode -ne 0) {
        $script:State.HardStop=$true
        Save-State
        Add-RepairHistory "PHYSICAL_SAFETY" "QUIESCE_ADSP" "HARD_STOP" "ADSP D0Exit could not be proved after MAX mute."
        return $false
    }
    Write-RunLog "FORCED_ADSP_QUIESCE=PASS"

    $ampEnable=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/enable-device",$AmpInstanceId) -AllowFailure
    if ($ampEnable.ExitCode -ne 0) {
        throw "Safe MAX98357A could not be re-enabled after proved mute."
    }
    $bound=Wait-AmpBinding $AmpInstanceId ([string]$Info.SafeAmpDriverVersion) ([string]$Info.SafeAmpProvider) ([string]$Info.SafeAmpService) 12
    if (-not $bound) {
        throw "Safe MAX98357A did not return after quiesce."
    }
    $script:State.AmpDisabledByRunner=$false

    $adspEnable=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/enable-device",$InstanceId) -AllowFailure
    if ($adspEnable.ExitCode -ne 0) {
        throw "ADSP could not be re-enabled after quiesce."
    }
    $scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure
    if ($scan.ExitCode -ne 0) {
        throw "PnP rescan failed after forced quiesce."
    }
    $script:State.PhysicalCommitted=$false
    Save-State
    Write-RunLog "QUIESCE=PASS SOURCE=FORCED_D0_EXIT"
    return $true
}

function Invoke-CoreRepair([object]$Decision,[string]$InstanceId,[string]$BusInstanceId,[string]$AmpInstanceId,$Info,[string]$Firmware) {
    if (-not [bool]$Decision.Auto) {
        throw "Failure class $($Decision.Class) is not automatically repairable."
    }

    switch ([string]$Decision.Action) {
        "RECOPY_FIRMWARE_AND_RESTART_ADSP" {
            Repair-PinnedFirmware $Firmware
            Clear-TestTelemetry
            Restart-Target $InstanceId | Out-Null
            Start-Sleep -Milliseconds 700
        }
        "RESTART_ADSP" {
            Clear-TestTelemetry
            Restart-Target $InstanceId | Out-Null
            Start-Sleep -Milliseconds 700
        }
        "REBIND_FINAL_ADSP" {
            Rebind-FinalAdsp $InstanceId $Info
        }
        "RESTART_SAFE_AMP_AND_ADSP" {
            Restart-SafeAmpForRepair $AmpInstanceId $Info
            Clear-TestTelemetry
            Restart-Target $InstanceId | Out-Null
            Start-Sleep -Milliseconds 700
        }
        "RESTART_AUDIO_BUS_AND_ADSP" {
            Restart-AudioBusSafely $BusInstanceId
            Rebind-FinalAdsp $InstanceId $Info
        }
        "QUIESCE_AND_RESTART_ADSP" {
            if (-not (Ensure-PhysicalQuiesced $InstanceId $AmpInstanceId $Info)) {
                throw "HARD_STOP_STREAM_NOT_QUIESCED"
            }
            Rebind-FinalAdsp $InstanceId $Info
        }
        "FORCE_QUIESCE" {
            if (-not (Ensure-PhysicalQuiesced $InstanceId $AmpInstanceId $Info)) {
                throw "HARD_STOP_MAX_MUTE_OR_STREAM_NOT_PROVED"
            }
            Rebind-FinalAdsp $InstanceId $Info
        }
        default {
            throw "No repair implementation for action $($Decision.Action)."
        }
    }
}

function Ensure-FinalCoreReady($Info,[string]$InstanceId,[string]$BusInstanceId,[string]$AmpInstanceId,[string]$Firmware) {
    $lastFingerprint=""
    $repeatCount=0

    for ($round=1; $round -le $MaxCoreRepairRounds; $round++) {
        $script:State.RepairRound=$round
        Save-State
        try {
            Write-RunLog "CORE_REPAIR_ROUND=$round"
            if ($round -eq 1) {
                Install-TestPackage "FinalSpeaker" $Info $InstanceId
            }
            $t=Wait-Telemetry -ExpectedFlags 47 -MinimumStage 70 -Seconds 25
            if ($t.BootEpoch -lt 1 -or $t.Stage -lt 70) {
                throw "Final HOST driver did not reach fresh AUDIO_CORE."
            }
            Add-RepairHistory "CORE" "VERIFY_AUDIO_CORE" "PASS" ("stage={0};epoch={1}" -f $t.Stage,$t.BootEpoch)
            return $t
        } catch {
            $errorText=[string]$_.Exception.Message
            $t=Get-Telemetry
            $decision=Classify-CoreFailure $t $errorText
            $fingerprint=Get-FailureFingerprint $t $errorText

            if ($fingerprint -eq $lastFingerprint) {
                $repeatCount++
            } else {
                $repeatCount=0
                $lastFingerprint=$fingerprint
            }

            Add-RepairHistory ([string]$decision.Class) ([string]$decision.Action) "DETECTED" $fingerprint

            if (-not [bool]$decision.Auto) {
                throw
            }

            if ($repeatCount -ge 2) {
                $script:State.NeedsDriverPatch=$true
                Save-State
                Add-RepairHistory ([string]$decision.Class) "NEEDS_DRIVER_PATCH" "STOP" "Same failure persisted after two repairs; preserve installed stack and diagnostics."
                throw "NEEDS_DRIVER_PATCH:$fingerprint"
            }

            Invoke-CoreRepair $decision $InstanceId $BusInstanceId $AmpInstanceId $Info $Firmware
            Add-RepairHistory ([string]$decision.Class) ([string]$decision.Action) "APPLIED" $errorText
        }
    }

    $script:State.NeedsDriverPatch=$true
    Save-State
    throw "NEEDS_DRIVER_PATCH:core repair rounds exhausted"
}

function Ensure-WindowsAudioServices([int]$Round) {
    foreach ($name in @("AudioEndpointBuilder","Audiosrv")) {
        $svc=Get-Service -Name $name -ErrorAction SilentlyContinue
        if (-not $svc) {
            throw "Required Windows audio service is missing: $name"
        }
        if ($svc.StartType -eq "Disabled") {
            Set-Service -Name $name -StartupType Automatic -ErrorAction Stop
            Write-RunLog "AUDIO_SERVICE_ENABLE=$name"
        }
        $svc=Get-Service -Name $name -ErrorAction Stop
        if ($svc.Status -ne "Running") {
            Start-Service -Name $name -ErrorAction Stop
            Write-RunLog "AUDIO_SERVICE_START=$name"
        }
    }

    if ($Round -gt 1) {
        Restart-Service -Name "Audiosrv" -Force -ErrorAction Stop
        Write-RunLog "AUDIO_SERVICE_RESTART=Audiosrv"
    }

    $scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure
    if ($scan.ExitCode -ne 0) {
        throw "PnP rescan failed during endpoint publication repair."
    }
    Start-Sleep -Milliseconds 1200
}

function Ensure-WaveRtPreflight([string]$WaveTest) {
    for ($round=1; $round -le $MaxEndpointRepairRounds; $round++) {
        $script:State.EndpointRepairRound=$round
        Save-State
        Ensure-WindowsAudioServices $round
        $pre=Invoke-Tool -Exe $WaveTest -Arguments @("--preflight") -AllowFailure
        if ($pre.ExitCode -eq 0 -and $pre.Output -match "(?im)^PREFLIGHT=PASS\s*$") {
            $script:State.EndpointPreflightPassed=$true
            Save-State
            Add-RepairHistory "ENDPOINT" "WAVE_FORMAT_QUERY" "PASS" "No audio buffer submitted."
            return
        }

        Add-RepairHistory "ENDPOINT" "PUBLISH_AND_FORMAT_QUERY" "RETRY" ("exit={0}; {1}" -f $pre.ExitCode,$pre.Output.Trim())
        if ($pre.ExitCode -notin @(20,21)) {
            throw "WaveRT no-audio preflight failed with non-publication exit code $($pre.ExitCode)."
        }
    }
    throw "WaveRT endpoint/format did not become ready after automatic publication repairs."
}

function Invoke-PhysicalPlaybackRepairLoop([string]$WaveTest,$Info,[string]$InstanceId,[string]$BusInstanceId,[string]$AmpInstanceId,[string]$Firmware) {
    for ($round=1; $round -le $MaxPhysicalRepairRounds; $round++) {
        $script:State.PhysicalAttempts=$round
        $script:State.EndpointPreflightPassed=$false
        Save-State

        Ensure-WaveRtPreflight $WaveTest

        Write-RunLog "PHYSICAL_AUDIO_TEST=BEGIN ATTEMPT=$round"
        $wave=Invoke-Tool -Exe $WaveTest -Arguments @() -AllowFailure
        $committed=($wave.Output -match "(?im)^PHYSICAL_COMMIT=YES\s*$")
        if ($committed) {
            $script:State.SpeakerAttempted=$true
            $script:State.PhysicalCommitted=$true
            Save-State
            Write-RunLog "PHYSICAL_PLAYBACK_COMMITTED=YES"
        }

        if ($wave.ExitCode -eq 0 -and
            $wave.Output -match "(?im)^PHYSICAL_COMPLETE=YES\s*$" -and
            $wave.Output -match "(?im)^TEST=PASS\s*$") {
            try {
                $t=Wait-Telemetry -ExpectedFlags 47 -MinimumStage 120 -Seconds 6
                if ($t.Stage -eq 120) {
                    $script:State.PhysicalCommitted=$false
                    Save-State
                    return $t
                }
            } catch {
                Add-RepairHistory "POST_PLAYBACK_STOP" "QUIESCE_AND_REPAIR" "RETRY" ([string]$_.Exception.Message)
            }
        }

        if (-not $committed) {
            Add-RepairHistory "WAVERT_PRE_COMMIT" "REPAIR_ENDPOINT_AND_CORE" "RETRY" ("exit={0}" -f $wave.ExitCode)
            Ensure-WindowsAudioServices ($round+1)
            Ensure-FinalCoreReady $Info $InstanceId $BusInstanceId $AmpInstanceId $Firmware | Out-Null
            continue
        }

        Add-RepairHistory "WAVERT_POST_COMMIT" "QUIESCE_AND_REPAIR" "BEGIN" ("exit={0}" -f $wave.ExitCode)
        if (-not (Ensure-PhysicalQuiesced $InstanceId $AmpInstanceId $Info)) {
            throw "HARD_STOP_MAX_MUTE_OR_STREAM_NOT_PROVED"
        }

        Rebind-FinalAdsp $InstanceId $Info
        Ensure-FinalCoreReady $Info $InstanceId $BusInstanceId $AmpInstanceId $Firmware | Out-Null
        Add-RepairHistory "WAVERT_POST_COMMIT" "QUIESCE_AND_REPAIR" "PASS" "Safe MAX mute and ADSP quiesce proved; retry allowed."
    }

    $script:State.NeedsDriverPatch=$true
    Save-State
    throw "NEEDS_DRIVER_PATCH:physical playback repair rounds exhausted"
}

function Copy-ResumeBaselineState {
    if (-not $script:ResumeState) { return }

    foreach ($name in @(
        "OriginalHadDriver","OriginalProblemCode","OriginalService","OriginalName",
        "OriginalInfName","OriginalDriverVersion","OriginalProvider","OriginalExportedInf",
        "AdspBackupComplete","AmpInstanceId","AmpOriginalService","AmpOriginalProblemCode",
        "AmpOriginalInfName","AmpOriginalDriverVersion","AmpOriginalProvider",
        "AmpOriginalExportedInf","AmpBackupComplete","FirmwareHadOriginal",
        "FirmwareBackup","FirmwareDestination","CertificateThumbprint",
        "PhysicalCommitted","HardStop","NeedsDriverPatch","NeedsManualRestart",
        "RepairHistory","LastRepairClass","LastRepairAction","PhysicalAttempts"
    )) {
        if ($script:ResumeState.PSObject.Properties[$name]) {
            $script:State.$name=$script:ResumeState.$name
        }
    }
    $script:State.ResumedRepairState=$true
    Save-State
    Write-RunLog "PERSISTENT_REPAIR_SESSION_RESUMED=YES"
}

function Assert-PersistentRepairState([string]$InstanceId) {
    $dev=Get-TargetByIdOrNull $InstanceId
    if (-not $dev) {
        throw "Persistent repair target is missing."
    }
    if ([string]$dev.Service -notin @("P360SofAudio","P360AdspProbe")) {
        throw "Persistent repair target has an unknown service: $($dev.Service)"
    }

    if ([int]$dev.ConfigManagerErrorCode -ne 0) {
        $enable=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/enable-device",$InstanceId) -AllowFailure
        if ($enable.ExitCode -ne 0) {
            throw "Persistent ADSP repair target could not be re-enabled."
        }
        $scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure
        if ($scan.ExitCode -ne 0) {
            throw "Persistent ADSP repair rescan failed."
        }
        Start-Sleep -Milliseconds 600
    }

    $amps=@(Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -and $_.PNPDeviceID.StartsWith($ExpectedAmpPrefix,[StringComparison]::OrdinalIgnoreCase)
    })
    if ($amps.Count -ne 1) {
        throw "Persistent repair requires exactly one MAX98357A device."
    }
    $amp=$amps[0]
    $ampDriver=Get-BoundDriverOrNull ([string]$amp.PNPDeviceID)
    if ($ampDriver -and
        [string]$amp.Service -eq $SafeAmpServiceName -and
        [string]$ampDriver.DriverProviderName -eq $SafeAmpProviderName -and
        [string]$ampDriver.DriverVersion -eq $SafeAmpDriverVersion -and
        [int]$amp.ConfigManagerErrorCode -ne 0) {
        $enableAmp=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/enable-device",[string]$amp.PNPDeviceID) -AllowFailure
        if ($enableAmp.ExitCode -ne 0) {
            throw "Persistent safe MAX98357A could not be re-enabled."
        }
        Start-Sleep -Milliseconds 500
    }

    Write-RunLog ("PERSISTENT_REPAIR_STATE=PASS SERVICE={0} CODE={1}" -f
        [string]$dev.Service,[int]$dev.ConfigManagerErrorCode)
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

function Assert-FinalAudioStack($Info,[string]$TargetInstanceId,[string]$AmpInstanceId) {
    $target=Wait-TargetHealthy $TargetInstanceId 12
    $targetDriver=Get-BoundDriverOrNull $TargetInstanceId
    if (-not $targetDriver -or
        [string]$target.Service -ne [string]$Info.FinalSpeakerService -or
        [string]$targetDriver.DriverVersion -ne [string]$Info.FinalSpeakerDriverVersion -or
        [string]$targetDriver.DriverProviderName -ne [string]$Info.FinalSpeakerProvider) {
        throw ("Final ADSP stack mismatch: service={0}, provider={1}, version={2}." -f
            [string]$target.Service,
            $(if ($targetDriver) {[string]$targetDriver.DriverProviderName} else {"<none>"}),
            $(if ($targetDriver) {[string]$targetDriver.DriverVersion} else {"<none>"}))
    }

    $amp=Get-AmpDevice
    if ([string]$amp.PNPDeviceID -ne $AmpInstanceId) {
        throw "MAX98357A instance changed after final audio test."
    }
    $ampDriver=Get-BoundDriverOrNull $AmpInstanceId
    if (-not $ampDriver -or
        [string]$amp.Service -ne [string]$Info.SafeAmpService -or
        [string]$ampDriver.DriverVersion -ne [string]$Info.SafeAmpDriverVersion -or
        [string]$ampDriver.DriverProviderName -ne [string]$Info.SafeAmpProvider) {
        throw "Fail-closed MAX98357A is no longer bound after final audio test."
    }

    if (-not $script:State.FirmwareDestination -or
        -not (Test-FirmwareFile ([string]$script:State.FirmwareDestination))) {
        throw "Pinned SOF firmware is not installed after final audio test."
    }

    $thumb=[string]$script:State.CertificateThumbprint
    if (-not $thumb) {
        throw "Final test certificate identity was lost."
    }
    foreach ($store in @("Root","TrustedPublisher")) {
        $certPath="Cert:\LocalMachine\$store\$thumb"
        if (-not (Test-Path -LiteralPath $certPath)) {
            throw "Final test certificate is missing from $store; driver would not survive a reboot."
        }
    }

    $t=Get-Telemetry
    if (-not $t -or
        $t.BuildFlags -ne 47 -or
        $t.FailureReason -ne 0 -or
        $t.LastNtStatus -ne 0 -or
        $t.Stage -ne 120) {
        throw "Final installed stack is not in proved idle/ready state after the 2-second test."
    }

    Write-RunLog ("FINAL_STACK=PASS ADSP_SERVICE={0} ADSP_VERSION={1} AMP_SERVICE={2} AMP_VERSION={3}" -f
        [string]$target.Service,
        [string]$targetDriver.DriverVersion,
        [string]$amp.Service,
        [string]$ampDriver.DriverVersion)
    return $t
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
    if ($script:State.PSObject.Properties["AdspBackupComplete"] -and
        -not [bool]$script:State.AdspBackupComplete) {
        Write-RunLog "RESTORE_ADSP_SKIPPED=backup_not_complete"
        return
    }

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

    $amp=$null
    try { $amp=Get-AmpDevice } catch { $amp=$null }
    if ($amp -and [string]$amp.Service -eq $SafeAmpServiceName) { return $true }

    $ampDriver=$null
    if ($amp) { $ampDriver=Get-BoundDriverOrNull ([string]$amp.PNPDeviceID) }
    if ($ampDriver -and
        [string]$ampDriver.DriverProviderName -eq $SafeAmpProviderName -and
        [string]$ampDriver.DriverVersion -eq $SafeAmpDriverVersion) {
        return $true
    }

    $staleAmp=@(Get-WindowsDriver -Online -All | Where-Object {
        [string]$_.ProviderName -eq $SafeAmpProviderName -and
        [string]$_.Version -eq $SafeAmpDriverVersion
    })
    if ($staleAmp.Count -gt 0) { return $true }

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

    Write-Host "PERSISTENT_REPAIR_STATE_DETECTED=YES"
    $candidate=Find-RecoverableSession $InstanceId
    if (-not $candidate) {
        throw "P360 repair state exists but its original baseline backup cannot be found. Refusing to overwrite recovery provenance."
    }

    $script:ResumeState=$candidate.State
    Write-Host ("PERSISTENT_REPAIR_RESUME_FROM={0}" -f [string]$candidate.Session)
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
        AdspBackupComplete=(Get-StateBool "AdspBackupComplete")
        AmpBackupComplete=(Get-StateBool "AmpBackupComplete")
        AmpInstanceId=$(if ($script:State.PSObject.Properties["AmpInstanceId"]) {[string]$script:State.AmpInstanceId} else {""})
        AmpOriginalService=$(if ($script:State.PSObject.Properties["AmpOriginalService"]) {[string]$script:State.AmpOriginalService} else {""})
        AmpOriginalDriverVersion=$(if ($script:State.PSObject.Properties["AmpOriginalDriverVersion"]) {[string]$script:State.AmpOriginalDriverVersion} else {""})
        SafeAmpInstalled=(Get-StateBool "SafeAmpInstalled")
        AmpRestoreVerified=(Get-StateBool "AmpRestoreVerified")
        InternalGatePassed=(Get-StateBool "InternalGatePassed")
        SpeakerAttempted=(Get-StateBool "SpeakerAttempted")
        SpeakerPassed=(Get-StateBool "SpeakerPassed")
        SpeakerStopProved=(Get-StateBool "SpeakerStopProved")
        FinalStackInstalled=(Get-StateBool "FinalStackInstalled")
        AudioReady=(Get-StateBool "AudioReady")
        RollbackPerformed=(Get-StateBool "RollbackPerformed")
        ResumedRepairState=(Get-StateBool "ResumedRepairState")
        RepairRound=$(if ($script:State.PSObject.Properties["RepairRound"]) {[int]$script:State.RepairRound} else {0})
        EndpointRepairRound=$(if ($script:State.PSObject.Properties["EndpointRepairRound"]) {[int]$script:State.EndpointRepairRound} else {0})
        EndpointPreflightPassed=(Get-StateBool "EndpointPreflightPassed")
        PhysicalAttempts=$(if ($script:State.PSObject.Properties["PhysicalAttempts"]) {[int]$script:State.PhysicalAttempts} else {0})
        PhysicalCommitted=(Get-StateBool "PhysicalCommitted")
        HardStop=(Get-StateBool "HardStop")
        NeedsDriverPatch=(Get-StateBool "NeedsDriverPatch")
        NeedsManualRestart=(Get-StateBool "NeedsManualRestart")
        LastRepairClass=$(if ($script:State.PSObject.Properties["LastRepairClass"]) {[string]$script:State.LastRepairClass} else {""})
        LastRepairAction=$(if ($script:State.PSObject.Properties["LastRepairAction"]) {[string]$script:State.LastRepairAction} else {""})
        RepairHistory=$(if ($script:State.PSObject.Properties["RepairHistory"]) {@($script:State.RepairHistory)} else {@()})
        RestoreVerified=$script:State.RestoreVerified
        LastError=$(if ($script:State.PSObject.Properties["LastError"]) {[string]$script:State.LastError} else {""})
        Telemetry=$Telemetry
    }
    $report | ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath (Join-Path $script:Session "RESULT.json") -Encoding UTF8
}

function Write-ResultZip([string]$Label="AUDIO") {
    if (-not $script:Session -or
        -not (Test-Path -LiteralPath $script:Session -PathType Container)) {
        Write-RunLog "RESULT_ZIP=FAIL session_missing"
        return ""
    }
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $desktop=[Environment]::GetFolderPath("Desktop")
        $leaf=Split-Path -Leaf $script:Session
        $suffix=$(if ($Label -eq "AUDIO") {""} else {"_" + $Label.ToUpperInvariant()})
        $zip=Join-Path $desktop ($leaf + $suffix + ".zip")
        if (Test-Path -LiteralPath $zip) {
            Remove-Item -LiteralPath $zip -Force
        }
        Write-RunLog "RESULT_ZIP_BEGIN=$zip"
        [IO.Compression.ZipFile]::CreateFromDirectory(
            $script:Session,
            $zip,
            [IO.Compression.CompressionLevel]::Optimal,
            $false)
        if (-not (Test-Path -LiteralPath $zip -PathType Leaf) -or
            (Get-Item -LiteralPath $zip).Length -le 0) {
            throw "Result ZIP was not created."
        }
        $sha=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
        Write-Host "RESULT_ZIP=$zip"
        Write-Host "RESULT_ZIP_SHA256=$sha"
        return $zip
    } catch {
        Write-RunLog "RESULT_ZIP=FAIL $($_.Exception.Message)"
        return ""
    }
}

Assert-Administrator

if ($Mode -eq "Restore") {
    Load-RestoreState $SessionPath
    $targetId=[string]$script:State.TargetInstanceId
    try {
        Restore-OriginalDriver $targetId
        Restore-OriginalAmpDriver
        Restore-Firmware
        Remove-TestCertificate ([string]$script:State.CertificateThumbprint)
        Write-RunLog "RESTORE=PASS"
        Write-ResultZip "RESTORE" | Out-Null
        exit 0
    } catch {
        Write-RunLog "RESTORE=FAIL $($_.Exception.Message)"
        Write-ResultZip "RESTORE" | Out-Null
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
Write-RunLog "SELF_AWARE_INSTALL_AND_AUDIO_TEST=YES"
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
    AdspBackupComplete=$false
    TestInfName=""
    TestDriverVersion=""
    AmpInstanceId=""
    AmpOriginalService=""
    AmpOriginalProblemCode=0
    AmpOriginalInfName=""
    AmpOriginalDriverVersion=""
    AmpOriginalProvider=""
    AmpOriginalExportedInf=""
    AmpBackupComplete=$false
    SafeAmpInfName=""
    SafeAmpInstalled=$false
    AmpDisabledByRunner=$false
    AmpRestoreVerified=$false
    CertificateThumbprint=""
    FirmwareHadOriginal=$false
    FirmwareBackup=""
    FirmwareDestination=""
    StopProved=$false
    RestoreVerified=$false
    InternalGatePassed=$false
    SpeakerAttempted=$false
    SpeakerPassed=$false
    SpeakerStopProved=$false
    FinalStackInstalled=$false
    AudioReady=$false
    RollbackPerformed=$false
    ResumedRepairState=$false
    RepairRound=0
    EndpointRepairRound=0
    EndpointPreflightPassed=$false
    PhysicalAttempts=0
    PhysicalCommitted=$false
    HardStop=$false
    NeedsDriverPatch=$false
    NeedsManualRestart=$false
    LastRepairClass=""
    LastRepairAction=""
    RepairHistory=@()
    LastError=""
}
Save-State
Copy-ResumeBaselineState

Write-RunLog "TARGET=$targetId"
Write-RunLog ("TARGET_NAME={0} CODE={1} SERVICE={2}" -f
    [string]$target.Name,
    [int]$target.ConfigManagerErrorCode,
    [string]$target.Service)
Write-RunLog "BUS=$($bus.PNPDeviceID) SERVICE=$($bus.Service)"

$telemetry=$null
$success=$false
$firmware=""
$ampId=""

try {
    Assert-TestSigning

    if ($script:State.ResumedRepairState -and
        ($script:State.PhysicalCommitted -or $script:State.HardStop)) {
        $ampId=[string]$script:State.AmpInstanceId
        if (-not $ampId) {
            throw "HARD_STOP_RESUME_MISSING_AMP_ID"
        }
        Write-RunLog "RESUME_SAFETY_RECOVERY=BEGIN"
        if (-not (Ensure-PhysicalQuiesced $targetId $ampId $info)) {
            throw "HARD_STOP_RESUME_QUIESCE_NOT_PROVED"
        }
        $script:State.HardStop=$false
        $script:State.PhysicalCommitted=$false
        Save-State
        Add-RepairHistory "RESUME_SAFETY" "PROVE_MUTE_AND_QUIESCE" "PASS" "Previous ambiguous physical ownership was cleared before repair continued."
        Write-RunLog "RESUME_SAFETY_RECOVERY=PASS"
    }

    if ($script:State.ResumedRepairState) {
        Assert-PersistentRepairState $targetId
    } else {
        Assert-SafeBaselineBeforeNewTest $targetId
    }

    $firmware=Resolve-Firmware $FirmwarePath
    Write-RunLog "FIRMWARE=$firmware"
    Write-RunLog "FIRMWARE_SHA256=$ExpectedFirmwareSha256"

    $finalFolder=Assert-Package "FinalSpeaker" $info
    $ampFolder=Assert-SafeAmpPackage $info
    Write-RunLog "PACKAGE_HEAD=$($info.HeadSha)"

    if (-not [bool]$script:State.AdspBackupComplete) {
        Backup-OriginalDriver $targetId
    } else {
        Write-RunLog "ORIGINAL_DRIVER_BACKUP=REUSED"
    }

    $amp=Get-AmpDevice
    $ampId=[string]$amp.PNPDeviceID
    if (-not [bool]$script:State.AmpBackupComplete) {
        Backup-OriginalAmpDriver $ampId
    } else {
        Write-RunLog "AMP_ORIGINAL_BACKUP=REUSED"
    }

    Install-Firmware $firmware
    Import-TestCertificate $info | Out-Null
    Install-SafeAmpPackage $info $ampId

    # Final proof is Windows PCM, not a DSP-generated Tone path:
    # WinMM -> Windows Audio Engine -> WaveRT -> CoolStar HDA DMA ->
    # SOF HOST -> SSP1 -> MAX98357A.
    $amp=Get-AmpDevice
    $ampDriver=Get-BoundDriverOrNull ([string]$amp.PNPDeviceID)
    if (-not $ampDriver -or
        [string]$amp.Service -ne [string]$info.SafeAmpService -or
        [string]$ampDriver.DriverVersion -ne [string]$info.SafeAmpDriverVersion -or
        [string]$ampDriver.DriverProviderName -ne [string]$info.SafeAmpProvider) {
        throw "Fail-closed MAX98357A identity changed before speaker phase."
    }
    Write-RunLog ("AMP_SAFE_READY=PASS ID={0} SERVICE={1} VERSION={2} PROVIDER={3}" -f
        [string]$amp.PNPDeviceID,
        [string]$amp.Service,
        [string]$ampDriver.DriverVersion,
        [string]$ampDriver.DriverProviderName)

    Write-RunLog "FINAL_STACK_INSTALL=BEGIN"

    $telemetry=Ensure-FinalCoreReady $info $targetId ([string]$bus.PNPDeviceID) $ampId $firmware

    $script:State.InternalGatePassed=$true
    Save-State
    Write-RunLog "INTERNAL_READY_GATE=PASS"
    Write-RunLog "FINAL_HOST_AUDIO_CORE=PASS"

    $waveTest=Join-Path $PackageRoot "P360_WAVERT_TEST.exe"
    if (-not (Test-Path -LiteralPath $waveTest -PathType Leaf)) {
        throw "P360_WAVERT_TEST.exe is missing from the final package."
    }

    $telemetry=Invoke-PhysicalPlaybackRepairLoop $waveTest $info $targetId ([string]$bus.PNPDeviceID) $ampId $firmware

    $script:State.SpeakerAttempted=$true
    $script:State.SpeakerPassed=$true
    $script:State.SpeakerStopProved=$true
    Save-State
    Write-RunLog "FINAL_WAVERT_2000MS_MAX_0P5PCT=PASS"
    Write-RunLog "STREAM_STOP_AND_AMP_MUTE=PASS"

    # Keep the final driver stack installed. Any physical retry is allowed
    # only after the previous attempt has been positively quiesced; after a
    # clean PASS the endpoint remains enabled for normal Windows audio.
    $telemetry=Assert-FinalAudioStack $info $targetId $ampId
    $script:State.FinalStackInstalled=$true
    $script:State.AudioReady=$true
    Save-State
    Write-RunLog "AUDIO_READY=PASS ENDPOINT_REMAINS_INSTALLED=YES"

    if (-not $script:State.InternalGatePassed -or
        -not $script:State.SpeakerAttempted -or
        -not $script:State.SpeakerPassed -or
        -not $script:State.SpeakerStopProved -or
        -not $script:State.FinalStackInstalled -or
        -not $script:State.AudioReady) {
        throw "Final audio proof vector is incomplete."
    }

    $success=$true
} catch {
    $script:State.LastError=[string]$_.Exception.Message
    Save-State
    $telemetry=Get-Telemetry
    Write-RunLog ("FAIL_DIAGNOSTIC={0}" -f
        (Format-TelemetryDiagnosis $telemetry $targetId))
    Write-RunLog "TEST=FAIL $($_.Exception.Message)"

    if ($script:State.PhysicalCommitted -and -not $script:State.HardStop) {
        try {
            if (-not (Ensure-PhysicalQuiesced $targetId $ampId $info)) {
                $script:State.HardStop=$true
            }
        } catch {
            $script:State.HardStop=$true
            Write-RunLog "FAILURE_QUIESCE=HARD_STOP $($_.Exception.Message)"
        }
        Save-State
    }

    $decision=Classify-CoreFailure $telemetry ([string]$script:State.LastError)
    Add-RepairHistory ([string]$decision.Class) ([string]$decision.Action) "PRESERVED" "Automatic rollback disabled; keep stack for repair/resume."
} finally {
    if ($success) {
        Write-RunLog "PERSISTENT_FINAL_STACK=YES"
        Write-RunLog "ROLLBACK_ON_SUCCESS=NO"
        Write-RunLog "MANUAL_ROLLBACK=RESTORE_LAST_SESSION.cmd"
    } else {
        Write-RunLog "PERSISTENT_REPAIR_STATE=YES"
        Write-RunLog "AUTOMATIC_ROLLBACK=NO"
        Write-RunLog "MANUAL_ROLLBACK=RESTORE_LAST_SESSION.cmd"
        if ($script:State.HardStop) {
            Write-RunLog "HARD_STOP=YES REASON=MAX_MUTE_OR_STREAM_QUIESCE_NOT_PROVED"
        }
        if ($script:State.NeedsDriverPatch) {
            Write-RunLog "NEEDS_DRIVER_PATCH=YES"
        }
    }
}

if ($success) {
    Write-RunLog "AUDIO_GATE=PASS AUDIO_READY=YES"
} else {
    Write-RunLog "AUDIO_GATE=FAIL"
}

Write-Report $(if ($success) {"PASS"} else {"FAIL"}) $telemetry
Write-RunLog "RESULT_DIR=$Session"
Write-ResultZip "AUDIO" | Out-Null

if ($success) { exit 0 }
if ($script:State.NeedsManualRestart) { exit 10 }
if ($script:State.HardStop) { exit 4 }
if ($script:State.NeedsDriverPatch) { exit 3 }
exit 2
