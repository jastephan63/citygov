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
from auto_draft import slug

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
            # key by slug(name) so it matches field_key (slug(label)) even when the
            # field name has umlauts/spaces (e.g. 'Kontrollkästchen 16').
            pos[slug(str(nm))] = (pi, min(x0,x1)/W, min(y0,y1)/H, max(x0,x1)/W, max(y0,y1)/H)
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

_VALUEONLY = re.compile(r"^[\d.,'\s/%:()-]+$")
def _ok(lab):
    return lab and realwords(lab) >= 1 and not _VALUEONLY.match(lab)

def label_for(field, boxes):
    pi, fx0, fy0, fx1, fy1 = field
    cy = (fy0 + fy1) / 2
    bs = boxes.get(pi, [])
    # 1) SAME ROW, to the LEFT — glue the contiguous run of tokens ending at the field
    row = sorted([(x, w, txt) for (x, y, w, h, txt) in bs
                  if abs((y + h/2) - cy) < 0.013 and (x + w) <= fx0 + 0.015
                  and 0 <= (fx0 - (x + w)) < 0.45 and txt and not BAD.match(txt)],
                 key=lambda r: r[0])
    if row:
        run = [row[-1]]
        for i in range(len(row) - 2, -1, -1):
            if run[0][0] - (row[i][0] + row[i][1]) < 0.06: run.insert(0, row[i])
            else: break
        lab = " ".join(t for _, _, t in run)
        if _ok(lab): return lab
    # 2) nearest row ABOVE, x-overlapping — glue that row
    abv = [(y, x, w, txt) for (x, y, w, h, txt) in bs
           if 0 < (y - fy1) < 0.05 and not (x + w < fx0 - 0.04 or x > fx1 + 0.04)
           and txt and not BAD.match(txt)]
    if abv:
        abv.sort(key=lambda r: r[0]); ny = abv[0][0]
        rowa = sorted([(x, txt) for (y, x, w, txt) in abv if abs(y - ny) < 0.012])
        lab = " ".join(t for _, t in rowa)
        if _ok(lab): return lab
    # 3) SAME ROW, to the RIGHT (checkbox option text) — glue the contiguous run
    rt = sorted([(x, w, txt) for (x, y, w, h, txt) in bs
                 if abs((y + h/2) - cy) < 0.013 and x >= fx1 - 0.01
                 and 0 <= (x - fx1) < 0.45 and txt and not BAD.match(txt)],
                key=lambda r: r[0])
    if rt:
        run = [rt[0]]
        for i in range(1, len(rt)):
            if rt[i][0] - (run[-1][0] + run[-1][1]) < 0.06: run.append(rt[i])
            else: break
        lab = " ".join(t for _, _, t in run)
        if _ok(lab): return lab
    # 4) TABLE cell: compose column-header (topmost text overlapping this column)
    #    + row-header (leftmost text on this row). Gives e.g. "AHV Betrag".
    fcx = (fx0 + fx1) / 2
    col = [(y, txt) for (x, y, w, h, txt) in bs
           if (x <= fcx <= x + w or abs((x + w/2) - fcx) < 0.05) and y > fy1 + 0.005
           and _ok(txt)]
    row = sorted([(x, txt) for (x, y, w, h, txt) in bs
                  if abs((y + h/2) - cy) < 0.02 and (x + w) < fx0 and _ok(txt)])
    colh = max(col, key=lambda r: r[0])[1] if col else ""        # topmost in column
    rowh = row[0][1] if row else ""                               # leftmost in row
    comp = " · ".join(p for p in (rowh, colh) if p).strip(" ·")
    if _ok(comp) and len(comp) <= 70:
        return comp
    return None

def main():
    ids = [int(a) for a in sys.argv[1:] if a.isdigit()]
    src = connect(DB_PATH)
    if ids:
        forms = src.execute(f"SELECT id, source_file, title FROM form WHERE id IN ({','.join('?'*len(ids))})", ids).fetchall()
    else:
        forms = src.execute("""SELECT f.id, f.source_file, f.title FROM form f WHERE EXISTS
            (SELECT 1 FROM form_field ff WHERE ff.form_id=f.id AND (ff.label GLOB '[0-9]*'
             OR length(trim(ff.label))<3 OR lower(ff.label) LIKE 'kontrollk%'
             OR lower(ff.label) LIKE 'optionsfeld%' OR lower(ff.label) LIKE 'toggle%'
             OR lower(ff.label) LIKE 'text %' OR lower(ff.label) LIKE 'text[0-9]%'
             OR lower(ff.label) LIKE 'feld %' OR lower(ff.label) LIKE 'auswahl%'
             OR lower(ff.label) LIKE 'undefined%' OR lower(ff.label) LIKE 'druckfeld%'))""").fetchall()
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
        # weak fields -> OCR label by position (filter with is_bad_label, in sync)
        for fid, fkey, lbl in conn.execute(
                "SELECT id, field_key, label FROM form_field WHERE form_id=?", [fm["id"]]).fetchall():
            if not is_bad_label(lbl):
                continue
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
