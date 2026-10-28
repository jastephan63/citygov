#!/usr/bin/env python3
"""Parse the harvested SHEP portal pages (the PUBLISHED citizen view of the
DVSH services) and load them into shep_service.

SHEP (shep.meetfrida.agency) renders what the modeller published — the same
service, but as the citizen sees it: teaser, Voraussetzungen, Unterlagen,
Ablauf, Formular-Link, Dokumente, rechtliche Grundlagen, Kontakt. We harvest
the server-rendered HTML read-only via plain GETs and parse by the template's
h2 sections. Matching to our service rows goes through dvsh_service.slug —
SHEP uses the modeller's slugs.

Idempotent (table rebuilt wholesale). Before the rebuild, quellen_log records what
this harvest changed against the pages the databank held (quellen_aenderung); the
harvest date is the date in the pages directory's path (else today), --vorher
<YYYY-MM-DD> names the earlier harvest when the log has no row for it yet.
Staging -> validate -> swap.

    python3 scripts/load_shep.py <pages-dir> [--vorher 2026-09-03]
"""
import glob, html, json, os, re, shutil, sys
from citygov.core.common import DB_PATH, connect
from citygov.checks.validate_db import validate
from citygov.load import quellen_log

# the columns whose change the harvest log records — the sections the template
# marks unambiguously (teaser and link labels were re-parsed in 2026-10 and are
# not compared)
COMPARE = ["title", "kurzbeschreibung", "voraussetzungen", "unterlagen", "ablauf",
           "formular_url", "kontakt_einheit", "kontakt_adresse", "kontakt_email"]

DDL = """
CREATE TABLE IF NOT EXISTS shep_service (
    slug TEXT PRIMARY KEY,
    service_id INTEGER REFERENCES service(id),
    dvsh_id INTEGER,
    title TEXT, teaser TEXT, updated TEXT,
    kurzbeschreibung TEXT,
    voraussetzungen TEXT,      -- JSON array
    unterlagen TEXT,           -- JSON array of {name, detail}
    ablauf TEXT,               -- JSON array of {nr, titel, text}
    formular_url TEXT,
    dokumente TEXT,            -- JSON array of {label, url, sha256} (SHEP asset store)
    links TEXT,                -- JSON array of {label, url}
    kontakt_einheit TEXT, kontakt_adresse TEXT, kontakt_email TEXT,
    harvested_at TEXT
);
"""

TAG = re.compile(r"<[^>]+>")
H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)


def text_of(fragment):
    t = TAG.sub("\n", fragment)
    t = html.unescape(t)
    return [ln.strip() for ln in t.splitlines() if ln.strip()]


def link_label(fragment):
    """Visible name of a link — without the template's «Externer Link · host» and
    «(öffnet in neuem Tab)» additions."""
    keep = [l for l in text_of(fragment)
            if not l.startswith("Externer Link") and l not in ("(", ")", "öffnet in neuem Tab")]
    return " ".join(keep).replace("(öffnet in neuem Tab)", "").strip()


def section(page, heading, until):
    """Raw HTML between the FIRST h2 with this heading and the next h2 in `until`."""
    parts = re.split(r"(<h2[^>]*>.*?</h2>)", page, flags=re.S)
    buf, active = [], False
    for p in parts:
        m = H2.fullmatch(p.strip()) if p.strip().startswith("<h2") else None
        head = html.unescape(TAG.sub("", m.group(1))).strip() if m else None
        if m:
            if active and (head in until or head == heading):
                break
            active = head == heading
            continue
        if active:
            buf.append(p)
    return "".join(buf)


