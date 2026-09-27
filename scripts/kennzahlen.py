#!/usr/bin/env python3
"""Key figures of the databank over time (verlauf.json) — ONE definition.

The dashboard's first question from a reader is «are we getting better?». Every
build therefore records a small snapshot in verlauf.json (one entry per day,
the day's last build wins). `db_kennzahlen(conn)` computes the figures straight
from a citygov.db of ANY vintage: a figure whose columns did not exist yet in
that version is recorded as None (not guessed), so the same definition holds
for today's build and for the snapshots reconstructed from the Git history
(scripts/backfill_verlauf.py).

Figures that need the export's own logic (Standard-Divergenzen, Begriffe, open
points by tone) are added by export_json.py for the current build only.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

VERLAUF_PATH = os.path.join(ROOT, "verlauf.json")


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _cols(conn, t):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}


def db_kennzahlen(conn):
    T = _tables(conn)
    if "form" not in T or "data_field" not in T:
        return None
    one = lambda q: conn.execute(q).fetchone()[0]
    dcols = _cols(conn, "data_field")
    k = {"formulare": one("SELECT COUNT(*) FROM form"), "datenfelder": one("SELECT COUNT(*) FROM data_field")}
    # data standard: atomic data points (a composite counts by its parts) with an eCH element
    if "ech_element_id" in dcols:
        if "data_subfield" in T and "ech_element_id" in _cols(conn, "data_subfield"):
            k["punkte"] = one("SELECT (SELECT COUNT(*) FROM data_subfield) + (SELECT COUNT(*) FROM data_field d "
                              "WHERE NOT EXISTS (SELECT 1 FROM data_subfield s WHERE s.data_field_id=d.id))")
            k["punkte_ech"] = one("SELECT (SELECT COUNT(*) FROM data_subfield WHERE ech_element_id IS NOT NULL) + "
                                  "(SELECT COUNT(*) FROM data_field d WHERE ech_element_id IS NOT NULL AND NOT EXISTS "
                                  "(SELECT 1 FROM data_subfield s WHERE s.data_field_id=d.id))")
        else:
            k["punkte"], k["punkte_ech"] = k["datenfelder"], one("SELECT COUNT(*) FROM data_field WHERE ech_element_id IS NOT NULL")
    else:
        k["punkte"] = k["punkte_ech"] = None
    # legal basis: cited / covered (cited, or needed for the task — for a
    # sensitive datum only with a citation, KDSG Art. 5) / surplus / to research
    has_lb = "data_field_legal_basis" in T
    cited = "EXISTS (SELECT 1 FROM data_field_legal_basis b WHERE b.data_field_id=d.id)" if has_lb else "0"
    k["felder_zitiert"] = one(f"SELECT COUNT(*) FROM data_field d WHERE {cited}") if has_lb else None
    if "basis_typ" in dcols:
        sens = "d.sensitive IS NOT NULL AND d.sensitive<>''" if "sensitive" in dcols else "0"
        k["felder_gedeckt"] = one(f"SELECT COUNT(*) FROM data_field d WHERE {cited} OR "
                                  f"(d.basis_typ='aufgabe' AND NOT ({sens}))")
        k["felder_ohne"] = one("SELECT COUNT(*) FROM data_field WHERE basis_typ='ohne'")
        k["felder_offen"] = one("SELECT COUNT(*) FROM data_field WHERE basis_typ='offen'")
        k["felder_zu_ermitteln"] = one(f"SELECT COUNT(*) FROM data_field d WHERE d.basis_typ IS NULL AND NOT ({cited})")
        k["felder_art5_offen"] = one(f"SELECT COUNT(*) FROM data_field d WHERE d.basis_typ='aufgabe' AND ({sens}) "
                                     f"AND NOT ({cited})")
    else:
        for x in ("felder_gedeckt", "felder_ohne", "felder_offen", "felder_zu_ermitteln", "felder_art5_offen"):
            k[x] = None
    # register: forms with a recorded purpose
    k["formulare_mit_zweck"] = one("SELECT COUNT(*) FROM form WHERE purpose IS NOT NULL AND purpose<>''") \
        if "purpose" in _cols(conn, "form") else None
    return k


def load():
    try:
        return json.load(open(VERLAUF_PATH, encoding="utf-8"))
    except (OSError, ValueError):
        return {"hinweis": None, "eintraege": []}


def save(doc):
    doc["hinweis"] = ("Kennzahlen je Stand der Databank, ein Eintrag je Tag (der letzte Build des Tages gilt). "
                      "Einträge mit «quelle: git …» sind aus der Git-Historie von citygov.db rekonstruiert "
                      "(scripts/backfill_verlauf.py); None = in jenem Stand noch nicht erhoben. "
                      "Geschrieben von scripts/export_json.py bei jedem Build.")
    doc["eintraege"].sort(key=lambda e: e["datum"])
    json.dump(doc, open(VERLAUF_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def upsert(doc, entry):
    doc["eintraege"] = [e for e in doc["eintraege"] if e["datum"] != entry["datum"]] + [entry]
    return doc
