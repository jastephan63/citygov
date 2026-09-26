"""German labels for every enumerated value the databank stores — ONE place.

The dashboard (scripts/build_dashboard.py, via data_export.json -> DATA.labels),
the dossiers (scripts/export_dossiers.py) and the LLM export read the same
dicts, so a code such as beilage.halter = 'kanton_andere' can never print raw on
one surface and translated on another. A code that is missing here is a bug:
render_label() marks it visibly (⟨code⟩) instead of hiding it.

Keys mirror the DB vocabularies (schema.sql). Keep the wording Swiss-German
(ss, not ß) and consistent with the terms the UI introduces on the home page:
Service · Formular · Dienststelle · Datenfeld · Teilfeld · Datenpunkt.
"""

DFTYPE = {"text": "Text", "date": "Datumsangabe", "number": "Zahl", "money": "Betrag",
          "boolean": "Ja/Nein", "enum": "Auswahl", "multiselect": "Mehrfachauswahl",
          "composite": "Zusammengesetzt", "attachment": "Beilage", "signature": "Unterschrift"}

SENS = {"gesundheit": "Gesundheit", "religion_weltanschauung": "Religion/Weltanschauung",
        "politik": "Politische oder gewerkschaftliche Ansichten", "ethnie_herkunft": "Ethnische Herkunft",
        "genetik_biometrie": "Genetik/Biometrie", "strafen_verfahren": "Verfolgungen und Sanktionen",
        "sozialhilfe": "Massnahmen der sozialen Hilfe"}

OUTCOME = {"bewilligung": "Bewilligung", "verfuegung": "Verfügung", "bestaetigung": "Bestätigung/Ausweis",
           "registereintrag": "Registereintrag", "auszahlung": "Auszahlung",
           "kein_entscheid": "kein Entscheid (Meldung)", "unbekannt": "aus dem DVSH-Text nicht belegbar"}

RM = {"einsprache": "Einsprache", "rekurs": "Rekurs", "beschwerde": "Beschwerde",
      "verwaltungsgerichtsbeschwerde": "Verwaltungsgerichtsbeschwerde", "verweis": "Rechtsmittel nach Verweis"}

# form_outcome.rechtsmittel_status (export_json.py): why a form shows the remedy it shows
RM_STATUS = {"beurteilt_offen": "geprüft, aus dem zitierten Recht nicht bestimmbar",
             "nicht_beurteilt": "noch nicht geprüft",
             "default_allgemein": "allgemeine Regel des VRG — noch ohne Prüfvermerk",
             "entscheidart_offen": "Verfahrens-Ergebnis nicht belegt — Rechtsmittelfrage noch nicht erreicht"}

HALTER = {"privat": "nur bei der Person", "einwohnerregister": "Einwohnerregister",
          "handelsregister": "Handelsregister", "betreibungsregister": "Betreibungsregister",
          "strafregister": "Strafregister", "steuerverwaltung": "Steuerverwaltung", "grundbuch": "Grundbuch",
          "kanton_andere": "andere kantonale Stelle", "bund": "Bund", "unbekannt": "Halter unbekannt"}

OBLIG = {"zwingend": "zwingend", "bedingt": "bedingt", "fakultativ": "fakultativ", "unbekannt": "unbekannt"}

CHAN = {"online_formular": "Online-Formular", "pdf": "PDF-Einreichung", "schalter": "Schalter",
        "unbekannt": "Kanal unbekannt"}

SIG = {"handschriftlich": "handschriftlich", "keine": "keine", "sig_widget": "digitale Signatur vorgesehen",
       "unbekannt": "unbekannt"}

# dvsh_service.endpoint_typ — the channel the modeller records for a service
ENDPOINT = {"eformular": "eFormular (Online-Service)", "formular_pdf": "PDF-Formular", "email": "E-Mail",
            "telefon": "Telefon", "externer_link": "externer Link", "vor_ort": "vor Ort"}

DVSH_STATUS = {"uebergeben": "übergeben"}

MODE = {"systematisch": "systematisch", "auf_anfrage": "auf Anfrage"}

DIV = {"pflicht": "Pflicht ↔ optional", "pflicht_uneinheitlich": "Pflicht im Korpus ungeklärt",
       "format": "Andere Form desselben Datums", "codeliste": "Eigene Werte statt der offiziellen Codes",
       "element_offen": "Element im Standard offen", "standard_ohne_elemente": "Standard ohne Elementkatalog",
       "standard_entwurf": "Standard nicht in Kraft", "kein_standard": "Kein eCH-Standard",
       "ungeprueft": "Noch nicht geprüft"}