def parse(page):
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", page, flags=re.S)
    d = {}
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    d["title"] = html.unescape(TAG.sub("", m.group(1))).strip() if m else None
    m = re.search(r"Aktualisiert:\s*([0-9]{1,2}\.\s*\w+\s*[0-9]{4})", TAG.sub(" ", page))
    d["updated"] = m.group(1).strip() if m else None
    ALL = {"Kurzbeschreibung", "Voraussetzungen", "Erforderliche Unterlagen", "Der Ablauf",
           "Weiterführende Informationen", "Kontakt", "Verwandte Services", "Beliebte Services",
           d["title"] or ""}
    d["kurzbeschreibung"] = "\n\n".join(text_of(section(page, "Kurzbeschreibung", ALL)))
    d["voraussetzungen"] = text_of(section(page, "Voraussetzungen", ALL))
    # Unterlagen: the template marks the name and the muted detail with
    # distinct classes inside each <li> — parse by markup, not heuristics
    ul = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", section(page, "Erforderliche Unterlagen", ALL), re.S):
        name = re.search(r'<span class="text-brand-black-200[^"]*">(.*?)</span>', li, re.S)
        det = re.search(r'<span class="text-brand-grey-20[^"]*">(.*?)</span>', li, re.S)
        if name:
            ul.append({"name": html.unescape(TAG.sub("", name.group(1))).strip(),
                       "detail": html.unescape(TAG.sub("", det.group(1))).strip() if det else None})
    d["unterlagen"] = ul
    steps, cur = [], None
    for ln in text_of(section(page, "Der Ablauf", ALL)):
        if re.fullmatch(r"\d{1,2}", ln):
            cur = {"nr": int(ln), "titel": None, "text": None}
            steps.append(cur)
        elif cur is not None:
            if cur["titel"] is None:
                cur["titel"] = ln
            else:
                cur["text"] = (cur["text"] + " " + ln) if cur["text"] else ln
    d["ablauf"] = steps
    # links: the Formular button plus the Dokumente/Links lists. Match from href="…"
    # on: since 2026-10 the template's class lists contain «>» ([&>svg]:…), which
    # breaks an <a[^>]+ prefix
    m = re.search(r'href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*Formular\b', page)
    d["formular_url"] = html.unescape(m.group(1)) if m else None
    info = section(page, "Weiterführende Informationen", ALL)
    d["links"] = [{"label": link_label(t), "url": html.unescape(u)}
                  for u, t in re.findall(r'href="(http[^"]+)"[^>]*>(.*?)</a>', info, re.S)]
    # every file the page offers (the SHEP asset store names a file by its sha256,
    # so it is compared with form.file_hash); the related/popular-service lists at
    # the foot belong to other services and are cut off
    foot = min([i for i in (page.find(">Verwandte Services<"), page.find(">Beliebte Services<")) if i > 0]
               or [len(page)])
    d["dokumente"], seen = [], set()
    for u, sha, t in re.findall(r'href="(/api/catalog/assets/([0-9a-f]{64})\.[a-z0-9]+)"[^>]*>(.*?)</a>',
                                page[:foot], re.S):
        if u not in seen:
            seen.add(u)
            d["dokumente"].append({"label": link_label(t), "url": u, "sha256": sha})
    kont = section(page, "Kontakt", ALL)
    lines = text_of(kont)
    d["kontakt_email"] = next((l for l in lines if "@" in l and " " not in l), None)
    d["kontakt_einheit"] = d["kontakt_adresse"] = None
    adr = re.search(r"<address[^>]*>(.*?)</address>", kont, re.S)
    if adr:
        # since 2026-10: <address> with one span per line — units, street, «PLZ Ort»
        al = text_of(adr.group(1))
        plz = next((i for i, l in enumerate(al) if re.match(r"\d{4}\s", l)), None)
        if plz is not None and plz >= 1:
            d["kontakt_einheit"] = "; ".join(al[:plz - 1]) or None
            d["kontakt_adresse"] = "; ".join(al[plz - 1:plz + 1])
    elif "Organisationseinheit" in lines:
        i = lines.index("Organisationseinheit")
        d["kontakt_einheit"] = "; ".join(lines[i + 1:i + 3])
        d["kontakt_adresse"] = "; ".join(lines[i + 3:i + 5])
    # the teaser is the paragraph right under the h1 (before «Aktualisiert:»); the
    # <head> is cut first — since 2026-10 its <title> carries «… | Kanton Schaffhausen»
    body = re.sub(r"<head[^>]*>.*?</head>", "", page, flags=re.S)
    h1 = re.search(r"</h1>", body)
    after = text_of(body[h1.end():h1.end() + 4000]) if h1 else []
    d["teaser"] = next((l for l in after if not l.startswith("Aktualisiert")
                        and l != "Kurzbeschreibung" and len(l) > 20), None)
    return d


def main():
    src = sys.argv[1]
    vorher_arg = sys.argv[sys.argv.index("--vorher") + 1] if "--vorher" in sys.argv else None
    from datetime import date
    m = re.search(r"\d{4}-\d{2}-\d{2}", os.path.abspath(src))
    abzug = m.group(0) if m else date.today().isoformat()
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    dvsh = {r["slug"]: r for r in c.execute("SELECT slug, dvsh_id, service_id FROM dvsh_service")}
    before = quellen_log.snapshot(c, "shep_service", "slug", COMPARE)
    c.execute("DELETE FROM shep_service")
    n = matched = 0
    for f in sorted(glob.glob(os.path.join(src, "*.html"))):
        slug = os.path.basename(f)[:-5]
        page = open(f, encoding="utf-8").read()
        d = parse(page)
        dv = dvsh.get(slug)
        if dv:
            matched += 1
        j = lambda v: json.dumps(v, ensure_ascii=False) if v else None
        c.execute("""INSERT OR REPLACE INTO shep_service(slug,service_id,dvsh_id,title,teaser,
            updated,kurzbeschreibung,voraussetzungen,unterlagen,ablauf,formular_url,dokumente,
            links,kontakt_einheit,kontakt_adresse,kontakt_email,harvested_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [slug, dv["service_id"] if dv else None, dv["dvsh_id"] if dv else None,
             d["title"], d["teaser"], d["updated"], d["kurzbeschreibung"] or None,
             j(d["voraussetzungen"]), j(d["unterlagen"]), j(d["ablauf"]),
             d["formular_url"], j(d["dokumente"]), j(d["links"]),
             d["kontakt_einheit"], d["kontakt_adresse"], d["kontakt_email"],
             abzug])
        n += 1
    after = quellen_log.snapshot(c, "shep_service", "slug", COMPARE)
    logged, counts = quellen_log.record_changes(c, "SHEP", abzug, "/".join(os.path.normpath(src).split(os.sep)[-2:]),
                                                n, before, after, COMPARE, vorher_arg)
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"shep_service: {n} publizierte Services geparst, {matched} via DVSH-Slug gematcht")
    print(f"Abzug {abzug}: " + (", ".join(f"{v} {k}" for k, v in counts.items()) if logged
                                else "schon protokolliert, Änderungen nicht neu verglichen"))


if __name__ == "__main__":
    main()
