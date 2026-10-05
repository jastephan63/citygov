#!/usr/bin/env python3
"""The contract of the published exports: a semantic version per export, a JSON
Schema per export under schema/, and a list of changes in exportvertrag.json.

The seven published files (data_export.json, citygov_llm.json,
citygov_datafields.jsonl, citygov_datarules.jsonl, citygov_prefill.json,
citygov_verzeichnis.json, citygov_ech_schemas.json) each get

  * a version MAJOR.MINOR.PATCH, raised by the build itself:
      MAJOR  a REQUIRED key path disappeared, a type changed (other than null), or an
             object turned into a map or back — a reader of the old file can break;
             also a reviewed note in quellen/exportvertrag_hinweise.json, e.g. that a
             key kept its name but changed its meaning ([{"id", "export", "stufe":
             major|minor|patch, "text"}]; applied once per id, optional file)
      MINOR  a key path was added, an OPTIONAL one disappeared (a reader of the old
             schema already handles its absence), may now be null or no longer is,
             or became optional or required
      PATCH  same structure, but a count moved (items of an array or map, lines), or
             only the schema's wording changed (e.g. a pattern for identifiers)
    Counts leave out the append-only history (data_export.json $.verlauf: one entry
    per build day), so a new day with unchanged data moves no count.
    The JSON files carry it in meta.vertrag (data_export.json: vertrag) as
    {version, schema, aenderungen}; the two JSON-lines files have no header line,
    so their version stands only in exportvertrag.json (one line = one record).
  * a JSON Schema (draft 2020-12) under schema/, derived from the file as built:
    every key path with its JSON types, which keys every object carries, and no
    other keys (additionalProperties false); a permanent identifier (key «kennung»
    or «…_kennung») carries the pattern of its scheme. Objects keyed by data (form
    ids, eCH codes, type names, states and their counts) are maps (KARTEN, plus any
    key that is not an identifier or is an eCH/eSH code): a state that appears or
    disappears is a moved count, not a new or removed key path. A part of the
    structure that this build did not observe (an array that is empty everywhere)
    keeps its old description.
  * an entry in exportvertrag.json «aenderungen» whenever the structure or a count
    changed: added and removed key paths, type changes, moved counts, notes.
    Deterministic: a build that changes nothing adds no entry and rewrites no file.

Hook (one call per published file, right before it is serialised, then one call
after all files of the run are written):

    import export_vertrag as EV
    vertrag = EV.Vertrag()
    doc = EV.fertigstellen(vertrag, "citygov_llm.json", doc, conn, generated_at)
    ...                                   # json.dumps + write as before
    vertrag.festschreiben()

fertigstellen() adds the permanent identifiers (kennungen.anreichern) and the
version stamp. The check (read-only, end of ./build.sh):

    python3 scripts/export_vertrag.py         # every file: version = contract,
                                              # schema file unchanged, file matches
                                              # its schema, counts as recorded
"""
import copy, hashlib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, assert_no_local_paths

WURZEL = ROOT                                   # where exportvertrag.json and schema/ live
VERTRAG = "exportvertrag.json"
SCHEMA_DIR = "schema"
HINWEISE = os.path.join("quellen", "exportvertrag_hinweise.json")
ERSTE_VERSION = "1.0.0"

