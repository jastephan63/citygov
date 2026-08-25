#!/usr/bin/env python3
"""Ingest federal laws into law+article from PDFs fetched from the official
Fedlex filestore, and optionally dump a JSON per law for the mapping agents.
Article numbers and headings are read from the actual PDF (extract_law.py
--index); rows get last_checked='verified' because Fedlex is the official
source. Writes go staging -> validate -> swap.

    python3 scripts/ingest_fed.py <SR>=<pdf_path>=<title>=<short> [...] [--out <dir>]
"""
import json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

HERE = os.path.dirname(os.path.abspath(__file__))
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
        arts = articles(path)
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
