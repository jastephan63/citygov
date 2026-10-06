#!/usr/bin/env python3
"""The shared look of every generated page — ONE definition, next to labels.py.

labels.py says what a code is called; this module says what a page looks like:
fonts, colours, the four tones, the status symbols, the eSH violet and the text
sizes. The four generators (build_dashboard.py, build_flows.py,
export_dossiers.py, build_index.py) write their colour and type block from
here — css_root() — and use var(--…) in their own rules, so a colour or a size
is changed in this file and nowhere else.

Rules the values follow (owner's decisions, do not change them here in passing):
  * colour = who acts next: green geklärt · red Dienststelle · amber Kanton ·
    grey Databank (the tone names ok/act/dec/open are labels.TON's)
  * the bright golds (--gold, --gold-deep) are for the crest, borders, bars and
    fills; TEXT in gold (links, accent labels) and the focus ring use --link
  * violet is the eSH draft (and the databank's own interpretation in the
    Leitfaden) — never a status
  * system fonts only: no page ships a font, so none is named
  * six text sizes; 12 px is the floor on screen, 9 pt on paper

Every text colour reaches a contrast of 4.5:1 (WCAG 2.1 AA) on every surface it
is used on; CONTRAST_PAIRS lists the pairs and check() computes them.

loose() finds what a generator still writes by hand: a hex, rgb()/hsl() or named
colour (in CSS, in an attribute, as %23… in a data URI, in el.style.color=…), a
font size in px/pt/em/rem/% (also el.style.fontSize=…) and a font family. A
literal kept on purpose carries «theme:keep» and its reason in the same line.

    python3 scripts/theme.py           prints the tokens, the contrast table and any
                                       colour, size or font literal left in the generators
    python3 scripts/theme.py --check   prints only what is wrong, then one line

Exit code 1 if a pair is below 4.5:1, a literal is left, or the tone names differ
from labels.TON.
"""
import os
import re
import sys

from citygov.core.common import ROOT

# ---- fonts: one stack for text, one for code; system fonts only -----------------
FONT = 'system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
MONO = 'ui-monospace,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace'

# ---- colours (CSS custom property name without the leading --) -----------------
COLOR = {
    # surfaces
    "paper": "#FAFAF6",        # page background (dashboard, guided forms, landing page)
    "card": "#FFFFFF",         # cards, tables, the dossier page
    "field": "#F4F1E7",        # inset surface: inputs, group rows, quotes
    "hover": "#FCFAF2",        # hovered or selected row / navigation entry
    # text
    "ink": "#16150F",          # text
    "ink-soft": "#5C594D",     # secondary text
    "ink-faint": "#6B6455",    # tertiary text: table headers, subtitles, notes
    # lines
    "line": "#E4E1D6",         # card and table borders
    "line-soft": "#EEEBE1",    # row separators, empty bar track
    "line-strong": "#C9C5B8",  # outline of a neutral Kennzeichen
    "line-dark": "#A9A597",    # stronger neutral outline (zwingend / dashed marks)
    # gold
    "gold": "#F2B705",         # crest, accent borders, progress fill
    "gold-deep": "#C98E00",    # hover/active border — never text
    "link": "#8F6400",         # link and accent TEXT, keyboard focus ring
    "gold-tint": "#FFF1B8",    # search hit, offline note
    # eSH draft: violet, dashed
    "esh": "#4A3570",
    "esh-bg": "#F3EFFA",
    "esh-line": "#9B84C9",
}

# ---- the four tones (names = labels.TON) ----------------------------------------
# fill: bar segment, swatch, symbol · bg: tint of a status chip · line: its border ·
# ink: the tone as TEXT (dossier badges, validation messages of the guided forms) ·
# sym: the symbol that keeps the tones apart without colour (print, colour blindness)
TON = {
    "ok":   {"fill": "#1E8657", "bg": "#E5F2EA", "line": "#8CC7A4", "ink": "#1D5B3A", "sym": "✓"},
    "act":  {"fill": "#C8372D", "bg": "#FBEAE8", "line": "#DE9A9A", "ink": "#8E1B1B", "sym": "●"},
    "dec":  {"fill": "#DB8B00", "bg": "#FCF1DC", "line": "#D9AE4A", "ink": "#6E4A00", "sym": "◆"},
    "open": {"fill": "#8A877D", "bg": "#EFEDE7", "line": COLOR["line-dark"], "ink": "#55524A", "sym": "○"},
}
TON_OK2 = TON["ok"]["line"]    # light green: geklärt auf Standard-Ebene (bar segment, swatch)
TON_SYM = {t: v["sym"] for t, v in TON.items()}

