#!/usr/bin/env python3
"""Law titles as the official PDF prints them (correction of 2026-10-05).

The first ingest of the cantonal laws took law.title from the first line(s) of each
PDF and law.short_title from its first 40 characters. Titles that span several lines
were cut mid-phrase («Gesetz über die Raumplanung und das öffentliche»), the footnote
marker of the Rechtsbuch stayed in the name («Polizeigesetz *»), and some titles
carried the edition line («Energiegesetz Vom 16. Dezember 2024 (Stand 1. Januar
2026)»). This loader reads the title block of the PDF the articles were read from
(gesetz_stand.datei, the same file and SHA-256) and corrects only a title that is
defective in one of these ways; a complete title stays as it is.

Two steps, so that the evidence is in the repository and the apply step needs no PDF:

    /usr/local/bin/python3 scripts/load_gesetz_titel.py --lesen
        (pypdf; reads ../Gesetze/<datei>) writes quellen/korrekturen/gesetz_titel_2026-10-05.json:
        per law the title block verbatim (the lines between «Kanton Schaffhausen <SHR>» and
        «Vom <Datum>» on the first page), the file and its SHA-256, the title and short title
        before and after, and why the old one is defective
    python3 scripts/load_gesetz_titel.py
        gate + apply: staging -> validate -> swap; standard library only; a second run
        reports «unverändert» and leaves the database untouched
    python3 scripts/load_gesetz_titel.py --pruefen
        gate only, nothing written

The gate: every entry names a law whose gesetz_stand row still points at the same file
with the same SHA-256; the new title is exactly the title block joined (a line break
after a hyphen before a lower-case word is a word break; the Rechtsbuch's footnote
marker «*» is dropped); the database holds either the recorded old value (pending)
or the new one (applied) — never a third, which would mean a later loader rewrote it.
The new short title is the name in the closing parenthesis of the title block
(«(Baugesetz)»; of «(Brandschutzgesetz, BSG)» the abbreviation when it is one),
otherwise the full title of the block. Not a build step (the --lesen step needs pypdf and the law folder).
The evidence file, its reading (zeilen) and the gate (pruefen) live in citygov/domain/gesetz_titel.py,
because the integrity gate runs them; this module reads the PDFs and applies the entries.
"""
import json
import os
import re
import shutil
import sys

from citygov.core.common import DB_PATH, ROOT, connect
from citygov.domain.gesetz_titel import DATEI, MAX_ZEILEN, kurztitel, titel_aus_block, zeilen

GESETZE_DIR = os.path.normpath(os.path.join(ROOT, "..", "Gesetze"))
KOPF = re.compile(r"^Kanton Schaffhausen\s+\d{3}\.\d{3}\s*$")
VOM = re.compile(r"^[Vv]om \d")

# what makes an old title or short title defective (the reason recorded per entry)
GRUND = {
    "stand": "der Name trägt die Zeile mit Erlassdatum und Stand («Vom … (Stand …)»)",
    "fussnote": "der Name trägt die Fussnotenmarke «*» des Rechtsbuchs",
    "abgeschnitten": "der Name bricht mitten im Titel ab — die Folgezeile(n) des Titels fehlen",
    "kurz_abgeschnitten": "der Kurztitel sind die ersten 40 Zeichen des Titels",
    "kurz_allgemein": "der Kurztitel ist nur die Art des Erlasses («Gesetz», «Verordnung»)",
}


def _kern(t):
    """A title without its closing parenthesis, the edition line and the footnote marker."""
    t = re.sub(r"\s+Vom\s+\d.*$", "", t or "")
    t = re.sub(r"\s*\*(?=\s|$)", "", t)
    return re.sub(r"\s*\([^()]*\)\s*$", "", t).strip()


def defekt_titel(titel, pdf_titel):
    """[reasons] why a title is defective against the PDF's title ([] = complete)."""
    g = []
    if re.search(r"\s+Vom\s+\d", titel or ""):
        g.append("stand")
    if re.search(r"\s\*(?:\s|$)", titel or ""):
        g.append("fussnote")
    alt, neu = _kern(titel), _kern(pdf_titel)
    if alt != neu and alt and alt in neu:
        g.append("abgeschnitten")
    return g


def defekt_kurz(kurz, titel_alt, titel_abgeschnitten=False):
    if not kurz:
        return []
    g = []
    if titel_abgeschnitten and kurz.strip() and kurz.strip() in (titel_alt or ""):
        g.append("abgeschnitten")              # the short title is the cut title or a piece of it
    if re.search(r"\sVom(?:\s|$)", kurz):
        g.append("stand")
    if re.search(r"\s\*\s*$", kurz) or kurz.count("(") != kurz.count(")"):
        g.append("fussnote" if "*" in kurz else "abgeschnitten")
    if len(kurz) >= 39 and len(titel_alt or "") > len(kurz.rstrip()) and (titel_alt or "").startswith(kurz.rstrip()):
        g.append("kurz_abgeschnitten")
    if kurz.strip() in ("Gesetz", "Verordnung", "Dekret", "Vertrag"):
        g.append("kurz_allgemein")
    return sorted(set(g))


