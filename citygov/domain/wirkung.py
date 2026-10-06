#!/usr/bin/env python3
"""The change-impact index («Wirkung»): if this law or this article changes, which data
points, Datenfelder, Formulare, services and Dienststellen cite it — and which edition
of the law the databank read and what the latest currency check found.

Computed ONCE for the export: export_json.py calls berechne(conn, forms) after the
Dienststellen are known, adds the edition layer with stand_anfuegen(conn, index) and
stops the export when pruefen(conn, index, forms) returns an error. Deterministic
(sorted lists, no clock), standard library only.

Units and predicates (one number, one predicate):
  zitate        rows of data_field_legal_basis (a field may cite an article once per
                Abs./lit.; the rows are counted as they are stored)
  felder        distinct Datenfelder with such a row
  datenpunkte   the atomic unit of every data-standard figure: the Teilfelder of a cited
                field, or the field itself when it has none (as export_json._units)
  formulare     Formulare of those fields
  services      the services of those Formulare
  dienststellen the Dienststelle of those Formulare by the export's rule
                (service.dienststelle, else form.publisher_dienststelle, else
                «(ohne Dienststelle)»)
  weitere       other places that rest on the article, kept apart so the counts above
                keep their meaning: regeln (data_rule rows), rechtsmittel_formulare
                (Formulare whose remedy rule cites it as provision or Frist),
                bekanntgabe_formulare (form_disclosure), entscheid_formulare
                (form_outcome.article_id)
A law or article is listed when at least one of these cites it.

Edition layer (stand_anfuegen; needs gesetz_stand and gesetz_stand_pruefung):
  stand     the row of gesetz_stand (veraltet = its basis no longer matches the databank)
  pruefung  the latest row of gesetz_stand_pruefung (veraltet = it compared another
            stand than the one recorded now)
  uebersicht.betroffen  the union of what cites the laws whose latest check found a newer
            edition in force — the list to re-read, not a finding that anything changed

    python3 scripts/wirkung.py                    # overview
    python3 scripts/wirkung.py --gesetz 810.100   # one law (law id, SHR or SR)
    python3 scripts/wirkung.py --artikel 4711     # one article id
    python3 scripts/wirkung.py --json             # the whole index
    python3 scripts/wirkung.py --selbsttest       # every invariant fires on a tampered copy
"""
import argparse
import copy
import json
import os
import sqlite3
import sys


OHNE_DST = "(ohne Dienststelle)"
WEITERE = ("rechtsmittel_formulare", "bekanntgabe_formulare", "entscheid_formulare")

# German labels and tones of the edition layer (to be merged into labels.py as one source)
LABELS = {
    "stand_status": {"belegt": "Stand belegt", "widerspruch": "Quellen nennen verschiedene Stände",
                     "unbekannt": "Stand unbekannt", "nicht_erhoben": "noch nicht erhoben"},
    "stand_quelle": {"einlesen": "beim Einlesen der Artikel vermerkt",
                     "pdf_datei": "im Kopf der gelesenen PDF-Datei"},
    # a Stand from the PDF head: are the stored article texts found in that file?
    "textabgleich": {"abgeglichen": "die gespeicherten Artikeltexte stehen in dieser Datei",
                     "nicht_abgeglichen": "Datei nicht mit gelesenen Artikeltexten abgeglichen (kein zitierter "
                                          "Artikel hat einen gespeicherten Text)"},
    "datei_herkunft": {"gesetzessammlung": "Gesetzessammlung des Kantons (PDF)",
                       "rechtsbuch_api": "Schaffhauser Rechtsbuch (PDF)", "fedlex": "Fedlex (PDF)"},
    "pruef_quelle": {"rechtsbuch": "Schaffhauser Rechtsbuch", "fedlex": "Fedlex", "keine": "keine Quelle"},
    "ergebnis": {"aktuell": "gelesener Stand ist in Kraft", "neuer_stand": "neuere Fassung in Kraft",
                 "aufgehoben": "laut Quelle aufgehoben", "stand_unbekannt": "nicht vergleichbar: gelesener Stand unbekannt",
                 "nicht_gefunden": "bei der Quelle nicht gefunden", "nicht_pruefbar": "nicht prüfbar: keine amtliche Nummer",
                 "fehler": "Abfrage fehlgeschlagen", "unklar": "Antwort nicht vergleichbar", "nicht_geprueft": "noch nicht geprüft"},
}
# who acts next (labels.TON): a newer edition means the databank re-reads the cited articles
TON = {"aktuell": "ok", "neuer_stand": "open", "aufgehoben": "open", "stand_unbekannt": "open",
       "nicht_gefunden": "open", "nicht_pruefbar": "open", "fehler": "open", "unklar": "open",
       "nicht_geprueft": "open"}


