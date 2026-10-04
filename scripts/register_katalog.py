#!/usr/bin/env python3
"""Catalogue of the Swiss registers that already hold data the Formulare ask for
(«Was der Kanton schon weiss», part E of the data-model programme of 2026-10-04).

Every register is a FACT with a fetched source: holder, level, what it holds, its
identifying key and the eCH standards it exchanges with are each backed by a
verbatim quote from an official page or law text that this script fetched with a
read-only GET and stored as a text snapshot under quellen/register/. A register,
a claim or a standard link whose quote is not in its snapshot is refused — no
register enters the databank from memory.

Tables (schema.sql, «Register-Katalog»):
  register_quelle    one row per fetched source (url, snapshot file, sha256 of the
                     snapshot text, fetch time)
  register           one row per register (code, name, holder, level, entity type,
                     content, key, the Schaffhausen office that keeps or feeds it)
  register_beleg     the quotes behind holder / content / key / documents
  register_standard  the eCH standards (present in ech_standard) the register
                     exchanges with — each with a quote from the standard's own
                     ech.ch page that names the register, or the project rule
                     init_register.REGISTER_STDS for the Einwohnerregister

Sources (QUELLEN) come in three kinds:
  html        an official web page or Fedlex filestore text (footnote markers are
              dropped from the text, so a quote reads like the law)
  rechtsbuch  the official Schaffhauser Rechtsbuch interface
              (rechtsbuch.sh.ch/api/de/texts_of_law/<SHR>, field selected_version.xhtml_tol)
  repo        a file already in this repository (an official eCH schema under ech_xsd/)

Commands
    python3 scripts/register_katalog.py --abrufen [--quellen DIR]
        network, read-only GETs: (re)writes the snapshots; a snapshot whose text is
        unchanged keeps its file and its fetch time (a second run changes nothing)
    python3 scripts/register_katalog.py [--quellen DIR]
        gate + load: staging -> validate -> swap; a second run reports «unverändert»
        and leaves the database file untouched
    python3 scripts/register_katalog.py --pruefen [--quellen DIR]
        gate only, nothing written

DIR defaults to quellen/register (env CITYGOV_REGISTER_QUELLEN overrides it).
Standard library only. Run before register_map.py.
"""
import hashlib
import html.parser
import json
import os
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, ROOT, SCHEMA_PATH, connect, pl

TABELLEN = ("register_quelle", "register", "register_beleg", "register_standard")
EBENEN = ("bund", "kanton", "gemeinde")
ENTITAETEN = ("natuerliche_person", "organisation", "sache", "gemischt")
ASPEKTE = ("inhaber", "inhalt", "schluessel", "dokument")
QUELLARTEN = ("html", "rechtsbuch", "repo")
FEDLEX = "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/"
RECHTSBUCH = "https://rechtsbuch.sh.ch/api/de/texts_of_law/"
ECH = "https://www.ech.ch/de/ech/ech-"


def quellen_dir(argv=None):
    argv = sys.argv if argv is None else argv
    if "--quellen" in argv:
        return os.path.abspath(argv[argv.index("--quellen") + 1])
    return os.environ.get("CITYGOV_REGISTER_QUELLEN") or os.path.join(ROOT, "quellen", "register")


