#!/usr/bin/env python3
"""Text detectors of the «Gestaltung» measurement: what a Formular prints about
contact and edition, read from its text lines.

    telefon(lines)                 -> printed phone/fax numbers and how each is explained
    emails(lines)                  -> printed e-mail addresses, as type + domain only
    elemente(seiten, dienststelle) -> edition mark, page numbers, sender on page 1
    schriftgruppe(familie)         -> the typeface of a measured font family, without its cut
    ist_neutral(farbe), ist_blass(farbe) -> what is a grey, what a pale tint (one definition for all file types)
    person_im_titel(text)          -> does a document title look like the name of a person?
    H_…                            -> the fixed parts of the `hinweise` sentences that other code reads

Pure functions on lists of text lines: no file access, standard library only,
so the module may be imported anywhere. The callers (gestaltung_pdf.py,
gestaltung_office.py) pass the lines as their extractor returns them: telefon()
and emails() take all lines of the document in reading order, elemente() the
pages as lists of lines. A caller without a text layer (messart 'pdf_bild')
must not report these values as measured — on empty input the functions say
«nothing found», which is not the same as «not there».

    python3 scripts/gestaltung_text.py      # self-test on built-in example lines

Everything here is a measured fact or nothing. The rules are conservative on
purpose and were checked by eye against the text of all 348 PDF Formulare;
what they cannot see is listed here, so that nobody reads a silent gap as a
finding. Nothing inside an image (logo, scanned page) reaches these functions.

Telefon — Swiss numbers as printed: +41 / 0041 / 0 followed by nine digits,
  with single spaces, dots, hyphens, a slash or parentheses between the groups.
  * The area code or service prefix must exist in the Swiss numbering plan
    (_VORWAHL2/3), and the groups must look like a phone number (one unbroken
    run, or an area code followed by one run or by groups of 2 to 4 digits).
    Digits that continue a longer digit run (IBAN, AHV number, reference and
    form numbers) are never matched; a number that is directly followed by
    further digits is dropped rather than cut. An unbroken run of ten digits,
    a number followed by a space and more digits, and a foreign number count
    only behind a phone or fax label; a number behind «Nr.» without such a
    label is another kind of number.
  * A label without digits («Telefon: ____») yields nothing: only printed
    numbers are reported, never the applicant's fields.
  * `art` is 'fax' when the label directly before the number is Fax/Telefax/F
    (or «zu faxen»), 'telefon' otherwise. An opening bracket or quotation
    mark may stand between the label and the number («per Fax: (052 …)»).
  * `format` follows the printed prefix: 'international' (+41 / 0041),
    'national' (0xx). 'andere' is a number with a foreign country code.
    schreibweise(nummer) gives the digit pattern («999 999 99 99») for
    comparing notations across Formulare.
  * `erklaerung`, three levels. «Names whom» means: the text names an office,
    a role, a person or a purpose (_ZWECK, _ROLLE, _STELLE_WORT/_STELLE_ENDE,
    a given name followed by a surname, the Dienststelle's own name when the
    caller passes it); e-mail and web addresses name nobody.
      'ohne'        no label, and nothing leads to the number: a bare number
                    under an address or at the end of an address line that
                    names no office;
      'bezeichnung' a label says that it is a phone/fax number, but neither its
                    line nor the sender block above it names whom;
      'erklaert'    a label, and its line or the sender block above it names
                    whom — or, without a label, what leads to the number does:
                    the words before it on its line («Bei Fragen:
                    Landwirtschaftsamt, 052 …», «Hans Muster (052 …)»,
                    «SECO | Direktion für Arbeit | 058 …»), together with the
                    line above when the sentence goes on from there (that line
                    ends with a hyphen or a colon, or the number's line begins
                    in lower case), or a purpose line directly above a number
                    that stands alone («Auskunft erteilt: …» ⏎ «052 …»).
    The sender block above a labelled number is read as a reader takes in a
    letterhead: first its address and contact lines (street, postbox, postcode
    and town, web and e-mail addresses, other phone lines, a lone page number;
    at most BLOCK_ADRESSE of them), then, above an address, up to BLOCK_NAMEN
    short lines (at most BLOCK_BREITE characters) — the names of the block.
    One of these lines must name whom. Without address lines only the two
    lines directly above count. A short line of capitalised nouns directly
    above the label («Führerwesen», «Mofa, Kontrollschilder, Schifffahrt»,
    «Aufsicht Sonderschulung und Therapien») names the unit; the labels of
    applicant fields («Unterschrift», «Ort, Datum», «Bemerkungen» …) do not.
    A block that repeats in the document with the same address lines is named
    by a line above it only where it is named every time: otherwise that line
    is text of the page, not the name of the block. Where nothing above names
    whom, a block BELOW the number counts as well, when it has the shape of a
    letterhead: contact lines, then up to BLOCK_NAMEN short lines that an
    address line follows (a text box with the phone lines that the file holds
    before the name of the office).
    A letterhead in two pieces: where the caller says where the pages end
    (seitenweise=True, lines SEITENWECHSEL between the pages), a labelled
    number in a contact block of its own — phone, fax, e-mail and web lines,
    no address line directly above — that stands at the very start or the
    very end of the text of its page is explained by a letterhead elsewhere
    on that page: up to BLOCK_NAMEN short lines of which one names whom,
    followed by an address line, and without a number of its own. (Name and
    address in one text box, the contact lines in another: the file holds
    them apart, a reader sees one letterhead.)
    What this reading cannot see: a name that stands only in a logo image (the
    number is then 'bezeichnung'); a bare number under an office name stays
    'ohne' (it is not said to be a phone number); the order of the lines is
    the one the text extraction gives, so a field label that happens to stand
    directly above an address («Ausgleichskasse» ⏎ «Oberstadt 9») is taken as
    the name of that block; the cells of a table row (Word, Excel) are one
    line. Empty lines are skipped. A label that ends the line above a number
    («Tel. direkt:» ⏎ «052 …») and the label of the number before
    («Tel. 052 … bzw. 052 …») count as standing directly before.
  * A number printed several times is listed once per (e164, art) with its
    most explained occurrence (the first one among equals).
  * «01/02» after a number (two direct numbers in short form) gives two
    entries with the same printed `nummer`.
  * A number broken over two lines by the text extraction is joined only when
    a phone or fax label stands directly before it.
  * `kontext` is the printed line, runs of white space collapsed, at most 100
    characters in all (a cut is marked «…»); the line above and «⏎» stand in
    front when the line holds nothing but the number, when its label ends the
    line above, when the sentence goes on from the line above (see
    'erklaert'), or when the line above is the unit whose number it is (a
    long line then gives up room for it). E-mail addresses
    inside the quote are reduced to «…@domain», and the head of an address
    that the text extraction broke over two lines is cut out, because
    addresses are never stored.
  Not recognised: short numbers (117, 144, 145 …), numbers with fewer or more
  digits than the Swiss plan allows, a foreign number without a label.

E-Mail — one entry per distinct address, in the order of first appearance,
  reduced to `art` and `domain`. 'persoenlich' needs positive evidence: a
  known given name before the dot (vorname.nachname, vorname.zweitname.
  nachname), initials before the dot (v.nachname, h.p.nachname), or the two
  words of «wort.wort» printed as a name on the same or a neighbouring line
  («Xyla Beispiel (xyla.beispiel@…)») — and a last part that is not an office
  word. Everything else is 'funktional' — also a personal address without a
  dot (hmuster@…) or with a given name the list _VORNAMEN does not know and
  no printed name beside it, which cannot be told from a function by
  spelling: 'persoenlich' is a lower bound. One occurrence with the evidence
  is enough for an address that is printed several times.
  Extraction damage is repaired only where it is unambiguous: a stray space or
  a line break inside the domain, a fragment split off the local part directly
  after «E-Mail:», the head of the local part at the end of the line above
  («vorname.» or «vorname.nachn» ⏎ «ame@…»).

Stand-Angabe — an edition mark printed on the form, quoted verbatim (≤ 60
  characters). Three classes, in this order of preference on one page:
  1. a key word followed by a date or number: «zuletzt angepasst am»,
     «ausgedruckt am», Neuausgabe, Freigabedatum, Erscheinungsjahr, «… Ersetzt
     Dokument vom …» anywhere; Stand, Version, Ausgabe, Fassung, Rev., «gültig
     ab» only on a footer-like line — at the start of the line or behind a
     file name, form label, page number or web address, and with no sentence
     going on after it;
  2. a form code with its print date: «Form. bei02 02.23», «Formular 112/25
     (03.25)», «716.052 d 10.2012», «10023d - 01-2024», «Gre-1 a … Juli 2023»,
     «FR_de_01-2025», a date in front of a file name;
  3. a short line that is nothing but a date or month/year — possibly next to
     a page number, initials («ZSW, 12.2022», «Juli 2017/MG»), a year next to
     a page number («2024 1 / 2»), or behind «office;».
  The first page that carries a mark wins. Only when no page carries one:
  4. a year alone on its line, when it is the only such line of its page
     («2024» in the footer of a one-page form; next to a page number the
     same year is class 3).
  NOT a Stand-Angabe: a date field of the applicant, a date in running text
  or in parentheses (the «Stand» of a cited law or of a rate), «gültig bis»,
  a lone «31.12.JJJJ» or «1.1.JJJJ» (the typical reference day of a table),
  the bare dates of a page that prints more than two different ones (a
  table), and the years of a page that prints several alone on their lines.

Seitenzahlen — null for a one-page form. Recognised, in this order of
  preference: «Seite 1 von 3» / «Seite 1/3» / «Seite 1 | 3» (anywhere, any
  numbers); «Seite 2» alone or ending a line, when it is the number of that
  page and no reference («siehe Seite 2»); «2/3», «2 von 3» at the start or
  end of a line when both numbers fit the page and the page count (on page 1
  alone only as a whole line); «- 2 -»; the number of the page alone on its
  line, from page 2 on and only when it is the single such number of the page,
  or in front of a Stand-Angabe; a running footer that ends with the number of
  its page and stands on another page too. `muster` is the first mark of the
  best class, verbatim; seitenzahl_schema(muster) replaces the digits for
  comparing notations. vorhanden = false also covers a form that numbers only
  page 1 with a bare «1» or whose bare numbers do not fit the page order.

Absender — page 1 only. `kanton`: the text names «Kanton Schaffhausen» (also
  «Kantons Schaffhausen», any case, line break allowed, a last letter lost at
  the end of a line tolerated) WHERE IT STANDS LIKE A SENDER: alone, leading
  its line, or closing a line of names («Erziehungsdepartement des Kantons
  Schaffhausen», «zustellen an: Landwirtschaftsamt Kanton Schaffhausen») —
  what stands before it are capitalised words and des / der / und / für /
  von, behind an optional short label that ends with a colon; the head of a
  genitive may stand on the line above («FEUERPOLIZEI DES» ⏎ «KANTONS
  SCHAFFHAUSEN»). Inside a sentence it names a place or another authority,
  not the sender («Wohnsitz im Kanton Schaffhausen seit», «ausserhalb des
  Kantons Schaffhausen», «beim Obergericht des Kantons Schaffhausen»): such
  a mention does not count. `dienststelle`: the
  text prints the Dienststelle's name as recorded in the databank — case, line
  breaks, stray spaces and a genitive ending are ignored, a leading
  «Kantonale(s)» is optional; null when no name was passed in. The name counts
  anywhere on page 1, also in running text, but not inside an e-mail or web
  address, a file name, or the name of a federal body («Bundesamt für
  Polizei», «Eidgenössische Steuerverwaltung»). An older or differently
  worded name of the same office («Tiefbauamt» for «Tiefbau Schaffhausen»,
  «Sicherheitspolizei» for «Polizei») is NOT recognised and gives false, as
  does a name that appears only in a logo image or in letter-spaced type.
  `text` quotes the printed line(s) that carry the evidence (one line: at most
  100 characters; two lines: at most 60 each, joined by «⏎»).

Where this module reads the specification of the measurement more closely
than its wording: 'andere' is used for foreign numbers (every Swiss number
starts with one of the three prefixes); the quotes are white-space collapsed
and never carry an e-mail address; telefon() accepts the Dienststelle's name
as an optional second argument and, with seitenweise=True, lines that are
separated into pages; the key words and form codes of the
Stand-Angabe are those found in the corpus, a superset of the ones first
listed; schreibweise() and seitenzahl_schema() are offered for the comparison
across Formulare.

Where this module CHANGES a definition of the specification (after the check
of the first measurement against the pages of the forms, 2026-10-04):
* `erklaerung` — the specification looked at «the same line or the two lines
  above». That made the level depend on the number of address lines between
  the office name and the number: one letterhead was 'erklaert', the same
  letterhead with a longer address 'bezeichnung' (131 of 172 'bezeichnung'
  entries stood in a block that names the office or its unit). The sender
  block replaces the two lines; the two lines still count.
* 'ohne' — the specification called every number without a label 'ohne'. A
  number that a sentence, a purpose line or a named person leads to is
  explained to a reader («Bei Fragen wenden Sie sich an:» ⏎ «Vorname Name
  (…; 052 …)»); 7 of 15 'ohne' entries were of this kind. 'ohne' is now the
  bare number that nothing leads to.
* `email.art` — a name printed beside the address («Xyla Beispiel
  (xyla.beispiel@…)») is evidence for 'persoenlich'; the specification
  judged by the spelling of the local part alone.
After the acceptance check of the second measurement (method 'gestaltung-2'):
* `erklaerung` — a letterhead in two pieces explains its phone line (see
  above): three Formulare carried 'bezeichnung' although the page names the
  office right beside the number.
* `absender.kanton` — the canton counts only where it stands like a sender.
  Before, any «Kanton(s) Schaffhausen» on page 1 counted: a field label, a
  place in the title of the form, a remedy instruction (17 Formulare).
  `absender.dienststelle` is unchanged: the office's own name counts
  anywhere on page 1, because it names whose Formular it is wherever it
  stands.
* Stand-Angabe — a year alone on its line counts when no page carries
  another mark (one Formular: «2024» in the footer, where its sister form
  prints «2024 1 / 2»).
* quotes never carry a character that no page can show (a control character,
  the private-use glyph of a symbol font): a blank stands in its place.
"""
import bisect
import re
import unicodedata

__all__ = ["telefon", "emails", "elemente", "schreibweise", "seitenzahl_schema", "schriftgruppe", "ist_neutral",
           "ist_blass", "person_im_titel", "SEITENWECHSEL"]

