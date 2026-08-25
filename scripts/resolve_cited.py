#!/usr/bin/env python3
"""Structure each draft form's VERBATIM cited legal references as 'cited_unverified'
legal bases (safe first legal pass for every office).

It does NOT match cited short-names to the 374 Gesetze PDFs (that mis-matches —
'Bau' -> Schulbau — and would inject wrong citations, conv 6). It records exactly
what the form/Merkblatt cites, as a lead, marked 'zitiert (unverifiziert)'. The
careful step (resolve to the real SHR/Fedlex article, verify, set verified/Quelle)
is the per-office review that upgrades these.

For each auto-draft service it reads the cited laws/SR/articles already mined into
the draft finding, creates one "Im Formular zitiert: ..." law record per service
(jurisdiction guessed from 'Bundes'/SR presence), with the cited articles as
article rows, and links them as legal bases to the service's requirements — only
those whose field mapping is classified mapped/identity_part/reason_facet, not
form_mechanic/overcollection.

    python3 scripts/resolve_cited.py
"""
import os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect, log
from commit_proposal import upsert
from validate_db import validate

CITED = "zitiert (unverifiziert)"
LAWS_RE = re.compile(r"zitierte Gesetze:\s*([^.]+)\.")
SR_RE   = re.compile(r"SR:\s*([0-9.,\s]+)")
ART_RE  = re.compile(r"zitierte Artikel:\s*([^.]+(?:\.[^.;]*)*)")
ART_ONE = re.compile(r"(?:Art\.?\s*|§\s*)?(\d+[a-z]?)((?:\s*(?:Abs\.?|Bst\.?|lit\.?|Ziff\.?)\s*\w+)*)")


def parse_finding(desc):
    lm = LAWS_RE.search(desc)
    laws = [x.strip() for x in lm.group(1).split(",") if x.strip()] if lm else []
    sm = SR_RE.search(desc)
    sr = [x.strip() for x in sm.group(1).split(",") if x.strip()] if sm else []
    arts = []
    m = ART_RE.search(desc)
    if m:
        for piece in re.split(r"[;]", m.group(1)):
            mm = ART_ONE.search(piece.strip())
            if mm:
                arts.append((mm.group(1), mm.group(2).strip()))
    return laws, sr, arts


def main():
    staging = DB_PATH + ".staging"
    if os.path.exists(staging): os.remove(staging)
    shutil.copy2(DB_PATH, staging)
    conn = connect(staging)
    n_law = n_basis = n_svc = 0
    try:
        services = conn.execute(
            "SELECT s.id, s.slug, s.name, f.description FROM service s "
            "JOIN finding f ON f.service_id=s.id "
            "WHERE f.fingerprint LIKE 'autodraft-%'").fetchall()
        for s in services:
            laws, sr, arts = parse_finding(s["description"] or "")
            if not arts and not laws:
                continue
            jur = "federal" if (sr or any("Bundes" in l for l in laws)) else "cantonal"
            law_id = upsert(conn, "law", ["slug"], {
                "slug": f"zit-{s['slug']}", "jurisdiction_level": jur,
                "title": "Im Formular zitiert: " + ("; ".join(laws) if laws else "(siehe Formular)"),
                "short_title": "; ".join(laws)[:60] if laws else "zitiert",
                "sr_number": sr[0] if (jur == "federal" and len(sr) == 1) else None,
                "source_note": f"Verbatim aus Formular/Merkblatt zitiert (SR: {', '.join(sr) or '—'}). "
                               f"NICHT gegen Gesetze/Fedlex verifiziert.",
                "last_checked": CITED}); n_law += 1
            art_ids = []
            for no, det in (arts or [("(siehe Formular)", "")]):
                aid = upsert(conn, "article", ["law_id", "article_no", "heading"], {
                    "law_id": law_id, "article_no": no, "heading": "im Formular zitiert",
                    "text_excerpt": None, "last_checked": CITED})
                art_ids.append((aid, det))
            # field requirements of this service that should carry a basis
            reqs = conn.execute(
                "SELECT DISTINCT r.id FROM requirement r "
                "JOIN service_requirement sr ON sr.requirement_id=r.id "
                "JOIN field_mapping fm ON fm.requirement_id=r.id "
                "WHERE sr.service_id=? AND fm.classification IN ('mapped','identity_part','reason_facet') "
                "AND NOT EXISTS (SELECT 1 FROM requirement_legal_basis b WHERE b.requirement_id=r.id)",
                [s["id"]]).fetchall()
            for r in reqs:
                for aid, det in art_ids:
                    upsert(conn, "requirement_legal_basis", ["requirement_id", "article_id"], {
                        "requirement_id": r["id"], "article_id": aid,
                        "citation_detail": det or None, "last_checked": CITED}); n_basis += 1
            n_svc += 1
        conn.commit()
    except Exception as e:
        conn.close(); os.remove(staging); log("resolve_cited.log", f"ABORT {e!r}")
        print(f"ABORT: {e!r}", file=sys.stderr); sys.exit(1)
    errs = validate(conn); conn.close()
    if errs:
        os.remove(staging); print("ABORT validation:", *errs[:5], sep="\n  ", file=sys.stderr); sys.exit(1)
    os.replace(staging, DB_PATH)
    print(f"attached cited references to {n_svc} services "
          f"({n_law} cited-law records, {n_basis} legal-basis links, all 'cited_unverified')")


if __name__ == "__main__":
    main()
