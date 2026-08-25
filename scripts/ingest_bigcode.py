#!/usr/bin/env python3
"""Ingest BIG federal codes (ZGB, OR, StGB, SVG …) whose multi-hundred-page PDFs
defeat the JXA whole-document extractor. Uses pypdf page-streaming instead.

Article index: lines starting 'Art. N…'. The trailing footnote counter that
Fedlex glues onto numbers ('Art. 654a576' = Art. 654a + fn 576) is removed
inline via the monotonic-sequence rule (article numbers only increase; the real
number is the shortest increasing prefix). Heading = the preceding short
marginal-title line when present, else the first words of the article body.
Upserts law+article (last_checked='verified') and dumps the agent JSON.

    python3 scripts/ingest_bigcode.py <SR>=<pdf>=<title>=<short> [...] --out <dir>
"""
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

ARTLINE = re.compile(r"^Art\.\s*(\d+)([a-z]{0,6})\b\.?\s*(.*)$")
PAGEHDR = re.compile(r"^\d+\s*/\s*\d+$|^\d{3}(\.\d+)*$")   # '51 / 388', '210'
TITLEISH = re.compile(r"^[A-ZÄÖÜIVX][^.]{2,70}$")


def deglue(digits, letters, last):
    """Monotonic rule: real article number = shortest increasing numeric prefix."""
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


def parse(pdf):
    from pypdf import PdfReader
    r = PdfReader(pdf)
    arts, seen = [], set()
    last = 0
    prev_lines = []
    for pg in r.pages:
        try:
            txt = pg.extract_text() or ""
        except Exception:
            continue
        for raw in txt.splitlines():
            line = raw.strip()
            if not line or PAGEHDR.match(line):
                continue
            m = ARTLINE.match(line)
            if m:
                digits, letters, rest = m.groups()
                no, last = deglue(digits, letters.strip(), last)
                key = "Art. " + no
                if key in seen:
                    prev_lines.append(line)
                    continue
                seen.add(key)
                # heading: nearest previous short title-ish line, else body start
                head = ""
                for pl in reversed(prev_lines[-4:]):
                    if TITLEISH.match(pl) and not pl.startswith("Art."):
                        head = pl
                        break
                if not head:
                    head = (rest or "").strip()
                arts.append({"no": key, "heading": re.sub(r"\s+", " ", head)[:110]})
                prev_lines = []
            else:
                prev_lines.append(line)
                if len(prev_lines) > 8:
                    prev_lines.pop(0)
    # Articles that got neither a marginal title nor body text on the Art. line
    # deliberately keep an empty heading — no second pass over the body.
    return arts


def main():
    outdir = None
    if "--out" in sys.argv:
        outdir = sys.argv[sys.argv.index("--out") + 1]
        os.makedirs(outdir, exist_ok=True)
    specs = [a for a in sys.argv[1:] if "=" in a]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    for spec in specs:
        sr, pdf, title, short = (spec.split("=", 3) + ["", ""])[:4]
        arts = parse(pdf)
        if len(arts) < 10:
            print(f"  SR {sr}: only {len(arts)} articles — skipped (parse failed)")
            continue
        row = c.execute("SELECT id FROM law WHERE sr_number=?", [sr]).fetchone()
        if row:
            lid = row["id"]
        else:
            slug = re.sub(r"[^a-z0-9]+", "-", (short or sr).lower())[:60].strip("-")
            c.execute("INSERT INTO law(slug,title,short_title,jurisdiction_level,sr_number,last_checked) "
                      "VALUES(?,?,?,?,?,'verified')", [slug, title, short, "federal", sr])
            lid = c.execute("SELECT id FROM law WHERE sr_number=?", [sr]).fetchone()["id"]
        n_new = 0
        for a in arts:
            ex = c.execute("SELECT id FROM article WHERE law_id=? AND article_no=?", [lid, a["no"]]).fetchone()
            if ex:
                c.execute("UPDATE article SET heading=?, last_checked='verified' WHERE id=?", [a["heading"], ex["id"]])
            else:
                c.execute("INSERT INTO article(law_id,article_no,heading,last_checked) VALUES(?,?,?,'verified')",
                          [lid, a["no"], a["heading"]])
                n_new += 1
        if outdir:
            json.dump({"cref": "SR " + sr, "title": title, "stand": "Fedlex", "articles": arts},
                      open(os.path.join(outdir, sr + ".json"), "w"), ensure_ascii=False)
        print(f"  SR {sr}: {len(arts)} articles (+{n_new} new)  ({title[:40]})")
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print("done")


if __name__ == "__main__":
    main()
