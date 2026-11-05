#!/usr/bin/env python3
"""Ingest cantonal laws (by SHR number) into law+article, and optionally dump a
compact JSON per law as mapping input. Article numbers and headings are
read from the full text of the official Gesetze PDF (extract_law.py, articles_text below:
an article line followed by its first paragraph; cross-references, the change table and
repealed articles are not articles) — the ground truth the proof gate maps against.
Upserts are idempotent; last_checked is set to 'Gesetze-PDF SHR <n> (Stand …)'.
Writes go staging -> validate -> swap.

    python3 scripts/ingest_laws.py <SHR> [<SHR> ...] [--out <dir>]
"""
import json, os, re, shutil, subprocess, sys
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate
from citygov.domain.gesetz_titel import kurztitel

HERE = os.path.join(ROOT, "scripts")   # runs scripts/extract_law.py, as before the move
IDX = json.load(open(os.path.join(HERE, "..", "inventory", "gesetze_index.json")))
BYSHR = {g.get("shr"): g for g in IDX}
ART = re.compile(r"^\s*((?:Art\.|§)\s*\d+[a-z]*)(?:\s+(.*?))?\s*$")
DATEY = re.compile(r"\d{2}\.\d{2}\.\d{4}")
XREF = re.compile(r"^(Abs\.|lit\.|Ziff\.|Bst\.|und\b|bis\b|oder\b|sowie\b|ff\.|f\.)")
SECTION = re.compile(r"^\d+(?:\.\d+[a-z]?)+\s+(\S.*)$")
PAGEHDR = re.compile(r"^(\d{3}\.\d{3}(?:\.\d+)?\s+Kanton Schaffhausen|Kanton Schaffhausen\s+\d{3}\.\d{3}(?:\.\d+)?)$")
PARA = re.compile(r"^\d+[a-z]?$")


def join_hyph(parts):
    out = ""
    for p in parts:
        p = p.strip()
        if out.endswith("-") and p[:1].islower():
            out = out[:-1] + p
        else:
            out = (out + " " + p).strip()
    return out


ABBR = re.compile(r"(?:Art|Abs|lit|Ziff|Fr|bzw|Nr|ff|vgl|S|Bst|al|Mio|Ziff|Kt|resp|inkl|ca|evtl|z\.B|u\.a|d\.h)\.$")


def first_sentence(t):
    """The text up to its first sentence end (not an abbreviation such as «Art.» or «Fr.»), else 80 chars."""
    for m in re.finditer(r"[.:](?=\s|$)", t):
        if m.end() >= 20 and not ABBR.search(t[:m.end()]) and not re.search(r"\b\d+\.$", t[:m.end()]):
            return t[:m.end()] if m.end() <= 120 else t[:80]
    return t[:80]


def key(no):
    m = re.search(r"(\d+)([a-z]*)", no)
    return (int(m.group(1)), m.group(2))


def articles_text(lines):
    """[{no, heading, quelle}] and the repealed numbers from the FULL text of a law PDF.

    An article is a line «Art. N» / «§ N» (optionally with its heading) that is followed by its
    first paragraph number, possibly after a «*» line that may carry the heading; «…» there means
    repealed. A line that only continues a sentence («Art. 65 sinngemäss.», «Art. 66a darf nicht …»,
    «Art. 94a Abs. 1 …») is a cross-reference, never an article. An article without a paragraph
    number counts only in number order right after the previous one. Without a heading of its own
    the article takes the section heading right above it (quelle 'abschnitt'), else the first
    sentence of its text (quelle 'text'); quelle 'eigen' is the printed article heading."""
    L = [l.rstrip() for l in lines]
    arts, seen, stubs, last = [], set(), [], None
    for i, line in enumerate(L):
        m = ART.match(line)
        if not m or DATEY.search(line):
            continue
        no, rest = re.sub(r"\s+", " ", m.group(1)), (m.group(2) or "").strip()
        if rest and (rest[0].islower() or XREF.match(rest)):
            continue                                   # a wrapped cross-reference, not an article
        j = i + 1
        while j < len(L) and PAGEHDR.match(L[j].strip()):
            j += 1
        head = rest
        k = j
        if k < len(L) and L[k].strip().startswith("*"):
            star = L[k].strip()[1:].strip()
            if star and not head:
                head = star
            k += 1
        # a heading broken over at most two more lines («… ausländische» / «Personengesamtheiten …»)
        if head:
            n_more = 0
            while n_more < 2 and k < len(L) and L[k].strip() and not PARA.match(L[k].strip()) \
                    and not ART.match(L[k]) and L[k].strip() not in ("…", "*") \
                    and k + 1 < len(L) and (PARA.match(L[k + 1].strip()) or (n_more == 0 and k + 2 < len(L) and PARA.match(L[k + 2].strip()))):
                head = join_hyph([head, L[k]]); k += 1; n_more += 1
        nxt = L[k].strip() if k < len(L) else ""
        if nxt == "…" or re.fullmatch(r"\*?\s*(…|Aufgehoben\.?)", nxt):
            stubs.append(no); seen.add(no); last = no; continue   # repealed
        if no in seen:
            continue
        if not PARA.match(nxt):
            # no paragraph number (a one-paragraph article, or a stray line of the previous article):
            # an article only when it stands in number order right after the last one read
            if not (last and key(no) > key(last) and key(no)[0] - key(last)[0] <= 1 and no.split()[0] == last.split()[0]):
                continue
            if rest:
                k = k - 1                              # the text starts right here
            else:
                while k < len(L) and L[k].strip() and not L[k].strip()[:1].isupper():
                    k += 1                             # skip the stray line («erfolgen.», «*»)
                k -= 1
        src = "eigen" if head else ""
        if not head:
            b = i - 1
            while b >= 0 and (PAGEHDR.match(L[b].strip()) or L[b].strip() == "*"):
                b -= 1
            s = SECTION.match(L[b].strip()) if b >= 0 else None
            if s:
                head, src = s.group(1).strip(), "abschnitt"
            else:
                # first words of the first paragraph
                txt, q = [], k + 1
                while q < len(L) and (PARA.match(L[q].strip()) or L[q].strip() == "*"):
                    q += 1                             # «1», «2», «*» before the text
                while q < len(L) and len(" ".join(txt)) < 160:
                    t = L[q].strip(); am = ART.match(L[q])
                    if PARA.match(t) or t == "*" or (am and not (am.group(2) or "")[:1].islower()):
                        break
                    if not PAGEHDR.match(t):
                        txt.append(L[q])
                    q += 1
                t = re.sub(r"^(?:[a-z]\)\s*|\d\s+(?=[A-ZÄÖÜ]))+", "", join_hyph(txt))   # «a) b)» markers, a paragraph number
                head, src = first_sentence(t), "text"
        seen.add(no); last = no
        arts.append({"no": no, "heading": head[:120], "quelle": src})
    return arts, stubs


