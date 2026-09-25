#!/usr/bin/env python3
"""Assign services to the eCH-0049 Themengruppen (Lebenslagen / Geschäftslagen).

The panel places each service where the person or business who needs it
would look (eCH-0049: perspective of the Leistungsbezüger); a sceptical
review corrects it. Gates: service id must be one that was asked; every
group id must exist in themenkatalog (loaded from the official PDF); at most
3 groups, most specific first; an empty assignment needs a reason. Review
corrections replace the first pass for that service. Idempotent.
Staging -> validate -> swap.

    python3 scripts/load_themen.py <dir-with-in_/out_/verify_*.json>
"""
import glob, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

DDL = """
CREATE TABLE IF NOT EXISTS service_thema (
    service_id    INTEGER NOT NULL REFERENCES service(id),
    thema_id      INTEGER NOT NULL REFERENCES themenkatalog(id),
    rang          INTEGER NOT NULL,
    PRIMARY KEY (service_id, thema_id)
);
CREATE TABLE IF NOT EXISTS service_thema_grund (
    service_id    INTEGER PRIMARY KEY REFERENCES service(id),
    grund         TEXT,
    zweitgeprueft INTEGER NOT NULL DEFAULT 0
);
"""


def main():
    src = sys.argv[1]
    asked = set()
    for jf in glob.glob(f"{src}/in_*.json"):
        asked |= {s["service_id"] for s in json.load(open(jf, encoding="utf-8"))}
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    valid = {r[0] for r in c.execute("SELECT id FROM themenkatalog")}
    c.execute("DELETE FROM service_thema"); c.execute("DELETE FROM service_thema_grund")
    ass, rej, korr = {}, [], 0
    for jf in sorted(glob.glob(f"{src}/out_*.json")):
        for z in json.load(open(jf, encoding="utf-8")).get("zuordnungen", []):
            ass[z.get("service_id")] = (z.get("themen") or [], z.get("grund"), 0)
    for jf in sorted(glob.glob(f"{src}/verify_*.json")):
        for z in json.load(open(jf, encoding="utf-8")).get("korrekturen", []):
            if z.get("service_id") in ass:
                ass[z["service_id"]] = (z.get("themen") or [], "Zweitprüfung: " + (z.get("grund") or ""), 1)
                korr += 1
    n_a = n_leer = 0
    for sid, (themen, grund, geprueft) in ass.items():
        if sid not in asked:
            rej.append(f"service {sid} nicht gefragt"); continue
        clean = []
        for t in themen:
            if t in valid and t not in clean:
                clean.append(t)
            elif t not in valid:
                rej.append(f"service {sid}: Thema {t} existiert nicht")
        clean = clean[:3]
        if not clean and not (grund or "").strip():
            rej.append(f"service {sid}: leer ohne Grund"); continue
        for rang, t in enumerate(clean, 1):
            c.execute("INSERT INTO service_thema VALUES(?,?,?)", [sid, t, rang]); n_a += 1
        c.execute("INSERT INTO service_thema_grund VALUES(?,?,?)", [sid, (grund or "")[:300], geprueft])
        n_leer += (not clean)
    unanswered = asked - set(ass)
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Themen: {len(ass) - len(unanswered & set(ass))} Services, {n_a} Zuordnungen, {n_leer} ohne Thema "
          f"(mit Grund), {korr} durch die Zweitprüfung korrigiert, {len(unanswered)} ohne Antwort, {len(rej)} REJECTED")
    for r in rej[:8]:
        print("  ", r)


if __name__ == "__main__":
    main()