def _dst(service_dst, publisher):
    """The Dienststelle of a Formular — the rule of export_json.uebersichten.dst_of."""
    return (service_dst or publisher or OHNE_DST).strip()


def _nummer(l):
    if l["jurisdiction_level"] == "federal" and l["sr_number"]:
        return "SR " + l["sr_number"]
    if l["cantonal_ref"]:
        return l["cantonal_ref"]
    return None


def _rows(conn, sql, *a):
    cur = conn.execute(sql, a)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _grundlagen(conn):
    """Everything the index is built from, read once."""
    g = {}
    g["einheiten"] = {r["id"]: (r["n"] or 1) for r in _rows(conn,
        "SELECT d.id, (SELECT COUNT(*) FROM data_subfield s WHERE s.data_field_id=d.id) n FROM data_field d")}
    g["feld_form"] = {r["id"]: r["form_id"] for r in _rows(conn, "SELECT id, form_id FROM data_field")}
    g["formulare"] = {r["id"]: {"service": r["service_id"], "dst": _dst(r["sdst"], r["publisher_dienststelle"])}
                      for r in _rows(conn, "SELECT f.id, f.service_id, f.publisher_dienststelle, s.dienststelle sdst "
                                           "FROM form f LEFT JOIN service s ON s.id=f.service_id")}
    g["zitate"] = _rows(conn, "SELECT lb.id, lb.data_field_id, lb.article_id, a.law_id FROM data_field_legal_basis lb "
                              "JOIN article a ON a.id=lb.article_id ORDER BY lb.id")
    g["artikel"] = {r["id"]: r for r in _rows(conn, "SELECT id, law_id, article_no, heading FROM article")}
    g["gesetze"] = {r["id"]: r for r in _rows(conn, "SELECT id, title, short_title, jurisdiction_level, sr_number, "
                                                    "cantonal_ref FROM law")}
    w = {}
    for r in _rows(conn, "SELECT article_id FROM data_rule"):
        w.setdefault(r["article_id"], {}).setdefault("regeln", 0)
        w[r["article_id"]]["regeln"] += 1
    def dazu(aid, art, fid):
        if aid is not None:
            w.setdefault(aid, {}).setdefault(art, set()).add(fid)
    for r in _rows(conn, "SELECT o.form_id, rr.article_id, rr.frist_article_id FROM form_outcome o "
                         "JOIN rechtsmittel_regel rr ON rr.id=o.rechtsmittel_regel_id"):
        dazu(r["article_id"], "rechtsmittel_formulare", r["form_id"])
        dazu(r["frist_article_id"], "rechtsmittel_formulare", r["form_id"])
    for r in _rows(conn, "SELECT form_id, article_id FROM form_disclosure WHERE article_id IS NOT NULL"):
        dazu(r["article_id"], "bekanntgabe_formulare", r["form_id"])
    for r in _rows(conn, "SELECT form_id, article_id FROM form_outcome WHERE article_id IS NOT NULL"):
        dazu(r["article_id"], "entscheid_formulare", r["form_id"])
    g["weitere"] = w
    return g