DIV_CLS = {"pflicht": "b-over", "pflicht_uneinheitlich": "b-unver", "format": "b-over", "codeliste": "b-over",
           "element_offen": "b-unver", "standard_ohne_elemente": "b-unver", "standard_entwurf": "b-unver",
           "kein_standard": "b-unver", "ungeprueft": "b-unver"}

CHECK = {"aktuell": "aktuell", "veraltet": "neuere Fassung online", "veraltet_verdacht": "evtl. veraltet",
         "nicht_auffindbar": "nicht mehr online", "nicht_gefunden": "online nicht gefunden"}

JUR = {"federal": "Bund", "cantonal": "Kanton", "communal": "Gemeinde", "interkantonal": "interkantonal"}

ASPECT = {"erhebung": "Erhebung", "bearbeitung": "Bearbeitung", "speicherung": "Speicherung",
          "aufbewahrung": "Aufbewahrung", "loeschung": "Löschung", "archivierung": "Archivierung",
          "bekanntgabe": "Bekanntgabe", "sicherheit": "Sicherheit", "betroffenenrechte": "Betroffenenrechte"}

SCOPE = {"allgemein": "allgemein", "besonders_schuetzenswert": "besonders schützenswert", "sektoral": "sektoral"}

KAT = {"privat": "Privatpersonen", "unternehmen": "Unternehmen"}

# retention_term.trigger_event / retention_decision.trigger_event: what starts the clock
TRIGGER = {"unbestimmt": "Beginn der Frist im Erlass nicht bestimmt",
           "abschluss_behandlung": "nach Abschluss der Behandlung",
           "letzte_bearbeitung": "nach der letzten Bearbeitung",
           "ablauf_mindestaufbewahrungsfrist": "nach Ablauf der Mindestaufbewahrungsfrist",
           "ablauf_vernichtungsfrist": "nach Ablauf der Vernichtungsfrist",
           "aufhebung_oder_anordnung": "nach Aufhebung oder Anordnung",
           "beendigung_datenbearbeitung": "nach Beendigung der Datenbearbeitung",
           "bezeichnung_archivwuerdig": "sobald als archivwürdig bezeichnet",
           "bezeichnung_nicht_archivwuerdig": "sobald als nicht archivwürdig bezeichnet",
           "ende_registraturperiode": "nach Ende der Registraturperiode",
           "loeschung_kantonales_system": "nach Löschung im kantonalen System",
           "meldung_edoeb": "ab der Meldung an den EDÖB",
           "nicht_mehr_benoetigt": "sobald nicht mehr benötigt",
           "nicht_mehr_erforderlich": "sobald nicht mehr erforderlich",
           "nicht_mehr_staendig_benoetigt": "sobald nicht mehr ständig benötigt",
           "nichtuebernahme_staatsarchiv": "nach Nichtübernahme durch das Staatsarchiv",
           "verlangen_betroffene_person": "auf Verlangen der betroffenen Person",
           "vernichtung_waffe": "nach Vernichtung der Waffe",
           "vertragsende": "nach Vertragsende",
           "wegfall_oeffentliches_interesse": "nach Wegfall des öffentlichen Interesses",
           "zustimmung_bundesarchiv": "nach Zustimmung des Bundesarchivs"}

DISPOSITION = {"vernichten": "vernichten", "anonymisieren": "anonymisieren",
               "anbieten_staatsarchiv": "dem Staatsarchiv anbieten", "loeschen_vermerken": "löschen und vermerken"}

MINMAX = {"min": "mindestens", "max": "höchstens", "exakt": "genau"}

BASIS_TYP = {"artikel": "Artikel belegt", "aufgabe": "aufgabennotwendig", "ohne": "Over-collection",
             "offen": "Aufgabenbedarf offen"}

SUBJEKT = {"natuerliche_person": "natürliche Person", "organisation": "Organisation", "sache": "Sache",
           "behoerde": "Behörde", "gemischt": "gemischt"}

BEGRIFF_KLASSE = {"vorschlag": "Vorschlag", "variante": "angleichen", "rolle": "Rolle",
                  "pruefen": "prüfen (Feld aufteilen oder eCH-Zuordnung korrigieren)",
                  "aufteilen": "Feld aufteilen", "zuordnung": "eCH-Zuordnung korrigieren"}

ESH_STATUS = {"entwurf": "Entwurf"}

# formflow node types (flows.html)
NODE_TYP = {"choice": "Auswahl", "multiselect": "Mehrfachauswahl", "text": "Text", "number": "Zahl",
            "date": "Datum", "form": "Formularblock", "confirm": "Bestätigung", "roster": "Liste",
            "doc_scan": "Dokument", "scan": "Dokument", "note": "Hinweis"}

