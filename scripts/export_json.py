#!/usr/bin/env python3
"""Export citygov.db -> data_export.json (compact base data for the dashboard).

The dashboard computes the reconciliation buckets in the browser from this base
data, so nothing is duplicated here (important now that the databank holds
hundreds of forms and thousands of fields). Heavy free-text columns
(source_note, text_excerpt, mapping notes) live in the DB for review but are not
inlined into the dashboard payload.

Also writes logs/citation_todo.txt — every not-yet-'verified' citation.

    python3 scripts/export_json.py
"""
import json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, EXPORT_PATH, LOGS_DIR, connect


def rows(conn, q, *a):
    return [dict(r) for r in conn.execute(q, a).fetchall()]


def build(conn):
    services = rows(conn, "SELECT id,slug,name,dienststelle,department FROM service ORDER BY name")
    laws = rows(conn, "SELECT id,slug,title,short_title,jurisdiction_level,sr_number,"
                      "cantonal_ref,last_checked FROM law")
    articles = rows(conn, "SELECT id,law_id,article_no,heading,last_checked FROM article")
    requirements = rows(conn, "SELECT id,data_point_key,data_point,label,data_type,condition,"
                              "is_composite FROM requirement")
    rlb = rows(conn, "SELECT * FROM requirement_legal_basis")
    svc_req = rows(conn, "SELECT * FROM service_requirement")
    forms = rows(conn, "SELECT id,service_id,title,actual_purpose,title_content_mismatch,"
                       "mismatch_note,publisher_dienststelle FROM form")
    fields = rows(conn, "SELECT id,form_id,label,section,field_type,options,raw_order "
                        "FROM form_field ORDER BY form_id, raw_order")
    mappings = {m["form_field_id"]: m for m in
                rows(conn, "SELECT form_field_id,requirement_id,classification,match_status,mapped_by "
                           "FROM field_mapping")}
    steps = rows(conn, "SELECT service_id,step_no,description,mode FROM process_step ORDER BY service_id,step_no")
    findings = rows(conn, "SELECT type,severity,service_id,form_id,law_id,description,status FROM finding")

    law_by_id = {l["id"]: l for l in laws}
    art_by_id = {a["id"]: a for a in articles}
    req_by_id = {r["id"]: r for r in requirements}

    for l in laws:
        l["articles"] = []
    for a in articles:
        law_by_id[a["law_id"]]["articles"].append(a)

    for r in requirements:
        r["legal_basis"] = []
        r["services"] = []
    for lb in rlb:
        art = art_by_id[lb["article_id"]]; law = law_by_id[art["law_id"]]
        req_by_id[lb["requirement_id"]]["legal_basis"].append({
            "jurisdiction": law["jurisdiction_level"], "law_short": law["short_title"],
            "law_title": law["title"], "sr_number": law["sr_number"],
            "cantonal_ref": law["cantonal_ref"], "article_no": art["article_no"],
            "article_heading": art["heading"], "citation_detail": lb["citation_detail"],
            "last_checked": lb["last_checked"]})
    for sr in svc_req:
        req_by_id[sr["requirement_id"]]["services"].append(sr["service_id"])

    fields_by_form = {}
    for f in fields:
        f["options"] = json.loads(f["options"]) if f["options"] else None
        m = mappings.get(f["id"])
        f["mapping"] = {"requirement_id": m["requirement_id"], "classification": m["classification"],
                        "match_status": m["match_status"], "mapped_by": m["mapped_by"]} if m else None
        fields_by_form.setdefault(f["form_id"], []).append(f)
    for fm in forms:
        fm["fields"] = fields_by_form.get(fm["id"], [])

    steps_by_service = {}
    for st in steps:
        steps_by_service.setdefault(st["service_id"], []).append(st)

    # citation TODO -> log file (not inlined; can be thousands of rows)
    todo = []
    for l in laws:
        for a in l["articles"]:
            if a["last_checked"] != "verified":
                todo.append((l["jurisdiction_level"], l["title"], l["sr_number"] or l["cantonal_ref"],
                             a["article_no"], a["heading"], a["last_checked"]))

    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "verification_note": "Zitate 'UNVERIFIED' sind nicht amtlich geprüft. "
                             "'Quelle' = aus offizieller SHR-PDF gelesen. Auto-Entwürfe: "
                             "Mappings 'proposed', juristisch zu prüfen.",
        "services": services, "laws": laws, "requirements": requirements,
        "forms": forms, "service_requirements": svc_req,
        "process_steps_by_service": steps_by_service,
        "findings": findings, "citation_todo_count": len(todo),
    }
    return data, todo


def main():
    conn = connect(DB_PATH)
    data, todo = build(conn)
    conn.close()
    with open(EXPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(os.path.join(LOGS_DIR, "citation_todo.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"UNVERIFIED / unsourced CITATIONS to verify ({len(todo)})\n" + "=" * 60 + "\n")
        for jur, title, num, art, head, lc in todo:
            fh.write(f"[{jur:9}] {title}  | Art. {art} ({head})  ref={num}  status={lc}\n")
    sz = os.path.getsize(EXPORT_PATH) / 1024
    print(f"exported {EXPORT_PATH}  ({sz:.0f} KB)")
    print(f"  services={len(data['services'])} forms={len(data['forms'])} "
          f"requirements={len(data['requirements'])} citation_todo={len(todo)}")


if __name__ == "__main__":
    main()
