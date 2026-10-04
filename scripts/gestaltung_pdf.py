#!/usr/bin/env python3
"""PDF measurement of the «Gestaltung»: how a PDF Formular looks and is
presented — fonts, sizes, colours, accessibility facts, contact and edition
marks. Facts only: what cannot be measured is null and explained in
`hinweise`; nothing here is a verdict or a comparison across Formulare.

    messen(path, dienststelle=None, formular=None) -> dict     the profil (messart 'pdf' or 'pdf_bild')

    /usr/local/bin/python3 scripts/gestaltung_pdf.py                 # self-test
    /usr/local/bin/python3 scripts/gestaltung_pdf.py <file.pdf> …    # print the profil(s) as JSON

Needs pypdf (imported inside messen(), so the helpers can be imported without
it): schriftfamilie(), schriftklasse(), farbfamilie(),
ist_neutral(), farbwahl(), titel_art(), seitenformat(), zaehlbar(), knapp_hinweise() and the
thresholds (CLUSTER, MIN_…, TINTE) are the one definition of these notions;
gestaltung_office.py imports them, so their names are part of this module's
interface. schriftgruppe() is defined in gestaltung_text.py (the comparison
layer needs it under a Python without pypdf) and passed on from here.
Nothing in the build chain may import this module. Measured with
pypdf 6.13: the handling of Form XObjects leans on how that version calls its
visitors, and the self-test notices when this changes. The text detectors
(Telefon, E-Mail, Stand-Angabe, Seitenzahlen, Absender) live in
gestaltung_text.py; this module hands them the lines of pypdf's plain text
extraction, page by page.

How it measures
---------------
One pass per page through pypdf's page.extract_text() with its three hooks.
The text visitor delivers the decoded text; the two operator hooks let this
module keep the whole graphics state next to it: transformation matrix, q/Q
stack, fill and stroke colour with their colour spaces, opacity, font and
size, text matrix and text line matrix, text render mode, the current path,
the clipping path as a bounding box, marked content of optional layers, and
nested Form XObjects with their own /Matrix and /Resources. Every
text-showing operator (Tj, TJ, ', ") is noted with the state it is shown in.
When pypdf hands over a piece of decoded text, it is booked on these notes in
their order: each takes as many characters as it showed glyphs. Glyphs that
the font's ToUnicode table maps to a blank are not glyphs of text (a font may
show its spaces as glyphs of their own). Where the two counts still differ,
the piece is divided in proportion. pypdf repeats the whole text of a Form
XObject after walking it; that repetition is dropped, and the transformation
matrix inside a Form XObject is carried on from the page (pypdf starts it
anew). The count is checked against the extracted text of the page; a
difference is reported in `hinweise`.

Characters   non-white-space characters of the decoded text. NOT counted:
             * leaders — three or more equal characters in a row that are
               punctuation, a mathematical or modifier symbol or a control
               character («______», «.......», «………»). They are the writing
               lines of a form, not its text: in 28 Formulare they are more
               than half of all characters, often set in 2 to 4 pt;
             * text of an effective size below 1 pt;
             * invisible text (render mode 3 or 7, the text layer of a scan
               after text recognition) — it counts for `textebene` and for
               the text detectors, but has no font, size or colour;
             * text that is not shown at all: its line starts outside the
               page or outside the bounding box of the clipping path (by
               more than its own size), the clipping box is empty, or it
               stands on a layer that is switched off (optional content).
               Such text is the rest of a placed page or of a layout
               program's work; a line of the page text that consists of it
               alone is also kept from the text detectors;
             * text set a second time at the same place (the same string,
               font and size at the same start of line): one visible text.
Size         font size × scale of the text matrix × scale of the current
             transformation matrix (square root of |determinant|), rounded
             to 0.5 pt. anteil_unter_8 and kleinste use the rounded sizes.
             For text that is stretched in one direction this is not the
             nominal height of the font (one Formular, about 5 % of its
             characters, 7.0 instead of 6.5 pt). When the base size leads
             the next size by less than 5 points of share, `hinweise` says
             that the form has no clear base size.
Font family  the /BaseFont name without subset prefix, style suffixes and
             edition marks (schriftfamilie()). The editions of one typeface
             (Frutiger LT Std/Pro/Com, Helvetica Neue LT Std/Pro, Univers LT
             Std, Gill Sans MT) are one family; a condensed or narrow cut is
             its own family (Arial Narrow, Frutiger Condensed); Arial,
             Helvetica and Times stay apart. schriftgruppe() gives the
             typeface without its cut and with Times New Roman under Times,
             schriftklasse() serif / sans for the families it knows — both
             for comparing Formulare; `hinweise` says when the main font
             leads the next family by less than 15 points of share. A font
             whose name is a placeholder of the PDF producer («CIDFont+F1»)
             is named after the name table of its embedded font program;
             when that is not possible it is listed as «(Name nicht lesbar)»,
             and hauptschrift / n_schriftfamilien become null rather than a
             guess.
             `symbol`: by name (Wingdings, Webdings, Symbol, Zapf Dingbats,
             pi and bar-code fonts, *Symbol) or because every character set
             in the family is a symbol character (Unicode category So — the
             check boxes set in MS Gothic).
             `eingebettet`: every font of the family that is used carries a
             font program (/FontFile, /FontFile2, /FontFile3; a Type 3 font
             is part of the file by nature). The 14 PDF standard fonts are
             reported as not embedded when they are not, and named in
             `hinweise`; barrierefrei.schriften_eingebettet asks only whether
             every OTHER font that sets counted characters is embedded (a
             font that sets nothing but blanks is named in `hinweise`).
Colour       every fill and stroke colour that the page content uses,
             converted to sRGB: DeviceGray/RGB, CalGray/CalRGB, ICCBased by
             its number of components, Lab by the usual formulas, Indexed
             through its base, DeviceCMYK by the simple formula with the real
             screen colours of the four inks (see below). A constant opacity
             (ExtGState /ca, /CA) is mixed with white paper.
             * neutral = HSV saturation < 0.15 or value < 0.30 (black, the
               greys, white, and a tinted black). As a filled area a pale
               tint counts as a colour from saturation 0.05 when its value
               is at least 0.80 — the light blue, green or beige of shaded
               fields; as the colour of text or of a line it stays neutral.
               Colours within 0.04 per channel form one cluster, named after
               its heaviest member.
             * anteil_text = share of all counted characters; anteil_flaeche
               = painted area ÷ area of all pages. Rectangles and straight
               polygons count with their exact area, curves as polygons (six
               segments per Bézier curve), a sub-path inside another one as a
               hole or a repetition by the fill rule, lines with length ×
               line width (at least 0.5 pt: a hairline is drawn one device
               pixel wide, on a screen about that) × the share of its length
               that its dash pattern paints. Nothing is rendered: overlap between paths and
               shapes covered later are not resolved, and the clipping path
               (W, W*, the /BBox of a Form XObject) is honoured only as a
               bounding box — a painted area is capped by the part of its
               own bounding box that lies inside it and on the page. The
               area therefore tends to be too large, never too small.
             * gewicht = the share of the page area that the colour paints:
               its fills and lines plus the ink of its text, taken as TINTE ×
               size² per character (0.16 — the median over the 32 Formulare
               whose colour is text only, counted on rendered pages). It
               puts text and fills on one scale and gives the order of
               `farben`.
             * a colour is reported when it colours at least 20 characters
               or paints at least 300 pt² (fills, lines and the ink of its
               text together), whatever the number of pages. The shades of
               one family that stay below that count together when their
               sum reaches it (the strips of a gradient). A colour that
               still stays below is named in `hinweise` (from one character
               or 10 pt²), so that «no colour» is never said of a form that
               shows some.
             * nur_link = every character of the colour belongs to an
               internet or e-mail address or stands under a link annotation
               — a linked word such as «Vollmacht» (together at least 90 %;
               an address shown in several pieces is put together first),
               the colour fills no area of 300 pt², and its lines (the
               underlines) weigh no more than the ink of that text. Under a
               link: the line of the text starts inside the annotation's
               box; for text that follows other text on its line only the
               line is known, and it counts when the box reaches further
               right than the start of the line. A link colour is listed in
               `farben`, but it is no accent and no colour family of the
               form (`hinweise` names it).
             * nur_kopf = the colour is nothing but a small mark in the head
               of page 1 — a logo that is drawn instead of placed as an
               image: it sets no text, paints on the first page only, and
               everything it paints lies in the upper 15 % of that page
               (KOPF_HOEHE) within a box of at most half the page width
               (KOPF_BREITE). Listed in `farben`, no accent and no colour
               family of the form, named in `hinweise` — as the same logo
               is when it is an image. A bar across the page, a panel
               further down and a colour that returns on a later page are
               colours of the form.
             * feld = the colour is painted by form fields, buttons or
               annotations, not by the page: measured apart, through their
               appearance streams (/AP /N; a widget without one through the
               /MK colours it declares), area only — the text that a field
               shows is not measured. Listed in `farben` with feld = true,
               no accent and no colour family of the form.
             * akzent = the heaviest colour of the heaviest colour family
               among the colours that are neither link colour, field colour
               nor head mark;
               n_farbfamilien counts those families (farbwahl()). akzent =
               null means: no colour of the page content above the
               threshold — not «black and white only»: colour in images, in
               form fields and below the threshold is outside it, and
               `hinweise` says which of these the file has.
             * anteil_text_farbig covers every non-neutral text colour,
               reported or not, link colours included.
             Images are not analysed. A logo is usually an image: its colours
             are invisible here, and `hinweise` says so whenever page 1
             paints an image.
Barrierefrei machine-checkable minimum marks, not a verdict: a missing mark is
             a finding, a present mark is no proof of an accessible form.
             tags = /StructTreeRoot with at least one structure element AND
             /MarkInfo /Marked true (`hinweise` says when the fields of a
             tagged form are not in the tree, when it has no headings, when
             the tree is there without the mark or the mark without a tree);
             sprache = /Lang of the catalog, as written; sprache_passt = false
             when it is not the language of the text (true when it is, null
             when no language is declared or the text is too short to tell;
             `hinweise` says so, and also when only structure elements carry
             a language); titel = /Title of the document
             information, else dc:title of the XMP metadata, verbatim (a
             blank title is null); titel_art see titel_art(); titel_anzeige =
             /ViewerPreferences /DisplayDocTitle (absent = false, the PDF
             default; it helps only together with a title that names the
             form, and `hinweise` says when that title is missing); felder = terminal AcroForm fields that take input
             (text, choice, check box / radio group, signature — push buttons
             are not counted; a radio group is one field, whatever the number
             of its widgets; read-only and hidden fields are counted);
             felder_beschriftet = those with a /TU that names the field — a
             /TU that is only a placeholder of the automatic field
             recognition («3», «[1]», «undefined», «Textfield») does not count
             (`hinweise` gives their number); textebene = the pages carry
             extractable text; text_lesbar = false when a page stores its
             text as control characters instead of letters (at least 10 % of
             its characters: a font without a usable character table) — such
             text is there, but neither a screen reader nor the search gets
             words from it. A PDF/UA declaration in the XMP metadata is
             named in `hinweise` and not checked.
Contact      a pre-filled text field prints its value like the text of the
             page: the values join the lines for Telefon and E-Mail (not for
             the other detectors), and `hinweise` says when a number or an
             address comes from there. Text under a strike-out marking of
             the file (a comment annotation that crosses text out) is taken
             out of the lines before the text detectors read them: the
             office has withdrawn it. Only text whose start is known
             exactly is taken out, and at least three characters of it
             (`hinweise` says so). telefon() gets the lines page by page, so
             that a contact block apart from the letterhead of its page is
             read together with it (gestaltung_text.py).
pdf_bild     fewer than 40 non-white-space characters in the whole file
             (leaders included): a scan. Fonts, sizes, colours and the text
             detectors are then null (not «nothing found»),
             barrierefrei.textebene is false.

Where this module reads the specification more closely than its wording
------------------------------------------------------------------------
* messen() takes the Dienststelle and the name of the Formular as optional
  arguments, because elemente.absender and barrierefrei.titel_art need them;
  messen(path) alone gives absender.dienststelle = null and, for a title that
  is neither empty nor generic, titel_art = null.
* Leaders are not characters (see above). Counted as text they would make
  2 pt the base size of a 12 pt form.
* DeviceCMYK: the textbook formula assumes ideal inks, so plain cyan becomes
  #00ffff («Türkis») while the same cyan given as Lab or RGB in a sister
  form is #009ee3 («Blau») — a difference the measurement would invent. The
  formula is kept, but with the screen colours of the real inks (_TINTEN);
  the ideal inks are its special case. `hinweise` names the approximation;
  the hex of such a colour is not exact.
* Separation colours are NOT skipped when their tint transform is an
  exponential function (type 2 — every spot colour of the corpus): they are
  converted through their alternate colour space, which is what a screen
  shows, and named in `hinweise`. DeviceN is converted when its colourants
  are process colours (Cyan/Magenta/Yellow/Black). Other spot colours,
  patterns and shadings are skipped with a hinweis, as specified; so is a
  spot colour that marks a cutting or creasing line («CutContour»): it is no
  colour of the print.
* Curved shapes are measured as polygons with holes instead of by their
  bounding box: the box made a thin rounded frame as heavy as a filled
  panel. `hinweise` says when a reported colour rests on such an estimate.
* For a `pdf_bild` and for an unreadable file the list values (schriften,
  groessen, farben, telefon, email) are null, not [], and the leaves of
  `elemente` are null: an empty list would claim «measured, none found». A
  file whose text is invisible throughout (a scan with a recognised text
  layer) stays 'pdf'; its fonts, sizes and colours are null, its text
  detectors are measured.
* An unreadable or password-protected PDF gives messart 'pdf' with every
  measured value null and the reason in `hinweise`; a missing file raises.
* Each entry of `farben` carries four keys more than the specification
  lists: gewicht, nur_link, feld, nur_kopf; `barrierefrei` carries two more:
  sprache_passt, text_lesbar.
* A control character inside a PDF string (a NUL that pads a title or a
  language tag) is no character of it.

Where this module CHANGES a definition of the specification
------------------------------------------------------------
The first measurement was held against rendered pages, a second PDF reader
and the forms themselves (2026-10-04). Where a definition, not the code, gave
values that a reader of the form would call wrong, the definition was changed:
* neutral: value < 0.30 instead of < 0.15 (a tinted black counted as «Grün»);
  a pale fill counts as a colour (shaded fields were invisible: 23 Formulare
  had at least 1 % of their pixels in such a tint).
* colour families: the borders Orange/Gelb at 40° (was 45°), Türkis/Blau at
  190° (195°) and Blau/Violett at 250° (255°). The old borders cut through
  one palette colour each: the Office gold and its tints (44.7° to 45.3°),
  process cyan (195° to 198°), the dark violet of one form (252° to 255°). A
  dark orange (value < 0.60) is «Braun».
* a colour counts by painted area (300 pt², any shape, any number of pages)
  or by 20 characters. Before, a hairline of 20 pt counted and a solid block
  of 31 × 32 pt did not, and the area needed grew with the page count.
* the order of `farben` and `akzent`: by gewicht (text as ink) and per colour
  family, instead of the share of characters plus the share of area. A few
  coloured sentences no longer outweigh a coloured panel.
* a link colour and a field colour are no accent (the specification listed
  the link blue «like any colour»): half of all accents were nothing but the
  colour of a web or e-mail address.
* tags: an empty structure tree is no tagging.
* felder_beschriftet: a placeholder tooltip is no label.
* titel_art: the value 'aussagekraeftig' needs evidence — the title names the
  Formular as the databank names it; the new value 'ohne_bezug' is a title
  that does not («Herr», «Office 2010», the title of another form); a
  print-driver title behind a bracket, a bare internet address and a file
  name without ending are 'generisch'.
* characters: text that is not shown and text set twice are not counted.
* contact data: the value of a pre-filled text field is read as printed text
  (the office's own address and number often stand in such a field).
After the acceptance check of that second measurement (method 'gestaltung-2'):
* a link colour is also the colour of linked WORDS (text under a link
  annotation), not only of addresses: on eight Formulare the «accent» was
  nothing but the colour of hyperlinks.
* a small mark of colour in the head of page 1 is no accent (nur_kopf): a
  logo drawn as vector graphics was judged as the colour of the form, the
  same logo as an image was not. The 300 pt² threshold stays; the rule takes
  the nine federal shields and the drawn logos of ten more Formulare out of
  the accent.
* a dashed line counts with the share of its length that is painted (a
  dashed hairline of 0.1 pt weighed as much as a solid line of 0.5 pt).
* text under a strike-out marking is kept from the text detectors.

Deliberately NOT measured
-------------------------
A full accessibility audit (reading order, alternative texts, contrast,
WCAG / PDF/UA conformance, the quality of the tags); the canton's corporate
design (the manual is not in the repository — the comparison is with the
practice of the other Formulare); logos and everything else inside images,
also phone numbers and addresses there; layout geometry (margins, positions,
alignment); the fonts and the text of form-field widgets, push buttons, links
and comments (their colours are measured apart, see feld); gradients and
patterns (named in `hinweise`); whether a colour is covered by a later
shape; the 42 eFormulare (their look is the platform's). Text is what pypdf
extracts: a font without a usable encoding gives wrong characters but the
right counts, and `hinweise` names a page whose text is not readable.
"""
import colorsys
import logging
import math
import os
import re
import struct
import sys
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gestaltung_text  # noqa: E402  (standard library only)
# defined there, because the comparison layer needs them under a Python without pypdf; part of this
# module's interface as before
from gestaltung_text import (schriftgruppe, ist_neutral, ist_blass, _rgb01,  # noqa: E402,F401
                             NEUTRAL_S, NEUTRAL_V, TON_S, TON_V)

__all__ = ["messen", "schriftfamilie", "schriftgruppe", "schriftklasse", "farbfamilie", "ist_neutral", "titel_art", "seitenformat",
           "zaehlbar", "farbwahl", "knapp_hinweise"]

# ------------------------------------------------------------------ thresholds
MIN_ZEICHEN_BILD = 40        # fewer characters in the whole file: pdf_bild
MIN_ZEICHEN_FARBE = 20       # a colour counts from this many characters …
MIN_FLAECHE_PT2 = 300.0      # … or from this painted area in pt² (fills, lines and the ink of its text together)
TINTE = 0.16                 # ink of one character ≈ TINTE × (size in pt)²: text and fills on one scale
LINIE_MAX_DICKE = 3.0        # a filled rectangle up to this thickness is a line
MIN_LINIE_DICKE = 0.5        # a stroked line counts at least this wide: a hairline is drawn one device pixel wide
MIN_ZEICHEN_KLEINSTE = 20    # `kleinste`: the size must carry this many characters
CLUSTER = 0.04               # colours this close per channel are one colour
# NEUTRAL_S, NEUTRAL_V, TON_S, TON_V (what is a grey, what a pale tint): gestaltung_text.py, imported above
KOPF_HOEHE = 0.15            # the head of page 1: its upper 15 % …
KOPF_BREITE = 0.50           # … and a mark there is at most half the page wide (a logo, not a title bar)
KNAPP_GROESSE = 0.05         # a base size whose lead over the next size is smaller is named in hinweise
KNAPP_SCHRIFT = 0.15         # the same for the main font
OHNE_NAME = "(Name nicht lesbar)"


# =============================================================== shared notions

# _rgb01(), ist_neutral() and their four thresholds are defined in gestaltung_text.py (imported above): the
# comparison layer asks the same question («is this a pale tint?») under a Python without pypdf.

_FAMILIEN = ((15, "Rot"), (40, "Orange"), (70, "Gelb"), (165, "Grün"), (190, "Türkis"),
             (250, "Blau"), (290, "Violett"), (345, "Magenta"), (361, "Rot"))
BRAUN_V = 0.60               # an orange hue darker than this is brown


def farbfamilie(farbe):
    """Colour family by hue: Rot [345–15), Orange [15–40), Gelb [40–70), Grün
    [70–165), Türkis [165–190), Blau [190–250), Violett [250–290), Magenta
    [290–345); an orange hue of HSV value below 0.60 is Braun."""
    h, _s, v = colorsys.rgb_to_hsv(*_rgb01(farbe))
    grad = h * 360.0
    for grenze, name in _FAMILIEN:
        if grad < grenze:
            return "Braun" if name == "Orange" and v < BRAUN_V else name
    return "Rot"


def farbwahl(eintraege):
    """(akzent, n_farbfamilien) for the entries of `farben` (each with familie,
    gewicht, nur_link, feld, nur_kopf) — the one rule for every file type.
    Link colours, the colours of form fields and annotations, and a colour
    that is only a small mark in the head of page 1 (a drawn logo) are no
    accent and no family of the form. The weights are added up per family;
    the accent is the heaviest colour of the heaviest family."""
    je_familie = {}
    for e in eintraege:
        if not e["nur_link"] and not e["feld"] and not e["nur_kopf"]:
            je_familie.setdefault(e["familie"], []).append(e)
    if not je_familie:
        return None, 0
    beste = min(je_familie.values(), key=lambda g: (-sum(e["gewicht"] for e in g), g[0]["familie"]))
    kopf = min(beste, key=lambda e: (-e["gewicht"], e["hex"]))
    return {"hex": kopf["hex"], "familie": kopf["familie"]}, len(je_familie)


def _pt(x):
    """A size as the dashboard writes numbers (de-CH): «10.5» (gestaltung_export.py reads an older «10,5» the same way)."""
    return "%g" % x


def knapp_hinweise(schriften, groessen, hinweise):
    """Say in hinweise when the base size or the main font wins by a small
    margin only: the value is measured, but the form has no clear one."""
    if groessen and len(groessen) > 1 and groessen[0]["anteil"] - groessen[1]["anteil"] < KNAPP_GROESSE:
        hinweise.append(gestaltung_text.H_GROESSE_KNAPP + " %s pt (%s) und %s pt (%s) liegen fast gleichauf."
                        % (_pt(groessen[0]["pt"]), _prozent(groessen[0]["anteil"]),
                           _pt(groessen[1]["pt"]), _prozent(groessen[1]["anteil"])))
    text = [s for s in (schriften or []) if not s["symbol"]]
    if len(text) > 1 and text[0]["anteil"] - text[1]["anteil"] < KNAPP_SCHRIFT:
        hinweise.append(gestaltung_text.H_SCHRIFT_KNAPP + " %s (%s) vor %s (%s)."
                        % (text[0]["familie"], _prozent(text[0]["anteil"]), text[1]["familie"], _prozent(text[1]["anteil"])))


def _hex(rgb255):
    return "#%02x%02x%02x" % tuple(rgb255)


_DATEI_ENDE = re.compile(r"(?i)\.(?:docx?|docm|dotx?|dotm|rtf|odt|ott|xlsx?|xlsm|xltx?|ods|pptx?|pdf|indd|qxd|qxp|"
                         r"ai|eps|txt|pages|pub|vsdx?|wpd|tmp|fm|p65|pm6?)$")
