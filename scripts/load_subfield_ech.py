#!/usr/bin/env python3
"""Apply agent-assigned eCH elements to SUBFIELDS (data_subfield), PROOF-GATED.

The key is the PAIR (parent field, subfield), because the parent decides what the
part means: 'Name' under 'Personalien' is a person's surname (eCH-0044
officialName), 'Name' under 'Angaben zum Hund' is an animal's call name. Keying on
the subfield alone would collapse those.

Same gate as everywhere: an element is accepted only if (standard, element) really
exists in the catalogue. Idempotent. Staging -> validate -> swap.

    python3 scripts/load_subfield_ech.py <sfmap_out-dir|file.json> [--inputs=<sfmap-dir>] [--dry-run]

Two kinds of entry in a zuordnungen list:
  * name-keyed  {elternfeld, teilfeld, standard, element | kein_standard}: applies to
    every subfield with that (parent, part) name pair, across forms (the original
    panel format);
  * id-keyed    {subfield_id, standard, element, kontext? | kein_standard}: applies to
    exactly that row (a reviewed correction of one form, e.g.
    quellen/korrekturen/subfield_ech_form131_2026-09-26.json). 'kontext' (the XSD
    complexType) picks the right row among same-named elements (eCH-0278 has
    several 'amount'); without it the first catalogue row is taken.
An element assigned to a part clears its eSH draft code (convention 7).
"""
import glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect, norm_ascii as norm
from validate_db import validate



def std_code(s):
    m = re.search(r"(\d{1,4})", s or "")
    return f"eCH-{int(m.group(1)):04d}" if m else None


