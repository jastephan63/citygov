#!/usr/bin/env python3
"""Konzepte: one preferred element per Angabe and role.

The data-standard comparison groups data points by eCH element. When one Formular
maps the applicant's surname to eCH-0044 officialName and another to eCH-0010
lastName, the two are never compared. This module adds the layer above the
elements: a concept is one real-world Angabe (Vorname, Geburtsdatum, Strasse,
IBAN …) and lists the canonical Angaben (eCH elements, by standard, name and XML
context) that mean exactly that Angabe. Per concept and party role it states which
element the Formulare use in practice:

  Vorschlag              one element (standard + element name) carries at least
                         two thirds (ANTEIL) of the cell's data points and the cell
                         has at least MINDESTENS (10) data points; the Formulare of
                         the cell that use another element or standard are listed
  der Kanton legt fest   no element reaches two thirds, or the cell has fewer than
                         10 data points

The Vorschlag describes the practice of the Formulare; the canton confirms it (an
owner decision). It is a data-standard finding of its own: it does not enter the
headline figures, the Handlungsbedarf board or the Dienststellen figures.

Membership is curated and reviewed: quellen/konzepte.json (read here, never
written) names the members of each concept with the reason, the party entity
types whose own Angabe the concept is («entitaeten»), and the elements that look
alike but mean something else («ausserhalb», with the reason). An element counts
only when it is listed AND passes three checks against the databank under every
catalogue id it has: it exists in the swept eCH catalogue (ech_element), its data
type is one of the concept's «typen», and the naming layer's proposed term
(begriff_vorschlag, else that of an element with the same standard and name) is
one of the concept's «begriffe» — without any term, the canonical label
(canonical_attribute.label) must match the concept's «bezeichnung». A listed
element that fails a check is «gesperrt» (shown with the failed check, not
counted). Every element in use whose name is in «namen» or whose term is in
«begriffe» and that the file does not judge is «nicht beurteilt» (shown, not
counted) — nothing joins a concept without review.

Units and predicates (one number, one predicate):
  data point   the atomic unit of every data-standard figure: a Teilfeld, or the
               Datenfeld itself when it has none (export_json._units)
  Angabe       (standard, element, context) — the natural key of the canonical
               Angabe and its permanent identifier; an element without a context
               may stand in the catalogue under several ids, all of them count
  counted      a data point whose own eCH element is a member and whose ech_state
               is «element»; one the naming layer found to be mapped to the wrong
               element («zuordnung_falsch») is counted apart, never in a cell
  role         the party the point is assigned to (rollen.parteien_anhaengen:
               u.partei.nr -> fm.parteien[]), with its role AND its entity type —
               Gesuchsteller/in as a natural person and as «Person oder
               Organisation» are two cells (a «Name» that may be a firm is not
               simply a Familienname); a point without an assigned party is «ohne
               Rolle», a point of a party whose entity type is not one of the
               concept's «entitaeten» is «andere Entität» (the «Feuerwehr» in a
               course participant's block is an organisation's name, but not the
               participant's own) — neither is in a cell
  element      the practice is read per standard + element name: the XML context
               (personIdentificationType or personIdentificationLightType) only
               says in which structure the same element stands
  cell         concept x role x entity type; share = points of the element /
               points of the cell (whole percent, half up; the rule itself is
               checked in integers: 3 x top >= 2 x n)

Computed ONCE for the export: export_json.py calls berechne(conn, forms) after the
Begriffe layer (ech_state) and the party layer (u.partei), stores the block as
data["konzepte"], which also sets fm["konzepte"] on every Formular, and stops
when pruefen(conn, block, forms) returns an error. Deterministic (sorted lists,
no clock), standard library only.

    python3 scripts/konzepte.py                     # the concepts table
    python3 scripts/konzepte.py --konzept vorname   # one concept: members, cells, Formulare
    python3 scripts/konzepte.py --json              # the whole block
    python3 scripts/konzepte.py --selbsttest        # every invariant fires on a tampered copy
(each honours CITYGOV_DB / CITYGOV_SCHEMA; the command line builds the export's
units in memory with export_json.build and writes nothing)
"""
import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, norm_ascii    # noqa: E402

DATEI = os.path.join(ROOT, "quellen", "konzepte.json")
ANTEIL = (2, 3)            # the Vorschlag needs at least two thirds of the cell's points
MINDESTENS = 10            # ... and the cell at least 10 points
# the entity types of a party (rollen.ENT_PARTEI), in the order the cells are listed
ENTITAETEN = ("natuerliche_person", "gemischt", "organisation", "behoerde", "sache", "offen")

# German labels of the layer (to be merged into labels.py as one source)
LABELS = {
    "status": {"vorschlag": "Vorschlag", "kanton": "der Kanton legt fest"},
    "grund": {"keine_mehrheit": "kein Element erreicht zwei Drittel der Datenpunkte",
              "zu_wenige": "weniger als 10 Datenpunkte"},
    "entitaet": {"natuerliche_person": "natürliche Person", "gemischt": "Person oder Organisation",
                 "organisation": "Organisation", "behoerde": "Behörde", "sache": "Sache", "offen": "offen"},
    "sperre": {"element_fehlt": "nicht im eCH-Katalog", "typ": "Datentyp nicht in der Liste des Konzepts",
               "begriff": "die Prüfung der Bezeichnungen benennt das Element anders",
               "bezeichnung": "ohne Begriff aus der Prüfung der Bezeichnungen, und die kanonische Bezeichnung passt "
                              "nicht"},
    "ohne_rolle": "Partei unklar oder noch nicht zugeordnet — in keiner Zelle",
    "andere_entitaet": "Partei einer anderen Art (Person, Organisation, Sache), deren eigene Angabe das Konzept nicht "
                       "ist — in keiner Zelle",
    "zuordnung_falsch": "eCH-Zuordnung laut Prüfung der Bezeichnungen falsch — nicht gezählt",
    "ausserhalb": "ähnlich, aber eine andere Angabe — nicht gezählt",
    "nicht_beurteilt": "gleicher Elementname oder gleicher Begriff, noch nicht beurteilt — nicht gezählt",
}
# who acts next (labels.TON): the canton — it confirms a Vorschlag or decides the element
TON = {"vorschlag": "dec", "kanton": "dec"}


