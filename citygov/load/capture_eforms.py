#!/usr/bin/env python3
"""Open the eForms behind the live portal's «Online erledigen» buttons READ-ONLY and save what a
visitor sees, for scripts/load_online.py. Owner rule (2026-11-03): «it is important we do not
actually submit any of these forms online» — this tool never types, ticks, uploads or sends.

    python3 scripts/capture_eforms.py ziele   <harvest-dir>          # -> <harvest-dir>/afs_ziele.json
    python3 scripts/capture_eforms.py abrufen <harvest-dir> [<folder> ...]  # -> <harvest-dir>/eforms/<folder>/

<harvest-dir> is ../SHEP/live-<date>/online; <folder> is a form's id in afs_ziele.json with «/»
written «__» (BuA__BuA_RzW for BuA/BuA_RzW). «ziele» reads ziele.json (one entry per live page:
slug, service_id, url of «Online erledigen») and migrationsamt_links.json (slug -> [[url, text]]
of the migrationsamt.sh.ch pages a button leads to) and collects every eforms.sh.ch form
(aforms2web AFS) with its canonical start URL — a stale session link is reduced to its original
request («wfjs_orig_req»). «abrufen» opens each form like a browser: the start page, the
JavaScript-detection redirect («data-yesurl»), and — ONLY where the first page shows no data
control at all — one «Weiter» with nothing but the page's own hidden fields. Each step is saved as
schritt<N>.html with meta.json (URL without the transaction id, number of visible controls);
eforms/capture_log.json lists every form of the run (a run limited to some folders rewrites it
with those alone). One request per second; a later page that asks for input
is never reached. What a form IS (its name, the Formular it matches) is judged afterwards from the
saved pages only (quellen/dokumente/online_<date>.json).
"""
import json, os, re, sys, time, html, uuid, urllib.request, urllib.parse, http.cookiejar

UA = "Mozilla/5.0 (citygov read-only check)"


def canon(u):
    u = html.unescape(u)
    q = urllib.parse.urlparse(u)
    qs = urllib.parse.parse_qs(q.query)
    if "wfjs_orig_req" in qs:
        orig = urllib.parse.unquote(qs["wfjs_orig_req"][0])
        oq = urllib.parse.parse_qs(urllib.parse.urlparse(orig).query)
    else:
        oq = qs
    mand = q.path.strip("/").split("/")[0]
    if "generalid" in oq:
        key, val = "generalid", oq["generalid"][0]
    elif "id" in oq:
        key, val = "id", oq["id"][0].rstrip("&")
    else:
        key, val = None, None
    if not val:
        return None
    if q.path.endswith("/app/portal"):
        start = f"https://eforms.sh.ch/{mand}/app/portal?event=view&generalid={val}" if key == "generalid" else None
    else:
        start = f"https://eforms.sh.ch/{mand}/start.do?{key}={val}"
    return {"mandant": mand, "schluessel": key, "kennung": val, "start": start}


def ziele(d):
    Z = json.load(open(os.path.join(d, "ziele.json"), encoding="utf-8"))
    M = json.load(open(os.path.join(d, "migrationsamt_links.json"), encoding="utf-8"))
    out = {}

    def add(u, slug, service_id, via):
        c = canon(u)
        if not c or not c["start"]:
            print("UNKLAR", slug, u); return
        k = f'{c["mandant"]}/{c["kennung"]}'
        z = out.setdefault(k, {**c, "id": k, "fundstellen": []})
        z["fundstellen"].append({"slug": slug, "service_id": service_id, "via": via, "url": u})

    by_slug = {z["slug"]: z for z in Z}
    for z in Z:
        if "eforms.sh.ch" in z["url"]:
            add(z["url"], z["slug"], z["service_id"], "Schaltfläche")
    for slug, links in M.items():
        for u, _t in links:
            if "eforms.sh.ch" in u:
                add(u, slug, by_slug[slug]["service_id"], "migrationsamt.sh.ch")
    json.dump(sorted(out.values(), key=lambda x: x["id"]), open(os.path.join(d, "afs_ziele.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(len(out), "AFS-Formulare")


def opener():
    cj = http.cookiejar.CookieJar()
    o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    o.addheaders = [("User-Agent", UA), ("Accept-Language", "de-CH,de;q=0.9")]
    return o


def get(o, url):
    time.sleep(1.0)
    r = o.open(url, timeout=40)
    return r.geturl(), r.read().decode("utf-8", "replace")


def post_weiter(o, url, fields):
    """The one «Weiter» of a page without any data control: only the page's hidden fields."""
    time.sleep(1.0)
    b = "----citygov" + uuid.uuid4().hex
    body = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields) \
        + f"--{b}--\r\n".encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    r = o.open(req, timeout=40)
    return r.geturl(), r.read().decode("utf-8", "replace")


def controls(p):
    """Visible data controls (not hidden, not buttons, not the XML upload of «Daten laden»)."""
    n = 0
    for m in re.finditer(r"<(input|select|textarea)\b([^>]*)>", p):
        a = m.group(2)
        t = (re.search(r'type="([^"]+)"', a) or [None, "text"])[1] if m.group(1) == "input" else m.group(1)
        name = (re.search(r'name="([^"]+)"', a) or [None, ""])[1]
        if t in ("hidden", "submit", "button", "image") or name in ("xml", "defaultAction"):
            continue
        n += 1
    return n


def abrufen(d, only):
    OUT = os.path.join(d, "eforms")
    Z = json.load(open(os.path.join(d, "afs_ziele.json"), encoding="utf-8"))
    log = []
    for z in Z:
        key = z["id"].replace("/", "__")
        if only and key not in only:
            continue
        dd = os.path.join(OUT, key); os.makedirs(dd, exist_ok=True)
        o = opener(); rec = {"id": z["id"], "start": z["start"], "schritte": []}
        try:
            url, p = get(o, z["start"])
            m = re.search(r'data-yesurl="([^"]+)"', p)
            if m:
                url, p = get(o, html.unescape(m.group(1)))
            open(os.path.join(dd, "schritt1.html"), "w", encoding="utf-8").write(p)
            rec["schritte"].append({"datei": "schritt1.html", "url": re.sub(r"txid=[0-9a-f]+", "txid=…", url), "felder": controls(p)})
            f = re.search(r'<form\b[^>]*action="([^"]+)"[^>]*>', p)
            nxt = re.search(r'<button name="(next\$[^"]+)"[^>]*title="Weiter auf nächste Seite"', p)
            if f and nxt and controls(p) == 0:
                fields = [(k, html.unescape(v)) for k, v in re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', p)]
                fields.append((html.unescape(nxt.group(1)), ""))
                url2, p2 = post_weiter(o, urllib.parse.urljoin(url, html.unescape(f.group(1))), fields)
                open(os.path.join(dd, "schritt2.html"), "w", encoding="utf-8").write(p2)
                rec["schritte"].append({"datei": "schritt2.html", "url": re.sub(r"txid=[0-9a-f]+", "txid=…", url2), "felder": controls(p2)})
            rec["ok"] = True
        except Exception as ex:
            rec["ok"] = False; rec["fehler"] = repr(ex)[:300]
        json.dump(rec, open(os.path.join(dd, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log.append(rec)
        print(z["id"], "ok" if rec["ok"] else rec.get("fehler"), [s["felder"] for s in rec["schritte"]], flush=True)
    json.dump(log, open(os.path.join(OUT, "capture_log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("ziele", "abrufen"):
        print(__doc__); sys.exit(2)
    if a[0] == "ziele":
        ziele(a[1])
    else:
        abrufen(a[1], set(a[2:]))


if __name__ == "__main__":
    main()
