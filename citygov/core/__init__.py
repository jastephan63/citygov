"""citygov.core — what every layer uses: paths and the database connection
(common), labels, theme, the key figures over time (kennzahlen) and the
permanent identifiers (kennungen). Imports nothing from the other layers, at
import time or when a function runs; the command line of the identifiers,
which runs the integrity gate, is load/kennungen_cli.py."""
