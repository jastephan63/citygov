#!/usr/bin/env python3
"""Measure how a Word or Excel Formular looks: fonts, sizes, colours, the few
accessibility facts such a file carries, and what it prints about contact and
edition. The Office counterpart of gestaltung_pdf.py, read straight from the
file's own XML (zipfile + xml.etree; no Office program, no conversion).

    messen_docx(path, dienststelle=None, formular=None) -> profil      # .docx; a .doc gives 'nicht_messbar'
    messen_xlsx(path, dienststelle=None, formular=None) -> profil      # .xlsx; an .xls gives 'nicht_messbar'

    python3 scripts/gestaltung_office.py                # self-test on two files built in memory
    python3 scripts/gestaltung_office.py <file> …       # print the profile of real files

The profil has the keys of the «Gestaltung» measurement for every file type.
Everything in it is a fact read from the file or null with a reason in
`hinweise` (German, for the reader of the dashboard); nothing is estimated.
`path` may also be an open binary file. `dienststelle` (service.dienststelle)
is optional and only handed on to the text detectors of gestaltung_text.py;
`formular` (form.title, optional) is the name the document title is held
against (titel_art; without it a title that is neither empty nor generic gets
titel_art null).
A file that cannot be read never raises: old binary formats (.doc, .xls), an
encrypted or damaged package give messart 'nicht_messbar' — every measured
value null (also the lists: «not measured» is not «nothing found») and one
hinweis that says why. Only a missing file raises (OSError). An error inside
the measuring code is caught the same way and named «unerwarteter Aufbau»;
scan_gestaltung.py lists such a file as a failure instead of writing the row.

Word (.docx)
  Characters are the printed, non-white-space characters of w:t in the body,
  in table cells, in content controls, in text boxes (w:txbxContent), in the
  footnotes/endnotes, and in every header and footer that a section really
  uses (first-page parts only with w:titlePg, even-page parts only with
  evenAndOddHeaders) — each part once, not once per page. Also counted: the
  cached result of a field (form-field text, page number), the entry that a
  drop-down form field shows (the chosen one, else the default, else the
  first — «+41 52 632 » followed by such a field prints a whole number), a
  w:sym symbol (one character in its own font) and the display text of a
  MACROBUTTON field. Not printed and not counted: field instructions, deleted text
  (w:del, w:moveFrom), hidden text (w:vanish), and the second copy of a text
  box (of an mc:AlternateContent only the first Choice is read).
  * Font and size of a character are resolved as Word does: run properties,
    then the character style, the paragraph style (the default paragraph
    style when none is named), the table style with its conditional parts
    (first/last row and column, bands, corners, by w:tblLook), the document
    defaults; every style with its basedOn chain. A theme reference
    (asciiTheme, hAnsiTheme …) takes the font of theme1.xml and wins over a
    name on the same level. ASCII characters take the ascii font, other
    Latin characters the hAnsi font, East Asian and complex-script
    characters theirs (sz / szCs accordingly). Where no level names a font
    or a size, Word's built-in default counts (Times New Roman, 10 pt) and a
    hinweis says for how many characters. The font is the one the file
    names; what a device without that font shows instead is not measured.
  * `eingebettet`: the font table of the file carries an embedded font
    program for the name (w:embedRegular …).
  * Colours: the text colour of each character (w:color through the same
    hierarchy; «auto» is no colour), the shading of paragraphs and table
    cells (w:shd, direct, from the paragraph style, from the table style,
    from the table), run shading and highlight, and the colours of paragraph
    and table borders. Theme colours are resolved through the colour scheme
    and its mapping in settings.xml, tint and shade on the HLS luminance as
    Word does; the value Word stored beside the reference is used when both
    agree (they did for every reference in the corpus). Percent patterns
    are mixed, other patterns are no colour (hinweis).
  * `seiten` is the page count of docProps/app.xml, i.e. of the last save
    (hinweis). The page breaks stored in the text (manual breaks, section
    breaks, w:lastRenderedPageBreak) are a second witness: when they prove
    more pages than the properties name, the count is null. A manual page
    break inside a table cell does not count (Word ignores it). The amount
    of text is a third: when it cannot fit on the stated pages even in the
    tightest setting (every glyph 0.4 em wide, lines 1 em high, the area
    inside the margins filled completely), the count is null as well.
  * `seitenformat`: w:pgSz of the first section, in mm.
  * barrierefrei: `sprache` is the w:lang of most characters; `titel` is
    dc:title; `ueberschriften` is true when at least one paragraph with text
    uses a heading style (name «heading 1–9», also through basedOn) or
    carries an outline level — a hinweis says when it is exactly one. tags,
    titel_anzeige, felder, felder_beschriftet, textebene,
    schriften_eingebettet are PDF notions and stay null.
  * `ausfuellbar`: legacy form fields (w:ffData) or content controls are
    present in the text (body, tables, text boxes, notes); a content control
    that only wraps a building block (page number gallery, table of
    contents) does not count, and neither does a field in a header or footer
    (the office's own drop-down for its phone extension; hinweis).
  * Text lines for telefon / email / elemente: one line per paragraph (a
    line break inside it starts a new line); a table row whose cells hold
    one line each is one line, cell by cell; text boxes stand before the
    paragraph they are anchored in. The lines are grouped into pages by the
    stored page breaks; each page gets the header and footer lines of the
    first section around it, with PAGE and NUMPAGES fields set to the page
    number and the page count — this is how the form prints, and it lets the
    detector quote «Seite 1 von 3» as it does for a PDF. The cached result
    of a DATE, TIME or PRINTDATE field is left out (it is the day of
    printing, not an edition mark). `seitenzahlen` is null for a one-page
    document; a page-number field counts as page numbering even where the
    detector does not recognise the printed line. When a document of
    several pages stores no page break, «page 1» is the whole text (hinweis).

Excel (.xlsx)
  Measured are the visible sheets (hidden sheets, rows and columns are left
  out; hinweis) and, where a sheet defines a print area, only the cells
  inside it — helper cells beside the form are not the form.
  * Characters are those of the text cells: shared strings, inline strings,
    text results of formulas and error values («#DIV/0!»), each run of a
    rich text with its own font, size and colour over the cell style
    (styles.xml fonts through cellXfs). Of a merged cell only the first
    cell counts. Cells that show a number or a date are not counted: how
    many characters they print depends on the number format (hinweis with
    their number). Text in drawn shapes and the labels of form controls
    count with the font and size their runs name (theme font when none is
    named).
  * Colours: text colours as above; the solid fills and the border colours
    of every stored cell, also of empty ones — the input cells of a form are
    empty by nature. rgb, theme (+ tint, on the HLS luminance) and indexed
    colours (default palette or the one in the file) are resolved; what
    cannot be resolved is left out and counted in a hinweis. Pattern and
    gradient fills and conditional formats are not evaluated (hinweis).
  * `seiten` is null (pagination happens at printing). `seitenformat` comes
    from paperSize and orientation of the first visible sheet. `titel` from
    dc:title; every other barrierefrei value and `ausfuellbar` are null (the
    measurement defines them for PDF and Word only).
  * Text lines: one per sheet row (cells joined; a cell with line breaks
    keeps its lines), then the text of the shapes; one «page» per sheet,
    with the text of its header and footer. `seitenzahlen`: a header or
    footer prints the page number (&P) → true, with the line as it prints
    on page 1 and «N» for the page count; otherwise null.

Colours in both file types
  Neutral colours are not reported: HSV saturation < 0.15 or value < 0.30;
  as a fill a pale tint (saturation from 0.05, value from 0.80) is a colour,
  as the colour of text or of a border it is none (gestaltung_pdf.ist_neutral
  — one rule for all file types). Near-identical colours (every channel
  within 0.04) are one colour, named after its heaviest member. A colour
  counts with at least 20 characters set in it, with one filled paragraph or
  cell, with 20 characters on a run-level fill, or with one border line; the
  shades of one colour family that do not count by themselves count together
  when they reach that, and what still stays below is named in a hinweis.
  This is NOT the rule of a PDF (there: 300 pt² of painted area): one filled
  cell counts here, so the numbers of colours of an Office file and of a PDF
  are not comparable.
  `anteil_text` is the share of all counted characters. `anteil_flaeche` is
  always null: without a fixed layout there is no area to measure (hinweis).
  `gewicht` is the stored weight that gives the order of `farben`: the share
  of paragraphs (Excel: cells) filled with the colour, plus the share of
  characters standing on it as a run-level fill, plus TINTE (0.16) times the
  share of characters set in it — coloured text counts with its ink, as in a
  PDF. `nur_link`: every character of the colour is link text (Word: a
  hyperlink element, field or character style) or nothing but internet and
  e-mail addresses, and the colour fills and frames nothing. `feld` and
  `nur_kopf` are always false (the keys exist for PDF form fields and for a
  logo drawn in the head of a PDF page). `akzent` is the heaviest colour
  of the heaviest colour family among the colours that are no link colour;
  n_farbfamilien counts those families (gestaltung_pdf.farbwahl).

Fonts in both file types
  The family is the name the file gives, reduced by the rule of
  gestaltung_pdf.schriftfamilie («Calibri Light» → Calibri,
  «MinionPro-Regular» → Minion Pro; Arial Narrow and Arial Black are
  families of their own, different families are never merged) after the
  technical tag of an old Windows name is dropped («Arial (W1)» → Arial).
  A placeholder name that a PDF program invented («CIDFont+F2», copied into
  a Word file) stays as the file gives it and is named in a hinweis.
  `symbol` is true for the symbol fonts by name (Wingdings, Symbol …) and for
  a font that sets nothing but check-box glyphs (MS Gothic for «☐»).

One definition for all file types
  Font family, colour family, neutral, the thresholds (20 characters, 0.04),
  titel_art and seitenformat are imported from gestaltung_pdf, so that a Word
  form and a PDF form are sorted by the same rule. Importing that module
  needs no pypdf (it loads pypdf only when it measures a PDF); this module
  runs on the standard library alone.

Where this module reads the specification more closely than its wording
  messen_docx / messen_xlsx take the optional `dienststelle` and `formular`;
  the lists of a 'nicht_messbar' profile are null; `anteil_flaeche` is null
  and a fill counts by its presence; Excel is measured inside the print
  area, fills from all stored cells there, fonts from the text cells;
  `seiten` of a Word file is null when the stored page breaks contradict the
  stored count; an Excel page number is quoted with «N» for the unknown page
  count; each entry of `farben` carries gewicht, nur_link, feld and nur_kopf;
  `barrierefrei` carries sprache_passt and text_lesbar, both null here (they
  are facts of a PDF).

Where this module changes a definition of the specification
  The changes of gestaltung_pdf.py apply here as well (its docstring gives
  the reasons): neutral and the pale fill, the colour families, akzent by
  colour family and without link colours, titel_art against the name of the
  Formular. Of its own:
  * `ausfuellbar` asks for a field in the text, not in a header or footer;
  * the shown entry of a drop-down form field is text (the office's phone
    extension in a letterhead is read like the printed text around it).
  The sentences of `hinweise` that the comparison layer reads are built from
  the constants of gestaltung_text.py (H_…), as in gestaltung_pdf.py.

Deliberately not measured
  A full accessibility audit (reading order, alternative texts, contrast,
  WCAG conformance); the canton's corporate design (the comparison is with
  the practice of the other Formulare); pictures and everything inside them
  (a logo's colours and text — hinweis whenever a file carries a picture);
  fills and outlines of drawn shapes (hinweis); layout geometry (margins,
  positions, the real page breaks); list numbers and bullets, footnote
  marks, the entries of a drop-down form field that are not shown, the smaller
  print of superscript and small caps; comments; Excel header/footer fonts, charts,
  column- and row-wide default formats of cells that are not stored.
  One known difference to Word is announced by a hinweis and did not occur
  in the corpus: a table style with its own font size in a document without
  the compatibility setting overrideTableStyleFontSizeAndJustification.

Checked on 2026-10-04 against two independent readers of the 60 .docx
Formulare. macOS Quick Look (which applies styles and theme fonts, but
states nothing for text that only the document defaults format, and cuts
half points): main font and body size agree for 60 of 60 when this module
leaves out the document defaults and cuts to whole points; the stated text
colours agree. macOS textutil (which applies no style sheet — Times 12
where a run has no direct format): main font agrees for 23, body size for 30
of 60 as is; told to read like textutil, this module reproduces its
character-by-character distribution for 48 files; the others differ by
fonts that are not installed on the test machine and by text boxes, which
textutil prints twice. The 20 .xlsx were read a second time with openpyxl:
the characters of the text cells by font and size are identical in all 20.
"""
import colorsys
import os
import posixpath
import re
import sys
import unicodedata
import zipfile
import zlib
import xml.etree.ElementTree as ET
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gestaltung_text as gt
# the notions every file type shares — one definition each (importing them needs no pypdf)
from gestaltung_pdf import (schriftfamilie, farbfamilie, ist_neutral, titel_art, seitenformat, farbwahl,
                            knapp_hinweise, CLUSTER, MIN_ZEICHEN_FARBE, MIN_ZEICHEN_KLEINSTE, TINTE,
                            H_TITEL_OHNE_NAMEN, _nur_adressen)

__all__ = ["messen_docx", "messen_xlsx"]

# ---------------------------------------------------------------- package access

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
XDR = "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
PIC = "{http://schemas.openxmlformats.org/drawingml/2006/picture}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
WPS = "{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}"
V = "{urn:schemas-microsoft-com:vml}"
DC = "{http://purl.org/dc/elements/1.1/}"
EP = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"

# Files saved as «Strict Open XML» use other namespace names for the same elements.
_STRICT = tuple((b"http://purl.oclc.org/ooxml/" + a, b"http://schemas.openxmlformats.org/" + b) for a, b in (
    (b"wordprocessingml/main", b"wordprocessingml/2006/main"),
    (b"spreadsheetml/main", b"spreadsheetml/2006/main"),
    (b"drawingml/main", b"drawingml/2006/main"),
    (b"drawingml/spreadsheetDrawing", b"drawingml/2006/spreadsheetDrawing"),
    (b"drawingml/picture", b"drawingml/2006/picture"),
    (b"officeDocument/relationships", b"officeDocument/2006/relationships"),
    (b"officeDocument/extendedProperties", b"officeDocument/2006/extended-properties")))
_MAX_TEIL = 150 * 1024 * 1024        # no part of a Formular is anywhere near this size
_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

SEITE, ANZAHL = "\ue000", "\ue001"   # stand-ins for a page-number / page-count field inside a text line


class _Unlesbar(Exception):
    """The file is not a package this module can read; the message is the German reason."""


class _Paket:
    """A zip package (.docx / .xlsx): parts by name, relationships, parsed on demand."""

    def __init__(self, z):
        self.z = z
        self.namen = {}
        for info in z.infolist():
            self.namen.setdefault(info.filename.lstrip("/").lower(), info)

    def hat(self, name):
        return bool(name) and name.lstrip("/").lower() in self.namen

    def xml(self, name):
        """Root element of a part, None when the part does not exist."""
        info = self.namen.get((name or "").lstrip("/").lower())
        if info is None:
            return None
        if info.file_size > _MAX_TEIL:
            raise _Unlesbar("Datei nicht lesbar: ein Teil des Dokuments ist ungewöhnlich gross.")
        daten = self.z.read(info)
        if b"<!DOCTYPE" in daten or b"<!ENTITY" in daten:      # never part of an Office file
            raise _Unlesbar("Datei nicht lesbar: unerwarteter Aufbau eines Dokumentteils.")
        if b"purl.oclc.org/ooxml" in daten:
            for alt, neu in _STRICT:
                daten = daten.replace(alt, neu)
        try:
            return ET.fromstring(daten)
        except (LookupError, ValueError) as e:              # e.g. an unknown encoding in the XML declaration
            raise ET.ParseError(str(e)) from None

    def rels(self, teil):
        """Relationships of a part: {id: (type suffix, target part name)}; external targets are left out."""
        ordner, datei = posixpath.split(teil)
        root = self.xml(posixpath.join(ordner, "_rels", datei + ".rels"))
        out = {}
        for r in (root if root is not None else ()):
            if r.get("TargetMode") == "External" or not r.get("Target"):
                continue
            ziel = r.get("Target")
            ziel = ziel.lstrip("/") if ziel.startswith("/") else posixpath.normpath(posixpath.join(ordner, ziel))
            out[r.get("Id")] = ((r.get("Type") or "").rsplit("/", 1)[-1], ziel)
        return out

    def ziel(self, rels, typ):
        """The first target of a relationship type, None when there is none."""
        for t, ziel in rels.values():
            if t == typ:
                return ziel
        return None


