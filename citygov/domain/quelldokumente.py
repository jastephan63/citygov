"""The files DVSH, SHEP and the live portal offer per service, what the databank
holds of them, what the latest harvests changed, and whether each Formular is live
on services.sh.ch. Standard library only.

Computed once in export_json (services[].dokumente, services[].aenderungen,
services[].portal, forms[].live and the overview quellenabgleich, all in
data_export.json); the dashboard reads it.

A file is identified by its sha256: DVSH records it per document (documents[],
submissionEndpoint), SHEP and the live portal name their asset files by it, and the
files on sh.ch the live portal links were fetched with its harvest. Its state:
  erfasst          a Formular of the databank holds these bytes (form.file_hash)
  gleicher_inhalt  same content as a held Formular, other bytes (judged: gleiche_ausgabe)
  aeltere_ausgabe  an older edition than the Formular the databank holds
  begleitdokument  Merkblatt, Wegleitung, list, law text … (judged: kein_formular)
  offen            judged a Formular (new, newer edition, misplaced) but not taken over
  nicht_lesbar     could not be read
  ungeprueft       not judged yet (a file of a newer harvest)
The judgements come from dokument_urteil (load_dokument_urteile.py).

A Formular on the live portal (forms[].live.stand):
  datei_live     the portal offers these very bytes (form.file_hash)
  inhalt_live    it offers a file of the same content (judged: gleiche_ausgabe)
  aeltere_live   it offers an older edition than the databank holds (comes before online_live:
                 the Dienststelle replaces it there)
  neuere_live    it offers a newer edition than the databank holds
  online_live    its button «Online erledigen» leads to an online form that is this
                 Formular (reviewed: online_formular.gegenstueck_form_id, load_online.py)
  service_live   the service has a live page, but this Formular is not offered there
  nicht_live     the service has no page on the live portal
"""
import json

SHEP_BASE = "https://shep.meetfrida.agency"
PORTAL_BASE = "https://services.sh.ch"
# the columns of a portal page whose change is compared (harvest log, live vs. SHEP): the
# sections the template marks unambiguously (teaser and link labels were re-parsed in
# 2026-10 and are not compared)
SEITEN_VERGLEICH = ["title", "kurzbeschreibung", "voraussetzungen", "unterlagen", "ablauf",
                    "formular_url", "kontakt_einheit", "kontakt_adresse", "kontakt_email"]
STAENDE = ["erfasst", "gleicher_inhalt", "aeltere_ausgabe", "begleitdokument", "offen", "nicht_lesbar", "ungeprueft"]


def _liste(v):
    for _ in range(3):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                return []
    if isinstance(v, dict):
        return [v]
    return [x for x in (v or []) if isinstance(x, dict)]


def _txt(s):
    """DVSH stores some file names as UTF-8 read as Latin-1 («WÃ¤rmepumpen»): repaired
    for display when the repair decodes cleanly, else left as stored."""
    if isinstance(s, str) and ("Ã" in s or "â€" in s):
        for enc in ("latin-1", "cp1252"):
            try:
                return s.encode(enc).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    return s


def _zeilen(conn, table):
    cur = conn.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _stand(sha, held, urteile):
    if sha in held:
        return "erfasst", held[sha]
    u = urteile.get(sha)
    if not u:
        return "ungeprueft", None
    return {"gleiche_ausgabe": "gleicher_inhalt", "aeltere_ausgabe": "aeltere_ausgabe",
            "kein_formular": "begleitdokument", "nicht_lesbar": "nicht_lesbar"}.get(u["urteil"], "offen"), u["form_id"]


