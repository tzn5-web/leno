#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VANCED = ROOT / "VancedIOS"
WORKFLOWS = ROOT / ".github" / "workflows"

EXPECTED_PACKAGES = {
    "youmod.deb": "YouMod.dylib",
    "ytvideooverlay.deb": "YTVideoOverlay.dylib",
    "youpip.deb": "YouPiP.dylib",
    "ytuhd.deb": "YTUHD.dylib",
    "return-youtube-dislikes.deb": "YouTubeDislikesReturn.dylib",
    "vancedios-core.deb": "VancedIOSCore.dylib",
}

EXPECTED_LOCAL_REPOS = {
    "YouMod": "YouMod",
    "YTVideoOverlay": "YTVideoOverlay",
    "YouPiP": "YouPiP",
    "YTUHD": "YTUHD",
    "ReturnYouTubeDislikes": "Return-YouTube-Dislikes",
    "Theos": "theos",
    "iOSSDKs": "iOS-SDKs",
}


@dataclass
class Check:
    name: str
    status: str
    detail: str


class Audit:
    def __init__(self, report_dir: Path) -> None:
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.checks: list[Check] = []

    def add(self, name: str, status: str, detail: str) -> None:
        self.checks.append(Check(name, status, detail))
        print(f"[{status}] {name}: {detail}")

    def require(self, name: str, condition: bool, ok: str, bad: str) -> None:
        self.add(name, "PASS" if condition else "FAIL", ok if condition else bad)

    def command(
        self,
        name: str,
        argv: list[str],
        env: dict[str, str] | None = None,
    ) -> bool:
        proc = subprocess.run(
            argv,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        log_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name) + ".log"
        (self.report_dir / log_name).write_text(proc.stdout or "", encoding="utf-8")
        if proc.returncode == 0:
            self.add(name, "PASS", f"exit 0; log={log_name}")
            return True
        self.add(name, "FAIL", f"exit {proc.returncode}; log={log_name}")
        return False

    def finish(self, host_state: str, build_requested: bool) -> int:
        failures = [c for c in self.checks if c.status == "FAIL"]
        if failures:
            final = "FAIL"
        elif host_state == "FULL":
            final = "PASS_FULL"
        elif host_state == "HOST_VALIDATED":
            final = "PASS_HOST_VALIDATED"
        else:
            final = "PASS_HOSTLESS"

        payload = {
            "final_status": final,
            "build_requested": build_requested,
            "host_state": host_state,
            "failure_count": len(failures),
            "checks": [asdict(c) for c in self.checks],
        }
        (self.report_dir / "report.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        lines = [
            "# VancedIOS stage audit",
            "",
            f"Final status: {final}",
            "",
        ]
        lines.extend(
            f"- {c.status} | {c.name} | {c.detail}"
            for c in self.checks
        )
        (self.report_dir / "report.md").write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )
        print(f"FINAL_VANCEDIOS_STAGE={final}")
        return 1 if failures else 0


def load_manifest(audit: Audit) -> dict:
    try:
        manifest = json.loads(
            (VANCED / "manifest.json").read_text(encoding="utf-8")
        )
    except Exception as exc:
        audit.add("manifest.parse", "FAIL", str(exc))
        return {}
    audit.add("manifest.parse", "PASS", "valid JSON")
    return manifest


def static_contract(audit: Audit, manifest: dict) -> None:
    target = manifest.get("target", {})
    deps = manifest.get("dependencies", {})
    validation = manifest.get("host_validation", {})
    payload = manifest.get("payload", {})

    audit.require(
        "architecture",
        manifest.get("architecture")
        == "youtube-official-plus-injected-modular-tweaks",
        "official YouTube host plus injected modules",
        "wrong architecture",
    )
    audit.require(
        "host.bundle",
        target.get("bundle_id") == "com.google.ios.youtube",
        "official YouTube bundle pinned",
        "bundle id is not com.google.ios.youtube",
    )
    audit.require(
        "host.minimum-ios",
        target.get("minimum_ios") == "15.0",
        "minimum iOS aligned to pinned rootless modules",
        "minimum iOS must be 15.0",
    )
    audit.require(
        "host.version-pin",
        bool(
            re.fullmatch(
                r"\d+\.\d+\.\d+",
                str(target.get("tested_youtube_version") or ""),
            )
        ),
        f"tested version={target.get('tested_youtube_version')}",
        "missing/malformed tested_youtube_version",
    )
    audit.require(
        "host.decrypted",
        validation.get("require_decrypted") is True,
        "cryptid=0 required",
        "decrypted host is not mandatory",
    )
    audit.require(
        "host.arm64",
        "arm64" in validation.get("required_arches", []),
        "arm64 required",
        "arm64 not required",
    )
    audit.require(
        "host.background-audio",
        "audio" in validation.get("required_background_modes", []),
        "UIBackgroundModes audio required",
        "background audio mode is not required",
    )

    sha40 = re.compile(r"^[0-9a-f]{40}$")
    bad = [
        name
        for name, dep in deps.items()
        if not sha40.fullmatch(str(dep.get("commit") or ""))
    ]
    audit.require(
        "dependencies.pins",
        not bad,
        "all dependency commits immutable",
        "non-exact pins: " + ", ".join(bad),
    )
    audit.require(
        "payload.dylibs",
        set(payload.get("required_dylibs", []))
        == set(EXPECTED_PACKAGES.values()),
        "required dylib set complete",
        "required dylib set does not match package contract",
    )


