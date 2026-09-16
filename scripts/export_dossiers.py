#!/usr/bin/env python3
"""One Datenschutz-Dossier per service, as a small self-contained HTML page
(dossiers/<slug>.html) and - with --pdf and a local Chrome - as PDF.

Why: a Dienststelle should get its own picture on one or two A4 pages without
opening the 33 MB dashboard. Everything on the page comes from
data_export.json, i.e. from citygov.db, and says what it is: verified,
curated, derived or open. Nothing here is a new judgment.

Contents: Service (Dienststelle, Kontakt aus dem DVSH, DVSH-Status, Zweck),
Rechtsgrundlagen des Services, Verfahrens-Ergebnis und Rechtsmittel, je
Formular: Kanal/Unterschrift/Bürgerlast, die Datenfelder (Pflicht, eCH-Element
und Datentyp, Grundlage, ⛨, ↺), Beilagen mit Halter, Empfänger mit Artikel,
Aufbewahrung, und der Handlungsbedarf des Formulars.

    python3 scripts/export_dossiers.py [--pdf] [--only <service_id>]
"""
import html, json, os, re, shutil, subprocess, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dossiers")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)
DFTYPE = {"text": "Text", "date": "Datum", "number": "Zahl", "money": "Betrag", "boolean": "Ja/Nein",
          "enum": "Auswahl", "multiselect": "Mehrfachauswahl", "composite": "Zusammengesetzt",
          "attachment": "Beilage", "signature": "Unterschrift"}
SENS = {"gesundheit": "Gesundheit", "religion_weltanschauung": "Religion/Weltanschauung", "politik": "Politische Ansichten",
        "ethnie_herkunft": "Ethnie/Herkunft", "genetik_biometrie": "Genetik/Biometrie",
        "strafen_verfahren": "Strafverfahren/Sanktionen", "sozialhilfe": "Soziale Hilfe"}
OUTCOME = {"bewilligung": "Bewilligung", "verfuegung": "Verfügung", "bestaetigung": "Bestätigung/Ausweis",
           "registereintrag": "Registereintrag", "auszahlung": "Auszahlung", "kein_entscheid": "kein Entscheid (Meldung)"}
RM = {"einsprache": "Einsprache", "rekurs": "Rekurs", "beschwerde": "Beschwerde",
      "verwaltungsgerichtsbeschwerde": "Verwaltungsgerichtsbeschwerde", "verweis": "Rechtsmittel nach Verweis"}
HALTER = {"privat": "nur beim Bürger", "einwohnerregister": "Einwohnerregister", "handelsregister": "Handelsregister",
          "betreibungsregister": "Betreibungsregister", "strafregister": "Strafregister", "steuerverwaltung": "Steuerverwaltung"}
CHAN = {"online_formular": "Online-Formular", "pdf": "PDF-Einreichung", "schalter": "Schalter", "unbekannt": "Kanal unbekannt"}
CHECK = {"veraltet": "neuere Fassung online", "veraltet_verdacht": "evtl. veraltet",
         "nicht_auffindbar": "nicht mehr online", "nicht_gefunden": "online nicht gefunden"}