# ---------------------------------------------------------------- sentences of `hinweise` that other code reads
# The comparison layer (gestaltung_export.py) passes some limitations of a measurement on as remarks of a
# Merkmal. It must not depend on the wording of a sentence that is written somewhere else: the fixed part of
# each such sentence is defined once, here. The measuring modules build their sentences from these constants,
# the comparison layer recognises them by the same constants (a sentence contains its constant verbatim).
H_OHNE_TEXT = "Die Seiten tragen keinen auslesbaren Text"
H_UNSICHTBAR = "Der auslesbare Text ist unsichtbar gesetzt"
H_TEIL_UNSICHTBAR = "der Zeichen sind unsichtbar gesetzt"
H_UNLESBAR = "ist nicht lesbar abgelegt"
H_NAMENLOS = "Schriften ohne lesbaren Namen"
H_PLATZHALTERNAME = "Die Datei nennt als Schrift einen Platzhalternamen"
H_SCHRIFT_KNAPP = "Hauptschrift knapp:"
H_GROESSE_KNAPP = "Keine eindeutige Grundgrösse:"
H_NICHT_EINGEBETTET = "Nicht eingebettet"
H_FARBE_NICHT_GEMESSEN = "Farben sind nicht gemessen"
H_FARBE_AUSGELASSEN = "Nicht in die Farbmessung eingegangen:"
H_FARBE_UNTER_SCHWELLE = "Farbe unter der Messschwelle"
H_BILD_SEITE1 = "Seite 1 enthält ein Bild"
H_TAGS_OHNE_FELDER = "Getaggt, aber die Formularfelder sind nicht in den Strukturbaum eingebunden"
H_TAGS_OHNE_UEBERSCHRIFT = "Getaggt, aber ohne Überschriften im Strukturbaum"
H_BAUM_LEER = "der Strukturbaum ist leer"
H_BAUM_OHNE_MARKE = "Strukturbaum vorhanden, aber"
H_MARKE_OHNE_BAUM = "aber ohne Strukturbaum"
H_PDFUA = "Die Datei erklärt sich in ihren Metadaten als PDF/UA"
H_SPRACHE_FREMD = "Die angegebene Dokumentsprache"
H_SPRACHE_TEILE = "Keine Dokumentsprache im Katalog;"
H_TITEL_ANZEIGE = "Die Datei ist so eingestellt, dass das Anzeigeprogramm den Dokumenttitel statt des Dateinamens zeigt"
H_KURZINFO_PLATZHALTER = "als Kurzinfo nur einen Platzhalter"
H_EINE_UEBERSCHRIFT = "Genau ein Absatz trägt eine Überschrift-Formatvorlage"
H_FELDWERT = "aus einem vorausgefüllten Formularfeld gelesen"
H_GESTRICHEN = "Durchgestrichener Text"
H_FORMAT_GEMISCHT = "Seitenformate gemischt:"
H_FORMAT_ABSCHNITTE = "Abschnitte mit unterschiedlichem Seitenformat"
H_FORMAT_BLAETTER = "Tabellenblätter mit unterschiedlichem Seitenformat"
H_SEITENZAHL = "Seitenzahl nicht messbar:"
H_OHNE_UMBRUCH = "Die Datei speichert keine Seitenumbrüche; der Absender"
# two whole sentences that the PDF and the Office measurement share (%s = the colours, as '#rrggbb')
H_LINKFARBE = ("Nur für Internet- und E-Mail-Adressen oder für verlinkte Wörter gesetzt (Link-Farbe) und deshalb "
               "nicht als Akzentfarbe gezählt: %s.")

# a line that separates two pages in the lines handed to telefon(…, seitenweise=True)
SEITENWECHSEL = "\f"
# key in table meta under which scan_gestaltung.py writes the day of the measurement (ISO date); the
# comparison layer reads it
META_STAND = "gestaltung_stand"

# ---------------------------------------------------------------- Farbe: what is a grey, what a pale tint
NEUTRAL_S = 0.15             # HSV saturation below this: a grey
NEUTRAL_V = 0.30             # HSV value below this: black to the eye, whatever its tint
TON_S, TON_V = 0.05, 0.80    # a filled area counts from this saturation when it is this light (a pale field tint)


def _rgb01(farbe):
    """'#rrggbb' or a 3-tuple (0..1 floats, or 0..255 ints) -> three floats 0..1."""
    if isinstance(farbe, str):
        h = farbe.lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    if all(isinstance(c, int) for c in farbe):
        return tuple(c / 255 for c in farbe)
    return tuple(float(c) for c in farbe)


def ist_neutral(farbe, flaeche=False):
    """Black, white and the greys: HSV saturation < 0.15 or value < 0.30.
    flaeche=True asks for a filled area: there a pale tint (saturation from
    0.05, value from 0.80 — the light blue or green of shaded fields) is a
    colour as well; as the colour of text or of a line it is none."""
    r, g, b = _rgb01(farbe)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < NEUTRAL_V:
        return True
    s = (mx - mn) / mx
    if s >= NEUTRAL_S:
        return False
    return not (flaeche and s >= TON_S and mx >= TON_V)


def ist_blass(farbe):
    """A pale tint: a colour that counts as a filled area only (shaded fields),
    because as the colour of text or of a line it would be a grey."""
    return ist_neutral(farbe) and not ist_neutral(farbe, flaeche=True)


# ---------------------------------------------------------------- Schrift: the typeface without its cut
_ZWILLING = {"Times New Roman": "Times"}


def schriftgruppe(familie):
    """The typeface a measured font family belongs to, for comparing Formulare:
    without its cut («Frutiger Condensed» → «Frutiger», «Arial Narrow» →
    «Arial») and with the two names of one design together («Times New
    Roman» → «Times»). The measured family itself stays as it is. (The one
    definition: gestaltung_pdf.py and gestaltung_export.py import it.)"""
    if not familie:
        return familie
    f = re.sub(r" (?:Condensed|Narrow)$", "", familie)
    return _ZWILLING.get(f, f)


# ---------------------------------------------------------------- shared helpers

_SPACES = str.maketrans({"\u00a0": " ", "\u2007": " ", "\u2009": " ", "\u202f": " ", "\t": " ",
                         "\u2010": "-", "\u2011": "-"})
# characters that no page can show — control characters and the private-use glyphs of a symbol font (a
# bullet set in Wingdings): a blank in their place, so that no quote carries one
_UNZEIGBAR = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\ue000-\uf8ff]")
_B = "A-Za-zÄÖÜäöüÀ-ÿ"          # letters, for look-arounds
UMBRUCH = "⏎"


def _clean(line):
    """A line with exotic spaces/hyphens mapped to plain ones and unshowable
    characters replaced by a blank; runs are kept."""
    return _UNZEIGBAR.sub(" ", unicodedata.normalize("NFC", line or "").translate(_SPACES))


def _eng(text):
    """Runs of white space collapsed, ends stripped (how a quote is stored)."""
    return " ".join(text.split())


def _nichtleer(lines):
    return [z for z in (_clean(l) for l in lines or []) if z.strip()]


