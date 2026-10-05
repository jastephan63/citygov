#!/usr/bin/env python3
"""Parteien und Rollen: whose Angabe each data point of a Formular is.

A Formular asks about several parties: the person who submits it, a spouse,
children, a representative, an employer, a Betrieb, a building or a vehicle.
Once-only needs to know which Name is the applicant's and which the spouse's;
the per-field `subjekt` (natural person / organisation / ...) cannot say that.
This module adds the finer layer:

  partei_rolle       the controlled role list (German label, entity type,
                     explanation, and how each entry is grounded in the
                     databank's own words), status «vorschlag» until the
                     canton confirms it
  formular_partei    the parties of each Formular (role, entity type, how the
                     Formular names it, evidence quote, stage)
  datenpunkt_partei  every data point (Teilfeld, or Datenfeld without parts)
                     assigned to exactly one party of its Formular, or
                     «unklar» with a reason — never a guess
  partei_urteil      the judged stage B2 per Formular (loaded through proof
                     gates), applied over the deterministic stage B1

Stage B1 (deterministic, this module, standard library only) settles what
existing signals settle without judgement, in this order of precedence:

  rolle_begriff     the naming layer read the label as naming a role
                    (begriff_label klasse 'rolle'); the free-text role is
                    mapped to the list with the same vocabulary as the labels,
                    and label and role must agree
  wort_bezeichnung  the unit's own label names a party («Geburtsdatum des
                    Kindes», «Zivilstand Ehepartner/in»)
  wort_abschnitt    the composite field around a Teilfeld names the party
                    («Personalien GesuchstellerIn › Name»)
  subjekt           data_field.subjekt 'behoerde' (judged per field) names the
                    party Behörde/Amt (identity, address and contact data only)
  definition        a yes/no field that names only a role or a thing («Grundeigentum»,
                    «Fahrzeug») belongs to the applicant when its definition names the
                    antragstellende/gesuchstellende Person («Angabe, ob die
                    antragstellende Person ein Fahrzeug besitzt»)

What a party may claim (the precision rules, tuned on the full label list and
checked by hand against the Formular text):
  * a person concerned by the matter (Gesuchsteller/in, Ehepartner/in, Kind,
    Elternteil …) owns every Angabe its own label names it in, and every
    natural person (and the applicant, and a named third person) owns every
    Teilfeld of its own block — the spouse's income, the child's Kindart;
  * every other party (Arbeitgeber, Betrieb, Versicherung, Behörde,
    Vertretung, Fachperson, Vertragspartei …) owns only its identity, address,
    contact data and signature — a salary in the employer's block is the
    employee's, an «Abrechnungsnummer» at the Ausgleichskasse is the client's;
  * a Gegenstand owns only what identifies or describes it (number, type,
    area, location), never its costs, counts or the requests about it;
  * an organisation word inside a natural person's block describes that person
    («Erwerbsangaben EhepartnerIn › Arbeitgeber» is the spouse's employer, as in
    eCH-0021 jobData).

Conservative throughout: two roles in one label, signals that disagree, a
person named only indirectly («bei wem», «… oder ihrer Vertretung»), a
statistic, an account or a count, a «Personalien» block without any role word
(it can belong to the applicant or to a representative), a yes/no option that
names only a role or a thing (a status or purpose the applicant ticks: «Schüler(in)»,
«Pflegekind»), a word whose role depends on the procedure («Gläubiger»: the
petitioner of a creditor's Begehren, the other side of a debtor's Gesuch) and an
entity type that contradicts the Angabe or the field's judged subjekt all stay
«unklar» with the reason. Gender forms («Vertreter/-in», «des/der») and «Name oder
Firma» (one party that may be a person or a firm) are read as one party. Parties are keyed by role, type (the Pächter is not the
Verpächter), qualifier (bisherig/neu, anderer), number, the person they belong
to («Arbeitgeber/in, zu: Ehepartner/in») and — for organisations and things
named outside a block of their own — the section. When unsure, B1 splits a
party in two; it never merges two. Stage B2 merges what is one real party.

The Lebenslagen key (export_json.datum_key) uses party words to keep data of
different people apart; LEBENSLAGEN_WOERTER below records how each of its
words maps to this list (or why it is too broad to settle a party alone).

The entity type of a party follows from the subjekt of its own Angaben (name,
person, organisation, address, contact data) — not from an attribute in its block
(«Wo Beiträge bezahlt GesuchstellerIn › Arbeitgeber» describes the applicant, but its
field may be judged «gemischt»).

Subjekt stays consistent: for every assigned point whose field carries a
subjekt, the party's entity type equals it — or the party is «gemischt»
(Person oder Organisation) and the field is natural person, organisation or
gemischt. A point that would break this stays «unklar» (grund «entitaet»):
the subjekt is then corrected through its own second review, never here.
The party layer is the finer one; subjekt stays the per-field verdict the
once-only mark reads today.

The gate pruefen(conn) is for validate_db.py; a data point without a row, a
row whose label changed since the derivation, and a party whose points another
loader removed (load_data_fields.py replaces a Formular's fields, the cascade
takes their rows along) are «noch nicht abgeleitet» and not an error there, and
the build re-derives the layer right after init_register.py. The loaders here
check completeness themselves (vollstaendig).

Commands (every one honours CITYGOV_DB / CITYGOV_SCHEMA):

    python3 scripts/rollen.py ableiten           stage B1 + apply loaded B2 verdicts
                                                 (staging -> validate -> swap; a run
                                                 that changes nothing says so)
    python3 scripts/rollen.py bericht [--json F] coverage per rule, per Formular, the
                                                 ambiguous register points (read-only)
    python3 scripts/rollen.py stichprobe [N] [SEED]   random settled assignments to
                                                 check against the Formular text
    python3 scripts/rollen.py vorbereiten DIR [ID …|--pilot N]  B2 input: one in_<id>.json
                                                 per Formular; --pilot = the stratified
                                                 sample of N (default 30) (read-only)
    python3 scripts/rollen.py laden DIR          B2 loader: out_<id>.json through the
                                                 proof gates (needs pypdf for PDF
                                                 text: /usr/local/bin/python3)
    python3 scripts/rollen.py pruefen            the validate_db gate plus completeness (every
                                                 data point exactly once), standalone
"""
import glob
import hashlib
import json
import os
import random
import re
import shutil
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, ROOT, connect, norm_ascii, norm_label     # noqa: E402

TABELLEN = ("partei_rolle", "formular_partei", "datenpunkt_partei", "partei_urteil")

# ---------------------------------------------------------------------------
# DDL — identical to the block in schema.sql (validate_db compares the columns)
# ---------------------------------------------------------------------------
DDL = """
CREATE TABLE IF NOT EXISTS partei_rolle (          -- the controlled role list («Vorschlag» until the canton confirms it)
    code       TEXT PRIMARY KEY,                   -- stable key, e.g. 'gesuchsteller'
    label      TEXT NOT NULL UNIQUE,               -- German label shown to readers
    entitaet   TEXT NOT NULL CHECK (entitaet IN ('natuerliche_person','organisation','sache','behoerde','offen')),
                                                   -- offen = person or organisation, the Formular decides
    erklaerung TEXT NOT NULL,
    grundlage  TEXT NOT NULL,                      -- JSON: role strings, party words and labels that ground it
    ord        INTEGER NOT NULL,
    status     TEXT NOT NULL DEFAULT 'vorschlag' CHECK (status IN ('vorschlag','bestaetigt')));

CREATE TABLE IF NOT EXISTS formular_partei (       -- the parties a Formular asks about
    form_id     INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    partei_nr   INTEGER NOT NULL,                  -- 1..n in the order the Formular first asks about them
    rolle       TEXT NOT NULL REFERENCES partei_rolle(code),
    entitaet    TEXT NOT NULL CHECK (entitaet IN ('natuerliche_person','organisation','sache','behoerde','gemischt','offen')),
    bezeichnung TEXT NOT NULL,                     -- how the Formular names it («Kind 2», «anderer Elternteil»)
    mehrere     INTEGER NOT NULL DEFAULT 0,        -- 1 = a list of several (Kinder, Gesellschafter/innen)
    beleg       TEXT NOT NULL,                     -- evidence: label/section text (B1) or Formular quote (B2)
    herkunft    TEXT NOT NULL CHECK (herkunft IN ('regel','urteil')),
    PRIMARY KEY (form_id, partei_nr));

CREATE TABLE IF NOT EXISTS datenpunkt_partei (     -- every data point -> exactly one party, or «unklar»
    data_field_id INTEGER NOT NULL REFERENCES data_field(id) ON DELETE CASCADE,
    teil          TEXT NOT NULL DEFAULT '',        -- norm_ascii(Teilfeld name); '' = Datenfeld without parts
    form_id       INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    teil_name     TEXT NOT NULL,                   -- the label when assigned (a changed label = stale row)
    status        TEXT NOT NULL CHECK (status IN ('zugeordnet','unklar')),
    partei_nr     INTEGER,                         -- NULL exactly when status = 'unklar'
    regel         TEXT,                            -- B1 rule (rolle_begriff | wort_bezeichnung | wort_abschnitt | subjekt | definition)
    grund_code    TEXT,                            -- why unklar (UNKLAR_GRUENDE)
    grund         TEXT NOT NULL,                   -- the evidence (zugeordnet) or the reason (unklar), German
    herkunft      TEXT NOT NULL CHECK (herkunft IN ('regel','urteil')),
    regel_rolle   TEXT,                            -- what stage B1 derived, kept when B2 decides (calibration)
    PRIMARY KEY (data_field_id, teil),
    FOREIGN KEY (form_id, partei_nr) REFERENCES formular_partei(form_id, partei_nr));
CREATE INDEX IF NOT EXISTS ix_datenpunkt_partei_form ON datenpunkt_partei(form_id);

CREATE TABLE IF NOT EXISTS partei_urteil (         -- stage B2: the judged parties of one Formular (proof-gated)
    form_id     INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    file_hash   TEXT,                              -- form.file_hash the verdict was made on (NULL for eFormulare)
    parteien    TEXT NOT NULL,                     -- JSON array: nr, rolle, entitaet, bezeichnung, mehrere, beleg
    punkte      TEXT NOT NULL,                     -- JSON array: key, partei | unklar, beleg
    quelle      TEXT NOT NULL,                     -- file the verdict was loaded from
    geladen     TEXT NOT NULL);                    -- load date (YYYY-MM-DD)
"""

# ---------------------------------------------------------------------------
# The controlled role list. `spec` = in the owner's starting list (2026-10-04);
# the others were added because the databank's own labels and role strings
# name them often and no listed role fits (grounding in partei_rolle.grundlage).
# ---------------------------------------------------------------------------
ROLLEN = [
    ("gesuchsteller", "Gesuchsteller/in", "offen", True,
     "Die Person oder Organisation, die das Formular in eigenem Namen einreicht oder in deren Namen es "
     "eingereicht wird (gesuchstellende, antragstellende, meldende, bestellende Person, Absender/in, klagende "
     "Partei, Vollmachtgeber/in einer Vollmacht)."),
    ("ehepartner", "Ehepartner/in bzw. eingetragene/r Partner/in", "natuerliche_person", True,
     "Die Ehegattin, der Ehegatte, die eingetragene Partnerin oder der eingetragene Partner einer Partei "
     "(auch Lebenspartner/in, wo das Formular sie gleich behandelt)."),
    ("kind", "Kind", "natuerliche_person", True,
     "Ein Kind, nach dem das Formular fragt, auch ein Pflege-, Stief- oder minderjähriges Kind. Nummeriert das "
     "Formular die Kinder, ist jedes Kind eine eigene Partei; eine Liste von Kindern ist eine Partei «mehrere»."),
    ("elternteil", "Elternteil", "natuerliche_person", False,
     "Vater, Mutter, anderer Elternteil, Eltern oder Pflegeeltern."),
    ("angehoerige", "weitere Angehörige", "natuerliche_person", False,
     "Weitere Familienangehörige: Geschwister, Enkel, Grosseltern, Familienmitglieder."),
    ("haushalt", "weitere Person im Haushalt", "natuerliche_person", True,
     "Eine Person, die im selben Haushalt lebt, ohne als Ehepartner/in oder Kind genannt zu sein (Mitbewohner/in)."),
    ("vertretung", "Vertreter/in (bevollmächtigt)", "offen", True,
     "Wer aufgrund einer Vollmacht für eine andere Partei handelt: bevollmächtigte Person, Vertreter/in, "
     "Prozessvertretung, Zustellungsbevollmächtigte."),
    ("gesetzliche_vertretung", "gesetzliche Vertretung", "natuerliche_person", True,
     "Wer von Gesetzes wegen für eine Person handelt: Beistand, Vormund, erziehungs- oder sorgeberechtigte Person."),
    ("arbeitgeber", "Arbeitgeber/in", "offen", True,
     "Die Arbeitgeberin oder der Arbeitgeber einer Partei, eine Person oder eine Firma."),
    ("arbeitnehmer", "Arbeitnehmer/in", "natuerliche_person", True,
     "Eine angestellte Person: Arbeitnehmer/in, Mitarbeitende, Beschäftigte, Angestellte."),
    ("betrieb", "Betrieb/Unternehmen", "organisation", True,
     "Ein Betrieb, ein Unternehmen oder eine Organisation, nach dem bzw. der das Formular als solchem fragt: "
     "Firma, Praxis, Institution, Verein, Hauptsitz, Zweigniederlassung — auch wenn er bzw. sie selbst einreicht."),
    ("organ", "Organ oder verantwortliche Person", "natuerliche_person", False,
     "Eine Person, die für einen Betrieb handelt oder verantwortlich ist: Geschäftsführung, Verwaltungsrat, "
     "Gesellschafter/in, Zeichnungsberechtigte, fachliche Leitung, Stellvertretung, Liquidator/in, Inhaber/in."),
    ("kontaktperson", "Kontaktperson", "natuerliche_person", False,
     "Eine Person, die für Rückfragen genannt wird: Kontakt- oder Ansprechperson, zuständige Person, Sachbearbeiter/in."),
    ("fachperson", "beigezogene Fachperson", "offen", False,
     "Eine Fachperson oder Fachfirma, die am Verfahren mitwirkt oder etwas bestätigt: Ärztin/Arzt, "
     "Projektverfasser/in, Planer/in, Bauleitung, Revisionsstelle, Gutachter/in, ausführende Firma."),
    ("bauherrschaft", "Bauherrschaft", "offen", True,
     "Die Bauherrin oder der Bauherr eines Bauvorhabens, eine Person oder eine Organisation."),
    ("grundeigentuemer", "Grundeigentümer/in", "offen", True,
     "Eigentümer/in eines Grundstücks, einer Liegenschaft oder eines Gebäudes."),
    ("vertragspartei", "Vertragspartei", "offen", False,
     "Eine Partei eines Vertrags, um den es im Formular geht: Käufer/in, Verkäufer/in, Veräusserer/in, "
     "Pächter/in, Verpächter/in, Mieter/in, Vermieter/in, Urkundspartei."),
    ("gegenpartei", "Gegenpartei", "offen", False,
     "Die Partei, gegen die sich eine Klage, ein Gesuch oder eine Beschwerde richtet: beklagte Partei, "
     "Beschwerdegegner/in."),
    ("halter", "Halter/in (Fahrzeug)", "offen", True,
     "Halter/in eines Fahrzeugs, Anhängers oder Schiffs."),
    ("tierhalter", "Tierhalter/in", "offen", True,
     "Halter/in, Eigentümer/in oder Besitzer/in eines Tiers."),
    ("betroffene_person", "betroffene Person", "natuerliche_person", False,
     "Die Person, um die es im Formular geht, wenn das Formular sie nicht als einreichende Person bezeichnet: "
     "versicherte Person, Patient/in, Schüler/in, untersuchte Person, Opfer. Sie kann zugleich die einreichende "
     "Person sein; ob sie es ist, steht je Formular."),
    ("verstorbene", "verstorbene Person", "natuerliche_person", True,
     "Eine verstorbene Person (Erblasser/in)."),
    ("dritte", "weitere beteiligte Person", "offen", False,
     "Eine weitere Person, die das Formular nennt, ohne dass eine andere Rolle passt: Zeugin/Zeuge, "
     "Begleitperson, Drittperson, Erbin/Erbe, Täter/in, Finder/in."),
    ("versicherung", "Versicherung oder Kasse", "offen", False,
     "Eine Versicherung oder Kasse: Ausgleichskasse, IV-Stelle, Krankenversicherer, Unfallversicherer, "
     "Vorsorgeeinrichtung, Arbeitslosenkasse. Ihre Art (Organisation oder Behörde) folgt dem Subjekt des Felds (eine Ausgleichskasse "
     "ist eine öffentliche Stelle)."),
    ("behoerde", "Behörde/Amt", "behoerde", True,
     "Eine Behörde, ein Amt, eine Gemeinde oder eine andere öffentliche Stelle, nach der das Formular fragt."),
    ("gegenstand", "Gegenstand", "sache", True,
     "Eine Sache, nach der das Formular fragt: Grundstück, Gebäude oder Anlage, Fahrzeug, Tier, Waffe, Dokument. "
     "Die Art steht in der Bezeichnung der Partei."),
]
ROLLE = {r[0]: {"code": r[0], "label": r[1], "entitaet": r[2], "spec": r[3], "erklaerung": r[4], "ord": i + 1}
         for i, r in enumerate(ROLLEN)}
GEGENSTAND_ARTEN = ("Grundstück", "Gebäude oder Anlage", "Fahrzeug", "Tier", "Waffe", "Dokument")
ENT_ROLLE = ("natuerliche_person", "organisation", "sache", "behoerde", "offen")
ENT_PARTEI = ("natuerliche_person", "organisation", "sache", "behoerde", "gemischt", "offen")
assert all(r[2] in ENT_ROLLE for r in ROLLEN) and len(ROLLE) == len(ROLLEN), "role list: entity type or duplicate code"

