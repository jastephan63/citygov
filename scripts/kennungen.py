#!/usr/bin/env python3
"""Permanent identifiers («Kennungen») for the objects of the databank.

Every service, Formular, Datenfeld, Teilfeld, canonical Angabe, law, article and
data-handling rule gets an identifier that never changes meaning, so that other
systems (the Datentresor, the LLM agent, a peer canton) can store it and still
find the same object after the next data change. The scheme is neutral (no web
address in it); the base address for resolvable URIs is an owner decision and
lives in the single constant BASIS_URI below.

    sh:service:<slug>                                  service
    sh:formular:<slug>                                 Formular
    sh:formular:<slug>:feld:<n>                        Datenfeld n of the Formular
    sh:formular:<slug>:feld:<n>:teil:<m>               Teilfeld m of that Datenfeld
    sh:angabe:<eCH-code>:<element>[:<context>]         canonical Angabe (eCH element)
    sh:angabe:<eSH-code>:<element>                     canonical Angabe (eSH draft key)
    sh:gesetz:sr-<SR> | shr-<SHR> | <slug>             law (federal / cantonal / other)
    sh:gesetz:<…>:art-<no> | par-<no> | nr-<no>        article («Art. 16f», «§ 11», bare number)
    sh:gesetz:<…>:<article>:regel:<aspect>-<scope>[-<category>]   data-handling rule

The string is minted ONCE from the natural key the object has at that moment and
is never changed, reused or reassigned. Fields and Teilfelder have no natural key
that survives a renamed label, so their last segment is a serial number minted
once per Formular (Datenfeld) or Datenfeld (Teilfeld), in field order, never
reused. A clash of two minted strings gets «~2», «~3» (never a reuse).

Natural keys (column kennung.schluessel) and the evidence that lets a renamed
object keep its identifier (column merkmal, a checksum except for the position):

    art       schluessel (what the object is)          merkmal (rename evidence)
    service   slug                                     name
    formular  slug                                     title
    feld      norm_label(name) within the Formular     ord|data_type|eCH element or eSH key|
                                                       definition and allowed values
    teilfeld  norm_label(name) within the Datenfeld    ord|eCH element or eSH key
    angabe    ech|standard|element|context  or esh|key (none: a different element
                                                         is a different Angabe)
    gesetz    sr:<SR> / shr:<SHR> / slug:<slug>        slug
    artikel   number within the law («Art. 12», «§ 12» heading
              and «12» are the same number)
    regel     aspect|scope|category within the article the quote

How a run recognises «the same object» again (deterministic, no judgement):
  1. same parent and same schluessel -> the same object (several candidates are
     paired by row id + merkmal, then merkmal, then row id, then a single pair);
  2. otherwise a renamed object keeps its identifier only on unambiguous evidence
     that a deleted and re-inserted row cannot fake (SQLite hands out the ids of
     deleted rows again, and load_data_fields.py / init_subfields.py delete and
     insert whole field lists), unique on both sides:
       Datenfeld  same parent, position and data type, and the same eCH element or
                  eSH key; a field without one only with the same non-empty
                  definition / allowed values — the row id is never evidence here;
       Teilfeld   same parent and position, and the same eCH element or eSH key; a
                  part that had none only when the Datenfeld still has as many parts
                  as before (so no position can have shifted);
       others     same parent and same merkmal, plus the same row id where the
                  table keeps its row ids (service, form, law, article; data_rule
                  is rebuilt wholesale, there the evidence must be unique instead).
     A unit that had an element and now has another one or none is never
     «renamed»: its identifier becomes «entfallen» and the unit gets a new one
     (a confirmed rename then goes through quellen/kennung_abloesungen.json);
  3. an identifier whose object is gone becomes «entfallen» (it stays, never
     deleted); it comes back only for the identical schluessel under the same parent;
  4. a new object gets a new identifier. The parent of a Datenfeld, Teilfeld,
     article or rule is the identifier it was minted under (its prefix).
«abgelöst durch …» is never guessed: it is set only from the reviewed decision
file quellen/kennung_abloesungen.json ([{"alt", "neu", "grund"}], optional): the
old identifier must be «entfallen», the new one active and of the same art.

Measured on the committed states 16.09. -> 04.10.2026 (seven builds replayed):
1,430 and then 1,910 canonical_attribute numbers changed meaning, no identifier
did; 285 renamed Datenfelder and Teilfelder kept theirs, and only removed objects
(one Formular with its fields and parts, five duplicate article rows, seven eCH
elements no longer used) became «entfallen». Re-measured 2026-10-05 with the rename
evidence above (4851de3 -> b8a28ca): the same 285 renames kept, every one with its
element (or a part slot that got its first element); a simulated reload of two
Formulare and a changed part list (Telefon -> Website, Spesen -> Unterkunft,
Wohnstaat -> Telefon) gives «entfallen» + a new identifier, never a re-pointed one.

The registry guards itself against being lost: the run refuses to mint into a
missing or empty table unless --erstausgabe is given (and never when the published
data_export.json already carries identifiers), and pruefen() — part of
validate_db — reports every identifier the published data_export.json carries that
the table does not hold (a citygov.db restored from Git, init_db.py --force plus the
loaders, a dropped table would otherwise re-issue retired strings for other objects).
Every identifier that is no longer active is published with its status, date,
reason and successor (block «kennungen» in data_export.json, meta.kennungen in
citygov_llm.json), so a consumer that stored one learns what became of it.

The gates live in the schema as triggers (no DELETE; kennung, art, target table
and issue date never change; an Angabe identifier never changes its eCH element or
eSH key; only an active identifier follows a rename; a superseded identifier stays
superseded; the history is append-only), so any client is bound, not only this
loader. pruefen(conn) is the gate for scripts/validate_db.py (safe while another
loader has changed data and this one has not run yet); pruefen_aktuell(conn)
additionally demands that every object has exactly one active identifier and
every active identifier points at the object it names (run after this loader).

Loader: staging -> validate -> swap; idempotent (a second run changes nothing,
says so and writes nothing). Runs in ./build.sh right after init_register.py,
which renumbers canonical_attribute on every build.

    python3 scripts/kennungen.py [--datum JJJJ-MM-TT] [--abloesungen <json>] [--erstausgabe]
    python3 scripts/kennungen.py --aufloesen <kennung>     # resolver, read-only
    python3 scripts/kennungen.py --pruefen                 # end-of-build check, read-only
"""
import hashlib, json, os, re, shutil, sqlite3, sys, unicodedata
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, ROOT, connect, norm_label

# Owner decision: the base address under which an identifier would resolve (a
# canton-owned domain is preferred over a personal GitHub Pages address). None =
# not decided; exports then carry the identifiers without a URI.
BASIS_URI = None

ABLOESUNGEN = os.path.join(ROOT, "quellen", "kennung_abloesungen.json")
# the published file whose identifiers must never be lost (CITYGOV_EXPORTE points at
# another folder of published files, e.g. for a test; unset = the repository's own)
VEROEFFENTLICHT = os.path.join(os.environ.get("CITYGOV_EXPORTE") or ROOT, "data_export.json")
_KENNUNG_IM_TEXT = re.compile(r'"(sh:(?:service|formular|angabe|gesetz):[^"\s]+)"')

# art -> target table, parent art, whether the target table keeps its row ids (a row
# id then pairs two objects with the same natural key; it is never rename evidence
# for a Datenfeld, whose rows load_data_fields.py deletes and inserts again)
ARTEN = {
    "service":  {"tabelle": "service",             "eltern": None,       "stabile_ids": True},
    "formular": {"tabelle": "form",                "eltern": None,       "stabile_ids": True},
    "feld":     {"tabelle": "data_field",          "eltern": "formular", "stabile_ids": True},
    "teilfeld": {"tabelle": "data_subfield",       "eltern": "feld",     "stabile_ids": False},
    "gesetz":   {"tabelle": "law",                 "eltern": None,       "stabile_ids": True},
    "artikel":  {"tabelle": "article",             "eltern": "gesetz",   "stabile_ids": True},
    "regel":    {"tabelle": "data_rule",           "eltern": "artikel",  "stabile_ids": False},
    "angabe":   {"tabelle": "canonical_attribute", "eltern": None,       "stabile_ids": False},
}
REIHENFOLGE = ("service", "formular", "feld", "teilfeld", "gesetz", "artikel", "regel", "angabe")
# arts whose schluessel is unique among the active identifiers (no parent scope)
EINDEUTIG = ("service", "formular", "gesetz", "angabe")