def _eintrag(felder, n_zitate, g):
    """Counts and lists for a set of cited fields."""
    forms = sorted({g["feld_form"][f] for f in felder})
    services = sorted({g["formulare"][f]["service"] for f in forms if g["formulare"][f]["service"] is not None})
    dsts = sorted({g["formulare"][f]["dst"] for f in forms})
    return {"n_zitate": n_zitate, "n_felder": len(felder), "n_datenpunkte": sum(g["einheiten"][f] for f in felder),
            "formulare": forms, "n_formulare": len(forms), "services": services, "n_services": len(services),
            "dienststellen": dsts, "n_dienststellen": len(dsts)}


def _weitere(ws):
    out = {"regeln": sum(w.get("regeln", 0) for w in ws)}
    for k in WEITERE:
        out[k] = sorted(set().union(*[w.get(k, set()) for w in ws]))
    return out


def berechne(conn, forms=None):
    """The index: {gesetze: [...], summen: {...}, labels, ton}. `forms` (the export's list)
    is not needed for the figures; pruefen() compares against it."""
    g = _grundlagen(conn)
    je_artikel = {}
    for z in g["zitate"]:
        a = je_artikel.setdefault(z["article_id"], {"felder": set(), "n": 0})
        a["felder"].add(z["data_field_id"]); a["n"] += 1
    artikel_ids = set(je_artikel) | {a for a, w in g["weitere"].items()
                                      if w.get("regeln") or any(w.get(k) for k in WEITERE)}
    je_gesetz = {}
    for aid in artikel_ids:
        je_gesetz.setdefault(g["artikel"][aid]["law_id"], []).append(aid)
    gesetze = []
    for lid, aids in je_gesetz.items():
        l = g["gesetze"][lid]
        arts = []
        for aid in sorted(aids):
            a = g["artikel"][aid]
            z = je_artikel.get(aid, {"felder": set(), "n": 0})
            e = {"id": aid, "nr": a["article_no"], "titel": a["heading"] or None,
                 "felder": sorted(z["felder"])}
            e.update(_eintrag(z["felder"], z["n"], g))
            e["weitere"] = _weitere([g["weitere"].get(aid, {})])
            arts.append(e)
        felder = set().union(*[je_artikel.get(a, {"felder": set()})["felder"] for a in aids])
        e = {"id": lid, "titel": l["title"], "kurz": l["short_title"], "ebene": l["jurisdiction_level"],
             "nummer": _nummer(l), "n_artikel": sum(1 for x in arts if x["n_zitate"]),
             "n_artikel_gesamt": len(arts)}
        e.update(_eintrag(felder, sum(x["n_zitate"] for x in arts), g))
        e["weitere"] = _weitere([g["weitere"].get(a, {}) for a in aids])
        e["artikel"] = arts
        gesetze.append(e)
    gesetze.sort(key=lambda e: (-e["n_datenpunkte"], -e["n_zitate"], -e["n_artikel_gesamt"], e["id"]))
    alle = set().union(*[set(x["felder"]) for e in gesetze for x in e["artikel"]]) if gesetze else set()
    summen = _eintrag(alle, len(g["zitate"]), g)
    summen.update({"n_gesetze": len(gesetze), "n_gesetze_zitiert": sum(1 for e in gesetze if e["n_zitate"]),
                   "n_artikel": sum(e["n_artikel"] for e in gesetze),
                   "n_artikel_gesamt": sum(e["n_artikel_gesamt"] for e in gesetze)})
    for k in ("formulare", "services", "dienststellen"):
        summen.pop(k)
    return {"gesetze": gesetze, "summen": summen, "labels": LABELS, "ton": TON}


