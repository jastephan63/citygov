#!/usr/bin/env python3
"""Export the databank in LLM-ready form (the durable artifact for later use).

The SQLite citygov.db remains the source of truth; this produces two stable,
self-describing files an LLM agent can ingest directly:

  citygov_llm.json   — nested: service -> form -> field -> legal_basis, with a
                       meta block explaining the verification levels and the
                       proposed/confirmed distinction so the model never mistakes
                       a draft for a verified fact.
  citygov_fields.jsonl — one JSON object per FIELD (flat, RAG-friendly): the field,
                       its service/office/department, classification, and legal
                       basis with provenance.

    python3 scripts/export_llm.py
"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, connect, DB_PATH

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
    c.close()

    fields_by_form = {}
    for fl in fields:
        m = maps.get(fl["id"]); req = reqs.get(m["requirement_id"]) if (m and m["requirement_id"]) else None
        rec = {
            "label": fl["label"], "section": fl["section"], "field_type": fl["field_type"],
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
            "fields": fields_by_form.get(fm["id"], [])})

    out_services = []
    jsonl = []
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

    doc = {"meta": {**META, "generated_at": datetime.now().isoformat(timespec="seconds")},
           "services": out_services}
    json.dump(doc, open(os.path.join(ROOT, "citygov_llm.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "citygov_fields.jsonl"), "w", encoding="utf-8") as fh:
        for r in jsonl:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote citygov_llm.json ({len(out_services)} services) + "
          f"citygov_fields.jsonl ({len(jsonl)} field records)")


if __name__ == "__main__":
    main()
