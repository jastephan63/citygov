#!/usr/bin/env python3
"""Apply the adversarial verification verdicts for the NEWEST Formulare only
(fields AND subfields), proof-gated.

load_ech_verdicts.py keys verdicts by field name and applies them to every
field with that name - right for the original corpus, wrong here: the fresh
assignments on forms 468+ include names that older, already verified forms
share, and a second opinion on a new form must not silently re-judge those.
So this loader touches only fields/subfields of forms with id >= FROM_FORM,
and handles the subfield verdicts (keyed by the exact (parent, subfield)
pair) that the original loader does not know.

  korrekt        -> leave as is
  besser         -> re-point to (standard, element); gate: the pair must exist
                    in the catalogue, the standard must not be Aufgehoben
  kein_standard  -> drop the assignment, mark 'kein_standard'

Idempotent. Staging -> validate -> swap.

    python3 scripts/load_ech_verdicts_new.py <dir-with-out_*.json> [--from=468]
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
    src = [a for a in sys.argv[1:] if not a.startswith("-")][0]
    from_form = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--from=")), "468"))
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
    known = {r["code"]: r["status"] for r in c.execute("SELECT code, status FROM ech_standard")}

    def resolve(u):
        """('element', id) | ('standard', code) | None(rejected)"""
        s, e = std_code(u.get("standard")), (u.get("element") or "").strip()
        if s not in known or known[s] in ("Aufgehoben", "Abgelöst"):
            return None
        eid = (cat.get((s, e)) or cat.get((s, e.lower()))) if e else None
        if eid:
            return ("element", eid)
        if e and s in with_xsd:
            return None
        return ("standard", s)

    fld, sub = {}, {}
    ok = rejected = 0
    for jf in sorted(glob.glob(os.path.join(src, "out_*.json"))):
        d = json.load(open(jf, encoding="utf-8"))
        for u in (d.get("urteile", []) if isinstance(d, dict) else d):
            if not isinstance(u, dict):
                continue
            v = (u.get("urteil") or "").strip()
            if v == "korrekt":
                ok += 1; continue
            if v == "kein_standard":
                val = ("none", None)
            elif v == "besser":
                val = resolve(u)
                if val is None:
                    rejected += 1; continue
            else:
                rejected += 1; continue
            if u.get("art") == "teilfeld":
                sub[(norm(u.get("elternfeld")), norm(u.get("teilfeld")))] = val
            else:
                fld[norm(u.get("feld"))] = val

    def apply(table, rid, val):
        if val[0] == "element":
            c.execute(f"UPDATE {table} SET ech_element_id=?, ech_standard_code=NULL, ech_status='assigned' WHERE id=?", [val[1], rid])
        elif val[0] == "standard":
            c.execute(f"UPDATE {table} SET ech_element_id=NULL, ech_standard_code=?, ech_status='standard_only' WHERE id=?", [val[1], rid])
        else:
            c.execute(f"UPDATE {table} SET ech_element_id=NULL, ech_standard_code=NULL, ech_status='kein_standard' WHERE id=?", [rid])

    nf = ns = 0
    for r in c.execute("SELECT id, name FROM data_field WHERE form_id>=?", [from_form]).fetchall():
        v = fld.get(norm(r["name"]))
        if v:
            apply("data_field", r["id"], v); nf += 1
    for r in c.execute("SELECT s.id, d.name p, s.name n FROM data_subfield s JOIN data_field d ON d.id=s.data_field_id "
                       "WHERE d.form_id>=?", [from_form]).fetchall():
        v = sub.get((norm(r["p"]), norm(r["n"])))
        if v:
            apply("data_subfield", r["id"], v); ns += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Urteile (Formulare ab #{from_form}): {ok} korrekt, {len(fld)} Feldnamen und {len(sub)} Teilfeld-Paare "
          f"geändert -> {nf} Felder, {ns} Teilfelder; {rejected} REJECTED")


if __name__ == "__main__":
    main()