# ---- the edition layer ----------------------------------------------------------------------
def stand_anfuegen(conn, index):
    """Adds stand and pruefung to every law and the overview. Raises sqlite3.OperationalError
    «no such table» when gesetz_stand or gesetz_stand_pruefung is missing (export_json then
    skips this layer loudly)."""
    from citygov.domain import gesetz_stand as GS
    rows = {r["law_id"]: r for r in _rows(conn, "SELECT * FROM gesetz_stand")}
    letzte = {r["law_id"]: r for r in _rows(conn,
        "SELECT p.* FROM gesetz_stand_pruefung p WHERE p.geprueft_am = "
        "(SELECT MAX(q.geprueft_am) FROM gesetz_stand_pruefung q WHERE q.law_id = p.law_id)")}
    zitiert = GS.zitierte_artikel(conn)
    for e in index["gesetze"]:
        r = rows.get(e["id"])
        e["stand"] = None if r is None else {
            "stand": r["stand"], "status": r["status"], "quelle": r["stand_quelle"], "datei": r["datei"],
            "datei_herkunft": r["datei_herkunft"], "texte_zitiert": r["texte_zitiert"],
            "texte_gefunden": r["texte_gefunden"], "texte_vollstaendig": r["texte_vollstaendig"],
            "grund": r["grund"], "erhoben_am": r["erhoben_am"],
            # a Stand read from the PDF head rests on that file; it is tied to the stored
            # articles only when their texts were found in it
            "textabgleich": (None if r["stand_quelle"] != "pdf_datei" else
                             "abgeglichen" if (r["texte_gefunden"] or 0) > 0 else "nicht_abgeglichen"),
            "veraltet": r["basis"] != GS.fingerabdruck(conn, e["id"], zitiert)}
        p = letzte.get(e["id"])
        e["pruefung"] = None if p is None else {
            "geprueft_am": p["geprueft_am"], "quelle": p["quelle"], "ergebnis": p["ergebnis"],
            "stand_gelesen": p["stand_gelesen"], "fassung_gelesen": p["fassung_gelesen"],
            "stand_aktuell": p["stand_aktuell"], "fassung_aktuell": p["fassung_aktuell"],
            "n_neuere": p["n_neuere"], "kuenftig": json.loads(p["kuenftig"] or "[]"), "grund": p["grund"],
            "veraltet": (r is None) or p["stand_gelesen"] != r["stand"]}
    index["uebersicht"] = _uebersicht(conn, index)
    return index


def _zaehle(werte):
    out = {}
    for v in werte:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


def _stand_key(e):
    s = e.get("stand")
    if s is None:
        return "nicht_erhoben"
    return f"belegt_{s['quelle']}" if s["status"] == "belegt" else s["status"]


def _pruef_key(e):
    p = e.get("pruefung")
    return "nicht_geprueft" if p is None else p["ergebnis"]


def _uebersicht(conn, index):
    g = _grundlagen(conn)
    ges = index["gesetze"]
    zitiert = [e for e in ges if e["n_zitate"]]
    neuer = [e for e in ges if _pruef_key(e) == "neuer_stand" and not e["pruefung"]["veraltet"]]
    felder = set().union(*[set(x["felder"]) for e in neuer for x in e["artikel"]]) if neuer else set()
    betroffen = _eintrag(felder, sum(e["n_zitate"] for e in neuer), g)
    betroffen.update({"gesetze": [e["id"] for e in neuer], "n_gesetze": len(neuer),
                      "n_artikel": sum(e["n_artikel"] for e in neuer)})
    tage = sorted({e["pruefung"]["geprueft_am"] for e in ges if e.get("pruefung")})
    return {
        "stand": _zaehle(_stand_key(e) for e in ges),
        "stand_zitiert": _zaehle(_stand_key(e) for e in zitiert),
        "zitate_mit_stand": sum(e["n_zitate"] for e in ges if (e.get("stand") or {}).get("stand")),
        "pruefung": _zaehle(_pruef_key(e) for e in ges),
        "pruefung_zitiert": _zaehle(_pruef_key(e) for e in zitiert),
        "geprueft_am": tage[-1] if tage else None, "geprueft_von": tage[0] if tage else None,
        "n_stand_veraltet": sum(1 for e in ges if (e.get("stand") or {}).get("veraltet")),
        "n_pruefung_veraltet": sum(1 for e in ges if (e.get("pruefung") or {}).get("veraltet")),
        "n_kuenftig": sum(1 for e in ges if (e.get("pruefung") or {}).get("kuenftig")),
        # cited laws whose Stand rests on the PDF head alone (no stored article text found in the file)
        "n_zitiert_ohne_textabgleich": sum(1 for e in zitiert if (e.get("stand") or {}).get("textabgleich")
                                           == "nicht_abgeglichen"),
        "betroffen": betroffen,
    }


