#!/usr/bin/env python3
"""Is the edition («Stand») the databank read each law from still the one in force?
Asks the official sources with read-only GETs and writes one dated row per law into
gesetz_stand_pruefung. It lists the laws whose current edition is newer than the one
read — it re-reads no article and changes no citation (a jurist decides whether the
cited wording changed).

Sources (one request per law, a pause of at least --pause seconds between requests,
gzip, a User-Agent that names the purpose, one retry after 10 s on a network error,
429 or 5xx):
  cantonal  https://rechtsbuch.sh.ch/api/de/texts_of_law/<SHR> — the interface
            fetch_rechtsbuch.py uses. The current version («Aktuelle Version in Kraft
            seit: …»), the older versions («Version in Kraft von: … bis: …», «wurde
            formlos berichtigt am: …») and the future versions are read from
            version_dates_str; abrogated marks a repealed law.
  federal   the Fedlex SPARQL endpoint https://fedlex.data.admin.ch/sparqlendpoint:
            the consolidated act (jolux:ConsolidationAbstract) classified under the SR
            number, its jolux:inForceStatus and its consolidations
            (jolux:dateApplicability = the «Stand am», jolux:publicationDate and whether
            a text exists, jolux:isRealizedBy). Fedlex also lists announced future
            consolidations that have an applicability date but no publication date and
            no text in any language: they are kept in details.versionen with
            «angekündigt, ohne veröffentlichten Text» and are never a «kuenftig»
            edition. The labels of the status vocabulary are read once per run.
  none      a law without an official number is not asked (ergebnis nicht_pruefbar).

Result per law (ergebnis), compared with gesetz_stand.stand (S) and the in-force date of
the current edition at the source (C), both calendar days:
  aktuell          S = C
  neuer_stand      S < C — n_neuere editions came into force after S (up to the day of
                   the check); a Stand older than the oldest version the Rechtsbuch keeps
                   still has C after it
  stand_unbekannt  S is not evidenced (gesetz_stand status unbekannt/widerspruch)
  aufgehoben       the source marks the law as repealed / no act under the SR number is
                   in force
  nicht_gefunden   the source does not know the number
  unklar           the answer cannot be compared (S after C, two acts in force under
                   one SR number, a current version without a date) — grund says which
  fehler           no usable answer (network, HTTP, JSON) — grund holds the error
  nicht_pruefbar   no official number
Editions already PUBLISHED with a later in-force date are listed in kuenftig; a version
with the same Stand that the Rechtsbuch corrected informally («formlos berichtigt») is
kept in details — the Stand is the same, the wording may differ editorially.

Idempotent: the row of a law and day is written only when it differs from the stored
one; a second run on the same day with the same answers prints «nichts zu tun» and
leaves citygov.db untouched. Writes go staging -> validate_db.validate() and
gesetz_stand.pruefen() -> swap. Needs gesetz_stand (scripts/gesetz_stand.py) to be
complete and current; stops otherwise.

    python3 scripts/check_gesetz_stand.py                     # every law, today
    python3 scripts/check_gesetz_stand.py --nur 120.100 831.10 # only these (law id, SHR or SR)
    python3 scripts/check_gesetz_stand.py --roh <dir>         # also keep every answer as a file
    python3 scripts/check_gesetz_stand.py --aus <dir>         # from kept answers, no network
                                                              # (rows dated as the answers were;
                                                              # a law without a number takes the
                                                              # day of the latest kept answer)
    python3 scripts/check_gesetz_stand.py --trocken           # ask and report, write nothing
    python3 scripts/check_gesetz_stand.py --liste             # the latest stored result per law
"""
import argparse
import datetime
import gzip
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
import gesetz_stand as GS

