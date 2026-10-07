"""One entry point for the databank: python3 -m citygov <command>, from the repository root
(no install needed; standard library only).

    python3 -m citygov build [--tresor] [--pdf]   every generated file from citygov.db, step by
                                                   step (./build.sh runs exactly this)
    python3 -m citygov validate [db]              the integrity gate: scripts/validate_db.py
    python3 -m citygov load <name> [args ...]     one command by its old script name:
                                                   python3 scripts/<name>.py [args ...]
    python3 -m citygov list                       every command with its purpose, and the build steps
    python3 -m citygov check-pages [args ...]     the page check: node scripts/check_pages.mjs
    python3 -m citygov test [args ...]            the tests: python3 -m unittest [args ...] in the
                                                   repository root (tests/)

Every documented command stays valid: ./build.sh and python3 scripts/<name>.py work as before.
`load`, `validate` and `check-pages` start exactly that command (same arguments, same output,
same exit code): this process becomes the command's process. `load` takes every name under
scripts/ — loaders, exporters, page builders and checks; `list` shows them by layer.

This module belongs to the package root, which imports no layer (core, checks, domain, load,
export, present): every command runs in a process of its own, through its wrapper under
scripts/, so `python3 -m citygov` stays light and a command behaves the same whichever way it
is started.
"""
import ast
import difflib
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
LAYERS = ("core", "checks", "domain", "load", "export", "present")

# ---- the build -------------------------------------------------------------------------------
# Every step is `<python> scripts/<name>.py <arguments>` in the repository root, in this order;
# <python> is .venv/bin/python3 when it exists, else the Python that runs this module. The first
# step that fails stops the build with its exit code. A step is (name, arguments, the word of
# the build without which it is skipped, the word of the build it is given when that is set).
BUILD = (
    # init_register.py: rewrites the DERIVED data inside citygov.db: the table canonical_attribute
    # and data_field.format_code; it also refreshes format_pattern and adds any new Dienststelle
    # name to dienststelle (tables it needs are created if missing). It and the next two steps
    # are the only ones that write to the DB, and only derived data
    ("init_register", (), None, None),
    # kennungen.py: permanent identifiers (table kennung): new objects get one, gone ones are
    # marked «entfallen», none is ever reused or re-pointed (a rename only on evidence a
    # re-inserted row cannot fake); refuses to mint into a missing or empty table; right after
    # init_register.py, which renumbers canonical_attribute; staging -> validate -> swap, writes
    # nothing when nothing changed. The vault and every export carry the identifiers
    ("kennungen", (), None, None),
    # rollen.py ableiten: Parteien und Rollen (stage B1, deterministic): rewrites partei_rolle,
    # formular_partei and datenpunkt_partei from the field layer and applies the loaded stage-B2
    # verdicts (partei_urteil) that still fit; staging -> validate -> swap, says «unverändert»
    # when nothing changed
    ("rollen", ("ableiten",), None, None),
    # build_datentresor.py: datentresor.db — only with --tresor (synthetic vault; needs the venv
    # with `cryptography`, and is not byte-reproducible because of random AES-GCM nonces). It
    # needs canonical_attribute/format_code (init_register) and the identifiers of the Angaben
    # (kennungen.py), and runs before export_json.py, which reads it for the Bürgersicht; it
    # reads citygov.db only
    ("build_datentresor", (), "--tresor", None),
    # export_json.py: data_export.json (base data every surface reads, one generated_at stamp for
    # the whole build) + today's entry in verlauf.json; stops with «ABBRUCH …» and writes nothing
    # when a layer fails, a sum does not add up or verlauf.json is unreadable. It computes the
    # parties per data point (rollen.py), the change-impact index (wirkung.py), the concepts
    # (konzepte.py: one preferred element per Angabe and role) and the register map with the
    # corrected prefill count and the time rule (register_map.py) once, puts the permanent
    # identifiers on every object and stamps the export contract (export_vertrag.py: version,
    # schema/*.schema.json, exportvertrag.json — rewritten only when the structure or a count
    # changed)
    ("export_json", (), None, None),
    # theme.py --check: the shared look (fonts, colours, tones, symbols, text sizes): every text
    # colour reaches 4.5:1 on its backgrounds and no colour, size or font literal is left in the
    # four page generators or their files under citygov/present/assets/; reads only
    ("theme", ("--check",), None, None),
    # build_flows.py: flows.html (inlines quellen/ch-geo.js; the profile prefill map is the
    # vorbefuellbar rule of data_export.json)
    ("build_flows", (), None, None),
    # export_llm.py: citygov_llm.json, citygov_datafields.jsonl, citygov_datarules.jsonl,
    # citygov_verzeichnis.json, citygov_prefill.json (identifiers and contract stamp as
    # export_json.py)
    ("export_llm", (), None, None),
    # export_ech_schema.py: citygov_ech_schemas.json (identifiers, contract stamp)
    ("export_ech_schema", (), None, None),
    # build_dashboard.py: dashboard.html — after the exports above, because its page «Datenmodell»
    # shows the version of every export as exportvertrag.json holds it once all of them are stamped
    ("build_dashboard", (), None, None),
    # export_vertrag.py: checks the export contract (read-only): every published export carries
    # the version exportvertrag.json records, matches its JSON Schema under schema/ and its counts
    ("export_vertrag", (), None, None),
    # kennungen.py --pruefen: every object has exactly one active identifier and every active
    # identifier names its object (read-only)
    ("kennungen", ("--pruefen",), None, None),
    # export_dossiers.py: dossiers/*.html + dossiers/index.html + dossiers/_repo.js (marker: the
    # repository is present); with --pdf also dossiers/*.pdf (local only, needs a local Chrome)
    ("export_dossiers", (), None, "--pdf"),
    # build_index.py: index.html — the landing page (GitHub Pages serves it at
    # https://jastephan63.github.io/citygov/) + 404.html
    ("build_index", (), None, None),
    # validate_db.py: final integrity check of the database (with the gates of the identifiers,
    # parties, law editions and registers; the register gate reads quellen/register/)
    ("validate_db", (), None, None),
)
WORDS = ("--tresor", "--pdf")
# then the sizes of the largest files, as `ls -lh` prints them
SIZES = ("dashboard.html", "flows.html", "data_export.json", "citygov_llm.json")
# then the tests (tests/; a failing test fails the build), and last the page check: it opens the
# built pages in a headless Chrome (scripts parse, every page starts without an error, bars add
# up, contrast, link colour, text size, file size, keyboard); needs Node and a local Chrome and
# is skipped without them; a Chrome that is found but does not start fails the build
# (CHROME_FLAGS=--no-sandbox in a container, CHECK_PAGES=skip to build without the check on
# purpose) — scripts/README.md
PAGE_CHECK = ("scripts", "check_pages.mjs")
SKIPPED = "Seitenprüfung übersprungen: Node oder Chrome nicht gefunden"
DONE = "done — open dashboard.html in a browser (or: python3 -m http.server 8917)"