# ---- effects (the only colours with transparency) -------------------------------
SHADOW = "rgba(22,21,15,.18)"  # drop shadow of a floating box
RING = "rgba(242,183,5,.28)"   # soft glow around a focused input (the border carries --link)

# ---- text sizes: six names, px on screen, pt on paper ---------------------------
SIZE = {"xs": 12, "s": 13, "m": 14, "l": 16, "xl": 22, "xxl": 28}
SIZE_PRINT = {"xs": 9, "s": 9, "m": 9.5, "l": 11.5, "xl": 16, "xxl": 20}
SIZE_USE = {
    "xs": "the floor: labels, chips, badges, table headers, notes",
    "s": "tables and secondary text",
    "m": "running text of the dashboard and the dossier",
    "l": "section headings; running text of the landing page and the guided forms; inputs",
    "xl": "page title",
    "xxl": "headline figure, title of the landing page, question of a guided form",
}


def tokens():
    """Every custom property of the look: name (without --) -> value, in output order."""
    t = dict(COLOR)
    for k, v in TON.items():
        t[f"ton-{k}"] = v["fill"]
    t["ton-ok2"] = TON_OK2
    for part in ("bg", "line", "ink"):
        for k, v in TON.items():
            t[f"ton-{k}-{part}"] = v[part]
    t["shadow"] = SHADOW
    t["ring"] = RING
    t["font"] = FONT
    t["mono"] = MONO
    for k, v in SIZE.items():
        t[f"fs-{k}"] = f"{v}px"
    return t


def css_root(compact=False):
    """The :root block every generated page starts its stylesheet with. On paper the
    six sizes switch to their pt values, so a page needs no size rules of its own
    for print. compact=True leaves the comments out (the dossiers: one copy per page)."""
    t = tokens()
    groups = [
        ("surfaces", ["paper", "card", "field", "hover"]),
        ("text", ["ink", "ink-soft", "ink-faint"]),
        ("lines", ["line", "line-soft", "line-strong", "line-dark"]),
        ("gold: fills and borders; --link is the gold for text and the focus ring",
         ["gold", "gold-deep", "link", "gold-tint"]),
        ("tones — the colour says who acts next: ok geklärt · act Dienststelle · dec Kanton · open Databank",
         ["ton-ok", "ton-ok2", "ton-act", "ton-dec", "ton-open"]),
        ("tone tints, their borders, and the tone as text",
         [f"ton-{k}-{p}" for p in ("bg", "line", "ink") for k in TON]),
        ("eSH draft: violet, dashed — never a status", ["esh", "esh-bg", "esh-line"]),
        ("effects", ["shadow", "ring"]),
        ("fonts: system fonts only", ["font", "mono"]),
        ("text sizes (12 px is the floor)", [f"fs-{k}" for k in SIZE]),
    ]
    used = [n for _, names in groups for n in names]
    assert sorted(used) == sorted(t), "css_root(): a token is missing from the groups or listed twice"
    on_paper = "@media print{:root{" + "".join(f"--fs-{k}:{v:g}pt;" for k, v in SIZE_PRINT.items()) + "}}"
    if compact:
        return ("/* the shared look — written from scripts/theme.py */\n:root{"
                + "".join(f"--{n}:{t[n]};" for n in used) + "}\n" + on_paper)
    lines = ["/* the shared look — written from scripts/theme.py, the one place it is set */", ":root{"]
    for title, names in groups:
        lines.append(f"  /* {title} */")
        lines.append("  " + " ".join(f"--{n}:{t[n]};" for n in names))
    lines.append("}")
    lines.append(on_paper)
    return "\n".join(lines)


