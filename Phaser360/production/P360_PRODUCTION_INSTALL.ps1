param(
    [ValidateSet("Install","Restore")]
    [string]$Mode="Install"
)

Set-StrictMode -Version 2.0
$ErrorActionPreference="Stop"

$Provider="PHASER360 Project"
$AdspPrefix="CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198"
$AmpPrefix="ACPI\MX98357A"
$AdspService="P360SofAudio"
$AmpService="P360Max98357Safe"
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$Inf=Join-Path $Root "P360AudioBundle.inf"
$Cat=Join-Path $Root "P360AudioBundle.cat"
$Cert=Join-Path $Root "P360_TEST.cer"
$InfoPath=Join-Path $Root "PACKAGE_INFO.json"
$Wasapi=Join-Path $Root "P360_WASAPI_TEST.exe"
$Legacy=Join-Path $Root "P360_WAVERT_TEST.exe"
$StateRoot=Join-Path $env:ProgramData "P360Audio"
$StatePath=Join-Path $StateRoot "ORIGINAL_STATE.json"
$RunStamp=Get-Date -Format "yyyyMMdd_HHmmss"
$Desktop=[Environment]::GetFolderPath("Desktop")
$RunDir=Join-Path $Desktop ("P360_PRODUCTION_RESULT_"+$RunStamp)
$LogPath=Join-Path $RunDir "RUN.log"
$FinalStatus="FAIL"

New-Item -ItemType Directory -Path $RunDir,$StateRoot -Force | Out-Null

function Log([string]$Text) {
    $line="[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"),$Text
    Write-Host $line
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Invoke-Tool([string]$Exe,[string[]]$Arguments,[switch]$AllowFailure) {
    Log ("EXEC={0} {1}" -f $Exe,($Arguments -join " "))
    $output=& $Exe @Arguments 2>&1 | Out-String
    $code=$LASTEXITCODE
    if ($output.Trim()) {
        Add-Content -LiteralPath $LogPath -Value $output.TrimEnd() -Encoding UTF8
    }
    if (-not $AllowFailure -and $code -ne 0) {
        throw "$Exe failed with exit code $code"
    }
    return [pscustomobject]@{ ExitCode=$code; Output=$output }
}

function Assert-Admin {
    $id=[Security.Principal.WindowsIdentity]::GetCurrent()
    $p=New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Administrator rights are required."
    }
}

function Get-OneDevice([string]$Prefix) {
    $all=@(Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -and $_.PNPDeviceID.StartsWith($Prefix,[StringComparison]::OrdinalIgnoreCase)
    })
    if ($all.Count -ne 1) {
        throw "Expected exactly one device for $Prefix; found $($all.Count)."
    }
    return $all[0]
}

function Get-Driver([string]$InstanceId) {
    return Get-CimInstance Win32_PnPSignedDriver | Where-Object {
        [string]$_.DeviceID -eq $InstanceId
    } | Select-Object -First 1
}

function Get-InfVersion([string]$Path) {
    $raw=Get-Content -LiteralPath $Path -Raw
    $m=[regex]::Match($raw,'(?im)^\s*DriverVer\s*=\s*[^,]+,\s*([0-9.]+)\s*$')
    if (-not $m.Success) { throw "DriverVer not found in $Path" }
    return $m.Groups[1].Value
}

function Assert-FileHash([string]$Name,[string]$Expected) {
    if (-not $Expected) { return }
    $path=Join-Path $Root $Name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file missing: $Name"
    }
    $actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Expected.ToLowerInvariant()) {
        throw "SHA256 mismatch for $Name"
    }
}

function Assert-Package {
    foreach($name in @(
        "P360AudioBundle.inf","P360AudioBundle.cat","P360SofAudio.sys",
        "P360Max98357Safe.sys","p360-f686.ri","P360_TEST.cer",
        "P360_WASAPI_TEST.exe","P360_WAVERT_TEST.exe","PACKAGE_INFO.json"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $name) -PathType Leaf)) {
            throw "Production package missing $name"
        }
    }

    $info=Get-Content -LiteralPath $InfoPath -Raw | ConvertFrom-Json
    $infVersion=Get-InfVersion $Inf
    if ([string]$info.DriverVersion -ne $infVersion) {
        throw "PACKAGE_INFO DriverVersion does not match INF."
    }
    if ([string]$info.Provider -ne $Provider) {
        throw "Unexpected provider in PACKAGE_INFO."
    }

    Assert-FileHash "P360SofAudio.sys" ([string]$info.P360SofAudioSha256)
    Assert-FileHash "P360Max98357Safe.sys" ([string]$info.P360Max98357SafeSha256)
    Assert-FileHash "p360-f686.ri" ([string]$info.FirmwareSha256)
    Assert-FileHash "P360_WASAPI_TEST.exe" ([string]$info.WasapiTestSha256)
    Assert-FileHash "P360_WAVERT_TEST.exe" ([string]$info.LegacyWaveOutTestSha256)

    $infText=Get-Content -LiteralPath $Inf -Raw
    if ($infText -notmatch 'PKEY_AudioEngine_OEMFormat') {
        throw "Production INF does not declare the explicit shared-mode OEM format."
    }
    if ($infText -match 'PKEY_AudioEndpoint_Supports_EventDriven_Mode') {
        throw "Production INF advertises event-driven mode without the ADSP notification contract."
    }

    Log ("PACKAGE=PASS VERSION={0} HEAD={1}" -f $infVersion,[string]$info.HeadSha)
    return $info
}

