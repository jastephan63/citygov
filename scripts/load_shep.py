#!/usr/bin/env python3
"""Parse the harvested SHEP portal pages (the PUBLISHED citizen view of the
DVSH services) and load them into shep_service.

SHEP (shep.meetfrida.agency) renders what the modeller published — the same
service, but as the citizen sees it: teaser, Voraussetzungen, Unterlagen,
Ablauf, Formular-Link, Dokumente, rechtliche Grundlagen, Kontakt. We harvest
the server-rendered HTML read-only via plain GETs and parse by the template's
h2 sections. Matching to our service rows goes through dvsh_service.slug —
SHEP uses the modeller's slugs.

Idempotent (table rebuilt wholesale). Staging -> validate -> swap.

    python3 scripts/load_shep.py <pages-dir>
"""
import glob, html, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

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
    dokumente TEXT,            -- JSON array of {label, url}
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
    # links: the Formular button plus the Dokumente/Links lists
    m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*Formular', page)
    d["formular_url"] = html.unescape(m.group(1)) if m else None
    info = section(page, "Weiterführende Informationen", ALL)
    d["links"] = [{"label": html.unescape(TAG.sub("", t)).replace("(öffnet in neuem Tab)", "").strip(),
                   "url": html.unescape(u)}
                  for u, t in re.findall(r'<a[^>]+href="(http[^"]+)"[^>]*>(.*?)</a>', info, re.S)]
    kont = section(page, "Kontakt", ALL)
    lines = text_of(kont)
    d["kontakt_email"] = next((l for l in lines if "@" in l and " " not in l), None)
    try:
        i = lines.index("Organisationseinheit")
        d["kontakt_einheit"] = "; ".join(lines[i + 1:i + 3])
        d["kontakt_adresse"] = "; ".join(lines[i + 3:i + 5])
    except ValueError:
        d["kontakt_einheit"] = d["kontakt_adresse"] = None
    # the teaser repeats right after the h1 block; take the first paragraph-ish line
    body = text_of(page[:page.find("Kurzbeschreibung")] if "Kurzbeschreibung" in page else page[:4000])
    d["teaser"] = next((l for l in body if len(l) > 80), None)
    return d


def main():
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    dvsh = {r["slug"]: r for r in c.execute("SELECT slug, dvsh_id, service_id FROM dvsh_service")}
    c.execute("DELETE FROM shep_service")
    n = matched = 0
    from datetime import date
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
             d["formular_url"], None, j(d["links"]),
             d["kontakt_einheit"], d["kontakt_adresse"], d["kontakt_email"],
             date.today().isoformat()])
        n += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"shep_service: {n} publizierte Services geparst, {matched} via DVSH-Slug gematcht")


if __name__ == "__main__":
    main()