# law.jurisdiction_level as the LEVEL OF LAW a decision rests on (sentence form),
# next to JUR (the short «Bund/Kanton/Gemeinde» chip)
EBENE = {"federal": "Bundesrecht", "cantonal": "kantonales Recht", "communal": "kommunales Recht",
         "interkantonal": "interkantonales Recht"}

# Handlungsbedarf: category -> (label, badge class, kind, meaning). The RULES that
# emit an item live in export_json.py (fm['handlungsbedarf']); this is only the wording.
TODO_ART = {"recherche": "Recherche (Databank)", "entscheid": "Entscheid (Kanton)",
            "bereinigung": "Bereinigung (Dienststelle)"}
TODO_CATS = [
    ("ermitteln", "Rechtsgrundlage zu ermitteln", "b-unver", "recherche",
     "Für das Feld ist noch keine Rechtsgrundlage recherchiert — weder ein Artikel noch ein Befund "
     "«aufgabennotwendig». Eine Wissenslücke der Databank, kein festgestellter Verstoss."),
    ("offen", "Aufgabenbedarf offen", "b-unver", "entscheid",
     "Keine Norm nennt das Feld; ob die gesetzliche Aufgabe es zwingend braucht (KDSG Art. 4 Abs. 1 lit. b), "
     "konnte aus dem Formular allein nicht entschieden werden."),
    ("ohne", "Over-collection bereinigen", "b-over", "bereinigung",
     "Weder eine Norm noch die Aufgabe verlangt das Feld. Optionen: Feld streichen, oder die Zustimmung der "
     "Person einholen (KDSG Art. 4 Abs. 1 lit. c; bei ⛨-Feldern KDSG Art. 5 Abs. 1 lit. b) — ausdrücklich "
     "oder nach den Umständen unzweifelhaft vorausgesetzt; in der Praxis ausdrücklich einholen."),
    ("sensibel_art5", "Grundlage nach KDSG Art. 5 benennen", "b-sens", "recherche",
     "Ein besonders schützenswertes Datum ist als aufgabennotwendig beurteilt; für solche Daten reicht die "
     "Aufgabe allein nicht — es braucht ein formelles Gesetz, das die Aufgabe klar umschreibt (KDSG Art. 5 "
     "Abs. 1 lit. a), oder die Zustimmung der Person — ausdrücklich oder nach den Umständen unzweifelhaft "
     "vorausgesetzt (lit. b). Diese Grundlage ist noch nicht benannt."),
    ("zweck", "Zweck nicht erfasst", "b-unver", "recherche",
     "Der Bearbeitungszweck — Kernangabe jedes Verzeichnisses (Struktur nach KDSG Art. 17b Abs. 2) — ist für "
     "dieses Formular noch nicht festgehalten."),
    ("empf", "Empfänger nicht dokumentiert", "b-unver", "recherche",
     "Keine belegte Bekanntgabe erfasst. Entweder es gibt keine (dann ist genau das festzuhalten) oder sie ist "
     "noch nicht mit Artikel dokumentiert."),
    ("dsfa", "DSFA-Entscheid offen", "b-sens", "entscheid",
     "Die berechnete Triage zeigt eine hohe Dichte besonders schützenswerter Felder; ob eine "
     "Datenschutz-Folgenabschätzung (KDSG Art. 14b) nötig ist, hat der Kanton noch nicht entschieden."),
    ("ech", "eCH-Zuordnung offen", "b-unver", "recherche",
     "Das Feld ist noch nicht gegen den eCH-Katalog geprüft, oder es ist nur der Standard, nicht das konkrete "
     "XML-Element bestimmt (nur bei Standards, die einen Elementkatalog haben)."),
    ("echalt", "eCH-Standard nicht in Kraft", "b-over", "recherche",
     "Der zugeordnete eCH-Standard ist aufgehoben, abgelöst oder sistiert — die Zuordnung ist durch den "
     "Nachfolger zu ersetzen."),
    ("veraltet", "Formular-Fassung prüfen", "b-over", "bereinigung",
     "Die Online-Prüfung meldet eine neuere Fassung, einen Verdacht darauf, oder das Formular wird online "
     "nicht mehr angeboten."),
    ("pruefung_faellig", "Online-Prüfung fällig", "b-unver", "recherche",
     "Die letzte Prüfung der Online-Fassung liegt hinter der Wiedervorlage (oder hat nie stattgefunden); ob "
     "die Kopie in der Databank noch die aktuelle Fassung ist, ist unbekannt — kein Befund, eine Lücke."),
    ("dup", "Duplikat-Verdacht unentschieden", "b-unver", "entscheid",
     "Ein anderes Formular verlangt einen sehr ähnlichen Feldsatz. Ob die beiden zusammengelegt werden "
     "sollen, ist nicht beurteilt."),
    ("keine-felder", "Datenfeld-Schicht fehlt", "b-unver", "recherche",
     "Für dieses Formular sind noch keine Datenfelder modelliert — alle anderen Prüfungen sind blind."),
    ("divergenz", "Standard-Divergenz angleichen", "b-over", "bereinigung",
     "Dasselbe Datum wird auf diesem Formular anders verlangt als auf den übrigen (Pflicht statt optional, "
     "andere Form, eigene Werte statt der offiziellen Codes). Entweder das Formular angleichen oder die "
     "abweichende Rechtsgrundlage dokumentieren."),
    ("divergenz_offen", "Pflicht im Korpus ungeklärt", "b-unver", "entscheid",
     "Dasselbe Datum ist über die Formulare hinweg mal Pflicht, mal optional, ohne erkennbare Praxis — hier "
     "ist nicht ein Formular die Ausnahme, sondern es fehlt eine kantonale Festlegung."),
    ("begriff", "Bezeichnung angleichen", "b-over", "bereinigung",
     "Das Feld benennt ein Datum anders als der einheitliche Begriff (Tab «Begriffe») oder bündelt mehrere "
     "Daten, die der Standard trennt — im Formular umbenennen bzw. aufteilen."),
    ("zuordnung", "eCH-Zuordnung korrigieren", "b-unver", "recherche",
     "Die Bezeichnung meint ein anderes Datum als das eCH-Element, dem die Databank das Feld zugeordnet hat "
     "— ein Fehler der Databank, nicht des Formulars."),
    ("rechtsmittel", "Rechtsmittel nicht bestimmt", "b-unver", "recherche",
     "Das Verfahren endet mit einem anfechtbaren Entscheid, aber weder eine Spezialnorm noch die allgemeine "
     "VRG-Regel konnte belegt zugeordnet werden (z. B. Registerverfahren nach Bundesrecht)."),
    ("rechtsmittel_default", "Rechtsmittel ohne Prüfvermerk", "b-unver", "recherche",
     "Das Formular zeigt die allgemeine Regel des VRG als Rückfall, ohne dass ein Prüfvermerk bestätigt hat, "
     "dass kein Fachgesetz vorgeht. Die Aussage ist die beste belegte, aber noch nicht die geprüfte."),
    ("entscheid_art", "Verfahrens-Ergebnis nicht belegt", "b-unver", "recherche",
     "Was das Verfahren zurückgibt (Bewilligung, Verfügung, Eintrag …), liess sich aus dem DVSH-Ablauftext "
     "nicht belegen — bis das feststeht, ist auch die Rechtsmittelfrage nicht erreicht."),
]
TODO_BY = {c[0]: c for c in TODO_CATS}


