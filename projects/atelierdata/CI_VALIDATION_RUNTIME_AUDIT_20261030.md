# AtelierData — Windows CI validation (2026-10-30, 21:24 UTC)

- Tested code commit: `2f4ce8f053b875368680a038e7c833b8f3a9aaef`.
- Workflow: [AtelierData Windows EXE — run 41130694382](https://github.com/tzn5-web/leno/actions/runs/41130694382).
- Result: **completed / success** (GitHub-hosted Windows, Python 3.12).
- Python regression suite: **55 tests passed in 23.456 seconds**, including six new synthetic original-runtime dependency tests.
- `ATELIERDATA_SELF_TEST=PASS`.
- PyInstaller one-file `AtelierData.exe`: **19,481,707 bytes**.
- Compiled EXE self-test: PASS.
- Compiled GUI smoke: `GUI_SMOKE_TEST=PASS`.
- `WINDOWS_EXE_TEST=PASS`, SHA256: `7d0d6e6c1ff985fa6ad5cf28079fdecef7fd66a39955bf35aa14a7c70627cde0`.
- Artifact: `AtelierData_Windows_OriginalApp`, ID `13011934279`, expiry 2026-11-13 21:24 UTC.
- The ZIP artifact was downloaded and its embedded EXE SHA256 independently matched the CI log.

The original Autodata executable and private databases were **not** run or published in CI. The static DLL audit was run privately on the supplied ZIPs and documented in `ORIGINAL_RUNTIME_DEPENDENCY_AUDIT_20261030.md`. This EXE is an independent original catalog; the smoke tests do not prove complete GUI coverage, real licensed technical content or compatibility with the proprietary IDF files.
