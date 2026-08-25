#!/usr/bin/env python3
"""Load parsed DVSH modeller services into the databank (authoritative source).

DVSH is the canton's own curated service model; per the user its legal bases are
AUTHORITATIVE. Stored verbatim in `dvsh_service` (never merged into our derived
tables) and matched to our services by name/Dienststelle so the dashboard can
show the official model next to our field-level analysis.

    python3 scripts/load_dvsh.py <parsed.json>
"""
import json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

DDL = """
CREATE TABLE IF NOT EXISTS dvsh_service (
    dvsh_id      INTEGER PRIMARY KEY,
    slug         TEXT,
    title        TEXT,
    version      TEXT,
    department   TEXT,
    dienststelle TEXT,
    kurzbeschreibung TEXT,
    beschreibung TEXT,
    voraussetzungen  TEXT,   -- JSON array
    unterlagen   TEXT,       -- JSON array
    ablauf       TEXT,       -- JSON array
    bearbeitungsdauer TEXT,
    fristen      TEXT,
    gebuehren    TEXT,
    recht_kantonal TEXT,     -- JSON array [{titel, ssr}]
    recht_bund   TEXT,       -- JSON array [{titel, sr}]
    externe_links TEXT,      -- JSON array
    abgabe       TEXT,       -- JSON array
    kontakt      TEXT,       -- JSON array
    service_id   INTEGER REFERENCES service(id),   -- our matched service (nullable)
    match_kind   TEXT        -- file | exact | normalized | fuzzy | none
);
CREATE INDEX IF NOT EXISTS idx_dvsh_service ON dvsh_service(service_id);
"""


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u"), ("ss", "s")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "", s)


def toks(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return {t for t in re.findall(r"[a-z]{4,}", s)}


def main():
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    ours = c.execute("SELECT id, name, dienststelle FROM service").fetchall()
    by_norm = {}
    for r in ours:
        by_norm.setdefault(norm(r["name"]), []).append(r)
    # strongest signal: the real source filename DVSH built the service from
    by_file = {}
    for r in c.execute("SELECT f.source_file, s.id sid FROM form f JOIN service s ON s.id=f.service_id"):
        by_file[norm(os.path.basename(r["source_file"]))] = r["sid"]

    counts = {"file": 0, "exact": 0, "normalized": 0, "fuzzy": 0, "none": 0}
    for d in data:
        sid, kind = None, "none"
        for f in (d.get("source_files") or []):          # 1) filename identity
            if norm(f) in by_file:
                sid, kind = by_file[norm(f)], "file"
                break
        if not sid:                                       # 2) title identity
            cands = by_norm.get(norm(d["title"]), [])
            if cands:
                same = [r for r in cands if norm(r["dienststelle"]) == norm(d.get("dienststelle"))]
                pick = same[0] if same else cands[0]
                sid, kind = pick["id"], ("exact" if same else "normalized")
        if not sid:                                       # 3) token overlap in same office
            dt = toks(d["title"]) | toks(d.get("kurzbeschreibung", "")[:120])
            best, score = None, 0.0
            for r in ours:
                if norm(r["dienststelle"]) != norm(d.get("dienststelle")):
                    continue
                rt = toks(r["name"])
                if not dt or not rt:
                    continue
                j = len(dt & rt) / len(rt)               # coverage of OUR name by DVSH text
                if j > score:
                    best, score = r, j
            if best and score >= 0.6:
                sid, kind = best["id"], "fuzzy"
        counts[kind] += 1
        c.execute("""INSERT OR REPLACE INTO dvsh_service
            (dvsh_id,slug,title,version,department,dienststelle,kurzbeschreibung,beschreibung,
             voraussetzungen,unterlagen,ablauf,bearbeitungsdauer,fristen,gebuehren,
             recht_kantonal,recht_bund,externe_links,abgabe,kontakt,service_id,match_kind)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [d["dvsh_id"], d.get("slug"), d.get("title"), d.get("version"),
             d.get("department"), d.get("dienststelle"), d.get("kurzbeschreibung"),
             d.get("beschreibung"),
             json.dumps(d.get("voraussetzungen") or [], ensure_ascii=False),
             json.dumps(d.get("erforderliche_unterlagen") or [], ensure_ascii=False),
             json.dumps(d.get("ablauf") or [], ensure_ascii=False),
             d.get("bearbeitungsdauer"), d.get("fristen"), d.get("gebuehren"),
             json.dumps(d.get("rechtsgrundlagen_kantonal") or [], ensure_ascii=False),
             json.dumps(d.get("rechtsgrundlagen_bund") or [], ensure_ascii=False),
             json.dumps(d.get("externe_links") or [], ensure_ascii=False),
             json.dumps(d.get("abgabe") or [], ensure_ascii=False),
             json.dumps(d.get("kontakt") or [], ensure_ascii=False), sid, kind])
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    matched = sum(v for k, v in counts.items() if k != "none")
    print(f"loaded {len(data)} DVSH services | matched {matched}: "
          f"file {counts['file']}, exact {counts['exact']}, normalized {counts['normalized']}, "
          f"fuzzy {counts['fuzzy']} | unmatched {counts['none']}")


if __name__ == "__main__":
    main()