# What a party may claim:
#  * own label (or the naming layer's role) of a person concerned by the matter —
#    everything («Zivilstand Ehepartner/in», «Einkommen (Antragstellerin)»)
#  * a block of a natural person (or of the applicant, or a third person) —
#    everything inside it («Kind 1 › Kindart», «Liquidator/in 1 › Zeichnungsberechtigung»)
#  * every other party (employer, Betrieb, insurer, authority, representative,
#    expert, contract party …) — only its identity, address, contact data and
#    signature, or a label that is nothing but the party («Firma»)
#  * a Gegenstand — only what identifies or describes it (objekt_angabe)
EIGEN_ALLES = {"gesuchsteller", "ehepartner", "kind", "elternteil", "angehoerige", "haushalt", "verstorbene",
               "betroffene_person"}
BLOCK_ALLES = {c for c, v in ROLLE.items() if v["entitaet"] == "natuerliche_person"} | {"gesuchsteller", "dritte"}
# a person's relatives and associates named in that person's block get a «zu:»
FAMILIE = {"ehepartner", "kind", "elternteil", "angehoerige", "haushalt", "verstorbene", "betroffene_person"}
# roles that, named inside a natural person's block, describe that person
# («Erwerbsangaben EhepartnerIn › Arbeitgeber» is the spouse's employer, eCH-0021 jobData)
ATTRIBUT_ROLLEN = {"arbeitgeber", "versicherung", "betrieb", "behoerde"}

REGELN = ("rolle_begriff", "wort_bezeichnung", "wort_abschnitt", "subjekt", "definition")
REGEL_LABEL = {
    "rolle_begriff": "Die Prüfung der Bezeichnungen (Begriffe) liest die Bezeichnung als Rolle",
    "wort_bezeichnung": "Die Bezeichnung nennt die Partei",
    "wort_abschnitt": "Der Abschnitt nennt die Partei",
    "subjekt": "Das Feld ist als Angabe einer Behörde beurteilt (Subjekt)",
    "definition": "Die Definition der Ja/Nein-Angabe nennt die einreichende Person",
}
REGEL_TEXT = {k: v + ": «{w}»" for k, v in REGEL_LABEL.items()}
# the code «urteil»: the reason is the one written per point when the Formular text was judged
URTEIL_LABEL = "aus dem Formulartext beurteilt — der Grund steht je Datenpunkt"
UNKLAR_GRUENDE = {
    "kein_hinweis": "Weder Bezeichnung noch Abschnitt noch Rolle nennen eine Partei",
    "personalien_ohne_rolle": "Personenangabe ohne Rollenwort: sie kann der einreichenden Person oder einer "
                              "Vertretung gehören",
    "mehrere_rollen": "Die Bezeichnung nennt zwei Rollen",
    "mehrere_parteien": "Die Angabe betrifft mehrere Parteien zugleich",
    "widerspruch": "Die Hinweise nennen verschiedene Parteien",
    "andere_person": "Die Bezeichnung verweist auf eine Person, die sie nicht als Rolle nennt",
    "sache_organisation": "Angabe zu einer Sache oder Organisation, die das Formular nicht als Partei führt",
    "auswahl": "Ja/Nein-Angabe, die nur eine Rolle oder Sache nennt (ein Status oder Zweck zum Ankreuzen): "
               "wessen Angabe sie ist, sagt das Wort allein nicht",
    "nicht_parteiangabe": "Die Angabe steht im Abschnitt einer Partei, ist aber keine Personen-, Adress- oder "
                          "Kontaktangabe dieser Partei",
    "entitaet": "Die Rolle passt nicht zur Art der Angabe (Person, Organisation, Sache)",
    "subjekt": "Die Rolle widerspricht dem beurteilten Subjekt des Felds",
    "kontext": "Das Wort braucht einen Bezug, den das Formular nicht nennt (z. B. Gläubiger/in: einreichende "
               "Partei eines Begehrens oder Gegenpartei)",
    "sache_ohne_gegenstand": "Angabe zu einer Sache oder einem Ort ohne Wort für einen Gegenstand",
    "arbeitsort": "Adress- oder Kontaktangabe im Abschnitt zu Erwerb oder Ausbildung: sie kann der Person oder "
                  "ihrem Arbeitgeber bzw. ihrer Schule gehören",
    "urteil": "{w}",            # the reason written per point in the judgement from the Formular text
}

# ---------------------------------------------------------------------------
# Vocabulary. Matched on a folded text (lower case, sharp s -> ss, ä/ö/ü -> ae/oe/ue,
# so «Equideneigentuemer» and «Eigentümer» meet). Order matters: a specific
# compound masks the shorter words inside it («Fahrzeughalter» before
# «Fahrzeug», «gesetzliche Vertretung» before «Vertretung»). An entry's third
# element is the instance label (None = the role label), the fourth the kind of
# Gegenstand. Role codes ending in '?' need the Formular's context (CONTEXT).
# ---------------------------------------------------------------------------
# «Name oder Firma», «Name, Vorname bzw. genaue Firmenbezeichnung»: ONE party that may be a
# person or a firm (an entity choice), never two roles
NAME_FIRMA = (r"\b(?:vor)?name[n]?(?:\s*(?:,|/|und)\s*(?:vor)?name[n]?)?\s*(?:oder|bzw\.?|/)\s*(?:genaue\s+)?"
              r"firm(?:a|en\s*-?\s*(?:name|bezeichnung))\b|\bfirm(?:a|enname)\s*(?:oder|bzw\.?|/)\s*(?:vor)?name[n]?\b")
WOERTER = [
    # never a party, masked first (statistics, benefits, products, the entity choice of one party)
    (None, NAME_FIRMA),
    (None, r"pflegende\s+angehoerige\w*"),
    (None, r"ehegattenunterhalt\w*|kinderunterhalt\w*|kinderbetreuung\w*|kinderzulage\w*|kinderrente\w*|"
           r"elternbeitr\w*|elterntarif\w*|elternzeit\w*|mutterschaft\w*|vaterschaft\w*|antragstellung|gesuchstellung"),
    (None, r"\bkein(e[rn]?)?\s+(elternteil|kind|ehe\w*|partner\w*)\w*|(nicht|kein\w*)\s+im\s+(gemeinsamen\s+)?haushalt"),
    (None, r"angestellte[rn]?\s+taetigkeit|selbstaendige[rn]?\s+taetigkeit"),
    (None, r"(kinder|kindes|eltern|ehegatten|ehepartner)\s*-\s*(/|und|oder)"),        # «Kinder-/Waisenrente»
    (None, r"arbeitgeber(beitr|anteil|kontroll|bescheinigung)\w*"),
    (None, r"\b(inhaber|inhaberin)\s+(der|des)\s+(vkf|bewilligung)\w*"),
    (None, r"bewilligungsinhaber\w*|konzessions\w*\s*/?\s*-?\s*bewilligungsempfaenger\w*"),
    # an animal holding is a Betrieb or a place, not the animal (TVD-Nr., Standort): never settled by B1
    (None, r"tierhaltung\w*"),
    ("KONTO?", r"konto\s*-?\s*inhaber\w*|inhaber\w*\s+des\s+kontos"),
    ("betroffene_person", r"angehoerige[nr]?\s+(der|des)\s+feuerwehr"),
    ("gesetzliche_vertretung", r"inhaber\w*\s+der\s+elterlichen\s+sorge"),
    # holders and owners: the compound names the thing
    ("tierhalter", r"(tier|hunde|bienen|equiden|pferde)\s*-?\s*(halter|besitzer|eigentuemer)\w*"),
    ("tierhalter", r"\b(halter|besitzer|eigentuemer)\w*\s+(des|der)\s+(gebissenen\s+)?(tier|hund)\w*"),
    ("halter", r"fahrzeug\s*-?\s*(halter|eigentuemer)\w*"),
    ("halter", r"\bhalter\w*\s+(des|der)\s+(fahrzeug|motorfahrzeug|schiff)\w*"),
    ("HALTER?", r"\bhalter(in|innen|s)?\b"),
    ("organ", r"(geschaefts|betriebs|praxis|firmen)\s*-?\s*inhaber\w*"),
    ("betroffene_person", r"pass\s*-?\s*inhaber\w*"),
    ("grundeigentuemer", r"(grund|grundstueck|grundstueck?s|gebaeude|liegenschafts|stockwerk|werk|mit)\s*-?\s*eigentuemer\w*"),
    ("grundeigentuemer", r"\beigentuemer\w*\s+(der|des)\s+(liegenschaft|grundstueck|gebaeude|parzelle)\w*"),
    ("EIGENTUEMER?", r"\beigentuemer(in|innen|schaft|s)?\b"),
    ("bauherrschaft", r"\bbauherr\w*"),
    # representation
    ("gesetzliche_vertretung", r"gesetzliche[rn]?\s+vertret\w*"),
    ("gesetzliche_vertretung", r"\bbeistand\b|\bbeistaendin\w*|\bvormund\w*|erziehungsberechtigt\w*|sorgeberechtigt\w*"),
    ("behoerde", r"vertretung\s+(der\s+)?feuerwehr|schweizer(ische)?\s+vertretung|\bbotschaft\b|\bkonsulat\w*"),
    ("organ", r"stell\s*-?\s*vertret\w*|vereins\s*-?\s*vertret\w*"),
    ("vertretung", r"\bvertret(er|erin|erinnen|ers|ung|ende|enden)\b\w*|bevollmaechtigt\w*|vollmacht\s*-?\s*nehmer\w*|"
                   r"zustell\w*\s*-?\s*bevollmaechtigt\w*|prozess\s*-?\s*vertret\w*|\bvertreter\w*|\w+vertreter\w*"),
    # the person who submits, and the other side
    ("gesuchsteller", r"gesuch\s*-?\s*stell(er|erin|erinnen|ers|ende[nrs]?)\b\w*|"
                      r"antrag\s*s?\s*-?\s*stell(er|erin|erinnen|ers|ende[nrs]?)\b\w*|\bbewerber\w*|beschwerde\s*-?\s*fuehr\w*|"
                      r"\w*meldende[nr]?\b|\bbesteller\w*|(?<!zu )\bbestellende[nr]?\b|\banmeldende[nr]?\b|"
                      r"\beinreichende[nr]?\b|\babsender\w*|\beinsender\w*|klagende[nr]?\s+partei|"
                      r"vollmacht\s*-?\s*geber\w*"),
    ("gegenpartei", r"beklagte[nr]?\s+partei|beschwerde\s*-?\s*gegner\w*"),
    # the creditor submits a creditor's Begehren and is the other side of a debtor's Gesuch
    ("GLAEUBIGER?", r"glaeubiger\w*"),
    ("verstorbene", r"verstorben\w*|erblasser\w*"),
    # family and household
    ("MEHRERE", r"\bbeide[rn]?\s+(ehe|eltern|partner)\w*|\bder\s+ehegatten\b|\behegatten\s+bzw|\behepaar\w*|"
                r"\behegatten\s+(seit|und)\b|\bder\s+ehepartner\b"),
    ("ehepartner", r"\behe\s*-?\s*(gatt|partner|frau|mann)\w*|lebens\s*-?\s*partner(in|innen|s|/in|/-in)?\b|eingetragene[rn]?\s+partner(in|innen|s|/in|/-in)?\b|"
                   r"\bpartner\s*/\s*-?\s*partnerin\b|\bpartner\s*/\s*-?\s*in\b|\bpartnerin\b|\bpartner\s*/\s*innen\b"),
    ("kind", r"pflege\s*-?\s*kind(es|er|ern|s)?\b(?!\s*-)|stief\s*-?\s*kind(es|er|ern|s)?\b(?!\s*-)|"
             r"\bkind(es|er|ern|s)?\b(?!\s*-)|\btochter\b|\bsohn(es)?\b|"
             r"\bsoehne\b|minderjaehrig\w*|\bwaise[n]?\b|\bjugendliche[rn]?\b"),
    ("elternteil", r"elternteil\w*|\beltern\b(?!\s*-)|pflege\s*-?\s*(vater|mutter|eltern)\b|\bvater\b(?!\s*-)|"
                   r"\bvaters\b|\bmutter\b(?!\s*-)"),
    ("angehoerige", r"geschwister\w*|\burenkel\w*|\benkel\w*|grosseltern|familienmitglied\w*|\bangehoerige[nr]?\b"),
    ("haushalt", r"mitbewohner\w*|personen\s+im\s+(gemeinsam(en)?\s+(gefuehrten\s+)?)?haushalt"),
    # employment and the organisation's people
    ("arbeitgeber", r"arbeit\s*-?\s*geb(er|erin|erinnen|ende|enden|ers|erdaten|erangaben)\w*"),
    ("arbeitnehmer", r"arbeit\s*-?\s*nehm\w*|\bmitarbeit(er|erin|erinnen|ende|enden)\b\w*|\bbeschaeftigte[nr]?\b|"
                     r"\w*angestellte[rn]?\b|\bangestellte\s*/\s*-?\s*r\b"),
    ("organ", r"geschaefts\s*-?\s*fuehr\w*|geschaefts\s*-?\s*leitung\w*|verwaltungsrat\w*|zeichnungsberecht\w*|"
              r"gesellschafter\w*|teilhaber\w*|liquidator\w*|\bgruender\w*|fachliche[nr]?\s+leitung|"
              r"institutionsleitung|betriebsleiter\w*|eingetragene\s+personen|ausgeschiedene\s+personen|"
              r"verantwortliche[rn]?\s+person\w*|\w+verantwortliche[rn]?\b"),
    ("kontaktperson", r"kontakt\s*-?\s*person\w*|ansprech\s*-?\s*(person|partner)\w*|zustaendige[rn]?\s+person|"
                      r"sachbearbeit\w*|auskunftsperson\w*"),
    ("fachperson", r"projekt\s*-?\s*verfass\w*|\bplaner\w*|bauleitung|architekt\w*|ingenieur\w*|geologe\w*|"
                   r"fachberater\w*|energiespezialist\w*|\barzt\b|\barztes\b|aerztin\w*|\baerzte\b|hausarzt\w*|"
                   r"tierarzt\w*|heimarzt\w*|gutachter\w*|revisionsstelle\w*|fahrlehrer\w*|lehrperson\w*|"
                   r"trainer\w*|probenehmer\w*|pruefende[rn]?\s+person|sachverstaendig\w*|installations\s*firma\w*|"
                   r"installateur\w*|ausfuehrende[rn]?\s+firma|bauunternehm\w*|transportunternehm\w*|fachperson\w*"),
    ("vertragspartei", r"\bkaeufer\w*|kauf\s*partei\w*|verkaeufer\w*|verkauf\s*partei\w*|veraeusser(er|in)\w*|"
                       r"\berwerber\w*|\bpaechter\w*|verpaechter\w*|\bmieter\w*|vermieter\w*|vertrags\s*partei\w*|"
                       r"urkunds\s*partei\w*"),
    ("dritte", r"\bzeuge[n]?\b|\bzeugin\w*|begleit\s*-?\s*person\w*|dritt\s*-?\s*person\w*|dritte[rn]?\s+person|"
               r"drittansprecher\w*|\btaeter\w*|\berbe[n]?\b|\berbin\w*|vermaechtnisnehm\w*|"
               r"\bfinder\w*|nahestehende[rn]?\s+person"),
    ("betroffene_person", r"versicherte[nr]?\s+person|\bpatient(in|innen|en)?\b|\bschueler(in|innen|s)?\b|"
                          r"\bkandidat(in|innen|en)?\b|\babsolvent(in|innen|en)?\b|\bathlet(in|innen|en)?\b|\bschuetze[n]?\b|\bopfer\b|\bopfers\b|untersuchte[nr]?\s+(person|frau|mann)|"
                          r"zu\s+untersuchende[nr]?\s+person|geimpfte[nr]?\s+person|\bklient(in|innen|en)?\b|"
                          r"betroffene[nr]?\s+person|zu\s+bewilligende[nr]?\s+person|zu\s+meldende[nr]?\s+person|"
                          r"\b(kurs)?teilnehmer(in|innen|s)?\b"),
    # organisations and authorities
    ("versicherung", r"ausgleichskasse[n]?\b|familienausgleichskasse[n]?\b|\biv\s*-?\s*stelle\b|krankenkasse[n]?\b|"
                     r"kranken\s*-?\s*versicherer\w*|unfall\s*-?\s*versicherer\w*|unfallversicherung\b|"
                     r"vorsorgeeinrichtung\w*|pensionskasse[n]?\b|arbeitslosenkasse[n]?\b|\bversicherer\w*|"
                     r"bvg\s*-?\s*versicherer\w*|haftpflicht\s*-?\s*versicherer\w*|\bsuva\b|\bzahlstelle[n]?\b|"
                     r"\bversicherung\b|haftpflicht\s*-?\s*versicherung\w*"),
    ("behoerde", r"\bbehoerde\w*|leitbehoerde|\bamt\b|amtsstelle\w*|"
                 r"(betreibungs|steuer|eich|grundbuch|migrations|zivilstands|handelsregister|strassenverkehrs|"
                 r"sozial|gesundheits|landwirtschafts|veterinaer|arbeits|finanz|bau|einwohner)amt(es|s)?\b|"
                 r"gemeinde\s*-?\s*(rat|verwaltung|schreiber|praesident|kanzlei)\w*|"
                 r"zustaendige[sn]?\s+(gemeinde|kanton|steueramt)\w*|anspruchsberechtigte\s+gemeinde|zweckverband\w*|"
                 r"feuerwehr\s*-?\s*kommando\w*|zustaendige[sn]?\s+feuerwehr\w*|\bfoerster\w*|waffenbuero|"
                 r"\bpolizei(posten|korps)?\b|\bgericht(e|s)?\b|\bkesb\b|steuerverwaltung|finanzverwalt\w*|"
                 r"zentralverwalt\w*|finanzreferent\w*|rechnungsfuehrer\w*|koerperschaft\w*|gueterkorporation\w*|"
                 r"\bfeuerwehr\b(?!\s*-)"),
    ("betrieb", r"\bfirma\b|\bfirmen\s*-?\s*(angaben|name|bezeichnung|daten)\w*|\bunternehmen\b|\bunternehmung\b|"
                r"\bbetrieb(s|es)?\b|betriebs\s*-?\s*(angaben|daten|adresse|anschrift)\w*|\bpraxis\b|praxis\s*-?\s*adresse\w*|"
                r"\binstitution\b|\bverein\b|\bgesellschaft\b|traegerschaft\w*|\borganisation\b|hauptsitz\w*|"
                r"zweigniederlassung\w*|\bfiliale\w*|lehrbetrieb\w*|einsatzbetrieb\w*|zweigbetrieb\w*|"
                r"\w+unternehmen\b"),
    # things
    ("gegenstand", r"grundstueck\w*|parzelle\w*|liegenschaft\w*|grundeigentum\b|pacht\s*-?\s*(gegenstand|land|flaeche|objekt)\w*|"
                   r"verpachtete[sn]?\s+(land|flaeche|flaechen|grundstueck|grundstuecke)\b|eigene[sn]?\s+land\b", "Grundstück"),
    ("gegenstand", r"gebaeude\w*|\bbaute[n]?\b|\bobjekt(s|es|e)?\b|objekt\s*-?\s*(angaben|daten|identifikation)\w*|"
                   r"schutzraum\w*|solaranlage\w*|erdsonde\w*|\bsonde[n]?\b|sonde\s*/\s*n|erdkollektor\w*|erdkoerbe\w*|"
                   r"\banlage\b|tankanlage\w*|wohnhaus\w*|\bremise\b|maschinenhalle\w*|\bscheune\b|\bstall\b|"
                   r"gehege\w*", "Gebäude oder Anlage"),
    ("gegenstand", r"\w*fahrzeug\w*|\banhaenger\w*|motorfahrrad\w*|\bschiff(es|s)?\b|kontrollschild\w*|"
                   r"kugelkopfkupplung|hakenkupplung|bolzenkupplung|schlusstraverse|zwischenplatte|herstellerschild\w*", "Fahrzeug"),
    ("gegenstand", r"\btier(e|es|en)?\b|tierbestand\w*|tierart\w*|tiergattung\w*|\bhund(e|es|en)?\b|"
                   r"schweisshund\w*|\bequide[n]?\b|\bpferd\w*|\bbienen\w*|\bkatze[n]?\b|frettchen", "Tier"),
    ("gegenstand", r"\bwaffe[n]?\b|waffenangaben|waffenbestandteil\w*|feuerwaffe\w*", "Waffe"),
]
_WOERTER_RX = [(w[0], re.compile(w[1]), w[2] if len(w) > 2 else None) for w in WOERTER]

