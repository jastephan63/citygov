#!/usr/bin/env python3
"""Turn the reviewed panel outputs of an intake into loader input, keep them as evidence under
quellen/dokumente/panel_<date>/, and run the loaders — one subcommand per layer, in this order:

    python3 scripts/apply_panel.py felder       <panel-dir> <output.json>   # data fields (new Formulare)
    python3 scripts/apply_panel.py ech          <panel-dir> <output.json>   # eCH element per field and part
    python3 scripts/apply_panel.py verfahren    <panel-dir> <output.json>   # purpose, decision, Beilagen
    python3 scripts/apply_panel.py recht        <panel-dir> <output.json> [...]   # citations, basis type, sensitive
    python3 scripts/apply_panel.py subjekt      <panel-dir> <output.json>   # whose Angabe (register fields only)
    python3 scripts/apply_panel.py rechtsmittel <panel-dir> <output.json>   # remedy verdict + three lenses
    python3 scripts/apply_panel.py ersetzen     <record.json> <korrektur.json> [...] --out <file>

<panel-dir> is quellen/dokumente/panel_<YYYY-MM-DD>; the date in its name dates the files written.
Each <output.json> is one panel's result (optionally wrapped in {"result": …}): a first judgement
(«erst») and the sceptical second review («zweit») that is loaded. The shapes, the instructions
the reviewers followed and the order of the layers are in docs/pruefprotokoll.md.

Order matters (each lesson cost a rerun): felder before everything; subjekt only after ech (its
scope is the fields with a register standard); rechtsmittel only after recht (its candidates are
the cited laws). «ersetzen» folds corrections into a record before «recht»: a completion
({recht: [{form_id, zweit}]}) or a harmonisation across sibling Formulare ({gruppen: [{zweit}]})
replaces entries by field id.

Gates on top of the loaders' own: «recht» stops when a basis text says «Datum» unless that text
is a reviewed «behalten» entry of quellen/wortwahl_datum.json; «rechtsmittel» stops on a reason
over 400 characters or with internal review wording («Kandidat», «Zweitprüfung», «im Material»,
«Regel N») — reword it and keep the panel's text as «begruendung_panel». Every loader writes
staging -> validate -> swap; a subcommand prints each loader's last line.
"""
import json, os, re, sqlite3, subprocess, sys

from citygov.core.common import ROOT, DB_PATH


def lese(path, key):
    r = json.load(open(path, encoding="utf-8"))
    r = r.get("result", r)
    if key not in r:
        sys.exit(f"{path}: kein Schlüssel «{key}»")
    return r[key]


def schreibe(path, obj, indent=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=indent)


def lauf(*args):
    p = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    zeile = (p.stdout.strip().splitlines() or [""])[-1][:400]
    print(f"{os.path.basename(args[0])}: {zeile}" + (f"\n  {p.stderr.strip()[-600:]}" if p.returncode else ""))
    if p.returncode:
        sys.exit(p.returncode)
    return p


def datum_von(panel):
    m = re.search(r"panel_(\d{4}-\d{2}-\d{2})", os.path.abspath(panel))
    if not m:
        sys.exit(f"{panel}: der Ordner muss quellen/dokumente/panel_<YYYY-MM-DD> heissen")
    return m.group(1)


# --- felder -------------------------------------------------------------------------------
def felder(panel, out):
    D = os.path.join(panel, "felder")
    for x in sorted(lese(out, "derived"), key=lambda x: x["form_id"]):
        z = x.get("zweit")
        if not z or not z.get("data_fields"):
            sys.exit(f"Formular {x['form_id']}: keine Zweitprüfung — nichts geladen")
        schreibe(os.path.join(D, f"{x['form_id']}.json"),
                 {"form_id": x["form_id"], "data_fields": z["data_fields"], "hinweis": z.get("hinweis", "")})
        print(x["form_id"], len(x["erst"]["data_fields"]), "->", len(z["data_fields"]), "Angaben")
    lauf("scripts/load_data_fields.py", D)
    lauf("scripts/init_subfields.py", "--nur-neue")
    lauf("scripts/propagate_ech_names.py")


