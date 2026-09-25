#!/usr/bin/env python3
"""One datum, one name: load the naming panel (plus its sceptical review).

Per eCH element the panel proposes ONE term (the vorschlag) and classifies
every label under which forms ask for that datum:

  vorschlag  the proposed term itself
  variante   same datum, no role, only worded differently -> rename
  rolle      same datum, the label names whose/which one  -> fine as it is
  pruefen    the label promises a different or larger datum -> check the
             eCH assignment or the way the field is cut

Gates: element id must be one that was asked; the vorschlag must be copied
verbatim from that element's own labels (no invented terms); every label must
be one of the asked labels; vocabulary. Review corrections are applied over
the first pass, under the same gates. Labels are matched to fields by their
normalised form (case, whitespace and trailing ':' '*' ignored). Idempotent.
Staging -> validate -> swap.

    python3 scripts/load_begriffe.py <dir-with-in_/out_/verify_*.json>
"""
import glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

VOCAB = {"vorschlag", "variante", "rolle", "pruefen"}
DDL = """
CREATE TABLE IF NOT EXISTS begriff_vorschlag (
    ech_element_id INTEGER PRIMARY KEY REFERENCES ech_element(id),
    term           TEXT NOT NULL,
    begruendung    TEXT,
    zweitgeprueft  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS begriff_label (
    ech_element_id INTEGER NOT NULL REFERENCES ech_element(id),
    label_norm     TEXT NOT NULL,
    label          TEXT NOT NULL,
    klasse         TEXT NOT NULL CHECK(klasse IN ('vorschlag','variante','rolle','pruefen')),
    rolle          TEXT,
    grund          TEXT,
    zweitgeprueft  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (ech_element_id, label_norm)
);
"""


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[:*]+\s*$", "", (s or "").strip())).lower()


def load(pattern):
    out = {}
    for jf in sorted(glob.glob(pattern)):
        try:
            out[os.path.basename(jf).split("_", 1)[1]] = json.load(open(jf, encoding="utf-8"))
        except Exception as e:
            print("  unlesbar:", jf, e)
    return out


def main():
    src = sys.argv[1]
    ins, outs, vers = load(f"{src}/in_*.json"), load(f"{src}/out_*.json"), load(f"{src}/verify_*.json")
    asked = {}                                   # element_id -> {label_norm: label}
    for chunk in ins.values():
        for e in chunk:
            asked[e["element_id"]] = {norm(b["label"]): b["label"] for b in e["bezeichnungen"]}
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    c.execute("DELETE FROM begriff_label"); c.execute("DELETE FROM begriff_vorschlag")
    rej, n_el, n_lab, korr_v, korr_k = [], 0, 0, 0, 0
    counts = {k: 0 for k in VOCAB}
    for key, out in outs.items():
        ver = vers.get(key) or {}
        vk = {v.get("element_id"): v for v in (ver.get("vorschlag_korrekturen") or [])}
        lk = {(v.get("element_id"), norm(v.get("label"))): v for v in (ver.get("korrekturen") or [])}
        for e in out.get("elemente", []):
            eid = e.get("element_id")
            if eid not in asked:
                rej.append(f"element {eid} nicht gefragt"); continue
            labels = asked[eid]
            vor, why, vok = e.get("vorschlag"), e.get("begruendung"), 0
            if eid in vk and norm(vk[eid].get("vorschlag")) in labels:
                vor, why, vok = vk[eid]["vorschlag"], "Zweitprüfung: " + (vk[eid].get("grund") or ""), 1
                korr_v += 1
            if norm(vor) not in labels:
                rej.append(f"element {eid}: Vorschlag «{vor}» ist keine der eigenen Bezeichnungen"); continue
            vor_n = norm(vor)
            c.execute("INSERT INTO begriff_vorschlag VALUES(?,?,?,?)", [eid, labels[vor_n], (why or "")[:300], vok])
            n_el += 1
            seen = set()
            for b in e.get("bezeichnungen", []):
                ln = norm(b.get("label"))
                if ln not in labels or ln in seen:
                    rej.append(f"element {eid}: Bezeichnung «{b.get('label')}» nicht gefragt/doppelt"); continue
                seen.add(ln)
                kl, rolle, grund, geprueft = b.get("klasse"), b.get("rolle"), b.get("grund"), 0
                if (eid, ln) in lk:
                    v = lk[(eid, ln)]
                    if v.get("klasse") in VOCAB:
                        kl, rolle, grund, geprueft = v["klasse"], v.get("rolle"), "Zweitprüfung: " + (v.get("grund") or ""), 1
                        korr_k += 1
                # the proposed term and 'vorschlag' must coincide — exactly one label
                if ln == vor_n:
                    kl = "vorschlag"
                elif kl == "vorschlag":
                    kl, grund = "variante", "gleiches Datum, anders geschrieben als der Vorschlag"
                if kl not in VOCAB:
                    rej.append(f"element {eid}: Klasse «{kl}»"); continue
                c.execute("INSERT INTO begriff_label VALUES(?,?,?,?,?,?,?)",
                          [eid, ln, labels[ln], kl, (rolle or None) if kl == "rolle" else None,
                           (grund or None), geprueft])
                counts[kl] += 1; n_lab += 1
            missing = set(labels) - seen
            for ln in missing:                     # an unanswered label stays unjudged, never guessed
                rej.append(f"element {eid}: «{labels[ln]}» ohne Urteil")
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Begriffe: {n_el} Elemente mit Vorschlag, {n_lab} Bezeichnungen {counts}; "
          f"Zweitprüfung korrigierte {korr_v} Vorschläge und {korr_k} Klassen; {len(rej)} REJECTED")
    for r in rej[:8]:
        print("  ", r)


if __name__ == "__main__":
    main()