# ---------------------------------------------------------------------------
# The sources: id -> (url, kind, short title). Fedlex links are the filestore
# HTML of the consolidated text in force on 2026-10-04 (found through the
# Fedlex SPARQL endpoint); the Rechtsbuch links are the canton's official API.
# ---------------------------------------------------------------------------
QUELLEN = {
    # federal law texts (Fedlex filestore)
    "fedlex_rhg": (FEDLEX + "2006/619/20220101/de/html/fedlex-data-admin-ch-eli-cc-2006-619-20220101-de-html-10.html",
                   "html", "Registerharmonisierungsgesetz (RHG, SR 431.02)"),
    "fedlex_ahvg": (FEDLEX + "63/837_843_843/20260101/de/html/fedlex-data-admin-ch-eli-cc-63-837_843_843-20260101-de-html-1.html",
                    "html", "AHV-Gesetz (AHVG, SR 831.10)"),
    "fedlex_zemisv": (FEDLEX + "2006/303/20261001/de/html/fedlex-data-admin-ch-eli-cc-2006-303-20261001-de-html.html",
                      "html", "ZEMIS-Verordnung (SR 142.513)"),
    "fedlex_uidg": (FEDLEX + "2010/705/20230901/de/html/fedlex-data-admin-ch-eli-cc-2010-705-20230901-de-html-4.html",
                    "html", "UID-Gesetz (UIDG, SR 431.03)"),
    "fedlex_uidv": (FEDLEX + "2011/81/20260715/de/html/fedlex-data-admin-ch-eli-cc-2011-81-20260715-de-html.html",
                    "html", "UID-Verordnung (UIDV, SR 431.031)"),
    "fedlex_hregv": (FEDLEX + "2007/686/20261001/de/html/fedlex-data-admin-ch-eli-cc-2007-686-20261001-de-html.html",
                     "html", "Handelsregisterverordnung (HRegV, SR 221.411)"),
    "fedlex_vgwr": (FEDLEX + "2017/376/20260715/de/html/fedlex-data-admin-ch-eli-cc-2017-376-20260715-de-html.html",
                    "html", "GWR-Verordnung (VGWR, SR 431.841)"),
    "fedlex_gbv": (FEDLEX + "2011/667/20240101/de/html/fedlex-data-admin-ch-eli-cc-2011-667-20240101-de-html-7.html",
                   "html", "Grundbuchverordnung (GBV, SR 211.432.1)"),
    "fedlex_ivzv": (FEDLEX + "2018/783/20260101/de/html/fedlex-data-admin-ch-eli-cc-2018-783-20260101-de-html-1.html",
                    "html", "Verordnung über das Informationssystem Verkehrszulassung (IVZV, SR 741.58)"),
    "fedlex_streg": (FEDLEX + "2022/600/20261001/de/html/fedlex-data-admin-ch-eli-cc-2022-600-20261001-de-html.html",
                     "html", "Strafregistergesetz (StReG, SR 330)"),
    "fedlex_schkg": (FEDLEX + "11/529_488_529/20260101/de/html/fedlex-data-admin-ch-eli-cc-11-529_488_529-20260101-de-html-3.html",
                     "html", "Bundesgesetz über Schuldbetreibung und Konkurs (SchKG, SR 281.1)"),
    "fedlex_tvdv": (FEDLEX + "2021/751/20260101/de/html/fedlex-data-admin-ch-eli-cc-2021-751-20260101-de-html-8.html",
                    "html", "Verordnung über die Identitas AG und die Tierverkehrsdatenbank (SR 916.404.1)"),
    "fedlex_tsg": (FEDLEX + "1966/1565_1621_1604/20230901/de/html/fedlex-data-admin-ch-eli-cc-1966-1565_1621_1604-20230901-de-html-9.html",
                   "html", "Tierseuchengesetz (TSG, SR 916.40)"),
    "fedlex_tsv": (FEDLEX + "1995/3716_3716_3716/20260101/de/html/fedlex-data-admin-ch-eli-cc-1995-3716_3716_3716-20260101-de-html-2.html",
                   "html", "Tierseuchenverordnung (TSV, SR 916.401)"),
    "fedlex_islv": (FEDLEX + "2013/733/20250101/de/html/fedlex-data-admin-ch-eli-cc-2013-733-20250101-de-html-3.html",
                    "html", "Verordnung über Informationssysteme im Bereich der Landwirtschaft (ISLV, SR 919.117.71)"),
    # cantonal law texts (Schaffhauser Rechtsbuch)
    "sh_gg": (RECHTSBUCH + "120.100", "rechtsbuch", "Gemeindegesetz (SHR 120.100)"),
    "sh_vewr": (RECHTSBUCH + "431.101", "rechtsbuch", "Verordnung über das Einwohnerregister (SHR 431.101)"),
    "sh_stg": (RECHTSBUCH + "641.100", "rechtsbuch", "Gesetz über die direkten Steuern (SHR 641.100)"),
    "sh_gebvg": (RECHTSBUCH + "960.100", "rechtsbuch", "Gebäudeversicherungsgesetz (SHR 960.100)"),
    "sh_av": (RECHTSBUCH + "211.441", "rechtsbuch", "Verordnung über die amtliche Vermessung (SHR 211.441)"),
    "sh_hundv": (RECHTSBUCH + "455.201", "rechtsbuch", "Verordnung zum Gesetz über das Halten von Hunden (SHR 455.201)"),
    # official agency pages
    "bj_zivilstand": ("https://www.bj.admin.ch/de/zivilstandswesen", "html", "BJ: Zivilstandswesen"),
    "bj_handelsregister": ("https://www.bj.admin.ch/de/handelsregister-zefix-und-regix", "html",
                           "BJ: Handelsregister, Zefix und Regix"),
    "kmu_uid_bur": ("https://www.kmu.admin.ch/de/uid-register-betriebs-und-unternehmensregister-bur-und-unternehmens-identifikationsnummer-uid",
                    "html", "KMU-Portal: UID-Register, BUR und UID"),
    "uid_admin": ("https://www.uid.admin.ch/", "html", "BFS: UID-Register"),
    "astra_fachanwendungen": ("https://www.astra.admin.ch/de/fachanwendungen", "html", "ASTRA: Fachanwendungen"),
    "blw_tvd": ("https://www.blw.admin.ch/de/anwendung-tvd", "html", "BLW: Tierverkehrsdatenbank"),
    "swisstopo_kataster": ("https://www.swisstopo.admin.ch/de/katasterwesen", "html", "swisstopo: Katasterwesen"),
    "cadastre_liegenschaften": ("https://www.cadastre-manual.admin.ch/de/informationsebene-liegenschaften", "html",
                                "cadastre-manual: Informationsebene «Liegenschaften»"),
    "housing_stat": ("https://www.housing-stat.ch/de/home.html", "html", "BFS: Gebäude- und Wohnungsregister (housing-stat)"),
    # eCH standard pages (each names the register it serves)
    "ech_0011": (ECH + "0011", "html", "eCH-0011"),
    "ech_0020": (ECH + "0020", "html", "eCH-0020"),
    "ech_0021": (ECH + "0021", "html", "eCH-0021"),
    "ech_0084": (ECH + "0084", "html", "eCH-0084"),
    "ech_0108": (ECH + "0108", "html", "eCH-0108"),
    "ech_0116": (ECH + "0116", "html", "eCH-0116"),
    "ech_0119": (ECH + "0119", "html", "eCH-0119"),
    "ech_0131": (ECH + "0131", "html", "eCH-0131"),
    "ech_0134": (ECH + "0134", "html", "eCH-0134"),
    "ech_0135": (ECH + "0135", "html", "eCH-0135"),
    "ech_0148": (ECH + "0148", "html", "eCH-0148"),
    "ech_0178": (ECH + "0178", "html", "eCH-0178"),
    "ech_0206": (ECH + "0206", "html", "eCH-0206"),
    "ech_0209": (ECH + "0209", "html", "eCH-0209"),
    "ech_0216": (ECH + "0216", "html", "eCH-0216"),
    "ech_0229": (ECH + "0229", "html", "eCH-0229"),
    "ech_0276": (ECH + "0276", "html", "eCH-0276"),
    "ech_0278": (ECH + "0278", "html", "eCH-0278"),
    "ech_0309": (ECH + "0309", "html", "eCH-0309"),
    # official schema file already in the repository
    "xsd_ech_0129": ("ech_xsd/eCH-0129/eCH-0129-6-0.xsd", "repo", "eCH-0129 V6.0 XML-Schema (ech_xsd)"),
}


