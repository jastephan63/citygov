#!/usr/bin/env python3
"""Export citygov.db -> data_export.json: the base data plus ONE computation of
every derived figure (Handlungsbedarf with tier and tone, Standard-Divergenzen,
Dienststellen summaries, kopfzahlen, Lebenslagen, Begriffe, labels, Datenstand)
that the dashboard, the guided flows, the dossiers, the landing page and the
machine-readable exports read. Heavy free-text columns (source_note, mapping
notes) stay in the DB for review; the one exception is the capped article
excerpt on data-field legal bases. The retired 2026-06 auto-draft layer
(form_field, field_mapping, requirement*, service_requirement) is not exported.

Also writes today's snapshot to verlauf.json (scripts/kennzahlen.py) and
logs/citation_todo.txt (every ingested article not at level 'verified').

Gates — when one fires, NOTHING is written (no data_export.json, no entry in
verlauf.json) and the script ends with one line «ABBRUCH …» and exit code 1:
  * a layer fails for another reason than a table this databank does not have
    (common._layer_skipped; the layer is named);
  * a published total is not the sum of its parts, or a figure computed in two
    places differs (_summen_pruefen; the figure is named);
  * the export would carry a local file path, or an unreviewed «Datum» in the
    databank's own naming/basis texts.

    python3 scripts/export_json.py
"""
import json, os, re, sqlite3, sys, unicodedata
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, EXPORT_PATH, LOGS_DIR, connect, assert_no_local_paths
from common import SKIPPED_LAYERS, _layer_skipped, dossier_slug, klartext as _klartext
import labels as LABELS


# «the same datum»: what may be compared across forms (Standard-Divergenzen)
# and across services (Lebenslagen). Same eCH element, same judged party for
# person/address data, same named role — conservative: when unsure, apart.
CONTAINER = {"document", "attachment", "comment"}
REG_STD = {"eCH-0044", "eCH-0010", "eCH-0011", "eCH-0007", "eCH-0008", "eCH-0046"}
PARTY = re.compile(r"ehe(gatt|partner|frau|mann)|partner|kind|tochter|sohn|vater|mutter|eltern|"
                   r"arbeitgeb|vertret|bevollm|verstorb|erblass|eigentüm|vermiet|mieter|pächter|"
                   r"verpächt|käufer|verkäufer|halter|begleit|zeug|gläubig|schuldn|bürge|"
                   r"teilhaber|gesellschafter|geschäftsführ|kontaktperson|ansprechperson", re.I)


def datum_key(d, u, subs):
    """(standard, element, party, role, party-words) for a unit, or None when the
    unit must not be compared: no element, a container element, a naming
    verdict that says the element is wrong, or an unjudged party on
    person/address data."""
    e = u.get("ech") or {}
    if not e.get("element") or e["element"] in CONTAINER:
        return None
    b = u.get("begriff") or {}
    if b.get("pruefart") == "zuordnung":
        return None
    reg_std = e["standard"] in REG_STD
    if reg_std and d.get("subjekt") in (None, "gemischt"):
        return None
    lab = u.get("name") if subs else d["name"]
    role = ((b.get("rolle") or "").strip().lower()) if b.get("klasse") == "rolle" else ""
    ctx = d["name"] if subs else lab
    party = "|".join(sorted({m.group(0).lower() for m in PARTY.finditer(ctx or "")}))
    return (e["standard"], e["element"], d.get("subjekt") if reg_std else "", role, party)


def rows(conn, q, *a):
    return [dict(r) for r in conn.execute(q, a).fetchall()]


def _tsd(n):
    """1234 -> «1'234» (de-CH), for a number inside a sentence."""
    return f"{int(n):,}".replace(",", "'")


def _sortierwort(t):
    """Sort key of a title as a German reader expects it: case and accents do not
    count (ä next to a, ß as ss); punctuation stays, so a space sorts first."""
    t = unicodedata.normalize("NFD", (t or "").lower().replace("ß", "ss"))
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def handlungsbedarf(fm, today):
    """Open points of one form as [{cat, n, detail}] — cat is a key of
    labels.TODO_CATS. Mirrors what the dashboard used to compute in the browser,
    so the board, the service page, the dossier and the CSV agree by construction."""
    dfs = fm.get("data_fields") or []
    it = []
    if not dfs:
        it.append({"cat": "keine-felder", "n": 1, "detail": "keine Datenfelder modelliert"})
        return it
    # the legal question of a field is answered once (basis_state, _basis_state)
    nE = sum(1 for d in dfs if d["basis_state"] == "zu_ermitteln")
    if nE:
        it.append({"cat": "ermitteln", "n": nE, "detail": LABELS.pl(nE, "Feld", "Felder") + " ohne recherchierte Grundlage"})
    nO = [d["name"] for d in dfs if d["basis_state"] == "offen"]
    if nO:
        it.append({"cat": "offen", "n": len(nO), "detail": " · ".join(nO)})
    nX = [d["name"] for d in dfs if d["basis_state"] == "ohne"]
    if nX:
        it.append({"cat": "ohne", "n": len(nX), "detail": " · ".join(nX)})
    a5 = [d["name"] for d in dfs if d["basis_state"] == "art5_offen"]
    if a5:
        it.append({"cat": "sensibel_art5", "n": len(a5), "detail": " · ".join(a5)})
    if not fm.get("purpose"):
        it.append({"cat": "zweck", "n": 1, "detail": "Zweck fehlt im Verzeichnis"})
    if not fm.get("disclosures"):
        it.append({"cat": "empf", "n": 1, "detail": "keine belegte Bekanntgabe erfasst"})
    sens = sum(1 for d in dfs if d.get("sensitive"))
    dsfa_ind = bool(sens >= 3 or (len(dfs) and sens / len(dfs) >= 0.5 and sens >= 1))
    fm["dsfa_indiziert"] = dsfa_ind        # the ONE triage judgment the surfaces read
    if dsfa_ind and not fm.get("dsfa_status"):
        it.append({"cat": "dsfa", "n": 1, "detail": f"{sens} von {len(dfs)} Feldern besonders schützenswert"})
    # eCH-Zuordnung offen: counted on the atomic unit from the stamped state, like every
    # other standard figure (ungeprueft = never checked; element_offen = a standard with an
    # element catalogue is assigned, the element is not — only there is an element «owed»)
    eN = sum(1 for d in dfs for u in _units(d) if u["ech_state"] == "ungeprueft")
    eS = sum(1 for d in dfs for u in _units(d) if u["ech_state"] == "element_offen")
    if eN + eS:
        it.append({"cat": "ech", "n": eN + eS,
                   "detail": ", ".join(x for x in (f"{eN} nicht geprüft" if eN else "", f"{eS} Element offen" if eS else "") if x)})
    # data points on a standard no longer in force (the same unit as every standard figure)
    alt = []
    for d in dfs:
        for u in _units(d):
            if u["ech_state"] == "standard_alt":
                alt.append(u.get("name") or d["name"])
    if alt:
        it.append({"cat": "echalt", "n": len(alt), "detail": " · ".join(alt)})
    chk = fm.get("check")
    if chk and chk.get("status") in LABELS.CHECK and chk["status"] != "aktuell":
        it.append({"cat": "veraltet", "n": 1, "detail": LABELS.CHECK[chk["status"]] + (" — " + chk["note"] if chk.get("note") else "")})
    due = fm.get("next_check_due")
    if not chk:
        it.append({"cat": "pruefung_faellig", "n": 1, "detail": "Online-Fassung noch nie geprüft"})
    elif due and due < today:
        it.append({"cat": "pruefung_faellig", "n": 1, "detail": f"Wiedervorlage überfällig seit {LABELS.fmt_date(due)} (letzte Prüfung {LABELS.fmt_date(chk.get('d')) or '?'})"})
    # a pair appears on both forms; count it on the lower id only, so the board
    # total is the number of open DECISIONS, not twice that
    du = [s_ for s_ in (fm.get("similar") or []) if not s_.get("verdict") and fm["id"] < s_["form_id"]]
    if du:
        it.append({"cat": "dup", "n": len(du),
                   "detail": " · ".join(f"{s_['titel']} ({round(s_['jaccard'] * 100)} % gleiche Felder)" for s_ in du)})
    sd = fm.get("standard_divergenzen")
    # data points without a standard in force for them: the canton decides (eSH or an eCH request)
    ks = ke = 0
    for d in dfs:
        for u in _units(d):
            stt = u["ech_state"]
            if stt in ("kein_standard", "standard_entwurf"):
                ks += 1
                ke += bool(u.get("esh"))
    if ks:
        it.append({"cat": "kein_standard", "n": ks,
                   "detail": LABELS.pl(ks, "Datenpunkt", "Datenpunkte") + " ohne geltenden eCH-Standard"
                             + (f", davon {ke} mit eSH-Entwurf" if ke else "")})
    if sd:
        ang = [i for i in sd.get("angleichen") or [] if i["art"] != "pflicht_uneinheitlich"]
        unk = [i for i in sd.get("angleichen") or [] if i["art"] == "pflicht_uneinheitlich"]
        if ang:
            it.append({"cat": "divergenz", "n": len({(i["feld"], i.get("teilfeld")) for i in ang}),
                       "detail": " · ".join(f"{i['feld']}{' › ' + i['teilfeld'] if i.get('teilfeld') else ''} "
                                            f"({LABELS.DIV.get(i['art'], i['art'])}: hier {i['hier']}, sonst {i['andere']})" for i in ang)})
        bz = sd.get("bezeichnungen") or []
        bzF = [i for i in bz if i.get("klasse") == "variante" or i.get("pruefart") == "aufteilen"]
        bzZ = [i for i in bz if i.get("klasse") == "pruefen" and i.get("pruefart") != "aufteilen"]
        if bzF:
            it.append({"cat": "begriff", "n": len(bzF),
                       "detail": " · ".join(f"«{i['hier']}»" + (f" → «{i['vorschlag']}»" if i.get("klasse") == "variante" else " (aufteilen)") for i in bzF)})
        if bzZ:
            it.append({"cat": "zuordnung", "n": len(bzZ),
                       "detail": " · ".join(f"«{i['hier']}» ≠ {i['standard']} {i['element']}" for i in bzZ)})
        # a point that differs from the practice counts there; «corpus split» keeps the rest
        ang_u = {(i["feld"], i.get("teilfeld")) for i in ang}
        unk = [i for i in unk if (i["feld"], i.get("teilfeld")) not in ang_u]
        if unk:
            it.append({"cat": "divergenz_offen", "n": len({(i["feld"], i.get("teilfeld")) for i in unk}),
                       "detail": " · ".join(f"{i['feld']}{' › ' + i['teilfeld'] if i.get('teilfeld') else ''} — {i['andere']}" for i in unk)})
    o = fm.get("outcome") or {}
    stt = o.get("rechtsmittel_status")
    ea_txt = LABELS.OUTCOME.get(o.get("entscheid_art"), o.get("entscheid_art") or "")
    if stt in ("beurteilt_offen", "nicht_beurteilt"):
        it.append({"cat": "rechtsmittel", "n": 1,
                   "detail": ea_txt + (" — " + o["rechtsmittel_verdikt"] if o.get("rechtsmittel_verdikt") else
                                       (" — noch nicht geprüft" if stt == "nicht_beurteilt" else ""))})
    elif stt == "default_allgemein":
        it.append({"cat": "rechtsmittel_default", "n": 1, "detail": ea_txt + " — allgemeine VRG-Regel ohne Prüfvermerk"})
    elif stt == "entscheidart_offen":
        it.append({"cat": "entscheid_art", "n": 1, "detail": "Ergebnis des Verfahrens aus dem DVSH-Text nicht belegbar"})
    return it


# the remedy notes are the review's reasoning; readers get it without the review's
# internal vocabulary. Substance is untouched; a truncated second opinion (the
# loader capped notes at 400 characters) is dropped rather than shown cut off.
_PV_WORDS = [
    ("Zweitprüfung: die zugeordnete Norm wurde in der Zweitprüfung gestrichen — ", "Die zunächst zugeordnete Norm trägt nicht — "),
    ("nicht unter den Kandidaten ist – aus dem Material nicht entscheidbar", "nicht unter den geprüften Normen ist — aus den ausgewerteten Rechtsgrundlagen nicht entscheidbar"),
    ("lässt sich aus den Kandidaten nicht entscheiden", "lässt sich aus den geprüften Normen nicht entscheiden"),
    ("fehlt im Material", "ist unter den ausgewerteten Rechtsgrundlagen nicht vorhanden"),
    ("ist im Material nicht erfasst", "ist in den ausgewerteten Rechtsgrundlagen nicht erfasst"),
    ("von keiner Kandidatenbestimmung erfasst", "von keiner der geprüften Normen erfasst"),
    ("fehlt unter den Kandidaten", "fehlt unter den geprüften Normen"),
    ("Kein Kandidat erfasst", "Keine der geprüften Normen erfasst"),
    ("von keinem Kandidaten erfasst", "von keiner der geprüften Normen erfasst"),
    ("die hier nicht als Kandidaten vorliegen", "die hier nicht unter den geprüften Normen sind"),
    ("Einziger Kandidat Art. 32b TSchG betrifft", "Die einzige geprüfte Norm, Art. 32b TSchG, betrifft"),
    (", weshalb 'offen' nicht zutrifft", ""),
]




def _lesbar_pruefvermerk(t):
    t = (t or "").strip()
    uneinig = t.startswith("Zweitprüfung uneinig: ")
    if uneinig:
        t = t[len("Zweitprüfung uneinig: "):]
        parts = [x.strip() for x in t.split(" / ")]
        if len(parts) > 1 and not re.search(r"[.!?)»]$", parts[-1]):
            parts = parts[:-1]                      # cut off at load time — never show a fragment
        t = " / ".join(parts)
    elif t.startswith("Zweitprüfung: ") and not t.startswith("Zweitprüfung: die zugeordnete Norm"):
        t = t[len("Zweitprüfung: "):]
    for a, b in _PV_WORDS:
        t = t.replace(a, b)
    t = re.sub(r"\s*\(Regel \d+[^)]*\)", "", t)
    if uneinig:
        t = "Die Prüfungen sind uneinig. Eine Prüfung hält fest: " + t
    left = [w for w in ("Kandidat", "Zweitprüfung", "im Material") if w in t] + re.findall(r"Regel \d+", t)
    if left:
        raise RuntimeError(f"Prüfvermerk mit interner Wortwahl ({left}): {t[:120]}")
    return t


def _dst_slug(name):
    from common import norm_ascii
    return norm_ascii(name).replace(" ", "-") or "ohne-dienststelle"


