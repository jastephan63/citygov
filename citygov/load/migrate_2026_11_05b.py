#!/usr/bin/env python3
"""One-off data correction of 2026-11-05 (second part: the remaining cantonal laws), with its
evidence, applied staging -> validate -> swap. Idempotent: a second run changes nothing,
reports 0 and leaves citygov.db untouched.

Runs AFTER `python3 scripts/ingest_laws.py <every cantonal SHR>`: the full-text reader of
ingest_laws.py reads the articles the corrections point to (§ 27 PolV, Art. 27/27a PolG,
§ A1a-2 of the Pflegekinderverordnung), and it no longer reads the rows removed here.
Evidence: quellen/korrekturen/artikel_artefakte_2026-11-05b.json.

  1. Citations of article rows that are ingest artefacts — wrapped lines of the law text that
     begin with a reference to another article («Art. 269d OR …» in Art. 142b EG ZGB, stored
     as «Art. 26d»; «Art. 27a PolG sind …» in § 31a PolV; …) — re-judged one by one
     («zitate», data_field_legal_basis): moved to the article that governs the Formular, or
     dropped where the field already cites the provision the line stands in (or the right one
     is not ingested). Gates: the artefact row is the recorded one (law, number, heading); each
     field is the recorded one (id, Formular, name); each target is an ingested article
     (last_checked «Gesetze-PDF …» or «verified», the proof gate of load_field_legal.py) whose
     text in the official PDF holds the recorded quote; a dropped citation never leaves a
     field without a citation.
  2. The Rechtsmittel rule that hung on such an artefact («regeln»): moved to the article that
     holds its quote (gate: the rule's quote stands in the target's PDF text).
  3. Article rows the full-text reader does not read («artikel»): the wrapped cross-reference
     lines (gate: the recorded line stands in the law's PDF text) and repealed articles (gate:
     the reader marks the number repealed, «…»). Every row: law, number and heading as
     recorded, no table refers to it any more, and the reader does not read the number as an
     article of the law. Afterwards scripts/gesetz_stand.py and scripts/kennungen.py (the
     identifiers of removed rows become «entfallen»; an identifier is never deleted).

    python3 scripts/migrate_2026_11_05b.py
"""
import json, os, re, shutil, subprocess, sys
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate
from citygov.load.ingest_laws import BYSHR, HERE, articles_text, join_hyph
from citygov.load.migrate_2026_10_05 import verweise

BELEG = os.path.join(ROOT, "quellen", "korrekturen", "artikel_artefakte_2026-11-05b.json")
BUND = os.path.normpath(os.path.join(ROOT, "..", "Gesetze", "Bund"))
_texte = {}


def gesetzestext(ref):
    """The lines of the official PDF of a law: «SHR 354.111» (cantonal) or «SR 220» (federal)."""
    if ref not in _texte:
        if ref.startswith("SHR "):
            path = os.path.normpath(os.path.join(ROOT, "..", "Gesetze", BYSHR[ref[4:]]["file"]))
        else:
            path = os.path.join(BUND, ref[3:] + ".pdf")
        out = subprocess.run(["python3", os.path.join(HERE, "extract_law.py"), path],
                             capture_output=True, text=True, timeout=180).stdout
        _texte[ref] = [ln for ln in out.splitlines() if not ln.startswith("# ")]
    return _texte[ref]


def norm(t):
    """Whitespace collapsed, a word broken at the line end («Zwangsmass- nahmengericht») joined."""
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"(\w)- (?=[a-zäöüß])", r"\1", t)


def artikeltext(ref, no):
    """The text of one article in the official PDF, normalised; None when it is not found.
    Cantonal: from the article's line to the next article the full-text reader reads.
    Federal (Fedlex PDF): from the line «Art. N» to the next line «Art. M»."""
    L = gesetzestext(ref)
    if ref.startswith("SHR "):
        arts, _ = articles_text(L)
        for k, a in enumerate(arts):
            if a["no"] == no:
                ende = arts[k + 1]["zeile"] if k + 1 < len(arts) else len(L)
                return norm(join_hyph(L[a["zeile"]:ende]))
        return None
    num = re.escape(no.split(None, 1)[1])
    start = next((i for i, ln in enumerate(L) if re.match(rf"^Art\. {num}(?![\da-z])", ln.strip())), None)
    if start is None:
        return None
    ende = next((i for i in range(start + 1, len(L)) if re.match(r"^Art\. \d+[a-z]*(\s|$)", L[i].strip())), len(L))
    return norm(join_hyph(L[start:ende]))


