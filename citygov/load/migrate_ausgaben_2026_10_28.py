#!/usr/bin/env python3
"""Carry the data fields of the Formulare whose newer edition arrived with the
harvests of 2026-10-28 (load_uebernahme.py swapped their files) over to the new
edition. Evidence: quellen/dokumente/ausgaben_2026-10-28.json — per Formular the
reviewed port (a panel compared the old and the new edition, a sceptical second
review corrected it): every existing field the edition still asks for keeps its
id and with it every curated layer (eCH, legal basis, basis_typ, subjekt …),
changed where the edition prints another label, type, options or parts; a field
the edition dropped goes, with the rows that hang on it; an Angabe the edition
adds is a new field without curated layers yet.

Parts (data_subfield) of a changed composite: a part that stays keeps its row,
id and eCH element (matched by normalised name), a dropped part goes, a new part
is added at the end of the table (no existing id moves). New fields get their
parts from init_subfields.py --nur-neue. Staging -> validate -> swap.
Idempotent: a second run changes nothing.

    python3 scripts/migrate_ausgaben_2026_10_28.py
"""
import json, os, shutil, sys
from citygov.core.common import ROOT, DB_PATH, connect, norm_ascii as norm
from citygov.checks.validate_db import validate

SRC = os.path.join(ROOT, "quellen", "dokumente", "ausgaben_2026-10-28.json")
COLS = ("name", "definition", "data_type", "required", "allowed_values", "subfields", "format")


def field_refs(c):
    """(table, column) of every column that points at data_field(id)."""
    out = []
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        for fk in c.execute(f"PRAGMA foreign_key_list({t})"):
            if fk[2] == "data_field" and fk[4] == "id":
                out.append((t, fk[3]))
    return out


def werte(f):
    return [str(f["name"]).strip()[:160], (f.get("definition") or "").strip()[:400], f["data_type"],
            0 if f.get("required") is False else 1,
            json.dumps(f.get("allowed_values") or [], ensure_ascii=False),
            json.dumps(f.get("subfields") or [], ensure_ascii=False), (f.get("format") or "").strip()]


def main():
    ev = json.load(open(SRC, encoding="utf-8"))
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    refs = field_refs(c)
    n = {"geaendert": 0, "neu": 0, "entfallen": 0, "teile_neu": 0, "teile_weg": 0}
    for p in ev["ports"]:
        fid = p["form_id"]
        have = {r["id"]: r for r in c.execute("SELECT * FROM data_field WHERE form_id=?", [fid])}
        # every existing field once — kept (felder) or dropped (entfallen); a second run
        # finds the dropped ones gone already
        ids = [f["id"] for f in p["felder"] if f["id"] is not None]
        listed = ids + [e["id"] for e in p["entfallen"]]
        # a field a former run added for a new Angabe (id null in the port) is covered by its name
        neu_namen = {str(f["name"]).strip()[:160] for f in p["felder"] if f["id"] is None}
        frueher_neu = {i for i, r in have.items() if r["name"] in neu_namen and i not in listed}
        if len(listed) != len(set(listed)) or not set(have) - frueher_neu <= set(listed) or set(ids) - set(have):
            sys.exit(f"ABBRUCH: Formular {fid}: die Feldliste deckt die bestehenden Felder nicht genau ab")
        for e in p["entfallen"]:
            if e["id"] not in have:
                continue
            for t, col in refs:
                if t == "beilage":
                    c.execute(f"UPDATE beilage SET {col}=NULL WHERE {col}=?", [e["id"]])
                elif t != "data_field":
                    c.execute(f"DELETE FROM {t} WHERE {col}=?", [e["id"]])
            c.execute("DELETE FROM panel_review WHERE kind IN ('basis','subjekt') AND item_id=?", [e["id"]])
            c.execute("DELETE FROM data_field WHERE id=?", [e["id"]])
            n["entfallen"] += 1
        for ord_, f in enumerate(p["felder"]):
            if f["id"] is None:
                if c.execute("SELECT 1 FROM data_field WHERE form_id=? AND name=?", [fid, f["name"].strip()[:160]]).fetchone():
                    continue
                c.execute("INSERT INTO data_field(form_id, ord, name, definition, data_type, required, allowed_values,"
                          " subfields, format, source_widgets, derived_by) VALUES(?,?,?,?,?,?,?,?,?,'[]','agent')",
                          [fid, ord_] + werte(f))
                n["neu"] += 1
                continue
            old = have[f["id"]]
            neu = werte(f)
            c.execute("UPDATE data_field SET ord=? WHERE id=?", [ord_, f["id"]])
            if f["aktion"] == "unveraendert" or [old[k] for k in COLS] == neu:
                continue
            c.execute(f"UPDATE data_field SET {', '.join(k + '=?' for k in COLS)} WHERE id=?", neu + [f["id"]])
            n["geaendert"] += 1
            # the parts: keep the rows of parts that stay, drop the others, add the new ones
            teile = [(s if isinstance(s, str) else (s or {}).get("name") or "").strip()
                     for s in (f.get("subfields") or [])] if f["data_type"] == "composite" else []
            want, seen = [], set()
            for t in teile:
                if t and norm(t) not in seen:
                    seen.add(norm(t)); want.append(t)
            rows = {norm(r["name"]): r for r in c.execute("SELECT id, name FROM data_subfield WHERE data_field_id=?", [f["id"]])}
            for k, r in rows.items():
                if k not in seen:
                    c.execute("DELETE FROM data_subfield WHERE id=?", [r["id"]]); n["teile_weg"] += 1
            # ord is unique per field: park the kept rows, then number them in the new order
            c.execute("UPDATE data_subfield SET ord=-1-ord WHERE data_field_id=?", [f["id"]])
            for o, t in enumerate(want):
                r = rows.get(norm(t))
                if r:
                    c.execute("UPDATE data_subfield SET ord=?, name=? WHERE id=?", [o, t[:200], r["id"]])
                else:
                    c.execute("INSERT INTO data_subfield(data_field_id, ord, name) VALUES(?,?,?)", [f["id"], o, t[:200]])
                    n["teile_neu"] += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:5], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print("migrate_ausgaben_2026_10_28: " + ", ".join(f"{k} {v}" for k, v in n.items()))


if __name__ == "__main__":
    main()
