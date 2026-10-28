"""The files DVSH and SHEP offer per service, what the databank holds of them,
and what the latest harvests changed. Standard library only.

Computed once in export_json (services[].dokumente, services[].aenderungen and the
overview quellenabgleich); the dashboard, the dossiers and the LLM export read it.

A file is identified by its sha256: DVSH records it per document (documents[],
submissionEndpoint), SHEP names its asset files by it. Its state:
  erfasst          a Formular of the databank holds these bytes (form.file_hash)
  gleicher_inhalt  same content as a held Formular, other bytes (judged: gleiche_ausgabe)
  aeltere_ausgabe  an older edition than the Formular the databank holds
  begleitdokument  Merkblatt, Wegleitung, list, law text … (judged: kein_formular)
  offen            judged a Formular (new, newer edition, misplaced) but not taken over
  nicht_lesbar     could not be read
  ungeprueft       not judged yet (a file of a newer harvest)
The judgements come from dokument_urteil (load_dokument_urteile.py).
"""
import json

SHEP_BASE = "https://shep.meetfrida.agency"
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
            it["url"] = it["url"] or url

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
        for q in ("DVSH", "SHEP"):
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
