# AtelierData — private Ghidra direct-callgraph triage (2026-11-01)

This extension addresses a limitation of the existing IDF/API correlation:
the xref reports can identify the same function, but do not identify
possible intermediate function calls between a function referencing an
.IDF filename and a function referencing a file I/O API.

## New implementation

- tools/ghidra/AtelierData_Direct_Callgraph.py is a read-only Jython post-script
  for a private Ghidra project. It enumerates Ghidra-recognized direct
  UNCONDITIONAL_CALL references between functions, bounded by function,
  instruction and edge caps. It independently hashes the authorized original
  PE (SHA256 and MD5) and checks both hashes against Ghidra imported-program
  metadata before producing a private JSON graph.
- projects/atelierdata/ghidra_idf_callgraph_triage.py accepts that private
  graph plus the two existing private IDF/API xref reports. It checks their
  source hashes and no-execution flags and computes shortest static
  function-edge distances (0–3 hops) from functions with .IDF literal
  references to functions with Ghidra-reported API CALL references.
- The output is aggregate-only JSON: no function addresses, callsite
  addresses, filename strings, binary bytes, or proprietary records.
  GetProcAddress is a separate category, not direct file I/O.
  Contradictory callsite targets and invalid identities fail closed.

## Private execution

Run the existing AtelierData_IDF_Xrefs.py and
AtelierData_File_API_Xrefs.py post-scripts on the same private Ghidra
imported program, then run AtelierData_Direct_Callgraph.py with these
three script arguments, in order:

1. Path to the original authorized, locally available AD(B)CD.exe.
2. Expected independently recorded SHA256.
3. Private output path for the callgraph JSON.

The previously documented expected SHA256 for AD(B)CD.exe is
a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4.
This value is a historical expected hash, not a fresh verification in
this development step.

Run the offline correlation with:

    python projects/atelierdata/ghidra_idf_callgraph_triage.py --idf-private-report C:\PRIVATE\idf-xrefs.json --api-private-report C:\PRIVATE\file-api-xrefs.json --callgraph-private-report C:\PRIVATE\callgraph.json --expected-sha256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 --public-output C:\PRIVATE\callgraph-aggregate.json

Do not place private input files, Ghidra projects, original binaries,
callgraph JSON or proprietary .IDF data in public GitHub or public CI.

## Evidence limitations

A path in Ghidra's static callgraph does not prove that any of its calls
are runtime reachable, that .IDF is read along that path, or that the
program can decode the format. This implementation deliberately excludes
computed/indirect calls and paths longer than three function edges.
Ghidra disassembly, missing xrefs and truncation can all cause omissions.
The exporter itself still needs real execution within Ghidra on the
verified original before any original-specific result can be claimed.

Public Windows CI exercises only synthetic fixtures. No executable from the
private archive is run. No license/DRM protection is bypassed and the
Google Drive-blocked part_0016 is not accessed.