DDL = """
CREATE TABLE IF NOT EXISTS kennung (
    kennung         TEXT PRIMARY KEY,
    art             TEXT NOT NULL CHECK (art IN ('service','formular','feld','teilfeld',
                                                 'angabe','gesetz','artikel','regel')),
    ziel_tabelle    TEXT NOT NULL CHECK (ziel_tabelle IN ('service','form','data_field','data_subfield',
                                                 'canonical_attribute','law','article','data_rule')),
    ziel_id         INTEGER,
    schluessel      TEXT NOT NULL,
    merkmal         TEXT,
    status          TEXT NOT NULL DEFAULT 'aktiv' CHECK (status IN ('aktiv','abgeloest','entfallen')),
    abgeloest_durch TEXT REFERENCES kennung(kennung),
    seit            TEXT NOT NULL,
    bis             TEXT,
    grund           TEXT,
    CHECK ((status = 'aktiv') = (ziel_id IS NOT NULL)),
    CHECK ((status = 'aktiv') = (bis IS NULL)),
    CHECK ((status = 'abgeloest') = (abgeloest_durch IS NOT NULL))
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS kennung_verlauf (
    id       INTEGER PRIMARY KEY,
    kennung  TEXT NOT NULL REFERENCES kennung(kennung),
    datum    TEXT NOT NULL,
    ereignis TEXT NOT NULL CHECK (ereignis IN ('umbenannt','entfallen','reaktiviert','abgeloest')),
    vorher   TEXT,
    nachher  TEXT
);
CREATE INDEX IF NOT EXISTS ix_kennung_verlauf ON kennung_verlauf(kennung);
CREATE TRIGGER IF NOT EXISTS tg_kennung_nie_loeschen BEFORE DELETE ON kennung
BEGIN SELECT RAISE(ABORT, 'GATE: eine Kennung wird nie gelöscht — sie bleibt als entfallen oder abgelöst stehen'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_unveraenderlich BEFORE UPDATE ON kennung
WHEN NEW.kennung IS NOT OLD.kennung OR NEW.art IS NOT OLD.art OR NEW.ziel_tabelle IS NOT OLD.ziel_tabelle
     OR NEW.seit IS NOT OLD.seit
BEGIN SELECT RAISE(ABORT, 'GATE: Kennung, Art, Zieltabelle und Vergabedatum ändern sich nie'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_angabe_fest BEFORE UPDATE ON kennung
WHEN OLD.art = 'angabe' AND NEW.schluessel IS NOT OLD.schluessel
BEGIN SELECT RAISE(ABORT, 'GATE: eine Angabe-Kennung steht für genau ein eCH-Element oder einen eSH-Schlüssel'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_schluessel_nur_aktiv BEFORE UPDATE ON kennung
WHEN NEW.schluessel IS NOT OLD.schluessel AND NOT (OLD.status = 'aktiv' AND NEW.status = 'aktiv')
BEGIN SELECT RAISE(ABORT, 'GATE: nur eine aktive Kennung folgt einer Umbenennung; eine entfallene lebt nur für denselben Schlüssel wieder auf'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_abgeloest_endgueltig BEFORE UPDATE ON kennung
WHEN OLD.status = 'abgeloest' AND (NEW.status IS NOT OLD.status OR NEW.abgeloest_durch IS NOT OLD.abgeloest_durch)
BEGIN SELECT RAISE(ABORT, 'GATE: eine abgelöste Kennung bleibt abgelöst, ihr Nachfolger ändert sich nie'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_verlauf_u BEFORE UPDATE ON kennung_verlauf
BEGIN SELECT RAISE(ABORT, 'GATE: der Verlauf der Kennungen ist unveränderlich'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_verlauf_d BEFORE DELETE ON kennung_verlauf
BEGIN SELECT RAISE(ABORT, 'GATE: der Verlauf der Kennungen ist unveränderlich'); END;
"""
TRIGGER = ("tg_kennung_nie_loeschen", "tg_kennung_unveraenderlich", "tg_kennung_angabe_fest",
           "tg_kennung_schluessel_nur_aktiv", "tg_kennung_abgeloest_endgueltig",
           "tg_kennung_verlauf_u", "tg_kennung_verlauf_d")

_SEG = r"[a-z0-9][a-z0-9.-]*"
_TILDE = r"(?:~[2-9]|~[1-9][0-9]+)?"
FORMAT = {
    "service":  re.compile(rf"^sh:service:{_SEG}{_TILDE}$"),
    "formular": re.compile(rf"^sh:formular:{_SEG}{_TILDE}$"),
    "feld":     re.compile(r"^(?P<eltern>.+):feld:[1-9][0-9]*$"),
    "teilfeld": re.compile(r"^(?P<eltern>.+):teil:[1-9][0-9]*$"),
    "angabe":   re.compile(rf"^sh:angabe:e(?:CH|SH)-[0-9]{{4}}:[A-Za-z0-9_.-]+(?::[A-Za-z0-9_]+)?{_TILDE}$"),
    "gesetz":   re.compile(rf"^sh:gesetz:{_SEG}{_TILDE}$"),
    "artikel":  re.compile(rf"^(?P<eltern>.+):(?:art|par|nr)-[a-z0-9][a-z0-9.-]*{_TILDE}$"),
    "regel":    re.compile(rf"^(?P<eltern>.+):regel:[a-z_]+-[a-z_]+(?:-[a-z_]+)?{_TILDE}$"),
}
PLACEHOLDER_LAW = "zitiert (unverifiziert)"   # retired auto-draft rows; never surfaces, never an identifier


def eltern_von(kennung, art):
    """The parent identifier a child identifier was minted under (None for root arts)."""
    if not ARTEN[art]["eltern"]:
        return None
    m = FORMAT[art].match(kennung)
    return m.group("eltern") if m else None


def _pruefsumme(text):
    """merkmal: a short checksum of the rename evidence (only ever compared for equality)."""
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:12]


def _rows(conn, sql, args=()):
    """Rows as dicts, whatever row_factory the caller's connection has."""
    cur = conn.cursor()
    cur.row_factory = sqlite3.Row
    return [dict(r) for r in cur.execute(sql, args)]


# ---- natural keys ---------------------------------------------------------------
def slug(text):
    """Lower-case ASCII segment: accents dropped, ß -> ss, anything else -> '-'."""
    t = unicodedata.normalize("NFKD", (text or "").replace("ß", "ss").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9.]+", "-", t).strip("-.") or "x"


def _slug_segment(existing):
    """A service or Formular slug as it is, when it is already a valid segment."""
    return existing if re.match(r"^[a-z0-9][a-z0-9.-]*$", existing or "") else slug(existing)


def angabe_schluessel_ech(standard, element, context):
    return f"ech|{standard}|{element}|{context or ''}"


def angabe_schluessel_esh(esh_key):
    return f"esh|{esh_key}"


def artikel_nummer(article_no):
    """The article number without its notation: «Art. 16f», «§ 16f» and «16f» -> «16f».
    Within one law the number identifies the article; a law uses one notation, and
    a row whose notation was corrected (12 -> § 12) is still the same article."""
    a = re.sub(r"\s+", " ", (article_no or "").strip())
    a = re.sub(r"^(?:Art\.|§)\s*", "", a)
    return a.lower()


def _artikel_segment(article_no):
    a = re.sub(r"\s+", " ", (article_no or "").strip())
    m = re.match(r"^Art\.\s*(.+)$", a)
    if m:
        return "art-" + slug(m.group(1))
    m = re.match(r"^§\s*(.+)$", a)
    if m:
        return "par-" + slug(m.group(1))
    return "nr-" + slug(a)


def _gesetz(r):
    """(schluessel, segment) of a law: its official number where it has one."""
    if r["jurisdiction_level"] == "federal" and r["sr_number"]:
        nr = r["sr_number"].strip()
        return f"sr:{nr}", "sr-" + slug(nr)
    m = re.match(r"^SHR\s+(\S+)$", (r["cantonal_ref"] or "").strip())
    if m:
        return f"shr:{m.group(1)}", "shr-" + slug(m.group(1))
    return f"slug:{r['slug']}", slug(r["slug"])


def _element_signatur(ech, esh_code, esh_element):
    if ech:
        return "ech:" + angabe_schluessel_ech(*ech)[4:]
    if esh_code and esh_element:
        return f"esh:{esh_code}:{esh_element}"
    return "-"


# the checksum part of a merkmal that stands for «no element» / «no content»
OHNE = hashlib.sha256(b"-").hexdigest()[:12]


def _inhalt(definition, allowed_values):
    """The content evidence of a Datenfeld: its definition and allowed values
    (whitespace collapsed); '-' when it has neither."""
    t = re.sub(r"\s+", " ", (definition or "").strip())
    v = re.sub(r"\s+", " ", (allowed_values or "").strip())
    return f"{t}|{v}" if (t or v) else "-"


