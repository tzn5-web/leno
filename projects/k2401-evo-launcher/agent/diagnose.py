#!/usr/bin/env python3
"""K2401 diagnostic agent: bounded, read-only investigation with optional LLM analysis.

GitHub Actions supplies GITHUB_TOKEN (actions:read, models:read) and an Azure OIDC
identity for VM inspection. The agent NEVER starts a VM, deploys or patches code.
Its JSON is an auditable recommendation, not proof that an APK is production-ready.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = os.environ.get("GITHUB_REPOSITORY", "tzn5-web/leno")
RUN_ID = os.environ.get("K2401_RUN_ID", "40382269545")
MODEL = os.environ.get("K2401_MODEL_ID", "openai/gpt-4.1-mini")
OUTPUT = Path(os.environ.get("K2401_AGENT_OUTPUT", "agent-output"))
OUTPUT.mkdir(parents=True, exist_ok=True)
ALLOWED_STATUSES = {"completed", "in_progress", "queued", "waiting", "requested", "pending"}


def request_json(url: str, token: str, payload: dict | None = None, timeout: int = 16) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "K2401-EVO-agent/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, separators=(",", ":")).encode()
    with urlopen(Request(url, data=body, headers=headers, method="POST" if payload else "GET"), timeout=timeout) as res:
        return json.load(res)


def read_run(token: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", REPO):
        raise ValueError("Invalid GitHub repository")
    if not RUN_ID.isdecimal():
        raise ValueError("Invalid workflow run ID")
    base = f"https://api.github.com/repos/{REPO}/actions/runs/{RUN_ID}"
    run = request_json(base, token)
    job_data = request_json(base + "/jobs?per_page=100", token)
    jobs = []
    for job in job_data.get("jobs", [])[:35]:
        jobs.append({
            "name": str(job.get("name", ""))[:120],
            "status": job.get("status"),
            "conclusion": job.get("conclusion"),
            "failed_steps": [str(s.get("name", ""))[:120] for s in job.get("steps", [])
                             if s.get("conclusion") == "failure"],
        })
    status = run.get("status", "unknown")
    if status not in ALLOWED_STATUSES:
        raise ValueError("Unexpected run status")
    return {"run_id": RUN_ID, "url": run.get("html_url"), "status": status,
            "conclusion": run.get("conclusion"), "jobs": jobs}


def vm_state() -> str:
    cmd = ["az", "vm", "show", "-g", "rg-phaser360-driverlab", "-n", "int34d2-lab",
           "--show-details", "--query", "powerState", "-o", "tsv"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=22, check=False)
        return p.stdout.strip() if p.returncode == 0 else "UNAVAILABLE (Azure read failed)"
    except (OSError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"


def diagnosis(run: dict, power: str) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    repairs: list[str] = []
    failed = [step for j in run["jobs"] for step in j["failed_steps"]]
    joined = " ".join(failed).lower()
    if "execute android emulator inside azure windows vm" in joined:
        findings.append("Azure Windows emulator execution failed. The previous run exceeded its 48-minute timeout.")
        repairs.append("Check Windows nested virtualization/WHPX BEFORE SDK download; fail fast if unavailable.")
        repairs.append("Use GitHub-hosted Android 10 KVM emulator for app/UI functional proof, not software-emulated nested Windows.")
    if "prepare isolated temporary azure blob transfer" in joined:
        findings.append("Azure Blob transfer failed.")
        repairs.append("Verify Microsoft.Storage is Registered and storage account is accessible before VM start.")
    if run["status"] == "completed" and run["conclusion"] == "success":
        findings.append("Workflow passed, but physical K2401 radio/CAN/reverse-camera compatibility remains unvalidated.")
    elif run["status"] != "completed":
        findings.append("Workflow is still running; no final PASS yet.")
    elif not failed and run["conclusion"] != "success":
        findings.append("Workflow failed with no named failing step; inspect job artifacts.")
    if power == "VM running" and run["status"] == "completed":
        findings.append("COST ALERT: VM is still running AFTER the CI run completed.")
        repairs.append("Deallocate the VM promptly; investigate why cleanup did not finish.")
    elif power == "VM deallocated":
        findings.append("VM is deallocated; no active VM compute billing.")
    else:
        findings.append("VM state: " + power)
    return findings, repairs


def inference(run: dict, findings: list[str], repairs: list[str], token: str) -> tuple[str, str]:
    if not token or os.getenv("K2401_USE_AI", "1") != "1":
        return "disabled", ""
    prompt = {
        "objective": "Analyze root cause and propose a minimal verified code/CI repair for K2401 EVO Android 10.",
        "constraints": ["Budget total 200 USD", "Never start Azure VM or suggest blind retries",
                        "Keep actual Maps vs demo and OBD real vs simulated truthfully labeled",
                        "No MCU/CAN firmware writing", "Do not claim hardware validation"],
        "observations": {"run": run, "vm_power": os.getenv("K2401_VM_STATE_OVERRIDE") or vm_state(),
                         "findings": findings, "proposed_repairs": repairs},
        "output": "Concise Romanian diagnosis, immediate next edit, how to verify, cost risk. No secrets.",
    }
    payload = {
        "model": MODEL, "messages": [
            {"role": "system", "content": "You are a conservative autonomous CI diagnostic agent. You have no write tools. Distinguish proven facts from hypotheses. Suggest only bounded tests."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ], "temperature": 0.1, "max_tokens": 580,
    }
    try:
        result = request_json("https://models.github.ai/inference/chat/completions", token, payload, timeout=24)
        answer = str(result.get("choices", [{}])[0].get("message", {}).get("content", ""))
        if not answer.strip():
            return "empty", ""
        return "success", answer[:5000]
    except HTTPError as exc:
        # An HTTP status identifies configuration/rate-limit problems without printing tokens.
        return "unavailable", f"HTTP {exc.code} from GitHub Models"
    except (URLError, TimeoutError, ValueError, KeyError, IndexError) as exc:
        return "unavailable", type(exc).__name__


def main() -> int:
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        print("Missing GITHUB_TOKEN; no GitHub API access", file=sys.stderr)
        return 2
    try:
        run = read_run(token)
    except Exception as exc:
        print("GITHUB_AUDIT_FAILED=" + type(exc).__name__, file=sys.stderr)
        return 2
    power = vm_state()
    findings, repairs = diagnosis(run, power)
    # Single inference max; optional and quota bounded.
    ai_state, ai_text = inference(run, findings, repairs, token)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "run": run,
              "azure_vm_power": power, "findings": findings,
              "recommended_fixes": repairs, "ai_state": ai_state, "ai_analysis": ai_text,
              "agent_writes_to_azure": False, "agent_restarts_vm": False,
              "release_ready": False}
    (OUTPUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# K2401 diagnostic report", "",
             f"Run: {run['url'] or RUN_ID}", f"Status: {run['status']} / {run['conclusion']}",
             f"Azure VM: **{power}**", "## Findings"]
    lines += ["- " + v for v in findings]
    lines += ["", "## Repair candidates"] + ["- " + v for v in repairs]
    lines += ["", "## AI interpretation", "Model state: " + ai_state, "", ai_text or "(none)"]
    summary = "\n".join(lines) + "\n"
    (OUTPUT / "report.md").write_text(summary, encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(summary)
    print(f"K2401_AGENT=PASS vm={power!r} run={run['conclusion']!r} ai={ai_state}")
    if power == "VM running" and run["status"] == "completed":
        print("K2401_AGENT_COST_ALERT=VM_LEFT_RUNNING", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
