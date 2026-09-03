#!/usr/bin/env python3
"""Apply the agent service-consolidation verdicts, PROOF-GATED.

Gates: the target must be a real, DVSH-linked service; confidence must use the
vocabulary; only 'sicher' and 'wahrscheinlich' are applied ('kein_match' rows
stay as honest ours-only services — DVSH has simply not modelled them yet).
Re-parented Formulare carry the verdict + Beleg in form.dvsh_match; legacy
references (findings, process steps, service_requirements) move along; emptied
rows are deleted. Idempotent. Staging -> validate -> swap.

    python3 scripts/apply_consolidation.py <dir-with-cons_out_*.json>
"""
import glob, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

CONF = {"sicher", "wahrscheinlich", "kein_match"}


def main():
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    dvsh_linked = {r["service_id"] for r in c.execute(
        "SELECT DISTINCT service_id FROM dvsh_service WHERE service_id IS NOT NULL")}

    applied = kept = rejected = 0
    emptied = set()
    for jf in sorted(glob.glob(os.path.join(src, "cons_out_*.json"))):
        for z in json.load(open(jf, encoding="utf-8")).get("zuordnungen", []):
            sid, tgt, conf = z.get("service_id"), z.get("target_service_id"), z.get("confidence")
            if conf not in CONF:
                rejected += 1; continue
            if conf == "kein_match" or not tgt:
                kept += 1; continue
            if tgt not in dvsh_linked or tgt == sid:
                rejected += 1; continue
            if not c.execute("SELECT 1 FROM service WHERE id=?", [sid]).fetchone():
                continue                       # already consolidated on a re-run
            beleg = (z.get("beleg") or "")[:180]
            c.execute("UPDATE form SET service_id=?, dvsh_match=? WHERE service_id=?",
                      [tgt, f"zuordnung ({conf}): {beleg}", sid])
            for tbl in ("finding", "process_step", "service_requirement"):
                # move references; a duplicate already present at the target
                # (legacy UNIQUE constraints) is simply dropped
                c.execute(f"UPDATE OR IGNORE {tbl} SET service_id=? WHERE service_id=?", [tgt, sid])
                c.execute(f"DELETE FROM {tbl} WHERE service_id=?", [sid])
            emptied.add(sid)
            applied += 1

    deleted = 0
    for sid in emptied:
        if c.execute("SELECT 1 FROM form WHERE service_id=?", [sid]).fetchone():
            continue
        c.execute("DELETE FROM service WHERE id=?", [sid])
        deleted += 1
    c.commit()
    errs = validate(c)
    n = c.execute("SELECT COUNT(*) n FROM service").fetchone()["n"]
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"konsolidiert: {applied} Services in ihr DVSH-Pendant gefaltet ({deleted} Zeilen entfernt), "
          f"{kept} bleiben ehrlich ours-only, {rejected} REJECTED — {n} Services übrig")


if __name__ == "__main__":
    main()
