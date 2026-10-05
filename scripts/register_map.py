#!/usr/bin/env python3
"""Once-only through registers: which Angaben and Beilagen of the Formulare a Swiss
register already holds (part E of the data-model programme of 2026-10-04).

Three curated layers, each loaded through a proof gate (the catalogue of
register_katalog.py must be loaded first):

  register_angabe   canonical Angabe (eCH element by id, or eSH key) × entity type
                    -> register. A rule names elements and the quote of the register's
                    content source that names this datum («alle Vornamen in der
                    richtigen Reihenfolge» -> eCH-0044 firstName …). An element that
                    does not exist in ech_element, an eSH key no data point carries,
                    or a quote that is not in the fetched source is refused.
  register_dokument documents a register or its office issues; the term must occur in
                    the quote. A Beilage whose name contains the term is attributed to
                    that register (besides beilage.halter, which is translated as is).
  register_zugriff  ingested articles about access, quoted: «kandidat» (a path the
                    canton's lawyers must check for each office) or «schranke» (a
                    secrecy duty). An article that is not ingested is NOT recorded —
                    its rule waits in ZUGRIFF and the run says so. No row ever says
                    «erlaubt»; every mapping without a candidate is «Zugriff offen —
                    rechtlich zu klären».

Levels of a data point × register (computed in export_register, once, in the export):
  standard    its eCH standard is one the register exchanges with (upper bound)
  element     a register_angabe rule names its element, the party is not judged
              (subjekt empty or «gemischt») and the element does not identify it
  bestaetigt  a rule names its element and the party matches: the judged subjekt equals
              the rule's entity, or the element is an IDENTIFIER of the party (a UID, an
              EGID, an E-GRID, a Stammnummer, a chip number — entitaet_aus_element; a
              name, an address or a legal form says nothing about whose it is)
A judged subjekt that contradicts the rule drops the point to «standard» (if the
standard is linked) or out. Units of a container element (document, attachment,
comment) or with pruefart «zuordnung» (the eCH mapping is in doubt) are never mapped.
A rule may also demand a context (KONTEXT: the dog database only where the Formular or
the label speaks of a dog — eCH-0185 dogDataType elements sit on people's and other
animals' fields too) or exclude one (the GWR holds the existing building, not the
heating or the areas a permit or a notification applies for; the IVZ holds no ships).

The prefill rule (quick win 1, corrected 2026-10-05 by the party layer):
prefill_korrigieren(forms, ang, std) sets the Einwohnerregister mark u.register on a
unit when a quoted Einwohnerregister rule names its element for a natural person
(level bestaetigt), and counts as «vorbefüllbar» (burden.prefillable, citygov_prefill.json
vorbefuellbar, the flows) only the required points that carry the mark AND belong to
the applicant (party role Gesuchsteller/in, entity natural person — the spouse's or a
child's Angaben only once the canton confirms that relations can be delivered: not by
default) AND are not «mehrdeutig» within that party AND ask for the register's
CURRENT value (the time rule below). The former figure stays as prefillable_bisher,
the excluded ones by reason in prefillable_ausgeschlossen. The model estimate uses the
existing burden model of export_json (MIN_ANGABE minutes per required input,
MIN_BEILAGE per Beilage); case numbers per service are canton data that the databank
does not have.

The time rule (2026-10-05, zeitbezug()): the register's entry holds the CURRENT value.
A point whose label (field name, for a Teilfeld «Feld | Teilfeld», folded) carries a
qualifier of another time is never filled from it, whatever its element:
  kuenftig  a later, new or planned value (neu, künftig, geplant, voraussichtlich,
            beabsichtigt, beantragt, nach dem Umzug …) — never filled;
  andere    an earlier value or another moment (früher, bisherig, ehemalig, vorherig,
            alte, letzte … Jahre, während, zuletzt, ursprünglich, beim Eintritt, zum
            Zeitpunkt, bei Abwesenheit, bei Realisierung, ledig, Geburtsname);
  wechsel   a change, an event or a period (Änderung, Wechsel, Mutation, Zuzug, Wegzug,
            Umzug, Ausreise, Einreise, Abmeldung, Heirat, Scheidung, Trennung,
            Einbürgerung, Dauer, Zeitraum, Aufenthalte, Wohnorte) or only a bare time
            preposition (seit, bis, ab).
The one exception: the element itself names that past value in the register's own
entry (ZEIT_EREIGNIS — Zuzug date and origin, Umzug date, Wegzug date and destination,
the date of the civil status, of the nationality, of the permit, of the health
insurance and the fire service duty, the name before marriage). It applies when the
label names the same event (the element's pattern), or carries only a bare preposition,
and never when the label names a conflicting circumstance (Zivilrechtlicher Wohnsitz IN
DER SCHWEIZ seit is not the Zuzug into the Gemeinde; a Trennung is not a civil status)
or a later value. A time word that qualifies a PERSON (neue Zeichnungsberechtigte,
Bewirtschafter neu, verantwortliche Person (bisher)) names which person, not which
value — that person's current data are meant (whose Angabe it is, the party layer
decides), so the phrase is not read as a time qualifier (ZEIT_PERSON). The death date
(ZEIT_NIE) is never filled from the submitting person's own profile. A point excluded
by the rule does not compete with the current value of its party either: «mehrdeutig»
compares only the points without time reference. Counted in
prefillable_ausgeschlossen.zeitbezug (the points the rule alone keeps out) and
vorbefuellung.zeitbezug; stamped as u.zeitbezug on the units that carry the
Einwohnerregister mark; citygov_prefill.json carries zeitbezug per point. The gate
(zeit_pruefen, part of pruefen): the patterns, the exception elements (each must be
named by a quoted Einwohnerregister rule), a fixed set of labelled examples
(ZEIT_BEISPIELE), and the reviewed eCH corrections of the same sweep
(quellen/korrekturen/prefill_inhalt_2026-10-05/: every entry with its old element,
reason, quote from the Formular text and second review; a correction is either pending
— every target still carries the old element — or applied, never half or overwritten;
a name-keyed verdict must name exactly the reviewed fields).

Commands
    python3 scripts/register_map.py              gate + load (staging -> validate -> swap);
                                                 a second run reports «unverändert»
    python3 scripts/register_map.py --pruefen    gate only
    python3 scripts/register_map.py --bericht [--json PATH]
                                                 the figures on today's data (builds the
                                                 export in memory with export_json.build,
                                                 writes nothing but PATH)
    python3 scripts/register_map.py --korrekturen
                                                 every quote of the correction files found
                                                 again in its Formular text and the state of
                                                 each correction (pending / applied); needs
                                                 pypdf for PDF Formulare (run it with a Python
                                                 that has it); writes nothing
Standard library only (--korrekturen reads the Formular files through rollen.py, which
imports pypdf only then); imported by validate_db.py (pruefen) and export_json.py.
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
import register_katalog as K

# the burden model of export_json.py (burden block): minutes per required input and
# per Beilage. export_json must use these two constants so both say the same.
MIN_ANGABE = 0.4
MIN_BEILAGE = 5.0
# the Einwohnerregister mark of export_json / export_llm / build_flows
REGISTER_STDS = ("eCH-0044", "eCH-0010", "eCH-0011", "eCH-0007", "eCH-0008")
CONTAINER = {"document", "attachment", "comment"}
TABELLEN = ("register_angabe", "register_dokument", "register_zugriff")
ENTITAETEN = ("natuerliche_person", "organisation", "sache", "jede")
STUFEN = ("standard", "element", "bestaetigt")


def _r(register, quelle, zitat, entitaet, ech=(), esh=(), aus_element=False, kontext=None, ohne=None):
    """One rule. aus_element: the element IDENTIFIES its party (UID, EGID, E-GRID, Stammnummer,
    chip number), so the level is «bestaetigt» even where no subjekt is judged; kontext /
    ohne: a pattern the unit's context (Formular title, field and part label, folded) must
    or must not contain."""
    return {"register": register, "quelle": quelle, "zitat": zitat, "entitaet": entitaet,
            "aus_element": aus_element, "ech": list(ech), "esh": list(esh), "kontext": kontext, "ohne": ohne}


# the unit context of the KONTEXT rules: «Hund» in the Formular or the label; the
# Bauprojekt of the GWR (planned or new heating and areas, the Formulare that apply
# for or notify an installation); ships are not in the IVZ
HUND = r"\bhund"
EQUIDE = r"equide|\bpferd|\besel\b|\bpony|maultier|maulesel|\bueln\b"
SCHIFF = r"schiff|\bboot"
GWR_PROJEKT_FLAECHE = r"\bneu\b|neubau|geplant|baugesuch"
GWR_PROJEKT_HEIZUNG = (r"geplant|bivalent|\bneu\b|neubau|entzug von waerme|waermeentzug|waermepumpe|energienachweis|"
                       r"waermeerzeuger|baugesuch|messprotokoll")
ZEMIS = r"zemis"


def falten(s):
    """Lower case, ä/ö/ü -> ae/oe/ue, sharp s -> ss, whitespace collapsed (for KONTEXT)."""
    t = (s or "").lower().replace("\u00df", "ss")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------
# Angaben: (standard, element name[, context]) — every context of the name unless
# one is given. Only data a source NAMES as register content; Bauprojekt data of
# the GWR are left out on purpose (they enter the GWR from the Baugesuch itself).
# ---------------------------------------------------------------------------
ANGABEN = [
    # Einwohnerregister: RHG Art. 6 and Gemeindegesetz Art. 88 Abs. 2
    _r("einwohnerregister", "fedlex_rhg",
       "AHV-Nummer nach Artikel 50c des Bundesgesetzes vom 20. Dezember 1946 über die Alters- und Hinterlassenenversicherung (AHVG);",
       "natuerliche_person", ech=[("eCH-0044", "vn")]),
    _r("einwohnerregister", "fedlex_rhg", "Gemeindenummer des Bundesamtes und amtlicher Gemeindename;",
       "natuerliche_person", ech=[("eCH-0007", "municipalityName"), ("eCH-0007", "municipalityId"),
                                  ("eCH-0011", "municipalityName")]),
    _r("einwohnerregister", "fedlex_rhg", "Wohnungsidentifikator nach dem GWR, Haushaltszugehörigkeit und Haushaltsart;",
       "natuerliche_person", ech=[("eCH-0011", "typeOfHousehold"), ("eCH-0011", "householdID")]),
    _r("einwohnerregister", "fedlex_rhg", "amtlicher Name und die anderen in den Zivilstandsregistern beurkundeten Namen einer Person;",
       "natuerliche_person", ech=[("eCH-0044", "officialName"), ("eCH-0044", "originalName"),
                                  ("eCH-0011", "officialName"), ("eCH-0011", "originalName"),
                                  ("eCH-0011", "nameData"), ("eCH-0010", "lastName")]),
    _r("einwohnerregister", "fedlex_rhg", "alle Vornamen in der richtigen Reihenfolge;",
       "natuerliche_person", ech=[("eCH-0044", "firstName"), ("eCH-0011", "firstName"), ("eCH-0010", "firstName")]),
    _r("einwohnerregister", "fedlex_rhg", "Wohnadresse und Zustelladresse einschliesslich Postleitzahl und Ort;",
       "natuerliche_person", ech=[("eCH-0010", "street"), ("eCH-0010", "houseNumber"), ("eCH-0010", "swissZipCode"),
                                  ("eCH-0010", "foreignZipCode"), ("eCH-0010", "town"), ("eCH-0010", "locality"),
                                  ("eCH-0010", "addressLine1"), ("eCH-0010", "addressLine2"),
                                  ("eCH-0010", "postOfficeBoxNumber"), ("eCH-0010", "country"),
                                  ("eCH-0010", "addressInformation"), ("eCH-0010", "mailAddress"),
                                  ("eCH-0010", "personMailAddress"), ("eCH-0011", "dwellingAddress"),
                                  ("eCH-0011", "contactAddress"), ("eCH-0011", "address")]),
    _r("einwohnerregister", "fedlex_rhg", "h. Geburtsdatum und Geburtsort; i. Heimatorte bei Schweizerinnen und Schweizern; j. Geschlecht; k. Zivilstand;",
       "natuerliche_person", ech=[("eCH-0044", "dateOfBirth"), ("eCH-0011", "dateOfBirth"), ("eCH-0011", "placeOfBirth"),
                                  ("eCH-0011", "placeOfOrigin"), ("eCH-0011", "originName"),
                                  ("eCH-0135", "placeOfOriginName"), ("eCH-0044", "sex"), ("eCH-0011", "sex"),
                                  ("eCH-0011", "maritalStatus"), ("eCH-0011", "dateOfMaritalStatus"),
                                  ("eCH-0011", "maritalData")]),
    _r("einwohnerregister", "fedlex_rhg", "Zugehörigkeit zu einer öffentlich-rechtlich oder auf andere Weise vom Kanton anerkannten Religionsgemeinschaft;",
       "natuerliche_person", ech=[("eCH-0011", "religion"), ("eCH-0011", "religionData")]),
    _r("einwohnerregister", "fedlex_rhg", "m. Staatsangehörigkeit; n. bei Ausländerinnen und Ausländern die Art des Ausweises;",
       "natuerliche_person", ech=[("eCH-0011", "nationalityData"), ("eCH-0011", "nationalityValidFrom"),
                                  ("eCH-0011", "residencePermit"), ("eCH-0011", "residencePermitValidFrom"),
                                  ("eCH-0011", "residencePermitValidTill"), ("eCH-0006", "residencePermit")]),
    _r("einwohnerregister", "fedlex_rhg", "o. Niederlassung oder Aufenthalt in der Gemeinde; p. Niederlassungsgemeinde oder Aufenthaltsgemeinde;",
       "natuerliche_person", ech=[("eCH-0011", "mainResidence"), ("eCH-0011", "hasMainResidence")]),
    _r("einwohnerregister", "fedlex_rhg", "q. bei Zuzug: Datum und Herkunftsgemeinde beziehungsweise Herkunftsstaat; r. bei Wegzug: Datum und Zielgemeinde beziehungsweise Zielstaat; s. bei Umzug in der Gemeinde: Datum;",
       "natuerliche_person", ech=[("eCH-0011", "arrivalDate"), ("eCH-0011", "comesFrom"), ("eCH-0011", "departureDate"),
                                  ("eCH-0011", "goesTo"), ("eCH-0011", "movingDate"),
                                  ("eCH-0011", "dwellingAddressValidFrom")]),
    _r("einwohnerregister", "fedlex_rhg", "t. Stimm- und Wahlrecht auf Bundes-, Kantons- und Gemeindeebene; u. Todesdatum.",
       "natuerliche_person", ech=[("eCH-0011", "deathDate")]),
    _r("einwohnerregister", "sh_gg", "Name und Vornamen der Eltern", "natuerliche_person",
       ech=[("eCH-0021", "nameOfParent")]),
    _r("einwohnerregister", "sh_gg", "gesetzliche Vertreterin oder gesetzlicher Vertreter mit Zustelladresse",
       "natuerliche_person", ech=[("eCH-0021", "guardianRelationship")]),
    _r("einwohnerregister", "sh_gg", "Krankenversicherung oder Befreiung von der Krankenversicherungspflicht",
       "natuerliche_person", ech=[("eCH-0021", "healthInsured"), ("eCH-0021", "insuranceName"),
                                  ("eCH-0021", "healthInsuranceData"), ("eCH-0021", "healthInsuranceValidFrom")]),
    _r("einwohnerregister", "sh_gg", "Feuerwehrpflicht", "natuerliche_person",
       ech=[("eCH-0021", "fireServiceData"), ("eCH-0021", "fireServiceValidFrom")]),
    _r("einwohnerregister", "sh_gg", "Beruf und Art der Erwerbstätigkeit", "natuerliche_person",
       ech=[("eCH-0021", "jobTitle"), ("eCH-0021", "kindOfEmployment")]),
    _r("einwohnerregister", "sh_gg", "Andere Vor- und Nachnamen", "natuerliche_person",
       ech=[("eCH-0011", "callName"), ("eCH-0011", "allianceName"), ("eCH-0011", "aliasName"),
            ("eCH-0011", "otherName")]),
    # GG Art. 88 Abs. 2 lit. h: the number in the foreigners' register (ZEMIS) — the element
    # otherPersonId carries any other number too (PIN, passport), so only with a ZEMIS label
    _r("einwohnerregister", "sh_gg", "bei Ausländerinnen und Ausländern: Nummer im Ausländerregister",
       "natuerliche_person", ech=[("eCH-0044", "otherPersonId"), ("eCH-0011", "otherPersonId")], kontext=ZEMIS),
    # Infostar: Personenstand (BJ)
    _r("infostar", "bj_zivilstand",
       "Der Begriff des Personenstandes umfasst neben den in direktem Zusammenhang mit einer Person stehenden Ereignissen über den Zivilstand (wie Geburt, Ehe, eingetragene Partnerschaft, Tod etc.)",
       "natuerliche_person", ech=[("eCH-0044", "dateOfBirth"), ("eCH-0011", "dateOfBirth"), ("eCH-0011", "placeOfBirth"),
                                  ("eCH-0011", "maritalStatus"), ("eCH-0011", "dateOfMaritalStatus"),
                                  ("eCH-0011", "maritalData"), ("eCH-0011", "deathDate")]),
    _r("infostar", "bj_zivilstand",
       "Angaben über den Personen- und Familienstand einer Person (wie Mündigkeit, Abstammung, Verhältnis zum Ehegatten oder Partner, Name und Staatsangehörigkeit).",
       "natuerliche_person", ech=[("eCH-0044", "officialName"), ("eCH-0044", "originalName"), ("eCH-0044", "firstName"),
                                  ("eCH-0011", "officialName"), ("eCH-0011", "originalName"), ("eCH-0011", "firstName"),
                                  ("eCH-0011", "nameData"), ("eCH-0011", "nationalityData"),
                                  ("eCH-0021", "nameOfParent"), ("eCH-0021", "personIdentificationPartner")]),
    _r("infostar", "bj_zivilstand", "In der Schweiz gilt die Zugehörigkeit zu einer Gemeinde (Bürgerrecht) ebenfalls als Element des Personenstandes.",
       "natuerliche_person", ech=[("eCH-0011", "placeOfOrigin"), ("eCH-0011", "originName"),
                                  ("eCH-0135", "placeOfOriginName")]),
    # ZEMIS: only the permit data (ZEMIS holds foreign nationals only — a name or a
    # birth date of a person whose nationality is unknown is not mapped)
    _r("zemis", "fedlex_zemisv",
       "die erstmaligen Kurzaufenthalts- oder Aufenthaltsbewilligungen sowie deren Erneuerung, Verlängerung, Änderung oder Widerruf und die arbeitsmarktlichen Vorentscheide;",
       "natuerliche_person", ech=[("eCH-0006", "residencePermit"), ("eCH-0006", "residencePermitBorder"),
                                  ("eCH-0011", "residencePermit"), ("eCH-0011", "residencePermitValidFrom"),
                                  ("eCH-0011", "residencePermitValidTill")]),
    # AHV-Versichertenregister (ZAS)
    _r("ahv_versichertenregister", "fedlex_ahvg", "die Versicherten und deren AHV-Nummer;", "natuerliche_person",
       ech=[("eCH-0044", "vn")]),
    # UID-Register (UIDG Art. 6, UIDV Art. 4)
    _r("uid_register", "fedlex_uidg", "UID, Status des Eintrags im UID-Register und UID-Ergänzung,", "jede",
       ech=[("eCH-0098", "uid"), ("eCH-0116", "uid"), ("eCH-0021", "uidOrganisationId"), ("eCH-0021", "UID"),
            ("eCH-0108", "uid"), ("eCH-0098", "organisationIdentification")], aus_element=True),
    # a name, an address, a status or a legal form identifies no organisation: «bestaetigt»
    # only where the field is judged to be an organisation's Angabe (subjekt)
    _r("uid_register", "fedlex_uidg", "Name, Firma oder Bezeichnung und Adresse,", "organisation",
       ech=[("eCH-0098", "organisationName"), ("eCH-0098", "organisationAdditionalName"), ("eCH-0098", "mainAddress"),
            ("eCH-0098", "businessAddress"), ("eCH-0108", "name"), ("eCH-0108", "mainAddress"),
            ("eCH-0010", "organisationName"), ("eCH-0010", "organisationNameAddOn1"),
            ("eCH-0010", "organisationMailAdress")]),
    _r("uid_register", "fedlex_uidg", "Status des Eintrags im Handelsregister,", "organisation",
       ech=[("eCH-0108", "commercialRegisterStatus")]),
    _r("uid_register", "fedlex_uidg", "Status des Eintrags im Mehrwertsteuerregister mit Beginn und Ende der Mehrwertsteuerpflicht,",
       "organisation", ech=[("eCH-0108", "vatUid")], aus_element=True),
    _r("uid_register", "fedlex_uidv", "wirtschaftliche Tätigkeit gemäss Allgemeiner Systematik der Wirtschaftszweige (NOGA);",
       "organisation", ech=[("eCH-0098", "nogaCode"), ("eCH-0115", "nogaCodeFull")]),
    _r("uid_register", "fedlex_uidv", "Datum der erstmaligen Eintragung in das Handelsregister;", "organisation",
       ech=[("eCH-0108", "commercialRegisterActivationDate")]),
    # Handelsregister (HRegV, Inhalt des Eintrags): the UID identifies, the Firma does not
    _r("handelsregister", "fedlex_hregv", "die Firma und die Unternehmens-Identifikationsnummer;", "organisation",
       ech=[("eCH-0098", "uid"), ("eCH-0116", "uid"), ("eCH-0021", "uidOrganisationId"), ("eCH-0021", "UID"),
            ("eCH-0098", "organisationIdentification")], aus_element=True),
    _r("handelsregister", "fedlex_hregv", "die Firma und die Unternehmens-Identifikationsnummer;", "organisation",
       ech=[("eCH-0098", "organisationName")]),
    _r("handelsregister", "fedlex_hregv", "der Sitz und das Rechtsdomizil;", "organisation",
       ech=[("eCH-0098", "headquarterMunicipality"), ("eCH-0098", "swissHeadquarter"), ("eCH-0098", "mainAddress"),
            ("eCH-0108", "mainAddress"), ("eCH-0108", "careOfAddressLine")]),
    _r("handelsregister", "fedlex_hregv", "c. die Rechtsform; d. der Zweck;", "organisation",
       ech=[("eCH-0098", "legalForm"), ("eCH-0108", "legalForm")]),
    _r("handelsregister", "fedlex_hregv", "e. das Datum der Statuten;", "organisation",
       esh=[("eSH-0019", "articlesAmendmentDate")]),
    _r("handelsregister", "fedlex_hregv", "f. die zur Vertretung berechtigten Personen.", "jede",
       esh=[("eSH-0019", "signatureType")]),
    # GWR (VGWR Art. 8 Abs. 2 and 3: buildings and dwellings, not Bauprojekte)
    _r("gwr", "fedlex_vgwr", "vom BFS zugewiesener Identifikator für Gebäude und gebäudeähnliche Objekte (EGID);", "sache",
       ech=[("eCH-0129", "EGID"), ("eCH-0211", "EGID"), ("eCH-0206", "EGID"), ("eCH-0216", "EGID")], aus_element=True),
    _r("gwr", "fedlex_vgwr", "b. Gebäudenummer des Kantons oder der Gemeinde;", "sache",
       ech=[("eCH-0129", "officialBuildingNo")], aus_element=True),
    _r("gwr", "fedlex_vgwr", "g. Gebäudekategorie;", "sache",
       ech=[("eCH-0129", "buildingCategory")], ohne=GWR_PROJEKT_FLAECHE),
    _r("gwr", "fedlex_vgwr", "i. Baudatum oder -periode und Abbruchdatum oder -periode des Gebäudes;", "sache",
       ech=[("eCH-0129", "dateOfConstruction"), ("eCH-0129", "periodOfConstruction"),
            ("eCH-0129", "yearOfConstruction")], ohne=GWR_PROJEKT_FLAECHE),
    _r("gwr", "fedlex_vgwr", "j. Gebäudedimensionen (Flächen, Volumen); k. Gebäudestruktur (Anzahl Stockwerke);", "sache",
       ech=[("eCH-0129", "energyRelevantSurface"), ("eCH-0129", "surfaceAreaOfBuilding"),
            ("eCH-0129", "numberOfFloors"), ("eCH-0216", "energyRelevantSurface")], ohne=GWR_PROJEKT_FLAECHE),
    _r("gwr", "fedlex_vgwr", "gebäudetechnische Hauptinstallationen (Heizsystem", "sache",
       ech=[("eCH-0129", "heatGeneratorHeating"), ("eCH-0129", "energySourceHeating"),
            ("eCH-0129", "heatGeneratorHotWater"), ("eCH-0129", "hotWater"),
            ("eCH-0206", "energySourceHeating"), ("eCH-0216", "thermotechnicalDeviceForHeating")],
       ohne=GWR_PROJEKT_HEIZUNG),
    _r("gwr", "fedlex_vgwr", "vom BFS zugewiesener Identifikator für Wohnung und wohnungsähnliche Objekte (EWID);", "sache",
       ech=[("eCH-0129", "EWID")], aus_element=True),
    _r("gwr", "fedlex_vgwr", "h. Wohnungsstruktur (Anzahl Zimmer, Kocheinrichtung, mehrstöckig);", "sache",
       ech=[("eCH-0129", "noOfHabitableRooms"), ("eCH-0129", "multipleFloor")], ohne=GWR_PROJEKT_FLAECHE),
    # Grundbuch (GBV Art. 18 and 26)
    _r("grundbuch", "fedlex_gbv", "die Gemeinde und eine Grundstücksnummer; ist die Gemeinde grundbuchmässig in mehrere Einheiten aufgeteilt, so werden auch diese angegeben;",
       "sache", ech=[("eCH-0129", "number", "buildingIdentificationType"), ("eCH-0129", "realestateIdentification"),
                     ("eCH-0129", "subDistrict"), ("eCH-0134", "realEstateNumber")], aus_element=True),
    _r("grundbuch", "fedlex_gbv", "für den Datenaustausch zwischen Informatiksystemen eine eidgenössische Grundstücksidentifikation (E-GRID).",
       "sache", ech=[("eCH-0129", "EGRID")], aus_element=True),
    _r("grundbuch", "fedlex_gbv", "den Namen und die Identifikation des Eigentümers oder der Eigentümerin, die Eigentumsform und das Erwerbsdatum",
       "jede", ech=[("eCH-0211", "owner"), ("eCH-0134", "ownershipPart"), ("eCH-0129", "accessionDate")]),
    _r("grundbuch", "fedlex_gbv", "die Dienstbarkeiten und Grundlasten;", "sache",
       ech=[("eCH-0134", "servitude")]),
    # amtliche Vermessung (Liegenschaften, E-GRID)
    _r("amtliche_vermessung", "cadastre_liegenschaften",
       "Zur Informationsebene Liegenschaften gehören die Grundstücke nach Artikel 655 Absatz 2 ZGB",
       "sache", ech=[("eCH-0129", "number", "buildingIdentificationType"), ("eCH-0129", "realestateIdentification")],
       aus_element=True),
    _r("amtliche_vermessung", "cadastre_liegenschaften",
       "Gestützt auf Artikel 18 GBV führte der Bund zu diesem Zweck die eindeutige Eidgenössische Grundstücksidentifikation (E-GRID) ein.",
       "sache", ech=[("eCH-0129", "EGRID")], aus_element=True),
    # Gebäudeversicherung (the insurance number type of eCH-0129; GebVG: every building insured)
    _r("gebaeudeversicherung", "xsd_ech_0129",
       '<xs:element name="insuranceNumber" type="eCH-0129:buildingInsuranceNumberType"/>',
       "sache", ech=[("eCH-0129", "insuranceNumber"), ("eCH-0211", "insuranceNumber")], aus_element=True),
    # IVZ (IVZV Anhang 1: vehicle and plate identification, make and type)
    _r("ivz", "fedlex_ivzv", "Identifikationsdaten – Stammnummer – Fahrgestellnummer", "sache",
       esh=[("eSH-0014", "vehicleMasterNumber"), ("eSH-0014", "chassisNumber")], aus_element=True, ohne=SCHIFF),
    _r("ivz", "fedlex_ivzv", "Nummer der Gesamtgenehmigung oder der Typengenehmigung – Markendaten – Typendaten", "sache",
       esh=[("eSH-0014", "vehicleMakeType"), ("eSH-0014", "vehicleMake")], ohne=SCHIFF),
    _r("ivz", "fedlex_ivzv", "Identifikationsdaten – Kontrollschildidentifikation", "sache",
       esh=[("eSH-0014", "licencePlateNumber")], aus_element=True, ohne=SCHIFF),
    # TVD (equids: UELN — the quote names equids only)
    _r("tvd", "fedlex_tvdv", "bei Equiden: Universal Equine Life Number (UELN) nach Artikel 15d Absatz 1 Buchstabe b TSV;",
       "sache", ech=[("eCH-0262", "individualAnimal")], aus_element=True, kontext=EQUIDE),
    # Hundedatenbank (TSV Art. 17 Abs. 3: data about the dog) — only where the Formular or the label
    # speaks of a dog: the field layer put dogDataType elements on people's and other animals' fields
    _r("hundedatenbank", "fedlex_tsv", "Bei der Kennzeichnung werden folgende Daten über den Hund erhoben: a. Name; b. Geschlecht; c. Geburtsdatum;",
       "sache", ech=[("eCH-0185", "name", "dogDataType"), ("eCH-0185", "sex", "dogDataType"),
                     ("eCH-0185", "birthDate", "dogDataType")], kontext=HUND),
    _r("hundedatenbank", "fedlex_tsv", "j. Mikrochipnummer.", "sache",
       ech=[("eCH-0185", "chipNumber", "dogDataType")], aus_element=True, kontext=HUND),
    # AGIS (ISLV Anhang 1: Betriebs- und Strukturdaten, Direktzahlungen)
    _r("agis", "fedlex_islv", "Identifikationsnummern der jeweiligen Betriebsform: Kantonale Betriebsnummer", "jede",
       ech=[("eCH-0261", "id")], aus_element=True),
    _r("agis", "fedlex_islv", "1.2.6 Gebiets- und Zonenzugehörigkeit", "jede",
       ech=[("eCH-0261", "agriculturalZone")]),
    _r("agis", "fedlex_islv", "2.1 Informationen zur Nutzung der Betriebsfläche", "jede",
       ech=[("eCH-0265", "areaSize"), ("eCH-0265", "cultivation")]),
    _r("agis", "fedlex_islv", "gehaltene Tiere pro Tierkategorie (nach Alters- oder Gewichtsklasse)", "jede",
       ech=[("eCH-0262", "animalCategoryPRIF")]),
    _r("agis", "fedlex_islv", "Daten zur Anmeldung für Direktzahlungsarten und zu Direktzahlungen", "jede",
       ech=[("eCH-0265", "directPaymentProgramme"), ("eCH-0265", "explicitDirectPaymentProgramme"),
            ("eCH-0265", "directPaymentAreaCategory")]),
]

# documents a register or its office issues (the term must occur in the quote)
DOKUMENTE = [
    ("infostar", "Personenstandsausweis", "bj_zivilstand",
     "Urkunden über den Personenstand und den Familienstand (Personenstandsausweis, Familienausweis, Partnerschaftsausweis, Ausweis über den registrierten Familienstand usw.) werden durch das Zivilstandsamt am Heimatort erstellt."),
    ("infostar", "Familienausweis", "bj_zivilstand",
     "Urkunden über den Personenstand und den Familienstand (Personenstandsausweis, Familienausweis, Partnerschaftsausweis, Ausweis über den registrierten Familienstand usw.) werden durch das Zivilstandsamt am Heimatort erstellt."),
    ("infostar", "Partnerschaftsausweis", "bj_zivilstand",
     "Urkunden über den Personenstand und den Familienstand (Personenstandsausweis, Familienausweis, Partnerschaftsausweis, Ausweis über den registrierten Familienstand usw.) werden durch das Zivilstandsamt am Heimatort erstellt."),
    ("einwohnerregister", "Heimatausweis", "sh_vewr",
     "kann bei der registerführenden Stelle die Ausstellung eines Heimatausweises verlangen."),
    ("ivz", "Fahrzeugausweis", "fedlex_ivzv", "Fahrzeugausweisdaten"),
    # no «Führerausweis»: IVZV names «Führerausweisdaten» only in the tachograph-card annex and in
    # IVZ-Massnahmen; IVZ-Personen holds «Ausweisdaten» of driving permits (Art. 6 lit. a) — a
    # document rule waits for a quote that names the Führerausweis itself
    ("vostra", "Strafregisterauszug", "fedlex_streg",
     "Im Bereich der Strafdatenverwaltung ist jedem Zugangsprofil ein eigener Strafregisterauszug zugeordnet, der online angezeigt oder gedruckt werden kann."),
    ("vostra", "Privatauszug", "fedlex_streg",
     "Der Privatauszug vermittelt Zugang zu den Daten des Behördenauszugs 4 (Art. 40), mit Ausnahme der Daten über hängige Strafverfahren (Art. 24)."),
    ("tvd", "TVD", "blw_tvd",
     "Im Auftrag des Bundesamts für Landwirtschaft wird die Tierverkehrsdatenbank (TVD) von der Identitas AG betrieben."),
]

# beilage.halter (the judged layer of load_verfahren.py) -> register; translated as is
HALTER = {"einwohnerregister": "einwohnerregister", "handelsregister": "handelsregister",
          "betreibungsregister": "betreibungsregister", "strafregister": "vostra",
          "steuerverwaltung": "steuerregister", "grundbuch": "grundbuch"}
# a document of another state is never held by a Swiss register (a Swiss document about
# a foreign national — «Meldebestätigung … bei ausländischen Personen» — is not meant)
AUSLAND = re.compile(r"Wohnsitzstaat|Herkunftsstaat|Heimatstaat|des Auslandes|aus dem Ausland|"
                     r"ausländische[rnms]? (?:Führer|Schiffsführer|Fahrzeug|Ausweis|Pass|Urkunde|Behörde|Register|Straf)",
                     re.I)
# the original is demanded: a register does not replace its return
ORIGINAL = re.compile(r"\boriginal", re.I)
# the document itself is handed in to be surrendered, exchanged or cancelled: a register
# entry does not replace handing it over
RUECKGABE = re.compile(r"umtausch|ausser\s*verkehr|verzicht|loeschung|\balle\b[^,;]*ausweise|zurueckgeben|rueckgabe|"
                       r"abzugeben|einzuziehen|abgeben")
# a copy of an identity document among alternatives («Kopie Pass / ID / … Familienausweis»): an
# identity proof, which a register entry does not replace
IDENTITAET = re.compile(r"\bpass\b|\bid\b|identitaetskarte")
# a Beilage that is a Formular, a Merkblatt or a guide is no document a register holds
KEIN_DOKUMENT = re.compile(r"formular|merkblatt|wegleitung|anleitung")
# not a document at all, whatever the judged holder (beilage.halter) says: a number is an Angabe
# («Steuerregister-Nummer (PID-Nummer)»), a figure about the Gemeinde is no document about a party
# («Einwohnerzahl der Gemeinde»), and a creditor's copy of the own claim is the creditor's paper
# («Kopie der Forderung an das Konkursamt …») — the review of 2026-10-05 found these four Beilagen
KEINE_URKUNDE = re.compile(r"register-?nummer|\(pid\b|\beinwohnerzahl|\bkopie der forderung")
# the applicant's own return or a plan the applicant annotates: no register holds it,
# even where the judged holder (beilage.halter) names the office
EIGENE_ANGABE = re.compile(r"steuererklaerung|selbstdeklaration|mit\s+(?:genauer\s+)?(?:bezeichnung|eintrag\w*|"
                           r"einzeichnung|markierung)|eingezeichnet|markiert")

# access: (register, law number (sr_number or cantonal_ref), article_no, art, adressat, quelle, zitat).
# Recorded only when the article is ingested; otherwise reported as waiting.
ZUGRIFF = [
    ("grundbuch", "211.432.1", "Art. 26", "kandidat", "Jede Person", "fedlex_gbv",
     "Jede Person kann vom Grundbuchamt, ohne ein Interesse glaubhaft zu machen, Auskunft oder einen Auszug über die folgenden rechtswirksamen Daten des Hauptbuchs verlangen:"),
    ("grundbuch", "211.432.1", "Art. 28", "kandidat",
     "Steuerbehörden und anderen Behörden des Bundes, der Kantone und der Gemeinden die Daten, die sie zur Erfüllung ihrer gesetzlichen Aufgaben benötigen",
     "fedlex_gbv",
     "Die Kantone können vorsehen, dass die Daten des Hauptbuchs, des Tagebuchs und der Hilfsregister den folgenden Personen und Behörden ohne Interessennachweis im Einzelfall elektronisch zugänglich gemacht werden:"),
    # the article names no addressee — «Auf Verlangen» says how, not who: adressat '' (the page says so)
    ("handelsregister", "221.411", "Art. 11", "kandidat", "", "fedlex_hregv",
     "Auf Verlangen gewähren die Handelsregisterämter Einsicht in das Hauptregister, in die Anmeldung und in die Belege"),
    ("steuerregister", "641.100", "Art. 127", "schranke", "Dritten", "sh_stg",
     "Wer mit dem Vollzug dieses Gesetzes betraut ist oder dazu beigezogen wird, muss über Tatsachen, die ihm bzw. ihr in Ausübung des Amtes bekannt werden, und über die Verhandlungen in den Behörden Stillschweigen bewahren und Dritten den Einblick in amtliche Akten verweigern."),
    ("steuerregister", "641.100", "Art. 127", "kandidat", "gegenüber inländischen Gerichts- und Verwaltungsbehörden", "sh_stg",
     "Das Finanzdepartement ist in den übrigen Fällen befugt, gegenüber inländischen Gerichts- und Verwaltungsbehörden Auskünfte aus den Steuerakten zu erteilen oder die kantonale Steuerverwaltung dazu zu ermächtigen, soweit ein öffentliches Interesse besteht."),
    ("steuerregister", "641.100", "Art. 128", "kandidat", "den Steuerbehörden des Bundes und der andern Kantone", "sh_stg",
     "Die Steuerbehörden erteilen den Steuerbehörden des Bundes und der andern Kantone kostenlos die benötigten Auskünfte"),
    # waits for the ingest of the Verordnung über das Einwohnerregister § 6 (only § 1 is ingested)
    ("einwohnerregister", "431.101", "§ 6", "kandidat", "Kantonale Stellen, welche zur Erfüllung ihrer Aufgaben Personendaten benötigen",
     "sh_vewr",
     "Kantonale Stellen, welche zur Erfüllung ihrer Aufgaben Personendaten benötigen, beziehen diese von der kantonalen Personendatenplattform, sofern keine besonderen Register oder Datensammlungen vorhanden sind."),
]


# ---------------------------------------------------------------------------
# helpers shared by the loader and the gate
# ---------------------------------------------------------------------------
def _has(conn, t):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [t]).fetchone())


def _texte(conn, qdir):
    """{quelle id: normalised snapshot text} for every register_quelle row whose
    snapshot exists and still has the recorded sha256, plus the error list."""
    texte, roh, fehler = {}, {}, []
    if not _has(conn, "register_quelle"):
        return texte, roh, fehler
    for r in conn.execute("SELECT id, url, datei, sha256 FROM register_quelle"):
        meta, text = K.snapshot_lesen(qdir, r["id"])
        if text is None:
            fehler.append(f"register_quelle {r['id']}: Text {r['datei']} fehlt in {qdir}")
        elif K.sha(text) != r["sha256"] or meta.get("url") != r["url"]:
            fehler.append(f"register_quelle {r['id']}: Text weicht vom geladenen Stand ab (sha256/url)")
        else:
            texte[r["id"]] = K.norm(text)
            roh[r["id"]] = text
    return texte, roh, fehler


# a holder quote names a body; an access word in a register's own sentence needs a quoted article
INHABER_WORT = re.compile(r"amt|ämter|stelle|verwaltung|behörde|kanton|gemeinde|bund|BFS|ASTRA|staatssekretariat|"
                          r"identitas|gebäudeversicherung|departement|zivilstands", re.I)
ZUGRIFF_WORT = re.compile(r"\b(?:bezieh\w*|bezog\w*|zugriff\w*|einsicht\w*|einseh\w*|abfrag\w*|auskunft|"
                          r"auskünfte)\b", re.I)
# a permission is never the databank's statement (whether an office may fetch is for the
# canton's lawyers): never in a register's own sentences, quoted article or not
ERLAUBNIS_WORT = re.compile(r"\b(?:erlaubt\w*|darf|dürfen|zulässig\w*|berechtigt\w*)\b", re.I)


def _gesetz_nr(s):
    return re.sub(r"^(SHR|SR)\s*", "", (s or "").strip())


def artikel_abschnitt(text, article_no):
    """The normalised text of one article inside a law snapshot: from its heading line
    («Art. 26 …», «Art. 127», «§ 6») to the next article heading."""
    no = article_no.strip()
    m = re.match(r"(Art\.|§)\s*(\S+)", no)
    if not m:
        return ""
    kopf = re.compile(rf"^{re.escape(m.group(1))}\s*{re.escape(m.group(2))}(\s|$)")
    lines = text.split("\n")
    out, inside = [], False
    for ln in lines:
        if not inside and kopf.match(ln):
            inside = True
        elif inside and re.match(r"^(Art\.|§)\s*\d", ln):
            break
        if inside:
            out.append(ln)
    return K.norm("\n".join(out))


def _esh_genutzt(conn):
    return {(r[0], r[1]) for r in conn.execute(
        "SELECT esh_code, esh_element FROM data_field WHERE esh_code IS NOT NULL "
        "UNION SELECT esh_code, esh_element FROM data_subfield WHERE esh_code IS NOT NULL")}


# ---------------------------------------------------------------------------
# rows + loader gate
# ---------------------------------------------------------------------------
def zeilen(conn, qdir):
    fehler, hinweise = [], []
    if not _has(conn, "register") or not conn.execute("SELECT COUNT(*) FROM register").fetchone()[0]:
        return None, ["kein Register-Katalog in der Databank — erst scripts/register_katalog.py laden"], hinweise
    texte, roh, fehler = _texte(conn, qdir)
    registers = {r[0] for r in conn.execute("SELECT code FROM register")}
    elemente = {}
    for r in conn.execute("SELECT id, standard, name, context FROM ech_element"):
        elemente.setdefault((r["standard"], r["name"]), []).append((r["id"], r["context"]))
    esh_codes = {r[0] for r in conn.execute("SELECT code FROM esh_standard")}
    esh_genutzt = _esh_genutzt(conn)

    angaben = {}
    for i, rule in enumerate(ANGABEN):
        reg, q, z = rule["register"], rule["quelle"], rule["zitat"]
        tag = f"Angabe-Regel {i + 1} ({reg})"
        if reg not in registers:
            fehler.append(f"{tag}: Register fehlt im Katalog"); continue
        if rule["entitaet"] not in ENTITAETEN:
            fehler.append(f"{tag}: Entität {rule['entitaet']} unbekannt"); continue
        if q not in texte:
            fehler.append(f"{tag}: Quelle {q} nicht geladen oder ohne gültigen Text"); continue
        if len(K.norm(z)) < 12 or K.norm(z) not in texte[q]:
            fehler.append(f"{tag}: Zitat nicht in {q}: «{z[:80]}»"); continue
        if not rule["ech"] and not rule["esh"]:
            fehler.append(f"{tag}: nennt kein Element"); continue
        keys = []
        for spec in rule["ech"]:
            std, name = spec[0], spec[1]
            ctx = spec[2] if len(spec) > 2 else None
            ids = [eid for eid, c in elemente.get((std, name), []) if ctx is None or c == ctx]
            if not ids:
                fehler.append(f"{tag}: Element {std}·{name}{'@' + ctx if ctx else ''} gibt es in ech_element nicht")
            keys += [(f"ech:{eid}", eid, None, None) for eid in ids]
        for code, el in rule["esh"]:
            if code not in esh_codes:
                fehler.append(f"{tag}: eSH-Code {code} fehlt in esh_standard")
            elif (code, el) not in esh_genutzt:
                fehler.append(f"{tag}: eSH-Schlüssel {code}·{el} trägt kein Datenpunkt")
            else:
                keys.append((f"esh:{code}:{el}", None, code, el))
        bad_rx = [x for x in (rule["kontext"], rule["ohne"]) if x and not _rx_ok(x)]
        if bad_rx:
            fehler.append(f"{tag}: Kontextmuster ungültig: {bad_rx}"); continue
        for angabe, eid, code, el in keys:
            k = (reg, angabe, rule["entitaet"])
            if k not in angaben:            # the first rule that names it keeps it (deterministic)
                angaben[k] = (reg, angabe, eid, code, el, rule["entitaet"], int(rule["aus_element"]), q, z,
                              rule["kontext"], rule["ohne"])

    dokumente = {}
    for reg, begriff, q, z in DOKUMENTE:
        if reg not in registers:
            fehler.append(f"Dokument {begriff}: Register {reg} fehlt"); continue
        if q not in texte or K.norm(z) not in texte[q]:
            fehler.append(f"Dokument {begriff}: Zitat nicht in {q}"); continue
        if begriff.lower() not in z.lower():
            fehler.append(f"Dokument {begriff}: der Begriff steht nicht im Zitat"); continue
        dokumente[(reg, begriff)] = (reg, begriff, q, z)

    gesetze = {}
    for r in conn.execute("SELECT id, sr_number, cantonal_ref FROM law"):
        for nr in (r["sr_number"], r["cantonal_ref"]):
            if nr:
                gesetze.setdefault(_gesetz_nr(nr), []).append(r["id"])
    titel = {r[0]: r[1] for r in conn.execute("SELECT id, titel FROM register_quelle")}
    zugriff = {}
    for reg, nr, art_no, art, adressat, q, z in ZUGRIFF:
        tag = f"Zugriff {reg} {art_no} ({nr})"
        if reg not in registers:
            fehler.append(f"{tag}: Register fehlt"); continue
        if art not in ("kandidat", "schranke"):
            fehler.append(f"{tag}: Art {art} — nur «kandidat» oder «schranke»"); continue
        law_ids = gesetze.get(nr, [])
        arts = [r[0] for lid in law_ids for r in conn.execute(
            "SELECT id FROM article WHERE law_id=? AND article_no=?", [lid, art_no])]
        if not arts:
            hinweise.append(f"{tag}: Artikel nicht ingestiert — Zugriff bleibt «offen — rechtlich zu klären»")
            continue
        if q not in texte:
            fehler.append(f"{tag}: Quelle {q} nicht geladen"); continue
        if nr not in (titel.get(q) or ""):
            fehler.append(f"{tag}: Quelle {q} ist nicht der Text dieses Gesetzes"); continue
        abschnitt = artikel_abschnitt(roh[q], art_no)
        if not abschnitt:
            fehler.append(f"{tag}: Artikel im Text von {q} nicht gefunden"); continue
        if K.norm(z) not in abschnitt or K.norm(adressat) not in abschnitt:
            fehler.append(f"{tag}: Zitat oder Adressat steht nicht in diesem Artikel"); continue
        zugriff[(reg, arts[0], art)] = (reg, arts[0], art, adressat, q, z)

    rows = {"register_angabe": sorted(angaben.values(), key=lambda r: (r[0], r[1], r[5])),
            "register_dokument": sorted(dokumente.values()),
            "register_zugriff": sorted(zugriff.values())}
    return rows, fehler, hinweise


def _rx_ok(x):
    try:
        re.compile(x)
        return True
    except re.error:
        return False


SPALTEN = {
    "register_angabe": ("register", "angabe", "ech_element_id", "esh_code", "esh_element", "entitaet",
                        "entitaet_aus_element", "quelle", "zitat", "kontext", "ohne"),
    "register_dokument": ("register", "begriff", "quelle", "zitat"),
    "register_zugriff": ("register", "article_id", "art", "adressat", "quelle", "zitat"),
}


def _aktuell(conn, t):
    if not _has(conn, t):
        return None
    if not set(SPALTEN[t]) <= {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}:
        return None                                     # an older layout: the loader rebuilds it
    return sorted(tuple(r) for r in conn.execute(f"SELECT {', '.join(SPALTEN[t])} FROM {t}"))


# ---------------------------------------------------------------------------
# the gate for validate_db.py
# ---------------------------------------------------------------------------
def pruefen(conn, nur_katalog=False):
    """Invariants of the register tables; [] when they hold. Each check is skipped when
    its table does not exist yet (a database before the register layer)."""
    if not _has(conn, "register"):
        return []
    fehler = []
    qdir = K.quellen_dir([])
    texte, roh, f0 = _texte(conn, qdir)
    fehler += f0

    def zitat_ok(tab, key, q, z):
        if q is None or q not in texte:
            if not any(q and q in x for x in f0):
                fehler.append(f"{tab} {key}: Quelle {q} ohne gültigen Text")
        elif K.norm(z) not in texte[q]:
            fehler.append(f"{tab} {key}: Zitat steht nicht in der Quelle {q}")

    belegt = {}
    for r in conn.execute("SELECT register, aspekt, quelle, zitat FROM register_beleg"):
        zitat_ok("register_beleg", r["register"], r["quelle"], r["zitat"])
        belegt.setdefault(r["register"], set()).add(r["aspekt"])
        if r["aspekt"] == "inhaber" and not INHABER_WORT.search(r["zitat"]):
            fehler.append(f"register_beleg {r['register']}/inhaber: das Zitat nennt keine Stelle (Amt, Behörde, "
                          f"Kanton, Gemeinde, Bund …): «{r['zitat'][:70]}»")
    # access is stated only through register_zugriff (a quoted, ingested article): the
    # register's own sentences never say who may fetch it
    mit_zugriff = {r[0] for r in conn.execute("SELECT DISTINCT register FROM register_zugriff")} \
        if _has(conn, "register_zugriff") else set()
    for r in conn.execute("SELECT code, inhalt, bemerkung FROM register"):
        for spalte in ("inhalt", "bemerkung"):
            t = re.sub(r"Zugriff\s*:?\s*offen", "", r[spalte] or "")
            if ERLAUBNIS_WORT.search(t):
                fehler.append(f"register {r['code']}.{spalte}: sagt, wer etwas darf — das entscheiden die Juristinnen "
                              f"und Juristen des Kantons, nie die Databank: «{(r[spalte] or '')[:80]}»")
            elif ZUGRIFF_WORT.search(t) and r["code"] not in mit_zugriff:
                fehler.append(f"register {r['code']}.{spalte}: spricht vom Zugriff ohne zitierten, ingestierten "
                              f"Artikel (register_zugriff): «{(r[spalte] or '')[:80]}»")
    for r in conn.execute("SELECT code, schluessel FROM register"):
        need = {"inhaber", "inhalt"} | ({"schluessel"} if r["schluessel"] else set())
        miss = need - belegt.get(r["code"], set())
        if miss:
            fehler.append(f"register {r['code']}: ohne Beleg für {sorted(miss)}")
    regel = set(REGISTER_STDS)
    for r in conn.execute("SELECT register, standard, art, quelle, zitat FROM register_standard"):
        if r["art"] == "projektregel":
            if r["register"] != "einwohnerregister" or r["standard"] not in regel:
                fehler.append(f"register_standard {r['register']}/{r['standard']}: Projektregel nur für das "
                              f"Einwohnerregister und {sorted(regel)}")
        else:
            zitat_ok("register_standard", f"{r['register']}/{r['standard']}", r["quelle"], r["zitat"] or "")
    if nur_katalog:
        return fehler

    if _has(conn, "register_angabe"):
        esh_genutzt = _esh_genutzt(conn)
        for r in conn.execute("SELECT * FROM register_angabe"):
            key = f"{r['register']}/{r['angabe']}"
            ech, esh = r["ech_element_id"] is not None, r["esh_code"] is not None
            if ech == esh or (esh and not r["esh_element"]) or (ech and r["esh_element"]):
                fehler.append(f"register_angabe {key}: genau eines von eCH-Element oder eSH-Schlüssel")
            elif ech and r["angabe"] != f"ech:{r['ech_element_id']}":
                fehler.append(f"register_angabe {key}: Schlüssel passt nicht zum Element")
            elif esh and r["angabe"] != f"esh:{r['esh_code']}:{r['esh_element']}":
                fehler.append(f"register_angabe {key}: Schlüssel passt nicht zum eSH-Schlüssel")
            elif esh and (r["esh_code"], r["esh_element"]) not in esh_genutzt:
                fehler.append(f"register_angabe {key}: eSH-Schlüssel trägt kein Datenpunkt")
            for spalte in ("kontext", "ohne"):
                if spalte in r.keys() and r[spalte] and not _rx_ok(r[spalte]):
                    fehler.append(f"register_angabe {key}: {spalte} ist kein gültiges Muster")
            zitat_ok("register_angabe", key, r["quelle"], r["zitat"])
    if _has(conn, "register_dokument"):
        for r in conn.execute("SELECT * FROM register_dokument"):
            if r["begriff"].lower() not in r["zitat"].lower():
                fehler.append(f"register_dokument {r['register']}/{r['begriff']}: Begriff nicht im Zitat")
            zitat_ok("register_dokument", f"{r['register']}/{r['begriff']}", r["quelle"], r["zitat"])
    if _has(conn, "register_zugriff"):
        for r in conn.execute("SELECT z.*, a.article_no, l.sr_number, l.cantonal_ref, q.titel FROM register_zugriff z "
                              "JOIN article a ON a.id=z.article_id JOIN law l ON l.id=a.law_id "
                              "LEFT JOIN register_quelle q ON q.id=z.quelle"):
            key = f"{r['register']}/{r['article_no']}"
            if r["art"] not in ("kandidat", "schranke"):      # re-checked here: a CHECK can be switched off
                fehler.append(f"register_zugriff {key}: art {r['art']!r} — nur kandidat oder schranke, nie «erlaubt»")
            nr = _gesetz_nr(r["sr_number"] or r["cantonal_ref"])
            if not nr or nr not in (r["titel"] or ""):
                fehler.append(f"register_zugriff {key}: die Quelle ist nicht der Text dieses Gesetzes")
            elif r["quelle"] in roh:
                ab = artikel_abschnitt(roh[r["quelle"]], r["article_no"])
                if K.norm(r["zitat"]) not in ab or K.norm(r["adressat"]) not in ab:
                    fehler.append(f"register_zugriff {key}: Zitat oder Adressat nicht in diesem Artikel")
            else:
                zitat_ok("register_zugriff", key, r["quelle"], r["zitat"])
    fehler += zeit_pruefen(conn)
    return fehler


# ---------------------------------------------------------------------------
# loader
# ---------------------------------------------------------------------------
def main_laden(pruefen_nur=False):
    qdir = K.quellen_dir()
    conn = connect(DB_PATH)
    rows, fehler, hinweise = zeilen(conn, qdir)
    for h in hinweise:
        print("  Hinweis:", h)
    if rows is not None:
        print(f"Register-Zuordnung: {len(rows['register_angabe'])} Angaben (Element × Entität), "
              f"{len(rows['register_dokument'])} Dokumentbegriffe, {len(rows['register_zugriff'])} Zugriffsartikel")
    if fehler:
        print(f"ABGELEHNT ({len(fehler)}):")
        for f in fehler:
            print("  -", f)
        sys.exit(1)
    if pruefen_nur:
        print("Gate bestanden (nichts geschrieben).")
        return
    if all(_aktuell(conn, t) == sorted(tuple(r) for r in rows[t]) for t in TABELLEN):
        conn.close()
        print("unverändert — die Databank hält diese Zuordnung bereits (nichts geschrieben).")
        return
    conn.close()
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    # the three tables are wholly derived from this module and the snapshots: a table whose
    # columns differ from schema.sql is dropped and created again
    import sqlite3 as _sq
    soll = _sq.connect(":memory:")
    for stmt in K.ddl(("register",) + TABELLEN):
        soll.execute(stmt)
    for t in TABELLEN:
        neu = [r[1] for r in soll.execute(f"PRAGMA table_info({t})")]
        alt = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
        if alt and alt != neu:
            c.execute(f"DROP TABLE {t}")
    soll.close()
    for stmt in K.ddl(TABELLEN):
        c.execute(stmt)
    for t in TABELLEN:
        c.execute(f"DELETE FROM {t}")
        cols = SPALTEN[t]
        c.executemany(f"INSERT INTO {t}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})", rows[t])
    c.commit()
    from validate_db import validate
    errs = list(dict.fromkeys(validate(c) + pruefen(c)))
    c.close()
    if errs:
        os.remove(st)
        print(f"ABBRUCH — Validierung ({len(errs)}):")
        for e in errs[:30]:
            print("  -", e)
        sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"geladen: {DB_PATH}")


# ---------------------------------------------------------------------------
# the export hooks (computed once; dashboard, dossiers and citygov_llm.json read them)
# ---------------------------------------------------------------------------
def _units(d):
    subs = [s for s in (d.get("subfields") or []) if isinstance(s, dict)]
    return subs, (subs or [d])


def kontext_text(fm, d, u, subs):
    """The folded context a KONTEXT rule reads: Formular title, field label, part label."""
    return falten(" | ".join(x for x in ((fm or {}).get("title"), d.get("name"), u.get("name") if subs else None) if x))


# the party status of a data point for the prefill rule (one definition)
PARTEI_STATUS = {
    "gesuchsteller": "Angabe der einreichenden Person (Rolle Gesuchsteller/in, natürliche Person)",
    "andere_partei": "Angabe einer Partei mit einer anderen Rolle als Gesuchsteller/in (Ehepartner/in, Kind, "
                     "Arbeitnehmer/in, Organ …; auch Bauherrschaft oder Halter/in, solange die Beurteilung aus dem "
                     "Formulartext sie nicht als einreichende Person bestätigt) — nicht vorbefüllbar; Angaben zu "
                     "Beziehungen erst nach dem "
                     "Entscheid des Kantons, ob das Register sie liefern darf",
    "partei_offen": "wessen Angabe es ist, ist nicht geklärt (Partei unklar, noch nicht abgeleitet, oder die "
                    "Gesuchsteller/in ist nicht als natürliche Person geklärt); nicht vorbefüllbar",
}


def partei_von(fm, u):
    """(party dict {nr, rolle, entitaet} or None, status) of an exported unit; status is
    one of PARTEI_STATUS. Reads u.partei (rollen.parteien_anhaengen) and fm.parteien."""
    pa = u.get("partei") or {}
    if pa.get("status") != "zugeordnet" or pa.get("nr") is None:
        return None, "partei_offen"
    p = next((x for x in fm.get("parteien") or [] if x.get("nr") == pa["nr"]), None)
    if p is None:
        return None, "partei_offen"
    info = {"nr": p["nr"], "rolle": p["rolle"], "entitaet": p["entitaet"]}
    if p["rolle"] != "gesuchsteller":
        return info, "andere_partei"
    return info, ("gesuchsteller" if p["entitaet"] == "natuerliche_person" else "partei_offen")


# ---------------------------------------------------------------------------
# the time rule of the prefill (see the module docstring): the register's CURRENT
# value fills a point only when the point asks for the current value
# ---------------------------------------------------------------------------
ZEIT_KUENFTIG = re.compile(
    r"\bneue?[nrs]?\b|\bkuenftig|\bzukuenftig|\bgeplant|\bvoraussichtlich|\bbeabsichtigt|\bbeantragt|"
    r"\bnach (?:dem|der) (?:umzug|zuzug|wegzug|heirat|scheidung|einbuergerung|adoption)")
ZEIT_ANDERE = re.compile(
    r"\bfrueher|\bbisherig|\bbisher\b|\bvorherig|\bvorig|\behemalig|\bvormalig|\bvormals\b|\bdamals\b|\bdamalig|"
    r"\burspruenglich|\bzuletzt\b|\bletzte[nrs]?\b|\bwaehrend\b|\balte[ns]?\b|\bbeim eintritt|\bzum zeitpunkt|"
    r"\bim zeitpunkt|\bzur zeit de[rs]\b|abwesenheit|\bbei realisierung|\bledig|geburtsname|\bbei der geburt")
ZEIT_WECHSEL = re.compile(
    r"aenderung|wechsel|\bmutation|\bmutierend|\bzuzug|\bzugezogen|\bwegzug|\bweggezogen|\bumzug|\bausreise|"
    r"\beinreise|\babmeld|\bdauer\b|\bzeitraum|\bperiode\b|\baufenthalte\b|\baufenthaltsorte|\bwohnorte\b|"
    r"\bheirat|\beheschliess|\bscheidung|\btrennung|\bverwitwung|\beinbuergerung")
ZEIT_PRAEPOSITION = re.compile(r"\bseit\b|\bbis\b|\bab\b")
# a time word that qualifies a PERSON (neue Zeichnungsberechtigte, Bewirtschafter neu, verantwortliche
# Person (bisher)) says which person, not which value: that person's current data are meant, and
# whose Angabe it is the party layer decides — the phrase is taken out before the time words are read
_ZEIT_WORT = r"(?:neue?[nrs]?|bisherige?[nrs]?|bisher|fruehere?[nrs]?|ehemalige?[nrs]?|kuenftige?[nrs]?)(?:\([a-z]\))?"
_PERSON_WORT = (r"(?:zeichnungsberechtigt\w*|bewirtschafter\w*|verantwortliche?[nrs]?\s+person\w*|person(?:en)?\b|"
                r"inhaber\w*|halter\w*|paechter\w*|eigentuemer\w*|geschaeftsfuehr\w*|mitglied\w*|"
                r"gesellschafter\w*|liquidator\w*|vertreter\w*|arbeitgeber\w*|mieter\w*|vermieter\w*|organ\w*)")
ZEIT_PERSON = re.compile(rf"\b{_ZEIT_WORT}\s*{_PERSON_WORT}|{_PERSON_WORT}\s*\(?\s*{_ZEIT_WORT}\b\)?:?")
# (standard, element) -> (pattern the label must carry unless it has only a bare
# preposition, pattern the label must not carry): elements whose value IS the date or
# place of that event in the register's own entry (the quoted rules of RHG Art. 6 and
# Gemeindegesetz Art. 88 Abs. 2 in ANGABEN) — each must be named by a quoted
# Einwohnerregister rule (zeit_pruefen)
ZEIT_EREIGNIS = {
    ("eCH-0011", "arrivalDate"): (r"\bzuzug|\bzugezogen|\bgemeinde\b|\bwohnort\b|\bwohnhaft\b|\bangemeldet|"
                                  r"\banmeldung|\bankunft|\beingezogen",
                                  r"schweiz|\bkanton|ausland|frankreich|\bstaat\b|\bland\b|aufenthalte\b|\bdauer\b|"
                                  r"\bbis\b|\bvon\b"),
    ("eCH-0011", "comesFrom"): (r"\bzuzug|\bzugezogen|herkunft|\bvorherig|\bvorig", r"aufenthalte\b|wohnorte\b|\bdauer\b"),
    ("eCH-0011", "movingDate"): (r"\bumzug|\bumgezogen", r"haushalt"),
    ("eCH-0011", "dwellingAddressValidFrom"): (r"\badresse|\bwohnung|\bwohnhaft|\bwohnsitz", None),
    ("eCH-0011", "departureDate"): (r"\bwegzug|\bweggezogen|\bausreise|\babmeld|\babreise", r"frueher|zivilstand"),
    ("eCH-0011", "goesTo"): (r"\bwegzug|\bweggezogen|\bausreise|\babmeld|\bzielort", None),
    ("eCH-0011", "dateOfMaritalStatus"): (r"zivilstand|verheiratet|\bheirat|eheschliess|partnerschaft|geschieden|"
                                          r"scheidung|verwitw", r"trenn|getrennt"),
    ("eCH-0011", "nationalityValidFrom"): (r"staatsangehoerig|nationalitaet|schweizer|buergerrecht|einbuergerung|"
                                           r"eingebuergert", None),
    ("eCH-0011", "residencePermitValidFrom"): (r"bewilligung|ausweis", None),
    ("eCH-0011", "residencePermitValidTill"): (r"bewilligung|ausweis", None),
    ("eCH-0021", "healthInsuranceValidFrom"): (r"kranken|versicher", None),
    ("eCH-0021", "fireServiceValidFrom"): (r"feuerwehr", None),
    ("eCH-0044", "originalName"): (r"\bledig|geburtsname|bei der geburt", None),
    ("eCH-0011", "originalName"): (r"\bledig|geburtsname|bei der geburt", None),
}
# the death date: never from the submitting person's own profile
ZEIT_NIE = {("eCH-0011", "deathDate")}
# the labelled examples of the gate (label as the export builds it, element, expected
# zeitbezug): the cases of the 2026-10-05 sweep and the exceptions that must stay open
ZEIT_BEISPIELE = [
    ("Frühere Wohnorte | Ort", "eCH-0010", "town", True),
    ("Personalien | Adresse(n) während der letzten zwei Jahre", "eCH-0010", "addressInformation", True),
    ("Adressen der letzten zwei Jahre", "eCH-0010", "addressInformation", True),
    ("Aufenthalte im Ausland | Wohnort / Land", "eCH-0010", "town", True),
    ("Aufenthalte in der Schweiz | Wohnort / Kanton", "eCH-0011", "municipalityName", True),
    ("Änderung Zivilstand | Datum", "eCH-0011", "departureDate", True),
    ("Änderung Zivilstand | Zivilstand neu", "eCH-0011", "maritalStatus", True),
    ("Datum Verstorben", "eCH-0011", "deathDate", True),
    ("Früherer Wohnort | bis", "eCH-0011", "departureDate", True),
    ("Personalien | Neue Adresse gültig ab", "eCH-0011", "dwellingAddressValidFrom", True),
    ("Personalien | Neue Adresse bei Um-/Wegzug", "eCH-0011", "goesTo", True),
    ("Zivilrechtlicher Wohnsitz in der Schweiz seit", "eCH-0011", "arrivalDate", True),
    ("Zivilrechtlicher Wohnsitz im Kanton Schaffhausen seit", "eCH-0011", "arrivalDate", True),
    ("Trennung/Scheidung seit", "eCH-0011", "dateOfMaritalStatus", True),
    ("Wohnsitz in der Schweiz beim Eintritt des Ereignisses", "eCH-0011", "hasMainResidence", True),
    ("Personalien | Kontaktadresse/Telefon (bei Abwesenheit)", "eCH-0011", "contactAddress", True),
    ("Änderung Personalien der Geschäftsinhaberin/des Geschäftsinhabers | Privatadresse", "eCH-0010",
     "personMailAddress", True),
    ("Gemeinsamer Haushalt der Ehegatten seit", "eCH-0011", "movingDate", True),
    ("Zivilstand seit", "eCH-0011", "dateOfMaritalStatus", False),
    ("Datum Änderung Zivilstand", "eCH-0011", "dateOfMaritalStatus", False),
    ("Personalien GesuchstellerIn | seit", "eCH-0011", "dateOfMaritalStatus", False),
    ("Personalien GesuchstellerIn | Wohnsitz in der Gemeinde seit", "eCH-0011", "arrivalDate", False),
    ("Personalien | Wohnort seit", "eCH-0011", "arrivalDate", False),
    ("Wegzug aus dieser Gemeinde seit", "eCH-0011", "departureDate", False),
    ("Aufenthaltsbewilligung gültig bis", "eCH-0011", "residencePermitValidTill", False),
    ("Personalien | lediger Name", "eCH-0044", "originalName", False),
    ("Personalien | Name", "eCH-0044", "officialName", False),
    ("Personalien | Geburtsdatum", "eCH-0044", "dateOfBirth", False),
    ("Zivilstand", "eCH-0011", "maritalStatus", False),
    ("Personalien Gesuchsteller/in | Aufenthaltsbewilligung", "eCH-0011", "residencePermit", False),
    ("Personalien der verstorbenen Person | Geburtsdatum", "eCH-0011", "dateOfBirth", False),
    ("Neue Zeichnungsberechtigte | Privatadresse", "eCH-0011", "dwellingAddress", False),
    ("Bewirtschafter neu: Personalien | Strasse", "eCH-0010", "street", False),
    ("Personalien bisherige(r) Bewirtschafter/in | PLZ, Ort", "eCH-0010", "swissZipCode", False),
    ("Verantwortliche Person (neu) | Name", "eCH-0044", "officialName", False),
    ("Neue AHV-Nummer", "eCH-0044", "vn", True),
    ("Eingetragene Personen neu oder mutierend | Privatadresse", "eCH-0010", "personMailAddress", True),
]


def zeit_label(d, u, subs):
    """The label the time rule reads: the field name, for a Teilfeld «Feld | Teilfeld»."""
    return " | ".join(x for x in (d.get("name"), u.get("name") if subs else None) if x)


def zeitbezug(label, standard, element):
    """True when the label asks for a value of another time than the register's current
    entry and the element does not itself name that value (module docstring)."""
    if (standard, element) in ZEIT_NIE:
        return True
    t = ZEIT_PERSON.sub(" ", falten(label))
    kuenftig, andere, wechsel = ZEIT_KUENFTIG.search(t), ZEIT_ANDERE.search(t), ZEIT_WECHSEL.search(t)
    if kuenftig:
        return True
    if not (andere or wechsel or ZEIT_PRAEPOSITION.search(t)):
        return False
    ereignis = ZEIT_EREIGNIS.get((standard, element))
    if ereignis is None:
        return True
    muss, nie = ereignis
    if nie and re.search(nie, t):
        return True
    if (andere or wechsel) and not re.search(muss, t):
        return True
    return False


def zeit_pruefen(conn):
    """The gate of the time rule ([] when it holds): every exception element is named by
    a quoted Einwohnerregister rule (register_angabe) and exists in the eCH catalogue,
    every pattern compiles, every labelled example classifies as recorded, and the
    reviewed eCH corrections of the sweep (KORREKTUR_DIR) are well formed and either
    pending or applied (korrekturen_pruefen)."""
    fehler = []
    for (s, n), (muss, nie) in ZEIT_EREIGNIS.items():
        for x in (muss, nie):
            if x and not _rx_ok(x):
                fehler.append(f"Zeitregel {s}·{n}: kein gültiges Muster «{x}»")
    if _has(conn, "register_angabe"):
        ewr = {(r[0], r[1]) for r in conn.execute(
            "SELECT e.standard, e.name FROM register_angabe a JOIN ech_element e ON e.id=a.ech_element_id "
            "WHERE a.register='einwohnerregister'")}
        for k in sorted(set(ZEIT_EREIGNIS) | ZEIT_NIE):
            if k not in ewr:
                fehler.append(f"Zeitregel: {k[0]}·{k[1]} nennt keine zitierte Regel des Einwohnerregisters — die "
                              f"Ausnahme darf nur Angaben betreffen, die das Register führt")
    for label, s, n, soll in ZEIT_BEISPIELE:
        if zeitbezug(label, s, n) != soll:
            fehler.append(f"Zeitregel: «{label}» ({s}·{n}) ergibt zeitbezug={not soll}, erwartet {soll}")
    fehler += korrekturen_pruefen(conn)
    return fehler


# ---------------------------------------------------------------------------
# the reviewed eCH corrections of the 2026-10-05 sweep (applied by the existing eCH
# loaders; this module only checks them)
# ---------------------------------------------------------------------------
KORREKTUR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quellen", "korrekturen",
                             "prefill_inhalt_2026-10-05")
KLASSEN = {
    "anderes_ereignis": "das Element nennt ein anderes Ereignis als die Angabe (anderes Datum, anderer Ort)",
    "anderer_zeitraum": "die Angabe ist ein Zeitraum oder eine Liste früherer Aufenthalte, das Element ein einzelner "
                        "Wert des heutigen Eintrags",
    "ja_nein": "eine Ja/Nein-Frage oder ein Ankreuzfeld auf einem Element, das einen Wert hält",
    "andere_angabe": "das Element nennt eine andere Angabe als das Formular erfragt",
}
ZWEITPRUEFUNG = ("bestaetigt", "geaendert")


def _korrektur_dateien(wurzel=None):
    wurzel = wurzel or KORREKTUR_DIR
    out = []
    for dp, _, fs in os.walk(wurzel):
        for f in sorted(fs):
            if f.endswith(".json"):
                out.append(os.path.join(dp, f))
    return sorted(out)


def _el_key(conn, s, n, kontext=None):
    """The ech_element id of (standard, name[, context]) as the loaders resolve it: with a
    context exactly that row, without one the first row of the catalogue."""
    if kontext:
        r = conn.execute("SELECT id FROM ech_element WHERE standard=? AND name=? AND context=?", [s, n, kontext]).fetchone()
    else:
        r = conn.execute("SELECT id FROM ech_element WHERE standard=? AND name=? ORDER BY id", [s, n]).fetchone()
    return r[0] if r else None


def korrekturen_lesen(conn, wurzel=None):
    """[(datei, art, eintrag, ziele, alt, neu)] for every correction entry: art 'teilfeld'
    (id-keyed, scripts/load_subfield_ech.py) or 'feld' (name-keyed verdict,
    scripts/load_ech_verdicts.py, or load_ech_verdicts_new.py --from=<ab_formular>);
    ziele = [(table, row id)], alt / neu = ('element', id) | ('kein_standard', None).
    Also returns the structural errors."""
    from common import norm_ascii
    out, fehler = [], []
    for pfad in _korrektur_dateien(wurzel):
        name = os.path.relpath(pfad, os.path.dirname(KORREKTUR_DIR))
        try:
            d = json.load(open(pfad, encoding="utf-8"))
        except ValueError as ex:
            fehler.append(f"Korrektur {name}: kein JSON ({ex})")
            continue
        if not isinstance(d, dict) or not d.get("hinweis") or not d.get("anwenden"):
            fehler.append(f"Korrektur {name}: ohne hinweis oder anwenden")
            continue
        ab = d.get("ab_formular")
        eintraege = [("teilfeld", z) for z in d.get("zuordnungen") or []] + \
                    [("feld", z) for z in d.get("urteile") or []]
        if not eintraege:
            fehler.append(f"Korrektur {name}: keine Einträge")
        for art, z in eintraege:
            tag = f"Korrektur {name} {z.get('subfield_id') or z.get('feld')}"
            for k in ("grund", "klasse", "bisher", "zweitpruefung"):
                if not z.get(k):
                    fehler.append(f"{tag}: ohne {k}")
            zitate = z.get("zitate") or ([{"form_id": z.get("form_id"), "zitat": z.get("zitat")}]
                                         if z.get("zitat") else [])
            if not zitate or any(not (x.get("zitat") or "").strip() or not x.get("form_id") for x in zitate):
                fehler.append(f"{tag}: ohne Zitat aus dem Formulartext")
            if z.get("klasse") and z["klasse"] not in KLASSEN:
                fehler.append(f"{tag}: Klasse {z['klasse']!r} nicht in {sorted(KLASSEN)}")
            zp = z.get("zweitpruefung") or {}
            if zp and (zp.get("urteil") not in ZWEITPRUEFUNG or not zp.get("grund")):
                fehler.append(f"{tag}: Zweitprüfung ohne Urteil {ZWEITPRUEFUNG} oder ohne Grund")
            b = z.get("bisher") or {}
            alt_id = _el_key(conn, b.get("standard"), b.get("element"), b.get("kontext")) if b else None
            if b and not alt_id:
                fehler.append(f"{tag}: das bisherige Element {b} steht nicht im Katalog")
            if z.get("kein_standard") or z.get("urteil") == "kein_standard":
                neu = ("kein_standard", None)
            else:
                nid = _el_key(conn, z.get("standard"), z.get("element"), z.get("kontext"))
                if not nid:
                    fehler.append(f"{tag}: das neue Element {z.get('standard')}·{z.get('element')} steht nicht im Katalog")
                    continue
                neu = ("element", nid)
            if art == "feld" and z.get("urteil") not in ("kein_standard", "besser"):
                fehler.append(f"{tag}: urteil muss kein_standard oder besser sein")
            if art == "teilfeld":
                r = conn.execute("SELECT s.name, d.name, d.form_id FROM data_subfield s JOIN data_field d "
                                 "ON d.id=s.data_field_id WHERE s.id=?", [z.get("subfield_id")]).fetchone()
                if not r:
                    fehler.append(f"{tag}: Teilfeld fehlt")
                    continue
                if (r[0], r[1], r[2]) != (z.get("teilfeld"), z.get("elternfeld"), z.get("form_id")):
                    fehler.append(f"{tag}: Teilfeld heisst heute «{r[1]} › {r[0]}» (Formular {r[2]}), die Korrektur "
                                  f"nennt «{z.get('elternfeld')} › {z.get('teilfeld')}» (Formular {z.get('form_id')})")
                ziele = [("data_subfield", z["subfield_id"])]
            else:
                k = norm_ascii(z.get("feld"))
                ids = sorted(r[0] for r in conn.execute("SELECT id, name, form_id FROM data_field").fetchall()
                             if norm_ascii(r[1]) == k and (ab is None or r[2] >= ab))
                if ids != sorted(z.get("field_ids") or []):
                    fehler.append(f"{tag}: der Name trifft die Felder {ids}, geprüft sind {sorted(z.get('field_ids') or [])}"
                                  f" — ein namensbasiertes Urteil darf nur geprüfte Felder treffen")
                ziele = [("data_field", i) for i in ids]
            out.append((name, art, z, ziele, ("element", alt_id), neu))
    return out, fehler


def _stand(conn, table, rid):
    r = conn.execute(f"SELECT ech_element_id, ech_status FROM {table} WHERE id=?", [rid]).fetchone()
    if not r:
        return None
    if r[0] is not None:
        return ("element", r[0])
    return ("kein_standard", None) if r[1] == "kein_standard" else ("sonst", r[1])


def korrekturen_stand(conn, wurzel=None):
    """({datei: 'ausstehend' | 'angewendet' | 'gemischt'}, errors): a correction file is
    pending while every target still carries its old element, applied when every target
    carries the corrected verdict; a target with neither, or a file that is half applied,
    is an error (a later loader overwrote the reviewed verdict)."""
    rows, fehler = korrekturen_lesen(conn, wurzel)
    stand = {}
    for datei, art, z, ziele, alt, neu in rows:
        for t, rid in ziele:
            s = _stand(conn, t, rid)
            if s == neu:
                stand.setdefault(datei, set()).add("angewendet")
            elif s == alt:
                stand.setdefault(datei, set()).add("ausstehend")
            else:
                fehler.append(f"Korrektur {datei}: {t} {rid} trägt weder das bisherige noch das korrigierte "
                              f"Element ({s}) — eine spätere Zuordnung hat das geprüfte Urteil überschrieben")
    out = {}
    for datei, s in stand.items():
        out[datei] = s.pop() if len(s) == 1 else "gemischt"
        if out[datei] == "gemischt":
            fehler.append(f"Korrektur {datei}: zum Teil angewendet — eine Korrekturdatei wird ganz oder gar nicht "
                          f"angewendet (Befehl in ihrem Feld «anwenden»)")
    return out, fehler


def korrekturen_pruefen(conn, wurzel=None):
    if not os.path.isdir(wurzel or KORREKTUR_DIR) or not _has(conn, "data_subfield"):
        return []
    return korrekturen_stand(conn, wurzel)[1]


def ewr_marke(fm, d, u, ang, std):
    """The Einwohnerregister mark of one unit: a quoted Einwohnerregister rule names its
    element and the field is judged a natural person's Angabe (level «bestaetigt»)."""
    subs = [s for s in (d.get("subfields") or []) if isinstance(s, dict)]
    return stufen(d, u, ang, std, kontext_text(fm, d, u, subs)).get("einwohnerregister") == "bestaetigt"