BUILD_HELP = """usage: python3 -m citygov build [--tresor] [--pdf]
       ./build.sh [--tresor] [--pdf]

Every generated file from citygov.db, step by step (python3 -m citygov list shows the steps):
  --tresor   also rebuild datentresor.db (before export_json.py reads it)
  --pdf      also write dossiers/*.pdf (local only; a plain build before committing drops
             the PDF column from dossiers/index.html again)
The first step that fails stops the build with its exit code."""


def _python():
    """The Python of the build steps: .venv/bin/python3 when it exists (relative, as the steps
    run in the repository root), else this interpreter."""
    venv = os.path.join(".venv", "bin", "python3")
    return venv if os.access(os.path.join(ROOT, venv), os.X_OK) else sys.executable


def _run(argv):
    """Run one step with its output straight through; its exit code (a step ended by a signal
    as a shell reports it: 128 + the signal number)."""
    sys.stdout.flush()
    sys.stderr.flush()
    code = subprocess.call(argv)
    return 128 - code if code < 0 else code


def _become(argv, cwd=None):
    """Replace this process by argv (same input and output, same exit code, same signals as
    when argv is started by hand); where a process cannot be replaced, run argv and pass its
    exit code on."""
    sys.stdout.flush()
    sys.stderr.flush()
    if cwd:
        os.chdir(cwd)
    if os.name == "posix":
        os.execv(argv[0], argv)
    return _run(argv)


def build(words):
    """The build. ./build.sh passes its own words after «--»: those are read as build.sh always
    read them (only --tresor and --pdf count, anywhere, any other word is ignored). Without
    «--» a word other than --tresor and --pdf is an error, and -h / --help shows the usage."""
    if words[:1] == ["--"]:
        words = words[1:]
    else:
        if any(w in ("-h", "--help") for w in words):
            print(BUILD_HELP)
            return 0
        unknown = [w for w in words if w not in WORDS]
        if unknown:
            print(f"python3 -m citygov build: unknown argument {' '.join(unknown)}\n\n{BUILD_HELP}",
                  file=sys.stderr)
            return 2
    line = " " + " ".join(words) + " "
    given = {w for w in WORDS if f" {w} " in line}
    os.chdir(ROOT)
    py = _python()
    for name, args, only_with, passes in BUILD:
        if only_with and only_with not in given:
            continue
        code = _run([py, f"scripts/{name}.py", *args, *([passes] if passes in given else [])])
        if code:
            return code
    code = _run(["bash", "-o", "pipefail", "-c",
                 "ls -lh " + " ".join(SIZES) + " | awk '{print \"  \" $5 \"\\t\" $9}'"])
    if code:
        return code
    code = _run([py, "-m", "unittest"])
    if code:
        return code
    if shutil.which("node"):
        code = _run(["node", "/".join(PAGE_CHECK)])
        if code:
            return code
    else:
        print(SKIPPED, flush=True)
    print(DONE, flush=True)
    return 0


