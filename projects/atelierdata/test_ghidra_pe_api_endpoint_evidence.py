"""Synthetic-only tests for independent PE-IAT endpoint byte correlation."""
import copy
import unittest

from ghidra_pe_api_endpoint_evidence import pe_backed_api_endpoints, _trusted_windows_api_import
from pe_file_io_xrefs import parse_pe32
from test_ghidra_api_callsite_replay import fixtures


class PeApiEndpointEvidenceTests(unittest.TestCase):
    def _run(self, change=None, data_change=None):
        data, sha, idf, api = fixtures()
        if change:
            change(api)
        if data_change:
            data = data_change(data)
        return pe_backed_api_endpoints(data, parse_pe32(data), api)

    def test_valid_synthetic_ff15_readfile_endpoint(self):
        endpoints, count, conflicts = self._run()
        self.assertEqual(count, 1)
        self.assertEqual(conflicts, 0)
        self.assertEqual(endpoints["file_read"], {0x401000})
        self.assertFalse(endpoints["dynamic_lookup"])

    def test_wrong_opcode_not_a_call(self):
        def tamper(data):
            data = bytearray(data)
            data[0x220] = 0x90
            return bytes(data)
        endpoints, count, conflicts = self._run(data_change=tamper)
        self.assertEqual(count, 0)
        self.assertFalse(endpoints["file_read"])

    def test_wrong_api_name_not_a_static_import_match(self):
        def tamper(api):
            api["api_symbols"]["CreateFileA"] = api["api_symbols"].pop("ReadFile")
        endpoints, count, conflicts = self._run(change=tamper)
        self.assertEqual(count, 0)
        self.assertFalse(endpoints["file_open"])

    def test_missing_or_wrong_instruction_boundary_is_excluded(self):
        for key, value in (("instruction_length", 5),
                           ("instruction_start_address", "00401021"),
                           ("instruction_mnemonic", "JMP"),
                           ("reference_is_call_or_jump", False)):
            with self.subTest(key=key):
                def tamper(api):
                    api["api_symbols"]["ReadFile"][0]["references"][0][key] = value
                self.assertEqual(self._run(change=tamper)[1], 0)

    def test_nonexecutable_function_entry_excluded(self):
        def tamper(api):
            api["api_symbols"]["ReadFile"][0]["references"][0]["function_entry"] = "00402000"
        self.assertEqual(self._run(change=tamper)[1], 0)

    def test_conflicting_same_site_attribution_rejected(self):
        def tamper(api):
            refs = api["api_symbols"]["ReadFile"][0]["references"]
            other = copy.deepcopy(refs[0])
            other["function_entry"] = "00401010"
            refs.append(other)
        endpoints, count, conflicts = self._run(change=tamper)
        self.assertEqual(count, 0)
        self.assertEqual(conflicts, 1)
        self.assertFalse(endpoints["file_read"])



    def test_same_name_export_from_untrusted_dll_is_not_file_api_evidence(self):
        def spoof(data):
            data = bytearray(data)
            data[0x480:0x48d] = b"FAKECORE.dll" + bytes((0,))
            return bytes(data)
        endpoints, count, conflicts = self._run(data_change=spoof)
        self.assertEqual(count, 0)
        self.assertEqual(conflicts, 0)
        self.assertFalse(endpoints["file_read"])

    def test_caller_entry_after_callsite_is_not_ownership_evidence(self):
        def tamper(api):
            api["api_symbols"]["ReadFile"][0]["references"][0]["function_entry"] = "00401030"
        endpoints, count, conflicts = self._run(change=tamper)
        self.assertEqual(count, 0)
        self.assertFalse(endpoints["file_read"])

    def test_windows_api_set_contract_is_family_specific(self):
        self.assertTrue(_trusted_windows_api_import("kernel32.DLL", ("file_read",)))
        self.assertTrue(_trusted_windows_api_import(
            "api-ms-win-core-file-l1-1-0.dll", ("file_read",)))
        self.assertTrue(_trusted_windows_api_import(
            "api-ms-win-core-libraryloader-l1-1-0.dll", ("dynamic_lookup",)))
        self.assertFalse(_trusted_windows_api_import(
            "api-ms-win-core-libraryloader-l1-1-0.dll", ("file_read",)))
        self.assertFalse(_trusted_windows_api_import(
            "api-ms-win-core-file-l1-1-0.dll", ("dynamic_lookup",)))
        self.assertTrue(_trusted_windows_api_import(
            "api-ms-win-core-memory-l1-1-0.dll", ("file_mapping",)))
        self.assertFalse(_trusted_windows_api_import(
            "api-ms-win-core-memory-l1-1-0.dll", ("file_read",)))
        self.assertFalse(_trusted_windows_api_import("custom.dll", ("file_read",)))


    def test_api_set_prefix_spoof_and_cross_family_rejected(self):
        for dll in (
                "api-ms-win-core-file-evil.dll",
                "api-ms-win-core-file-l1-1-0.dll.evil",
                "api-ms-win-core-file-l1-1-0x.dll",
                "C:\\\\Windows\\\\api-ms-win-core-file-l1-1-0.dll",
                "api-ms-win-core-file-l1-1-0.dll\\x00suffix",
                "api-ms-win-core-file-l1-1-0.dll/extra"):
            with self.subTest(dll=dll):
                self.assertFalse(_trusted_windows_api_import(dll, ("file_read",)))
        self.assertTrue(_trusted_windows_api_import(
            "API-MS-WIN-CORE-FILE-L1-2-0.DLL", ("file_read",)))
        self.assertFalse(_trusted_windows_api_import(
            "API-MS-WIN-CORE-MEMORY-L1-1-0.DLL", ("file_read",)))
        self.assertFalse(_trusted_windows_api_import(
            "API-MS-WIN-CORE-FILE-L1-1-0.DLL", ("file_mapping",)))

    def test_invalid_duplicate_reference_taints_same_physical_site(self):
        def tamper(api):
            refs = api["api_symbols"]["ReadFile"][0]["references"]
            duplicate = copy.deepcopy(refs[0])
            duplicate["instruction_length"] = 5
            refs.append(duplicate)
        endpoints, count, conflicts = self._run(change=tamper)
        self.assertEqual(count, 0)
        self.assertEqual(conflicts, 1)
        self.assertFalse(endpoints["file_read"])

    def test_inconsistent_duplicate_start_taints_same_physical_site(self):
        def tamper(api):
            refs = api["api_symbols"]["ReadFile"][0]["references"]
            duplicate = copy.deepcopy(refs[0])
            duplicate["instruction_start_address"] = "RAM:00401021"
            refs.append(duplicate)
        endpoints, count, conflicts = self._run(change=tamper)
        self.assertEqual(count, 0)
        self.assertEqual(conflicts, 1)
        self.assertFalse(endpoints["file_read"])

if __name__ == "__main__":
    unittest.main()