_GENERISCH = re.compile(r"(?i)^(?:dokument|document|untitled|unbenannt|formular)[\s_\-]*\d*$")
_DRUCKTITEL = re.compile(r"(?i)^[(\[«\"' ]*microsoft (?:word|excel|powerpoint|publisher|visio)\b")
_NUR_ADRESSE = re.compile(r"(?i)^(?:https?://|www\.)\S+$")
_DATEICODE = re.compile(r"^(?=\S*_)(?=\S*\d{3})\S+$")        # «4907369_Gesuch_LFA_SH:-»: a file name without its ending
_TITEL_STOPP = frozenset("""der die das des dem den und oder für fuer von vom zur zum bei mit auf aus als ein eine einer
eines einem einen über ueber unter nach gemäss gemaess sowie bzw resp betreffend the and for les des pour del per
formular""".split())


def _titelworte(text):
    """The words of a title or of a Formular's name that can name it: lower
    case, umlauts as ae/oe/ue, from three letters or two digits, without
    articles, prepositions and the word «Formular»."""
    t = unicodedata.normalize("NFC", text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    t = "".join(ch for ch in unicodedata.normalize("NFD", t) if not unicodedata.combining(ch))
    worte = []
    for w in re.findall(r"[^\W_]+", t):
        if (len(w) >= 3 or (w.isdigit() and len(w) >= 2)) and w not in _TITEL_STOPP and w not in worte:
            worte.append(w)
    return worte


def _gleiches_wort(a, b):
    """The same word, or one begins with the other («gesuch» / «gesuchsformular»; at least five letters)."""
    if a == b:
        return True
    kurz, lang = (a, b) if len(a) <= len(b) else (b, a)
    return len(kurz) >= 5 and lang.startswith(kurz)


def titel_bezug(titel, formular):
    """Does the title name the Formular? True when two words of the title
    occur in the Formular's name, or one does and it is at least half of the
    words of the title or covers at least half of the words of the name."""
    t, f = _titelworte(titel), _titelworte(formular)
    if not t or not f:
        return False
    in_name = sum(1 for w in t if any(_gleiches_wort(w, x) for x in f))
    im_titel = sum(1 for x in f if any(_gleiches_wort(w, x) for w in t))
    return in_name >= 2 or (in_name == 1 and (2 * in_name >= len(t) or 2 * im_titel >= len(f)))


def titel_art(titel, formular=None):
    """'leer' | 'generisch' | 'aussagekraeftig' | 'ohne_bezug' | None for a
    document title.
    leer: missing or blank. generisch: empty-like (fewer than three letters —
    «1», «1   0001»), a file name (also without its ending: no blank, an
    underscore and a number), a print-driver title («Microsoft Word - …», also
    behind a bracket), a bare internet address, or one of Dokument / Document /
    Untitled / Unbenannt / Formular (also numbered).
    Every other title is held against `formular`, the name of the Formular in
    the databank: aussagekraeftig when it names the Formular (titel_bezug),
    ohne_bezug when the two share no naming word («Herr», «Office 2010», the
    title of another form). Without `formular` this cannot be told: None."""
    t = (titel or "").replace("\x00", "").strip()
    if not t:
        return "leer"
    if sum(1 for ch in t if ch.isalpha()) < 3:
        return "generisch"
    if _DATEI_ENDE.search(t) or _DRUCKTITEL.match(t) or _GENERISCH.match(t) or _NUR_ADRESSE.match(t) \
            or _DATEICODE.match(t):
        return "generisch"
    if not (formular or "").strip():
        return None
    return "aussagekraeftig" if titel_bezug(t, formular) else "ohne_bezug"


H_TITEL_OHNE_NAMEN = ("Dokumenttitel vorhanden; ob er das Formular nennt, ist ohne den Namen des Formulars "
                      "nicht bestimmbar.")


def seitenformat(breite_pt, hoehe_pt):
    """{'name': 'A4 hoch' | 'A4 quer' | 'anderes', 'breite_mm', 'hoehe_mm'} for a
    page of the given size in points; A4 (210 × 297 mm) with ± 3 mm tolerance."""
    b = breite_pt * 25.4 / 72.0
    h = hoehe_pt * 25.4 / 72.0
    if abs(b - 210) <= 3 and abs(h - 297) <= 3:
        name = "A4 hoch"
    elif abs(b - 297) <= 3 and abs(h - 210) <= 3:
        name = "A4 quer"
    else:
        name = "anderes"
    return {"name": name, "breite_mm": int(round(b)), "hoehe_mm": int(round(h))}


# ---------------------------------------------------------------- font families

# one style word of a PostScript name («-BoldItalicMT», «-SemiboldIt», «-BlackCn»)
_STILWORT = (r"(?:Ultra|Extra|Semi|Demi|Bold|Bd|Black|Blk|Heavy|Light|Lt|Thin|Medium|Md|Regular|Regu|Reg|"
             r"Roman|Book|Italic|Ital|It|Oblique|Obl|Kursiv|Fett|bold|italic|regular|light|"
             r"Condensed|Cond|Cn|Narrow)")
_STIL = re.compile(_STILWORT + r"+(?:PSMT|PS|MT)?")
_SCHMAL = re.compile(r"Condensed|Cond|Cn")
# style words behind a blank, as Office names a cut: «Arial Narrow Bold», «Frutiger LT Com 45 Light»
_STIL_LEER = re.compile(r" (?:Bold|Italic|Oblique|Regular|Light|Medium|Semibold|SemiBold|Thin|Book|Fett|Kursiv|"
                        r"Standard|\d{2}(?: Roman)?)$")
_SCHMAL_LEER = re.compile(r" (?:Condensed|Cond|Cn)$")
_STIL_KLEBT = re.compile(r"(?<=[a-z])(?:BoldItalic|BoldOblique|Bold|Italic|Oblique|Regular)$")
_PSMT = re.compile(r"(?<=[a-z])(?:PSMT|PS|MT)$")
_AUSGABE = re.compile(r"(?<=[a-z])(?: ?LT)?(?: ?(?:Std|Pro|Com))?$")      # FrutigerLTStd, UniversLTStd
_ITC = re.compile(r"(?<=[a-z])ITC$")
_PLATZHALTER = re.compile(r"^(?:CIDFont\+F\d+|TT[0-9A-F]{2,4}o\d{2}|F\d+|T\d+_\d+|T\d+|TT\d+|Font\d+|R\d+|"
                          r"C\d+_\d+|[A-Z]\d{1,3})$")

# checked first, on the name reduced to lower-case letters and digits
_ALIAS_ANFANG = (
    (re.compile(r"^arialblack"), "Arial Black"),
    (re.compile(r"^arialrounded"), "Arial Rounded"),
    (re.compile(r"^arialunicode"), "Arial Unicode MS"),
    (re.compile(r"^wingdings2"), "Wingdings 2"),
    (re.compile(r"^wingdings3"), "Wingdings 3"),
    (re.compile(r"^wingdings"), "Wingdings"),
    (re.compile(r"^webdings"), "Webdings"),
    (re.compile(r"^zapfdingbats"), "Zapf Dingbats"),
    (re.compile(r"^segoeuisymbol"), "Segoe UI Symbol"),
    (re.compile(r"^segoeuiemoji"), "Segoe UI Emoji"),
    (re.compile(r"^msgothic"), "MS Gothic"),
    (re.compile(r"^mspgothic"), "MS PGothic"),
    (re.compile(r"^msmincho"), "MS Mincho"),
    (re.compile(r"^europeanpi"), "European Pi"),
    (re.compile(r"^ocrb"), "OCR-B"),
    (re.compile(r"^ocra"), "OCR-A"),
)
# after the generic cleaning, on the same reduced form: known families get their spaces back
_ALIAS = {
    "arial": "Arial", "arialnarrow": "Arial Narrow", "timesnewroman": "Times New Roman", "times": "Times",
    "couriernew": "Courier New", "courier": "Courier", "helvetica": "Helvetica",
    "helveticaneue": "Helvetica Neue", "segoeui": "Segoe UI", "bookantiqua": "Book Antiqua",
    "gillsans": "Gill Sans", "frutiger": "Frutiger", "frutigerneue": "Frutiger Neue",
    "myriadpro": "Myriad Pro", "myriad": "Myriad Pro", "minionpro": "Minion Pro", "minion": "Minion Pro",
    "scalasans": "Scala Sans", "scalasanspro": "Scala Sans", "univers": "Univers",
    "corporatea": "Corporate A", "corporates": "Corporate S", "dinot": "DIN OT", "din": "DIN",
    "eualbertina": "EU Albertina", "freestylescript": "Freestyle Script", "malgungothic": "Malgun Gothic",
    "symbol": "Symbol", "opensymbol": "OpenSymbol", "centurygothic": "Century Gothic",
    "centuryschoolbook": "Century Schoolbook", "trebuchet": "Trebuchet MS", "trebuchetms": "Trebuchet MS",
    "comicsans": "Comic Sans MS", "comicsansms": "Comic Sans MS", "lucidasans": "Lucida Sans",
    "lucidasansunicode": "Lucida Sans Unicode", "lucidaconsole": "Lucida Console",
    "palatinolinotype": "Palatino Linotype", "bookmanoldstyle": "Bookman Old Style",
    "sourcesanspro": "Source Sans Pro", "sourcesans3": "Source Sans 3", "opensans": "Open Sans",
    "notosans": "Noto Sans", "liberationsans": "Liberation Sans", "liberationserif": "Liberation Serif",
    "dejavusans": "DejaVu Sans", "franklingothic": "Franklin Gothic", "microsoftsansserif": "Microsoft Sans Serif",
    "akzidenzgrotesk": "Akzidenz-Grotesk", "thesans": "TheSans", "avenirnext": "Avenir Next",
}
_SYMBOL_NAME = re.compile(r"^(?:wingdings|webdings|symbol|zapfdingbats|europeanpi|opensymbol|segoeuisymbol|"
                          r"segoeuiemoji|mtextra|marlett|bookshelfsymbol|c39|code39|code128|ean13|"
                          r"msreferencespecialty|monotypesorts)|symbols?$|dingbats")
_STANDARD14 = frozenset("""Times-Roman Times-Bold Times-Italic Times-BoldItalic Helvetica Helvetica-Bold
    Helvetica-Oblique Helvetica-BoldOblique Courier Courier-Bold Courier-Oblique Courier-BoldOblique
    Symbol ZapfDingbats""".split())


def _reduziert(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _ohne_praefix(name):
    """The /BaseFont name without slash, name escapes, subset prefix and CMap suffix."""
    n = (name or "").lstrip("/").replace("#2320", " ").replace("#20", " ").strip()
    n = re.sub(r"^[A-Z]{6}\+", "", n)
    return re.sub(r"-{1,2}Identity-[HV]$", "", n)


def schriftfamilie(name):
    """(familie, symbol) for a font name as a PDF or an Office file gives it:
    'ABCDEF+Arial-BoldMT' -> ('Arial', False), 'TimesNewRomanPS-ItalicMT' ->
    ('Times New Roman', False), 'ArialNarrow,Bold' -> ('Arial Narrow', False),
    'Wingdings-Regular' -> ('Wingdings', True). (None, False) for a missing name
    or a producer's placeholder («CIDFont+F1», «TTC78o00»)."""
    n = _ohne_praefix(name)
    if not n or n == "None" or _PLATZHALTER.match(n):
        return None, False
    roh = _reduziert(n)
    symbol = bool(_SYMBOL_NAME.search(roh))
    for rx, fam in _ALIAS_ANFANG:
        if rx.match(roh):
            return fam, symbol
    n = n.split(",")[0].strip()
    zusatz = ""
    while "-" in n:
        kopf, _, schwanz = n.rpartition("-")
        if not kopf or not _STIL.fullmatch(schwanz):
            break
        if _SCHMAL.search(schwanz):
            zusatz = " Condensed"
        elif "Narrow" in schwanz:
            zusatz = " Narrow"
        n = kopf
    while True:
        if _STIL_LEER.search(n):
            n = _STIL_LEER.sub("", n)
        elif _SCHMAL_LEER.search(n):
            n, zusatz = _SCHMAL_LEER.sub("", n), " Condensed"
        else:
            break
    n = _PSMT.sub("", n)
    n = _STIL_KLEBT.sub("", n)
    n = _PSMT.sub("", n)
    if _reduziert(n) not in _ALIAS:
        n = _ITC.sub("", _AUSGABE.sub("", n)).strip() or n
    fam = _ALIAS.get(_reduziert(n), n.strip())
    return fam + zusatz, symbol


_SERIF = frozenset("""Times|Times New Roman|Cambria|Georgia|Garamond|Book Antiqua|Palatino Linotype|Century Schoolbook|
Bookman Old Style|Minion Pro|EU Albertina|Liberation Serif|Corporate A""".replace("\n", "").split("|"))
_SANS = frozenset("""Arial|Arial Narrow|Arial Black|Arial Rounded|Arial Unicode MS|Helvetica|Helvetica Neue|Frutiger|
Frutiger Condensed|Frutiger Neue|Calibri|Verdana|Tahoma|Myriad Pro|Univers|Scala Sans|Segoe UI|Trebuchet MS|Gill Sans|
Corporate S|DIN|DIN OT|Open Sans|Source Sans Pro|Source Sans 3|Noto Sans|Century Gothic|Aptos|TheSans|Akzidenz-Grotesk|
Avenir Next|Franklin Gothic|Lucida Sans|Lucida Sans Unicode|Microsoft Sans Serif|Liberation Sans|DejaVu Sans|
Malgun Gothic""".replace("\n", "").split("|"))
_FEST = frozenset("Courier|Courier New|Lucida Console|OCR-A|OCR-B".split("|"))


def schriftklasse(familie):
    """'serif' | 'sans' | 'fest' (fixed pitch) for the families this module
    knows, None for every other name (never a guess from the name)."""
    return "serif" if familie in _SERIF else "sans" if familie in _SANS else "fest" if familie in _FEST else None


def _name_aus_programm(daten):
    """The PostScript or family name in the name table of a TrueType font program."""
    try:
        n_tab = struct.unpack(">H", daten[4:6])[0]
        for i in range(min(n_tab, 64)):
            tag, _, off, laenge = struct.unpack(">4sLLL", daten[12 + 16 * i:28 + 16 * i])
            if tag != b"name":
                continue
            nt = daten[off:off + laenge]
            _, anzahl, lager = struct.unpack(">HHH", nt[:6])
            gefunden = {}
            for j in range(min(anzahl, 400)):
                pid, _, _, nid, l2, o2 = struct.unpack(">HHHHHH", nt[6 + 12 * j:18 + 12 * j])
                if nid not in (1, 6):
                    continue
                roh = nt[lager + o2:lager + o2 + l2]
                text = roh.decode("utf-16-be", "replace") if pid in (0, 3) else roh.decode("latin-1")
                text = text.replace("\x00", "").strip()
                if text and nid not in gefunden:
                    gefunden[nid] = text
            return gefunden.get(6) or gefunden.get(1)
    except Exception:
        return None
    return None


# ================================================================ PDF helpers

def _o(x):
    """The object behind an indirect reference (None stays None)."""
    try:
        return x.get_object()
    except Exception:
        return x


def _wahr(x):
    x = _o(x)
    return getattr(x, "value", x) is True


def _zahlen(operanden, n):
    return [float(x) for x in operanden[:n]]


_STEUERZEICHEN = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _text(x):
    """A PDF string as str, without control characters other than tab and line
    breaks (None when it is none)."""
    x = _o(x)
    if x is None:
        return None
    if isinstance(x, bytes):
        x = x.decode("utf-16", "replace") if x[:2] in (b"\xfe\xff", b"\xff\xfe") else x.decode("latin-1")
    if isinstance(x, str):
        return _STEUERZEICHEN.sub("", str(x))        # a NUL that pads a PDF string is no character of it
    return None


def _mult(m, n):
    """m × n for two PDF matrices [a b c d e f] (m is applied first)."""
    return (m[0] * n[0] + m[1] * n[2], m[0] * n[1] + m[1] * n[3],
            m[2] * n[0] + m[3] * n[2], m[2] * n[1] + m[3] * n[3],
            m[4] * n[0] + m[5] * n[2] + n[4], m[4] * n[1] + m[5] * n[3] + n[5])


_EINS = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _massstab(m):
    return math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))


