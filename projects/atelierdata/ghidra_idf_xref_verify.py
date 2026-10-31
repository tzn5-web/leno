"""Independently verify SHA-bound private Ghidra IDF xref evidence against PE bytes.

Does not execute the target or decode proprietary files. Reports stay private.
Ghidra reference counts remain claims of the Ghidra analysis database; only
literal-byte identities are independently checked here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from pe_file_io_xrefs import MAX_PE, parse_pe32

MAX_JSON = 8 * 1024 * 1024
MAX_SCAN = 128 * 1024 * 1024
MAX_HITS = 32
MAX_REFS = 32
PUBLIC_SCHEMA = "atelierdata-ghidra-idf-xrefs-public-v1"
PRIVATE_SCHEMA = "atelierdata-ghidra-idf-xrefs-private-v1"
TERMS = ("MODELS.IDF", "CONST.IDF", "CSS.IDF", "DTC.IDF", ".IDF",
         "inflate 1.2.3", "TFRMAUTODATABASE", "ChilkatCrypt2")


def limited_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_JSON + 1)
    if len(data) > MAX_JSON:
        raise ValueError("Report exceeds size limit")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("Report must be a JSON object")
    return result


def address_to_file(data, pe, address, length):
    if not isinstance(address, str) or not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{1,8}", address):
        raise ValueError("Unrecognized PE32 Ghidra address")
    va = int(address, 16)
    rva = va - pe["image_base"]
    matches = []
    for section in pe["sections"]:
        if section["raw_size"] and 0 <= rva - section["rva"] <= section["raw_size"] - length:
            matches.append(section["raw_at"] + rva - section["rva"])
    if len(matches) != 1:
        raise ValueError("Ghidra literal address has no unique PE raw mapping")
    at = matches[0]
    if at < 0 or at + length > len(data):
        raise ValueError("Literal extends beyond original PE")
    return at


def verify(data, expected_sha, private, public):
    if (not isinstance(expected_sha, str) or
        not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha)):
        raise ValueError("Expected SHA256 is mandatory")
    if len(data) > MAX_PE:
        raise ValueError("Original PE exceeds size limit")
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha.lower():
        raise ValueError("Original PE SHA256 mismatch")
    if private.get("schema") != PRIVATE_SCHEMA or public.get("schema") != PUBLIC_SCHEMA:
        raise ValueError("Unsupported Ghidra evidence schema")
    if private.get("private_only") is not True:
        raise ValueError("Private evidence flag missing")
    shared = {key: value for key, value in private.items()
              if key not in ("schema", "private_only", "hits_with_addresses")}
    shared["schema"] = PUBLIC_SCHEMA
    if shared != public:
        raise ValueError("Private and public Ghidra reports disagree")
    if (public.get("original_sha256_verified") != digest or
        public.get("ghidra_program_md5_verified") is not True or
        public.get("target_executed") is not False or
        public.get("idf_decoder_proven") is not False):
        raise ValueError("Evidence identity or safety flags mismatch")
    if (type(public.get("scanned_bytes")) is not int or
        not 0 < public["scanned_bytes"] <= MAX_SCAN or
        type(public.get("initialized_blocks")) is not int or
        public["initialized_blocks"] < 1 or
        type(public.get("scan_truncated")) is not bool):
        raise ValueError("Invalid Ghidra scan coverage")
    pe = parse_pe32(data)
    patterns = public.get("patterns")
    hits = private.get("hits_with_addresses")
    if not isinstance(patterns, dict) or not isinstance(hits, dict):
        raise ValueError("Missing pattern evidence")
    expected_keys = {term + ":" + enc for term in TERMS for enc in ("ascii", "utf16le")}
    if set(patterns) != expected_keys or not set(hits).issubset(expected_keys):
        raise ValueError("Unexpected pattern names")
    total_hits = total_code_refs = 0
    for key in sorted(expected_keys):
        term, encoding = key.rsplit(":", 1)
        needle = term.encode("ascii" if encoding == "ascii" else "utf-16le")
        rows = hits.get(key, [])
        aggregate = patterns[key]
        if not isinstance(rows, list) or len(rows) > MAX_HITS or not isinstance(aggregate, dict):
            raise ValueError("Invalid pattern evidence rows")
        seen = set()
        refs = code_refs = 0
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Invalid hit")
            address = row.get("address")
            if address in seen:
                raise ValueError("Duplicate Ghidra literal address")
            seen.add(address)
            at = address_to_file(data, pe, address, len(needle))
            if data[at:at + len(needle)] != needle:
                raise ValueError("Ghidra literal does not match verified original bytes")
            count, code = row.get("reference_count"), row.get("code_reference_count")
            ref_list = row.get("references_from")
            if (type(count) is not int or type(code) is not int or
                not 0 <= code <= count or not isinstance(ref_list, list) or
                len(ref_list) > MAX_REFS or len(ref_list) != min(count, MAX_REFS) or
                row.get("references_from_truncated") is not (count > MAX_REFS)):
                raise ValueError("Inconsistent Ghidra reference counts")
            if any(not isinstance(item, str) for item in ref_list):
                raise ValueError("Invalid Ghidra reference address")
            refs += count
            code_refs += code
        if (aggregate.get("hits_at_most_32") != len(rows) or
            aggregate.get("hit_cap_reached") is not (len(rows) == MAX_HITS) or
            aggregate.get("ghidra_existing_references") != refs or
            aggregate.get("ghidra_existing_code_references") != code_refs):
            raise ValueError("Ghidra public aggregate does not match private evidence")
        total_hits += len(rows)
        total_code_refs += code_refs
    return {"status": "EVIDENCE_CONSISTENT", "original_sha256": digest,
            "verified_literal_hits": total_hits,
            "ghidra_claimed_code_references": total_code_refs,
            "ghidra_runtime_execution_verified": False,
            "idf_decoder_proven": False,
            "limitation": "Original literal bytes verified; Ghidra disassembly and references not independently reproduced."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pe", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--private-ghidra", type=Path, required=True)
    parser.add_argument("--public-ghidra", type=Path, required=True)
    args = parser.parse_args()
    with args.pe.open("rb") as stream:
        data = stream.read(MAX_PE + 1)
    result = verify(data, args.expected_sha256,
                    limited_json(args.private_ghidra), limited_json(args.public_ghidra))
    print("GHIDRA_IDF_EVIDENCE=" + result["status"] +
          " literal_hits=" + str(result["verified_literal_hits"]) +
          " claimed_code_xrefs=" + str(result["ghidra_claimed_code_references"]))


if __name__ == "__main__":
    main()
