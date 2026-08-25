#!/usr/bin/env python3
"""Apply agent-assigned eCH standards to data fields, PROOF-GATED against the
catalogue swept from the official eCH site (290 standards, 85 of them with XSD).

Three outcomes per field, in descending quality:
  * element level    - (standard, element) really exists in an ingested XSD
                       -> ech_element_id set, ech_status='assigned'
  * standard level   - the standard exists but publishes no XSD (older, mostly
                       process/data standards such as eCH-0012 Parkkarten);
                       the topic is standardised, no citable XML element exists
                       -> ech_standard_code set, ech_status='standard_only'
  * kein Standard    - no eCH standard covers the field
                       -> ech_status='kein_standard'
Anything else (invented element or standard code) is REJECTED, so nothing that
does not exist on ech.ch can enter the databank.

Assignments are made per NORMALISED field name and applied to every data field
sharing that name. Idempotent. Staging -> validate -> swap.

    python3 scripts/load_ech_map.py <out-dir> [<out-dir> ...]
"""
import glob, json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def std_code(s):
    """'ech-0044', 'eCH 0044', '44' -> 'eCH-0044'"""
    m = re.search(r"(\d{1,4})", s or "")
    return f"eCH-{int(m.group(1)):04d}" if m else None


def main():
    srcs = [a for a in sys.argv[1:] if not a.startswith("-")]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    # catalogue = the proof gate
    cat = {}
    for r in c.execute("SELECT id, standard, name FROM ech_element"):
        cat.setdefault((r["standard"], r["name"]), r["id"])
        cat.setdefault((r["standard"], r["name"].lower()), r["id"])
    known_std = {r["code"] for r in c.execute("SELECT code FROM ech_standard")}
    with_xsd = {r["code"] for r in c.execute("SELECT code FROM ech_standard WHERE n_elements>0")}

    elem, sonly, none_, rejected = {}, {}, set(), []
    for src in srcs:
        for jf in sorted(glob.glob(os.path.join(src, "*.json"))):
            try:
                d = json.load(open(jf, encoding="utf-8"))
            except Exception:
                continue
            # agents write either {"zuordnungen": [...]} or a bare list
            zs = d.get("zuordnungen", []) if isinstance(d, dict) else d
            for z in zs:
                if not isinstance(z, dict):
                    continue
                k = norm(z.get("feld"))
                if not k:
                    continue
                if z.get("kein_standard"):
                    if k not in elem and k not in sonly:
                        none_.add(k)
                    continue
                std, el = std_code(z.get("standard")), (z.get("element") or "").strip()
                if std not in known_std:
                    rejected.append(f"{z.get('standard')}:{el}")
                    continue
                eid = cat.get((std, el)) or cat.get((std, el.lower())) if el else None
                if eid:
                    elem[k] = eid
                    none_.discard(k); sonly.pop(k, None)
                elif el and std in with_xsd:
                    # standard HAS an XSD but the named element is not in it -> invented
                    rejected.append(f"{std}:{el}")
                elif k not in elem:
                    sonly[k] = std           # standard without XSD: topic-level match
                    none_.discard(k)

    ne = ns = nn = 0
    for r in c.execute("SELECT id, name FROM data_field").fetchall():
        k = norm(r["name"])
        if k in elem:
            c.execute("UPDATE data_field SET ech_element_id=?, ech_standard_code=NULL,"
                      " ech_status='assigned' WHERE id=?", [elem[k], r["id"]]); ne += 1
        elif k in sonly:
            c.execute("UPDATE data_field SET ech_element_id=NULL, ech_standard_code=?,"
                      " ech_status='standard_only' WHERE id=?", [sonly[k], r["id"]]); ns += 1
        elif k in none_:
            c.execute("UPDATE data_field SET ech_element_id=NULL, ech_standard_code=NULL,"
                      " ech_status='kein_standard' WHERE id=?", [r["id"]]); nn += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"eCH: {ne} fields at element level ({len(elem)} names), "
          f"{ns} at standard level ({len(sonly)} names), "
          f"{nn} 'kein Standard' ({len(none_)} names), "
          f"{len(rejected)} REJECTED by the catalogue gate")
    if rejected:
        from collections import Counter
        for k, v in Counter(rejected).most_common(8):
            print(f"    rejected: {k} ({v}x)")


if __name__ == "__main__":
    main()