RECHTSBUCH = "https://rechtsbuch.sh.ch/api/de/texts_of_law/{}"
RECHTSBUCH_VERSION = "https://rechtsbuch.sh.ch/api/de/versions/{}/pdf_file"
FEDLEX = "https://fedlex.data.admin.ch/sparqlendpoint"
STATUS_IN_KRAFT = "https://fedlex.data.admin.ch/vocabulary/enforcement-status/0"
USER_AGENT = "citygov-gesetzesstand/1.0 (Kanton Schaffhausen, Datenbank der Formulare; nur lesende Abfragen)"
SPALTEN = ["law_id", "geprueft_am", "quelle", "abfrage", "ergebnis", "stand_gelesen", "fassung_gelesen",
           "stand_aktuell", "fassung_aktuell", "n_neuere", "kuenftig", "details", "grund"]
# the xhtml renderings of the law text are not needed for the edition and make up most of an answer
OHNE = ("xhtml_tol", "xhtml_cac_tol", "xhtml_cac_unified_tol")
_D = r"(\d{2}\.\d{2}\.\d{4})"

FEDLEX_ABFRAGE = """PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?cc ?status ?cons ?date ?end ?pub ?text WHERE {
 ?cc a jolux:ConsolidationAbstract ; jolux:classifiedByTaxonomyEntry ?e ; jolux:inForceStatus ?status .
 ?e skos:notation ?n . FILTER(str(?n) = "%s")
 OPTIONAL { ?cons jolux:isMemberOf ?cc ; jolux:dateApplicability ?date .
            OPTIONAL { ?cons jolux:dateEndApplicability ?end }
            OPTIONAL { ?cons jolux:publicationDate ?pub }
            BIND(EXISTS { ?cons jolux:isRealizedBy ?x } AS ?text) } }
ORDER BY ?cc ?date"""
ANGEKUENDIGT = "angekündigt, ohne veröffentlichten Text"
FEDLEX_STATUS = """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?s ?l WHERE { ?s skos:prefLabel ?l .
 FILTER(STRSTARTS(STR(?s), "https://fedlex.data.admin.ch/vocabulary/enforcement-status/")) FILTER(lang(?l) = "de") }"""