def favicon():
    """<link rel="icon"> — the gold square of the crest, as a data URI (no request)."""
    return ("<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
            "viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23"
            + COLOR["gold"].lstrip("#") + "'/%3E%3C/svg%3E\">")


VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'


def css_swatch(sel=".sw", prefixes=("t-", "st-")):
    """The tone swatch as a shape, so the four tones differ without colour — the same
    four symbols the dossier prints (TON_SYM): check · dot · diamond · ring. The fill
    comes from the page's own tone classes; this adds the shape. In a Windows contrast
    theme the swatches and bar segments keep their colours (forced-color-adjust)."""
    check = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'%3E"
             "%3Cpath d='M2.1 5.3l2 2 3.8-4.4' fill='none' stroke='%23" + COLOR["card"].lstrip("#")
             + "' stroke-width='1.7' "
             "stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E\")")
    both = lambda t: ",".join(f"{sel}.{p}{t}" for p in prefixes)
    return "\n".join([
        f"  {both('ok')},{sel}.t-ok2{{background-image:{check};background-size:100% 100%}}",
        f"  {both('act')}{{border-radius:50%}}",
        f"  {both('dec')}{{border-radius:0;clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%)}}",
        f"  {both('open')}{{border-radius:50%;background:none;box-shadow:inset 0 0 0 2px var(--ton-open)}}",
        f"  @media (forced-colors:active){{{sel},.tbar>i,.minibar>i,.pbar>i{{forced-color-adjust:none}}}}",
    ])


# ---- contrast (WCAG 2.1) ---------------------------------------------------------
def _lum(hexcol):
    h = hexcol.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(ch[0]) + 0.7152 * f(ch[1]) + 0.0722 * f(ch[2])


def contrast(fg, bg):
    """Contrast ratio of two #RRGGBB colours (relative luminance, WCAG 2.1)."""
    a, b = _lum(fg), _lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# text token -> the surfaces it is drawn on in the generated pages (measured in the
# browser per text node; a new use on another surface belongs in this list)
_TINTS = [f"ton-{k}-bg" for k in TON]
CONTRAST_PAIRS = {
    "ink": ["card", "paper", "field", "hover", "line-soft", "gold-tint", "gold", "esh-bg"] + _TINTS,
    "ink-soft": ["card", "paper", "field", "hover", "line-soft"] + _TINTS,
    "ink-faint": ["card", "paper", "field", "hover"],
    "link": ["card", "paper", "field", "hover"],
    "esh": ["esh-bg", "card"],
    "card": ["ink"],           # white text on the dark button and band
    "paper": ["ink"],
    "line": ["ink"],           # secondary text on the dark band
}
for _k in TON:                 # the tone as text: on its own tint and on the neutral surfaces
    CONTRAST_PAIRS[f"ton-{_k}-ink"] = [f"ton-{_k}-bg", "card", "paper", "field"]


def check(minimum=4.5):
    """[(text token, surface token, ratio, ok)] for every pair in CONTRAST_PAIRS."""
    t = tokens()
    return [(fg, bg, contrast(t[fg], t[bg]), contrast(t[fg], t[bg]) >= minimum)
            for fg, bgs in CONTRAST_PAIRS.items() for bg in bgs]


# ---- what a generator may still write by hand ------------------------------------
GENERATORS = ("build_dashboard.py", "build_flows.py", "export_dossiers.py", "build_index.py")
# the forms a colour, a size or a font can take in CSS, in an attribute, in a data URI and
# in a JavaScript style assignment — each one a var(--…) from this module instead
_HEX = re.compile(r"(?<![&\w])#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b(?![\w-])|%23(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b(?![\w-])")
_RGB = re.compile(r"(?:rgba?|hsla?)\([^)]*\)")
_NAMED = re.compile(r"(?:(?:color|background(?:-color)?|fill|stroke|border(?:-\w+)*|outline(?:-color)?)\s*:|"
                    r"\.(?:color|background(?:Color)?|borderColor|outlineColor|fill|stroke)\s*=)\s*['\"]?[^;}'\"]*?"
                    r"(?<![\w-])(white|black|red|green|blue|gr[ae]y|yellow|orange|purple|violet|brown|pink|silver|gold|navy|teal|"
                    r"olive|maroon|lime|aqua|cyan|magenta|beige|ivory|tan|khaki|coral|salmon|crimson|indigo|turquoise)(?![\w-])", re.I)