CSS = """
@page{size:A4;margin:14mm 14mm 16mm}
*{box-sizing:border-box}
:root{color-scheme:light only}
body{font:10.5pt/1.35 -apple-system,"Helvetica Neue",Arial,sans-serif;color:#1F2A37;background:#fff;margin:0;padding:18px 22px;max-width:900px}
h1{font-size:16pt;margin:0 0 2px}h2{font-size:11.5pt;margin:14px 0 4px;border-bottom:1px solid #D8D2C4;padding-bottom:2px}
h3{font-size:10.5pt;margin:10px 0 3px}
.sub{color:#6B6455;font-size:9.5pt}.muted{color:#6B6455}.small{font-size:9pt}
table{border-collapse:collapse;width:100%;font-size:9pt}th,td{text-align:left;vertical-align:top;padding:2px 5px;border-bottom:1px solid #EAE5DA}
th{font-weight:600;color:#6B6455;font-size:8.5pt;text-transform:uppercase;letter-spacing:.03em}
.b{display:inline-block;border:1px solid #D8D2C4;border-radius:4px;padding:0 4px;font-size:8.5pt;white-space:nowrap}
.b.ok{color:#1F5A3A;background:#E3F2E8;border-color:#B9DEC6}.b.warn{color:#8F6400;background:#FBF3DC;border-color:#EBD9A8}
.b.bad{color:#7A1F1F;background:#FBEAEA;border-color:#E8B4B4}.b.sens{color:#5A1F6B;background:#F1E6F5;border-color:#D7BFE0}
.b.info{color:#1F3A6B;background:#E6ECF5;border-color:#BFCDE0}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:8.5pt}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px}
.box{border:1px solid #D8D2C4;border-radius:6px;padding:6px 9px;margin:6px 0}
.print{position:fixed;right:14px;top:10px;border:1px solid #D8D2C4;background:#fff;border-radius:6px;padding:5px 10px;font:inherit;cursor:pointer}
.foot{margin-top:14px;font-size:8.5pt;color:#6B6455;border-top:1px solid #D8D2C4;padding-top:4px}
@media print{.print{display:none}body{padding:0}.form{break-inside:avoid-page}}
"""


def basis_label(d):
    if d.get("legal_basis"):
        b = d["legal_basis"][0]
        nr = b.get("sr_number") or b.get("cantonal_ref") or ""
        return f'<span class="b ok">{esc(b.get("article_no"))} {esc(b.get("law_short") or "")}{(" · " + esc(nr)) if nr else ""}</span>'
    bt = d.get("basis_typ")
    if bt == "aufgabe":
        return '<span class="b warn" title="KDSG Art. 4 Abs. 1 lit. b">aufgabennotwendig — keine explizite Norm</span>'
    if bt == "ohne":
        return '<span class="b bad">Over-collection — weder Norm noch Aufgabenbedarf</span>'
    if bt == "offen":
        return '<span class="b warn">keine explizite Norm — Aufgabenbedarf offen</span>'
    return '<span class="b warn">Rechtsgrundlage zu ermitteln</span>'


def todo(f):
    dfs = f.get("data_fields") or []
    it = []
    if not dfs:
        return ["Datenfeld-Schicht fehlt"]
    n = sum(1 for d in dfs if not d.get("basis_typ") and not d.get("legal_basis"))
    if n: it.append(f"Rechtsgrundlage zu ermitteln: {n} Felder")
    n = sum(1 for d in dfs if d.get("basis_typ") == "offen")
    if n: it.append(f"Aufgabenbedarf offen: {n}")
    n = sum(1 for d in dfs if d.get("basis_typ") == "ohne")
    if n: it.append(f"Over-collection bereinigen: {n}")
    if not f.get("purpose"): it.append("Zweck nicht erfasst")
    if not f.get("disclosures"): it.append("Empfänger nicht dokumentiert")
    sens = sum(1 for d in dfs if d.get("sensitive"))
    if (sens >= 3 or (sens and sens / len(dfs) >= 0.5)) and not f.get("dsfa_status"):
        it.append(f"DSFA-Entscheid offen ({sens} ⛨-Felder, KDSG Art. 14b)")
    n = sum(1 for d in dfs if not d.get("ech_status") or d.get("ech_status") == "standard_only")
    if n: it.append(f"eCH-Zuordnung offen: {n}")
    ck = (f.get("check") or {}).get("status")
    if ck in CHECK: it.append(f"Formular-Fassung prüfen: {CHECK[ck]}")
    n = sum(1 for s in (f.get("similar") or []) if not s.get("verdict"))
    if n: it.append(f"Duplikat-Verdacht unentschieden: {n}")
    return it