# ---- asking ----------------------------------------------------------------------------
class Abfrage:
    """Sequential read-only GETs with a pause between requests; optionally keeps every
    answer in a folder (--roh) or answers from such a folder without network (--aus)."""

    def __init__(self, pause, roh=None, aus=None):
        self.pause, self.roh, self.aus = pause, roh, aus
        self.letzte = 0.0
        self.n = 0

    def tag(self):
        """The day of this run: today, or with --aus the day of the latest kept answer
        (a law without a number is dated like the answers it was checked with)."""
        if not self.aus:
            return datetime.date.today().isoformat()
        tage = []
        for f in sorted(os.listdir(self.aus)):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(self.aus, f), encoding="utf-8") as fh:
                        a = json.load(fh).get("abgerufen")
                except (OSError, ValueError):
                    continue
                if a:
                    tage.append(a)
        return max(tage) if tage else datetime.date.today().isoformat()

    def _get(self, url, accept):
        warte = self.pause - (time.monotonic() - self.letzte)
        if warte > 0:
            time.sleep(warte)
        for versuch in (1, 2):
            req = urllib.request.Request(url, headers={"Accept": accept, "Accept-Encoding": "gzip",
                                                       "User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    roh = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        roh = gzip.decompress(roh)
                    self.letzte = time.monotonic(); self.n += 1
                    return r.status, roh, None
            except urllib.error.HTTPError as ex:
                self.letzte = time.monotonic(); self.n += 1
                if ex.code in (429, 500, 502, 503, 504) and versuch == 1:
                    time.sleep(10); continue
                return ex.code, None, f"HTTP {ex.code}"
            except (urllib.error.URLError, TimeoutError, OSError) as ex:
                self.letzte = time.monotonic(); self.n += 1
                if versuch == 1:
                    time.sleep(10); continue
                return None, None, f"{type(ex).__name__}: {ex}"
        return None, None, "keine Antwort"

    def holen(self, name, url, accept, umformen):
        """{url, abgerufen, http, antwort, fehler} for one question; `umformen(bytes)` turns the
        body into the JSON kept (it may raise ValueError: then fehler says so)."""
        pfad = os.path.join(self.aus or self.roh or "", name + ".json")
        if self.aus:
            if not os.path.isfile(pfad):
                return {"url": url, "abgerufen": None, "http": None, "antwort": None,
                        "fehler": f"keine aufbewahrte Antwort {name}.json"}
            with open(pfad, encoding="utf-8") as fh:
                return json.load(fh)
        code, body, fehler = self._get(url, accept)
        antwort = None
        if body is not None and code == 200:
            try:
                antwort = umformen(body)
            except ValueError as ex:
                fehler = f"Antwort nicht lesbar: {ex}"
        e = {"url": url, "abgerufen": datetime.date.today().isoformat(), "http": code,
             "antwort": antwort, "fehler": fehler}
        if self.roh:
            os.makedirs(self.roh, exist_ok=True)
            with open(pfad, "w", encoding="utf-8") as fh:
                json.dump(e, fh, ensure_ascii=False, indent=1, sort_keys=True)
        return e


def _rechtsbuch_json(body):
    d = json.loads(body)
    t = d.get("text_of_law") if isinstance(d, dict) else None
    if isinstance(t, dict) and isinstance(t.get("selected_version"), dict):
        for k in OHNE:
            t["selected_version"].pop(k, None)
    return d


def _sparql_json(body):
    d = json.loads(body)
    return [{k: v.get("value") for k, v in b.items()} for b in d["results"]["bindings"]]


def fedlex_url(abfrage):
    return FEDLEX + "?" + urllib.parse.urlencode({"query": abfrage})


# ---- reading the answers -----------------------------------------------------------------
def _version(v, art):
    s = (v or {}).get("version_dates_str") or ""
    def tag(muster):
        m = re.search(muster + r":\s*" + _D, s)
        return GS.iso_datum(m.group(1)) if m else None
    vid = (v or {}).get("id")
    return {"id": vid, "art": art, "in_kraft": tag(r"in Kraft (?:seit|von|ab)"), "bis": tag(r"bis"),
            "berichtigt_am": tag(r"formlos berichtigt am"), "beschluss": tag(r"Beschlussdatum"),
            "fassung": RECHTSBUCH_VERSION.format(vid) if isinstance(vid, int) else None, "roh": s}


def _ergebnis(gelesen, versionen, aktuell_tag, tag, fassung_aktuell):
    """The comparison shared by both sources: (ergebnis, n_neuere, fassung_gelesen, hinweis, grund)."""
    n = GS._anzahl_neuere({"versionen": versionen}, gelesen, tag) if gelesen else None
    gleiche = [v for v in versionen if v.get("in_kraft") == gelesen and v.get("in_kraft") and v["in_kraft"] <= tag]
    fassung_gelesen, hinweis = None, None
    if gelesen:
        if len({v["fassung"] for v in gleiche}) == 1:
            fassung_gelesen = gleiche[0]["fassung"]
        elif gleiche:
            hinweis = (f"{len(gleiche)} Fassungen mit demselben Stand: "
                       + "; ".join(f"{v['fassung']}" + (f" (formlos berichtigt am {v['berichtigt_am']})"
                                                        if v.get("berichtigt_am") else "") for v in gleiche))
        else:
            fruehste = min((v["in_kraft"] for v in versionen if v.get("in_kraft")), default=None)
            hinweis = ("keine Fassung mit diesem Stand in der Liste der Quelle"
                       + (f"; die älteste geführte gilt ab {fruehste}" if fruehste else ""))
    if not gelesen:
        return "stand_unbekannt", None, None, None, None
    if gelesen == aktuell_tag and n == 0:
        return "aktuell", n, fassung_gelesen, hinweis, None
    if gelesen < aktuell_tag:
        return "neuer_stand", n, fassung_gelesen, hinweis, None
    return ("unklar", n, fassung_gelesen, hinweis,
            f"gelesener Stand {gelesen} liegt nach dem aktuellen Stand {aktuell_tag} der Quelle"
            if gelesen > aktuell_tag else
            f"gelesener Stand {gelesen} ist der aktuelle, aber die Liste der Quelle führt {n} spätere Fassung(en)")


def rechtsbuch_auswerten(e, gelesen, tag):
    """Row fields from a kept Rechtsbuch answer."""
    if e.get("fehler") and e.get("http") != 404:
        return {"ergebnis": "fehler", "grund": f"Rechtsbuch: {e['fehler']}"}
    t = (e.get("antwort") or {}).get("text_of_law") if isinstance(e.get("antwort"), dict) else None
    if not isinstance(t, dict):
        return {"ergebnis": "nicht_gefunden", "grund": "Das Rechtsbuch führt diese SHR-Nummer nicht"
                + (f" ({e['fehler']})" if e.get("fehler") else " (Antwort ohne text_of_law)")}
    versionen = ([_version(t.get("current_version"), "aktuell")] if t.get("current_version") else []) \
        + [_version(v, "alt") for v in t.get("old_versions") or []] \
        + [_version(v, "kuenftig") for v in t.get("future_versions") or []]
    details = {"titel": t.get("title"), "erlass_in_kraft": t.get("enactment"),
               "publication_enactment": t.get("publication_enactment"),
               "aufgehoben": bool(t.get("abrogated")), "aufhebung": t.get("abrogated_dates_str"),
               "aufhebung_geplant": t.get("abrogated_scheduled_date_str") if t.get("abrogated_scheduled") else None,
               "adresse": t.get("canonical_link"), "versionen": versionen}
    kuenftig = [{"art": "fassung", "stand": v["in_kraft"], "fassung": v["fassung"]}
                for v in versionen if v["art"] == "kuenftig" and v.get("in_kraft") and v["in_kraft"] > tag]
    unlesbar = [v["roh"] for v in versionen if not v.get("in_kraft")]
    if unlesbar:
        details["unlesbar"] = unlesbar
    if t.get("abrogated_scheduled"):
        m = re.search(_D, t.get("abrogated_scheduled_date_str") or "")
        d = GS.iso_datum(m.group(1)) if m else None
        if d and d > tag:
            kuenftig.append({"art": "aufhebung", "stand": d, "fassung": None})
    out = {"details": details, "kuenftig": kuenftig}
    if t.get("abrogated"):
        return dict(out, ergebnis="aufgehoben",
                    grund=f"Das Rechtsbuch führt den Erlass als aufgehoben: {t.get('abrogated_dates_str') or 'ohne Datum'}")
    cv = versionen[0] if versionen and versionen[0]["art"] == "aktuell" else None
    if not cv or not cv["in_kraft"] or cv["in_kraft"] > tag:
        return dict(out, ergebnis="unklar",
                    grund="Die aktuelle Version nennt kein Datum «in Kraft seit» bis heute: "
                          + (cv["roh"] if cv else "keine current_version"))
    erg, n, fg, hinweis, grund = _ergebnis(gelesen, [v for v in versionen if v["art"] != "kuenftig"],
                                           cv["in_kraft"], tag, cv["fassung"])
    if hinweis:
        details["fassung_gelesen_hinweis"] = hinweis
    return dict(out, ergebnis=erg, stand_aktuell=cv["in_kraft"], fassung_aktuell=cv["fassung"],
                n_neuere=n, fassung_gelesen=fg, grund=grund)


def fedlex_auswerten(e, gelesen, tag, labels, eli_vermerk=None):
    """Row fields from a kept Fedlex answer."""
    if e.get("fehler") or not isinstance(e.get("antwort"), list):
        return {"ergebnis": "fehler", "grund": f"Fedlex: {e.get('fehler') or 'Antwort ohne Ergebniszeilen'}"}
    erlasse = {}
    neue_abfrage = any("text" in b for b in e["antwort"])     # kept answers before 2026-10-05 lack it
    for b in e["antwort"]:
        x = erlasse.setdefault(b["cc"], {"status": b.get("status"), "fassungen": {}})
        if b.get("cons") and b.get("date"):
            alt = x["fassungen"].get(b["cons"])
            pub = (b.get("pub") or "")[:10] or None
            if alt and alt[2] and (not pub or alt[2] < pub):
                pub = alt[2]                                   # several publication dates: the first
            text = str(b.get("text", "")).lower() in ("true", "1") or bool(alt and alt[3])
            x["fassungen"][b["cons"]] = (b["date"][:10], (b.get("end") or "")[:10] or None, pub, text)
    if not erlasse:
        return {"ergebnis": "nicht_gefunden", "grund": "Fedlex führt keinen konsolidierten Erlass unter dieser SR-Nummer"}
    details = {"erlasse": [{"eli": cc, "status": labels.get(x["status"], x["status"]), "n_fassungen": len(x["fassungen"])}
                           for cc, x in sorted(erlasse.items())]}
    if eli_vermerk:
        details["eli_vermerk"] = eli_vermerk
    in_kraft = sorted(cc for cc, x in erlasse.items() if x["status"] == STATUS_IN_KRAFT)
    if not in_kraft:
        return {"ergebnis": "aufgehoben", "details": details,
                "grund": "Fedlex: kein Erlass unter dieser SR-Nummer in Kraft ("
                         + "; ".join(f"{d['eli']}: {d['status']}" for d in details["erlasse"]) + ")"}
    if len(in_kraft) > 1:
        return {"ergebnis": "unklar", "details": details,
                "grund": "Fedlex führt mehrere Erlasse in Kraft unter dieser SR-Nummer: " + ", ".join(in_kraft)}
    cc = in_kraft[0]
    if eli_vermerk:
        details["eli_vermerk_passt"] = cc.endswith("/eli/" + eli_vermerk)
    versionen = []
    for cons, (d, bis, pub, text) in sorted(erlasse[cc]["fassungen"].items(), key=lambda kv: (kv[1][0], kv[0])):
        v = {"fassung": cons, "in_kraft": d, "bis": bis, "art": "kuenftig" if d > tag else "gilt_oder_galt"}
        if neue_abfrage:
            v["veroeffentlicht"], v["mit_text"] = pub, text
            if d > tag and not pub and not text:
                v["hinweis"] = ANGEKUENDIGT
        versionen.append(v)
    details["eli"], details["versionen"] = cc, versionen
    # a later edition is «kuenftig» only when it is published (a placeholder that has an
    # applicability date but no publication date and no text is announced, not published)
    kuenftig = [{"art": "fassung", "stand": v["in_kraft"], "fassung": v["fassung"]} for v in versionen
                if v["in_kraft"] > tag and (not neue_abfrage or v["veroeffentlicht"])]
    vergangen = [v for v in versionen if v["in_kraft"] <= tag]
    out = {"details": details, "kuenftig": kuenftig}
    if not vergangen:
        return dict(out, ergebnis="unklar", grund="Fedlex führt für den Erlass keine Fassung, die bis heute in Kraft trat")
    akt = max(vergangen, key=lambda v: (v["in_kraft"], v["fassung"]))
    erg, n, fg, hinweis, grund = _ergebnis(gelesen, vergangen, akt["in_kraft"], tag, akt["fassung"])
    if hinweis:
        details["fassung_gelesen_hinweis"] = hinweis
    return dict(out, ergebnis=erg, stand_aktuell=akt["in_kraft"], fassung_aktuell=akt["fassung"],
                n_neuere=n, fassung_gelesen=fg, grund=grund)


# ---- the run -----------------------------------------------------------------------------
def gesetze_waehlen(conn, nur):
    laws = conn.execute("SELECT id, title, short_title, jurisdiction_level, sr_number, cantonal_ref, source_note "
                        "FROM law ORDER BY id").fetchall()
    if not nur:
        return laws
    wahl = {x.replace("SHR", "").replace("SR", "").strip() for x in nur}
    return [l for l in laws if str(l["id"]) in wahl or (GS.nummer(l)[1] or "") in wahl]


def stand_lesen(conn):
    """{law_id: gesetz_stand row}; stops when the table is missing, incomplete or stale."""
    if not GS._has(conn, GS.TABELLE):
        sys.exit("ABBRUCH: Tabelle gesetz_stand fehlt — zuerst scripts/gesetz_stand.py ausführen.")
    rows = {r["law_id"]: r for r in conn.execute(f"SELECT * FROM {GS.TABELLE}")}
    fehlt = [r[0] for r in conn.execute("SELECT id FROM law ORDER BY id") if r[0] not in rows]
    zitiert = GS.zitierte_artikel(conn)
    alt = [i for i, r in rows.items() if r["basis"] != GS.fingerabdruck(conn, i, zitiert)]
    if fehlt or alt:
        sys.exit(f"ABBRUCH: gesetz_stand ist nicht aktuell ({len(fehlt)} Gesetze ohne Zeile, {len(alt)} Zeilen veraltet) "
                 "— zuerst scripts/gesetz_stand.py ausführen.")
    return rows


def pruefen_lauf(conn, laws, stand, abfrage):
    """{law_id: row dict} of today's (or the kept answers') check."""
    labels = {}
    if any(GS.nummer(l)[0] == "sr" for l in laws):
        e = abfrage.holen("fedlex_status", fedlex_url(FEDLEX_STATUS), "application/sparql-results+json", _sparql_json)
        labels = {b["s"]: b["l"] for b in (e.get("antwort") or [])}
    out = {}
    heute = abfrage.tag()
    for law in laws:
        art, nr = GS.nummer(law)
        gs = stand.get(law["id"])
        gelesen = gs["stand"] if gs else None
        if art is None:
            z = {"quelle": "keine", "abfrage": None, "ergebnis": "nicht_pruefbar", "geprueft_am": heute,
                 "grund": "kein Erlass mit amtlicher Nummer — es gibt nichts, wonach die Quellen gefragt werden könnten"}
        elif art == "shr":
            url = RECHTSBUCH.format(nr)
            e = abfrage.holen(f"rechtsbuch_{nr}", url, "application/json", _rechtsbuch_json)
            tag = e.get("abgerufen") or heute
            # the address actually asked (a kept answer keeps its own: replaying an older
            # answer reproduces its row)
            z = dict(rechtsbuch_auswerten(e, gelesen, tag), quelle="rechtsbuch", abfrage=e.get("url") or url,
                     geprueft_am=tag)
        else:
            url = fedlex_url(FEDLEX_ABFRAGE % nr)
            e = abfrage.holen(f"fedlex_{nr}", url, "application/sparql-results+json", _sparql_json)
            tag = e.get("abgerufen") or heute
            m = re.search(r"fedlex\.admin\.ch/eli/(cc/[^/\s]+/[^/\s]+)", law["source_note"] or "")
            z = dict(fedlex_auswerten(e, gelesen, tag, labels, m.group(1) if m else None),
                     quelle="fedlex", abfrage=e.get("url") or url, geprueft_am=tag)
        if z["ergebnis"] == "stand_unbekannt":
            z["grund"] = ("Der gelesene Stand ist nicht belegt (gesetz_stand: "
                          + (f"{gs['status']} — {gs['grund']}" if gs else "keine Zeile") + ")")
        row = {k: None for k in SPALTEN}
        row.update({k: v for k, v in z.items() if k in SPALTEN})
        row["law_id"], row["stand_gelesen"] = law["id"], gelesen
        row["kuenftig"] = json.dumps(sorted(z.get("kuenftig") or [], key=lambda k: (k["stand"], k["art"], k["fassung"] or "")),
                                     ensure_ascii=False, sort_keys=True)
        row["details"] = json.dumps(z.get("details") or {}, ensure_ascii=False, sort_keys=True)
        out[law["id"]] = row
        print(f"  {law['id']:>4} {(nr or '—'):<10} {row['ergebnis']:<16} gelesen {gelesen or '—'}"
              f"  aktuell {row['stand_aktuell'] or '—'}", flush=True)
    return out


def bericht(conn, neu):
    """Plain-German report: counts, the newer editions by citations, the rest with reasons."""
    zit = {r[0]: r[1:] for r in conn.execute(
        "SELECT a.law_id, COUNT(*), COUNT(DISTINCT d.data_field_id), COUNT(DISTINCT f.form_id) "
        "FROM data_field_legal_basis d JOIN article a ON a.id=d.article_id "
        "JOIN data_field f ON f.id=d.data_field_id GROUP BY a.law_id")}
    namen = {r[0]: (r[1] or r[2], r[3]) for r in conn.execute(
        "SELECT id, short_title, title, COALESCE(cantonal_ref, 'SR ' || sr_number) FROM law")}
    def zaehle(ids):
        c = {}
        for i in ids:
            c[neu[i]["ergebnis"]] = c.get(neu[i]["ergebnis"], 0) + 1
        return ", ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))
    alle = sorted(neu)
    zitiert = [i for i in alle if i in zit]
    print(f"Geprüft: {len(alle)} Gesetze — {zaehle(alle)}")
    print(f"  davon von Datenfeldern zitiert: {len(zitiert)} — {zaehle(zitiert)}")
    neuer = sorted((i for i in alle if neu[i]["ergebnis"] == "neuer_stand"),
                   key=lambda i: (-(zit.get(i, (0,))[0]), i))
    if neuer:
        print(f"Neuere Fassung in Kraft ({len(neuer)}), nach Zitaten geordnet:")
        for i in neuer:
            z = neu[i]; n = zit.get(i, (0, 0, 0))
            print(f"  {namen[i][1]:<12} {namen[i][0][:44]:<44} gelesen {z['stand_gelesen']} -> aktuell "
                  f"{z['stand_aktuell']} ({z['n_neuere']} neuere) | {n[0]} Zitate, {n[1]} Felder, {n[2]} Formulare")
    rest = [i for i in alle if neu[i]["ergebnis"] not in ("aktuell", "neuer_stand")]
    if rest:
        print(f"Nicht verglichen ({len(rest)}):")
        for i in rest:
            print(f"  {namen[i][1] or '—':<12} {namen[i][0][:44]:<44} {neu[i]['ergebnis']}: {neu[i]['grund']}")
    kuenftig = [i for i in alle if json.loads(neu[i]["kuenftig"])]
    if kuenftig:
        print(f"Bereits beschlossene spätere Fassungen oder Aufhebungen: {len(kuenftig)} Gesetze")
        for i in kuenftig:
            k = json.loads(neu[i]["kuenftig"])
            print(f"  {namen[i][1]:<12} {namen[i][0][:44]:<44} " + ", ".join(f"{x['art']} ab {x['stand']}" for x in k))
    ber = [i for i in alle if neu[i]["ergebnis"] == "aktuell"
           and "fassung_gelesen_hinweis" in json.loads(neu[i]["details"])]
    if ber:
        print(f"Aktuell, aber mehrere Fassungen mit demselben Stand (formlos berichtigt): {len(ber)} Gesetze")


def liste(conn):
    for r in conn.execute(f"SELECT p.*, l.short_title, l.title FROM {GS.PRUEFTABELLE} p JOIN law l ON l.id=p.law_id "
                          f"WHERE p.geprueft_am=(SELECT MAX(geprueft_am) FROM {GS.PRUEFTABELLE} q WHERE q.law_id=p.law_id) "
                          "ORDER BY p.ergebnis, p.law_id"):
        print(f"{r['law_id']:>4} {r['geprueft_am']} {r['ergebnis']:<16} {r['stand_gelesen'] or '—'} -> "
              f"{r['stand_aktuell'] or '—'}  {(r['short_title'] or r['title'])[:50]}")


def tabelle_sql():
    scratch = sqlite3.connect(":memory:")
    from common import SCHEMA_PATH
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        scratch.executescript(fh.read())
    row = scratch.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", [GS.PRUEFTABELLE]).fetchone()
    scratch.close()
    if not row:
        sys.exit(f"ABBRUCH: schema.sql kennt die Tabelle {GS.PRUEFTABELLE} nicht.")
    return row[0]


def main():
    ap = argparse.ArgumentParser(description="Gesetzesstand gegen Rechtsbuch und Fedlex prüfen (nur lesend).")
    ap.add_argument("--nur", nargs="+", metavar="GESETZ", help="nur diese Gesetze (law id, SHR oder SR)")
    ap.add_argument("--roh", metavar="ORDNER", help="jede Antwort zusätzlich als Datei aufbewahren")
    ap.add_argument("--aus", metavar="ORDNER", help="aufbewahrte Antworten statt Netz (Zeilen mit deren Datum)")
    ap.add_argument("--pause", type=float, default=1.5, help="Sekunden zwischen zwei Anfragen (mindestens 1)")
    ap.add_argument("--trocken", action="store_true", help="fragen und berichten, nichts schreiben")
    ap.add_argument("--liste", action="store_true", help="das letzte gespeicherte Ergebnis je Gesetz zeigen")
    args = ap.parse_args()
    if args.pause < 1.0:
        sys.exit("ABBRUCH: --pause unter einer Sekunde ist nicht höflich genug.")
    if not os.path.isfile(DB_PATH):
        sys.exit(f"ABBRUCH: keine Databank unter {DB_PATH}")
    conn = connect(DB_PATH)
    if args.liste:
        liste(conn); return
    stand = stand_lesen(conn)
    laws = gesetze_waehlen(conn, args.nur)
    if not laws:
        sys.exit("ABBRUCH: kein Gesetz ausgewählt.")
    abfrage = Abfrage(args.pause, roh=args.roh, aus=args.aus)
    print(f"Frage {len(laws)} Gesetze ab ({'aufbewahrte Antworten aus ' + args.aus if args.aus else 'Rechtsbuch und Fedlex, nur lesend'}):")
    neu = pruefen_lauf(conn, laws, stand, abfrage)
    if not args.aus:
        print(f"{abfrage.n} Anfragen gesendet")
    bericht(conn, neu)
    vorhanden = GS._has(conn, GS.PRUEFTABELLE)
    alt = {}
    if vorhanden:
        for r in conn.execute(f"SELECT * FROM {GS.PRUEFTABELLE}"):
            alt[(r["law_id"], r["geprueft_am"])] = {k: r[k] for k in SPALTEN}
    schreiben = [z for z in neu.values() if alt.get((z["law_id"], z["geprueft_am"])) != z]
    print(f"Zeilen: {len(schreiben)} neu oder geändert, {len(neu) - len(schreiben)} unverändert")
    conn.close()
    if args.trocken:
        print("--trocken: nichts geschrieben"); return
    if not schreiben:
        print("nichts zu tun — citygov.db bleibt unverändert"); return
    from validate_db import validate
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    if not vorhanden:
        c.execute(tabelle_sql())
    for z in sorted(schreiben, key=lambda z: (z["law_id"], z["geprueft_am"])):
        c.execute(f"INSERT OR REPLACE INTO {GS.PRUEFTABELLE} ({', '.join(SPALTEN)}) "
                  f"VALUES ({', '.join('?' * len(SPALTEN))})", [z[k] for k in SPALTEN])
    c.commit()
    errs = validate(c) + GS.pruefen(c)
    n = c.execute(f"SELECT COUNT(*) FROM {GS.PRUEFTABELLE}").fetchone()[0]
    c.close()
    if errs:
        os.remove(st)
        print("ABORT:", *errs[:8], sep="\n  ")
        sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"geschrieben: {GS.PRUEFTABELLE} hat jetzt {n} Zeilen")


if __name__ == "__main__":
    main()
