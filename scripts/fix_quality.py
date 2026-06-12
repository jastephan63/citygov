#!/usr/bin/env python3
"""Targeted quality pass: re-derive ONLY the weak document titles and field labels
from the original PDFs, keeping good ones untouched (conv 9 safe: staging->swap).

  * Title: the most prominent (largest-font) heading on page 1 that reads like a
    form name (skips authority headers, emails, 'Seite x von y / Version' footers).
  * Field label: for AcroForm fields whose name is numeric/blank, the printed text
    immediately to the LEFT (same line) or just ABOVE the field widget.
A new value is accepted only if it is clearly better; otherwise the item is left
as-is and written to logs/quality_review.txt for a human.

    python3 scripts/fix_quality.py [--apply]   (default: dry-run report)
"""
import os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, LOGS_DIR, connect
from validate_db import validate

AUTH = re.compile(r"eidgen|departement\b|bundesamt|staatssekretariat|kanton schaffhausen|"
                  r"^amt f[üu]r|@|https?:|www\.|seite \d+ von|version:|\.docx?|\.pdf|^\[", re.I)
FORMW = re.compile(r"gesuch|antrag|anmeldung|formular|\bmeldung|erkl[äa]rung|bewilligung|"
                   r"deklaration|nachweis|vollmacht|bescheinigung|bestellung", re.I)
def realwords(t): return len(re.findall(r"[A-Za-zÄÖÜäöü]{3,}", t or ""))

def is_bad_title(t):
    return (not t) or realwords(t) < 2 or AUTH.search(t) or re.match(r"^[\W\d]", t or "") \
        or len(t) < 5
def is_bad_label(l):
    return (not l) or len(l.strip()) < 3 or l.strip().isdigit() \
        or re.match(r"^[a-z]{1,2}\d*$|^kontrollk|^toggle|^text\d|^check ?box|^feld|^\W+$", l or "", re.I)

def font_title(path):
    try:
        from pypdf import PdfReader
        r = PdfReader(path); lines = {}
        def v(t, cm, tm, font, size):
            t = t.strip()
            if not t: return
            sz = round((size or 0) * abs(tm[0] or 1), 1); y = round(tm[5])
            e = lines.setdefault(y, [0, ""]); e[0] = max(e[0], sz); e[1] = (e[1] + " " + t).strip()
        r.pages[0].extract_text(visitor_text=v)
    except Exception:
        return None
    cand = [(sz, re.sub(r"\s+", " ", txt).strip()) for sz, txt in lines.values()
            if realwords(txt) >= 2 and not AUTH.search(txt) and 6 <= len(txt) <= 110]
    if not cand: return None
    cand.sort(key=lambda x: -x[0]); top = [t for s, t in cand if s >= cand[0][0] * 0.8]
    return next((t for t in top if FORMW.search(t)), top[0])

def positional_labels(path):
    """{acro_field_name: label} from text near each widget (numeric fields only)."""
    out = {}
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        for pg in r.pages:
            words = []
            def v(t, cm, tm, font, size):
                t = t.strip()
                if t: words.append((round(tm[5]), round(tm[4]), t))
            try: pg.extract_text(visitor_text=v)
            except Exception: pass
            for a in (pg.get("/Annots") or []):
                try: o = a.get_object()
                except Exception: continue
                if o.get("/Subtype") != "/Widget": continue
                nm = o.get("/T"); rect = o.get("/Rect")
                if not (nm and rect): continue
                nm = str(nm)
                if not (nm.isdigit() or re.match(r"^[a-z]{1,2}\d*$", nm, re.I)): continue
                fy, fx = float(rect[1]), float(rect[3] if False else rect[0])
                left = [(fx - wx, wt) for wy, wx, wt in words if abs(fy - wy) <= 4 and 2 < (fx - wx) < 230]
                above = [(wy - fy, wt) for wy, wx, wt in words if 2 < (wy - fy) < 18 and abs(wx - fx) < 90]
                src = sorted(left)[:8] or sorted(above)[:8]
                lab = re.sub(r"\s+", " ", " ".join(w for _, w in src)).strip(" .:_-")
                if realwords(lab) >= 1 and 3 <= len(lab) <= 70 and not re.match(r"^(ja|nein|x)\b", lab, re.I):
                    out[nm] = lab[:70]
    except Exception:
        pass
    return out

def main():
    apply = "--apply" in sys.argv
    src = connect(DB_PATH)
    forms = src.execute("SELECT id, title, source_file FROM form").fetchall()
    review = []
    db = DB_PATH + ".staging"
    if os.path.exists(db): os.remove(db)
    shutil.copy2(DB_PATH, db)
    conn = connect(db)
    nT = nF = 0
    for fm in forms:
        path = os.path.normpath(os.path.join(ROOT, fm["source_file"]))
        is_pdf = path.lower().endswith(".pdf") and os.path.exists(path)
        # --- title ---
        if is_bad_title(fm["title"]):
            new = font_title(path) if is_pdf else None
            if new and not is_bad_title(new):
                conn.execute("UPDATE form SET title=? WHERE id=?", [new, fm["id"]])
                conn.execute("UPDATE service SET name=? WHERE id=(SELECT service_id FROM form WHERE id=?)",
                             [new, fm["id"]]); nT += 1
            else:
                review.append(("TITLE", fm["title"], fm["source_file"]))
        # --- fields ---
        bad = conn.execute("SELECT id, field_key, label FROM form_field WHERE form_id=? AND "
                           "(label IS NULL OR length(trim(label))<3 OR label GLOB '[0-9]*')", [fm["id"]]).fetchall()
        if bad and is_pdf:
            pos = positional_labels(path)
            for b in bad:
                key = re.sub(r"-\d+$", "", b["field_key"])   # field_key was slug(label)-i
                cand = pos.get(b["label"].strip()) or pos.get(key)
                if cand:
                    conn.execute("UPDATE form_field SET label=? WHERE id=?", [cand, b["id"]]); nF += 1
                else:
                    review.append(("FIELD", f"{fm['title'][:40]} :: {b['label']}", fm["source_file"]))
        elif bad:
            for b in bad: review.append(("FIELD", f"{fm['title'][:40]} :: {b['label']}", fm["source_file"]))
    src.close()
    if apply:
        conn.commit(); errs = validate(conn); conn.close()
        if errs: os.remove(db); print("ABORT:", *errs[:4], sep="\n  "); sys.exit(1)
        os.replace(db, DB_PATH)
    else:
        conn.close(); os.remove(db)
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(os.path.join(LOGS_DIR, "quality_review.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"Could not auto-improve ({len(review)}) — needs a human eye:\n"+"="*60+"\n")
        for kind, what, sf in review:
            fh.write(f"[{kind}] {what}   <- {sf}\n")
    print(f"{'APPLIED' if apply else 'DRY-RUN'}: improved {nT} titles, {nF} field labels; "
          f"{len(review)} left for review (logs/quality_review.txt)")


if __name__ == "__main__":
    main()
