#!/usr/bin/env python3
"""Load the curated Verfahren layer — Beilagen and Entscheide — PROOF-GATED.

Gates:
  * beilage  — every row must be traceable to one of the three real sources:
               an attachment data_field of that form, a value in one of the
               form's Beilagen-checklist fields, or an entry in the DVSH
               unterlagen of the form's service. A document no source names
               is rejected; halter/obligatorium must use the CHECK vocabulary.
  * outcome  — only forms whose service has DVSH data; the agent's beleg
               substring must literally occur in the DVSH titel/kurz-
               beschreibung/ablauf text, or the row falls back to 'unbekannt'.

Idempotent (agent rows replaced wholesale). Staging -> validate -> swap.

    python3 scripts/load_verfahren.py <out-dir>
"""
import glob, json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

HALTER = {"privat", "einwohnerregister", "handelsregister", "betreibungsregister",
          "strafregister", "steuerverwaltung", "grundbuch", "kanton_andere", "bund", "unbekannt"}
OBLIG = {"zwingend", "bedingt", "fakultativ", "unbekannt"}
ARTEN = {"bewilligung", "verfuegung", "bestaetigung", "registereintrag",
         "auszahlung", "kein_entscheid", "unbekannt"}


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    rejected = []

    # source evidence per form: attachment fields, checklist values, DVSH text
    att = {}          # form_id -> {data_field_id, ...}
    txt = {}          # form_id -> normalised text of all form-side sources
    for r in c.execute("SELECT id, form_id, name, data_type, allowed_values FROM data_field"):
        base = txt.setdefault(r["form_id"], [])
        if r["data_type"] == "attachment":
            att.setdefault(r["form_id"], set()).add(r["id"])
            base.append(norm(r["name"]))
        if r["data_type"] in ("multiselect", "enum") and re.search(r"eilage|nterlagen", r["name"] or ""):
            try:
                base.extend(norm(v) for v in json.loads(r["allowed_values"] or "[]"))
            except Exception:
                pass
    dvsh_txt, dvsh_raw = {}, {}
    for r in c.execute("SELECT f.id fid, dv.unterlagen, dv.titel, dv.kurzbeschreibung, dv.ablauf "
                       "FROM form f JOIN dvsh_service dv ON dv.service_id=f.service_id"):
        try:
            u = json.loads(r["unterlagen"] or "[]")
        except Exception:
            u = []
        dvsh_txt[r["fid"]] = norm(" ".join(str(x) for x in u))
        try:
            ab = " ".join(str(x) for x in json.loads(r["ablauf"] or "[]"))
        except Exception:
            ab = r["ablauf"] or ""
        dvsh_raw[r["fid"]] = norm(f"{r['titel']} {r['kurzbeschreibung']} {ab}")

    def traceable(fid, bez, source):
        k = norm(bez)
        toks = [t for t in k.split() if len(t) > 3][:4]
        def hit(hay):
            return hay and (k[:60] in hay or (toks and all(t in hay for t in toks)))
        if source in ("formular", "beide") and hit(" ".join(txt.get(fid, []))):
            return True
        if source in ("dvsh", "beide") and hit(dvsh_txt.get(fid, "")):
            return True
        return False

    c.execute("DELETE FROM beilage WHERE last_checked LIKE 'agent%'")
    nb = 0
    for jf in sorted(glob.glob(os.path.join(src, "beilagen_*.json"))):
        for b in json.load(open(jf, encoding="utf-8")).get("beilagen", []):
            fid, bez = b.get("form_id"), (b.get("bezeichnung") or "").strip()[:120]
            if not bez or b.get("halter") not in HALTER or (b.get("obligatorium") or "unbekannt") not in OBLIG:
                rejected.append(f"Beilage Vokabular: #{fid} {bez[:30]}"); continue
            dfid = b.get("data_field_id")
            if dfid and dfid not in att.get(fid, set()):
                dfid = None
            if not (dfid or traceable(fid, bez, b.get("source") or "formular")):
                rejected.append(f"Beilage nicht rückführbar: #{fid} {bez[:40]}"); continue
            c.execute("INSERT OR IGNORE INTO beilage(form_id,data_field_id,bezeichnung,obligatorium,"
                      "bedingung,halter,fetchable,source,last_checked) VALUES(?,?,?,?,?,?,?,?,'agent (quellen-rückgeführt)')",
                      [fid, dfid, bez, b.get("obligatorium") or "unbekannt",
                       (b.get("bedingung") or None), b.get("halter"),
                       1 if b.get("fetchable") else 0, b.get("source") or "formular"])
            nb += c.execute("SELECT changes() n").fetchone()["n"]

    c.execute("DELETE FROM form_outcome WHERE last_checked LIKE 'agent%'")
    no = nu = 0
    of = os.path.join(src, "outcomes.json")
    if os.path.exists(of):
        for o in json.load(open(of, encoding="utf-8")).get("outcomes", []):
            fid, art = o.get("form_id"), o.get("entscheid_art")
            if fid not in dvsh_raw or art not in ARTEN:
                rejected.append(f"Outcome: #{fid} {art}"); continue
            beleg = norm(o.get("beleg") or "")
            if art != "unbekannt" and (not beleg or beleg not in dvsh_raw[fid]):
                art, doc = "unbekannt", None   # unverifiable claim degrades honestly
                nu += 1
            else:
                doc = (o.get("ergebnis_dokument") or None)
            c.execute("INSERT OR REPLACE INTO form_outcome(form_id,entscheid_art,ergebnis_dokument,"
                      "last_checked) VALUES(?,?,?,'agent (Beleg im DVSH-Text)')", [fid, art, doc])
            no += 1

    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Verfahren: {nb} Beilagen, {no} Entscheide ({nu} mangels Beleg auf 'unbekannt' gestuft), "
          f"{len(rejected)} REJECTED")
    for r in rejected[:8]:
        print("    rejected:", r)


if __name__ == "__main__":
    main()
