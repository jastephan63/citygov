#!/usr/bin/env python3
"""Load the official eCH-0049 topic catalogues (Themenkataloge, V4.00,
Genehmigt) — the Swiss structure for grouping public services from the
perspective of the person or business who needs them ("Lebenslagen").

Two catalogues, two levels each (eCH-0141): Themenbereich -> Themengruppe.
  privat       Beilage 1-1, Privatpersonen (natürliche Personen)
  unternehmen  Beilage 2-1, Unternehmen (juristische Personen, Körperschaften)

The lists below are copied from Darstellung 1 of each annex. Gate: every
Bereich and every Gruppe must appear verbatim in the text of the official
PDF (quellen/ech-0049/, downloaded from ech.ch), whitespace collapsed and
line-break hyphenation removed — nothing enters that the standard does not
say. Staging -> validate -> swap. Idempotent.

    python3 scripts/load_themenkatalog.py
"""
import os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PDF = {"privat": os.path.join(ROOT, "quellen/ech-0049/eCH-0049_V4.00_Beilage1_Privatpersonen.pdf"),
       "unternehmen": os.path.join(ROOT, "quellen/ech-0049/eCH-0049_V4.00_Beilage2_Unternehmen.pdf")}

KATALOG = {
    "privat": [
        ("Persönliches", ["Aufenthaltsbewilligungen", "Ausweise und Bescheinigungen", "Einbürgerung",
                          "Zivilstand", "Geburt", "Adoption", "Todesfall", "Wohnen und Umziehen",
                          "Versicherungen", "Kinder und Jugendliche", "Pflege", "Religion", "Tiere", "Sport"]),
        ("Gesundheit und Soziales", ["AHV / IV", "Krankenversicherung", "Soziale Sicherheit", "Behinderung",
                                     "Prävention", "Sucht und Drogen", "Konsumentenschutz",
                                     "Lebensmittelsicherheit"]),
        ("Arbeit", ["Arbeitnehmende", "Arbeitslosigkeit", "Arbeitskonflikt", "Berufliche Selbständigkeit",
                    "Pensionierung"]),
        ("Bildung und Forschung", ["Vorschule", "Obligatorische Schulzeit", "Mittelschulen", "Universität",
                                   "Fachhochschule", "Stipendien und Darlehen", "Berufliche Grundbildung",
                                   "Erwachsenenbildung und Weiterbildung", "Wissenschaftsförderung"]),
        ("Umwelt und Bauen", ["Boden, Natur und Landschaft", "Luft und Klima", "Energie", "Lärm", "Abfall",
                              "Chemie und Gifte", "Baubewilligungen", "Raumplanung", "Grundbuch", "Eigentum"]),
        ("Mobilität", ["Schiene und öffentlicher Verkehr", "Strasse", "Langsamverkehr", "Flugverkehr",
                       "Schifffahrt"]),
        ("Kultur und Medien", ["Kulturelle Einrichtungen", "Kulturförderung",
                               "Bewilligungspflichtige Veranstaltungen", "Archive und Bibliotheken", "Medien",
                               "Internet", "Telekommunikation"]),
        ("Staat und Recht", ["Demokratie", "Konsularischer Schutz", "Gleichstellung von Frau und Mann",
                             "Rassismus", "Bundessteuern", "Kantonale Steuern", "Gemeindesteuern", "Zölle",
                             "Betreibung und Konkurs", "Strafregister und Strafverfahren", "Zivilverfahren",
                             "Vormundschaft", "Ombudsstellen"]),
        ("Sicherheit", ["Armee", "Zivildienst", "Zivilschutz", "Bevölkerungsschutz", "Polizei", "Feuerwehr",
                        "Waffen"]),
    ],
    "unternehmen": [
        ("Arbeit und Soziales", ["Arbeitskonflikt", "Arbeitslosigkeit und Kurzarbeit", "Arbeitssicherheit",
                                 "Berufliche Selbständigkeit", "Gleichstellung", "Nachfolgeregelung",
                                 "Sozialversicherung", "Stellen und Stellenvermittlung", "Strafregister",
                                 "Versicherungen"]),
        ("Geld und Förderung", ["Betreibung und Konkurs", "Energie", "Geldgeber und Finanzen",
                                "Kinder- und Familienzulagen", "Kulturförderung", "Landwirtschaft", "Lohnwesen",
                                "Schulden", "Steuern und Abgaben", "Wirtschaft und Tourismus"]),
        ("Wissen und Bildung", ["Berufsbildung", "Erwachsenenbildung", "Forschung und Hochschulen",
                                "Geistiges Eigentum", "Networking", "Zertifizierungen"]),
        ("Verkehr und Energie", ["Bahn", "Baustellen", "Energieanlagen", "Luftfahrt", "Öffentlicher Verkehr",
                                 "Schifffahrt", "Seilbahnen und Lifte", "Strassenverkehr und Motorfahrzeuge"]),
        ("Standort und Umwelt", ["Bauen und Wohnen", "Chemikalien", "Denkmalschutz", "Wasser", "Immobilien",
                                 "Kehricht und Entsorgung", "Lärm", "Luft", "Raumplanung und Grundbuch",
                                 "Infrastruktur", "Umweltschutz"]),
        ("Bewilligungen und Meldepflichten", ["Arbeit und Beruf", "Bauen", "Energie und Verkehr",
                                              "Finanzwirtschaft", "Gewerbe", "Handelsregister", "Waffen",
                                              "Landwirtschaft und Veterinärwesen", "Medizin und Gesundheit",
                                              "Mehrwertsteuer", "Sozialversicherung", "Umwelt", "Wettbewerb"]),
        ("Internationales", ["Arbeitsbewilligung für Ausländer", "Grenzgänger", "Auslandschweizer",
                             "Import und Export", "Währungsfragen", "Zoll"]),
        ("Information und Statistik", ["Arbeit", "Bauen", "Bildung", "Kultur", "Land- und Forstwirtschaft",
                                       "Öffentliche Ausschreibungen", "Ombudsstellen", "Recht und Gerichte",
                                       "Sicherheit und Ordnung", "Umwelt", "Wirtschaft und Tourismus"]),
    ],
}

