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
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, ROOT, connect

GESETZE_DIR = os.path.normpath(os.path.join(ROOT, "..", "Gesetze"))
DATEI = os.path.join(ROOT, "quellen", "korrekturen", "gesetz_titel_2026-10-05.json")
KOPF = re.compile(r"^Kanton Schaffhausen\s+\d{3}\.\d{3}\s*$")
VOM = re.compile(r"^[Vv]om \d")
MAX_ZEILEN = 12

# what makes an old title or short title defective (the reason recorded per entry)
GRUND = {
    "stand": "der Name trägt die Zeile mit Erlassdatum und Stand («Vom … (Stand …)»)",
    "fussnote": "der Name trägt die Fussnotenmarke «*» des Rechtsbuchs",
    "abgeschnitten": "der Name bricht mitten im Titel ab — die Folgezeile(n) des Titels fehlen",
    "kurz_abgeschnitten": "der Kurztitel sind die ersten 40 Zeichen des Titels",
    "kurz_allgemein": "der Kurztitel ist nur die Art des Erlasses («Gesetz», «Verordnung»)",
}


def titel_aus_block(zeilen):
    """The title as one line: a break after «-» before a lower-case word that is not
    «und/oder/bzw.» is a word break; the footnote marker «*» is dropped."""
    out = ""
    for z in zeilen:
        z = z.strip()
        if not z:
            continue
        if out.endswith("-") and re.match(r"[a-zäöü]", z) and not re.match(r"(?:und|oder)\b|bzw\.", z):
            out = out[:-1] + z
        else:
            out = (out + " " + z) if out else z
    out = re.sub(r"\s*\*(?=\s|$|\))", "", out)
    return re.sub(r"\s+", " ", out).strip()


def _kern(t):
    """A title without its closing parenthesis, the edition line and the footnote marker."""
    t = re.sub(r"\s+Vom\s+\d.*$", "", t or "")
    t = re.sub(r"\s*\*(?=\s|$)", "", t)
    return re.sub(r"\s*\([^()]*\)\s*$", "", t).strip()


def kurztitel(titel):
    """The short title of a corrected title: the closing parenthesis («Baugesetz»), of a
    pair («Brandschutzgesetz, BSG») the abbreviation when it is one, else the full title."""
    m = re.search(r"\(([^()]+)\)\s*$", titel)
    if not m:
        return titel
    teile = [p.strip() for p in m.group(1).split(",") if p.strip()]
    letzt = teile[-1]
    if len(teile) > 1 and re.fullmatch(r"[A-ZÄÖÜ][A-Za-zÄÖÜäöü0-9-]*", letzt) and \
            len(re.findall(r"[A-ZÄÖÜ]", letzt)) >= 2:
        return letzt
    return teile[0]


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


def zeilen(conn):
    """([(law_id, titel, kurz)], [(law_id, titel_bisher, kurz_bisher)], errors) from the evidence file."""
    try:
        doc = json.load(open(DATEI, encoding="utf-8"))
    except (OSError, ValueError) as ex:
        return [], [], [f"{os.path.relpath(DATEI, ROOT)}: nicht lesbar ({ex})"]
    neu, alt, fehler = [], [], []
    for e in doc.get("eintraege") or []:
        tag = f"Gesetz {e.get('law_id')}"
        g = conn.execute("SELECT datei, datei_sha256 FROM gesetz_stand WHERE law_id=?", [e.get("law_id")]).fetchone()
        if not g or (g["datei"], g["datei_sha256"]) != (e.get("datei"), e.get("sha256")):
            fehler.append(f"{tag}: gelesen wurde nicht {e.get('datei')} mit dieser SHA-256")
            continue
        block = e.get("titelblock") or []
        if not block or len(block) > MAX_ZEILEN:
            fehler.append(f"{tag}: ohne Titelblock")
            continue
        soll = titel_aus_block(block)
        if e.get("grund_titel") and e.get("titel") != soll:
            fehler.append(f"{tag}: der Titel «{e.get('titel')}» ist nicht der Titelblock «{soll}»")
        if not e.get("grund_titel") and e.get("titel") != e.get("titel_bisher"):
            fehler.append(f"{tag}: Titel geändert ohne Grund")
        if e.get("grund_kurz") and e.get("kurz") != kurztitel(soll):
            fehler.append(f"{tag}: der Kurztitel «{e.get('kurz')}» folgt nicht aus dem Titelblock")
        if not e.get("grund_kurz") and e.get("kurz") != e.get("kurz_bisher"):
            fehler.append(f"{tag}: Kurztitel geändert ohne Grund")
        for t in (e.get("titel"), e.get("kurz")):
            if t and (re.search(r"\s+Vom\s+\d", t) or "*" in t or "ß" in t):
                fehler.append(f"{tag}: «{t}» trägt noch Stand, Fussnote oder «ß»")
        neu.append((e["law_id"], e["titel"], e["kurz"]))
        alt.append((e["law_id"], e["titel_bisher"], e["kurz_bisher"]))
    for (lid, t, k), (_, ta, ka) in zip(neu, alt):
        r = conn.execute("SELECT title, short_title FROM law WHERE id=?", [lid]).fetchone()
        if not r:
            fehler.append(f"Gesetz {lid}: fehlt")
        elif (r["title"], r["short_title"]) not in ((t, k), (ta, ka)):
            fehler.append(f"Gesetz {lid}: trägt weder den bisherigen noch den korrigierten Namen "
                          f"(«{r['title']}» / «{r['short_title']}») — ein anderer Lader hat ihn geändert")
    return neu, alt, fehler


def pruefen(conn):
    """The gate for validate_db: every entry of the evidence file is either pending or
    applied (errors only; [] without the law layer)."""
    if not os.path.exists(DATEI):
        return []
    return zeilen(conn)[2]


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
    from validate_db import validate
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
