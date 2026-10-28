#!/usr/bin/env python3
"""The service-level consequences of the DVSH/SHEP harvests of 2026-10-28, with the
evidence in quellen/korrekturen/dvsh_abzug_2026-10-28.json. Staging -> validate ->
swap. Idempotent: a second run changes nothing and reports 0 everywhere.

Run after scripts/load_dvsh_harvest.py ../DVSH/dvsh_harvest_2026-10-28.json and
scripts/load_shep.py ../SHEP/2026-10-28/pages (the new service rows exist then).

  1. Removed services: a service DVSH deleted (it is in the modeller's trash) and
     that holds nothing of the databank — no Formular — goes, with its rows in the
     tables that point at it. A service with a Formular is never removed here.
  2. Duplicates: a new DVSH service that is the same service as an existing row
     (same procedure, same office, same Formular — judged and reviewed): the
     existing row takes the DVSH link and SHEP page, the new row goes; the DVSH
     title stays findable in name_alt.
  2b. Split: a row that carries a DVSH service whose Formular it does not hold
     keeps the identity its slug, name_alt and Formular show (rule of
     2026-09-27); the DVSH service gets its own row and takes its DVSH link,
     SHEP page and Themengruppen; the row is marked open until placed (3).
  3. Themengruppen of the new services (eCH-0049, panel + sceptical review, the
     DVSH's own Themen codes as a cross-check): the loader's mark «Themengruppe
     noch nicht zugeordnet» is replaced by the groups (rank = order), or by the
     reason why none fits. Only a service without any group is touched.

    python3 scripts/migrate_2026_10_28.py
"""
import json, os, shutil, sys
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate

SRC = os.path.join(ROOT, "quellen", "korrekturen", "dvsh_abzug_2026-10-28.json")
PLATZHALTER = "Themengruppe noch nicht zugeordnet"


def service_refs(c):
    """(table, column) of every column that points at service(id)."""
    out = []
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        for fk in c.execute(f"PRAGMA foreign_key_list({t})"):
            if fk[2] == "service" and fk[4] == "id":
                out.append((t, fk[3]))
    return out