# ---- the commands under scripts/ ---------------------------------------------------------------
def _script(name):
    """scripts/<name> as a path relative to the working directory (as the documentation types it
    from the repository root)."""
    return os.path.relpath(os.path.join(SCRIPTS, name))


def _purpose(path):
    """The first sentence of the docstring of a module (read with ast, never imported)."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = ast.get_docstring(ast.parse(fh.read())) or ""
    except (OSError, SyntaxError):
        return ""
    para = " ".join(doc.strip().split("\n\n")[0].split())
    first = re.split(r"(?<=[.!?])\s", para, maxsplit=1)[0]
    return first if len(first) <= 100 else first[:99].rsplit(" ", 1)[0] + " …"


def commands():
    """{name: (layer, module the wrapper runs)} for every scripts/<name>.py, read from the
    wrappers (runpy.run_module("citygov.<layer>.<module>", …)); nothing is imported."""
    out = {}
    for f in sorted(os.listdir(SCRIPTS)):
        if not f.endswith(".py"):
            continue
        with open(os.path.join(SCRIPTS, f), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        target = next((n.args[0].value for n in ast.walk(tree)
                       if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "run_module" and n.args and isinstance(n.args[0], ast.Constant)), None)
        if target:
            out[f[:-3]] = (target.split(".")[1], target)
    return out


def list_commands():
    cmds = commands()
    width = max(len(n) for n in cmds) + 2
    print("python3 -m citygov load <name> [args ...] runs python3 scripts/<name>.py [args ...]; "
          "the commands by layer:")
    for layer in LAYERS:
        names = sorted(n for n, (lay, _) in cmds.items() if lay == layer)
        if not names:
            continue
        print(f"\n{layer} ({len(names)})")
        for n in names:
            mod = cmds[n][1]
            print(f"  {n:<{width}}{_purpose(os.path.join(ROOT, *mod.split('.')) + '.py')}")
    print("\npython3 -m citygov build (./build.sh), in this order:")
    for i, (name, args, only_with, passes) in enumerate(BUILD, 1):
        cmd = " ".join([f"scripts/{name}.py", *args] + ([f"[{passes}]"] if passes else []))
        note = (f"only with {only_with}" if only_with else
                f"given {passes} when the build has it" if passes else "")
        print(f"  {i:>2}  {cmd:<44}{note}".rstrip())
    print(f"      {'ls -lh ' + ' '.join(SIZES)}")
    print(f"      {'python3 -m unittest':<44}the tests (tests/)")
    print(f"      {'node ' + '/'.join(PAGE_CHECK):<44}the page check (skipped without Node)")
    return 0


def load(args):
    if not args or args[0] in ("-h", "--help"):
        print("usage: python3 -m citygov load <name> [args ...]   (runs python3 scripts/<name>.py "
              "[args ...]; python3 -m citygov list shows every name)", file=sys.stderr if not args else sys.stdout)
        return 2 if not args else 0
    name = args[0][:-3] if args[0].endswith(".py") else args[0]
    cmds = commands()
    if name not in cmds:
        near = difflib.get_close_matches(name, list(cmds), n=3)
        print(f"python3 -m citygov load: no command scripts/{name}.py"
              + (f" — did you mean {', '.join(near)}?" if near else "")
              + " (python3 -m citygov list shows every name)", file=sys.stderr)
        return 2
    return _become([sys.executable, _script(f"{name}.py"), *args[1:]])


def check_pages(args):
    node = shutil.which("node")
    if not node:
        print(SKIPPED, flush=True)
        return 0
    return _become([node, _script(PAGE_CHECK[1]), *args])


def test(args):
    return _become([sys.executable, "-m", "unittest", *args], cwd=ROOT)


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip(), file=sys.stdout if argv else sys.stderr)
        return 0 if argv else 2
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == "build":
            return build(args)
        if cmd == "validate":
            return _become([sys.executable, _script("validate_db.py"), *args])
        if cmd == "load":
            return load(args)
        if cmd == "list":
            return list_commands()
        if cmd == "check-pages":
            return check_pages(args)
        if cmd == "test":
            return test(args)
    except KeyboardInterrupt:
        return 130
    print(f"python3 -m citygov: unknown command {cmd!r} — build, validate, load, list, check-pages, test "
          "(python3 -m citygov --help)", file=sys.stderr)
    return 2
