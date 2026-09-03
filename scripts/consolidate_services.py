#!/usr/bin/env python3
"""Consolidate the Formular-era service rows into the DVSH service universe.

DVSH (and SHEP) are the catalogue of record: a service row that exists only
because a Formular once got its own row should fold into the DVSH service the
Formular belongs to — several Formulare per service is the normal shape.

Stage 1 (this script, mechanical): match our ours-only services' form FILES
against the file names the DVSH model itself declares (sources[].url basename
and originalFilename, documents[].titel/datei, submissionEndpoint.titel).
A form is re-parented only when exactly ONE DVSH service claims its file —
ambiguity is left for the agent pass (stage 2, gated separately).

When a re-parenting empties an ours-only service row, its legacy references
(findings, process steps, service_requirements) move along to the target and
the empty row is deleted. Empty ours-only rows with no references at all are
deleted too. Idempotent. Staging -> validate -> swap.

    python3 scripts/consolidate_services.py
"""
import json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate


def normfile(s):
    s = (s or "").rsplit("/", 1)[-1]
    s = s.rsplit(".", 1)[0] if "." in s else s
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", s)


def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)

    dvsh_of = {}     # service_id -> True for DVSH-linked services
    claims = {}      # normalised filename -> set(target service_id)
    for r in c.execute("SELECT service_id, sources, documents, submission_endpoint "
                       "FROM dvsh_service WHERE service_id IS NOT NULL"):
        dvsh_of[r["service_id"]] = True
        names = []
        for col, keys in (("sources", ("url", "originalFilename", "title")),
                          ("documents", ("datei", "titel"))):
            try:
                for x in json.loads(r[col] or "[]"):
                    for k in keys:
                        if x.get(k):
                            names.append(str(x[k]))
            except Exception:
                pass
        try:
            se = json.loads(r["submission_endpoint"] or "{}")
            if se.get("titel"):
                names.append(se["titel"])
        except Exception:
            pass
        for n in names:
            k = normfile(n)
            if len(k) >= 6:
                claims.setdefault(k, set()).add(r["service_id"])

    moved = ambiguous = 0
    emptied = set()
    for f in c.execute("SELECT f.id, f.service_id, f.source_file, f.title FROM form f "
                       "WHERE f.service_id NOT IN "
                       "(SELECT service_id FROM dvsh_service WHERE service_id IS NOT NULL)").fetchall():
        keys = []
        if f["source_file"]:
            keys.append(normfile(f["source_file"]))
        keys.append(normfile(f["title"]))
        targets = set()
        for k in keys:
            targets |= claims.get(k, set())
        if len(targets) == 1:
            tgt = targets.pop()
            c.execute("UPDATE form SET service_id=?, dvsh_match='konsolidiert (Dateiname im DVSH-Modell)' "
                      "WHERE id=?", [tgt, f["id"]])
            emptied.add(f["service_id"])
            # legacy references follow the Formular to its real service
            for tbl in ("finding", "process_step", "service_requirement"):
                c.execute(f"UPDATE {tbl} SET service_id=? WHERE service_id=?", [tgt, f["service_id"]])
            moved += 1
        elif len(targets) > 1:
            ambiguous += 1

    # drop ours-only rows that now hold nothing at all
    deleted = 0
    for sid in list(emptied) + [r["id"] for r in c.execute(
            "SELECT id FROM service s WHERE NOT EXISTS (SELECT 1 FROM dvsh_service d WHERE d.service_id=s.id) "
            "AND NOT EXISTS (SELECT 1 FROM form f WHERE f.service_id=s.id)")]:
        if c.execute("SELECT 1 FROM form WHERE service_id=?", [sid]).fetchone():
            continue
        if c.execute("SELECT 1 FROM dvsh_service WHERE service_id=?", [sid]).fetchone():
            continue
        busy = any(c.execute(f"SELECT 1 FROM {t} WHERE service_id=?", [sid]).fetchone()
                   for t in ("finding", "process_step", "service_requirement"))
        if busy:
            continue
        c.execute("DELETE FROM service WHERE id=?", [sid])
        deleted += 1
    c.commit()
    errs = validate(c)
    n_total = c.execute("SELECT COUNT(*) n FROM service").fetchone()["n"]
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Stufe 1: {moved} Formulare per Dateinamen-Beleg konsolidiert, {ambiguous} mehrdeutig "
          f"(für die Agenten-Stufe), {deleted} geleerte Zeilen entfernt — {n_total} Services übrig")


if __name__ == "__main__":
    main()
