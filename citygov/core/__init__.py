"""citygov.core — what every layer uses: paths and the database connection
(common), labels, theme, the key figures over time (kennzahlen) and the
permanent identifiers (kennungen). Imports nothing from the other layers at
import time; kennungen.main (the loader entry point of the identifiers) still
imports checks.validate_db when it runs."""