def _c(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def _gamma(v):
    v = _c(v)
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def _lab_rgb(L, a, b):
    """CIE L*a*b* (taken as relative to D50, the usual white point of a PDF) -> sRGB
    by the Bradford-adapted matrix."""
    fy = (L + 16.0) / 116.0
    fx, fz = fy + a / 500.0, fy - b / 200.0

    def kehr(t):
        return t ** 3 if t > 6.0 / 29.0 else 3 * (6.0 / 29.0) ** 2 * (t - 4.0 / 29.0)
    x, y, z = 0.9642 * kehr(fx), 1.0 * kehr(fy), 0.8249 * kehr(fz)
    return (_gamma(3.1338561 * x - 1.6168667 * y - 0.4906146 * z),
            _gamma(-0.9787684 * x + 1.9161415 * y + 0.0334540 * z),
            _gamma(0.0719453 * x - 0.2289914 * y + 1.4052427 * z))


# The four process inks as a screen shows them at full coverage (the usual sRGB
# equivalents of the European offset inks on coated paper: cyan #009fe3,
# magenta #e6007e, yellow #ffed00, black #1d1d1b). The textbook conversion
# assumes ideal inks (#00ffff, #ff00ff, #ffff00, #000000); with it, plain cyan
# falls into another colour family than the same cyan given as RGB or Lab.
_TINTEN = ((0.0, 0.624, 0.890), (0.902, 0.0, 0.494), (1.0, 0.929, 0.0), (0.114, 0.114, 0.106))


def _cmyk_rgb(c, m, y, k):
    """Each ink filters the white paper by its coverage: per channel the product
    of 1 - coverage × (1 - ink)."""
    rgb = [1.0, 1.0, 1.0]
    for deckung, tinte in zip((c, m, y, k), _TINTEN):
        if deckung:
            for i in range(3):
                rgb[i] *= 1.0 - deckung * (1.0 - tinte[i])
    return tuple(rgb)


# colour spaces as small tuples: (kind, …)
_CS_G, _CS_RGB, _CS_CMYK = ("g",), ("rgb",), ("cmyk",)
_CS_MUSTER = ("x", "Muster")
_GERAET = {"/DeviceGray": _CS_G, "/G": _CS_G, "/CalGray": _CS_G, "/DeviceRGB": _CS_RGB, "/RGB": _CS_RGB,
           "/CalRGB": _CS_RGB, "/DeviceCMYK": _CS_CMYK, "/CMYK": _CS_CMYK, "/Pattern": _CS_MUSTER}
_KOMP = {"g": 1, "rgb": 3, "cmyk": 4, "lab": 3, "idx": 1, "sep": 1}
# spot colours that mark where the sheet is cut, creased or varnished: production marks, not part of the print
_HILFSFARBE = re.compile(r"(?i)^(?:cut ?contour|thru-?cut|kiss ?cut|die ?line|dieline|stanze?|stanzlinie|stanzform|"
                         r"crease|rill(?:ung|linie)?|falz(?:linie)?|perfo(?:ration)?|varnish|lack|spot ?uv)\d*$")
_PROZESS = {"/Cyan": 0, "/Magenta": 1, "/Yellow": 2, "/Black": 3}


def _cs_lesen(v, tiefe=0):
    """A colour space object -> tuple understood by _umrechnen()."""
    v = _o(v)
    if isinstance(v, str):
        return _GERAET.get(str(v), ("x", "Farbraum " + str(v).lstrip("/")))
    if not isinstance(v, list) or not v or tiefe > 4:
        return ("x", "unbekannter Farbraum")
    art = str(_o(v[0]))
    if art in _GERAET:
        return _GERAET[art]
    try:
        if art == "/ICCBased":
            n = int(_o(v[1]).get("/N", 3))
            return {1: _CS_G, 3: _CS_RGB, 4: _CS_CMYK}.get(n, ("x", "ICC-Farbraum mit %d Kanälen" % n))
        if art == "/Lab":
            d = _o(v[1]) or {}
            bereich = [float(x) for x in (_o(d.get("/Range")) or [-100, 100, -100, 100])]
            return ("lab", tuple(bereich))
        if art == "/Indexed":
            basis = _cs_lesen(v[1], tiefe + 1)
            tab = _o(v[3])
            if hasattr(tab, "get_data"):
                daten = tab.get_data()
            elif hasattr(tab, "original_bytes"):
                daten = tab.original_bytes
            else:
                daten = bytes(tab)
            return ("idx", basis, bytes(daten))
        if art == "/Separation":
            name = str(_o(v[1])).lstrip("/")
            if name == "None":
                return ("x", None)                       # paints nothing
            if _HILFSFARBE.match(name.replace("#20", " ")):
                return ("x", "Hilfsfarbe «%s» (Stanz- oder Schnittlinie, wird nicht gedruckt)" % name.replace("#20", " "))
            ersatz = _cs_lesen(v[2], tiefe + 1)
            fn = _o(v[3])
            n = _KOMP.get(ersatz[0])
            if ersatz[0] != "x" and n and int(fn.get("/FunctionType", -1)) == 2:
                c0 = [float(x) for x in (_o(fn.get("/C0")) or [0.0] * n)]
                c1 = [float(x) for x in (_o(fn.get("/C1")) or [1.0] * n)]
                if len(c0) == n and len(c1) == n:
                    return ("sep", name, ersatz, tuple(c0), tuple(c1), float(fn.get("/N", 1)))
            return ("x", "Sonderfarbe «%s»" % name)
        if art == "/DeviceN":
            namen = [str(_o(x)) for x in _o(v[1])]
            if namen and all(x in _PROZESS or x == "/None" for x in namen):
                return ("devn", tuple(_PROZESS.get(x, -1) for x in namen))
            return ("x", "Sonderfarben «%s»" % ", ".join(x.lstrip("/") for x in namen))
    except Exception:
        return ("x", "unlesbarer Farbraum")
    return ("x", "Farbraum " + art.lstrip("/"))


def _cs_anfang(cs):
    """The initial colour components of a colour space."""
    k = cs[0]
    if k == "cmyk":
        return (0.0, 0.0, 0.0, 1.0)
    if k in ("sep",):
        return (1.0,)
    if k == "devn":
        return (1.0,) * len(cs[1])
    return (0.0,) * _KOMP.get(k, 1)


def _umrechnen(cs, komp, spur=None):
    """Colour components in colour space cs -> (r, g, b) floats, or a str saying
    why not (None: the colour paints nothing). spur collects how the colour was
    given: 'cmyk', or the name of a spot colour."""
    k = cs[0]
    try:
        if k == "g":
            v = _c(komp[0])
            return (v, v, v)
        if k == "rgb":
            return (_c(komp[0]), _c(komp[1]), _c(komp[2]))
        if k == "cmyk":
            c, m, y, s = (_c(x) for x in komp[:4])
            if spur is not None:
                spur.append("cmyk")
            return _cmyk_rgb(c, m, y, s)
        if k == "lab":
            br = cs[1]
            return _lab_rgb(min(max(komp[0], 0.0), 100.0), min(max(komp[1], br[0]), br[1]),
                            min(max(komp[2], br[2]), br[3]))
        if k == "idx":
            basis, tab = cs[1], cs[2]
            n = _KOMP.get(basis[0])
            if not n or basis[0] == "x":
                return basis[1] if basis[0] == "x" else "unbekannter Farbraum"
            i = int(komp[0])
            roh = tab[i * n:(i + 1) * n]
            if len(roh) < n:
                return "Farbtabelle unvollständig"
            werte = [x / 255.0 for x in roh]
            if basis[0] == "lab":
                br = basis[1]
                werte = [werte[0] * 100.0, br[0] + werte[1] * (br[1] - br[0]), br[2] + werte[2] * (br[3] - br[2])]
            return _umrechnen(basis, werte, spur)
        if k == "sep":
            t = _c(komp[0]) ** cs[5]
            rgb = _umrechnen(cs[2], [a + t * (b - a) for a, b in zip(cs[3], cs[4])], spur)
            if spur is not None and isinstance(rgb, tuple):
                spur.append("«%s»" % cs[1])
            return rgb
        if k == "devn":
            cmyk = [0.0, 0.0, 0.0, 0.0]
            for platz, wert in zip(cs[1], komp):
                if platz >= 0:
                    cmyk[platz] = wert
            return _umrechnen(_CS_CMYK, cmyk, spur)
    except Exception:
        return "unlesbare Farbangabe"
    return cs[1]


_KURVE = tuple((i / 6.0, 1.0 - i / 6.0) for i in range(1, 7))     # six segments per Bézier curve
MAX_TEILPFADE = 150          # beyond this, holes are not resolved (sum of the parts, capped)


def _pfad_flaeche(pfad, gerade_ungerade):
    """(area, of it approximated curves, of it thin rectangles, their length, bbox)
    of a path to be filled; device space. Sub-paths that lie inside another
    one (by bounding box) are holes or repetitions, by the fill rule."""
    teile = []
    for punkte, krumm, _ in pfad:
        if len(punkte) > 3 and punkte[0] == punkte[-1]:
            punkte = punkte[:-1]
        if len(punkte) < 3:
            continue
        a = 0.0
        x0 = x1 = punkte[0][0]
        y0 = y1 = punkte[0][1]
        n = len(punkte)
        for i in range(n):
            xa, ya = punkte[i]
            xb, yb = punkte[(i + 1) % n]
            a += xa * yb - xb * ya
            if xa < x0:
                x0 = xa
            elif xa > x1:
                x1 = xa
            if ya < y0:
                y0 = ya
            elif ya > y1:
                y1 = ya
        teile.append([abs(a) / 2.0, 1 if a >= 0 else -1, (x0, y0, x1, y1), krumm, punkte, -1, 0.0])
    if not teile:
        return 0.0, 0.0, 0.0, 0.0, None
    box = (min(t[2][0] for t in teile), min(t[2][1] for t in teile),
           max(t[2][2] for t in teile), max(t[2][3] for t in teile))
    verschachtelt = 1 < len(teile) <= MAX_TEILPFADE
    if verschachtelt:
        teile.sort(key=lambda t: -t[0])
        for j in range(1, len(teile)):
            bj = teile[j][2]
            for i in range(j - 1, -1, -1):              # the smallest larger part that contains it
                bi = teile[i][2]
                if (bi[0] <= bj[0] and bi[1] <= bj[1] and bi[2] >= bj[2] and bi[3] >= bj[3]
                        and teile[i][0] > teile[j][0]):
                    teile[j][5] = i
                    teile[i][6] += teile[j][0]
                    break
    summe = kurve = linie = linie_pt = 0.0
    for t in teile:
        a, richtung, _, krumm, punkte, eltern, kinder = t
        if verschachtelt:
            tiefe, windung, e = 0, richtung, eltern
            while e >= 0:
                tiefe += 1
                windung += teile[e][1]
                e = teile[e][5]
            if (tiefe % 2 == 1) if gerade_ungerade else (windung == 0):
                continue
            a = max(0.0, a - kinder)
        summe += a
        if krumm:
            kurve += a
        elif len(punkte) == 4 and eltern < 0 and not kinder:
            s1 = math.dist(punkte[0], punkte[1])
            s2 = math.dist(punkte[1], punkte[2])
            if min(s1, s2) <= LINIE_MAX_DICKE < max(s1, s2):
                linie += a
                linie_pt += max(s1, s2)
    return summe, kurve, linie, linie_pt, box


_FUELL = re.compile(r"(.)\1{2,}", re.S)
_ADRESSE = re.compile(r"(?i)^(?:(?:mailto:)?[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)*\.?|(?:https?://|www\.)\S+|"
                      r"[\w\-]+(?:\.[\w\-]+)*\.(?:ch|com|org|net|de|li|swiss|info|eu)(?:/\S*)?)[.,;:)]?$")
_KLEBT_VORN = tuple(".@/-_#?=&%")
_KLEBT_HINTEN = tuple(".@/-_=&")
_ANFANG = frozenset("h ht htt http https http: https: w ww www".split())
_TEIL = re.compile(r"^[a-z0-9._\-]+$")
_PFAD = re.compile(r"(?i)^(?:https?://|www\.)[^/]+/\S*$")
_URL_TEIL = re.compile(r"^[A-Za-z0-9._~%/?=&#\-]+$")


def _nur_adressen(stuecke):
    """Share of the characters in these pieces of text (in reading order) that
    belong to an internet or e-mail address. An address that the PDF shows in
    several pieces («name.amt» «@sh.» «ch») is put together first."""
    worte = []
    for st in stuecke:
        vor = worte[-1] if worte else ""
        if st.lower() in _ANFANG:                                              # a new link begins
            worte.append(st)
        elif vor and (st.startswith(_KLEBT_VORN) or vor.endswith(_KLEBT_HINTEN)
                      or vor.lower() in _ANFANG                                # «htt» «p://…»
                      or ("@" in st and _TEIL.match(vor) and not _ADRESSE.match(vor))     # «name.a» «mt@sh.ch»
                      or ("@" in vor and "." not in vor.split("@")[-1] and st.isalpha())  # «name@sh» «ch»
                      or (_PFAD.match(vor) and _URL_TEIL.match(st))):          # a long link in several pieces
            worte[-1] += st
        else:
            worte.append(st)
    gesamt = sum(len(w) for w in worte)
    return sum(len(w) for w in worte if _ADRESSE.match(w)) / float(gesamt) if gesamt else 0.0


def _fuell_weg(m):
    """A run of three or more equal characters that are punctuation, a
    mathematical or modifier symbol or a control character is a writing line
    or a leader («______», «.......», «………»), not text."""
    kat = unicodedata.category(m.group(1))
    return "" if kat[0] == "P" or kat in ("Sm", "Sk", "Cc") else m.group(0)


def zaehlbar(text):
    """The characters of a text that are counted: without white space and
    without leaders. len(zaehlbar(text)) is «the number of characters»."""
    kompakt = "".join((text or "").split())
    return _FUELL.sub(_fuell_weg, kompakt) if len(kompakt) > 2 else kompakt


_LEER = frozenset((0x20,))
_BF_ZEICHEN = re.compile(rb"<([0-9A-Fa-f]{2,8})>\s*<([0-9A-Fa-f]{4,})>")
_BF_BEREICH = re.compile(rb"<([0-9A-Fa-f]{2,8})>\s*<([0-9A-Fa-f]{2,8})>\s*<([0-9A-Fa-f]{4})>")
_BLANK = frozenset((0x20, 0xA0, 0x09, 0x2002, 0x2003, 0x2009, 0x202F, 0x3000))


def _leere_codes(cmap):
    """The character codes that a ToUnicode CMap maps to a blank: a font may
    show its spaces as glyphs of their own (code 3 in an Identity-H font)."""
    codes = set()
    for teil in re.findall(rb"beginbfchar(.*?)endbfchar", cmap, re.S):
        for code, ziel in _BF_ZEICHEN.findall(teil):
            if len(ziel) == 4 and int(ziel, 16) in _BLANK:
                codes.add(int(code, 16))
    for teil in re.findall(rb"beginbfrange(.*?)endbfrange", cmap, re.S):
        for von, bis, ziel in _BF_BEREICH.findall(teil):
            a, b, z0 = int(von, 16), int(bis, 16), int(ziel, 16)
            if b - a < 4096:
                codes.update(c for c in range(a, b + 1) if z0 + c - a in _BLANK)
    return frozenset(codes)


def _strichel(muster):
    """The share of a stroked line that a dash pattern paints: [3 2] -> 0.6, [4] -> 0.5, [] -> 1."""
    try:
        werte = [abs(float(x)) for x in (muster or [])]
    except Exception:
        return 1.0
    if not werte or sum(werte) <= 0:
        return 1.0
    if len(werte) % 2:
        werte = werte * 2
    return sum(werte[0::2]) / sum(werte)


class _Zustand:
    """The part of the graphics state this measurement needs."""
    __slots__ = ("ctm", "fuell", "strich", "fuell_cs", "strich_cs", "fa", "sa", "lw", "font", "size", "tr", "clip",
                 "strichel")

    def __init__(self):
        self.ctm = _EINS
        self.fuell = (0.0, 0.0, 0.0)
        self.strich = (0.0, 0.0, 0.0)
        self.fuell_cs = _CS_G
        self.strich_cs = _CS_G
        self.fa = 1.0
        self.sa = 1.0
        self.lw = 1.0
        self.font = None
        self.size = 0.0
        self.tr = 0
        self.clip = None            # bounding box of the clipping path; None = the page
        self.strichel = 1.0         # share of a stroked line that the dash pattern paints

    def kopie(self):
        z = _Zustand.__new__(_Zustand)
        for s in _Zustand.__slots__:
            setattr(z, s, getattr(self, s))
        return z


def _schluessel(farbe, alpha):
    """A colour as it is seen: (r, g, b) ints 0..255, a constant opacity mixed
    with white. A str (reason) or None passes through."""
    if not isinstance(farbe, tuple):
        return farbe
    if alpha < 1.0:
        a = _c(alpha)
        farbe = tuple(1.0 - a * (1.0 - c) for c in farbe)
    return (int(round(farbe[0] * 255)), int(round(farbe[1] * 255)), int(round(farbe[2] * 255)))


class _Lauf:
    """Graphics state and counters of one document; fed by the hooks of
    page.extract_text(), page after page."""

    def __init__(self, leser):
        self.leser = leser
        # document totals
        self.fonts = {}                         # key -> info dict
        self.font_zeichen = defaultdict(float)
        self.font_symbol = defaultdict(float)   # characters of Unicode category So
        self.groessen = defaultdict(float)      # pt (0.5 steps) -> characters
        self.farbe_text = defaultdict(float)    # (r, g, b) -> characters
        self.farbe_tinte = defaultdict(float)   # (r, g, b) -> pt² of ink of these characters (TINTE × size²)
        self.farbe_flaeche = defaultdict(float)  # -> pt² filled
        self.farbe_linie = defaultdict(float)    # -> pt² of lines (stroked, or thin filled rectangles)
        self.farbe_linie_pt = defaultdict(float)  # -> pt length of these lines
        self.farbe_kurve = defaultdict(float)    # -> pt² that are bounding boxes of curved shapes
        self.farbe_sonder = defaultdict(set)     # (r, g, b) -> names of spot colours
        self.farbe_stuecke = defaultdict(list)   # (r, g, b) -> (number, piece of text, under a link) set in it (non-neutral, capped)
        self.farbe_ort = {}                      # (r, g, b) -> {page: bounding box of what it fills and strokes}
        self.seite1 = None                       # (box, /Rotate) of the first page, for the head mark
        self.links = ()                          # boxes of the link annotations of the current page
        self.striche = ()                        # boxes of its strike-out markings
        self.gestrichen = 0                      # characters under a strike-out marking
        self.farbe_cmyk = set()                  # colours that were given as process colours
        self.fuell = 0                          # leader characters (not counted anywhere else)
        self.folge = 0                          # running number of the booked pieces of text
        self.zeichen = 0.0                      # visible characters of at least 1 pt
        self.unsichtbar = 0.0
        self.winzig = 0.0
        self.ohne_zustand = 0.0                 # characters without a text-showing operator before them
        self.ungelesen = defaultdict(float)     # reason -> characters or painted shapes in a colour not converted
        self.text_fremd = 0                     # glyphs shown inside XObjects pypdf does not read
        self.fehler = 0                         # operators that could not be interpreted
        self.bild_seiten = set()
        self.verlauf = False
        self.font_gezeigt = set()               # every font that shows a glyph, blanks included
        self.aus = set()                        # optional content groups that are switched off (object numbers)
        self.aus_namen = set()                  # the names of those that painted something
        self.wiederholt = 0                     # characters of text drawn a second time at the same place
        self.weg = 0.0                          # characters outside the page, cut away by clipping, or on a hidden layer
        self._gezeigt = set()
        self._cs_cache = {}
        self.seite = 0
        self.box = (0.0, 0.0, 595.0, 842.0)
        self._neu()

    # ---- per page
    def _neu(self):
        self.z = _Zustand()
        self.stapel = []
        self.boden = 0
        self.res = []
        self.do = []
        self.tm = 1.0
        self.tlm = _EINS            # text line matrix (Tm, Td, TD, T*): where a line of text starts
        self.tl = 0.0               # text leading
        self.tfolge = 0             # text-showing operators since the line matrix last moved
        self.pfad = []
        self.offen = []
        self.gehalten = []
        self.zuletzt = "after"
        self.letzter = None
        self.fremd = 0
        self.clip_wartet = False
        self.mc = []                # marked-content stack: True where the content belongs to a hidden layer
        self.versteckt = 0
        self._gezeigt = set()       # (text, place, font, size) of the text-showing operators of this page
        self.text_weg = []          # the pieces of text of this page that are not shown at all …
        self.text_da = []           # … and those that are (visible, or the text layer of a scan)
        self.text_gestrichen = []   # the pieces of text of this page under a strike-out marking

    def seite_beginnen(self, nr, seite, box, einheit):
        """Reset the state for a page. False when the page has no resources:
        pypdf then does not read it at all, and seite_selbst() has to."""
        self._neu()
        self.seite = nr
        self.box = box
        if einheit != 1.0:
            self.z.ctm = (einheit, 0.0, 0.0, einheit, 0.0, 0.0)
        knoten, res = seite, None
        for _ in range(32):                         # /Resources may be inherited from the page tree
            if not isinstance(knoten, dict):
                break
            res = _o(knoten.get("/Resources"))
            if res is not None:
                break
            knoten = _o(knoten.get("/Parent"))
        self.res = [res if isinstance(res, dict) else {}]
        return bool(self.res[0])

    def seite_selbst(self, seite):
        """Walk a page that pypdf skips (no resources): colours and images only."""
        from pypdf.generic import ContentStream
        inhalt = seite.get_contents()
        if inhalt is None:
            return
        self.fremd += 1
        try:
            for operanden, op in ContentStream(inhalt, self.leser, "bytes").operations:
                try:
                    self._op(op, operanden)
                except Exception:
                    self.fehler += 1
        finally:
            self.fremd -= 1

    def seite_beenden(self):
        self._buchen_alle()
        self.offen = []

    # ---- hooks
    def vor(self, op, operanden, cm, tm):
        try:
            if self.gehalten:
                self._buchen_alle()
        except Exception:
            self.fehler += 1
        self.zuletzt = "before"
        try:
            self._op(op, operanden)
        except Exception:
            self.fehler += 1

    def nach(self, op, operanden, cm, tm):
        try:
            if op == b"Do":
                # pypdf hands the whole text of a Form XObject to the visitor a second
                # time, as the last call before this hook: drop that repetition
                if self.gehalten and self.zuletzt == "after":
                    self.gehalten.pop()
                self._buchen_alle()
                self._do_ende()
            elif self.gehalten:
                self._buchen_alle()
        except Exception:
            self.fehler += 1
        self.zuletzt = "after"

    def text(self, text, cm, tm, font, groesse):
        if text:
            self.gehalten.append(text)

    # ---- booking of characters
    def _buchen_alle(self):
        gehalten, self.gehalten = self.gehalten, []
        for t in gehalten:
            self._buchen(t)

    def _buchen(self, text):
        """Book one piece of decoded text on the text-showing operators that
        produced it: in their order, each takes as many characters as it showed
        glyphs (in proportion, when the two counts differ)."""
        kompakt = "".join(text.split())
        n = len(kompakt)
        offen, self.offen = self.offen, []
        if not n:
            return
        if not offen:
            if self.letzter is None:
                self.ohne_zustand += n
                return
            offen = [[self.letzter, n]]
        gewicht = sum(w for _, w in offen)
        pos = summe = 0
        for i, (zustand, w) in enumerate(offen):
            summe += w
            if i == len(offen) - 1:
                ende = n
            elif gewicht == n:
                ende = summe
            elif gewicht:
                ende = int(round(n * summe / float(gewicht)))
            else:
                ende = int(round(n * (i + 1.0) / len(offen)))
            ende = max(pos, min(n, ende))
            if ende > pos:
                self._zaehlen(zustand, kompakt[pos:ende])
            pos = ende

    def _zaehlen(self, zustand, stueck):
        font, pt, farbe, sichtbar, marke = zustand
        kern = zaehlbar(stueck)
        z = len(kern)
        self.fuell += len(stueck) - z
        if not z:
            return
        if sichtbar is None:                    # drawn a second time at the same place
            self.wiederholt += z
            return
        if sichtbar == "weg":                   # outside the page, clipped away, or on a hidden layer
            self.weg += z
            self.text_weg.append(stueck)
            return
        self.text_da.append(stueck)
        if marke & 2:                           # struck through by a marking: counted, but kept from the text detectors
            self.text_gestrichen.append(stueck)
            self.gestrichen += z
        if not sichtbar:
            self.unsichtbar += z
            return
        if pt < 1.0:
            self.winzig += z
            return
        self.zeichen += z
        self.font_zeichen[font] += z
        self.font_symbol[font] += sum(1 for ch in kern if unicodedata.category(ch) == "So")
        self.groessen[pt] += z
        if isinstance(farbe, tuple):
            self.farbe_text[farbe] += z
            self.farbe_tinte[farbe] += z * pt * pt * TINTE
            if self.farbe_text[farbe] <= 3000 and not ist_neutral(farbe):
                self.farbe_stuecke[farbe].append((self.folge, kern, bool(marke & 1)))
            self.folge += 1
        elif farbe is not None:
            self.ungelesen[farbe] += z

    def _zeigen(self, teile):
        z = self.z
        info = self.fonts.get(z.font)
        breit = bool(info and info["typ0"])
        leer = info["leer"] if info else _LEER
        w, roh = 0, []
        for s in teile:
            if isinstance(s, bytes):
                roh.append(s)
                if breit:                       # two-byte codes; the font's ToUnicode table says which are blanks
                    w += sum(1 for i in range(0, len(s) - 1, 2) if (s[i] << 8 | s[i + 1]) not in leer)
                else:
                    w += sum(1 for b in s if b not in leer)
            elif isinstance(s, str):
                roh.append(s.encode("utf-8", "replace"))
                w += len(s) - s.count(" ")
        if self.fremd:
            self.text_fremd += w
            return
        if z.font is not None:
            self.font_gezeigt.add(z.font)
        pt = abs(z.size) * self.tm * _massstab(z.ctm)
        pt = round(pt * 2) / 2.0 if pt >= 1.0 else 0.0
        # where the line of text starts, in page coordinates
        stelle = _mult(self.tlm, z.ctm)
        weg = bool(self.versteckt)
        rand = max(pt, 2.0)
        for kasten in (self.box, z.clip):       # the page, and the bounding box of the clipping path
            if not weg and kasten is not None and (
                    kasten[2] - kasten[0] < 0.5 or kasten[3] - kasten[1] < 0.5 or
                    not (kasten[0] - rand <= stelle[4] <= kasten[2] + rand and
                         kasten[1] - rand <= stelle[5] <= kasten[3] + rand)):
                weg = True                      # outside the page, or cut away by the clipping path
        sichtbar = not weg and z.tr not in (3, 7)
        # what lies over the text: a link (1), a strike-out marking (2). The start of the text is exact for
        # the first text-showing operator after the line matrix moved; later ones stand somewhere to its right.
        marke = 0
        if not weg and (self.links or self.striche):
            genau = self.tfolge == 0
            if self._unter(self.links, stelle[4], stelle[5], genau, True):
                marke |= 1
            if genau and self._unter(self.striche, stelle[4], stelle[5], True, False):
                marke |= 2
        # the same string, shown again at the same place in the same font: one visible text, counted once
        ort = (tuple(round(v, 1) for v in stelle), self.tfolge, b"\x00".join(roh), z.font, pt)
        self.tfolge += 1
        doppelt = sichtbar and w > 0 and ort in self._gezeigt
        if sichtbar:
            self._gezeigt.add(ort)
        if doppelt:
            zustand = (z.font, pt, None, None, 0)
        elif weg:
            zustand = (z.font, pt, None, "weg", 0)
        elif not sichtbar:
            zustand = (z.font, pt, None, False, marke & 2)
        elif z.tr in (1, 5):
            zustand = (z.font, pt, _schluessel(z.strich, z.sa), True, marke)
        else:
            zustand = (z.font, pt, _schluessel(z.fuell, z.fa), True, marke)
        if self.offen and self.offen[-1][0] == zustand:
            self.offen[-1][1] += w
        else:
            self.offen.append([zustand, w])
        self.letzter = zustand

    @staticmethod
    def _unter(kaesten, x, y, genau, rechts_offen):
        """Does text whose line starts at (x, y) stand under one of these boxes? genau: (x, y) is where the
        text itself starts. Otherwise only its line is known, and the text stands to the right of (x, y): it
        counts when the box reaches further right than that start (rechts_offen)."""
        for x0, y0, x1, y1 in kaesten:
            if y0 - 2.0 <= y <= y1 + 1.0 and (x0 - 2.0 <= x < x1 if genau else rechts_offen and x < x1):
                return True
        return False

    # ---- fonts
    def _font(self, name):
        res = self.res[-1] if self.res else {}
        try:
            fonts = _o(res.get("/Font")) or {}
            roh = fonts.raw_get(name) if hasattr(fonts, "raw_get") else fonts[name]
        except Exception:
            return None
        idnum = getattr(roh, "idnum", None)
        fd = _o(roh)
        key = ("i", idnum, getattr(roh, "generation", 0)) if idnum is not None else ("d", id(fd))
        if key not in self.fonts:
            self.fonts[key] = self._font_info(fd)
            self.fonts[key]["_halt"] = fd          # keeps id() unique while the document is measured
        return key

    def _font_info(self, fd):
        info = {"name": None, "typ0": False, "eingebettet": None, "standard": False, "type3": False,
                "aus_programm": False, "leer": _LEER}
        if not isinstance(fd, dict):
            return info
        try:
            if "/ToUnicode" in fd:
                info["leer"] = _LEER | _leere_codes(_o(fd["/ToUnicode"]).get_data())
        except Exception:
            pass
        art = str(fd.get("/Subtype"))
        basis = _text(fd.get("/BaseFont")) if "/BaseFont" in fd else None
        beschr = _o(fd.get("/FontDescriptor"))
        if art == "/Type0":
            info["typ0"] = True
            try:
                kind = _o(_o(fd["/DescendantFonts"])[0])
                beschr = _o(kind.get("/FontDescriptor"))
                basis = basis or _text(kind.get("/BaseFont"))
            except Exception:
                beschr = None
        if art == "/Type3":
            info["type3"] = True
            info["eingebettet"] = True
            basis = basis or _text(fd.get("/Name"))
            if isinstance(beschr, dict):
                basis = basis or _text(beschr.get("/FontName"))
        elif isinstance(beschr, dict):
            info["eingebettet"] = any(k in beschr for k in ("/FontFile", "/FontFile2", "/FontFile3"))
            basis = basis or _text(beschr.get("/FontName"))
        else:
            info["eingebettet"] = False
        name = _ohne_praefix(basis)
        info["standard"] = name in _STANDARD14
        if (not name or _PLATZHALTER.match(name)) and isinstance(beschr, dict) and "/FontFile2" in beschr:
            try:
                eigen = _name_aus_programm(_o(beschr["/FontFile2"]).get_data())
            except Exception:
                eigen = None
            if eigen and schriftfamilie(eigen)[0]:
                name, info["aus_programm"] = eigen, True
        info["name"] = name or None
        return info

    # ---- colours
    def _cs(self, name):
        s = str(name)
        if s in _GERAET:
            return _GERAET[s]
        res = self.res[-1] if self.res else {}
        key = (id(res), s)
        if key not in self._cs_cache:
            try:
                self._cs_cache[key] = (_cs_lesen(_o(res["/ColorSpace"])[name]), res)
            except Exception:
                self._cs_cache[key] = (("x", "unbekannter Farbraum"), res)
        return self._cs_cache[key][0]

    def _farbe(self, cs, komp):
        spur = []
        rgb = _umrechnen(cs, komp, spur)
        if spur and isinstance(rgb, tuple):
            key = _schluessel(rgb, 1.0)
            for wie in spur:
                if wie == "cmyk":
                    self.farbe_cmyk.add(key)
                else:
                    self.farbe_sonder[key].add(wie)
        return rgb

    # ---- paths
    def _punkt(self, x, y):
        m = self.z.ctm
        return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])

    def _beschneiden(self, pfad):
        """W / W*: the clipping path becomes its intersection with this path — kept
        as a bounding box, the tightest frame this measurement knows."""
        self.clip_wartet = False
        xs = [p[0] for teil in pfad for p in teil[0]]
        ys = [p[1] for teil in pfad for p in teil[0]]
        if xs:
            b = self.z.clip or self.box
            self.z.clip = (max(b[0], min(xs)), max(b[1], min(ys)), min(b[2], max(xs)), min(b[3], max(ys)))

    def _ebene_aus(self, name):
        """Is the optional content this property-list entry names switched off?"""
        res = self.res[-1] if self.res else {}
        try:
            eigenschaften = _o(res["/Properties"])
            roh = eigenschaften.raw_get(name) if hasattr(eigenschaften, "raw_get") else eigenschaften[name]
        except Exception:
            return False
        return self._gruppe_aus(roh)

    def _gruppe_aus(self, roh):
        """An optional content group that is off, or a membership dictionary whose groups all are."""
        d = _o(roh)
        if not isinstance(d, dict):
            return False
        if d.get("/Type") == "/OCMD":
            glieder = _o(d.get("/OCGs"))
            glieder = glieder if isinstance(glieder, list) else [d.raw_get("/OCGs")] if "/OCGs" in d else []
            alle = [getattr(g, "idnum", None) in self.aus for g in glieder]
            aus = bool(alle) and (any(alle) if str(d.get("/P", "/AnyOn")) == "/AllOn" else all(alle))
            namen = [_text(_o(g).get("/Name")) for g in glieder if getattr(g, "idnum", None) in self.aus]
        else:
            aus = getattr(roh, "idnum", None) in self.aus
            namen = [_text(d.get("/Name"))]
        if aus:
            self.aus_namen.update(n for n in namen if n)
        return aus

    def _malen(self, fuellen, streichen, gerade_ungerade=False):
        pfad, self.pfad = self.pfad, []
        if not pfad:
            self.clip_wartet = False
            return
        if self.versteckt:                      # a layer that is switched off paints nothing
            if self.clip_wartet:
                self._beschneiden(pfad)
            return
        z = self.z
        b = z.clip or self.box
        if fuellen:
            farbe = _schluessel(z.fuell, z.fa)
            if farbe is not None:
                summe, kurve, linie, linie_pt, rahmen = _pfad_flaeche(pfad, gerade_ungerade)
                if rahmen:
                    dach = (max(0.0, min(rahmen[2], b[2]) - max(rahmen[0], b[0])) *
                            max(0.0, min(rahmen[3], b[3]) - max(rahmen[1], b[1])))
                    if summe > dach:
                        faktor = dach / summe if summe else 0.0
                        summe, kurve, linie = dach, kurve * faktor, linie * faktor
                    if isinstance(farbe, tuple):
                        if summe > 0:
                            self.farbe_flaeche[farbe] += summe - linie
                            self.farbe_linie[farbe] += linie
                            self.farbe_linie_pt[farbe] += linie_pt
                            self.farbe_kurve[farbe] += kurve
                            self._ort(farbe, max(rahmen[0], b[0]), max(rahmen[1], b[1]),
                                      min(rahmen[2], b[2]), min(rahmen[3], b[3]))
                    elif summe > 0:
                        self.ungelesen[farbe] += 1
        if streichen:
            farbe = _schluessel(z.strich, z.sa)
            if farbe is not None:
                laenge, kasten = 0.0, None
                for punkte, _, zu in pfad:
                    xs, ys = [q[0] for q in punkte], [q[1] for q in punkte]
                    if max(xs) < b[0] or min(xs) > b[2] or max(ys) < b[1] or min(ys) > b[3]:
                        continue                        # wholly outside the page or the clipping path
                    for i in range(len(punkte) - 1):
                        laenge += math.dist(punkte[i], punkte[i + 1])
                    if zu and len(punkte) > 2:
                        laenge += math.dist(punkte[-1], punkte[0])
                    k = (max(min(xs), b[0]), max(min(ys), b[1]), min(max(xs), b[2]), min(max(ys), b[3]))
                    kasten = k if kasten is None else (min(kasten[0], k[0]), min(kasten[1], k[1]),
                                                       max(kasten[2], k[2]), max(kasten[3], k[3]))
                if laenge > 0:
                    if isinstance(farbe, tuple):
                        # a dashed line paints only the share of its length that the dash pattern is «on»
                        self.farbe_linie[farbe] += (laenge * z.strichel
                                                    * max(z.lw * _massstab(z.ctm), MIN_LINIE_DICKE))
                        self.farbe_linie_pt[farbe] += laenge
                        self._ort(farbe, *kasten)
                    else:
                        self.ungelesen[farbe] += 1
        if self.clip_wartet:
            self._beschneiden(pfad)

    def _ort(self, farbe, x0, y0, x1, y1):
        """Remember where a colour paints: per page, the bounding box of everything it fills and strokes."""
        if x1 < x0 or y1 < y0:
            return
        je_seite = self.farbe_ort.setdefault(farbe, {})
        o = je_seite.get(self.seite)
        if o is None:
            je_seite[self.seite] = [x0, y0, x1, y1]
        else:
            o[0], o[1], o[2], o[3] = min(o[0], x0), min(o[1], y0), max(o[2], x1), max(o[3], y1)

    # ---- XObjects
    def _do(self, name, eigen=False):
        res = self.res[-1] if self.res else {}
        try:
            xo = _o(_o(res["/XObject"])[name])
        except Exception:
            xo = None
        if not isinstance(xo, dict):
            return None
        art = xo.get("/Subtype")
        aus = False
        try:
            aus = bool(self.aus) and "/OC" in xo and self._gruppe_aus(xo.raw_get("/OC"))
        except Exception:
            pass
        if art == "/Image":
            if not (aus or self.versteckt):
                self.bild_seiten.add(self.seite)
            return None
        if art != "/Form":
            return None
        rahmen = (self.z.kopie(), len(self.stapel), self.boden, len(self.res), self.tm, self.versteckt, len(self.mc),
                  self.tlm, self.tl, self.tfolge)
        self.versteckt += aus
        try:
            self.z.ctm = _mult(tuple(_zahlen(_o(xo["/Matrix"]), 6)), self.z.ctm) if "/Matrix" in xo else self.z.ctm
        except Exception:
            pass
        try:
            x0, y0, x1, y1 = _zahlen(_o(xo["/BBox"]), 4)
            ecken = [self._punkt(x0, y0), self._punkt(x1, y0), self._punkt(x1, y1), self._punkt(x0, y1)]
            self._beschneiden([[ecken, False, True]])
        except Exception:
            pass
        self.boden = len(self.stapel)
        eigene = _o(xo.get("/Resources"))
        if eigen or not eigene:
            # pypdf does not read a Form XObject without resources of its own:
            # walk it here for its colours (its text cannot be decoded)
            if len(self.do) + self.fremd < 12:
                self.res.append(eigene or res)
                self.fremd += 1
                try:
                    from pypdf.generic import ContentStream
                    for operanden, op in ContentStream(xo, self.leser, "bytes").operations:
                        try:
                            self._op(op, operanden)
                        except Exception:
                            self.fehler += 1
                except Exception:
                    self.fehler += 1
                self.fremd -= 1
            self._zurueck(rahmen)
            return None
        self.res.append(eigene)
        return rahmen

    def _zurueck(self, rahmen):
        self.z, tiefe, self.boden, n_res, self.tm, self.versteckt, n_mc, self.tlm, self.tl, self.tfolge = rahmen
        del self.stapel[tiefe:]
        del self.res[n_res:]
        del self.mc[n_mc:]
        self.pfad = []

    def _do_ende(self):
        rahmen = self.do.pop() if self.do else None
        if rahmen is not None:
            self._zurueck(rahmen)

    # ---- one operator
    def _op(self, op, a):
        z = self.z
        if op == b"re":
            x, y, w, h = _zahlen(a, 4)
            self.pfad.append([[self._punkt(x, y), self._punkt(x + w, y), self._punkt(x + w, y + h),
                               self._punkt(x, y + h)], False, True])
        elif op == b"m":
            self.pfad.append([[self._punkt(float(a[0]), float(a[1]))], False, False])
        elif op == b"l":
            if self.pfad:
                self.pfad[-1][0].append(self._punkt(float(a[0]), float(a[1])))
        elif op in (b"c", b"v", b"y"):
            if self.pfad and self.pfad[-1][0]:
                punkte = self.pfad[-1][0]
                p0 = punkte[-1]
                if op == b"c":
                    x1, y1, x2, y2, x3, y3 = _zahlen(a, 6)
                    p1, p2, p3 = self._punkt(x1, y1), self._punkt(x2, y2), self._punkt(x3, y3)
                elif op == b"v":
                    x2, y2, x3, y3 = _zahlen(a, 4)
                    p1, p2, p3 = p0, self._punkt(x2, y2), self._punkt(x3, y3)
                else:
                    x1, y1, x3, y3 = _zahlen(a, 4)
                    p1 = self._punkt(x1, y1)
                    p2 = p3 = self._punkt(x3, y3)
                for t, u in _KURVE:                     # the Bézier curve as a polyline
                    k0, k1, k2, k3 = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
                    punkte.append((k0 * p0[0] + k1 * p1[0] + k2 * p2[0] + k3 * p3[0],
                                   k0 * p0[1] + k1 * p1[1] + k2 * p2[1] + k3 * p3[1]))
                self.pfad[-1][1] = True
        elif op == b"h":
            if self.pfad:
                self.pfad[-1][2] = True
        elif op in (b"f", b"F", b"f*"):
            self._malen(True, False, op == b"f*")
        elif op in (b"B", b"B*"):
            self._malen(True, True, op == b"B*")
        elif op in (b"b", b"b*"):
            if self.pfad:
                self.pfad[-1][2] = True
            self._malen(True, True, op == b"b*")
        elif op == b"S":
            self._malen(False, True)
        elif op == b"s":
            if self.pfad:
                self.pfad[-1][2] = True
            self._malen(False, True)
        elif op == b"n":
            if self.clip_wartet:
                self._beschneiden(self.pfad)
            self.pfad = []
        elif op in (b"W", b"W*"):
            self.clip_wartet = True
        elif op == b"q":
            self.stapel.append(z.kopie())
        elif op == b"Q":
            if len(self.stapel) > self.boden:
                self.z = self.stapel.pop()
        elif op == b"cm":
            z.ctm = _mult(tuple(_zahlen(a, 6)), z.ctm)
        elif op == b"w":
            z.lw = abs(float(a[0]))
        elif op == b"d":
            z.strichel = _strichel(_o(a[0]) if a else None)
        elif op == b"g":
            z.fuell_cs, z.fuell = _CS_G, _umrechnen(_CS_G, _zahlen(a, 1))
        elif op == b"G":
            z.strich_cs, z.strich = _CS_G, _umrechnen(_CS_G, _zahlen(a, 1))
        elif op == b"rg":
            z.fuell_cs, z.fuell = _CS_RGB, _umrechnen(_CS_RGB, _zahlen(a, 3))
        elif op == b"RG":
            z.strich_cs, z.strich = _CS_RGB, _umrechnen(_CS_RGB, _zahlen(a, 3))
        elif op == b"k":
            z.fuell_cs, z.fuell = _CS_CMYK, self._farbe(_CS_CMYK, _zahlen(a, 4))
        elif op == b"K":
            z.strich_cs, z.strich = _CS_CMYK, self._farbe(_CS_CMYK, _zahlen(a, 4))
        elif op == b"cs":
            z.fuell_cs = self._cs(a[0])
            z.fuell = self._farbe(z.fuell_cs, _cs_anfang(z.fuell_cs))
        elif op == b"CS":
            z.strich_cs = self._cs(a[0])
            z.strich = self._farbe(z.strich_cs, _cs_anfang(z.strich_cs))
        elif op in (b"sc", b"scn"):
            z.fuell = self._farbe(z.fuell_cs, [float(x) for x in a if not isinstance(x, str)])
        elif op in (b"SC", b"SCN"):
            z.strich = self._farbe(z.strich_cs, [float(x) for x in a if not isinstance(x, str)])
        elif op == b"BT":
            self.tm, self.tlm, self.tfolge = 1.0, _EINS, 0
        elif op == b"Tm":
            self.tlm, self.tfolge = tuple(_zahlen(a, 6)), 0
            self.tm = _massstab(self.tlm)
        elif op in (b"Td", b"TD"):
            tx, ty = _zahlen(a, 2)
            self.tlm, self.tfolge = _mult((1.0, 0.0, 0.0, 1.0, tx, ty), self.tlm), 0
            if op == b"TD":
                self.tl = -ty
        elif op == b"TL":
            self.tl = float(a[0])
        elif op == b"T*":
            self.tlm, self.tfolge = _mult((1.0, 0.0, 0.0, 1.0, 0.0, -self.tl), self.tlm), 0
        elif op == b"Tf":
            z.font = self._font(a[0])
            z.size = float(a[1])
        elif op == b"Tr":
            z.tr = int(a[0])
        elif op == b"Tj":
            self._zeigen(a[:1])
        elif op in (b"'", b'"'):                  # move to the next line, then show
            self.tlm, self.tfolge = _mult((1.0, 0.0, 0.0, 1.0, 0.0, -self.tl), self.tlm), 0
            self._zeigen(a[:1] if op == b"'" else a[2:3])
        elif op == b"TJ":
            self._zeigen(a[0] if a else ())
        elif op == b"Do":
            rahmen = None
            try:
                rahmen = self._do(a[0], eigen=bool(self.fremd))
            finally:
                if not self.fremd:
                    self.do.append(rahmen)     # one entry per Do, whatever happened: nach() takes it off
        elif op == b"gs":
            d = _o(_o(self.res[-1]["/ExtGState"])[a[0]])
            if "/ca" in d:
                z.fa = float(d["/ca"])
            if "/CA" in d:
                z.sa = float(d["/CA"])
            if "/LW" in d:
                z.lw = abs(float(d["/LW"]))
            if "/D" in d:
                z.strichel = _strichel(_o(_o(d["/D"])[0]))
            if "/Font" in d:
                eintrag = _o(d["/Font"])
                roh = eintrag[0]
                fd = _o(roh)
                idnum = getattr(roh, "idnum", None)
                key = ("i", idnum, getattr(roh, "generation", 0)) if idnum is not None else ("d", id(fd))
                if key not in self.fonts:
                    self.fonts[key] = self._font_info(fd)
                    self.fonts[key]["_halt"] = fd
                z.font, z.size = key, float(eintrag[1])
        elif op == b"sh":
            if not self.versteckt:
                self.verlauf = True
        elif op == b"INLINE IMAGE":
            if not self.versteckt:
                self.bild_seiten.add(self.seite)
        elif op == b"BDC":
            aus = False
            if len(a) > 1 and str(a[0]) == "/OC" and self.aus:
                aus = self._ebene_aus(a[1])
            self.mc.append(aus)
            self.versteckt += aus
        elif op == b"BMC":
            self.mc.append(False)
        elif op == b"EMC":
            if self.mc:
                self.versteckt -= self.mc.pop()


