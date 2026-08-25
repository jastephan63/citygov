#!/usr/bin/env python3
"""Fetch cantonal laws by SHR number straight from the official Schaffhauser
Rechtsbuch register API and add them to ../Gesetze/ + the local index.

    https://rechtsbuch.sh.ch/api/de/texts_of_law/<SHR>  ->  {..., pdf_link}

This is the authoritative cantonal source (same register DVSH links to), so any
law DVSH cites can be obtained even when it is not in the offline collection.
Downloads the official PDF, registers it in inventory/gesetze_index.json, and
leaves ingestion to ingest_laws.py (which reads real articles from the PDF).

    python3 scripts/fetch_rechtsbuch.py 921.100 922.100 ...
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GESETZE = os.path.normpath(os.path.join(HERE, "..", "..", "Gesetze"))
INDEX = os.path.join(HERE, "..", "inventory", "gesetze_index.json")
API = "https://rechtsbuch.sh.ch/api/de/texts_of_law/{}"


def curl(url, out=None, timeout=60):
    cmd = ["curl", "-sS", "-L", "--max-time", str(timeout)]
    if out:
        cmd += ["-o", out]
    try:
        r = subprocess.run(cmd + [url], capture_output=True, text=(out is None), timeout=timeout + 20)
        return r.stdout if out is None else os.path.exists(out)
    except Exception:
        return None if out is None else False


def main():
    ssrs = [a for a in sys.argv[1:] if re.match(r"^\d{3}\.\d{2,4}$", a)]
    idx = json.load(open(INDEX, encoding="utf-8"))
    have = {g["shr"] for g in idx}
    added = failed = skipped = 0
    for ssr in ssrs:
        if ssr in have:
            skipped += 1
            continue
        raw = curl(API.format(ssr))
        if not raw:
            print(f"  {ssr}: API unreachable"); failed += 1; continue
        try:
            t = json.loads(raw)["text_of_law"]
        except Exception:
            print(f"  {ssr}: no such law in register"); failed += 1; continue
        pdf = t.get("pdf_link")
        title = (t.get("title") or "").strip()
        if not pdf:
            print(f"  {ssr}: no pdf_link ({title[:40]})"); failed += 1; continue
        fn = f"{ssr}-rechtsbuch.de.pdf"
        dest = os.path.join(GESETZE, fn)
        if not curl(pdf, dest, timeout=90):
            print(f"  {ssr}: download failed"); failed += 1; continue
        kind = subprocess.run(["file", "-b", dest], capture_output=True, text=True).stdout
        if not kind.startswith("PDF"):
            os.remove(dest); print(f"  {ssr}: not a PDF"); failed += 1; continue
        idx.append({"file": fn, "shr": ssr, "title": title})
        have.add(ssr)
        added += 1
        print(f"  {ssr}: {title[:52]}")
    json.dump(idx, open(INDEX, "w"), ensure_ascii=False, indent=0)
    print(f"fetched {added} laws from Rechtsbuch (skipped {skipped} already present, {failed} failed)")


if __name__ == "__main__":
    main()
