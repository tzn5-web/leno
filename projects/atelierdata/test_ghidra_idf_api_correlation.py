"""Synthetic-only tests for static Ghidra xref correlation."""
import copy
import json
import os
import sys
from unittest import mock
import tempfile
import unittest
from pathlib import Path

from ghidra_idf_api_correlation import correlate, load_private

SHA = "a" * 64


def fixtures():
    idf = {
        "source_sha256": SHA, "executed_target_binary": False,
        "idf_decoder_proven": False,
        "keyword_hits": {
            ".rdata": {
                "MODELS.IDF:ascii": [
                    {"address": "00402000", "references_from": [
                        {"function_entry": "00401000", "source_address": "00401030"}]}],
                "ReadFile:ascii": [
                    {"address": "00403000", "references_from": [
                        {"function_entry": "00409999"}]}]
            }
        }
    }
    api = {
        "schema": "atelierdata-ghidra-file-api-xrefs-v1",
        "source_sha256": SHA, "target_executed": False,
        "idf_decoder_proven": False,
        "api_symbols": {
            "ReadFile": [{"address": "EXTERNAL:00000001", "references": [
                {"function_entry": "00401000", "instruction_mnemonic": "CALL",
                 "reference_type": "UNCONDITIONAL_CALL"},
                {"function_entry": "00401100", "instruction_mnemonic": None,
                 "reference_type": "DATA"}]}]
        }
    }
    return idf, api