def read_law(shr):
    g = BYSHR.get(shr)
    if not g:
        return None
    path = os.path.normpath(os.path.join(ROOT, "..", "Gesetze", g["file"]))
    if not os.path.exists(path):
        return None
    try:
        out = subprocess.run(["python3", os.path.join(HERE, "extract_law.py"), path],
                             capture_output=True, text=True, timeout=90).stdout
    except Exception:
        return None
    stand = ""
    m = re.search(r"\(Stand ([^)]+)\)", out)
    if m:
        stand = m.group(1).strip()
    arts, aufgehoben = articles_text([ln for ln in out.splitlines() if not ln.startswith("# ")])
    return {"shr": shr, "title": g["title"], "stand": stand,
            "articles": [{"no": a["no"], "heading": a["heading"]} for a in arts],
            "quelle": {a["no"]: a["quelle"] for a in arts}, "aufgehoben": aufgehoben}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    outdir = None
    if "--out" in sys.argv:
        outdir = sys.argv[sys.argv.index("--out") + 1]
        os.makedirs(outdir, exist_ok=True)
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    nl = na = 0
    for shr in args:
        law = read_law(shr)
        if not law or not law["articles"]:
            print(f"  {shr}: no articles read (skipped)")
            continue
        cref = "SHR " + shr
        lc = f"Gesetze-PDF {cref}" + (f" (Stand {law['stand']})" if law["stand"] else "")
        r = c.execute("SELECT id FROM law WHERE cantonal_ref=?", [cref]).fetchone()
        if r:
            lid = r["id"]
        else:
            # a new law: the title without the Rechtsbuch's edition line «Vom … (Stand …)» and
            # footnote marker, the short title as the title correction derives it (the gate in
            # citygov/domain/gates.py refuses both; quellen/korrekturen/gesetz_titel_2026-10-05.json)
            title = re.split(r"\s+Vom\s+\d", law["title"] or shr)[0]
            title = re.sub(r"\s*\*\s*$", "", title).strip()
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:60].strip("-")
            c.execute("INSERT INTO law(slug,title,short_title,jurisdiction_level,cantonal_ref,last_checked) "
                      "VALUES(?,?,?,?,?,?)", [slug, title, kurztitel(title), "cantonal", cref, "Gesetze-PDF"])
            lid = c.execute("SELECT id FROM law WHERE cantonal_ref=?", [cref]).fetchone()["id"]
            nl += 1
        for a in law["articles"]:
            ex = c.execute("SELECT id FROM article WHERE law_id=? AND article_no=?", [lid, a["no"]]).fetchone()
            if ex:
                c.execute("UPDATE article SET heading=?, last_checked=? WHERE id=?", [a["heading"], lc, ex["id"]])
            else:
                c.execute("INSERT INTO article(law_id,article_no,heading,last_checked) VALUES(?,?,?,?)",
                          [lid, a["no"], a["heading"], lc])
                na += 1
        if outdir:
            json.dump({"cref": cref, "title": law["title"], "stand": law["stand"],
                       "articles": law["articles"]},
                      open(os.path.join(outdir, shr + ".json"), "w"), ensure_ascii=False)
        print(f"  {shr}: {len(law['articles'])} articles  ({law['title'][:50]})")
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"ingested: +{nl} laws, +{na} articles")


if __name__ == "__main__":
    main()
