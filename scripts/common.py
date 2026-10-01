"""Shared helpers for the citygov build/ingest scripts.

Pure stdlib. No network. Paths are resolved relative to the project root so the
scripts can be run from anywhere.
"""
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH        = os.path.join(ROOT, "citygov.db")
SCHEMA_PATH    = os.path.join(ROOT, "schema.sql")
EXPORT_PATH    = os.path.join(ROOT, "data_export.json")
DASHBOARD_PATH = os.path.join(ROOT, "dashboard.html")
FORMS_DIR      = os.path.join(ROOT, "forms")
INVENTORY_DIR  = os.path.join(ROOT, "inventory")
PROPOSALS_DIR  = os.path.join(ROOT, "proposals")   # read only by scripts/deprecated/extract_form.py
LOGS_DIR       = os.path.join(ROOT, "logs")


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def log(name, message):
    """Append a line to logs/<name>.log (timestamp passed in by caller if wanted)."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(os.path.join(LOGS_DIR, name), "a", encoding="utf-8") as fh:
        fh.write(message.rstrip("\n") + "\n")


# ---- shared normalisation ---------------------------------------------------
# Two families exist on purpose and must not be mixed:
#   norm_ascii  — fuzzy matching of names across sources (subfield pairs, DVSH
#                 titles): case-, accent- and punctuation-insensitive.
#   norm_label  — the KEY of begriff_label (ech_element_id, label_norm): only
#                 whitespace collapsed and a trailing ':'/'*' dropped, case folded.
#                 Every loader and exporter that touches begriff_label uses THIS
#                 one; validate_db.py checks label_norm == norm_label(label).
import re as _re
import unicodedata as _ud


def norm_ascii(s):
    s = _ud.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not _ud.combining(ch))
    return _re.sub(r"[^a-z0-9]+", " ", s).strip()


def norm_label(s):
    return _re.sub(r"\s+", " ", _re.sub(r"[:*]+\s*$", "", (s or "").strip())).lower()


def pl(n, singular, plural):
    """'1 Regel' / '2 Regeln' — never «1 Regeln»."""
    return f"{n} {singular if n == 1 else plural}"


def _layer_skipped(name, ex):
    """Exporters: a layer whose table/column does not exist yet is skipped LOUDLY
    (stderr); anything else aborts the export — a half-empty export with a green
    build was the worst failure mode."""
    import sys
    if isinstance(ex, sqlite3.OperationalError) and ("no such table" in str(ex) or "no such column" in str(ex)):
        print(f"  LAYER SKIPPED {name}: {ex}", file=sys.stderr)
        return
    raise RuntimeError(f"export layer '{name}' failed: {ex}") from ex


# Paths of the author's machine that must never reach a published file: the
# sibling source folders (../Verwaltung, ../Gesetze, ../DVSH, ../formflows) and
# absolute macOS home or temp paths. A URL path («admin.ch/…/home/…») is not
# one: the absolute paths count only where no host name runs into them.
# Exporters call assert_no_local_paths() on the exact text they are about to write.
LOCAL_PATH = _re.compile(r"\.\./(?:Verwaltung|Gesetze|DVSH|formflows)\b|(?<![\w.%-])/(?:Users|private)/")


def assert_no_local_paths(name, text):
    """Stop the export when its text names a local path (the first hits are shown)."""
    hits = [m.group(0) for m in LOCAL_PATH.finditer(text)]
    if hits:
        import sys
        ctx = []
        for m in list(LOCAL_PATH.finditer(text))[:3]:
            ctx.append(text[max(0, m.start() - 60):m.end() + 40].replace("\n", " "))
        sys.exit(f"ABBRUCH: {name} enthielte {len(hits)} lokale Pfade ({', '.join(sorted(set(hits)))}) — "
                 "nichts geschrieben. Beispiele: " + " | ".join(ctx))


# ---- the size of a published page, as the pages state it -----------------------
# dashboard.html says how large it must be (a truncated download is the commonest
# failure) and index.html repeats it; both measure the real bytes with these two.
def size_txt(n_bytes):
    """«30 MB» for «knapp 30 MB»: rounded UP to the next 10 MB, so it is true in
    decimal and in binary units."""
    import math
    return f"{int(math.ceil(n_bytes / 1e7) * 10)} MB"


def net_size_txt(data):
    """«4 MB» for «über das Netz etwa 4 MB»: the gzip size of the page bytes (GitHub
    Pages sends the page compressed), rounded to whole MB, never below 1 MB."""
    import gzip
    return f"{max(1, round(len(gzip.compress(data, compresslevel=6)) / 1e6))} MB"


def klartext(t):
    """Reader-facing reasoning without the review's shorthand («Korpus» = the forms)."""
    if not t:
        return t
    t = _re.sub(r"\bim Korpus\b", "in den Formularen", t)
    t = _re.sub(r"\bdes Korpus\b", "der Formulare", t)
    return _re.sub(r"\bKorpus\b", "Formularbestand", t)
