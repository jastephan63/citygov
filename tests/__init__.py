"""The tests of the package citygov (standard library only: unittest).

    python3 -m unittest                   every test, from the repository root
    python3 -m citygov test               the same
    python3 -m unittest tests.test_gates  one file

./build.sh runs them after validate_db.py and before the page check; a failing test fails
the build. They take about 45 seconds.

No test writes the shared database. Importing this package — unittest does so before any test
module, so before any test imports citygov — copies citygov.db, schema.sql and datentresor.db
(the ones CITYGOV_DB / CITYGOV_SCHEMA name, else the repository's) into a temporary folder,
makes the copies read-only and points CITYGOV_DB and CITYGOV_SCHEMA at them; the folder is
removed when the run ends. quellen/ is linked beside the copies, because export_json.py reads
quellen/verlauf_bemerkungen.json and datentresor.db next to the database file. A test reads the
copy through lesen() (read-only) and tampers only with an in-memory copy (kopie()).
"""
import atexit
import contextlib
import io
import os
import pathlib
import shutil
import sqlite3
import stat
import sys
import tempfile
import unittest
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if "citygov.core.common" in sys.modules:
    # it would hold the paths of the shared database: they are read once, when it is imported
    raise ImportError("tests: citygov.core.common was imported before the tests set CITYGOV_DB — "
                      "run the tests with python3 -m unittest from the repository root")

_QUELLE_DB = os.environ.get("CITYGOV_DB") or os.path.join(ROOT, "citygov.db")
_QUELLE_SCHEMA = os.environ.get("CITYGOV_SCHEMA") or os.path.join(ROOT, "schema.sql")
TMP = tempfile.mkdtemp(prefix="citygov-tests-")
atexit.register(shutil.rmtree, TMP, True)
DB = os.path.join(TMP, "citygov.db")
SCHEMA = os.path.join(TMP, "schema.sql")
for _src, _dst in ((_QUELLE_DB, DB), (_QUELLE_SCHEMA, SCHEMA),
                   (os.path.join(os.path.dirname(_QUELLE_DB), "datentresor.db"), os.path.join(TMP, "datentresor.db"))):
    if os.path.exists(_src):
        shutil.copyfile(_src, _dst)
        os.chmod(_dst, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
_QUELLEN = os.path.join(os.path.dirname(_QUELLE_DB), "quellen")
if os.path.isdir(_QUELLEN):
    os.symlink(_QUELLEN, os.path.join(TMP, "quellen"))
os.environ["CITYGOV_DB"] = DB
os.environ["CITYGOV_SCHEMA"] = SCHEMA


def lesen():
    """A read-only connection to the private copy, rows by name (as common.connect gives them)."""
    conn = sqlite3.connect(pathlib.Path(DB).as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def kopie():
    """An in-memory copy of the private copy to tamper with (rows by name; foreign keys are not
    enforced, so a test can break them)."""
    quelle = lesen()
    mem = sqlite3.connect(":memory:")
    quelle.backup(mem)
    quelle.close()
    mem.row_factory = sqlite3.Row
    return mem


@contextlib.contextmanager
def still():
    """What the package prints while a test calls it goes to a buffer (the build log shows only
    the test result); yields the buffer."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        yield buf


_EXPORT = []


def export_daten():
    """(connection, data): the export as export_json.build computes it from the private copy, in
    memory (nothing is written; computed once per run, as the command lines of konzepte.py and
    gestaltung_export.py compute it)."""
    if not _EXPORT:
        from citygov.export import export_json
        conn = lesen()
        atexit.register(conn.close)
        with still():
            data, _todo = export_json.build(conn)
        _EXPORT.append((conn, data))
    return _EXPORT[0]


class TestCase(unittest.TestCase):
    """A test of this suite. ResourceWarning is not shown: some functions of the package leave a
    file or a database connection to the garbage collector (validate_db.judgment_layer_checks:
    its scratch connection and schema.sql; register_map, line 1022, and gesetz_titel, line 54:
    json.load(open(…)); the in-memory copies of gestaltung_export._selbsttest), which unittest
    would report with object addresses, so the build log would differ from run to run. Every
    other warning is shown."""

    def setUp(self):
        warnings.filterwarnings("ignore", category=ResourceWarning)
