#!/usr/bin/env python3
"""Classify source files as Formular / calculation_tool / helper (convention 7).

Classification happens BEFORE modelling: only files classified 'formular' enter
the reconciliation pipeline. Calculation tools (Excel formulas) are documented but
not modelled as forms; helper documents (Wegleitung/Merkblatt) are catalogued only.

This produces a *proposal* (inventory/<dir>.classified.json) for human review — the
heuristics are a starting point, not the final word. Review it, correct doc_type,
then fold the entries into a service proposal's `documents` list (or commit as-is).

    python3 scripts/classify.py forms/
    python3 scripts/classify.py "../Verwaltung/Finanzdepartement /Steuerverwaltung"
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import INVENTORY_DIR, ROOT

# strong helper signals — these win even over form-ish words (e.g. "Vollzugshilfe
# Baubewilligung" contains 'bewilligung' but is guidance, not a form).
HELPER  = re.compile(r"merkblatt|wegleitung|leitfaden|anleitung|richtlinie|erl[aä]uter|"
                     r"checkliste|factsheet|infoblatt|\binfo\b|broschure|broschüre|flyer|"
                     r"hinweis|tipps|vorschriften|vollzugshilfe|schulungsunterlagen|"
                     r"ablaufschema|bewilligungskriterien|bewilligungsablauf|"
                     r"beilagen|reglement|musterarbeitsvertrag|mustervertrag", re.I)
FORM    = re.compile(r"formular|gesuch|antrag|anmeld|\bmeldung\b|meldeform|bewilligung|"
                     r"vollmacht|erkl[aä]rung|deklaration|bestellformular|fragebogen|"
                     r"bewerbung|nachweis|vertrag", re.I)
CALC    = re.compile(r"rechner|berechnung|kalkul|tarif|abrechnungsformular", re.I)


def classify(name):
    base = os.path.splitext(name)[0]
    ext = os.path.splitext(name)[1].lower()
    is_sheet = ext in (".xlsx", ".xlsm", ".xls", ".csv")
    # strong helper signal wins first (conv 7): guidance is not a form even if its
    # title contains 'Gesuch'/'Bewilligung' (e.g. 'Vollzugshilfe ...bewilligung').
    if HELPER.search(base):
        return "helper", "filename indicates guidance (Wegleitung/Merkblatt/Vollzugshilfe)"
    # Abrechnungsformular*.xlsx etc. are genuine forms even though they're sheets.
    if FORM.search(base) and not (is_sheet and CALC.search(base) and "formular" not in base.lower()):
        return "formular", "filename indicates a citizen-fillable form"
    if is_sheet:
        if CALC.search(base) or True:   # default: a spreadsheet is a calc tool unless named a form
            return "calculation_tool", "spreadsheet — likely implements a formula; confirm"
    if HELPER.search(base):
        return "helper", "filename indicates guidance (Wegleitung/Merkblatt)"
    return "helper", "UNCLEAR — defaulted to helper; REVIEW (do not assume a form)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    args = ap.parse_args()
    if not os.path.isdir(args.directory):
        print(f"not a directory: {args.directory}", file=sys.stderr); sys.exit(2)

    items = []
    for fn in sorted(os.listdir(args.directory)):
        full = os.path.join(args.directory, fn)
        if not os.path.isfile(full) or fn.startswith(".") or fn.lower().endswith((".md", ".txt")):
            continue
        if os.path.splitext(fn)[1].lower() not in (".pdf", ".xlsx", ".xlsm", ".xls", ".csv", ".doc", ".docx"):
            continue
        doc_type, note = classify(fn)
        items.append({"source_file": os.path.relpath(full, ROOT), "file_name": fn,
                      "doc_type": doc_type, "classification_note": note, "is_this_form": False})

    os.makedirs(INVENTORY_DIR, exist_ok=True)
    tag = re.sub(r"[^a-z0-9]+", "-", os.path.basename(os.path.normpath(args.directory)).lower()).strip("-") or "root"
    out = os.path.join(INVENTORY_DIR, f"{tag}.classified.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"_comment": "PROPOSED classifications (conv 7) — REVIEW before use. "
                   "Only doc_type='formular' should be modelled as a form.",
                   "source_dir": args.directory, "documents": items}, fh,
                  ensure_ascii=False, indent=2)
    from collections import Counter
    c = Counter(i["doc_type"] for i in items)
    print(f"wrote {out}  ({len(items)} files: " +
          ", ".join(f"{k}={v}" for k, v in sorted(c.items())) + ")")


if __name__ == "__main__":
    main()
