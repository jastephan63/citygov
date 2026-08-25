#!/usr/bin/env python3
"""Extract a Formular's ACTUAL fields, independently of any law.

Reads one file from forms/ and writes proposals/<slug>.extracted.json — a
skeleton with the form and its extracted fields populated, and the law side
(laws / requirements / service_requirements / field_mappings) left EMPTY for a
human to model. This is
the same shape commit_proposal.py consumes; the worked example is a hand-authored
instance of it.

Field extraction:
  * PDF with an AcroForm  -> interactive fields via pypdf (label, type, options)
  * Excel (.xlsx/.xlsm)   -> candidate labels via openpyxl
  * otherwise             -> empty fields + a note; fill in by reading the form.

Offline by default: pypdf / openpyxl are imported lazily. If missing, the script
still emits a valid skeleton and tells you what to `pip install`. It never fetches
anything and never decides which service the form serves — that is a human call
made by reading the content (form content beats form title, convention 1).

    python3 scripts/extract_form.py forms/some-form.pdf [--slug my-service]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PROPOSALS_DIR, ROOT


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "form"


def extract_pdf(path):
    """Return (fields, note). fields = list of dicts."""
    try:
        import pypdf  # noqa
    except ImportError:
        return [], ("pypdf not installed — run `pip install pypdf` to extract PDF "
                    "AcroForm fields; meanwhile fill form_fields by hand.")
    from pypdf import PdfReader
    reader = PdfReader(path)
    acro = reader.get_fields() or {}
    fields, order = [], 0
    TYPE = {"/Tx": "text", "/Btn": "checkbox", "/Ch": "select", "/Sig": "signature"}
    for name, f in acro.items():
        order += 1
        states = f.get("/_States_")
        fields.append({
            "ref": f"f_{slugify(str(name))}",
            "field_key": slugify(str(name)),
            "label": str(name),
            "section": None,
            "field_type": TYPE.get(f.get("/FT"), "text"),
            "options": [s for s in states if s != "/Off"] if states else None,
            "required": False,
            "raw_order": order,
            "notes": "extracted from PDF AcroForm; verify label against printed form",
        })
    note = (f"{len(fields)} interactive field(s) extracted." if fields else
            "no AcroForm fields found (flat PDF) — read the form and add fields by hand.")
    return fields, note


def extract_xlsx(path):
    try:
        import openpyxl  # noqa
    except ImportError:
        return [], ("openpyxl not installed — run `pip install openpyxl`; meanwhile "
                    "fill form_fields by hand. NOTE: many .xlsx files are calculation "
                    "tools, not Formulare (convention 7) — classify before modelling.")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    fields, order = [], 0
    for row in ws.iter_rows(values_only=True):
        for cell in row:
            if isinstance(cell, str) and 2 <= len(cell.strip()) <= 60:
                order += 1
                lab = cell.strip()
                fields.append({
                    "ref": f"f_{slugify(lab)}_{order}", "field_key": f"{slugify(lab)}_{order}",
                    "label": lab, "section": ws.title, "field_type": "text",
                    "required": False, "raw_order": order,
                    "notes": "candidate label from spreadsheet cell; verify"})
            if order >= 200:
                break
    return fields, (f"{len(fields)} candidate label(s) from spreadsheet — REVIEW: "
                    f"confirm this is a Formular and not a calculation tool (conv 7).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--slug", help="service/form slug (default: from filename)")
    args = ap.parse_args()

    path = args.file
    if not os.path.exists(path):
        print(f"no such file: {path}", file=sys.stderr); sys.exit(2)

    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        fields, note = extract_pdf(path); ftype = "pdf"
    elif ext in (".xlsx", ".xlsm", ".xls"):
        fields, note = extract_xlsx(path); ftype = "excel"
    else:
        fields, note, ftype = [], f"unsupported extension {ext}", ext.lstrip(".")

    base = os.path.splitext(os.path.basename(path))[0]
    slug = args.slug or slugify(base)
    rel = os.path.relpath(path, ROOT)

    skeleton = {
        "_comment": f"AUTO-EXTRACTED SKELETON for {rel}. {note} "
                    "Form side is populated; LAW side is empty. Read the form CONTENT "
                    "to decide which service it really serves (conv 1), then add laws, "
                    "requirements, service_requirements, and run propose_mapping.py.",
        "service": {"slug": slug, "name": f"TODO: service for {base}",
                    "dienststelle": None, "department": None, "description": None},
        "laws": [], "requirements": [], "service_requirements": [],
        "form": {"slug": f"{slug}-form", "title": base, "actual_purpose": None,
                 "title_content_mismatch": False, "mismatch_note": None,
                 "source_file": rel, "file_type": ftype,
                 "publisher_dienststelle": None, "last_extracted": "auto"},
        "form_fields": fields,
        "field_mappings": [],
        "documents": [{"source_file": rel, "file_name": os.path.basename(path),
                       "doc_type": "formular", "is_this_form": True,
                       "classification_note": "VERIFY classification (conv 7) before commit."}],
        "findings": [],
    }
    os.makedirs(PROPOSALS_DIR, exist_ok=True)
    out = os.path.join(PROPOSALS_DIR, f"{slug}.extracted.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(skeleton, fh, ensure_ascii=False, indent=2)
    print(f"wrote {out}")
    print(f"  {note}")
    print("  next: model the law side, then `propose_mapping.py`, then `commit_proposal.py`.")


if __name__ == "__main__":
    main()
