#!/usr/bin/env python3
"""Add the data-management layer: register columns, retention tables, the
canonical attribute catalogue, format patterns and the Dienststellen entity.

This is the schema + mechanical-seed half of the 2026-09 data-management
build (the curated half — purposes, recipients, retention terms — comes from
agent output through load_register.py's proof gates). Everything here is
derivable or empty-by-design:

  * form.purpose / dsfa_status / dsfa_note  — empty until curated/decided
  * data_field.schutzstufe                  — empty until the canton decides
                                              (no fake defaults: Luecke = Luecke)
  * data_field.format_code                  — mechanically normalised from the
                                              existing prose format hints
  * format_pattern     — ~15 canonical Swiss patterns; every regex must match
                          its own beispiel or the script aborts
  * canonical_attribute — fully derived from the eCH/eSH mappings (one row per
                          unique datum), rebuilt wholesale on every run
  * dienststelle        — one row per distinct office name (owner/contact empty)
  * form_disclosure / retention_term / retention_decision — created empty here

Idempotent. Staging -> validate -> swap.

    python3 scripts/init_register.py
"""
import json, os, re, shutil, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

DDL = """
CREATE TABLE IF NOT EXISTS format_pattern (
    code     TEXT PRIMARY KEY,
    regex    TEXT NOT NULL,
    beispiel TEXT NOT NULL,
    beschreibung TEXT
);
CREATE TABLE IF NOT EXISTS canonical_attribute (
    id             INTEGER PRIMARY KEY,
    ech_element_id INTEGER UNIQUE REFERENCES ech_element(id),
    esh_key        TEXT UNIQUE,
    label          TEXT NOT NULL,
    datatype       TEXT,
    sensitive_categories TEXT,
    register_source TEXT,
    n_instances    INTEGER NOT NULL,
    n_forms        INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS dienststelle (
    name        TEXT PRIMARY KEY,
    department  TEXT,
    dateninhaber TEXT,
    kontakt     TEXT
);
CREATE TABLE IF NOT EXISTS form_disclosure (
    id         INTEGER PRIMARY KEY,
    form_id    INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    empfaenger TEXT NOT NULL,
    mode       TEXT CHECK(mode IN ('systematisch','auf_anfrage')),
    article_id INTEGER REFERENCES article(id),
    last_checked TEXT,
    UNIQUE(form_id, empfaenger)
);
CREATE TABLE IF NOT EXISTS retention_term (
    id             INTEGER PRIMARY KEY,
    data_rule_id   INTEGER NOT NULL UNIQUE REFERENCES data_rule(id) ON DELETE CASCADE,
    duration_value INTEGER,
    duration_unit  TEXT CHECK(duration_unit IN ('jahre','monate')),
    min_or_max     TEXT CHECK(min_or_max IN ('min','max','exakt')),
    trigger_event  TEXT,
    disposition    TEXT CHECK(disposition IN ('vernichten','anonymisieren',
                       'anbieten_staatsarchiv','loeschen_vermerken')),
    last_checked   TEXT
);
CREATE TABLE IF NOT EXISTS retention_decision (
    id             INTEGER PRIMARY KEY,
    form_id        INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    duration_value INTEGER,
    duration_unit  TEXT,
    trigger_event  TEXT,
    disposition    TEXT,
    decided_by     TEXT,
    decided_at     TEXT,
    basis          TEXT,
    note           TEXT
);
"""