# ---- invariants ---------------------------------------------------------------------------
def pruefen(conn, index=None, forms=None):
    """Invariants of the index against the databank (and the export's forms when given).
    List of error texts; empty = valid."""
    if index is None:
        index = berechne(conn)
    f = []
    g = _grundlagen(conn)
    zit_art, zit_gesetz = {}, {}
    for z in g["zitate"]:
        zit_art.setdefault(z["article_id"], []).append(z["data_field_id"])
        zit_gesetz.setdefault(z["law_id"], 0)
        zit_gesetz[z["law_id"]] += 1
    def listen(wo, e):
        for k in ("formulare", "services", "dienststellen"):
            if e.get(f"n_{k}") != len(e.get(k) or []):
                f.append(f"{wo}: n_{k} {e.get(f'n_{k}')} != {len(e.get(k) or [])} listed")
            if (e.get(k) or []) != sorted(set(e.get(k) or [])):
                f.append(f"{wo}: {k} not sorted or not distinct")
    gesehen = set()
    for e in index.get("gesetze") or []:
        wo = f"wirkung law {e.get('id')}"
        if e.get("id") not in g["gesetze"]:
            f.append(f"{wo}: no such law"); continue
        if e["id"] in gesehen:
            f.append(f"{wo}: listed twice")
        gesehen.add(e["id"])
        listen(wo, e)
        felder, forms_art, n = set(), set(), 0
        for a in e.get("artikel") or []:
            wa = f"{wo} article {a.get('id')}"
            if g["artikel"].get(a.get("id"), {}).get("law_id") != e["id"]:
                f.append(f"{wa}: the article does not belong to the law"); continue
            listen(wa, a)
            soll = zit_art.get(a["id"], [])
            if a["n_zitate"] != len(soll):
                f.append(f"{wa}: n_zitate {a['n_zitate']} != {len(soll)} citation rows")
            if a["felder"] != sorted(set(soll)) or a["n_felder"] != len(a["felder"]):
                f.append(f"{wa}: felder are not the citing fields")
            if a["n_datenpunkte"] != sum(g["einheiten"].get(x, 0) for x in a["felder"]):
                f.append(f"{wa}: n_datenpunkte {a['n_datenpunkte']} is not the sum of the fields' units")
            if a["formulare"] != sorted({g["feld_form"].get(x) for x in a["felder"]}):
                f.append(f"{wa}: formulare are not the Formulare of the fields")
            if a["dienststellen"] != sorted({g["formulare"][x]["dst"] for x in a["formulare"] if x in g["formulare"]}):
                f.append(f"{wa}: dienststellen are not those of the Formulare")
            w = g["weitere"].get(a["id"], {})
            if a["weitere"].get("regeln") != w.get("regeln", 0) or any(
                    a["weitere"].get(k) != sorted(w.get(k, set())) for k in WEITERE):
                f.append(f"{wa}: weitere differ from data_rule / remedies / disclosures / outcomes")
            if not (a["n_zitate"] or a["weitere"]["regeln"] or any(a["weitere"][k] for k in WEITERE)):
                f.append(f"{wa}: listed although nothing cites it")
            felder |= set(a["felder"]); forms_art |= set(a["formulare"]); n += a["n_zitate"]
        if e["n_zitate"] != n or e["n_zitate"] != zit_gesetz.get(e["id"], 0):
            f.append(f"{wo}: n_zitate {e['n_zitate']} != sum of its articles {n} / citation rows {zit_gesetz.get(e['id'], 0)}")
        if e["n_felder"] != len(felder) or e["n_datenpunkte"] != sum(g["einheiten"].get(x, 0) for x in felder):
            f.append(f"{wo}: n_felder/n_datenpunkte are not those of the union of its articles")
        if e["formulare"] != sorted(forms_art):
            f.append(f"{wo}: formulare are not the union of its articles")
        if e["n_artikel"] != sum(1 for a in e.get("artikel") or [] if a["n_zitate"]) \
                or e["n_artikel_gesamt"] != len(e.get("artikel") or []):
            f.append(f"{wo}: n_artikel / n_artikel_gesamt do not count its articles")
        for k in ("regeln",) + WEITERE:
            soll = (sum(a["weitere"]["regeln"] for a in e["artikel"]) if k == "regeln"
                    else sorted(set().union(*[set(a["weitere"][k]) for a in e["artikel"]])))
            if e["weitere"].get(k) != soll:
                f.append(f"{wo}: weitere.{k} is not the union of its articles")
        st = e.get("stand")
        if st is not None and (st["stand"] is None) != (st["status"] != "belegt"):
            f.append(f"{wo}: stand {st['stand']} does not fit status {st['status']}")
        p = e.get("pruefung")
        if p is not None:
            if p["ergebnis"] == "neuer_stand" and not (p["stand_gelesen"] and p["stand_aktuell"]
                                                       and p["stand_gelesen"] < p["stand_aktuell"]):
                f.append(f"{wo}: pruefung neuer_stand without a later current edition")
            if p["ergebnis"] == "aktuell" and p["stand_gelesen"] != p["stand_aktuell"]:
                f.append(f"{wo}: pruefung aktuell with different editions")
            if st is not None and p["veraltet"] != (p["stand_gelesen"] != st["stand"]):
                f.append(f"{wo}: pruefung.veraltet does not compare the stand recorded now")
    # every cited law is listed; the totals are the databank's
    fehlend = set(zit_gesetz) - gesehen
    if fehlend:
        f.append(f"wirkung: cited laws missing from the index: {sorted(fehlend)[:8]}")
    s = index.get("summen") or {}
    if s.get("n_zitate") != len(g["zitate"]):
        f.append(f"wirkung.summen.n_zitate {s.get('n_zitate')} != {len(g['zitate'])} citation rows")
    alle = {z["data_field_id"] for z in g["zitate"]}
    if s.get("n_felder") != len(alle) or s.get("n_datenpunkte") != sum(g["einheiten"][x] for x in alle):
        f.append("wirkung.summen: n_felder/n_datenpunkte are not those of all citing fields")
    if s.get("n_formulare") != len({g["feld_form"][x] for x in alle}):
        f.append("wirkung.summen.n_formulare is not the number of citing Formulare")
    if s.get("n_gesetze") != len(index.get("gesetze") or []) or s.get("n_gesetze_zitiert") != len(zit_gesetz):
        f.append("wirkung.summen: n_gesetze / n_gesetze_zitiert do not count the laws")
    reihe = [(-e["n_datenpunkte"], -e["n_zitate"], -e["n_artikel_gesamt"], e["id"]) for e in index.get("gesetze") or []]
    if reihe != sorted(reihe):
        f.append("wirkung.gesetze are not in their documented order")
    u = index.get("uebersicht")
    if u is not None:
        ges = index["gesetze"]
        for k, werte in (("stand", [_stand_key(e) for e in ges]), ("pruefung", [_pruef_key(e) for e in ges])):
            if u.get(k) != _zaehle(werte) or sum((u.get(k) or {}).values()) != len(ges):
                f.append(f"wirkung.uebersicht.{k} does not count the laws")
        b = u.get("betroffen") or {}
        soll = sorted(e["id"] for e in ges if _pruef_key(e) == "neuer_stand" and not e["pruefung"]["veraltet"])
        if sorted(b.get("gesetze") or []) != soll or b.get("n_gesetze") != len(soll):
            f.append("wirkung.uebersicht.betroffen does not list the laws with a newer edition")
        else:
            felder = set().union(*[set(x["felder"]) for e in ges if e["id"] in soll for x in e["artikel"]]) if soll else set()
            if b.get("n_felder") != len(felder) or b.get("n_formulare") != len({g["feld_form"][x] for x in felder}):
                f.append("wirkung.uebersicht.betroffen counts are not the union of those laws")
    # one computation: the Dienststelle and the units are the export's
    if forms is not None:
        fm = {x["id"]: x for x in forms}
        for fid, info in g["formulare"].items():
            if fid in fm and "dienststelle" in fm[fid] and fm[fid]["dienststelle"] != info["dst"]:
                f.append(f"wirkung: Formular {fid} has Dienststelle {info['dst']!r} here and "
                         f"{fm[fid]['dienststelle']!r} in the export"); break
        for x in forms:
            for d in x.get("data_fields") or []:
                subs = [s for s in (d.get("subfields") or []) if isinstance(s, dict)]
                if g["einheiten"].get(d["id"]) != (len(subs) or 1):
                    f.append(f"wirkung: Datenfeld {d['id']} has {g['einheiten'].get(d['id'])} units here and "
                             f"{len(subs) or 1} in the export"); break
    # the layer's own words (titles and quotes of the sources stay verbatim)
    if "ß" in json.dumps([index.get("labels"), LABELS], ensure_ascii=False):
        f.append("wirkung: a label uses «ß» (Swiss orthography: ss)")
    return f


