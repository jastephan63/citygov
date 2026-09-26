#!/usr/bin/env python3
"""Load the panel's verdicts on WHICH remedy provision governs a form's decision.

load_rechtsmittel.py collects every verified Rechtsmittel provision of the
laws a form cites. Where a law offers several (Steuergesetz: Einsprache gegen
die Veranlagung, Rekurs gegen die Sicherstellung, Aufsichtsbeschwerde ...) the
choice is a legal judgment, not a ranking. The panel reads the form (title,
purpose, kind of decision, office) and the candidate provisions with their
quotes, and returns one of:

  sektoral   regel_id = the provision that governs the applicant's remedy
  allgemein  none of the provisions covers this decision -> VRG general rule
  offen      cannot be decided from the material (stays open, shown as such)

Gate: form must have an outcome, a sektoral verdict must name a regel_id that
is among THAT form's candidates (a provision of a law the form cites), the
reason must be present. Idempotent. Staging -> validate -> swap. Afterwards
run load_rechtsmittel.py again so form_outcome reflects the verdicts.

    python3 scripts/load_rechtsmittel_verdicts.py <dir-with-out_*.json>
"""
import glob, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

DDL = """
CREATE TABLE IF NOT EXISTS rechtsmittel_verdikt (
    form_id      INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    regel_id     INTEGER REFERENCES rechtsmittel_regel(id),
    quelle       TEXT NOT NULL CHECK(quelle IN ('sektoral','allgemein','offen')),
    begruendung  TEXT NOT NULL,
    last_checked TEXT
);
"""


def main():
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    have = {r["form_id"] for r in c.execute("SELECT form_id FROM form_outcome")}
    cands = {}
    # a provision the second review struck is not a remedy and may not be named;
    # the candidate laws are the ones load_rechtsmittel.py uses (fields + DVSH)
    from load_rechtsmittel import cited_laws
    rules_by_law = {}
    for r in c.execute("SELECT id, law_id, article_id, rechtsmittel_art FROM rechtsmittel_regel "
                       "WHERE scope='sektoral' AND COALESCE(gestrichen,0)=0"):
        rules_by_law.setdefault(r["law_id"], []).append(r["id"])
    for fid, laws in cited_laws(c).items():
        for lid in laws:
            for rid in rules_by_law.get(lid, []):
                cands.setdefault(fid, set()).add(rid)
    # a verdict written before the rule had an id names it by (law, article, art)
    by_key = {(r["law_id"], (r["article_no"] or "").strip().lower(), r["rechtsmittel_art"]): r["id"]
              for r in c.execute("SELECT rr.id, rr.law_id, a.article_no, rr.rechtsmittel_art FROM rechtsmittel_regel rr "
                                 "JOIN article a ON a.id=rr.article_id")}
    n = rejected = 0
    counts = {}
    for jf in sorted(glob.glob(os.path.join(src, "out_*.json"))):
        for v in json.load(open(jf, encoding="utf-8")).get("verdicts", []):
            fid, q, rid = v.get("form_id"), v.get("quelle"), v.get("regel_id")
            if rid is None and isinstance(v.get("regel"), dict):
                k = v["regel"]
                rid = by_key.get((k.get("law_id"), (k.get("article_no") or "").strip().lower(), k.get("rechtsmittel_art")))
            why = (v.get("begruendung") or "").strip()
            if fid not in have or q not in ("sektoral", "allgemein", "offen") or len(why) < 8:
                rejected += 1; continue
            if q == "sektoral" and rid not in cands.get(fid, set()):
                rejected += 1; continue
            c.execute("INSERT OR REPLACE INTO rechtsmittel_verdikt(form_id, regel_id, quelle, begruendung, last_checked) "
                      "VALUES(?,?,?,?,?)", [fid, rid if q == "sektoral" else None, q, why[:400], "Panel-Verdikt"])
            counts[q] = counts.get(q, 0) + 1
            n += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"rechtsmittel_verdikt: {n} Verdikte geladen {counts}, {rejected} REJECTED — "
          f"jetzt scripts/load_rechtsmittel.py erneut ausführen")


if __name__ == "__main__":
    main()