def field_row(d):
    e = d.get("ech") or {}
    el = ""
    if e.get("element"):
        el = f'<span class="mono">{esc(e["standard"])} {esc(e["element"])}</span>' + (f' <span class="mono muted">⟨{esc(e["datatype"])}⟩</span>' if e.get("datatype") else "")
        if e.get("status") and e["status"] != "Genehmigt":
            el += f' <span class="b warn">{esc(e["status"])}</span>'
    elif e.get("standard"):
        el = f'<span class="mono">{esc(e["standard"])}</span> <span class="muted">Element offen</span>'
    elif d.get("ech_status") == "kein_standard":
        el = '<span class="muted">kein eCH-Standard</span>' + (f' <span class="b info">{esc(d["esh"]["code"])} Entwurf</span>' if d.get("esh") else "")
    else:
        el = '<span class="muted">nicht geprüft</span>'
    marks = ""
    if d.get("sensitive"):
        marks += f' <span class="b sens">⛨ {esc(SENS.get(d["sensitive"], d["sensitive"]))}</span>'
    units = [s for s in (d.get("subfields") or []) if isinstance(s, dict)] or [d]
    if any(u.get("register") for u in units):
        marks += ' <span class="b ok">↺ Einwohnerregister</span>'
    subs = [s.get("name") if isinstance(s, dict) else s for s in (d.get("subfields") or [])]
    subs_txt = f'<div class="small muted">Teilfelder: {esc(" · ".join(x for x in subs if x)[:160])}</div>' if subs else ""
    return (f'<tr><td><b>{esc(d["name"])}</b>{marks}{subs_txt}</td>'
            f'<td>{"Pflicht" if d.get("required") else "<span class=muted>optional</span>"}</td>'
            f'<td>{el}</td><td>{basis_label(d)}</td></tr>')