# ---------------------------------------------------------------------------
# The registers. Every claim carries (aspekt, quelle, zitat); the gate finds the
# quote verbatim (whitespace collapsed) in the snapshot. «standards» lists
# (eCH code, quelle, zitat): the quote comes from that standard's own ech.ch page
# and names the register, or («projektregel», None) for the five person and
# address standards the export already treats as Einwohnerregister data.
# ---------------------------------------------------------------------------
REGISTER = [
    {"code": "einwohnerregister", "name": "Einwohnerregister der Gemeinden",
     "inhaber": "die Gemeinden (Einwohnerkontrolle); kantonale Koordinationsstelle: Amt für Justiz und Gemeinden",
     "ebene": "gemeinde", "entitaet": "natuerliche_person",
     "inhalt": "alle Personen, die in der Gemeinde niedergelassen sind oder sich dort aufhalten, mit den Identifikatoren "
               "und Merkmalen nach Art. 6 RHG und den zusätzlichen Daten nach Art. 88 Gemeindegesetz",
     "schluessel": "AHV-Nummer; Gebäude- und Wohnungsidentifikator (EGID, EWID) des GWR",
     "stelle_sh": "Amt für Justiz und Gemeinden",
     # no access statement without a quoted, ingested article: § 6 VEWR is not ingested
     # (register_map.ZUGRIFF waits for it), so the access stays open here
     "bemerkung": "Zugriff offen — § 6 der Verordnung über das Einwohnerregister ist noch nicht ingestiert; "
                  "rechtlich zu klären.",
     "belege": [
         ("inhaber", "sh_gg", "Die Gemeinden führen das Einwohnerregister in elektronischer Form."),
         ("inhaber", "sh_vewr", "Das Amt für Justiz und Gemeinden ist die gemäss Art. 9 des Registerharmonisierungsgesetzes (RHG) zuständige kantonale Koordinationsstelle."),
         ("inhalt", "fedlex_rhg", "Die Einwohnerregister enthalten von jeder Person, die sich niedergelassen hat oder aufhält, mindestens die Daten zu den folgenden Identifikatoren und Merkmalen:"),
         ("inhalt", "sh_gg", "Der Inhalt des Einwohnerregisters richtet sich nach Art. 6 des Registerharmonisierungsgesetzes. Im Weiteren werden im Einwohnerregister geführt:"),
         ("schluessel", "fedlex_rhg", "AHV-Nummer nach Artikel 50c des Bundesgesetzes vom 20. Dezember 1946 über die Alters- und Hinterlassenenversicherung (AHVG);"),
         ("schluessel", "fedlex_rhg", "Gebäudeidentifikator nach dem eidgenössischen Gebäude- und Wohnungsregister (GWR) des Bundesamtes;"),
         ("dokument", "sh_vewr", "kann bei der registerführenden Stelle die Ausstellung eines Heimatausweises verlangen."),
     ],
     "standards": [
         ("eCH-0044", "projektregel", None), ("eCH-0010", "projektregel", None),
         ("eCH-0011", "projektregel", None), ("eCH-0007", "projektregel", None),
         ("eCH-0008", "projektregel", None),
         ("eCH-0011", "ech_0011", "Der Merkmalskatalog basiert auf dem Registerharmonisierungsgesetz [RHG]."),
         ("eCH-0020", "ech_0020", "welche zu Mutationen der Daten in den Einwohnerregistern führen"),
         ("eCH-0021", "ech_0021", "welche in den Einwohnerregistern geführt und evtl. elektronisch ausgetauscht werden"),
     ]},
    {"code": "infostar", "name": "Informatisiertes Standesregister (Infostar)",
     "inhaber": "die Zivilstandsämter der Kantone; betrieben vom Bundesamt für Justiz (Fachbereich Infostar)",
     "ebene": "bund", "entitaet": "natuerliche_person",
     "inhalt": "alle Zivilstandsereignisse und der Personen- und Familienstand (Geburt, Ehe, eingetragene Partnerschaft, "
               "Tod, Abstammung, Name, Staatsangehörigkeit, Bürgerrecht)",
     "schluessel": None, "stelle_sh": None, "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_rhg", "das von den Kantonen geführte und vom Bundesamt für Justiz betriebene Informatisierte Standesregister (Infostar);"),
         ("inhaber", "bj_zivilstand", "Das elektronische Zivilstandsregister (Informatisiertes Standesregister Infostar) wird vom Bund betrieben, im dafür zuständigen Fachbereich Infostar (FIS) innerhalb des Bundesamtes für Justiz BJ."),
         ("inhalt", "bj_zivilstand", "Seit 2005 werden alle Zivilstandsereignisse im Personenstandsregister, an welches alle schweizerischen Zivilstandsämter angeschlossen sind, beurkundet."),
         ("inhalt", "bj_zivilstand", "Angaben über den Personen- und Familienstand einer Person (wie Mündigkeit, Abstammung, Verhältnis zum Ehegatten oder Partner, Name und Staatsangehörigkeit)."),
         ("dokument", "bj_zivilstand", "Urkunden über den Personenstand und den Familienstand (Personenstandsausweis, Familienausweis, Partnerschaftsausweis, Ausweis über den registrierten Familienstand usw.) werden durch das Zivilstandsamt am Heimatort erstellt."),
     ],
     "standards": [
         ("eCH-0135", "ech_0135", "welche vom elektronischen Personenstandsregister Infostar zur Verfügung gestellt werden"),
     ]},
    {"code": "zemis", "name": "Zentrales Migrationsinformationssystem (ZEMIS)",
     "inhaber": "Staatssekretariat für Migration (SEM); Meldungen der kantonalen Ausländerbehörden",
     "ebene": "bund", "entitaet": "natuerliche_person",
     "inhalt": "Personendaten aus dem Ausländer- und Asylbereich: Personalien, Personennummer, AHV-Nummer, Bewilligungen",
     "schluessel": "ZEMIS-Personennummer; AHV-Nummer", "stelle_sh": "Migrationsamt und Passbüro", "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_rhg", "das zentrale Migrationsinformationssystem (ZEMIS) des Staatssekretariats für Migration;"),
         ("inhaber", "fedlex_zemisv", "Die kantonalen und kommunalen Ausländerbehörden, die für den Vollzug der Landesverweisung zuständigen Behörden sowie die kantonalen und kommunalen Arbeitsmarktbehörden melden unverzüglich:"),
         ("inhalt", "fedlex_zemisv", "Personalien der betroffenen Person (Namen, Vornamen, Aliasnamen, Geburtsdatum, Geschlecht, Staatsangehörigkeit, Zivilstand);"),
         ("inhalt", "fedlex_zemisv", "die erstmaligen Kurzaufenthalts- oder Aufenthaltsbewilligungen sowie deren Erneuerung, Verlängerung, Änderung oder Widerruf und die arbeitsmarktlichen Vorentscheide;"),
         ("schluessel", "fedlex_zemisv", "Personennummer;"),
     ],
     "standards": []},
    {"code": "ahv_versichertenregister", "name": "Zentrales Versichertenregister der AHV (UPI)",
     "inhaber": "Zentrale Ausgleichsstelle (ZAS)",
     "ebene": "bund", "entitaet": "natuerliche_person",
     "inhalt": "die Versicherten mit ihrer AHV-Nummer und den demographischen Attributen (Personendatenbank UPI)",
     "schluessel": "AHV-Nummer", "stelle_sh": None, "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_ahvg", "Die Zentrale Ausgleichsstelle führt ein zentrales Versichertenregister mit dem Zweck:"),
         ("inhalt", "fedlex_ahvg", "die Versicherten und deren AHV-Nummer;"),
         ("inhalt", "ech_0084", "Zu diesem Zweck betreibt die ZAS eine Personendatenbank namens „UPI“, die zusätzlich zur AHVN auch die demographischen Attribute der Personen speichert."),
         ("schluessel", "fedlex_ahvg", "den versicherten Personen eine AHV-Nummer nach Artikel 50c zuzuweisen;"),
     ],
     "standards": [
         ("eCH-0084", "ech_0084", "Der eCH-0084 Schnittstellen-Standard umfasst alle Meldungen, die in UPI schreiben."),
     ]},
    {"code": "uid_register", "name": "UID-Register",
     "inhaber": "Bundesamt für Statistik (BFS)",
     "ebene": "bund", "entitaet": "organisation",
     "inhalt": "alle UID-Einheiten mit UID, Name oder Firma, Adresse, Status im Handels- und im Mehrwertsteuerregister "
               "und Angaben zur wirtschaftlichen Tätigkeit",
     "schluessel": "Unternehmens-Identifikationsnummer (UID, CHE-…)", "stelle_sh": None, "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_uidg", "Das BFS führt das UID-Register."),
         ("inhalt", "fedlex_uidg", "Das UID-Register enthält die Daten zu folgenden Merkmalen der UID-Einheiten (UID-Daten):"),
         ("inhalt", "fedlex_uidg", "Name, Firma oder Bezeichnung und Adresse,"),
         ("inhalt", "uid_admin", "Sitz- oder Domiziladresse der UID-Einheit"),
         ("schluessel", "fedlex_uidg", "UID: nichtsprechende und unveränderliche Nummer, die eine UID-Einheit eindeutig identifiziert;"),
     ],
     "standards": [
         ("eCH-0108", "ech_0108", "zwischen den Unternehmensregistern des Bundesamtes für Statistik (BFS), namentlich UID-Register sowie Betriebs- und Unternehmensregister (BUR) und den Behörden der Schweiz."),
         ("eCH-0116", "ech_0116", "welche zu Mutationen der Daten von Unternehmen im Bereich des UID-Registers führen"),
         ("eCH-0098", "ech_0116", "Voraussetzungen: Version ist abhängig von eCH-0108 Datenstandard Unternehmensregister (UID-Register) V5.1 eCH-0058 Schnittstellenstandard Meldungsrahmen V5.0 eCH-0098 Datenstandard Unternehmensdaten V5.1"),
     ]},
    {"code": "handelsregister", "name": "Handelsregister (kantonale Handelsregisterämter, Zentralregister Zefix)",
     "inhaber": "die kantonalen Handelsregisterämter; das Eidgenössische Amt für das Handelsregister (EHRA) führt das Zentralregister",
     "ebene": "kanton", "entitaet": "organisation",
     "inhalt": "die Rechtseinheiten mit Firma, UID, Sitz, Rechtsform, Zweck, Kapital, Organen, vertretungsberechtigten "
               "Personen und Revisionsstelle",
     "schluessel": "Unternehmens-Identifikationsnummer (UID)", "stelle_sh": "Handelsregisteramt", "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_hregv", "Die Organisation der Handelsregisterämter obliegt den Kantonen."),
         ("inhaber", "bj_handelsregister", "Das Eidg. Amt für das Handelsregister führt ein Firmenzentralregister. Dieses wird täglich aktualisiert über den zentralen Firmenindex Zefix® zugänglich gemacht."),
         ("inhalt", "fedlex_hregv", "Das Tages- und das Hauptregister enthalten Einträge über:"),
         ("inhalt", "fedlex_hregv", "die Firma und die Unternehmens-Identifikationsnummer;"),
         ("schluessel", "kmu_uid_bur", "Seit dem 1. Januar 2014 ist die UID die gültige Identifikationsnummer für das Handelsregister (HR) wie auch für die Mehrwertsteuer (MWST)."),
         ("dokument", "fedlex_hregv", "beglaubigte Auszüge über die Einträge einer Rechtseinheit im Hauptregister;"),
     ],
     "standards": []},
    {"code": "bur", "name": "Betriebs- und Unternehmensregister (BUR)",
     "inhaber": "Bundesamt für Statistik (BFS)",
     "ebene": "bund", "entitaet": "organisation",
     "inhalt": "alle Unternehmen und örtlichen Einheiten mit wirtschaftlicher Tätigkeit in der Schweiz; ein "
               "Statistikregister, nicht öffentlich",
     "schluessel": "BUR-Nummer", "stelle_sh": None,
     "bemerkung": "Statistikregister: die Daten dienen statistischen Zwecken; ein Bezug für Verwaltungsverfahren ist "
                  "rechtlich zu klären.",
     "belege": [
         ("inhaber", "kmu_uid_bur", "Das Betriebs- und Unternehmensregister (BUR) wird vom Bundesamt für Statistik (BFS) geführt und enthält sämtliche Unternehmen und Betriebe privaten und öffentlichen Rechts, die ihren Sitz in der Schweiz haben."),
         ("inhalt", "kmu_uid_bur", "Das BUR ist ein Statistikregister, das gemäss den gesetzlichen Bestimmungen nicht öffentlich ist."),
         ("schluessel", "fedlex_islv", "Identifikationsnummer im Betriebs- und Unternehmensregister (BUR-Nummer)"),
     ],
     "standards": [
         ("eCH-0108", "ech_0108", "zwischen den Unternehmensregistern des Bundesamtes für Statistik (BFS), namentlich UID-Register sowie Betriebs- und Unternehmensregister (BUR) und den Behörden der Schweiz."),
     ]},
    {"code": "gwr", "name": "Eidgenössisches Gebäude- und Wohnungsregister (GWR)",
     "inhaber": "Bundesamt für Statistik (BFS); nachgeführt von den Bauämtern der Gemeinden und Kantone",
     "ebene": "bund", "entitaet": "sache",
     "inhalt": "Bauprojekte, Gebäude und Wohnungen mit Identifikatoren, Adressen, Kategorie, Baujahr, Dimensionen, "
               "Heizsystem und Wohnungsmerkmalen",
     "schluessel": "EGID (Gebäude), EDID (Eingang), EWID (Wohnung)", "stelle_sh": None, "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_vgwr", "Das Bundesamt für Statistik (BFS) führt das eidgenössische Gebäude- und Wohnungsregister (GWR) als Referenzinformationssystem für Zwecke der Statistik, Forschung und Planung."),
         ("inhalt", "fedlex_vgwr", "Im GWR werden zu jedem Gebäude und zu jedem gebäudeähnlichen Objekt folgende Informationen geführt:"),
         ("inhalt", "fedlex_vgwr", "Im GWR werden zu jeder Wohnung und zu jedem wohnungsähnlichen Objekt folgende Informationen geführt:"),
         ("schluessel", "fedlex_vgwr", "vom BFS zugewiesener Identifikator für Gebäude und gebäudeähnliche Objekte (EGID);"),
         ("schluessel", "housing_stat", "Von Adresse zu EGID, EDID und EWID"),
     ],
     "standards": [
         ("eCH-0206", "ech_0206", "Der vorliegende Standard eCH-0206 beschreibt den GWR-Datenzugang für die berechtigten Stellen gemäss Art. 15 VGWR."),
         ("eCH-0216", "ech_0216", "Der vorliegende Standard beschreibt die Art der Nachführung des GWR und die Meldungen, mit denen die Nachführung vorgenommen werden kann."),
         ("eCH-0129", "ech_0206", "Voraussetzungen: Version ist abhängig von eCH-0129 Objektwesen V5.0"),
     ]},
    {"code": "grundbuch", "name": "Grundbuch",
     "inhaber": "die kantonalen Grundbuchämter; Oberaufsicht: Eidgenössisches Amt für Grundbuch- und Bodenrecht (EGBA)",
     "ebene": "kanton", "entitaet": "sache",
     "inhalt": "die Grundstücke mit ihrer Bezeichnung und den dinglichen Rechten: Eigentum, Dienstbarkeiten, "
               "Grundlasten, Anmerkungen",
     "schluessel": "Gemeinde und Grundstücksnummer; eidgenössische Grundstücksidentifikation (E-GRID)",
     "stelle_sh": "Grundbuchamt Notariat", "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_gbv", "Die Organisation der Grundbuchämter und der Grundbuchführung obliegt den Kantonen."),
         ("inhaber", "fedlex_gbv", "Das Eidgenössische Amt für Grundbuch- und Bodenrecht (EGBA) im Bundesamt für Justiz übt die Oberaufsicht über die Grundbuchführung in den Kantonen und über die privaten Aufgabenträger nach Artikel 949d ZGB aus."),
         ("inhalt", "fedlex_gbv", "die Bezeichnung des Grundstücks und die Grundstücksbeschreibung, den Namen und die Identifikation des Eigentümers oder der Eigentümerin, die Eigentumsform und das Erwerbsdatum"),
         ("inhalt", "fedlex_gbv", "die Dienstbarkeiten und Grundlasten;"),
         ("schluessel", "fedlex_gbv", "die Gemeinde und eine Grundstücksnummer; ist die Gemeinde grundbuchmässig in mehrere Einheiten aufgeteilt, so werden auch diese angegeben;"),
         ("schluessel", "fedlex_gbv", "für den Datenaustausch zwischen Informatiksystemen eine eidgenössische Grundstücksidentifikation (E-GRID)."),
         ("dokument", "fedlex_gbv", "Jede Person kann vom Grundbuchamt, ohne ein Interesse glaubhaft zu machen, Auskunft oder einen Auszug über die folgenden rechtswirksamen Daten des Hauptbuchs verlangen:"),
     ],
     "standards": [
         ("eCH-0134", "ech_0134", "Das vorliegende Dokument definiert die Meldungen des Objektwesens aus dem Grundbuch an Dritte"),
         ("eCH-0209", "ech_0209", "Das vorliegende Dokument definiert die Meldungen des Objektwesens in der Domäne Grundbuch"),
         ("eCH-0178", "ech_0178", "welcher beim Austausch von Grundbuchmeldungen die Geschäftsdaten"),
         ("eCH-0129", "ech_0134", "Voraussetzung für das Verständnis des vorliegenden Dokuments ist die Kenntnis der Datenstandards eCH Standards eCH-0129"),
     ]},
    {"code": "amtliche_vermessung", "name": "Amtliche Vermessung",
     "inhaber": "die Kantone (in Schaffhausen das Amt für Geoinformation); Oberaufsicht: Bund (swisstopo)",
     "ebene": "kanton", "entitaet": "sache",
     "inhalt": "die Geodaten über die Grundstücke: Liegenschaften mit ihren Grenzen, Gebäude, Bodenbedeckung und "
               "Nomenklatur; Grundlage des Plans für das Grundbuch",
     "schluessel": "eidgenössische Grundstücksidentifikation (E-GRID)", "stelle_sh": "Amt für Geoinformation",
     "bemerkung": None,
     "belege": [
         ("inhaber", "sh_av", "Die Auszüge und Dokumentationen werden vom Amt für Geoinformation aufbewahrt."),
         ("inhalt", "cadastre_liegenschaften", "Zur Informationsebene Liegenschaften gehören die Grundstücke nach Artikel 655 Absatz 2 ZGB, soweit sie flächenmässig ausgeschieden werden können, mit Aus­nahme der Miteigentumsanteile."),
         ("schluessel", "cadastre_liegenschaften", "Gestützt auf Artikel 18 GBV führte der Bund zu diesem Zweck die eindeutige Eidgenössische Grundstücksidentifikation (E-GRID) ein."),
     ],
     "standards": [
         ("eCH-0131", "ech_0131", "Das vorliegende Dokument definiert die Meldungen des Objektwesens in der Domäne der amtlichen Vermessung (AV)"),
         ("eCH-0129", "ech_0131", "die dabei genutzten Entitäten des Austauschdatenmodells [eCH-0129]"),
     ]},
    {"code": "gebaeudeversicherung", "name": "Verwaltungsregister der Gebäudeversicherung des Kantons Schaffhausen",
     "inhaber": "Gebäudeversicherung des Kantons Schaffhausen (selbständige juristische Person des öffentlichen Rechts)",
     "ebene": "kanton", "entitaet": "sache",
     "inhalt": "alle Gebäude im Kanton, die bei der Gebäudeversicherung obligatorisch versichert sind, mit "
               "Versicherungswert und Schätzung",
     "schluessel": "Gebäudeversicherungsnummer (eCH-0129: buildingInsuranceNumberType)",
     "stelle_sh": "Gebäudeversicherung", "bemerkung": None,
     "belege": [
         ("inhaber", "sh_gebvg", "Unter dem Namen «Gebäudeversicherung des Kantons Schaffhausen» (nachstehend Gebäudeversicherung genannt) besteht eine selbständige juristische Person des öffentlichen Rechts mit Sitz in Schaffhausen."),
         ("inhalt", "sh_gebvg", "Alle Gebäude im Kanton sind für die nach diesem Gesetz versicherten Gefahren bei der Gebäudeversicherung versichert und dürfen nicht anderweitig versichert werden."),
         ("inhalt", "fedlex_vgwr", "Verwaltungsregister der kantonalen Gebäudeversicherungen;"),
         ("schluessel", "xsd_ech_0129", '<xs:element name="insuranceNumber" type="eCH-0129:buildingInsuranceNumberType"/>'),
     ],
     "standards": []},
    {"code": "steuerregister", "name": "Kantonales Steuerregister (Steuerverwaltung)",
     "inhaber": "Kantonale Steuerverwaltung Schaffhausen",
     "ebene": "kanton", "entitaet": "gemischt",
     "inhalt": "die Steuerpflichtigen (natürliche und juristische Personen) mit Steuererklärungen, Veranlagungen und "
               "Steuerakten; unter Geheimhaltungspflicht (Art. 127 StG)",
     "schluessel": None, "stelle_sh": "Steuerverwaltung",
     "bemerkung": "Steuerdaten unterliegen der Geheimhaltungspflicht; eine Auskunft braucht eine gesetzliche Grundlage "
                  "(Art. 127 Abs. 2 StG).",
     "belege": [
         ("inhaber", "fedlex_uidv", "Register der AHV-Ausgleichskassen, kantonale Steuerregister, Mehrwertsteuerregister;"),
         ("inhaber", "sh_stg", "Die Durchführung dieses Gesetzes obliegt, soweit nicht besondere Behörden bezeichnet sind, der kantonalen Steuerverwaltung."),
         ("inhalt", "sh_stg", "Die kantonale Steuerverwaltung speichert elektronische Eingaben auf einem vom Kanton betriebenen Server."),
         ("inhalt", "sh_stg", "Wer mit dem Vollzug dieses Gesetzes betraut ist oder dazu beigezogen wird, muss über Tatsachen, die ihm bzw. ihr in Ausübung des Amtes bekannt werden, und über die Verhandlungen in den Behörden Stillschweigen bewahren und Dritten den Einblick in amtliche Akten verweigern."),
     ],
     "standards": [
         ("eCH-0119", "ech_0119", "beschreibt das Austauschformat für die Steuermeldung der natürlichen Personen"),
         ("eCH-0278", "ech_0278", "für die Steuern von natürlichen Personen basierend auf dem Datenmodell der Schweizerischen Steuerkonferenz"),
         ("eCH-0276", "ech_0276", "beschreibt das Austauschformat für die E-Bilanz und E-Tax der juristischen Personen"),
         ("eCH-0229", "ech_0229", "beschreibt das Austauschformat für die Steuermeldung der juristischen Personen"),
         ("eCH-0148", "ech_0148", "welche zu Mutationen der Daten von Unternehmen im Bereich der Steuern führen"),
     ]},
    {"code": "ivz", "name": "Informationssystem Verkehrszulassung (IVZ)",
     "inhaber": "Bundesamt für Strassen (ASTRA); die kantonalen Strassenverkehrsämter übermitteln die Daten",
     "ebene": "bund", "entitaet": "gemischt",
     "inhalt": "Fahrzeuge mit Halterinnen und Haltern und Kontrollschildern (IVZ-Fahrzeuge) sowie Fahrberechtigungen "
               "und Ausweise (IVZ-Personen)",
     "schluessel": "Stammnummer, Fahrgestellnummer, Kontrollschild; PIN IVZ-Personen",
     "stelle_sh": "Strassenverkehrs- und Schifffahrtsamt", "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_ivzv", "Das Bundesamt für Strassen (ASTRA) führt das IVZ und trägt die Verantwortung für das Informationssystem."),
         ("inhaber", "fedlex_ivzv", "Die für die Erteilung und den Entzug der Fahrzeugausweise zuständigen Behörden des Bundes und der Kantone übermitteln dem IVZ die in ihrem Zuständigkeitsbereich befindlichen Daten nach Artikel 4 sowie Änderungen dieser Daten."),
         ("inhalt", "astra_fachanwendungen", "Hierfür betreibt es das zentrale Informationssystem Verkehrszulassung IVZ mit den Registern Personen, Fahrzeuge, Massnahmen und Auswertungen."),
         ("inhalt", "fedlex_ivzv", "Das Subsystem IVZ-Fahrzeuge enthält folgende Daten zu den von schweizerischen Behörden zugelassenen oder für die Zulassung vorgesehenen Fahrzeugen:"),
         ("schluessel", "fedlex_ivzv", "persönliche Identifikationsnummer (PIN IVZ-Personen)"),
         ("schluessel", "fedlex_ivzv", "Kontrollschildidentifikation"),
         # «Führerausweisdaten» occurs only in the tachograph-card annex and in IVZ-Massnahmen;
         # IVZ-Personen names «Ausweisdaten» of driving permits, not the Führerausweis — no document rule
         ("dokument", "fedlex_ivzv", "Fahrzeugausweisdaten"),
     ],
     "standards": []},
    {"code": "vostra", "name": "Strafregister-Informationssystem VOSTRA",
     "inhaber": "Bundesamt für Justiz (BJ)",
     "ebene": "bund", "entitaet": "natuerliche_person",
     "inhalt": "Strafurteile und hängige Strafverfahren; der Privatauszug zeigt die Daten des Behördenauszugs 4 ohne "
               "hängige Verfahren",
     "schluessel": None, "stelle_sh": None, "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_streg", "Das Bundesamt für Justiz ist das für VOSTRA verantwortliche Bundesorgan."),
         ("inhalt", "fedlex_streg", "Der Privatauszug vermittelt Zugang zu den Daten des Behördenauszugs 4 (Art. 40), mit Ausnahme der Daten über hängige Strafverfahren (Art. 24)."),
         ("dokument", "fedlex_streg", "Im Bereich der Strafdatenverwaltung ist jedem Zugangsprofil ein eigener Strafregisterauszug zugeordnet, der online angezeigt oder gedruckt werden kann."),
     ],
     "standards": []},
    {"code": "betreibungsregister", "name": "Betreibungsregister (Protokolle und Register der Betreibungsämter)",
     "inhaber": "die Betreibungs- und Konkursämter (in Schaffhausen: Betreibungs- und Konkursamt)",
     "ebene": "kanton", "entitaet": "gemischt",
     "inhalt": "die Betreibungen und Konkurse; Auszüge an Personen mit glaubhaft gemachtem Interesse",
     "schluessel": None, "stelle_sh": "Betreibungs- und Konkursamt", "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_schkg", "die Protokolle und Register der Betreibungs- und der Konkursämter einsehen"),
         ("inhalt", "fedlex_schkg", "Jede Person, die ein Interesse glaubhaft macht, kann die Protokolle und Register der Betreibungs- und der Konkursämter einsehen und sich Auszüge daraus geben lassen."),
         ("dokument", "fedlex_schkg", "und sich Auszüge daraus geben lassen."),
     ],
     "standards": []},
    {"code": "tvd", "name": "Tierverkehrsdatenbank (TVD)",
     "inhaber": "Identitas AG im Auftrag des Bundesamts für Landwirtschaft (BLW)",
     "ebene": "bund", "entitaet": "gemischt",
     "inhalt": "Tierhaltungen, Tierhalterinnen und Tierhalter, Nutztiere mit Identifikationsnummer und Tierverkehr "
               "(Geburten, Standortwechsel, Schlachtungen)",
     "schluessel": "Ohrmarkennummer bzw. UELN des Tiers; TVD-Nummer der Tierhaltung", "stelle_sh": None,
     "bemerkung": None,
     "belege": [
         ("inhaber", "blw_tvd", "Im Auftrag des Bundesamts für Landwirtschaft wird die Tierverkehrsdatenbank (TVD) von der Identitas AG betrieben."),
         ("inhalt", "fedlex_tvdv", "die Daten zu Tierhaltungen, Tierhalterinnen und Tierhaltern nach den Artikeln 12–15;"),
         ("inhalt", "fedlex_tvdv", "die Daten zu Tieren und zum Tierverkehr nach den Artikeln 15–21;"),
         ("schluessel", "fedlex_tvdv", "bei Equiden: Universal Equine Life Number (UELN) nach Artikel 15d Absatz 1 Buchstabe b TSV;"),
         ("schluessel", "fedlex_islv", "Nummer für die Tierverkehrsdatenbank (TVD-Nummer)"),
     ],
     "standards": [
         ("eCH-0309", "ech_0309", "beschreibt die Daten der Tierverkehrsdatenbank (TVD) auf semantischer Ebene."),
     ]},
    {"code": "hundedatenbank", "name": "Hundedatenbank nach Art. 30 Abs. 2 TSG",
     "inhaber": "Betreiberin der Hundedatenbank; die Kantone sorgen für die Registrierung (in Schaffhausen über die "
                "Hundekontrolle der Gemeinden)",
     "ebene": "bund", "entitaet": "gemischt",
     "inhalt": "alle Hunde mit Mikrochipnummer, Name, Geschlecht, Geburtsdatum, Rasse und die Hundehalterinnen und "
               "Hundehalter",
     "schluessel": "Mikrochipnummer des Hundes", "stelle_sh": None, "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_tsg", "Die Hunde müssen in einer zentralen Datenbank registriert sein. Die Kantone sorgen für die Registrierung."),
         ("inhaber", "sh_hundv", "Die Gemeinden führen eine Hundekontrolle. Sie können zu diesem Zweck die zentrale Datenbank gemäss Art. 30 des Tierseuchengesetzes einsetzen."),
         ("inhalt", "fedlex_tsv", "Sie erfasst die Daten in der Datenbank nach Artikel 30 Absatz 2 TSG (Hundedatenbank)."),
         ("inhalt", "fedlex_tsv", "Bei der Kennzeichnung werden folgende Daten über den Hund erhoben:"),
         ("schluessel", "fedlex_tsv", "Mikrochipnummer."),
     ],
     "standards": []},
    {"code": "agis", "name": "Agrarpolitisches Informationssystem AGIS (Betriebs-, Struktur- und Beitragsdaten)",
     "inhaber": "Bundesamt für Landwirtschaft (BLW); die Kantone beschaffen und übermitteln die Daten",
     "ebene": "bund", "entitaet": "gemischt",
     "inhalt": "Betriebsdaten (Bewirtschafterin oder Bewirtschafter, Betrieb), Strukturdaten (Flächen, Tiere) und "
               "Daten zu Direktzahlungen",
     "schluessel": "kantonale Betriebsnummer, BUR-Nummer, UID, TVD-Nummer", "stelle_sh": "Landwirtschaftsamt",
     "bemerkung": None,
     "belege": [
         ("inhaber", "fedlex_islv", "Die Kantone übermitteln die Daten an das Bundesamt für Landwirtschaft (BLW) innerhalb folgender Fristen:"),
         ("inhaber", "fedlex_islv", "Die Kantone beschaffen die Daten."),
         ("inhalt", "fedlex_islv", "Das Informationssystem für Betriebs-, Struktur- und Beitragsdaten (AGIS) enthält folgende Daten:"),
         ("schluessel", "fedlex_islv", "Identifikationsnummern der jeweiligen Betriebsform: Kantonale Betriebsnummer, Identifikationsnummer im Betriebs- und Unternehmensregister (BUR-Nummer), Unternehmens-Identifikationsnummer (UID), Nummer für die Tierverkehrsdatenbank (TVD-Nummer)"),
     ],
     "standards": []},
]