# A section that is a statistic, a count or an account names no party: it is the
# Formular's question about a whole group or about money, not one party's Angabe
# («Personalbestand», «Abschreibungstabelle Maschinen inkl. Fahrzeuge»).
STATISTIK = re.compile(r"^\s*(anzahl|total|summe|bestand|personalbestand|gesamtstellenprozente|ausbildungsleistung|"
                       r"lohnsumme|stellenprozente)\b|\bin\s+pensen\b|\bvzae\b|verrechenbare|\bklienten\s+nur\b")
FINANZ = re.compile(r"kosten|abschreibung|anlagewert|buchwert|wertverminderung|\bertrag|ertraege|erloes|aufwand|"
                    r"lagerbestand|budget|ausgaben|einnahmen|bilanz|erfolgsrechnung|umsatz|lohnsumme|naturalbez|"
                    r"privatanteil|klientenanteil|aufgeteilte\s+liegenschaft|liegenschaftsk(ae|au)uf|"
                    r"liegenschaftsverk|mietertrag|unterhaltsbetrag")
# a label that counts or rates (per child, in %, minutes) names no party by its role word
ZAEHLUNG = re.compile(r"\banzahl\b|\bje\s+(kind|person)|\bpro\s+(kind|person)|\bgrundbetrag|\bansatz\b|\bminuten\b|"
                      r"\bstunden\b|\bin\s*%|prozent|\bdavon\b|!\s*$|\d+\s*-\s*\d+\s*jahr|"
                      r"\b(unter|ueber|bis|ab)\s+\d+\s*jahr")
# an employment or education context: an address or contact there may be the
# workplace's or the school's («Erwerbstätigkeit Ehepartner/in › Adresse» is the
# employer's address on the Formular, not the spouse's home)
ERWERB = re.compile(r"erwerb|anstellung|beschaeftigung|taetigkeit|arbeitsverhaeltnis|arbeitsort|arbeitsstelle|"
                    r"arbeitgeb|ausbildungs(staette|ort)|\bschule|studium|lehrbetrieb|einsatz")
# a label that relates two parties («Tierbetreuung identisch mit Gesuchsteller/in»)
BEZIEHUNG = re.compile(r"identisch\s+mit|gleich\s+wie|abweichend\s+vo[nm]|\bfalls\s+abweichend")
# a label that names a person only indirectly
ANDERE_PERSON = re.compile(r"\bbei\s+wem\b|\bmit\s+wem\b|\bvon\s+wem\b|\bbei\s+welcher\s+person\b")
# German markers that make a later word an attribute of the first («Vertreter der klagenden Partei»)
_ATTR_VOR = re.compile(r"(\bdes|\bder|\bdem|\bden|\bvon|\bvom|\bbeim|\bbei|\bfuer|\bzur|\bzum|\bim|\bam|"
                       r"\bgegenueber)\s+(\w+\s+){0,2}$")
# the same, for the FIRST party word: any preposition makes it an attribute of the words before it
_PRAEP_VOR = re.compile(r"(\bdes|\bder|\bdem|\bden|\bvon|\bvom|\bbeim|\bbei|\bfuer|\bzur|\bzum|\bim|\bam|"
                        r"\bgegenueber|\bueber|\bmit|\bdurch|\ban|\bzu|\bgegen)\s+(\w+\s+){0,2}$")
_JOIN = re.compile(r"^\s*(/|,|\boder\b|\bbzw\.?|\bund\b|&|\+)")
# the head before «des/der …» must be a data noun for the genitive to name the party
DATEN_KOPF = {"personalien", "angaben", "adresse", "wohnadresse", "name", "namen", "vorname", "daten", "kontakt",
              "kontaktangaben", "kontaktdaten", "kontoangaben", "erwerbsangaben", "erwerbstaetigkeit",
              "arbeitsverhaeltnis", "wohnsitz", "wohnort", "unterschrift", "einkommen", "beruf", "zivilstand",
              "geburtsdatum", "identitaet", "personendaten", "personaldaten", "lage", "standort", "beschreibung",
              "bezeichnung", "und", "oder", "nr", "nummer", "telefon", "e", "mail", "email", "anschrift",
              "zustimmung", "staatsangehoerigkeit", "nationalitaet", "heimatort", "geschlecht", "ahv", "sozialversicherungsnummer",
              "versichertennummer", "wohnadresse", "aufenthaltsort", "korrespondenzadresse", "postadresse", "titel",
              "nachname", "familienname", "ledigname", "vornamen", "angabe", "detailangaben", "alter", "jahrgang",
              "mitglied", "mitglieder", "funktion", "kontoangaben", "zahlungsverbindung", "erreichbarkeit",
              "personalangaben", "finanzielle", "verhaeltnisse", "wohnsitzadresse", "zustelladresse"}
# words that may stand before «des/der …» besides a data noun: articles, plain adjectives
# of the Angabe and the actions on a register entry («Lediger Name des Ehepartners»,
# «Genaue Adresse des Fahrzeughalters», «Löschung von Zeichnungsberechtigten»)
KOPF_FREI = {"des", "der", "dem", "den", "die", "das", "ein", "eine", "einer", "eines", "einem", "firma", "firmenname",
             "firmenbezeichnung", "loeschung", "eintragung", "neueintragung", "aenderung", "mutation"}
KOPF_ADJ = re.compile(r"(vollstaendig|genau|ledig|amtlich|aktuell|bisherig|frueher|offiziell)\w*")
# a gender ending right after a party word («Vertreter/-in der klagenden Partei») is no join
_GENUS_NACH = re.compile(r"^\s*(?:/\s*-?\s*(?:in|innen|r|n|e)\b|\(\s*(?:in|innen|r|n)\s*\))")
# «Name des Arbeitgebers oder Ihrer Einzelfirma»: the party word or the person's own firm
EIGENE_ALTERNATIVE = re.compile(r"\boder\s+(?:ihre[rnms]?|eigene[rnms]?|seine[rnms]?|meine[rnms]?)\s+(?:\w+\s+)?"
                                r"(?:einzel)?(?:firma|unternehmen|betrieb)\w*")


def kopf_ok(w):
    """May this word stand before the genitive that names the party?"""
    return w in DATEN_KOPF or len(w) <= 2 or w in KOPF_FREI or bool(KOPF_ADJ.fullmatch(w))


CONTEXT = {
    "HALTER?": [("halter", r"fahrzeug|kontrollschild|anhaenger|schiff|motorrad|motorfahrrad|fahrausweis|"
                           r"fuehrerausweis|strassenverkehr|\bverkehrs|immatrikul|zulassung von fahr"),
                ("tierhalter", r"\btier|\bhund|equide|pferd|bienen|katze|vieh|frettchen|nachsuche|\bjagd|\bwild")],
    "EIGENTUEMER?": [("grundeigentuemer", r"grundstueck|liegenschaft|parzelle|gebaeude|\bbau|grundbuch|pacht|"
                                          r"\bland\b|wohnung|stockwerk|boden|grundeigentum"),
                     ("tierhalter", r"\btier|\bhund|equide|pferd|bienen|katze|vieh"),
                     ("halter", r"fahrzeug|anhaenger|schiff")],
    "KONTO?": [],          # an account holder can be anyone: never settled by B1
    # SchKG: the creditor files the Begehren (Arrest, Konkurs, Retention, Fortsetzung,
    # Rechtsöffnung, Forderungseingabe); the debtor's Gesuch names the creditor as the other side
    "GLAEUBIGER?": [("gesuchsteller", r"arrest|konkursbegehren|eroeffnung des konkurses|retention|fortsetzung|"
                                      r"rechtsoeffnung|forderungseingabe|betreibungsbegehren|pfaendungsbegehren|"
                                      r"verwertungsbegehren"),
                    ("gegenpartei", r"nichtbekanntgabe|schuldner\w*\s*(gesuch|antrag)|insolvenzerklaerung")],
}
_ZAHL_VOR = re.compile(r"\b(\d{1,2})(\.\s*|\s+-\s+)$")
_ZAHL_NACH = re.compile(r"^\s*(?:/\s*-?\s*in\s*|\(in\)\s*|person\s+)?(?:nr\.?\s*)?(\d{1,2}|[abc])\b(?!\s*\.\s*\d)")
_QUALI_VOR = re.compile(r"\b(neue[rnms]?|bisherige[rnms]?|fruehere[rnms]?|letzte[rnms]?|andere[rnms]?|weitere[rnms]?|"
                        r"zusaetzliche[rnms]?|leibliche[rnms]?|ueberlebende[rnms]?|aktuelle[rnms]?|"
                        r"vorherige[rnms]?|uebergeordnete[rnms]?|uebernehmende[rnms]?)\s+(\w+\s+)?$")
_QUALI_NACH = re.compile(r"^\s*(?:\(|,|-)?\s*(neu|bisher|alt)\b")
_PLURAL = re.compile(r"(innen|personen|kinder|kindern|eltern|geschwister|enkel|mitglieder|mitarbeitende|"
                     r"beschaeftigte[n]?|zeugen|erben|gesellschafter\b|/en\b|teilhaberinnen|pächter\b)$")


# Within one role, these words name DIFFERENT real parties on one Formular (the
# Pächter is not the Verpächter, the fachliche Leitung not the Geschäftsleitung);
# the first type whose pattern matches the party word becomes part of the party.
TYPEN = {
    "fachperson": [("Projektverfasser/in", r"projekt\s*-?\s*verfass|planer|architekt|ingenieur|bauleitung"),
                   ("Tierärztin/Tierarzt", r"tierarzt|tieraerzt"), ("Ärztin/Arzt", r"arzt|aerzt"),
                   ("Revisionsstelle", r"revisionsstelle"), ("Gutachter/in", r"gutachter|sachverstaendig"),
                   ("Fahrlehrer/in", r"fahrlehrer"), ("Lehrperson", r"lehrperson"), ("Trainer/in", r"trainer"),
                   ("ausführende Firma", r"unternehm|firma|installat"),
                   ("Fachberater/in", r"geolog|fachberater|energiespezialist"),
                   ("prüfende Person", r"probenehmer|pruefende"), ("Fachperson", r"fachperson")],
    "organ": [("Geschäftsführung", r"geschaefts\s*-?\s*(fuehr|leitung)|betriebsleiter|institutionsleitung"),
              ("Verwaltungsrat", r"verwaltungsrat"), ("fachliche Leitung", r"fachliche"),
              ("Stellvertretung", r"stell\s*-?\s*vertret"), ("Gesellschafter/in", r"gesellschafter|teilhaber"),
              ("Liquidator/in", r"liquidator"), ("Gründer/in", r"gruender"),
              ("ausgeschiedene Personen", r"ausgeschiedene"), ("eingetragene Personen", r"eingetragene\s+personen"),
              ("Zeichnungsberechtigte", r"zeichnungsberecht"),
              ("Inhaber/in", r"inhaber"), ("Vereinsvertretung", r"vereins"), ("verantwortliche Person", r"verantwortlich")],
    "vertragspartei": [("Verkäufer/in", r"verkaeufer|verkaufpartei|veraeusser"), ("Käufer/in", r"kaeufer|kaufpartei|erwerber"),
                       ("Verpächter/in", r"verpaechter"), ("Pächter/in", r"paechter"), ("Vermieter/in", r"vermieter"),
                       ("Mieter/in", r"mieter"), ("Urkundspartei", r"urkunds"), ("Vertragspartei", r"vertrags")],
    "versicherung": [("Ausgleichskasse", r"ausgleichskasse"), ("IV-Stelle", r"iv\s*-?\s*stelle"),
                     ("Krankenversicherer", r"kranken"), ("Unfallversicherer", r"unfall|suva"),
                     ("Vorsorgeeinrichtung", r"vorsorge|pensionskasse|bvg"), ("Arbeitslosenkasse", r"arbeitslosen"),
                     ("Haftpflichtversicherer", r"haftpflicht"), ("Zahlstelle", r"zahlstelle"), ("Versicherung", r"versicher")],
    "behoerde": [("Gemeinde", r"gemeinde|zweckverband|gueterkorporation|koerperschaft"),
                 ("Betreibungsamt", r"betreibungsamt"), ("Steuerbehörde", r"steuer|finanzamt|finanzverwalt"),
                 ("Feuerwehr", r"feuerwehr"), ("Gericht", r"gericht"), ("Polizei", r"polizei"), ("KESB", r"kesb"),
                 ("Eichamt", r"eichamt"), ("Vertretung im Ausland", r"botschaft|konsulat|schweizer\w*\s+vertretung"),
                 ("Förster/in", r"foerster"), ("Kanton", r"kanton|amtsstelle|leitbehoerde|waffenbuero|amt\b")],
    "tierhalter": [("gebissenes Tier", r"gebissen"), ("Eigentümer/in", r"eigentuemer|besitzer"), ("Halter/in", r"halter")],
    "gesetzliche_vertretung": [("Beistand/Vormund", r"beistand|beistaendin|vormund"),
                               ("Inhaber/in der elterlichen Sorge", r"elterlichen\s+sorge|sorgeberecht|erziehungsberecht")],
    "dritte": [("Zeugin/Zeuge", r"zeug"), ("Begleitperson", r"begleit"), ("Täter/in", r"taeter"),
               ("Erbin/Erbe", r"\berb|vermaechtnis"), ("Finder/in", r"finder"),
               ("nahestehende Person", r"nahestehend"), ("Drittperson", r"dritt")],
    "betrieb": [("Zweigniederlassung", r"zweigniederlassung|filiale|zweigbetrieb"), ("Einsatzbetrieb", r"einsatzbetrieb"),
                ("Lehrbetrieb", r"lehrbetrieb")],
    "kind": [("Pflegekind", r"pflege"), ("Stiefkind", r"stief")],
    "vertretung": [("Zustellungsbevollmächtigte/r", r"zustell")],
}


def falten(s):
    """The folded text the vocabulary is matched on (one definition for every caller)."""
    t = unicodedata.normalize("NFC", s or "").lower().replace("\u00df", "ss").replace("\u00ad", "")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("–", "-"), ("—", "-"), ("’", "'")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def woerter(text):
    """All party words of a text as (start, end, role, instance, kind), specific
    entries masking the shorter words inside them; sorted by position."""
    t = falten(text)
    belegt = [False] * len(t)
    treffer = []
    for rolle, rx, art in _WOERTER_RX:
        for m in rx.finditer(t):
            a, b = m.start(), m.end()
            if a == b or any(belegt[a:b]):
                continue
            for i in range(a, b):
                belegt[i] = True
            if rolle is not None:
                treffer.append((a, b, rolle, art, m.group(0)))
    treffer.sort()
    return t, treffer


class Hinweis:
    """What a text says about a party: a role (with instance) or a reason it
    cannot say (unklar), or nothing (None is returned instead)."""
    __slots__ = ("rolle", "instanz", "mehrere", "beleg", "unklar", "wort", "bezug")

    def __init__(self, rolle=None, instanz="", mehrere=False, beleg="", unklar=None, wort="", bezug=None):
        self.rolle, self.instanz, self.mehrere = rolle, instanz, mehrere
        self.beleg, self.unklar, self.wort = beleg, unklar, wort
        self.bezug = bezug                      # (role, instance) of the person it belongs to, or None