def lesen():
    """--lesen: the title block of every cantonal law's PDF -> the evidence file."""
    import hashlib
    import pypdf
    conn = connect(DB_PATH)
    eintraege, ohne = [], []
    for r in conn.execute("SELECT l.id, l.title, l.short_title, l.cantonal_ref, g.datei, g.datei_sha256 "
                          "FROM law l JOIN gesetz_stand g ON g.law_id = l.id "
                          "WHERE l.jurisdiction_level = 'cantonal' AND g.datei IS NOT NULL ORDER BY l.id"):
        pfad = os.path.join(GESETZE_DIR, r["datei"])
        if not os.path.isfile(pfad):
            ohne.append(f"{r['id']}: {r['datei']} fehlt")
            continue
        sha = hashlib.sha256(open(pfad, "rb").read()).hexdigest()
        if sha != r["datei_sha256"]:
            ohne.append(f"{r['id']}: {r['datei']} ist nicht mehr die gelesene Datei")
            continue
        zeilen = [z.strip() for z in (pypdf.PdfReader(pfad).pages[0].extract_text() or "").split("\n")]
        if not zeilen or not KOPF.match(zeilen[0]):
            ohne.append(f"{r['id']}: erste Zeile ist nicht «Kanton Schaffhausen <SHR>»")
            continue
        block = []
        for z in zeilen[1:]:
            if VOM.match(z):
                break
            block.append(z)
        else:
            block = None
        if not block or len(block) > MAX_ZEILEN:
            ohne.append(f"{r['id']}: kein Titelblock vor «Vom …»")
            continue
        neu = titel_aus_block(block)
        g_t = defekt_titel(r["title"], neu)
        g_k = defekt_kurz(r["short_title"], r["title"], "abgeschnitten" in g_t)
        if not g_t and not g_k:
            continue
        titel = neu if g_t else r["title"]
        eintraege.append({
            "law_id": r["id"], "nummer": r["cantonal_ref"], "datei": r["datei"], "sha256": sha,
            "titelblock": block,
            "titel_bisher": r["title"], "titel": titel, "grund_titel": [GRUND[x] for x in g_t],
            "kurz_bisher": r["short_title"], "kurz": kurztitel(neu) if g_k else r["short_title"],
            "grund_kurz": [GRUND[x] for x in g_k]})
    doc = {"hinweis": "Titel und Kurztitel kantonaler Gesetze, wie der Titelblock der amtlichen PDF-Datei sie druckt "
                      "(die Datei, aus der die Databank die Artikel gelesen hat: gesetz_stand.datei, gleiche "
                      "SHA-256). Korrigiert ist nur ein Name, der mitten im Titel abbricht, die Fussnotenmarke «*» "
                      "oder die Zeile «Vom … (Stand …)» trägt, sowie ein Kurztitel aus den ersten 40 Zeichen oder "
                      "nur der Art des Erlasses. Geschrieben von scripts/load_gesetz_titel.py --lesen.",
           "anwenden": "python3 scripts/load_gesetz_titel.py",
           "eintraege": eintraege}
    os.makedirs(os.path.dirname(DATEI), exist_ok=True)
    with open(DATEI, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"{len(eintraege)} Gesetze mit fehlerhaftem Titel oder Kurztitel -> {os.path.relpath(DATEI, ROOT)}")
    for x in ohne:
        print("  ohne Titelblock:", x)


def main():
    if "--lesen" in sys.argv:
        lesen()
        return
    conn = connect(DB_PATH)
    neu, alt, fehler = zeilen(conn)
    if fehler:
        print(f"ABGELEHNT ({len(fehler)}):")
        for f in fehler:
            print("  -", f)
        sys.exit(1)
    offen = [x for x in neu if tuple(conn.execute("SELECT title, short_title FROM law WHERE id=?", [x[0]]).fetchone())
             != (x[1], x[2])]
    print(f"Gesetzestitel: {len(neu)} Einträge, {len(offen)} noch anzuwenden")
    if "--pruefen" in sys.argv:
        print("Gate bestanden (nichts geschrieben).")
        return
    conn.close()
    if not offen:
        print("unverändert — die Databank trägt die korrigierten Titel bereits (nichts geschrieben).")
        return
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    for lid, t, k in offen:
        c.execute("UPDATE law SET title=?, short_title=? WHERE id=?", [t, k, lid])
    c.commit()
    from citygov.checks.validate_db import validate
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st)
        print(f"ABBRUCH — Validierung ({len(errs)}):")
        for e in errs[:30]:
            print("  -", e)
        sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"geladen: {len(offen)} Titel korrigiert -> {DB_PATH}")


if __name__ == "__main__":
    main()
