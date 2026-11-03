"""Deterministic two-connection SQLite and Tkinter regression tests.

All procedure steps and documents are synthetic; no OEM data is included.
"""
from __future__ import annotations

import sqlite3
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tkinter import ttk

import repair_procedures as procedures
from atelierdata import Store
from repair_procedures import (
    add_step, create_procedure, delete_step, list_steps, move_step, update_step,
)
from repair_procedures_gui import open_procedures_window


class ProcedureStepWriteAtomicityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "atomic.sqlite3"
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "CAR", "DEMO")
        self.other = self.store.add_vehicle("OTHER", "CAR", "DEMO")
        self.pid = create_procedure(
            self.store, self.vehicle, "Synthetic system", "Synthetic task",
            source="AUTHOR-OWNED TEST")
        self.doc = self.store.add_article(
            self.vehicle, "Note atelier", "Synthetic note", "No real repair",
            "AUTHORIZED TEST")
        self.foreign = self.store.add_article(
            self.other, "Note atelier", "Other note", "Private test",
            "FOREIGN TEST")
        self.first = add_step(self.store, self.pid, "Synthetic step one")
        self.second = add_step(self.store, self.pid, "Synthetic step two")
        # A second independent SQLite connection is used to simulate a
        # concurrent writer without relying on threads or timing sleeps.
        self.peer = Store(self.path)
        self.addCleanup(self.peer.close)
        self.peer.db.execute("PRAGMA busy_timeout=0")

    def assert_peer_write_blocked(self, sql, params):
        with self.assertRaises(sqlite3.OperationalError) as error:
            self.peer.db.execute(sql, params)
        self.assertIn("locked", str(error.exception).lower())
        self.peer.db.rollback()

    def test_add_step_locks_before_reference_vehicle_validation(self):
        original = procedures._article_reference

        def checked(store, procedure_id, article_id):
            self.assertTrue(store.db.in_transaction)
            self.assert_peer_write_blocked(
                "UPDATE articles SET vehicle_id=? WHERE id=?",
                (self.other, self.doc))
            return original(store, procedure_id, article_id)

        with patch.object(procedures, "_article_reference", side_effect=checked):
            added = add_step(self.store, self.pid, "Synthetic linked step",
                             article_id=self.doc)
        self.assertEqual(list_steps(self.store, self.pid)[-1]["id"], added)
        self.assertEqual(list_steps(self.store, self.pid)[-1]["article_id"], self.doc)
        self.assertEqual(self.peer.db.execute(
            "SELECT vehicle_id FROM articles WHERE id=?", (self.doc,)
        ).fetchone()[0], self.vehicle)

    def test_add_step_locks_before_reading_current_order(self):
        original = procedures.list_steps

        def checked(store, procedure_id):
            self.assertTrue(store.db.in_transaction)
            self.assert_peer_write_blocked(
                "INSERT INTO procedure_steps(procedure_id,step_number,instruction)"
                " VALUES(?,?,?)", (self.pid, 3, "Concurrent synthetic step"))
            return original(store, procedure_id)

        with patch.object(procedures, "list_steps", side_effect=checked):
            added = add_step(self.store, self.pid, "Synthetic inserted step", position=2)
        self.assertEqual([r["id"] for r in list_steps(self.store, self.pid)],
                         [self.first, added, self.second])
        self.assertEqual([r["step_number"] for r in list_steps(self.store, self.pid)],
                         [1, 2, 3])

    def test_update_step_locks_before_reference_validation(self):
        original = procedures._article_reference

        def checked(store, procedure_id, article_id):
            self.assertTrue(store.db.in_transaction)
            self.assert_peer_write_blocked(
                "UPDATE procedures SET vehicle_id=? WHERE id=?",
                (self.other, self.pid))
            return original(store, procedure_id, article_id)

        with patch.object(procedures, "_article_reference", side_effect=checked):
            update_step(self.store, self.first, "Updated synthetic step",
                        article_id=self.doc)
        self.assertEqual(list_steps(self.store, self.pid)[0]["article_id"], self.doc)
        self.assertEqual(self.peer.db.execute(
            "SELECT vehicle_id FROM procedures WHERE id=?", (self.pid,)
        ).fetchone()[0], self.vehicle)

    def test_move_step_locks_before_reading_order(self):
        original = procedures.list_steps

        def checked(store, procedure_id):
            self.assertTrue(store.db.in_transaction)
            self.assert_peer_write_blocked(
                "UPDATE procedure_steps SET instruction=? WHERE id=?",
                ("Concurrent change", self.second))
            return original(store, procedure_id)

        with patch.object(procedures, "list_steps", side_effect=checked):
            self.assertTrue(move_step(self.store, self.second, -1))
        self.assertEqual([r["id"] for r in list_steps(self.store, self.pid)],
                         [self.second, self.first])

    def test_failed_link_update_rolls_back_and_releases_writer_lock(self):
        before = [(r["id"], r["instruction"], r["article_id"])
                  for r in list_steps(self.store, self.pid)]
        with self.assertRaises(ValueError):
            update_step(self.store, self.first, "Uncommitted", article_id=self.foreign)
        with self.assertRaises(ValueError):
            add_step(self.store, self.pid, "Uncommitted", article_id=self.foreign)
        self.assertFalse(self.store.db.in_transaction)
        self.peer.db.execute(
            "UPDATE procedure_steps SET instruction=? WHERE id=?",
            ("Peer committed", self.second))
        self.peer.db.commit()
        after = list_steps(self.store, self.pid)
        self.assertEqual(after[0]["instruction"], before[0][1])
        self.assertEqual(after[0]["article_id"], before[0][2])
        self.assertEqual(after[1]["instruction"], "Peer committed")
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_delete_and_boundary_move_release_transaction(self):
        self.assertFalse(move_step(self.store, self.first, -1))
        self.assertFalse(self.store.db.in_transaction)
        delete_step(self.store, 987654321)
        self.assertFalse(self.store.db.in_transaction)
        delete_step(self.store, self.first)
        self.assertEqual([r["step_number"] for r in list_steps(self.store, self.pid)],
                         [1])
        self.assertFalse(self.store.db.execute("PRAGMA foreign_key_check").fetchall())

    def test_tk_add_step_button_uses_transactional_writer_and_refreshes(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()

        # Resolve the fixture ID from the test, not from the dialog itself.
        document_id = self.doc

        class Editor:
            def __init__(self, *args, **kwargs):
                self.value = {
                    "instruction": "Synthetic GUI-added instruction",
                    "safety_note": "Synthetic GUI warning",
                    "article_id": str(document_id),
                }

        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = open_procedures_window(
            app, Editor, selected_procedure_id=self.pid)
        try:
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            buttons = [widget for widget in descendants(window)
                       if isinstance(widget, ttk.Button)
                       and widget.cget("text") == "+ Pas"]
            self.assertEqual(len(buttons), 1)
            with patch("tkinter.messagebox.showerror") as errors:
                buttons[0].invoke()
                errors.assert_not_called()
            rows = list_steps(self.store, self.pid)
            self.assertEqual(len(rows), 3)
            added = rows[-1]["id"]
            self.assertTrue(window.steps_tree.exists(str(added)))
            window.steps_tree.selection_set(str(added))
            detail = window.render_selected_step()
            self.assertIn("Synthetic GUI warning", detail)
            self.assertIn("AUTHORIZED TEST", detail)
            self.assertFalse(self.store.db.in_transaction)
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()