def _instanz(t, a, b, rolle, art, wort, gleiche=()):
    """Instance label of a hit: the type of the party («Verpächter/in»), the
    parent's word (Vater/Mutter), the kind of Gegenstand, a qualifier
    («anderer Elternteil», «neue Halterin») and a number («Kind 2», «1. Kind»,
    «Waffenangaben Waffe 2», «Tätigkeit 1 - Arbeitgeber»). `gleiche` are the
    spans of further words of the same role in the text (they may carry the number)."""
    teile = []
    if rolle == "gegenstand":
        teile.append(art)
        # «Startparzelle» and «Zielparzelle», «Zugfahrzeug» and «Fahrzeug» are two things;
        # «beissender Hund» and «gebissenes Tier» too
        m = re.match(r"(\w*?)(parzelle|grundstueck|liegenschaft|fahrzeug|anhaenger|schiff|hund|tier|gebaeude|"
                     r"objekt|anlage|waffe)", wort)
        if m and m.group(1) and len(m.group(1)) > 2:
            teile.append(m.group(1).capitalize() + "-")
        for typ, rx in (("gebissen", r"gebissen"), ("beissend", r"beissend")):
            if re.search(rx, t):
                teile.append(typ)
    for typ, rx in TYPEN.get(rolle, []):
        if re.search(rx, wort) or (rolle == "tierhalter" and re.search(rx, t)):
            teile.append(typ)
            break
    if rolle == "elternteil":
        w = wort
        teile.append("Vater" if "vater" in w else "Mutter" if "mutter" in w else
                     "Eltern" if re.search(r"\beltern\b", w) else "Elternteil")
        if w.startswith("pflege"):
            teile[-1] = "Pflege" + teile[-1].lower()
    q = _QUALI_VOR.search(t[max(0, a - 30):a])
    if q:
        stamm = re.sub(r"(e[rnms]?)$", "", q.group(1))
        stamm = QUALI.get(stamm, stamm)
        if rolle == "elternteil" and stamm in ("andere/r", "leibliche/r"):
            teile[-1] = {"andere/r": "anderer", "leibliche/r": "leiblicher"}[stamm] + " " + teile[-1]
        else:
            teile.append(stamm)
    q = _QUALI_NACH.match(t[b:b + 12])
    if q:
        teile.append({"alt": "bisherig", "bisher": "bisherig"}.get(q.group(1), q.group(1)))
    for a2, b2 in [(a, b)] + list(gleiche):
        z = _ZAHL_VOR.search(t[max(0, a2 - 8):a2]) or _ZAHL_NACH.match(t[b2:b2 + 14])
        if z:
            teile.append(z.group(1).upper())
            break
    return " ".join(x for x in teile if x)


QUALI = {"neu": "neu", "bisherig": "bisherig", "frueher": "frühere/r", "letzt": "letzte/r", "ander": "andere/r",
         "weiter": "weitere", "zusaetzlich": "zusätzlich", "leiblich": "leibliche/r", "ueberlebend": "überlebend",
         "aktuell": "aktuell", "vorherig": "vorherig", "uebergeordnet": "übergeordnet", "uebernehmend": "übernehmend"}


def hinweis(text, kontext=""):
    """Read one text (a label, a section name or a free-text role) for a party.
    Returns None (no party word), or a Hinweis with a role, or one with `unklar`
    set. The FIRST party word is the head; a later one counts only as its
    attribute («Kinder der gesuchstellenden Person», «Vertreter der klagenden
    Partei»), as an apposition in brackets, or as the same role; two roles joined
    by «/», «oder», «bzw.», «und» are two parties -> unklar."""
    if not text:
        return None
    t, tr = woerter(text)
    if not tr:
        return None
    if STATISTIK.search(t):
        return None
    if EIGENE_ALTERNATIVE.search(t):
        return Hinweis(unklar="mehrere_rollen", beleg=text)
    if any(r == "MEHRERE" for _, _, r, _, _ in tr):
        return Hinweis(unklar="mehrere_parteien", beleg=text)
    a, b, rolle, art, wort = tr[0]
    vor = t[:a]
    # a genitive head that is not a data noun («Betreuungsperson des Hundes»,
    # «Ansprüche gegenüber der Täterschaft») is someone or something else
    # «Zu Mutter», «Bei Vater» (Besuchsregelung): a relation to the party, not its Angabe
    if re.fullmatch(r"\s*(zu|zum|zur|bei|beim|mit|von|vom|an|fuer|gegenueber)\s+((dem|der|den|die|das)\s+)?", vor):
        return Hinweis(unklar="andere_person", beleg=text)
    m = _PRAEP_VOR.search(vor)
    if m:
        kopf = [w for w in re.findall(r"[a-z0-9]+", vor[:m.start()])]
        if kopf and not all(kopf_ok(w) for w in kopf):
            # «Art des Fahrzeuges», «Rechtsform der Organisation»: an Angabe about a thing or an
            # organisation that is not a party of its own here — no person is meant
            if rolle == "gegenstand" or rolle in ("betrieb", "behoerde", "versicherung"):
                return Hinweis(unklar="sache_organisation", beleg=text)
            return Hinweis(unklar="andere_person", beleg=text)
    # the first party word is an alternative to someone the text does not name
    # as a role («… der leistungsberechtigten Person oder ihrer Vertretung»);
    # a truncated compound («Ehe- oder Lebenspartner/in») is no alternative
    m = re.search(r"(\S+)\s+(oder|bzw\.?)\s+(\w+\s+){0,2}$", vor)
    if m and not m.group(1).endswith("-") and not re.search(NAME_FIRMA, vor):
        return Hinweis(unklar="mehrere_rollen", beleg=text)
    rest, gleiche, bezug = [], [], None
    for a2, b2, r2, art2, w2 in tr[1:]:
        if r2 == rolle and (art2 == art):
            gleiche.append((a2, b2))
            continue
        zwischen = t[b:a2]
        zw = _GENUS_NACH.sub("", zwischen)          # «Vertreter/-in der …»: the ending is no join
        if "(" in zw and ")" not in zw:
            if rolle == "gegenstand" and r2 != "gegenstand":
                rest.append(r2)               # «Wohnhaus (Ortsbezeichnung, Eigentümer)»: thing and owner
            continue                          # apposition in brackets: the same party
        if not zw.strip():
            # «Arbeitgeber Ehepartner/in»: the employer OF the spouse (one party, belonging to her)
            if rolle in ATTRIBUT_ROLLEN and r2 in FAMILIE and bezug is None:
                bezug = (r2, _instanz(t, a2, b2, r2, art2, w2))
                continue
            # «Bevollmächtigte Drittperson»: the noun the role word qualifies
            if r2 == "dritte" and re.match(r"dritt", w2):
                continue
        if _ATTR_VOR.search(t[:a2]) and not _JOIN.match(zw.strip() and zw or " "):
            if not re.search(r"(/|\boder\b|\bbzw\.?)\s*$", t[:a2]):
                continue                      # attribute: «X des Y»
        # «Gesuchsteller/in (Betrieb)», «Arbeitgeber/Firma»: the Betrieb word only
        # names the entity of an organisation-capable role
        if r2 == "betrieb" and ROLLE.get(rolle.rstrip("?"), {}).get("entitaet") in ("offen", "organisation"):
            continue
        if rolle == "betrieb" and ROLLE.get(r2.rstrip("?"), {}).get("entitaet") in ("offen",):
            rolle, art, wort, a, b = r2, art2, w2, a2, b2
            continue
        rest.append(r2)
    if rest:
        return Hinweis(unklar="mehrere_rollen", beleg=text)
    if rolle.endswith("?"):
        regeln = CONTEXT.get(rolle, [])
        ctx = falten(kontext)
        passt = [r for r, rx in regeln if re.search(rx, t) or re.search(rx, ctx)]
        if len(passt) != 1:
            return Hinweis(unklar="kontext", beleg=text)
        rolle = passt[0]
    inst = _instanz(t, a, b, rolle, art, t[a:b], gleiche)
    mehrere = bool(_PLURAL.search(wort) or re.match(r"\s*(personen|/en)\b", t[b:b + 12])
                   or re.search(r"verzeichnis|\bliste\b|\balle\b", t))
    return Hinweis(rolle=rolle, instanz=inst, mehrere=mehrere, beleg=text, wort=t[a:b], bezug=bezug)


# ---------------------------------------------------------------------------
# What kind of Angabe a unit is (decides what a party block may claim)
# ---------------------------------------------------------------------------
STD_PERSON = {"eCH-0044", "eCH-0011", "eCH-0021", "eCH-0006", "eCH-0135", "eCH-0020"}
STD_ORG = {"eCH-0097", "eCH-0098", "eCH-0108", "eCH-0116"}
STD_ADRESSE = {"eCH-0010", "eCH-0007", "eCH-0008"}
STD_KONTAKT = {"eCH-0046"}
EL_PERSON = {"officialName", "firstName", "lastName", "dateOfBirth", "sex", "vn", "personIdentification",
             "otherPersonId", "localPersonId", "euPersonId", "personId", "callName", "originalName",
             "nationalityData", "maritalStatus", "placeOfOrigin", "originName", "birthDate"}
EL_ORG = {"organisationName", "uid", "legalForm", "headquarterMunicipality", "organisationIdentification",
          "organisationAdditionalName", "uidOrganisationId"}
EL_ADRESSE = {"street", "houseNumber", "swissZipCode", "town", "addressInformation", "country", "locality",
              "postOfficeBoxNumber", "addressLine1", "mailAddress", "addressForCorrespondence", "mainAddress",
              "careOfAddressLine", "foreignZipCode", "municipalityName", "correspondenceAddress"}
EL_KONTAKT = {"phoneNumber", "emailAddress", "internetAddress", "phone", "email", "contact"}
LBL_PERSON = re.compile(r"\b(vorname|vornamen|nachname|familienname|ledigname|zivilstand|heimatort|buergerort|"
                        r"nationalitaet|staatsangehoerigkeit|ahv|ahv-nr|ahv-nummer|sozialversicherungsnummer|"
                        r"versichertennummer|versicherten-nr|personalien|beruf|geburtsort|konfession|religion)\b")
# a name, sex, age or birth date fits a person, an animal and (a name) an organisation
LBL_NAME = re.compile(r"\b(name|namen|bezeichnung)\b")
LBL_MERKMAL = re.compile(r"\b(geburtsdatum|geburtsjahr|geschlecht|jahrgang|alter|titel)\b")
LBL_ORG = re.compile(r"\b(firma|firmenname|firmenbezeichnung|uid|uid-nr|uid-nummer|rechtsform|handelsregister)\b")
LBL_ADRESSE = re.compile(r"\b(adresse|\w+adresse|strasse|plz|postleitzahl|\bort\b|wohnort|wohnsitz|land|postfach|"
                         r"anschrift|hausnummer|gemeinde|kanton|sitz)\b")
LBL_KONTAKT = re.compile(r"\b(telefon|telefonnummer|tel|mobile|mobil|natel|e-mail|e-mail-adresse|email|fax|homepage|"
                         r"website)\b")
LBL_UNTERSCHRIFT = re.compile(r"\bunterschrift\w*|\bunterzeichn\w*|\bvisum\b")
# a Gegenstand owns the Angaben that identify or describe it — not the costs,
# counts or requests the Formular asks about it
STD_OBJEKT = {"eCH-0129", "eCH-0216", "eCH-0206", "eCH-0134", "eCH-0185", "eCH-0262", "eCH-0265", "eCH-0131"}
ESH_OBJEKT = {"eSH-0014", "eSH-0017"}
OBJ_ATTR = re.compile(r"\b(nr|nummer|\w+nummer|\w*-nr|\w+nr|kontrollschild\w*|stamm\w*|marke|typ|\w*art|fabrikat|"
                      r"modell|baujahr|jahrgang|\w*flaeche\w*|lage|standort|adresse|strasse|ort|plz|bezeichnung|"
                      r"\w*name|kaliber|chip\w*|geschlecht|rasse|geburtsdatum|farbe|gewicht|leistung|groesse|"
                      r"ortsbezeichnung|gemeinde|egid|egrid|gb|grundbuch\w*|kataster\w*|alter|abmessung\w*|"
                      r"\w*geometrie|\w*umfang|\w*abstand|kastriert|kupiert)\b")
# what may stand next to a role word when the label is just the party itself
# («Firma», «Bauherrschaft», «Name der Vorsorgeeinrichtung», «Firma und Sitz»)
NUR_ROLLE = {"und", "oder", "bzw", "der", "die", "das", "des", "den", "dem", "zeile", "name", "namen", "adresse",
             "sitz", "ort", "angaben", "personalien", "daten", "neu", "neue", "neuer", "neues", "bisher", "bisherige",
             "bisheriger", "letzter", "letzte", "weitere", "weiterer", "zustaendige", "zustaendiger", "zustaendiges",
             "zustaendigen", "in", "im", "schweiz", "kanton", "ch", "sh", "schaffhausen", "inkl", "registrierten",
             "eingetragene", "zugelassene", "z", "b", "ausland"}


def art_der_angabe(std, el, label):
    """person | organisation | adresse | kontakt | unterschrift | sonstig — by the
    eCH element where there is one, else by the label."""
    if LBL_UNTERSCHRIFT.search(falten(label)):
        return "unterschrift"
    if el in EL_ORG or std in STD_ORG:
        return "organisation"
    if el in EL_PERSON or std in STD_PERSON:
        return "person"
    if el in EL_KONTAKT or std in STD_KONTAKT:
        return "kontakt"
    if el in ("country", "countryNameShort", "countryId"):
        return "sonstig"                  # a country alone identifies no party
    if el in EL_ADRESSE or std in STD_ADRESSE:
        return "adresse"
    if std:
        return "sonstig"
    t = falten(label)
    if LBL_ORG.search(t):
        return "organisation"
    if LBL_KONTAKT.search(t):
        return "kontakt"
    if LBL_PERSON.search(t):
        return "person"
    if LBL_ADRESSE.search(t):
        return "adresse"
    if LBL_MERKMAL.search(t):
        return "merkmal"
    if LBL_NAME.search(t):
        return "name"
    return "sonstig"


PARTEIANGABE = {"person", "organisation", "adresse", "kontakt", "unterschrift", "name", "merkmal"}


def objekt_angabe(p):
    """Does the point identify or describe a thing (for the role Gegenstand)?"""
    if p["std"] in STD_OBJEKT and p["el"] not in ("person", "relationshipToPerson"):
        return True
    if p["esh"] in ESH_OBJEKT:
        return True
    t = falten(p["teil_name"])
    return bool(OBJ_ATTR.search(t)) and not FINANZ.search(t) and not ZAEHLUNG.search(t)


def nur_rolle(text, h):
    """Is the label nothing but the party itself («Firma», «Bauherrschaft»,
    «Name der Vorsorgeeinrichtung»)? Then it asks for that party's name."""
    t = falten(text)
    w = h.wort or ""
    rest = t.replace(w, " ", 1) if w else t
    toks = [x for x in re.findall(r"[a-z0-9]+", rest) if not re.fullmatch(r"\d+|[a-c]|in|innen|r|n", x)]
    # the other words of the vocabulary entry (gender endings, «/-in») are not content
    return all(x in NUR_ROLLE for x in toks)


# ---------------------------------------------------------------------------
# The data points — the same unit as every export: a Teilfeld, or a Datenfeld
# without parts; keyed (data_field_id, teil) with teil = norm_ascii(name)
# ---------------------------------------------------------------------------
def punkte(conn):
    """Every data point with what B1 reads: labels, element, subjekt, begriff role."""
    ech = {r[0]: (r[1], r[2]) for r in conn.execute("SELECT id, standard, name FROM ech_element")}
    sib = {}
    for eid, (std, nm) in ech.items():
        sib.setdefault((std, nm), []).append(eid)
    bv = {r[0] for r in conn.execute("SELECT ech_element_id FROM begriff_vorschlag")} if _hat(conn, "begriff_vorschlag") else set()
    bl = {}
    if _hat(conn, "begriff_label"):
        for r in conn.execute("SELECT ech_element_id, label_norm, klasse, rolle FROM begriff_label"):
            bl[(r[0], r[1])] = (r[2], r[3])

    def begriff(eid, lab):
        # the same lookup as export_json (element id + norm_label, sibling contexts)
        if eid is None or eid not in ech:
            return None
        ln = norm_label(lab)
        if not ((eid, ln) in bl and eid in bv):
            alt = next((x for x in sib.get(ech[eid], []) if (x, ln) in bl and x in bv), None)
            if alt is not None:
                eid = alt
        return bl.get((eid, ln)) if eid in bv else None

    titel = {r[0]: r[1] for r in conn.execute("SELECT id, title FROM form")}
    # a yes/no option of a list: several yes/no fields of one Formular share one definition
    # («Für Nichterwerbstätige» on «Schüler(in)», «Pflegekind», «Rentner(in)» …)
    optionen = {}
    for fid_, defin_ in conn.execute("SELECT form_id, definition FROM data_field WHERE data_type='boolean' "
                                     "AND definition IS NOT NULL AND trim(definition) != ''"):
        k = (fid_, re.sub(r"\s+", " ", defin_.strip()))
        optionen[k] = optionen.get(k, 0) + 1
    subs = {}
    for r in conn.execute("SELECT data_field_id, ord, name, ech_element_id, esh_code FROM data_subfield "
                          "ORDER BY data_field_id, ord"):
        subs.setdefault(r[0], []).append((r[1], r[2], r[3], r[4]))
    out = []
    for d in conn.execute("SELECT id, form_id, ord, name, definition, subjekt, required, ech_element_id, esh_code, "
                          "data_type FROM data_field ORDER BY form_id, ord, id"):
        fid, form_id, ford, fname, defin, subjekt, req, eid, esh, dtyp = d
        teile = subs.get(fid)
        for sord, sname, seid, sesh in (teile or [(None, fname, eid, esh)]):
            std, el = ech.get(seid, (None, None))
            b = begriff(seid, sname)
            out.append({
                "data_field_id": fid, "form_id": form_id, "ford": ford if ford is not None else 0,
                "sord": sord if sord is not None else -1,
                "teil": norm_ascii(sname) if teile else "", "teil_name": sname, "feld": fname,
                "ist_teil": bool(teile), "definition": defin or "", "subjekt": subjekt,
                "pflicht": bool(req), "std": std, "el": el, "esh": sesh, "titel": titel.get(form_id, ""),
                "typ": dtyp, "option": dtyp == "boolean" and bool(defin) and
                optionen.get((form_id, re.sub(r"\s+", " ", (defin or "").strip())), 0) >= 3,
                "begriff_rolle": (b[1] or "").strip() if b and b[0] == "rolle" else "",
                "art": "sonstig" if dtyp == "boolean" else art_der_angabe(std, el, sname),
            })
    return out