# ============================================================== document facts

# a tooltip that Acrobat's automatic field recognition left behind is no accessible name
_TU_PLATZHALTER = re.compile(r"(?i)^(?:undefined|null|[\d\s\[\](){}<>.,;:_\-–/\\#*|]+|"
                             r"(?:text ?field|textfeld|field|feld|check ?box|kontrollkästchen)[ _]?\d*)$")


def _felder(katalog):
    """The terminal AcroForm fields: {"felder": those that take input,
    "beschriftet": of them with a /TU that names the field, "platzhalter": of
    them with a /TU that is only a placeholder («3», «[1]», «undefined»),
    "schaltflaechen": push buttons (not counted as fields), "knoten": the ids
    of the fields and their widgets, "werte": the pre-filled values of text
    fields}."""
    form = _o(katalog.get("/AcroForm"))
    f = {"felder": 0, "beschriftet": 0, "platzhalter": 0, "schaltflaechen": 0, "knoten": set(), "werte": []}
    if not isinstance(form, dict):
        return f
    gesehen = f["knoten"]

    def lauf(knoten, ft, ff, wert, tiefe):
        knoten = _o(knoten)
        if not isinstance(knoten, dict) or id(knoten) in gesehen or tiefe > 40:
            return
        gesehen.add(id(knoten))
        ft = knoten.get("/FT", ft)
        ff = knoten.get("/Ff", ff)
        wert = knoten.get("/V", wert)
        kinder = [_o(k) for k in (_o(knoten.get("/Kids")) or [])]
        unterfelder = [k for k in kinder if isinstance(k, dict) and "/T" in k]
        if unterfelder:
            for k in unterfelder:
                lauf(k, ft, ff, wert, tiefe + 1)
            return
        gesehen.update(id(k) for k in kinder if isinstance(k, dict))       # the widgets of this field
        if ft is None:
            return
        try:
            schalter = int(_o(ff) or 0)
        except Exception:
            schalter = 0
        if str(ft) == "/Btn" and schalter & 65536:
            f["schaltflaechen"] += 1
            return
        f["felder"] += 1
        tu = (_text(knoten.get("/TU")) or "").strip()
        if tu and _TU_PLATZHALTER.match(tu):
            f["platzhalter"] += 1
        elif tu:
            f["beschriftet"] += 1
        if str(ft) == "/Tx":
            text = _text(wert)
            if text and text.strip():
                f["werte"].append(text)

    for feld in (_o(form.get("/Fields")) or []):
        lauf(feld, None, None, None, 0)
    return f


_UEBERSCHRIFT = re.compile(r"^/H[1-6]?$")
MAX_STRUKTUR = 200000


def _struktur(katalog):
    """The structure tree in numbers: {"elemente", "form" (elements of type
    Form), "ueberschrift" (H, H1–H6), "sprache": {lang: elements that carry
    it}} — types after the /RoleMap. None when there is no tree."""
    baum = _o(katalog.get("/StructTreeRoot"))
    if not isinstance(baum, dict):
        return None
    rollen = _o(baum.get("/RoleMap"))
    rollen = rollen if isinstance(rollen, dict) else {}

    def typ(name):
        for _ in range(8):                                   # a role may be mapped more than once
            if str(name) in ("/Form",) or _UEBERSCHRIFT.match(str(name)) or name not in rollen:
                break
            name = rollen[name]
        return str(name)

    zahl = {"elemente": 0, "form": 0, "ueberschrift": 0, "sprache": defaultdict(int)}
    gesehen, stapel = set(), [baum.get("/K")]
    while stapel and zahl["elemente"] < MAX_STRUKTUR:
        k = _o(stapel.pop())
        if isinstance(k, list):
            stapel.extend(k)
            continue
        if not isinstance(k, dict) or id(k) in gesehen or "/S" not in k or k.get("/Type") in ("/MCR", "/OBJR"):
            continue
        gesehen.add(id(k))
        zahl["elemente"] += 1
        t = typ(k["/S"])
        if t == "/Form":
            zahl["form"] += 1
        elif _UEBERSCHRIFT.match(t):
            zahl["ueberschrift"] += 1
        lang = (_text(k.get("/Lang")) or "").strip()
        if lang:
            zahl["sprache"][lang] += 1
        if "/K" in k:
            stapel.append(k["/K"])
    return zahl


# the commonest words of the four languages a Formular of the canton may be written in
_SPRACHWORT = {                              # only words that none of the other three languages uses
    "de": frozenset("der das und ist nicht oder mit von für dem ein eine auf bei werden wird sind zur zum "
                    "nach durch sowie bitte dass auch aus sich als".split()),
    "fr": frozenset("les et est pas ou avec pour du une sur dans par que qui au aux ce cette sont être "
                    "vous nous".split()),
    "it": frozenset("il lo gli è con di del della una nel nella che sono essere alla dei delle".split()),
    "en": frozenset("the and not with for of that this are which you your must will".split()),
}
_SPRACHNAME = {"de": "deutsch", "fr": "französisch", "it": "italienisch", "en": "englisch"}