def prefill_punkte(fm, zeitregel=True):
    """The points of one exported Formular as citygov_prefill.json lists them — the
    ONE rule: export_llm.py writes the file with it, prefill_korrigieren() counts
    burden.prefillable with it and build_flows.py fills the guided Formulare by it
    (flow_schluessel): every atomic point with an eCH element; einwohnerregister = the
    mark prefill_korrigieren put on the unit (a quoted Einwohnerregister rule names the
    element, subjekt natürliche Person); partei / partei_status = whose Angabe it is
    (party layer); zeitbezug = the label asks for a value of another time than the
    register's current entry and the element does not name it (zeitbezug(), the time
    rule); mehrdeutig = the element (standard·name) names more than one natural-person
    point OF THE SAME PARTY on this Formular among the points without zeitbezug, the
    parent's own element of a composite counting as a virtual partner of every party
    that owns one of its parts unless the parent's own label has zeitbezug (points
    without a party are compared among themselves); vorbefuellbar = einwohnerregister
    AND partei_status «gesuchsteller» AND not mehrdeutig AND not zeitbezug. Each point
    keeps its unit under «_u» (the caller drops it before writing). zeitregel=False
    gives the outcome without the time rule (prefill_korrigieren counts the rule's
    effect with it)."""
    pts, virt = [], []
    for d in fm.get("data_fields") or []:
        subs, units = _units(d)
        pe = d.get("ech") or {}
        if subs and d.get("subjekt") == "natuerliche_person" and pe.get("element") and not (
                zeitregel and zeitbezug(d.get("name") or "", pe.get("standard"), pe.get("element"))):
            nrs = {(s.get("partei") or {}).get("nr") if (s.get("partei") or {}).get("status") == "zugeordnet"
                   else None for s in subs}
            virt.append(((pe.get("standard"), pe.get("element")), nrs))
        for u in units:
            e = u.get("ech") or {}
            if not e.get("element"):
                continue
            partei, status = partei_von(fm, u)
            zb = bool(zeitregel and zeitbezug(zeit_label(d, u, subs), e.get("standard"), e.get("element")))
            pts.append({"feld": d["name"] + ("›" + u["name"] if subs else ""),
                        "feld_parent": d["name"] if subs else None,
                        "standard": e.get("standard"), "element": e.get("element"),
                        "pflicht": bool(d.get("required")), "subjekt": d.get("subjekt"),
                        "einwohnerregister": u.get("register") == "einwohnerregister",
                        "partei": partei, "partei_status": status, "zeitbezug": zb,
                        "mehrdeutig": False, "vorbefuellbar": False, "_u": u})
    seen = {}
    for p in pts:
        if p["subjekt"] == "natuerliche_person" and not p["zeitbezug"]:
            seen.setdefault((p["partei"]["nr"] if p["partei"] else None, p["standard"], p["element"]), []).append(p)
    for k, nrs in virt:
        for nr in nrs:
            seen.setdefault((nr,) + k, []).append(None)
    for ps in seen.values():
        if len(ps) > 1:
            for p in ps:
                if p is not None:
                    p["mehrdeutig"] = True
    for p in pts:
        p["vorbefuellbar"] = (p["einwohnerregister"] and p["partei_status"] == "gesuchsteller" and not p["mehrdeutig"]
                              and not p["zeitbezug"])
    return pts