def _hat(conn, t):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [t]).fetchone())


# ---------------------------------------------------------------------------
# Stage B1: one point
# ---------------------------------------------------------------------------
NIE_PERSON = {"betrieb", "behoerde", "versicherung"}     # never a natural person
# numbers that identify the CLIENT at an insurer or office, not the insurer or office
KUNDEN_NR = re.compile(r"abrechnungs\s*-?\s*(nr|nummer)|mitglied\w*\s*-?\s*(nr|nummer)|kunden\w*\s*-?\s*(nr|nummer)|"
                       r"police\w*|vertrags\s*-?\s*(nr|nummer)|versicherten\w*\s*-?\s*(nr|nummer)|\bahv\s*-?\s*(nr|nummer)")


def _passt(rolle, art):
    """Can a party of this role own an Angabe of this kind (by entity type)?"""
    ent = ROLLE[rolle]["entitaet"]
    if rolle == "gegenstand":
        return art in ("adresse", "sonstig", "name", "merkmal")
    if ent == "natuerliche_person" and art == "organisation":
        return False
    if (ent in ("organisation", "behoerde") or rolle in NIE_PERSON) and art in ("person", "merkmal"):
        return False
    return True


def _eigen_ok(h, p, nackt):
    """May the unit's own label / role claim this point for h.rolle?"""
    if h.rolle in EIGEN_ALLES:
        return True
    if h.rolle == "gegenstand":
        return objekt_angabe(p) or nackt
    if h.rolle in NIE_PERSON and (KUNDEN_NR.search(falten(p["teil_name"]))
                                  or (nackt and KUNDEN_NR.search(falten(p["definition"])))):
        # «Haftpflichtversicherung» defined as «Gesellschaft und Police-Nummer …»: the
        # policy number is the client's, not the insurer's
        return False
    return p["art"] in PARTEIANGABE or nackt


def _block_ok(h, p):
    """May a section (composite) of this role claim a Teilfeld without its own role word?"""
    if h.rolle == "gegenstand":
        return objekt_angabe(p) and p["art"] in ("adresse", "sonstig", "name", "merkmal")
    if h.rolle in BLOCK_ALLES:
        return True
    if h.rolle in NIE_PERSON and KUNDEN_NR.search(falten(p["teil_name"])):
        return False
    return p["art"] in PARTEIANGABE


def _instanz_vereinen(sec_i, own_i, own_nackt):
    """The instance when label and section name the same role: a label that is
    just the role word («Zeichnungsberechtigung», «Gebäude 1») keeps the section's
    instance and adds its number; a label that names a member of the section's
    group («Eltern des Kindes › Vater Vorname, Name») is the more specific one."""
    if not own_i:
        return sec_i
    if not sec_i:
        return own_i
    nummer = lambda s: [x for x in s.split() if re.fullmatch(r"\d+|[A-C]", x)]
    if own_nackt:
        return sec_i + ("" if nummer(sec_i) or not nummer(own_i) else " " + " ".join(nummer(own_i)))
    return own_i


def _zu(h, regel, bezug=None, instanz=None, abschnitt=None, attribut=False):
    return {"status": "zugeordnet", "rolle": h.rolle, "instanz": h.instanz if instanz is None else instanz,
            "bezug": bezug, "abschnitt": abschnitt, "mehrere": h.mehrere, "regel": regel, "beleg": h.beleg,
            "wort": h.wort, "attribut": attribut}


# the definition of a yes/no field names the person who submits
DEF_GESUCHSTELLER = re.compile(r"\b(?:die|der)\s+(?:antrag|gesuch)\s*-?\s*stellende[n]?\s+person\b|"
                               r"\b(?:antrag|gesuch)\s*-?\s*steller(?:in)?\b")


def _unklar(code, beleg=""):
    return {"status": "unklar", "grund_code": code, "beleg": beleg}


def ableiten_punkt(p):
    """Stage B1 for one data point: a party (role, instance, bezug) or «unklar»."""
    r = _ableiten_punkt(p)
    # a person's block never claims the address or contact of a workplace or school
    if r["status"] == "zugeordnet" and r["rolle"] in BLOCK_ALLES and r["rolle"] != "gegenstand" \
            and p["art"] in ("adresse", "kontakt") and r["regel"] == "wort_abschnitt" \
            and (ERWERB.search(falten(p["feld"])) or ERWERB.search(falten(p["teil_name"]))):
        return _unklar("arbeitsort", p["feld"])
    return r


def _ableiten_punkt(p):
    kontext = f"{p['titel']} {p['feld']}"
    own_txt = p["teil_name"]
    own_f = falten(own_txt)
    if ANDERE_PERSON.search(own_f) and p["art"] in ("person", "adresse", "kontakt"):
        return _unklar("andere_person", own_txt)
    if BEZIEHUNG.search(own_f):
        return _unklar("mehrere_parteien", own_txt)
    sec_fin = p["ist_teil"] and bool(FINANZ.search(falten(p["feld"])))
    own_fin = bool(FINANZ.search(own_f))
    zaehlt = bool(ZAEHLUNG.search(own_f))
    h_beg = hinweis(p["begriff_rolle"], kontext) if p["begriff_rolle"] and not zaehlt else None
    h_own = hinweis(own_txt, kontext) if not zaehlt else None
    h_sec = hinweis(p["feld"], p["titel"]) if p["ist_teil"] and not sec_fin else None
    # an accounted label or section names no party for anyone but the persons concerned
    if own_fin or sec_fin:
        if h_own and h_own.rolle not in EIGEN_ALLES:
            h_own = None
        if h_beg and h_beg.rolle not in EIGEN_ALLES:
            h_beg = None

    # the unit's own signal: label words and the naming layer's role must agree
    own, regel = None, None
    if h_own and h_beg:
        if h_own.unklar and h_beg.unklar:
            return _unklar(h_own.unklar, own_txt)
        if h_own.unklar or h_beg.unklar or h_own.rolle != h_beg.rolle:
            return _unklar("widerspruch", f"{own_txt} | Rolle «{p['begriff_rolle']}»")
        own, regel = h_beg, "rolle_begriff"
        own.beleg = own_txt
        if not own.instanz and h_own.instanz:
            own.instanz = h_own.instanz
    elif h_beg:
        if h_beg.unklar:
            return _unklar(h_beg.unklar, p["begriff_rolle"])
        own, regel = h_beg, "rolle_begriff"
    elif h_own:
        if h_own.unklar:
            return _unklar(h_own.unklar, own_txt)
        own, regel = h_own, "wort_bezeichnung"
    nackt = bool(h_own and h_own.rolle and nur_rolle(own_txt, h_own))
    # a yes/no option that names only a role or a thing — the label alone, or the head of one
    # option of a list («Schüler(in)», «Pflegekind zur späteren Adoption», «Fahrzeug») — is a
    # status, purpose or possession someone ticks, not a party of its own: the applicant's when
    # the definition says so, else unklar
    if p["typ"] == "boolean" and not p["ist_teil"] and own and own.rolle and h_own and h_own.rolle and \
            (nackt or (p["option"] and own_f.startswith(h_own.wort or "\0"))):
        if DEF_GESUCHSTELLER.search(falten(p["definition"])):
            h = Hinweis(rolle="gesuchsteller", beleg=p["definition"], wort="")
            return _zu(h, "definition") if _passt("gesuchsteller", p["art"]) else _unklar("entitaet", own_txt)
        return _unklar("auswahl", own_txt)
    sec = h_sec if (h_sec and h_sec.unklar is None) else None
    if h_sec and h_sec.unklar and own and not (own.rolle == "gesuchsteller"
                                               or ROLLE[own.rolle]["entitaet"] == "natuerliche_person"):
        # a section that is itself unclear («Finanzielle Beteiligung an einem anderen Betrieb»)
        # leaves an organisation's or a thing's word in it unclear too
        return _unklar(h_sec.unklar, p["feld"])

    if own:
        if sec and sec.rolle != own.rolle:
            if sec.rolle in BLOCK_ALLES and sec.rolle != "gegenstand" and own.rolle in ATTRIBUT_ROLLEN:
                # «Erwerbsangaben EhepartnerIn › Arbeitgeber»: an attribute of the person (it
                # does not decide the person's entity type)
                return _zu(sec, "wort_abschnitt", attribut=True)
            if own.rolle == "betrieb" and sec.rolle != "gegenstand" and \
                    ROLLE[sec.rolle]["entitaet"] in ("offen", "organisation"):
                # «Revisionsstelle › Firma»: the firm of that party
                if not _passt(sec.rolle, p["art"]):
                    return _unklar("entitaet", own_txt)
                return _zu(sec, "wort_abschnitt")
            if not _eigen_ok(own, p, nackt):
                return _unklar("nicht_parteiangabe", own_txt)
            if not _passt(own.rolle, p["art"]):
                return _unklar("entitaet", own_txt)
            bezug = own.bezug or ((sec.rolle, sec.instanz) if sec.rolle in FAMILIE and own.rolle != "gesuchsteller"
                                  else None)
            # an insurer named in the trailer's block is not the one named in the towing vehicle's
            abschnitt = p["feld"] if (bezug is None and own.rolle not in EIGEN_ALLES
                                      and sec.rolle not in BLOCK_ALLES - {"gegenstand"}) else None
            return _zu(own, regel, bezug, abschnitt=abschnitt)
        if sec and sec.rolle == own.rolle:
            if not (_eigen_ok(own, p, nackt) or _block_ok(sec, p)):
                return _unklar("nicht_parteiangabe", own_txt)
            if not _passt(own.rolle, p["art"]):
                return _unklar("entitaet", own_txt)
            return _zu(own, regel, own.bezug, instanz=_instanz_vereinen(sec.instanz, own.instanz, nackt),
                       abschnitt=p["feld"] if own.rolle == "gegenstand" else None)
        if not _eigen_ok(own, p, nackt):
            return _unklar("nicht_parteiangabe", own_txt)
        if not _passt(own.rolle, p["art"]):
            return _unklar("entitaet", own_txt)
        # «Verdienst aus Provision › Firma» is another firm than «Angaben zur Firma»
        abschnitt = p["feld"] if (p["ist_teil"] and own.rolle not in EIGEN_ALLES) else None
        return _zu(own, regel, own.bezug, abschnitt=abschnitt)

    if h_sec:
        if h_sec.unklar:
            return _unklar(h_sec.unklar, p["feld"])
        if not _block_ok(h_sec, p):
            return _unklar("nicht_parteiangabe", p["feld"])
        if not _passt(h_sec.rolle, p["art"]):
            return _unklar("entitaet", p["feld"])
        # «Fahrzeugangaben Anhänger» and «Fahrzeugangaben Zugfahrzeug» are two vehicles
        return _zu(h_sec, "wort_abschnitt", abschnitt=p["feld"] if h_sec.rolle == "gegenstand" else None)

    if p["subjekt"] == "behoerde" and p["art"] in PARTEIANGABE and not (own_fin or zaehlt):
        # one field = one authority: two fields judged 'behoerde' may name two of them
        return _zu(Hinweis(rolle="behoerde", beleg=p["feld"], wort=""), "subjekt", abschnitt=p["feld"])
    if p["subjekt"] == "sache":
        return _unklar("sache_ohne_gegenstand", p["feld"])
    if p["art"] == "person" or (p["ist_teil"] and re.search(r"personalien|angaben zur person|persoenliche",
                                                              falten(p["feld"]))):
        return _unklar("personalien_ohne_rolle", p["feld"] if p["ist_teil"] else own_txt)
    return _unklar("kein_hinweis", "")


# ---------------------------------------------------------------------------
# Stage B1: parties of a Formular, entity types, subjekt consistency
# ---------------------------------------------------------------------------
def _bezeichnung(rolle, instanz, bezug, abschnitt=None):
    """«Kind 2», «anderer Elternteil», «Arbeitgeber/in (letzte/r)», «Gegenstand: Fahrzeug»,
    «Arbeitgeber/in, zu: Ehepartner/in …»."""
    lab = ROLLE[rolle]["label"]
    teile = instanz.split() if instanz else []
    nummer = [x for x in teile if re.fullmatch(r"\d+|[A-C]", x)]
    rest = " ".join(x for x in teile if x not in nummer)
    if rest and lab.lower().startswith(rest.lower()):
        rest = ""                         # «Vertragspartei (Vertragspartei)» says nothing
    if rolle == "gegenstand":
        art = next((a for a in GEGENSTAND_ARTEN if rest.startswith(a)), "")
        mehr = rest[len(art):].strip()
        lab = "Gegenstand" + (f": {art}" if art else "") + (f" ({mehr})" if mehr else "")
    elif rolle == "elternteil" and rest:
        lab = rest[0].upper() + rest[1:]
    elif rest:
        lab = f"{lab} ({rest})"
    if nummer:
        lab += " " + " ".join(nummer)
    if bezug:
        lab += ", zu: " + _bezeichnung(bezug[0], bezug[1], None)
    if abschnitt:
        lab += f" — im Abschnitt «{abschnitt[:70]}»"
    return lab


# the kinds of Angabe that are a party's own (they decide its entity type)
EIGENE_ARTEN = {"person", "organisation", "adresse", "kontakt", "name", "merkmal"}


def _eigene_subjekte(L):
    """The judged subjekte that decide a party's entity type: those of its own Angaben
    (name, person, organisation, address, contact), not of an attribute in its block;
    all of its points when none of them is such an Angabe with a subjekt."""
    eigen = [p["subjekt"] for p, r in L if p["art"] in EIGENE_ARTEN and not r.get("attribut") and p["subjekt"]]
    return eigen or [p["subjekt"] for p, _ in L]


def _entitaet(rolle, subjekte):
    fix = ROLLE[rolle]["entitaet"]
    s = {x for x in subjekte if x}
    if fix != "offen":
        return fix
    if not s:
        return "offen"
    if len(s) == 1:
        return next(iter(s))
    if s <= {"natuerliche_person", "organisation", "gemischt"}:
        return "gemischt"
    return None                       # sache/behoerde mixed with persons: no one entity


def subjekt_passt(ent, subjekt):
    """THE consistency rule between a party and a field's judged subjekt (also the gate)."""
    if not subjekt:
        return True
    if ent == subjekt:
        return True
    return ent == "gemischt" and subjekt in ("natuerliche_person", "organisation", "gemischt")


def ableiten_formular(ps):
    """B1 for all points of one Formular: (parties, assignments). Deterministic:
    party numbers follow the order in which the Formular first asks about them."""
    res = [ableiten_punkt(p) for p in ps]
    for _ in range(3):                # demote points that break the entity rule, then rebuild
        gruppen = {}
        for p, r in zip(ps, res):
            if r["status"] == "zugeordnet":
                k = (r["rolle"], r["instanz"], r["bezug"], r.get("abschnitt"))
                gruppen.setdefault(k, []).append((p, r))
        geaendert = False
        for k, L in gruppen.items():
            ent = _entitaet(k[0], _eigene_subjekte(L))
            for p, r in L:
                if ent is None or not subjekt_passt(ent, p["subjekt"]):
                    r.clear()
                    r.update(_unklar("subjekt", p["feld"]))
                    geaendert = True
        if not geaendert:
            break
    parteien, nr_of = [], {}
    for p, r in zip(ps, res):
        if r["status"] != "zugeordnet":
            continue
        k = (r["rolle"], r["instanz"], r["bezug"], r.get("abschnitt"))
        if k not in nr_of:
            nr_of[k] = len(parteien) + 1
            parteien.append({"nr": nr_of[k], "rolle": k[0], "instanz": k[1], "bezug": k[2], "abschnitt": k[3],
                             "bezeichnung": _bezeichnung(*k), "mehrere": False, "beleg": r["beleg"],
                             "punkte": []})
        pa = parteien[nr_of[k] - 1]
        pa["mehrere"] = pa["mehrere"] or bool(r["mehrere"])
        pa["punkte"].append((p, r))
        r["partei_nr"] = nr_of[k]
    for pa in parteien:
        pa["entitaet"] = _entitaet(pa["rolle"], _eigene_subjekte(pa.pop("punkte")))
    return parteien, res


def _grund_text(r):
    if r["status"] == "zugeordnet":
        w = r["beleg"]
        return REGEL_TEXT[r["regel"]].format(w=w)
    t = UNKLAR_GRUENDE[r["grund_code"]]
    return t + (f": «{r['beleg']}»" if r.get("beleg") else "")


