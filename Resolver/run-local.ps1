$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = $null

foreach ($candidate in @("python", "python3", "py")) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue

    if ($command) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    Write-Host "ERROR: Python 3.12+ nu este instalat." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Node.js nu este instalat. VcdResolver il foloseste pentru challenge-urile YouTube." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv")) {
    & $python -m venv .venv
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

$lanIP = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.InterfaceOperationalStatus -eq "Up"
    } |
    Sort-Object InterfaceMetric |
    Select-Object -First 1 -ExpandProperty IPAddress

if (-not $lanIP) {
    $lanIP = "IP-UL-PC-ULUI"
}

Write-Host ""
Write-Host "VcdResolver porneste pe:"
Write-Host "  http://127.0.0.1:8085"
Write-Host "Din iPhone, in aceeasi retea:"
Write-Host ("  http://{0}:8085" -f $lanIP)
Write-Host ""
Write-Host "Lasa fereastra deschisa cat timp testezi."
Write-Host ""

& $venvPython -m uvicorn app.main:app --host 0.0.0.0 --port 8085
