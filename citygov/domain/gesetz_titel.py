"""Law titles as the official PDF prints them: the evidence file and its gate.

The half of the title correction of 2026-10-05 that the loader and the integrity gate
share (load/load_gesetz_titel.py describes the correction, the evidence file and its
two steps): zeilen() reads quellen/korrekturen/gesetz_titel_2026-10-05.json and checks
every entry against the title block it records and against the databank; pruefen() is
the gate validate_db runs on every staging copy (through citygov.domain.gates); the
loader's --lesen step builds the entries with titel_aus_block() and kurztitel(). Moved
unchanged from load/load_gesetz_titel.py. Standard library only, nothing written.
"""
import json
import os
import re

from citygov.core.common import ROOT

DATEI = os.path.join(ROOT, "quellen", "korrekturen", "gesetz_titel_2026-10-05.json")
MAX_ZEILEN = 12


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