# ---------------------------------------------------------------------------
# Grounding of the role list (computed from the databank's own words)
# ---------------------------------------------------------------------------
# The party words of the Lebenslagen key (export_json.PARTY) and what each says here.
LEBENSLAGEN_WOERTER = {
    "ehe(gatt|partner|frau|mann)": "ehepartner", "partner": "ehepartner (allein zu breit: auch Ansprechpartner)",
    "kind": "kind", "tochter": "kind (allein zu breit: auch Tochtergesellschaft)", "sohn": "kind",
    "vater": "elternteil", "mutter": "elternteil (allein zu breit: auch Mutterschaft)", "eltern": "elternteil",
    "arbeitgeb": "arbeitgeber", "vertret": "vertretung / gesetzliche_vertretung / organ (Stellvertretung)",
    "bevollm": "vertretung", "verstorb": "verstorbene", "erblass": "verstorbene",
    "eigentüm": "grundeigentuemer / tierhalter / halter (je nach Gegenstand)", "vermiet": "vertragspartei",
    "mieter": "vertragspartei", "pächter": "vertragspartei", "verpächt": "vertragspartei", "käufer": "vertragspartei",
    "verkäufer": "vertragspartei", "halter": "halter / tierhalter (je nach Gegenstand)",
    "begleit": "dritte (Begleitperson)", "zeug": "dritte (allein zu breit: auch Fahrzeug, Zeugnis)",
    "gläubig": "gesuchsteller / gegenpartei (je nach Verfahren; sonst unklar)", "schuldn": "keine Rolle (Schuldner der steuerbaren Leistung ist meist die einreichende Firma)",
    "bürge": "keine Rolle (allein zu breit: auch Bürgerort)", "teilhaber": "organ", "gesellschafter": "organ",
    "geschäftsführ": "organ", "kontaktperson": "kontaktperson", "ansprechperson": "kontaktperson",
}


def lebenslagen_abgleich():
    """The party words of the Lebenslagen key (export_json.PARTY, read from the
    source text, never imported) against LEBENSLAGEN_WOERTER: every word must
    say what it means here. Returns (missing, extra)."""
    import ast
    pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "export_json.py")
    try:
        baum = ast.parse(open(pfad, encoding="utf-8").read())
    except OSError:
        return None
    muster = None
    for n in baum.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PARTY" for t in n.targets):
            arg = n.value.args[0]
            muster = "".join(x.value for x in ast.walk(arg) if isinstance(x, ast.Constant) and isinstance(x.value, str))
    if muster is None:
        return None
    teile, tiefe, akt = [], 0, ""
    for ch in muster:
        if ch == "(":
            tiefe += 1
        elif ch == ")":
            tiefe -= 1
        if ch == "|" and tiefe == 0:
            teile.append(akt); akt = ""
        else:
            akt += ch
    teile.append(akt)
    return sorted(set(teile) - set(LEBENSLAGEN_WOERTER)), sorted(set(LEBENSLAGEN_WOERTER) - set(teile))


def rollentexte(conn):
    """The free-text role strings of the naming layer (every non-empty
    begriff_label.rolle, 790 on 2026-10-04) with their number of labels, each
    read with the vocabulary: (text, n, role code | None, reason)."""
    out = []
    if not _hat(conn, "begriff_label"):
        return out
    for txt, n in conn.execute("SELECT rolle, COUNT(*) FROM begriff_label WHERE rolle IS NOT NULL "
                               "AND trim(rolle)!='' GROUP BY rolle ORDER BY rolle"):
        h = hinweis(txt)
        if h and h.rolle:
            out.append((txt, n, h.rolle, None))
        else:
            out.append((txt, n, None, h.unklar if h else "keine_partei"))
    return out


def grundlage(conn, ps):
    """Per role, how the list entry is grounded in the databank's own words:
    the free-text role strings of the naming layer the vocabulary maps to it,
    the Lebenslagen party words, and how many distinct labels and sections of
    the Formulare carry one of its words (with the shortest examples)."""
    g = {c: {"im_auftrag_genannt": ROLLE[c]["spec"], "rollen_texte": {}, "lebenslagen_woerter": [],
             "n_bezeichnungen": 0, "n_abschnitte": 0, "beispiele": []} for c in ROLLE}
    for txt, n, rolle, _ in rollentexte(conn):
        if rolle in g:
            g[rolle]["rollen_texte"][txt] = n
    for w, r in LEBENSLAGEN_WOERTER.items():
        for c in re.findall(r"[a-z_]+", r.split(" (")[0]):
            if c in g:
                g[c]["lebenslagen_woerter"].append(w)
    labs, secs = {}, {}
    for p in ps:
        for txt, ziel in ((p["teil_name"], labs), (p["feld"] if p["ist_teil"] else None, secs)):
            if not txt:
                continue
            h = hinweis(txt, p["titel"])
            if h and h.rolle:
                ziel.setdefault(h.rolle, set()).add(txt)
    for c in g:
        g[c]["n_rollen_texte"] = len(g[c]["rollen_texte"])
        g[c]["n_bezeichnungen"] = len(labs.get(c, ()))
        g[c]["n_abschnitte"] = len(secs.get(c, ()))
        g[c]["beispiele"] = sorted(secs.get(c, set()) | labs.get(c, set()), key=lambda s: (len(s), s))[:6]
        g[c]["rollen_texte"] = dict(sorted(g[c]["rollen_texte"].items(), key=lambda kv: (-kv[1], kv[0])))
    return g


# ---------------------------------------------------------------------------
# Stage B2 verdicts: applied over B1 where current
# ---------------------------------------------------------------------------
def _punkt_key(p):
    return f"{p['data_field_id']}" + (f"|{p['teil']}" if p["teil"] else "")


# the reason of an «unklar» point as the reader sees it: the judged verdict (partei_urteil, kept as
# loaded) sometimes names the next step of the review («Kandidat für die Zweitprüfung des Subjekts»,
# «das Subjekt zuerst in der Zweitprüfung prüfen») or says «Entität»; the derived reason describes
# the contradiction only — the subjekt question itself is counted and listed elsewhere
LESER_WORTLAUT = (
    (r"\s*—\s*Kandidat für die Zweitprüfung des Subjekts", ""),
    (r"\s*—\s*das Subjekt zuerst in der Zweitprüfung prüfen\.?", "."),
    (r",\s*darum zuerst das Subjekt in der Zweitprüfung klären", ""),
    (r"\bdie Entität passt nicht\b", "die Art der Partei passt nicht dazu"),
)


def leser_grund(t):
    for muster, ersatz in LESER_WORTLAUT:
        t = re.sub(muster, ersatz, t)
    return re.sub(r"\.\.+$", ".", t).strip()


def urteil_anwenden(urteil, ps):
    """A loaded B2 verdict for the current points of its Formular, or None when
    it no longer covers exactly these points (then B1 applies and the verdict
    is reported as stale)."""
    pk = {_punkt_key(p): p for p in ps}
    punkte_u = {x["key"]: x for x in urteil["punkte"]}
    if set(punkte_u) != set(pk):
        return None
    parteien = [{"nr": x["nr"], "rolle": x["rolle"], "entitaet": x["entitaet"], "bezeichnung": x["bezeichnung"],
                 "mehrere": bool(x.get("mehrere")), "beleg": x["beleg"]} for x in urteil["parteien"]]
    res = []
    for p in ps:
        x = punkte_u[_punkt_key(p)]
        if x.get("partei") is not None:
            res.append({"status": "zugeordnet", "partei_nr": x["partei"],
                        "grund": "Aus dem Formulartext: " + (x.get("beleg") or "Zuordnung aus dem Formulartext")})
        else:
            res.append({"status": "unklar", "partei_nr": None, "grund_code": "urteil",
                        "grund": UNKLAR_GRUENDE["urteil"].format(w=leser_grund(x["unklar"]))})
    return parteien, res


# ---------------------------------------------------------------------------
# Writing: staging -> validate -> swap, idempotent
# ---------------------------------------------------------------------------
def berechnen(conn):
    """Everything the three derived tables should hold, as row lists (deterministic)."""
    ps = punkte(conn)
    nach_form = {}
    for p in ps:
        nach_form.setdefault(p["form_id"], []).append(p)
    urteile = {}
    if _hat(conn, "partei_urteil"):
        for r in conn.execute("SELECT form_id, parteien, punkte FROM partei_urteil"):
            urteile[r[0]] = {"parteien": json.loads(r[1]), "punkte": json.loads(r[2])}
    g = grundlage(conn, ps)
    rollen_rows = [(c, ROLLE[c]["label"], ROLLE[c]["entitaet"], ROLLE[c]["erklaerung"],
                    json.dumps(g[c], ensure_ascii=False, sort_keys=True), ROLLE[c]["ord"], "vorschlag")
                   for c in ROLLE]
    partei_rows, punkt_rows, veraltet = [], [], []
    for form_id in sorted(nach_form):
        L = nach_form[form_id]
        b1_parteien, b1 = ableiten_formular(L)
        b1_rolle = [r.get("rolle") if r["status"] == "zugeordnet" else None for r in b1]
        u = urteile.get(form_id)
        angewandt = urteil_anwenden(u, L) if u else None
        if u and angewandt is None:
            veraltet.append(form_id)
        if angewandt:
            parteien, res = angewandt
            for pa in parteien:
                partei_rows.append((form_id, pa["nr"], pa["rolle"], pa["entitaet"], pa["bezeichnung"],
                                    int(pa["mehrere"]), pa["beleg"], "urteil"))
            for p, r, br in zip(L, res, b1_rolle):
                punkt_rows.append((p["data_field_id"], p["teil"], form_id, p["teil_name"], r["status"],
                                   r["partei_nr"], None, r.get("grund_code"), r["grund"], "urteil", br))
            continue
        for pa in b1_parteien:
            partei_rows.append((form_id, pa["nr"], pa["rolle"], pa["entitaet"], pa["bezeichnung"],
                                int(pa["mehrere"]), pa["beleg"], "regel"))
        for p, r in zip(L, b1):
            zug = r["status"] == "zugeordnet"
            punkt_rows.append((p["data_field_id"], p["teil"], form_id, p["teil_name"], r["status"],
                               r.get("partei_nr") if zug else None, r.get("regel") if zug else None,
                               None if zug else r["grund_code"], _grund_text(r), "regel",
                               r.get("rolle") if zug else None))
    return rollen_rows, partei_rows, punkt_rows, veraltet


def _dump(conn):
    """A fingerprint of everything this layer writes (the three derived tables, the
    loaded verdicts without their load date, and the second reviews of kind 'partei')."""
    if not all(_hat(conn, t) for t in TABELLEN):
        return None
    h = hashlib.sha256()
    for q in ("SELECT * FROM partei_rolle ORDER BY code",
              "SELECT * FROM formular_partei ORDER BY form_id, partei_nr",
              "SELECT * FROM datenpunkt_partei ORDER BY data_field_id, teil",
              "SELECT form_id, file_hash, parteien, punkte FROM partei_urteil ORDER BY form_id"):
        for r in conn.execute(q):
            h.update(json.dumps(list(r), ensure_ascii=False).encode())
    if _hat(conn, "panel_review"):
        for r in conn.execute("SELECT * FROM panel_review WHERE kind='partei' ORDER BY item_id"):
            h.update(json.dumps(list(r), ensure_ascii=False).encode())
    return h.hexdigest()


def schreiben(c, rollen_rows, partei_rows, punkt_rows):
    c.executescript(DDL)
    c.execute("DELETE FROM datenpunkt_partei")
    c.execute("DELETE FROM formular_partei")
    c.execute("DELETE FROM partei_rolle")
    c.executemany("INSERT INTO partei_rolle(code,label,entitaet,erklaerung,grundlage,ord,status) VALUES(?,?,?,?,?,?,?)",
                  rollen_rows)
    c.executemany("INSERT INTO formular_partei(form_id,partei_nr,rolle,entitaet,bezeichnung,mehrere,beleg,herkunft) "
                  "VALUES(?,?,?,?,?,?,?,?)", partei_rows)
    c.executemany("INSERT INTO datenpunkt_partei(data_field_id,teil,form_id,teil_name,status,partei_nr,regel,"
                  "grund_code,grund,herkunft,regel_rolle) VALUES(?,?,?,?,?,?,?,?,?,?,?)", punkt_rows)
    c.commit()


def _validieren(c):
    """validate_db plus this gate (once validate_db calls pruefen itself, nothing is reported twice)."""
    from validate_db import validate
    errs = validate(c)
    return errs + [e for e in pruefen(c) if e not in errs]


def ableiten():
    live = connect(DB_PATH)
    vorher = _dump(live)
    live.close()
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    rollen_rows, partei_rows, punkt_rows, veraltet = berechnen(c)
    schreiben(c, rollen_rows, partei_rows, punkt_rows)
    fehlt = vollstaendig(c)
    errs = fehlt + _validieren(c)
    nachher = _dump(c)
    c.close()
    if errs:
        os.remove(st)
        print("ABBRUCH — nichts geschrieben:", *errs[:8], sep="\n  ")
        sys.exit(1)
    n_zu = sum(1 for r in punkt_rows if r[4] == "zugeordnet")
    msg = (f"{len(rollen_rows)} Rollen, {len(partei_rows)} Parteien auf "
           f"{len({r[0] for r in partei_rows})} Formularen, {len(punkt_rows)} Datenpunkte: {n_zu} zugeordnet, "
           f"{len(punkt_rows) - n_zu} unklar; {sum(1 for r in punkt_rows if r[9] == 'urteil')} aus Stufe B2")
    if veraltet:
        msg += f"; {len(veraltet)} B2-Urteile veraltet (Felder geändert, Stufe B1 gilt): {veraltet[:10]}"
    if vorher == nachher:
        os.remove(st)
        print("rollen: unverändert — " + msg)
        return
    os.replace(st, DB_PATH)
    print("rollen: geschrieben — " + msg)


def vollstaendig(conn):
    """Every current data point exactly once (the loaders' completeness rule)."""
    soll = {(p["data_field_id"], p["teil"]) for p in punkte(conn)}
    ist = [(r[0], r[1]) for r in conn.execute("SELECT data_field_id, teil FROM datenpunkt_partei")]
    errs = []
    if len(ist) != len(set(ist)):
        errs.append("datenpunkt_partei: ein Datenpunkt steht mehrfach")
    if soll - set(ist):
        errs.append(f"datenpunkt_partei: {len(soll - set(ist))} Datenpunkte ohne Zuordnung")
    if set(ist) - soll:
        errs.append(f"datenpunkt_partei: {len(set(ist) - soll)} Zeilen ohne Datenpunkt")
    k = conn.execute("SELECT COUNT(*) FROM formular_partei fp WHERE NOT EXISTS (SELECT 1 FROM datenpunkt_partei d "
                     "WHERE d.form_id=fp.form_id AND d.partei_nr=fp.partei_nr)").fetchone()[0]
    if k:
        errs.append(f"formular_partei: {k} Parteien ohne einen einzigen Datenpunkt")
    return errs


# ---------------------------------------------------------------------------
# The gate for validate_db
# ---------------------------------------------------------------------------
def pruefen(conn):
    """Integrity of the party layer; [] when the layer is absent (fresh database).
    A data point without a row, or a row whose label changed since the
    derivation, is NOT an error here (like a missing Gestaltung measurement): it
    is «noch nicht abgeleitet» until `rollen.py ableiten` runs, which the build
    does right after init_register.py; the loaders of this layer check
    completeness themselves (vollstaendig)."""
    da = [t for t in TABELLEN if _hat(conn, t)]
    if not da:
        return []
    errs = []
    if set(da) != set(TABELLEN):
        return [f"Parteien-Schicht unvollständig: es fehlen {sorted(set(TABELLEN) - set(da))}"]

    def n(q, *a):
        return conn.execute(q, a).fetchone()[0]

    # the role list equals the module's list (labels and entity types are the contract)
    dbr = {r[0]: (r[1], r[2]) for r in conn.execute("SELECT code, label, entitaet FROM partei_rolle")}
    soll = {c: (ROLLE[c]["label"], ROLLE[c]["entitaet"]) for c in ROLLE}
    if dbr != soll:
        errs.append(f"partei_rolle weicht von der Liste in scripts/rollen.py ab: "
                    f"{sorted(set(dbr.items()) ^ set(soll.items()))[:4]}")
    for (g,) in conn.execute("SELECT grundlage FROM partei_rolle"):
        try:
            if not isinstance(json.loads(g), dict):
                raise ValueError
        except ValueError:
            errs.append("partei_rolle.grundlage ist kein JSON-Objekt")
            break
    k = n("SELECT COUNT(*) FROM partei_rolle WHERE trim(erklaerung)='' OR trim(label)=''")
    if k:
        errs.append(f"{k} Rollen ohne Bezeichnung oder Erklärung")
    # parties
    k = n("SELECT COUNT(*) FROM formular_partei WHERE rolle NOT IN (SELECT code FROM partei_rolle)")
    if k:
        errs.append(f"{k} Parteien mit einer Rolle ausserhalb der Liste")
    k = n("SELECT COUNT(*) FROM formular_partei fp JOIN partei_rolle r ON r.code=fp.rolle "
          "WHERE r.entitaet!='offen' AND fp.entitaet!=r.entitaet")
    if k:
        errs.append(f"{k} Parteien, deren Entität der festen Entität ihrer Rolle widerspricht")
    k = n("SELECT COUNT(*) FROM formular_partei WHERE partei_nr<1 OR trim(beleg)='' OR trim(bezeichnung)=''")
    if k:
        errs.append(f"{k} Parteien ohne Nummer, Bezeichnung oder Beleg")
    # a party without a single point is stale, not an error: another loader replaced the
    # fields it rests on (the cascade removed their rows); `rollen.py ableiten` derives the
    # layer again, and the loaders here demand it themselves (vollstaendig)
    # assignments
    k = n("SELECT COUNT(*) FROM datenpunkt_partei WHERE (status='zugeordnet') != (partei_nr IS NOT NULL)")
    if k:
        errs.append(f"{k} Datenpunkte: Status und Partei passen nicht zusammen")
    k = n("SELECT COUNT(*) FROM datenpunkt_partei d JOIN data_field f ON f.id=d.data_field_id WHERE f.form_id!=d.form_id")
    if k:
        errs.append(f"{k} Datenpunkte zeigen auf ein anderes Formular als ihr Feld")
    k = n("SELECT COUNT(*) FROM datenpunkt_partei WHERE trim(grund)=''")
    if k:
        errs.append(f"{k} Datenpunkte ohne Beleg oder Grund")
    ok_g = "','".join(UNKLAR_GRUENDE)
    k = n(f"SELECT COUNT(*) FROM datenpunkt_partei WHERE status='unklar' AND COALESCE(grund_code,'') NOT IN ('{ok_g}')")
    if k:
        errs.append(f"{k} unklare Datenpunkte ohne gültigen Grund (Codes: {', '.join(UNKLAR_GRUENDE)})")
    ok_r = "','".join(REGELN)
    k = n(f"SELECT COUNT(*) FROM datenpunkt_partei WHERE herkunft='regel' AND status='zugeordnet' "
          f"AND COALESCE(regel,'') NOT IN ('{ok_r}')")
    if k:
        errs.append(f"{k} Zuordnungen der Stufe B1 ohne gültige Regel")
    # subjekt consistency: the party's entity type equals the field's judged subjekt
    bad = 0
    for ent, sj in conn.execute("SELECT fp.entitaet, f.subjekt FROM datenpunkt_partei d "
                                "JOIN formular_partei fp ON fp.form_id=d.form_id AND fp.partei_nr=d.partei_nr "
                                "JOIN data_field f ON f.id=d.data_field_id WHERE f.subjekt IS NOT NULL"):
        if not subjekt_passt(ent, sj):
            bad += 1
    if bad:
        errs.append(f"{bad} Datenpunkte: die Entität der Partei widerspricht dem beurteilten Subjekt des Felds")
    # stages: a Formular is either B1 or B2 throughout; B2 rows need a loaded verdict
    k = n("SELECT COUNT(*) FROM (SELECT form_id FROM datenpunkt_partei GROUP BY form_id HAVING COUNT(DISTINCT herkunft)>1)")
    if k:
        errs.append(f"{k} Formulare mischen Stufe B1 und B2")
    k = n("SELECT COUNT(*) FROM formular_partei fp WHERE herkunft='urteil' "
          "AND NOT EXISTS (SELECT 1 FROM partei_urteil u WHERE u.form_id=fp.form_id)")
    if k:
        errs.append(f"{k} Parteien der Stufe B2 ohne geladenes Urteil")
    for fid, pj, uj in conn.execute("SELECT form_id, parteien, punkte FROM partei_urteil"):
        e = _urteil_struktur(fid, pj, uj)
        if e:
            errs.append(f"partei_urteil Formular {fid}: {e}")
    if _hat(conn, "panel_review"):
        k = n("SELECT COUNT(*) FROM panel_review WHERE kind='partei' AND item_id NOT IN (SELECT form_id FROM partei_urteil)")
        if k:
            errs.append(f"{k} Zweitprüfungen (panel_review partei) ohne Urteil der Stufe B2")
    return errs


