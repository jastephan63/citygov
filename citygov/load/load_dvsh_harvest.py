#!/usr/bin/env python3
"""Ingest a full DVSH modeller harvest (read-only page-context export) into the
databank: refresh dvsh_service for every service, store the organisation tree,
and keep/extend the service matching.

The harvest file is produced in the browser from the modeller's own tRPC
queries (strictly GETs) and saved to ../DVSH/. DVSH is the source of truth for
service modelling — this loader REPLACES the dvsh_service rows wholesale but
never invents a match: existing service_id links are preserved by dvsh_id, new
DVSH services are matched by slug/normalised title, and whatever stays
unmatched becomes a NEW service row (DVSH-first world) rather than a guess.
A new row takes the databank's spelling of its office (the office of our rows
already linked to the same DVSH organisation, else the closest existing office
name, else DVSH's own) and is marked «Themengruppe noch nicht zugeordnet» until
the Lebenslagen panel has placed it (the gate wants a group or a reason).

Before the mirror is replaced, quellen_log.record_changes() writes what this
harvest changed against the one the databank held (quellen_aenderung, dated);
--vorher <YYYY-MM-DD> names that earlier harvest when the log has no row for it
yet (only the first logged run needs it).

Idempotent. Staging -> validate -> swap.

    python3 scripts/load_dvsh_harvest.py ../DVSH/dvsh_harvest_2026-10-28.json [--vorher 2026-09-03]
"""
import difflib, json, os, re, shutil, sys
from collections import Counter
from citygov.core.common import DB_PATH, connect, norm_ascii as norm
from citygov.checks.validate_db import validate
from citygov.load import quellen_log

# the columns whose change the harvest log records
COMPARE = ["title", "kurzbeschreibung", "beschreibung", "voraussetzungen", "unterlagen", "ablauf",
           "bearbeitungsdauer", "fristen", "gebuehren", "recht_kantonal", "recht_bund",
           "externe_links", "submission_endpoint", "documents", "form_definitions",
           "vollzugsbehoerde", "email", "phone", "address", "opening_hours", "status", "online",
           "endpoint_typ"]

DDL = """
CREATE TABLE IF NOT EXISTS dvsh_organisation (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER,
    slug TEXT, name TEXT, kind TEXT,
    contact_name TEXT, contact_email TEXT, contact_phone TEXT,
    contact_address TEXT, contact_url TEXT, opening_hours TEXT,
    updated_at TEXT
);
"""
NEWCOLS = ["status TEXT", "online INTEGER", "online_version INTEGER", "published_at TEXT",
           "dvsh_updated_at TEXT", "endpoint_typ TEXT", "vollzugsbehoerde TEXT",
           "submission_endpoint TEXT", "documents TEXT", "sources TEXT",
           "form_definitions TEXT", "completeness TEXT", "email TEXT", "phone TEXT",
           "address TEXT", "org_id INTEGER", "opening_hours TEXT"]



