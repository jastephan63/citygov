#!/usr/bin/env python3
"""Parse harvested DVSH modeller pages (raw text) into structured JSON.

Purely deterministic (no model judgement): the admin page renders fixed section
headers, so we slice between them. Extracts the authoritative legal bases
(KANTONALES RECHT with SSR numbers, BUNDESRECHT with SR numbers) plus the
service metadata that is useful in the dashboard.

    python3 scripts/parse_dvsh.py <services_txt-dir> <out.json>
"""
import json, os, re, sys

# section headers in render order; used as slice boundaries
SECTIONS = ["WORUM GEHT ES?", "WAS WIRD BENÖTIGT?", "WIE LÄUFT ES AB?",
            "KANTONALES RECHT", "BUNDESRECHT", "EXTERNE LINKS", "WO ERLEDIGEN?",
            "DOWNLOADS", "KONTAKT", "GRUNDLAGE", "ANMERKUNGEN / RÜCKFRAGEN",
            "VERSIONS-HISTORIE"]
# noise lines the admin UI renders around values
NOISE = {"i", "Immer online", "Online", "Offline", "Leer", "leer", "keine", "BEARBEITEN",
         "✕", "ÄNDERN", "Struktur", "JSON (API)", "Wissensgefässe (BETA)",
         "Konversationsmodell (BETA)", "Online-Auskunft testen (BETA)",
         "ZURÜCK IN MODELLIERUNG", "← SERVICES", "SERVICE LÖSCHEN", "Umbenennen",
         "aus Organisation", "ANMERKUNG HINZUFÜGEN", "IHRE NACHRICHT"}
SSR = re.compile(r"^(.*?)(\d{3}\.\d{2,4})(?:↗.*)?$")          # "Dekret …211.440↗ Link"
SR_IN_LABEL = re.compile(r"\((\d{3}(?:\.\d+)*)\)")            # "… Geoinformation (510.62)"


def lines_of(txt):
    return [l.strip() for l in txt.splitlines()]


def section(txt, name):
    """Text between header `name` and the next known section header."""
    i = txt.find("\n" + name)
    if i < 0:
        return ""
    start = i + len(name) + 1
    # never end on the section's own name again — it repeats as the field label
    ends = [txt.find("\n" + s, start) for s in SECTIONS if s != name]
    ends = [e for e in ends if e > 0]
    return txt[start:min(ends)] if ends else txt[start:]


def field(sec, label):
    """Value lines following an UPPERCASE field label inside a section."""
    ls = lines_of(sec)
    try:
        i = ls.index(label)
    except ValueError:
        return []
    out = []
    for l in ls[i + 1:]:
        if not l:
            continue
        if l in NOISE:
            continue
        if l.isupper() and len(l) > 3 and not l.startswith("("):
            break                      # next field label
        out.append(l)
    return out


