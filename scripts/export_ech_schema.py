#!/usr/bin/env python3
"""Export every Formular as an eCH-shaped exchange schema (citygov_ech_schemas.json).

For each form, the eCH-mapped data points are grouped by standard and nested by
their parent complexType (ech_element.context, from the swept XSDs); points
without an eCH element land in an explicit 'ohne_standard' section — the gap is
part of the payload, never hidden. A form is 'voll' exchange-ready only when
every atomic point carries an element.

meta.xsd_versionen records the XSD version each standard was mapped against
(ech_standard.xsd_version, written by scripts/sweep_ech_xsd.py); a standard
without its own schema file has no entry there, and the export says so.
meta.generated_at and meta.datenstand (build date, XSD sweep) repeat the stamp
of data_export.json, like every other export of the same build.

    python3 scripts/export_ech_schema.py          # after scripts/export_json.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, EXPORT_PATH, connect, assert_no_local_paths
import export_vertrag as EV


def _stamp():
    """generated_at and the Datenstand of data_export.json — one stamp per build."""
    try:
        with open(EXPORT_PATH, encoding="utf-8") as fh:
            x = json.load(fh)
    except Exception as ex:
        sys.exit(f"data_export.json fehlt oder ist nicht lesbar ({ex}) — zuerst scripts/export_json.py ausführen")
    if not x.get("generated_at"):
        sys.exit("data_export.json trägt kein generated_at — zuerst scripts/export_json.py ausführen")
    ds = x.get("datenstand") or {}
    return x["generated_at"], {"build": ds.get("build"), "xsd_sweep": ds.get("xsd_sweep")}


def main():
    generated_at, datenstand = _stamp()
    c = connect(DB_PATH)
    rows = lambda q, *a: [dict(r) for r in c.execute(q, a).fetchall()]
    elems = {r["id"]: r for r in rows("SELECT id, standard, name, datatype, context FROM ech_element")}

    def point(name, eid, fmt):
        e = elems.get(eid)
        if not e:
            return None, {"feld": name, "format": fmt}
        return {"standard": e["standard"], "context": e["context"], "element": e["name"],
                "datatype": e["datatype"], "feld": name}, None

    out = []
    for fm in rows("SELECT f.id, f.title, s.name svc, s.dienststelle FROM form f "
                   "JOIN service s ON s.id=f.service_id ORDER BY f.id"):
        mapped, unmapped = [], []
        for d in rows("SELECT id, name, format, ech_element_id FROM data_field "
                      "WHERE form_id=? ORDER BY ord", fm["id"]):
            subs = rows("SELECT name, ech_element_id FROM data_subfield "
                        "WHERE data_field_id=? ORDER BY ord", d["id"])
            # the atomic unit: a composite's subfields replace it (the atomic part, convention 3)
            pts = subs if subs else [d]
            for p in pts:
                m, u = point(p["name"], p.get("ech_element_id"), d.get("format"))
                (mapped.append(m) if m else unmapped.append(u))
        if not mapped and not unmapped:
            continue
        # nest by standard -> parent complexType, mirroring the XSD structure
        tree = {}
        for m in mapped:
            tree.setdefault(m["standard"], {}).setdefault(m["context"] or "(root)", []).append(
                {"element": m["element"], "datatype": m["datatype"], "feld": m["feld"]})
        pct = round(100 * len(mapped) / (len(mapped) + len(unmapped)))
        out.append({"form_id": fm["id"], "titel": fm["title"], "dienststelle": fm["dienststelle"],
                    "exchange_ready": "voll" if not unmapped else ("teilweise" if mapped else "nein"),
                    "abdeckung_pct": pct, "ech": tree, "ohne_standard": unmapped})
    c.close()

    # the sweep pins a version per standard; publish it, so a consumer knows
    # which schema edition the mapping was made against
    versions = {}
    try:
        c2 = connect(DB_PATH)
        versions = {r["code"]: r["xsd_version"] for r in
                    c2.execute("SELECT code, xsd_version FROM ech_standard WHERE xsd_version IS NOT NULL")}
        c2.close()
    except Exception:
        pass
    doc = {"meta": {"generated_at": generated_at, "datenstand": datenstand,
                    "hinweis": "eCH-Austauschschemata je Formular, verschachtelt nach den "
                    "complexTypes der offiziellen XSDs. 'ohne_standard' sind echte Lücken. "
                    "'xsd_versionen' nennt die Schema-Fassung, gegen die zugeordnet wurde "
                    "(scripts/sweep_ech_xsd.py); ein Standard ohne Eintrag publiziert keine "
                    "eigene XSD.",
                    "xsd_versionen": versions,
                    "quelle": "citygov.db (generated_at = Stempel von data_export.json)"},
           "formulare": out}
    # permanent identifiers on every point and the version stamp of the export contract
    vertrag = EV.Vertrag()
    ck = connect(DB_PATH)
    doc = EV.fertigstellen(vertrag, "citygov_ech_schemas.json", doc, ck, generated_at)
    ck.close()
    path = os.path.join(ROOT, "citygov_ech_schemas.json")
    text = json.dumps(doc, ensure_ascii=False, indent=1)
    assert_no_local_paths("citygov_ech_schemas.json", text)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    vertrag.festschreiben()             # schema/citygov_ech_schemas.schema.json + exportvertrag.json
    voll = sum(1 for f in out if f["exchange_ready"] == "voll")
    print(f"wrote citygov_ech_schemas.json: {len(out)} Formulare, {voll} voll exchange-ready")


if __name__ == "__main__":
    main()
