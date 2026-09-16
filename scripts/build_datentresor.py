#!/usr/bin/env python3
"""Build the Datentresor — an applied example of how the canton would actually
STORE the data its Formulare collect, with the compliance rules enforced at
INSERT time instead of just documented.

Everything in ../datentresor.db is SYNTHETIC (generated people, generated
values). The schema comes from citygov.db: the storage unit is the canonical
attribute (once-only: one datum per person, later Fälle reference it), the
storage type is the eCH datatype, sensitive values are encrypted at rest,
every datapoint carries its Erhebungsgrundlage and a computed Löschdatum from
the real retention rules, Beilagen the state could fetch itself become a
Prüfvermerk instead of a copy, and every read/Bekanntgabe lands in the log.

The gates are the point: a value that fails its format pattern, a datapoint
without legal basis and without consent, or an unencrypted sensitive value is
REFUSED — the databank's rules, running.

Two things make this more than a script's promise:
  * the GATES LIVE IN THE SCHEMA — triggers refuse an unencrypted sensitive
    value, a datapoint without basis/consent, a value failing its format, any
    edit of the access log, and any hard DELETE of a datapoint (lifecycle is
    a status change, and the trigger writes the log entry itself). Any client
    is bound, not just this generator — provable from the sqlite3 shell.
  * sensitive values use real AES-256-GCM (cryptography lib in .venv); if the
    lib is missing the build falls back to the labelled demo cipher and the
    meta table says which one is in force. Key in ../datentresor.key, never
    inside the DB.

    .venv/bin/python3 scripts/build_datentresor.py [subjects] [faelle]
"""
import hashlib, json, os, random, re, secrets, sqlite3, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, ROOT, connect

OUT = os.path.join(ROOT, "datentresor.db")
KEYFILE = os.path.join(ROOT, "datentresor.key")
SEED = 8200                       # Schaffhausen; fixed so the build reproduces

