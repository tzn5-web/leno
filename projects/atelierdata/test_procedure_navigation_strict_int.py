"""Strict GUI search pagination index regression; no database access needed."""
import unittest

from procedure_search_hits import next_hit_index


class IntSubclass(int):
    pass


class NavigationIndexTypeTests(unittest.TestCase):
    def test_rejects_int_subclasses_before_navigation(self):
        for count, index in ((IntSubclass(2), None), (2, IntSubclass(0)),
                             (IntSubclass(0), None)):
            with self.subTest(count=count, index=index):
                with self.assertRaisesRegex(ValueError, "Invalid"):
                    next_hit_index(count, index)

    def test_builtin_int_navigation_still_wraps(self):
        self.assertEqual(next_hit_index(2, 1), 0)
        self.assertEqual(next_hit_index(2, 0, -1), 1)
        self.assertEqual(next_hit_index(2, None, -1), 1)
        self.assertIsNone(next_hit_index(0))


if __name__ == "__main__":
    unittest.main()