function Import-PackageCertificate {
    $certObj=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($Cert)
    $thumb=$certObj.Thumbprint.ToUpperInvariant()
    Log "CERT_THUMBPRINT=$thumb"
    Invoke-Tool "certutil.exe" @("-addstore","-f","Root",$Cert) | Out-Null
    Invoke-Tool "certutil.exe" @("-addstore","-f","TrustedPublisher",$Cert) | Out-Null
}

function Export-CurrentDriver([string]$Role,[object]$Device) {
    $drv=Get-Driver ([string]$Device.PNPDeviceID)
    if (-not $drv) {
        return [pscustomobject]@{
            Role=$Role; HadDriver=$false; InstanceId=[string]$Device.PNPDeviceID
            Service=[string]$Device.Service; ProblemCode=[int]$Device.ConfigManagerErrorCode
            InfName=""; Version=""; Provider=""; ExportedInf=""
        }
    }

    $inf=[string]$drv.InfName
    $outDir=Join-Path (Join-Path $StateRoot "original") $Role
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    $exported=""
    if ($inf -match '(?i)^oem\d+\.inf$') {
        Invoke-Tool "pnputil.exe" @("/export-driver",$inf,$outDir) | Out-Null
        $hit=Get-ChildItem -LiteralPath $outDir -Filter "*.inf" -File -Recurse | Select-Object -First 1
        if ($hit) { $exported=$hit.FullName }
    }

    return [pscustomobject]@{
        Role=$Role; HadDriver=$true; InstanceId=[string]$Device.PNPDeviceID
        Service=[string]$Device.Service; ProblemCode=[int]$Device.ConfigManagerErrorCode
        InfName=$inf; Version=[string]$drv.DriverVersion
        Provider=[string]$drv.DriverProviderName; ExportedInf=$exported
    }
}

function Ensure-OriginalBackup {
    if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
        Log "ORIGINAL_BACKUP=REUSED"
        return
    }

    $adsp=Get-OneDevice $AdspPrefix
    $amp=Get-OneDevice $AmpPrefix
    $adspDrv=Get-Driver ([string]$adsp.PNPDeviceID)
    if ($adspDrv -and [string]$adspDrv.DriverProviderName -eq $Provider -and
        [string]$adsp.Service -eq $AdspService) {
        Log "ORIGINAL_BACKUP=SKIPPED_ALREADY_PRODUCTION"
        return
    }

    $state=[ordered]@{
        CapturedAt=(Get-Date).ToString("o")
        Adsp=(Export-CurrentDriver "adsp" $adsp)
        Amp=(Export-CurrentDriver "amp" $amp)
    }
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatePath -Encoding UTF8
    Copy-Item -LiteralPath $StatePath -Destination (Join-Path $RunDir "ORIGINAL_STATE.json") -Force
    Log "ORIGINAL_BACKUP=PASS"
}

function Report-NonAudioBoot0000 {
    $items=@(Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -and $_.PNPDeviceID.StartsWith("ACPI\\BOOT0000",[StringComparison]::OrdinalIgnoreCase)
    })
    if ($items.Count -eq 0) {
        Log "BOOT0000=NOT_PRESENT NOT_AUDIO_BLOCKER=YES"
        return
    }
    foreach($item in $items) {
        Log ("BOOT0000=OBSERVED INSTANCE={0} CODE={1} STATUS={2} SERVICE={3} NOT_AUDIO_BLOCKER=YES" -f
            [string]$item.PNPDeviceID,[int]$item.ConfigManagerErrorCode,[string]$item.Status,[string]$item.Service)
    }
}

