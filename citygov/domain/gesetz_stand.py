#!/usr/bin/env python3
"""Record, per law, the edition («Stand») the databank read its articles from —
table gesetz_stand — from evidence only.

Evidence, in the order it counts:
  einlesen   recorded when the articles were read:
             artikel_vermerk  the «(Stand …)» in article.last_checked (ingest_laws.py
                              writes 'Gesetze-PDF SHR <n> (Stand …)'), one entry per value,
                              with how many articles (and cited articles) carry it
             gesetz_vermerk   law.last_checked «(Stand …)» and law.source_note «(Stand …)»
                              or «Fassung d.m.yyyy» (the two federal laws ingested by hand)
  pdf_datei  the file the loaders read, as it is today:
             pdf_kopf         the «(Stand …)» / «(Stand am …)» printed in the head of the PDF
                              (cantonal: the file ingest_laws.py and extract_quotes.py take from
                              inventory/gesetze_index.json — the last entry of an SHR number, or
                              the file law.source_note names; federal: ../Gesetze/Bund/<SR>.pdf,
                              which extract_quotes.py reads the article texts from)
             index_titel      the «(Stand …)» in the title inventory/gesetze_index.json recorded
                              from the same file when the index was built
  The file is tied to the row by its SHA-256, and a text comparison says whether it is the
  file the stored article texts came from: texte_zitiert cited articles with a stored
  text_excerpt, texte_gefunden of them occur in the file (at least one window of 40
  letters, compared on letters only, so line breaks, hyphenation and footnote counters do
  not matter), texte_vollstaendig occur in every window.

Status
  belegt       every source that names a Stand names the same day -> stand = that day;
               stand_quelle 'einlesen' when a reading-time record names it, else 'pdf_datei'
  widerspruch  the sources name different days -> stand NULL, grund names them
  unbekannt    no source names one -> stand NULL, grund says why
Nothing is inferred from file names: the parts after the SHR number ('-3-1', '-1-2')
are not documented, so they are kept as the file name only.

Idempotent: every run derives every row anew and compares it with the stored one
(erhoben_am apart). Only rows that differ are written, with today's day in erhoben_am;
when none differs the run prints «nichts zu tun» and leaves citygov.db untouched.
Otherwise copy to citygov.db.staging -> write -> validate_db.validate() and pruefen()
-> swap. The table definition comes from schema.sql (created when missing, rebuilt with
the same rows when its wording changed). Without PDF text (no macOS PDFKit) the run
stops instead of writing rows that lack the file evidence.

The gate pruefen(conn) -> list[str] holds the invariants of gesetz_stand and
gesetz_stand_pruefung; validate_db.validate() runs it. A row whose basis (fingerprint
of the law row and its articles' last_checked and cited texts) differs from the
databank is stale: the gate then does not compare its reading-time evidence, the export
shows it as «veraltet», and the next run of this script renews it — so a re-ingest of a
law never blocks another loader.

    python3 scripts/gesetz_stand.py               # derive, compare, write what differs
    python3 scripts/gesetz_stand.py --trocken     # derive and report, write nothing
    python3 scripts/gesetz_stand.py --zeigen <law_id|SHR|SR>   # one stored row
    python3 scripts/gesetz_stand.py --pruefen     # run the gate on citygov.db
(the command line and the write side, erheben() and main(), are citygov/load/gesetz_stand_cli.py:
they read the PDFs through load/extract_law.py; this module is the read side and the gate)
"""
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata

from citygov.core.common import ROOT, SCHEMA_PATH, INVENTORY_DIR

TABELLE = "gesetz_stand"
PRUEFTABELLE = "gesetz_stand_pruefung"
SPALTEN = ["law_id", "stand", "status", "stand_quelle", "datei", "datei_herkunft", "datei_sha256",
           "texte_zitiert", "texte_gefunden", "texte_vollstaendig", "belege", "grund", "basis", "erhoben_am"]
