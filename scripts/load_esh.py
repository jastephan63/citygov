#!/usr/bin/env python3
"""Load the eSH (E-Schaffhausen) DRAFT standard catalogue + assignments.

eSH is the canton's own PROPOSED standard covering every data point eCH does
not. It is an ENTWURF: nothing here is official, and the dashboard must label it
as such. Gate:
  * assignments only to codes present in the catalogue
  * element names must be eCH-style camelCase (^[a-z][a-zA-Z0-9]{2,50}$)
  * one normalised field name -> ONE element (first-majority wins), so the same
    datum is named identically across all offices
  * only fields/subfields with ech_status='kein_standard' receive an eSH code
    (eSH never shadows an existing eCH assignment)

    python3 scripts/load_esh.py <katalog.json> <assign-dir> [--dry-run]
"""
import collections, glob, json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

EL = re.compile(r"^[a-z][a-zA-Z0-9]{2,50}$")


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    katp, srcdir = sys.argv[1], sys.argv[2]
    dry = "--dry-run" in sys.argv
    k = json.load(open(katp, encoding="utf-8"))
    kat = k.get("katalog", k) if isinstance(k, dict) else k
    codes = {x["code"] for x in kat}

    # collect votes per normalised name -> (code, element)
    votes = collections.defaultdict(collections.Counter)
    rejected = []
    for jf in sorted(glob.glob(os.path.join(srcdir, "*.json"))):
        try:
            d = json.load(open(jf, encoding="utf-8"))
        except Exception:
            continue
        for z in (d.get("zuordnungen", []) if isinstance(d, dict) else d):
            if not isinstance(z, dict):
                continue
            name, code, el = z.get("name"), (z.get("code") or "").strip(), (z.get("element") or "").strip()
            if code not in codes:
                rejected.append(f"code {code!r} ({name})"); continue
            if not EL.match(el):
                rejected.append(f"element {el!r} ({name})"); continue
            votes[norm(name)][(code, el)] += 1
    final = {k_: c.most_common(1)[0][0] for k_, c in votes.items()}

    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.execute("""CREATE TABLE IF NOT EXISTS esh_standard(
        code TEXT PRIMARY KEY, titel TEXT NOT NULL, beschreibung TEXT, themen TEXT,
        status TEXT DEFAULT 'entwurf', n_felder INTEGER DEFAULT 0)""")
    # idempotent reload: clear references first, else the DELETE trips the FK
    c.execute("UPDATE data_field SET esh_code=NULL, esh_element=NULL WHERE esh_code IS NOT NULL")
    c.execute("UPDATE data_subfield SET esh_code=NULL, esh_element=NULL WHERE esh_code IS NOT NULL")
    c.execute("DELETE FROM esh_standard")
    for x in kat:
        c.execute("INSERT INTO esh_standard(code,titel,beschreibung,themen) VALUES(?,?,?,?)",
                  [x["code"], x["titel"][:160], (x.get("beschreibung") or "")[:600],
                   json.dumps(x.get("themen") or [], ensure_ascii=False)])

    nf = ns = 0
    for r in c.execute("SELECT id, name FROM data_field WHERE ech_status='kein_standard'").fetchall():
        hit = final.get(norm(r["name"]))
        if hit:
            c.execute("UPDATE data_field SET esh_code=?, esh_element=? WHERE id=?",
                      [hit[0], hit[1], r["id"]]); nf += 1
    for r in c.execute("""SELECT sf.id, d.name dn, sf.name sn FROM data_subfield sf
                          JOIN data_field d ON d.id=sf.data_field_id
                          WHERE sf.ech_status='kein_standard'""").fetchall():
        hit = final.get(norm(r["dn"] + " › " + r["sn"])) or final.get(norm(r["sn"]))
        if hit:
            c.execute("UPDATE data_subfield SET esh_code=?, esh_element=? WHERE id=?",
                      [hit[0], hit[1], r["id"]]); ns += 1
    for code, in c.execute("SELECT code FROM esh_standard").fetchall():
        n = c.execute("SELECT (SELECT count(*) FROM data_field WHERE esh_code=?) + "
                      "(SELECT count(*) FROM data_subfield WHERE esh_code=?)", [code, code]).fetchone()[0]
        c.execute("UPDATE esh_standard SET n_felder=? WHERE code=?", [n, code])

    if dry:
        c.close(); os.remove(st)
    else:
        c.commit()
        errs = validate(c)
        c.close()
        if errs:
            os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
        os.replace(st, DB_PATH)
    print(f"eSH: {len(kat)} Standards, {nf} Felder + {ns} Teilfelder zugeordnet "
          f"({len(final)} Namen), {len(rejected)} REJECTED" + ("  (dry-run)" if dry else ""))
    for x in rejected[:6]:
        print("    rejected:", x)


if __name__ == "__main__":
    main()
