#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done

if [[ -z "$PYTHON" ]]; then
  echo "ERROR: Python 3.12+ nu este instalat."
  exit 1
fi

if ! command -v deno >/dev/null 2>&1; then
  echo "ERROR: Deno 2.3+ nu este instalat. VcdResolver il foloseste pentru challenge-urile YouTube."
  echo "Instalare oficiala: https://deno.com/"
  exit 1
fi

if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

LAN_IP="$(
  hostname -I 2>/dev/null     | awk '{print $1}'     || true
)"

if [[ -z "$LAN_IP" ]]; then
  LAN_IP="IP-UL-PC-ULUI"
fi

echo
echo "VcdResolver porneste pe:"
echo "  http://127.0.0.1:8085"
echo "Din iPhone, in aceeasi retea:"
echo "  http://${LAN_IP}:8085"
echo
echo "Lasa terminalul deschis cat timp testezi. Pentru VPS seteaza optional VCD_API_TOKEN."
echo

exec python -m uvicorn app.main:app   --host 0.0.0.0   --port 8085