def main():
    path = sys.argv[1]
    vorher_arg = sys.argv[sys.argv.index("--vorher") + 1] if "--vorher" in sys.argv else None
    d = json.load(open(path, encoding="utf-8"))
    m = re.search(r"\d{4}-\d{2}-\d{2}", d.get("harvested_at") or os.path.basename(path))
    abzug = m.group(0) if m else None
    if not abzug:
        sys.exit("ABBRUCH: das Datum des Abzugs fehlt (harvested_at oder Dateiname)")
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    for col in NEWCOLS:
        try:
            c.execute(f"ALTER TABLE dvsh_service ADD COLUMN {col}")
        except Exception:
            pass

    # organisation tree first — it names departments and holds the contacts
    orgs = {int(o["id"]): o for o in (d.get("organisations") or [])}
    c.execute("DELETE FROM dvsh_organisation")
    for o in orgs.values():
        c.execute("INSERT INTO dvsh_organisation(id,parent_id,slug,name,kind,contact_name,"
                  "contact_email,contact_phone,contact_address,contact_url,opening_hours,updated_at)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  [int(o["id"]), int(o["parentId"]) if o.get("parentId") else None,
                   o.get("slug"), o.get("name"), o.get("kind"), o.get("contactName"),
                   o.get("contactEmail"), o.get("contactPhone"), o.get("contactAddress"),
                   o.get("contactUrl"), o.get("openingHours"), o.get("updatedAt")])

    def org_chain(oid):
        """Walk up the tree: returns (own name, department = topmost ancestor name)."""
        seen, cur = set(), orgs.get(oid)
        top = cur
        while cur and cur.get("parentId") and int(cur["parentId"]) in orgs and cur["id"] not in seen:
            seen.add(cur["id"])
            cur = orgs[int(cur["parentId"])]
            top = cur
        return (orgs[oid]["name"] if oid in orgs else None, top["name"] if top else None)

    def chain(oid):
        """Organisation names from the root down to oid."""
        out, seen, cur = [], set(), orgs.get(oid)
        while cur and cur["id"] not in seen:
            seen.add(cur["id"]); out.append(cur)
            cur = orgs.get(int(cur["parentId"])) if cur.get("parentId") else None
        return list(reversed(out))

    # the databank's spelling of an office, for NEW service rows: DVSH spells
    # offices and departments differently («Betreibungsamt» vs «Betreibungs- und
    # Konkursamt», root «Verwaltung» vs the Departement), and a second spelling
    # would open a second heading in the navigation
    by_org = {}
    for r in c.execute("SELECT d.org_id, s.department, s.dienststelle FROM dvsh_service d "
                       "JOIN service s ON s.id=d.service_id WHERE d.org_id IS NOT NULL"):
        by_org.setdefault(r["org_id"], Counter())[(r["department"], r["dienststelle"])] += 1
    offices = Counter((r["department"], r["dienststelle"]) for r in
                      c.execute("SELECT department, dienststelle FROM service WHERE dienststelle IS NOT NULL"))

    def office_of(oid):
        if oid in by_org:
            return by_org[oid].most_common(1)[0][0]
        ch = chain(oid)
        if not ch:
            return (None, None)
        name = ch[-1]["name"]
        key = lambda s: norm(re.sub(r"\s*\(.*?\)", "", s or ""))
        best = max(offices, key=lambda o: (difflib.SequenceMatcher(None, key(o[1]), key(name)).ratio(), offices[o]),
                   default=None)
        if best and difflib.SequenceMatcher(None, key(best[1]), key(name)).ratio() >= .88:
            return best
        dept = ch[1]["name"] if ch[0]["name"] == "Verwaltung" and len(ch) > 1 else ch[0]["name"]
        return (dept, name)

    # preserve existing matches, then match the rest by slug/normalised title
    old_match = {r["dvsh_id"]: r["service_id"] for r in
                 c.execute("SELECT dvsh_id, service_id FROM dvsh_service WHERE service_id IS NOT NULL")}
    before = quellen_log.snapshot(c, "dvsh_service", "dvsh_id", COMPARE)
    svc_by_norm = {norm(r["name"]): r["id"] for r in c.execute("SELECT id, name FROM service")}
    svc_by_slug = {r["slug"]: r["id"] for r in c.execute("SELECT id, slug FROM service") if r["slug"]}

    c.execute("DELETE FROM dvsh_service")
    n = new_svc = 0
    listing = {s["id"]: s for s in d.get("list", [])}
    for sid_str, entry in d["services"].items():
        s = entry["service"]
        p = s.get("payload") or {}
        if isinstance(p, str):
            p = json.loads(p)
        did = int(s["id"])
        li = listing.get(did, {})
        dienststelle, department = org_chain(int(s["organisationId"])) if s.get("organisationId") else (None, None)
        j = lambda v: json.dumps(v, ensure_ascii=False) if v not in (None, "", []) else None
        title = p.get("serviceName") or li.get("title")
        # resolve/create the service link — DVSH is the catalogue of record now
        svc_id = old_match.get(did) or svc_by_slug.get(s.get("slug")) \
                 or svc_by_norm.get(norm(title))
        if not svc_id:
            dep_db, off_db = office_of(int(s["organisationId"])) if s.get("organisationId") else (None, None)
            c.execute("INSERT INTO service(slug,name,dienststelle,department,in_dvsh) "
                      "VALUES(?,?,?,?,1)", [s.get("slug"), title, off_db or dienststelle, dep_db or department])
            svc_id = c.execute("SELECT last_insert_rowid() i").fetchone()["i"]
            svc_by_norm[norm(title)] = svc_id
            new_svc += 1
            # open, and said so, until the Lebenslagen panel has placed it
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='service_thema_grund'").fetchone():
                c.execute("INSERT OR IGNORE INTO service_thema_grund(service_id, grund, zweitgeprueft) VALUES(?,?,0)",
                          [svc_id, f"Neu im DVSH-Abzug vom {abzug} — Themengruppe noch nicht zugeordnet."])
        else:
            c.execute("UPDATE service SET in_dvsh=1 WHERE id=?", [svc_id])
        c.execute("""INSERT INTO dvsh_service(dvsh_id,slug,title,version,department,dienststelle,
            kurzbeschreibung,beschreibung,voraussetzungen,unterlagen,ablauf,bearbeitungsdauer,
            fristen,gebuehren,recht_kantonal,recht_bund,externe_links,abgabe,kontakt,service_id,
            match_kind,status,online,online_version,published_at,dvsh_updated_at,endpoint_typ,
            vollzugsbehoerde,submission_endpoint,documents,sources,form_definitions,completeness,
            email,phone,address,org_id,opening_hours)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [did, s.get("slug"), title, s.get("onlineVersion") or li.get("version"),
             department, dienststelle,
             p.get("kurzbeschreibung"), p.get("description"),
             j(p.get("prerequisites")), j(p.get("requiredDocuments")), j(p.get("processSteps")),
             p.get("processingTime"), p.get("deadlines"), p.get("fees"),
             j(p.get("rechtsgrundlagen")), j(p.get("bundesrecht")), j(p.get("externalLinks")),
             j([ (p.get("submissionEndpoint") or {}).get("typ"),
                 (p.get("submissionEndpoint") or {}).get("titel") ]),
             p.get("emailAddress"), svc_id,
             f"harvest-{abzug[:7]}" if did not in old_match else "kept",
             li.get("status"), 1 if li.get("online") else 0, li.get("onlineVersion"),
             li.get("publishedAt"), li.get("updatedAt"), li.get("endpointTyp"),
             p.get("vollzugsbehoerde"), j(p.get("submissionEndpoint")), j(p.get("documents")),
             j(p.get("sources")), j(p.get("formDefinitions")), j(p.get("completenessStatus")),
             p.get("emailAddress"), p.get("phoneNumber"), p.get("address"),
             int(s["organisationId"]) if s.get("organisationId") else None,
             j(p.get("openingHours"))])
        n += 1

    # enrich the dienststelle entity with the org tree's contacts (fill, never clobber)
    ne = 0
    for o in orgs.values():
        if o.get("contactEmail") or o.get("contactAddress"):
            k = f"{o.get('contactEmail') or ''} · {o.get('contactAddress') or ''}".strip(" ·")
            ne += c.execute("UPDATE dienststelle SET kontakt=? WHERE name=? AND (kontakt IS NULL OR kontakt='')",
                            [k, o.get("name")]).rowcount
    after = quellen_log.snapshot(c, "dvsh_service", "dvsh_id", COMPARE)
    logged, counts = quellen_log.record_changes(c, "DVSH", abzug, os.path.basename(path), n,
                                                before, after, COMPARE, vorher_arg)
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"dvsh_service: {n} Services (davon {new_svc} neue service-Zeilen), "
          f"{len(orgs)} Organisationen, {ne} Dienststellen-Kontakte ergänzt")
    print(f"Abzug {abzug}: " + (", ".join(f"{v} {k}" for k, v in counts.items()) if logged
                                else "schon protokolliert, Änderungen nicht neu verglichen"))


if __name__ == "__main__":
    main()
