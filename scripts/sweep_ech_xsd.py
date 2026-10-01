#!/usr/bin/env python3
"""Re-sweep the official XSDs of every eCH standard the catalogue knows to have
one, pin the version we mapped against, and harvest the official code lists.

Why: the element catalogue (ech_element) was swept once, without recording
WHICH XSD version each element came from, and without the enumerations the
XSDs define (sex = 1/2/3, maritalStatus = 1..9, ...). Both matter: a mapping
against eCH-0044 4.1 is not the same claim as one against 4.0, and a form that
offers «ledig / verheiratet / …» as free text diverges from the code list the
exchange format expects.

What it does, per standard with n_elements>0:
  * GET https://www.ech.ch/de/ech/<code>, collect every *.xsd href on the page
    (soft-404 guard: the site serves its homepage for unknown codes)
  * download the XSDs into ech_xsd/<code>/ under their decoded, composed (NFC)
    file name (kept in the repo: they are the proof behind every element
    citation)
  * parse, prefix-agnostic (xs:/xsd:): schema version attribute, element
    names (to compare with the catalogue), simpleType enumerations
  * write ech_standard.xsd_version / xsd_file / xsd_swept_at and the table
    ech_codelist(standard, type_name, value, doc)

Read-only towards ech.ch. Staging -> validate -> swap. Network failures for a
standard are reported and leave that standard untouched.

    python3 scripts/sweep_ech_xsd.py [--offline]   (offline = parse what is on disk)
"""
import glob, html, os, re, shutil, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import date
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XSD_DIR = os.path.join(ROOT, "ech_xsd")
BASE = "https://www.ech.ch"
UA = {"User-Agent": "citygov-databank/1.0 (read-only sweep of public eCH XSDs)"}
SOFT404 = "Startseite eCH - E-Government Standards"
XS = "{http://www.w3.org/2001/XMLSchema}"

DDL = """
CREATE TABLE IF NOT EXISTS ech_codelist (
    id        INTEGER PRIMARY KEY,
    standard  TEXT NOT NULL REFERENCES ech_standard(code),
    type_name TEXT NOT NULL,      -- the named simpleType, or '@<complexType>.<element>' for an
                                  -- anonymous enumeration inline in that element
    value     TEXT NOT NULL,
    doc       TEXT,               -- xs:documentation of the value, if any
    UNIQUE(standard, type_name, value)
);
CREATE INDEX IF NOT EXISTS ix_codelist_std ON ech_codelist(standard);
"""


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def page_xsds(code):
    """Every .xsd link on the standard's page; [] on soft-404."""
    page = get(f"{BASE}/de/ech/{code.lower()}")
    if SOFT404 in page:
        return []
    hrefs = re.findall(r'href="([^"]+\.xsd)"', page)
    return sorted({html.unescape(h) for h in hrefs})


def parse_xsd(path):
    """(version, {element names}, [(type_name, value, doc)]) - prefix-agnostic."""
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return None, set(), []
    root = tree.getroot()
    version = root.get("version")
    names = set()
    for el in root.iter(XS + "element"):
        n = el.get("name")
        if n:
            names.add(n)
    codes = []

    def enums_of(st, key):
        for en in st.iter(XS + "enumeration"):
            v = en.get("value")
            if v is None:
                continue
            doc = None
            d = en.find(f"{XS}annotation/{XS}documentation")
            if d is not None and d.text:
                doc = re.sub(r"\s+", " ", d.text).strip()[:200]
            codes.append((key, v, doc))

    # named simpleTypes: keyed by their type name (the element's datatype)
    for st in root.iter(XS + "simpleType"):
        if st.get("name"):
            enums_of(st, st.get("name"))
    # anonymous simpleTypes inline in an element (eCH-0278 does this for most
    # of its value lists): keyed '@<complexType>.<element>' so a field mapped
    # to that element (context = the complexType) can find its code list
    for ct in root.iter(XS + "complexType"):
        cname = ct.get("name") or ""
        for el in ct.iter(XS + "element"):
            ename = el.get("name")
            if not ename:
                continue
            for st in el.findall(XS + "simpleType"):
                if st.find(f".//{XS}enumeration") is not None:
                    enums_of(st, f"@{cname}.{ename}")
    for el in root.findall(XS + "element"):          # top-level elements
        for st in el.findall(XS + "simpleType"):
            if st.find(f".//{XS}enumeration") is not None:
                enums_of(st, f"@.{el.get('name')}")
    return version, names, codes


# an illustrative supplement published next to the schema (eCH-0147 «V1.2
# Zusatzbestimmungen ÜDP illustrativ») is an example, not the standard
SUPPLEMENT = re.compile(r"illustrativ|zusatzbestimmung", re.I)


def own_files(code, files):
    """The standard's OWN schema files: named after the code, without the French
    twins (-4-1f) and without illustrative supplements — the files whose
    elements and enumerations may stand for this standard."""
    own = [f for f in files if os.path.basename(f).lower().startswith(code.lower())]
    own = [f for f in own if not re.search(r"-\d+-\d+f\.xsd$", f, re.I)] or own
    return [f for f in own if not SUPPLEMENT.search(os.path.basename(f))]