def _units(d):
    """The atomic data points of a Datenfeld — the unit of every data-standard
    figure: its Teilfelder, or the field itself when it has none."""
    subs = [x for x in (d.get("subfields") or []) if isinstance(x, dict)]
    return subs or [d]


def _ech_state(u):
    """The eCH state of one Datenfeld or Teilfeld — a key of labels.TON_MAP['ech'].
    The ONE classification: _zustaende_setzen() writes it on every field and
    Teilfeld as `ech_state`, the figures below count that key, and the pages read
    it instead of asking these questions again."""
    e = u.get("ech") or {}
    if e.get("element") and (u.get("begriff") or {}).get("pruefart") == "zuordnung":
        # an element is assigned, but the naming layer found the label means another
        # datum: the databank corrects its own mapping (grey) — never counted as settled
        return "zuordnung_falsch"
    if e.get("element"):
        return "element"
    if e.get("standard") and e.get("status") == "In Arbeit":
        return "standard_entwurf"
    if e.get("standard") and e.get("status") in ("Sistiert", "Aufgehoben", "Abgelöst"):
        return "standard_alt"
    if e.get("standard") and not e.get("n_elements"):
        return "standard_ohne_elemente"
    if e.get("standard"):
        return "element_offen"
    if u.get("ech_status") == "kein_standard":
        return "kein_standard"
    return "ungeprueft"


def _basis_state(d):
    """The answer to the legal question of one Datenfeld — a key of
    labels.TON_MAP['basis']: «artikel» (an article is cited), «art5_offen» (a
    besonders schützenswerte Angabe judged task-necessary, its basis under KDSG
    Art. 5 Abs. 1 not yet named — open, never covered), «aufgabe», «ohne», «offen»
    (the panel's verdict) or «zu_ermitteln» (not researched; also a verdict
    «artikel» without a citation). Written on every field as `basis_state`."""
    if d.get("legal_basis"):
        return "artikel"
    if d.get("art5_offen"):
        return "art5_offen"
    return d["basis_typ"] if d.get("basis_typ") in ("aufgabe", "ohne", "offen") else "zu_ermitteln"


def _zustaende_setzen(forms):
    """Stamp the two classifications on the units the pages draw: `ech_state` on every
    Datenfeld and every Teilfeld, `basis_state` on every Datenfeld. For a field with
    Teilfelder, ech_state describes the field's OWN mapping (its chip); the figures
    count its Teilfelder (_units). Runs after the Begriffe layer, whose verdict
    «zuordnung» decides between element and zuordnung_falsch."""
    for fm in forms:
        for d in fm.get("data_fields") or []:
            d["ech_state"] = _ech_state(d)
            d["basis_state"] = _basis_state(d)
            for u in d.get("subfields") or []:
                if isinstance(u, dict):
                    u["ech_state"] = _ech_state(u)


def _ech_ton(ech):
    """eCH states {state: n} as the four parts a bar draws, by who acts next
    (labels.TON_MAP['ech']): ok = with an eCH element, ok2 = settled at standard
    level (the standard has no element catalogue; light green), dec = the canton
    decides, open = the databank maps or corrects (zuordnung_falsch included).
    The parts sum to the number of data points."""
    t = {"ok": 0, "ok2": 0, "dec": 0, "open": 0}
    for st, n in ech.items():
        t["ok2" if st == "standard_ohne_elemente" else LABELS.TON_MAP["ech"][st]] += n
    return t


def _standard_zahlen(fms):
    """Data-standard figures of a set of forms: atomic points, their eCH state, how
    many are demanded differently than elsewhere, how many labels to align."""
    z = {"punkte": 0, "ech": {}, "div_punkte": 0, "div_offen": 0, "begriff_felder": 0, "formulare_div": 0}
    for fm in fms:
        for d in fm.get("data_fields") or []:
            for u in _units(d):
                z["punkte"] += 1
                st = u["ech_state"]
                z["ech"][st] = z["ech"].get(st, 0) + 1
        sd = fm.get("standard_divergenzen") or {}
        ang = sd.get("angleichen") or []
        # distinct data points, not items: one point can differ in requiredness AND format
        act_u = {(i["feld"], i.get("teilfeld")) for i in ang if i["art"] != "pflicht_uneinheitlich"}
        dec_u = {(i["feld"], i.get("teilfeld")) for i in ang if i["art"] == "pflicht_uneinheitlich"} - act_u
        z["div_punkte"] += len(act_u)
        z["div_offen"] += len(dec_u)
        z["formulare_div"] += bool(any(i["art"] != "pflicht_uneinheitlich" for i in ang))
        z["begriff_felder"] += sum(1 for i in (sd.get("bezeichnungen") or [])
                                   if i.get("klasse") == "variante" or i.get("pruefart") == "aufteilen")
    # «with an eCH element» = every point with an assigned element, including the
    # ones whose mapping the databank itself flags for correction (shown apart)
    z["mit_element"] = z["ech"].get("element", 0) + z["ech"].get("zuordnung_falsch", 0)
    z["ech_ton"] = _ech_ton(z["ech"])
    return z


def _rechtsgrundlage_zahlen(forms):
    """Legal basis per Datenfeld, counted on basis_state: wert = covered (an article,
    or the task — green), teile by who acts next (labels.TON_MAP['basis']), and the
    open kinds by name. teile sum to von by construction: each field has one state."""
    n = {}
    for fm in forms:
        for d in fm.get("data_fields") or []:
            n[d["basis_state"]] = n.get(d["basis_state"], 0) + 1
    teile = {"ok": 0, "act": 0, "dec": 0, "open": 0}
    for k, v in n.items():
        teile[LABELS.TON_MAP["basis"][k]] += v
    return {"wert": teile["ok"], "von": sum(n.values()), "teile": teile,
            "ohne": n.get("ohne", 0), "offen": n.get("offen", 0),
            "zu_ermitteln": n.get("zu_ermitteln", 0), "art5_offen": n.get("art5_offen", 0)}


def _verzeichnis_zahlen(forms):
    """Register entries per Formular with data fields, each form in exactly one part:
    open = purpose or recipients not recorded (the databank's research — categories
    «zweck» and «empf»), ok = purpose, evidenced recipients and an own retention term
    (Spezialfrist or Fristentscheid), rest = only the own term is missing (the
    standard term applies; no open point)."""
    t = {"ok": 0, "open": 0, "rest": 0}
    for fm in forms:
        if not fm.get("data_fields"):
            continue
        if not fm.get("purpose") or not fm.get("disclosures"):
            t["open"] += 1
        elif fm.get("retention") or fm.get("retention_decisions"):
            t["ok"] += 1
        else:
            t["rest"] += 1
    return {"wert": t["ok"], "von": sum(t.values()), "teile": t}


def _benannt_zahlen(forms, von):
    """Naming verdicts on the Datenpunkte that carry an eCH element (`von`), from
    standard_divergenzen.bezeichnungen — one verdict per Datenpunkt. teile, keyed
    like labels.TON_MAP['begriff']: variante = rename to the uniform term, aufteilen =
    split a field that bundles data the standard separates (both: category «begriff»,
    the Dienststelle acts), zuordnung = the label means another datum than the
    element (category «zuordnung», the databank corrects its mapping), rest = no
    deviation recorded. formulare_*: how many forms carry such a point."""
    t = {"variante": 0, "aufteilen": 0, "zuordnung": 0}
    fs = {k: set() for k in t}
    for fm in forms:
        for i in (fm.get("standard_divergenzen") or {}).get("bezeichnungen") or []:
            k = ("variante" if i.get("klasse") == "variante"
                 else "aufteilen" if i.get("pruefart") == "aufteilen" else "zuordnung")
            t[k] += 1
            fs[k].add(fm["id"])
    t["rest"] = von - sum(t.values())
    return {"von": von, "teile": t, "formulare_begriff": len(fs["variante"] | fs["aufteilen"]),
            "formulare_teile": {k: len(v) for k, v in fs.items()}}


def _kein_standard_zahlen(forms):
    """The amber part of the data standard — Datenpunkte without an eCH standard in
    force (ech_state kein_standard or standard_entwurf; category «kein_standard») —
    by the decision the canton faces: esh = a cantonal eSH draft exists, ohne =
    neither an eCH standard nor an eSH draft, ech_entwurf = an eCH standard still
    in the works. formulare: forms concerned; codes: Datenpunkte per eSH draft and
    per eCH standard in the works."""
    t = {"esh": 0, "ohne": 0, "ech_entwurf": 0}
    fs = {k: set() for k in t}
    codes = {"esh": {}, "ech_entwurf": {}}
    for fm in forms:
        for d in fm.get("data_fields") or []:
            for u in _units(d):
                if u["ech_state"] == "kein_standard":
                    k, code = ("esh", u["esh"]["code"]) if u.get("esh") else ("ohne", None)
                elif u["ech_state"] == "standard_entwurf":
                    k, code = "ech_entwurf", u["ech"]["standard"]
                else:
                    continue
                t[k] += 1
                fs[k].add(fm["id"])
                if code:
                    codes[k][code] = codes[k].get(code, 0) + 1
    return {"von": sum(t.values()), "teile": t, "formulare": {k: len(v) for k, v in fs.items()},
            "codes": {k: dict(sorted(v.items())) for k, v in codes.items()}}


def _kategorien(forms):
    """Open points per category (labels.CAT_ORDER; every category, also with 0): n =
    points over all forms (what n counts: labels.EINHEIT), formulare = forms
    concerned. A duplicate pair is counted on one of its two forms; «formulare»
    of «dup» names both."""
    known = {fm["id"] for fm in forms}
    k = {c: {"n": 0, "formulare": set()} for c in LABELS.CAT_ORDER}
    for fm in forms:
        for it in fm.get("handlungsbedarf") or []:
            c = k[it["cat"]]
            c["n"] += it["n"]
            c["formulare"].add(fm["id"])
            if it["cat"] == "dup":
                c["formulare"].update(s_["form_id"] for s_ in fm.get("similar") or []
                                      if not s_.get("verdict") and fm["id"] < s_["form_id"] and s_["form_id"] in known)
    return {c: {"n": v["n"], "formulare": len(v["formulare"])} for c, v in k.items()}


def _massnahmen(fms):
    """What a Dienststelle can do itself: one entry per red category, summed over its
    forms, in priority order (tier, then labels.CAT_ORDER). gross = the three
    largest forms (by points, then title); mix (only «divergenz») = the kinds of
    divergence, counted per entry of standard_divergenzen.angleichen (one Datenpunkt
    can have several); aktion = the imperative of labels.AKTION — for divergences in
    value lists only, the wording that nothing on the form has to change."""
    order = {c: i for i, c in enumerate(LABELS.CAT_ORDER)}
    G = {}
    for fm in fms:
        for it in fm.get("handlungsbedarf") or []:
            if it["ton"] != "act":
                continue
            g = G.setdefault(it["cat"], {"cat": it["cat"], "stufe": it["stufe"], "n": 0, "forms": [], "mix": {}})
            g["n"] += it["n"]
            g["forms"].append((it["n"], fm))
            if it["cat"] == "divergenz":
                for x in (fm.get("standard_divergenzen") or {}).get("angleichen") or []:
                    if x["art"] in ("pflicht", "format", "codeliste"):
                        g["mix"][x["art"]] = g["mix"].get(x["art"], 0) + 1
    out = []
    for g in sorted(G.values(), key=lambda g: (g["stufe"], order.get(g["cat"], 99))):
        fl = sorted(g["forms"], key=lambda nf: (-nf[0], _sortierwort(nf[1].get("title")), nf[1]["id"]))
        nur_codes = g["cat"] == "divergenz" and g["mix"].get("codeliste") and not (g["mix"].get("pflicht") or g["mix"].get("format"))
        m = {"cat": g["cat"], "stufe": g["stufe"], "n": g["n"], "formulare": len(fl),
             "gross": [{"form_id": fm["id"], "n": n} for n, fm in fl[:3]],
             "aktion": (LABELS.AKTION["divergenz_codeliste"] if nur_codes
                        else LABELS.AKTION.get(g["cat"]) or LABELS.TODO_BY[g["cat"]][1])}
        if g["cat"] == "divergenz":
            m["mix"] = g["mix"]
        out.append(m)
    return out


# verlauf.json with today's entry, as uebersichten() prepared it. main() writes it
# only after every gate has passed — an aborted export records no figures.
VERLAUF_DOC = None


