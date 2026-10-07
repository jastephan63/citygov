#!/usr/bin/env python3
"""Build flows.html — the guided-flow dashboard (TurboTax principle), separate
from dashboard.html (the compliance view, which stays untouched).

The design and player follow three hand-built prototypes that were the
formatting reference (they are not part of this repository, and the build does
not read them): paper theme, gold crest topbar, thin progress bar with section
name, "Frage N" eyebrow, help drawer with per-node prose, radio-card choices
with [value, label, sub], scan drop zones, roster chips, autocomplete over
canonical Swiss geo data (inlined from quellen/ch-geo.js — municipalities,
postcodes and countries, sources named in its header; the build stops when the
file is missing), and a review screen that mimics the official form (formdoc)
with checklist highlights and a Behörden-Ansicht toggle that reveals the
machine field names.

Self-contained: flow JSON + geo data inlined, opens via file:// and works
offline — the 21 icons are inline SVG (Tabler Icons, MIT); no web fonts are
loaded, the page uses the system font stack declared in the CSS.

Keyboard: everything that reacts to a click is a real <button> or link (the form
picker, the answer cards, the Behörden-Ansicht switch), every new screen moves the
focus to its heading, and the place autocomplete is operated with the arrow keys.

What the page keeps: answers stay in the reader's browser (localStorage keys
«ff_profil» and «ff_draft_<form id>»), nothing is sent anywhere; the page says so
on the start screen and under every question and offers «Profil und Entwürfe
löschen» there. A new storage key must be added to storeKeys() in flows.js.

The page's HTML, stylesheet and script are real files in citygov/present/assets/flows/
(page.html, the template; flows.css, flows.js), inlined into the one page at build time.

What the build corrects against citygov.db (the DB wins over the July flow JSON):
  * meta.amt / departement / quelldatei come from service + form.source_file,
    so «Original ansehen» points at the repository file;
  * a node whose fields the form REQUIRES and the databank bases on the task
    (no_basis=1, basis_typ aufgabe/offen) loses its optional flag;
  * prose that calls a task-necessary or article-based field «freiwillig» is
    neutralised (only basis_typ 'ohne' is voluntary) — every rewrite is printed;
  * the sensitive-data note reads the documented form_disclosure rows instead
    of promising «nur für diesen Antrag»;
  * the profile prefill map (ech_map) holds only the points citygov_prefill.json marks
    vorbefuellbar (register_map.flow_schluessel, read from data_export.json): the
    applicant's own Angaben with the Einwohnerregister mark, never a spouse's, a
    child's or an employee's — the player also saves answers into the profile by it.

    python3 scripts/build_flows.py
"""
import json
import os
import re
import sys
from datetime import date

from citygov.core.common import ROOT, DB_PATH, EXPORT_PATH, connect, assert_no_local_paths
from citygov.core import labels as LABELS
from citygov.core import theme as THEME
from citygov.domain import register_map                     # the one prefill rule (flow_schluessel), standard library only
from citygov.present import template

OUT = os.path.join(ROOT, "flows.html")
# Swiss municipalities, postcodes and countries for the autocomplete (tracked
# reference data; sources and generation date in the file's header comment)
GEO = os.path.join(ROOT, "quellen", "ch-geo.js")