def flow_schluessel(fm):
    """The keys the guided flow fills from (and saves to) the citizen's profile — the
    vorbefuellbar points of prefill_punkte(), as «Feld» or «Feld›Teilfeld» -> element
    («eCH-XXXX·element»). Only meaningful for a Formular with a flow."""
    return {p["feld"]: f"{p['standard']}·{p['element']}" for p in prefill_punkte(fm) if p["vorbefuellbar"]}


AUSGESCHLOSSEN = ("ohne_registerquelle", "andere_partei", "partei_offen", "mehrdeutig", "zeitbezug")
# the German text of each reason (exported once as vorbefuellung.gruende; the pages only draw)
AUSGESCHLOSSEN_TEXT = {
    "ohne_registerquelle": "keine zitierte Regel des Einwohnerregisters nennt das Element (die frühere Zählung nahm "
                           "jede Angabe der Personen- und Adressstandards)",
    "andere_partei": "Angabe einer anderen Partei als der einreichenden Person (Ehepartner/in, Kind, "
                     "Arbeitnehmer/in, Organ …)",
    "partei_offen": "wessen Angabe es ist, ist nicht geklärt",
    "mehrdeutig": "dasselbe Element bezeichnet auf diesem Formular mehr als eine Angabe derselben Partei",
    "zeitbezug": "die Bezeichnung fragt nach einem Wert einer anderen Zeit (früher, neu, Änderung, seit …); der "
                 "Registereintrag hält den heutigen Wert",
}


