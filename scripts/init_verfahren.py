#!/usr/bin/env python3
"""Add the Verfahren/lifecycle layer around each Formular: submission channel,
enclosures (beilage), procedure outcome, edition similarity, review dates and
reachable owners.

Mechanical part (this script): DDL, channel harvest from the DVSH abgabe
strings, form_check review dates, Dienststellen contacts backfilled from the
read-only DVSH harvest, and the truncated VRG title repaired from the official
Rechtsbuch API. The curated part (beilage classification, outcome derivation)
comes from agents through load_verfahren.py's gates.

Idempotent. Staging -> validate -> swap.

    python3 scripts/init_verfahren.py
"""
import json, os, shutil, sys, urllib.request
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

DDL = """
CREATE TABLE IF NOT EXISTS beilage (
    id            INTEGER PRIMARY KEY,
    form_id       INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    data_field_id INTEGER REFERENCES data_field(id),
    bezeichnung   TEXT NOT NULL,
    obligatorium  TEXT CHECK(obligatorium IN ('zwingend','bedingt','fakultativ','unbekannt')),
    bedingung     TEXT,
    halter        TEXT CHECK(halter IN ('privat','einwohnerregister','handelsregister',
                     'betreibungsregister','strafregister','steuerverwaltung','grundbuch',
                     'kanton_andere','bund','unbekannt')),
    fetchable     INTEGER NOT NULL DEFAULT 0,
    source        TEXT NOT NULL CHECK(source IN ('formular','dvsh','beide')),
    last_checked  TEXT,
    UNIQUE(form_id, bezeichnung)
);
CREATE TABLE IF NOT EXISTS form_outcome (
    form_id            INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    entscheid_art      TEXT CHECK(entscheid_art IN ('bewilligung','verfuegung','bestaetigung',
                          'registereintrag','auszahlung','kein_entscheid','unbekannt')),
    ergebnis_dokument  TEXT,
    rechtsmittel_art   TEXT,
    rechtsmittel_frist_tage INTEGER,
    rechtsmittel_instanz TEXT,
    article_id         INTEGER REFERENCES article(id),
    last_checked       TEXT
);
CREATE TABLE IF NOT EXISTS form_similarity (
    form_a  INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    form_b  INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    jaccard_names REAL NOT NULL,
    jaccard_ech   REAL,
    verdict TEXT CHECK(verdict IN ('duplicate_ingest','merge_candidate','template_family','ok')),
    note    TEXT,
    PRIMARY KEY(form_a, form_b)
);
"""


def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    for col in ("form", "submission_channel TEXT"), ("form_check", "next_check_due TEXT"):
        try:
            c.execute(f"ALTER TABLE {col[0]} ADD COLUMN {col[1]}")
        except Exception:
            pass

    # submission channel from the DVSH abgabe strings; 'unbekannt' stays honest
    ch = Counter()
    dv = {r["service_id"]: r["abgabe"] for r in c.execute(
        "SELECT service_id, abgabe FROM dvsh_service WHERE service_id IS NOT NULL")}
    for r in c.execute("SELECT id, service_id FROM form").fetchall():
        a = dv.get(r["service_id"])
        try:
            items = " ".join(json.loads(a)) if a else ""
        except Exception:
            items = a or ""
        kind = ("online_formular" if "Online-Formular" in items
                else "pdf" if "PDF-Formular" in items
                else "schalter" if "Schalter" in items else "unbekannt")
        c.execute("UPDATE form SET submission_channel=? WHERE id=?", [kind, r["id"]])
        ch[kind] += 1

    # review date: currency verdicts age — 42 days, suspects sooner
    c.execute("UPDATE form_check SET next_check_due = date(substr(checked_at,1,10), "
              "CASE WHEN status IN ('veraltet','veraltet_verdacht') THEN '+14 days' "
              "ELSE '+42 days' END) WHERE checked_at IS NOT NULL")

    # reachable owners: DVSH kontakt (read-only harvest) -> dienststelle
    kb = {}
    for r in c.execute("SELECT s.dienststelle d, dv.kontakt k FROM dvsh_service dv "
                       "JOIN service s ON s.id=dv.service_id "
                       "WHERE dv.kontakt IS NOT NULL AND dv.kontakt!='' AND s.dienststelle IS NOT NULL"):
        kb.setdefault(r["d"], Counter())[r["k"]] += 1
    nk = 0
    for name, cnt in kb.items():
        k = cnt.most_common(1)[0][0][:200]
        nk += c.execute("UPDATE dienststelle SET kontakt=? WHERE name=? AND kontakt IS NULL",
                        [k, name]).rowcount

    # repair the truncated VRG title from the official Rechtsbuch API
    try:
        d = json.load(urllib.request.urlopen(
            "https://rechtsbuch.sh.ch/api/de/texts_of_law/172.200", timeout=20))
        t = d["text_of_law"]["title"]
        if "Rechtsschutz" in t:
            c.execute("UPDATE law SET title=?, short_title='VRG' WHERE id=328", [t])
    except Exception as e:
        print("  VRG-Titel nicht korrigiert:", type(e).__name__)

    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Verfahren-Layer: Kanäle {dict(ch)}, {nk} Dienststellen-Kontakte aus DVSH, "
          f"Wiedervorlage-Daten gesetzt")


if __name__ == "__main__":
    main()