DDL = """
CREATE TABLE IF NOT EXISTS themenkatalog (
    id        INTEGER PRIMARY KEY,
    katalog   TEXT NOT NULL CHECK(katalog IN ('privat','unternehmen')),
    bereich   TEXT NOT NULL,
    gruppe    TEXT NOT NULL,
    ord       INTEGER NOT NULL,
    quelle    TEXT NOT NULL,
    UNIQUE(katalog, bereich, gruppe)
);
"""


def pdf_text(path):
    out = subprocess.run(["python3", os.path.join(HERE, "extract_law.py"), path],
                         capture_output=True, text=True, timeout=120).stdout
    t = re.sub(r"\s+", " ", out)
    # line-break hyphenation («Kurz- arbeit»), but keep real ones («Kinder- und»)
    t2 = re.sub(r"(\w)- (?!und\b|oder\b|bis\b)([a-zäöüß])", r"\1\2", t)
    return t, t2


def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    missing = []
    rows = []
    for kat, bereiche in KATALOG.items():
        if not os.path.exists(PDF[kat]):
            os.remove(st); print("ABORT: PDF fehlt", PDF[kat]); sys.exit(1)
        t, t2 = pdf_text(PDF[kat])
        ordn = 0
        for bereich, gruppen in bereiche:
            if bereich not in t and bereich not in t2:
                missing.append(f"{kat}: Bereich «{bereich}»")
            for g in gruppen:
                ordn += 1
                if g not in t and g not in t2:
                    missing.append(f"{kat}: Gruppe «{g}»")
                rows.append((kat, bereich, g, ordn, f"eCH-0049 V4.00 Beilage {'1-1' if kat == 'privat' else '2-1'}"))
    if missing:
        os.remove(st); print("ABORT — nicht im PDF:", *missing, sep="\n  "); sys.exit(1)
    # keep ids stable across runs (service assignments point at them)
    for kat, bereich, g, ordn, q in rows:
        c.execute("INSERT INTO themenkatalog(katalog,bereich,gruppe,ord,quelle) VALUES(?,?,?,?,?) "
                  "ON CONFLICT(katalog,bereich,gruppe) DO UPDATE SET ord=excluded.ord, quelle=excluded.quelle",
                  [kat, bereich, g, ordn, q])
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    n_p = sum(len(g) for _, g in KATALOG["privat"]); n_u = sum(len(g) for _, g in KATALOG["unternehmen"])
    print(f"eCH-0049: {n_p} Themengruppen Privatpersonen, {n_u} Unternehmen — alle im amtlichen PDF belegt")


if __name__ == "__main__":
    main()
