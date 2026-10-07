"""The layer order of the package, by a static scan of every import under citygov/ (read with
ast, never imported):

    core <- checks <- domain <- (load, export) <- present

A module imports its own layer and the layers below it; export and present never import load,
load never imports export or present. This holds at module level and inside functions,
classes and blocks, for `import citygov.x.y`, `from citygov.x import y`, `from citygov import x`,
relative imports and dynamic imports with a constant name (importlib.import_module, __import__,
runpy.run_module). The package root (citygov/__init__.py, __main__.py, cli.py) imports no layer:
the command line starts every command in a process of its own.

One import of a higher layer is part of the design, the registry trigger: validate_db (checks)
runs gates that live in domain; domain adds them to citygov.checks.registry when the PACKAGE
citygov.domain is imported, and validate_db imports that package once (`import citygov.domain`,
nothing from it). Exactly that statement, exactly once in checks, is accepted.

And the package __init__ files stay light: unittest discovery imports every one of them before
tests/__init__.py points CITYGOV_DB at a private copy, so no __init__ under citygov/, and nothing
it imports at module level (followed module by module), may import citygov.core.common.
"""
import ast
import os

from tests import ROOT, TestCase

from citygov.cli import LAYERS
ALLOWED = {"core": {"core"},
           "checks": {"core", "checks"},
           "domain": {"core", "checks", "domain"},
           "load": {"core", "checks", "domain", "load"},
           "export": {"core", "checks", "domain", "export"},
           "present": {"core", "checks", "domain", "export", "present"},
           "<root>": set()}
TRIGGER = ("checks", "citygov.domain")
DYNAMIC = {("importlib", "import_module"), ("runpy", "run_module"), (None, "__import__"), (None, "import_module")}


def layer_of(modname):
    """The layer of a module name (or of a name inside a module): one of LAYERS, «<root>» for the
    package itself and the modules directly in it (cli, __main__), None outside the package.
    test_every_module_is_in_a_layer holds that no other folder exists."""
    parts = modname.split(".")
    if parts[0] != "citygov":
        return None
    return parts[1] if len(parts) > 1 and parts[1] in LAYERS else "<root>"


def _targets(node, me, is_pkg):
    """[(imported module name, kind)] of one node."""
    out = []
    if isinstance(node, ast.Import):
        out += [(a.name, "import") for a in node.names]
    elif isinstance(node, ast.ImportFrom):
        if node.level:
            base = me.split(".") if is_pkg else me.split(".")[:-1]
            base = base[:len(base) - (node.level - 1)]
            mod = ".".join(base + ([node.module] if node.module else []))
        else:
            mod = node.module or ""
        out.append((mod, "from"))
        out += [(mod + "." + a.name, "from-name") for a in node.names if a.name != "*"]
    elif isinstance(node, ast.Call):
        f = node.func
        key = (f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else None,
               f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None)
        if key in DYNAMIC and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            out.append((node.args[0].value, "dynamic"))
    return out


def scan(sources):
    """(violations, triggers) for {relative path under the repository: source text}."""
    violations, triggers = [], []
    for rel, src in sorted(sources.items()):
        parts = rel[:-3].split("/")
        is_pkg = parts[-1] == "__init__"
        me = ".".join(parts[:-1] if is_pkg else parts)
        mine = layer_of(me)
        for node in ast.walk(ast.parse(src, filename=rel)):
            for mod, kind in _targets(node, me, is_pkg):
                lay = layer_of(mod)
                if lay is None:
                    continue
                if kind == "from-name" and lay == layer_of(mod.rsplit(".", 1)[0]):
                    continue                     # a name inside a module already counted by its "from"
                if lay in ALLOWED.get(mine, set()) or (mine == lay == "<root>") or mod == "citygov":
                    continue
                desc = f"{rel} [{mine}] imports {mod} [{lay}] (line {node.lineno}, {kind})"
                if (mine, mod, kind) == (TRIGGER[0], TRIGGER[1], "import") and \
                        all(a.asname is None for a in node.names):
                    triggers.append(desc)
                else:
                    violations.append(desc)
    if len(triggers) > 1:
        violations += [t + " — more than one registry trigger" for t in triggers]
    return violations, triggers


def package_sources():
    out = {}
    for dp, dns, fns in os.walk(os.path.join(ROOT, "citygov")):
        dns[:] = sorted(d for d in dns if d != "__pycache__")
        for f in sorted(fns):
            if f.endswith(".py"):
                p = os.path.join(dp, f)
                with open(p, encoding="utf-8") as fh:
                    out[os.path.relpath(p, ROOT).replace(os.sep, "/")] = fh.read()
    return out


