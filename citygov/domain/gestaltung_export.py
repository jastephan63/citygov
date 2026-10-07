#!/usr/bin/env python3
"""Comparison layer of the «Gestaltung»: how each Formular looks and is
presented, held against the other Formulare. The facts are measured elsewhere
(table form_gestaltung, written by scan_gestaltung.py); this module turns them
into what the pages show — per Formular one verdict per Merkmal, and one
overview for the canton. It measures nothing, opens no Formular file and
writes nothing.

    berechne(conn, forms, services, dienststellen) -> (per_form, overview)
    pruefen(per_form, overview, forms, dienststellen, profile)      the invariants

    python3 scripts/gestaltung_export.py              # the overview as a table
    python3 scripts/gestaltung_export.py --form 37    # one Formular, every Merkmal
    python3 scripts/gestaltung_export.py --json       # both results as JSON
    python3 scripts/gestaltung_export.py --selbsttest # every invariant fires on tampered copies
    (the entry point is citygov/export/gestaltung_export_cli.py: it builds the export in memory)

Standard library only, and nothing here imports pypdf, directly or through
another module: gestaltung_text.py (standard library only) is the one
measuring module that is imported — it holds every notion that the measurement
and this layer share (schriftgruppe, ist_blass, person_im_titel, the fixed
parts H_… of the `hinweise` sentences, the key of the measurement's date).
gestaltung_pdf.py and gestaltung_office.py are NOT imported — the plain build
runs under a Python without pypdf.

The owner's rule for every reader text: describe what differs, never tell an
office to change its Formular («I do not want to change any of the Formulare,
just identify points that are inconsistent»). Open points are «Lücken». The
figures of this layer stay on their own page: they never enter «offene
Punkte» or the Handlungsbedarf of the data standard.

The hook in export_json.build() (three lines after uebersichten(); the page
#gestaltung of build_dashboard.py draws what it returns):
    gest, gestaltung = gestaltung_export.berechne(conn, forms, services, dienststellen_uebersicht)
    for fm in forms: fm["gestaltung"] = gest[fm["id"]]
    data["gestaltung"] = gestaltung
The vocabulary below (URTEIL, TON, ART, GRUPPEN, MERKMALE, MESSART, ENTSCHEID,
KENNZAHL) is written as plain constants so that it can move into labels.py
unchanged. labels.TON["act"] says «Die Dienststelle muss ihr Formular ändern»:
that sentence is NOT this layer's — its page shows gestaltung.labels.ton.

Input
  conn           read for table form_gestaltung (form_id, messart, methode,
                 profil) and for the one row of table meta that holds the day
                 of the measurement. A databank without table form_gestaltung
                 has no measured Formular: every Formular with a file is then
                 «noch nicht gemessen». The profiles must be those of method
                 'gestaltung-2' or later (farben[].nur_kopf,
                 barrierefrei.text_lesbar / .sprache_passt): an older row
                 stops the export with a sentence that says so.
  forms          export_json's forms: id, source_file, file_type (title for the
                 command line only). A Formular without source_file is an
                 eFormular.
  services       not read. It stays in the signature so that the hook passes
                 what export_json.py holds. Whose Formular it is, is answered
                 once, in export_json.uebersichten(), and read here from the
                 next argument.
  dienststellen  export_json's dienststellen_uebersicht: slug, name, formulare
                 (form ids). The slug and the Dienststelle of a Formular have
                 no second definition here.

The yardstick is the PRACTICE of the measured Formulare — the canton's
corporate design manual is not in the repository. A value shared by at least
two thirds (PRAXIS_SCHWELLE, exact fraction) of the Formulare for which a
Merkmal is measured is the practice, provided at least PRAXIS_MIN Formulare
are measured: those Formulare «entspricht», the others «weicht_ab». Without
such a value nobody is the outlier: every measured Formular gets the neutral
«uneinheitlich», and the Merkmal carries ONE open decision of the canton. The
databank does not know what the canton has laid down: the text of a decision
says that no rule lies before the DATABANK and that the Formulare show none —
never that «nothing is laid down».

Output — per Formular (compact; to be stored as forms[].gestaltung)
  {"messart", "n": {"act", "betroffen", "dec", "open"}, "merkmale": [{"k", "u",
  "w", "p", "d"}]}; an eFormular: {"messart": null, "entfaellt": true}.
  k Merkmal, u verdict key, w the value as shown, p the practice value (only
  with «entspricht»/«weicht_ab»), d a LIST of detail sentences or null.
Output — overview (to be stored as top-level «gestaltung»): stand, methode,
  bestand, gruppen, merkmale, kennzahlen, entscheide, dienststellen, grenzen,
  labels — see _uebersicht().

Judgements the specification leaves open (each decided conservatively)
  * Eleven verdict keys, not ten: «kein_hinweis» is a Merkmal that applies,
    is measured and gives nothing to remark (one typeface, no fax number, less
    than 5 % small text). It is counted in the overview and, like «entfaellt»,
    left out of the per-Formular list.
  * Per Formular, n.act counts «weicht_ab» + «luecke», n.open «nicht_messbar»
    + «nicht_gemessen», n.betroffen only «betroffen», and n.dec the Merkmale of
    the Formular that wait for the canton: «uneinheitlich» + «betroffen» —
    exactly the entscheide whose lists name the Formular (invariant 3), so that
    the summary of a Formular says as many as its rows show. The open point
    stays the canton's, once per Merkmal: on a Formular it has no colour.
  * The five keys k, u, w, p, d are always present (null when empty); d is
    always a list when it holds something — never a bare string.
  * A row with messart 'nicht_messbar' (.doc, .xls) and a Formular with a file
    but without a row get «nicht_messbar» / «nicht_gemessen» for every Merkmal
    that its file type can have, also for the conditional ones (phone
    explanation, page numbers, field descriptions): whether they apply is not
    known. A Merkmal that the file type cannot have is «entfaellt».
  * A scan (messart 'pdf_bild') is judged wherever the file carries the fact
    (tags, language, title, field descriptions, text layer, page format) and
    is «nicht_messbar» for everything read from its text.
  * schrift compares typefaces without their cut (gestaltung_text.
    schriftgruppe); the family is shown as measured. When the main font sets
    less than two thirds of the characters, the shares stand in the detail
    (an annex in another typeface can outvote the form itself); groesse does
    the same when the second size sets at least a third.
  * schriftfamilien counts what profil.n_schriftfamilien counts (families
    with at least 2 % of the characters, no symbol fonts), by typeface. The
    stored count and the list must agree.
  * akzentfarbe: the value is the colour family of profil.akzent; the
    threshold AKZENT_MIN applies to the gewicht of ALL colours of that family
    together (the measurement picks the accent by the same sum). A family
    below it is «keine Akzentfarbe» with a remark that names it. Link colours,
    field colours and a head mark (a drawn logo) are never an accent — the
    measurement keeps them apart; where a Formular without accent shows them,
    the remark says so. The detail says WHAT is coloured (areas or lines,
    text, or both), a pale tint is shown as «(blass)», and a PDF whose first
    page carries an image gets the remark that its colours are not measured.
    Coloured text stays part of the accent: a Formular whose headings are set
    in a colour has one. Word and Excel files are outside the comparison:
    with an accent they get a «hinweis» that names it, without one
    «kein_hinweis».
  * farbvielfalt is a fact about the one Formular and is stated for every
    file type (the reader text says that one filled cell is enough in Office
    files).
  * kleinschrift: below KLEIN_ANTEIL a Formular gets a «hinweis» when its
    smallest size is below KLEIN_WINZIG (very small print, but little of it).
  * eingebettet names the fonts that are not embedded («Arial nicht
    eingebettet») — read from the sentence of the measurement that lists them.
  * bf_sprache: the language is folded («DE-CH» = «de-CH») for the
    distribution and shown as declared. «Does not fit the text» is
    profil.barrierefrei.sprache_passt = false.
  * bf_titel: the stored title is quoted for 'generisch' and 'ohne_bezug' —
    unless it looks like the name of a person (gestaltung_text.
    person_im_titel): then the detail says so and quotes nothing. The stored
    form of an e-mail address («…@domain») is shown as «[E-Mail-Adresse]»: no
    exported string may carry an «@». A profil without titel_art (no name of
    the Formular was passed to the measurement) is «nicht_messbar».
  * bf_feldnamen applies to PDFs with at least one fillable field.
  * bf_textebene: a PDF whose text is there but stored unreadably
    (barrierefrei.text_lesbar = false) is a Lücke «Text nicht lesbar
    abgelegt», like a scan without a text layer: neither a screen reader nor
    the search gets words from it.
  * tel_erklaerung and tel_format look at every printed number, fax numbers
    included. The weakest number decides: 'ohne' (a bare number) is a Lücke;
    'bezeichnung' («Tel. 052 …» with no office named in the text beside it)
    is a «hinweis», NOT a Lücke — the specification called it one, but every
    such number of the corpus stands in a letterhead whose office is named in
    a logo, which the measurement cannot read: a reader sees whose number it
    is. The quote («kontext») is exported for 'bezeichnung' and 'ohne' only.
  * stand_angabe: the initials of an author behind the mark («…/MG») are not
    quoted.
  * Text that the file stores unreadably (two Formulare): what the text
    detectors FOUND there stands (an unexplained number, a fax number, a
    personal mailbox, an edition mark, page numbers, a full sender); what they
    did not find is «nicht_messbar», never «fehlt» — nothing found is not the
    same as not there.
  * seitenzahlen applies to PDF and Word: one page is «entfaellt»
    («einseitig»), an Excel file is «entfaellt» (how many pages it prints is
    decided at printing), an unknown page count of a Word file is
    «nicht_messbar».
  * absender: when the databank knows no Dienststelle for the Formular the
    measurement could not look for one: «nicht_messbar».
  * kleinschrift carries the decision «Mindest-Schriftgrösse» as soon as one
    Formular is «betroffen».
  * A praxis Merkmal with fewer than PRAXIS_MIN measured Formulare has no
    practice; it carries a decision as soon as one Formular is measured. A
    decision whose commonest value holds at least KNAPP says how close it is.
  * entscheide[].verteilung lists the Formulare by value (form ids); for
    kleinschrift only the bands that are «betroffen».
  * overview.dienststellen has one entry per entry of the input, in its
    order, also for a Dienststelle without Formulare; n.act is split into
    n.abweichungen («weicht_ab») and n.luecken («luecke»); top = the TOP pairs
    (Merkmal, verdict) with the most «act» verdicts, each with its verdict u;
    akzente counts accent families of PDFs only; act_je_formular puts the count
    in relation to the Formulare whose content could be measured — n_gemessen
    minus n_nicht_messbar (a file in an old format has a row but no measured
    Merkmal).
  * kennzahlen: formulare_mit_luecke counts Formulare with a «luecke»,
    formulare_mit_abweichung those with a «weicht_ab», formulare_mit_act
    those with either. Nearly every Formular has one: the figure says little.
  * stand is the day scan_gestaltung.py wrote into table meta
    (gestaltung_text.META_STAND); null when it is not there.
  * «local path» = common.LOCAL_PATH (the author's machine) plus drive-letter,
    UNC and file:// paths — a document title can carry the path of the
    machine the Formular was written on.
  * Beyond the keys the specification lists, the overview carries
    merkmale[].basis (what n_gemessen counts), merkmale[].urteile (every
    verdict with its count, the basis of the sum check), merkmale[].zusatz
    (tel_format: one number in several notations; seitenzahlen: the numbering
    patterns; akzentfarbe: what stands beside the comparison; bf_tags: tagged
    without fields or headings; tel_erklaerung: the Dienststellen of the
    remark), merkmale[].urteil_labels (a verdict named for this Merkmal:
    akzentfarbe's «hinweis» / «kein_hinweis» are the Word and Excel files with
    and without a colour), gruppen[].vorbehalt, gruppen[].kennzahl (the ONE
    figure of the group's door on the page, with its source — invariant 10),
    entscheide[].frage (what is to be decided), praxis.n, bestand.ohne_datei,
    bestand.dienststellen / .dienststellen_gemessen / .dienststellen_ohne_formular
    (the page's door and table «Je Dienststelle»), labels.eformular (the
    sentence of an eFormular), labels.ton_zusatz (what a tone adds to its
    verdicts), labels.art_erklaerung (what each kind of Merkmal means),
    labels.urteil_gesamt (a verdict named for a count over many Formulare),
    labels.urteil_nomen (a red verdict as a noun: «Abweichung», «Lücke»),
    labels.entscheide (the one sentence on the missing rule, said once for all
    decisions), dienststellen[].act_je_formular / .n_nicht_messbar /
    .n.abweichungen / .n.luecken, labels.kennzahl and the kennzahlen ok,
    abweichungen, luecken, betroffen, hinweis, formulare_mit_act,
    formulare_mit_abweichung.

Numbers are written as the rest of the dashboard writes them (de-CH): a
decimal point («10.5 pt», «4.8 %»).

Remarks of the measurement
  BEMERKUNG passes `hinweise` of the measurement on as remarks of a Merkmal,
  verbatim. A sentence is recognised by the constant of gestaltung_text.py
  from which the measuring modules build it (H_…), never by a wording written
  down here a second time; the two facts that decide a verdict are values of
  the profil (text_lesbar, sprache_passt). Two changes of form only: a decimal
  comma that an older run of the measurement wrote before «pt» or «%» is
  written as a point (_DEZIMALKOMMA), and the sentences of KURZ lose their
  closing parenthesis with the element name of the PDF structure («(kein
  Form-Element)», «(H, H1–H6)», «(/MarkInfo)»). The remarks name colours by
  their family, never by a colour code.

Invariants (pruefen(); each raises RuntimeError and names the Merkmal)
  1 per Merkmal the verdict counts sum to the number of Formulare, and the
    Formulare without «entfaellt»/«kein_hinweis» are exactly the per-Formular
    entries; n_gemessen equals the sum of the distribution;
  2 every act / betroffen / hinweis / open count equals the length of its
    list, the lists equal the per-Formular entries; n.dec is 0 or 1 and the
    decisions are exactly the Merkmale with n.dec = 1;
  3 per Formular n equals its own entries, and n.dec the number of entscheide
    whose lists name it; the kennzahlen equal the sums over Merkmale and over
    Formulare;
  4 the Dienststellen sums equal the canton's (Formulare, gemessen, nicht
    messbar, act, Abweichungen, Lücken, open), act = Abweichungen + Lücken for
    each, and bestand counts them (dienststellen, dienststellen_gemessen,
    dienststellen_ohne_formular);
  5 no «@» in any exported string;
  6 no local path in any exported string;
  7 the quote of a phone number appears only for 'bezeichnung' / 'ohne';
  8 (added here) no control character and no private-use glyph in any
    exported string: stored texts are passed on without them (_rein), and a
    page must never receive one;
  9 (added here) a stored document title that looks like the name of a person
    appears in no exported string;
 10 (added here) the figure of each group's door (gruppen[].kennzahl) is the
    count it names as its source: a verdict of a Merkmal of that group, or a
    kennzahl.
"""
import copy
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from fractions import Fraction

from citygov.core.common import LOCAL_PATH      # noqa: E402
from citygov.domain import gestaltung_text as GT                # noqa: E402  (standard library only)

__all__ = ["berechne", "pruefen", "URTEIL", "TON", "ART", "GRUPPEN", "MERKMALE", "MESSART", "ENTSCHEID", "KENNZAHL",
           "PRAXIS_SCHWELLE", "PRAXIS_MIN", "KLEIN_ANTEIL", "AKZENT_MIN"]

# ------------------------------------------------------------------ thresholds
PRAXIS_SCHWELLE = Fraction(2, 3)    # a value shared by this share of the measured Formulare is the practice
PRAXIS_MIN = 30                     # … when at least this many Formulare are measured
KLEIN_PT = 8                        # the measurement's own border (profil.anteil_unter_8)
KLEIN_ANTEIL = 0.05                 # «betroffen» from this share of characters below KLEIN_PT
KLEIN_WINZIG = 6                    # below KLEIN_ANTEIL a remark is made when the smallest size is below this
AKZENT_MIN = 0.001                  # an accent counts from this share of the page area — the gewicht of all
#                                     colours of its family together (profil.farben[].gewicht)
SCHRIFT_MIN_ANTEIL = 0.02           # as profil.n_schriftfamilien counts a family
MEHR_SCHRIFTEN = 3                  # «more than two typefaces»
MEHR_FARBEN = 2                     # «two or more colour families»
ZWEITE_GROESSE = Fraction(1, 3)     # the shares of the sizes are shown when the second size holds this much
KNAPP = 0.60                        # no practice, but close: the commonest value holds at least this share
TOP = 3                             # Merkmale named per Dienststelle

# ------------------------------------------------- vocabulary (to move into labels.py)
# verdict key -> (label, tone). The tone says who acts next (labels.TON): on a
# Formular only ok / act / open are drawn; «dec» is drawn once per Merkmal.
URTEIL = {
    "entspricht":     ("entspricht der Praxis", "ok"),
    "weicht_ab":      ("weicht von der Praxis ab", "act"),
    "uneinheitlich":  ("keine klare Praxis — der Kanton legt fest", "dec"),
    "vorhanden":      ("vorhanden", "ok"),
    "luecke":         ("Lücke", "act"),
    "betroffen":      ("betrifft dieses Formular", None),
    "hinweis":        ("Hinweis", None),
    "kein_hinweis":   ("kein Hinweis", None),
    "nicht_messbar":  ("nicht messbar", "open"),
    "nicht_gemessen": ("noch nicht gemessen", "open"),
    "entfaellt":      ("entfällt", None),
}
# a verdict named for a count over many Formulare (the overview), where the label above speaks of one Formular
URTEIL_GESAMT = {"betroffen": "betroffen"}
# a red finding as a noun, for the lists of the most frequent ones per Dienststelle («Lücke bei 41»)
URTEIL_NOMEN = {"weicht_ab": "Abweichung", "luecke": "Lücke"}
# a verdict named for one Merkmal: akzentfarbe compares PDF only — its «hinweis» / «kein_hinweis» are the Word and
# Excel files with and without a colour
URTEIL_MERKMAL = {"akzentfarbe": {"hinweis": "Word/Excel mit Farbe", "kein_hinweis": "Word/Excel ohne Farbe"}}
NICHT_EXPORTIERT = ("entfaellt", "kein_hinweis")        # left out of forms[].gestaltung.merkmale
LISTEN = ("weicht_ab", "luecke", "betroffen", "hinweis", "nicht_messbar", "nicht_gemessen")
_GEMESSEN = (None, "vorhanden", "luecke", "betroffen", "hinweis", "kein_hinweis")   # None: a value still to be judged

