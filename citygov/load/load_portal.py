#!/usr/bin/env python3
"""Load the live service portal of the canton, services.sh.ch, into portal_service.

services.sh.ch is the PRODUCTION portal of the services SHEP (shep.meetfrida.agency)
prepares: the same template, so the pages are parsed with load_shep.parse(). The
harvest is read-only — one plain GET per public page (the slug list from the
overview /de/services), no login, no click, no form — and lands in a directory
named after its date:

    <dir>/pages/<slug>.html     the service pages
    <dir>/links/manifest.json   the files on sh.ch the pages link to (sh.ch/CMS/get/file/<id>),
                                each fetched once: {url: {datei, status, bytes, sha256, dateiname}}

What a page offers is kept as the citizen sees it: the action buttons verbatim
(«Formular», «Online erledigen», «Per E-Mail erledigen», «Zum Angebot» …), the files
of the portal's asset store (named by their sha256) and the linked sh.ch files with
the sha256 of their fetched bytes — so citygov/domain/quelldokumente.py can say per
Formular whether the live portal offers it.

Matching to our services goes through dvsh_service.slug, as for SHEP. A slug the DVSH
harvest does not know is matched to the SHEP page it replaced only when that page's
slug is gone from the live portal and title AND teaser are the same (the portal
renamed the page); zuordnung records how. Idempotent (table rebuilt wholesale);
quellen_log records what the harvest changed against the previous live harvest
(quelle 'Portal'). Staging -> validate -> swap.

    python3 scripts/load_portal.py <harvest-dir>
"""
import glob, json, os, re, shutil, sys
from citygov.core.common import DB_PATH, connect
from citygov.checks.validate_db import validate
from citygov.load import quellen_log
from citygov.load.load_shep import parse, COMPARE

DDL = """
CREATE TABLE IF NOT EXISTS portal_service (
    slug TEXT PRIMARY KEY,
    service_id INTEGER REFERENCES service(id),
    dvsh_id INTEGER,
    zuordnung TEXT,
    title TEXT, teaser TEXT, updated TEXT,
    kurzbeschreibung TEXT,
    voraussetzungen TEXT,      -- JSON array
    unterlagen TEXT,           -- JSON array of {name, detail}
    ablauf TEXT,               -- JSON array of {nr, titel, text}
    formular_url TEXT,
    aktionen TEXT,             -- JSON array of {art, url}: the action buttons, verbatim
    dokumente TEXT,            -- JSON array of {label, url, sha256} (asset store of the portal)
    datei_links TEXT,          -- JSON array of {label, url, sha256} (linked sh.ch files, fetched bytes)
    links TEXT,                -- JSON array of {label, url}
    kontakt_einheit TEXT, kontakt_adresse TEXT, kontakt_email TEXT,
    harvested_at TEXT
);
"""


def main():
    src = sys.argv[1]
    pages = os.path.join(src, "pages")
    if not os.path.isdir(pages):
        sys.exit(f"ABBRUCH: {pages} fehlt")
    m = re.search(r"\d{4}-\d{2}-\d{2}", os.path.abspath(src))
    if not m:
        sys.exit("ABBRUCH: das Verzeichnis des Abzugs trägt kein Datum (YYYY-MM-DD)")
    abzug = m.group(0)
    mf = os.path.join(src, "links", "manifest.json")
    geladen = json.load(open(mf, encoding="utf-8"))["dateien"] if os.path.exists(mf) else {}
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    dvsh = {r["slug"]: r for r in c.execute("SELECT slug, dvsh_id, service_id FROM dvsh_service")}
    parsed = {os.path.basename(f)[:-5]: parse(open(f, encoding="utf-8").read())
              for f in sorted(glob.glob(os.path.join(pages, "*.html")))}
    if not parsed:
        sys.exit(f"ABBRUCH: keine Seiten in {pages}")
    # a page the portal renamed: the SHEP page whose slug is gone, with the same title and teaser
    shep_weg = {}
    for r in c.execute("SELECT slug, service_id, dvsh_id, title, teaser FROM shep_service"):
        if r["slug"] not in parsed:
            shep_weg.setdefault((r["title"], r["teaser"]), []).append(r)
    before = quellen_log.snapshot(c, "portal_service", "slug", COMPARE)
    c.execute("DELETE FROM portal_service")
    n = matched = renamed = 0
    fehlt = []
    for slug, d in parsed.items():
        dv, zu = dvsh.get(slug), "slug"
        if not dv:
            cand = shep_weg.get((d["title"], d["teaser"]), [])
            if len(cand) == 1 and cand[0]["service_id"] is not None:
                dv, zu = cand[0], f"umbenannt, vorher {cand[0]['slug']}"
                renamed += 1
            else:
                zu = None
        matched += 1 if dv else 0
        links = []
        for x in d["datei_links"]:
            g = geladen.get(x["url"]) or {}
            ok = g.get("status") == 200 and g.get("sha256")
            if not ok:
                fehlt.append(x["url"])
            links.append({**x, "sha256": g["sha256"] if ok else None, "dateiname": g.get("dateiname") if ok else None})
        j = lambda v: json.dumps(v, ensure_ascii=False) if v else None
        c.execute("""INSERT INTO portal_service(slug,service_id,dvsh_id,zuordnung,title,teaser,updated,
            kurzbeschreibung,voraussetzungen,unterlagen,ablauf,formular_url,aktionen,dokumente,datei_links,
            links,kontakt_einheit,kontakt_adresse,kontakt_email,harvested_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [slug, dv["service_id"] if dv else None, dv["dvsh_id"] if dv else None, zu,
             d["title"], d["teaser"], d["updated"], d["kurzbeschreibung"] or None,
             j(d["voraussetzungen"]), j(d["unterlagen"]), j(d["ablauf"]), d["formular_url"],
             j(d["aktionen"]), j(d["dokumente"]), j(links), j(d["links"]),
             d["kontakt_einheit"], d["kontakt_adresse"], d["kontakt_email"], abzug])
        n += 1
    after = quellen_log.snapshot(c, "portal_service", "slug", COMPARE)
    logged, counts = quellen_log.record_changes(c, "Portal", abzug, "/".join(os.path.normpath(src).split(os.sep)[-2:]),
                                                n, before, after, COMPARE)
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"portal_service: {n} Live-Seiten geparst, {matched} zugeordnet ({renamed} umbenannte Seite"
          f"{'' if renamed == 1 else 'n'} über die SHEP-Seite), {n - matched} ohne Service")
    if fehlt:
        print(f"  {len(fehlt)} verlinkte Datei(en) nicht im Manifest — ohne Fingerabdruck geladen:", *fehlt[:5], sep="\n    ")
    print(f"Abzug {abzug}: " + (", ".join(f"{v} {k}" for k, v in counts.items()) if logged and before
                                else "erster Abzug des Live-Portals, nichts zu vergleichen" if logged
                                else "schon protokolliert, Änderungen nicht neu verglichen"))


if __name__ == "__main__":
    main()