def pl(n, singular, plural):
    """'1 Regel' / '2 Regeln' — never «1 Regeln»."""
    return f"{n} {singular if n == 1 else plural}"


def fmt_date(s):
    """ISO date (or datetime) -> dd.mm.yyyy for readers; anything else unchanged."""
    import re
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(s or ""))
    return f"{m[3]}.{m[2]}.{m[1]}" if m else (s or "")


def render_label(mapping, code, missing="⟨{code}⟩"):
    """A code without a label is shown as ⟨code⟩ — visible, never silently raw."""
    if code is None or code == "":
        return ""
    return mapping.get(code) or missing.format(code=code)


def as_export():
    """The dicts as one JSON-able object (data_export.json -> DATA.labels)."""
    return {"dftype": DFTYPE, "sens": SENS, "outcome": OUTCOME, "rm": RM, "rm_status": RM_STATUS,
            "halter": HALTER, "oblig": OBLIG, "chan": CHAN, "sig": SIG, "endpoint": ENDPOINT,
            "dvsh_status": DVSH_STATUS, "mode": MODE, "div": DIV, "div_cls": DIV_CLS, "check": CHECK,
            "jur": JUR, "aspect": ASPECT, "scope": SCOPE, "kat": KAT, "trigger": TRIGGER,
            "disposition": DISPOSITION, "minmax": MINMAX, "basis_typ": BASIS_TYP, "subjekt": SUBJEKT,
            "begriff_klasse": BEGRIFF_KLASSE, "esh_status": ESH_STATUS, "ebene": EBENE, "node_typ": NODE_TYP,
            "todo_art": TODO_ART,
            "todo_cats": [list(c) for c in TODO_CATS]}
