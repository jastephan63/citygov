#!/usr/bin/env python3
"""Load the online targets behind the button «Online erledigen» of the live portal
services.sh.ch: what each button leads to, every eForm (eforms.sh.ch, aforms2web AFS)
reached from it, and which Formular of the databank is the same form.

The harvest is read-only and sends nothing (owner: «it is important we do not actually
submit any of these forms online»): each eForm's start page is opened like a browser
(with its JavaScript-detection redirect), and only where that first page asks for
nothing, «Weiter» is pressed once with no input. Nothing is typed, ticked, uploaded or
sent; the session expires unused. The harvest directory holds

    ziele.json                    the 87 buttons (slug, service_id, url)
    afs_ziele.json                every eForm reached (directly or via migrationsamt.sh.ch)
    eforms/<mandant>__<kennung>/schritt<n>.html   the pages reached without input
    migrationsamt_links.json      what the intermediate migrationsamt.sh.ch pages link
    dateien/manifest.json         the documents those pages link, each fetched once (sha256)
    suche/manifest.json           documents found by a web search for the paper version
    andere/codes.txt              the fetch result of every other target

The facts (name, steps, visible fields) are read from the saved pages here; the
judgements (what a target is, which Formular or document is the same form) come from
the reviewed evidence quellen/dokumente/online_<date>.json (panel + sceptical second
review). A document named as the paper version that a Formular now holds (after
load_uebernahme.py) is linked to that Formular. Gates: vocabularies; every eForm and
every button of the evidence exists in the harvest; a named form_id exists; a named
document is one of the harvest's documents. Idempotent (tables rebuilt). Staging ->
validate -> swap.

    python3 scripts/load_online.py ../SHEP/live-2026-11-03/online quellen/dokumente/online_2026-11-03.json
"""
import glob, html, json, os, re, shutil, sys
from citygov.core.common import DB_PATH, connect
from citygov.checks.validate_db import validate

ZIEL_ART = ("eformular", "eformular_beilagen", "fremdformular", "anmeldung", "rechner", "termin", "portal",
            "info", "defekt", "anderes")
ZUGANG = ("alle_seiten_sichtbar", "teilweise_sichtbar", "nur_beilagen", "nur_einstieg")
GEGEN = ("databank_formular", "databank_dvsh_eformular", "pdf_kandidat", "keins")

DDL = """
CREATE TABLE IF NOT EXISTS online_ziel (
    slug       TEXT PRIMARY KEY,
    service_id INTEGER REFERENCES service(id),
    url        TEXT,
    art        TEXT NOT NULL CHECK (art IN ('eformular','eformular_beilagen','fremdformular','anmeldung','rechner',
                                            'termin','portal','info','defekt','anderes')),
    befund     TEXT,
    abruf      TEXT,
    abzug      TEXT);
CREATE TABLE IF NOT EXISTS online_formular (
    id                  TEXT PRIMARY KEY,
    system              TEXT,
    start_url           TEXT,
    name                TEXT,
    name_intern         TEXT,
    zugang              TEXT NOT NULL CHECK (zugang IN ('alle_seiten_sichtbar','teilweise_sichtbar','nur_beilagen',
                                                        'nur_einstieg')),
    schritte            TEXT,
    felder_sichtbar     TEXT,
    n_felder_sichtbar   INTEGER,
    gegenstueck_art     TEXT NOT NULL CHECK (gegenstueck_art IN ('databank_formular','databank_dvsh_eformular',
                                                                 'pdf_kandidat','keins')),
    gegenstueck_form_id INTEGER REFERENCES form(id),
    gegenstueck_sha256  TEXT,
    beleg               TEXT,
    pruefung            TEXT,
    abzug               TEXT);
CREATE TABLE IF NOT EXISTS online_formular_seite (
    formular_id TEXT NOT NULL REFERENCES online_formular(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
    service_id  INTEGER REFERENCES service(id),
    via         TEXT,
    PRIMARY KEY (formular_id, slug));
CREATE TABLE IF NOT EXISTS online_datei (
    url        TEXT PRIMARY KEY,
    sha256     TEXT NOT NULL,
    bytes      INTEGER,
    dateiname  TEXT,
    herkunft   TEXT NOT NULL CHECK (herkunft IN ('verlinkt','websuche')),
    slug       TEXT,
    service_id INTEGER REFERENCES service(id),
    label      TEXT,
    abzug      TEXT);
"""
TAG = re.compile(r"<[^>]+>")


