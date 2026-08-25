#!/usr/bin/env python3
"""Apply the duplicate-Formular verdicts (scratchpad/dup2_out/*.json).

Removals are destructive, so this is deliberately conservative:
  * a group must keep at least one service, else it is skipped
  * before deleting a service, its DVSH link and in_dvsh flag MOVE to the
    survivor — otherwise dropping an older Formular would silently lose the
    authoritative DVSH modelling attached to it
  * child rows are deleted explicitly in dependency order (no reliance on
    cascades), so no orphans can survive
  * 'kopie'/'veraltet' inside ONE service removes the duplicate FORM only

Staging -> validate -> swap.

    python3 scripts/apply_dedup.py <dup2_out-dir> [--apply]
"""
import glob, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate


def main():
    src = [a for a in sys.argv[1:] if not a.startswith("-")][0]
    apply = "--apply" in sys.argv
    groups = []
    for jf in sorted(glob.glob(os.path.join(src, "*.json"))):
        try:
            d = json.load(open(jf, encoding="utf-8"))
        except Exception:
            continue
        groups += (d.get("gruppen", []) if isinstance(d, dict) else d)

    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)

    drop_svc, drop_form, rename, plan = {}, {}, {}, []
    for g in groups:
        # renames apply regardless of the verdict
        for r in g.get("umbenennen") or []:
            if r.get("service_id") and (r.get("name") or "").strip():
                rename[r["service_id"]] = r["name"].strip()[:160]
        if g.get("urteil") == "verschieden":
            continue
        keep = [s for s in (g.get("behalten") or []) if s]
        if not keep:
            print(f"  SKIP {g.get('gruppe')}: kein 'behalten'"); continue
        for s in (g.get("entfernen") or []):
            if s in keep:
                continue
            drop_svc[s] = (keep[0], g.get("gruppe"), g.get("begruendung", ""))
        for f in (g.get("formular_entfernen") or []):
            drop_form[f] = (g.get("gruppe"), g.get("begruendung", ""))

    # resolve each service marked for removal; skip ids that no longer exist
    for sid, (keep, grp, why) in list(drop_svc.items()):
        row = c.execute("SELECT name, COALESCE(in_dvsh,0) dv FROM service WHERE id=?", [sid]).fetchone()
        if not row:
            del drop_svc[sid]; continue
        plan.append((sid, row["name"], keep, row["dv"], grp, why))

    print(f"Services zu entfernen: {len(drop_svc)}   Formulare zu entfernen: {len(drop_form)}"
          f"   Umbenennungen: {len(rename)}")
    for sid, name, keep, dv, grp, why in plan:
        k = c.execute("SELECT name FROM service WHERE id=?", [keep]).fetchone()
        print(f"  − #{sid} {name[:52]}")
        print(f"      → bleibt: #{keep} {(k['name'] if k else '?')[:52]}"
              f"{'   [DVSH-Verknüpfung wird übertragen]' if dv else ''}")
    for fid, (grp, why) in drop_form.items():
        r = c.execute("SELECT f.title, f.source_file FROM form f WHERE f.id=?", [fid]).fetchone()
        if r:
            print(f"  − Formular #{fid} {os.path.basename(r['source_file'] or '')[:60]}")

    if not apply:
        c.close(); os.remove(st); print("(dry-run — pass --apply)"); return

    nd = nf = 0
    for sid, name, keep, dv, grp, why in plan:
        # 1. move the authoritative DVSH modelling to the survivor
        c.execute("UPDATE dvsh_service SET service_id=? WHERE service_id=?", [keep, sid])
        if dv:
            c.execute("UPDATE service SET in_dvsh=1 WHERE id=?", [keep])
        # 2. delete this service's forms and their children, deepest first;
        #    their inventory documents get repointed to a form of the survivor
        sv = c.execute("SELECT id FROM form WHERE service_id=? ORDER BY id LIMIT 1", [keep]).fetchone()
        fids = [r["id"] for r in c.execute("SELECT id FROM form WHERE service_id=?", [sid])]
        for fid in fids:
            _drop_form(c, fid, sv["id"] if sv else None, why[:90])
        for t in ("service_requirement", "process_step", "finding"):
            c.execute(f"DELETE FROM {t} WHERE service_id=?", [sid])
        c.execute("DELETE FROM service WHERE id=?", [sid])
        nd += 1
    for fid, (grp, why) in drop_form.items():
        row = c.execute("SELECT service_id FROM form WHERE id=?", [fid]).fetchone()
        if not row:
            continue
        sv = c.execute("SELECT id FROM form WHERE service_id=? AND id<>? ORDER BY id LIMIT 1",
                       [row["service_id"], fid]).fetchone()
        _drop_form(c, fid, sv["id"] if sv else None, (why or "")[:90]); nf += 1
    for sid, nm in rename.items():
        c.execute("UPDATE service SET name=? WHERE id=?", [nm, sid])
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"entfernt: {nd} Services, {nf} doppelte Formulare; {len(rename)} umbenannt")


def _drop_form(c, fid, survivor=None, reason=''):
    dfs = [r["id"] for r in c.execute("SELECT id FROM data_field WHERE form_id=?", [fid])]
    for did in dfs:
        c.execute("DELETE FROM data_subfield WHERE data_field_id=?", [did])
        c.execute("DELETE FROM data_field_legal_basis WHERE data_field_id=?", [did])
    c.execute("DELETE FROM data_field WHERE form_id=?", [fid])
    ffs = [r["id"] for r in c.execute("SELECT id FROM form_field WHERE form_id=?", [fid])]
    for ff in ffs:
        c.execute("DELETE FROM field_mapping WHERE form_field_id=?", [ff])
    c.execute("DELETE FROM form_field WHERE form_id=?", [fid])
    c.execute("DELETE FROM finding WHERE form_id=?", [fid])
    # The document inventory (conv 7) must keep recording this FILE. The file really
    # is a Formular — a superseded/duplicate edition of the one we keep — so repoint
    # it at the survivor and say so, rather than deleting the inventory row or
    # mislabelling it 'helper'. doc_type stays 'formular', so conv 7 still holds.
    if survivor:
        c.execute("UPDATE document SET form_id=?, classification_note="
                  "COALESCE(NULLIF(classification_note,'')||' | ','')||? WHERE form_id=?",
                  [survivor, f"ältere/doppelte Fassung; modelliert wird Formular #{survivor} ({reason})"[:400], fid])
    else:
        c.execute("DELETE FROM document WHERE form_id=?", [fid])
    c.execute("DELETE FROM form WHERE id=?", [fid])


if __name__ == "__main__":
    main()