def uebersichten(conn, services, forms, dienststellen, begriffe_stats):
    """Per Dienststelle: services, forms, open points by tone and tier, the most
    important actions and the data-standard figures; the headline figures of the
    home page (data standard first); and the trend (verlauf.json with today's
    snapshot — prepared here, written by main())."""
    global VERLAUF_DOC
    import kennzahlen as KZ
    svc = {s["id"]: s for s in services}
    def dst_of(fm):
        s = svc.get(fm["service_id"]) or {}
        return (s.get("dienststelle") or fm.get("publisher_dienststelle") or "(ohne Dienststelle)").strip()
    info = {}
    for d in dienststellen:
        try:
            k = json.loads(d.get("kontakt") or "[]")
        except ValueError:
            k = [d["kontakt"]] if d.get("kontakt") else []
        info[d["name"]] = {"department": d.get("department"), "kontakt": [x for x in k if x and x != d["name"]]}
    by_dst = {}
    for fm in forms:
        fm["dienststelle"] = dst_of(fm)             # whose form it is — answered once, read by the pages
        fm["standard"] = _standard_zahlen([fm])     # its data-standard figures on the atomic unit (the header of the Formular)
        by_dst.setdefault(fm["dienststelle"], []).append(fm)
    svc_by_dst = {}
    for s in services:
        svc_by_dst.setdefault((s.get("dienststelle") or "(ohne Dienststelle)").strip(), []).append(s["id"])
    order = {c: i for i, c in enumerate(LABELS.CAT_ORDER)}
    uebersicht = []
    for name in sorted(set(by_dst) | set(svc_by_dst)):
        fms = by_dst.get(name, [])
        cnt = {"act": 0, "dec": 0, "open": 0}
        stufen = {}
        pairs = []                                  # every open point of the Dienststelle with its form
        for fm in fms:
            for it in fm.get("handlungsbedarf") or []:
                cnt[it["ton"]] += it["n"]
                st = stufen.setdefault(str(it["stufe"]), {"act": 0, "dec": 0, "open": 0})
                st[it["ton"]] += it["n"]
                pairs.append((it, fm))
        entscheide = {}
        for it, fm in pairs:
            if it["ton"] == "dec":
                e = entscheide.setdefault(it["cat"], {"cat": it["cat"], "stufe": it["stufe"], "n": 0, "formulare": 0})
                e["n"] += it["n"]; e["formulare"] += 1
        i = info.get(name, {})
        uebersicht.append({
            "slug": _dst_slug(name), "name": name,
            "department": i.get("department") or next((svc[x].get("department") for x in svc_by_dst.get(name, [])
                                                       if svc.get(x) and svc[x].get("department")), None),
            "kontakt": i.get("kontakt", []),
            "services": sorted(svc_by_dst.get(name, [])), "formulare": sorted(fm["id"] for fm in fms),
            # the Massnahmen: what THIS Dienststelle can do itself (red), data standard
            # first; the canton's decisions (entscheide) and the databank's research
            # are listed apart on its page
            "offen": cnt, "stufen": stufen, "massnahmen": _massnahmen(fms),
            "entscheide": sorted(entscheide.values(), key=lambda e: (e["stufe"], order.get(e["cat"], 99))),
            "standard": _standard_zahlen(fms)})
    # headline figures — data standard first; each as a share of the whole, each
    # with parts that sum to it (checked in _summen_pruefen)
    std = _standard_zahlen(forms)
    mit_daten = [fm for fm in forms if fm.get("data_fields")]
    rg = _rechtsgrundlage_zahlen(forms)
    vz = _verzeichnis_zahlen(forms)
    tot = {"act": 0, "dec": 0, "open": 0}
    for fm in forms:
        for it in fm.get("handlungsbedarf") or []:
            tot[it["ton"]] += it["n"]
    e = std["ech"]
    kopf = {
        # «with an eCH element» stays the headline (as on every page); points whose
        # standard has no element catalogue are settled at standard level — own segment.
        # ech = every state with its number; ech_ton = the four parts a bar draws
        # (grey = open + zuordnung_falsch); teile keeps the corrected mappings apart
        "standard_ech": {"wert": std["mit_element"], "von": std["punkte"],
                          "teile": {"ok": e.get("element", 0), "zuordnung_falsch": e.get("zuordnung_falsch", 0),
                                    "ok_standard": e.get("standard_ohne_elemente", 0),
                                    "dec": e.get("kein_standard", 0) + e.get("standard_entwurf", 0),
                                    "open": e.get("element_offen", 0) + e.get("ungeprueft", 0) + e.get("standard_alt", 0)},
                          "ech": e, "ech_ton": std["ech_ton"]},
        "standard_einheitlich": {"wert": std["mit_element"] - std["div_punkte"] - std["div_offen"], "von": std["mit_element"],
                                 "teile": {"ok": std["mit_element"] - std["div_punkte"] - std["div_offen"],
                                           "act": std["div_punkte"], "dec": std["div_offen"]},
                                 "formulare_div": std["formulare_div"], "formulare": len(mit_daten)},
        # begriff_felder: the whole category «begriff» (rename or split); von/teile: every
        # naming verdict (teile.variante = the labels to rename, formulare_teile their forms)
        "standard_benannt": {"begriff_felder": std["begriff_felder"], **_benannt_zahlen(forms, std["mit_element"])},
        "rechtsgrundlage": rg,
        "verzeichnis": vz,
        "offene_punkte": tot,
        "kein_standard": _kein_standard_zahlen(forms),
        "kategorien": _kategorien(forms),
    }
    # trend: today's snapshot (DB-level figures + the export-level ones), history, notes
    doc = KZ.load()
    snap = KZ.db_kennzahlen(conn) or {}
    snap.update({"div_punkte": std["div_punkte"], "div_offen": std["div_offen"],
                 "formulare_div": std["formulare_div"], "begriff_felder": std["begriff_felder"],
                 "verzeichnis_vollstaendig": vz["wert"], "offen_act": tot["act"], "offen_dec": tot["dec"],
                 "offen_open": tot["open"]})
    KZ.upsert(doc, {"datum": date.today().isoformat(), "quelle": "build", **snap})
    doc["eintraege"].sort(key=lambda e: e["datum"])
    VERLAUF_DOC = doc
    notes_path = os.path.join(os.path.dirname(DB_PATH), "quellen", "verlauf_bemerkungen.json")
    try:
        with open(notes_path, encoding="utf-8") as fh:
            notes = json.load(fh)
    except FileNotFoundError:
        notes = {}
    except (OSError, ValueError) as ex:
        raise RuntimeError(f"quellen/verlauf_bemerkungen.json ist nicht lesbar ({ex}) — die Bemerkungen zum "
                           "Verlauf gingen verloren; Datei reparieren") from ex
    verlauf = [{**e, "bemerkung": notes.get(e["datum"])} for e in doc["eintraege"]]
    return uebersicht, kopf, verlauf


def _summen_pruefen(data):
    """Gate before anything is written: wherever the export publishes a total next to
    its parts, the parts sum to the total; and a figure that exists in two places
    (headline and category, canton and Dienststellen, SQL snapshot and export) is the
    same in both. Raises RuntimeError naming every figure that does not add up.
    The comparisons with a second source are left out when a layer was skipped
    (a table this databank does not have): the two sources then differ by design."""
    fehler = []

    def gleich(name, ist, soll, was):
        if ist != soll:
            if isinstance(ist, dict) and isinstance(soll, dict):      # name only what differs
                keys = [k for k in {**ist, **soll} if ist.get(k) != soll.get(k)]
                ist, soll = {k: ist.get(k) for k in keys}, {k: soll.get(k) for k in keys}
            fehler.append(f"{name}: {was} — {ist} statt {soll}")

    K, forms = data["kopfzahlen"], data["forms"]
    tones = ("act", "dec", "open")
    # (1) every headline figure with «teile»: the parts sum to «von»
    for k, v in K.items():
        if isinstance(v, dict) and "teile" in v:
            gleich(f"kopfzahlen.{k}", sum(v["teile"].values()), v.get("von"),
                   "die teile " + json.dumps(v["teile"], ensure_ascii=False) + " summieren nicht zum Ganzen «von»")
    E, U, N, R, V, Z, KAT = (K[k] for k in ("standard_ech", "standard_einheitlich", "standard_benannt",
                                            "rechtsgrundlage", "verzeichnis", "kein_standard", "kategorien"))
    # (2) the classifications on the units: stamped once, still true, with a tone
    ech, basis, n_units = {}, {}, 0
    for fm in forms:
        for d in fm.get("data_fields") or []:
            where = f"forms[{fm['id']}] «{d.get('name')}»"
            if d.get("basis_state") != _basis_state(d) or d.get("basis_state") not in LABELS.TON_MAP["basis"]:
                fehler.append(f"{where}: basis_state {d.get('basis_state')!r} statt {_basis_state(d)!r}")
            basis[d.get("basis_state")] = basis.get(d.get("basis_state"), 0) + 1
            for u in [d] + [x for x in (d.get("subfields") or []) if isinstance(x, dict)]:
                if u.get("ech_state") != _ech_state(u) or u.get("ech_state") not in LABELS.TON_MAP["ech"]:
                    fehler.append(f"{where}: ech_state {u.get('ech_state')!r} statt {_ech_state(u)!r}")
            for u in _units(d):
                n_units += 1
                ech[u.get("ech_state")] = ech.get(u.get("ech_state"), 0) + 1
    gleich("kopfzahlen.standard_ech.von", E["von"], n_units, "Datenpunkte der Formulare")
    gleich("kopfzahlen.standard_ech.ech", E["ech"], ech, "eCH-Stand der Datenpunkte (ech_state) nachgezählt")
    gleich("kopfzahlen.standard_ech.ech", sum(E["ech"].values()), E["von"], "Summe der Zustände gegen «von»")
    gleich("kopfzahlen.standard_ech.ech_ton", sum(E["ech_ton"].values()), E["von"], "Summe der vier Balkenteile gegen «von»")
    gleich("kopfzahlen.standard_ech.ech_ton", E["ech_ton"],
           {"ok": E["teile"]["ok"], "ok2": E["teile"]["ok_standard"], "dec": E["teile"]["dec"],
            "open": E["teile"]["open"] + E["teile"]["zuordnung_falsch"]}, "Balkenteile gegen teile (grau = open + zuordnung_falsch)")
    gleich("kopfzahlen.standard_ech.wert", E["wert"], E["teile"]["ok"] + E["teile"]["zuordnung_falsch"],
           "«mit eCH-Element» = ok + zuordnung_falsch")
    gleich("kopfzahlen.standard_einheitlich.von", U["von"], E["wert"], "das Ganze sind die Datenpunkte mit eCH-Element")
    gleich("kopfzahlen.standard_einheitlich.wert", U["wert"], U["teile"]["ok"], "wert = grüner Teil")
    gleich("kopfzahlen.standard_benannt.von", N["von"], E["wert"], "das Ganze sind die Datenpunkte mit eCH-Element")
    gleich("kopfzahlen.standard_benannt.begriff_felder", N["begriff_felder"], N["teile"]["variante"] + N["teile"]["aufteilen"],
           "Kategorie «begriff» = variante + aufteilen")
    gleich("kopfzahlen.standard_benannt.teile.zuordnung", N["teile"]["zuordnung"], E["teile"]["zuordnung_falsch"],
           "Bezeichnungen mit Urteil «zuordnung» gegen ech_state zuordnung_falsch")
    if min(N["teile"].values()) < 0:
        fehler.append(f"kopfzahlen.standard_benannt.teile: negativer Teil {N['teile']}")
    gleich("kopfzahlen.rechtsgrundlage.wert", R["wert"], R["teile"]["ok"], "wert = grüner Teil")
    gleich("kopfzahlen.rechtsgrundlage.teile", (R["teile"]["act"], R["teile"]["dec"], R["teile"]["open"]),
           (R["ohne"], R["offen"], R["zu_ermitteln"] + R["art5_offen"]), "rot/amber/grau gegen ohne/offen/zu_ermitteln+art5_offen")
    gleich("kopfzahlen.rechtsgrundlage.von", R["von"], sum(basis.values()), "Datenfelder der Formulare")
    gleich("kopfzahlen.verzeichnis.wert", V["wert"], V["teile"]["ok"], "wert = grüner Teil")
    gleich("kopfzahlen.verzeichnis.von", V["von"], sum(1 for fm in forms if fm.get("data_fields")), "Formulare mit Datenfeldern")
    gleich("kopfzahlen.kein_standard.von", Z["von"], E["teile"]["dec"], "der amber Teil von standard_ech")
    for k in ("esh", "ech_entwurf"):
        gleich(f"kopfzahlen.kein_standard.codes.{k}", sum(Z["codes"][k].values()), Z["teile"][k], "Summe je Code gegen den Teil")
    # (3) Handlungsbedarf: tones, categories and the headline say the same
    tot, cat_n = dict.fromkeys(tones, 0), {}
    for fm in forms:
        for it in fm.get("handlungsbedarf") or []:
            tot[it["ton"]] += it["n"]
            cat_n[it["cat"]] = cat_n.get(it["cat"], 0) + it["n"]
            if it["ton"] != LABELS.TON_OF_ART[LABELS.TODO_BY[it["cat"]][3]] or it["stufe"] != LABELS.STUFE_OF_CAT[it["cat"]]:
                fehler.append(f"forms[{fm['id']}].handlungsbedarf «{it['cat']}»: ton/stufe weichen von labels.py ab")
    gleich("kopfzahlen.offene_punkte", K["offene_punkte"], tot, "Punkte je Ton über alle Formulare")
    gleich("kopfzahlen.kategorien", {c: v["n"] for c, v in KAT.items() if v["n"]}, cat_n, "Punkte je Kategorie über alle Formulare")
    gleich("kopfzahlen.kategorien", {t: sum(v["n"] for c, v in KAT.items() if LABELS.TON_OF_ART[LABELS.TODO_BY[c][3]] == t) for t in tones},
           K["offene_punkte"], "Kategorien je Ton gegen offene_punkte")
    for cat, ist, was in (("kein_standard", E["teile"]["dec"], "standard_ech.teile.dec"),
                          ("echalt", E["ech"].get("standard_alt", 0), "standard_ech.ech.standard_alt"),
                          ("zuordnung", E["teile"]["zuordnung_falsch"], "standard_ech.teile.zuordnung_falsch"),
                          ("divergenz", U["teile"]["act"], "standard_einheitlich.teile.act"),
                          ("divergenz_offen", U["teile"]["dec"], "standard_einheitlich.teile.dec"),
                          ("begriff", N["begriff_felder"], "standard_benannt.begriff_felder"),
                          ("ech", E["ech"].get("element_offen", 0) + E["ech"].get("ungeprueft", 0),
                           "standard_ech.ech.element_offen+ungeprueft"),
                          ("ohne", R["ohne"], "rechtsgrundlage.ohne"), ("offen", R["offen"], "rechtsgrundlage.offen"),
                          ("ermitteln", R["zu_ermitteln"], "rechtsgrundlage.zu_ermitteln"),
                          ("sensibel_art5", R["art5_offen"], "rechtsgrundlage.art5_offen")):
        gleich(f"kopfzahlen.kategorien.{cat}.n", KAT[cat]["n"], ist, f"Kategorie gegen kopfzahlen.{was}")
    # (4) the Formulare: the per-form standard figures (forms[].standard, the header of
    # the Formular) add up to the canton
    ech_fm, punkte_fm = {}, 0
    for fm in forms:
        S = fm.get("standard") or {}
        punkte_fm += S.get("punkte", 0)
        for st, n in (S.get("ech") or {}).items():
            ech_fm[st] = ech_fm.get(st, 0) + n
    gleich("forms[].standard.punkte", punkte_fm, E["von"], "Summe über die Formulare gegen kopfzahlen.standard_ech.von")
    gleich("forms[].standard.ech", ech_fm, E["ech"], "Summe über die Formulare gegen kopfzahlen.standard_ech.ech")
    # (5) Dienststellen: each adds up, and together they are the canton
    fm_by_id = {fm["id"]: fm for fm in forms}
    DU = data["dienststellen_uebersicht"]
    for d in DU:
        nm, S = f"dienststellen_uebersicht[{d['slug']}]", d["standard"]
        gleich(nm + ".stufen", {t: sum(st[t] for st in d["stufen"].values()) for t in tones}, d["offen"], "Stufen je Ton gegen offen")
        gleich(nm + ".massnahmen", sum(m["n"] for m in d["massnahmen"]), d["offen"]["act"], "Punkte der Massnahmen gegen offen.act")
        gleich(nm + ".massnahmen[].formulare", sum(m["formulare"] for m in d["massnahmen"]),
               sum(1 for fid in d["formulare"] for it in fm_by_id[fid].get("handlungsbedarf") or [] if it["ton"] == "act"),
               "Formulare der Massnahmen gegen die roten Punkte (Kategorie × Formular) ihrer Formulare")
        gleich(nm + ".entscheide", sum(x["n"] for x in d["entscheide"]), d["offen"]["dec"], "Punkte der Entscheide gegen offen.dec")
        gleich(nm + ".standard.ech", sum(S["ech"].values()), S["punkte"], "Summe der Zustände gegen punkte")
        gleich(nm + ".standard.ech_ton", sum(S["ech_ton"].values()), S["punkte"], "Summe der vier Balkenteile gegen punkte")
        gleich(nm + ".standard.mit_element", S["mit_element"], S["ech"].get("element", 0) + S["ech"].get("zuordnung_falsch", 0),
               "element + zuordnung_falsch")
    gleich("dienststellen_uebersicht[].offen", {t: sum(d["offen"][t] for d in DU) for t in tones}, K["offene_punkte"],
           "Summe über die Dienststellen gegen kopfzahlen.offene_punkte")
    ech_dst = {}
    for d in DU:
        for st, n in d["standard"]["ech"].items():
            ech_dst[st] = ech_dst.get(st, 0) + n
    gleich("dienststellen_uebersicht[].standard.ech", ech_dst, E["ech"], "Summe über die Dienststellen gegen kopfzahlen.standard_ech.ech")
    for key, soll, was in (("div_punkte", U["teile"]["act"], "standard_einheitlich.teile.act"),
                           ("div_offen", U["teile"]["dec"], "standard_einheitlich.teile.dec"),
                           ("formulare_div", U["formulare_div"], "standard_einheitlich.formulare_div"),
                           ("begriff_felder", N["begriff_felder"], "standard_benannt.begriff_felder")):
        gleich(f"dienststellen_uebersicht[].standard.{key}", sum(d["standard"][key] for d in DU), soll,
               f"Summe über die Dienststellen gegen kopfzahlen.{was}")
    gleich("dienststellen_uebersicht[].formulare", sorted(i for d in DU for i in d["formulare"]), sorted(fm["id"] for fm in forms),
           "jedes Formular bei genau einer Dienststelle")
    gleich("dienststellen_uebersicht[].services", sorted(i for d in DU for i in d["services"]), sorted(sv["id"] for sv in data["services"]),
           "jeder Service bei genau einer Dienststelle")
    names = {d["name"] for d in DU}
    for fm in forms:
        if fm.get("dienststelle") not in names:
            fehler.append(f"forms[{fm['id']}].dienststelle {fm.get('dienststelle')!r} fehlt in dienststellen_uebersicht")
    # (5) one dossier file per service
    slugs = [sv.get("dossier_slug") for sv in data["services"]]
    gleich("services[].dossier_slug", len(set(slugs)), len(slugs), "Dateinamen der Dossiers eindeutig (sonst überschreibt ein Service den anderen)")
    z = data["zitate"]
    gleich("zitate.total", z["verifiziert"] + z["quelle_pdf"] + z["unverifiziert"], z["total"], "Summe der Stufen")
    # (6) the same figure from a second source
    if not SKIPPED_LAYERS:
        # this run's snapshot: the newest entry (uebersichten() has just upserted it)
        heute = max(data["verlauf"], key=lambda e: e["datum"], default={})
        for key, soll, was in (("formulare", len(forms), "forms"), ("punkte", E["von"], "kopfzahlen.standard_ech.von"),
                               ("punkte_ech", E["wert"], "kopfzahlen.standard_ech.wert"),
                               ("datenfelder", R["von"], "kopfzahlen.rechtsgrundlage.von"),
                               ("felder_gedeckt", R["wert"], "kopfzahlen.rechtsgrundlage.wert"),
                               ("felder_zitiert", basis.get("artikel", 0), "Datenfelder mit basis_state artikel"),
                               ("felder_ohne", R["ohne"], "kopfzahlen.rechtsgrundlage.ohne"),
                               ("felder_offen", R["offen"], "kopfzahlen.rechtsgrundlage.offen"),
                               ("felder_zu_ermitteln", R["zu_ermitteln"], "kopfzahlen.rechtsgrundlage.zu_ermitteln"),
                               ("felder_art5_offen", R["art5_offen"], "kopfzahlen.rechtsgrundlage.art5_offen")):
            gleich(f"verlauf[{heute.get('datum')}].{key}", heute.get(key), soll, f"SQL-Kennzahl (kennzahlen.py) gegen {was}")
        esh = {}
        for fm in forms:
            for d in fm.get("data_fields") or []:
                for u in _units(d):
                    if u.get("esh"):
                        esh[u["esh"]["code"]] = esh.get(u["esh"]["code"], 0) + 1
        gleich("esh_katalog[].n_live", {k["code"]: k["n_live"] for k in data["esh_katalog"] if k["n_live"]}, esh,
               "SQL-Zählung je eSH-Entwurf gegen die Datenpunkte der Formulare")
        BS = data["begriffe_stats"]
        gleich("begriffe_stats.n_felder_angleichen", BS.get("n_felder_angleichen"), N["teile"]["variante"],
               "Zählung der Begriffe-Schicht gegen kopfzahlen.standard_benannt.teile.variante")
        gleich("begriffe_stats.n_formulare_angleichen", BS.get("n_formulare_angleichen"), N["formulare_teile"]["variante"],
               "Zählung der Begriffe-Schicht gegen kopfzahlen.standard_benannt.formulare_teile.variante")
    if fehler:
        raise RuntimeError(f"{len(fehler)} Kennzahl(en) gehen nicht auf: " + " | ".join(fehler[:12])
                           + (f" | … und {len(fehler) - 12} weitere" if len(fehler) > 12 else ""))


