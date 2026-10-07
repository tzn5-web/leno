param(
    [ValidateSet("Install","Restore")]
    [string]$Mode="Install"
)

Set-StrictMode -Version 2.0
$ErrorActionPreference="Stop"

$Provider="PHASER360 Project"
$AdspHwid="CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198"
$AmpHwid="ACPI\MX98357A"
$AdspPrefix=$AdspHwid
$AmpPrefix=$AmpHwid
$AdspService="P360SofAudio"
$AmpService="P360Max98357Safe"

$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$Inf=Join-Path $Root "P360AudioBundle.inf"
$Cat=Join-Path $Root "P360AudioBundle.cat"
$Cert=Join-Path $Root "P360_TEST.cer"
$InfoPath=Join-Path $Root "PACKAGE_INFO.json"
$Wasapi=Join-Path $Root "P360_WASAPI_TEST.exe"
$Force=Join-Path $Root "P360_FORCE_INSTALL.exe"

$StateRoot=Join-Path $env:ProgramData "P360Audio"
$StatePath=Join-Path $StateRoot "ORIGINAL_STATE.json"
$RunStamp=Get-Date -Format "yyyyMMdd_HHmmss"
$Desktop=[Environment]::GetFolderPath("Desktop")
$RunDir=Join-Path $Desktop ("P360_FULL_INSTALL_RESULT_"+$RunStamp)
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
    $principal=New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
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
    if (-not $Expected) { throw "PACKAGE_INFO missing SHA256 for $Name" }
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
        "P360_WASAPI_TEST.exe","P360_FORCE_INSTALL.exe","PACKAGE_INFO.json"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $name) -PathType Leaf)) {
            throw "Full-install package missing $name"
        }
    }

    $info=Get-Content -LiteralPath $InfoPath -Raw | ConvertFrom-Json
    $version=Get-InfVersion $Inf
    if ([string]$info.DriverVersion -ne $version) {
        throw "PACKAGE_INFO DriverVersion does not match INF."
    }
    if ([string]$info.Provider -ne $Provider) {
        throw "Unexpected package provider."
    }

    Assert-FileHash "P360SofAudio.sys" ([string]$info.P360SofAudioSha256)
    Assert-FileHash "P360Max98357Safe.sys" ([string]$info.P360Max98357SafeSha256)
    Assert-FileHash "p360-f686.ri" ([string]$info.FirmwareSha256)
    Assert-FileHash "P360_WASAPI_TEST.exe" ([string]$info.WasapiTestSha256)
    Assert-FileHash "P360_FORCE_INSTALL.exe" ([string]$info.ForceInstallSha256)

    $fw=Get-Item -LiteralPath (Join-Path $Root "p360-f686.ri")
    if ($fw.Length -ne 246528 -or
        [string]$info.FirmwareSha256 -ne "f68694b6197250016a9c5ffb46fa8adaa599a32db95aa19a0ecf5bd4ed1c62ab") {
        throw "Pinned firmware identity mismatch."
    }

    $infText=Get-Content -LiteralPath $Inf -Raw
    foreach($token in @(
        $AdspHwid,$AmpHwid,"PKEY_AudioEngine_OEMFormat",
        "PKEY_AudioEndpoint_Association%,,%KSNODETYPE_SPEAKER%"
    )) {
        if ($infText -notmatch [regex]::Escape($token)) {
            throw "INF contract missing: $token"
        }
    }

    Log ("PACKAGE=PASS VERSION={0} HEAD={1}" -f $version,[string]$info.HeadSha)
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
        $hit=Get-ChildItem -LiteralPath $outDir -Filter "*.inf" -File -Recurse |
            Select-Object -First 1
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

    $state=[ordered]@{
        CapturedAt=(Get-Date).ToString("o")
        Adsp=(Export-CurrentDriver "adsp" (Get-OneDevice $AdspPrefix))
        Amp=(Export-CurrentDriver "amp" (Get-OneDevice $AmpPrefix))
    }
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatePath -Encoding UTF8
    Copy-Item -LiteralPath $StatePath -Destination (Join-Path $RunDir "ORIGINAL_STATE.json") -Force
    Log "ORIGINAL_BACKUP=PASS"
}

