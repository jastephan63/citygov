#!/usr/bin/env python3
"""Measure how every Formular with a file looks and is presented, and store
the facts in table form_gestaltung: fonts, sizes, colours, the accessibility
facts the file carries, the phone numbers and e-mail types it prints, edition
mark, page numbers, sender. Facts only — a value that cannot be measured is
NULL with the reason in `hinweise`; the comparison across Formulare and every
verdict are computed elsewhere, from these rows.

    python3 scripts/scan_gestaltung.py                  # every Formular with a file
    python3 scripts/scan_gestaltung.py --only 12 345    # only these form ids
    python3 scripts/scan_gestaltung.py --dry            # print the rows as JSON, write nothing

Needs pypdf (requirements.txt) and refuses to start under a Python without
it: half a scan would look like «not measured» for 348 PDFs. ./build.sh does
not run this script; it reads the stored rows through gestaltung_export.py,
which imports only gestaltung_text.py (standard library), so the plain build
keeps working without pypdf.

Who measures what
  pdf    gestaltung_pdf.messen()          -> messart 'pdf' | 'pdf_bild' (a scan)
  word   gestaltung_office.messen_docx()  -> 'word' | 'nicht_messbar' (.doc, damaged)
  excel  gestaltung_office.messen_xlsx()  -> 'excel' | 'nicht_messbar' (.xls, damaged)
  The module docstrings define every value of the profil. Each module gets
  service.dienststelle of the Formular's service (elemente.absender asks
  whether page 1 names it) and form.title, the name of the Formular
  (barrierefrei.titel_art asks whether the document title names it). The 42
  eFormulare have no file and get no row.

One row per Formular
  file_hash   sha256 of the measured file. It must equal form.file_hash (the
              databank's edition anchor, written by scan_documents.py): when
              the file on disk is a different one, the Formular is NOT
              measured and is listed as a failure — run scan_documents.py
              first (it takes the new hash and removes the row measured on
              the old file), then this script again. This script never
              writes to table form.
  methode     METHODE below. Raise it whenever a measuring module changes
              what it returns for an unchanged file. ('gestaltung-1' was the
              first released method; 'gestaltung-2' followed the acceptance
              check of 2026-10-04: linked words carry a link colour, a drawn
              logo in the head of page 1 is no accent, a dashed line paints
              its dashes only, struck-through text is not read, a letterhead
              in two pieces explains its phone line, the canton counts as
              sender only where it stands like one, a year alone in a footer
              is an edition mark, two flags more in `barrierefrei`.)
  profil      the module's profile as compact JSON, keys in the module's
              order; its top-level keys are validate_db.GESTALTUNG_KEYS.
  scalar columns (messart, seiten, hauptschrift, grundgroesse, akzentfarbe,
              pdf_tags, hinweise) repeat profil values through the one mapping
              validate_db.gestaltung_spalten(); hinweise is NULL when the
              measurement names no limitation.

One step between module and row (the only place where the stored profil
differs from what messen() returns): an e-mail address inside the document
title is reduced to «…@domain» — addresses are never stored, and that rule
wins over «titles verbatim», as it does for the phone quotes in
gestaltung_text.py. A hinweis says so on the row. A profile that still holds
an address anywhere, lacks a key or names a messart its file type cannot
have is not written; the Formular is listed as a failure. So is a Word or
Excel file that the module gives up on with «unerwarteter Aufbau»: that is
the trace of an error in the measuring code or of a file it does not
understand, and neither may pass as a quiet 'nicht_messbar'.

Idempotent
  Every run measures anew and compares with the stored rows: the same file,
  the same Dienststelle, the same name of the Formular and the same METHODE
  give a byte-identical row. Only rows that differ are written. When none
  differs the run prints «nichts zu tun» and leaves citygov.db untouched (no
  staging copy, no swap). Otherwise: copy to citygov.db.staging -> write ->
  validate_db.validate() -> swap. When the table definition in schema.sql has
  changed in its wording (a column comment), the table is rebuilt with the
  same rows in that write, so that the databank documents itself as
  schema.sql does.
  A full run also removes rows whose Formular no longer has a file; a failed
  measurement keeps the stored row while it still belongs to the current
  file (a stale row never survives, validate_db.py refuses it).
  Whenever a run writes a row, it also writes the day into table meta (key
  'gestaltung_stand', ISO date): the comparison layer shows it as the date of
  the measurement. A run that changes nothing leaves the date as it is.

Before measuring, the self-tests of the three measuring modules are run
(they take well under a second): gestaltung_pdf.py leans on how pypdf calls
its text hooks, and a pypdf that behaves differently must stop the scan, not
shift the figures.

Exit status: 0 = done (also «nichts zu tun»), 1 = at least one Formular
could not be measured (the others are written) or the run was refused.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from common import ROOT, DB_PATH, SCHEMA_PATH, connect
from validate_db import validate, gestaltung_spalten, GESTALTUNG_KEYS, GESTALTUNG_MESSART
import gestaltung_text                 # standard library only: the key of the measurement's date in table meta

METHODE = "gestaltung-2"
TABELLE = "form_gestaltung"
SPALTEN = ("form_id", "file_hash", "messart", "methode", "seiten", "hauptschrift", "grundgroesse",
           "akzentfarbe", "pdf_tags", "profil", "hinweise")
MODULE = ("gestaltung_text.py", "gestaltung_pdf.py", "gestaltung_office.py")
MESSARTEN = ("pdf", "pdf_bild", "word", "excel", "nicht_messbar")

# an e-mail address that is still spelled out («…@domain» is the stored form)
_ADRESSE = re.compile(r"[^\s@…«»<>()\[\]{},;:\"']+@[^\s@«»<>()\[\]{},;:\"']+\.[A-Za-z]{2,}")
H_TITEL = ("Der Dokumenttitel enthält eine E-Mail-Adresse; sie ist hier auf «…@Domain» gekürzt "
           "(Adressen werden nicht gespeichert).")


class Abbruch(Exception):
    """One Formular cannot be measured; the text is shown in the summary."""


def pypdf_version():
    """The version of pypdf, or stop: without it no PDF can be measured."""
    try:
        import pypdf
    except ImportError:
        sys.exit("ABBRUCH: scan_gestaltung.py braucht pypdf, und dieses Python hat es nicht "
                 f"({sys.executable}).\n"
                 "  Mit einem Python starten, in dem pypdf installiert ist "
                 "(pip install -r requirements.txt).\n"
                 "  Nichts gemessen, nichts geschrieben.")
    return getattr(pypdf, "__version__", "?")


def selbsttests():
    """Run the self-test of each measuring module with this interpreter; stop when one fails."""
    for name in MODULE:
        lauf = subprocess.run([sys.executable, os.path.join(HIER, name)], capture_output=True, text=True)
        if lauf.returncode != 0 or "checks passed" not in lauf.stdout or "skipped" in lauf.stdout:
            sys.exit(f"ABBRUCH: der Selbsttest von {name} schlägt fehl — nichts gemessen, nichts geschrieben.\n"
                     + (lauf.stdout + lauf.stderr).strip()[-1500:])


def formulare(conn):
    """Every Formular with a file: id, file, type, the databank's hash, the Dienststelle."""
    return conn.execute(
        "SELECT f.id, f.source_file, f.file_type, f.file_hash, f.title, s.dienststelle "
        "FROM form f LEFT JOIN service s ON s.id = f.service_id "
        "WHERE f.source_file IS NOT NULL AND f.source_file != '' ORDER BY f.id").fetchall()


