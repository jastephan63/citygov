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

DIV = {"pflicht": "Pflicht ↔ optional", "pflicht_uneinheitlich": "Pflicht uneinheitlich",
       "format": "Andere Form derselben Angabe", "codeliste": "Eigene Werte statt der offiziellen Codes",
       "element_offen": "Element im Standard offen", "standard_ohne_elemente": "Standard ohne Elementkatalog",
       "standard_entwurf": "Standard bei eCH in Arbeit", "standard_alt": "Standard nicht mehr in Kraft",
       "kein_standard": "Kein eCH-Standard",
       "ungeprueft": "Noch nicht geprüft"}
DIV_CLS = {k: "st-" + v for k, v in {"pflicht": "act", "pflicht_uneinheitlich": "dec", "format": "act", "codeliste": "act", "element_offen": "open", "standard_ohne_elemente": "ok", "standard_entwurf": "dec", "standard_alt": "open", "kein_standard": "dec", "ungeprueft": "open"}.items()}

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

BASIS_TYP = {"artikel": "Artikel belegt", "aufgabe": "aufgabennotwendig", "ohne": "ohne Grundlage",
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
TON_OF_ART_EARLY = {"bereinigung": "act", "entscheid": "dec", "recherche": "open"}
TODO_ART = {"recherche": "Recherche (Databank)", "entscheid": "Entscheid (Kanton)",
            "bereinigung": "Bereinigung (Dienststelle)"}
TODO_CATS = [
    ("ermitteln", "Rechtsgrundlage zu ermitteln", "b-unver", "recherche",
     "Für das Feld ist noch keine Rechtsgrundlage recherchiert — weder ein Artikel noch ein Befund "
     "«aufgabennotwendig». Eine Wissenslücke der Databank, keine Aussage über die Verwaltung."),
    ("offen", "Aufgabenbedarf offen", "b-unver", "entscheid",
     "Keine Norm nennt das Feld; ob die gesetzliche Aufgabe es zwingend braucht (KDSG Art. 4 Abs. 1 lit. b), "
     "konnte aus dem Formular allein nicht entschieden werden."),
    ("ohne", "Felder ohne Grundlage bereinigen", "b-over", "bereinigung",
     "Weder eine Norm noch die Aufgabe verlangt das Feld. Optionen: Feld streichen, oder die Zustimmung der "
     "Person einholen (KDSG Art. 4 Abs. 1 lit. c; bei ⛨-Feldern KDSG Art. 5 Abs. 1 lit. b) — ausdrücklich "
     "oder nach den Umständen unzweifelhaft vorausgesetzt; in der Praxis ausdrücklich einholen."),
    ("sensibel_art5", "Grundlage nach KDSG Art. 5 benennen", "b-sens", "recherche",
     "Eine besonders schützenswerte Angabe ist als aufgabennotwendig beurteilt; für solche Daten reicht die "
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
     "Das Formular verlangt mindestens drei besonders schützenswerte Datenfelder, oder mindestens die Hälfte "
     "seiner Datenfelder ist besonders schützenswert. Das ist ein berechneter Anhaltspunkt (vgl. KDSV § 6: "
     "Sammlung vieler besonders schützenswerter Personendaten). Ob eine Datenschutz-Folgenabschätzung nötig "
     "ist, ist noch nicht entschieden. Durchzuführen hat sie das verantwortliche öffentliche Organ "
     "(KDSG Art. 14b)."),
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
     "Dieselbe Angabe wird auf diesem Formular anders verlangt als auf den übrigen. Pflicht statt optional "
     "oder eine andere Form: das Formular angleichen oder die abweichende Rechtsgrundlage dokumentieren. "
     "Eigene Werte statt der offiziellen Codes: beim Austausch auf die eCH-Codes abbilden — im Formular "
     "darf der Klartext stehen bleiben."),
    ("kein_standard", "Kein geltender eCH-Standard", "b-unver", "entscheid",
     "Für diese Datenpunkte gibt es keinen eCH-Standard, oder er ist bei eCH erst in Arbeit. Der Kanton "
     "entscheidet, ob der kantonale Entwurf eSH gilt oder ob er bei eCH einen Standard beantragt."),
    ("divergenz_offen", "Pflicht uneinheitlich", "b-unver", "entscheid",
     "Dieselbe Angabe ist über die Formulare hinweg mal Pflicht, mal optional, ohne erkennbare Praxis — hier "
     "ist nicht ein Formular die Ausnahme, sondern es fehlt eine kantonale Festlegung."),
    ("begriff", "Bezeichnung angleichen oder Feld aufteilen", "b-over", "bereinigung",
     "Das Feld benennt eine Angabe anders als der einheitliche Begriff (Tab «Begriffe») oder bündelt mehrere "
     "Daten, die der Standard trennt — im Formular umbenennen bzw. aufteilen."),
    ("zuordnung", "eCH-Zuordnung korrigieren", "b-unver", "recherche",
     "Die Bezeichnung meint eine andere Angabe als das eCH-Element, dem die Databank das Feld zugeordnet hat "
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
# the badge class of a category follows its tone (who acts next), never a colour of its own
TODO_CATS = [(c[0], c[1], "st-" + TON_OF_ART_EARLY[c[3]], c[3], c[4]) for c in TODO_CATS]
TODO_BY = {c[0]: c for c in TODO_CATS}
# what n counts, per category (singular, plural)
EINHEIT = {
    "divergenz": ("Datenpunkt", "Datenpunkte"), "divergenz_offen": ("Datenpunkt", "Datenpunkte"),
    "kein_standard": ("Datenpunkt", "Datenpunkte"), "echalt": ("Datenpunkt", "Datenpunkte"),
    # a naming verdict sits on the atomic unit (a Teilfeld, or a Datenfeld without parts)
    "begriff": ("Datenpunkt", "Datenpunkte"), "zuordnung": ("Datenpunkt", "Datenpunkte"), "ech": ("Feld", "Felder"),
    "ermitteln": ("Feld", "Felder"), "offen": ("Feld", "Felder"), "ohne": ("Feld", "Felder"),
    "sensibel_art5": ("Feld", "Felder"), "dup": ("Formularpaar", "Formularpaare"),
}   # every other category counts Formulare


# ---- one status language -------------------------------------------------------
# The colour of every status says WHO has to act next. Four tones, used the same
# way on every page (CSS classes st-ok / st-act / st-dec / st-open):
TON = {
    "ok":   {"label": "geklärt", "farbe": "grün",
             "bedeutung": "Erledigt oder belegt — niemand muss etwas tun."},
    "act":  {"label": "Dienststelle handelt", "farbe": "rot",
             "bedeutung": "Die Dienststelle muss ihr Formular ändern (bereinigen, angleichen, ersetzen)."},
    "dec":  {"label": "Kanton entscheidet", "farbe": "amber",
             "bedeutung": "Es braucht einen Entscheid des Kantons (Datenschutz, Standard, Fristen)."},
    "open": {"label": "Databank recherchiert", "farbe": "grau",
             "bedeutung": "Noch nicht recherchiert oder belegt — eine Hausaufgabe der Databank, kein Befund über die Verwaltung."},
}
TON_OF_ART = {"bereinigung": "act", "entscheid": "dec", "recherche": "open"}

# per domain: code -> tone. A code missing here is shown grey (not yet settled).
TON_MAP = {
    # the legal question of a data field
    "basis": {"artikel": "ok", "aufgabe": "ok", "art5_offen": "open", "ohne": "act",
              "offen": "dec", "zu_ermitteln": "open"},
    # verification level of a citation
    "verif": {"verified": "ok", "quelle_pdf": "ok", "unverifiziert": "open"},
    # remedy of a Verfahren (rechtsmittel_status; absent status + a rule = confirmed)
    "rechtsmittel": {"bestaetigt": "ok", "kein_entscheid": "ok", "default_allgemein": "open", "beurteilt_offen": "open",
                     "nicht_beurteilt": "open", "entscheidart_offen": "open"},
    # eCH mapping of a data point
    "ech": {"element": "ok", "zuordnung_falsch": "open", "standard_ohne_elemente": "ok", "element_offen": "open", "ungeprueft": "open",
            "kein_standard": "dec", "standard_entwurf": "dec", "standard_alt": "open"},
    # standard divergences
    "div": {"pflicht": "act", "format": "act", "codeliste": "act", "pflicht_uneinheitlich": "dec",
            "element_offen": "open", "standard_ohne_elemente": "ok", "standard_entwurf": "dec", "standard_alt": "open",
            "kein_standard": "dec", "ungeprueft": "open"},
    # one datum, one name
    "begriff": {"vorschlag": "ok", "rolle": "ok", "variante": "act", "aufteilen": "act",
                "zuordnung": "open", "vorbehalt": "dec"},
    # currency of the Formular
    "check": {"aktuell": "ok", "veraltet": "act", "veraltet_verdacht": "act", "nicht_auffindbar": "act",
              "nicht_gefunden": "act", "faellig": "open", "nie": "open"},
    # register (Verzeichnis) items and cantonal decisions
    "dsfa": {"entschieden": "ok", "indiziert": "dec", "nicht_indiziert": "ok"},
    "schutzstufe": {"festgelegt": "ok", "fehlt": "dec"},
    "dup": {"entschieden": "ok", "offen": "dec"},
}

# ---- priority: what comes first on the board ------------------------------------
# The data standard is the core of the databank, so it leads. These are GAPS —
# work still to do — not findings of a risk or a breach. Independent of the tone:
# a grey (research) item can still come first.
STUFEN = [
    (1, "Datenstandard", "Dieselbe Angabe soll überall gleich verlangt, gleich benannt und nach eCH-Standard "
        "ausgetauscht werden: Element, Form, Werteliste, Bezeichnung."),
    (2, "Rechtsgrundlage", "Für jedes Datenfeld soll feststehen, worauf es sich stützt — belegte Norm oder "
        "Aufgabe; wo das noch fehlt, ist es eine Lücke."),
    (3, "Verfahren & Verzeichnis", "Was das Verzeichnis und die betroffene Person brauchen: Zweck, Empfänger, "
        "Rechtsmittel, Verfahrens-Ergebnis, DSFA-Entscheid."),
    (4, "Bestand & Aktualität", "Ist das Formular die geltende Fassung, gibt es Doppelungen, ist es vollständig erfasst?"),
]
STUFE_OF_CAT = {
    "divergenz": 1, "begriff": 1, "ech": 1, "zuordnung": 1, "echalt": 1, "divergenz_offen": 1, "kein_standard": 1,
    "ohne": 2, "offen": 2, "sensibel_art5": 2, "ermitteln": 2,
    "zweck": 3, "empf": 3, "rechtsmittel": 3, "rechtsmittel_default": 3, "entscheid_art": 3, "dsfa": 3,
    "dup": 4, "keine-felder": 4, "veraltet": 4, "pruefung_faellig": 4,
}
# order of the categories inside a tier (first = shown first)
CAT_ORDER = ["divergenz", "begriff", "ech", "zuordnung", "echalt", "divergenz_offen", "kein_standard",
             "ohne", "offen", "sensibel_art5", "ermitteln",
             "zweck", "empf", "dsfa", "rechtsmittel", "rechtsmittel_default", "entscheid_art",
             "veraltet", "dup", "keine-felder", "pruefung_faellig"]
# a short imperative per category for the «top 5 actions» of a Dienststelle
AKTION = {
    "ohne": "Felder ohne Grundlage streichen oder die Zustimmung einholen",
    "offen": "Klären, ob die Aufgabe diese Felder wirklich braucht",
    "dsfa": "Über eine Datenschutz-Folgenabschätzung entscheiden",
    "ech": "Datenfelder dem passenden eCH-Element zuordnen lassen",
    "sensibel_art5": "Grundlage nach KDSG Art. 5 für besonders schützenswerte Daten benennen",
    "divergenz": "Abweichung vom Datenstandard angleichen oder ihre Rechtsgrundlage dokumentieren",
    # the same category when only value lists differ: nothing on the form has to change
    "divergenz_codeliste": "Werte beim Austausch auf die eCH-Codes abbilden",
    "divergenz_offen": "Kantonal festlegen, ob die Angabe Pflicht ist",
    "kein_standard": "Festlegen, ob der kantonale Entwurf eSH für diese Daten gilt",
    "begriff": "Bezeichnungen umstellen oder Felder aufteilen",
    "dup": "Entscheiden, ob ähnliche Formulare zusammengelegt werden",
    "veraltet": "Prüfen, welche Fassung des Formulars gilt, und ersetzen",
    # not a category of form.handlungsbedarf: the ISV decision for every field at once (#kanton)
    "schutzstufe": "Schutzbedarf nach den Schutzzielen von ISV Art. 5 festlegen und die Daten nach ISV Art. 6 "
                   "klassifizieren (Verfügbarkeit, Vertraulichkeit, Integrität, Nachvollziehbarkeit, "
                   "Beweistauglichkeit)",
}


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
            "todo_art": TODO_ART, "ton": TON, "ton_of_art": TON_OF_ART, "ton_map": TON_MAP,
            "stufen": [list(x) for x in STUFEN], "stufe_of_cat": STUFE_OF_CAT, "cat_order": CAT_ORDER, "aktion": AKTION, "einheit": EINHEIT,
            "todo_cats": [list(c) for c in TODO_CATS]}
