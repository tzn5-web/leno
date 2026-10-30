"""AtelierData maintenance planning for user-sourced manufacturer/service intervals.

No vehicle-specific interval is bundled or inferred. Due status is advisory and
requires an explicit verified plan and a recorded maintenance baseline.
"""
from __future__ import annotations
import calendar
from datetime import date

MAX_KM = 3_000_000
MAX_MONTHS = 240


def _string(value, field, limit=400, required=False):
    if not isinstance(value, str):
        raise ValueError(field + ": text required")
    value = value.strip()
    if (required and not value) or len(value) > limit or "\0" in value:
        raise ValueError(field + ": missing/invalid")
    return value


def _interval(value, label, upper):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(label + ": invalid integer")
    try:
        n = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(label + ": invalid integer") from exc
    if n <= 0 or n > upper or str(n) != str(value).strip():
        raise ValueError(label + ": out of bounds")
    return n


def _odometer(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError("Kilometraj invalid")
    try:
        n = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("Kilometraj invalid") from exc
    if n < 0 or n > 9_999_999 or str(n) != str(value).strip():
        raise ValueError("Kilometraj invalid")
    return n


def _day(value):
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("Dată invalidă")
    try:
        if len(value) != 10 or value[4] != "-" or value[7] != "-":
            raise ValueError
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise ValueError("Data trebuie să fie YYYY-MM-DD") from exc


def add_months(day, count):
    day = _day(day)
    count = _interval(count, "Luni", MAX_MONTHS)
    month_index = day.year * 12 + day.month - 1 + count
    year, index = divmod(month_index, 12)
    if not 1 <= year <= 9999:
        raise ValueError("Dată rezultată invalidă")
    month = index + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def ensure_schema(store):
    store.db.executescript("""
      CREATE TABLE IF NOT EXISTS maintenance_plans(
        id INTEGER PRIMARY KEY,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        system TEXT NOT NULL,
        interval_km INTEGER CHECK(interval_km IS NULL OR (interval_km>0 AND interval_km<=3000000)),
        interval_months INTEGER CHECK(interval_months IS NULL OR (interval_months>0 AND interval_months<=240)),
        conditions TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL,
        UNIQUE(vehicle_id,title,source),
        CHECK(interval_km IS NOT NULL OR interval_months IS NOT NULL)
      );
      CREATE INDEX IF NOT EXISTS idx_maintenance_plans_vehicle
        ON maintenance_plans(vehicle_id,system,title);
      CREATE TABLE IF NOT EXISTS maintenance_events(
        id INTEGER PRIMARY KEY,
        plan_id INTEGER NOT NULL REFERENCES maintenance_plans(id) ON DELETE CASCADE,
        performed_on TEXT NOT NULL,
        odometer_km INTEGER CHECK(odometer_km IS NULL OR
                         (odometer_km>=0 AND odometer_km<=9999999)),
        notes TEXT NOT NULL DEFAULT ''
      );
      CREATE INDEX IF NOT EXISTS idx_maintenance_events
        ON maintenance_events(plan_id,performed_on DESC,id DESC);
    """)
    store.db.commit()


def _plan_fields(title, system, interval_km, interval_months, conditions, source):
    km = _interval(interval_km, "Kilometri", MAX_KM)
    months = _interval(interval_months, "Luni", MAX_MONTHS)
    if km is None and months is None:
        raise ValueError("Precizează interval în kilometri și/sau luni")
    return (
        _string(title, "Operație", 180, True),
        _string(system, "Sistem", 120, True),
        km, months,
        _string(conditions, "Condiții", 3000),
        _string(source, "Sursă", 500, True)
    )


def add_plan(store, vehicle_id, title, system, interval_km=None, interval_months=None,
             conditions="", source=""):
    fields = _plan_fields(title, system, interval_km, interval_months, conditions, source)
    if not store.db.execute("SELECT 1 FROM vehicles WHERE id=?", (vehicle_id,)).fetchone():
        raise ValueError("Vehicul inexistent")
    try:
        cursor = store.db.execute(
            "INSERT INTO maintenance_plans(vehicle_id,title,system,interval_km,"
            "interval_months,conditions,source) VALUES(?,?,?,?,?,?,?)", (vehicle_id,*fields))
        store.db.commit()
        return cursor.lastrowid
    except Exception as exc:
        if "UNIQUE constraint" in str(exc):
            raise ValueError("Plan duplicat pentru acest vehicul și sursă") from exc
        raise


def update_plan(store, plan_id, title, system, interval_km=None, interval_months=None,
                conditions="", source=""):
    fields = _plan_fields(title, system, interval_km, interval_months, conditions, source)
    try:
        cursor = store.db.execute(
            "UPDATE maintenance_plans SET title=?,system=?,interval_km=?,interval_months=?,"
            "conditions=?,source=? WHERE id=?", (*fields,plan_id))
        if cursor.rowcount == 0:
            raise ValueError("Plan inexistent")
        store.db.commit()
    except Exception as exc:
        if "UNIQUE constraint" in str(exc):
            raise ValueError("Plan duplicat pentru acest vehicul și sursă") from exc
        raise


def list_plans(store, vehicle_id=None):
    query = ("SELECT p.*,v.make,v.model,v.engine FROM maintenance_plans p "
             "JOIN vehicles v ON v.id=p.vehicle_id")
    args=[]
    if vehicle_id is not None:
        query += " WHERE vehicle_id=?"
        args.append(vehicle_id)
    return store.db.execute(query+" ORDER BY v.make,v.model,p.system,p.title",args).fetchall()


def get_plan(store, plan_id):
    return store.db.execute("SELECT * FROM maintenance_plans WHERE id=?", (plan_id,)).fetchone()


def delete_plan(store, plan_id):
    store.db.execute("DELETE FROM maintenance_plans WHERE id=?", (plan_id,))
    store.db.commit()


def log_service(store, plan_id, performed_on, odometer_km=None, notes=""):
    plan = get_plan(store, plan_id)
    if plan is None:
        raise ValueError("Plan inexistent")
    completed = _day(performed_on)
    km = _odometer(odometer_km)
    if plan["interval_km"] is not None and km is None:
        raise ValueError("Kilometrajul este obligatoriu pentru un interval în kilometri")
    notes = _string(notes, "Note", 3000)
    past = store.db.execute(
        "SELECT performed_on,odometer_km FROM maintenance_events WHERE plan_id=? "
        "ORDER BY performed_on,id", (plan_id,)).fetchall()
    for item in past:
        recorded_date = _day(item["performed_on"])
        if item["odometer_km"] is None or km is None:
            continue
        if completed > recorded_date and km < item["odometer_km"]:
            raise ValueError("Kilometraj inferior unei intervenții anterioare")
        if completed < recorded_date and km > item["odometer_km"]:
            raise ValueError("Kilometraj superior unei intervenții ulterioare")
    cursor = store.db.execute(
        "INSERT INTO maintenance_events(plan_id,performed_on,odometer_km,notes)"
        " VALUES(?,?,?,?)", (plan_id, completed.isoformat(), km, notes))
    store.db.commit()
    return cursor.lastrowid


def list_services(store, plan_id):
    return store.db.execute(
        "SELECT * FROM maintenance_events WHERE plan_id=? ORDER BY performed_on DESC,id DESC",
        (plan_id,)).fetchall()


def delete_service(store, service_id):
    store.db.execute("DELETE FROM maintenance_events WHERE id=?", (service_id,))
    store.db.commit()


def due_status(store, plan_id, current_km=None, as_of=None):
    """No baseline -> unknown; any reached threshold -> due. Never invent intervals."""
    plan = get_plan(store, plan_id)
    if plan is None:
        raise ValueError("Plan inexistent")
    day = _day(as_of) if as_of is not None else date.today()
    km = _odometer(current_km)
    past = list_services(store, plan_id)
    if not past:
        return {"status":"fără istoric","due_km":None,"due_date":None,
                "remaining_km":None,"remaining_days":None}
    latest = past[0]
    last_date = _day(latest["performed_on"])
    if day < last_date:
        raise ValueError("Data evaluării precede ultima intervenție")
    previous = latest["odometer_km"]
    if km is not None and previous is not None and km < previous:
        raise ValueError("Kilometraj curent sub ultima intervenție")
    due_km = (previous + plan["interval_km"]) if previous is not None and plan["interval_km"] else None
    due_date = add_months(last_date, plan["interval_months"]) if plan["interval_months"] else None
    remain_km = due_km-km if due_km is not None and km is not None else None
    remain_days = (due_date-day).days if due_date is not None else None
    reached = ((remain_km is not None and remain_km<=0) or
               (remain_days is not None and remain_days<=0))
    missing = due_km is not None and km is None
    status = "scadent" if reached else "necalculat (kilometraj lipsă)" if missing else "în termen"
    return {"status":status,"due_km":due_km,
            "due_date":due_date.isoformat() if due_date else None,
            "remaining_km":remain_km,"remaining_days":remain_days,
            "last_date":last_date.isoformat(),"last_km":previous}


def list_due(store, vehicle_id, current_km=None, as_of=None):
    return [{"plan":dict(plan),"status":due_status(store,plan["id"],current_km,as_of)}
            for plan in list_plans(store,vehicle_id)]