def _fold(s):
    """Lower case, umlauts as ae/oe/ue, other accents dropped — for name look-ups."""
    s = s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _fenster(text, a, b, n):
    """At most n characters of text that contain text[a:b]; cuts are marked «…»."""
    if len(text) <= n:
        return text
    start = max(0, min(a - (n - (b - a)) * 2 // 3, len(text) - n))
    out = text[start:start + n]
    if start > 0:
        out = "…" + out[1:]
    if start + n < len(text):
        out = out[:-1] + "…"
    return out


def _zitat(text, a, b):
    """(line, a2, b2): text with runs of white space collapsed and the place of
    text[a:b] in it."""
    roh_l, roh_r = text[:a], text[b:]
    links, mitte, rechts = _eng(roh_l), _eng(text[a:b]), _eng(roh_r)
    if links and roh_l[-1:].isspace():
        links += " "
    if rechts and roh_r[:1].isspace():
        rechts = " " + rechts
    return links + mitte + rechts, len(links), len(links) + len(mitte)


# Given names (folded: ae/oe/ue, no accents). Positive evidence for a person in
# an e-mail address (vorname.nachname@) and next to a phone number («Hans Muster»).
_VORNAMEN = frozenset("""
aaron adrian adriana adriano agnes alain albert alberto aldo alessandra alessandro alessia alex alexander
alexandra alexia alfred alfredo alice alina aline alois amelie anastasia andre andrea andreas andrin angela
angelika angelo anita anja anna annamaria anne annemarie annette annina anton antonia antonio ariane armin
arno arnold arthur astrid aurelia barbara bastian beat beata beatrice beatrix ben benedikt benjamin benno
bernadette bernard bernhard bettina bianca birgit bjoern boris brigitta brigitte bruno carina carl carla
carlo carmen carole carolin caroline cecile cedric chantal charles charlotte chiara christa christian
christiane christina christine christof christoph christophe claire clara claudia claudio clemens
conny conrad cora corina corinna corinne cornel cornelia cyril cyrill dagmar damian daniel daniela daniele
danielle dario david deborah denis denise dennis diana diego dieter dietmar dimitri dino dirk dominic
dominik dominique doris dorothea eda edgar edith eduard edwin elena eliane elias elisabeth elke ella ellen
elmar elsbeth emil emilia emma enrico eric erica erich erik erika erna ernst erwin esther eugen eva evelyn
evelyne fabian fabienne fabio fabrice felix ferdinand filip flavia flavio florence florian francesca
francesco francine franco francois frank franz franziska fred frederic fredy friedrich fritz gabi gabriel
gabriela gabriele gabriella georg georges gerald gerda gerhard gertrud gian gianni gino giovanni gisela
giuseppe gloria gottfried gregor guido gustav hanna hannah hannes hans hansjoerg hanspeter hansruedi harald
harry hedwig heidi heike heiko heinrich heinz helen helena helene helga helmut henri henry herbert hermann
hildegard holger hubert hugo ida ignaz ilona ines inge ingrid irene iris irma isabel isabella isabelle
ivan ivana ivo jacqueline jakob jan jana janine jasmin jean jeannette jeannine jennifer jens jeremias
jessica joachim joel joerg johann johanna johannes jolanda jonas jonathan josef josefine joseph josephine
judith juerg juergen julia julian juliane julien juliette julius jutta karin karl karoline katharina kathrin
katja katrin kevin kilian klara klaus konrad kurt lara larissa lars laura laurent lea leandro lena leo leon
leonie leopold lilian liliane lina linda lisa livia lorenz lorenzo lothar louis louise luca lucas lucia
lucie ludwig luigi luis luisa lukas luzia lydia madeleine magdalena maja manfred manuel manuela marc marcel
marcello marco marcus margot margrit maria marianne marie marina mario marion marius mark marko markus
marlene marlies marta martha martin martina mateo mathias matteo matthias maurice mauro max maximilian maya
melanie melina michael michaela michel michele michelle miriam mirjam mirko monica monika moritz myriam
nadia nadine nadja natalie natascha nathalie nicola nicolas nicole niklaus nils nina noah noemi nora
norbert oliver olivia olivier oscar oskar otto pascal pascale patricia patrick patrik paul paula pedro peter
petra philip philipp philippe pia pierre pirmin priska rafael rahel rainer ralf ralph ramon ramona raphael
raphaela raymond rebecca rebekka regina regula reinhard remo renata renate renato rene reto richard rita
robert roberto robin roger roland rolf roman romana romeo ronald rosa rosemarie rosmarie ruben rudolf ruedi
ruth sabina sabine sabrina salome samuel sandra sandro sara sarah sascha sebastian selina serge sergio
severin sibylle silvan silvana silvia silvio simon simona simone sina sofia sonja sophia sophie stefan
stefanie stefano steffen stephan stephanie susanna susanne sven svenja sylvia tamara tanja theo theodor
theres therese thomas tim timo tina tobias tom toni ulrich ulrike urs ursina ursula valentin valentina
valeria valerie vanessa vera verena veronika victor victoria viktor viktoria vincent vinzenz viola vreni
walter waltraud werner wilhelm willi willy wolfgang yannick yves yvonne zoe
agatha bea bernd cindy claudine dana dora elvira fiona flurina gaby gerd hansueli heiner ingo irina ivonne
jacques janina jelena jenny jost karina kaspar kerstin kim kristina kuno ladina lilly lorena luzius maike
mareike margrith marisa marlen marlis martine mathis maurizio melissa meret mike milena mira mona natalia
nico niklas nives noe norman olga otmar ottmar paolo patrizia pius regine renzo ricarda rico roberta saskia
selin seraina silja silke susan sybille tabea tatjana thea till tino trudi ueli ursi ute uwe vivien volker
wendelin xaver xenia yannik yvette yvo zeno zita
""".split())

# Words that mark an office, not a person, as the last part of an e-mail local part.
_FUNKTIONSWORT = frozenset("""
info kontakt contact sekretariat admin office mail post service services support team bestellung
bestellungen anmeldung anmeldungen kontrolle technik dispo nautik naturschutz abklaerung kanzlei zentrale
empfang auskunft beratung personal finanzen recht bewilligung bewilligungen gesuche gesuch meldung
meldungen rechnung rechnungen government voting umzug kurse kurs archiv bibliothek museum redaktion
medien kommunikation it informatik helpdesk hotline
""".split())
_STELLEN_ENDUNG = ("amt", "stelle", "dienst", "dienste", "polizei", "verwaltung", "sekretariat", "kasse",
                   "klinik", "gericht", "departement", "abteilung", "kanzlei", "buero", "inspektorat",
                   "behoerde", "zentrum", "schutz", "steuer", "wesen", "kontrolle", "kommando")


# ---------------------------------------------------------------- E-Mail

_MAIL_LOKAL = re.compile(r"(?<![\w.+\-äöüÄÖÜ])([A-Za-z0-9äöüÄÖÜ](?:[\w.+\-äöüÄÖÜ]*[A-Za-z0-9äöüÄÖÜ_])?)@")
_MAIL_DOMAIN = re.compile(r"(?:[A-Za-z0-9äöüÄÖÜ\-]{1,63}\.){1,8}[A-Za-z]{2,}")
_TLD = frozenset("ch com org net li de at fr it eu swiss info gov edu".split())
_MAIL_VOR = re.compile(r"(?i)(?:e\s?-?\s?mail|mail)(?:\s?-?\s?adresse)?\s?:\s*([a-z0-9][a-z0-9._\-]*)\s$")
# the head of a local part that the text extraction left at the end of the line above
_MAIL_BRUCH = re.compile(r"(?<![\w.@/])((?!www\.)[a-zäöü]{2,}\.(?!(?:ch|com|org|net|li|de)$)[a-zäöü]*)$")
_MAIL_FOLGT = re.compile(r"\s*[A-Za-z0-9äöüÄÖÜ._+\-]*@[A-Za-z0-9äöüÄÖÜ\-]+ ?\.")       # the line goes on inside an address
_MAIL_REST = re.compile(r"[A-Za-z0-9äöüÄÖÜ._+\-]+$")


def _domain(rest, folgezeile):
    """(domain, consumed characters of rest) or (None, 0). Repairs a stray
    space or a line break inside the domain, nothing else."""
    m = _MAIL_DOMAIN.match(rest)
    if m:
        return m.group(0).lower(), m.end()
    sp = rest.find(" ")
    if 0 < sp <= 30 and not rest[sp + 1:sp + 2].isspace():      # «s h.ch», «sh. ch»
        m = _MAIL_DOMAIN.match(rest[:sp] + rest[sp + 1:])
        if m and m.end() > sp and m.group(0).rsplit(".", 1)[1].lower() in _TLD:
            return m.group(0).lower(), m.end() + 1
    if folgezeile is not None and re.fullmatch(r"[A-Za-z0-9äöüÄÖÜ\-.]{1,40}", rest):   # «@m» ⏎ «sd.com»
        m = _MAIL_DOMAIN.match(rest + folgezeile.lstrip())
        if m and m.end() > len(rest) and m.group(0).rsplit(".", 1)[1].lower() in _TLD:
            return m.group(0).lower(), len(rest)
    return None, 0


def _mails_zeile(zeile, vorzeile=None, folgezeile=None):
    """[(a, b, local, domain)] for one cleaned line; a/b are positions in it."""
    out = []
    for m in _MAIL_LOKAL.finditer(zeile):
        am_ende = m.end() + 130 >= len(zeile)
        dom, n = _domain(zeile[m.end():m.end() + 130], folgezeile if am_ende else None)
        if not dom:
            continue
        local, a = m.group(1), m.start()
        ab = max(0, a - 80)
        v = _MAIL_VOR.search(zeile[ab:a])
        if v:                                                    # «E-Mail: strassenverk ehrsamt@…»
            local, a = v.group(1) + local, ab + v.start(1)
        elif vorzeile and not zeile[:a].strip():                 # «vorname.» ⏎ «nachname@…», «vorname.nachn» ⏎ «ame@…»
            v = _MAIL_BRUCH.search(vorzeile.rstrip()[-40:])
            if v:
                local = v.group(1) + local
        out.append((a, m.end() + n, local, dom))
    return out


def _ersetzt(zeile, ersatz):
    """The line with every e-mail address replaced by ersatz(domain)."""
    teile, pos = [], 0
    for a, b, _l, dom in _mails_zeile(zeile):
        if a >= pos:
            teile += [zeile[pos:a], ersatz(dom)]
            pos = b
    return "".join(teile) + zeile[pos:]


def _mail_art(local):
    teile = [t for t in re.split(r"[._]", _fold(local)) if t]
    if not 2 <= len(teile) <= 3 or not all(re.fullmatch(r"[a-z]+(?:-[a-z]+)*", t) for t in teile):
        return "funktional"
    vor, nach = teile[:-1], teile[-1]
    if len(nach) < 3 or nach in _FUNKTIONSWORT or nach.endswith(_STELLEN_ENDUNG):
        return "funktional"
    if all(len(t) == 1 for t in vor):                                    # v.nachname, h.p.nachname
        return "persoenlich"
    if all(p in _VORNAMEN for p in vor[0].split("-")) and (len(vor) == 1 or len(vor[1]) == 1
                                                           or vor[1] in _VORNAMEN):
        return "persoenlich"                                             # vorname(.zweitname).nachname
    return "funktional"


def _name_gedruckt(local, zeilen):
    """Is the local part «wort.wort» printed as a name («Wort Wort», «Wort, Wort»)
    in one of these lines? Then the address is a person's, whatever the given name."""
    teile = [t for t in re.split(r"[._]", _fold(local)) if t]
    if len(teile) != 2 or not all(re.fullmatch(r"[a-z]{3,}(?:-[a-z]+)*", t) for t in teile):
        return False
    vor, nach = teile
    if nach in _FUNKTIONSWORT or vor in _FUNKTIONSWORT or nach.endswith(_STELLEN_ENDUNG) or vor.endswith(_STELLEN_ENDUNG):
        return False
    rx = re.compile(r"(?<![a-z])(?:" + re.escape(vor) + r"\s+" + re.escape(nach) + "|" + re.escape(nach)
                    + r",?\s+" + re.escape(vor) + r")(?![a-z])")
    return any(rx.search(_fold(zeile)) for zeile in zeilen)


def emails(lines):
    """Printed e-mail addresses as [{"art": "funktional"|"persoenlich", "domain": str}],
    one entry per distinct address in the order of first appearance. The
    address itself is never returned."""
    z = _nichtleer(lines)
    out, gesehen = [], {}
    for i, zeile in enumerate(z):
        for _a, _b, local, dom in _mails_zeile(zeile, z[i - 1] if i else None, z[i + 1] if i + 1 < len(z) else None):
            art = _mail_art(local)
            if art == "funktional" and _name_gedruckt(local, z[max(0, i - 1):i + 2]):
                art = "persoenlich"
            key = (local.lower(), dom)
            if key not in gesehen:
                gesehen[key] = len(out)
                out.append({"art": art, "domain": dom})
            elif art == "persoenlich":                      # one occurrence beside the printed name is enough
                out[gesehen[key]]["art"] = art
    return out


def _ohne_adressen(zeile):
    """The line without e-mail and web addresses (they do not name an office)."""
    zeile = _ersetzt(zeile, lambda _dom: " ")
    return re.sub(r"(?i)\b(?:https?://|www\.)\S+|(?<![\w.\-])[\w\-]{1,63}(?:\.[\w\-]{1,63}){0,6}\.(?:ch|com|org|net)\b(?:/\S*)?",
                  " ", zeile)


# ---------------------------------------------------------------- Telefon

# National destination codes of the Swiss numbering plan (BAKOM): two digits
# after the trunk 0 for geographic, corporate (58) and mobile (74–79) numbers,
# three digits for the service numbers.
_VORWAHL2 = frozenset("21 22 24 26 27 31 32 33 34 41 43 44 51 52 55 56 58 61 62 71 74 75 76 77 78 79 81 91".split())
_VORWAHL3 = frozenset("800 840 842 844 848 900 901 906".split())

_S = r"(?: ?/ ?|[ .\-])"                      # one separator between two digits of a number
_TEL = re.compile(
    r"(?<![\d+])(?:"
    r"(?P<ip>\+ ?41|0041) ?(?P<i0>\( ?0 ?\) ?|0)?(?P<ir>(?:\(\d{2}\)|\d{2})(?:" + _S + r"?\d){7})"
    r"|(?P<nr>(?:\(0\d{2}\)|0\d{2})(?:" + _S + r"?\d){7})"
    r"|(?P<ap>\+ ?|00)(?P<ar>(?!41)[1-9]\d{0,2}(?: ?\(0\))?(?:[ .\-/]?\d){6,12})"
    r")")

_L_FAX = r"Telefax|Fax|faxen"
_L_TEL = (r"Telefonnummer|Telefon|Telephon|Tel|Natel|Mobiltelefon|Mobilnummer|Mobile|Mobil|Handy|Fon|Phone|"
          r"Hotline|Helpline|Infoline|Gratisnummer|Rufnummer|Servicenummer|Notfallnummer|Direktwahl|telefonisch")
_LABEL = re.compile(
    r"(?:^|(?<=[^" + _B + r"]))(?:"
    r"(?P<lang>(?i:" + _L_FAX + "|" + _L_TEL + r"))\.?(?:\s?-?\s?(?i:Nummer|Nr)\.?)?"
    r"(?:\s+[" + _B + r"][" + _B + r".\-]{0,13}){0,2}"            # «direkt», «Nr.», «für Rückfragen»
    r"|(?P<kurz>[TFM])"
    r")\s?[:.]?\s*[(\[«„\"]?\s*$")
_KETTE = re.compile(r"^\s*(?:\([^()]{0,30}\))?\s*(?:,|;|/|oder|bzw\.?|resp\.?|und)?\s*$")
_KETTE_ENDE = re.compile(r"^\s*(?:\([^()]{0,30}\))?\s*(?:,|;|/|oder|bzw\.?|resp\.?|und)\s*$")

_ZWECK = re.compile(
    r"(?i)(?<![" + _B + r"])(?:auskunft|auskünfte|fragen|rückfragen|kontakt\w*|zuständig(?:e[mnrs]?)?|erreich(?:bar\w*|en|t)|"
    r"beratung\w*|ansprech\w+|informationen|notfall\w*|pikett\w*)(?![" + _B + r"])")
_ROLLE = re.compile(
    r"(?<![" + _B + r"])(?:Sachbearbeit\w+|Kantons(?:arzt|ärztin|apotheker(?:in)?|tierarzt|tierärztin)|"
    r"(?:Frau|Herrn?)\s+(?!Herr|Frau|Name|Vorname|Dr\b|und\b|oder\b)[A-ZÄÖÜ][a-zäöü]+|"
    r"Dr\.\s*(?:med\.\s*)?[A-ZÄÖÜ][a-zäöü]+)")
_STELLE_WORT = frozenset("""amt abteilung sekretariat fachstelle dienststelle stelle amtsstelle kanzlei
staatskanzlei departement inspektorat notariat kommando zentrale gefängnis institut direktion
ag gmbh""".split())
_STELLE_ENDE = ("amt", "amtes", "amts", "stelle", "verwaltung", "polizei", "inspektorat", "behörde", "kasse",
                "klinik", "gericht", "departement", "sekretariat", "abteilung", "kanzlei", "büro", "kommando",
                "notariat", "anstalt", "institut", "direktion")
_KEINE_STELLE = frozenset("""gesamt insgesamt samt mitsamt allesamt baustelle arbeitsstelle lehrstelle
feuerstelle haltestelle tankstelle schnittstelle messstelle""".split())
_DIENST = re.compile(r"[A-ZÄÖÜ][a-zäöü]+(?:er|e)\s+Dienste?(?![" + _B + r"])")
_STRASSE = re.compile(r"(?i)^[\- ]?(?:\w+[\- ])?(?:strasse|str\.|weg|gasse|gässchen|platz|allee)")
_WORT = re.compile(r"[" + _B + r"]+(?:-[" + _B + r"]+)*")

_RANG = {"ohne": 0, "bezeichnung": 1, "erklaert": 2}


def _wort(w):
    """A word as a pattern that tolerates a stray space between its letters."""
    return r"\s?".join(re.escape(ch) for ch in w)


def _name_rx(name):
    """The name of a Dienststelle as a pattern: white space flexible, stray
    spaces inside words tolerated, genitive ending allowed, whole words only;
    a leading «Kantonale(s)» is optional."""
    kern = re.sub(r"^(?i:kantonale[rsn]?)\s+", "", name.strip())
    if not kern:
        return None
    return re.compile(r"(?<![" + _B + r"_])" + r"\s*".join(_wort(t) for t in kern.split())
                      + r"(?:e?s)?(?![" + _B + r"_])", re.I)


_FREMD = re.compile(r"(?i)(?:eidgenössische[nrs]?|eidg\.|schweizerische[nrs]?|bundesamt\s+für|bundes)\s*$")


def _nennt_stelle(rx, text):
    """The first place where the text prints the Dienststelle's name — not
    where the name belongs to a federal body («Bundesamt für Polizei»)."""
    for m in rx.finditer(text):
        if not _FREMD.search(text[max(0, m.start() - 40):m.start()]):
            return m
    return None


def _nennt_wen(text, dienst_rx=None):
    """Does the text name an office, a role, a person or a purpose?"""
    t = _ohne_adressen(text)
    if _ZWECK.search(t) or _ROLLE.search(t) or _DIENST.search(t):
        return True
    if dienst_rx is not None and _nennt_stelle(dienst_rx, t):
        return True
    for m in _WORT.finditer(t):
        w = m.group(0)
        k = w.lower()
        if k in _KEINE_STELLE or not w[0].isupper():
            continue
        if (k in _STELLE_WORT and (k not in ("ag", "gmbh") or w in ("AG", "GmbH"))) \
                or (len(k) > 4 and k.endswith(_STELLE_ENDE)):
            return True
        if _fold(w) in _VORNAMEN and len(w) > 2:                   # «Hans Muster», not «Ernst Müller-Strasse»
            n = re.match(r"\s+([A-ZÄÖÜ][a-zäöüéèà]+(?:-[A-ZÄÖÜ][a-zäöüéèà]+)?)", t[m.end():])
            if n and not _STRASSE.match(t[m.end() + n.end():]) and not _STRASSE.match(" " + n.group(1)):
                return True
    return False


def _gruppen_ok(gruppen, erste):
    """Digit groups as a phone number is written: one unbroken run, or an area
    code followed by one run or by groups of two to four digits."""
    return len(gruppen) == 1 or (len(gruppen[0]) in erste
                                 and (len(gruppen) == 2 or all(2 <= len(g) <= 4 for g in gruppen[1:])))


def _nummern(text):
    """Phone-number candidates of one cleaned line that pass every check:
    [{a, b, nummer, e164: [..], format, bedingt}]. `bedingt` marks a candidate
    that counts only behind a phone or fax label: a foreign number, an
    unbroken run of ten digits, a number followed by further digits."""
    out = []
    for m in _TEL.finditer(text):
        a, b = m.span()
        vor, nach = text[max(0, a - 80):a], text[b:b + 40]
        nachbar = bool(out) and out[-1]["b"] == a - 1 and text[a - 1] == " "     # «052 632 75 28 052 632 75 27»
        if m.group("ar") is not None:
            ziffern = re.sub(r"\D", "", m.group("ar").replace("(0)", ""))
            if not 8 <= len(ziffern) <= 14:
                continue
            fmt, e164, bedingt = "andere", "+" + ziffern, True
        elif m.group("ip") is not None:
            nsn, fmt, bedingt = re.sub(r"\D", "", m.group("ir")), "international", False
            if not _gruppen_ok(re.findall(r"\d+", m.group("ir")), (2, 3)):
                continue
        else:
            nsn, fmt = re.sub(r"\D", "", m.group("nr"))[1:], "national"
            gruppen = re.findall(r"\d+", m.group("nr"))
            if not _gruppen_ok(gruppen, (3, 4)):
                continue
            if re.search(r"(?:\d[ .\-'’/]?|[" + _B + r"_])$", vor) and not nachbar:
                continue                      # the tail of a longer digit run or of a code («CH93 0076 …»)
            if re.search(r"(?i)(?<![" + _B + r"])(?:nr|no|nummer)\.?\s?:?\s*$", vor) and not _LABEL.search(vor):
                continue                      # «Kunden-Nr. 044 …»: another kind of number
            bedingt = len(gruppen) == 1
        if fmt != "andere":
            if len(nsn) != 9 or not (nsn[:2] in _VORWAHL2 or nsn[:3] in _VORWAHL3):
                continue
            e164 = "+41" + nsn
        alle = [e164]
        zusatz = re.match(r"/(\d{2})(?![\d.])", nach) if fmt != "andere" else None
        if zusatz:                            # «… 71 01/02»: two numbers in short form
            b += zusatz.end()
            alle.append(e164[:-2] + zusatz.group(1))
        elif re.match(r"[.\-'’/]?\d", nach):
            continue                          # the digits go on: not a phone number
        elif re.match(r" \d", nach) and not _TEL.match(nach.lstrip()) and not re.match(r" \d{4} [A-ZÄÖÜ]", nach):
            bedingt = True                    # «… 78 21 1/2»: only behind a label
        out.append({"a": a, "b": b, "nummer": _eng(text[a:b]), "e164": alle, "format": fmt, "bedingt": bedingt})
    return out


# ---- the sender block above a number: its address and contact lines, and the name lines above them
_ADR_PLZ = re.compile(r"(?<![\d.])(?:[A-Z]{1,2}[- ] ?)?[1-9]\d{3} [A-ZÄÖÜ][a-zäöü]")            # «CH-8200 Schaffhausen»
_ADR_HAUSNR = re.compile(r"[A-ZÄÖÜ][" + _B + r".\- ]{2,40} \d{1,3} ?[A-Za-z]?")                 # «Herrenacker 3»
_ADR_POSTFACH = re.compile(r"(?i)\s*(?:postfach|case postale)\b")
_KONTAKT_WORT = re.compile(r"(?i)(?<![" + _B + r"])(?:e-?mail|mail|internet|web|website|homepage)(?![" + _B + r"])\.?\s?:?")
_LABEL_VORN = re.compile(r"\s*(?:(?i:" + _L_FAX + "|" + _L_TEL + r")(?![" + _B + r"])|[TFM] ?[:.]? ?\(?\+?\d)")
BLOCK_ADRESSE, BLOCK_NAMEN, BLOCK_BREITE = 6, 3, 70     # lines of address/contact, name lines above, their length
_EINHEIT_BINDEWORT = frozenset("und für der des die von".split())
_KEINE_EINHEIT = frozenset("""unterschrift unterschriften stempel datum ort name vorname nachname adresse
bemerkungen bemerkung telefon telefonnummer fax mail email seite kanton schaffhausen schweiz beilagen beilage
ja nein total summe betrag anzahl hinweis hinweise wichtig achtung formular gesuch antrag""".split())


def _adresszeile(t):
    """A street, postbox or postcode line («Mühlentalstrasse 105», «CH-8200 Schaffhausen»)."""
    t = t.strip()
    return len(t) <= 80 and bool(_ADR_PLZ.search(t) or _ADR_HAUSNR.fullmatch(t) or _ADR_POSTFACH.match(t))


def _kontaktzeile(t):
    """A line of a contact block that names nobody: a web or e-mail address,
    another phone or fax line, a lone page number. A bare label («Telefon»,
    «E-Mail» — a field of the applicant) is none."""
    ohne = _ohne_adressen(t)
    if not (re.search(r"\d", t) or ohne != t):
        return False
    return bool(_LABEL_VORN.match(t)) or not re.search(r"[" + _B + r"]", _KONTAKT_WORT.sub(" ", ohne))


def _einheit(t):
    """A short line of capitalised nouns («Führerwesen», «Mofa, Kontrollschilder,
    Schifffahrt», «Aufsicht Sonderschulung und Therapien»): directly above a
    phone label it names the unit whose number follows."""
    t = _eng(_ohne_adressen(t))
    if not t or len(t) > 50 or re.search(r"[\d:;.!?_…()/|]", t):
        return False
    worte = _WORT.findall(t)
    if not 1 <= len(worte) <= 5 or not worte[0][0].isupper():
        return False
    for w in worte:
        if w[0].islower():
            if w not in _EINHEIT_BINDEWORT:
                return False
        elif len(w) < 4 or _fold(w) in _KEINE_EINHEIT:
            return False
    return True


def _vorkommen(lines, dienststelle=None, seitenweise=False):
    """Every printed occurrence, in reading order, as the dicts telefon() returns
    (plus «zeile», the index among the non-empty lines)."""
    z, seite, nr = [], [], 0                       # the non-empty lines, and the page each stands on
    for roh in lines or []:
        if seitenweise and roh == SEITENWECHSEL:
            nr += 1
            continue
        t = _clean(roh)
        if t.strip():
            z.append(t)
            seite.append(nr)
    dienst_rx = _name_rx(dienststelle) if dienststelle else None
    out = []
    nennt = {}                                     # line index -> the line names an office, role, person, purpose
    block = {}                                     # line index -> the sender block above it names whom
    offen = [-9, False, "telefon"]                 # line index, label, art of a chain left open at a line end

    def nennt_wen(k):
        if k not in nennt:
            nennt[k] = _nennt_wen(z[k], dienst_rx)
        return nennt[k]

    def oben_nennt(i):
        return any(nennt_wen(k) for k in range(max(0, i - 2), i))

    def block_nennt(j):
        """(named, how, address lines) for the sender block above line j: its
        address and contact lines (they name nobody, but one of them may:
        «Kantonale Feuerpolizei, Herrenacker 3»), then up to BLOCK_NAMEN short
        lines — the names of a letterhead. A unit name directly above line j
        counts as well. `how` says which part named whom."""
        if j not in block:
            k, wie, adresse = j - 1, "einheit" if j > 0 and _einheit(z[j - 1]) else None, []
            while not wie and k >= 0 and j - 1 - k < BLOCK_ADRESSE and (_kontaktzeile(z[k]) or _adresszeile(z[k])):
                adresse.append(_eng(z[k]))
                wie = "adresse" if nennt_wen(k) else None
                k -= 1
            for _ in range(BLOCK_NAMEN if adresse else 0):  # name lines stand above an address, not above a bare label
                if wie or k < 0 or len(_eng(z[k])) > BLOCK_BREITE:
                    break
                wie = "name" if nennt_wen(k) else None
                k -= 1
            block[j] = (bool(wie), wie, tuple(adresse))
        return block[j]

    def block_unten(i):
        """A sender block BELOW line i — a letterhead whose phone lines stand
        above its name (a text box that the file holds first): contact lines,
        then up to BLOCK_NAMEN short lines that an address line follows."""
        k = i + 1
        while k < len(z) and k - i <= BLOCK_ADRESSE and _kontaktzeile(z[k]):
            k += 1
        namen = []
        while (k < len(z) and len(namen) < BLOCK_NAMEN and len(_eng(z[k])) <= BLOCK_BREITE
               and not _adresszeile(z[k]) and not _kontaktzeile(z[k])):
            namen.append(k)
            k += 1
        return bool(namen) and k < len(z) and _adresszeile(z[k]) and any(nennt_wen(n) for n in namen)

    def briefkopf_nennt(i):
        """The number stands in a contact block of its own — phone, fax, e-mail and
        web lines, no address — at the very start or the very end of the text of
        its page, and the same page carries a letterhead without a number: up to
        BLOCK_NAMEN short lines of which one names whom, then an address line. A
        letterhead in two text boxes (name and address left, contact lines right)
        reaches the text in two pieces; a reader sees one. Only where the caller
        says where the pages end (seitenweise)."""
        if not seitenweise or not _kontaktzeile(z[i]):
            return False
        a = b = i
        while a > 0 and seite[a - 1] == seite[i]:
            a -= 1
        while b + 1 < len(z) and seite[b + 1] == seite[i]:
            b += 1
        lo = hi = i
        while lo > a and _kontaktzeile(z[lo - 1]):
            lo -= 1
        while hi < b and _kontaktzeile(z[hi + 1]):
            hi += 1
        if lo != a and hi != b:
            return False                           # not detached: text of the page on both sides
        for k in range(a, b + 1):
            if lo <= k <= hi or not _adresszeile(z[k]) or (k > a and _adresszeile(z[k - 1])):
                continue                           # k = the first address line of a block
            namen = []
            for n in range(k - 1, max(a, k - BLOCK_NAMEN) - 1, -1):
                if len(_eng(z[n])) > BLOCK_BREITE or _kontaktzeile(z[n]) or lo <= n <= hi:
                    break
                namen.append(n)
            m, eigene = k, False                   # a letterhead with a number of its own explains only that one
            while m <= b and (_adresszeile(z[m]) or _kontaktzeile(z[m])):
                eigene = eigene or bool(_LABEL_VORN.match(z[m]))
                m += 1
            if namen and not eigene and any(nennt_wen(n) for n in namen):
                return True
        return False

    def aufnehmen(i, text, treffer, nur_mit_label=False):
        umfeld = []                                # filled once: explained by this line or the block above
        allein = not re.search(r"[" + _B + r"]", text)
        letzte = None                              # (end, label, art) of the previous number on this line
        oben = z[i - 1].rstrip() if i > 0 and not nur_mit_label else ""
        # a sentence that goes on from the line above: that line leads to the number as well
        fortsetzung = bool(oben) and (oben.endswith(("-", ":")) or re.match(r"\s*[a-zäöü]", _ohne_adressen(text)) is not None)
        # the line as it is quoted: e-mail addresses reduced to «…@domain»; enden/versatz map a place in
        # text to its place in maske
        teile, pos, enden, versatz = [], 0, [0], [0]
        for ma, mb, _l, dom in _mails_zeile(text):
            if ma >= pos and not any(t["a"] < mb and ma < t["b"] for t in treffer):
                teile += [text[pos:ma], "…@" + dom]
                enden.append(mb)
                versatz.append(versatz[-1] + len(dom) + 2 - (mb - ma))
                pos = mb
        maske = "".join(teile) + text[pos:]
        if i + 1 < len(z) and _MAIL_FOLGT.match(z[i + 1]) and not nur_mit_label and _MAIL_BRUCH.search(maske.rstrip()[-40:]):
            maske = _MAIL_REST.sub("…", maske.rstrip())      # the head of an address that goes on in the next line

        def zitat(a, b):                           # (collapsed quote, place of the number in it)
            a, b = (x + versatz[bisect.bisect_right(enden, x) - 1] for x in (a, b))
            lo, hi = max(0, a - 250), min(len(maske), b + 250)
            zeile, a2, b2 = _zitat(maske[lo:hi], a - lo, b - lo)
            if (lo == 0 or a2 > 100) and (hi == len(maske) or len(zeile) - b2 > 100):
                return zeile, a2, b2               # the cut-out holds everything a 100-character quote can show
            return _zitat(maske, a, b)

        for t in treffer:
            vor = text[max(0, t["a"] - 200):t["a"]]
            if t["a"] > 200:
                vor = vor.split(" ", 1)[-1]                    # no word cut in half
            lm = _LABEL.search(vor)
            oben_label = False
            if not lm and i > 0 and not nur_mit_label and not re.search(r"[\w" + _B + r"]", vor):
                lm = _LABEL.search(z[i - 1].rstrip()[-90:])    # the label ends the line above («Tel. direkt:» ⏎ number)
                oben_label = bool(lm)
            label, art, kette = bool(lm), "telefon", False
            if lm:
                if (lm.group("lang") or lm.group("kurz")).lower() in ("telefax", "fax", "faxen", "f"):
                    art = "fax"
            elif letzte and _KETTE.match(text[letzte[0]:t["a"]]):           # «Tel. 052 … bzw. 052 …»
                label, art = letzte[1], letzte[2]
            elif letzte is None and offen[0] == i - 1 and not vor.strip():   # … «bzw.» ⏎ «052 …»
                label, art, kette = offen[1], offen[2], True
            letzte = (t["b"], label, art)
            if (t["bedingt"] or nur_mit_label) and not label:
                continue
            if label:
                if not umfeld:
                    j = i - 1 if oben_label else i             # the line that carries the label
                    if _nennt_wen(text, dienst_rx):
                        umfeld.append(("zeile", ()))
                    elif oben_nennt(i):
                        umfeld.append(("oben", ()))
                    else:
                        ja, wie, adresse = block_nennt(j)
                        if not ja and not nur_mit_label and block_unten(i):
                            ja, wie, adresse = True, "unten", ()
                        if not ja and not adresse and not nur_mit_label and not oben_label and briefkopf_nennt(i):
                            ja, wie = True, "briefkopf"
                        umfeld.append((wie if ja else None, adresse))
                grund, adresse = umfeld[0]
                erkl = "erklaert" if grund else "bezeichnung"
            else:
                # no label: explained by what leads to the number — the words before it on its line (and the
                # line above, when the sentence goes on from there), or a purpose line above a number alone
                fuehrt = (oben + " " + vor) if fortsetzung else vor
                grund, adresse = None, ()
                if _nennt_wen(fuehrt, dienst_rx):
                    grund = "zeile"
                elif allein and oben and _ZWECK.search(_ohne_adressen(oben)):
                    grund = "oben"
                erkl = "erklaert" if grund else "ohne"
            zeile, a2, b2 = zitat(t["a"], t["b"])
            kontext = _fenster(zeile, a2, b2, 100)
            if (allein or oben_label or fortsetzung or kette or grund == "einheit") and i > 0 and not nur_mit_label:
                # the line above belongs to the quote; a long line gives up room for it
                dar = _eng(_ohne_mail_lokal(z[i - 1]))
                if _MAIL_FOLGT.match(text) and _MAIL_BRUCH.search(dar[-40:]):
                    dar = _MAIL_REST.sub("…", dar)             # the line above ends inside an address
                unten = _fenster(zeile, a2, b2, 100 - 3 - min(len(dar), 37))
                platz = 100 - len(unten) - 3
                if platz >= 8:
                    kontext = (dar if len(dar) <= platz else "…" + dar[-(platz - 1):]) + " " + UMBRUCH + " " + unten
            for e in t["e164"]:
                out.append({"nummer": t["nummer"], "e164": e, "format": t["format"], "art": art,
                            "erklaerung": erkl, "kontext": kontext, "zeile": i, "grund": grund, "adresse": adresse})
        if letzte and letzte[1] and not nur_mit_label and _KETTE_ENDE.match(text[letzte[0]:letzte[0] + 60]):
            offen[:] = [i, letzte[1], letzte[2]]         # a labelled number, then «bzw.» at the end of the line

    for i, text in enumerate(z):
        aufnehmen(i, text, _nummern(text))
        # a number broken over two lines by the extraction: only behind a label
        if i + 1 < len(z) and re.search(r"(?:\d|\+ ?41|\()$", text.rstrip()) and re.match(r"\s*\d", z[i + 1]):
            links, rechts = text.rstrip(), z[i + 1].lstrip()
            for zusammen in (links + rechts, links + " " + rechts):
                ueber = [t for t in _nummern(zusammen) if t["a"] < len(links) < t["b"]]
                if ueber:
                    aufnehmen(i, zusammen, ueber, nur_mit_label=True)
                    break
    return out


def _ohne_mail_lokal(zeile):
    """The line with every e-mail address reduced to «…@domain» (addresses are not stored)."""
    return _ersetzt(zeile, lambda dom: "…@" + dom)


def telefon(lines, dienststelle=None, seitenweise=False):
    """Printed phone and fax numbers of a document (all its lines, in reading order):
    [{"nummer", "e164", "format", "art", "erklaerung", "kontext"}], one entry per
    distinct (e164, art) with its most explained occurrence. `dienststelle`
    (optional) lets the office's own name count as an explanation.
    seitenweise=True: the caller separates the pages by a line SEITENWECHSEL —
    then a contact block that stands apart from the letterhead of its page is
    read together with it (see 'erklaert' in the module docstring)."""
    beste, folge = {}, []
    alle = _vorkommen(lines, dienststelle, seitenweise)
    # a block that repeats in the document (the same address lines above the same number) is named
    # only where it is named every time: other lines above it are the text of the page, not its name
    je_block = {}
    for v in alle:
        if v["adresse"]:
            je_block.setdefault((v["e164"], v["art"], v["adresse"]), []).append(v)
    for gruppe in je_block.values():
        if any(v["grund"] is None for v in gruppe):
            for v in gruppe:
                if v["grund"] == "name":
                    v["grund"], v["erklaerung"] = None, "bezeichnung"
    for v in alle:
        key = (v["e164"], v["art"])
        if key not in beste:
            folge.append(key)
            beste[key] = v
        elif _RANG[v["erklaerung"]] > _RANG[beste[key]["erklaerung"]]:
            beste[key] = v
    return [{k: beste[key][k] for k in ("nummer", "e164", "format", "art", "erklaerung", "kontext")}
            for key in folge]


_TITEL_DATUM = re.compile(r"\d{1,2}\.\s?\d{1,2}\.\s?(?:\d{2}|\d{4})")
_TITEL_NAME = r"[A-ZÄÖÜ][a-zäöüéèàç]+(?:-[A-ZÄÖÜ][a-zäöüéèàç]+)?"


def person_im_titel(text):
    """Does this document title look like the name of a person — the author's
    stamp that a word processor leaves behind? True for a known given name
    followed by a capitalised word («Hans Muster», «Muster Hans» is not seen),
    and for one or two capitalised words followed by nothing but a day
    («Muster 26.4.01»): a title like that names no Formular, and whose name it
    is cannot be told from here. Conservative on purpose: a title that says
    more is a title."""
    t = _eng(_clean(text or ""))
    if re.fullmatch(_TITEL_NAME + r"(?: " + _TITEL_NAME + r")? ?,? ?" + _TITEL_DATUM.pattern, t):
        return True
    for m in _WORT.finditer(t):
        w = m.group(0)
        if len(w) > 2 and w[0].isupper() and _fold(w) in _VORNAMEN:
            n = re.match(r"\s+(" + _TITEL_NAME + r")", t[m.end():])
            if n and not _STRASSE.match(t[m.end() + n.end():]) and not _STRASSE.match(" " + n.group(1)) \
                    and _fold(n.group(1)) not in _VORNAMEN | _KEINE_EINHEIT and not n.group(1).lower().endswith(_STELLE_ENDE):
                return True
    return False


def schreibweise(nummer):
    """The notation of a printed number with every digit as 9: «+99 99 999 99 99»."""
    return re.sub(r"\d", "9", nummer)


# ---------------------------------------------------------------- Elemente: Stand-Angabe

_MONATE = (r"Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|"
           r"Jan\.?|Febr?\.?|Mrz\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sept?\.?|Okt\.?|Nov\.?|Dez\.?|"
           r"janvier|février|mars|avril|juin|juillet|août|septembre|octobre|novembre|décembre|"
           r"gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|dicembre")
_JAHR = r"(?:19[89]\d|20[0-3]\d)"
_TAG = r"(?:0?[1-9]|[12]\d|3[01])"
_MON = r"(?:0?[1-9]|1[0-2])"
_D_VOLL = _TAG + r"\. ?" + _MON + r"\. ?" + _JAHR                      # 11.02.2022
_D_MONAT = r"(?i:" + _MONATE + r") " + _JAHR                           # Juni 2024, juin 2019
_D_TEXT = r"(?:" + _TAG + r"\. ?)?" + _D_MONAT                         # 1. Mai 2025, Juni 2024
_D_ISO = _JAHR + r"[-.]" + _MON + r"(?:[-.]" + _TAG + r")?"           # 2023-06-13, 2022.11.25, 2022-01
_D_MJ = _MON + r"[./_\-]" + _JAHR                                     # 12.2017, 05/2023, 03_2023, 01-2024
_D_MJ2 = _MON + r"\.\d{2}"                                            # 05.20 — only next to a form code
_DATUM = r"(?:" + _D_VOLL + "|" + _D_TEXT + "|" + _D_ISO + "|" + _D_MJ + r")"
_ENDE = r"(?![\d.]\d|\d)"                                             # the value ends here

# 1a. key words that can only mean the edition of the document: no further checks
_STAND_KLAR = re.compile(
    r"(?<![" + _B + r"])(?:(?i:(?:zuletzt|letztmals) (?:angepasst|geändert|aktualisiert|überarbeitet)(?: am)?|"
    r"letzte Änderung|(?:aus)?gedruckt am|Druckdatum|Neuausgabe|Freigabedatum|Erscheinungsdatum)\s?:?\s?" + _DATUM + _ENDE +
    r"|(?i:Erscheinungsjahr)\s?:?\s?" + _JAHR + r"(?!\d)"
    r"|" + _D_VOLL + r" Ersetzt (?:Dokument|Version|Ausgabe) vom(?: " + _D_VOLL + r")?)")
# 1b. key words that also occur in running text: only on a footer-like line
_SW_DATUM = r"Stand|STAND|Fassung|[Gg]ültig ab|Freigabe"
_SW_VERSION = r"Version|VERSION|Vers\.|Ausgabe|Rev\.|Revision"
_STAND_SW = re.compile(
    r"(?<![" + _B + r"(\-])(?:"
    r"(?:" + _SW_DATUM + r")\s?:?\s?(?:(?:am|vom|per) )?(?:" + _DATUM + "|" + _JAHR + r")" + _ENDE +
    r"|(?:" + _SW_VERSION + r")\s?:?\s?(?:(?:am|vom|per|gültig ab) )?"
    r"(?:" + _DATUM + "|" + _JAHR + r"(?:/\d{1,2})?|\d{1,2}(?:\.\d{1,3}){0,2})" + _ENDE +
    r")(?: ?/ ?" + _DATUM + _ENDE + r")?")
_VOR_OK = re.compile(
    r"\d{1,3}|(?:https?://|www\.)\S+|.*\.(?:docx?|dotx?|xlsx?|pdf)\b.*|(?:Formular|Form\.?|File|Datei|Dok\.?|Dokument|FO)\b.*|"
    r"(?:Seite|S\.) ?\d+(?: ?(?:von|/|\|) ?\d+)?|[^a-zäöü]{1,30}/|.{1,60}\|")
# 2. a form code with its print date
_FORM_LABEL = re.compile(r"(?<![" + _B + r"])(?:Formular|Form\.?) (?=\S*\d)(\S+)")
_FORM_WERT = re.compile(
    r"(?<![\w.])(?:\((?:" + _D_MJ2 + "|" + _D_MJ + r")\)|(?:" + _D_VOLL + "|" + _D_MJ + "|" + _D_MJ2 + r")" + _ENDE +
    r"|V ?\d{1,2}(?:\.\d{1,2})?(?![\d.])(?: " + _JAHR + r"(?!\d))?)")
_BUND_CODE = re.compile(r"(?<![\d.])\d{3}\.\d{3}(?:\.\d{1,3})? [dfi]{1,3} (?:" + _D_MJ + r"|\d{1,2}\.\d{2})" + _ENDE)
_CODE_STRICH = re.compile(r"\w{3,12} ?[-–] ?" + _D_MJ)                                     # «10023d - 01-2024»
_CODE_ZEILE = re.compile(r"(?P<code>[A-Za-z]{1,6}-?\d+[a-z]?(?: [a-z])?) .{3,70} (?P<d>" + _D_MONAT + "|" + _D_MJ + r")")
_FRIST = re.compile(r"(?i)(?<![" + _B + r"])(?:bis|vom|von|am|ab|seit|im|in|per|ende|anfang|mitte|monat|des|der|den|dem|"
                    r"zum|zur|und|oder|für)\s*$")       # «… bis Ende Mai 2025» is a deadline, not an edition
_CODE_DATUM = re.compile(r"(?<![" + _B + r"\d_])[A-Za-z]{2,}(?:_[A-Za-z]{1,4}){0,3}_" + _MON + r"[-.]" + _JAHR + r"$")
_DATEI_DATUM = re.compile(r"(?:" + _JAHR + r"-" + _MON + r"-" + _TAG + "|" + _D_VOLL + r") ?[-–]? ?\S.{0,60}?"
                          r"\.(?:docx?|xlsx?|pdf)\b")                                    # «2025-10-02 - Gesuch X.docx»
# 3. a line that is nothing but a date (next to a page number, initials, an office after «;»)
_S_MARKE = r"(?:(?:Seite|S\.|Page) ?)?\d{1,3} ?(?:(?:von|/|\|) ?\d{0,3})?"
_BLOSS = re.compile(
    r"(?:(?:Seite|S\.|Page) ?\d{1,3} ?(?:(?:von|/|\|) ?\d{1,3})? )?"
    r"(?P<kern>(?:[A-ZÄÖÜ]{2,5}, )?(?P<d>" + _DATUM + r")(?:/[A-Za-z]{2,4})?(?: ?/ ?Formular \w+)?)(?: " + _S_MARKE + r")?")
_BLOSS_JAHR = re.compile(r"(?P<kern>" + _JAHR + r") \d{1,3} ?(?:von|/|\|) ?\d{1,3}")              # «2024 1 / 2»
_BLOSS_STELLE = re.compile(r"[^;\d]{5,70}; (?P<kern>" + _TAG + r"\. ?" + _D_MONAT + "|" + _D_VOLL + r")(?: \d{1,3})?")
_STICHTAG = re.compile(r"(?:31\. ?12|0?1\. ?0?1)\. ?" + _JAHR)


def _stand_seite(zeilen):
    """The edition mark of one page: (class, text) with class 1 key word,
    2 form code, 3 bare date — or None."""
    kandidaten, bloss = [], []
    for roh in zeilen:
        t = _eng(roh)
        if not t or len(t) > 200:
            continue
        m = _STAND_KLAR.search(t)
        if m:
            kandidaten.append((1, m.group(0)))
            continue
        if len(t) > 100:
            continue
        for m in _STAND_SW.finditer(t):
            vor, nach = t[:m.start()].strip(), t[m.end():].strip()
            if vor and not _VOR_OK.fullmatch(vor):
                continue                      # running text before the key word
            if len(nach) > 50 or re.match(r"[,;:)]|[a-zäöü]{2,}", nach):
                continue                      # the sentence goes on
            kandidaten.append((1, m.group(0)))
            break
        else:
            m = _BUND_CODE.search(t) or (_CODE_STRICH.fullmatch(t) if len(t) <= 30 else None) \
                or _DATEI_DATUM.match(t) or (_CODE_DATUM.search(t) if len(t) <= 80 else None)
            if m:
                kandidaten.append((2, m.group(0)))
                continue
            m = _CODE_ZEILE.fullmatch(t) if len(t) <= 85 else None
            if m and not _FRIST.search(t[:m.start("d")]):
                kandidaten.append((2, t if len(t) <= 60 else m.group("code") + " … " + m.group("d")))
                continue
            m = _FORM_LABEL.search(t)
            if m and len(t) <= 90 and len(t[:m.start()]) <= 40 \
                    and not re.search(r"(?<![" + _B + r"])[a-zäöü]{3,}", t[:m.start()]):
                ende = None
                for w in _FORM_WERT.finditer(t, m.end()):
                    if w.start() - m.end() > 45:
                        break
                    ende = w.end()
                if ende:
                    kandidaten.append((2, t[m.start():ende]))
                    continue
            m = _BLOSS_STELLE.fullmatch(t)
            if m:
                bloss.append(m.group("kern"))
            elif len(t) <= 45:
                m = _BLOSS.fullmatch(t) or _BLOSS_JAHR.fullmatch(t)
                if m and not (m.group("kern") == t and _STICHTAG.fullmatch(t)):
                    bloss.append(m.group("kern"))
    if kandidaten:
        return min(kandidaten, key=lambda k: k[0])      # min is stable: the first of the best class
    if bloss and len(set(bloss)) <= 2:                  # more different bare dates = a table of dates
        return (3, bloss[0])
    return None


_NUR_JAHR = re.compile(_JAHR)


def _jahr_seite(zeilen):
    """A year alone on its line, when it is the only such line of the page («2024»
    in the footer of a one-page form): the weakest edition mark."""
    jahre = [t for t in (_eng(roh) for roh in zeilen) if _NUR_JAHR.fullmatch(t)]
    return jahre[0] if len(jahre) == 1 else None


def _stand(seiten):
    seiten = [_nichtleer(zeilen) for zeilen in seiten]
    for zeilen in seiten:
        k = _stand_seite(zeilen)
        if k:
            text = k[1] if len(k[1]) <= 60 else k[1][:59] + "…"
            return {"vorhanden": True, "text": text}
    for zeilen in seiten:                               # no mark of the three classes on any page
        jahr = _jahr_seite(zeilen)
        if jahr:
            return {"vorhanden": True, "text": jahr}
    return {"vorhanden": False, "text": None}


# ---------------------------------------------------------------- Elemente: Seitenzahlen

_SZ_VOLL = re.compile(r"(?<![" + _B + r"])(?:Seite|Page|Pagina|Blatt) ?(\d{1,3}) ?(?:von|of|de|di|/|\|) ?(\d{1,3})(?!\d)")
_SZ_SEITE = re.compile(r"(?<![" + _B + r"])(?:Seite|Page|Blatt) ?(\d{1,3})")
_SZ_VERWEIS = re.compile(r"(?i)(?:auf|siehe|vgl\.?|s\.|der|die|und|oder|ab|bis|von|zur?|in|en|voir|[,+(])\s*$")
_SZ_BRUCH = re.compile(r"(?<![\d.,/|])([1-9]\d{0,2}) ?(?:/|\||von) ?([1-9]\d{0,2})(?![\d.,/|])")
_SZ_STRICH = re.compile(r"[-–—] ?([1-9]\d{0,2}) ?[-–—]")
_SZ_ZAHL = re.compile(r"\d{1,3}")
_SZ_FUSS = re.compile(r"(.{8,}?) (\d{1,3})")


def _seitenzahlen(seiten):
    n = len(seiten)
    if n <= 1:
        return {"vorhanden": None, "muster": None}
    alle = [[_eng(x) for x in _nichtleer(zeilen)] for zeilen in seiten]
    funde, halb = [], []                           # (class, page, text); halb: valid only with a full find
    for p, z in enumerate(alle, 1):
        nur_zahl = [t for t in z if _SZ_ZAHL.fullmatch(t)]
        for t in z:
            m = _SZ_VOLL.search(t)                                       # 1  «Seite 1 von 3», anywhere
            if m and int(m.group(1)) <= int(m.group(2)):
                funde.append((1, p, m.group(0)))
                continue
            m = _SZ_SEITE.fullmatch(t)                                   # 2  «Seite 2», alone or ending a line
            if not m:
                m = _SZ_SEITE.search(t)
                if m and (m.end() != len(t) or _SZ_VERWEIS.search(t[:m.start()])):
                    m = None
            if m and int(m.group(1)) == p:
                funde.append((2, p, m.group(0)))
                continue
            for m in _SZ_BRUCH.finditer(t):                              # 3  «2/3», «2 von 3»
                if int(m.group(1)) == p and int(m.group(2)) == n and (m.start() == 0 or m.end() == len(t)):
                    (funde if m.group(0) == t or p >= 2 else halb).append((3, p, m.group(0)))
                    break
            m = _SZ_STRICH.fullmatch(t)
            if m and int(m.group(1)) <= n:                               # 4  «- 2 -»
                funde.append((4, p, t))
            elif t == str(p) and len(nur_zahl) == 1 and p >= 2:          # 5  the number alone on its line
                funde.append((5, p, t))
            else:
                m = re.match(r"(\d{1,3}) (?=\S)", t)                     # 5  «1 Version 2024»
                if m and int(m.group(1)) == p and _STAND_SW.match(t, m.end()):
                    funde.append((5, p, m.group(1)))
                    continue
                m = _SZ_FUSS.fullmatch(t)                                # 6  running footer + number
                if m and p >= 2 and int(m.group(2)) == p:
                    kopf = m.group(1)
                    if any(kopf in a or kopf + " " + str(q) in a for q, a in enumerate(alle, 1) if q != p):
                        funde.append((6, p, m.group(2)))
    if any(k == 3 for k, _p, _t in funde):
        funde += halb
    if not funde:
        return {"vorhanden": False, "muster": None}
    return {"vorhanden": True, "muster": min(funde, key=lambda f: (f[0], f[1]))[2]}


def seitenzahl_schema(muster):
    """The notation of a page mark with its numbers replaced: «Seite n von N»,
    «n/N», «- n -», «n» — for comparing notations across Formulare."""
    if not muster:
        return None
    teile = iter(("n", "N"))
    return re.sub(r"\d+", lambda _m: next(teile, "N"), muster)


# ---------------------------------------------------------------- Elemente: Absender

# «Kanton Schaffhausen», «Kantons Schaffhausen»; a line break may stand between the two words, and the
# text extraction may have lost the last letter at the end of a line («Kanton Schaffhause»)
_KANTON = re.compile(r"(?<![" + _B + r"])" + _wort("Kanton") + r"(?P<gen>s?)\s*" + _wort("Schaffhause")
                     + r"(?:\s?n(?![" + _B + r"])|(?=[ \t]*(?:\n|$)))", re.I)
_KT_BINDEWORT = frozenset("des der und für von".split())
_KT_VORSPANN = re.compile(r"^[^:\n]{1,30}:\s*")          # «Kontaktadresse:», «zustellen an:»
# a line that breaks off in the middle of a sentence: it ends with a preposition, an article or a conjunction
_KT_OFFEN = re.compile(r"(?<![" + _B + r"])(?:im|in|beim|bei|vom|von|zum|zur|an|am|auf|aus|mit|für|des|dem|den|der|"
                       r"das|die|ein|eine|einem|einen|einer|eines|und|oder|sowie|ausserhalb|innerhalb)\s*$")


def _kanton_absender(text, m, rx=None):
    """Does this «Kanton(s) Schaffhausen» stand like a sender — alone, leading
    its line, or closing a line of names («Erziehungsdepartement des Kantons
    Schaffhausen», «zustellen an: Landwirtschaftsamt Kanton Schaffhausen») —
    and not inside a sentence («Wohnsitz im Kanton Schaffhausen seit»,
    «ausserhalb des Kantons Schaffhausen», «beim Obergericht des Kantons
    Schaffhausen, Frauengasse …»)? What stands before it must be names only:
    capitalised words and des / der / und / für / von, behind an optional short
    label that ends with a colon; the Dienststelle's own name counts as a
    name however the text extraction broke it. The line above belongs to it
    when nothing or nothing but «des» precedes the canton on its own line and
    the canton stands in the genitive or the line above breaks off in the
    middle of a sentence (it ends with a preposition, an article or a
    conjunction). The first word behind it must not carry a sentence on."""
    beginn = text.rfind("\n", 0, m.start()) + 1
    ende = text.find("\n", m.end())
    vor, nach = text[beginn:m.start()], text[m.end():len(text) if ende < 0 else ende]
    worte = _WORT.findall(vor)
    oben = text[text.rfind("\n", 0, beginn - 1) + 1:beginn - 1] if beginn > 0 else ""
    if oben and all(w.lower() in _KT_BINDEWORT for w in worte):
        # nothing before it on its line, or nothing but «des»: what it belongs to stands on the line above —
        # the head of a genitive («FEUERPOLIZEI DES» ⏎ «KANTONS SCHAFFHAUSEN»), or a sentence that runs on
        if m.group("gen") or worte or _KT_OFFEN.search(oben):
            vor = oben + " " + vor
    if rx is not None:
        vor = rx.sub(" ", vor)
    vor = _KT_VORSPANN.sub("", _eng(vor))
    if len(vor) > BLOCK_BREITE:
        return False
    for w in _WORT.findall(vor):
        if len(w) > 1 and w[0].islower() and w.lower() not in _KT_BINDEWORT:
            return False
    w = _WORT.search(nach)
    if w and len(w.group(0)) > 2 and w.group(0)[0].islower() and w.group(0).lower() not in _KT_BINDEWORT \
            and not re.search(r"[.,;:|/()]", nach[:w.start()]):
        return False
    return True


def _absender(seiten, dienststelle):
    # e-mail and web addresses are taken out first: «gesundheitsamt@sh.ch» does not name the office
    zeilen = _nichtleer(seiten[0]) if seiten else []
    for i in range(len(zeilen) - 1):              # the head of an address that goes on in the next line
        if _MAIL_FOLGT.match(zeilen[i + 1]) and _MAIL_BRUCH.search(zeilen[i].rstrip()[-40:]):
            zeilen[i] = _MAIL_REST.sub(" ", zeilen[i].rstrip())
    text = "\n".join(_ohne_adressen(z) for z in zeilen)
    rx = _name_rx(dienststelle) if dienststelle and dienststelle.strip() else None
    k = next((m for m in _KANTON.finditer(text) if _kanton_absender(text, m, rx)), None)
    dm = _nennt_stelle(rx, text) if rx else None
    funde = []                                    # [line start, line end, match start, match end]
    for m in (k, dm):
        if m:
            ende = text.find("\n", m.end())
            funde.append([text.rfind("\n", 0, m.start()) + 1, len(text) if ende < 0 else ende, m.start(), m.end()])
    funde.sort()
    if len(funde) == 2 and funde[1][0] < funde[0][1]:           # both on the same line(s): one quote
        funde = [[funde[0][0], max(funde[0][1], funde[1][1]),
                  min(funde[0][2], funde[1][2]), max(funde[0][3], funde[1][3])]]
    teile = []
    for beginn, ende, a, b in funde:
        zeile, a2, b2 = _zitat(text[beginn:ende], a - beginn, b - beginn)
        teile.append(_fenster(zeile, a2, b2, 100 if len(funde) == 1 else 60))
    return {"kanton": bool(k), "dienststelle": bool(dm) if rx else None,
            "text": (" " + UMBRUCH + " ").join(teile) if teile else None}


def elemente(seiten, dienststelle=None):
    """Edition mark, page numbers and sender of a document given as its pages
    (each a list of text lines). `dienststelle` is service.dienststelle or None."""
    seiten = [list(s or []) for s in (seiten or [])]
    return {"stand_angabe": _stand(seiten),
            "seitenzahlen": _seitenzahlen(seiten),
            "absender": _absender(seiten, dienststelle)}


# ---------------------------------------------------------------- self-test

def _selbsttest():
    """Assertions on built-in example lines (invented persons, public office numbers)."""
    n = [0]

    def gleich(ist, soll, was):
        n[0] += 1
        assert ist == soll, f"{was}: {ist!r} != {soll!r}"

    def tel(lines, **kw):
        return [(t["nummer"], t["e164"], t["format"], t["art"], t["erklaerung"]) for t in telefon(lines, **kw)]

    # --- Telefon: every notation of the corpus
    for zeile, nummer, e164, fmt in [
            ("Tel. 052 632 78 21", "052 632 78 21", "+41526327821", "national"),
            ("T +41 52 632 74 67, gesundheitsamt.ga@sh.ch", "+41 52 632 74 67", "+41526327467", "international"),
            ("Tel. +4152 632 71 11", "+4152 632 71 11", "+41526327111", "international"),
            ("Telefon: (052) 632 74 65", "(052) 632 74 65", "+41526327465", "national"),
            ("Telefon +41 (0)52 632 74 67", "+41 (0)52 632 74 67", "+41526327467", "international"),
            ("Tel. +41 (52) 632 74 67", "+41 (52) 632 74 67", "+41526327467", "international"),
            ("Tel.: + 41 (0) 58 618 38 38", "+ 41 (0) 58 618 38 38", "+41586183838", "international"),
            ("Tel: 058 345 6859", "058 345 6859", "+41583456859", "national"),
            ("Tel. 052 / 632 74 66", "052 / 632 74 66", "+41526327466", "national"),
            ("Telefon 0041 52 632 78 21", "0041 52 632 78 21", "+41526327821", "international"),
            ("Gratisnummer 0800 55 42 10", "0800 55 42 10", "+41800554210", "national"),
            ("Hotline 0848 800 900", "0848 800 900", "+41848800900", "national"),
            ("Natel 079 123 45 67", "079 123 45 67", "+41791234567", "national"),
            ("Tel. 0526327821", "0526327821", "+41526327821", "national"),
            ("Tel. 052\u00a0632\u00a078\u00a021", "052 632 78 21", "+41526327821", "national"),
            ("Tel. +49 7731 123 45 67", "+49 7731 123 45 67", "+4977311234567", "andere")]:
        gleich(tel([zeile]), [(nummer, e164, fmt, "telefon", "bezeichnung")], zeile)
    # --- Telefon: what must not match
    for zeile in ["IBAN CH93 0076 2011 6238 5295 7", "CH9300762011623852957", "LI21 0881 0000 2324 013A A",
                  "AHV-Nr. 756.1234.5678.97", "Referenz 21 00000 00003 13947 14300 09017", "Konto 01-039139-1",
                  "01.01.2024 – 31.12.2024", "8200 Schaffhausen", "CHF 1'052.50", "0716052 – 001 – 10 - 2012",
                  "Form 0716052001", "0716052 001", "Kunden-Nr. 044 123 45 67", "052 632 78 21 1/2", "+49 7731 123 45 67",
                  "Monate Abzug 235 –/+ 3213211 3213211", "Telefon: ______________", "Tel. P: ........ G: ........",
                  "Telefon / Natel:", "Tel. 052 632 78", "Notruf 144"]:
        gleich(tel([zeile]), [], zeile)
    # --- Telefon: Art, Kette, Kurzform, Umbruch
    gleich(tel(["Tel. 052 632 73 29  /  Fax. Nr. 052 632 75 38"]),
           [("052 632 73 29", "+41526327329", "national", "telefon", "bezeichnung"),
            ("052 632 75 38", "+41526327538", "national", "fax", "bezeichnung")], "Tel/Fax")
    gleich([t[3] for t in tel(["T +41 (0) 58 345 68 75, F +41 (0) 58 345 68 41"])], ["telefon", "fax"], "T/F")
    gleich([t[3] for t in tel(["oder zu faxen: 052 / 632 71 04"])], ["fax"], "zu faxen")
    gleich([t[1] for t in tel(["Telefon +41 (0)52 632 71 01/02"])], ["+41526327101", "+41526327102"], "01/02")
    gleich([(t[1], t[4]) for t in tel(["Amt für Grundstückschätzung, per Tel. 052 632 75 28 (Schaffhausen) bzw.",
                                       "052 632 75 27 (übrige Gemeinden)"])],
           [("+41526327528", "erklaert"), ("+41526327527", "erklaert")], "Kette über den Zeilenumbruch")
    gleich(tel(["bei der Schlichtungsstelle für Mietsachen, Vordergasse 54,", "8200 Schaffhausen (Tel. 0",
                " 52 632 75 18), als missbräuchlich"]),
           [("052 632 75 18", "+41526327518", "national", "telefon", "erklaert")], "umbrochene Nummer")
    gleich(tel(["Tel. 052 632 68 88 8200 Schaffhausen"])[0][1], "+41526326888", "Nummer vor der Postleitzahl")
    gleich([t[1] for t in tel(["Tel. 052 632 75 28 052 632 75 27"])], ["+41526327528", "+41526327527"], "zwei Nummern nebeneinander")
    gleich(tel(["Anrede: Frau Herr", "Tel. 052 632 78 21"])[0][4], "bezeichnung", "Anrede ist keine Person")
    gleich(tel(["Frau Muster", "Tel. 052 632 78 21"])[0][4], "erklaert", "Frau Muster")
    # --- Telefon: Erklärung
    brief = ["Kanton Schaffhausen", "Gesundheitsamt", "Mühlentalstrasse 105", "CH-8200 Schaffhausen"]
    gleich(tel(brief + ["052 632 74 67"])[0][4], "ohne", "nackte Nummer unter der Adresse")
    gleich(tel(brief + ["Tel. 052 632 74 67"])[0][4], "erklaert", "Amt im Absenderblock, über der Adresse")
    gleich(tel(brief + ["www.sh.ch", "E-Mail: amt@sh.ch", "Telefon +41 52 632 74 67", "Fax +41 52 632 74 68"])[1][4],
           "erklaert", "Absenderblock mit Kontaktzeilen")
    gleich(tel(brief[:2] + ["Tel. 052 632 74 67"])[0][4], "erklaert", "Amt eine Zeile höher")
    gleich(tel(["Kanton Schaffhausen"] + brief[2:] + ["Tel. 052 632 74 67"])[0][4], "bezeichnung", "Block ohne Amt")
    gleich(tel(["Telefon +41 52 632 71 01", "Fax +41 52 632 71 04", "Kanton Schaffhausen", "Veterinäramt",
                "Mühlentalstrasse 188", "CH-8200 Schaffhausen"])[0][4], "erklaert", "Absenderblock unter den Nummern")
    gleich(tel(["Tel. 052 632 61 11", "www.svash.ch", "Vollmacht / Ermächtigung AHV-Ausgleichskasse",
                "(bitte Zutreffendes ankreuzen)"])[0][4], "bezeichnung", "Text unter der Nummer ist kein Absenderblock")
    # a letterhead in two pieces: name and address in one place of the page text, the contact lines at its
    # start or end — read together only where the caller says where the pages end
    kopf = ["Stand: April 2023", "Kanton Schaffhausen", "Veterinäramt", "Mühlentalstrasse 188", "CH-8200 Schaffhausen"]
    rumpf = ["Antrag für ein Validierungsabzeichen", "Name Vorname", "Adresse PLZ Ort"]
    kontakt = ["Telefon +41 (0)52 632 71 01", "amt@sh.ch", "www.veterinaeramt.sh.ch"]
    gleich(tel(kopf + rumpf + kontakt, seitenweise=True)[0][4], "erklaert", "Kontaktblock am Ende der Seite, Briefkopf oben")
    gleich(tel(kontakt[:2] + rumpf + kopf[1:], seitenweise=True)[0][4], "erklaert", "Kontaktblock am Anfang, Briefkopf unten")
    gleich(tel(kopf + rumpf + kontakt)[0][4], "bezeichnung", "ohne Seitenangabe gilt die Regel nicht")
    gleich(tel(kopf + [SEITENWECHSEL] + rumpf + kontakt, seitenweise=True)[0][4], "bezeichnung",
           "ein Briefkopf auf einer anderen Seite erklärt nicht")
    gleich(tel(kopf + rumpf + kontakt + ["Ort, Datum"] + rumpf, seitenweise=True)[0][4], "bezeichnung",
           "ein Kontaktblock mitten im Text der Seite steht nicht abgesetzt")
    gleich(tel(["Kanton Schaffhausen"] + kopf[3:] + rumpf + kontakt, seitenweise=True)[0][4], "bezeichnung",
           "ein Briefkopf, der keine Stelle nennt, erklärt nicht")
    gleich(tel(kopf + rumpf + ["Oberstadt 9", "8200 Schaffhausen", "Tel. 052 632 61 11"],
               seitenweise=True)[0][4], "bezeichnung", "eine Nummer unter einer eigenen Adresse ohne Namen bleibt, wie sie ist")
    gleich([t[4] for t in tel(kopf + ["Telefon 052 632 71 02"] + rumpf + ["Tel. 052 632 61 11", "info@beispiel.ch"],
                              seitenweise=True)], ["erklaert", "bezeichnung"],
           "ein Briefkopf mit eigener Nummer erklärt nur diese")
    gleich(tel(["Kontaktperson bei Rückfragen", "Name / Vorname", "E-Mail", "Telefon", "Oberstadt 9", "8200 Schaffhausen",
                "Tel. 052 632 61 11"])[0][4], "bezeichnung", "Feldbezeichnungen über einer Adresse ohne Namen")
    lang = "Bitte bis spätestens 30. Juni an das Gesundheitsamt zurücksenden, sonst kann das Gesuch nicht behandelt werden."
    gleich(tel([lang, "Unterschrift", "Ort, Datum", "Oberstadt 9", "8200 Schaffhausen", "Tel. 052 632 61 11"])[0][4],
           "bezeichnung", "Fliesstext über dem Block zählt nicht")
    fuss = ["Oberstadt 9", "8200 Schaffhausen", "Tel. 052 632 61 11"]
    gleich(tel(["Ausgleichskasse"] + fuss + ["Unterschrift"] + fuss)[0][4], "bezeichnung",
           "ein wiederholter Block ist nur benannt, wenn er es jedes Mal ist")
    gleich(tel(["Ausgleichskasse"] + fuss + ["Ausgleichskasse"] + fuss)[0][4], "erklaert", "wiederholter Block mit Namen")
    gleich(tel(["Ernst Müller-Strasse 2", "CH-8207 Schaffhausen", "Tel. direkt: 052 632 68 81"])[0][4],
           "bezeichnung", "Strassenname ist keine Person")
    gleich(tel(["Hans Muster", "Fachperson Neobiota", "Telefon: 052 632 69 28"])[0][4], "erklaert", "Person")
    gleich(tel(["Tel. 052 632 73 29 / E-Mail: hans.muster@sh.ch"])[0][4], "bezeichnung", "E-Mail erklärt nicht")
    gleich(tel(["Für Fragen steht Ihnen die Jagdverwaltung, Tel. 052 / 632 74 66, zur Verfügung."])[0][4],
           "erklaert", "Zweck und Stelle in der Zeile")
    gleich(tel(["Bei Fragen: Landwirtschaftsamt des Kantons Schaffhausen, 052 632 66 67"])[0][4],
           "erklaert", "Zweck vor der Nummer, ohne Bezeichnung")
    gleich(tel(["SECO | Direktion für Arbeit | Arbeitsbedingungen | 058 463 89 14"])[0][4], "erklaert",
           "Stelle vor der Nummer, ohne Bezeichnung")
    gleich(tel(["Mühlentalstrasse 105, 8200 Schaffhausen, 052 632 74 67"])[0][4], "ohne", "Adresszeile ohne Stelle")
    gleich(tel(["Bei Fragen wenden Sie sich an:", "Lara Beispiel (lara.beispiel@sh.ch; 052 632 75 22) oder",
                "Hans Muster (052 632 7907)"]), [("052 632 75 22", "+41526327522", "national", "telefon", "erklaert"),
                                                  ("052 632 7907", "+41526327907", "national", "telefon", "erklaert")],
           "Zweckzeile mit Doppelpunkt darüber; Person vor der Nummer")
    gleich(tel(["Auskunft erteilt: amt@sh.ch", "052 632 76 37"])[0][4], "erklaert", "Zweckzeile über einer Nummer allein")
    gleich(tel(["amt@sh.ch", "052 632 76 37"])[0][4], "ohne", "Adresse über einer Nummer allein")
    gleich(tel(["Gesundheitsamt", "052 632 76 37"])[0][4], "ohne", "nackte Nummer unter dem Amt bleibt ohne")
    gleich(tel(["Zuständiger Geologe: Dr. von Moos AG, Dorfstr. 40, 8214 Gächlin-", "gen, 052 681 43 27"])[0][4],
           "erklaert", "der Satz kommt aus der Zeile darüber")
    gleich(tel(["per Post (Veterinäramt, 8200 Schaffhausen) oder per Fax: (052 632 71 04) oder per Mail"])[0][3:5],
           ("fax", "erklaert"), "Bezeichnung vor der Klammer")
    gleich(tel(["Sonderbewilligungen", "Tel. direkt:", "052 632 68 87"])[0][4], "erklaert", "Einheit über der Bezeichnung")
    gleich(tel(["Fax", ". 052 632 71 04 senden."])[0][3], "fax", "Fax eine Zeile höher")
    gleich(tel(["Führerwesen", "Tel. direkt: 052 632 68 82"])[0][4], "erklaert", "Einheit ohne Amtswort")
    gleich(telefon(["Führerwesen", "Tel. direkt: 052 632 68 82"])[0]["kontext"], "Führerwesen ⏎ Tel. direkt: 052 632 68 82",
           "die Einheit steht im Kontext")
    gleich(tel(["Mofa, Kontrollschilder, Schifffahrt", "Tel. direkt: 052 632 68 84"])[0][4], "erklaert", "Einheit, mehrteilig")
    gleich(tel(["Aufsicht Sonderschulung und Therapien", "Herrenacker 3 8200 Schaffhausen Tel. 052 632 75 06"])[0][4],
           "erklaert", "Einheit über der Adresszeile mit Nummer")
    for zeile in ["Unterschrift, Stempel", "Ort, Datum", "Bemerkungen", "Name Vorname", "negativ", "Nein:", "Seite 2"]:
        gleich(tel([zeile, "Tel. 052 632 68 82"])[0][4], "bezeichnung", "keine Einheit: " + zeile)
    gleich(tel(["Tel.: +41 52 632 XX (gem. Zuständigkeitsliste)", "Fax: +41 52 632 77 43"])[0][3:5],
           ("fax", "bezeichnung"), "Zuständigkeitsliste erklärt nichts")
    # --- Telefon: beste Fundstelle, Kontext
    t = telefon(brief + ["052 632 74 67", "", "Auskunft: Gesundheitsamt, Tel. 052 632 74 67", "Ort, Datum",
                         "Unterschrift", "Fax 052 632 74 67"])
    gleich([(x["art"], x["erklaerung"]) for x in t], [("telefon", "erklaert"), ("fax", "bezeichnung")], "beste Fundstelle")
    gleich(t[0]["kontext"], "Auskunft: Gesundheitsamt, Tel. 052 632 74 67", "Kontext der besten Fundstelle")
    gleich(telefon(["8200 Schaffhausen", "", "052 632 78 21"])[0]["kontext"], "8200 Schaffhausen ⏎ 052 632 78 21", "Zeile darüber")
    gleich(telefon(["Zuständiger Geologe: Dr. von Moos AG, Dorfstr. 40, 8214 Gächlin-", "gen, 052 681 43 27"])[0]["kontext"],
           "Zuständiger Geologe: Dr. von Moos AG, Dorfstr. 40, 8214 Gächlin- ⏎ gen, 052 681 43 27", "Satz über zwei Zeilen")
    gleich(telefon(["Kontakt: hans.mus", "ter@sh.ch oder 052 632 78 21"])[0]["kontext"],
           "Kontakt: … ⏎ …@sh.ch oder 052 632 78 21", "kein Bruchstück einer Adresse im Kontext")
    gleich(telefon(["Tel. 052 632 78 21 oder hans.mus", "ter@sh.ch"])[0]["kontext"], "Tel. 052 632 78 21 oder …",
           "kein Bruchstück einer Adresse am Zeilenende")
    gleich(telefon(["Tel. 052 632 73 29 /   E-Mail: hans.muster@sh.ch"])[0]["kontext"],
           "Tel. 052 632 73 29 / E-Mail: …@sh.ch", "E-Mail-Adresse im Kontext")
    lang = ("Kantonale Feuerpolizei    Ringkengässchen 18    8200 Schaffhausen     Tel. +4152 632 71 11"
            "    Fax +4152 632 78 31   www.feuerpolizei.sh.ch")
    for x in telefon([lang]):
        gleich((len(x["kontext"]) <= 100, x["nummer"] in x["kontext"], x["erklaerung"]), (True, True, "erklaert"), "lange Zeile")
    gleich(schreibweise("+41 (0)52 632 74 67"), "+99 (9)99 999 99 99", "schreibweise")
    for titel, soll in [("Muster  26.4.01", True), ("Hans Muster", True), ("Brief Hans Muster.doc", True),
                        ("Gesuch um Bewilligung", False), ("Office 2010", False), ("Herr", False), ("Herisau, 12", False),
                        ("Dokument", False), ("Kanton Schaffhausen", False), ("Stand 26.4.2001", True), ("", False),
                        ("Microsoft Word - Antragsformular 2025.doc", False), ("Ernst Müller-Strasse 2", False)]:
        gleich(person_im_titel(titel), soll, "person_im_titel(%r)" % titel)
    gleich([(ist_neutral(f), ist_neutral(f, flaeche=True), ist_blass(f)) for f in ("#000000", "#dbe5f1", "#ff0000", "#eeece1")],
           [(True, True, False), (True, False, True), (False, False, False), (True, False, True)], "grau, blass, farbig")
    gleich(telefon(["\uf0d8 Auskunft erteilt das Amt unter Telefon 052 632 74 66"])[0]["kontext"],
           "Auskunft erteilt das Amt unter Telefon 052 632 74 66", "kein Zeichen einer Symbolschrift im Kontext")
    for familie, schrift in (("Frutiger Condensed", "Frutiger"), ("Arial Narrow", "Arial"), ("Times New Roman", "Times"),
                             ("Times", "Times"), ("Arial", "Arial"), ("Helvetica Neue", "Helvetica Neue"), (None, None)):
        gleich(schriftgruppe(familie), schrift, "schriftgruppe(%r)" % (familie,))

    # --- E-Mail
    for adresse, art in [("hans.muster@sh.ch", "persoenlich"), ("Hans.Muster@ktsh.ch", "persoenlich"),
                         ("h.muster@sh.ch", "persoenlich"), ("hans-peter.muster@sh.ch", "persoenlich"),
                         ("jürg.muster@sh.ch", "persoenlich"), ("hans.p.muster@sh.ch", "persoenlich"),
                         ("info@sh.ch", "funktional"), ("gesundheitsamt.ga@sh.ch", "funktional"),
                         ("stva.fawe@sh.ch", "funktional"), ("sekretariat.stva@sh.ch", "funktional"),
                         ("ab.sekretariat@seco.admin.ch", "funktional"), ("la-sh@sh.ch", "funktional"),
                         ("veterinäramt@ktsh.ch", "funktional"), ("hans.sekretariat@sh.ch", "funktional"),
                         ("e.government@sh.ch", "funktional"), ("hmuster@sh.ch", "funktional")]:
        gleich(emails(["E-Mail " + adresse])[0]["art"], art, adresse)
    gleich(emails(["E-Mail: stva.fawe@s h.ch", "www.sh.ch E-Mail: stva.fuwe@sh. ch", "→ msd.bestellungen@m", "sd.com"]),
           [{"art": "funktional", "domain": "sh.ch"}, {"art": "funktional", "domain": "sh.ch"},
            {"art": "funktional", "domain": "msd.com"}], "beschädigte Domain")
    gleich(emails(["info@sh.ch", "Info@SH.ch", "per Mail an fachstelle@fsgb-sh.ch.", "Email  @", "Email: ........ @ ........"]),
           [{"art": "funktional", "domain": "sh.ch"}, {"art": "funktional", "domain": "fsgb-sh.ch"}], "einmal je Adresse")
    gleich(emails(["Kontakt: hans.", "muster@sh.ch"]), [{"art": "persoenlich", "domain": "sh.ch"}], "umbrochene Adresse")
    gleich(emails(["Kontakt: hans.mus", "ter@sh.ch"]), [{"art": "persoenlich", "domain": "sh.ch"}], "im Namen umbrochen")
    gleich(emails(["www.gewaesser.sh.ch", "info@sh.ch"]), [{"art": "funktional", "domain": "sh.ch"}],
           "eine Internetadresse darüber ist kein Bruchstück")
    gleich(emails(["Xyla Beispiel (xyla.beispiel@sh.ch)"]), [{"art": "persoenlich", "domain": "sh.ch"}],
           "der Name steht daneben")
    gleich(emails(["xyla.beispiel@sh.ch"]), [{"art": "funktional", "domain": "sh.ch"}], "unbekannter Vorname ohne Namen")
    gleich(emails(["Team Technik: stva.technik@sh.ch"]), [{"art": "funktional", "domain": "sh.ch"}], "Funktion bleibt")
    gleich(emails(["xyla.beispiel@sh.ch", "Xyla Beispiel, xyla.beispiel@sh.ch"]), [{"art": "persoenlich", "domain": "sh.ch"}],
           "eine Fundstelle beim Namen genügt")
    gleich(sorted(emails(["a@b.ch"])[0]), ["art", "domain"], "nur Art und Domain")

    # --- Stand-Angabe
    def stand(*zeilen):
        return elemente([list(zeilen)])["stand_angabe"]["text"]

    for zeile, text in [
            ("Version Januar 2026", "Version Januar 2026"), ("Stand: 1. Mai 2025", "Stand: 1. Mai 2025"),
            ("bestellung-kontrollschilder.doc Seite 1 von 1 Version: 2022.11.14", "Version: 2022.11.14"),
            ("File: nachprüfung-ausland-23.docx Stand: 2023-06-13 1/1", "Stand: 2023-06-13"),
            ("1 Stand 03.02.2025/HO", "Stand 03.02.2025"), ("www.sh.ch Version 2024", "Version 2024"),
            ("FO 4.3.04.docx / Version 0.2 / 23.03.2016 / Hans Muster / Seite 1 von 1", "Version 0.2 / 23.03.2016"),
            ("Formular 18 R / gültig ab 1.1.2019", "gültig ab 1.1.2019"), ("Ausgabe 2025/2", "Ausgabe 2025/2"),
            ("Version juin 2019", "Version juin 2019"), ("Neuausgabe: 01.07.2024", "Neuausgabe: 01.07.2024"),
            ("722FO107_P / Freigabedatum 15.05.2023 1/1", "Freigabedatum 15.05.2023"),
            ("4.12.2024 Ersetzt Dokument vom 01.09.2022 Seite 1 von 2", "4.12.2024 Ersetzt Dokument vom 01.09.2022"),
            ("Formular wurde zuletzt angepasst am: 1. Oktober 2008; Dokumentname: X", "zuletzt angepasst am: 1. Oktober 2008"),
            ("21 | 1 Form. bei02 02.23", "Form. bei02 02.23"), ("Form. el06 05.20Seite 3 | 3", "Form. el06 05.20"),
            ("Formular 112/25 (03.25)", "Formular 112/25 (03.25)"), ("716.052 d  10.2012", "716.052 d 10.2012"),
            ("Form. 56.99 d V 03 / 05.09  siehe Rückseite", "Form. 56.99 d V 03 / 05.09"),
            ("10023d - 01-2024", "10023d - 01-2024"), ("März 2021", "März 2021"), ("05/2023", "05/2023"),
            ("11.02.2022", "11.02.2022"), ("ZSW, 12.2022", "ZSW, 12.2022"), ("Juli 2017/MG", "Juli 2017/MG"),
            ("31.03.2025 Seite 1 / 2", "31.03.2025"), ("Seite 1 von 8 2022-01", "2022-01"), ("2024 1 / 2", "2024"),
            ("Volkswirtschaftsdepartement des Kantons Schaffhausen; 1. Mai 2016 2", "1. Mai 2016"),
            ("Gre-1 a Ansässigkeitsbescheinigung für Grenzgänger Juli 2023",
             "Gre-1 a Ansässigkeitsbescheinigung für Grenzgänger Juli 2023"),
            ("Gre-3 a Bescheinigung des Arbeitgebers über die Nichtrückkehr Juli 2023", "Gre-3 a … Juli 2023"),
            ("AG an AN gemäss Zusatzabkommen FR_de_01-2025", "FR_de_01-2025"),
            ("2025-10-02 - Gesuch Händlerschild Formular.docx Seite 1 / 2", "2025-10-02 - Gesuch Händlerschild Formular.docx"),
            ("info@seco.admin.ch | Erscheinungsjahr: 2019", "Erscheinungsjahr: 2019"),
            ("ausgedruckt am: 02.03.2018 Seite 1 von 2 Datei GD.xls", "ausgedruckt am: 02.03.2018")]:
        gleich(stand(zeile), text, zeile)
    for zeile in ["Ort, Datum: ______________", "Datum: 16. März bis 28. März 2026", "am 31.12.2021", "31.12.2021",
                  "Ein Anspruch besteht bei einem Verdienst ab CHF 630.- pro Monat (Stand: 01.01.2025).",
                  "vom 20. März 2001 (Stand am 1. Juli 2015)", "Zivilgesetzbuches (OR) SR 220, Stand 1.1.2022",
                  "EFTA; gültig ab 1. Juni 2007.", "2. Stand der Liquidation (ein Feld ankreuzen)", "gültig bis 31.12.2026",
                  "Schaffhausen, 2. März 2018", "Formular 18.21, S. 2", "Formular DA-2 605.040.04d (Steuerperiode 2021)  1/2",
                  "Steuerperiode 2024", "Ziffer 180: Veteranenfahrzeug: Km-Stand: ____________ Datum: ____________",
                  "in der Fassung vom 12. Dezember 2014 oder eine gleichwertige Ausbildung",
                  "A1 Anmeldung bis Ende Mai 2025", "Muster Engineering 2009", "Messprotokoll_SH-2019-1.doc Seite 1",
                  "Pflanzenschutzgeräteprüfung Obst-/Weinbau 2026", "ausgedruckt am: ____________"]:
        gleich(stand(zeile), None, zeile)
    gleich(stand("Januar 2025", "Februar 2025", "März 2025"), None, "Tabelle von Daten")
    gleich(stand("März 2021", "Form. bei02 02.23", "Version 2024"), "Version 2024", "Stichwort vor Code vor Datum")
    gleich(elemente([["Ort, Datum"], ["Stand: Juni 2024"]])["stand_angabe"], {"vorhanden": True, "text": "Stand: Juni 2024"},
           "Stand auf Seite 2")
    gleich(elemente([["Ort, Datum"]])["stand_angabe"], {"vorhanden": False, "text": None}, "kein Stand")
    gleich(stand("www.gewaesser.sh.ch", "2024", "GESUCH"), "2024", "eine Jahreszahl allein auf ihrer Zeile")
    gleich(stand("2023", "2024", "2025"), None, "mehrere Jahreszahlen sind eine Tabelle")
    gleich(elemente([["2024", "Titel"], ["Stand: Juni 2024"]])["stand_angabe"]["text"], "Stand: Juni 2024",
           "ein Vermerk auf einer späteren Seite geht der blossen Jahreszahl vor")

    # --- Seitenzahlen
    def seiten(*s):
        return elemente([list(x) for x in s])["seitenzahlen"]["muster"]

    gleich(elemente([["Seite 1 von 1"]])["seitenzahlen"], {"vorhanden": None, "muster": None}, "einseitig")
    gleich(elemente([["Text"], ["Text"]])["seitenzahlen"], {"vorhanden": False, "muster": None}, "keine Seitenzahl")
    gleich(seiten(["x.doc Seite 1 von 2 Version: 2022.11.02"], ["Seite 2 von 2"]), "Seite 1 von 2", "Seite n von N")
    gleich(seiten(["Seite 1 | 3"], ["Seite 2 | 3"], ["Seite 3 | 3"]), "Seite 1 | 3", "Seite n | N")
    gleich(seiten(["Titel"], ["Steuererklärung Seite 2"], ["siehe Seite 2"]), "Seite 2", "Seite n")
    gleich(seiten(["siehe Seite 1"], ["auf Seite 2 stehende Adresse"]), None, "Verweis ist keine Seitenzahl")
    gleich(seiten(["1/2 Lt Fl."], ["Text"]), None, "Bruch nur auf Seite 1")
    gleich(seiten(["Formular DA-2 1/2"], ["2/2 Formular DA-2"]), "1/2", "Bruch am Zeilenrand")
    gleich(seiten(["Text"], ["x.docx 2/2"]), "2/2", "Bruch am Zeilenrand, nur Seite 2")
    gleich(seiten(["1 / 2"], ["Text"]), "1 / 2", "Bruch allein auf der Zeile")
    gleich(seiten(["Text"], ["- 2 -"]), "- 2 -", "Strichform")
    gleich(seiten(["Text"], ["2", "Text"], ["3"]), "2", "blosse Zahl")
    gleich(seiten(["1", "Text"], ["Text"]), None, "blosse 1 auf Seite 1")
    gleich(seiten(["Text"], ["1.", "2.", "3."]), None, "Aufzählung")
    gleich(seiten(["Text"], ["1", "2", "3"]), None, "mehrere Zahlen auf der Seite")
    gleich(seiten(["1 Version 2024"], ["Text"]), "1", "Zahl vor der Stand-Angabe")
    gleich(seiten(["Handelsregisteramt des Kantons Schaffhausen"], ["Handelsregisteramt des Kantons Schaffhausen 2"]),
           "2", "Fusszeile mit Zahl")
    gleich(seitenzahl_schema("Seite 1 von 3"), "Seite n von N", "Schema")
    gleich(seitenzahl_schema("2"), "n", "Schema einer Zahl")

    # --- Absender
    def absender(zeilen, dienst):
        return elemente([zeilen], dienst)["absender"]

    gleich(absender(["Kanton Schaffhausen", "Veterinäramt", "Mühlentalstrasse 188"], "Veterinäramt"),
           {"kanton": True, "dienststelle": True, "text": "Kanton Schaffhausen ⏎ Veterinäramt"}, "Briefkopf")
    gleich(absender(["zustellen an: Landwirtschaftsamt des Kantons Schaffhausen"], "Landwirtschaftsamt"),
           {"kanton": True, "dienststelle": True, "text": "zustellen an: Landwirtschaftsamt des Kantons Schaffhausen"},
           "eine Zeile")
    gleich(absender(["FEUERPOLIZEI DES", "KANTONS SCHAFFHAUSEN"], "Kantonale Feuerpolizei"),
           {"kanton": True, "dienststelle": True, "text": "FEUERPOLIZEI DES ⏎ KANTONS SCHAFFHAUSEN"}, "Grossbuchstaben")
    gleich(absender(["Kanton", "Schaffh", "ausen", "Tiefbauamt, Abteilung Gewässer"], "Tiefbau Schaffhausen"),
           {"kanton": True, "dienststelle": False, "text": "Kanton Schaffh ausen"}, "anderer Name der Stelle")
    gleich(absender(["Sicherheitspolizei", "Kantonsgericht Schaffhausen"], "Polizei"),
           {"kanton": False, "dienststelle": False, "text": None}, "nur ganze Wörter")
    # the canton counts where it stands like a sender, not inside a sentence
    for zeilen, soll in [
            (["Kanton Schaffhausen EN-101a-SH"], True), (["Gesundheitsamt Kanton Schaffhausen"], True),
            (["Erziehungsdepartement des Kantons Schaffhausen", "Dienststelle Familie und Jugend"], True),
            (["Kindes- und Erwachsenenschutzbehörde", "des Kantons Schaffhausen"], True),
            (["Kontaktadresse: Strassenver kehrs- und Schifffahrtsamt", "des Kantons Schaffhausen"], True),
            (["Bitte Rückseite beachten", "Kanton Schaffhausen", "Strassenverkehrs- und Schifffahrtsamt"], True),
            (["Stand: April 2023", "Kanton Schaffhause", "Veterinäramt"], True),
            (["Zivilrechtlicher Wohnsitz im Kanton Schaffhausen seit"], False),
            (["Sicherheitsunternehmen mit Sitz oder Niederlassung ausserhalb", "des Kantons Schaffhausen"], False),
            (["Zweigniederlassung eines Sicherheitsunternehmens im Kanton Schaffhausen"], False),
            (["Die Beschwerde kann innert 20 Tagen beim Obergericht des Kantons Schaffhausen, Frauengasse 17,"], False),
            (["für den Schulbesuch an der Kantonsschule des Kantons Schaffhausen"], False),
            (["bis spätestens 15. Januar an das Gesundheitsamt des", "Kantons Schaffhausen senden: Mühlentalstrasse 105"], False),
            (["Tierhaltungen im", "Kanton Schaffhausen können durch das Amt kontrolliert werden."], False),
            (["Wohnsitz im Kanton Schaffhausen seit", "Kanton Schaffhausen", "Veterinäramt"], True)]:
        gleich(absender(zeilen, "Strassenverkehrs- und Schifffahrtsamt")["kanton"], soll, "Kanton als Absender: %r" % zeilen)
    gleich(absender(["Wohnsitz im Kanton Schaffhausen seit", "Kanton Schaffhausen", "Veterinäramt"], "Veterinäramt")["text"],
           "Kanton Schaffhausen ⏎ Veterinäramt", "belegt ist die Zeile, die wie ein Absender steht")
    gleich(absender(["Telefon 052 632 67 56", "gesundheitsamt@sh.ch"], "Gesundheitsamt")["dienststelle"], False,
           "E-Mail-Adresse nennt die Stelle nicht")
    gleich(absender(["Formular des Gesundheitsamtes"], "Gesundheitsamt")["dienststelle"], True, "Genitiv")
    gleich(absender(["Kanton Schaffhausen"], None)["dienststelle"], None, "Dienststelle unbekannt")
    gleich(absender(["Kanton Schaffhausen, Veterinäramt, hans.mus", "ter@sh.ch"], "Veterinäramt")["text"],
           "Kanton Schaffhausen, Veterinäramt,", "kein Bruchstück einer Adresse im Absender")
    gleich(elemente([], "Veterinäramt"),
           {"stand_angabe": {"vorhanden": False, "text": None}, "seitenzahlen": {"vorhanden": None, "muster": None},
            "absender": {"kanton": False, "dienststelle": False, "text": None}}, "ohne Text")
    gleich((telefon([]), emails([None, ""]), telefon(["", None])), ([], [], []), "leere Eingabe")
    return n[0]


if __name__ == "__main__":
    print(f"gestaltung_text: {_selbsttest()} checks passed")