class CorrelationTests(unittest.TestCase):

    def test_private_report_read_accepts_exact_byte_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            path.write_bytes(b"{}")
            with mock.patch("ghidra_idf_api_correlation.MAX_REPORT", 2):
                self.assertEqual(load_private(path), {})

    def test_private_report_read_rejects_over_byte_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            path.write_bytes(b"{} ")
            with mock.patch("ghidra_idf_api_correlation.MAX_REPORT", 2):
                with self.assertRaisesRegex(ValueError, "oversized"):
                    load_private(path)

    def test_private_report_rejects_duplicate_top_level_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            path.write_text('{"source_sha256":"a","source_sha256":"b"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate key"):
                load_private(path)

    def test_private_report_rejects_nested_duplicate_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            path.write_text('{"api_symbols":{"ReadFile":{"references":[],"references":[1]}}}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate key"):
                load_private(path)

    def test_distinct_idf_filenames_are_aggregated_without_disclosure(self):
        idf, api = fixtures()
        idf["keyword_hits"][".rdata"]["models.idf:utf16"] = [
            {"references_from": [{"function_entry": "00401000"}]}]
        idf["keyword_hits"][".rdata"]["EMPTY.IDF:ascii"] = [
            {"references_from": []}]
        idf["keyword_hits"][".rdata"]["OTHER.IDF:ascii"] = [
            {"references_from": [{"function_entry": None}]}]
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_distinct_filenames_with_xrefs"], 2)
        self.assertEqual(result["idf_reference_count"], 3)
        self.assertNotIn("MODELS.IDF", json.dumps(result))
        self.assertNotIn("OTHER.IDF", json.dumps(result))

    def test_windows_drive_path_idf_xrefs_are_counted_without_path_disclosure(self):
        idf, api = fixtures()
        idf["keyword_hits"][".rdata"] = {
            r"C:\\PRIVATE\\MODELS.IDF:ascii": [
                {"references_from": [{"function_entry": "00401000"}]}],
            r"c:\\private\\models.idf:utf16": [
                {"references_from": [{"function_entry": "00401000"}]}],
            r"D:\\PRIVATE\\OTHER.IDF:utf16": [
                {"references_from": [{"function_entry": None}]}],
            r"C:\\PRIVATE\\NOT.IDF.bak:ascii": [
                {"references_from": [{"function_entry": "00401000"}]}],
        }
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_distinct_filenames_with_xrefs"], 2)
        self.assertEqual(result["idf_reference_count"], 3)
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("MODELS.IDF", json.dumps(result))

    def test_shared_function_is_only_a_candidate(self):
        idf, api = fixtures()
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_referencing_functions"], 1)
        self.assertEqual(result["api_referencing_functions"], 2)
        self.assertEqual(result["shared_idf_and_api_functions"], 1)
        self.assertEqual(result["shared_idf_and_api_call_or_jump_functions"], 1)
        self.assertFalse(result["idf_decoder_proven"])
        self.assertNotIn("00401000", json.dumps(result))

    def test_direct_read_family_counts_shared_call_only(self):
        idf, api = fixtures()
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 1)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["file_read"], 1)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["file_open"], 0)
        self.assertEqual(result["shared_idf_and_api_family_call_or_jump_functions"]["file_read"], 1)

    def test_dynamic_lookup_only_is_not_direct_file_io(self):
        idf, api = fixtures()
        api["api_symbols"]["GetProcAddress"] = api["api_symbols"].pop("ReadFile")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_functions"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 0)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["dynamic_lookup"], 1)

    def test_closehandle_only_is_not_direct_file_io(self):
        idf, api = fixtures()
        api["api_symbols"]["CloseHandle"] = api["api_symbols"].pop("ReadFile")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_functions"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 0)

    def test_same_function_in_multiple_io_families_is_not_double_counted(self):
        idf, api = fixtures()
        api["api_symbols"]["CreateFileW"] = copy.deepcopy(api["api_symbols"]["ReadFile"])
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["file_open"], 1)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["file_read"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 1)

    def test_data_reference_is_not_a_call_or_jump(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["instruction_mnemonic"] = None
        api["api_symbols"]["ReadFile"][0]["references"][0]["reference_type"] = "DATA"
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 0)

    def test_call_mnemonic_with_data_reference_is_not_a_flow_edge(self):
        idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["reference_type"] = "DATA"
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 0)

    def test_legacy_mnemonic_only_reference_is_unclassified(self):
        idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref.pop("reference_type")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 0)
        self.assertEqual(result["api_references_with_unknown_flow_type"], 1)
        self.assertTrue(result["api_flow_reference_classification_incomplete_or_unknown"])

    def test_unrecognized_type_containing_call_is_not_a_flow_edge(self):
        idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["reference_type"] = "NOT_CALL"
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 0)
        self.assertEqual(result["api_references_with_unknown_flow_type"], 1)

    def test_unrecognized_type_with_explicit_false_is_not_a_call(self):
        idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["reference_type"] = "CALL_HINT"
        ref["reference_is_call_or_jump"] = False
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 0)
        self.assertEqual(result["api_references_with_unknown_flow_type"], 1)

    def test_unknown_reference_type_cannot_claim_flow_with_true_flag(self):
        idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["reference_type"] = "NOT_CALL"
        ref["reference_is_call_or_jump"] = True
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 0)
        self.assertEqual(result["api_references_with_unknown_flow_type"], 1)

    def test_missing_reference_type_cannot_claim_flow_with_true_flag(self):
        idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref.pop("reference_type")
        ref["reference_is_call_or_jump"] = True
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_call_or_jump_functions"], 0)
        self.assertTrue(result["api_flow_reference_classification_incomplete_or_unknown"])

    def test_known_nonflow_reference_with_false_flag_remains_nonflow(self):
        idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["reference_type"] = "DATA"
        ref["reference_is_call_or_jump"] = False
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 0)
        self.assertEqual(result["api_references_with_unknown_flow_type"], 0)

    def test_known_computed_jump_is_a_flow_edge(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["reference_type"] = "COMPUTED_JUMP"
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 1)

    def test_explicit_ghidra_flow_flag_controls_classification(self):
        idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["reference_type"] = "UNCONDITIONAL_CALL"
        ref["reference_is_call_or_jump"] = True
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 1)
        self.assertFalse(result["api_flow_reference_classification_incomplete_or_unknown"])

    def test_invalid_ghidra_flow_flag_is_rejected(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["reference_is_call_or_jump"] = "false"
        with self.assertRaisesRegex(ValueError, "flow flag"):
            correlate(idf, api, SHA)

    def test_contradictory_flow_flag_is_rejected(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["reference_is_call_or_jump"] = False
        with self.assertRaisesRegex(ValueError, "Contradictory Ghidra flow"):
            correlate(idf, api, SHA)

    def test_conflicting_execution_declarations_are_rejected(self):
        idf, api = fixtures()
        api["executed_target_binary"] = True
        with self.assertRaisesRegex(ValueError, "no target execution"):
            correlate(idf, api, SHA)

    def test_non_api_string_does_not_count_as_idf(self):
        idf, api = fixtures()
        idf["keyword_hits"][".rdata"].pop("MODELS.IDF:ascii")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_functions"], 0)

    def test_different_executable_hash_is_rejected(self):
        idf, api = fixtures()
        api["source_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            correlate(idf, api, SHA)

    def test_claim_of_decoding_is_rejected(self):
        idf, api = fixtures()
        idf["idf_decoder_proven"] = True
        with self.assertRaisesRegex(ValueError, "decoding"):
            correlate(idf, api, SHA)

    def test_malformed_xrefs_are_rejected(self):
        idf, api = fixtures()
        idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"] = "bad"
        with self.assertRaisesRegex(ValueError, "IDF xref"):
            correlate(idf, api, SHA)

    def test_truncated_evidence_is_explicit(self):
        idf, api = fixtures()
        api["symbol_scan_truncated"] = True
        api["api_symbols"]["ReadFile"][0]["references_truncated"] = True
        result = correlate(idf, api, SHA)
        self.assertTrue(result["api_scan_or_reference_coverage_truncated"])
        self.assertEqual(result["api_symbols_with_truncated_references"], 1)
        self.assertFalse(result["idf_decoder_proven"])

    def test_invalid_truncation_flag_is_rejected(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references_truncated"] = "false"
        with self.assertRaisesRegex(ValueError, "truncation"):
            correlate(idf, api, SHA)

    def test_legacy_idf_report_coverage_is_unknown(self):
        idf, api = fixtures()
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_coverage_status"], "unknown")
        self.assertTrue(result["idf_coverage_incomplete_or_unknown"])

    def test_new_idf_report_complete_coverage(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=False,
                   keyword_match_cap_reached=False,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=True)
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_coverage_status"], "complete")
        self.assertFalse(result["idf_coverage_incomplete_or_unknown"])

    def test_reached_keyword_cap_marks_incomplete(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=False,
                   keyword_match_cap_reached=True,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=False)
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_coverage_status"], "capped")
        self.assertTrue(result["idf_coverage_incomplete_or_unknown"])

    def test_partial_idf_coverage_metadata_rejected(self):
        idf, api = fixtures()
        idf["block_scan_cap_reached"] = False
        with self.assertRaisesRegex(ValueError, "Incomplete IDF coverage"):
            correlate(idf, api, SHA)

    def test_invalid_idf_coverage_flag_rejected(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=0,
                   keyword_match_cap_reached=False,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=True)
        with self.assertRaisesRegex(ValueError, "Invalid IDF coverage"):
            correlate(idf, api, SHA)

    def test_contradictory_idf_coverage_metadata_rejected(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=False,
                   keyword_match_cap_reached=False,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=False)
        with self.assertRaisesRegex(ValueError, "Contradictory IDF coverage"):
            correlate(idf, api, SHA)

    def test_report_load_rejects_symlink_when_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "private.json"
            report.write_text("{}", encoding="utf-8")
            link = root / "linked.json"
            try:
                link.symlink_to(report)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink unavailable")
            with self.assertRaisesRegex(ValueError, "linked"):
                load_private(link)



    def test_unowned_idf_reference_prevents_complete_claim(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=False, keyword_match_cap_reached=False,
                   keyword_xref_cap_reached=False, short_memory_read=False,
                   keyword_scan_coverage_complete=True)
        idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"].append(
            {"function_entry": None, "source_address": "00401050"})
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_reference_count"], 2)
        self.assertEqual(result["idf_references_without_function_owner"], 1)
        self.assertEqual(result["idf_referencing_functions"], 1)
        self.assertEqual(result["idf_coverage_status"], "complete")
        self.assertTrue(result["idf_coverage_incomplete_or_unknown"])

    def test_unowned_api_reference_prevents_complete_claim(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"].append(
            {"function_entry": None, "reference_type": "UNCONDITIONAL_CALL"})
        result = correlate(idf, api, SHA)
        self.assertEqual(result["api_reference_count"], 3)
        self.assertEqual(result["api_references_without_function_owner"], 1)
        self.assertTrue(result["api_flow_reference_classification_incomplete_or_unknown"])
        self.assertEqual(result["shared_idf_and_api_call_or_jump_functions"], 1)

    def test_all_owned_references_have_no_owner_warning(self):
        idf, api = fixtures()
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_references_without_function_owner"], 0)
        self.assertEqual(result["api_references_without_function_owner"], 0)
        self.assertFalse(result["api_flow_reference_classification_incomplete_or_unknown"])


    def test_unowned_api_invalid_flow_flag_rejected(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"].append(
            {"function_entry": None, "reference_type": "DATA",
             "reference_is_call_or_jump": "false"})
        with self.assertRaisesRegex(ValueError, "flow flag"):
            correlate(idf, api, SHA)

    def test_unowned_api_contradictory_flow_rejected(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"].append(
            {"function_entry": None, "reference_type": "DATA",
             "reference_is_call_or_jump": True})
        with self.assertRaisesRegex(ValueError, "Contradictory Ghidra flow"):
            correlate(idf, api, SHA)

    def test_unowned_api_unknown_flow_is_counted(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"].append(
            {"function_entry": None, "reference_type": "NOT_CALL"})
        result = correlate(idf, api, SHA)
        self.assertEqual(result["api_references_without_function_owner"], 1)
        self.assertEqual(result["api_references_with_unknown_flow_type"], 1)
        self.assertTrue(result["api_flow_reference_classification_incomplete_or_unknown"])

    def test_unowned_api_invalid_reference_type_rejected(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"].append(
            {"function_entry": None, "reference_type": 42})
        with self.assertRaisesRegex(ValueError, "reference type"):
            correlate(idf, api, SHA)


    def test_public_output_hardlink_to_private_report_is_rejected(self):
        from ghidra_idf_api_correlation import main
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            idf, api = fixtures()
            source = root / "idf-private.json"
            other = root / "api-private.json"
            output = root / "public.json"
            source.write_text(json.dumps(idf), encoding="utf-8")
            other.write_text(json.dumps(api), encoding="utf-8")
            try:
                os.link(source, output)
            except OSError:
                self.skipTest("Hard links unavailable")
            original = source.read_bytes()
            argv = ["ghidra_idf_api_correlation.py", "--idf-private-report", str(source),
                    "--api-private-report", str(other), "--expected-sha256", SHA,
                    "--public-output", str(output)]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual(source.read_bytes(), original)

    def test_private_report_rejects_nonregular_opened_descriptor(self):
        import ghidra_idf_api_correlation as module
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            report.write_text("{}", encoding="utf-8")
            original = module.os.fstat
            def altered(fd):
                info = original(fd)
                return mock.Mock(st_mode=0, st_size=info.st_size,
                                 st_mtime_ns=info.st_mtime_ns)
            with mock.patch.object(module.os, "fstat", side_effect=altered):
                with self.assertRaisesRegex(ValueError, "regular file"):
                    load_private(report)

    def test_private_report_detects_mutation_during_read(self):
        import ghidra_idf_api_correlation as module
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            report.write_text("{}", encoding="utf-8")
            original = module.os.fstat
            calls = [0]
            def altered(fd):
                info = original(fd)
                calls[0] += 1
                if calls[0] == 2:
                    return mock.Mock(st_mode=info.st_mode, st_size=info.st_size,
                                     st_mtime_ns=info.st_mtime_ns + 1,
                                     st_ctime_ns=info.st_ctime_ns)
                return info
            with mock.patch.object(module.os, "fstat", side_effect=altered):
                with self.assertRaisesRegex(ValueError, "changed during read"):
                    load_private(report)


    def test_private_report_rejects_short_read_with_unchanged_metadata(self):
        import ghidra_idf_api_correlation as module
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            report.write_text('{"ok":true}', encoding="utf-8")
            original = module.os.fdopen
            class ShortReader:
                def __init__(self, stream):
                    self.stream = stream
                def __enter__(self):
                    self.stream.__enter__()
                    return self
                def __exit__(self, *args):
                    return self.stream.__exit__(*args)
                def fileno(self):
                    return self.stream.fileno()
                def read(self, size):
                    return self.stream.read(2)
            with mock.patch.object(module.os, "fdopen",
                                   side_effect=lambda *a, **kw: ShortReader(original(*a, **kw))):
                with self.assertRaisesRegex(ValueError, "short read"):
                    load_private(report)

    def test_private_report_detects_ctime_change_without_mtime_change(self):
        import ghidra_idf_api_correlation as module
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            report.write_text("{}", encoding="utf-8")
            original = module.os.fstat
            calls = [0]
            def altered(fd):
                info = original(fd)
                calls[0] += 1
                if calls[0] == 2:
                    return mock.Mock(st_mode=info.st_mode, st_size=info.st_size,
                                     st_mtime_ns=info.st_mtime_ns,
                                     st_ctime_ns=info.st_ctime_ns + 1)
                return info
            with mock.patch.object(module.os, "fstat", side_effect=altered):
                with self.assertRaisesRegex(ValueError, "changed during read"):
                    load_private(report)

if __name__ == "__main__":
    unittest.main()