# ---- the curated file -----------------------------------------------------------------------
def lade(pfad=None):
    """The reviewed concept file (structure checked by datei_pruefen)."""
    with open(pfad or DATEI, encoding="utf-8") as fh:
        return json.load(fh)


def _triple(e):
    return (e[0], e[1], e[2] if len(e) > 2 else None)


def datei_pruefen(K):
    """Structural checks of the curated file. List of error texts."""
    f = []
    r = K.get("regel") or {}
    if (r.get("anteil_zaehler"), r.get("anteil_nenner"), r.get("mindestens")) != (ANTEIL[0], ANTEIL[1], MINDESTENS):
        f.append("konzepte.json: regel does not state the rule of this module (2/3, at least 10)")
    if not (r.get("text") or "").strip():
        f.append("konzepte.json: regel.text missing")
    codes, gesehen = set(), {}
    for k in K.get("konzepte") or []:
        c = k.get("code")
        wo = f"konzepte.json {c}"
        if not c or not re.fullmatch(r"[a-z][a-z0-9_]*", c) or c in codes:
            f.append(f"{wo}: code missing, malformed or twice")
        codes.add(c)
        for key in ("label", "gruppe", "erklaerung", "grund"):
            if not (k.get(key) or "").strip():
                f.append(f"{wo}: {key} missing")
        for key in ("namen", "begriffe", "typen", "elemente", "entitaeten"):
            if not isinstance(k.get(key), list) or not k.get(key):
                f.append(f"{wo}: {key} must be a non-empty list")
        if set(k.get("entitaeten") or []) - set(ENTITAETEN):
            f.append(f"{wo}: entitaeten outside {ENTITAETEN}")
        if not k.get("bezeichnung"):
            f.append(f"{wo}: bezeichnung missing")
        else:
            try:
                re.compile(k["bezeichnung"])
            except re.error:
                f.append(f"{wo}: bezeichnung is no valid pattern")
        mit = set()
        for e in k.get("elemente") or []:
            t = _triple(e)
            if t in gesehen:
                f.append(f"{wo}: element {t} is already listed in {gesehen[t]}")
            gesehen[t] = c
            mit.add(t)
        for a in k.get("ausserhalb") or []:
            t = _triple(a.get("element") or ["", ""])
            if not (a.get("grund") or "").strip():
                f.append(f"{wo}: ausserhalb {t} without grund")
            if t in mit:
                f.append(f"{wo}: element {t} is member and ausserhalb")
    texte = json.dumps(K, ensure_ascii=False)
    if "ß" in texte:
        f.append("konzepte.json: «ß» (Swiss orthography: ss)")
    if re.search(r"\bRisik", texte):
        f.append("konzepte.json: a risk word (gaps are Lücken)")
    return f


# ---- what the databank says about the elements -----------------------------------------------
def katalog(conn):
    """eCH elements, the naming layer's terms and the canonical labels, read once."""
    el = {r[0]: {"standard": r[1], "element": r[2], "context": r[3], "datentyp": r[4]}
          for r in conn.execute("SELECT id, standard, name, context, datatype FROM ech_element")}
    # an element without a context can stand in the catalogue more than once (SQLite's
    # UNIQUE lets NULLs repeat), so one Angabe names a sorted list of ids
    nach_triple = {}
    for i, e in sorted(el.items()):
        nach_triple.setdefault((e["standard"], e["element"], e["context"]), []).append(i)
    term = {r[0]: r[1] for r in conn.execute("SELECT ech_element_id, term FROM begriff_vorschlag")}
    label = {r[0]: r[1] for r in conn.execute(
        "SELECT ech_element_id, label FROM canonical_attribute WHERE ech_element_id IS NOT NULL")}
    geschwister = {}
    for i, e in sorted(el.items()):
        geschwister.setdefault((e["standard"], e["element"]), []).append(i)
    return {"el": el, "nach_triple": nach_triple, "term": term, "label": label, "geschwister": geschwister}


def begriffe_von(kat, eid):
    """The naming layer's term for an element: its own, else those of the elements with
    the same standard and name (the export's Begriffe layer reads them the same way)."""
    if eid in kat["term"]:
        return {kat["term"][eid]}
    e = kat["el"][eid]
    return {kat["term"][x] for x in kat["geschwister"][(e["standard"], e["element"])] if x in kat["term"]}


def _begriffe_t(kat, t):
    return sorted(set().union(*[begriffe_von(kat, i) for i in kat["nach_triple"].get(t, [])]))


def _bezeichnung_t(kat, t):
    return next((kat["label"][i] for i in kat["nach_triple"].get(t, []) if i in kat["label"]), None)


def _falten(s):
    import rollen                    # the one folding rule of the party vocabulary
    return rollen.falten(s)


def _pruefen_id(kat, k, eid):
    e = kat["el"][eid]
    if (e["datentyp"] or "") not in k["typen"]:
        return "typ"
    b = begriffe_von(kat, eid)
    if b:
        return None if b & set(k["begriffe"]) else "begriff"
    return None if re.search(k["bezeichnung"], _falten(kat["label"].get(eid) or "")) else "bezeichnung"