# what the four tones mean IN THIS LAYER (the colours are those of labels.TON): TON_ZUSATZ is what a tone adds to
# its verdicts (the page's reading hint names the verdicts once and puts this beside them), TON the whole sentence.
# A red verdict describes a difference; whether a rule is broken, the databank cannot say (no corporate-design
# manual, no accessibility test)
TON_ZUSATZ = {
    "ok":   "derselbe Wert wie bei mindestens zwei Dritteln der gemessenen Formulare, oder das geprüfte Merkmal ist da",
    "act":  "ein Unterschied am Formular der Dienststelle, keine Aufforderung, es zu ändern; ob eine Vorgabe "
            "verletzt ist, sagt das nicht",
    "dec":  "der Databank liegt keine Vorgabe vor; festgelegt wird einmal je Merkmal, nicht je Formular",
    "open": "offen bei der Databank, kein Befund über das Formular",
}
TON = {
    "ok":   "entspricht der Praxis, oder das Merkmal ist vorhanden — " + TON_ZUSATZ["ok"],
    "act":  "weicht von der Praxis ab, oder ein Merkmal fehlt — " + TON_ZUSATZ["act"],
    "dec":  "keine klare Praxis oder keine Regel — " + TON_ZUSATZ["dec"],
    "open": "nicht messbar oder noch nicht gemessen — " + TON_ZUSATZ["open"],
}
# the headline figures (overview.kennzahlen)
KENNZAHL = {
    "pdf": "PDF-Formulare",
    "pdf_mindestmerkmale": "PDF-Formulare mit Struktur-Tags, Dokumentsprache und einem Dokumenttitel, der das "
                           "Formular nennt",
    "ok": "Merkmale, die der Praxis entsprechen oder vorhanden sind (Formular × Merkmal)",
    "act": "Abweichungen von der Praxis und Lücken (Formular × Merkmal)",
    "abweichungen": "Abweichungen von der Praxis (Formular × Merkmal)",
    "luecken": "Lücken (Formular × Merkmal)",
    "dec": "offene Festlegungen des Kantons",
    "betroffen": "Formulare, die eine offene Festlegung betrifft",
    "hinweis": "Hinweise (Formular × Merkmal)",
    "open": "nicht messbar oder noch nicht gemessen (Formular × Merkmal)",
    "formulare_mit_act": "Formulare mit mindestens einer Abweichung oder Lücke",
    "formulare_mit_abweichung": "Formulare mit mindestens einer Abweichung von der Praxis",
    "formulare_mit_luecke": "Formulare mit mindestens einer Lücke",
}
ART = {"praxis": "Vergleich mit der Praxis", "pruefpunkt": "Prüfpunkt", "regel_offen": "Regel offen",
       "hinweis": "Hinweis"}
ART_ERKLAERUNG = {
    "praxis": "Der Wert eines Formulars ist mit der Praxis verglichen: dem Wert, den mindestens zwei Drittel der "
              "gemessenen Formulare teilen. Erreicht kein Wert zwei Drittel, gibt es keine klare Praxis, und der "
              "Kanton legt fest.",
    "pruefpunkt": "Das Merkmal ist vorhanden oder fehlt — unabhängig davon, was die übrigen Formulare zeigen. Ein "
                  "fehlendes Merkmal ist eine Lücke.",
    "regel_offen": "Eine Grenze liegt der Databank nicht vor: Sie nennt die Formulare über ihrer eigenen Schwelle, "
                   "und der Kanton legt fest, ob und welche Regel gilt.",
    "hinweis": "Eine Feststellung ohne Bewertung und ohne Farbe.",
}
MESSART = {"pdf": "PDF", "pdf_bild": "PDF ohne Text (Bild, z. B. ein Scan)", "word": "Word", "excel": "Excel",
           "nicht_messbar": "nicht messbar (altes Dateiformat)"}

V_FARBEN = "Farben sind nur im Seiteninhalt gemessen; Logos und Bilder sind nicht ausgewertet."
V_BARRIEREFREI = ("Maschinell prüfbare Mindestmerkmale — kein vollständiger Test nach eCH-0059, WCAG oder PDF/UA. "
                  "Ein fehlendes Merkmal ist eine Lücke; ein vorhandenes ist kein Nachweis der Barrierefreiheit.")
V_KONTAKT = ("Gelesen ist nur der Text: Ein Name, der im Logo oder an anderer Stelle der Seite steht, wird bei "
             "einer Nummer nicht gesehen.")
V_HANDBUCH = "das Corporate-Design-Handbuch des Kantons ist nicht erfasst"
# (key, label, frage, vorbehalt)
GRUPPEN = (
    ("schrift", "Schrift", "Sind die Formulare in derselben Schrift und Schriftgrösse gesetzt?", None),
    ("farben", "Farben", "Welche Farben verwenden die Formulare im Seiteninhalt — ohne Logos und Bilder?", V_FARBEN),
    ("barrierefrei", "Barrierefreiheit — Mindestmerkmale",
     "Tragen die Dateien die maschinell prüfbaren Mindestmerkmale, auf die sich ein Screenreader "
     "(Vorleseprogramm) stützt?", V_BARRIEREFREI),
    ("kontakt", "Kontaktangaben",
     "Steht bei gedruckten Telefonnummern, wessen Nummer es ist, und sind sie einheitlich geschrieben?", V_KONTAKT),
    ("aufbau", "Aufbau", "Sind Seitenformat, Stand-Angabe, Seitenzahlen und Absender einheitlich?", None),
)

_T_SCHNITT = ("Ein Schnitt zählt zu seiner Schrift (Arial Narrow zu Arial, Frutiger Condensed zu Frutiger), "
              "Times New Roman zu Times.")
_T_ANHANG = ("Gezählt sind alle Seiten der Datei: Ein dicht gesetzter Anhang (Merkblatt, Gesetzesauszug) kann das "
             "eigentliche Formular überstimmen.")
# (key, gruppe, art, file types it can apply to | None = all, label, frage, erklaerung, basis)
# basis says what n_gemessen counts: the Formulare for which the Merkmal is measured or compared
MERKMALE = (
    ("schrift", "schrift", "praxis", None, "Schrift",
     "In welcher Schrift ist das Formular gesetzt?",
     "Verglichen wird die Schrift, in der die meisten Zeichen des Formulars gesetzt sind — so, wie die Datei sie "
     "nennt, nicht wie ein Gerät ohne diese Schrift sie anzeigt. " + _T_SCHNITT + " " + _T_ANHANG + " Setzt die "
     "Hauptschrift weniger als zwei Drittel der Zeichen, stehen die Anteile beim Formular. Schrift in Bildern und "
     "in Formularfeldern ist nicht gemessen.",
     "Formulare mit gemessener Schrift"),
    ("groesse", "schrift", "praxis", None, "Grundgrösse",
     "In welcher Schriftgrösse steht der grösste Teil des Textes?",
     "Die Grundgrösse ist die Schriftgrösse mit den meisten Zeichen, auf einen halben Punkt gerundet. "
     + _T_ANHANG + " Liegt die Grundgrösse nur knapp vor der nächsten Grösse oder setzt die zweite Grösse "
     "mindestens ein Drittel der Zeichen, stehen die Anteile beim Formular.",
     "Formulare mit gemessener Schriftgrösse"),
    ("kleinschrift", "schrift", "regel_offen", None, "Kleine Schrift",
     "Wie viel Text ist kleiner als 8 Punkt gesetzt?",
     "Betroffen ist ein Formular, wenn mindestens 5 % seiner Zeichen kleiner als 8 pt gesetzt sind; genannt sind "
     "der Anteil und die kleinste Grösse. Auch Fusszeilen, Fussnoten und Feldhinweise zählen. Die Grenzen 8 pt "
     "und 5 % sind Setzungen der Databank, keine Norm: Sie kennt keine Vorgabe für eine Mindest-Schriftgrösse, "
     "und ob der Kanton eine vorgibt, ist ihr nicht bekannt. Deshalb ist das keine Lücke des einzelnen "
     "Formulars. Unter 5 % steht nur dann ein Hinweis, wenn die kleinste Grösse unter 6 pt liegt. Grössen sind "
     "auf einen halben Punkt gerundet — 7.75 pt zählt als 8 pt.",
     "Formulare mit gemessener Schriftgrösse"),
    ("eingebettet", "schrift", "pruefpunkt", ("pdf",), "Schriften eingebettet",
     "Bringt die PDF-Datei ihre Schriften mit?",
     "Ist eine Schrift nicht eingebettet, zeigt ein Gerät ohne diese Schrift eine Ersatzschrift. Bei verbreiteten "
     "Schriften wie Arial ist der Unterschied meist klein; die Lücke sagt nur, dass die Datei die Schrift nicht "
     "selbst mitbringt. Geprüft sind die Schriften, die sichtbare Zeichen setzen; die Standardschriften, die "
     "jedes PDF-Programm mitbringt (zum Beispiel Helvetica), zählen nicht als Lücke. Nur PDF.",
     "PDF-Formulare mit gemessener Schrift"),
    ("schriftfamilien", "schrift", "hinweis", None, "Mehrere Schriften",
     "Mischt das Formular mehr als zwei Schriften?",
     "Gezählt sind Schriften, die mindestens 2 % der Zeichen setzen; Symbolschriften (Ankreuzfelder, Pfeile) "
     "zählen nicht. " + _T_SCHNITT + " Ein Hinweis ohne Bewertung.",
     "Formulare mit gemessener Schrift"),
    ("akzentfarbe", "farben", "praxis", None, "Akzentfarbe",
     "Verwendet der Seiteninhalt — ohne Logo und Bilder — neben Schwarz und Grau eine Farbe, und welche?",
     "Die Akzentfarbe ist die Farbfamilie (Rot, Blau, Gelb …), die im Seiteninhalt am meisten Fläche einnimmt: "
     "Flächen, Linien und farbiger Text; beim Formular steht, was davon farbig ist. Sie zählt, wenn ihre "
     "Farbtöne zusammen mindestens 0.1 % der Seitenfläche einnehmen; darunter gilt «keine Akzentfarbe», und die "
     "Farbe ist beim Formular genannt. Die Grenze ist eine Setzung der Databank: Formulare derselben Gestaltung "
     "können knapp darüber und knapp darunter liegen. Nicht als Akzentfarbe zählen die Farbe von Internet- und "
     "E-Mail-Adressen und von verlinkten Wörtern, die Farbe von Formularfeldern und eine kleine Farbmarke im Kopf "
     "der ersten Seite (in der Regel ein gezeichnetes Logo). «(blass)» heisst: ein heller Farbton, wie ihn "
     "getönte Eingabefelder tragen. Verglichen werden PDF-Formulare untereinander; bei Word- und Excel-Dateien "
     "ist die Farbe genannt, aber nicht beurteilt. " + V_FARBEN,
     "PDF-Formulare mit gemessenen Farben (Word und Excel: genannt, nicht verglichen)"),
    ("farbvielfalt", "farben", "hinweis", None, "Mehrere Farben",
     "Kommen im Seiteninhalt zwei oder mehr Farbfamilien vor — ohne die Farbe von Adressen, Formularfeldern und der "
     "Farbmarke im Kopf?",
     "Gezählt sind die Farbfamilien der Flächen, der Linien und des farbigen Textes — ohne die Farbe von "
     "Internet- und E-Mail-Adressen und verlinkten Wörtern, ohne die Farbe von Formularfeldern und ohne eine "
     "kleine Farbmarke im Kopf der ersten Seite. In Word- und Excel-Dateien zählt schon eine einzelne gefüllte "
     "Zelle. Ein Hinweis ohne Bewertung. " + V_FARBEN,
     "Formulare mit gemessenen Farben"),
    ("bf_tags", "barrierefrei", "pruefpunkt", ("pdf",), "Struktur-Tags",
     "Ist das PDF für Screenreader ausgezeichnet (getaggt)?",
     "Vorhanden heisst: Die Datei ist als getaggt gekennzeichnet, und ihr Strukturbaum ist nicht leer. Über die "
     "Qualität der Tags sagt das nichts; fehlen im Strukturbaum die Überschriften oder die Formularfelder, steht "
     "das als Bemerkung beim Formular. Nur PDF.",
     "PDF-Formulare"),
    ("bf_sprache", "barrierefrei", "pruefpunkt", ("pdf", "word"), "Dokumentsprache",
     "Nennt die Datei die Sprache ihres Textes?",
     "Ohne Sprachangabe muss ein Screenreader die Aussprache erraten. Als Lücke zählt auch eine Angabe, die "
     "nicht zur Sprache des Textes passt. Tragen nur einzelne Teile des Dokuments eine Sprachangabe, steht das "
     "beim Formular. «de-DE» statt «de-CH» ist nur eine Bemerkung. PDF und Word.",
     "PDF- und Word-Formulare"),
    ("bf_titel", "barrierefrei", "pruefpunkt", ("pdf", "word", "excel"), "Dokumenttitel (Dateieigenschaft)",
     "Trägt die Datei in ihren Eigenschaften einen Titel, der das Formular nennt — nicht die Überschrift, die auf "
     "dem Formular gedruckt ist?",
     "Fehlt der Titel, nennen der Reiter (Tab) des Anzeigeprogramms und der Screenreader den Dateinamen. Als "
     "Lücke zählt auch ein Titel, der nur ein Datei- oder Platzhaltername ist («Microsoft Word - …», "
     "«Dokument»), und ein Titel, der etwas anderes nennt als das Formular. Massstab ist der Name des Formulars "
     "in der Databank; der Titel der Datei ist wörtlich zitiert — ausser er sieht aus wie der Name einer Person. "
     "PDF, Word und Excel.",
     "PDF-, Word- und Excel-Formulare"),
    ("bf_feldnamen", "barrierefrei", "pruefpunkt", ("pdf",), "Feldbeschreibungen",
     "Trägt jedes ausfüllbare Feld eine Beschreibung?",
     "Ein Screenreader liest zu jedem Feld dessen Beschreibung (Kurzinfo) vor; fehlt sie, hört die Person nur "
     "den internen Feldnamen (oft «Text1»). Ein Platzhalter wie «3» oder «undefined» zählt nicht als "
     "Beschreibung. Ob eine Beschreibung verständlich ist, ist nicht geprüft. Nur PDF mit ausfüllbaren Feldern.",
     "PDF-Formulare mit ausfüllbaren Feldern"),
    ("bf_textebene", "barrierefrei", "pruefpunkt", ("pdf",), "Textebene",
     "Ist der Text als lesbarer Text abgelegt und nicht nur als Bild?",
     "Ein eingescanntes Formular ohne Textebene lässt sich weder vorlesen noch durchsuchen. Dasselbe gilt, wenn "
     "die Datei ihren Text nicht lesbar ablegt (Steuerzeichen statt Buchstaben): Der Text ist da, aber "
     "Vorleseprogramm und Suche erhalten keine Wörter. Nur PDF.",
     "PDF-Formulare"),
    ("bf_ueberschriften", "barrierefrei", "pruefpunkt", ("word",), "Überschriften",
     "Gliedert die Word-Datei ihren Text mit Überschriften?",
     "Vorhanden heisst: Mindestens ein Absatz trägt eine Überschrift-Formatvorlage. Trägt genau einer eine, "
     "steht «eine einzige Überschrift»: Eine Gliederung ist das noch nicht. Nur Word.",
     "Word-Formulare"),
    ("tel_erklaerung", "kontakt", "pruefpunkt", None, "Telefonnummer erklärt",
     "Steht bei jeder gedruckten Telefonnummer, wessen Nummer es ist?",
     "Es zählt die am wenigsten erklärte Nummer des Formulars (Telefon oder Fax). Erklärt ist eine Nummer, wenn "
     "ihre Zeile oder der Absenderblock, zu dem sie gehört, eine Stelle, eine Funktion, eine Person oder einen "
     "Zweck nennt. Eine Lücke ist eine Nummer ohne jede Bezeichnung — etwa eine blosse Nummer unter einer "
     "Adresse; ihre Zeile ist wörtlich zitiert. Ein Hinweis, keine Lücke, ist eine Nummer, die als Telefon- oder "
     "Faxnummer bezeichnet ist («Tel. 052 …»), bei der aber im Text daneben keine Stelle steht. " + V_KONTAKT
     + " Nur Formulare, die eine Nummer drucken.",
     "Formulare, die eine Telefon- oder Faxnummer drucken"),
    ("tel_format", "kontakt", "praxis", None, "Schreibweise der Telefonnummern",
     "Sind die Nummern international (+41 …) oder national (052 …) geschrieben?",
     "International heisst mit Landesvorwahl (+41 oder 0041), national mit führender Null; «gemischt» heisst, "
     "dass ein Formular beides druckt. Nur Formulare, die eine Nummer drucken.",
     "Formulare, die eine Telefon- oder Faxnummer drucken"),
    ("fax", "kontakt", "hinweis", None, "Faxnummer",
     "Druckt das Formular eine Faxnummer?",
     "Genannt sind die Formulare, die eine Faxnummer drucken. Eine Nummer, die in der Datei durchgestrichen ist, "
     "zählt nicht. Ein Hinweis ohne Bewertung.",
     "Formulare mit lesbarem Text"),
    ("email_art", "kontakt", "hinweis", None, "Persönliche E-Mail-Adresse",
     "Druckt das Formular die E-Mail-Adresse einer Person?",
     "Die Databank speichert keine Adressen, nur ihre Art und die Domain. Als persönlich zählt eine Adresse nur "
     "mit Beleg (Vorname.Nachname, Initialen oder der Name daneben): Die Zahl ist deshalb eine Untergrenze. Ein "
     "Hinweis ohne Bewertung.",
     "Formulare mit lesbarem Text"),
    ("seitenformat", "aufbau", "praxis", None, "Seitenformat",
     "Welches Seitenformat hat das Formular?",
     "Gemessen ist die erste Seite (bei Excel das erste Tabellenblatt): A4 hoch, A4 quer oder ein anderes "
     "Format. Wechselt das Format innerhalb der Datei, steht das als Bemerkung beim Formular.",
     "Formulare mit gemessenem Seitenformat"),
    ("stand_angabe", "aufbau", "praxis", None, "Stand-Angabe",
     "Ist auf dem Formular gedruckt, welche Fassung es ist?",
     "Als Stand-Angabe zählt ein gedruckter Vermerk zur Fassung: «Stand …», «Version …», «Ausgabe …», ein Druck- "
     "oder Änderungsvermerk («ausgedruckt am …», «zuletzt angepasst am …»), eine Formularnummer oder ein "
     "Dateiname mit Monat und Jahr, Monat und Jahr allein in der Fusszeile oder — wenn sonst nichts dasteht — "
     "eine Jahreszahl allein auf ihrer Zeile. Der Vermerk ist wörtlich zitiert (ohne ein Namenskürzel dahinter); "
     "trägt eine Datei mehrere, ist es der erste. Ein Feld, in das die antragstellende Person Ort und Tag der "
     "Unterschrift einträgt, ist keine Stand-Angabe.",
     "Formulare mit lesbarem Text"),
    ("seitenzahlen", "aufbau", "praxis", ("pdf", "word"), "Seitenzahlen",
     "Sind mehrseitige Formulare nummeriert?",
     "Geprüft sind PDF- und Word-Formulare mit mehr als einer Seite; einseitige entfallen. Excel-Dateien "
     "entfallen ebenfalls: Wie viele Seiten sie drucken, steht erst beim Drucken fest.",
     "mehrseitige PDF- und Word-Formulare"),
    ("absender", "aufbau", "praxis", None, "Absender",
     "Nennt die erste Seite im Text den Kanton und die Dienststelle?",
     "Gelesen wird der Text der ersten Seite. «Kanton Schaffhausen» zählt, wo es wie ein Absender steht — "
     "allein, am Anfang einer Zeile oder in einer Namenszeile wie «Amt … des Kantons Schaffhausen» —, nicht "
     "mitten in einem Satz («Wohnsitz im Kanton Schaffhausen»). Die Dienststelle zählt mit dem Namen, den die "
     "Databank führt, überall auf der ersten Seite. Steht ein Name nur im Logo oder druckt das Formular die "
     "Dienststelle unter einem anderen Namen (etwa «Sicherheitspolizei» für die Polizei oder ein früherer "
     "Amtsname), ist er nicht erkannt. Ob ein Formular vom Kanton stammt, ist nicht unterschieden: Auch "
     "Formulare des Bundes oder Dritter sind so gelesen.",
     "Formulare mit lesbarem Text und bekannter Dienststelle"),
)
MERKMAL_KEYS = tuple(m[0] for m in MERKMALE)
_M = {m[0]: m for m in MERKMALE}