def feld_merkmal(m):
    """(ord, data_type, element checksum, content checksum) of a Datenfeld merkmal;
    a merkmal written before 2026-10-05 has only «ord|data_type» (then the last two
    are None: no element evidence, so such an identifier never follows a rename)."""
    teile = (m or "").split("|")
    if len(teile) == 4:
        return tuple(teile)
    return (teile[0], teile[1] if len(teile) > 1 else "", None, None)


def objekte(conn, art, eltern_karte=None):
    """The current objects of one art as dicts: ziel_id, eltern_ziel (row id of the
    parent object or None), schluessel, merkmal, segment (None = serial), sort."""
    q = lambda sql: conn.execute(sql).fetchall()
    out = []
    if art == "service":
        for r in q("SELECT id, slug, name FROM service"):
            out.append(dict(ziel_id=r[0], eltern_ziel=None, schluessel=r[1], merkmal=r[2],
                            segment=_slug_segment(r[1]), sort=(r[1],)))
    elif art == "formular":
        for r in q("SELECT id, slug, title FROM form"):
            out.append(dict(ziel_id=r[0], eltern_ziel=None, schluessel=r[1], merkmal=r[2],
                            segment=_slug_segment(r[1]), sort=(r[1],)))
    elif art == "feld":
        for r in q("SELECT d.id, d.form_id, d.ord, d.name, d.data_type, e.standard, e.name, e.context, d.esh_code, "
                   "d.esh_element, d.definition, d.allowed_values FROM data_field d "
                   "LEFT JOIN ech_element e ON e.id = d.ech_element_id"):
            ech = (r[5], r[6], r[7]) if r[5] else None
            merkmal = (f"{r[2]}|{r[4] or ''}|{_pruefsumme(_element_signatur(ech, r[8], r[9]))}|"
                       f"{_pruefsumme(_inhalt(r[10], r[11]))}")
            out.append(dict(ziel_id=r[0], eltern_ziel=r[1], schluessel=norm_label(r[3]),
                            merkmal=merkmal, segment=None, sort=(r[2] if r[2] is not None else -1, r[0])))
    elif art == "teilfeld":
        for r in q("SELECT s.id, s.data_field_id, s.ord, s.name, e.standard, e.name, e.context, s.esh_code, "
                   "s.esh_element FROM data_subfield s LEFT JOIN ech_element e ON e.id = s.ech_element_id"):
            ech = (r[4], r[5], r[6]) if r[4] else None
            out.append(dict(ziel_id=r[0], eltern_ziel=r[1], schluessel=norm_label(r[3]),
                            merkmal=f"{r[2]}|{_pruefsumme(_element_signatur(ech, r[7], r[8]))}", segment=None,
                            sort=(r[2], r[0])))
    elif art == "gesetz":
        for r in conn.execute("SELECT id, slug, jurisdiction_level, sr_number, cantonal_ref FROM law "
                              "WHERE last_checked IS NOT ?", [PLACEHOLDER_LAW]):
            r = dict(zip(("id", "slug", "jurisdiction_level", "sr_number", "cantonal_ref"), r))
            key, seg = _gesetz(r)
            out.append(dict(ziel_id=r["id"], eltern_ziel=None, schluessel=key, merkmal=r["slug"],
                            segment=seg, sort=(key,)))
    elif art == "artikel":
        for r in conn.execute("SELECT a.id, a.law_id, a.article_no, a.heading FROM article a JOIN law l "
                              "ON l.id = a.law_id WHERE l.last_checked IS NOT ?", [PLACEHOLDER_LAW]):
            out.append(dict(ziel_id=r[0], eltern_ziel=r[1], schluessel=artikel_nummer(r[2]),
                            merkmal=re.sub(r"\s+", " ", (r[3] or "").strip()),
                            segment=_artikel_segment(r[2]), sort=(r[0],)))
    elif art == "regel":
        for r in q("SELECT id, article_id, aspect, scope, sensitive_category, quote FROM data_rule"):
            seg = f"regel:{slug(r[2]).replace('-', '_')}-{slug(r[3]).replace('-', '_')}"
            if r[4]:
                seg += "-" + slug(r[4]).replace("-", "_")
            out.append(dict(ziel_id=r[0], eltern_ziel=r[1], schluessel=f"{r[2]}|{r[3]}|{r[4] or ''}",
                            merkmal=r[5] or "",
                            segment=seg, sort=(r[0],)))
    elif art == "angabe":
        for r in q("SELECT ca.id, e.standard, e.name, e.context, ca.esh_key FROM canonical_attribute ca "
                   "LEFT JOIN ech_element e ON e.id = ca.ech_element_id"):
            if r[1]:
                key = angabe_schluessel_ech(r[1], r[2], r[3])
                seg = f"{r[1]}:{r[2]}" + (f":{r[3]}" if r[3] else "")
            elif r[4]:
                key, seg = angabe_schluessel_esh(r[4]), r[4]
            else:
                raise RuntimeError(f"canonical_attribute {r[0]} hat weder eCH-Element noch eSH-Schlüssel")
            # minting order follows the natural key, never the renumbered row id
            out.append(dict(ziel_id=r[0], eltern_ziel=None, schluessel=key, merkmal=None,
                            segment=seg, sort=(key,)))
    else:
        raise ValueError(art)
    if art not in ("feld", "teilfeld"):          # these keep «ord|…» readable (position and type matter)
        for o in out:
            if o["merkmal"] is not None:
                o["merkmal"] = _pruefsumme(o["merkmal"])
    if ARTEN[art]["eltern"]:
        for o in out:
            o["eltern"] = (eltern_karte or {}).get(o["eltern_ziel"])
            if o["eltern"] is None:
                raise RuntimeError(f"{art} {o['ziel_id']}: übergeordnetes Objekt {o['eltern_ziel']} hat keine aktive Kennung")
    else:
        for o in out:
            o["eltern"] = None
    return out


# ---- the loader -------------------------------------------------------------------
def _praefix(art, eltern):
    return {"service": "sh:service:", "formular": "sh:formular:", "gesetz": "sh:gesetz:",
            "angabe": "sh:angabe:"}.get(art) or f"{eltern}:"


