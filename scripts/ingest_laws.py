#!/usr/bin/env python3
"""Ingest cantonal laws (by SHR number) into law+article, and optionally dump a
compact JSON per law for the mapping agents. Article numbers and headings are
read from the official Gesetze PDF (extract_law.py --index) — the ground truth
the proof gate maps against. Upserts are idempotent; last_checked is set to
'Gesetze-PDF SHR <n> (Stand …)'. Writes go staging -> validate -> swap.

    python3 scripts/ingest_laws.py <SHR> [<SHR> ...] [--out <dir>]
"""
import json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect
from validate_db import validate

HERE = os.path.dirname(os.path.abspath(__file__))
IDX = json.load(open(os.path.join(HERE, "..", "inventory", "gesetze_index.json")))
BYSHR = {g.get("shr"): g for g in IDX}
ART = re.compile(r"^\s*\d+:\s*((?:Art\.|§)\s*[\w.]+[a-z]?)(?:\s+(.*?))?\s*$")
DATEY = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def read_law(shr):
    g = BYSHR.get(shr)
    if not g:
        return None
    path = os.path.normpath(os.path.join(ROOT, "..", "Gesetze", g["file"]))
    if not os.path.exists(path):
        return None
    try:
        out = subprocess.run(["python3", os.path.join(HERE, "extract_law.py"), path, "--index"],
                             capture_output=True, text=True, timeout=90).stdout
    except Exception:
        return None
    stand = ""
    m = re.search(r"\(Stand ([^)]+)\)", out)
    if m:
        stand = m.group(1).strip()
    arts, seen = [], set()
    for ln in out.splitlines():
        m = ART.match(ln)
        if not m:
            continue
        no, head = m.group(1).strip(), (m.group(2) or "").strip()
        if DATEY.search(ln):                       # change-log line, not an article
            continue
        if head and not re.search(r"[A-Za-zÄÖÜäöü]{3,}", head):
            head = ""                              # junk heading -> keep article, drop heading
        no = re.sub(r"\s+", " ", no)
        if no in seen:
            continue
        seen.add(no)
        arts.append({"no": no, "heading": head[:120]})
    return {"shr": shr, "title": g["title"], "stand": stand, "articles": arts}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    outdir = None
    if "--out" in sys.argv:
        outdir = sys.argv[sys.argv.index("--out") + 1]
        os.makedirs(outdir, exist_ok=True)
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    nl = na = 0
    for shr in args:
        law = read_law(shr)
        if not law or not law["articles"]:
            print(f"  {shr}: no articles read (skipped)")
            continue
        cref = "SHR " + shr
        lc = f"Gesetze-PDF {cref}" + (f" (Stand {law['stand']})" if law["stand"] else "")
        r = c.execute("SELECT id FROM law WHERE cantonal_ref=?", [cref]).fetchone()
        if r:
            lid = r["id"]
        else:
            slug = re.sub(r"[^a-z0-9]+", "-", (law["title"] or shr).lower())[:60].strip("-")
            c.execute("INSERT INTO law(slug,title,short_title,jurisdiction_level,cantonal_ref,last_checked) "
                      "VALUES(?,?,?,?,?,?)", [slug, law["title"], law["title"][:40], "cantonal", cref, "Gesetze-PDF"])
            lid = c.execute("SELECT id FROM law WHERE cantonal_ref=?", [cref]).fetchone()["id"]
            nl += 1
        for a in law["articles"]:
            ex = c.execute("SELECT id FROM article WHERE law_id=? AND article_no=?", [lid, a["no"]]).fetchone()
            if ex:
                c.execute("UPDATE article SET heading=?, last_checked=? WHERE id=?", [a["heading"], lc, ex["id"]])
            else:
                c.execute("INSERT INTO article(law_id,article_no,heading,last_checked) VALUES(?,?,?,?)",
                          [lid, a["no"], a["heading"], lc])
                na += 1
        if outdir:
            json.dump({"cref": cref, "title": law["title"], "stand": law["stand"],
                       "articles": law["articles"]},
                      open(os.path.join(outdir, shr + ".json"), "w"), ensure_ascii=False)
        print(f"  {shr}: {len(law['articles'])} articles  ({law['title'][:50]})")
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"ingested: +{nl} laws, +{na} articles")


if __name__ == "__main__":
    main()