# ---------------------------------------------------------------------------
# snapshots
# ---------------------------------------------------------------------------
class _Text(html.parser.HTMLParser):
    """Visible text of a page: scripts/styles/head dropped, block elements on their
    own lines, Fedlex footnote markers (<sup><a href="#fn-…">n</a></sup>) dropped."""
    SKIP = {"script", "style", "noscript", "svg", "template", "head"}
    BLOCK = {"p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "br", "section",
             "article", "dd", "dt", "ul", "ol", "table", "header", "footer", "nav", "main", "aside",
             "option", "title", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.sup, self.fn = [], 0, 0, False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "sup":
            self.sup += 1
        elif tag == "a" and self.sup and (dict(attrs).get("href") or "").startswith("#fn"):
            self.fn = True
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "sup" and self.sup:
            self.sup -= 1
            if not self.sup:
                self.fn = False
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip and not self.fn:
            self.out.append(data)


def html_text(raw):
    p = _Text()
    p.feed(raw)
    p.close()
    t = "".join(p.out).replace("\xa0", " ").replace("­", "")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in t.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def norm(s):
    """Quote matching: whitespace collapsed, non-breaking space and soft hyphen removed."""
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ").replace("­", "")).strip()


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get(url):
    # imported here, not at the top: validate_db.py imports this module (through
    # register_map.pruefen) and must load no network code
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "citygov-register-katalog (read-only)",
                                               "Accept-Language": "de-CH,de;q=0.9"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        cs = r.headers.get_content_charset() or "utf-8"
    return body.decode(cs, errors="replace")


def text_der_quelle(qid):
    """Fetch (or read, for repo files) one source and return its text."""
    url, art, _ = QUELLEN[qid]
    if art == "repo":
        with open(os.path.join(ROOT, url), encoding="utf-8") as fh:
            return fh.read()
    raw = _get(url)
    if art == "rechtsbuch":
        return html_text(json.loads(raw)["text_of_law"]["selected_version"]["xhtml_tol"] or "")
    return html_text(raw)


def datei(qid):
    return qid + ".txt"


def snapshot_lesen(qdir, qid):
    """(header dict, text) of a snapshot, or (None, None) when the file is missing."""
    path = os.path.join(qdir, datei(qid))
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    head, _, text = raw.partition("\n---\n")
    meta = dict(ln.split(": ", 1) for ln in head.splitlines() if ": " in ln)
    return meta, text


def abrufen(qdir):
    """Fetch every source; keep a snapshot whose text did not change (and its time)."""
    os.makedirs(qdir, exist_ok=True)
    neu = gleich = fehler = 0
    for qid, (url, art, titel) in QUELLEN.items():
        try:
            text = text_der_quelle(qid)
        except Exception as ex:                       # network: report, keep the old snapshot
            print(f"  FEHLER {qid}: {type(ex).__name__}: {ex}")
            fehler += 1
            continue
        if not text.strip():
            print(f"  FEHLER {qid}: leerer Text")
            fehler += 1
            continue
        meta, alt = snapshot_lesen(qdir, qid)
        if alt is not None and alt == text and meta.get("url") == url:
            gleich += 1
            continue
        stamp = datetime.now().replace(microsecond=0).isoformat()
        with open(os.path.join(qdir, datei(qid)), "w", encoding="utf-8") as fh:
            fh.write(f"url: {url}\nart: {art}\ntitel: {titel}\nabgerufen: {stamp}\nsha256: {sha(text)}\n---\n{text}")
        neu += 1
        print(f"  {qid}: {len(text)} Zeichen gespeichert")
    print(f"Quellen: {neu} neu oder geändert, {gleich} unverändert, {fehler} Fehler ({qdir})")
    return fehler


# ---------------------------------------------------------------------------
# rows + gate
# ---------------------------------------------------------------------------
def projektregel():
    """The five standards the export treats as Einwohnerregister data (one rule)."""
    import init_register
    return set(init_register.REGISTER_STDS)


def zeilen(qdir, conn):
    """Build every row of the four tables and the list of gate errors.
    A row is only produced when its evidence passed."""
    fehler = []
    q_rows, texte = [], {}
    for qid, (url, art, titel) in QUELLEN.items():
        if art not in QUELLARTEN:
            fehler.append(f"Quelle {qid}: Art {art} unbekannt")
            continue
        meta, text = snapshot_lesen(qdir, qid)
        if text is None:
            fehler.append(f"Quelle {qid}: kein abgerufener Text ({datei(qid)} fehlt — erst --abrufen)")
            continue
        if meta.get("url") != url:
            fehler.append(f"Quelle {qid}: Text stammt von {meta.get('url')}, erwartet {url}")
            continue
        if meta.get("sha256") != sha(text):
            fehler.append(f"Quelle {qid}: sha256 des Texts stimmt nicht (Datei verändert?)")
            continue
        texte[qid] = norm(text)
        q_rows.append((qid, url, art, titel, datei(qid), meta["sha256"], meta.get("abgerufen") or ""))

    std_codes = {r[0]: r[1] for r in conn.execute("SELECT code, url FROM ech_standard")}
    stellen = {r[0] for r in conn.execute("SELECT name FROM dienststelle")}
    regel = projektregel()
    r_rows, b_rows, s_rows = [], [], []
    codes = set()
    for reg in REGISTER:
        c = reg["code"]
        if not re.fullmatch(r"[a-z][a-z_]*", c) or c in codes:
            fehler.append(f"Register {c}: Code ungültig oder doppelt")
            continue
        codes.add(c)
        if reg["ebene"] not in EBENEN or reg["entitaet"] not in ENTITAETEN:
            fehler.append(f"Register {c}: Ebene/Entität ausserhalb der Liste")
        if reg.get("stelle_sh") and reg["stelle_sh"] not in stellen:
            fehler.append(f"Register {c}: Dienststelle «{reg['stelle_sh']}» fehlt in dienststelle")
        for feld in ("name", "inhaber", "inhalt"):
            if not (reg.get(feld) or "").strip():
                fehler.append(f"Register {c}: {feld} leer")
        aspekte = set()
        for aspekt, qid, zitat in reg["belege"]:
            if aspekt not in ASPEKTE:
                fehler.append(f"Register {c}: Aspekt {aspekt} unbekannt")
            elif qid not in texte:
                fehler.append(f"Register {c}: Beleg aus Quelle {qid} ohne gültigen Text")
            elif len(norm(zitat)) < 12 or norm(zitat) not in texte[qid]:
                fehler.append(f"Register {c}: Zitat nicht in {qid}: «{zitat[:80]}»")
            else:
                aspekte.add(aspekt)
                b_rows.append((c, aspekt, qid, zitat))
        for pflicht in ("inhaber", "inhalt") + (("schluessel",) if reg.get("schluessel") else ()):
            if pflicht not in aspekte:
                fehler.append(f"Register {c}: kein geprüfter Beleg für «{pflicht}» — so wird es nicht geladen")
        for code, qid, zitat in reg["standards"]:
            if code not in std_codes:
                fehler.append(f"Register {c}: Standard {code} fehlt in ech_standard")
            elif qid == "projektregel":
                if c != "einwohnerregister" or code not in regel:
                    fehler.append(f"Register {c}: Projektregel gilt nur für die Standards {sorted(regel)} des Einwohnerregisters")
                else:
                    s_rows.append((c, code, "projektregel", None, None))
            elif qid not in texte:
                fehler.append(f"Register {c}: Standard {code} aus Quelle {qid} ohne gültigen Text")
            elif QUELLEN[qid][0] != ECH + code[4:] and code not in zitat:
                fehler.append(f"Register {c}: Standard {code}: der Beleg stammt weder von dessen ech.ch-Seite noch nennt er den Code")
            elif norm(zitat) not in texte[qid]:
                fehler.append(f"Register {c}: Standard-Zitat nicht in {qid}: «{zitat[:80]}»")
            else:
                s_rows.append((c, code, "quelle", qid, zitat))
        r_rows.append((c, reg["name"], reg["inhaber"], reg["ebene"], reg["entitaet"], reg["inhalt"],
                       reg.get("schluessel"), reg.get("stelle_sh"), reg.get("bemerkung")))
    # one link per (register, standard): a project rule and a quote may both exist —
    # the quote wins (it is the stronger evidence)
    best = {}
    for row in s_rows:
        k = (row[0], row[1])
        if k not in best or row[2] == "quelle":
            best[k] = row
    return {"register_quelle": sorted(q_rows), "register": sorted(r_rows, key=lambda r: r[0]),
            "register_beleg": sorted(set(b_rows)), "register_standard": sorted(best.values(), key=lambda r: (r[0], r[1]))}, fehler


SPALTEN = {
    "register_quelle": ("id", "url", "art", "titel", "datei", "sha256", "abgerufen"),
    "register": ("code", "name", "inhaber", "ebene", "entitaet", "inhalt", "schluessel", "stelle_sh", "bemerkung"),
    "register_beleg": ("register", "aspekt", "quelle", "zitat"),
    "register_standard": ("register", "standard", "art", "quelle", "zitat"),
}


def ddl(namen):
    """The CREATE statements of the named tables (and their indices), read from
    schema.sql, so the database and the documented schema can never disagree.
    Statements are split with sqlite3.complete_statement, so a «;» inside a
    comment does not cut one."""
    import sqlite3
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        text = fh.read()
    stmts, buf = [], ""
    for line in text.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            stmts.append(buf.strip())
            buf = ""
    out = []
    for stmt in stmts:
        body = "\n".join(ln for ln in stmt.splitlines() if not ln.lstrip().startswith("--"))
        m = re.search(r"CREATE (?:TABLE|INDEX|UNIQUE INDEX) IF NOT EXISTS (\w+)(?:\s+ON\s+(\w+))?", body)
        if m and (m.group(1) in namen or (m.group(2) and m.group(2) in namen)):
            out.append(body[m.start():])
    missing = [n for n in namen if not any(re.match(rf"CREATE TABLE IF NOT EXISTS {n}\b", s) for s in out)]
    if missing:
        sys.exit(f"ABBRUCH: schema.sql ({SCHEMA_PATH}) beschreibt die Tabellen {missing} nicht — erst den "
                 "Register-Block in schema.sql übernehmen.")
    return out


def aktuell(conn, tabelle):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [tabelle]).fetchone():
        return None
    cols = ", ".join(SPALTEN[tabelle])
    return sorted(tuple(r) for r in conn.execute(f"SELECT {cols} FROM {tabelle}"))