def alte_marke(p):
    """The mark before 2026-10-05 (prefillable_bisher): an element of one of the five
    person and address standards, subjekt natürliche Person."""
    return p["standard"] in REGISTER_STDS and p["subjekt"] == "natuerliche_person"


def prefill_korrigieren(forms, ang, std):
    """Sets the Einwohnerregister mark u.register (ewr_marke), u.vorbefuellbar and, on a
    marked unit the time rule keeps out, u.zeitbezug, and counts per Formular the
    required points that are vorbefüllbar (prefill_punkte): burden.prefillable. The
    figure of the standard-based mark before 2026-10-05 stays as prefillable_bisher
    (export_json counts it in its burden loop); every point it counted that the rule
    leaves out is in prefillable_ausgeschlossen by its first reason (no quoted register
    rule, another party, the party open, mehrdeutig, zeitbezug — the last one counts what
    the time rule alone keeps out), and prefillable_hinzu counts the vorbefüllbar points
    it did not count (an element a quoted rule names outside the five standards, e.g.
    eCH-0021): bisher − Σ ausgeschlossen + hinzu = prefillable. vorbefuellung.zeitbezug
    holds the effect of the time rule against the same points without it (weniger: kept
    out, mehr: no longer mehrdeutig because their twin asks for another time). Returns
    the totals, with the German text of each reason (gruende, AUSGESCHLOSSEN_TEXT).
    Idempotent."""
    tot = {"bisher": 0, "korrigiert": 0, "ausgeschlossen": {k: 0 for k in AUSGESCHLOSSEN}, "hinzu": 0,
           "formulare_zu_hoch": 0, "minuten_bisher": 0.0, "minuten_korrigiert": 0.0}
    zb = {"punkte_mit_marke": 0, "weniger": 0, "weniger_pflicht": 0, "mehr": 0, "mehr_pflicht": 0,
          "formulare_geaendert": 0, "formulare_mit_zeitbezug": 0}
    for fm in forms:
        for d in fm.get("data_fields") or []:
            for u in _units(d)[1]:
                u.pop("register", None)
                if ewr_marke(fm, d, u, ang, std):
                    u["register"] = "einwohnerregister"
        bu = fm.get("burden")
        pts = prefill_punkte(fm)
        ohne = prefill_punkte(fm, zeitregel=False)
        geaendert = False
        for p, q in zip(pts, ohne):
            if p["vorbefuellbar"]:
                p["_u"]["vorbefuellbar"] = True
            else:
                p["_u"].pop("vorbefuellbar", None)
            if p["zeitbezug"] and p["einwohnerregister"]:
                p["_u"]["zeitbezug"] = True
                zb["punkte_mit_marke"] += 1
            else:
                p["_u"].pop("zeitbezug", None)
            if q["vorbefuellbar"] and not p["vorbefuellbar"]:
                zb["weniger"] += 1
                zb["weniger_pflicht"] += p["pflicht"]
                geaendert |= p["pflicht"]
            elif p["vorbefuellbar"] and not q["vorbefuellbar"]:
                zb["mehr"] += 1
                zb["mehr_pflicht"] += p["pflicht"]
                geaendert |= p["pflicht"]
        zb["formulare_geaendert"] += geaendert
        zb["formulare_mit_zeitbezug"] += any(p["zeitbezug"] and p["einwohnerregister"] for p in pts)
        if not bu:
            continue
        bisher = bu["prefillable_bisher"]
        korr = sum(1 for p in pts if p["pflicht"] and p["vorbefuellbar"])
        aus, hinzu = {k: 0 for k in AUSGESCHLOSSEN}, 0
        for p in pts:
            if not p["pflicht"]:
                continue
            if p["vorbefuellbar"]:
                hinzu += not alte_marke(p)
                continue
            if not alte_marke(p):
                continue
            grund = ("ohne_registerquelle" if not p["einwohnerregister"] else
                     "andere_partei" if p["partei_status"] == "andere_partei" else
                     "partei_offen" if p["partei_status"] == "partei_offen" else
                     "mehrdeutig" if p["mehrdeutig"] else "zeitbezug")
            aus[grund] += 1
        bu["prefillable"] = korr
        bu["prefillable_ausgeschlossen"] = aus
        bu["prefillable_hinzu"] = hinzu
        bu["minutes_saved"] = round(korr * MIN_ANGABE, 1)
        tot["bisher"] += bisher
        tot["korrigiert"] += korr
        tot["hinzu"] += hinzu
        for k in AUSGESCHLOSSEN:
            tot["ausgeschlossen"][k] += aus[k]
        tot["formulare_zu_hoch"] += bisher > korr
        tot["minuten_bisher"] += round(bisher * MIN_ANGABE, 1)
        tot["minuten_korrigiert"] += round(korr * MIN_ANGABE, 1)
    tot["minuten_bisher"] = round(tot["minuten_bisher"], 1)
    tot["minuten_korrigiert"] = round(tot["minuten_korrigiert"], 1)
    tot["n_ausgeschlossen"] = sum(tot["ausgeschlossen"].values())
    tot["zeitbezug"] = zb
    tot["gruende"] = {k: AUSGESCHLOSSEN_TEXT[k] for k in AUSGESCHLOSSEN}
    tot["regel"] = ("vorbefüllbar = Pflichtangabe mit Einwohnerregister-Marke (eine zitierte Regel des "
                    "Einwohnerregisters nennt das Element, Subjekt natürliche Person) UND Angabe der einreichenden "
                    "Person (Partei Gesuchsteller/in, natürliche Person) UND innerhalb dieser Partei nicht mehrdeutig "
                    "UND die Angabe fragt nach dem heutigen Wert des Registers (Zeitregel: eine Bezeichnung mit einem "
                    "Zeitbezug — früher, bisherig, letzte zwei Jahre, während, neu, geplant, Änderung, Zuzug, Wegzug, "
                    "seit, bis, Dauer — wird nie aus dem heutigen Eintrag gefüllt, ausser das Element nennt "
                    "selbst diesen Wert, etwa das Zuzugsdatum oder das Datum des Zivilstands; das Todesdatum nie); "
                    "Angaben des Ehepartners, eines Kindes oder anderer Personen erst, wenn der Kanton bestätigt, "
                    "dass Beziehungen geliefert werden dürfen")
    return tot