function Remove-StaleProjectPackages {
    $adsp=Get-OneDevice $AdspPrefix
    $amp=Get-OneDevice $AmpPrefix
    $keep=@()
    foreach($dev in @($adsp,$amp)) {
        $drv=Get-Driver ([string]$dev.PNPDeviceID)
        if ($drv -and [string]$drv.InfName -match '(?i)^oem\d+\.inf
    $r=Invoke-Tool "pnputil.exe" @("/add-driver",$Inf,"/install") -AllowFailure
    if ($r.ExitCode -ne 0) {
        throw "Production bundle staging/install failed."
    }
    if ($r.Output -match '(?i)reboot is needed|restart is needed') {
        Log "REBOOT_REQUIRED=YES"
    }
    Invoke-Tool "pnputil.exe" @("/scan-devices") | Out-Null
    Start-Sleep -Milliseconds 800
}

function Wait-ProductionBinding([string]$Prefix,[string]$Service,[string]$Version,[int]$Seconds=20) {
    $deadline=(Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Milliseconds 500
        try {
            $dev=Get-OneDevice $Prefix
            $drv=Get-Driver ([string]$dev.PNPDeviceID)
            if ($drv -and
                [int]$dev.ConfigManagerErrorCode -eq 0 -and
                [string]$dev.Service -eq $Service -and
                [string]$drv.DriverProviderName -eq $Provider -and
                [string]$drv.DriverVersion -eq $Version) {
                return [pscustomobject]@{ Device=$dev; Driver=$drv }
            }
        } catch {}
    } while((Get-Date) -lt $deadline)
    return $null
}

function Assert-ProductionBinding([object]$Info) {
    $version=[string]$Info.DriverVersion
    $a=Wait-ProductionBinding $AdspPrefix $AdspService $version 20
    $m=Wait-ProductionBinding $AmpPrefix $AmpService $version 20
    if (-not $a -or -not $m) {
        throw "Production driver binding is not healthy for both ADSP and MAX98357A."
    }
    Log ("ADSP_BIND=PASS INF={0} VERSION={1}" -f [string]$a.Driver.InfName,[string]$a.Driver.DriverVersion)
    Log ("AMP_BIND=PASS INF={0} VERSION={1}" -f [string]$m.Driver.InfName,[string]$m.Driver.DriverVersion)
}

function Restart-ExactProductionDevices {
    $amp=Get-OneDevice $AmpPrefix
    $adsp=Get-OneDevice $AdspPrefix
    $ra=Invoke-Tool "pnputil.exe" @("/restart-device",[string]$amp.PNPDeviceID) -AllowFailure
    $rd=Invoke-Tool "pnputil.exe" @("/restart-device",[string]$adsp.PNPDeviceID) -AllowFailure
    Invoke-Tool "pnputil.exe" @("/scan-devices") -AllowFailure | Out-Null
    Log ("DEVICE_RESTART amp={0} adsp={1}" -f $ra.ExitCode,$rd.ExitCode)
    Start-Sleep -Seconds 1
}

function Reenumerate-Adsp {
    $adsp=Get-OneDevice $AdspPrefix
    $id=[string]$adsp.PNPDeviceID
    $r=Invoke-Tool "pnputil.exe" @("/remove-device",$id) -AllowFailure
    if ($r.ExitCode -ne 0) { return $false }
    Invoke-Tool "pnputil.exe" @("/scan-devices") -AllowFailure | Out-Null
    Start-Sleep -Seconds 1
    return $true
}

function Restart-WindowsAudio {
    try {
        Stop-Service -Name Audiosrv -Force -ErrorAction SilentlyContinue
        Stop-Service -Name AudioEndpointBuilder -Force -ErrorAction SilentlyContinue
        Start-Service -Name AudioEndpointBuilder -ErrorAction Stop
        Start-Service -Name Audiosrv -ErrorAction Stop
        Log "WINDOWS_AUDIO_SERVICES_RESTART=PASS"
        Start-Sleep -Seconds 1
    } catch {
        Log ("WINDOWS_AUDIO_SERVICES_RESTART=FAIL "+$_.Exception.Message)
    }
}

function Run-Wasapi([switch]$Preflight) {
    $args=@()
    if ($Preflight) { $args+= "--preflight" }
    $r=Invoke-Tool $Wasapi $args -AllowFailure
    if ($r.ExitCode -eq 0) {
        if ($Preflight) { Log "WASAPI_SHARED_PREFLIGHT=PASS" }
        else { Log "WASAPI_SHARED_ENDPOINT=PASS" }
        return $true
    }
    Log ("WASAPI_SHARED_TEST=FAIL EXIT="+$r.ExitCode)
    return $false
}

function Reset-WasapiEndpointFormat {
    $r=Invoke-Tool $Wasapi @("--reset-default") -AllowFailure
    if ($r.ExitCode -eq 0) {
        Log "WASAPI_DEVICE_FORMAT_RESET=PASS"
        return $true
    }
    Log ("WASAPI_DEVICE_FORMAT_RESET=FAIL EXIT="+$r.ExitCode)
    return $false
}

function Write-ResultZip {
    try {
        if (Test-Path -LiteralPath $StatePath) {
            Copy-Item -LiteralPath $StatePath -Destination (Join-Path $RunDir "STATE_SNAPSHOT.json") -Force
        }
        $zip=Join-Path $Desktop ("P360_PRODUCTION_RESULT_"+$RunStamp+".zip")
        Compress-Archive -Path (Join-Path $RunDir "*") -DestinationPath $zip -Force
        Write-Host "RESULT_ZIP=$zip"
    } catch {
        Write-Host ("RESULT_ZIP_ERROR="+$_.Exception.Message)
    }
}

function Restore-Original {
    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        throw "No original-driver backup exists. Restore is manual and cannot guess a baseline."
    }
    $state=Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json

    $amp=Get-OneDevice $AmpPrefix
    $adsp=Get-OneDevice $AdspPrefix
    $productionInfNames=@()
    foreach($dev in @($adsp,$amp)) {
        $drv=Get-Driver ([string]$dev.PNPDeviceID)
        if ($drv -and [string]$drv.DriverProviderName -eq $Provider) {
            $productionInfNames += [string]$drv.InfName
        }
    }

    Invoke-Tool "pnputil.exe" @("/remove-device",[string]$amp.PNPDeviceID) -AllowFailure | Out-Null
    Invoke-Tool "pnputil.exe" @("/remove-device",[string]$adsp.PNPDeviceID) -AllowFailure | Out-Null

    foreach($name in @($productionInfNames | Select-Object -Unique)) {
        if ($name -match '(?i)^oem\d+\.inf$') {
            Invoke-Tool "pnputil.exe" @("/delete-driver",$name,"/force") -AllowFailure | Out-Null
        }
    }

    foreach($entry in @($state.Adsp,$state.Amp)) {
        if ([bool]$entry.HadDriver -and [string]$entry.ExportedInf -and
            (Test-Path -LiteralPath ([string]$entry.ExportedInf) -PathType Leaf)) {
            Invoke-Tool "pnputil.exe" @("/add-driver",[string]$entry.ExportedInf,"/install") | Out-Null
        }
    }
    Invoke-Tool "pnputil.exe" @("/scan-devices") | Out-Null
    Restart-WindowsAudio
    Log "MANUAL_RESTORE_REQUESTED=YES"
    Log "MANUAL_RESTORE_STAGE=COMPLETE"
}

Assert-Admin
Log "PHASER360 PRODUCTION AUDIO"
Log ("MODE="+$Mode)
Log "ARCHITECTURE=WindowsAudio/WASAPI_SHARED->PortCls/WaveRT->P360SofAudio->SklHDAudBus/HDA_DMA->SOF_HOST->SSP1->MAX98357A"
Log "AUTOMATIC_ROLLBACK=NO"
Log "ALTERNATE_DRIVER_SWAP=NO"

try {
    if ($Mode -eq "Restore") {
        Restore-Original
        $FinalStatus="RESTORE_COMPLETE"
    } else {
        $info=Assert-Package
        Ensure-OriginalBackup
        Import-PackageCertificate
        Install-Bundle $info
        Report-NonAudioBoot0000

        $preflightPassed=$false
        $staleCleaned=$false
        for($round=1;$round -le 3;$round++) {
            Log ("PREFLIGHT_REPAIR_ROUND="+$round)
            try {
                Assert-ProductionBinding $info

                if (-not $staleCleaned) {
                    Remove-StaleProjectPackages
                    Assert-ProductionBinding $info
                    $staleCleaned=$true
                }

                if (-not (Run-Wasapi -Preflight)) {
                    throw "WASAPI shared preflight failed."
                }

                $preflightPassed=$true
                break
            } catch {
                Log ("PREFLIGHT_ROUND_FAIL="+$_.Exception.Message)
                if ($round -eq 1) {
                    [void](Reset-WasapiEndpointFormat)
                    Restart-WindowsAudio
                    Restart-ExactProductionDevices
                    Install-Bundle $info
                } elseif ($round -eq 2) {
                    [void](Reenumerate-Adsp)
                    Install-Bundle $info
                    [void](Reset-WasapiEndpointFormat)
                    Restart-WindowsAudio
                }
            }
        }

        if (-not $preflightPassed) {
            throw "WASAPI shared preflight did not become functional after same-package repairs."
        }

        Assert-ProductionBinding $info
        Log "PHYSICAL_WASAPI_ATTEMPTS_MAX=1"
        Log "PHYSICAL_WASAPI_ATTEMPT=1"
        if (-not (Run-Wasapi)) {
            throw "One-shot WASAPI shared playback failed. No automatic physical replay is permitted."
        }

        Assert-ProductionBinding $info
        Log "FINAL_ACCEPTANCE=WASAPI_SHARED_ENDPOINT_FUNCTIONAL"
        Log "WAVEOUT_ROLE=LOWER_LEVEL_DIAGNOSTIC_ONLY"
        Log "ENDPOINT_REMAINS_INSTALLED=YES"
        Log "AUDIO_READY=PASS"
        $FinalStatus="PASS"
    }
} catch {
    Log ("ERROR="+$_.Exception.Message)
    Log "PRODUCTION_DRIVER_LEFT_INSTALLED_FOR_DIAGNOSIS=YES"
    Log "AUTOMATIC_ROLLBACK=NO"
    $FinalStatus="FAIL"
}

Log ("FINAL_STATUS="+$FinalStatus)
Write-ResultZip

if ($FinalStatus -eq "PASS" -or $FinalStatus -eq "RESTORE_COMPLETE") { exit 0 }
exit 3
) {
            $keep += ([string]$drv.InfName).ToLowerInvariant()
        }
    }
    $keep=@($keep | Select-Object -Unique)
    if ($keep.Count -lt 1) {
        throw "Cannot identify the currently bound production INF."
    }

    $stale=@(Get-WindowsDriver -Online -All -ErrorAction Stop | Where-Object {
        [string]$_.ProviderName -eq $Provider -and
        [string]$_.Driver -match '(?i)^oem\d+\.inf
    $r=Invoke-Tool "pnputil.exe" @("/add-driver",$Inf,"/install") -AllowFailure
    if ($r.ExitCode -ne 0) {
        throw "Production bundle staging/install failed."
    }
    if ($r.Output -match '(?i)reboot is needed|restart is needed') {
        Log "REBOOT_REQUIRED=YES"
    }
    Invoke-Tool "pnputil.exe" @("/scan-devices") | Out-Null
    Start-Sleep -Milliseconds 800
}

function Wait-ProductionBinding([string]$Prefix,[string]$Service,[string]$Version,[int]$Seconds=20) {
    $deadline=(Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Milliseconds 500
        try {
            $dev=Get-OneDevice $Prefix
            $drv=Get-Driver ([string]$dev.PNPDeviceID)
            if ($drv -and
                [int]$dev.ConfigManagerErrorCode -eq 0 -and
                [string]$dev.Service -eq $Service -and
                [string]$drv.DriverProviderName -eq $Provider -and
                [string]$drv.DriverVersion -eq $Version) {
                return [pscustomobject]@{ Device=$dev; Driver=$drv }
            }
        } catch {}
    } while((Get-Date) -lt $deadline)
    return $null
}

function Assert-ProductionBinding([object]$Info) {
    $version=[string]$Info.DriverVersion
    $a=Wait-ProductionBinding $AdspPrefix $AdspService $version 20
    $m=Wait-ProductionBinding $AmpPrefix $AmpService $version 20
    if (-not $a -or -not $m) {
        throw "Production driver binding is not healthy for both ADSP and MAX98357A."
    }
    Log ("ADSP_BIND=PASS INF={0} VERSION={1}" -f [string]$a.Driver.InfName,[string]$a.Driver.DriverVersion)
    Log ("AMP_BIND=PASS INF={0} VERSION={1}" -f [string]$m.Driver.InfName,[string]$m.Driver.DriverVersion)
}

function Restart-ExactProductionDevices {
    $amp=Get-OneDevice $AmpPrefix
    $adsp=Get-OneDevice $AdspPrefix
    $ra=Invoke-Tool "pnputil.exe" @("/restart-device",[string]$amp.PNPDeviceID) -AllowFailure
    $rd=Invoke-Tool "pnputil.exe" @("/restart-device",[string]$adsp.PNPDeviceID) -AllowFailure
    Invoke-Tool "pnputil.exe" @("/scan-devices") -AllowFailure | Out-Null
    Log ("DEVICE_RESTART amp={0} adsp={1}" -f $ra.ExitCode,$rd.ExitCode)
    Start-Sleep -Seconds 1
}

function Reenumerate-Adsp {
    $adsp=Get-OneDevice $AdspPrefix
    $id=[string]$adsp.PNPDeviceID
    $r=Invoke-Tool "pnputil.exe" @("/remove-device",$id) -AllowFailure
    if ($r.ExitCode -ne 0) { return $false }
    Invoke-Tool "pnputil.exe" @("/scan-devices") -AllowFailure | Out-Null
    Start-Sleep -Seconds 1
    return $true
}

function Restart-WindowsAudio {
    try {
        Stop-Service -Name Audiosrv -Force -ErrorAction SilentlyContinue
        Stop-Service -Name AudioEndpointBuilder -Force -ErrorAction SilentlyContinue
        Start-Service -Name AudioEndpointBuilder -ErrorAction Stop
        Start-Service -Name Audiosrv -ErrorAction Stop
        Log "WINDOWS_AUDIO_SERVICES_RESTART=PASS"
        Start-Sleep -Seconds 1
    } catch {
        Log ("WINDOWS_AUDIO_SERVICES_RESTART=FAIL "+$_.Exception.Message)
    }
}

function Run-Wasapi([switch]$Preflight) {
    $args=@()
    if ($Preflight) { $args+= "--preflight" }
    $r=Invoke-Tool $Wasapi $args -AllowFailure
    if ($r.ExitCode -eq 0) {
        if ($Preflight) { Log "WASAPI_SHARED_PREFLIGHT=PASS" }
        else { Log "WASAPI_SHARED_ENDPOINT=PASS" }
        return $true
    }
    Log ("WASAPI_SHARED_TEST=FAIL EXIT="+$r.ExitCode)
    return $false
}

function Write-ResultZip {
    try {
        if (Test-Path -LiteralPath $StatePath) {
            Copy-Item -LiteralPath $StatePath -Destination (Join-Path $RunDir "STATE_SNAPSHOT.json") -Force
        }
        $zip=Join-Path $Desktop ("P360_PRODUCTION_RESULT_"+$RunStamp+".zip")
        Compress-Archive -Path (Join-Path $RunDir "*") -DestinationPath $zip -Force
        Write-Host "RESULT_ZIP=$zip"
    } catch {
        Write-Host ("RESULT_ZIP_ERROR="+$_.Exception.Message)
    }
}

function Restore-Original {
    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        throw "No original-driver backup exists. Restore is manual and cannot guess a baseline."
    }
    $state=Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json

    $amp=Get-OneDevice $AmpPrefix
    $adsp=Get-OneDevice $AdspPrefix
    $productionInfNames=@()
    foreach($dev in @($adsp,$amp)) {
        $drv=Get-Driver ([string]$dev.PNPDeviceID)
        if ($drv -and [string]$drv.DriverProviderName -eq $Provider) {
            $productionInfNames += [string]$drv.InfName
        }
    }

    Invoke-Tool "pnputil.exe" @("/remove-device",[string]$amp.PNPDeviceID) -AllowFailure | Out-Null
    Invoke-Tool "pnputil.exe" @("/remove-device",[string]$adsp.PNPDeviceID) -AllowFailure | Out-Null

    foreach($name in @($productionInfNames | Select-Object -Unique)) {
        if ($name -match '(?i)^oem\d+\.inf$') {
            Invoke-Tool "pnputil.exe" @("/delete-driver",$name,"/force") -AllowFailure | Out-Null
        }
    }

    foreach($entry in @($state.Adsp,$state.Amp)) {
        if ([bool]$entry.HadDriver -and [string]$entry.ExportedInf -and
            (Test-Path -LiteralPath ([string]$entry.ExportedInf) -PathType Leaf)) {
            Invoke-Tool "pnputil.exe" @("/add-driver",[string]$entry.ExportedInf,"/install") | Out-Null
        }
    }
    Invoke-Tool "pnputil.exe" @("/scan-devices") | Out-Null
    Restart-WindowsAudio
    Log "MANUAL_RESTORE_REQUESTED=YES"
    Log "MANUAL_RESTORE_STAGE=COMPLETE"
}

