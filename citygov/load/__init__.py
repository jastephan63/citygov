"""citygov.load — every loader, harvester, ingest, scan and sweep, the Begriffe
chain (run_begriffe) and the one-off migrations. A loader writes to a staging
copy, runs the gate (checks.validate_db) and swaps. Each one keeps its command,
python3 scripts/<name>.py; commands that start other loaders (run_begriffe,
the ingests, scan_gestaltung) still start them through scripts/."""