def berechne(conn, services, dvsh_rows_by_service, shep_by_service):
    """Sets s['dokumente'] and s['aenderungen'] on every service; returns the overview."""
    held = {r[0]: r[1] for r in conn.execute("SELECT file_hash, id FROM form WHERE file_hash IS NOT NULL")}
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    portal_by_service = {}
    for p in (_zeilen(conn, "portal_service") if "portal_service" in have else []):
        if p["service_id"] is not None:
            portal_by_service.setdefault(p["service_id"], []).append(p)
    # the documents the targets of «Online erledigen» link (migrationsamt.sh.ch pages)
    online_by_service = {}
    for d in (_zeilen(conn, "online_datei") if "online_datei" in have else []):
        if d["service_id"] is not None and d["herkunft"] == "verlinkt":
            online_by_service.setdefault(d["service_id"], []).append(d)
    urteile = {}
    if "dokument_urteil" in have:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(dokument_urteil)")]
        urteile = {r[0]: dict(zip(cols, r)) for r in conn.execute(f"SELECT {', '.join(cols)} FROM dokument_urteil")}
    alle = {}
    for s in services:
        items = {}

        def add(sha, quelle, titel, datei, rolle, url):
            if not sha:
                return
            it = items.setdefault(sha, {"sha256": sha, "titel": None, "datei": None, "quellen": [],
                                        "rolle": rolle, "url": None})
            if quelle not in it["quellen"]:
                it["quellen"].append(quelle)
            it["titel"] = it["titel"] or _txt(titel)
            it["datei"] = it["datei"] or _txt(datei)
            if rolle == "einreichung":
                it["rolle"] = "einreichung"
            # the link a reader opens: the live portal's when it offers the file
            it["url"] = url if quelle == "Live" and url else it["url"] or url

        for g in dvsh_rows_by_service.get(s["id"], []):
            src = {x.get("id"): x for x in _liste(g.get("sources"))}
            for d in _liste(g.get("documents")):
                u = (src.get(d.get("source_id")) or {}).get("url")
                add(d.get("sha256"), "DVSH", d.get("titel"), d.get("datei"),
                    "einreichung" if d.get("rolle") == "endpunkt" else "begleitend",
                    u if u and u.startswith("https://") and "sh.ch" in u else None)
            for e in _liste(g.get("submission_endpoint")):
                u = (src.get(e.get("source_id")) or {}).get("url")
                add(e.get("sha256"), "DVSH", e.get("titel"), e.get("datei"), "einreichung",
                    u if u and u.startswith("https://") and "sh.ch" in u else None)
        sp = shep_by_service.get(s["id"])
        for d in _liste((sp or {}).get("dokumente")):
            add(d.get("sha256"), "SHEP", d.get("label"), None,
                "einreichung" if (d.get("label") or "").strip() == "Formular" else "begleitend",
                SHEP_BASE + d["url"] if (d.get("url") or "").startswith("/api/catalog/assets/") else None)
        for sp in portal_by_service.get(s["id"], []):
            for d in _liste(sp.get("dokumente")):
                add(d.get("sha256"), "Live", d.get("label"), None,
                    "einreichung" if (d.get("label") or "").strip() == "Formular" else "begleitend",
                    PORTAL_BASE + d["url"] if (d.get("url") or "").startswith("/api/catalog/assets/") else None)
            # the sh.ch files the page links under «Weiterführende Informationen»
            for d in _liste(sp.get("datei_links")):
                add(d.get("sha256"), "Live", d.get("label"), d.get("dateiname"), "begleitend", d.get("url"))
        for d in online_by_service.get(s["id"], []):
            add(d["sha256"], "Online", d.get("label"), d.get("dateiname"), "begleitend", d.get("url"))
        out = []
        for sha, it in items.items():
            stand, fid = _stand(sha, held, urteile)
            u = urteile.get(sha) or {}
            it.update(stand=stand, form_id=fid, art=u.get("art") or ("formular" if stand == "erfasst" else None),
                      titel_gedruckt=u.get("titel"), zweitgeprueft=bool(u.get("zweitgeprueft")))
            if it["titel"] is None:
                it["titel"] = u.get("titel") or it["datei"] or sha[:12]
            out.append(it)
            alle.setdefault(sha, stand)
        out.sort(key=lambda x: (x["rolle"] != "einreichung", STAENDE.index(x["stand"]), (x["titel"] or "").lower()))
        s["dokumente"] = out

    # the latest harvest of each source and what it changed
    abgleich = {"dokumente": {k: 0 for k in STAENDE}, "n_dokumente": len(alle), "quellen": {}}
    for st in alle.values():
        abgleich["dokumente"][st] += 1
    aend_by_service = {}
    if "quellen_abzug" in have:
        for q in ("DVSH", "SHEP", "Portal"):
            ab = conn.execute("SELECT datum, datei, anzahl FROM quellen_abzug WHERE quelle=? ORDER BY datum DESC LIMIT 2",
                              [q]).fetchall()
            if not ab:
                continue
            datum = ab[0][0]
            rows = conn.execute("SELECT schluessel, service_id, titel, art, felder, vorher FROM quellen_aenderung "
                                "WHERE quelle=? AND abzug=? ORDER BY art, titel", [q, datum]).fetchall() \
                if "quellen_aenderung" in have else []
            liste = []
            for k, sid, titel, art, felder, vorher in rows:
                e = {"quelle": q, "schluessel": k, "service_id": sid, "titel": titel, "art": art,
                     "felder": json.loads(felder) if felder else []}
                liste.append(e)
                if sid is not None:
                    aend_by_service.setdefault(sid, []).append({"quelle": q, "art": art, "felder": e["felder"],
                                                                "abzug": datum, "vorher": vorher})
            abgleich["quellen"][q] = {
                "abzug": datum, "datei": ab[0][1], "anzahl": ab[0][2],
                "vorher": rows[0][5] if rows else (ab[1][0] if len(ab) > 1 else None),
                "vorher_anzahl": ab[1][2] if len(ab) > 1 else None,
                "n": {a: sum(1 for e in liste if e["art"] == a) for a in ("neu", "entfernt", "geaendert")},
                "aenderungen": liste}
    ids = {s["id"] for s in services}
    for s in services:
        s["aenderungen"] = aend_by_service.get(s["id"], [])
    # every DVSH service and SHEP page of the harvest has its service row
    abgleich["dvsh_ohne_service"] = conn.execute("SELECT COUNT(*) FROM dvsh_service WHERE service_id IS NULL").fetchone()[0] \
        if "dvsh_service" in have else None
    abgleich["shep_ohne_service"] = conn.execute("SELECT COUNT(*) FROM shep_service WHERE service_id IS NULL").fetchone()[0] \
        if "shep_service" in have else None
    abgleich["dvsh_services"] = conn.execute("SELECT COUNT(*) FROM dvsh_service").fetchone()[0] if "dvsh_service" in have else 0
    abgleich["shep_seiten"] = conn.execute("SELECT COUNT(*) FROM shep_service").fetchone()[0] if "shep_service" in have else 0
    abgleich["entfernte_ohne_zeile"] = sum(1 for q in abgleich["quellen"].values() for e in q["aenderungen"]
                                           if e["art"] == "entfernt" and e["service_id"] not in ids)
    return abgleich


