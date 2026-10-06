#!/usr/bin/env python3
"""Split the services that bundled several DVSH services (2026-09-27), with the
evidence and the owner's decisions in quellen/korrekturen/dvsh_aufteilung_2026-09-27.json.
Staging -> validate -> swap. Idempotent: a second run changes nothing and
reports 0 everywhere.

DVSH is the catalogue of record for services. 13 service rows were linked to
several DVSH services (dvsh_service.service_id, kept from the filename matching
of 2026-07), and each carried the name of only one of them. Evidence per row =
the sha256 the DVSH model records for each file against form.file_hash.

  1. Split (8 rows): a DVSH service whose model declares its OWN file (or its
     own procedure) gets its own service row, keyed by the DVSH slug: name and
     description from DVSH, Dienststelle as given in the file (the DVSH office,
     spelled as the databank spells it). Its DVSH link, its SHEP page and the
     forms its model declares move with it; form.dvsh_match records why. The
     row that stays takes the DVSH title of the service it keeps where the old
     name belonged to another one (35, 171, 293, 397). New rows inherit the
     Themengruppen of the row they came from (a reason per row, not
     zweitgeprüft). Legacy rows (service_requirement, finding «Auto-Entwurf»)
     stay where they are: no surface shows them.
  2. Rename (3 rows kept together because every DVSH service names the SAME
     file): a name from DVSH wording that covers all of them (34, 56, 616). A
     DVSH title that leaves the name stays findable in name_alt. 188 and 513
     already carried a fitting DVSH name and stay unchanged (8 + 3 + 2 = 13).
  3. Dienststelle of 191 follows DVSH 358 (Energiefachstelle, Baudepartement).
  4. Duplicate form 475 = the same file as 439 (identical sha256). 475's eCH
     verdicts are copied onto 439 only where 439 has a same-named field (or a
     same-named part under a same-named field) that was never judged — the rule
     of propagate_ech_names.py; everything else is dropped and listed in the
     evidence file. 475 and its rows go; 439 takes the title printed on the
     sheet. Naming rows (begriff_label / begriff_vorschlag) that lose their
     last field through this deletion go with it.

Order: after scripts/run_begriffe.py (load_themen.py rebuilds service_thema
from the panel outputs), run this again.

    python3 scripts/migrate_2026_09_27.py
"""
import json, os, shutil, sys
from citygov.core.common import ROOT, DB_PATH, connect, norm_label
from citygov.checks.validate_db import validate

SRC = os.path.join(ROOT, "quellen", "korrekturen", "dvsh_aufteilung_2026-09-27.json")
DATUM = "2026-09-27"


def units(c):
    """(ech_element_id, label_norm) of every judged field and part — what the
    naming tables are keyed by."""
    return {(r[0], norm_label(r[1])) for r in c.execute(
        "SELECT ech_element_id, name FROM data_field WHERE ech_element_id IS NOT NULL "
        "UNION ALL SELECT ech_element_id, name FROM data_subfield WHERE ech_element_id IS NOT NULL")}


def match_note(dv, fid):
    """form.dvsh_match: the DVSH file that names this form, or the title evidence."""
    for d in dv["dateien"]:
        if fid in (d.get("formulare") or []):
            return (f"zuordnung (DVSH-Aufteilung {DATUM}): DVSH {dv['dvsh_id']} «{dv['titel']}» nennt diese "
                    f"Datei ({d['rolle']}: {d['datei']}, sha256 gleich)")
    return (f"zuordnung (DVSH-Aufteilung {DATUM}): DVSH {dv['dvsh_id']} «{dv['titel']}» — Zuordnung nach "
            f"Titel bzw. verlangter Unterlage, siehe quellen/korrekturen/dvsh_aufteilung_{DATUM}.json")