def _urteil_struktur(fid, pj, uj):
    """Structure of a stored B2 verdict (the text gates ran at load time)."""
    try:
        parteien, pkte = json.loads(pj), json.loads(uj)
    except ValueError:
        return "kein JSON"
    if not isinstance(parteien, list) or not isinstance(pkte, list):
        return "parteien/punkte sind keine Listen"
    nrs = set()
    for x in parteien:
        if not isinstance(x, dict) or x.get("rolle") not in ROLLE or x.get("entitaet") not in ENT_PARTEI \
                or not isinstance(x.get("nr"), int) or x["nr"] in nrs or not (x.get("beleg") or "").strip():
            return f"Partei ungültig: {str(x)[:80]}"
        fix = ROLLE[x["rolle"]]["entitaet"]
        if fix != "offen" and x["entitaet"] != fix:
            return f"Partei {x['nr']}: Entität passt nicht zur Rolle"
        nrs.add(x["nr"])
    keys = [x.get("key") for x in pkte if isinstance(x, dict)]
    if len(keys) != len(pkte) or len(keys) != len(set(keys)):
        return "ein Datenpunkt fehlt der Schlüssel oder steht doppelt"
    for x in pkte:
        if x.get("partei") is None and len((x.get("unklar") or "").strip()) < 8:
            return f"Datenpunkt {x.get('key')}: weder Partei noch Grund"
        if x.get("partei") is not None and x["partei"] not in nrs:
            return f"Datenpunkt {x.get('key')}: Partei {x['partei']} nicht aufgeführt"
    return None


# ---------------------------------------------------------------------------
# Export hook (export_json.py): parties per Formular and per data point
# ---------------------------------------------------------------------------
def export_parteien(conn):
    """The party layer as the export reads it: role list, parties per Formular
    and the assignment per data point keyed (data_field_id, teil). Raises
    sqlite3.OperationalError «no such table» when the layer is absent, so the
    caller's _layer_skipped() skips it loudly."""
    rollen = [{"code": r[0], "label": r[1], "entitaet": r[2], "erklaerung": r[3], "status": r[4]}
              for r in conn.execute("SELECT code, label, entitaet, erklaerung, status FROM partei_rolle ORDER BY ord")]
    parteien = {}
    for r in conn.execute("SELECT form_id, partei_nr, rolle, entitaet, bezeichnung, mehrere, beleg, herkunft "
                          "FROM formular_partei ORDER BY form_id, partei_nr"):
        parteien.setdefault(r[0], []).append({"nr": r[1], "rolle": r[2], "entitaet": r[3], "bezeichnung": r[4],
                                              "mehrere": bool(r[5]), "beleg": r[6], "herkunft": r[7]})
    zuordnung = {}
    for r in conn.execute("SELECT data_field_id, teil, teil_name, status, partei_nr, regel, grund_code, grund, herkunft "
                          "FROM datenpunkt_partei"):
        zuordnung[(r[0], r[1])] = {"teil_name": r[2], "status": r[3], "partei": r[4], "regel": r[5],
                                   "grund_code": r[6], "grund": r[7], "herkunft": r[8]}
    return {"rollen": rollen, "parteien": parteien, "zuordnung": zuordnung}


def parteien_anhaengen(conn, forms):
    """The export hook (export_json.build(), once, after the units exist): sets
    fm['parteien'] on every Formular and u['partei'] on every data point, always
    with the same four keys (a fixed shape, so a state that appears or disappears
    never changes the structure of the export):
      {"status": "zugeordnet", "nr": n, "code": rule, "grund": null}     stage B1 (rule code)
      {"status": "zugeordnet", "nr": n, "code": "urteil", "grund": null} stage B2
      {"status": "unklar", "nr": null, "code": reason, "grund": null}    unklar (B1 reason code)
      {"status": "unklar", "nr": null, "code": "urteil", "grund": t}     unklar by stage B2, its reason
      {"status": "offen", "nr": null, "code": null, "grund": null}       not yet derived (row missing
                                                                         or its label changed)
    The German texts of the rule and reason codes are returned once (regeln,
    gruende), with the role list and the figures, for data_export.json."""
    x = export_parteien(conn)
    z = {"punkte": 0, "zugeordnet": 0, "unklar": 0, "offen": 0, "formulare_mit_partei": 0,
         "aus_urteil": 0, "regel": {}, "grund": {}}
    for fm in forms:
        fm["parteien"] = x["parteien"].get(fm["id"], [])
        z["formulare_mit_partei"] += bool(fm["parteien"])
        for d in fm.get("data_fields") or []:
            subs = [s for s in (d.get("subfields") or []) if isinstance(s, dict)]
            for u in (subs or [d]):
                key = (d["id"], norm_ascii(u.get("name")) if subs else "")
                a = x["zuordnung"].get(key)
                z["punkte"] += 1
                if not a or a["teil_name"] != (u.get("name") if subs else d["name"]):
                    u["partei"] = {"status": "offen", "nr": None, "code": None, "grund": None}
                    z["offen"] += 1
                    continue
                z[a["status"]] += 1
                z["aus_urteil"] += a["herkunft"] == "urteil"
                if a["status"] == "zugeordnet":
                    code = "urteil" if a["herkunft"] == "urteil" else a["regel"]
                    u["partei"] = {"status": "zugeordnet", "nr": a["partei"], "code": code, "grund": None}
                    if a["herkunft"] == "regel":
                        z["regel"][a["regel"]] = z["regel"].get(a["regel"], 0) + 1
                else:
                    u["partei"] = {"status": "unklar", "nr": None, "code": a["grund_code"],
                                   "grund": a["grund"] if a["grund_code"] == "urteil" else None}
                    z["grund"][a["grund_code"]] = z["grund"].get(a["grund_code"], 0) + 1
    return {"rollen": x["rollen"], "zahlen": z,
            "regeln": dict(REGEL_LABEL),
            "gruende": {k: URTEIL_LABEL if k == "urteil" else v for k, v in UNKLAR_GRUENDE.items()}}


# ---------------------------------------------------------------------------
# Formular text (for the B2 quote gate and the hand check of B1)
# ---------------------------------------------------------------------------
def _xml_text(data):
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return ""
    out = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in ("t", "delText") and el.text:
            out.append(el.text)
        elif tag in ("p", "tab", "br", "row", "si", "c"):
            out.append(" ")
    return "".join(out)


def formular_text(conn, form_id):
    """(text, quelle) of a Formular: the PDF text layer (pypdf, imported only
    here), the XML of a .docx/.xlsx, or for an eFormular the DVSH form
    definition it was built from. ('', reason) when the file has no readable
    text (.doc/.xls, a scanned PDF)."""
    r = conn.execute("SELECT source_file, file_type, title, service_id FROM form WHERE id=?", [form_id]).fetchone()
    if not r:
        return "", "Formular fehlt"
    sf, ft, title, sid = r
    if ft == "eformular" or not sf:
        teile = []
        for (fd,) in conn.execute("SELECT form_definitions FROM dvsh_service WHERE service_id=? "
                                  "AND form_definitions IS NOT NULL", [sid]):
            try:
                defs = json.loads(fd)
            except ValueError:
                continue
            passend = [x for x in defs if isinstance(x, dict) and (x.get("titel") or "")[:160] == title] or \
                [x for x in defs if isinstance(x, dict)]
            for x in passend:
                teile.append(json.dumps(x, ensure_ascii=False))
        txt = " ".join(_json_strings(json.loads(t)) for t in teile)
        return (txt, "DVSH-Formulardefinition") if txt.strip() else ("", "keine DVSH-Formulardefinition")
    pfad = os.path.join(ROOT, sf)
    ext = os.path.splitext(sf)[1].lower()
    if ext == ".pdf":
        try:
            import pypdf
        except ImportError:
            raise SystemExit("pypdf fehlt — mit /usr/local/bin/python3 ausführen")
        try:
            rd = pypdf.PdfReader(pfad)
            txt = "\n".join((pg.extract_text() or "") for pg in rd.pages)
        except Exception as ex:                     # a broken file is a reason, not a crash
            return "", f"PDF nicht lesbar: {type(ex).__name__}"
        # field labels of a fillable PDF are Formular text too (tooltips, field names)
        try:
            for f in (rd.get_fields() or {}).values():
                for k in ("/TU", "/T"):
                    if f.get(k):
                        txt += "\n" + str(f.get(k))
        except Exception:
            pass
        return (txt, "PDF-Text") if txt.strip() else ("", "PDF ohne Textebene (Scan)")
    if ext in (".docx", ".xlsx", ".xlsm"):
        import zipfile
        try:
            z = zipfile.ZipFile(pfad)
        except zipfile.BadZipFile:
            return "", "Datei nicht lesbar"
        namen = [n for n in z.namelist() if re.match(r"(word/(document|header\d*|footer\d*)\.xml|"
                                                      r"xl/sharedStrings\.xml|xl/worksheets/sheet\d+\.xml)$", n)]
        txt = " ".join(_xml_text(z.read(n)) for n in sorted(namen))
        return (txt, "Office-XML") if txt.strip() else ("", "Office-Datei ohne Text")
    return "", f"Dateiformat {ext} ohne lesbaren Text (Standardbibliothek)"


def _json_strings(x):
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        return " ".join(_json_strings(v) for v in x.values())
    if isinstance(x, list):
        return " ".join(_json_strings(v) for v in x)
    return ""


def zitat_norm(s):
    """Quote matching: folded, whitespace and line-break hyphens removed — a
    quote must occur in the Formular text, but not its PDF line breaks."""
    t = falten(s)
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)
    return re.sub(r"[\s_.:;,/()\[\]«»\"'*]+", " ", t).strip()


def zitat_im_text(zitat, text_norm):
    z = zitat_norm(zitat)
    return len(z) >= 3 and (z in text_norm or z.replace(" ", "") in text_norm.replace(" ", ""))


# ---------------------------------------------------------------------------
# Stage B2: input files and loader
# ---------------------------------------------------------------------------
B2_ANLEITUNG = (
    "Lies das Formular (Datei bzw. DVSH-Definition) und die Liste der Datenpunkte. Lege die Parteien fest, nach "
    "denen das Formular fragt — jede mit einer Rolle aus «rollen» (code), der Entität (natuerliche_person, "
    "organisation, sache, behoerde, gemischt = Person oder Organisation, offen) und einem Beleg: einem wörtlichen "
    "Zitat aus dem Formulartext, das die Partei nennt. Ordne dann JEDEN Datenpunkt genau einer Partei zu (partei = "
    "nr) oder setze «unklar» mit einem Grund. Nie raten: wenn das Formular nicht zeigt, wessen Angabe es ist, "
    "bleibt der Punkt unklar. Der Vorschlag der Stufe B1 ist eine Hilfe, kein Urteil; B1 trennt im Zweifel, fasse "
    "darum zu einer Partei zusammen, was im Formular dieselbe Person oder Organisation ist. Ist das Subjekt eines Felds "
    "gesetzt, muss die Entität der Partei dazu passen (gemischt deckt natuerliche_person und organisation).")