Assert-Admin
Log "PHASER360 PRODUCTION AUDIO"
Log ("MODE="+$Mode)
Log "ARCHITECTURE=WindowsAudio/WASAPI_SHARED->PortCls/WaveRT->P360SofAudio->SklHDAudBus/HDA_DMA->SOF_HOST->SSP1->MAX98357A"
Log "AUTOMATIC_ROLLBACK=NO"
Log "ALTERNATE_DRIVER_SWAP=NO"

try {
    if ($Mode -eq "Restore") {
        Restore-Original
        $FinalStatus="RESTORE_COMPLETE"
    } else {
        $info=Assert-Package
        Ensure-OriginalBackup
        Import-PackageCertificate
        Install-Bundle $info

        $passed=$false
        for($round=1;$round -le 3;$round++) {
            Log ("REPAIR_ROUND="+$round)
            try {
                Assert-ProductionBinding $info
                if (-not (Run-Wasapi -Preflight)) {
                    throw "WASAPI shared preflight failed."
                }
                if (-not (Run-Wasapi)) {
                    throw "WASAPI shared playback failed."
                }
                $passed=$true
                break
            } catch {
                Log ("ROUND_FAIL="+$_.Exception.Message)
                if ($round -eq 1) {
                    Restart-ExactProductionDevices
                    Restart-WindowsAudio
                    Install-Bundle $info
                } elseif ($round -eq 2) {
                    [void](Reenumerate-Adsp)
                    Install-Bundle $info
                    Restart-WindowsAudio
                }
            }
        }

        if (-not $passed) {
            throw "WASAPI shared endpoint did not become functional after same-package repairs."
        }

        Assert-ProductionBinding $info
        Log "FINAL_ACCEPTANCE=WASAPI_SHARED_ENDPOINT_FUNCTIONAL"
        Log "WAVEOUT_ROLE=LOWER_LEVEL_DIAGNOSTIC_ONLY"
        Log "ENDPOINT_REMAINS_INSTALLED=YES"
        Log "AUDIO_READY=PASS"
        $FinalStatus="PASS"
    }
} catch {
    Log ("ERROR="+$_.Exception.Message)
    Log "PRODUCTION_DRIVER_LEFT_INSTALLED_FOR_DIAGNOSIS=YES"
    Log "AUTOMATIC_ROLLBACK=NO"
    $FinalStatus="FAIL"
}

