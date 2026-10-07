"""The page code under citygov/present/assets/ and the helpers that read it (citygov.present):

- every file is plain text by the rules the byte-identical pages rest on — UTF-8 without a
  BOM, no CR, exactly one final line end, no blank first line — and no template carries the
  page banner («GENERATED … do not edit»), which its generator writes;
- template() inlines every %%FILE:<name>%% of a page in one pass, fill() puts every
  %%NAME%% in one pass and stops on a marker without a value;
- every script file parses (node --check; skipped when Node is missing — the page check of
  the build parses the scripts inlined in the built pages as well), and the check fires on a
  broken one.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tests import ROOT, TestCase

from citygov import present

ASSETS = os.path.join(ROOT, "citygov", "present", "assets")
NODE = shutil.which("node")


def files(ext=None):
    out = []
    for dp, dns, fns in os.walk(ASSETS):
        dns.sort()
        out += [os.path.join(dp, f) for f in sorted(fns)
                if not f.startswith(".") and (ext is None or f.endswith(ext))]   # not .DS_Store
    return out


def scripts():
    return files(".js")


def node_check(path):
    return subprocess.run([NODE, "--check", path], capture_output=True, text=True, timeout=60)


class Files(TestCase):
    def test_every_file_is_plain_text(self):
        alle = files()
        self.assertGreaterEqual(len(alle), 10)
        for p in alle:
            with self.subTest(file=os.path.relpath(p, ROOT)):
                with open(p, "rb") as fh:
                    raw = fh.read()
                raw.decode("utf-8")                                  # UTF-8, or UnicodeDecodeError
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "a byte order mark")
                self.assertNotIn(b"\r", raw, "a CR line end")
                self.assertTrue(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "not exactly one final line end")
                self.assertTrue(raw.split(b"\n", 1)[0].strip(), "a blank first line")

    def test_no_template_carries_the_page_banner(self):
        for p in files(".html"):
            with self.subTest(file=os.path.relpath(p, ROOT)), open(p, encoding="utf-8") as fh:
                erste = fh.readline()
                self.assertNotIn("GENERATED", erste)
                self.assertNotIn("do not edit", erste)


class Helpers(TestCase):
    def test_template_inlines_every_file_of_the_page(self):
        for page in ("dashboard", "flows"):
            with self.subTest(page=page):
                roh = present.asset(page, "page.html")
                namen = re.findall(r"%%FILE:([\w.-]+)%%", roh)
                self.assertGreaterEqual(len(namen), 2)
                seite = present.template(page, "page.html")
                self.assertNotIn("%%FILE:", seite)
                for name in namen:
                    self.assertIn(present.asset(page, name), seite)

    def test_template_one_pass_and_line_ends(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(present, "ASSETS", d):
            os.makedirs(os.path.join(d, "p"))
            for name, inhalt in (("page.html", b"<a>%%FILE:x.css%%</a>\n"), ("x.css", b"b\r\n%%FILE:y.css%%\r\n"),
                                 ("y.css", b"nie\n")):
                with open(os.path.join(d, "p", name), "wb") as fh:
                    fh.write(inhalt)
            self.assertEqual(present.template("p", "page.html"), "<a>b\n%%FILE:y.css%%\n</a>\n")

    def test_fill(self):
        self.assertEqual(present.fill("%%A%% und %%B%%", {"A": "%%B%%", "B": "2"}), "%%B%% und 2")
        with self.assertRaises(KeyError):
            present.fill("x %%UNBEKANNT%% y", {"A": "1"})


@unittest.skipUnless(NODE, "Node not found")
class Scripts(TestCase):
    def test_every_script_parses(self):
        found = scripts()
        self.assertGreaterEqual(len(found), 3)
        for p in found:
            with self.subTest(script=os.path.relpath(p, ROOT)):
                r = node_check(p)
                self.assertEqual(r.returncode, 0, r.stderr[-600:])

    def test_the_check_fires(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "kaputt.js")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("function f(){ return [1, 2; }\n")
            self.assertNotEqual(node_check(p).returncode, 0)