# Tabler Icons (https://tabler.io/icons, MIT) — 24×24 stroke paths, inlined so the
# page needs no icon font from a CDN. Referenced in flows.html / flows.js as %%I:name%%;
# an unknown name fails the build instead of rendering an empty box.
ICONS = {
    "x": '<path d="M18 6l-12 12"/><path d="M6 6l12 12"/>',
    "check": '<path d="M5 12l5 5l10 -10"/>',
    "plus": '<path d="M12 5l0 14"/><path d="M5 12l14 0"/>',
    "arrow-right": '<path d="M5 12l14 0"/><path d="M13 18l6 -6"/><path d="M13 6l6 6"/>',
    "arrow-left": '<path d="M5 12l14 0"/><path d="M5 12l6 6"/><path d="M5 12l6 -6"/>',
    "search": '<path d="M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M21 21l-6 -6"/>',
    "info-circle": '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/><path d="M12 9h.01"/><path d="M11 12h1v4h1"/>',
    "alert-triangle": '<path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z"/><path d="M12 16h.01"/>',
    "download": '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2"/><path d="M7 11l5 5l5 -5"/><path d="M12 4l0 12"/>',
    "camera": '<path d="M5 7h1a2 2 0 0 0 2 -2a1 1 0 0 1 1 -1h6a1 1 0 0 1 1 1a2 2 0 0 0 2 2h1a2 2 0 0 1 2 2v9a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-9a2 2 0 0 1 2 -2"/><path d="M9 13a3 3 0 1 0 6 0a3 3 0 0 0 -6 0"/>',
    "player-play": '<path d="M7 4v16l13 -8z"/>',
    "player-track-next": '<path d="M3 5v14l8 -7z"/><path d="M14 5v14l8 -7z"/>',
    "loader": '<path d="M12 6l0 -3"/><path d="M16.25 7.75l2.15 -2.15"/><path d="M18 12l3 0"/><path d="M16.25 16.25l2.15 2.15"/><path d="M12 18l0 3"/><path d="M7.75 16.25l-2.15 2.15"/><path d="M6 12l-3 0"/><path d="M7.75 7.75l-2.15 -2.15"/>',
    "route": '<path d="M3 19a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/><path d="M19 7m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M11 19h5.5a3.5 3.5 0 0 0 0 -7h-8a3.5 3.5 0 0 1 0 -7h4.5"/>',
    "list-check": '<path d="M3.5 5.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 11.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 17.5l1.5 1.5l2.5 -2.5"/><path d="M11 6l9 0"/><path d="M11 12l9 0"/><path d="M11 18l9 0"/>',
    "lifebuoy": '<path d="M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0 -8 0"/><path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/><path d="M15 15l3.35 3.35"/><path d="M9 15l-3.35 3.35"/><path d="M5.65 5.65l3.35 3.35"/><path d="M18.35 5.65l-3.35 3.35"/>',
    "shield-check": '<path d="M11.46 20.846a12 12 0 0 1 -7.96 -14.846a12 12 0 0 0 8.5 -3a12 12 0 0 0 8.5 3a12 12 0 0 1 -.09 7.06"/><path d="M15 19l2 2l4 -4"/>',
    "shield-lock": '<path d="M12 3a12 12 0 0 0 8.5 3a12 12 0 0 1 -8.5 15a12 12 0 0 1 -8.5 -15a12 12 0 0 0 8.5 -3"/><path d="M12 11m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M12 12l0 2.5"/>',
    "user-check": '<path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0"/><path d="M6 21v-2a4 4 0 0 1 4 -4h4"/><path d="M15 19l2 2l4 -4"/>',
    "scale": '<path d="M7 20l10 0"/><path d="M6 6l6 -1l6 1"/><path d="M12 3l0 17"/><path d="M9 12l-3 -6l-3 6a3 3 0 0 0 6 0"/><path d="M21 12l-3 -6l-3 6a3 3 0 0 0 6 0"/>',
    "arrows-split-2": '<path d="M21 17h-8l-3.5 -5h-6.5"/><path d="M21 7h-8l-3.495 5"/><path d="M18 10l3 -3l-3 -3"/><path d="M18 20l3 -3l-3 -3"/>',
}