STATUS = ("belegt", "widerspruch", "unbekannt")
STAND_QUELLEN = ("einlesen", "pdf_datei")
HERKUNFT = ("gesetzessammlung", "rechtsbuch_api", "fedlex")
BELEG_QUELLEN = ("artikel_vermerk", "gesetz_vermerk", "pdf_kopf", "index_titel")
EINLESEN = ("artikel_vermerk", "gesetz_vermerk")
ERGEBNISSE = ("aktuell", "neuer_stand", "aufgehoben", "stand_unbekannt", "nicht_gefunden",
              "nicht_pruefbar", "fehler", "unklar")
PRUEF_QUELLEN = ("rechtsbuch", "fedlex", "keine")
GESETZE_DIR = os.path.normpath(os.path.join(ROOT, "..", "Gesetze"))
FENSTER = 40                      # letters per window of the text comparison
KOPFZEILEN = 25                   # non-empty lines of the PDF head searched for the Stand

MONATE = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7,
          "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12}
_STAND = re.compile(r"\(Stand(?: am)?\s+([^)]+)\)")
_FASSUNG = re.compile(r"Fassung\s+(\d{1,2}\.\d{1,2}\.\d{4})")
_DATEI = re.compile(r"Gesetze/([\w.\-]+\.pdf)")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---- dates -----------------------------------------------------------------------
def iso_datum(text):
    """'1. Januar 2026', '1.1.2022', '01.01.2026' or '2026-01-01' -> '2026-01-01';
    None when the text is no complete, valid calendar day."""
    s = unicodedata.normalize("NFC", (text or "").strip()).rstrip(".")
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        j, mo, t = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.fullmatch(r"(\d{1,2})\.\s*([A-Za-zÄäÖöÜü]+)\s+(\d{4})", s)
        if m and m.group(2).lower() in MONATE:
            t, mo, j = int(m.group(1)), MONATE[m.group(2).lower()], int(m.group(3))
        else:
            m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
            if not m:
                return None
            t, mo, j = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime.date(j, mo, t).isoformat()
    except ValueError:
        return None


def ist_iso(s):
    return isinstance(s, str) and bool(_ISO.match(s)) and iso_datum(s) == s


# ---- what the databank says about a law --------------------------------------------
def nummer(law):
    """(kind, number) of a law row: ('shr', '120.100') for cantonal law, ('sr', '831.10') for
    federal law, (None, None) without an official number. The level decides: some cantonal
    rows carry their SHR number in sr_number too."""
    if law["jurisdiction_level"] == "federal" and law["sr_number"]:
        return "sr", law["sr_number"].strip()
    if law["jurisdiction_level"] == "cantonal" and law["cantonal_ref"]:
        return "shr", law["cantonal_ref"].replace("SHR", "").strip()
    return None, None


def zitierte_artikel(conn):
    """Ids of the articles a data field cites (read once per run; data_field_legal_basis has
    no index on article_id, so a per-article EXISTS would scan it again and again)."""
    return {r[0] for r in conn.execute("SELECT DISTINCT article_id FROM data_field_legal_basis")}


def _zitierte_texte(conn, law_id, zitiert=None):
    """Cited articles of the law with a stored text (as extract_quotes.py stores them)."""
    zitiert = zitierte_artikel(conn) if zitiert is None else zitiert
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT id, text_excerpt FROM article WHERE law_id=? AND text_excerpt IS NOT NULL "
        "AND length(text_excerpt) > 40 ORDER BY id", [law_id]) if r[0] in zitiert]


def fingerabdruck(conn, law_id, zitiert=None):
    """SHA-256 over what this script reads from the databank for one law: the law row's
    last_checked and source_note, every article's last_checked, the cited texts. A row
    whose basis differs from this value is stale."""
    law = conn.execute("SELECT last_checked, source_note FROM law WHERE id=?", [law_id]).fetchone()
    if law is None:
        return None
    arts = conn.execute("SELECT id, last_checked FROM article WHERE law_id=? ORDER BY id", [law_id]).fetchall()
    texte = [[r[0], hashlib.sha256((r[1] or "").encode("utf-8")).hexdigest()]
             for r in _zitierte_texte(conn, law_id, zitiert)]
    stoff = json.dumps([law[0], law[1], [[a[0], a[1]] for a in arts], texte], ensure_ascii=False)
    return hashlib.sha256(stoff.encode("utf-8")).hexdigest()