EXPORTE = {
    # name: (path of the stamp inside the file, JSON lines?)
    "data_export.json":         (("vertrag",), False),
    "citygov_llm.json":         (("meta", "vertrag"), False),
    "citygov_datafields.jsonl": (None, True),
    "citygov_datarules.jsonl":  (None, True),
    "citygov_prefill.json":     (("meta", "vertrag"), False),
    "citygov_verzeichnis.json": (("meta", "vertrag"), False),
    "citygov_ech_schemas.json": (("meta", "vertrag"), False),
}
# objects keyed by data whose keys look like identifiers (they are maps, not records):
# a new register, rule or check result is a moved count, not a new key path
KARTEN = {
    "citygov_ech_schemas.json": {"$.formulare[].ech.*"},
    "data_export.json": {"$.forms[].register.je_register",           # register code -> figures
                         "$.parteien.zahlen.regel", "$.parteien.zahlen.grund",   # code -> points
                         "$.parteien.regeln", "$.parteien.gruende",              # code -> German text
                         "$.wirkung.uebersicht.stand", "$.wirkung.uebersicht.stand_zitiert",
                         "$.wirkung.uebersicht.pruefung", "$.wirkung.uebersicht.pruefung_zitiert",
                         # state -> count: a state that reaches zero is a moved count, not a removed key
                         "$.forms[].standard.ech", "$.dienststellen_uebersicht[].standard.ech",
                         "$.kopfzahlen.standard_ech.ech", "$.gestaltung.merkmale[].urteile",
                         "$.dienststellen_uebersicht[].massnahmen[].mix",
                         # the pages «Datenmodell» and «Was Register schon wissen» (export_json._datenmodell):
                         # role code, Dienststelle slug, kind, status -> figures; code -> German text
                         "$.datenmodell.parteien.rollen", "$.datenmodell.dienststellen",
                         "$.datenmodell.einwohnerregister_andere.je_rolle", "$.datenmodell.zugriff",
                         "$.datenmodell.beilagen.je_register",                   # register code -> Beilagen
                         "$.datenmodell.beilagen.je_register.*[].ersetzt_nicht",  # reason -> Beilagen
                         "$.datenmodell.kennungen.aktiv", "$.datenmodell.kennungen.nicht_aktiv",
                         "$.datenmodell.parteien.methode.stichprobe.schichten",
                         "$.datenmodell.parteien.methode.stichprobe.urteile",
                         "$.datenmodell.parteien.methode.stichprobe.damals",
                         "$.datenmodell.parteien.methode.stichprobe.damals.*",
                         "$.datenmodell.labels.entitaet", "$.datenmodell.labels.entitaet_rolle",
                         "$.datenmodell.labels.herkunft", "$.datenmodell.labels.register_ebene",
                         "$.datenmodell.labels.zugriff_status", "$.datenmodell.labels.zugriff_art",
                         "$.datenmodell.labels.ersetzt_nicht", "$.datenmodell.labels.kennung_art",
                         "$.datenmodell.labels.kennung_status"},
    "citygov_prefill.json": {"$.meta.zaehlung.partei"},              # party status -> points
}
# append-only histories: their length is not a count of the data (one entry per build day)
OHNE_ZAEHLUNG = {"data_export.json": ("$.verlauf",)}
# the pattern of a permanent identifier by key name (scripts/kennungen.py FORMAT, written
# without Python-only syntax so that any JSON Schema validator reads it)
_SEG = r"[a-z0-9][a-z0-9.-]*(?:~[0-9]+)?"
MUSTER = {
    "formular_kennung": rf"^sh:formular:{_SEG}$",
    "artikel_kennung": rf"^sh:gesetz:{_SEG}:(?:art|par|nr)-{_SEG}$",
    "angabe_kennung": r"^sh:angabe:e(?:CH|SH)-[0-9]{4}:[A-Za-z0-9_.-]+(?::[A-Za-z0-9_]+)?(?:~[0-9]+)?$",
    "kennung": r"^sh:(?:service|formular|angabe|gesetz):[A-Za-z0-9_.:~-]+$",
    "abgeloest_durch": r"^sh:(?:service|formular|angabe|gesetz):[A-Za-z0-9_.:~-]+$",
}


def muster(key):
    """The identifier pattern for a key name (None for other keys)."""
    if key in MUSTER:
        return MUSTER[key]
    return MUSTER["kennung"] if key.endswith("_kennung") else None
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_CODE = re.compile(r"^e(?:CH|SH)-[0-9]{4}")
# counts recorded per export: arrays and maps at most this deep (number of [] and .*)
ZAEHL_TIEFE = 2

REGELN = {
    "major": "ein Pflicht-Schlüsselpfad fällt weg, ein Typ ändert sich (ausser null), ein Objekt wird zur "
             "Zuordnung oder umgekehrt, oder ein geprüfter Hinweis meldet eine geänderte Bedeutung",
    "minor": "ein Schlüsselpfad kommt hinzu, ein optionaler fällt weg, darf neu null sein oder nicht mehr, "
             "oder wird optional bzw. Pflicht",
    "patch": "gleiche Struktur, aber eine Anzahl hat sich bewegt (Einträge, Zeilen; ohne den Verlauf, der je "
             "Tag einen Eintrag erhält), oder nur die Beschreibung des Schemas hat sich geändert",
}


