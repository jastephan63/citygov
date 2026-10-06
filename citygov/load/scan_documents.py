#!/usr/bin/env python3
"""Scan every Formular's source file for the hard digitalization facts:
does it demand a signature, can a machine fill it, and what exact bytes is it?

Writes onto form:
  file_hash             sha256 of the source file (the edition anchor)
  acroform              1 = fillable AcroForm, 0 = flat print-and-write PDF,
                        NULL = not a PDF, or its fields could not be read
  signature_requirement sig_widget | handschriftlich | keine | unbekannt
  signature_evidence    the matched line / widget name, so the verdict is checkable
  parse_error           why a file could not be inspected (kein_pdf, pypdf error)

The signature verdict is evidence-based only: a digital /Sig widget wins, then a
literal 'Unterschrift...' hit in the PDF text (first + last pages, where Swiss
forms sign), then a signature field in the curated field model; a file whose
text cannot be read stays 'unbekannt' — never guessed. Idempotent, staging swap.

file_hash is also the anchor of form_gestaltung (how the Formular looks,
scan_gestaltung.py): a row measured on a file whose hash has moved on is
removed here, in the same write, because validate_db.py refuses a stale row.
The Formular then counts as «noch nicht gemessen» until scan_gestaltung.py
has run again.

The fields come from pypdf's get_fields(). Where that call fails on a file
(a button widget without /AP /N raises KeyError), the catalog's /AcroForm
/Fields are read directly and the run names the file; a failed read is never
written as «no fields»: without a field found either way the row carries the
error and acroform stays NULL.

Needs pypdf (requirements.txt) and refuses to start under a Python without
it: a missing library must not be written onto every PDF as its parse_error.

    python3 scripts/scan_documents.py
"""
import hashlib, os, re, shutil, sys
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate

SIG_RX = re.compile(r"unterschrift|unterschreib|unterzeichn|signatur", re.I)


def _obj(x):
    """The object behind an indirect reference."""
    try:
        return x.get_object()
    except Exception:
        return x


def acroform_fields(rd):
    """(n, sig_widget) straight from the catalog's /AcroForm /Fields, without
    pypdf's get_fields(): n terminal fields (/FT own or inherited; a kid
    without /T is a widget of its field, not a field) and whether one of them
    is a /Sig field."""
    form = _obj(rd.trailer["/Root"].get("/AcroForm"))
    if not isinstance(form, dict):
        return 0, False
    found, seen = [], set()

    def walk(node, ft, depth):
        node = _obj(node)
        if not isinstance(node, dict) or id(node) in seen or depth > 40:
            return
        seen.add(id(node))
        ft = node.get("/FT", ft)
        kids = [_obj(k) for k in (_obj(node.get("/Kids")) or [])]
        sub = [k for k in kids if isinstance(k, dict) and "/T" in k]
        if sub:
            for k in sub:
                walk(k, ft, depth + 1)
        elif ft is not None:
            found.append(str(ft))

    for f in (_obj(form.get("/Fields")) or []):
        walk(f, None, 0)
    return len(found), "/Sig" in found


def scan_pdf(path, notes=None):
    """Return (acroform, sig_widget, sig_line, error). Text from first+last pages.
    A get_fields() that fails is answered from /AcroForm /Fields (said in notes)."""
    try:
        import pypdf
        rd = pypdf.PdfReader(path)
        try:
            fields = rd.get_fields() or {}
            n = len(fields)
            sigw = any((f.get("/FT") == "/Sig") for f in fields.values() if hasattr(f, "get"))
        except Exception as e:
            n, sigw = acroform_fields(rd)
            if not n:
                raise       # no field found either way: the error, not «flat»
            if notes is not None:
                notes.append(f"{type(e).__name__} {e}, {n} Felder")
        pages = list(rd.pages)
        pick = pages[:1] + pages[-3:] if len(pages) > 4 else pages
        line = None
        for p in pick:
            try:
                for ln in (p.extract_text() or "").splitlines():
                    if SIG_RX.search(ln):
                        line = " ".join(ln.split())[:120]
                        break
            except Exception:
                continue
            if line:
                break
        return (1 if n else 0), sigw, line, None
    except Exception as e:
        return None, False, None, type(e).__name__


