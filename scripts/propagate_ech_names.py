#!/usr/bin/env python3
"""Close eCH gaps mechanically where the databank already knows the answer.

eCH verdicts are keyed by the normalised field name (load_ech_map.py) and, for
subfields, by the (parent, subfield) pair (load_subfield_ech.py). A field on a
newly added Formular that carries a name the databank has ALREADY judged - and
judged consistently, one verdict only - gets that verdict copied. Nothing new
is invented: every element id copied already passed the catalogue gate once.

Names with conflicting verdicts elsewhere, or never judged, are left NULL for
the panel. Idempotent. Staging -> validate -> swap.

    python3 scripts/propagate_ech_names.py
"""
import os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect, norm_ascii as norm
from validate_db import validate



def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    # provenance: a copied verdict is weaker evidence than a judged one - it is
    # marked so the verification pass (and any reader) can tell them apart
    for tbl in ("data_field", "data_subfield"):
        if "ech_herkunft" not in {r[1] for r in c.execute(f"PRAGMA table_info({tbl})")}:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN ech_herkunft TEXT")
    known, seen_n = {}, {}
    for r in c.execute("SELECT name, ech_status, ech_element_id, ech_standard_code, esh_code, esh_element "
                       "FROM data_field WHERE ech_status IS NOT NULL"):
        k = norm(r["name"])
        known.setdefault(k, set()).add(
            (r["ech_status"], r["ech_element_id"], r["ech_standard_code"], r["esh_code"], r["esh_element"]))
        seen_n[k] = seen_n.get(k, 0) + 1
    nf = 0
    for r in c.execute("SELECT id, name FROM data_field WHERE ech_status IS NULL").fetchall():
        v = known.get(norm(r["name"]))
        if v and len(v) == 1:
            status, eid, std, esh, eshel = next(iter(v))
            c.execute("UPDATE data_field SET ech_status=?, ech_element_id=?, ech_standard_code=?, "
                      "esh_code=?, esh_element=?, ech_herkunft=? WHERE id=?",
                      [status, eid, std, esh, eshel,
                       f"propagiert (Name {seen_n.get(norm(r['name']), 0)}x geprüft)", r["id"]])
            nf += 1
    ks = {}
    for r in c.execute("SELECT d.name p, s.name n, s.ech_status, s.ech_element_id, s.ech_standard_code, "
                       "s.esh_code, s.esh_element FROM data_subfield s JOIN data_field d ON d.id=s.data_field_id "
                       "WHERE s.ech_status IS NOT NULL"):
        ks.setdefault((norm(r["p"]), norm(r["n"])), set()).add(
            (r["ech_status"], r["ech_element_id"], r["ech_standard_code"], r["esh_code"], r["esh_element"]))
    ns = 0
    for r in c.execute("SELECT s.id, d.name p, s.name n FROM data_subfield s JOIN data_field d ON d.id=s.data_field_id "
                       "WHERE s.ech_status IS NULL").fetchall():
        v = ks.get((norm(r["p"]), norm(r["n"])))
        if v and len(v) == 1:
            status, eid, std, esh, eshel = next(iter(v))
            c.execute("UPDATE data_subfield SET ech_status=?, ech_element_id=?, ech_standard_code=?, "
                      "esh_code=?, esh_element=?, ech_herkunft='propagiert' WHERE id=?",
                      [status, eid, std, esh, eshel, r["id"]])
            ns += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"eCH propagated by known name: {nf} Felder, {ns} Teilfelder")


if __name__ == "__main__":
    main()