LIVE_STAENDE = ["datei_live", "inhalt_live", "aeltere_live", "neuere_live", "online_live", "service_live", "nicht_live"]
# a judged file of the portal that is an edition of a Formular -> its live state
_URTEIL_LIVE = {"gleiche_ausgabe": "inhalt_live", "neue_ausgabe": "neuere_live", "aeltere_ausgabe": "aeltere_live"}


def live(conn, services, forms):
    """Is each Formular on the live portal services.sh.ch? Sets fm['live'] on every form
    and s['portal'] on every service (None without a live page); returns
    quellenabgleich['portal'] (None when the live portal was never harvested)."""
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    portal_rows = _zeilen(conn, "portal_service") if "portal_service" in have else []
    shep_rows = _zeilen(conn, "shep_service") if "shep_service" in have else []
    if not portal_rows:
        for fm in forms:
            fm["live"] = None
        for s in services:
            s["portal"] = s["online"] = None
        return None
    file_hash = {r[0]: r[1] for r in conn.execute("SELECT id, file_hash FROM form")}
    held = set(file_hash.values())
    urteile = {r[0]: (r[1], r[2]) for r in conn.execute("SELECT sha256, urteil, form_id FROM dokument_urteil")} \
        if "dokument_urteil" in have else {}
    seite = lambda slug: f"{PORTAL_BASE}/de/services/{slug}"
    # every file of the portal: where it is offered and how (button / list / link to sh.ch)
    angebot = {}
    pages_by_service = {}
    for p in portal_rows:
        if p.get("service_id") is not None:
            pages_by_service.setdefault(p["service_id"], []).append(p)
        for d in _liste(p.get("dokumente")):
            if d.get("sha256"):
                angebot.setdefault(d["sha256"], []).append(
                    {"slug": p["slug"], "seite": seite(p["slug"]), "label": d.get("label"),
                     "datei": PORTAL_BASE + d["url"] if (d.get("url") or "").startswith("/") else d.get("url"),
                     "wie": "Schaltfläche" if (d.get("label") or "").strip() == "Formular" else "Dokumentliste"})
        for d in _liste(p.get("datei_links")):
            if d.get("sha256"):
                angebot.setdefault(d["sha256"], []).append(
                    {"slug": p["slug"], "seite": seite(p["slug"]), "label": d.get("label"), "datei": d.get("url"),
                     "wie": "Link auf sh.ch"})
    ausgabe = {}            # form_id -> [(live state, file offers)] from the judged editions
    for sha, wo in angebot.items():
        urt, fid = urteile.get(sha, (None, None))
        if fid is not None and urt in _URTEIL_LIVE and file_hash.get(fid) != sha:
            ausgabe.setdefault(fid, []).append((_URTEIL_LIVE[urt], wo))
    # the service's live page(s): the action buttons, verbatim
    for s in services:
        P = pages_by_service.get(s["id"], [])
        s["portal"] = [{"slug": p["slug"], "url": seite(p["slug"]), "titel": p.get("title"),
                        "aktualisiert": p.get("updated"), "zuordnung": p.get("zuordnung"),
                        "aktionen": [a for a in _liste(p.get("aktionen"))]} for p in P] or None
    # the online forms behind «Online erledigen» (load_online.py) and the Formular each one is
    of_rows = _zeilen(conn, "online_formular") if "online_formular" in have else []
    of_seiten = {}
    for r in (_zeilen(conn, "online_formular_seite") if "online_formular_seite" in have else []):
        of_seiten.setdefault(r["formular_id"], []).append(r)
    online_by_form, online_by_service = {}, {}
    for o in of_rows:
        S = of_seiten.get(o["id"], [])
        e = {"id": o["id"], "name": o["name"], "system": o["system"], "start_url": o["start_url"],
             "zugang": o["zugang"], "schritte": _liste_s(o["schritte"]), "n_felder_sichtbar": o["n_felder_sichtbar"],
             "gegenstueck_art": o["gegenstueck_art"], "gegenstueck_form_id": o["gegenstueck_form_id"],
             "gegenstueck_sha256": o["gegenstueck_sha256"], "beleg": o["beleg"],
             "seiten": [{"slug": r["slug"], "seite": seite(r["slug"]), "via": r["via"]} for r in S]}
        for r in S:
            if r["service_id"] is not None:
                online_by_service.setdefault(r["service_id"], []).append(e)
        if o["gegenstueck_form_id"] is not None and S:
            online_by_form.setdefault(o["gegenstueck_form_id"], []).append(
                {"slug": S[0]["slug"], "seite": seite(S[0]["slug"]), "label": o["name"], "datei": o["start_url"],
                 "wie": "Online-Formular"})
    ziele = _zeilen(conn, "online_ziel") if "online_ziel" in have else []
    ziel_by_service = {}
    for z in ziele:
        ziel_by_service.setdefault(z["service_id"], []).append(
            {"slug": z["slug"], "url": z["url"], "art": z["art"], "befund": z["befund"]})
    for s in services:
        s["online"] = {"ziele": ziel_by_service.get(s["id"], []), "formulare": online_by_service.get(s["id"], [])} \
            if s["id"] in ziel_by_service or s["id"] in online_by_service else None
    n = {k: 0 for k in LIVE_STAENDE}
    for fm in forms:
        sha = file_hash.get(fm["id"])
        if sha and sha in angebot:
            stand, wo = "datei_live", angebot[sha]
        elif fm["id"] in ausgabe:
            # another edition on the portal comes first: an older one is the Dienststelle's to
            # replace there, even when the online form is live too
            stand, wo = min(ausgabe[fm["id"]], key=lambda x: LIVE_STAENDE.index(x[0]))
            wo = wo + online_by_form.get(fm["id"], [])
        elif fm["id"] in online_by_form:
            stand, wo = "online_live", online_by_form[fm["id"]]
        elif fm.get("service_id") in pages_by_service:
            stand, wo = "service_live", []
        else:
            stand, wo = "nicht_live", []
        n[stand] += 1
        fm["live"] = {"stand": stand, "angebot": wo}
    # the live portal against the SHEP staging pages of the last harvest
    shep = {r["slug"]: r for r in shep_rows}
    port = {p["slug"]: p for p in portal_rows}
    geaendert = []
    for slug, p in sorted(port.items()):
        r = shep.get(slug)
        if not r:
            continue
        felder = [k for k in SEITEN_VERGLEICH if (p.get(k) or None) != (r.get(k) or None)]
        if sorted(d.get("sha256") or "" for d in _liste(p.get("dokumente"))) != \
                sorted(d.get("sha256") or "" for d in _liste(r.get("dokumente"))):
            felder.append("dokumente")
        if felder:
            geaendert.append({"slug": slug, "service_id": p.get("service_id"), "titel": p.get("title"), "felder": felder})
    umbenannt = {p["zuordnung"].split("vorher ", 1)[1]: slug for slug, p in port.items()
                 if (p.get("zuordnung") or "").startswith("umbenannt, vorher ")}
    vs = {"abzug_shep": max((r.get("harvested_at") or "" for r in shep_rows), default=None) or None,
          "umbenannt": [{"vorher": a, "live": b, "service_id": port[b].get("service_id"), "titel": port[b].get("title")}
                        for a, b in sorted(umbenannt.items())],
          "nur_live": [{"slug": k, "service_id": port[k].get("service_id"), "titel": port[k].get("title")}
                       for k in sorted(set(port) - set(shep) - set(umbenannt.values()))],
          "nur_shep": [{"slug": k, "service_id": shep[k].get("service_id"), "titel": shep[k].get("title")}
                       for k in sorted(set(shep) - set(port) - set(umbenannt))],
          "geaendert": geaendert}
    # what a reader can see on the portal that does not fit: a link named «Formular»
    # that leads to a file judged not to be one; a page without any action button
    auff = []
    for p in portal_rows:
        for d in _liste(p.get("datei_links")):
            u = urteile.get(d.get("sha256") or "")
            if "formular" in (d.get("label") or "").lower() and u and u[0] == "kein_formular" \
                    and d.get("sha256") not in held:
                auff.append({"slug": p["slug"], "seite": seite(p["slug"]), "service_id": p.get("service_id"),
                             "art": "link_kein_formular", "label": d.get("label"), "url": d.get("url"),
                             "dateiname": d.get("dateiname")})
        if not _liste(p.get("aktionen")):
            auff.append({"slug": p["slug"], "seite": seite(p["slug"]), "service_id": p.get("service_id"),
                         "art": "ohne_aktion", "label": None, "url": None, "dateiname": None})
    aktionen = {}
    for p in portal_rows:
        for a in {a.get("art") for a in _liste(p.get("aktionen"))}:
            aktionen[a] = aktionen.get(a, 0) + 1
    files_live = {sha for sha in angebot}
    return {"abzug": max(p.get("harvested_at") or "" for p in portal_rows) or None,
            "basis": PORTAL_BASE, "seiten": len(portal_rows),
            "zugeordnet": sum(1 for p in portal_rows if p.get("service_id") is not None),
            "services_live": sum(1 for s in services if s.get("portal")),
            "formulare": n, "n_formulare": len(forms),
            "dateien": len(files_live), "dateien_formular": len(files_live & held),
            "aktionen": dict(sorted(aktionen.items(), key=lambda x: -x[1])),
            "vs_shep": vs, "auffaelligkeiten": auff,
            "online": {"ziele": len(ziele), "ziel_art": _zaehle(z["art"] for z in ziele),
                       "formulare": len(of_rows), "gegenstueck": _zaehle(o["gegenstueck_art"] for o in of_rows),
                       "zugang": _zaehle(o["zugang"] for o in of_rows),
                       "defekt": [{"slug": z["slug"], "seite": seite(z["slug"]), "service_id": z["service_id"],
                                   "url": z["url"], "befund": z["befund"]} for z in ziele if z["art"] == "defekt"]}
            if ziele else None}


