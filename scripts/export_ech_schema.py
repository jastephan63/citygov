#!/usr/bin/env python3
"""Export every Formular as an eCH-shaped exchange schema (citygov_ech_schemas.json).

For each form, the eCH-mapped data points are grouped by standard and nested by
their parent complexType (ech_element.context, from the swept XSDs); points
without an eCH element land in an explicit 'ohne_standard' section — the gap is
part of the payload, never hidden. A form is 'voll' exchange-ready only when
every atomic point carries an element.

Honest limitation, stated in the file's meta: the catalogue has no XSD version
column yet (needs a re-sweep of the eCH XSDs), so schemas are unversioned.

    python3 scripts/export_ech_schema.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect


def main():
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
            # the atomic unit: a composite's subfields replace it (convention 6)
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

    doc = {"meta": {"hinweis": "eCH-Austauschschemata je Formular, verschachtelt nach den "
                    "complexTypes der offiziellen XSDs. 'ohne_standard' sind echte Lücken. "
                    "XSD-Versionen sind noch nicht gepinnt (braucht einen erneuten XSD-Sweep).",
                    "quelle": "citygov.db"}, "formulare": out}
    path = os.path.join(ROOT, "citygov_ech_schemas.json")
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    voll = sum(1 for f in out if f["exchange_ready"] == "voll")
    print(f"wrote citygov_ech_schemas.json: {len(out)} Formulare, {voll} voll exchange-ready")


if __name__ == "__main__":
    main()