PARTY = None


def _party():
    global PARTY
    if PARTY is None:
        from export_json import PARTY as P      # one definition of the party words
        PARTY = P
    return PARTY


def regeln(conn):
    """(ang, std): the Angabe rules {angabe key: [(register, entity, aus_element, kontext, ohne)]}
    and the standards {standard: {register}} — read once per export."""
    ang = {}
    for r in conn.execute("SELECT register, angabe, entitaet, entitaet_aus_element, kontext, ohne FROM register_angabe"):
        ang.setdefault(r["angabe"], []).append((r["register"], r["entitaet"], r["entitaet_aus_element"],
                                                r["kontext"], r["ohne"]))
    std = {}
    for r in conn.execute("SELECT register, standard FROM register_standard"):
        std.setdefault(r["standard"], set()).add(r["register"])
    return ang, std


_regeln = regeln


def stufen(d, u, ang, std, kontext=""):
    """{register: level} for one exported unit (see the module docstring); kontext is
    kontext_text() of the unit (the rules with a KONTEXT need it)."""
    e = u.get("ech") or {}
    if e.get("element") in CONTAINER or (u.get("begriff") or {}).get("pruefart") == "zuordnung":
        return {}
    esh = u.get("esh") or {}
    key = f"ech:{e['id']}" if e.get("id") and e.get("element") else (
        f"esh:{esh['code']}:{esh['element']}" if esh.get("code") and esh.get("element") else None)
    sj = d.get("subjekt")
    out = {}
    for reg, ent, aus, muss, ohne in ang.get(key, []):
        if (muss and not re.search(muss, kontext)) or (ohne and re.search(ohne, kontext)):
            continue                                    # the rule's context is not this unit's
        if ent == "jede" or sj == ent:
            lvl = "bestaetigt"
        elif sj in (None, "gemischt"):
            lvl = "bestaetigt" if aus else "element"
        else:
            lvl = None                                  # a judged party that contradicts the rule
        if lvl and (reg not in out or STUFEN.index(lvl) > STUFEN.index(out[reg])):
            out[reg] = lvl
    if e.get("element"):
        for reg in std.get(e.get("standard"), ()):
            out.setdefault(reg, "standard")
    return out


