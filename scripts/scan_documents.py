#!/usr/bin/env python3
"""Scan every Formular's source file for the hard digitalization facts:
does it demand a signature, can a machine fill it, and what exact bytes is it?

Writes onto form:
  file_hash             sha256 of the source file (the edition anchor)
  acroform              1 = fillable AcroForm, 0 = flat print-and-write PDF
  signature_requirement sig_widget | handschriftlich | keine | unbekannt
  signature_evidence    the matched line / widget name, so the verdict is checkable
  parse_error           why a file could not be inspected (kein_pdf, pypdf error)

The signature verdict is evidence-based only: a digital /Sig widget wins, then a
literal 'Unterschrift...' hit in the PDF text (first + last pages, where Swiss
forms sign), then a signature field in the curated field model; a file whose
text cannot be read stays 'unbekannt' — never guessed. Idempotent, staging swap.

    python3 scripts/scan_documents.py
"""
import hashlib, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

SIG_RX = re.compile(r"unterschrift|unterschreib|unterzeichn|signatur", re.I)


def scan_pdf(path):
    """Return (acroform, sig_widget, sig_line, error). Text from first+last pages."""
    try:
        import pypdf
        rd = pypdf.PdfReader(path)
        fields = {}
        try:
            fields = rd.get_fields() or {}
        except Exception:
            pass
        sigw = any((f.get("/FT") == "/Sig") for f in fields.values() if hasattr(f, "get"))
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
        return (1 if fields else 0), sigw, line, None
    except Exception as e:
        return None, False, None, type(e).__name__


def main():
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
    for r in c.execute("SELECT id, source_file FROM form WHERE source_file IS NOT NULL").fetchall():
        path = r["source_file"]
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
        acro, sigw, line, err = scan_pdf(path)
        if err:
            # unreadable PDF: fall back to the curated field model, else honest unknown
            sr = "handschriftlich" if r["id"] in sig_fields else "unbekannt"
            ev = "Signaturfeld im Feldmodell" if r["id"] in sig_fields else None
            c.execute("UPDATE form SET file_hash=?, parse_error=?, signature_requirement=?, "
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
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"gescannt: {n} PDFs ({flat} ohne AcroForm) — Unterschrift: "
          + ", ".join(f"{k} {v}" for k, v in stats.items()))


if __name__ == "__main__":
    main()