def _abgleichen(c, art, objs, datum, stat):
    """Match the current objects of one art against its identifiers and write the
    changes. Returns {ziel_id: kennung} of the active identifiers of this art."""
    cfg = ARTEN[art]
    alt = _rows(c, "SELECT kennung, ziel_id, schluessel, merkmal, status FROM kennung "
                   "WHERE art = ? AND status IN ('aktiv','entfallen') ORDER BY kennung", [art])
    for a in alt:
        a["eltern"] = eltern_von(a["kennung"], art)
    paare = []                                   # (old row, object, how)
    frei_alt = {a["kennung"]: a for a in alt}
    frei_obj = {id(o): o for o in objs}

    def paar(a, o, wie):
        paare.append((a, o, wie))
        del frei_alt[a["kennung"]]
        del frei_obj[id(o)]

    # 1. same parent and same schluessel (active identifiers first, then retired ones)
    gruppen = {}
    for o in objs:
        gruppen.setdefault((o["eltern"], o["schluessel"]), ([], []))[1].append(o)
    for a in alt:
        g = gruppen.get((a["eltern"], a["schluessel"]))
        if g is not None:
            g[0].append(a)
    for key in sorted(gruppen, key=lambda k: (k[0] or "", k[1])):
        alte, neue = gruppen[key]
        neue = sorted(neue, key=lambda o: o["sort"])
        for welle in ("aktiv", "entfallen"):
            kand = [a for a in alte if a["status"] == welle and a["kennung"] in frei_alt]
            offen = lambda: [o for o in neue if id(o) in frei_obj]
            regeln = ((lambda a, o: a["ziel_id"] == o["ziel_id"] and a["merkmal"] == o["merkmal"]),
                      (lambda a, o: a["merkmal"] is not None and a["merkmal"] == o["merkmal"]),
                      (lambda a, o: cfg["stabile_ids"] and a["ziel_id"] == o["ziel_id"]))
            for regel in (regeln if welle == "aktiv" else regeln[1:2]):
                for a in list(kand):
                    if a["kennung"] not in frei_alt:
                        continue
                    treffer = [o for o in offen() if regel(a, o)]
                    gegen = [b for b in kand if b["kennung"] in frei_alt and treffer and regel(b, treffer[0])]
                    if len(treffer) == 1 and len(gegen) == 1:
                        paar(a, treffer[0], "gleich")
            rest_a = [a for a in kand if a["kennung"] in frei_alt]
            if len(rest_a) == 1 and len(offen()) == 1:
                paar(rest_a[0], offen()[0], "gleich")

    # 2. a renamed object keeps its identifier only on unambiguous evidence
    if art != "angabe":
        akt = [a for a in frei_alt.values() if a["status"] == "aktiv" and a["merkmal"] is not None]
        teile_vorher, teile_jetzt = {}, {}
        if art == "teilfeld":
            for a in alt:
                if a["status"] == "aktiv":
                    teile_vorher[a["eltern"]] = teile_vorher.get(a["eltern"], 0) + 1
            for o in objs:
                teile_jetzt[o["eltern"]] = teile_jetzt.get(o["eltern"], 0) + 1
        for a in sorted(akt, key=lambda a: a["kennung"]):
            if a["kennung"] not in frei_alt:
                continue
            def passt(x, o):
                if x["eltern"] != o["eltern"]:
                    return False
                if art == "teilfeld":
                    pos_x, el_x = x["merkmal"].split("|", 1)
                    pos_o, el_o = o["merkmal"].split("|", 1)
                    if pos_x != pos_o:
                        return False
                    if el_x != OHNE:              # it had an element: only the same element
                        return el_x == el_o
                    # an element-less part: only when no position can have shifted (the Datenfeld
                    # still has as many parts) — then the slot is the same part, also when it
                    # got its first element in the same run
                    return teile_vorher.get(x["eltern"]) == teile_jetzt.get(x["eltern"])
                if art == "feld":
                    # never the row id: load_data_fields.py deletes and re-inserts a Formular's
                    # fields, and SQLite hands out the ids of the highest deleted rows again
                    o_x, t_x, el_x, in_x = feld_merkmal(x["merkmal"])
                    o_o, t_o, el_o, in_o = feld_merkmal(o["merkmal"])
                    if el_x is None or (o_x, t_x) != (o_o, t_o):
                        return False
                    if el_x != OHNE:              # it had an element: only the same element
                        return el_x == el_o
                    return el_o == OHNE and in_x != OHNE and in_x == in_o
                if x["merkmal"] != o["merkmal"]:
                    return False
                return x["ziel_id"] == o["ziel_id"] if cfg["stabile_ids"] else True
            treffer = [o for o in frei_obj.values() if passt(a, o)]
            if len(treffer) != 1:
                continue
            gegen = [b for b in frei_alt.values() if b["status"] == "aktiv" and b["merkmal"] is not None
                     and passt(b, treffer[0])]
            if len(gegen) == 1:
                paar(a, treffer[0], "umbenannt")

    # write: first retire, then move every changed target to a negative placeholder
    # and flip all placeholders at once, then insert — so no two active rows name
    # the same target at any moment (should a unique index on the targets be added)
    # 3. identifiers whose object is gone stay, marked «entfallen»
    for a in sorted(frei_alt.values(), key=lambda a: a["kennung"]):
        if a["status"] != "aktiv":
            continue
        c.execute("UPDATE kennung SET status='entfallen', ziel_id=NULL, bis=?, grund=? WHERE kennung=?",
                  [datum, f"Objekt nicht mehr in der Databank (Lauf {datum})", a["kennung"]])
        c.execute("INSERT INTO kennung_verlauf(kennung, datum, ereignis, vorher, nachher) VALUES(?,?,?,?,?)",
                  [a["kennung"], datum, "entfallen", a["schluessel"], None])
        stat["entfallen"] += 1
    karte = {}
    for a, o, wie in sorted(paare, key=lambda p: p[0]["kennung"]):
        k = a["kennung"]
        karte[o["ziel_id"]] = k
        if a["status"] == "entfallen":
            c.execute("UPDATE kennung SET status='aktiv', ziel_id=?, merkmal=?, bis=NULL, grund=NULL "
                      "WHERE kennung=?", [-o["ziel_id"], o["merkmal"], k])
            c.execute("INSERT INTO kennung_verlauf(kennung, datum, ereignis, vorher, nachher) VALUES(?,?,?,?,?)",
                      [k, datum, "reaktiviert", None, o["schluessel"]])
            stat["reaktiviert"] += 1
            continue
        neu_id = o["ziel_id"] if a["ziel_id"] == o["ziel_id"] else -o["ziel_id"]
        if wie == "umbenannt":
            c.execute("UPDATE kennung SET schluessel=?, ziel_id=?, merkmal=? WHERE kennung=?",
                      [o["schluessel"], neu_id, o["merkmal"], k])
            c.execute("INSERT INTO kennung_verlauf(kennung, datum, ereignis, vorher, nachher) VALUES(?,?,?,?,?)",
                      [k, datum, "umbenannt", a["schluessel"], o["schluessel"]])
            stat["umbenannt"] += 1
            continue
        if a["ziel_id"] != o["ziel_id"]:
            stat["umgehaengt"] += 1
        if a["merkmal"] != o["merkmal"]:
            stat["merkmal"] += 1
        if a["ziel_id"] != o["ziel_id"] or a["merkmal"] != o["merkmal"]:
            c.execute("UPDATE kennung SET ziel_id=?, merkmal=? WHERE kennung=?", [neu_id, o["merkmal"], k])
    c.execute("UPDATE kennung SET ziel_id = -ziel_id WHERE art = ? AND ziel_id < 0", [art])

    # 4. new objects get a new identifier (serial within the parent, or the segment)
    vergeben = {r[0] for r in c.execute("SELECT kennung FROM kennung")}
    serial = {}
    if art in ("feld", "teilfeld"):
        wort = "feld" if art == "feld" else "teil"
        rx = re.compile(r"^(.*):" + wort + r":([0-9]+)$")
        for k in vergeben:
            m = rx.match(k)
            if m:
                serial[m.group(1)] = max(serial.get(m.group(1), 0), int(m.group(2)))
    for o in sorted(frei_obj.values(), key=lambda o: (o["eltern"] or "", o["sort"])):
        p = _praefix(art, o["eltern"])
        if o["segment"] is None:
            serial[o["eltern"]] = serial.get(o["eltern"], 0) + 1
            k = f"{o['eltern']}:{wort}:{serial[o['eltern']]}"
        else:
            k, n = p + o["segment"], 1
            while k in vergeben:
                n += 1
                k = f"{p}{o['segment']}~{n}"
        if k in vergeben:
            raise RuntimeError(f"Kennung {k} wäre doppelt vergeben")
        vergeben.add(k)
        c.execute("INSERT INTO kennung(kennung, art, ziel_tabelle, ziel_id, schluessel, merkmal, status, seit) "
                  "VALUES(?,?,?,?,?,?, 'aktiv', ?)",
                  [k, art, cfg["tabelle"], o["ziel_id"], o["schluessel"], o["merkmal"], datum])
        karte[o["ziel_id"]] = k
        stat["neu"] += 1
    return karte


def _abloesungen_anwenden(c, pfad, datum, stat):
    """Reviewed «abgelöst durch» decisions: the old identifier must be «entfallen»,
    the new one active and of the same art, and the reason must be stated."""
    if not pfad or not os.path.exists(pfad):
        return
    with open(pfad, encoding="utf-8") as fh:
        liste = json.load(fh)
    for i, e in enumerate(liste):
        alt, neu, grund = e.get("alt"), e.get("neu"), (e.get("grund") or "").strip()
        ra = c.execute("SELECT art, status, abgeloest_durch FROM kennung WHERE kennung=?", [alt]).fetchone()
        rn = c.execute("SELECT art, status FROM kennung WHERE kennung=?", [neu]).fetchone()
        if not ra or not rn or not grund:
            raise RuntimeError(f"Ablösung {i}: alt/neu unbekannt oder Grund fehlt ({alt} -> {neu})")
        if ra[1] == "abgeloest":
            if ra[2] != neu:
                raise RuntimeError(f"Ablösung {i}: {alt} ist bereits durch {ra[2]} abgelöst")
            continue                         # already applied (idempotent)
        if ra[1] != "entfallen" or rn[1] != "aktiv" or ra[0] != rn[0] or alt == neu:
            raise RuntimeError(f"Ablösung {i}: {alt} muss entfallen, {neu} aktiv und von derselben Art sein")
        c.execute("UPDATE kennung SET status='abgeloest', abgeloest_durch=?, grund=? WHERE kennung=?",
                  [neu, grund, alt])
        c.execute("INSERT INTO kennung_verlauf(kennung, datum, ereignis, vorher, nachher) VALUES(?,?,?,?,?)",
                  [alt, datum, "abgeloest", None, neu])
        stat["abgeloest"] += 1


def _ddl_stand(c):
    return sorted(r[0] or "" for r in c.execute("SELECT sql FROM sqlite_master WHERE name LIKE '%kennung%'"))


