"""Regression: vehicle-scoped search must reject coerced/subclassed IDs.

Synthetic fixtures only; no proprietary repair data.
"""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure
from procedure_search_hits import list_procedure_hits


class SearchVehicleIdContractTests(unittest.TestCase):
    def test_only_exact_positive_integer_vehicle_ids_are_accepted(self):
        class PretendVehicleId(int):
            pass

        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "strict-ids.sqlite3")
            try:
                vehicle = store.add_vehicle("SYNTHETIC", "MODEL")
                create_procedure(store, vehicle, "TEST", "SYNTH-SEARCH",
                                 source="SYNTHETIC")
                before = store.db.total_changes
                for invalid in (True, False, 0, -1, 1.0, str(vehicle),
                                PretendVehicleId(vehicle)):
                    with self.subTest(invalid=repr(invalid)):
                        with self.assertRaises(ValueError):
                            list_procedure_hits(store, invalid, "SYNTH-SEARCH")
                hits = list_procedure_hits(store, vehicle, "SYNTH-SEARCH")
                self.assertTrue(hits)
                self.assertEqual(store.db.total_changes, before)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