# ---- self-test and command line --------------------------------------------------------------
def selbsttest(conn):
    """Every invariant must fire on a tampered copy of today's index."""
    idx = berechne(conn)
    try:
        stand_anfuegen(conn, idx)
    except sqlite3.OperationalError:
        pass
    assert not pruefen(conn, idx), pruefen(conn, idx)[:3]
    e = next(x for x in idx["gesetze"] if x["n_zitate"] and len(x["artikel"]) > 1)
    a = next(x for x in e["artikel"] if x["n_zitate"])
    faelle = {
        "n_zitate eines Artikels": lambda i, e, a: a.__setitem__("n_zitate", a["n_zitate"] + 1),
        "Feld fehlt": lambda i, e, a: a.__setitem__("felder", a["felder"][1:]),
        "Datenpunkte": lambda i, e, a: a.__setitem__("n_datenpunkte", a["n_datenpunkte"] + 1),
        "Formular fremd": lambda i, e, a: a.__setitem__("formulare", sorted(a["formulare"] + [10 ** 6])),
        "n_formulare": lambda i, e, a: e.__setitem__("n_formulare", e["n_formulare"] + 1),
        "Dienststelle": lambda i, e, a: a.__setitem__("dienststellen", sorted(a["dienststellen"] + ["X"])),
        "Gesetz fehlt": lambda i, e, a: i["gesetze"].remove(e),
        "Reihenfolge": lambda i, e, a: i["gesetze"].reverse(),
        "Summe": lambda i, e, a: i["summen"].__setitem__("n_zitate", 0),
        "weitere": lambda i, e, a: a["weitere"].__setitem__("regeln", a["weitere"]["regeln"] + 1),
        "fremder Artikel": lambda i, e, a: a.__setitem__("id", next(x for x in conn.execute(
            "SELECT id FROM article WHERE law_id != ? LIMIT 1", [e["id"]]))[0]),
        "ß": lambda i, e, a: i["labels"]["ergebnis"].__setitem__("aktuell", "gemäß Quelle in Kraft"),
    }
    if idx.get("uebersicht"):
        faelle["Übersicht"] = lambda i, e, a: i["uebersicht"]["pruefung"].__setitem__("aktuell", 999)
        faelle["betroffen"] = lambda i, e, a: i["uebersicht"]["betroffen"].__setitem__("gesetze", [])
    stumm = []
    for name, fn in faelle.items():
        k = copy.deepcopy(idx)
        ke = next(x for x in k["gesetze"] if x["id"] == e["id"])
        ka = next(x for x in ke["artikel"] if x["id"] == a["id"])
        fn(k, ke, ka)
        if not pruefen(conn, k):
            stumm.append(name)
    print(f"Selbsttest: {len(faelle) - len(stumm)} von {len(faelle)} Manipulationen erkannt"
          + (f" — STUMM: {stumm}" if stumm else ""))
    return not stumm


