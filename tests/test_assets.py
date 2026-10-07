"""The page code under citygov/present/assets/: every script file parses (node --check; skipped
when Node is missing — the page check of the build parses the scripts inlined in the built
pages as well), and the check fires on a broken one.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from tests import ROOT, TestCase

ASSETS = os.path.join(ROOT, "citygov", "present", "assets")
NODE = shutil.which("node")


def scripts():
    out = []
    for dp, dns, fns in os.walk(ASSETS):
        dns.sort()
        out += [os.path.join(dp, f) for f in sorted(fns) if f.endswith(".js")]
    return out


def node_check(path):
    return subprocess.run([NODE, "--check", path], capture_output=True, text=True, timeout=60)


@unittest.skipUnless(NODE, "Node not found")
class Scripts(TestCase):
    def test_every_script_parses(self):
        files = scripts()
        self.assertGreaterEqual(len(files), 3)
        for p in files:
            with self.subTest(script=os.path.relpath(p, ROOT)):
                r = node_check(p)
                self.assertEqual(r.returncode, 0, r.stderr[-600:])

    def test_the_check_fires(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "kaputt.js")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("function f(){ return [1, 2; }\n")
            self.assertNotEqual(node_check(p).returncode, 0)


if __name__ == "__main__":
    unittest.main()