def dossier(s, forms, dst, kat):
    dv = s.get("dvsh") or {}
    kontakt = []
    if dst and dst.get("kontakt"):
        try:
            kontakt = json.loads(dst["kontakt"])
        except Exception:
            kontakt = [dst["kontakt"]]
    laws = []
    for key, jl in (("recht_kantonal", "Kanton"), ("recht_bund", "Bund")):
        v = dv.get(key)
        if isinstance(v, str):
            try: v = json.loads(v)
            except Exception: v = []
        for x in v or []:
            if isinstance(x, dict) and (x.get("titel") or "").strip():
                laws.append(f'<span class="b">{jl} · {esc(x.get("titel") or "")}{(" · " + esc(x.get("ssr_nummer") or x.get("sr_nummer") or "")) if (x.get("ssr_nummer") or x.get("sr_nummer")) else ""}</span>')
    out = (forms[0].get("outcome") if forms else None) or {}
    rm = out.get("rechtsmittel")
    rm_html = ""
    if rm:
        frist = f"innert {rm['frist_tage']} Tagen" if rm.get("frist_tage") else "Frist im Gesetz nicht beziffert"
        nr = rm.get("sr_number") or rm.get("cantonal_ref") or ""
        what = (f"Rechtsmittel nach {esc(rm.get('instanz') or 'dem verwiesenen Erlass')}" if rm["rechtsmittel_art"] == "verweis"
                else f"<b>{esc(RM.get(rm['rechtsmittel_art'], rm['rechtsmittel_art']))}</b>{(' an ' + esc(rm['instanz'])) if rm.get('instanz') else ''} {frist}")
        src = ('<span class="b warn">allgemeine Regel des VRG — Spezialgesetz vorbehalten</span>' if rm.get("scope") == "allgemein"
               else f'<span class="b ok">sektoral: {esc(rm.get("short_title") or "")}</span>')
        rm_html = (f'<div><b>Rechtsmittel:</b> {what} — {esc(rm.get("article_no"))} {esc(rm.get("short_title") or rm.get("law_title") or "")}'
                   f'{(" (" + esc(nr) + ")") if nr else ""} {src}</div>'
                   f'<div class="small muted">«{esc((rm.get("quote") or "")[:300])}»</div>')
    elif out.get("entscheid_art") == "registereintrag":
        rm_html = '<div><b>Rechtsmittel:</b> <span class="b warn">noch nicht bestimmt — Registerverfahren nach Bundesrecht</span></div>'
    h = [f"<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'><title>Datenschutz-Dossier · {esc(s['name'])}</title><style>{CSS}</style></head><body>",
         "<button class='print' onclick='window.print()'>⎙ Drucken / als PDF sichern</button>",
         f"<div class='sub'>Kanton Schaffhausen · Compliance-Databank · Datenschutz-Dossier · Stand {date.today().isoformat()}</div>",
         f"<h1>{esc(s['name'])}</h1>",
         f"<div class='sub'>{esc(s.get('dienststelle') or '')} · {esc(s.get('department') or '')}"
         f"{(' · Kontakt: ' + esc(' · '.join(map(str, kontakt)))) if kontakt else ''}</div>",
         "<div class='grid'>",
         f"<div><b>DVSH:</b> {esc(dv.get('status') or 'nicht modelliert')}{' · online' if dv.get('online') else ''}"
         f"{(' · Vollzug: ' + esc(dv.get('vollzugsbehoerde'))) if dv.get('vollzugsbehoerde') else ''}</div>",
         f"<div><b>Ergebnis des Verfahrens:</b> {esc(OUTCOME.get(out.get('entscheid_art'), out.get('entscheid_art') or '—'))}"
         f"{(' — «' + esc(out['ergebnis_dokument']) + '»') if out.get('ergebnis_dokument') else ''}</div>",
         "</div>"]
    if dv.get("kurzbeschreibung"):
        h.append(f"<div class='small'>{esc(dv['kurzbeschreibung'][:400])}</div>")
    if laws:
        h.append("<h2>Rechtsgrundlagen des Services (DVSH)</h2><div>" + " ".join(laws) + "</div>")
    if rm_html:
        h.append("<h2>Rechtsmittel gegen den Entscheid</h2>" + rm_html)
    for f in forms:
        dfs = f.get("data_fields") or []
        bu = f.get("burden") or {}
        h.append(f"<div class='form'><h2>Formular: {esc(f['title'])}</h2>")
        facts = [CHAN.get(f.get("submission_channel"), f.get("submission_channel") or "Kanal unbekannt")]
        if f.get("signature_requirement"):
            facts.append("Unterschrift: " + esc(f["signature_requirement"]))
        if bu:
            facts.append(f"Bürgerlast: {bu.get('inputs', 0)} Angaben · ~{bu.get('minutes', 0)} Min · {bu.get('prefillable', 0)} aus dem Einwohnerregister vorbefüllbar")
        if f.get("purpose"):
            facts.append("Zweck: " + esc(f["purpose"]))
        ck = (f.get("check") or {}).get("status")
        if ck in CHECK:
            facts.append(f'<span class="b bad">{CHECK[ck]}</span>')
        h.append("<div class='small'>" + " · ".join(facts) + "</div>")
        if dfs:
            h.append("<h3>Verlangte Daten</h3><table><thead><tr><th>Datenfeld</th><th>Pflicht</th><th>Standard / Datentyp</th><th>Rechtsgrundlage</th></tr></thead><tbody>")
            h.extend(field_row(d) for d in dfs)
            h.append("</tbody></table>")
        if f.get("beilagen"):
            h.append("<h3>Beilagen</h3><div class='small'>" + " · ".join(
                f"{esc(b['bezeichnung'])}" + (f" <span class='b ok'>Once-Only: {esc(HALTER.get(b['halter'], b['halter']))}</span>" if b.get("fetchable") else (f" <span class='muted'>({esc(HALTER.get(b['halter'], b['halter']))})</span>" if b.get("halter") else ""))
                for b in f["beilagen"]) + "</div>")
        if f.get("disclosures"):
            h.append("<h3>Empfänger (belegte Bekanntgaben)</h3><div class='small'>" + " · ".join(
                f"{esc(x['empfaenger'])} <span class='muted'>({esc(x.get('mode') or '')}{(', ' + esc(x.get('short_title') or '') + ' ' + esc(x.get('article_no') or '')) if x.get('article_no') else ''})</span>"
                for x in f["disclosures"]) + "</div>")
        else:
            h.append("<h3>Empfänger</h3><div class='small muted'>keine belegte Bekanntgabe erfasst — offen</div>")
        ret = f.get("retention") or []
        if ret:
            h.append("<h3>Aufbewahrung / Löschung</h3><div class='small'>" + " ".join(
                f"<div>• {esc(r.get('summary') or '')} <span class='muted'>({esc(r.get('short_title') or '')} {esc(r.get('article_no') or '')})</span></div>"
                for r in ret[:4]) + "</div>")
        else:
            h.append("<h3>Aufbewahrung / Löschung</h3><div class='small muted'>keine sektorale Frist — es gelten die allgemeinen Regeln (KDSG Art. 4: nicht länger als zur Zweckerreichung erforderlich; Art. 17: Vernichtung und Archivierung)</div>")
        td = todo(f)
        h.append("<h3>Handlungsbedarf</h3><div class='small'>" + (" · ".join(f"<span class='b warn'>{esc(t)}</span>" for t in td) if td else "<span class='b ok'>keine offenen Punkte</span>") + "</div></div>")
    if not forms:
        h.append("<div class='box small'>Dieser Service ist im DVSH ohne Formular modelliert (Kanal: E-Mail, Telefon oder externer Link) — es gibt keine Feld-Schicht.</div>")
    h.append("<div class='foot'>Quelle: citygov.db (Feld-Schicht kuratiert; Rechtsgrundlagen gegen die amtlichen Gesetzestexte geprüft; eCH aus den offiziellen XSDs; Empfänger und Fristen nur mit Artikel-Beleg). "
             "«zu ermitteln» und «offen» sind Wissenslücken der Databank, keine festgestellten Verstösse. Schutzstufen (ISV) sind für alle Felder noch nicht festgelegt — kantonaler Entscheid ausstehend.</div></body></html>")
    return "\n".join(h)


