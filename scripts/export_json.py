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
import json, os, re, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, EXPORT_PATH, LOGS_DIR, connect
from fix_quality import is_bad_label


def rows(conn, q, *a):
    return [dict(r) for r in conn.execute(q, a).fetchall()]


def _n(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def compose_path(f, req_by_id):
    """Full-depth contextual label for a field, so a sub-item reads standalone:
    'Kennzeichnung › Nummer', 'Personalien › Vorname', 'Rasse › Terrier'.
    Levels = section  ›  group (the requirement a sub-field maps to)  ›  the
    field's own label (which may itself already be a dotted breadcrumb). Levels
    are de-duplicated so nothing repeats, and the field's own label is always the
    leaf. Purely derived — the DB label is untouched."""
    label = (f.get("label") or "").strip()
    parts, seen = [], set()

    def add(x, guard=False):
        x = (x or "").strip(" ›").strip()
        if not x:
            return
        # guarded levels (section/group) must look like a real heading: a proper
        # word, not too long, not a mangled slug token (e.g. '1erdsonde','12bivalent'),
        # and NOT a raw technical field name (Kontrollkästchen 20, Optionsfeld 19, …).
        if guard and (len(x) > 48 or re.match(r"^\d", x)
                      or not re.search(r"[A-Za-zÄÖÜäöü]{3,}", x)
                      or is_bad_label(x)):
            return
        n = _n(x)
        if n and n not in seen:
            seen.add(n)
            parts.append(x)

    grp = None
    m = f.get("mapping")
    if m and m.get("requirement_id") and m.get("classification") in ("identity_part", "reason_facet"):
        r = req_by_id.get(m["requirement_id"])
        if r:
            grp = (r.get("data_point") or "").strip()
    sec = (f.get("section") or "").strip()
    if sec and grp:                                # drop section if it just echoes the group
        st = set(re.findall(r"[a-zäöü]{4,}", sec.lower()))
        gt = set(re.findall(r"[a-zäöü]{4,}", grp.lower()))
        if st & gt:
            sec = ""
    add(sec, True)                                 # section header (top level)
    add(grp, True)                                 # the group this sub-field belongs to
    for seg in label.split("›"):                   # the field's own (possibly nested) label
        add(seg)
    return " › ".join(parts) if parts else label


def _has_esh(conn):
    try:
        conn.execute("SELECT 1 FROM esh_standard LIMIT 1")
        return True
    except Exception:
        return False


def build(conn):
    services = rows(conn, "SELECT id,slug,name,dienststelle,department,COALESCE(in_dvsh,0) AS in_dvsh FROM service ORDER BY name")
    laws = rows(conn, "SELECT id,slug,title,short_title,jurisdiction_level,sr_number,"
                      "cantonal_ref,last_checked FROM law")
    articles = rows(conn, "SELECT id,law_id,article_no,heading,last_checked FROM article")
    requirements = rows(conn, "SELECT id,data_point_key,data_point,label,data_type,condition,"
                              "is_composite FROM requirement")
    rlb = rows(conn, "SELECT * FROM requirement_legal_basis")
    svc_req = rows(conn, "SELECT * FROM service_requirement")
    forms = rows(conn, "SELECT id,service_id,title,actual_purpose,title_content_mismatch,"
                       "mismatch_note,publisher_dienststelle,source_file,file_type,"
                       "purpose,dsfa_status,submission_channel,signature_requirement,"
                       "signature_evidence,acroform,parse_error FROM form")
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
        f["path"] = compose_path(f, req_by_id)     # full-depth contextual label
        fields_by_form.setdefault(f["form_id"], []).append(f)

    # logical data-field catalogue (Datenfeld-Katalog), if derived for this form
    dfs_by_form = {}
    try:
        df_lb = {}
        for lb in rows(conn, "SELECT dflb.data_field_id did, a.article_no, a.heading, a.text_excerpt, "
                             "l.id lid, l.title, l.short_title, l.jurisdiction_level, l.sr_number, l.cantonal_ref, "
                             "dflb.last_checked, dflb.relation FROM data_field_legal_basis dflb "
                             "JOIN article a ON a.id=dflb.article_id JOIN law l ON l.id=a.law_id"):
            df_lb.setdefault(lb["did"], []).append({
                "law_id": lb["lid"],
                "jurisdiction": lb["jurisdiction_level"], "law_short": lb["short_title"],
                "law_title": lb["title"], "sr_number": lb["sr_number"], "cantonal_ref": lb["cantonal_ref"],
                "article_no": lb["article_no"], "article_heading": lb["heading"],
                "quote": (lb["text_excerpt"] or "")[:1600],
                "last_checked": lb["last_checked"], "relation": lb["relation"]})
        ech, ech_std = {}, {}
        try:
            for s in rows(conn, "SELECT code, title, url, n_elements, status, reifegrad "
                                "FROM ech_standard"):
                ech_std[s["code"]] = s
            for e in rows(conn, "SELECT e.id, e.standard, e.name, e.datatype, s.title, s.url, "
                                "s.status, s.reifegrad "
                                "FROM ech_element e JOIN ech_standard s ON s.code=e.standard"):
                ech[e["id"]] = {"standard": e["standard"], "element": e["name"],
                                "datatype": e["datatype"], "standard_titel": e["title"], "url": e["url"],
                                "status": e["status"], "reifegrad": e["reifegrad"]}
        except Exception:
            pass
        # subfields with their OWN eCH element (Name/Vorname/Geburtsdatum each exact)
        esh_std2 = {}
        try:
            for r in rows(conn, "SELECT code, titel FROM esh_standard"):
                esh_std2[r["code"]] = r
        except Exception:
            pass
        subs_by_field = {}
        try:
            for s in rows(conn, "SELECT sf.*, st.title stitle, st.url surl, st.n_elements snel, "
                                "st.status sstatus, st.reifegrad sreif "
                                "FROM data_subfield sf LEFT JOIN ech_standard st "
                                "ON st.code=sf.ech_standard_code ORDER BY sf.data_field_id, sf.ord"):
                e = ech.get(s.get("ech_element_id"))
                if not e and s.get("ech_standard_code"):
                    e = {"standard": s["ech_standard_code"], "element": None, "datatype": None,
                         "standard_titel": s["stitle"], "url": s["surl"], "n_elements": s["snel"],
                         "status": s["sstatus"], "reifegrad": s["sreif"]}
                sub = {"name": s["name"], "ech": e, "ech_status": s.get("ech_status")}
                if s.get("esh_code") and s["esh_code"] in esh_std2:
                    sub["esh"] = {"code": s["esh_code"], "element": s.get("esh_element"),
                                  "titel": esh_std2[s["esh_code"]]["titel"]}
                subs_by_field.setdefault(s["data_field_id"], []).append(sub)
        except Exception:
            pass
        esh_std = {}
        try:
            for r in rows(conn, "SELECT code, titel, beschreibung, n_felder FROM esh_standard"):
                esh_std[r["code"]] = r
        except Exception:
            pass
        for d in rows(conn, "SELECT * FROM data_field ORDER BY form_id, ord"):
            d["ech"] = ech.get(d.get("ech_element_id"))
            if d.get("esh_code") and d["esh_code"] in esh_std:
                d["esh"] = {"code": d["esh_code"], "element": d.get("esh_element"),
                            "titel": esh_std[d["esh_code"]]["titel"]}
            if not d["ech"] and d.get("ech_standard_code"):
                s = ech_std.get(d["ech_standard_code"])
                if s:      # standard-level match; n_elements>0 means an element is still owed
                    d["ech"] = {"standard": s["code"], "element": None, "datatype": None,
                                "standard_titel": s["title"], "url": s["url"],
                                "n_elements": s["n_elements"], "status": s["status"],
                                "reifegrad": s["reifegrad"]}
            for k in ("allowed_values", "subfields", "source_widgets"):
                d[k] = json.loads(d[k]) if d.get(k) else []
            if d["id"] in subs_by_field:      # normalised subfields win over the raw JSON
                d["subfields"] = subs_by_field[d["id"]]
            d["required"] = bool(d["required"])
            d["no_basis"] = bool(d.get("no_basis"))
            d["legal_basis"] = df_lb.get(d["id"], [])
            dfs_by_form.setdefault(d["form_id"], []).append(d)
    except Exception:
        pass

    checks = {}
    try:
        for r in rows(conn, "SELECT form_id, status, quelle, dvsh_neu, note, "
                            "substr(checked_at,1,10) d FROM form_check"):
            checks[r["form_id"]] = r
    except Exception:
        pass

    # Verzeichnis layer: recipients, retention profile, decisions — per form
    disc_by_form, ret_by_form, dec_by_form = {}, {}, {}
    try:
        for r in rows(conn, "SELECT fd.form_id, fd.empfaenger, fd.mode, a.article_no, "
                            "l.short_title, l.sr_number FROM form_disclosure fd "
                            "LEFT JOIN article a ON a.id=fd.article_id "
                            "LEFT JOIN law l ON l.id=a.law_id ORDER BY fd.empfaenger"):
            disc_by_form.setdefault(r.pop("form_id"), []).append(r)
        # a form's specific retention terms = terms of retention rules in the laws it cites
        law_terms = {}
        for r in rows(conn, "SELECT a.law_id, rt.duration_value, rt.duration_unit, rt.min_or_max, "
                            "rt.trigger_event, rt.disposition, dr.aspect, dr.summary, "
                            "a.article_no, l.short_title, l.sr_number "
                            "FROM retention_term rt JOIN data_rule dr ON dr.id=rt.data_rule_id "
                            "JOIN article a ON a.id=dr.article_id JOIN law l ON l.id=a.law_id "
                            "WHERE dr.scope='sektoral'"):
            law_terms.setdefault(r.pop("law_id"), []).append(r)
        for r in rows(conn, "SELECT DISTINCT d.form_id, a.law_id FROM data_field_legal_basis lb "
                            "JOIN data_field d ON d.id=lb.data_field_id "
                            "JOIN article a ON a.id=lb.article_id"):
            for t in law_terms.get(r["law_id"], []):
                ret_by_form.setdefault(r["form_id"], []).append(t)
        for r in rows(conn, "SELECT * FROM retention_decision"):
            dec_by_form.setdefault(r.pop("form_id"), []).append(r)
    except Exception:
        pass

    # Verfahren layer: enclosures, outcomes, near-duplicates, guided-flow anchor
    beil_by_form, out_by_form, sim_by_form = {}, {}, {}
    flow_forms = set()
    try:
        for r in rows(conn, "SELECT form_id, bezeichnung, obligatorium, bedingung, halter, "
                            "fetchable, source FROM beilage ORDER BY obligatorium, bezeichnung"):
            beil_by_form.setdefault(r.pop("form_id"), []).append(r)
        for r in rows(conn, "SELECT * FROM form_outcome"):
            out_by_form[r.pop("form_id")] = r
        tit = {f["id"]: f["title"] for f in forms}
        for r in rows(conn, "SELECT form_a, form_b, jaccard_names, verdict FROM form_similarity "
                            "WHERE jaccard_names>=0.5 AND (verdict IS NULL OR verdict!='ok')"):
            for me, other in ((r["form_a"], r["form_b"]), (r["form_b"], r["form_a"])):
                sim_by_form.setdefault(me, []).append(
                    {"form_id": other, "titel": tit.get(other, "?"),
                     "jaccard": r["jaccard_names"], "verdict": r["verdict"]})
        flow_forms = {r["form_id"] for r in rows(conn, "SELECT DISTINCT form_id FROM formflow")}
    except Exception:
        pass
    # which eCH elements the Einwohnerregister already holds (for the burden metric)
    reg_elems = set()
    try:
        reg_elems = {r["id"] for r in rows(
            conn, "SELECT id FROM ech_element WHERE standard IN "
                  "('eCH-0044','eCH-0010','eCH-0011','eCH-0007','eCH-0008')")}
        checks_due = {r["form_id"]: r["next_check_due"] for r in rows(
            conn, "SELECT form_id, next_check_due FROM form_check")}
    except Exception:
        checks_due = {}
    conn_elem_ids = {}
    try:
        for eid, e in ech.items():
            conn_elem_ids[(e["standard"], e["element"])] = eid
    except Exception:
        pass

    # exchange readiness, citizen burden and named digitalization blockers per form
    for fm in forms:
        pts = ok = req = pref = att = 0
        for d in dfs_by_form.get(fm["id"], []):
            subs = [s for s in (d.get("subfields") or []) if isinstance(s, dict)]
            if d.get("data_type") == "attachment":
                att += 1
            units = subs if subs else [d]
            pts += len(units)
            for u in units:
                e = u.get("ech")
                if e and e.get("element"):
                    ok += 1
                if d.get("required"):
                    req += 1
                    eid = None
                    # prefillable = the unit's element is one the Einwohnerregister holds
                    if e and e.get("element"):
                        eid = conn_elem_ids.get((e.get("standard"), e.get("element")))
                    if eid in reg_elems:
                        pref += 1
        fm["exchange_pct"] = round(100 * ok / pts) if pts else None
        # time model: ~0.4 min per required input, 5 min per enclosure (documented here)
        fm["burden"] = ({"inputs": req, "attachments": att, "prefillable": pref,
                         "minutes": round(req * 0.4 + att * 5, 1),
                         "minutes_saved": round(pref * 0.4, 1)} if pts else None)
        blockers = []
        if fm.get("signature_requirement") == "handschriftlich":
            blockers.append("Unterschrift")
        if fm.get("parse_error") or fm.get("acroform") == 0:
            blockers.append("Quelle nicht befüllbar")
        if fm.get("submission_channel") != "online_formular":
            blockers.append("kein Online-Kanal")
        if fm["exchange_pct"] is not None and fm["exchange_pct"] < 50:
            blockers.append("eCH-Abdeckung < 50%")
        if fm["id"] not in flow_forms:
            blockers.append("kein geführter Flow")
        fm["blockers"] = blockers if pts else None
        fm["has_flow"] = fm["id"] in flow_forms
        fm["next_check_due"] = checks_due.get(fm["id"])
        fm["fields"] = fields_by_form.get(fm["id"], [])
        fm["data_fields"] = dfs_by_form.get(fm["id"], [])
        fm["check"] = checks.get(fm["id"])
        fm["disclosures"] = disc_by_form.get(fm["id"], [])
        fm["retention"] = ret_by_form.get(fm["id"], [])
        fm["retention_decisions"] = dec_by_form.get(fm["id"], [])
        fm["beilagen"] = beil_by_form.get(fm["id"], [])
        fm["outcome"] = out_by_form.get(fm["id"])
        fm["similar"] = sim_by_form.get(fm["id"], [])

    # DVSH modeller data (source of truth for the service), keyed by service id
    dvsh_by_service = {}
    try:
        for d in rows(conn, "SELECT * FROM dvsh_service WHERE service_id IS NOT NULL"):
            for k in ("voraussetzungen", "unterlagen", "ablauf", "recht_kantonal",
                      "recht_bund", "externe_links", "abgabe", "kontakt", "documents",
                      "sources", "form_definitions", "submission_endpoint",
                      "completeness", "opening_hours"):
                try:
                    d[k] = json.loads(d[k]) if d.get(k) else []
                except Exception:
                    d[k] = d.get(k) or []
            dvsh_by_service.setdefault(d["service_id"], []).append(d)
    except Exception:
        pass
    # SHEP: the PUBLISHED citizen view of the same service
    shep_by_service = {}
    try:
        for sp in rows(conn, "SELECT * FROM shep_service WHERE service_id IS NOT NULL"):
            for k in ("voraussetzungen", "unterlagen", "ablauf", "links", "dokumente"):
                try:
                    sp[k] = json.loads(sp[k]) if sp.get(k) else []
                except Exception:
                    sp[k] = []
            shep_by_service[sp["service_id"]] = sp
    except Exception:
        pass
    for s in services:
        got = dvsh_by_service.get(s["id"])
        if got:
            s["dvsh"] = got[0]
        if s["id"] in shep_by_service:
            s["shep"] = shep_by_service[s["id"]]

    steps_by_service = {}
    for st in steps:
        steps_by_service.setdefault(st["service_id"], []).append(st)

    esh_katalog = []
    if _has_esh(conn):
        esh_katalog = rows(conn, "SELECT code, titel, beschreibung, themen, status, n_felder "
                                 "FROM esh_standard ORDER BY code")

    # canonical attribute catalogue + the divergence lists for the Datenkatalog tab
    katalog, dienststellen = [], []
    try:
        katalog = rows(conn, "SELECT ca.id, ca.label, ca.datatype, ca.sensitive_categories, "
                             "ca.register_source, ca.n_instances, ca.n_forms, "
                             "e.standard ech_standard, e.name ech_element, ca.esh_key "
                             "FROM canonical_attribute ca "
                             "LEFT JOIN ech_element e ON e.id=ca.ech_element_id "
                             "ORDER BY ca.n_forms DESC, ca.n_instances DESC")
        dienststellen = rows(conn, "SELECT name, department, dateninhaber, kontakt FROM dienststelle")
    except Exception:
        pass

    # data-governance rules (how data may be stored, treated, communicated);
    # the dashboard groups by scope and matches 'sektoral' rules to a form via law_id
    handhabung = []
    try:
        for r in rows(conn, "SELECT dr.aspect, dr.scope, dr.sensitive_category, dr.summary, "
                            "dr.quote, dr.quote_verified, a.article_no, a.heading, a.law_id, "
                            "l.short_title, l.title law_title, l.sr_number, l.jurisdiction_level "
                            "FROM data_rule dr JOIN article a ON a.id=dr.article_id "
                            "JOIN law l ON l.id=a.law_id ORDER BY dr.scope, a.law_id, a.id"):
            handhabung.append(r)
    except Exception:
        pass

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
        "esh_katalog": esh_katalog, "datenhandhabung": handhabung,
        "attribut_katalog": katalog, "dienststellen": dienststellen,
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
