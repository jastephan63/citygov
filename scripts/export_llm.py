#!/usr/bin/env python3
"""Export the databank in LLM-ready form (the durable artifact for later use).

The SQLite citygov.db remains the source of truth; this produces three stable,
self-describing files an LLM agent can ingest directly:

  citygov_llm.json   — nested: service -> form -> field -> legal_basis, with a
                       meta block explaining the verification levels and the
                       proposed/confirmed distinction so the model never mistakes
                       a draft for a verified fact.
  citygov_fields.jsonl — one JSON object per form FIELD (flat, RAG-friendly): the
                       field, its service/office/department, classification, and
                       legal basis with provenance.
  citygov_datafields.jsonl — one JSON object per logical Datenfeld: definition,
                       eCH/eSH standard mapping, legal basis, and sensitivity.
  citygov_datarules.jsonl — one JSON object per data-governance rule: what the
                       law says about storing, processing and disclosing the
                       data, each with a PDF-verified verbatim quote.

    python3 scripts/export_llm.py
"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, connect, DB_PATH
from export_json import compose_path

META = {
    "about": "Kanton Schaffhausen city-services compliance databank. Per service: "
             "the forms, every form field, and the legal basis (Rechtsgrundlage) "
             "for each field.",
    "trust_rules": {
        "match_status": "Field<->requirement links are 'proposed' (auto-drafted, "
                        "unreviewed) or 'confirmed' (human-reviewed). Treat 'proposed' "
                        "as a hypothesis, not fact.",
        "legal_basis.verification": {
            "verified": "cross-checked live against Fedlex / cantonal register — authoritative",
            "sourced_pdf": "read from the official cantonal SHR PDF (Gesetze folder); not yet live-checked",
            "cited_unverified": "a citation lifted from the form/Merkblatt, not yet resolved to source",
            "UNVERIFIED": "no source; do NOT rely on it",
            "missing": "no legal basis recorded yet ('zu ermitteln')",
        },
        "field_classification": "mapped=captures a requirement; identity_part=sub-field of "
            "a person-identity requirement; reason_facet=one option of a multi-choice "
            "requirement; form_mechanic=plumbing (signature/date), no legal basis needed; "
            "overcollection=collected with no legal basis (data-protection risk).",
        "datenhandhabung.scope": "allgemein=applies to every personal-data field; "
            "besonders_schuetzenswert=additionally applies to fields with a sensitive "
            "category (matching sensitive_category, or all when null); sektoral=applies "
            "only to fields whose legal basis cites the same law (match on law).",
    },
}


def verlevel(lc):
    if not lc or lc == "UNVERIFIED":
        return "UNVERIFIED"
    if lc == "verified":
        return "verified"
    if str(lc).startswith("Gesetze"):
        return "sourced_pdf"
    return "cited_unverified"


def basis_list(req, rlb, art_by_id, law_by_id):
    out = []
    for lb in rlb.get(req["id"], []):
        art = art_by_id[lb["article_id"]]; law = law_by_id[art["law_id"]]
        out.append({
            "jurisdiction": law["jurisdiction_level"], "law_title": law["title"],
            "law_short": law["short_title"], "sr_number": law["sr_number"],
            "cantonal_ref": law["cantonal_ref"], "article_no": art["article_no"],
            "citation_detail": lb["citation_detail"], "verification": verlevel(lb["last_checked"])})
    return out


def main():
    c = connect(DB_PATH)
    rows = lambda q: [dict(r) for r in c.execute(q).fetchall()]
    services = rows("SELECT * FROM service")
    laws = {l["id"]: dict(l) for l in c.execute("SELECT * FROM law")}
    arts = {a["id"]: dict(a) for a in c.execute("SELECT * FROM article")}
    reqs = {r["id"]: dict(r) for r in c.execute("SELECT * FROM requirement")}
    rlb = {}
    for lb in rows("SELECT * FROM requirement_legal_basis"):
        rlb.setdefault(lb["requirement_id"], []).append(lb)
    forms = rows("SELECT * FROM form")
    fields = rows("SELECT * FROM form_field ORDER BY form_id, raw_order")
    maps = {m["form_field_id"]: dict(m) for m in c.execute("SELECT * FROM field_mapping")}
    steps = {}
    for st in rows("SELECT * FROM process_step ORDER BY service_id, step_no"):
        steps.setdefault(st["service_id"], []).append({"step": st["step_no"], "description": st["description"], "mode": st["mode"]})
    findings = {}
    for f in rows("SELECT * FROM finding"):
        findings.setdefault(f["service_id"], []).append({"type": f["type"], "severity": f["severity"], "description": f["description"]})

    # logical Datenfeld catalogue: legal basis + eCH standard + DSG sensitivity
    dflb = {}
    for lb in rows("SELECT dflb.data_field_id did, a.article_no, dflb.citation_detail, dflb.last_checked, "
                   "l.title, l.short_title, l.jurisdiction_level, l.sr_number, l.cantonal_ref "
                   "FROM data_field_legal_basis dflb JOIN article a ON a.id=dflb.article_id "
                   "JOIN law l ON l.id=a.law_id"):
        dflb.setdefault(lb["did"], []).append({
            "jurisdiction": lb["jurisdiction_level"], "law_title": lb["title"],
            "law_short": lb["short_title"], "sr_number": lb["sr_number"],
            "cantonal_ref": lb["cantonal_ref"], "article_no": lb["article_no"],
            "citation_detail": lb["citation_detail"], "verification": verlevel(lb["last_checked"])})
    eshk = {}
    try:
        for r in rows("SELECT code, titel FROM esh_standard"):
            eshk[r["code"]] = r["titel"]
    except Exception:
        pass
    subs = {}
    for r in rows("SELECT sf.data_field_id d, sf.name, sf.ech_status, sf.esh_code, sf.esh_element, "
                  "e.standard estd, e.name ename, st.status sstat, "
                  "COALESCE(s1.code, s2.code) scode "
                  "FROM data_subfield sf "
                  "LEFT JOIN ech_element e ON e.id=sf.ech_element_id "
                  "LEFT JOIN ech_standard s1 ON s1.code=e.standard "
                  "LEFT JOIN ech_standard s2 ON s2.code=sf.ech_standard_code "
                  "LEFT JOIN ech_standard st ON st.code=COALESCE(e.standard, sf.ech_standard_code) "
                  "ORDER BY sf.data_field_id, sf.ord"):
        sub = {"name": r["name"],
               "ech": ({"standard": r["scode"], "element": r["ename"],
                        "standard_status": r["sstat"], "status": r["ech_status"]}
                       if r["scode"] else {"status": r["ech_status"] or "offen"})}
        if r["esh_code"]:
            sub["esh_entwurf"] = {"code": r["esh_code"], "element": r["esh_element"],
                                  "titel": eshk.get(r["esh_code"]), "status": "entwurf"}
        subs.setdefault(r["d"], []).append(sub)

    dfs_by_form = {}
    for d in rows("SELECT d.*, e.standard estd, e.name ename, e.datatype edt, "
                  "COALESCE(s1.title, s2.title) etitle, COALESCE(s1.url, s2.url) eurl, "
                  "COALESCE(s1.status, s2.status) estatus "
                  "FROM data_field d "
                  "LEFT JOIN ech_element e ON e.id=d.ech_element_id "
                  "LEFT JOIN ech_standard s1 ON s1.code=e.standard "
                  "LEFT JOIN ech_standard s2 ON s2.code=d.ech_standard_code "
                  "ORDER BY d.form_id, d.ord"):
        std = d["estd"] or d["ech_standard_code"]
        dfs_by_form.setdefault(d["form_id"], []).append({
            "name": d["name"], "definition": d["definition"], "data_type": d["data_type"],
            "required": bool(d["required"]),
            "allowed_values": json.loads(d["allowed_values"]) if d["allowed_values"] else [],
            "sensitive": bool(d["sensitive"]), "sensitive_category": d["sensitive"],
            "ech": ({"status": d["ech_status"], "standard": std, "element": d["ename"],
                     "datatype": d["edt"], "standard_titel": d["etitle"], "url": d["eurl"],
                     "standard_status": d["estatus"]}
                    if std else {"status": d["ech_status"] or "offen"}),
            "legal_basis": dflb.get(d["id"], []),
            "over_collection": bool(d["no_basis"]),
            "esh_entwurf": ({"code": d["esh_code"], "element": d["esh_element"],
                             "titel": eshk.get(d["esh_code"]), "status": "entwurf"}
                            if d["esh_code"] else None),
            "subfields": subs.get(d["id"], [])})

    # data-governance rules: how the data may be stored, treated, communicated
    datarules = []
    try:
        for r in rows("SELECT dr.aspect, dr.scope, dr.sensitive_category, dr.summary, "
                      "dr.quote, dr.quote_verified, a.article_no, a.heading, "
                      "l.title law_title, l.short_title law_short, l.sr_number, "
                      "l.jurisdiction_level jurisdiction "
                      "FROM data_rule dr JOIN article a ON a.id=dr.article_id "
                      "JOIN law l ON l.id=a.law_id ORDER BY dr.scope, a.law_id, a.id"):
            r["quote_verified"] = bool(r["quote_verified"])
            datarules.append(r)
    except Exception:
        pass
    c.close()

    fields_by_form = {}
    for fl in fields:
        m = maps.get(fl["id"]); req = reqs.get(m["requirement_id"]) if (m and m["requirement_id"]) else None
        pth = compose_path({"label": fl["label"], "section": fl["section"],
                            "mapping": ({"requirement_id": m["requirement_id"],
                                         "classification": m["classification"]} if m else None)}, reqs)
        rec = {
            "label": fl["label"], "path": pth, "section": fl["section"], "field_type": fl["field_type"],
            "classification": m["classification"] if m else None,
            "match_status": m["match_status"] if m else None,
            "legal_basis": basis_list(req, rlb, arts, laws) if req else [],
        }
        fields_by_form.setdefault(fl["form_id"], []).append(rec)
    forms_by_service = {}
    for fm in forms:
        forms_by_service.setdefault(fm["service_id"], []).append({
            "title": fm["title"], "source_file": fm["source_file"], "file_type": fm["file_type"],
            "title_content_mismatch": bool(fm["title_content_mismatch"]),
            "data_fields": dfs_by_form.get(fm["id"], []),
            "fields": fields_by_form.get(fm["id"], [])})

    out_services = []
    jsonl, dfl = [], []
    for s in services:
        svc = {"id": s["id"], "slug": s["slug"], "name": s["name"],
               "department": s["department"], "dienststelle": s["dienststelle"],
               "description": s["description"], "forms": forms_by_service.get(s["id"], []),
               "process_steps": steps.get(s["id"], []), "findings": findings.get(s["id"], [])}
        out_services.append(svc)
        for fm in svc["forms"]:
            for fld in fm["fields"]:
                jsonl.append({"service": s["name"], "department": s["department"],
                              "dienststelle": s["dienststelle"], "form": fm["title"],
                              "source_file": fm["source_file"], **fld})
            for d in fm["data_fields"]:
                dfl.append({"service": s["name"], "department": s["department"],
                            "dienststelle": s["dienststelle"], "form": fm["title"],
                            "source_file": fm["source_file"], **d})

    doc = {"meta": {**META, "generated_at": datetime.now().isoformat(timespec="seconds")},
           "datenhandhabung": datarules, "services": out_services}
    json.dump(doc, open(os.path.join(ROOT, "citygov_llm.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "citygov_fields.jsonl"), "w", encoding="utf-8") as fh:
        for r in jsonl:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(ROOT, "citygov_datafields.jsonl"), "w", encoding="utf-8") as fh:
        for r in dfl:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(ROOT, "citygov_datarules.jsonl"), "w", encoding="utf-8") as fh:
        for r in datarules:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    nech = sum(1 for r in dfl if r["ech"].get("standard"))
    print(f"wrote citygov_llm.json ({len(out_services)} services) + "
          f"citygov_fields.jsonl ({len(jsonl)} widget records) + "
          f"citygov_datafields.jsonl ({len(dfl)} Datenfelder, {nech} mit eCH-Standard) + "
          f"citygov_datarules.jsonl ({len(datarules)} Regeln)")


if __name__ == "__main__":
    main()
