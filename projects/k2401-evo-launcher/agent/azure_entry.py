#!/usr/bin/env python3
"""K2401 Azure-native diagnostic AI job; manual/ephemeral, no inbound port or secrets.

Runs inside an Azure Container Apps Job with its OWN read-only managed identity.
The identity has Reader only on a pre-existing VM and Cognitive Services OpenAI User
only on the existing Foundry resource. No GitHub PAT or service principal secret.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = "tzn5-web/leno"
RUN_ID = os.getenv("K2401_RUN_ID", "40382269545")
AZURE_RESOURCE = "andreplaja-6488-resource"
AZURE_ENDPOINT = "https://andreplaja-6488-resource.cognitiveservices.azure.com"
AZURE_DEPLOYMENT = "k2401-gpt41mini"
AZURE_API_VERSION = "2024-10-21"


def cli(args: list[str], timeout: int = 25) -> str:
    done = subprocess.run(["az"] + args, text=True, capture_output=True, timeout=timeout)
    if done.returncode:
        raise RuntimeError("Azure CLI failed: " + " ".join(args[:3]))
    return done.stdout.strip()


def github_json(path: str) -> dict:
    url = f"https://api.github.com/repos/{REPO}/{path}"
    with urlopen(Request(url, headers={"Accept": "application/vnd.github+json",
                                       "User-Agent": "K2401-Azure-Agent/1.0"}), timeout=20) as response:
        return json.load(response)


def azure_ai(prompt: dict) -> dict:
    # Preferred: managed identity. Fallback: an Azure Container Apps secret with
    # the existing Foundry account's key, never exported to logs or the repository.
    account_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    token = ""
    if not account_key:
        token = cli(["account", "get-access-token", "--resource",
                     "https://cognitiveservices.azure.com", "--query", "accessToken", "-o", "tsv"])
    payload = {
        "messages": [
            {"role": "system", "content": ("You are K2401 EVO's bounded Azure diagnostic agent. "
             "Explain verified cause and safe next patch in Romanian. "
             "Never write MCU, CAN, flash ROM, start VMs or suggest repeated expensive tests. "
             "Distinguish Google Maps DEMO from real Maps SDK and OBD SIMULATED from live telemetry.")},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "max_tokens": 450,
    }
    url = (f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions"
           f"?api-version={AZURE_API_VERSION}")
    headers = {"Content-Type": "application/json"}
    if account_key:
        headers["api-key"] = account_key
    else:
        headers["Authorization"] = "Bearer " + token
    req = Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                  headers=headers)
    with urlopen(req, timeout=45) as response:
        return json.load(response)


def main() -> int:
    if not re.fullmatch(r"[0-9]{8,13}", RUN_ID):
        raise ValueError("Invalid K2401 run id")
    identity_client_id = os.getenv("AZURE_CLIENT_ID", "")
    if identity_client_id:
        if not re.fullmatch(r"[0-9a-f-]{36}", identity_client_id):
            raise ValueError("Invalid managed identity client id")
        cli(["login", "--identity", "--client-id", identity_client_id, "-o", "none"], timeout=25)
    elif not os.getenv("AZURE_OPENAI_API_KEY"):
        raise ValueError("Neither Azure MI nor encrypted Azure AI API-key secret is available")
    run = github_json(f"actions/runs/{RUN_ID}")
    jobs = github_json(f"actions/runs/{RUN_ID}/jobs?per_page=100")
    steps = [
        {"job": str(j.get("name"))[:70],
         "failed": [s.get("name") for s in j.get("steps", []) if s.get("conclusion") == "failure"]}
        for j in jobs.get("jobs", [])[:25]
    ]
    if identity_client_id:
        power = cli(["vm", "show", "-g", "rg-phaser360-driverlab", "-n", "int34d2-lab",
                     "--show-details", "--query", "powerState", "-o", "tsv"])
    else:
        # Report externally verified GitHub OIDC check as a timestamped snapshot.
        # Do not pretend the Azure job itself holds VM Reader privileges.
        power = os.getenv("K2401_VM_POWER", "UNVERIFIED")
    safe_context = {
        "run_id": RUN_ID,
        "run_status": run.get("status"),
        "run_conclusion": run.get("conclusion"),
        "vm_power": power,
        "failed_steps": steps,
        "known_prior_failure": "Windows Android emulator timed out at 48 minutes; "
                               "nested virtualization/WHPX not verified before SDK download.",
        "budget": "Azure Free Trial 200 USD total, avoid idle or repeated Windows VM boots.",
        "app_goal": "K2401 Android 10 EVO launcher: half-screen real navigation, "
                    "YouTube Music top right, 4 real OBD gauges bottom right. "
                    "No hardware or actual Google Maps SDK validation yet.",
        "allowed": "diagnostic only; output plan, no resource mutations",
    }
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), **safe_context,
              "model": AZURE_DEPLOYMENT, "model_status": "not_called", "analysis": ""}
    try:
        response = azure_ai(safe_context)
        result["analysis"] = str(response.get("choices", [{}])[0].get("message", {}).get("content", ""))[:4000]
        result["model_status"] = "PASS" if result["analysis"] else "EMPTY"
    except HTTPError as exc:
        result["model_status"] = f"HTTP_{exc.code}"
    except (URLError, RuntimeError, ValueError, KeyError, TimeoutError, IndexError) as exc:
        result["model_status"] = type(exc).__name__
    # Single output and bounded model tokens. No secrets or token text in output.
    print("K2401_AZURE_AGENT_REPORT=" + json.dumps(result, ensure_ascii=False))
    if run.get("status") == "completed" and power == "VM running":
        print("K2401_COST_ALERT=VM_LEFT_RUNNING", file=sys.stderr)
        return 4
    if result["model_status"] != "PASS":
        print("K2401_AZURE_AI_NOT_READY=" + result["model_status"], file=sys.stderr)
        return 3
    print("K2401_AZURE_AGENT=PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("K2401_AZURE_AGENT_FATAL=" + type(e).__name__, file=sys.stderr)
        sys.exit(2)