def schema_datei(name):
    return f"{SCHEMA_DIR}/{name.rsplit('.', 1)[0]}.schema.json"


def _dump(obj):
    # key order is the construction order, which is fixed (properties sorted by name)
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


# ---- the structure of a file ---------------------------------------------------------
def _typ(v):
    if v is None: return "null"
    if isinstance(v, bool): return "boolean"
    if isinstance(v, int): return "integer"
    if isinstance(v, float): return "number"
    if isinstance(v, str): return "string"
    if isinstance(v, (list, tuple)): return "array"
    if isinstance(v, dict): return "object"
    raise TypeError(f"kein JSON-Wert: {type(v).__name__}")


def struktur(name, doc):
    """{path: {typen, n, n_obj, keys, karte}} of an export object (a JSON-lines file
    is a list of records; each record is an observation of '$')."""
    karten = KARTEN.get(name, set())
    s = {}

    def knoten(p):
        return s.setdefault(p, {"typen": set(), "n": 0, "n_obj": 0, "keys": {}, "karte": False,
                                "muster": [0, 0]})

    def walk(v, p):
        k = knoten(p)
        t = _typ(v)
        k["typen"].add(t)
        k["n"] += 1
        if t == "string":
            m = re.match(r".*\.([A-Za-z_][A-Za-z0-9_]*)$", p)
            rx = muster(m.group(1)) if m else None
            if rx:                                     # [matches the identifier pattern, does not]
                k["muster"][0 if re.search(rx, v) else 1] += 1
        if t == "object":
            k["n_obj"] += 1
            keys = [str(x) for x in v]
            if p in karten or k["karte"] or any(not _IDENT.match(x) or _CODE.match(x) for x in keys):
                if not k["karte"] and k["keys"]:
                    raise RuntimeError(f"{name}: {p} ist teils Objekt, teils Zuordnung — in KARTEN eintragen")
                k["karte"] = True
                for x in v.values():
                    walk(x, p + ".*")
                knoten(p + ".*")
            else:
                for x, w in v.items():
                    x = str(x)
                    k["keys"][x] = k["keys"].get(x, 0) + 1
                    walk(w, f"{p}.{x}")
        elif t == "array":
            knoten(p + "[]")
            for w in v:
                walk(w, p + "[]")

    if EXPORTE[name][1]:
        for row in doc:
            walk(row, "$")
    else:
        walk(doc, "$")
    return s


def _alt_teil(alt, p):
    """The node of the old schema at path p (or None)."""
    if alt is None:
        return None
    node = alt
    for tok in re.findall(r"\[\]|\.\*|\.[^.\[\]]+", p[1:]):
        if tok == "[]":
            node = node.get("items") if isinstance(node, dict) else None
        elif tok == ".*":
            node = node.get("additionalProperties") if isinstance(node, dict) else None
        else:
            node = (node.get("properties") or {}).get(tok[1:]) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            return None
    return node


def schema_aus(s, alt=None, p="$"):
    """JSON Schema of path p; a node this build did not observe keeps its old text."""
    k = s.get(p)
    if not k or not k["typen"]:
        teil = _alt_teil(alt, p)
        return copy.deepcopy(teil) if teil is not None else {}
    typen = set(k["typen"])
    if {"integer", "number"} <= typen:
        typen.discard("integer")
    ordnung = ["object", "array", "string", "number", "integer", "boolean", "null"]
    t = sorted(typen, key=ordnung.index)
    out = {"type": t[0] if len(t) == 1 else t}
    m = re.match(r".*\.([A-Za-z_][A-Za-z0-9_]*)$", p)
    ja, nein = k.get("muster", (0, 0))
    if "string" in typen and m and muster(m.group(1)) and ja:
        # an identifier key: every value carries the pattern of its scheme (a key of that name
        # that only ever holds prose — a field description in meta — gets none)
        if nein:
            raise RuntimeError(f"{p}: {nein} von {ja + nein} Werten sind keine gültige Kennung "
                               f"(Muster {muster(m.group(1))})")
        out["pattern"] = muster(m.group(1))
    if "object" in typen:
        if k["karte"]:
            out["additionalProperties"] = schema_aus(s, alt, p + ".*")
        else:
            keys = sorted(k["keys"])
            out["properties"] = {x: schema_aus(s, alt, f"{p}.{x}") for x in keys}
            out["required"] = [x for x in keys if k["keys"][x] == k["n_obj"]]
            out["additionalProperties"] = False
    if "array" in typen:
        out["items"] = schema_aus(s, alt, p + "[]")
    return out