def main():
    ev = json.load(open(SRC, encoding="utf-8"))
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    refs = service_refs(c)
    valid = {r[0] for r in c.execute("SELECT id FROM themenkatalog")}
    n = {"entfernt": 0, "zusammengefuehrt": 0, "themen": 0, "grund": 0}

    def drop_service(sid):
        if c.execute("SELECT 1 FROM form WHERE service_id=?", [sid]).fetchone():
            sys.exit(f"ABBRUCH: Service {sid} hat Formulare — wird hier nicht entfernt")
        for t, col in refs:
            if t not in ("service", "form"):
                c.execute(f"DELETE FROM {t} WHERE {col}=?", [sid])
        c.execute("DELETE FROM service WHERE id=?", [sid])

    # 1. services DVSH deleted
    for e in ev.get("entfernte_services", []):
        sid = e["service_id"]
        if not c.execute("SELECT 1 FROM service WHERE id=?", [sid]).fetchone():
            continue
        if c.execute("SELECT 1 FROM dvsh_service WHERE service_id=?", [sid]).fetchone():
            sys.exit(f"ABBRUCH: Service {sid} ist im DVSH-Abzug noch enthalten")
        drop_service(sid); n["entfernt"] += 1

    # 2. a new row that duplicates an existing service
    for m in ev.get("zusammenfuehren", []):
        new, old = m["new_service_id"], m["existing_service_id"]
        if not c.execute("SELECT 1 FROM service WHERE id=?", [new]).fetchone():
            continue
        c.execute("UPDATE dvsh_service SET service_id=?, match_kind='zusammengefuehrt-2026-10-28' WHERE service_id=?", [old, new])
        c.execute("UPDATE shep_service SET service_id=? WHERE service_id=?", [old, new])
        c.execute("UPDATE quellen_aenderung SET service_id=? WHERE service_id=?", [old, new])
        c.execute("UPDATE service SET in_dvsh=1 WHERE id=?", [old])
        # the DVSH title stays findable when it differs from the row's name (name_alt, «·»-joined)
        name, alt = c.execute("SELECT name, name_alt FROM service WHERE id=?", [old]).fetchone()
        t = (m.get("dvsh_titel") or "").strip()
        if t and t != name and t not in (alt or "").split(" · "):
            c.execute("UPDATE service SET name_alt=? WHERE id=?", [" · ".join(filter(None, [alt, t])), old])
        drop_service(new); n["zusammengefuehrt"] += 1

    # 2b. a row that carries a DVSH service whose Formular it does not hold: the row keeps
    #     the identity its slug, name_alt and Formular show (precedent 2026-09-27); the
    #     DVSH service gets a row of its own and takes its link, SHEP page and Themengruppen
    n["aufgeteilt"] = 0
    for a in ev.get("aufteilen", []):
        sid, did = a["service_id"], a["dvsh_id"]
        if not c.execute("SELECT 1 FROM dvsh_service WHERE dvsh_id=? AND service_id=?", [did, sid]).fetchone():
            continue
        dv = c.execute("SELECT slug, title FROM dvsh_service WHERE dvsh_id=?", [did]).fetchone()
        s = c.execute("SELECT department, dienststelle FROM service WHERE id=?", [sid]).fetchone()
        c.execute("INSERT INTO service(slug, name, dienststelle, department, in_dvsh) VALUES(?,?,?,?,1)",
                  [dv["slug"], dv["title"], s["dienststelle"], s["department"]])
        neu = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("UPDATE dvsh_service SET service_id=?, match_kind='aufgeteilt-2026-10-28' WHERE dvsh_id=?", [neu, did])
        c.execute("UPDATE shep_service SET service_id=? WHERE service_id=? AND dvsh_id=?", [neu, sid, did])
        c.execute("UPDATE quellen_aenderung SET service_id=? WHERE service_id=? AND quelle='DVSH' AND schluessel=?",
                  [neu, sid, str(did)])
        c.execute("UPDATE service_thema SET service_id=? WHERE service_id=?", [neu, sid])
        c.execute("UPDATE service_thema_grund SET service_id=? WHERE service_id=?", [neu, sid])
        c.execute("UPDATE service SET name=?, name_alt=NULL, in_dvsh=0 WHERE id=?", [a["name"], sid])
        c.execute("INSERT OR REPLACE INTO service_thema_grund(service_id, grund, zweitgeprueft) VALUES(?,?,0)",
                  [sid, f"Neu getrennt am {ev['abzug']} — {PLATZHALTER}."])
        n["aufgeteilt"] += 1

    # 3. Themengruppen of the new services
    for z in ev.get("themen", []):
        sid, themen = z["service_id"], z.get("themen") or []
        if not c.execute("SELECT 1 FROM service WHERE id=?", [sid]).fetchone():
            continue
        if c.execute("SELECT 1 FROM service_thema WHERE service_id=?", [sid]).fetchone():
            continue
        if len(themen) > 3 or any(t not in valid for t in themen):
            sys.exit(f"ABBRUCH: Service {sid}: Themengruppen {themen} ungültig")
        g = c.execute("SELECT grund FROM service_thema_grund WHERE service_id=?", [sid]).fetchone()
        if themen:
            if g and PLATZHALTER in (g[0] or ""):
                c.execute("DELETE FROM service_thema_grund WHERE service_id=?", [sid])
            for rang, t in enumerate(themen, 1):
                c.execute("INSERT INTO service_thema(service_id, thema_id, rang) VALUES(?,?,?)", [sid, t, rang])
            n["themen"] += 1
        elif (z.get("grund") or "").strip() and (not g or PLATZHALTER in (g[0] or "")):
            c.execute("INSERT OR REPLACE INTO service_thema_grund(service_id, grund, zweitgeprueft) VALUES(?,?,?)",
                      [sid, z["grund"].strip(), 1 if z.get("zweitgeprueft") else 0])
            n["grund"] += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:5], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print("migrate_2026_10_28: " + ", ".join(f"{k} {v}" for k, v in n.items()))


if __name__ == "__main__":
    main()