def _rank(code, f):
    """Sort key: highest version first; within a version the lowest part
    (eCH-0147_V1.2_T0 holds the types T1 and T2 import); ties by file name."""
    b = os.path.basename(f)[len(code):]
    m = re.search(r"[-_]v?(\d+)[-.](\d+)", b, re.I)
    ver = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
    t = re.search(r"_T(\d+)", b)
    return (-ver[0], -ver[1], int(t.group(1)) if t else 0, b)


def main_xsd(code, files):
    """The schema file of the standard ITSELF: eCH-0044-4-1.xsd, not the French
    twin (-4-1f), not an illustrative supplement and not an imported foreign
    standard (ili2.xsd and friends).

    Returns None when the standard publishes no own schema — pinning a foreign
    file as this standard's proof, and storing its enumerations as this
    standard's official code list, would be worse than recording nothing."""
    own = sorted(own_files(code, files), key=lambda f: _rank(code, f))
    return own[0] if own else None


def main():
    offline = "--offline" in sys.argv
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    cols = {r[1] for r in c.execute("PRAGMA table_info(ech_standard)")}
    for col in ("xsd_version", "xsd_file", "xsd_swept_at"):
        if col not in cols:
            c.execute(f"ALTER TABLE ech_standard ADD COLUMN {col} TEXT")
    # every standard with elements, plus every standard a field or subfield is
    # mapped to (even without elements) — so "swept, nothing found" is recorded
    used = "SELECT DISTINCT ech_standard_code FROM data_field WHERE ech_standard_code IS NOT NULL " \
           "UNION SELECT DISTINCT ech_standard_code FROM data_subfield WHERE ech_standard_code IS NOT NULL " \
           "UNION SELECT DISTINCT e.standard FROM data_field d JOIN ech_element e ON e.id=d.ech_element_id"
    stds = [r["code"] for r in c.execute(f"SELECT code FROM ech_standard WHERE n_elements>0 OR code IN ({used}) ORDER BY code")]
    cat = {}
    for r in c.execute("SELECT standard, name FROM ech_element"):
        cat.setdefault(r["standard"], set()).add(r["name"])
    ok = failed = 0
    n_codes = 0
    report = []
    for code in stds:
        d = os.path.join(XSD_DIR, code)
        os.makedirs(d, exist_ok=True)
        if not offline:
            try:
                links = page_xsds(code)
                for h in links:
                    url = h if h.startswith("http") else BASE + h
                    # the href is URL-encoded («%20%C3%9C»); the file keeps its real name
                    name = unicodedata.normalize("NFC", urllib.parse.unquote(os.path.basename(h)))
                    dest = os.path.join(d, name)
                    if not os.path.exists(dest):
                        open(dest, "wb").write(get(url, binary=True))
                        time.sleep(0.3)
                time.sleep(0.2)
            except Exception as e:
                failed += 1
                report.append(f"{code}: Netz {e}")
                continue
        files = sorted(glob.glob(os.path.join(d, "*.xsd")))
        mx = main_xsd(code, files)
        if not mx:
            failed += 1
            report.append(f"{code}: keine eigene XSD auf der Seite"
                          + (f" (nur fremde: {', '.join(os.path.basename(f) for f in files[:3])})" if files else ""))
            # never keep a version or code list that came from a foreign schema;
            # but record that the sweep looked, so the surfaces can say so
            c.execute("UPDATE ech_standard SET xsd_version=NULL, xsd_file=NULL, xsd_swept_at=? WHERE code=?",
                      [date.today().isoformat(), code])
            c.execute("DELETE FROM ech_codelist WHERE standard=?", [code])
            continue
        version, names, codes = parse_xsd(mx)
        # a standard may split its schema over several files (eCH-0147 T0/T1/T2,
        # eCH-0213 base + messages): union the standard's OWN files, skip the
        # French twins, illustrative supplements and imported foreign schemas
        for f in own_files(code, files):
            if f == mx or re.search(r"-\d+-\d+f\.xsd$", os.path.basename(f), re.I):
                continue
            v2, n2, c2 = parse_xsd(f)
            names |= n2
            codes += c2
            version = version or v2
        if not version:
            # some schemas carry no version attribute; the file name does
            # (eCH-0033-1-0.xsd, eCH-0147_V1.2_T0.xsd)
            m = re.search(r"[-_]v?(\d+)[-.](\d+)", os.path.basename(mx), re.I)
            version = f"{m.group(1)}.{m.group(2)} (aus Dateiname)" if m else None
        # sanity: the catalogue's elements should be in the freshly parsed file
        missing = cat.get(code, set()) - names
        if names and missing and len(missing) > 0.2 * max(1, len(cat.get(code, ()))):
            report.append(f"{code}: {len(missing)}/{len(cat.get(code, ()))} Katalog-Elemente nicht in {os.path.basename(mx)}")
        c.execute("UPDATE ech_standard SET xsd_version=?, xsd_file=?, xsd_swept_at=? WHERE code=?",
                  [version, os.path.relpath(mx, ROOT), date.today().isoformat(), code])
        c.execute("DELETE FROM ech_codelist WHERE standard=?", [code])
        for tname, v, doc in codes:
            c.execute("INSERT OR IGNORE INTO ech_codelist(standard, type_name, value, doc) VALUES(?,?,?,?)",
                      [code, tname, v, doc])
            n_codes += 1
        ok += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"XSD-Sweep: {ok} Standards gepinnt, {n_codes} Codelisten-Werte, {failed} ohne Ergebnis")
    for line in report:
        print("  ", line)


if __name__ == "__main__":
    main()