def repository_scan(audit: Audit) -> None:
    proprietary = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        name = path.name.lower()
        if path.is_file() and name.endswith(".ipa"):
            proprietary.append(str(path.relative_to(ROOT)))
        if path.is_dir() and name == "youtube.app":
            proprietary.append(str(path.relative_to(ROOT)))
    audit.require(
        "repo.no-youtube-binary",
        not proprietary,
        "no host IPA/app committed",
        "proprietary host artifacts: " + ", ".join(proprietary),
    )

    core = (VANCED / "Core" / "VancedIOSCore.xm").read_text(
        encoding="utf-8",
        errors="replace",
    )
    forbidden = [
        token
        for token in (
            "MPRemoteCommandCenter",
            "AVAudioSession",
            "applicationDidEnterBackground",
            "applicationWillEnterForeground",
            "applicationWillResignActive",
            "applicationDidBecomeActive",
        )
        if token in core
    ]
    audit.require(
        "core.single-media-authority",
        not forbidden,
        "official YouTube media session remains authoritative",
        "competing media lifecycle tokens: " + ", ".join(forbidden),
    )

    required_defaults = [
        "YouModEnablesBackgroundPlayback",
        "YouModSBEnabled",
        "YouPiPEnabled",
        "YouModWifiQualityIndex",
        "YouModCellQualityIndex",
        "YouModLowPowerQualityIndex",
        "YouModAutoSpeedIndex",
    ]
    missing = [key for key in required_defaults if key not in core]
    audit.require(
        "core.defaults",
        not missing,
        "background/PiP/SponsorBlock/quality/speed contract exposed",
        "missing defaults: " + ", ".join(missing),
    )


def syntax_scan(audit: Audit) -> None:
    for path in sorted(VANCED.rglob("*.py")):
        audit.command(
            f"syntax.python.{path.name}",
            [sys.executable, "-m", "py_compile", str(path)],
        )
    for path in sorted(VANCED.rglob("*.sh")):
        audit.command(
            f"syntax.shell.{path.name}",
            ["bash", "-n", str(path)],
        )


def workflow_scan(audit: Audit) -> None:
    workflows = sorted(WORKFLOWS.glob("vanced-ios-*.yml"))
    audit.require(
        "workflow.present",
        bool(workflows),
        f"{len(workflows)} VancedIOS workflows",
        "no VancedIOS workflows found",
    )

    unpinned = []
    missing_permissions = []
    legacy = []
    for path in workflows:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not re.search(
            r"(?m)^permissions:\s*\n(?:[ \t].*\n)*?[ \t]+contents:\s*read\s*$",
            text,
        ):
            missing_permissions.append(path.name)
        for match in re.finditer(r"uses:\s*([^\s@]+)@([^\s#]+)", text):
            if not re.fullmatch(r"[0-9a-f]{40}", match.group(2)):
                unpinned.append(
                    f"{path.name}:{match.group(1)}@{match.group(2)}"
                )
        for token in ("WKWebView", "MPVRender", "Resolver/", "V9Player"):
            if token in text:
                legacy.append(f"{path.name}:{token}")

    audit.require(
        "workflow.pinned-actions",
        not unpinned,
        "all actions pinned to commit SHA",
        "mutable action refs: " + ", ".join(unpinned),
    )
    audit.require(
        "workflow.permissions",
        not missing_permissions,
        "least privilege contents: read",
        "missing permissions in: " + ", ".join(missing_permissions),
    )
    audit.require(
        "workflow.no-legacy-runtime",
        not legacy,
        "no active WebView/MPV/V9 pipeline",
        "legacy references: " + ", ".join(legacy),
    )


def verify_dependency_heads(audit: Audit, manifest: dict, work: Path) -> None:
    for name, local_name in EXPECTED_LOCAL_REPOS.items():
        path = work / local_name
        expected = str(
            manifest.get("dependencies", {}).get(name, {}).get("commit") or ""
        )
        if not (path / ".git").exists():
            audit.add(f"dependency.{name}", "FAIL", f"missing clone {path}")
            continue
        proc = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        actual = proc.stdout.strip()
        audit.require(
            f"dependency.{name}",
            proc.returncode == 0 and actual == expected,
            f"HEAD={expected}",
            f"expected {expected}, got {actual or '<none>'}",
        )


