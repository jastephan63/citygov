#!/usr/bin/env python3
"""Load generated QuestionFlows (TurboTax-style guided flows) into citygov.db,
PROOF-GATED.

A flow is only accepted when it is complete and honest:
  * every data field of the Formular appears in AT LEAST one node's `field` list
    OR in `ausgelassen` with a reason — nothing may silently disappear. A composite
    split across several questions is legitimate (that is the product's point);
    Teilfeld names in `field` are repaired back to their parent Datenfeld first.
  * node ids are unique; show_if uses only the simple syntax the player evaluates
    (key == 'x' | key != 'x' | key in ['a','b']) and references a defined key
  * review.highlight entries reference existing node ids
Rejected flows are reported per form and NOT loaded (fix + rerun; idempotent).

    python3 scripts/load_flows.py <flowgen_out-dir> [more dirs...] [--dry-run]
"""
import glob, hashlib, json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

DDL = """
CREATE TABLE IF NOT EXISTS formflow (
    form_id      INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    flow         TEXT NOT NULL,          -- the QuestionFlow JSON
    n_nodes      INTEGER NOT NULL,
    n_ausgelassen INTEGER NOT NULL DEFAULT 0,
    form_hash    TEXT,                   -- sha256 of the source file the flow was derived from
    generated_at TEXT DEFAULT (datetime('now'))
);
"""

SHOWIF = re.compile(r"^\s*(\w+)\s*(==|!=|in)\s*(.+?)\s*$")


def _n(x):
    x = unicodedata.normalize("NFD", (x or "").lower())
    x = "".join(ch for ch in x if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", x)


def repair_fields(flow, dfnames, submap):
    """Agents sometimes put a TEILFELD name (or a slight variant) into node.field.
    Map it back to the parent Datenfeld deterministically; unknowns stay and get
    rejected by the gate. Also dedupes within a node."""
    ndf = {_n(x): x for x in dfnames}
    for n in (flow.get("nodes") or []):
        fs, out = (n.get("field") or []), []
        for f in fs:
            if f in dfnames or f.startswith("Beilage.") or f == "":
                out.append(f); continue
            k = _n(f)
            if k in ndf:
                out.append(ndf[k])
            elif k in submap:
                out.append(submap[k])
            else:
                out.append(f)
        seen, ded = set(), []
        for f in out:
            if f not in seen:
                seen.add(f); ded.append(f)
        n["field"] = ded
    return flow


def check(flow, dfnames):
    """-> list of problems (empty = OK)"""
    probs = []
    nodes = flow.get("nodes") or []
    if not isinstance(nodes, list) or not nodes:
        return ["keine nodes"]
    ids, keys, covered = set(), set(), {}
    for n in nodes:
        nid = n.get("id")
        if not nid or nid in ids:
            probs.append(f"node-id fehlt/doppelt: {nid}")
        ids.add(nid)
        if n.get("key"):
            keys.add(n["key"])
        if n.get("type") not in ("text", "date", "number", "choice", "multiselect",
                                 "form", "roster", "doc_scan", "note", "confirm"):
            probs.append(f"{nid}: unbekannter type {n.get('type')}")
        for f in (n.get("field") or []):
            if f.startswith("Beilage.") or f == "":
                continue
            covered[f] = covered.get(f, 0) + 1
    for n in nodes:
        si = n.get("show_if")
        if si:
            m = SHOWIF.match(si)
            if not m:
                probs.append(f"{n.get('id')}: show_if-Syntax: {si!r}")
            elif m.group(1) not in keys:
                probs.append(f"{n.get('id')}: show_if-Key '{m.group(1)}' ist kein choice-key")
    aus = {(a.get("feld") or "").strip(): (a.get("grund") or "") for a in (flow.get("ausgelassen") or [])}
    for name in dfnames:
        c, inaus = covered.get(name, 0), name in aus
        if c == 0 and not inaus:
            probs.append(f"Datenfeld NICHT abgedeckt: {name!r}")
        elif c >= 1 and inaus:
            probs.append(f"Datenfeld gefragt UND ausgelassen: {name!r}")
    for f in covered:
        if f not in dfnames:
            probs.append(f"field verweist auf unbekanntes Datenfeld: {f!r}")
    for h in ((flow.get("review") or {}).get("highlight") or []):
        if h.get("answer") not in ids:
            probs.append(f"review.highlight verweist auf unbekannten node: {h.get('answer')!r}")
    return probs


def main():
    srcs = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry = "--dry-run" in sys.argv
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)

    ok = bad = 0
    for src in srcs:
        for jf in sorted(glob.glob(os.path.join(src, "*.flow.json"))):
            try:
                flow = json.load(open(jf, encoding="utf-8"))
            except Exception as e:
                print(f"  REJECT {os.path.basename(jf)}: kein JSON ({e})"); bad += 1
                continue
            fid = (flow.get("meta") or {}).get("form_id")
            if not fid or not c.execute("SELECT 1 FROM form WHERE id=?", [fid]).fetchone():
                print(f"  REJECT {os.path.basename(jf)}: form_id {fid!r} unbekannt"); bad += 1
                continue
            dfnames = {r["name"] for r in c.execute(
                "SELECT name FROM data_field WHERE form_id=?", [fid])}
            submap = {}
            for r in c.execute("""SELECT sf.name sn, d.name dn FROM data_subfield sf
                                  JOIN data_field d ON d.id=sf.data_field_id
                                  WHERE d.form_id=?""", [fid]):
                submap.setdefault(_n(r["sn"]), r["dn"])
            flow = repair_fields(flow, dfnames, submap)
            probs = check(flow, dfnames)
            if probs:
                print(f"  REJECT form#{fid} ({os.path.basename(jf)}):")
                for p in probs[:6]:
                    print(f"      - {p}")
                bad += 1
                continue
            # record which edition of the source file this flow was derived from (staleness check)
            sfile = c.execute("SELECT source_file FROM form WHERE id=?", [fid]).fetchone()["source_file"]
            fh = None
            if sfile and os.path.exists(sfile):
                fh = hashlib.sha256(open(sfile, "rb").read()).hexdigest()[:16]
            c.execute("INSERT OR REPLACE INTO formflow(form_id, flow, n_nodes, n_ausgelassen, form_hash) "
                      "VALUES(?,?,?,?,?)",
                      [fid, json.dumps(flow, ensure_ascii=False),
                       len(flow["nodes"]), len(flow.get("ausgelassen") or []), fh])
            ok += 1
    if dry:
        c.close(); os.remove(st)
    else:
        c.commit()
        errs = validate(c)
        c.close()
        if errs:
            os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
        os.replace(st, DB_PATH)
    print(f"Flows geladen: {ok}   abgelehnt: {bad}" + ("   (dry-run)" if dry else ""))


if __name__ == "__main__":
    main()
