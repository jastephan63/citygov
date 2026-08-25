#!/usr/bin/env python3
"""Load agent-proposed data-field -> article mappings (scratchpad/dfmap/<form_id>.json)
into data_field_legal_basis, PROOF-GATED: a citation is accepted only if the cited
(cref, article_no) exists as a real article that was ingested from the official law
PDF (last_checked starts 'Gesetze-PDF' or 'verified'). Anything else is rejected as
unsourced — no invented citation may enter the DB. Idempotent per form.
Safe wrapper: staging -> validate -> swap.

    python3 scripts/load_field_legal.py <dir-of-json>
"""
import glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate


def norm_no(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s


def cite_candidates(no):
    """Footnote-tolerant: 'Art. 1181' -> ['Art. 1181','Art. 118','Art. 11','Art. 1'];
    keeps a letter-suffix variant first ('Art. 153g'). Longest match wins."""
    m = re.match(r"^\s*(Art\.|§)\s*(\d+)([A-Za-z]*)\s*$", no or "")
    if not m:
        return [norm_no(no)]
    kind, digits, letters = m.groups()
    cands = []
    if letters:
        cands.append(f"{kind} {digits}{letters}")
    for k in range(len(digits), 0, -1):
        cands.append(f"{kind} {digits[:k]}")
    return cands


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "."
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    # (cref, article_no) -> (article_id, last_checked)  for SOURCED articles only
    artmap = {}
    for r in c.execute("SELECT a.id aid, a.article_no no, a.last_checked lc, l.cantonal_ref cref, l.sr_number sr "
                       "FROM article a JOIN law l ON l.id=a.law_id "
                       "WHERE a.last_checked LIKE 'Gesetze-PDF%' OR a.last_checked='verified'"):
        lc = r["lc"] or ""
        key = (r["cref"] or ("SR " + (r["sr"] or "")), norm_no(r["no"]))
        artmap[key] = (r["aid"], lc)
        if r["sr"]:
            artmap[("SR " + r["sr"], norm_no(r["no"]))] = (r["aid"], lc)

    linked = rejected = forms = over = 0
    for jf in sorted(glob.glob(os.path.join(src, "*.json"))):
        try:
            fid = int(os.path.splitext(os.path.basename(jf))[0])
            data = json.load(open(jf, encoding="utf-8"))
        except Exception:
            continue
        maps = data.get("mappings") if isinstance(data, dict) else None
        if not isinstance(maps, list):
            continue
        dfid = {r["name"]: r["id"] for r in
                c.execute("SELECT id, name FROM data_field WHERE form_id=?", [fid])}
        if not dfid:
            continue
        c.execute("DELETE FROM data_field_legal_basis WHERE data_field_id IN "
                  "(SELECT id FROM data_field WHERE form_id=?)", [fid])
        c.execute("UPDATE data_field SET no_basis=0 WHERE form_id=?", [fid])
        forms += 1
        for m in maps:
            if not isinstance(m, dict):
                continue
            did = dfid.get((m.get("data_field") or "").strip())
            if not did:
                continue
            got = 0
            for ci in (m.get("cites") or []):
                cref = (ci.get("cref") or "").strip()
                hit = None
                for cand in cite_candidates(ci.get("article_no")):   # footnote-tolerant
                    hit = artmap.get((cref, norm_no(cand)))
                    if hit:
                        break
                if not hit:                       # PROOF GATE: not a real ingested article
                    rejected += 1
                    continue
                c.execute("INSERT INTO data_field_legal_basis(data_field_id,article_id,last_checked,relation) "
                          "VALUES(?,?,?,?)", [did, hit[0], hit[1], "requires"])
                linked += 1
                got += 1
            if got == 0 and m.get("over_collection"):   # honest verdict: no law requires it
                c.execute("UPDATE data_field SET no_basis=1 WHERE id=?", [did])
                over += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"linked {linked} sourced citations across {forms} forms; "
          f"{over} fields marked over-collection (no basis); "
          f"{rejected} proposed cites REJECTED by proof gate (not in real law text)")


if __name__ == "__main__":
    main()