# --- ech ----------------------------------------------------------------------------------
def ech(panel, out):
    base = os.path.join(panel, "ech")
    r = lese(out, "ech")
    schreibe(os.path.join(base, "panel_erst_und_zweit.json"), r, indent=None)
    for x in r:
        fid = x["form_id"]
        d = os.path.join(base, str(fid))
        urteile = []
        for u in x["zweit"]["urteile"]:
            item = {"art": u["art"], "urteil": u["urteil"], "grund": u.get("grund")}
            if u["art"] == "feld":
                item["feld"] = u["feld"]
            else:
                item["elternfeld"] = u["elternfeld"]; item["teilfeld"] = u["teilfeld"]
            if u["urteil"] == "besser":
                item["standard"] = u["standard"]; item["element"] = u.get("element") or ""
            urteile.append(item)
        rel = os.path.relpath(d, ROOT)
        schreibe(os.path.join(d, f"out_{fid}.json"),
                 {"hinweis": f"eCH-Urteile Formular {fid}, {os.path.basename(panel)}, Zweitprüfung angewendet",
                  "anwenden": f"python3 scripts/load_ech_verdicts_new.py {rel} --nur-offene={fid}", "urteile": urteile})
        # one Formular per run: the loader keys its verdicts by name
        lauf("scripts/load_ech_verdicts_new.py", d, f"--nur-offene={fid}")


# --- verfahren ----------------------------------------------------------------------------
def verfahren(panel, out):
    dt = datum_von(panel)
    D = os.path.join(panel, "verfahren")
    recs = lese(out, "verf")
    schreibe(os.path.join(D, "panel_erst_und_zweit.json"), recs, indent=None)
    beil, outc, purp = [], [], []
    for x in recs:
        z, fid = x["zweit"], x["form_id"]
        purp.append({"form_id": fid, "zweck": z["zweck"]})
        outc.append({"form_id": fid, "entscheid_art": z["entscheid_art"], "beleg": z["entscheid_beleg"],
                     "ergebnis_dokument": z.get("ergebnis_dokument")})
        for b in z["beilagen"]:
            beil.append({"form_id": fid, **{k: b.get(k) for k in ("bezeichnung", "data_field_id", "obligatorium",
                                                                    "bedingung", "halter", "fetchable", "source")}})
    H = f"Panel {dt} (Zweitprüfung angewendet): "
    schreibe(os.path.join(D, f"beilagen_{dt}.json"), {"hinweis": H + "Beilagen je Formular", "beilagen": beil})
    schreibe(os.path.join(D, "outcomes.json"), {"hinweis": H + "Entscheid je Formular", "outcomes": outc})
    schreibe(os.path.join(D, f"purposes_{dt}.json"), {"hinweis": H + "Zweck je Formular", "purposes": purp})
    ids = ",".join(str(x["form_id"]) for x in recs)
    print(len(recs), "Formulare,", len(beil), "Beilagen")
    lauf("scripts/load_verfahren.py", D, "--nur", ids)
    lauf("scripts/load_register.py", D, "--nur", ids)


# --- recht --------------------------------------------------------------------------------
def behalten():
    p = os.path.join(ROOT, "quellen", "wortwahl_datum.json")
    return set(json.load(open(p, encoding="utf-8")).get("behalten", [])) if os.path.exists(p) else set()


