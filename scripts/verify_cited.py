#!/usr/bin/env python3
"""Upgrade 'cited_unverified' citations to 'sourced' by confirming them against the
official cantonal Gesetze PDFs (safe, offline; convention 3).

resolve_cited.py records each form's cited laws+articles verbatim as one pseudo-law
("Im Formular zitiert: …") with last_checked 'zitiert (unverifiziert)'. This pass
tries to RESOLVE each cited article to a real SHR law:
  * candidate laws = Gesetze whose TITLE contains a cited law name (len>=6),
  * an article is upgraded only if EXACTLY ONE candidate law actually contains that
    article number (verified via the law's text) — this both confirms the citation
    and resolves which law the article belongs to. Ambiguous/absent -> left as-is.
On a match it creates a real cantonal law+article (last_checked 'Gesetze-PDF <shr>')
and re-points the requirement's legal_basis to it. Safe wrapper: staging->validate->swap.

    python3 scripts/verify_cited.py
"""
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect, INVENTORY_DIR, log
from extract_law import extract_text, article_index
from commit_proposal import upsert
from validate_db import validate

GESETZE = os.path.normpath(os.path.join(ROOT, "..", "Gesetze"))
INDEX = json.load(open(os.path.join(INVENTORY_DIR, "gesetze_index.json")))
NUM = re.compile(r"\d+[a-z]?")

_artcache = {}
def law_article_nums(fname):
    if fname not in _artcache:
        nums = set()
        for _, head in article_index(extract_text(os.path.join(GESETZE, fname))):
            m = NUM.search(head)
            if m: nums.add(m.group(0))
        _artcache[fname] = nums
    return _artcache[fname]

def candidates(name):
    n = name.lower().strip()
    if len(n) < 6: return []
    cands = [g for g in INDEX if g.get("title") and n in g["title"].lower()]
    if cands:
        return cands
    # fall back to the de-suffixed root (Energiegesetz -> energie), but only against
    # actual 'Gesetz' titles. The article-presence gate downstream filters false hits.
    root = re.sub(r"(gesetz|verordnung|reglement|ordnung)$", "", n).strip()
    if len(root) >= 5:
        cands = [g for g in INDEX if g.get("title") and root in g["title"].lower()
                 and "gesetz" in g["title"].lower()]
    return cands

def main():
    staging = DB_PATH + ".staging"
    if os.path.exists(staging): os.remove(staging)
    shutil.copy2(DB_PATH, staging)
    conn = connect(staging)
    upgraded = 0; matched_laws = set()
    try:
        zit = conn.execute("SELECT id, short_title, title FROM law WHERE slug LIKE 'zit-%'").fetchall()
        for law in zit:
            names = [x.strip() for x in (law["short_title"] or "").split(";") if x.strip()]
            cand = {}
            for nm in names:
                for g in candidates(nm):
                    cand[g["file"]] = (g["shr"], g["title"])
            if not cand:
                continue
            for art in conn.execute("SELECT id, article_no FROM article WHERE law_id=?", [law["id"]]).fetchall():
                m = NUM.search(art["article_no"] or "")
                if not m: continue
                num = m.group(0)
                owners = [(f, shr, t) for f, (shr, t) in cand.items() if num in law_article_nums(f)]
                if len(owners) != 1:
                    continue                      # ambiguous or unconfirmed -> keep cited
                f, shr, title = owners[0]
                prov = f"Gesetze-PDF {shr}"
                rlaw = upsert(conn, "law", ["slug"], {
                    "slug": f"shr-{shr}", "jurisdiction_level": "cantonal",
                    "title": title, "short_title": (title.split()[0] if title else shr),
                    "cantonal_ref": f"SHR {shr}",
                    "source_note": f"Gesetze/{f}; im Formular zitiert und Art. {num} im Volltext bestätigt.",
                    "last_checked": prov})
                rart = upsert(conn, "article", ["law_id", "article_no", "heading"], {
                    "law_id": rlaw, "article_no": art["article_no"], "heading": "im Formular zitiert, in Quelle bestätigt",
                    "text_excerpt": None, "last_checked": prov})
                matched_laws.add(shr)
                for b in conn.execute("SELECT id, requirement_id, citation_detail FROM requirement_legal_basis WHERE article_id=?", [art["id"]]).fetchall():
                    # re-point to the verified article (skip if that pair already exists)
                    exists = conn.execute("SELECT 1 FROM requirement_legal_basis WHERE requirement_id=? AND article_id=?",
                                          [b["requirement_id"], rart]).fetchone()
                    if exists:
                        conn.execute("DELETE FROM requirement_legal_basis WHERE id=?", [b["id"]])
                    else:
                        conn.execute("UPDATE requirement_legal_basis SET article_id=?, last_checked=? WHERE id=?",
                                     [rart, prov, b["id"]])
                    upgraded += 1
        conn.commit()
    except Exception as e:
        conn.close(); os.remove(staging); log("verify_cited.log", f"ABORT {e!r}")
        print(f"ABORT: {e!r}", file=sys.stderr); sys.exit(1)
    errs = validate(conn); conn.close()
    if errs:
        os.remove(staging); print("ABORT validation:", *errs[:5], sep="\n  ", file=sys.stderr); sys.exit(1)
    os.replace(staging, DB_PATH)
    print(f"upgraded {upgraded} citation links to sourced; resolved {len(matched_laws)} cantonal laws "
          f"({', '.join(sorted(matched_laws)[:12])}{'…' if len(matched_laws)>12 else ''})")


if __name__ == "__main__":
    main()
