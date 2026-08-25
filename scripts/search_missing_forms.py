#!/usr/bin/env python3
"""Find DVSH-referenced files that the bulk index missed, via the sh.ch CMS
full-text search, and download them.

The list endpoint (/CMS/lists/list?filter_text=(term)) searches page content;
each hit's content JSON (/CMS/content?contentid=) carries its file uuids +
originalname. We derive search terms from the wanted filename, collect hits,
and download when the originalname matches exactly.

    python3 scripts/search_missing_forms.py <not_found.json> [--apply]
"""
import json, os, re, subprocess, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
VERW = os.path.normpath(os.path.join(HERE, "..", "..", "Verwaltung"))
UUID = re.compile(r"get/file/([0-9a-fA-F-]{36})")
ONAME = re.compile(r'originalname\\?":\\?"([^"\\]+)')


def nf(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "").lower().strip())


def curl(url, out=None, t=40):
    cmd = ["curl", "-sS", "--compressed", "--max-time", str(t)]
    if out:
        cmd += ["-o", out]
    try:
        r = subprocess.run(cmd + [url], capture_output=True, timeout=t + 20)
        if out:
            return os.path.exists(out)
        return (r.stdout or b"").decode("utf-8", "replace")
    except Exception:
        return "" if out is None else False


def terms(fname):
    """Search terms from a filename: longest German-ish words."""
    base = os.path.splitext(fname)[0]
    base = re.sub(r"[_\-]+", " ", base)
    base = re.sub(r"\b\d+\b|\bp\b|\bdef\b|\bv?\d+[._]\d+\b", " ", base, flags=re.I)
    words = re.findall(r"[A-Za-zÄÖÜäöüß]{5,}", base)
    words.sort(key=len, reverse=True)
    out = words[:2]
    if len(words) >= 2:
        out.append(" ".join(words[:2]))
    return out[:3]


def office_dir(amt):
    def key(s):
        s = unicodedata.normalize("NFD", (s or "").lower())
        s = "".join(c for c in s if not unicodedata.combining(c))
        for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u")):
            s = s.replace(a, b)
        return re.sub(r"[^a-z]", "", s)
    want = key(amt)
    best, score = None, 0
    for dep in sorted(os.listdir(VERW)):
        dp = os.path.join(VERW, dep)
        if not os.path.isdir(dp) or dep.startswith("_"):
            continue
        for off in sorted(os.listdir(dp)):
            op = os.path.join(dp, off)
            if not os.path.isdir(op):
                continue
            k = key(off)
            if k and want:
                if k == want:
                    return op
                if (want in k or k in want) and min(len(k), len(want)) > score:
                    best, score = op, min(len(k), len(want))
    return best


def find_one(item):
    fname, amt = item["datei"], item.get("amt", "")
    want = nf(fname)
    seen_ids = set()
    for t in terms(fname):
        html = curl(f"https://sh.ch/CMS/lists/list?start=0&mode=list&language=DE&filter_text=({t})")
        ids = re.findall(r'contentid="(\d+)"', html)
        for cid in ids[:12]:
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            js = curl(f"https://sh.ch/CMS/content?contentid={cid}&language=DE")
            names = ONAME.findall(js)
            if not any(nf(n) == want for n in names):
                continue
            for m in UUID.finditer(js):
                w = js[m.end():m.end() + 800]
                om = ONAME.search(w)
                if om and nf(om.group(1)) == want:
                    return (fname, amt, m.group(1))
            # fallback: single file on the page
            if len(set(UUID.findall(js))) == 1 and len(set(names)) == 1:
                return (fname, amt, UUID.findall(js)[0])
    return (fname, amt, None)


def main():
    need = json.load(open(sys.argv[1], encoding="utf-8"))
    apply = "--apply" in sys.argv
    seen, uniq = set(), []
    for n in need:
        if nf(n["datei"]) not in seen:
            seen.add(nf(n["datei"]))
            uniq.append(n)
    print(f"searching sh.ch for {len(uniq)} files ...")
    found, still = [], []
    with ThreadPoolExecutor(6) as ex:
        for fname, amt, uuid in ex.map(find_one, uniq):
            (found if uuid else still).append((fname, amt, uuid))
    print(f"found: {len(found)} | still missing: {len(still)}")
    if not apply:
        for f, a, u in found[:12]:
            print(f"   would fetch {f[:52]}")
        return
    got = []
    from collections import Counter
    res = Counter()
    for fname, amt, uuid in found:
        ddir = office_dir(amt) or os.path.join(VERW, "_DVSH", re.sub(r"[/:]", "-", amt or "Unbekannt"))
        os.makedirs(ddir, exist_ok=True)
        dest = os.path.join(ddir, fname)
        if os.path.exists(dest):
            res["have"] += 1; got.append(fname); continue
        curl(f"https://sh.ch/CMS/get/file/{uuid}", dest, t=90)
        kind = subprocess.run(["file", "-b", dest], capture_output=True).stdout.decode("utf-8","replace")
        if "HTML" in kind or not os.path.getsize(dest):
            os.remove(dest); res["dead"] += 1; continue
        res["ok"] += 1; got.append(fname)
    print("download:", dict(res))
    json.dump(got, open(os.path.join(HERE, "..", "inventory", "dvsh_downloaded2.json"), "w"),
              ensure_ascii=False, indent=1)
    json.dump([{"datei": f, "amt": a} for f, a, _ in still],
              open(os.path.join(HERE, "..", "inventory", "dvsh_still_missing.json"), "w"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
