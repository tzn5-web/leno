$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RepoRoot = Resolve-Path (Join-Path $Root "..\..")
$Upstream = Join-Path $RepoRoot "_upstream\sklhdaudbus"
$Commit = "5477b93a3b68c474819abf2094a49d0e2d8d9799"

function Run-Git {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "git failed ($LASTEXITCODE): git $($Args -join ' ')"
    }
}

function Replace-Once {
    param([string]$Path,[string]$Old,[string]$New,[string]$Label)
    $text = Get-Content -LiteralPath $Path -Raw
    $idx = $text.IndexOf($Old, [System.StringComparison]::Ordinal)
    if ($idx -lt 0) { throw "Patch anchor not found: $Label in $Path" }
    if ($text.IndexOf($Old, $idx + $Old.Length, [System.StringComparison]::Ordinal) -ge 0) {
        throw "Patch anchor not unique: $Label in $Path"
    }
    $text = $text.Substring(0,$idx) + $New + $text.Substring($idx + $Old.Length)
    [System.IO.File]::WriteAllText($Path, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "PATCHED: $Label"
}

if (Test-Path $Upstream) { Remove-Item -Recurse -Force $Upstream }
New-Item -ItemType Directory -Force -Path (Split-Path $Upstream) | Out-Null

Run-Git clone https://github.com/coolstar/sklhdaudbus.git $Upstream
Run-Git -C $Upstream checkout --detach $Commit

$inf = Join-Path $Upstream "sklhdaudbus\sklhdaudbus.inf"
$pdo = Join-Path $Upstream "sklhdaudbus\buspdo.cpp"
$fdo = Join-Path $Upstream "sklhdaudbus\fdo.cpp"
$vcx = Join-Path $Upstream "sklhdaudbus\sklhdaudbus.vcxproj"

Replace-Once $inf '%SklHDAudBus.DeviceDesc%=SklHDAudBus_Device, PCI\VEN_8086&DEV_3198&CC_0401 ;Intel Gemini Lake' '%P360SklHDAudBus.DeviceDesc%=SklHDAudBus_Device, PCI\VEN_8086&DEV_3198&CC_0401 ;Google Phaser360 / Intel Gemini Lake' "Phaser360 Gemini Lake model"

Replace-Once $inf 'HKR,Settings,"ConnectInterrupt",0x00010001,0' 'HKR,Settings,"ConnectInterrupt",0x00010001,1
HKR,Settings,"Phaser360Mode",0x00010001,1' "Enable interrupt intent + Phaser360 marker"

Replace-Once $inf 'SklHDAudBus.DeviceDesc = "CoolStar HD Audio"
SklHDAudBus.SVCDESC    = "CoolStar HD Audio Service"' 'SklHDAudBus.DeviceDesc = "CoolStar HD Audio"
P360SklHDAudBus.DeviceDesc = "PHASER360 Gemini Lake HD Audio Bus"
SklHDAudBus.SVCDESC    = "CoolStar HD Audio Service"' "Phaser360 friendly name"

$pdoAnchor = @'
        status = WdfPdoInitAddCompatibleID(DeviceInit, &compatId);
        if (!NT_SUCCESS(status)) {
            return status;
        }
    }
    else {
'@

$pdoReplacement = @'
        status = WdfPdoInitAddCompatibleID(DeviceInit, &compatId);
        if (!NT_SUCCESS(status)) {
            return status;
        }

        /*
         * PHASER360 / Gemini Lake bridge identity.
         * Keep canonical CSAUDIO\ADSP for production SOF and add a
         * project-specific compatible ID for the custom host.
         */
        if (Desc->CodecIds.CtlrVenId == 0x8086 &&
            Desc->CodecIds.CtlrDevId == 0x3198) {
            status = RtlUnicodeStringPrintf(&compatId, L"P360AUDIO\\ADSP_GEMINILAKE");
            if (!NT_SUCCESS(status)) {
                return status;
            }

            status = WdfPdoInitAddCompatibleID(DeviceInit, &compatId);
            if (!NT_SUCCESS(status)) {
                return status;
            }
        }
    }
    else {
'@
Replace-Once $pdo $pdoAnchor $pdoReplacement "Phaser360 DSP compatible ID"

Replace-Once $fdo '    UNREFERENCED_PARAMETER(ResourcesRaw);

    BOOLEAN fBar0Found = FALSE;' '    BOOLEAN fBar0Found = FALSE;' "Use raw resources for IRQ diagnostics"

$irqAnchor = @'
        switch (pDescriptor->Type)
        {
        case CmResourceTypeMemory:
'@

$irqReplacement = @'
        switch (pDescriptor->Type)
        {
        case CmResourceTypeInterrupt:
        {
            const BOOLEAN isMessage =
                ((pDescriptor->Flags & CM_RESOURCE_INTERRUPT_MESSAGE) != 0);

            if (isMessage) {
                SklHdAudBusPrint(DEBUG_LEVEL_INFO, DBG_INIT,
                    "[P360] IRQ translated: message-signaled Flags=0x%x\n",
                    pDescriptor->Flags);
            }
            else {
                SklHdAudBusPrint(DEBUG_LEVEL_INFO, DBG_INIT,
                    "[P360] IRQ translated: line Level=%lu Vector=%lu Affinity=0x%llx Flags=0x%x\n",
                    pDescriptor->u.Interrupt.Level,
                    pDescriptor->u.Interrupt.Vector,
                    (UINT64)pDescriptor->u.Interrupt.Affinity,
                    pDescriptor->Flags);
            }

            if (i < WdfCmResourceListGetCount(ResourcesRaw)) {
                PCM_PARTIAL_RESOURCE_DESCRIPTOR pRawDescriptor =
                    WdfCmResourceListGetDescriptor(ResourcesRaw, i);
                if (pRawDescriptor && pRawDescriptor->Type == CmResourceTypeInterrupt) {
                    const BOOLEAN rawIsMessage =
                        ((pRawDescriptor->Flags & CM_RESOURCE_INTERRUPT_MESSAGE) != 0);

                    if (rawIsMessage) {
                        SklHdAudBusPrint(DEBUG_LEVEL_INFO, DBG_INIT,
                            "[P360] IRQ raw: message-signaled Flags=0x%x\n",
                            pRawDescriptor->Flags);
                    }
                    else {
                        SklHdAudBusPrint(DEBUG_LEVEL_INFO, DBG_INIT,
                            "[P360] IRQ raw: line Level=%lu Vector=%lu Affinity=0x%llx Flags=0x%x\n",
                            pRawDescriptor->u.Interrupt.Level,
                            pRawDescriptor->u.Interrupt.Vector,
                            (UINT64)pRawDescriptor->u.Interrupt.Affinity,
                            pRawDescriptor->Flags);
                    }
                }
            }
            break;
        }

        case CmResourceTypeMemory:
'@
Replace-Once $fdo $irqAnchor $irqReplacement "Log actual raw/translated IRQ resource"

$vcxText = Get-Content -LiteralPath $vcx -Raw
$oldCount = ([regex]::Matches($vcxText, '<TimeStamp>1\.0\.6</TimeStamp>')).Count
if ($oldCount -ne 4) { throw "Expected 4 TimeStamp anchors, found $oldCount" }
$vcxText = $vcxText.Replace('<TimeStamp>1.0.6</TimeStamp>','<TimeStamp>1.1.0.360</TimeStamp>')
[System.IO.File]::WriteAllText($vcx, $vcxText, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "PATCHED: driver package version 1.1.0.360"

Run-Git -C $Upstream diff --check

$diff = & git -C $Upstream diff -- sklhdaudbus/sklhdaudbus.inf sklhdaudbus/buspdo.cpp sklhdaudbus/fdo.cpp sklhdaudbus/sklhdaudbus.vcxproj
if ($LASTEXITCODE -ne 0) { throw "git diff failed" }
$diff | Set-Content -LiteralPath (Join-Path $Root "PATCH_APPLIED.diff") -Encoding utf8NoBOM

$combined = (Get-Content $pdo -Raw) + (Get-Content $fdo -Raw) + (Get-Content $inf -Raw) + (Get-Content $vcx -Raw)
$mustContain = @('P360AUDIO\\ADSP_GEMINILAKE','[P360] IRQ translated:','PCI\VEN_8086&DEV_3198&CC_0401','<TimeStamp>1.1.0.360</TimeStamp>')
foreach ($needle in $mustContain) {
    if (-not $combined.Contains($needle)) { throw "Post-patch assertion failed: $needle" }
}

Write-Host "PHASER360 deterministic patch applied to pinned CoolStar commit $Commit"
Write-Host "Diff saved: $(Join-Path $Root 'PATCH_APPLIED.diff')"