def mitglied_pruefen(kat, k, t):
    """None when the Angabe t = (standard, element, context) passes the concept's three
    checks under every catalogue id it has, else the first failed check."""
    ids = kat["nach_triple"].get(t)
    if not ids:
        return "element_fehlt"
    for eid in ids:
        g = _pruefen_id(kat, k, eid)
        if g:
            return g
    return None


def _el_key(e):
    return f"{e['standard']}:{e['element']}"


# ---- the export's units ---------------------------------------------------------------------
def _einheiten(fm):
    """(Datenfeld, Teilfeld name or None, unit) for every data point of a Formular."""
    for d in fm.get("data_fields") or []:
        subs = [s for s in (d.get("subfields") or []) if isinstance(s, dict)]
        if subs:
            for s in subs:
                yield d, s.get("name"), s
        else:
            yield d, None, d


def _partei(fm, u):
    """(role, entity type) of the party a unit is assigned to, or None."""
    p = u.get("partei") or {}
    if p.get("status") != "zugeordnet":
        return None
    for x in fm.get("parteien") or []:
        if x.get("nr") == p.get("nr"):
            return (x.get("rolle"), x.get("entitaet"))
    return None


def _elemente_liste(ziel, total):
    out = []
    for key, z in ziel.items():
        std, name = key.split(":", 1)
        out.append({"standard": std, "element": name, "n": z["n"], "n_formulare": len(z["formulare"]),
                    "formulare": sorted(z["formulare"]),
                    "anteil": int(100 * z["n"] / total + 0.5) if total else 0})
    out.sort(key=lambda x: (-x["n"], -x["n_formulare"], x["standard"], x["element"]))
    return out


def _sammeln(ziel, key, fid):
    z = ziel.setdefault(key, {"n": 0, "formulare": set()})
    z["n"] += 1
    z["formulare"].add(fid)