def _oeffnen(pfad, alt_endungen, alt_name):
    """(_Paket, None) for a zip package, (None, German reason) for a file that is none."""
    if hasattr(pfad, "read"):
        kopf = pfad.read(8)
        pfad.seek(0)
        endung = ""
    else:
        with open(pfad, "rb") as fh:
            kopf = fh.read(8)
        endung = os.path.splitext(str(pfad))[1].lower()
    if kopf == _OLE2:
        if endung in alt_endungen:
            return None, f"Altes {alt_name}-Format ({endung}): ohne Umwandlung in das heutige Format nicht messbar."
        return None, f"Kein lesbares {alt_name}-Dokument im heutigen Format (altes Format oder verschlüsselt)."
    try:
        return _Paket(zipfile.ZipFile(pfad)), None
    except zipfile.BadZipFile:
        return None, f"Datei nicht lesbar: kein {alt_name}-Dokument im heutigen Format."


def _an(el):
    """An on/off element or attribute value: present means on unless it says 0/false/off."""
    wert = el if isinstance(el, str) or el is None else (el.get(W + "val") or el.get("val"))
    return wert not in ("0", "false", "off")


def _wahl(el):
    """The branch of an mc:AlternateContent that is read: the first Choice, else the Fallback
    (both hold the same content in two notations — reading both would count it twice)."""
    zweig = el.find(MC + "Choice")
    if zweig is None:
        zweig = el.find(MC + "Fallback")
    return zweig if zweig is not None else ()


def _lokal(tag):
    return tag.rsplit("}", 1)[-1]


def _punkt(text, teiler=1):
    """A font size in pt from its attribute (Word: half-points, DrawingML: hundredths); None
    for anything that is no plausible size."""
    try:
        pt = float(text) / teiler
    except (TypeError, ValueError):
        return None
    return pt if 0.5 <= pt <= 2000 else None


# ---------------------------------------------------------------- colour

def _hex(wert):
    """'#rrggbb' from 'RRGGBB' / 'AARRGGBB' / '#rrggbb', None when it is no colour value."""
    w = (wert or "").strip().lstrip("#")
    if len(w) == 8:
        w = w[2:]
    return "#" + w.lower() if re.fullmatch(r"[0-9A-Fa-f]{6}", w) else None


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _von_rgb(r, g, b):
    return "#%02x%02x%02x" % tuple(min(255, max(0, int(round(x * 255)))) for x in (r, g, b))


def _nah(a, b):
    """Two colours that count as one: every channel within CLUSTER."""
    return max(abs(x - y) for x, y in zip(_rgb(a), _rgb(b))) <= CLUSTER + 1e-9


def _helligkeit(h, faktor, zu_weiss):
    """WordprocessingML themeTint / themeShade: the HLS luminance scaled by `faktor`,
    for a tint towards white (L × f + 1 − f), for a shade towards black (L × f)."""
    hh, l, s = colorsys.rgb_to_hls(*_rgb(h))
    l = l * faktor + (1 - faktor) if zu_weiss else l * faktor
    return _von_rgb(*colorsys.hls_to_rgb(hh, min(1.0, max(0.0, l)), s))


def _hls_tint(h, tint):
    """SpreadsheetML tint: the luminance moved towards white (tint > 0) or black (tint < 0)."""
    r, g, b = _rgb(h)
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
    return _von_rgb(*colorsys.hls_to_rgb(hh, min(1.0, max(0.0, l)), s))


def _farbprofil(text, gesamt, flaeche, bloecke, lauf, linien, nur_link):
    """farben / akzent / n_farbfamilien / anteil_text_farbig.

    text:    {hex: characters set in the colour}           gesamt:  all counted characters
    flaeche: {hex: paragraphs or cells filled with it}     bloecke: all paragraphs or cells
    lauf:    {hex: characters standing on a run-level fill (shading, highlight)}
    linien:  {hex: border lines drawn in it}               nur_link: colours whose text is link text only
    Neutral colours are dropped — as a fill a pale tint is a colour, as text or line it is none
    (gestaltung_pdf.ist_neutral); near-identical ones are one colour, named after its heaviest
    member. A colour counts with MIN_ZEICHEN_FARBE characters set in it or standing on it as a
    run-level fill, with one filled paragraph/cell, or with one border line; the shades of one
    family that do not count by themselves count together when they reach that.
    `gewicht` puts text and fills on one scale, the share of the document that is painted: a
    filled paragraph or cell counts as its share of all paragraphs or cells, text on a run-level
    fill as its share of all characters, coloured text as TINTE times its share of characters
    (the ink of a character covers about a fifth of its place)."""
    t = {h: n for h, n in text.items() if h and not ist_neutral(h)}
    f = {h: n for h, n in flaeche.items() if h and not ist_neutral(h, flaeche=True)}
    a = {h: n for h, n in lauf.items() if h and not ist_neutral(h, flaeche=True)}
    li = {h: n for h, n in linien.items() if h and not ist_neutral(h)}

    def gewicht(h):
        return ((TINTE * t.get(h, 0) + a.get(h, 0)) / gesamt if gesamt else 0.0) + \
               (f.get(h, 0) / bloecke if bloecke else 0.0)

    def zaehlt(glieder):
        return (sum(t.get(h, 0) for h in glieder) >= MIN_ZEICHEN_FARBE or sum(a.get(h, 0) for h in glieder) >= MIN_ZEICHEN_FARBE
                or any(f.get(h) or li.get(h) for h in glieder))

    bunt = sorted(set(t) | set(f) | set(a) | set(li), key=lambda h: (-gewicht(h), -li.get(h, 0), -t.get(h, 0), h))
    gruppen = []                                   # near-identical colours, heaviest first
    for h in bunt:
        for g in gruppen:
            if _nah(h, g[0]):
                g.append(h)
                break
        else:
            gruppen.append([h])
    fertig, rest = [], {}
    for g in gruppen:
        if zaehlt(g):
            fertig.append(g)
        else:
            rest.setdefault(farbfamilie(g[0]), []).extend(g)
    unter = []
    for familie, g in rest.items():
        if zaehlt(g):
            fertig.append(g)
        elif not any(farbfamilie(x[0]) == familie for x in fertig):
            unter.append((g[0], familie))
    farben = []
    for glieder in fertig:
        zeichen = sum(t.get(h, 0) for h in glieder)
        gefuellt = any(f.get(h) for h in glieder)
        auf = sum(a.get(h, 0) for h in glieder)
        g = sum(gewicht(h) for h in glieder)
        farben.append({"hex": glieder[0], "familie": farbfamilie(glieder[0]),
                       "anteil_text": round(zeichen / gesamt, 4) if gesamt else 0.0, "anteil_flaeche": None,
                       "gewicht": round(min(1.0, g), 5),
                       "nur_link": bool(zeichen and all(h in nur_link for h in glieder if t.get(h))
                                        and not gefuellt and not auf and not any(li.get(h) for h in glieder)),
                       "feld": False, "nur_kopf": False,
                       "_gewicht": g, "_flaeche": gefuellt or auf >= MIN_ZEICHEN_FARBE})
    farben.sort(key=lambda e: (-e["_gewicht"], e["hex"]))
    akzent, n_familien = farbwahl(farben)
    return {"farben": farben, "akzent": akzent, "n_farbfamilien": n_familien,
            "anteil_text_farbig": round(sum(t.values()) / gesamt, 4) if gesamt else None,
            "_unter": sorted(unter)}


# ---------------------------------------------------------------- fonts

_KASTEN = frozenset("☐☑☒✓✔✗✘□■▢▣◻◼❏❐❑❒○●◯⬜⬛")
_UNSICHTBAR = frozenset("\u200b\u200c\u200d\u2060\ufeff\xad")
_MARKE = re.compile(r" ?\((?:W1|TT|TrueType|OpenType|Vektor)\)$")       # «Arial (W1)», «Times (TT)»


def _familie(name):
    """(family, symbol font by its name, placeholder name) for a font name of an Office file:
    gestaltung_pdf.schriftfamilie — one rule for all file types — after the technical tag of
    old Windows names is dropped. A producer's placeholder («CIDFont+F2», copied in from a
    PDF) is no family there; here the name stays, because it is what the file names."""
    n = _MARKE.sub("", " ".join(unicodedata.normalize("NFC", name or "").split()))
    familie, symbol = schriftfamilie(n)
    return familie or n, symbol, familie is None


def _schriftprofil(zaehlung, nur_kasten, eingebettet):
    """schriften … anteil_unter_8 from {(…, font name, pt, …): characters} (name at [1], pt at [2]),
    and the placeholder names among the families."""
    gesamt = sum(zaehlung.values())
    if not gesamt:
        return {"schriften": [], "hauptschrift": None, "n_schriftfamilien": None, "groessen": [],
                "grundgroesse": None, "kleinste": None, "anteil_unter_8": None}, []
    fam, glieder, pt, nach_name, platzhalter = Counter(), {}, Counter(), set(), set()
    for key, n in zaehlung.items():
        f, symbol, platz = _familie(key[1])
        fam[f] += n
        glieder.setdefault(f, set()).add(key[1])
        pt[round(key[2] * 2) / 2] += n
        if symbol:
            nach_name.add(f)
        if platz:
            platzhalter.add(f)
    schriften = []
    for f, n in sorted(fam.items(), key=lambda x: (-x[1], x[0])):
        namen = glieder[f]
        schriften.append({"familie": f, "anteil": round(n / gesamt, 4),
                          "eingebettet": None if eingebettet is None else all(m in eingebettet for m in namen),
                          "symbol": f in nach_name or all(nur_kasten.get(m) for m in namen)})
    text = [s for s in schriften if not s["symbol"]]
    groessen = sorted(pt.items(), key=lambda x: (-x[1], x[0]))
    return {"schriften": schriften,
            "hauptschrift": text[0]["familie"] if text else None,
            "n_schriftfamilien": sum(1 for s in text if s["anteil"] >= 0.02),
            "groessen": [{"pt": p, "anteil": round(n / gesamt, 4)} for p, n in groessen[:6]],
            "grundgroesse": groessen[0][0],
            "kleinste": min((p for p, n in pt.items() if n >= MIN_ZEICHEN_KLEINSTE), default=None),
            "anteil_unter_8": round(sum(n for p, n in pt.items() if p < 8.0) / gesamt, 4)}, sorted(platzhalter)


# ---------------------------------------------------------------- document properties, profile frame

def _eigenschaften(paket):
    """(title or None, page count of the last save or None) from docProps/core.xml and app.xml."""
    titel = seiten = None
    haupt = paket.rels("")
    kern = paket.xml(paket.ziel(haupt, "core-properties") or "docProps/core.xml")
    if kern is not None:
        e = kern.find(DC + "title")
        titel = e.text if e is not None and (e.text or "").strip() else None
    app = paket.xml(paket.ziel(haupt, "extended-properties") or "docProps/app.xml")
    if app is not None:
        e = app.find(EP + "Pages")
        if e is not None and re.fullmatch(r"[0-9]{1,6}", (e.text or "").strip()) and int(e.text) > 0:
            seiten = int(e.text)
    return titel, seiten


def _rahmen(messart):
    """A profile with every key of the specification and nothing measured yet."""
    return {"messart": messart, "seiten": None, "seitenformat": None,
            "schriften": None, "hauptschrift": None, "n_schriftfamilien": None,
            "groessen": None, "grundgroesse": None, "kleinste": None, "anteil_unter_8": None,
            "farben": None, "akzent": None, "n_farbfamilien": None, "anteil_text_farbig": None,
            "barrierefrei": {"tags": None, "sprache": None, "sprache_passt": None, "titel": None, "titel_art": None,
                             "titel_anzeige": None, "felder": None, "felder_beschriftet": None,
                             "textebene": None, "text_lesbar": None, "schriften_eingebettet": None,
                             "ueberschriften": None},
            "telefon": None, "email": None,
            "elemente": {"stand_angabe": {"vorhanden": None, "text": None},
                         "seitenzahlen": {"vorhanden": None, "muster": None},
                         "absender": {"kanton": None, "dienststelle": None, "text": None}},
            "ausfuellbar": None, "hinweise": []}


def _nicht_messbar(grund):
    p = _rahmen("nicht_messbar")
    p["hinweise"].append(grund)
    return p


def _setzen(zeile, seite, anzahl):
    return zeile.replace(SEITE, str(seite)).replace(ANZAHL, str(anzahl))


def _kuerzen(text, n=60):
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n - 1] + "…"


# ---------------------------------------------------------------- theme (shared by Word and Excel)

class _Thema:
    """theme1.xml: the fonts of the major/minor scheme and the twelve scheme colours."""

    def __init__(self, root):
        self.schrift, self.farbe = {}, {}
        if root is None:
            return
        fs = root.find(".//" + A + "fontScheme")
        for art in ("major", "minor"):
            f = fs.find(A + art + "Font") if fs is not None else None
            for skript in ("latin", "ea", "cs"):
                e = f.find(A + skript) if f is not None else None
                if e is not None and (e.get("typeface") or "").strip():
                    self.schrift[(art, skript)] = e.get("typeface")
        cs = root.find(".//" + A + "clrScheme")
        for e in (cs if cs is not None else ()):
            for k in e:
                wert = k.get("val") if k.tag == A + "srgbClr" else (
                    k.get("lastClr") or {"windowText": "000000", "window": "FFFFFF"}.get(k.get("val")))
                if _hex(wert):
                    self.farbe[_lokal(e.tag)] = _hex(wert)

    def name(self, verweis):
        """Font of a theme reference: Word «minorHAnsi», «majorBidi» …, DrawingML «+mn-lt» …"""
        v = verweis or ""
        art = "major" if v.startswith(("major", "+mj")) else "minor"
        skript = "ea" if v.endswith(("EastAsia", "-ea")) else "cs" if v.endswith(("Bidi", "-cs")) else "latin"
        return self.schrift.get((art, skript)) or self.schrift.get((art, "latin"))


# ---------------------------------------------------------------- Word: properties and styles

_FEHLT = object()                    # «not set at this level» (None means «set to: no fill»)
_HELL = {"black": "#000000", "blue": "#0000ff", "cyan": "#00ffff", "green": "#00ff00", "magenta": "#ff00ff",
         "red": "#ff0000", "yellow": "#ffff00", "white": "#ffffff", "darkBlue": "#000080", "darkCyan": "#008080",
         "darkGreen": "#008000", "darkMagenta": "#800080", "darkRed": "#800000", "darkYellow": "#808000",
         "darkGray": "#808080", "lightGray": "#c0c0c0"}
_PROZENT = {"pct5": .05, "pct10": .10, "pct12": .125, "pct15": .15, "pct20": .20, "pct25": .25, "pct30": .30,
            "pct35": .35, "pct37": .375, "pct40": .40, "pct45": .45, "pct50": .50, "pct55": .55, "pct60": .60,
            "pct62": .625, "pct65": .65, "pct70": .70, "pct75": .75, "pct80": .80, "pct85": .85, "pct87": .875,
            "pct90": .90, "pct95": .95}
_RAND_SEITEN = frozenset(W + s for s in ("top", "left", "bottom", "right", "start", "end", "insideH", "insideV",
                                         "between", "bar", "tl2br", "tr2bl"))
_FELD_STUMM = frozenset(("PAGE", "NUMPAGES", "SECTIONPAGES", "DATE", "TIME", "PRINTDATE"))
_UEBERSCHRIFT = re.compile(r"(?i)(?:heading|überschrift|ueberschrift|titre|titolo) ?[1-9]")
_MAKRO = re.compile(r"\s*MACROBUTTON\s+\S+\s")