def abgleich(c, datum, abloesungen=ABLOESUNGEN):
    """Bring the identifiers in line with the database (in a transaction on c)."""
    vorher = _ddl_stand(c)
    c.executescript(DDL)
    stat = {k: 0 for k in ("neu", "entfallen", "umbenannt", "reaktiviert", "umgehaengt", "merkmal", "abgeloest",
                           "schema")}
    stat["schema"] = int(_ddl_stand(c) != vorher)
    karten = {}
    for art in REIHENFOLGE:
        eltern = ARTEN[art]["eltern"]
        objs = objekte(c, art, karten.get(eltern))
        karten[art] = _abgleichen(c, art, objs, datum, stat)
    _abloesungen_anwenden(c, abloesungen, datum, stat)
    return stat, karten


# ---- the gates ----------------------------------------------------------------------
def _has(conn, table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [table]).fetchone())


_VEROEFF_CACHE = {}


def veroeffentlichte(pfad=None):
    """The identifiers the published data_export.json carries (active and retired
    ones); an empty set when there is no such file yet."""
    pfad = pfad or VEROEFFENTLICHT
    try:
        st = os.stat(pfad)
    except OSError:
        return set()
    key = (pfad, st.st_mtime_ns, st.st_size)
    if key not in _VEROEFF_CACHE:
        with open(pfad, encoding="utf-8") as fh:
            _VEROEFF_CACHE.clear()
            _VEROEFF_CACHE[key] = set(_KENNUNG_IM_TEXT.findall(fh.read()))
    return _VEROEFF_CACHE[key]


def pruefen(conn):
    """Invariants of the identifier table that hold at any time, also while another
    loader has changed data and kennungen.py has not run yet (scripts/validate_db.py
    calls this on every staging copy). Without the table it only checks that no
    identifier was published yet; with it, also that every published one is held."""
    veroeff = veroeffentlichte()
    if not _has(conn, "kennung"):
        return ([f"Tabelle kennung fehlt, aber das veröffentlichte data_export.json trägt {len(veroeff)} Kennungen "
                 "— die Kennungen wären verloren und würden neu vergeben; citygov.db mit der Tabelle wiederherstellen"]
                if veroeff else [])
    err = []
    fehlt = sorted(veroeff - {r[0] for r in conn.execute("SELECT kennung FROM kennung")})
    if fehlt:
        err.append(f"{len(fehlt)} veröffentlichte Kennungen fehlen in der Tabelle kennung (z. B. {fehlt[:3]}) — "
                   "eine verlorene Kennung darf nie neu vergeben werden; citygov.db mit der Tabelle wiederherstellen")
    count = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    fehlt = [t for t in TRIGGER if t not in have]
    if fehlt:
        err.append(f"kennung: Trigger fehlen ({', '.join(fehlt)}) — die Tabelle schützt sich nicht selbst")
    rows = _rows(conn, "SELECT * FROM kennung")
    by_k = {r["kennung"]: r for r in rows}
    bad = {k: [] for k in ("format", "tabelle", "status", "eltern", "abl", "kette")}
    for r in rows:
        art, k = r["art"], r["kennung"]
        cfg = ARTEN.get(art)
        m = FORMAT[art].match(k) if cfg else None
        if not cfg or not m:
            bad["format"].append(k); continue
        if r["ziel_tabelle"] != cfg["tabelle"]:
            bad["tabelle"].append(k)
        st = r["status"]
        if (st == "aktiv") != (r["ziel_id"] is not None) or (st == "aktiv") != (r["bis"] is None) \
                or (st == "abgeloest") != (r["abgeloest_durch"] is not None) or st not in ("aktiv", "abgeloest", "entfallen"):
            bad["status"].append(k)
        pa = cfg["eltern"]
        if pa:
            e = by_k.get(m.group("eltern"))
            if not e or e["art"] != pa or (st == "aktiv" and e["status"] != "aktiv"):
                bad["eltern"].append(k)
        elif not k.startswith(_praefix(art, None)):
            bad["eltern"].append(k)
        if r["abgeloest_durch"]:
            n = by_k.get(r["abgeloest_durch"])
            if not n or n["art"] != art or n["kennung"] == k:
                bad["abl"].append(k)
            else:                                    # no cycle along «abgelöst durch»
                seen, cur = {k}, n
                while cur and cur["abgeloest_durch"]:
                    if cur["kennung"] in seen:
                        bad["kette"].append(k); break
                    seen.add(cur["kennung"]); cur = by_k.get(cur["abgeloest_durch"])
    for key, text in (("format", "haben kein gültiges Format für ihre Art"),
                      ("tabelle", "zeigen auf die falsche Zieltabelle"),
                      ("status", "verletzen die Statusregeln (aktiv ⇔ Ziel, abgelöst ⇔ Nachfolger, bis)"),
                      ("eltern", "passen nicht zu ihrer Eltern-Kennung (fehlt, andere Art, aktiv unter nicht aktiv)"),
                      ("abl", "nennen einen Nachfolger, der fehlt, sich selbst ist oder eine andere Art hat"),
                      ("kette", "liegen auf einem Kreis von Ablösungen")):
        if bad[key]:
            err.append(f"{len(bad[key])} Kennungen {text}: {bad[key][:3]}")
    n = count("SELECT COUNT(*) FROM (SELECT ziel_tabelle, ziel_id FROM kennung WHERE status='aktiv' "
              "GROUP BY 1, 2 HAVING COUNT(*) > 1)")
    if n:
        err.append(f"{n} Objekte tragen mehr als eine aktive Kennung")
    for art in EINDEUTIG:
        n = count("SELECT COUNT(*) FROM (SELECT schluessel FROM kennung WHERE art=? AND status='aktiv' "
                  "GROUP BY 1 HAVING COUNT(*) > 1)", art)
        if n:
            err.append(f"{n} Schlüssel der Art {art} tragen mehr als eine aktive Kennung")
    if _has(conn, "kennung_verlauf"):
        n = count("SELECT COUNT(*) FROM kennung_verlauf v WHERE NOT EXISTS (SELECT 1 FROM kennung k "
                  "WHERE k.kennung = v.kennung)")
        if n:
            err.append(f"{n} Verlaufseinträge nennen eine unbekannte Kennung")
    return err


def pruefen_aktuell(conn):
    """pruefen() plus: every current object has exactly one active identifier, and
    every active identifier points at an existing object with the recorded natural
    key and parent. True right after kennungen.py; a stale table says which step."""
    if not _has(conn, "kennung"):
        return ["Tabelle kennung fehlt — scripts/kennungen.py ausführen"]
    err = pruefen(conn)
    karten = {}
    for art in REIHENFOLGE:
        cfg = ARTEN[art]
        akt = {r[0]: (r[0], r[1], eltern_von(r[1], art), r[2]) for r in conn.execute(
            "SELECT ziel_id, kennung, schluessel FROM kennung WHERE art=? AND status='aktiv'", [art])}
        try:
            objs = objekte(conn, art, karten.get(cfg["eltern"]))
        except RuntimeError as ex:
            err.append(f"kennung {art}: {ex} — scripts/kennungen.py ausführen")
            karten[art] = {z: r[1] for z, r in akt.items()}
            continue
        ohne = [o["ziel_id"] for o in objs if o["ziel_id"] not in akt]
        falsch = [akt[o["ziel_id"]][1] for o in objs if o["ziel_id"] in akt
                  and (akt[o["ziel_id"]][3] != o["schluessel"] or akt[o["ziel_id"]][2] != o["eltern"])]
        weg = set(akt) - {o["ziel_id"] for o in objs}
        if ohne:
            err.append(f"{len(ohne)} {cfg['tabelle']}-Zeilen ohne aktive Kennung (ids {ohne[:5]}) — scripts/kennungen.py ausführen")
        if falsch:
            err.append(f"{len(falsch)} aktive Kennungen der Art {art} zeigen auf ein Objekt mit anderem Schlüssel "
                       f"oder anderer Eltern-Kennung: {falsch[:3]}")
        if weg:
            err.append(f"{len(weg)} aktive Kennungen der Art {art} zeigen auf eine fehlende {cfg['tabelle']}-Zeile")
        karten[art] = {z: r[1] for z, r in akt.items()}
    return err


# ---- the resolver -------------------------------------------------------------------
def uri(kennung):
    """The resolvable address of an identifier, once the owner has set BASIS_URI."""
    return (BASIS_URI.rstrip("/") + "/" + kennung) if BASIS_URI else None


