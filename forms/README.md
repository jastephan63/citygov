# forms/ — source documents (read-only)

Drop real Formulare (PDF) and calculation tools (Excel) here. Scripts read from
this directory; they never write to it.

The worked example references `forms/anmeldung-wohnsitz.pdf`, which is a
**synthesized placeholder** — there is no real file, because residence
registration (Einwohnerkontrolle) is a communal service and its form is not in
the cantonal collection. The seed proposal stands in for what
`scripts/extract_form.py` would emit from a real PDF.

Real source forms for the canton live one level up in
`../../Verwaltung/<Department>/<Office>/`. Copy the ones you want to model into
this directory as you go, so each modelled service has provenance to a file here.