# ---- the computation ------------------------------------------------------------------------
def berechne(conn, forms, K=None):
    """The block {regel, labels, ton, konzepte, summen, …}; sets fm["konzepte"] on every
    Formular. Raises ValueError when the curated file is malformed."""
    K = K if K is not None else lade()
    fehler = datei_pruefen(K)
    if fehler:
        raise ValueError("quellen/konzepte.json: " + " | ".join(fehler[:5]))
    kat = katalog(conn)
    ord_rolle = {r[0]: r[1] for r in conn.execute("SELECT code, ord FROM partei_rolle")}

    def angabe(t, **mehr):
        ids = kat["nach_triple"].get(t) or []
        return dict({"standard": t[0], "element": t[1], "context": t[2], "element_ids": ids,
                     "datentyp": kat["el"][ids[0]]["datentyp"] if ids else None,
                     "begriffe": _begriffe_t(kat, t), "bezeichnung": _bezeichnung_t(kat, t)}, **mehr)

    # members, blocked members, judged outsiders, per concept
    mitglied = {}                       # element id -> concept code (every id of a member Angabe)
    konzepte, datei = [], {}
    for k in K["konzepte"]:
        datei[k["code"]] = k
        mit, gesperrt = [], []
        for e in k["elemente"]:
            t = _triple(e)
            g = mitglied_pruefen(kat, k, t)
            if g:
                gesperrt.append(angabe(t, sperre=g))
            else:
                mit.append(angabe(t))
                for eid in kat["nach_triple"][t]:
                    mitglied[eid] = k["code"]
        konzepte.append({"code": k["code"], "label": k["label"], "gruppe": k["gruppe"],
                         "erklaerung": k["erklaerung"], "grund": k["grund"],
                         "entitaeten": [x for x in ENTITAETEN if x in k["entitaeten"]],
                         "mitglieder": mit, "gesperrt": gesperrt,
                         "ausserhalb": [angabe(_triple(a["element"]), grund=a["grund"])
                                        for a in k.get("ausserhalb") or []]})
    beurteilt = {_triple(e) for k in K["konzepte"] for e in k["elemente"]} | \
                {_triple(a["element"]) for k in K["konzepte"] for a in k.get("ausserhalb") or []}

    # one pass over the export's units
    benutzt = {}            # Angabe -> [n element, n zuordnung_falsch, Formulare]
    zellen = {}             # (code, rolle, entitaet) -> element key -> {n, formulare}
    ohne_rolle, andere, falsch = {}, {}, {}     # code -> element key -> {n, formulare}
    punkte = {}             # form id -> [(feld, teil, code, (rolle, entitaet) | None, im Konzept?, element key)]
    for fm in forms:
        for d, teil, u in _einheiten(fm):
            e = u.get("ech") or {}
            eid = e.get("id")
            if eid is None or not e.get("element") or eid not in kat["el"]:
                continue
            st = u.get("ech_state")
            x = kat["el"][eid]
            b = benutzt.setdefault((x["standard"], x["element"], x["context"]), [0, 0, set()])
            b[2].add(fm["id"])
            b[0] += st == "element"
            b[1] += st == "zuordnung_falsch"
            code = mitglied.get(eid)
            if code is None or st not in ("element", "zuordnung_falsch"):
                continue
            key = _el_key(x)
            if st == "zuordnung_falsch":
                _sammeln(falsch.setdefault(code, {}), key, fm["id"])
                continue
            p = _partei(fm, u)
            if p is None:
                _sammeln(ohne_rolle.setdefault(code, {}), key, fm["id"])
            elif p[1] not in datei[code]["entitaeten"]:
                _sammeln(andere.setdefault(code, {}), key, fm["id"])
            else:
                _sammeln(zellen.setdefault((code,) + p, {}), key, fm["id"])
            punkte.setdefault(fm["id"], []).append(
                (d["id"], teil, code, p, p is not None and p[1] in datei[code]["entitaeten"], key))

    vorschlag_von = {}      # (code, rolle, entitaet) -> element key of the Vorschlag
    for kz in konzepte:
        code = kz["code"]
        schluessel = sorted((k for k in zellen if k[0] == code),
                            key=lambda k: (ord_rolle.get(k[1], 999), k[1], ENTITAETEN.index(k[2])
                                           if k[2] in ENTITAETEN else 99))
        zl = []
        for zk in schluessel:
            ziel = zellen[zk]
            n = sum(z["n"] for z in ziel.values())
            els = _elemente_liste(ziel, n)
            top = els[0]
            forms_zelle = set().union(*[z["formulare"] for z in ziel.values()])
            c = {"rolle": zk[1], "entitaet": zk[2], "n": n, "n_formulare": len(forms_zelle),
                 "status": "kanton", "grund": None, "vorschlag": None, "elemente": els, "abweichend": [],
                 "n_abweichend": 0, "n_abweichend_formulare": 0}
            if n >= MINDESTENS and top["n"] * ANTEIL[1] >= n * ANTEIL[0]:
                vk = f"{top['standard']}:{top['element']}"
                vorschlag_von[zk] = vk
                abw = {}
                for fid, ps in punkte.items():
                    for _, _, c_, p_, drin, key in ps:
                        if drin and c_ == code and p_ == zk[1:] and key != vk:
                            abw.setdefault((fid, key), 0)
                            abw[(fid, key)] += 1
                c.update(status="vorschlag", vorschlag={"standard": top["standard"], "element": top["element"],
                                                        "n": top["n"], "anteil": top["anteil"]},
                         abweichend=[{"form_id": fid, "element": key, "n": m} for (fid, key), m in sorted(abw.items())])
                c["n_abweichend"] = sum(a["n"] for a in c["abweichend"])
                c["n_abweichend_formulare"] = len({a["form_id"] for a in c["abweichend"]})
            else:
                c["grund"] = "zu_wenige" if n < MINDESTENS else "keine_mehrheit"
            zl.append(c)
        kz["zellen"] = zl
        for name, quelle in (("ohne_rolle", ohne_rolle), ("andere_entitaet", andere), ("zuordnung_falsch", falsch)):
            q = quelle.get(code, {})
            n_q = sum(z["n"] for z in q.values())
            kz[name] = {"n": n_q, "elemente": _elemente_liste(q, n_q)}
        for a in kz["mitglieder"] + kz["ausserhalb"] + kz["gesperrt"]:
            b = benutzt.get((a["standard"], a["element"], a["context"]), [0, 0, set()])
            a["n"], a["n_zuordnung_falsch"], a["n_formulare"] = b[0], b[1], len(b[2])
        # every element in use that looks like a member and that the file does not judge
        k = datei[code]
        nb = [angabe(t, n=b[0], n_zuordnung_falsch=b[1], n_formulare=len(b[2]))
              for t, b in benutzt.items() if t not in beurteilt and
              (t[1] in k["namen"] or set(_begriffe_t(kat, t)) & set(k["begriffe"]))]
        kz["nicht_beurteilt"] = sorted(nb, key=lambda x: (-x["n"], x["standard"], x["element"], x["context"] or ""))
        kz["n_punkte"] = sum(c["n"] for c in zl) + kz["ohne_rolle"]["n"] + kz["andere_entitaet"]["n"]
        kz["n_formulare"] = len({fid for fid, ps in punkte.items() if any(p[2] == code for p in ps)})
        kz["n_zellen_vorschlag"] = sum(1 for c in zl if c["status"] == "vorschlag")
        kz["n_abweichend"] = sum(c["n_abweichend"] for c in zl)
        kz["n_abweichend_formulare"] = len({a["form_id"] for c in zl for a in c["abweichend"]})

    # per Formular: its points in the concepts and those that use another element than the Vorschlag
    for fm in forms:
        x = {"n_punkte": 0, "n_mit_vorschlag": 0, "n_vorschlag": 0, "n_abweichend": 0, "n_ohne_vorschlag": 0,
             "n_ohne_rolle": 0, "n_andere_entitaet": 0, "n_zuordnung_falsch": 0, "abweichungen": []}
        for did, teil, code, p, drin, key in punkte.get(fm["id"], []):
            x["n_punkte"] += 1
            if p is None:
                x["n_ohne_rolle"] += 1
            elif not drin:
                x["n_andere_entitaet"] += 1
            elif (code,) + p not in vorschlag_von:
                x["n_ohne_vorschlag"] += 1
            else:
                x["n_mit_vorschlag"] += 1
                vk = vorschlag_von[(code,) + p]
                if key == vk:
                    x["n_vorschlag"] += 1
                else:
                    x["abweichungen"].append({"feld": did, "teil": teil, "konzept": code, "rolle": p[0],
                                              "entitaet": p[1], "element": key, "vorschlag": vk})
        x["n_abweichend"] = len(x["abweichungen"])
        x["n_zuordnung_falsch"] = sum(1 for d, teil, u in _einheiten(fm)
                                      if (u.get("ech") or {}).get("id") in mitglied
                                      and u.get("ech_state") == "zuordnung_falsch")
        fm["konzepte"] = x

    zl_alle = [c for kz in konzepte for c in kz["zellen"]]
    summen = {
        "n_konzepte": len(konzepte),
        "n_mitglieder": sum(len(kz["mitglieder"]) for kz in konzepte),
        "n_gesperrt": sum(len(kz["gesperrt"]) for kz in konzepte),
        "n_ausserhalb": sum(len(kz["ausserhalb"]) for kz in konzepte),
        "n_nicht_beurteilt": sum(len(kz["nicht_beurteilt"]) for kz in konzepte),
        "n_punkte": sum(kz["n_punkte"] for kz in konzepte),
        "n_punkte_in_zellen": sum(c["n"] for c in zl_alle),
        "n_ohne_rolle": sum(kz["ohne_rolle"]["n"] for kz in konzepte),
        "n_andere_entitaet": sum(kz["andere_entitaet"]["n"] for kz in konzepte),
        "n_zuordnung_falsch": sum(kz["zuordnung_falsch"]["n"] for kz in konzepte),
        "n_formulare": sum(1 for fm in forms if fm["konzepte"]["n_punkte"]),
        "n_zellen": len(zl_alle),
        "n_zellen_vorschlag": sum(1 for c in zl_alle if c["status"] == "vorschlag"),
        "n_zellen_kanton": sum(1 for c in zl_alle if c["status"] == "kanton"),
        "n_zellen_kanton_keine_mehrheit": sum(1 for c in zl_alle if c["grund"] == "keine_mehrheit"),
        "n_zellen_kanton_zu_wenige": sum(1 for c in zl_alle if c["grund"] == "zu_wenige"),
        # cells without a Vorschlag whose points all use ONE element: no split practice, only few points
        "n_zellen_kanton_ein_element": sum(1 for c in zl_alle if c["status"] == "kanton" and len(c["elemente"]) == 1),
        "n_punkte_kanton_ein_element": sum(c["n"] for c in zl_alle if c["status"] == "kanton" and len(c["elemente"]) == 1),
        "n_punkte_in_vorschlag_zellen": sum(c["n"] for c in zl_alle if c["status"] == "vorschlag"),
        "n_punkte_in_kanton_zellen": sum(c["n"] for c in zl_alle if c["status"] == "kanton"),
        "n_punkte_vorschlag": sum(c["vorschlag"]["n"] for c in zl_alle if c["vorschlag"]),
        "n_abweichend": sum(c["n_abweichend"] for c in zl_alle),
        "n_abweichend_formulare": sum(1 for fm in forms if fm["konzepte"]["n_abweichend"]),
        "n_konzepte_mit_abweichung": sum(1 for kz in konzepte if kz["n_abweichend"]),
        "n_konzepte_uneinheitlich": sum(1 for kz in konzepte if any(len(c["elemente"]) > 1 for c in kz["zellen"])),
    }
    return {"regel": {"anteil_zaehler": ANTEIL[0], "anteil_nenner": ANTEIL[1], "mindestens": MINDESTENS,
                      "text": K["regel"]["text"]},          # the reviewed wording of the rule
            "stand": K.get("stand"), "pruefung": K.get("pruefung"),
            "labels": copy.deepcopy(LABELS), "ton": dict(TON), "konzepte": konzepte, "summen": summen}