# the tables of datentresor.db the Bürgersicht reads (scripts/build_datentresor.py)
DT_TABLES = {"meta", "subjekt", "fall", "datenpunkt", "datenpunkt_verwendung", "beleg", "zugriff_log", "einwilligung"}


def build(conn):
    del SKIPPED_LAYERS[:]                  # the skips of THIS run (common._layer_skipped)
    services = rows(conn, "SELECT id,slug,name,name_alt,dienststelle,department,"
                          "COALESCE(in_dvsh,0) AS in_dvsh FROM service ORDER BY name")
    # placeholder rows of the retired auto-draft (last_checked 'zitiert
    # (unverifiziert)') are no laws; the migration removed them, this keeps
    # a re-run of the old tool from reintroducing them into the surfaces
    laws = rows(conn, "SELECT id,slug,title,short_title,jurisdiction_level,sr_number,"
                      "cantonal_ref,last_checked FROM law "
                      "WHERE last_checked IS NULL OR last_checked != 'zitiert (unverifiziert)'")
    articles = rows(conn, "SELECT id,law_id,article_no,heading,last_checked FROM article")
    forms = rows(conn, "SELECT id,service_id,title,actual_purpose,title_content_mismatch,"
                       "mismatch_note,publisher_dienststelle,source_file,file_type,"
                       "purpose,dsfa_status,submission_channel,signature_requirement,"
                       "signature_evidence,acroform,parse_error,dvsh_match FROM form")
    # the retired 2026-06 auto-draft layer (form_field, field_mapping, requirement,
    # requirement_legal_basis, service_requirement) and its service-level rows
    # (process_step, finding) are not read here: no page shows them, and the
    # proof-gated data_field layer below is the only source of a legal basis
    # (citygov_llm.json lists process_step/finding as legacy text, read by
    # export_llm.py from the DB)

    law_by_id = {l["id"]: l for l in laws}
    for l in laws:
        l["articles"] = []
    articles = [a for a in articles if a["law_id"] in law_by_id]
    for a in articles:
        law_by_id[a["law_id"]]["articles"].append(a)

    # logical data-field catalogue (Datenfeld-Katalog), if derived for this form
    dfs_by_form = {}
    ech = {}                               # eCH elements by id; read again further down
    try:
        df_lb = {}
        for lb in rows(conn, "SELECT dflb.data_field_id did, a.article_no, a.heading, a.text_excerpt, "
                             "l.id lid, l.title, l.short_title, l.jurisdiction_level, l.sr_number, l.cantonal_ref, "
                             "a.last_checked, dflb.relation FROM data_field_legal_basis dflb "
                             "JOIN article a ON a.id=dflb.article_id JOIN law l ON l.id=a.law_id"):
            df_lb.setdefault(lb["did"], []).append({
                "law_id": lb["lid"],
                "jurisdiction": lb["jurisdiction_level"], "law_short": lb["short_title"],
                "law_title": lb["title"], "sr_number": lb["sr_number"], "cantonal_ref": lb["cantonal_ref"],
                "article_no": lb["article_no"], "article_heading": lb["heading"],
                "quote": (lb["text_excerpt"] or "")[:1600],
                "last_checked": lb["last_checked"], "relation": lb["relation"]})
        ech, ech_std = {}, {}
        try:
            for s in rows(conn, "SELECT code, title, url, n_elements, status, reifegrad "
                                "FROM ech_standard"):
                ech_std[s["code"]] = s
            xsd_ver = {}
            try:
                xsd_ver = {r["code"]: r["xsd_version"] for r in rows(conn, "SELECT code, xsd_version FROM ech_standard")}
            except Exception as _ex:
                _layer_skipped('XSD-Fassungen (ech_standard.xsd_version)', _ex)
            for e in rows(conn, "SELECT e.id, e.standard, e.name, e.datatype, e.context, s.title, s.url, "
                                "s.status, s.reifegrad, s.n_elements "
                                "FROM ech_element e JOIN ech_standard s ON s.code=e.standard"):
                ech[e["id"]] = {"id": e["id"], "standard": e["standard"], "element": e["name"],
                                "datatype": e["datatype"], "context": e["context"],
                                "standard_titel": e["title"], "url": e["url"],
                                "status": e["status"], "reifegrad": e["reifegrad"],
                                "n_elements": e["n_elements"], "xsd_version": xsd_ver.get(e["standard"])}
        except Exception as _ex:
            _layer_skipped('eCH-Katalog (ech_standard, ech_element)', _ex)
        # subfields with their OWN eCH element (Name/Vorname/Geburtsdatum each exact)
        esh_std2 = {}
        try:
            for r in rows(conn, "SELECT code, titel FROM esh_standard"):
                esh_std2[r["code"]] = r
        except Exception as _ex:
            _layer_skipped('eSH-Titel (esh_standard)', _ex)
        subs_by_field = {}
        try:
            for s in rows(conn, "SELECT sf.*, st.title stitle, st.url surl, st.n_elements snel, "
                                "st.status sstatus, st.reifegrad sreif "
                                "FROM data_subfield sf LEFT JOIN ech_standard st "
                                "ON st.code=sf.ech_standard_code ORDER BY sf.data_field_id, sf.ord"):
                e = ech.get(s.get("ech_element_id"))
                if not e and s.get("ech_standard_code"):
                    e = {"standard": s["ech_standard_code"], "element": None, "datatype": None,
                         "standard_titel": s["stitle"], "url": s["surl"], "n_elements": s["snel"],
                         "status": s["sstatus"], "reifegrad": s["sreif"]}
                sub = {"name": s["name"], "ech": e, "ech_status": s.get("ech_status")}
                if s.get("esh_code") and s["esh_code"] in esh_std2:
                    sub["esh"] = {"code": s["esh_code"], "element": s.get("esh_element"),
                                  "titel": esh_std2[s["esh_code"]]["titel"]}
                subs_by_field.setdefault(s["data_field_id"], []).append(sub)
        except Exception as _ex:
            _layer_skipped('Teilfelder (data_subfield)', _ex)
        esh_std = {}
        try:
            for r in rows(conn, "SELECT code, titel, beschreibung, n_felder FROM esh_standard"):
                esh_std[r["code"]] = r
        except Exception as _ex:
            _layer_skipped('eSH-Titel (esh_standard)', _ex)
        for d in rows(conn, "SELECT * FROM data_field ORDER BY form_id, ord"):
            d["ech"] = ech.get(d.get("ech_element_id"))
            if d.get("esh_code") and d["esh_code"] in esh_std:
                d["esh"] = {"code": d["esh_code"], "element": d.get("esh_element"),
                            "titel": esh_std[d["esh_code"]]["titel"]}
            if not d["ech"] and d.get("ech_standard_code"):
                s = ech_std.get(d["ech_standard_code"])
                if s:      # standard-level match; n_elements>0 means an element is still owed
                    d["ech"] = {"standard": s["code"], "element": None, "datatype": None,
                                "standard_titel": s["title"], "url": s["url"],
                                "n_elements": s["n_elements"], "status": s["status"],
                                "reifegrad": s["reifegrad"]}
            for k in ("allowed_values", "subfields", "source_widgets"):
                d[k] = json.loads(d[k]) if d.get(k) else []
            if d["id"] in subs_by_field:      # normalised subfields win over the raw JSON
                d["subfields"] = subs_by_field[d["id"]]
            if d.get("ech_herkunft") is None:   # provenance marker, set only on copied verdicts
                d.pop("ech_herkunft", None)
            d["required"] = bool(d["required"])
            d["no_basis"] = bool(d.get("no_basis"))
            d["legal_basis"] = df_lb.get(d["id"], [])
            # a besonders schützenswerte Angabe judged «aufgabennotwendig» is NOT
            # covered by KDSG Art. 4 Abs. 1 lit. b alone: Art. 5 Abs. 1 demands a
            # formal law that clearly describes the task (lit. a) or express
            # consent (lit. b) — until that is named, the basis is open
            d["art5_offen"] = bool(d.get("sensitive")) and d.get("basis_typ") == "aufgabe" and not d["legal_basis"]
            dfs_by_form.setdefault(d["form_id"], []).append(d)
    except Exception as _ex:
        _layer_skipped('Datenfelder (data_field, data_subfield, data_field_legal_basis)', _ex)

    checks = {}
    try:
        for r in rows(conn, "SELECT form_id, status, quelle, dvsh_neu, note, "
                            "substr(checked_at,1,10) d FROM form_check"):
            checks[r["form_id"]] = r
    except Exception as _ex:
        _layer_skipped('Online-Prüfung (form_check)', _ex)

    # Verzeichnis layer: recipients, retention profile, decisions — per form
    disc_by_form, ret_by_form, dec_by_form = {}, {}, {}
    try:
        for r in rows(conn, "SELECT fd.form_id, fd.empfaenger, fd.mode, a.article_no, "
                            "l.short_title, l.sr_number FROM form_disclosure fd "
                            "LEFT JOIN article a ON a.id=fd.article_id "
                            "LEFT JOIN law l ON l.id=a.law_id ORDER BY fd.empfaenger"):
            disc_by_form.setdefault(r.pop("form_id"), []).append(r)
        # a form's specific retention terms = terms of retention rules in the laws it cites
        law_terms = {}
        for r in rows(conn, "SELECT a.law_id, rt.duration_value, rt.duration_unit, rt.min_or_max, "
                            "rt.trigger_event, rt.disposition, dr.aspect, dr.summary, "
                            "a.article_no, l.short_title, l.sr_number "
                            "FROM retention_term rt JOIN data_rule dr ON dr.id=rt.data_rule_id "
                            "JOIN article a ON a.id=dr.article_id JOIN law l ON l.id=a.law_id "
                            "WHERE dr.scope='sektoral'"):
            law_terms.setdefault(r.pop("law_id"), []).append(r)
        for r in rows(conn, "SELECT DISTINCT d.form_id, a.law_id FROM data_field_legal_basis lb "
                            "JOIN data_field d ON d.id=lb.data_field_id "
                            "JOIN article a ON a.id=lb.article_id"):
            for t in law_terms.get(r["law_id"], []):
                ret_by_form.setdefault(r["form_id"], []).append(t)
        for r in rows(conn, "SELECT * FROM retention_decision"):
            dec_by_form.setdefault(r.pop("form_id"), []).append(r)
    except Exception as _ex:
        _layer_skipped('Bekanntgabe/Aufbewahrung (form_disclosure, retention_term, retention_decision)', _ex)

    # Verfahren layer: enclosures, outcomes, near-duplicates, guided-flow anchor
    beil_by_form, out_by_form, sim_by_form = {}, {}, {}
    flow_forms = set()
    try:
        for r in rows(conn, "SELECT form_id, bezeichnung, obligatorium, bedingung, halter, "
                            "fetchable, source FROM beilage ORDER BY obligatorium, bezeichnung"):
            beil_by_form.setdefault(r.pop("form_id"), []).append(r)
        for r in rows(conn, "SELECT * FROM form_outcome"):
            out_by_form[r.pop("form_id")] = r
        # the remedy behind each outcome, with the verified quote and its source
        try:
            for r in rows(conn, "SELECT o.form_id, rr.scope, rr.rechtsmittel_art, rr.frist_tage, rr.instanz, "
                                "rr.gilt_fuer, rr.quote, rr.frist_quote, rr.hinweis, rr.last_checked, "
                                "a.article_no, af.article_no frist_article_no, l.short_title, l.title law_title, "
                                "l.sr_number, l.cantonal_ref, l.jurisdiction_level FROM form_outcome o "
                                "JOIN rechtsmittel_regel rr ON rr.id=o.rechtsmittel_regel_id "
                                "JOIN article a ON a.id=rr.article_id LEFT JOIN article af ON af.id=rr.frist_article_id "
                                "JOIN law l ON l.id=rr.law_id"):
                fid = r.pop("form_id")
                if fid in out_by_form:
                    out_by_form[fid]["rechtsmittel"] = r
            # every verified remedy provision in the laws a form's fields cite -
            # shown as candidates so a reader sees the Spezialnormen, not only
            # the one the databank applied
            cand_by_law = {}
            for r in rows(conn, "SELECT rr.id, rr.law_id, rr.rechtsmittel_art, rr.frist_tage, rr.instanz, rr.gilt_fuer, "
                                "rr.hinweis, rr.quote, a.article_no, l.short_title, l.title law_title "
                                "FROM rechtsmittel_regel rr JOIN article a ON a.id=rr.article_id JOIN law l ON l.id=rr.law_id "
                                "WHERE rr.scope='sektoral' AND rr.gestrichen=0 ORDER BY rr.law_id, a.id"):
                cand_by_law.setdefault(r["law_id"], []).append(r)
            from load_rechtsmittel import cited_laws      # fields + DVSH-named laws
            laws_of_form = {fid: list(d.keys()) for fid, d in cited_laws(conn).items()}
            lvl_of_law = {l["id"]: l["jurisdiction_level"] for l in laws}
            reviewed = set()
            try:
                reviewed = {r["form_id"] for r in rows(conn, "SELECT form_id FROM rechtsmittel_verdikt")}
            except Exception as _ex:
                _layer_skipped('Rechtsmittel-Verdikt (rechtsmittel_verdikt)', _ex)
            for fid, o in out_by_form.items():
                cands = [c for lid in laws_of_form.get(fid, []) for c in cand_by_law.get(lid, [])]
                if cands:
                    o["rechtsmittel_kandidaten"] = cands
                # why a form has no remedy: assessed and left open, or not yet
                # assessed at all - the surfaces must not claim the same reason
                # for both, nor call a cantonal procedure federal
                ea = o.get("entscheid_art")
                if ea == "unbekannt":
                    # the outcome itself could not be backed from the DVSH text —
                    # the remedy question is not reached yet (a gap, shown as one)
                    o["rechtsmittel_status"] = "entscheidart_offen"
                elif ea in (None, "kein_entscheid"):
                    pass
                elif not o.get("rechtsmittel"):
                    o["rechtsmittel_status"] = ("beurteilt_offen"
                                                if o.get("rechtsmittel_quelle") == "offen" or fid in reviewed
                                                else "nicht_beurteilt")
                    o["gesetzesebenen"] = sorted({lvl_of_law.get(lid) for lid in laws_of_form.get(fid, [])
                                                  if lvl_of_law.get(lid)})
                elif o.get("rechtsmittel_quelle") == "allgemein" and fid not in reviewed:
                    # the VRG fallback applied mechanically, no verdict yet that
                    # no Fachgesetz goes first — distinguishable from a confirmed one
                    o["rechtsmittel_status"] = "default_allgemein"
            # the panel's reasoning where a judgment was needed
            try:
                for r in rows(conn, "SELECT form_id, quelle, begruendung FROM rechtsmittel_verdikt"):
                    if r["form_id"] in out_by_form:
                        out_by_form[r["form_id"]]["rechtsmittel_verdikt"] = f"{r['quelle']}: {_lesbar_pruefvermerk(r['begruendung'])}"
            except Exception as _ex:
                _layer_skipped('Rechtsmittel-Verdikt (rechtsmittel_verdikt)', _ex)
        except Exception as _ex:
            # nothing in here may fail silently: without it the forms lose their remedy,
            # the candidates and the Prüfvermerk, and open points vanish from the board
            _layer_skipped('Rechtsmittel (rechtsmittel_regel, Kandidaten, Prüfvermerk)', _ex)
        tit = {f["id"]: f["title"] for f in forms}
        for r in rows(conn, "SELECT form_a, form_b, jaccard_names, verdict FROM form_similarity "
                            "WHERE jaccard_names>=0.5 AND (verdict IS NULL OR verdict!='ok')"):
            for me, other in ((r["form_a"], r["form_b"]), (r["form_b"], r["form_a"])):
                sim_by_form.setdefault(me, []).append(
                    {"form_id": other, "titel": tit.get(other, "?"),
                     "jaccard": r["jaccard_names"], "verdict": r["verdict"]})
        flow_forms = {r["form_id"] for r in rows(conn, "SELECT DISTINCT form_id FROM formflow")}
    except Exception as _ex:
        _layer_skipped('Verfahren (beilage, form_outcome, form_similarity, formflow)', _ex)
    # which eCH elements the Einwohnerregister already holds (for the burden metric)
    reg_elems = set()
    try:
        reg_elems = {r["id"] for r in rows(
            conn, "SELECT id FROM ech_element WHERE standard IN "
                  "('eCH-0044','eCH-0010','eCH-0011','eCH-0007','eCH-0008')")}
    except Exception as _ex:
        _layer_skipped('Einwohnerregister-Elemente (ech_element)', _ex)
    # when the online version of each form is due for its next check — without it
    # every «Online-Prüfung fällig» point would vanish, so it never fails silently
    checks_due = {}
    try:
        checks_due = {r["form_id"]: r["next_check_due"] for r in rows(
            conn, "SELECT form_id, next_check_due FROM form_check")}
    except Exception as _ex:
        _layer_skipped('Wiedervorlage der Online-Prüfung (form_check.next_check_due)', _ex)
    conn_elem_ids = {(e["standard"], e["element"]): eid for eid, e in ech.items()}

    # exchange readiness, citizen burden and named digitalization blockers per form
    linked_dfs = set()
    try:
        linked_dfs = {r["data_field_id"] for r in rows(conn, "SELECT data_field_id FROM beilage WHERE data_field_id IS NOT NULL")}
    except Exception as _ex:
        _layer_skipped("Beilagen (beilage)", _ex)
    for fm in forms:
        pts = ok = req = pref = 0
        # enclosures = every row of the Beilagen list (Formular and DVSH), plus
        # attachment fields that have no Beilage row; obligatorium is not weighted
        att = len(beil_by_form.get(fm["id"], [])) + sum(
            1 for d in dfs_by_form.get(fm["id"], []) if d.get("data_type") == "attachment" and d.get("id") not in linked_dfs)
        for d in dfs_by_form.get(fm["id"], []):
            subs = [s for s in (d.get("subfields") or []) if isinstance(s, dict)]
            units = subs if subs else [d]
            pts += len(units)
            for u in units:
                e = u.get("ech")
                if e and e.get("element"):
                    ok += 1
                    # the Einwohnerregister already holds this datum -> once-only
                    # candidate; marked on the unit so the field row can show it.
                    # Only for a natural person's datum: the register knows no
                    # business address, vehicle location or authority (subjekt
                    # is the panel verdict per field; unset = never marked)
                    eid = conn_elem_ids.get((e.get("standard"), e.get("element")))
                    if eid in reg_elems and d.get("subjekt") == "natuerliche_person":
                        u["register"] = "einwohnerregister"
                        if d.get("required"):
                            pref += 1
                if d.get("required"):
                    req += 1
        fm["exchange_pct"] = round(100 * ok / pts) if pts else None
        # time model: ~0.4 min per required input, 5 min per enclosure (documented here)
        fm["burden"] = ({"inputs": req, "attachments": att, "prefillable": pref,
                         "minutes": round(req * 0.4 + att * 5, 1),
                         "minutes_saved": round(pref * 0.4, 1)} if pts else None)
        blockers = []
        if fm.get("signature_requirement") == "handschriftlich":
            blockers.append("Unterschrift")
        if fm.get("parse_error") or fm.get("acroform") == 0:
            blockers.append("Quelle nicht befüllbar")
        if fm.get("submission_channel") != "online_formular":
            blockers.append("kein Online-Kanal")
        if fm["exchange_pct"] is not None and fm["exchange_pct"] < 50:
            blockers.append("eCH-Abdeckung < 50%")
        # a missing guided flow is our own backlog, not a property of the form —
        # it stays visible as has_flow but no longer counts as a blocker
        fm["blockers"] = blockers if pts else None
        fm["has_flow"] = fm["id"] in flow_forms
        fm["next_check_due"] = checks_due.get(fm["id"])
        fm["data_fields"] = dfs_by_form.get(fm["id"], [])
        fm["check"] = checks.get(fm["id"])
        fm["disclosures"] = disc_by_form.get(fm["id"], [])
        fm["retention"] = ret_by_form.get(fm["id"], [])
        fm["retention_decisions"] = dec_by_form.get(fm["id"], [])
        fm["beilagen"] = beil_by_form.get(fm["id"], [])
        fm["outcome"] = out_by_form.get(fm["id"])
        fm["similar"] = sim_by_form.get(fm["id"], [])

    # DVSH modeller data (source of truth for the service), keyed by service id
    dvsh_by_service = {}
    try:
        for d in rows(conn, "SELECT * FROM dvsh_service WHERE service_id IS NOT NULL"):
            for k in ("voraussetzungen", "unterlagen", "ablauf", "recht_kantonal",
                      "recht_bund", "externe_links", "abgabe", "kontakt", "documents",
                      "sources", "form_definitions", "submission_endpoint",
                      "completeness", "opening_hours"):
                # some modeller columns are double-encoded (a JSON string whose
                # content is itself JSON); one decode then yields text where the
                # consumers expect a list, so decode until it stops being a
                # string. Whatever is left that is not a list/dict is wrapped,
                # so no consumer ever receives bare text where a list belongs
                v = d.get(k)
                for _ in range(3):
                    if not isinstance(v, str) or not v.strip():
                        break
                    try:
                        v = json.loads(v)
                    except Exception:
                        break
                if v is None or v == "":
                    v = []
                elif isinstance(v, str):
                    v = [v]
                if isinstance(v, list):
                    # a list may still hold JSON text as items (double-encoded rows)
                    flat = []
                    for x in v:
                        if isinstance(x, str) and x.lstrip().startswith(("[", "{")):
                            try:
                                y = json.loads(x)
                                flat.extend(y if isinstance(y, list) else [y]); continue
                            except Exception:
                                pass
                        flat.append(x)
                    v = flat
                d[k] = v
            # scalar modeller text: «null» is no fee, and a parser glitch that left
            # markup in the text is cut at the first tag and recorded as a defect
            for k in ("gebuehren", "bearbeitungsdauer", "fristen"):
                t = d.get(k)
                if isinstance(t, str):
                    if t.strip().lower() in ("null", "none", "leer", ""):
                        d[k] = None; continue
                    m = re.search(r"</|<parameter", t)
                    if m:
                        d[k] = t[:m.start()].rstrip()
                        d.setdefault("dvsh_text_glitch", []).append(k)
            dvsh_by_service.setdefault(d["service_id"], []).append(d)
    except Exception as _ex:
        _layer_skipped('DVSH-Modell (dvsh_service)', _ex)
    # SHEP: the PUBLISHED citizen view of the same service
    shep_by_service = {}
    try:
        for sp in rows(conn, "SELECT * FROM shep_service WHERE service_id IS NOT NULL"):
            for k in ("voraussetzungen", "unterlagen", "ablauf", "links", "dokumente"):
                try:
                    sp[k] = json.loads(sp[k]) if sp.get(k) else []
                except Exception:
                    sp[k] = []
            shep_by_service[sp["service_id"]] = sp
    except Exception as _ex:
        _layer_skipped('SHEP-Portal (shep_service)', _ex)
    for s in services:
        s["dossier_slug"] = dossier_slug(s)         # dossiers/<dossier_slug>.html (export_dossiers.py)
        got = dvsh_by_service.get(s["id"])
        if got:
            same = [g for g in got if (g.get("title") or "").strip().lower() == (s["name"] or "").strip().lower()]
            s["dvsh"] = (same or got)[0]
            if len(got) > 1:
                s["dvsh_n"] = len(got)      # the dashboard says «eine von N Modellierungen»
        if s["id"] in shep_by_service:
            s["shep"] = shep_by_service[s["id"]]

    esh_katalog = []
    try:
        # n_felder is a snapshot from the eSH draft's creation; the live count
        # is what the field layer says TODAY (on the atomic unit: a composite is
        # represented by its parts), and the two drift apart with every eCH
        # assignment that replaces a draft code. _summen_pruefen compares n_live
        # with the Datenpunkte of the forms — the pages read it as it is
        esh_katalog = rows(conn, "SELECT code, titel, beschreibung, themen, status, n_felder, "
                                 "(SELECT COUNT(*) FROM data_field d WHERE d.esh_code=esh_standard.code AND NOT EXISTS "
                                 " (SELECT 1 FROM data_subfield x WHERE x.data_field_id=d.id)) "
                                 "+(SELECT COUNT(*) FROM data_subfield s WHERE s.esh_code=esh_standard.code) n_live "
                                 "FROM esh_standard ORDER BY code")
    except Exception as _ex:
        _layer_skipped('eSH-Katalog (esh_standard)', _ex)

    # canonical attribute catalogue + the divergence lists for the Datenkatalog tab
    katalog, dienststellen = [], []
    try:
        katalog = rows(conn, "SELECT ca.id, ca.label, ca.datatype, ca.sensitive_categories, "
                             "ca.register_source, ca.n_instances, ca.n_forms, ca.n_register, "
                             "e.standard ech_standard, e.name ech_element, ca.esh_key "
                             "FROM canonical_attribute ca "
                             "LEFT JOIN ech_element e ON e.id=ca.ech_element_id "
                             "ORDER BY ca.n_forms DESC, ca.n_instances DESC")
        dienststellen = rows(conn, "SELECT name, department, dateninhaber, kontakt FROM dienststelle")
    except Exception as _ex:
        _layer_skipped('Attributkatalog (canonical_attribute, dienststelle)', _ex)

    # data-governance rules (how data may be stored, treated, communicated);
    # the dashboard groups by scope and matches 'sektoral' rules to a form via law_id
    handhabung = []
    try:
        for r in rows(conn, "SELECT dr.aspect, dr.scope, dr.sensitive_category, dr.summary, "
                            "dr.quote, dr.quote_verified, a.article_no, a.heading, a.law_id, "
                            "l.short_title, l.title law_title, l.sr_number, l.jurisdiction_level "
                            "FROM data_rule dr JOIN article a ON a.id=dr.article_id "
                            "JOIN law l ON l.id=a.law_id ORDER BY dr.scope, a.law_id, a.id"):
            handhabung.append(r)
    except Exception as _ex:
        _layer_skipped('Datenhandhabung (data_rule)', _ex)

    # official code lists (enumerations from the swept XSDs) for the datatypes
    # of elements that fields actually map to - the dashboard compares a form's
    # value list against them
    codelists = {}
    try:
        used = set()
        for r in rows(conn, "SELECT DISTINCT e.standard, e.datatype, e.context, e.name FROM ech_element e "
                            "WHERE e.id IN (SELECT ech_element_id FROM data_field WHERE ech_element_id IS NOT NULL "
                            "UNION SELECT ech_element_id FROM data_subfield WHERE ech_element_id IS NOT NULL)"):
            if r["datatype"]:
                used.add((r["standard"], r["datatype"]))
            used.add((r["standard"], f"@{r['context'] or ''}.{r['name']}"))
        for r in rows(conn, "SELECT standard, type_name, value, doc FROM ech_codelist ORDER BY standard, type_name, id"):
            if (r["standard"], r["type_name"]) in used:
                codelists.setdefault(f"{r['standard']}|{r['type_name']}", []).append(
                    {"value": r["value"], "doc": r["doc"]})
    except Exception as _ex:
        _layer_skipped('Codelisten (ech_codelist)', _ex)

    # ---- Begriffe: one datum, one name --------------------------------------
    # The naming verdicts (load_begriffe.py) land on each unit, so the field
    # row, the form's divergence panel and the Begriffe page read one answer.
    begriffe, begriffe_stats, bez_by_form = [], {}, {}
    try:
        from common import norm_label as _bn      # the key of begriff_label, one definition
        bv = {r["ech_element_id"]: r for r in rows(conn, "SELECT * FROM begriff_vorschlag")}
        bl = {(r["ech_element_id"], r["label_norm"]): r for r in rows(conn, "SELECT * FROM begriff_label")}
        # the same element name exists in several XML contexts (several ids);
        # a verdict judged under one of them also answers the others
        sib = {}
        for eid0, e0 in ech.items():
            sib.setdefault((e0["standard"], e0["element"]), []).append(eid0)
        use = {}          # element id -> label_norm -> {"n", "forms"}
        forms_var = set()
        for fm in forms:
            items = []
            for d in fm.get("data_fields") or []:
                subs = [x for x in (d.get("subfields") or []) if isinstance(x, dict)]
                for u in (subs or [d]):
                    e = u.get("ech") or {}
                    if not e.get("element"):
                        continue
                    eid = e.get("id") or conn_elem_ids.get((e["standard"], e["element"]))
                    lab = u.get("name") if subs else d["name"]
                    ln = _bn(lab)
                    if not ((eid, ln) in bl and eid in bv):
                        alt = next((x for x in sib.get((e["standard"], e["element"]), [])
                                    if (x, ln) in bl and x in bv), None)
                        if alt is not None:
                            eid = alt
                    uu = use.setdefault(eid, {}).setdefault(ln, {"n": 0, "forms": set()})
                    uu["n"] += 1; uu["forms"].add(fm["id"])
                    v, lr = bv.get(eid), bl.get((eid, ln))
                    if not (v and lr):
                        continue
                    u["begriff"] = {"klasse": lr["klasse"], "vorschlag": v["term"], "vorbehalt": bool(v.get("vorbehalt")),
                                    "rolle": lr["rolle"], "grund": _klartext(lr.get("pruefart_grund") or lr["grund"]),
                                    "pruefart": lr.get("pruefart")}
                    if lr["klasse"] == "variante":
                        forms_var.add(fm["id"])
                    if lr["klasse"] in ("variante", "pruefen"):
                        items.append({"feld": d["name"], "teilfeld": u.get("name") if subs else None,
                                      "standard": e["standard"], "element": e["element"],
                                      "klasse": lr["klasse"], "hier": lab, "vorschlag": v["term"],
                                      "pruefart": lr.get("pruefart"),
                                      "grund": _klartext(lr.get("pruefart_grund") or lr["grund"])})
            bez_by_form[fm["id"]] = items
        for eid, v in bv.items():
            e = ech.get(eid) or {}
            labs = []
            for r in rows(conn, "SELECT * FROM begriff_label WHERE ech_element_id=? ORDER BY klasse, label", eid):
                uu = use.get(eid, {}).get(r["label_norm"], {"n": 0, "forms": set()})
                labs.append({"label": r["label"], "klasse": r["klasse"], "rolle": r["rolle"],
                             "pruefart": r.get("pruefart"), "grund": _klartext(r.get("pruefart_grund") or r["grund"]),
                             "n": uu["n"], "formulare": sorted(uu["forms"])[:40], "n_formulare": len(uu["forms"])})
            begriffe.append({"element_id": eid, "standard": e.get("standard"), "element": e.get("element"),
                             "datentyp": e.get("datatype"), "standard_titel": e.get("standard_titel"),
                             "vorschlag": v["term"], "begruendung": _klartext(v.get("pruefung") or v["begruendung"]),
                             "vorbehalt": bool(v.get("vorbehalt")), "herkunft": v.get("herkunft") or "eigen",
                             "labels": labs})
        begriffe.sort(key=lambda b: -sum(l["n"] for l in b["labels"] if l["klasse"] == "variante"))
        # untruncated totals — the per-label form lists above are capped at 40
        n_single = sum(1 for eid0, labs in use.items() if eid0 not in bv and len(labs) == 1)
        begriffe_stats = {"n_formulare_angleichen": len(forms_var),
                          "n_felder_angleichen": sum(u2["n"] for eid0, labs in use.items() for ln0, u2 in labs.items()
                                                     if (bl.get((eid0, ln0)) or {}).get("klasse") == "variante"),
                          "n_elemente_eine_bezeichnung": n_single}
    except Exception as ex:
        _layer_skipped("Begriffe", ex)

    # ---- ech_state / basis_state: ONE classification per unit, read by every figure
    # below and by every page (needs the naming verdicts above)
    _zustaende_setzen(forms)

    # ---- Standard-Divergenzen je Formular ------------------------------------
    # What keeps THIS form out of one coherent data standard. Two very different
    # things, kept apart: (a) the same datum demanded DIFFERENTLY than on the
    # other forms (mandatory vs optional, other type/format, own value list
    # instead of the official codes) - that is a divergence someone has to
    # settle; (b) no citable standard for the datum at all - that is a missing
    # standard, not a divergence. Computed once, here, so dashboard, dossier and
    # LLM export cannot tell different stories.
    DRAFT_STATUS = {"In Arbeit", "Sistiert", "Aufgehoben", "Abgelöst"}

    def _parts(d):
        subs = [s for s in (d.get("subfields") or []) if isinstance(s, dict)]
        return subs, (subs if subs else [d])

    # statistics per datum — keyed like the Lebenslagen (datum_key): the address
    # of the Ehegatte is never the practice the applicant's address deviates from
    el_stat = {}
    for fm in forms:
        for d in fm.get("data_fields") or []:
            subs, units = _parts(d)
            for u in units:
                key = datum_key(d, u, subs)
                if key is None:
                    continue
                st = el_stat.setdefault(key, {"req": 0, "opt": 0, "shape": {}, "forms": set(), "by_form": {}})
                st["req" if d.get("required") else "opt"] += 1
                bf = st["by_form"].setdefault(fm["id"], {"req": 0, "opt": 0})
                bf["req" if d.get("required") else "opt"] += 1
                st["forms"].add(fm["id"])
                if not subs:          # shape belongs to the field, not to a part
                    sh = ((d.get("data_type") or "?"), (d.get("format") or ""))
                    st["shape"][sh] = st["shape"].get(sh, 0) + 1

    def _basis_txt(d):
        if d.get("legal_basis"):
            b = d["legal_basis"][0]
            return f"{b.get('article_no','')} {b.get('law_short') or ''}".strip()
        if d.get("art5_offen"):
            return "aufgabennotwendig — Grundlage nach KDSG Art. 5 Abs. 1 noch nicht benannt"
        return {"aufgabe": "aufgabennotwendig (KDSG Art. 4 Abs. 1 lit. b)",
                "ohne": "ohne Grundlage", "offen": "Aufgabenbedarf offen"}.get(
                    d.get("basis_typ"), "Rechtsgrundlage zu ermitteln")

    for fm in forms:
        items, offen = [], {}
        for d in fm.get("data_fields") or []:
            subs, units = _parts(d)
            for u in units:
                e = u.get("ech") or {}
                tf = u.get("name") if subs else None
                if e.get("element"):
                    key = datum_key(d, u, subs)
                    st = (el_stat.get(key) or {}) if key else {}
                    # (a1) requiredness: this form against the OTHER forms — every
                    # occurrence on this form is taken out of «the others»
                    r, o = st.get("req", 0), st.get("opt", 0)
                    mine = st.get("by_form", {}).get(fm["id"], {"req": 0, "opt": 0})
                    n_other_forms = len(st.get("forms", ())) - 1
                    if r and o and (r + o) >= 3 and n_other_forms >= 2:
                        here = bool(d.get("required"))
                        others_req, others_opt = r - mine["req"], o - mine["opt"]
                        n_oth = others_req + others_opt
                        # the first two numbers count Datenpunkte (occurrences), the last
                        # one Formulare — said so, or «17 Pflicht / 27 optional auf 27
                        # Formularen» reads as a contradiction (44 > 27)
                        andere = (f"{_tsd(others_req)}× Pflicht, {_tsd(others_opt)}× optional "
                                  f"({_tsd(n_oth)} Datenpunkte) auf {_tsd(n_other_forms)} anderen Formularen")
                        maj_req = others_req > others_opt
                        share = max(others_req, others_opt) / n_oth if n_oth else 0
                        if n_oth >= 2 and share >= 2 / 3 and here != maj_req:
                            # a clear practice elsewhere, and this form departs from it
                            items.append({
                                "art": "pflicht", "feld": d["name"], "teilfeld": tf,
                                "standard": e["standard"], "element": e["element"],
                                "hier": "Pflicht" if here else "optional",
                                "andere": andere, "basis": _basis_txt(d),
                                "aktion": ("Angleichen oder begründen: dieselbe Angabe ist anderswo "
                                           + ("Pflicht" if maj_req else "optional")
                                           + ". Eine abweichende Rechtsgrundlage rechtfertigt die "
                                             "Abweichung — dann gehört sie dokumentiert.")})
                        elif n_oth >= 2 and share < 2 / 3:
                            # no practice to deviate from: the corpus itself is split,
                            # so no single form is the outlier — this needs one decision
                            items.append({
                                "art": "pflicht_uneinheitlich", "feld": d["name"], "teilfeld": tf,
                                "standard": e["standard"], "element": e["element"],
                                "hier": "Pflicht" if here else "optional",
                                "andere": andere, "basis": _basis_txt(d),
                                "aktion": ("Die übrigen Formulare sind bei dieser Angabe selbst uneinheitlich — hier "
                                           "ist nicht dieses Formular die Ausnahme, sondern es fehlt "
                                           "eine kantonale Festlegung, ob die Angabe verlangt wird.")})
                    # (a2) type/format of the same datum
                    if not subs and st.get("shape"):
                        mine = ((d.get("data_type") or "?"), (d.get("format") or ""))
                        top = max(st["shape"].items(), key=lambda kv: kv[1])
                        tot_sh = sum(st["shape"].values())
                        if (len(st["shape"]) > 1 and st["shape"].get(mine, 0) < top[1]
                                and top[1] >= 2 and top[1] / tot_sh >= 2 / 3):
                            items.append({
                                "art": "format", "feld": d["name"], "teilfeld": None,
                                "standard": e["standard"], "element": e["element"],
                                "hier": (mine[0] + (" · " + mine[1] if mine[1] else "")),
                                "andere": (top[0][0] + (" · " + top[0][1] if top[0][1] else "")
                                           + f" auf {top[1]} Feldern"),
                                "basis": _basis_txt(d),
                                "aktion": ("Auf die gebräuchliche Form bringen — beim Austausch "
                                           + (f"gilt ohnehin der XSD-Typ ⟨{e['datatype']}⟩." if e.get("datatype")
                                              else "gilt der Typ des Standards; er ist im Elementkatalog nicht erhoben."))})
                    # (a3) own value list where the standard defines codes — a named
                    # type, or the enumeration inline in the element (eCH-0278);
                    # a restricted context with a single value is no code list
                    if not subs:
                        clk = f"{e['standard']}|{e['datatype']}" if e.get("datatype") else None
                        cl = codelists.get(clk) if clk else None
                        if not cl:
                            clk = f"{e['standard']}|@{e.get('context') or ''}.{e['element']}"
                            cl = codelists.get(clk)
                        if cl and len(cl) >= 2:
                            e["codelist_key"] = clk
                        else:
                            cl = None
                        vals = [str(v) for v in (d.get("allowed_values") or [])]
                        if cl and vals:
                            codes = {c["value"] for c in cl}
                            if not all(v in codes for v in vals):
                                items.append({
                                    "art": "codeliste", "feld": d["name"], "teilfeld": None,
                                    "standard": e["standard"], "element": e["element"],
                                    "hier": " · ".join(vals[:6]) + ("…" if len(vals) > 6 else ""),
                                    "andere": (f"{len(cl)} offizielle Codes: "
                                               + ", ".join(c["value"] + (" = " + c["doc"] if c.get("doc") else "")
                                                           for c in cl[:6])
                                               + ("…" if len(cl) > 6 else "")),
                                    "basis": _basis_txt(d),
                                    "aktion": ("Werte auf die Codeliste des Standards abbilden — "
                                               "im Formular darf der Klartext stehen, ausgetauscht "
                                               "wird der Code.")})
                    if e.get("status") in DRAFT_STATUS:
                        k = ("standard_entwurf" if e.get("status") == "In Arbeit" else "standard_alt",
                             e["standard"], e.get("status"))
                        offen.setdefault(k, []).append(tf or d["name"])
                elif e.get("standard") and e.get("status") in DRAFT_STATUS:
                    k = ("standard_entwurf" if e.get("status") == "In Arbeit" else "standard_alt",
                         e["standard"], e.get("status"))
                    offen.setdefault(k, []).append(tf or d["name"])
                elif e.get("standard") and not e.get("n_elements"):
                    # the standard has no element catalogue in the databank (no
                    # XSD, or a process/FHIR standard): a standard-level match is
                    # the final answer here, not an element still owed
                    k = ("standard_ohne_elemente", e["standard"], e.get("status"))
                    offen.setdefault(k, []).append(tf or d["name"])
                elif e.get("standard"):
                    k = ("element_offen", e["standard"], e.get("status"))
                    offen.setdefault(k, []).append(tf or d["name"])
                elif u.get("ech_status") == "kein_standard":
                    k = ("kein_standard", (u.get("esh") or {}).get("code"), None)
                    offen.setdefault(k, []).append(tf or d["name"])
                else:
                    offen.setdefault(("ungeprueft", None, None), []).append(tf or d["name"])
        AKT = {
            "element_offen": "Element im Standard bestimmen — der Standard passt, das konkrete "
                             "XML-Element fehlt noch.",
            "standard_entwurf": "Bei eCH noch in Arbeit — bis der Standard verabschiedet ist, entscheidet der "
                                "Kanton, was gilt; eine element-genaue Zuordnung ist erst danach möglich.",
            "standard_alt": "Nicht mehr in Kraft (sistiert, aufgehoben oder abgelöst) — die Zuordnung ist auf den "
                            "Nachfolger umzustellen.",
            "standard_ohne_elemente": "Der Standard führt in der Databank keinen XML-Elementkatalog "
                                      "(keine eigene XSD bzw. Prozess-/FHIR-Standard) — die Zuordnung "
                                      "bleibt auf Standard-Ebene; ein Element ist hier nicht zu bestimmen.",
            # {obj}: «diese Angabe» / «diese Angaben» — the item collects one or several fields
            "kein_standard": "Kein eCH-Standard deckt {obj} ab — hier braucht es den "
                             "kantonalen Entwurf eSH (oder einen neuen, wo auch eSH fehlt).",
            "ungeprueft": "Noch nicht gegen den eCH-Katalog geprüft.",
        }
        for (art, std, status), felder in sorted(offen.items(), key=lambda kv: -len(kv[1])):
            items.append({"art": art, "sammel": True, "n": len(felder),
                          "standard": std, "status": status,
                          "felder": sorted(set(felder))[:14],
                          "aktion": AKT[art].replace("{obj}", "diese Angabe" if len(felder) == 1 else "diese Angaben")
                                    + (" Entwurf vorhanden: " + std if art == "kein_standard" and std
                                                else (" Kein eSH-Entwurf vorhanden." if art == "kein_standard" else ""))})
        ang = [i for i in items if not i.get("sammel")]
        bez = bez_by_form.get(fm["id"], [])
        fm["standard_divergenzen"] = {
            "angleichen": ang,
            "fehlend": [i for i in items if i.get("sammel")],
            # n_angleichen counts only what THIS form should align; a split
            # corpus (pflicht_uneinheitlich) is a cantonal decision, counted apart
            "n_angleichen": sum(1 for i in ang if i["art"] != "pflicht_uneinheitlich"),
            "n_pflicht_ungeklaert": sum(1 for i in ang if i["art"] == "pflicht_uneinheitlich"),
            "n_fehlend": sum(i["n"] for i in items if i.get("sammel")),
            "bezeichnungen": bez, "n_bezeichnungen": len(bez),
        } if (fm.get("data_fields") or []) else None

    # ---- Lebenslagen: eCH-0049 Themengruppen, with live statistics -----------
    # What a person (or business) meets in one situation: which services, which
    # offices, how many answers, how many of them asked AGAIN by another service
    # of the same situation, and how many the Einwohnerregister could supply.
    # Only data with an eCH element can be recognised as "the same datum"
    # across forms; everything else is counted separately, never guessed.
    themenkatalog = []
    try:
        th_by_svc = {}
        for r in rows(conn, "SELECT st.service_id, st.rang, t.id, t.katalog, t.bereich, t.gruppe "
                            "FROM service_thema st JOIN themenkatalog t ON t.id=st.thema_id ORDER BY st.service_id, st.rang"):
            th_by_svc.setdefault(r["service_id"], []).append(
                {"id": r["id"], "katalog": r["katalog"], "bereich": r["bereich"], "gruppe": r["gruppe"], "rang": r["rang"]})
        grund = {r["service_id"]: r["grund"] for r in rows(conn, "SELECT service_id, grund FROM service_thema_grund")}
        for sv in services:
            sv["themen"] = th_by_svc.get(sv["id"], [])
            if sv["id"] in grund and not sv["themen"]:
                sv["themen_grund"] = grund[sv["id"]]
        forms_by_svc = {}
        for fm in forms:
            forms_by_svc.setdefault(fm["service_id"], []).append(fm)
        svc_by_id = {sv["id"]: sv for sv in services}
        # "The same datum" across two services is claimed only when it is
        # provably the same thing asked of the same party:
        #  * same eCH element (by standard and element name)
        #  * not a generic container (a «Dokument», «Beilage» or «Bemerkung»
        #    element holds unrelated things under one name)
        #  * not flagged as a different datum by the naming layer (zuordnung)
        #  * for person/address data: the same judged party (subjekt); an
        #    unjudged party is never matched, only counted
        #  * a role named in the label («… des Ehegatten») or in the composite
        #    around it keeps data of different people apart — conservative:
        #    when unsure the units are counted apart, never together
        # CONTAINER / REG_STD / PARTY and datum_key() are module-level: the same
        # definition decides «same datum» here and in the Standard-Divergenzen
        for t in rows(conn, "SELECT id, katalog, bereich, gruppe, ord FROM themenkatalog ORDER BY katalog, ord"):
            sids = [sid for sid, L in th_by_svc.items() if any(x["id"] == t["id"] for x in L)]
            g = {"id": t["id"], "katalog": t["katalog"], "bereich": t["bereich"], "gruppe": t["gruppe"],
                 "services": sids, "n_services": len(sids)}
            if sids:
                el_svcs, el_label = {}, {}
                c = {k: 0 for k in ("units", "pflicht", "pflicht_teil", "reg", "reg_offen", "kein_std",
                                    "el_offen", "ungeprueft", "zuordnung", "container", "partei_offen",
                                    "sens", "beil", "fetch", "online", "sig", "forms")}
                dsts, modelliert, ohne_daten = set(), [], []
                for sid in sids:
                    sv = svc_by_id.get(sid) or {}
                    dsts.add(sv.get("dienststelle"))
                    fms = [fm for fm in forms_by_svc.get(sid, []) if fm.get("data_fields")]
                    (modelliert if fms else ohne_daten).append(sid)
                    for fm in fms:
                        c["forms"] += 1
                        c["beil"] += len(fm.get("beilagen") or [])
                        c["fetch"] += sum(1 for b in (fm.get("beilagen") or []) if b.get("fetchable"))
                        c["online"] += fm.get("submission_channel") == "online_formular"
                        c["sig"] += fm.get("signature_requirement") == "handschriftlich"
                        for d in fm["data_fields"]:
                            c["sens"] += bool(d.get("sensitive"))
                            subs = [x for x in (d.get("subfields") or []) if isinstance(x, dict)]
                            for u in (subs or [d]):
                                c["units"] += 1
                                if d.get("required"):
                                    c["pflicht_teil" if subs else "pflicht"] += 1
                                e = u.get("ech") or {}
                                b = u.get("begriff") or {}
                                if not e.get("element"):
                                    if e.get("standard"):
                                        c["el_offen"] += 1
                                    elif u.get("ech_status") == "kein_standard":
                                        c["kein_std"] += 1
                                    else:
                                        c["ungeprueft"] += 1
                                    continue
                                reg_std = e["standard"] in REG_STD
                                if b.get("pruefart") == "zuordnung":
                                    c["zuordnung"] += 1
                                    if reg_std:
                                        c["reg_offen"] += 1
                                    continue
                                c["reg"] += bool(u.get("register"))
                                if reg_std and not d.get("subjekt"):
                                    c["reg_offen"] += 1
                                if e["element"] in CONTAINER:
                                    c["container"] += 1
                                    continue
                                if reg_std and d.get("subjekt") in (None, "gemischt"):
                                    c["partei_offen"] += 1
                                    continue
                                lab = u.get("name") if subs else d["name"]
                                role_txt = (b.get("rolle") or "").strip() if b.get("klasse") == "rolle" else ""
                                role = role_txt.lower()
                                k = datum_key(d, u, subs)
                                if k is None:
                                    continue
                                party = k[4]
                                el_svcs.setdefault(k, set()).add(sid)
                                el_label.setdefault(k, (b.get("vorschlag") or lab)
                                                    + (f" ({role_txt})" if role_txt else "")
                                                    + (f" — {party.replace('|', ', ')}" if party and not role else ""))
                rep = sorted(((k, v) for k, v in el_svcs.items() if len(v) >= 2), key=lambda kv: -len(kv[1]))
                g.update({
                    "n_dienststellen": len(dsts - {None}), "n_formulare": c["forms"],
                    "services_modelliert": modelliert, "services_ohne_daten": ohne_daten,
                    "n_angaben": c["units"], "n_pflicht": c["pflicht"], "n_pflicht_teil": c["pflicht_teil"],
                    "n_vorbefuellbar": c["reg"], "n_vorbefuellbar_offen": c["reg_offen"],
                    "n_kein_standard": c["kein_std"], "n_element_offen": c["el_offen"], "n_ungeprueft": c["ungeprueft"],
                    "n_ohne_standard": c["kein_std"] + c["el_offen"] + c["ungeprueft"],
                    "n_zuordnung_offen": c["zuordnung"], "n_container": c["container"],
                    "n_partei_offen": c["partei_offen"],
                    "n_sensibel": c["sens"], "n_beilagen": c["beil"], "n_beilagen_beziehbar": c["fetch"],
                    "n_online": c["online"], "n_unterschrift": c["sig"],
                    "n_daten": len(el_svcs),
                    "wiederholt": [{"element": f"{k[0]}·{k[1]}", "label": el_label.get(k), "services": sorted(v)}
                                   for k, v in rep[:40]],
                    "n_wiederholt": len(rep),
                    # requests for a datum another service of the SAME group also asks
                    # for — an overlap across the offer; the services can be
                    # alternatives that no single person goes through together
                    "n_ueberschneidungen": sum(len(v) - 1 for _, v in rep),
                })
            themenkatalog.append(g)
    except Exception as ex:
        _layer_skipped("Lebenslagen", ex)

    # Bürgersicht: what the Datentresor holds about three synthetic people, seen
    # from THEIR side (Auskunft, Bekanntgaben, Einwilligungen, Löschdaten). Only
    # the persons with the most offices involved are exported, so the dashboard
    # stays small; every value is synthetic by construction of datentresor.db
    buergersicht = {"personen": [], "hinweis": None}
    dt_path = os.path.join(os.path.dirname(DB_PATH), "datentresor.db")
    if os.path.exists(dt_path):
        try:
            dt = sqlite3.connect(dt_path)
            dt.row_factory = sqlite3.Row
            meta = {r["k"]: r["v"] for r in dt.execute("SELECT k, v FROM meta")}
            buergersicht["hinweis"] = meta.get("hinweis")
            buergersicht["verschluesselung"] = meta.get("verschluesselung")
            for p in dt.execute(
                    "SELECT s.id, s.ahvn13, s.name, s.vorname, s.geburtsdatum, s.plz, s.ort, "
                    "COUNT(DISTINCT f.id) faelle, COUNT(DISTINCT f.dienststelle) dst "
                    "FROM subjekt s JOIN fall f ON f.subjekt_id=s.id "
                    "GROUP BY s.id ORDER BY dst DESC, faelle DESC LIMIT 3"):
                person = {k: p[k] for k in ("ahvn13", "name", "vorname", "geburtsdatum", "plz", "ort")}
                person["faelle"] = []
                for f in dt.execute("SELECT id, service_id, form_id, formular, dienststelle, "
                                    "eingereicht, abgeschlossen, entscheid FROM fall "
                                    "WHERE subjekt_id=? ORDER BY eingereicht", [p["id"]]):
                    fall = dict(f)
                    # newly collected in this Fall (encrypted values never leave the vault)
                    fall["neu"] = [dict(r) for r in dt.execute(
                        "SELECT attribut, ech_standard, ech_element, ech_datatype, "
                        "CASE WHEN verschluesselt THEN NULL ELSE wert END wert, verschluesselt, "
                        "sensitive, grundlage, einwilligung_id IS NOT NULL einwilligung, "
                        "loeschdatum, status FROM datenpunkt WHERE erhebungs_fall=? ORDER BY id", [f["id"]])]
                    # referenced from an earlier Fall instead of asked again (once-only)
                    fall["wiederverwendet"] = [dict(r) for r in dt.execute(
                        "SELECT d.attribut, d.erhoben_am, f2.formular herkunft, f2.dienststelle herkunft_dst "
                        "FROM datenpunkt_verwendung v JOIN datenpunkt d ON d.id=v.datenpunkt_id "
                        "JOIN fall f2 ON f2.id=d.erhebungs_fall "
                        "WHERE v.fall_id=? AND v.wiederverwendet=1 ORDER BY d.attribut", [f["id"]])]
                    fall["belege"] = [dict(r) for r in dt.execute(
                        "SELECT bezeichnung, art, halter, geprueft_am, geprueft_von, loeschdatum "
                        "FROM beleg WHERE fall_id=? ORDER BY id", [f["id"]])]
                    fall["bekanntgaben"] = [dict(r) for r in dt.execute(
                        "SELECT zeitpunkt, wer, zweck, grundlage FROM zugriff_log "
                        "WHERE fall_id=? AND art='bekanntgabe' ORDER BY zeitpunkt", [f["id"]])]
                    fall["lesezugriffe"] = dt.execute(
                        "SELECT COUNT(*) FROM zugriff_log WHERE fall_id=? AND art='lesen'", [f["id"]]).fetchone()[0]
                    person["faelle"].append(fall)
                person["einwilligungen"] = [dict(r) for r in dt.execute(
                    "SELECT e.gegenstand, e.erteilt_am, e.widerrufen_am, f.formular "
                    "FROM einwilligung e LEFT JOIN fall f ON f.id=e.fall_id "
                    "WHERE e.subjekt_id=? ORDER BY e.erteilt_am", [p["id"]])]
                # deletion calendar: how many datapoints fall due per year
                person["loeschkalender"] = [dict(r) for r in dt.execute(
                    "SELECT substr(loeschdatum,1,4) jahr, COUNT(*) n FROM datenpunkt "
                    "WHERE subjekt_id=? AND status='aktiv' GROUP BY 1 ORDER BY 1", [p["id"]])]
                person["statistik"] = dict(dt.execute(
                    "SELECT COUNT(*) datenpunkte, SUM(verschluesselt) verschluesselt, "
                    "SUM(einwilligung_id IS NOT NULL) mit_einwilligung, "
                    "SUM(grundlage_artikel IS NOT NULL) mit_artikel FROM datenpunkt WHERE subjekt_id=?",
                    [p["id"]]).fetchone())
                person["statistik"]["wiederverwendet"] = dt.execute(
                    "SELECT COUNT(*) FROM datenpunkt_verwendung v JOIN fall f ON f.id=v.fall_id "
                    "WHERE f.subjekt_id=? AND v.wiederverwendet=1", [p["id"]]).fetchone()[0]
                buergersicht["personen"].append(person)
            dt.close()
        except Exception as _ex:
            # the vault is optional (no file: no Bürgersicht); one that is there but
            # of an older shape is skipped loudly, anything else stops the export
            _layer_skipped('Bürgersicht (datentresor.db)', _ex, tables=DT_TABLES)
            buergersicht = {"personen": [], "hinweis": None}

    # ---- Handlungsbedarf per form: ONE computation for the board, the service
    # page, the dossiers and the CSV. Wording lives in scripts/labels.py.
    today = date.today().isoformat()
    for fm in forms:
        fm["handlungsbedarf"] = handlungsbedarf(fm, today)
        for it in fm["handlungsbedarf"]:
            it["stufe"] = LABELS.STUFE_OF_CAT[it["cat"]]
            it["ton"] = LABELS.TON_OF_ART[LABELS.TODO_BY[it["cat"]][3]]

    # ---- Dienststellen, headline figures, trend: computed once here ----------------
    dienststellen_uebersicht, kopfzahlen, verlauf = uebersichten(conn, services, forms, dienststellen, begriffe_stats)

    # ---- Datenstand: when was what last read (never only the build time) -------
    datenstand = {"build": None}
    try:
        datenstand["shep_harvest"] = (rows(conn, "SELECT MAX(harvested_at) m FROM shep_service")[0]["m"] or "")[:10] or None
        datenstand["dvsh_stand"] = (rows(conn, "SELECT MAX(dvsh_updated_at) m FROM dvsh_service")[0]["m"] or "")[:10] or None
        oc = rows(conn, "SELECT MAX(substr(checked_at,1,10)) d, COUNT(*) n, "
                        "SUM(next_check_due < date('now')) overdue, "
                        "SUM(substr(checked_at,1,10) = (SELECT MAX(substr(checked_at,1,10)) FROM form_check)) recent FROM form_check")[0]
        # the date most rows carry = the last FULL sweep; later dates are partial re-checks
        full = rows(conn, "SELECT substr(checked_at,1,10) d, COUNT(*) n FROM form_check "
                          "GROUP BY 1 ORDER BY n DESC LIMIT 1")
        datenstand["online_check"] = {"date": oc["d"], "full_date": full[0]["d"] if full else None,
                                      "n_checked": oc["n"], "n_recent": oc["recent"] or 0,
                                      "n_forms": len(forms), "n_overdue": oc["overdue"] or 0,
                                      "n_never": len(forms) - (oc["n"] or 0)}
        sw = rows(conn, "SELECT MAX(xsd_swept_at) m, COUNT(xsd_swept_at) n, COUNT(xsd_file) n_xsd FROM ech_standard")[0]
        datenstand["xsd_sweep"] = {"date": sw["m"], "n": sw["n"], "n_xsd": sw["n_xsd"]}
    except Exception as ex:
        _layer_skipped("Datenstand", ex)

    # ---- verification levels of the curated citations (for the header chip) -------
    zitate = {"verifiziert": 0, "quelle_pdf": 0, "unverifiziert": 0, "total": 0}
    for fm in forms:
        for d in fm.get("data_fields") or []:
            for b in d.get("legal_basis") or []:
                lc = b.get("last_checked") or ""
                zitate["total"] += 1
                if lc == "verified":
                    zitate["verifiziert"] += 1
                elif lc.startswith("Gesetze-PDF"):
                    zitate["quelle_pdf"] += 1
                else:
                    zitate["unverifiziert"] += 1

    # ---- shared sentences built from verified rules (never typed twice) -------------
    texte = {}
    try:
        refs = []
        for cref, art in (("SHR 174.100", "Art. 4"), ("SHR 172.301", "§ 6"), ("SHR 172.301", "§ 5"), ("SHR 172.301", "§ 7")):
            r = rows(conn, "SELECT dr.aspect FROM data_rule dr JOIN article a ON a.id=dr.article_id "
                           "JOIN law l ON l.id=a.law_id WHERE l.cantonal_ref=? AND a.article_no=? "
                           "AND dr.quote_verified=1 AND dr.aspect IN ('aufbewahrung','archivierung') LIMIT 1", cref, art)
            if r:
                refs.append([cref.replace("SHR ", ""), art, r[0]["aspect"]])
        texte["aufbewahrung_standard"] = {
            "text": ("Ohne eigene Frist im Fachgesetz gilt der Standard: Personendaten nicht länger aufbewahren, "
                     "als es zur Erreichung des Zwecks erforderlich ist (KDSG Art. 4); Akten bleiben in der "
                     "Registratur, solange die laufende Verwaltungstätigkeit sie braucht — Registraturperioden von "
                     "in der Regel zehn bis zwanzig Jahren (ArchivV § 6, § 5); danach sind sie dem Staatsarchiv "
                     "anzubieten, nicht Übernommenes wird vernichtet (ArchivV § 7)."),
            "refs": refs}
    except Exception as ex:
        _layer_skipped("Texte", ex)

    # every ingested article not at level 'verified' -> log file (not inlined;
    # thousands of rows, most of them cantonal articles read from the Gesetze PDF)
    todo = []
    for l in laws:
        for a in l["articles"]:
            if a["last_checked"] != "verified":
                todo.append((l["jurisdiction_level"], l["title"], l["sr_number"] or l["cantonal_ref"],
                             a["article_no"], a["heading"], a["last_checked"]))

    # one stamp: every surface and export built from this file repeats it
    now = datetime.now().isoformat(timespec="seconds")
    datenstand["build"] = now[:10]
    data = {
        "generated_at": now,
        # the levels as the ingest scripts set them (ingest_fed.py / ingest_bigcode.py
        # write 'verified', ingest_laws.py writes 'Gesetze-PDF SHR … (Stand …)')
        "verification_note": "Verifikationsstufen der Zitate (last_checked): 'verified' = Artikel des "
                             "Bundesrechts, beim Einlesen aus dem amtlichen Fedlex-Text gelesen "
                             "(Dashboard: «verifiziert»); 'Gesetze-PDF SHR … (Stand …)' = Artikel aus "
                             "dem amtlichen Gesetzes-PDF gelesen, für kantonales Recht aus dem "
                             "Schaffhauser Rechtsbuch (Dashboard: «Quelle SHR-PDF»); 'UNVERIFIED' = "
                             "ohne Quelle, nicht amtlich geprüft. Massgeblich ist die geprüfte "
                             "Feld-Schicht (forms[].data_fields); der Auto-Entwurf von 2026-06 "
                             "(form_field, field_mapping, requirement) ist stillgelegt und wird "
                             "nicht exportiert.",
        "datenstand": datenstand, "zitate": zitate, "labels": LABELS.as_export(), "texte": texte,
        "services": services, "laws": laws, "forms": forms,
        "esh_katalog": esh_katalog, "datenhandhabung": handhabung,
        "attribut_katalog": katalog,
        "dienststellen_uebersicht": dienststellen_uebersicht, "kopfzahlen": kopfzahlen, "verlauf": verlauf,
        "buergersicht": buergersicht, "ech_codelists": codelists,
        "begriffe": begriffe, "begriffe_stats": begriffe_stats, "themenkatalog": themenkatalog,
    }
    if SKIPPED_LAYERS:
        # a half-empty export says so itself (convention: skipped only when the table is missing)
        datenstand["uebersprungen"] = [f"{name} — Tabelle {table} fehlt" for name, table in SKIPPED_LAYERS]
    _summen_pruefen(data)
    return data, todo


