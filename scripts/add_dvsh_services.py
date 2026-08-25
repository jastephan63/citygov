#!/usr/bin/env python3
"""Add DVSH services that have no counterpart in our databank as first-class
services (DVSH is the master catalogue). Used for pure online/eServices, which
have no downloadable form — they carry DVSH's authoritative legal bases and
service metadata but no form/data fields of ours.

    python3 scripts/add_dvsh_services.py <parsed.json> [--only-online]
"""
import json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate


def slugify(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:70] or "service"


def main():
    data = {x["dvsh_id"]: x for x in json.load(open(sys.argv[1], encoding="utf-8"))}
    only_online = "--only-online" in sys.argv
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    todo = c.execute("SELECT dvsh_id, title, department, dienststelle FROM dvsh_service "
                     "WHERE service_id IS NULL").fetchall()
    slugs = {r["slug"] for r in c.execute("SELECT slug FROM service")}
    added = 0
    for r in todo:
        d = data.get(r["dvsh_id"], {})
        if only_online and d.get("source_files"):
            continue                      # has a form -> handled by the download path
        base = slugify(r["title"]); slug = base; i = 2
        while slug in slugs:
            slug = f"{base}-{i}"; i += 1
        slugs.add(slug)
        c.execute("INSERT INTO service(slug,name,dienststelle,department,description,notes) "
                  "VALUES(?,?,?,?,?,?)",
                  [slug, r["title"], r["dienststelle"], r["department"],
                   (d.get("kurzbeschreibung") or "")[:500],
                   "Online-/eService aus dem DVSH-Modell — kein herunterladbares Formular; "
                   "Rechtsgrundlagen und Ablauf stammen aus der amtlichen DVSH-Modellierung."])
        sid = c.execute("SELECT id FROM service WHERE slug=?", [slug]).fetchone()["id"]
        c.execute("UPDATE dvsh_service SET service_id=?, match_kind='dvsh-only' WHERE dvsh_id=?",
                  [sid, r["dvsh_id"]])
        # process steps from DVSH's Ablauf (authoritative, mode unknown -> manual)
        for n, step in enumerate(d.get("ablauf") or [], 1):
            if len(step) > 4:
                c.execute("INSERT INTO process_step(service_id,step_no,description,mode) "
                          "VALUES(?,?,?,?)", [sid, n, step[:400], "manual"])
        added += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"added {added} DVSH-only services")


if __name__ == "__main__":
    main()
