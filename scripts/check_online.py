#!/usr/bin/env python3
"""Currency sweep: is every Formular in the databank still online, and is our
copy the current edition?

Per form: search the sh.ch CMS full-text API for the form's filename/title,
pull the matching content pages' file lists (uuid + originalname), download the
best candidate and byte-compare against our copy.

  aktuell        online file found, byte-identical to ours
  aktualisiert   same (or year-shifted) name online, DIFFERENT content — the
                 form was revised; candidate saved next to results
  nicht_gefunden no online trace via CMS search (tail goes to websearch agents)

Read-only towards the databank; results land in <out>/results.json.

    python3 scripts/check_online.py <out-dir> [--limit N]
"""
import hashlib, json, os, re, subprocess, sys, time, unicodedata
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import DB_PATH, connect

BASE = "https://sh.ch"
UUID = re.compile(r"get/file/([0-9a-fA-F-]{36})")
# results page carries content ids as HTML attributes (contentid="1674680"),
# not JSON — the JSON-style pattern matched nothing and the sweep found nothing
CID = re.compile(r'contentid="(\d+)"')


def nf(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s)


def strip_year(s):
    return re.sub(r"(19|20)\d{2}", "", nf(s))


def curl(url, out=None, t=45):
    cmd = ["curl", "-sS", "--compressed", "--max-time", str(t)]
    if out:
        cmd += ["-o", out]
    try:
        r = subprocess.run(cmd + [url], capture_output=True, timeout=t + 15)
        if out:
            return os.path.exists(out) and os.path.getsize(out) > 200
        return (r.stdout or b"").decode("utf-8", "replace")
    except Exception:
        return "" if out is None else False


def terms(fname, title):
    base = re.sub(r"[_\-+.]+", " ", os.path.splitext(fname)[0])
    base = re.sub(r"\b(19|20)\d{2}\b|\bp\b|\bdt\b|\bde\b|\bdef\b", " ", base, flags=re.I)
    words = sorted(re.findall(r"[A-Za-zÄÖÜäöüß]{5,}", base), key=len, reverse=True)
    out = []
    if words:
        out.append(words[0])
    if len(words) >= 2:
        out.append(" ".join(words[:2]))
    tw = sorted(re.findall(r"[A-Za-zÄÖÜäöüß]{6,}", title or ""), key=len, reverse=True)
    if tw:
        out.append(tw[0] if len(tw) < 2 else " ".join(tw[:2]))
    seen, res = set(), []
    for t_ in out:
        if t_.lower() not in seen:
            seen.add(t_.lower()); res.append(t_)
    return res[:3]


def content_files(cid):
    """(uuid, originalname) pairs of one CMS content page."""
    raw = curl(f"{BASE}/CMS/content?contentid={cid}&mode=json&language=DE")
    pairs = []
    for m in re.finditer(r'"originalname\\?"\s*:\s*\\?"((?:[^"\\]|\\.)*?)\\?"', raw):
        name = m.group(1).replace('\\/', '/').replace('\\"', '"')
        tail = raw[m.end():m.end() + 600]
        u = UUID.search(tail) or UUID.search(raw[max(0, m.start() - 600):m.start()])
        if u:
            pairs.append((u.group(1), name))
    return pairs


def check_form(f, outdir):
    fid, src, title = f["id"], f["source_file"], f["title"]
    ours = src if os.path.exists(src) else None
    base = os.path.basename(src or "")
    res = {"form_id": fid, "titel": title, "datei": base, "status": "nicht_gefunden",
           "online_name": None, "url": None, "note": None}
    if not ours:
        res["status"] = "lokal_fehlt"; res["note"] = "Quelldatei lokal nicht vorhanden"
        return res
    myhash = hashlib.sha256(open(ours, "rb").read()).hexdigest()
    cand = {}                                     # (uuid, name) -> match quality
    for t_ in terms(base, title):
        raw = curl(f"{BASE}/CMS/lists/list?filter_text=({t_})&mode=list&language=DE")
        cids = list(dict.fromkeys(CID.findall(raw)))[:6]
        for cid in cids:
            for uuid, name in content_files(cid):
                q = 0
                if nf(name) == nf(base):
                    q = 3                          # exact
                elif strip_year(name) == strip_year(base) and strip_year(base):
                    q = 2                          # same modulo year
                elif nf(os.path.splitext(name)[0]) and \
                        nf(os.path.splitext(name)[0]) in nf(base) or nf(base) in nf(name):
                    q = 1
                if q:
                    cand[(uuid, name)] = max(cand.get((uuid, name), 0), q)
        if any(v == 3 for v in cand.values()):
            break
        time.sleep(0.4)
    if not cand:
        return res
    (uuid, name), q = sorted(cand.items(), key=lambda kv: -kv[1])[0]
    url = f"{BASE}/CMS/get/file/{uuid}"
    tmp = os.path.join(outdir, "dl", f"{fid}-{re.sub(r'[^A-Za-z0-9._-]', '_', name)[:80]}")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    if not curl(url, out=tmp):
        res.update(status="nicht_gefunden", note="Treffer, Download fehlgeschlagen")
        return res
    ohash = hashlib.sha256(open(tmp, "rb").read()).hexdigest()
    res.update(online_name=name, url=url)
    if ohash == myhash:
        res["status"] = "aktuell"
        os.remove(tmp)
    else:
        res["status"] = "aktualisiert"
        res["note"] = f"match q={q}; Kandidat gespeichert: {os.path.basename(tmp)}"
        res["kandidat"] = tmp
    return res


def main():
    outdir = sys.argv[1]
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--limit":
            limit = int(sys.argv[i + 1])
    os.makedirs(outdir, exist_ok=True)
    rpath = os.path.join(outdir, "results.json")
    results = json.load(open(rpath, encoding="utf-8")) if os.path.exists(rpath) else {}
    c = connect(DB_PATH)
    forms = [dict(r) for r in c.execute("SELECT id, title, source_file FROM form ORDER BY id")]
    c.close()
    todo = [f for f in forms if str(f["id"]) not in results]
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} Formulare zu prüfen (von {len(forms)}; {len(results)} bereits erledigt)")
    done = 0
    def work(f):
        nonlocal done
        try:
            r = check_form(f, outdir)
        except Exception as e:
            r = {"form_id": f["id"], "titel": f["title"], "status": "fehler", "note": str(e)[:120]}
        results[str(f["id"])] = r
        done += 1
        if done % 10 == 0:
            json.dump(results, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"  {done}/{len(todo)}  (aktuell {sum(1 for x in results.values() if x['status']=='aktuell')}, "
                  f"aktualisiert {sum(1 for x in results.values() if x['status']=='aktualisiert')}, "
                  f"offen {sum(1 for x in results.values() if x['status']=='nicht_gefunden')})", flush=True)
        time.sleep(0.3)
    with ThreadPoolExecutor(max_workers=5) as ex:
        list(ex.map(work, todo))
    json.dump(results, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("FERTIG:", dict(Counter(v["status"] for v in results.values())))


if __name__ == "__main__":
    main()
