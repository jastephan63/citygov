# Deprecated scripts

Retired, not deleted — each of these did its job once and got superseded.
Kept for the record; git history has the full story.

- **parse_dvsh.py / load_dvsh.py** — the first DVSH harvest (navigate +
  get_page_text over the admin pages). Superseded by load_dvsh_harvest.py,
  which reads the modeller's own tRPC JSON in one pass.
- **add_dvsh_services.py** — added the DVSH-only service rows after the first
  harvest. load_dvsh_harvest.py now does this itself.
- **apply_dedup.py** — the one-off Formular dedup (newest-edition rule).
  Ran to completion; the Duplikat-Radar (build_similarity.py) watches now.
- **extract_form.py / propose_mapping.py / resolve_cited.py / verify_cited.py**
  — the auto-draft proposal era: widget extraction, auto mapping, citation
  resolution. Superseded by the curated data_field layer with agent
  derivation + proof-gated loaders. (auto_draft.py and commit_proposal.py
  stay in scripts/ because ingest_new.py still imports them.)
- **fetch_missing_forms.py / search_missing_forms.py** — the sh.ch missing-
  forms hunt (CMS full-text search + websearch). Collection is complete;
  the method is written up in the project memory if we ever need it again.

Note: these still point their sys.path at their own folder; to actually run
one again, move it back to scripts/ first.
