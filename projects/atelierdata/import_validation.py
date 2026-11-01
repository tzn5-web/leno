"""Bounded, strict import of user-authored AtelierData CSV/JSON records.

No proprietary Autodata data is included or decoded. Parsing happens before
any SQLite write; malformed rows cannot create partial vehicle/article data.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

MAX_IMPORT_BYTES = 32 * 1024 * 1024
MAX_IMPORT_ROWS = 50_000
FIELD_LIMITS = {
    "make": 200, "model": 200, "engine": 200, "years": 100,
    "fuel": 100, "variant": 200, "category": 200, "title": 500,
    "content": 1_000_000, "body": 1_000_000, "source": 2_000,
}
REQUIRED = ("make", "model", "category", "title")
VEHICLE_FIELDS = ("make", "model", "engine", "years", "fuel", "variant")


def read_import_rows(path):
    """Read at most MAX_IMPORT_ROWS from a bounded regular CSV/JSON file."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Importul trebuie să fie un fișier obișnuit, nu un link")
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("Fișierul de import depășește 32 MiB")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames
            if (not headers or len(headers) != len(set(headers)) or
                    any(not name or name not in FIELD_LIMITS for name in headers) or
                    any(name not in headers for name in REQUIRED)):
                raise ValueError("Antet CSV duplicat, necunoscut sau incomplet")
            rows = []
            for index, row in enumerate(reader, 1):
                if index > MAX_IMPORT_ROWS:
                    raise ValueError("Importul depășește limita de 50000 înregistrări")
                if None in row:
                    raise ValueError("CSV conține mai multe valori decât coloane")
                rows.append(row)
            return rows
    if suffix == ".json":
        with path.open(encoding="utf-8-sig") as stream:
            payload = json.load(stream)
        if isinstance(payload, dict):
            if (payload.get("schema") not in (None, "atelierdata-records-v1") or
                    "records" not in payload):
                raise ValueError("Schemă JSON necunoscută sau lipsă records")
            rows = payload["records"]
        else:
            rows = payload
        if not isinstance(rows, list):
            raise ValueError("JSON trebuie să conțină o listă records")
        if len(rows) > MAX_IMPORT_ROWS:
            raise ValueError("Importul depășește limita de 50000 înregistrări")
        return rows
    raise ValueError("Accept doar CSV/JSON")


def validate_import_row(row):
    """Return normalized fields; never stringify None, objects or booleans."""
    if not isinstance(row, dict) or any(key not in FIELD_LIMITS for key in row):
        raise ValueError("Înregistrare sau câmp necunoscut")
    normalized = {}
    for key, limit in FIELD_LIMITS.items():
        value = row.get(key, "")
        if value is None and key not in REQUIRED:
            value = ""
        if not isinstance(value, str) or len(value) > limit or "\x00" in value:
            raise ValueError("Tip, lungime sau caracter invalid în " + key)
        normalized[key] = value
    if any(not normalized[key].strip() for key in REQUIRED):
        raise ValueError("Câmpurile make, model, category, title sunt obligatorii")
    fields = [normalized[key].strip() for key in VEHICLE_FIELDS]
    content = normalized["content"] if "content" in row else normalized["body"]
    return (fields, normalized["category"].strip(), normalized["title"].strip(),
            content, normalized["source"])
