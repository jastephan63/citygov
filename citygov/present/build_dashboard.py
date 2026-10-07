#!/usr/bin/env python3
"""Build dashboard.html from data_export.json (convention 9: generated, never edited).

The JSON is inlined into the HTML so the file opens straight from disk via file://
with no server and no fetch (offline by default). Vanilla JS, no framework.
The page's HTML, stylesheet and scripts are real files in citygov/present/assets/dashboard/
(page.html, the template; dashboard.css, dashboard.js and boot.js, the start-up guard),
inlined into the one page at build time; the functions named below live in dashboard.js.

Views (2026-09 redesign; state lives in the URL hash, so links are shareable),
in the six groups of the sidebar:
  * Einstieg — Übersicht (#home: the data standard first, three headline cards
    from DATA.kopfzahlen, further gaps, three doors, the tone key, a compact
    Verlauf) · Für Dienststellen (#dienststellen, + /all/<slug> per office) ·
    Für den Kanton (#kanton) · Methode & Quellen (#methode: method, tones and
    tiers, all key figures, the Verlauf table)
  * Datenstandard — Datenkatalog (#katalog) · Begriffe (#begriffe) ·
    eSH-Katalog (#esh, marked «Entwurf»)
  * Datenmodell & Once-Only — Datenmodell (#datenmodell, + /all/parteien · konzepte ·
    kennungen · gesetzesstand · wirkung, a concept /all/k-<code>, the change-impact explorer at
    a law /all/g-<law id> or an article /all/a-<article id>: whose Angabe each data point is and
    how that was made and checked, one element per Angabe and role, the permanent identifiers
    and the export contract, the edition of every cited law, what a change of a law or article
    affects) · Was Register schon wissen (#onceonly, + /all/register · g-<group> · r-<register>
    · beilagen · zeit · offen: the registers and what they hold according to a cited source, the
    Beilagen they issue, the model estimate of the time saved, the canton's open decisions).
    Read from DATA.parteien, konzepte, wirkung, register, vorbefuellung, kennungen and
    datenmodell (export_json.py) and the export contract (exportvertrag.json, read when the page
    is built); every law and article elsewhere carries its edition chip and a link «betrifft N
    Datenpunkte in M Formularen ›» to the explorer
  * Erscheinungsbild — Gestaltung der Formulare (#gestaltung, + /all/<gruppe> and
    /all/m-<merkmal>, /all/e-<merkmal>, /all/kanton, /all/dienststellen, /all/grenzen as
    shareable section addresses: how the Formulare look — Schrift, Farben, Mindestmerkmale
    der Barrierefreiheit, Kontaktangaben, Aufbau — against the practice of the measured
    Formulare; DATA.gestaltung and form.gestaltung from scripts/gestaltung_export.py; the
    texts describe what differs and never ask an office to change its Formular)
  * Arbeitslisten — Handlungsbedarf (#todo: red and amber only, per
    Dienststelle, CSV) · Recherche der Databank (#recherche: the databank's own
    homework) · Datenschutz-Dossiers (link to dossiers/index.html)
  * Nachschlagewerke — Lebenslagen (#lebenslagen, eCH-0049 Themengruppen) ·
    Verzeichnis (#register) · Datenhandhabung (#rules) · Leitfaden (#guide) ·
    Datenfluss (#datenfluss)
  * Werkstatt · Prototypen — Bürgersicht (#buerger, synthetic Datentresor) ·
    Geführte Formulare (link to flows.html)
plus the Service-Seite (#fields/<service id>: the per-Service hub with
Datenfelder & Handhabung, Gesetze, Beilagen, Digitalisierungs-Hürden,
Duplikat-Radar, the folded panels «Parteien», «Was Register schon wissen» and «Gestaltung» and
a Formular-Ansicht per Formular with its permanent identifier (#fields/<id>/form-<id>~part,
~reg, ~gest open it at that panel)), the sidebar list of
Formulare & Services, and the header search (#search/all/<query>).
The page draws, it does not compute: every figure and every classification comes from
data_export.json (kopfzahlen, dienststellen_uebersicht, the stamped ech_state /
basis_state of each Datenfeld, form.dienststelle, service.dossier_slug); the build stops
when the export lacks one of them (REQUIRED). One helper each for what recurs: a contact
(kontaktHtml — «Kontakt (laut DVSH): Adresse · Tel. … · E-Mail …»), a term of the glossary
(GLOSSAR / term — explained where a headline card uses it, listed on #methode, found by
the search), a share (pctTxt, one decimal everywhere). One rule says where a page opens
(placeAfterRender: a new page at its top, Back/Forward at the place the reader left, a
redraw of the same page where it is); the sidebar stays in view. A view that fails says
so under its own address (viewFailed). The places a new page must be registered are
listed in a comment above drawView() (dashboard.js).
One status language on every page: a status is drawn in its tone (st-ok / st-act /
st-dec / st-open from DATA.labels.ton_map — the colour says who acts next; a code
without a tone is grey, never green); Kennzeichen (level of law, ⛨, DVSH/SHEP,
↺ Once-Only, channel) stay neutral. The legend is drawn from what the page shows:
the four tones, then only the Kennzeichen the page draws, the data standard first.
Every titled non-link element opens its explanation by click, tap, Enter or Space
(#tipbox, announced via #tiplive) — inside a clickable row too, where the row keeps
its action through its link; a chip with an action of its own (⛨, a rule chip)
offers it in the box. Rows, toggles and links without an address are reachable by
keyboard. Open points are gaps, never «risk»; «Over-collection» is said in plain German
(«ohne Grundlage») and explained once on Methode (gap_wording for texts from elsewhere).
Refuses to build when the Leitfaden cites a rule the databank does not hold.
The page states its own size (and its transfer size over the network) in the
start and failure messages; both are measured on the page being written.

    python3 scripts/build_dashboard.py
"""
import json
import os
import sys

