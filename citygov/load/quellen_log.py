"""The harvest log of the two read-only sources (DVSH modeller, SHEP portal).

Both loaders replace their mirror table wholesale (dvsh_service, shep_service).
Before they do, record_changes() compares the rows the databank holds with the
rows just loaded and writes what is new, removed or changed into
quellen_aenderung, dated with the harvest; quellen_abzug keeps one row per
harvest. The dashboard reads both («Änderungen seit dem letzten Abzug»).

A harvest that is already logged is not compared again: a second run with the
same file would compare the new state with itself and erase the record.
"""
import json

DDL = """
CREATE TABLE IF NOT EXISTS quellen_abzug (
    quelle TEXT NOT NULL CHECK (quelle IN ('DVSH','SHEP')),
    datum  TEXT NOT NULL,
    datei  TEXT,
    anzahl INTEGER,
    PRIMARY KEY (quelle, datum));
CREATE TABLE IF NOT EXISTS quellen_aenderung (
    quelle     TEXT NOT NULL CHECK (quelle IN ('DVSH','SHEP')),
    abzug      TEXT NOT NULL,
    vorher     TEXT,
    schluessel TEXT NOT NULL,
    service_id INTEGER,
    titel      TEXT,
    art        TEXT NOT NULL CHECK (art IN ('neu','entfernt','geaendert')),
    felder     TEXT,
    PRIMARY KEY (quelle, abzug, schluessel));
"""


def snapshot(c, table, key, cols):
    """{key: {col: value}} of the mirror rows before the reload."""
    have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
    use = [k for k in cols if k in have]
    return {str(r[key]): {k: r[k] for k in use + ["service_id", "title"] if k in have}
            for r in c.execute(f"SELECT {', '.join(sorted(set([key, 'service_id', 'title'] + use)))} FROM {table}")}


def _same(a, b):
    """Equal as stored, or equal once JSON text is decoded (key order, spacing)."""
    if a == b:
        return True
    try:
        return json.loads(a) == json.loads(b)
    except Exception:
        return False


def record_changes(c, quelle, abzug, datei, anzahl, before, after, cols, vorher_arg=None):
    """Write the harvest row and its changes. Returns (logged, counts) — logged
    is False when this harvest was logged already (nothing is touched then)."""
    c.executescript(DDL)
    if c.execute("SELECT 1 FROM quellen_abzug WHERE quelle=? AND datum=?", [quelle, abzug]).fetchone():
        return False, {}
    prev = c.execute("SELECT MAX(datum) FROM quellen_abzug WHERE quelle=? AND datum<?", [quelle, abzug]).fetchone()[0]
    vorher = prev or vorher_arg
    counts = {"neu": 0, "entfernt": 0, "geaendert": 0}
    if before:          # the very first load has nothing to compare against
        for k in sorted(set(after) | set(before)):
            a, b = after.get(k), before.get(k)
            if a and not b:
                art, felder, row = "neu", None, a
            elif b and not a:
                art, felder, row = "entfernt", None, b
            else:
                diff = [col for col in cols if col in a and col in b and not _same(a[col], b[col])]
                if not diff:
                    continue
                art, felder, row = "geaendert", json.dumps(diff, ensure_ascii=False), a
            c.execute("INSERT INTO quellen_aenderung(quelle,abzug,vorher,schluessel,service_id,titel,art,felder)"
                      " VALUES(?,?,?,?,?,?,?,?)",
                      [quelle, abzug, vorher, k, row.get("service_id"), row.get("title"), art, felder])
            counts[art] += 1
    if vorher and not c.execute("SELECT 1 FROM quellen_abzug WHERE quelle=? AND datum=?", [quelle, vorher]).fetchone():
        c.execute("INSERT INTO quellen_abzug(quelle,datum,datei,anzahl) VALUES(?,?,?,?)",
                  [quelle, vorher, None, len(before) or None])
    c.execute("INSERT INTO quellen_abzug(quelle,datum,datei,anzahl) VALUES(?,?,?,?)",
              [quelle, abzug, datei, anzahl])
    return True, counts
