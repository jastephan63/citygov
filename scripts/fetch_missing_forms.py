#!/usr/bin/env python3
"""Download the forms DVSH references but our collection lacks, into the right
office folder under Verwaltung/.

Input: need_files.json (DVSH services with their source filenames) + a docs.tsv
index of sh.ch (uuid <TAB> originalname). Files are matched by filename and
downloaded from https://sh.ch/CMS/get/file/<uuid>. Dry-run by default; with
--apply it downloads in parallel and records the results in
inventory/dvsh_downloaded.json and inventory/dvsh_not_found.json.

    python3 scripts/fetch_missing_forms.py <need_files.json> <docs.tsv> [--apply]
"""
import json, os, re, subprocess, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
VERW = os.path.normpath(os.path.join(HERE, "..", "..", "Verwaltung"))


def nf(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "").lower().strip())


def office_dir(amt):
    """Best-matching existing office folder for a DVSH Dienststelle name."""
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
            if not k or not want:
                continue
            if k == want:
                return op
            if want in k or k in want:
                s = min(len(k), len(want))
                if s > score:
                    best, score = op, s
    return best


def main():
    need = json.load(open(sys.argv[1], encoding="utf-8"))
    apply = "--apply" in sys.argv
    index = {}
    with open(sys.argv[2], encoding="utf-8") as fh:
        for ln in fh:
            p = ln.rstrip("\n").split("\t")
            if len(p) >= 2 and p[1]:
                index.setdefault(nf(p[1]), p[0])
    print(f"sh.ch index: {len(index)} distinct filenames")

    jobs, missing = [], []
    for n in need:
        amt = n.get("amt") or ""
        dest_dir = office_dir(amt) or os.path.join(VERW, "_DVSH", re.sub(r"[/:]", "-", amt or "Unbekannt"))
        for f in n["dateien"]:
            uuid = index.get(nf(f))
            if uuid:
                jobs.append((uuid, f, dest_dir, n["dvsh_id"]))
            else:
                missing.append((f, amt))
    # Keep only the first job per (normalised) filename.
    seen = set()
    unique = []
    for j in jobs:
        k = nf(j[1])
        if k not in seen:
            seen.add(k)
            unique.append(j)
    jobs = unique
    print(f"found on sh.ch: {len(jobs)} files | not found: {len(missing)}")
    if not apply:
        for u, f, d, i in jobs[:10]:
            print(f"   would fetch {f[:46]:48} -> {os.path.relpath(d, VERW)}")
        for f, a in missing[:10]:
            print(f"   MISSING     {f[:46]:48} [{a[:26]}]")
        print("(dry-run — pass --apply)")
        return

    def dl(job):
        uuid, fname, ddir, dvid = job
        os.makedirs(ddir, exist_ok=True)
        dest = os.path.join(ddir, fname)
        if os.path.exists(dest):
            return ("have", fname, dest, dvid)
        try:
            subprocess.run(["curl", "-sS", "-L", "--max-time", "90", "-o", dest,
                            f"https://sh.ch/CMS/get/file/{uuid}"], capture_output=True, timeout=120)
        except Exception:
            return ("fail", fname, dest, dvid)
        kind = subprocess.run(["file", "-b", dest], capture_output=True, text=True).stdout
        if "HTML" in kind:                      # dead link -> maintenance page
            os.remove(dest)
            return ("dead", fname, dest, dvid)
        return ("ok", fname, dest, dvid)

    from collections import Counter
    res = Counter()
    got = []
    with ThreadPoolExecutor(8) as ex:
        for state, fname, dest, dvid in ex.map(dl, jobs):
            res[state] += 1
            if state in ("ok", "have"):
                got.append({"datei": fname, "pfad": os.path.relpath(dest, os.path.join(HERE, "..")),
                            "dvsh_id": dvid})
    json.dump(got, open(os.path.join(HERE, "..", "inventory", "dvsh_downloaded.json"), "w"),
              ensure_ascii=False, indent=1)
    print("download:", dict(res))
    json.dump([{"datei": f, "amt": a} for f, a in missing],
              open(os.path.join(HERE, "..", "inventory", "dvsh_not_found.json"), "w"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