def schreiben(conn, rows):
    """Synchronise the four tables with the new rows. register and register_quelle are
    updated in place (upsert, then delete what is gone), so the mapping of
    register_map.py that points at them survives a catalogue run; only rows of a
    register or a source that left the catalogue go with it."""
    for stmt in ddl(TABELLEN):
        conn.execute(stmt)
    neu_q = {r[0] for r in rows["register_quelle"]}
    neu_r = {r[0] for r in rows["register"]}
    for t in ("register_standard", "register_beleg"):
        conn.execute(f"DELETE FROM {t}")
    weg_q = [r[0] for r in conn.execute("SELECT id FROM register_quelle") if r[0] not in neu_q]
    for t in ("register_angabe", "register_dokument", "register_zugriff"):
        if weg_q and conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [t]).fetchone():
            n = conn.execute(f"DELETE FROM {t} WHERE quelle IN ({','.join('?' * len(weg_q))})", weg_q).rowcount
            if n:
                print(f"  {pl(n, 'Zeile', 'Zeilen')} in {t} stützte(n) sich auf entfernte Quellen — register_map.py neu laden")
    for t, key, neu in (("register_quelle", "id", neu_q), ("register", "code", neu_r)):
        cols = SPALTEN[t]
        upd = ", ".join(f"{c}=excluded.{c}" for c in cols if c != key)
        conn.executemany(f"INSERT INTO {t}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))}) "
                         f"ON CONFLICT({key}) DO UPDATE SET {upd}", rows[t])
    for code in [r[0] for r in conn.execute("SELECT code FROM register")]:
        if code not in neu_r:
            conn.execute("DELETE FROM register WHERE code=?", [code])     # its mapping rows cascade
    for code in weg_q:
        conn.execute("DELETE FROM register_quelle WHERE id=?", [code])
    for t in ("register_beleg", "register_standard"):
        cols = SPALTEN[t]
        conn.executemany(f"INSERT INTO {t}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})", rows[t])


