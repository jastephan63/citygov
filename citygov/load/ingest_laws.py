#!/usr/bin/env python3
"""Ingest cantonal laws (by SHR number) into law+article, and optionally dump a
compact JSON per law as mapping input. Article numbers and headings are
read from the full text of the official Gesetze PDF (extract_law.py, articles_text below:
an article line followed by its first paragraph; cross-references, the change table and
repealed articles are not articles) — the ground truth the proof gate maps against.
Upserts are idempotent; last_checked is set to 'Gesetze-PDF SHR <n> (Stand …)', on the article and
on every data_field_legal_basis row citing it (a citation shows its article's verification level);
a row stored with the bare number («88») is the same article as «Art. 88» and gets the notation.
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
# the number: «12», «12a», «14quater»; an annex provision «A1a-2», «A1-0.1»; a transitional «T1»
ART = re.compile(r"^\s*((?:Art\.|§)\s*(?:[A-Z]\d+[a-z]*-\d+(?:\.\d+)?[a-z]*|T\d+[a-z]*|\d+[a-z]*))(?:\s+(.*?))?\s*$")
DATEY = re.compile(r"\d{2}\.\d{2}\.\d{4}")
XREF = re.compile(r"^(Abs\.|lit\.|Ziff\.|Bst\.|und\b|bis\b|oder\b|sowie\b|ff\.|f\.)")
SECTION = re.compile(r"^\d+(?:\.\d+[a-z]?)+\s+(\S.*)$")
PAGEHDR = re.compile(r"^(\d{3}\.\d{3}(?:\.\d+)?\s+Kanton Schaffhausen|Kanton Schaffhausen\s+\d{3}\.\d{3}(?:\.\d+)?)$")
PARA = re.compile(r"^\d+[a-z]?$")
RANGE = re.compile(r"^\d+[a-z]?\s*[–-]\s*\d+[a-z]?$")   # «1–2»: paragraphs 1 to 2 (followed by «…» when repealed)
PAGENO = re.compile(r"^\d{1,3}$")
FOOTNOTE = re.compile(r"^\d+\)")                      # «12)Gegenstandslos.», «4) SHR 172.200.»
LAWABBR = re.compile(r"^[A-ZÄÖÜ][a-zäöü]*[A-ZÄÖÜ][A-Za-zÄÖÜäöü]*\)?[.,;:]?$")   # «PolG», «StGB», «GesG.», «AVIG.»


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


LATEIN = {"bis": 2, "ter": 3, "quater": 4, "quinquies": 5, "sexies": 6, "septies": 7, "octies": 8, "novies": 9, "decies": 10}


def key(no):
    """(series, number, suffix) in number order: «14» < «14a» < «14b», «14bis» < «14ter» < «14quater»;
    an annex provision «A1a-2» counts in the series «A1a-», a transitional one «T1» in «T»."""
    m = re.search(r"(?:\s)([A-Z]\d+[a-z]*-|T(?=\d))?(\d+)(?:\.\d+)?([a-z]*)$", " " + no.split(None, 1)[-1])
    s = m.group(3)
    return (m.group(1) or "", int(m.group(2)), LATEIN.get(s, ord(s[0]) - 96 if len(s) == 1 else (0 if not s else 99)))


def folgt(no, last):
    """True when «no» stands in number order right after «last» (same notation and series)."""
    return bool(last) and no.split()[0] == last.split()[0] and key(no)[0] == key(last)[0] \
        and key(no) > key(last) and key(no)[1] - key(last)[1] <= 1


def seitenumbruch(L, k):
    """The first line at or after k that is not a page break: a page header, or a page number
    right before one («12» / «Kanton Schaffhausen 354.111»)."""
    while k < len(L):
        t = L[k].strip()
        if PAGEHDR.match(t):
            k += 1
        elif PAGENO.match(t) and k + 1 < len(L) and PAGEHDR.match(L[k + 1].strip()):
            k += 2
        else:
            break
    return k


def articles_text(lines):
    """[{no, heading, quelle, zeile}] and the repealed numbers from the FULL text of a law PDF
    (zeile = the index of the article's line in `lines`).

    An article is a line «Art. N» / «§ N» (optionally with its heading) that is followed by its
    first paragraph number, possibly after a «*» line that may carry the heading; «…» there means
    repealed. A paragraph range «1–2» followed by «…» repeals those paragraphs only: the article
    stands when a paragraph follows (GG Art. 73: «1–2 / … / 3»), else it is repealed. A line that
    only continues a sentence («Art. 65 sinngemäss.», «Art. 66a darf nicht …», «Art. 94a Abs. 1 …»,
    «Art. 292 StGB eröffnet.», «Art. 27a PolG sind …») is a cross-reference, never an article —
    unless it stands in number order and only carries a stray end of a sentence before its heading
    line («Art. 44 pflichtet.») or a lettered heading («Art. 50 b) Genehmigung …»); a page number
    and header between the line and the next one do not count. An article without a
    paragraph number counts only in number order right after the previous one. A footnote marker
    («Dekreten12)») and a footnote line are no part of a heading. Without a heading of its own
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
            # a wrapped cross-reference, not an article — unless the article stands in number order
            # and its line only carries a stray end of a sentence («Art. 44 pflichtet.» / heading / «1»)
            # or a lettered heading («Art. 50 b) Genehmigung durch den Kantonsrat» / «1»)
            jj = seitenumbruch(L, i + 1)
            nach = L[jj].strip() if jj < len(L) else ""
            lm = re.match(r"^[a-z]\)\s+([A-ZÄÖÜ].*)$", rest)
            if lm and folgt(no, last) and PARA.match(nach):
                rest = lm.group(1)
            elif re.fullmatch(r"[a-zäöü][\wäöü-]*\.", rest) and folgt(no, last) and nach[:1].isupper() \
                    and not re.search(r"[.:;,]$", nach) and len(nach) < 100 and not ART.match(nach) \
                    and jj + 1 < len(L) and PARA.match(L[jj + 1].strip()):
                rest = ""                              # the heading follows on its own line
            else:
                continue
        if PARA.match(rest):
            rest = ""                                  # «§ 3 1»: the first paragraph number on the same line
        in_order = folgt(no, last)
        if rest and LAWABBR.match(rest.split()[0]):
            if not in_order:
                continue                               # «Art. 292 StGB eröffnet.»: another law's article
            if len(rest.split()) == 1 and rest.endswith("."):
                rest = ""                              # «Art. 13 AVIG.»: the end of the sentence before
        j = seitenumbruch(L, i + 1)
        head = rest
        k = j
        if k + 1 < len(L) and L[k].strip()[:1].islower() and re.search(r"[.;:]$", L[k].strip()) \
                and not head.endswith("-") and L[k + 1].strip().startswith("*"):
            k += 1                                     # «dard.»: the end of a sentence of the article before
        if k < len(L) and L[k].strip().startswith("*"):
            star = L[k].strip()[1:].strip()
            if star and not head:
                head = star
            k += 1
            while star and k < len(L) and L[k].strip() == "*":
                k += 1                                 # «* Begrenzung der Heim- und Spitaltaxen» / «*» / «1»
        elif not head and k + 1 < len(L) and PARA.match(L[k + 1].strip()) and L[k].strip()[:1].isupper() \
                and not re.search(r"[.:;,]$", L[k].strip()) and len(L[k].strip()) < 100 \
                and not ART.match(L[k]) and not (k + 2 < len(L) and PAGEHDR.match(L[k + 2].strip())):
            head = L[k].strip()                        # a heading on its own line without «*»
            k += 1
        # a heading broken over at most two more lines («… ausländische» / «Personengesamtheiten …»)
        if head:
            n_more = 0
            while n_more < 2 and k < len(L) and L[k].strip() and not PARA.match(L[k].strip()) \
                    and not RANGE.match(L[k].strip()) and not FOOTNOTE.match(L[k].strip()) \
                    and not PAGEHDR.match(L[k].strip()) \
                    and not ART.match(L[k]) and L[k].strip() not in ("…", "*") \
                    and k + 1 < len(L) and ((PARA.match(L[k + 1].strip()) and not (k + 2 < len(L) and PAGEHDR.match(L[k + 2].strip())))
                                            or (n_more == 0 and k + 2 < len(L) and PARA.match(L[k + 2].strip()))):
                head = join_hyph([head, L[k]]); k += 1; n_more += 1
            head = re.sub(r"(?<=\D)\d+\)$", "", head).strip()   # footnote marker «Dekreten12)»
            if head.endswith("-"):
                # «… Beistand-» / «*» / «schaft», «… Ausbildungsleis-» / «1» / «a) b) c) tungen»
                for q in range(k, min(k + 3, len(L))):
                    t = re.sub(r"^(?:[a-z]\)\s*)+", "", L[q].strip())
                    if re.fullmatch(r"[a-zäöüß][\wäöüß]*", t):
                        head = join_hyph([head, t])
                        if all(L[x].strip() == "*" for x in range(k, q)) and L[q].strip() == t:
                            k = q + 1                  # the word stood on its own line before the paragraph
                        break
                    if L[q].strip() != "*" and not PARA.match(L[q].strip()):
                        break
        nxt = L[k].strip() if k < len(L) else ""
        aufgehoben = nxt == "…" or bool(re.fullmatch(r"\*?\s*(…|Aufgehoben\.?)", nxt))
        while not aufgehoben and RANGE.match(nxt):
            # «1–2» / «…»: those paragraphs are repealed; the article stands when a paragraph follows
            q, weg = k + 1, False
            while q < len(L):
                t = L[q].strip()
                if t in ("*", "…") or FOOTNOTE.match(t):
                    weg = weg or t == "…"; q += 1
                elif seitenumbruch(L, q) > q:
                    q = seitenumbruch(L, q)
                else:
                    break
            if not weg:
                break                                  # a range in force: read like a paragraph number
            if q < len(L) and (PARA.match(L[q].strip()) or RANGE.match(L[q].strip())):
                k, nxt = q, L[q].strip()               # the first paragraph in force
            else:
                aufgehoben = True                      # every paragraph repealed
        if aufgehoben:
            stubs.append(no); seen.add(no); last = no; continue   # repealed
        if no in seen:
            continue
        if not PARA.match(nxt) and not RANGE.match(nxt):
            # no paragraph number (a one-paragraph article, or a stray line of the previous article):
            # an article only when it stands in number order right after the last one read
            if not folgt(no, last):
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
                while q < len(L) and (re.fullmatch(r"[a-zäöü][\wäöü-]*[.:]", L[q].strip())
                                      or re.fullmatch(r"(?:\d+\.\s*)+\*?", L[q].strip())
                                      or PARA.match(L[q].strip()) or L[q].strip() == "*"):
                    q += 1                             # «ze.», «gen:»: the end of a sentence printed out of place
                stern = re.sub(r"^(?:[a-z]\)\s*)+", "", L[q].strip()) if q < len(L) else ""
                if re.match(r"^\*\s+[A-ZÄÖÜ]", stern) and not re.search(r"[.,;-]$", stern):
                    seen.add(no); last = no
                    arts.append({"no": no, "heading": stern[1:].strip()[:120], "quelle": "eigen", "zeile": i})
                    continue                           # «§ A4-4 / 1 / ze. / * Betreuungsschlüssel», «a) * Kantonale …»
                ref = L[q].strip() if q < len(L) else ""
                if ART.match(ref) and LAWABBR.match(ref.split()[-1]) and not re.search(r"[.:;,]$", ref):
                    seen.add(no); last = no
                    arts.append({"no": no, "heading": ref[:120], "quelle": "eigen", "zeile": i})
                    continue                           # «§ 23 1 / Art. 35 Abs. 1 lit. a StG»: the StV heading
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
        arts.append({"no": no, "heading": head[:120], "quelle": src, "zeile": i})
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
    nl = na = nn = nz = 0
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
            if not ex:
                # a row stored with the bare number («88» for «Art. 88») is the same article: it gets the
                # notation, keeps its id, its citations and its identifier (kennungen.artikel_nummer)
                ex = c.execute("SELECT id FROM article WHERE law_id=? AND article_no=?",
                               [lid, a["no"].split(None, 1)[1]]).fetchone()
                if ex:
                    c.execute("UPDATE article SET article_no=? WHERE id=?", [a["no"], ex["id"]])
                    nn += 1
            if ex:
                c.execute("UPDATE article SET heading=?, last_checked=? WHERE id=?", [a["heading"], lc, ex["id"]])
                # a citation shows the verification level of its article (validate_db: one source)
                nz += c.execute("UPDATE data_field_legal_basis SET last_checked=? WHERE article_id=? "
                                "AND last_checked IS NOT ?", [lc, ex["id"], lc]).rowcount
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
    print(f"ingested: +{nl} laws, +{na} articles" + (f", {nn} bare numbers given their notation" if nn else "")
          + (f", {nz} citations given their article's verification level" if nz else ""))


if __name__ == "__main__":
    main()
