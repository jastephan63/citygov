#!/usr/bin/env python3
"""Corrections to the harvest log after the live portal services.sh.ch was first
harvested (2026-11-03), with the evidence in quellen/korrekturen/quellen_log_2026-11-03.json.

A field the log names as changed although only the page parser erred (not the source)
is taken out of that log row; a row left without a changed field goes. Staging ->
validate -> swap. Idempotent: a second run changes nothing.

    python3 scripts/migrate_2026_11_03.py
"""
import json, os, shutil, sys
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate

SRC = os.path.join(ROOT, "quellen", "korrekturen", "quellen_log_2026-11-03.json")


def main():
    ev = json.load(open(SRC, encoding="utf-8"))
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    n = {"felder": 0, "zeilen": 0}
    for e in ev["streichen"]:
        if not (e.get("beleg") or "").strip():
            sys.exit(f"ABBRUCH: {e['schluessel']}: Beleg fehlt")
        key = [e["quelle"], e["abzug"], e["schluessel"]]
        r = c.execute("SELECT art, felder FROM quellen_aenderung WHERE quelle=? AND abzug=? AND schluessel=?", key).fetchone()
        if not r or r["art"] != "geaendert":
            continue
        felder = json.loads(r["felder"] or "[]")
        if e["feld"] not in felder:
            continue
        felder.remove(e["feld"])
        n["felder"] += 1
        if felder:
            c.execute("UPDATE quellen_aenderung SET felder=? WHERE quelle=? AND abzug=? AND schluessel=?",
                      [json.dumps(felder, ensure_ascii=False)] + key)
        else:
            c.execute("DELETE FROM quellen_aenderung WHERE quelle=? AND abzug=? AND schluessel=?", key)
            n["zeilen"] += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:5], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"migrate_2026_11_03: {n['felder']} Feld(er) aus dem Abzugsprotokoll gestrichen, {n['zeilen']} Zeile(n) entfernt")


if __name__ == "__main__":
    main()