def textsprache(zeilen):
    """'de' | 'fr' | 'it' | 'en' for text whose commonest words belong clearly
    to one of them (at least 15 hits, three times as many as for the next
    language); None otherwise."""
    treffer = dict.fromkeys(_SPRACHWORT, 0)
    for zeile in zeilen:
        for w in re.findall(r"[^\W\d_]+", zeile.lower()):
            for sprache, worte in _SPRACHWORT.items():
                if w in worte:
                    treffer[sprache] += 1
    folge = sorted(treffer.items(), key=lambda kv: (-kv[1], kv[0]))
    return folge[0][0] if folge[0][1] >= 15 and folge[0][1] >= 3 * folge[1][1] else None


def _titel(leser, hinweise):
    """The document title, verbatim: /Title of the document information, else
    dc:title of the XMP metadata."""
    info = xmp = None
    try:
        md = leser.metadata
        if md is not None and md.get("/Title") is not None:
            info = _text(md.get("/Title"))
    except Exception:
        pass
    try:
        x = leser.xmp_metadata
        werte = x.dc_title if x is not None else None
        if werte:
            xmp = werte.get("x-default") or next(iter(werte.values()), None)
    except Exception:
        xmp = None
    info_da = bool(info and info.replace("\x00", "").strip())
    xmp_da = bool(xmp and xmp.strip())
    if info_da and xmp_da and " ".join(info.split()) != " ".join(xmp.split()):
        hinweise.append("Der Titel in den XMP-Metadaten weicht ab: «%s»." % " ".join(xmp.split())[:120])
    if info_da:
        return info
    return xmp if xmp_da else None


_KOMMENTAR = {"/Text": "Notiz", "/FreeText": "Textfeld", "/Highlight": "Hervorhebung", "/Underline": "Unterstreichung",
              "/StrikeOut": "Durchstreichung", "/Squiggly": "Unterschlängelung", "/Stamp": "Stempel", "/Ink": "Freihandlinie",
              "/Line": "Linie", "/Square": "Rechteck", "/Circle": "Ellipse", "/Polygon": "Vieleck", "/PolyLine": "Linienzug",
              "/Caret": "Einfügemarke", "/FileAttachment": "Dateianhang", "/Redact": "Schwärzung"}


def _anmerkungen(leser, seiten, boxen, feldknoten):
    """What the annotations of the pages paint — form-field widgets, comments,
    markings — measured apart from the page content, through their appearance
    streams (/AP /N; where a widget has none, through the colours it declares
    in /MK). Returns (a _Lauf with the colour counters, {kind: number} of the
    comments and markings, the number of widgets that belong to no field)."""
    from pypdf.generic import ContentStream
    anno = _Lauf(leser)
    kommentare, fremd = defaultdict(int), 0
    for nr, seite in enumerate(seiten):
        try:
            liste = _o(seite.get("/Annots")) or []
        except Exception:
            continue
        box, einheit = boxen[nr]
        for roh in liste:
            try:
                a = _o(roh)
                if not isinstance(a, dict):
                    continue
                art = str(a.get("/Subtype"))
                if int(_o(a.get("/F", 0)) or 0) & 34:          # hidden, or not shown on the screen
                    continue
                if art in ("/Link", "/Popup"):
                    continue
                if art == "/Widget":
                    fremd += id(a) not in feldknoten
                else:
                    kommentare[_KOMMENTAR.get(art, art.lstrip("/"))] += 1
                x0, y0, x1, y1 = _zahlen(_o(a["/Rect"]), 4)
                x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
                if x1 - x0 <= 0 or y1 - y0 <= 0:
                    continue
                bild = _o(a.get("/AP"))
                bild = _o(bild.get("/N")) if isinstance(bild, dict) else None
                if isinstance(bild, dict) and not hasattr(bild, "get_data"):       # one stream per state
                    bild = _o(bild.get(a["/AS"])) if "/AS" in a else None
                anno._neu()
                anno.seite, anno.box = nr, box
                rahmen = (max(box[0], x0 * einheit), max(box[1], y0 * einheit),
                          min(box[2], x1 * einheit), min(box[3], y1 * einheit))
                if hasattr(bild, "get_data"):
                    m = tuple(_zahlen(_o(bild["/Matrix"]), 6)) if "/Matrix" in bild else _EINS
                    try:
                        b0, b1, b2, b3 = _zahlen(_o(bild["/BBox"]), 4)
                    except Exception:
                        b0, b1, b2, b3 = 0.0, 0.0, x1 - x0, y1 - y0
                    ecken = [(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])
                             for x, y in ((b0, b1), (b2, b1), (b2, b3), (b0, b3))]
                    t0, t1 = min(e[0] for e in ecken), min(e[1] for e in ecken)
                    tb, th = max(e[0] for e in ecken) - t0, max(e[1] for e in ecken) - t1
                    sx, sy = ((x1 - x0) / tb if tb > 0 else 1.0), ((y1 - y0) / th if th > 0 else 1.0)
                    anno.z.ctm = _mult(_mult(m, (sx, 0.0, 0.0, sy, x0 - t0 * sx, y0 - t1 * sy)),
                                       (einheit, 0.0, 0.0, einheit, 0.0, 0.0))
                    anno.z.clip = rahmen
                    anno.res = [_o(bild.get("/Resources")) or {}]
                    anno.fremd = 1
                    for operanden, op in ContentStream(bild, leser, "bytes").operations:
                        try:
                            anno._op(op, operanden)
                        except Exception:
                            anno.fehler += 1
                elif art == "/Widget":                                              # no appearance stored: /MK
                    mk = _o(a.get("/MK"))
                    flaeche = max(0.0, rahmen[2] - rahmen[0]) * max(0.0, rahmen[3] - rahmen[1])
                    for k in ("/BG", "/BC") if isinstance(mk, dict) else ():
                        werte = [float(x) for x in (_o(mk.get(k)) or [])]
                        cs = {1: _CS_G, 3: _CS_RGB, 4: _CS_CMYK}.get(len(werte))
                        farbe = _schluessel(_umrechnen(cs, werte), 1.0) if cs else None
                        if not isinstance(farbe, tuple):
                            continue
                        if k == "/BG":
                            anno.farbe_flaeche[farbe] += flaeche
                        else:
                            try:
                                dicke = float(_o(_o(a.get("/BS")).get("/W", 1.0)))
                            except Exception:
                                dicke = 1.0
                            anno.farbe_linie[farbe] += 2 * ((x1 - x0) + (y1 - y0)) * einheit * dicke * einheit
            except Exception:
                anno.fehler += 1
    return anno, kommentare, fremd


def _anmerkungsfarben(anno, flaeche_gesamt):
    """[(hex, familie, share of the page area)] of the colours the annotations
    paint, heaviest first; a colour counts from MIN_FLAECHE_PT2."""
    je_farbe = defaultdict(float)
    for c in set(anno.farbe_flaeche) | set(anno.farbe_linie):
        voll, linie = anno.farbe_flaeche.get(c, 0.0), anno.farbe_linie.get(c, 0.0)
        if not ist_neutral(c):
            je_farbe[c] += voll + linie
        elif not ist_neutral(c, flaeche=True):
            je_farbe[c] += voll
    gruppen = []
    grenze = CLUSTER * 255 + 1e-9
    for c in sorted(je_farbe, key=lambda c: (-je_farbe[c], c)):
        for g in gruppen:
            if max(abs(c[i] - g[0][i]) for i in range(3)) <= grenze:
                g[1] += je_farbe[c]
                break
        else:
            gruppen.append([c, je_farbe[c]])
    return [(_hex(c), farbfamilie(c), (a / flaeche_gesamt if flaeche_gesamt else 0.0))
            for c, a in sorted(gruppen, key=lambda g: (-g[1], g[0])) if a >= MIN_FLAECHE_PT2]


def _leer_profil(messart, hinweise):
    return {
        "messart": messart, "seiten": None, "seitenformat": None,
        "schriften": None, "hauptschrift": None, "n_schriftfamilien": None,
        "groessen": None, "grundgroesse": None, "kleinste": None, "anteil_unter_8": None,
        "farben": None, "akzent": None, "n_farbfamilien": None, "anteil_text_farbig": None,
        "barrierefrei": {"tags": None, "sprache": None, "sprache_passt": None, "titel": None, "titel_art": None,
                         "titel_anzeige": None, "felder": None, "felder_beschriftet": None, "textebene": None,
                         "text_lesbar": None, "schriften_eingebettet": None, "ueberschriften": None},
        "telefon": None, "email": None,
        "elemente": {"stand_angabe": {"vorhanden": None, "text": None},
                     "seitenzahlen": {"vorhanden": None, "muster": None},
                     "absender": {"kanton": None, "dienststelle": None, "text": None}},
        "ausfuellbar": None, "hinweise": hinweise,
    }


def _r(x):
    return round(x + 0.0, 4)


def _liste(namen):
    namen = list(namen)
    return namen[0] if len(namen) == 1 else ", ".join(namen[:-1]) + " und " + namen[-1]


def _schriften(lauf, hinweise):
    """schriften, hauptschrift, n_schriftfamilien, schriften_eingebettet."""
    familien = {}
    for key, z in lauf.font_zeichen.items():
        if z <= 0:
            continue
        info = lauf.fonts.get(key) or {"name": None, "eingebettet": None, "standard": False, "type3": False,
                                       "aus_programm": False}
        fam, sym = schriftfamilie(info["name"]) if info["name"] else (None, False)
        f = familien.setdefault(fam or OHNE_NAME, {"z": 0.0, "so": 0.0, "symbol": False, "ein": [], "std": set(),
                                                   "fehlt": False, "prog": False})
        f["z"] += z
        f["so"] += lauf.font_symbol.get(key, 0.0)
        f["symbol"] = f["symbol"] or sym
        f["ein"].append(info["eingebettet"])
        f["prog"] = f["prog"] or info["aus_programm"]
        if info["eingebettet"] is False:
            if info["standard"]:
                f["std"].add(info["name"])
            else:
                f["fehlt"] = True
    gesamt = sum(f["z"] for f in familien.values())
    if not gesamt:
        return None, None, None, None
    liste = []
    for name, f in familien.items():
        symbol = f["symbol"] or (name != OHNE_NAME and f["so"] >= 0.999 * f["z"])
        ein = None if any(e is None for e in f["ein"]) else all(f["ein"])
        liste.append({"familie": name, "anteil": _r(f["z"] / gesamt), "eingebettet": ein, "symbol": bool(symbol)})
    liste.sort(key=lambda e: (-e["anteil"], e["familie"]))
    text = [e for e in liste if not e["symbol"]]
    unbenannt = [e for e in text if e["familie"] == OHNE_NAME]
    haupt = text[0]["familie"] if text and text[0]["familie"] != OHNE_NAME else None
    n_fam = None if any(e["anteil"] >= 0.02 for e in unbenannt) else sum(1 for e in text if e["anteil"] >= 0.02)
    if unbenannt:
        folge = ("; Hauptschrift und Zahl der Schriftfamilien sind deshalb nicht bestimmbar" if haupt is None
                 else "; die Zahl der Schriftfamilien ist deshalb nicht bestimmbar" if n_fam is None else "")
        hinweise.append(gestaltung_text.H_NAMENLOS + " (im PDF steht nur ein Platzhalter oder kein Name) tragen "
                        "%s der Zeichen%s."
                        % (_prozent(sum(e["anteil"] for e in unbenannt)), folge))
    if any(z > 0 and (lauf.fonts.get(key) or {}).get("type3") for key, z in lauf.font_zeichen.items()):
        hinweise.append("Enthält eine Type-3-Schrift; ihre Grössenangabe kann vom gedruckten Bild abweichen.")
    if any(f["prog"] for f in familien.values()):
        hinweise.append("Schriftnamen aus den eingebetteten Schriftdateien gelesen (im PDF stehen nur Platzhalter).")
    fehlt = sorted(n for n, f in familien.items() if f["fehlt"])
    standard = sorted({s for f in familien.values() for s in f["std"]})
    if fehlt:
        hinweise.append(gestaltung_text.H_NICHT_EINGEBETTET + ": %s." % _liste(fehlt))
    if standard:
        hinweise.append(gestaltung_text.H_NICHT_EINGEBETTET + ", aber PDF-Standardschrift (jedes Anzeigeprogramm "
                        "bringt sie mit): %s." % _liste(standard))
    nur_leer = set()                               # fonts that show glyphs but set no counted character
    for key in lauf.font_gezeigt:
        info = lauf.fonts.get(key) or {}
        if lauf.font_zeichen.get(key, 0) <= 0 and info.get("eingebettet") is False and not info.get("standard") \
                and info.get("name"):
            nur_leer.add(schriftfamilie(info["name"])[0] or OHNE_NAME)
    if nur_leer and not fehlt:                     # otherwise schriften_eingebettet is false anyway
        hinweise.append(gestaltung_text.H_NICHT_EINGEBETTET + ", setzt aber nur Leerzeichen und zählt deshalb "
                        "nicht: %s." % _liste(sorted(nur_leer)))
    if any(f["ein"] and any(e is None for e in f["ein"]) for f in familien.values()):
        eingebettet = None
    else:
        eingebettet = not fehlt
    return liste, haupt, n_fam, eingebettet


def _prozent(x):
    p = x * 100.0
    if 0 < p < 1:
        return "weniger als 1 %"
    return "%d %%" % int(round(p))


def _groessen(lauf):
    gesamt = sum(lauf.groessen.values())
    if not gesamt:
        return None, None, None, None
    folge = sorted(lauf.groessen.items(), key=lambda kv: (-kv[1], kv[0]))
    liste = [{"pt": pt, "anteil": _r(z / gesamt)} for pt, z in folge[:6]]
    tragend = [pt for pt, z in lauf.groessen.items() if z >= MIN_ZEICHEN_KLEINSTE]
    unter8 = sum(z for pt, z in lauf.groessen.items() if pt < 8.0) / gesamt
    return liste, folge[0][0], (min(tragend) if tragend else None), _r(unter8)


MIN_ERWAEHNT_PT2 = 10.0       # a colour below the threshold is named in hinweise from this painted area (or one character)


def _nur_kopf(lauf, gruppe, n_text):
    """Is this colour nothing but a small mark in the head of page 1 — a logo that
    is drawn, not placed as an image? It sets no text, paints on the first page
    only, and everything it paints lies in the upper KOPF_HOEHE of that page,
    within a box of at most KOPF_BREITE of its width. (A title bar across the
    page, a panel further down and a colour that returns on later pages are
    colours of the form.)"""
    if n_text or lauf.seite1 is None:
        return False
    kasten = None
    for c in gruppe:
        je_seite = lauf.farbe_ort.get(c)
        if not je_seite or set(je_seite) != {0}:
            return False
        o = je_seite[0]
        kasten = list(o) if kasten is None else [min(kasten[0], o[0]), min(kasten[1], o[1]),
                                                 max(kasten[2], o[2]), max(kasten[3], o[3])]
    (x0, y0, x1, y1), dreh = lauf.seite1
    breite, hoehe = x1 - x0, y1 - y0
    if breite <= 0 or hoehe <= 0:
        return False
    # the page as it is shown: /Rotate turns it clockwise
    if dreh == 90:
        tief, weit = (kasten[2] - x0) / breite, (kasten[3] - kasten[1]) / hoehe
    elif dreh == 180:
        tief, weit = (kasten[3] - y0) / hoehe, (kasten[2] - kasten[0]) / breite
    elif dreh == 270:
        tief, weit = (x1 - kasten[0]) / breite, (kasten[3] - kasten[1]) / hoehe
    else:
        tief, weit = (y1 - kasten[1]) / hoehe, (kasten[2] - kasten[0]) / breite
    return tief <= KOPF_HOEHE and weit <= KOPF_BREITE


def _farben(lauf, flaeche_gesamt, hinweise):
    """farben, akzent, n_farbfamilien, anteil_text_farbig."""
    zeichen = lauf.zeichen
    roh = {}                                    # colour -> (characters, ink, filled, lines, of it curved)
    for c in set(lauf.farbe_text) | set(lauf.farbe_flaeche) | set(lauf.farbe_linie):
        if not ist_neutral(c):
            roh[c] = (lauf.farbe_text.get(c, 0.0), lauf.farbe_tinte.get(c, 0.0), lauf.farbe_flaeche.get(c, 0.0),
                      lauf.farbe_linie.get(c, 0.0), lauf.farbe_kurve.get(c, 0.0))
        elif not ist_neutral(c, flaeche=True) and lauf.farbe_flaeche.get(c, 0.0) > 0:
            roh[c] = (0.0, 0.0, lauf.farbe_flaeche[c], 0.0, lauf.farbe_kurve.get(c, 0.0))     # a pale tint: as a fill only

    def gemalt(w):
        return w[1] + w[2] + w[3]

    def summe(g):
        return tuple(sum(roh[c][i] for c in g) for i in range(5))

    def zaehlt(w):
        return w[0] >= MIN_ZEICHEN_FARBE or gemalt(w) >= MIN_FLAECHE_PT2

    bunt = sorted(roh, key=lambda c: (-gemalt(roh[c]), -roh[c][0], c))
    gruppen = []
    grenze = CLUSTER * 255 + 1e-9
    for c in bunt:
        for g in gruppen:
            if max(abs(c[i] - g[0][i]) for i in range(3)) <= grenze:
                g.append(c)
                break
        else:
            gruppen.append([c])
    # a colour counts by itself, or the remaining shades of one family count together (the strips of a
    # gradient, the tints of one design colour)
    fertig, rest = [], {}
    for g in gruppen:
        if zaehlt(summe(g)):
            fertig.append(g)
        else:
            rest.setdefault(farbfamilie(g[0]), []).extend(g)
    unter = []
    for familie, g in rest.items():
        w = summe(g)
        if zaehlt(w):
            fertig.append(g)
        elif (w[0] >= 1 or gemalt(w) >= MIN_ERWAEHNT_PT2) and not any(farbfamilie(f[0]) == familie for f in fertig):
            unter.append((_hex(g[0]), familie))
    liste, kurven, sonder, cmyk = [], False, set(), False
    for g in fertig:
        n_text, tinte, voll, linie, kurve = summe(g)
        stuecke = sorted(st for c in g for st in lauf.farbe_stuecke.get(c, ()))
        # link text: nothing but addresses and text under link annotations (a linked word); its underlines
        # are lines of the same colour, lighter than its own ink
        n_st = sum(len(text) for _, text, _l in stuecke)
        frei = [text for _, text, verlinkt in stuecke if not verlinkt]
        n_frei = sum(len(text) for text in frei)
        als_link = max(_nur_adressen([text for _, text, _l in stuecke]),
                       ((n_st - n_frei) + _nur_adressen(frei) * n_frei) / float(n_st) if n_st else 0.0)
        nur_link = bool(1 <= n_text <= 3000 and voll < MIN_FLAECHE_PT2 and linie <= max(tinte, MIN_ERWAEHNT_PT2)
                        and als_link >= 0.9)
        gewicht = (tinte + voll + linie) / flaeche_gesamt if flaeche_gesamt else 0.0
        liste.append({"hex": _hex(g[0]), "familie": farbfamilie(g[0]),
                      "anteil_text": _r(n_text / zeichen) if zeichen else 0.0,
                      "anteil_flaeche": _r(min(1.0, (voll + linie) / flaeche_gesamt)) if flaeche_gesamt else 0.0,
                      "gewicht": round(min(1.0, gewicht), 5), "nur_link": nur_link, "feld": False,
                      "nur_kopf": _nur_kopf(lauf, g, n_text), "_g": gewicht})
        if kurve > 0.25 * (voll + linie) > 0:
            kurven = True
        for c in g:
            sonder |= lauf.farbe_sonder.get(c, set())
            cmyk = cmyk or c in lauf.farbe_cmyk
    liste.sort(key=lambda e: (-e["_g"], e["hex"]))
    for e in liste:
        del e["_g"]
    farbig = sum(z for c, z in lauf.farbe_text.items() if not ist_neutral(c))
    akzent, n_familien = farbwahl(liste)
    if kurven:
        hinweise.append("Farbflächen mit gekrümmtem Umriss sind angenähert (Kurven als Vieleck gerechnet).")
    if sonder:
        hinweise.append("Sonderfarbe %s über ihre Ersatzfarbe in eine Bildschirmfarbe umgerechnet."
                        % _liste(sorted(sonder)))
    if cmyk:
        hinweise.append("Druckfarben (CMYK) sind näherungsweise in Bildschirmfarben umgerechnet; der Farbton kann "
                        "vom gewohnten Bild leicht abweichen.")
    links = [e["hex"] for e in liste if e["nur_link"]]
    if links:
        hinweise.append(gestaltung_text.H_LINKFARBE % ", ".join(links))
    elif len(liste) == 1 and liste[0]["hex"] == "#0000ff":
        hinweise.append("Die einzige Farbe ist reines Blau #0000ff (nicht nur für Adressen und verlinkte Wörter "
                        "gesetzt).")
    marken = [e["hex"] for e in liste if e["nur_kopf"]]
    if marken:
        hinweise.append("Nur als kleine Farbmarke im Kopf der ersten Seite gemalt (in der Regel ein gezeichnetes "
                        "Logo) und deshalb nicht als Akzentfarbe gezählt: %s." % ", ".join(marken))
    if unter:
        hinweise.append(gestaltung_text.H_FARBE_UNTER_SCHWELLE + " (weniger als %d Zeichen und weniger als %d pt² "
                        "gemalte Fläche), nicht als Farbe des Formulars gezählt: %s."
                        % (MIN_ZEICHEN_FARBE, MIN_FLAECHE_PT2, ", ".join("%s (%s)" % u for u in sorted(unter))))
    return liste, akzent, n_familien, (_r(farbig / zeichen) if zeichen else None)


# ======================================================================= messen

def messen(path, dienststelle=None, formular=None):
    """The measured profil of one PDF Formular (see the module docstring).

    path          the PDF file
    dienststelle  the responsible Dienststelle as recorded in the databank
                  (service.dienststelle), for elemente.absender; optional
    formular      the name of the Formular in the databank (form.title), for
                  barrierefrei.titel_art; optional
    """
    logger = logging.getLogger("pypdf")
    stufe = logger.level
    logger.setLevel(logging.ERROR)
    try:
        return _messen(path, dienststelle, formular)[0]
    finally:
        logger.setLevel(stufe)


_PDFUA = re.compile(rb"pdfuaid:part\s*(?:=\s*[\"']|>)\s*(\d+)")
UNLESBAR = 0.10              # a page with this share of control characters in its text is not readable


