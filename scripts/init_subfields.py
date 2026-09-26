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
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect, norm_ascii as norm
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
    esh_code          TEXT REFERENCES esh_standard(code),   -- draft eSH where eCH has nothing
    esh_element       TEXT,
    UNIQUE(data_field_id, ord)
);
CREATE INDEX IF NOT EXISTS ix_subfield_field ON data_subfield(data_field_id);
"""



def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)

    # keep any eCH AND eSH work already done, keyed by (field, normalised name) —
    # the 2026-09-03 rebuild kept only the eCH columns and wiped 1,221 eSH parts
    keep = {}
    has_esh = "esh_code" in {r[1] for r in c.execute("PRAGMA table_info(data_subfield)")}
    for r in c.execute("SELECT data_field_id, name, ech_element_id, ech_standard_code, ech_status"
                       + (", esh_code, esh_element" if has_esh else ", NULL esh_code, NULL esh_element")
                       + " FROM data_subfield"):
        keep[(r["data_field_id"], norm(r["name"]))] = (
            r["ech_element_id"], r["ech_standard_code"], r["ech_status"], r["esh_code"], r["esh_element"])

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
            eid, scode, status, esh_c, esh_e = keep.get((r["id"], k), (None, None, None, None, None))
            c.execute("INSERT INTO data_subfield(data_field_id, ord, name, ech_element_id,"
                      " ech_standard_code, ech_status, esh_code, esh_element) VALUES(?,?,?,?,?,?,?,?)",
                      [r["id"], ord_, name[:200], eid, scode, status, esh_c, esh_e])
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