def flach(schema, p="$", pflicht=True, out=None):
    """path -> (types, required, map) of a schema produced by schema_aus()."""
    out = {} if out is None else out
    if not isinstance(schema, dict):
        return out
    t = schema.get("type")
    typen = tuple(t) if isinstance(t, list) else ((t,) if t else ())
    karte = isinstance(schema.get("additionalProperties"), dict)
    out[p] = (typen, pflicht, karte)
    req = set(schema.get("required") or [])
    for x, sub in (schema.get("properties") or {}).items():
        flach(sub, f"{p}.{x}", x in req, out)
    if karte:
        flach(schema["additionalProperties"], p + ".*", False, out)
    if isinstance(schema.get("items"), dict):
        flach(schema["items"], p + "[]", False, out)
    return out


def zaehlungen(s, jsonl=False, name=None):
    """Observed items per array and map path (and lines of a JSON-lines file); the
    append-only histories of OHNE_ZAEHLUNG are left out."""
    out = {"$": s["$"]["n"]} if jsonl and "$" in s else {}
    ohne = OHNE_ZAEHLUNG.get(name, ())
    for p, k in s.items():
        if any(p == x or p.startswith(x + "[") or p.startswith(x + ".") for x in ohne):
            continue
        tiefe = p.count("[]") + p.count(".*")
        if (p.endswith("[]") or p.endswith(".*")) and tiefe <= ZAEHL_TIEFE:
            out[p] = k["n"]
    return dict(sorted(out.items()))


def unterschiede(alt_flach, neu_flach):
    """(level, details) between two flattened schemas."""
    neu_p = sorted(set(neu_flach) - set(alt_flach))
    weg_p = sorted(set(alt_flach) - set(neu_flach))
    typ, null, pflicht, karte = [], [], [], []
    for p in sorted(set(alt_flach) & set(neu_flach)):
        (ta, pa, ka), (tn, pn, kn) = alt_flach[p], neu_flach[p]
        if not ta or not tn:
            continue                                  # an unobserved node is no change
        a_, n_ = set(ta) - {"null"}, set(tn) - {"null"}
        if a_ and n_ and a_ != n_:
            typ.append({"pfad": p, "vorher": list(ta), "nachher": list(tn)})
        elif set(ta) != set(tn):
            # null may now occur or no longer does — including a path seen only as null
            # that now carries a value (or the reverse): no reader of a value breaks
            null.append({"pfad": p, "vorher": list(ta), "nachher": list(tn)})
        if pa != pn:
            pflicht.append({"pfad": p, "vorher": "Pflicht" if pa else "optional",
                            "nachher": "Pflicht" if pn else "optional"})
        if ka != kn:
            karte.append({"pfad": p, "vorher": "Zuordnung" if ka else "Objekt", "nachher": "Zuordnung" if kn else "Objekt"})
    # a key path whose removal can break a reader: required in the old schema, and so
    # are all the objects above it (an optional key of a required object is optional)
    def pflicht_pfad(p):
        if p.endswith("[]") or p.endswith(".*"):
            return False                              # the items node goes only with its array or map
        return alt_flach[p][1] and all(alt_flach[q][1] for q in _vorfahren(p)
                                       if q in alt_flach and q != "$" and not q.endswith(("[]", ".*")))
    weg_pflicht = [p for p in weg_p if pflicht_pfad(p)]
    weg_optional = [p for p in weg_p if p not in weg_pflicht]
    stufe = "major" if (weg_pflicht or typ or karte) else (
        "minor" if (neu_p or weg_optional or null or pflicht) else None)
    return stufe, {"schluessel_neu": neu_p, "schluessel_entfernt": weg_pflicht,
                   "optional_entfernt": weg_optional, "typ_geaendert": typ,
                   "null_geaendert": null, "pflicht_geaendert": pflicht, "objekt_zuordnung": karte}