def _marken(seite, einheit):
    """(boxes of the link annotations, boxes of the strike-out markings) of a page,
    in page coordinates. A hidden annotation has no box."""
    links, striche = [], []
    try:
        liste = _o(seite.get("/Annots")) or []
    except Exception:
        return (), ()
    for roh in liste:
        try:
            a = _o(roh)
            art = str(a.get("/Subtype"))
            if art not in ("/Link", "/StrikeOut") or int(_o(a.get("/F", 0)) or 0) & 34:
                continue
            ecken = [float(v) for v in (_o(a.get("/QuadPoints")) or [])] if art == "/StrikeOut" else []
            if len(ecken) >= 8 and len(ecken) % 8 == 0:
                for i in range(0, len(ecken), 8):
                    xs, ys = ecken[i:i + 8:2], ecken[i + 1:i + 8:2]
                    striche.append((min(xs) * einheit, min(ys) * einheit, max(xs) * einheit, max(ys) * einheit))
                continue
            x0, y0, x1, y1 = _zahlen(_o(a["/Rect"]), 4)
            (links if art == "/Link" else striche).append(
                (min(x0, x1) * einheit, min(y0, y1) * einheit, max(x0, x1) * einheit, max(y0, y1) * einheit))
        except Exception:
            continue
    return tuple(links), tuple(striche)


MIN_GESTRICHEN = 3            # a struck-through piece of fewer characters is not cut out of its line


def _ohne_stuecke(zeilen, stuecke):
    """(the lines without these pieces of text, the number of pieces cut out). A
    piece is given without white space; it is cut out of the first line that
    holds it whole."""
    aus, n = list(zeilen), 0
    for stueck in stuecke:
        if len(stueck) < MIN_GESTRICHEN:
            continue
        for i, zeile in enumerate(aus):
            orte = [k for k, ch in enumerate(zeile) if not ch.isspace()]
            p = "".join(zeile[k] for k in orte).find(stueck)
            if p >= 0:
                aus[i] = (zeile[:orte[p]].rstrip() + " " + zeile[orte[p + len(stueck) - 1] + 1:].lstrip()).strip()
                n += 1
                break
    return aus, n


def _ebenen_aus(katalog):
    """(object numbers of the optional content groups that are switched off by default)."""
    oc = _o(katalog.get("/OCProperties"))
    if not isinstance(oc, dict):
        return set()
    d = _o(oc.get("/D"))
    d = d if isinstance(d, dict) else {}
    aus = {getattr(g, "idnum", None) for g in (_o(d.get("/OFF")) or [])}
    if str(d.get("/BaseState", "/ON")) == "/OFF":
        an = {getattr(g, "idnum", None) for g in (_o(d.get("/ON")) or [])}
        aus |= {getattr(g, "idnum", None) for g in (_o(oc.get("/OCGs")) or [])} - an
    aus.discard(None)
    return aus


def _messen(path, dienststelle=None, formular=None):
    """(profil, lauf): messen() plus the raw counters, for tests."""
    import pypdf

    hinweise = []
    with open(path, "rb"):
        pass                                    # a missing or unreadable file is the caller's error: raise
    try:
        leser = pypdf.PdfReader(path)
        if leser.is_encrypted:
            try:
                offen = leser.decrypt("")
            except Exception as e:
                return _leer_profil("pdf", ["Die Datei ist verschlüsselt und liess sich nicht öffnen (%s)."
                                            % type(e).__name__]), None
            if not offen:
                return _leer_profil("pdf", ["Die Datei ist mit einem Passwort geschützt und nicht lesbar."]), None
        katalog = leser.trailer["/Root"]
        seiten = list(leser.pages)
    except Exception as e:
        return _leer_profil("pdf", ["Die Datei liess sich nicht als PDF lesen (%s)." % type(e).__name__]), None
    if not seiten:
        return _leer_profil("pdf", ["Die Datei enthält keine Seite."]), None

    profil = _leer_profil("pdf", hinweise)
    profil["seiten"] = len(seiten)

    if leser.is_encrypted:
        try:
            rechte = int(_o(leser.trailer["/Encrypt"]).get("/P", -1))
        except Exception:
            rechte = -1
        gesperrt = []
        if not rechte & 16:
            gesperrt.append("das Kopieren von Text")
        if not rechte & 512:
            gesperrt.append("die Textentnahme für Hilfsmittel")
        hinweise.append("Die Datei ist verschlüsselt (ohne Passwort lesbar)%s."
                        % ("; gesperrt ist " + _liste(gesperrt) if gesperrt else ""))

    # ---- pages: format, text, fonts, sizes, colours
    lauf = _Lauf(leser)
    try:
        lauf.aus = _ebenen_aus(katalog)
    except Exception:
        pass
    formate, texte, boxen, flaeche_gesamt, ohne_text_mit_bild, kaputt, n_roh = [], [], [], 0.0, 0, [], 0
    gestrichen = 0                              # pieces of struck-through text taken out of the lines
    for nr, seite in enumerate(seiten):
        try:
            box = seite.cropbox
            x0, y0, x1, y1 = (float(box.left), float(box.bottom), float(box.right), float(box.top))
            einheit = float(seite.get("/UserUnit", 1.0) or 1.0)
            breite, hoehe = abs(x1 - x0) * einheit, abs(y1 - y0) * einheit
            if int(seite.get("/Rotate", 0) or 0) % 180 == 90:
                breite, hoehe = hoehe, breite
            formate.append(seitenformat(breite, hoehe))
            flaeche_gesamt += breite * hoehe
        except Exception:
            formate.append(None)
            x0, y0, x1, y1, einheit = 0.0, 0.0, 595.0, 842.0, 1.0
        zeichen_vorher = (lauf.zeichen + lauf.unsichtbar + lauf.winzig + lauf.ohne_zustand + lauf.fuell
                          + lauf.wiederholt + lauf.weg)
        rahmen = (min(x0, x1) * einheit, min(y0, y1) * einheit, max(x0, x1) * einheit, max(y0, y1) * einheit)
        boxen.append((rahmen, einheit))
        mit_ressourcen = lauf.seite_beginnen(nr, seite, rahmen, einheit)
        lauf.links, lauf.striche = _marken(seite, einheit)
        if nr == 0:
            try:
                lauf.seite1 = (rahmen, int(seite.rotation or 0) % 360)
            except Exception:
                lauf.seite1 = (rahmen, 0)
        try:
            text = seite.extract_text(visitor_operand_before=lauf.vor, visitor_operand_after=lauf.nach,
                                      visitor_text=lauf.text) or ""
            if not mit_ressourcen:
                lauf.seite_selbst(seite)
        except Exception as e:
            text = ""
            kaputt.append("%d (%s)" % (nr + 1, type(e).__name__))
        try:
            lauf.seite_beenden()
        except Exception:
            lauf.fehler += 1
        zeilen_seite = [zeile.rstrip() for zeile in text.splitlines()]
        n_roh += sum(1 for zeile in zeilen_seite for ch in zeile if not ch.isspace())
        if lauf.text_weg:
            # text that is not shown (outside the page, clipped away, hidden layer) is no text of the form:
            # a line that consists of such text only is left out for the text detectors
            weg, da = "".join(lauf.text_weg), "".join(lauf.text_da)
            behalten = []
            for zeile in zeilen_seite:
                kompakt = "".join(zeile.split())
                if kompakt and kompakt in weg and kompakt not in da:
                    continue
                behalten.append(zeile)
            zeilen_seite = behalten
        if lauf.text_gestrichen:
            # text under a strike-out marking is withdrawn by the office itself: the detectors do not read it
            zeilen_seite, n = _ohne_stuecke(zeilen_seite, lauf.text_gestrichen)
            gestrichen += n
        texte.append(zeilen_seite)
        if (lauf.zeichen + lauf.unsichtbar + lauf.winzig + lauf.ohne_zustand + lauf.fuell + lauf.wiederholt + lauf.weg
                - zeichen_vorher < 1 and nr in lauf.bild_seiten):
            ohne_text_mit_bild += 1

    profil["seitenformat"] = formate[0]
    arten = defaultdict(int)
    for f in formate:
        if f:
            arten[(f["name"], f["breite_mm"], f["hoehe_mm"]) if f["name"] == "anderes" else (f["name"],)] += 1
    if len(arten) > 1:
        hinweise.append(gestaltung_text.H_FORMAT_GEMISCHT + " %s." % _liste(
            "%d × %s" % (n, k[0] if len(k) == 1 else "%d × %d mm" % (k[1], k[2]))
            for k, n in sorted(arten.items(), key=lambda kv: (-kv[1], kv[0]))))
    if kaputt:
        hinweise.append("Nicht lesbar und deshalb nicht gemessen: Seite %s." % _liste(kaputt))

    # ---- accessibility facts of the catalog
    zeilen = [zeile for seite in texte for zeile in seite]
    b = profil["barrierefrei"]
    try:
        struktur = _struktur(katalog)
    except Exception:
        struktur = None
        hinweise.append("Der Strukturbaum liess sich nicht lesen.")
    baum = isinstance(_o(katalog.get("/StructTreeRoot")), dict)
    marke = _o(katalog.get("/MarkInfo"))
    markiert = isinstance(marke, dict) and _wahr(marke.get("/Marked"))
    leer = bool(baum and struktur is not None and struktur["elemente"] == 0)
    b["tags"] = bool(baum and markiert and not leer)
    if leer:
        hinweise.append("Als getaggt gekennzeichnet, aber " + gestaltung_text.H_BAUM_LEER
                        + ": Die Datei trägt keine Tags." if markiert else
                        gestaltung_text.H_BAUM_OHNE_MARKE + " leer und nicht als markiert gekennzeichnet.")
    elif baum != markiert:
        hinweise.append(gestaltung_text.H_BAUM_OHNE_MARKE + " nicht als markiert gekennzeichnet (/MarkInfo)."
                        if baum else
                        "Als markiert gekennzeichnet (/MarkInfo), " + gestaltung_text.H_MARKE_OHNE_BAUM + ".")
    sprache = (_text(katalog.get("/Lang")) or "").strip()
    b["sprache"] = sprache or None
    im_text = textsprache(zeilen)
    if sprache and im_text:
        b["sprache_passt"] = sprache.lower().replace("_", "-").split("-")[0] == im_text
    if b["sprache_passt"] is False:
        hinweise.append(gestaltung_text.H_SPRACHE_FREMD + " «%s» passt nicht zum Text (%s)."
                        % (sprache, _SPRACHNAME[im_text]))
    if not sprache and struktur and struktur["sprache"]:
        mit = sum(struktur["sprache"].values())
        hinweise.append(gestaltung_text.H_SPRACHE_TEILE + " %d von %d Strukturelementen %s eine eigene "
                        "Sprachangabe (%s)." % (mit, struktur["elemente"], "trägt" if mit == 1 else "tragen",
                                                ", ".join(sorted(struktur["sprache"]))))
    titel = _titel(leser, hinweise)
    b["titel"] = titel
    b["titel_art"] = titel_art(titel, formular)
    if b["titel_art"] is None:
        hinweise.append(H_TITEL_OHNE_NAMEN)
    anzeige = _o(katalog.get("/ViewerPreferences"))
    b["titel_anzeige"] = bool(isinstance(anzeige, dict) and _wahr(anzeige.get("/DisplayDocTitle")))
    if b["titel_anzeige"] and b["titel_art"] in ("leer", "generisch", "ohne_bezug"):
        hinweise.append(gestaltung_text.H_TITEL_ANZEIGE + " — der Titel %s."
                        % {"leer": "fehlt aber (angezeigt wird dann doch der Dateiname)",
                           "generisch": "ist aber nur ein Datei- oder Platzhaltername",
                           "ohne_bezug": "nennt das Formular aber nicht"}[b["titel_art"]])
    felder = None
    try:
        felder = _felder(katalog)
        b["felder"], b["felder_beschriftet"] = felder["felder"], felder["beschriftet"]
        profil["ausfuellbar"] = felder["felder"] > 0
        if felder["platzhalter"]:
            hinweise.append(("%d von %d Formularfeldern %s " + gestaltung_text.H_KURZINFO_PLATZHALTER
                             + " (z. B. «3», «[1]», «undefined») und %s nicht als beschriftet.")
                            % (felder["platzhalter"], felder["felder"], "trägt" if felder["platzhalter"] == 1 else "tragen",
                               "zählt" if felder["platzhalter"] == 1 else "zählen"))
        form = _o(katalog.get("/AcroForm"))
        if isinstance(form, dict) and "/XFA" in form:
            hinweise.append("Das Formular enthält eine XFA-Beschreibung; gemessen ist die gewöhnliche PDF-Fassung.")
    except Exception:
        hinweise.append("Die Formularfelder liessen sich nicht lesen.")
    if b["tags"] and struktur:
        if felder and felder["felder"] and not struktur["form"]:
            hinweise.append(gestaltung_text.H_TAGS_OHNE_FELDER + " (kein Form-Element).")
        if not struktur["ueberschrift"]:
            hinweise.append(gestaltung_text.H_TAGS_OHNE_UEBERSCHRIFT + " (H, H1–H6).")
    try:
        xmp = _o(katalog.get("/Metadata"))
        ua = _PDFUA.search(xmp.get_data()) if hasattr(xmp, "get_data") else None
        if ua:
            hinweise.append(gestaltung_text.H_PDFUA + "-%s; ob sie die Norm erfüllt, ist hier nicht geprüft."
                            % ua.group(1).decode("ascii"))
    except Exception:
        pass

    # ---- text layer or image
    n_text = n_roh                              # every extracted character, shown or not
    bilder = bool(lauf.bild_seiten)
    if n_text < MIN_ZEICHEN_BILD:
        profil["messart"] = "pdf_bild"
        b["textebene"] = False
        hinweise.append(gestaltung_text.H_OHNE_TEXT + " (%s); Schrift, Farben, Telefonnummern und "
                        "weitere Angaben sind nicht messbar."
                        % ("Bild-PDF, z. B. ein Scan" if bilder else "die Schrift ist als Zeichnung abgelegt oder fehlt"))
        if 0 in lauf.bild_seiten:               # counted like the image on page 1 of every other PDF
            hinweise.append(gestaltung_text.H_BILD_SEITE1 + "; Farben, Schrift, Telefonnummern und "
                            "E-Mail-Adressen in Bildern sind nicht gemessen.")
        return profil, lauf
    b["textebene"] = True
    unlesbar = []
    for nr, seite in enumerate(texte, 1):
        text = "".join("".join(zeile.split()) for zeile in seite)
        if len(text) >= MIN_ZEICHEN_BILD and \
                sum(1 for ch in text if unicodedata.category(ch) in ("Cc", "Co", "Cn") or ch == "�") >= UNLESBAR * len(text):
            unlesbar.append(str(nr))
    b["text_lesbar"] = not unlesbar
    if unlesbar:
        hinweise.append(("Der Text von Seite %s " + gestaltung_text.H_UNLESBAR + " (Steuerzeichen statt Buchstaben): "
                         "Ein Vorleseprogramm und die Suche erhalten dort keine Wörter; Telefonnummern, "
                         "E-Mail-Adressen, Stand-Angabe, Seitenzahlen und Absender sind dort nicht geprüft.")
                        % _liste(unlesbar))

    # ---- fonts and sizes
    nur_bildtext = lauf.zeichen < 1 and lauf.unsichtbar >= 1
    if lauf.zeichen >= 1:
        profil["schriften"], profil["hauptschrift"], profil["n_schriftfamilien"], b["schriften_eingebettet"] = \
            _schriften(lauf, hinweise)
        profil["groessen"], profil["grundgroesse"], profil["kleinste"], profil["anteil_unter_8"] = _groessen(lauf)
        knapp_hinweise(profil["schriften"] if profil["hauptschrift"] else None, profil["groessen"], hinweise)
    elif nur_bildtext:
        hinweise.append(gestaltung_text.H_UNSICHTBAR + " (Textebene über einem Bild, z. B. nach einer "
                        "Texterkennung); Schrift und Grössen sind nicht messbar.")
    else:
        hinweise.append("Der auslesbare Text enthält keine zählbaren Zeichen (nur Füllzeichen oder Schrift unter "
                        "1 pt); Schrift und Grössen sind nicht messbar.")
    gezaehlt = lauf.zeichen + lauf.unsichtbar + lauf.winzig + lauf.fuell + lauf.wiederholt + lauf.weg
    if lauf.zeichen >= 1 and lauf.unsichtbar >= max(20.0, 0.02 * gezaehlt):
        hinweise.append(("%s " + gestaltung_text.H_TEIL_UNSICHTBAR + " (Textebene über einem Bild) und nicht in "
                         "Schrift, Grösse und Farbe gezählt.") % _prozent(lauf.unsichtbar / gezaehlt))
    if lauf.weg >= max(20.0, 0.02 * gezaehlt):
        hinweise.append("%s der Zeichen im Dateitext sind auf der Seite nicht zu sehen (ausserhalb der Seite, "
                        "weggeschnitten oder auf einer ausgeblendeten Ebene); sie sind nicht gezählt und, wo eine "
                        "ganze Zeile betroffen ist, nicht in Telefon, E-Mail, Stand-Angabe und Absender einbezogen."
                        % _prozent(lauf.weg / gezaehlt))
    if lauf.wiederholt >= max(20.0, 0.02 * gezaehlt):
        hinweise.append("%s der Zeichen sind an derselben Stelle ein zweites Mal gesetzt und nur einmal gezählt."
                        % _prozent(lauf.wiederholt / gezaehlt))
    if lauf.winzig >= max(20.0, 0.02 * gezaehlt):
        hinweise.append("%s der Zeichen sind kleiner als 1 pt gesetzt und nicht gezählt."
                        % _prozent(lauf.winzig / gezaehlt))
    if lauf.ohne_zustand >= max(20.0, 0.02 * (gezaehlt + lauf.ohne_zustand)) or \
            abs(gezaehlt + lauf.ohne_zustand - n_text) > max(20.0, 0.02 * n_text):
        hinweise.append("Die Zeichenzählung nach Schrift, Grösse und Farbe erfasst nicht den ganzen Text "
                        "(%d von %d Zeichen)." % (int(round(gezaehlt)), n_text))
    if lauf.text_fremd >= 20:
        hinweise.append("Text in einem eingebetteten Objekt ohne eigene Ressourcen ist nicht mitgezählt.")
    if ohne_text_mit_bild and ohne_text_mit_bild < len(seiten):
        hinweise.append("%d von %d Seiten bestehen nur aus einem Bild ohne auslesbaren Text."
                        % (ohne_text_mit_bild, len(seiten)))
    if lauf.aus_namen:
        hinweise.append("Ausgeblendete Ebene %s ist nicht mitgemessen."
                        % _liste("«%s»" % n for n in sorted(lauf.aus_namen)))

    # ---- colours
    if nur_bildtext:
        hinweise.append(gestaltung_text.H_FARBE_NICHT_GEMESSEN + ": Die Seiten sind Bilder.")
    else:
        profil["farben"], profil["akzent"], profil["n_farbfamilien"], profil["anteil_text_farbig"] = \
            _farben(lauf, flaeche_gesamt, hinweise)
    if 0 in lauf.bild_seiten:
        hinweise.append(gestaltung_text.H_BILD_SEITE1 + " (z. B. ein Logo); Farben, Schrift, Telefonnummern und "
                        "E-Mail-Adressen in Bildern sind nicht gemessen.")
    elif bilder:
        hinweise.append("Enthält Bilder; Farben, Schrift, Telefonnummern und E-Mail-Adressen in Bildern sind nicht "
                        "gemessen.")
    gruende = sorted(g for g in lauf.ungelesen if g)
    if gruende or lauf.verlauf:
        teile = gruende + (["Farbverlauf"] if lauf.verlauf else [])
        hinweise.append(gestaltung_text.H_FARBE_AUSGELASSEN + " %s." % _liste(teile))
    try:
        anno, kommentare, fremde_felder = _anmerkungen(leser, seiten, boxen, felder["knoten"] if felder else set())
        farben_anno = _anmerkungsfarben(anno, flaeche_gesamt)
        if farben_anno and profil["farben"] is not None:
            # what form fields and annotations paint is listed in farben (feld = true), apart from the page
            profil["farben"] = sorted(
                profil["farben"] + [{"hex": h, "familie": fam, "anteil_text": 0.0, "anteil_flaeche": _r(min(1.0, a)),
                                     "gewicht": round(min(1.0, a), 5), "nur_link": False, "feld": True,
                                     "nur_kopf": False}
                                    for h, fam, a in farben_anno],
                key=lambda e: (-e["gewicht"], e["hex"], e["feld"]))
            hinweise.append("Formularfelder, Schaltflächen oder Anmerkungen tragen eigene Farbe (%s); sie ist als "
                            "Farbe von Formularfeldern geführt und zählt nicht als Akzentfarbe."
                            % ", ".join("%s, %s der Seitenfläche" % (h, _prozent(a)) for h, _fam, a in farben_anno[:3]))
        if kommentare:
            hinweise.append("Die Datei enthält %d Kommentar%s oder Markierung%s (%s)."
                            % (sum(kommentare.values()), "" if sum(kommentare.values()) == 1 else "e",
                               "" if sum(kommentare.values()) == 1 else "en", ", ".join(sorted(kommentare))))
        if fremde_felder and felder is not None:
            hinweise.append("%d Feld-Elemente auf den Seiten gehören zu keinem Feld des Formulars (/AcroForm) und "
                            "sind bei den Formularfeldern nicht mitgezählt." % fremde_felder)
        lauf.fehler += anno.fehler
    except Exception:
        hinweise.append("Die Anmerkungen und Formularfeld-Darstellungen liessen sich nicht auswerten.")
    if lauf.fehler:
        hinweise.append("%d Zeichenbefehle liessen sich nicht auswerten." % lauf.fehler)

    # ---- contact and edition marks (gestaltung_text)
    if gestrichen:
        hinweise.append(gestaltung_text.H_GESTRICHEN + " (eine Durchstreichung als Markierung in der Datei) ist für "
                        "Telefonnummern, E-Mail-Adressen, Stand-Angabe, Seitenzahlen und Absender nicht gelesen.")
    getrennt = []                               # the lines of all pages, the pages apart
    for nr, seite in enumerate(texte):
        getrennt += ([gestaltung_text.SEITENWECHSEL] if nr else []) + seite
    profil["telefon"] = gestaltung_text.telefon(getrennt, dienststelle, seitenweise=True)
    profil["email"] = gestaltung_text.emails(zeilen)
    profil["elemente"] = gestaltung_text.elemente(texte, dienststelle)
    werte = [zeile for wert in (felder["werte"] if felder else ()) for zeile in wert.splitlines()]
    if werte:
        # a pre-filled text field prints its value like any other text of the form: an office address with
        # its number may stand there. The values join the lines for Telefon and E-Mail only (as a page of
        # their own: no letterhead of a page explains them).
        mit_tel = gestaltung_text.telefon(getrennt + [gestaltung_text.SEITENWECHSEL] + werte, dienststelle,
                                          seitenweise=True)
        mit_mail = gestaltung_text.emails(zeilen + werte)
        if mit_tel != profil["telefon"] or mit_mail != profil["email"]:
            profil["telefon"], profil["email"] = mit_tel, mit_mail
            hinweise.append("Telefonnummer oder E-Mail-Adresse " + gestaltung_text.H_FELDWERT + ".")
    return profil, lauf


# ==================================================================== self-test

