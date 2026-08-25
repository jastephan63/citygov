#!/usr/bin/env python3
"""Extract the ACTUAL text of a cantonal law PDF, offline, for citation sourcing.

Citations must never be typed from memory. This reads the real
published law text from the Kanton's PDF (the official SHR systematic collection
in ../Gesetze/) using macOS PDFKit via JavaScript-for-Automation — no third-party
library, no network. Use it to find the real Art./§ that grounds a requirement,
then record that article with its provenance.

    python3 scripts/extract_law.py ../Gesetze/120.100-3-1.de-1.pdf            # full text
    python3 scripts/extract_law.py ../Gesetze/120.100-3-1.de-1.pdf --index    # Art./§ headings
    python3 scripts/extract_law.py ../Gesetze/120.100-3-1.de-1.pdf --grep Meldepflicht

The header line of each SHR PDF carries the systematic number and the "Stand"
(version date) — record both as the citation provenance.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

JXA = r"""
ObjC.import('Quartz'); ObjC.import('Foundation');
function run(argv){
  var url=$.NSURL.fileURLWithPath(argv[0]);
  var doc=$.PDFDocument.alloc.initWithURL(url);
  if(!doc.js) return '__OPENFAIL__';
  return ObjC.unwrap(doc.string)||'';
}
"""


def extract_text(pdf_path):
    """Return the full text of a PDF via macOS PDFKit (offline). Empty on failure."""
    abspath = os.path.abspath(pdf_path)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(JXA)
        js = fh.name
    try:
        out = subprocess.run(["osascript", "-l", "JavaScript", js, abspath],
                             capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(js)
    txt = out.stdout
    if txt.strip() == "__OPENFAIL__" or not txt.strip():
        return ""
    return txt


def header(txt):
    lines = [l.strip() for l in txt.splitlines() if l.strip()][:4]
    return " | ".join(lines)


def article_index(txt):
    """Yield (line_no, heading) for Art. N / § N markers."""
    for i, line in enumerate(txt.splitlines(), 1):
        if re.match(r"^\s*(Art\.\s*\d+[a-z]?|§\s*\d+[a-z]?)(\s|$)", line):
            yield i, line.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--index", action="store_true", help="list Art./§ headings")
    ap.add_argument("--grep", help="show numbered lines matching a pattern")
    args = ap.parse_args()
    if not os.path.exists(args.pdf):
        print(f"no such file: {args.pdf}", file=sys.stderr); sys.exit(2)

    txt = extract_text(args.pdf)
    if not txt:
        print("could not extract text (PDFKit/osascript unavailable or scanned image)",
              file=sys.stderr)
        sys.exit(1)

    print("# SOURCE:", header(txt))
    print(f"# {len(txt)} chars from {os.path.relpath(args.pdf)}\n")
    if args.index:
        for ln, h in article_index(txt):
            print(f"{ln:5}: {h}")
    elif args.grep:
        rx = re.compile(args.grep, re.I)
        for i, line in enumerate(txt.splitlines(), 1):
            if rx.search(line):
                print(f"{i:5}: {line.strip()}")
    else:
        print(txt)


if __name__ == "__main__":
    main()
