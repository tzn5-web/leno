# K2401 EVO - Windows Azure VM emulator runner
# Called only through Azure VM Run Command. No changes to MCU, car hardware or Windows boot config.
param([Parameter(Mandatory=$true)][string]$SasUrlB64, [Parameter(Mandatory=$true)][string]$ExpectedApkSha)
$SasUrl = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($SasUrlB64))
if ($ExpectedApkSha -notmatch '^[0-9a-fA-F]{64}$') { throw 'Invalid APK SHA256 parameter' }
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = 'C:\K2401-EVO-LAB'
$sdk = Join-Path $root 'android-sdk'
$results = Join-Path $root 'results'
$script:status = 'FAIL'
$script:detail = 'Unspecified'
New-Item -ItemType Directory -Force -Path $root,$sdk,$results | Out-Null
$parts = $SasUrl.Split('?',2)
if ($parts.Length -ne 2 -or $parts[0] -notmatch '^https://[a-z0-9]+\.blob\.core\.windows\.net/[^/]+$') { throw 'Invalid scoped storage SAS URL' }
$baseUrl = $parts[0]; $sas = $parts[1]
function SendResult([string]$FilePath,[string]$Destination,[string]$Mime) {
    if (!(Test-Path $FilePath)) { return }
    $dest = "$baseUrl/$Destination" + '?' + $sas
    Invoke-WebRequest -Uri $dest -Method Put -InFile $FilePath -ContentType $Mime -Headers @{'x-ms-blob-type'='BlockBlob';'x-ms-version'='2020-10-02'} -UseBasicParsing | Out-Null
}
function ExecNative([string]$Exe,[string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Exe $($Arguments -join ' ')" }
}
try {
    # BEFORE any JDK/SDK downloads or costly software emulation: prove WHPX is enabled.
    # Do not change Windows features on the shared Phaser360 driver-lab VM.
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $system = Get-CimInstance Win32_ComputerSystem
    $whpx = Get-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -ErrorAction Stop
    $capability = [ordered]@{
        checkedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
        hypervisorPresent = [bool]$system.HypervisorPresent
        firmwareVirtualization = [bool]$cpu.VirtualizationFirmwareEnabled
        secondLevelAddressTranslation = [bool]$cpu.SecondLevelAddressTranslationExtensions
        whpxFeatureState = [string]$whpx.State
        processorName = [string]$cpu.Name
        decision = 'NO_SOFTWARE_EMULATOR'
    }
    ($capability | ConvertTo-Json -Depth 3) | Out-File -FilePath (Join-Path $results 'windows-capability.json') -Encoding UTF8
    if ($whpx.State -ne 'Enabled' -or
        (-not $system.HypervisorPresent -and -not $cpu.VirtualizationFirmwareEnabled)) {
        throw 'WHPX_NOT_READY: Windows HypervisorPlatform or nested virtualization is unavailable. Azure VM cannot run the fast Android emulator; run Android 10 KVM test in GitHub instead.'
    }
    $java = Get-ChildItem -Path $root -Recurse -Filter java.exe -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match '\\bin\\java.exe$' } | Select-Object -First 1
    if (!$java) {
        $jdkZip = Join-Path $root 'jdk17.zip'
        Invoke-WebRequest -Uri 'https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse' -OutFile $jdkZip -UseBasicParsing
        Expand-Archive $jdkZip -DestinationPath $root -Force
        $java = Get-ChildItem -Path $root -Recurse -Filter java.exe | Where-Object { $_.FullName -match '\\bin\\java.exe$' } | Select-Object -First 1
    }
    if (!$java) { throw 'Portable Java 17 not found' }
    $env:JAVA_HOME = Split-Path (Split-Path $java.FullName -Parent) -Parent
    $env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
    $tools = Join-Path $sdk 'cmdline-tools\latest\bin\sdkmanager.bat'
    if (!(Test-Path $tools)) {
        $toolsZip = Join-Path $root 'android-cmdline-tools.zip'
        Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip' -OutFile $toolsZip -UseBasicParsing
        $actualHash = (Get-FileHash -Path $toolsZip -Algorithm SHA256).Hash.ToLowerInvariant()
        $expectedHash = '90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a'
        if ($actualHash -ne $expectedHash) { throw 'ANDROID_SDK_TOOL_ARCHIVE_SHA256_MISMATCH' }
        $unpacked = Join-Path $root 'android-cli-unpacked'
        Expand-Archive $toolsZip -DestinationPath $unpacked -Force
        New-Item -ItemType Directory -Force -Path (Join-Path $sdk 'cmdline-tools') | Out-Null
        Move-Item -Path (Join-Path $unpacked 'cmdline-tools') -Destination (Join-Path $sdk 'cmdline-tools\latest')
    }
    $env:ANDROID_HOME = $sdk
    $env:ANDROID_SDK_ROOT = $sdk
    $env:ANDROID_AVD_HOME = Join-Path $root 'avd'
    New-Item -ItemType Directory -Force -Path $env:ANDROID_AVD_HOME | Out-Null
    $sdkArgs = @("--sdk_root=$sdk",'platform-tools','emulator','system-images;android-29;google_apis;x86_64')
    # Accept SDK package licenses and install supported Android 10 image.
    (('y' + [Environment]::NewLine) * 120) | & $tools "--sdk_root=$sdk" '--licenses' | Out-Null
    (('y' + [Environment]::NewLine) * 120) | & $tools @sdkArgs | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "ANDROID_SDK_INSTALL_FAILED=$LASTEXITCODE" }
    $avdtool = Join-Path $sdk 'cmdline-tools\latest\bin\avdmanager.bat'
    $adb = Join-Path $sdk 'platform-tools\adb.exe'
    $emulator = Join-Path $sdk 'emulator\emulator.exe'
    if (!(Test-Path (Join-Path $env:ANDROID_AVD_HOME 'k2401api29.avd'))) {
        'no' | & $avdtool create avd --force -n k2401api29 -k 'system-images;android-29;google_apis;x86_64'
        if ($LASTEXITCODE -ne 0) { throw 'AVD_CREATION_FAILED' }
    }
    $apk = Join-Path $root 'launcher.apk'
    Invoke-WebRequest -Uri ("$baseUrl/launcher.apk" + '?' + $sas) -OutFile $apk -UseBasicParsing
    if ((Get-Item $apk).Length -lt 8000) { throw 'APK_STAGING_EMPTY' }
    $foundApkSha = (Get-FileHash -Path $apk -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($foundApkSha -ne $ExpectedApkSha.ToLowerInvariant()) { throw 'APK_TRANSFER_SHA256_MISMATCH' }
    "APK_SHA256=$foundApkSha" | Out-File -FilePath (Join-Path $results 'apk-hash.txt') -Encoding UTF8
    & $adb start-server | Out-Null
    $accelInfo = (& $emulator -accel-check 2>&1 | Out-String)
    $accelInfo | Out-File -FilePath (Join-Path $results 'accel.txt')
    $args = @('-avd','k2401api29','-no-window','-no-audio','-no-boot-anim','-no-snapshot','-no-metrics','-gpu','swiftshader_indirect','-memory','2048','-partition-size','2048','-skin','1280x720','-accel','off')
    # Deliberately avoid enabling Hyper-V/WHPX or changing Windows features on an existing driver-lab VM.
    if ($accelInfo -notmatch '(?i)acceleration.*usable|WHPX.*installed and usable') {
        throw 'ANDROID_EMULATOR_ACCELERATION_UNAVAILABLE: refusing an unaccelerated 48-minute loop'
    }
    $args[-1] = 'on'
    $proc = Start-Process -FilePath $emulator -ArgumentList $args -PassThru -WindowStyle Hidden
    $booted = $false
    for ($attempt=0;$attempt -lt 120;$attempt++) {
        Start-Sleep -Seconds 7
        $state = (& $adb -e shell getprop sys.boot_completed 2>$null | Out-String).Trim()
        if ($state -eq '1') { $booted = $true; break }
        if ($proc.HasExited) { throw "EMULATOR_EXITED_EARLY=$($proc.ExitCode)" }
    }
    if (!$booted) { throw 'EMULATOR_BOOT_TIMEOUT_14_MIN' }
    ExecNative $adb @('-e','shell','wm','size','1280x720')
    ExecNative $adb @('-e','shell','wm','density','160')
    ExecNative $adb @('-e','install','-r',$apk)
    ExecNative $adb @('-e','shell','am','start','-W','-n','ro.evolauncher.k2401/.MainActivity')
    Start-Sleep -Seconds 4
    $pages = @(
        @('home',120), @('music',225), @('navigation',332),
        @('car',435), @('apps',545), @('settings',645)
    )
    foreach ($entry in $pages) {
        $name = $entry[0]; $y = $entry[1]
        ExecNative $adb @('-e','shell','input','tap','45',"$y")
        Start-Sleep -Seconds 1
        ExecNative $adb @('-e','shell','screencap','-p',"/sdcard/$name.png")
        ExecNative $adb @('-e','pull',"/sdcard/$name.png",(Join-Path $results "$name.png"))
        $bytes = [System.IO.File]::ReadAllBytes((Join-Path $results "$name.png"))
        if ($bytes.Length -lt 24 -or $bytes[0] -ne 137) { throw "SCREENSHOT_INVALID_$name" }
        [Array]::Reverse($bytes,16,4); [Array]::Reverse($bytes,20,4)
        $width = [BitConverter]::ToUInt32($bytes,16); $height = [BitConverter]::ToUInt32($bytes,20)
        if ($width -ne 1280 -or $height -ne 720) { throw "SCREEN_DIMENSIONS_$name=$($width)x$height" }
    }
    ExecNative $adb @('-e','shell','am','force-stop','ro.evolauncher.k2401')
    ExecNative $adb @('-e','shell','am','start','-W','-n','ro.evolauncher.k2401/.MainActivity')
    Start-Sleep -Seconds 2
    $pidResult = (& $adb -e shell pidof ro.evolauncher.k2401 | Out-String).Trim()
    if (!$pidResult) { throw 'APP_NOT_RUNNING_AFTER_RELAUNCH' }
    (& $adb -e shell dumpsys meminfo ro.evolauncher.k2401 | Out-String) | Out-File (Join-Path $results 'memory.txt')
    (& $adb -e shell dumpsys gfxinfo ro.evolauncher.k2401 | Out-String) | Out-File (Join-Path $results 'gfxinfo.txt')
    $logText = (& $adb -e logcat -d -s AndroidRuntime:E ActivityManager:E | Out-String)
    $logText | Out-File (Join-Path $results 'logcat.txt')
    if ($logText -match '(?s)FATAL EXCEPTION.*?Process: ro\.evolauncher\.k2401') { throw 'LAUNCHER_CRASH' }
    $script:status = 'PASS'
    $script:detail = 'Android 10 emulator: 1280x720, six screenshots, relaunch, memory and logcat collected'
} catch {
    $script:status = 'FAIL'
    $script:detail = $_.Exception.Message
} finally {
    "STATUS=$script:status`r`nDETAIL=$script:detail`r`nAPK=ro.evolauncher.k2401`r`nMAP=DEMO`r`nOBD=SIMULATED_IN_EMULATOR" |
        Out-File -FilePath (Join-Path $results 'report.txt') -Encoding UTF8
    Get-ChildItem $results -File | ForEach-Object {
        try {
            $mime = if ($_.Extension -eq '.png') { 'image/png' } else { 'text/plain' }
            SendResult $_.FullName ("results/" + $_.Name) $mime
        } catch {
            Write-Output "UPLOAD_FAILED: $($_.Name): $($_.Exception.Message)"
        }
    }
    try { if ($proc -and !$proc.HasExited) { Stop-Process -Id $proc.Id -Force } } catch {}
    Write-Output "K2401_AZURE_TEST_STATUS=$script:status"
    Write-Output "DETAIL=$script:detail"
    if ($script:status -ne 'PASS') { throw "K2401_EMULATOR_TEST_FAILED: $script:detail" }
}