def ziel(c, ref, no):
    """(id, last_checked) of an ingested article of the law «SHR …» / «SR …», else None."""
    col = "l.cantonal_ref" if ref.startswith("SHR ") else "l.sr_number"
    key = ref if ref.startswith("SHR ") else ref[3:]
    r = c.execute(f"SELECT a.id, a.last_checked FROM article a JOIN law l ON l.id=a.law_id WHERE {col}=? "
                  "AND a.article_no=? AND (a.last_checked LIKE 'Gesetze-PDF%' OR a.last_checked='verified')",
                  [key, no]).fetchall()
    return tuple(r[0]) if len(r) == 1 else None


def pruefen(c, beleg):
    """[(action, args)] after every gate, and the errors."""
    tun, fehler = [], []
    zeilen = {e["article_id"]: e for e in beleg["artikel"]}
    # 1. citations
    for z in beleg["zitate"]:
        quelle = zeilen.get(z["von"])
        if quelle is None:
            fehler.append(f"Zitate von Artikel {z['von']}: die Zeile fehlt in «artikel»"); continue
        ziele = []
        for t in z["nach"]:
            hit = ziel(c, t["ref"], t["article_no"])
            if not hit:
                fehler.append(f"Ziel {t['ref']} {t['article_no']}: kein eingelesener Artikel (zuerst ingest_laws.py?)"); continue
            text = artikeltext(t["ref"], t["article_no"])
            if not text or norm(t["beleg"]) not in text:
                fehler.append(f"Ziel {t['ref']} {t['article_no']}: das Zitat «{t['beleg'][:50]}…» steht nicht im Gesetzestext")
                continue
            ziele.append(hit)
        if len(ziele) != len(z["nach"]):
            continue
        for f in z["felder"]:
            r = c.execute("SELECT form_id, name FROM data_field WHERE id=?", [f["data_field_id"]]).fetchone()
            if r is None or (r[0], r[1]) != (f["form_id"], f["name"]):
                fehler.append(f"Datenfeld {f['data_field_id']}: Formular oder Name weichen vom Beleg ab"); continue
            alt = [row[0] for row in c.execute("SELECT id FROM data_field_legal_basis WHERE data_field_id=? "
                                                "AND article_id=?", [f["data_field_id"], z["von"]])]
            if not alt:
                continue                                    # already corrected (idempotent)
            hat = {row[0] for row in c.execute("SELECT article_id FROM data_field_legal_basis WHERE data_field_id=?",
                                                [f["data_field_id"]])}
            if not ziele and not (hat - {z["von"]}):
                fehler.append(f"Datenfeld {f['data_field_id']} ({f['name']}): verlöre sein letztes Zitat"); continue
            tun.append(("zitat", (f["data_field_id"], z["von"], alt, [h for h in ziele if h[0] not in hat])))
    # 2. Rechtsmittel rules
    for g in beleg["regeln"]:
        r = c.execute("SELECT article_id, quote, frist_article_id FROM rechtsmittel_regel WHERE id=?", [g["regel_id"]]).fetchone()
        hit = ziel(c, g["nach"]["ref"], g["nach"]["article_no"])
        if r is None or not hit:
            fehler.append(f"Regel {g['regel_id']}: fehlt, oder das Ziel ist nicht eingelesen"); continue
        if r[0] == hit[0]:
            continue                                        # already corrected
        if r[0] != g["von"] or r[2] == g["von"]:
            fehler.append(f"Regel {g['regel_id']}: hängt nicht am Artikel {g['von']} wie im Beleg"); continue
        text = artikeltext(g["nach"]["ref"], g["nach"]["article_no"])
        if not text or norm(r[1]) not in text:
            fehler.append(f"Regel {g['regel_id']}: ihr Zitat steht nicht im Text von {g['nach']['article_no']}"); continue
        tun.append(("regel", (g["regel_id"], hit[0])))
    # 3. article rows
    gelesen = {}
    for e in beleg["artikel"]:
        r = c.execute("SELECT a.law_id, a.article_no, coalesce(a.heading,''), l.cantonal_ref FROM article a "
                      "JOIN law l ON l.id=a.law_id WHERE a.id=?", [e["article_id"]]).fetchone()
        if r is None:
            continue                                        # already removed (idempotent)
        if tuple(r) != (e["law_id"], e["article_no"], e["heading"], e["cantonal_ref"]):
            fehler.append(f"Artikel {e['article_id']}: Gesetz, Nummer oder Überschrift weichen vom Beleg ab"); continue
        ref = e["cantonal_ref"]
        if ref not in gelesen:
            gelesen[ref] = articles_text(gesetzestext(ref))
        arts, aufgehoben = gelesen[ref]
        if e["article_no"] in {a["no"] for a in arts}:
            fehler.append(f"Artikel {e['article_id']}: der Volltext-Leser liest «{e['article_no']}» als Artikel"); continue
        if e["art"] == "aufgehoben" and e["article_no"] not in aufgehoben:
            fehler.append(f"Artikel {e['article_id']}: «{e['article_no']}» ist im Gesetzestext nicht aufgehoben"); continue
        if e["art"] == "verweiszeile" and e["fundstelle"] not in {re.sub(r"\s+", " ", ln.strip()) for ln in gesetzestext(ref)}:
            fehler.append(f"Artikel {e['article_id']}: die Zeile «{e['fundstelle']}» steht nicht im Gesetzestext"); continue
        tun.append(("artikel", e["article_id"]))
    return tun, fehler


