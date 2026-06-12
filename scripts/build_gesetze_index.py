#!/usr/bin/env python3
"""Index every cantonal law PDF in ../Gesetze/ by its SHR number + title.

Writes inventory/gesetze_index.json: [{file, shr, title}]. Used by the legal pass
to resolve a cited cantonal law name (e.g. "Baugesetz") to the real SHR PDF, so
citations are matched to source, never invented (conv 6). Offline (macOS PDFKit
via JXA).

    python3 scripts/build_gesetze_index.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, INVENTORY_DIR
from extract_law import extract_text

GESETZE = os.path.normpath(os.path.join(ROOT, "..", "Gesetze"))


def main():
    out = []
    files = sorted(f for f in os.listdir(GESETZE) if f.lower().endswith(".pdf"))
    for i, f in enumerate(files, 1):
        txt = extract_text(os.path.join(GESETZE, f))
        lines = [l.strip() for l in txt.splitlines() if l.strip()][:6]
        # header line carries "Kanton Schaffhausen <SHR>"; title follows
        shr = ""; title = ""
        for ln in lines:
            m = ln.replace("Kanton Schaffhausen", "").strip()
            if not shr and m and m[0].isdigit():
                shr = m.split()[0]
        # title = first non-header, non-number line(s)
        body = [l for l in lines if "Kanton Schaffhausen" not in l and not l[:3].replace(".", "").isdigit()]
        title = " ".join(body[:2])[:160]
        out.append({"file": f, "shr": shr, "title": title})
        if i % 50 == 0:
            sys.stderr.write(f"  indexed {i}/{len(files)}\n")
    os.makedirs(INVENTORY_DIR, exist_ok=True)
    p = os.path.join(INVENTORY_DIR, "gesetze_index.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"wrote {p}  ({len(out)} laws)")


if __name__ == "__main__":
    main()
