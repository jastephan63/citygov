#!/usr/bin/env python3
"""Apply individually verified corrections from a reviewable JSON file.

Each correction came from the adversarial review and was confirmed by a second,
independent check; the file (quellen/korrekturen/…) keeps them visible with
their reason. Gates: element / service / group ids must exist; for a single
label the (element, label) row must exist; vocabulary. Runs LAST in the
Begriffe chain (scripts/run_begriffe.py) so no earlier step overwrites it.

    python3 scripts/load_korrekturen.py quellen/korrekturen/<file>.json
"""
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

KL = {"variante", "rolle", "pruefen"}
PA = {None, "aufteilen", "zuordnung"}


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[:*]+\s*$", "", (s or "").strip())).lower()


def main():
    if os.environ.get("BEGRIFFE_CHAIN") != "1":
        sys.exit("Dieser Schritt baut auf den vorherigen auf und darf nicht allein laufen — "
                 "bitte scripts/run_begriffe.py verwenden.")
    K = json.load(open(sys.argv[1], encoding="utf-8"))
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    n = rej = 0
    for k in K.get("begriff_label", []):
        eid, kl, pa, gr = k["element_id"], k["klasse"], k.get("pruefart"), k["grund"]
        if kl not in KL or pa not in PA or not c.execute("SELECT 1 FROM begriff_vorschlag WHERE ech_element_id=?", [eid]).fetchone():
            rej += 1; continue
        where, args = "ech_element_id=?", [eid]
        if k.get("label"):
            where += " AND label_norm=?"; args.append(norm(k["label"]))
            if not c.execute(f"SELECT 1 FROM begriff_label WHERE {where}", args).fetchone():
                rej += 1; continue
        elif k.get("klasse_von"):
            where += " AND klasse=?"; args.append(k["klasse_von"])
        elif not k.get("alle"):
            rej += 1; continue
        n += c.execute(f"UPDATE begriff_label SET klasse=?, pruefart=?, pruefart_grund=?, rolle=NULL, grund=? WHERE {where}",
                       [kl, pa, gr, "Korrektur: " + gr] + args).rowcount
    for k in K.get("begriff_vorschlag", []):
        eid = k["element_id"]
        if not c.execute("SELECT 1 FROM begriff_vorschlag WHERE ech_element_id=?", [eid]).fetchone():
            rej += 1; continue
        if "term" in k:
            own = {r[0] for r in c.execute("SELECT label_norm FROM begriff_label WHERE ech_element_id=?", [eid])}
            if norm(k["term"]) not in own:
                rej += 1; continue
            c.execute("UPDATE begriff_label SET klasse='vorschlag', pruefart=NULL, grund=NULL WHERE ech_element_id=? AND label_norm=?",
                      [eid, norm(k["term"])])
            c.execute("UPDATE begriff_label SET klasse='variante', grund='gleiches Datum, anders geschrieben' "
                      "WHERE ech_element_id=? AND klasse='vorschlag' AND label_norm!=?", [eid, norm(k["term"])])
            c.execute("UPDATE begriff_vorschlag SET term=?, herkunft=? WHERE ech_element_id=?", [k["term"], k.get("herkunft", "eigen"), eid])
        c.execute("UPDATE begriff_vorschlag SET vorbehalt=?, pruefung=? WHERE ech_element_id=?",
                  [int(k.get("vorbehalt", 0)), k.get("pruefung"), eid])
        n += 1
    groups = {r[0] for r in c.execute("SELECT id FROM themenkatalog")}
    for k in K.get("service_thema", []):
        sid, th = k["service_id"], [t for t in k.get("themen", []) if t in groups]
        if not c.execute("SELECT 1 FROM service WHERE id=?", [sid]).fetchone() or not th:
            rej += 1; continue
        c.execute("DELETE FROM service_thema WHERE service_id=?", [sid])
        for rang, t in enumerate(th[:3], 1):
            c.execute("INSERT INTO service_thema VALUES(?,?,?)", [sid, t, rang])
        c.execute("INSERT OR REPLACE INTO service_thema_grund VALUES(?,?,1)", [sid, "Korrektur: " + k["grund"]])
        n += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Korrekturen: {n} angewandt, {rej} REJECTED")


if __name__ == "__main__":
    main()
