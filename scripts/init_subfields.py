#!/usr/bin/env python3
"""Promote the subfields of composite data fields into their own table, so every
atomic datum can carry its OWN eCH standard element.

A composite field like "Personalien" carries one assignment for the whole bundle
(eCH-0044 personIdentification), which says nothing about Name / Vorname /
Geburtsdatum inside it — not exact enough for a compliance databank.
data_field.subfields (a JSON array) stays as the raw extraction record;
data_subfield is the queryable, validatable source of truth for the parts.

Idempotent: re-running re-syncs names/ordinals without losing eCH assignments
(matched by data_field_id + normalised name). Staging -> validate -> swap.

    python3 scripts/init_subfields.py
"""
import json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

DDL = """
CREATE TABLE IF NOT EXISTS data_subfield (
    id                INTEGER PRIMARY KEY,
    data_field_id     INTEGER NOT NULL REFERENCES data_field(id) ON DELETE CASCADE,
    ord               INTEGER NOT NULL,
    name              TEXT NOT NULL,
    ech_element_id    INTEGER REFERENCES ech_element(id),
    ech_standard_code TEXT REFERENCES ech_standard(code),
    ech_status        TEXT,          -- assigned | standard_only | kein_standard
    UNIQUE(data_field_id, ord)
);
CREATE INDEX IF NOT EXISTS ix_subfield_field ON data_subfield(data_field_id);
"""


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)

    # keep any eCH work already done, keyed by (field, normalised name)
    keep = {}
    for r in c.execute("SELECT data_field_id, name, ech_element_id, ech_standard_code, ech_status "
                       "FROM data_subfield"):
        keep[(r["data_field_id"], norm(r["name"]))] = (
            r["ech_element_id"], r["ech_standard_code"], r["ech_status"])

    c.execute("DELETE FROM data_subfield")
    n = nf = 0
    for r in c.execute("SELECT id, subfields FROM data_field "
                       "WHERE subfields IS NOT NULL AND subfields NOT IN ('', '[]')").fetchall():
        try:
            subs = json.loads(r["subfields"])
        except Exception:
            continue
        seen = set()
        ord_ = 0
        for s in subs:
            name = (s if isinstance(s, str) else (s or {}).get("name") or "").strip()
            if not name:
                continue
            k = norm(name)
            if not k or k in seen:          # a composite never has the same part twice
                continue
            seen.add(k)
            eid, scode, status = keep.get((r["id"], k), (None, None, None))
            c.execute("INSERT INTO data_subfield(data_field_id, ord, name, ech_element_id,"
                      " ech_standard_code, ech_status) VALUES(?,?,?,?,?,?)",
                      [r["id"], ord_, name[:200], eid, scode, status])
            ord_ += 1
            n += 1
        if ord_:
            nf += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    kept = sum(1 for v in keep.values() if v[2])
    print(f"data_subfield: {n} Teilfelder aus {nf} zusammengesetzten Datenfeldern"
          f"{f' ({kept} bestehende eCH-Zuordnungen erhalten)' if kept else ''}")


if __name__ == "__main__":
    main()