def beilage_register(bez, halter, dokumente, titel=""):
    """[(register, grundlage, begriff)] for one Beilage; [] for a foreign document, a
    Formular or Merkblatt (or the Formular itself), a number, a figure or the own claim
    (KEINE_URKUNDE), and no halter mapping for the
    applicant's own return or a plan the applicant annotates; no IVZ for a ship."""
    if AUSLAND.search(bez or ""):
        return []
    f = falten(bez)
    if KEIN_DOKUMENT.search(f) or KEINE_URKUNDE.search(f) or (titel and f == falten(titel)):
        return []
    out = {}
    if halter in HALTER and not EIGENE_ANGABE.search(f):
        out[HALTER[halter]] = ("halter", None)
    for reg, begriff in dokumente:
        if begriff.lower() in (bez or "").lower():
            g = "beide" if reg in out else "bezeichnung"
            out[reg] = (g, begriff)
    if re.search(SCHIFF, f):
        out.pop("ivz", None)
    return sorted((reg, g, b) for reg, (g, b) in out.items())


def ersetzt_nicht(bez, titel="", begriffe=()):
    """Why a register does not replace this Beilage although it holds the document:
    'original' (the original is demanded), 'rueckgabe' (the document is handed in to be
    surrendered, exchanged or cancelled — said by the Beilage, or by the Formular title
    that names the same document: «Löschung der Ziffer 178 im Fahrzeugausweis»),
    'identitaet' (a copy of an identity document among alternatives), or None."""
    f, t = falten(bez), falten(titel)
    if ORIGINAL.search(bez or ""):
        return "original"
    if RUECKGABE.search(f) or (RUECKGABE.search(t) and any(b and falten(b) in t for b in begriffe)):
        return "rueckgabe"
    if IDENTITAET.search(f):
        return "identitaet"
    return None