_PX = re.compile(r"(?:font(?:-size)?\s*:|\.fontSize\s*=)\s*['\"]?[^;}\"']*?\b\d*\.?\d+(?:px|pt|em|rem|%)(?![\w-])")
_FAM = re.compile(r"font-family\s*:\s*(?!var\(|inherit)[^;}]+|\.fontFamily\s*=|\b(?:Inter|Roboto|Helvetica|Arial|Segoe)\b")


def loose(path):
    """Colour, size and font literals in a generator — everything that should be a
    var(--…) from this module. Returns [(line number, kind, text)]."""
    out = []
    with open(path, encoding="utf-8") as fh:
        for no, line in enumerate(fh, 1):
            if "theme:keep" in line:      # a literal kept on purpose, with its reason in the comment
                continue
            for kind, rx in (("colour", _HEX), ("colour", _RGB), ("colour", _NAMED), ("size", _PX), ("font", _FAM)):
                for m in rx.finditer(line):
                    # an anchor (href="#main"), a URL fragment or an HTML entity is not a colour
                    before = line[:m.start()]
                    if kind == "colour" and m.group(0).startswith("#") and (
                            not re.search(r"[:\s,(='\"]$|^$", before[-1:] or "")
                            or re.search(r"href=['\"]$", before)):
                        continue
                    out.append((no, kind, m.group(0) if rx is not _NAMED else m.group(1)))
    return out


def problems():
    """Everything that breaks the one-definition rule, as a list of plain sentences:
    a text colour below 4.5:1, a literal left in a generator, a tone that labels.py
    does not know (or the other way round)."""
    t = tokens()
    out = [f"contrast {r:.2f}:1 below 4.5:1 — --{fg} {t[fg]} on --{bg} {t[bg]}"
           for fg, bg, r, ok in check() if not ok]
    here = os.path.join(ROOT, "citygov", "present")      # the four generators
    for g in GENERATORS:
        p = os.path.join(here, g)
        if os.path.exists(p):
            out += [f"{g} line {no}: {kind} literal {txt} — use a var(--…) from theme.py"
                    for no, kind, txt in loose(p)]
    try:
        from citygov.core import labels
        if set(labels.TON) != set(TON):
            out.append(f"tone names differ: labels.TON {sorted(labels.TON)} — theme.TON {sorted(TON)}")
    except ImportError:
        pass
    return out


def main():
    bad = problems()
    if "--check" in sys.argv[1:]:
        for line in bad:
            print("  " + line)
        print(f"theme.py: {len(check())} colour pairs, {len(GENERATORS)} generators — "
              + ("ok" if not bad else f"{len(bad)} finding(s)"))
        sys.exit(1 if bad else 0)
    t = tokens()
    print("Tokens (CSS custom properties, from scripts/theme.py)")
    for k, v in t.items():
        print(f"  --{k}: {v}")
    print("  print: " + " ".join(f"--fs-{k}:{v:g}pt" for k, v in SIZE_PRINT.items()))
    print("  symbols: " + " ".join(f"{k} {v}" for k, v in TON_SYM.items()))
    print("\nContrast of every text colour on every surface it is used on (WCAG 2.1, minimum 4.5:1)")
    for fg, bg, r, ok in check():
        print(f"  {'ok  ' if ok else 'FAIL'} {r:5.2f}  --{fg} {t[fg]} on --{bg} {t[bg]}")
    print("\nFindings (contrast below 4.5:1, literals left in the generators — «theme:keep» in the"
          "\nline marks a justified one —, tone names against labels.TON)")
    for line in bad:
        print("  " + line)
    print(f"\n{len(bad)} finding(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