# ---- invariants ---------------------------------------------------------------------------
def _db_einheiten(conn):
    """Every data point as the databank stores it: (data_field_id, teil key, form id,
    element id) — the Teilfelder of a field that has any, else the field."""
    teile = {}
    for did, name, eid in conn.execute("SELECT data_field_id, name, ech_element_id FROM data_subfield "
                                       "ORDER BY data_field_id, ord"):
        teile.setdefault(did, []).append((name, eid))
    out = []
    for did, fid, eid in conn.execute("SELECT id, form_id, ech_element_id FROM data_field"):
        for n, e in (teile.get(did) or [(None, eid)]):
            out.append((did, norm_ascii(n) if n is not None else "", fid, e))
    return out


def pruefen(conn, block=None, forms=None, K=None):
    """Invariants of the block against the curated file, the databank (the elements and
    the party of every counted point, read a second way) and the export's units.
    List of error texts; empty = valid."""
    K = K if K is not None else lade()
    f = datei_pruefen(K)
    if block is None or forms is None:
        return f + ["konzepte: pruefen() needs the block and the export's forms"]
    kat = katalog(conn)
    ord_rolle = {r[0]: r[1] for r in conn.execute("SELECT code, ord FROM partei_rolle")}
    datei = {k["code"]: k for k in K["konzepte"]}
    if [kz["code"] for kz in block["konzepte"]] != [k["code"] for k in K["konzepte"]]:
        f.append("konzepte: the concepts are not those of quellen/konzepte.json in its order")
    mitglied = {}
    for kz in block["konzepte"]:
        k = datei.get(kz["code"])
        wo = f"konzept {kz['code']}"
        if k is None:
            continue
        if kz["entitaeten"] != [x for x in ENTITAETEN if x in k["entitaeten"]]:
            f.append(f"{wo}: entitaeten are not those of the file")
        if {_triple(e) for e in k["elemente"]} != \
                {(m["standard"], m["element"], m["context"]) for m in kz["mitglieder"] + kz["gesperrt"]}:
            f.append(f"{wo}: members + blocked are not the elements the file lists")
        for m in kz["mitglieder"]:
            t = (m["standard"], m["element"], m["context"])
            if not m["element_ids"] or kat["nach_triple"].get(t) != m["element_ids"]:
                f.append(f"{wo}: member {m['standard']} {m['element']} does not name its catalogue elements")
                continue
            g = mitglied_pruefen(kat, k, t)
            if g:
                f.append(f"{wo}: member {m['standard']} {m['element']} fails the check «{g}»")
            for eid in m["element_ids"]:
                if eid in mitglied:
                    f.append(f"{wo}: element {eid} is also a member of {mitglied[eid]}")
                mitglied[eid] = kz["code"]
        for g in kz["gesperrt"]:
            if not mitglied_pruefen(kat, k, (g["standard"], g["element"], g["context"])):
                f.append(f"{wo}: {g['standard']} {g['element']} is blocked although it passes every check")
        for nb in kz["nicht_beurteilt"]:
            if any(i in mitglied for i in nb["element_ids"]):
                f.append(f"{wo}: «nicht beurteilt» {nb['standard']} {nb['element']} is a member")
        # cells: arithmetic and the rule
        reihe = [(ord_rolle.get(c["rolle"], 999), c["rolle"], ENTITAETEN.index(c["entitaet"])
                  if c["entitaet"] in ENTITAETEN else 99) for c in kz["zellen"]]
        if reihe != sorted(reihe) or len(set(reihe)) != len(reihe):
            f.append(f"{wo}: cells are not one per role and entity in the order of the role list")
        for c in kz["zellen"]:
            wc = f"{wo} / {c['rolle']} ({c['entitaet']})"
            if c["rolle"] not in ord_rolle or c["entitaet"] not in k["entitaeten"]:
                f.append(f"{wc}: no such role, or an entity the concept does not cover")
            n = sum(e["n"] for e in c["elemente"])
            if c["n"] != n or n == 0:
                f.append(f"{wc}: n {c['n']} is not the sum of its elements {n}")
            if [(-e["n"], -e["n_formulare"], e["standard"], e["element"]) for e in c["elemente"]] != \
                    sorted((-e["n"], -e["n_formulare"], e["standard"], e["element"]) for e in c["elemente"]):
                f.append(f"{wc}: elements not in their documented order")
            for e in c["elemente"]:
                if e["n_formulare"] != len(e["formulare"]) or e["formulare"] != sorted(set(e["formulare"])):
                    f.append(f"{wc}: n_formulare of {e['element']} does not count its Formulare")
                if e["anteil"] != (int(100 * e["n"] / n + 0.5) if n else 0):
                    f.append(f"{wc}: anteil of {e['element']} is not its share")
            top = c["elemente"][0] if c["elemente"] else {"n": 0, "standard": None, "element": None}
            soll = "vorschlag" if (n >= MINDESTENS and top["n"] * ANTEIL[1] >= n * ANTEIL[0]) else "kanton"
            if c["status"] != soll:
                f.append(f"{wc}: status {c['status']} but the rule gives {soll}")
            if soll == "vorschlag":
                v = c["vorschlag"] or {}
                if (v.get("standard"), v.get("element"), v.get("n")) != (top["standard"], top["element"], top["n"]):
                    f.append(f"{wc}: the Vorschlag is not the element with the most points")
                vk = f"{top['standard']}:{top['element']}"
                soll_abw = sorted((fid, f"{e['standard']}:{e['element']}") for e in c["elemente"][1:]
                                  for fid in e["formulare"])
                if soll_abw != sorted((a["form_id"], a["element"]) for a in c["abweichend"]) \
                        or any(a["element"] == vk for a in c["abweichend"]):
                    f.append(f"{wc}: abweichend are not the Formulare of the other elements")
                if c["n_abweichend"] != sum(a["n"] for a in c["abweichend"]) or c["n_abweichend"] != n - top["n"] \
                        or c["n_abweichend_formulare"] != len({a["form_id"] for a in c["abweichend"]}):
                    f.append(f"{wc}: n_abweichend {c['n_abweichend']} is not the points of the other elements")
            else:
                if c["vorschlag"] is not None or c["abweichend"] or c["n_abweichend"]:
                    f.append(f"{wc}: a cell without a Vorschlag lists one or deviations")
                if c["grund"] != ("zu_wenige" if n < MINDESTENS else "keine_mehrheit"):
                    f.append(f"{wc}: grund {c['grund']} does not fit")
        for name in ("ohne_rolle", "andere_entitaet", "zuordnung_falsch"):
            if kz[name]["n"] != sum(e["n"] for e in kz[name]["elemente"]):
                f.append(f"{wo}: {name}.n is not the sum of its elements")
        if kz["n_punkte"] != sum(c["n"] for c in kz["zellen"]) + kz["ohne_rolle"]["n"] + kz["andere_entitaet"]["n"]:
            f.append(f"{wo}: n_punkte is not the cells plus the points without a role or of another entity")
        if sum(m["n"] for m in kz["mitglieder"]) != kz["n_punkte"]:
            f.append(f"{wo}: the members' points {sum(m['n'] for m in kz['mitglieder'])} != n_punkte {kz['n_punkte']}")
        if sum(m["n_zuordnung_falsch"] for m in kz["mitglieder"]) != kz["zuordnung_falsch"]["n"]:
            f.append(f"{wo}: zuordnung_falsch is not the members' wrongly mapped points")

    # the databank, read a second way: every point with a member element, and its party
    db_n = {}
    for did, teil, fid, eid in _db_einheiten(conn):
        if eid in mitglied:
            db_n[mitglied[eid]] = db_n.get(mitglied[eid], 0) + 1
    for kz in block["konzepte"]:
        ist = kz["n_punkte"] + kz["zuordnung_falsch"]["n"]
        if db_n.get(kz["code"], 0) != ist:
            f.append(f"konzept {kz['code']}: the databank holds {db_n.get(kz['code'], 0)} points with a member "
                     f"element, the block counts {ist}")
    partei = {(r[0], r[1]): (r[2], r[3]) for r in conn.execute(
        "SELECT form_id, partei_nr, rolle, entitaet FROM formular_partei")}
    zuo = {(r[0], r[1]): r[2:] for r in conn.execute(
        "SELECT data_field_id, teil, teil_name, status, partei_nr FROM datenpunkt_partei")}
    zelle = {(kz["code"], c["rolle"], c["entitaet"]): c for kz in block["konzepte"] for c in kz["zellen"]}
    gezaehlt, je_form = {}, {}
    for fm in forms:
        for d, teil, u in _einheiten(fm):
            eid = (u.get("ech") or {}).get("id")
            if eid not in mitglied or u.get("ech_state") != "element":
                continue
            code = mitglied[eid]
            p = _partei(fm, u)
            a = zuo.get((d["id"], norm_ascii(teil) if teil is not None else ""))
            db_p = (partei.get((fm["id"], a[2])) if a and a[1] == "zugeordnet"
                    and a[0] == (teil if teil is not None else d["name"]) else None)
            if p != db_p:
                f.append(f"Formular {fm['id']} Datenfeld {d['id']} {teil or ''}: party {p} here, {db_p} in the databank")
            je_form[fm["id"]] = je_form.get(fm["id"], 0) + 1
            if p is not None and p[1] in datei[code]["entitaeten"]:
                gezaehlt.setdefault((code,) + p, {}).setdefault(_el_key(kat["el"][eid]), set()).add(fm["id"])
    if set(gezaehlt) != set(zelle):
        f.append("konzepte: the cells are not the roles and entities of the export's points")
    for k_, els in gezaehlt.items():
        c = zelle.get(k_)
        if c is not None and {f"{e['standard']}:{e['element']}": set(e["formulare"]) for e in c["elemente"]} != els:
            f.append(f"konzept {k_[0]} / {k_[1]} ({k_[2]}): the cell is not the export's points")
    # per Formular: the lists agree with the cells
    vorschlag = {(kz["code"], c["rolle"], c["entitaet"]): f"{c['vorschlag']['standard']}:{c['vorschlag']['element']}"
                 for kz in block["konzepte"] for c in kz["zellen"] if c["vorschlag"]}
    abw_zelle = {(a["form_id"], kz["code"], c["rolle"], c["entitaet"], a["element"]): a["n"]
                 for kz in block["konzepte"] for c in kz["zellen"] for a in c["abweichend"]}
    abw_form = {}
    for fm in forms:
        x = fm.get("konzepte")
        if not isinstance(x, dict):
            f.append(f"Formular {fm['id']}: konzepte missing")
            continue
        if x["n_punkte"] != je_form.get(fm["id"], 0) or x["n_punkte"] != (
                x["n_mit_vorschlag"] + x["n_ohne_vorschlag"] + x["n_ohne_rolle"] + x["n_andere_entitaet"]) \
                or x["n_mit_vorschlag"] != x["n_vorschlag"] + x["n_abweichend"] \
                or x["n_abweichend"] != len(x["abweichungen"]):
            f.append(f"Formular {fm['id']}: konzepte counts do not add up")
        for a in x["abweichungen"]:
            if vorschlag.get((a["konzept"], a["rolle"], a["entitaet"])) != a["vorschlag"] or a["element"] == a["vorschlag"]:
                f.append(f"Formular {fm['id']}: deviation {a['konzept']}/{a['rolle']} is not against the Vorschlag")
            k_ = (fm["id"], a["konzept"], a["rolle"], a["entitaet"], a["element"])
            abw_form[k_] = abw_form.get(k_, 0) + 1
    if abw_form != abw_zelle:
        f.append("konzepte: the deviations per Formular are not those of the cells")
    s = block["summen"]
    zl = [c for kz in block["konzepte"] for c in kz["zellen"]]
    soll = {"n_konzepte": len(block["konzepte"]), "n_zellen": len(zl),
            "n_zellen_vorschlag": sum(1 for c in zl if c["status"] == "vorschlag"),
            "n_punkte": sum(kz["n_punkte"] for kz in block["konzepte"]),
            "n_abweichend": sum(c["n_abweichend"] for c in zl),
            "n_abweichend_formulare": sum(1 for fm in forms if (fm.get("konzepte") or {}).get("n_abweichend")),
            "n_formulare": sum(1 for fm in forms if (fm.get("konzepte") or {}).get("n_punkte")),
            "n_zuordnung_falsch": sum(kz["zuordnung_falsch"]["n"] for kz in block["konzepte"])}
    for key, v in soll.items():
        if s.get(key) != v:
            f.append(f"konzepte.summen.{key} {s.get(key)} != {v}")
    if s.get("n_zellen") != s.get("n_zellen_vorschlag", 0) + s.get("n_zellen_kanton", 0) or \
            s.get("n_zellen_kanton") != s.get("n_zellen_kanton_zu_wenige", 0) + s.get("n_zellen_kanton_keine_mehrheit", 0):
        f.append("konzepte.summen: the cells by status do not add up")
    ein = [c for c in zl if c["status"] == "kanton" and len(c["elemente"]) == 1]
    if (s.get("n_zellen_kanton_ein_element"), s.get("n_punkte_kanton_ein_element")) != (len(ein), sum(c["n"] for c in ein)) \
            or len(ein) > s.get("n_zellen_kanton", 0):
        f.append("konzepte.summen: the cells without a Vorschlag that use one element are miscounted")
    if s.get("n_punkte") != s.get("n_punkte_in_zellen", 0) + s.get("n_ohne_rolle", 0) + s.get("n_andere_entitaet", 0) \
            or s.get("n_punkte_in_zellen") != s.get("n_punkte_in_vorschlag_zellen", 0) + s.get("n_punkte_in_kanton_zellen", 0) \
            or s.get("n_punkte_in_vorschlag_zellen") != s.get("n_punkte_vorschlag", 0) + s.get("n_abweichend", 0):
        f.append("konzepte.summen: the points do not add up")
    import labels as L
    if set((block.get("ton") or {}).values()) - set(L.TON) or set(block.get("ton") or {}) != {"vorschlag", "kanton"}:
        f.append("konzepte: ton is not one tone of labels.TON per status")
    texte = json.dumps([block.get("labels"), LABELS], ensure_ascii=False)
    if "ß" in texte:
        f.append("konzepte: a label uses «ß» (Swiss orthography: ss)")
    if re.search(r"\bRisik", texte):
        f.append("konzepte: a label uses a risk word (gaps are Lücken)")
    return f