def _vorfahren(p):
    """The key paths above p ('$.a[].b.c' -> '$.a[].b', '$.a[]', '$.a')."""
    out = []
    while True:
        m = re.match(r"^(.*)(\[\]|\.\*|\.[^.\[\]]+)$", p)
        if not m or not m.group(1):
            return out
        p = m.group(1)
        out.append(p)


def _schema_text(name, version, jsonl, wurzel):
    """The schema file of one export, as written."""
    return _dump({"$schema": "https://json-schema.org/draft/2020-12/schema",
                  "title": name,
                  "description": (f"Struktur von {name}, Version {version}" +
                                  (" — eine Zeile der Datei (JSON Lines)" if jsonl else "") +
                                  ". Erzeugt aus der Datei, wie der Build sie schreibt (scripts/export_vertrag.py); "
                                  "Änderungen und Regeln in exportvertrag.json. Nie von Hand ändern."),
                  "$ref": "#/$defs/datei", "$defs": {"datei": wurzel}})


def _schema_text_alt(alt_schema):
    return _dump(alt_schema) if alt_schema is not None else None


def _hoeher(v, stufe):
    a, b, c = (int(x) for x in v.split("."))
    return {"major": f"{a + 1}.0.0", "minor": f"{a}.{b + 1}.0", "patch": f"{a}.{b}.{c + 1}"}[stufe]