def anwenden(c, tun):
    n = {"zitat": 0, "regel": 0, "artikel": 0}
    for art, a in tun:
        if art == "zitat":
            did, von, alt, ziele = a
            if ziele:
                c.execute("UPDATE data_field_legal_basis SET article_id=?, last_checked=? WHERE id=?",
                          [ziele[0][0], ziele[0][1], alt[0]])
                for aid, lc in ziele[1:]:
                    c.execute("INSERT INTO data_field_legal_basis(data_field_id, article_id, citation_detail, last_checked, "
                              "relation) SELECT data_field_id, ?, citation_detail, ?, relation FROM data_field_legal_basis "
                              "WHERE id=?", [aid, lc, alt[0]])
                alt = alt[1:]
            c.executemany("DELETE FROM data_field_legal_basis WHERE id=?", [[i] for i in alt])
        elif art == "regel":
            c.execute("UPDATE rechtsmittel_regel SET article_id=? WHERE id=?", [a[1], a[0]])
        n[art] += 1
    for art, a in tun:
        if art == "artikel":
            if verweise(c, a):
                raise RuntimeError(f"Artikel {a}: wird noch zitiert ({verweise(c, a)})")
            c.execute("DELETE FROM article WHERE id=?", [a])
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
        print("1.–3. Zitate, Regeln, Einleseartefakte: 0 — nichts zu tun, citygov.db unverändert")
        return
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    try:
        n = anwenden(c, tun)                           # stops when a row of step 3 is still cited
    except RuntimeError as e:
        c.close(); os.remove(st)
        sys.exit(f"ABBRUCH — nichts geschrieben:\n  {e}")
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st)
        sys.exit("ABBRUCH — Validierung, nichts geschrieben:\n  " + "\n  ".join(errs[:10]))
    os.replace(st, DB_PATH)
    print(f"1. Zitate (data_field_legal_basis): {n['zitat']} Felder neu beurteilt\n"
          f"2. Rechtsmittel-Regeln: {n['regel']} umgehängt\n"
          f"3. Einleseartefakte und aufgehobene Artikel (article): {n['artikel']} entfernt — danach "
          "scripts/gesetz_stand.py und scripts/kennungen.py (markiert ihre Kennungen «entfallen»)")


if __name__ == "__main__":
    main()