def vermerke(conn, law_id, zitiert=None):
    """The reading-time evidence of one law (artikel_vermerk, gesetz_vermerk entries), in a
    fixed order. The ONE derivation, used by the loader and by the gate."""
    out = []
    zitiert = zitierte_artikel(conn) if zitiert is None else zitiert
    gruppen = {}
    for aid, lc in conn.execute("SELECT id, last_checked FROM article WHERE law_id=? ORDER BY id", [law_id]):
        m = _STAND.search(lc or "")
        roh = m.group(0) if m else None
        st = iso_datum(m.group(1)) if m else None
        if m and st is None:
            st = "?"                                         # a Stand that is not a calendar day
        g = gruppen.setdefault(st, {"roh": set(), "n_artikel": 0, "n_zitiert": 0})
        if roh:
            g["roh"].add(roh)
        g["n_artikel"] += 1
        g["n_zitiert"] += aid in zitiert
    for st in sorted(gruppen, key=lambda k: (k is None, k or "")):
        g = gruppen[st]
        out.append({"quelle": "artikel_vermerk",
                    "stand": None if st in (None, "?") else st,
                    "roh": " | ".join(sorted(g["roh"])) if g["roh"] else "ohne Stand-Vermerk",
                    "n_artikel": g["n_artikel"], "n_zitiert": g["n_zitiert"]})
    law = conn.execute("SELECT last_checked, source_note FROM law WHERE id=?", [law_id]).fetchone()
    for feld, text in (("law.last_checked", law[0]), ("law.source_note", law[1])):
        m = _STAND.search(text or "") or _FASSUNG.search(text or "")
        if not m:
            continue
        roh = m.group(0)
        if feld == "law.source_note":                       # keep the retrieval day the note states
            ab = re.search(r"abgerufen\s+(\d{4}-\d{2}-\d{2})", text or "")
            if ab:
                roh += f", abgerufen {ab.group(1)}"
        out.append({"quelle": "gesetz_vermerk", "stand": iso_datum(m.group(1)), "roh": f"{feld}: {roh}"})
    return out


# ---- the file the loaders read -------------------------------------------------------
def gesetzes_index():
    """inventory/gesetze_index.json as {shr: entry}; the LAST entry of a number wins, as in
    ingest_laws.py and extract_quotes.py."""
    with open(os.path.join(INVENTORY_DIR, "gesetze_index.json"), encoding="utf-8") as fh:
        return {g.get("shr"): g for g in json.load(fh)}


def datei_waehlen(law, index):
    """(relative file, herkunft, index entry or None, reason when there is none)."""
    art, nr = nummer(law)
    if art == "sr":
        rel = f"Bund/{nr}.pdf"
        if os.path.isfile(os.path.join(GESETZE_DIR, rel)):
            return rel, "fedlex", None, None
        return None, None, None, f"keine Datei Bund/{nr}.pdf"
    if art == "shr":
        m = _DATEI.search(law["source_note"] or "")
        eintrag = index.get(nr)
        if m:                                                # the file the ingest note names
            rel = m.group(1)
            eintrag = eintrag if eintrag and eintrag.get("file") == rel else None
        elif eintrag:
            rel = eintrag["file"]
        else:
            return None, None, None, f"SHR {nr} fehlt in inventory/gesetze_index.json"
        if not os.path.isfile(os.path.join(GESETZE_DIR, rel)):
            return None, None, None, f"Datei {rel} fehlt"
        return rel, ("rechtsbuch_api" if rel.endswith("-rechtsbuch.de.pdf") else "gesetzessammlung"), eintrag, None
    return None, None, None, "kein Erlass mit amtlicher Nummer"


