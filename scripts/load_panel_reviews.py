#!/usr/bin/env python3
"""Apply the second-opinion (adversarial) reviews of the single-pass panels.

Every judgment layer gets a sceptical second pass; this loader applies what
the reviewers changed, under the same gates as the first pass, and records
that the item was reviewed. Four kinds, chosen by the sub-folder name:

  basis      geaendert -> data_field.basis_typ (vocab aufgabe/ohne/offen),
             begruendung prefixed «Zweitprüfung:»; the fixed Bemerkungen
             rule of load_basis_typ.py is re-applied afterwards
  subjekt    geaendert -> data_field.subjekt (vocab)
  rmrules    korrigiert -> rechtsmittel_regel art/frist/instanz/gilt_fuer
             (a corrected Frist must still appear in the verified quote);
             streichen -> rechtsmittel_regel.gestrichen=1 (kept as evidence,
             never applied again)
  rmverdicts three lenses per form; a verdict is overturned when at least two
             lenses refute it: if two refuters agree on the same better
             verdict it is applied (gated: regel_id among the form's
             candidates), otherwise the form goes to 'offen' with the reason
             «Zweitprüfung uneinig»

Reviewed ids are recorded in panel_review(kind, item_id, urteil, grund).
Idempotent. Staging -> validate -> swap. After rmrules/rmverdicts run
load_rechtsmittel.py again.

    python3 scripts/load_panel_reviews.py <verify-dir>   (contains basis/ subjekt/ rmrules/ rmverdicts/)
"""
import glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate
from load_basis_typ import HARMONISE_SQL, HARMONISE_WHY
from load_rechtsmittel import frist_ok

DDL = """
CREATE TABLE IF NOT EXISTS panel_review (
    kind     TEXT NOT NULL,
    item_id  INTEGER NOT NULL,
    urteil   TEXT NOT NULL,
    grund    TEXT,
    PRIMARY KEY (kind, item_id)
);
"""
BASIS = {"aufgabe", "ohne", "offen"}
SUBJ = {"natuerliche_person", "organisation", "sache", "behoerde", "gemischt"}
RMART = {"einsprache", "rekurs", "beschwerde", "verwaltungsgerichtsbeschwerde", "verweis"}


def load_all(d, prefix):
    out = []
    for jf in sorted(glob.glob(os.path.join(d, prefix + "*.json"))):
        try:
            x = json.load(open(jf, encoding="utf-8"))
        except Exception:
            continue
        out.append((os.path.basename(jf), x))
    return out


def ids_asked(d):
    s = set()
    for _, x in load_all(d, "in_"):
        for it in x:
            s.add(it.get("id") or it.get("form_id"))
    return s