Log ("FINAL_STATUS="+$FinalStatus)
Write-ResultZip

if ($FinalStatus -eq "PASS" -or $FinalStatus -eq "RESTORE_COMPLETE") { exit 0 }
exit 3
 -and
        ($keep -notcontains ([string]$_.Driver).ToLowerInvariant())
    })

    if ($stale.Count -eq 0) {
        Log "STALE_P360_PACKAGES=NONE"
        return
    }

    foreach($entry in $stale) {
        $name=[string]$entry.Driver
        $r=Invoke-Tool "pnputil.exe" @("/delete-driver",$name,"/force") -AllowFailure
        Log ("STALE_P360_PACKAGE_DELETE INF={0} EXIT={1}" -f $name,$r.ExitCode)
    }
}

function Install-Bundle([object]$Info) {
    $r=Invoke-Tool "pnputil.exe" @("/add-driver",$Inf,"/install") -AllowFailure
    if ($r.ExitCode -ne 0) {
        throw "Production bundle staging/install failed."
    }
    if ($r.Output -match '(?i)reboot is needed|restart is needed') {
        Log "REBOOT_REQUIRED=YES"
    }
    Invoke-Tool "pnputil.exe" @("/scan-devices") | Out-Null
    Start-Sleep -Milliseconds 800
}