def _farbangabe(el, wert, thema, tint, shade):
    return (el.get(W + wert), el.get(W + thema), el.get(W + tint), el.get(W + shade))


def _shd(el):
    """A w:shd as (pattern, fill colour reference, pattern colour reference)."""
    return (el.get(W + "val") or "clear",
            _farbangabe(el, "fill", "themeFill", "themeFillTint", "themeFillShade"),
            _farbangabe(el, "color", "themeColor", "themeTint", "themeShade"))


def _rand(el):
    """Colour references of the drawn sides of a border element (w:pBdr, w:tblBorders, w:tcBorders)."""
    return [_farbangabe(k, "color", "themeColor", "themeTint", "themeShade") for k in (el if el is not None else ())
            if k.tag in _RAND_SEITEN and k.get(W + "val") not in (None, "nil", "none")]


def _rpr(el):
    """What a w:rPr sets, and only that: the levels of the style hierarchy are merged with dict.update."""
    d = {}
    for k in (el if el is not None else ()):
        t = k.tag
        if t == W + "rFonts":
            for slot, thema in (("ascii", "asciiTheme"), ("hAnsi", "hAnsiTheme"), ("eastAsia", "eastAsiaTheme"),
                                ("cs", "cstheme")):
                if k.get(W + thema):
                    d[slot] = (True, k.get(W + thema))        # a theme reference wins over a name beside it
                elif k.get(W + slot):
                    d[slot] = (False, k.get(W + slot))
            if k.get(W + "hint"):
                d["hint"] = k.get(W + "hint")
        elif t in (W + "sz", W + "szCs"):
            if _punkt(k.get(W + "val"), 2):
                d[_lokal(t)] = _punkt(k.get(W + "val"), 2)
        elif t == W + "color":
            d["color"] = _farbangabe(k, "val", "themeColor", "themeTint", "themeShade")
        elif t == W + "shd":
            d["shd"] = _shd(k)
        elif t == W + "highlight":
            d["highlight"] = k.get(W + "val")
        elif t == W + "lang":
            if k.get(W + "val"):
                d["lang"] = k.get(W + "val")
        elif t == W + "rStyle":
            d["rStyle"] = k.get(W + "val")
        elif t in (W + "vanish", W + "cs", W + "rtl"):
            d["_" + _lokal(t)] = _an(k)
    return d


def _ppr(el):
    d = {}
    for k in (el if el is not None else ()):
        t = k.tag
        if t == W + "pStyle":
            d["pStyle"] = k.get(W + "val")
        elif t == W + "shd":
            d["shd"] = _shd(k)
        elif t == W + "pBdr":
            d["rand"] = _rand(k)
        elif t == W + "outlineLvl":
            d["ebene"] = k.get(W + "val")
        elif t == W + "pageBreakBefore":
            d["umbruch"] = _an(k)
        elif t == W + "sectPr":
            d["sectPr"] = k
    return d


class _Stile:
    """styles.xml: document defaults and the styles with their basedOn chains resolved."""

    def __init__(self, root):
        self.std, self.s, self.vorgabe, self._memo = {}, {}, {}, {}
        if root is None:
            return
        self.std = _rpr(root.find(W + "docDefaults/" + W + "rPrDefault/" + W + "rPr"))
        for st in root.findall(W + "style"):
            sid, typ = st.get(W + "styleId"), st.get(W + "type") or "paragraph"
            name, basis = st.find(W + "name"), st.find(W + "basedOn")
            e = {"typ": typ, "name": name.get(W + "val") if name is not None else "",
                 "basis": basis.get(W + "val") if basis is not None else None,
                 "rpr": _rpr(st.find(W + "rPr")), "ppr": _ppr(st.find(W + "pPr"))}
            if typ == "table":
                e["tab"] = self._tabelle(st)
            self.s[sid] = e
            if st.get(W + "default") in ("1", "true", "on"):
                self.vorgabe.setdefault(typ, sid)

    @staticmethod
    def _zelle(tcpr, d):
        if tcpr is not None:
            if tcpr.find(W + "shd") is not None:
                d["shd"] = _shd(tcpr.find(W + "shd"))
            if tcpr.find(W + "tcBorders") is not None:
                d["rand"] = _rand(tcpr.find(W + "tcBorders"))

    def _tabelle(self, st):
        d = {"bedingt": {}}
        tblpr = st.find(W + "tblPr")
        if tblpr is not None:
            for tag, key in (("tblStyleRowBandSize", "zband"), ("tblStyleColBandSize", "sband")):
                e = tblpr.find(W + tag)
                if e is not None and re.fullmatch(r"[1-9][0-9]{0,3}", e.get(W + "val") or ""):
                    d[key] = int(e.get(W + "val"))
            if tblpr.find(W + "shd") is not None:
                d["tblshd"] = _shd(tblpr.find(W + "shd"))
            if tblpr.find(W + "tblBorders") is not None:
                d["rand"] = _rand(tblpr.find(W + "tblBorders"))
        self._zelle(st.find(W + "tcPr"), d)
        for b in st.findall(W + "tblStylePr"):
            bd = {"rpr": _rpr(b.find(W + "rPr"))}
            self._zelle(b.find(W + "tcPr"), bd)
            d["bedingt"][b.get(W + "type")] = bd
        return d

    def kette(self, sid):
        """The styles from the root of the basedOn chain down to sid."""
        out, gesehen = [], set()
        while sid in self.s and sid not in gesehen:
            gesehen.add(sid)
            out.append(self.s[sid])
            sid = self.s[sid]["basis"]
        return out[::-1]

    def rpr(self, sid):
        if ("r", sid) not in self._memo:
            d = {}
            for st in self.kette(sid):
                d.update(st["rpr"])
            self._memo[("r", sid)] = d
        return self._memo[("r", sid)]

    def ppr(self, sid):
        if ("p", sid) not in self._memo:
            d = {}
            for st in self.kette(sid):
                d.update(st["ppr"])
            d["ueberschrift"] = any(_UEBERSCHRIFT.fullmatch(st["name"] or "") for st in self.kette(sid))
            self._memo[("p", sid)] = d
        return self._memo[("p", sid)]

    def tab(self, sid):
        """A table style with its chain merged: run properties, shading, borders, conditional parts."""
        if ("t", sid) not in self._memo:
            d = {"rpr": {}, "bedingt": {}, "zband": 1, "sband": 1}
            for st in self.kette(sid):
                d["rpr"].update(st["rpr"])
                for k, v in st.get("tab", {}).items():
                    if k != "bedingt":
                        d[k] = v
                for typ, b in st.get("tab", {}).get("bedingt", {}).items():
                    ziel = d["bedingt"].setdefault(typ, {"rpr": {}})
                    ziel["rpr"].update(b["rpr"])
                    ziel.update({k: v for k, v in b.items() if k != "rpr"})
            self._memo[("t", sid)] = d
        return self._memo[("t", sid)]


def _tbllook(tblpr):
    """Which conditional parts of the table style a table switches on (w:tblLook)."""
    e = tblpr.find(W + "tblLook") if tblpr is not None else None
    namen = (("firstRow", 0x0020), ("lastRow", 0x0040), ("firstColumn", 0x0080), ("lastColumn", 0x0100),
             ("noHBand", 0x0200), ("noVBand", 0x0400))
    if e is None:
        return {n: False for n, _b in namen}
    try:
        bits = int(e.get(W + "val") or "0", 16)
    except ValueError:
        bits = 0
    return {n: (e.get(W + n) in ("1", "true", "on")) if e.get(W + n) is not None else bool(bits & b)
            for n, b in namen}