def _wortwahl_pruefen(data):
    """«Datum» is a calendar date to readers. The databank's own naming and basis
    texts may say «Datum» only where quellen/wortwahl_datum.json confirms a date
    (scripts/apply_wortwahl.py applies the reviewed rewrites). A new text without
    a verdict stops the export; field definitions only warn, because they are
    almost always about real dates."""
    import apply_wortwahl as W
    _, behalten = W.lade()
    streng, def_ = set(), set()
    def fld(d):
        b = d.get("begriff") or {}
        streng.update([b.get("grund"), b.get("rolle"), d.get("basis_begruendung")])
        def_.add(d.get("definition"))
    for b in data.get("begriffe") or []:
        streng.add(b.get("begruendung"))
        for l in b.get("labels") or []:
            streng.update([l.get("grund"), l.get("rolle")])
    for f in data.get("forms") or []:
        for d in f.get("data_fields") or []:
            fld(d)
            for s in d.get("subfields") or []:
                fld(s)
        for b in (f.get("standard_divergenzen") or {}).get("bezeichnungen") or []:
            streng.add(b.get("grund"))
    offen = W.offen(streng, behalten)
    if offen:
        raise RuntimeError(f"{len(offen)} Begriffs-/Grundlagentext(e) sagen «Datum» ohne Prüfung — "
                           "in quellen/wortwahl_datum.json einordnen, dann scripts/apply_wortwahl.py: "
                           + " | ".join(t[:100] for t in offen[:5]))
    offen_def = W.offen(def_, behalten)
    if offen_def:
        print(f"  Hinweis: {len(offen_def)} Felddefinition(en) mit «Datum» noch ohne Prüfung "
              f"(quellen/wortwahl_datum.json), z. B. {offen_def[0][:90]!r}")