def _modell(pflicht_bestaetigt, beilagen):
    return round(pflicht_bestaetigt * MIN_ANGABE + beilagen * MIN_BEILAGE, 1)


def export_register(conn, forms, themenkatalog=None, party=None):
    """Stamps the register layer onto the exported Formulare (units, Beilagen, a
    per-Formular summary) and the Themengruppen, and returns the top-level block
    data_export["register"]. Whose Angabe a confirmed point is comes from the party
    layer (u.partei, rollen.parteien_anhaengen — run before this hook): andere_partei
    counts the points of a named party other than the applicant, partei_unklar those
    whose party is not settled. `party` (export_json.PARTY, the Lebenslagen words) is
    no longer read here and kept for the caller's signature. Raises
    sqlite3.OperationalError «no such table» when the layer is not loaded
    (export_json then skips it loudly)."""
    import sqlite3
    if not _has(conn, "register_angabe"):
        raise sqlite3.OperationalError("no such table: register_angabe")
    ang, std = regeln(conn)
    dok = [(r[0], r[1]) for r in conn.execute("SELECT register, begriff FROM register_dokument")]
    kat = [dict(r) for r in conn.execute("SELECT * FROM register ORDER BY code")]
    codes = [r["code"] for r in kat]
    # a party word («Arbeitgeber», «Ehegatte») says whose Angabe it is only for registers
    # about persons or organisations; for a building or a vehicle it says nothing
    partei_relevant = {r["code"] for r in kat if r["entitaet"] in ("natuerliche_person", "organisation")}
    zahl = {c: {"obergrenze": 0, "obergrenze_pflicht": 0, "element": 0, "bestaetigt": 0, "bestaetigt_pflicht": 0,
                "partei_offen": 0, "andere_partei": 0, "partei_unklar": 0, "eigene_partei": 0,
                "partei_art_offen": 0, "formulare_obergrenze": set(),
                "formulare_bestaetigt": set(), "beilagen": 0, "formulare_beilagen": set(), "beilagen_original": 0,
                "beilagen_rueckgabe": 0} for c in codes}
    gesamt = {"punkte": 0, "ausgeschlossen": 0, "mit_register_obergrenze": 0, "mit_register_bestaetigt": 0,
              "pflicht_bestaetigt": 0, "beilagen": 0, "beilagen_register": 0, "beilagen_ausland": 0,
              "beilagen_original": 0, "beilagen_rueckgabe": 0, "beilagen_identitaet": 0, "minuten_modell": 0.0}
    for fm in forms:
        pb = 0
        per_reg = {}
        for d in fm.get("data_fields") or []:
            subs, units = _units(d)
            for u in units:
                gesamt["punkte"] += 1
                e = u.get("ech") or {}
                if e.get("element") in CONTAINER or (u.get("begriff") or {}).get("pruefart") == "zuordnung":
                    gesamt["ausgeschlossen"] += 1
                    continue
                st = stufen(d, u, ang, std, kontext_text(fm, d, u, subs))
                if not st:
                    continue
                # stamped: the levels a source backs (element / bestaetigt); the upper bound
                # by standard follows from katalog[].standards and is not repeated per unit
                bezug = {lv: sorted(c for c, s in st.items() if s == lv) for lv in ("bestaetigt", "element")}
                bezug = {lv: v for lv, v in bezug.items() if v}
                if bezug:
                    u["register_bezug"] = bezug
                gesamt["mit_register_obergrenze"] += 1
                pinfo, pstatus = partei_von(fm, u)
                if any(s == "bestaetigt" for s in st.values()):
                    gesamt["mit_register_bestaetigt"] += 1
                    if d.get("required"):
                        pb += 1
                for c, s in st.items():
                    z = zahl[c]
                    z["obergrenze"] += 1
                    z["obergrenze_pflicht"] += bool(d.get("required"))
                    z["formulare_obergrenze"].add(fm["id"])
                    if s in ("element", "bestaetigt"):
                        z["element"] += 1
                    if s == "element":
                        z["partei_offen"] += 1
                    if s == "bestaetigt":
                        z["bestaetigt"] += 1
                        z["bestaetigt_pflicht"] += bool(d.get("required"))
                        z["formulare_bestaetigt"].add(fm["id"])
                        if c in partei_relevant:
                            # whose Angabe: the party layer (a Gesuchsteller/in that is not settled as
                            # a natural person counts as unklar, like an open party)
                            # (the four parts sum to «bestaetigt»): the submitting party — a person or,
                            # for the registers of organisations, the organisation itself —, the same
                            # party settled only as «Person oder Organisation», another party, or none
                            if pstatus == "andere_partei":
                                z["andere_partei"] += 1
                            elif pinfo and pinfo["rolle"] == "gesuchsteller":
                                z["partei_art_offen" if pinfo["entitaet"] == "gemischt" else "eigene_partei"] += 1
                            else:
                                z["partei_unklar"] += 1
                        pr = per_reg.setdefault(c, {"bestaetigt": 0, "pflicht": 0, "beilagen": 0})
                        pr["bestaetigt"] += 1
                        pr["pflicht"] += bool(d.get("required"))
        bz = 0
        for b in fm.get("beilagen") or []:
            gesamt["beilagen"] += 1
            bez = b.get("bezeichnung") or ""
            if AUSLAND.search(bez):
                gesamt["beilagen_ausland"] += 1
            regs = beilage_register(bez, b.get("halter"), dok, fm.get("title"))
            if not regs:
                continue
            warum = ersetzt_nicht(bez, fm.get("title"), [w for _, _, w in regs])
            b["register"] = [{"register": c, "grundlage": g, "begriff": w} for c, g, w in regs]
            b["register_ersetzt_nicht"] = warum
            gesamt["beilagen_register"] += 1
            gesamt["beilagen_original"] += warum == "original"
            gesamt["beilagen_rueckgabe"] += warum == "rueckgabe"
            gesamt["beilagen_identitaet"] += warum == "identitaet"
            if not warum:
                bz += 1
            for c, g, w in regs:
                zahl[c]["beilagen"] += 1
                zahl[c]["beilagen_original"] += warum == "original"
                zahl[c]["beilagen_rueckgabe"] += warum == "rueckgabe"
                zahl[c]["formulare_beilagen"].add(fm["id"])
                per_reg.setdefault(c, {"bestaetigt": 0, "pflicht": 0, "beilagen": 0})["beilagen"] += 1
        if per_reg or fm.get("burden"):
            # per Formular: what a source shows a register holds (level bestaetigt) and the
            # Beilagen it issues or holds; minuten_modell is the model estimate (see «modell»)
            fm["register"] = {
                "je_register": {c: per_reg[c] for c in sorted(per_reg)},
                "pflicht_bestaetigt": pb, "beilagen": bz,
                "minuten_modell": _modell(pb, bz)}
            gesamt["pflicht_bestaetigt"] += pb
            gesamt["minuten_modell"] += fm["register"]["minuten_modell"]
    gesamt["minuten_modell"] = round(gesamt["minuten_modell"], 1)

    zugriff = {}
    for r in conn.execute("SELECT z.register, z.art, z.adressat, z.zitat, a.article_no, l.short_title, "
                          "l.sr_number, l.cantonal_ref FROM register_zugriff z JOIN article a ON a.id=z.article_id "
                          "JOIN law l ON l.id=a.law_id ORDER BY z.register, a.article_no, z.art"):
        zugriff.setdefault(r["register"], []).append({
            "art": r["art"], "artikel": f"{r['short_title']} {r['article_no']}",
            "gesetz": r["sr_number"] or r["cantonal_ref"], "adressat": r["adressat"], "zitat": r["zitat"]})
    belege = {}
    for r in conn.execute("SELECT b.register, b.aspekt, b.zitat, q.url, q.titel FROM register_beleg b "
                          "JOIN register_quelle q ON q.id=b.quelle ORDER BY b.register, b.aspekt"):
        belege.setdefault(r["register"], []).append({"aspekt": r["aspekt"], "zitat": r["zitat"],
                                                     "quelle": r["titel"], "url": r["url"]})
    stds = {}
    for r in conn.execute("SELECT register, standard, art FROM register_standard ORDER BY register, standard"):
        stds.setdefault(r["register"], []).append(r["standard"])
    katalog = []
    for r in kat:
        z = zahl[r["code"]]
        katalog.append({**r, "standards": stds.get(r["code"], []), "belege": belege.get(r["code"], []),
                        "zugriff": zugriff.get(r["code"], []),
                        "zugriff_status": "kandidat" if any(x["art"] == "kandidat" for x in zugriff.get(r["code"], []))
                                          else "offen",
                        "zahlen": {k: (len(v) if isinstance(v, set) else v) for k, v in z.items()}})

    if themenkatalog:
        by_svc = {}
        for fm in forms:
            if fm.get("data_fields"):
                by_svc.setdefault(fm.get("service_id"), []).append(fm)
        for g in themenkatalog:
            fms = [fm for sid in g.get("services") or [] for fm in by_svc.get(sid, [])]
            if not fms:
                continue
            bu = [fm.get("burden") or {} for fm in fms]
            rg = [fm.get("register") or {} for fm in fms]
            g["register"] = {
                "n_vorbefuellbar_korrigiert": sum(b.get("prefillable", 0) for b in bu),
                "minuten_vorbefuellt": round(sum(b.get("minutes_saved", 0) for b in bu), 1),
                "n_pflicht_register": sum(x.get("pflicht_bestaetigt", 0) for x in rg),
                "n_beilagen_register": sum(x.get("beilagen", 0) for x in rg),
                "minuten_modell": round(sum(x.get("minuten_modell", 0) for x in rg), 1)}
    return {"katalog": katalog, "gesamt": gesamt,
            "modell": {"min_angabe": MIN_ANGABE, "min_beilage": MIN_BEILAGE,
                       "hinweis": "Modellschätzung mit dem Zeitmodell der Bürgerlast (Minuten je Pflichtangabe und je "
                                  "Beilage); Fallzahlen je Leistung sind Daten des Kantons und liegen nicht vor, darum "
                                  "gilt jede Zahl für einen einzigen Durchgang durch ein Formular."},
            "hinweise": {
                "formular": "Modellschätzung, obere Grenze: Angaben und Beilagen, die ein Register hält; ob die "
                            "Dienststelle sie beziehen darf, ist offen — rechtlich zu klären.",
                "themengruppe": "Summe über das Angebot der Themengruppe, keine Last einer einzelnen Person; "
                                "Modellschätzung ohne Fallzahlen.",
                "vorbefuellbar": "burden.prefillable zählt die Pflichtangaben, die citygov_prefill.json und die "
                                 "geführten Formulare mit der Einwohnerregister-Marke vorbefüllen würden: Angaben der "
                                 "einreichenden Person (Partei Gesuchsteller/in, natürliche Person), nicht mehrdeutig, "
                                 "und nach dem heutigen Wert gefragt (Zeitregel; vorbefuellbar = true). Befüllt wird aus dem Profil der Person; der Bezug aus dem "
                                 "Register selbst ist rechtlich offen. prefillable_bisher ist die frühere Zählung, "
                                 "prefillable_ausgeschlossen nennt je Grund, was sie mehr zählte, prefillable_hinzu "
                                 "die Angaben, die erst eine zitierte Regel des Einwohnerregisters belegt.",
                "beilagen": "Eine Beilage gilt als vom Register gehalten, wenn ihre Bezeichnung ein Dokument nennt, das "
                            "eine zitierte Quelle dem Register zuschreibt, oder wenn die beurteilte Halterin ein Register "
                            "ist; nie ein Formular oder Merkblatt, nie die eigene Steuererklärung oder ein Plan mit eigenen "
                            "Eintragungen, nie ein Dokument eines anderen Staats. register_ersetzt_nicht: original (das "
                            "Original wird verlangt), rueckgabe (das Dokument wird abgegeben, umgetauscht oder geändert), "
                            "identitaet (Ausweiskopie als Identitätsnachweis) — solche Beilagen zählen im Modell nicht.",
                "partei": "andere_partei = bestätigte Angaben einer anderen genannten Partei als der einreichenden "
                          "Person (Parteien-Schicht); eigene_partei = bestätigte Angaben der einreichenden Partei "
                          "(Gesuchsteller/in als natürliche Person oder Organisation); partei_unklar = bestätigte "
                          "Angaben, deren Partei nicht geklärt ist; partei_art_offen = bestätigte Angaben der "
                          "einreichenden Partei, deren Art «Person oder Organisation» bleibt; die vier ergeben bei den "
                          "Registern über Personen und Organisationen «bestaetigt». partei_offen = Angaben auf Stufe «element» (wessen Angabe es "
                          "ist, ist nicht beurteilt).",
                "beilagen_leser": "Eine Beilage zählt, wenn ihre Bezeichnung ein Dokument nennt, das eine zitierte "
                                  "Quelle dem Register zuschreibt, oder wenn die beurteilte Stelle, die das Dokument "
                                  "hält, ein Register führt — nie ein Formular oder Merkblatt, nie eine Nummer oder "
                                  "eine eigene Angabe wie die Steuererklärung, nie ein Dokument eines anderen Staats.",
                "zeit": "«Hält» zählt das Element: auch eine Angabe, die nach einem früheren, künftigen oder "
                        "geänderten Wert fragt, zählt hier, obwohl der Registereintrag den heutigen Wert hält. Die "
                        "Zeitregel gilt nur für die Vorbefüllung."},
            "stufen": {"standard": "Obergrenze: der eCH-Standard der Angabe ist einer, mit dem das Register Daten austauscht",
                       "element": "das Register führt diese Angabe laut Quelle; wessen Angabe es ist, ist offen",
                       "bestaetigt": "das Register führt diese Angabe laut Quelle, und die Art der Partei passt "
                                     "(natürliche Person bzw. Organisation)"},
            "zugriff": "Ein Register hält die Angabe; ob die Dienststelle sie beziehen darf, ist offen — rechtlich zu "
                       "klären, ausser ein Artikel in der Databank ist als Kandidat zitiert (auch dann prüfen die "
                       "Juristinnen und Juristen des Kantons)."}


