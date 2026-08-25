#!/usr/bin/env python3
"""Apply the gap-closing verdicts (scratchpad/gap_out/*.json), PROOF-GATED.

Three kinds of item, two target tables:
  teilfeld_offen        -> data_subfield  (a part that had no verdict yet)
  aufgehoben_ersetzen   -> data_field     (was citing a REPEALED standard; either
                           re-pointed to a valid one or honestly dropped)
  kein_standard_pruefen -> data_field     (recall re-check; usually confirms)

A replacement is refused unless it exists in the catalogue AND its standard is not
itself repealed — otherwise this would just move the citation from one withdrawn
standard to another. Idempotent. Staging -> validate -> swap.

    python3 scripts/load_ech_gaps.py <gap_out-dir> [--dry-run]
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
    known = {r["code"] for r in c.execute("SELECT code FROM ech_standard")}
    with_xsd = {r["code"] for r in c.execute("SELECT code FROM ech_standard WHERE n_elements>0")}
    dead = {r["code"] for r in c.execute("SELECT code FROM ech_standard WHERE status='Aufgehoben'")}

    res = []
    for jf in sorted(glob.glob(os.path.join(src, "*.json"))):
        try:
            d = json.load(open(jf, encoding="utf-8"))
        except Exception:
            continue
        res += (d.get("ergebnisse", []) if isinstance(d, dict) else d)

    def resolve(z):
        """-> ('element', id) | ('standard', code) | ('none', None) | ('reject', why)"""
        if z.get("kein_standard"):
            return ("none", None)
        s, e = std_code(z.get("standard")), (z.get("element") or "").strip()
        if s not in known:
            return ("reject", f"unbekannter Standard {z.get('standard')}")
        if s in dead:
            return ("reject", f"{s} ist selbst aufgehoben")
        eid = cat.get((s, e)) or cat.get((s, e.lower())) if e else None
        if eid:
            return ("element", eid)
        if e and s in with_xsd:
            return ("reject", f"erfundenes Element {s}:{e}")
        return ("standard", s)

    nsub = nrep = nrec = ndrop = 0
    rejected = []
    subrows = c.execute("""SELECT sf.id, sf.name sn, d.name dn FROM data_subfield sf
                           JOIN data_field d ON d.id=sf.data_field_id
                           WHERE sf.ech_status IS NULL""").fetchall()
    subidx = {}
    for r in subrows:
        subidx.setdefault((norm(r["dn"]), norm(r["sn"])), []).append(r["id"])

    for z in res:
        task = z.get("aufgabe")
        kind, val = resolve(z)
        if kind == "reject":
            rejected.append(f"{z.get('feld') or z.get('teilfeld')}: {val}")
            continue
        if task == "teilfeld_offen":
            ids = subidx.get((norm(z.get("elternfeld")), norm(z.get("teilfeld"))), [])
            for sid in ids:
                if kind == "element":
                    c.execute("UPDATE data_subfield SET ech_element_id=?, ech_standard_code=NULL,"
                              " ech_status='assigned' WHERE id=?", [val, sid])
                elif kind == "standard":
                    c.execute("UPDATE data_subfield SET ech_element_id=NULL, ech_standard_code=?,"
                              " ech_status='standard_only' WHERE id=?", [val, sid])
                else:
                    c.execute("UPDATE data_subfield SET ech_element_id=NULL, ech_standard_code=NULL,"
                              " ech_status='kein_standard' WHERE id=?", [sid])
                nsub += 1
            continue
        # field-level tasks, matched by normalised field name
        fname = norm(z.get("feld"))
        if not fname:
            continue
        targets = [r["id"] for r in c.execute("SELECT id, name FROM data_field").fetchall()
                   if norm(r["name"]) == fname]
        if task == "aufgehoben_ersetzen":
            # only touch the ones actually citing a repealed standard
            targets = [t for t in targets if c.execute(
                "SELECT 1 FROM data_field d LEFT JOIN ech_element e ON e.id=d.ech_element_id "
                "LEFT JOIN ech_standard s ON s.code=COALESCE(e.standard,d.ech_standard_code) "
                "WHERE d.id=? AND s.status='Aufgehoben'", [t]).fetchone()]
        elif task == "kein_standard_pruefen":
            targets = [t for t in targets if c.execute(
                "SELECT 1 FROM data_field WHERE id=? AND ech_status='kein_standard'", [t]).fetchone()]
        for t in targets:
            if kind == "element":
                c.execute("UPDATE data_field SET ech_element_id=?, ech_standard_code=NULL,"
                          " ech_status='assigned' WHERE id=?", [val, t])
            elif kind == "standard":
                c.execute("UPDATE data_field SET ech_element_id=NULL, ech_standard_code=?,"
                          " ech_status='standard_only' WHERE id=?", [val, t])
            else:
                c.execute("UPDATE data_field SET ech_element_id=NULL, ech_standard_code=NULL,"
                          " ech_status='kein_standard' WHERE id=?", [t])
                ndrop += 1
            if task == "aufgehoben_ersetzen":
                nrep += 1
            else:
                nrec += 1

    if dry:
        c.close(); os.remove(st)
    else:
        c.commit()
        errs = validate(c)
        c.close()
        if errs:
            os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
        os.replace(st, DB_PATH)
    print(f"Teilfelder geschlossen: {nsub} | aufgehobene Zitate ersetzt/entfernt: {nrep} "
          f"(davon {ndrop} ehrlich auf 'kein Standard') | Recall-Prüfungen angewendet: {nrec} | "
          f"{len(rejected)} REJECTED" + ("   (dry-run)" if dry else ""))
    for r in rejected[:8]:
        print(f"    rejected: {r}")


if __name__ == "__main__":
    main()