# the ONE open decision of a Merkmal without a clear practice: (label, what a rule would be about, a sentence
# more | None). The databank does not know whether the canton has laid something down — it only knows that it
# holds no rule and that the Formulare show none.
ENTSCHEID = {
    "schrift": ("Schrift der Formulare", "zur Schrift der Formulare", None),
    "groesse": ("Grundgrösse der Schrift", "zur Grundgrösse der Schrift", None),
    "kleinschrift": ("Mindest-Schriftgrösse", "für eine Mindest-Schriftgrösse", None),
    "akzentfarbe": ("Akzentfarbe der Formulare", "zur Akzentfarbe der Formulare", None),
    "tel_format": ("Schreibweise der Telefonnummern", "zur Schreibweise der Telefonnummern", None),
    "seitenformat": ("Seitenformat der Formulare", "zum Seitenformat", None),
    "stand_angabe": ("Stand-Angabe auf dem Formular", "zur Stand-Angabe", None),
    "seitenzahlen": ("Seitenzahlen auf mehrseitigen Formularen", "zu den Seitenzahlen", None),
    "absender": ("Absender auf der ersten Seite", "zum Absender auf der ersten Seite",
                 "Ob der Absender im Text der ersten Seite steht, ist uneinheitlich; ein Absender, der nur im Logo "
                 "steht, ist nicht erkannt."),
}
# what is to be decided (entscheide[].frage), and the one sentence on the missing rule, said once for all
# decisions (labels.entscheide) — the databank knows only that it holds no rule, not what the canton laid down
T_FRAGE = "ob eine Vorgabe {wozu} gilt und welche — oder ob das Corporate-Design-Handbuch des Kantons sie schon regelt"
T_ENTSCHEIDE = ("Zu keinem dieser Merkmale liegt der Databank eine Vorgabe vor (" + V_HANDBUCH + "); ob der Kanton "
                "schon etwas festgelegt hat, weiss sie nicht.")

# ---- sentences of the measurement that this layer passes on as remarks of a Merkmal (or as the reason of
# «nicht messbar»), verbatim. They are recognised by the constants of gestaltung_text.py from which the
# measuring modules build them — never by a wording that is written down a second time here.
BEMERKUNG = {
    "schrift": (GT.H_OHNE_TEXT, GT.H_UNSICHTBAR, GT.H_NAMENLOS, GT.H_PLATZHALTERNAME, GT.H_SCHRIFT_KNAPP),
    "groesse": (GT.H_OHNE_TEXT, GT.H_UNSICHTBAR, GT.H_GROESSE_KNAPP),
    "kleinschrift": (GT.H_OHNE_TEXT, GT.H_UNSICHTBAR),
    "eingebettet": (GT.H_OHNE_TEXT, GT.H_UNSICHTBAR, GT.H_NICHT_EINGEBETTET),
    "schriftfamilien": (GT.H_OHNE_TEXT, GT.H_UNSICHTBAR, GT.H_NAMENLOS, GT.H_PLATZHALTERNAME),
    "akzentfarbe": (GT.H_OHNE_TEXT, GT.H_FARBE_NICHT_GEMESSEN, GT.H_FARBE_AUSGELASSEN),
    "farbvielfalt": (GT.H_OHNE_TEXT, GT.H_FARBE_NICHT_GEMESSEN, GT.H_FARBE_AUSGELASSEN),
    "bf_tags": (GT.H_TAGS_OHNE_FELDER, GT.H_TAGS_OHNE_UEBERSCHRIFT, GT.H_BAUM_LEER, GT.H_BAUM_OHNE_MARKE,
                GT.H_MARKE_OHNE_BAUM, GT.H_PDFUA),
    "bf_sprache": (GT.H_SPRACHE_FREMD, GT.H_SPRACHE_TEILE),
    "bf_titel": (GT.H_TITEL_ANZEIGE,),
    "bf_feldnamen": (GT.H_KURZINFO_PLATZHALTER,),
    "bf_textebene": (GT.H_OHNE_TEXT, GT.H_UNSICHTBAR, GT.H_UNLESBAR, GT.H_TEIL_UNSICHTBAR),
    "bf_ueberschriften": (GT.H_EINE_UEBERSCHRIFT,),
    "tel_erklaerung": (GT.H_OHNE_TEXT, GT.H_FELDWERT, GT.H_GESTRICHEN),
    "tel_format": (GT.H_OHNE_TEXT,),
    "fax": (GT.H_OHNE_TEXT, GT.H_GESTRICHEN),
    "email_art": (GT.H_OHNE_TEXT,),
    "seitenformat": (GT.H_FORMAT_GEMISCHT, GT.H_FORMAT_ABSCHNITTE, GT.H_FORMAT_BLAETTER),
    "stand_angabe": (GT.H_OHNE_TEXT,),
    "seitenzahlen": (GT.H_OHNE_TEXT, GT.H_SEITENZAHL),
    "absender": (GT.H_OHNE_TEXT, GT.H_OHNE_UMBRUCH),
}

# a decimal comma that an older run of the measurement wrote before a unit («10,5 pt»): written as a point, like
# every number of the dashboard
_DEZIMALKOMMA = re.compile(r"(?<=\d),(?=\d+\s?(?:pt|%))")
# sentences of the measurement that close with the element name of the PDF structure in parentheses — passed on
# without it
KURZ = (GT.H_TAGS_OHNE_FELDER, GT.H_TAGS_OHNE_UEBERSCHRIFT, GT.H_BAUM_OHNE_MARKE)
_SCHLUSSKLAMMER = re.compile(r"\s\([^()]*\)(?=\.?$)")

T_EFORMULAR = "eFormular der Plattform — kein eigenes Erscheinungsbild"
T_NUR = {("pdf",): "nur PDF", ("word",): "nur Word", ("pdf", "word"): "nur PDF und Word",
         ("pdf", "word", "excel"): "nur PDF, Word und Excel"}
T_AKZENT_OHNE = "keine Akzentfarbe"
T_SEITENZAHLEN_JA = "Seitenzahlen vorhanden"
T_FARBEN_KEINE = "keine Farbfamilie gezählt"
T_BILD = "Seite 1 trägt ein Bild (in der Regel das Logo); seine Farben sind nicht gemessen."
T_OHNE_NUMMER = "keine Telefonnummer im Text"      # a number inside an image is not read
T_UNLESBAR = "Die Datei legt ihren Text nicht lesbar ab (Steuerzeichen statt Buchstaben)."
T_FORMAT = {"international": "international (+41 …)", "national": "national (0…)", "andere": "ausländische Nummer"}
T_TITEL = {"aussagekraeftig": "nennt das Formular", "leer": "Titel fehlt",
           "generisch": "Datei- oder Platzhaltername", "ohne_bezug": "nennt das Formular nicht"}
T_TITEL_PERSON = "Titel der Datei nicht zitiert: Er sieht aus wie der Name einer Person."
T_ERKLAERUNG = {"erklaert": "erklärt", "bezeichnung": "Stelle nicht im Text bei der Nummer",
                "ohne": "ohne jede Bezeichnung"}
T_NUR_TEXT = ("Die Zeile nennt nur, dass es eine Telefon- oder Faxnummer ist. Ein Logo oder ein Absender an "
              "anderer Stelle der Seite ist dafür nicht gelesen.")
T_ABSENDER = {(True, True): "Kanton und Dienststelle", (True, False): "nur Kanton", (False, True): "nur Dienststelle",
              (False, False): "weder Kanton noch Dienststelle im Text genannt"}
_RANG = {"ohne": 0, "bezeichnung": 1, "erklaert": 2}                 # the weakest printed number decides
_TEL_URTEIL = {"ohne": "luecke", "bezeichnung": "hinweis", "erklaert": "vorhanden"}

# the stored form of an e-mail address in a quote («…@domain», scan_gestaltung.py / gestaltung_text.py)
_ADRESSREST = re.compile(r"…@[^\s«»<>()\[\]{},;:\"']+")
# characters a page cannot show: control characters (a NUL from a PDF string), private-use glyphs of a
# symbol font (a bullet set in Wingdings), line and paragraph separators
_UNZEIGBAR = re.compile("[\x00-\x1f\x7f-\x9f-  ]")
# paths of a machine beyond common.LOCAL_PATH: drive letter, UNC share, file://
_PFAD_FREMD = re.compile(r"(?<![A-Za-z])[A-Za-z]:\\[^\s]|\\\\[A-Za-z0-9_.$-]+\\[A-Za-z0-9_.$-]|file://", re.I)
# the initials of an author behind an edition mark («Juli 2017/MG»): not quoted
_KUERZEL = re.compile(r"(?<=\d)\s?/\s?[A-Za-zÄÖÜäöü]{2,4}$")


# =============================================================== small helpers

def _pl(n, einzahl, mehrzahl):
    return f"{n} {einzahl if n == 1 else mehrzahl}"


def _zahl(x, stellen):
    """A number as the dashboard writes it (de-CH): decimal point, no trailing zeros."""
    t = f"{x:.{stellen}f}"
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t


def _pt(x):
    return _zahl(x, 1) + " pt"


def _proz(x):
    """A share as whole per cent: «88 %»; a share above zero is never shown as «0 %»."""
    p = round(x * 100)
    return "unter 1 %" if p == 0 and x > 0 else f"{p} %"


def _proz_flaeche(x):
    """A share of the page area — small values keep their digits: «0.016 %», «0.59 %», «2.5 %», «33 %»."""
    p = x * 100
    return _zahl(p, 0 if p >= 10 else 1 if p >= 1 else 2 if p >= 0.1 else 3) + " %"


def _rein(text):
    """A stored text without the characters a page cannot show (_UNZEIGBAR)."""
    return _UNZEIGBAR.sub("", (text or "").replace("\t", " ").replace("\n", " ")).strip()


def _sauber(text):
    """A stored quote as it is exported: the reduced e-mail address «…@domain» named, not shown; the mark
    of a line break («⏎») as a slash."""
    return _rein(_ADRESSREST.sub("[E-Mail-Adresse]", text or "").replace(" " + GT.UMBRUCH + " ", " / ")
                 .replace(GT.UMBRUCH, " / "))


def _zitat(text):
    return "«" + _sauber(text) + "»"


def _sprache_norm(s):
    """«DE-CH», «de-ch» -> «de-CH»: one spelling per language for the distribution."""
    teile = s.strip().replace("_", "-").split("-")
    return "-".join([teile[0].lower()] + [t.upper() if len(t) == 2 else t for t in teile[1:]])


def _hin_lesen(profil):
    """The hinweise of a stored profil, in their stored order; a decimal comma before a unit as a point."""
    return [_DEZIMALKOMMA.sub(".", h) for h in (profil.get("hinweise") or []) if isinstance(h, str)]


def _ohne_klammer(h):
    """A sentence of KURZ without its closing parenthesis (the element name of the PDF structure)."""
    return _SCHLUSSKLAMMER.sub("", h) if any(h.startswith(teil) for teil in KURZ) else h


def _bem(z, key):
    """The hinweise of the measurement that belong to this Merkmal, verbatim (but _ohne_klammer), in their stored order."""
    return [_ohne_klammer(h) for h in z["hin"] if any(teil in h for teil in BEMERKUNG.get(key, ()))]


def _hat(z, teil):
    return any(teil in h for h in z["hin"])


def _f(u, w, v=None, d=None, pop=None):
    """One cell of the table Formular × Merkmal. u = verdict key (None: a value the
    practice still has to judge), w = shown, v = the value compared and counted
    in the distribution, d = details, pop = belongs to the measured population."""
    if pop is None:
        pop = u in _GEMESSEN
    w = _rein(w)
    return {"u": u, "w": w, "v": (w if v is None else _rein(v)) if pop else None, "p": None,
            "d": [_rein(x) for x in (d or []) if x and _rein(x)] or None, "pop": pop}


def _nm(z, key, zusatz=None):
    """«nicht messbar», with the reason: what the measurement says about it, and for a Merkmal read from the
    text the short sentence about text that is stored unreadably (the long one stands at bf_textebene)."""
    kurz = [T_UNLESBAR] if z["unles"] and GT.H_UNLESBAR not in BEMERKUNG[key] else []
    return _f("nicht_messbar", URTEIL["nicht_messbar"][0], d=(zusatz or []) + kurz + _bem(z, key))


def _entf(grund):
    return _f("entfaellt", grund)


# ================================================== one evaluator per Merkmal
# z = {"id", "p": profil, "hin": its hinweise, "art": 'pdf' | 'word' | 'excel', "unles": the file stores text
#      that cannot be read (barrierefrei.text_lesbar is false), "bild1": page 1 carries an image}

def _m_schrift(z):
    h = z["p"]["hauptschrift"]
    if h is None:
        return _nm(z, "schrift")
    bem = _bem(z, "schrift")
    text = [s for s in z["p"]["schriften"] or [] if not s["symbol"]]
    if text and Fraction(text[0]["anteil"]) < PRAXIS_SCHWELLE and not _hat(z, GT.H_SCHRIFT_KNAPP):
        # the main font does not set two thirds of the characters: say who sets the rest (an annex?)
        bem = [", ".join(f"{s['familie']} {_proz(s['anteil'])}" + (" der Zeichen" if i == 0 else "")
                         for i, s in enumerate(text[:3]) if s["anteil"] >= SCHRIFT_MIN_ANTEIL)] + bem
    return _f(None, h, v=GT.schriftgruppe(h), d=bem)


def _m_groesse(z):
    g = z["p"]["grundgroesse"]
    if g is None:
        return _nm(z, "groesse")
    bem = _bem(z, "groesse")
    alle = z["p"]["groessen"] or []
    if len(alle) > 1 and Fraction(alle[1]["anteil"]) >= ZWEITE_GROESSE and not _hat(z, GT.H_GROESSE_KNAPP):
        bem = [", ".join(f"{_pt(s['pt'])} {_proz(s['anteil'])}" + (" der Zeichen" if i == 0 else "")
                         for i, s in enumerate(alle[:3]) if s["anteil"] >= SCHRIFT_MIN_ANTEIL)] + bem
    return _f(None, _pt(g), d=bem)


def _m_kleinschrift(z):
    a = z["p"]["anteil_unter_8"]
    if a is None:
        return _nm(z, "kleinschrift")
    band = ("kein Zeichen unter 8 pt" if a == 0 else "unter 5 % der Zeichen" if a < KLEIN_ANTEIL else
            "5 bis unter 20 % der Zeichen" if a < 0.20 else "20 bis unter 50 % der Zeichen" if a < 0.50 else
            "50 % der Zeichen und mehr")
    k = z["p"]["kleinste"]
    klein = [f"kleinste Schriftgrösse: {_pt(k)}"] if k is not None else None
    wert = f"{_zahl(a * 100, 1 if a < 0.10 else 0)} % der Zeichen unter {KLEIN_PT} pt"     # «4.8 %», «5.3 %», «23 %»
    if a < KLEIN_ANTEIL:
        if a > 0 and k is not None and k < KLEIN_WINZIG:        # little small text, but very small
            return _f("hinweis", wert, v=band, d=klein)
        return _f("kein_hinweis", band)
    return _f("betroffen", wert, v=band, d=klein)


