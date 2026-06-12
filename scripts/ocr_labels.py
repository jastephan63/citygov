#!/usr/bin/env python3
"""Best-quality field labelling: macOS Vision OCR (accurate, with boxes) correlated
to each AcroForm field's rectangle, to read the PRINTED label next to a field that
the PDF names only '1','26', … . Also upgrades a weak form title from the OCR.

Pipeline per form: pypdf gives each field's /Rect + page (normalised); a Swift
Vision program renders+OCRs each page returning text boxes (normalised, bottom-left
origin); for each weak field we take the OCR text immediately to its LEFT on the
same row, else just ABOVE. Only confident, sane labels are written (conv 6: better
the field's id than a wrong label). Safe wrapper: staging -> validate -> swap.

    python3 scripts/ocr_labels.py [form_id ...]      # default: all forms with weak fields
"""
import os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect, log
from validate_db import validate
from fix_quality import is_bad_label, is_bad_title, realwords

SWIFT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_pdf.swift")
BAD = re.compile(r"^(ja|nein|x|☐|□)\b", re.I)

def field_positions(path):
    """name -> (page, nx0, ny0, nx1, ny1) normalised, origin bottom-left."""
    from pypdf import PdfReader
    pos = {}
    try: r = PdfReader(path)
    except Exception: return pos, 0
    for pi, pg in enumerate(r.pages):
        try:
            mb = pg.mediabox; W = float(mb.width); H = float(mb.height)
        except Exception: continue
        if not (W and H): continue
        for a in (pg.get("/Annots") or []):
            try: o = a.get_object()
            except Exception: continue
            if o.get("/Subtype") != "/Widget": continue
            nm = o.get("/T")
            if nm is None and o.get("/Parent"):
                nm = o["/Parent"].get_object().get("/T")
            rect = o.get("/Rect")
            if nm is None or not rect: continue
            try: x0, y0, x1, y1 = [float(v) for v in rect]
            except Exception: continue
            pos[str(nm)] = (pi, min(x0,x1)/W, min(y0,y1)/H, max(x0,x1)/W, max(y0,y1)/H)
    return pos, len(r.pages)

def ocr(path):
    """page -> list of (minX,minY,w,h,text) normalised, bottom-left origin."""
    try:
        out = subprocess.run(["swift", SWIFT, path, "2.0"], capture_output=True, text=True, timeout=120).stdout
    except Exception as e:
        log("ocr_labels.log", f"swift fail {path}: {e!r}"); return {}
    boxes = {}
    for ln in out.splitlines():
        p = ln.split("\t")
        if len(p) != 6: continue
        try: pi = int(p[0]); x, y, w, h = map(float, p[1:5])
        except Exception: continue
        boxes.setdefault(pi, []).append((x, y, w, h, p[5].strip()))
    return boxes

def label_for(field, boxes):
    pi, fx0, fy0, fx1, fy1 = field
    cy = (fy0 + fy1) / 2
    bs = boxes.get(pi, [])
    # 1) text on the same row, to the LEFT, nearest
    left = [(fx0 - (x + w), txt) for (x, y, w, h, txt) in bs
            if abs((y + h/2) - cy) < 0.012 and (x + w) <= fx0 + 0.01 and 0 <= (fx0 - (x + w)) < 0.35
            and txt and not BAD.match(txt)]
    if left:
        left.sort(); lab = left[0][1]
        # glue an immediately-preceding token if short
        return lab
    # 2) nearest text ABOVE, x-overlapping
    above = [((y) - fy1, txt) for (x, y, w, h, txt) in bs
             if 0 < (y - fy1) < 0.05 and not (x + w < fx0 - 0.02 or x > fx1 + 0.02)
             and txt and not BAD.match(txt)]
    if above:
        above.sort(); return above[0][1]
    return None

def main():
    ids = [int(a) for a in sys.argv[1:] if a.isdigit()]
    src = connect(DB_PATH)
    if ids:
        forms = src.execute(f"SELECT id, source_file, title FROM form WHERE id IN ({','.join('?'*len(ids))})", ids).fetchall()
    else:
        forms = src.execute("""SELECT f.id, f.source_file, f.title FROM form f WHERE EXISTS
            (SELECT 1 FROM form_field ff WHERE ff.form_id=f.id AND (ff.label GLOB '[0-9]*' OR length(trim(ff.label))<3))""").fetchall()
    src.close()
    staging = DB_PATH + ".staging"
    if os.path.exists(staging): os.remove(staging)
    shutil.copy2(DB_PATH, staging)
    conn = connect(staging)
    nF = nT = done = 0
    for fm in forms:
        path = os.path.normpath(os.path.join(ROOT, fm["source_file"]))
        if not (path.lower().endswith(".pdf") and os.path.exists(path)):
            continue
        pos, npages = field_positions(path)
        if not pos: continue
        boxes = ocr(path)
        if not boxes: continue
        done += 1
        # title from largest OCR box on page 0 (if weak)
        if is_bad_title(fm["title"]) and 0 in boxes:
            big = sorted(boxes[0], key=lambda b: -b[3])
            cand = next((t for _, _, _, _, t in big if realwords(t) >= 2 and 8 <= len(t) <= 90), None)
            if cand and not is_bad_title(cand):
                conn.execute("UPDATE form SET title=? WHERE id=?", [cand, fm["id"]])
                conn.execute("UPDATE service SET name=? WHERE id=(SELECT service_id FROM form WHERE id=?)", [cand, fm["id"]])
                nT += 1
        # weak fields -> OCR label by position
        for fid, fkey, lbl in conn.execute(
                "SELECT id, field_key, label FROM form_field WHERE form_id=? AND (label GLOB '[0-9]*' OR length(trim(label))<3)",
                [fm["id"]]).fetchall():
            name = fkey.rsplit("-", 1)[0]
            if name not in pos: continue
            lab = label_for(pos[name], boxes)
            if lab:
                lab = re.sub(r"^\s*\d{1,3}[.)]?\s+", "", lab)          # drop leading question-no.
                lab = re.sub(r"\s+", " ", lab).strip(" .:_-")[:70]
                if realwords(lab) >= 1 and 3 <= len(lab) <= 70 and not lab.isdigit():
                    conn.execute("UPDATE form_field SET label=? WHERE id=?", [lab, fid]); nF += 1
    conn.commit()
    errs = validate(conn); conn.close()
    if errs:
        os.remove(staging); print("ABORT:", *errs[:4], sep="\n  "); sys.exit(1)
    os.replace(staging, DB_PATH)
    print(f"OCR-labelled {nF} fields and {nT} titles across {done} form(s)")


if __name__ == "__main__":
    main()
