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
PROPOSALS_DIR  = os.path.join(ROOT, "proposals")
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