def _m_eingebettet(z):
    e = z["p"]["barrierefrei"]["schriften_eingebettet"]
    if e is None:
        return _nm(z, "eingebettet")
    bem = _bem(z, "eingebettet")
    if e:
        return _f("vorhanden", "alle eingebettet", d=bem)
    # which fonts are missing: the sentence «Nicht eingebettet: Arial.» of the measurement names them
    kopf = GT.H_NICHT_EINGEBETTET + ": "
    namen = next((h[len(kopf):].rstrip(". ") for h in bem if h.startswith(kopf)), None)
    if not namen:
        return _f("luecke", "nicht alle eingebettet", d=bem)
    return _f("luecke", namen + " nicht eingebettet", d=[h for h in bem if not h.startswith(kopf)])


def _m_schriftfamilien(z):
    n = z["p"]["n_schriftfamilien"]
    if n is None:
        return _nm(z, "schriftfamilien")
    namen = [s["familie"] for s in z["p"]["schriften"] or [] if not s["symbol"] and s["anteil"] >= SCHRIFT_MIN_ANTEIL]
    if len(namen) != n:
        raise RuntimeError(f"schriftfamilien: Formular {z['id']} — n_schriftfamilien = {n}, die Liste schriften "
                           f"ergibt {len(namen)}; die Zählregel der Messung hat sich geändert")
    schriften = []
    for name in namen:
        if GT.schriftgruppe(name) not in schriften:
            schriften.append(GT.schriftgruppe(name))
    wert = _pl(len(schriften), "Schrift", "Schriften")
    if len(schriften) >= MEHR_SCHRIFTEN:
        return _f("hinweis", wert, d=[", ".join(schriften)] + [h for h in _bem(z, "schriftfamilien")
                                                               if GT.H_PLATZHALTERNAME in h])
    return _f("kein_hinweis", wert)


def _eigene_farben(p):
    """The colours of the page content that can be an accent: no link colour, no field colour, no head mark."""
    return [f for f in p["farben"] if not f["nur_link"] and not f["feld"] and not f["nur_kopf"]]


def _familien(farben):
    """The colour families of a list of colours, each once, in their order: «Blau», «Blau, Rot»."""
    aus = []
    for f in farben:
        if f["familie"] not in aus:
            aus.append(f["familie"])
    return ", ".join(aus)


def _nebenfarben(p):
    """Why a Formular that shows colour has no accent: link colours, field colours, a mark in the head —
    named by their family, never by a colour code."""
    link = [f for f in p["farben"] if f["nur_link"]]
    feld = [f for f in p["farben"] if f["feld"]]
    kopf = [f for f in p["farben"] if f["nur_kopf"]]
    teile = ([f"die Farbe der Internet- und E-Mail-Adressen und der verlinkten Wörter ({_familien(link)})"] if link else []) + \
            ([f"die Farbe der Formularfelder ({_familien(feld)})"] if feld else []) + \
            ([f"eine kleine Farbmarke im Kopf der ersten Seite, in der Regel ein gezeichnetes Logo ({_familien(kopf)})"]
             if kopf else [])
    if not teile:
        return None
    return "Zählt nicht als Akzentfarbe: " + (", ".join(teile[:-1]) + " und " if len(teile) > 1 else "") + teile[-1] + "."


def _was_farbig(toene):
    """What the colours of one family colour: areas and lines, text, or both."""
    flaeche = sum(f["anteil_flaeche"] or 0 for f in toene)
    text = sum(f["anteil_text"] or 0 for f in toene)
    gemalt = "getönte Flächen" if all(GT.ist_blass(f["hex"]) for f in toene) else "Flächen oder Linien"
    if text and flaeche:
        return f"{gemalt} und Text ({_proz(text)} der Zeichen)"
    if text:
        return f"nur Text ({_proz(text)} der Zeichen)"
    return gemalt


def _m_akzentfarbe(z):
    p = z["p"]
    if p["farben"] is None:
        return _nm(z, "akzentfarbe")
    a = p["akzent"]
    if z["art"] != "pdf":                      # Office files count colours by other rules: named, not judged
        if not a:
            return _f("kein_hinweis", T_AKZENT_OHNE, pop=False)
        return _f("hinweis", a["familie"] + (" (blass)" if GT.ist_blass(a["hex"]) else ""), pop=False,
                  d=["Word- und Excel-Dateien zählen Farben nach anderen Regeln als PDF und sind nicht verglichen."])
    bild = [T_BILD] if z["bild1"] else []
    if not a:
        return _f(None, T_AKZENT_OHNE, d=[_nebenfarben(p)] + _bem(z, "akzentfarbe") + bild)
    toene = [f for f in _eigene_farben(p) if f["familie"] == a["familie"]]
    if sum(1 for f in toene if f["hex"] == a["hex"]) != 1 or any(f.get("gewicht") is None for f in toene):
        raise RuntimeError(f"akzentfarbe: Formular {z['id']} — die Akzentfarbe {a['hex']} steht nicht genau "
                           "einmal mit ihrem Gewicht unter den Farben ihrer Familie; die Regel der Messung hat "
                           "sich geändert")
    g = round(sum(f["gewicht"] for f in toene), 5)             # the family as a whole, as the measurement weighs it
    toene_n = _pl(len(toene), "Farbton", "Farbtöne")
    if g < AKZENT_MIN:
        return _f(None, T_AKZENT_OHNE,
                  d=[f"{a['familie']} ({toene_n}) auf {_proz_flaeche(g)} der Seitenfläche — {_was_farbig(toene)}; "
                     f"unter {_proz_flaeche(AKZENT_MIN)}, zählt nicht als Akzentfarbe.", _nebenfarben(p)]
                  + _bem(z, "akzentfarbe") + bild)
    return _f(None, a["familie"] + (" (blass)" if GT.ist_blass(a["hex"]) else ""), v=a["familie"],
              d=[f"{toene_n} der Familie {a['familie']}, {_proz_flaeche(g)} der Seitenfläche — {_was_farbig(toene)}"]
              + _bem(z, "akzentfarbe") + bild)


def _m_farbvielfalt(z):
    p = z["p"]
    n = p["n_farbfamilien"]
    if n is None:
        return _nm(z, "farbvielfalt")
    familien = []
    for f in _eigene_farben(p):
        if f["familie"] not in familien:
            familien.append(f["familie"])
    if len(familien) != n:
        raise RuntimeError(f"farbvielfalt: Formular {z['id']} — n_farbfamilien = {n}, die Liste farben ergibt "
                           f"{len(familien)}; die Zählregel der Messung hat sich geändert")
    wert = T_FARBEN_KEINE if n == 0 else _pl(n, "Farbfamilie", "Farbfamilien")
    if n >= MEHR_FARBEN:
        return _f("hinweis", wert, d=[", ".join(familien)] + _bem(z, "farbvielfalt")
                  + ([T_BILD] if z["bild1"] and z["art"] == "pdf" else []))
    return _f("kein_hinweis", wert)


def _m_bf_tags(z):
    t = z["p"]["barrierefrei"]["tags"]
    if t is None:
        return _nm(z, "bf_tags")
    return _f("vorhanden" if t else "luecke", "getaggt" if t else "nicht getaggt", d=_bem(z, "bf_tags"))


def _m_bf_sprache(z):
    b = z["p"]["barrierefrei"]
    if z["art"] == "pdf" and b["tags"] is None:          # a PDF that could not be read at all
        return _nm(z, "bf_sprache")
    s = b["sprache"]
    if s and b["sprache_passt"] is False:
        return _f("luecke", f"{s} — passt nicht zum Text", v="Angabe passt nicht zum Text", d=_bem(z, "bf_sprache"))
    if not s:
        teile = _hat(z, GT.H_SPRACHE_TEILE)              # a language on some structure elements, none for the whole
        return _f("luecke", "keine Sprachangabe für das ganze Dokument" if teile else "keine Sprachangabe",
                  v="keine Sprachangabe", d=_bem(z, "bf_sprache"))
    norm = _sprache_norm(s)
    return _f("vorhanden", s, v=norm,
              d=["Angegeben ist de-DE (Deutsch, Deutschland), nicht de-CH."] if norm == "de-DE" else None)


def _m_bf_titel(z):
    b = z["p"]["barrierefrei"]
    art = b["titel_art"]
    if art is None:
        return _nm(z, "bf_titel")
    if art not in T_TITEL:
        raise RuntimeError(f"bf_titel: Formular {z['id']} — unbekannte titel_art «{art}»")
    if art == "aussagekraeftig":
        return _f("vorhanden", T_TITEL[art], d=_bem(z, "bf_titel"))
    zitat = []
    if art != "leer" and b["titel"]:
        zitat = [T_TITEL_PERSON if GT.person_im_titel(b["titel"]) else f"Titel der Datei: {_zitat(b['titel'])}"]
    return _f("luecke", T_TITEL[art], d=zitat + _bem(z, "bf_titel"))


def _m_bf_feldnamen(z):
    b = z["p"]["barrierefrei"]
    n, mit = b["felder"], b["felder_beschriftet"]
    if n is None or mit is None:
        return _nm(z, "bf_feldnamen")
    if n == 0:
        return _entf("kein ausfüllbares PDF")
    wert = f"{mit} von {n} {'Feld' if n == 1 else 'Feldern'} beschrieben"
    if mit == n:
        return _f("vorhanden", wert, v="alle Felder beschrieben", d=_bem(z, "bf_feldnamen"))
    return _f("luecke", wert, v="kein Feld beschrieben" if mit == 0 else "ein Teil der Felder beschrieben",
              d=_bem(z, "bf_feldnamen"))


def _m_bf_textebene(z):
    t = z["p"]["barrierefrei"]["textebene"]
    if t is None:
        return _nm(z, "bf_textebene")
    if not t:
        return _f("luecke", "kein auslesbarer Text", d=_bem(z, "bf_textebene"))
    if z["unles"]:                               # the text is there, but stored as control characters
        return _f("luecke", "Text nicht lesbar abgelegt", d=_bem(z, "bf_textebene"))
    return _f("vorhanden", "Text auslesbar", d=_bem(z, "bf_textebene"))


def _m_bf_ueberschriften(z):
    u = z["p"]["barrierefrei"]["ueberschriften"]
    if u is None:
        return _nm(z, "bf_ueberschriften")
    if not u:
        return _f("luecke", "keine Überschrift")
    if _hat(z, GT.H_EINE_UEBERSCHRIFT):
        return _f("vorhanden", "eine einzige Überschrift", d=_bem(z, "bf_ueberschriften"))
    return _f("vorhanden", "Überschriften vorhanden")


_TEL_ZITAT = re.compile(r" (?:steht ohne jede Bezeichnung|steht nicht im Text daneben): «")


def _tel_satz(t):
    """The one sentence that quotes the line of a printed number (_TEL_ZITAT recognises it)."""
    if t["erklaerung"] == "ohne":
        return f"{t['nummer']} steht ohne jede Bezeichnung: {_zitat(t['kontext'])}"
    art = "Faxnummer" if t["art"] == "fax" else "Telefonnummer"
    return f"{t['nummer']} ist als {art} bezeichnet; wessen Nummer es ist, steht nicht im Text daneben: {_zitat(t['kontext'])}"


def _m_tel_erklaerung(z):
    tel = z["p"]["telefon"]
    if tel is None:
        return _nm(z, "tel_erklaerung")
    fremd = sorted({t["erklaerung"] for t in tel} - set(_RANG))
    if fremd:
        raise RuntimeError(f"tel_erklaerung: Formular {z['id']} — unbekannte erklaerung {fremd}")
    offen = [t for t in tel if t["erklaerung"] != "erklaert"]
    if offen:
        stufe = min((t["erklaerung"] for t in offen), key=_RANG.get)
        return _f(_TEL_URTEIL[stufe], T_ERKLAERUNG[stufe],
                  d=[_tel_satz(t) for t in offen] + ([T_NUR_TEXT] if stufe == "bezeichnung" else [])
                  + _bem(z, "tel_erklaerung"))
    if z["unles"]:
        return _nm(z, "tel_erklaerung")
    if not tel:
        return _entf(T_OHNE_NUMMER)
    return _f("vorhanden", T_ERKLAERUNG["erklaert"], d=_bem(z, "tel_erklaerung"))


def _m_tel_format(z):
    tel = z["p"]["telefon"]
    if tel is None or z["unles"]:
        return _nm(z, "tel_format")
    if not tel:
        return _entf(T_OHNE_NUMMER)
    arten = sorted({t["format"] for t in tel})
    return _f(None, T_FORMAT.get(arten[0], arten[0]) if len(arten) == 1 else "gemischt")


def _m_fax(z):
    tel = z["p"]["telefon"]
    if tel is None:
        return _nm(z, "fax")
    nummern = [t["nummer"] for t in tel if t["art"] == "fax"]
    if nummern:
        return _f("hinweis", "Faxnummer gedruckt", d=[", ".join(nummern)])
    if z["unles"]:
        return _nm(z, "fax")
    return _f("kein_hinweis", "keine Faxnummer im Text")


def _m_email_art(z):
    mails = z["p"]["email"]
    if mails is None:
        return _nm(z, "email_art")
    pers = [m["domain"] for m in mails if m["art"] == "persoenlich"]
    if pers:
        return _f("hinweis", "persönliche Adresse",
                  d=[_pl(len(pers), "persönliche Adresse", "persönliche Adressen") + " ("
                     + ", ".join(sorted(set(pers))) + ")"])
    if z["unles"]:
        return _nm(z, "email_art")
    return _f("kein_hinweis", "nur Adressen von Stellen" if mails else "keine E-Mail-Adresse im Text")


def _m_seitenformat(z):
    sf = z["p"]["seitenformat"]
    if not sf:
        return _nm(z, "seitenformat")
    if sf["name"] == "anderes":
        return _f(None, f"anderes Format ({sf['breite_mm']} × {sf['hoehe_mm']} mm)", v="anderes Format",
                  d=_bem(z, "seitenformat"))
    return _f(None, sf["name"], d=_bem(z, "seitenformat"))


def _m_stand_angabe(z):
    s = z["p"]["elemente"]["stand_angabe"]
    if s["vorhanden"] is None or (z["unles"] and not s["vorhanden"]):
        return _nm(z, "stand_angabe")
    if s["vorhanden"]:
        # the initials of an author behind the mark are not quoted
        return _f(None, "vorhanden", d=[f"gedruckt: {_zitat(_KUERZEL.sub('/…', s['text']))}"] if s["text"] else None)
    return _f(None, "fehlt")


def _m_seitenzahlen(z):
    s = z["p"]["elemente"]["seitenzahlen"]
    if s["vorhanden"] is None:
        if z["p"]["seiten"] == 1:
            return _entf("einseitig")
        return _nm(z, "seitenzahlen")
    if s["vorhanden"]:
        return _f(None, T_SEITENZAHLEN_JA, d=[f"gedruckt: {_zitat(s['muster'])}"] if s["muster"] else None)
    if z["unles"]:
        return _nm(z, "seitenzahlen")
    return _f(None, "keine Seitenzahlen")


def _m_absender(z):
    a = z["p"]["elemente"]["absender"]
    k, dst = a["kanton"], a["dienststelle"]
    if k is None:
        return _nm(z, "absender")
    if dst is None:
        return _nm(z, "absender", ["Die Databank kennt für dieses Formular keine Dienststelle; ob die erste "
                                   "Seite sie nennt, liess sich nicht prüfen."])
    if z["unles"] and not (k and dst):
        return _nm(z, "absender")
    return _f(None, T_ABSENDER[(bool(k), bool(dst))], d=_bem(z, "absender"))


_FN = {"schrift": _m_schrift, "groesse": _m_groesse, "kleinschrift": _m_kleinschrift,
       "eingebettet": _m_eingebettet, "schriftfamilien": _m_schriftfamilien, "akzentfarbe": _m_akzentfarbe,
       "farbvielfalt": _m_farbvielfalt, "bf_tags": _m_bf_tags, "bf_sprache": _m_bf_sprache,
       "bf_titel": _m_bf_titel, "bf_feldnamen": _m_bf_feldnamen, "bf_textebene": _m_bf_textebene,
       "bf_ueberschriften": _m_bf_ueberschriften, "tel_erklaerung": _m_tel_erklaerung,
       "tel_format": _m_tel_format, "fax": _m_fax, "email_art": _m_email_art, "seitenformat": _m_seitenformat,
       "stand_angabe": _m_stand_angabe, "seitenzahlen": _m_seitenzahlen, "absender": _m_absender}
assert set(_FN) == set(MERKMAL_KEYS) and set(BEMERKUNG) == set(MERKMAL_KEYS)
assert {k for k, m in _M.items() if m[2] in ("praxis", "regel_offen")} == set(ENTSCHEID)


# ======================================================================= table

_DATEIART = {"pdf": "pdf", "pdf_bild": "pdf", "word": "word", "excel": "excel"}


