#!/usr/bin/env python3
"""Find near-duplicate Formulare across the catalogue (the Duplikat-Radar).

Compares every form pair on two independent signals — the normalised set of
field names and the set of assigned eCH elements — and persists pairs with a
name-Jaccard >= 0.35 into form_similarity. The verdict column stays NULL for
curation (duplicate_ingest / merge_candidate / template_family / ok); this
script never decides, it only surfaces. Existing verdicts survive re-runs.

    python3 scripts/build_similarity.py
"""
import os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def jac(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)

    names, echs, svc = {}, {}, {}
    for r in c.execute("SELECT d.form_id f, d.name, d.ech_element_id e, fm.service_id s "
                       "FROM data_field d JOIN form fm ON fm.id=d.form_id"):
        names.setdefault(r["f"], set()).add(norm(r["name"]))
        svc[r["f"]] = r["s"]
        if r["e"]:
            echs.setdefault(r["f"], set()).add(r["e"])

    keep = {(r["form_a"], r["form_b"]): (r["verdict"], r["note"]) for r in
            c.execute("SELECT form_a, form_b, verdict, note FROM form_similarity")}
    c.execute("DELETE FROM form_similarity")
    ids = sorted(f for f, s in names.items() if len(s) >= 4)   # tiny forms only make noise
    n = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            jn = jac(names[a], names[b])
            if jn < 0.35:
                continue
            je = jac(echs.get(a, set()), echs.get(b, set())) if (a in echs or b in echs) else None
            v, note = keep.get((a, b), (None, None))
            c.execute("INSERT INTO form_similarity(form_a,form_b,jaccard_names,jaccard_ech,"
                      "verdict,note) VALUES(?,?,?,?,?,?)",
                      [a, b, round(jn, 3), round(je, 3) if je is not None else None, v, note])
            n += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"form_similarity: {n} Paare mit Namens-Jaccard ≥ 0.35 "
          f"({len(keep)} bestehende Verdikte erhalten)")


if __name__ == "__main__":
    main()
