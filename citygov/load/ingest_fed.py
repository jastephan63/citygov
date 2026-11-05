#!/usr/bin/env python3
"""Ingest federal laws into law+article from files fetched from the official
Fedlex filestore, and optionally dump a JSON per law as mapping input.
Article numbers and headings are read from the actual file: from the PDF
(extract_law.py --index), or — when the path ends in .xml — from the Fedlex XML
(Akoma Ntoso) of the same consolidated edition, where every <article> carries its
number and heading; footnotes are dropped and repealed articles («Aufgehoben») are
not citable and skipped. The PDF index of some laws glues footnote numbers to the
article number («Art. 1417» for Art. 14 + note 17) and misses articles whose heading
stands on the next line: use the XML there. Rows get last_checked='verified' because
Fedlex is the official source. Writes go staging -> validate -> swap.

    python3 scripts/ingest_fed.py <SR>=<pdf_or_xml_path>=<title>=<short> [...] [--out <dir>]
"""
import json, os, re, shutil, subprocess, sys
from citygov.core.common import DB_PATH, ROOT, connect
from citygov.checks.validate_db import validate

HERE = os.path.join(ROOT, "scripts")   # runs scripts/extract_law.py, as before the move
ART = re.compile(r"^\s*\d+:\s*((?:Art\.|§)\s*[\w.]+[a-z]?)\s+(.+?)\s*$")
DATEY = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def articles(path):
    try:
        out = subprocess.run(["python3", os.path.join(HERE, "extract_law.py"), path, "--index"],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception:
        return []
    arts, seen = [], set()
    for ln in out.splitlines():
        m = ART.match(ln)
        if not m:
            continue
        no, head = re.sub(r"\s+", " ", m.group(1).strip()), m.group(2).strip()
        if DATEY.search(ln) or len(head) < 3 or not re.search(r"[A-Za-zÄÖÜäöü]{3,}", head) or no in seen:
            continue
        seen.add(no)
        arts.append({"no": no, "heading": head[:120]})
    return arts


def articles_xml(path):
    """[{no, heading}] from a Fedlex Akoma-Ntoso XML: the <num> and <heading> of every
    <article>, footnotes (<authorialNote>) removed; a repealed article and a renumbering stub without
    text are skipped. Inline tags join without a space, so «<b>Art. 66</b><i>a</i>» is «Art. 66a»."""
    import html as H
    x = open(path, encoding="utf-8").read()
    x = re.sub(r"<authorialNote\b.*?</authorialNote>", "", x, flags=re.S)
    # inline tags (bold, italic, superscript «bis») join without a space, block tags with one
    inline = lambda s: re.sub(r"</?(?:b|i|sup|sub|span|em|strong|inline)\b[^>]*>", "", s or "")
    txt = lambda s: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", inline(s)))).strip()
    arts, seen = [], set()
    for m in re.finditer(r"<article\b[^>]*>(.*?)</article>", x, re.S):
        body = m.group(1)
        num = re.search(r"<num\b[^>]*>(.*?)</num>", body, re.S)
        # «Art. 66 a» (inline tags read as spaces) would fail the pattern and drop every lettered article
        no = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", num.group(1)))).strip() if num else ""
        if not re.fullmatch(r"(Art\.|§)\s*\d+[a-z]*(\s*(bis|ter|quater|quinquies|sexies|septies|octies))?", no):
            continue
        rest = body[num.end():] if num else body
        if re.fullmatch(r"\s*(…|\.\.\.)?\s*Aufgehoben\.?\s*", txt(re.sub(r"<heading\b.*?</heading>", "", rest, flags=re.S))):
            continue
        hd = re.search(r"<heading\b[^>]*>(.*?)</heading>", body, re.S)
        head = txt(hd.group(1)) if hd else ""
        if not head:
            # an article without a heading: the first words of its text stand in
            head = txt(re.sub(r"<num\b.*?</num>", "", rest, flags=re.S))[:80]
        if not head:
            continue    # a renumbering stub («Art. 220a», only a footnote «Heute: Art. 205bbis»): no article
        no = re.sub(r"\s+", " ", no)
        if no in seen:
            continue
        seen.add(no)
        arts.append({"no": no, "heading": head[:120]})
    return arts


def main():
    outdir = None
    if "--out" in sys.argv:
        outdir = sys.argv[sys.argv.index("--out") + 1]
        os.makedirs(outdir, exist_ok=True)
    specs = [a for a in sys.argv[1:] if "=" in a and not a.startswith("--")]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    nl = na = 0
    for spec in specs:
        sr, path, title, short = (spec.split("=", 3) + ["", "", ""])[:4]
        arts = articles_xml(path) if path.lower().endswith(".xml") else articles(path)
        if not arts:
            print(f"  SR {sr}: no articles (skipped)")
            continue
        r = c.execute("SELECT id FROM law WHERE sr_number=?", [sr]).fetchone()
        if r:
            lid = r["id"]
        else:
            slug = re.sub(r"[^a-z0-9]+", "-", (short or sr).lower())[:60].strip("-")
            c.execute("INSERT INTO law(slug,title,short_title,jurisdiction_level,sr_number,last_checked) "
                      "VALUES(?,?,?,?,?,?)", [slug, title, short, "federal", sr, "verified"])
            lid = c.execute("SELECT id FROM law WHERE sr_number=?", [sr]).fetchone()["id"]
            nl += 1
        for a in arts:
            ex = c.execute("SELECT id FROM article WHERE law_id=? AND article_no=?", [lid, a["no"]]).fetchone()
            if ex:
                c.execute("UPDATE article SET heading=?, last_checked='verified' WHERE id=?", [a["heading"], ex["id"]])
            else:
                c.execute("INSERT INTO article(law_id,article_no,heading,last_checked) VALUES(?,?,?,'verified')",
                          [lid, a["no"], a["heading"]])
                na += 1
        if outdir:
            json.dump({"cref": "SR " + sr, "title": title, "stand": "Fedlex", "articles": arts},
                      open(os.path.join(outdir, sr + ".json"), "w"), ensure_ascii=False)
        print(f"  SR {sr}: {len(arts)} articles ({title[:44]})")
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"ingested: +{nl} federal laws, +{na} articles")


if __name__ == "__main__":
    main()