def _liste_s(v):
    try:
        v = json.loads(v) if isinstance(v, str) else v
    except Exception:
        return []
    return [x for x in (v or []) if isinstance(x, str)]


def _zaehle(werte):
    out = {}
    for w in werte:
        out[w] = out.get(w, 0) + 1
    return dict(sorted(out.items(), key=lambda x: -x[1]))


def pruefen(services, abgleich):
    """The parts add up: the states sum to the distinct files; every service's list
    is counted in the overview. Returns a list of error strings."""
    err = []
    if sum(abgleich["dokumente"].values()) != abgleich["n_dokumente"]:
        err.append("quelldokumente: die Stände ergeben nicht die Zahl der Dateien")
    seen = {d["sha256"] for s in services for d in s.get("dokumente", [])}
    if len(seen) != abgleich["n_dokumente"]:
        err.append(f"quelldokumente: {len(seen)} Dateien auf den Service-Seiten, {abgleich['n_dokumente']} in der Übersicht")
    for q in abgleich["quellen"].values():
        if sum(q["n"].values()) != len(q["aenderungen"]):
            err.append("quelldokumente: die Änderungen ergeben nicht ihre Liste")
    return err


def pruefen_live(forms, portal):
    """Every Formular has exactly one live state, and the states sum to the Formulare."""
    if not portal:
        return []
    err = []
    if sum(portal["formulare"].values()) != portal["n_formulare"] or portal["n_formulare"] != len(forms):
        err.append("quelldokumente: die Live-Stände ergeben nicht die Zahl der Formulare")
    ist = {k: 0 for k in LIVE_STAENDE}
    for fm in forms:
        st = (fm.get("live") or {}).get("stand")
        if st not in ist:
            err.append(f"quelldokumente: Formular {fm['id']} ohne Live-Stand"); continue
        ist[st] += 1
    if ist != portal["formulare"]:
        err.append(f"quelldokumente: Live-Stände der Formulare {ist} statt {portal['formulare']}")
    o = portal.get("online")
    if o and (sum(o["gegenstueck"].values()) != o["formulare"] or sum(o["zugang"].values()) != o["formulare"]
              or sum(o["ziel_art"].values()) != o["ziele"]):
        err.append("quelldokumente: die Online-Formulare und -Ziele ergeben nicht ihre Zahl")
    return err