# ---- the contract ---------------------------------------------------------------------
class Vertrag:
    """The contract state (exportvertrag.json + schema/) of one build run."""

    def __init__(self, wurzel=None, hinweise=None):
        self.wurzel = wurzel or WURZEL
        self.pfad = os.path.join(self.wurzel, VERTRAG)
        self.hinweise_pfad = hinweise or os.path.join(self.wurzel, HINWEISE)
        if os.path.exists(self.pfad):
            with open(self.pfad, encoding="utf-8") as fh:
                self.stand = json.load(fh)
        else:
            self.stand = {"exporte": {}, "aenderungen": []}
        self.offen = {}                               # name -> (schema text, export state, entry or None)

    def _altes_schema(self, name, eintrag):
        """The schema file of the current version, checked against the recorded hash."""
        if not eintrag:
            return None
        p = os.path.join(self.wurzel, eintrag["schema"])
        try:
            text = open(p, encoding="utf-8").read()
        except OSError:
            raise RuntimeError(f"{eintrag['schema']} fehlt, exportvertrag.json nennt es für {name}")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != eintrag["schema_sha256"]:
            raise RuntimeError(f"{eintrag['schema']} wurde verändert (Prüfsumme weicht von exportvertrag.json ab) — "
                               "nie von Hand ändern")
        return json.loads(text)

    def _hinweise(self, name):
        if not os.path.exists(self.hinweise_pfad):
            return []
        with open(self.hinweise_pfad, encoding="utf-8") as fh:
            liste = json.load(fh)
        erledigt = {h for e in self.stand["aenderungen"] if e["export"] == name for h in e.get("hinweise_ids", [])}
        out = []
        for h in liste:
            if h.get("export") != name or h.get("id") in erledigt:
                continue
            if not h.get("id") or not (h.get("text") or "").strip() or h.get("stufe") not in ("major", "minor", "patch"):
                raise RuntimeError(f"{self.hinweise_pfad}: Hinweis braucht id, text und stufe major|minor|patch: {h}")
            out.append(h)
        return out

    def stempeln(self, name, doc, stand):
        """Decide the version of one export for this build and put the stamp into the
        file object (JSON files). `stand` is the build's generated_at."""
        stempel_pfad, jsonl = EXPORTE[name]
        alt = self.stand["exporte"].get(name)
        alt_schema = self._altes_schema(name, alt)
        if stempel_pfad:                               # placeholder of the final shape
            ziel = doc
            for teil in stempel_pfad[:-1]:
                ziel = ziel.setdefault(teil, {})
            ziel[stempel_pfad[-1]] = {"version": "0.0.0", "schema": schema_datei(name), "aenderungen": VERTRAG}
        s = struktur(name, doc)
        wurzel = schema_aus(s, alt_schema.get("$defs", {}).get("datei") if alt_schema else None)
        zahl = zaehlungen(s, jsonl, name)
        hinweise = self._hinweise(name)
        if alt is None:
            version, stufe, details = ERSTE_VERSION, "erstfassung", {}
        else:
            stufe, details = unterschiede(flach(alt_schema["$defs"]["datei"]), flach(wurzel))
            bewegt = [{"pfad": p, "vorher": alt["zaehlungen"].get(p), "nachher": zahl.get(p)}
                      for p in sorted(set(zahl) | set(alt["zaehlungen"])) if zahl.get(p) != alt["zaehlungen"].get(p)]
            if bewegt:
                details["zaehlungen"] = bewegt
                stufe = stufe or "patch"
            for h in hinweise:
                stufe = min((stufe, h["stufe"]), key=["major", "minor", "patch", None].index) if stufe else h["stufe"]
            if not stufe and _schema_text(name, alt["version"], jsonl, wurzel) != _schema_text_alt(alt_schema):
                # same structure and counts, but the schema's wording changed (a pattern)
                stufe, details["schema_beschreibung"] = "patch", "geändert"
            version = _hoeher(alt["version"], stufe) if stufe else alt["version"]
        text = _schema_text(name, version, jsonl, wurzel)
        eintrag_neu = {"version": version, "schema": schema_datei(name),
                       "schema_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                       "version_steht": ("nur hier: eine JSON-Zeilen-Datei hat keine Kopfzeile" if jsonl
                                         else ".".join(stempel_pfad) + ".version"),
                       "seit": alt["seit"] if alt and not stufe else stand,
                       "zaehlungen": zahl}
        aenderung = None
        if stufe:
            aenderung = {"export": name, "version": version, "vorher": alt["version"] if alt else None,
                         "stufe": stufe, "stand": stand}
            aenderung.update({k: v for k, v in details.items() if v})
            if hinweise:
                aenderung["hinweise"] = [h["text"] for h in hinweise]
                aenderung["hinweise_ids"] = [h["id"] for h in hinweise]
            if stufe == "erstfassung":
                aenderung["zaehlungen"] = [{"pfad": p, "nachher": n} for p, n in zahl.items()]
        self.offen[name] = (text, eintrag_neu, aenderung)
        if stempel_pfad:
            ziel = doc
            for teil in stempel_pfad[:-1]:
                ziel = ziel[teil]
            ziel[stempel_pfad[-1]]["version"] = version
        return doc

    def festschreiben(self):
        """Write the schema files and exportvertrag.json of the exports stamped in this
        run — only files whose content changes."""
        if not self.offen:
            return []
        geschrieben = []
        for name in sorted(self.offen):
            text, eintrag, aenderung = self.offen[name]
            self.stand["exporte"][name] = eintrag
            if aenderung:
                self.stand["aenderungen"].append(aenderung)
            p = os.path.join(self.wurzel, eintrag["schema"])
            if _schreiben(p, text):
                geschrieben.append(eintrag["schema"])
        self.stand["hinweis"] = ("Vertrag der veröffentlichten Exporte: Version je Datei (Semantic Versioning), "
                                 "JSON Schema unter schema/, Änderungen je Build. Geschrieben von "
                                 "scripts/export_vertrag.py beim Export; nie von Hand ändern. Kennungen (sh:…) "
                                 "sind dauerhaft und werden nie neu vergeben (scripts/kennungen.py).")
        self.stand["regeln"] = REGELN
        self.stand["exporte"] = dict(sorted(self.stand["exporte"].items()))
        text = _dump({k: self.stand[k] for k in ("hinweis", "regeln", "exporte", "aenderungen")})
        if _schreiben(self.pfad, text):
            geschrieben.append(VERTRAG)
        self.offen = {}
        return geschrieben


def _schreiben(pfad, text):
    """Write text only when it differs from the file (a build without change touches nothing)."""
    assert_no_local_paths(os.path.basename(pfad), text)
    try:
        if open(pfad, encoding="utf-8").read() == text:
            return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    tmp = pfad + ".staging"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, pfad)
    return True


def fertigstellen(vertrag, name, doc, conn, stand):
    """The export hook: permanent identifiers, then the version stamp."""
    import kennungen
    kennungen.anreichern(name, doc, conn)
    return vertrag.stempeln(name, doc, stand)