function Report-NonAudioBoot0000 {
    $items=@(Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -and
        $_.PNPDeviceID.StartsWith("ACPI\BOOT0000",[StringComparison]::OrdinalIgnoreCase)
    })
    foreach($item in $items) {
        Log ("BOOT0000=OBSERVED CODE={0} SERVICE={1} NOT_AUDIO_BLOCKER=YES" -f
            [int]$item.ConfigManagerErrorCode,[string]$item.Service)
    }
    if ($items.Count -eq 0) { Log "BOOT0000=NOT_PRESENT NOT_AUDIO_BLOCKER=YES" }
}

function Force-FullDriverBinding {
    $r=Invoke-Tool $Force @($Inf,$AdspHwid,$AmpHwid) -AllowFailure
    if ($r.ExitCode -ne 0 -and $r.ExitCode -ne 3010) {
        throw "Forced driver binding failed with exit code $($r.ExitCode)."
    }
    if ($r.ExitCode -eq 3010 -or $r.Output -match 'REBOOT_REQUIRED=YES') {
        Log "REBOOT_REQUIRED=YES"
    }
    Invoke-Tool "pnputil.exe" @("/scan-devices") -AllowFailure | Out-Null
    Start-Sleep -Seconds 1
}

function Wait-FullBinding([object]$Info,[int]$Seconds=25) {
    $deadline=(Get-Date).AddSeconds($Seconds)
    $version=[string]$Info.DriverVersion

    do {
        Start-Sleep -Milliseconds 500
        try {
            $adsp=Get-OneDevice $AdspPrefix
            $amp=Get-OneDevice $AmpPrefix
            $adspDrv=Get-Driver ([string]$adsp.PNPDeviceID)
            $ampDrv=Get-Driver ([string]$amp.PNPDeviceID)

            if ($adspDrv -and $ampDrv -and
                [int]$adsp.ConfigManagerErrorCode -eq 0 -and
                [int]$amp.ConfigManagerErrorCode -eq 0 -and
                [string]$adsp.Service -eq $AdspService -and
                [string]$amp.Service -eq $AmpService -and
                [string]$adspDrv.DriverProviderName -eq $Provider -and
                [string]$ampDrv.DriverProviderName -eq $Provider -and
                [string]$adspDrv.DriverVersion -eq $version -and
                [string]$ampDrv.DriverVersion -eq $version) {
                Log ("ADSP_BIND=PASS INF={0} VERSION={1}" -f
                    [string]$adspDrv.InfName,[string]$adspDrv.DriverVersion)
                Log ("AMP_BIND=PASS INF={0} VERSION={1}" -f
                    [string]$ampDrv.InfName,[string]$ampDrv.DriverVersion)
                return $true
            }
        } catch {}
    } while((Get-Date) -lt $deadline)

    return $false
}

function Restart-ExactDevices {
    foreach($prefix in @($AmpPrefix,$AdspPrefix)) {
        try {
            $dev=Get-OneDevice $prefix
            [void](Invoke-Tool "pnputil.exe" @("/restart-device",[string]$dev.PNPDeviceID) -AllowFailure)
        } catch {
            Log ("DEVICE_RESTART_SKIP PREFIX="+$prefix)
        }
    }
    Invoke-Tool "pnputil.exe" @("/scan-devices") -AllowFailure | Out-Null
    Start-Sleep -Seconds 1
}

function Restart-WindowsAudio {
    Stop-Service -Name Audiosrv -Force -ErrorAction SilentlyContinue
    Stop-Service -Name AudioEndpointBuilder -Force -ErrorAction SilentlyContinue
    Start-Service -Name AudioEndpointBuilder -ErrorAction Stop
    Start-Service -Name Audiosrv -ErrorAction Stop
    Log "WINDOWS_AUDIO_SERVICES_RESTART=PASS"
    Start-Sleep -Seconds 1
}