def ohne_adressen(profil):
    """The profil as it is stored: an e-mail address in the document title reduced to «…@domain»."""
    titel = profil["barrierefrei"]["titel"]
    if titel and _ADRESSE.search(titel):
        profil = dict(profil, barrierefrei=dict(profil["barrierefrei"]), hinweise=list(profil["hinweise"]))
        profil["barrierefrei"]["titel"] = _ADRESSE.sub(lambda m: "…@" + m.group(0).split("@", 1)[1], titel)
        profil["hinweise"].append(H_TITEL)
    return profil


def messen(form):
    """(row, profil) for one Formular; raises Abbruch with the reason when it cannot be measured."""
    import gestaltung_pdf
    import gestaltung_office
    pfad = os.path.join(ROOT, form["source_file"])          # repository-relative, never the cwd
    if not os.path.isfile(pfad):
        raise Abbruch("Datei fehlt")
    with open(pfad, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    if sha != form["file_hash"]:
        raise Abbruch("die Datei ist nicht die, deren Hash in form.file_hash steht — zuerst scan_documents.py")
    funktion = {"pdf": gestaltung_pdf.messen, "word": gestaltung_office.messen_docx,
                "excel": gestaltung_office.messen_xlsx}.get(form["file_type"])
    if funktion is None:
        raise Abbruch(f"für file_type «{form['file_type']}» gibt es keine Messung")
    try:
        profil = funktion(pfad, form["dienststelle"], form["title"])
    except Exception as e:                                   # a bug in a module must not stop the other files
        raise Abbruch(f"Messung abgebrochen ({type(e).__name__}: {str(e)[:120]})")
    if not isinstance(profil, dict) or set(profil) != set(GESTALTUNG_KEYS):
        raise Abbruch("das Profil hat nicht die vereinbarten Schlüssel")
    if any("unerwarteter Aufbau" in h for h in profil["hinweise"]):
        raise Abbruch("das Messmodul kommt mit dem Aufbau der Datei nicht zurecht (" + profil["hinweise"][0] + ")")
    if profil["messart"] not in GESTALTUNG_MESSART[form["file_type"]]:
        raise Abbruch(f"messart «{profil['messart']}» passt nicht zu file_type «{form['file_type']}»")
    try:
        profil = ohne_adressen(profil)
        text = json.dumps(profil, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        text.encode("utf-8")
        spalten = gestaltung_spalten(profil)
    except (TypeError, ValueError, KeyError, AttributeError) as e:
        raise Abbruch(f"das Profil lässt sich nicht speichern ({type(e).__name__})")
    if _ADRESSE.search(text):
        raise Abbruch("das Profil enthält eine ausgeschriebene E-Mail-Adresse")
    zeile = dict(spalten, form_id=form["id"], file_hash=sha, methode=METHODE, profil=text)
    return tuple(zeile[k] for k in SPALTEN), profil


def tabelle_sql():
    """The CREATE TABLE statement of form_gestaltung as schema.sql documents it (the one definition)."""
    scratch = sqlite3.connect(":memory:")
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        scratch.executescript(fh.read())
    row = scratch.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", [TABELLE]).fetchone()
    scratch.close()
    if not row:
        sys.exit(f"ABBRUCH: schema.sql kennt die Tabelle {TABELLE} nicht.")
    return row[0]


def gespeichert(conn):
    """({form_id: row tuple} of the stored rows, the stored CREATE TABLE statement);
    (None, None) when the table does not exist yet."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", [TABELLE]).fetchone()
    if not row:
        return None, None
    return {r["form_id"]: tuple(r[k] for k in SPALTEN)
            for r in conn.execute(f"SELECT {', '.join(SPALTEN)} FROM {TABELLE}")}, row[0]


def main():
    ap = argparse.ArgumentParser(description="Gestaltung der Formulare messen (Tabelle form_gestaltung).")
    ap.add_argument("--only", nargs="+", type=int, metavar="FORM_ID", help="nur diese Formulare messen")
    ap.add_argument("--dry", action="store_true", help="die Zeilen als JSON ausgeben, nichts schreiben")
    args = ap.parse_args()
    aus = sys.stderr if args.dry else sys.stdout            # --dry: stdout carries the JSON only

    version = pypdf_version()
    selbsttests()
    if not os.path.isfile(DB_PATH):
        sys.exit(f"ABBRUCH: keine Databank unter {DB_PATH}")

    conn = connect(DB_PATH)
    alle = formulare(conn)
    alt, ddl_alt = gespeichert(conn)
    ohne_datei = conn.execute("SELECT COUNT(*) FROM form WHERE source_file IS NULL OR source_file = ''").fetchone()[0]
    hash_db = {f["id"]: f["file_hash"] for f in alle}
    conn.close()
    tabelle_fehlt = alt is None
    alt = alt or {}
    ddl = tabelle_sql()
    ddl_anders = not tabelle_fehlt and ddl_alt != ddl      # schema.sql words the table differently (a comment)

    auswahl = alle
    if args.only:
        bekannt = {f["id"] for f in alle}
        fremd = sorted(set(args.only) - bekannt)
        if fremd:
            sys.exit(f"ABBRUCH: kein Formular mit Datei unter der Nummer {', '.join(map(str, fremd))} "
                     "(eFormulare haben keine Datei und werden nicht gemessen).")
        auswahl = [f for f in alle if f["id"] in set(args.only)]

    neu, fehler, profile = {}, [], {}
    for f in auswahl:
        try:
            neu[f["id"]], profile[f["id"]] = messen(f)
        except Abbruch as e:
            fehler.append((f["id"], f["source_file"], str(e)))

    if args.dry:
        namen = {f["id"]: f["source_file"] for f in alle}
        json.dump([dict(zip(SPALTEN, z), source_file=namen[fid], profil=profile[fid],
                        hinweise=profile[fid]["hinweise"]) for fid, z in neu.items()],
                  sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")

    # what differs from the stored rows
    dazu = [fid for fid in neu if fid not in alt]
    anders = [fid for fid in neu if fid in alt and alt[fid] != neu[fid]]
    gleich = [fid for fid in neu if fid in alt and alt[fid] == neu[fid]]
    weg = set()
    if not args.only:                                        # a full run: rows of Formulare without a file
        weg |= set(alt) - {f["id"] for f in alle}
    for fid, _datei, _grund in fehler:                       # not measured now: a stale row must not stay
        if fid in alt and alt[fid][SPALTEN.index("file_hash")] != hash_db[fid]:
            weg.add(fid)

    je_art = {m: 0 for m in MESSARTEN}
    for z in neu.values():
        je_art[z[SPALTEN.index("messart")]] += 1
    print(f"Gestaltung gemessen (Methode {METHODE}, pypdf {version}): {len(neu)} von {len(auswahl)} Formularen"
          + (f" (Auswahl; {len(alle)} haben eine Datei)" if args.only else " mit Datei")
          + f"; {ohne_datei} eFormulare ohne Datei werden nicht gemessen", file=aus)
    print("  Messart: " + ", ".join(f"{m} {n}" for m, n in je_art.items()), file=aus)
    print(f"  Zeilen: {len(dazu)} neu, {len(anders)} geändert, {len(gleich)} unverändert, {len(weg)} entfernt",
          file=aus)
    print(f"  Fehler: {len(fehler)}", file=aus)
    for fid, datei, grund in fehler:
        print(f"    Formular {fid} ({datei}): {grund}", file=aus)

    if args.dry:
        print("  --dry: nichts geschrieben", file=aus)
    elif not (dazu or anders or weg or ddl_anders):
        print("nichts zu tun — citygov.db bleibt unverändert")
    else:
        st = DB_PATH + ".staging"
        if os.path.exists(st):
            os.remove(st)
        shutil.copy2(DB_PATH, st)
        c = connect(st)
        if tabelle_fehlt:
            c.execute(ddl)
        elif ddl_anders:                                     # same columns, new wording: rebuild with the same rows
            c.execute(f"ALTER TABLE {TABELLE} RENAME TO {TABELLE}_alt")
            c.execute(ddl)
            c.execute(f"INSERT INTO {TABELLE} ({', '.join(SPALTEN)}) SELECT {', '.join(SPALTEN)} FROM {TABELLE}_alt")
            c.execute(f"DROP TABLE {TABELLE}_alt")
            print(f"  Tabellendefinition von {TABELLE} aus schema.sql übernommen (Zeilen unverändert)")
        for fid in sorted(weg):
            c.execute(f"DELETE FROM {TABELLE} WHERE form_id=?", [fid])
        for fid in sorted(dazu + anders):
            c.execute(f"INSERT OR REPLACE INTO {TABELLE} ({', '.join(SPALTEN)}) "
                      f"VALUES ({', '.join('?' * len(SPALTEN))})", neu[fid])
        if dazu or anders or weg:                            # rows changed: this is the day of the measurement
            c.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                      [gestaltung_text.META_STAND, datetime.date.today().isoformat()])
        c.commit()
        errs = validate(c)
        n = c.execute(f"SELECT COUNT(*) FROM {TABELLE}").fetchone()[0]
        c.close()
        if errs:
            os.remove(st)
            print("ABORT:", *errs[:5], sep="\n  ")
            sys.exit(1)
        os.replace(st, DB_PATH)
        print(f"geschrieben: {TABELLE} hat jetzt {n} Zeilen")
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
