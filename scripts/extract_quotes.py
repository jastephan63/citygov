#!/usr/bin/env python3
"""Fill article.text_excerpt with the real text of every article cited by a
data_field_legal_basis row, copied mechanically from the official law PDF —
no agent involved, so the never-type-a-citation-from-memory rule holds.

Pages are streamed with pypdf and split into articles at 'Art. N' / '§ N'
headings. Extracted headings often have footnote counters glued onto the
number (e.g. 'Art. 91' comes out as 'Art. 911'); since article numbers only
increase within a law, deglue() recovers the real number. Excerpts are capped,
repeating page headers are stripped, and the DB write follows the usual
staging -> validate -> swap pattern.

    python3 scripts/extract_quotes.py <fed-pdf-dir>
"""
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect
from validate_db import validate

HERE = os.path.dirname(os.path.abspath(__file__))
ARTLINE = re.compile(r"^(Art\.|§)\s*(\d+)([a-z]{0,6})\b\.?\s*(.*)$")
PAGEHDR = re.compile(r"^\d+\s*/\s*\d+$|^\d{3}(\.\d+)*$|^[A-ZÄÖÜ][\wäöüÄÖÜ .,()/-]{0,70}\d*$")
CAP = 1600


def deglue(digits, letters, last):
    """Split a real article number off a glued footnote counter.

    Article numbers increase monotonically, so the shortest digit prefix that
    exceeds the previous number is the real one. A Latin suffix (bis, ter,
    quater, quinquies) or a single trailing letter is kept.
    """
    for k in range(1, len(digits) + 1):
        if int(digits[:k]) > last:
            num = digits[:k]
            break
    else:
        num = digits
    suf = ""
    if letters[:3] in ("bis", "ter", "qua", "qui"):
        suf = letters[:3]
    elif letters and letters[0].islower() and len(letters) <= 2:
        suf = letters[0]
    return num + suf, int(num)


def segments(pdf):
    """Ordered {'<kind> <no>': text} spans from a law PDF."""
    from pypdf import PdfReader
    try:
        r = PdfReader(pdf)
    except Exception:
        return {}
    spans = {}
    cur = None
    buf = []
    last = 0
    hdr_seen = {}
    def flush():
        nonlocal buf
        if cur and cur not in spans:
            t = re.sub(r"\s+", " ", " ".join(buf)).strip()
            # Undo PDF artifacts: re-join words split by a hyphen at a line
            # break (but keep compound enumerations like "Alters- und ..."),
            # then strip footnote counters glued onto word ends.
            t = re.sub(r"([a-zäöüß])- (?!(?:und|oder|bzw|sowie|resp|beziehungsweise)\b)([a-zäöü])", r"\1\2", t)
            t = re.sub(r"([A-Za-zäöüÄÖÜ]{3,})\d{1,4}(\s|$)", r"\1\2", t)
            spans[cur] = t[:CAP]
        buf = []
    for pg in r.pages:
        try:
            txt = pg.extract_text() or ""
        except Exception:
            continue
        for raw in txt.splitlines():
            line = raw.strip()
            if not line:
                continue
            # drop repeating page-header lines (law title, page counter, SR no.)
            hdr_seen[line] = hdr_seen.get(line, 0) + 1
            if hdr_seen[line] > 3 and len(line) < 80:
                continue
            if re.match(r"^\d+\s*/\s*\d+$", line):
                continue
            m = ARTLINE.match(line)
            if m:
                kind, digits, letters, rest = m.groups()
                no, last = deglue(digits, letters.strip(), last)
                flush()
                cur = f"{'Art.' if kind=='Art.' else '§'} {no}"
                if rest.strip():
                    buf.append(rest.strip())
            elif cur:
                buf.append(line)
    flush()
    return spans


def main():
    feddir = sys.argv[1] if len(sys.argv) > 1 else "."
    idx = {g["shr"]: g["file"] for g in
           json.load(open(os.path.join(HERE, "..", "inventory", "gesetze_index.json")))}
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    # Every law that has at least one article cited by a data-field legal basis.
    laws = c.execute("""SELECT DISTINCT l.id lid, l.sr_number sr, l.cantonal_ref cr FROM law l
        JOIN article a ON a.law_id=l.id
        JOIN data_field_legal_basis d ON d.article_id=a.id""").fetchall()
    filled = missing = nolaw = 0
    for L in laws:
        pdf = None
        if L["sr"] and os.path.exists(os.path.join(feddir, L["sr"] + ".pdf")):
            pdf = os.path.join(feddir, L["sr"] + ".pdf")
        elif L["cr"]:
            f = idx.get(L["cr"].replace("SHR ", ""))
            if f and os.path.exists(os.path.join(ROOT, "..", "Gesetze", f)):
                pdf = os.path.join(ROOT, "..", "Gesetze", f)
        if not pdf:
            nolaw += 1
            continue
        spans = segments(pdf)
        # The DB may say 'Art. 4' where the PDF says '§ 4' (or vice versa):
        # look up the exact key first, then the same number with the other kind.
        for a in c.execute("""SELECT a.id, a.article_no FROM article a
             JOIN data_field_legal_basis d ON d.article_id=a.id WHERE a.law_id=? GROUP BY a.id""", [L["lid"]]):
            no = re.sub(r"\s+", " ", a["article_no"].strip())
            txt = spans.get(no) or spans.get(no.replace("Art. ", "§ ")) or spans.get(no.replace("§ ", "Art. "))
            if txt and len(txt) > 40:
                c.execute("UPDATE article SET text_excerpt=? WHERE id=?", [txt, a["id"]])
                filled += 1
            else:
                missing += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"quotes filled: {filled} articles | not found in PDF: {missing} | laws without PDF: {nolaw}")


if __name__ == "__main__":
    main()
