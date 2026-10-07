"""python3 -m citygov — the one entry point; the commands are in citygov/cli.py."""
import sys

from citygov.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
