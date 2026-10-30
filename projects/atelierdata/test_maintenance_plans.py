"""Maintenance engine regression tests, using synthetic values only."""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from maintenance_plans import (
    add_months, add_plan, update_plan, delete_plan, list_plans, get_plan,
    log_service, list_services, delete_service, due_status, list_due
)

class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = Store(self.root/"test.sqlite3")
        self.addCleanup(self.db.close)
        self.vehicle = self.db.add_vehicle("TEST","Vehicul fictiv","TEST","N/A")
        self.other = self.db.add_vehicle("DEMO","Altă mașină","TEST")
        self.plan = add_plan(self.db,self.vehicle,"Operație inventată","Sistem fictiv",
                             interval_km=1000,interval_months=6,source="TEST SINTETIC")

    def test_due_kilometers_or_months_and_missing_baseline(self):
        self.assertEqual(due_status(self.db,self.plan,1500,"2026-04-30")["status"],"fără istoric")
        log_service(self.db,self.plan,"2026-01-31",odometer_km=2000,notes="test")
        status = due_status(self.db,self.plan,2500,"2026-04-30")
        self.assertEqual(status["due_km"],3000)
        self.assertEqual(status["due_date"],"2026-07-31")
        self.assertEqual(status["remaining_km"],500)
        self.assertEqual(status["status"],"în termen")
        self.assertEqual(due_status(self.db,self.plan,3000,"2026-04-30")["status"],"scadent")
        self.assertEqual(due_status(self.db,self.plan,2200,"2026-08-01")["status"],"scadent")
        self.assertEqual(due_status(self.db,self.plan,None,"2026-04-30")["status"],
                         "necalculat (kilometraj lipsă)")
        self.assertEqual(due_status(self.db,self.plan,None,"2026-08-01")["status"],"scadent")

    def test_month_calendar_rollover_and_leap_year(self):
        self.assertEqual(add_months("2024-01-31",1).isoformat(),"2024-02-29")
        self.assertEqual(add_months("2025-01-31",1).isoformat(),"2025-02-28")
        self.assertEqual(add_months("2025-12-30",2).isoformat(),"2026-02-28")

    def test_history_checks_and_delete(self):
        first=log_service(self.db,self.plan,"2026-01-01",100)
        second=log_service(self.db,self.plan,"2026-03-01",1200)
        self.assertEqual(len(list_services(self.db,self.plan)),2)
        with self.assertRaises(ValueError):
            log_service(self.db,self.plan,"2026-05-01",1100)
        with self.assertRaises(ValueError):
            log_service(self.db,self.plan,"2025-11-01",1500)
        with self.assertRaises(ValueError):
            due_status(self.db,self.plan,50,"2026-05-01")
        with self.assertRaises(ValueError):
            due_status(self.db,self.plan,1300,"2025-05-01")
        delete_service(self.db,second)
        self.assertEqual(len(list_services(self.db,self.plan)),1)
        delete_service(self.db,first)
        self.assertEqual(due_status(self.db,self.plan)["status"],"fără istoric")

    def test_source_validation_ownership_and_cascade(self):
        with self.assertRaises(ValueError):
            add_plan(self.db,self.vehicle,"Fictiv","TEST")
        with self.assertRaises(ValueError):
            add_plan(self.db,self.vehicle,"Fictiv","TEST",interval_km=1234)
        with self.assertRaises(ValueError):
            add_plan(self.db,self.vehicle,"Fictiv","TEST",interval_months=-10,source="TEST")
        with self.assertRaises(ValueError):
            add_plan(self.db,999999,"Fictiv","TEST",interval_months=5,source="TEST")
        with self.assertRaises(ValueError):
            add_plan(self.db,self.vehicle,"Operație inventată","Sistem fictiv",
                     interval_km=1000,interval_months=6,source="TEST SINTETIC")
        log_service(self.db,self.plan,"2026-01-01",1000)
        self.assertEqual(len(list_due(self.db,self.vehicle,1200,"2026-05-01")),1)
        self.assertEqual(len(list_due(self.db,self.other,1200,"2026-05-01")),0)
        self.db.delete_vehicle(self.vehicle)
        self.assertIsNone(get_plan(self.db,self.plan))
        self.assertEqual(len(list_services(self.db,self.plan)),0)
        self.assertEqual(self.db.db.execute("PRAGMA foreign_key_check").fetchall(),[])

    def test_edit_plan_and_calendar_only(self):
        update_plan(self.db,self.plan,"Actualizat","Sistem 2",interval_months=1,source="FICTIV")
        self.assertEqual(get_plan(self.db,self.plan)["interval_km"],None)
        log_service(self.db,self.plan,"2026-01-31",None)
        status=due_status(self.db,self.plan,None,"2026-02-28")
        self.assertEqual(status["due_date"],"2026-02-28")
        self.assertEqual(status["status"],"scadent")
        self.assertEqual(len(list_plans(self.db,self.vehicle)),1)
        delete_plan(self.db,self.plan)
        self.assertEqual(len(list_plans(self.db,self.vehicle)),0)

    def test_invalid_dates_missing_km(self):
        with self.assertRaises(ValueError):
            log_service(self.db,self.plan,"2026-02-30",100)
        with self.assertRaises(ValueError):
            log_service(self.db,self.plan,"2026-02-28",None)
        with self.assertRaises(ValueError):
            log_service(self.db,self.plan,"2026-02-28",True)
        with self.assertRaises(ValueError):
            due_status(self.db,self.plan,-1,"2026-02-28")
        self.assertEqual(self.db.db.execute("PRAGMA quick_check").fetchone()[0],"ok")

if __name__=="__main__":
    unittest.main()