def buchstaben(text):
    """Letters only, lower case, NFC, ß as ss — line breaks, hyphens, digits (footnote
    counters) and spaces do not take part in the comparison."""
    s = unicodedata.normalize("NFC", (text or "").lower()).replace("ß", "ss")
    return re.sub(r"[^a-zäöüéèàâêîôûç]+", "", s)


def fenster(text):
    """Up to six windows of FENSTER letters spread over the text (the whole text when shorter)."""
    e = buchstaben(text)
    if len(e) <= FENSTER:
        return [e] if e else []
    schritt = max(FENSTER, (len(e) - FENSTER) // 5)
    return [e[i:i + FENSTER] for i in range(0, len(e) - FENSTER + 1, schritt)][:6]


def texte_abgleichen(texte, pdf_text):
    """(cited texts, found, found completely) of the stored excerpts in the file text."""
    voll = buchstaben(pdf_text)
    n = gef = ganz = 0
    for _aid, excerpt in texte:
        w = fenster(excerpt)
        if not w:
            continue
        n += 1
        treffer = sum(1 for x in w if x in voll)
        gef += treffer > 0
        ganz += treffer == len(w)
    return n, gef, ganz


def kopf_stand(pdf_text):
    """(iso or None, raw) of the Stand printed in the head of a law PDF."""
    zeilen = [z.strip() for z in pdf_text.splitlines() if z.strip()][:KOPFZEILEN]
    m = _STAND.search(" ".join(zeilen))
    if not m:
        return None, "kein Stand im Kopf der Datei"
    return iso_datum(m.group(1)), m.group(0)


# ---- one row -------------------------------------------------------------------------
def zeile(conn, law, index, pdf_texte, zitiert):
    """The row of one law as a dict (erhoben_am left empty). pdf_texte: {relative file: text}."""
    belege = vermerke(conn, law["id"], zitiert)
    rel, herkunft, eintrag, ohne = datei_waehlen(law, index)
    sha = n = gef = ganz = None
    gruende = []
    if rel:
        pfad = os.path.join(GESETZE_DIR, rel)
        with open(pfad, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        text = pdf_texte.get(rel) or ""
        if text:
            st, roh = kopf_stand(text)
            belege.append({"quelle": "pdf_kopf", "stand": st, "roh": roh, "datei": rel})
            n, gef, ganz = texte_abgleichen(_zitierte_texte(conn, law["id"], zitiert), text)
        else:
            belege.append({"quelle": "pdf_kopf", "stand": None, "roh": "Text der Datei nicht lesbar", "datei": rel})
        if eintrag:
            m = _STAND.search(eintrag.get("title") or "")
            if m:
                belege.append({"quelle": "index_titel", "stand": iso_datum(m.group(1)), "roh": m.group(0)})
    else:
        gruende.append(ohne)
    werte = sorted({b["stand"] for b in belege if b.get("stand")})
    if len(werte) == 1:
        stand, status, grund = werte[0], "belegt", None
        quelle = "einlesen" if any(b["quelle"] in EINLESEN and b.get("stand") == stand for b in belege) else "pdf_datei"
    elif len(werte) > 1:
        stand, status, quelle = None, "widerspruch", None
        grund = "Die Quellen nennen verschiedene Stände: " + "; ".join(
            f"{b['quelle']} {b['stand']} ({b['roh']})" for b in belege if b.get("stand"))
    else:
        stand, status, quelle = None, "unbekannt", None
        unlesbar = [b["roh"] for b in belege if b["quelle"] in EINLESEN and "(Stand" in b["roh"] and not b.get("stand")]
        if unlesbar:
            gruende.append("Stand-Vermerk beim Einlesen ist kein lesbarer Kalendertag: " + " | ".join(unlesbar))
        else:
            gruende.append("beim Einlesen kein Stand vermerkt")
        for b in belege:
            if b["quelle"] == "pdf_kopf" and not b.get("stand"):
                gruende.append(b["roh"])
        grund = "; ".join(gruende) or "keine Quelle nennt einen Stand"
    return {"law_id": law["id"], "stand": stand, "status": status, "stand_quelle": quelle,
            "datei": rel, "datei_herkunft": herkunft, "datei_sha256": sha,
            "texte_zitiert": n, "texte_gefunden": gef, "texte_vollstaendig": ganz,
            "belege": json.dumps(belege, ensure_ascii=False, sort_keys=True),
            "grund": grund, "basis": fingerabdruck(conn, law["id"], zitiert), "erhoben_am": ""}


# ---- the gate ----------------------------------------------------------------------------
def _has(conn, table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [table]).fetchone())


def _json(text, typ):
    try:
        v = json.loads(text)
    except (TypeError, ValueError):
        return None
    return v if isinstance(v, typ) else None


def _anzahl_neuere(details, gelesen, tag):
    """Editions in force after `gelesen` up to `tag`, from the edition list a check stored."""
    tage = {v.get("in_kraft") for v in (details.get("versionen") or []) if isinstance(v, dict)}
    return sum(1 for d in tage if ist_iso(d) and gelesen < d <= tag)


def pruefen(conn):
    """Invariants of gesetz_stand and gesetz_stand_pruefung; list of error texts (empty = valid).
    A missing table is no error (not loaded yet); a missing row neither («noch nicht erhoben»)."""
    fehler = []
    conn_rf = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        if _has(conn, TABELLE):
            fehler += _pruefen_stand(conn)
        if _has(conn, PRUEFTABELLE):
            fehler += _pruefen_pruefung(conn)
    finally:
        conn.row_factory = conn_rf
    return fehler


def _pruefen_stand(conn):
    fehler = []
    zitiert = zitierte_artikel(conn)
    for r in conn.execute(f"SELECT * FROM {TABELLE} ORDER BY law_id").fetchall():
        wo = f"gesetz_stand law {r['law_id']}"
        if r["status"] not in STATUS:
            fehler.append(f"{wo}: status {r['status']!r} not in {STATUS}"); continue
        if r["stand_quelle"] is not None and r["stand_quelle"] not in STAND_QUELLEN:
            fehler.append(f"{wo}: stand_quelle {r['stand_quelle']!r} not in {STAND_QUELLEN}")
        if r["datei_herkunft"] is not None and r["datei_herkunft"] not in HERKUNFT:
            fehler.append(f"{wo}: datei_herkunft {r['datei_herkunft']!r} not in {HERKUNFT}")
        if (r["stand"] is None) != (r["status"] != "belegt"):
            fehler.append(f"{wo}: stand {r['stand']!r} does not fit status {r['status']!r}")
        if r["stand"] is not None and not ist_iso(r["stand"]):
            fehler.append(f"{wo}: stand {r['stand']!r} is no ISO calendar day")
        if (r["stand_quelle"] is None) != (r["stand"] is None):
            fehler.append(f"{wo}: stand_quelle {r['stand_quelle']!r} without a stand or a stand without its source")
        if r["status"] != "belegt" and not (r["grund"] or "").strip():
            fehler.append(f"{wo}: status {r['status']} without grund")
        if r["status"] == "belegt" and r["grund"]:
            fehler.append(f"{wo}: status belegt carries a grund")
        if not ist_iso(r["erhoben_am"]):
            fehler.append(f"{wo}: erhoben_am {r['erhoben_am']!r} is no ISO day")
        if (r["datei"] is None) != (r["datei_herkunft"] is None) or (r["datei"] is None) != (r["datei_sha256"] is None):
            fehler.append(f"{wo}: datei, datei_herkunft and datei_sha256 must be set together")
        if r["datei_sha256"] is not None and not re.fullmatch(r"[0-9a-f]{64}", r["datei_sha256"]):
            fehler.append(f"{wo}: datei_sha256 is no SHA-256")
        if r["datei"] is not None and (r["datei"].startswith(("/", "..")) or ".." in r["datei"].split("/")):
            fehler.append(f"{wo}: datei {r['datei']!r} must be relative to the law folder")
        n, g, v = r["texte_zitiert"], r["texte_gefunden"], r["texte_vollstaendig"]
        if (n is None) != (g is None) or (n is None) != (v is None):
            fehler.append(f"{wo}: texte_zitiert/gefunden/vollstaendig must be set together")
        elif n is not None and not (0 <= v <= g <= n):
            fehler.append(f"{wo}: text counts {v} <= {g} <= {n} do not hold")
        belege = _json(r["belege"], list)
        if belege is None:
            fehler.append(f"{wo}: belege is no JSON list"); continue
        werte = set()
        for b in belege:
            if not isinstance(b, dict) or b.get("quelle") not in BELEG_QUELLEN:
                fehler.append(f"{wo}: beleg {b!r} has no known quelle"); continue
            if b.get("stand") is not None:
                if not ist_iso(b["stand"]):
                    fehler.append(f"{wo}: beleg {b['quelle']} stand {b['stand']!r} is no ISO day")
                werte.add(b["stand"])
            if not (b.get("roh") or "").strip():
                fehler.append(f"{wo}: beleg {b['quelle']} without its raw text")
        soll = {1: "belegt", 0: "unbekannt"}.get(len(werte), "widerspruch")
        if r["status"] != soll:
            fehler.append(f"{wo}: status {r['status']} but the evidence names {sorted(werte)} (would be {soll})")
        if r["status"] == "belegt" and werte != {r["stand"]}:
            fehler.append(f"{wo}: stand {r['stand']} is not the day its evidence names {sorted(werte)}")
        if r["stand"] is not None:
            einlesen = any(b.get("quelle") in EINLESEN and b.get("stand") == r["stand"] for b in belege if isinstance(b, dict))
            if r["stand_quelle"] != ("einlesen" if einlesen else "pdf_datei"):
                fehler.append(f"{wo}: stand_quelle {r['stand_quelle']} does not fit the evidence")
        if r["datei"] is not None and not any(isinstance(b, dict) and b.get("quelle") == "pdf_kopf"
                                              and b.get("datei") == r["datei"] for b in belege):
            fehler.append(f"{wo}: the file {r['datei']} has no pdf_kopf entry")
        # the reading-time evidence against the databank — unless the row is stale
        if r["basis"] == fingerabdruck(conn, r["law_id"], zitiert):
            ist = [b for b in belege if isinstance(b, dict) and b.get("quelle") in EINLESEN]
            if json.dumps(ist, sort_keys=True, ensure_ascii=False) != json.dumps(
                    vermerke(conn, r["law_id"], zitiert), sort_keys=True, ensure_ascii=False):
                fehler.append(f"{wo}: the reading-time evidence differs from article/law last_checked and source_note")
            if n is not None and n > len(_zitierte_texte(conn, r["law_id"], zitiert)):
                fehler.append(f"{wo}: texte_zitiert {n} exceeds the cited articles with a text")
    return fehler


def urllib_unquote(s):
    from urllib.parse import unquote_plus
    return unquote_plus(s)


def _pruefen_pruefung(conn):
    fehler = []
    laws = {r["id"]: r for r in conn.execute("SELECT id, jurisdiction_level, sr_number, cantonal_ref FROM law")}
    for r in conn.execute(f"SELECT * FROM {PRUEFTABELLE} ORDER BY law_id, geprueft_am"):
        wo = f"gesetz_stand_pruefung law {r['law_id']} {r['geprueft_am']}"
        law = laws.get(r["law_id"])
        if law is None:
            continue                                          # the FK check names it
        if r["quelle"] not in PRUEF_QUELLEN:
            fehler.append(f"{wo}: quelle {r['quelle']!r} not in {PRUEF_QUELLEN}"); continue
        if r["ergebnis"] not in ERGEBNISSE:
            fehler.append(f"{wo}: ergebnis {r['ergebnis']!r} not in {ERGEBNISSE}"); continue
        tag = r["geprueft_am"]
        if not ist_iso(tag):
            fehler.append(f"{wo}: geprueft_am is no ISO day"); continue
        art, nr = nummer(law)
        soll = {"shr": "rechtsbuch", "sr": "fedlex"}.get(art, "keine")
        if r["quelle"] != soll:
            fehler.append(f"{wo}: quelle {r['quelle']} but the law asks for {soll}")
        if r["quelle"] == "rechtsbuch" and r["abfrage"] != f"https://rechtsbuch.sh.ch/api/de/texts_of_law/{nr}":
            fehler.append(f"{wo}: abfrage is not the Rechtsbuch address of SHR {nr}")
        if r["quelle"] == "fedlex" and not ((r["abfrage"] or "").startswith("https://fedlex.data.admin.ch/sparqlendpoint?")
                                            and f"%22{nr}%22" in (r["abfrage"] or "")):
            fehler.append(f"{wo}: abfrage is not a Fedlex query for SR {nr}")
        if r["quelle"] == "keine" and (r["abfrage"] is not None or r["ergebnis"] != "nicht_pruefbar"):
            fehler.append(f"{wo}: without a source only ergebnis nicht_pruefbar and no abfrage")
        for k in ("stand_gelesen", "stand_aktuell"):
            if r[k] is not None and not ist_iso(r[k]):
                fehler.append(f"{wo}: {k} {r[k]!r} is no ISO day")
        if r["stand_aktuell"] and ist_iso(r["stand_aktuell"]) and r["stand_aktuell"] > tag:
            fehler.append(f"{wo}: stand_aktuell {r['stand_aktuell']} lies after the check day")
        details = _json(r["details"], dict)
        kuenftig = _json(r["kuenftig"], list)
        if details is None:
            fehler.append(f"{wo}: details is no JSON object"); continue
        if kuenftig is None:
            fehler.append(f"{wo}: kuenftig is no JSON list"); continue
        for k in kuenftig:
            if not isinstance(k, dict) or k.get("art") not in ("fassung", "aufhebung") or not ist_iso(k.get("stand")) \
                    or k["stand"] <= tag:
                fehler.append(f"{wo}: kuenftig entry {k!r} is not a later edition or repeal"); break
        # Fedlex: a later edition counts only when it is published (Fedlex also lists announced
        # consolidations without a publication date or a text): a check made with the query of
        # 2026-10-05 (it asks for jolux:publicationDate) shows a publication date in
        # details.versionen for every kuenftig edition. An older check could not tell; it is
        # superseded by the next run of scripts/check_gesetz_stand.py, never an error here
        if r["quelle"] == "fedlex" and kuenftig and "publicationDate" in urllib_unquote(r["abfrage"] or ""):
            pub = {v.get("fassung"): v.get("veroeffentlicht") for v in details.get("versionen") or []
                   if isinstance(v, dict)}
            ohne = [k.get("fassung") for k in kuenftig if k.get("art") == "fassung" and not pub.get(k.get("fassung"))]
            if ohne:
                fehler.append(f"{wo}: kuenftig lists editions without a publication date: {ohne[:2]}")
        e, g, a = r["ergebnis"], r["stand_gelesen"], r["stand_aktuell"]
        if e not in ("aktuell", "neuer_stand") and not (r["grund"] or "").strip():
            fehler.append(f"{wo}: ergebnis {e} without grund")
        if e == "aktuell" and not (g and a and g == a and r["n_neuere"] == 0):
            fehler.append(f"{wo}: aktuell needs stand_gelesen = stand_aktuell and n_neuere 0")
        if e == "neuer_stand" and not (g and a and g < a and (r["n_neuere"] or 0) >= 1):
            fehler.append(f"{wo}: neuer_stand needs stand_gelesen < stand_aktuell and n_neuere >= 1")
        if e == "stand_unbekannt" and (g is not None or a is None):
            fehler.append(f"{wo}: stand_unbekannt needs no stand_gelesen and a stand_aktuell")
        if e in ("aktuell", "neuer_stand") and r["n_neuere"] != _anzahl_neuere(details, g, tag):
            fehler.append(f"{wo}: n_neuere {r['n_neuere']} differs from the stored edition list "
                          f"({_anzahl_neuere(details, g, tag)})")
        fa, fg = r["fassung_aktuell"], r["fassung_gelesen"]
        if r["quelle"] == "rechtsbuch":
            for k, f in (("fassung_aktuell", fa), ("fassung_gelesen", fg)):
                if f is not None and not re.fullmatch(r"https://rechtsbuch\.sh\.ch/api/de/versions/\d+/pdf_file", f):
                    fehler.append(f"{wo}: {k} {f!r} is no Rechtsbuch version address")
        if r["quelle"] == "fedlex":
            for k, f, d in (("fassung_aktuell", fa, a), ("fassung_gelesen", fg, g)):
                if f is None:
                    continue
                m = re.fullmatch(r"https://fedlex\.data\.admin\.ch/eli/cc/[\w/.-]+/(\d{8})", f)
                if not m or d is None or m.group(1) != d.replace("-", ""):
                    fehler.append(f"{wo}: {k} {f!r} is not the Fedlex consolidation of {d}")
        if e in ("aktuell", "neuer_stand") and fa is None:
            fehler.append(f"{wo}: {e} without the address of the current edition")
    return fehler


# ---- loader ------------------------------------------------------------------------------
def tabelle_sql():
    """The CREATE TABLE statement of gesetz_stand as schema.sql documents it."""
    scratch = sqlite3.connect(":memory:")
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        scratch.executescript(fh.read())
    row = scratch.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", [TABELLE]).fetchone()
    scratch.close()
    if not row:
        sys.exit(f"ABBRUCH: schema.sql kennt die Tabelle {TABELLE} nicht.")
    return row[0]


def gespeichert(conn):
    """({law_id: row dict}, stored CREATE TABLE statement) or (None, None) without the table."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", [TABELLE]).fetchone()
    if not row:
        return None, None
    return {r["law_id"]: dict(r) for r in conn.execute(f"SELECT * FROM {TABELLE}")}, row[0]


def _ohne_tag(z):
    return {k: v for k, v in z.items() if k != "erhoben_am"}


def zusammenfassung(neu, conn):
    """Plain-German summary lines of the derived rows."""
    zit = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT a.law_id, COUNT(*), COUNT(DISTINCT d.data_field_id) FROM data_field_legal_basis d "
        "JOIN article a ON a.id=d.article_id GROUP BY a.law_id")}
    lvl = {r[0]: r[1] for r in conn.execute("SELECT id, jurisdiction_level FROM law")}
    def zaehle(ids):
        out = {}
        for i in ids:
            z = neu[i]
            k = z["status"] if z["status"] != "belegt" else f"belegt ({z['stand_quelle']})"
            out[k] = out.get(k, 0) + 1
        return ", ".join(f"{k} {v}" for k, v in sorted(out.items()))
    alle = sorted(neu)
    zitiert = [i for i in alle if i in zit]
    zeilen = [f"Gesetze: {len(alle)} — {zaehle(alle)}",
              f"  davon von Datenfeldern zitiert: {len(zitiert)} — {zaehle(zitiert)}"]
    for ebene in ("cantonal", "federal", "communal"):
        ids = [i for i in zitiert if lvl.get(i) == ebene]
        if ids:
            n_zit = sum(zit[i][0] for i in ids)
            n_st = sum(zit[i][0] for i in ids if neu[i]["stand"])
            zeilen.append(f"  {ebene}: {len(ids)} zitierte Gesetze, {n_zit} Zitate, davon {n_st} mit belegtem Stand")
    n = sum(z["texte_zitiert"] or 0 for z in neu.values())
    g = sum(z["texte_gefunden"] or 0 for z in neu.values())
    v = sum(z["texte_vollstaendig"] or 0 for z in neu.values())
    zeilen.append(f"Textabgleich: {g} von {n} zitierten Artikeltexten in der Datei wiedergefunden "
                  f"({v} in jedem Fenster)")
    return zeilen