function Wait-ProductionBinding([string]$Prefix,[string]$Service,[string]$Version,[int]$Seconds=20) {
    $deadline=(Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Milliseconds 500
        try {
            $dev=Get-OneDevice $Prefix
            $drv=Get-Driver ([string]$dev.PNPDeviceID)
            if ($drv -and
                [int]$dev.ConfigManagerErrorCode -eq 0 -and
                [string]$dev.Service -eq $Service -and
                [string]$drv.DriverProviderName -eq $Provider -and
                [string]$drv.DriverVersion -eq $Version) {
                return [pscustomobject]@{ Device=$dev; Driver=$drv }
            }
        } catch {}
    } while((Get-Date) -lt $deadline)
    return $null
}

function Assert-ProductionBinding([object]$Info) {
    $version=[string]$Info.DriverVersion
    $a=Wait-ProductionBinding $AdspPrefix $AdspService $version 20
    $m=Wait-ProductionBinding $AmpPrefix $AmpService $version 20
    if (-not $a -or -not $m) {
        throw "Production driver binding is not healthy for both ADSP and MAX98357A."
    }
    Log ("ADSP_BIND=PASS INF={0} VERSION={1}" -f [string]$a.Driver.InfName,[string]$a.Driver.DriverVersion)
    Log ("AMP_BIND=PASS INF={0} VERSION={1}" -f [string]$m.Driver.InfName,[string]$m.Driver.DriverVersion)
}