# ---- check (read-only) ----------------------------------------------------------------------
def _gueltig(wert, schema, p="$", fehler=None, grenze=20):
    """Minimal JSON Schema check for what schema_aus() writes (type, pattern,
    properties, required, additionalProperties, items)."""
    fehler = [] if fehler is None else fehler
    if len(fehler) >= grenze or not schema:
        return fehler
    t = schema.get("type")
    erlaubt = set(t if isinstance(t, list) else [t]) if t else None
    ist = _typ(wert)
    if erlaubt is not None and ist not in erlaubt and not (ist == "integer" and "number" in erlaubt):
        fehler.append(f"{p}: {ist} statt {sorted(erlaubt)}")
        return fehler
    if ist == "string" and schema.get("pattern") and not re.search(schema["pattern"], wert):
        fehler.append(f"{p}: «{wert[:60]}» passt nicht zum Muster {schema['pattern']}")
    if ist == "object":
        props = schema.get("properties")
        zusatz = schema.get("additionalProperties")
        for r in schema.get("required") or []:
            if r not in wert:
                fehler.append(f"{p}: Pflichtschlüssel {r} fehlt")
        for k, v in wert.items():
            if props is not None and k in props:
                _gueltig(v, props[k], f"{p}.{k}", fehler, grenze)
            elif isinstance(zusatz, dict):
                _gueltig(v, zusatz, f"{p}.*", fehler, grenze)
            elif zusatz is False:
                fehler.append(f"{p}: unbekannter Schlüssel {k}")
    elif ist == "array" and isinstance(schema.get("items"), dict):
        for v in wert:
            _gueltig(v, schema["items"], p + "[]", fehler, grenze)
            if len(fehler) >= grenze:
                break
    return fehler


def pruefen(wurzel=None, dateien=None):
    """Every published file against the contract. Returns a list of errors."""
    wurzel = wurzel or WURZEL
    dateien = dateien or wurzel
    try:
        stand = json.load(open(os.path.join(wurzel, VERTRAG), encoding="utf-8"))
    except OSError:
        return [f"{VERTRAG} fehlt"]
    err = []
    for name, (stempel_pfad, jsonl) in EXPORTE.items():
        e = stand["exporte"].get(name)
        p = os.path.join(dateien, name)
        if not e:
            err.append(f"{name}: nicht im Vertrag"); continue
        if not os.path.exists(p):
            err.append(f"{name}: Datei fehlt"); continue
        try:
            text = open(os.path.join(wurzel, e["schema"]), encoding="utf-8").read()
        except OSError:
            err.append(f"{name}: {e['schema']} fehlt"); continue
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != e["schema_sha256"]:
            err.append(f"{name}: {e['schema']} weicht von der Prüfsumme in {VERTRAG} ab")
        schema = json.loads(text)["$defs"]["datei"]
        with open(p, encoding="utf-8") as fh:
            doc = [json.loads(z) for z in fh if z.strip()] if jsonl else json.load(fh)
        if stempel_pfad:
            v = doc
            for teil in stempel_pfad:
                v = v.get(teil) if isinstance(v, dict) else None
            if not isinstance(v, dict) or v.get("version") != e["version"]:
                err.append(f"{name}: Version in der Datei {v.get('version') if isinstance(v, dict) else None} "
                           f"≠ Vertrag {e['version']}")
        fehler = []
        for zeile in (doc if jsonl else [doc]):
            _gueltig(zeile, schema, "$", fehler)
        if fehler:
            err.append(f"{name}: passt nicht zu {e['schema']}: " + "; ".join(fehler[:3]))
        zahl = zaehlungen(struktur(name, doc), jsonl, name)
        if zahl != e["zaehlungen"]:
            diff = [p_ for p_ in sorted(set(zahl) | set(e["zaehlungen"])) if zahl.get(p_) != e["zaehlungen"].get(p_)]
            err.append(f"{name}: Anzahlen weichen vom Vertrag ab ({len(diff)} Pfade, z. B. {diff[:2]})")
    return err


if __name__ == "__main__":
    errs = pruefen()
    if errs:
        print("ABBRUCH Exportvertrag:", *errs, sep="\n  ")
        sys.exit(1)
    st = json.load(open(os.path.join(WURZEL, VERTRAG), encoding="utf-8"))
    print("Exportvertrag geprüft: " + ", ".join(f"{n} {e['version']}" for n, e in st["exporte"].items()))