def main():
    from citygov.core.common import DB_PATH, connect
    ap = argparse.ArgumentParser(description="Wirkungsindex: wer zitiert welches Gesetz und welchen Artikel.")
    ap.add_argument("--gesetz", help="ein Gesetz (law id, SHR oder SR)")
    ap.add_argument("--artikel", type=int, help="ein Artikel (article id)")
    ap.add_argument("--json", action="store_true", help="den ganzen Index als JSON")
    ap.add_argument("--selbsttest", action="store_true", help="jede Prüfregel an manipulierten Kopien auslösen")
    args = ap.parse_args()
    conn = connect(DB_PATH)
    if args.selbsttest:
        sys.exit(0 if selbsttest(conn) else 1)
    idx = berechne(conn)
    try:
        stand_anfuegen(conn, idx)
    except sqlite3.OperationalError as ex:
        print(f"  (Gesetzesstand fehlt: {ex})", file=sys.stderr)
    fehler = pruefen(conn, idx)
    if args.json:
        print(json.dumps(idx, ensure_ascii=False, indent=1, sort_keys=True))
    elif args.gesetz or args.artikel:
        q = (args.gesetz or "").replace("SHR", "").replace("SR", "").strip()
        for e in idx["gesetze"]:
            if args.gesetz and q not in (str(e["id"]), (e["nummer"] or "").split(" ")[-1]):
                continue
            arts = [a for a in e["artikel"] if not args.artikel or a["id"] == args.artikel]
            if args.artikel and not arts:
                continue
            print(json.dumps(dict({k: v for k, v in e.items() if k != "artikel"}, artikel=arts),
                             ensure_ascii=False, indent=1))
    else:
        s = idx["summen"]
        print(f"Wirkung: {s['n_gesetze']} Gesetze ({s['n_gesetze_zitiert']} von Datenfeldern zitiert), "
              f"{s['n_artikel_gesamt']} Artikel ({s['n_artikel']} von Datenfeldern zitiert), {s['n_zitate']} Zitate, "
              f"{s['n_felder']} Felder, {s['n_datenpunkte']} Datenpunkte, {s['n_formulare']} Formulare, "
              f"{s['n_services']} Services, {s['n_dienststellen']} Dienststellen")
        for e in idx["gesetze"][:12]:
            p = e.get("pruefung") or {}
            print(f"  {e['nummer'] or '—':<14} {(e['kurz'] or e['titel'])[:34]:<34} {e['n_datenpunkte']:>5} Datenpunkte "
                  f"{e['n_formulare']:>3} Formulare {e['n_services']:>3} Services {e['n_dienststellen']:>2} Dienststellen"
                  f"  | {LABELS['ergebnis'].get(p.get('ergebnis', 'nicht_geprueft'))}")
        if idx.get("uebersicht"):
            print("Übersicht:", json.dumps({k: v for k, v in idx["uebersicht"].items() if k != "betroffen"},
                                         ensure_ascii=False))
            b = idx["uebersicht"]["betroffen"]
            print(f"Betroffen von neueren Fassungen: {b['n_gesetze']} Gesetze, {b['n_artikel']} zitierte Artikel, "
                  f"{b['n_zitate']} Zitate, {b['n_felder']} Felder, {b['n_datenpunkte']} Datenpunkte, "
                  f"{b['n_formulare']} Formulare, {b['n_services']} Services, {b['n_dienststellen']} Dienststellen")
    if fehler:
        print("FEHLER:", *fehler[:10], sep="\n  ", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