def _module_level(stmts):
    """The import statements that run when a module is imported: at module level, also inside
    if / try / with / for / while there, never inside a function or a class."""
    for n in stmts:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            yield n
            continue
        for feld in ("body", "orelse", "finalbody"):
            yield from _module_level(getattr(n, feld, []) or [])
        for h in getattr(n, "handlers", []) or []:
            yield from _module_level(h.body)


def loaded_on_import(sources, start):
    """The modules of the package that importing each module of `start` loads, following the
    module-level imports from module to module (a module also loads its parent packages)."""
    files = {}
    for rel in sources:
        parts = rel[:-3].split("/")
        files[".".join(parts[:-1] if parts[-1] == "__init__" else parts)] = rel

    def with_parents(name):
        parts = name.split(".")
        return {".".join(parts[:i]) for i in range(1, len(parts) + 1)} & set(files)

    seen, todo = set(), set()
    for m in start:
        todo |= with_parents(m)
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        rel = files[m]
        is_pkg = rel.endswith("/__init__.py")
        for node in _module_level(ast.parse(sources[rel], filename=rel).body):
            for mod, _kind in _targets(node, m, is_pkg):
                todo |= with_parents(mod) - seen
    return seen


def package_inits(sources):
    return sorted(".".join(rel.split("/")[:-1]) for rel in sources if rel.endswith("/__init__.py"))


class LayerOrder(TestCase):
    def test_no_import_goes_against_the_order(self):
        sources = package_sources()
        self.assertGreater(len(sources), 90)
        violations, triggers = scan(sources)
        self.assertEqual(violations, [])
        self.assertEqual(len(triggers), 1, triggers)
        self.assertTrue(triggers[0].startswith("citygov/checks/validate_db.py"), triggers)

    def test_every_module_is_in_a_layer(self):
        for rel in package_sources():
            parts = rel.split("/")
            with self.subTest(module=rel):
                self.assertTrue(len(parts) == 2 or parts[1] in LAYERS, "a module outside the six layers")

    def test_the_scan_fires(self):
        """The scan itself: each kind of import against the order is found."""
        cases = {
            "citygov/domain/x.py": "from citygov.load import init_register",
            "citygov/core/x.py": "def f():\n    from citygov.checks.validate_db import validate",
            "citygov/export/x.py": "import citygov.load.run_begriffe",
            "citygov/load/x.py": "from ..present import build_index",
            "citygov/present/x.py": "import importlib\nimportlib.import_module('citygov.load.init_db')",
            "citygov/cli.py": "from citygov.core import common",
            "citygov/checks/x.py": "from citygov.domain import gates",
        }
        for rel, src in cases.items():
            with self.subTest(case=rel):
                violations, _ = scan({rel: src})
                self.assertEqual(len(violations), 1, violations)
        _, triggers = scan({"citygov/checks/x.py": "def f():\n    import citygov.domain"})
        self.assertEqual(len(triggers), 1)
        violations, _ = scan({"citygov/checks/x.py": "import citygov.domain", "citygov/checks/y.py": "import citygov.domain"})
        self.assertEqual(len(violations), 2, "a second registry trigger")


class LightInits(TestCase):
    def test_no_package_init_loads_common(self):
        """What unittest discovery loads before tests/__init__.py runs: every package __init__
        and what they import at module level — today domain/gates.py and checks/registry.py."""
        sources = package_sources()
        inits = package_inits(sources)
        self.assertEqual(len(inits), 1 + len(LAYERS))
        loaded = loaded_on_import(sources, inits)
        self.assertIn("citygov.domain.gates", loaded)           # the walk follows the imports
        self.assertIn("citygov.checks.registry", loaded)
        self.assertNotIn("citygov.core.common", loaded,
                         "a package __init__ (or a module it imports) imports citygov.core.common: "
                         + ", ".join(sorted(loaded)))

    def test_the_walk_fires(self):
        sources = {"citygov/__init__.py": "", "citygov/core/__init__.py": "", "citygov/core/common.py": "",
                   "citygov/present/__init__.py": "def f():\n    from citygov.core import common\n",
                   "citygov/domain/__init__.py": "from citygov.domain import gates\n",
                   "citygov/domain/gates.py": "try:\n    from ..core.common import ROOT\nexcept ImportError:\n    pass\n"}
        self.assertNotIn("citygov.core.common", loaded_on_import(sources, ["citygov.present"]))
        self.assertIn("citygov.core.common", loaded_on_import(sources, ["citygov.domain"]))