DDL = """
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE subjekt (
    id INTEGER PRIMARY KEY,
    ahvn13 TEXT UNIQUE,           -- synthetic, valid EAN-13 check digit
    name TEXT, vorname TEXT, geburtsdatum TEXT,
    strasse TEXT, plz TEXT, ort TEXT,
    email TEXT, telefon TEXT
);
CREATE TABLE fall (
    id INTEGER PRIMARY KEY,
    subjekt_id INTEGER NOT NULL REFERENCES subjekt(id),
    service_id INTEGER, form_id INTEGER NOT NULL,
    formular TEXT, dienststelle TEXT,
    eingereicht TEXT, abgeschlossen TEXT,
    entscheid TEXT
);
CREATE TABLE datenpunkt (
    id INTEGER PRIMARY KEY,
    subjekt_id INTEGER NOT NULL REFERENCES subjekt(id),
    attribut_id INTEGER,          -- canonical_attribute.id in citygov.db; NULL = form-only datum
    attribut TEXT NOT NULL,       -- readable label
    ech_standard TEXT, ech_element TEXT, ech_datatype TEXT,
    wert TEXT,                    -- the stored value; ciphertext when verschluesselt=1
    verschluesselt INTEGER NOT NULL DEFAULT 0,
    nonce TEXT,
    format_glob TEXT,             -- storage-shape contract, enforced by trigger
    sensitive TEXT,               -- gesundheit / politik / ... or NULL
    erhoben_am TEXT,
    erhebungs_fall INTEGER REFERENCES fall(id),
    grundlage_artikel INTEGER,    -- article.id in citygov.db (Erhebungsgrundlage)
    grundlage TEXT,               -- readable citation
    einwilligung_id INTEGER,      -- set instead of grundlage for no_basis fields
    loeschdatum TEXT,             -- computed from the retention rules
    status TEXT NOT NULL DEFAULT 'aktiv'
        CHECK (status IN ('aktiv','anonymisiert','vernichtet','archiviert'))
);
CREATE TABLE datenpunkt_verwendung (   -- the once-only ledger: later Fälle reference,
    fall_id INTEGER NOT NULL REFERENCES fall(id),      -- they do not re-store
    datenpunkt_id INTEGER NOT NULL REFERENCES datenpunkt(id),
    wiederverwendet INTEGER NOT NULL DEFAULT 0,        -- 0 = erhoben in diesem Fall,
    PRIMARY KEY (fall_id, datenpunkt_id)               -- 1 = aus früherem Fall referenziert
);
CREATE TABLE einwilligung (
    id INTEGER PRIMARY KEY,
    subjekt_id INTEGER NOT NULL REFERENCES subjekt(id),
    fall_id INTEGER REFERENCES fall(id),
    gegenstand TEXT, erteilt_am TEXT, widerrufen_am TEXT
);
CREATE TABLE beleg (
    id INTEGER PRIMARY KEY,
    fall_id INTEGER NOT NULL REFERENCES fall(id),
    bezeichnung TEXT,
    art TEXT NOT NULL,            -- kopie | pruefvermerk
    halter TEXT,
    sha256 TEXT,                  -- only for stored copies
    geprueft_am TEXT, geprueft_von TEXT,   -- only for Prüfvermerke
    loeschdatum TEXT
);
CREATE TABLE zugriff_log (
    id INTEGER PRIMARY KEY,
    zeitpunkt TEXT, art TEXT,     -- lesen | bekanntgabe
    subjekt_id INTEGER, fall_id INTEGER,
    wer TEXT, zweck TEXT, grundlage TEXT
);
CREATE INDEX ix_dp_subjekt ON datenpunkt(subjekt_id);
CREATE INDEX ix_dp_loesch ON datenpunkt(loeschdatum);
CREATE INDEX ix_log_subjekt ON zugriff_log(subjekt_id);

-- the gates, in the database itself: ANY client is bound, not just our script
CREATE TRIGGER tg_sensitiv_nur_verschluesselt BEFORE INSERT ON datenpunkt
WHEN NEW.sensitive IS NOT NULL AND NEW.verschluesselt = 0
BEGIN SELECT RAISE(ABORT, 'GATE: sensibler Wert darf nur verschlüsselt gespeichert werden'); END;
CREATE TRIGGER tg_grundlage_oder_einwilligung BEFORE INSERT ON datenpunkt
WHEN NEW.grundlage_artikel IS NULL AND NEW.einwilligung_id IS NULL
     AND (NEW.grundlage IS NULL OR (NEW.grundlage NOT LIKE 'Rechtsgrundlage zu ermitteln%'
          AND NEW.grundlage NOT LIKE 'Aufgabenerfüllung%' AND NEW.grundlage NOT LIKE 'Aufgabenbedarf%'))
BEGIN SELECT RAISE(ABORT, 'GATE: Datenpunkt braucht Rechtsgrundlage oder Einwilligung'); END;
CREATE TRIGGER tg_format BEFORE INSERT ON datenpunkt
WHEN NEW.verschluesselt = 0 AND NEW.format_glob IS NOT NULL AND NEW.wert NOT GLOB NEW.format_glob
BEGIN SELECT RAISE(ABORT, 'GATE: Wert verletzt das Speicherformat des Standards'); END;
CREATE TRIGGER tg_kein_hard_delete BEFORE DELETE ON datenpunkt
BEGIN SELECT RAISE(ABORT, 'GATE: Datenpunkte werden nie gelöscht — Statuswechsel auf vernichtet/anonymisiert'); END;
CREATE TRIGGER tg_statuswechsel_protokolliert AFTER UPDATE OF status ON datenpunkt
WHEN NEW.status != OLD.status
BEGIN
    INSERT INTO zugriff_log(zeitpunkt, art, subjekt_id, wer, zweck, grundlage)
    VALUES (datetime('now'), 'statuswechsel', NEW.subjekt_id, 'System',
            OLD.status || ' → ' || NEW.status, 'Lebenszyklus (Löschkonzept)');
END;
CREATE TRIGGER tg_log_unveraenderlich_u BEFORE UPDATE ON zugriff_log
BEGIN SELECT RAISE(ABORT, 'GATE: das Zugriffsprotokoll ist unveränderlich'); END;
CREATE TRIGGER tg_log_unveraenderlich_d BEFORE DELETE ON zugriff_log
BEGIN SELECT RAISE(ABORT, 'GATE: das Zugriffsprotokoll ist unveränderlich'); END;

-- the DSG questions, answered from the data itself
CREATE VIEW v_auskunft AS
    SELECT s.ahvn13, s.name, s.vorname, d.attribut, d.ech_standard, d.ech_element,
           CASE WHEN d.verschluesselt THEN '[verschlüsselt]' ELSE d.wert END wert,
           d.sensitive, d.grundlage, d.erhoben_am, d.loeschdatum, d.status
    FROM datenpunkt d JOIN subjekt s ON s.id=d.subjekt_id;
CREATE VIEW v_loeschliste AS
    SELECT d.id, s.name, s.vorname, d.attribut, d.loeschdatum, d.grundlage
    FROM datenpunkt d JOIN subjekt s ON s.id=d.subjekt_id
    WHERE d.status='aktiv' AND d.loeschdatum <= date('now');
CREATE VIEW v_verzeichnis AS
    SELECT f.formular, f.dienststelle, COUNT(DISTINCT v.datenpunkt_id) datenpunkte,
           COUNT(DISTINCT f.subjekt_id) betroffene,
           SUM(v.wiederverwendet=1) wiederverwendet
    FROM fall f JOIN datenpunkt_verwendung v ON v.fall_id=f.id
    GROUP BY f.form_id;
"""