def aufloesen(conn, kennung):
    """What an identifier names today: its row, the chain of «abgelöst durch» to the
    current identifier, and the target row (checked against the natural key; a
    stale ziel_id of an Angabe is resolved again by its natural key). None if the
    identifier was never issued."""
    r = _rows(conn, "SELECT * FROM kennung WHERE kennung=?", [kennung])
    if not r:
        return None
    out = dict(r[0])
    kette, cur = [kennung], dict(r[0])
    while cur["status"] == "abgeloest":
        cur = _rows(conn, "SELECT * FROM kennung WHERE kennung=?", [cur["abgeloest_durch"]])[0]
        if cur["kennung"] in kette:
            raise RuntimeError(f"Kreis in den Ablösungen bei {cur['kennung']}")
        kette.append(cur["kennung"])
    out["kette"] = kette
    out["aktuell"] = cur["kennung"] if cur["status"] == "aktiv" else None
    out["uri"] = uri(kennung)
    out["ziel"] = None
    if cur["status"] == "aktiv":
        tab = ARTEN[cur["art"]]["tabelle"]
        row = (_rows(conn, f"SELECT * FROM {tab} WHERE id=?", [cur["ziel_id"]]) or [None])[0]
        if cur["art"] in _EINZELN and _EINZELN[cur["art"]][0](conn, cur["ziel_id"]) != cur["schluessel"]:
            # stale ziel_id (e.g. canonical_attribute renumbered since the last run):
            # resolve again by the natural key, never by the number
            hit = _EINZELN[cur["art"]][1](conn, cur["schluessel"])
            row = (_rows(conn, f"SELECT * FROM {tab} WHERE id=?", [hit[0]]) or [None])[0] if len(hit) == 1 else None
            out["hinweis"] = ("ziel_id veraltet, über den Schlüssel neu aufgelöst — scripts/kennungen.py ausführen"
                              if row is not None else "Objekt nicht gefunden — scripts/kennungen.py ausführen")
        out["ziel"] = row
    return out


def _angabe_von(conn, ziel_id):
    r = conn.execute("SELECT e.standard, e.name, e.context, ca.esh_key FROM canonical_attribute ca "
                     "LEFT JOIN ech_element e ON e.id = ca.ech_element_id WHERE ca.id=?", [ziel_id]).fetchone()
    if r is None:
        return None
    return angabe_schluessel_ech(r[0], r[1], r[2]) if r[0] else angabe_schluessel_esh(r[3])


def _angabe_suchen(conn, schluessel):
    teile = schluessel.split("|")
    if teile[0] == "ech":
        return [r[0] for r in conn.execute(
            "SELECT ca.id FROM canonical_attribute ca JOIN ech_element e ON e.id = ca.ech_element_id "
            "WHERE e.standard=? AND e.name=? AND COALESCE(e.context, '')=?", teile[1:4])]
    return [r[0] for r in conn.execute("SELECT id FROM canonical_attribute WHERE esh_key=?", [teile[1]])]


def _gesetz_von(conn, ziel_id):
    r = _rows(conn, "SELECT id, slug, jurisdiction_level, sr_number, cantonal_ref FROM law WHERE id=?", [ziel_id])
    return _gesetz(r[0])[0] if r else None


def _gesetz_suchen(conn, schluessel):
    return [r["id"] for r in _rows(conn, "SELECT id, slug, jurisdiction_level, sr_number, cantonal_ref FROM law")
            if _gesetz(r)[0] == schluessel]


# root arts whose target can be checked and found again by its natural key alone
_EINZELN = {
    "angabe":   (_angabe_von, _angabe_suchen),
    "service":  (lambda c, i: (c.execute("SELECT slug FROM service WHERE id=?", [i]).fetchone() or [None])[0],
                 lambda c, k: [r[0] for r in c.execute("SELECT id FROM service WHERE slug=?", [k])]),
    "formular": (lambda c, i: (c.execute("SELECT slug FROM form WHERE id=?", [i]).fetchone() or [None])[0],
                 lambda c, k: [r[0] for r in c.execute("SELECT id FROM form WHERE slug=?", [k])]),
    "gesetz":   (_gesetz_von, _gesetz_suchen),
}


def nicht_aktiv(conn):
    """Every identifier that is no longer active, for the published lookup: what
    became of it (status, since when, why, the successor). Sorted by identifier."""
    return [{"kennung": r[0], "art": r[1], "status": r[2], "bis": r[3], "grund": r[4], "abgeloest_durch": r[5]}
            for r in conn.execute("SELECT kennung, art, status, bis, grund, abgeloest_durch FROM kennung "
                                  "WHERE status != 'aktiv' ORDER BY kennung")]


def kennungen_block(conn):
    """The block «kennungen» of data_export.json (meta.kennungen of citygov_llm.json)."""
    return {"schema": "sh:service:… · sh:formular:…[:feld:<n>[:teil:<m>]] · sh:angabe:… · "
                      "sh:gesetz:…[:art-…[:regel:…]]",
            "basis_uri": BASIS_URI,
            "hinweis": "Kennungen sind dauerhaft: keine wird je gelöscht, neu vergeben oder auf ein anderes Objekt "
                       "umgehängt. Jede Kennung, die nicht mehr aktiv ist, steht hier mit Status (entfallen: das "
                       "Objekt gibt es nicht mehr; abgeloest: geprüfter Nachfolger), Datum, Grund und Nachfolger.",
            "nicht_aktiv": nicht_aktiv(conn)}


def kennungen_aktiv(conn, art):
    """{ziel_id: kennung} of the active identifiers of one art."""
    return {z: k for z, k in conn.execute("SELECT ziel_id, kennung FROM kennung WHERE art=? AND status='aktiv'", [art])}


def angabe_karte(conn):
    """{natural key: kennung} of the active Angabe identifiers — what the Datentresor
    and the exports use instead of canonical_attribute.id."""
    return {s: k for s, k in conn.execute("SELECT schluessel, kennung FROM kennung WHERE art='angabe' AND status='aktiv'")}


def angabe_nach_attribut(conn):
    """{canonical_attribute.id: kennung}, checked: every row of canonical_attribute
    must have an active identifier with its own natural key (else RuntimeError —
    run scripts/kennungen.py after init_register.py)."""
    ak = angabe_karte(conn)
    out, fehlt = {}, []
    for o in objekte(conn, "angabe"):
        k = ak.get(o["schluessel"])
        if k is None:
            fehlt.append(o["schluessel"])
        out[o["ziel_id"]] = k
    if fehlt:
        raise RuntimeError(f"{len(fehlt)} kanonische Angaben ohne Kennung (z. B. {fehlt[0]}) — "
                           "zuerst scripts/kennungen.py ausführen")
    return out


# ---- the exports carry the identifiers ---------------------------------------------
class _Index:
    """Everything the export enrichment needs, read once from the database."""

    def __init__(self, conn):
        q = lambda sql, *a: conn.execute(sql, a).fetchall()
        self.k = {art: kennungen_aktiv(conn, art) for art in REIHENFOLGE}
        self.angabe = angabe_karte(conn)
        self.einheiten = {}           # data_field id -> [unit]; unit = (art, ziel_id, name, angabe-key or None, ech_element_id)
        subs = {}
        for sid, did, name, std, en, ctx, eid, esc, esl in q(
                "SELECT s.id, s.data_field_id, s.name, e.standard, e.name, e.context, s.ech_element_id, "
                "s.esh_code, s.esh_element FROM data_subfield s LEFT JOIN ech_element e ON e.id = s.ech_element_id "
                "ORDER BY s.data_field_id, s.ord"):
            subs.setdefault(did, []).append(("teilfeld", sid, name, self._ak(std, en, ctx, esc, esl), eid))
        self.felder = {}
        for did, fid, name, std, en, ctx, eid, esc, esl in q(
                "SELECT d.id, d.form_id, d.name, e.standard, e.name, e.context, d.ech_element_id, d.esh_code, "
                "d.esh_element FROM data_field d LEFT JOIN ech_element e ON e.id = d.ech_element_id "
                "ORDER BY d.form_id, d.ord"):
            self.felder.setdefault(fid, []).append(did)
            self.einheiten[did] = subs.get(did) or [("feld", did, name, self._ak(std, en, ctx, esc, esl), eid)]
        self.teil_namen = {did: [u[2] for u in us] for did, us in subs.items()}
        self.feld_name = dict(q("SELECT id, name FROM data_field"))
        self.element = {r[0]: (r[1], r[2], r[3]) for r in q("SELECT id, standard, name, context FROM ech_element")}
        self.zitate = {}              # data_field id -> [(article id, article_no, law identity tuple)]
        for did, aid, no, lid, title, short, sr, ref in q(
                "SELECT b.data_field_id, a.id, a.article_no, l.id, l.title, l.short_title, l.sr_number, "
                "l.cantonal_ref FROM data_field_legal_basis b JOIN article a ON a.id = b.article_id "
                "JOIN law l ON l.id = a.law_id"):
            self.zitate.setdefault(did, []).append((aid, no, lid, title, short, sr, ref))
        self.artikel = {}             # (law id, article_no, heading) -> article id
        for aid, lid, no, head in q("SELECT id, law_id, article_no, heading FROM article"):
            self.artikel[(lid, no, head or "")] = aid
        self.gesetze = [dict(zip(("id", "title", "short_title", "sr_number", "cantonal_ref"), r))
                        for r in q("SELECT id, title, short_title, sr_number, cantonal_ref FROM law")]
        self.regeln = {}              # (article id, aspect, scope, category) -> [(rule id, quote)]
        for rid, aid, asp, sc, cat, quote in q("SELECT id, article_id, aspect, scope, sensitive_category, quote FROM data_rule"):
            self.regeln.setdefault((aid, asp, sc, cat), []).append((rid, quote))

    def _ak(self, std, en, ctx, esc, esl):
        if std:
            return angabe_schluessel_ech(std, en, ctx)
        if esc and esl:
            return angabe_schluessel_esh(f"{esc}:{esl}")
        return None

    def kennung(self, art, ziel_id):
        k = self.k[art].get(ziel_id)
        if k is None:
            raise RuntimeError(f"{ARTEN[art]['tabelle']} {ziel_id} hat keine aktive Kennung — "
                               "zuerst scripts/kennungen.py ausführen")
        return k

    def angabe_kennung(self, key):
        if key is None:
            return None
        k = self.angabe.get(key)
        if k is None:
            raise RuntimeError(f"Angabe {key} hat keine aktive Kennung — zuerst scripts/kennungen.py ausführen")
        return k

    def gesetz_ids(self, title=None, short=None, sr=None, ref=None):
        """Law rows that match the identity an export entry carries."""
        hits = [g["id"] for g in self.gesetze
                if (title is None or g["title"] == title) and (short is None or g["short_title"] == short)
                and (sr is None or g["sr_number"] == sr) and (ref is None or g["cantonal_ref"] == ref)]
        return hits

    def regel(self, aid, asp, sc, cat, quote):
        cand = self.regeln.get((aid, asp, sc, cat)) or []
        if len(cand) > 1:
            cand = [c for c in cand if c[1] == quote]
        if len(cand) != 1:
            raise RuntimeError(f"Regel zu Artikel {aid} ({asp}/{sc}/{cat}) nicht eindeutig: {len(cand)} Kandidaten")
        return self.kennung("regel", cand[0][0])


