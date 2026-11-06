"""GUI search-result selection regression tests (synthetic records only).

The filtered Tkinter row index is not the underlying search hit index.
Preserve the mapping when switching fields or wrapping navigation.
"""
import unittest

from procedure_search_hits import filter_hit_indices, next_hit_index


class SearchResultSelectionTests(unittest.TestCase):
    def setUp(self):
        self.hits = [
            {"field": "Instrucțiune pas", "step_id": 11},
            {"field": "Avertisment pas", "step_id": 11},
            {"field": "Instrucțiune pas", "step_id": 12},
            {"field": "Proveniență document", "step_id": 12},
            {"field": "Avertisment pas", "step_id": 13},
        ]

    def test_filtered_rows_map_back_to_original_step_ids(self):
        indices = filter_hit_indices(self.hits, "Avertisment pas")
        self.assertEqual(indices, [1, 4])
        self.assertEqual([self.hits[i]["step_id"] for i in indices], [11, 13])
        self.assertEqual(len(self.hits), 5)

    def test_wrap_navigation_uses_filtered_row_count(self):
        indices = filter_hit_indices(self.hits, "Avertisment pas")
        current = next_hit_index(len(indices), None, 1)
        self.assertEqual(self.hits[indices[current]]["step_id"], 11)
        current = next_hit_index(len(indices), current, -1)
        self.assertEqual(self.hits[indices[current]]["step_id"], 13)
        self.assertEqual(next_hit_index(len(indices), current, 1), 0)

    def test_empty_filter_does_not_select_unrelated_result(self):
        indices = filter_hit_indices(self.hits, "Titlu document")
        self.assertEqual(indices, [])
        self.assertIsNone(next_hit_index(len(indices), None, 1))

    def test_switching_filter_does_not_mutate_original_hits(self):
        original = [row.copy() for row in self.hits]
        self.assertEqual(filter_hit_indices(self.hits), [0, 1, 2, 3, 4])
        self.assertEqual(filter_hit_indices(self.hits, "Instrucțiune pas"), [0, 2])
        self.assertEqual(filter_hit_indices(self.hits, "Proveniență document"), [3])
        self.assertEqual(self.hits, original)


if __name__ == "__main__":
    unittest.main()
