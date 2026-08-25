#!/usr/bin/env python3
"""Close the loop: write flow answers into the official Formular (AcroForm PDF).

Input = the form_id and an answers JSON of {"<question/field label>": "<value>", ...}
(e.g. hand-written, or adapted from the player's eCH export). Answers are mapped
to the PDF's AcroForm widgets, in order of trust:
  1. data_field.source_widgets — the widget names recorded at extraction time
  2. normalised name match: answer label vs widget name (exact first, then a
     containment match if it is unambiguous)
Unmatched answers are listed, never silently dropped; unmatched widgets stay
empty. The source PDF is never touched — output is a new file.

    python3 scripts/fill_pdf.py <form_id> <answers.json> [-o out.pdf]
    python3 scripts/fill_pdf.py <form_id> --demo          # sample answers
"""
import json, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect
import pypdf


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", s)


def main():
    fid = int(sys.argv[1])
    out = None
    for i, a in enumerate(sys.argv):
        if a == "-o":
            out = sys.argv[i + 1]
    c = connect(DB_PATH)
    fm = c.execute("SELECT title, source_file FROM form WHERE id=?", [fid]).fetchone()
    if not fm:
        print(f"form #{fid} unbekannt"); sys.exit(1)
    src = fm["source_file"]
    reader = pypdf.PdfReader(src)
    widgets = reader.get_fields() or {}
    if not widgets:
        print(f"'{fm['title']}' hat keine AcroForm-Felder — PDF-Befüllung nicht möglich "
              f"(Flachdruck; hier würde ein Overlay-Renderer greifen)."); sys.exit(2)

    # answers
    if "--demo" in sys.argv:
        answers = {}
        for d in c.execute("SELECT name, data_type, allowed_values FROM data_field "
                           "WHERE form_id=? ORDER BY ord", [fid]):
            if d["data_type"] in ("attachment", "signature"):
                continue
            v = {"date": "12.04.1990", "number": "1", "boolean": "Ja"}.get(d["data_type"], "Muster")
            try:
                av = json.loads(d["allowed_values"]) if d["allowed_values"] else []
                if av:
                    v = str(av[0])
            except Exception:
                pass
            answers[d["name"]] = v
        answers.update({"Name": "Muster", "Vorname": "Anna", "Wohnort": "8200 Schaffhausen",
                        "Telefon": "052 632 00 00", "E-Mail": "anna.muster@example.ch",
                        "Geburtsdatum": "12.04.1990"})
    else:
        answers = json.load(open(sys.argv[2], encoding="utf-8"))

    # data_field -> recorded widget names
    dfw = {}
    for d in c.execute("SELECT name, source_widgets FROM data_field WHERE form_id=?", [fid]):
        try:
            ws = json.loads(d["source_widgets"]) if d["source_widgets"] else []
        except Exception:
            ws = []
        dfw[norm(d["name"])] = [w for w in ws if isinstance(w, str)]
    c.close()

    wnorm = {norm(k): k for k in widgets}
    fill, unmatched = {}, []
    for label, val in answers.items():
        if val in (None, ""):
            continue
        nk = norm(label)
        hit = None
        for w in dfw.get(nk, []):                    # 1. recorded widgets
            if norm(w) in wnorm:
                hit = wnorm[norm(w)]; break
        if not hit and nk in wnorm:                   # 2. direct name match
            hit = wnorm[nk]
        if not hit:                                   # 2b. containment match
            cands = [v for k2, v in wnorm.items() if nk and (nk in k2 or k2 in nk) and len(k2) > 2]
            if len(cands) == 1:
                hit = cands[0]
        if hit:
            fill[hit] = str(val)
        else:
            unmatched.append(label)

    writer = pypdf.PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, fill)
    out = out or os.path.join(ROOT, "logs", f"ausgefuellt-form{fid}.pdf")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        writer.write(fh)
    print(f"'{fm['title']}' → {out}")
    print(f"  {len(fill)}/{len(widgets)} AcroForm-Felder befüllt, "
          f"{len(unmatched)} Antworten ohne Widget-Treffer")
    for u in unmatched[:8]:
        print(f"    ohne Treffer: {u}")


if __name__ == "__main__":
    main()
