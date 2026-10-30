# Ghidra: bounded static interoperability investigation

The script `AtelierData_IDF_Xrefs.py` scans **an analyst-provided, legally obtained Windows executable** for a small set of known literal patterns (ASCII and UTF-16LE), records matching addresses and existing Ghidra cross-references, and writes a JSON report **to the analyst's private local directory**. It never launches the target executable, reads IDF file contents, bypasses a license, or claims that a decoder has been found.

## Headless example (run locally, not in public CI)

Install an official Ghidra release with the required Java version. In a private shell, replace the placeholders:

```bash
/path/to/ghidra/support/analyzeHeadless /private/ghidra-projects AtelierDataScan \
  -import /private/original/ADBCD.exe \
  -scriptPath /path/to/leno/tools/ghidra \
  -postScript AtelierData_IDF_Xrefs.py /private/reports/ADBCD_ghidra_xrefs.json \
  -analysisTimeoutPerFile 900 -max-cpu 2 -deleteProject
```

Verify SHA256 of the original executable **before** import, using the private inventory. The known original SHA256 for the analyzed sample is `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`. Do not upload the original executable, IDF files, a decompilation, or proprietary strings to the public repository. Inspect the output locally and publish only conclusions that do not disclose protected content.

**Status:** the Ghidra script is committed and syntax-checked in Windows CI, but no successful Ghidra headless execution on the original binary has been verified. The previously observed `inflate 1.2.3` and `TFRMAUTODATABASE` literals are leads, not proof of an IDF loader. Absence of literal `.IDF` names in the executable does not prove that the application cannot load IDF.