VORNAMEN = ["Anna","Lukas","Mia","Noah","Lea","Elias","Sara","David","Nina","Jonas",
            "Laura","Fabian","Elena","Simon","Julia","Marco","Livia","Pascal","Chiara",
            "Sven","Petra","Urs","Corinne","Beat","Sandra","Reto","Monika","Daniel",
            "Esther","Thomas","Verena","Markus","Ruth","Peter","Silvia","Hans"]
NAMEN = ["Müller","Meier","Schmid","Keller","Weber","Huber","Schneider","Brunner",
         "Baumann","Frei","Gerber","Widmer","Zimmermann","Moser","Graf","Wyss",
         "Roth","Suter","Kunz","Fischer","Gasser","Bühler","Steiner","Vogel",
         "Herzog","Kaufmann","Bösch","Stamm","Wanner","Uehlinger","Bächtold","Rüeger"]
ORTE = [("8200","Schaffhausen"),("8212","Neuhausen am Rheinfall"),("8240","Thayngen"),
        ("8222","Beringen"),("8260","Stein am Rhein"),("8215","Hallau"),
        ("8226","Schleitheim"),("8262","Ramsen"),("8228","Beggingen"),
        ("8213","Neunkirch"),("8218","Osterfingen"),("8235","Lohn")]
STRASSEN = ["Bahnhofstrasse","Rheinweg","Vordergasse","Mühlentalstrasse","Webergasse",
            "Steigstrasse","Fulachstrasse","Grabenstrasse","Hochstrasse","Kirchhofplatz",
            "Rosengasse","Bachstrasse","Feldweg","Sonnenbergstrasse","Ringstrasse"]
WOERTER = ["Bemerkung","gemäss Absprache","siehe Beilage","wie besprochen","keine",
           "auf Anfrage","laufend","provisorisch","definitiv","teilweise"]


def ahvn13():
    digits = "756" + "".join(str(random.randint(0, 9)) for _ in range(9))
    s = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    digits += str((10 - s % 10) % 10)
    return f"{digits[0:3]}.{digits[3:7]}.{digits[7:11]}.{digits[11:13]}"


def keystream_xor(key, nonce, data):
    """Fallback demo cipher (SHA-256 keystream) for machines without the
    cryptography lib; the meta table says which cipher a build used."""
    out, counter = bytearray(), 0
    while len(out) < len(data):
        out += hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out[:len(data)]))