function Run-WasapiPreflight {
    $r=Invoke-Tool $Wasapi @("--preflight") -AllowFailure
    if ($r.ExitCode -eq 0) {
        Log "WINDOWS_AUDIO_ENDPOINT=PASS"
        return $true
    }
    Log ("WINDOWS_AUDIO_ENDPOINT=FAIL EXIT="+$r.ExitCode)
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

function Remove-StaleProjectPackages {
    $keep=@()
    foreach($prefix in @($AdspPrefix,$AmpPrefix)) {
        $dev=Get-OneDevice $prefix
        $drv=Get-Driver ([string]$dev.PNPDeviceID)
        if ($drv -and [string]$drv.InfName -match '(?i)^oem\d+\.inf$') {
            $keep += ([string]$drv.InfName).ToLowerInvariant()
        }
    }
    $keep=@($keep | Select-Object -Unique)

    $stale=@(Get-WindowsDriver -Online -All -ErrorAction Stop | Where-Object {
        [string]$_.ProviderName -eq $Provider -and
        [string]$_.Driver -match '(?i)^oem\d+\.inf$' -and
        ($keep -notcontains ([string]$_.Driver).ToLowerInvariant())
    })

    foreach($entry in $stale) {
        $name=[string]$entry.Driver
        $r=Invoke-Tool "pnputil.exe" @("/delete-driver",$name,"/force") -AllowFailure
        Log ("STALE_P360_DELETE INF={0} EXIT={1}" -f $name,$r.ExitCode)
    }
    if ($stale.Count -eq 0) { Log "STALE_P360_PACKAGES=NONE" }
}

function Install-FullStack([object]$Info) {
    # Stage first so the signed package is in Driver Store, then force this
    # exact INF onto both matching Phaser360 functions regardless of rank.
    $stage=Invoke-Tool "pnputil.exe" @("/add-driver",$Inf) -AllowFailure
    if ($stage.ExitCode -ne 0) {
        throw "Driver Store staging failed."
    }

    for($round=1;$round -le 3;$round++) {
        Log ("FULL_INSTALL_ROUND="+$round)
        Force-FullDriverBinding

        if (Wait-FullBinding $Info 25) {
            Restart-WindowsAudio
            if (Run-WasapiPreflight) {
                Remove-StaleProjectPackages
                return
            }

            [void](Reset-WasapiEndpointFormat)
            Restart-WindowsAudio
            if (Run-WasapiPreflight) {
                Remove-StaleProjectPackages
                return
            }
        }

        Restart-ExactDevices
    }

    throw "Full Phaser360 audio stack did not converge to a healthy Windows Audio endpoint."
}

function Write-ResultZip {
    try {
        if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
            Copy-Item -LiteralPath $StatePath -Destination (Join-Path $RunDir "STATE_SNAPSHOT.json") -Force
        }
        $zip=Join-Path $Desktop ("P360_FULL_INSTALL_RESULT_"+$RunStamp+".zip")
        Compress-Archive -Path (Join-Path $RunDir "*") -DestinationPath $zip -Force
        Write-Host "RESULT_ZIP=$zip"
    } catch {
        Write-Host ("RESULT_ZIP_ERROR="+$_.Exception.Message)
    }
}

function Restore-Original {
    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        throw "No saved original-driver state exists."
    }

    $state=Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    $currentInfs=@()

    foreach($prefix in @($AmpPrefix,$AdspPrefix)) {
        try {
            $dev=Get-OneDevice $prefix
            $drv=Get-Driver ([string]$dev.PNPDeviceID)
            if ($drv -and [string]$drv.DriverProviderName -eq $Provider) {
                $currentInfs += [string]$drv.InfName
            }
            [void](Invoke-Tool "pnputil.exe" @("/remove-device",[string]$dev.PNPDeviceID) -AllowFailure)
        } catch {}
    }

    foreach($name in @($currentInfs | Select-Object -Unique)) {
        if ($name -match '(?i)^oem\d+\.inf$') {
            [void](Invoke-Tool "pnputil.exe" @("/delete-driver",$name,"/force") -AllowFailure)
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
    Log "RESTORE=COMPLETE"
}

Assert-Admin
Log "PHASER360 FULL AUDIO DRIVER INSTALL"
Log ("MODE="+$Mode)
Log "TARGET=ADSP+MAX98357A+SOF+WAVERT+WINDOWS_AUDIO"
Log "PHYSICAL_AUDIO_TEST=NO"

try {
    if ($Mode -eq "Restore") {
        Restore-Original
        $FinalStatus="RESTORE_COMPLETE"
    } else {
        $info=Assert-Package
        Ensure-OriginalBackup
        Import-PackageCertificate
        Report-NonAudioBoot0000
        Install-FullStack $info

        Log "FULL_DRIVER_INSTALL=PASS"
        Log "WINDOWS_AUDIO_ENDPOINT=READY"
        Log "AUDIO_DRIVER_READY=YES"
        $FinalStatus="PASS"
    }
} catch {
    Log ("ERROR="+$_.Exception.Message)
    Log "FULL_DRIVER_INSTALL=FAIL"
    $FinalStatus="FAIL"
}

Log ("FINAL_STATUS="+$FinalStatus)
Write-ResultZip

if ($FinalStatus -eq "PASS" -or $FinalStatus -eq "RESTORE_COMPLETE") { exit 0 }
exit 3
