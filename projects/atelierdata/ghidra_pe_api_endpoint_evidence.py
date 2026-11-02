"""PE-byte-corroborated *direct IAT* API endpoint candidates from private Ghidra xrefs.

This does not disassemble independently or establish runtime reachability.
Dynamic resolution, delay imports, indirect calls and .IDF decoding remain unknown.
Only callers can publish aggregate counts; never serialize returned addresses.
"""
from __future__ import annotations

import struct

from ghidra_api_callsite_replay import _raw_offset
from pe_api_import_trust import _trusted_windows_api_import
from ghidra_idf_callgraph_triage import FAMILIES, _address


def _same_executable_section(pe, function, site):
    """Require a candidate caller entry before its callsite in one backed section.

    This is a conservative provenance filter, not a function-boundary proof.
    """
    if function > site:
        return False
    base = pe["image_base"]
    first, last = function - base, site - base
    for section in pe["sections"]:
        backed = min(section["raw_size"], section["vsize"])
        start = section["rva"]
        if (section["executable"] and backed >= 6 and
                start <= first <= last and last + 6 <= start + backed):
            return True
    return False


def pe_backed_api_endpoints(binary, pe, api_report):
    """Return API-family function sets backed by exact FF 15 IAT bytes.

    A single physical callsite with conflicting function/API attribution is
    discarded entirely. Ghidra instruction boundaries are still assertions.
    """
    sites = {}
    tainted_sites = set()
    for api_name, symbols in api_report["api_symbols"].items():
        families = tuple(name for name, members in FAMILIES.items()
                         if api_name in members)
        if not families:
            continue
        for symbol in symbols:
            for ref in symbol["references"]:
                # Any conflicting or incomplete Ghidra claim at a known
                # physical callsite disqualifies the site. Otherwise one
                # valid row could conceal another contradictory row.
                source = ref.get("source_address")
                if source is None:
                    continue
                site = _address(source)
                if (ref.get("reference_type") != "UNCONDITIONAL_CALL" or
                        ref.get("reference_is_call_or_jump") is not True or
                        ref.get("instruction_mnemonic") != "CALL" or
                        type(ref.get("instruction_length")) is not int or
                        ref["instruction_length"] != 6 or
                        ref.get("instruction_start_address") is None or
                        ref.get("function_entry") is None):
                    tainted_sites.add(site)
                    continue
                if site != _address(ref["instruction_start_address"]):
                    tainted_sites.add(site)
                    continue
                function = _address(ref["function_entry"])
                sites.setdefault(site, set()).add((api_name, function, families))

    endpoints = {family: set() for family in FAMILIES}
    matched = conflicts = 0
    for site, candidates in sites.items():
        if site in tainted_sites or len(candidates) != 1:
            conflicts += 1
            continue
        api_name, function, families = next(iter(candidates))
        mapped = _raw_offset(binary, pe, site, 6)
        function_mapped = _raw_offset(binary, pe, function, 1)
        if (mapped is None or not mapped[1] or
                function_mapped is None or not function_mapped[1] or
                not _same_executable_section(pe, function, site)):
            continue
        offset = mapped[0]
        if binary[offset:offset + 2] != b"\xff\x15":
            continue
        iat_address = struct.unpack_from("<I", binary, offset + 2)[0]
        imported = pe["imports"].get(iat_address)
        if (imported is None or imported["symbol"] != api_name or
                not _trusted_windows_api_import(imported["dll"], families)):
            continue
        matched += 1
        for family in families:
            endpoints[family].add(function)
    return endpoints, matched, conflicts
