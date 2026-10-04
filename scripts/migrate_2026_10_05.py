#!/usr/bin/env python3
"""One-off data correction of 2026-10-05, with its evidence, applied staging ->
validate -> swap. Idempotent: a second run changes nothing, reports 0 and leaves
citygov.db untouched.

  1. Two article rows that are ingest artefacts, not articles
     (quellen/korrekturen/artikel_artefakte_2026-10-05.json): SR 831.20 «Art. 27»
     (row 1673) and SR 510.10 «Art. 48» (row 3997). Their «heading» is a list of
     paragraphs and in-force dates or of Amtliche-Sammlung references from the
     final provisions; each law has the real article with the same number as its
     own row (1629, 3904). They carry no text and nothing cites them. Because two
     rows had the same number, the second one got the permanent identifier «~2»
     (sh:gesetz:sr-831.20:art-27~2, sh:gesetz:sr-510.10:art-48~2): before
     identifiers are published, the rows are removed, and kennungen.py marks the two
     identifiers «entfallen» (an identifier is never deleted). Gates per row: the
     recorded law, number and heading match exactly, the real row with the same
     number exists, the row has no text, and no table refers to it.

    python3 scripts/migrate_2026_10_05.py
"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect
from validate_db import validate

BELEG = os.path.join(ROOT, "quellen", "korrekturen", "artikel_artefakte_2026-10-05.json")


def verweise(c, article_id):
    """[(table, column, n)] of every row that refers to the article (declared foreign keys)."""
    out = []
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        for fk in c.execute(f"PRAGMA foreign_key_list({t})"):
            if fk[2] == "article":
                n = c.execute(f"SELECT COUNT(*) FROM {t} WHERE {fk[3]}=?", [article_id]).fetchone()[0]
                if n:
                    out.append((t, fk[3], n))
    return out


def artefakte(c):
    """The rows to remove (after every gate) and the errors."""
    with open(BELEG, encoding="utf-8") as fh:
        liste = json.load(fh)
    weg, fehler = [], []
    for e in liste:
        r = c.execute("SELECT a.id, a.law_id, a.article_no, a.heading, a.text_excerpt, l.sr_number FROM article a "
                      "JOIN law l ON l.id=a.law_id WHERE a.id=?", [e["article_id"]]).fetchone()
        if r is None:
            continue                                         # already removed (idempotent)
        if (r[1], r[2], r[3], r[5]) != (e["law_id"], e["article_no"], e["heading"], e["sr_number"]):
            fehler.append(f"Artikel {e['article_id']}: Gesetz, Nummer oder Überschrift weichen vom Beleg ab")
            continue
        if (r[4] or "").strip():
            fehler.append(f"Artikel {e['article_id']}: hat Text — kein leeres Artefakt")
            continue
        echt = c.execute("SELECT heading FROM article WHERE id=? AND law_id=? AND article_no=?",
                         [e["echte_zeile"], e["law_id"], e["article_no"]]).fetchone()
        if not echt or echt[0] != e["echte_ueberschrift"]:
            fehler.append(f"Artikel {e['article_id']}: die echte Zeile {e['echte_zeile']} fehlt oder passt nicht")
            continue
        v = verweise(c, e["article_id"])
        if v:
            fehler.append(f"Artikel {e['article_id']}: wird zitiert ({v})")
            continue
        weg.append(e["article_id"])
    return weg, fehler


def main():
    c = connect(DB_PATH)
    weg, fehler = artefakte(c)
    c.close()
    if fehler:
        sys.exit("ABBRUCH — nichts geschrieben:\n  " + "\n  ".join(fehler))
    if not weg:
        print("1. Einleseartefakte (article): 0 entfernt — nichts zu tun, citygov.db unverändert")
        return
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executemany("DELETE FROM article WHERE id=?", [[i] for i in weg])
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st)
        sys.exit("ABBRUCH — Validierung, nichts geschrieben:\n  " + "\n  ".join(errs[:10]))
    os.replace(st, DB_PATH)
    print(f"1. Einleseartefakte (article): {len(weg)} entfernt ({weg}) — danach scripts/kennungen.py "
          "(markiert ihre Kennungen «entfallen»)")


if __name__ == "__main__":
    main()
