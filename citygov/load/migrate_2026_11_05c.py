#!/usr/bin/env python3
"""One-off data correction of 2026-11-05 (third part), with its evidence, applied staging ->
validate -> swap. Idempotent: a second run changes nothing, reports 0 and leaves citygov.db
untouched.

The citations of Formulare 275 (Vollständigkeitserklärung zur Jahresrechnung) and 280 (Bericht
und Antrag Rechnungsprüfungsorgan, Formularsatz Jahresrechnung Zweckverband) rested on GG
(SHR 120.100) Art. 73 «Rechnungsablage»; its Abs. 1–2 are repealed since 1 January 2018 (the
Finanzhaushaltsgesetz of 20 February 2017 took over), only Abs. 3 (the accounts NOT approved)
is in force. A panel (first judgement and a sceptical second review, quellen/dokumente/
panel_2026-11-05/recht/art73/) re-judged every field of both Formulare; the adjudicated result
is quellen/korrekturen/zitate_gg73_2026-11-05.json:

  per field: the citations to remove, the citations to add (each with a verbatim quote from
  the article), and — where no article governs the field — basis_typ aufgabe/ohne with the
  reason (data_field.no_basis=1, as load_field_legal.py + load_basis_typ.py would set it).

Gates: the field is the recorded one (id, Formular, name); a citation to add is an ingested
article (last_checked «Gesetze-PDF …» or «verified», the proof gate of load_field_legal.py)
whose text in the official PDF holds the recorded quote; a field left without a citation has a
basis_typ from the vocabulary and a reason of 8–240 characters that does not say «Datum» for
a piece of data; a field with a citation is basis_typ «artikel». The second review of every
basis_typ verdict is recorded in panel_review (kind 'basis'), as load_panel_reviews.py does.
Afterwards scripts/gesetz_stand.py and scripts/extract_quotes.py (the new articles' texts).

    python3 scripts/migrate_2026_11_05c.py
"""
import json, os, re, shutil, sys
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate
from citygov.load.migrate_2026_11_05b import artikeltext, norm, ziel

BELEG = os.path.join(ROOT, "quellen", "korrekturen", "zitate_gg73_2026-11-05.json")
BASIS = {"aufgabe", "ohne"}
PANEL_REVIEW = """CREATE TABLE IF NOT EXISTS panel_review (
    kind     TEXT NOT NULL,
    item_id  INTEGER NOT NULL,
    urteil   TEXT NOT NULL,
    grund    TEXT,
    PRIMARY KEY (kind, item_id)
)"""


def pruefen(c, beleg):
    """[(field id, removals [(article id)], additions [(article id, last_checked)], basis or None,
    review)] after every gate, and the errors."""
    tun, fehler = [], []
    for f in beleg["felder"]:
        did = f["data_field_id"]
        r = c.execute("SELECT form_id, name, basis_typ, coalesce(basis_begruendung,''), no_basis FROM data_field "
                      "WHERE id=?", [did]).fetchone()
        if r is None or (r[0], r[1]) != (f["form_id"], f["name"]):
            fehler.append(f"Datenfeld {did}: Formular oder Name weichen vom Beleg ab"); continue
        hat = {row[0] for row in c.execute("SELECT article_id FROM data_field_legal_basis WHERE data_field_id=?", [did])}
        weg = []
        for t in f["entfernen"]:
            hit = ziel(c, t["cref"], t["article_no"])
            if not hit:
                fehler.append(f"Datenfeld {did}: {t['cref']} {t['article_no']} ist kein eingelesener Artikel"); continue
            if hit[0] in hat:
                weg.append(hit[0])
        dazu = []
        for t in f["hinzu"]:
            hit = ziel(c, t["cref"], t["article_no"])
            if not hit:
                fehler.append(f"Datenfeld {did}: Ziel {t['cref']} {t['article_no']} nicht eingelesen"); continue
            text = artikeltext(t["cref"], t["article_no"])
            if not text or norm(t["beleg"]) not in text:
                fehler.append(f"Datenfeld {did}: das Zitat «{t['beleg'][:50]}…» steht nicht in {t['article_no']}")
                continue
            if hit[0] not in hat:
                dazu.append(hit)
        rest = (hat - set(weg)) | {h[0] for h in dazu}
        basis = None
        if not rest:
            bt, why = f.get("basis_typ"), (f.get("begruendung") or "").strip()
            if bt not in BASIS or not 8 <= len(why) <= 240:
                fehler.append(f"Datenfeld {did}: ohne Zitat braucht es basis_typ aufgabe/ohne und eine Begründung"); continue
            if re.search(r"\bDatum\b", why):
                fehler.append(f"Datenfeld {did}: die Begründung sagt «Datum» (Wortwahl: «Angabe»)"); continue
            if (r[2], r[3], r[4]) != (bt, why, 1):
                basis = (bt, why)
        elif f.get("basis_typ") not in (None, "artikel"):
            fehler.append(f"Datenfeld {did}: hat ein Zitat, basis_typ muss «artikel» sein"); continue
        elif r[2] != "artikel" or r[4] != 0:
            basis = ("artikel", None)
        review = f.get("zweitpruefung")
        if not (weg or dazu or basis):
            continue
        tun.append((did, weg, dazu, basis, review))
    return tun, fehler


def anwenden(c, tun):
    c.execute(PANEL_REVIEW)
    n = 0
    for did, weg, dazu, basis, review in tun:
        for aid, lc in dazu:
            c.execute("INSERT INTO data_field_legal_basis(data_field_id, article_id, last_checked, relation) "
                      "VALUES(?,?,?,?)", [did, aid, lc, "requires"])
        c.executemany("DELETE FROM data_field_legal_basis WHERE data_field_id=? AND article_id=?",
                      [[did, aid] for aid in weg])
        if basis and basis[0] == "artikel":
            c.execute("UPDATE data_field SET basis_typ='artikel', basis_begruendung=NULL, no_basis=0 WHERE id=?", [did])
        elif basis:
            c.execute("UPDATE data_field SET basis_typ=?, basis_begruendung=?, no_basis=1 WHERE id=?",
                      [basis[0], basis[1], did])
            if review:
                c.execute("INSERT OR REPLACE INTO panel_review(kind, item_id, urteil, grund) VALUES('basis',?,?,?)",
                          [did, review["urteil"], review["grund"][:380]])
        n += 1
    return n


def main():
    with open(BELEG, encoding="utf-8") as fh:
        beleg = json.load(fh)
    c = connect(DB_PATH)
    tun, fehler = pruefen(c, beleg)
    c.close()
    if fehler:
        sys.exit("ABBRUCH — nichts geschrieben:\n  " + "\n  ".join(fehler))
    if not tun:
        print("Zitate auf GG Art. 73 (Formulare 275, 280): 0 — nichts zu tun, citygov.db unverändert")
        return
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    n = anwenden(c, tun)
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st)
        sys.exit("ABBRUCH — Validierung, nichts geschrieben:\n  " + "\n  ".join(errs[:10]))
    os.replace(st, DB_PATH)
    print(f"Zitate auf GG Art. 73 (Formulare 275, 280): {n} Felder neu beurteilt — danach "
          "scripts/gesetz_stand.py und scripts/extract_quotes.py")


if __name__ == "__main__":
    main()