def seite(p):
    """name, internal form name, progress steps and visible controls of one saved AFS page"""
    t = re.search(r"<title>(.*?)</title>", p, re.S)
    titel = re.sub(r"\s+", " ", html.unescape(t.group(1))).strip() if t else None
    fn = re.search(r'<form\b[^>]*name="([^"]+)"', p)
    st = re.search(r"Fortschrittanzeige(.*?)(?:</ol>|</ul>|</nav>)", p, re.S)
    schritte = []
    for s in re.findall(r"<li[^>]*>(.*?)</li>", st.group(1), re.S) if st else []:
        s = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", s))).strip()
        if s and s not in schritte:
            schritte.append(s)
    labs = {i: re.sub(r"\s+", " ", html.unescape(TAG.sub("", t))).strip()
            for i, t in re.findall(r'<label[^>]*for="([^"]+)"[^>]*>(.*?)</label>', p, re.S)}
    felder = []
    for m in re.finditer(r"<(input|select|textarea)\b([^>]*)>", p):
        a = m.group(2)
        typ = (re.search(r'type="([^"]+)"', a) or [None, "text"])[1] if m.group(1) == "input" else m.group(1)
        nm = (re.search(r'name="([^"]+)"', a) or [None, ""])[1]
        if typ in ("hidden", "submit", "button", "image") or nm in ("xml", "defaultAction"):
            continue
        i = (re.search(r'\bid="([^"]+)"', a) or [None, ""])[1]
        felder.append({"label": labs.get(i), "typ": typ})
    return titel, (fn.group(1) if fn else None), schritte, felder