def main():
    import kennzahlen as KZ
    conn = connect(DB_PATH)
    data, todo = build(conn)            # layers (common._layer_skipped) and sums (_summen_pruefen)
    conn.close()
    _wortwahl_pruefen(data)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # a published file never carries a path of the author's machine
    assert_no_local_paths("data_export.json", text)
    # every gate has passed — only now anything is written
    with open(EXPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(text)
    KZ.save(VERLAUF_DOC)                # today's entry in verlauf.json
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(os.path.join(LOGS_DIR, "citation_todo.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"ARTICLES NOT AT LEVEL 'verified' ({len(todo)}) — status 'Gesetze-PDF …' = read from "
                 "the official PDF; any other status has no source yet\n" + "=" * 60 + "\n")
        for jur, title, num, art, head, lc in todo:
            fh.write(f"[{jur:9}] {title}  | Art. {art} ({head})  ref={num}  status={lc}\n")
    sz = os.path.getsize(EXPORT_PATH) / 1024
    print(f"exported {EXPORT_PATH}  ({sz:.0f} KB, generated_at {data['generated_at']})")
    print(f"  services={len(data['services'])} forms={len(data['forms'])} "
          f"not_verified_articles={len(todo)}")
    k = data["kopfzahlen"]
    print(f"  Summen geprüft: {sum(1 for v in k.values() if isinstance(v, dict) and 'teile' in v)} Kennzahlen mit Teilen, "
          f"{len(data['dienststellen_uebersicht'])} Dienststellen, {k['standard_ech']['von']} Datenpunkte — alles geht auf")
    if SKIPPED_LAYERS:
        # said again at the very end: one stderr line among the build's output is easy to miss
        sys.stdout.flush()
        print(f"ACHTUNG: {len(SKIPPED_LAYERS)} Schicht(en) fehlen in diesem Export, weil ihre Tabelle in "
              "citygov.db fehlt — die Seiten zeigen weniger, als die Databank sonst weiss: "
              + "; ".join(f"{name} (Tabelle {table})" for name, table in SKIPPED_LAYERS), file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as ex:          # a gate fired: one line instead of a traceback
        sys.exit(f"ABBRUCH export_json.py — nichts geschrieben: {ex}")