# ---- self-test and command line --------------------------------------------------------------
def selbsttest(conn, forms):
    """Every invariant must fire on a tampered copy of today's block."""
    block = berechne(conn, forms)
    fehler = pruefen(conn, block, forms)
    assert not fehler, fehler[:3]
    kz = next(k for k in block["konzepte"] if any(c["abweichend"] for c in k["zellen"]))
    c = next(c for c in kz["zellen"] if c["abweichend"])
    ck = next((k["code"], x["rolle"], x["entitaet"]) for k in block["konzepte"] for x in k["zellen"]
              if x["status"] == "kanton")
    fid = c["abweichend"][0]["form_id"]

    def fall(fn):
        b, fs = copy.deepcopy(block), copy.deepcopy(forms)
        k2 = next(k for k in b["konzepte"] if k["code"] == kz["code"])
        c2 = next(x for x in k2["zellen"] if (x["rolle"], x["entitaet"]) == (c["rolle"], c["entitaet"]))
        ck2 = next(x for k in b["konzepte"] for x in k["zellen"] if (k["code"], x["rolle"], x["entitaet"]) == ck)
        fn(b, k2, c2, ck2, next(x for x in fs if x["id"] == fid))
        return pruefen(conn, b, fs)

    def einheit(fm):
        a = fm["konzepte"]["abweichungen"][0]
        return next(u for d, teil, u in _einheiten(fm) if d["id"] == a["feld"] and teil == a["teil"])

    def partei_weg(b, k, c, ck, fm):
        u = einheit(fm)
        u["partei"] = dict(u["partei"], status="unklar", nr=None)

    def entitaet_anders(b, k, c, ck, fm):
        nr = einheit(fm)["partei"]["nr"]
        for p in fm["parteien"]:
            if p["nr"] == nr:
                p["entitaet"] = "sache" if p["entitaet"] != "sache" else "organisation"

    faelle = {
        "n einer Zelle": lambda b, k, c, ck, fm: c.__setitem__("n", c["n"] + 1),
        "Status": lambda b, k, c, ck, fm: c.__setitem__("status", "kanton"),
        "Kanton mit Vorschlag": lambda b, k, c, ck, fm: ck.__setitem__("status", "vorschlag"),
        "Vorschlag falsch": lambda b, k, c, ck, fm: c["vorschlag"].__setitem__("element", "x"),
        "Abweichung fehlt": lambda b, k, c, ck, fm: c["abweichend"].pop(),
        "Anteil": lambda b, k, c, ck, fm: c["elemente"][0].__setitem__("anteil", 1),
        "Reihenfolge der Elemente": lambda b, k, c, ck, fm: c["elemente"].reverse(),
        "Entität der Zelle": lambda b, k, c, ck, fm: c.__setitem__("entitaet", "sache"),
        "Mitglied fehlt": lambda b, k, c, ck, fm: k["mitglieder"].pop(),
        "Summe": lambda b, k, c, ck, fm: b["summen"].__setitem__("n_abweichend", 0),
        "Formular-Liste": lambda b, k, c, ck, fm: fm["konzepte"]["abweichungen"].pop(),
        "Formular-Zahl": lambda b, k, c, ck, fm: fm["konzepte"].__setitem__("n_vorschlag", 0),
        "Partei einer Einheit": partei_weg,
        "Entität einer Partei": entitaet_anders,
        "Konzept-Reihenfolge": lambda b, k, c, ck, fm: b["konzepte"].reverse(),
        "ß": lambda b, k, c, ck, fm: b["labels"]["status"].__setitem__("kanton", "der Kanton legt fest, gemäß"),
        "Ton": lambda b, k, c, ck, fm: b["ton"].__setitem__("kanton", "gelb"),
    }
    stumm = [name for name, fn in faelle.items() if not fall(fn)]
    K = lade()
    datei_faelle = {
        "Element doppelt": lambda K: K["konzepte"][1]["elemente"].append(K["konzepte"][0]["elemente"][0]),
        "ohne Grund": lambda K: K["konzepte"][0].__setitem__("grund", ""),
        "Mitglied und ausserhalb": lambda K: K["konzepte"][0].setdefault("ausserhalb", []).append(
            {"element": K["konzepte"][0]["elemente"][0], "grund": "x"}),
        "Regel": lambda K: K["regel"].__setitem__("mindestens", 5),
        "Entität unbekannt": lambda K: K["konzepte"][0]["entitaeten"].append("tier"),
    }
    for name, fn in datei_faelle.items():
        k2 = copy.deepcopy(K)
        fn(k2)
        if not datei_pruefen(k2):
            stumm.append(name)
    n = len(faelle) + len(datei_faelle)
    print(f"Selbsttest: {n - len(stumm)} von {n} Manipulationen erkannt" + (f" — STUMM: {stumm}" if stumm else ""))
    return not stumm


def _export_forms(conn):
    """The export's Formulare with their units (export_json.build, in memory, nothing written)."""
    import contextlib
    import io
    import export_json
    with contextlib.redirect_stdout(io.StringIO()):
        data, _ = export_json.build(conn)
    return data["forms"]


def _el(e):
    return f"{e['standard']} {e['element']}"


def main():
    from common import DB_PATH, connect
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