def _setzen(obj, schluessel, wert, nach="id"):
    """Put obj[schluessel] = wert right after the key `nach` (in place, so objects
    shared between two exports stay one object)."""
    items = [(k, v) for k, v in obj.items() if k != schluessel]
    pos = next((i + 1 for i, (k, _) in enumerate(items) if k == nach), 0)
    items.insert(pos, (schluessel, wert))
    obj.clear()
    obj.update(items)


def _teile(ix, did, subfields, wo):
    """Pair an exported subfield list with the Teilfelder of data_field did (same
    length, same names, in ord order) — or None when the field has none."""
    us = ix.einheiten.get(did) or []
    dicts = [s for s in (subfields or []) if isinstance(s, dict)]
    if not us or us[0][0] != "teilfeld":
        if dicts:
            raise RuntimeError(f"{wo}: Datenfeld {did} trägt Teilfelder, die Datenbank keine")
        return None
    if [s.get("name") for s in dicts] != [u[2] for u in us]:
        raise RuntimeError(f"{wo}: Teilfelder von Datenfeld {did} passen nicht zur Datenbank")
    return list(zip(dicts, us))


def _feld(ix, d, wo, mit_formular=False):
    """kennung (+ angabe_kennung for a unit) on an exported Datenfeld and its parts."""
    did = d["id"]
    _setzen(d, "kennung", ix.kennung("feld", did))
    if mit_formular:
        _setzen(d, "formular_kennung", ix.kennung("formular", d["form_id"]), nach="form_id")
    paare = _teile(ix, did, d.get("subfields"), wo)
    if paare is None:
        _setzen(d, "angabe_kennung", ix.angabe_kennung(ix.einheiten[did][0][3]), nach="kennung")
    else:
        _setzen(d, "angabe_kennung", None, nach="kennung")    # a composite is no unit
        for s, u in paare:
            _setzen(s, "kennung", ix.kennung("teilfeld", u[1]), nach="name")
            _setzen(s, "angabe_kennung", ix.angabe_kennung(u[3]), nach="kennung")


def _zitate_llm(ix, d, wo):
    """artikel_kennung on legal_basis entries that carry no article id: resolved
    among the field's own citations by article number and law identity."""
    for lb in d.get("legal_basis") or []:
        cand = {z[0] for z in ix.zitate.get(d["id"], []) if z[1] == lb.get("article_no")
                and z[3] == lb.get("law_title") and z[4] == lb.get("law_short")
                and z[5] == lb.get("sr_number") and z[6] == lb.get("cantonal_ref")}
        if len(cand) != 1:
            raise RuntimeError(f"{wo}: Zitat {lb.get('article_no')} von Datenfeld {d['id']} nicht eindeutig ({len(cand)})")
        _setzen(lb, "artikel_kennung", ix.kennung("artikel", cand.pop()), nach="article_no")


def _regel_llm(ix, r, wo):
    lids = ix.gesetz_ids(title=r.get("law_title"), short=r.get("law_short"), sr=r.get("sr_number"))
    aids = {ix.artikel.get((lid, r.get("article_no"), r.get("heading") or "")) for lid in lids} - {None}
    if len(aids) != 1:
        raise RuntimeError(f"{wo}: Artikel {r.get('article_no')} ({r.get('law_short')}) nicht eindeutig ({len(aids)})")
    aid = aids.pop()
    _setzen(r, "kennung", ix.regel(aid, r["aspect"], r["scope"], r.get("sensitive_category"), r.get("quote")), nach=None)
    _setzen(r, "artikel_kennung", ix.kennung("artikel", aid), nach="kennung")


def _punkte(ix, fid, mit_element):
    """The units of a Formular in export order (fields by ord, parts by ord)."""
    for did in ix.felder.get(fid, []):
        for u in ix.einheiten[did]:
            if not mit_element or u[4] is not None:
                yield did, u


