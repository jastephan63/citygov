#!/usr/bin/env python3
"""Export citygov.db -> data_export.json (the single file the dashboard reads).

Everything the dashboard shows is *derived here* from the source of truth, so the
visualization can never drift from the data (convention 9). In particular the
three reconciliation buckets are computed, never stored:

  * match         — a service requirement with >=1 CONFIRMED capturing field.
  * legal gap     — a service requirement with no confirmed capturing field.
  * over-collection — a form field classified 'overcollection'.

A requirement matched only by a PROPOSED (unconfirmed) mapping is reported as
'proposed', NOT counted as compliant (convention 5) — so the compliance number
is honest and never inflated.

    python3 scripts/export_json.py
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, EXPORT_PATH, LOGS_DIR, connect, log


def rows(conn, q, *a):
    return [dict(r) for r in conn.execute(q, a).fetchall()]


def build(conn):
    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "verification_note": "Citations marked UNVERIFIED have NOT been checked "
                             "against Fedlex / the cantonal register. Do not treat "
                             "them as authoritative.",
    }

    services = rows(conn, "SELECT * FROM service ORDER BY name")
    laws = rows(conn, "SELECT * FROM law ORDER BY jurisdiction_level, title")
    articles = rows(conn, "SELECT * FROM article")
    requirements = rows(conn, "SELECT * FROM requirement ORDER BY data_point")
    rlb = rows(conn, "SELECT * FROM requirement_legal_basis")
    svc_req = rows(conn, "SELECT * FROM service_requirement")
    forms = rows(conn, "SELECT * FROM form")
    fields = rows(conn, "SELECT * FROM form_field ORDER BY form_id, raw_order")
    mappings = {m["form_field_id"]: m
                for m in rows(conn, "SELECT * FROM field_mapping")}
    steps = rows(conn, "SELECT * FROM process_step ORDER BY service_id, step_no")
    documents = rows(conn, "SELECT * FROM document ORDER BY doc_type, file_name")
    declared_findings = rows(conn, "SELECT * FROM finding")

    law_by_id = {l["id"]: l for l in laws}
    art_by_id = {a["id"]: a for a in articles}
    req_by_id = {r["id"]: r for r in requirements}

    # ---- legal basis attached to each requirement (with full citation) -------
    for r in requirements:
        r["legal_basis"] = []
        r["services"] = []
    for lb in rlb:
        art = art_by_id[lb["article_id"]]
        law = law_by_id[art["law_id"]]
        req_by_id[lb["requirement_id"]]["legal_basis"].append({
            "law_id": law["id"], "law_slug": law["slug"], "law_title": law["title"],
            "law_short": law["short_title"], "jurisdiction": law["jurisdiction_level"],
            "sr_number": law["sr_number"], "cantonal_ref": law["cantonal_ref"],
            "article_id": art["id"], "article_no": art["article_no"],
            "article_heading": art["heading"],
            "citation_detail": lb["citation_detail"],
            "last_checked": lb["last_checked"],
        })
    # which services demand each requirement
    reqs_by_service = {}
    for sr in svc_req:
        reqs_by_service.setdefault(sr["service_id"], []).append(sr["requirement_id"])
        req_by_id[sr["requirement_id"]]["services"].append(sr["service_id"])

    # ---- attach fields + their mapping to each form --------------------------
    fields_by_form = {}
    for f in fields:
        f["options"] = json.loads(f["options"]) if f["options"] else None
        f["mapping"] = mappings.get(f["id"])
        fields_by_form.setdefault(f["form_id"], []).append(f)
    forms_by_service = {}
    for fm in forms:
        fm["fields"] = fields_by_form.get(fm["id"], [])
        forms_by_service.setdefault(fm["service_id"], []).append(fm)

    # ---- nested law -> article tree (for the law-side tree view) -------------
    arts_by_law = {}
    for a in articles:
        arts_by_law.setdefault(a["law_id"], []).append(a)
    for l in laws:
        l["articles"] = arts_by_law.get(l["id"], [])

    # =====================================================================
    # DERIVED reconciliation, per service
    # =====================================================================
    reconciliation = {}
    derived_findings = []
    for s in services:
        sid = s["id"]
        svc_reqs = [req_by_id[rid] for rid in reqs_by_service.get(sid, [])]
        svc_forms = forms_by_service.get(sid, [])

        # confirmed/proposed capturing fields per requirement
        cap = {}   # requirement_id -> {"confirmed":[...], "proposed":[...]}
        over = []  # overcollection fields
        field_view = []
        for fm in svc_forms:
            for fl in fm["fields"]:
                m = fl["mapping"]
                cls = m["classification"] if m else None
                entry = {"form": fm["title"], "field_id": fl["id"],
                         "label": fl["label"], "section": fl["section"],
                         "field_type": fl["field_type"],
                         "classification": cls,
                         "match_status": m["match_status"] if m else None,
                         "mapped_by": m["mapped_by"] if m else None,
                         "requirement_id": m["requirement_id"] if m else None}
                field_view.append(entry)
                if not m:
                    continue
                if cls == "overcollection":
                    over.append(entry)
                elif m["requirement_id"]:
                    bucket = cap.setdefault(m["requirement_id"],
                                            {"confirmed": [], "proposed": []})
                    key = "confirmed" if m["match_status"] == "confirmed" else "proposed"
                    bucket[key].append(entry)

        req_view, n_match, n_proposed, n_gap = [], 0, 0, 0
        for r in svc_reqs:
            c = cap.get(r["id"], {"confirmed": [], "proposed": []})
            if c["confirmed"]:
                status = "match"; n_match += 1
            elif c["proposed"]:
                status = "proposed"; n_proposed += 1
            else:
                status = "legal_gap"; n_gap += 1
                derived_findings.append({
                    "type": "legal_gap", "severity": "critical",
                    "service_id": sid, "service": s["name"],
                    "description": f"Anforderung '{r['data_point']}' ist gesetzlich "
                                   f"verlangt, wird aber von keinem Formularfeld erfasst."})
            req_view.append({
                "requirement_id": r["id"], "data_point": r["data_point"],
                "label": r["label"], "data_type": r["data_type"],
                "condition": r["condition"], "is_composite": bool(r["is_composite"]),
                "legal_basis": r["legal_basis"], "status": status,
                "captured_by_confirmed": c["confirmed"],
                "captured_by_proposed": c["proposed"]})

        for o in over:
            derived_findings.append({
                "type": "overcollection", "severity": "warning",
                "service_id": sid, "service": s["name"],
                "description": f"Formularfeld '{o['label']}' wird erhoben, hat aber "
                               f"keine gesetzliche Grundlage fuer diesen Dienst (DSG-Risiko)."})

        total = len(svc_reqs)
        reconciliation[sid] = {
            "service": s,
            "summary": {
                "requirements_total": total,
                "matched": n_match, "proposed": n_proposed, "legal_gaps": n_gap,
                "overcollection": len(over),
                "compliance_pct": round(100 * n_match / total) if total else None,
                "fields_total": len(field_view),
            },
            "requirements": req_view,
            "fields": field_view,
            "overcollection_fields": over,
        }

    # ---- citation TODO list (convention 6) -----------------------------------
    citation_todo = []
    for l in laws:
        for a in l["articles"]:
            if a["last_checked"] != "verified":
                citation_todo.append({
                    "law": l["title"], "law_slug": l["slug"],
                    "jurisdiction": l["jurisdiction_level"],
                    "sr_number": l["sr_number"], "article_no": a["article_no"],
                    "heading": a["heading"], "last_checked": a["last_checked"]})
    for c in citation_todo:
        sourced = str(c["last_checked"]).startswith("Gesetze")
        derived_findings.append({
            "type": "citation_todo",
            "severity": "info" if sourced else "warning",
            "service_id": None,
            "description": (
                f"{'Quelle: '+c['last_checked']+' — Live-Abgleich offen' if sourced else 'UNVERIFIED — keine Quelle'}: "
                f"{c['law']} Art. {c['article_no']} ({c['jurisdiction']})."
                f"{'' if sourced else ' Gegen Fedlex/kant. Register pruefen, nicht erfinden.'}")})

    data.update({
        "services": services, "laws": laws, "requirements": requirements,
        "forms": forms, "process_steps": steps, "documents": documents,
        "declared_findings": declared_findings, "derived_findings": derived_findings,
        "reconciliation": reconciliation, "citation_todo": citation_todo,
    })
    return data


def main():
    conn = connect(DB_PATH)
    data = build(conn)
    conn.close()
    with open(EXPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(os.path.join(LOGS_DIR, "citation_todo.txt"), "w", encoding="utf-8") as fh:
        fh.write("UNVERIFIED CITATIONS — verify against Fedlex / cantonal register\n")
        fh.write("=" * 64 + "\n")
        for c in data["citation_todo"]:
            fh.write(f"[{c['jurisdiction']:9}] {c['law']}\n"
                     f"            Art. {c['article_no']}  ({c['heading']})  "
                     f"SR={c['sr_number']}  status={c['last_checked']}\n")

    s = data["reconciliation"]
    print(f"exported {EXPORT_PATH}")
    for sid, rec in s.items():
        sm = rec["summary"]
        print(f"  {rec['service']['name']}: {sm['matched']}/{sm['requirements_total']} "
              f"matched, {sm['proposed']} proposed, {sm['legal_gaps']} gap(s), "
              f"{sm['overcollection']} over-collection")


if __name__ == "__main__":
    main()