def pilot(conn, n=30, seed=20261004):
    """A stratified sample of Formulare for the B2 pilot: every file type (PDF,
    Word, Excel, eFormular) and every third of the B1 coverage (low, middle,
    high share of settled points) is represented in proportion, at least one
    Formular per non-empty stratum; Formulare without data points are left out.
    Seeded, so the same data give the same pilot."""
    abl = alle_ableiten(conn)
    typ = {r[0]: r[1] for r in conn.execute("SELECT id, file_type FROM form")}
    anteile = sorted((sum(1 for r in res if r["status"] == "zugeordnet") / len(L), fid)
                     for fid, (L, _, res) in abl.items() if L)
    drittel = {fid: min(2, i * 3 // len(anteile)) for i, (_, fid) in enumerate(anteile)}
    schichten = {}
    for fid in drittel:
        schichten.setdefault((typ.get(fid) or "?", drittel[fid]), []).append(fid)
    rnd = random.Random(seed)
    total = sum(len(v) for v in schichten.values())
    wahl = []
    for k in sorted(schichten):
        L = sorted(schichten[k])
        wahl += rnd.sample(L, max(1, round(n * len(L) / total)))
    rest = sorted(set(drittel) - set(wahl))
    while len(wahl) < n and rest:
        wahl.append(rest.pop(rnd.randrange(len(rest))))
    return sorted(wahl[:n]) if len(wahl) > n else sorted(wahl)


def vorbereiten(ziel, ids=None):
    """Write one in_<form id>.json per Formular: the Formular, the role list,
    the points with B1's proposal, the answer format and the instruction."""
    c = connect(DB_PATH)
    abl = alle_ableiten(c)
    forms = {r[0]: r for r in c.execute("SELECT id, title, source_file, file_type, file_hash FROM form")}
    rollen = [{"code": k, "label": v["label"], "entitaet": v["entitaet"], "erklaerung": v["erklaerung"]}
              for k, v in ROLLE.items()]
    try:
        import pypdf  # noqa: F401  (only to say whether the text can be checked here)
        pdf_ok = True
    except ImportError:
        pdf_ok = False
    os.makedirs(ziel, exist_ok=True)
    n = 0
    for fid in sorted(ids or abl):
        if fid not in abl:
            continue
        L, parteien, res = abl[fid]
        f = forms[fid]
        quelle = (formular_text(c, fid)[1] if (f[3] != "pdf" or pdf_ok) else "PDF-Text (mit pypdf prüfbar)")
        out = {
            "form_id": fid, "titel": f[1], "datei": f[2], "dateityp": f[3], "file_hash": f[4],
            "textquelle": quelle, "anleitung": B2_ANLEITUNG, "rollen": rollen,
            "vorschlag_parteien": [{"nr": pa["nr"], "rolle": pa["rolle"], "entitaet": pa["entitaet"],
                                    "bezeichnung": pa["bezeichnung"], "beleg_label": pa["beleg"]} for pa in parteien],
            "punkte": [{"key": _punkt_key(p), "feld": p["feld"], "teilfeld": p["teil_name"] if p["ist_teil"] else None,
                        "definition": p["definition"], "element": f"{p['std']} {p['el']}" if p["el"] else None,
                        "subjekt": p["subjekt"], "pflicht": p["pflicht"],
                        "vorschlag": ({"partei": r["partei_nr"], "regel": r["regel"]} if r["status"] == "zugeordnet"
                                      else {"unklar": _grund_text(r)})} for p, r in zip(L, res)],
            "antwortformat": {"form_id": fid, "file_hash": f[4],
                              "parteien": [{"nr": 1, "rolle": "<code>", "entitaet": "<entität>",
                                            "bezeichnung": "<wie das Formular sie nennt>", "mehrere": False,
                                            "beleg": "<wörtliches Zitat aus dem Formular>"}],
                              "punkte": [{"key": "<key>", "partei": 1, "beleg": "<optional: Zitat>"},
                                         {"key": "<key>", "unklar": "<Grund>"}]},
        }
        with open(os.path.join(ziel, f"in_{fid}.json"), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        n += 1
    c.close()
    print(f"vorbereiten: {n} Eingabedateien in {ziel}")


def urteil_pruefen(conn, u, text_cache, nach_form=None):
    """All gates for one B2 verdict; returns (errors, normalised verdict). Gates:
    the Formular exists and the verdict was made on its current file; every
    party has a role from the list, an entity type the role allows and a
    quote that occurs in the Formular text; every current data point is named
    exactly once (no point missing, none twice, none that does not exist);
    each point names a listed party or says why it stays unklar; a party's
    entity type agrees with the judged subjekt of every field it gets; no
    party is left without a point."""
    errs = []
    fid = u.get("form_id")
    f = conn.execute("SELECT id, file_hash, file_type FROM form WHERE id=?", [fid]).fetchone() if isinstance(fid, int) else None
    if not f:
        return [f"Formular {fid} gibt es nicht"], None
    if f[1] and u.get("file_hash") != f[1]:
        errs.append("file_hash weicht von der aktuellen Datei ab (Urteil über eine andere Fassung)")
    if fid not in text_cache:
        text_cache[fid] = formular_text(conn, fid)
    txt, quelle = text_cache[fid]
    if not txt:
        return errs + [f"kein prüfbarer Formulartext ({quelle}) — Belege nicht nachweisbar"], None
    tn = zitat_norm(txt)
    if nach_form is None:
        nach_form = {}
        for p in punkte(conn):
            nach_form.setdefault(p["form_id"], []).append(p)
    ps = nach_form.get(fid, [])
    subj = {_punkt_key(p): p["subjekt"] for p in ps}
    parteien = u.get("parteien")
    if not isinstance(parteien, list) or not parteien:
        return errs + ["keine Parteien"], None
    nrs = {}
    for x in parteien:
        if not isinstance(x, dict):
            errs.append("Partei ist kein Objekt"); continue
        nr, rolle, ent = x.get("nr"), x.get("rolle"), x.get("entitaet")
        if not isinstance(nr, int) or nr < 1 or nr in nrs:
            errs.append(f"Partei-Nummer ungültig oder doppelt: {nr}")
        if rolle not in ROLLE:
            errs.append(f"Partei {nr}: Rolle «{rolle}» steht nicht in der Liste")
        elif ent not in ENT_PARTEI:
            errs.append(f"Partei {nr}: Entität «{ent}» ungültig")
        elif ROLLE[rolle]["entitaet"] != "offen" and ent != ROLLE[rolle]["entitaet"]:
            errs.append(f"Partei {nr}: Entität {ent} passt nicht zur Rolle {rolle} ({ROLLE[rolle]['entitaet']})")
        if not (x.get("bezeichnung") or "").strip():
            errs.append(f"Partei {nr}: Bezeichnung fehlt")
        if not zitat_im_text(x.get("beleg") or "", tn):
            errs.append(f"Partei {nr}: Beleg «{(x.get('beleg') or '')[:60]}» steht nicht im Formulartext")
        nrs[nr] = x
    pk = u.get("punkte")
    if not isinstance(pk, list):
        return errs + ["punkte fehlt"], None
    keys = [x.get("key") for x in pk if isinstance(x, dict)]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        errs.append(f"Datenpunkte doppelt: {sorted(dup)[:5]}")
    fehlt, fremd = set(subj) - set(keys), set(keys) - set(subj)
    if fehlt:
        errs.append(f"{len(fehlt)} Datenpunkte fehlen: {sorted(fehlt)[:5]}")
    if fremd:
        errs.append(f"{len(fremd)} Schlüssel ohne Datenpunkt: {sorted(fremd)[:5]}")
    benutzt = set()
    for x in pk:
        if not isinstance(x, dict):
            continue
        k, pa = x.get("key"), x.get("partei")
        if pa is None:
            if len((x.get("unklar") or "").strip()) < 8:
                errs.append(f"{k}: weder Partei noch Grund für «unklar»")
            continue
        if pa not in nrs:
            errs.append(f"{k}: Partei {pa} ist nicht aufgeführt"); continue
        benutzt.add(pa)
        ent = nrs[pa].get("entitaet")
        if k in subj and not subjekt_passt(ent, subj[k]):
            errs.append(f"{k}: Partei {pa} ({ent}) widerspricht dem Subjekt des Felds ({subj[k]}) — "
                        "das Subjekt zuerst über die Zweitprüfung ändern")
        if x.get("beleg") and not zitat_im_text(x["beleg"], tn):
            errs.append(f"{k}: Beleg «{x['beleg'][:60]}» steht nicht im Formulartext")
    leer = set(nrs) - benutzt
    if leer:
        errs.append(f"Parteien ohne Datenpunkt: {sorted(leer)}")
    if errs:
        return errs, None
    norm = {"parteien": [{"nr": x["nr"], "rolle": x["rolle"], "entitaet": x["entitaet"],
                          "bezeichnung": x["bezeichnung"].strip(), "mehrere": bool(x.get("mehrere")),
                          "beleg": x["beleg"].strip()} for x in sorted(parteien, key=lambda y: y["nr"])],
            "punkte": [{"key": x["key"], "partei": x.get("partei"),
                        **({"unklar": x["unklar"].strip()} if x.get("partei") is None else {}),
                        **({"beleg": x["beleg"].strip()} if x.get("beleg") else {})}
                       for x in sorted(pk, key=lambda y: y["key"])]}
    return [], norm


def laden(quelle_dir):
    """Load B2 verdicts (out_<id>.json) through the gates, then derive again.
    A file with "zweitpruefung": {"urteil": "bestaetigt"|"geaendert", "grund": …}
    is a second review: «geaendert» carries the full corrected verdict (same
    gates); both are recorded in panel_review (kind 'partei')."""
    from datetime import date
    live = connect(DB_PATH)
    vorher = _dump(live)
    live.close()
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    cache, ok, abgelehnt, reviews = {}, 0, [], 0
    nach_form = {}
    for p in punkte(c):
        nach_form.setdefault(p["form_id"], []).append(p)
    for jf in sorted(glob.glob(os.path.join(quelle_dir, "out_*.json"))):
        name = os.path.basename(jf)
        try:
            u = json.load(open(jf, encoding="utf-8"))
        except ValueError as ex:
            abgelehnt.append((name, [f"kein JSON: {ex}"])); continue
        zp = u.get("zweitpruefung")
        if zp is not None:
            if not isinstance(zp, dict) or zp.get("urteil") not in ("bestaetigt", "geaendert") \
                    or len((zp.get("grund") or "").strip()) < 8:
                abgelehnt.append((name, ["Zweitprüfung: urteil bestaetigt|geaendert und ein Grund nötig"])); continue
            if not c.execute("SELECT 1 FROM partei_urteil WHERE form_id=?", [u.get("form_id")]).fetchone():
                abgelehnt.append((name, ["Zweitprüfung ohne geladenes Urteil der Stufe B2"])); continue
            if zp["urteil"] == "bestaetigt":
                c.execute("INSERT OR REPLACE INTO panel_review(kind,item_id,urteil,grund) VALUES('partei',?,?,?)",
                          [u["form_id"], "bestaetigt", zp["grund"].strip()])
                reviews += 1
                continue
        errs, norm = urteil_pruefen(c, u, cache, nach_form)
        if errs:
            abgelehnt.append((name, errs)); continue
        alt = c.execute("SELECT parteien, punkte, file_hash, geladen FROM partei_urteil WHERE form_id=?",
                        [u["form_id"]]).fetchone()
        pj = json.dumps(norm["parteien"], ensure_ascii=False)
        uj = json.dumps(norm["punkte"], ensure_ascii=False)
        # the same verdict again keeps its first load date (a second run changes nothing)
        geladen = alt[3] if alt and (alt[0], alt[1], alt[2]) == (pj, uj, u.get("file_hash")) else date.today().isoformat()
        c.execute("INSERT OR REPLACE INTO partei_urteil(form_id,file_hash,parteien,punkte,quelle,geladen) "
                  "VALUES(?,?,?,?,?,?)", [u["form_id"], u.get("file_hash"), pj, uj, name, geladen])
        if zp is not None:
            c.execute("INSERT OR REPLACE INTO panel_review(kind,item_id,urteil,grund) VALUES('partei',?,?,?)",
                      [u["form_id"], "geaendert", zp["grund"].strip()])
            reviews += 1
        ok += 1
    c.commit()
    if not ok and not reviews:
        c.close()
        os.remove(st)
        for name, e in abgelehnt:
            print(f"  ABGELEHNT {name}: " + " | ".join(e[:4]))
        print(f"laden: unverändert — kein Urteil übernommen, {len(abgelehnt)} abgelehnt")
        return
    rollen_rows, partei_rows, punkt_rows, veraltet = berechnen(c)
    schreiben(c, rollen_rows, partei_rows, punkt_rows)
    errs = vollstaendig(c) + _validieren(c)
    c.close()
    for name, e in abgelehnt:
        print(f"  ABGELEHNT {name}: " + " | ".join(e[:4]))
    if errs:
        os.remove(st)
        print("ABBRUCH — nichts geschrieben:", *errs[:8], sep="\n  ")
        sys.exit(1)
    msg = f"{ok} Urteile geprüft und übernommen, {reviews} Zweitprüfungen, {len(abgelehnt)} abgelehnt"
    if veraltet:
        msg += f"; {len(veraltet)} Urteile veraltet (Stufe B1 gilt): {veraltet[:10]}"
    c2 = connect(st)
    nachher = _dump(c2)
    c2.close()
    if nachher == vorher:
        os.remove(st)
        print("laden: unverändert — " + msg)
        return
    os.replace(st, DB_PATH)
    print("laden: geschrieben — " + msg)


# ---------------------------------------------------------------------------
# Report and sample (read-only)
# ---------------------------------------------------------------------------
EWR = {"eCH-0044", "eCH-0010", "eCH-0011", "eCH-0007", "eCH-0008"}      # the Einwohnerregister standards


def alle_ableiten(conn):
    """B1 for every Formular: {form_id: (points, parties, results)} (read-only)."""
    nach_form = {}
    for p in punkte(conn):
        nach_form.setdefault(p["form_id"], []).append(p)
    return {fid: (L,) + ableiten_formular(L) for fid, L in sorted(nach_form.items())}


def bericht(conn, als_json=None):
    """Coverage of stage B1 on the current data (read-only)."""
    abl = alle_ableiten(conn)
    z = {"punkte": 0, "zugeordnet": 0, "unklar": 0, "regel": {}, "grund": {}, "parteien": 0, "rollen_parteien": {},
         "rollen_punkte": {}}
    pro_form = []
    for fid, (L, parteien, res) in abl.items():
        n_zu = 0
        for p, r in zip(L, res):
            z["punkte"] += 1
            z[r["status"]] += 1
            if r["status"] == "zugeordnet":
                n_zu += 1
                z["regel"][r["regel"]] = z["regel"].get(r["regel"], 0) + 1
                z["rollen_punkte"][r["rolle"]] = z["rollen_punkte"].get(r["rolle"], 0) + 1
            else:
                z["grund"][r["grund_code"]] = z["grund"].get(r["grund_code"], 0) + 1
        for pa in parteien:
            z["rollen_parteien"][pa["rolle"]] = z["rollen_parteien"].get(pa["rolle"], 0) + 1
        z["parteien"] += len(parteien)
        pro_form.append({"form_id": fid, "titel": L[0]["titel"], "punkte": len(L), "zugeordnet": n_zu,
                         "unklar": len(L) - n_zu, "parteien": len(parteien),
                         "anteil": round(n_zu / len(L), 3) if L else None})
    anteile = sorted(f["anteil"] for f in pro_form)
    z["formulare"] = len(pro_form)
    z["formulare_ganz"] = sum(1 for f in pro_form if f["unklar"] == 0)
    z["formulare_ohne"] = sum(1 for f in pro_form if f["zugeordnet"] == 0)
    z["formulare_mit_partei"] = sum(1 for f in pro_form if f["parteien"])
    z["anteil_median"] = anteile[len(anteile) // 2] if anteile else None
    z.update(register_mehrdeutig(conn, abl))
    rt = rollentexte(conn)
    z["rollen_texte"] = {"n": len(rt), "zu_rolle": sum(1 for x in rt if x[2]),
                         "keine_partei": sum(1 for x in rt if not x[2] and x[3] == "keine_partei"),
                         "unklar": sum(1 for x in rt if not x[2] and x[3] != "keine_partei"),
                         "beispiele_keine_partei": [x[0] for x in rt if not x[2]][:25]}
    ab = lebenslagen_abgleich()
    z["lebenslagen_woerter"] = ({"n": len(LEBENSLAGEN_WOERTER), "ohne_zuordnung": ab[0], "nicht_mehr_im_schluessel": ab[1]}
                                if ab else "export_json.PARTY nicht gefunden")
    z["pro_formular"] = pro_form
    if als_json:
        with open(als_json, "w", encoding="utf-8") as fh:
            json.dump(z, fh, ensure_ascii=False, indent=1)
    return z


def register_mehrdeutig(conn, abl):
    """Today's prefill rule (export_llm.py, the same in flows.html): among a natural
    person's points of one Formular, an Einwohnerregister element that names more
    than one point — counting the composite's own element when its parts are
    points — fills none of them. How many of those points does B1 give a party,
    and how many does that make unique (same element, same party, no other
    point or composite of that party with the element)? And what happens to
    the «gemischt» person/address points (Person oder Firma), which are never
    prefilled?"""
    eigen = {}
    for fid, did, std, el in conn.execute(
            "SELECT d.form_id, d.id, e.standard, e.name FROM data_field d JOIN ech_element e ON e.id=d.ech_element_id "
            "WHERE d.subjekt='natuerliche_person' AND EXISTS (SELECT 1 FROM data_subfield s WHERE s.data_field_id=d.id)"):
        eigen.setdefault(fid, []).append((did, (std, el)))
    z = {"register_punkte": 0, "register_mehrdeutig": 0, "register_mehrdeutig_partei": 0,
         "register_mehrdeutig_eindeutig": 0, "register_mehrdeutig_eindeutig_gesuchsteller": 0,
         "register_mehrdeutig_eindeutig_andere": 0, "register_mehrdeutig_eindeutig_rollen": {},
         "gemischt": 0, "gemischt_partei": 0, "gemischt_rollen": {}}
    for fid, (L, parteien, res) in abl.items():
        seen = {}
        for p, r in zip(L, res):
            if p["el"] and p["subjekt"] == "natuerliche_person":
                seen.setdefault((p["std"], p["el"]), []).append((p, r))
        virt = {}
        for did, key in eigen.get(fid, []):
            virt.setdefault(key, []).append(did)
        # the party of a composite = the one party all its assigned parts share (else none)
        teil_partei = {}
        for p, r in zip(L, res):
            if p["ist_teil"]:
                teil_partei.setdefault(p["data_field_id"], set()).add(
                    r.get("partei_nr") if r["status"] == "zugeordnet" else None)
        for p, r in zip(L, res):
            if p["std"] in EWR and p["subjekt"] == "gemischt" and p["el"]:
                z["gemischt"] += 1
                if r["status"] == "zugeordnet":
                    z["gemischt_partei"] += 1
                    z["gemischt_rollen"][r["rolle"]] = z["gemischt_rollen"].get(r["rolle"], 0) + 1
            if not (p["el"] and p["std"] in EWR and p["subjekt"] == "natuerliche_person"):
                continue
            z["register_punkte"] += 1
            key = (p["std"], p["el"])
            if len(seen[key]) + len(virt.get(key, [])) <= 1:
                continue
            z["register_mehrdeutig"] += 1
            if r["status"] != "zugeordnet":
                continue
            z["register_mehrdeutig_partei"] += 1
            nr = r["partei_nr"]
            gleich = [q for q, s in seen[key] if s["status"] == "zugeordnet" and s.get("partei_nr") == nr]
            komp = [did for did in virt.get(key, []) if teil_partei.get(did) == {nr}]
            if len(gleich) == 1 and not komp:
                z["register_mehrdeutig_eindeutig"] += 1
                z["register_mehrdeutig_eindeutig_rollen"][r["rolle"]] = \
                    z["register_mehrdeutig_eindeutig_rollen"].get(r["rolle"], 0) + 1
                z["register_mehrdeutig_eindeutig_" + ("gesuchsteller" if r["rolle"] == "gesuchsteller"
                                                      else "andere")] += 1
    return z


def stichprobe(conn, n=30, seed=20261004):
    """n random settled assignments of stage B1 (seeded, reproducible), for the
    hand check against the Formular text."""
    zu = []
    for fid, (L, parteien, res) in alle_ableiten(conn).items():
        for p, r in zip(L, res):
            if r["status"] == "zugeordnet":
                zu.append((p, r, parteien[r["partei_nr"] - 1]))
    return random.Random(seed).sample(zu, min(n, len(zu)))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "bericht"
    if cmd == "ableiten":
        ableiten()
    elif cmd == "pruefen":
        c = connect(DB_PATH)
        e = pruefen(c) + (vollstaendig(c) if _hat(c, "datenpunkt_partei") else [])
        print("\n".join(e) if e else "Parteien-Schicht: in Ordnung")
        sys.exit(1 if e else 0)
    elif cmd == "bericht":
        c = connect(DB_PATH)
        out = argv[argv.index("--json") + 1] if "--json" in argv else None
        z = bericht(c, out)
        zz = {k: v for k, v in z.items() if k != "pro_formular"}
        print(json.dumps(zz, ensure_ascii=False, indent=1))
    elif cmd == "stichprobe":
        c = connect(DB_PATH)
        n = int(argv[2]) if len(argv) > 2 else 30
        seed = int(argv[3]) if len(argv) > 3 else 20261004
        for p, r, pa in stichprobe(c, n, seed):
            print(json.dumps({"form_id": p["form_id"], "titel": p["titel"][:70], "feld": p["feld"],
                              "teilfeld": p["teil_name"] if p["ist_teil"] else None, "element": p["el"],
                              "subjekt": p["subjekt"], "partei": pa["bezeichnung"], "rolle": pa["rolle"],
                              "regel": r["regel"], "beleg": r["beleg"]}, ensure_ascii=False))
    elif cmd == "vorbereiten":
        if "--pilot" in argv:
            c = connect(DB_PATH)
            ids = pilot(c, int(argv[argv.index("--pilot") + 1]) if len(argv) > argv.index("--pilot") + 1 else 30)
            c.close()
            print("Pilot (geschichtet nach Dateityp und Abdeckung durch B1):", ids)
        else:
            ids = [int(x) for x in argv[3:]] or None
        vorbereiten(argv[2], ids)
    elif cmd == "laden":
        laden(argv[2])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv)