function Restart-ExactProductionDevices {
    $amp=Get-OneDevice $AmpPrefix
    $adsp=Get-OneDevice $AdspPrefix
    $ra=Invoke-Tool "pnputil.exe" @("/restart-device",[string]$amp.PNPDeviceID) -AllowFailure
    $rd=Invoke-Tool "pnputil.exe" @("/restart-device",[string]$adsp.PNPDeviceID) -AllowFailure
    Invoke-Tool "pnputil.exe" @("/scan-devices") -AllowFailure | Out-Null
    Log ("DEVICE_RESTART amp={0} adsp={1}" -f $ra.ExitCode,$rd.ExitCode)
    Start-Sleep -Seconds 1
}

function Reenumerate-Adsp {
    $adsp=Get-OneDevice $AdspPrefix
    $id=[string]$adsp.PNPDeviceID
    $r=Invoke-Tool "pnputil.exe" @("/remove-device",$id) -AllowFailure
    if ($r.ExitCode -ne 0) { return $false }
    Invoke-Tool "pnputil.exe" @("/scan-devices") -AllowFailure | Out-Null
    Start-Sleep -Seconds 1
    return $true
}

function Restart-WindowsAudio {
    try {
        Stop-Service -Name Audiosrv -Force -ErrorAction SilentlyContinue
        Stop-Service -Name AudioEndpointBuilder -Force -ErrorAction SilentlyContinue
        Start-Service -Name AudioEndpointBuilder -ErrorAction Stop
        Start-Service -Name Audiosrv -ErrorAction Stop
        Log "WINDOWS_AUDIO_SERVICES_RESTART=PASS"
        Start-Sleep -Seconds 1
    } catch {
        Log ("WINDOWS_AUDIO_SERVICES_RESTART=FAIL "+$_.Exception.Message)
    }
}

function Run-Wasapi([switch]$Preflight) {
    $args=@()
    if ($Preflight) { $args+= "--preflight" }
    $r=Invoke-Tool $Wasapi $args -AllowFailure
    if ($r.ExitCode -eq 0) {
        if ($Preflight) { Log "WASAPI_SHARED_PREFLIGHT=PASS" }
        else { Log "WASAPI_SHARED_ENDPOINT=PASS" }
        return $true
    }
    Log ("WASAPI_SHARED_TEST=FAIL EXIT="+$r.ExitCode)
    return $false
}

