#!/usr/bin/env python3
"""The command line of the register map (python3 scripts/register_map.py).

The loading run and --pruefen (main_laden) and --korrekturen (korrekturen_bericht)
are citygov/domain/register_map.py's; --bericht builds the export in memory with
export_json.build, so bericht() and the choice of the command live here in export/.
bericht() and the main block are moved from register_map.py unchanged; that module's
docstring describes every command.
"""
import json
import os
import sys

from citygov.core.common import DB_PATH, ROOT, connect
from citygov.domain.register_map import flow_schluessel, korrekturen_bericht, main_laden, prefill_punkte


# ---------------------------------------------------------------------------
# report on today's data (nothing written except --json PATH)
# ---------------------------------------------------------------------------
def bericht():
    from citygov.export import export_json
    conn = connect(DB_PATH)
    data, _ = export_json.build(conn)          # the export runs prefill_korrigieren and export_register
    forms = data["forms"]
    tot = data.get("vorbefuellung") or {}
    reg = data.get("register") or {"katalog": [], "gesamt": {}}
    titel = {fm["id"]: fm["title"] for fm in forms}
    diff = sorted(((fm["id"], fm["burden"]["prefillable_bisher"], fm["burden"]["prefillable"])
                   for fm in forms if fm.get("burden")), key=lambda x: -(x[1] - x[2]))
    # the flows fill exactly the vorbefuellbar points (flow_schluessel)
    flow_diff = [(fm["id"], p["feld"]) for fm in forms if fm.get("has_flow") for p in prefill_punkte(fm)
                 if p["vorbefuellbar"] != (p["feld"] in flow_schluessel(fm))]
    partei = {}
    for fm in forms:
        for p in prefill_punkte(fm):
            if p["pflicht"] and p["einwohnerregister"]:
                k = p["partei"]["rolle"] if p["partei"] else "offen"
                partei[k] = partei.get(k, 0) + 1
    out = {"prefill": tot, "prefill_flow_abweichung": flow_diff,
           "pflicht_mit_marke_je_rolle": dict(sorted(partei.items(), key=lambda kv: -kv[1])),
           "formulare_mit_vorbefuellbar": sum(1 for fm in forms if (fm.get("burden") or {}).get("prefillable")),
           "zu_hoch": [{"form": f, "titel": titel[f], "bisher": a, "korrigiert": k} for f, a, k in diff if a > k],
           "register": [{"code": k["code"], **k["zahlen"], "zugriff": k["zugriff_status"]} for k in reg["katalog"]],
           "gesamt": reg["gesamt"]}
    prefill_file = os.path.join(ROOT, "citygov_prefill.json")
    if os.path.exists(prefill_file):
        pf = json.load(open(prefill_file, encoding="utf-8"))["formulare"]
        out["prefill_datei_vergleich"] = sum(
            1 for fm in forms
            if fm.get("burden") and fm["burden"]["prefillable"] != sum(
                1 for p in pf.get(str(fm["id"]), []) if p["pflicht"] and p.get("vorbefuellbar")))
    lebenslagen = [(g["katalog"], g["gruppe"], g["register"]) for g in data.get("themenkatalog") or [] if g.get("register")]
    out["lebenslagen"] = [{"katalog": k, "gruppe": gr, **r} for k, gr, r in lebenslagen]
    out["formulare_modell"] = sorted(({"form": fm["id"], "titel": fm["title"], **{k: v for k, v in fm["register"].items()
                                                                                  if k != "hinweis"}}
                                      for fm in forms if fm.get("register")), key=lambda x: -x["minuten_modell"])
    print(json.dumps({k: v for k, v in out.items() if k not in ("formulare_modell", "lebenslagen", "zu_hoch")},
                     ensure_ascii=False, indent=1))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
    return out, data


if __name__ == "__main__":
    if "--korrekturen" in sys.argv:
        korrekturen_bericht()
    elif "--bericht" in sys.argv:
        bericht()
    else:
        main_laden(pruefen_nur="--pruefen" in sys.argv)