def anreichern(name, doc, conn):
    """Add the permanent identifiers to an export object right before it is
    serialised (one call per published file; the object is changed in place and
    returned): kennung next to the id of every service, Formular, Datenfeld,
    Teilfeld, law, article, rule and canonical attribute, and in data_export.json
    also on every law and article of the change-impact index (wirkung);
    formular_kennung, artikel_kennung (citations, rules, the article a decision
    rests on) and angabe_kennung next to every reference. Every reference is
    resolved exactly or the export stops."""
    ix = _Index(conn)
    if name == "data_export.json":
        for s in doc.get("services") or []:
            _setzen(s, "kennung", ix.kennung("service", s["id"]))
        for f in doc.get("forms") or []:
            _setzen(f, "kennung", ix.kennung("formular", f["id"]))
            o = f.get("outcome")              # the article a decision rests on (citygov_llm.json copies it)
            if o and o.get("article_id") is not None:
                _setzen(o, "artikel_kennung", ix.kennung("artikel", o["article_id"]), nach="article_id")
            for d in f.get("data_fields") or []:
                _feld(ix, d, name)
                for lb in d.get("legal_basis") or []:
                    aid = ix.artikel.get((lb.get("law_id"), lb.get("article_no"), lb.get("article_heading") or ""))
                    if aid is None:
                        raise RuntimeError(f"{name}: Zitat {lb.get('article_no')} (Gesetz {lb.get('law_id')}) unbekannt")
                    if "article_id" in lb and lb["article_id"] != aid:
                        raise RuntimeError(f"{name}: Zitat {lb.get('article_no')} von Datenfeld {d['id']}: article_id "
                                           f"{lb['article_id']} ≠ Artikel {aid} nach Gesetz, Nummer und Titel")
                    _setzen(lb, "artikel_kennung", ix.kennung("artikel", aid), nach="article_no")
        for l in doc.get("laws") or []:
            _setzen(l, "kennung", ix.kennung("gesetz", l["id"]))
            for a in l.get("articles") or []:
                _setzen(a, "kennung", ix.kennung("artikel", a["id"]))
        for r in doc.get("datenhandhabung") or []:
            aid = ix.artikel.get((r.get("law_id"), r.get("article_no"), r.get("heading") or ""))
            if aid is None:
                raise RuntimeError(f"{name}: Regel zu {r.get('article_no')} (Gesetz {r.get('law_id')}) ohne Artikel")
            _setzen(r, "kennung", ix.regel(aid, r["aspect"], r["scope"], r.get("sensitive_category"), r.get("quote")),
                    nach=None)
            _setzen(r, "artikel_kennung", ix.kennung("artikel", aid), nach="kennung")
        # the change-impact index (scripts/wirkung.py): every law and article it lists
        for g in (doc.get("wirkung") or {}).get("gesetze") or []:
            _setzen(g, "kennung", ix.kennung("gesetz", g["id"]))
            for a in g.get("artikel") or []:
                _setzen(a, "kennung", ix.kennung("artikel", a["id"]))
        attr = angabe_nach_attribut(conn)
        for a in doc.get("attribut_katalog") or []:
            _setzen(a, "kennung", attr[a["id"]])
        for b in doc.get("begriffe") or []:
            e = ix.element.get(b.get("element_id"))
            _setzen(b, "angabe_kennung", ix.angabe.get(angabe_schluessel_ech(*e)) if e else None, nach="element_id")
        doc["kennungen"] = kennungen_block(conn)
    elif name == "citygov_llm.json":
        for s in doc.get("services") or []:
            _setzen(s, "kennung", ix.kennung("service", s["id"]))
            for f in s.get("forms") or []:
                _setzen(f, "kennung", ix.kennung("formular", f["id"]))
                for d in f.get("data_fields") or []:
                    _feld(ix, d, name)
                    _zitate_llm(ix, d, name)
        for r in doc.get("datenhandhabung") or []:
            _regel_llm(ix, r, name)
        doc.setdefault("meta", {})["kennungen"] = kennungen_block(conn)
    elif name == "citygov_datafields.jsonl":
        for d in doc:
            _feld(ix, d, name, mit_formular=True)
            _zitate_llm(ix, d, name)
    elif name == "citygov_datarules.jsonl":
        for r in doc:
            _regel_llm(ix, r, name)
    elif name == "citygov_verzeichnis.json":
        for v in doc.get("verzeichnis") or []:
            _setzen(v, "formular_kennung", ix.kennung("formular", v["form_id"]), nach="form_id")
    elif name == "citygov_prefill.json":
        fk = {}
        for key, pts in (doc.get("formulare") or {}).items():
            fid = int(key)
            fk[key] = ix.kennung("formular", fid)
            units = list(_punkte(ix, fid, mit_element=True))
            if len(units) != len(pts):
                raise RuntimeError(f"{name}: Formular {fid} hat {len(pts)} Punkte, die Datenbank {len(units)} Einheiten")
            for p, (did, u) in zip(pts, units):
                label = ix.feld_name[did] + ("›" + u[2] if u[0] == "teilfeld" else "")
                if p.get("feld") != label:
                    raise RuntimeError(f"{name}: Punkt {p.get('feld')!r} ≠ Einheit {label!r} (Formular {fid})")
                _setzen(p, "kennung", ix.kennung(u[0], u[1]), nach=None)
                _setzen(p, "angabe_kennung", ix.angabe_kennung(u[3]), nach="kennung")
        meta = doc.setdefault("meta", {})
        meta["formular_kennung"] = fk
    elif name == "citygov_ech_schemas.json":
        for f in doc.get("formulare") or []:
            fid = f["form_id"]
            _setzen(f, "formular_kennung", ix.kennung("formular", fid), nach="form_id")
            baum, unmapped = {}, []
            for did, u in _punkte(ix, fid, mit_element=False):
                if u[4] is None:
                    unmapped.append(u)
                else:
                    std, el, ctx = ix.element[u[4]]
                    baum.setdefault(std, {}).setdefault(ctx or "(root)", []).append((u, el))
            ech = f.get("ech") or {}
            if [(std, list(c)) for std, c in ech.items()] != [(std, list(c)) for std, c in baum.items()]:
                raise RuntimeError(f"{name}: Gliederung der eCH-Punkte von Formular {fid} passt nicht zur Datenbank")
            for std, ctxs in ech.items():
                for ctx, pts in ctxs.items():
                    if len(pts) != len(baum[std][ctx]):
                        raise RuntimeError(f"{name}: eCH-Punkte von Formular {fid} ({std} {ctx}) passen nicht")
                    for p, (u, el) in zip(pts, baum[std][ctx]):
                        if p.get("feld") != u[2] or p.get("element") != el:
                            raise RuntimeError(f"{name}: Punkt {p.get('feld')!r} ≠ {u[2]!r} (Formular {fid})")
                        _setzen(p, "kennung", ix.kennung(u[0], u[1]), nach="feld")
                        _setzen(p, "angabe_kennung", ix.angabe_kennung(u[3]), nach="kennung")
            uo = f.get("ohne_standard") or []
            if len(uo) != len(unmapped):
                raise RuntimeError(f"{name}: Lücken von Formular {fid} passen nicht zur Datenbank")
            for p, u in zip(uo, unmapped):
                if p.get("feld") != u[2]:
                    raise RuntimeError(f"{name}: Lücke {p.get('feld')!r} ≠ {u[2]!r} (Formular {fid})")
                _setzen(p, "kennung", ix.kennung(u[0], u[1]), nach="feld")
    else:
        raise ValueError(f"unbekannter Export {name}")
    return doc


# ---- entry point ----------------------------------------------------------------------
def main(argv):
    from validate_db import validate
    datum, abl = date.today().isoformat(), ABLOESUNGEN
    if "--aufloesen" in argv:
        k = argv[argv.index("--aufloesen") + 1]
        c = connect(DB_PATH)
        r = aufloesen(c, k)
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str) if r else f"{k}: nie vergeben")
        return 0 if r else 1
    if "--pruefen" in argv:                   # read-only: the end-of-build check
        c = connect(DB_PATH)
        errs = pruefen_aktuell(c)
        n = c.execute("SELECT COUNT(*) FROM kennung WHERE status='aktiv'").fetchone()[0] if not errs else 0
        c.close()
        if errs:
            print("ABBRUCH Kennungen:", *errs[:8], sep="\n  ")
            return 1
        print(f"Kennungen geprüft: {n} aktiv, jedes Objekt hat genau eine, jede nennt ihr Objekt")
        return 0
    if "--datum" in argv:
        datum = argv[argv.index("--datum") + 1]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", datum):
            sys.exit("ABBRUCH: --datum JJJJ-MM-TT")
    if "--abloesungen" in argv:
        abl = argv[argv.index("--abloesungen") + 1]
    # never mint into a lost registry: a missing or empty table is a first issue only on
    # purpose, and never once identifiers are published
    c0 = connect(DB_PATH)
    leer = not _has(c0, "kennung") or not c0.execute("SELECT COUNT(*) FROM kennung").fetchone()[0]
    c0.close()
    if leer:
        veroeff = veroeffentlichte()
        if veroeff:
            sys.exit(f"ABBRUCH kennungen.py — nichts geschrieben: die Tabelle kennung fehlt oder ist leer, das "
                     f"veröffentlichte data_export.json trägt aber {len(veroeff)} Kennungen. Neu vergeben hiesse, "
                     "dieselben Zeichenketten anderen Objekten zu geben — citygov.db mit der Tabelle wiederherstellen.")
        if "--erstausgabe" not in argv:
            sys.exit("ABBRUCH kennungen.py — nichts geschrieben: die Tabelle kennung fehlt oder ist leer. Die erste "
                     "Vergabe geschieht nur ausdrücklich: python3 scripts/kennungen.py --erstausgabe")
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    try:
        stat, karten = abgleich(c, datum, abl)
        c.commit()
        errs = list(dict.fromkeys(validate(c) + pruefen_aktuell(c)))
    except (RuntimeError, sqlite3.DatabaseError) as ex:
        c.close(); os.remove(st)
        sys.exit(f"ABBRUCH kennungen.py — nichts geschrieben: {ex}")
    n_akt = {art: len(karten[art]) for art in REIHENFOLGE}
    n_alle = dict(c.execute("SELECT status, COUNT(*) FROM kennung GROUP BY 1").fetchall())
    c.close()
    if errs:
        os.remove(st)
        print("ABBRUCH kennungen.py — nichts geschrieben:", *errs[:8], sep="\n  ")
        return 1
    geaendert = any(stat.values())
    if not geaendert:
        os.remove(st)
    else:
        os.replace(st, DB_PATH)
    print(f"Kennungen: {sum(n_akt.values())} aktiv (" + ", ".join(f"{a} {n_akt[a]}" for a in REIHENFOLGE) + ")"
          + f"; entfallen {n_alle.get('entfallen', 0)}, abgelöst {n_alle.get('abgeloest', 0)}")
    if geaendert:
        print("  geändert: " + ", ".join(f"{k} {v}" for k, v in stat.items() if v)
              + " — geschrieben" + (f" (Vergabedatum {datum})" if stat["neu"] else ""))
    else:
        print("  keine Änderung — nichts geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
