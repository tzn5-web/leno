"""Synthetic SQLite and Windows Tk integration tests for repair-step navigation."""
import sqlite3
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from procedure_step_navigation import adjacent_step_id


class StepNavigationTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
          CREATE TABLE procedures(id INTEGER PRIMARY KEY,vehicle_id INTEGER);
          CREATE TABLE procedure_steps(id INTEGER PRIMARY KEY,procedure_id INTEGER,step_number INTEGER);
          INSERT INTO procedures VALUES(11,1),(22,2),(33,1);
          INSERT INTO procedure_steps VALUES(101,11,1),(102,11,2),(103,11,3),(201,22,1);
        """)
        self.store=SimpleNamespace(db=self.db)

    def nav(self,current=None,direction=1,vehicle=1,procedure=11):
        return adjacent_step_id(self.store,vehicle,procedure,current,direction)

    def test_boundaries_and_read_only(self):
        before=self.db.total_changes
        self.assertEqual([self.nav(),self.nav(direction=-1),self.nav(101),
                          self.nav(103,-1)],[101,103,102,102])
        self.assertIsNone(self.nav(103))
        self.assertIsNone(self.nav(101,-1))
        self.assertIsNone(self.nav(procedure=33))
        self.assertEqual(self.db.total_changes,before)

    def test_live_reordering_and_deleted_selection(self):
        self.db.execute("UPDATE procedure_steps SET step_number=4 WHERE id=101")
        self.db.execute("DELETE FROM procedure_steps WHERE id=102")
        before=self.db.total_changes
        self.assertEqual(self.nav(),103)
        self.assertEqual(self.nav(103),101)
        with self.assertRaisesRegex(ValueError,"no longer belongs"):
            self.nav(102)
        self.assertEqual(self.db.total_changes,before)

    def test_scope_and_strict_ids(self):
        before=self.db.total_changes
        for vehicle,procedure,step in ((2,11,None),(1,22,None),(1,11,201),
                                       (1,11,999),(1,999,None)):
            with self.subTest(vehicle=vehicle,procedure=procedure,step=step):
                with self.assertRaises(ValueError):
                    self.nav(step,vehicle=vehicle,procedure=procedure)
        for bad in (True,False,1.0,"1",0,-1):
            for field in ("vehicle_id","procedure_id","current_step_id"):
                kwargs=dict(vehicle_id=1,procedure_id=11,current_step_id=101)
                kwargs[field]=bad
                with self.subTest(field=field,bad=repr(bad)):
                    with self.assertRaises(ValueError):
                        adjacent_step_id(self.store,**kwargs)
        for bad in (True,1.0,"1",0,2,None):
            with self.assertRaises(ValueError):
                self.nav(direction=bad)
        self.assertEqual(self.db.total_changes,before)

    def test_one_scoped_sql_snapshot_for_each_navigation(self):
        """The vehicle ownership and ordered steps must not use two SELECTs."""
        statements=[]
        self.db.set_trace_callback(statements.append)
        try:
            before=self.db.total_changes
            self.assertEqual(self.nav(101),102)
            self.assertIsNone(self.nav(procedure=33))
            self.assertEqual(self.db.total_changes,before)
        finally:
            self.db.set_trace_callback(None)
        selects=[sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
        self.assertEqual(len(selects),2,selects)
        self.assertTrue(all("JOIN procedure_steps" in sql for sql in selects))

    def test_windows_gui_navigation_and_stale_row(self):
        try:
            root=tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: "+str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        from atelierdata import Store
        from repair_procedures import add_step,create_procedure,delete_step,move_step
        from repair_procedures_gui import open_procedures_window
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/"fixture.sqlite3")
            try:
                vehicle=store.add_vehicle("SYNTHETIC","CAR")
                pid=create_procedure(store,vehicle,"TEST","Navigation",
                                     source="User-authored fixture")
                first=add_step(store,pid,"Synthetic first",safety_note="Fixture warning")
                second=add_step(store,pid,"Synthetic second")
                third=add_step(store,pid,"Synthetic third")
                app=SimpleNamespace(root=root,tk=tk,db=store,vid=vehicle)
                window=open_procedures_window(app,object,selected_procedure_id=pid)
                try:
                    window.update_idletasks()
                    before=store.db.total_changes
                    self.assertEqual(window.navigate_step(1),first)
                    self.assertEqual(window.navigate_step(1),second)
                    self.assertEqual(window.navigate_step(-1),first)
                    self.assertIsNone(window.navigate_step(-1))
                    self.assertEqual(store.db.total_changes,before)
                    move_step(store,third,-1)
                    window.refresh_steps(first)
                    self.assertEqual(window.navigate_step(1),third)
                    delete_step(store,third)
                    window.steps_tree.selection_set(str(third))
                    with patch("tkinter.messagebox.showerror") as error:
                        self.assertIsNone(window.navigate_step(1))
                        self.assertTrue(error.called)
                    # A reassigned procedure must clear previously cached
                    # steps and metadata, not merely reject the button click.
                    other=store.add_vehicle("SYNTHETIC","OTHER")
                    store.db.execute(
                        "UPDATE procedures SET vehicle_id=? WHERE id=?",
                        (other,pid))
                    store.db.commit()
                    window.steps_tree.selection_set(str(first))
                    before=store.db.total_changes
                    with patch("tkinter.messagebox.showerror") as error:
                        self.assertIsNone(window.navigate_step(1))
                    error.assert_called_once()
                    self.assertEqual(window.steps_tree.get_children(),())
                    self.assertFalse(window.procedures_tree.exists(str(pid)))
                    self.assertNotIn("Synthetic first",
                                     window.procedure_detail_text.get("1.0","end"))
                    self.assertEqual(store.db.total_changes,before)
                finally:
                    window.destroy()
            finally:
                store.close()


if __name__=="__main__":
    unittest.main()
