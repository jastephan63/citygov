#!/usr/bin/env python3
"""The command line of the concepts (python3 scripts/konzepte.py): the table, one concept
(--konzept), the whole block (--json) and the self-test (--selbsttest).

It builds the export's Formulare in memory with export_json.build (nothing is written),
so it lives in export/; the concept layer itself is citygov/domain/konzepte.py, whose
docstring describes it. _export_forms, _el and main are moved from there unchanged.
"""
import argparse
import json
import sys

from citygov.domain.konzepte import LABELS, MINDESTENS, berechne, pruefen, selbsttest


def _export_forms(conn):
    """The export's Formulare with their units (export_json.build, in memory, nothing written)."""
    import contextlib
    import io
    from citygov.export import export_json
    with contextlib.redirect_stdout(io.StringIO()):
        data, _ = export_json.build(conn)
    return data["forms"]


def _el(e):
    return f"{e['standard']} {e['element']}"


def main():
    from citygov.core.common import DB_PATH, connect
    ap = argparse.ArgumentParser(description="Konzepte: ein bevorzugtes Element je Angabe und Rolle.")
    ap.add_argument("--konzept", help="ein Konzept (code, z. B. vorname)")
    ap.add_argument("--json", action="store_true", help="den ganzen Block als JSON")
    ap.add_argument("--selbsttest", action="store_true", help="jede Prüfregel an manipulierten Kopien auslösen")
    args = ap.parse_args()
    conn = connect(DB_PATH)
    forms = _export_forms(conn)
    if args.selbsttest:
        sys.exit(0 if selbsttest(conn, forms) else 1)
    block = berechne(conn, forms)
    fehler = pruefen(conn, block, forms)
    rl = {r[0]: r[1] for r in conn.execute("SELECT code, label FROM partei_rolle")}
    ent = LABELS["entitaet"]

    def rolle(c):
        return f"{rl.get(c['rolle'], c['rolle'])} ({ent.get(c['entitaet'], c['entitaet'])})"
    if args.json:
        print(json.dumps(block, ensure_ascii=False, indent=1, sort_keys=True))
    elif args.konzept:
        kz = next((k for k in block["konzepte"] if k["code"] == args.konzept), None)
        if kz is None:
            sys.exit(f"kein Konzept «{args.konzept}» — vorhanden: {', '.join(k['code'] for k in block['konzepte'])}")
        print(f"{kz['label']} ({kz['code']}, {kz['gruppe']}): {kz['erklaerung']}")
        print(f"  Grund: {kz['grund']}")
        print(f"  Eigene Angabe von: {', '.join(ent[x] for x in kz['entitaeten'])}")
        print(f"  {kz['n_punkte']} Datenpunkte auf {kz['n_formulare']} Formularen; ohne Rolle {kz['ohne_rolle']['n']}; "
              f"andere Entität {kz['andere_entitaet']['n']}; eCH-Zuordnung falsch {kz['zuordnung_falsch']['n']}")
        print("  Mitglieder:")
        for m in kz["mitglieder"]:
            print(f"    {'/'.join(map(str, m['element_ids'])):>5} {_el(m)} [{m['context']}] Typ {m['datentyp']} "
                  f"Begriff {'/'.join(m['begriffe']) or '—'} | {m['n']} Punkte, {m['n_formulare']} Formulare"
                  + (f", {m['n_zuordnung_falsch']} falsch zugeordnet" if m["n_zuordnung_falsch"] else ""))
        for g in kz["gesperrt"]:
            print(f"    GESPERRT {_el(g)} [{g['context']}]: {LABELS['sperre'][g['sperre']]}")
        for a in kz["ausserhalb"]:
            print(f"    ausserhalb {_el(a)} [{a['context']}] ({a['n']} Punkte): {a['grund']}")
        for nb in kz["nicht_beurteilt"]:
            print(f"    NICHT BEURTEILT {'/'.join(map(str, nb['element_ids']))} {_el(nb)} [{nb['context']}] "
                  f"Begriff {'/'.join(nb['begriffe']) or '—'} ({nb['n']} Punkte)")
        print("  Je Rolle:")
        for c in kz["zellen"]:
            kopf = (f"Vorschlag {_el(c['vorschlag'])} {c['vorschlag']['anteil']} %"
                    if c["vorschlag"] else f"{LABELS['status']['kanton']} ({LABELS['grund'][c['grund']]})")
            print(f"    {rolle(c)}: {c['n']} Punkte, {c['n_formulare']} Formulare — {kopf}")
            for e in c["elemente"]:
                ist_v = c["vorschlag"] and _el(e) == _el(c["vorschlag"])
                print(f"        {_el(e):<38} {e['n']:>4} ({e['anteil']:>3} %) {e['n_formulare']:>3} Formulare"
                      + ("" if ist_v else f": {', '.join(map(str, e['formulare'][:30]))}"))
        for name in ("ohne_rolle", "andere_entitaet"):
            if kz[name]["n"]:
                print(f"    {LABELS[name]}: " + ", ".join(f"{_el(e)} {e['n']} ({', '.join(map(str, e['formulare'][:12]))})"
                                                     for e in kz[name]["elemente"]))
    else:
        s = block["summen"]
        print(f"Konzepte: {s['n_konzepte']} Konzepte, {s['n_mitglieder']} Angaben "
              f"({s['n_gesperrt']} gesperrt, {s['n_ausserhalb']} ausserhalb, {s['n_nicht_beurteilt']} nicht beurteilt); "
              f"{s['n_punkte']} Datenpunkte auf {s['n_formulare']} Formularen — {s['n_punkte_in_zellen']} in Zellen, "
              f"{s['n_ohne_rolle']} ohne Rolle, {s['n_andere_entitaet']} andere Entität; "
              f"{s['n_zuordnung_falsch']} falsch zugeordnete nicht gezählt")
        print(f"  {s['n_zellen']} Zellen (Konzept × Rolle mit Entität): {s['n_zellen_vorschlag']} mit Vorschlag, "
              f"{s['n_zellen_kanton']} legt der Kanton fest ({s['n_zellen_kanton_keine_mehrheit']} ohne Mehrheit, "
              f"{s['n_zellen_kanton_zu_wenige']} mit weniger als {MINDESTENS} Punkten)")
        print(f"  In Zellen mit Vorschlag: {s['n_punkte_in_vorschlag_zellen']} Punkte, {s['n_punkte_vorschlag']} nutzen den "
              f"Vorschlag, {s['n_abweichend']} ein anderes Element auf {s['n_abweichend_formulare']} Formularen "
              f"({s['n_konzepte_mit_abweichung']} Konzepte)")
        print(f"  {'Konzept':<26} {'Rolle (Entität)':<44} {'Punkte':>6} {'Form.':>5}  Ergebnis")
        for kz in block["konzepte"]:
            for c in kz["zellen"]:
                if c["vorschlag"]:
                    erg = (f"Vorschlag {_el(c['vorschlag'])} {c['vorschlag']['anteil']} %"
                           + (f" — {c['n_abweichend']} abweichend auf {c['n_abweichend_formulare']} Formularen"
                              if c["n_abweichend"] else ""))
                else:
                    erg = "Kanton: " + ", ".join(f"{_el(e)} {e['n']}" for e in c["elemente"][:4])
                print(f"  {kz['label'][:26]:<26} {rolle(c)[:44]:<44} {c['n']:>6} {c['n_formulare']:>5}  {erg}")
    if fehler:
        print("FEHLER:", *fehler[:10], sep="\n  ", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