def main():
    try:
        import pypdf  # noqa: F401
    except ImportError:
        sys.exit("ABBRUCH: scan_documents.py braucht pypdf, und dieses Python hat es nicht "
                 f"({sys.executable}).\n"
                 "  Mit einem Python starten, in dem pypdf installiert ist "
                 "(pip install -r requirements.txt).\n"
                 "  Nichts gescannt, nichts geschrieben.")
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    for col in ("file_hash TEXT", "acroform INTEGER", "signature_requirement TEXT",
                "signature_evidence TEXT", "parse_error TEXT"):
        try:
            c.execute(f"ALTER TABLE form ADD COLUMN {col}")
        except Exception:
            pass

    sig_fields = {r["form_id"] for r in c.execute(
        "SELECT DISTINCT form_id FROM data_field WHERE data_type='signature' "
        "OR name LIKE '%nterschrift%'")}
    stats = {"sig_widget": 0, "handschriftlich": 0, "keine": 0, "unbekannt": 0}
    n = flat = 0
    direkt = []     # files whose fields were read from /AcroForm /Fields
    for r in c.execute("SELECT id, source_file FROM form WHERE source_file IS NOT NULL").fetchall():
        path = os.path.join(ROOT, r["source_file"])     # repository-relative, never the cwd
        if not os.path.exists(path):
            c.execute("UPDATE form SET parse_error='datei_fehlt' WHERE id=?", [r["id"]])
            continue
        h = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if not path.lower().endswith(".pdf"):
            c.execute("UPDATE form SET file_hash=?, parse_error='kein_pdf', "
                      "signature_requirement=?, signature_evidence=? WHERE id=?",
                      [h, "handschriftlich" if r["id"] in sig_fields else "unbekannt",
                       "Signaturfeld im Feldmodell" if r["id"] in sig_fields else None, r["id"]])
            stats["handschriftlich" if r["id"] in sig_fields else "unbekannt"] += 1
            continue
        notes = []
        acro, sigw, line, err = scan_pdf(path, notes)
        direkt += [f"#{r['id']} ({x})" for x in notes]
        if err:
            # unreadable PDF: fall back to the curated field model, else honest unknown
            sr = "handschriftlich" if r["id"] in sig_fields else "unbekannt"
            ev = "Signaturfeld im Feldmodell" if r["id"] in sig_fields else None
            c.execute("UPDATE form SET file_hash=?, acroform=NULL, parse_error=?, signature_requirement=?, "
                      "signature_evidence=? WHERE id=?", [h, err, sr, ev, r["id"]])
            stats[sr] += 1
            continue
        if sigw:
            sr, ev = "sig_widget", "digitales /Sig-Feld im PDF"
        elif line:
            sr, ev = "handschriftlich", f"PDF-Text: «{line}»"
        elif r["id"] in sig_fields:
            sr, ev = "handschriftlich", "Signaturfeld im Feldmodell"
        else:
            sr, ev = "keine", None
        c.execute("UPDATE form SET file_hash=?, acroform=?, parse_error=NULL, "
                  "signature_requirement=?, signature_evidence=? WHERE id=?",
                  [h, acro, sr, ev, r["id"]])
        stats[sr] += 1
        flat += 1 if acro == 0 else 0
        n += 1
    # a measurement of the look belongs to the file it was taken from
    veraltet = 0
    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='form_gestaltung'").fetchone():
        veraltet = c.execute("DELETE FROM form_gestaltung WHERE file_hash IS NOT "
                             "(SELECT f.file_hash FROM form f WHERE f.id = form_gestaltung.form_id)").rowcount
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"gescannt: {n} PDFs ({flat} ohne AcroForm) — Unterschrift: "
          + ", ".join(f"{k} {v}" for k, v in stats.items()))
    if direkt:
        print(f"  get_fields() scheitert bei {len(direkt)} PDF — Felder direkt aus /AcroForm /Fields gelesen: "
              + ", ".join(direkt))
    if veraltet:
        print(f"  {veraltet} Zeilen in form_gestaltung entfernt (Datei geändert) — scan_gestaltung.py erneut laufen lassen")


if __name__ == "__main__":
    main()