def main():
    qdir = quellen_dir()
    if "--abrufen" in sys.argv:
        sys.exit(1 if abrufen(qdir) else 0)
    conn = connect(DB_PATH)
    rows, fehler = zeilen(qdir, conn)
    print(f"Register-Katalog: {len(rows['register'])} Register, {len(rows['register_beleg'])} Belege, "
          f"{len(rows['register_standard'])} Standard-Verknüpfungen, {len(rows['register_quelle'])} Quellen")
    if fehler:
        print(f"ABGELEHNT ({len(fehler)}):")
        for f in fehler:
            print("  -", f)
        sys.exit(1)
    if "--pruefen" in sys.argv:
        print("Gate bestanden (nichts geschrieben).")
        return
    if all(aktuell(conn, t) == sorted(tuple(r) for r in rows[t]) for t in TABELLEN):
        conn.close()
        print("unverändert — die Databank hält diesen Katalog bereits (nichts geschrieben).")
        return
    conn.close()
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    schreiben(c, rows)
    c.commit()
    from validate_db import validate
    errs = validate(c)
    try:
        import register_map
        errs += register_map.pruefen(c)
    except ImportError:
        pass
    c.close()
    if errs:
        os.remove(st)
        print(f"ABBRUCH — Validierung ({len(errs)}):")
        for e in errs[:30]:
            print("  -", e)
        sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"geladen: {DB_PATH}")


if __name__ == "__main__":
    main()