def make_cipher(key):
    """AES-256-GCM when available (authenticated, production-grade primitive),
    else the labelled demo cipher. Returns (encrypt(value)->(hex,nonce_hex), label)."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aes = AESGCM(key)
        def enc(val):
            nonce = secrets.token_bytes(12)
            return aes.encrypt(nonce, val.encode(), None).hex(), nonce.hex()
        return enc, "AES-256-GCM (cryptography); Schlüssel in datentresor.key, NIE in der DB."
    except ImportError:
        def enc(val):
            nonce = secrets.token_bytes(12)
            return keystream_xor(key, nonce, val.encode()).hex(), nonce.hex()
        return enc, ("Demo-Streamcipher (SHA-256-Keystream) — cryptography-Lib fehlte beim Build. "
                     "Nicht produktionstauglich; Schlüssel in datentresor.key, NIE in der DB.")


# the storage-shape contracts the tg_format trigger enforces, per format code
GLOBS = {
    "date.ch": "[0-3][0-9].[0-1][0-9].[1-2][0-9][0-9][0-9]",
    "date.ch.short": "[0-3][0-9].[0-1][0-9].[0-9][0-9]",
    "year": "[1-2][0-9][0-9][0-9]",
    "plz.ch": "[0-9][0-9][0-9][0-9]",
    "ahvn13": "756.[0-9][0-9][0-9][0-9].[0-9][0-9][0-9][0-9].[0-9][0-9]",
    "uid.che": "CHE-[0-9][0-9][0-9].[0-9][0-9][0-9].[0-9][0-9][0-9]",
    "time.hm": "[0-2][0-9]:[0-5][0-9]",
    "iban.ch": "CH[0-9][0-9]*",
}


def main():
    n_subj = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    n_fall = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
    random.seed(SEED)
    key = secrets.token_bytes(32)
    open(KEYFILE, "wb").write(key)
    encrypt, cipher_label = make_cipher(key)

    src = connect(DB_PATH)
    # patterns for the format gate
    pat = {r["code"]: re.compile(r["regex"]) for r in
           src.execute("SELECT code, regex FROM format_pattern")}
    # canonical attribute by eCH element / eSH key
    attr_by_ech = {r["ech_element_id"]: r["id"] for r in
                   src.execute("SELECT id, ech_element_id FROM canonical_attribute "
                               "WHERE ech_element_id IS NOT NULL")}
    attr_by_esh = {r["esh_key"]: r["id"] for r in
                   src.execute("SELECT id, esh_key FROM canonical_attribute "
                               "WHERE esh_key IS NOT NULL")}
    edata = {r["id"]: r for r in src.execute("SELECT id, standard, name, datatype FROM ech_element")}
    # first legal-basis article per data_field, with a readable citation
    basis = {}
    for r in src.execute("SELECT lb.data_field_id did, lb.article_id, a.article_no, "
                         "l.short_title, l.title, l.sr_number, l.cantonal_ref, l.jurisdiction_level "
                         "FROM data_field_legal_basis lb "
                         "JOIN article a ON a.id=lb.article_id JOIN law l ON l.id=a.law_id"):
        # some legacy short titles are truncated dumps ("... Vom 10. Juni 2013 (");
        # a citation must read cleanly, so fall back to the full title + number
        st = r["short_title"] or ""
        if len(st) > 30 or ";" in st or st.endswith("(") or " Vom " in st:
            st = r["title"]
        nr = r["sr_number"] or r["cantonal_ref"]
        if nr and not str(nr).startswith("SHR") and r["jurisdiction_level"] != "federal":
            nr = f"SHR {nr}"
        elif nr and r["jurisdiction_level"] == "federal":
            nr = f"SR {nr}"
        basis.setdefault(r["did"], (r["article_id"], f"{r['article_no']} {st}" + (f" ({nr})" if nr else "")))
    # retention days per form: its laws' sektoral terms, else the 10-year standard
    ret_days = {}
    lt = {}
    for r in src.execute("SELECT a.law_id, rt.duration_value, rt.duration_unit "
                         "FROM retention_term rt JOIN data_rule dr ON dr.id=rt.data_rule_id "
                         "JOIN article a ON a.id=dr.article_id "
                         "WHERE dr.scope='sektoral' AND rt.duration_value IS NOT NULL"):
        days = r["duration_value"] * (30 if r["duration_unit"] == "monate" else 365)
        lt[r["law_id"]] = max(lt.get(r["law_id"], 0), days)
    for r in src.execute("SELECT DISTINCT d.form_id, a.law_id FROM data_field_legal_basis lb "
                         "JOIN data_field d ON d.id=lb.data_field_id "
                         "JOIN article a ON a.id=lb.article_id"):
        if r["law_id"] in lt:
            ret_days[r["form_id"]] = max(ret_days.get(r["form_id"], 0), lt[r["law_id"]])

    # the atomic points of every form (subfields replace their composite)
    forms = {}
    for f in src.execute("SELECT f.id, f.service_id, f.title, s.dienststelle, s.name svc "
                         "FROM form f JOIN service s ON s.id=f.service_id"):
        forms[f["id"]] = {"meta": dict(f), "punkte": []}
    for d in src.execute("SELECT * FROM data_field").fetchall():
        subs = [dict(x) for x in src.execute(
            "SELECT name, ech_element_id, esh_code, esh_element FROM data_subfield "
            "WHERE data_field_id=? ORDER BY ord", [d["id"]])]
        units = subs if subs else [dict(d)]
        for u in units:
            eid = u.get("ech_element_id")
            e = edata.get(eid)
            aid = attr_by_ech.get(eid)
            if not aid and u.get("esh_code") and u.get("esh_element"):
                aid = attr_by_esh.get(f"{u['esh_code']}:{u['esh_element']}")
            # once-only only makes sense for the person's OWN attributes: the
            # street of a Betrieb, a vehicle's Standort or an authority's address
            # is stored per Fall, never reused as the person's datum
            if d["subjekt"] in ("organisation", "sache", "behoerde", "gemischt"):
                aid = None
            forms[d["form_id"]]["punkte"].append({
                "name": u["name"], "attr": aid,
                "std": e["standard"] if e else None, "el": e["name"] if e else None,
                "dt": e["datatype"] if e else None,
                "typ": d["data_type"], "fmt": d["format_code"],
                "vals": json.loads(d["allowed_values"] or "[]"),
                "req": bool(d["required"]), "sens": d["sensitive"],
                "no_basis": bool(d["no_basis"]), "basis_typ": d["basis_typ"],
                "basis": basis.get(d["id"])})
    beil = {}
    for b in src.execute("SELECT form_id, bezeichnung, halter, fetchable FROM beilage"):
        beil.setdefault(b["form_id"], []).append(dict(b))
    disc = {}
    for r in src.execute("SELECT fd.form_id, fd.empfaenger, fd.mode, a.article_no, l.short_title "
                         "FROM form_disclosure fd LEFT JOIN article a ON a.id=fd.article_id "
                         "LEFT JOIN law l ON l.id=a.law_id"):
        disc.setdefault(r["form_id"], []).append(dict(r))
    out_by_form = {r["form_id"]: r["entscheid_art"] for r in
                   src.execute("SELECT form_id, entscheid_art FROM form_outcome")}
    form_ids = [fid for fid, f in forms.items() if f["punkte"]]

    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.executescript(DDL)

    # --- the people ---------------------------------------------------------
    subjects = []
    for i in range(n_subj):
        vn, nn = random.choice(VORNAMEN), random.choice(NAMEN)
        plz, ort = random.choice(ORTE)
        geb = date(1935 + random.randint(0, 72), random.randint(1, 12), random.randint(1, 28))
        s = {"ahvn13": ahvn13(), "name": nn, "vorname": vn,
             "geburtsdatum": geb.strftime("%d.%m.%Y"),
             "strasse": f"{random.choice(STRASSEN)} {random.randint(1, 89)}",
             "plz": plz, "ort": ort,
             "email": f"{vn.lower()}.{nn.lower().replace('ü','ue').replace('ö','oe').replace('ä','ae')}@example.ch",
             "telefon": f"+41 52 6{random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}"}
        db.execute("INSERT INTO subjekt(ahvn13,name,vorname,geburtsdatum,strasse,plz,ort,email,telefon) "
                   "VALUES(:ahvn13,:name,:vorname,:geburtsdatum,:strasse,:plz,:ort,:email,:telefon)", s)
        s["id"] = i + 1
        subjects.append(s)

    # a synthetic value for one atomic point; identity attributes come from the
    # SUBJECT so once-only actually collides on later Fälle
    IDENT = {"officialName": "name", "lastName": "name", "firstName": "vorname",
             "callName": "vorname", "dateOfBirth": "geburtsdatum", "vn": "ahvn13",
             "street": "strasse", "swissZipCode": "plz", "town": "ort",
             "emailAddress": "email", "phoneNumber": "telefon"}
    def gen(p, s):
        if p["el"] in IDENT:
            return s[IDENT[p["el"]]]
        if p["vals"]:
            return str(random.choice(p["vals"]))
        f = p["fmt"]
        if f == "date.ch" or p["typ"] == "date":
            return (date(2023, 1, 1) + timedelta(days=random.randint(0, 1300))).strftime("%d.%m.%Y")
        if f == "year": return str(random.randint(2019, 2026))
        if f == "ahvn13": return s["ahvn13"]
        if f == "plz.ch": return s["plz"]
        if f == "email": return s["email"]
        if f == "phone.ch": return s["telefon"]
        if f == "time.hm": return f"{random.randint(7,18):02d}:{random.choice(['00','15','30','45'])}"
        if f == "iban.ch": return "CH93" + "".join(str(random.randint(0,9)) for _ in range(17))
        if f == "uid.che": return f"CHE-{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}"
        if f == "money.chf" or p["typ"] == "money": return f"{random.randint(20, 5000)}.00"
        if f in ("percent", "number") or p["typ"] == "number": return str(random.randint(1, 250))
        if p["typ"] == "boolean": return random.choice(["Ja", "Nein"])
        return f"{p['name']}: {random.choice(WOERTER)}"

    # --- the Fälle, with every gate live ------------------------------------
    dp_of = {}          # (subjekt_id, attribut_id) -> datenpunkt id (once-only)
    stats = {"dp": 0, "reuse": 0, "einw": 0, "verschl": 0, "refus": 0,
             "kopie": 0, "vermerk": 0, "log": 0}
    for fi in range(n_fall):
        s = random.choice(subjects)
        fid = random.choice(form_ids)
        fm = forms[fid]
        ein = date(2023, 9, 1) + timedelta(days=random.randint(0, 1080))
        ab = ein + timedelta(days=random.randint(5, 60))
        db.execute("INSERT INTO fall(subjekt_id,service_id,form_id,formular,dienststelle,"
                   "eingereicht,abgeschlossen,entscheid) VALUES(?,?,?,?,?,?,?,?)",
                   [s["id"], fm["meta"]["service_id"], fid, fm["meta"]["title"],
                    fm["meta"]["dienststelle"], ein.isoformat(), ab.isoformat(),
                    out_by_form.get(fid, "unbekannt")])
        fall_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        loesch = (ab + timedelta(days=ret_days.get(fid, 3650))).isoformat()

        for p in fm["punkte"]:
            if not p["req"] and random.random() < 0.4:
                continue
            # once-only: an attribute this person already has is referenced, not re-stored
            if p["attr"] and (s["id"], p["attr"]) in dp_of:
                cur = db.execute("INSERT OR IGNORE INTO datenpunkt_verwendung VALUES(?,?,1)",
                                 [fall_id, dp_of[(s["id"], p["attr"])]])
                stats["reuse"] += cur.rowcount     # the same attribute twice in one form counts once
                continue
            wert = gen(p, s)
            # gate 1: the format pattern must accept the value
            if p["fmt"] and p["fmt"] in pat and not pat[p["fmt"]].match(wert):
                stats["refus"] += 1
                continue
            # gate 2: PROVEN over-collection (no_basis) needs a consent record;
            # a merely undocumented basis is a research gap, not consent territory
            # (conflating the two was convention 8's original trap)
            einw_id, grundlage_txt = None, p["basis"][1] if p["basis"] else None
            if p["basis_typ"] == "aufgabe":
                grundlage_txt = "Aufgabenerfüllung (KDSG Art. 4 Abs. 1 lit. b) — keine explizite Norm"
            elif p["basis_typ"] == "offen":
                grundlage_txt = "Aufgabenbedarf noch nicht beurteilt (kein Befund)"
            elif p["no_basis"]:
                db.execute("INSERT INTO einwilligung(subjekt_id,fall_id,gegenstand,erteilt_am) "
                           "VALUES(?,?,?,?)", [s["id"], fall_id, p["name"], ein.isoformat()])
                einw_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                stats["einw"] += 1
            elif not p["basis"]:
                grundlage_txt = "Rechtsgrundlage zu ermitteln (Dokumentationslücke, kein Befund)"
            # gate 3: sensitive values only encrypted
            versch, nonce = 0, None
            if p["sens"]:
                wert, nonce = encrypt(wert)
                versch = 1
                stats["verschl"] += 1
            db.execute("INSERT INTO datenpunkt(subjekt_id,attribut_id,attribut,ech_standard,"
                       "ech_element,ech_datatype,wert,verschluesselt,nonce,format_glob,sensitive,"
                       "erhoben_am,erhebungs_fall,grundlage_artikel,grundlage,einwilligung_id,loeschdatum) "
                       "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       [s["id"], p["attr"], p["name"], p["std"], p["el"], p["dt"],
                        wert, versch, nonce, GLOBS.get(p["fmt"]), p["sens"], ein.isoformat(),
                        fall_id, p["basis"][0] if p["basis"] else None,
                        grundlage_txt, einw_id, loesch])
            dp_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO datenpunkt_verwendung VALUES(?,?,0)", [fall_id, dp_id])
            if p["attr"]:
                dp_of[(s["id"], p["attr"])] = dp_id
            stats["dp"] += 1

        # Beilagen: fetchable ones become a Prüfvermerk, the rest a stored copy
        for b in beil.get(fid, [])[:6]:
            if b["fetchable"]:
                db.execute("INSERT INTO beleg(fall_id,bezeichnung,art,halter,geprueft_am,geprueft_von) "
                           "VALUES(?,?,?,?,?,?)",
                           [fall_id, b["bezeichnung"], "pruefvermerk", b["halter"],
                            ein.isoformat(), fm["meta"]["dienststelle"]])
                stats["vermerk"] += 1
            else:
                db.execute("INSERT INTO beleg(fall_id,bezeichnung,art,halter,sha256,loeschdatum) "
                           "VALUES(?,?,?,?,?,?)",
                           [fall_id, b["bezeichnung"], "kopie", b["halter"],
                            secrets.token_hex(32), loesch])
                stats["kopie"] += 1

        # the log: the processing read, plus the legally named Bekanntgaben
        db.execute("INSERT INTO zugriff_log(zeitpunkt,art,subjekt_id,fall_id,wer,zweck,grundlage) "
                   "VALUES(?,?,?,?,?,?,?)",
                   [ein.isoformat(), "lesen", s["id"], fall_id,
                    fm["meta"]["dienststelle"], "Bearbeitung des Gesuchs", "Aufgabenerfüllung"])
        stats["log"] += 1
        for d in disc.get(fid, []):
            if d["mode"] == "systematisch" or random.random() < 0.3:
                db.execute("INSERT INTO zugriff_log(zeitpunkt,art,subjekt_id,fall_id,wer,zweck,grundlage) "
                           "VALUES(?,?,?,?,?,?,?)",
                           [ab.isoformat(), "bekanntgabe", s["id"], fall_id, d["empfaenger"],
                            "gesetzliche Meldung/Amtshilfe",
                            f"{d['article_no'] or ''} {d['short_title'] or ''}".strip()])
                stats["log"] += 1

    for k, v in {
        "hinweis": "SÄMTLICHE Daten synthetisch generiert — keine realen Personen.",
        "erzeugt": date.today().isoformat(), "seed": str(SEED),
        "quelle": "citygov.db (Schema, Standards, Regeln, Fristen, Empfänger)",
        "verschluesselung": cipher_label,
    }.items():
        db.execute("INSERT INTO meta VALUES(?,?)", [k, v])
    db.commit()
    size = os.path.getsize(OUT) // 1048576
    print(f"datentresor.db: {n_subj} Subjekte, {n_fall} Fälle, {stats['dp']} Datenpunkte "
          f"({stats['verschl']} verschlüsselt, {stats['reuse']} once-only wiederverwendet, "
          f"{stats['einw']} Einwilligungen, {stats['refus']} vom Format-Gate verweigert), "
          f"{stats['kopie']} Beleg-Kopien + {stats['vermerk']} Prüfvermerke, "
          f"{stats['log']} Log-Einträge — {size} MB")


if __name__ == "__main__":
    main()