def recht(panel, outs):
    dt = datum_von(panel)
    B = os.path.join(panel, "recht")
    results = []
    for f in outs:
        results += lese(f, "recht")
    schreibe(os.path.join(B, "panel_erst_und_zweit.json"), results, indent=None)
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
    Z = os.path.join(B, "zitate")
    asked = {}
    for x in results:
        fid = x["form_id"]
        z = {f["id"]: f for f in x["zweit"]["felder"]}
        e = {f["id"]: f for f in x["erst"]["felder"]}
        asked[fid] = (z, e)
        mappings = []
        for row in c.execute("SELECT id, name, no_basis FROM data_field WHERE form_id=? ORDER BY ord", [fid]):
            if row["id"] in z:
                f = z[row["id"]]
                mappings.append({"data_field": row["name"],
                                 "cites": [{"cref": k["cref"], "article_no": k["article_no"], "beleg": k["beleg"]} for k in f["cites"]],
                                 "over_collection": bool(f["over_collection"]) and not f["cites"]})
            else:   # an existing field of a ported edition keeps the citations the databank holds
                cites = [{"cref": r2["cref"], "article_no": r2["article_no"]} for r2 in c.execute(
                    "SELECT COALESCE(l.cantonal_ref, 'SR ' || l.sr_number) cref, a.article_no FROM data_field_legal_basis lb "
                    "JOIN article a ON a.id=lb.article_id JOIN law l ON l.id=a.law_id WHERE lb.data_field_id=?", [row["id"]])]
                mappings.append({"data_field": row["name"], "cites": cites, "over_collection": bool(row["no_basis"]) and not cites})
        schreibe(os.path.join(Z, f"{fid}.json"), {"form_id": fid, "mappings": mappings})
    c.close()
    lauf("scripts/load_field_legal.py", Z)
    # load_field_legal swapped the database file: read the new one
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
    BT = os.path.join(B, "basis_typ"); RV = os.path.join(B, "review", "basis")
    verdicts, reviews, ids = [], [], []
    for fid, (z, e) in asked.items():
        for i, f in z.items():
            r = c.execute("SELECT no_basis, (SELECT COUNT(*) FROM data_field_legal_basis WHERE data_field_id=?) n "
                          "FROM data_field WHERE id=?", [i, i]).fetchone()
            if not r or r["no_basis"] != 1 or r["n"] or not f["basis_typ"]:
                continue
            first = (e.get(i) or {}).get("basis_typ") or f["basis_typ"]
            verdicts.append({"id": i, "basis_typ": first,
                             "begruendung": (e.get(i) or {}).get("basis_begruendung") or f["basis_begruendung"]})
            reviews.append({"id": i, "urteil": "bestaetigt" if first == f["basis_typ"] else "geaendert",
                            "basis_typ": f["basis_typ"], "begruendung": f["basis_begruendung"]})
            ids.append({"id": i, "form_id": fid})
    c.close()
    schreibe(os.path.join(BT, f"out_{dt}.json"), {"verdicts": verdicts})
    schreibe(os.path.join(RV, f"in_{dt}.json"), ids)
    schreibe(os.path.join(RV, f"out_{dt}.json"), {"urteile": reviews})
    ok = behalten()
    datum = sorted({v["begruendung"] for v in verdicts + reviews if "Datum" in (v.get("begruendung") or "")} - ok)
    if datum:
        print("ABBRUCH vor load_basis_typ: Begründungen mit «Datum», die quellen/wortwahl_datum.json nicht als",
              "«behalten» führt — ein Kalenderdatum dort aufnehmen, sonst umformulieren, dann erneut ausführen:")
        for t in datum:
            print("  -", t)
        sys.exit(1)
    lauf("scripts/load_basis_typ.py", BT)
    lauf("scripts/load_panel_reviews.py", os.path.join(B, "review"))
    SE = os.path.join(B, "sensitiv")
    fel = [{"id": i, "kategorie": f["sensitiv"], "beleg": f["sensitiv_beleg"]}
           for fid, (z, e) in asked.items() for i, f in z.items() if f["sensitiv"]]
    schreibe(os.path.join(SE, f"out_{dt}.json"), {"felder": fel})
    lauf("scripts/load_sensitiv.py", SE)


def ersetzen(record, korrekturen, out):
    """Replace entries of a legal-basis record by field id with corrected ones."""
    r = json.load(open(record, encoding="utf-8")); r = r.get("result", r)
    neu, quelle = {}, {}
    for k in korrekturen:
        x = json.load(open(k, encoding="utf-8")); x = x.get("result", x)
        teile = [g["zweit"] for g in x.get("gruppen", [])] + [y["zweit"] for y in x.get("recht", [])]
        if not teile:
            sys.exit(f"{k}: weder «gruppen» noch «recht»")
        for z in teile:
            for f in z["felder"]:
                neu[f["id"]] = f; quelle[f["id"]] = os.path.basename(k)
    gesehen = set()
    for x in r["recht"]:
        for i, f in enumerate(x["zweit"]["felder"]):
            if f["id"] in neu:
                if neu[f["id"]]["name"] != f["name"]:
                    sys.exit(f"Feld {f['id']}: Name {neu[f['id']]['name']!r} != {f['name']!r}")
                x["zweit"]["felder"][i] = neu[f["id"]]; gesehen.add(f["id"])
                x.setdefault("ersetzt", []).append({"id": f["id"], "aus": quelle[f["id"]]})
    fehlt = set(neu) - gesehen
    if fehlt:
        sys.exit(f"Korrekturen ohne Feld im Record: {sorted(fehlt)}")
    json.dump(r, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(gesehen)} Einträge ersetzt -> {out}")