def package_scan(audit: Audit, dist: Path) -> None:
    present = {p.name for p in dist.glob("*.deb")} if dist.is_dir() else set()
    audit.require(
        "packages.complete",
        present == set(EXPECTED_PACKAGES),
        "exact six-package set produced",
        f"package set={sorted(present)}",
    )

    hashes = []
    for package_name, dylib_name in EXPECTED_PACKAGES.items():
        package = dist / package_name
        if not package.is_file():
            continue
        hashes.append(
            f"{hashlib.sha256(package.read_bytes()).hexdigest()}  {package_name}"
        )
        with tempfile.TemporaryDirectory(prefix="vancedios-deb-") as temp:
            proc = subprocess.run(
                ["dpkg-deb", "-x", str(package), temp],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                audit.add(
                    f"package.extract.{package_name}",
                    "FAIL",
                    proc.stdout.strip(),
                )
                continue
            matches = list(Path(temp).rglob(dylib_name))
            audit.require(
                f"package.dylib.{package_name}",
                len(matches) == 1,
                f"contains {dylib_name}",
                f"{dylib_name} count={len(matches)}",
            )
            if len(matches) != 1:
                continue
            arch = subprocess.run(
                ["lipo", "-archs", str(matches[0])],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            arches = arch.stdout.strip().split()
            audit.require(
                f"package.arch.{package_name}",
                arch.returncode == 0
                and "arm64" in arches
                and "x86_64" not in arches,
                "arm64 device dylib",
                "architectures=" + " ".join(arches),
            )

    (audit.report_dir / "SHA256SUMS").write_text(
        "\n".join(hashes) + ("\n" if hashes else ""),
        encoding="utf-8",
    )


def build_phase(
    audit: Audit,
    manifest: dict,
    work: Path,
    dist: Path,
) -> None:
    env = dict(os.environ)
    env["VANCEDIOS_WORK"] = str(work)
    env["VANCEDIOS_DIST"] = str(dist)
    if not audit.command(
        "build.patches",
        ["bash", str(VANCED / "Scripts" / "build_patches.sh")],
        env=env,
    ):
        return
    verify_dependency_heads(audit, manifest, work)
    audit.command(
        "dependencies.contract",
        [
            sys.executable,
            str(VANCED / "Scripts" / "audit_patches.py"),
            str(work),
        ],
    )
    package_scan(audit, dist)


def host_phase(audit: Audit, args: argparse.Namespace) -> str:
    if args.ipa is None:
        audit.add(
            "host.dynamic",
            "SKIP",
            "no user-supplied decrypted IPA; hostless audit only",
        )
        return "HOSTLESS"

    validator = VANCED / "Scripts" / "validate_ipa.py"
    manifest = VANCED / "manifest.json"
    if not audit.command(
        "host.validate-input",
        [
            sys.executable,
            str(validator),
            "host",
            str(args.ipa),
            "--manifest",
            str(manifest),
        ],
    ):
        return "HOST_FAILED"

    if not args.inject:
        audit.add("host.inject", "SKIP", "input validated; injection not requested")
        return "HOST_VALIDATED"

    if args.output is None:
        audit.add("host.inject", "FAIL", "--inject requires --output")
        return "HOST_FAILED"

    if not audit.command(
        "host.inject",
        [
            "bash",
            str(VANCED / "Scripts" / "inject.sh"),
            str(args.ipa),
            str(args.output),
            args.bundle_id,
            args.display_name,
        ],
    ):
        return "HOST_FAILED"

    if not audit.command(
        "host.validate-output",
        [
            sys.executable,
            str(validator),
            "output",
            str(args.output),
            "--manifest",
            str(manifest),
            "--bundle-id",
            args.bundle_id,
            "--display-name",
            args.display_name,
        ],
    ):
        return "HOST_FAILED"
    return "FULL"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Autonomous VancedIOS stage audit/build runner"
    )
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--ipa", type=Path)
    parser.add_argument("--inject", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle-id", default="com.google.ios.youtube")
    parser.add_argument("--display-name", default="YouTube")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=ROOT / ".vancedios-build",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=ROOT / "dist" / "vanced-ios",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=ROOT / "artifacts" / "vanced-ios-stage-audit",
    )
    args = parser.parse_args()

    audit = Audit(args.report_dir)
    manifest = load_manifest(audit)
    if manifest:
        static_contract(audit, manifest)
    repository_scan(audit)
    syntax_scan(audit)
    workflow_scan(audit)

    audit.command(
        "architecture.audit",
        [sys.executable, str(VANCED / "Scripts" / "audit.py")],
    )

    if args.build and manifest:
        build_phase(audit, manifest, args.work_dir, args.dist_dir)
    else:
        audit.add("build.patches", "SKIP", "build not requested")

    host_state = host_phase(audit, args)
    return audit.finish(host_state, args.build)


if __name__ == "__main__":
    raise SystemExit(main())
