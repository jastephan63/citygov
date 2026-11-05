#!/usr/bin/env python3
"""One-off data correction of 2026-11-05, with its evidence, applied staging ->
validate -> swap. Idempotent: a second run changes nothing, reports 0 and leaves
citygov.db untouched.

  1. Six article rows of the Steuergesetz (SHR 641.100) and its Verordnung
     (SHR 641.111) that are ingest artefacts, not articles
     (quellen/korrekturen/artikel_artefakte_2026-11-05.json): wrapped lines of the
     law text that begin with a reference to another article — «Art. 24a des
     Bundesgesetzes …» (StHG), «§ 28 der Vollzugsverordnung zum altStG», the second
     line «Art. 78 und 79» of the heading of Art. 238 StG, and three «Art. N … StG»
     lines in the Verordnung, which numbers its articles with «§». The old line-index
     reader took them for articles; the full-text reader of ingest_laws.py does not.
     Gates per row: the recorded law, number and heading match exactly, the row has
     no text, no table refers to it, the recorded line stands in the law's PDF text,
     and the full-text reader does not read that number as an article of the law.
     Afterwards scripts/kennungen.py marks their identifiers «entfallen» (an
     identifier is never deleted).

    python3 scripts/migrate_2026_11_05.py
"""
import json, os, shutil, subprocess, sys
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate
from citygov.load.ingest_laws import BYSHR, HERE, read_law
from citygov.load.migrate_2026_10_05 import verweise

BELEG = os.path.join(ROOT, "quellen", "korrekturen", "artikel_artefakte_2026-11-05.json")


def gesetzestext(shr):
    path = os.path.normpath(os.path.join(ROOT, "..", "Gesetze", BYSHR[shr]["file"]))
    return subprocess.run(["python3", os.path.join(HERE, "extract_law.py"), path],
                          capture_output=True, text=True, timeout=90).stdout


def artefakte(c):
    """The rows to remove (after every gate) and the errors."""
    with open(BELEG, encoding="utf-8") as fh:
        liste = json.load(fh)
    weg, fehler, gelesen = [], [], {}
    for e in liste:
        r = c.execute("SELECT a.id, a.law_id, a.article_no, a.heading, a.text_excerpt, l.cantonal_ref FROM article a "
                      "JOIN law l ON l.id=a.law_id WHERE a.id=?", [e["article_id"]]).fetchone()
        if r is None:
            continue                                         # already removed (idempotent)
        if (r[1], r[2], r[3], r[5]) != (e["law_id"], e["article_no"], e["heading"], e["cantonal_ref"]):
            fehler.append(f"Artikel {e['article_id']}: Gesetz, Nummer oder Überschrift weichen vom Beleg ab")
            continue
        if (r[4] or "").strip():
            fehler.append(f"Artikel {e['article_id']}: hat Text — kein leeres Artefakt")
            continue
        v = verweise(c, e["article_id"])
        if v:
            fehler.append(f"Artikel {e['article_id']}: wird zitiert ({v})")
            continue
        shr = e["cantonal_ref"][4:]
        if shr not in gelesen:
            gelesen[shr] = (gesetzestext(shr), read_law(shr))
        text, law = gelesen[shr]
        if e["fundstelle"] not in {ln.strip() for ln in text.splitlines()}:
            fehler.append(f"Artikel {e['article_id']}: die Zeile «{e['fundstelle']}» steht nicht im Gesetzestext")
            continue
        if not law or e["article_no"] in {a["no"] for a in law["articles"]}:
            fehler.append(f"Artikel {e['article_id']}: der Volltext-Leser liest «{e['article_no']}» als Artikel")
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
