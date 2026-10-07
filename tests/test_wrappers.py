"""The wrappers: every scripts/<name>.py is the same thin file, resolves to its module of the
package, runs it as __main__ with the arguments untouched, and hands `import <name>` the module
itself — so every documented command `python3 scripts/<name>.py …` and every subprocess call of
the loaders keeps its arguments, output and exit code.
"""
import ast
import importlib
import importlib.util
import os
import re
import runpy
import subprocess
import sys
import unittest
from unittest import mock

from tests import ROOT, TestCase

SCRIPTS = os.path.join(ROOT, "scripts")
LAYERS = ("core", "checks", "domain", "load", "export", "present")


def wrappers():
    return sorted(f[:-3] for f in os.listdir(SCRIPTS) if f.endswith(".py"))


def _source(name):
    with open(os.path.join(SCRIPTS, name + ".py"), encoding="utf-8") as fh:
        return fh.read()


def _shape(name):
    """(the wrapper's statements as an AST dump with the two module names replaced, run target,
    import target)."""
    tree = ast.parse(_source(name))
    body = tree.body[1:] if isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) \
        else tree.body
    found = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.args \
                and isinstance(n.args[0], ast.Constant) and n.func.attr in ("run_module", "import_module"):
            found[n.func.attr] = n.args[0].value
    dump = re.sub(r"Constant\(value='citygov\.[\w.]+'\)", "Constant(value=MODULE)", ast.dump(ast.Module(body, [])))
    return dump, found.get("run_module"), found.get("import_module")


def _python(*args, **kw):
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, timeout=120, **kw)


class Wrappers(TestCase):
    def test_one_template(self):
        names = wrappers()
        self.assertGreaterEqual(len(names), 88)
        shapes = {name: _shape(name)[0] for name in names}
        template = shapes["common"]
        for name in names:
            with self.subTest(wrapper=name):
                self.assertEqual(shapes[name], template, "differs from the wrapper template (scripts/common.py)")

    def test_each_resolves_to_its_module(self):
        for name in wrappers():
            with self.subTest(wrapper=name):
                _dump, run, imp = _shape(name)
                # an import gets the module of the same name; a command runs it, or its command line
                # <name>_cli where that needs a higher layer than the module
                self.assertRegex(imp, r"^citygov\.(%s)\.%s$" % ("|".join(LAYERS), re.escape(name)))
                self.assertIn(run, [imp] + [f"citygov.{lay}.{name}_cli" for lay in LAYERS])
                for target in {run, imp}:
                    spec = importlib.util.find_spec(target)
                    self.assertIsNotNone(spec, target)
                    self.assertTrue(os.path.isfile(spec.origin), spec.origin)
                if run != imp:                    # a command line of its own starts in its main block
                    with open(importlib.util.find_spec(run).origin, encoding="utf-8") as fh:
                        tree = ast.parse(fh.read())
                    self.assertTrue(any(isinstance(n, ast.If) and "__main__" in ast.dump(n.test) for n in tree.body),
                                    f"{run} has no main block")

    def test_runs_its_module_as_main_with_the_arguments_untouched(self):
        for name in wrappers():
            path = os.path.join(SCRIPTS, name + ".py")
            argv = [path, "--erstens", "zwei drei", "-x"]
            seen = []

            def run_module(mod, run_name=None, **kw):
                seen.append((mod, run_name, list(sys.argv), kw))

            with self.subTest(wrapper=name), mock.patch.object(sys, "argv", list(argv)), \
                    mock.patch.object(sys, "path", list(sys.path)), mock.patch.object(runpy, "run_module", run_module):
                exec(compile(_source(name), path, "exec"), {"__name__": "__main__", "__file__": path})
                self.assertEqual(seen, [(_shape(name)[1], "__main__", argv, {})])

    def test_import_gives_the_module_itself(self):
        for name in wrappers():
            path = os.path.join(SCRIPTS, name + ".py")
            target = _shape(name)[2]
            sentinel = object()
            asked = []

            def import_module(mod, package=None):
                asked.append(mod)
                return sentinel

            before = sys.modules.get(name, sentinel)
            with self.subTest(wrapper=name), mock.patch.object(sys, "path", list(sys.path)), \
                    mock.patch.object(importlib, "import_module", import_module):
                try:
                    exec(compile(_source(name), path, "exec"), {"__name__": name, "__file__": path})
                    self.assertEqual(asked, [target])
                    self.assertIs(sys.modules[name], sentinel)
                finally:                          # the entry the wrapper set is this test's, not the run's
                    if before is sentinel:
                        sys.modules.pop(name, None)
                    else:
                        sys.modules[name] = before

    def test_a_real_run_is_the_package_module(self):
        """One command through its wrapper and as the package module: the same output and exit code
        (exit 1: an identifier that was never issued). Not compared with --help: since Python 3.14
        argparse names a module started with -m by its module name, a wrapper by its file name."""
        args = ["--aufloesen", "sh:formular:gibt-es-nicht"]
        alt = _python("scripts/kennungen.py", *args)
        neu = _python("-m", "citygov.load.kennungen_cli", *args)
        self.assertEqual(alt.returncode, 1, alt.stderr.decode(errors="replace")[-400:])
        self.assertEqual((alt.returncode, alt.stdout, alt.stderr), (neu.returncode, neu.stdout, neu.stderr))


if __name__ == "__main__":
    unittest.main()