# canonical Swiss input patterns; the loader gate below proves regex vs beispiel
PATTERNS = [
    ("date.ch",       r"^\d{2}\.\d{2}\.\d{4}$",              "31.12.2026", "Datum TT.MM.JJJJ"),
    ("date.ch.short", r"^\d{2}\.\d{2}\.\d{2}$",              "31.12.26",   "Datum TT.MM.JJ"),
    ("year",          r"^\d{4}$",                            "2026",       "Jahreszahl JJJJ"),
    ("time.hm",       r"^([01]\d|2[0-3]):[0-5]\d$",          "08:30",      "Uhrzeit HH:MM"),
    ("ahvn13",        r"^756\.\d{4}\.\d{4}\.\d{2}$",         "756.1234.5678.97", "AHV-Nummer (AHVN13)"),
    ("uid.che",       r"^CHE-\d{3}\.\d{3}\.\d{3}$",          "CHE-123.456.789",  "Unternehmens-ID"),
    ("plz.ch",        r"^\d{4}$",                            "8200",       "Schweizer Postleitzahl"),
    ("money.chf",     r"^\d{1,3}(['’ ]?\d{3})*(\.\d{1,2})?$", "1250.50",   "Frankenbetrag"),
    ("percent",       r"^\d{1,3}(\.\d+)?$",                  "42.5",       "Prozentwert"),
    ("number",        r"^\d+([.,]\d+)?$",                    "12",         "Zahl (Einheit steht im Feld)"),
    ("email",         r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$",    "hans.muster@sh.ch", "E-Mail-Adresse"),
    ("phone.ch",      r"^[+0][0-9 ()./-]{8,20}$",            "+41 52 632 70 00",  "Telefonnummer"),
    ("iban.ch",       r"^CH\d{2}[0-9A-Za-z]{17}$",           "CH9300762011623852957", "IBAN Schweiz"),
]

# prose format hint -> pattern code (matched lowercased, longest rule first)
PROSE_MAP = [
    ("756.", "ahvn13"), ("che-", "uid.che"), ("iban", "iban.ch"),
    ("tt.mm.jjjj", "date.ch"), ("dd.mm.yyyy", "date.ch"), ("tt.mm.jj", "date.ch.short"),
    ("hh:mm", "time.hm"), ("jjjj", "year"), ("e-mail", "email"), ("email", "email"),
    ("telefon", "phone.ch"), ("chf", "money.chf"), ("%", "percent"), ("prozent", "percent"),
    ("plz", "plz.ch"),
    ("kg", "number"), ("stunden", "number"), ("m²", "number"), ("mwh", "number"),
    ("anzahl", "number"), ("liter", "number"), ("aren", "number"), ("minuten", "number"),
]

# the five eCH register standards whose data the Einwohnerregister already holds
REGISTER_STDS = {"eCH-0044", "eCH-0010", "eCH-0011", "eCH-0007", "eCH-0008"}


def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    for tbl, col, typ in [("form", "purpose", "TEXT"), ("form", "dsfa_status", "TEXT"),
                          ("form", "dsfa_note", "TEXT"), ("data_field", "schutzstufe", "TEXT"),
                          ("data_field", "format_code", "TEXT")]:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
        except Exception:
            pass    # column already exists (idempotent re-run)

    # format patterns — a regex that cannot match its own beispiel is a bug
    for code, rx, bsp, desc in PATTERNS:
        if not re.match(rx, bsp):
            print(f"ABORT: pattern {code} matcht sein eigenes Beispiel nicht"); sys.exit(1)
        c.execute("INSERT OR REPLACE INTO format_pattern(code,regex,beispiel,beschreibung) "
                  "VALUES(?,?,?,?)", [code, rx, bsp, desc])

    # normalise the prose format hints to codes (mechanical, report the rest)
    n_fmt, unmatched = 0, Counter()
    for r in c.execute("SELECT id, format FROM data_field WHERE format IS NOT NULL AND format!=''").fetchall():
        f = r["format"].lower()
        code = next((cd for key, cd in PROSE_MAP if key in f), None)
        if code:
            c.execute("UPDATE data_field SET format_code=? WHERE id=?", [code, r["id"]])
            n_fmt += 1
        else:
            unmatched[r["format"][:40]] += 1

    # canonical attribute catalogue: one row per unique datum, fully derived
    c.execute("DELETE FROM canonical_attribute")
    attrs = {}
    def collect(key, name, sens, form_id):
        a = attrs.setdefault(key, {"names": Counter(), "sens": set(), "forms": set(), "n": 0})
        a["names"][name] += 1; a["forms"].add(form_id); a["n"] += 1
        if sens: a["sens"].add(sens)
    for r in c.execute("SELECT d.ech_element_id k, d.name, d.sensitive, d.form_id "
                       "FROM data_field d WHERE d.ech_element_id IS NOT NULL"):
        collect(("ech", r["k"]), r["name"], r["sensitive"], r["form_id"])
    for r in c.execute("SELECT s.ech_element_id k, s.name, d.sensitive, d.form_id "
                       "FROM data_subfield s JOIN data_field d ON d.id=s.data_field_id "
                       "WHERE s.ech_element_id IS NOT NULL"):
        collect(("ech", r["k"]), r["name"], r["sensitive"], r["form_id"])
    for r in c.execute("SELECT d.esh_code, d.esh_element, d.name, d.sensitive, d.form_id "
                       "FROM data_field d WHERE d.esh_code IS NOT NULL AND d.esh_element IS NOT NULL"):
        collect(("esh", f"{r['esh_code']}:{r['esh_element']}"), r["name"], r["sensitive"], r["form_id"])
    for r in c.execute("SELECT s.esh_code, s.esh_element, s.name, d.sensitive, d.form_id "
                       "FROM data_subfield s JOIN data_field d ON d.id=s.data_field_id "
                       "WHERE s.esh_code IS NOT NULL AND s.esh_element IS NOT NULL"):
        collect(("esh", f"{r['esh_code']}:{r['esh_element']}"), r["name"], r["sensitive"], r["form_id"])
    edata = {r["id"]: r for r in c.execute("SELECT id, standard, datatype FROM ech_element")}
    for (kind, key), a in attrs.items():
        label = a["names"].most_common(1)[0][0]
        sens = json.dumps(sorted(a["sens"]), ensure_ascii=False) if a["sens"] else None
        if kind == "ech":
            e = edata.get(key)
            reg = "einwohnerregister" if e and e["standard"] in REGISTER_STDS else None
            c.execute("INSERT INTO canonical_attribute(ech_element_id,label,datatype,"
                      "sensitive_categories,register_source,n_instances,n_forms) VALUES(?,?,?,?,?,?,?)",
                      [key, label, e["datatype"] if e else None, sens, reg, a["n"], len(a["forms"])])
        else:
            c.execute("INSERT INTO canonical_attribute(esh_key,label,sensitive_categories,"
                      "n_instances,n_forms) VALUES(?,?,?,?,?)",
                      [key, label, sens, a["n"], len(a["forms"])])

    # Dienststellen as an entity (owner/contact stay empty until the canton fills them)
    dep = {}
    for r in c.execute("SELECT dienststelle, department FROM service WHERE dienststelle IS NOT NULL"):
        dep.setdefault(r["dienststelle"], Counter())[r["department"] or ""] += 1
    for r in c.execute("SELECT publisher_dienststelle d FROM form WHERE publisher_dienststelle IS NOT NULL"):
        dep.setdefault(r["d"], Counter())
    for name, cnt in dep.items():
        c.execute("INSERT OR IGNORE INTO dienststelle(name, department) VALUES(?,?)",
                  [name, cnt.most_common(1)[0][0] if cnt else None])

    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"register layer: {len(PATTERNS)} format patterns, {n_fmt} Felder mit format_code, "
          f"{len(attrs)} kanonische Attribute, {len(dep)} Dienststellen")
    if unmatched:
        print(f"  ohne format_code ({sum(unmatched.values())} Felder): "
              + ", ".join(f"{k} ({v}x)" for k, v in unmatched.most_common(6)))


if __name__ == "__main__":
    main()