# ---------------------------------------------------------------------------
# report on today's data (nothing written except --json PATH)
# ---------------------------------------------------------------------------
def bericht():
    import export_json
    conn = connect(DB_PATH)
    data, _ = export_json.build(conn)          # the export runs prefill_korrigieren and export_register
    forms = data["forms"]
    tot = data.get("vorbefuellung") or {}
    reg = data.get("register") or {"katalog": [], "gesamt": {}}
    titel = {fm["id"]: fm["title"] for fm in forms}
    diff = sorted(((fm["id"], fm["burden"]["prefillable_bisher"], fm["burden"]["prefillable"])
                   for fm in forms if fm.get("burden")), key=lambda x: -(x[1] - x[2]))
    # the flows fill exactly the vorbefuellbar points (flow_schluessel)
    flow_diff = [(fm["id"], p["feld"]) for fm in forms if fm.get("has_flow") for p in prefill_punkte(fm)
                 if p["vorbefuellbar"] != (p["feld"] in flow_schluessel(fm))]
    partei = {}
    for fm in forms:
        for p in prefill_punkte(fm):
            if p["pflicht"] and p["einwohnerregister"]:
                k = p["partei"]["rolle"] if p["partei"] else "offen"
                partei[k] = partei.get(k, 0) + 1
    out = {"prefill": tot, "prefill_flow_abweichung": flow_diff,
           "pflicht_mit_marke_je_rolle": dict(sorted(partei.items(), key=lambda kv: -kv[1])),
           "formulare_mit_vorbefuellbar": sum(1 for fm in forms if (fm.get("burden") or {}).get("prefillable")),
           "zu_hoch": [{"form": f, "titel": titel[f], "bisher": a, "korrigiert": k} for f, a, k in diff if a > k],
           "register": [{"code": k["code"], **k["zahlen"], "zugriff": k["zugriff_status"]} for k in reg["katalog"]],
           "gesamt": reg["gesamt"]}
    prefill_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "citygov_prefill.json")
    if os.path.exists(prefill_file):
        pf = json.load(open(prefill_file, encoding="utf-8"))["formulare"]
        out["prefill_datei_vergleich"] = sum(
            1 for fm in forms
            if fm.get("burden") and fm["burden"]["prefillable"] != sum(
                1 for p in pf.get(str(fm["id"]), []) if p["pflicht"] and p.get("vorbefuellbar")))
    lebenslagen = [(g["katalog"], g["gruppe"], g["register"]) for g in data.get("themenkatalog") or [] if g.get("register")]
    out["lebenslagen"] = [{"katalog": k, "gruppe": gr, **r} for k, gr, r in lebenslagen]
    out["formulare_modell"] = sorted(({"form": fm["id"], "titel": fm["title"], **{k: v for k, v in fm["register"].items()
                                                                                  if k != "hinweis"}}
                                      for fm in forms if fm.get("register")), key=lambda x: -x["minuten_modell"])
    print(json.dumps({k: v for k, v in out.items() if k not in ("formulare_modell", "lebenslagen", "zu_hoch")},
                     ensure_ascii=False, indent=1))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
    return out, data


def korrekturen_bericht():
    """--korrekturen: every quote of the correction files found again in its Formular
    text (rollen.formular_text — pypdf for a PDF Formular, imported only here), every
    Formular a name-keyed verdict reaches backed by a quote, and the state of each file
    (ausstehend / angewendet). Writes nothing; exit 1 on a finding."""
    import rollen
    conn = connect(DB_PATH)
    rows, fehler = korrekturen_lesen(conn)
    texte, n = {}, 0
    for datei, art, z, ziele, alt, neu in rows:
        zitate = z.get("zitate") or [{"form_id": z.get("form_id"), "zitat": z.get("zitat")}]
        for x in zitate:
            fid = x.get("form_id")
            if fid not in texte:
                t, quelle = rollen.formular_text(conn, fid)
                texte[fid] = (rollen.zitat_norm(t), quelle)
            n += 1
            if not rollen.zitat_im_text(x.get("zitat") or "", texte[fid][0]):
                fehler.append(f"Korrektur {datei} {z.get('subfield_id') or z.get('feld')}: Zitat «{x.get('zitat')}» "
                              f"steht nicht im Formulartext von Formular {fid} ({texte[fid][1]})")
        if art == "feld":
            formulare = {conn.execute("SELECT form_id FROM data_field WHERE id=?", [rid]).fetchone()[0] for _, rid in ziele}
            ohne = sorted(formulare - {x.get("form_id") for x in zitate})
            if ohne:
                fehler.append(f"Korrektur {datei} {z.get('feld')}: ohne Zitat für Formular {ohne}")
    stand, f2 = korrekturen_stand(conn)
    fehler += f2
    print(f"Korrekturen: {len(rows)} Einträge, {sum(len(r[3]) for r in rows)} Datenpunkte, {n} Zitate geprüft")
    for datei in sorted(stand):
        print(f"  {datei}: {stand[datei]}")
    if fehler:
        print(f"BEFUNDE ({len(fehler)}):")
        for f in fehler:
            print("  -", f)
        sys.exit(1)
    print("alle Zitate gefunden, kein Befund.")


if __name__ == "__main__":
    if "--korrekturen" in sys.argv:
        korrekturen_bericht()
    elif "--bericht" in sys.argv:
        bericht()
    else:
        main_laden(pruefen_nur="--pruefen" in sys.argv)