def _test_pdf():
    """A two-page PDF with known content, written by hand (bytes)."""
    seite1 = (b"q 0.9 0.1 0.1 rg 50 400 200 20 re f Q\n"
              b"BT /F1 12 Tf 72 720 Td (Antrag auf Bewilligung einer Sache) Tj ET\n"
              b"BT /F1 1 Tf 8 0 0 8 72 700 Tm 0 0 1 rg (Auskunft unter www.sh.ch und amt@sh.ch) Tj 0 g ET\n"
              b"BT /F2 10 Tf 72 680 Td (Name: ______________________) Tj ET\n"
              b"q 0.5 0 0 0.5 0 0 cm /X1 Do Q\n"
              b"q 10 0 0 10 400 700 cm /I1 Do Q\n"
              b"0 0 1 RG 2 w 72 650 m 300 650 l S\n"
              b"q 0 0 10 10 re W n 1 0 1 rg 0 0 500 500 re f Q\n"
              b"BT 3 Tr /F1 12 Tf 72 600 Td (unsichtbarer Text hier) Tj 0 Tr ET\n"
              b"BT /F1 12 Tf 72 560 Td (Seite 1 von 2) Tj ET\n")
    objekt = (b"BT /F1 20 Tf 100 1000 Td (Text im eingebetteten Objekt) Tj ET\n"
              b"0 1 0 rg 0 0 100 100 re f\n")
    seite2 = (b"BT /F1 12 Tf 72 500 Td (Bei Fragen: Amt fuer Beispiele, Tel. 052 632 11 11) Tj\n"
              b"0 -20 Td (Stand 01.2024) Tj 0 -20 Td (Seite 2 von 2) Tj ET\n")

    def strom(kopf, daten):
        return b"<< " + kopf + b" /Length %d >>\nstream\n" % len(daten) + daten + b"\nendstream"
    f1 = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    koerper = [
        b"<< /Type /Catalog /Pages 2 0 R /Lang (de-CH) /MarkInfo << /Marked true >> "
        b"/StructTreeRoot << /Type /StructTreeRoot /K [17 0 R] >> /ViewerPreferences << /DisplayDocTitle true >> "
        b"/AcroForm << /Fields [13 0 R 14 0 R 15 0 R] >> >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 5 0 R /Resources << "
        b"/Font << /F1 7 0 R /F2 8 0 R >> /XObject << /X1 11 0 R /I1 12 0 R >> >> >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Contents 6 0 R /Resources << "
        b"/Font << /F1 7 0 R >> >> >>",
        strom(b"", seite1),
        strom(b"", seite2),
        f1,
        b"<< /Type /Font /Subtype /TrueType /BaseFont /ABCDEF+Arial-BoldMT /Encoding /WinAnsiEncoding "
        b"/FirstChar 32 /LastChar 126 /Widths [" + b" ".join([b"556"] * 95) + b"] /FontDescriptor 9 0 R >>",
        b"<< /Type /FontDescriptor /FontName /ABCDEF+Arial-BoldMT /Flags 32 /FontFile2 10 0 R >>",
        strom(b"", b"\x00\x01\x00\x00\x00\x00"),
        strom(b"/Type /XObject /Subtype /Form /BBox [0 0 600 1200] /Matrix [1 0 0 1 10 10] "
              b"/Resources << /Font << /F1 7 0 R >> >>", objekt),
        strom(b"/Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray /BitsPerComponent 8",
              b"\x80"),
        b"<< /FT /Tx /T (name) /TU (Name der Person) >>",
        b"<< /FT /Btn /T (einverstanden) >>",
        b"<< /FT /Btn /Ff 65536 /T (drucken) /TU (Drucken) >>",
        b"<< /Title (Antrag auf Bewilligung) >>",
        b"<< /Type /StructElem /S /P >>",
    ]
    return _pdf_datei(koerper, b"/Info 16 0 R")


def _pdf_datei(koerper, schluss=b""):
    """A PDF file from the bodies of its objects 1 … n (object 1 is the catalog)."""
    aus = b"%PDF-1.7\n"
    stellen = []
    for nr, k in enumerate(koerper, 1):
        stellen.append(len(aus))
        aus += b"%d 0 obj\n" % nr + k + b"\nendobj\n"
    xref = len(aus)
    aus += b"xref\n0 %d\n0000000000 65535 f \n" % (len(koerper) + 1)
    for st in stellen:
        aus += b"%010d 00000 n \n" % st
    aus += b"trailer\n<< /Size %d /Root 1 0 R %s >>\nstartxref\n%d\n%%%%EOF\n" % (len(koerper) + 1, schluss, xref)
    return aus


def _test_pdf2():
    """One page that holds what is NOT the visible text and colour of a form: a
    hidden layer, text outside the page, clipped text, text set twice, a link
    colour, a pale tint, a colour below the threshold, a coloured form field
    with a pre-filled value and a placeholder tooltip, a comment."""
    seite = (b"/OC /MC0 BDC 0 1 1 rg 0 0 50 50 re f EMC\n"
             b"0.86 0.90 0.95 rg 50 300 200 50 re f\n"
             b"1 0 0 rg 300 300 10 10 re f 0 g\n"
             b"BT /F1 10 Tf 72 700 Td (Gesuch um eine Bewilligung fuer Beispiele) Tj ET\n"
             b"BT /F1 10 Tf 72 680 Td 0.02 0.39 0.76 rg (www.beispielamt.sh.ch/formulare) Tj 0 g ET\n"
             b"BT /F1 10 Tf 72 660 Td (doppelt gesetzt) Tj ET\n"
             b"BT /F1 10 Tf 72 660 Td (doppelt gesetzt) Tj ET\n"
             b"BT /F1 10 Tf 72 2000 Td (Tel. 052 632 33 33 ausserhalb der Seite) Tj ET\n"
             b"q 0 0 10 10 re W n BT /F1 10 Tf 72 640 Td (Tel. 052 632 44 44 weggeschnitten) Tj ET Q\n")
    koerper = [
        b"<< /Type /Catalog /Pages 2 0 R /Lang (en-US) /AcroForm << /Fields [6 0 R] >> "
        b"/OCProperties << /OCGs [7 0 R] /D << /OFF [7 0 R] >> >> >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Annots [6 0 R 8 0 R] /Resources << "
        b"/Font << /F1 5 0 R >> /Properties << /MC0 7 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(seite) + seite + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Annot /Subtype /Widget /Rect [100 100 200 150] /F 4 /FT /Tx /T (stelle) /TU (3) "
        b"/V (Amt fuer Beispiele\\r052 632 22 22) /MK << /BG [1 1 0] >> >>",
        b"<< /Type /OCG /Name (Hilfslinien) >>",
        b"<< /Type /Annot /Subtype /Highlight /Rect [72 690 300 712] /C [1 1 0] >>",
    ]
    return _pdf_datei(koerper)


