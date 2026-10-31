# Ghidra evidence replay — static-only verification (2026-10-31)

This workflow is **prepared**, not a claim that Ghidra ran on the original. It prevents stale or modified PE-triage JSON from being accepted as a match for the original executable. It also checks internal consistency of a Ghidra report. It does **not** establish an IDF decoder or runtime reachability.

## Inputs and privacy

Keep the original ADBCD.exe and two detailed JSON reports **private** on an authorized workstation or private Drive workspace. Do not commit them to the public GitHub repository or upload them as public Actions artifacts. ZIP part 0016 is blocked and must not be bypassed.

1. Original PE, SHA256: a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4.
2. Private triage from pe_loadlibrary_literals.py with --private-output.
3. Private Ghidra report from AtelierData_LoadLibrary_Argument_Check.java, run with the same private triage and correctly imported original PE. The Java script checks Ghidra's imported program MD5 and instruction boundaries. It must be run in a properly configured private Ghidra installation; no Ghidra execution is implied by adding the script.

## Run the cross-check locally (read-only)

~~~powershell
python projects/atelierdata/ghidra_evidence_replay.py --pe C:\PRIVATE\ADBCD.exe --expected-sha256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 --private-triage C:\PRIVATE\loadlibrary-details.json --private-ghidra C:\PRIVATE\ghidra-details.json --public-output C:\PRIVATE\ghidra-aggregate.json
~~~

The replay independently hashes and reparses the original PE, regenerates **every candidate** and requires an exact match with the private triage (including addresses, literals and MD5). It then checks Ghidra's reported identity, candidate membership, boolean relationships and aggregate counts. It writes only aggregate counters; no proprietary bytes, filenames, call addresses or DLL literals appear in the output.

GHIDRA_EVIDENCE_REPLAY=PASS would mean **consistency with these static observations only**, not proof of actual dynamic execution, full CFG reachability or IDF format decoding. A fabricated but internally consistent Ghidra report cannot be ruled out by this check; provenance still depends on a genuine Ghidra run and its private logs.

## Synthetic CI coverage

test_ghidra_evidence_replay.py uses an invented PE32 fixture and invented Ghidra report to verify rejection of tampered binaries, SHA256 mismatches, modified triage candidates, contradictory Ghidra counters and symlinked inputs. The public Windows workflow runs this synthetic suite before building AtelierData.exe.

Also fixed the technical_specs.list_specs search to treat %, _ and backslash literally and reject invalid input, with regression coverage. This improves AtelierData independently of proprietary source material.

## Open research questions

- Ghidra direct-call graph: verify whether candidate LoadLibraryA calls belong to identified functions and whether their containing functions appear in the bounded direct-call graph. A missing direct path does not prove unreachable code.
- Identify a **legitimate, documented** data-access API or an authorized export for .IDF; existing repetitive-byte/entropy observations alone cannot identify record semantics.
- No static report should be labeled as a decoder without independently verifiable parsing of authorized test data and format documentation.