def main():
    pdf = "--pdf" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = int(sys.argv[sys.argv.index("--only") + 1])
    D = json.load(open(os.path.join(ROOT, "data_export.json"), encoding="utf-8"))
    dst = {d["name"]: d for d in D.get("dienststellen", [])}
    by_svc = {}
    for f in D["forms"]:
        by_svc.setdefault(f["service_id"], []).append(f)
    os.makedirs(OUT, exist_ok=True)
    index = []
    n = 0
    for s in sorted(D["services"], key=lambda x: (x.get("department") or "", x["name"])):
        if only and s["id"] != only:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", (s.get("slug") or s["name"]).lower()).strip("-")[:80] or f"service-{s['id']}"
        page = dossier(s, by_svc.get(s["id"], []), dst.get(s.get("dienststelle")), D.get("attribut_katalog"))
        open(os.path.join(OUT, slug + ".html"), "w", encoding="utf-8").write(page)
        index.append((s, slug, len(by_svc.get(s["id"], []))))
        n += 1
        if pdf and os.path.exists(CHROME):
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={os.path.join(OUT, slug + '.pdf')}",
                            "file://" + os.path.join(OUT, slug + ".html")],
                           capture_output=True, timeout=120)
    if not only:
        rows = "".join(f"<tr><td>{esc(s.get('department') or '')}</td><td><a href='{slug}.html'>{esc(s['name'])}</a></td>"
                       f"<td>{esc(s.get('dienststelle') or '')}</td><td>{nf}</td>"
                       f"<td>{('<a href=' + chr(39) + slug + '.pdf' + chr(39) + '>PDF</a>') if os.path.exists(os.path.join(OUT, slug + '.pdf')) else ''}</td></tr>"
                       for s, slug, nf in index)
        open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(
            f"<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'><title>Datenschutz-Dossiers</title><style>{CSS}</style></head><body>"
            f"<h1>Datenschutz-Dossiers je Service</h1><div class='sub'>{n} Services · Stand {date.today().isoformat()} · eine Seite je Service, druckbar</div>"
            f"<table><thead><tr><th>Departement</th><th>Service</th><th>Dienststelle</th><th>Formulare</th><th></th></tr></thead><tbody>{rows}</tbody></table></body></html>")
    print(f"dossiers: {n} HTML" + (" + PDF" if pdf else "") + f" in {OUT}")


if __name__ == "__main__":
    main()
