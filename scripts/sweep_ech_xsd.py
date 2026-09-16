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
  * download the XSDs into ech_xsd/<code>/ (kept in the repo: they are the
    proof behind every element citation)
  * parse, prefix-agnostic (xs:/xsd:): schema version attribute, element
    names (to compare with the catalogue), simpleType enumerations
  * write ech_standard.xsd_version / xsd_file / xsd_swept_at and the table
    ech_codelist(standard, type_name, value, doc)

Read-only towards ech.ch. Staging -> validate -> swap. Network failures for a
standard are reported and leave that standard untouched.

    python3 scripts/sweep_ech_xsd.py [--offline]   (offline = parse what is on disk)
"""
import glob, html, os, re, shutil, sys, time, urllib.request
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
    type_name TEXT NOT NULL,      -- the simpleType that carries the enumeration
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
    for st in root.iter(XS + "simpleType"):
        tname = st.get("name")
        if not tname:
            continue
        for en in st.iter(XS + "enumeration"):
            v = en.get("value")
            if v is None:
                continue
            doc = None
            d = en.find(f"{XS}annotation/{XS}documentation")
            if d is not None and d.text:
                doc = re.sub(r"\s+", " ", d.text).strip()[:200]
            codes.append((tname, v, doc))
    return version, names, codes


def main_xsd(code, files):
    """The schema file of the standard itself: eCH-0044-4-1.xsd, not the
    French twin (-4-1f) and not an imported foreign standard."""
    own = [f for f in files if os.path.basename(f).lower().startswith(code.lower() + "-")]
    own = [f for f in own if not re.search(r"-\d+-\d+f\.xsd$", f, re.I)] or own
    own.sort(key=lambda f: [int(x) for x in re.findall(r"\d+", os.path.basename(f))], reverse=True)
    return own[0] if own else (files[0] if files else None)


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
    stds = [r["code"] for r in c.execute("SELECT code FROM ech_standard WHERE n_elements>0 ORDER BY code")]
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
                    dest = os.path.join(d, os.path.basename(h))
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
            report.append(f"{code}: keine XSD auf der Seite")
            continue
        version, names, codes = parse_xsd(mx)
        # a standard may split its schema over several files (eCH-0147 T0/T1/T2,
        # eCH-0213 base + messages): union the standard's OWN files, skip the
        # French twins and imported foreign schemas
        for f in files:
            b = os.path.basename(f).lower()
            if f == mx or not b.startswith(code.lower()) or re.search(r"-\d+-\d+f\.xsd$", b):
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
