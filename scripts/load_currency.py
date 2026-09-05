#!/usr/bin/env python3
"""Merge the two currency sweeps into a per-Formular verdict (table form_check).

Sources:
  * sh.ch CMS sweep   (onlinecheck/results.json)  — file found online? byte-identical?
  * DVSH re-read      (dvshcheck/out/*.json)      — which files does the modeller
                        reference TODAY, vs the July snapshot and our holdings

Verdicts (pessimistic signals win):
  aktuell            our copy is what's online / what DVSH references today
  veraltet_verdacht  a differing or newer-year edition exists online or in DVSH
  nicht_gefunden     no online trace found (sh.ch + DVSH) — possibly out of use,
                     possibly hosted elsewhere; listed for the websearch tail
  lokal_fehlt        we have no local source file to compare

Idempotent. Staging -> validate -> swap.

    python3 scripts/load_currency.py <onlinecheck-dir> <dvshcheck-out-dir> [--dry-run]
"""
import glob, json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

DDL = """
CREATE TABLE IF NOT EXISTS form_check (
    form_id     INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    status      TEXT NOT NULL,
    quelle      TEXT,
    online_name TEXT,
    online_url  TEXT,
    dvsh_neu    TEXT,
    note        TEXT,
    checked_at  TEXT DEFAULT (datetime('now'))
);
"""


def nf(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", s)


def stem_year(name):
    """('stem without year tokens', max year seen as int|None) — handles 2024,
    '25-p' style 2-digit stamps and plain 2-digit tokens before the extension."""
    base = os.path.splitext(name or "")[0]
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", base)]
    for m in re.findall(r"[-_](\d\d)[-_]?p?$", base) + re.findall(r"[-_](\d\d)[-_]p\b", base):
        y = int(m)
        if 15 <= y <= 35:
            years.append(2000 + y)
    stem = re.sub(r"\b20\d\d\b", "", base)
    stem = re.sub(r"[-_]\d\d([-_]p)?$", "", stem)
    return nf(stem), (max(years) if years else None)


def main():
    ocdir, dvdir = sys.argv[1], sys.argv[2]
    dry = "--dry-run" in sys.argv
    oc = {}
    p = os.path.join(ocdir, "results.json")
    if os.path.exists(p):
        oc = {int(k): v for k, v in json.load(open(p, encoding="utf-8")).items()}
    now_files = {}                       # dvsh_id -> [files referenced today]
    for jf in sorted(glob.glob(os.path.join(dvdir, "*.json"))):
        try:
            d = json.load(open(jf, encoding="utf-8"))
        except Exception:
            continue
        for s in (d.get("services") or []):
            now_files[s["dvsh_id"]] = s.get("dateien_jetzt") or []

    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)

    # form -> linked dvsh ids
    fdv = {}
    for r in c.execute("""SELECT f.id fid, dv.dvsh_id FROM form f
                          JOIN service s ON s.id=f.service_id
                          JOIN dvsh_service dv ON dv.service_id=s.id"""):
        fdv.setdefault(r["fid"], []).append(r["dvsh_id"])

    from collections import Counter
    stats = Counter()
    for f in c.execute("SELECT id, source_file FROM form").fetchall():
        fid = f["id"]
        base = os.path.basename(f["source_file"] or "")
        mystem, myyear = stem_year(base)
        o = oc.get(fid, {})
        status, quelle, note, dvneu = None, [], [], None

        if o.get("status") == "aktuell":
            status = "aktuell"; quelle.append("sh.ch")
        elif o.get("status") == "aktualisiert":
            status = "veraltet_verdacht"; quelle.append("sh.ch")
            note.append("sh.ch liefert gleichnamige Datei mit anderem Inhalt")
        elif o.get("status") == "lokal_fehlt":
            status = "lokal_fehlt"

        seen_dvsh = False
        for dvid in fdv.get(fid, []):
            for name in now_files.get(dvid, []):
                nstem, nyear = stem_year(name)
                if nf(name) == nf(base):
                    seen_dvsh = True
                    if status != "veraltet_verdacht":
                        status = status or "aktuell"
                    if "DVSH" not in quelle:
                        quelle.append("DVSH")
                elif nstem and nstem == mystem:
                    seen_dvsh = True
                    if nyear and myyear and nyear > myyear:
                        status = "veraltet_verdacht"; dvneu = name
                        note.append(f"DVSH referenziert neuere Ausgabe: {name}")
                        if "DVSH" not in quelle:
                            quelle.append("DVSH")
                    elif not myyear and nyear:
                        note.append(f"DVSH-Jahresvariante: {name}")
        if fdv.get(fid) and not seen_dvsh and base:
            note.append("von DVSH nicht (mehr) referenziert")

        if not status:
            status = "nicht_gefunden"
        c.execute("INSERT OR REPLACE INTO form_check(form_id,status,quelle,online_name,"
                  "online_url,dvsh_neu,note) VALUES(?,?,?,?,?,?,?)",
                  [fid, status, "+".join(quelle) or None, o.get("online_name"),
                   o.get("url"), dvneu, "; ".join(note) or None])
        stats[status] += 1

    if dry:
        c.close(); os.remove(st)
    else:
        c.commit()
        errs = validate(c)
        c.close()
        if errs:
            os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
        os.replace(st, DB_PATH)
    print("form_check:", dict(stats), ("  (dry-run)" if dry else ""))


if __name__ == "__main__":
    main()