def parse(txt):
    ls = lines_of(txt)
    d = {}
    m = re.search(r"/admin/services/(\d+)", txt)
    d["dvsh_id"] = int(m.group(1)) if m else None
    # title: first non-empty line after the "SERVICE" banner
    try:
        i = ls.index("SERVICE")
        d["title"] = next(l for l in ls[i + 1:] if l)
    except (ValueError, StopIteration):
        d["title"] = ""
    m = re.search(r"^/([a-z0-9\-]+) · (v\d+)$", txt, re.M)
    d["slug"], d["version"] = (m.group(1), m.group(2)) if m else ("", "")
    m = re.search(r"^Verwaltung › (.+)$", txt, re.M)
    if m:
        parts = [p.strip() for p in m.group(1).split("›")]
        d["department"] = parts[0] if parts else ""
        d["dienststelle"] = parts[-1] if parts else ""
    d["status"] = "Übergeben" if "\nÜbergeben" in txt else ""

    s1 = section(txt, "WORUM GEHT ES?")
    d["kurzbeschreibung"] = " ".join(field(s1, "KURZBESCHREIBUNG"))
    d["beschreibung"] = "\n".join(field(s1, "BESCHREIBUNG"))
    s2 = section(txt, "WAS WIRD BENÖTIGT?")
    d["voraussetzungen"] = field(s2, "VORAUSSETZUNGEN")
    d["erforderliche_unterlagen"] = field(s2, "ERFORDERLICHE UNTERLAGEN")
    s3 = section(txt, "WIE LÄUFT ES AB?")
    d["ablauf"] = field(s3, "ABLAUF")
    d["bearbeitungsdauer"] = " ".join(field(s3, "BEARBEITUNGSDAUER"))
    d["fristen"] = " ".join(field(s3, "FRISTEN"))
    d["gebuehren"] = " ".join(field(s3, "GEBÜHREN"))

    # --- authoritative legal bases ---
    kant = []
    for l in field(section(txt, "KANTONALES RECHT"), "GESETZE"):
        if l in ("keine", "Leer"):
            continue
        m = SSR.match(l)
        if m and m.group(1).strip():
            kant.append({"titel": m.group(1).strip(), "ssr": m.group(2)})
        elif l and not l.startswith("↗"):
            kant.append({"titel": l.replace("↗ Link", "").strip(), "ssr": None})
    d["rechtsgrundlagen_kantonal"] = kant
    bund = []
    for l in field(section(txt, "BUNDESRECHT"), "BUNDESRECHT"):
        if l in ("keine", "Leer") or l.startswith("↗"):
            continue
        m = SR_IN_LABEL.search(l)
        bund.append({"titel": re.sub(r"\s*\(\d{3}(?:\.\d+)*\)\s*$", "", l).strip(),
                     "sr": m.group(1) if m else None})
    d["rechtsgrundlagen_bund"] = bund

    d["externe_links"] = [l for l in field(section(txt, "EXTERNE LINKS"), "EXTERNE LINKS")
                          if l not in ("keine", "Leer") and not l.startswith("↗")]

    # --- matching signals: real source filenames (WO ERLEDIGEN / DOWNLOADS / GRUNDLAGE) ---
    files, seen = [], set()
    for fn in re.findall(r"([^\n/\\]+?\.(?:pdf|docx?|xlsx?|xlsm))(?:\s*↗)?\s*$",
                         txt, re.M | re.I):
        f = fn.strip()
        if f.isupper():          # the duplicated ALL-CAPS echo line
            continue
        k = f.lower()
        if k not in seen:
            seen.add(k)
            files.append(f)
    d["source_files"] = files
    # the form/link the citizen actually starts at
    wo_sec = section(txt, "WO ERLEDIGEN?")
    d["startpunkt"] = [l for l in lines_of(wo_sec)
                       if l and l not in NOISE and not l.isupper()
                       and not l.startswith("Online-Formular, ein PDF")
                       and not l.startswith("↗")][:2]
    # source links (law names + doc titles the model was built from)
    d["quellen"] = [l for l in lines_of(section(txt, "GRUNDLAGE"))
                    if l and l not in NOISE and not l.isupper()
                    and l not in ("Link", "PDF", "Word", "Excel")
                    and not l.startswith("Die Dokumente")
                    and not re.match(r"^\d+([.,]\d+)?\s*(KB|MB)$", l)][:14]
    d["abgabe"] = [l for l in lines_of(wo_sec) if l and l not in NOISE and not l.isupper()
                   and not l.startswith("Online-Formular, ein PDF")][:3]
    kont = section(txt, "KONTAKT")
    d["kontakt"] = [l for l in lines_of(kont) if l and l not in NOISE and not l.isupper()
                    and not l.startswith("Wird mit dem Service")][:4]
    return d


def main():
    src, out = sys.argv[1], sys.argv[2]
    res, skipped = [], 0
    for fn in sorted(os.listdir(src), key=lambda x: int(x.split(".")[0]) if x[0].isdigit() else 0):
        if not fn.endswith(".txt"):
            continue
        txt = open(os.path.join(src, fn), encoding="utf-8", errors="replace").read()
        if "NOT_FOUND" in txt[:40] or "SEITE NICHT GEFUNDEN" in txt or len(txt) < 400:
            skipped += 1
            continue
        d = parse(txt)
        if not d.get("dvsh_id"):
            d["dvsh_id"] = int(fn.split(".")[0])
        res.append(d)
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    nk = sum(1 for r in res if r["rechtsgrundlagen_kantonal"])
    nb = sum(1 for r in res if r["rechtsgrundlagen_bund"])
    print(f"parsed {len(res)} services (skipped {skipped}); "
          f"with kantonalem Recht: {nk}, mit Bundesrecht: {nb}")


if __name__ == "__main__":
    main()