def icon_svg(name):
    if name not in ICONS:
        raise KeyError(f"unbekanntes Icon %%I:{name}%% — in ICONS nachtragen")
    return ('<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + '</svg>')


# the page itself is a set of real files under citygov/present/assets/flows/: page.html, which
# inlines flows.css and flows.js; the markers in them (/*FAVICON*/, /*THEME*/, %%DATA%%,
# %%I:name%% …) are filled below and in main(). flows.html ends at </html> with no line end:
# page.html ends with one, like every text file, and it is dropped here
TEMPLATE = template("flows", "page.html").rstrip("\n")


# the look comes from scripts/theme.py (one definition for all generated pages)
TEMPLATE = TEMPLATE.replace("/*THEME*/", THEME.css_root()).replace("/*FAVICON*/", THEME.favicon())


def datenfelder(c, fid):
    """Data fields of a form incl. eCH assignment and subfields with their own eCH."""
    subs = {}
    for r in c.execute("""SELECT sf.data_field_id d, sf.name, sf.ech_status,
                          COALESCE(e.standard, sf.ech_standard_code) std, e.name el,
                          st.status sstat, st.url surl
                          FROM data_subfield sf
                          LEFT JOIN ech_element e ON e.id=sf.ech_element_id
                          LEFT JOIN ech_standard st ON st.code=COALESCE(e.standard, sf.ech_standard_code)
                          ORDER BY sf.data_field_id, sf.ord""", ):
        subs.setdefault(r["d"], []).append({
            "name": r["name"],
            "ech": ({"standard": r["std"], "element": r["el"], "status": r["sstat"],
                     "url": r["surl"]} if r["std"] else None),
            "ech_status": r["ech_status"]})
    out = []
    for d in c.execute("""SELECT d.id, d.name, d.definition, d.data_type, d.required, d.sensitive,
                          d.no_basis, d.basis_typ, d.subjekt, d.ech_status, COALESCE(e.standard, d.ech_standard_code) std, e.name el,
                          st.status sstat, st.url surl, st.title stitle,
                          EXISTS(SELECT 1 FROM data_field_legal_basis lb WHERE lb.data_field_id=d.id) has_basis
                          FROM data_field d
                          LEFT JOIN ech_element e ON e.id=d.ech_element_id
                          LEFT JOIN ech_standard st ON st.code=COALESCE(e.standard, d.ech_standard_code)
                          WHERE d.form_id=? ORDER BY d.ord""", [fid]):
        out.append({"name": d["name"], "definition": d["definition"], "typ": d["data_type"],
                    "pflicht": bool(d["required"]), "sensibel": d["sensitive"],
                    "freiwillig": d["basis_typ"] == "ohne",   # task-necessary fields stay required
                    "no_basis": bool(d["no_basis"]), "basis_typ": d["basis_typ"],
                    "has_basis": bool(d["has_basis"]),   # a cited article exists (data_field_legal_basis)
                    "subjekt": d["subjekt"],
                    "ech_status": d["ech_status"],
                    "ech": ({"standard": d["std"], "element": d["el"], "status": d["sstat"],
                             "url": d["surl"], "titel": d["stitle"]} if d["std"] else None),
                    "teilfelder": subs.get(d["id"], [])})
    return out


def bekanntgaben(c, fid):
    """Documented recipients of a form — the same form_disclosure/article/law join
    export_json.py uses for the dashboard's Verzeichnis and Datenfluss, so the
    flow's note can never name a recipient the compliance view does not."""
    out = []
    for r in c.execute("""SELECT fd.empfaenger, fd.mode, a.article_no, l.short_title, l.sr_number,
                          l.jurisdiction_level jur
                          FROM form_disclosure fd
                          LEFT JOIN article a ON a.id=fd.article_id
                          LEFT JOIN law l ON l.id=a.law_id
                          WHERE fd.form_id=? ORDER BY fd.empfaenger""", [fid]):
        art = None
        if r["article_no"]:
            art = r["article_no"] + (" " + r["short_title"].strip() if r["short_title"] else "")
            if r["sr_number"]:   # federal law is numbered SR, the Schaffhauser Rechtsbuch SHR
                art += ", " + ("SR " if r["jur"] == "federal" else "SHR ") + r["sr_number"]
        out.append({"empfaenger": r["empfaenger"], "mode": r["mode"], "artikel": art})
    return out


# ---- flow prose vs. the databank's basis verdicts ---------------------------
# The July flow JSON calls fields «freiwillig» by the look of the form. In the
# databank only basis_typ 'ohne' (Over-collection) is voluntary; 'artikel',
# 'aufgabe' and 'offen' fields are legally based, task-necessary or undecided —
# the same word on two surfaces would contradict the compliance view.
FREI_RX = re.compile(r"freiwillig|keine gesetzliche Pflicht", re.I)
PROSE_KEYS = ("ask", "hint", "why", "text", "intro")
# sentence split that does not break after the abbreviations the prose uses
# («Art. 33», «z.B. MedReg», «bzw. im Berufsregister») — a split there would let a
# sentence-level rewrite drop half a citation
SENT_SPLIT = re.compile(r"(?<!\bArt\.)(?<!\bAbs\.)(?<!\blit\.)(?<!\bZiff\.)(?<!\bNr\.)(?<!\bz\.B\.)"
                        r"(?<!\bbzw\.)(?<!\bu\.a\.)(?<!\bd\.h\.)(?<!\bca\.)(?<!\bvgl\.)(?<!\binkl\.)"
                        r"(?<!\bevtl\.)(?<!\bggf\.)(?<!\bresp\.)(?<=[.!?])\s+")
# form-optional fields (required=0): «freiwillig» -> «optional», the form's own vocabulary
OPT_SUBS = [
    (re.compile(r"\bFreiwillige Angaben\b"), "Optionale Angaben"),
    (re.compile(r"\bfreiwillige Angaben\b"), "optionale Angaben"),
    (re.compile(r"\bFreiwillige Angabe\b"), "Optionale Angabe"),
    (re.compile(r"\bfreiwillige Angabe\b"), "optionale Angabe"),
    (re.compile(r"\bFreiwillig\b"), "Optional"),
    (re.compile(r"\bfreiwillig\b"), "optional"),
    (re.compile(r"\b(E|e)s (besteht|gibt) keine gesetzliche Pflicht( zu dies\w+ Angaben?)?"),
     lambda m: ("D" if m.group(1) == "E" else "d") + "as Formular verlangt sie nicht"),
]
# `hilfe` (help drawer, «So füllen Sie das aus») talks about the node's own sub-fields
# — «Der Titel ist freiwillig», «Fax und Webseite sind freiwillig» — on data fields
# the form REQUIRES. Those sentences are about form-optional SUB-PARTS, so they take
# the word-level path («optional», the label's own vocabulary: «Titel (optional)») and
# only when they name one of the node's own optional sub-field labels; the sentence
# replacement («Das Formular verlangt diese Angabe») would be wrong for the Titel/Fax
# part. Domain uses never name a sub-field label and stay: «freiwillige AHV» (F273),
# «für ein gewöhnliches Wohnhaus ist es meist freiwillig» (F187), «freiwillige, aber
# regelmässige Unterstützung» (F282), «Eine Vertretung ist freiwillig» (F254).
LABEL_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")   # «Titel (optional)» -> «Titel»

# ---- exclusive-use promises vs. the documented disclosures -------------------
# «… werden nur für die Abklärung verwendet», «dienen allein der Beurteilung Ihres
# Gesuchs»: a promise no databank row backs — and on forms WITH form_disclosure rows
# (F26, F37, F170, F273) the node badge right beside it names article-backed
# recipients. Such a sentence is replaced by what the databank documents (the same
# sentence the page's bekText() builds: recipients, or «noch nicht dokumentiert»);
# a sentence that cites a norm itself is left alone — the citation is its backing.
PROMISE_RX = re.compile(
    r"\b(?:werden|wird) (?:nur|ausschliesslich|allein) (?:für|zur|zum) [^.;]*?\b(?:verwendet|genutzt|gebraucht)\b"
    r"|\bdienen allein der Beurteilung\b", re.I)
CITED_RX = re.compile(r"§|\bArt\.|\bArtikel\b")
# «X ist besonders geschützt und wird nur für … verwendet.» -> keep the first clause
PROMISE_TAIL = re.compile(r"^(?P<pre>.+?)(?:,|;| –)?\s+und\s+(?:werden|wird|dienen)\s+(?:nur|ausschliesslich|allein)\b.*$", re.S)
# «Ihre Kontodaten werden nur für … verwendet und haben keinen Einfluss …» -> keep the second
PROMISE_HEAD = re.compile(r"^(?P<subj>[^,;]+?)\s+(?:werden|wird)\s+(?:nur|ausschliesslich|allein)\s+(?:für|zur|zum)\s+"
                          r"[^.;]*?\b(?:verwendet|genutzt|gebraucht)\b\s+und\s+(?P<rest>.+)$", re.S)
# a whole-form claim in an opening note («Keine der Angaben ist gesetzlich
# vorgeschrieben – Sie dürfen einzelne Fragen überspringen»), which the flag pass
# below contradicts as soon as one node loses its skip button
NOTE_FREI_RX = re.compile(r"\bKeine der Angaben ist gesetzlich vorgeschrieben\b|\bdürfen (?:Sie )?einzelne Fragen überspringen\b", re.I)

# hand-checked touch-ups AFTER the mechanical rewrite of the same key: a dropped
# sentence took a pronoun's antecedent («es» = Erziehungsdepartement) or a contrast
# word's counterpart («aber» vs. «rechtlich freiwillig») with it. Applied only when
# the rewrite happened and the anchor is present — otherwise the build says so, so a
# regenerated flow never silently keeps a stale patch.
TOUCH_UPS = {
    (405, "absender", "why"): ("Mit der Telefonnummer erreicht es Sie direkt",
                               "Mit der Telefonnummer erreicht das Erziehungsdepartement Sie direkt"),
    (170, "kinder", "why"): ("Ohne sie kann die Dienststelle die Betreuungsgutschriften aber keinem Kind zuordnen",
                             "Ohne sie kann die Dienststelle die Betreuungsgutschriften keinem Kind zuordnen"),
}


def basis_of(field):
    """artikel / aufgabe / ohne / offen / zu_ermitteln. A field without a panel verdict
    (basis_typ NULL) is 'artikel' only when an article is actually cited for it
    (data_field_legal_basis row) — the dashboard's rule («Rechtsgrundlage zu
    ermitteln» otherwise); an unjudged no_basis field stays 'offen'. Never upgraded."""
    if field.get("basis_typ"):
        return field["basis_typ"]
    if field.get("no_basis"):
        return "offen"
    return "artikel" if field.get("has_basis") else "zu_ermitteln"


def basis_sentence(fields, plural):
    """One neutral sentence for a node the form REQUIRES; the weakest claim among
    its fields wins (offen > zu_ermitteln > aufgabe > artikel) so nothing is overclaimed."""
    typs = {basis_of(f) for f in fields if f["pflicht"]}
    ang = "diese Angaben" if plural else "diese Angabe"
    if "offen" in typs:
        return f"Das Formular verlangt {ang} – ob die Aufgabe sie erfordert, ist noch nicht beurteilt."
    if "zu_ermitteln" in typs:
        return f"Das Formular verlangt {ang} – die Rechtsgrundlage ist noch zu ermitteln."
    if "aufgabe" in typs:
        return f"Das Formular verlangt {ang} – ohne ausdrückliche Norm, aber für die Aufgabe notwendig (aufgabennotwendig)."
    return f"Das Formular verlangt {ang} – die gesetzliche Grundlage ist mit Artikel belegt."


def neutralise(text, fields, plural):
    """Rewrite one prose string so it no longer calls a non-'ohne' field freiwillig."""
    if not text or not FREI_RX.search(text):
        return text
    if any(f["pflicht"] for f in fields):
        # required by the form: drop every sentence that claims voluntariness and
        # put the databank's verdict where the first one stood
        sents = SENT_SPLIT.split(text.strip())
        kept, inserted = [], False
        for s in sents:
            if FREI_RX.search(s):
                if not inserted:
                    kept.append(basis_sentence(fields, plural))
                    inserted = True
            else:
                kept.append(s)
        text = " ".join(kept)
    else:
        for rx, rep in OPT_SUBS:
            text = rx.sub(rep, text)
    if FREI_RX.search(text):   # an unforeseen phrasing: drop the sentence rather than keep the claim
        sents = [s for s in SENT_SPLIT.split(text.strip()) if not FREI_RX.search(s)]
        text = " ".join(sents) or basis_sentence(fields, plural)
    return text


def optional_labels(node):
    """Labels of the node's form-optional sub-fields («Titel (optional)» -> «Titel»)."""
    out = []
    for f in node.get("fields") or []:
        if f.get("pflicht"):
            continue
        lab = LABEL_SUFFIX.sub("", f.get("label") or "").strip()
        if lab:
            out.append(lab)
    return out


def neutralise_hilfe(text, labels):
    """Word-level «freiwillig» -> «optional», only in sentences that name one of the
    node's own optional sub-field labels; every other sentence is left as it is."""
    if not text or not labels or not FREI_RX.search(text):
        return text
    rxs = [re.compile(r"(?<!\w)" + re.escape(l) + r"(?!\w)") for l in labels]
    out = []
    for s in SENT_SPLIT.split(text.strip()):
        if FREI_RX.search(s) and any(rx.search(s) for rx in rxs):
            for rx, rep in OPT_SUBS:
                s = rx.sub(rep, s)
        out.append(s)
    return " ".join(out)


def bek_text(bek):
    """Python twin of the page's bekText(): the documented recipients of the form as
    one sentence, recipients sharing an article cited once. Returns (text, offen)."""
    if not bek:
        return "Eine Weitergabe an andere Stellen ist für dieses Formular noch nicht dokumentiert.", True
    mode_lab = LABELS.as_export()["mode"]

    def grouped(lst):
        by, order = {}, []
        for x in lst:
            a = x["artikel"] or "Rechtsgrundlage noch nicht benannt"
            if a not in by:
                by[a] = []
                order.append(a)
            by[a].append(x["empfaenger"])
        return "; ".join(", ".join(by[a]) + " (" + a + ")" for a in order)
    sys_ = [x for x in bek if x["mode"] == "systematisch"]
    anf = [x for x in bek if x["mode"] == "auf_anfrage"]
    rest = [x for x in bek if x["mode"] not in ("systematisch", "auf_anfrage")]
    parts = []
    if sys_:
        parts.append("werden von Gesetzes wegen gemeldet an " + grouped(sys_))
    if anf:
        parts.append("können auf Anfrage bekanntgegeben werden an " + grouped(anf))
    if rest:
        parts.append("Bekanntgabe " + "; ".join(
            mode_lab.get(x["mode"], f"⟨{x['mode']}⟩") + ": " + x["empfaenger"]
            + " (" + (x["artikel"] or "Rechtsgrundlage noch nicht benannt") + ")" for x in rest))
    return "Angaben aus diesem Formular " + " und ".join(parts) + ".", False


def neutralise_promise(text, bek, bek_offen):
    """Replace every exclusive-use promise sentence by the documented disclosure
    sentence; a sentence that cites a norm is kept (the citation is its backing)."""
    if not text or not PROMISE_RX.search(text):
        return text
    after_semicolon = (bek[0].lower() + bek[1:]) if bek_offen else bek   # «…; eine Weitergabe …»
    out = []
    for s in SENT_SPLIT.split(text.strip()):
        if not PROMISE_RX.search(s) or CITED_RX.search(s):
            out.append(s)
            continue
        m = PROMISE_TAIL.match(s)
        if m:
            out.append(m.group("pre").rstrip(" ,;–") + "; " + after_semicolon)
            continue
        m = PROMISE_HEAD.match(s)
        if m:
            out.append(bek + " " + m.group("subj").strip() + " " + m.group("rest").strip())
            continue
        out.append(bek)
    return " ".join(out)


def correct_nodes(fl, fid, log):
    """Apply the databank's verdicts to the flow nodes (in memory, at build time).
    Returns nothing; appends human-readable lines to `log`."""
    by_name = {d["name"]: d for d in fl.get("datenfelder", [])}
    bek, bek_offen = bek_text(fl.get("bekanntgaben") or [])
    for n in fl.get("nodes", []):
        # 0) exclusive-use promises are about the FORM, so every node incl. notes
        for k in PROSE_KEYS + ("hilfe",):
            old = n.get(k)
            if isinstance(old, str) and PROMISE_RX.search(old):
                new = neutralise_promise(old, bek, bek_offen)
                if new != old:
                    n[k] = new
                    log.append(f"PROSA-ZWECK  F{fid} {n['id']}.{k}\n    «{old}»\n  → «{new}»")
        fields = [by_name[x] for x in (n.get("field") or []) if x in by_name]
        if not fields or all(f["freiwillig"] for f in fields):
            continue   # no data field, or genuinely voluntary ('ohne'): chip + skip stay
        plural = len(fields) > 1 or n.get("type") in ("form", "roster", "confirm")
        # 1) optional flag: every field required by the form, no_basis, judged aufgabe/offen
        if n.get("optional") and all(f["pflicht"] and f["no_basis"] and basis_of(f) in ("aufgabe", "offen")
                                     for f in fields):
            n["optional"] = False
            log.append(f"OPTIONAL→PFLICHT  F{fid} {n['id']}: {', '.join(f['name'] for f in fields)}")
        elif n.get("optional") and all(f["pflicht"] for f in fields):
            typs = "/".join(sorted({basis_of(f) for f in fields}))
            log.append(f"HINWEIS optional belassen ({typs}) F{fid} {n['id']}: "
                       f"{', '.join(f['name'] for f in fields)}")
        # 2) prose
        for k in PROSE_KEYS:
            old = n.get(k)
            if isinstance(old, str) and FREI_RX.search(old):
                new = neutralise(old, fields, plural)
                if new != old:
                    tu = TOUCH_UPS.get((fid, n["id"], k))
                    if tu:
                        if tu[0] in new:
                            new = new.replace(tu[0], tu[1])
                        else:
                            log.append(f"WARN Lesbarkeits-Patch F{fid} {n['id']}.{k}: Anker «{tu[0]}» fehlt — "
                                       f"Eintrag in TOUCH_UPS prüfen")
                    n[k] = new
                    log.append(f"PROSA  F{fid} {n['id']}.{k}\n    «{old}»\n  → «{new}»")
            elif TOUCH_UPS.get((fid, n["id"], k)):
                log.append(f"HINWEIS Lesbarkeits-Patch F{fid} {n['id']}.{k} nicht mehr nötig (Text neu erzeugt?)")
        # 3) help drawer: sub-field statements, word-level and label-gated only
        old = n.get("hilfe")
        if isinstance(old, str) and FREI_RX.search(old):
            new = neutralise_hilfe(old, optional_labels(n))
            if new != old:
                n["hilfe"] = new
                log.append(f"PROSA-HILFE  F{fid} {n['id']}.hilfe\n    «{old}»\n  → «{new}»")


def flow_basis_note(fl):
    """One sentence on the flow's required fields for an opening note that claimed
    «Keine der Angaben ist gesetzlich vorgeschrieben» (weakest claim wins), plus the
    skip sentence only while a node is still skippable after the flag pass."""
    typs = {basis_of(d) for d in fl.get("datenfelder", []) if d["pflicht"] and not d["freiwillig"]}
    if not typs:
        return None
    if typs == {"aufgabe"}:
        s = ("Eine ausdrückliche gesetzliche Vorschrift gibt es für diese Angaben nicht; das Formular "
             "verlangt die Pflichtfelder aber, weil die Aufgabe sie braucht (aufgabennotwendig).")
    elif typs & {"offen", "zu_ermitteln"}:
        s = ("Nicht jede Angabe ist gesetzlich vorgeschrieben; ob die Aufgabe einzelne Angaben erfordert, "
             "ist noch nicht beurteilt – das Formular verlangt die Pflichtfelder gleichwohl.")
    elif "aufgabe" in typs:
        s = ("Nicht jede Angabe ist gesetzlich vorgeschrieben; das Formular verlangt die Pflichtfelder "
             "aber, weil die Aufgabe sie braucht (aufgabennotwendig).")
    else:
        s = "Die Pflichtangaben sind gesetzlich vorgeschrieben (die Grundlage ist mit Artikel belegt)."
    by_name = {d["name"]: d for d in fl.get("datenfelder", [])}
    skippable = any(n.get("optional") or (n.get("field") and all(by_name.get(x, {}).get("freiwillig")
                                                                  for x in n["field"]))
                    for n in fl.get("nodes", []))
    if skippable:   # the player marks those nodes with an «Überspringen» button, nothing else
        s += " Wo die Schaltfläche «Überspringen» erscheint, dürfen Sie die Frage auslassen."
    return s


def correct_notes(fl, fid, log):
    """Opening notes (type note, no field) that declare the whole form skippable
    contradict the flipped flags — rewritten from the flow's own fields, AFTER the
    flag pass of correct_nodes()."""
    for n in fl.get("nodes", []):
        if n.get("type") != "note" or n.get("field"):
            continue
        old = n.get("text")
        if not isinstance(old, str) or not NOTE_FREI_RX.search(old):
            continue
        rep = flow_basis_note(fl)
        sents, done = [], False
        for s in SENT_SPLIT.split(old.strip()):
            if NOTE_FREI_RX.search(s):
                if rep and not done:
                    sents.append(rep)
                    done = True
            else:
                sents.append(s)
        new = " ".join(sents)
        if new != old:
            n["text"] = new
            log.append(f"NOTIZ  F{fid} {n['id']}.text\n    «{old}»\n  → «{new}»")


EMAIL_RX = re.compile(r"^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$")


def kontakt_teile(dv):
    """The DVSH contact of a service as typed parts — adresse, telefon, email — so the page
    can label each one as the dashboard does («Kontakt (laut DVSH): Adresse · Tel. … ·
    E-Mail …»). Values stay exactly as the DVSH stores them (a number written «052 …» is
    shown as «052 …»; only the page's tel: link target is normalised). dvsh_service.kontakt
    is the e-mail address in today's data; a free text there is kept as `text`, a JSON
    object contributes its own name/telefon/email/adresse. None when nothing is stored."""
    teile = {"adresse": (dv["address"] or "").strip(), "telefon": (dv["phone"] or "").strip(),
             "email": (dv["email"] or "").strip()}
    raw = dv["kontakt"]
    try:
        ko = json.loads(raw) if raw else None
    except ValueError:
        ko = raw
    if isinstance(ko, dict):
        for k in ("name", "adresse", "telefon", "email"):
            v = str(ko.get(k) or "").strip()
            if v and (k == "name" or not teile.get(k)):
                teile[k] = v
    elif isinstance(ko, list):
        ko = " · ".join(str(x).strip() for x in ko if str(x or "").strip())
    if isinstance(ko, str) and ko.strip():
        ko = ko.strip()
        if EMAIL_RX.match(ko):
            teile["email"] = ko          # the address the page has always shown for this service
        elif ko not in teile.values():
            teile["text"] = ko
    teile = {k: v for k, v in teile.items() if v}
    return teile or None


def datenstand():
    """The data date is computed once, in export_json.py — read it, never re-derive it."""
    try:
        with open(EXPORT_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        ds = d.get("datenstand") or {}
        return {"build": ds.get("build") or (d.get("generated_at") or "")[:10] or None,
                "dvsh_stand": ds.get("dvsh_stand"), "shep_harvest": ds.get("shep_harvest")}
    except (OSError, ValueError) as e:
        print("WARN: data_export.json nicht lesbar — Datenstand bleibt offen:", e)
        return {"build": None, "dvsh_stand": None, "shep_harvest": None}


def main():
    c = connect(DB_PATH)
    flows = []
    log = []
    # the exported Formulare (units with their party and prefill marks), read once
    try:
        with open(EXPORT_PATH, encoding="utf-8") as fh:
            export_forms = {f["id"]: f for f in json.load(fh).get("forms") or []}
    except (OSError, ValueError) as e:
        sys.exit(f"ABBRUCH build_flows.py: data_export.json nicht lesbar ({e}) — zuerst scripts/export_json.py")
    import hashlib
    n_forms = c.execute("SELECT count(*) FROM form").fetchone()[0]
    try:
        for r in c.execute("""SELECT ff.form_id, ff.flow, ff.form_hash, ff.generated_at,
                              f.source_file, s.id sid, s.dienststelle, s.department FROM formflow ff
                              JOIN form f ON f.id=ff.form_id JOIN service s ON s.id=f.service_id
                              ORDER BY s.department, s.name"""):
            fl = json.loads(r["flow"])
            # DB is the source of truth for office/department — flow drafts sometimes
            # "correct" the spelling (Departement vs Department) and split the sidebar
            fl["meta"]["amt"] = r["dienststelle"] or fl["meta"].get("amt")
            fl["meta"]["departement"] = r["department"] or fl["meta"].get("departement")
            fl["meta"]["stand"] = (r["generated_at"] or "")[:10]
            fl["meta"]["stand_txt"] = LABELS.fmt_date(fl["meta"]["stand"])   # reader-facing dd.mm.yyyy
            # the «Original ansehen» link must resolve inside the repository: form.source_file
            # (relative to ROOT, like flows.html itself) — the flow JSON's own quelldatei points
            # at a folder on the author's machine. No file → no link, said so.
            fl["meta"]["quelldatei"] = r["source_file"] or None
            # staleness: source file changed since the flow was derived?
            stale = False
            src = os.path.join(ROOT, r["source_file"]) if r["source_file"] else None
            if src and os.path.exists(src) and r["form_hash"]:
                cur = hashlib.sha256(open(src, "rb").read()).hexdigest()[:16]
                stale = (cur != r["form_hash"])
            fl["meta"]["veraltet"] = stale
            fl["datenfelder"] = datenfelder(c, r["form_id"])
            fl["bekanntgaben"] = bekanntgaben(c, r["form_id"])
            correct_nodes(fl, r["form_id"], log)     # flags + prose (reads bekanntgaben)
            correct_notes(fl, r["form_id"], log)     # whole-form notes, after the flag pass
            # eCH map for once-only prefill: the player prefills from the CITIZEN's
            # profile and saves answers back into it, keyed by element — so only the
            # applicant's own Angaben may be in it, never a spouse's, a child's or an
            # employee's (they would be offered later as the citizen's own). ONE rule,
            # the one citygov_prefill.json and burden.prefillable use
            # (register_map.prefill_punkte: Einwohnerregister mark, party Gesuchsteller/in
            # as a natural person, not mehrdeutig within that party). Keys «Feld» or
            # «Feld›Teilfeld» -> "eCH-XXXX·element"
            xf = export_forms.get(r["form_id"])
            if xf is None:
                sys.exit(f"ABBRUCH build_flows.py: Formular {r['form_id']} fehlt in data_export.json — "
                         "zuerst scripts/export_json.py ausführen")
            fl["ech_map"] = register_map.flow_schluessel(xf)
            # DVSH: real process steps + contact for the done screen
            dv = c.execute("SELECT ablauf, kontakt, email, phone, address FROM dvsh_service "
                           "WHERE service_id=? LIMIT 1", [r["sid"]]).fetchone()
            if dv:
                try:
                    ab = json.loads(dv["ablauf"]) if dv["ablauf"] else []
                    if isinstance(ab, str):   # double-encoded row: decode once more, never slice text
                        ab = json.loads(ab)
                    # items that are still JSON text are decoded too, so no step is shown as raw JSON
                    ab = [json.loads(x) if isinstance(x, str) and x.lstrip().startswith("{") else x
                          for x in (ab if isinstance(ab, list) else [])]
                except Exception:
                    ab = []
                ko = kontakt_teile(dv)   # typed parts: adresse / telefon / email
                if ab or ko:
                    fl["dvsh"] = {"ablauf": ab[:8], "kontakt": ko}
                    if len(ab) > 8:   # capped list: the gap is shown as a gap, never silently cut
                        fl["dvsh"]["ablauf_mehr"] = LABELS.pl(len(ab) - 8, "weiterer Schritt", "weitere Schritte")
            flows.append(fl)
    except Exception as e:
        # loud, never a half-empty page (lesson 16): a missing formflow table or a
        # broken flow JSON aborts the build instead of writing 0 flows
        print("ABBRUCH beim Lesen der Flows (formflow-Tabelle fehlt oder Flow-JSON defekt):", e)
        raise
    c.close()
    for line in log:
        print(line)
    def n_of(prefix):
        return sum(1 for l in log if l.startswith(prefix + " "))
    print(f"-- {n_of('OPTIONAL→PFLICHT')} Knoten optional→Pflicht, {n_of('PROSA')} Prosa-Stellen neutralisiert "
          f"(«freiwillig» nur noch für basis_typ 'ohne'), {n_of('PROSA-HILFE')} Hilfetexte «freiwillig»→«optional», "
          f"{n_of('PROSA-ZWECK')} Zweckversprechen durch dokumentierte Bekanntgaben ersetzt, "
          f"{n_of('NOTIZ')} Formular-Hinweise angepasst, {n_of('WARN')} Warnungen")
    # without the geo lists the guided forms lose their place/postcode/country
    # autocomplete — never publish that degraded page silently
    if not os.path.exists(GEO):
        sys.exit("ABBRUCH: quellen/ch-geo.js fehlt — ohne die Datei verliert flows.html die "
                 "Autocomplete-Listen für Gemeinde, PLZ und Land")
    geo = open(GEO, encoding="utf-8").read()
    # the geo lists are inlined as script text, not as JSON: they cannot be escaped, so a
    # «<» in them (which could end or swallow the script element) stops the build instead
    if "<" in geo:
        sys.exit("ABBRUCH: quellen/ch-geo.js enthält das Zeichen «<» — als Skripttext eingebettet "
                 "könnte es das Skript der Seite beenden; bitte im Quelltext als \\u003c schreiben")
    ds = datenstand()
    today = date.today().isoformat()
    flow_dates = sorted({f["meta"].get("stand") for f in flows if f["meta"].get("stand")})
    fmt = LABELS.fmt_date   # reader-facing dates as dd.mm.yyyy (the HTML build comment keeps ISO)
    stamp = ("Datenstand: Export " + (fmt(ds["build"]) if ds["build"] else "offen")
             + (" · DVSH-Stand " + fmt(ds["dvsh_stand"]) if ds["dvsh_stand"] else "")
             + (" · Flows erzeugt " + (fmt(flow_dates[0]) if len(flow_dates) == 1
                                      else f"{fmt(flow_dates[0])} bis {fmt(flow_dates[-1])}") if flow_dates else "")
             + " · Seite gebaut " + fmt(today))
    labels_js = {k: LABELS.as_export()[k] for k in ("sens", "mode", "basis_typ", "node_typ", "kontakt")}

    def js(obj):
        # JSON inside <script>: every «<» is written as backslash-u003c, so no text of the data
        # can end the script element («</script») or open a comment that swallows the rest
        # («<!--» followed by «<script»). The browser reads the escape back as «<», and outside
        # of strings JSON has no «<».
        return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")
    html = (TEMPLATE
            .replace("%%BUILD%%", today)
            .replace("%%NFORMS%%", str(n_forms))
            .replace("%%STAMP%%", js(stamp))
            .replace("%%LABELS%%", js(labels_js))
            .replace("%%GEO%%", geo)
            .replace("%%DATA%%", js(flows)))
    html = re.sub(r"%%I:([a-z0-9-]+)%%", lambda m: icon_svg(m.group(1)), html)
    # guards: the page must work offline (no CDN scripts/stylesheets, no icon font) and
    # every placeholder must be resolved
    leftover = re.findall(r"%%[A-Z]+(?::[a-z0-9-]+)?%%", html)
    assert not leftover, f"unaufgelöste Platzhalter: {leftover[:5]}"
    assert "cdnjs" not in html and 'class="ti ' not in html, "Icon-Font-Rest im Template"
    ext = re.findall(r'<link[^>]+href="(https?://[^"]+)"', html)
    ext += re.findall(r'<script[^>]+src="(https?://[^"]+)"', html)
    assert not ext, f"externe Abhängigkeit (Stylesheet, Schrift oder Skript): {ext}"
    # the inlined data holds no «<» any more (see js()); checked on the finished page: between
    # «var FLOWS=» and the end of that statement there must be none
    a = html.index("var FLOWS=")
    b = html.index(";\n// coverage + data date", a)
    assert "<" not in html[a:b], "die eingebetteten Flow-Daten enthalten ein unmaskiertes «<»"
    assert_no_local_paths("flows.html", html)
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"wrote {OUT}  ({os.path.getsize(OUT)//1024} KB, {len(flows)} von {n_forms} Formularen mit Flow; {stamp})")


if __name__ == "__main__":
    main()