def main():
    srcs = [a for a in sys.argv[1:] if not a.startswith("-")]
    inputs = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--inputs=")]
    dry = "--dry-run" in sys.argv
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    cat, cat_ctx = {}, {}
    for r in c.execute("SELECT id, standard, name, context FROM ech_element"):
        cat.setdefault((r["standard"], r["name"]), r["id"])
        cat.setdefault((r["standard"], r["name"].lower()), r["id"])
        cat_ctx[(r["standard"], r["name"], r["context"] or "")] = r["id"]
    known = {r["code"] for r in c.execute("SELECT code FROM ech_standard")}
    with_xsd = {r["code"] for r in c.execute("SELECT code FROM ech_standard WHERE n_elements>0")}

    # The chunk INPUTS were keyed by (parent standard, subfield) — one representative
    # parent name stands for every parent sharing that standard. The agents echo back
    # only that representative, so applying by parent NAME alone would leave every
    # other parent unassigned. Read the inputs to recover parent name -> standard.
    pstd = {}
    for ind in inputs:
        for jf in sorted(glob.glob(os.path.join(ind, "*.json"))):
            try:
                for it in json.load(open(jf, encoding="utf-8")):
                    if it.get("eltern_standard"):
                        pstd[norm(it.get("elternfeld"))] = it["eltern_standard"]
            except Exception:
                continue

    elem, sonly, none_, rejected = {}, {}, set(), []
    elem_std, none_std = {}, set()          # fallback keyed by (parent standard, subfield)
    by_id = {}                              # subfield_id -> ('elem', eid) | ('none',)
    for src in srcs:
        files = [src] if os.path.isfile(src) else sorted(glob.glob(os.path.join(src, "*.json")))
        for jf in files:
            try:
                d = json.load(open(jf, encoding="utf-8"))
            except Exception:
                continue
            for z in (d.get("zuordnungen", []) if isinstance(d, dict) else d):
                if not isinstance(z, dict):
                    continue
                if z.get("subfield_id") is not None:          # id-keyed: exactly this row
                    sid = int(z["subfield_id"])
                    if z.get("kein_standard"):
                        by_id[sid] = ("none",)
                        continue
                    s_, e_ = std_code(z.get("standard")), (z.get("element") or "").strip()
                    eid = (cat_ctx.get((s_, e_, (z.get("kontext") or "").strip())) if z.get("kontext") else None) \
                          or cat.get((s_, e_)) or cat.get((s_, e_.lower()))
                    if s_ in known and eid:
                        by_id[sid] = ("elem", eid)
                    else:
                        rejected.append(f"{z.get('standard')}:{e_} (id {sid})")
                    continue
                k = (norm(z.get("elternfeld")), norm(z.get("teilfeld")))
                if not k[1]:
                    continue
                ps = pstd.get(k[0])                # standard of the representative parent
                if z.get("kein_standard"):
                    if k not in elem and k not in sonly:
                        none_.add(k)
                    if ps and (ps, k[1]) not in elem_std:
                        none_std.add((ps, k[1]))
                    continue
                s, e = std_code(z.get("standard")), (z.get("element") or "").strip()
                if s not in known:
                    rejected.append(f"{z.get('standard')}:{e}")
                    continue
                eid = cat.get((s, e)) or cat.get((s, e.lower())) if e else None
                if eid:
                    elem[k] = eid; none_.discard(k); sonly.pop(k, None)
                    if ps:
                        elem_std[(ps, k[1])] = eid; none_std.discard((ps, k[1]))
                elif e and s in with_xsd:
                    rejected.append(f"{s}:{e}")
                elif k not in elem:
                    sonly[k] = s; none_.discard(k)

    ne = ns = nn = nfb = 0
    rows = c.execute("""SELECT sf.id, sf.name sn, d.name dn,
                               COALESCE(e.standard, d.ech_standard_code) pstd
                        FROM data_subfield sf JOIN data_field d ON d.id=sf.data_field_id
                        LEFT JOIN ech_element e ON e.id=d.ech_element_id""").fetchall()
    nid = 0
    for r in rows:
        if r["id"] in by_id:                     # a reviewed row-level verdict wins
            v = by_id[r["id"]]
            if v[0] == "elem":
                c.execute("UPDATE data_subfield SET ech_element_id=?, ech_standard_code=NULL,"
                          " ech_status='assigned', esh_code=NULL, esh_element=NULL WHERE id=?", [v[1], r["id"]]); ne += 1
            else:
                c.execute("UPDATE data_subfield SET ech_element_id=NULL, ech_standard_code=NULL,"
                          " ech_status='kein_standard' WHERE id=?", [r["id"]]); nn += 1
            nid += 1
            continue
        k = (norm(r["dn"]), norm(r["sn"]))
        ks = (r["pstd"], norm(r["sn"]))          # same subfield under a same-standard parent
        if k in elem:
            c.execute("UPDATE data_subfield SET ech_element_id=?, ech_standard_code=NULL,"
                      " ech_status='assigned' WHERE id=?", [elem[k], r["id"]]); ne += 1
        elif k in sonly:
            c.execute("UPDATE data_subfield SET ech_element_id=NULL, ech_standard_code=?,"
                      " ech_status='standard_only' WHERE id=?", [sonly[k], r["id"]]); ns += 1
        elif r["pstd"] and ks in elem_std:
            c.execute("UPDATE data_subfield SET ech_element_id=?, ech_standard_code=NULL,"
                      " ech_status='assigned' WHERE id=?", [elem_std[ks], r["id"]]); ne += 1; nfb += 1
        elif k in none_ or (r["pstd"] and ks in none_std):
            c.execute("UPDATE data_subfield SET ech_element_id=NULL, ech_standard_code=NULL,"
                      " ech_status='kein_standard' WHERE id=?", [r["id"]]); nn += 1
    if dry:
        c.close(); os.remove(st)
    else:
        c.commit()
        errs = validate(c)
        c.close()
        if errs:
            os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
        os.replace(st, DB_PATH)
    print(f"Teilfelder: {ne} auf Element-Ebene ({len(elem)} Namens-Schlüssel, {nid} per Zeilen-ID, davon {nfb} über den "
          f"Eltern-Standard zugeordnet), {ns} nur Standard, {nn} 'kein Standard', "
          f"{len(rejected)} REJECTED durch das Katalog-Gate"
          + ("   (dry-run)" if dry else ""))
    if rejected:
        from collections import Counter
        for k, v in Counter(rejected).most_common(8):
            print(f"    rejected: {k} ({v}x)")


if __name__ == "__main__":
    main()
