#!/usr/bin/env python3
"""Build index.html — the landing page of the published site and of a clone.

GitHub cannot display dashboard.html (the whole databank in one file of some
tens of MB) and serves its «raw» link as sandboxed plain text, so a visitor
needs one address that simply opens it.
With GitHub Pages serving the repository, that address is this page:
https://jastephan63.github.io/citygov/ . It links the dashboard, the guided
flows, the dossiers and the repository, states size and data date, and says
how to keep an offline copy. Figures come from data_export.json (one source),
so the page never drifts from the dashboard; the dashboard's size and transfer
size are measured on dashboard.html with the same rounding the dashboard uses
for itself (common.size_txt / net_size_txt). Also writes 404.html, which GitHub
Pages serves for any missing path.

The look (font, ink, link colour, text sizes) comes from scripts/theme.py; every
value written into the two pages passes e() — text and attribute values alike.
The pages carry no script and inline no data.

    python3 scripts/build_index.py        (run by ./build.sh)
"""
import html, json, os, sys
from citygov.core.common import ROOT, EXPORT_PATH, size_txt, net_size_txt
from citygov.core.labels import fmt_date
from citygov.core import theme as THEME
from citygov.present import asset, fill

SITE = "https://jastephan63.github.io/citygov/"
REPO = "https://github.com/jastephan63/citygov"


def dash_size():
    """«knapp 30 MB, über das Netz etwa 4 MB» for dashboard.html as it is on disk."""
    try:
        raw = open(os.path.join(ROOT, "dashboard.html"), "rb").read()
    except OSError:
        sys.exit("dashboard.html fehlt — zuerst scripts/build_dashboard.py ausführen")
    return f"knapp {size_txt(len(raw))}, über das Netz etwa {net_size_txt(raw)}"


def main():
    D = json.load(open(EXPORT_PATH, encoding="utf-8"))
    ds = D.get("datenstand") or {}
    n_services, n_forms = len(D["services"]), len(D["forms"])
    n_fields = sum(len(f.get("data_fields") or []) for f in D["forms"])
    n_flows = sum(1 for f in D["forms"] if f.get("has_flow"))
    n_dossiers = len([x for x in os.listdir(os.path.join(ROOT, "dossiers")) if x.endswith(".html") and x != "index.html"]) \
        if os.path.isdir(os.path.join(ROOT, "dossiers")) else 0
    dash = dash_size()
    fields_txt = f"{n_fields:,}".replace(",", "'")      # thousands grouped as on the dashboard: 5'991

    def e(v):
        """A value on its way into the page, as text or inside a quoted attribute."""
        return html.escape(str(v if v is not None else ""), quote=True)
    stand = " · ".join(x for x in (
        f"Daten exportiert {fmt_date(ds.get('build'))}" if ds.get("build") else "",
        f"DVSH-Modell {fmt_date(ds.get('dvsh_stand'))}" if ds.get("dvsh_stand") else "",
        f"SHEP-Portal {fmt_date(ds.get('shep_harvest'))}" if ds.get("shep_harvest") else "") if x)

    # the two pages are templates under citygov/present/assets/index/ (start.html for
    # index.html, notfound.html for 404.html); fill() puts each value in place of its %%NAME%% marker
    page = fill(asset("index", "start.html"), {
        "FAVICON": THEME.favicon(), "THEME": THEME.css_root(), "DASH": e(dash),
        "N_DOSSIERS": e(n_dossiers), "N_FLOWS": e(n_flows), "N_FORMS": e(n_forms), "REPO": e(REPO),
        "N_SERVICES": e(n_services), "FIELDS": e(fields_txt), "STAND": e(stand)})
    out = os.path.join(ROOT, "index.html")
    open(out, "w", encoding="utf-8").write(page)
    # GitHub Pages serves 404.html for any missing path, at the depth of the wrong
    # URL — so every link here is absolute
    open(os.path.join(ROOT, "404.html"), "w", encoding="utf-8").write(fill(asset("index", "notfound.html"), {
        "FAVICON": THEME.favicon(), "THEME": THEME.css_root(compact=True), "SITE": e(SITE), "REPO": e(REPO)}))
    print(f"wrote {out}  ({n_services} Services, {n_forms} Formulare, {n_dossiers} Dossiers, {n_flows} Flows)")


if __name__ == "__main__":
    main()