def main():
    K = json.load(open(SRC, encoding="utf-8"))
    NOTIZ = K.get("notizen", {})
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    rep = {k: 0 for k in ("1 neue Service-Zeilen", "1 DVSH-Verknüpfungen verschoben", "1 SHEP-Seiten verschoben",
                          "1 Formulare verschoben", "1 Namen", "1 Themengruppen-Zeilen", "2 Namen", "3 Dienststelle",
                          "4 eCH übernommen", "4 Formular entfernt", "4 Zeilen entfernt", "4 Begriffs-Zeilen entfernt")}

    def dvsh_row(did):
        r = c.execute("SELECT dvsh_id, service_id FROM dvsh_service WHERE dvsh_id=?", [did]).fetchone()
        if not r:
            sys.exit(f"ABBRUCH: DVSH {did} fehlt in dvsh_service — Ernte prüfen")
        return r

    def set_thema(sid, themen, grund):
        have = [r[0] for r in c.execute("SELECT thema_id FROM service_thema WHERE service_id=? ORDER BY rang", [sid])]
        g = c.execute("SELECT grund FROM service_thema_grund WHERE service_id=?", [sid]).fetchone()
        if themen is not None and have != themen:
            c.execute("DELETE FROM service_thema WHERE service_id=?", [sid])
            for rang, t in enumerate(themen, 1):
                c.execute("INSERT INTO service_thema(service_id, thema_id, rang) VALUES(?,?,?)", [sid, t, rang])
            rep["1 Themengruppen-Zeilen"] += 1
        if grund and (not g or g[0] != grund):
            c.execute("INSERT OR REPLACE INTO service_thema_grund(service_id, grund, zweitgeprueft) VALUES(?,?,0)",
                      [sid, grund])
            rep["1 Themengruppen-Zeilen"] += 1

    def move_dvsh(did, slug, sid):
        rep["1 DVSH-Verknüpfungen verschoben"] += c.execute(
            "UPDATE dvsh_service SET service_id=? WHERE dvsh_id=? AND service_id IS NOT ?", [sid, did, sid]).rowcount
        rep["1 SHEP-Seiten verschoben"] += c.execute(
            "UPDATE shep_service SET service_id=? WHERE (dvsh_id=? OR slug=?) AND service_id IS NOT ?",
            [sid, did, slug, sid]).rowcount

    def move_forms(dv, sid, parent):
        """Forms the DVSH model declares go to its row. A form that moves gets a
        dvsh_match stating why; a form that stays keeps its note unless the file
        gives a new one (its old note named a DVSH service that moved away)."""
        for fid in dv.get("formulare", []):
            f = c.execute("SELECT service_id, dvsh_match FROM form WHERE id=?", [fid]).fetchone()
            if not f or f["service_id"] not in (sid, parent):
                sys.exit(f"ABBRUCH: Formular {fid} steht nicht unter Service {parent}/{sid}")
            moves = f["service_id"] != sid
            if moves:
                c.execute("UPDATE form SET service_id=? WHERE id=?", [sid, fid])
                c.execute("UPDATE finding SET service_id=? WHERE form_id=?", [sid, fid])
                rep["1 Formulare verschoben"] += 1
            note = NOTIZ.get(str(fid)) or (match_note(dv, fid) if sid != parent else None)
            if note and f["dvsh_match"] != note:
                c.execute("UPDATE form SET dvsh_match=? WHERE id=?", [note, fid])

    # 1. split ---------------------------------------------------------------
    for a in K["aufteilen"]:
        parent = a["service_id"]
        p = c.execute("SELECT * FROM service WHERE id=?", [parent]).fetchone()
        keep = a["behaelt"]
        if dvsh_row(keep["dvsh_id"])["service_id"] != parent:
            sys.exit(f"ABBRUCH: DVSH {keep['dvsh_id']} gehört nicht (mehr) zu Service {parent}")
        for n in a["neu"]:
            cur = dvsh_row(n["dvsh_id"])["service_id"]
            row = c.execute("SELECT id FROM service WHERE slug=?", [n["slug"]]).fetchone()
            if row:
                sid = row["id"]
            else:
                if cur != parent:
                    sys.exit(f"ABBRUCH: DVSH {n['dvsh_id']} gehört nicht zu Service {parent}")
                kurz = c.execute("SELECT kurzbeschreibung FROM dvsh_service WHERE dvsh_id=?",
                                 [n["dvsh_id"]]).fetchone()[0]
                c.execute("INSERT INTO service(slug, name, dienststelle, department, description, notes, in_dvsh) "
                          "VALUES(?,?,?,?,?,?,1)",
                          [n["slug"], n["titel"], n.get("dienststelle") or p["dienststelle"],
                           n.get("department") or p["department"], (kurz or "").strip() or None,
                           f"Aus Service {parent} herausgelöst (Aufteilung nach DVSH-Modell, {DATUM}); "
                           f"Themengruppen von dort übernommen."])
                sid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                rep["1 neue Service-Zeilen"] += 1
            move_dvsh(n["dvsh_id"], n["slug"], sid)
            move_forms(n, sid, parent)
            set_thema(sid, n["thema"], n["grund_thema"])
        move_forms(keep, parent, parent)
        if a.get("name") and p["name"] != a["name"]:
            c.execute("UPDATE service SET name=? WHERE id=?", [a["name"], parent])
            rep["1 Namen"] += 1
        # an alias equal to the name says nothing
        c.execute("UPDATE service SET name_alt=NULL WHERE id=? AND name_alt=name", [parent])
        if a.get("grund_thema"):
            set_thema(parent, None, a["grund_thema"])
        if a.get("dienststelle"):
            rep["3 Dienststelle"] += c.execute(
                "UPDATE service SET dienststelle=?, department=? WHERE id=? AND (dienststelle IS NOT ? OR department IS NOT ?)",
                [a["dienststelle"], a["department"], parent, a["dienststelle"], a["department"]]).rowcount

    # 2. rename rows that stay together -----------------------------------------
    for u in K["umbenennen"]:
        s = c.execute("SELECT name, name_alt FROM service WHERE id=?", [u["service_id"]]).fetchone()
        if s["name"] != u["name"]:
            c.execute("UPDATE service SET name=? WHERE id=?", [u["name"], u["service_id"]])
            rep["2 Namen"] += 1
        alt = [x for x in (s["name_alt"] or "").split(" · ") if x]
        for x in u.get("name_alt_plus", []):
            if x not in alt:
                alt.append(x)
        if " · ".join(alt) != (s["name_alt"] or ""):
            c.execute("UPDATE service SET name_alt=? WHERE id=?", [" · ".join(alt) or None, u["service_id"]])

    # 4. duplicate form ------------------------------------------------------------
    D = K["duplikat"]
    gone, keep = D["entfernen"], D["behalten"]
    if c.execute("SELECT 1 FROM form WHERE id=?", [gone]).fetchone():
        a_hash, b_hash = (c.execute("SELECT file_hash FROM form WHERE id=?", [i]).fetchone()[0] for i in (gone, keep))
        if not a_hash or a_hash != b_hash:
            sys.exit(f"ABBRUCH: Formular {gone} ist nicht byte-gleich mit {keep}")
        cols = "ech_status, ech_element_id, ech_standard_code, esh_code, esh_element"
        # fields by name; parts by (parent name, part name) — never a bare generic part label
        src_f = {norm_label(r["name"]): r for r in c.execute(
            f"SELECT name, {cols} FROM data_field WHERE form_id=? AND ech_status IS NOT NULL", [gone])}
        for r in c.execute("SELECT id, name FROM data_field WHERE form_id=? AND ech_status IS NULL", [keep]).fetchall():
            v = src_f.get(norm_label(r["name"]))
            if v:
                c.execute("UPDATE data_field SET ech_status=?, ech_element_id=?, ech_standard_code=?, esh_code=?, "
                          "esh_element=? WHERE id=?", [*(v[k] for k in cols.split(", ")), r["id"]])
                rep["4 eCH übernommen"] += 1
        src_s = {(norm_label(r["p"]), norm_label(r["name"])): r for r in c.execute(
            f"SELECT d.name p, s.name, s.ech_status, s.ech_element_id, s.ech_standard_code, s.esh_code, s.esh_element "
            f"FROM data_subfield s JOIN data_field d ON d.id=s.data_field_id "
            f"WHERE d.form_id=? AND s.ech_status IS NOT NULL", [gone])}
        for r in c.execute("SELECT s.id, d.name p, s.name FROM data_subfield s JOIN data_field d ON d.id=s.data_field_id "
                           "WHERE d.form_id=? AND s.ech_status IS NULL", [keep]).fetchall():
            v = src_s.get((norm_label(r["p"]), norm_label(r["name"])))
            if v:
                c.execute("UPDATE data_subfield SET ech_status=?, ech_element_id=?, ech_standard_code=?, esh_code=?, "
                          "esh_element=? WHERE id=?", [*(v[k] for k in cols.split(", ")), r["id"]])
                rep["4 eCH übernommen"] += 1
        before = units(c)
        fids = [r[0] for r in c.execute("SELECT id FROM data_field WHERE form_id=?", [gone])]
        ph = ",".join("?" * len(fids)) or "NULL"
        n = 0
        n += c.execute(f"DELETE FROM data_subfield WHERE data_field_id IN ({ph})", fids).rowcount
        n += c.execute(f"DELETE FROM data_field_legal_basis WHERE data_field_id IN ({ph})", fids).rowcount
        n += c.execute(f"DELETE FROM beilage WHERE data_field_id IN ({ph}) OR form_id=?", [*fids, gone]).rowcount
        n += c.execute(f"DELETE FROM panel_review WHERE kind IN ('basis','subjekt') AND item_id IN ({ph})", fids).rowcount
        n += c.execute("DELETE FROM form_similarity WHERE form_a=? OR form_b=?", [gone, gone]).rowcount
        n += c.execute("DELETE FROM field_mapping WHERE form_field_id IN (SELECT id FROM form_field WHERE form_id=?)",
                       [gone]).rowcount
        for t in ("form_field", "form_check", "formflow", "form_disclosure", "retention_decision", "form_outcome",
                  "rechtsmittel_verdikt", "finding"):
            n += c.execute(f"DELETE FROM {t} WHERE form_id=?", [gone]).rowcount
        c.execute("UPDATE document SET form_id=NULL WHERE form_id=?", [gone])
        n += c.execute(f"DELETE FROM data_field WHERE id IN ({ph})", fids).rowcount
        c.execute("DELETE FROM form WHERE id=?", [gone])
        rep["4 Formular entfernt"] += 1
        rep["4 Zeilen entfernt"] += n
        # naming rows whose last field was on the removed form
        after = units(c)
        lost = before - after
        for eid, lab in lost:
            rep["4 Begriffs-Zeilen entfernt"] += c.execute(
                "DELETE FROM begriff_label WHERE ech_element_id=? AND label_norm=?", [eid, lab]).rowcount
        used = {e for e, _ in after}
        for eid in {e for e, _ in lost} - used:
            rep["4 Begriffs-Zeilen entfernt"] += c.execute(
                "DELETE FROM begriff_vorschlag WHERE ech_element_id=?", [eid]).rowcount
    c.execute("UPDATE form SET title=? WHERE id=? AND title<>?", [D["titel_439"], keep, D["titel_439"]])

    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st)
        print("ABORT:", *errs[:5], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    for k, v in rep.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
