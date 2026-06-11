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
