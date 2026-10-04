#!/usr/bin/env python3
"""Build flows.html — the guided-flow dashboard (TurboTax principle), separate
from dashboard.html (the compliance view, which stays untouched).

The design and player follow three hand-built prototypes that were the
formatting reference (they are not part of this repository, and the build does
not read them): paper theme, gold crest topbar, thin progress bar with section
name, "Frage N" eyebrow, help drawer with per-node prose, radio-card choices
with [value, label, sub], scan drop zones, roster chips, autocomplete over
canonical Swiss geo data (inlined from quellen/ch-geo.js — municipalities,
postcodes and countries, sources named in its header; the build stops when the
file is missing), and a review screen that mimics the official form (formdoc)
with checklist highlights and a Behörden-Ansicht toggle that reveals the
machine field names.

Self-contained: flow JSON + geo data inlined, opens via file:// and works
offline — the 21 icons are inline SVG (Tabler Icons, MIT); no web fonts are
loaded, the page uses the system font stack declared in the CSS.

Keyboard: everything that reacts to a click is a real <button> or link (the form
picker, the answer cards, the Behörden-Ansicht switch), every new screen moves the
focus to its heading, and the place autocomplete is operated with the arrow keys.

What the page keeps: answers stay in the reader's browser (localStorage keys
«ff_profil» and «ff_draft_<form id>»), nothing is sent anywhere; the page says so
on the start screen and under every question and offers «Profil und Entwürfe
löschen» there. A new storage key must be added to storeKeys() in the template.

What the build corrects against citygov.db (the DB wins over the July flow JSON):
  * meta.amt / departement / quelldatei come from service + form.source_file,
    so «Original ansehen» points at the repository file;
  * a node whose fields the form REQUIRES and the databank bases on the task
    (no_basis=1, basis_typ aufgabe/offen) loses its optional flag;
  * prose that calls a task-necessary or article-based field «freiwillig» is
    neutralised (only basis_typ 'ohne' is voluntary) — every rewrite is printed;
  * the sensitive-data note reads the documented form_disclosure rows instead
    of promising «nur für diesen Antrag»;
  * the profile prefill map (ech_map) holds only the points citygov_prefill.json marks
    vorbefuellbar (register_map.flow_schluessel, read from data_export.json): the
    applicant's own Angaben with the Einwohnerregister mark, never a spouse's, a
    child's or an employee's — the player also saves answers into the profile by it.

    python3 scripts/build_flows.py
"""
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, EXPORT_PATH, connect, assert_no_local_paths
import labels as LABELS
import theme as THEME
import register_map                     # the one prefill rule (flow_schluessel), standard library only

OUT = os.path.join(ROOT, "flows.html")
# Swiss municipalities, postcodes and countries for the autocomplete (tracked
# reference data; sources and generation date in the file's header comment)
GEO = os.path.join(ROOT, "quellen", "ch-geo.js")

# Tabler Icons (https://tabler.io/icons, MIT) — 24×24 stroke paths, inlined so the
# page needs no icon font from a CDN. Referenced in the template as %%I:name%%;
# an unknown name fails the build instead of rendering an empty box.
ICONS = {
    "x": '<path d="M18 6l-12 12"/><path d="M6 6l12 12"/>',
    "check": '<path d="M5 12l5 5l10 -10"/>',
    "plus": '<path d="M12 5l0 14"/><path d="M5 12l14 0"/>',
    "arrow-right": '<path d="M5 12l14 0"/><path d="M13 18l6 -6"/><path d="M13 6l6 6"/>',
    "arrow-left": '<path d="M5 12l14 0"/><path d="M5 12l6 6"/><path d="M5 12l6 -6"/>',
    "search": '<path d="M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M21 21l-6 -6"/>',
    "info-circle": '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/><path d="M12 9h.01"/><path d="M11 12h1v4h1"/>',
    "alert-triangle": '<path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z"/><path d="M12 16h.01"/>',
    "download": '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2"/><path d="M7 11l5 5l5 -5"/><path d="M12 4l0 12"/>',
    "camera": '<path d="M5 7h1a2 2 0 0 0 2 -2a1 1 0 0 1 1 -1h6a1 1 0 0 1 1 1a2 2 0 0 0 2 2h1a2 2 0 0 1 2 2v9a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-9a2 2 0 0 1 2 -2"/><path d="M9 13a3 3 0 1 0 6 0a3 3 0 0 0 -6 0"/>',
    "player-play": '<path d="M7 4v16l13 -8z"/>',
    "player-track-next": '<path d="M3 5v14l8 -7z"/><path d="M14 5v14l8 -7z"/>',
    "loader": '<path d="M12 6l0 -3"/><path d="M16.25 7.75l2.15 -2.15"/><path d="M18 12l3 0"/><path d="M16.25 16.25l2.15 2.15"/><path d="M12 18l0 3"/><path d="M7.75 16.25l-2.15 2.15"/><path d="M6 12l-3 0"/><path d="M7.75 7.75l-2.15 -2.15"/>',
    "route": '<path d="M3 19a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/><path d="M19 7m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M11 19h5.5a3.5 3.5 0 0 0 0 -7h-8a3.5 3.5 0 0 1 0 -7h4.5"/>',
    "list-check": '<path d="M3.5 5.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 11.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 17.5l1.5 1.5l2.5 -2.5"/><path d="M11 6l9 0"/><path d="M11 12l9 0"/><path d="M11 18l9 0"/>',
    "lifebuoy": '<path d="M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0 -8 0"/><path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/><path d="M15 15l3.35 3.35"/><path d="M9 15l-3.35 3.35"/><path d="M5.65 5.65l3.35 3.35"/><path d="M18.35 5.65l-3.35 3.35"/>',
    "shield-check": '<path d="M11.46 20.846a12 12 0 0 1 -7.96 -14.846a12 12 0 0 0 8.5 -3a12 12 0 0 0 8.5 3a12 12 0 0 1 -.09 7.06"/><path d="M15 19l2 2l4 -4"/>',
    "shield-lock": '<path d="M12 3a12 12 0 0 0 8.5 3a12 12 0 0 1 -8.5 15a12 12 0 0 1 -8.5 -15a12 12 0 0 0 8.5 -3"/><path d="M12 11m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M12 12l0 2.5"/>',
    "user-check": '<path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0"/><path d="M6 21v-2a4 4 0 0 1 4 -4h4"/><path d="M15 19l2 2l4 -4"/>',
    "scale": '<path d="M7 20l10 0"/><path d="M6 6l6 -1l6 1"/><path d="M12 3l0 17"/><path d="M9 12l-3 -6l-3 6a3 3 0 0 0 6 0"/><path d="M21 12l-3 -6l-3 6a3 3 0 0 0 6 0"/>',
    "arrows-split-2": '<path d="M21 17h-8l-3.5 -5h-6.5"/><path d="M21 7h-8l-3.495 5"/><path d="M18 10l3 -3l-3 -3"/><path d="M18 20l3 -3l-3 -3"/>',
}


