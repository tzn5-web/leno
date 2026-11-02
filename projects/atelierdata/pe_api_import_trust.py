"""Conservative Windows PE import-provider checks for static API evidence.

An export name alone does not identify a Windows API implementation.
No binary is loaded or executed here.
"""
from __future__ import annotations

import re


def _trusted_windows_api_import(dll, families):
    """A matching export name alone is not evidence of a Windows file API.

    An arbitrary DLL can export ReadFile/GetProcAddress. API-set forwarder
    contracts are accepted only for their corresponding Windows API family.
    """
    dll = dll.upper()
    if dll in ("KERNEL32.DLL", "KERNELBASE.DLL"):
        return True
    # A prefix is not an API-set contract: arbitrary PE import DLL names
    # such as api-ms-win-core-file-malicious.dll must not be trusted.
    match = re.fullmatch(
        r"API-MS-WIN-CORE-(FILE|MEMORY|LIBRARYLOADER)-L[0-9]+-[0-9]+-[0-9]+\.DLL",
        dll,
    )
    if match is None:
        return False
    contract_family = match.group(1)
    if contract_family == "LIBRARYLOADER":
        return "dynamic_lookup" in families
    if contract_family == "MEMORY":
        return "file_mapping" in families
    return bool({"file_open", "file_read", "file_position"}.intersection(families))

