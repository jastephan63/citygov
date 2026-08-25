#!/usr/bin/env python3
"""Apply the adversarial verification verdicts on eCH assignments.

The proof gate in load_ech_map.py only proves an element EXISTS in the official
catalogue — not that it is the semantically right one. A second, critical pass
re-judges every assignment; this script applies its verdicts, under the same
gate (a replacement element must itself exist in the catalogue).

  korrekt        -> leave as is
  besser         -> re-point to the named (standard, element), gate-checked
  kein_standard  -> drop the assignment, mark the field 'kein_standard'

Assignments are keyed by NORMALISED field name, as everywhere else. Idempotent.
Staging -> validate -> swap.

    python3 scripts/load_ech_verdicts.py <echver_out-dir> [--dry-run]
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
    m = re.search(r"(\d{1,4})", s or "")
    return f"eCH-{int(m.group(1)):04d}" if m else None


def main():
    srcs = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry = "--dry-run" in sys.argv
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    cat = {}
    for r in c.execute("SELECT id, standard, name FROM ech_element"):
        cat.setdefault((r["standard"], r["name"]), r["id"])
        cat.setdefault((r["standard"], r["name"].lower()), r["id"])
    with_xsd = {r["code"] for r in c.execute("SELECT code FROM ech_standard WHERE n_elements>0")}
    known = {r["code"] for r in c.execute("SELECT code FROM ech_standard")}

    better, drop, rejected, ok = {}, set(), [], 0
    for src in srcs:
        for jf in sorted(glob.glob(os.path.join(src, "*.json"))):
            try:
                d = json.load(open(jf, encoding="utf-8"))
            except Exception:
                continue
            # agents write either {"urteile": [...]} or a bare list
            for u in (d.get("urteile", []) if isinstance(d, dict) else d):
                if not isinstance(u, dict):
                    continue
                k = norm(u.get("feld"))
                if not k:
                    continue
                v = (u.get("urteil") or "").strip()
                if v == "korrekt":
                    ok += 1
                elif v == "kein_standard":
                    drop.add(k)
                elif v == "besser":
                    s, e = std_code(u.get("standard")), (u.get("element") or "").strip()
                    if s not in known:
                        rejected.append(f"{u.get('standard')}:{e}"); continue
                    eid = cat.get((s, e)) or cat.get((s, e.lower())) if e else None
                    if eid:
                        better[k] = ("element", eid)
                    elif e and s in with_xsd:
                        rejected.append(f"{s}:{e}")           # invented element name
                    else:
                        better[k] = ("standard", s)

    nb = nd = 0
    for r in c.execute("SELECT id, name FROM data_field").fetchall():
        k = norm(r["name"])
        if k in better:
            kind, val = better[k]
            if kind == "element":
                c.execute("UPDATE data_field SET ech_element_id=?, ech_standard_code=NULL,"
                          " ech_status='assigned' WHERE id=?", [val, r["id"]])
            else:
                c.execute("UPDATE data_field SET ech_element_id=NULL, ech_standard_code=?,"
                          " ech_status='standard_only' WHERE id=?", [val, r["id"]])
            nb += 1
        elif k in drop:
            c.execute("UPDATE data_field SET ech_element_id=NULL, ech_standard_code=NULL,"
                      " ech_status='kein_standard' WHERE id=?", [r["id"]]); nd += 1
    print(f"Urteile: {ok} korrekt, {len(better)} Namen umgehängt ({nb} Felder), "
          f"{len(drop)} Namen auf 'kein Standard' ({nd} Felder), "
          f"{len(rejected)} Ersatzvorschläge REJECTED durch das Katalog-Gate")
    if rejected:
        from collections import Counter
        for k, v in Counter(rejected).most_common(8):
            print(f"    rejected: {k} ({v}x)")
    if dry:
        c.close(); os.remove(st); print("(dry-run — nichts geschrieben)"); return
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print("angewendet.")


if __name__ == "__main__":
    main()
