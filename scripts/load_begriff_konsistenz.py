#!/usr/bin/env python3
"""Align proposed terms across elements that share an XML element name.

Where the same element name (email, amount, officialName …) carries different
proposals in different standards, a consistency pass decided per group whether
the elements mean the SAME datum (one shared term) or different things (keep).
Gates as everywhere: the shared term must occur verbatim-normalised in the
forms; element ids must belong to the group. The old proposal label of an
aligned element becomes a 'variante' of the shared term.

Decisions taken on top of the pass, each with its reason (kept here so they
stay visible and reviewable):
  * residencePermit -> «Bewilligungsart», not «Aufenthaltsbewilligung»: in
    Swiss law the latter is the B permit only, the element is the category
  * the only spellings in the forms are flawed -> kept, but provisional:
    addressCategory «adressart» (lower case), purchasePrice «Kaufpreis (Fr.)»
    (unit in the name)
  * eCH-0276 amount (id 7784) counts shares, it is no money amount: its
    «Betrag» is flagged provisional until the mapping is corrected

    python3 scripts/load_begriff_konsistenz.py <dir-with-out_0.json>
"""
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect, norm_label as norm
from validate_db import validate

OVERRIDE_TERM = {"residencePermit": "Bewilligungsart"}
VORBEHALT = {
    "addressCategory": "Die saubere Schreibweise «Adressart» kommt in keinem Formular vor; «adressart» ist der einzige vorhandene Begriff.",
    "purchasePrice": "«Kaufpreis» ohne Einheit kommt in keinem Formular vor; die Einheit gehört nicht in den Begriff.",
}
# eCH-0108 addressCategory has its own clean term («Domizilart»); a company's
# Domizil is no address category of a person — never align it (review 2026-09-25)
EXCLUDE_IDS = {1487}
VORBEHALT_ID = {7784: "Das Element zählt Anteile (ganze Zahl neben Nominalwert und Prozent), es ist kein Geldbetrag — Zuordnung prüfen."}



def main():
    if os.environ.get("BEGRIFFE_CHAIN") != "1":
        sys.exit("Dieser Schritt baut auf den vorherigen auf und darf nicht allein laufen — "
                 "bitte scripts/run_begriffe.py verwenden.")
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    # normalised term -> spelling in the forms; a capitalised occurrence wins
    # over a lowercase one (German labels start with a capital; a technical
    # key like «familienname» must not become the displayed term)
    corpus = {}
    for r in c.execute("SELECT name FROM data_field UNION SELECT name FROM data_subfield"):
        if r[0] and r[0].strip():
            k, v = norm(r[0]), r[0].strip()
            if k not in corpus or (corpus[k][:1].islower() and v[:1].isupper()):
                corpus[k] = v
    name_of = {r[0]: r[1] for r in c.execute(
        "SELECT v.ech_element_id, e.name FROM begriff_vorschlag v JOIN ech_element e ON e.id=v.ech_element_id")}
    term_of = {r[0]: r[1] for r in c.execute("SELECT ech_element_id, term FROM begriff_vorschlag")}
    n = rej = 0
    for u in json.load(open(os.path.join(src, "out_0.json"), encoding="utf-8")).get("urteile", []):
        if u.get("urteil") != "angleichen":
            continue
        group = u.get("elementname")
        term = OVERRIDE_TERM.get(group) or u.get("vorschlag")
        if norm(term) not in corpus:
            rej += 1; continue
        term = corpus[norm(term)] if group not in OVERRIDE_TERM else term
        for eid in u.get("element_ids") or []:
            if eid in EXCLUDE_IDS:
                continue
            if name_of.get(eid) != group:
                rej += 1; continue
            old = norm(term_of[eid])
            if old == norm(term):
                continue
            own = {r[0] for r in c.execute("SELECT label_norm FROM begriff_label WHERE ech_element_id=?", [eid])}
            c.execute("UPDATE begriff_label SET klasse='variante', grund=? WHERE ech_element_id=? AND label_norm=? AND klasse='vorschlag'",
                      [f"gleiches Datum wie in den anderen Standards — einheitlich «{term}»", eid, old])
            if norm(term) in own:
                c.execute("UPDATE begriff_label SET klasse='vorschlag', pruefart=NULL, grund=NULL WHERE ech_element_id=? AND label_norm=?",
                          [eid, norm(term)])
            c.execute("UPDATE begriff_vorschlag SET term=?, herkunft=?, pruefung=? WHERE ech_element_id=?",
                      [term, "eigen" if norm(term) in own else "korpus",
                       f"Einheitlich mit den anderen Elementen «{group}»: {(u.get('grund') or '')[:180]}", eid])
            n += 1
    # every proposal gets the capitalised spelling if the forms contain one
    cap = 0
    for eid, t in list(c.execute("SELECT ech_element_id, term FROM begriff_vorschlag")):
        best = corpus.get(norm(t))
        if best and best != t and t[:1].islower() and best[:1].isupper():
            c.execute("UPDATE begriff_vorschlag SET term=? WHERE ech_element_id=?", [best, eid])
            cap += 1
    for group, why in VORBEHALT.items():
        c.execute("UPDATE begriff_vorschlag SET vorbehalt=1, pruefung=? WHERE ech_element_id IN "
                  "(SELECT id FROM ech_element WHERE name=?) AND ech_element_id NOT IN (%s)"
                  % ",".join(map(str, EXCLUDE_IDS)), [why, group])
    for eid, why in VORBEHALT_ID.items():
        c.execute("UPDATE begriff_vorschlag SET vorbehalt=1, pruefung=? WHERE ech_element_id=?", [why, eid])
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Konsistenz: {n} Elemente angeglichen, {cap} Schreibweisen gross, {rej} REJECTED; Vorbehalt gesetzt für "
          f"{', '.join(VORBEHALT)} und Element {', '.join(map(str, VORBEHALT_ID))}")


if __name__ == "__main__":
    main()