def _zeilen(conn):
    """{form_id: (messart, methode, profil)} of the measured Formulare; {} when the
    databank has no table form_gestaltung yet."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='form_gestaltung'").fetchone():
        return {}
    aus = {}
    for fid, messart, methode, profil in conn.execute(
            "SELECT form_id, messart, methode, profil FROM form_gestaltung ORDER BY form_id"):
        if messart not in MESSART:
            raise RuntimeError(f"form_gestaltung: Formular {fid} hat die unbekannte Messart «{messart}»")
        try:
            p = json.loads(profil)
        except (TypeError, ValueError) as e:
            raise RuntimeError(f"form_gestaltung: das Profil von Formular {fid} ist kein JSON ({e})")
        if not isinstance(p, dict) or p.get("messart") != messart:
            raise RuntimeError(f"form_gestaltung: Profil und Spalte messart von Formular {fid} widersprechen sich")
        aus[fid] = (messart, methode, p)
    return aus


def _tabelle(forms, zeilen):
    """{form_id: {Merkmal: cell}} — every Formular, every Merkmal; the practice is not judged yet."""
    bekannt = {fm["id"] for fm in forms}
    fremd = sorted(set(zeilen) - bekannt)
    if fremd:
        raise RuntimeError(f"form_gestaltung: Messzeilen ohne Formular im Export: {fremd[:8]}")
    tab = {}
    for fm in forms:
        fid, zeile = fm["id"], zeilen.get(fm["id"])
        if not fm.get("source_file"):
            if zeile:
                raise RuntimeError(f"form_gestaltung: Formular {fid} hat eine Messzeile, aber keine Datei")
            tab[fid] = {k: _entf(T_EFORMULAR) for k in MERKMAL_KEYS}
            continue
        art = _DATEIART.get(zeile[0]) if zeile else None
        if art is None:                                    # no row, or a row 'nicht_messbar': the file type decides
            art = fm.get("file_type") if fm.get("file_type") in ("pdf", "word", "excel") else None
        z = None
        if zeile and zeile[0] != "nicht_messbar":
            hin = _hin_lesen(zeile[2])
            try:
                z = {"id": fid, "p": zeile[2], "hin": hin, "art": art,
                     "unles": zeile[2]["barrierefrei"]["text_lesbar"] is False,
                     "bild1": any(GT.H_BILD_SEITE1 in h for h in hin)}
            except (KeyError, TypeError) as e:
                raise RuntimeError(f"form_gestaltung: das Profil von Formular {fid} hat nicht den Aufbau, den diese "
                                   f"Fassung liest ({type(e).__name__}: {e}) — mit einer älteren Methode gemessen? "
                                   "scan_gestaltung.py misst neu")
        zellen = {}
        for key in MERKMAL_KEYS:
            nur = _M[key][3]
            if nur and art is not None and art not in nur:
                zellen[key] = _entf(T_NUR[nur])
            elif zeile is None:
                zellen[key] = _f("nicht_gemessen", URTEIL["nicht_gemessen"][0])
            elif z is None:
                zellen[key] = _f("nicht_messbar", URTEIL["nicht_messbar"][0], d=[_ohne_klammer(h) for h in _hin_lesen(zeile[2])])
            else:
                try:
                    zellen[key] = _FN[key](z)
                except (KeyError, TypeError, AttributeError) as e:
                    raise RuntimeError(f"{key}: das Profil von Formular {fid} hat nicht den vereinbarten Aufbau "
                                       f"({type(e).__name__}: {e})")
        tab[fid] = zellen
    return tab


def _praxis(zaehlung):
    """(value, n) of the clear practice among {value: n}, or None."""
    n = sum(zaehlung.values())
    if n < PRAXIS_MIN:
        return None
    wert, k = min(zaehlung.items(), key=lambda x: (-x[1], x[0]))
    return (wert, k) if Fraction(k, n) >= PRAXIS_SCHWELLE else None


def _praxis_setzen(forms, tab):
    """Second pass: judge every value of a praxis Merkmal against the practice. -> {Merkmal: (value, n) | None}"""
    praxis = {}
    for key in MERKMAL_KEYS:
        if _M[key][2] != "praxis":
            continue
        offen = [tab[fm["id"]][key] for fm in forms if tab[fm["id"]][key]["u"] is None]
        praxis[key] = _praxis(Counter(c["v"] for c in offen))
        for c in offen:
            if praxis[key]:
                c["u"] = "entspricht" if c["v"] == praxis[key][0] else "weicht_ab"
                c["p"] = praxis[key][0]
            else:
                c["u"] = "uneinheitlich"
    return praxis


# ===================================================================== results

def _kompakt(messart, zellen):
    merkmale = [{"k": k, "u": c["u"], "w": c["w"], "p": c["p"], "d": c["d"]}
                for k, c in zellen.items() if c["u"] not in NICHT_EXPORTIERT]
    return {"messart": messart, "n": _n_formular(merkmale), "merkmale": merkmale}


def _n_formular(merkmale):
    """act, betroffen, open — and dec: the Merkmale of the Formular that wait for the canton (uneinheitlich,
    betroffen), the open decisions whose lists name it."""
    ton = Counter(URTEIL[m["u"]][1] for m in merkmale)
    return {"act": ton["act"], "betroffen": sum(1 for m in merkmale if m["u"] == "betroffen"),
            "dec": sum(1 for m in merkmale if m["u"] in ("uneinheitlich", "betroffen")), "open": ton["open"]}


def _mindestmerkmale(g):
    """A PDF whose tags, document language and document title are all «vorhanden» (kennzahlen.pdf_mindestmerkmale)."""
    da = {m["k"] for m in g["merkmale"] if m["u"] == "vorhanden"}
    return g["messart"] in ("pdf", "pdf_bild") and {"bf_tags", "bf_sprache", "bf_titel"} <= da


def _hat_urteil(g, urteil):
    return any(m["u"] == urteil for m in g["merkmale"])


def _verteilung(zellen_mit_id, mit_formularen=False):
    """[{w, n(, formulare)}] of (form id, cell) pairs, most frequent first, ties by value."""
    je = {}
    for fid, c in zellen_mit_id:
        je.setdefault(c["v"], []).append(fid)
    aus = []
    for w, ids in sorted(je.items(), key=lambda x: (-len(x[1]), x[0])):
        aus.append({"w": w, "n": len(ids), "formulare": sorted(ids)} if mit_formularen else {"w": w, "n": len(ids)})
    return aus


def _hinweise(zeile):
    return _hin_lesen(zeile[2]) if zeile else []


def _zusatz_tel(forms, zeilen):
    """Overview fact of tel_format: one number printed in several notations across Formulare."""
    je, muster = {}, Counter()
    for fm in forms:
        zeile = zeilen.get(fm["id"])
        for t in (zeile[2].get("telefon") or []) if zeile else []:
            s = _rein(GT.schreibweise(t["nummer"]))
            muster[s] += 1
            je.setdefault(t["e164"], {}).setdefault(s, set()).add(fm["id"])
    mehrfach = [{"nummer": e164, "formulare": sorted(set().union(*arten.values())),
                 "schreibweisen": [{"w": s, "n": len(ids)}
                                   for s, ids in sorted(arten.items(), key=lambda x: (-len(x[1]), x[0]))]}
                for e164, arten in sorted(je.items()) if len(arten) > 1]
    return {"label": "Dieselbe Nummer in mehreren Schreibweisen", "n_nummern": len(je), "n_mehrfach": len(mehrfach),
            "schreibweisen": [{"w": s, "n": n} for s, n in sorted(muster.items(), key=lambda x: (-x[1], x[0]))],
            "nummern": mehrfach}


def _zusatz_seitenzahlen(forms, tab, zeilen):
    """Overview fact of seitenzahlen: the numbering patterns in use (of the Formulare that are compared)."""
    muster = Counter()
    for fm in forms:
        zeile = zeilen.get(fm["id"])
        m = ((zeile[2].get("elemente") or {}).get("seitenzahlen") or {}).get("muster") if zeile else None
        if m and tab[fm["id"]]["seitenzahlen"]["pop"]:
            muster[_rein(GT.seitenzahl_schema(m))] += 1
    return {"label": "Schreibweisen der Seitenzahl",
            "muster": [{"w": s, "n": n} for s, n in sorted(muster.items(), key=lambda x: (-x[1], x[0]))]}


def _zusatz_akzent(forms, tab, zeilen):
    """Overview facts of akzentfarbe: what stands beside the comparison of the PDF Formulare."""
    n = Counter()
    for fm in forms:
        c, zeile = tab[fm["id"]]["akzentfarbe"], zeilen.get(fm["id"])
        if not zeile or zeile[2].get("farben") is None:
            continue
        n["farben_gemessen"] += 1
        if not c["pop"]:
            n["office"] += 1
            n["office_mit_farbe" if c["u"] == "hinweis" else "office_ohne_farbe"] += 1
            continue
        farben = zeile[2]["farben"]
        n["pdf_mit_linkfarbe"] += any(f["nur_link"] for f in farben)
        n["pdf_mit_feldfarbe"] += any(f["feld"] for f in farben)
        n["pdf_mit_kopfmarke"] += any(f["nur_kopf"] for f in farben)
        if c["v"] == T_AKZENT_OHNE:
            n["pdf_ohne_akzent"] += 1
            n["pdf_ohne_akzent_mit_bild"] += any(GT.H_BILD_SEITE1 in h for h in _hinweise(zeile))
            n["pdf_ohne_akzent_farbe_unter_schwelle"] += bool(zeile[2]["akzent"])
    schluessel = ("farben_gemessen", "office", "office_mit_farbe", "office_ohne_farbe", "pdf_mit_linkfarbe",
                  "pdf_mit_feldfarbe", "pdf_mit_kopfmarke", "pdf_ohne_akzent", "pdf_ohne_akzent_mit_bild",
                  "pdf_ohne_akzent_farbe_unter_schwelle")
    return dict({"label": "Neben dem Vergleich der PDF-Formulare"}, **{k: n[k] for k in schluessel})


def _zusatz_tags(forms, tab, zeilen):
    """Overview facts of bf_tags: what «getaggt» does not say."""
    n = Counter()
    for fm in forms:
        if tab[fm["id"]]["bf_tags"]["u"] == "vorhanden":
            hin = _hinweise(zeilen.get(fm["id"]))
            n["getaggt"] += 1
            n["ohne_formularfelder"] += any(GT.H_TAGS_OHNE_FELDER in h for h in hin)
            n["ohne_ueberschriften"] += any(GT.H_TAGS_OHNE_UEBERSCHRIFT in h for h in hin)
    return {"label": "Getaggt, aber ohne Formularfelder oder ohne Überschriften im Strukturbaum",
            "getaggt": n["getaggt"], "ohne_formularfelder": n["ohne_formularfelder"],
            "ohne_ueberschriften": n["ohne_ueberschriften"]}


def _zusatz_tel_erklaerung(forms, dienststellen, tab):
    """Overview fact of tel_erklaerung: where the remark «Stelle nicht im Text bei der Nummer» stands."""
    je = []
    for d in dienststellen:
        n = sum(1 for fid in d["formulare"] if fid in tab and tab[fid]["tel_erklaerung"]["u"] == "hinweis")
        if n:
            je.append({"name": d["name"], "slug": d["slug"], "n": n})
    je.sort(key=lambda x: (-x["n"], x["slug"]))
    return {"label": "Nummer als Telefonnummer bezeichnet, Stelle nicht im Text daneben", "dienststellen": je}


def _stand(conn):
    """The day of the measurement as scan_gestaltung.py recorded it in table meta (ISO date), or None."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone():
        return None
    row = conn.execute("SELECT value FROM meta WHERE key = ?", [GT.META_STAND]).fetchone()
    wert = row[0] if row else None
    return wert if isinstance(wert, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", wert) else None


def _grenzen(forms, dienststellen, zeilen, tab):
    """What a reader must know before reading a verdict — plain sentences; figures only where counted here."""
    art = Counter(z[0] for z in zeilen.values())
    n_pdf = art["pdf"] + art["pdf_bild"]
    n_bild = sum(1 for z in zeilen.values() if z[0] in ("pdf", "pdf_bild")
                 and any(GT.H_BILD_SEITE1 in h for h in _hinweise(z)))
    n_unles = sum(1 for z in zeilen.values() if (z[2].get("barrierefrei") or {}).get("text_lesbar") is False)
    n_eform = sum(1 for fm in forms if not fm.get("source_file"))
    akz = _zusatz_akzent(forms, tab, zeilen)
    tel = _zusatz_tel_erklaerung(forms, dienststellen, tab)["dienststellen"]
    n_tel = sum(d["n"] for d in tel)
    bild = (f" {n_bild} von {n_pdf} PDF-Formularen tragen auf der ersten Seite ein Bild, in der Regel das Logo."
            if n_bild else "")
    ohne_akzent = (f" Bei {akz['pdf_ohne_akzent_mit_bild']} der {akz['pdf_ohne_akzent']} PDF-Formulare ohne "
                   "Akzentfarbe trägt die erste Seite ein Bild; ob es farbig ist, ist nicht gemessen."
                   if akz["pdf_ohne_akzent"] else "")
    telefon = (f" Das betrifft {_pl(n_tel, 'Formular', 'Formulare')}, {tel[0]['n']} davon bei «{tel[0]['name']}»."
               if n_tel else "")
    ohne = ([_pl(art["nicht_messbar"], "Datei", "Dateien") + " in einem alten Format (.doc, .xls)"]
            if art["nicht_messbar"] else []) + \
           ([f"{art['pdf_bild']} PDF ohne auslesbaren Text (Bilder, z. B. Scans)"] if art["pdf_bild"] else []) + \
           ([f"der Text von {n_unles} PDF, " + ("das ihn nicht lesbar ablegt" if n_unles == 1 else
                                                "die ihn nicht lesbar ablegen")] if n_unles else [])
    nicht_messbar = ("Nicht messbar: " + (", ".join(ohne[:-1]) + " und " if len(ohne) > 1 else "") + ohne[-1] + ". "
                     if ohne else "")
    eformulare = ([f"Die {n_eform} eFormulare der Plattform haben keine eigene Datei: Ihr Erscheinungsbild ist das "
                   "der Plattform und ist hier nicht beurteilt."] if n_eform > 1 else
                  ["Das eFormular der Plattform hat keine eigene Datei: Sein Erscheinungsbild ist das der Plattform "
                   "und ist hier nicht beurteilt."] if n_eform else [])
    return [
        "Massstab ist die Praxis der gemessenen Formulare, nicht das Corporate Design des Kantons: Dessen Handbuch "
        "liegt der Databank nicht vor. «Entspricht der Praxis» heisst, dass ein Formular in diesem einen Merkmal "
        "denselben Wert hat wie mindestens zwei Drittel der gemessenen Formulare — nicht, dass es einer Vorgabe "
        "genügt. «Weicht ab» heisst ebenso wenig, dass es eine verletzt.",
        "Wo es keine klare Praxis gibt, weiss die Databank nur, dass ihr keine Vorgabe vorliegt und dass die "
        "Formulare keine einheitliche Regel zeigen — nicht, ob der Kanton etwas festgelegt hat.",
        "Nicht jedes Formular stammt vom Kanton: Formulare des Bundes, anderer Kantone, ausländischer Behörden "
        "oder Dritter sind gleich gemessen; die Databank unterscheidet die Herausgeberschaft nicht.",
        "Alles, was in einem Bild steckt, ist nicht gemessen: Logos und ihre Farben, Schrift, Telefonnummern und "
        "E-Mail-Adressen in Bildern." + bild,
        "Welches Logo ein Formular trägt und in welcher Farbe, ist nicht erfasst. Ein Logo, das nicht als Bild eingefügt, sondern gezeichnet ist, zählt "
        "als kleine Farbmarke im Kopf der ersten Seite ebenfalls nicht als Akzentfarbe.",
        V_FARBEN + " «Keine Akzentfarbe» heisst deshalb nicht «schwarz-weiss»: Farbe kann im Logo stehen, in "
        "Formularfeldern, in Internet-Adressen und verlinkten Wörtern oder auf sehr kleinen Flächen." + ohne_akzent,
        f"Eine Farbfamilie zählt ab {_proz_flaeche(AKZENT_MIN)} der Seitenfläche als Akzentfarbe; die Grenze ist eine Setzung der "
        "Databank. Die Flächen sind Obergrenzen, weil überlappende Formen nicht verrechnet sind. Farbfamilien "
        "(Rot, Blau, Gelb …) sind grobe Namen: Ein Farbton nahe an einer Grenze kann in die Nachbarfamilie fallen, "
        "ein blasser Farbton wirkt oft eher grau oder beige als nach seiner Familie, und Druckfarben (CMYK, "
        "Sonderfarben) sind nur näherungsweise umgerechnet. Farbverläufe und Muster sind nicht gemessen.",
        "Word- und Excel-Dateien zählen Farben nach anderen Regeln als PDF (eine gefüllte Zelle genügt) und haben "
        "keine messbaren Flächen. Ihre Farben sind genannt, aber nicht mit den PDF-Formularen verglichen.",
        "Die Schrift ist die, die die Datei nennt — nicht, was ein Gerät ohne diese Schrift anzeigt. " + _T_SCHNITT
        + " " + _T_ANHANG + " Schrift und Text in Formularfeldern sind nicht gemessen.",
        "Schriftgrössen sind auf einen halben Punkt gerundet: 7.75 pt zählt als 8 pt. Die Grundgrösse ist die "
        "Grösse mit den meisten Zeichen. Die Grenzen für kleine Schrift (8 pt, 5 % der Zeichen) sind Setzungen der "
        "Databank; auch Fusszeilen, Fussnoten und Feldhinweise zählen.",
        "Die Merkmale zur Barrierefreiheit sind maschinell prüfbare Mindestmerkmale. Ein fehlendes Merkmal ist "
        "eine Lücke; ein vorhandenes ist kein Nachweis der Barrierefreiheit. Nicht geprüft sind Lesereihenfolge, "
        "Alternativtexte, Kontraste, die Qualität der Tags und der Feldbeschreibungen sowie die Normen eCH-0059, "
        "WCAG und PDF/UA.",
        "Ob ein Dokumenttitel das Formular nennt, misst sich am Namen des Formulars in der Databank; ein Titel in "
        "Abkürzungen kann deshalb als «nennt das Formular nicht» gelten. Titel sind wörtlich zitiert, so wie sie "
        "in der veröffentlichten Datei stehen — ausser ein Titel sieht aus wie der Name einer Person.",
        "Ob eine Telefonnummer erklärt ist, folgt der Reihenfolge des Textes in der Datei. Steht der Name der "
        "Stelle nur im Logo, lautet der Befund «Stelle nicht im Text bei der Nummer» — ein Hinweis, keine Lücke."
        + telefon + " Steht zufällig eine Feldbeschriftung direkt über einer Adresse, kann eine Nummer als erklärt "
        "gelten, die es nicht ist.",
        "Der Absender ist nur im Text der ersten Seite gesucht. Ein Name, der nur im Logo steht oder anders "
        "lautet als in der Databank (zum Beispiel «Sicherheitspolizei» für die Polizei oder ein früherer Amtsname), "
        "ist nicht erkannt.",
        "Persönliche E-Mail-Adressen sind eine Untergrenze: Als persönlich zählt eine Adresse nur mit Beleg. "
        "Adressen selbst sind nirgends gespeichert.",
        "Seitenzahlen von Word-Dateien stammen aus den Dokumenteigenschaften (Stand beim letzten Speichern); "
        "Excel-Dateien haben keine feste Seitenzahl und sind bei den Seitenzahlen nicht verglichen.",
        nicht_messbar + "Wo sich ein Merkmal nicht messen lässt, steht «nicht messbar» statt eines Befunds: "
        "Nichts gefunden heisst nicht, dass nichts da ist.",
    ] + eformulare


def _entscheid_text(key, m_art, eintrag, pop, urteile):
    """What is open about ONE decision of a Merkmal: the threshold the Formulare miss. The values themselves stand
    beside it as a list (entscheide[].verteilung), the missing rule is said once for all decisions
    (labels.entscheide), what is to be decided in entscheide[].frage."""
    mehr = ENTSCHEID[key][2]
    n = len(pop)
    if m_art == "regel_offen":
        stark = sum(1 for _fid, c in pop if c["u"] == "betroffen" and c["v"] in ("20 bis unter 50 % der Zeichen",
                                                                                 "50 % der Zeichen und mehr"))
        return (f"{urteile['betroffen']} von {n} gemessenen Formularen setzen mindestens {_proz(KLEIN_ANTEIL)} "
                f"ihrer Zeichen kleiner als {KLEIN_PT} pt, {stark} davon 20 % und mehr. Auch Fusszeilen, Fussnoten "
                "und Feldhinweise zählen.")
    vert = eintrag["verteilung"]
    if n < PRAXIS_MIN:
        kopf = (f"Keine klare Praxis: Gemessen sind nur {_pl(n, 'Formular', 'Formulare')} — zu wenige für eine "
                f"Praxis (unter {PRAXIS_MIN}).")
    else:
        kopf = f"Keine klare Praxis: Unter den {n} gemessenen Formularen erreicht kein Wert zwei Drittel."
        if vert and vert[0]["n"] / n >= KNAPP:                  # close: say how close
            noetig = -(-2 * n // 3)
            kopf += (f" Knapp: «{vert[0]['w']}» haben {vert[0]['n']} Formulare, für zwei Drittel wären es {noetig}.")
    return " ".join([kopf] + ([mehr] if mehr else []))


def _tuer(gruppe, M, K):
    """The ONE figure of a group's door on the page: {n, text (what follows the number), quelle (a verdict of a
    Merkmal of the group, or a kennzahl)} — or None. Invariant 10 recounts it."""
    def tuer(n, text, **quelle):
        return {"n": n, "text": text, "quelle": quelle}

    def wa(key):
        return M[key]["urteile"].get("weicht_ab", 0)

    def praxis(key):
        return (M.get(key) or {}).get("praxis") and M[key]["praxis"]["w"]
    if gruppe == "schrift" and praxis("schrift"):
        n = wa("schrift")
        return tuer(n, f"{'Formular' if n == 1 else 'Formulare'} in einer anderen Schrift als {praxis('schrift')}",
                    merkmal="schrift", urteil="weicht_ab")
    if gruppe == "farben" and praxis("akzentfarbe"):
        n, p = wa("akzentfarbe"), praxis("akzentfarbe")
        wort = "PDF-Formular" if n == 1 else "PDF-Formulare"
        return tuer(n, f"{wort} mit einer Akzentfarbe; die Praxis ist «{p}»" if p == T_AKZENT_OHNE
                    else f"{wort} mit einer anderen Akzentfarbe als {p}", merkmal="akzentfarbe", urteil="weicht_ab")
    if gruppe == "barrierefrei" and K["pdf"]:
        n = K["pdf_mindestmerkmale"]
        return tuer(n, f"von {K['pdf']} PDF-Formularen {'trägt' if n == 1 else 'tragen'} Struktur-Tags, eine "
                       "Dokumentsprache und einen Dokumenttitel, der das Formular nennt", kennzahl="pdf_mindestmerkmale")
    if gruppe == "kontakt" and "tel_erklaerung" in M:
        n = M["tel_erklaerung"]["urteile"].get("luecke", 0)
        return tuer(n, f"{'Formular druckt' if n == 1 else 'Formulare drucken'} eine Telefonnummer ohne jede "
                       "Bezeichnung", merkmal="tel_erklaerung", urteil="luecke")
    if gruppe == "aufbau" and praxis("seitenzahlen") == T_SEITENZAHLEN_JA:
        n = wa("seitenzahlen")
        return tuer(n, f"von {M['seitenzahlen']['n_gemessen']} mehrseitigen Formularen {'trägt' if n == 1 else 'tragen'}"
                       " keine Seitenzahlen", merkmal="seitenzahlen", urteil="weicht_ab")
    # otherwise: the first comparison with a practice of the group, or its first check with a Lücke
    ms = [m for m in M.values() if m["gruppe"] == gruppe]
    p = next((m for m in ms if m["praxis"]), None)
    if p:
        n = wa(p["key"])
        return tuer(n, f"{'Formular weicht' if n == 1 else 'Formulare weichen'} beim Merkmal «{p['label']}» von der "
                       "Praxis ab", merkmal=p["key"], urteil="weicht_ab")
    lu = next((m for m in ms if m["urteile"].get("luecke")), None)
    if lu:
        n = lu["urteile"]["luecke"]
        return tuer(n, f"{'Formular' if n == 1 else 'Formulare'} mit einer Lücke beim Merkmal «{lu['label']}»",
                    merkmal=lu["key"], urteil="luecke")
    return None


def _uebersicht(conn, forms, dienststellen, zeilen, tab, praxis, per_form):
    """The overview (top-level «gestaltung»):
    stand, methode — when and with which method the Formulare were measured;
    bestand       — formulare, mit_datei, ohne_datei (eFormulare), gemessen (has a row), messart counts,
                    dienststellen (entries of the input), dienststellen_gemessen (those with at least
                    one measured Formular) and dienststellen_ohne_formular (those without a Formular);
    gruppen       — [{key, label, frage(, vorbehalt), kennzahl}], the five groups in reading order; kennzahl
                    is the ONE figure of the group's door ({n, text, quelle} or null, _tuer);
    merkmale      — per Merkmal: key, gruppe, label, art, frage, erklaerung, basis (what n_gemessen
                    counts), n_gemessen and verteilung [{w, n}] (the measured population; for a praxis
                    Merkmal the Formulare that are compared), praxis {w, n, anteil} | null,
                    n {ok, act, dec, betroffen, hinweis, open}, urteile {verdict: count} over ALL
                    Formulare, formulare {verdict: [form ids]} for the verdicts in LISTEN(, zusatz);
    kennzahlen    — pdf, pdf_mindestmerkmale (tags + language + title all «vorhanden»), ok / act /
                    abweichungen / luecken / betroffen / hinweis / open (Formular × Merkmal), dec (open
                    decisions), formulare_mit_act / _mit_abweichung / _mit_luecke (Formulare with at least
                    one such verdict); their labels: labels.kennzahl;
    entscheide    — the open decisions of the canton: key (the Merkmal), label, was, verteilung
                    [{w, n, formulare}];
    dienststellen — per Dienststelle of the export: name, slug, n_formulare, n_gemessen, n {act, open},
                    n_nicht_messbar, n {act, abweichungen, luecken, open}, act_je_formular (act ÷ the
                    Formulare measured in content, null without one), schriften /
                    groessen / akzente (distinct values among its Formulare), top;
    grenzen       — what a reader must know before reading a verdict;
    labels        — urteil {key: {label, ton}}, ton, ton_zusatz, urteil_gesamt, urteil_nomen, art, art_erklaerung, messart,
                    gruppe, merkmal, kennzahl, eformular (the sentence that stands for an eFormular, which has
                    no look of its own), entscheide (the sentence on the missing rule)."""
    art = Counter(z[0] for z in zeilen.values())
    methoden = sorted({z[1] for z in zeilen.values() if z[1]})
    mit_datei = sum(1 for fm in forms if fm.get("source_file"))
    merkmale, entscheide = [], []
    for key, gruppe, m_art, _nur, label, frage, erklaerung, basis in MERKMALE:
        zellen = [(fm["id"], tab[fm["id"]][key]) for fm in forms]
        urteile = Counter(c["u"] for _fid, c in zellen)
        pop = [(fid, c) for fid, c in zellen if c["pop"]]
        dec = 0
        if m_art == "praxis":
            dec = 1 if pop and not praxis[key] else 0
        elif m_art == "regel_offen":
            dec = 1 if urteile["betroffen"] else 0
        eintrag = {
            "key": key, "gruppe": gruppe, "label": label, "art": m_art, "frage": frage, "erklaerung": erklaerung,
            **({"urteil_labels": URTEIL_MERKMAL[key]} if key in URTEIL_MERKMAL else {}),
            "basis": basis, "n_gemessen": len(pop), "verteilung": _verteilung(pop),
            "praxis": ({"w": praxis[key][0], "n": praxis[key][1], "anteil": round(praxis[key][1] / len(pop), 4)}
                       if m_art == "praxis" and praxis[key] else None),
            "n": {"ok": urteile["entspricht"] + urteile["vorhanden"], "act": urteile["weicht_ab"] + urteile["luecke"],
                  "dec": dec, "betroffen": urteile["betroffen"], "hinweis": urteile["hinweis"],
                  "open": urteile["nicht_messbar"] + urteile["nicht_gemessen"]},
            "urteile": {u: urteile[u] for u in URTEIL if urteile[u]},
            "formulare": {u: sorted(fid for fid, c in zellen if c["u"] == u) for u in LISTEN if urteile[u]},
        }
        if key == "tel_format":
            eintrag["zusatz"] = _zusatz_tel(forms, zeilen)
        elif key == "seitenzahlen":
            eintrag["zusatz"] = _zusatz_seitenzahlen(forms, tab, zeilen)
        elif key == "akzentfarbe":
            eintrag["zusatz"] = _zusatz_akzent(forms, tab, zeilen)
        elif key == "bf_tags":
            eintrag["zusatz"] = _zusatz_tags(forms, tab, zeilen)
        elif key == "tel_erklaerung":
            eintrag["zusatz"] = _zusatz_tel_erklaerung(forms, dienststellen, tab)
        merkmale.append(eintrag)
        if dec:
            vert = (_verteilung([(fid, c) for fid, c in pop if c["u"] == "betroffen"], True)
                    if m_art == "regel_offen" else _verteilung(pop, True))
            entscheide.append({"key": key, "label": ENTSCHEID[key][0],
                               "was": _entscheid_text(key, m_art, eintrag, pop, urteile),
                               "frage": T_FRAGE.format(wozu=ENTSCHEID[key][1]), "verteilung": vert})

    # per Dienststelle — from the lists the export holds; the sums are checked against the canton's
    dst = []
    rang = {k: i for i, k in enumerate(MERKMAL_KEYS)}
    for d in dienststellen:
        ids = [fid for fid in d["formulare"] if fid in tab]
        n_act, n_open = Counter(), 0                       # n_act: (Merkmal, verdict) -> Formulare
        for fid in ids:
            n_open += per_form[fid].get("n", {}).get("open", 0)
            for m in per_form[fid].get("merkmale", []):
                if URTEIL[m["u"]][1] == "act":
                    n_act[(m["k"], m["u"])] += 1
        pdf_akzente = {tab[fid]["akzentfarbe"]["v"] for fid in ids if tab[fid]["akzentfarbe"]["pop"]} - {T_AKZENT_OHNE}
        n_gemessen = sum(1 for fid in ids if fid in zeilen)
        n_nm = sum(1 for fid in ids if fid in zeilen and zeilen[fid][0] == "nicht_messbar")
        n_messbar = n_gemessen - n_nm                      # a file in an old format has a row, but nothing measured
        dst.append({
            "name": d["name"], "slug": d["slug"], "n_formulare": len(d["formulare"]), "n_gemessen": n_gemessen,
            "n_nicht_messbar": n_nm,
            "n": {"act": sum(n_act.values()),
                  "abweichungen": sum(n for (_k, u), n in n_act.items() if u == "weicht_ab"),
                  "luecken": sum(n for (_k, u), n in n_act.items() if u == "luecke"), "open": n_open},
            "act_je_formular": round(sum(n_act.values()) / n_messbar, 2) if n_messbar else None,
            "schriften": len({tab[fid]["schrift"]["v"] for fid in ids if tab[fid]["schrift"]["pop"]}),
            "groessen": len({tab[fid]["groesse"]["v"] for fid in ids if tab[fid]["groesse"]["pop"]}),
            "akzente": len(pdf_akzente),
            "top": [{"key": k, "u": u, "n": n} for (k, u), n in sorted(n_act.items(),
                                                                         key=lambda x: (-x[1], rang[x[0][0]], x[0][1]))][:TOP],
        })

    exportiert = [g for g in per_form.values() if not g.get("entfaellt")]
    kennzahlen = {
        "pdf": art["pdf"] + art["pdf_bild"],
        "pdf_mindestmerkmale": sum(1 for g in exportiert if _mindestmerkmale(g)),
        "ok": sum(m["n"]["ok"] for m in merkmale), "act": sum(m["n"]["act"] for m in merkmale),
        "abweichungen": sum(m["urteile"].get("weicht_ab", 0) for m in merkmale),
        "luecken": sum(m["urteile"].get("luecke", 0) for m in merkmale),
        "dec": len(entscheide), "betroffen": sum(m["n"]["betroffen"] for m in merkmale),
        "hinweis": sum(m["n"]["hinweis"] for m in merkmale),
        "open": sum(m["n"]["open"] for m in merkmale),
        "formulare_mit_act": sum(1 for g in exportiert if g["n"]["act"]),
        "formulare_mit_abweichung": sum(1 for g in exportiert if _hat_urteil(g, "weicht_ab")),
        "formulare_mit_luecke": sum(1 for g in exportiert if _hat_urteil(g, "luecke")),
    }
    assert set(kennzahlen) == set(KENNZAHL)
    M = {m["key"]: m for m in merkmale}
    return {
        "stand": _stand(conn) if zeilen else None,
        "methode": ", ".join(methoden) or None,
        "bestand": {"formulare": len(forms), "mit_datei": mit_datei, "ohne_datei": len(forms) - mit_datei,
                    "gemessen": len(zeilen), "messart": {k: art[k] for k in MESSART if art[k]},
                    "dienststellen": len(dst), "dienststellen_gemessen": sum(1 for d in dst if d["n_gemessen"]),
                    "dienststellen_ohne_formular": sum(1 for d in dst if not d["n_formulare"])},
        "gruppen": [dict({"key": k, "label": l, "frage": f}, **({"vorbehalt": v} if v else {}),
                         kennzahl=_tuer(k, M, kennzahlen))
                    for k, l, f, v in GRUPPEN],
        "merkmale": merkmale, "kennzahlen": kennzahlen, "entscheide": entscheide, "dienststellen": dst,
        "grenzen": _grenzen(forms, dienststellen, zeilen, tab),
        "labels": {"urteil": {k: {"label": v[0], "ton": v[1]} for k, v in URTEIL.items()}, "ton": TON,
                   "ton_zusatz": TON_ZUSATZ, "urteil_gesamt": URTEIL_GESAMT, "urteil_nomen": URTEIL_NOMEN,
                   "art": ART, "art_erklaerung": ART_ERKLAERUNG, "messart": MESSART,
                   "gruppe": {g[0]: g[1] for g in GRUPPEN},
                   "merkmal": {m[0]: m[4] for m in MERKMALE}, "kennzahl": KENNZAHL, "eformular": T_EFORMULAR,
                   "entscheide": T_ENTSCHEIDE},
    }


# ================================================================== invariants

def _strings(o, pfad=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(v, f"{pfad}.{k}" if pfad else str(k))
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            yield from _strings(v, f"{pfad}[{i}]")
    elif isinstance(o, str):
        yield pfad, o


def pruefen(per_form, overview, forms, dienststellen, profile):
    """The invariants of the export layer (module docstring, 1–8). `profile` is
    {form_id: profil} of the measured Formulare. Raises RuntimeError naming
    every figure that does not hold; returns None."""
    fehler = []
    alle = [fm["id"] for fm in forms]
    n_alle = len(set(alle))                            # «all Formulare»: each one once
    if set(per_form) != set(alle) or len(alle) != n_alle:
        fehler.append(f"forms: {len(alle)} Einträge im Export, {n_alle} verschiedene Formulare, "
                      f"{len(per_form)} mit Urteil")
    je = {k: {} for k in MERKMAL_KEYS}                 # Merkmal -> verdict -> [form ids], recounted from per_form
    for fid in sorted(per_form):
        g = per_form[fid]
        if g.get("entfaellt"):
            continue
        for m in g["merkmale"]:
            if m["k"] not in je or m["u"] not in URTEIL or m["u"] in NICHT_EXPORTIERT:
                fehler.append(f"{m['k']}: Formular {fid} trägt das unbekannte Urteil «{m['u']}»")
                continue
            je[m["k"]].setdefault(m["u"], []).append(fid)
        if g["n"] != _n_formular([m for m in g["merkmale"] if m["u"] in URTEIL]):
            fehler.append(f"Formular {fid}: n = {g['n']} entspricht nicht seinen Merkmalen")
    schluessel = [m["key"] for m in overview["merkmale"]]
    if schluessel != list(MERKMAL_KEYS):
        fehler.append(f"merkmale: {schluessel} statt {list(MERKMAL_KEYS)}")
    for m in overview["merkmale"]:
        key, u, n = m["key"], m["urteile"], m["n"]
        if key not in je:
            continue
        if sum(u.values()) != n_alle:                                           # 1
            fehler.append(f"{key}: die Urteile summieren sich auf {sum(u.values())}, es sind {n_alle} Formulare")
        for urteil in URTEIL:
            if urteil in NICHT_EXPORTIERT:
                continue
            ist = len(je[key].get(urteil, []))
            if u.get(urteil, 0) != ist:
                fehler.append(f"{key}: «{urteil}» {u.get(urteil, 0)} in der Übersicht, {ist} bei den Formularen")
        if m["n_gemessen"] != sum(v["n"] for v in m["verteilung"]):
            fehler.append(f"{key}: n_gemessen {m['n_gemessen']} ist nicht die Summe der Verteilung")
        if m["praxis"] and not (m["n_gemessen"] >= PRAXIS_MIN
                                and Fraction(m["praxis"]["n"], m["n_gemessen"]) >= PRAXIS_SCHWELLE):
            fehler.append(f"{key}: die Praxis «{m['praxis']['w']}» erreicht die Schwelle nicht")
        soll = {"ok": ("entspricht", "vorhanden"), "act": ("weicht_ab", "luecke"), "betroffen": ("betroffen",),
                "hinweis": ("hinweis",), "open": ("nicht_messbar", "nicht_gemessen")}
        for zahl, urteile in soll.items():                                      # 2
            if n[zahl] != sum(u.get(x, 0) for x in urteile):
                fehler.append(f"{key}: n.{zahl} = {n[zahl]} ist nicht die Summe seiner Urteile")
            if zahl != "ok" and n[zahl] != sum(len(m["formulare"].get(x, [])) for x in urteile):
                fehler.append(f"{key}: n.{zahl} = {n[zahl]}, die Listen nennen "
                              f"{sum(len(m['formulare'].get(x, [])) for x in urteile)} Formulare")
        for urteil in LISTEN:
            if m["formulare"].get(urteil, []) != je[key].get(urteil, []):
                fehler.append(f"{key}: die Liste «{urteil}» stimmt nicht mit den Formularen überein")
        if set(m["formulare"]) - set(LISTEN):
            fehler.append(f"{key}: Listen für {sorted(set(m['formulare']) - set(LISTEN))}")
        if n["dec"] not in (0, 1):
            fehler.append(f"{key}: n.dec = {n['dec']}")
    mit_dec = [m["key"] for m in overview["merkmale"] if m["n"]["dec"] == 1]
    if [e["key"] for e in overview["entscheide"]] != mit_dec:
        fehler.append(f"entscheide: {[e['key'] for e in overview['entscheide']]} statt {mit_dec}")
    in_entscheiden = Counter()                                                  # 3: n.dec of a Formular
    for e in overview["entscheide"]:
        for v in e["verteilung"]:
            if v["n"] != len(v["formulare"]):
                fehler.append(f"entscheide: «{e['key']}» nennt beim Wert «{v['w']}» {v['n']} Formulare, die Liste "
                              f"{len(v['formulare'])}")
            in_entscheiden.update(v["formulare"])
    for fid in sorted(per_form):
        g = per_form[fid]
        if not g.get("entfaellt") and g["n"].get("dec") != in_entscheiden.get(fid, 0):
            fehler.append(f"Formular {fid}: n.dec = {g['n'].get('dec')}, die Listen der Entscheide nennen es "
                          f"{in_entscheiden.get(fid, 0)}-mal")
    K = overview["kennzahlen"]                                                  # 3
    exportiert = [g for g in per_form.values() if not g.get("entfaellt")]
    for name, ist, soll in (
            ("act", K["act"], sum(m["n"]["act"] for m in overview["merkmale"])),
            ("act", K["act"], sum(g["n"]["act"] for g in exportiert)),
            ("open", K["open"], sum(m["n"]["open"] for m in overview["merkmale"])),
            ("open", K["open"], sum(g["n"]["open"] for g in exportiert)),
            ("betroffen", K["betroffen"], sum(g["n"]["betroffen"] for g in exportiert)),
            ("ok", K["ok"], sum(m["n"]["ok"] for m in overview["merkmale"])),
            ("hinweis", K["hinweis"], sum(m["n"]["hinweis"] for m in overview["merkmale"])),
            ("abweichungen + luecken", K["abweichungen"] + K["luecken"], K["act"]),
            ("luecken", K["luecken"], sum(1 for g in exportiert for m in g["merkmale"] if m["u"] == "luecke")),
            ("dec", K["dec"], len(overview["entscheide"])),
            ("formulare_mit_act", K["formulare_mit_act"], sum(1 for g in exportiert if g["n"]["act"])),
            ("formulare_mit_abweichung", K["formulare_mit_abweichung"],
             sum(1 for g in exportiert if _hat_urteil(g, "weicht_ab"))),
            ("formulare_mit_luecke", K["formulare_mit_luecke"], sum(1 for g in exportiert if _hat_urteil(g, "luecke"))),
            ("pdf", K["pdf"], sum(1 for g in exportiert if g["messart"] in ("pdf", "pdf_bild"))),
            ("pdf_mindestmerkmale", K["pdf_mindestmerkmale"], sum(1 for g in exportiert if _mindestmerkmale(g)))):
        if ist != soll:
            fehler.append(f"kennzahlen.{name} = {ist}, nachgezählt {soll}")
    B = overview["bestand"]
    if (B["formulare"] != n_alle or B["gemessen"] != sum(1 for g in exportiert if g["messart"])
            or B["gemessen"] != sum(B["messart"].values()) or B["mit_datei"] + B["ohne_datei"] != B["formulare"]
            or B["ohne_datei"] != n_alle - len(exportiert)):
        fehler.append(f"bestand: {B} geht nicht auf ({n_alle} Formulare, {len(exportiert)} mit Datei)")
    D = overview["dienststellen"]                                               # 4
    if [d["slug"] for d in D] != [d["slug"] for d in dienststellen]:
        fehler.append("dienststellen: nicht die Dienststellen des Exports, oder in anderer Reihenfolge")
    for name, ist, soll in (("n_formulare", sum(d["n_formulare"] for d in D), B["formulare"]),
                            ("n_gemessen", sum(d["n_gemessen"] for d in D), B["gemessen"]),
                            ("n_nicht_messbar", sum(d["n_nicht_messbar"] for d in D), B["messart"].get("nicht_messbar", 0)),
                            ("n.act", sum(d["n"]["act"] for d in D), K["act"]),
                            ("n.abweichungen", sum(d["n"]["abweichungen"] for d in D), K["abweichungen"]),
                            ("n.luecken", sum(d["n"]["luecken"] for d in D), K["luecken"]),
                            ("n.open", sum(d["n"]["open"] for d in D), K["open"])):
        if ist != soll:
            fehler.append(f"dienststellen: die Summe von {name} ist {ist}, der Kanton hat {soll}")
    for d in D:
        if d["n"]["abweichungen"] + d["n"]["luecken"] != d["n"]["act"]:
            fehler.append(f"dienststellen: «{d['slug']}» — Abweichungen {d['n']['abweichungen']} und Lücken "
                          f"{d['n']['luecken']} ergeben nicht act {d['n']['act']}")
    gezaehlt = (len(D), sum(1 for d in D if d["n_gemessen"]), sum(1 for d in D if not d["n_formulare"]))
    if (B.get("dienststellen"), B.get("dienststellen_gemessen"), B.get("dienststellen_ohne_formular")) != gezaehlt:
        fehler.append(f"dienststellen: bestand nennt {B.get('dienststellen')} Dienststellen, "
                      f"{B.get('dienststellen_gemessen')} mit gemessenem Formular, {B.get('dienststellen_ohne_formular')} "
                      f"ohne Formular — nachgezählt {gezaehlt[0]}, {gezaehlt[1]}, {gezaehlt[2]}")
    M = {m["key"]: m for m in overview["merkmale"]}                              # 10
    for g in overview["gruppen"]:
        t = g.get("kennzahl")
        if not t:
            continue
        q = t.get("quelle") or {}
        if "kennzahl" in q:
            soll = K.get(q["kennzahl"])
        elif q.get("merkmal") in M and M[q["merkmal"]]["gruppe"] == g["key"]:
            soll = M[q["merkmal"]]["urteile"].get(q.get("urteil"), 0)
        else:
            soll = None
        if t.get("n") != soll:
            fehler.append(f"gruppen: die Tür «{g['key']}» nennt {t.get('n')}, ihre Quelle {q} zählt {soll}")
    in_dst = sorted(fid for d in dienststellen for fid in d["formulare"])
    if in_dst != sorted(alle):
        fehler.append("dienststellen: die Formulare der Dienststellen sind nicht genau die Formulare des Exports")
    for wo, daten in (("forms[].gestaltung", per_form), ("gestaltung", overview)):   # 5, 6
        for pfad, s in _strings(daten):
            ort = pfad
            mm = re.match(r"^(\d+)\.merkmale\[(\d+)\]", pfad) if daten is per_form else None
            if mm:
                ort = f"{per_form[int(mm.group(1))]['merkmale'][int(mm.group(2))]['k']}: Formular {mm.group(1)}"
            if "@" in s:
                fehler.append(f"{ort} ({wo}): «@» in einem exportierten Text — {s[:80]!r}")
            if LOCAL_PATH.search(s) or _PFAD_FREMD.search(s):
                fehler.append(f"{ort} ({wo}): lokaler Pfad in einem exportierten Text — {s[:80]!r}")
            if _UNZEIGBAR.search(s):
                fehler.append(f"{ort} ({wo}): Steuer- oder Sonderzeichen in einem exportierten Text — {s[:80]!r}")
    for fid in sorted(per_form):                                                # 7
        g, p = per_form[fid], profile.get(fid)
        if g.get("entfaellt") or not p:
            continue
        tel = p.get("telefon") or []
        frei = {_sauber(t["kontext"]) for t in tel if t["erklaerung"] != "erklaert"}
        gesperrt = {_sauber(t["kontext"]) for t in tel if t["erklaerung"] == "erklaert"} - frei
        # a quote that is nothing but the printed number carries nothing beyond the number
        gesperrt = {k for k in gesperrt if k and k not in {t["nummer"] for t in tel}}
        eintrag = next((m for m in g["merkmale"] if m["k"] == "tel_erklaerung"), None)
        zitate = [d for d in (eintrag["d"] or []) if _TEL_ZITAT.search(d)] if eintrag else []
        if eintrag and eintrag["u"] not in ("luecke", "hinweis") and zitate:
            fehler.append(f"tel_erklaerung: Formular {fid} zitiert eine Nummer ohne Lücke oder Hinweis")
        if len(zitate) != (len([t for t in tel if t["erklaerung"] != "erklaert"])
                           if eintrag and eintrag["u"] in ("luecke", "hinweis") else 0):
            fehler.append(f"tel_erklaerung: Formular {fid} — die Zitate sind nicht genau die der Nummern "
                          "mit «bezeichnung» oder «ohne»")
        for pfad, s in _strings(g):
            for k in gesperrt:
                if k in s:
                    fehler.append(f"tel_erklaerung: Formular {fid} exportiert das Zitat einer erklärten Nummer "
                                  f"({pfad})")
    for fid in sorted(per_form):                                                # 9
        g, p = per_form[fid], profile.get(fid)
        titel = ((p or {}).get("barrierefrei") or {}).get("titel")
        if g.get("entfaellt") or not titel or not GT.person_im_titel(titel):
            continue
        for pfad, s in _strings(g):
            if _sauber(titel) in s:
                fehler.append(f"bf_titel: Formular {fid} zitiert einen Titel, der wie der Name einer Person "
                              f"aussieht ({pfad})")
    if fehler:
        raise RuntimeError(f"Gestaltung — {len(fehler)} Prüfung(en) gehen nicht auf: " + " | ".join(fehler[:12])
                           + (f" | … und {len(fehler) - 12} weitere" if len(fehler) > 12 else ""))


def _berechnen(conn, forms, dienststellen):
    for d in dienststellen:
        if not isinstance(d, dict) or not {"slug", "name", "formulare"} <= set(d):
            raise RuntimeError("Gestaltung: «dienststellen» ist nicht export_jsons dienststellen_uebersicht "
                               "(slug, name, formulare)")
    zeilen = _zeilen(conn)
    tab = _tabelle(forms, zeilen)
    praxis = _praxis_setzen(forms, tab)
    per_form = {}
    for fm in forms:
        if not fm.get("source_file"):
            per_form[fm["id"]] = {"messart": None, "entfaellt": True}
        else:
            zeile = zeilen.get(fm["id"])
            per_form[fm["id"]] = _kompakt(zeile[0] if zeile else None, tab[fm["id"]])
    overview = _uebersicht(conn, forms, dienststellen, zeilen, tab, praxis, per_form)
    pruefen(per_form, overview, forms, dienststellen, {fid: z[2] for fid, z in zeilen.items()})
    return per_form, overview, tab


def berechne(conn, forms, services, dienststellen):
    """(per_form, overview) — see the module docstring. Raises RuntimeError when an
    invariant does not hold or the stored profiles are not what this layer reads."""
    per_form, overview, _tab = _berechnen(conn, forms, dienststellen)
    return per_form, overview


# ================================================================ command line
# the printing helpers and the self-test; the entry point (main, _eingabe) is
# citygov/export/gestaltung_export_cli.py, because it builds the export in memory

def _bytes(per_form, overview):
    """Bytes the two results add to data_export.json (its separators, UTF-8)."""
    def j(o):
        return len(json.dumps(o, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    je_formular = sum(j(g) + len(',"gestaltung":') for g in per_form.values())
    return je_formular, j(overview) + len(',"gestaltung":')


def _kurz(text, n):
    return text if len(text) <= n else text[:n - 1] + "…"


def _drucke_uebersicht(per_form, overview):
    B, K = overview["bestand"], overview["kennzahlen"]
    print(f"Gestaltung der Formulare — Methode {overview['methode'] or '—'}, Stand der Messung "
          f"{overview['stand'] or 'nicht gespeichert'}")
    print(f"  Bestand: {B['formulare']} Formulare, {B['mit_datei']} mit Datei, {B['ohne_datei']} eFormulare, "
          f"{B['gemessen']} mit Messzeile (" + ", ".join(f"{k} {n}" for k, n in B["messart"].items()) + ")")
    gruppe = None
    kurz = {"entspricht": "entspricht", "weicht_ab": "weicht ab", "uneinheitlich": "uneinheitlich",
            "vorhanden": "vorhanden", "luecke": "Lücke", "betroffen": "betroffen", "hinweis": "Hinweis",
            "kein_hinweis": "kein Hinweis", "nicht_messbar": "nicht messbar", "nicht_gemessen": "nicht gemessen",
            "entfaellt": "entfällt"}
    for m in overview["merkmale"]:
        if m["gruppe"] != gruppe:
            gruppe = m["gruppe"]
            print(f"\n{overview['labels']['gruppe'][gruppe]}")
            print(f"  {'Merkmal':<18}{'Art':<12}{'betrifft':>8}{'gemessen':>9}  {'Praxis':<40}Urteile")
        betrifft = B["formulare"] - m["urteile"].get("entfaellt", 0)
        if m["praxis"]:
            praxis = f"{m['praxis']['w']} ({m['praxis']['n']}, {_proz(m['praxis']['anteil'])})"
        elif m["art"] == "praxis":
            v = m["verteilung"][0] if m["verteilung"] else None
            praxis = f"keine (am häufigsten: {v['w']}, {_proz(v['n'] / m['n_gemessen'])})" if v else "keine"
        else:
            praxis = "—"
        print(f"  {m['key']:<18}{m['art']:<12}{betrifft:>8}{m['n_gemessen']:>9}  {_kurz(praxis, 39):<40}"
              + " · ".join(f"{kurz[u]} {n}" for u, n in m["urteile"].items())
              + ("  → 1 Entscheid" if m["n"]["dec"] else ""))
    print(f"\nKennzahlen: {K['pdf']} PDF, davon {K['pdf_mindestmerkmale']} mit Tags + Sprache + Titel · "
          f"act {K['act']} (Abweichungen {K['abweichungen']}, Lücken {K['luecken']}) · betroffen {K['betroffen']} · "
          f"Hinweise {K['hinweis']} · open {K['open']} · ok {K['ok']} · Entscheide {K['dec']}")
    print(f"  Formulare mit Abweichung oder Lücke {K['formulare_mit_act']} · mit Abweichung "
          f"{K['formulare_mit_abweichung']} · mit Lücke {K['formulare_mit_luecke']}")
    print("\nOffene Entscheide des Kantons")
    for e in overview["entscheide"]:
        print(f"  {e['key']:<14}{e['label']}: {e['was']}")
    for m in overview["merkmale"]:
        z = m.get("zusatz")
        if z and "nummern" in z:
            print(f"\n{z['label']}: {z['n_mehrfach']} von {z['n_nummern']} Nummern — Muster: "
                  + ", ".join(f"«{s['w']}» {s['n']}" for s in z["schreibweisen"][:6]))
        elif z and "muster" in z:
            print(f"\n{z['label']}: " + ", ".join(f"«{s['w']}» {s['n']}" for s in z["muster"]))
        elif z and "dienststellen" in z:
            print(f"\n{z['label']}: " + ", ".join(f"{d['name']} {d['n']}" for d in z["dienststellen"]))
        elif z:
            print(f"\n{z['label']}: " + ", ".join(f"{k} {v}" for k, v in z.items() if k != "label"))
    D = sorted(overview["dienststellen"], key=lambda d: (-d["n"]["act"], d["slug"]))
    print(f"\nDienststellen: {len(D)} — die zehn mit den meisten Abweichungen und Lücken (act)")
    print(f"  {'Dienststelle':<46}{'Form.':>6}{'gem.':>6}{'act':>6}{'je F.':>7}{'open':>6}{'Schr.':>6}{'Gr.':>5}{'Akz.':>5}  top")
    for d in D[:10]:
        je = "—" if d["act_je_formular"] is None else _zahl(d["act_je_formular"], 2)
        print(f"  {_kurz(d['name'], 45):<46}{d['n_formulare']:>6}{d['n_gemessen']:>6}{d['n']['act']:>6}{je:>7}"
              f"{d['n']['open']:>6}{d['schriften']:>6}{d['groessen']:>5}{d['akzente']:>5}  "
              + ", ".join(f"{t['key']} ({t['u']}) {t['n']}" for t in d["top"]))
    a, b = _bytes(per_form, overview)
    print(f"\nGrösse in data_export.json: forms[].gestaltung {a:,} Bytes + gestaltung {b:,} Bytes = "
          f"{a + b:,} Bytes".replace(",", "'"))


def _drucke_formular(fid, forms, services, dienststellen, per_form, overview, tab):
    fm = next((f for f in forms if f["id"] == fid), None)
    if fm is None:
        sys.exit(f"ABBRUCH: kein Formular mit der Nummer {fid}")
    sv = next((s for s in services if s["id"] == fm.get("service_id")), {})
    dst = next((d["name"] for d in dienststellen if fid in d["formulare"]), "—")
    g = per_form[fid]
    print(f"Formular {fid}: {fm.get('title')}")
    print(f"  Service: {sv.get('name', '—')} · Dienststelle: {dst} · Datei: {fm.get('file_type')} · "
          f"Messart: {g['messart'] or '—'}")
    if not g.get("entfaellt"):
        print(f"  n: act {g['n']['act']} · betroffen {g['n']['betroffen']} · dec {g['n']['dec']} · open {g['n']['open']}")
    praxis = {m["key"]: m for m in overview["merkmale"]}
    gruppe = None
    for key, grp, m_art, _nur, label, _frage, _erkl, _basis in MERKMALE:
        if grp != gruppe:
            gruppe = grp
            print(f"\n{overview['labels']['gruppe'][grp]}")
        c = tab[fid][key]
        zeile = f"  {label + ' (' + key + ')':<46}{URTEIL[c['u']][0]}"
        if c["u"] in ("entfaellt", "nicht_messbar", "nicht_gemessen"):
            zeile += f" — {c['w']}" if c["u"] == "entfaellt" else ""
        else:
            zeile += f": {c['w']}"
        pr = praxis[key]["praxis"]
        if c["u"] in ("entspricht", "weicht_ab") and pr:
            zeile += f"  [Praxis: {pr['w']}, {_proz(pr['anteil'])}]"
        if c["u"] in NICHT_EXPORTIERT:
            zeile += "  (nicht im Export)"
        print(zeile)
        for d in c["d"] or []:
            print(f"      · {d}")
    print("\nIm Export (forms[].gestaltung):")
    print(json.dumps(g, ensure_ascii=False, separators=(",", ":")))


def _selbsttest(conn, forms, services, dienststellen):
    """Every invariant must fire: on tampered copies of the INPUT of berechne()
    where the input can break it, and on tampered copies of the result that
    pruefen() is given. Works on copies in memory; nothing is written."""
    per_form, overview, _tab = _berechnen(conn, forms, dienststellen)
    zeilen = _zeilen(conn)
    profile = {fid: z[2] for fid, z in zeilen.items()}
    n = [0]

    def muss(name, lauf, *teile):
        try:
            lauf()
        except RuntimeError as e:
            text = str(e)
            if all(t in text for t in teile):
                n[0] += 1
                print(f"  feuert: {name}\n          {_kurz(text, 200)}")
                return
            sys.exit(f"SELBSTTEST: «{name}» bricht ab, nennt aber {teile} nicht: {text[:400]}")
        sys.exit(f"SELBSTTEST: «{name}» feuert nicht")

    def kopie_db(aendern):
        """An in-memory databank with table form_gestaltung only, one profil changed."""
        mem = sqlite3.connect(":memory:")
        mem.execute("CREATE TABLE form_gestaltung (form_id INTEGER PRIMARY KEY, messart TEXT, methode TEXT, profil TEXT)")
        for fid, (messart, methode, p) in zeilen.items():
            p = copy.deepcopy(p)
            neu = aendern(fid, p)
            messart = neu if isinstance(neu, str) else messart
            mem.execute("INSERT INTO form_gestaltung VALUES (?,?,?,?)",
                        [fid, messart, methode, json.dumps(p, ensure_ascii=False)])
        return mem

    def erste(bedingung):
        return next(fid for fid in sorted(profile) if bedingung(profile[fid]))

    def setze(ziel, tun):
        def aendern(fid, p):
            if fid == ziel:
                return tun(p)
        return aendern

    print("Eingabe von berechne() verändert")
    f_titel = erste(lambda p: p["barrierefrei"]["titel_art"] == "generisch")
    muss("5 «@» — eine ausgeschriebene Adresse im Dokumenttitel",
         lambda: berechne(kopie_db(setze(f_titel, lambda p: p["barrierefrei"].update(titel="Auskunft: amt@example.org"))),
                          forms, services, dienststellen), "bf_titel", f"Formular {f_titel}", "«@»")
    f_stand = erste(lambda p: p["elemente"]["stand_angabe"]["vorhanden"])
    muss("6 lokaler Pfad — in der Stand-Angabe",
         lambda: berechne(kopie_db(setze(f_stand, lambda p: p["elemente"]["stand_angabe"].update(
             text="/Users/beispiel/Formulare/antrag.docx"))), forms, services, dienststellen),
         "stand_angabe", f"Formular {f_stand}", "lokaler Pfad")
    muss("6 lokaler Pfad — Laufwerkspfad im Dokumenttitel",
         lambda: berechne(kopie_db(setze(f_titel, lambda p: p["barrierefrei"].update(
             titel="C:\\Users\\beispiel\\antrag.doc"))), forms, services, dienststellen),
         "bf_titel", "lokaler Pfad")
    f_erkl = erste(lambda p: any(t["erklaerung"] == "erklaert" and t["kontext"] != t["nummer"]
                                 for t in p["telefon"] or [])
                   and p["barrierefrei"]["titel_art"] in ("generisch", "ohne_bezug"))
    def leck(p):
        t = next(t for t in p["telefon"] if t["erklaerung"] == "erklaert" and t["kontext"] != t["nummer"])
        p["barrierefrei"]["titel"] = t["kontext"]
    muss("7 Zitat einer erklärten Nummer — über den Dokumenttitel exportiert",
         lambda: berechne(kopie_db(setze(f_erkl, leck)), forms, services, dienststellen),
         "tel_erklaerung", f"Formular {f_erkl}", "erklärten Nummer")
    muss("1 Summe je Merkmal — ein Formular steht zweimal in forms",
         lambda: berechne(conn, forms + [forms[0]], services, dienststellen), "summieren sich auf", "Formulare")
    d2 = copy.deepcopy(dienststellen)
    voll = next(d for d in d2 if d["formulare"])
    leer = next(d for d in d2 if d is not voll)
    leer["formulare"] = leer["formulare"] + [voll["formulare"][0]]
    muss("4 Dienststellen — ein Formular bei zwei Dienststellen",
         lambda: berechne(conn, forms, services, d2), "dienststellen", "n_formulare")
    d3 = copy.deepcopy(dienststellen)
    next(d for d in d3 if d["formulare"])["formulare"].pop()
    muss("4 Dienststellen — ein Formular bei keiner Dienststelle",
         lambda: berechne(conn, forms, services, d3), "dienststellen", "n_formulare")
    muss("Eingabe — unbekannte Messart",
         lambda: berechne(kopie_db(setze(f_titel, lambda p: p.update(messart="papier") or "papier")),
                          forms, services, dienststellen), "Messart")
    muss("Eingabe — Zählregel der Schriftfamilien geändert",
         lambda: berechne(kopie_db(setze(erste(lambda p: p["n_schriftfamilien"] == 1),
                                         lambda p: p.update(n_schriftfamilien=2))),
                          forms, services, dienststellen), "schriftfamilien")
    muss("Eingabe — unbekannte titel_art",
         lambda: berechne(kopie_db(setze(f_titel, lambda p: p["barrierefrei"].update(titel_art="neu"))),
                          forms, services, dienststellen), "bf_titel")
    muss("Eingabe — Profil ohne vereinbarten Schlüssel",
         lambda: berechne(kopie_db(setze(f_titel, lambda p: p.pop("elemente"))), forms, services, dienststellen),
         "Aufbau")
    muss("Eingabe — «dienststellen» ist nicht dienststellen_uebersicht",
         lambda: berechne(conn, forms, services, [{"name": "x"}]), "dienststellen_uebersicht")
    muss("Eingabe — Profil einer älteren Methode (ohne text_lesbar)",
         lambda: berechne(kopie_db(setze(f_titel, lambda p: p["barrierefrei"].pop("text_lesbar"))),
                          forms, services, dienststellen), f"Formular {f_titel}", "Aufbau")
    f_farbe = erste(lambda p: p["messart"] == "pdf" and p["akzent"])
    muss("Eingabe — Farbe ohne das Merkmal nur_kopf",
         lambda: berechne(kopie_db(setze(f_farbe, lambda p: [f.pop("nur_kopf") for f in p["farben"]] and None)),
                          forms, services, dienststellen), "akzentfarbe", f"Formular {f_farbe}", "Aufbau")

    print("Ergebnis verändert, pruefen() darauf angesetzt")

    def mit(aendern, *teile, name):
        pf, ov = copy.deepcopy(per_form), copy.deepcopy(overview)
        aendern(pf, ov)
        muss(name, lambda: pruefen(pf, ov, forms, dienststellen, profile), *teile)

    def merkmal(ov, key):
        return next(m for m in ov["merkmale"] if m["key"] == key)

    mit(lambda pf, ov: merkmal(ov, "schrift")["urteile"].update(entfaellt=merkmal(ov, "schrift")["urteile"]["entfaellt"] + 1),
        "schrift", "summieren", name="1 Urteile je Merkmal summieren sich nicht auf alle Formulare")
    f_l = merkmal(overview, "bf_titel")["formulare"]["luecke"][0]
    def ohne_eintrag(pf, ov):
        pf[f_l]["merkmale"] = [m for m in pf[f_l]["merkmale"] if m["k"] != "bf_titel"]
        pf[f_l]["n"] = _n_formular(pf[f_l]["merkmale"])
    mit(ohne_eintrag, "bf_titel", "bei den Formularen", name="1 ein Urteil fehlt beim Formular")
    mit(lambda pf, ov: merkmal(ov, "groesse").update(n_gemessen=merkmal(ov, "groesse")["n_gemessen"] + 1),
        "groesse", "n_gemessen", name="1 n_gemessen ist nicht die Summe der Verteilung")
    mit(lambda pf, ov: merkmal(ov, "bf_tags")["formulare"]["luecke"].pop(),
        "bf_tags", "n.act", name="2 act-Zahl und Länge der Liste")
    mit(lambda pf, ov: merkmal(ov, "kleinschrift")["formulare"]["betroffen"].pop(),
        "kleinschrift", "n.betroffen", name="2 betroffen-Zahl und Länge der Liste")
    mit(lambda pf, ov: merkmal(ov, "schrift")["formulare"]["nicht_messbar"].pop(),
        "schrift", "n.open", name="2 open-Zahl und Länge der Liste")
    mit(lambda pf, ov: merkmal(ov, "farbvielfalt")["formulare"]["hinweis"].pop(),
        "farbvielfalt", "n.hinweis", name="2 hinweis-Zahl und Länge der Liste")
    mit(lambda pf, ov: merkmal(ov, "groesse")["n"].update(dec=0),
        "entscheide", name="2 dec-Zahl und Liste der Entscheide")
    mit(lambda pf, ov: ov["entscheide"].pop(), "entscheide", name="2 ein Entscheid fehlt")
    mit(lambda pf, ov: merkmal(ov, "seitenformat")["praxis"].update(n=10),
        "seitenformat", "Schwelle", name="Praxis unter der Schwelle")
    mit(lambda pf, ov: pf[f_l]["n"].update(act=pf[f_l]["n"]["act"] + 1),
        f"Formular {f_l}", name="3 n eines Formulars entspricht nicht seinen Merkmalen")
    mit(lambda pf, ov: ov["kennzahlen"].update(act=ov["kennzahlen"]["act"] + 1),
        "kennzahlen.act", name="3 Kennzahl act")
    mit(lambda pf, ov: ov["kennzahlen"].update(formulare_mit_luecke=0),
        "kennzahlen.formulare_mit_luecke", name="3 Kennzahl Formulare mit Lücke")
    mit(lambda pf, ov: ov["kennzahlen"].update(pdf_mindestmerkmale=ov["kennzahlen"]["pdf"]),
        "kennzahlen.pdf_mindestmerkmale", name="3 Kennzahl PDF mit den drei Mindestmerkmalen")
    mit(lambda pf, ov: next(d for d in ov["dienststellen"] if d["n"]["act"])["n"].update(act=0),
        "dienststellen", "n.act", name="4 Dienststellen-Summe act")
    mit(lambda pf, ov: next(d for d in ov["dienststellen"] if d["n"]["open"])["n"].update(open=0),
        "dienststellen", "n.open", name="4 Dienststellen-Summe open")
    mit(lambda pf, ov: ov["dienststellen"][0].update(n_gemessen=ov["dienststellen"][0]["n_gemessen"] + 1),
        "dienststellen", "n_gemessen", name="4 Dienststellen-Summe gemessen")
    mit(lambda pf, ov: ov["bestand"].update(dienststellen_gemessen=ov["bestand"]["dienststellen_gemessen"] + 1),
        "dienststellen", "mit gemessenem Formular", name="4 Dienststellen mit gemessenem Formular")
    mit(lambda pf, ov: ov["bestand"].update(dienststellen_ohne_formular=ov["bestand"]["dienststellen_ohne_formular"] + 1),
        "dienststellen", "ohne Formular", name="4 Dienststellen ohne Formular")
    mit(lambda pf, ov: next(d for d in ov["dienststellen"] if d["n"]["luecken"])["n"].update(luecken=0),
        "dienststellen", "n.luecken", name="4 Dienststellen-Summe Lücken")
    mit(lambda pf, ov: next(d for d in ov["dienststellen"] if d["n"]["abweichungen"])["n"].update(
            abweichungen=0, luecken=next(d for d in ov["dienststellen"] if d["n"]["abweichungen"])["n"]["act"]),
        "dienststellen", "n.abweichungen", name="4 Abweichungen einer Dienststelle als Lücken gezählt")
    mit(lambda pf, ov: ov["dienststellen"][0].update(n_nicht_messbar=ov["dienststellen"][0]["n_nicht_messbar"] + 1),
        "dienststellen", "n_nicht_messbar", name="4 Dienststellen-Summe nicht messbar")
    f_dec = next(fid for fid in sorted(per_form) if not per_form[fid].get("entfaellt") and per_form[fid]["n"]["dec"])
    def ohne_im_entscheid(pf, ov):
        for e in ov["entscheide"]:
            for v in e["verteilung"]:
                if f_dec in v["formulare"]:
                    v["formulare"].remove(f_dec)
                    v["n"] -= 1
                    return
    mit(ohne_im_entscheid, f"Formular {f_dec}", "n.dec", name="3 n.dec eines Formulars gegen die Listen der Entscheide")
    mit(lambda pf, ov: next(e for e in ov["entscheide"])["verteilung"][0].update(n=0),
        "entscheide", "Liste", name="3 Zahl eines Werts gegen seine Liste im Entscheid")
    mit(lambda pf, ov: next(g for g in ov["gruppen"] if g["key"] == "schrift")["kennzahl"].update(n=0),
        "gruppen", "schrift", name="10 Zahl der Tür gegen ihre Quelle")
    mit(lambda pf, ov: next(g for g in ov["gruppen"] if g["key"] == "barrierefrei")["kennzahl"].update(n=1),
        "gruppen", "barrierefrei", name="10 Zahl der Tür gegen ihre Kennzahl")
    mit(lambda pf, ov: ov["grenzen"].append("Auskunft: amt@example.org"), "«@»", "gestaltung",
        name="5 «@» in der Übersicht")
    mit(lambda pf, ov: pf[f_l]["merkmale"][0].update(d=["siehe ../Verwaltung/liste.xlsx"]), "lokaler Pfad",
        f"Formular {f_l}", name="6 lokaler Pfad beim Formular")
    mit(lambda pf, ov: pf[f_l]["merkmale"][0].update(w="Arial\x00"), "Steuer- oder Sonderzeichen",
        f"Formular {f_l}", name="8 Steuerzeichen beim Formular")
    f_ok = next(fid for fid in sorted(per_form) if not per_form[fid].get("entfaellt")
                and any(m["k"] == "tel_erklaerung" and m["u"] == "vorhanden" for m in per_form[fid]["merkmale"]))
    def zitat_dazu(pf, ov):
        m = next(m for m in pf[f_ok]["merkmale"] if m["k"] == "tel_erklaerung")
        m["d"] = [f"052 000 00 00 ist nur als Telefonnummer bezeichnet: «{profile[f_ok]['telefon'][0]['kontext']}»"]
    mit(zitat_dazu, "tel_erklaerung", f"Formular {f_ok}", name="7 Zitat bei einer erklärten Nummer")
    f_hin = merkmal(overview, "tel_erklaerung")["formulare"]["hinweis"][0]
    def zitat_weg(pf, ov):
        m = next(m for m in pf[f_hin]["merkmale"] if m["k"] == "tel_erklaerung")
        m["d"] = [d for d in m["d"] if not _TEL_ZITAT.search(d)]
    mit(zitat_weg, "tel_erklaerung", f"Formular {f_hin}", "Zitate", name="7 Hinweis ohne das Zitat seiner Nummer")
    f_name = next((fid for fid in sorted(profile) if GT.person_im_titel(profile[fid]["barrierefrei"]["titel"] or "")), None)
    if f_name is None:
        sys.exit("SELBSTTEST: kein gespeicherter Titel sieht aus wie ein Personenname — Prüfung 9 ist nicht belegt")
    mit(lambda pf, ov: next(m for m in pf[f_name]["merkmale"] if m["k"] == "bf_titel").update(
            d=["Titel der Datei: " + _zitat(profile[f_name]["barrierefrei"]["titel"])]),
        "bf_titel", f"Formular {f_name}", "Person", name="9 Titel, der wie ein Personenname aussieht, zitiert")
    print(f"gestaltung_export: {n[0]} Prüfungen feuern auf veränderten Kopien; die echten Daten gehen auf")
