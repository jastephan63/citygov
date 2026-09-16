#!/usr/bin/env python3
"""Load the panel verdicts that split "no explicit legal basis" into its two
very different cases.

no_basis=1 used to mean one thing on every surface: over-collection. But a
field with no article naming it is often still NECESSARY to perform the
task (KDSG Art. 4 Abs. 1 lit. b) — the amount on a payout request, the
applicant's e-mail. Treating that as surplus, or rendering it as a
voluntary question in the flows, would be wrong. So data_field.basis_typ is:

  artikel  — an explicit article names the datum (set mechanically)
  aufgabe  — no explicit norm, but needed to fulfil the task (panel verdict)
  ohne     — surplus for the purpose: real over-collection (panel verdict)
  offen    — no_basis and not yet assessed
  NULL     — basis not researched at all ('zu ermitteln')

Gate: the id must be a no_basis field, the verdict must use the vocabulary,
and a reason must be present. Idempotent. Staging -> validate -> swap.

    python3 scripts/load_basis_typ.py <dir-with-out_*.json>
"""
import glob, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

VOCAB = {"aufgabe", "ohne", "offen"}

# One rule the panel applied inconsistently (75:13), settled here so the
# surfaces do not contradict each other: an OPTIONAL free-text Bemerkungen box
# is not a targeted collection by the office - the applicant decides whether
# and what to write, and it is the normal channel for explaining the
# particulars of one's own case. That is task-related, not surplus.
# Only optional fields named like a remarks box are touched.
HARMONISE_WHY = ("Freiwilliges Freitextfeld: keine gezielte Erhebung durch die Stelle, "
                 "die gesuchstellende Person entscheidet selbst, ob und was sie zur "
                 "Erläuterung ihres Falls angibt (Regel der Databank, einheitlich angewandt)")
HARMONISE_SQL = """
UPDATE data_field SET basis_typ='aufgabe', basis_begruendung=?
WHERE no_basis=1 AND required=0 AND basis_typ IN ('ohne','offen')
  AND id NOT IN (SELECT data_field_id FROM data_field_legal_basis)
  AND (name LIKE 'Bemerkung%' OR name LIKE '%Bemerkungen%' OR name LIKE 'Anmerkung%')
"""


def main():
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    # only fields with no explicit article are the panel's to judge; a field
    # that has one keeps 'artikel' whatever the flag says
    nb = {r["id"] for r in c.execute(
        "SELECT id FROM data_field WHERE no_basis=1 AND id NOT IN "
        "(SELECT data_field_id FROM data_field_legal_basis)")}
    n = rejected = 0
    counts = {}
    for jf in sorted(glob.glob(os.path.join(src, "out_*.json"))):
        for v in json.load(open(jf, encoding="utf-8")).get("verdicts", []):
            fid, bt, why = v.get("id"), v.get("basis_typ"), (v.get("begruendung") or "").strip()
            if fid not in nb or bt not in VOCAB or len(why) < 8:
                rejected += 1
                continue
            c.execute("UPDATE data_field SET basis_typ=?, basis_begruendung=? WHERE id=?",
                      [bt, why[:240], fid])
            counts[bt] = counts.get(bt, 0) + 1
            n += 1
    harmonised = c.execute(HARMONISE_SQL, [HARMONISE_WHY]).rowcount
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"basis_typ: {n} Verdikte geladen {counts}, {rejected} REJECTED, "
          f"{harmonised} Bemerkungsfelder vereinheitlicht")


if __name__ == "__main__":
    main()
