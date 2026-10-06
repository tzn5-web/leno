#!/usr/bin/env python3
from pathlib import Path
import hashlib
import re
import sys

ROOT=Path(__file__).resolve().parents[1]

PINNED={
    "sof_core/p360_transport_core.c":"fe593c280b7d66a152fe28997b9e76ed5eecc59105ffddc1cc1acccdb642fbee",
    "sof_core/p360_transport_core.h":"e89e42e0ba5119dbd4670fa607f6e81d33f19c25eeb744df08e6713c661c41d5",
    "sof_core/loader/p360_loader.c":"476a53cab8901a891a53a76eddfdb1b5f64dbdf270bfe0cbb3211e0623c05379",
    "sof_core/loader/p360_loader.h":"358dac81c37edcda164c4f075b7ed7644e989570221f0c29be43ce56cdd3d1df",
    "sof_core/loader/p360_dispatch.c":"397428e361f8bb8a18172cd5503f7e4450cdeea80ab4096f7e0a7b8b4c6f1fa8",
    "sof_core/loader/p360_dispatch.h":"790472539798e630c444b16d7f3fde86d174e095e51a462d2764ff9d596133e1",
    "sof_core/loader/p360_fw_image.c":"3b370ae00596ff8ae3f3ca4c30e62a078a9c178af6a261c4d0009164854b6ab7",
    "sof_core/loader/p360_ipc_timer.c":"37148efb6a24877ae4379038eb1c108ab8b8f02824a5bfda1051b2d21454a0e9",
    "sof_core/loader/p360_ipc_timer.h":"2df15b4d9e0b16380d96503e83192e03e5d4685121f36a27e11af9b4e7e891d3",
    "sof_core/loader/p360_irq.c":"04dae608b067e3c7d4bf399f025a30a5cf0a2dc37737cea686bd1b033f813d81",
    "sof_core/loader/p360_irq.h":"0afd7c95168b4bb27db871e48c4acd10f92ff808394ad66c733f83fb2164e42d",
}

for rel,want in PINNED.items():
    p=ROOT/rel
    if not p.is_file():
        raise SystemExit(f"missing pinned B4 file: {rel}")
    got=hashlib.sha256(p.read_bytes()).hexdigest()
    if got!=want:
        raise SystemExit(f"B4 provenance drift: {rel}: {got} != {want}")

for name in (
    "p360_loader.c","p360_loader.h","p360_dispatch.c","p360_dispatch.h",
    "p360_fw_image.c","p360_irq.c","p360_irq.h",
    "p360_ipc_timer.c","p360_ipc_timer.h"
):
    if (ROOT/"sof_core"/name).exists():
        raise SystemExit(f"duplicate B4 source reintroduced: sof_core/{name}")

safety=(ROOT/"include/p360_safety.h").read_text()
if not re.search(r"#define\s+P360_ENABLE_INTERNAL_SPEAKER\s+0\b",safety):
    raise SystemExit("internal speaker compile-time barrier is not zero")

boot=(ROOT/"src/p360_cs_boot.c").read_text()
for forbidden in ("p360_cs_boot_set_processing", "P360_PPCTL_OFFSET"):
    if forbidden in boot:
        raise SystemExit(f"direct PPCTL ownership reintroduced: {forbidden}")

bus=(ROOT/"src/p360_cs_bus.c").read_text()
if "if (!bus->ppcap)" not in bus:
    raise SystemExit("CoolStar PP capability hard gate missing")

abi=(ROOT/"include/p360_coolstar_adsp.h").read_text()
for token in (
    "P360_CS_ADSP_INTERFACE_VERSION 1u",
    "0x752a2cae",
    "sizeof(P360_CS_ADSP_BUS_INTERFACE) == 144",
    "sizeof(P360_CS_PCI_BAR) == 16",
):
    if token not in abi:
        raise SystemExit(f"CoolStar ABI pin missing: {token}")

print("Phaser360 source contract: PASS")