def icon_svg(name):
    if name not in ICONS:
        raise KeyError(f"unbekanntes Icon %%I:{name}%% — in ICONS nachtragen")
    return ('<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + '</svg>')


TEMPLATE = r"""<!-- GENERATED by scripts/build_flows.py from citygov.db — do not edit; regenerate with: python3 scripts/build_flows.py (Build %%BUILD%%) -->
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">/*FAVICON*/
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Geführte Formulare — Kanton Schaffhausen</title>
<!-- No web fonts are loaded: the page uses the system font stack of scripts/theme.py. -->
<style>
/* colours, fonts and text sizes are written from scripts/theme.py — the same look as the
   dashboard; use var(--…) below. A confirmation wears the tone «geklärt» (--ton-ok…), a
   hint to check or an error the tone «handeln» (--ton-act…); as TEXT they use …-ink. */
/*THEME*/
:root{--radius:14px;--maxw:680px}
*{box-sizing:border-box}html,body{margin:0;padding:0}
a{color:var(--link);text-underline-offset:2px}
body{background:var(--paper);color:var(--ink);font-family:var(--font);font-size:var(--fs-l);line-height:1.5;-webkit-font-smoothing:antialiased}
.mono{font-family:var(--mono)}
/* keyboard: one visible ring on whatever has the focus (text fields keep their own border and
   glow, further down); a heading or message that only RECEIVES the focus after a screen
   change shows none */
:focus-visible{outline:2px solid var(--link);outline-offset:2px}
[tabindex="-1"]:focus{outline:none}
/* read by screen readers, not shown */
.vh{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0}
/* first Tab stop of the page: jumps over top bar and form list */
.skip{position:absolute;left:-9999px;top:8px;z-index:100;background:var(--card);color:var(--link);border:1.5px solid var(--link);border-radius:8px;padding:8px 14px;font-size:var(--fs-m);font-weight:600}
.skip:focus{left:8px}
/* inline SVG icons (Tabler, MIT): sized by the surrounding font-size, coloured by currentColor */
.ico{width:1em;height:1em;flex:none;display:inline-block;vertical-align:-.15em}
.btn .ico,.btn-link .ico,.whylink .ico{vertical-align:-.18em}
.topbar{border-bottom:1px solid var(--line);background:var(--card)}
.topbar-inner{max-width:var(--maxw);margin:0 auto;padding:14px 22px;display:flex;align-items:center;gap:12px}
.crest{width:26px;height:30px;flex:none;border-radius:3px;background:var(--gold);position:relative;overflow:hidden;box-shadow:inset 0 0 0 1px var(--shadow)}
.crest::after{content:"";position:absolute;left:50%;top:52%;transform:translate(-50%,-50%);width:14px;height:11px;background:var(--ink);clip-path:polygon(50% 0,100% 38%,82% 100%,18% 100%,0 38%);opacity:.85}
.topbar h1{font-size:var(--fs-m);margin:0;font-weight:600;letter-spacing:.2px}
.topbar .sub{font-size:var(--fs-xs);color:var(--ink-faint);font-weight:500;letter-spacing:.3px;text-transform:uppercase}
.sitenav{font-size:var(--fs-s);white-space:nowrap;color:var(--ink-faint);margin-left:12px}
.sitenav a{color:var(--link)}
@media (max-width:600px){.sitenav{display:none}}
.proto-tag{margin-left:auto;font-size:var(--fs-xs);font-weight:600;letter-spacing:.6px;text-transform:uppercase;color:var(--link);border:1px solid var(--gold);border-radius:99px;padding:3px 9px;white-space:nowrap}
.allbtn{margin-left:auto;background:none;border:1px solid var(--line);border-radius:8px;color:var(--ink-soft);font:inherit;font-size:var(--fs-s);font-weight:600;padding:6px 12px;cursor:pointer;white-space:nowrap}
.allbtn:hover{border-color:var(--gold-deep);color:var(--ink)}
.progress-wrap{max-width:var(--maxw);margin:0 auto;padding:0 22px}
.progress{height:4px;background:var(--line-soft);border-radius:99px;margin-top:18px;overflow:hidden}
.progress span{display:block;height:100%;background:var(--gold);width:0;border-radius:99px;transition:width .35s cubic-bezier(.2,.7,.3,1)}
.stepmeta{display:flex;justify-content:space-between;margin-top:8px;font-size:var(--fs-xs);color:var(--ink-faint);font-weight:500}
.stage{max-width:var(--maxw);margin:0 auto;padding:30px 22px 80px}
.screen{animation:rise .32s cubic-bezier(.2,.7,.3,1)}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.screen{animation:none}.progress span{transition:none}}
.eyebrow{font-size:var(--fs-xs);font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--link);margin-bottom:10px}
h2.q{font-size:var(--fs-xxl);line-height:1.18;letter-spacing:-.4px;margin:0 0 8px;font-weight:700}
.hint{font-size:var(--fs-l);color:var(--ink-soft);margin:0 0 22px;max-width:52ch}
.field-row{display:flex;gap:14px;flex-wrap:wrap}.field-row>.fc{flex:1 1 200px}.fc{margin-bottom:16px}
label.lbl{display:block;font-size:var(--fs-m);font-weight:600;margin-bottom:7px}
input[type=text],input[type=date],input[type=number],select,textarea{width:100%;font:inherit;font-size:var(--fs-l);padding:13px 14px;border:1.5px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);transition:border-color .15s,box-shadow .15s}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--link);box-shadow:0 0 0 3px var(--ring)}
.choices{display:flex;flex-direction:column;gap:10px}
/* an answer card is a <button>: font, colour and alignment are set here because a button inherits none of them */
.choice{display:flex;align-items:center;gap:13px;width:100%;font:inherit;font-size:var(--fs-l);font-weight:500;text-align:left;color:var(--ink);padding:15px 16px;border:1.5px solid var(--line);border-radius:12px;cursor:pointer;background:var(--card);transition:border-color .15s,background .15s}
.choice:hover{border-color:var(--gold-deep)}
.choice .dot{width:20px;height:20px;border-radius:99px;border:2px solid var(--ink-faint);flex:none;position:relative;transition:border-color .15s}
.choice.sel{border-color:var(--ink);background:var(--hover)}.choice.sel .dot{border-color:var(--ink)}
.choice.sel .dot::after{content:"";position:absolute;inset:3px;border-radius:99px;background:var(--gold-deep)}
.choice .sub{display:block;font-size:var(--fs-s);color:var(--ink-faint);font-weight:500;margin-top:2px}
.choice.multi .dot{border-radius:5px}.choice.multi.sel .dot::after{border-radius:2px}
.scan-drop{border:1.5px dashed var(--gold-deep);border-radius:12px;padding:28px;text-align:center;color:var(--ink-soft);background:var(--field)}
.scan-drop .ic{font-size:var(--fs-xxl);color:var(--link);line-height:1}
.roster-card{border:1.5px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.chip{display:flex;justify-content:space-between;align-items:center;background:var(--field);border-radius:10px;padding:10px 13px;margin:7px 0;font-size:var(--fs-m);font-weight:500}
.chip button{background:none;border:none;color:var(--ink-faint);cursor:pointer;font-size:var(--fs-s);font-weight:600;display:inline-flex;align-items:center;gap:4px;font-family:inherit}
.chip button:hover{color:var(--ton-act-ink)}
.ac{position:relative}
.ac-list{position:absolute;left:0;right:0;top:calc(100% + 4px);z-index:30;background:var(--card);border:1.5px solid var(--line);border-radius:10px;max-height:230px;overflow:auto;box-shadow:0 8px 20px var(--shadow);display:none}
.ac-list.open{display:block}
.ac-item{padding:10px 13px;cursor:pointer;font-size:var(--fs-l);display:flex;justify-content:space-between;gap:10px;align-items:center}
.ac-item:hover,.ac-item.act{background:var(--field)}
.ac-item .code{color:var(--ink-faint);font-size:var(--fs-xs);font-family:var(--mono)}
.ac-empty{padding:10px 13px;color:var(--ink-faint);font-size:var(--fs-m)}
.nav{display:flex;gap:12px;align-items:center;margin-top:30px}
.btn{font:inherit;font-size:var(--fs-l);font-weight:600;border-radius:10px;padding:13px 24px;cursor:pointer;border:1.5px solid transparent;transition:transform .08s,background .15s,border-color .15s}
.btn:active{transform:translateY(1px)}.btn-primary{background:var(--ink);color:var(--card)}.btn-primary:hover{background:var(--ink-soft)}
.btn-ghost{background:transparent;color:var(--ink-soft);border-color:var(--line);padding:13px 18px}.btn-ghost:hover{border-color:var(--ink-faint);color:var(--ink)}
.btn-link{background:none;border:none;color:var(--link);font-weight:600;cursor:pointer;font-size:var(--fs-m);padding:4px 2px}
.nav .spacer{flex:1}.err{color:var(--ton-act-ink);font-size:var(--fs-s);font-weight:600;margin-top:10px;min-height:18px}
.whylink{background:none;border:none;color:var(--link);font-weight:600;cursor:pointer;font-size:var(--fs-m);padding:0;margin:-8px 0 20px;display:inline-flex;align-items:center;gap:6px}
.whylink:hover{text-decoration:underline}
.note-box{font-size:var(--fs-m);color:var(--ink-soft);background:var(--field);border-left:3px solid var(--gold);padding:11px 14px;border-radius:0 8px 8px 0;margin:0 0 22px;max-width:60ch;white-space:pre-wrap}
.rev-head{display:flex;align-items:flex-start;gap:14px;margin-bottom:6px}
.rev-head .check{flex:none;width:40px;height:40px;border-radius:99px;background:var(--ton-ok-bg);display:grid;place-items:center;color:var(--ton-ok-ink);font-size:var(--fs-xl);font-weight:700}
h2.rev-title{font-size:var(--fs-xl);letter-spacing:-.3px;margin:0;font-weight:700}
.rev-sub{font-size:var(--fs-m);color:var(--ink-soft);margin:6px 0 18px;max-width:52ch}
.checklist{background:var(--ton-act-bg);border:1px solid var(--ton-act-line);border-radius:12px;padding:13px 16px;margin-bottom:18px}
.checklist .ttl{font-size:var(--fs-s);text-transform:uppercase;letter-spacing:.4px;color:var(--ton-act-ink);font-weight:700}
.checklist div{font-size:var(--fs-m);color:var(--ink-soft);margin-top:5px}
.formdoc{border:1px solid var(--line);border-radius:var(--radius);background:var(--card);overflow:hidden}
.formdoc-top{padding:18px 20px;border-bottom:2px solid var(--ink);display:flex;align-items:center;gap:12px}
.formdoc-top .crest{width:22px;height:25px}
.formdoc-top .t{font-size:var(--fs-s);font-weight:700;letter-spacing:.2px}
.formdoc-top .t span{display:block;font-size:var(--fs-xs);font-weight:500;color:var(--ink-faint);letter-spacing:.4px;text-transform:uppercase}
.formdoc-top .formnr{margin-left:auto;font-size:var(--fs-xs);color:var(--ink-faint)}
.grp{border-top:1px solid var(--line-soft)}.grp:first-of-type{border-top:none}
.grp-h{font-size:var(--fs-xs);font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint);padding:14px 20px 4px}
.rowf{display:flex;align-items:flex-start;gap:12px;padding:9px 20px 13px}.rowf:last-child{padding-bottom:16px}
.rowf .meta{flex:1;min-width:0}
.rowf .flabel{font-size:var(--fs-xs);color:var(--ink-faint);font-weight:500;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rowf .machine{display:none;font-size:var(--fs-xs);color:var(--link);background:var(--field);padding:1px 6px;border-radius:4px}
body.behoerden .rowf .machine{display:inline-block}
.rowf .fval{font-size:var(--fs-l);font-weight:600;margin-top:3px;word-break:break-word;white-space:pre-wrap}
.rowf .src{font-size:var(--fs-xs);color:var(--ink-faint);margin-top:3px;font-style:italic}
.rowf .edit{flex:none;align-self:center;font-size:var(--fs-s);color:var(--link);font-weight:600;background:none;border:1px solid var(--line);border-radius:8px;padding:6px 11px;cursor:pointer}
.rowf .edit:hover{border-color:var(--gold-deep)}
.toolbar{display:flex;align-items:center;gap:14px;margin:18px 2px 4px;flex-wrap:wrap}
.toggle{display:inline-flex;align-items:center;gap:9px;background:none;border:none;padding:0;font:inherit;font-size:var(--fs-s);font-weight:600;color:var(--ink-soft);cursor:pointer;user-select:none}
.switch{width:38px;height:22px;border-radius:99px;background:var(--line);position:relative;transition:background .18s;flex:none}
.switch::after{content:"";position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:99px;background:var(--card);box-shadow:0 1px 3px var(--shadow);transition:left .18s}
body.behoerden .switch{background:var(--gold-deep)}body.behoerden .switch::after{left:18px}
.toolbar .note{font-size:var(--fs-s);color:var(--ink-faint)}
.submit-row{margin-top:24px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.done-msg{margin-top:18px;background:var(--ton-ok-bg);border:1px solid var(--ton-ok-line);color:var(--ton-ok-ink);border-radius:12px;padding:16px 18px;font-size:var(--fs-m);font-weight:500;display:none}
.done-msg.show{display:block}
.restart{margin-top:36px;text-align:center}
.help-tab{position:fixed;right:0;top:50%;transform:translateY(-50%);z-index:60;background:var(--gold);color:var(--ink);border:none;border-radius:12px 0 0 12px;padding:14px 9px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:7px;box-shadow:-2px 2px 12px var(--shadow)}
.help-tab .ico{font-size:var(--fs-xl)}
.help-tab .label{writing-mode:vertical-rl;transform:rotate(180deg);font-size:var(--fs-xs);font-weight:600;letter-spacing:.4px}
.help-tab .dot{position:absolute;top:7px;right:7px;width:9px;height:9px;border-radius:50%;background:var(--ton-act);display:none}
.help-tab.has-why .dot{display:block}
.help-overlay{position:fixed;inset:0;background:var(--ink);opacity:0;visibility:hidden;transition:opacity .25s;z-index:65}
.help-overlay.open{opacity:.28;visibility:visible}
/* closed = hidden for real (visibility), so nothing inside it is a Tab stop and its shadow
   does not show at the window edge; visibility switches after the slide-out has finished */
.help-drawer{position:fixed;top:0;right:0;height:100%;width:370px;max-width:88vw;background:var(--card);border-left:1px solid var(--line);box-shadow:-8px 0 30px var(--shadow);transform:translateX(100%);visibility:hidden;transition:transform .28s cubic-bezier(.2,.7,.3,1),visibility 0s .28s;z-index:70;display:flex;flex-direction:column}
.help-drawer.open{transform:translateX(0);visibility:visible;transition:transform .28s cubic-bezier(.2,.7,.3,1)}
@media (prefers-reduced-motion:reduce){.help-drawer,.help-drawer.open,.help-overlay,.help-overlay.open{transition:none}}
.help-head{display:flex;align-items:center;gap:10px;padding:18px 20px;border-bottom:1px solid var(--line)}
.help-head .ico{font-size:var(--fs-xl);color:var(--link)}
.help-head h3{margin:0;font-size:var(--fs-l);font-weight:600}
.help-head .x{margin-left:auto;background:none;border:none;cursor:pointer;color:var(--ink-soft);font-size:var(--fs-xl);line-height:1;display:flex;padding:2px}
.help-head .x .ico{color:var(--ink-soft)}
.help-body{padding:18px 20px;overflow:auto;flex:1}
.help-q{font-size:var(--fs-l);font-weight:600;margin-bottom:16px;line-height:1.35}
.help-sec{margin-bottom:18px}
.help-h{font-size:var(--fs-xs);font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--link);display:flex;align-items:center;gap:7px;margin-bottom:6px}
.help-h .ico{font-size:var(--fs-l)}
.help-p{font-size:var(--fs-m);color:var(--ink-soft);margin:0;line-height:1.6}
.help-foot{padding:14px 20px;border-top:1px solid var(--line);font-size:var(--fs-s);color:var(--ink-faint);display:flex;gap:8px;align-items:flex-start}
.help-foot .ico{font-size:var(--fs-l);color:var(--ton-ok);margin-top:1px}
.fwchip{display:flex;gap:8px;align-items:flex-start;background:var(--field);border:1px solid var(--line);color:var(--ink-soft);
  font-size:var(--fs-s);font-weight:500;border-radius:9px;padding:9px 12px;margin:-6px 0 16px;max-width:56ch}
.fwchip .ico{color:var(--link);font-size:var(--fs-l);margin-top:2px}
/* ⛨ is a Kennzeichen (the category of the data), neutral and outlined as in the dashboard —
   violet is the eSH draft and nothing else */
.snote{display:flex;gap:8px;align-items:flex-start;background:var(--card);border:1px solid var(--line-strong);color:var(--ink-soft);
  font-size:var(--fs-s);font-weight:500;border-radius:9px;padding:9px 12px;margin:-6px 0 16px;max-width:56ch}
.snote .ico{font-size:var(--fs-l);margin-top:2px}
.snote .bek{display:block;margin-top:4px;font-weight:500}
.snote .bek.offen{font-style:italic}
.next-steps{margin-top:18px;border:1px solid var(--line);border-radius:12px;background:var(--card);padding:16px 18px;display:none}
.next-steps.show{display:block}
.next-steps .ttl{font-size:var(--fs-s);text-transform:uppercase;letter-spacing:.4px;color:var(--link);font-weight:700;margin-bottom:8px}
.next-steps ol{margin:0 0 8px;padding-left:20px;font-size:var(--fs-m);color:var(--ink-soft)}
.next-steps ol li{margin-bottom:5px}
.next-steps ol li .note{color:var(--ink-faint)}
.next-steps .more{font-size:var(--fs-s);color:var(--ink-faint);margin:0 0 8px}
/* the contact line reads as in the dashboard: «Kontakt (laut DVSH): Adresse · Tel. … · E-Mail …»,
   links in the normal link style (base rule a{…}) */
.next-steps .kontakt{font-size:var(--fs-s);color:var(--ink-soft);border-top:1px solid var(--line-soft);padding-top:8px;margin-top:6px}
.next-steps .kontakt .kp{white-space:nowrap}
.stale{display:inline-flex;gap:6px;align-items:center;background:var(--ton-act-bg);color:var(--ton-act-ink);border:1px solid var(--ton-act-line);
  font-size:var(--fs-xs);font-weight:600;border-radius:8px;padding:3px 9px;margin-left:8px;vertical-align:middle}
.fchip{display:inline-block;font-size:var(--fs-xs);font-weight:600;border-radius:6px;padding:1px 7px;margin-left:5px;vertical-align:middle}
.fchip.frei{background:var(--field);color:var(--link);border:1px solid var(--line)}
.fchip.sens{background:var(--card);color:var(--ink-soft);border:1px solid var(--line-strong)}
/* layout: sidebar + main */
.layout{display:flex;min-height:calc(100vh - 55px)}
aside{width:290px;flex:0 0 290px;background:var(--card);border-right:1px solid var(--line);
  padding:18px 16px;overflow:auto;max-height:calc(100vh - 55px);position:sticky;top:0}
body.playing #side{display:none}   /* only the form sidebar, NOT the help drawer (also an <aside>) */
body.playing .topbar-inner,body.playing .progress-wrap{max-width:var(--maxw)}
.topbar-inner{max-width:1100px}
aside .dep{font-size:var(--fs-xs);font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint);margin:18px 0 7px}
/* an entry of the form picker is a <button> (Tab, Enter, Space); it looks like the former list row */
.sv{display:block;width:100%;font:inherit;font-size:var(--fs-m);font-weight:500;text-align:left;background:none;padding:8px 11px;border-radius:9px;cursor:pointer;color:var(--ink-soft);margin:0 0 2px;border:1.5px solid transparent}
.nohit{font-size:var(--fs-s);color:var(--ink-soft);margin:14px 2px}
.sv:hover{background:var(--field);color:var(--ink)}
.sv.active{border-color:var(--gold-deep);background:var(--hover);color:var(--ink)}
.sv .m{display:block;font-size:var(--fs-xs);color:var(--ink-faint);font-weight:500}
main.stage{flex:1;max-width:none;padding:30px 34px 80px}
body.playing main.stage{max-width:var(--maxw);margin:0 auto;padding:30px 22px 80px}
.detail{max-width:860px}
.dhead{display:flex;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:6px}
.dhead h2{font-size:var(--fs-xxl);letter-spacing:-.4px;margin:0;font-weight:700}
/* title and introduction share the row with the «Ausprobieren» button: the text block takes
   the room that is left and wraps inside it, so a long title never pushes the button down */
.dhead>div:first-child{flex:1 1 300px;min-width:0}
.dhead .try{margin-left:auto}
.dfl{border:1px solid var(--line);border-radius:var(--radius);background:var(--card);overflow:hidden;margin-top:18px}
.dfl-h{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:14px;padding:11px 18px;
  font-size:var(--fs-xs);font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint);border-bottom:2px solid var(--ink)}
.dfr{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:14px;padding:13px 18px;border-top:1px solid var(--line-soft)}
.dfr:first-of-type{border-top:none}
.dfr .fn{font-size:var(--fs-m);font-weight:600}
.dfr .fdef{font-size:var(--fs-xs);color:var(--ink-faint);margin-top:2px}
/* a field the flow does not ask: soft ink, never transparency */
.dfr.aus,.dfr.aus .fn,.dfr.aus .fdef{color:var(--ink-soft)}.dfr.aus .fn{font-weight:500}
.echb{display:inline-flex;align-items:center;gap:4px;font-size:var(--fs-xs);font-weight:600;font-family:var(--mono);
  background:var(--field);color:var(--link);border:1px solid var(--line);border-radius:6px;padding:2px 7px;
  text-decoration:none;margin-top:5px;margin-right:4px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.echb:hover{border-color:var(--gold-deep)}
.echb.none{color:var(--ink-faint);font-family:var(--font);font-weight:500}
.echb.warn{color:var(--ton-act-ink)}
.sfl{margin-top:6px;font-size:var(--fs-xs);color:var(--ink-soft)}
.sfl .sf{display:inline-flex;align-items:center;gap:5px;background:var(--field);border-radius:6px;padding:2px 8px;margin:2px 3px 0 0;font-size:var(--fs-xs)}
.sfl .sf .se{color:var(--link);font-family:var(--mono);font-size:var(--fs-xs)}
.qrow{border-left:3px solid var(--gold);background:var(--hover);border-radius:0 9px 9px 0;padding:9px 12px;margin-bottom:7px}
.qrow:last-child{margin-bottom:0}
.qrow .qq{font-size:var(--fs-m);font-weight:600}
.qrow .qm{font-size:var(--fs-xs);color:var(--ink-faint);margin-top:2px;display:flex;gap:8px;flex-wrap:wrap}
.qrow .qm .tag{background:var(--field);border-radius:5px;padding:1px 6px;font-weight:600;color:var(--link)}
.qrow.ausq{border-left-color:var(--line);background:var(--paper);color:var(--ink-faint)}
/* landing */
.land h2{font-size:var(--fs-xl);letter-spacing:-.3px;margin:0 0 6px;font-weight:700}
.land .lead{font-size:var(--fs-l);color:var(--ink-soft);margin:0 0 24px;max-width:54ch}
.search{position:relative;margin-bottom:22px}
.search input{padding-left:42px}
.search .ico{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--ink-faint);font-size:var(--fs-l)}
aside .cover{font-size:var(--fs-s);color:var(--ink-soft);line-height:1.45;margin:10px 2px 0;padding:8px 10px;background:var(--field);border-radius:8px}
aside .cover b{color:var(--ink)}
aside .stamp{font-size:var(--fs-xs);color:var(--ink-faint);line-height:1.5;margin:8px 2px 0}
.bekline{font-size:var(--fs-s);color:var(--ink-soft);margin:8px 0 0;max-width:80ch}
.bekline .lbl2{font-weight:600;color:var(--ink)}
/* what the page keeps in this browser, and the button that removes it: on the start screen
   (beside the «Bekanntgabe» line) and under every screen of a flow */
.storenote{font-size:var(--fs-s);color:var(--ink-soft);margin:8px 0 0;max-width:80ch}
.storenote.flow{margin-top:34px;padding-top:12px;border-top:1px solid var(--line-soft)}
.storenote .lbl2{font-weight:600;color:var(--ink)}
.storenote .btn-link{font-size:var(--fs-s);padding:0;text-decoration:underline;text-underline-offset:2px}
.storeask{display:block;margin-top:8px;background:var(--ton-act-bg);border:1px solid var(--ton-act-line);border-radius:10px;padding:10px 13px;color:var(--ink)}
.storeask .btn{font-size:var(--fs-s);padding:7px 14px;margin:8px 8px 0 0}
.storemsg{display:block;margin-top:8px;background:var(--ton-ok-bg);border:1px solid var(--ton-ok-line);color:var(--ton-ok-ink);border-radius:10px;padding:10px 13px;font-weight:500}
.storemsg.bad{background:var(--ton-act-bg);border-color:var(--ton-act-line);color:var(--ton-act-ink)}
/* a step that could not be drawn says so and offers the way out */
.failbox{background:var(--ton-act-bg);border:1px solid var(--ton-act-line);border-radius:12px;padding:14px 16px;font-size:var(--fs-m);color:var(--ink);max-width:60ch}
.dep{font-size:var(--fs-xs);font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint);margin:22px 0 10px}
.svcgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.gi{border:1.5px solid var(--line);border-radius:12px;padding:15px 17px;background:var(--card);cursor:pointer;transition:border-color .15s}
.gi:hover{border-color:var(--gold-deep)}
.gi b{display:block;font-size:var(--fs-l);margin-bottom:3px}
.gi span{font-size:var(--fs-s);color:var(--ink-faint);font-weight:500}
@media (max-width:600px){.svcgrid{grid-template-columns:1fr}.help-drawer{width:100%;max-width:100%}.help-tab{padding:12px 8px}}
/* a phone: the field list of a form stacks (the field with its standard, then its questions),
   and an eCH chip wraps instead of losing its element name to an ellipsis */
@media (max-width:600px){
  .dfl-h,.dfr{grid-template-columns:1fr;gap:8px}
  .dfl-h span+span{display:none}
  .echb{white-space:normal;text-overflow:clip}
}
/* narrow windows and phones: the form picker stands above the content instead of beside it,
   its list scrolls in a box of its own so the chosen form is one swipe away */
@media (max-width:700px){
  .layout{display:block;min-height:0}
  #side{width:auto;max-height:none;position:static;overflow:visible;border-right:none;border-bottom:1px solid var(--line)}
  #svlist{max-height:42vh;overflow:auto;margin-top:10px;padding:0 4px;border-top:1px solid var(--line-soft)}
  main.stage{padding:24px 18px 70px}
  .dhead .try{margin-left:0}
}
</style>
</head>
<body>
<a class="skip" href="#stage">Zum Inhalt springen</a>
<header class="topbar">
  <div class="topbar-inner" id="topInner">
    <div class="crest" aria-hidden="true"></div>
    <div><div class="sub" id="topSub">Kanton Schaffhausen</div><h1 id="topTitle">Geführte Formulare</h1></div>
    <div class="proto-tag" id="protoTag">Prototyp</div>
    <nav class="sitenav" aria-label="Seitennavigation"><a href="index.html">← Startseite</a> · <a href="dashboard.html">Dashboard</a></nav>
  </div>
  <div class="progress-wrap" id="progWrap" style="display:none">
    <div class="progress" id="pbar"><span></span></div>
    <div class="stepmeta"><span id="stepName">Start</span><span id="stepCount"></span></div>
  </div>
</header>
<div class="layout" id="layout"><aside id="side" aria-label="Formular auswählen"></aside><main class="stage" id="stage" tabindex="-1">Wird geladen…</main></div>
<button class="help-tab" id="helpTab" onclick="__help.open()" aria-label="Hilfe öffnen" style="display:none"><span class="dot"></span>%%I:lifebuoy%%<span class="label">Hilfe</span></button>
<div class="help-overlay" id="helpOverlay" onclick="__help.close()"></div>
<aside class="help-drawer" id="helpDrawer" aria-label="Hilfe zu dieser Seite">
  <div class="help-head">%%I:lifebuoy%%<h3>Hilfe zu dieser Seite</h3><button class="x" onclick="__help.close()" aria-label="Schliessen">%%I:x%%</button></div>
  <div class="help-body" id="helpBody"></div>
  <div class="help-foot">%%I:shield-check%%<span>Ihre Angaben werden erst am Schluss geprüft. Im Prototyp wird nichts verschickt; Antworten bleiben nur in diesem Browser gespeichert.</span></div>
</aside>
<script>%%GEO%%</script>
<script>
var FLOWS=%%DATA%%;
// coverage + data date + German labels, all computed at build time (never re-derived here)
var NFORMS=%%NFORMS%%,STAMP=%%STAMP%%,LABELS=%%LABELS%%;
var DS={gemeinden:window.CH_GEMEINDEN||[],plz:window.CH_PLZ||[],laender:window.CH_COUNTRIES||[],
        heimat:(window.CH_HEIMAT||(window.CH_GEMEINDEN||[]).concat(window.CH_COUNTRIES||[]))};
(function(){
// a code without a label renders visibly as ⟨code⟩ — never raw, never hidden
function lab(map,code){if(code==null||code==="")return"";var m=LABELS[map]||{};return m[code]!==undefined?m[code]:"⟨"+code+"⟩"}
// the documented disclosures of a form (form_disclosure + article) as one honest sentence —
// never a promise the data cannot back
function bekText(fl){var b=(fl&&fl.bekanntgaben)||[];
  if(!b.length)return{offen:true,text:"Eine Weitergabe an andere Stellen ist für dieses Formular noch nicht dokumentiert."};
  // recipients that share the same article are cited once: «X, Y, Z (Art. …)»
  function grouped(list){var by={},order=[];list.forEach(function(x){var a=x.artikel||"Rechtsgrundlage noch nicht benannt";
      if(!by[a]){by[a]=[];order.push(a)}by[a].push(x.empfaenger)});
    return order.map(function(a){return by[a].join(", ")+" ("+a+")"}).join("; ")}
  var sys=[],anf=[],rest=[];b.forEach(function(x){
    if(x.mode==="systematisch")sys.push(x);else if(x.mode==="auf_anfrage")anf.push(x);else rest.push(x)});
  var parts=[];sys=sys.length?grouped(sys):"";anf=anf.length?grouped(anf):"";
  rest=rest.map(function(x){return lab("mode",x.mode)+": "+x.empfaenger+" ("+(x.artikel||"Rechtsgrundlage noch nicht benannt")+")"});
  if(sys)parts.push("werden von Gesetzes wegen gemeldet an "+sys);
  if(anf)parts.push("können auf Anfrage bekanntgegeben werden an "+anf);
  if(rest.length)parts.push("Bekanntgabe "+rest.join("; "));
  return{offen:false,text:"Angaben aus diesem Formular "+parts.join(" und ")+"."}}
var F=null,N=[],A={},hist=[],mode="land",editReturn=false,ACOPTS={},SELT=0;
var PROFIL={};try{PROFIL=JSON.parse(localStorage.getItem("ff_profil")||"{}")}catch(e){}
// a stored entry is only used when it has the expected shape (a damaged or foreign one is ignored)
if(!PROFIL||typeof PROFIL!=="object"||Array.isArray(PROFIL))PROFIL={};
var PROV={},FREI={},SENS={},EMAPN={};
var stage=document.getElementById("stage");
function normk(x){return(""+(x||"")).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/[^a-z0-9]+/g,"")}
function profKey(n,f){var names=n.field||[];if(!names.length)return null;var base=names[0];
  if(f&&f.label){var k=EMAPN[normk(base+"\u203a"+f.label)];if(k)return k;
    k=EMAPN[normk(f.label)];if(k)return k;
    if((n.fields||[]).length===1)return EMAPN[normk(base)]||null;return null}
  return EMAPN[normk(base)]||null}
// equivalent elements across standards: the same datum lives under sibling names
// (officialName in eCH-0044 vs lastName in eCH-0010 address blocks etc.)
var EQUIV={"eCH-0010\u00b7lastName":"eCH-0044\u00b7officialName","eCH-0044\u00b7officialName":"eCH-0010\u00b7lastName",
"eCH-0010\u00b7firstName":"eCH-0044\u00b7firstName","eCH-0011\u00b7officialName":"eCH-0044\u00b7officialName",
"eCH-0011\u00b7firstName":"eCH-0044\u00b7firstName","eCH-0011\u00b7dateOfBirth":"eCH-0044\u00b7dateOfBirth"};
function profVal(n,f){var k=profKey(n,f);if(!k)return null;
  if(PROFIL[k])return PROFIL[k].v;
  var a=EQUIV[k];return a&&PROFIL[a]?PROFIL[a].v:null}
function profSave(n,f,v){if(v===undefined||v===""||v===null)return;var k=profKey(n,f);
  if(k){PROFIL[k]={v:v,label:(f&&f.label)||n.kurzlabel||n.ask||"",t:Date.now()};
    try{localStorage.setItem("ff_profil",JSON.stringify(PROFIL))}catch(e){}}}
function draftKey(){return"ff_draft_"+(F?F.meta.form_id:"x")}
function saveDraft(){if(!F)return;try{localStorage.setItem(draftKey(),JSON.stringify({A:A,hist:hist,t:Date.now()}))}catch(e){}}
function clearDraft(){try{localStorage.removeItem(draftKey())}catch(e){}}
function loadDraft(){var d=null;try{d=JSON.parse(localStorage.getItem(draftKey())||"null")}catch(e){}
  return d&&typeof d==="object"&&Array.isArray(d.hist)&&d.A&&typeof d.A==="object"&&!Array.isArray(d.A)?d:null}
// ---------- what this page keeps in the browser ----------
// Two kinds of entries, both in localStorage and nowhere else: «ff_profil» (answers about the
// person, reused to prefill the next form) and «ff_draft_<form id>» (a form that was begun).
// The page writes nothing else (no sessionStorage, no cookie) and sends nothing anywhere.
// storeKeys() is the ONE list of what is stored: the note counts with it, the button deletes
// with it — a new key must be added here.
function storeKeys(){var ks=[];try{for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);
  if(k==="ff_profil"||(k&&k.indexOf("ff_draft_")===0))ks.push(k)}}catch(e){}return ks}
function storeInfo(){var ks=storeKeys(),p=0,d=0;ks.forEach(function(k){
    if(k!=="ff_profil"){d++;return}
    try{var o=JSON.parse(localStorage.getItem(k)||"{}");p=o&&typeof o==="object"?Object.keys(o).length:1}catch(e){p=1}});
  return{keys:ks,profil:p,entwuerfe:d}}
function plur(n,one,many){return n+" "+(n===1?one:many)}
function storeText(i){var t=[];if(i.profil)t.push("Profil mit "+plur(i.profil,"Angabe","Angaben"));
  if(i.entwuerfe)t.push(plur(i.entwuerfe,"Entwurf","Entw\u00fcrfe"));return t.join(" und ")}
var STORE={ask:false,msg:"",bad:false};
// kind: "start" (start screen) and "intro" (first screen of a flow) explain what is kept,
// "flow" (every further screen) is the short form
function storeNote(kind){var i=storeInfo(),was=storeText(i),mem=!!F&&Object.keys(A).length>0;
  var h='<div class="storenote'+(kind==="start"?"":" flow")+'" id="storeNote" data-kind="'+kind+'"><span class="lbl2">Ihre Eingaben:</span> Antworten bleiben nur in diesem Browser gespeichert';
  if(kind!=="flow")h+=' \u2013 als Profil (Angaben zu Ihrer Person, mit denen das n\u00e4chste Formular vorausgef\u00fcllt wird) und als Entw\u00fcrfe (angefangene Formulare)';
  h+='. Es wird nichts verschickt, weder an eine Dienststelle noch an einen Server. <span id="storeCount">'+(was?"Derzeit gespeichert: "+was+".":"Derzeit ist nichts gespeichert.")+'</span> ';
  if(!STORE.ask)h+='<button type="button" class="btn-link" id="storeDel" onclick="__store.ask()">Profil und Entw\u00fcrfe l\u00f6schen</button>';
  else h+='<span class="storeask" role="group" aria-labelledby="storeQ" onkeydown="if(event.key===\'Escape\')__store.cancel()"><span id="storeQ"><b>Wirklich l\u00f6schen?</b> '
    +(was?"Aus diesem Browser entfernt werden: "+was+".":"Gespeichert ist nichts.")+(mem?" Auch die Antworten im ge\u00f6ffneten Formular gehen verloren.":"")
    +' Das l\u00e4sst sich nicht r\u00fcckg\u00e4ngig machen.</span><br><button type="button" class="btn btn-ghost" id="storeNo" onclick="__store.cancel()">Abbrechen</button><button type="button" class="btn btn-primary" id="storeYes" onclick="__store.wipe()">Ja, l\u00f6schen</button></span>';
  if(STORE.msg){h+='<span class="storemsg'+(STORE.bad?" bad":"")+'" id="storeMsg" role="status" tabindex="-1">'+esc(STORE.msg)+'</span>';STORE.msg="";STORE.bad=false}
  return h+'</div>'}
function refreshStore(focusId){var n=document.getElementById("storeNote");if(!n)return;
  n.outerHTML=storeNote(n.getAttribute("data-kind"));var t=focusId&&document.getElementById(focusId);if(t)t.focus()}
window.__store={
ask:function(){var i=storeInfo(),mem=!!F&&Object.keys(A).length>0;
  if(!i.keys.length&&!mem){STORE.ask=false;STORE.msg="Derzeit ist nichts gespeichert \u2013 es gibt nichts zu l\u00f6schen.";refreshStore("storeMsg");return}
  STORE.ask=true;refreshStore("storeNo")},
cancel:function(){STORE.ask=false;refreshStore("storeDel")},
wipe:function(){var i=storeInfo(),was=storeText(i),mem=!!F&&Object.keys(A).length>0;
  i.keys.forEach(function(k){try{localStorage.removeItem(k)}catch(e){}});
  PROFIL={};STORE.ask=false;
  var rest=storeKeys().length;   // looked up again: the message says what IS, not what was meant
  if(rest){STORE.bad=true;STORE.msg="Das L\u00f6schen ist nicht gelungen: "+plur(rest,"Eintrag ist","Eintr\u00e4ge sind")+" noch gespeichert. Sie k\u00f6nnen die Website-Daten auch in den Einstellungen des Browsers l\u00f6schen."}
  else STORE.msg=(was?"Gel\u00f6scht: "+was+".":"Gespeichert war nichts.")+(mem?" Die Antworten im ge\u00f6ffneten Formular wurden verworfen.":"")+" In diesem Browser ist jetzt nichts mehr gespeichert.";
  if(F){A={};hist=[];PROV={};editReturn=false;document.body.classList.remove("behoerden");introScreen()}
  else detail(SEL||FLOWS[0]);
  var t=document.getElementById("storeMsg");if(t)t.focus()}
};
// the contact of the service in the dashboard's wording: «Kontakt (laut DVSH): Adresse · Tel. … ·
// E-Mail …» — the words are labels.KONTAKT (LABELS.kontakt), the same the dashboard and the
// dossiers read. Address and number are shown as the DVSH stores them; only the link target of
// the number is brought into the international form (052 … -> +41 52 …; a «(0)» is dropped).
function telHref(t){var d=(""+t).replace(/\(0\)/g,"").replace(/[^\d+]/g,"");if(d.indexOf("00")===0)d="+"+d.slice(2);else if(d.charAt(0)==="0")d="+41"+d.slice(1);return d}
function kontaktHtml(ko){if(!ko)return"";if(typeof ko==="string")ko={text:ko};var p=[],KL=LABELS.kontakt;
  if(ko.text)p.push(esc(ko.text));if(ko.name)p.push(esc(ko.name));if(ko.adresse)p.push(esc(ko.adresse));
  if(ko.telefon)p.push('<span class="kp">'+esc(KL.tel)+' <a href="tel:'+esc(telHref(ko.telefon))+'">'+esc(ko.telefon)+'</a></span>');
  if(ko.email)p.push('<span class="kp">'+esc(KL.mail)+' <a href="mailto:'+esc(ko.email)+'">'+esc(ko.email)+'</a></span>');
  return p.length?esc(KL.label)+": "+p.join(" \u00b7 "):""}
function ahv13ok(v){var d=(""+v).replace(/\D/g,"");if(d.length!==13)return false;var s0=0;
  for(var i=0;i<12;i++)s0+=(+d[i])*(i%2===0?1:3);return((10-(s0%10))%10)===(+d[12])}
function esc(s){return(""+(s==null?"":s)).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;")}
function fmtDate(s){if(!s)return"—";var p=(""+s).split("-");return p.length===3?p[2]+"."+p[1]+"."+p[0]:s}
function normOpts(o){return(o||[]).map(function(x){return Array.isArray(x)?x:[String(x),String(x)]})}
function optLabel(opts,v){opts=normOpts(opts);for(var i=0;i<opts.length;i++)if(opts[i][0]===v)return opts[i][1];return v}
function passes(n){if(!n.show_if)return true;var m=n.show_if.match(/^\s*(\w+)\s*==\s*'([^']*)'\s*$/);if(m)return A[m[1]]===m[2];
m=n.show_if.match(/^\s*(\w+)\s*!=\s*'([^']*)'\s*$/);if(m)return A[m[1]]!==m[2];
m=n.show_if.match(/^\s*(\w+)\s+in\s+\[(.+)\]\s*$/);if(m){var os=m[2].split(",").map(function(x){return x.trim().replace(/^'|'$/g,"")});return os.indexOf(A[m[1]])>-1}
return true}
function byId(id){for(var i=0;i<N.length;i++)if(N[i].id===id)return N[i];return null}
function nextFrom(idx){for(var i=idx;i<N.length;i++)if(passes(N[i]))return N[i];return null}
function okey(n){return n.key||n.id}
function olabel(n){return n.kurzlabel||n.ask||n.id}
function ofield(n){return(n.field&&n.field.length)?n.field.join(" · "):""}
function dsFor(f){return f.datenquelle&&DS[f.datenquelle]?DS[f.datenquelle]:normOpts(f.options)}
// ---------- sidebar + detail (data field -> questions mapping) ----------
// The form picker. The frame (search field, coverage, data date) is built once; typing only
// redraws the list below it, so the search field keeps the focus by itself. Every entry is a
// real <button>: Tab reaches it, Enter and Space open it. Extras: Enter in the search field
// opens the first hit, the arrow keys walk the list, and from the heading of the opened form
// Shift+Tab returns to its entry.
var SEL=null,HITS=[];
function sidebar(){
  var h='<div class="search" style="margin-bottom:4px">%%I:search%%<input type="text" id="q" aria-label="Formular suchen" autocomplete="off" placeholder="Formular suchen …" oninput="__side.filter(this.value)" onkeydown="__side.key(event)"></div>';
  h+='<div class="vh" id="svcount" role="status"></div>';
  // coverage is a fact, not a promise: the other Formulare have no guided flow yet
  h+='<div class="cover"><b>'+FLOWS.length+' von '+NFORMS+' Formularen</b> haben einen geführten Ablauf; die übrigen '+(NFORMS-FLOWS.length)+' noch nicht.</div>';
  h+='<div class="stamp">'+esc(STAMP)+'</div>';
  h+='<div id="svlist" role="group" aria-label="Formulare mit geführtem Ablauf" onkeydown="__side.key(event)"></div>';
  document.getElementById("side").innerHTML=h;sideList("")}
function sideList(filter){
  var f=(filter||"").toLowerCase().trim(),by={},h="";HITS=[];
  FLOWS.forEach(function(fl){var m=fl.meta;
    if(f&&((m.titel_einfach||"")+" "+(m.titel||"")+" "+(m.amt||"")).toLowerCase().indexOf(f)<0)return;
    var d=m.departement||"Übrige";(by[d]=by[d]||[]).push(fl)});
  Object.keys(by).sort().forEach(function(dep){
    h+='<div class="dep">'+esc(dep)+'</div>';
    by[dep].sort(function(a,b){return(a.meta.titel_einfach||a.meta.titel).localeCompare(b.meta.titel_einfach||b.meta.titel)}).forEach(function(fl){
      var on=SEL&&SEL.meta.form_id===fl.meta.form_id;HITS.push(fl);
      h+='<button type="button" class="sv'+(on?" active":"")+'"'+(on?' aria-current="true"':"")+' data-fid="'+fl.meta.form_id+'" onclick="__side.pick('+fl.meta.form_id+')"><b>'+esc(fl.meta.titel_einfach||fl.meta.titel)+'</b><span class="m">'+esc(fl.meta.amt||"")+' · '+fl.nodes.length+' Schritte</span></button>'});
  });
  if(!HITS.length)h='<p class="nohit">Kein Formular gefunden. Gesucht wird im Titel und im Namen der Dienststelle.</p>';
  document.getElementById("svlist").innerHTML=h;
  // the number of hits, for screen readers (the list itself shows it to everyone else)
  document.getElementById("svcount").textContent=!f?"":!HITS.length?"Kein Formular gefunden":
    plur(HITS.length,"Formular","Formulare")+" gefunden; die Eingabetaste öffnet das erste"}
function markActive(){var bs=document.querySelectorAll("#svlist .sv");
  for(var i=0;i<bs.length;i++){var on=!!SEL&&(+bs[i].getAttribute("data-fid"))===SEL.meta.form_id;
    bs[i].classList.toggle("active",on);if(on)bs[i].setAttribute("aria-current","true");else bs[i].removeAttribute("aria-current")}}
window.__side={filter:function(v){sideList(v)},
pick:function(fid){var fl=null;FLOWS.forEach(function(x){if(x.meta.form_id===fid)fl=x});if(fl)detail(fl,true)},
key:function(e){var t=e.target,k=e.key;
  if(t.id==="q"){
    if(k==="Enter"){e.preventDefault();if(HITS.length)this.pick(HITS[0].meta.form_id)}
    else if(k==="ArrowDown"){var b=document.querySelector("#svlist .sv");if(b){e.preventDefault();b.focus()}}
    return}
  if(k!=="ArrowDown"&&k!=="ArrowUp"&&k!=="Home"&&k!=="End")return;
  var bs=[].slice.call(document.querySelectorAll("#svlist .sv")),i=bs.indexOf(t);if(i<0)return;
  e.preventDefault();
  if(k==="ArrowUp"&&i===0){document.getElementById("q").focus();return}
  var n=k==="Home"?0:k==="End"?bs.length-1:i+(k==="ArrowDown"?1:-1);if(bs[n])bs[n].focus()},
back:function(e){if(e.key!=="Tab"||!e.shiftKey||e.target!==e.currentTarget)return;
  var b=document.querySelector("#svlist .sv.active")||document.getElementById("q");if(b){e.preventDefault();b.focus()}}};
function echBadge(e,status){
  if(e){var lab=e.standard+(e.element?" · "+e.element:" · nur Standard");
    var warn=e.status&&e.status!=="Genehmigt";
    return '<a class="echb'+(warn?" warn":"")+'" href="'+esc(e.url||"#")+'" target="_blank" rel="noreferrer" title="'+esc((e.titel||e.standard)+(e.status?" · Status: "+e.status:""))+'">'+esc(lab)+(warn?" ⚠":"")+'</a>'}
  if(status==="kein_standard")return '<span class="echb none" title="kein eCH-Standard deckt dieses Feld ab">kein eCH-Standard</span>';
  return ""}
function nodesForField(fl,name){var out=[];fl.nodes.forEach(function(n){if((n.field||[]).indexOf(name)>-1)out.push(n)});return out}
function detail(fl,focus){
  SEL=fl;F=null;mode="detail";document.body.classList.remove("playing");
  document.getElementById("progWrap").style.display="none";
  document.getElementById("helpTab").style.display="none";
  document.getElementById("topSub").textContent="Kanton Schaffhausen · "+(fl.meta.amt||"");
  document.getElementById("topTitle").textContent="Geführte Formulare";
  var tag=document.getElementById("protoTag");tag.outerHTML='<div class="proto-tag" id="protoTag">Prototyp</div>';
  markActive();
  var m=fl.meta,h='<div class="screen detail">';
  h+='<div class="eyebrow">'+esc(m.amt||"")+'</div>';
  h+='<div class="dhead"><div><h2 id="dtitle" tabindex="-1" onkeydown="__side.back(event)">'+esc(m.titel_einfach||m.titel)+(m.veraltet?'<span class="stale" title="Die Quelldatei des Formulars hat sich seit der Flow-Erzeugung geändert – Flow neu generieren">%%I:alert-triangle%% Formular aktualisiert</span>':"")+'</h2><p class="hint" style="margin:6px 0 0">'+esc(m.intro||"")+'</p></div>';
  h+='<div class="try"><button class="btn btn-primary" onclick="__side.play()">%%I:player-play%% Ausprobieren</button></div></div>';
  h+='<p class="hint" style="margin-top:10px;font-size:var(--fs-s)">Amtliches Formular: <b>'+esc(m.titel)+'</b> · '+(m.quelldatei?'<a href="'+esc(m.quelldatei)+'" style="color:var(--link)" title="'+esc(m.quelldatei)+'">Original ansehen</a>':'<span title="kein Quelldokument hinterlegt">Kein Quelldokument</span>')+' · '+fl.nodes.length+' Schritte</p>';
  var bk=bekText(fl);h+='<p class="bekline"><span class="lbl2">Bekanntgabe an andere Stellen:</span> '+esc(bk.text)+'</p>';
  h+=storeNote("start");
  h+='<div class="dfl"><div class="dfl-h"><span>Datenfeld & eCH-Standard</span><span>Frage(n) im geführten Ablauf</span></div>';
  var aus={};(fl.ausgelassen||[]).forEach(function(a){aus[a.feld]=a.grund});
  (fl.datenfelder||[]).forEach(function(d){
    var isAus=aus[d.name]!==undefined;
    h+='<div class="dfr'+(isAus?" aus":"")+'"><div><div class="fn">'+esc(d.name)+(d.pflicht?' <span style="color:var(--link)">*</span>':"")+(d.freiwillig?'<span class="fchip frei" title="keine gesetzliche Grundlage – wird als freiwillige Angabe gestellt">freiwillig</span>':"")+(d.sensibel?'<span class="fchip sens" title="besonders schützenswerte Personendaten (KDSG Art. 2 Abs. 1 lit. d)">⛨ '+esc(lab("sens",d.sensibel))+'</span>':"")+'</div>';
    if(d.definition)h+='<div class="fdef">'+esc(d.definition)+'</div>';
    h+='<div>'+echBadge(d.ech,d.ech_status)+'</div>';
    if((d.teilfelder||[]).length){h+='<div class="sfl">';
      d.teilfelder.forEach(function(sf){h+='<span class="sf">'+esc(sf.name)+(sf.ech&&sf.ech.element?' <span class="se">'+esc(sf.ech.standard+"·"+sf.ech.element)+'</span>':(sf.ech_status==="kein_standard"?' <span class="se" style="color:var(--ink-faint)">kein Std.</span>':""))+'</span>'});
      h+='</div>'}
    h+='</div><div>';
    if(isAus){h+='<div class="qrow ausq"><div class="qq">Wird nicht gefragt</div><div class="qm">'+esc(aus[d.name])+'</div></div>'}
    else{var ns=nodesForField(fl,d.name);
      if(!ns.length)h+='<div class="qrow ausq"><div class="qq">—</div></div>';
      ns.forEach(function(n){
        h+='<div class="qrow"><div class="qq">«'+esc(n.ask||n.text||n.id)+'»</div><div class="qm"><span class="tag">'+esc(lab("node_typ",n.type))+'</span><span>'+esc(secName2(fl,n.section))+'</span>'+(n.show_if?'<span title="Bedingung: '+esc(n.show_if)+'">%%I:arrows-split-2%% nur bei Bedarf</span>':"")+'</div>';
        if(n.type==="form"&&(n.fields||[]).length)h+='<div class="qm" style="margin-top:4px">'+n.fields.map(function(f){return esc(f.label)}).join(" · ")+'</div>';
        h+='</div>'})}
    h+='</div></div>'});
  h+='</div></div>';
  stage.innerHTML=h;
  // a form was chosen (not the first drawing of the page): the heading takes the focus, so the
  // next Tab is «Ausprobieren»; where the picker stands ABOVE the content (narrow window) the
  // window moves to the content instead of to the top
  var stacked=getComputedStyle(document.getElementById("layout")).display==="block";
  if(focus&&stacked)stage.scrollIntoView();else window.scrollTo(0,0);
  if(focus){var t=document.getElementById("dtitle");if(t){try{t.focus({preventScroll:true})}catch(e){t.focus()}}}}
function secName2(fl,sid){var ss=fl.sections||[];for(var i=0;i<ss.length;i++)if(ss[i][0]===sid)return ss[i][1];return sid}
window.__side.play=function(){if(SEL)startFlow(SEL)};
function landing(){sidebar();
  if(FLOWS.length){detail(FLOWS[0])}else{stage.innerHTML="<p class=hint>Keine Flows geladen.</p>"}}
// ---------- one place that puts a screen of a flow on the page ----------
// The note on what is stored follows the screen; the window returns to the top and the heading
// takes the focus, so the Tab key continues with the first control of the new screen (focusSel
// names a field that takes it instead; stay=true keeps the place, for a list that only grew).
function show(h,focusSel,stay){stage.innerHTML=h+storeNote(mode==="intro"?"intro":"flow");
  if(!stay)window.scrollTo(0,0);
  var t=(focusSel&&stage.querySelector(focusSel))||stage.querySelector("h2");if(!t)return;
  if(t.tagName==="H2")t.setAttribute("tabindex","-1");
  try{t.focus({preventScroll:!stay})}catch(e){t.focus()}}
// a step that cannot be drawn says so and offers the way out — never a half-drawn or empty screen
function fail(e){try{console.error(e)}catch(x){}
  stage.innerHTML='<div class="screen"><div class="failbox" role="alert"><b>Dieser Schritt konnte nicht angezeigt werden.</b> Das ist ein Fehler der Seite, nicht Ihrer Eingaben. Sie k\u00f6nnen zur \u00dcbersicht zur\u00fcckkehren'+(F?' oder das Formular von vorne beginnen':'')+'; hilft das nicht, l\u00f6schen Sie die gespeicherten Entw\u00fcrfe.</div><div class="nav"><button class="btn btn-ghost" onclick="__ff.toLanding()">Zur \u00dcbersicht</button>'+(F?'<button class="btn btn-ghost" onclick="__ff.restart()">Von vorne beginnen</button>':'')+'</div></div>'+storeNote("flow")}
function guard(o){Object.keys(o).forEach(function(k){var fn=o[k];if(typeof fn!=="function")return;
  o[k]=function(){try{return fn.apply(o,arguments)}catch(e){fail(e)}}})}
// ---------- flow ----------
function startFlow(fl){
  F=fl;N=fl.nodes;A={};hist=[];mode="flow";editReturn=false;PROV={};document.body.classList.add("playing");
  FREI={};SENS={};(fl.datenfelder||[]).forEach(function(d){if(d.freiwillig)FREI[d.name]=1;if(d.sensibel)SENS[d.name]=d.sensibel});
  EMAPN={};var em=fl.ech_map||{};Object.keys(em).forEach(function(k){EMAPN[normk(k)]=em[k]});
  document.getElementById("progWrap").style.display="";
  document.getElementById("helpTab").style.display="";
  document.getElementById("topSub").textContent="Kanton Schaffhausen · "+(fl.meta.amt||"");
  document.getElementById("topTitle").textContent=fl.meta.titel_einfach||fl.meta.titel;
  var tag=document.getElementById("protoTag");tag.outerHTML='<button class="allbtn" id="protoTag" onclick="__ff.toLanding()">%%I:arrow-left%% Zur Übersicht</button>';
  introScreen()}
function introScreen(){
  mode="intro";updateHelp(null);
  var m=F.meta,vis=N.filter(passes);
  var h='<div class="screen"><div class="eyebrow">'+esc(m.amt||"")+'</div><h2 class="q">'+esc(m.titel_einfach||m.titel)+'</h2>';
  h+='<p class="hint" style="max-width:56ch">'+esc(m.intro||"")+'</p>';
  var mins=Math.max(2,Math.round(vis.length*22/60)),mins2=Math.max(mins+2,Math.round(vis.length*40/60));
  var docs=[];N.forEach(function(n){if((n.type==="doc_scan"||n.type==="scan")&&n.document)docs.push(n.document)});
  h+='<div class="note-box" style="white-space:normal"><b>Bevor Sie beginnen</b><br>\u23f1 Dauer: ca. '+mins+'\u2013'+mins2+' Minuten \u00b7 '+vis.length+' Schritte';
  if(docs.length){h+='<br>\ud83d\udcce Bereithalten: '+docs.map(esc).join(" \u00b7 ")}
  var pc=0;Object.keys(EMAPN).forEach(function(k){if(PROFIL[EMAPN[k]])pc++});
  if(pc){h+='<br>\u2713 <b>'+pc+' Angaben</b> werden aus Ihrem Profil vorausgef\u00fcllt \u2013 Sie m\u00fcssen sie nur best\u00e4tigen.'}
  h+='</div>';
  h+='<div class="note-box" style="white-space:normal">Amtliches Formular: <b>'+esc(m.titel)+'</b> \u00b7 '+(m.quelldatei?'<a href="'+esc(m.quelldatei)+'" style="color:var(--link)">Original ansehen</a>':'Kein Quelldokument')+(m.stand_txt?' \u00b7 Flow-Stand '+esc(m.stand_txt):"")+'</div>';
  var draft=loadDraft();
  h+='<div class="nav">';
  if(draft&&draft.hist.length){h+='<button class="btn btn-ghost" onclick="__ff.resume()">%%I:player-track-next%% Fortsetzen (Schritt '+draft.hist.length+')</button>'}
  h+='<div class="spacer"></div><button class="btn btn-primary" onclick="__ff.begin()">Los geht\u2019s %%I:arrow-right%%</button></div></div>';
  show(h);
  document.querySelector("#pbar span").style.width="2%";
  document.getElementById("stepName").textContent="Start";
  document.getElementById("stepCount").textContent=N.filter(passes).length+" Schritte"}
function eyebrowFor(n){if(n.type==="note")return"Hinweis";if(n.type==="doc_scan"||n.type==="scan")return"Dokument";
  var vis=N.filter(passes),c=0;for(var j=0;j<vis.length;j++){if(vis[j].type!=="note"&&vis[j].type!=="doc_scan"&&vis[j].type!=="scan"){c++;if(vis[j].id===n.id)break}}return"Frage "+c}
function nodeBadges(n){var h="";var names=n.field||[];
  var alleFrei=names.length&&names.every(function(x){return FREI[x]});
  var sens=null;names.forEach(function(x){if(SENS[x])sens=SENS[x]});
  if(alleFrei)h+='<div class="fwchip">%%I:scale%% Freiwillige Angabe \u2013 keine gesetzliche Pflicht. Sie k\u00f6nnen diesen Schritt \u00fcberspringen.</div>';
  // the disclosure sentence comes from form_disclosure (article-backed) \u2014 no fixed promise
  if(sens){var bk=bekText(F);h+='<div class="snote">%%I:shield-lock%%<span>Besonders sch\u00fctzenswerte Daten ('+esc(lab("sens",sens))+').<span class="bek'+(bk.offen?" offen":"")+'">'+esc(bk.text)+'</span></span></div>'}
  return h}
function whyHTML(n){var b=nodeBadges(n);if(!n.why&&!n.hilfe)return b;return b+'<button class="whylink" onclick="__help.open()">%%I:info-circle%% '+(n.why?"Warum fragen wir das?":"Hilfe zu dieser Seite")+'</button>'}
function helpFor(n){var s=n.hilfe||"";
  if(!s){if(n.type==="choice")s="Wählen Sie die zutreffende Antwort. Sie können jederzeit zurückgehen und die Auswahl ändern.";
  else if(n.type==="multiselect")s="Wählen Sie alle zutreffenden Antworten aus und tippen Sie dann auf Weiter.";
  else if(n.type==="doc_scan"||n.type==="scan")s="Fotografieren Sie das Dokument gut lesbar. Ohne Dokument überspringen Sie den Schritt, wo möglich.";
  else if(n.type==="roster")s="Fügen Sie jede Person bzw. jeden Eintrag einzeln hinzu. Falsche Einträge entfernen Sie mit dem ✕.";
  else if(n.type==="form")s="Füllen Sie die Felder aus und tippen Sie auf Weiter. Bei Orten und Ländern wählen Sie einen Vorschlag aus der Liste.";
  else s="Geben Sie Ihre Antwort ein und tippen Sie auf Weiter.";}
  return{steps:s,why:n.why}}
function updateHelp(n){var body=document.getElementById("helpBody"),tab=document.getElementById("helpTab");if(!body)return;
  if(!n){body.innerHTML='<div class="help-q">'+(mode==="review"?"Prüfung Ihrer Angaben":"Geführtes Ausfüllen")+'</div><div class="help-sec"><div class="help-h">%%I:list-check%% So gehen Sie vor</div><p class="help-p">'+(mode==="review"?"Prüfen Sie jede Zeile in Ruhe. Tippen Sie auf «Ändern», um etwas zu korrigieren. Im Prototyp wird auch mit «Absenden» nichts verschickt.":"Beantworten Sie die Fragen Schritt für Schritt. Über «Zurück» ändern Sie frühere Antworten jederzeit.")+'</p></div>';if(tab)tab.classList.remove("has-why");return}
  var hf=helpFor(n),html='<div class="help-q">'+esc(n.ask||n.intro||("Abschnitt: "+(n.section||"")))+'</div>';
  html+='<div class="help-sec"><div class="help-h">%%I:list-check%% So füllen Sie das aus</div><p class="help-p">'+esc(hf.steps)+'</p></div>';
  if(hf.why)html+='<div class="help-sec"><div class="help-h">%%I:info-circle%% Warum fragen wir das?</div><p class="help-p">'+esc(hf.why)+'</p></div>';
  body.innerHTML=html;if(tab)tab.classList.toggle("has-why",!!hf.why)}
function isFrei(n){var names=n.field||[];return names.length&&names.every(function(x){return FREI[x]})}
function nav(onclick,label,n){var skip=(n&&(n.optional||isFrei(n)))?'<button class="btn btn-ghost" onclick="__ff.skipNode(\''+n.id+'\')">\u00dcberspringen</button>':"";
  return'<div class="err" id="fferr" role="alert"></div><div class="nav">'+(hist.length>1?'<button class="btn btn-ghost" onclick="__ff.back()">Zur\u00fcck</button>':"")+'<div class="spacer"></div>'+skip+'<button class="btn btn-primary" onclick="'+onclick+'">'+(label||"Weiter")+'</button></div>'}
function fieldId(f,cls){return(cls||"ffc")+"_"+f.key}
function fieldInput(f,val,cls){cls=cls||"ffc";var fid=esc(fieldId(f,cls));
  if(f.type==="select"){var opts=normOpts(f.options);var o='<select id="'+fid+'" class="'+cls+'" data-k="'+esc(f.key)+'"><option value=""'+(val?"":" selected")+'>– bitte wählen –</option>';
    for(var i=0;i<opts.length;i++)o+='<option value="'+esc(opts[i][0])+'"'+(val===opts[i][0]?" selected":"")+'>'+esc(opts[i][1])+'</option>';return o+'</select>'}
  if(f.type==="autocomplete"){var ds=dsFor(f);ACOPTS[f.key]=ds;var disp=optLabel(ds,val);
    return'<div class="ac" data-k="'+esc(f.key)+'"><input type="text" id="'+fid+'" class="ac-input" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="ac_'+f.key+'" autocomplete="off" placeholder="'+esc(f.placeholder||"Tippen zum Suchen …")+'" value="'+esc(val?disp:"")+'" oninput="__ac.f(this,\''+f.key+'\')" onfocus="__ac.open(this,\''+f.key+'\')" onblur="__ac.close(\''+f.key+'\',this)" onkeydown="__ac.k(event,\''+f.key+'\')"><input type="hidden" class="'+cls+'" data-k="'+esc(f.key)+'" value="'+esc(val||"")+'"><div class="ac-list" role="listbox" tabindex="-1" id="ac_'+f.key+'" onmousedown="event.preventDefault()"></div></div>'}
  var t=f.type==="date"?"date":(f.type==="number"?"number":"text");
  return'<input id="'+fid+'" class="'+cls+'" data-k="'+esc(f.key)+'" type="'+t+'" value="'+esc(val||"")+'" placeholder="'+esc(f.placeholder||"")+'">'}
function updateProgress(n){var vis=N.filter(passes),total=vis.length,done=hist.length,pct;
  if(mode==="review")pct=100;else pct=Math.round((done-1)/Math.max(1,total)*92)+4;
  document.querySelector("#pbar span").style.width=pct+"%";
  var sn="";if(n){var ss=F.sections||[];var si=-1;for(var i2=0;i2<ss.length;i2++)if(ss[i2][0]===n.section)si=i2;
    sn=(si>-1?("Abschnitt "+(si+1)+"/"+ss.length+" \u00b7 "):"")+(secName(n.section)||n.section||"")}
  document.getElementById("stepName").textContent=mode==="review"?"Prüfung":sn;
  document.getElementById("stepCount").textContent=mode==="review"?"":("Schritt "+done+" von "+total)}
function secName(sid){var ss=F.sections||[];for(var i=0;i<ss.length;i++)if(ss[i][0]===sid)return ss[i][1];return sid}
function vrule(f,v){if(!f.validate)return null;var r=f.validate;
  if(r.pattern){try{if(!new RegExp(r.pattern).test((v||"").trim()))return r.meldung||"Bitte prüfen Sie das Format."}catch(e){}}
  if(r.checksum==="ahvn13"||/756/.test(r.pattern||"")){if(!ahv13ok(v))return r.meldung||"Diese AHV-Nummer ist nicht gültig – bitte prüfen Sie die 13 Ziffern."}
  return null}
// stay=true: the same screen is drawn again (an entry was added to or removed from a list)
function renderNode(n,stay){var h="",eb=eyebrowFor(n);updateHelp(n);
  if(n.type==="choice"){var opts=normOpts(n.options);
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q" id="ffq">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n)+'<div class="choices" role="group" aria-labelledby="ffq">';
    for(var i=0;i<opts.length;i++){var v=opts[i][0],lab=opts[i][1],sub=opts[i][2];
      h+='<button type="button" class="choice'+(A[okey(n)]===v?" sel":"")+'" aria-pressed="'+(A[okey(n)]===v)+'" onclick="__ff.select(\''+n.id+'\',this)" data-v="'+esc(v)+'"><span class="dot"></span><span>'+esc(lab)+(sub?'<span class="sub">'+esc(sub)+'</span>':"")+'</span></button>'}
    h+='</div>'+nav("__ff.choiceNext('"+n.id+"')",null,n)+'</div>';show(h);updateProgress(n);return}
  if(n.type==="multiselect"){var opts2=normOpts(n.options);var cur=A[okey(n)]||[];
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q" id="ffq">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"Mehrere Antworten möglich.")+'</p>'+whyHTML(n)+'<div class="choices" role="group" aria-labelledby="ffq">';
    for(var i2=0;i2<opts2.length;i2++){var v2=opts2[i2][0],l2=opts2[i2][1];
      h+='<button type="button" class="choice multi'+(cur.indexOf(v2)>-1?" sel":"")+'" aria-pressed="'+(cur.indexOf(v2)>-1)+'" onclick="__ff.multi(this)" data-v="'+esc(v2)+'"><span class="dot"></span><span>'+esc(l2)+'</span></button>'}
    h+='</div>'+nav("__ff.multiNext('"+n.id+"')",null,n)+'</div>';show(h);updateProgress(n);return}
  if(n.type==="text"||n.type==="number"){var pre=A[okey(n)];var fromProf=false;
    if(pre===undefined){var pv0=profVal(n,null);if(pv0!=null){pre=pv0;fromProf=true;PROV[okey(n)]="profil"}}
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q" id="ffq">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n)+(fromProf?'<div class="fwchip" style="background:var(--field);color:var(--link)">%%I:user-check%% Aus Ihrem Profil vorausgef\u00fcllt \u2013 bitte pr\u00fcfen.</div>':"")+'<div class="fc"'+(n.type==="number"?' style="max-width:240px"':"")+'><input id="ffi" aria-labelledby="ffq" type="'+(n.type==="number"?"number":"text")+'" value="'+esc(pre||"")+'" placeholder="'+esc(n.placeholder||"")+'"></div>'+nav("__ff.textNext('"+n.id+"')",null,n)+'</div>';
    show(h,"#ffi");updateProgress(n);return}
  if(n.type==="date"){var pv=A[okey(n)]||"";
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q" id="ffq">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n)+'<div class="fc" style="max-width:240px"><input id="ffi" aria-labelledby="ffq" type="date" value="'+esc(pv)+'"></div>'+nav("__ff.textNext('"+n.id+"')",null,n)+'</div>';
    show(h,"#ffi");updateProgress(n);return}
  if(n.type==="note"){h='<div class="screen"><div class="eyebrow">Hinweis</div><h2 class="q" style="font-size:var(--fs-xl)">'+esc(n.ask||"Gut zu wissen")+'</h2><div class="note-box">'+esc(n.text||"")+'</div>'+nav("__ff.advance('"+n.id+"')","Verstanden")+'</div>';show(h);updateProgress(n);return}
  if(n.type==="doc_scan"||n.type==="scan"){
    h='<div class="screen"><div class="eyebrow">Dokument</div><h2 class="q">'+esc(n.ask||("Dokument: "+(n.document||"")))+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n);
    h+='<div class="scan-drop" id="ffdrop"><div class="ic">%%I:camera%%</div><div style="margin-top:8px;font-size:var(--fs-m)">Foto von: '+esc(n.document||"Dokument")+'</div><button class="btn btn-primary" style="margin-top:14px" onclick="__ff.scan(\''+n.id+'\')">Foto hinzufügen</button></div>';
    h+='<div class="err" id="fferr" role="alert"></div><div class="nav">'+(hist.length>1?'<button class="btn btn-ghost" onclick="__ff.back()">Zurück</button>':"")+'<div class="spacer"></div>'+(n.optional?'<button class="btn btn-ghost" onclick="__ff.skip(\''+n.id+'\')">Habe ich nicht – überspringen</button>':"")+'</div></div>';
    show(h);updateProgress(n);return}
  if(n.type==="form"||n.type==="confirm"){
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div>';
    if(n.ask)h+='<h2 class="q">'+esc(n.ask)+'</h2>';else h+='<h2 class="q" style="font-size:var(--fs-xl)">'+esc(n.intro||"")+'</h2>';
    if(n.hint)h+='<p class="hint">'+esc(n.hint)+'</p>';
    h+=whyHTML(n)+'<div style="margin-top:10px">';
    var pf={};if(n.prefill)for(var pk in n.prefill){pf[pk]=n.prefill[pk]==="@heute"?new Date().toISOString().slice(0,10):(A[n.prefill[pk]]||"")}
    for(var j=0;j<(n.fields||[]).length;j++){var f=n.fields[j];var val=A[f.key]!==undefined?A[f.key]:(pf[f.key]||"");
      var fromProf=false;
      if(val===""){var pv=profVal(n,f);if(pv!=null){val=pv;fromProf=true;PROV[f.key]="profil"}}
      h+='<div class="fc"><label class="lbl" for="'+esc(fieldId(f))+'">'+esc(f.label)+(fromProf?' <span style="color:var(--link);font-weight:600">\u00b7 aus Ihrem Profil</span>':"")+'</label>'+fieldInput(f,val)+'</div>'}
    h+='</div>'+nav("__ff.formNext('"+n.id+"')",n.intro&&!n.ask?"Stimmt so":"Weiter",n)+'</div>';
    show(h);updateProgress(n);return}
  if(n.type==="roster"){var key=okey(n);if(!A[key])A[key]=[];
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n);
    var ifs=n.item_fields||[];
    for(var p=0;p<A[key].length;p++){var per=A[key][p];var vals=[];for(var q=0;q<Math.min(2,ifs.length);q++){var vv=per[ifs[q].key];if(vv)vals.push(vv)}
      h+='<div class="chip"><span>'+esc(vals.join(" ")||"Eintrag "+(p+1))+'</span><button onclick="__ff.rosterRemove(\''+n.id+'\','+p+')" aria-label="Eintrag entfernen">%%I:x%% Entfernen</button></div>'}
    h+='<div class="roster-card">';
    for(var j2=0;j2<ifs.length;j2++){var f2=ifs[j2];h+='<div class="fc"><label class="lbl" for="'+esc(fieldId(f2,"ffr"))+'">'+esc(f2.label)+'</label>'+fieldInput(f2,"","ffr")+'</div>'}
    h+='<button class="btn btn-ghost" onclick="__ff.rosterAdd(\''+n.id+'\')">%%I:plus%% Hinzufügen</button></div>'+nav("__ff.advance('"+n.id+"')",null,n)+'</div>';
    if(stay)show(h,".roster-card input,.roster-card select",true);else show(h);updateProgress(n);return}
  __ff.advance(n.id)}
// ---------- review ----------
function reviewRows(){var rows=[];
  for(var i=0;i<N.length;i++){var n=N[i];if(!passes(n))continue;
    if(n.type==="roster"){var arr=A[okey(n)];if(arr&&arr.length){var ifs=n.item_fields||[];
      var names=arr.map(function(p){var v=[];for(var q=0;q<Math.min(2,ifs.length);q++)if(p[ifs[q].key])v.push(p[ifs[q].key]);return v.join(" ")}).join(", ");
      rows.push({section:n.section,label:olabel(n),value:arr.length+" – "+names,machine:ofield(n),node:n.id})}continue}
    if(n.type==="form"||n.type==="confirm"){for(var j=0;j<(n.fields||[]).length;j++){var f=n.fields[j];var v=A[f.key];
      if(v===undefined||v==="")continue;var d=f.type==="select"||f.type==="autocomplete"?optLabel(f.type==="autocomplete"?dsFor(f):f.options,v):(f.type==="date"?fmtDate(v):v);
      rows.push({section:n.section,label:f.label,value:d,machine:ofield(n),node:n.id,prov:PROV[f.key]})}continue}
    if(n.type==="note")continue;
    if(n.type==="doc_scan"||n.type==="scan"){if(A[okey(n)])rows.push({section:n.section,label:olabel(n),value:A[okey(n)],machine:ofield(n),node:n.id});continue}
    var val=A[okey(n)];if(val===undefined||val===""||val===null)continue;
    if(n.type==="choice")val=optLabel(n.options,val);
    if(n.type==="multiselect")val=(val||[]).map(function(x){return optLabel(n.options,x)}).join(" · ");
    if(n.type==="date")val=fmtDate(val);
    rows.push({section:n.section,label:olabel(n),value:val,machine:ofield(n),node:n.id})}
  return rows}
function goReview(){mode="review";updateHelp(null);
  var rows=reviewRows(),m=F.meta;
  var html='<div class="screen"><div class="rev-head"><div class="check">%%I:check%%</div><div><h2 class="rev-title">Bitte prüfen Sie Ihr Formular</h2></div></div>';
  html+='<p class="rev-sub">Wir haben das amtliche Formular <b>'+esc(m.titel)+'</b> aus Ihren Antworten ausgefüllt. Stimmt etwas nicht, tippen Sie auf «Ändern».</p>';
  var hl=((F.review||{}).highlight)||[];
  if(hl.length){html+='<div class="checklist"><div class="ttl">Bitte besonders prüfen</div>';
    hl.forEach(function(h){var n=byId(h.answer);if(!n||!passes(n))return;var v=A[okey(n)];
      if(n.type==="choice")v=optLabel(n.options,v);if(v===undefined||v==="")v="—";if(Array.isArray(v))v=v.length+" Einträge";
      html+='<div>• '+esc(h.prompt)+' <b style="color:var(--ink)">('+esc(""+v)+')</b></div>'});html+='</div>'}
  html+='<div class="toolbar"><button type="button" class="toggle" id="behTog" role="switch" aria-checked="false" onclick="__ff.togBeh()"><span class="switch"></span> Behörden-Ansicht (Datenfelder zeigen)</button><span class="note">Zeigt die Datenfelder des Katalogs im Hintergrund.</span></div>';
  html+='<div class="formdoc"><div class="formdoc-top"><div class="crest" aria-hidden="true"></div><div class="t">'+esc(m.titel)+'<span>Kanton Schaffhausen · '+esc(m.amt||"")+'</span></div><div class="formnr mono">'+esc(m.formnr||("Formular #"+m.form_id))+'</div></div>';
  var ss=F.sections&&F.sections.length?F.sections:[];
  if(!ss.length){var seen={};N.forEach(function(n){if(!seen[n.section]){seen[n.section]=1;ss.push([n.section,n.section])}})}
  ss.forEach(function(s){var block="";rows.forEach(function(r){if(r.section!==s[0])return;
    block+='<div class="rowf"><div class="meta"><div class="flabel">'+esc(r.label)+' <span class="machine mono">'+esc(r.machine)+'</span></div><div class="fval">'+esc(r.value)+'</div><div class="src">'+(r.prov==="profil"?"aus Ihrem Profil übernommen":"übernommen aus Ihren Antworten")+'</div></div><button class="edit" onclick="__ff.edit(\''+r.node+'\')">Ändern</button></div>'});
    if(block)html+='<div class="grp"><div class="grp-h">'+esc(s[1])+'</div>'+block+'</div>'});
  html+='</div>';
  html+='<div class="submit-row"><button class="btn btn-ghost" onclick="__ff.back()">Zurück</button><button class="btn btn-ghost" onclick="__ff.exportECH()">%%I:download%% Daten als eCH-JSON</button><div class="spacer"></div><button class="btn btn-primary" id="submitBtn" onclick="__ff.submit()">Absenden</button></div>';
  html+='<div class="done-msg" id="doneMsg">Im Prototyp wird nichts abgeschickt. In der echten Anwendung ginge das geprüfte Formular jetzt direkt an die zuständige Dienststelle'+(m.amt?' («'+esc(m.amt)+'»)':'')+'.</div>';
  var dv=F.dvsh||{};var steps=(dv.ablauf||[]).filter(function(x){return x});
  html+='<div class="next-steps" id="nextSteps"><div class="ttl">%%I:route%% So geht es weiter</div>';
  if(steps.length){html+='<ol>'+steps.map(function(st2){if(typeof st2==="string")return'<li>'+esc(st2)+'</li>';var t=st2.title||st2.text||'';if(!t)return'';return'<li>'+esc(t)+(st2.description?' <span class="note">– '+esc(st2.description)+'</span>':'')+'</li>'}).join("")+'</ol>'+(dv.ablauf_mehr?'<div class="more">… '+esc(dv.ablauf_mehr)+' siehe DVSH</div>':'')}
  else{html+='<ol><li>Die zuständige Dienststelle'+(m.amt?' («'+esc(m.amt)+'»)':'')+' prüft Ihre Angaben.</li><li>Bei Rückfragen werden Sie kontaktiert.</li><li>Sie erhalten den Entscheid bzw. die Bestätigung.</li></ol>'}
  var kt=kontaktHtml(dv.kontakt);if(kt)html+='<div class="kontakt">'+kt+'</div>';
  html+='</div>';
  html+='<div class="restart"><button class="btn-link" onclick="__ff.restart()">Von vorne beginnen</button> · <button class="btn-link" onclick="__ff.toLanding()">Zur Übersicht</button></div></div>';
  document.body.classList.remove("behoerden");show(html);updateProgress(null)}
window.__ff={
begin:function(){mode="flow";var f=nextFrom(0);hist.push(f.id);renderNode(f)},
select:function(id,el){var n=byId(id);A[okey(n)]=el.getAttribute("data-v");
  var cs=stage.querySelectorAll(".choice");for(var i=0;i<cs.length;i++){cs[i].classList.remove("sel");cs[i].setAttribute("aria-pressed","false")}
  el.classList.add("sel");el.setAttribute("aria-pressed","true");
  clearTimeout(SELT);
  var self=this;SELT=setTimeout(function(){self.choiceNext(id)},180)},
choiceNext:function(id){var n=byId(id);if(A[okey(n)]===undefined){document.getElementById("fferr").textContent="Bitte eine Option wählen.";return}this.advance(id)},
multi:function(el){el.setAttribute("aria-pressed",String(el.classList.toggle("sel")))},
multiNext:function(id){var n=byId(id);var sel=[];stage.querySelectorAll(".choice.sel").forEach(function(c){sel.push(c.getAttribute("data-v"))});
  A[okey(n)]=sel;this.advance(id)},
textNext:function(id){var n=byId(id);var v=document.getElementById("ffi").value;
  if(n.validate){var e=vrule(n,v);if(e){document.getElementById("fferr").textContent=e;return}}
  if(!v&&!n.optional&&!isFrei(n)){document.getElementById("fferr").textContent="Bitte ausfüllen.";return}
  A[okey(n)]=v;if(n.key)A[n.key]=v;profSave(n,null,v);this.advance(id)},
formNext:function(id){var n=byId(id);var ins=stage.querySelectorAll(".ffc");
  for(var i=0;i<ins.length;i++){var k=ins[i].getAttribute("data-k"),val=ins[i].value,fd=null;
    for(var j=0;j<(n.fields||[]).length;j++)if(n.fields[j].key===k)fd=n.fields[j];
    if(fd&&fd.validate){var e=vrule(fd,val);if(e){document.getElementById("fferr").textContent=e;return}}
    if(fd&&fd.pflicht&&!val&&!isFrei(n)){document.getElementById("fferr").textContent="Bitte «"+fd.label+"» ausfüllen.";return}
    A[k]=val;if(fd)profSave(n,fd,val)}
  this.advance(id)},
rosterAdd:function(id){var n=byId(id);var ins=stage.querySelectorAll(".ffr");var obj={},any=false;
  for(var i=0;i<ins.length;i++){var k=ins[i].getAttribute("data-k");obj[k]=ins[i].value;if(ins[i].value)any=true}
  if(!any){document.getElementById("fferr").textContent="Bitte mindestens ein Feld ausfüllen.";return}
  A[okey(n)].push(obj);renderNode(n,true)},
rosterRemove:function(id,idx){var n=byId(id);A[okey(n)].splice(idx,1);renderNode(n,true)},
scan:function(id){var n=byId(id);var d=document.getElementById("ffdrop");
  d.innerHTML='<div style="font-size:var(--fs-m);color:var(--link)">%%I:loader%% '+esc(n.document||"Dokument")+' wird gelesen …</div>';
  var self=this;setTimeout(function(){A[okey(n)]="✓ beigelegt";self.advance(id)},900)},
skip:function(id){this.advance(id)},
skipNode:function(id){var n=byId(id);if(A[okey(n)]===undefined)A[okey(n)]="";this.advance(id)},
advance:function(id){saveDraft();if(editReturn){editReturn=false;goReview();return}
  var cur=byId(id||hist[hist.length-1]);var idx=N.indexOf(cur)+1;var nx=nextFrom(idx);
  if(!nx){goReview();return}hist.push(nx.id);renderNode(nx)},
back:function(){if(mode==="review"){mode="flow";renderNode(byId(hist[hist.length-1]));return}
  if(hist.length>1){hist.pop();renderNode(byId(hist[hist.length-1]))}else introScreen()},
edit:function(id){editReturn=true;mode="flow";renderNode(byId(id))},
togBeh:function(){var on=document.body.classList.toggle("behoerden");var b=document.getElementById("behTog");if(b)b.setAttribute("aria-checked",String(on))},
submit:function(){document.getElementById("doneMsg").classList.add("show");
  var ns=document.getElementById("nextSteps");if(ns)ns.classList.add("show");
  clearDraft();refreshStore();var b=document.getElementById("submitBtn");b.disabled=true;b.textContent="Geprüft ✓"},
exportECH:function(){var out={form:F.meta.titel,form_id:F.meta.form_id,erzeugt:new Date().toISOString(),ech:{},ohne_standard:{}};
  for(var i=0;i<N.length;i++){var n=N[i];if(!passes(n))continue;
    if(n.type==="form"||n.type==="confirm"){(n.fields||[]).forEach(function(f){var v=A[f.key];if(v===undefined||v==="")return;
      var k=profKey(n,f);if(k){var pp=k.split("·");(out.ech[pp[0]]=out.ech[pp[0]]||{})[pp[1]]=v}else out.ohne_standard[f.label]=v});continue}
    var v0=A[okey(n)];if(v0===undefined||v0===""||n.type==="note")continue;
    var k0=profKey(n,null);if(k0){var p0=k0.split("·");(out.ech[p0[0]]=out.ech[p0[0]]||{})[p0[1]]=v0}
    else out.ohne_standard[olabel(n)]=Array.isArray(v0)?v0.join(" | "):v0}
  var a=document.createElement("a");a.href="data:application/json;charset=utf-8,"+encodeURIComponent(JSON.stringify(out,null,1));
  a.download=(F.meta.id||"formular")+"-ech.json";a.click()},
restart:function(){A={};hist=[];PROV={};mode="flow";editReturn=false;clearDraft();document.body.classList.remove("behoerden");introScreen()},
resume:function(){var d=loadDraft();
  if(!d){this.begin();return}A=d.A;hist=d.hist.filter(function(id){return!!byId(id)});mode="flow";
  var last=byId(hist[hist.length-1]);if(last)renderNode(last);else this.begin()},
toLanding:function(){var fl=F||SEL;document.body.classList.remove("playing");detail(fl||FLOWS[0],true)}
};
// Enter in a field of a question continues like the «Weiter» button (an open suggestion list
// takes the key first, see __ac.k)
stage.addEventListener("keydown",function(e){if(e.key!=="Enter"||e.defaultPrevented)return;var t=e.target;
  if(t.tagName!=="INPUT"||!(t.id==="ffi"||t.classList.contains("ffc")||(t.classList.contains("ac-input")&&!t.closest(".roster-card"))))return;
  var b=stage.querySelector(".nav .btn-primary");if(b){e.preventDefault();b.click()}});
// The suggestion list of a place or country field. With the mouse: click a suggestion. With the
// keyboard: arrow down/up marks a suggestion, Enter takes the marked one (or the first), Escape
// closes the list; the focus stays in the field the whole time (the list itself is no Tab stop,
// tabindex=-1: a scrolling box would otherwise become one, and leaving the field closes it). A
// name typed out in full counts as chosen.
window.__ac={
render:function(inp,key,clearHidden){var q=(inp.value||"").toLowerCase().trim();var opts=ACOPTS[key]||[];
  var list=document.getElementById("ac_"+key);var wrap=inp.parentNode,hid=wrap.querySelector("input[type=hidden]");
  if(clearHidden)hid.value="";
  inp.removeAttribute("aria-activedescendant");inp.setAttribute("aria-expanded","true");
  var m=[];for(var i=0;i<opts.length&&m.length<8;i++){if((""+opts[i][1]).toLowerCase().indexOf(q)>-1)m.push(opts[i])}
  if(!m.length){list.innerHTML='<div class="ac-empty">Kein Treffer – Sie können den Text auch frei stehen lassen.</div>';list.classList.add("open");
    hid.value=inp.value;return}
  if(clearHidden&&q){for(var e=0;e<opts.length;e++){if((""+opts[e][1]).toLowerCase()===q){hid.value=opts[e][1];break}}}
  var h="";for(var j=0;j<m.length;j++){h+='<div class="ac-item" role="option" aria-selected="false" id="ac_'+key+'_'+j+'" onmousedown="__ac.pick(event,\''+key+'\',this)" data-code="'+esc(m[j][0])+'"><span>'+esc(m[j][1])+'</span><span class="code">'+esc(m[j][0])+'</span></div>'}
  list.innerHTML=h;list.classList.add("open")},
f:function(inp,key){this.render(inp,key,true)},
open:function(inp,key){this.render(inp,key,false)},
close:function(key,inp){var l=document.getElementById("ac_"+key);if(l)l.classList.remove("open");
  if(inp){inp.setAttribute("aria-expanded","false");inp.removeAttribute("aria-activedescendant")}},
choose:function(key,el){var wrap=el.parentNode.parentNode,inp=wrap.querySelector(".ac-input"),t=el.querySelector("span").textContent;
  inp.value=t;wrap.querySelector("input[type=hidden]").value=t;this.close(key,inp)},
pick:function(ev,key,el){ev.preventDefault();this.choose(key,el)},
k:function(ev,key){var inp=ev.target,list=document.getElementById("ac_"+key),open=list.classList.contains("open");
  if(ev.key==="Escape"){if(open){ev.stopPropagation();this.close(key,inp)}return}
  if(ev.key==="ArrowDown"||ev.key==="ArrowUp"){ev.preventDefault();if(!open)this.render(inp,key,false);
    var its=list.querySelectorAll(".ac-item");if(!its.length)return;
    var cur=-1;for(var i=0;i<its.length;i++)if(its[i].classList.contains("act"))cur=i;
    var nx=ev.key==="ArrowDown"?(cur+1)%its.length:(cur<=0?its.length-1:cur-1);
    for(i=0;i<its.length;i++){its[i].classList.toggle("act",i===nx);its[i].setAttribute("aria-selected",String(i===nx))}
    inp.setAttribute("aria-activedescendant",its[nx].id);if(its[nx].scrollIntoView)its[nx].scrollIntoView({block:"nearest"});return}
  if(ev.key==="Enter"&&open){var a=list.querySelector(".ac-item.act")||list.querySelector(".ac-item");
    if(a){ev.preventDefault();this.choose(key,a)}else this.close(key,inp)}}
};
document.addEventListener("click",function(e){if(!e.target.closest||!e.target.closest(".ac")){var ls=document.querySelectorAll(".ac-list.open");for(var i=0;i<ls.length;i++)ls[i].classList.remove("open")}});
// the help drawer: opening moves the focus to its close button, closing (button, Escape, click
// beside it) returns it to where it was
window.__help={last:null,
open:function(){this.last=document.activeElement;document.getElementById("helpDrawer").classList.add("open");document.getElementById("helpOverlay").classList.add("open");
  var x=document.querySelector("#helpDrawer .x");if(x)x.focus()},
close:function(){document.getElementById("helpDrawer").classList.remove("open");document.getElementById("helpOverlay").classList.remove("open");
  var l=this.last;this.last=null;if(l&&l!==document.body&&document.contains(l))l.focus()}};
document.addEventListener("keydown",function(e){if(e.key==="Escape"&&document.getElementById("helpDrawer").classList.contains("open"))__help.close()});
// whatever a click or key starts runs behind fail(): a step that throws shows a message
guard(window.__ff);guard(window.__side);guard(window.__store);
try{landing();window.__ffStarted=true}catch(e){try{console.error(e)}catch(x){}}
})();
</script>
<script>
// the page's own script did not get as far as drawing the start screen (cut-off file, damaged
// data): say so instead of leaving «Wird geladen…» on the page
if(!window.__ffStarted){document.getElementById("stage").innerHTML='<div class="failbox" role="alert"><b>Die geführten Formulare konnten nicht gestartet werden.</b> Bitte laden Sie die Seite neu. Bleibt die Meldung, ist die Datei unvollständig oder beschädigt – zum Beispiel nach einem abgebrochenen Download.</div>'}
</script>
</body>
</html>"""


# the look comes from scripts/theme.py (one definition for all generated pages)
TEMPLATE = TEMPLATE.replace("/*THEME*/", THEME.css_root()).replace("/*FAVICON*/", THEME.favicon())


def datenfelder(c, fid):
    """Data fields of a form incl. eCH assignment and subfields with their own eCH."""
    subs = {}
    for r in c.execute("""SELECT sf.data_field_id d, sf.name, sf.ech_status,
                          COALESCE(e.standard, sf.ech_standard_code) std, e.name el,
                          st.status sstat, st.url surl
                          FROM data_subfield sf
                          LEFT JOIN ech_element e ON e.id=sf.ech_element_id
                          LEFT JOIN ech_standard st ON st.code=COALESCE(e.standard, sf.ech_standard_code)
                          ORDER BY sf.data_field_id, sf.ord""", ):
        subs.setdefault(r["d"], []).append({
            "name": r["name"],
            "ech": ({"standard": r["std"], "element": r["el"], "status": r["sstat"],
                     "url": r["surl"]} if r["std"] else None),
            "ech_status": r["ech_status"]})
    out = []
    for d in c.execute("""SELECT d.id, d.name, d.definition, d.data_type, d.required, d.sensitive,
                          d.no_basis, d.basis_typ, d.subjekt, d.ech_status, COALESCE(e.standard, d.ech_standard_code) std, e.name el,
                          st.status sstat, st.url surl, st.title stitle,
                          EXISTS(SELECT 1 FROM data_field_legal_basis lb WHERE lb.data_field_id=d.id) has_basis
                          FROM data_field d
                          LEFT JOIN ech_element e ON e.id=d.ech_element_id
                          LEFT JOIN ech_standard st ON st.code=COALESCE(e.standard, d.ech_standard_code)
                          WHERE d.form_id=? ORDER BY d.ord""", [fid]):
        out.append({"name": d["name"], "definition": d["definition"], "typ": d["data_type"],
                    "pflicht": bool(d["required"]), "sensibel": d["sensitive"],
                    "freiwillig": d["basis_typ"] == "ohne",   # task-necessary fields stay required
                    "no_basis": bool(d["no_basis"]), "basis_typ": d["basis_typ"],
                    "has_basis": bool(d["has_basis"]),   # a cited article exists (data_field_legal_basis)
                    "subjekt": d["subjekt"],
                    "ech_status": d["ech_status"],
                    "ech": ({"standard": d["std"], "element": d["el"], "status": d["sstat"],
                             "url": d["surl"], "titel": d["stitle"]} if d["std"] else None),
                    "teilfelder": subs.get(d["id"], [])})
    return out


def bekanntgaben(c, fid):
    """Documented recipients of a form — the same form_disclosure/article/law join
    export_json.py uses for the dashboard's Verzeichnis and Datenfluss, so the
    flow's note can never name a recipient the compliance view does not."""
    out = []
    for r in c.execute("""SELECT fd.empfaenger, fd.mode, a.article_no, l.short_title, l.sr_number,
                          l.jurisdiction_level jur
                          FROM form_disclosure fd
                          LEFT JOIN article a ON a.id=fd.article_id
                          LEFT JOIN law l ON l.id=a.law_id
                          WHERE fd.form_id=? ORDER BY fd.empfaenger""", [fid]):
        art = None
        if r["article_no"]:
            art = r["article_no"] + (" " + r["short_title"].strip() if r["short_title"] else "")
            if r["sr_number"]:   # federal law is numbered SR, the Schaffhauser Rechtsbuch SHR
                art += ", " + ("SR " if r["jur"] == "federal" else "SHR ") + r["sr_number"]
        out.append({"empfaenger": r["empfaenger"], "mode": r["mode"], "artikel": art})
    return out


# ---- flow prose vs. the databank's basis verdicts ---------------------------
# The July flow JSON calls fields «freiwillig» by the look of the form. In the
# databank only basis_typ 'ohne' (Over-collection) is voluntary; 'artikel',
# 'aufgabe' and 'offen' fields are legally based, task-necessary or undecided —
# the same word on two surfaces would contradict the compliance view.
FREI_RX = re.compile(r"freiwillig|keine gesetzliche Pflicht", re.I)
PROSE_KEYS = ("ask", "hint", "why", "text", "intro")
# sentence split that does not break after the abbreviations the prose uses
# («Art. 33», «z.B. MedReg», «bzw. im Berufsregister») — a split there would let a
# sentence-level rewrite drop half a citation
SENT_SPLIT = re.compile(r"(?<!\bArt\.)(?<!\bAbs\.)(?<!\blit\.)(?<!\bZiff\.)(?<!\bNr\.)(?<!\bz\.B\.)"
                        r"(?<!\bbzw\.)(?<!\bu\.a\.)(?<!\bd\.h\.)(?<!\bca\.)(?<!\bvgl\.)(?<!\binkl\.)"
                        r"(?<!\bevtl\.)(?<!\bggf\.)(?<!\bresp\.)(?<=[.!?])\s+")
# form-optional fields (required=0): «freiwillig» -> «optional», the form's own vocabulary
OPT_SUBS = [
    (re.compile(r"\bFreiwillige Angaben\b"), "Optionale Angaben"),
    (re.compile(r"\bfreiwillige Angaben\b"), "optionale Angaben"),
    (re.compile(r"\bFreiwillige Angabe\b"), "Optionale Angabe"),
    (re.compile(r"\bfreiwillige Angabe\b"), "optionale Angabe"),
    (re.compile(r"\bFreiwillig\b"), "Optional"),
    (re.compile(r"\bfreiwillig\b"), "optional"),
    (re.compile(r"\b(E|e)s (besteht|gibt) keine gesetzliche Pflicht( zu dies\w+ Angaben?)?"),
     lambda m: ("D" if m.group(1) == "E" else "d") + "as Formular verlangt sie nicht"),
]
# `hilfe` (help drawer, «So füllen Sie das aus») talks about the node's own sub-fields
# — «Der Titel ist freiwillig», «Fax und Webseite sind freiwillig» — on data fields
# the form REQUIRES. Those sentences are about form-optional SUB-PARTS, so they take
# the word-level path («optional», the label's own vocabulary: «Titel (optional)») and
# only when they name one of the node's own optional sub-field labels; the sentence
# replacement («Das Formular verlangt diese Angabe») would be wrong for the Titel/Fax
# part. Domain uses never name a sub-field label and stay: «freiwillige AHV» (F273),
# «für ein gewöhnliches Wohnhaus ist es meist freiwillig» (F187), «freiwillige, aber
# regelmässige Unterstützung» (F282), «Eine Vertretung ist freiwillig» (F254).
LABEL_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")   # «Titel (optional)» -> «Titel»

# ---- exclusive-use promises vs. the documented disclosures -------------------
# «… werden nur für die Abklärung verwendet», «dienen allein der Beurteilung Ihres
# Gesuchs»: a promise no databank row backs — and on forms WITH form_disclosure rows
# (F26, F37, F170, F273) the node badge right beside it names article-backed
# recipients. Such a sentence is replaced by what the databank documents (the same
# sentence the page's bekText() builds: recipients, or «noch nicht dokumentiert»);
# a sentence that cites a norm itself is left alone — the citation is its backing.
PROMISE_RX = re.compile(
    r"\b(?:werden|wird) (?:nur|ausschliesslich|allein) (?:für|zur|zum) [^.;]*?\b(?:verwendet|genutzt|gebraucht)\b"
    r"|\bdienen allein der Beurteilung\b", re.I)
CITED_RX = re.compile(r"§|\bArt\.|\bArtikel\b")
# «X ist besonders geschützt und wird nur für … verwendet.» -> keep the first clause
PROMISE_TAIL = re.compile(r"^(?P<pre>.+?)(?:,|;| –)?\s+und\s+(?:werden|wird|dienen)\s+(?:nur|ausschliesslich|allein)\b.*$", re.S)
# «Ihre Kontodaten werden nur für … verwendet und haben keinen Einfluss …» -> keep the second
PROMISE_HEAD = re.compile(r"^(?P<subj>[^,;]+?)\s+(?:werden|wird)\s+(?:nur|ausschliesslich|allein)\s+(?:für|zur|zum)\s+"
                          r"[^.;]*?\b(?:verwendet|genutzt|gebraucht)\b\s+und\s+(?P<rest>.+)$", re.S)
# a whole-form claim in an opening note («Keine der Angaben ist gesetzlich
# vorgeschrieben – Sie dürfen einzelne Fragen überspringen»), which the flag pass
# below contradicts as soon as one node loses its skip button
NOTE_FREI_RX = re.compile(r"\bKeine der Angaben ist gesetzlich vorgeschrieben\b|\bdürfen (?:Sie )?einzelne Fragen überspringen\b", re.I)

# hand-checked touch-ups AFTER the mechanical rewrite of the same key: a dropped
# sentence took a pronoun's antecedent («es» = Erziehungsdepartement) or a contrast
# word's counterpart («aber» vs. «rechtlich freiwillig») with it. Applied only when
# the rewrite happened and the anchor is present — otherwise the build says so, so a
# regenerated flow never silently keeps a stale patch.
TOUCH_UPS = {
    (405, "absender", "why"): ("Mit der Telefonnummer erreicht es Sie direkt",
                               "Mit der Telefonnummer erreicht das Erziehungsdepartement Sie direkt"),
    (170, "kinder", "why"): ("Ohne sie kann die Dienststelle die Betreuungsgutschriften aber keinem Kind zuordnen",
                             "Ohne sie kann die Dienststelle die Betreuungsgutschriften keinem Kind zuordnen"),
}


def basis_of(field):
    """artikel / aufgabe / ohne / offen / zu_ermitteln. A field without a panel verdict
    (basis_typ NULL) is 'artikel' only when an article is actually cited for it
    (data_field_legal_basis row) — the dashboard's rule («Rechtsgrundlage zu
    ermitteln» otherwise); an unjudged no_basis field stays 'offen'. Never upgraded."""
    if field.get("basis_typ"):
        return field["basis_typ"]
    if field.get("no_basis"):
        return "offen"
    return "artikel" if field.get("has_basis") else "zu_ermitteln"


def basis_sentence(fields, plural):
    """One neutral sentence for a node the form REQUIRES; the weakest claim among
    its fields wins (offen > zu_ermitteln > aufgabe > artikel) so nothing is overclaimed."""
    typs = {basis_of(f) for f in fields if f["pflicht"]}
    ang = "diese Angaben" if plural else "diese Angabe"
    if "offen" in typs:
        return f"Das Formular verlangt {ang} – ob die Aufgabe sie erfordert, ist noch nicht beurteilt."
    if "zu_ermitteln" in typs:
        return f"Das Formular verlangt {ang} – die Rechtsgrundlage ist noch zu ermitteln."
    if "aufgabe" in typs:
        return f"Das Formular verlangt {ang} – ohne ausdrückliche Norm, aber für die Aufgabe notwendig (aufgabennotwendig)."
    return f"Das Formular verlangt {ang} – die gesetzliche Grundlage ist mit Artikel belegt."


def neutralise(text, fields, plural):
    """Rewrite one prose string so it no longer calls a non-'ohne' field freiwillig."""
    if not text or not FREI_RX.search(text):
        return text
    if any(f["pflicht"] for f in fields):
        # required by the form: drop every sentence that claims voluntariness and
        # put the databank's verdict where the first one stood
        sents = SENT_SPLIT.split(text.strip())
        kept, inserted = [], False
        for s in sents:
            if FREI_RX.search(s):
                if not inserted:
                    kept.append(basis_sentence(fields, plural))
                    inserted = True
            else:
                kept.append(s)
        text = " ".join(kept)
    else:
        for rx, rep in OPT_SUBS:
            text = rx.sub(rep, text)
    if FREI_RX.search(text):   # an unforeseen phrasing: drop the sentence rather than keep the claim
        sents = [s for s in SENT_SPLIT.split(text.strip()) if not FREI_RX.search(s)]
        text = " ".join(sents) or basis_sentence(fields, plural)
    return text


def optional_labels(node):
    """Labels of the node's form-optional sub-fields («Titel (optional)» -> «Titel»)."""
    out = []
    for f in node.get("fields") or []:
        if f.get("pflicht"):
            continue
        lab = LABEL_SUFFIX.sub("", f.get("label") or "").strip()
        if lab:
            out.append(lab)
    return out


def neutralise_hilfe(text, labels):
    """Word-level «freiwillig» -> «optional», only in sentences that name one of the
    node's own optional sub-field labels; every other sentence is left as it is."""
    if not text or not labels or not FREI_RX.search(text):
        return text
    rxs = [re.compile(r"(?<!\w)" + re.escape(l) + r"(?!\w)") for l in labels]
    out = []
    for s in SENT_SPLIT.split(text.strip()):
        if FREI_RX.search(s) and any(rx.search(s) for rx in rxs):
            for rx, rep in OPT_SUBS:
                s = rx.sub(rep, s)
        out.append(s)
    return " ".join(out)


def bek_text(bek):
    """Python twin of the page's bekText(): the documented recipients of the form as
    one sentence, recipients sharing an article cited once. Returns (text, offen)."""
    if not bek:
        return "Eine Weitergabe an andere Stellen ist für dieses Formular noch nicht dokumentiert.", True
    mode_lab = LABELS.as_export()["mode"]

    def grouped(lst):
        by, order = {}, []
        for x in lst:
            a = x["artikel"] or "Rechtsgrundlage noch nicht benannt"
            if a not in by:
                by[a] = []
                order.append(a)
            by[a].append(x["empfaenger"])
        return "; ".join(", ".join(by[a]) + " (" + a + ")" for a in order)
    sys_ = [x for x in bek if x["mode"] == "systematisch"]
    anf = [x for x in bek if x["mode"] == "auf_anfrage"]
    rest = [x for x in bek if x["mode"] not in ("systematisch", "auf_anfrage")]
    parts = []
    if sys_:
        parts.append("werden von Gesetzes wegen gemeldet an " + grouped(sys_))
    if anf:
        parts.append("können auf Anfrage bekanntgegeben werden an " + grouped(anf))
    if rest:
        parts.append("Bekanntgabe " + "; ".join(
            mode_lab.get(x["mode"], f"⟨{x['mode']}⟩") + ": " + x["empfaenger"]
            + " (" + (x["artikel"] or "Rechtsgrundlage noch nicht benannt") + ")" for x in rest))
    return "Angaben aus diesem Formular " + " und ".join(parts) + ".", False


def neutralise_promise(text, bek, bek_offen):
    """Replace every exclusive-use promise sentence by the documented disclosure
    sentence; a sentence that cites a norm is kept (the citation is its backing)."""
    if not text or not PROMISE_RX.search(text):
        return text
    after_semicolon = (bek[0].lower() + bek[1:]) if bek_offen else bek   # «…; eine Weitergabe …»
    out = []
    for s in SENT_SPLIT.split(text.strip()):
        if not PROMISE_RX.search(s) or CITED_RX.search(s):
            out.append(s)
            continue
        m = PROMISE_TAIL.match(s)
        if m:
            out.append(m.group("pre").rstrip(" ,;–") + "; " + after_semicolon)
            continue
        m = PROMISE_HEAD.match(s)
        if m:
            out.append(bek + " " + m.group("subj").strip() + " " + m.group("rest").strip())
            continue
        out.append(bek)
    return " ".join(out)


def correct_nodes(fl, fid, log):
    """Apply the databank's verdicts to the flow nodes (in memory, at build time).
    Returns nothing; appends human-readable lines to `log`."""
    by_name = {d["name"]: d for d in fl.get("datenfelder", [])}
    bek, bek_offen = bek_text(fl.get("bekanntgaben") or [])
    for n in fl.get("nodes", []):
        # 0) exclusive-use promises are about the FORM, so every node incl. notes
        for k in PROSE_KEYS + ("hilfe",):
            old = n.get(k)
            if isinstance(old, str) and PROMISE_RX.search(old):
                new = neutralise_promise(old, bek, bek_offen)
                if new != old:
                    n[k] = new
                    log.append(f"PROSA-ZWECK  F{fid} {n['id']}.{k}\n    «{old}»\n  → «{new}»")
        fields = [by_name[x] for x in (n.get("field") or []) if x in by_name]
        if not fields or all(f["freiwillig"] for f in fields):
            continue   # no data field, or genuinely voluntary ('ohne'): chip + skip stay
        plural = len(fields) > 1 or n.get("type") in ("form", "roster", "confirm")
        # 1) optional flag: every field required by the form, no_basis, judged aufgabe/offen
        if n.get("optional") and all(f["pflicht"] and f["no_basis"] and basis_of(f) in ("aufgabe", "offen")
                                     for f in fields):
            n["optional"] = False
            log.append(f"OPTIONAL→PFLICHT  F{fid} {n['id']}: {', '.join(f['name'] for f in fields)}")
        elif n.get("optional") and all(f["pflicht"] for f in fields):
            typs = "/".join(sorted({basis_of(f) for f in fields}))
            log.append(f"HINWEIS optional belassen ({typs}) F{fid} {n['id']}: "
                       f"{', '.join(f['name'] for f in fields)}")
        # 2) prose
        for k in PROSE_KEYS:
            old = n.get(k)
            if isinstance(old, str) and FREI_RX.search(old):
                new = neutralise(old, fields, plural)
                if new != old:
                    tu = TOUCH_UPS.get((fid, n["id"], k))
                    if tu:
                        if tu[0] in new:
                            new = new.replace(tu[0], tu[1])
                        else:
                            log.append(f"WARN Lesbarkeits-Patch F{fid} {n['id']}.{k}: Anker «{tu[0]}» fehlt — "
                                       f"Eintrag in TOUCH_UPS prüfen")
                    n[k] = new
                    log.append(f"PROSA  F{fid} {n['id']}.{k}\n    «{old}»\n  → «{new}»")
            elif TOUCH_UPS.get((fid, n["id"], k)):
                log.append(f"HINWEIS Lesbarkeits-Patch F{fid} {n['id']}.{k} nicht mehr nötig (Text neu erzeugt?)")
        # 3) help drawer: sub-field statements, word-level and label-gated only
        old = n.get("hilfe")
        if isinstance(old, str) and FREI_RX.search(old):
            new = neutralise_hilfe(old, optional_labels(n))
            if new != old:
                n["hilfe"] = new
                log.append(f"PROSA-HILFE  F{fid} {n['id']}.hilfe\n    «{old}»\n  → «{new}»")


def flow_basis_note(fl):
    """One sentence on the flow's required fields for an opening note that claimed
    «Keine der Angaben ist gesetzlich vorgeschrieben» (weakest claim wins), plus the
    skip sentence only while a node is still skippable after the flag pass."""
    typs = {basis_of(d) for d in fl.get("datenfelder", []) if d["pflicht"] and not d["freiwillig"]}
    if not typs:
        return None
    if typs == {"aufgabe"}:
        s = ("Eine ausdrückliche gesetzliche Vorschrift gibt es für diese Angaben nicht; das Formular "
             "verlangt die Pflichtfelder aber, weil die Aufgabe sie braucht (aufgabennotwendig).")
    elif typs & {"offen", "zu_ermitteln"}:
        s = ("Nicht jede Angabe ist gesetzlich vorgeschrieben; ob die Aufgabe einzelne Angaben erfordert, "
             "ist noch nicht beurteilt – das Formular verlangt die Pflichtfelder gleichwohl.")
    elif "aufgabe" in typs:
        s = ("Nicht jede Angabe ist gesetzlich vorgeschrieben; das Formular verlangt die Pflichtfelder "
             "aber, weil die Aufgabe sie braucht (aufgabennotwendig).")
    else:
        s = "Die Pflichtangaben sind gesetzlich vorgeschrieben (die Grundlage ist mit Artikel belegt)."
    by_name = {d["name"]: d for d in fl.get("datenfelder", [])}
    skippable = any(n.get("optional") or (n.get("field") and all(by_name.get(x, {}).get("freiwillig")
                                                                  for x in n["field"]))
                    for n in fl.get("nodes", []))
    if skippable:   # the player marks those nodes with an «Überspringen» button, nothing else
        s += " Wo die Schaltfläche «Überspringen» erscheint, dürfen Sie die Frage auslassen."
    return s


def correct_notes(fl, fid, log):
    """Opening notes (type note, no field) that declare the whole form skippable
    contradict the flipped flags — rewritten from the flow's own fields, AFTER the
    flag pass of correct_nodes()."""
    for n in fl.get("nodes", []):
        if n.get("type") != "note" or n.get("field"):
            continue
        old = n.get("text")
        if not isinstance(old, str) or not NOTE_FREI_RX.search(old):
            continue
        rep = flow_basis_note(fl)
        sents, done = [], False
        for s in SENT_SPLIT.split(old.strip()):
            if NOTE_FREI_RX.search(s):
                if rep and not done:
                    sents.append(rep)
                    done = True
            else:
                sents.append(s)
        new = " ".join(sents)
        if new != old:
            n["text"] = new
            log.append(f"NOTIZ  F{fid} {n['id']}.text\n    «{old}»\n  → «{new}»")


EMAIL_RX = re.compile(r"^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$")


def kontakt_teile(dv):
    """The DVSH contact of a service as typed parts — adresse, telefon, email — so the page
    can label each one as the dashboard does («Kontakt (laut DVSH): Adresse · Tel. … ·
    E-Mail …»). Values stay exactly as the DVSH stores them (a number written «052 …» is
    shown as «052 …»; only the page's tel: link target is normalised). dvsh_service.kontakt
    is the e-mail address in today's data; a free text there is kept as `text`, a JSON
    object contributes its own name/telefon/email/adresse. None when nothing is stored."""
    teile = {"adresse": (dv["address"] or "").strip(), "telefon": (dv["phone"] or "").strip(),
             "email": (dv["email"] or "").strip()}
    raw = dv["kontakt"]
    try:
        ko = json.loads(raw) if raw else None
    except ValueError:
        ko = raw
    if isinstance(ko, dict):
        for k in ("name", "adresse", "telefon", "email"):
            v = str(ko.get(k) or "").strip()
            if v and (k == "name" or not teile.get(k)):
                teile[k] = v
    elif isinstance(ko, list):
        ko = " · ".join(str(x).strip() for x in ko if str(x or "").strip())
    if isinstance(ko, str) and ko.strip():
        ko = ko.strip()
        if EMAIL_RX.match(ko):
            teile["email"] = ko          # the address the page has always shown for this service
        elif ko not in teile.values():
            teile["text"] = ko
    teile = {k: v for k, v in teile.items() if v}
    return teile or None


def datenstand():
    """The data date is computed once, in export_json.py — read it, never re-derive it."""
    try:
        with open(EXPORT_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        ds = d.get("datenstand") or {}
        return {"build": ds.get("build") or (d.get("generated_at") or "")[:10] or None,
                "dvsh_stand": ds.get("dvsh_stand"), "shep_harvest": ds.get("shep_harvest")}
    except (OSError, ValueError) as e:
        print("WARN: data_export.json nicht lesbar — Datenstand bleibt offen:", e)
        return {"build": None, "dvsh_stand": None, "shep_harvest": None}


def main():
    c = connect(DB_PATH)
    flows = []
    log = []
    # the exported Formulare (units with their party and prefill marks), read once
    try:
        with open(EXPORT_PATH, encoding="utf-8") as fh:
            export_forms = {f["id"]: f for f in json.load(fh).get("forms") or []}
    except (OSError, ValueError) as e:
        sys.exit(f"ABBRUCH build_flows.py: data_export.json nicht lesbar ({e}) — zuerst scripts/export_json.py")
    import hashlib
    n_forms = c.execute("SELECT count(*) FROM form").fetchone()[0]
    try:
        for r in c.execute("""SELECT ff.form_id, ff.flow, ff.form_hash, ff.generated_at,
                              f.source_file, s.id sid, s.dienststelle, s.department FROM formflow ff
                              JOIN form f ON f.id=ff.form_id JOIN service s ON s.id=f.service_id
                              ORDER BY s.department, s.name"""):
            fl = json.loads(r["flow"])
            # DB is the source of truth for office/department — flow drafts sometimes
            # "correct" the spelling (Departement vs Department) and split the sidebar
            fl["meta"]["amt"] = r["dienststelle"] or fl["meta"].get("amt")
            fl["meta"]["departement"] = r["department"] or fl["meta"].get("departement")
            fl["meta"]["stand"] = (r["generated_at"] or "")[:10]
            fl["meta"]["stand_txt"] = LABELS.fmt_date(fl["meta"]["stand"])   # reader-facing dd.mm.yyyy
            # the «Original ansehen» link must resolve inside the repository: form.source_file
            # (relative to ROOT, like flows.html itself) — the flow JSON's own quelldatei points
            # at a folder on the author's machine. No file → no link, said so.
            fl["meta"]["quelldatei"] = r["source_file"] or None
            # staleness: source file changed since the flow was derived?
            stale = False
            src = os.path.join(ROOT, r["source_file"]) if r["source_file"] else None
            if src and os.path.exists(src) and r["form_hash"]:
                cur = hashlib.sha256(open(src, "rb").read()).hexdigest()[:16]
                stale = (cur != r["form_hash"])
            fl["meta"]["veraltet"] = stale
            fl["datenfelder"] = datenfelder(c, r["form_id"])
            fl["bekanntgaben"] = bekanntgaben(c, r["form_id"])
            correct_nodes(fl, r["form_id"], log)     # flags + prose (reads bekanntgaben)
            correct_notes(fl, r["form_id"], log)     # whole-form notes, after the flag pass
            # eCH map for once-only prefill: the player prefills from the CITIZEN's
            # profile and saves answers back into it, keyed by element — so only the
            # applicant's own Angaben may be in it, never a spouse's, a child's or an
            # employee's (they would be offered later as the citizen's own). ONE rule,
            # the one citygov_prefill.json and burden.prefillable use
            # (register_map.prefill_punkte: Einwohnerregister mark, party Gesuchsteller/in
            # as a natural person, not mehrdeutig within that party). Keys «Feld» or
            # «Feld›Teilfeld» -> "eCH-XXXX·element"
            xf = export_forms.get(r["form_id"])
            if xf is None:
                sys.exit(f"ABBRUCH build_flows.py: Formular {r['form_id']} fehlt in data_export.json — "
                         "zuerst scripts/export_json.py ausführen")
            fl["ech_map"] = register_map.flow_schluessel(xf)
            # DVSH: real process steps + contact for the done screen
            dv = c.execute("SELECT ablauf, kontakt, email, phone, address FROM dvsh_service "
                           "WHERE service_id=? LIMIT 1", [r["sid"]]).fetchone()
            if dv:
                try:
                    ab = json.loads(dv["ablauf"]) if dv["ablauf"] else []
                    if isinstance(ab, str):   # double-encoded row: decode once more, never slice text
                        ab = json.loads(ab)
                    # items that are still JSON text are decoded too, so no step is shown as raw JSON
                    ab = [json.loads(x) if isinstance(x, str) and x.lstrip().startswith("{") else x
                          for x in (ab if isinstance(ab, list) else [])]
                except Exception:
                    ab = []
                ko = kontakt_teile(dv)   # typed parts: adresse / telefon / email
                if ab or ko:
                    fl["dvsh"] = {"ablauf": ab[:8], "kontakt": ko}
                    if len(ab) > 8:   # capped list: the gap is shown as a gap, never silently cut
                        fl["dvsh"]["ablauf_mehr"] = LABELS.pl(len(ab) - 8, "weiterer Schritt", "weitere Schritte")
            flows.append(fl)
    except Exception as e:
        # loud, never a half-empty page (lesson 16): a missing formflow table or a
        # broken flow JSON aborts the build instead of writing 0 flows
        print("ABBRUCH beim Lesen der Flows (formflow-Tabelle fehlt oder Flow-JSON defekt):", e)
        raise
    c.close()
    for line in log:
        print(line)
    def n_of(prefix):
        return sum(1 for l in log if l.startswith(prefix + " "))
    print(f"-- {n_of('OPTIONAL→PFLICHT')} Knoten optional→Pflicht, {n_of('PROSA')} Prosa-Stellen neutralisiert "
          f"(«freiwillig» nur noch für basis_typ 'ohne'), {n_of('PROSA-HILFE')} Hilfetexte «freiwillig»→«optional», "
          f"{n_of('PROSA-ZWECK')} Zweckversprechen durch dokumentierte Bekanntgaben ersetzt, "
          f"{n_of('NOTIZ')} Formular-Hinweise angepasst, {n_of('WARN')} Warnungen")
    # without the geo lists the guided forms lose their place/postcode/country
    # autocomplete — never publish that degraded page silently
    if not os.path.exists(GEO):
        sys.exit("ABBRUCH: quellen/ch-geo.js fehlt — ohne die Datei verliert flows.html die "
                 "Autocomplete-Listen für Gemeinde, PLZ und Land")
    geo = open(GEO, encoding="utf-8").read()
    # the geo lists are inlined as script text, not as JSON: they cannot be escaped, so a
    # «<» in them (which could end or swallow the script element) stops the build instead
    if "<" in geo:
        sys.exit("ABBRUCH: quellen/ch-geo.js enthält das Zeichen «<» — als Skripttext eingebettet "
                 "könnte es das Skript der Seite beenden; bitte im Quelltext als \\u003c schreiben")
    ds = datenstand()
    today = date.today().isoformat()
    flow_dates = sorted({f["meta"].get("stand") for f in flows if f["meta"].get("stand")})
    fmt = LABELS.fmt_date   # reader-facing dates as dd.mm.yyyy (the HTML build comment keeps ISO)
    stamp = ("Datenstand: Export " + (fmt(ds["build"]) if ds["build"] else "offen")
             + (" · DVSH-Stand " + fmt(ds["dvsh_stand"]) if ds["dvsh_stand"] else "")
             + (" · Flows erzeugt " + (fmt(flow_dates[0]) if len(flow_dates) == 1
                                      else f"{fmt(flow_dates[0])} bis {fmt(flow_dates[-1])}") if flow_dates else "")
             + " · Seite gebaut " + fmt(today))
    labels_js = {k: LABELS.as_export()[k] for k in ("sens", "mode", "basis_typ", "node_typ", "kontakt")}

    def js(obj):
        # JSON inside <script>: every «<» is written as backslash-u003c, so no text of the data
        # can end the script element («</script») or open a comment that swallows the rest
        # («<!--» followed by «<script»). The browser reads the escape back as «<», and outside
        # of strings JSON has no «<».
        return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")
    html = (TEMPLATE
            .replace("%%BUILD%%", today)
            .replace("%%NFORMS%%", str(n_forms))
            .replace("%%STAMP%%", js(stamp))
            .replace("%%LABELS%%", js(labels_js))
            .replace("%%GEO%%", geo)
            .replace("%%DATA%%", js(flows)))
    html = re.sub(r"%%I:([a-z0-9-]+)%%", lambda m: icon_svg(m.group(1)), html)
    # guards: the page must work offline (no CDN scripts/stylesheets, no icon font) and
    # every placeholder must be resolved
    leftover = re.findall(r"%%[A-Z]+(?::[a-z0-9-]+)?%%", html)
    assert not leftover, f"unaufgelöste Platzhalter: {leftover[:5]}"
    assert "cdnjs" not in html and 'class="ti ' not in html, "Icon-Font-Rest im Template"
    ext = re.findall(r'<link[^>]+href="(https?://[^"]+)"', html)
    ext += re.findall(r'<script[^>]+src="(https?://[^"]+)"', html)
    assert not ext, f"externe Abhängigkeit (Stylesheet, Schrift oder Skript): {ext}"
    # the inlined data holds no «<» any more (see js()); checked on the finished page: between
    # «var FLOWS=» and the end of that statement there must be none
    a = html.index("var FLOWS=")
    b = html.index(";\n// coverage + data date", a)
    assert "<" not in html[a:b], "die eingebetteten Flow-Daten enthalten ein unmaskiertes «<»"
    assert_no_local_paths("flows.html", html)
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"wrote {OUT}  ({os.path.getsize(OUT)//1024} KB, {len(flows)} von {n_forms} Formularen mit Flow; {stamp})")


if __name__ == "__main__":
    main()