from citygov.core.common import DB_PATH, EXPORT_PATH, DASHBOARD_PATH, ROOT, connect, size_txt, net_size_txt
from citygov.present.leitfaden import LEITFADEN
from citygov.present import template
from citygov.core import theme as THEME

# the page itself is a set of real files under citygov/present/assets/dashboard/: page.html,
# which inlines boot.js (the start-up guard), dashboard.css and dashboard.js; the markers in
# them (%%FAVICON%%, /*THEME*/, /*DATA*/, %%SIZE%% …) are filled below and in main(). The
# banner the page opens with is written here, not in page.html, which is edited by hand
TEMPLATE = ("<!-- GENERATED by scripts/build_dashboard.py from citygov.db via data_export.json — "
            "do not edit; run ./build.sh -->\n" + template("dashboard", "page.html"))


# the look comes from scripts/theme.py (one definition for all generated pages)
TEMPLATE = (TEMPLATE.replace("/*THEME*/", THEME.css_root())
            .replace("/*THEME_SWATCH*/", THEME.css_swatch(".sw"))
            .replace("%%FAVICON%%", THEME.favicon()))


def check_guide(conn):
    """Refuse to build if the Leitfaden cites a rule that is not in data_rule —
    the guide must never reference law the databank does not hold."""
    have = set()
    for r in conn.execute("SELECT l.sr_number sr, a.article_no art, dr.aspect, dr.scope "
                          "FROM data_rule dr JOIN article a ON a.id=dr.article_id "
                          "JOIN law l ON l.id=a.law_id"):
        have.add((r["sr"], r["art"], r["aspect"], r["scope"]))
        have.add((r["sr"], r["art"], r["aspect"], None))
    level = {r["sr"]: r["lvl"] for r in conn.execute("SELECT sr_number sr, jurisdiction_level lvl FROM law "
                                                        "WHERE sr_number IS NOT NULL")}
    BUND = ("Bund", "DSG", "DSV", "EMBAG", "BGA", "Bundesorgan")
    bad = []
    for sec in LEITFADEN:
        for p in sec.get("punkte", []):
            refs = p.get("refs", [])
            for ref in refs:
                scope = ref[3] if len(ref) > 3 else None
                if (ref[0], ref[1], ref[2], scope) not in have:
                    bad.append(f"{sec['id']}: {ref[0]} {ref[1]} {ref[2]} {scope or ''}".strip())
            # a bullet resting ONLY on federal rules must say so in its text —
            # DSG/DSV/BGA/EMBAG bind Bundesorgane, not the canton (KDSG Art. 3 Abs. 1)
            if refs and all(level.get(ref[0]) == "federal" for ref in refs) \
                    and not any(w in (p.get("text") or "") for w in BUND):
                bad.append(f"{sec['id']}: Punkt stützt sich nur auf Bundesrecht, nennt den Bund aber nicht — "
                           f"«{(p.get('text') or '')[:60]}…»")
    return bad