def _test_pdf3():
    """Two pages for what a reader takes in differently from the bare text: a
    drawn logo in the head, a linked word in a link colour, a struck-through
    fax number, a dashed hairline, a letterhead in two pieces (name and address
    first, the phone line at the end of the page), and a page whose text is
    stored as control characters; the catalog names a language that is not the
    text's."""
    satz = b"(Der Antrag ist bei der Gemeinde einzureichen und wird nicht zurueckgesandt.) Tj 0 -12 Td "
    seite1 = (b"1 0.84 0 rg 420 780 150 34 re f 0 g\n"
              b"BT /F1 10 Tf 72 760 Td (Kanton Schaffhausen) Tj 0 -12 Td (Amt fuer Beispiele) Tj "
              b"0 -12 Td (Musterstrasse 5) Tj 0 -12 Td (8200 Schaffhausen) Tj ET\n"
              b"BT /F1 10 Tf 72 690 Td " + satz * 6 + b"ET\n"
              b"BT /F1 10 Tf 72 600 Td (Naeheres steht im ) Tj 0 0.62 0.89 rg (Merkblatt zum Gesuch um Bewilligung) Tj "
              b"0 g ( dazu.) Tj ET\n"
              b"BT /F1 10 Tf 72 580 Td (Bestellung an die obige Adresse) Tj ET\n"
              b"BT /F1 10 Tf 230 580 Td (oder per Telefax an 052 632 55 55) Tj ET\n"
              b"0.92 0.42 0.52 RG 0.1 w [10 10] 0 d 50 500 m 550 500 l S [] 0 d\n"
              b"BT /F1 10 Tf 72 60 Td (Telefon 052 632 66 66) Tj 0 -12 Td (www.beispielamt.sh.ch) Tj ET\n")
    seite2 = b"BT /F1 10 Tf 72 700 Td (" + b"\\001\\002\\003\\004\\005" * 8 + b" Ende der Seite zwei hier) Tj ET\n"
    koerper = [
        b"<< /Type /Catalog /Pages 2 0 R /Lang (fr-CH) >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 5 0 R /Annots [8 0 R 9 0 R] /Resources << "
        b"/Font << /F1 7 0 R >> >> >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 6 0 R /Resources << "
        b"/Font << /F1 7 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(seite1) + seite1 + b"\nendstream",
        b"<< /Length %d >>\nstream\n" % len(seite2) + seite2 + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Annot /Subtype /Link /Rect [150 597 330 610] /A << /S /URI /URI (http://www.sh.ch/merkblatt) >> >>",
        b"<< /Type /Annot /Subtype /StrikeOut /F 4 /Rect [228 577 402 591] "
        b"/QuadPoints [230 590 400 590 230 578 400 578] /C [1 0 0] >>",
    ]
    return _pdf_datei(koerper)


def _selbsttest():
    n = [0]

    def gleich(ist, soll, was):
        n[0] += 1
        if ist != soll:
            raise AssertionError("%s: %r statt %r" % (was, ist, soll))

    def nah(ist, soll, was, tol=0.002):
        n[0] += 1
        if ist is None or abs(ist - soll) > tol:
            raise AssertionError("%s: %r statt %r" % (was, ist, soll))

    # ---- font families
    for name, soll in (
            ("/ABCDEF+Arial-BoldMT", ("Arial", False)), ("ArialMT", ("Arial", False)), ("Arial,Bold", ("Arial", False)),
            ("Arial", ("Arial", False)), ("Arial-ItalicMT", ("Arial", False)), ("Arial--Identity-H", ("Arial", False)),
            ("Arial,Bold--Identity-H", ("Arial", False)), ("ArialNarrow", ("Arial Narrow", False)),
            ("ArialNarrow-Bold", ("Arial Narrow", False)), ("Arial Narrow,Bold", ("Arial Narrow", False)),
            ("Arial-Black", ("Arial Black", False)), ("Arial Black", ("Arial Black", False)),
            ("TimesNewRomanPSMT", ("Times New Roman", False)), ("TimesNewRomanPS-BoldItalicMT", ("Times New Roman", False)),
            ("Times New Roman,Italic", ("Times New Roman", False)), ("TimesNewRoman", ("Times New Roman", False)),
            ("Times-Roman", ("Times", False)), ("Helvetica-BoldOblique", ("Helvetica", False)),
            ("HelveticaNeueLTPro-Bd", ("Helvetica Neue", False)), ("HelveticaNeueLTStd-Roman", ("Helvetica Neue", False)),
            ("HelveticaNeue-Medium", ("Helvetica Neue", False)), ("FrutigerLTStd-BoldCn", ("Frutiger Condensed", False)),
            ("FrutigerLTStd-Cn", ("Frutiger Condensed", False)), ("FrutigerLTCom-UltraBlack", ("Frutiger", False)),
            ("FrutigerLT-LightItalic", ("Frutiger", False)), ("Frutiger-Roman", ("Frutiger", False)),
            ("FrutigerLTPro-BoldItalic", ("Frutiger", False)), ("UniversLTStd-BoldObl", ("Univers", False)),
            ("UniversLTStd", ("Univers", False)), ("MyriadPro-SemiboldIt", ("Myriad Pro", False)),
            ("MinionPro-Regular", ("Minion Pro", False)), ("ScalaSansPro-Bold", ("Scala Sans", False)),
            ("ScalaSans-Italic", ("Scala Sans", False)), ("CourierNewPS-BoldMT", ("Courier New", False)),
            ("CourierNewPSMT", ("Courier New", False)), ("GillSansMT", ("Gill Sans", False)),
            ("GillSans", ("Gill Sans", False)), ("BookAntiqua", ("Book Antiqua", False)),
            ("Calibri-Bold", ("Calibri", False)), ("Calibri-Light", ("Calibri", False)), ("Cambria", ("Cambria", False)),
            ("CorporateS-Light", ("Corporate S", False)), ("CorporateA-Light", ("Corporate A", False)),
            ("DINOT-Medium", ("DIN OT", False)), ("EUAlbertina-ReguItal", ("EU Albertina", False)),
            ("MalgunGothicBold", ("Malgun Gothic", False)), ("FreestyleScript-Regular", ("Freestyle Script", False)),
            ("SegoeUI", ("Segoe UI", False)), ("SegoeUI-Bold", ("Segoe UI", False)), ("Verdana-Bold", ("Verdana", False)),
            ("OCR-B-Music", ("OCR-B", False)), ("Playbill", ("Playbill", False)), ("Aptos", ("Aptos", False)),
            ("Wingdings-Regular", ("Wingdings", True)), ("Wingdings2", ("Wingdings 2", True)),
            ("Wingdings3", ("Wingdings 3", True)), ("SymbolMT", ("Symbol", True)), ("Symbol", ("Symbol", True)),
            ("ZapfDingbatsITC", ("Zapf Dingbats", True)), ("ZapfDingbats", ("Zapf Dingbats", True)),
            ("SegoeUISymbol", ("Segoe UI Symbol", True)), ("Segoe#2320UI#2320Symbol", ("Segoe UI Symbol", True)),
            ("OpenSymbol", ("OpenSymbol", True)), ("EuropeanPi-Three", ("European Pi", True)),
            ("EuropeanPiStd-1", ("European Pi", True)), ("C39HrP36DlTt", ("C39HrP36DlTt", True)),
            ("MS-Gothic", ("MS Gothic", False)), ("MS#2320Gothic", ("MS Gothic", False)), ("MS Mincho", ("MS Mincho", False)),
            ("CIDFont+F1", (None, False)), ("GNFQDA+TTC78o00", (None, False)), ("None", (None, False)),
            ("", (None, False)), (None, (None, False)), ("FooBar-Bold", ("FooBar", False)),
            # names as Word and Excel give them
            ("Times New Roman", ("Times New Roman", False)), ("Arial Narrow Bold", ("Arial Narrow", False)),
            ("Calibri Light", ("Calibri", False)), ("Segoe UI Semibold", ("Segoe UI", False)),
            ("Frutiger LT Com 45 Light", ("Frutiger", False)), ("Frutiger LT Com 55 Roman", ("Frutiger", False)),
            ("Frutiger LT Std 57 Condensed", ("Frutiger Condensed", False)), ("Frutiger 45 Light", ("Frutiger", False)),
            ("Wingdings 2", ("Wingdings 2", True)), ("MS Gothic", ("MS Gothic", False)), ("Symbol", ("Symbol", True)),
            ("Courier New", ("Courier New", False)), ("Book Antiqua", ("Book Antiqua", False)),
            ("Century Gothic", ("Century Gothic", False)), ("Verdana", ("Verdana", False))):
        gleich(schriftfamilie(name), soll, "schriftfamilie(%r)" % name)
    for familie, gruppe, klasse in (("Frutiger Condensed", "Frutiger", "sans"), ("Arial Narrow", "Arial", "sans"),
                                    ("Times New Roman", "Times", "serif"), ("Times", "Times", "serif"),
                                    ("Arial", "Arial", "sans"), ("Courier New", "Courier New", "fest"),
                                    ("FooBar", "FooBar", None), (None, None, None)):
        gleich((schriftgruppe(familie), schriftklasse(familie)), (gruppe, klasse), "schriftgruppe(%r)" % familie)

    # ---- colours
    for hexa, soll in (("#000000", True), ("#ffffff", True), ("#808080", True), ("#1d1d1b", True), ("#e6ffff", True),
                       ("#ff0000", False), ("#0563c1", False), ("#fff8bd", False), ("#200000", True),
                       ("#d0ffff", False), ("#dadaff", True), ("#293725", True), ("#26232b", True),
                       ("#17365d", False), ("#000080", False), ("#dbe5f1", True), ("#eeece1", True)):
        gleich(ist_neutral(hexa), soll, "ist_neutral(%s)" % hexa)
    for hexa, soll in (("#dbe5f1", False), ("#e2efda", False), ("#eeece1", False), ("#f5f9fd", True), ("#f2f2f2", True),
                       ("#808088", True), ("#ff0000", False), ("#293725", True)):
        gleich(ist_neutral(hexa, flaeche=True), soll, "ist_neutral(%s) as a fill" % hexa)
    gleich(ist_neutral((1.0, 0.851, 0.851)), True, "saturation 0.149")
    gleich(ist_neutral((1.0, 0.849, 0.849)), False, "saturation 0.151")
    gleich(ist_neutral((0.29, 0.0, 0.0)), True, "value 0.29")
    gleich(ist_neutral((0.31, 0.0, 0.0)), False, "value 0.31")
    for grad, soll in ((0, "Rot"), (14.9, "Rot"), (15.1, "Orange"), (39.9, "Orange"), (40.1, "Gelb"), (69.9, "Gelb"),
                       (70.1, "Grün"), (164.9, "Grün"), (165.1, "Türkis"), (189.9, "Türkis"), (190.1, "Blau"),
                       (249.9, "Blau"), (250.1, "Violett"), (289.9, "Violett"), (290.1, "Magenta"),
                       (344.9, "Magenta"), (345.1, "Rot"), (359.9, "Rot")):
        gleich(farbfamilie(colorsys.hsv_to_rgb(grad / 360.0, 1.0, 1.0)), soll, "farbfamilie(%s°)" % grad)
    for hexa, soll in (("#fff2cc", "Gelb"), ("#ffc000", "Gelb"), ("#ed8300", "Orange"), ("#6a3500", "Braun"),
                       ("#009fe3", "Blau"), ("#00a3da", "Blau"), ("#1b066c", "Violett"), ("#0000ff", "Blau")):
        gleich(farbfamilie(hexa), soll, "farbfamilie(%s)" % hexa)
    e = [{"hex": "#aa0000", "familie": "Rot", "gewicht": 0.03, "nur_link": False, "feld": False, "nur_kopf": False},
         {"hex": "#00aa00", "familie": "Grün", "gewicht": 0.02, "nur_link": False, "feld": False, "nur_kopf": False},
         {"hex": "#00cc00", "familie": "Grün", "gewicht": 0.015, "nur_link": False, "feld": False, "nur_kopf": False},
         {"hex": "#0000ff", "familie": "Blau", "gewicht": 0.5, "nur_link": True, "feld": False, "nur_kopf": False},
         {"hex": "#ffff00", "familie": "Gelb", "gewicht": 0.4, "nur_link": False, "feld": True, "nur_kopf": False},
         {"hex": "#ffd700", "familie": "Gelb", "gewicht": 0.3, "nur_link": False, "feld": False, "nur_kopf": True}]
    gleich(farbwahl(e), ({"hex": "#00aa00", "familie": "Grün"}, 2), "akzent: the heaviest family, not the heaviest hex")
    gleich(farbwahl(e[3:]), (None, 0), "link colours, field colours and a head mark are no accent")
    gleich((_strichel([3, 2]), _strichel([4]), _strichel([]), _strichel(None)), (0.6, 0.5, 1.0, 1.0), "dash patterns")
    gleich(_ohne_stuecke(["Bestellung an die Adresse oder per Telefax an 052 632 55 55", "Tel. 052 632 66 66"],
                         ["oderperTelefaxan0526325555", "ab"]),
           (["Bestellung an die Adresse", "Tel. 052 632 66 66"], 1), "struck-through text leaves its line")
    gleich(_leere_codes(b"2 beginbfchar <0003> <0020> <0041> <0041> endbfchar 1 beginbfrange <00A0> <00A1> <00A0> endbfrange"),
           frozenset((3, 160)), "codes that a ToUnicode table maps to a blank")
    gleich(bool(_HILFSFARBE.match("CutContour")) and not _HILFSFARBE.match("PANTONE 199 C"), True, "production marks")
    gleich(farbfamilie("#0000ff"), "Blau", "farbfamilie hex")
    gleich(farbfamilie((0, 150, 45)), "Grün", "farbfamilie ints")
    gleich(_hex(_schluessel(_umrechnen(_CS_CMYK, [0, 0, 0, 0]), 1.0)), "#ffffff", "cmyk paper")
    gleich(_hex(_schluessel(_umrechnen(_CS_CMYK, [1, 0, 0, 0]), 1.0)), "#009fe3", "cmyk cyan")
    gleich(farbfamilie(_umrechnen(_CS_CMYK, [1, 0, 0, 0])), "Blau", "cyan is Blau")
    gleich(farbfamilie(_umrechnen(_CS_CMYK, [0, 1, 1, 0])), "Rot", "magenta + yellow")
    gleich(farbfamilie(_umrechnen(_CS_CMYK, [1, 0, 1, 0])), "Grün", "cyan + yellow")
    gleich(farbfamilie(_umrechnen(_CS_CMYK, [0, 1, 0, 0])), "Magenta", "magenta")
    gleich(ist_neutral(_umrechnen(_CS_CMYK, [0, 0, 0, 1])), True, "cmyk black")
    gleich(ist_neutral(_umrechnen(_CS_CMYK, [0, 0, 0, 0.4])), True, "cmyk grey")
    gleich(_umrechnen(_CS_G, [0.5]), (0.5, 0.5, 0.5), "gray")
    gleich(_umrechnen(_CS_RGB, [1, 0, 2]), (1.0, 0.0, 1.0), "rgb clamps")
    gleich(_hex(_schluessel(_umrechnen(("lab", (-100, 100, -100, 100)), [100, 0, 0]), 1.0)), "#ffffff", "Lab white")
    gleich(ist_neutral(_umrechnen(("lab", (-100, 100, -100, 100)), [50, 0, 0])), True, "Lab grey")
    gleich(farbfamilie(_umrechnen(("lab", (-128, 127, -128, 127)), [50, 70, 50])), "Rot", "Lab red")
    spur = []
    sep = ("sep", "HKS13", _CS_CMYK, (0.0, 0.0, 0.0, 0.0), (0.0, 1.0, 1.0, 0.0), 1.0)
    gleich(farbfamilie(_umrechnen(sep, [1.0], spur)), "Rot", "Separation over CMYK")
    gleich(spur, ["cmyk", "«HKS13»"], "trace of a spot colour")
    gleich(_umrechnen(sep, [0.0]), (1.0, 1.0, 1.0), "Separation tint 0")
    gleich(_umrechnen(("idx", _CS_RGB, bytes([0, 0, 0, 255, 0, 0])), [1]), (1.0, 0.0, 0.0), "Indexed")
    gleich(_umrechnen(("idx", _CS_RGB, bytes([0, 0, 0])), [3]), "Farbtabelle unvollständig", "Indexed out of range")
    gleich(_umrechnen(("devn", (0, 2)), [1.0, 1.0]), _cmyk_rgb(1, 0, 1, 0), "DeviceN process colours")
    gleich(_umrechnen(_CS_MUSTER, []), "Muster", "pattern is skipped")
    gleich(_umrechnen(("x", None), [1]), None, "Separation None paints nothing")
    gleich(_schluessel((1.0, 0.0, 0.0), 0.5), (255, 128, 128), "opacity over white")
    gleich(_cs_anfang(_CS_CMYK), (0.0, 0.0, 0.0, 1.0), "initial colour CMYK")

    # ---- titles and page formats
    for titel, soll in ((None, "leer"), ("", "leer"), ("  \x00", "leer"), (" ", "leer"), ("-", "generisch"), ("1", "generisch"),
                        ("1        0001 ", "generisch"), ("A4", "generisch"),
                        ("Dokument", "generisch"), ("Dokument1", "generisch"), ("document 2", "generisch"),
                        ("Unbenannt-1", "generisch"), ("Untitled", "generisch"), ("Formular", "generisch"),
                        ("Microsoft Word - Antrag.doc", "generisch"), ("Microsoft Word - 716.007 d V3.1-BBL", "generisch"),
                        ("(Microsoft Word - Pr\\374fblatt f\\374r Masken)", "generisch"),
                        ("http://eur-lex.europa.eu/legal-content/DE/TXT/PDF/?uri=CELEX:32013R0576", "generisch"),
                        ("4907369_Gesuch_LFA_SH:-", "generisch"),
                        ("Adressänderung.xls", "generisch"), ("05_055_d.indd", "generisch"),
                        ("2-212-D-2025-d_screen.pdf", "generisch"), ("Formular 150", "generisch")):
        gleich(titel_art(titel, "Gesuch um Erteilung eines Ausweises"), soll, "titel_art(%r)" % titel)
    for titel, formular, soll in (
            ("Vollmacht / Ermächtigung", "Vollmacht / Ermächtigung", "aussagekraeftig"),
            ("Formular DA-3: Antrag", "Formular DA-3: Antrag auf Anrechnung ausländischer Quellensteuer", "aussagekraeftig"),
            ("Formular 18 R", "Hilfsblatt Rebbau zur Steuererklärung (Formular 18 R)", "aussagekraeftig"),
            ("Gesuchsformular", "Gesuch um ordentliche Einbürgerung", "aussagekraeftig"),
            ("schaetzungsauftrag", "Schätzungsauftrag", "aussagekraeftig"),
            ("Bewerbungsformular_Schaffhauser_Polizei", "Bewerbung als Aspirant bei der Schaffhauser Polizei", "aussagekraeftig"),
            ("Sozialamt Kanton Schaffhausen Gesuchsformular Solidaritätsbeitrag A4", "Gesuchsformular Solidaritätsbeitrag",
             "aussagekraeftig"),
            ("Gesuchformular für Heimtiere aus Tollwut-Risikoländern 2016",
             "Gesuch für die Einfuhr von Hunden, Katzen oder Frettchen aus einem Tollwut-Risikoland", "aussagekraeftig"),
            ("Herr", "Vertrag ÖLN gesamt", "ohne_bezug"), ("Office 2010", "Stellungnahme zum Polizeigesetz", "ohne_bezug"),
            ("Arbeitszeitbestätigung", "Bestätigung des Arbeitgebers über die Benützung des privaten Motorfahrzeuges",
             "ohne_bezug"),
            ("Anmeldung für Nichterwerbstätige (NE)", "Austritt aus dem Unternehmen: Mutationsmeldung für Familienzulagen",
             "ohne_bezug"),
            ("Bundesamt für Polizei, Zentralstelle Waffen, CH – 3003 Bern", "Gesuch um Erteilung einer Waffentragbewilligung",
             "ohne_bezug"),
            ("Gesuch um Stipendien", None, None), ("Gesuch um Stipendien", " ", None)):
        gleich(titel_art(titel, formular), soll, "titel_art(%r, %r)" % (titel, formular))
    gleich(textsprache(["Der Antrag ist bei der Gemeinde einzureichen und wird nicht zurückgesandt."] * 6), "de", "German text")
    gleich(textsprache(["La demande est à déposer dans la commune et ne sera pas retournée par le service."] * 6), "fr",
           "French text")
    gleich(textsprache(["Name Vorname Strasse PLZ Ort Datum Unterschrift"] * 20), None, "labels only: no language")
    gleich(bool(_PDFUA.search(b"<pdfuaid:part>1</pdfuaid:part>")) and bool(_PDFUA.search(b'pdfuaid:part="1"')), True,
           "PDF/UA declaration in XMP")
    for tu, soll in (("3", True), ("[1]", True), ("undefined", True), ("1.2", True), ("Textfield", True),
                     ("Feld 3", True), ("Name der Person", False), ("Ja", False), ("Telefon", False)):
        gleich(bool(_TU_PLATZHALTER.match(tu)), soll, "placeholder tooltip %r" % tu)
    gleich(seitenformat(595, 842), {"name": "A4 hoch", "breite_mm": 210, "hoehe_mm": 297}, "A4 hoch")
    gleich(seitenformat(842, 595)["name"], "A4 quer", "A4 quer")
    gleich(seitenformat(603, 842)["name"], "A4 hoch", "A4 within 3 mm")
    gleich(seitenformat(605, 842)["name"], "anderes", "A4 beyond 3 mm")
    gleich(seitenformat(612, 792), {"name": "anderes", "breite_mm": 216, "hoehe_mm": 279}, "US Letter")

    # ---- leaders and addresses
    for text, soll in (("Name:______________", "Name:"), ("Ort.........Datum", "OrtDatum"), ("a...b", "ab"),
                       ("Nr.12..", "Nr.12.."), ("………………", ""), ("AAA BBB", "AAA BBB"), ("1000", "1000"),
                       ("x\x11\x11\x11\x11y", "xy"), ("☐☐☐", "☐☐☐"), ("---", ""), ("+++", "")):
        gleich(zaehlbar(text), soll.replace(" ", ""), "leader %r" % text)
    gleich(zaehlbar("Name:  . . . . . . .  Vorname: _ _ _"), "Name:Vorname:", "leaders set with blanks")
    gleich((zaehlbar(None), zaehlbar(""), zaehlbar(" \n\u00a0")), ("", "", ""), "nothing to count")
    for stuecke, soll in ((["www.sh.ch"], 1.0), (["www.", "sh.ch", "strassenverk", "ehrsamt@sh.ch"], 1.0),
                          (["stva.fuwe@sh.", "ch"], 1.0), (["d", "aniel.muster@sh.ch"], 1.0),
                          (["http://www.admin.ch/opc/de/classified", "-", "compilation/1/index.html", "htt",
                            "p://www.admin.ch/opc"], 1.0),
                          (["Achtung!"], 0.0), (["HabenSieFragen?"], 0.0), ([], 0.0)):
        nah(_nur_adressen(stuecke), soll, "_nur_adressen(%r)" % stuecke)
    n[0] += 1
    if not 0.4 < _nur_adressen(["Vollmacht", "Anmeldeformular", "https://www.svash.ch/online-schalter"]) < 0.9:
        raise AssertionError("mixed link text")

    # ---- areas of paths
    def rechteck(x, y, w, h, uhr=False):
        p = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return [p[::-1] if uhr else p, False, True]
    nah(_pfad_flaeche([rechteck(0, 0, 100, 50)], False)[0], 5000.0, "rectangle")
    nah(_pfad_flaeche([rechteck(0, 0, 100, 100), rechteck(10, 10, 80, 80, uhr=True)], False)[0], 3600.0, "frame")
    nah(_pfad_flaeche([rechteck(0, 0, 100, 100), rechteck(10, 10, 80, 80)], False)[0], 10000.0, "same direction")
    nah(_pfad_flaeche([rechteck(0, 0, 100, 100), rechteck(10, 10, 80, 80)], True)[0], 3600.0, "even-odd")
    nah(_pfad_flaeche([rechteck(0, 0, 10, 10), rechteck(50, 50, 10, 10, uhr=True)], False)[0], 200.0, "two apart")
    gleich(_pfad_flaeche([rechteck(0, 0, 200, 1)], False)[2:4], (200.0, 200.0), "thin rectangle is a line")
    gleich(_pfad_flaeche([rechteck(0, 0, 200, 4)], False)[2:4], (0.0, 0.0), "4 pt is not a line")
    gleich(_pfad_flaeche([[[(0, 0), (5, 5)], False, False]], False)[0], 0.0, "a stroke has no area")

    # ---- a whole PDF
    import tempfile
    try:
        import pypdf  # noqa: F401
    except ImportError:
        print("gestaltung_pdf: %d checks passed (pypdf missing: the PDF part was skipped)" % n[0])
        return
    logging.getLogger("pypdf").setLevel(logging.ERROR)       # the damaged test files make pypdf talk
    with tempfile.TemporaryDirectory() as ordner:
        datei = os.path.join(ordner, "probe.pdf")
        with open(datei, "wb") as fh:
            fh.write(_test_pdf())
        name = "Antrag auf Bewilligung einer Sache"
        p, lauf = _messen(datei, "Amt für Beispiele", name)
        gleich(messen(datei, "Amt für Beispiele", name), p, "messen() is repeatable")
        gleich(messen(datei)["barrierefrei"]["titel_art"], None, "without the Formular's name the title is not judged")
        zwei = os.path.join(ordner, "zwei.pdf")
        with open(zwei, "wb") as fh:
            fh.write(_test_pdf2())
        q, q_lauf = _messen(zwei, "Amt fuer Beispiele", "Gesuch um eine Bewilligung")
        drei = os.path.join(ordner, "drei.pdf")
        with open(drei, "wb") as fh:
            fh.write(_test_pdf3())
        r, r_lauf = _messen(drei, "Amt fuer Beispiele", "Gesuch um Bewilligung")
        kaputt = os.path.join(ordner, "kaputt.pdf")
        with open(kaputt, "wb") as fh:
            fh.write(b"kein PDF")
        k = messen(kaputt)
        leer = os.path.join(ordner, "leer.pdf")
        with open(leer, "wb") as fh:
            fh.write(_test_pdf().replace(b"(Antrag auf Bewilligung einer Sache) Tj", b"() Tj")
                     .replace(b"(Auskunft unter www.sh.ch und amt@sh.ch) Tj", b"() Tj")
                     .replace(b"(Text im eingebetteten Objekt) Tj", b"() Tj")
                     .replace(b"(unsichtbarer Text hier) Tj", b"() Tj").replace(b"(Seite 1 von 2) Tj", b"() Tj")
                     .replace(b"(Name: ______________________) Tj", b"() Tj")
                     .replace(b"(Bei Fragen: Amt fuer Beispiele, Tel. 052 632 11 11) Tj", b"() Tj")
                     .replace(b"(Stand 01.2024) Tj", b"() Tj").replace(b"(Seite 2 von 2) Tj", b"() Tj"))
        b = messen(leer)
        halb = os.path.join(ordner, "halb.pdf")
        with open(halb, "wb") as fh:                     # page 2 with a damaged content stream
            fh.write(_test_pdf().replace(b"(Stand 01.2024) Tj", b"(Stand 01.2024 Tj ((( "))
        h = messen(halb)
        seite2 = b"/Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>"
        geerbt = os.path.join(ordner, "geerbt.pdf")
        with open(geerbt, "wb") as fh:                   # page 2 takes its resources from the page tree
            fh.write(_test_pdf().replace(seite2, b"/Contents 6 0 R >>")
                     .replace(b"/Count 2 >>", b"/Count 2 /Resources << /Font << /F1 7 0 R >> >> >>"))
        e, e_lauf = _messen(geerbt, "Amt für Beispiele")
        ohne = os.path.join(ordner, "ohne.pdf")
        with open(ohne, "wb") as fh:                     # page 2 is a drawing without any resources
            fh.write(_test_pdf().replace(seite2, b"/Contents 6 0 R >>")
                     .replace(b"BT /F1 12 Tf 72 500 Td", b"0 0.6 0 rg 0 0 300 300 re f BT 72 500 Td"))
        o, o_lauf = _messen(ohne)
        n[0] += 1
        try:
            messen(os.path.join(ordner, "fehlt.pdf"))
            raise AssertionError("a missing file must raise")
        except OSError:
            pass

    def z(text):
        return len("".join(text.split()))
    z12 = sum(z(t) for t in ("Antrag auf Bewilligung einer Sache", "Seite 1 von 2", "Stand 01.2024", "Seite 2 von 2",
                             "Bei Fragen: Amt fuer Beispiele, Tel. 052 632 11 11"))
    z8 = z("Auskunft unter www.sh.ch und amt@sh.ch")
    z10 = z("Name:") + z("Text im eingebetteten Objekt")
    alle = float(z12 + z8 + z10)
    gleich(set(p), set(_leer_profil("pdf", [])), "keys of the profil")
    gleich((p["messart"], p["seiten"]), ("pdf", 2), "messart, seiten")
    gleich(p["seitenformat"], {"name": "A4 hoch", "breite_mm": 210, "hoehe_mm": 297}, "seitenformat")
    gleich(lauf.zeichen, alle, "counted characters")
    gleich(lauf.fuell, 22, "leader characters")
    gleich(lauf.unsichtbar, z("unsichtbarer Text hier"), "invisible characters")
    gleich([s["familie"] for s in p["schriften"]], ["Helvetica", "Arial"], "families")
    nah(p["schriften"][1]["anteil"], z("Name:") / alle, "share of Arial", 0.0001)
    gleich([(s["eingebettet"], s["symbol"]) for s in p["schriften"]], [(False, False), (True, False)], "embedding")
    gleich((p["hauptschrift"], p["n_schriftfamilien"]), ("Helvetica", 2), "hauptschrift")
    gleich([g["pt"] for g in p["groessen"]], [12.0, 8.0, 10.0], "sizes (text matrix, form matrix × cm)")
    nah(p["groessen"][0]["anteil"], z12 / alle, "share of 12 pt", 0.0001)
    nah(p["groessen"][2]["anteil"], z10 / alle, "share of 10 pt", 0.0001)
    gleich((p["grundgroesse"], p["kleinste"]), (12.0, 8.0), "grundgroesse, kleinste")
    gleich(p["anteil_unter_8"], 0.0, "anteil_unter_8")
    flaeche = 595.0 * 842.0 * 2
    gleich([f["hex"] for f in p["farben"]], ["#e61a1a", "#00ff00", "#0000ff"], "colours, by painted area")
    gleich([f["familie"] for f in p["farben"]], ["Rot", "Grün", "Blau"], "colour families")
    gleich([set(f) for f in p["farben"]], [{"hex", "familie", "anteil_text", "anteil_flaeche", "gewicht", "nur_link",
                                            "feld", "nur_kopf"}] * 3, "keys of a colour")
    nah(p["farben"][2]["anteil_text"], z8 / alle, "blue text", 0.0001)
    nah(p["farben"][2]["anteil_flaeche"], 228 * 2 / flaeche, "blue line: length × width", 0.0001)
    nah(p["farben"][2]["gewicht"], (228 * 2 + z8 * 8 * 8 * TINTE) / flaeche, "blue: line and the ink of the text", 0.00001)
    nah(p["farben"][0]["anteil_flaeche"], 4000 / flaeche, "red rectangle", 0.0001)
    nah(p["farben"][1]["anteil_flaeche"], 2500 / flaeche, "green square in the form, scaled by cm", 0.0001)
    gleich([(f["nur_link"], f["feld"], f["nur_kopf"]) for f in p["farben"]], [(False, False, False)] * 3,
           "no link colour, no field colour, no head mark (the red bar stands in the middle of the page)")
    gleich(lauf.farbe_flaeche[(255, 0, 255)], 100.0, "a clipped fill counts inside its clipping box only")
    gleich(any("Messschwelle" in h and "#ff00ff (Magenta)" in h for h in p["hinweise"]), True, "a colour below the threshold is named")
    gleich(p["akzent"], {"hex": "#e61a1a", "familie": "Rot"}, "akzent")
    gleich(p["n_farbfamilien"], 3, "n_farbfamilien")
    nah(p["anteil_text_farbig"], z8 / alle, "anteil_text_farbig", 0.0001)
    gleich(p["barrierefrei"], {"tags": True, "sprache": "de-CH", "sprache_passt": None,
                               "titel": "Antrag auf Bewilligung", "titel_art": "aussagekraeftig",
                               "titel_anzeige": True, "felder": 2, "felder_beschriftet": 1, "textebene": True,
                               "text_lesbar": True, "schriften_eingebettet": True, "ueberschriften": None},
           "barrierefrei")
    gleich(p["ausfuellbar"], True, "ausfuellbar")
    gleich([(t["e164"], t["erklaerung"]) for t in p["telefon"]], [("+41526321111", "erklaert")], "telefon")
    gleich(p["email"], [{"art": "funktional", "domain": "sh.ch"}], "email")
    gleich(p["elemente"]["stand_angabe"], {"vorhanden": True, "text": "Stand 01.2024"}, "stand_angabe")
    gleich(p["elemente"]["seitenzahlen"], {"vorhanden": True, "muster": "Seite 1 von 2"}, "seitenzahlen")
    gleich(p["elemente"]["absender"]["dienststelle"], False, "absender: page 1 does not name the office")
    for teil in ("Seitenformate gemischt: 1 × A4 hoch und 1 × A4 quer.", "PDF-Standardschrift",
                 "Seite 1 enthält ein Bild", "unsichtbar gesetzt"):
        n[0] += 1
        if not any(teil in h for h in p["hinweise"]):
            raise AssertionError("hinweis fehlt: %s in %r" % (teil, p["hinweise"]))
    gleich(any("Link" in h for h in p["hinweise"]), False, "no link note with three colours")
    # what is not the visible text and colour of a form
    sichtbar = z("Gesuch um eine Bewilligung fuer Beispiele") + z("www.beispielamt.sh.ch/formulare") + z("doppelt gesetzt")
    gleich((q_lauf.zeichen, q_lauf.wiederholt), (sichtbar, z("doppelt gesetzt")), "text set twice counts once")
    gleich(q_lauf.weg, z("Tel. 052 632 33 33 ausserhalb der Seite") + z("Tel. 052 632 44 44 weggeschnitten"),
           "text outside the page and clipped text")
    gleich([(f["hex"], f["familie"], f["nur_link"], f["feld"]) for f in q["farben"]],
           [("#dbe6f2", "Blau", False, False), ("#ffff00", "Gelb", False, True), ("#0563c2", "Blau", True, False)],
           "a pale tint, a field colour, a link colour")
    nah(q["farben"][0]["anteil_flaeche"], 10000 / (595.0 * 842.0), "the pale tint", 0.0001)
    nah(q["farben"][1]["anteil_flaeche"], 5000 / (595.0 * 842.0), "the field's background", 0.0001)
    gleich((q["akzent"], q["n_farbfamilien"]), ({"hex": "#dbe6f2", "familie": "Blau"}, 1), "akzent without link and field")
    gleich((0, 255, 255) in q_lauf.farbe_flaeche, False, "a hidden layer paints nothing")
    for teil in ("Ausgeblendete Ebene «Hilfslinien»", "Link-Farbe", "#ff0000 (Rot)", "Farbe von Formularfeldern", "1 Kommentar",
                 "nur einen Platzhalter", "vorausgefüllten Formularfeld", "nicht zu sehen"):
        gleich(any(teil in h for h in q["hinweise"]), True, "hinweis: " + teil)
    gleich((q["barrierefrei"]["felder"], q["barrierefrei"]["felder_beschriftet"], q["barrierefrei"]["tags"]), (1, 0, False),
           "a placeholder tooltip is no label")
    gleich([(t["e164"], t["erklaerung"]) for t in q["telefon"]], [("+41526322222", "ohne")],
           "the number of a pre-filled field; none from text that is not shown")
    gleich(q["barrierefrei"]["titel_art"], "leer", "no title")
    # what a reader takes in differently from the bare text
    gleich([(f["hex"], f["nur_link"], f["nur_kopf"]) for f in r["farben"]],
           [("#ffd600", False, True), ("#009ee3", True, False)], "a drawn logo in the head; a linked word in a link colour")
    gleich((r["akzent"], r["n_farbfamilien"]), (None, 0), "neither is an accent")
    nah(r_lauf.farbe_linie[(235, 107, 133)], 500 * 0.5 * MIN_LINIE_DICKE, "a dashed hairline paints half its length", 0.01)
    gleich([(t["e164"], t["art"], t["erklaerung"]) for t in r["telefon"]], [("+41526326666", "telefon", "erklaert")],
           "the struck-through fax number is not read; the phone line apart from its letterhead is explained")
    gleich((r["barrierefrei"]["sprache_passt"], r["barrierefrei"]["text_lesbar"], r["barrierefrei"]["textebene"]),
           (False, False, True), "a language that is not the text's; a page of control characters")
    for teil in ("Link-Farbe", "Kopf der ersten Seite", gestaltung_text.H_GESTRICHEN, gestaltung_text.H_UNLESBAR,
                 gestaltung_text.H_SPRACHE_FREMD, "#eb6b85 (Rot)"):
        gleich(any(teil in x for x in r["hinweise"]), True, "hinweis: " + teil)
    # unreadable file and image-only file
    gleich((k["messart"], k["seiten"], k["schriften"], k["telefon"], k["barrierefrei"]["tags"]),
           ("pdf", None, None, None, None), "unreadable file")
    gleich(len(k["hinweise"]), 1, "unreadable file: one hinweis")
    gleich((h["messart"], h["seiten"], h["hauptschrift"], h["grundgroesse"]), ("pdf", 2, "Helvetica", 12.0),
           "a broken page does not lose the file")
    gleich(any("Nicht lesbar" in x and "Seite 2" in x for x in h["hinweise"]), True, "a broken page is named")
    gleich((e_lauf.zeichen, e["schriften"], e["telefon"]), (lauf.zeichen, p["schriften"], p["telefon"]),
           "resources inherited from the page tree")
    gleich((o_lauf.farbe_flaeche[(0, 153, 0)], o["seiten"], "#009900" in [f["hex"] for f in o["farben"]]),
           (90000.0, 2, True), "a page without resources is walked for its colours")
    gleich((b["messart"], b["schriften"], b["farben"], b["telefon"], b["email"], b["hauptschrift"]),
           ("pdf_bild", None, None, None, None, None), "pdf_bild: text-based values are null")
    gleich(b["elemente"]["stand_angabe"], {"vorhanden": None, "text": None}, "pdf_bild: elemente are null")
    gleich((b["barrierefrei"]["textebene"], b["barrierefrei"]["tags"], b["barrierefrei"]["felder"], b["seiten"]),
           (False, True, 2, 2), "pdf_bild: catalog facts stay")
    print("gestaltung_pdf: %d checks passed" % n[0])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        import json
        for datei in sys.argv[1:]:
            print(json.dumps(messen(datei), ensure_ascii=False, indent=1))
    else:
        _selbsttest()