function Write-ResultZip {
    try {
        if (Test-Path -LiteralPath $StatePath) {
            Copy-Item -LiteralPath $StatePath -Destination (Join-Path $RunDir "STATE_SNAPSHOT.json") -Force
        }
        $zip=Join-Path $Desktop ("P360_PRODUCTION_RESULT_"+$RunStamp+".zip")
        Compress-Archive -Path (Join-Path $RunDir "*") -DestinationPath $zip -Force
        Write-Host "RESULT_ZIP=$zip"
    } catch {
        Write-Host ("RESULT_ZIP_ERROR="+$_.Exception.Message)
    }
}

function Restore-Original {
    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        throw "No original-driver backup exists. Restore is manual and cannot guess a baseline."
    }
    $state=Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json

    $amp=Get-OneDevice $AmpPrefix
    $adsp=Get-OneDevice $AdspPrefix
    $productionInfNames=@()
    foreach($dev in @($adsp,$amp)) {
        $drv=Get-Driver ([string]$dev.PNPDeviceID)
        if ($drv -and [string]$drv.DriverProviderName -eq $Provider) {
            $productionInfNames += [string]$drv.InfName
        }
    }

    Invoke-Tool "pnputil.exe" @("/remove-device",[string]$amp.PNPDeviceID) -AllowFailure | Out-Null
    Invoke-Tool "pnputil.exe" @("/remove-device",[string]$adsp.PNPDeviceID) -AllowFailure | Out-Null

    foreach($name in @($productionInfNames | Select-Object -Unique)) {
        if ($name -match '(?i)^oem\d+\.inf$') {
            Invoke-Tool "pnputil.exe" @("/delete-driver",$name,"/force") -AllowFailure | Out-Null
        }
    }

    foreach($entry in @($state.Adsp,$state.Amp)) {
        if ([bool]$entry.HadDriver -and [string]$entry.ExportedInf -and
            (Test-Path -LiteralPath ([string]$entry.ExportedInf) -PathType Leaf)) {
            Invoke-Tool "pnputil.exe" @("/add-driver",[string]$entry.ExportedInf,"/install") | Out-Null
        }
    }
    Invoke-Tool "pnputil.exe" @("/scan-devices") | Out-Null
    Restart-WindowsAudio
    Log "MANUAL_RESTORE_REQUESTED=YES"
    Log "MANUAL_RESTORE_STAGE=COMPLETE"
}

Assert-Admin
Log "PHASER360 PRODUCTION AUDIO"
Log ("MODE="+$Mode)
Log "ARCHITECTURE=WindowsAudio/WASAPI_SHARED->PortCls/WaveRT->P360SofAudio->SklHDAudBus/HDA_DMA->SOF_HOST->SSP1->MAX98357A"
Log "AUTOMATIC_ROLLBACK=NO"
Log "ALTERNATE_DRIVER_SWAP=NO"

try {
    if ($Mode -eq "Restore") {
        Restore-Original
        $FinalStatus="RESTORE_COMPLETE"
    } else {
        $info=Assert-Package
        Ensure-OriginalBackup
        Import-PackageCertificate
        Install-Bundle $info

        $passed=$false
        for($round=1;$round -le 3;$round++) {
            Log ("REPAIR_ROUND="+$round)
            try {
                Assert-ProductionBinding $info
                if (-not (Run-Wasapi -Preflight)) {
                    throw "WASAPI shared preflight failed."
                }
                if (-not (Run-Wasapi)) {
                    throw "WASAPI shared playback failed."
                }
                $passed=$true
                break
            } catch {
                Log ("ROUND_FAIL="+$_.Exception.Message)
                if ($round -eq 1) {
                    Restart-ExactProductionDevices
                    Restart-WindowsAudio
                    Install-Bundle $info
                } elseif ($round -eq 2) {
                    [void](Reenumerate-Adsp)
                    Install-Bundle $info
                    Restart-WindowsAudio
                }
            }
        }

        if (-not $passed) {
            throw "WASAPI shared endpoint did not become functional after same-package repairs."
        }

        Assert-ProductionBinding $info
        Log "FINAL_ACCEPTANCE=WASAPI_SHARED_ENDPOINT_FUNCTIONAL"
        Log "WAVEOUT_ROLE=LOWER_LEVEL_DIAGNOSTIC_ONLY"
        Log "ENDPOINT_REMAINS_INSTALLED=YES"
        Log "AUDIO_READY=PASS"
        $FinalStatus="PASS"
    }
} catch {
    Log ("ERROR="+$_.Exception.Message)
    Log "PRODUCTION_DRIVER_LEFT_INSTALLED_FOR_DIAGNOSIS=YES"
    Log "AUTOMATIC_ROLLBACK=NO"
    $FinalStatus="FAIL"
}

Log ("FINAL_STATUS="+$FinalStatus)
Write-ResultZip

if ($FinalStatus -eq "PASS" -or $FinalStatus -eq "RESTORE_COMPLETE") { exit 0 }
exit 3