def _bedingte_teile(look, ts, zeile, n_zeilen, spalte, n_spalten):
    """The conditional parts of a table style that apply to a cell, lowest precedence first."""
    kopf, fuss = look["firstRow"] and zeile == 0, look["lastRow"] and zeile == n_zeilen - 1
    erste, letzte = look["firstColumn"] and spalte == 0, look["lastColumn"] and spalte == n_spalten - 1
    out = []
    if not look["noVBand"] and not erste and not letzte:
        i = spalte - (1 if look["firstColumn"] else 0)
        out.append("band1Vert" if (i // ts["sband"]) % 2 == 0 else "band2Vert")
    if not look["noHBand"] and not kopf and not fuss:
        i = zeile - (1 if look["firstRow"] else 0)
        out.append("band1Horz" if (i // ts["zband"]) % 2 == 0 else "band2Horz")
    out += [n for n, an in (("firstCol", erste), ("lastCol", letzte), ("firstRow", kopf), ("lastRow", fuss),
                            ("neCell", kopf and letzte), ("nwCell", kopf and erste),
                            ("seCell", fuss and letzte), ("swCell", fuss and erste)) if an]
    return out


def _zahl(text, vorgabe=None, typ=float):
    try:
        return typ(text)
    except (TypeError, ValueError):
        return vorgabe


def _feldtyp(anweisung):
    m = re.match(r"\s*([A-Za-z]+|=)", anweisung or "")
    return m.group(1).upper() if m else None


def _slot(c, eff):
    """Which of the four fonts of a run sets the character (ascii / hAnsi / eastAsia / cs)."""
    o = ord(c)
    if eff.get("_cs") or eff.get("_rtl") or 0x0590 <= o <= 0x08FF or 0xFB1D <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
        return "cs"
    if o < 0x80:
        return "ascii"
    if (0x1100 <= o <= 0x11FF or 0x2E80 <= o <= 0x9FFF or 0xA000 <= o <= 0xA4CF or 0xAC00 <= o <= 0xD7FF
            or 0xF900 <= o <= 0xFAFF or 0xFE30 <= o <= 0xFE4F or 0xFF00 <= o <= 0xFFEF):
        return "eastAsia"
    if eff.get("hint") == "eastAsia" and 0x2000 <= o <= 0x2BFF:
        return "eastAsia"
    return "hAnsi"


# ---------------------------------------------------------------- Word: the walk through the text

class _Word:
    """One pass over a .docx: characters by font, size, colour and language; fills and border
    colours; the text lines by page; form fields, content controls, headings."""

    WORD_SCHRIFT, WORD_PT = "Times New Roman", 10.0       # what Word sets when a file names nothing

    def __init__(self, paket, haupt):
        self.paket, self.haupt = paket, haupt
        self.rels = paket.rels(haupt)
        self.thema = _Thema(paket.xml(paket.ziel(self.rels, "theme")))
        self.stile = _Stile(paket.xml(paket.ziel(self.rels, "styles")))
        self.abbild = {"bg1": "light1", "t1": "dark1", "bg2": "light2", "t2": "dark2"}
        self.gerade_kopf = self.tab_regel = self.tabstil_alt = False
        einst = paket.xml(paket.ziel(self.rels, "settings"))
        if einst is not None:
            for k in einst.iter(W + "compatSetting"):
                if k.get(W + "name") == "overrideTableStyleFontSizeAndJustification":
                    self.tab_regel = _an(k)
            m = einst.find(W + "clrSchemeMapping")
            for k, v in (m.attrib.items() if m is not None else ()):
                self.abbild[_lokal(k)] = v
            e = einst.find(W + "evenAndOddHeaders")
            self.gerade_kopf = e is not None and _an(e)
        self.eingebettet = set()
        ft = paket.xml(paket.ziel(self.rels, "fontTable"))
        for f in (ft if ft is not None else ()):
            if any(_lokal(k.tag).startswith("embed") for k in f):
                self.eingebettet.add(f.get(W + "name"))

        self.z = Counter()            # (region, font, pt, text colour, language, link text) → characters
        self.kasten = {}              # font name → True while it has set nothing but check-box glyphs
        self.n = 0                    # characters counted so far
        self.absaetze = 0
        self.flaeche, self.lauf, self.linien = Counter(), Counter(), Counter()
        self.felder = []              # the open fields, innermost last
        self.formfelder = self.steuerelemente = 0
        self.felder_rand = 0          # of these, form fields and content controls in a header or footer
        self.ueberschriften = 0       # paragraphs with text that are headings
        self.bilder = self.formen = self.seitenfeld = False
        self.stuecke = {}             # text colour → the pieces of text set in it (for the link test)
        self.im_rand = False          # walking a header or footer
        self.ohne_schrift = self.ohne_groesse = 0
        self.muster = set()           # shading patterns that are no plain colour
        self.fremd = False            # w:altChunk: content in another format, not read
        self.thema_ungleich = 0       # theme colours that resolve to another value than the one stored beside
        self.bereich = "text"
        self.link = 0
        self.seiten = [[]]            # body text lines by page, as far as the file stores page breaks
        self.senke = self.seiten[0]
        self.puffer = []
        self.fliesst = False          # walking the body flow: page breaks count
        self.tiefe = 0                # table nesting
        self.umbruch_offen = False
        self._farbe_memo, self._abschnitt = {}, 0
        self.abschnitte = []
        self.textflaeche = None       # pt², the page of the first section inside its margins

    # ---- colours

    def farbe(self, angabe):
        """'#rrggbb' of a colour reference (value, theme colour, tint, shade); None for automatic."""
        if angabe not in self._farbe_memo:
            wert, thema, tint, shade = angabe
            fest, h = _hex(wert), None
            if thema and thema != "none":
                name = {"background1": "bg1", "text1": "t1", "background2": "bg2", "text2": "t2"}.get(thema, thema)
                name = self.abbild.get(name, name)
                name = {"dark1": "dk1", "light1": "lt1", "dark2": "dk2", "light2": "lt2", "hyperlink": "hlink",
                        "followedHyperlink": "folHlink"}.get(name, name)
                h = self.thema.farbe.get(name)
                try:
                    if h and tint:
                        h = _helligkeit(h, int(tint, 16) / 255, True)
                    if h and shade:
                        h = _helligkeit(h, int(shade, 16) / 255, False)
                except ValueError:
                    h = None
                if h and fest:                 # the value Word stored beside the reference, unless the theme differs
                    if _nah(h, fest):
                        h = fest
                    else:
                        self.thema_ungleich += 1
            self._farbe_memo[angabe] = h or fest
        return self._farbe_memo[angabe]

    def fuellung(self, shd):
        """'#rrggbb' of a shading, None for none (clear/auto) or a pattern that is no plain colour."""
        if shd is _FEHLT or shd is None:
            return None
        art, grund, vorn = shd
        if art in ("clear", "nil"):
            return self.farbe(grund)
        if art == "solid":
            return self.farbe(vorn) or "#000000"
        if art in _PROZENT:
            return _von_rgb(*(a * _PROZENT[art] + b * (1 - _PROZENT[art]) for a, b in
                              zip(_rgb(self.farbe(vorn) or "#000000"), _rgb(self.farbe(grund) or "#ffffff"))))
        self.muster.add(art)
        return None

    def linie(self, angaben):
        for a in angaben or ():
            h = self.farbe(a)
            if h:
                self.linien[h] += 1

    # ---- characters

    def schrift(self, eff, slot):
        v = eff.get(slot)
        if v is None:
            return None
        return self.thema.name(v[1]) if v[0] else v[1]

    def zaehle(self, text, eff, schrift=None):
        """Count the printed characters of a piece of a run (white space is not counted)."""
        if eff.get("_vanish"):
            return
        farbe = self.farbe(eff["color"]) if "color" in eff else None
        grund = _HELL.get(eff.get("highlight")) or (self.fuellung(eff["shd"]) if "shd" in eff else None)
        link = self.link > 0 or eff.get("_link", False) or any(f["typ"] == "HYPERLINK" for f in self.felder)
        namen = {}
        for c in text:
            if c.isspace() or c in _UNSICHTBAR:
                continue
            slot = _slot(c, eff)
            if slot not in namen:
                name = schrift or self.schrift(eff, slot)
                pt = eff.get("szCs" if slot == "cs" else "sz")
                namen[slot] = (name or self.WORD_SCHRIFT, pt or self.WORD_PT, name is None, pt is None)
            name, pt, ohne_s, ohne_g = namen[slot]
            self.ohne_schrift += ohne_s
            self.ohne_groesse += ohne_g
            self.z[(self.bereich, name, pt, farbe, eff.get("lang"), link)] += 1
            self.kasten[name] = self.kasten.get(name, True) and (schrift is not None or c in _KASTEN)
            self.n += 1
            if grund:
                self.lauf[grund] += 1
        if farbe and schrift is None and text.strip():
            teile = self.stuecke.setdefault(farbe, [])
            if len(teile) < 400:
                teile.extend(text.split())

    # ---- lines and pages

    def zeile(self):
        """Close the current text line."""
        text = "".join(self.puffer).rstrip()
        self.puffer = []
        if text.strip():
            self.senke.append(text)

    def neue_seite(self):
        """A page break of the body text (a manual, a section or a stored rendered one)."""
        if not self.fliesst:
            return
        if self.tiefe:
            self.umbruch_offen = True          # inside a table: the page turns before the row
            return
        self.zeile()
        self.seitenwechsel()

    def seitenwechsel(self):
        self.umbruch_offen = False
        if self.seiten[-1]:
            self.seiten.append([])
        self.senke = self.seiten[-1]

    # ---- fields

    def gedruckt(self):
        """Is text at this place printed? Not inside a field instruction — except the display
        text of a MACROBUTTON field, which is part of its instruction."""
        for i, f in enumerate(self.felder):
            if f["phase"] == "ergebnis":
                continue
            if not (i == len(self.felder) - 1 and f["typ"] == "MACROBUTTON" and _MAKRO.match(f["instr"])):
                return False
        return True

    def stumm(self):
        """Inside the cached result of a page or print-date field: printed, but not text of the form."""
        return any(f["phase"] == "ergebnis" and f["typ"] in _FELD_STUMM for f in self.felder)

    def feld_ende(self):
        f = self.felder.pop()
        if self.gedruckt() and not self.stumm():
            if f["typ"] == "PAGE":
                self.puffer.append(SEITE)
                self.seitenfeld = True
            elif f["typ"] in ("NUMPAGES", "SECTIONPAGES"):
                self.puffer.append(ANZAHL)
            elif f["typ"] == "FORMDROPDOWN" and f.get("wahl"):
                self.zaehle(f["wahl"], f["eff"])           # the entry a drop-down field shows is printed
                self.puffer.append(f["wahl"])

    def feldzeichen(self, el, eff):
        art = el.get(W + "fldCharType")
        if art == "begin":
            feld = {"typ": None, "instr": "", "phase": "anweisung"}
            daten = el.find(W + "ffData")
            if daten is not None:
                self.formfelder += 1
                self.felder_rand += self.im_rand
                liste = daten.find(W + "ddList")
                if liste is not None:                      # shown: the chosen entry, else the default, else the first
                    eintraege = [e.get(W + "val") or "" for e in liste.findall(W + "listEntry")]
                    wahl = liste.find(W + "result")
                    wahl = wahl if wahl is not None else liste.find(W + "default")
                    i = _zahl(wahl.get(W + "val"), 0, int) if wahl is not None else 0
                    if eintraege:
                        feld["wahl"], feld["eff"] = eintraege[i if 0 <= i < len(eintraege) else 0], eff
            self.felder.append(feld)
        elif art == "separate" and self.felder:
            self.felder[-1]["phase"] = "ergebnis"
        elif art == "end" and self.felder:
            self.feld_ende()

    def anweisung(self, text, eff):
        if not self.felder or self.felder[-1]["phase"] != "anweisung":
            return
        f = self.felder[-1]
        alt = len(f["instr"])
        f["instr"] += text
        f["typ"] = _feldtyp(f["instr"])
        m = _MAKRO.match(f["instr"]) if f["typ"] == "MACROBUTTON" else None
        if m and self.gedruckt():
            sichtbar = f["instr"][max(m.end(), alt):]
            self.zaehle(sichtbar, eff)
            self.puffer.append(sichtbar)

    # ---- content

    def sdt(self, el):
        """A content control counts as fillable unless it only wraps a building block."""
        pr = el.find(W + "sdtPr")
        if pr is None or not any(_lokal(k.tag) in ("docPartObj", "docPartList", "bibliography", "citation", "equation")
                                 for k in pr):
            self.steuerelemente += 1
            self.felder_rand += self.im_rand

    def block(self, eltern, tab):
        for el in eltern:
            t = el.tag
            if t == W + "p":
                self.absatz(el, tab)
            elif t == W + "tbl":
                self.tabelle(el)
            elif t == W + "sdt":
                self.sdt(el)
                inhalt = el.find(W + "sdtContent")
                if inhalt is not None:
                    self.block(inhalt, tab)
            elif t in (W + "customXml", W + "ins", W + "moveTo", W + "smartTag"):
                self.block(el, tab)
            elif t == MC + "AlternateContent":
                self.block(_wahl(el), tab)
            elif t == W + "altChunk":
                self.fremd = True

    def absatz(self, p, tab):
        ppr = _ppr(p.find(W + "pPr"))
        sid = ppr.get("pStyle") or self.stile.vorgabe.get("paragraph")
        stil = self.stile.ppr(sid)
        basis = dict(self.stile.std)
        if tab:
            basis.update(tab["rpr"])
        basis.update(self.stile.rpr(sid))
        if ppr.get("umbruch", stil.get("umbruch", False)):
            self.neue_seite()
        grund = self.fuellung(ppr.get("shd", stil.get("shd", _FEHLT))) or (tab["grund"] if tab else None)
        self.absaetze += 1
        if grund:
            self.flaeche[grund] += 1
        self.linie(ppr.get("rand", stil.get("rand")))
        vorher = self.n
        self.inhalt(p, basis)
        self.zeile()
        if self.n > vorher and (stil["ueberschrift"] or ppr.get("ebene", stil.get("ebene")) in tuple("012345678")):
            self.ueberschriften += 1
        if "sectPr" in ppr and self.fliesst:               # the last paragraph of a section
            self._abschnitt += 1
            if self._abschnitt < len(self.abschnitte) and self.abschnitte[self._abschnitt]["neue_seite"]:
                self.neue_seite()

    def inhalt(self, eltern, basis):
        for k in eltern:
            t = k.tag
            if t == W + "r":
                self.text_lauf(k, basis)
            elif t == W + "hyperlink":
                self.link += 1
                self.inhalt(k, basis)
                self.link -= 1
            elif t == W + "fldSimple":
                self.felder.append({"typ": _feldtyp(k.get(W + "instr")), "instr": k.get(W + "instr") or "",
                                    "phase": "ergebnis"})
                self.inhalt(k, basis)
                self.feld_ende()
            elif t == W + "sdt":
                self.sdt(k)
                inhalt = k.find(W + "sdtContent")
                if inhalt is not None:
                    self.inhalt(inhalt, basis)
            elif t in (W + "ins", W + "moveTo", W + "smartTag", W + "customXml", W + "dir", W + "bdo"):
                self.inhalt(k, basis)
            elif t == MC + "AlternateContent":
                self.inhalt(_wahl(k), basis)
            # w:del, w:moveFrom (deleted text), bookmarks, proofing marks: nothing printed

    def text_lauf(self, r, basis):
        rpr = _rpr(r.find(W + "rPr"))
        eff = dict(basis)
        zeichenstil = rpr.get("rStyle") or self.stile.vorgabe.get("character")
        if zeichenstil:
            eff.update(self.stile.rpr(zeichenstil))
            if any("hyperlink" in (st["name"] or "").lower() for st in self.stile.kette(zeichenstil)):
                eff["_link"] = True
        eff.update(rpr)
        for k in r:
            t = k.tag
            if t == W + "t":
                if self.gedruckt():
                    self.zaehle(k.text or "", eff)
                    if not self.stumm() and not eff.get("_vanish"):
                        self.puffer.append(k.text or "")
            elif t == W + "instrText":
                self.anweisung(k.text or "", eff)
            elif t == W + "fldChar":
                self.feldzeichen(k, eff)
            elif t == W + "tab" or t == W + "ptab":
                self.puffer.append("\t")
            elif t in (W + "br", W + "cr"):
                if k.get(W + "type") == "page" and self.fliesst and not self.tiefe:
                    self.neue_seite()              # (inside a table cell Word ignores a manual page break)
                else:
                    self.zeile()
            elif t == W + "lastRenderedPageBreak":
                self.neue_seite()
            elif t == W + "sym":
                if self.gedruckt():
                    self.zaehle("□", eff,
                                schrift=k.get(W + "font") or self.schrift(eff, "hAnsi") or self.WORD_SCHRIFT)
            elif t == W + "noBreakHyphen":
                if self.gedruckt():
                    self.zaehle("-", eff)
                    self.puffer.append("-")
            elif t == W + "pgNum":
                self.puffer.append(SEITE)
                self.seitenfeld = True
            elif t in (W + "drawing", W + "pict", W + "object"):
                self.zeichnung(k)
            elif t == MC + "AlternateContent":
                self.zeichnung(_wahl(k))

    def zeichnung(self, el):
        """Pictures and drawn shapes are only noted; the text of text boxes is read."""
        stapel = [el]
        while stapel:
            for k in stapel.pop():
                t = k.tag
                if t == W + "txbxContent":
                    self.textfeld(k)
                    continue
                if t == MC + "AlternateContent":
                    stapel.append(_wahl(k))
                    continue
                if t in (PIC + "pic", V + "imagedata", A + "blip"):
                    self.bilder = True
                elif t == WPS + "wsp" or (t.startswith(V) and _lokal(t) in ("shape", "rect", "roundrect", "oval",
                                                                           "line", "polyline", "arc", "curve")
                                          and k.find(V + "imagedata") is None):
                    self.formen = True
                stapel.append(k)

    def textfeld(self, inhalt):
        alt = (self.puffer, self.senke, self.fliesst, self.bereich, self.felder, self.tiefe)
        self.puffer, self.senke, self.fliesst, self.bereich, self.felder, self.tiefe = [], [], False, "feld", [], 0
        self.block(inhalt, None)
        zeilen = self.senke
        self.puffer, self.senke, self.fliesst, self.bereich, self.felder, self.tiefe = alt
        self.senke.extend(zeilen)

    def _entpackt(self, eltern, tag):
        """The rows of a table / cells of a row, also when a content control or the like wraps them."""
        for k in eltern:
            if k.tag == tag:
                yield k
            elif k.tag == W + "sdt":
                self.sdt(k)
                inhalt = k.find(W + "sdtContent")
                if inhalt is not None:
                    yield from self._entpackt(inhalt, tag)
            elif k.tag in (W + "customXml", W + "ins", W + "moveTo"):
                yield from self._entpackt(k, tag)

    def tabelle(self, tbl):
        tblpr = tbl.find(W + "tblPr")
        e = tblpr.find(W + "tblStyle") if tblpr is not None else None
        ts = self.stile.tab(e.get(W + "val") if e is not None else self.stile.vorgabe.get("table"))
        look = _tbllook(tblpr)
        if not self.tab_regel and ("sz" in ts["rpr"] or any("sz" in b["rpr"] for b in ts["bedingt"].values())):
            self.tabstil_alt = True
        e = tblpr.find(W + "shd") if tblpr is not None else None
        tblshd = _shd(e) if e is not None else ts.get("tblshd", _FEHLT)
        e = tblpr.find(W + "tblBorders") if tblpr is not None else None
        self.linie(_rand(e) if e is not None else ts.get("rand"))
        zeilen = list(self._entpackt(tbl, W + "tr"))
        self.tiefe += 1
        for zi, tr in enumerate(zeilen):
            zellen = list(self._entpackt(tr, W + "tc"))
            je_zelle = []
            for si, tc in enumerate(zellen):
                rpr, shd = dict(ts["rpr"]), ts.get("shd", _FEHLT)
                for teil in _bedingte_teile(look, ts, zi, len(zeilen), si, len(zellen)):
                    b = ts["bedingt"].get(teil)
                    if b:
                        rpr.update(b["rpr"])
                        shd = b.get("shd", shd)
                        self.linie(b.get("rand"))
                tcpr = tc.find(W + "tcPr")
                e = tcpr.find(W + "shd") if tcpr is not None else None
                if e is not None:
                    shd = _shd(e)
                elif shd is _FEHLT:
                    shd = tblshd
                self.linie(_rand(tcpr.find(W + "tcBorders")) if tcpr is not None else None)
                aussen, self.senke = self.senke, []
                self.block(tc, {"rpr": rpr, "grund": self.fuellung(shd)})
                je_zelle.append(self.senke)
                self.senke = aussen
            if self.tiefe == 1 and self.umbruch_offen and self.fliesst:
                self.seitenwechsel()                       # a row with a stored page break starts the new page
            if all(len(z) <= 1 for z in je_zelle):         # a simple row prints as one line
                text = " ".join(z[0] for z in je_zelle if z)
                if text.strip():
                    self.senke.append(text)
            else:
                for z in je_zelle:
                    self.senke.extend(z)
        self.tiefe -= 1

    # ---- parts

    def teil(self, root, bereich):
        """The text lines of a header, footer or notes part (counted like the body)."""
        alt = (self.puffer, self.senke, self.fliesst, self.bereich, self.felder, self.tiefe)
        self.puffer, self.senke, self.fliesst, self.bereich, self.felder, self.tiefe = [], [], False, bereich, [], 0
        self.im_rand = bereich == "kopf"
        self.block(root, None)
        self.im_rand = False
        zeilen = self.senke
        self.puffer, self.senke, self.fliesst, self.bereich, self.felder, self.tiefe = alt
        return zeilen

    def lesen(self):
        root = self.paket.xml(self.haupt)
        body = root.find(W + "body") if root is not None else None
        if body is None:
            raise _Unlesbar("Datei nicht lesbar: Das Word-Dokument enthält keinen Textteil.")
        # sections: page size, first-page header, how each section starts
        alte = {id(s) for c in body.iter(W + "sectPrChange") for s in c.iter(W + "sectPr")}
        geerbt = {}
        for sp in body.iter(W + "sectPr"):
            if id(sp) in alte:
                continue
            for ref in sp:
                if ref.tag in (W + "headerReference", W + "footerReference"):
                    geerbt[(_lokal(ref.tag)[:6], ref.get(W + "type") or "default")] = ref.get(R + "id")
            typ, pg, titel = sp.find(W + "type"), sp.find(W + "pgSz"), sp.find(W + "titlePg")
            masse = None                                   # page size in points (the file gives twentieths)
            if pg is not None and _punkt(pg.get(W + "w"), 20) and _punkt(pg.get(W + "h"), 20):
                masse = (_punkt(pg.get(W + "w"), 20), _punkt(pg.get(W + "h"), 20))
                if not self.abschnitte:                    # the text area of a page of the first section
                    rand = sp.find(W + "pgMar")
                    r = {k: abs(_zahl(rand.get(W + k), 0.0)) / 20 if rand is not None else 0.0
                         for k in ("left", "right", "top", "bottom")}
                    breite, hoehe = masse[0] - r["left"] - r["right"], masse[1] - r["top"] - r["bottom"]
                    self.textflaeche = breite * hoehe if breite > 72 and hoehe > 72 else masse[0] * masse[1]
            self.abschnitte.append({
                "neue_seite": (typ.get(W + "val") if typ is not None else "nextPage") in ("nextPage", "oddPage",
                                                                                          "evenPage"),
                "masse": masse, "titelseite": titel is not None and _an(titel), "teile": dict(geerbt)})
        self.fliesst = True
        self.block(body, None)
        self.zeile()
        self.fliesst = False
        if not self.seiten[-1] and len(self.seiten) > 1:
            self.seiten.pop()
        # headers and footers that some section really uses
        self.kopf_fuss = {}
        for a in self.abschnitte:
            for (art, typ), rid in a["teile"].items():
                aktiv = typ == "default" or (typ == "first" and a["titelseite"]) or (typ == "even" and self.gerade_kopf)
                if aktiv and rid in self.rels and rid not in self.kopf_fuss:
                    wurzel = self.paket.xml(self.rels[rid][1])
                    self.kopf_fuss[rid] = self.teil(wurzel, "kopf") if wurzel is not None else []
        self.noten = []
        for typ in ("footnotes", "endnotes"):
            wurzel = self.paket.xml(self.paket.ziel(self.rels, typ))
            for note in (wurzel if wurzel is not None else ()):
                if note.get(W + "type") in (None, "normal"):
                    self.noten.extend(self.teil(note, "note"))
        return self

    def rand_der_seite(self, erste):
        """(header lines, footer lines) of the first section, for its first page or its later pages."""
        if not self.abschnitte:
            return [], []
        a = self.abschnitte[0]
        typ = "first" if erste and a["titelseite"] else "default"
        return (self.kopf_fuss.get(a["teile"].get(("header", typ)), []),
                self.kopf_fuss.get(a["teile"].get(("footer", typ)), []))


def _mz(n, einzahl, mehrzahl):
    return f"{n} {einzahl if n == 1 else mehrzahl}"


def _erkennen(alle, seiten, dienststelle):
    """telefon / email / elemente of the text detectors for the lines of a file."""
    return gt.telefon(alle, dienststelle), gt.emails(alle), gt.elemente(seiten, dienststelle)


def _farben_fertig(fp, p, datei):
    """Move the colour profile into the profile; the private keys become hinweise."""
    hin = p["hinweise"]
    farben = fp["farben"]
    links = [f["hex"] for f in farben if f["nur_link"]]     # the same wording as for a PDF
    if links:
        hin.append(gt.H_LINKFARBE % ", ".join(links))
    elif len(farben) == 1 and farben[0]["hex"] == "#0000ff":
        hin.append("Die einzige Farbe ist reines Blau #0000ff (nicht nur für Adressen und verlinkte Wörter "
                   "gesetzt).")
    if fp["_unter"]:
        hin.append(gt.H_FARBE_UNTER_SCHWELLE + " (weniger als %d Zeichen, keine gefüllte Fläche, keine Linie), "
                   "nicht als Farbe des Formulars gezählt: %s."
                   % (MIN_ZEICHEN_FARBE, ", ".join("%s (%s)" % u for u in fp["_unter"])))
    if any(f["_flaeche"] for f in farben):
        hin.append(f"Flächenanteile der Farben sind in einer {datei}-Datei nicht messbar; gefüllte "
                   + ("Absätze und Tabellenzellen" if datei == "Word" else "Zellen") + " zählen als vorhanden.")
    for f in farben:
        for k in ("_gewicht", "_flaeche"):
            del f[k]
    del fp["_unter"]
    p.update(fp)


# The tightest setting assumed when the stored page count is held against the amount of text:
# every glyph 0.4 em wide, every line 1 em high, the text area filled to the last corner.
ENG_BREITE, ENG_HOEHE = 0.4, 1.0


def _word_profil(w, titel, gespeichert, dienststelle, formular=None):
    p = _rahmen("word")
    hin = p["hinweise"]

    # pages: the count of the last save, unless the stored page breaks or the amount of text contradict it
    nachweis = len(w.seiten)
    bedarf = sum(n * ENG_BREITE * pt * ENG_HOEHE * pt for (bereich, _n, pt, *_r), n in w.z.items() if bereich != "kopf")
    zu_eng = bool(gespeichert and w.textflaeche and bedarf > gespeichert * w.textflaeche)
    if gespeichert is None:
        hin.append(gt.H_SEITENZAHL + " Die Datei speichert keine Seitenzahl.")
    elif nachweis > gespeichert:
        hin.append(gt.H_SEITENZAHL + f" Die Dokumenteigenschaften nennen {_mz(gespeichert, 'Seite', 'Seiten')}, "
                   f"die gespeicherten Seitenumbrüche belegen mindestens {nachweis}.")
    elif zu_eng:
        hin.append(gt.H_SEITENZAHL + f" Die Dokumenteigenschaften nennen {_mz(gespeichert, 'Seite', 'Seiten')}; "
                   "so viel Text hat darauf auch eng gesetzt keinen Platz.")
    else:
        p["seiten"] = gespeichert
        hin.append("Seitenzahl aus den Dokumenteigenschaften (Stand beim letzten Speichern), nicht neu umbrochen.")
    n_seiten = p["seiten"] or nachweis
    mehrseitig = n_seiten > 1 or zu_eng

    formate = [seitenformat(*a["masse"]) for a in w.abschnitte if a["masse"]]
    if w.abschnitte and w.abschnitte[0]["masse"]:
        p["seitenformat"] = formate[0]
        if any(f != formate[0] for f in formate):
            hin.append(gt.H_FORMAT_ABSCHNITTE + "; angegeben ist das Format der ersten Seite.")
    else:
        hin.append("Seitenformat nicht messbar: Die Datei legt für die erste Seite keines fest.")

    # fonts and sizes
    schrift, platzhalter = _schriftprofil(w.z, w.kasten, w.eingebettet)
    p.update(schrift)
    knapp_hinweise(p["schriften"], p["groessen"], hin)
    if not w.n:
        hin.append("Kein Text in der Datei gefunden.")
    if platzhalter:
        hin.append(gt.H_PLATZHALTERNAME + " (" + ", ".join(platzhalter) + "), wie ihn "
                   "PDF-Programme vergeben; eine Schrift dieses Namens gibt es nicht, und was stattdessen "
                   "angezeigt wird, ist nicht gemessen.")
    if w.ohne_schrift:
        hin.append(f"Für {_mz(w.ohne_schrift, 'Zeichen', 'Zeichen')} nennt die Datei keine Schrift; "
                   f"gezählt mit der Word-Vorgabe {w.WORD_SCHRIFT}.")
    if w.ohne_groesse:
        hin.append(f"Für {_mz(w.ohne_groesse, 'Zeichen', 'Zeichen')} nennt die Datei keine Schriftgrösse; "
                   "gezählt mit der Word-Vorgabe 10 Punkt.")
    if w.tabstil_alt:
        hin.append("Tabellenformatvorlage mit eigener Schriftgrösse in einem Dokument im älteren Word-Modus: "
                   "Word kann die Grösse in diesen Tabellen anders auflösen.")

    # colours
    text, link = Counter(), Counter()
    sprache = Counter()
    for (_bereich, _name, _pt, farbe, lang, ist_link), n in w.z.items():
        sprache[lang] += n
        if farbe:
            text[farbe] += n
            link[farbe] += n if ist_link else 0
    # link text: set as a hyperlink (element, field or character style), or nothing but internet and e-mail addresses
    nur_link = {h for h in text if (link[h] == text[h] or _nur_adressen(w.stuecke.get(h, [])) >= 0.9)
                and not (w.flaeche.get(h) or w.lauf.get(h) or w.linien.get(h))}
    _farben_fertig(_farbprofil(text, w.n, w.flaeche, w.absaetze, w.lauf, w.linien, nur_link), p, "Word")
    if w.thema_ungleich:
        hin.append(f"{_mz(w.thema_ungleich, 'Farbangabe weicht', 'Farbangaben weichen')} vom Farbschema des "
                   "Dokuments ab; gezählt ist die Farbe aus dem Farbschema.")
    if w.muster:
        hin.append("Gemusterte Füllungen (" + ", ".join(sorted(w.muster)) + ") sind nicht als Farbe gezählt.")
    if w.bilder:
        hin.append("Enthält Bilder; Farben, Schrift, Telefonnummern und E-Mail-Adressen in Bildern sind nicht gemessen.")
    if w.formen:
        hin.append("Gezeichnete Formen und Textfelder: Füllungen und Linien sind nicht ausgewertet "
                   "(der Text der Textfelder ist gezählt).")
    if w.fremd:
        hin.append("Eingebetteter Inhalt in einem anderen Dateiformat ist nicht gelesen.")

    # accessibility facts a Word file carries
    b = p["barrierefrei"]
    if sprache:
        b["sprache"] = max(sprache.items(), key=lambda x: (x[1], x[0] or ""))[0]
        if b["sprache"] is None:
            hin.append("Sprache nicht messbar: Für den grössten Teil des Textes nennt die Datei keine.")
    else:
        b["sprache"] = w.stile.std.get("lang")
    b["titel"], b["titel_art"], b["ueberschriften"] = titel, titel_art(titel, formular), w.ueberschriften > 0
    if titel and b["titel_art"] is None:
        hin.append(H_TITEL_OHNE_NAMEN)
    if w.ueberschriften == 1:
        hin.append(gt.H_EINE_UEBERSCHRIFT + "; eine Gliederung durch Überschriften ist das nicht.")
    # fields the applicant fills in stand in the text; a field in the header or footer (the office's own
    # drop-down for its phone extension) does not make the Formular fillable
    p["ausfuellbar"] = w.formfelder + w.steuerelemente - w.felder_rand > 0
    if w.felder_rand:
        hin.append(f"{_mz(w.felder_rand, 'Formularfeld steht', 'Formularfelder stehen')} in der Kopf- oder Fusszeile "
                   "und " + ("zählt" if w.felder_rand == 1 else "zählen") + " nicht als ausfüllbar.")

    # text detectors: the lines by page, with the header and footer of the first section around each page
    kopf1, fuss1 = w.rand_der_seite(True)
    kopf, fuss = w.rand_der_seite(False)
    seiten = []
    for i in range(n_seiten):
        k, f = (kopf1, fuss1) if i == 0 else (kopf, fuss)
        rumpf = w.seiten[i] if i < nachweis else []
        seiten.append([_setzen(z, i + 1, n_seiten) for z in k + rumpf + f])
    seiten[nachweis - 1].extend(_setzen(z, nachweis, n_seiten) for z in w.noten)
    uebrige = [z for rid, zeilen in w.kopf_fuss.items() for z in zeilen
               if not any(zeilen is x for x in (kopf1, fuss1))]
    alle = [_setzen(z, 1, n_seiten) for z in kopf1 + [z for s in w.seiten for z in s] + fuss1 + uebrige + w.noten]
    p["telefon"], p["email"], el = _erkennen(alle, seiten, dienststelle)
    vorlage = next((z for z in fuss + kopf + fuss1 + kopf1 + uebrige + [z for s in w.seiten for z in s]
                    if SEITE in z), None)
    if p["seiten"] is None and nachweis == 1:              # page count unknown: only a field is evidence
        el["seitenzahlen"] = {"vorhanden": True if w.seitenfeld else False if mehrseitig else None,
                              "muster": _kuerzen(vorlage.replace(SEITE, "1").replace(ANZAHL, "N")) if vorlage else None}
    elif n_seiten > 1 and not el["seitenzahlen"]["vorhanden"] and w.seitenfeld:
        el["seitenzahlen"] = {"vorhanden": True, "muster": _kuerzen(_setzen(vorlage, 1, n_seiten)) if vorlage else None}
    if mehrseitig and nachweis == 1:
        hin.append(gt.H_OHNE_UMBRUCH + " wurde im ganzen Dokument statt nur auf Seite 1 gesucht.")
    p["elemente"] = el
    return p


FEHLER_ZEIGEN = False        # True: an unexpected file structure raises instead of giving 'nicht_messbar'


def _gemessen(pfad, alt_endungen, name, ordner, messen):
    """Open the package and measure it; whatever makes the file unreadable becomes the one
    hinweis of a 'nicht_messbar' profile, so that a scan over all Formulare never stops."""
    paket, grund = _oeffnen(pfad, alt_endungen, name)
    if paket is None:
        return _nicht_messbar(grund)
    try:
        with paket.z:
            haupt = (paket.ziel(paket.rels(""), "officeDocument")
                     or ordner + ("document.xml" if name == "Word" else "workbook.xml"))
            if not paket.hat(haupt) or not haupt.lower().startswith(ordner):
                raise _Unlesbar(f"Datei nicht lesbar: kein {name}-Dokument im heutigen Format.")
            return messen(paket, haupt)
    except _Unlesbar as e:
        return _nicht_messbar(str(e))
    except (zipfile.BadZipFile, ET.ParseError, zlib.error, NotImplementedError, EOFError):
        return _nicht_messbar("Datei nicht lesbar: beschädigt oder verschlüsselt.")
    except (RuntimeError, LookupError, ValueError, TypeError, AttributeError) as e:
        if FEHLER_ZEIGEN:
            raise
        return _nicht_messbar(f"Datei nicht lesbar: unerwarteter Aufbau ({type(e).__name__}).")


def messen_docx(pfad, dienststelle=None, formular=None):
    """The measured profile of a Word Formular (.docx); a .doc gives messart 'nicht_messbar'.
    `dienststelle` (service.dienststelle, optional) is passed to the text detectors, `formular`
    (form.title, optional) is the name the document title is held against."""
    def messen(paket, haupt):
        w = _Word(paket, haupt).lesen()
        return _word_profil(w, *_eigenschaften(paket), dienststelle, formular)
    return _gemessen(pfad, (".doc", ".dot"), "Word", "word/", messen)


# ---------------------------------------------------------------- Excel

_PAPIER = {1: (216, 279), 3: (279, 432), 5: (216, 356), 7: (184, 267), 8: (297, 420), 9: (210, 297),
           10: (210, 297), 11: (148, 210), 12: (257, 364), 13: (182, 257)}          # paperSize → mm, upright
_X_THEMA = ("lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
            "hlink", "folHlink")
_INDEXIERT = ("000000 FFFFFF FF0000 00FF00 0000FF FFFF00 FF00FF 00FFFF 000000 FFFFFF FF0000 00FF00 0000FF FFFF00 "
              "FF00FF 00FFFF 800000 008000 000080 808000 800080 008080 C0C0C0 808080 9999FF 993366 FFFFCC CCFFFF "
              "660066 FF8080 0066CC CCCCFF 000080 FF00FF FFFF00 00FFFF 800080 800000 008080 0000FF 00CCFF CCFFFF "
              "CCFFCC FFFF99 99CCFF FF99CC CC99FF FFCC99 3366FF 33CCCC 99CC00 FFCC00 FF9900 FF6600 666699 969696 "
              "003366 339966 003300 333300 993300 993366 333399 333333").split()
_DML_NAME = {"tx1": "dk1", "bg1": "lt1", "tx2": "dk2", "bg2": "lt2"}
_DML_FEST = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000", "blue": "#0000ff",
             "yellow": "#ffff00", "gray": "#808080", "grey": "#808080"}


def _kinder(el, pfad):
    ziel = el.find(pfad) if el is not None else None
    return list(ziel) if ziel is not None else []


def _spalte(ref):
    """Column number (1 = A) of a cell reference like «AB12»; None without one."""
    n = 0
    for c in ref or "":
        if not c.isalpha():
            break
        n = n * 26 + ord(c.upper()) - 64
    return n or None


_XZEICHEN = re.compile(r"_x([0-9A-Fa-f]{4})_")
_BEREICH = re.compile(r"!\$?([A-Z]{1,3})?\$?(\d+)?(:\$?([A-Z]{1,3})?\$?(\d+)?)?(?=,|$)")


def _druckbereich(text):
    """The print area of a sheet as [(first column, last column, first row, last row)], None = open
    end; an empty list when the defined name cannot be read (then the whole sheet is measured)."""
    out = []
    for m in _BEREICH.finditer(text or ""):
        s1, z1, bis, s2, z2 = m.groups()
        if not (s1 or z1):
            return []
        if not bis:
            s2, z2 = s1, z1
        out.append((_spalte(s1), _spalte(s2), _zahl(z1, None, int), _zahl(z2, None, int)))
    return out


def _xtext(text):
    """A string of the file with its «_x000D_» escapes turned back into the characters they stand for."""
    return _XZEICHEN.sub(lambda m: chr(int(m.group(1), 16)), text or "") if text and "_x" in text else (text or "")


def _im_bereich(bereich, spalte, zeile):
    return not bereich or any((s1 is None or s1 <= spalte) and (s2 is None or spalte <= s2)
                              and (z1 is None or z1 <= zeile) and (z2 is None or zeile <= z2)
                              for s1, s2, z1, z2 in bereich)


def _kopfzeile(code, blatt):
    """The text lines of an Excel header/footer code string («&L…&C…&R…»). Page number and page
    count become SEITE / ANZAHL; date, time, file name and formatting codes leave no text."""
    teile, akt, i, bild = [], [], 0, False
    while i < len(code):
        c = code[i]
        if c != "&":
            akt.append(c)
            i += 1
            continue
        d = code[i + 1:i + 2]
        i += 2
        if d in ("L", "C", "R"):
            teile.append("".join(akt))
            akt = []
        elif d == "P":
            akt.append(SEITE)
        elif d == "N":
            akt.append(ANZAHL)
        elif d == "A":
            akt.append(blatt)
        elif d == "&":
            akt.append("&")
        elif d == "G":
            bild = True
        elif d == '"':
            ende = code.find('"', i)
            i = ende + 1 if ende >= 0 else len(code)
        elif d == "K":
            i += 6
        elif d.isdigit():
            while i < len(code) and code[i].isdigit():
                i += 1
    teile.append("".join(akt))
    return [z.strip() for t in teile for z in t.splitlines() if z.strip()], bild


class _Excel:
    """One pass over an .xlsx: the text cells of the visible sheets by font, size and colour, the
    fills and border colours of the stored cells, the text lines by sheet."""

    def __init__(self, paket, haupt):
        self.paket, self.haupt = paket, haupt
        self.rels = paket.rels(haupt)
        self.thema = _Thema(paket.xml(paket.ziel(self.rels, "theme")))
        self.z, self.kasten, self.n = Counter(), {}, 0
        self.stuecke = {}             # text colour → the pieces of text set in it (for the link test)
        self.zellen = self.zahlzellen = self.unklar = self.ohne_schrift = self.form_ohne = self.ausserhalb = 0
        self.flaeche, self.linien = Counter(), Counter()
        self.muster = self.verlauf = self.bilder = self.formen = self.bedingt = False
        self.blaetter = []            # visible sheets: {"name", "zeilen", "kopf", "fuss", "papier"}
        self.versteckt = 0
        self._xf_memo = {}
        self._stile(paket.xml(paket.ziel(self.rels, "styles")))
        sst = paket.xml(paket.ziel(self.rels, "sharedStrings"))
        self.texte = [self._laeufe(si) for si in (sst if sst is not None else ()) if si.tag == S + "si"]

    # ---- styles

    def farbe(self, el):
        """'#rrggbb' of a colour element (rgb / theme + tint / indexed); None for automatic or unresolved."""
        if el is None or el.get("auto") in ("1", "true"):
            return None
        if el.get("rgb"):
            h = _hex(el.get("rgb"))
        elif el.get("theme") is not None:
            i = _zahl(el.get("theme"), -1, int)
            h = self.thema.farbe.get(_X_THEMA[i]) if 0 <= i < len(_X_THEMA) else None
        elif el.get("indexed") is not None:
            i = _zahl(el.get("indexed"), -1, int)
            h = self.palette[i] if 0 <= i < len(self.palette) else {64: "#000000", 65: "#ffffff"}.get(i)
        else:
            return None
        if h is None:
            self.unklar += 1
            return None
        tint = _zahl(el.get("tint"), 0.0)
        return _hls_tint(h, tint) if -1 <= tint <= 1 and tint else h

    def _stile(self, root):
        self.palette = ["#" + h.lower() for h in _INDEXIERT]
        for i, c in enumerate(_kinder(root, S + "colors/" + S + "indexedColors")):
            if i < len(self.palette) and _hex(c.get("rgb")):
                self.palette[i] = _hex(c.get("rgb"))
        self.fonts = _kinder(root, S + "fonts")
        self.fills = _kinder(root, S + "fills")
        self.borders = _kinder(root, S + "borders")
        self.xfs = [(_zahl(x.get("fontId"), 0, int), _zahl(x.get("fillId"), 0, int), _zahl(x.get("borderId"), 0, int))
                    for x in _kinder(root, S + "cellXfs")]

    def _schrift(self, el):
        """(name, pt, colour) as far as a font or rPr element sets them."""
        name = pt = farbe = None
        for k in (el if el is not None else ()):
            if k.tag in (S + "name", S + "rFont"):
                name = k.get("val")
            elif k.tag == S + "sz":
                pt = _punkt(k.get("val"))
            elif k.tag == S + "color":
                farbe = self.farbe(k)
        return name, pt, farbe

    def xf(self, s):
        """(font name, pt, text colour, fill colour, border colours) of a cell style index."""
        if s not in self._xf_memo:
            font, fill, border = self.xfs[s] if 0 <= s < len(self.xfs) else (0, 0, 0)
            name, pt, farbe = self._schrift(self.fonts[font] if 0 <= font < len(self.fonts) else None)
            grund = None
            f = self.fills[fill] if 0 <= fill < len(self.fills) else None
            pf = f.find(S + "patternFill") if f is not None else None
            if pf is not None:
                art = pf.get("patternType") or "none"
                if art == "solid":
                    grund = self.farbe(pf.find(S + "fgColor"))
                elif art != "none":
                    grund = "muster"
            elif f is not None and f.find(S + "gradientFill") is not None:
                grund = "verlauf"
            raender = []
            for seite in (self.borders[border] if 0 <= border < len(self.borders) else ()):
                if seite.get("style") not in (None, "none"):
                    h = self.farbe(seite.find(S + "color"))
                    if h:
                        raender.append(h)
            self._xf_memo[s] = (name, pt, farbe, grund, raender)
        return self._xf_memo[s]

    @staticmethod
    def _laeufe(si):
        """A string item as [(text, rPr element or None)]; phonetic runs are no text of the form."""
        out = [(_xtext(t.text), None) for t in si.findall(S + "t")]
        for r in si.findall(S + "r"):
            t = r.find(S + "t")
            out.append((_xtext(t.text) if t is not None else "", r.find(S + "rPr")))
        return out

    # ---- counting

    def zaehle(self, text, name, pt, farbe, bereich):
        n = sum(1 for c in text if not (c.isspace() or c in _UNSICHTBAR))
        if not n:
            return
        if not name or not pt:
            self.ohne_schrift += n
            return
        self.z[(bereich, name, pt, farbe, None, False)] += n
        self.kasten[name] = self.kasten.get(name, True) and all(c in _KASTEN or c.isspace() for c in text)
        self.n += n
        if farbe:
            teile = self.stuecke.setdefault(farbe, [])
            if len(teile) < 400:
                teile.extend(text.split())

    def blatt(self, name, ziel, bereich):
        """One visible sheet; `bereich` is its print area (empty: none defined, everything counts)."""
        root = self.paket.xml(ziel)
        if root is None:
            return
        info = {"name": name, "zeilen": [], "kopf": [], "fuss": [], "papier": None}
        weg = [(_zahl(c.get("min"), 0, int), _zahl(c.get("max"), 0, int)) for c in _kinder(root, S + "cols")
               if c.get("hidden") in ("1", "true")]
        verbunden = {}                                     # row → [(first column, last column, is the top row)]
        for m in _kinder(root, S + "mergeCells"):
            b = _BEREICH.search("!" + (m.get("ref") or ""))
            if b and b.group(1) and b.group(2) and b.group(4) and b.group(5):
                s1, s2, z1, z2 = _spalte(b.group(1)), _spalte(b.group(4)), int(b.group(2)), int(b.group(5))
                if z2 - z1 < 5000:
                    for z in range(z1, z2 + 1):
                        verbunden.setdefault(z, []).append((s1, s2, z == z1))
        zeile = 0
        for row in _kinder(root, S + "sheetData"):
            zeile = _zahl(row.get("r"), zeile + 1, int)
            if row.get("hidden") in ("1", "true"):
                continue
            texte, spalte = [], 0
            for c in row:
                if c.tag != S + "c":
                    continue
                spalte = _spalte(c.get("r")) or spalte + 1
                if any(a <= spalte <= b for a, b in weg):
                    continue
                if not _im_bereich(bereich, spalte, zeile):
                    self.ausserhalb += c.find(S + "v") is not None or c.find(S + "is") is not None
                    continue
                if any(s1 <= spalte <= s2 and not (oben and spalte == s1) for s1, s2, oben in verbunden.get(zeile, ())):
                    continue                               # covered by a merged cell: only its first cell shows
                name_, pt, farbe, grund, raender = self.xf(_zahl(c.get("s"), 0, int))
                self.zellen += 1
                if grund == "muster":
                    self.muster = True
                elif grund == "verlauf":
                    self.verlauf = True
                elif grund:
                    self.flaeche[grund] += 1
                for h in raender:
                    self.linien[h] += 1
                art, v = c.get("t"), c.find(S + "v")
                if art == "s":
                    i = _zahl(v.text if v is not None else None, -1, int)
                    laeufe = self.texte[i] if 0 <= i < len(self.texte) else []
                elif art == "inlineStr":
                    laeufe = self._laeufe(c.find(S + "is")) if c.find(S + "is") is not None else []
                elif art in ("str", "e"):                  # the text result of a formula, an error value («#DIV/0!»)
                    laeufe = [(_xtext(v.text) if v is not None else "", None)]
                else:
                    self.zahlzellen += v is not None and bool((v.text or "").strip())
                    continue
                for text, rpr in laeufe:                   # a rich-text run sets its own font over the cell's
                    n2, p2, f2 = self._schrift(rpr)
                    eigene_farbe = rpr is not None and rpr.find(S + "color") is not None
                    self.zaehle(text, n2 or name_, p2 or pt, f2 if eigene_farbe else farbe, "zelle")
                ganz = "".join(t for t, _r in laeufe)
                if ganz.strip():
                    texte.append(ganz)
            if any("\n" in t for t in texte):              # a cell with several lines keeps its lines
                info["zeilen"].extend(z for t in texte for z in t.splitlines() if z.strip())
            elif texte:
                info["zeilen"].append(" ".join(t.strip() for t in texte))
        if root.find(S + "conditionalFormatting") is not None:
            self.bedingt = True
        ps = root.find(S + "pageSetup")
        if ps is not None and ps.get("paperSize") is not None:
            info["papier"] = (_zahl(ps.get("paperSize"), None, int), ps.get("orientation"))
        hf = root.find(S + "headerFooter")
        for k in (hf if hf is not None else ()):
            art = _lokal(k.tag)
            erste = art.startswith("first") and hf.get("differentFirst") in ("1", "true")
            if art in ("oddHeader", "oddFooter") or erste:
                zeilen, bild = _kopfzeile(k.text or "", name)
                self.bilder = self.bilder or bild
                ziel_liste = info["kopf" if art.endswith("Header") else "fuss"]
                ziel_liste.extend(z for z in zeilen if z not in info["kopf"] + info["fuss"])
        rels = self.paket.rels(ziel)
        for typ, teil in rels.values():
            if typ == "drawing":
                zeichnung = self.paket.xml(teil)
                if zeichnung is not None:
                    self.zeichnung(zeichnung, info["zeilen"], bereich)
        self.blaetter.append(info)

    # ---- drawings: text boxes and the labels of form controls

    def dml_farbe(self, fuell):
        """'#rrggbb' of a DrawingML solid fill; None for none; counts what this module cannot resolve."""
        for k in (fuell if fuell is not None else ()):
            art = _lokal(k.tag)
            if art == "srgbClr":
                h = _hex(k.get("val"))
            elif art == "schemeClr":
                h = self.thema.farbe.get(_DML_NAME.get(k.get("val"), k.get("val")))
            elif art == "sysClr":
                h = _hex(k.get("lastClr"))
            elif art == "prstClr":
                h = _DML_FEST.get(k.get("val"))
            else:
                h = None
            if h is None:
                self.unklar += 1
                return None
            hh, l, s = colorsys.rgb_to_hls(*_rgb(h))
            for t in k:
                wert = _zahl(t.get("val"), 100000.0) / 100000
                if not 0 <= wert <= 10:
                    wert = 1.0
                if t.tag == A + "lumMod":
                    l *= wert
                elif t.tag == A + "lumOff":
                    l += wert
                elif t.tag != A + "alpha":                 # tint, shade, satMod …: not resolved here
                    self.unklar += 1
                    return None
            return _von_rgb(*colorsys.hls_to_rgb(hh, min(1.0, max(0.0, l)), s))
        return None

    def zeichnung(self, eltern, zeilen, bereich):
        for k in eltern:
            t = k.tag
            if t == MC + "AlternateContent":
                self.zeichnung(_wahl(k), zeilen, bereich)
            elif t == XDR + "pic":
                self.bilder = True
            elif t in (XDR + "cxnSp", XDR + "graphicFrame"):
                self.formen = True
            elif t == XDR + "sp":
                self.form(k, zeilen)
            else:
                von = k.find(XDR + "from")                 # an anchor: where the drawing sits on the sheet
                if von is not None and not _im_bereich(bereich, _zahl(von.findtext(XDR + "col"), 0, int) + 1,
                                                       _zahl(von.findtext(XDR + "row"), 0, int) + 1):
                    continue
                self.zeichnung(k, zeilen, bereich)

    def form(self, sp, zeilen):
        """A drawn shape: its text counts where the run names its size; fill and outline are not read."""
        kopf = sp.find(XDR + "nvSpPr/" + XDR + "cNvPr")
        if kopf is None or kopf.get("hidden") not in ("1", "true"):   # hidden: the stand-in of a form control
            self.formen = True
        ref = sp.find(XDR + "style/" + A + "fontRef")
        thema_schrift = self.thema.name("+mj-lt" if ref is not None and ref.get("idx") == "major" else "+mn-lt")
        for absatz in sp.iter(A + "p"):
            vorgabe = absatz.find(A + "pPr/" + A + "defRPr")
            zeile = []
            for r in absatz:
                if r.tag == A + "br":
                    zeile.append("\n")
                    continue
                if r.tag not in (A + "r", A + "fld"):
                    continue
                t = r.find(A + "t")
                text = (t.text or "") if t is not None else ""
                zeile.append(text)
                rpr = r.find(A + "rPr")
                pt = name = None
                for quelle in (rpr, vorgabe):
                    if quelle is not None:
                        pt = pt or _punkt(quelle.get("sz"), 100)
                        latin = quelle.find(A + "latin")
                        if name is None and latin is not None and latin.get("typeface"):
                            name = latin.get("typeface")
                if name and name.startswith("+"):
                    name = self.thema.name(name)
                name = name or thema_schrift
                n = sum(1 for c in text if not c.isspace())
                if pt and name:
                    farbe = self.dml_farbe(rpr.find(A + "solidFill")) if rpr is not None else None
                    self.zaehle(text, name, pt, farbe, "form")
                else:
                    self.form_ohne += n
            zeilen.extend(z for z in "".join(zeile).splitlines() if z.strip())

    def lesen(self):
        root = self.paket.xml(self.haupt)
        blaetter = _kinder(root, S + "sheets")
        if root is None or not blaetter:
            raise _Unlesbar("Datei nicht lesbar: Die Excel-Datei enthält kein Tabellenblatt.")
        bereiche = {_zahl(d.get("localSheetId"), -1, int): _druckbereich(d.text)
                    for d in _kinder(root, S + "definedNames") if d.get("name") == "_xlnm.Print_Area"}
        for i, b in enumerate(blaetter):
            typ, ziel = self.rels.get(b.get(R + "id"), (None, None))
            if typ != "worksheet":
                continue                                   # chart and dialog sheets carry no cells
            if b.get("state") in ("hidden", "veryHidden"):
                self.versteckt += 1
                continue
            self.blatt(b.get("name") or "", ziel, bereiche.get(i, []))
        return self


def _blattformat(papier):
    """seitenformat of a sheet's (paperSize, orientation); None when either is missing or unknown."""
    if not papier or papier[0] not in _PAPIER or papier[1] not in ("portrait", "landscape"):
        return None
    b, h = (mm * 72 / 25.4 for mm in _PAPIER[papier[0]])
    return seitenformat(h, b) if papier[1] == "landscape" else seitenformat(b, h)


def _excel_profil(x, titel, dienststelle, formular=None):
    p = _rahmen("excel")
    hin = p["hinweise"]
    hin.append(gt.H_SEITENZAHL + " Wie viele Seiten eine Excel-Datei druckt, entscheidet sich erst beim Drucken.")
    if x.versteckt:
        hin.append(f"{_mz(x.versteckt, 'ausgeblendetes Tabellenblatt ist', 'ausgeblendete Tabellenblätter sind')} "
                   "nicht gemessen.")

    # page format of the first visible sheet
    formate = [_blattformat(b["papier"]) for b in x.blaetter]
    if formate and formate[0]:
        p["seitenformat"] = formate[0]
        if any(f and f != formate[0] for f in formate[1:]):
            hin.append(gt.H_FORMAT_BLAETTER + "; angegeben ist das Format des ersten Blatts.")
    else:
        hin.append("Seitenformat nicht messbar: Das erste Tabellenblatt legt kein bekanntes Papierformat "
                   "mit Ausrichtung fest.")

    p.update(_schriftprofil(x.z, x.kasten, None)[0])
    knapp_hinweise(p["schriften"], p["groessen"], hin)
    if not x.n:
        hin.append("Kein Text in den sichtbaren Tabellenblättern gefunden.")
    if x.ausserhalb:
        hin.append(f"{_mz(x.ausserhalb, 'Zelle mit Inhalt', 'Zellen mit Inhalt')} ausserhalb des Druckbereichs "
                   f"{'ist' if x.ausserhalb == 1 else 'sind'} nicht gemessen.")
    if x.zahlzellen:
        hin.append(f"{_mz(x.zahlzellen, 'Zelle mit Zahl oder Formelwert ist', 'Zellen mit Zahlen oder Formelwerten sind')} "
                   "bei Schrift und Grösse nicht gezählt (ihre Anzeige hängt vom Zahlenformat ab).")
    if x.ohne_schrift:
        hin.append(f"{_mz(x.ohne_schrift, 'Zeichen', 'Zeichen')} ohne Schrift- oder Grössenangabe in der Datei "
                   "sind nicht gezählt.")
    if x.form_ohne:
        hin.append(f"{_mz(x.form_ohne, 'Zeichen', 'Zeichen')} in gezeichneten Formen ohne eigene Grössenangabe "
                   "sind bei Schrift und Grösse nicht gezählt.")

    text = Counter()
    for key, n in x.z.items():
        if key[3]:
            text[key[3]] += n
    nur_link = {h for h in text if _nur_adressen(x.stuecke.get(h, [])) >= 0.9
                and not (x.flaeche.get(h) or x.linien.get(h))}
    _farben_fertig(_farbprofil(text, x.n, x.flaeche, x.zellen, {}, x.linien, nur_link), p, "Excel")
    if x.unklar:
        hin.append(f"{_mz(x.unklar, 'Farbangabe liess', 'Farbangaben liessen')} sich nicht auflösen "
                   "und fehlen in dieser Messung.")
    if x.muster or x.verlauf:
        hin.append("Gemusterte Füllungen und Farbverläufe sind nicht als Farbe gezählt.")
    if x.bedingt:
        hin.append("Bedingte Formatierungen sind nicht ausgewertet.")
    if x.bilder:
        hin.append("Enthält Bilder; Farben, Schrift, Telefonnummern und E-Mail-Adressen in Bildern sind nicht gemessen.")
    if x.formen:
        hin.append("Gezeichnete Formen und Textfelder: Füllungen und Linien sind nicht ausgewertet "
                   "(ihr Text ist gezählt, soweit er eine Grössenangabe trägt).")

    b = p["barrierefrei"]
    b["titel"], b["titel_art"] = titel, titel_art(titel, formular)
    if titel and b["titel_art"] is None:
        hin.append(H_TITEL_OHNE_NAMEN)

    # text detectors: one «page» per visible sheet; page numbers come only from header/footer codes
    seiten = [[z.replace(SEITE, "1").replace(ANZAHL, "N") for z in bl["kopf"] + bl["zeilen"] + bl["fuss"]]
              for bl in x.blaetter]
    p["telefon"], p["email"], el = _erkennen([z for s in seiten for z in s], seiten, dienststelle)
    vorlage = next((z for bl in x.blaetter for z in bl["fuss"] + bl["kopf"] if SEITE in z), None)
    el["seitenzahlen"] = {"vorhanden": True if vorlage else None,
                          "muster": _kuerzen(vorlage.replace(SEITE, "1").replace(ANZAHL, "N")) if vorlage else None}
    p["elemente"] = el
    return p


def messen_xlsx(pfad, dienststelle=None, formular=None):
    """The measured profile of an Excel Formular (.xlsx); an .xls gives messart 'nicht_messbar'.
    `dienststelle` (service.dienststelle, optional) is passed to the text detectors, `formular`
    (form.title, optional) is the name the document title is held against."""
    def messen(paket, haupt):
        x = _Excel(paket, haupt).lesen()
        return _excel_profil(x, _eigenschaften(paket)[0], dienststelle, formular)
    return _gemessen(pfad, (".xls", ".xlt"), "Excel", "xl/", messen)


# ---------------------------------------------------------------- self-test

_T_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_T_OD = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_T_NS = (f'xmlns:w="{_T_W}" xmlns:r="{_T_OD}" '
         'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
         'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
         'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
         'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
         'xmlns:v="urn:schemas-microsoft-com:vml"')
_T_THEMA = '''<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:themeElements>
<a:clrScheme name="x"><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="1F497D"/></a:dk2>
<a:lt2><a:srgbClr val="EEECE1"/></a:lt2><a:accent1><a:srgbClr val="4F81BD"/></a:accent1>
<a:hlink><a:srgbClr val="0000FF"/></a:hlink></a:clrScheme>
<a:fontScheme name="x"><a:majorFont><a:latin typeface="Cambria"/></a:majorFont>
<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/></a:minorFont></a:fontScheme>
</a:themeElements></a:theme>'''
_T_KERN = ('<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
           'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>%s</dc:title></cp:coreProperties>')


def _t_rels(*ziele):
    return ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="{rid}" Type="{_T_OD}/{typ}" Target="{ziel}"/>' for rid, typ, ziel in ziele)
            + "</Relationships>")


def _t_zip(teile):
    import io
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        for name, inhalt in teile.items():
            z.writestr(name, inhalt)
    puffer.seek(0)
    return puffer


def _t_docx():
    """A small Word file that uses every level of the style hierarchy once."""
    stile = f'''<w:styles {_T_NS}><w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:asciiTheme="minorHAnsi" w:hAnsiTheme="minorHAnsi"/><w:sz w:val="22"/><w:lang w:val="de-CH"/>
</w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Standard"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Basis"><w:name w:val="Basis"/><w:basedOn w:val="Standard"/>
 <w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="U1"><w:name w:val="heading 1"/><w:basedOn w:val="Basis"/>
 <w:rPr><w:sz w:val="32"/><w:color w:val="4F81BD" w:themeColor="accent1"/></w:rPr></w:style>
<w:style w:type="character" w:styleId="Rot"><w:name w:val="Rot"/><w:rPr><w:color w:val="FF0000"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="Raster"><w:name w:val="Table Grid"/><w:rPr><w:sz w:val="18"/></w:rPr>
 <w:tblStylePr w:type="firstRow"><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="FFFF00"/></w:tcPr></w:tblStylePr>
</w:style></w:styles>'''
    feld = ('<w:r><w:fldChar w:fldCharType="begin">%s</w:fldChar></w:r><w:r><w:instrText> %s </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>%s</w:t></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
    feldbox = "<w:txbxContent><w:p><w:r><w:t>Im Textfeld</w:t></w:r></w:p></w:txbxContent>"
    text = f'''<w:document {_T_NS}><w:body>
<w:p><w:pPr><w:pStyle w:val="U1"/></w:pPr><w:r><w:t>Gesuch um einen Beitrag an die Kosten</w:t></w:r></w:p>
<w:p><w:r><w:t>Kanton Schaffhausen, Veterinäramt</w:t></w:r></w:p>
<w:p><w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t>Tel. 052 632 71 01</w:t></w:r>
 <w:r><w:rPr><w:rStyle w:val="Rot"/></w:rPr><w:t xml:space="preserve"> Pflichtfelder sind rot markiert</w:t></w:r></w:p>
<w:tbl><w:tblPr><w:tblStyle w:val="Raster"/><w:tblLook w:val="0620" w:firstRow="1" w:noHBand="1" w:noVBand="1"/></w:tblPr>
 <w:tr><w:tc><w:p><w:r><w:t>Name</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Vorname</w:t></w:r></w:p></w:tc></w:tr>
 <w:tr><w:tc><w:p><w:r><w:t>Muster</w:t></w:r></w:p></w:tc>
  <w:tc><w:p>{feld % ("<w:ffData/>", "FORMTEXT", "Hans")}<w:r><w:br w:type="page"/></w:r></w:p></w:tc></w:tr></w:tbl>
<w:p><w:sdt><w:sdtPr><w14:checkbox/></w:sdtPr><w:sdtContent><w:r>
 <w:rPr><w:rFonts w:ascii="MS Gothic" w:eastAsia="MS Gothic" w:hAnsi="MS Gothic" w:hint="eastAsia"/></w:rPr>
 <w:t>☐</w:t></w:r></w:sdtContent></w:sdt><w:r><w:t xml:space="preserve"> einverstanden</w:t></w:r></w:p>
<w:p><w:r><mc:AlternateContent>
 <mc:Choice Requires="wps"><w:drawing><wps:wsp><wps:txbx>{feldbox}</wps:txbx></wps:wsp></w:drawing></mc:Choice>
 <mc:Fallback><w:pict><v:rect><v:textbox>{feldbox}</v:textbox></v:rect></w:pict></mc:Fallback>
</mc:AlternateContent></w:r></w:p>
<w:p><w:del><w:r><w:delText>gestrichen</w:delText></w:r></w:del>
 <w:r><w:rPr><w:vanish/></w:rPr><w:t>versteckt</w:t></w:r><w:r><w:sym w:font="Wingdings" w:char="F0A8"/></w:r></w:p>
<w:p><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="B8CCE4" w:themeFill="accent1" w:themeFillTint="66"/></w:pPr>
 <w:r><w:t>Hinweis</w:t></w:r></w:p>
<w:p><w:r><w:lastRenderedPageBreak/><w:t>Zweite Seite mit der Unterschrift</w:t></w:r></w:p>
<w:sectPr><w:footerReference w:type="default" r:id="rId9"/><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>
</w:body></w:document>'''
    fuss = (f'<w:ftr {_T_NS}><w:p><w:r><w:rPr><w:sz w:val="14"/></w:rPr><w:t xml:space="preserve">Seite </w:t></w:r>'
            + feld % ("", "PAGE", "7") + '<w:r><w:t xml:space="preserve"> von </w:t></w:r>'
            + feld % ("", "NUMPAGES", "9") + "</w:p></w:ftr>")
    return {"_rels/.rels": _t_rels(("rId1", "officeDocument", "word/document.xml")),
            "word/_rels/document.xml.rels": _t_rels(("rId1", "styles", "styles.xml"), ("rId2", "theme", "theme/theme1.xml"),
                                                    ("rId9", "footer", "footer1.xml")),
            "word/document.xml": text, "word/styles.xml": stile, "word/footer1.xml": fuss,
            "word/theme/theme1.xml": _T_THEMA, "docProps/core.xml": _T_KERN % "Dokument1",
            "docProps/app.xml": '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
                                'extended-properties"><Pages>2</Pages></Properties>'}


def _t_docx2():
    """A second small Word file: a drop-down form field in the header (the office's own phone
    extension), a link colour on a typed address, a pale shading, no heading, no field in the text."""
    wahl = ('<w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:ddList><w:result w:val="1"/>'
            '<w:listEntry w:val="71 01"/><w:listEntry w:val="71 02"/></w:ddList></w:ffData></w:fldChar></w:r>'
            '<w:r><w:instrText> FORMDROPDOWN </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>')
    text = f'''<w:document {_T_NS}><w:body>
<w:p><w:r><w:t>Meldung einer Tierhaltung an das Veterinäramt</w:t></w:r></w:p>
<w:p><w:r><w:rPr><w:color w:val="0563C1"/></w:rPr><w:t>www.sh.ch/veterinaeramt/formulare</w:t></w:r></w:p>
<w:p><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="DBE5F1"/></w:pPr><w:r><w:t>Name und Vorname</w:t></w:r></w:p>
<w:sectPr><w:headerReference w:type="default" r:id="rId8"/><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>
</w:body></w:document>'''
    kopf = (f'<w:hdr {_T_NS}><w:p><w:r><w:t xml:space="preserve">Kanton Schaffhausen, Veterinäramt, Telefon +41 52 632 </w:t></w:r>'
            + wahl + "</w:p></w:hdr>")
    return {"_rels/.rels": _t_rels(("rId1", "officeDocument", "word/document.xml")),
            "word/_rels/document.xml.rels": _t_rels(("rId8", "header", "header1.xml")),
            "word/document.xml": text, "word/header1.xml": kopf, "docProps/core.xml": _T_KERN % "Logo hoch"}


def _t_xlsx():
    """A small workbook: a visible sheet with a print area, a hidden one, a rich text, two fills,
    a merged cell that covers a text, an error value."""
    ns = f'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="{_T_OD}"'
    return {"_rels/.rels": _t_rels(("rId1", "officeDocument", "xl/workbook.xml")),
            "xl/_rels/workbook.xml.rels": _t_rels(
                ("rId1", "worksheet", "worksheets/sheet1.xml"), ("rId2", "worksheet", "worksheets/sheet2.xml"),
                ("rId3", "styles", "styles.xml"), ("rId4", "sharedStrings", "sharedStrings.xml"),
                ("rId5", "theme", "theme/theme1.xml")),
            "xl/workbook.xml": f'''<workbook {ns}><sheets><sheet name="Formular" sheetId="1" r:id="rId1"/>
<sheet name="Listen" sheetId="2" state="hidden" r:id="rId2"/></sheets><definedNames>
<definedName name="_xlnm.Print_Area" localSheetId="0">Formular!$A$1:$C$10</definedName></definedNames></workbook>''',
            "xl/styles.xml": f'''<styleSheet {ns}><fonts><font><sz val="10"/><name val="Arial"/></font>
<font><b/><sz val="14"/><color theme="4"/><name val="Arial"/></font></fonts>
<fills><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFFF00"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor theme="4" tint="0.6"/></patternFill></fill></fills>
<borders><border><left/><right/></border></borders>
<cellXfs><xf fontId="0" fillId="0" borderId="0"/><xf fontId="1" fillId="0" borderId="0"/>
<xf fontId="0" fillId="2" borderId="0"/><xf fontId="0" fillId="3" borderId="0"/></cellXfs></styleSheet>''',
            "xl/sharedStrings.xml": f'''<sst {ns}><si><t>Gesuch um einen Beitrag</t></si><si><t>Kanton Schaffhausen</t></si>
<si><r><t xml:space="preserve">Tel. </t></r>
 <r><rPr><sz val="8"/><color rgb="FFFF0000"/><rFont val="Courier New"/></rPr><t>052 632 71 01</t></r></si>
<si><t>Name</t></si><si><t>ausserhalb</t></si><si><t>geheim</t></si></sst>''',
            "xl/worksheets/sheet1.xml": f'''<worksheet {ns}><sheetData>
<row r="1"><c r="A1" s="1" t="s"><v>0</v></c><c r="E1" t="s"><v>4</v></c></row>
<row r="2"><c r="A2" t="s"><v>1</v></c></row><row r="3"><c r="A3" t="s"><v>2</v></c></row>
<row r="4"><c r="A4" t="s"><v>3</v></c><c r="B4" s="2"/><c r="C4" s="3"/></row>
<row r="5"><c r="A5"><v>42</v></c></row>
<row r="6"><c r="A6" t="s"><v>3</v></c><c r="B6" t="s"><v>4</v></c></row>
<row r="7"><c r="A7" t="e"><v>#DIV/0!</v></c></row></sheetData>
<mergeCells count="1"><mergeCell ref="A6:B6"/></mergeCells>
<pageSetup paperSize="9" orientation="landscape"/>
<headerFooter><oddFooter>&amp;C&amp;8Seite &amp;P von &amp;N</oddFooter></headerFooter></worksheet>''',
            "xl/worksheets/sheet2.xml": f'''<worksheet {ns}><sheetData>
<row r="1"><c r="A1" t="s"><v>5</v></c></row></sheetData></worksheet>''',
            "xl/theme/theme1.xml": _T_THEMA, "docProps/core.xml": _T_KERN % "Beitragsgesuch"}


def _selbsttest():
    """Assertions on two small files built in memory and on the helpers."""
    n = [0]

    def gleich(ist, soll, was):
        n[0] += 1
        assert ist == soll, f"{was}: {ist!r} != {soll!r}"

    # --- helpers (the first four blocks hold the shared notions of gestaltung_pdf to what this module relies on)
    for name, soll in [("Arial", "Arial"), ("Arial (W1)", "Arial"), ("Times (TT)", "Times"), ("Calibri Light", "Calibri"),
                       ("Arial Narrow", "Arial Narrow"), ("Arial Black", "Arial Black"),
                       ("Times New Roman", "Times New Roman"), ("MinionPro-Regular", "Minion Pro"),
                       ("ABCDEF+ArialMT", "Arial"), ("TimesNewRomanPS-BoldMT", "Times New Roman"),
                       ("Futura Medium", "Futura"), ("Helvetica", "Helvetica"), ("MS Gothic", "MS Gothic"),
                       ("JUST", "JUST")]:
        gleich(_familie(name), (soll, False, False), "Familie von " + name)
    gleich([_familie(n) for n in ("Wingdings 2", "Segoe UI Symbol", "CIDFont+F2")],
           [("Wingdings 2", True, False), ("Segoe UI Symbol", True, False), ("CIDFont+F2", False, True)],
           "Symbolschriften und Platzhaltername")
    for titel, soll in [(None, "leer"), ("  ", "leer"), ("Dokument1", "generisch"), ("Microsoft Word - Gesuch", "generisch"),
                        ("gesuch_v3.docx", "generisch"), ("1", "generisch"), ("Formular", "generisch"),
                        ("Gesuch um Namensänderung", "aussagekraeftig"), ("Logo hoch", "ohne_bezug")]:
        gleich(titel_art(titel, "Namensänderung – Formular zur Einreichung eines Gesuches"), soll, f"Titelart von {titel!r}")
    gleich(titel_art("Gesuch um Namensänderung"), None, "Titelart ohne den Namen des Formulars")
    for h, soll in [("#ff0000", "Rot"), ("#ffc000", "Gelb"), ("#fff2cc", "Gelb"), ("#00b050", "Grün"),
                    ("#00b0f0", "Blau"), ("#0563c1", "Blau"), ("#7030a0", "Violett"), ("#ff00ff", "Magenta"),
                    ("#00ffff", "Türkis"), ("#ed7d31", "Orange"), ("#843c0c", "Braun")]:
        gleich(farbfamilie(h), soll, "Farbfamilie von " + h)
    gleich([ist_neutral(h) for h in ("#000000", "#808080", "#f2f2f2", "#ffffff", "#dbe5f1", "#b8cce4", "#201010")],
           [True, True, True, True, True, False, True], "neutral")
    gleich([ist_neutral(h, flaeche=True) for h in ("#f2f2f2", "#dbe5f1", "#e2efda", "#fff2cc", "#201010")],
           [True, False, False, False, True], "neutral als Füllung: ein blasser Farbton ist eine Farbe")
    gleich(seitenformat(11906 / 20, 16838 / 20), {"name": "A4 hoch", "breite_mm": 210, "hoehe_mm": 297}, "A4 hoch")
    gleich((_nah("#003366", "#003367"), _nah("#003366", "#0d3366")), (True, False), "nahe Farben")
    gleich(_helligkeit("#4f81bd", 0x99 / 255, True), "#95b3d7", "themeTint 99")
    gleich(_helligkeit("#99ccff", 0x40 / 255, False), "#003366", "themeShade 40")         # Word itself stores 003367
    gleich(_hls_tint("#4f81bd", 0.6), "#b9cde5", "Excel-Tint 0.6")
    gleich((_punkt("22", 2), _punkt("1100", 100), _punkt("NaN"), _punkt("0"), _punkt("1e9"), _punkt(None)),
           (11.0, 11.0, None, None, None, None), "Schriftgrössen")
    gleich(_kopfzeile('&L&8Gemeinde&R&"Arial,Bold"&8Seite &P von &N', "Blatt"),
           (["Gemeinde", f"Seite {SEITE} von {ANZAHL}"], False), "Kopfzeile")
    gleich(_kopfzeile("&L&G&C&A &D&R5.2016", "Budget"), (["Budget", "5.2016"], True), "Kopfzeile mit Bild und Blattname")
    gleich(_druckbereich("'Blatt 1'!$A$1:$O$61,'Blatt 1'!$Q:$R"), [(1, 15, 1, 61), (17, 18, None, None)], "Druckbereich")
    gleich(_druckbereich("#REF!"), [], "Druckbereich ohne Bezug")
    gleich((_im_bereich([(1, 15, 1, 61)], 16, 5), _im_bereich([(1, 15, 1, 61)], 3, 5), _im_bereich([], 99, 99)),
           (False, True, True), "im Druckbereich")
    gleich(_spalte("AB12"), 28, "Spalte")

    # --- Word
    teile = _t_docx()
    p = messen_docx(_t_zip(teile), "Veterinäramt", "Gesuch um einen Beitrag")
    gleich((p["messart"], p["seiten"], p["seitenformat"]),
           ("word", 2, {"name": "A4 hoch", "breite_mm": 210, "hoehe_mm": 297}), "Word: Rahmen")
    gleich([(s["familie"], s["symbol"], s["eingebettet"]) for s in p["schriften"]],
           [("Calibri", False, False), ("Arial", False, False), ("MS Gothic", True, False), ("Wingdings", True, False)],
           "Word: Schriften")
    gleich(round(sum(s["anteil"] for s in p["schriften"]), 3), 1.0, "Word: Anteile ergeben 1")
    gleich((p["hauptschrift"], p["n_schriftfamilien"], p["grundgroesse"], p["kleinste"]), ("Calibri", 2, 11.0, 9.0),
           "Word: Schrift und Grösse")
    gleich([g["pt"] for g in p["groessen"]], [11.0, 16.0, 9.0, 8.0, 7.0], "Word: Grössen")   # 125, 31, 21, 14, 5 characters
    gleich(p["groessen"][0]["anteil"], round(125 / 196, 4), "Word: Anteil der Grundgrösse")
    gleich(p["anteil_unter_8"], round(5 / 196, 4), "Word: Anteil unter 8 Punkt")
    gleich(sorted((f["hex"], f["familie"], f["anteil_text"], f["anteil_flaeche"]) for f in p["farben"]),
           [("#4f81bd", "Blau", round(31 / 196, 4), None), ("#b8cce4", "Blau", 0.0, None),
            ("#ff0000", "Rot", round(28 / 196, 4), None), ("#ffff00", "Gelb", 0.0, None)], "Word: Farben")
    gleich([(f["hex"], f["gewicht"]) for f in p["farben"]],
           [("#ffff00", round(2 / 14, 5)), ("#b8cce4", round(1 / 14, 5)), ("#4f81bd", round(TINTE * 31 / 196, 5)),
            ("#ff0000", round(TINTE * 28 / 196, 5))], "Word: Gewicht — gefüllte Absätze ganz, Text mit seinem Farbauftrag")
    gleich([list(f) for f in p["farben"]][0],
           ["hex", "familie", "anteil_text", "anteil_flaeche", "gewicht", "nur_link", "feld", "nur_kopf"],
           "Word: Schlüssel einer Farbe wie bei einem PDF")
    gleich((p["akzent"], p["n_farbfamilien"], p["anteil_text_farbig"]),
           ({"hex": "#ffff00", "familie": "Gelb"}, 3, round(59 / 196, 4)), "Word: Akzent ist die schwerste Farbfamilie")
    b = p["barrierefrei"]
    gleich((b["sprache"], b["titel"], b["titel_art"], b["ueberschriften"], b["tags"], b["felder"]),
           ("de-CH", "Dokument1", "generisch", True, None, None), "Word: barrierefrei")
    gleich(p["ausfuellbar"], True, "Word: ausfüllbar")
    gleich(any("Genau ein Absatz" in h for h in p["hinweise"]), True, "Word: Hinweis auf die einzige Überschrift")
    gleich([(t["nummer"], t["art"]) for t in p["telefon"]], [("052 632 71 01", "telefon")], "Word: Telefon")
    gleich(p["elemente"]["seitenzahlen"], {"vorhanden": True, "muster": "Seite 1 von 2"}, "Word: Seitenzahlen aus dem Feld")
    gleich((p["elemente"]["absender"]["kanton"], p["elemente"]["absender"]["dienststelle"]), (True, True), "Word: Absender")
    gleich(any("Flächenanteile" in h for h in p["hinweise"]), True, "Word: Hinweis zu den Flächen")
    gleich(messen_docx(_t_zip(teile)) == messen_docx(_t_zip(teile)), True, "Word: wiederholbar")
    streng = {k: v.replace(_T_W, "http://purl.oclc.org/ooxml/wordprocessingml/main") for k, v in teile.items()}
    gleich(messen_docx(_t_zip(streng), "Veterinäramt", "Gesuch um einen Beitrag"), p, "Word: Strict-Namensraum")
    ohne = dict(teile)                               # no theme, no styles, no properties: Word's own defaults
    for name in ("word/styles.xml", "word/theme/theme1.xml", "docProps/core.xml", "docProps/app.xml"):
        del ohne[name]
    q = messen_docx(_t_zip(ohne))
    gleich((q["hauptschrift"], q["grundgroesse"], q["seiten"], q["barrierefrei"]["titel_art"], q["barrierefrei"]["sprache"]),
           ("Times New Roman", 10.0, None, "leer", None), "Word: ohne Formatvorlagen")
    gleich(sum("Word-Vorgabe" in h for h in q["hinweise"]), 2, "Word: Hinweise auf die Vorgaben")
    eins = dict(teile, **{"docProps/app.xml": teile["docProps/app.xml"].replace("<Pages>2", "<Pages>1")})
    q = messen_docx(_t_zip(eins))
    gleich((q["seiten"], q["elemente"]["seitenzahlen"]["vorhanden"]), (None, True),
           "Word: Seitenzahl widerspricht den Umbrüchen")
    lang = "<w:p><w:r><w:t>" + "Sehr viel Text. " * 2000 + "</w:t></w:r></w:p><w:sectPr>"
    q = messen_docx(_t_zip(dict(eins, **{"word/document.xml": teile["word/document.xml"]
                                         .replace("<w:lastRenderedPageBreak/>", "").replace("<w:sectPr>", lang)})))
    gleich((q["seiten"], q["elemente"]["seitenzahlen"], [h for h in q["hinweise"] if "keinen Platz" in h] != []),
           (None, {"vorhanden": True, "muster": "Seite 1 von N"}, True), "Word: zu viel Text für die genannte Seitenzahl")

    q = messen_docx(_t_zip(_t_docx2()), "Veterinäramt", "Meldung einer Tierhaltung")
    gleich([(t["e164"], t["erklaerung"]) for t in q["telefon"]], [("+41526327102", "erklaert")],
           "Word: der gewählte Eintrag eines Auswahlfelds ist gedruckter Text")
    gleich((q["ausfuellbar"], any("Kopf- oder Fusszeile" in h for h in q["hinweise"])), (False, True),
           "Word: ein Feld nur in der Kopfzeile macht das Formular nicht ausfüllbar")
    gleich([(f["hex"], f["familie"], f["nur_link"]) for f in q["farben"]],
           [("#dbe5f1", "Blau", False), ("#0563c1", "Blau", True)], "Word: blasser Farbton als Füllung, Link-Farbe")
    gleich((q["akzent"], q["n_farbfamilien"]), ({"hex": "#dbe5f1", "familie": "Blau"}, 1), "Word: Link-Farbe ist kein Akzent")
    gleich((q["barrierefrei"]["titel_art"], q["barrierefrei"]["ueberschriften"]), ("ohne_bezug", False),
           "Word: Titel ohne Bezug zum Formular, keine Überschrift")
    gleich(any("Link-Farbe" in h for h in q["hinweise"]), True, "Word: Hinweis auf die Link-Farbe")

    # --- Excel
    p = messen_xlsx(_t_zip(_t_xlsx()), "Veterinäramt", "Gesuch um einen Beitrag")
    gleich((p["messart"], p["seiten"], p["seitenformat"]),
           ("excel", None, {"name": "A4 quer", "breite_mm": 297, "hoehe_mm": 210}), "Excel: Rahmen")
    gleich([(s["familie"], s["anteil"], s["eingebettet"]) for s in p["schriften"]],
           [("Arial", round(57 / 67, 4), None), ("Courier New", round(10 / 67, 4), None)], "Excel: Schriften")
    gleich((p["hauptschrift"], p["grundgroesse"], p["kleinste"], p["anteil_unter_8"]), ("Arial", 10.0, 10.0, 0.0),
           "Excel: Grössen")
    gleich([(f["hex"], f["familie"], f["anteil_text"]) for f in p["farben"]],
           [("#b9cde5", "Blau", 0.0), ("#ffff00", "Gelb", 0.0), ("#4f81bd", "Blau", round(20 / 67, 4))], "Excel: Farben")
    gleich((p["akzent"]["hex"], p["n_farbfamilien"], p["anteil_text_farbig"]), ("#b9cde5", 2, round(30 / 67, 4)),
           "Excel: Akzent")
    gleich((p["barrierefrei"]["titel"], p["barrierefrei"]["titel_art"], p["barrierefrei"]["sprache"], p["ausfuellbar"]),
           ("Beitragsgesuch", "aussagekraeftig", None, None), "Excel: barrierefrei")
    gleich([t["nummer"] for t in p["telefon"]], ["052 632 71 01"], "Excel: Telefon")
    gleich(p["elemente"]["seitenzahlen"], {"vorhanden": True, "muster": "Seite 1 von N"}, "Excel: Seitenzahlen")
    gleich(p["elemente"]["absender"]["kanton"], True, "Excel: Absender")
    gleich([h.split(" ")[0] for h in p["hinweise"]], ["Seitenzahl", "1", "1", "1", "Farbe", "Flächenanteile"], "Excel: Hinweise")
    gleich(any("#ff0000 (Rot)" in h for h in p["hinweise"]), True, "Excel: eine Farbe unter der Schwelle ist genannt")

    # --- what cannot be measured
    import io
    for messen, endung in ((messen_docx, "Word"), (messen_xlsx, "Excel")):
        q = messen(io.BytesIO(_OLE2 + b"\x00" * 600))
        gleich((q["messart"], q["schriften"], q["telefon"], q["grundgroesse"], q["elemente"]["stand_angabe"]["vorhanden"],
                len(q["hinweise"])), ("nicht_messbar", None, None, None, None, 1), endung + ": altes Format")
        gleich(messen(io.BytesIO(b"kein Paket"))["messart"], "nicht_messbar", endung + ": keine Zip-Datei")
        gleich((set(q), set(q["barrierefrei"]), set(q["elemente"])), (set(p), set(p["barrierefrei"]), set(p["elemente"])),
               endung + ": gleiche Schlüssel")
    gleich(messen_docx(_t_zip(_t_xlsx()))["messart"], "nicht_messbar", "Excel-Datei ist kein Word-Dokument")
    kaputt = dict(_t_docx(), **{"word/styles.xml": "<w:styles"})
    gleich(messen_docx(_t_zip(kaputt))["hinweise"], ["Datei nicht lesbar: beschädigt oder verschlüsselt."],
           "beschädigter Teil")
    return n[0]


if __name__ == "__main__":
    if len(sys.argv) > 1:                                  # print the profile of the given files
        import json
        for pfad in sys.argv[1:]:
            messen = messen_xlsx if pfad.lower().endswith((".xlsx", ".xlsm", ".xltx", ".xls")) else messen_docx
            print(json.dumps(messen(pfad), ensure_ascii=False, indent=1))
    else:
        print(f"gestaltung_office: {_selbsttest()} checks passed")