# --- subjekt ------------------------------------------------------------------------------
def subjekt(panel, out):
    D = os.path.join(panel, "subjekt"); R = os.path.join(panel, "review", "subjekt")
    sj = lese(out, "subjekt")
    schreibe(os.path.join(D, "panel_erst_und_zweit.json"), sj, indent=None)
    for x in sj:
        fid = x["form_id"]
        ids = [{"id": v["id"], "form_id": fid} for v in x["erst"]["verdicts"]]
        schreibe(os.path.join(D, f"in_{fid}.json"), ids, indent=None)
        schreibe(os.path.join(D, f"out_{fid}.json"), {"verdicts": x["erst"]["verdicts"]})
        first = {v["id"]: v["subjekt"] for v in x["erst"]["verdicts"]}
        rev = [{"id": v["id"], "urteil": "bestaetigt" if first.get(v["id"]) == v["subjekt"] else "geaendert",
                "subjekt": v["subjekt"], "grund": v["grund"]} for v in x["zweit"]["verdicts"] if v["id"] in first]
        schreibe(os.path.join(R, f"in_{fid}.json"), ids, indent=None)
        schreibe(os.path.join(R, f"out_{fid}.json"), {"urteile": rev})
    lauf("scripts/load_subjekt.py", D)


# --- rechtsmittel -------------------------------------------------------------------------
INTERN = re.compile(r"Kandidat|Zweitprüfung|im Material|Regel \d")


def rechtsmittel(panel, out):
    dt = datum_von(panel)
    D = os.path.join(panel, "rechtsmittel"); R = os.path.join(panel, "review", "rmverdicts")
    rm = lese(out, "rechtsmittel")
    schlecht = [(x["form_id"], len(x["verdikt"]["begruendung"]), INTERN.findall(x["verdikt"]["begruendung"]))
                for x in rm if len(x["verdikt"]["begruendung"]) > 400 or INTERN.search(x["verdikt"]["begruendung"])]
    if schlecht:
        print("ABBRUCH: Begründungen über 400 Zeichen oder mit interner Prüfwortwahl (Formular, Länge, Wörter) —",
              "umformulieren, den Text des Panels als «begruendung_panel» behalten:")
        for s in schlecht:
            print("  -", s)
        sys.exit(1)
    schreibe(os.path.join(D, "panel_verdikt_und_linsen.json"), rm, indent=None)
    verdicts = [{"form_id": x["form_id"], "quelle": x["verdikt"]["quelle"],
                 **({"regel_id": x["verdikt"]["regel_id"]} if x["verdikt"]["quelle"] == "sektoral" else {}),
                 "begruendung": x["verdikt"]["begruendung"]} for x in rm]
    schreibe(os.path.join(D, f"out_{dt}.json"), {"verdicts": verdicts})
    lauf("scripts/load_rechtsmittel_verdicts.py", D)
    schreibe(os.path.join(R, f"in_{dt}.json"), [{"form_id": x["form_id"]} for x in rm], indent=None)
    for lens in ("norm", "entscheid", "praxis"):
        items = [{"form_id": x["form_id"], "refuted": l["refuted"], "besser": l["besser"], "grund": l["grund"]}
                 for x in rm for l in x["linsen"] if l["lens"] == lens]
        schreibe(os.path.join(R, f"out_{dt}_{lens}.json"), {"urteile": items})
    lauf("scripts/load_panel_reviews.py", os.path.join(panel, "review"))
    lauf("scripts/load_rechtsmittel.py")


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return
    cmd, rest = a[0], a[1:]
    if cmd == "ersetzen":
        if "--out" not in rest:
            sys.exit("ersetzen <record.json> <korrektur.json> [...] --out <file>")
        i = rest.index("--out"); out = rest[i + 1]; rest = rest[:i] + rest[i + 2:]
        return ersetzen(rest[0], rest[1:], out)
    if len(rest) < 2:
        sys.exit(f"{cmd} <panel-dir> <output.json>")
    panel = os.path.abspath(rest[0]); datum_von(panel)
    fn = {"felder": felder, "ech": ech, "verfahren": verfahren, "subjekt": subjekt, "rechtsmittel": rechtsmittel}.get(cmd)
    if cmd == "recht":
        return recht(panel, rest[1:])
    if not fn:
        sys.exit(f"unbekannt: {cmd} (felder, ech, verfahren, recht, ersetzen, subjekt, rechtsmittel)")
    fn(panel, rest[1])


if __name__ == "__main__":
    main()