def main():
    src, ev_path = sys.argv[1], sys.argv[2]
    m = re.search(r"\d{4}-\d{2}-\d{2}", os.path.abspath(src))
    abzug = m.group(0) if m else None
    Z = {z["slug"]: z for z in json.load(open(os.path.join(src, "ziele.json"), encoding="utf-8"))}
    AFS = {a["id"]: a for a in json.load(open(os.path.join(src, "afs_ziele.json"), encoding="utf-8"))}
    codes = {}
    cf = os.path.join(src, "andere", "codes.txt")
    for ln in open(cf, encoding="utf-8") if os.path.exists(cf) else []:
        k, _, rest = ln.strip().partition(" ")
        codes[k] = rest
    docs = {}
    for name, herkunft in (("dateien", "verlinkt"), ("suche", "websuche")):
        mf = os.path.join(src, name, "manifest.json")
        for u, d in (json.load(open(mf, encoding="utf-8"))["dateien"].items() if os.path.exists(mf) else []):
            docs[u] = {**d, "herkunft": herkunft}
    ev = json.load(open(ev_path, encoding="utf-8"))
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    for t in ("online_formular_seite", "online_formular", "online_ziel", "online_datei"):
        c.execute(f"DELETE FROM {t}")
    forms = {r[0] for r in c.execute("SELECT id FROM form")}
    held = {r[0]: r[1] for r in c.execute("SELECT file_hash, id FROM form WHERE file_hash IS NOT NULL")}
    shas = {d["sha256"] for d in docs.values()}
    fehler = []

    def stop(msg):
        fehler.append(msg)

    # the documents: linked by an intermediate page, or found by the web search
    for u, d in docs.items():
        q = (d.get("quellen") or [{}])[0]
        c.execute("INSERT INTO online_datei VALUES(?,?,?,?,?,?,?,?,?)",
                  [u, d["sha256"], d.get("bytes"), d.get("dateiname"), d["herkunft"], q.get("slug"),
                   Z[q["slug"]]["service_id"] if q.get("slug") in Z else None, q.get("label"), d.get("abgerufen") or abzug])
    seen_f = set()
    for it in ev["ziele"]:
        z = Z.get(it["slug"])
        if not z:
            stop(f"{it['slug']}: kein Button des Abzugs"); continue
        if it["ziel_art"] not in ZIEL_ART:
            stop(f"{it['slug']}: ziel_art {it['ziel_art']}"); continue
        c.execute("INSERT INTO online_ziel VALUES(?,?,?,?,?,?,?)",
                  [it["slug"], z["service_id"], z["url"], it["ziel_art"], it.get("ziel_befund"),
                   codes.get(it["slug"]), abzug])
        for e in it.get("eformulare", []):
            g = e["gegenstueck"]
            if e["zugang"] not in ZUGANG or g["art"] not in GEGEN:
                stop(f"{e['id']}: zugang/gegenstueck"); continue
            if g.get("form_id") is not None and g["form_id"] not in forms:
                stop(f"{e['id']}: form_id {g['form_id']} unbekannt"); continue
            if g["art"] == "pdf_kandidat" and g.get("pdf_sha256") not in shas and g.get("pdf_sha256") not in held:
                stop(f"{e['id']}: Dokument {str(g.get('pdf_sha256'))[:12]} nicht im Abzug"); continue
            if e["id"] in AFS:
                a = AFS[e["id"]]
                pages = sorted(glob.glob(os.path.join(src, "eforms", e["id"].replace("/", "__"), "schritt*.html")))
                if not pages:
                    stop(f"{e['id']}: keine gespeicherte Seite"); continue
                name_i, schritte, felder = None, [], []
                for pth in pages:
                    t, fn, sch, fl = seite(open(pth, encoding="utf-8").read())
                    name_i = name_i or fn
                    schritte = sch or schritte
                    felder += [f for f in fl if f not in felder]
                system, start = "eforms.sh.ch", a["start"]
                via = {f["slug"]: f["via"] for f in a["fundstellen"]}
            elif e["id"] == it["slug"]:                 # a form on another provider (jotform …)
                system, start, name_i, schritte, felder = re.sub(r"^https?://([^/]+).*", r"\1", z["url"]), z["url"], None, \
                    e.get("schritte") or [], []
                via = {it["slug"]: "Schaltfläche"}
            else:
                stop(f"{e['id']}: weder eForm des Abzugs noch der Button selbst"); continue
            # a named document a Formular now holds (taken over) is that Formular
            art, fid, sha = g["art"], g.get("form_id"), g.get("pdf_sha256")
            if art == "pdf_kandidat" and sha in held:
                art, fid = "databank_formular", held[sha]
            if e["id"] not in seen_f:
                seen_f.add(e["id"])
                c.execute("INSERT INTO online_formular VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          [e["id"], system, start, e["name"], name_i, e["zugang"],
                           json.dumps(schritte, ensure_ascii=False), json.dumps(felder, ensure_ascii=False),
                           e.get("n_felder_sichtbar") if e["id"] not in AFS else len(felder),
                           art, fid, sha, g.get("beleg"), it.get("pruefung"), abzug])
            for slug, v in via.items():
                if slug in Z:
                    c.execute("INSERT OR IGNORE INTO online_formular_seite VALUES(?,?,?,?)",
                              [e["id"], slug, Z[slug]["service_id"], v])
    missing = set(Z) - {it["slug"] for it in ev["ziele"]}
    if missing:
        stop(f"{len(missing)} Buttons ohne Urteil: {sorted(missing)[:3]}")
    if fehler:
        c.close(); os.remove(st)
        sys.exit("ABBRUCH:\n  " + "\n  ".join(fehler[:20]))
    c.commit()
    errs = validate(c)
    n = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
         for t in ("online_ziel", "online_formular", "online_formular_seite", "online_datei")}
    g = dict(c.execute("SELECT gegenstueck_art, COUNT(*) FROM online_formular GROUP BY 1").fetchall())
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:5], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"online: {n['online_ziel']} Buttons, {n['online_formular']} Online-Formulare ({n['online_formular_seite']} Seiten), "
          f"{n['online_datei']} Dokumente — Gegenstück {g}")


if __name__ == "__main__":
    main()