# The owner's rule: open points are GAPS — to be clarified, decided or evidenced — never
# «risk» or «Verstoss» (the verbatim law term «erhöhtes Risiko für die Grundrechte» stays).
# Two texts that reach the page from other sources still frame it otherwise; the page shows
# them in gap wording. Once scripts/labels.py (todo_cats «ermitteln») and scripts/leitfaden.py
# («verwenden») carry the same wording, these replacements find nothing and change nothing.
WORDING = [
    # «Over-collection» is explained once, on #methode; everywhere else the plain words
    ('"basis":"Over-collection"', '"basis":"ohne Grundlage"'),
    # «Korpus» is databank jargon: the other forms of the canton
    ("Der Korpus ist bei diesem Datum selbst gespalten — hier ist nicht dieses Formular die Ausnahme",
     "Die Formulare verlangen diese Angabe uneinheitlich — hier ist nicht dieses Formular die Ausnahme"),
    ("im Korpus", "in den Formularen des Kantons"),
    ("Over-collection ist nur, was weder eine Norm ", "Ohne Grundlage ist nur, was weder eine Norm "),
    ("Eine Wissenslücke der Databank, kein festgestellter Verstoss.",
     "Eine Wissenslücke der Databank, kein Befund über die Verwaltung."),
    ("Wer Dritte bearbeiten lässt oder riskante Bearbeitungen plant, hat zusätzliche Pflichten.",
     "Wer Dritte bearbeiten lässt oder eine Bearbeitung plant, die eine Datenschutz-Folgenabschätzung "
     "verlangt, hat zusätzliche Pflichten."),
]


def gap_wording(text):
    for old, new in WORDING:
        text = text.replace(old, new)
    return text


# What the page reads from the export without a fallback of its own: the figures and the
# classifications computed once in export_json.py. An export that lacks one of them is an
# older one — the page would draw empty cards as if nothing were open, so the build stops.
REQUIRED = {
    "": ("labels", "kopfzahlen", "dienststellen_uebersicht", "forms", "services", "laws",
         "zitate", "datenstand", "verlauf", "gestaltung", "parteien", "konzepte", "wirkung", "register",
         "vorbefuellung", "kennungen", "vertrag", "datenmodell"),
    "labels": ("ton", "ton_map", "kontakt"),
    "kopfzahlen": ("standard_ech", "standard_einheitlich", "standard_benannt", "rechtsgrundlage",
                   "verzeichnis", "offene_punkte", "kein_standard", "kategorien"),
    "kopfzahlen.standard_ech": ("wert", "von", "ech", "ech_ton"),
    "kopfzahlen.standard_benannt": ("begriff_felder", "von", "teile", "formulare_begriff", "formulare_teile"),
    "kopfzahlen.verzeichnis": ("wert", "von", "teile"),
    "kopfzahlen.kein_standard": ("von", "teile", "formulare", "codes"),
    # scripts/gestaltung_export.py (the hook in export_json.py)
    "gestaltung": ("stand", "methode", "bestand", "gruppen", "merkmale", "kennzahlen", "entscheide",
                   "dienststellen", "grenzen", "labels"),
    "gestaltung.bestand": ("formulare", "mit_datei", "ohne_datei", "gemessen", "messart", "dienststellen_gemessen",
                           "dienststellen_ohne_formular"),
    "gestaltung.labels": ("urteil", "ton", "ton_zusatz", "urteil_gesamt", "urteil_nomen", "art", "art_erklaerung",
                          "messart", "gruppe", "merkmal", "eformular", "entscheide"),
}


