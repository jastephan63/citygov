"""citygov.present — the generated pages: build_dashboard (with its guide,
leitfaden), build_flows, export_dossiers and build_index, and fill_pdf (flow
answers written into the official Formular). theme.problems() reads the four
page generators from this folder, and their files under assets/.

assets/<page>/ holds what a page is made of besides its data, as real files:
the HTML template page.html, the stylesheet and the scripts (dashboard, flows),
the dossiers' stylesheet and the two templates of the start page (index:
start.html for index.html, notfound.html for 404.html). A template is not named
like the page it becomes, so the .gitattributes patterns that mark the
generated pages (dashboard.html, flows.html, index.html, 404.html, at any
depth) do not catch these hand-written files. The generators read them at
build time; a page receives their text unchanged, with every line end read as
LF (also from a checkout that wrote CRLF), as Python read the literals they
were before. Each file is plain text: it ends with one line end and starts with
its first rule or tag; where a page needs it otherwise, its generator says so.
"""
import os
import re

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def asset(page, name):
    """The text of assets/<page>/<name> (UTF-8; a CRLF or CR line end is read as LF)."""
    with open(os.path.join(ASSETS, page, name), encoding="utf-8") as fh:
        return fh.read()


def template(page, name):
    """The HTML template assets/<page>/<name> with each «%%FILE:<file>%%» replaced by the
    text of assets/<page>/<file> — the page's stylesheet and scripts, inlined so the page
    stays one file. One pass: an inlined file is not searched for markers again, and the
    page's own markers (%%SIZE%%, /*DATA*/ …) are left for its generator."""
    return re.sub(r"%%FILE:([\w.-]+)%%", lambda m: asset(page, m.group(1)), asset(page, name))


def fill(text, values):
    """text with each «%%NAME%%» replaced by values[NAME], in one pass (a value is never
    searched for markers again). A marker without a value stops the build."""
    def value(m):
        if m.group(1) not in values:
            raise KeyError(f"%%{m.group(1)}%%: kein Wert für diese Marke")
        return values[m.group(1)]
    return re.sub(r"%%([A-Z_]+)%%", value, text)
