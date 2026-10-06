"""Shared helpers for the citygov build/ingest scripts.

Pure stdlib. No network. Paths are resolved relative to the project root so the
scripts can be run from anywhere.
"""
import os
import sqlite3

# the repository root: this file is citygov/core/common.py
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# CITYGOV_DB / CITYGOV_SCHEMA point a loader at a private copy of the database and
# its schema (develop or test a new layer without touching the shared files);
# unset, they are the repository's own files.
DB_PATH        = os.environ.get("CITYGOV_DB") or os.path.join(ROOT, "citygov.db")
SCHEMA_PATH    = os.environ.get("CITYGOV_SCHEMA") or os.path.join(ROOT, "schema.sql")
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


class LayerError(RuntimeError):
    """An export layer failed for another reason than a table the databank does not
    have (yet). It stops the export and names the layer; it is never caught as a skip."""


# the layers the running export skipped, as (layer, missing table) — the exporter
# repeats them at the end of its output, where a line among 190 others is not lost
SKIPPED_LAYERS = []
_SCHEMA_TABLES = None


def schema_tables():
    """The tables schema.sql declares (read once). A table is «genuinely missing»
    only when it is one of these and the database does not have it."""
    global _SCHEMA_TABLES
    if _SCHEMA_TABLES is None:
        try:
            scratch = sqlite3.connect(":memory:")
            with open(SCHEMA_PATH, encoding="utf-8") as fh:
                scratch.executescript(fh.read())
            _SCHEMA_TABLES = {r[0] for r in scratch.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            scratch.close()
        except (OSError, sqlite3.Error):
            _SCHEMA_TABLES = set()          # no readable schema: nothing counts as known, every miss is fatal
    return _SCHEMA_TABLES


def _layer_skipped(name, ex, tables=None):
    """Exporters call this in the except branch of a layer. A layer is skipped — LOUDLY
    (stderr, and listed in SKIPPED_LAYERS) — only when its table is genuinely missing:
    SQLite says «no such table: T» and T is a table of schema.sql (or of `tables`, for a
    second database such as datentresor.db) that this database does not have. Everything
    else stops the export with a LayerError that names the layer: a missing column, a
    table name schema.sql does not know (a typo), a failing helper, a wording gate. A
    half-empty export with a green build was the worst failure mode."""
    import sys
    if isinstance(ex, LayerError):
        raise ex                            # an inner layer already said what failed
    m = _re.match(r"no such table: (?:main\.)?(\w+)", str(ex)) if isinstance(ex, sqlite3.OperationalError) else None
    if m and m.group(1) in (schema_tables() if tables is None else tables):
        if (name, m.group(1)) not in SKIPPED_LAYERS:
            SKIPPED_LAYERS.append((name, m.group(1)))
            print(f"  LAYER SKIPPED {name}: Tabelle {m.group(1)} fehlt in dieser Databank", file=sys.stderr)
        return
    raise LayerError(f"export layer '{name}' failed: {type(ex).__name__}: {ex}") from ex


def dossier_slug(service):
    """File name (without .html) of a service's dossier under dossiers/ — ONE rule for
    export_dossiers.py (writes the file) and export_json.py (services[].dossier_slug,
    which the dashboard links to)."""
    return (_re.sub(r"[^a-z0-9]+", "-", (service.get("slug") or service["name"]).lower()).strip("-")[:80]
            or f"service-{service['id']}")


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