def missing_keys(export):
    """The keys of REQUIRED the export does not have, as dotted paths; and whether its
    Datenfelder carry the stamped classifications (ech_state, basis_state), its forms
    their Dienststelle, their data-standard figures (standard) and their Gestaltung, and
    its services the file name of their dossier."""
    out = []
    for path, keys in REQUIRED.items():
        node = export
        for part in filter(None, path.split(".")):
            node = node.get(part) if isinstance(node, dict) else None
        out += [f"{path + '.' if path else ''}{k}" for k in keys if not isinstance(node, dict) or k not in node]
    forms = export.get("forms") or []
    fields = [d for fm in forms for d in fm.get("data_fields") or []]
    if any("ech_state" not in d or "basis_state" not in d for d in fields):
        out.append("forms[].data_fields[].ech_state / basis_state")
    if any("dienststelle" not in fm for fm in forms):
        out.append("forms[].dienststelle")
    if any("standard" not in fm for fm in forms if fm.get("data_fields")):
        out.append("forms[].standard")
    if any("dossier_slug" not in s for s in export.get("services") or []):
        out.append("services[].dossier_slug")
    if any("gestaltung" not in fm for fm in forms):
        out.append("forms[].gestaltung")
    return out


# the export contract (exportvertrag.json at the root of the repository): build.sh builds this page
# after every export has stamped its version, so the versions the page shows are the published ones
VERTRAG_PATH = os.path.join(ROOT, "exportvertrag.json")


def vertrag_kurz():
    """The export contract as the page «Datenmodell» shows it: per published export its version,
    its JSON Schema and since when the version holds, and the rules of the version numbers. Read
    from exportvertrag.json, which build.sh has written before this step (every export stamps its
    version first): a missing or unreadable file stops the build — a page without the contract
    table must not pass as complete."""
    try:
        with open(VERTRAG_PATH, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as ex:
        raise SystemExit(f"ABBRUCH build_dashboard.py: exportvertrag.json fehlt oder ist nicht lesbar ({ex}) — "
                         "erst die Exporte bauen (./build.sh), die ihn schreiben")
    if not isinstance(doc, dict) or not doc.get("exporte"):
        raise SystemExit("ABBRUCH build_dashboard.py: exportvertrag.json nennt keinen Export")
    ex = {n: {"version": v.get("version"), "schema": v.get("schema"), "seit": v.get("seit")}
          for n, v in (doc.get("exporte") or {}).items()}
    return embed(json.dumps({"exporte": ex, "regeln": doc.get("regeln") or {}}, ensure_ascii=False))


def embed(text):
    """JSON text for a <script> block: every «<» is written as \\u003c, so no harvested
    text — an HTML comment, a script tag — can end or swallow the block. JSON.parse (and
    the JavaScript parser, for the Leitfaden literal) read it back unchanged."""
    return text.replace("<", "\\u003c")


def main():
    with open(EXPORT_PATH, encoding="utf-8") as fh:
        data = gap_wording(fh.read())
    missing = missing_keys(json.loads(data))
    if missing:
        print("ABORT — data_export.json fehlt, was die Seite ohne eigene Berechnung liest "
              "(zuerst python3 scripts/export_json.py):")
        for k in missing:
            print("  ", k)
        sys.exit(1)
    conn = connect(DB_PATH)
    bad = check_guide(conn)
    conn.close()
    if bad:
        print("ABORT — Leitfaden zitiert Regeln, die nicht in der Databank sind:")
        for b in bad[:12]:
            print("  ", b)
        sys.exit(1)
    # inline as JSON text inside a <script type=application/json>, and the Leitfaden as a
    # JavaScript literal — both with every «<» escaped (embed)
    safe = embed(data)
    guide = embed(gap_wording(json.dumps(LEITFADEN, ensure_ascii=False)))
    vertrag = vertrag_kurz()
    fill = lambda tpl: tpl.replace("/*DATA*/", safe).replace("/*GUIDE*/", guide).replace("/*VERTRAG*/", vertrag)
    # the page names its own size: measured on the page itself (the two size
    # words change it by a few bytes only, far below the rounding)
    raw = fill(TEMPLATE).encode("utf-8")
    size, net = size_txt(len(raw)), net_size_txt(raw)
    html = fill(TEMPLATE.replace("%%SIZE%%", size).replace("%%NETSIZE%%", net))
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote {DASHBOARD_PATH}  ({len(html.encode('utf-8'))//1024} KB — page says «knapp {size}, "
          f"über das Netz etwa {net}», Leitfaden: {len(LEITFADEN)} Abschnitte)")


if __name__ == "__main__":
    main()