def main():
    root = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    if "gestrichen" not in {r[1] for r in c.execute("PRAGMA table_info(rechtsmittel_regel)")}:
        c.execute("ALTER TABLE rechtsmittel_regel ADD COLUMN gestrichen INTEGER NOT NULL DEFAULT 0")
    stats = {}

    # --- basis ----------------------------------------------------------------
    d = os.path.join(root, "basis")
    if os.path.isdir(d):
        asked = ids_asked(d); n = ch = rej = 0
        for _, x in load_all(d, "out_"):
            for u in (x.get("urteile") if isinstance(x, dict) else x) or []:
                fid, bt = u.get("id"), u.get("basis_typ")
                if fid not in asked or bt not in BASIS or u.get("urteil") not in ("bestaetigt", "geaendert"):
                    rej += 1; continue
                n += 1
                c.execute("INSERT OR REPLACE INTO panel_review VALUES('basis',?,?,?)", [fid, u["urteil"], u.get("begruendung")])
                if u["urteil"] == "geaendert":
                    why = "Zweitprüfung: " + (u.get("begruendung") or "").strip()
                    if len(why) < 20:
                        rej += 1; continue
                    c.execute("UPDATE data_field SET basis_typ=?, basis_begruendung=? WHERE id=? AND no_basis=1 "
                              "AND id NOT IN (SELECT data_field_id FROM data_field_legal_basis)", [bt, why[:240], fid])
                    ch += c.execute("SELECT changes()").fetchone()[0]
        harm = c.execute(HARMONISE_SQL, [HARMONISE_WHY]).rowcount
        stats["basis"] = f"{n} geprüft, {ch} geändert, {harm} Bemerkungsfelder re-harmonisiert, {rej} rejected"

    # --- subjekt --------------------------------------------------------------
    d = os.path.join(root, "subjekt")
    if os.path.isdir(d):
        asked = ids_asked(d); n = ch = rej = 0
        for _, x in load_all(d, "out_"):
            for u in (x.get("urteile") if isinstance(x, dict) else x) or []:
                fid, sj = u.get("id"), u.get("subjekt")
                if fid not in asked or sj not in SUBJ or u.get("urteil") not in ("bestaetigt", "geaendert"):
                    rej += 1; continue
                n += 1
                c.execute("INSERT OR REPLACE INTO panel_review VALUES('subjekt',?,?,?)", [fid, u["urteil"], u.get("grund")])
                if u["urteil"] == "geaendert":
                    c.execute("UPDATE data_field SET subjekt=? WHERE id=?", [sj, fid]); ch += 1
        stats["subjekt"] = f"{n} geprüft, {ch} geändert, {rej} rejected"

    # --- rmrules --------------------------------------------------------------
    d = os.path.join(root, "rmrules")
    if os.path.isdir(d):
        asked = ids_asked(d); n = ch = dele = rej = 0
        for _, x in load_all(d, "out_"):
            for u in (x.get("urteile") if isinstance(x, dict) else x) or []:
                rid, v = u.get("id"), u.get("urteil")
                if rid not in asked or v not in ("bestaetigt", "korrigiert", "streichen"):
                    rej += 1; continue
                n += 1
                c.execute("INSERT OR REPLACE INTO panel_review VALUES('rmrule',?,?,?)", [rid, v, u.get("grund")])
                if v == "streichen":
                    c.execute("UPDATE rechtsmittel_regel SET gestrichen=1 WHERE id=?", [rid]); dele += 1
                elif v == "korrigiert":
                    row = c.execute("SELECT * FROM rechtsmittel_regel WHERE id=?", [rid]).fetchone()
                    if not row:
                        rej += 1; continue
                    art = u.get("rechtsmittel_art") or row["rechtsmittel_art"]
                    frist = u.get("frist_tage", row["frist_tage"])
                    if art not in RMART or (frist is not None and not frist_ok(int(frist), row["quote"])):
                        rej += 1; continue
                    c.execute("UPDATE rechtsmittel_regel SET rechtsmittel_art=?, frist_tage=?, instanz=?, gilt_fuer=?, "
                              "hinweis=COALESCE(?, hinweis) WHERE id=?",
                              [art, int(frist) if frist is not None else None,
                               u.get("instanz") if "instanz" in u else row["instanz"],
                               u.get("gilt_fuer") if "gilt_fuer" in u else row["gilt_fuer"],
                               ("Zweitprüfung: " + u["grund"]) if u.get("grund") else None, rid])
                    ch += 1
        stats["rmrules"] = f"{n} geprüft, {ch} korrigiert, {dele} gestrichen, {rej} rejected"

    # --- rmverdicts: three lenses per form ---------------------------------------
    d = os.path.join(root, "rmverdicts")
    if os.path.isdir(d):
        asked = ids_asked(d)
        cands = {}
        for r in c.execute("SELECT DISTINCT df.form_id, rr.id FROM data_field_legal_basis lb "
                           "JOIN data_field df ON df.id=lb.data_field_id JOIN article a ON a.id=lb.article_id "
                           "JOIN rechtsmittel_regel rr ON rr.law_id=a.law_id AND rr.scope='sektoral'"):
            cands.setdefault(r["form_id"], set()).add(r["id"])
        votes = {}   # form_id -> list of (refuted, besser, grund)
        for _, x in load_all(d, "out_"):
            for u in (x.get("urteile") if isinstance(x, dict) else x) or []:
                fid = u.get("form_id")
                if fid not in asked:
                    continue
                votes.setdefault(fid, []).append((bool(u.get("refuted")), u.get("besser"), u.get("grund")))
        n = over = offen = rej = 0
        for fid, vs in votes.items():
            n += 1
            ref = [v for v in vs if v[0]]
            if len(ref) < 2:
                c.execute("INSERT OR REPLACE INTO panel_review VALUES('rmverdict',?,?,?)", [fid, "bestaetigt", f"{len(vs)-len(ref)}/{len(vs)} Linsen"])
                continue
            # do two refuters agree on the same better verdict?
            agree = {}
            for _, b, g in ref:
                if b and b.get("quelle") in ("sektoral", "allgemein", "offen"):
                    key = (b["quelle"], b.get("regel_id") if b["quelle"] == "sektoral" else None)
                    agree.setdefault(key, []).append(g or "")
            pick = next(((k, g) for k, g in agree.items() if len(g) >= 2), None)
            if pick and (pick[0][0] != "sektoral" or pick[0][1] in cands.get(fid, set())):
                q, rid = pick[0]
                c.execute("INSERT OR REPLACE INTO rechtsmittel_verdikt(form_id, regel_id, quelle, begruendung, last_checked) VALUES(?,?,?,?,?)",
                          [fid, rid, q, ("Zweitprüfung: " + " / ".join(pick[1])[:380]), "Panel-Zweitprüfung"])
                c.execute("INSERT OR REPLACE INTO panel_review VALUES('rmverdict',?,?,?)", [fid, "geaendert", " / ".join(pick[1])[:400]])
                over += 1
            else:
                c.execute("INSERT OR REPLACE INTO rechtsmittel_verdikt(form_id, regel_id, quelle, begruendung, last_checked) VALUES(?,?,?,?,?)",
                          [fid, None, "offen", "Zweitprüfung uneinig: " + " / ".join(g or "" for _, _, g in ref)[:360], "Panel-Zweitprüfung"])
                c.execute("INSERT OR REPLACE INTO panel_review VALUES('rmverdict',?,?,?)", [fid, "offen", "Zweitprüfung uneinig"])
                offen += 1
        stats["rmverdicts"] = f"{n} Formulare geprüft, {over} umgehängt, {offen} auf offen gesetzt"

    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    for k, v in stats.items():
        print(f"{k}: {v}")
    if "rmrules" in stats or "rmverdicts" in stats:
        print("-> scripts/load_rechtsmittel.py erneut ausführen")


if __name__ == "__main__":
    main()
