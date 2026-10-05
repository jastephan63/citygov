#!/usr/bin/env python3
"""Build dashboard.html from data_export.json (convention 9: generated, never edited).

The JSON is inlined into the HTML so the file opens straight from disk via file://
with no server and no fetch (offline by default). Vanilla JS, no framework.

Views (2026-09 redesign; state lives in the URL hash, so links are shareable),
in the six groups of the sidebar:
  * Einstieg — Übersicht (#home: the data standard first, three headline cards
    from DATA.kopfzahlen, further gaps, three doors, the tone key, a compact
    Verlauf) · Für Dienststellen (#dienststellen, + /all/<slug> per office) ·
    Für den Kanton (#kanton) · Methode & Quellen (#methode: method, tones and
    tiers, all key figures, the Verlauf table)
  * Datenstandard — Datenkatalog (#katalog) · Begriffe (#begriffe) ·
    eSH-Katalog (#esh, marked «Entwurf»)
  * Datenmodell & Once-Only — Datenmodell (#datenmodell, + /all/parteien · konzepte ·
    kennungen · gesetzesstand · wirkung, a concept /all/k-<code>, the change-impact explorer at
    a law /all/g-<law id> or an article /all/a-<article id>: whose Angabe each data point is and
    how that was made and checked, one element per Angabe and role, the permanent identifiers
    and the export contract, the edition of every cited law, what a change of a law or article
    affects) · Was Register schon wissen (#onceonly, + /all/register · g-<group> · r-<register>
    · beilagen · zeit · offen: the registers and what they hold according to a cited source, the
    Beilagen they issue, the model estimate of the time saved, the canton's open decisions).
    Read from DATA.parteien, konzepte, wirkung, register, vorbefuellung, kennungen and
    datenmodell (export_json.py) and the export contract (exportvertrag.json, read when the page
    is built); every law and article elsewhere carries its edition chip and a link «betrifft N
    Datenpunkte in M Formularen ›» to the explorer
  * Erscheinungsbild — Gestaltung der Formulare (#gestaltung, + /all/<gruppe> and
    /all/m-<merkmal>, /all/e-<merkmal>, /all/kanton, /all/dienststellen, /all/grenzen as
    shareable section addresses: how the Formulare look — Schrift, Farben, Mindestmerkmale
    der Barrierefreiheit, Kontaktangaben, Aufbau — against the practice of the measured
    Formulare; DATA.gestaltung and form.gestaltung from scripts/gestaltung_export.py; the
    texts describe what differs and never ask an office to change its Formular)
  * Arbeitslisten — Handlungsbedarf (#todo: red and amber only, per
    Dienststelle, CSV) · Recherche der Databank (#recherche: the databank's own
    homework) · Datenschutz-Dossiers (link to dossiers/index.html)
  * Nachschlagewerke — Lebenslagen (#lebenslagen, eCH-0049 Themengruppen) ·
    Verzeichnis (#register) · Datenhandhabung (#rules) · Leitfaden (#guide) ·
    Datenfluss (#datenfluss)
  * Werkstatt · Prototypen — Bürgersicht (#buerger, synthetic Datentresor) ·
    Geführte Formulare (link to flows.html)
plus the Service-Seite (#fields/<service id>: the per-Service hub with
Datenfelder & Handhabung, Gesetze, Beilagen, Digitalisierungs-Hürden,
Duplikat-Radar, the folded panels «Parteien», «Was Register schon wissen» and «Gestaltung» and
a Formular-Ansicht per Formular with its permanent identifier (#fields/<id>/form-<id>~part,
~reg, ~gest open it at that panel)), the sidebar list of
Formulare & Services, and the header search (#search/all/<query>).
The page draws, it does not compute: every figure and every classification comes from
data_export.json (kopfzahlen, dienststellen_uebersicht, the stamped ech_state /
basis_state of each Datenfeld, form.dienststelle, service.dossier_slug); the build stops
when the export lacks one of them (REQUIRED). One helper each for what recurs: a contact
(kontaktHtml — «Kontakt (laut DVSH): Adresse · Tel. … · E-Mail …»), a term of the glossary
(GLOSSAR / term — explained where a headline card uses it, listed on #methode, found by
the search), a share (pctTxt, one decimal everywhere). One rule says where a page opens
(placeAfterRender: a new page at its top, Back/Forward at the place the reader left, a
redraw of the same page where it is); the sidebar stays in view. A view that fails says
so under its own address (viewFailed). The places a new page must be registered are
listed in a comment above drawView().
One status language on every page: a status is drawn in its tone (st-ok / st-act /
st-dec / st-open from DATA.labels.ton_map — the colour says who acts next; a code
without a tone is grey, never green); Kennzeichen (level of law, ⛨, DVSH/SHEP,
↺ Once-Only, channel) stay neutral. The legend is drawn from what the page shows:
the four tones, then only the Kennzeichen the page draws, the data standard first.
Every titled non-link element opens its explanation by click, tap, Enter or Space
(#tipbox, announced via #tiplive) — inside a clickable row too, where the row keeps
its action through its link; a chip with an action of its own (⛨, a rule chip)
offers it in the box. Rows, toggles and links without an address are reachable by
keyboard. Open points are gaps, never «risk»; «Over-collection» is said in plain German
(«ohne Grundlage») and explained once on Methode (gap_wording for texts from elsewhere).
Refuses to build when the Leitfaden cites a rule the databank does not hold.
The page states its own size (and its transfer size over the network) in the
start and failure messages; both are measured on the page being written.

    python3 scripts/build_dashboard.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, EXPORT_PATH, DASHBOARD_PATH, connect, size_txt, net_size_txt
from leitfaden import LEITFADEN
import theme as THEME

TEMPLATE = r"""<!-- GENERATED by scripts/build_dashboard.py from citygov.db via data_export.json — do not edit; run ./build.sh -->
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">%%FAVICON%%
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kanton Schaffhausen — Compliance-Databank</title>
<script>
/* shows a readable message instead of a blank page if the app cannot start
   (old browser, truncated download, blocked script) */
window.__cgStarted=false;
window.__cgFailed=false;
function __cgFail(why){
  // the first message names the true cause; a later call (the three-second check below,
  // a follow-up error) never replaces it
  if(window.__cgStarted||window.__cgFailed) return;
  var m=document.getElementById('main'); if(!m) return;
  window.__cgFailed=true;
  m.innerHTML='<div class="bootmsg err"><b>Das Dashboard konnte nicht gestartet werden.</b>'
    +'<span>Häufigste Ursachen: die Datei ist unvollständig heruntergeladen (sie muss knapp %%SIZE%% gross sein), '
    +'oder der Browser ist zu alt. Am einfachsten: die Online-Fassung öffnen — '
    +'<a href="https://jastephan63.github.io/citygov/dashboard.html">jastephan63.github.io/citygov/dashboard.html</a>. '
    +'Technische Meldung: '+String(why||'unbekannt').replace(/[<>&]/g,'')+'</span></div>';
}
window.addEventListener('error',function(e){__cgFail(e&&e.message);});
// A single saved copy of this file (e-mail, share drive, «Link speichern unter»)
// has no dossiers/, formulare/ or flows.html next to it. Opened from a local
// file, the page probes for a marker the dossier export writes; if it is
// missing, repository links open on the website instead of a browser error page.
window.__cgRepo=null;
var __cgSite='https://jastephan63.github.io/citygov/';
if(location.protocol==='file:'){
  var __p=document.createElement('script'); __p.src='dossiers/_repo.js';
  __p.onload=function(){window.__cgRepo=true;};
  __p.onerror=function(){window.__cgRepo=false;
    var show=function(){ if(document.getElementById('offnote')) return;
      var b=document.createElement('div'); b.id='offnote'; b.className='offnote';
      b.innerHTML='Einzelne Offline-Kopie: Dossiers, Quelldateien und geführte Formulare öffnen sich auf der Website '
        +'(<a href="'+__cgSite+'" target="_blank" rel="noopener">jastephan63.github.io/citygov</a>). '
        +'Ganz ohne Internet gehen sie nur mit dem ganzen Repository («Download ZIP» auf GitHub).';
      document.body.insertBefore(b, document.body.firstChild); };
    if(document.body) show(); else document.addEventListener('DOMContentLoaded', show); };
  document.head.appendChild(__p);
  // capture phase: the link's href is swapped before the browser follows it, so
  // target=_blank and downloads behave exactly as before
  document.addEventListener('click',function(e){
    if(window.__cgRepo!==false) return;
    var a=e.target&&e.target.closest?e.target.closest('a[href]'):null; if(!a) return;
    var h=a.getAttribute('href')||'';
    if(!h||/^(#|[a-z][a-z0-9+.-]*:|\/\/)/i.test(h)) return;
    a.setAttribute('href', __cgSite+h.replace(/^\.\//,''));
  },true);
}
// the page finished loading but the app never started: a cut-off download ends
// before the app script, so no error is ever thrown
window.addEventListener('load',function(){setTimeout(function(){__cgFail('Die Seite endet vor dem Programmteil (Datei unvollständig).');},3000);});
</script>
<style>
  /* Kanton Schaffhausen paper theme — one look for dashboard, guided forms, dossiers and
     landing page: colours, fonts and text sizes are written from scripts/theme.py.
     Use var(--…) below; a new colour or size belongs in theme.py, not here.
     tones — the colour says who acts next (DATA.labels.ton): green geklärt · red
     Dienststelle handelt · amber Kanton entscheidet · grey Databank recherchiert */
/*THEME*/
  /* aliases kept for the JS template strings */
  :root{
    --bg:var(--paper); --panel:var(--card); --panel2:var(--field);
    --bd:var(--line); --bd2:var(--line-soft); --tx:var(--ink);
    --mut:var(--ink-soft); --mut2:var(--ink-faint);
  }
  *{box-sizing:border-box}
  /* every link without a class of its own (tel:, mailto:, links in texts); the keyboard
     focus of a link is the ring of the page, not the browser's own */
  a{color:var(--link);text-underline-offset:2px}
  a:focus-visible{outline:2px solid var(--link);outline-offset:1px;border-radius:4px}
  /* the same ring on every native control (sidebar tabs, filter chips, search fields), not
     the browser's own blue — one focus look on the page */
  button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{
    outline:2px solid var(--link);outline-offset:1px}
  body{margin:0;font:var(--fs-m)/1.5 var(--font);
       background:var(--paper);color:var(--ink);-webkit-font-smoothing:antialiased}
  code,.mono{font-family:var(--mono);font-size:var(--fs-xs)}
  sup{font-size:var(--fs-xs);line-height:0}
  header{padding:13px 20px;background:var(--card);border-bottom:1px solid var(--line);
         display:flex;align-items:center;gap:13px;flex-wrap:wrap}
  .crest{width:26px;height:30px;flex:none;border-radius:3px;background:var(--gold);position:relative;
         overflow:hidden;box-shadow:inset 0 0 0 1px var(--shadow)}
  .crest::after{content:"";position:absolute;left:50%;top:52%;transform:translate(-50%,-50%);
         width:14px;height:11px;background:var(--ink);
         clip-path:polygon(50% 0,100% 38%,82% 100%,18% 100%,0 38%);opacity:.85}
  header .htxt .sub{font-size:var(--fs-xs);color:var(--ink-faint);font-weight:600;letter-spacing:.4px;text-transform:uppercase}
  header h1{font-size:var(--fs-l);margin:0;font-weight:700;letter-spacing:-.2px}
  header .stamp{margin-left:auto;color:var(--ink-faint);font-size:var(--fs-xs);text-align:right}
  /* header chip: unverified citations are the databank's own homework — grey tone (st-open) */
  .warn{border:1px solid transparent;padding:5px 12px;border-radius:8px;font-size:var(--fs-xs);font-weight:500}
  .layout{display:flex;min-height:calc(100vh - 57px)}
  /* the sidebar stays in view while the page scrolls and scrolls on its own (the drawer
     of narrow windows and the print layout reset it) */
  aside{width:290px;flex:0 0 290px;background:var(--card);border-right:1px solid var(--line);
        padding:16px;overflow:auto;position:sticky;top:0;align-self:flex-start;max-height:100vh}
  aside h2{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.7px;color:var(--ink-faint);margin:18px 0 8px}
  aside h2:first-child{margin-top:0}
  .svc{padding:8px 10px;border-radius:8px;cursor:pointer;color:var(--ink-soft);margin-bottom:3px;
       border:1.5px solid transparent;font-size:var(--fs-s);line-height:1.35;overflow-wrap:anywhere}
  .svc .svname{white-space:normal}
  .svc:hover{background:var(--field);color:var(--ink)}
  .svc.active{background:var(--hover);color:var(--ink);border-color:var(--gold-deep)}
  .svc .meta{display:block;font-size:var(--fs-xs);color:var(--ink-faint)}
  /* sidebar grouping: Departement > Dienststelle > Formulare, both levels collapsible */
  .dept{margin-bottom:4px}
  .dephd{padding:7px 9px;border-radius:8px;cursor:pointer;color:var(--ink);font-weight:700;
         font-size:var(--fs-s);display:flex;align-items:center;gap:6px;background:var(--field)}
  .dephd:hover{background:var(--line-soft)}
  .dephd .tg{color:var(--ink-faint);width:10px;display:inline-block}
  .dephd .ct{margin-left:auto;font-weight:500;font-size:var(--fs-xs);color:var(--ink-faint)}
  .office{margin:2px 0 2px 8px}
  .offhd{padding:5px 8px;border-radius:6px;color:var(--ink-soft);font-size:var(--fs-xs);
         font-weight:600;display:flex;gap:6px;align-items:baseline}
  .offtg{display:inline-flex;gap:6px;cursor:pointer}
  .offhd:hover{color:var(--ink)}
  .offhd .ct{margin-left:auto;font-size:var(--fs-xs);color:var(--ink-faint)}
  .dept.collapsed .office,.office.collapsed .svc{display:none}
  .tab{display:block;width:100%;text-align:left;padding:9px 11px;border-radius:8px;cursor:pointer;
       background:none;border:1.5px solid transparent;color:var(--ink-soft);font:inherit;font-size:var(--fs-s);
       font-weight:500;margin-bottom:3px}
  .tab:hover{background:var(--field);color:var(--ink)}
  .tab.active{background:var(--hover);color:var(--ink);border-color:var(--gold-deep);font-weight:600}
  main{flex:1;padding:22px 26px;overflow:auto;max-width:1300px}
  h3.view{font-size:var(--fs-xl);line-height:1.25;margin:0 0 6px;font-weight:700;letter-spacing:-.3px}
  /* the page title takes the focus after a change of page (screen readers read it); no ring */
  h3.view:focus,main:focus{outline:none}
  /* skip link: the first stop of the Tab key, visible only while focused */
  .skip{position:absolute;left:8px;top:8px;z-index:2000;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);
    white-space:nowrap;border:0;padding:0;font:inherit;font-size:var(--fs-s);font-weight:600;background:var(--card);color:var(--ink);cursor:pointer}
  .skip:focus{width:auto;height:auto;clip:auto;overflow:visible;padding:8px 14px;border-radius:8px;
    outline:2px solid var(--link);outline-offset:1px;box-shadow:0 2px 10px var(--shadow)}
  /* print-only lines (a URL instead of a long link list) */
  .printonly{display:none}
  .hint{color:var(--ink-soft);font-size:var(--fs-xs);margin:0 0 18px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:16px}
  .badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:var(--fs-xs);font-weight:600;
         vertical-align:middle;white-space:nowrap;border:1px solid transparent}
  /* Kennzeichen — they mark a fact (level of the law, ⛨, source DVSH/SHEP, Once-Only,
     channel, obligation), they never judge: outlined and neutral, never in one of the
     four tone colours. Every STATUS is drawn with the tone classes st-* further down. */
  .mk{background:var(--card);border-color:var(--line-strong);color:var(--ink-soft)}
  .mk.mk-open{border-style:dashed}
  table{border-collapse:collapse;width:100%;font-size:var(--fs-s)}
  th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line-soft);vertical-align:top}
  th{color:var(--ink-faint);font-weight:600;font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.4px}
  tr:hover td{background:var(--hover)}
  /* a status badge stays on one line (symbol and word never part); only the list of
     ⛨ categories is long enough to need a second line */
  td .badge.b-sens{white-space:normal}
  /* a table wider than its card scrolls inside the card, not the whole content area */
  .card:has(table){overflow-x:auto}
  .summary{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:6px}
  .gauge{font-size:var(--fs-xxl);font-weight:700}
  .pill{padding:6px 12px;border-radius:10px;background:var(--field);border:1px solid var(--line);min-width:96px}
  .pill .n{font-size:var(--fs-xl);font-weight:700;display:block}
  .pill .l{font-size:var(--fs-xs);color:var(--ink-faint);text-transform:uppercase;letter-spacing:.4px}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .colhead{font-size:var(--fs-xs);color:var(--ink-faint);text-transform:uppercase;letter-spacing:.6px;margin:0 0 8px}
  .cite{color:var(--ink-soft);font-size:var(--fs-xs);margin-top:4px}
  /* law tree (list) */
  .tree{font-size:var(--fs-s)}
  .tnode{margin-left:18px;border-left:1px dashed var(--line);padding-left:14px}
  .tline{padding:3px 0}
  .ttog{cursor:pointer;user-select:none;color:var(--ink-faint);display:inline-block;width:14px}
  .collapsed > .tnode{display:none}
  /* law tree (diagram) */
  .dg{padding:6px 0}
  .dgnode{margin:6px 0}
  .dgbox{display:inline-block;border:1px solid var(--line);border-left-width:4px;border-radius:9px;
         padding:6px 11px;background:var(--card);cursor:pointer}
  .dgbox .ttl{font-weight:600}
  .dgbox .sub{color:var(--ink-soft);font-size:var(--fs-xs)}
  .dgchildren{margin-left:26px;border-left:2px solid var(--line-soft);padding-left:18px;margin-top:2px}
  .dgnode.collapsed > .dgchildren{display:none}
  .muted{color:var(--ink-soft)} .small{font-size:var(--fs-xs)}
  /* a table cell or a block that is read, not scanned, takes the next step of the scale
     (theme.SIZE_USE: xs is for labels, chips, badges, table heads and notes) */
  td.small,.dsmob{font-size:var(--fs-s)}
  .ft td b{font-weight:600}
  .dfhdr{display:flex;align-items:center;gap:8px;margin-bottom:6px;padding-bottom:8px;border-bottom:1px solid var(--line-soft)}
  .dfrow{display:grid;grid-template-columns:1fr auto;gap:14px;padding:12px 2px;border-bottom:1px solid var(--line-soft)}
  .dfrow:last-child{border-bottom:none}
  .tp{display:inline-block;font-size:var(--fs-xs);padding:2px 8px;border-radius:6px;background:var(--field);
      color:var(--ink-soft);border:1px solid var(--line);vertical-align:middle}
  .dfname{font-weight:600;font-size:var(--fs-m);color:var(--ink)}
  .req{font-size:var(--fs-xs);color:var(--link);margin-left:6px;font-weight:600}
  .dfdef{font-size:var(--fs-m);color:var(--ink-soft);margin-top:5px;line-height:1.45}
  .dfchips{margin-top:7px} .chip{display:inline-block;font-size:var(--fs-xs);background:var(--field);
      border:1px solid var(--line);border-radius:7px;padding:2px 8px;margin:2px 3px 0 0}
  .dfprov{font-size:var(--fs-s);color:var(--ink-faint);margin-top:6px}
  .dfrg{min-width:150px;max-width:340px;text-align:right}
  /* ⛨ is a Kennzeichen (the category of the datum), not a verdict: neutral, outlined */
  .b-sens{background:var(--card);color:var(--ink-soft);border:1px solid var(--line-strong);font-size:var(--fs-xs);padding:1px 8px;
      border-radius:6px;margin-left:6px;font-weight:600}
  /* eCH chips: the tone (st-*) says the state — element ok · element open grey ·
     no standard / not in force amber; the label says it in words */
  .echb{display:inline-block;margin-left:6px;font-size:var(--fs-xs);padding:1px 7px;border-radius:6px;
    border:1px solid var(--line);text-decoration:none;vertical-align:middle;color:var(--ink);
    font-family:var(--mono)}
  .echb:hover{text-decoration:underline}
  .echn{display:inline-block;margin-left:6px;font-size:var(--fs-xs);padding:1px 7px;border-radius:6px;
    border:1px solid var(--line);vertical-align:middle;color:var(--ink)}
  .echb .sw,.echn .sw,.echdraft .sw,.fcheck .sw,.divc .sw,.begc .sw,.hubdiv .sw{width:7px;height:7px;margin-right:4px;vertical-align:0}
  .eshb{display:inline-block;margin-left:6px;font-size:var(--fs-xs);padding:1px 7px;border-radius:6px;
    background:var(--esh-bg);color:var(--esh);border:1px dashed var(--esh-line);vertical-align:middle;
    font-family:var(--mono)}
  .eshb .ent,.sfe.esh .ent{font-size:var(--fs-xs);margin-left:4px;font-family:var(--font)}
  .chip.sub{display:inline-flex;align-items:center;gap:5px;padding-right:3px}
  .sfe{font-size:var(--fs-xs);font-family:var(--mono);padding:0 5px;border-radius:4px;
    border:1px solid var(--line);color:var(--ink);text-decoration:none;white-space:nowrap}
  a.sfe:hover{text-decoration:underline}
  /* the eSH code is a Kennzeichen (a draft of the canton, never official eCH): violet, dashed */
  .sfe.esh{background:var(--esh-bg);color:var(--esh);border:1px dashed var(--esh-line)}
  .echdraft{display:inline-block;margin-left:5px;font-size:var(--fs-xs);padding:1px 6px;border-radius:6px;
    border:1px solid var(--line);vertical-align:middle;color:var(--ink)}
  .fcheck{display:inline-block;font-size:var(--fs-xs);font-weight:600;border-radius:6px;padding:1px 8px;
    margin-left:8px;vertical-align:middle;border:1px solid var(--line)}
  .flinks{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:11px 16px}
  .flabel{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.5px;color:var(--ink-faint)}
  .flink,.srcbtn{display:inline-block;padding:5px 11px;border-radius:8px;border:1px solid var(--line);
    background:var(--card);color:var(--link);font-size:var(--fs-xs);font-weight:600;text-decoration:none}
  .flink:hover,.srcbtn:hover{border-color:var(--gold-deep)}
  .qd summary{cursor:pointer;color:var(--link);font-weight:600}
  .quote{font-size:var(--fs-xs);color:var(--ink-soft);background:var(--field);border-left:3px solid var(--gold);
    padding:8px 12px;border-radius:0 8px 8px 0;margin:6px 0 0}
  /* Datenhandhabung: one rule = aspect chip + duty + verbatim law quote */
  .hrule{display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-top:1px dashed var(--line)}
  .hrule:first-child{border-top:none}
  .hasp{flex:0 0 auto;font-size:var(--fs-xs);padding:2px 8px;border-radius:999px;margin-top:1px;
    background:var(--field);border:1px solid var(--line-strong);color:var(--ink-soft);font-weight:600;white-space:nowrap}
  .hbody{font-size:var(--fs-s);line-height:1.45}
  .hbody .small{margin-top:2px}
  .hgrp{margin-top:10px}
  .hgen{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}
  .hscope{font-size:var(--fs-m);color:var(--ink-soft);margin:18px 2px 8px;text-transform:uppercase;letter-spacing:.4px}
  /* card sub-headings and the DVSH Verfahren block */
  .dvsub{font-size:var(--fs-xs);font-weight:600;color:var(--ink-soft);margin:0 0 6px}
  .dvl{font-size:var(--fs-s);line-height:1.5;margin:2px 0}
  .dvdesc{font-size:var(--fs-m);color:var(--ink-soft);margin:6px 0 10px}
  .dvgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px 20px}
  .dvmeta{margin-top:8px;font-size:var(--fs-s)}
  .dvm{margin:2px 0} .dvk{font-weight:600;color:var(--ink-soft);margin-right:4px}
  /* Leitfaden: question -> plain answer -> grounded bullets with rule chips */
  .gsec{max-width:860px}
  .gq{font-size:var(--fs-l);margin:2px 0 10px;color:var(--ink)}
  .gkurz{background:var(--field);border-left:3px solid var(--gold);border-radius:0 10px 10px 0;
    padding:10px 14px;font-size:var(--fs-m);line-height:1.55;margin-bottom:6px}
  .gklabel,.gplabel{display:block;font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.6px;
    color:var(--link);font-weight:700;margin-bottom:3px}
  .gpt{padding:9px 2px 2px;border-top:1px dashed var(--line);font-size:var(--fs-s);line-height:1.5}
  .gpt:first-of-type{border-top:none}
  .gchips{margin-top:5px}
  .gchip{display:inline-block;font-size:var(--fs-xs);padding:1px 8px;margin:2px 4px 0 0;border-radius:999px;
    background:var(--field);border:1px solid var(--gold);color:var(--ink-soft);font-weight:600;cursor:pointer}
  .gchip:hover{border-color:var(--gold-deep);background:var(--hover)}
  /* «Einordnung»: the databank's own reading, not the wording of the law — it wears the
     violet of the draft (not official), solid instead of dashed */
  .gprax{margin-top:10px;background:var(--esh-bg);border:1px solid var(--esh-line);border-radius:10px;
    padding:10px 14px;font-size:var(--fs-s);line-height:1.5;color:var(--esh)}
  .gprax .gplabel{color:var(--esh)}
  /* per-Formular Datenhandhabung profile */
  .pfstrip{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
  /* profile chips are Kennzeichen (⛨ category, special laws, retention regime) — neutral;
     only the «ohne Grundlage» chip is a status and wears its tone (st-act) */
  .pfc{font-size:var(--fs-xs);padding:3px 10px;border-radius:999px;font-weight:600;border:1px solid var(--line-strong);background:var(--card);color:var(--ink-soft)}
  .pfc.frist{border-style:solid;color:var(--ink)}
  .pfc .sw{width:8px;height:8px;margin-right:5px;vertical-align:0}
  .hstd{font-size:var(--fs-s);line-height:1.55;color:var(--ink-soft);padding:4px 0}
  .hstd.over{color:var(--ink);border-top:1px dashed var(--line);margin-top:8px;padding-top:8px}
  .hstd .gchip{cursor:default}
  .hcat{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;padding:3px 0}
  /* redesigned navigation: grouped tabs with question subtitles */
  .tabsub{display:block;font-size:var(--fs-xs);font-weight:400;color:var(--ink-faint);margin-top:1px;line-height:1.3}
  .tab.active .tabsub{color:var(--ink-soft)}
  .legsub{font-size:var(--fs-xs);font-weight:400;text-transform:none;letter-spacing:0}
  /* consistent page header: what / source / how-to-read */
  .pagehead{background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:11px 16px;margin-bottom:14px;font-size:var(--fs-s);line-height:1.55}
  .pagehead>div{margin:3px 0}
  .phl{display:inline-block;min-width:164px;font-size:var(--fs-xs);text-transform:uppercase;
    letter-spacing:.5px;color:var(--link);font-weight:700;vertical-align:top}
  /* landing page */
  .methodbox{background:var(--field);border-left:3px solid var(--gold);border-radius:0 10px 10px 0;
    padding:10px 14px;font-size:var(--fs-s);line-height:1.6}
  .methodbox>div{margin:4px 0}
  .hometiles{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px}
  .hometile{flex:1 1 130px;background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:10px 8px;cursor:pointer;text-align:center}
  .hometile:hover{border-color:var(--gold-deep)}
  .htn{display:block;font-size:var(--fs-xl);font-weight:700;color:var(--link)}
  .htl{display:block;font-size:var(--fs-xs);color:var(--ink-soft);margin-top:2px}
  /* form-page hub head */
  .hubhead{padding:10px 16px}
  .hubrow{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:var(--fs-xs)}
  .hubchan{font-weight:600;color:var(--ink-soft)}
  /* signature and digitalisation blockers are facts about the Formular, not a tone */
  .hubsig{color:var(--ink-soft);font-weight:600}
  .hubmeta{color:var(--ink-faint)}
  .hubout{margin-top:7px;font-size:var(--fs-s)}
  .hubburden{margin-top:5px;font-size:var(--fs-s);color:var(--ink-soft)}
  /* Beilagen */
  .beirow{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;padding:4px 0;
    border-top:1px dashed var(--line);font-size:var(--fs-s)}
  .beirow:first-of-type{border-top:none}
  /* obligation and holder of a Beilage are Kennzeichen: neutral (zwingend solid, bedingt dashed) */
  .beiob{font-size:var(--fs-xs);padding:1px 7px;border-radius:999px;font-weight:700;border:1px solid var(--line);color:var(--ink-soft);background:var(--card)}
  .beiob.zwingend{border-color:var(--line-dark);color:var(--ink)}
  .beiob.bedingt{border-style:dashed;border-color:var(--line-dark)}
  .beih{margin-left:auto;font-size:var(--fs-xs);color:var(--ink-faint)}
  .beih.f{color:var(--ink-soft);font-weight:600}
  .simlink{color:var(--link);cursor:pointer;text-decoration:none;font-weight:600}
  .simlink:hover{text-decoration:underline}
  .lawforms summary{cursor:pointer;font-size:var(--fs-xs);color:var(--link);font-weight:600;margin-top:6px}
  .flash{outline:2px solid var(--link);outline-offset:2px}
  .katrow[aria-expanded]{cursor:pointer}
  .katforms td{background:var(--field);font-size:var(--fs-xs);line-height:1.7}
  /* Service-Dossier */
  .svclaws{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 12px;
    background:var(--card);border:1px solid var(--line);border-radius:12px;padding:9px 14px}
  .lawchip{font-size:var(--fs-xs);padding:2px 9px;border-radius:999px;border:1px solid var(--gold);
    background:var(--hover);color:var(--ink);text-decoration:none;font-weight:600;display:inline-block}
  a.lawchip:hover{border-color:var(--gold-deep)}
  .lawchip.nolink{border-style:dashed;color:var(--ink-soft)}
  .lawchip .lawabbr{font-weight:500;color:var(--ink-soft)}
  .hsl{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.5px;color:var(--link);
    font-weight:700;margin-right:6px}
  .verf summary{cursor:pointer;padding:2px 0}
  .verf>summary b{font-size:var(--fs-m)}
  .hstrip{display:flex;flex-wrap:wrap;gap:14px;border-top:1px dashed var(--line);
    margin-top:7px;padding-top:7px;font-size:var(--fs-xs);align-items:baseline}
  .hs{display:inline-flex;align-items:baseline;gap:4px;flex-wrap:wrap}
  .formsec{border-left:3px solid var(--gold);padding-left:12px;margin:0 0 22px}
  /* per-field Handhabung line: standard datatype, retention, stricter ⛨ rules */
  .dfhb{font-size:var(--fs-xs);color:var(--ink-soft);margin:2px 0 1px;display:flex;gap:5px;
    align-items:baseline;flex-wrap:wrap}
  .edt{font-family:var(--mono);font-size:var(--fs-xs);background:var(--field);
    border:1px solid var(--line);border-radius:6px;padding:0 6px}
  /* Handlungsbedarf board + global search */
  .gsearch{margin-left:auto;min-width:240px;max-width:420px;flex:1;border:1px solid var(--line);border-radius:8px;
    padding:6px 10px;font:inherit;font-size:var(--fs-s);background:var(--field)}
  .todocats{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 12px;align-items:center}
  .tcat{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:999px;
    padding:3px 10px;font-size:var(--fs-xs);cursor:pointer;background:var(--card)}
  .tcat.on{border-color:currentColor;box-shadow:0 0 0 1px currentColor inset}
  .tcat b{font-variant-numeric:tabular-nums}
  .todoexpl summary{cursor:pointer}
  .todoexpl td{vertical-align:top;font-size:var(--fs-s)}
  @media (max-width:1060px){.todoexpl td.nowrap{white-space:normal}}
  .dsthead{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;margin-bottom:4px}
  .dsthead h4{margin:0;font-size:var(--fs-l)}
  .dstkontakt{font-size:var(--fs-xs);color:var(--ink-soft);margin-bottom:4px}
  /* a contact, the same on every page (kontaktHtml): «Kontakt (laut DVSH): Adresse · Tel. … ·
     E-Mail …»; telephone and e-mail are links in the link style of the page (a.inl) */
  .klbl{font-weight:600}
  .kontakt .kp{white-space:nowrap}
  .hubk{color:var(--ink-soft)}
  .tchip{cursor:pointer;margin:2px 4px 2px 0;display:inline-block}
  .tchip b{font-variant-numeric:tabular-nums}
  .sres .srow{display:flex;gap:10px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--line)}
  .sres .srow:last-of-type{border-bottom:0}
  .stype{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.04em;color:var(--ink-soft);min-width:106px}
  a.slink{color:inherit;text-decoration:none;cursor:pointer;display:block}
  .slink:hover{text-decoration:underline}
  mark.hl{background:var(--gold-tint);color:inherit;padding:0 1px;border-radius:2px}
  /* Lebenslagen */
  .llgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px;margin:4px 0 10px}
  .lltile{text-align:left;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;padding:9px 11px;
    cursor:pointer;display:flex;flex-direction:column;gap:3px;font:inherit}
  .lltile:hover{border-color:var(--gold)}
  .lln{font-weight:700;font-size:var(--fs-m)}
  .lls{font-size:var(--fs-xs);color:var(--ink-soft)}
  /* an overlap across the offer is a count, not a status: neutral */
  .llrep{color:var(--ink);font-weight:600}
  .llsum{font-size:var(--fs-m);line-height:1.6}
  .llnum{display:inline-block;font-size:var(--fs-m);color:var(--ink-soft)}
  .rstat .sw{width:8px;height:8px;margin:0 3px 0 6px;vertical-align:0}
  .rstat .sw:first-child{margin-left:0}
  .crumbs{margin:0 0 6px;font-size:var(--fs-s)}
  /* Begriffe */
  .bgcard{padding:10px 14px}
  .bghead{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
  .bgvor{font-weight:700;font-size:var(--fs-l)}
  .bgrow{display:flex;flex-wrap:wrap;gap:5px;align-items:baseline;margin-top:6px}
  .bglab{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.04em;min-width:170px;font-weight:700;color:var(--ink)}
  .bglab .sw{width:8px;height:8px;margin-right:5px;vertical-align:0}
  .bgl{font-size:var(--fs-xs);border:1px solid var(--line);border-radius:6px;padding:1px 7px;background:var(--card)}
  .begc{font-size:var(--fs-xs);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:0 6px;white-space:nowrap}
  .svthemen{display:flex;flex-wrap:wrap;gap:5px;align-items:baseline;margin-top:6px;font-size:var(--fs-xs)}
  .svthemen a{cursor:pointer}
  /* Standard divergence markers */
  /* ⇄ divergence marker: red where the Dienststelle aligns, amber where the canton decides */
  .divc{font-size:var(--fs-xs);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:0 6px;white-space:nowrap}
  .divc.mini{padding:0 3px;margin-left:3px}
  .hubdiv{font-size:var(--fs-xs);color:var(--ink);border:1px solid var(--line);border-radius:999px;padding:1px 9px}
  a.hubdiv{text-decoration:none} a.hubdiv:hover{text-decoration:underline}
  .dvval{display:inline-block;white-space:normal;border:1px solid var(--line);border-radius:6px;padding:1px 6px;color:var(--ink)}
  table.dvt{table-layout:fixed}
  table.dvt td{vertical-align:top;overflow-wrap:anywhere}
  table.dvt th{overflow-wrap:anywhere;hyphens:auto}
  table.dvt th:nth-child(1),table.dvt td:nth-child(1){width:32%}
  table.dvt th:nth-child(2),table.dvt td:nth-child(2){width:22%}
  table.dvt th:nth-child(3),table.dvt td:nth-child(3){width:28%}
  table.dvt th:nth-child(4),table.dvt td:nth-child(4){width:18%}
  tr.dvact td{border-bottom:1px solid var(--line);color:var(--ink-soft);padding-top:0}
  /* Rechtsmittel line under the Verfahrens-Ergebnis */
  .hubout.rm{display:flex;flex-wrap:wrap;gap:6px 8px;align-items:baseline}
  .rmlbl{font-weight:600}
  .hubout.rm details.qd summary{font-size:var(--fs-xs)}
  .rmcand{margin:2px 0 8px 14px}
  .rmcand summary{font-size:var(--fs-xs);color:var(--ink-soft);cursor:pointer}
  .rmc{margin:6px 0 0 8px}
  .rmc blockquote.quote{margin:2px 0 0}
  /* Datenfluss diagram + Bürgersicht */
  /* the labels are sized in units of the drawing (980 wide): it never shrinks below the
     width at which they are 12 px; a narrow window scrolls the card sideways instead */
  .flowsvg{width:100%;min-width:906px;height:auto;display:block;font-size:var(--fs-s)}
  .card:has(>.flowsvg){overflow-x:auto;padding-left:12px;padding-right:12px}
  .flowsvg .flowhd{font-size:var(--fs-s);font-weight:700;fill:var(--ink-soft);text-transform:uppercase;letter-spacing:.04em}
  .flowsvg .fn{cursor:pointer;fill:var(--ink)}
  .flowsvg .fn:hover{text-decoration:underline}
  /* the mode of a disclosure is a Kennzeichen: solid = systematisch, dashed = auf Anfrage,
     both neutral ink — never a tone */
  .flowsvg .fe{stroke:var(--ink-soft);stroke-opacity:.5;transition:stroke-opacity .15s;cursor:pointer}
  @media (prefers-reduced-motion:reduce){.flowsvg .fe{transition:none}}
  .flowsvg .fe.auf_anfrage{stroke-dasharray:5 4}
  .flowsvg .fe:hover{stroke-opacity:1}
  .flowsvg .fe.dim{stroke-opacity:.08}
  .flowleg{display:flex;gap:16px;align-items:center;font-size:var(--fs-xs);margin-bottom:6px}
  .flowleg .fl{display:inline-block;width:26px;height:0;border-top:2px solid var(--ink-soft);vertical-align:middle;margin-right:4px}
  .flowleg .fl.anf{border-top:2px dashed var(--ink-soft)}
  .lkrow{display:flex;align-items:center;gap:10px;margin:3px 0}
  .lky{font-variant-numeric:tabular-nums;min-width:40px;font-size:var(--fs-s)}
  /* once-only: the Einwohnerregister already holds this datum */
  .regc{font-size:var(--fs-xs);color:var(--ink-soft);background:var(--card);border:1px solid var(--line-strong);
    border-radius:6px;padding:0 6px;white-space:nowrap;font-weight:600}
  .chip.sub .regc{margin-left:4px;padding:0 4px}
  /* navigation redesign: browse modes, breadcrumb, Formular quick-jump */
  .navmodes{display:flex;gap:6px;margin:0 0 8px}
  .navmodes button{flex:1;padding:5px 8px;border-radius:8px;border:1px solid var(--line);
    background:var(--card);color:var(--ink-soft);font-size:var(--fs-xs);cursor:pointer;font-weight:600}
  .navmodes button.active{border-color:var(--gold-deep);color:var(--ink);background:var(--hover)}
  .fnav .meta{display:block;font-size:var(--fs-xs);color:var(--ink-faint)}
  .bcrumb{display:flex;gap:8px;align-items:center;font-size:var(--fs-xs);color:var(--ink-faint);margin:0 0 4px}
  .bcrumb a{color:var(--link);cursor:pointer;font-weight:600}
  .bcrumb a:hover{text-decoration:underline}
  .fjump{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 10px}
  .fjc{font-size:var(--fs-xs);padding:3px 10px;border-radius:999px;border:1px solid var(--gold);
    background:var(--hover);cursor:pointer;color:var(--ink)}
  .fjc:hover{border-color:var(--gold-deep)}
  /* Verzeichnis + Datenkatalog */
  .regstats{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
  .rstat{font-size:var(--fs-xs);padding:6px 12px;border-radius:10px;background:var(--card);border:1px solid var(--line)}
  .rstat b{color:var(--link)}
  /* recipients, channel and source are Kennzeichen: neutral, outlined */
  .empchip{display:inline-block;font-size:var(--fs-xs);padding:2px 9px;margin:2px 4px 0 0;border-radius:999px;
    background:var(--card);border:1px solid var(--line-strong);color:var(--ink);font-weight:600}
  .zweckline{font-size:var(--fs-s);color:var(--ink-soft);margin:-4px 0 10px;font-style:italic}
  .nodv{color:var(--ink-faint);margin-right:4px}
  .esvc{display:inline-block;font-size:var(--fs-xs);background:var(--card);color:var(--ink-soft);border:1px solid var(--line-strong);
    border-radius:6px;padding:0 6px;margin-left:6px;font-weight:600}
  .b-nodv{background:var(--card);color:var(--ink-soft);border:1px dashed var(--line-dark);font-size:var(--fs-xs);padding:2px 8px;
    border-radius:6px;white-space:nowrap;font-weight:600}
  .b-dvsh{background:var(--card);color:var(--ink-soft);border:1px solid var(--line-strong);font-size:var(--fs-xs);padding:2px 8px;
    border-radius:6px;font-weight:700}
  .seg{display:inline-flex;border:1.5px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:14px}
  .seg button{border:none;background:var(--card);color:var(--ink-soft);font:inherit;font-size:var(--fs-s);
    font-weight:600;padding:6px 14px;cursor:pointer}
  .seg button.active{background:var(--field);color:var(--ink)}
  .pbar{height:8px;border-radius:5px;background:var(--field);border:1px solid var(--line);
    overflow:hidden;flex:1;min-width:140px;max-width:280px}
  /* the filled part of a progress bar is what is settled (tone ok); a bar that only
     counts (Löschkalender) is neutral (.nt) */
  .pbar > i{display:block;height:100%;background:var(--ton-ok)}
  .pbar.nt > i{background:var(--ink-faint)}
  .nores{color:var(--ink-faint);padding:30px 0;text-align:center}
  .legend{font-size:var(--fs-s);color:var(--ink-soft);line-height:1.45}
  .legblk{margin:0 0 12px}
  .leghd{font-size:var(--fs-xs);font-weight:700;color:var(--ink);margin:0 0 5px}
  .legend .tleg{font-size:var(--fs-s);gap:5px}
  .legend .tleg li{align-items:flex-start}
  .legend .tleg li .sw{transform:translateY(3px)}
  .legend .tleg.mkl li{display:block}
  .legend .tleg.mkl li>.badge,.legend .tleg.mkl li>.regc,.legend .tleg.mkl li>.eshb,.legend .tleg.mkl li>.edt,.legend .tleg.mkl li>.llnum{margin:0 5px 0 0;vertical-align:1px}
  .legend .tleg.mkl li>.mkline{margin:0 4px 3px 0;vertical-align:middle}
  .legex{display:block;color:var(--ink-faint);font-size:var(--fs-xs);line-height:1.4}
  .mkline{display:inline-block;width:22px;height:0;border-top:2px solid var(--ink-soft);vertical-align:middle}
  .mkline.dash{border-top-style:dashed}
  input#svcfilter{width:100%;padding:8px 10px;margin-bottom:8px;background:var(--card);
    border:1.5px solid var(--line);border-radius:8px;color:var(--ink);font:inherit;font-size:var(--fs-s)}
  input#svcfilter:focus-visible{border-color:var(--link)}
  .tab.ext{text-decoration:none;color:var(--ink-soft);display:block}
  .datenstand{font-size:var(--fs-xs);color:var(--ink-soft);margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)}
  /* page head: one visible sentence, the rest folded away */
  .phkurz{margin:0;font-size:var(--fs-m);line-height:1.5;color:var(--ink)}
  details.phmore{margin-top:6px}
  details.phmore>summary{cursor:pointer;font-size:var(--fs-xs);font-weight:600;color:var(--link);width:max-content}
  details.phmore[open]>summary{margin-bottom:4px}
  details.phmore>div{margin:3px 0}
  /* tones — the colour says who acts next: segments, swatches (chips follow in the
     status-language pass); text never wears the tone colour, it sits beside it */
  .t-ok{background:var(--ton-ok)} .t-ok2{background:var(--ton-ok2)} .t-act{background:var(--ton-act)}
  .t-dec{background:var(--ton-dec)} .t-open{background:var(--ton-open)} .t-rest{background:var(--line)}
  .tbar{display:flex;gap:2px;height:10px;border-radius:4px;overflow:hidden;margin:2px 0 0}
  .tbar>i{display:block;flex:1 1 0;min-width:3px}
  .sw{display:inline-block;width:10px;height:10px;border-radius:3px;flex:none;vertical-align:-1px;margin-right:5px}
  .tleg{list-style:none;margin:0;padding:0;font-size:var(--fs-xs);color:var(--ink-soft);display:flex;flex-direction:column;gap:3px}
  .tleg li{display:flex;gap:6px;align-items:baseline}
  .tleg li .sw{margin-right:0;transform:translateY(1px)}
  .tleg li>b{color:var(--ink);font-variant-numeric:tabular-nums;min-width:48px;text-align:right;font-weight:600}
  /* an entry that counts nothing here steps back in soft ink — never by transparency,
     which would take the text below the contrast minimum */
  .tleg li.zero,.tleg li.zero b{color:var(--ink-soft);font-weight:400}
  .tleg li.zero .sw{opacity:.45}
  .tleg .tw{color:var(--ink-faint)}
  .tleg a.inl{margin-left:2px}
  .tonlist li{font-size:var(--fs-s);line-height:1.5}
  /* home: data standard first */
  .lead{font-size:var(--fs-m);line-height:1.6;margin:0 0 12px;max-width:880px;color:var(--ink)}
  .tonkey{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;font-size:var(--fs-s);color:var(--ink-soft);
    margin:0 0 18px;padding:7px 12px;background:var(--card);border:1px solid var(--line);border-radius:10px;width:max-content;max-width:100%}
  .tonkey .tk{display:inline-flex;align-items:center;white-space:nowrap}
  .tonkey .sep{color:var(--ink-faint)}
  .hsec{margin:0 0 22px}
  .hsec>h4{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.6px;color:var(--ink-soft);margin:0 0 4px}
  .hsec.core>h4{font-size:var(--fs-l);text-transform:none;letter-spacing:-.1px;color:var(--ink)}
  .hsec.core{border-left:3px solid var(--gold);padding-left:14px}
  .hsub{font-size:var(--fs-s);color:var(--ink-soft);margin:0 0 10px;max-width:880px;line-height:1.5}
  .kzgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px}
  .kz{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:flex;
    flex-direction:column;gap:8px;min-width:0}
  .kzl{font-size:var(--fs-s);font-weight:700;color:var(--ink)}
  .kzv{font-size:var(--fs-xxl);font-weight:700;line-height:1.05;letter-spacing:-.5px;color:var(--ink)}
  .kzv .kzvon{font-size:var(--fs-l);font-weight:600;color:var(--ink-soft);letter-spacing:0}
  .kzsub{font-size:var(--fs-s);color:var(--ink-soft);line-height:1.45;margin-top:-4px}
  .kzziel{font-size:var(--fs-xs);color:var(--ink);border-left:2px solid var(--gold);padding:1px 0 1px 8px}
  .kznote{font-size:var(--fs-xs);color:var(--ink-faint);line-height:1.45}
  .kznote.dsnote{margin-top:6px}
  .kztrend{font-size:var(--fs-xs);color:var(--ink-soft);line-height:1.45}
  .kztrend>b{color:var(--ink);font-weight:600}
  .kztrend .bem{display:block;margin-top:3px;padding-left:8px;border-left:2px solid var(--line)}
  .kzfoot{margin-top:auto;padding-top:2px}
  .kzlink{font-size:var(--fs-xs);font-weight:600;color:var(--link);text-decoration:none}
  /* small links get a 24 px target without moving the layout */
  .kzlink,.offlink,a.inl{display:inline-block;padding:4px 2px;margin:-4px 0}
  .kzlink:hover,a.inl:hover{text-decoration:underline}
  a.inl{color:var(--link);font-weight:600;text-decoration:none;white-space:nowrap}
  .doors{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
  .door{display:flex;flex-direction:column;gap:4px;background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:14px 16px;text-decoration:none;color:var(--ink)}
  .door:hover{border-color:var(--gold-deep);background:var(--hover)}
  .door .dk{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.6px;color:var(--link);font-weight:700}
  .door .dq{font-size:var(--fs-l);font-weight:700;line-height:1.3}
  .door .dn{font-size:var(--fs-xs);color:var(--ink-soft)}
  /* Gestaltung der Formulare — the page #gestaltung, the panel of a Formular, a section of the
     briefing. What the Formulare show is drawn neutral (ink and grey); only a verdict wears a tone */
  .glinkline{margin:12px 0 0;font-size:var(--fs-s);color:var(--ink-soft)}
  .gdoors .door .dq{font-size:var(--fs-m);font-weight:600;line-height:1.4}
  .gdoors .door .dz{padding-top:6px;font-size:var(--fs-s);color:var(--ink-soft);line-height:1.4}
  .gdoors .door .dz b{display:block;font-size:var(--fs-xl);color:var(--ink);line-height:1.15}
  .gstsec{margin:24px 0 0}
  .gstsec>h4{margin:0 0 6px;padding-bottom:4px;border-bottom:2px solid var(--gold);font-size:var(--fs-l)}
  .gfrage{margin:0 0 6px;max-width:880px;font-size:var(--fs-m);line-height:1.5}
  .gvorb{margin:0 0 12px;max-width:880px;padding:1px 0 1px 9px;border-left:2px solid var(--line-strong);
    font-size:var(--fs-s);color:var(--ink-soft);line-height:1.45}
  .gm{padding:14px 18px 12px}
  /* the heading and the badge of its kind flow as text («Schrift Vergleich mit der Praxis»), so that
     a reader that copies or reads them aloud hears a space between them */
  .gmhd{line-height:1.6}
  .gmhd h5{display:inline;margin:0 6px 0 0;font-size:var(--fs-l);font-weight:700}
  .gmhd .badge{vertical-align:2px}
  .gzue{margin:0 0 10px;font-size:var(--fs-s);line-height:1.5}
  .gzue .hsl{margin-right:2px}
  [data-jump]:focus{outline:none}
  .gmq{margin:2px 0 10px;font-size:var(--fs-s);color:var(--ink-soft);line-height:1.45}
  .gpr{margin:0 0 10px;font-size:var(--fs-s);line-height:1.6}
  .gcols{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:12px 28px;align-items:start}
  .gcap{margin:0 0 5px;font-size:var(--fs-xs);color:var(--ink-soft);line-height:1.4}
  .gcap b{color:var(--ink)}
  ul.gdist{list-style:none;margin:0;padding:0;font-size:var(--fs-s)}
  ul.gdist>li{display:grid;grid-template-columns:minmax(0,15em) minmax(40px,1fr) 3.4em;gap:10px;align-items:center;
    padding:1px 0;line-height:1.35}
  ul.gdist>li[hidden]{display:none}
  .gdl{overflow-wrap:anywhere}
  .gdb{height:8px;border-radius:3px;background:var(--line-soft);overflow:hidden}
  .gdb>i{display:block;height:100%;min-width:2px;background:var(--ink-faint)}
  .gdn{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
  ul.gdist>li.gp .gdl{font-weight:700}
  ul.gdist>li.gp .gdb>i{background:var(--ink-soft)}
  .gpm{margin-left:2px;padding:0 5px;border:1px solid var(--line-strong);border-radius:6px;font-size:var(--fs-xs);
    font-weight:600;color:var(--ink-soft);white-space:nowrap}
  .gdbx{display:inline-block;width:22px;height:8px;border-radius:3px;background:var(--ink-faint);vertical-align:middle}
  .gurt{display:flex;flex-wrap:wrap;gap:5px}
  .gfr .tchip{margin:0 2px 0 0}
  .gurt .tchip{margin:0}
  .gm .tchip:not([data-tip]),.gpanel .tchip:not([data-tip]){cursor:default}
  .gmorebtn{display:inline-block;margin-top:3px;padding:4px 0;border:0;background:none;cursor:pointer;font:inherit;
    font-size:var(--fs-xs);font-weight:600;color:var(--link)}
  .gmorebtn:hover{text-decoration:underline}
  .gzus{margin-top:10px;padding-top:8px;border-top:1px dashed var(--line);font-size:var(--fs-s);color:var(--ink-soft);line-height:1.5}
  .gzus b{color:var(--ink);font-weight:600}
  details.gfl,details.gwie{margin-top:8px}
  details.gfl>summary,details.gwie>summary{cursor:pointer;font-size:var(--fs-xs);font-weight:600;color:var(--link)}
  ul.gfll{margin:6px 0 0;padding-left:18px;font-size:var(--fs-s);line-height:1.5;columns:2 24em;column-gap:28px;overflow-wrap:anywhere}
  ul.gfll>li{break-inside:avoid;padding:1px 0}
  .gvw{margin:10px 0 0;font-size:var(--fs-s)}
  details.gwie>p{margin:6px 0 0;max-width:880px;font-size:var(--fs-s);color:var(--ink-soft);line-height:1.5}
  .gmlink{margin-top:8px;font-size:var(--fs-xs)}
  ul.ggrenz{margin:8px 0 0;padding-left:20px;max-width:900px;font-size:var(--fs-s);color:var(--ink-soft);line-height:1.5}
  ul.ggrenz>li{margin:0 0 6px}
  table.gdst{min-width:880px}
  table.gdst td{vertical-align:baseline}
  .gpanel{padding:10px 16px}
  details.gpanel>summary{cursor:pointer;font-size:var(--fs-s);line-height:1.5}
  .gpanel .dvsub{display:inline;margin:0 4px 0 0;color:var(--ink)}
  .gsumm{color:var(--ink-soft)}
  .gsumm .sw{vertical-align:-1px}
  .gfgrp{margin:12px 0 2px;font-size:var(--fs-xs);font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint)}
  .gfr{display:grid;grid-template-columns:minmax(0,190px) minmax(0,1fr);gap:2px 14px;padding:6px 0;
    border-top:1px dashed var(--line);font-size:var(--fs-s);line-height:1.5}
  .gfgrp+.gfr{border-top:none}
  .gfr.gfr1{grid-template-columns:minmax(0,1fr)}
  ul.gfd{margin:3px 0 0;padding-left:18px;color:var(--ink-soft)}
  .gfoot{margin-top:10px;font-size:var(--fs-xs);color:var(--ink-soft)}
  @media (max-width:1100px){.gcols{grid-template-columns:minmax(0,1fr)} ul.gdist{max-width:720px}}
  /* Datenmodell & Once-Only — the pages #datenmodell and #onceonly and the panels «Parteien» and
     «Was Register schon wissen» of a Formular, built on the blocks of the Gestaltung page (cards,
     sections, folded lists). Numbers and lists are neutral; a tone only on a decision or a finding */
  h5.dmh{margin:18px 0 6px;font-size:var(--fs-m);font-weight:700}
  ul.dmgr{font-size:var(--fs-s);gap:4px}
  ul.dmgr li>b{min-width:56px}
  ul.dmgr.dmcols{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:3px 18px}
  ol.dmwie{margin:0;padding-left:22px;font-size:var(--fs-s);line-height:1.55;max-width:920px}
  ol.dmwie>li{padding:7px 0 7px 2px;border-top:1px dashed var(--line)}
  ol.dmwie>li:first-child{border-top:none;padding-top:0}
  details.dmk{padding:10px 16px;margin-bottom:8px}
  details.dmk>summary{cursor:pointer;line-height:1.5}
  .dmkn{font-weight:700;font-size:var(--fs-m);margin-right:10px}
  .dmks{font-size:var(--fs-s);color:var(--ink-soft)}
  .dmks b{color:var(--ink);font-weight:600}
  ul.dmlist{margin:4px 0 8px;padding-left:18px;line-height:1.5}
  table.dmz td,table.dmgs td,table.dmwl td,table.dmwa td,table.dmrol td,table.dmzg td{vertical-align:top}
  table.dmz td .badge{white-space:normal}
  code.kennc{font-family:var(--mono);font-size:var(--fs-xs);background:var(--field);border:1px solid var(--line);border-radius:5px;
    padding:0 5px;overflow-wrap:anywhere;user-select:all}
  code.kennmini{margin-left:6px;color:var(--ink-soft);font-weight:400}
  .kenn{display:inline-flex;flex-wrap:wrap;gap:4px 8px;align-items:baseline}
  .kennl{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.5px;color:var(--ink-faint);font-weight:700}
  .copybtn{font:inherit;font-size:var(--fs-xs);font-weight:600;color:var(--link);background:var(--card);border:1px solid var(--line);
    border-radius:6px;padding:2px 9px;cursor:pointer}
  .copybtn:hover{border-color:var(--link)}
  .lawimp{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;margin-top:6px;font-size:var(--fs-xs)}
  .dfrg .lawimp{justify-content:flex-end}
  .nomono{font-family:var(--font)}
  tr.sel>td{background:var(--hover)}
  .dwdet{border-left:3px solid var(--gold-deep)}
  dl.dmfacts{margin:6px 0 8px;font-size:var(--fs-s);line-height:1.5}
  dl.dmfacts>div{display:grid;grid-template-columns:150px minmax(0,1fr);gap:2px 12px;padding:3px 0;border-top:1px dashed var(--line)}
  dl.dmfacts>div:first-child{border-top:none}
  dl.dmfacts dt{font-weight:600;color:var(--ink-soft)}
  dl.dmfacts dd{margin:0;overflow-wrap:anywhere}
  .dmzr{display:flex;flex-direction:column;gap:3px;font-size:var(--fs-s);line-height:1.45;padding:7px 0;border-top:1px solid var(--line-soft)}
  .dmvb{margin:8px 0;padding:8px 12px;background:var(--field);border-radius:8px;font-size:var(--fs-s);line-height:1.5}
  .dmvb .gcap{margin-top:6px}
  .oovorb{margin-bottom:16px}
  caption.gcap{text-align:left;caption-side:top;padding:0 0 6px}
  .ppanel .quote{margin:4px 0}
  .dml{display:none}
  /* a group of the register catalogue: a row header (th scope=rowgroup) that reads like the group's name */
  table.dmreg tr.gdep th{color:var(--ink);font-size:var(--fs-s);font-weight:700;text-transform:none;letter-spacing:0;padding-top:12px}
  @media (max-width:700px){dl.dmfacts>div{grid-template-columns:minmax(0,1fr)}}
  /* on a phone the tables of the two pages stack: one block per row, each number with its label
     (.dml), a long cell (.dmw) across the block; the column heads stay for a screen reader */
  @media screen and (max-width:700px){
    table.dmstack{min-width:0}
    table.dmstack thead{position:absolute;left:0;top:0;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
    table.dmstack,table.dmstack tbody{display:block}
    table.dmstack tr{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:4px 14px;padding:9px 0;border-bottom:1px solid var(--line)}
    table.dmstack td{display:block;border:0;padding:0;text-align:left}
    table.dmstack td:first-child,table.dmstack td.dmw,table.dmstack tr.gdep td,table.dmstack tr.gdep th{grid-column:1/-1}
    table.dmstack tr.gdep th{display:block;border:0;padding:4px 0 0}
    table.dmstack .dml{display:inline;margin-right:6px;font-size:var(--fs-xs);font-weight:600;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.4px}
    table.dmstack td.nowrap{white-space:normal}
    table.dmstack caption{display:block;width:auto}
    table.dmstack td.dmw .badge{white-space:normal}
  }
  /* the table per Dienststelle: up to 1340 px «Häufigste Abweichungen und Lücken» stands under the name (.wd/.nw);
     up to 1100 px (a narrow content column beside the sidebar, or a phone) each Dienststelle is
     a block of labelled numbers */
  table.gdst{min-width:600px}
  @media screen and (min-width:1341px){table.gdst{min-width:880px} table.gdst th.wd{width:24%}}
  .gtop{white-space:nowrap}
  table.gdst td.wd .gtop{white-space:normal}
  .gml{display:none}
  table.gdst tr.gdep td{padding-top:12px;font-size:var(--fs-s)}
  /* up to 1100 px each Dienststelle is a block; each number stands on one line with its label
     («ABWEICHUNGEN 3»), so the numbers of a block line up. The column headers stay for a screen
     reader (hidden from view only); the labels in the cells are for the eye only */
  @media screen and (max-width:1100px){
    table.gdst{min-width:0}
    table.gdst thead{position:absolute;left:0;top:0;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
    table.gdst,table.gdst tbody{display:block}
    table.gdst tr{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:4px 14px;padding:8px 0;border-bottom:1px solid var(--line)}
    table.gdst tr.dgrp{background:var(--field);padding:8px 6px}
    table.gdst td{display:block;border:0;padding:0;text-align:left}
    table.gdst td:first-child{grid-column:1/-1}
    table.gdst td:empty,table.gdst td.wd{display:none}
    table.gdst tr.dgrp td,table.gdst tr.gdep td{border:0;background:none}
    table.gdst tr.gdep{padding:12px 0 2px}
    table.gdst .gml{display:inline;margin-right:6px;font-size:var(--fs-xs);font-weight:600;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.4px}
    .gtop{white-space:normal}
  }
  @media (max-width:600px){
    ul.gdist>li{grid-template-columns:minmax(0,9.5em) minmax(32px,1fr) 3em;gap:8px}
    .gfr{grid-template-columns:minmax(0,1fr)}
    ul.gfll{columns:1}
    .gm{padding:12px 14px}
  }
  /* Verlauf: compact trend lines */
  /* a sparkline is 320 units wide and its labels are sized in those units: the card is
     never narrower than the drawing, so the labels stay at 12 px or more */
  .vlgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,356px),1fr));gap:12px}
  .spark{width:100%;min-width:320px;max-width:360px;height:auto;display:block;overflow:visible}
  .spark .sg{stroke:var(--line);stroke-width:1}
  .spark .sl{font-size:var(--fs-xs);fill:var(--ink-faint)}
  .spark .sp{fill:none;stroke:var(--ink-soft);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
  .spark .hit{fill:transparent}
  .spark .pt{fill:var(--ink-soft);stroke:var(--card);stroke-width:2}
  .spark .pt.cur{fill:var(--ink)}
  .spark .pt.git{fill:var(--card);stroke:var(--ink-soft);stroke-width:2}
  .spark .nn{font-size:var(--fs-xs);font-weight:700;fill:var(--ink)}
  .spark g[data-tip]:focus{outline:none}
  .spark g[data-tip]:focus .pt,.spark g[aria-expanded="true"] .pt{stroke:var(--link);stroke-width:3}
  .vlrow{font-size:var(--fs-xs);color:var(--ink-soft);font-variant-numeric:tabular-nums;line-height:1.5}
  .vlrow b{color:var(--ink);font-weight:600}
  .vlnotes{font-size:var(--fs-xs);color:var(--ink-soft);margin:10px 0 0;padding-left:20px;line-height:1.5}
  .vlnote{font-size:var(--fs-xs);color:var(--ink-faint);margin-top:6px}
  /* Methode & Quellen */
  .stufen{margin:0;padding-left:0;list-style:none;font-size:var(--fs-s);line-height:1.5}
  .stufen li{padding:5px 0;border-top:1px dashed var(--line)}
  .stufen li:first-child{border-top:none}
  .stcats{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}
  .stcats .tchip.zero{color:var(--ink-soft);border-style:dashed}
  .stcats .tchip.zero b{font-weight:400}
  .stcats .tchip.zero .sw{opacity:.45}
  /* a wide table scrolls inside this block, never the whole content area: either the card
     itself (.card.tscroll) or a block inside a card, which then has no padding of its own */
  .tscroll{overflow-x:auto;padding:6px 10px}
  .card .tscroll,details .tscroll{padding:0}
  /* reference tables that must fit a laptop window (class «fit»: Datenkatalog, Verzeichnis,
     Datenfluss, Bürgersicht, the Rechtsgrundlage overview): long words hyphenate, an element
     code breaks after its standard (codeBrk), other identifiers anywhere (.brk), marks wrap;
     up to 1340 px a column of the wide layout (.wd) gives way to a line under the first
     cell (.nw). What still does not fit scrolls inside .tscroll */
  table.fit td:first-child,table.fit td.hy{hyphens:auto}
  table.fit td.mono,table.fit td .mono{hyphens:manual}
  .brk,table.fit td .edt{overflow-wrap:anywhere}
  table.fit td .eshb{white-space:normal;overflow-wrap:anywhere}
  table.fit td .stdcell{white-space:normal;flex-wrap:wrap;gap:2px 0}
  .nw{display:none}
  @media screen and (max-width:1340px){
    .wd{display:none}
    div.nw{display:block} span.nw{display:inline}
  }
  /* Glossar (Methode & Quellen): the term, then one or two plain sentences */
  dl.gloss{margin:0;font-size:var(--fs-s);line-height:1.5}
  dl.gloss>div{display:grid;grid-template-columns:200px minmax(0,1fr);gap:2px 14px;padding:6px 0;border-top:1px dashed var(--line)}
  dl.gloss>div:first-child{border-top:none;padding-top:0}
  dl.gloss dt{font-weight:700;color:var(--ink)}
  dl.gloss dd{margin:0;color:var(--ink-soft)}
  @media (max-width:700px){dl.gloss>div{grid-template-columns:1fr}}
  table.vltab{min-width:720px}
  table.vltab td .nowrap{white-space:normal}
  table.vltab tr.hasbem td{border-bottom:none;padding-bottom:2px}
  table.vltab tr.vlbemrow td{padding-top:0;color:var(--ink-soft)}
  table.vltab td{line-height:1.55}
  .nowrap{white-space:nowrap}
  /* prototypes and drafts carry a band nobody can overlook */
  .band{border-radius:10px;padding:10px 14px;margin:0 0 12px;font-size:var(--fs-s);line-height:1.5}
  .band>b{display:block;font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.7px;margin-bottom:2px}
  .band .small{display:block;margin-top:3px}
  .band.werk{background:var(--ink);color:var(--paper)}
  .band.werk .small{color:var(--line)}
  .band.entwurf{background:var(--esh-bg);color:var(--esh);border:2px dashed var(--esh-line)}
  /* status classes: the tone of a chip or badge (DATA.labels.ton) — tinted surface,
     tone-coloured border, ink text; a swatch inside names the tone, so the colour
     never carries the statement alone */
  .st-ok{background:var(--ton-ok-bg);border-color:var(--ton-ok-line);color:var(--ink)}
  .st-act{background:var(--ton-act-bg);border-color:var(--ton-act-line);color:var(--ink)}
  .st-dec{background:var(--ton-dec-bg);border-color:var(--ton-dec-line);color:var(--ink)}
  .st-open{background:var(--ton-open-bg);border-color:var(--ton-open-line);color:var(--ink)}
  /* the same four classes as a solid fill where the element IS the colour: bar
     segments, swatches, markers (the .t-* fills of the page head and bars are the same tones) */
  .tbar>i.st-ok,.minibar>i.st-ok,.pbar>i.st-ok,.sw.st-ok{background:var(--ton-ok)}
  .tbar>i.st-act,.minibar>i.st-act,.pbar>i.st-act,.sw.st-act{background:var(--ton-act)}
  .tbar>i.st-dec,.minibar>i.st-dec,.pbar>i.st-dec,.sw.st-dec{background:var(--ton-dec)}
  .tbar>i.st-open,.minibar>i.st-open,.pbar>i.st-open,.sw.st-open{background:var(--ton-open)}
  /* the swatch carries the symbol of its tone — check · dot · diamond · ring, the dossier's
     ✓ ● ◆ ○ (theme.TON_SYM) — so a tone never rests on colour alone */
/*THEME_SWATCH*/
  .badge.st-ok,.badge.st-act,.badge.st-dec,.badge.st-open{font-weight:600}
  .badge>.sw{width:7px;height:7px;margin-right:4px;vertical-align:0}
  .tchip.badge{font-weight:500;white-space:normal}
  .tchip .sw,.tcat .sw{width:8px;height:8px;margin-right:5px;vertical-align:0}
  /* explanations without a mouse: an element with a title can be focused and opened
     (click, tap, Enter, Space) — a small box shows the title text; subtle cue only */
  [data-tip]{cursor:help}
  span[data-tip]:not([class]),.tnum>span[data-tip],td[data-tip],b[data-tip],div[data-tip]:not([class]),sup[data-tip],li[data-tip]>span{
    text-decoration:underline dotted var(--line-dark);text-underline-offset:2px}
  [data-tip]:focus-visible{outline:2px solid var(--link);outline-offset:1px;border-radius:4px}
  [data-tip][aria-expanded="true"]{outline:2px solid var(--link);outline-offset:1px;border-radius:4px}
  #tipbox{position:absolute;z-index:1000;left:0;top:0;max-width:min(380px,calc(100vw - 24px));background:var(--card);
    color:var(--ink);border:1px solid var(--line);border-radius:10px;box-shadow:0 6px 24px var(--shadow);
    padding:9px 32px 9px 12px;font-size:var(--fs-s);line-height:1.5;white-space:pre-line;overflow-wrap:anywhere;text-align:left}
  #tipbox[hidden]{display:none}
  /* a long explanation scrolls inside the box; the box itself always fits the window */
  #tipbox .tipt{max-height:calc(100vh - 96px);overflow-y:auto}
  #tipbox .tipx{position:absolute;top:4px;right:4px;border:0;background:none;font:inherit;font-size:var(--fs-l);line-height:1;
    padding:3px 7px;cursor:pointer;color:var(--ink-soft);border-radius:6px}
  #tipbox .tipx:hover,#tipbox .tipx:focus-visible{background:var(--field);color:var(--ink)}
  #tipbox .tipx:focus-visible,#tipbox .tipgo:focus-visible{outline:2px solid var(--link);outline-offset:1px}
  /* the box offers the action of a chip that has one (⛨ → Leitfaden, a rule → Datenhandhabung) */
  #tipbox .tipgo{display:block;margin-top:7px;padding:4px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);
    color:var(--link);font:inherit;font-size:var(--fs-xs);font-weight:600;cursor:pointer;white-space:normal;text-align:left}
  #tipbox .tipgo[hidden]{display:none}
  #tipbox .tipgo:hover,#tipbox .tipgo:focus-visible{border-color:var(--link)}
  /* rows, toggles and links without an address that act on a click are reachable by keyboard */
  [data-act]:focus-visible{outline:2px solid var(--link);outline-offset:1px;border-radius:4px}
  tr[data-act]:focus-visible{outline-offset:-2px}
  tr[data-act]:focus-visible>td{background:var(--hover)}
  .svc a.svname{color:inherit;text-decoration:none}
  .svc a.svname:hover{text-decoration:underline}
  .svc a.svname:focus-visible{outline:2px solid var(--link);outline-offset:1px;border-radius:4px}
  .vh{position:absolute;left:0;top:0;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
  /* worklists: who acts next, priority tier */
  .tnum{display:inline-flex;gap:12px;font-variant-numeric:tabular-nums;white-space:nowrap;font-weight:600}
  .tnum>span{display:inline-flex;align-items:center;position:relative}
  .tnum>span.z{color:var(--ink-faint);font-weight:400}
  .filt{margin:6px 0 14px}
  .filtrow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 7px}
  .filtrow .fl{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.5px;color:var(--ink-faint);font-weight:700;min-width:100px}
  button.tcat,a.tcat{font:inherit;font-size:var(--fs-xs);color:var(--ink);text-decoration:none}
  .tcat.zero{color:var(--ink-soft)}
  .tcat.zero b{font-weight:400}
  .tcat.zero .sw{opacity:.45}
  .tcat.out{border-style:dashed}
  .filtrow.top{align-items:flex-start}
  .filtrow.top .fl{padding-top:6px}
  .stgs{display:flex;flex-direction:column;gap:5px;flex:1 1 400px;min-width:0}
  .stg{display:flex;flex-wrap:wrap;gap:5px;align-items:center}
  .stgl{font-size:var(--fs-xs);color:var(--ink-soft);font-weight:700;white-space:nowrap;min-width:168px}
  a.dlink{color:var(--ink);font-weight:600;text-decoration:none;border-bottom:1px solid var(--line)}
  a.dlink:hover{border-bottom-color:var(--gold-deep);color:var(--link)}
  a.dlink.lt{font-weight:500}
  .stufehd{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.6px;color:var(--ink-soft);font-weight:700;margin:20px 0 4px}
  .stufetx{font-size:var(--fs-s);color:var(--ink-soft);margin:0 0 8px;max-width:880px}
  .catblk{padding:12px 16px}
  .cathd{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline}
  .cathd .tchip{font-size:var(--fs-xs);font-weight:600}
  .catn{font-size:var(--fs-s);color:var(--ink-soft)}
  .catn b{color:var(--ink)}
  .catx{font-size:var(--fs-s);line-height:1.5;color:var(--ink-soft);margin-top:5px;max-width:900px}
  .catx .hsl{display:inline-block;min-width:118px}
  details.catdet{margin-top:8px}
  details.catdet>summary,details.dsdet>summary,details.dsov>summary{cursor:pointer;font-size:var(--fs-xs);font-weight:600;color:var(--link)}
  details.catdet table,details.dsdet table{margin-top:6px}
  tr.dgrp td{background:var(--field);font-weight:600;border-bottom:1px solid var(--line)}
  td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
  .clipd{font-size:var(--fs-xs);color:var(--ink-soft);line-height:1.45}
  /* Für Dienststellen: overview table */
  table.dsttab td{vertical-align:middle}
  table.dsttab td:last-child{overflow-wrap:anywhere}
  table.dsttab tr.dstrow{cursor:pointer}
  table.dsttab tr.deprow td{background:var(--field);border-bottom:1px solid var(--line);font-size:var(--fs-xs)}
  table.dsttab tr.deprow td b{font-size:var(--fs-s)}
  .minibar{display:inline-flex;gap:1px;height:8px;width:84px;border-radius:3px;overflow:hidden;vertical-align:middle;background:var(--line-soft);margin-right:6px}
  .minibar>i{display:block;height:100%;flex:1 1 0;min-width:2px}
  .stdcell{display:inline-flex;align-items:center;white-space:nowrap}
  details.dsov{margin:4px 0 16px}
  details.dsov>summary{font-size:var(--fs-s);padding:4px 0}
  /* one Dienststelle: the briefing */
  .dshead{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;padding:11px 16px}
  .dshead .dsmeta{display:flex;flex-direction:column;gap:3px;font-size:var(--fs-s);flex:1 1 320px}
  /* in the head of a briefing the contact label stands in the label column, like «Departement» */
  .dshead .hsl,.dshead .klbl{display:inline-block;min-width:164px}
  .dshead .kontakt{display:flex;align-items:baseline}
  .dshead .klbl{flex:none;font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.5px;color:var(--link);font-weight:700;margin-right:6px}
  .dshead .klbl .kc{display:none}
  .dssec{margin:0 0 18px}
  .dssec>h4{font-size:var(--fs-m);margin:0 0 8px;padding-bottom:4px;border-bottom:2px solid var(--gold)}
  .dssec .card{margin-bottom:10px}
  .dsnone{margin:0;font-size:var(--fs-s);color:var(--ink-soft)}
  ol.massn{margin:0;padding-left:24px;font-size:var(--fs-s);line-height:1.5}
  ol.massn>li{padding:6px 0 6px 2px;border-top:1px dashed var(--line)}
  ol.massn>li:first-child{border-top:none;padding-top:0}
  ol.massn .sw{vertical-align:0}
  .dsline{display:flex;gap:6px;align-items:baseline;font-size:var(--fs-s);line-height:1.5;margin:6px 0 0}
  .dsline .sw{transform:translateY(1px)}
  .dsstdv{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline;margin-bottom:6px}
  .dsstdv .kzv{font-size:var(--fs-xxl)}
  .dsstufe{padding:8px 0;border-top:1px dashed var(--line)}
  .dsstufe:first-child{border-top:none;padding-top:0}
  .dsshd{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline;font-size:var(--fs-s)}
  ul.pline{list-style:none;margin:0;padding:0}
  ul.pline>li{padding:2px 0;display:flex;flex-wrap:wrap;gap:2px 8px;align-items:baseline}
  table.dsptab td:first-child{width:36%}
  ul.dssvc{margin:0;padding-left:18px;font-size:var(--fs-s);line-height:1.55}
  ul.dssvc a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
  ul.dssvc a:hover{border-bottom-color:var(--gold-deep)}
  .dsfc{display:none}
  .dsmob,.dsmobl{display:none}
  /* a DVSH grouping that is not an office of its own */
  .sammel{font-size:var(--fs-xs);font-weight:600;color:var(--ink-soft);border:1px dashed var(--line-dark);border-radius:6px;padding:0 6px;margin-left:4px;display:inline-block}
  .mzmix{font-size:var(--fs-xs);color:var(--ink-soft);margin-top:2px}
  .offlink{font-size:var(--fs-xs);font-weight:600;color:var(--link);text-decoration:none;white-space:nowrap;margin-left:2px}
  .offlink:hover{text-decoration:underline}
  .offhd.active{color:var(--ink);background:var(--hover);box-shadow:inset 0 0 0 1px var(--gold-deep)}
  /* narrow viewports: the sidebar becomes a drawer behind a ☰ button — it is
     ~38'000 px tall at phone width, so stacking it above the content would
     push every page off screen */
  .navbtn{display:none;font:inherit;font-size:var(--fs-s);padding:6px 10px;border:1px solid var(--line);
    border-radius:8px;background:var(--field);cursor:pointer;color:var(--ink)}
  @media (max-width:900px){
    .layout{flex-direction:column}
    aside{display:none;position:static;align-self:auto;width:auto;flex:none;max-height:60vh;border-right:0;border-bottom:1px solid var(--line)}
    .layout.nav-open aside{display:block}
    main{padding:14px 16px;max-width:none;min-width:0}
    header{padding:10px 14px}
    header .gsearch{min-width:0;flex:1 1 100%;margin-left:0}
    header .stamp{margin-left:0;text-align:left;flex:1 1 100%}
    header .htxt{flex:1 1 0;min-width:0}
    #warn.stamp,#stamp{display:none}
    .navbtn{display:inline-block;position:fixed;right:12px;bottom:12px;z-index:60;box-shadow:0 2px 8px var(--shadow)}
    main{padding-bottom:64px}
    .cols{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
    .hometiles .hometile{flex:1 1 140px}
    .dfrow{grid-template-columns:1fr}
    .dfrg{text-align:left;max-width:none}
    .dvgrid{grid-template-columns:1fr}
    .card{overflow-x:auto}
  }
  /* a phone: the head of a Formular card, its counts and chips, and the contact line of a
     briefing wrap instead of scrolling inside their card */
  @media (max-width:600px){
    .dfhdr{flex-wrap:wrap}
    .dfhdr .nowrap,.chip.sub,.kontakt .kp,a.inl,.dfrg .badge,.eshb,.dfname{white-space:normal}
    .eshb,.chip.sub{overflow-wrap:anywhere}
    .chip.sub{flex-wrap:wrap}
    .dshead .kontakt{flex-wrap:wrap}
    .dshead .hsl,.dshead .klbl{min-width:0;margin-right:6px}
  }
  /* up to 1340 px the six columns do not fit side by side: a Dienststelle becomes a block of
     two lines — its name (Services and Formulare below it), its data standard and its open
     points under the column heads, then its most important measure across the full width */
  @media screen and (max-width:1340px){
    table.dsttab,table.dsttab thead,table.dsttab tbody{display:block;width:100%}
    table.dsttab tr{display:grid;grid-template-columns:minmax(0,1fr) 176px 200px;gap:3px 16px;align-items:center;
      padding:8px 0;border-bottom:1px solid var(--line)}
    table.dsttab thead tr{padding:2px 0 6px}
    table.dsttab tr.deprow{background:var(--field);padding:8px 6px}
    table.dsttab th,table.dsttab td{display:block;border:0;padding:0}
    table.dsttab th:nth-child(2),table.dsttab th:nth-child(3),table.dsttab th:nth-child(6),
    table.dsttab td:nth-child(2),table.dsttab td:nth-child(3),table.dsttab tr.deprow td:nth-child(6){display:none}
    table.dsttab td:nth-child(6){grid-column:1/-1}
    table.dsttab .dsmob{display:block}
    table.dsttab .dsmobl{display:inline-block;margin-right:8px;font-size:var(--fs-xs);color:var(--ink-faint);
      text-transform:uppercase;letter-spacing:.4px;font-weight:600}
    table.dsttab .dsmobl.ph{display:none}
  }
  /* a phone: no column heads, the open points on a line of their own, labelled */
  @media screen and (max-width:700px){
    table.dsttab thead{display:none}
    table.dsttab tr{grid-template-columns:minmax(0,1fr) auto;gap:2px 10px}
    table.dsttab td:nth-child(5){grid-column:1/-1}
    table.dsttab .tnum{white-space:normal;flex-wrap:wrap;gap:4px 12px}
    table.dsttab .dsmobl.ph{display:inline-block}
  }
  .offnote{background:var(--gold-tint);border-bottom:1px solid var(--gold);padding:8px 16px;font-size:var(--fs-s);line-height:1.45}
  .offnote a{color:inherit}
  .bootmsg{max-width:720px;margin:48px auto;padding:20px 24px;border:1px solid var(--line);border-radius:10px;
    background:var(--card);display:flex;flex-direction:column;gap:8px;font-size:var(--fs-m);line-height:1.5}
  .bootmsg b{font-size:var(--fs-l)}
  .bootmsg.err{border-color:var(--ton-act)}
  .bootmsg a{color:inherit}
  /* print: the content only — no sidebar, no header bar, no controls; colours kept,
     small blocks never split across pages. The text sizes need no rule here: theme.py
     switches the six sizes to pt on paper (9 to 9.5 pt for the briefing, two to three pages) */
  @media print{
    header,aside,.navbtn,.offnote,.noprint,details.phmore,#bootmsg,#tipbox{display:none !important}
    [data-tip],li[data-tip]>span{text-decoration:none !important;outline:none !important}
    body{background:var(--card)}
    .layout{display:block;min-height:0}
    main{padding:0;max-width:none;overflow:visible}
    main *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .card,.pagehead{box-shadow:none;border-color:var(--line-strong)}
    h3.view,h4,.dvsub,.stufehd,.dsshd{break-after:avoid;page-break-after:avoid}
    tr,li,.kz,.dsstufe,.dshead,.pagehead,.catblk{break-inside:avoid;page-break-inside:avoid}
    .dssec{break-inside:auto}
    a,a.dlink,a.inl{color:inherit;text-decoration:none;border-bottom:none}
    ul.dssvc{columns:2;column-gap:24px;line-height:1.35}
    .card{padding:8px 12px;margin-bottom:8px}
    .pagehead{padding:6px 12px;margin-bottom:8px}
    .dssec{margin:0 0 6px}
    .dssec>h4{margin:0 0 5px;padding-bottom:2px}
    .dssec .card{margin-bottom:4px;padding:6px 12px}
    ol.massn{line-height:1.4}
    ol.massn>li{padding:3px 0 3px 2px}
    .tleg{gap:1px}
    .dsstufe{padding:3px 0}
    .dshead{padding:6px 12px}
    table.ft th,table.ft td{padding:4px 8px}
    .kznote.dsnote{line-height:1.3;margin-top:3px}
    ul.dssvc>li{break-inside:avoid}
    .dsfl{display:none}
    .dsfc{display:inline}
    details.dsdet{display:none}
    .card,.card:has(table),.card:has(>.flowsvg){overflow:visible}
    .printonly{display:block}
    .dssvcsec.long .card{display:none}
    .dsstufe .tnum{gap:10px;white-space:normal;flex-wrap:wrap}
    .dsstufe .tnum .vh{position:static;width:auto;height:auto;overflow:visible;clip:auto;white-space:nowrap;font-weight:400;margin-right:3px}
    .tonkey{padding:3px 8px;margin:0 0 6px}
    .stufetx{margin:1px 0 3px;line-height:1.35}
    .dsline{margin:4px 0 0}
    .dshead .dsmeta{gap:1px}
    /* on paper a label is only as wide as its words: the contact stays on one line where it can */
    .dshead .hsl,.dshead .klbl{min-width:0}
    /* printed, the Formular's own title stays: two forms of one service must stay distinguishable */
    .tscroll{overflow:visible}
    @page{margin:14mm 12mm}
  }
</style>
</head>
<body>
<button class="skip" type="button" onclick="var m=document.getElementById('main');m.setAttribute('tabindex','-1');m.focus();">Zum Inhalt</button>
<header>
  <div class="crest" aria-hidden="true"></div>
  <div class="htxt"><div class="sub">Kanton Schaffhausen</div>
    <h1>Compliance-Databank · Datenstandards, Formulare &amp; Recht</h1></div>
  <button class="navbtn" type="button" aria-controls="sidenav" aria-expanded="false" onclick="var o=document.querySelector('.layout').classList.toggle('nav-open');this.setAttribute('aria-expanded',String(o));if(o)window.scrollTo(0,0);" title="Navigation ein-/ausblenden">☰ Navigation</button>
  <input id="gsearch" class="gsearch" type="search" placeholder="Suche: Gesetz, Artikel, Datenfeld, Teilfeld, Regel, Empfänger, Dienststelle …" title="Suche über Services, Formulare, Datenfelder (inkl. Teilfelder), Gesetze, Regeln, Empfänger, Beilagen, Themengruppen (Lebenslagen), Begriffe, eCH-Standards, eSH-Entwürfe, Dienststellen, die Gestaltung der Formulare, Rollen, Konzepte und Register — Enter oder kurz warten">
  <span class="warn" id="warn"></span>
  <span class="stamp" id="stamp"></span>
</header>
<div class="layout">
  <aside id="sidenav" aria-label="Navigation">
    <h2>Einstieg</h2>
    <button class="tab" data-tab="home">Übersicht<span class="tabsub">Datenstandard und Lücken auf einen Blick</span></button>
    <button class="tab" data-tab="dienststellen">Für Dienststellen<span class="tabsub">Was muss ich an meinen Formularen ändern?</span></button>
    <button class="tab" data-tab="kanton">Für den Kanton<span class="tabsub">Was muss entschieden werden?</span></button>
    <button class="tab" data-tab="methode">Methode &amp; Quellen<span class="tabsub">Wie ist die Databank gebaut, woher stammen die Daten?</span></button>
    <h2>Datenstandard</h2>
    <button class="tab" data-tab="katalog">Datenkatalog<span class="tabsub">Jede Angabe einmal: eCH-Element, Einheitlichkeit, Once-Only</span></button>
    <button class="tab" data-tab="begriffe">Begriffe<span class="tabsub">Eine Angabe, ein Name</span></button>
    <button class="tab" data-tab="esh">eSH-Katalog (Entwurf)<span class="tabsub">Entwurf des Kantons, wo kein eCH-Standard besteht</span></button>
    <h2>Datenmodell &amp; Once-Only</h2>
    <button class="tab" data-tab="datenmodell">Datenmodell<span class="tabsub">Wessen Angabe, ein Element je Angabe, Kennungen, Gesetzesstand, Wirkung einer Änderung</span></button>
    <button class="tab" data-tab="onceonly">Was Register schon wissen<span class="tabsub">Welche Angaben und Beilagen ein Register hält — und was das sparen könnte</span></button>
    <h2>Erscheinungsbild</h2>
    <button class="tab" data-tab="gestaltung">Gestaltung der Formulare<span class="tabsub">Schrift, Farben, Barrierefreiheit, Kontaktangaben, Aufbau</span></button>
    <h2>Arbeitslisten</h2>
    <button class="tab" data-tab="todo">Handlungsbedarf<span class="tabsub">Was Dienststellen ändern und der Kanton entscheidet — je Dienststelle</span></button>
    <button class="tab" data-tab="recherche">Recherche der Databank<span class="tabsub">Was die Databank selbst noch nachschlagen muss</span></button>
    <a class="tab ext" href="dossiers/index.html" target="_blank" rel="noreferrer" title="Index aller Datenschutz-Dossiers (ein Dossier je Service, druckbar; aus derselben Databank erzeugt)">Datenschutz-Dossiers ↗<span class="tabsub">Ein druckbares Dossier je Service (dossiers/index.html)</span></a>
    <h2>Nachschlagewerke</h2>
    <button class="tab" data-tab="lebenslagen">Lebenslagen<span class="tabsub">Die Themengruppen von eCH-0049: was eine Situation verlangt</span></button>
    <button class="tab" data-tab="register">Verzeichnis der Bearbeitungstätigkeiten<span class="tabsub">Registerstruktur nach KDSG Art. 17b Abs. 2 &amp; DSFA-Triage</span></button>
    <button class="tab" data-tab="rules">Datenhandhabung<span class="tabsub">Die Regeln im Wortlaut, je Gesetz</span></button>
    <button class="tab" data-tab="guide">Leitfaden<span class="tabsub">Dieselben Regeln in einfacher Sprache</span></button>
    <button class="tab" data-tab="datenfluss">Datenfluss<span class="tabsub">Wer gibt wem Daten weiter — belegte Bekanntgaben</span></button>
    <h2>Werkstatt · Prototypen</h2>
    <button class="tab" data-tab="buerger">Bürgersicht<span class="tabsub">Datentresor, synthetisch: wie der Kanton speichern könnte</span></button>
    <a class="tab ext" href="flows.html" target="_blank" rel="noopener" title="Prototyp: ein Formular als Folge einfacher Fragen, mit Vorbefüllung und Prüfung am Schluss (flows.html, mit eigener Formularsuche)">Geführte Formulare ↗<span class="tabsub">Prototyp: das Formular als einfache Fragen (flows.html)</span></a>
    <h2>Formulare &amp; Services</h2>
    <div id="services"></div>
    <h2 id="legendhd">Legende <span class="legsub">— Farben und Kennzeichen dieser Seite</span></h2>
    <div class="legend" id="legend"></div>
  </aside>
  <main id="main"><div class="bootmsg" id="bootmsg"><b>Die Databank wird geladen …</b>
    <span>Die Seite enthält alle Daten (knapp %%SIZE%%, über das Netz etwa %%NETSIZE%%). Beim ersten Öffnen dauert das je nach Verbindung und Gerät einige Sekunden bis gegen eine Minute.</span></div>
    <noscript><div class="bootmsg err"><b>JavaScript ist ausgeschaltet.</b> <span>Das Dashboard braucht JavaScript — bitte im Browser erlauben und die Seite neu laden.</span></div></noscript></main>
</div>
<div id="tipbox" role="dialog" aria-label="Erklärung" hidden><div class="tipt"></div><button class="tipgo" type="button" hidden></button><button class="tipx" type="button" aria-label="Erklärung schliessen">×</button></div>
<div id="tiplive" class="vh" aria-live="polite"></div>
<div id="routelive" class="vh" aria-live="polite"></div>
<script id="data" type="application/json">/*DATA*/</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const GUIDE = /*GUIDE*/;
// the export contract as exportvertrag.json holds it when this page is built (versions, JSON Schemas)
const VERTRAG = /*VERTRAG*/;
const state = {service:'all', tab:'home', sub:'felder', tree:'list', filter:'', open:{}, navmode:'services', begq:''};
// scrolling to a target glides — unless the reader's system asks for reduced motion
const MOTION=(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)?'auto':'smooth';
// ---- German labels: ONE source (scripts/labels.py -> data_export.json -> DATA.labels) ----
// A code that has no label renders visibly as ⟨code⟩ — never raw, never silently.
const LAB=DATA.labels||{};
const lab=(m,c)=>(c==null||c==='')?'':(((m||{})[c])||('⟨'+c+'⟩'));
const ESH_STATUS=LAB.esh_status||{entwurf:'Entwurf'};
const DFTYPE=LAB.dftype||{}, SENS=LAB.sens||{}, HSENS=SENS, OUTCOME_DE=LAB.outcome||{}, RM_DE=LAB.rm||{},
  RM_STATUS=LAB.rm_status||{}, HALTER_DE=LAB.halter||{}, OBLIG_DE=LAB.oblig||{}, CHAN_DE=LAB.chan||{},
  ENDPOINT_DE=LAB.endpoint||{}, DVSH_STATUS=LAB.dvsh_status||{}, MODE_DE=LAB.mode||{}, DIV_DE=LAB.div||{},
  CHECK_DE=LAB.check||{}, JUR_DE=LAB.jur||{}, ASPECT=LAB.aspect||{}, SCOPE_DE=LAB.scope||{},
  KAT_DE=LAB.kat||{}, TRIGGER_DE=LAB.trigger||{}, DISP_DE=LAB.disposition||{}, MINMAX_DE=LAB.minmax||{},
  TODO_ART=LAB.todo_art||{}, TODO_CATS=LAB.todo_cats||[];
const TODO_BY=Object.fromEntries(TODO_CATS.map(c=>[c[0],c]));
// a category the labels do not know still renders (visibly marked), never crashes the board
const todoCat=k=>TODO_BY[k]||[k,'⟨'+k+'⟩','st-open','recherche',''];
// ---- one status language: the colour says who acts next (DATA.labels.ton / ton_map) ----
// every status is drawn with st-ok · st-act · st-dec · st-open; a code without a tone
// entry is not settled — grey, never green. Kennzeichen (level of law, ⛨, DVSH/SHEP,
// ↺ Once-Only, channel) are neutral and outlined: they mark, they do not judge.
const tonOf=(dom,code)=>((LAB.ton_map||{})[dom]||{})[code]||'open';
const SW=t=>`<i class="sw t-${t}"></i>`;
// the colour in words, for a title: «(rot: Dienststelle handelt)»
const tonWords=t=>{const x=(LAB.ton||{})[t]||{}; return `(${x.farbe||'⟨'+t+'⟩'}: ${x.label||'⟨'+t+'⟩'})`;};
// a status badge: tinted surface, tone border, swatch and a visible short label; the
// title (raw text, escaped here) explains it and names who acts next. label arrives escaped
const stBadge=(t,label,tip,cls,attrs)=>`<span class="badge st-${t}${cls?' '+cls:''}" title="${esc((tip?tip+'\n':'')+tonWords(t))}"${attrs||''}>${SW(t)}${label}</span>`;
// a Kennzeichen as a badge: outlined, neutral — label arrives escaped, tip raw
const mkBadge=(label,tip,cls)=>`<span class="badge mk${cls?' '+cls:''}"${tip?` title="${esc(tip)}"`:''}>${label}</span>`;
// The eCH state of a data point is classified ONCE — export_json._ech_state — and stamped on
// every Datenfeld and Teilfeld as `ech_state` (a key of DATA.labels.ton_map.ech); the legal
// question of a Datenfeld likewise as `basis_state` (ton_map.basis). Chips, counts and bars
// read these keys and the figures the export counted from them (kopfzahlen,
// dienststellen_uebersicht[].standard) — the page never asks the questions a second time.
// The STATUS of a standard has a small chip of its own: still in the works (In Arbeit) — the
// canton decides meanwhile (amber); no longer in force (sistiert, aufgehoben, abgelöst) —
// the databank replaces the mapping by the successor (grey)
const ECH_STD_STATE={'In Arbeit':'standard_entwurf','Sistiert':'standard_alt','Aufgehoben':'standard_alt','Abgelöst':'standard_alt'};
// the tone of a standard's status; a status the export does not know is not settled: grey
const echDraftTon=st=>ECH_STD_STATE[st]?tonOf('ech',ECH_STD_STATE[st]):'open';
// shareable links: state lives in location.hash (#tab/serviceId/sub), read at
// startup and on back/forward, written by render()
// the canonical (omitted) sub per tab: #lebenslagen === #lebenslagen/all/privat,
// #todo === #todo/all/alle, #begriffe === #begriffe/all/angleichen
const DEFAULT_SUB={lebenslagen:'privat',buerger:'0',todo:'alle',begriffe:'angleichen'};
const defSub=tab=>DEFAULT_SUB[tab]||'felder';
function readHash(){
  // ALWAYS reset every part: a missing segment means its default, otherwise a
  // stale state.sub survives the browser's Back and the old hash gets
  // re-pushed — the "back button does nothing" loop
  const p=(location.hash||'').replace(/^#/,'').split('/');
  state.tab=p[0]||'home';
  state.service=p[1]||'all';
  state.sub=p[2]||'felder';
  // legacy links (#tree/<id>, #info/<id>) open the Gesetze segment of the service page
  if(state.tab==='tree'||state.tab==='info'){state.tab='fields';state.sub='gesetze';}
  // short form of a Dienststelle link (#dienststellen/<slug>) opens the same page
  // as the canonical #dienststellen/all/<slug>; writeHash then normalises it
  if(state.tab==='dienststellen'&&p[1]&&p[1]!=='all'&&!p[2]) state.sub=p[1];
  // a service id is meaningful on the service page only
  if(state.tab!=='fields') state.service='all';
}
// hash changes this page wrote itself and whose hashchange event is still to come
let _writingHash=0;
// a render triggered by the URL itself (startup, Back/Forward) may normalise
// the hash, but must REPLACE it — pushing would trap the Back button
let _fromUrl=false;
// history.replaceState can throw on pages opened from a local file in some
// browsers; the hash then simply is not normalised — rendering never depends on it.
// The entry keeps its state (the mark the scroll rule below reads)
function safeReplace(h){try{if(history.replaceState){history.replaceState(history.state,'',h);return true;}}catch(e){}return false;}
// the address of the current state, as the hash writes it
function hashOfState(){
  const svc=state.tab==='fields'?String(state.service):'all';
  const sub=state.sub===defSub(state.tab)?'felder':state.sub;
  return '#'+state.tab+(svc!=='all'||sub!=='felder'?'/'+svc:'')+(sub!=='felder'?'/'+sub:'');
}
function writeHash(){
  const fromUrl=_fromUrl; _fromUrl=false;
  const svc=state.tab==='fields'?String(state.service):'all';
  const sub=state.sub===defSub(state.tab)?'felder':state.sub;
  const h=hashOfState();
  if(location.hash===h) return;
  if(fromUrl&&safeReplace(h)) return;
  // a hand-written or shared link may spell the SAME state non-canonically
  // (#fields/40/felder vs #fields/40). Rewriting it as a new history entry
  // would trap the back button, so normalise in place instead.
  const p=(location.hash||'').replace(/^#/,'').split('/');
  const same=(p[0]||'home')===state.tab&&(p[1]||'all')===svc&&(p[2]||'felder')===sub;
  if(same&&safeReplace(h)) return;
  // successive search queries (debounce while typing) share ONE history entry
  if(/^#search\//.test(location.hash)&&/^#search\//.test(h)&&safeReplace(h)) return;
  // (counted only when the address really changes: only then a hashchange event follows)
  const was=location.href; location.hash=h; if(location.href!==was) _writingHash++;
}
// ---------- where a page opens: ONE rule, applied at the end of render() ----------
// A new page opens at its top. Back and Forward return to the place the reader left, with
// the folded lists as they were. A redraw of the same page (a filter, a segment, a toggle)
// stays where it is. No click handler scrolls on its own; one that leads to an anchor (a
// category card, the block of a Formular) jumps there after render().
// Every history entry carries a mark of its own in history.state (it survives Back,
// Forward and a reload); the place is remembered per mark, for this visit.
try{history.scrollRestoration='manual';}catch(e){}
const _places={}; let _entry=null, _nav=null, _lastPage=null;
const entryMark=()=>{try{const s=history.state; return s&&s.cg?String(s.cg):null;}catch(e){return null;}};
// the mark of the current entry; where the browser refuses a state (some do for local
// files) the address stands in for it
function markEntry(){
  let k=entryMark();
  if(!k){k=Date.now().toString(36)+Math.random().toString(36).slice(2,7);
    try{history.replaceState({cg:k},'');}catch(e){}
    if(entryMark()!==k) k=location.hash||'#';}
  return k;
}
// which page the address names — the filters and segments of one page share it
function pageKey(){
  const s=String(state.sub||'');
  const part=state.tab==='fields'?(s.startsWith('form-')?s.split('~')[0]:'')
    :state.tab==='dienststellen'?(s==='felder'?'':s)
    :state.tab==='lebenslagen'?(/^g-\d+$/.test(s)?s:'')
    :state.tab==='search'?s:'';
  return state.tab+'/'+state.service+'/'+part;
}
// the place on the page as it stands: scroll position, which folded lists are open, which
// hit lists are shown in full, the filter text of the Begriffe list
function placeNow(){
  const m=document.getElementById('main'), q=document.getElementById('begq');
  if(!m) return null;
  return {page:_lastPage, y:window.scrollY, q:q?q.value:null,
    det:[...m.querySelectorAll('details')].map(d=>d.open?'1':'0').join(''),
    rows:[...m.querySelectorAll('tr.katforms')].map(r=>r.hidden?'0':'1').join(''),
    more:[...m.querySelectorAll('[data-shown]')].map(x=>x.getAttribute('data-shown'))};
}
function placeBack(p){
  const m=document.getElementById('main'); if(!m||!p) return;
  const q=document.getElementById('begq');
  if(q&&p.q!=null&&q.value!==p.q){q.value=p.q; q.dispatchEvent(new Event('input'));}
  (p.more||[]).forEach(id=>{const a=m.querySelector('[data-showmore="'+String(id).replace(/[^a-z0-9]/gi,'')+'"]'); if(a&&a.onclick) a.onclick();});
  const D=[...m.querySelectorAll('details')];
  if(D.length===String(p.det||'').length) D.forEach((d,i)=>{d.open=p.det[i]==='1';});
  const R=[...m.querySelectorAll('tr.katforms')];
  if(R.length===String(p.rows||'').length) R.forEach((r,i)=>{const on=p.rows[i]==='1';
    if(r.hidden===on){r.hidden=!on; const t=r.previousElementSibling; if(t) t.setAttribute('aria-expanded',String(on));}});
  window.scrollTo(0,Number(p.y)||0);
}
// true while a Back/Forward render returns to a remembered place: the jump to an anchor
// (focusCat, focusDiv) is then left out
const comingBack=()=>!!(_nav&&_nav.traverse&&_places[entryMark()||location.hash||'#']);
// called at the end of render(): open at the top, return to the place, or stay
function placeAfterRender(){
  const nav=_nav; _nav=null;
  const page=pageKey(), mark=markEntry(), back=nav&&nav.traverse?_places[mark]:null;
  const fresh=_lastPage!==null&&page!==_lastPage;
  _entry=mark; _lastPage=page;
  if(back&&back.page===page) placeBack(back);
  else if(fresh) window.scrollTo(0,0);
  if(fresh||back) navIntoView();
}
// the entry of the current page stays visible in the sidebar, which scrolls on its own
function navIntoView(){
  const a=document.getElementById('sidenav'), t=a&&a.querySelector('.tab.active,.svc.active');
  if(!t||a.scrollHeight<=a.clientHeight+1) return;
  const ar=a.getBoundingClientRect(), tr=t.getBoundingClientRect(), bottom=Math.min(ar.bottom,window.innerHeight);
  if(tr.top<ar.top||tr.bottom>bottom) a.scrollTop+=tr.top-ar.top-(bottom-ar.top)/3;
}
// a reload returns to the place as well (the browser's own restoration is switched off above)
window.addEventListener('pagehide',()=>{try{sessionStorage.setItem('cgPlace',JSON.stringify({h:location.hash,p:placeNow()}));}catch(e){}});
function placeAfterReload(){
  try{const nt=((performance.getEntriesByType('navigation')||[])[0]||{}).type, s=JSON.parse(sessionStorage.getItem('cgPlace')||'null');
    if((nt==='reload'||nt==='back_forward')&&s&&s.p&&s.h===location.hash&&s.p.page===_lastPage) placeBack(s.p);}catch(e){}
}
// how the latest navigation came about, where the browser has the Navigation API
// ('traverse' = Back/Forward)
let _navType=null;
try{if(window.navigation&&navigation.addEventListener) navigation.addEventListener('navigate',e=>{_navType=e.navigationType;});}catch(e){}
window.addEventListener('hashchange',()=>{
  const type=_navType; _navType=null;
  closeNav();
  if(_writingHash>0){_writingHash--;return;}
  const asked=location.hash;
  // Back/Forward: the Navigation API says so; without it, an entry that already carries a
  // mark (or an address with a remembered place) is one the reader has been on before
  _nav={traverse:type?type==='traverse':!!(entryMark()||_places[location.hash||'#'])};
  _fromUrl=true;readHash();render();
  // a link the page had to correct shows its notice at the top
  if(location.hash!==asked) window.scrollTo(0,0);
});
const DEPT_ORDER=['Baudepartement','Departement des Innern','Erziehungsdepartement','Finanzdepartement','Volkswirtschaftsdepartement'];
// departments in that order, any other A–Z after them («Für Dienststellen», «Gestaltung der Formulare»)
const deptCmp=(a,b)=>{const ia=DEPT_ORDER.indexOf(a), ib=DEPT_ORDER.indexOf(b);
  return (ia<0?99:ia)-(ib<0?99:ib)||a.localeCompare(b,'de');};
function deptName(s){return (s.department||'(ohne Departement)').trim();}

// ---- indexes + in-browser reconciliation (computed, never stored) ----------
const lawById={}, svcById={};
DATA.laws.forEach(l=>lawById[l.id]=l);
DATA.services.forEach(s=>svcById[s.id]=s);
const formsByService={};
DATA.forms.forEach(f=>{(formsByService[f.service_id]=formsByService[f.service_id]||[]).push(f);});
// department -> office -> services
const deptTree={};
DATA.services.forEach(s=>{const d=deptName(s), o=(s.dienststelle||'(ohne Dienststelle)').trim();
  (deptTree[d]=deptTree[d]||{})[o]=(deptTree[d][o]||[]); deptTree[d][o].push(s);});
function deptKeys(){return Object.keys(deptTree).sort((a,b)=>{
  const ia=DEPT_ORDER.indexOf(a), ib=DEPT_ORDER.indexOf(b);
  return (ia<0?99:ia)-(ib<0?99:ib) || a.localeCompare(b);});}
// documentation state per service, on the CURATED data_field layer: every field falls into
// the tone of its exported answer to the legal question (d.basis_state, classified once in
// export_json._basis_state — the split of the Rechtsgrundlage card on the Übersicht,
// kopfzahlen.rechtsgrundlage): a cited norm or the task → ok; «ohne» → the Dienststelle
// acts; «offen» → the canton decides; not yet researched, or ⛨ judged task-necessary
// without its basis under KDSG Art. 5 → the databank. have = the green part only.
function grounding(sid){
  const g={need:0,have:0,ok:0,act:0,dec:0,open:0};
  (formsByService[sid]||[]).forEach(fm=>(fm.data_fields||[]).forEach(d=>{
    g.need++;
    const t=tonOf('basis',d.basis_state);
    const k=t in g?t:'open'; g[k]++; if(k==='ok') g.have++;}));
  return g;
}
// the same split as a small segmented bar (tone fills), readable without colour through
// its label and the numbers beside it
function basisBar(g,aria,w){
  const T=['ok','act','dec','open'], tot=T.reduce((a,t)=>a+(g[t]||0),0); if(!tot) return '';
  return `<span class="minibar" style="width:${w||140}px" role="img" aria-label="${esc(aria+': '+T.map(t=>tonLabel(t)+' '+nf(g[t]||0)).join(', '))}">${
    T.filter(t=>g[t]).map(t=>`<i class="t-${t}" style="flex-grow:${g[t]}"></i>`).join('')}</span>`;
}

// quotes included: most of this page puts DB text into title="…" attributes,
// and a Gesetzestitel or Feldname containing " would otherwise break the tag
const esc = s => (s==null?'':String(s)).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const el = (h)=>{const d=document.createElement('div');d.innerHTML=h;return d.firstElementChild;};
// the level of a law is a Kennzeichen, never a tone
const jur = j => `<span class="badge mk mk-${esc(j)}">${esc(lab(JUR_DE,j))}</span>`;
// SR = Bundesrecht (Fedlex), SHR = Schaffhauser Rechtsbuch: the prefix follows the
// law's jurisdiction, never the mere presence of a number — «SR 120.100» would send
// a reader to a federal act instead of the Gemeindegesetz
const refNo=(j,sr,cref)=>sr?(j==='federal'?'SR ':'SHR ')+sr:(cref||'');
// numbers de-CH (1'234), numerus («1 Regel», «2 Regeln» — never a bare plural behind
// a count) and dates dd.mm.yyyy[, hh:mm] from the export's ISO strings — the three
// formatting helpers every view uses
// (one Intl.NumberFormat each, created once — not a locale lookup per number)
const NF=new Intl.NumberFormat('de-CH'), NF1=new Intl.NumberFormat('de-CH',{minimumFractionDigits:1,maximumFractionDigits:1});
const nf=n=>NF.format(Number(n||0));
const nf1=x=>NF1.format(Number(x||0));
const plw=(n,sg,p)=>Number(n)===1?sg:p;
const pl=(n,sg,p)=>`${nf(n)} ${plw(n,sg,p)}`;
const fmtDate=s=>{const m=/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}:\d{2}))?/.exec(String(s||''));
  return m?`${m[3]}.${m[2]}.${m[1]}${m[4]?', '+m[4]:''}`:(s==null?'':String(s));};
// blocker keys are ASCII constants shared with export_json («eCH-Abdeckung < 50%»);
// for the reader the percent sign gets its space («50 %») like every other percentage
const blockerLabel=b=>esc(b).replace(/(\d)%/g,'$1 %');
function unver(lc){   // three verification levels, in their tone (ton_map.verif)
  const v=(k,label,tip)=>' '+stBadge(tonOf('verif',k),label,tip);
  if(!lc || lc==='UNVERIFIED') return v('unverifiziert','unverifiziert','nicht verifiziert, keine Quelle — eine Hausaufgabe der Databank');
  // the levels as the ingest scripts set them: 'verified' = a federal article read from
  // the official Fedlex text (ingest_fed.py), 'Gesetze-PDF …' = read from the official
  // law PDF (ingest_laws.py; cantonal law: the Schaffhauser Rechtsbuch)
  if(lc==='verified') return v('verified','verifiziert','Bundesrecht: Artikel aus dem amtlichen Fedlex-Text gelesen');
  if(/^Gesetze/.test(lc)) return v('quelle_pdf','Quelle '+esc(lc.replace('Gesetze-PDF ','')),'aus dem amtlichen Gesetzes-PDF gelesen (kantonales Recht: Schaffhauser Rechtsbuch)');
  if(/^zitiert/.test(lc)) return v('unverifiziert','zitiert (unverif.)','im Formular zitiert; noch nicht gegen Gesetze/Fedlex verifiziert');
  // a level this page does not know: not settled — grey
  return v('⟨'+lc+'⟩',esc(lc),'Verifikationsstufe ohne Zuordnung');
}
function artLabel(no){
  if(!no || no==='UNKNOWN') return 'Art. UNBEKANNT';
  return /^(§|Art)/.test(no) ? no : 'Art. '+no;   // Swiss acts use Art. or §
}
function citeStr(lb){
  const art = artLabel(lb.article_no);
  const det = lb.citation_detail ? ' '+lb.citation_detail : '';
  const sr  = refNo(lb.jurisdiction,lb.sr_number,lb.cantonal_ref);
  return `${jur(lb.jurisdiction)} <span class="mono">${esc(art+det)}</span> ${esc(lb.law_short||lb.law_title)}${sr?' · '+esc(sr):''}${unver(lb.last_checked)}`;
}

// no explicit article is NOT one thing: needed for the task (KDSG Art. 4 lit. b),
// genuinely surplus, not yet assessed, or not yet researched at all
function basisBadge(d){
  const why=d.basis_begruendung?' — '+d.basis_begruendung:'';
  // label and tone of the exported answer to the legal question (d.basis_state, ton_map.basis):
  // aufgabe ok · art5_offen grey · ohne red · offen amber · not yet researched grey
  const B=(k,label,tip)=>stBadge(tonOf('basis',k),label,tip);
  // a besonders schützenswerte Angabe needs KDSG Art. 5 Abs. 1 (lit. a formelles
  // Gesetz / unentbehrlich, or lit. b Zustimmung); Art. 4 Abs. 1 lit. b alone is
  // not enough — until that anchor is named the field is OPEN, not covered
  const bs=d.basis_state;
  if(bs==='art5_offen') return B('art5_offen','aufgabennotwendig — Grundlage nach KDSG Art. 5 Abs. 1 noch nicht benannt',`Erforderlichkeit für die Aufgabe bejaht (KDSG Art. 4 Abs. 1 lit. b); als besonders schützenswerte Angabe nur zulässig nach KDSG Art. 5 Abs. 1 (lit. a: ein formelles Gesetz sieht sie vor oder sie ist für eine darin klar umschriebene Aufgabe unentbehrlich; lit. b: Zustimmung, ausdrücklich oder nach den Umständen unzweifelhaft vorausgesetzt) — diese Grundlage ist noch nicht benannt${why}`);
  if(bs==='aufgabe') return B('aufgabe','aufgabennotwendig — keine explizite Norm',`Keine Norm nennt dieses Feld ausdrücklich, aber die Aufgabe ist ohne diese Angabe nicht erfüllbar — Einordnung der Databank nach dem Massstab von KDSG Art. 4 Abs. 1 lit. b${why}`);
  if(bs==='ohne') return B('ohne','ohne Grundlage — weder Norm noch Aufgabenbedarf',`Weder eine Norm noch die Aufgabe verlangen dieses Feld — nur freiwillig erhebbar (Leitfaden «Erheben»)${why}`);
  if(bs==='offen') return B('offen','keine explizite Norm — Aufgabenbedarf offen','Keine explizite Norm; ob die Aufgabe das Feld zwingend braucht, ist noch nicht beurteilt');
  return B('zu_ermitteln','Rechtsgrundlage zu ermitteln','Noch nicht juristisch ermittelt — heisst NICHT, dass keine Grundlage existiert; hier fehlt Recherche, kein Recht');
}

// ---------- sidebar (grouped by department) ----------
// the mobile drawer closes as soon as a view or a service is chosen
const closeNav=()=>{const l=document.querySelector('.layout'); if(l) l.classList.remove('nav-open');
  const b=document.querySelector('.navbtn'); if(b) b.setAttribute('aria-expanded','false');};
// Datenstand: WHEN the underlying facts were true — not only when the file was built
function datenstandText(){
  const ds=DATA.datenstand||{}, oc=ds.online_check||{}, xs=ds.xsd_sweep||{};
  const p=[];
  if(ds.dvsh_stand) p.push('DVSH-Modell '+fmtDate(ds.dvsh_stand));
  if(ds.shep_harvest) p.push('SHEP-Abzug '+fmtDate(ds.shep_harvest));
  if(oc.date) p.push(`Online-Prüfung: vollständig ${fmtDate(oc.full_date||oc.date)}${oc.full_date&&oc.date!==oc.full_date?', Nachprüfung '+fmtDate(oc.date)+' ('+pl(oc.n_recent||0,'Formular','Formulare')+')':''} — ${nf(oc.n_checked)}/${nf(oc.n_forms)} Formulare geprüft${oc.n_overdue?', '+pl(oc.n_overdue,'Wiedervorlage überfällig','Wiedervorlagen überfällig'):''}${oc.n_never?', '+nf(oc.n_never)+' nie geprüft':''}`);
  else p.push('Online-Prüfung: noch keine');
  if(xs.date) p.push(`XSD-Prüfung ${fmtDate(xs.date)} (${pl(xs.n,'Standard','Standards')} geprüft${xs.n_xsd!=null?', '+nf(xs.n_xsd)+' mit eigener XSD, '+nf(xs.n-xs.n_xsd)+' ohne':''})`);
  p.push('Gesetze: Stand je SHR-PDF');
  p.push('erstellt '+fmtDate(ds.build||DATA.generated_at||''));
  // a layer the export had to leave out (its table was missing) is said, never passed over
  if((ds.uebersprungen||[]).length) p.push('beim Export ausgelassen: '+ds.uebersprungen.join('; '));
  return p.join(' · ');
}
// the Datenstand of one Dienststelle's page: only what its readers need — the DVSH model,
// the last online check of ITS forms, the date of this page
function datenstandKurz(fms){
  const ds=DATA.datenstand||{}, p=[];
  if(ds.dvsh_stand) p.push('Dienstleistungsmodell (DVSH) '+fmtDate(ds.dvsh_stand));
  const last=(fms||[]).map(f=>f.check&&f.check.d).filter(Boolean).sort().pop();
  p.push(last?'Formulare dieser Dienststelle zuletzt online geprüft '+fmtDate(last):'Formulare dieser Dienststelle noch nie online geprüft');
  p.push('erstellt '+fmtDate(ds.build||DATA.generated_at||''));
  return p.join(' · ');
}
// citation verification levels, counted once in export_json (build_dashboard.py refuses an
// export without this key)
const ZIT=DATA.zitate;
let _navSvc=null, _navDst=null;
function renderSidebar(){
  const nForms=DATA.forms.length;
  const noForm=DATA.services.filter(x=>!(formsByService[x.id]||[]).length);
  const nEs=noForm.length, nEsDv=noForm.filter(x=>x.dvsh).length;
  // the headline figure of the start page (kopfzahlen.standard_ech): the ATOMIC data points
  // — a composite's Teilfelder replace it — that carry a citable eCH ELEMENT
  const KE=(DATA.kopfzahlen||{}).standard_ech||{}, dfN=KE.von||0, dfE=KE.wert||0;
  const ech = dfN ? ` · ${nf(dfE)}/${nf(dfN)} atomare Datenpunkte mit eCH-Element (${pctTxt(dfE,dfN)})` : '';
  const stamp=document.getElementById('stamp');
  // «ohne Formular» is the fact; whether the service is an eService is read
  // from the DVSH endpoint per service (sidebar badge, service page), never assumed
  stamp.textContent=`${pl(nForms,'Formular','Formulare')} · ${pl(nEs,'Service','Services')} ohne Formular (${nEsDv} mit DVSH-Modellierung, ${nEs-nEsDv} ohne)${ech} — erzeugt ${fmtDate(DATA.generated_at)}`;
  stamp.title='Datenstand: '+datenstandText();
  // the header chip states the LIVE count of unverified citations — a permanent
  // red «UNVERIFIED» over a corpus with zero such citations was the opposite of the data
  const w=document.getElementById('warn');
  if(ZIT.unverifiziert>0){const t=tonOf('verif','unverifiziert'); w.className='warn st-'+t;
    w.innerHTML=SW(t)+esc(`${nf(ZIT.unverifiziert)} von ${nf(ZIT.total)} Zitaten noch unverifiziert`);
    w.title='unverifiziert = noch nicht am Gesetzestext geprüft — eine Wissenslücke der Databank, kein Befund über die Verwaltung\n'+tonWords(t);}
  else {w.className='stamp';w.style.marginLeft='0';w.textContent=`Zitate: ${nf(ZIT.verifiziert)} verifiziert · ${nf(ZIT.quelle_pdf)} Quelle SHR-PDF · 0 ungeprüft`;
    w.title='Jedes Zitat der kuratierten Feld-Schicht trägt eine Verifikationsstufe; die Stufe «unverifiziert» ist definiert, kommt derzeit nicht vor';}
  const sv = document.getElementById('services'); sv.innerHTML='';
  // layout and focus look come from the stylesheet (input#svcfilter): an inline border here
  // would beat the :focus rule and leave the field without a visible keyboard focus
  const fb=el(`<input id="svcfilter" placeholder="Formular, Dienststelle oder Datenfeld suchen…" value="${esc(state.filter)}">`);
  sv.appendChild(fb);
  fb.oninput=()=>{state.filter=fb.value;(state.navmode==='formulare'?renderFormNav:renderNav)();};
  // two browse modes: by SERVICE (department tree) or by FORMULAR (flat A–Z)
  const modes=el(`<div class="navmodes">
    <button data-nm="services" class="${state.navmode==='services'?'active':''}">nach Service</button>
    <button data-nm="formulare" class="${state.navmode==='formulare'?'active':''}">nach Formular</button></div>`);
  sv.appendChild(modes);
  modes.querySelectorAll('button').forEach(b=>b.onclick=()=>{state.navmode=b.dataset.nm;renderSidebar();});
  const allr=el(`<div class="svc" style="margin-left:0;font-weight:600">▤ Alle Services · Übersicht <span class="meta">${pl(DATA.services.length,'Service','Services')}, ${pl(deptKeys().length,'Departement','Departemente')}</span></div>`);
  // the row is «current» only on the service page — on every other tab the
  // active tab button is the one current location
  if(state.service==='all'&&state.tab==='fields'){allr.classList.add('active'); allr.setAttribute('aria-current','page');}
  allr.onclick=()=>{state.service='all';state.sub='felder';state.tab='fields';closeNav();render();};
  sv.appendChild(allr);
  const nav=el('<div id="nav"></div>'); sv.appendChild(nav);
  // a service reached via search, a link or a shared URL sits inside a collapsed
  // department: open its ancestors once, when the current service changes
  if(state.service!==_navSvc){_navSvc=state.service; const sv0=svcById[state.service];
    if(sv0){state.open[deptName(sv0)]=true; state.open[deptName(sv0)+'›'+(sv0.dienststelle||'(ohne Dienststelle)').trim()]=true;}}
  const dsl=state.tab==='dienststellen'?state.sub:null;
  if(dsl!==_navDst){_navDst=dsl; const d0=dstBySlug[dsl];
    if(d0){const dk=(d0.department||'(ohne Departement)').trim(); state.open[dk]=true;}}
  if(state.navmode==='formulare') renderFormNav(); else renderNav();
  document.querySelectorAll('.tab[data-tab]').forEach(b=>{
    const on=b.dataset.tab===state.tab;
    b.classList.toggle('active', on);
    if(on) b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current');
    // a tab switch resets the per-tab sub-state: a Handlungsbedarf category or
    // a Lebenslage id carried into «Begriffe» matched nothing and rendered an empty list
    b.onclick=()=>{state.tab=b.dataset.tab;state.sub='felder';closeNav();render();};
  });
  // the sidebar's own titled chips (◇, channel) explain themselves too; its rows and
  // toggles are reachable by keyboard
  enhanceTips(sv); enhanceActs(sv);
}
// ---------- legend: «Farbe = wer als Nächstes handelt» + the Kennzeichen of this page ----------
// Drawn after the view, from what #main actually shows: the four tones always as one
// block (a tone the page does not use is faded, «hier:» says what it marks on this page),
// then only the Kennzeichen the page draws («Kennzeichen, keine Bewertung») — the data
// standard first, like everything that has an order. A page without either has no legend.
function renderLegend(){
  const main=document.getElementById('main'), leg=document.getElementById('legend'); if(!main||!leg) return;
  const has=sel=>!!main.querySelector(sel);
  const hasTxt=(sel,ch)=>[...main.querySelectorAll(sel)].some(e=>e.textContent.includes(ch));
  const unvEx=ZIT.unverifiziert>0?`Zitat unverifiziert (${nf(ZIT.unverifiziert)} Zitate)`:'';
  const svcAll=state.tab==='fields'&&state.service==='all';
  // what each tone marks on this page — the data standard first
  const TONEX={
    home: {ok:'Datenpunkt mit eCH-Element · Datenfeld mit Grundlage · Verzeichnis-Angaben erfasst',
      act:'Datenpunkt anders verlangt · Bezeichnung angleichen · Feld ohne Grundlage',
      dec:'kein eCH-Standard (eSH) oder Standard erst im Entwurf · Pflicht uneinheitlich · Aufgabenbedarf offen',
      open:'eCH-Zuordnung offen oder zu korrigieren · eCH-Standard nicht mehr in Kraft · Rechtsgrundlage noch zu ermitteln'},
    methode: {ok:'verifiziert · Quelle SHR-PDF · aufgabennotwendig',act:'ohne Grundlage',dec:'Aufgabenbedarf offen',
      open:['unverifiziert','Rechtsgrundlage zu ermitteln'].join(' · ')},
    fields: svcAll?{ok:'Datenfeld mit belegter Norm oder für die Aufgabe nötig',act:'Datenfeld ohne Grundlage',
        dec:'Aufgabenbedarf offen',open:'Rechtsgrundlage noch zu ermitteln · ⛨ Grundlage nach KDSG Art. 5 offen'}
      :{ok:'eCH-Element · Standard ohne Elementkatalog · keine Standard-Divergenz · Zitat verifiziert oder aus dem SHR-PDF · aufgabennotwendig · Formular aktuell · Rechtsmittel geklärt · Duplikat entschieden · Gesetz in der gelesenen Fassung in Kraft',
      act:'⇄ Standard-Divergenz anzugleichen · ✎ Bezeichnung angleichen oder Feld aufteilen · Feld ohne Grundlage · neuere Fassung online',
      dec:'kein eCH-Standard (eSH) · eCH-Standard erst im Entwurf · ⇄ Pflicht uneinheitlich · Begriff unter Vorbehalt · Aufgabenbedarf offen · Duplikat unentschieden',
      open:['eCH-Element offen','eCH noch nicht geprüft','eCH-Standard nicht mehr in Kraft','eCH-Zuordnung wird korrigiert (✎? Zuordnung prüfen)','Rechtsgrundlage zu ermitteln','⛨ Grundlage nach KDSG Art. 5 offen','Rechtsmittel noch ohne Prüfvermerk','Online-Prüfung fällig','neuere Fassung eines zitierten Gesetzes (die Databank liest nach)',unvEx].filter(Boolean).join(' · ')},
    register: {ok:'Zweck erfasst',act:'Felder ohne Grundlage',dec:'DSFA indiziert — Entscheid des Kantons offen',
      open:'fehlt (Zweck, Empfänger) · ⛨ Grundlage nach KDSG Art. 5 offen · noch nicht recherchiert'},
    todo: {act:'Punkte, die eine Dienststelle an ihrem Formular ändert',dec:'Punkte, die auf einen Entscheid des Kantons warten',
      open:'nicht auf dieser Seite — «Recherche der Databank»'},
    dienststellen: {ok:'Datenpunkte mit eCH-Element',act:'Massnahmen der Dienststelle',
      dec:'Entscheide des Kantons · kein eCH-Standard oder Standard erst im Entwurf',
      open:'Hausaufgaben der Databank · eCH-Zuordnung offen oder zu korrigieren, Standard nicht mehr in Kraft'},
    kanton: {dec:'alle Entscheide dieser Seite'},
    recherche: {open:'alle Punkte dieser Seite — kein Befund über die Verwaltung'},
    lebenslagen: {dec:'kein eCH-Standard',open:'eCH-Element offen · noch nicht geprüft'},
    begriffe: {ok:'einheitlicher Begriff (Vorschlag) · Rolle — in Ordnung',act:'Bezeichnung angleichen · Feld aufteilen',
      dec:'Vorschlag unter Vorbehalt',open:'eCH-Zuordnung korrigieren'},
    katalog: {ok:'Formulare voll eCH-zugeordnet',act:'Divergenz anzugleichen · Klartext statt der offiziellen Codes',dec:'Pflicht uneinheitlich'},
    rules: {ok:'Gesetz in der gelesenen Fassung in Kraft',open:'Zitat unverifiziert · neuere Fassung des Gesetzes — die Databank liest die Artikel nach'},
    datenmodell: {ok:'Gesetz in der gelesenen Fassung in Kraft',dec:'Rollenliste und Vorschlag eines Elements: der Kanton bestätigt · ohne klare Praxis legt der Kanton das Element fest',
      open:'neuere Fassung des Gesetzes — die Databank liest die zitierten Artikel nach'},
    onceonly: {dec:'Zugriff je Register und Angaben von Familienangehörigen: der Kanton entscheidet · Rollenliste: der Kanton bestätigt'},
  };
  const tx=TONEX[state.tab]||{};
  // on #gestaltung the tones speak the layer's words (DATA.gestaltung.labels: the findings of a tone
  // and what the tone adds); elsewhere the panel «Gestaltung» of a Formular (.gpanel) lights no tone
  // of the data standard — it gets a block of its own below, in the layer's words
  const gst=state.tab==='gestaltung'&&!!GEST;
  const hasOut=sel=>[...main.querySelectorAll(sel)].some(e=>!e.closest('.gpanel'));
  const drawn=t=>hasOut(`.st-${t},.t-${t}${t==='ok'?',.t-ok2':''}`);
  const T=['ok','act','dec','open'], shown=T.filter(drawn);
  const tonBlk=shown.length?`<div class="legblk"><div class="leghd">${gst?'Farbe nur bei einem Befund — er beschreibt einen Unterschied und verlangt keine Änderung':'Farbe = wer als Nächstes handelt'}</div><ul class="tleg">${
    T.map(t=>{const on=shown.includes(t);
      if(gst) return `<li${on?'':' class="zero"'}>${SW(t)}<span class="legt" title="${esc(gTonTip(t))}"><b>${esc(gTonWords(t))}</b> <span class="tw">${esc((TON[t]||{}).farbe||'')}</span><span class="legex">${esc(gTonZusatz(t))}</span></span></li>`;
      return `<li${on?'':' class="zero"'}>${SW(t)}<span class="legt" title="${esc(tonTip(t))}"><b>${esc(tonLabel(t))}</b> <span class="tw">${esc((TON[t]||{}).farbe||'')}</span>${on&&tx[t]?`<span class="legex">hier: ${esc(tx[t])}</span>`:''}</span></li>`;}).join('')}</ul></div>`:'';
  // the panel «Gestaltung» of a Formular: its tones in the layer's words, apart from «wer handelt»
  const gT=!gst&&GEST&&has('.gpanel')?T.filter(t=>has(`.gpanel .st-${t},.gpanel .t-${t}`)):[];
  const gBlk=gT.length?`<div class="legblk"><div class="leghd">Gestaltung der Formulare — Farbe nur bei einem Befund</div><ul class="tleg">${
    gT.map(t=>`<li>${SW(t)}<span class="legt" title="${esc(gTonTip(t))}"><b>${esc(gTonWords(t))}</b> <span class="legex">${esc(gTonZusatz(t))}</span></span></li>`).join('')}</ul></div>`:'';
  // Kennzeichen: [present on this page?, sample html, text] — the data standard first
  const MK=[
    [()=>has('.edt'),'<span class="edt">⟨Typ⟩</span>','Datentyp laut offiziellem eCH-XSD — in diesem Typ wird die Angabe ausgetauscht (☰: mit offizieller Codeliste)'],
    [()=>has('.eshb,.sfe.esh'),'<span class="eshb">eSH</span>','eSH-Code — Entwurf des Kantons, nie offizielles eCH'],
    [()=>has('.regc')||hasTxt('.beih','↺'),'<span class="regc">↺</span>','Once-Only: das Einwohnerregister führt diese Angabe bereits (bei einer Beilage: der Kanton könnte sie beim Register beschaffen)'],
    [()=>hasTxt('.b-sens,.pfc,.badge,th,.rstat','⛨'),'<span class="badge b-sens">⛨</span>','besonders schützenswert (KDSG Art. 2 Abs. 1 lit. d)'],
    [()=>hasTxt('.b-sens','verschlüsselt'),'<span class="badge b-sens">verschlüsselt</span>','im Tresor verschlüsselt gespeichert'],
    [()=>has('.mk-federal,.mk-cantonal,.mk-communal,.mk-interkantonal,.lawchip .mk-open'),`${jur('federal')} ${jur('cantonal')} ${jur('communal')}`,'Rechtsebene des Erlasses; «Ebene offen» (gestrichelt), wo sie nicht belegbar ist'],
    [()=>has('.b-dvsh,.b-nodv'),'<span class="badge b-dvsh">DVSH</span>','DVSH — amtliches Dienstleistungsmodell (massgeblich für Verfahren und Rechtsgrundlage, nur lesend übernommen) · SHEP — das publizierte Service-Portal · ◇ keine DVSH-Modellierung'],
    [()=>has('.hubchan'),'<span class="hubchan">PDF-Einreichung</span>','Kanal, über den das Formular eingereicht wird'],
    [()=>has('.hubsig'),'<span class="hubsig">✍</span>','Unterschrift nötig (✍) oder digitale Signatur möglich (✓)'],
    [()=>hasTxt('.badge.mk','Digitalisierung'),'<span class="badge mk">Digitalisierung</span>','Digitalisierungs-Hürden des Formulars (Unterschrift, kein Online-Kanal …) — ein Befund zum Formular, keine Farbe'],
    [()=>has('.beiob'),'<span class="beiob zwingend">zwingend</span> <span class="beiob bedingt">bedingt</span>','Beilage zwingend (durchgezogen) oder nur unter einer Bedingung (gestrichelt) verlangt'],
    [()=>has('.empchip'),'<span class="empchip">Empfänger</span>','belegter Empfänger einer Bekanntgabe (↻ = systematische Lieferpflicht)'],
    [()=>has('.pfc:not(.st-ok):not(.st-act):not(.st-dec):not(.st-open)'),'<span class="pfc">Profil</span>','Profil der Datenhandhabung: ⛨-Kategorie, Spezialnormen, Aufbewahrung'],
    [()=>has('.esvc'),'<span class="esvc">ohne Formular</span>','Service ohne Formular in der Databank, mit seinem Kanal laut DVSH (eService, E-Mail, vor Ort …)'],
    [()=>hasTxt('.badge.mk','mehrere Entscheide'),'<span class="badge mk">mehrere Entscheide</span>','Der Service hat mehrere Formulare mit je eigenem Entscheid'],
    [()=>hasTxt('.badge.mk','aus anderen Formularen'),'<span class="badge mk">aus anderen Formularen</span>','Herkunft des Vorschlags: der Begriff stammt aus anderen Formularen des Kantons (nie erfunden)'],
    [()=>hasTxt('.badge.mk','Einwilligung'),'<span class="badge mk">Einwilligung</span>','Erhebungsgrundlage: Einwilligung der Person'],
    [()=>has('.flowsvg,.mkline'),'<span class="mkline"></span>','systematisch — regelmässige Meldung von Gesetzes wegen'],
    [()=>has('.flowsvg,.mkline.dash'),'<span class="mkline dash"></span>','auf Anfrage — Amtshilfe im Einzelfall'],
    [()=>has('.llnum'),'<span class="llnum">①</span>','Nummer des Services in der Tabelle der Themengruppe'],
    [()=>has('.gdist'),'<span class="gdbx"></span>','gemessene Werte (Gestaltung) — grau und ohne Bewertung; die Farbe steht nur bei einem Befund'],
    [()=>has('.gurt .badge.mk,.gfr .badge.mk'),'<span class="badge mk">Hinweis</span>','Gestaltung: «Hinweis», «betroffen», «entfällt» — eine Feststellung ohne Farbe. Auf einem Formular steht auch «keine klare Praxis» ohne Farbe: Der Kanton legt einmal je Merkmal fest'],
  ];
  const mks=MK.filter(([t])=>t());
  const mkBlk=mks.length?`<div class="legblk"><div class="leghd">Kennzeichen, keine Bewertung</div><ul class="tleg mkl">${
    mks.map(([,s,l])=>`<li>${s}<span>${esc(l)}</span></li>`).join('')}</ul></div>`:'';
  const lh=document.getElementById('legendhd'); if(lh) lh.style.display=(tonBlk||gBlk||mkBlk)?'':'none';
  const html=tonBlk+gBlk+mkBlk;
  // redrawn only when it changes (the observer calls this after every change in #main)
  if(leg._raw!==html){leg._raw=html; leg.innerHTML=html; enhanceTips(leg);}
}

// flat A–Z Formular navigation: one row per Formular, click = Formular-Ansicht
const formNavIdx=DATA.forms.map(f=>{
  const svc=svcById[f.service_id]||{};
  // whose Formular it is: form.dienststelle, answered once in export_json (dstOf below reads the same key)
  return {fid:f.id, sid:f.service_id, t:f.title, o:f.dienststelle||'',
          k:(f.title+' '+(svc.name||'')+' '+(svc.name_alt||'')+' '+(f.dienststelle||'')).toLowerCase()};
}).sort((a,b)=>a.t.localeCompare(b.t,'de'));
function renderFormNav(){
  const f=state.filter.toLowerCase(); const nav=document.getElementById('nav'); if(!nav)return;
  const hits=formNavIdx.filter(x=>!f||x.k.includes(f)||(f.length>=3&&(fieldIdx[x.sid]||'').includes(f)));
  nav.innerHTML=`<div class="muted small" style="margin:2px 0 6px">${pl(hits.length,'Formular','Formulare')} A–Z — Klick öffnet die Formular-Ansicht</div>`+
    (hits.map(x=>{const on=state.tab==='fields'&&(String(state.sub).split('~')[0]==='form-'+x.fid||(state.sub==='felder'&&String(x.sid)===String(state.service)));
      return `<div class="svc fnav ${on?'active':''}"${on?' aria-current="page"':''} data-fid="${x.fid}" data-sid="${x.sid}">
      <a class="svname" href="#fields/${encodeURIComponent(x.sid)}/form-${encodeURIComponent(x.fid)}" data-rowlink title="${esc(x.t)} — ${esc(x.o)}">${esc(x.t)}</a>
      <span class="meta">${esc(x.o)}</span></div>`;}).join('')||'<div class="nores small">keine Treffer</div>');
  nav.querySelectorAll('.fnav').forEach(e=>e.onclick=()=>{
    state.service=e.dataset.sid;state.tab='fields';state.sub='form-'+e.dataset.fid;closeNav();render();});
  navLinks(nav);
}
// a sidebar entry's name is a real link (keyboard, copy, new tab); a plain click routes
// like the whole row, the ◇ and channel chips beside it explain themselves
function navLinks(nav){
  nav.querySelectorAll('a.svname').forEach(a=>a.onclick=e=>{e.stopPropagation();
    if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button) return;
    e.preventDefault(); const r=a.closest('.svc'); if(r&&r.onclick) r.onclick();});
  enhanceTips(nav); enhanceActs(nav);
}
// search also finds services by their DATA FIELD names ('AHV-Nummer' -> forms asking it)
const fieldIdx={};
DATA.forms.forEach(fm=>{
  const t=(fm.data_fields||[]).map(d=>{
    const ss=(d.subfields||[]).filter(s=>s&&typeof s==='object'&&s.name).map(s=>s.name);
    return d.name+' '+ss.join(' ');}).join(' ').toLowerCase();
  fieldIdx[fm.service_id]=(fieldIdx[fm.service_id]||'')+' '+t;
});
function renderNav(){
  const f=state.filter.toLowerCase(); const nav=document.getElementById('nav'); if(!nav)return;
  let h='';
  deptKeys().forEach(d=>{
    const offices=deptTree[d];
    let svcMatch=0, deptHTML='';
    Object.keys(offices).sort().forEach(o=>{
      const svcs=offices[o].filter(s=>!f || (s.name+' '+(s.name_alt||'')+' '+o+' '+d).toLowerCase().includes(f)
        || (f.length>=3 && (fieldIdx[s.id]||'').includes(f)));
      if(!svcs.length) return; svcMatch+=svcs.length;
      const offOpen = f || state.open[d+'›'+o];
      const du=dstByName[o];
      const offOn=du&&state.tab==='dienststellen'&&state.sub===du.slug;
      deptHTML+=`<div class="office ${offOpen?'':'collapsed'}"><div class="offhd${offOn?' active':''}"${offOn?' aria-current="page"':''}>`+
        `<span class="offtg" role="button" tabindex="0" aria-expanded="${offOpen?'true':'false'}" data-o="${esc(d+'›'+o)}"><span class="tg" aria-hidden="true">${offOpen?'▾':'▸'}</span>${esc(o)}</span>`+
        (du?`<a class="offlink" href="#dienststellen/all/${esc(du.slug)}" data-slug="${esc(du.slug)}" title="Seite der Dienststelle «${esc(o)}»: ihre Massnahmen, ihr Datenstandard, die Entscheide des Kantons, die offenen Punkte">Seite ›</a>`:'')+
        `<span class="ct">${svcs.length}</span></div>`+
        svcs.map(s=>{const on=String(s.id)===String(state.service)&&state.tab==='fields'; return `<div class="svc ${on?'active':''}"${on?' aria-current="page"':''} data-sid="${s.id}">`+
          `${s.dvsh?'':'<span class="nodv" title="keine DVSH-Modellierung in der Databank">◇</span>'}<a class="svname" href="#fields/${encodeURIComponent(s.id)}" data-rowlink title="${esc(s.name)}${s.dienststelle?' — '+esc(s.dienststelle):''}">${esc(s.name)}</a>`+
          `${(formsByService[s.id]||[]).length?'':noFormBadge(s)}</div>`;}).join('')+`</div>`;
    });
    if(!svcMatch) return;
    const open = f || state.open[d];
    h+=`<div class="dept ${open?'':'collapsed'}"><div class="dephd" data-d="${esc(d)}" role="button" aria-expanded="${open?'true':'false'}">`+
       `<span class="tg">${open?'▾':'▸'}</span>${esc(d)}<span class="ct">${svcMatch}</span></div>${deptHTML}</div>`;
  });
  nav.innerHTML=h || '<div class="nores small">keine Treffer</div>';
  // a toggle redraws the tree: the keyboard focus stays on the toggle
  const refocus=(sel,k,v)=>{const n=[...nav.querySelectorAll(sel)].find(x=>x.dataset[k]===v); if(n) n.focus({preventScroll:true});};
  nav.querySelectorAll('.dephd').forEach(e=>e.onclick=()=>{const d=e.dataset.d, f=document.activeElement===e;
    state.open[d]=!state.open[d];renderNav(); if(f) refocus('.dephd','d',d);});
  nav.querySelectorAll('.offtg').forEach(e=>{const tog=()=>{const k=e.dataset.o, f=document.activeElement===e;
      state.open[k]=!state.open[k];renderNav(); if(f) refocus('.offtg','o',k);};
    e.onclick=tog; e.onkeydown=ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault(); tog();}};});
  nav.querySelectorAll('.offlink[data-slug]').forEach(a=>a.onclick=e=>{
    e.stopPropagation();
    if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button) return;
    e.preventDefault(); state.tab='dienststellen'; state.service='all'; state.sub=a.dataset.slug; closeNav(); render();});
  // a form click ALWAYS opens the form page — on corpus tabs a mere selection
  // change would be invisible and read as a broken click
  nav.querySelectorAll('.svc[data-sid]').forEach(e=>e.onclick=()=>{
    state.service=e.dataset.sid;state.tab='fields';state.sub='felder';closeNav();render();});
  navLinks(nav);
}
// a service without a Formular in the databank: «eService» ONLY when the DVSH
// endpoint says eFormular; otherwise the badge names the DVSH channel (E-Mail,
// Telefon, externer Link, vor Ort) or the absence of a DVSH model — never a
// guessed online channel
function noFormBadge(s){
  const ep=s.dvsh?s.dvsh.endpoint_typ:null;
  if(s.dvsh&&ep==='eformular') return '<span class="esvc" title="laut DVSH ein eFormular (Online-Service) — kein herunterladbares Formular in der Databank">eService</span>';
  const tip=s.dvsh?('kein Formular in der Databank — laut DVSH Kanal: '+(ep?lab(ENDPOINT_DE,ep):'kein DVSH-Kanal hinterlegt'))
                  :'kein Formular in der Databank und keine DVSH-Modellierung';
  return `<span class="esvc" title="${esc(tip)}">ohne Formular</span>`;
}

// ---------- PRIMARY: fields & legal basis ----------
// consistent page header: the title, ONE visible sentence, and the details —
// what the page shows, where its data comes from, how to read it — folded into
// «Mehr zu dieser Seite», so a reader who wants the page is not held up by its method
function pageHead(title, kurz, was, quelle, lesen){
  const more=[[was,'Was zeigt diese Seite'],[quelle,'Datenherkunft'],[lesen,'Lesehinweis']]
    .filter(([t])=>t&&t!=='—').map(([t,l])=>`<div><span class="phl">${l}</span>${t}</div>`).join('');
  return `<h3 class="view" tabindex="-1">${title}</h3>
  <div class="pagehead"><p class="phkurz">${kurz}</p>${more?`<details class="phmore"><summary>Mehr zu dieser Seite</summary>${more}</details>`:''}</div>`;
}
// ---------- tones: the colour says who acts next (DATA.labels.ton — one source) ----------
// ok = geklärt · act = Dienststelle handelt · dec = Kanton entscheidet · open = Databank
// recherchiert (the databank's own homework, never a finding about the administration)
const TON=LAB.ton||{};
const tonLabel=t=>(TON[t]&&TON[t].label)||('⟨'+t+'⟩');
const tonTip=t=>(TON[t]&&TON[t].bedeutung)||'';
// in-page links carry a real href (copyable, opens in a new tab) and change the
// state like the sidebar does
function wireGo(root){
  root.querySelectorAll('a[data-go]').forEach(a=>a.onclick=e=>{
    if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button) return;
    e.preventDefault(); state.tab=a.dataset.go; state.service='all'; state.sub=a.dataset.sub||'felder';
    render();});
  // links into a service or a Formular (#fields/<id>[/form-<id>]) carry the whole
  // address in their href and are routed the way the hash itself would be
  root.querySelectorAll('a[data-nav]').forEach(a=>a.onclick=e=>{
    if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button) return;
    e.preventDefault(); goHref(a.getAttribute('href'));});
}
function goHref(h){
  const p=String(h||'').replace(/^#/,'').split('/');
  state.tab=p[0]||'home'; state.service=state.tab==='fields'?(p[1]||'all'):'all'; state.sub=p[2]||'felder';
  closeNav(); render();
}
// tab and sub are escaped here (a slug or a key of the data); txt is html the caller escaped
const goLink=(tab,sub,txt,cls)=>`<a class="${cls||'kzlink'}" href="#${esc(tab)}${sub?'/all/'+esc(sub):''}" data-go="${esc(tab)}"${sub?` data-sub="${esc(sub)}"`:''}>${txt}</a>`;
const svcLink=(sid,txt,cls)=>`<a class="${cls||'dlink'}" href="#fields/${encodeURIComponent(sid)}" data-nav="1">${txt}</a>`;
// sec 'div' opens the Formular-Ansicht at its block «Standard-Divergenzen» (#…/form-<id>~div)
const formLink=(sid,fid,txt,cls,sec)=>`<a class="${cls||'dlink'}" href="#fields/${encodeURIComponent(sid)}/form-${encodeURIComponent(fid)}${sec?'~'+sec:''}" data-nav="1">${txt}</a>`;
// the categories whose details sit in that block
const DIV_SEC=k=>(k==='divergenz'||k==='begriff'||k==='divergenz_offen')?'div':'';
// an element code («eCH-0129·typeOfConstructionProject», escaped) may break after its standard
const codeBrk=s=>esc(s).replace(/·/g,'·<wbr>');
// a long text in a table cell: the first `n` characters, the whole text in the title
const clip=(s,n)=>{const t=String(s||''); return t.length>n?`<span title="${esc(t)}">${esc(t.slice(0,n-1).trimEnd())} …</span>`:esc(t);};
// a share in words — ONE precision wherever a share stands (headline, table, briefing,
// trend): one decimal. It never rounds a gap away: «100.0 %» only when nothing is missing
const pctTxt=(a,b)=>{if(!b) return '—'; const p=Math.round(1000*a/b)/10;
  return a<b&&p>=100?'> 99.9 %':(a>0&&p<=0?'< 0.1 %':nf1(p)+' %');};

// ---------- worklists: who acts next (tone), priority tier, the Dienststellen pages ----------
// tone and tier of a point are computed once in export_json (item.ton, item.stufe);
// the category mapping from DATA.labels is only the fallback for a point without them
const AKTION=LAB.aktion||{};
const CAT_ORDER=(()=>{const o=(LAB.cat_order||[]).slice(); TODO_CATS.forEach(c=>{if(!o.includes(c[0])) o.push(c[0]);}); return o;})();
const STUFEN=(LAB.stufen||[]).map(s=>({n:Number(s[0]),name:String(s[1]||''),text:String(s[2]||'')}));
const LAST_STUFE=STUFEN.length?STUFEN[STUFEN.length-1].n:4;
const stufeLabel=n=>{const s=STUFEN.find(x=>x.n===Number(n)); return s?`Stufe ${s.n} — ${s.name}`:`Stufe ⟨${n}⟩`;};
// a category or status without a tone is not settled: grey, never green; the tone class
// of a category is DATA.labels.todo_cats[*][2] (st-act · st-dec · st-open)
const catTon=k=>{const x=/^st-(ok|act|dec|open)$/.exec(String(todoCat(k)[2]||'')); return x?x[1]:'open';};
const catStufe=k=>Number((LAB.stufe_of_cat||{})[k]||LAST_STUFE);
const itemTon=i=>i.ton||catTon(i.cat);
const itemStufe=i=>Number(i.stufe||catStufe(i.cat));
const catRank=k=>{const i=CAT_ORDER.indexOf(k); return i<0?999:i;};
const byPrio=(a,b)=>itemStufe(a)-itemStufe(b)||catRank(a.cat)-catRank(b.cat)||b.n-a.n;
// what ONE point of a category counts: DATA.labels.einheit[cat] = [singular, plural]; a
// category missing there is about the whole form and counts Formulare
const EINHEIT=LAB.einheit||{};
const formCat=k=>!EINHEIT[k];
const catUnitOf=k=>{const u=EINHEIT[k]; return Array.isArray(u)&&u.length>1?u:['Formular','Formulare'];};
const catWord=(k,n)=>{const u=catUnitOf(k); return plw(n,u[0],u[1]);};
const catUnit=(k,n)=>`${nf(n)} ${catWord(k,n)}`;
// «· 76 Datenpunkte» for an explanation — unless its detail already begins with it
const unitTip=i=>{const u=catUnit(i.cat,i.n); return String(i.detail||'').startsWith(u)?'':' · '+u;};
// the open points of every category over all Formulare, counted once in export_json
// (kopfzahlen.kategorien[cat] = {n: points, formulare: forms concerned})
const KAT=(DATA.kopfzahlen||{}).kategorien||{};
const CAT_N=Object.fromEntries(Object.entries(KAT).map(([k,v])=>[k,v.n]));
// a point as a chip: swatch + label (+ count), tinted in its tone; label arrives escaped.
// The count stands on the chip whenever the category counts something (also when it is 1);
// a chip without a number is about the whole Formular (chipN)
const chipN=i=>formCat(i.cat)?null:i.n;
const tonChip=(t,label,n,tip,attrs)=>`<span class="tchip badge st-${t}"${attrs||''} title="${esc(tip||tonLabel(t))}"><i class="sw t-${t}"></i>${label}${n!=null?` <b>${nf(n)}</b>`:''}</span>`;
// three counts side by side — red Dienststelle, amber Kanton, grey Databank; the tone is
// also said in words for screen readers and in the title
function tonNums(o, ts){
  return `<span class="tnum">${(ts||['act','dec','open']).map(t=>{const n=(o&&o[t])||0;
    return `<span${n?'':' class="z"'} title="${esc(tonLabel(t))}: ${nf(n)}"><i class="sw t-${t}"></i><span class="vh">${esc(tonLabel(t))}: </span>${nf(n)}</span>`;}).join('')}</span>`;
}
// The eCH states of a set of data points arrive from the export twice: every state with its
// number (standard.ech / kopfzahlen.standard_ech.ech) and the four parts a bar draws
// (…ech_ton: ok · ok2 = settled at standard level, light green · dec · open). The grey part
// holds every state the databank still works on — an element it assigned although the label
// means another Angabe (zuordnung_falsch) included; a bar draws ech_ton as it is.
// The grey part in words — every state it holds, each with its number
function stdOpenLabel(ech){
  const E=ech||{}, alt=Number(E.standard_alt)||0, rest=(Number(E.element_offen)||0)+(Number(E.ungeprueft)||0),
    zf=Number(E.zuordnung_falsch)||0;
  const parts=[rest&&`eCH-Zuordnung noch offen (${nf(rest)})`, zf&&`eCH-Zuordnung wird von der Databank korrigiert (${nf(zf)})`,
    alt&&`Standard nicht mehr in Kraft — sistiert, aufgehoben oder abgelöst (${nf(alt)})`].filter(Boolean);
  if(!parts.length) return 'eCH-Zuordnung noch offen';
  return parts.join(' · ')+' — die Databank ordnet zu';
}
// the green part in words: the headline counts every point that carries an element, the green
// part only those whose mapping stands — where the two differ, the label says by how many
const echOkLabel=zf=>zf?`mit eCH-Element (ohne die ${nf(zf)}, deren Zuordnung die Databank korrigiert)`:'mit eCH-Element';
// the amber part: exactly the points of the category «Kein geltender eCH-Standard»
const KS_LABEL=()=>`${esc(todoCat('kein_standard')[1])} (keiner vorhanden oder erst im Entwurf): der Kanton legt fest (eSH)`;
// the target of the data standard — the same line on the start page and on every Dienststelle page
const ZIEL_STD='Ziel: jede Angabe mit Standard, damit sie ausgetauscht werden kann';
// the title of every eCH standard the field layer uses (visible where a code alone says little)
const ECH_TITEL=(()=>{const t={}; DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>[d,...(d.subfields||[])].forEach(u=>{
  const e=u&&typeof u==='object'&&u.ech; if(e&&e.standard&&e.standard_titel&&!t[e.standard]) t[e.standard]=e.standard_titel;}))); return t;})();
// the unit «Feld» of DATA.labels.einheit, as the page names it elsewhere
const UNIT_WORD=w=>w==='Felder'?'Datenfelder':w==='Feld'?'Datenfeld':w;
// the naming verdicts of the whole canton, one per Datenpunkt with an eCH element
// (kopfzahlen.standard_benannt, counted in export_json): teile.variante = rename, .aufteilen =
// split — both «Bezeichnung angleichen oder Feld aufteilen» —, .zuordnung = a wrong eCH mapping
// the databank corrects, .rest = no deviation recorded; formulare_teile = forms concerned
const BEN=(DATA.kopfzahlen||{}).standard_benannt||{}, BEN_T=BEN.teile||{}, BEN_F=BEN.formulare_teile||{};
// «Kein geltender eCH-Standard» (kopfzahlen.kein_standard, the amber part of the data
// standard) by the decision the canton faces: teile.esh = an eSH draft exists · .ohne =
// neither eCH nor eSH · .ech_entwurf = an eCH standard only in the works; formulare = forms
// concerned, codes = Datenpunkte per draft. The eSH catalogue's own counts (esh_katalog[]
// .n_live) come from the export as well, on the atomic unit like every other figure
const KS=(DATA.kopfzahlen||{}).kein_standard||{}, KS_T=KS.teile||{}, KS_F=KS.formulare||{}, KS_C=KS.codes||{};
// «Pflicht uneinheitlich» per datum (standard · element): the unit the canton decides on. A
// Datenpunkt that is also demanded differently (red) on the same form counts there, as in
// form.handlungsbedarf — so the totals come back to the category's Datenpunkte
function pflichtUneinheitlichAgg(){
  const A={};
  DATA.forms.forEach(f=>{const L=((f.standard_divergenzen||{}).angleichen)||[], key=i=>String(i.feld)+'\u0001'+String(i.teilfeld||'');
    const red=new Set(L.filter(i=>i.art!=='pflicht_uneinheitlich').map(key)), seen=new Set();
    L.forEach(i=>{if(i.art!=='pflicht_uneinheitlich'||red.has(key(i))||seen.has(key(i))) return; seen.add(key(i));
      const el=`${i.standard}·${i.element}`, x=A[el]=A[el]||{el,forms:new Set(),n:0,req:0,opt:0,labels:{},akt:new Set()};
      x.forms.add(f); x.n++; if(i.hier==='Pflicht') x.req++; else x.opt++;
      const lb=i.teilfeld||i.feld; x.labels[lb]=(x.labels[lb]||0)+1; if(i.aktion) x.akt.add(i.aktion);});});
  return Object.values(A).map(x=>Object.assign(x,{label:Object.entries(x.labels).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'de'))[0][0]}))
    .sort((a,b)=>b.forms.size-a.forms.size||b.n-a.n||a.el.localeCompare(b.el));
}
// the Massnahmen of a Dienststelle (dienststellen_uebersicht[].massnahmen, built in
// export_json): one entry per red category, summed over all its forms, in priority order
// (tier, then DATA.labels.cat_order) — n points in `formulare` forms, the three largest
// forms (gross), the imperative (aktion) and, for divergences, their kinds (mix)
const massnahmenOf=d=>(d.massnahmen||[]).map(g=>Object.assign({mix:{}},g,
  {gross:(g.gross||[]).map(x=>({f:formById[x.form_id],n:x.n})).filter(x=>x.f)}));
// a Massnahme in a few words, for the overview table: the name of its category — except where
// only value lists differ, which changes nothing on the form: then the export's own wording
const mzKurz=g=>AKTION.divergenz_codeliste&&g.aktion===AKTION.divergenz_codeliste?g.aktion:todoCat(g.cat)[1];
// how a Massnahme names a Formular: by its service (the name a reader knows), the form's
// own title only where it says something else
const sameName=(a,b)=>String(a||'').toLowerCase().replace(/[^a-z0-9äöüéèà]+/g,'')===String(b||'').toLowerCase().replace(/[^a-z0-9äöüéèà]+/g,'');
function mzFormRef(f, cat, cls){
  const s=svcById[f.service_id], nm=s?s.name:f.title;
  return `«${formLink(f.service_id,f.id,esc(nm),cls||'dlink lt',DIV_SEC(cat))}»${s&&!sameName(f.title,s.name)?` <span class="muted mzft">(Formular «${esc(f.title)}»)</span>`:''}`;
}
// the kinds of a divergence Massnahme, in words
function mzMix(g){
  if(g.cat!=='divergenz') return '';
  const W={pflicht:'Pflicht ↔ optional',format:'andere Form',codeliste:'eigene Werte statt der eCH-Codes'};
  const p=['pflicht','format','codeliste'].filter(k=>g.mix[k]).map(k=>`${nf(g.mix[k])} ${W[k]}`);
  if(!p.length) return '';
  return `<div class="mzmix">Arten der Abweichung (ein Datenpunkt kann mehrere haben): ${p.join(' · ')}${g.mix.codeliste?' — Wertelisten nur beim Austausch auf die eCH-Codes abbilden; der Klartext im Formular darf bleiben':''}</div>`;
}
function miniBar(g, aria){
  const tot=Object.values(g).reduce((a,b)=>a+b,0); if(!tot) return '';
  return `<span class="minibar" role="img" aria-label="${esc(aria)}">${['ok','ok2','dec','open'].filter(t=>g[t]).map(t=>`<i class="t-${t}" style="flex-grow:${g[t]}"></i>`).join('')}</span>`;
}
const tonKeyLine=()=>`<div class="tonkey"><span>Die Farbe sagt, wer als Nächstes handelt:</span>${
  [['ok','grün','geklärt'],['act','rot','Dienststelle'],['dec','amber','Kanton'],['open','grau','Databank']].map(([t,f,w])=>
    `<span class="tk" title="${esc(tonLabel(t)+' — '+tonTip(t))}"><i class="sw t-${t}"></i>${esc((TON[t]&&TON[t].farbe)||f)} ${w}</span>`).join('<span class="sep">·</span>')}</div>`;
// the Dienststellen (DATA.dienststellen_uebersicht, computed once in export_json)
const DST=DATA.dienststellen_uebersicht||[];
const dstBySlug=Object.fromEntries(DST.map(d=>[d.slug,d]));
const dstByName=Object.fromEntries(DST.map(d=>[d.name,d]));
const dstLink=(name,cls)=>{const d=dstByName[name]; return d?goLink('dienststellen',d.slug,esc(name),cls||'dlink'):esc(name);};
const formById={}; DATA.forms.forEach(f=>{formById[f.id]=f;});
// whose Formular it is (form.dienststelle, answered once in export_json)
const dstOf=f=>f.dienststelle;
// ---------- a contact: ONE rendering for every page ----------
// «Kontakt (laut DVSH): Adresse · Tel. … · E-Mail …» — on the briefing, the service page, the
// Handlungsbedarf and in search results. The parts are those of the DVSH model
// (dienststellen_uebersicht[].kontakt) and are shown exactly as stored — a number or an
// address is never rewritten; only the target of a telephone link is put into the
// international form (tel:+41…; a «(0)» in «+41 (0)52 …» is dropped). Address first, then
// telephone, then e-mail, each named — the words are labels.KONTAKT (DATA.labels.kontakt),
// the same the guided forms and the dossiers read.
// opt.wer (HTML) names the Dienststelle where the page's heading does not.
const kontaktOf=name=>(dstByName[name]||{}).kontakt||[];
const telHref=p=>{let d=String(p).replace(/\(0\)/g,'').replace(/[^\d+]/g,''); if(/^00/.test(d)) d='+'+d.slice(2); else if(/^0/.test(d)) d='+41'+d.slice(1); return 'tel:'+d;};
function kontaktHtml(k, opt){
  const o=opt||{}, adr=[], tel=[], mail=[], KL=LAB.kontakt;
  (k||[]).forEach(x=>String(x||'').split(' · ').forEach(p=>{p=p.trim(); if(!p) return;
    if(/^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i.test(p)) mail.push(`<span class="kp">${esc(KL.mail)} <a class="inl" href="mailto:${esc(p)}">${esc(p)}</a></span>`);
    else if(/^\+?[\d\s()\/.-]+$/.test(p)&&(p.match(/\d/g)||[]).length>=9) tel.push(`<span class="kp">${esc(KL.tel)} <a class="inl" href="${esc(telHref(p))}">${esc(p)}</a></span>`);
    else adr.push(esc(p));}));
  const parts=[...adr,...tel,...mail];
  return `<span class="kontakt"><span class="klbl">${esc(KL.label)}<span class="kc">:</span></span> <span class="kval">${
    [o.wer,parts.length?parts.join(' · '):`<span class="muted">${esc(KL.leer)}</span>`].filter(Boolean).join(parts.length?' · ':' — ')}</span></span>`;
}
// every category of one tone: its points and forms as the export counted them
// (kopfzahlen.kategorien), and — grouped here — per Dienststelle the forms behind it
function aggByCat(ton){
  const A={};
  DATA.forms.forEach(f=>todoItems(f).forEach(i=>{
    if(itemTon(i)!==ton) return;
    const a=A[i.cat]=A[i.cat]||{n:(KAT[i.cat]||{}).n||0,forms:(KAT[i.cat]||{}).formulare||0,byDst:{}};
    const dn=dstOf(f), b=a.byDst[dn]=a.byDst[dn]||{n:0,rows:[]};
    b.n+=i.n; b.rows.push({f,i});
    // a duplicate pair is counted on one of its two forms (export_json); the other form and
    // its Dienststelle are just as affected — listed as the partner, without a second count
    if(i.cat==='dup') (f.similar||[]).filter(s=>!s.verdict&&f.id<s.form_id).forEach(s=>{
      const p=formById[s.form_id]; if(!p) return;
      const pd=dstOf(p), pb=a.byDst[pd]=a.byDst[pd]||{n:0,rows:[]};
      pb.rows.push({f:p,i:{cat:'dup',n:0,partner:1,detail:`Partner von «${f.title}» (${dstOf(f)}) — dort gezählt`}});});}));
  return A;
}
// one category as a card: what it means, what is to be done, and — folded — where it occurs
function catBlock(k, a, verb, open, extra, headPre){
  const c=todoCat(k), t=catTon(k), perForm=!formCat(k);
  const dsts=Object.entries(a.byDst).sort((x,y)=>y[1].n-x[1].n||x[0].localeCompare(y[0],'de'));
  const rows=dsts.map(([dn,b])=>`<tr class="dgrp"><td colspan="2">${dstLink(dn)}</td><td class="num">${b.n?nf(b.n):'—'}</td></tr>`
    +b.rows.sort((x,y)=>y.i.n-x.i.n||String(x.f.title).localeCompare(String(y.f.title),'de')).map(({f,i})=>
      `<tr><td>${formLink(f.service_id,f.id,esc(f.title),'',DIV_SEC(k))}</td><td class="clipd">${clip(i.detail,220)}</td><td class="num">${perForm&&!i.partner?nf(i.n):''}</td></tr>`).join('')).join('');
  const size=k==='dup'?`<b>${catUnit(k,a.n)}</b> (${pl(a.forms,'Formular','Formulare')})`
    :`<b>${catUnit(k,a.n)}</b>${formCat(k)?'':' in '+pl(a.forms,'Formular','Formularen')}`;
  return `<div class="card catblk" id="cat-${esc(k)}">
    <div class="cathd">${tonChip(t,esc(c[1]),null,tonLabel(t)+' · '+stufeLabel(catStufe(k)))}<span class="catn">${headPre?headPre+' (':''}${size} bei ${pl(dsts.length,'Dienststelle','Dienststellen')}${headPre?')':''}</span></div>
    <div class="catx">${esc(c[4])}</div>
    ${AKTION[k]?`<div class="catx"><span class="hsl">${verb}</span>${esc(AKTION[k])}</div>`:''}${extra||''}
    <details class="catdet"${open?' open':''}><summary>Betroffene Dienststellen und Formulare (${nf(dsts.length)})</summary>
      <div class="tscroll"><table class="ft"><thead><tr><th>Formular</th><th>Detail</th><th class="num">${esc(catUnitOf(k)[1])}</th></tr></thead><tbody>${rows}</tbody></table></div></details></div>`;
}
// the categories of one tone, grouped under their priority tier (DATA.labels.stufen, cat_order);
// opt.stufen limits the tiers, opt.extra[cat] adds a body to that category's card
function catSections(ton, verb, focus, opt){
  const o=opt||{}, A=aggByCat(ton);
  return STUFEN.filter(s=>!o.stufen||o.stufen.includes(s.n)).map(s=>{
    const ks=CAT_ORDER.filter(k=>A[k]&&catStufe(k)===s.n);
    if(!ks.length) return '';
    const n=ks.reduce((x,k)=>x+A[k].n,0);
    return `<div class="stufehd">${esc(stufeLabel(s.n))} · ${pl(n,'Punkt','Punkte')}</div><p class="stufetx">${esc(s.text)}</p>`
      +ks.map(k=>catBlock(k,A[k],verb,focus===k,(o.extra||{})[k],(o.head||{})[k])).join('');}).join('');
}
// a category named in the URL (#kanton/all/<cat>): open its card and bring it into view —
// after render() has put the new page at its top, hence the timeout
function focusCat(m, k){
  if(!k||comingBack()) return;
  setTimeout(()=>{const t=document.getElementById('cat-'+k); if(!t||!m.contains(t)) return;
    t.scrollIntoView({behavior:MOTION}); focusIn(t); t.classList.add('flash'); setTimeout(()=>t.classList.remove('flash'),1600);},0);
}
// segmented bar: one segment per part, widths proportional, a 2px surface gap
// between them; every part is also a legend row with its number and the tone in
// words, so no statement rests on colour alone. t: ok | ok2 | act | dec | open | rest
function tonBar(parts, aria){
  const tot=parts.reduce((a,p)=>a+(p.n||0),0);
  const tw=p=>p.t==='rest'||p.bare?'':` <span class="tw">· ${esc(p.t==='ok2'?tonLabel('ok')+' (Standard-Ebene)':tonLabel(p.t))}</span>`;
  const tip=p=>{const d=document.createElement('div'); d.innerHTML=p.label;
    return `${d.textContent}: ${nf(p.n)} (${nf1(tot?100*p.n/tot:0)} %)${p.t==='rest'?'':' '+tonWords(p.t==='ok2'?'ok':p.t)}`;};
  return `<div class="tbar" role="img" aria-label="${esc(aria)}">${parts.filter(p=>p.n>0).map(p=>
      `<i class="t-${p.t}" style="flex-grow:${p.n}" data-notip></i>`).join('')}</div>
    <ul class="tleg">${parts.map(p=>`<li${p.n?'':' class="zero"'}${p.n?` title="${esc(tip(p))}"`:''}><i class="sw t-${p.t}"></i><b>${nf(p.n)}</b><span>${p.label}${tw(p)}${p.link?' '+p.link:''}</span></li>`).join('')}</ul>`;
}
// ---------- Verlauf: are we getting better? (DATA.verlauf, one entry per day) ----------
const VERLAUF=(DATA.verlauf||[]).filter(e=>e&&e.datum).slice().sort((a,b)=>String(a.datum).localeCompare(String(b.datum)));
const isGit=e=>/^git/.test(String(e.quelle||''));
const vDay=e=>Date.parse(String(e.datum).slice(0,10)+'T00:00:00Z');
// the notes of every stand after `from` up to `to` — a jump is explained where it is shown
const notesBetween=(from,to)=>VERLAUF.filter(e=>e.bemerkung&&e.datum>from&&e.datum<=to);
// trend of one figure: compared with the LAST EARLIER entry that has it (a figure not
// yet recorded in a stand is None there, never 0); get(e) -> {n, von} | null, von
// null = an absolute count; the notes in between always stand beside a trend that
// moved, otherwise a correction reads as a setback (an unchanged figure has no jump
// to explain, so a note about another figure does not land on it); unit: a sentence
// naming the series' unit where it differs from the card's headline
// on the start page a note stands in full under the FIRST card where its figure moved; a later card
// names it by its number and the card that carries it (_bemSeen, reset by viewHome) — the same note
// three times would push the doors far down
let _bemSeen=null;
const bemNr=e=>VERLAUF.filter(x=>x.bemerkung).indexOf(e)+1;
function trendLine(get, what, unit, card){
  const L=VERLAUF.map(e=>({e,r:get(e)})).filter(x=>x.r&&x.r.n!=null);
  if(!L.length) return '';
  const c=L[L.length-1], p=L[L.length-2];
  if(!p) return `<div class="kztrend">Verlauf: erster erfasster Stand am ${fmtDate(c.e.datum)} — noch kein Vergleich möglich.</div>`;
  let d, cnt;
  if(c.r.von&&p.r.von){
    const dp=100*c.r.n/c.r.von-100*p.r.n/p.r.von;
    d=Math.abs(dp)<0.05?'unverändert':(dp>0?'+':'−')+nf1(Math.abs(dp))+' Prozentpunkte';
    cnt=c.r.n===p.r.n&&c.r.von===p.r.von?`${nf(c.r.n)} von ${nf(c.r.von)}`
      :c.r.von===p.r.von?`${nf(p.r.n)} → ${nf(c.r.n)} von ${nf(c.r.von)}`
      :`${nf(p.r.n)} von ${nf(p.r.von)} → ${nf(c.r.n)} von ${nf(c.r.von)}`;
  } else {
    const dn=c.r.n-p.r.n, w=Array.isArray(what)?plw(Math.abs(dn),what[0],what[1]):(what||'');
    d=dn===0?'unverändert':(dn>0?'+':'−')+nf(Math.abs(dn))+' '+w;
    cnt=dn===0?nf(c.r.n):`${nf(p.r.n)} → ${nf(c.r.n)}`;
  }
  const notes=d==='unverändert'?[]:notesBetween(p.e.datum,c.e.datum);
  return `<div class="kztrend"><b>${d}</b> gegenüber ${fmtDate(p.e.datum)}${isGit(p.e)?' (Stand aus der Git-Historie rekonstruiert)':''}: ${cnt}.${
    unit?` ${unit}`:''}${
    notes.map(e=>{
      if(_bemSeen&&_bemSeen.has(e.datum)) return `<span class="bem">Anmerkung ${bemNr(e)} zum Stand ${fmtDate(e.datum)}: siehe «${esc(_bemSeen.get(e.datum))}» und den Verlauf unten.</span>`;
      if(_bemSeen&&card) _bemSeen.set(e.datum,card);
      return `<span class="bem">Anmerkung ${bemNr(e)} zum Stand ${fmtDate(e.datum)}: ${esc(e.bemerkung)}</span>`;}).join('')}</div>`;
}
// compact trend line over all stands: x follows time and is shared by every
// sparkline on the page (stands a day apart are pushed at least SPARK_GAP px apart,
// so no point hides another), y = the enclosing 10-%-band (printed at the left);
// hollow point = stand reconstructed from the Git history; a small number = a note
// on that stand where this figure moved (listed under the sparklines); hover names
// date, value and that note
const SPARK_W=320, SPARK_LP=40, SPARK_RP=12, SPARK_GAP=14;
function sparkX(){
  const x0=SPARK_LP, x1=SPARK_W-SPARK_RP, n=VERLAUF.length, m=new Map();
  if(!n) return m;
  const ts=VERLAUF.map(vDay), t0=Math.min(...ts), t1=Math.max(...ts);
  let xs=ts.map(t=>x0+(t1>t0?(t-t0)/(t1-t0):1)*(x1-x0));
  for(let i=1;i<n;i++) xs[i]=Math.max(xs[i],xs[i-1]+SPARK_GAP);
  if(xs[n-1]>x1){xs[n-1]=x1; for(let i=n-2;i>=0;i--) xs[i]=Math.min(xs[i],xs[i+1]-SPARK_GAP);}
  if(n>1&&xs[0]<x0) xs=xs.map((_,i)=>x0+i*(x1-x0)/(n-1));   // too many stands: even spacing
  VERLAUF.forEach((e,i)=>m.set(e,xs[i]));
  return m;
}
function sparkline(get, name, noteNo){
  const P=VERLAUF.map(e=>({e,r:get(e)})).filter(x=>x.r&&x.r.n!=null&&x.r.von).map(x=>Object.assign(x,{p:100*x.r.n/x.r.von}));
  if(!P.length) return '<div class="vlrow">Noch kein Stand erfasst.</div>';
  const W=SPARK_W,H=84,Lp=SPARK_LP,Rp=SPARK_RP,Tp=16,Bp=20;
  const XS=sparkX(), X=e=>XS.get(e);
  // a note is marked only where this figure moved against the previous stand
  const moved=i=>i>0&&(P[i].r.n!==P[i-1].r.n||P[i].r.von!==P[i-1].r.von);
  const noteOf=i=>moved(i)&&P[i].e.bemerkung?noteNo[P[i].e.datum]:0;
  let lo=Math.floor(Math.min(...P.map(x=>x.p))/10)*10, hi=Math.ceil(Math.max(...P.map(x=>x.p))/10)*10;
  if(hi<=lo) hi=lo+10;
  const Y=v=>Tp+(hi-v)/(hi-lo)*(H-Tp-Bp);
  const r1=x=>Math.round(x*10)/10;
  let s=`<svg class="spark" viewBox="0 0 ${W} ${H}" role="group" aria-label="${esc(name)}: ${P.map(x=>fmtDate(x.e.datum)+' '+nf1(x.p)+' %').join(', ')}">`;
  [hi,lo].forEach(v=>{s+=`<line class="sg" x1="${Lp}" x2="${W-Rp}" y1="${r1(Y(v))}" y2="${r1(Y(v))}"/><text class="sl" x="${Lp-6}" y="${r1(Y(v)+3)}" text-anchor="end">${v} %</text>`;});
  const d0=VERLAUF[0], d1=VERLAUF[VERLAUF.length-1];
  s+=`<text class="sl" x="${Lp}" y="${H-4}">${fmtDate(d0.datum)}</text>`;
  if(d1!==d0) s+=`<text class="sl" x="${W-Rp}" y="${H-4}" text-anchor="end">${fmtDate(d1.datum)}</text>`;
  if(P.length>1) s+=`<path class="sp" d="${P.map((x,i)=>(i?'L':'M')+r1(X(x.e))+' '+r1(Y(x.p))).join(' ')}"/>`;
  P.forEach((x,i)=>{
    const cx=r1(X(x.e)), cy=r1(Y(x.p)), n=noteOf(i), last=i===P.length-1;
    const tip=`${fmtDate(x.e.datum)}: ${nf1(x.p)} % (${nf(x.r.n)} von ${nf(x.r.von)})${isGit(x.e)?' — aus der Git-Historie rekonstruiert':''}${n?' — Anmerkung: '+x.e.bemerkung:''}`;
    s+=`<g><title>${esc(tip)}</title><circle class="hit" cx="${cx}" cy="${cy}" r="${SPARK_GAP/2}"/><circle class="pt${isGit(x.e)?' git':''}${last?' cur':''}" cx="${cx}" cy="${cy}" r="4"/>${n?`<text class="nn" x="${cx}" y="${r1(cy-8)}" text-anchor="middle">${n}</text>`:''}</g>`;
  });
  s+='</svg>';
  const tail=P.slice(-6);
  const off=P.length-tail.length;
  return s+`<div class="vlrow">${off?'… ':''}${tail.map((x,j)=>{const n=noteOf(off+j);return `${fmtDate(x.e.datum).slice(0,6)} <b>${nf1(x.p)} %</b>${n?`<sup>${n}</sup>`:''}`;}).join(' · ')}</div>`
    +(P[0].e!==VERLAUF[0]?`<div class="vlrow">erhoben ab ${fmtDate(P[0].e.datum)}; frühere Stände kannten diese Kennzahl noch nicht</div>`:'');
}
// ---------- Gestaltung der Formulare: the layer's data and words ----------
// Computed once in scripts/gestaltung_export.py — per Formular form.gestaltung, the overview
// DATA.gestaltung — and only drawn here. Its vocabulary is its own (DATA.gestaltung.labels): a
// verdict and its tone (urteil) and what each tone means in this layer (ton) — never the generic
// «Die Dienststelle muss ihr Formular ändern». Its figures never enter the counts of the data
// standard, the open points or the Handlungsbedarf.
const GEST=DATA.gestaltung||null;
const GL=(GEST&&GEST.labels)||{};
const GM=Object.fromEntries(((GEST&&GEST.merkmale)||[]).map(m=>[m.key,m]));
const GGRP=(GEST&&GEST.gruppen)||[];
// ---------- Glossar: the terms the headline figures rest on, each said once ----------
// One list for three places: the explanation of a term where a headline card uses it
// (term() — a click, a tap or Enter opens it, like every explanation), the section «Glossar»
// on «Methode & Quellen», and the search index (type «Glossar»). Plain German; a law is
// named with the title and number the databank holds (DATA.laws), an example comes from
// the data (the most frequent eCH element of the term «Familienname»).
const GLOSSAR=(()=>{
  const law=k=>(DATA.laws||[]).find(l=>l.short_title===k);
  const kdsg=law('KDSG');
  const fam=(DATA.begriffe||[]).filter(b=>b.vorschlag==='Familienname'&&b.standard&&b.element)
    .map(b=>({b,n:(b.labels||[]).reduce((a,l)=>a+(Number(l.n)||0),0)})).sort((x,y)=>y.n-x.n)[0];
  const ex=fam?` — zum Beispiel «${fam.b.element}» in ${fam.b.standard} für den Familiennamen`:'';
  return [
    ['ech','eCH','Der Verein eCH gibt in der Schweiz die Standards für die digitale Verwaltung heraus (ech.ch) — unter anderem dafür, wie Behörden eine Angabe benennen, aufbauen und elektronisch austauschen. Jeder eCH-Standard trägt eine Nummer, zum Beispiel eCH-0044.'],
    ['ech-element','eCH-Element',`Der Baustein eines eCH-Standards für genau eine Angabe${ex}. Ein Element zählt nur, wenn es in der offiziellen technischen Beschreibung des Standards (XSD) steht.`],
    ['esh','eSH','Der Entwurf des Kantons für Angaben, die kein eCH-Standard abdeckt (E-Schaffhausen-Standard). Kein offizieller Standard: überall violett gestrichelt und als «Entwurf» markiert.'],
    ['formularfeld','Formularfeld','Das rohe Eingabeelement, wie es im Formular steht.'],
    ['datenfeld','Datenfeld','Das kuratierte logische Feld, zu dem Formularfelder verdichtet werden — zum Beispiel «Personalien».'],
    ['teilfeld','Teilfeld','Der atomare Teil eines zusammengesetzten Datenfelds: Name, Vorname und Geburtsdatum in «Personalien».'],
    ['datenpunkt','Datenpunkt','Eine einzelne Angabe, die ein Formular verlangt — zum Beispiel der Familienname. In dieser Einheit zählt die Databank beim Datenstandard: ein Teilfeld, oder ein Datenfeld ohne Teilfelder.'],
    ['attribut','Attribut','Der Eintrag im Datenkatalog: ein eCH- oder eSH-Element, egal auf wie vielen Formularen es erhoben wird.'],
    ['luecke','Lücke','Ein offener Punkt: etwas ist noch zu klären, zu entscheiden oder zu belegen. Die Farbe sagt, wer als Nächstes handelt — die Dienststelle, der Kanton oder die Databank.'
      +(GEST?' In der Gestaltung der Formulare heisst Lücke: ein geprüftes Merkmal fehlt, etwa ein Mindestmerkmal der Barrierefreiheit — ein Befund über die Datei, kein offener Punkt des Datenstandards.':'')],
    ['dvsh','DVSH','Das Dienstleistungsmodell des Kantons (amtliches Modellierungswerkzeug): massgebliche Quelle für Verfahren und Rechtsgrundlage, nur lesend übernommen. Auch die Kontakte der Dienststellen stammen von dort.'],
    ['shep','SHEP','Das publizierte Service-Portal des Kantons — was Bürgerinnen und Bürger zu einem Service sehen.'],
    kdsg&&['kdsg','KDSG',`${kdsg.title}${kdsg.sr_number?' (SHR '+kdsg.sr_number+')':''} — das Datenschutzgesetz des Kantons; es gilt für die Organe des Kantons.`],
    ['besonders-schuetzenswert','Besonders schützenswert (⛨)','Besonders schützenswerte Personendaten nach KDSG Art. 2 Abs. 1 lit. d. Für sie genügt «aufgabennotwendig» nicht: die Grundlage nach KDSG Art. 5 Abs. 1 muss benannt sein.'],
    ['dsfa','DSFA','Datenschutz-Folgenabschätzung (KDSG Art. 14b). Die Databank berechnet nur einen Anhaltspunkt aus der Zahl der besonders schützenswerten Felder; ob eine DSFA nötig ist, ist ein Entscheid, kein Rechenergebnis.'],
    ['once-only','Once-Only (↺)','Eine Angabe nur einmal erheben. Die Marke ↺ zeigt, dass das Einwohnerregister die Angabe führt — bei der einreichenden Person wie bei anderen Personen des Formulars; sie gilt nur für Daten natürlicher Personen. Ob der Kanton die Angabe aus dem Register beziehen darf, ist rechtlich offen.'
      +(DATA.register?' Welche Angaben und Beilagen weitere Register halten, zeigt die Seite «Was Register schon wissen».':'')],
    DATA.parteien&&['partei','Partei','Wem eine Angabe gehört: der Person oder Organisation, die das Formular einreicht, einem Familienmitglied, einer Vertretung, einem Arbeitgeber — oder einer Sache wie einem Grundstück. Jede Partei eines Formulars trägt eine Rolle und eine Art (natürliche Person, Organisation, Sache, Behörde); jeder Datenpunkt gehört genau einer Partei oder ist «unklar», mit einem Grund.'],
    DATA.parteien&&['rolle','Rolle','Was eine Partei im Verfahren ist — Gesuchsteller/in, Ehepartner/in, Kind, Vertreter/in, Arbeitgeber/in, Gegenstand und so weiter. Die Liste der Rollen ist ein Vorschlag der Databank, gebildet aus den Rollenwörtern der Formulare; der Kanton bestätigt sie.'],
    DATA.kennungen&&['kennung','Kennung','Ein dauerhafter Name für ein Objekt der Databank — Service, Formular, Datenfeld, Teilfeld, Angabe, Gesetz, Artikel, Regel —, auf den andere Systeme verweisen können, zum Beispiel «sh:formular:…». Eine Kennung bezeichnet immer dasselbe Objekt und wird nie neu vergeben.'],
    DATA.wirkung&&['gesetzesstand','Gesetzesstand','Die Fassung eines Gesetzes, aus der die Databank die zitierten Artikel gelesen hat — benannt nach dem Tag, ab dem sie gilt —, verglichen mit der Fassung, die bei der amtlichen Quelle heute in Kraft ist. Bei einer neueren Fassung liest die Databank die zitierten Artikel nach.'],
    DATA.register&&['register','Register','Ein amtliches Verzeichnis, das eine Behörde führt — das Einwohnerregister, das Handelsregister, das Grundbuch. Die Databank hält je Register Inhaber, Inhalt, Schlüssel und Quelle und zählt die Angaben und Beilagen der Formulare, die es laut Quelle hält; ob eine Dienststelle sie beziehen darf, ist eine eigene Rechtsfrage.'],
    DATA.vorbefuellung&&['vorbefuellung','Vorbefüllung','Vorbefüllbar heisst: die geführten Formulare (Prototyp) würden die Angabe aus dem Profil der Person einsetzen. Das gilt nur für eine Angabe mit der Marke ↺, die der einreichenden Person (natürliche Person) gehört, nach dem heutigen Wert fragt und nicht mehrdeutig ist; Angaben von Familienangehörigen erst nach einem Entscheid des Kantons. Die Zahl beschreibt, was sich vorbefüllen liesse, nicht, was eine Dienststelle heute vorbefüllt; ob der Kanton die Angabe aus dem Register beziehen darf, ist offen.'],
    GEST&&['gestaltung','Gestaltung der Formulare','Wie ein Formular aussieht und aufgebaut ist — Schrift, Farben, die Mindestmerkmale der Barrierefreiheit, Kontaktangaben und Aufbau —, gemessen an den veröffentlichten Dateien und mit den übrigen Formularen verglichen. Ein eigener Teil des Dashboards: Er beschreibt, was sich unterscheidet; seine Zahlen gehören nicht zu den offenen Punkten des Datenstandards.'],
    GEST&&['praxis','Praxis (Gestaltung)',`Der Wert, den mindestens zwei Drittel der gemessenen Formulare in einem Merkmal teilen${GM.schrift&&GM.schrift.praxis?' — zum Beispiel die Schrift '+GM.schrift.praxis.w:''}. Er ist der Massstab, weil der Databank kein Corporate-Design-Handbuch des Kantons vorliegt: «weicht von der Praxis ab» heisst nicht, dass eine Vorgabe verletzt ist. Erreicht kein Wert zwei Drittel, gibt es keine klare Praxis, und der Kanton legt fest.`],
    GEST&&['mindestmerkmale','Mindestmerkmale (Barrierefreiheit)',`Was sich an einer Datei maschinell prüfen lässt und worauf sich ein Screenreader (Vorleseprogramm) stützt: ${(GEST.merkmale||[]).filter(m=>m.gruppe==='barrierefrei').map(m=>m.label).join(', ')}. Ein fehlendes Merkmal ist eine Lücke; ein vorhandenes ist kein Nachweis der Barrierefreiheit — kein Test nach eCH-0059, WCAG oder PDF/UA.`],
  ].filter(Boolean).map(([id,wort,text])=>({id,wort,text}));})();
const GLOSS_BY=Object.fromEntries(GLOSSAR.map(g=>[g.id,g]));
// a term of the glossary inside a text: its explanation opens like every other one
const term=(id,txt)=>{const g=GLOSS_BY[id]; return g?`<span title="${esc(g.wort+' — '+g.text)}">${txt}</span>`:txt;};
// ---------- Übersicht (the landing page): the data standard first ----------
function viewHome(){
  const m=document.getElementById('main');
  const K=DATA.kopfzahlen||{};
  _bemSeen=new Map();          // a note in full under its first card, by number under the next ones
  const S1=(LAB.stufen||[]).find(s=>Number(s[0])===1);
  const card=o=>`<div class="kz"><div class="kzl">${o.label}</div><div class="kzv">${o.value}</div>${o.sub?`<div class="kzsub">${o.sub}</div>`:''}${o.body||''}${o.ziel?`<div class="kzziel">${o.ziel}</div>`:''}${o.trend||''}${o.link?`<div class="kzfoot">${o.link}</div>`:''}</div>`;
  // (a) exchangeable: data points with a citable eCH element. The bar draws the four parts
  // the export counted (standard_ech.ech_ton, they sum to `von`); an element the databank
  // assigned wrongly (the label means another Angabe) is not settled — it sits in the grey
  // part, while the headline still counts every point that carries an element
  const E=K.standard_ech, EB=(E&&E.ech_ton)||{}, EA=(E&&E.ech)||{}, ZF=EA.zuordnung_falsch||0;
  const cA=E?card({label:`${term('datenpunkt','Datenpunkte')} mit ${term('ech-element','eCH-Element')}`, value:pctTxt(E.wert,E.von),
    sub:`${nf(E.wert)} von ${nf(E.von)} Datenpunkten tragen ein Element eines eCH-Standards${ZF?` — bei ${nf(ZF)} davon korrigiert die Databank die Zuordnung`:''}`,
    body:tonBar([{t:'ok',n:EB.ok||0,label:echOkLabel(ZF)},
      {t:'ok2',n:EB.ok2||0,label:'nur auf Standard-Ebene (der Standard hat keinen Elementkatalog)'},
      {t:'dec',n:EB.dec||0,label:KS_LABEL(),link:EB.dec?goLink('kanton','kein_standard','Für den Kanton ›','inl'):''},
      {t:'open',n:EB.open||0,label:stdOpenLabel(EA),link:EB.open?goLink('recherche',ZF?'zuordnung':EA.standard_alt?'echalt':'ech','Recherche der Databank ›','inl'):''}],'Datenpunkte nach eCH-Stand'),
    ziel:ZIEL_STD,
    trend:trendLine(e=>e.punkte_ech!=null&&e.punkte?{n:e.punkte_ech,von:e.punkte}:null,null,null,'Datenpunkte mit eCH-Element'),
    link:goLink('katalog','','Zum Datenkatalog ›')}):'';
  // (b) demanded the same way everywhere
  const U=K.standard_einheitlich, UT=(U&&U.teile)||{};
  const cB=U?card({label:'Einheitlich verlangt', value:pctTxt(U.wert,U.von),
    sub:`${nf(U.wert)} von ${nf(U.von)} ${term('datenpunkt','Datenpunkten')} mit ${term('ech-element','eCH-Element')} werden überall gleich verlangt (Pflicht, Format, Werteliste)`,
    body:tonBar([{t:'ok',n:UT.ok||0,label:'gleich verlangt wie in der übrigen Praxis'},
      {t:'act',n:UT.act||0,label:'anders verlangt als die übrige Praxis (Pflicht, Format oder Werteliste)'},
      {t:'dec',n:UT.dec||0,label:`${esc(todoCat('divergenz_offen')[1])} (mal Pflicht, mal optional) — Kanton legt fest`,
        link:UT.dec?goLink('kanton','divergenz_offen','Für den Kanton ›','inl'):''}],'Datenpunkte nach Einheitlichkeit')
      +`<div class="kznote">Gezählt je Datenpunkt, jeder nur einmal; ein abweichender Datenpunkt zählt nicht zusätzlich als uneinheitlich.${
        (CAT_N.divergenz||0)===(UT.act||0)&&(CAT_N.divergenz_offen||0)===(UT.dec||0)?' Der Handlungsbedarf zählt genauso.'
        :` Der Handlungsbedarf zählt ${catUnit('divergenz',CAT_N.divergenz||0)} anders verlangt und ${catUnit('divergenz_offen',CAT_N.divergenz_offen||0)} «${esc(todoCat('divergenz_offen')[1])}», weil er jeden Eintrag je Formular zählt.`}</div>`,
    trend:trendLine(e=>e.punkte_ech!=null&&e.div_punkte!=null&&e.div_offen!=null&&e.punkte_ech>0
      ?{n:e.punkte_ech-e.div_punkte-e.div_offen,von:e.punkte_ech}:null,null,null,'Einheitlich verlangt'),
    link:goLink('todo','divergenz',`${nf(U.formulare_div)} von ${pl(U.formulare,'Formular','Formularen')} ${plw(U.formulare_div,'weicht','weichen')} ab ›`)}):'';
  // (c) named differently — title and number point the same way: how many of the Datenpunkte
  // with an eCH element carry a label that deviates. The number is the whole category
  // «Bezeichnung angleichen oder Feld aufteilen» (the figure the Verlauf, the Handlungsbedarf
  // and the Dienststellen count); the bar shows every naming verdict of the export
  // (standard_benannt.teile, they sum to `von`): rename, split, a mapping the databank
  // corrects, and the rest, for which no deviation is recorded
  const N=K.standard_benannt, NT=(N&&N.teile)||{};
  const nBen=N?N.begriff_felder:0;
  const cC=N?card({label:'Abweichend benannt', value:`${nf(nBen)} <span class="kzvon">von ${nf(N.von)}</span>`,
    sub:`${term('datenpunkt','Datenpunkten')} mit ${term('ech-element','eCH-Element')} ${plw(nBen,'trägt','tragen')} eine Bezeichnung, die vom einheitlichen Begriff abweicht oder mehrere Daten bündelt — in ${pl(N.formulare_begriff,'Formular','Formularen')}`,
    body:tonBar([{t:'act',n:NT.variante||0,label:'auf den einheitlichen Begriff umbenennen'},
      {t:'act',n:NT.aufteilen||0,label:'im Formular aufteilen (bündelt Daten, die der Standard trennt)'},
      {t:tonOf('begriff','zuordnung'),n:NT.zuordnung||0,label:'die Bezeichnung meint eine andere Angabe — die Databank korrigiert die eCH-Zuordnung',
        link:NT.zuordnung?goLink('recherche','zuordnung','Recherche der Databank ›','inl'):''},
      {t:'rest',n:NT.rest||0,label:'keine abweichende Bezeichnung festgestellt'}],'Datenpunkte mit eCH-Element nach Bezeichnung'),
    trend:trendLine(e=>e.begriff_felder!=null?{n:e.begriff_felder,von:null}:null,catUnitOf('begriff'),null,'Abweichend benannt'),
    link:goLink('begriffe','','Zu den Begriffen ›')}):'';
  // further gaps
  const R=K.rechtsgrundlage, RT=(R&&R.teile)||{};
  const cR=R?card({label:'Rechtsgrundlage je Datenfeld', value:pctTxt(R.wert,R.von),
    sub:`${nf(R.wert)} von ${nf(R.von)} Datenfeldern mit belegter oder begründeter Grundlage`,
    body:tonBar([{t:'ok',n:RT.ok||0,label:'Norm belegt oder für die Aufgabe nötig'},
      {t:'act',n:RT.act||0,label:'ohne Grundlage — weder Norm noch Aufgabe verlangt das Feld'},
      {t:'dec',n:RT.dec||0,label:'Aufgabenbedarf offen'},
      {t:'open',n:RT.open||0,label:`noch zu ermitteln${R.art5_offen?` (davon ${nf(R.art5_offen)} ⛨: Grundlage nach KDSG Art. 5 zu benennen)`:''}`}],'Datenfelder nach Rechtsgrundlage'),
    ziel:'Ziel: jedes Datenfeld mit Grundlage (KDSG Art. 4)',
    trend:trendLine(e=>e.felder_gedeckt!=null&&e.datenfelder?{n:e.felder_gedeckt,von:e.datenfelder}:null,null,null,'Rechtsgrundlage je Datenfeld'),
    link:goLink('register','','Grundlagen je Service im Verzeichnis ›')}):'';
  // every Formular in exactly one part (kopfzahlen.verzeichnis.teile): the forms whose purpose
  // or recipients are not yet recorded are the databank's research (grey, as on «Recherche
  // der Databank»); a missing own retention period alone is no point
  const V=K.verzeichnis, VT=(V&&V.teile)||{};
  const cV=V?card({label:'Verzeichnis-Angaben', value:`${nf(V.wert)} <span class="kzvon">von ${nf(V.von)}</span>`,
    sub:'Formularen mit Zweck, belegten Empfängern und eigener Frist (Spezialfrist oder Fristentscheid)',
    body:tonBar([{t:'ok',n:VT.ok||0,label:'Zweck, Empfänger und Frist erfasst'},
      {t:catTon('zweck'),n:VT.open||0,label:'Zweck oder Empfänger nicht erfasst',link:VT.open?goLink('recherche','zweck','Recherche der Databank ›','inl'):''},
      {t:'rest',n:VT.rest||0,label:'nur die eigene Frist nicht festgelegt'}],'Formulare nach Verzeichnis-Angaben')
      +'<div class="kznote">Ein Steuerungsinstrument: ein öffentliches Register verlangt KDSG Art. 17b nur von Polizei, Staatsanwaltschaft und Justizvollzug.</div>',
    link:goLink('register','','Zum Verzeichnis ›')}):'';
  const O=K.offene_punkte;
  const nO=O?(O.act||0)+(O.dec||0)+(O.open||0):0;
  // what one point counts: the units of DATA.labels.einheit, over every category with points
  const UNITS=(()=>{const u={}; CAT_ORDER.filter(k=>CAT_N[k]).forEach(k=>{const w=catUnitOf(k); u[w[1]]=(u[w[1]]||0)+CAT_N[k];});
    const ord=['Datenpunkte','Felder','Formularpaare','Formulare'];
    return Object.entries(u).sort((a,b)=>(ord.indexOf(a[0])+1||9)-(ord.indexOf(b[0])+1||9));})();
  const unitWord=UNIT_WORD;
  const cO=O?card({label:'Offene Punkte nach «wer handelt»', value:nf(nO),
    sub:`Punkte — je nach Art gezählt je ${UNITS.filter(([w])=>w!=='Formulare').map(([w])=>unitWord(catUnitOf(CAT_ORDER.find(k=>catUnitOf(k)[1]===w))[0])).join(', je ')}${UNITS.some(([w])=>w==='Formulare')?'; bei Angaben zum ganzen Formular je Formular':''}`,
    body:tonBar([{t:'act',n:O.act||0,label:esc(tonLabel('act')),bare:1,link:goLink('dienststellen','','Für Dienststellen ›','inl')},
      {t:'dec',n:O.dec||0,label:esc(tonLabel('dec')),bare:1,link:goLink('kanton','','Für den Kanton ›','inl')},
      {t:'open',n:O.open||0,label:esc(tonLabel('open')),bare:1,link:goLink('recherche','','Recherche der Databank ›','inl')}],'Offene Punkte nach wer handelt')
      +`<div class="kznote">davon ${UNITS.map(([w,n])=>`${nf(n)} ${unitWord(w)}`).join(' · ')}</div>`}):'';
  const nDst=(DATA.dienststellen_uebersicht||[]).filter(d=>d.offen&&d.offen.act>0).length;
  const door=(tab,k,q,n)=>`<a class="door" href="#${tab}" data-go="${tab}"><span class="dk">${k}</span><span class="dq">${q}</span><span class="dn">${n}</span></a>`;
  const key=`<div class="tonkey"><span>Die Farbe sagt, wer als Nächstes handelt:</span>${
    [['ok','grün','geklärt'],['act','rot','Dienststelle'],['dec','amber','Kanton'],['open','grau','Databank']].map(([t,f,w])=>
      `<span class="tk" title="${esc(tonLabel(t)+' — '+tonTip(t))}"><i class="sw t-${t}"></i>${esc((TON[t]&&TON[t].farbe)||f)} ${w}</span>`).join('<span class="sep">·</span>')}</div>`;
  _bemSeen=null;
  const notes=VERLAUF.filter(e=>e.bemerkung), noteNo={}; notes.forEach((e,i)=>{noteNo[e.datum]=i+1;});
  const anyGit=VERLAUF.some(isGit);
  m.innerHTML=`<h3 class="view">Compliance-Databank Kanton Schaffhausen</h3>
  <p class="lead">Die Databank hält für jedes der ${nf(DATA.forms.length)} Formulare der kantonalen Verwaltung fest, welche Daten es verlangt,
  nach welchem Standard sie ausgetauscht werden können und auf welcher Rechtsgrundlage sie erhoben werden.
  Sie zeigt den Dienststellen, was sie an ihren Formularen ändern können, und dem Kanton, was er festlegen muss.</p>
  ${key}
  <section class="hsec core"><h4>Datenstandard — das Kernstück</h4>
    ${S1?`<p class="hsub">${esc(S1[2])}</p>`:''}
    <p class="hsub">${term('ech','eCH')} ist der Verein, der in der Schweiz die Standards für den elektronischen Datenaustausch der Verwaltung herausgibt; ein ${term('datenpunkt','Datenpunkt')} ist eine einzelne Angabe, die ein Formular verlangt — zum Beispiel der Familienname.</p>
    <div class="kzgrid">${cA}${cB}${cC}</div></section>
  <section class="hsec"><h4>Weitere Lücken</h4>
    <p class="hsub">Eine Lücke heisst: etwas ist noch zu klären, zu entscheiden oder zu belegen.</p>
    <div class="kzgrid">${cR}${cV}${cO}</div></section>
  <section class="hsec"><h4>Wo anfangen?</h4><div class="doors">
    ${door('dienststellen','Für Dienststellen','Was muss ich an meinen Formularen ändern?',O?`${nf(O.act)} Punkte, die ${nDst===1?'eine Dienststelle':nf(nDst)+' Dienststellen'} selbst lösen ${plw(nDst,'kann','können')}`:'')}
    ${door('kanton','Für den Kanton','Was muss entschieden werden?',O?`${nf(O.dec)} offene Punkte, meist Datenpunkte ohne Standard, warten auf einen Entscheid des Kantons`:'')}
    ${door('methode','Für Fachleute','Wie ist die Databank gebaut?','Belege, Verifikationsstufen, Quellen und der Verlauf aller Kennzahlen')}
  </div>${(()=>{const L=[GEST&&goLink('gestaltung','','Gestaltung der Formulare — Schrift, Farben, Barrierefreiheit ›','inl'),
      (PAR||WIRK||KONZ)&&goLink('datenmodell','','Datenmodell — wessen Angabe, Kennungen, Wirkung einer Änderung ›','inl'),
      REG&&goLink('onceonly','','Was Register schon wissen ›','inl')].filter(Boolean);
    return L.length?`<p class="glinkline">Auch: ${L.join(' · ')}</p>`:'';})()}</section>
  <section class="hsec"><h4>Verlauf</h4>
    <div class="vlgrid">
      <div class="kz"><div class="kzl">Datenpunkte mit eCH-Element</div>${sparkline(e=>e.punkte_ech!=null&&e.punkte?{n:e.punkte_ech,von:e.punkte}:null,'Anteil der Datenpunkte mit eCH-Element',noteNo)}</div>
      <div class="kz"><div class="kzl">Datenfelder mit Rechtsgrundlage</div>${sparkline(e=>e.felder_gedeckt!=null&&e.datenfelder?{n:e.felder_gedeckt,von:e.datenfelder}:null,'Anteil der Datenfelder mit belegter oder begründeter Grundlage',noteNo)}</div>
    </div>
    ${notes.length?`<ol class="vlnotes">${notes.map(e=>`<li value="${noteNo[e.datum]}"><b>${fmtDate(e.datum)}:</b> ${esc(e.bemerkung)}</li>`).join('')}</ol>`:''}
    <div class="vlnote">${anyGit?'Hohle Punkte: Stand aus der Git-Historie rekonstruiert. ':''}Alle Werte je Stand: ${goLink('methode','','Verlaufstabelle unter «Methode &amp; Quellen» ›','inl')}</div>
  </section>
  <div class="datenstand"><b>Datenstand</b> — wann die zugrunde liegenden Fakten galten: ${esc(datenstandText())}</div>`;
  wireGo(m);
}
// ---------- Methode & Quellen: how the databank works, and every figure in detail ----------
function viewMethode(){
  const m=document.getElementById('main');
  const F=DATA.forms, H=DATA.datenhandhabung||[], K=DATA.attribut_katalog||[];
  // the figures of the tiles are the exported ones (kopfzahlen); only two plain counts are
  // taken here, both on what the export stamped on each Datenfeld: the fields the task
  // carries without a norm (basis_state «aufgabe») and the ⛨ fields
  const KZ=DATA.kopfzahlen||{}, KE=KZ.standard_ech||{}, RG=KZ.rechtsgrundlage||{}, UE=KZ.standard_einheitlich||{};
  let nAuf=0,nSens=0;
  F.forEach(f=>(f.data_fields||[]).forEach(d=>{if(d.basis_state==='aufgabe')nAuf++; if(d.sensitive)nSens++;}));
  const nDf=RG.von||0, nOver=RG.ohne||0, nA5=RG.art5_offen||0;
  const tile=(n,l,tab,sub)=>`<button class="hometile" data-go="${tab}"${sub?` data-sub="${sub}"`:''}><span class="htn">${n}</span><span class="htl">${l}</span></button>`;
  const tonRows=['ok','act','dec','open'].map(t=>`<li><i class="sw t-${t}"></i><span><b>${esc(tonLabel(t))}</b>${TON[t]&&TON[t].farbe?` <span class="muted">(${esc(TON[t].farbe)})</span>`:''} — ${esc(tonTip(t))}</span></li>`).join('');
  // each category as a chip in the tone of whoever closes it, with its points (0 dimmed, not hidden)
  const stufen=STUFEN.map(s=>{
    const cats=CAT_ORDER.filter(c=>TODO_BY[c]&&catStufe(c)===s.n);
    return `<li><b>${esc(stufeLabel(s.n))}:</b> ${esc(s.text)}${cats.length?`<div class="stcats">${cats.map(c=>{const t=catTon(c), n=CAT_N[c]||0;
      return tonChip(t,esc(todoCat(c)[1]),n,`${tonLabel(t)} · ${catUnit(c,n)} — ${todoCat(c)[4]}`,n?'':' data-zero="1"').replace('class="tchip badge','class="tchip badge'+(n?'':' zero'));}).join('')}</div>`:''}</li>`;}).join('');
  const v=x=>x==null?'<span class="muted" title="in jenem Stand noch nicht erhoben">—</span>':nf(x);
  const pc=(a,b)=>a!=null&&b?` <span class="muted">(${nf1(100*a/b)} %)</span>`:'';
  const ln=(...xs)=>xs.map(x=>`<div class="nowrap">${x}</div>`).join('');
  // the note explaining a jump sits in its own full-width row under the stand
  const vrows=VERLAUF.map(e=>`<tr${e.bemerkung?' class="hasbem"':''}><td class="nowrap"><b>${fmtDate(e.datum)}</b>
    <div class="small">${e.quelle==='build'?'Export':isGit(e)?`<div class="nowrap">Git-Historie</div><span class="mono">${esc(String(e.quelle).slice(4))}</span>`:esc(e.quelle||'')}</div></td>
    <td class="small">${ln(v(e.formulare)+' Formulare',v(e.datenfelder)+' Datenfelder',v(e.punkte)+' Datenpunkte')}</td>
    <td class="small">${ln('mit eCH-Element '+v(e.punkte_ech)+pc(e.punkte_ech,e.punkte),'anders verlangt '+v(e.div_punkte),esc(todoCat('divergenz_offen')[1])+' '+v(e.div_offen),'Formulare mit Abweichung '+v(e.formulare_div),catUnitOf('begriff')[1]+' umzubenennen oder aufzuteilen '+v(e.begriff_felder))}</td>
    <td class="small">${ln('belegt oder begründet '+v(e.felder_gedeckt)+pc(e.felder_gedeckt,e.datenfelder),'mit Zitat '+v(e.felder_zitiert),'ohne Grundlage '+v(e.felder_ohne),'Aufgabenbedarf offen '+v(e.felder_offen),'zu ermitteln '+v(e.felder_zu_ermitteln),'Art. 5 offen '+v(e.felder_art5_offen))}</td>
    <td class="small">${ln('mit Zweck '+v(e.formulare_mit_zweck),'vollständig '+v(e.verzeichnis_vollstaendig))}</td>
    <td class="small">${ln(...['act','dec','open'].map(t=>`<i class="sw t-${t}"></i>${esc(tonLabel(t))} ${v(e['offen_'+t])}`))}</td>
    </tr>${e.bemerkung?`<tr class="vlbemrow"><td></td><td colspan="5" class="small"><b>Anmerkung:</b> ${esc(e.bemerkung)}</td></tr>`:''}`).join('');
  m.innerHTML=pageHead('Methode &amp; Quellen',
    'Wie die Databank arbeitet: was «belegt» heisst, was Farben und Prioritäten bedeuten, woher die Daten stammen und wie sich die Kennzahlen entwickeln.',
    'Die Arbeitsweise der Databank (Belege, Verifikationsstufen, Begriffe), die Farbsprache und die Prioritätsstufen der offenen Punkte, alle Kennzahlen im Detail und ihr Verlauf je Stand.',
    'Farben, Stufen und Kennzahlen kommen aus demselben Export wie jede andere Seite (data_export.json, erzeugt aus citygov.db). Der Verlauf ist verlauf.json: ein Eintrag je Tag; frühere Stände sind aus der Git-Historie der Databank rekonstruiert.',
    'Eine Kennzahl, die ein früherer Stand noch nicht kannte, steht dort als «—», nicht als 0. Eine Anmerkung erklärt einen Sprung, etwa wenn falsche Zuordnungen korrigiert wurden.')+`
  <div class="card">
    <p style="font-size:var(--fs-m);line-height:1.6;margin:0">Diese Databank erfasst pro <b>Formular</b> der kantonalen
    Verwaltung: die <b>Gesetze</b>, die es verlangen (artikelgenau), die <b>Datenfelder</b>, die es erhebt (bis aufs
    atomare Teilfeld), den <b>Standard</b> jeder Angabe (eCH, ersatzweise der kantonale Entwurf eSH), die
    <b>Handhabungsregeln</b> (Speichern, Weitergeben, Löschen — mit Wortlaut-Zitat) und den <b>Digitalisierungs-Stand</b>.
    Ihre Angaben werden auch maschinell weiterverarbeitet (Exporte für automatisierte Abläufe) — deshalb muss jede Angabe
    <b>präzise, belegt und nie stillschweigend falsch</b> sein.</p>
  </div>
  <div class="card"><div class="dvsub">Die Farbe sagt, wer als Nächstes handelt</div>
    <ul class="tleg tonlist">${tonRows}<li><i class="sw t-ok2"></i><span><b>Hellgrün</b> — geklärt auf Standard-Ebene: der Standard hat keinen Elementkatalog, ein Element ist hier nicht zu bestimmen.</span></li></ul>
    <p class="small muted" style="margin:8px 0 0">Offene Punkte sind Lücken — noch zu klären, zu entscheiden oder zu belegen. Grau ist die
    Arbeitsliste der Databank selbst und sagt nichts über die Verwaltung. Ein Status, dem kein Ton zugeordnet ist, gilt als nicht geklärt, nie als geklärt.</p></div>
  <div class="card"><div class="dvsub">Vier Prioritätsstufen — der Datenstandard zuerst</div>
    <ol class="stufen">${stufen}</ol>
    <p class="small muted" style="margin:6px 0 0">Die Farbe des Chips sagt, wer die Kategorie schliesst — rot die Dienststelle, amber der Kanton, grau die Databank; die Zahl sind die offenen Punkte heute. Innerhalb einer Stufe gilt die Reihenfolge der Kategorien. Die Massnahmen einer Dienststelle sind zuerst nach Stufe, dann nach dieser Reihenfolge der Kategorien und erst zuletzt nach Umfang geordnet.</p></div>
  <div class="card">
    <div class="methodbox"><b>Methode — was hier «verifiziert» heisst</b>
      <div>• <b>Prüfschranken:</b> Zuordnungen werden maschinell vorgeschlagen, aber die Ladeprogramme lehnen alles ab, was nicht existiert:
      ein Gesetzesartikel muss eingelesen sein, ein eCH-Element muss im offiziellen XSD stehen, ein Regel-Zitat muss
      wörtlich im Gesetzes-PDF vorkommen, eine Frist-Zahl muss im Zitat stehen.</div>
      <div id="m-datenstandard">• <b>Datenstandard — wie gemessen wird:</b> Ein eCH-Element zählt nur, wenn es im offiziellen XSD steht. Gezählt wird
      jeder atomare Datenpunkt einmal. ${stBadge(tonOf('div','pflicht'),'anders verlangt','Die Dienststelle gleicht das Formular an oder dokumentiert die abweichende Rechtsgrundlage')} heisst: Pflicht oder optional
      gegen eine klare Praxis (die Angabe kommt mindestens dreimal vor, auf mindestens zwei anderen Formularen, und mindestens 2/3 der
      übrigen Vorkommen verlangen sie umgekehrt) · ein anderer Datentyp oder ein anderes Format als mindestens 2/3 der Vorkommen ·
      eigene Werte, wo das XSD eine Codeliste festlegt (dann genügt es, beim Austausch auf die Codes abzubilden).
      ${stBadge(tonOf('div','pflicht_uneinheitlich'),esc(todoCat('divergenz_offen')[1]),'Kein Formular ist die Ausnahme — der Kanton legt fest')} heisst: die übrigen
      Vorkommen sind gespalten, keine Seite erreicht 2/3 — kein Formular ist die Ausnahme, der Kanton legt fest.
      <b>Begriffe:</b> der Vorschlag ist eine Bezeichnung, die für diese Angabe schon vorkommt, sonst eine aus anderen Formularen des
      Kantons — nie erfunden. Klassen: angleichen · Rolle — in Ordnung · Feld aufteilen · eCH-Zuordnung korrigieren. Eine zweite,
      unabhängige Prüfung bestätigt jeden Eintrag; korrigierte Einträge tragen in der Begründung den Vermerk «Zweitprüfung:», die
      Korrekturen liegen in quellen/korrekturen/. <b>eSH</b> gilt nur für Datenpunkte ohne eCH-Standard, ist überall als «Entwurf»
      markiert und überdeckt nie ein eCH-Element.</div>
      <div>• <b>Drei Verifikationsstufen</b> an jeder Zitation: ${stBadge(tonOf('verif','verified'),'verifiziert','Bundesrecht: Artikel aus dem amtlichen Fedlex-Text gelesen')} (Bundesrecht,
      aus dem amtlichen Fedlex-Text gelesen) · ${stBadge(tonOf('verif','quelle_pdf'),'Quelle SHR-PDF','aus dem amtlichen Gesetzes-PDF gelesen')} (kantonales Recht, aus dem amtlichen PDF des Schaffhauser Rechtsbuchs gelesen) ·
      ${stBadge(tonOf('verif','unverifiziert'),'unverifiziert','noch nicht am Gesetzestext geprüft')} (noch ungeprüft — eine Wissenslücke der Databank, kein Befund über
      die Verwaltung). In der Databank heute (${nf(ZIT.total)} Zitate der kuratierten Feld-Schicht): verifiziert <b>${nf(ZIT.verifiziert)}</b> ·
      Quelle SHR-PDF <b>${nf(ZIT.quelle_pdf)}</b> · unverifiziert <b>${nf(ZIT.unverifiziert)}</b>${ZIT.unverifiziert?'':' (Stufe definiert, kommt derzeit nicht vor)'}.</div>
      <div>• <b>Die Rechtsfrage je Datenfeld</b> — drei Antworten und zwei Arten von Lücken: Artikel belegt · ${stBadge(tonOf('basis','aufgabe'),'aufgabennotwendig','keine explizite Norm, aber für die Aufgabe nötig')}
      (keine explizite Norm, aber ohne die Angabe ist die Aufgabe nicht erfüllbar — Einordnung der Databank nach dem Massstab von KDSG Art. 4 Abs. 1 lit. b) ·
      ${stBadge(tonOf('basis','ohne'),'ohne Grundlage','weder Norm noch Aufgabe verlangt das Feld')} (Fachbegriff: Over-collection — weder Norm noch Aufgabe verlangt es) ·
      ${stBadge(tonOf('basis','offen'),'Aufgabenbedarf offen','keine Norm; ob die Aufgabe die Angabe braucht, ist noch nicht beurteilt')} (noch nicht beurteilt) ·
      ${stBadge(tonOf('basis','zu_ermitteln'),'zu ermitteln','noch nicht recherchiert')} (noch nicht recherchiert) — die letzten beiden sind Lücken, die eine wartet auf eine Beurteilung, die andere auf die Recherche der Databank. Für ⛨-Felder genügt
      «aufgabennotwendig» nicht: die Grundlage nach KDSG Art. 5 Abs. 1 muss benannt sein; sonst bleibt das Feld offen
      (${stBadge(tonOf('basis','art5_offen'),'⛨ Grundlage nach KDSG Art. 5 offen','aufgabennotwendig, aber die Grundlage nach KDSG Art. 5 Abs. 1 ist noch nicht benannt')} — Recherche der Databank, nicht «Aufgabenbedarf offen»).</div>
      <div>• <b>↺ Once-Only:</b> das Einwohnerregister führt die Angabe bereits; vorbefüllbar ist davon nur, was der einreichenden Person gehört und nach dem heutigen Wert fragt (Glossar: Vorbefüllung). Die Marke gilt nur für
      Daten natürlicher Personen, nie für Betriebs-, Behörden- oder Objektadressen. Sie ist eine Einordnung der Databank, kein
      Rechtsanspruch: ob eine Dienststelle das Register abfragen darf, richtet sich nach dem Recht des Registers — bei kantonalen Stellen nach KDSG Art. 8 Abs. 1 (gesetzliche Grundlage oder Bedarf für die gesetzlichen Aufgaben des Empfängers), bei Registern des Bundes nach Bundesrecht.</div>
      <div>• <b>Fünf Begriffsebenen</b>, die hier nie vermischt werden: Formularfeld, Datenfeld, Teilfeld, Datenpunkt und Attribut — jede im Glossar unten erklärt.</div>
      <div>• <b>Lücke = Lücke:</b> Fehlendes steht als «fehlt», «kein Standard», «zu ermitteln» offen da. Eine
      geschönte Anzeige von 100&nbsp;% wäre hier ein Defekt.</div>
      ${GEST?`<div id="m-gestaltung">• <b>Gestaltung der Formulare</b> — ein eigener Teil: wie die Formulare aussehen — Schrift, Farben,
      die maschinell prüfbaren Mindestmerkmale der Barrierefreiheit, Kontaktangaben und Aufbau —, gemessen an den veröffentlichten Dateien
      (Methode ${esc(GEST.methode||'—')}, Stand der Messung ${fmtDate(GEST.stand)}). Massstab ist die Praxis der gemessenen Formulare: ein Wert,
      den mindestens zwei Drittel von ihnen teilen; ein Corporate-Design-Handbuch des Kantons liegt der Databank nicht vor. Erreicht kein Wert
      zwei Drittel, legt der Kanton fest. Was in Bildern und Logos steht, ist nicht gemessen; die eFormulare der Plattform haben kein eigenes
      Erscheinungsbild. Die Seite beschreibt, was sich unterscheidet, und verlangt von keiner Dienststelle, ein Formular zu ändern; ihre Zahlen
      gehören nicht zu den offenen Punkten und nicht zu den Kennzahlen des Datenstandards. ${goLink('gestaltung','','Zur Gestaltung der Formulare ›','inl')}</div>`:''}
      ${(()=>{const Z=PAR&&PAR.zahlen, MT=(DM.parteien||{}).methode, KS=KONZ&&KONZ.summen, KN=DM.kennungen, WU=WIRK&&WIRK.uebersicht, WS=WIRK&&WIRK.summen, VF=(REG_GRP.find(g=>g.key==='einwohner')||{}).vorbefuellbar;
        return [Z?`<div id="m-parteien">• <b>Parteien und Rollen</b> — wessen Angabe ein Datenpunkt ist: ${nf(Z.zugeordnet)} von ${nf(Z.punkte)} Datenpunkten sind einer Partei des Formulars zugeordnet, die übrigen «unklar» mit einem Grund. Zuerst leitet die Databank ab, was ihre Hinweise eindeutig sagen (Rolle aus der Prüfung der Bezeichnungen, Wort für die Partei in Bezeichnung oder Abschnitt, Subjekt des Felds)${MT?`; dann beurteilt sie ${pl(MT.formulare_beurteilt,'Formular','Formulare')} aus ihrem Text, jede Partei und jede Zuordnung mit einem Zitat, das im Formulartext stehen muss; eine Zweitprüfung bestätigt ${nf(MT.zweitpruefung.bestaetigt)} und ändert ${nf(MT.zweitpruefung.geaendert)}; eine Stichprobe von ${nf(MT.stichprobe?MT.stichprobe.n:0)} Datenpunkten prüft das Ergebnis am Formulartext`:''}. Die Art der Partei passt zum beurteilten Subjekt des Felds. Die Rollen sind ein Vorschlag der Databank, den der Kanton bestätigt. ${goLink('datenmodell','parteien','Zu den Parteien ›','inl')}</div>`:'',
          KS?`<div id="m-konzepte">• <b>Konzepte</b> — ${pl(KS.n_konzepte,'Konzept fasst','Konzepte fassen')} die eCH-Elemente zusammen, die dieselbe Angabe bezeichnen (Vorname, Strasse, AHV-Nummer …); die Liste ist geprüft und liegt in quellen/konzepte.json. Je Konzept und Rolle der Partei ist das Element, das mindestens zwei Drittel von mindestens ${nf((KONZ.regel||{}).mindestens||10)} Datenpunkten nutzen, der «Vorschlag», den der Kanton bestätigt; sonst legt der Kanton fest. Ein Befund zum Datenstandard ausserhalb der Kennzahlen und der offenen Punkte. ${goLink('datenmodell','konzepte','Zu den Konzepten ›','inl')}</div>`:'',
          KN?`<div id="m-kennungen">• <b>Kennungen und Exportvertrag</b> — ${pl(KN.n_aktiv,'dauerhafte Kennung','dauerhafte Kennungen')} für Services, Formulare, Datenfelder, Teilfelder, Angaben, Gesetze, Artikel und Regeln; keine wird gelöscht oder neu vergeben. Jeder veröffentlichte Export trägt eine Version, ein JSON Schema unter schema/ und seine Änderungen in exportvertrag.json. ${goLink('datenmodell','kennungen','Zu den Kennungen ›','inl')}</div>`:'',
          WU?`<div id="m-gesetzesstand">• <b>Gesetzesstand und Wirkung einer Änderung</b> — je Gesetz die Fassung, aus der die Artikel gelesen sind, und ob sie bei der amtlichen Quelle noch in Kraft ist (geprüft ${pruefTage(WU)}); eine neuere Fassung liest die Databank nach, sie ändert die Zitate nicht von selbst. Je Gesetz und Artikel die Datenpunkte, Formulare, Services und Dienststellen, die ihn zitieren (${pl(WS.n_zitate,'Zitat','Zitate')}). ${goLink('datenmodell','wirkung','Zur Wirkung einer Änderung ›','inl')}</div>`:'',
          REG?`<div id="m-register">• <b>Register und Once-Only</b> — ${pl(Object.keys(REG_BY).length,'Register','Register')} mit Inhaber, Inhalt, Schlüssel und amtlicher Quelle. Eine Angabe zählt als vom Register gehalten, wenn eine zitierte Quelle das sagt und die Art der Partei passt (natürliche Person bzw. Organisation) — gezählt wird das Element, auch bei Angaben anderer Personen des Formulars und bei einer Frage nach einem früheren Wert; die obere Grenze nimmt jede Angabe eines Standards, mit dem das Register austauscht. Vorbefüllbar${VF?` (${pl(VF.pflicht,'Pflichtangabe','Pflichtangaben')})`:''} ist nur eine Angabe der einreichenden Person, nach ihrem heutigen Wert gefragt und nicht mehrdeutig; die gesparte Zeit ist eine Modellschätzung ohne Fallzahlen. Ob eine Dienststelle beziehen darf, was ein Register hält, ist rechtlich offen. ${goLink('onceonly','','Zu den Registern ›','inl')}</div>`:''].join('');})()}
      <div>• <b>Quellen:</b> <b>DVSH</b> — das Dienstleistungsmodell des Kantons (amtliches Modellierungswerkzeug; massgebliche Quelle für Verfahren
      und Rechtsgrundlage, nur lesend übernommen) · <b>SHEP</b> — das publizierte Service-Portal des Kantons (Bürgersicht,
      shep.meetfrida.agency) · die amtlichen Formulare selbst ·
      Gesetzestexte (Schaffhauser Rechtsbuch SHR, Fedlex) · die eCH-Standards von ech.ch.
      <b>eSH</b> ist der Entwurf des Kantons für Daten ohne eCH-Standard — überall als «Entwurf» markiert, nie mit
      offiziellem eCH verwechselbar.</div>
      <div class="datenstand"><b>Datenstand</b> — wann die zugrunde liegenden Fakten galten (nicht nur, wann die Datei gebaut wurde): ${esc(datenstandText())}</div>
    </div>
  </div>
  <h4 class="hscope" id="glossar">Glossar — die wichtigsten Begriffe</h4>
  <div class="card"><dl class="gloss">${GLOSSAR.map(g=>`<div id="gl-${esc(g.id)}"><dt>${esc(g.wort)}</dt><dd>${esc(g.text)}</dd></div>`).join('')}</dl></div>
  <h4 class="hscope">Kennzahlen im Detail</h4>
  <div class="hometiles">
    ${tile(nf(KE.von),'atomare Datenpunkte','katalog')}
    ${tile(pctTxt(KE.wert,KE.von),'atomare Datenpunkte mit eCH-Element','katalog')}
    ${tile(nf(UE.formulare_div),'Formulare mit Standard-Divergenz','todo','divergenz')}
    ${tile(nf((DATA.begriffe||[]).reduce((n,b)=>n+b.labels.filter(l=>l.klasse==='variante').length,0)),`verschiedene Bezeichnungen anzugleichen (auf ${pl(BEN_T.variante,'Datenpunkt','Datenpunkten')})`,'begriffe','angleichen')}
    ${tile(nf(BEN.begriff_felder),`${catUnitOf('begriff')[1]} umzubenennen oder aufzuteilen`,'todo','begriff')}
    ${tile(nf(K.length),'verschiedene Attribute','katalog')}
    ${tile((DATA.esh_katalog||[]).length,'eSH-Entwürfe','esh')}
    ${tile(DATA.services.filter(s=>s.dvsh).length,'Services im DVSH modelliert','fields')}
    ${(()=>{const noF=DATA.services.filter(x=>!(formsByService[x.id]||[]).length), dv=noF.filter(x=>x.dvsh).length;
      return tile(nf(noF.length),`Services ohne Formular (${nf(dv)} mit DVSH-Modellierung, ${nf(noF.length-dv)} ohne)`,'fields');})()}
    ${tile(DATA.services.filter(s=>s.shep).length,'auf SHEP publiziert','fields')}
    ${tile(F.length,'Formulare','fields')}
    ${tile(nf(nDf),'Datenfelder','fields')}
    ${tile(H.length,'Regeln, Zitat PDF-verifiziert','rules')}
    ${tile(nOver,'Felder ohne Grundlage','register')}
    ${tile(nAuf,'aufgabennotwendig ohne Norm','register')}
    ${nA5?tile(nA5,'⛨ aufgabennotwendig, Art.-5-Grundlage offen','recherche','sensibel_art5'):''}
    ${tile(nSens,'⛨ sensible Felder','register')}
    ${tile((DATA.themenkatalog||[]).filter(t=>t.n_services).length,'Themengruppen mit Services (eCH-0049)','lebenslagen')}
  </div>
  <h4 class="hscope">Verlauf der Kennzahlen</h4>
  <p class="hint">Ein Eintrag je Tag (die letzte Aktualisierung des Tages gilt). Einträge mit Quelle «Git-Historie» sind aus früheren Ständen der Databank
  rekonstruiert; «—» heisst: in jenem Stand noch nicht erhoben. Offene Punkte nach wer handelt: rot = ${esc(tonLabel('act'))} · amber = ${esc(tonLabel('dec'))} · grau = ${esc(tonLabel('open'))}.</p>
  ${VERLAUF.length?`<div class="card tscroll"><table class="ft vltab"><thead><tr><th>Stand · Quelle</th><th>Umfang</th><th>Datenstandard</th><th>Rechtsgrundlage (Datenfelder)</th><th>Verzeichnis (Formulare)</th><th>Offene Punkte</th></tr></thead><tbody>${vrows}</tbody></table></div>`
    :'<div class="nores">Noch kein Verlauf erfasst.</div>'}`;
  m.querySelectorAll('.hometile').forEach(b=>b.onclick=()=>{
    state.tab=b.dataset.go; state.service='all'; state.sub=b.dataset.sub||'felder'; render();});
  wireGo(m);
}
// ---------- Gestaltung der Formulare (#gestaltung): how the Formulare look ----------
// The page opens like the start page — one question, a handful of doors (the readers first, then the
// groups) —, then one section per group with one block per Merkmal: the practice (or none), the
// measured values as a NEUTRAL list (ink and grey: a value is no finding), the findings as chips in
// their tone, the Formulare concerned folded. The Merkmale without a clear practice, the comparison
// per Dienststelle and the limits of the measurement follow. Every figure is the export's
// (DATA.gestaltung, also the figure of each door); the page counts nothing itself. The texts describe
// what differs — they never ask an office to change its Formular. Section addresses:
// #gestaltung/all/<gruppe> · m-<merkmal> · e-<merkmal> (an open decision) · kanton · dienststellen ·
// grenzen.
const GTON=['ok','act','dec','open'];
// a finding (verdict) and its tone; its name for one Merkmal (merkmale[].urteil_labels) or for a
// count over many Formulare (labels.urteil_gesamt) where the layer gives one
const gUrteil=(u,o)=>{const x=((GL.urteil||{})[u])||{label:'⟨'+u+'⟩',ton:null}, p=o||{};
  const lbl=(p.m&&p.m.urteil_labels&&p.m.urteil_labels[u])||(p.gesamt&&(GL.urteil_gesamt||{})[u])||x.label;
  return {label:lbl,ton:GTON.includes(x.ton)?x.ton:null};};
// a measured value or a sentence of the layer, escaped; a number keeps its unit on its line («30 %», «8 pt», «+41 …»)
const gx=v=>esc(v).replace(/(\d) (?=%|pt\b|…)/g,'$1 ').replace(/ …/g,' …');
const gMerkmal=k=>(GL.merkmal||{})[k]||('⟨'+k+'⟩');
// the four tones in the words of this layer: the findings of a tone, what the tone adds to them, the
// whole sentence (a tooltip)
const gTonWords=t=>Object.values(GL.urteil||{}).filter(x=>x.ton===t).map(x=>x.label).join(' / ');
const gTonZusatz=t=>(GL.ton_zusatz||{})[t]||'';
const gTonTip=t=>(GL.ton||{})[t]||'';
// a finding as a chip: in its tone (colour, symbol and word), or outlined and neutral where it has
// none (Hinweis, betroffen, entfällt). On a Formular the canton's open decision («keine klare
// Praxis») is neutral as well: it is drawn once per Merkmal, on the page
function gChip(u,n,opt){
  const o=opt||{}, U=gUrteil(u,o), t=o.form&&U.ton==='dec'?null:U.ton;
  const lbl=esc(U.label), num=n!=null?` <b class="sumn">${nf(n)}</b>`:'', tip=o.tip?` title="${esc(o.tip)}"`:'';
  return t?`<span class="tchip badge st-${t}"${tip}><i class="sw t-${t}"></i>${lbl}${num}</span>`
    :`<span class="tchip badge mk"${tip}>${lbl}${num}</span>`;
}
// the amber chip of a Merkmal that waits for the canton: no clear practice, or no rule at all
const gDecChip=m=>m&&m.art==='regel_offen'
  ?`<span class="tchip badge st-dec"><i class="sw t-dec"></i>${esc(lab(GL.art,'regel_offen'))} — der Kanton legt fest</span>`
  :gChip('uneinheitlich');
// the kind of a Merkmal as a badge that explains itself (labels.art, labels.art_erklaerung)
const gArt=a=>mkBadge(esc(lab(GL.art,a)),(GL.art_erklaerung||{})[a]||'');
// a finding in a list of the most frequent ones: «Abweichung», «Lücke» (labels.urteil_nomen)
const gNomen=u=>(GL.urteil_nomen||{})[u]||gUrteil(u).label;
// the value one Formular shows for a Merkmal (form.gestaltung — as measured, never recomputed)
const gWert=(f,k)=>{const x=f&&f.gestaltung&&(f.gestaltung.merkmale||[]).find(y=>y.k===k); return x?x.w:null;};
// a list of Formulare, each linking to its Formular-Ansicht with the panel «Gestaltung» open;
// the first GCAP are drawn, «weitere N anzeigen» draws the rest (Back/Forward draws it again)
const GCAP=24;
let _gN=0; const _gRest={};
function gFormItem(fid,k){
  const f=formById[fid]; if(!f) return `<li>Formular ${esc(fid)}</li>`;
  const w=k?gWert(f,k):null;
  return `<li>${formLink(f.service_id,f.id,esc(f.title),'dlink lt','gest')} <span class="small muted">· ${esc(f.dienststelle||'')}${w?' · '+gx(w):''}</span></li>`;
}
function gFormList(ids,k){
  const by=x=>{const f=formById[x]||{}; return [String((k&&gWert(f,k))||''),String(f.dienststelle||''),String(f.title||'')];};
  const L=(ids||[]).slice().sort((a,b)=>{const x=by(a), y=by(b);
    for(let i=0;i<3;i++){const c=x[i].localeCompare(y[i],'de'); if(c) return c;} return a-b;});
  const id='gl'+(_gN++), rest=L.slice(GCAP);
  if(rest.length) _gRest[id]={ids:rest,k};
  return `<ul class="gfll" id="${id}">${L.slice(0,GCAP).map(x=>gFormItem(x,k)).join('')}</ul>${
    rest.length?`<button type="button" class="gmorebtn" data-showmore="${id}">weitere ${nf(rest.length)} anzeigen</button>`:''}`;
}
const gFolded=(summary,body,open)=>`<details class="gfl"${open?' open':''}><summary>${summary}</summary>${body}</details>`;
// the measured values as a neutral list: value, a grey bar, the number — the practice is named
// («Praxis», bold), never coloured. The numbers add up to the total the caption states (.sumbox)
function gDist(vert,total,cap,praxisW){
  const F=6, L=vert||[];
  const rows=L.map((v,i)=>{const p=praxisW!=null&&v.w===praxisW;
    return `<li${p?' class="gp"':''}${i>=F?' hidden data-gx':''}><span class="gdl">${gx(v.w)}${p?' <span class="gpm">Praxis</span>':''}</span>`
      +`<span class="gdb" aria-hidden="true"><i style="width:${total?(100*v.n/total).toFixed(1):0}%"></i></span><b class="gdn sumn">${nf(v.n)}</b></li>`;}).join('');
  const more=L.length>F?`alle ${nf(L.length)} Werte zeigen`:'';
  return `<div class="sumbox"><div class="gcap">${cap}</div><ul class="gdist">${rows}</ul>${
    more?`<button type="button" class="gmorebtn" data-gx data-label="${more}" aria-expanded="false">${more}</button>`:''}</div>`;
}
// every finding of a Merkmal over all Formulare, in the order of the layer's labels
function gUrteile(m){
  const U=m.urteile||{};
  return `<div class="sumbox"><div class="gcap">Befunde über alle <b class="sumtot">${nf(GEST.bestand.formulare)}</b> Formulare</div><div class="gurt">${
    Object.keys(GL.urteil||{}).filter(u=>U[u]).map(u=>gChip(u,U[u],{m,gesamt:1})).join(' ')}</div></div>`;
}
const gEntscheidOf=k=>(GEST.entscheide||[]).find(e=>e.key===k);
function gPraxis(m){
  if(m.praxis) return `<div class="gpr">Praxis: <b>${gx(m.praxis.w)}</b> — ${nf(m.praxis.n)} von ${nf(m.n_gemessen)} gemessenen Formularen (${nf1(100*m.praxis.anteil)} %)</div>`;
  const e=gEntscheidOf(m.key);
  return e?`<div class="gpr">${gDecChip(m)} ${goLink('gestaltung','e-'+m.key,`Ohne Vorgabe in der Databank: «${esc(e.label)}» ›`,'inl')}</div>`:'';
}
// a list of written forms with their counts: each «form» N on one line, the separator at its end
const gMuster=L=>(L||[]).map((x,i,a)=>`<span class="nowrap">«${esc(x.w)}» ${nf(x.n)}${i<a.length-1?' ·':''}</span>`).join(' ');
// what the overview says beside a Merkmal (merkmale[].zusatz), in plain sentences
function gZusatz(m){
  const z=m.zusatz; if(!z) return '';
  const L=`<b>${esc(z.label)}:</b> `;
  if(m.key==='akzentfarbe') return `<div class="gzus">${L}${nf(z.farben_gemessen)} Formulare mit gemessenen Farben, davon ${nf(z.office)} Word- und Excel-Dateien
    (${nf(z.office_mit_farbe)} mit einer Farbe, ${nf(z.office_ohne_farbe)} ohne) — ihre Farben sind genannt, aber nicht verglichen.
    Unter den PDF-Formularen zeigen ${nf(z.pdf_mit_linkfarbe)} farbige Internet- oder E-Mail-Adressen, ${nf(z.pdf_mit_feldfarbe)} farbige Formularfelder
    und ${nf(z.pdf_mit_kopfmarke)} eine kleine Farbmarke im Kopf der ersten Seite; keine davon zählt als Akzentfarbe.
    Von den ${nf(z.pdf_ohne_akzent)} PDF-Formularen ohne Akzentfarbe tragen ${nf(z.pdf_ohne_akzent_mit_bild)} auf der ersten Seite ein Bild, dessen Farben nicht gemessen sind;
    ${nf(z.pdf_ohne_akzent_farbe_unter_schwelle)} zeigen eine Farbe unter der Schwelle.</div>`;
  if(m.key==='bf_tags') return `<div class="gzus">${L}Von den ${nf(z.getaggt)} getaggten PDF-Formularen binden ${nf(z.ohne_formularfelder)} ihre Formularfelder nicht in den Strukturbaum ein,
    und ${nf(z.ohne_ueberschriften)} tragen dort keine Überschriften.</div>`;
  if(m.key==='tel_erklaerung'&&(z.dienststellen||[]).length) return `<div class="gzus">${L}${z.dienststellen.map(d=>`${goLink('dienststellen',d.slug,esc(d.name),'dlink lt')} ${nf(d.n)}`).join(' · ')}</div>`;
  if(m.key==='tel_format') return `<div class="gzus">${L}${nf(z.n_mehrfach)} von ${nf(z.n_nummern)} gedruckten Nummern stehen auf den Formularen in mehr als einer Schreibweise.
    ${gFolded('Schreibweisen anzeigen (9 steht für eine Ziffer)',`<div class="gvw">Alle gedruckten Nummern: ${gMuster(z.schreibweisen)}</div>${
      (z.nummern||[]).length?`<ul class="gfll">${z.nummern.map(x=>`<li><span class="mono">${esc(x.nummer)}</span>: ${(x.schreibweisen||[]).map(y=>`«${esc(y.w)}» auf ${pl(y.n,'Formular','Formularen')}`).join(' · ')}</li>`).join('')}</ul>`:''}`)}</div>`;
  if(m.key==='seitenzahlen') return `<div class="gzus">${L}${gMuster(z.muster)} <span class="small">(n steht für die Seite, N für die Zahl der Seiten)</span></div>`;
  return '';
}
function gBlock(m){
  const lists=Object.keys(m.formulare||{}).map(u=>{const ids=m.formulare[u]||[]; if(!ids.length) return '';
    // a value is shown beside each Formular — not where it would only repeat «nicht messbar»
    return gFolded(`${pl((m.urteile||{})[u]!=null?m.urteile[u]:ids.length,'Formular','Formulare')} anzeigen — ${esc(gUrteil(u,{m,gesamt:1}).label)}`,gFormList(ids,u==='nicht_messbar'||u==='nicht_gemessen'?null:m.key));}).join('');
  return `<div class="card gm" id="gm-${esc(m.key)}"><div class="gmhd"><h5>${esc(m.label)}</h5> ${gArt(m.art)}</div>
    <p class="gmq">${esc(m.frage)}</p>${gPraxis(m)}
    <div class="gcols">${gDist(m.verteilung,m.n_gemessen,`Verteilung: <b class="sumtot">${nf(m.n_gemessen)}</b> ${esc(m.basis)}`,m.praxis?m.praxis.w:null)}${gUrteile(m)}</div>
    ${gZusatz(m)}${lists}
    <details class="gwie"><summary>Wie gemessen</summary><p>${gx(m.erklaerung)}</p></details></div>`;
}
// one Merkmal without a clear practice or rule: what is open, what is to be decided, the values the
// Formulare show, the Formulare per value
function gEntscheid(e){
  const m=GM[e.key]||{}, kl=m.art==='regel_offen';
  const total=kl?((m.urteile||{}).betroffen||0):m.n_gemessen;
  const per=(e.verteilung||[]).map(v=>`<div class="gvw"><b>${gx(v.w)}</b> · ${pl(v.n,'Formular','Formulare')}</div>${gFormList(v.formulare||[],e.key)}`).join('');
  return `<div class="card gm" id="ge-${esc(e.key)}"><div class="gmhd"><h5>${esc(e.label)}</h5> ${gDecChip(m)}</div>
    <p class="gpr">${gx(e.was)}</p>${e.frage?`<p class="gzue"><span class="hsl">Zu entscheiden</span> ${gx(e.frage)}</p>`:''}
    <div class="gcols">${gDist(e.verteilung,total,`Verteilung: <b class="sumtot">${nf(total)}</b> ${kl?'Formulare, die es betrifft':esc(m.basis||'')}`,null)}
      <div>${gFolded('Formulare je Wert anzeigen',per)}<div class="gmlink">${goLink('gestaltung','m-'+e.key,`Zum Merkmal «${esc(gMerkmal(e.key))}» ›`,'inl')}</div></div></div></div>`;
}
// the most frequent Abweichungen and Lücken of a Dienststelle: «Merkmal: Lücke bei N»
const gTopItem=(t,lang)=>`${esc(gMerkmal(t.key))}: ${esc(gNomen(t.u))} bei ${lang?pl(t.n,'Formular','Formularen'):nf(t.n)}`;
// per Dienststelle (overview.dienststellen), in the order of «Für Dienststellen» (by Departement,
// A–Z inside): Abweichungen and Lücken apart, each adding up to the canton's (.sumbox, data-s)
function gDstTabelle(){
  const K=GEST.kennzahlen, B=GEST.bestand, A=(GEST.dienststellen||[]).filter(d=>d.n_formulare);
  const depOf=Object.fromEntries(DST.map(d=>[d.slug,(d.department||'(ohne Departement)').trim()]));
  const deps={}; A.forEach(d=>{const k=depOf[d.slug]||'(ohne Departement)'; (deps[k]=deps[k]||[]).push(d);});
  // a separator stays at the end of its line, never at the start of the next
  const topL=d=>(d.top||[]).map((t,i,a)=>`<span class="gtop">${goLink('gestaltung','m-'+t.key,esc(gMerkmal(t.key)),'dlink lt')}: ${esc(gNomen(t.u))} bei ${nf(t.n)}${i<a.length-1?' ·':''}</span>`);
  const dash='<span class="muted">—</span>', ml=t=>`<span class="gml" aria-hidden="true">${t}</span>`;
  const row=d=>{const T=topL(d), mess=d.act_je_formular!=null;
    return `<tr><td>${goLink('dienststellen',d.slug,esc(d.name),'dlink')}${T.length?`<div class="nw small">Häufigste Abweichungen und Lücken: ${T.join(' ')}</div>`:''}</td>
    <td class="num">${ml('gemessen')}${nf(d.n_gemessen)} <span class="muted">von ${nf(d.n_formulare)}</span>${d.n_nicht_messbar?`<div class="small muted">${nf(d.n_nicht_messbar)} nicht messbar</div>`:''}</td>
    <td class="num">${ml('Abweichungen')}${mess?`<b class="sumn" data-s="ab">${nf(d.n.abweichungen)}</b>`:dash}</td>
    <td class="num">${ml('Lücken')}${mess?`<b class="sumn" data-s="lu">${nf(d.n.luecken)}</b>`:dash}</td>
    <td class="num">${ml('je Formular')}${mess?nf1(d.act_je_formular):dash}</td>
    <td class="num">${ml('Schriften')}${mess?nf(d.schriften):dash}</td><td class="num">${ml('Grundgrössen')}${mess?nf(d.groessen):dash}</td><td class="num">${ml('Akzentfarben')}${mess?nf(d.akzente):dash}</td>
    <td class="small wd">${T.length?T.map(x=>x.replace(/ ·<\/span>$/,'</span>')).join('<br>'):dash}</td></tr>`;};
  const rows=Object.keys(deps).sort(deptCmp).map(dep=>`<tr class="gdep"><td colspan="9"><b>${esc(dep)}</b> <span class="muted">· ${pl(deps[dep].length,'Dienststelle','Dienststellen')}</span></td></tr>`
    +deps[dep].slice().sort((a,b)=>a.name.localeCompare(b.name,'de')).map(row).join('')).join('');
  const ohne=B.dienststellen_ohne_formular||0;
  return `<div class="card tscroll sumbox"><table class="ft gdst"><thead><tr><th>Dienststelle</th><th class="num">Formulare gemessen</th>
      <th class="num" title="Abweichungen von der Praxis, gezählt je Formular und Merkmal">${SW('act')}Abweichungen von der Praxis</th>
      <th class="num" title="Lücken — ein geprüftes Merkmal fehlt, zum Beispiel ein Mindestmerkmal der Barrierefreiheit; gezählt je Formular und Merkmal">${SW('act')}Lücken</th>
      <th class="num" title="Abweichungen und Lücken je Formular, dessen Inhalt gemessen ist (ohne Dateien in einem alten Format)">je Formular</th>
      <th class="num" title="Verschiedene Schriften unter ihren gemessenen Formularen">Schriften</th>
      <th class="num" title="Verschiedene Grundgrössen der Schrift unter ihren gemessenen Formularen">Grund&shy;grössen</th>
      <th class="num" title="Verschiedene Akzentfarben unter ihren PDF-Formularen — «keine Akzentfarbe» zählt nicht">Akzent&shy;farben</th>
      <th class="wd">Häufigste Abweichungen und Lücken (Formulare)</th></tr></thead><tbody>
    <tr class="dgrp"><td>Ganzer Kanton</td><td class="num">${ml('gemessen')}${nf(B.gemessen)} <span class="muted">von ${nf(B.formulare)}</span></td><td class="num">${ml('Abweichungen')}<b class="sumtot" data-s="ab">${nf(K.abweichungen)}</b></td><td class="num">${ml('Lücken')}<b class="sumtot" data-s="lu">${nf(K.luecken)}</b></td><td></td><td></td><td></td><td></td><td class="wd"></td></tr>
    ${rows}</tbody></table></div>${ohne?`<p class="hint">${pl(ohne,'Dienststelle','Dienststellen')} ohne Formular in der Databank ${plw(ohne,'ist','sind')} nicht aufgeführt. «—»: keine Datei der Dienststelle ist gemessen — ihre Formulare sind eFormulare der Plattform oder in einem alten Format.</p>`:''}`;
}
// the keyboard follows a jump within a page: the heading of the target (or its summary) takes the
// focus without scrolling again — not away from a field the reader is typing in
function focusIn(t){
  const ae=document.activeElement; if(ae&&/^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName)) return;
  const h=t.tagName==='DETAILS'?t.querySelector(':scope>summary')
    :(t.querySelector(':scope>h4,:scope>.gmhd>h5,:scope>.cathd,:scope>.dvsub')||t);
  if(!h) return;
  if(h.tagName!=='SUMMARY'&&!h.hasAttribute('tabindex')){h.setAttribute('tabindex','-1'); h.setAttribute('data-jump','');}
  h.focus({preventScroll:true});
}
// a section named in the address: open it (the limits are folded), bring it into view and give it
// the focus — after render() has put a new page at its top, hence the timeout
function gFocus(m,k){
  if(!k||comingBack()) return;
  setTimeout(()=>{const id=k.startsWith('m-')?'gm-'+k.slice(2):k.startsWith('e-')?'ge-'+k.slice(2):'gs-'+k;
    const t=document.getElementById(id); if(!t||!m.contains(t)) return;
    if(k==='grenzen') t.querySelectorAll('details').forEach(d=>{d.open=true;});
    t.scrollIntoView({behavior:MOTION}); focusIn(t); t.classList.add('flash'); setTimeout(()=>t.classList.remove('flash'),1600);},0);
}
// the buttons of the page: the rest of a list of Formulare, all values of a distribution
function gWire(root){
  root.querySelectorAll('button.gmorebtn[data-showmore]').forEach(b=>b.onclick=()=>{
    const id=b.dataset.showmore, r=_gRest[id], ul=document.getElementById(id); if(!r||!ul) return;
    const had=document.activeElement===b, n0=ul.children.length;
    ul.insertAdjacentHTML('beforeend',r.ids.map(x=>gFormItem(x,r.k)).join(''));
    ul.setAttribute('data-shown',id); b.remove(); wireGo(ul);
    // the keyboard stays in the list: on the first Formular that was added
    if(had){const a=ul.children[n0]&&ul.children[n0].querySelector('a'); if(a) a.focus({preventScroll:true});}});
  root.querySelectorAll('button.gmorebtn[data-gx]').forEach(b=>b.onclick=()=>{
    const box=b.closest('.sumbox'), on=b.getAttribute('aria-expanded')!=='true';
    if(box) box.querySelectorAll('li[data-gx]').forEach(li=>{li.hidden=!on;});
    b.setAttribute('aria-expanded',String(on)); b.textContent=on?'weniger zeigen':b.dataset.label;});
}
function viewGestaltung(){
  const m=document.getElementById('main');
  if(!GEST){m.innerHTML=pageHead('Gestaltung der Formulare','Dieser Export enthält keine Messung der Gestaltung.')
    +`<div class="nores">${goLink('home','','Zur Übersicht ›','inl')}</div>`; wireGo(m); return;}
  _gN=0; Object.keys(_gRest).forEach(k=>{delete _gRest[k];});
  const B=GEST.bestand, K=GEST.kennzahlen, MA=GL.messart||{};
  const sub=(state.sub&&state.sub!=='felder')?state.sub:null;
  const known=new Set([...GGRP.map(g=>g.key),'kanton','dienststellen','grenzen',
    ...Object.keys(GM).map(k=>'m-'+k),...(GEST.entscheide||[]).map(e=>'e-'+e.key)]);
  const bad=sub&&!known.has(sub); if(bad) state.sub='felder';
  // «Wo anfangen?»: the readers first (a Dienststelle, the canton), then one door per group — each
  // with ONE figure of the export (gruppen[].kennzahl)
  const door=(sub,k,q,f)=>`<a class="door" href="#gestaltung/all/${esc(sub)}" data-go="gestaltung" data-sub="${esc(sub)}"><span class="dk">${k}</span><span class="dq">${q}</span>${f?`<span class="dz"><b>${f[0]}</b> ${f[1]}</span>`:''}</a>`;
  const doors=door('dienststellen','Je Dienststelle','Wie unterscheiden sich die Formulare der einzelnen Dienststellen?',[nf(B.dienststellen_gemessen),`${plw(B.dienststellen_gemessen,'Dienststelle','Dienststellen')} mit gemessenen Formularen — Abweichungen, Lücken, Schriften und Farben je Dienststelle`])
    +door('kanton','Für den Kanton','Was ist festzulegen, wo die Formulare keine klare Praxis zeigen?',[nf(K.dec),`${plw(K.dec,'Merkmal','Merkmale')} ohne klare Praxis oder Regel — eine Vorgabe liegt der Databank nicht vor`])
    +GGRP.map(g=>door(g.key,esc(g.label),esc(g.frage),g.kennzahl?[nf(g.kennzahl.n),esc(g.kennzahl.text)]:null)).join('');
  const sec=(id,title,body)=>`<section class="gstsec" id="gs-${esc(id)}"><h4>${title}</h4>${body}</section>`;
  // the first use of a term of the glossary explains itself (term())
  const frage=g=>g.key==='barrierefrei'?esc(g.frage).replace('Mindestmerkmale',term('mindestmerkmale','Mindestmerkmale')):esc(g.frage);
  const groups=GGRP.map(g=>sec(g.key,esc(g.label),`<p class="gfrage">${frage(g)}</p>${g.vorbehalt?`<p class="gvorb">${esc(g.vorbehalt)}</p>`:''}`
    +(GEST.merkmale||[]).filter(x=>x.gruppe===g.key).map(gBlock).join(''))).join('');
  const ENT=GEST.entscheide||[];
  const kanton=sec('kanton','Für den Kanton — Merkmale ohne klare Praxis',`<p class="gfrage">Bei ${pl(K.dec,'Merkmal','Merkmalen')} zeigen die Formulare keine klare Praxis, oder es gibt keine Regel. ${esc(GL.entscheide||'')}</p>
    <p class="gvorb">Nicht in den offenen Punkten des Datenstandards gezählt — die Seite «Für den Kanton» weist nur auf sie hin.</p>`
    +(ENT.length?ENT.map(gEntscheid).join(''):'<div class="nores">Kein Merkmal ohne klare Praxis.</div>'));
  const dst=sec('dienststellen','Je Dienststelle',`<p class="gfrage">Wie viele Abweichungen von der Praxis und wie viele Lücken die Formulare einer Dienststelle zeigen und wie viele verschiedene Schriften, Grundgrössen und Akzentfarben sie verwenden — die Dienststelle öffnet ihr Briefing.</p>
    <p class="gvorb">Die meisten Lücken sind Eigenschaften der Datei — Dokumenttitel, Feldbeschreibungen, eingebettete Schriften, Struktur-Tags, Dokumentsprache —, nicht das sichtbare Aussehen.</p>`+gDstTabelle());
  const grenzen=sec('grenzen','Grenzen der Messung',gFolded(`Alle ${nf((GEST.grenzen||[]).length)} Punkte anzeigen — was die Messung nicht sieht und was ein Befund nicht heisst`,
    `<ul class="ggrenz">${(GEST.grenzen||[]).map(t=>`<li>${gx(t)}</li>`).join('')}</ul>`,sub==='grenzen'));
  const arten=Object.keys(GL.art||{}).map(a=>`<br><b>${esc(lab(GL.art,a))}</b> — ${esc((GL.art_erklaerung||{})[a]||'')}`).join('');
  m.innerHTML=pageHead('Gestaltung der Formulare',
    `Wie die Formulare aussehen — und wo ein Formular von der ${term('praxis','Praxis')} der anderen abweicht.`,
    `Für jedes Merkmal der Gestaltung — ${GGRP.map(g=>esc(g.label)).join(', ')} —, welche Werte die Formulare zeigen, ob es eine Praxis gibt und welche Formulare davon abweichen; dazu die Merkmale ohne klare Praxis, die der Kanton festlegt, der Vergleich je Dienststelle und die Grenzen der Messung. Die Seite beschreibt, was sich unterscheidet; sie verlangt von keiner Dienststelle, ein Formular zu ändern.`,
    `Gemessen an den veröffentlichten Dateien der ${nf(B.mit_datei)} Formulare mit eigener Datei (PDF, Word, Excel) — Methode ${esc(GEST.methode||'—')}, Stand der Messung ${fmtDate(GEST.stand)}. Die ${nf(B.ohne_datei)} eFormulare der Plattform haben keine eigene Datei. Ein Corporate-Design-Handbuch des Kantons liegt der Databank nicht vor. Die Zahlen dieser Seite gehören nicht zu den offenen Punkten des Datenstandards und nicht zu den Kennzahlen der Startseite.`,
    `Massstab ist die Praxis der gemessenen Formulare: ein Wert, den mindestens zwei Drittel von ihnen teilen. Die Farbe steht nur bei einem Befund, nie bei einem gemessenen Wert:${GTON.map(t=>`<br>${SW(t)}<b>${esc(gTonWords(t))}</b> — ${esc(gTonZusatz(t))}`).join('')}<br>Ohne Farbe: «${esc(gUrteil('hinweis').label)}» und «${esc(gUrteil('betroffen',{gesamt:1}).label)}» — eine Feststellung ohne Bewertung.<br><br>Jedes Merkmal trägt seine Art:${arten}`)
    +(bad?`<div class="nores">Den Abschnitt «${esc(sub)}» gibt es auf dieser Seite nicht — gezeigt wird die ganze Seite.</div>`:'')
    +`<div class="tonkey"><span>Farbe nur bei einem Befund — er beschreibt einen Unterschied und verlangt keine Änderung:</span>${GTON.map(t=>`<span class="tk" title="${esc(gTonTip(t))}"><i class="sw t-${t}"></i>${esc(gTonWords(t))}</span>`).join(' ')}</div>
    <div class="regstats"><span class="rstat">Formulare <b>${nf(B.formulare)}</b></span>
      <span class="rstat">gemessen <b>${nf(B.gemessen)}</b> <span class="small muted">— ${Object.entries(B.messart||{}).map(([k,n])=>`${esc(lab(MA,k))} ${nf(n)}`).join(' · ')}</span></span>
      <span class="rstat">eFormulare ohne eigene Datei <b>${nf(B.ohne_datei)}</b></span>
      <span class="rstat">Abweichungen <b>${nf(K.abweichungen)}</b> · Lücken <b>${nf(K.luecken)}</b> <span class="small muted">(je Formular und Merkmal)</span></span></div>
    <section class="hsec"><h4>Wo anfangen?</h4><div class="doors gdoors">${doors}</div></section>
    ${groups}${kanton}${dst}${grenzen}
    <div class="datenstand"><b>Stand der Messung</b> ${fmtDate(GEST.stand)} · Methode ${esc(GEST.methode||'—')} · erstellt ${fmtDate((DATA.datenstand||{}).build||DATA.generated_at||'')}</div>`;
  gWire(m); wireGo(m); gFocus(m,bad?null:sub);
}
// the panel «Gestaltung» of one Formular (form.gestaltung): folded, one line of summary; open,
// one row per Merkmal — label, finding, value, the practice where the value differs, the remarks
// of the measurement. What cannot be measured is said once, with its reason, not row by row
function gestPanel(fm,open){
  const g=fm.gestaltung; if(!g||!GEST) return '';
  const head='<span class="dvsub">Gestaltung</span>';
  if(g.entfaellt) return `<div class="card gpanel" id="gest-${esc(fm.id)}">${head} <span class="gsumm">${esc(GL.eformular||'')}</span></div>`;
  const n=g.n||{}, L=g.merkmale||[];
  const OFFEN=['nicht_messbar','nicht_gemessen'], mess=L.filter(x=>!OFFEN.includes(x.u));
  // the summary says as many as the rows show: n.dec = the rows «keine klare Praxis» and
  // «betroffen» — the Merkmale of this Formular that wait for the canton
  const sum=[g.messart?esc(lab(GL.messart,g.messart)):esc(gUrteil('nicht_gemessen').label),
    n.act?`${SW('act')}${pl(n.act,'Abweichung oder Lücke','Abweichungen oder Lücken')}`:(mess.length?'keine Abweichung und keine Lücke':''),
    n.dec?`${pl(n.dec,'Merkmal','Merkmale')} ohne Vorgabe in der Databank — der Kanton legt fest`:'',
    n.open?`${SW('open')}${pl(n.open,'Merkmal','Merkmale')} ${g.messart?'nicht messbar':'noch nicht gemessen'}`:''].filter(Boolean).join(' · ');
  // the remarks of the measurement, verbatim (data-wortlaut: the page check reads no program word in them)
  const dl=d=>(d||[]).length?`<ul class="gfd" data-wortlaut>${d.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'';
  const tipDec='Keine klare Praxis: Kein Wert erreicht zwei Drittel der gemessenen Formulare, und der Databank liegt keine Vorgabe vor. Das betrifft nicht dieses Formular allein — der Kanton legt einmal je Merkmal fest (Seite «Gestaltung der Formulare», Abschnitt «Für den Kanton»).';
  const rows=GGRP.map(gr=>{const R=mess.filter(x=>(GM[x.k]||{}).gruppe===gr.key); if(!R.length) return '';
    return `<div class="gfgrp">${esc(gr.label)}</div>`+R.map(x=>`<div class="gfr"><div>${goLink('gestaltung','m-'+x.k,esc(gMerkmal(x.k)),'dlink lt')}</div>
      <div>${gChip(x.u,null,{form:1,m:GM[x.k],tip:x.u==='uneinheitlich'?tipDec:''})} <span class="gfw">${gx(x.w||'')}</span>${x.u==='weicht_ab'&&x.p?` <span class="muted">· Praxis: ${gx(x.p)}</span>`:''}${dl(x.d)}</div></div>`).join('');}).join('');
  const offen=OFFEN.map(u=>{const R=L.filter(x=>x.u===u); if(!R.length) return '';
    return `<div class="gfgrp">${esc(gUrteil(u).label)}</div><div class="gfr gfr1"><div>${gChip(u,null,{form:1})} ${R.map(x=>esc(gMerkmal(x.k))).join(', ')}${dl([...new Set(R.flatMap(x=>x.d||[]))])}</div></div>`;}).join('');
  return `<details class="card gpanel" id="gest-${esc(fm.id)}"${open?' open':''}><summary>${head} <span class="gsumm">${sum}</span></summary>
    ${rows}${offen}<div class="gfoot">Verglichen mit den übrigen Formularen; beschreibt, was sich unterscheidet, und verlangt keine Änderung — ${goLink('gestaltung','','Gestaltung der Formulare ›','inl')}</div></details>`;
}
// the Formular-Ansicht opened at its panel «Gestaltung» (#…/form-<id>~gest): open, in view, focused
function focusGest(fid){
  if(comingBack()) return;
  setTimeout(()=>{const t=document.getElementById('gest-'+fid); if(!t) return; if(t.tagName==='DETAILS') t.open=true;
    t.scrollIntoView({behavior:MOTION}); focusIn(t); t.classList.add('flash'); setTimeout(()=>t.classList.remove('flash'),1600);},0);
}
// the short section of a Dienststelle's briefing: its counts as the overview holds them — a part of
// its own, never in the open points of the briefing, and no Massnahme
function gestBrief(d){
  const g=GEST&&(GEST.dienststellen||[]).find(x=>x.slug===d.slug);
  if(!g||!g.n_formulare) return '';
  const top=(g.top||[]).map(t=>gTopItem(t,true)).join(' · ');
  // nothing measured: say why — all eFormulare (no file of their own), or no measured file
  const alleE=(d.formulare||[]).length&&(d.formulare||[]).every(id=>{const f=formById[id]; return f&&f.gestaltung&&f.gestaltung.entfaellt;});
  const nichts=alleE
    ?(g.n_formulare===1?'Ihr einziges Formular ist ein eFormular der Plattform: Es hat keine eigene Datei und kein eigenes Erscheinungsbild.'
      :`Alle ${nf(g.n_formulare)} Formulare sind eFormulare der Plattform: Sie haben keine eigene Datei und kein eigenes Erscheinungsbild.`)
    :(g.n_formulare===1?'Ihr Formular hat keine gemessene Datei.':`Keines ihrer ${nf(g.n_formulare)} Formulare hat eine gemessene Datei.`);
  const body=g.n_gemessen
    ?`<div class="dsline"><span><b>${nf(g.n_gemessen)}</b> von ${pl(g.n_formulare,'Formular','Formularen')} gemessen${g.n_nicht_messbar?` (${pl(g.n_nicht_messbar,'Datei','Dateien')} in einem alten Format, nicht messbar)`:''} · <b>${nf(g.n.abweichungen)}</b> ${plw(g.n.abweichungen,'Abweichung','Abweichungen')} von der Praxis · <b>${nf(g.n.luecken)}</b> ${plw(g.n.luecken,'Lücke','Lücken')} (je Formular und Merkmal gezählt${g.act_je_formular!=null?`; zusammen ${nf1(g.act_je_formular)} je Formular mit gemessenem Inhalt`:''})${g.n.open?` · ${pl(g.n.open,'Merkmal','Merkmale')} nicht messbar`:''}</span></div>
      ${top?`<div class="dsline"><span>Häufigste Abweichungen und Lücken: ${top}</span></div>`:''}
      ${g.act_je_formular!=null?`<div class="dsline"><span>Unter ihren gemessenen Formularen: ${pl(g.schriften,'Schrift','Schriften')}, ${pl(g.groessen,'Grundgrösse','Grundgrössen')}, ${pl(g.akzente,'Akzentfarbe','Akzentfarben')} (PDF)</span></div>`:''}`
    :`<p class="dsnone">${nichts}</p>`;
  return body+`<div class="kznote dsnote">Ein eigener Teil des Dashboards: Er beschreibt, wie die Formulare aussehen und wo sie von der Praxis der übrigen abweichen — keine Massnahme und keine Aufforderung, ein Formular zu ändern; nicht in den offenen Punkten dieses Briefings gezählt.</div>
    <div class="small noprint" style="margin-top:6px">${goLink('gestaltung','dienststellen','Zur Gestaltung der Formulare ›','inl')}</div>`;
}
// ---------- Datenmodell & Once-Only: the layers the two pages and the panels draw ----------
// Computed once in scripts/export_json.py and only drawn here: the parties of every data point
// (DATA.parteien, scripts/rollen.py), one preferred element per Angabe and role (DATA.konzepte,
// scripts/konzepte.py), the change-impact index with the edition of every law (DATA.wirkung,
// scripts/wirkung.py), the registers and the prefill rule (DATA.register, DATA.vorbefuellung,
// scripts/register_map.py), the permanent identifiers (DATA.kennungen, scripts/kennungen.py) and
// the figures of the two pages (DATA.datenmodell, export_json._datenmodell). None of them enters
// the headline figures, the open points or the Handlungsbedarf. A Vorschlag the canton confirms and
// a decision it takes are amber; an edition in force green, a newer one grey (the databank re-reads
// the articles); everything else is neutral.
const PAR=DATA.parteien&&(DATA.parteien.rollen||[]).length?DATA.parteien:null;
const KONZ=DATA.konzepte||null, WIRK=DATA.wirkung||null, REG=DATA.register||null, VORB=DATA.vorbefuellung||null;
const DM=DATA.datenmodell||{}, DML=DM.labels||{}, KENN=DATA.kennungen||null;
const ROLLE=Object.fromEntries(((PAR&&PAR.rollen)||[]).map(r=>[r.code,r]));
const rolleLabel=c=>(ROLLE[c]&&ROLLE[c].label)||('⟨'+c+'⟩');
const entLabel=c=>lab(DML.entitaet,c);
const W_LAW={}, W_ART={};
((WIRK&&WIRK.gesetze)||[]).forEach(g=>{W_LAW[g.id]=g; (g.artikel||[]).forEach(a=>{W_ART[a.id]={g,a};});});
const REG_BY=Object.fromEntries(((REG&&REG.katalog)||[]).map(k=>[k.code,k]));
const regName=c=>(REG_BY[c]&&REG_BY[c].name)||('⟨'+c+'⟩');
const REG_GRP=DM.register_gruppen||[];
// a law by the number readers know it by («SHR 641.100», «SR 831.10»)
const lawNr=g=>g?(g.nummer||''):'';
// an abbreviation («FamZG», «AHVV») names a law; a generic or cut short title («Gesetz») does not
const isAbk=k=>/^[A-ZÄÖÜ][A-Za-zÄÖÜäöü0-9-]{1,14}$/.test(k||'')&&((String(k).match(/[A-ZÄÖÜ]/g)||[]).length>=2);
const lawName=g=>g?(isAbk(g.kurz)?g.kurz:g.titel):'';
const lawSub=g=>g?lawNr(g)+(isAbk(g.kurz)?' · '+g.titel:''):'';
const entRolle=c=>lab(DML.entitaet_rolle||DML.entitaet,c);
// the days of the latest currency check of the cited laws (wirkung.uebersicht.geprueft_von … _am):
// one day, or a range when the laws were last asked on different days
function pruefTage(WU){
  const a=(WU||{}).geprueft_von, b=(WU||{}).geprueft_am;
  if(!b) return '—'; if(!a||a===b) return fmtDate(b);
  const A=fmtDate(a), B=fmtDate(b);
  return A.slice(3)===B.slice(3)?`${A.slice(0,3)}–${B}`:`${A} bis ${B}`;
}
// the edition of a law as the latest currency check found it (wirkung.gesetze[].pruefung): in force
// green, a newer edition grey — the databank re-reads the cited articles (wirkung.ton)
function standChip(lawId){
  const g=W_LAW[lawId]; if(!g||!WIRK) return '';
  const p=g.pruefung||{}, L=WIRK.labels||{}, e=p.ergebnis||'nicht_geprueft', t=(WIRK.ton||{})[e]||'open';
  const lbl=e==='aktuell'?'aktuell':e==='neuer_stand'?(p.stand_aktuell?'neuerer Stand seit '+fmtDate(p.stand_aktuell):'neuerer Stand')
    :(e==='stand_unbekannt'||e==='nicht_geprueft'||!p.stand_gelesen)?'Stand unbekannt':lab(L.ergebnis,e);
  const tip=[`Gesetzesstand: Artikel gelesen in der Fassung vom ${p.stand_gelesen?fmtDate(p.stand_gelesen):'— (unbekannt)'}`,
    p.stand_aktuell?`in Kraft: Fassung vom ${fmtDate(p.stand_aktuell)}`:'',
    `${lab(L.ergebnis,e)} — geprüft ${fmtDate(p.geprueft_am)} bei der Quelle «${lab(L.pruef_quelle,p.quelle)}»`,
    e==='neuer_stand'?'Die Databank liest die zitierten Artikel nicht von selbst neu; sie stehen zur Durchsicht an.':''].filter(Boolean).join('\n');
  return stBadge(t,esc(lbl),tip,'stchip');
}
// «betrifft N Datenpunkte in M Formularen ›» — the change-impact explorer at this law or article
function wirkLink(lawId,artId){
  const A=artId!=null?W_ART[artId]:null, x=A?A.a:W_LAW[lawId];
  if(!x||!x.n_datenpunkte) return '';
  return goLink('datenmodell',A?'a-'+artId:'g-'+lawId,`betrifft ${pl(x.n_datenpunkte,'Datenpunkt','Datenpunkte')} in ${pl(x.n_formulare,'Formular','Formularen')} ›`,'inl wlink');
}
// a list of Formulare, each a link to its Formular-Ansicht (sec opens a panel there); the first
// DMCAP are drawn, «weitere N anzeigen» draws the rest (Back/Forward draws it again)
const DMCAP=24; let _dmN=0; const _dmRest={};
function dmFormItem(x,sec){
  const f=formById[x.id]; if(!f) return `<li>Formular ${esc(x.id)}</li>`;
  const datei=String(f.source_file||'').split('/').pop();
  const wer=x.dup?` · Nr. ${esc(f.id)}${datei?`, Datei «${esc(datei)}»`:f.file_type==='eformular'?', eFormular':''}`:'';
  return `<li>${formLink(f.service_id,f.id,esc(f.title),'dlink lt',sec)} <span class="small muted">· ${esc(f.dienststelle||'')}${wer}${x.extra?' · '+x.extra:''}</span></li>`;
}
function dmFormList(items,sec){
  const L=(items||[]).map(x=>typeof x==='object'?Object.assign({},x):{id:x}).filter(x=>formById[x.id])
    .sort((a,b)=>(b.rang||0)-(a.rang||0)||String(formById[a.id].title).localeCompare(String(formById[b.id].title),'de')||a.id-b.id);
  // two Formulare of one Dienststelle with the same title cannot be told apart by it: they say which they are
  const nT={}; L.forEach(x=>{const f=formById[x.id], k=f.title+'|'+(f.dienststelle||''); nT[k]=(nT[k]||0)+1;});
  L.forEach(x=>{const f=formById[x.id]; if(nT[f.title+'|'+(f.dienststelle||'')]>1) x.dup=true;});
  const id='dl'+(_dmN++), rest=L.slice(DMCAP);
  if(rest.length) _dmRest[id]={items:rest,sec};
  return `<ul class="gfll" id="${id}">${L.slice(0,DMCAP).map(x=>dmFormItem(x,sec)).join('')}</ul>${
    rest.length?`<button type="button" class="gmorebtn" data-showmore="${id}">weitere ${nf(rest.length)} anzeigen</button>`:''}`;
}
function dmWire(root){
  root.querySelectorAll('button.gmorebtn[data-showmore]').forEach(b=>{if(!_dmRest[b.dataset.showmore]) return; b.onclick=()=>{
    const id=b.dataset.showmore, r=_dmRest[id], ul=document.getElementById(id); if(!r||!ul) return;
    const had=document.activeElement===b, n0=ul.children.length;
    ul.insertAdjacentHTML('beforeend',r.items.map(x=>dmFormItem(x,r.sec)).join(''));
    ul.setAttribute('data-shown',id); b.remove(); wireGo(ul);
    if(had){const a=ul.children[n0]&&ul.children[n0].querySelector('a'); if(a) a.focus({preventScroll:true});}};});
  root.querySelectorAll('button.copybtn[data-copy]').forEach(b=>b.onclick=()=>copyText(b.dataset.copy,b));
}
// a permanent identifier, copyable: the text itself selects as a whole, the button copies it
function copyText(t,btn){
  const done=()=>{const l=document.getElementById('tiplive'); if(l) l.textContent='Kennung kopiert: '+t;
    if(btn){btn.textContent='kopiert'; setTimeout(()=>{btn.textContent='kopieren';},1400);}};
  // the fallback: execCommand answers false (or throws) when nothing was copied — then the identifier
  // stays selected in its own text for copying by hand, and the live region says so
  const fb=()=>{const ta=document.createElement('textarea'); ta.value=t; ta.setAttribute('readonly',''); ta.className='vh';
    document.body.appendChild(ta); ta.select(); let ok=false; try{ok=document.execCommand('copy');}catch(e){ok=false;} ta.remove();
    if(ok){done(); return;}
    const l=document.getElementById('tiplive'); if(l) l.textContent='Kennung nicht kopiert — sie ist markiert und lässt sich von Hand kopieren: '+t;
    const c=btn&&btn.parentElement&&btn.parentElement.querySelector('code.kennc');
    if(c){const r=document.createRange(); r.selectNodeContents(c); const sl=window.getSelection(); sl.removeAllRanges(); sl.addRange(r);}};
  try{if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done,fb); else fb();}catch(e){fb();}
}
// the label of a table cell on a phone, where the table stacks (.dmstack): hidden on a wider screen
const ML=t=>`<span class="dml" aria-hidden="true">${t}</span>`;
const kennTag=(k,was)=>k?`<span class="kenn"><span class="kennl">${esc(was||'Kennung')}</span> <code class="kennc">${esc(k)}</code> <button type="button" class="copybtn" data-copy="${esc(k)}" title="Die Kennung ${esc(k)} in die Zwischenablage kopieren">kopieren</button></span>`:'';
// a section of the two pages, its address #<page>/all/<key>
const dmSec=(pre,id,title,body)=>`<section class="gstsec" id="${pre}-${esc(id)}"><h4>${title}</h4>${body}</section>`;
// a «Wo anfangen?» card: one question, one figure of the export
const dmDoor=(tab,sub,k,q,f)=>`<a class="door" href="#${tab}/all/${esc(sub)}" data-go="${tab}" data-sub="${esc(sub)}"><span class="dk">${k}</span><span class="dq">${q}</span>${f?`<span class="dz"><b>${f[0]}</b> ${f[1]}</span>`:''}</a>`;
// a section, a law or a concept named in the address: open it, bring it into view, focus it
function dmFocus(m,id,open){
  if(!id||comingBack()) return;
  setTimeout(()=>{const t=document.getElementById(id); if(!t||!m.contains(t)) return;
    if(t.tagName==='DETAILS') t.open=true;
    (open||[]).forEach(x=>{const d=document.getElementById(x); if(d&&d.tagName==='DETAILS') d.open=true;});
    t.scrollIntoView({behavior:MOTION}); focusIn(t); t.classList.add('flash'); setTimeout(()=>t.classList.remove('flash'),1600);},0);
}
// the data points of a Formular, each with its label («Personalien › Name») and its Datenfeld
function unitsOf(fm){
  const out=[];
  (fm.data_fields||[]).forEach(d=>{const subs=(d.subfields||[]).filter(s=>s&&typeof s==='object');
    (subs.length?subs:[d]).forEach(u=>out.push({d,u,name:subs.length?d.name+' › '+u.name:d.name}));});
  return out;
}

// ---------- Datenmodell (#datenmodell): whose Angabe, one element, identifiers, editions, impact ----------
// Opens like the start page — one question, five cards with one figure each —, then one section per
// card. Section addresses: #datenmodell/all/parteien · konzepte · kennungen · gesetzesstand · wirkung,
// a concept k-<code>, the explorer at a law g-<law id> or an article a-<article id>.
const DM_SEC=['parteien','konzepte','kennungen','gesetzesstand','wirkung'];
function viewDatenmodell(){
  const m=document.getElementById('main');
  if(!PAR&&!WIRK&&!KONZ){m.innerHTML=pageHead('Datenmodell','Dieser Export enthält weder die Parteien noch die Konzepte noch den Wirkungsindex.')
    +`<div class="nores">${goLink('home','','Zur Übersicht ›','inl')}</div>`; wireGo(m); return;}
  _dmN=0; Object.keys(_dmRest).forEach(k=>{delete _dmRest[k];});
  const sub=(state.sub&&state.sub!=='felder')?state.sub:null;
  let selLaw=null, selArt=null, selK=null;
  if(sub&&/^g-\d+$/.test(sub)) selLaw=W_LAW[+sub.slice(2)]||null;
  if(sub&&/^a-\d+$/.test(sub)&&W_ART[+sub.slice(2)]){selArt=W_ART[+sub.slice(2)].a; selLaw=W_ART[+sub.slice(2)].g;}
  if(sub&&/^k-/.test(sub)) selK=((KONZ&&KONZ.konzepte)||[]).find(k=>k.code===sub.slice(2))||null;
  const bad=sub&&!DM_SEC.includes(sub)&&!selLaw&&!selK; if(bad) state.sub='felder';
  const Z=PAR?PAR.zahlen:null, DP=DM.parteien||null, KS=KONZ?KONZ.summen:null, KN=DM.kennungen||null,
    WU=WIRK?WIRK.uebersicht||{}:null, WS=WIRK?WIRK.summen||{}:null, PZ=WU?WU.pruefung_zitiert||{}:{};
  const sec=(id,t,b)=>dmSec('dm',id,t,b);
  const doors=[
    PAR&&dmDoor('datenmodell','parteien','Wessen Angabe?','Welcher Partei gehört jede Angabe — der einreichenden Person, ihrer Familie, einer Vertretung, einem Betrieb?',
      [pctTxt(Z.zugeordnet,Z.punkte),`der ${nf(Z.punkte)} Datenpunkte sind einer Partei zugeordnet; die ${nf(PAR.rollen.length)} Rollen sind ein Vorschlag der Databank, den der Kanton bestätigt`]),
    KONZ&&dmDoor('datenmodell','konzepte','Eine Angabe — ein Element','Nutzen die Formulare für dieselbe Angabe derselben Partei dasselbe eCH-Element?',
      [nf(KS.n_abweichend),`Datenpunkte in ${pl(KS.n_abweichend_formulare,'Formular','Formularen')} nutzen ein anderes Element als den Vorschlag — in ${nf(KS.n_konzepte_mit_abweichung)} der ${nf(KS.n_konzepte)} Konzepte${(()=>{
        const t=(KONZ.konzepte||[]).filter(k=>k.n_abweichend).sort((a,b)=>b.n_abweichend-a.n_abweichend||a.label.localeCompare(b.label,'de')).slice(0,3).map(k=>k.label);
        return t.length?', am häufigsten '+t.join(', '):'';})()}`]),
    KN&&dmDoor('datenmodell','kennungen','Dauerhafte Kennungen','Wie verweisen andere Systeme auf ein Formular, ein Feld, eine Angabe oder einen Artikel?',
      [nf(KN.n_aktiv),'aktive Kennungen nach einem Schema ohne Webadresse — die Basisadresse ist offen']),
    WIRK&&dmDoor('datenmodell','gesetzesstand','Gesetzesstand','Stammen die zitierten Artikel aus der Fassung, die heute in Kraft ist?',
      [nf(PZ.neuer_stand||0),`von ${pl(WS.n_gesetze_zitiert,'zitiertem Gesetz','zitierten Gesetzen')} haben eine neuere Fassung — ${pl((WU.betroffen||{}).n_formulare||0,'Formular zitiert','Formulare zitieren')} eines davon`]),
    WIRK&&dmDoor('datenmodell','wirkung','Wirkung einer Änderung','Ein Gesetz oder ein Artikel ändert sich — welche Formulare, Daten und Dienststellen betrifft es?',
      [nf(WS.n_artikel),`zitierte Artikel in ${pl(WS.n_gesetze_zitiert,'Gesetz','Gesetzen')} — ein Gesetz wählen, dann seine Artikel`]),
  ].filter(Boolean).join('');

  // ---- (1) parties and roles
  let sP='';
  if(PAR){
    const R=(DP&&DP.rollen)||{}, MT=(DP&&DP.methode)||null;
    const rows=PAR.rollen.map(r=>{const x=R[r.code]||{parteien:0,formulare:0,punkte:0};
      return `<tr id="dr-${esc(r.code)}"><td><b>${esc(r.label)}</b> <span class="small muted">· ${esc(entRolle(r.entitaet))}</span><div class="small muted">${esc(r.erklaerung)}</div></td>
        <td class="num">${ML('Parteien')}<b class="sumn" data-s="pa">${nf(x.parteien)}</b></td><td class="num">${ML('Formulare')}${nf(x.formulare)}</td><td class="num">${ML('Datenpunkte')}<b class="sumn" data-s="pu">${nf(x.punkte)}</b></td></tr>`;}).join('');
    const tab=`<div class="card tscroll sumbox"><table class="ft dmrol dmstack"><thead><tr><th>Rolle · Art der Partei</th><th class="num">Parteien</th><th class="num">Formulare</th><th class="num">Datenpunkte zugeordnet</th></tr></thead><tbody>
      <tr class="dgrp"><td>Alle Rollen</td><td class="num">${ML('Parteien')}<b class="sumtot" data-s="pa">${nf(DP?DP.n_parteien:0)}</b></td><td class="num">${ML('Formulare')}${nf(Z.formulare_mit_partei)}</td><td class="num">${ML('Datenpunkte')}<b class="sumtot" data-s="pu">${nf(Z.zugeordnet)}</b></td></tr>${rows}</tbody></table></div>`;
    const vert=((DP&&DP.verteilung)||[]).map(v=>({w:v.label,n:v.formulare}));
    const nForms=MT?MT.formulare:DATA.forms.length;
    const verteil=vert.length?`<div class="card gm"><div class="sumbox"><div class="gcap">Parteien je Formular: <b class="sumtot">${nf(nForms)}</b> Formulare</div><ul class="gdist">${vert.map(v=>
      `<li><span class="gdl">${esc(v.w)}</span><span class="gdb" aria-hidden="true"><i style="width:${nForms?(100*v.n/nForms).toFixed(1):0}%"></i></span><b class="gdn sumn">${nf(v.n)}</b></li>`).join('')}</ul></div></div>`:'';
    // the reasons of «unklar»: the codes of the rules, and the reasons written per point in the judgement
    const GR=Z.grund||{}, gk=Object.keys(GR).sort((a,b)=>(a==='urteil')-(b==='urteil')||GR[b]-GR[a]);
    const gl=gk.map(k=>`<li><b class="sumn">${nf(GR[k])}</b><span>${k==='urteil'?`${esc(lab(DML.herkunft,'urteil'))} — der Grund steht je Datenpunkt im Abschnitt «Parteien» der Formular-Ansicht; zum Beispiel gilt eine Zeile beiden Ehepartnern, betrifft eine Liste von Beilagen mehrere Parteien oder nennt das Formular die Person nicht`:esc(lab(PAR.gruende,k))}</span></li>`).join('');
    const unklar=`<div class="card gm sumbox"><div class="gcap">«unklar» — <b class="sumtot">${nf(Z.unklar)}</b> Datenpunkte, jeder mit einem Grund</div><ul class="tleg dmgr">${gl}</ul></div>`;
    // how the layer was made and checked: rules, judgement from the Formular text, second review, sample
    let wie='';
    if(MT){
      const SP=MT.stichprobe, D=SP?SP.damals:null, H=SP?SP.heute:null, SCH=SP?SP.schichten||{}:{};
      const DG=SP?SP.damals_gesamt||{}:{};
      wie=`<ol class="dmwie">
        <li><b>Aus Hinweisen abgeleitet.</b> ${esc(MT.stufen.regel)}. So sind ${pl(MT.punkte_regel.zugeordnet,'Datenpunkt','Datenpunkte')} zugeordnet und ${nf(MT.punkte_regel.unklar)} «unklar» mit einem Grund aus der Liste oben; ${pl(MT.formulare_nur_regel,'Formular steht','Formulare stehen')} nur auf dieser Stufe${MT.formulare_nur_regel_ohne_partei?` (${nf(MT.formulare_nur_regel_ohne_partei)} davon ohne Partei)`:''}.</li>
        <li><b>Aus dem Formulartext beurteilt.</b> ${pl(MT.formulare_beurteilt,'Formular','Formulare')}: ${pl(MT.punkte_urteil.zugeordnet,'Datenpunkt','Datenpunkte')} zugeordnet, ${nf(MT.punkte_urteil.unklar)} «unklar». ${esc(MT.stufen.urteil)}. Eine Zuordnung gilt nur, wenn die Art der Partei zum beurteilten Subjekt des Datenfelds passt; sonst bleibt der Datenpunkt «unklar».</li>
        <li><b>Zweitprüfung.</b> Jedes beurteilte Formular ist ein zweites Mal gegen seinen Text geprüft: ${pl(MT.zweitpruefung.bestaetigt,'Formular','Formulare')} bestätigt, ${nf(MT.zweitpruefung.geaendert)} geändert${MT.zweitpruefung.ohne?`, ${nf(MT.zweitpruefung.ohne)} noch ohne Zweitprüfung`:''}.</li>
        ${SP?`<li><b>Stichprobe.</b> ${pl(SP.n,'Datenpunkt','Datenpunkte')}, zufällig gezogen (fester Startwert ${esc(String(SP.startwert))}) und je am Formulartext geprüft, in drei Schichten: ${Object.values(SCH).map(s=>`${nf(s.gezogen)} von ${nf(s.bestand)} <span class="muted">(${esc(s.text)})</span>`).join(', ')}.
          <br>Ergebnis der Prüfung: ${nf(DG.richtig)} von ${pl(DG.zugeordnet,'Zuordnung','Zuordnungen')} richtig${DG.falsch?`, ${nf(DG.falsch)} falsch (seither korrigiert)`:''}; von ${nf(DG.unklar)} «unklar» ${nf(DG.offen)} zu Recht offen, ${nf(DG.grenzfall)} ${plw(DG.grenzfall,'Grenzfall','Grenzfälle')}, ${nf(DG.klaerbar)} aus dem Formulartext klärbar.
          <br><b>Heute</b> sind ${nf(H.zugeordnet)} der gezogenen Datenpunkte zugeordnet, ${nf(H.zugeordnet_wie_pruefung)} davon der Partei, die die Prüfung festhielt${H.zugeordnet_anders?`, ${nf(H.zugeordnet_anders)} einer anderen`:''}; ${nf(H.unklar)} sind «unklar»: ${nf(H.unklar_wie_pruefung)} wie in der Prüfung, ${nf(H.unklar_grenzfall)} ${plw(H.unklar_grenzfall,'Grenzfall','Grenzfälle')}${H.unklar_klaerbar?`, ${nf(H.unklar_klaerbar)} laut Prüfung klärbar (das Subjekt des Felds lässt die Zuordnung nicht zu)`:''}${H.unklar_statt_zuordnung?`, ${nf(H.unklar_statt_zuordnung)} seither «unklar» statt zugeordnet`:''}${H.fehlt?` · ${nf(H.fehlt)} gibt es nicht mehr`:''}.
          <br><span class="muted">Zuordnungen, die erst nach der Stichprobe geändert wurden, gehören nicht zu ihr. Beleg: ${esc(SP.quelle)}</span></li>`:''}
      </ol>`;
    }
    sP=sec('parteien','Wessen Angabe? — Parteien und Rollen',
      `<p class="gfrage">Jede Angabe gehört einer Partei: der Person oder Organisation, die das Formular einreicht, ihrer Familie, einer Vertretung, einem Arbeitgeber — oder einer Sache wie einem Grundstück oder einem Fahrzeug.
        ${nf(Z.zugeordnet)} von ${nf(Z.punkte)} Datenpunkten (${pctTxt(Z.zugeordnet,Z.punkte)}) sind einer Partei zugeordnet, ${nf(Z.unklar)} sind «unklar», jeder mit einem Grund; ${pl(DP?DP.n_parteien:0,'Partei','Parteien')} in ${pl(Z.formulare_mit_partei,'Formular','Formularen')}.</p>
      <p class="gvorb">${stBadge('dec','Vorschlag der Databank','Die Rollenliste ist ein Vorschlag der Databank, gebildet aus den Rollenwörtern der Formulare; der Kanton bestätigt sie.')} Die ${nf(PAR.rollen.length)} Rollen sind aus den Rollenwörtern der Formulare gebildet; der Kanton bestätigt die Liste. Wessen Angabe ein Datenpunkt ist, entscheidet auch, ob ein Register sie vorbefüllen könnte: nur Angaben der einreichenden Person — ${goLink('onceonly','','Was Register schon wissen ›','inl')}</p>
      <h5 class="dmh">Die Rollen</h5>${tab}
      <div class="gcols"><div><h5 class="dmh">Parteien je Formular</h5>${verteil}</div><div><h5 class="dmh">Warum «unklar»</h5>${unklar}</div></div>
      ${wie?`<h5 class="dmh">Wie die Zuordnung entstand und geprüft ist</h5><div class="card gm">${wie}</div>`:''}`);
  }

  // ---- (2) concepts: one element per Angabe and role
  let sK='';
  if(KONZ){
    const L=KONZ.labels||{}, ton=k=>(KONZ.ton||{})[k]||'dec', el=e=>`${esc(e.standard)}·${esc(e.element)}`;
    const zelle=(k,z)=>{
      const st=z.status==='vorschlag'
        ?stBadge(ton('vorschlag'),`Vorschlag: ${el(z.vorschlag)} (${nf(z.vorschlag.anteil)} %)`,`${nf(z.vorschlag.n)} von ${nf(z.n)} Datenpunkten (${nf(z.vorschlag.anteil)} %) nutzen dieses Element — die Praxis der Formulare; der Kanton bestätigt den Vorschlag`)
        :stBadge(ton('kanton'),esc(lab(L.status,'kanton')),lab(L.grund,z.grund)+((z.elemente||[]).length===1?' — alle nutzen dasselbe Element, für einen Vorschlag sind es zu wenige':'')+'; der Kanton legt das Element fest');
      const els=(z.elemente||[]).map(e=>`<span class="nowrap">${el(e)} ${nf(e.n)}</span>`).join(' · ');
      const ab=(z.abweichend||[]).length?gFolded(`${pl(z.n_abweichend,'Datenpunkt','Datenpunkte')} in ${pl(z.n_abweichend_formulare,'Formular','Formularen')} mit einem anderen Element`,
        dmFormList(z.abweichend.map(a=>({id:a.form_id,extra:esc(a.element.replace(':','·'))+(a.n>1?' ('+nf(a.n)+')':'')}))),false):'';
      return `<tr><td><b>${esc(rolleLabel(z.rolle))}</b><div class="small muted">${esc(entLabel(z.entitaet))}</div></td><td class="num">${ML('Datenpunkte')}${nf(z.n)}<div class="small muted">${pl(z.n_formulare,'Formular','Formulare')}</div></td>
        <td class="dmw">${st}${z.status!=='vorschlag'?` <span class="small muted">${esc(lab(L.grund,z.grund))}</span>`:''}<div class="small">${els}</div>${ab}</td></tr>`;};
    const kCard=k=>{
      const mem=(k.mitglieder||[]).map(e=>`<li><span class="mono">${el(e)}</span>${e.context?` <span class="small muted">in ${esc(e.context)}</span>`:''} — ${pl(e.n,'Datenpunkt','Datenpunkte')}${e.n_zuordnung_falsch?` (${nf(e.n_zuordnung_falsch)} laut Prüfung der Bezeichnungen falsch zugeordnet, nicht gezählt)`:''}</li>`).join('');
      const aus=(k.ausserhalb||[]).map(e=>`<li><span class="mono">${el(e)}</span>${e.context?` <span class="small muted">in ${esc(e.context)}</span>`:''} — ${esc(e.grund||'')}</li>`).join('');
      const nab=k.n_abweichend||0;
      return `<details class="card gm dmk" id="dk-${esc(k.code)}"${selK&&selK.code===k.code?' open':''}><summary><span class="dmkn">${esc(k.label)}</span>
        <span class="dmks"><b class="sumn" data-s="kp">${nf(k.n_punkte)}</b> ${plw(k.n_punkte,'Datenpunkt','Datenpunkte')} in ${pl(k.n_formulare,'Formular','Formularen')} · ${pl((k.zellen||[]).length,'Zelle','Zellen')}, ${nf(k.n_zellen_vorschlag)} mit Vorschlag · <b class="sumn" data-s="ka">${nf(nab)}</b> ${plw(nab,'weicht','weichen')} vom Vorschlag ab</span></summary>
        <p class="gmq">${esc(k.erklaerung||'')}</p>
        <div class="small"><b>Elemente dieses Konzepts:</b><ul class="dmlist">${mem}</ul>${aus?`<b>Ähnlich, aber eine andere Angabe — nicht gezählt:</b><ul class="dmlist">${aus}</ul>`:''}</div>
        <details class="gwie"><summary>Warum diese Elemente zusammengehören</summary><p>${esc(k.grund||'')}</p></details>
        ${(()=>{const Z=k.zellen||[], gross=Z.filter(z=>z.grund!=='zu_wenige'), klein=Z.filter(z=>z.grund==='zu_wenige');
          const hd='<thead><tr><th>Rolle der Partei</th><th class="num">Datenpunkte</th><th>Element</th></tr></thead>';
          return (gross.length?`<div class="tscroll"><table class="ft dmz dmstack">${hd}<tbody>${gross.map(z=>zelle(k,z)).join('')}</tbody></table></div>`:'')
            +(klein.length?gFolded(`${pl(klein.length,'Rolle','Rollen')} mit weniger als ${nf((KONZ.regel||{}).mindestens||10)} Datenpunkten — ohne Vorschlag, ${nf(klein.filter(z=>(z.elemente||[]).length===1).length)} davon mit durchgehend demselben Element`,
                `<div class="tscroll"><table class="ft dmz dmstack">${hd}<tbody>${klein.map(z=>zelle(k,z)).join('')}</tbody></table></div>`):'');})()}
        ${k.ohne_rolle&&k.ohne_rolle.n?`<p class="small muted">${pl(k.ohne_rolle.n,'Datenpunkt','Datenpunkte')} ohne geklärte Partei — in keiner Zelle.</p>`:''}${k.andere_entitaet&&k.andere_entitaet.n?`<p class="small muted">${pl(k.andere_entitaet.n,'Datenpunkt','Datenpunkte')} einer Partei, deren eigene Angabe das Konzept nicht ist — in keiner Zelle.</p>`:''}</details>`;};
    const grp={}; (KONZ.konzepte||[]).forEach(k=>{(grp[k.gruppe]=grp[k.gruppe]||[]).push(k);});
    const S=KS;
    const parts=[[S.n_punkte_vorschlag,'nutzen das vorgeschlagene Element'],[S.n_abweichend,'nutzen ein anderes Element als den Vorschlag'],
      [S.n_punkte_in_kanton_zellen,`stehen in Zellen ohne Vorschlag (keine Mehrheit von zwei Dritteln oder weniger als ${nf((KONZ.regel||{}).mindestens||10)} Datenpunkte) — der Kanton legt das Element fest`],[S.n_ohne_rolle,esc(L.ohne_rolle||'ohne geklärte Partei')],[S.n_andere_entitaet,esc(L.andere_entitaet||'')]];
    sK=sec('konzepte','Eine Angabe — ein Element',
      `<p class="gfrage">Ein Konzept fasst die eCH-Elemente zusammen, die dieselbe Angabe bezeichnen${(()=>{
        // the example: the standards of the concept «Vorname», as its members name them (most points first)
        const v=(KONZ.konzepte||[]).find(k=>k.code==='vorname'); if(!v) return '';
        const st=[]; (v.mitglieder||[]).slice().sort((a,b)=>b.n-a.n).forEach(e=>{if(!st.includes(e.standard)) st.push(e.standard);});
        return st.length>1?` — der Vorname steht zum Beispiel in ${st.slice(0,3).join(', ').replace(/, ([^,]*)$/,' und $1')}`:'';})()}. Je Konzept und Rolle der Partei zeigt die Seite, welches Element die Formulare nutzen und welche Formulare ein anderes nutzen.</p>
      <p class="gmq">${esc(KONZ.regel&&KONZ.regel.text||'')}</p>
      <p class="gvorb">Ein Befund zum Datenstandard: er geht nicht in die Kennzahlen der Startseite und nicht in die offenen Punkte ein. Beides wartet auf den Kanton: einen ${stBadge(ton('vorschlag'),esc(lab(L.status,'vorschlag')),'Die Praxis der Formulare; der Kanton bestätigt den Vorschlag')} bestätigt er; ${stBadge(ton('kanton'),esc(lab(L.status,'kanton')),'Ohne Vorschlag legt der Kanton das Element fest')} steht, wo es keinen Vorschlag gibt. Zusammen ${pl(S.n_konzepte,'Konzept','Konzepte')} mit ${pl(S.n_mitglieder,'Element','Elementen')} und ${pl(S.n_zellen,'Zelle','Zellen')} (Rolle × Art der Partei): ${nf(S.n_zellen_vorschlag)} mit Vorschlag, ${nf(S.n_zellen_kanton)} ohne Vorschlag — ${nf(S.n_zellen_kanton_keine_mehrheit)} ohne Mehrheit von zwei Dritteln, ${nf(S.n_zellen_kanton_zu_wenige)} mit weniger als ${nf((KONZ.regel||{}).mindestens||10)} Datenpunkten${S.n_zellen_kanton_ein_element!=null?` (${nf(S.n_zellen_kanton_ein_element)} der Zellen ohne Vorschlag nutzen durchgehend dasselbe Element, zusammen ${pl(S.n_punkte_kanton_ein_element,'Datenpunkt','Datenpunkte')})`:''}.</p>
      <div class="card gm sumbox"><div class="gcap"><b class="sumtot">${nf(S.n_punkte)}</b> Datenpunkte in ${pl(S.n_formulare,'Formular','Formularen')} gehören zu einem Konzept${S.n_zuordnung_falsch?` (dazu ${nf(S.n_zuordnung_falsch)}, deren eCH-Zuordnung laut Prüfung der Bezeichnungen falsch ist — nicht gezählt)`:''}:</div>
        <ul class="tleg dmgr">${parts.filter(p=>p[1]).map(p=>`<li><b class="sumn">${nf(p[0])}</b><span>${p[1]}</span></li>`).join('')}</ul></div>
      <div class="sumbox"><div class="gcap">Die ${nf(S.n_konzepte)} Konzepte mit <b class="sumtot" data-s="kp">${nf(S.n_punkte)}</b> Datenpunkten, davon <b class="sumtot" data-s="ka">${nf(S.n_abweichend)}</b> mit einem anderen Element als dem Vorschlag — ein Konzept aufklappen für seine Elemente, Rollen und Formulare.</div>
      ${Object.keys(grp).map(g=>`<div class="gfgrp">${esc(g)}</div>${grp[g].map(kCard).join('')}`).join('')}</div>`);
  }

  // ---- (3) permanent identifiers and the export contract
  let sI='';
  if(KN){
    const ART=DML.kennung_art||{}, A=KN.aktiv||{};
    // one Formular as the example: the first with a Teilfeld that carries an Angabe and a cited article
    let ex=null;
    for(const f of DATA.forms){for(const d of (f.data_fields||[])){
      const s=(d.subfields||[]).find(x=>x&&x.kennung&&x.angabe_kennung), lb=(d.legal_basis||[]).find(b=>b.artikel_kennung&&W_LAW[b.law_id]);
      if(s&&lb&&d.kennung&&f.kennung){ex={f,d,s,lb}; break;}} if(ex) break;}
    const exRow=(art,k,was)=>k?`<tr><td class="nowrap">${esc(lab(ART,art))}</td><td class="small dmw">${esc(was||'')}</td><td class="dmw"><code class="kennc">${esc(k)}</code></td></tr>`:'';
    const exTab=ex?`<div class="tscroll"><table class="ft dmkex dmstack"><thead><tr><th>Art</th><th>Objekt</th><th>Kennung</th></tr></thead><tbody>
      ${exRow('service',(svcById[ex.f.service_id]||{}).kennung,(svcById[ex.f.service_id]||{}).name)}
      ${exRow('formular',ex.f.kennung,ex.f.title)}${exRow('feld',ex.d.kennung,ex.d.name)}${exRow('teilfeld',ex.s.kennung,ex.d.name+' › '+ex.s.name)}
      ${exRow('angabe',ex.s.angabe_kennung,ex.s.ech?ex.s.ech.standard+' '+ex.s.ech.element:'')}
      ${exRow('gesetz',W_LAW[ex.lb.law_id].kennung,lawName(W_LAW[ex.lb.law_id]))}${exRow('artikel',ex.lb.artikel_kennung,artLabel(ex.lb.article_no)+' '+(ex.lb.law_short||''))}
      ${(DATA.datenhandhabung||[])[0]?exRow('regel',DATA.datenhandhabung[0].kennung,DATA.datenhandhabung[0].summary):''}</tbody></table></div>`:'';
    const nicht=(KENN&&KENN.nicht_aktiv)||[];
    const V=VERTRAG.exporte||{}, vk=Object.keys(V).sort((a,b)=>(a!=='data_export.json')-(b!=='data_export.json')||a.localeCompare(b));
    sI=sec('kennungen','Dauerhafte Kennungen',
      `<p class="gfrage">Jedes Objekt der Databank trägt eine dauerhafte Kennung, auf die andere Systeme verweisen können: ${['service','formular','feld','teilfeld','angabe','gesetz','artikel','regel'].map(a=>esc(lab(ART,a))).join(', ')}. Eine Kennung bezeichnet immer dasselbe Objekt: keine wird gelöscht, neu vergeben oder auf ein anderes Objekt umgehängt; eine Kennung, deren Objekt wegfällt, bleibt als «entfallen» stehen. Sie entsteht einmal aus dem, was das Objekt bei der Vergabe ausmacht — dem Kurznamen des Formulars, dem eCH-Element einer Angabe, der Nummer eines Gesetzes und eines Artikels; Datenfelder und Teilfelder erhalten eine Nummer, die je Formular einmal vergeben und nie wieder verwendet wird. Keine hängt an einer Zeilennummer der Datenbank.</p>
      <p class="gvorb">Schema: <code class="kennc">${esc((KENN&&KENN.schema)||'sh:…')}</code>. Die Basisadresse, unter der eine Kennung als Webadresse aufgelöst würde, ist ${KENN&&KENN.basis_uri?`<code>${esc(KENN.basis_uri)}</code>`:'noch nicht festgelegt — ein offener Entscheid; bis dahin sind die Kennungen Namen ohne Webadresse'}.</p>
      <div class="card gm sumbox"><div class="gcap"><b class="sumtot">${nf(KN.n_aktiv)}</b> aktive Kennungen${Object.keys(KN.nicht_aktiv||{}).length?` · nicht mehr aktiv: ${Object.entries(KN.nicht_aktiv).map(([k,n])=>`${nf(n)} ${esc(k)}`).join(', ')}`:''}</div>
          <ul class="tleg dmgr dmcols">${['service','formular','feld','teilfeld','angabe','gesetz','artikel','regel'].map(a=>`<li><b class="sumn">${nf(A[a]||0)}</b><span>${esc(lab(ART,a))}</span></li>`).join('')}</ul></div>
      ${exTab?`<h5 class="dmh">Beispiel: ein Formular und was dazugehört</h5><div class="card gm">${exTab}</div>`:''}
      ${nicht.length?gFolded(`${pl(nicht.length,'Kennung ist','Kennungen sind')} nicht mehr aktiv — anzeigen`,`<ul class="dmlist small">${nicht.map(x=>`<li><code class="kennc">${esc(x.kennung)}</code> — ${esc(lab(DML.kennung_status,x.status))} seit ${fmtDate(x.bis)}${x.abgeloest_durch?` · Nachfolger <code class="kennc">${esc(x.abgeloest_durch)}</code>`:''}${x.grund&&x.status==='abgeloest'?` · ${esc(x.grund)}`:''}</li>`).join('')}</ul>`):''}
      <h5 class="dmh">Der Exportvertrag</h5>
      <p class="gmq">Jede veröffentlichte Datei trägt eine Version nach Semantic Versioning und ein JSON Schema im Ordner schema/; jede Änderung der Struktur oder einer Anzahl steht mit ihrem Stand in exportvertrag.json. Diese Seite liest data_export.json in der Version ${esc((DATA.vertrag||{}).version||'—')}.</p>
      ${vk.length?`<div class="card tscroll"><table class="ft dmvt dmstack"><thead><tr><th>Datei</th><th>Version</th><th>JSON Schema</th><th>Version seit</th></tr></thead><tbody>${vk.map(n=>`<tr><td><code>${esc(n)}</code></td><td>${ML('Version')}<b>${esc(V[n].version)}</b></td><td class="dmw">${ML('JSON Schema')}<code>${esc(V[n].schema||'—')}</code></td><td>${ML('seit')}${fmtDate(V[n].seit)}</td></tr>`).join('')}</tbody></table></div>
      ${VERTRAG.regeln?`<details class="gwie"><summary>Wann sich welche Stelle der Version ändert</summary><p>${Object.entries(VERTRAG.regeln).map(([k,t])=>`<b>${esc(k)}</b>: ${esc(t)}`).join('<br>')}</p></details>`:''}`:''}`);
  }

  // ---- (4) law editions
  let sG='', sW='';
  if(WIRK){
    const G=(WIRK.gesetze||[]), zit=G.filter(g=>g.n_zitate), ohne=G.filter(g=>!g.n_zitate);
    const rank=g=>({neuer_stand:0,aktuell:2}[(g.pruefung||{}).ergebnis]??1);
    const gRow=g=>{const p=g.pruefung||{};
      return `<tr><td>${goLink('datenmodell','g-'+g.id,esc(lawName(g)),'dlink')}<div class="small muted">${esc(lawSub(g))}</div></td>
        <td class="nowrap">${ML('gelesen')}${p.stand_gelesen?fmtDate(p.stand_gelesen):'—'}</td><td class="nowrap">${ML('in Kraft')}${p.stand_aktuell?fmtDate(p.stand_aktuell):'—'}</td>
        <td class="dmw">${standChip(g.id)}</td><td class="num">${ML('Zitate')}${nf(g.n_zitate)}</td><td class="num">${ML('Formulare')}${nf(g.n_formulare)}</td></tr>`;};
    const ze=zit.slice().sort((a,b)=>rank(a)-rank(b)||b.n_formulare-a.n_formulare||lawName(a).localeCompare(lawName(b),'de'));
    const gHead='<thead><tr><th>Gesetz</th><th>Fassung gelesen</th><th>Fassung in Kraft</th><th>Stand</th><th class="num">Zitate</th><th class="num">Formulare</th></tr></thead>';
    const B=WU.betroffen||{}, PZT=Object.keys(PZ);
    sG=sec('gesetzesstand','Gesetzesstand',
      `<p class="gfrage">Für jedes Gesetz, aus dem die Databank Artikel zitiert, hält sie fest, aus welcher Fassung sie die Artikel gelesen hat, und fragt bei der amtlichen Quelle (Schaffhauser Rechtsbuch, Fedlex) nach, ob diese Fassung noch in Kraft ist — zuletzt geprüft ${pruefTage(WU)}.
        ${pl(B.n_formulare||0,'Formular zitiert','Formulare zitieren')} mit ${pl(B.n_datenpunkte||0,'Datenpunkt','Datenpunkten')} ein Gesetz mit einer neueren Fassung${WU.n_kuenftig?`; für ${nf(WU.n_kuenftig)} der ${pl(WS.n_gesetze,'Gesetz','Gesetze')} dieser Seite ist zudem eine künftige Fassung veröffentlicht`:''}.</p>
      <p class="gvorb">Eine neuere Fassung heisst nicht, dass sich die zitierten Artikel geändert haben. Die Databank liest sie nicht von selbst neu; sie stehen zur Durchsicht an (grau: die Databank handelt).</p>
      <div class="card gm sumbox"><div class="gcap"><b class="sumtot">${nf(WS.n_gesetze_zitiert)}</b> zitierte Gesetze</div><ul class="tleg dmgr">${PZT.map(k=>`<li>${SW((WIRK.ton||{})[k]||'open')}<b class="sumn">${nf(PZ[k])}</b><span>${esc(lab((WIRK.labels||{}).ergebnis,k))}</span></li>`).join('')}</ul></div>
      <div class="card tscroll"><table class="ft dmgs dmstack">${gHead}<tbody>${ze.map(gRow).join('')}</tbody></table></div>
      ${ohne.length?gFolded(`${pl(ohne.length,'Gesetz','Gesetze')} ohne zitierten Artikel in einem Datenfeld — Regeln der Datenhandhabung, Rechtsmittel, Register`,`<div class="tscroll"><table class="ft dmgs dmstack">${gHead}<tbody>${ohne.map(gRow).join('')}</tbody></table></div>`):''}`);

    // ---- (5) change impact: a law list, a law with its articles, an article with its Formulare
    let det='';
    if(selLaw){
      const g=selLaw, W=g.weitere||{};
      const arts=(g.artikel||[]).filter(a=>a.n_zitate).sort((a,b)=>b.n_datenpunkte-a.n_datenpunkte||String(a.nr).localeCompare(String(b.nr),'de',{numeric:true}));
      const nOhne=(g.n_artikel_gesamt||0)-(g.n_artikel||0);
      const aRow=a=>{const sel=selArt&&selArt.id===a.id;
        return `<tr id="dwa-${a.id}"${sel?' class="sel"':''}><td><b>${esc(artLabel(a.nr))}</b> ${esc(a.titel||'')}</td>
          <td class="num">${ML('Zitate')}<b class="sumn" data-s="wz">${nf(a.n_zitate)}</b></td><td class="num">${ML('Datenpunkte')}${nf(a.n_datenpunkte)}</td>
          <td class="dmw">${gFolded(`${pl(a.n_formulare,'Formular','Formulare')} · ${pl(a.n_services,'Service','Services')} · ${pl(a.n_dienststellen,'Dienststelle','Dienststellen')}`,
            `<div class="small muted">${(a.dienststellen||[]).map(n=>dstLink(n,'dlink lt')).join(' · ')}</div>${dmFormList(a.formulare)}`,sel)}</td></tr>`;};
      det=`<div class="card gm dwdet sumbox" id="dw-detail"><div class="gmhd"><h5>${esc(g.titel)}</h5> ${standChip(g.id)}</div>
        <p class="gmq">${esc(lawNr(g))} · ${esc(lab(JUR_DE,g.ebene))} · Kennung <code class="kennc">${esc(g.kennung||'')}</code></p>
        <div class="regstats"><span class="rstat">Artikel zitiert <b>${nf(g.n_artikel)}</b></span>
          <span class="rstat">Zitate <b class="sumtot" data-s="wz">${nf(g.n_zitate)}</b></span><span class="rstat">Datenfelder <b>${nf(g.n_felder)}</b></span>
          <span class="rstat">Datenpunkte <b>${nf(g.n_datenpunkte)}</b></span><span class="rstat">Formulare <b>${nf(g.n_formulare)}</b></span>
          <span class="rstat">Services <b>${nf(g.n_services)}</b></span><span class="rstat">Dienststellen <b>${nf(g.n_dienststellen)}</b></span></div>
        <p class="small">Dienststellen: ${(g.dienststellen||[]).map(n=>dstLink(n,'dlink lt')).join(' · ')||'—'}</p>
        ${(W.regeln||(W.rechtsmittel_formulare||[]).length||(W.bekanntgabe_formulare||[]).length)?`<p class="small muted">Ausserdem: ${[W.regeln?pl(W.regeln,'Regel der Datenhandhabung','Regeln der Datenhandhabung'):'',(W.rechtsmittel_formulare||[]).length?`Rechtsmittelnorm für ${pl(W.rechtsmittel_formulare.length,'Formular','Formulare')}`:'',(W.bekanntgabe_formulare||[]).length?`Bekanntgaben aus ${pl(W.bekanntgabe_formulare.length,'Formular','Formularen')}`:''].filter(Boolean).join(' · ')}</p>`:''}
        ${arts.length?`<div class="tscroll"><table class="ft dmwa dmstack"><thead><tr><th>Artikel</th><th class="num">Zitate</th><th class="num">Datenpunkte</th><th>Formulare, Services, Dienststellen</th></tr></thead><tbody>${arts.map(aRow).join('')}</tbody></table></div>`
          :'<p class="dsnone">Kein Datenfeld zitiert einen Artikel dieses Gesetzes.</p>'}
        ${nOhne?`<p class="small muted">${pl(nOhne,'weiterer Artikel','weitere Artikel')} dieses Gesetzes ${plw(nOhne,'steht','stehen')} in einer Regel der Datenhandhabung, einer Rechtsmittelnorm oder einer Bekanntgabe, nicht in einem Datenfeld.</p>`:''}
        <div class="gmlink">${goLink('datenmodell','wirkung','Zurück zur Liste der Gesetze ›','inl')}</div></div>`;
    }
    const lRow=g=>`<tr${selLaw&&selLaw.id===g.id?' class="sel"':''}><td>${goLink('datenmodell','g-'+g.id,esc(lawName(g)),'dlink')}<div class="small muted">${esc(lawSub(g))}</div></td>
      <td class="num">${ML('Artikel')}${nf(g.n_artikel)}</td><td class="num">${ML('Zitate')}<b class="sumn" data-s="lz">${nf(g.n_zitate)}</b></td><td class="num">${ML('Datenpunkte')}${nf(g.n_datenpunkte)}</td><td class="num">${ML('Formulare')}${nf(g.n_formulare)}</td><td class="num">${ML('Dienststellen')}${nf(g.n_dienststellen)}</td><td class="dmw">${standChip(g.id)}</td></tr>`;
    const zl=zit.slice().sort((a,b)=>b.n_datenpunkte-a.n_datenpunkte||lawName(a).localeCompare(lawName(b),'de'));
    sW=sec('wirkung','Wirkung einer Änderung',
      `<p class="gfrage">Ändert sich ein Gesetz oder ein Artikel, betrifft das die Datenfelder, die ihn zitieren — und ihre Formulare, Services und Dienststellen. ${pl(WS.n_zitate,'Zitat','Zitate')} auf ${pl(WS.n_artikel,'Artikel','Artikel')} in ${pl(WS.n_gesetze_zitiert,'Gesetz','Gesetzen')} verbinden ${pl(WS.n_datenpunkte,'Datenpunkt','Datenpunkte')} in ${pl(WS.n_formulare,'Formular','Formularen')} von ${pl(WS.n_dienststellen,'Dienststelle','Dienststellen')} mit dem Recht. Ein Gesetz wählen: die Seite zeigt seine zitierten Artikel und je Artikel die Formulare.</p>
      ${det}
      <div class="card tscroll sumbox"><table class="ft dmwl dmstack"><caption class="gcap">Die ${nf(zit.length)} zitierten Gesetze, nach Datenpunkten — zusammen <b class="sumtot" data-s="lz">${nf(WS.n_zitate)}</b> Zitate</caption><thead><tr><th>Gesetz</th><th class="num">Artikel</th><th class="num">Zitate</th><th class="num">Datenpunkte</th><th class="num">Formulare</th><th class="num">Dienst&shy;stellen</th><th>Stand</th></tr></thead><tbody>${zl.map(lRow).join('')}</tbody></table></div>`);
  }

  const B=(DATA.datenstand||{});
  m.innerHTML=pageHead('Datenmodell',
    'Wem jede Angabe gehört, welches Element eine Angabe tragen könnte, wie andere Systeme auf die Objekte verweisen — und was eine Änderung eines Gesetzes betrifft.',
    'Die Parteien und Rollen jedes Formulars und wie sie entstanden sind; je Angabe und Rolle das eCH-Element, das die Formulare meist nutzen; die dauerhaften Kennungen und den Exportvertrag; den Stand der zitierten Gesetze; und je Gesetz und Artikel die Formulare, Daten und Dienststellen, die ihn zitieren.',
    'Alles aus derselben Databank: die Parteien aus den Hinweisen der Databank und dem Text der Formulare (mit Zitat, zweitgeprüft, Stichprobe), die Konzepte aus dem eCH-Katalog und einer geprüften Liste (quellen/konzepte.json), der Gesetzesstand aus den amtlichen Quellen. Die Zahlen dieser Seite gehören nicht zu den Kennzahlen der Startseite und nicht zu den offenen Punkten.',
    'Farbe nur bei einem Entscheid oder Befund: amber, was der Kanton bestätigt oder festlegt (Rollenliste, Vorschlag eines Elements); grün eine Fassung in Kraft, grau eine neuere Fassung, deren Artikel die Databank nachliest. Zahlen und Listen sind neutral.')
    +(bad?`<div class="nores">Den Abschnitt «${esc(sub)}» gibt es auf dieser Seite nicht — gezeigt wird die ganze Seite.</div>`:'')
    +`<section class="hsec"><h4>Wo anfangen?</h4><div class="doors gdoors">${doors}</div></section>`
    +sP+sK+sI+sG+sW
    +`<div class="datenstand"><b>Datenstand</b> — Gesetzesstand geprüft ${pruefTage(WU)} · Konzepte Stand ${fmtDate(KONZ&&KONZ.stand)} · erstellt ${fmtDate(B.build||DATA.generated_at||'')}</div>`;
  dmWire(m); wireGo(m);
  if(!bad&&sub) dmFocus(m,selArt?'dwa-'+selArt.id:selLaw?'dw-detail':selK?'dk-'+selK.code:'dm-'+sub);
}

// ---------- Was Register schon wissen (#onceonly): registers and the once-only potential ----------
// Opens like the start page — one card per group of registers, then the Beilagen, the time a register
// could save and the open legal questions —, then the catalogue, one section per group with a card per
// register, the Beilagen, the model estimate per Lebenslage and the canton's open decisions. The
// figures say what a register HOLDS according to a cited source — never that the canton may fetch it.
// Section addresses: #onceonly/all/register · g-<group> · r-<register> · beilagen · zeit · offen.
function viewOnceonly(){
  const m=document.getElementById('main');
  if(!REG){m.innerHTML=pageHead('Was Register schon wissen','Dieser Export enthält keine Register.')
    +`<div class="nores">${goLink('home','','Zur Übersicht ›','inl')}</div>`; wireGo(m); return;}
  _dmN=0; Object.keys(_dmRest).forEach(k=>{delete _dmRest[k];});
  const sub=(state.sub&&state.sub!=='felder')?state.sub:null;
  const known=new Set(['register','beilagen','zeit','offen',...REG_GRP.map(g=>'g-'+g.key),...Object.keys(REG_BY).map(c=>'r-'+c)]);
  const bad=sub&&!known.has(sub); if(bad) state.sub='felder';
  const GS=REG.gesamt||{}, MO=REG.modell||{}, HI=REG.hinweise||{}, ST=REG.stufen||{}, VB=VORB, ZG=DM.zugriff||{}, EA=DM.einwohnerregister_andere||null;
  const sec=(id,t,b)=>dmSec('oo',id,t,b);
  const ew=REG_GRP.find(g=>g.key==='einwohner'), VF=ew&&ew.vorbefuellbar;
  const BZ=DM.beilagen||{register:GS.beilagen_register,ersetzbar:0}, MD=DM.modell||null, nReg=Object.keys(REG_BY).length;
  const doors=REG_GRP.map(g=>dmDoor('onceonly','g-'+g.key,esc(g.label),esc(g.frage),
      g.key==='einwohner'&&VF?[nf(VF.pflicht),`Pflichtangaben in ${pl(VF.formulare,'Formular','Formularen')} wären vorbefüllbar — Angaben der einreichenden Person, nach ihrem heutigen Wert; insgesamt hält das Register ${pl(g.punkte,'Angabe','Angaben')} der Personen dieser Formulare`]
      :g.punkte?[nf(g.punkte),`Angaben in ${pl(g.formulare,'Formular','Formularen')} hält ein Register dieser Gruppe laut Quelle`]
      :[nf(g.beilagen),`${plw(g.beilagen,'Beilage','Beilagen')} in ${pl(g.formulare_beilagen,'Formular','Formularen')} stellt ein Register dieser Gruppe aus`])).join('')
    +dmDoor('onceonly','beilagen','Beilagen, die ein Register ausstellt','Welche verlangten Unterlagen stellt ein Register selbst aus oder hält es?',[nf(GS.beilagen_register),`von ${pl(GS.beilagen,'Beilage','Beilagen')} der Formulare — ${nf(BZ.ersetzbar)} davon könnte ein Abruf beim Register ersetzen`])
    +dmDoor('onceonly','zeit','Gesparte Zeit (Modellschätzung)','Wie viel Zeit liesse sich sparen, wo ein Register die Angabe schon hält?',[nf1(GS.minuten_modell)+' Min.',`obere Grenze für je einen Durchgang durch jedes Formular, mit Angaben anderer Parteien und Registern mit offenem Zugriff${VB?`; nach der Regel der Vorbefüllung ${nf1(VB.minuten_korrigiert)} Min.`:''} — Fallzahlen liegen nicht vor`])
    +dmDoor('onceonly','offen','Offene Rechtsfragen','Darf eine Dienststelle beziehen, was ein Register hält?',[nf(nReg),`von ${pl(nReg,'Register','Registern')}: Zugriff rechtlich offen${ZG.kandidat?` — für ${nf(ZG.kandidat)} zitiert die Databank mögliche Kandidat-Artikel`:''}${EA?`; dazu ${pl(EA.familie.punkte,'Angabe','Angaben')} von Familienangehörigen und weiteren Personen im Haushalt`:''}`]);
  // (1) the catalogue, in groups
  const kat=REG_GRP.map(g=>`<tbody><tr class="gdep"><th colspan="5" scope="rowgroup">${esc(g.label)}</th></tr>`+(g.register||[]).map(c=>{const k=REG_BY[c]; if(!k) return '';
    const z=k.zahlen||{};
    return `<tr><td>${goLink('onceonly','r-'+c,esc(k.name),'dlink')}</td><td>${ML('Ebene')}${esc(lab(DML.register_ebene,k.ebene))}</td><td class="small dmw">${esc(k.inhaber||'')}</td>
      <td class="num">${ML('Angaben')}${nf(z.bestaetigt)}<div class="small muted">${pl(z.formulare_bestaetigt,'Formular','Formulare')}</div></td><td class="num">${ML('Beilagen')}${nf(z.beilagen)}</td></tr>`;}).join('')+'</tbody>').join('');
  const sKat=sec('register','Die Register',
    `<p class="gfrage">${pl(Object.keys(REG_BY).length,'Register','Register')} des Bundes, des Kantons und der Gemeinden, je mit Inhaber, Inhalt, Schlüssel und den eCH-Standards, mit denen es Daten austauscht — jede Angabe mit einer amtlichen Quelle, die die Databank gelesen hat. Ein Name öffnet die Karte des Registers.</p>
     <div class="card tscroll"><table class="ft dmreg dmstack"><thead><tr><th>Register</th><th>Ebene</th><th>Inhaber</th><th class="num">Angaben bestätigt</th><th class="num">Beilagen</th></tr></thead>${kat}</table></div>`);
  // (2) per group, a card per register
  const fact=(k,v)=>v?`<div><dt>${k}</dt><dd>${v}</dd></div>`:'';
  // whose Angaben the confirmed ones are (registers about persons and organisations; the four parts
  // of the export sum to «bestätigt»): the applicant, other parties, open (unklar or of open kind)
  const parteiTeile=z=>{const e=z.eigene_partei||0, a=z.andere_partei||0, u=z.partei_unklar||0, o=z.partei_art_offen||0;
    if(!(a||u||o)) return '';
    return [`${nf(e)} der einreichenden Partei`,`${nf(a)} einer anderen Partei`,
      `${nf(u+o)} mit ungeklärter Partei${o?` (${nf(u)} «unklar», ${nf(o)} der einreichenden Partei, deren Art «Person oder Organisation» offen bleibt)`:''}`].join(', ');};
  const regCard=c=>{const k=REG_BY[c]; if(!k) return ''; const z=k.zahlen||{};
    const urls=[]; (k.belege||[]).forEach(b=>{if(b.url&&!urls.some(u=>u.url===b.url)) urls.push(b);});
    // an official source opens in a new tab; a file of this repository (an eCH schema under ech_xsd/) is
    // named as a copy in the databank, without a link out; anything else is not drawn as a link
    const quelle=b=>/^https:\/\//.test(b.url)?`<a class="inl" href="${esc(b.url)}" target="_blank" rel="noreferrer" title="${esc(b.zitat||'')}">${esc(b.quelle||b.url)} ↗</a>`
      :/^ech_xsd\/[\w./-]+$/.test(b.url)?`<span title="${esc(b.zitat||'')}">${esc(b.quelle||b.url)}</span>`:esc(b.quelle||'');
    const fms=DATA.forms.filter(f=>f.register&&f.register.je_register&&f.register.je_register[c])
      .map(f=>{const r=f.register.je_register[c]; return {id:f.id,rang:r.bestaetigt*1000+r.beilagen,
        extra:[r.bestaetigt?pl(r.bestaetigt,'Angabe','Angaben')+(r.pflicht?` (${nf(r.pflicht)} Pflicht)`:''):'',r.beilagen?pl(r.beilagen,'Beilage','Beilagen'):''].filter(Boolean).join(', ')};});
    const ew_=c==='einwohnerregister'&&VF&&VB?`<div class="dmvb"><b>Vorbefüllbar:</b> ${pl(VF.pflicht,'Pflichtangabe','Pflichtangaben')} (${nf(VF.alle)} mit den freiwilligen) in ${pl(VF.formulare,'Formular','Formularen')} — die Angaben, die die geführten Formulare (Prototyp) vorbefüllen: Angaben der einreichenden Person (Gesuchsteller/in, natürliche Person), nicht mehrdeutig und nach dem heutigen Wert gefragt.
        <div class="sumbox"><div class="gcap">Nach der früheren Regel heute: ${nf(VB.bisher)} — davon ausgeschlossen <b class="sumtot">${nf(VB.n_ausgeschlossen)}</b>, hinzu ${nf(VB.hinzu)} = ${nf(VB.korrigiert)}:</div>
        <ul class="tleg dmgr">${Object.entries(VB.ausgeschlossen||{}).map(([r,n])=>`<li><b class="sumn">${nf(n)}</b><span>${esc(lab(VB.gruende,r))}</span></li>`).join('')}</ul></div>
        ${VB.zeitbezug?`<p class="small muted">${pl(VB.zeitbezug.punkte_mit_marke,'Datenpunkt','Datenpunkte')} mit ↺ (Einwohnerregister) in ${pl(VB.zeitbezug.formulare_mit_zeitbezug,'Formular','Formularen')} fragen nach einem Wert einer anderen Zeit («früher», «neu», «Änderung», «seit» …) und werden nicht vorbefüllt. ${esc(HI.zeit||'')}</p>`:''}</div>`:'';
    return `<div class="card gm dmrc" id="or-${esc(c)}"><div class="gmhd"><h5>${esc(k.name)}</h5> ${stBadge('dec',esc(lab(DML.zugriff_status,k.zugriff_status)),k.bemerkung||lab(DML.zugriff_status,k.zugriff_status))}</div>
      <dl class="dmfacts">${fact('Inhaber',esc(k.inhaber||''))}${fact('Ebene',esc(lab(DML.register_ebene,k.ebene)))}${fact('Hält',esc(k.inhalt||''))}${fact('Schlüssel',esc(k.schluessel||''))}
        ${fact('eCH-Standards',(k.standards||[]).map(esc).join(', ')||'<span class="muted">keiner erfasst</span>')}${fact('Stelle im Kanton',esc(k.stelle_sh||''))}
        ${fact('Quellen',urls.map(quelle).join('<br>'))}</dl>
      <div class="dmzr"><span><b>${nf(z.bestaetigt)}</b> ${plw(z.bestaetigt,'Angabe','Angaben')} <span class="small muted">(${nf(z.bestaetigt_pflicht)} Pflicht, in ${pl(z.formulare_bestaetigt,'Formular','Formularen')}) — ${esc(ST.bestaetigt||'')}</span></span>
        ${z.obergrenze!==z.bestaetigt?`<span><b>${nf(z.obergrenze)}</b> ${plw(z.obergrenze,'Angabe','Angaben')} <span class="small muted">(${nf(z.obergrenze_pflicht)} Pflicht, in ${pl(z.formulare_obergrenze,'Formular','Formularen')}) — ${(k.standards||[]).length?esc(ST.standard||''):'Obergrenze (kein eCH-Standard erfasst, darum auf der Stufe des Elements): jede Angabe, deren Element eine zitierte Regel des Registers nennt — auch wo die Art der Partei offen ist'}</span></span>`:''}
        ${z.partei_offen?`<span><b>${nf(z.partei_offen)}</b> ${plw(z.partei_offen,'Angabe','Angaben')} <span class="small muted">— ${esc(ST.element||'')}</span></span>`:''}
        ${parteiTeile(z)?`<span class="small muted">Unter den bestätigten: ${parteiTeile(z)}</span>`:''}
        ${z.beilagen?`<span><b>${nf(z.beilagen)}</b> ${plw(z.beilagen,'Beilage','Beilagen')} in ${pl(z.formulare_beilagen,'Formular','Formularen')}${z.beilagen_original||z.beilagen_rueckgabe?` <span class="small muted">(${[z.beilagen_original?nf(z.beilagen_original)+' im Original verlangt':'',z.beilagen_rueckgabe?nf(z.beilagen_rueckgabe)+' abgegeben oder umgetauscht':''].filter(Boolean).join(', ')})</span>`:''}</span>`:''}</div>
      ${ew_}
      ${fms.length?gFolded(`${pl(fms.length,'Formular','Formulare')} anzeigen, deren Angaben oder Beilagen es hält`,dmFormList(fms,'reg')):''}</div>`;};
  const gTeile=g=>{const t=g.partei; if(!t) return '';
    return ` — davon ${nf(t.eigene)} der einreichenden Partei, ${nf(t.andere)} anderer Parteien, ${nf(t.unklar+t.art_offen)} mit ungeklärter Partei`;};
  const sGr=REG_GRP.map(g=>sec('g-'+g.key,esc(g.label),`<p class="gfrage">${esc(g.frage)} ${g.punkte?`${pl(g.punkte,'Angabe','Angaben')} (${nf(g.pflicht)} Pflicht) in ${pl(g.formulare,'Formular','Formularen')} hält ein Register dieser Gruppe laut Quelle, und die Art der Partei passt${gTeile(g)}`:'Keine Angabe der Formulare ist einem Register dieser Gruppe mit einer Quelle zugeordnet'}${g.beilagen?`; dazu ${pl(g.beilagen,'Beilage','Beilagen')} in ${pl(g.formulare_beilagen,'Formular','Formularen')}`:''}.${(g.register||[]).length>1?' Eine Angabe kann in mehreren Registern stehen; die Gruppe zählt sie einmal.':''}</p>`
    +(g.register||[]).map(regCard).join(''))).join('');
  // (3) Beilagen
  const byReg=(DM.beilagen||{}).je_register||{};
  const sBei=sec('beilagen','Beilagen, die ein Register ausstellt',
    `<p class="gfrage">Von ${pl(GS.beilagen,'Beilage','Beilagen')}, die die Formulare verlangen, nennt die Bezeichnung von ${nf(GS.beilagen_register)} ein Dokument, das ein Register ausstellt oder hält — einen Fahrzeugausweis, einen Handelsregisterauszug, eine Wohnsitzbestätigung. ${esc(HI.beilagen_leser||'')}</p>
     <p class="gvorb">Nicht ersetzbar, auch wenn das Register das Dokument hält: ${nf(GS.beilagen_original)} im Original verlangt, ${nf(GS.beilagen_rueckgabe)} abgegeben oder umgetauscht, ${nf(GS.beilagen_identitaet)} als Identitätsnachweis${GS.beilagen_ausland?`; ${pl(GS.beilagen_ausland,'Beilage stammt','Beilagen stammen')} aus einem anderen Staat und zählen nicht`:''}.</p>
     <div class="card gm sumbox"><div class="gcap"><b class="sumtot">${nf(GS.beilagen_register)}</b> Beilagen nach Register</div>${Object.keys(byReg).sort((a,b)=>(((REG_BY[b]||{}).zahlen||{}).beilagen||0)-(((REG_BY[a]||{}).zahlen||{}).beilagen||0)||regName(a).localeCompare(regName(b),'de')).map(c=>{
       const L=byReg[c]||[], n=((REG_BY[c]||{}).zahlen||{}).beilagen||0;
       return `<div class="gfr"><div><b class="sumn">${nf(n)}</b> ${goLink('onceonly','r-'+c,esc(regName(c)),'dlink lt')}</div><div>${L.map(x=>{
         const W=Object.entries(x.ersetzt_nicht||{});
         return `«${esc(x.bezeichnung)}»${x.n>1?' '+nf(x.n)+'×':''}${W.length?` <span class="small muted">(${W.map(([w,k])=>`${x.n>1?(k===x.n?'alle':nf(k)+' davon')+': ':''}${esc(lab(DML.ersetzt_nicht,w))}`).join('; ')})</span>`:''}`;}).join(' · ')}</div></div>`;}).join('')}</div>`);
  // (4) model estimate
  const TK=(DATA.themenkatalog||[]).filter(t=>t.register&&(t.register.minuten_modell||t.register.n_vorbefuellbar_korrigiert)).sort((a,b)=>b.register.minuten_modell-a.register.minuten_modell||a.gruppe.localeCompare(b.gruppe,'de'));
  const tRow=t=>{const r=t.register; return `<tr><td><a class="dlink lt" href="#lebenslagen/all/g-${encodeURIComponent(t.id)}" data-go="lebenslagen" data-sub="g-${esc(t.id)}">${esc(t.gruppe)}</a><div class="small muted">${esc(lab(KAT_DE,t.katalog))} · ${pl(t.n_formulare,'Formular','Formulare')}</div></td>
    <td class="num">${ML('Pflichtangaben')}${nf(r.n_pflicht_register)}</td><td class="num">${ML('Beilagen')}${nf(r.n_beilagen_register)}</td><td class="num">${ML('Minuten')}<b>${nf1(r.minuten_modell)}</b></td><td class="num">${ML('vorbefüllbar')}${nf(r.n_vorbefuellbar_korrigiert)}<div class="small muted">${nf1(r.minuten_vorbefuellt)} Min.</div></td></tr>`;};
  const tHead='<thead><tr><th>Themengruppe (Lebenslage)</th><th class="num">Pflichtangaben im Register</th><th class="num">Beilagen</th><th class="num">Minuten (Modell)</th><th class="num">davon vorbefüllbar (Einwohnerregister)</th></tr></thead>';
  const sZeit=sec('zeit','Gesparte Zeit (Modellschätzung)',
    `<p class="gfrage">${esc(MO.hinweis||'')} Das Modell rechnet ${nf1(MO.min_angabe)} Minuten je Pflichtangabe und ${nf1(MO.min_beilage)} Minuten je Beilage.</p>
     <div class="regstats"><span class="rstat">obere Grenze, alle Register <b>${nf1(GS.minuten_modell)} Min.</b> ${MD?`<span class="small muted">— ${pl(MD.pflicht,'Pflichtangabe','Pflichtangaben')} und ${pl(MD.beilagen,'Beilage','Beilagen')}, die ein Register hält: auch Angaben anderer Parteien und Fragen nach einem anderen Zeitpunkt, und bei jedem Register ist offen, ob die Dienststelle beziehen darf (Beilagen, die das Original verlangen oder abgegeben werden, zählen nicht)</span>`:''}</span>
       ${VB?`<span class="rstat">davon nach der Regel der Vorbefüllung (Einwohnerregister) <b>${nf1(VB.minuten_korrigiert)} Min.</b> <span class="small muted">— ${pl(VB.korrigiert,'Pflichtangabe','Pflichtangaben')} der einreichenden Person; nach der früheren Regel heute ${nf1(VB.minuten_bisher)} Min.</span></span>`:''}</div>
     <p class="gvorb">${esc(HI.themengruppe||'')} Je Themengruppe (eCH-0049) die Formulare ihrer Services; eine Gruppe mit mehreren Services fasst Angebote zusammen, die sich ausschliessen können.</p>
     ${TK.length?`<div class="card tscroll"><table class="ft dmtk dmstack">${tHead}<tbody>${TK.slice(0,15).map(tRow).join('')}</tbody></table>
       ${TK.length>15?gFolded(`alle ${nf(TK.length)} Themengruppen anzeigen`,`<table class="ft dmtk dmstack">${tHead}<tbody>${TK.slice(15).map(tRow).join('')}</tbody></table>`):''}</div>`:''}`);
  // (5) the canton's open decisions
  const zRows=Object.values(REG_BY).slice().sort((a,b)=>(a.zugriff_status==='offen')-(b.zugriff_status==='offen')||a.name.localeCompare(b.name,'de')).map(k=>
    `<tr><td>${goLink('onceonly','r-'+k.code,esc(k.name),'dlink lt')}</td><td>${stBadge('dec',esc(lab(DML.zugriff_status,k.zugriff_status)),'Ob die Dienststelle beziehen darf, was das Register hält, klären die Juristinnen und Juristen des Kantons')}</td>
      <td class="small dmw">${(k.zugriff||[]).length?(k.zugriff||[]).map(z=>`<details class="qd"><summary>${esc(lab(DML.zugriff_art,z.art))}: ${esc(z.artikel)}</summary><blockquote class="quote">«${esc(z.zitat)}»</blockquote><div class="small muted">${z.adressat?`Adressat laut Text: ${esc(z.adressat)}`:'Adressat: im Artikel nicht genannt'}</div></details>`).join(''):`<span class="muted">${esc(k.bemerkung||'kein Artikel als Kandidat in der Databank')}</span>`}</td></tr>`).join('');
  const sOffen=sec('offen','Offene Rechtsfragen — für den Kanton',
    `<p class="gfrage">Die Zahlen dieser Seite sagen, was ein Register hält. Ob eine Dienststelle es beziehen darf, richtet sich nach dem Recht des Registers — bei kantonalen Stellen nach KDSG Art. 8 Abs. 1, bei Registern des Bundes nach Bundesrecht; das klären die Juristinnen und Juristen des Kantons. Drei Entscheide stehen offen.</p>
     <h5 class="dmh">1 · Zugriff je Register</h5>
     <div class="card tscroll sumbox"><table class="ft dmzg dmstack"><caption class="gcap">${Object.entries(ZG).map(([k,n])=>`<b class="sumn">${nf(n)}</b> ${esc(lab(DML.zugriff_status,k))}`).join(' · ')} — zusammen <b class="sumtot">${nf(nReg)}</b> Register</caption><thead><tr><th>Register</th><th>Zugriff</th><th>Artikel in der Databank — möglicher Kandidat oder Schranke</th></tr></thead><tbody>${zRows}</tbody></table></div>
     ${EA?`<h5 class="dmh">2 · ${esc(EA.familie.label||'Familienangehörige')}</h5>
     <p class="gmq">${stBadge('dec','Entscheid des Kantons','Ob das Einwohnerregister Angaben von Familienangehörigen und weiteren Personen im Haushalt für ein Formular liefern darf, entscheidet der Kanton')} ${pl(EA.familie.punkte,'Angabe','Angaben')} (${nf(EA.familie.pflicht)} Pflicht) in ${pl(EA.familie.formulare,'Formular','Formularen')} gehören ${EA.familie.rollen.map(r=>esc(rolleLabel(r))).join(', ')} der einreichenden Person und tragen die Marke des Einwohnerregisters. Vorbefüllt wird keine davon, bis der Kanton entscheidet, ob das Register solche Angaben liefern darf. Mit allen übrigen Parteien sind es ${pl(EA.punkte,'Angabe','Angaben')}:</p>
     <div class="card gm sumbox"><div class="gcap"><b class="sumtot">${nf(EA.punkte)}</b> Angaben mit der Marke des Einwohnerregisters, die einer anderen Partei als der einreichenden Person gehören</div><ul class="tleg dmgr dmcols">${Object.entries(EA.je_rolle||{}).map(([r,n])=>`<li><b class="sumn">${nf(n)}</b><span>${esc(rolleLabel(r))}</span></li>`).join('')}</ul></div>`:''}
     ${PAR?`<h5 class="dmh">3 · Die Rollenliste</h5><p class="gmq">${stBadge('dec','Vorschlag der Databank','Der Kanton bestätigt die Rollenliste')} Wessen Angabe ein Datenpunkt ist, beruht auf ${pl(PAR.rollen.length,'Rolle','Rollen')}, die die Databank vorschlägt; der Kanton bestätigt sie. ${goLink('datenmodell','parteien','Zur Rollenliste ›','inl')}</p>`:''}`);
  m.innerHTML=pageHead('Was Register schon wissen',
    'Welche Angaben und Beilagen der Formulare ein Register schon hält — und wie viel Zeit das sparen könnte. Die Zahlen sagen, was ein Register hält, nicht, dass der Kanton es beziehen darf.',
    'Die Register der Schweiz und des Kantons mit Inhaber, Inhalt, Schlüssel und Quelle; je Register die Angaben der Formulare, die es laut Quelle hält, und die Formulare dazu; die Beilagen, die ein Register ausstellt; die Zeit, die das sparen könnte (Modellschätzung); und die Fragen, die der Kanton entscheidet.',
    `Register, Inhalt und Schlüssel aus amtlichen Quellen, die die Databank gelesen hat (Gesetze, Verordnungen, Seiten der Bundesämter). Eine Angabe zählt als «bestätigt», wenn eine zitierte Quelle sagt, dass das Register sie führt, und die Art der Partei passt (natürliche Person bzw. Organisation) — wessen Angabe es ist, sagt die Karte jedes Registers; die «obere Grenze» nimmt jede Angabe eines eCH-Standards, mit dem das Register Daten austauscht. ${esc(HI.formular||'')}`,
    'Amber, was der Kanton entscheidet: der Zugriff je Register und die Angaben von Familienangehörigen. Alle Zahlen sind neutral; eine Zahl ist kein Auftrag.')
    +(bad?`<div class="nores">Den Abschnitt «${esc(sub)}» gibt es auf dieser Seite nicht — gezeigt wird die ganze Seite.</div>`:'')
    +`<p class="gvorb oovorb">Ein Register hält eine Angabe — das heisst nicht, dass eine Dienststelle sie beziehen darf. Ob sie es darf, richtet sich nach dem Recht des Registers: bei kantonalen Stellen nach KDSG Art. 8 Abs. 1 (eine gesetzliche Grundlage, lit. a, oder der Bedarf für die gesetzlichen Aufgaben des Empfängers, lit. b; besonders schützenswerte Personendaten nach Art. 5, Art. 8 Abs. 3), bei Registern des Bundes nach Bundesrecht. Das klären die Juristinnen und Juristen des Kantons, auch wo die Databank einen Artikel als möglichen Kandidaten zitiert.</p>`
    +`<section class="hsec"><h4>Wo anfangen?</h4><div class="doors gdoors">${doors}</div></section>`
    +sKat+sGr+sBei+sZeit+sOffen
    +`<div class="datenstand"><b>Datenstand</b> — ${esc(datenstandText())}</div>`;
  dmWire(m); wireGo(m);
  if(!bad&&sub) dmFocus(m,sub.startsWith('r-')?'or-'+sub.slice(2):'oo-'+sub);
}

// ---------- the panels of a Formular: «Parteien» and «Was Register schon wissen» ----------
// Folded, one line of summary; open: each party with its role, its kind, how the Formular names it,
// the quote and its data points; the «unklar» points with their reason. The second panel: per
// register the Angaben and Beilagen it holds, the vorbefüllbar ones marked, and the model estimate.
function parteiPanel(fm,open){
  if(!PAR||!(fm.data_fields||[]).length) return '';
  const U=unitsOf(fm), P=fm.parteien||[], HK=DML.herkunft||{};
  const by={}, unk=[], off=[];
  U.forEach(x=>{const pa=x.u.partei||{}; if(pa.status==='zugeordnet') (by[pa.nr]=by[pa.nr]||[]).push(x); else if(pa.status==='unklar') unk.push(x); else off.push(x);});
  const PZ=fm.partei_zahlen||{};
  const sum=[`${pl(P.length,'Partei','Parteien')}`,`${nf(PZ.zugeordnet)} von ${pl(PZ.punkte,'Datenpunkt','Datenpunkten')} zugeordnet`,PZ.unklar?`${nf(PZ.unklar)} «unklar»`:'',PZ.offen?`${nf(PZ.offen)} noch nicht abgeleitet`:''].filter(Boolean).join(' · ');
  const names=L=>{const a=L.map(x=>esc(x.name)); return a.length>14?a.slice(0,14).join(' · ')+gFolded(`weitere ${nf(a.length-14)} anzeigen`,a.slice(14).join(' · ')):a.join(' · ');};
  const rows=P.map(p=>{const L=by[p.nr]||[];
    return `<div class="gfr"><div><b>${esc(rolleLabel(p.rolle))}</b><div class="small muted">${esc(entLabel(p.entitaet))}${p.mehrere?' · mehrere':''}</div></div>
      <div>«${esc(p.bezeichnung)}» <span class="small muted">· ${esc(lab(HK,p.herkunft))}</span>${p.beleg?`<div class="small muted pbeleg">Beleg im Formular: <span data-wortlaut>«${esc(p.beleg)}»</span></div>`:''}
        <div class="small">${p.n_punkte?`<b>${pl(p.n_punkte,'Datenpunkt','Datenpunkte')}:</b> ${names(L)}`:'<span class="muted">kein Datenpunkt zugeordnet</span>'}</div></div></div>`;}).join('');
  const why=x=>{const pa=x.u.partei||{}; return pa.code==='urteil'?String(pa.grund||''):lab(PAR.gruende,pa.code);};
  const unkRows=unk.length?`<div class="gfgrp">«unklar» — ${pl(unk.length,'Datenpunkt','Datenpunkte')}, jeder mit einem Grund</div>${unk.map(x=>`<div class="gfr"><div>${esc(x.name)}</div><div class="small" data-wortlaut>${esc(why(x))}</div></div>`).join('')}`:'';
  const offRows=off.length?`<div class="gfgrp">Noch nicht abgeleitet</div><div class="gfr gfr1"><div class="small">${names(off)}</div></div>`:'';
  return `<details class="card gpanel ppanel" id="part-${esc(fm.id)}"${open?' open':''}><summary><span class="dvsub">Parteien</span> <span class="gsumm">${sum}</span></summary>
    ${P.length?rows:'<p class="dsnone">Das Formular nennt keine Partei, die die Databank belegen könnte.</p>'}${unkRows}${offRows}
    <div class="gfoot">Wessen Angabe: ${esc(lab(HK,'urteil'))} (mit Zitat, zweitgeprüft) oder ${esc(lab(HK,'regel'))}; die Rollen sind ein Vorschlag der Databank, den der Kanton bestätigt — ${goLink('datenmodell','parteien','Datenmodell: Parteien und Rollen ›','inl')}</div></details>`;
}
function registerPanel(fm,open){
  if(!REG) return '';
  const R=fm.register||{}, JE=R.je_register||{}, codes=Object.keys(JE), b=fm.burden||{};
  const bei=(fm.beilagen||[]).filter(x=>(x.register||[]).length);
  if(!codes.length&&!bei.length&&!b.prefillable&&!b.prefillable_bisher) return '';
  const U=unitsOf(fm);
  const sum=[codes.length?`${pl(codes.length,'Register','Register')} ${plw(codes.length,'hält','halten')} Angaben dieses Formulars`:'',
    b.prefillable?`${nf(b.prefillable)} ${plw(b.prefillable,'Pflichtangabe','Pflichtangaben')} vorbefüllbar (~${nf1(b.minutes_saved||0)} Min.)`:'',
    bei.length?pl(bei.length,'Beilage','Beilagen')+' aus einem Register':'',
    R.minuten_modell?`obere Grenze ~${nf1(R.minuten_modell)} Min. für ${[R.pflicht_bestaetigt?pl(R.pflicht_bestaetigt,'Pflichtangabe','Pflichtangaben'):'',R.beilagen?pl(R.beilagen,'Beilage','Beilagen'):''].filter(Boolean).join(' und ')}, die ein Register hält (Modellschätzung)`:''].filter(Boolean).join(' · ');
  const rows=codes.sort((a,c)=>(JE[c].bestaetigt-JE[a].bestaetigt)||a.localeCompare(c)).map(c=>{const z=JE[c];
    const L=U.filter(x=>((x.u.register_bezug||{}).bestaetigt||[]).includes(c));
    const it=L.map(x=>`${esc(x.name)}${x.d.required?' <span class="req">✱ Pflicht</span>':''}${c==='einwohnerregister'&&x.u.vorbefuellbar?' <span class="regc" title="Vorbefüllbar aus dem Einwohnerregister: eine Angabe der einreichenden Person, nach dem heutigen Wert gefragt">↺ vorbefüllbar</span>':''}${c==='einwohnerregister'&&x.u.zeitbezug?' <span class="small muted">(fragt nach einem Wert einer anderen Zeit — nicht vorbefüllt)</span>':''}`);
    const BL=bei.filter(x=>x.register.some(r=>r.register===c));
    return `<div class="gfr"><div>${goLink('onceonly','r-'+c,esc(regName(c)),'dlink lt')}<div class="small muted">${[z.bestaetigt?pl(z.bestaetigt,'Angabe','Angaben')+` (${nf(z.pflicht)} Pflicht)`:'',z.beilagen?pl(z.beilagen,'Beilage','Beilagen'):''].filter(Boolean).join(' · ')}</div></div>
      <div class="small">${it.join(' · ')}${BL.length?`<div>${BL.map(x=>`Beilage «${esc(x.bezeichnung)}»${x.register_ersetzt_nicht?` <span class="muted">(${esc(lab(DML.ersetzt_nicht,x.register_ersetzt_nicht))} — zählt im Modell nicht)</span>`:''}`).join(' · ')}</div>`:''}</div></div>`;}).join('');
  const AG=b.prefillable_ausgeschlossen||{}, ag=Object.entries(AG).filter(([,n])=>n);
  const vb=(b.prefillable||b.prefillable_bisher)?`<div class="gfgrp">Vorbefüllung aus dem Einwohnerregister</div><div class="gfr gfr1"><div class="small">${pl(b.prefillable||0,'Pflichtangabe','Pflichtangaben')} vorbefüllbar (~${nf1(b.minutes_saved||0)} Min.)${b.prefillable_bisher!==b.prefillable?` — nach der früheren Regel ${nf(b.prefillable_bisher)}${ag.length?`; nicht mehr gezählt: ${ag.map(([k,n])=>`${nf(n)} ${esc(lab((VORB||{}).gruende,k))}`).join('; ')}`:''}${b.prefillable_hinzu?`; hinzu ${nf(b.prefillable_hinzu)}`:''}`:''}.</div></div>`:'';
  return `<details class="card gpanel rpanel" id="reg-${esc(fm.id)}"${open?' open':''}><summary><span class="dvsub">Was Register schon wissen</span> <span class="gsumm">${sum||'kein Register hält eine Angabe dieses Formulars laut Quelle'}</span></summary>
    <p class="small muted">${esc((REG.hinweise||{}).formular||'')} ${esc((REG.hinweise||{}).zeit||'')}</p>${rows}${vb}
    <div class="gfoot">Ein Register hält die Angabe — ob die Dienststelle sie beziehen darf, ist offen. ${goLink('onceonly','','Was Register schon wissen ›','inl')}</div></details>`;
}
// the panel «Eine Angabe — ein Element» of a Formular (forms[].konzepte, konzepte.py): its data points
// that use another eCH element than the Vorschlag for the same Angabe of the same party role — each
// with its field, concept, role, element and the Vorschlag; drawn only where there is one
function konzeptPanel(fm){
  const K=fm.konzepte; if(!KONZ||!K||!K.n_abweichend) return '';
  const byK=Object.fromEntries((KONZ.konzepte||[]).map(k=>[k.code,k]));
  const feld=Object.fromEntries((fm.data_fields||[]).map(d=>[d.id,d.name]));
  const el=e=>`<span class="mono">${esc(String(e||'').replace(':','·'))}</span>`;
  const rows=(K.abweichungen||[]).map(a=>{const k=byK[a.konzept];
    return `<div class="gfr"><div>${esc(feld[a.feld]||'')}${a.teil?' › '+esc(a.teil):''}<div class="small muted">${k?goLink('datenmodell','k-'+a.konzept,esc(k.label),'dlink lt'):esc(a.konzept)} · ${esc(rolleLabel(a.rolle))}, ${esc(entLabel(a.entitaet))}</div></div>
      <div class="small">${el(a.element)} — Vorschlag: ${el(a.vorschlag)}</div></div>`;}).join('');
  const sum=`${pl(K.n_abweichend,'Datenpunkt nutzt','Datenpunkte nutzen')} ein anderes Element als der Vorschlag · ${pl(K.n_punkte,'Datenpunkt','Datenpunkte')} in einem Konzept`;
  return `<details class="card gpanel kpanel" id="konz-${esc(fm.id)}"><summary><span class="dvsub">Eine Angabe — ein Element</span> <span class="gsumm">${sum}</span></summary>
    <p class="small muted">Für dieselbe Angabe derselben Partei nutzen über alle Formulare mindestens zwei Drittel der Datenpunkte das Element des Vorschlags; dieses Formular nutzt ein anderes. Der Vorschlag beschreibt die Praxis der Formulare und wartet auf die Bestätigung des Kantons — ein Befund zum Datenstandard, nicht in den offenen Punkten gezählt.</p>${rows}
    <div class="gfoot">${goLink('datenmodell','konzepte','Datenmodell: Eine Angabe — ein Element ›','inl')}</div></details>`;
}
// the Formular-Ansicht opened at one of its panels (#…/form-<id>~part, ~reg): open, in view, focused
function focusPanel(id){
  if(comingBack()) return;
  setTimeout(()=>{const t=document.getElementById(id); if(!t) return; if(t.tagName==='DETAILS') t.open=true;
    t.scrollIntoView({behavior:MOTION}); focusIn(t); t.classList.add('flash'); setTimeout(()=>t.classList.remove('flash'),1600);},0);
}
// the section «Datenmodell und Register» of a Dienststelle's briefing (datenmodell.dienststellen)
function dmBrief(d){
  const z=(DM.dienststellen||{})[d.slug]; if(!z||!z.formulare) return '';
  return `<div class="dsline"><span><b>${nf(z.zugeordnet)}</b> von ${pl(z.punkte,'Datenpunkt','Datenpunkten')} einer Partei zugeordnet (${pctTxt(z.zugeordnet,z.punkte)})${z.unklar?`, ${nf(z.unklar)} «unklar» mit einem Grund`:''} · ${pl(z.parteien,'Partei','Parteien')} in ${pl(z.formulare_mit_partei!=null?z.formulare_mit_partei:z.formulare,'Formular','Formularen')}</span></div>
    <div class="dsline"><span><b>${nf(z.vorbefuellbar)}</b> ${plw(z.vorbefuellbar,'Pflichtangabe','Pflichtangaben')} aus dem Einwohnerregister vorbefüllbar${z.vorbefuellbar?` in ${pl(z.formulare_vorbefuellbar,'Formular','Formularen')} (~${nf1(z.minuten_vorbefuellt)} Min.)`:''} · ${pl(z.register_pflicht,'Pflichtangabe','Pflichtangaben')}, die ein Register hält, und ${pl(z.beilagen_register,'Beilage','Beilagen')}, die ein Registerabruf ersetzen könnte (obere Grenze ~${nf1(z.minuten_modell)} Min., Modellschätzung)</span></div>
    <div class="kznote dsnote">Ein eigener Teil des Dashboards, nicht in den offenen Punkten dieses Briefings gezählt: wessen Angabe ein Datenpunkt ist und was ein Register schon hält. Ein Register hält eine Angabe — ob die Dienststelle sie beziehen darf, ist offen und rechtlich zu klären.</div>
    <div class="small noprint" style="margin-top:6px">${goLink('datenmodell','','Datenmodell ›','inl')} · ${goLink('onceonly','','Was Register schon wissen ›','inl')}</div>`;
}
// ---------- Für Dienststellen: every Dienststelle in one table, then one briefing each ----------
// DVSH groupings of services that are not an office with a leadership of their own — their
// contact is another office (checked against the DVSH harvest; the DVSH data stays as it is)
const SAMMEL=new Set(['Allgemein','Weitere Dienste','Departementssekretariat']);
const sammelTag=d=>SAMMEL.has(d.name)?` <span class="sammel" title="Im DVSH-Dienstleistungsmodell eine Sammelgruppe von Services, keine Dienststelle mit eigener Leitung; der Kontakt ist der, den das DVSH für diese Gruppe führt">Sammelgruppe im DVSH — keine eigene Leitung</span>`:'';
// the Schutzstufe, spelled out with its law (DATA.laws — never typed from memory)
const ISV_LAW=(DATA.laws||[]).find(l=>l.short_title==='ISV');
const ISV_TXT=`Schutzstufe nach der Informatiksicherheitsverordnung (ISV${ISV_LAW&&ISV_LAW.sr_number?', SHR '+ISV_LAW.sr_number:''})`;
function viewDienststellen(){
  if(state.sub&&state.sub!=='felder'){ viewDienststelle(state.sub); return; }
  const m=document.getElementById('main');
  const K=DATA.kopfzahlen||{}, KE=K.standard_ech;
  // grouped by department (DEPT_ORDER), A–Z inside
  const deps={};
  DST.forEach(d=>{const k=(d.department||'(ohne Departement)').trim(); (deps[k]=deps[k]||[]).push(d);});
  const depKeys=Object.keys(deps).sort(deptCmp);
  const all={act:0,dec:0,open:0};
  DST.forEach(d=>['act','dec','open'].forEach(t=>{all[t]+=((d.offen||{})[t])||0;}));
  const nAct=DST.filter(d=>d.offen&&d.offen.act>0).length;
  // the order of the Massnahmen: tier, then the fixed category order
  const actOrder=CAT_ORDER.filter(k=>TODO_BY[k]&&catTon(k)==='act').map(k=>'«'+esc(todoCat(k)[1])+'»').join(' vor ');
  let rows='';
  depKeys.forEach(dep=>{
    const ds=deps[dep].slice().sort((a,b)=>a.name.localeCompare(b.name,'de'));
    const sum={act:0,dec:0,open:0}; let pts=0, mit=0, nS=0, nF=0; const eg={ok:0,ok2:0,dec:0,open:0};
    ds.forEach(d=>{const S=d.standard||{}; pts+=S.punkte||0; mit+=S.mit_element||0; nS+=(d.services||[]).length; nF+=(d.formulare||[]).length;
      Object.entries(S.ech_ton||{}).forEach(([k,n])=>{eg[k]=(eg[k]||0)+n;});
      ['act','dec','open'].forEach(t=>{sum[t]+=((d.offen||{})[t])||0;});});
    rows+=`<tr class="deprow"><td><b>${esc(dep)}</b> <span class="muted">· ${pl(ds.length,'Dienststelle','Dienststellen')}</span><div class="small muted dsmob">${pl(nS,'Service','Services')} · ${pl(nF,'Formular','Formulare')}</div></td>
      <td class="num">${nf(nS)}</td><td class="num">${nf(nF)}</td>
      <td>${pts?`<span class="stdcell">${miniBar(eg,'Datenpunkte des Departements nach eCH-Stand')}<b>${pctTxt(mit,pts)}</b></span>`:''}</td>
      <td><span class="dsmobl ph">Offene Punkte</span>${tonNums(sum)}</td><td></td></tr>`;
    ds.forEach(d=>{
      const S=d.standard||{}, p=S.punkte||0, e=S.mit_element||0, MZ=massnahmenOf(d), mz=MZ[0], nf_=(d.formulare||[]).length, nS_=(d.services||[]).length;
      rows+=`<tr class="dstrow" data-slug="${esc(d.slug)}">
        <td>${goLink('dienststellen',d.slug,esc(d.name),'dlink')}${sammelTag(d)}<div class="small muted dsmob">${pl(nS_,'Service','Services')} · ${pl(nf_,'Formular','Formulare')}</div></td>
        <td class="num">${nf(nS_)}</td>
        <td class="num">${nf(nf_)}</td>
        <td>${p?`<span class="stdcell" title="${esc(`${nf(e)} von ${pl(p,'Datenpunkt','Datenpunkten')} mit eCH-Element`)}">${miniBar(S.ech_ton||{},'Datenpunkte nach eCH-Stand')}<b>${pctTxt(e,p)}</b></span><div class="small muted">${nf(e)} von ${nf(p)}</div>`
          :'<span class="small muted">keine Datenpunkte erfasst</span>'}</td>
        <td><span class="dsmobl ph">Offene Punkte</span>${nf_?tonNums(d.offen):'<span class="small muted">—</span>'}</td>
        <td class="small"><span class="dsmobl">Wichtigste Massnahme</span>${mz?`<i class="sw t-act"></i>${esc(mzKurz(mz))}: ${catUnit(mz.cat,mz.n)}${formCat(mz.cat)?'':' in '+pl(mz.formulare,'Formular','Formularen')}${MZ.length>1?` <span class="muted">· +${pl(MZ.length-1,'weitere Massnahme','weitere Massnahmen')}</span>`:''}`
          :`<span class="muted">${nf_?'keine Massnahme, die sie selbst treffen muss':'kein Formular in der Databank'}</span>`}</td></tr>`;
    });
  });
  m.innerHTML=pageHead('Für Dienststellen · Was muss ich an meinen Formularen ändern?',
    `Für jede der ${nf(DST.length)} Dienststellen: wie weit ihre Daten dem eCH-Standard folgen, wer ihre offenen Punkte lösen kann und was sie als Erstes ändern kann — eine Zeile öffnet das Briefing der Dienststelle.`,
    'Je Dienststelle die Zahl ihrer Services und Formulare, der Anteil ihrer Datenpunkte mit eCH-Element, die offenen Punkte nach «wer handelt» und die wichtigste Massnahme, die sie selbst treffen kann — mit ihrem Umfang; was genau zu tun ist und an welchen Formularen, steht im Briefing der Dienststelle. Darunter, aufklappbar, die Rechtsgrundlage je Service.',
    'Aus den offenen Punkten der einzelnen Formulare und ihrer Datenstandard-Schicht zusammengezählt — dieselben Zahlen wie in den Briefings der Dienststellen. Die roten und amber Punkte stehen ebenso im Handlungsbedarf, die grauen unter «Recherche der Databank», alle zusammen in der CSV des Handlungsbedarfs. Dienststelle, Departement und Kontakt laut DVSH-Dienstleistungsmodell; «Sammelgruppe im DVSH» heisst: das DVSH fasst dort Services zusammen, die keine eigene Dienststelle mit eigener Leitung haben.',
    `Rot: die Dienststelle kann es an ihrem Formular selbst ändern. Amber: es wartet auf einen Entscheid des Kantons. Grau: eine Hausaufgabe der Databank, kein Befund über die Dienststelle. Eine Massnahme fasst alle Punkte einer Kategorie über alle Formulare der Dienststelle zusammen. Die wichtigste folgt der Priorität: zuerst die Stufe (Datenstandard zuerst), dann die feste Reihenfolge der Kategorien (${actOrder}), erst zuletzt der Umfang.`)
    +tonKeyLine()
    +`<div class="regstats">
      ${KE?`<span class="rstat">Datenpunkte mit eCH-Element, ganzer Kanton <b>${pctTxt(KE.wert,KE.von)}</b></span>`:''}
      <span class="rstat">Dienststellen <b>${nf(DST.length)}</b></span>
      <span class="rstat" title="Dienststellen mit mindestens einem roten Punkt — etwas, das sie an ihren Formularen selbst ändern kann">mit eigenen Massnahmen <b>${nf(nAct)}</b></span>
      <span class="rstat">Offene Punkte ${tonNums(all)}</span></div>
    <div class="card tscroll"><table class="ft dsttab"><thead><tr><th>Dienststelle</th><th class="num">Services</th><th class="num">Formulare</th>
      <th title="Anteil der Datenpunkte mit dem Element eines eCH-Standards — der Balken zeigt auch die übrigen: hellgrün nur auf Standard-Ebene, amber ohne eCH-Standard oder Standard erst im Entwurf (kantonaler Entscheid, eSH), grau Zuordnung offen oder Standard nicht mehr in Kraft (Databank)">Datenstandard</th>
      <th title="rot: Dienststelle handelt · amber: Kanton entscheidet · grau: Databank recherchiert">Offene Punkte</th><th>Wichtigste Massnahme</th></tr></thead><tbody>${rows}</tbody></table></div>
    <details class="dsov"><summary>Rechtsgrundlage je Service — Dokumentationsstand der Databank, nach Departement</summary>${deptOverview({nested:true})}</details>`;
  m.querySelectorAll('tr.dstrow').forEach(tr=>tr.onclick=e=>{
    if(e.target.closest('a')) return;
    state.tab='dienststellen'; state.service='all'; state.sub=tr.dataset.slug; render();});
  m.querySelectorAll('tr[data-sid]').forEach(tr=>tr.onclick=e=>{
    if(e.target.closest('a')) return;
    state.tab='fields'; state.service=tr.dataset.sid; state.sub='felder'; render();});
  wireGo(m);
}
// one Dienststelle: the briefing for its leadership — one to two printed pages
function viewDienststelle(slug){
  const m=document.getElementById('main');
  const d=dstBySlug[slug];
  if(!d){
    m.innerHTML=pageHead('Dienststelle','Diese Dienststelle ist nicht in der Databank («'+esc(String(slug))+'») — der Link ist veraltet oder vertippt.')
      +`<div class="nores">${goLink('dienststellen','','Alle Dienststellen ›','inl')}</div>`;
    wireGo(m); return;
  }
  const fms=(d.formulare||[]).map(id=>formById[id]).filter(Boolean);
  const O=Object.assign({act:0,dec:0,open:0},d.offen||{});
  const nSvc=(d.services||[]).length, dep=d.department||'(ohne Departement)';
  const S1=STUFEN.find(s=>s.n===1);
  const kurz=!fms.length
    ?`${pl(nSvc,'Service','Services')}, aber kein Formular in der Databank — darum auch keine offenen Punkte zu Formularen.`
    :O.act
    ?`${pl(nSvc,'Service','Services')} mit ${pl(fms.length,'Formular','Formularen')}: ${pl(O.act,'offenen Punkt','offene Punkte')} kann die Dienststelle selbst lösen, ${nf(O.dec)} ${plw(O.dec,'wartet','warten')} auf einen Entscheid des Kantons, ${nf(O.open)} ${plw(O.open,'ist eine Hausaufgabe','sind Hausaufgaben')} der Databank — gezählt je Datenpunkt, Feld oder Formular, aufgeschlüsselt unten.`
    :`${pl(nSvc,'Service','Services')} mit ${pl(fms.length,'Formular','Formularen')}: Die Dienststelle muss an ihren Formularen selbst nichts ändern; ${pl(O.dec,'offener Punkt wartet','offene Punkte warten')} auf einen Entscheid des Kantons, ${nf(O.open)} ${plw(O.open,'ist eine Hausaufgabe','sind Hausaufgaben')} der Databank.`;
  // (1) what the Dienststelle can do itself: one line per red category, data standard first —
  // and why the data standard comes first, in the words of its priority tier
  const MZ=massnahmenOf(d);
  const s1=(S1?`<p class="stufetx">Zuerst der Datenstandard: ${esc(S1.text.charAt(0).toLowerCase()+S1.text.slice(1))}</p>`:'')
    +(MZ.length
    ?`<ol class="massn">${MZ.map(x=>`<li><i class="sw t-act"></i><b>${esc(x.aktion)}</b> — ${catUnit(x.cat,x.n)}${formCat(x.cat)?'':' in '+pl(x.formulare,'Formular','Formularen')}
        ${mzMix(x)}
        <div class="small">${x.formulare>1?'grösste: ':''}${x.gross.map(g=>mzFormRef(g.f,x.cat)+(x.formulare>1&&!formCat(x.cat)?` — ${catUnit(x.cat,g.n)}`:'')).join(' · ')}${x.formulare>x.gross.length?` · ${pl(x.formulare-x.gross.length,'weiteres Formular','weitere Formulare')}`:''}</div>
        <div class="small muted">${esc(stufeLabel(x.stufe))} · ${esc(todoCat(x.cat)[1])}</div></li>`).join('')}</ol>`
    :'<p class="dsnone">Keine Massnahme, die die Dienststelle selbst treffen muss.</p>');
  // (2) its data standard, as the export counted it (standard.ech_ton, the four parts of
  // the bar); an element the databank assigned wrongly is not settled — it is in the grey part
  const S=d.standard||{}, pts=S.punkte||0, EZ=S.ech||{}, g=Object.assign({ok:0,ok2:0,dec:0,open:0},S.ech_ton), zf=EZ.zuordnung_falsch||0, KE=(DATA.kopfzahlen||{}).standard_ech;
  const mitE=S.mit_element||0;
  // section (2) counts every Datenpunkt once (like the home page); the Massnahmen,
  // section (4) and the CSV count every entry of form.handlungsbedarf — where the two
  // differ, one line says by how much and why (reasons from standard_divergenzen)
  const stdNote=(()=>{
    let dvI=0, doI=0, multi=0, twiceA=0, twiceU=0, ovl=0;
    fms.forEach(f=>{todoItems(f).forEach(i=>{if(i.cat==='divergenz') dvI+=i.n; else if(i.cat==='divergenz_offen') doI+=i.n;});
      const act={}, unk={}, key=i=>String(i.feld)+'\u0001'+String(i.teilfeld||'');
      (((f.standard_divergenzen||{}).angleichen)||[]).forEach(i=>{const o=i.art==='pflicht_uneinheitlich'?unk:act; (o[key(i)]=o[key(i)]||[]).push(i.art);});
      Object.values(act).forEach(L=>{const u=new Set(L).size; multi+=u>1?1:0; twiceA+=L.length-u;});
      Object.entries(unk).forEach(([k,L])=>{twiceU+=L.length-1; if(act[k]) ovl++;});});
    const dp=S.div_punkte||0, dq=S.div_offen||0, parts=[];
    if(dvI!==dp){const why=[multi&&'ein Datenpunkt weicht mehrfach ab', twiceA&&'dieselbe Angabe steht zweimal auf einem Formular'].filter(Boolean);
      parts.push(`${catUnit('divergenz',dvI)} anders verlangt statt ${nf(dp)}${why.length?' ('+why.join('; ')+')':''}`);}
    if(doI!==dq){const why=[ovl&&`${nf(ovl)} ${plw(ovl,'wird','werden')} zugleich anders verlangt und ${plw(ovl,'zählt','zählen')} hier als rot`, twiceU&&'dieselbe Angabe steht zweimal auf einem Formular'].filter(Boolean);
      parts.push(`${nf(doI)} statt ${nf(dq)} ${catWord('divergenz_offen',doI)} «${esc(todoCat('divergenz_offen')[1])}»${why.length?' ('+why.join('; ')+')':''}`);}
    return parts.length?`<div class="kznote dsnote">Hier zählt jeder Datenpunkt einmal; die Massnahmen, die offenen Punkte nach Priorität und die CSV zählen jeden Eintrag: dort ${parts.join(' und ')}.</div>`:'';})();
  const s2=pts?`<div class="dsstdv"><span class="kzv">${pctTxt(mitE,pts)}</span><span class="kzsub" style="margin:0">${nf(mitE)} von ${pl(pts,'Datenpunkt','Datenpunkten')} tragen ein Element eines eCH-Standards${zf?` — bei ${nf(zf)} davon korrigiert die Databank die Zuordnung`:''}${KE?` — im ganzen Kanton ${pctTxt(KE.wert,KE.von)}`:''}.</span></div>
      <div class="kzziel">${esc(ZIEL_STD)}</div>
      ${tonBar([{t:'ok',n:g.ok,label:echOkLabel(zf)},
        {t:'ok2',n:g.ok2,label:'nur auf Standard-Ebene (der Standard hat keinen Elementkatalog)'},
        {t:'dec',n:g.dec,label:KS_LABEL()+(g.dec?' — steht unter «Was der Kanton entscheiden muss»':'')},
        {t:'open',n:g.open,label:stdOpenLabel(EZ),link:g.open?goLink('recherche',zf?'zuordnung':EZ.standard_alt?'echalt':'ech','Recherche der Databank ›','inl noprint'):''}],'Datenpunkte dieser Dienststelle nach eCH-Stand')}
      <ul class="tleg" style="margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)">
        <li${S.div_punkte?'':' class="zero"'}><i class="sw t-act"></i><b>${nf(S.div_punkte)}</b><span>${catWord('divergenz',S.div_punkte)} anders verlangt als die übrige Praxis (Pflicht, Format oder Werteliste)${S.formulare_div?` — in ${pl(S.formulare_div,'Formular','Formularen')}`:''} <span class="tw">· ${esc(tonLabel('act'))}</span></span></li>
        <li${S.div_offen?'':' class="zero"'}><i class="sw t-dec"></i><b>${nf(S.div_offen)}</b><span>${catWord('divergenz_offen',S.div_offen)} «${esc(todoCat('divergenz_offen')[1])}» — der Kanton legt fest, ob die Angabe Pflicht ist <span class="tw">· ${esc(tonLabel('dec'))}</span></span></li>
        <li${S.begriff_felder?'':' class="zero"'}><i class="sw t-act"></i><b>${nf(S.begriff_felder)}</b><span>${catWord('begriff',S.begriff_felder)} mit einer Bezeichnung, die auf den einheitlichen Begriff umzustellen oder aufzuteilen ist <span class="tw">· ${esc(tonLabel('act'))}</span></span></li>
      </ul>${stdNote}
      <div class="small noprint" style="margin-top:6px">${goLink('katalog','','Zum Datenkatalog ›','inl')} · ${goLink('begriffe','','Zu den Begriffen ›','inl')}</div>`
    :'<p class="dsnone">Für diese Dienststelle sind keine Datenpunkte erfasst.</p>';
  // (3) what only the canton can decide; a duplicate pair whose other form is counted at
  // another Dienststelle is named here too (pairs count once, on one of their forms)
  const EN=d.entscheide||[];
  let nSf=0, nSfm=0;
  fms.forEach(f=>{const k=(f.data_fields||[]).filter(x=>!x.schutzstufe).length; if(k){nSf+=k; nSfm++;}});
  const myIds=new Set(fms.map(f=>f.id)); let dupP=0; const dupPD=new Set();
  DATA.forms.forEach(f=>{if(myIds.has(f.id)) return; (f.similar||[]).forEach(s=>{
    if(!s.verdict&&f.id<s.form_id&&myIds.has(s.form_id)){dupP++; dupPD.add(dstOf(f));}});});
  const s3=(EN.length||dupP
      ?`<table class="ft"><thead><tr><th>Entscheid</th><th>Umfang</th></tr></thead><tbody>${EN.map(e=>`<tr>
          <td>${tonChip('dec',esc(todoCat(e.cat)[1]),null,tonLabel('dec')+' — '+todoCat(e.cat)[4])}${AKTION[e.cat]?`<div class="small muted">${esc(AKTION[e.cat])}</div>`:''}</td>
          <td>${catUnit(e.cat,e.n)}${formCat(e.cat)||e.cat==='dup'?'':' in '+pl(e.formulare,'Formular','Formularen')}<div class="small noprint">${goLink('kanton',e.cat,'im ganzen Kanton ›','inl')}</div></td></tr>`).join('')}${dupP?`<tr>
          <td>${tonChip('dec',esc(todoCat('dup')[1]),null,tonLabel('dec')+' — '+todoCat('dup')[4])}${AKTION.dup?`<div class="small muted">${esc(AKTION.dup)}</div>`:''}</td>
          <td>${pl(dupP,'Formularpaar','Formularpaare')} mit einem Formular ${[...dupPD].map(x=>'der Dienststelle «'+esc(x)+'»').join(', ')} — dort gezählt<div class="small noprint">${goLink('kanton','dup','im ganzen Kanton ›','inl')}</div></td></tr>`:''}</tbody></table>`
      :'<p class="dsnone">Kein Entscheid des Kantons zu einzelnen Formularen dieser Dienststelle offen.</p>')
    +(nSf?`<div class="dsline"><i class="sw t-dec"></i><span>${esc(ISV_TXT)} für ${pl(nSf,'Datenfeld','Datenfelder')} in ${pl(nSfm,'Formular','Formularen')} nicht festgelegt — eine Klassifizierung, die der Kanton für alle Dienststellen zugleich trifft.</span></div>`:'');
  // (4) every open point, by priority tier, each tier with the reason it has its place;
  // per tier the forms fold open
  const byS={};
  fms.forEach(f=>{const gi={}; todoItems(f).forEach(i=>{const s=itemStufe(i); (gi[s]=gi[s]||[]).push(i);});
    Object.entries(gi).forEach(([s,L])=>{(byS[s]=byS[s]||[]).push({f,its:L.sort(byPrio)});});});
  const tsum=(its,t)=>its.filter(i=>itemTon(i)===t).reduce((a,i)=>a+i.n,0);
  const s4=fms.length?STUFEN.map(st=>{
    const c=Object.assign({act:0,dec:0,open:0},(d.stufen||{})[String(st.n)]||{});
    const L=(byS[st.n]||[]).sort((a,b)=>tsum(b.its,'act')-tsum(a.its,'act')||tsum(b.its,'dec')-tsum(a.its,'dec')
      ||b.its.reduce((x,i)=>x+i.n,0)-a.its.reduce((x,i)=>x+i.n,0));
    return `<div class="dsstufe"><div class="dsshd"><b>${esc(stufeLabel(st.n))}</b>${tonNums(c)}</div><p class="stufetx">${esc(st.text)}</p>
      ${L.length?`<details class="dsdet"><summary>${pl(L.length,'Formular','Formulare')} mit Punkten dieser Stufe</summary>
        <table class="ft dsptab"><thead><tr><th>Formular</th><th>Offene Punkte dieser Stufe</th></tr></thead><tbody>${L.map(({f,its})=>`<tr><td>${formLink(f.service_id,f.id,esc(f.title),'',its.some(i=>DIV_SEC(i.cat))?'div':'')}</td>
          <td><ul class="pline">${its.map(i=>{const t=itemTon(i); return `<li>${tonChip(t,esc(todoCat(i.cat)[1]),chipN(i),`${tonLabel(t)} · ${catUnit(i.cat,i.n)} — ${todoCat(i.cat)[4]}`)}<span class="clipd">${clip(i.detail,160)}</span></li>`;}).join('')}</ul></td></tr>`).join('')}</tbody></table></details>`
        :'<div class="small muted">Keine offenen Punkte in dieser Stufe.</div>'}</div>`;}).join('')
    :'<p class="dsnone">Keine Formulare, keine offenen Punkte.</p>';
  // (5) the databank's own homework
  const rc={};
  fms.forEach(f=>todoItems(f).filter(i=>itemTon(i)==='open').forEach(i=>{rc[i.cat]=(rc[i.cat]||0)+i.n;}));
  const rk=Object.keys(rc).sort((a,b)=>catRank(a)-catRank(b));
  const s5=(O.open?`<div class="dsline"><i class="sw t-open"></i><span><b>${pl(O.open,'offener Punkt','offene Punkte')}</b> (Datenpunkte, Felder oder Formulare — aufgeschlüsselt darunter): Hausaufgaben der Databank — kein Befund über die Dienststelle.</span></div>`
      :'<p class="dsnone">Die Databank hat zu dieser Dienststelle keine offenen Recherche-Punkte.</p>')+`
    ${rk.length?`<div class="small muted" style="margin:4px 0 0 16px">${rk.map(k=>`${esc(todoCat(k)[1])}: ${catUnit(k,rc[k])}`).join(' · ')}</div>`:''}
    <div class="small noprint" style="margin:6px 0 0 16px">${goLink('recherche','','Zur Recherche der Databank ›','inl')}</div>`;
  // (6) its services and forms; printed, a long list becomes one line with the page's address
  const svcs=(d.services||[]).map(id=>svcById[id]).filter(Boolean).sort((a,b)=>a.name.localeCompare(b.name,'de'));
  const online=(window.__cgSite||'https://jastephan63.github.io/citygov/')+'dashboard.html#dienststellen/all/'+encodeURIComponent(d.slug);
  // one line per service; a Formular named like its service is not repeated
  const s6=svcs.length?`<ul class="dssvc">${svcs.map(s=>{const fs=formsByService[s.id]||[];
      return `<li>${svcLink(s.id,esc(s.name))} ${!fs.length?noFormBadge(s)
        :fs.length===1&&sameName(fs[0].title,s.name)?`<span class="small muted">· ${formLink(fs[0].service_id,fs[0].id,'Formular','dlink lt')}</span>`
        :`<span class="small muted dsfl">· ${plw(fs.length,'Formular','Formulare')} ${fs.map(f=>`«${formLink(f.service_id,f.id,esc(f.title),'dlink lt')}»`).join(' · ')}</span><span class="small muted dsfc">· ${fs.length===1?'Formular':pl(fs.length,'Formular','Formulare')}</span>`}</li>`;}).join('')}</ul>`
    :'<p class="dsnone">Keine Services in der Databank.</p>';
  // printed, more than a dozen services would push the briefing onto a third page
  const longList=svcs.length>12;
  const s6print=longList?`<div class="printonly small">${pl(svcs.length,'Service','Services')} mit ${pl(fms.length,'Formular','Formularen')} — vollständige Liste mit Links online: ${esc(online)}</div>`:'';
  const sec=(t,b,card,cls)=>`<section class="dssec${cls?' '+cls:''}"><h4>${t}</h4>${card===false?b:`<div class="card">${b}</div>`}</section>`;
  const sam=SAMMEL.has(d.name);
  m.innerHTML=`<div class="bcrumb noprint"><a href="#dienststellen" data-go="dienststellen">‹ Alle Dienststellen</a><span>›</span><span>${esc(dep)}</span></div>`
    +pageHead(esc(d.name)+sammelTag(d), kurz,
      'Das Briefing für die Leitung der Dienststelle: zuerst, was sie selbst ändern kann, dann ihr Datenstandard, die Entscheide des Kantons, alle offenen Punkte nach Priorität, die Hausaufgaben der Databank und ihre Services und Formulare.',
      'Aus den offenen Punkten der einzelnen Formulare zusammengezählt. Die roten und amber Punkte stehen ebenso im Handlungsbedarf, die grauen unter «Recherche der Databank», alle zusammen in der CSV des Handlungsbedarfs. Der Abschnitt «Datenstandard» zählt wie die Startseite jeden Datenpunkt einmal. Departement und Kontakt laut DVSH-Dienstleistungsmodell.',
      'Rot handelt die Dienststelle, amber entscheidet der Kanton, grau recherchiert die Databank. Die Prioritätsstufen beginnen beim Datenstandard. Die Formulare je Stufe sind aufklappbar: die Zahl auf einem Punkt zählt Datenpunkte, Felder oder Formularpaare, ein Punkt ohne Zahl betrifft das ganze Formular. Gedruckt erscheinen die Zahlen je Stufe, und die Liste der Services steht bei grossen Dienststellen nur online.')
    +tonKeyLine()
    +`<div class="card dshead"><div class="dsmeta">
        <div><span class="hsl">Departement</span>${esc(dep)}</div>
        <div>${kontaktHtml(d.kontakt)}${sam?` <span class="small muted">(gilt für die ganze Sammelgruppe; sie umfasst ${svcs.map(s=>'«'+esc(s.name)+'»').join(', ')||'keine Services'})</span>`:''}</div>
        <div class="printonly small"><span class="hsl">Online</span>${esc(online)}</div></div>
      <button class="srcbtn noprint" id="dsprint" type="button" title="Dieses Briefing drucken oder als PDF sichern — ohne Seitenleiste und Kopfzeile">⎙ Briefing drucken</button></div>`
    +sec('Die wichtigsten Massnahmen',s1)
    +sec('Datenstandard dieser Dienststelle',s2)
    +sec('Was der Kanton entscheiden muss',s3)
    +sec('Offene Punkte nach Priorität',s4)
    +sec('Recherche der Databank',s5)
    +(gestBrief(d)?sec('Gestaltung ihrer Formulare',gestBrief(d)):'')
    +(dmBrief(d)?sec('Datenmodell und Register',dmBrief(d)):'')
    +sec('Services und Formulare',`<div class="card">${s6}</div>`+s6print,false,'dssvcsec'+(longList?' long':''))
    +`<div class="datenstand"><b>Datenstand</b> — ${esc(datenstandKurz(fms))}</div>`;
  const pb=document.getElementById('dsprint'); if(pb) pb.onclick=()=>window.print();
  wireGo(m);
}
// ---------- Für den Kanton: what only the canton can decide (amber) ----------
function viewKanton(){
  const m=document.getElementById('main');
  const K=DATA.kopfzahlen||{}, E=K.standard_ech||{}, ET=E.teile||{}, U=K.standard_einheitlich||{}, UT=U.teile||{};
  const A=aggByCat('dec');
  const focus=(state.sub&&state.sub!=='felder')?state.sub:null;
  const badSub=focus&&!A[focus]&&focus!=='schutzstufe';
  // a category of this page that has no open points right now is not a bad link
  const emptySub=badSub&&TODO_BY[focus]&&catTon(focus)==='dec';
  if(badSub) state.sub='felder';
  // the data-standard decisions are the category cards of Stufe 1 — every gap once; the
  // cards say how they relate to the figures of the start page (kopfzahlen)
  const nEsh=(DATA.esh_katalog||[]).length, eshT=Object.fromEntries((DATA.esh_katalog||[]).map(k=>[k.code,k.titel]));
  const ks=A.kein_standard, dvo=A.divergenz_offen, extra={}, head={};
  if(ks){
    // «Kein geltender eCH-Standard» holds three different decisions: set an eSH draft in force,
    // fill a gap nobody has drafted yet, or wait for (or adopt) an eCH draft
    const echT=ECH_TITEL;
    const list=(codes,title,link)=>`<table class="ft"><thead><tr><th>Standard</th><th>Titel</th><th class="num">Datenpunkte</th></tr></thead><tbody>${
      Object.entries(codes).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([c,n])=>`<tr><td class="mono small nowrap">${link?`<a class="inl" href="#esh" data-go="esh">${esc(c)}</a>`:esc(c)}</td><td class="small">${esc(title[c]||'')}</td><td class="num">${nf(n)}</td></tr>`).join('')}</tbody></table>`;
    const cEsh=KS_C.esh||{}, cEch=KS_C.ech_entwurf||{}, nEshC=Object.keys(cEsh).length, nEchC=Object.keys(cEch).length;
    const nE=KS_T.esh||0, nO=KS_T.ohne||0, nW=KS_T.ech_entwurf||0;
    extra.kein_standard=`<ul class="tleg" style="margin-top:8px">
      <li><i class="sw t-dec"></i><b>${nf(nE)}</b><span>${catWord('kein_standard',nE)} in ${pl(KS_F.esh||0,'Formular','Formularen')}: ein eSH-Entwurf liegt vor — der Kanton setzt den Entwurf in Kraft (${pl(nEshC,'Entwurf','Entwürfe')})</span></li>
      <li><i class="sw t-dec"></i><b>${nf(nO)}</b><span>${catWord('kein_standard',nO)} in ${pl(KS_F.ohne||0,'Formular','Formularen')}: weder eCH-Standard noch eSH-Entwurf — eSH ergänzen oder bei eCH einen Standard beantragen</span></li>
      <li><i class="sw t-dec"></i><b>${nf(nW)}</b><span>${catWord('kein_standard',nW)} in ${pl(KS_F.ech_entwurf||0,'Formular','Formularen')}: eCH-Standard erst im Entwurf (${pl(nEchC,'Entwurf','Entwürfe')}) — eCH abwarten oder den Entwurf vorläufig übernehmen</span></li></ul>
    ${nEshC?`<details class="catdet"><summary>Die eSH-Entwürfe (${nf(nEshC)})</summary>${list(cEsh,eshT,true)}</details>`:''}
    ${nEchC?`<details class="catdet"><summary>Die eCH-Standards im Entwurf (${nf(nEchC)})</summary>${list(cEch,echT,false)}</details>`:''}
    <div class="kznote">${pctTxt(ks.n,E.von||0)} aller Datenpunkte — ${(ET.dec||0)===ks.n?'auf der Startseite der amber Teil':`die Startseite zählt ${nf(ET.dec||0)} im amber Teil`} von «Datenpunkte mit eCH-Element». Für ${nf(nE)} davon liegt ein eSH-Entwurf vor, für ${nf(nO+nW)} nicht; ein eSH-Entwurf ist kein offizieller eCH-Standard (${pl(nEsh,'Entwurf','Entwürfe')} im Katalog). ${goLink('esh','','Zum eSH-Katalog (Entwurf) ›','inl')}</div>`;
  }
  if(dvo){
    // the canton decides once per datum, not per Formular: the same points, by eCH element
    const PU=pflichtUneinheitlichAgg(), nPU=PU.reduce((a,x)=>a+x.n,0);
    const row=x=>`<tr><td><span class="mono small">${esc(x.el.replace('·',' · '))}</span><div class="small muted">«${esc(x.label)}»</div></td>
      <td class="small nowrap">${nf(x.req)} Pflicht · ${nf(x.opt)} optional</td><td class="num">${nf(x.forms.size)}</td><td class="num">${nf(x.n)}</td></tr>`;
    const thead=`<thead><tr><th>eCH-Element</th><th title="Wie die Formulare dieser Zeile die Angabe selbst verlangen">auf diesen Formularen</th><th class="num">Formulare</th><th class="num">Datenpunkte</th></tr></thead>`;
    head.divergenz_offen=`<b>${pl(PU.length,'Angabe','Angaben')} festzulegen</b>`;
    extra.divergenz_offen=`<div class="dvsub" style="margin-top:10px">Je Angabe — festgelegt wird einmal je Angabe, nicht je Formular</div>
      <div class="tscroll"><table class="ft">${thead}<tbody>${PU.slice(0,20).map(row).join('')}</tbody></table></div>
      ${PU.length>20?`<details class="catdet"><summary>alle ${nf(PU.length)} anzeigen</summary><div class="tscroll"><table class="ft">${thead}<tbody>${PU.slice(20).map(row).join('')}</tbody></table></div></details>`:''}
      <div class="kznote">${(UT.dec||0)===dvo.n?'Dieselbe Zahl wie auf der Startseite («Einheitlich verlangt», amber).'
        :`Gezählt wie im Handlungsbedarf: jede offene Festlegung je Formular. Die Startseite zählt jeden Datenpunkt nur einmal (${nf(UT.dec||0)}); ein Datenpunkt, der zugleich anders verlangt wird, zählt dort als rot.`}${nPU!==dvo.n?` Die Tabelle zählt ${nf(nPU)} Datenpunkte.`:''}
        ${goLink('katalog','','Im Datenkatalog ›','inl')}</div>`;
  }
  // the ISV protection level: open for the fields of every Dienststelle at once
  const ss={}; let nSf=0, nSfm=0, nAll=0, nSens=0; const sensF=new Set();
  DATA.forms.forEach(f=>{const dfs=f.data_fields||[]; nAll+=dfs.length; const k=dfs.filter(x=>!x.schutzstufe).length;
    dfs.forEach(x=>{if(x.sensitive&&!x.schutzstufe){nSens++; sensF.add(f.id);}});
    if(!k) return;
    nSf+=k; nSfm++; const dn=dstOf(f), e=ss[dn]=ss[dn]||{fields:0,forms:0}; e.fields+=k; e.forms++;});
  const ssRows=Object.entries(ss).sort((a,b)=>b[1].fields-a[1].fields||a[0].localeCompare(b[0],'de'))
    .map(([dn,e])=>`<tr><td>${dstLink(dn)}</td><td class="num">${nf(e.fields)}</td><td class="num">${nf(e.forms)}</td></tr>`).join('');
  const isv=nSf?`<div class="card catblk" id="cat-schutzstufe">
      <div class="cathd">${tonChip('dec','Schutzstufe (ISV) nicht festgelegt',null,tonLabel('dec'))}<span class="catn"><b>${pl(nSf,'Datenfeld','Datenfelder')}</b> in ${pl(nSfm,'Formular','Formularen')} bei ${pl(Object.keys(ss).length,'Dienststelle','Dienststellen')}</span></div>
      <div class="catx">${nSf===nAll?'Für kein Datenfeld':'Für '+pl(nSf,'Datenfeld','Datenfelder')+' von '+nf(nAll)} ist eine ${esc(ISV_TXT)} festgelegt. Das ist eine kantonale Klassifizierung; die Databank setzt bewusst keine Standardwerte.</div>
      ${AKTION.schutzstufe?`<div class="catx"><span class="hsl">Zu entscheiden</span>${esc(AKTION.schutzstufe)}</div>`:''}
      ${nSens?`<div class="catx"><span class="hsl">Ein Anfang</span>Die ${pl(nSens,'besonders schützenswerte Datenfeld','besonders schützenswerten Datenfelder')} (⛨) in ${pl(sensF.size,'Formular','Formularen')} — für solche Daten nennt ISV Art. 6 Abs. 1 lit. b die Vertraulichkeitsstufe G (besonders schützenswert).</div>`:''}
      <details class="catdet"${focus==='schutzstufe'?' open':''}><summary>Je Dienststelle (${nf(Object.keys(ss).length)})</summary>
        <div class="tscroll"><table class="ft"><thead><tr><th>Dienststelle</th><th class="num">Datenfelder</th><th class="num">Formulare</th></tr></thead><tbody>${ssRows}</tbody></table></div></details></div>`:'';
  const nDec=Object.values(A).reduce((a,x)=>a+x.n,0);
  // «Punkte» of different kinds: said, never summed silently
  const uS={}; Object.keys(A).forEach(k=>{const w=catUnitOf(k)[1]; uS[w]=(uS[w]||0)+A[k].n;});
  const uOrd=['Datenpunkte','Felder','Formularpaare','Formulare'];
  const uTxt=Object.entries(uS).sort((a,b)=>(uOrd.indexOf(a[0])+1||9)-(uOrd.indexOf(b[0])+1||9)).map(([w,n])=>`${nf(n)} ${UNIT_WORD(w)}`).join(' · ');
  const mostKs=ks&&ks.n*2>nDec;
  m.innerHTML=pageHead('Für den Kanton · Was muss entschieden werden?',
    `${pl(nDec,'offener Punkt wartet','offene Punkte warten')}${mostKs?' — die meisten davon Datenpunkte ohne geltenden eCH-Standard —':''} auf einen Entscheid des Kantons; der Datenstandard zuerst. Dazu die ${esc(ISV_TXT)}, die für alle Datenfelder noch festzulegen ist.`,
    'Alles, was nur der Kanton entscheiden kann (amber): wo er einen Datenstandard festlegen muss, dann die Entscheide je Kategorie in der Reihenfolge der Prioritätsstufen, mit den betroffenen Dienststellen und Formularen, und die Schutzstufen nach ISV.',
    'Die offenen Punkte je Formular, einmal für alle Seiten berechnet — dieselbe Liste wie im Handlungsbedarf, in den Briefings der Dienststellen und in der CSV. Die Aufteilung «kein eCH-Standard / Standard im Entwurf» stammt aus der Datenstandard-Auswertung derselben Datenpunkte, die Vergleichszahlen aus den Kennzahlen der Startseite.',
    'Ein offener Entscheid ist eine Lücke, kein Versäumnis: die Databank setzt dort bewusst keinen Standardwert. «Zu entscheiden» nennt, was festzulegen ist; die aufklappbare Liste, wo es gilt. Ein Punkt ist je nach Kategorie ein Datenpunkt, ein Datenfeld, ein Formular oder ein Formularpaar.')
    +(emptySub?`<div class="nores">Zur Kategorie «${esc(todoCat(focus)[1])}» gibt es zurzeit keine offenen Entscheide — gezeigt werden alle.</div>`
      :badSub?`<div class="nores">Kategorie «${esc(TODO_BY[focus]?todoCat(focus)[1]:String(focus))}» gibt es unter den Entscheiden des Kantons nicht — gezeigt werden alle.</div>`:'')
    +`<div class="regstats"><span class="rstat"><i class="sw t-dec"></i>${esc(tonLabel('dec'))} <b>${nf(nDec)}</b>${uTxt?` <span class="small muted">— davon ${uTxt}</span>`:''}</span>
      <span class="rstat">Kategorien <b>${nf(Object.keys(A).length)}</b></span>
      ${nSf?`<span class="rstat">dazu Schutzstufe (ISV) für <b>${nf(nSf)}</b> ${plw(nSf,'Datenfeld','Datenfelder')}</span>`:''}</div>
    <section class="hsec core"><h4>Datenstandard: wo der Kanton festlegen muss</h4>
      <p class="hsub">Wo eCH nichts vorgibt oder die Praxis auseinandergeht, kann keine Dienststelle allein entscheiden — erst eine kantonale Festlegung macht die Angabe überall gleich.</p>
      ${catSections('dec','Zu entscheiden',focus,{stufen:[1],extra,head})||'<div class="nores">Keine offenen Entscheide zum Datenstandard.</div>'}</section>
    <h4 class="hscope">Weitere Entscheide des Kantons — nach Priorität</h4>
    ${catSections('dec','Zu entscheiden',focus,{stufen:STUFEN.map(x=>x.n).filter(n=>n!==1)})||'<div class="nores">Keine weiteren offenen Entscheide.</div>'}
    ${isv?`<div class="stufehd">Für alle Datenfelder zugleich</div>${isv}`:''}
    ${GEST&&(GEST.entscheide||[]).length?`<div class="stufehd">Ausserhalb dieser Zählung</div>
      <div class="dsline"><i class="sw t-dec"></i><span>Gestaltung der Formulare: ${pl(GEST.kennzahlen.dec,'Merkmal','Merkmale')} ohne klare Praxis oder Regel — ${GEST.entscheide.map(e=>esc(e.label)).join(', ')}. Eine Vorgabe liegt der Databank nicht vor; ob und welche gilt, legt der Kanton fest. Ein eigener Teil des Dashboards, in den Zahlen dieser Seite nicht enthalten. ${goLink('gestaltung','kanton','Zu diesen Merkmalen ›','inl')}</span></div>`:''}`;
  wireGo(m); focusCat(m, badSub?null:focus);
}
// ---------- Recherche der Databank: the databank's own homework (grey) ----------
function viewRecherche(){
  const m=document.getElementById('main');
  const A=aggByCat('open');
  const focus=(state.sub&&state.sub!=='felder')?state.sub:null;
  const badSub=focus&&!A[focus];
  // a grey category without open points belongs here all the same — it just has none now
  const emptySub=badSub&&TODO_BY[focus]&&catTon(focus)==='open';
  if(badSub) state.sub='felder';
  const n=Object.values(A).reduce((a,x)=>a+x.n,0);
  const nF=new Set(), nD=new Set();
  Object.values(A).forEach(a=>Object.entries(a.byDst).forEach(([dn,b])=>{nD.add(dn); b.rows.forEach(r=>nF.add(r.f.id));}));
  const perS=STUFEN.map(s=>{const k=Object.keys(A).filter(c=>catStufe(c)===s.n).reduce((x,c)=>x+A[c].n,0);
    return k?`<span class="rstat">${esc(stufeLabel(s.n))} <b>${nf(k)}</b></span>`:'';}).join('');
  m.innerHTML=pageHead('Recherche der Databank',
    `Hausaufgaben der Databank — kein Befund über die Verwaltung: ${pl(n,'Punkt','Punkte')}, die die Databank selbst noch nachschlagen, belegen oder zuordnen muss.`,
    'Alle grauen Punkte nach Kategorie, in der Reihenfolge der Prioritätsstufen, mit ihrer Anzahl und — aufklappbar — den Dienststellen und Formularen, bei denen sie anfallen.',
    'Die offenen Punkte je Formular, einmal für alle Seiten berechnet — dieselbe Liste wie in den Briefings der Dienststellen und in der CSV des Handlungsbedarfs.',
    'Grau heisst: die Databank hat noch nicht nachgeschaut oder noch nicht belegt. Das sagt nichts darüber, ob die Dienststelle richtig arbeitet — erst die Recherche zeigt, ob dahinter etwas zu ändern oder zu entscheiden ist.')
    +(emptySub?`<div class="nores">Zur Kategorie «${esc(todoCat(focus)[1])}» gibt es zurzeit keine offenen Punkte — gezeigt werden alle.</div>`
      :badSub?`<div class="nores">Kategorie «${esc(TODO_BY[focus]?todoCat(focus)[1]:String(focus))}» gehört nicht zur Recherche der Databank — gezeigt werden alle.</div>`:'')
    +`<div class="regstats"><span class="rstat"><i class="sw t-open"></i>${esc(tonLabel('open'))} <b>${nf(n)}</b></span>
      <span class="rstat">Formulare <b>${nf(nF.size)}</b></span><span class="rstat">Dienststellen <b>${nf(nD.size)}</b></span>${perS}</div>
    ${catSections('open','Zu tun',focus)||'<div class="nores">Die Databank hat keine offenen Recherche-Punkte.</div>'}`;
  wireGo(m); focusCat(m, badSub?null:focus);
}
// nested (on «Für Dienststellen»): no own title, and the sidebar's filter text does not apply
function deptOverview(opt){
  const o=opt||{};
  const f=o.nested?'':state.filter.toLowerCase();
  let h=`${o.nested?'':'<h3 class="view">Übersicht nach Departement</h3>'}
  <p class="hint">Dokumentationsstand der Databank, gerechnet auf der kuratierten Datenfeld-Schicht, in derselben Farbsprache wie
  die Startseite — die Farbe sagt, wer als Nächstes handelt: grün Norm belegt oder für die Aufgabe nötig; rot ohne Grundlage
  (die Dienststelle streicht das Feld oder holt die Zustimmung ein); amber Aufgabenbedarf offen (Kanton);
  grau noch zu ermitteln, dazu ⛨-Felder, die als aufgabennotwendig gelten, deren Grundlage nach KDSG Art. 5 Abs. 1 aber noch
  nicht benannt ist (Databank). Grau heisst: noch nicht ermittelt — eine Hausaufgabe der Databank. Zeile anklicken öffnet die Service-Seite.</p>`;
  deptKeys().forEach(d=>{
    const offices=deptTree[d]; let body='',dsvc=0; const D={need:0,have:0,ok:0,act:0,dec:0,open:0};
    Object.keys(offices).sort().forEach(o=>offices[o].forEach(s=>{
      if(f && !(s.name+' '+o+' '+d).toLowerCase().includes(f)) return;
      const g=grounding(s.id); Object.keys(D).forEach(k=>{D[k]+=g[k];}); dsvc++;
      body+=`<tr data-sid="${s.id}" style="cursor:pointer"><td>${svcLink(s.id,esc(s.name))}<div class="small muted nw">${esc(o)}</div></td>
        <td class="small muted wd hy">${esc(o)}</td><td class="small">${g.need}</td>
        <td>${g.need?`<span class="stdcell">${basisBar(g,'Datenfelder nach Rechtsgrundlage')}<span class="small muted">${g.have}/${g.need} mit Grundlage</span></span>`:'<span class="small muted">keine Datenfelder</span>'}</td></tr>`;
    }));
    if(!body) return;
    h+=`<div class="card"><div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap">
      <b style="font-size:var(--fs-m)">${esc(d)}</b> <span class="small muted">${pl(dsvc,'Service','Services')}</span>
      ${basisBar(D,'Datenfelder des Departements nach Rechtsgrundlage',220)}<span class="small muted">${nf(D.have)}/${nf(D.need)} ${plw(D.need,'Datenfeld','Datenfelder')} mit Grundlage</span>${tonNums(D)}</div>
      <div class="tscroll"><table class="ft fit"><thead><tr><th>Service</th><th class="wd">Dienststelle</th><th>Datenfelder</th><th title="grün Norm belegt oder für die Aufgabe nötig · rot ohne Grundlage · amber Aufgabenbedarf offen · grau noch zu ermitteln">Rechtsgrundlage</th></tr></thead><tbody>${body}</tbody></table></div></div>`;
  });
  return h;
}
// the stricter rules a sensitive category triggers, as tooltip text
const _sensRules={};
(DATA.datenhandhabung||[]).filter(r=>r.scope==='besonders_schuetzenswert').forEach(r=>{
  (_sensRules[r.sensitive_category||'*']=_sensRules[r.sensitive_category||'*']||[]).push(r);});
function sensTip(cat){
  const rs=[...(_sensRules[cat]||[]),...(_sensRules['*']||[])];
  return rs.slice(0,4).map(r=>`• ${r.summary} (${artLabel(r.article_no)} ${r.short_title||''})`).join('\n')
    +(rs.length>4?`\n… und ${rs.length-4} weitere (Tab «Datenhandhabung»)`:'');
}
// why a chip with an eCH element is grey: the state «zuordnung_falsch» of the export
const ZF_TIP='Ein eCH-Element ist zugeordnet, aber die Bezeichnung meint eine andere Angabe — die Databank korrigiert diese Zuordnung; bis dahin gilt der Datenpunkt nicht als geklärt';
function viewDataFields(forms,ohneKennung){
  let h='';
  forms.forEach(fm=>{
    const dfs=fm.data_fields||[]; if(!dfs.length) return;
    const DIX=divIndex(fm);
    h+=`<div class="card"><div class="dfhdr"><b>${esc(fm.title)}</b>${fm.kennung&&!ohneKennung?` <code class="kennc kennmini" title="Dauerhafte Kennung dieses Formulars">${esc(fm.kennung)}</code>`:''}
      <span class="muted small">— ${pl(dfs.length,'Datenfeld','Datenfelder')}${(()=>{
        // every count is the exported state of the atomic data point (forms[].standard.ech,
        // counted once in export_json: the Teilfelder where a Datenfeld has them) — the same
        // unit as the chips below and as every other standard figure, so the header cannot
        // contradict them: a composite whose Teilfeld the databank corrects counts as corrected
        // 'standardisiert' = a citable XML element; an element the databank has to correct
        // (zuordnung_falsch) is not «standardisiert» — it has its own count. «Element offen»
        // only where the standard HAS an element catalogue; a standard without one is a
        // final answer (standard_ohne_elemente), not a task
        const SE=(fm.standard||{}).ech||{}, pts=(fm.standard||{}).punkte||0, byS=k=>SE[k]||0;
        const n=byS('element'), zf=byS('zuordnung_falsch'), off=byS('element_offen'), so=byS('standard_ohne_elemente'), dr=byS('standard_entwurf'), alt=byS('standard_alt');
        const cnt=(k,num,txt,tip)=>{const t=tonOf('ech',k); return ` · <span class="nowrap" title="${esc(tip+'\n'+tonWords(t))}">${SW(t)}${num}</span>`;};
        return (n?` · <span class="nowrap">${SW(tonOf('ech','element'))}<b>${n}/${pts}</b> ${pts===dfs.length?'':'Datenpunkte '}eCH-standardisiert</span>`:'')
          +(zf?cnt('zuordnung_falsch',`${zf} eCH-Zuordnung wird korrigiert`,'',ZF_TIP):'')
          +(off?cnt('element_offen',`${off} Element offen`,'','Standard zugeordnet, konkretes XML-Element noch offen (der Standard führt einen Elementkatalog)'):'')
          +(so?cnt('standard_ohne_elemente',`${so} nur Standard-Ebene`,'',`${lab(DIV_DE,'standard_ohne_elemente')} — der Standard führt in der Databank keinen XML-Elementkatalog (FHIR-/Prozessstandard oder XSD noch nicht geprüft); die Zuordnung bleibt auf Standard-Ebene, ein Element ist hier nicht zu bestimmen`):'')
          +(dr?cnt('standard_entwurf',`${dr} Standard im Entwurf`,'','Der zugeordnete eCH-Standard ist noch in Arbeit (nicht genehmigt) — bis eCH ihn verabschiedet, legt der Kanton fest, wie die Angabe verlangt wird (eSH)'):'')
          +(alt?cnt('standard_alt',`${alt} Standard nicht mehr in Kraft`,'','Der zugeordnete eCH-Standard ist sistiert, aufgehoben oder abgelöst — die Databank ersetzt die Zuordnung durch den Nachfolger'):'');})()}</span>
      ${(()=>{const ck=fm.check; if(!ck||!ck.status) return '';
        // currency of the Formular, in its tone (ton_map.check): aktuell ok, every
        // «not the current version» red; label from DATA.labels.check. Past its Wiedervorlage
        // an «aktuell» is open again (grey) — the rule of formFacts and the dossier
        const faellig=ck.status==='aktuell'&&((fm.handlungsbedarf||[]).some(i=>i.cat==='pruefung_faellig')
          ||(fm.next_check_due&&fm.next_check_due<new Date().toISOString().slice(0,10)));
        if(faellig){const tf=tonOf('check','faellig');
          return `<span class="fcheck st-${tf}" title="${esc('Wiedervorlage der Online-Prüfung abgelaufen — ob die Kopie der Databank noch die aktuelle Fassung ist, ist unbekannt (Recherche der Databank «Online-Prüfung fällig»)\n'+tonWords(tf))}">${SW(tf)}geprüft ${esc(fmtDate(ck.d))} · Wiedervorlage fällig</span>`;}
        const t=tonOf('check',ck.status);
        const tip={aktuell:`online geprüft${ck.quelle?' ('+ck.quelle+')':''} — die Kopie der Databank ist die aktuelle Fassung`,
          veraltet:ck.note||'Online liegt eine neuere Fassung',
          veraltet_verdacht:(ck.note||'Verdacht auf eine neuere Fassung')+(ck.dvsh_neu?' — neu: '+ck.dvsh_neu:''),
          nicht_auffindbar:`${ck.note||''} (geprüft ${fmtDate(ck.d)}) — Formular wird online nicht mehr angeboten; evtl. ausser Gebrauch oder durch eServices ersetzt`,
          nicht_gefunden:`weder auf sh.ch, im DVSH noch per Websuche auffindbar (geprüft ${fmtDate(ck.d)})`}[ck.status]||'Ergebnis der Online-Prüfung';
        return `<span class="fcheck st-${t}" title="${esc(tip+'\n'+tonWords(t))}">${SW(t)}${esc(lab(CHECK_DE,ck.status))}${ck.status==='aktuell'&&ck.d?' · geprüft '+esc(fmtDate(ck.d)):''}</span>`;})()}
      ${fm.source_file?`<a class="srcbtn" href="${esc(fm.source_file)}" style="margin-left:auto">↗ Quelldatei</a>`:''}</div>`;
    dfs.forEach(d=>{
      const subs=(d.subfields||[]).map(s=>typeof s==='string'?s:(s&&s.name)||'').filter(Boolean);
      const vals=(d.allowed_values||[]);
      h+=`<div class="dfrow"><div class="dfmain">
        <div><span class="tp">${esc(lab(DFTYPE,d.data_type))}</span>
          <span class="dfname">${esc(d.name)}</span>
          ${d.required?'<span class="req">✱ Pflicht</span>':'<span class="muted small">optional</span>'}
          ${divChip(DIX[d.name+'|'])}${begChip(d.begriff)}
          ${d.ech?(()=>{const e=d.ech.element, nx=!e&&d.ech.n_elements>0, t=tonOf('ech',d.ech_state);
            const st=d.ech.status, draft=st&&st!=='Genehmigt';
            const tip=(d.ech_state==='zuordnung_falsch'?ZF_TIP+'\n':'')+(d.ech.standard_titel||'')+(e?` — Element ${e}`
              :(nx?` — Element noch nicht bestimmt (${pl(d.ech.n_elements,'Element','Elemente')} im Standard)`
                  :' — Standard ohne XSD: kein zitierbares XML-Element'))
              +(st?` · Status: ${st}${d.ech.reifegrad?', Reifegrad '+d.ech.reifegrad:''}`:' · Status nicht erhoben (kein Genehmigungsstatus dieses Standards in der Databank geladen)')
              +'\n'+tonWords(t);
            return `<a class="echb st-${t}" href="${esc(d.ech.url)}" target="_blank" rel="noreferrer" title="${esc(tip)}">${SW(t)}${esc(d.ech.standard)}${e?` · ${esc(e)}`:(nx?' · Element offen':' · nur Standard')}</a>`
              +(d.ech.datatype?(()=>{const cl=(DATA.ech_codelists||{})[d.ech.codelist_key||(d.ech.standard+'|'+d.ech.datatype)];
                  const ver=d.ech.xsd_version?` (XSD ${esc(d.ech.xsd_version)})`:'';
                  const codes=cl?`\nOffizielle Codeliste (${pl(cl.length,'Wert','Werte')}): `+cl.slice(0,12).map(c=>c.value+(c.doc?' = '+c.doc:'')).join(' · ')+(cl.length>12?' …':''):'';
                  return `<span class="edt${cl?' cl':''}" title="Datentyp gemäss dem offiziellen ${esc(d.ech.standard)}-XSD${ver} — in diesem Typ ist die Angabe zu speichern und auszutauschen${esc(codes)}">⟨${esc(d.ech.datatype)}⟩${cl?'<span style="font-size:var(--fs-xs);margin-left:2px">☰</span>':''}</span>`;})():'')
              +(d.register?`<span class="regc" title="Once-Only: diese Angabe (eCH-Element ${esc(e||'')}) führt das Einwohnerregister für Einwohnerinnen und Einwohner bereits (zitierte Quelle) — Einordnung der Databank: statt die Angabe neu zu erheben, liessen sich eigene Daten vorbefüllen und Daten Dritter abgleichen (Verhältnismässigkeit, KDSG Art. 4 Abs. 2); ob die Dienststelle das Register abfragen darf, richtet sich nach dem Recht des Registers (bei kantonalen Stellen KDSG Art. 8 Abs. 1). Gilt nur für Daten natürlicher Personen; Betriebs-, Behörden- und Objektadressen tragen die Marke nicht.${d.vorbefuellbar?' Vorbefüllbar: eine Angabe der einreichenden Person.':d.zeitbezug?' Nicht vorbefüllbar: die Bezeichnung fragt nach einem Wert einer anderen Zeit (früher, neu, Änderung, seit …); der Registereintrag hält den heutigen Wert.':' Nicht vorbefüllbar: die Angabe gehört nicht sicher der einreichenden Person (andere Partei, Partei offen oder mehrdeutig).'}">↺ ${d.vorbefuellbar?'vorbefüllbar · ':''}Einwohnerregister</span>`:'')
              // a standard that is not in force: still in the works — the canton decides
              // meanwhile (amber); sistiert, aufgehoben or abgelöst — the databank replaces the
              // mapping by the successor (grey, the tone of the worklists' «nicht in Kraft» point)
              +(draft?(()=>{const t2=echDraftTon(st), gone=st==='Aufgehoben'||st==='Abgelöst';
                  return `<span class="echdraft st-${t2}" title="${esc((gone?`Dieser eCH-Standard ist ${String(st).toUpperCase()} — nicht mehr in Kraft; die Databank ersetzt die Zuordnung durch den Nachfolger`
                    : st==='Sistiert'?'Dieser eCH-Standard ist SISTIERT (ausgesetzt) — nicht in Kraft; die Databank ersetzt die Zuordnung durch den Nachfolger'
                    : st==='In Arbeit'?'Dieser eCH-Standard ist noch nicht genehmigt (in Arbeit) — bis eCH ihn verabschiedet, legt der Kanton fest, wie die Angabe verlangt wird'
                    : `Status «${st}» dieses eCH-Standards ist keinem Ton zugeordnet — gilt als nicht geklärt`)+'\n'+tonWords(t2))}">${SW(t2)}${esc(st)}</span>`;})():'');})()
            :(d.ech_status==='kein_standard'?(()=>{const t=tonOf('ech','kein_standard');
                return `<span class="echn st-${t}" title="${esc('kein eCH-Standard deckt dieses Feld ab — damit es trotzdem einheitlich verlangt und ausgetauscht werden kann, legt der Kanton es fest (eSH-Entwurf)\n'+tonWords(t))}">${SW(t)}kein eCH-Standard</span>`
                  +(d.esh?`<span class="eshb" title="Vorschlag für den kantonalen Standard eSH (E-Schaffhausen) — ENTWURF, nicht offiziell: ${esc(d.esh.titel)}">${esc(d.esh.code)} · ${esc(d.esh.element||'')}<span class="ent">Entwurf</span></span>`:'');})()
              // a Datenpunkt nobody has checked against eCH yet: a gap, said — never silence
              :(!subs.length?(()=>{const t=tonOf('ech','ungeprueft');
                return `<span class="echn st-${t}" title="${esc('Dieses Datenfeld ist noch nicht gegen den eCH-Katalog geprüft\n'+tonWords(t))}">${SW(t)}eCH noch nicht geprüft</span>`;})():''))}
          ${d.sensitive?(()=>{const n=(_sensRules[d.sensitive]||[]).length+(_sensRules['*']||[]).length;
            return `<span class="badge b-sens senslink" title="besonders schützenswert nach KDSG Art. 2 Abs. 1 lit. d (für Bundesorgane: DSG Art. 5 lit. c) — es gelten zusätzlich:\n${esc(sensTip(d.sensitive))}" data-tipgo="Leitfaden: besonders schützenswerte Daten ›">⛨ ${esc(lab(SENS,d.sensitive))}${n?` · ${pl(n,'Zusatzregel','Zusatzregeln')}`:''}</span>`;})():''}
          ${d.format?`<span class="muted small">· ${esc(d.format)}</span>`:''}
          ${d.schutzstufe?stBadge(tonOf('schutzstufe','festgelegt'),'Schutzstufe '+esc(d.schutzstufe),'Schutzstufe nach ISV festgelegt'):''}</div>
        ${d.definition?`<div class="dfdef">${esc(d.definition)}</div>`:''}
        ${subs.length?`<div class="dfchips"><span class="muted small">Teilfelder:</span> ${(d.subfields||[]).slice(0,24).map(s=>{
            const nmv=typeof s==='string'?s:(s&&s.name)||''; if(!nmv) return '';
            const e=s&&s.ech, t=tonOf('ech',s&&typeof s==='object'?s.ech_state:'ungeprueft'), zfs=s&&s.ech_state==='zuordnung_falsch'?ZF_TIP+'\n':'';
            // a subfield on a standard not in force: its own small chip, in the tone of a field's
            const dr=e&&e.status&&e.status!=='Genehmigt'?(()=>{const t2=echDraftTon(e.status);
              return `<span class="echdraft st-${t2}" title="${esc((ECH_STD_STATE[e.status]==='standard_alt'?'Standard nicht mehr in Kraft ('+e.status+') — die Databank ersetzt die Zuordnung durch den Nachfolger'
                :e.status==='In Arbeit'?'Standard noch nicht in Kraft (in Arbeit) — bis eCH ihn verabschiedet, legt der Kanton fest'
                :'Standard-Status «'+e.status+'» ohne Ton — nicht geklärt')+'\n'+tonWords(t2))}">${SW(t2)}${esc(e.status)}</span>`;})():'';
            const dvs=DIX[d.name+'|'+nmv];
            if(e&&e.element) return `<span class="chip sub${dvs?' dvs':''}"${dvs?` title="${esc(dvs.map(i=>lab(DIV_DE,i.art)+': hier '+i.hier+' — '+i.andere+' '+tonWords(tonOf('div',i.art))).join('\n'))}"`:''}><b>${esc(nmv)}</b>${dvs?`<span class="divc mini st-${divTon(dvs)}">⇄</span>`:''}<a class="sfe st-${t}" href="${esc(e.url)}" target="_blank" rel="noreferrer" title="${esc(zfs+(e.standard_titel||'')+' — '+e.standard+' '+e.element+(e.datatype?' · wird geführt als '+e.datatype:'')+(e.status?' · Status: '+e.status:' · Status nicht erhoben')+'\n'+tonWords(t))}">${esc(e.standard)}·${esc(e.element)}</a>${dr}${begChip(s.begriff,true)}${s.register?`<span class="regc" title="Once-Only: dieses Teilfeld führt das Einwohnerregister bereits (${esc(e.standard)} ${esc(e.element)}, zitierte Quelle)${s.vorbefuellbar?' — vorbefüllbar, eine Angabe der einreichenden Person':s.zeitbezug?' — nicht vorbefüllbar: die Bezeichnung fragt nach einem Wert einer anderen Zeit (früher, neu, Änderung, seit …); der Registereintrag hält den heutigen Wert':' — nicht vorbefüllbar: die Angabe gehört nicht sicher der einreichenden Person (andere Partei, Partei offen oder mehrdeutig)'}. Einordnung der Databank: ob die Stelle das Register abfragen darf, richtet sich nach dem Recht des Registers (bei kantonalen Stellen KDSG Art. 8 Abs. 1)">↺</span>`:''}</span>`;
            if(e){const nx=e.n_elements>0;
              return `<span class="chip sub"><b>${esc(nmv)}</b><a class="sfe st-${t}" href="${esc(e.url)}" target="_blank" rel="noreferrer" title="${esc((e.standard_titel||'')+(nx?' — Element noch nicht bestimmt':' — Standard ohne XSD: kein zitierbares Element')+'\n'+tonWords(t))}">${esc(e.standard)}${nx?'·Element offen':'·nur Standard'}</a>${dr}</span>`;}
            if(s&&s.ech_status==='kein_standard') return `<span class="chip sub"><b>${esc(nmv)}</b><span class="sfe st-${t}" title="${esc('kein eCH-Standard — der Kanton legt fest, wie die Angabe verlangt wird (eSH-Entwurf)\n'+tonWords(t))}">kein Std.</span>${s.esh?`<span class="sfe esh" title="eSH-Entwurf des Kantons, nicht offiziell: ${esc(s.esh.titel)}">${esc(s.esh.code)}·${esc(s.esh.element||'')}<span class="ent">Entwurf</span></span>`:''}</span>`;
            return `<span class="chip sub"><b>${esc(nmv)}</b></span>`;}).join('')}</div>`
          :(vals.length?`<div class="dfchips"><span class="muted small">Werte:</span> ${vals.slice(0,24).map(v=>`<span class="chip">${esc(String(v))}</span>`).join('')}</div>`:'')}
        ${(d.source_widgets||[]).length?`<div class="dfprov">↩ erfasst durch: ${d.source_widgets.slice(0,8).map(w=>esc(String(w))).join(' · ')}</div>`:''}
      </div><div class="dfrg">${(d.legal_basis&&d.legal_basis.length)?d.legal_basis.map(b=>{
          const imp=W_LAW[b.law_id]?`<div class="lawimp">${standChip(b.law_id)} ${wirkLink(b.law_id,b.article_id)}</div>`:'';
          return b.quote||imp?`<details class="qd"><summary>${citeStr(b)}</summary>${b.quote?`<blockquote class="quote">«${esc(b.quote)}»</blockquote>`:''}${imp}</details>`
                 :citeStr(b);}).join('<br>'):basisBadge(d)}</div></div>`;
    });
    h+=`</div>`;
  });
  return h;
}
// a Formular whose data-field layer is not modelled yet (Handlungsbedarf «keine
// Datenfelder modelliert»): a gap of the databank, said as one, with the way to
// the source file. The retired 2026-06 auto-draft inventory is never shown instead.
function noFieldsCard(fm){
  return `<div class="card"><div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    ${stBadge(tonOf('basis','zu_ermitteln'),'Datenfeld-Schicht noch nicht erfasst','Die Datenfelder dieses Formulars sind noch nicht modelliert — welche Angaben es verlangt und auf welcher Grundlage, ist noch zu ermitteln; heisst NICHT, dass keine Grundlage existiert')}
    <span class="muted small">zu ermitteln</span>
    ${fm.source_file?`<a class="srcbtn" href="${esc(fm.source_file)}" style="margin-left:auto">↗ Quelldatei</a>`:''}</div></div>`;
}
// SERVICE-level head: publication state, Verfahrens-Ergebnis, contact —
// nothing form-specific lives here any more
function serviceHead(s, forms){
  const dv=s.dvsh, sp=s.shep;
  const fm0=forms[0]||{};
  // the Dienststelle of the service, with its contact as the DVSH model holds it
  const dn=s.dienststelle||fm0.dienststelle||'', du=dstByName[dn];
  // a service can have several Formulare and only one of them carries the
  // modelled Entscheid; taking forms[0] blindly hid the proven Rechtsmittel
  const outForm=forms.find(f=>f.outcome&&(f.outcome.rechtsmittel||f.outcome.entscheid_art))||fm0;
  const out=outForm.outcome;
  const outMulti=forms.filter(f=>f.outcome&&f.outcome.entscheid_art&&f.outcome.entscheid_art!=='unbekannt').length>1;
  return `<div class="card hubhead">
    <div class="hubrow" style="margin-bottom:6px">
      ${dv?`<span class="badge b-dvsh" title="DVSH — amtliches Dienstleistungsmodell des Kantons (nur lesend übernommen) · Status im DVSH-Modellierungswerkzeug${dv.version?' · Version '+esc(String(dv.version)):''}${s.dvsh_n>1?' · dieser Service ist mit '+s.dvsh_n+' DVSH-Modellierungen verknüpft; gezeigt wird eine davon':''}">DVSH: ${esc(dv.status?lab(DVSH_STATUS,dv.status):'modelliert')}${dv.online?' · online':''}${s.dvsh_n>1?' · eine von '+s.dvsh_n+' DVSH-Modellierungen':''}</span>`:'<span class="badge b-nodv">◇ nicht im DVSH modelliert</span>'}
      ${sp?`<a class="badge b-dvsh" style="text-decoration:none" href="https://shep.meetfrida.agency/de/services/${esc(sp.slug)}" target="_blank" rel="noreferrer" title="SHEP — publiziertes Service-Portal des Kantons (Bürgersicht) · auf SHEP publiziert · Stand ${esc(sp.updated||'')}">SHEP publiziert ↗</a>`:(dv?'<span class="hubmeta">noch nicht auf SHEP publiziert</span>':'')}
      ${dv&&dv.vollzugsbehoerde?`<span class="hubmeta">Vollzug: ${esc(dv.vollzugsbehoerde)}</span>`:''}
      ${dv?(()=>{const g=dv.gebuehren==null?'':String(dv.gebuehren).trim(), has=/[0-9A-Za-zÄÖÜäöü]/.test(g);
        return `<span class="hubmeta"${has?(g.length>60?` title="${esc(g)}"`:''):` title="${(dv.dvsh_text_glitch||[]).length?'Gebühren-Feld im DVSH-Modell leer — der Modelltext enthält an anderer Stelle Markup-Reste, eine Gebührenangabe kann dort stecken (siehe Fristen)':'keine Gebührenangabe im DVSH-Modell'}"`}>Gebühren: ${has?esc(g.slice(0,60))+(g.length>60?' …':''):'—'}${dvCut(dv,'gebuehren')}</span>`;})():''}
      <a class="srcbtn" style="margin-left:auto" href="dossiers/${esc(s.dossier_slug)}.html" target="_blank" rel="noreferrer" title="Ein- bis zweiseitiges Datenschutz-Dossier dieses Services zum Drucken oder als PDF — Daten, Grundlagen, Empfänger, Fristen, Rechtsmittel, offene Punkte (dossiers/-Ordner, aus derselben Databank erzeugt)">⎙ Dossier (Druck/PDF)</a>
    </div>
    ${du?`<div class="hubout hubk">${kontaktHtml(du.kontakt,{wer:dstLink(dn,'dlink lt')})}</div>`:''}
    ${out&&out.entscheid_art?`<div class="hubout">Ergebnis des Verfahrens:
      <b>${esc(lab(OUTCOME_DE,out.entscheid_art))}</b>${out.ergebnis_dokument?` — «${esc(out.ergebnis_dokument)}»`:''}
      <span class="muted small">(${out.entscheid_art==='unbekannt'?'DVSH-Ablauftext geprüft, kein belegbares Ergebnis':'aus dem DVSH-Ablauftext abgeleitet'}${forms.length>1?', Formular «'+esc(outForm.title)+'»':''})</span>
      ${outMulti?mkBadge('mehrere Entscheide im Service','Dieser Service hat mehrere Formulare mit je eigenem Entscheid — hier steht der des genannten Formulars; die übrigen stehen in ihrer Formular-Ansicht'):''}</div>`:''}
    ${out?rechtsmittelLine(out):''}
    ${(s.themen||[]).length?`<div class="svthemen"><span class="muted small">Themengruppe (eCH-0049):</span>${s.themen.map(x=>`<a class="lawchip thlink" href="#lebenslagen/all/g-${encodeURIComponent(x.id)}" data-g="${x.id}" title="${esc(lab(KAT_DE,x.katalog))} · ${esc(x.bereich)}">${esc(x.gruppe)}</a>`).join('')}</div>`:''}
  </div>`;
}
// Rechtsmittel: what a person can do against the decision - sektoral (the cited
// law says it itself) or the VRG's general rule, always labelled which
function rechtsmittelLine(out){
  const r=out.rechtsmittel;
  if(!r){
    // nothing to appeal: the remedy question has its answer — the state of a confirmed
    // provision (ton_map.rechtsmittel.bestaetigt); no point is open, nobody acts
    if(out.entscheid_art==='kein_entscheid') return `<div class="hubout rm"><span class="rmlbl">Rechtsmittel:</span> ${stBadge(tonOf('rechtsmittel','bestaetigt'),'keines','Das Verfahren endet ohne anfechtbare Verfügung (Meldung) — es gibt nichts anzufechten; die Rechtsmittelfrage ist damit beantwortet')} <span class="muted small">das Verfahren endet ohne anfechtbare Verfügung (Meldung)</span></div>`;
    if(!out.rechtsmittel_status) return '';
    // the outcome itself could not be backed from the DVSH text: the remedy
    // question is not reached yet — said, never left as silence
    if(out.rechtsmittel_status==='entscheidart_offen') return `<div class="hubout rm"><span class="rmlbl">Rechtsmittel:</span>
      ${stBadge(tonOf('rechtsmittel','entscheidart_offen'),esc(lab(RM_STATUS,'entscheidart_offen')),'Was das Verfahren zurückgibt (Bewilligung, Verfügung, Eintrag …), liess sich aus dem DVSH-Ablauftext nicht belegen; bis das feststeht, stellt sich die Rechtsmittelfrage nicht — eine Lücke der Databank, kein Befund.')}</div>`;
    // say exactly WHY nothing is stated: assessed and undecidable, or not yet
    // assessed — and name the level of the cited law instead of assuming Bund
    const lv=(out.gesetzesebenen||[]).map(x=>lab(LAB.ebene||{},x));
    const lvTxt=lv.length?lv.join(' und '):'die zitierten Erlasse';
    const beurteilt=out.rechtsmittel_status==='beurteilt_offen';
    return `<div class="hubout rm"><span class="rmlbl">Rechtsmittel:</span>
      ${stBadge(tonOf('rechtsmittel',out.rechtsmittel_status),esc(lab(RM_STATUS,out.rechtsmittel_status)),beurteilt
        ?'Geprüft: keine der Rechtsmittelnormen der zitierten Gesetze deckt diesen Entscheid, und die allgemeine VRG-Regel wurde nicht unterstellt. Die Begründung steht im Prüfvermerk.'
        :'Für dieses Verfahren wurde noch keine Rechtsmittelnorm untersucht — eine Wissenslücke der Databank, kein Befund.')}
      <span class="muted small">Der Entscheid stützt sich auf ${esc(lvTxt)}${out.entscheid_art==='registereintrag'?'; Registerverfahren haben oft eine eigene Rechtsmittelordnung':''}.</span>
      ${out.rechtsmittel_verdikt?`<details class="qd" style="display:inline-block"><summary>Prüfvermerk</summary><blockquote class="quote">${esc(out.rechtsmittel_verdikt)}</blockquote></details>`:''}</div>`;
  }
  const nr=refNo(r.jurisdiction_level,r.sr_number,r.cantonal_ref);
  const law=(r.short_title||r.law_title||'')+(nr?' ('+nr+')':'');
  const frist=r.frist_tage?`innert <b>${r.frist_tage} Tagen</b>${r.frist_article_no?' ('+esc(artLabel(r.frist_article_no))+')':''}`:'<span class="muted">Frist im Gesetz nicht beziffert</span>';
  const tip=esc((r.quote||'')+(r.frist_quote?'\n\n'+r.frist_quote:'')+(r.hinweis?'\n\n'+r.hinweis:''));
  const what=r.rechtsmittel_art==='verweis'?`Rechtsmittel nach ${esc(r.instanz||'dem verwiesenen Erlass')}`
    :`<b>${esc(lab(RM_DE,r.rechtsmittel_art))}</b>${r.instanz?' an '+esc(r.instanz):''} ${frist}`;
  // the VRG general rule appears in two states that must look different: a
  // panel has confirmed no Fachgesetz goes first (Prüfvermerk), or it is the
  // bare fallback nobody has checked yet (default_allgemein) — a default is not a verdict
  const dflt=out.rechtsmittel_status==='default_allgemein';
  // tone (ton_map.rechtsmittel): a confirmed provision green, the bare fallback grey
  const tOk=tonOf('rechtsmittel','bestaetigt');
  const src=r.scope==='allgemein'
    ?(dflt
      ?stBadge(tonOf('rechtsmittel','default_allgemein'),esc(lab(RM_STATUS,'default_allgemein')),'VRG Art. 1: die allgemeinen Verfahrensregeln gelten nur, soweit nicht abweichende Vorschriften in andern Gesetzen, Dekreten oder Verordnungen bestehen. Ob für dieses Formular ein Fachgesetz eine eigene Rechtsmittelnorm vorsieht, hat noch kein Prüfvermerk geklärt — die allgemeine Regel steht hier als Rückfall, nicht als Befund.')
      :stBadge(tOk,'allgemeine Regel des VRG — Prüfvermerk bestätigt','VRG Art. 1: die allgemeinen Verfahrensregeln gelten nur, soweit nicht abweichende Vorschriften in andern Gesetzen, Dekreten oder Verordnungen bestehen. Ein Prüfvermerk hat bestätigt, dass für dieses Formular kein Fachgesetz eine eigene Rechtsmittelnorm vorsieht.'))
    :stBadge(tOk,'sektoral: '+esc(r.short_title||r.law_title||''),'Rechtsmittelnorm aus dem Fachgesetz, das die Datenfelder dieses Formulars zitieren'+(r.gilt_fuer?' — gilt für: '+r.gilt_fuer:''));
  const cands=(out.rechtsmittel_kandidaten||[]).filter(k=>!(r.scope==='sektoral'&&k.id===out.rechtsmittel_regel_id));
  const candList=cands.length?`<details class="qd rmcand"><summary>${cands.length} weitere Rechtsmittelnorm${cands.length===1?'':'en'} in den zitierten Gesetzen${r.scope==='allgemein'?' — zu prüfen, ob eine davon vorgeht':''}</summary>
      ${cands.map(k=>`<div class="small rmc"><b>${esc(lab(RM_DE,k.rechtsmittel_art))}</b>${k.instanz?' an '+esc(k.instanz):''}${k.frist_tage?' · '+k.frist_tage+' Tage':''} — ${esc(artLabel(k.article_no))} ${esc(k.short_title||k.law_title||'')}${k.gilt_fuer?' · gilt für: '+esc(k.gilt_fuer):''}${k.hinweis?' <span class="muted">('+esc(k.hinweis)+')</span>':''}<blockquote class="quote">«${esc(k.quote||'')}»</blockquote></div>`).join('')}</details>`:'';
  return `<div class="hubout rm"><span class="rmlbl">Rechtsmittel:</span> ${what}
    <details class="qd" style="display:inline-block;margin-left:6px"><summary title="${tip}">${esc(artLabel(r.article_no))} ${esc(law)} · Zitat</summary><blockquote class="quote">«${esc(r.quote||'')}»${r.frist_quote?`<br>«${esc(r.frist_quote)}»`:''}</blockquote></details>
    ${src}${out.rechtsmittel_verdikt?stBadge(tOk,'Zuordnung geprüft',out.rechtsmittel_verdikt):''}</div>${candList}`;
}
// FORM-level facts strip: channel, signature, Ampel, Bürgerlast, currency
function formFacts(fm){
  const bl=fm.blockers||[];
  // the check date is a FACT and stands as text; the age is computed when the
  // page is opened (not frozen at build time); an overdue Wiedervorlage and a
  // never-checked form are said, not hidden in a tooltip
  let checked='';
  const nowMs=Date.now(), today=new Date(nowMs).toISOString().slice(0,10);
  if(fm.check&&fm.check.d){
    const days=Math.round((nowMs-Date.parse(fm.check.d))/864e5);
    const over=fm.next_check_due&&fm.next_check_due<today;
    checked=`<span class="hubmeta" title="Aktualität der Online-Fassung geprüft${fm.check.quelle?' ('+esc(fm.check.quelle)+')':''}${fm.next_check_due?' · Wiedervorlage '+esc(fmtDate(fm.next_check_due)):''}">online geprüft ${esc(fmtDate(fm.check.d))}${isFinite(days)?` (${days<=0?'heute':days===1?'gestern':'vor '+pl(days,'Tag','Tagen')})`:''}</span>`
      +(over?stBadge(tonOf('check','faellig'),'Wiedervorlage überfällig seit '+esc(fmtDate(fm.next_check_due)),'Die Wiedervorlage der Online-Prüfung ist abgelaufen — ob die Kopie der Databank noch die aktuelle Fassung ist, ist unbekannt (Recherche der Databank «Online-Prüfung fällig»)'):'');
  } else checked=stBadge(tonOf('check','nie'),'online noch nie geprüft','Für dieses Formular gibt es noch keine Online-Prüfung — ob die Kopie der Databank die aktuelle Fassung ist, ist unbekannt');
  // the data standard leads the row (the owner's order): divergences and naming first; each
  // chip jumps to the block «Standard-Divergenzen» of this Formular
  const divHref=`#fields/${encodeURIComponent(fm.service_id)}/form-${encodeURIComponent(fm.id)}~div`;
  const dsfaInd=dsfaIndOf(fm), dsfaIt=(fm.handlungsbedarf||[]).find(i=>i.cat==='dsfa');
  return `<div class="hubrow">
      ${(()=>{const sd=fm.standard_divergenzen; if(!sd) return '';
        // red: the Formular demands a datum differently; amber: the practice is split and
        // the canton decides; green: every standardised datum is demanded like elsewhere
        const nU=(sd.angleichen||[]).filter(i=>i.art==='pflicht_uneinheitlich').length;
        const chip=(t,txt,tip)=>`<a class="hubdiv st-${t}" href="${divHref}" data-fid="${fm.id}" title="${esc(tip+' — zum Abschnitt «Standard-Divergenzen» springen\n'+tonWords(t))}">${SW(t)}${txt}</a>`;
        return (sd.n_angleichen?chip(tonOf('div','pflicht'),`⇄ ${sd.n_angleichen} Standard-Divergenz${sd.n_angleichen===1?'':'en'}`,'Dieselbe Angabe wird hier anders verlangt als auf den übrigen Formularen'):'')
          +(nU?chip(tonOf('div','pflicht_uneinheitlich'),`⇄ ${nU} ${esc(todoCat('divergenz_offen')[1])}`,'Dieselbe Angabe ist über die Formulare hinweg mal Pflicht, mal optional — der Kanton legt fest'):'')
          +(!sd.n_angleichen&&!nU?chip('ok','⇄ keine Standard-Divergenz','Jede standardisierte Angabe wird gleich verlangt wie anderswo'):'');})()}
      ${(()=>{const bz=(fm.standard_divergenzen||{}).bezeichnungen||[]; const n=bz.filter(i=>i.klasse==='variante'||i.pruefart==='aufteilen').length;
        const t=tonOf('begriff','variante');
        return n?`<a class="hubdiv st-${t}" href="${divHref}" data-fid="${fm.id}" title="${esc('Datenpunkte, die eine Angabe anders benennen als der einheitliche Begriff oder mehrere Daten bündeln — zum Abschnitt «Standard-Divergenzen» springen\n'+tonWords(t))}">${SW(t)}✎ ${n} Bezeichnung${n===1?'':'en'}</a>`:'';})()}
      ${dsfaInd?stBadge(tonOf('dsfa',fm.dsfa_status?'entschieden':'indiziert'),fm.dsfa_status?esc(fm.dsfa_status):esc(todoCat('dsfa')[1]),
        (fm.dsfa_status?'DSFA-Entscheid getroffen':todoCat('dsfa')[4])+(dsfaIt&&dsfaIt.detail?' — '+dsfaIt.detail:'')):''}
      ${(fm.data_fields||[]).length?mkBadge(bl.length?'Digitalisierung: '+pl(bl.length,'Hürde','Hürden'):'Digitalisierung: keine Hürden',
        'Digitalisierungs-Hürden: '+(bl.length?bl.map(b=>String(b).replace(/(\d)%/g,'$1 %')).join(' · '):'keine')+' — ein Befund zum Formular, keine Farbe; Einzelheiten unter «Details zu diesem Formular»'):''}
      ${fm.dvsh_match&&/konsolidiert|zuordnung/.test(fm.dvsh_match)?`<span class="hubmeta" title="${esc(fm.dvsh_match)}">↳ diesem DVSH-Service zugeordnet</span>`:''}
      <span class="hubchan">${esc(fm.submission_channel?lab(CHAN_DE,fm.submission_channel):(CHAN_DE.unbekannt||'Kanal unbekannt'))}</span>
      ${fm.signature_requirement==='handschriftlich'?`<span class="hubsig" title="${esc(fm.signature_evidence||'')}">✍ Unterschrift nötig</span>`:''}
      ${fm.signature_requirement==='sig_widget'?`<span class="hubsig">✓ digitale Signatur möglich</span>`:''}
      ${fm.has_flow?`<a class="hubmeta" href="flows.html" target="_blank" rel="noopener" title="Prototyp: geführter Flow zu diesem Formular — flows.html öffnet mit eigener Formularsuche">geführter Flow (Prototyp) ↗</a>`:''}
      ${checked}
    </div>
    ${fm.burden?`<div class="hubburden">Bürgerlast: <b>${fm.burden.inputs}</b> ${plw(fm.burden.inputs,'Pflichtangabe','Pflichtangaben')}
      ${fm.burden.attachments?` · <b>${fm.burden.attachments}</b> ${plw(fm.burden.attachments,'Beilage','Beilagen')}`:''} · ~<b>${fm.burden.minutes}</b> Min.
      ${fm.burden.prefillable?` · <b>${fm.burden.prefillable}</b> aus dem Einwohnerregister vorbefüllbar`:''}
      <span class="muted small" title="Zeitmodell: 0.4 Min. je Pflichtangabe, 5 Min. je Beilage — Beilagen = jeder Eintrag der Beilagenliste (Formular und DVSH) plus Anhang-Felder ohne Eintrag in dieser Liste; Obligatorium nicht gewichtet">ⓘ</span></div>`:''}`;
}
function blockerPanel(forms){
  const fm=forms[0]||{}; const bl=fm.blockers||[];
  if(!(fm.data_fields||[]).length) return '';
  if(!bl.length) return `<div class="card"><div class="dvsub">Digitalisierung</div>
    <div class="hstd">Keine Hürden erkannt — dieses Formular ist ein Kandidat für die durchgängig digitale Abwicklung.</div></div>`;
  const detail={'Unterschrift':fm.signature_evidence?`Beleg: ${fm.signature_evidence}`:'',
    'Quelle nicht befüllbar':fm.parse_error?`PDF nicht maschinell lesbar (${fm.parse_error})`:'flaches PDF ohne AcroForm-Felder',
    'kein Online-Kanal':'kein Online-Formular im DVSH-Abgabekanal',
    'eCH-Abdeckung < 50%':`nur ${fm.exchange_pct} % der atomaren Datenpunkte standardisiert`,
    };
  return `<div class="card"><div class="dvsub">Digitalisierungs-Hürden (${bl.length})</div>
    ${bl.map(b=>`<div class="hstd">✕ <b>${blockerLabel(b)}</b><span class="muted small"> — ${esc(detail[b]||'')}</span></div>`).join('')}</div>`;
}
function beilagenPanel(forms){
  const bs=forms.flatMap(fm=>fm.beilagen||[]);
  if(!bs.length) return '';
  const fetch_=bs.filter(b=>b.fetchable).length;
  return `<div class="card"><div class="dvsub">Beilagen (${bs.length})${fetch_?` — <b>${fetch_}</b> davon könnte der Kanton selbst beim Register beschaffen`:''}</div>
    ${bs.map(b=>`<div class="beirow">
      <span class="beiob ${b.obligatorium||'unbekannt'}">${esc(lab(OBLIG_DE,b.obligatorium||'unbekannt'))}</span>
      <span>${esc(b.bezeichnung)}${b.bedingung?` <span class="muted small">(${esc(b.bedingung)})</span>`:''}</span>
      <span class="beih ${b.fetchable?'f':''}" title="${b.fetchable?'staatlich geführt — Once-Only-Kandidat: Abruf statt Papierkopie':''}">${esc(lab(HALTER_DE,b.halter))}${b.fetchable?' ↺':''}</span>
      ${b.source==='dvsh'?'<span class="muted small" title="nur im DVSH-Modell verlangt, nicht im Formular selbst — Abgleich-Fund">nur DVSH</span>':''}
    </div>`).join('')}</div>`;
}
function similarPanel(forms){
  const sim=forms.flatMap(fm=>fm.similar||[]);
  if(!sim.length) return '';
  return `<div class="card"><div class="dvsub">Duplikat-Radar — sehr ähnliche Formulare (Feldmengen-Überlappung ≥ 50&nbsp;%)</div>
    ${sim.slice(0,6).map(x=>{
      const svc=DATA.forms.find(f=>f.id===x.form_id);
      const t=tonOf('dup',x.verdict?'entschieden':'offen');
      return `<div class="hstd">≈ <a class="simlink" data-sid="${svc?svc.service_id:''}">${esc(x.titel)}</a>
      <span class="muted small">Jaccard ${x.jaccard}</span> ${stBadge(t,x.verdict?esc(x.verdict):'unbeurteilt',x.verdict?'Duplikat-Verdacht beurteilt':'Ob die beiden Formulare zusammengelegt werden sollen, ist noch nicht entschieden')}</div>`;}).join('')}</div>`;
}
// ---------- the Service-Dossier ----------
// One narrative per page: SERVICE (identity, legal basis, Verfahren)
//   -> each FORMULAR -> the DATA it demands (Angaben + Beilagen + Unterschrift)
//   -> per datum its LEGAL BASIS, and the HANDLING rules glued to the table.
// Everything that is not this narrative folds into a Details drawer.
function lawChip(t,n,u,j){
  // the level is a Kennzeichen; where it cannot be evidenced it says so (dashed), still neutral
  const badge=j?jur(j):mkBadge('Ebene offen','Ebene nicht belegbar: der DVSH-Eintrag ist freier Text ohne SR/SHR-Nummer, ohne Quelle und ohne selbsterklärenden Titel — «Verordnung über …» gibt es auf Bundes- und auf Kantonsebene','mk-open');
  // no URL in the DVSH entry -> not a link; a href="#" that opens a blank tab
  // promises a source that does not exist. A bare host («www.rechtsbuch.sh.ch»)
  // is completed to a URL; a non-URL value («<UNKNOWN>») is not a link either —
  // relative to this file it would open a 404
  if(u&&/^www\./i.test(String(u).trim())) u='https://'+String(u).trim();
  // a number alone («721.100») says nothing on a phone: its abbreviation («WWG») or title stands beside it
  const ab=n&&t&&n!==t?((/\(([^)]{2,24})\)/.exec(String(t))||[])[1]||t):'';
  const txt=`${badge} ${esc(n||t)}${ab?` <span class="lawabbr">${esc(ab)}</span>`:''}`;
  if(!u||u==='#'||!/^https?:\/\//i.test(u)) return `<span class="lawchip nolink" title="${esc(t)} — im DVSH ohne Quellenlink, nur als Freitext geführt">${txt}</span>`;
  return `<a class="lawchip" href="${esc(u)}" target="_blank" rel="noreferrer" title="${esc(t)}">${txt}</a>`;
}
// The DVSH's second list is free text ("Art. 3 GesG", a rechtsbuch link ...) and
// often holds CANTONAL law despite its name - the level is read from evidence
// (URL host, SR/SHR marker, a short title the databank knows), never assumed
const LAWJUR=(()=>{const m={};(DATA.laws||[]).forEach(l=>{
  const add=s=>{s=(s||'').trim(); if(s.length>=2&&s.length<=24&&!/;/.test(s)) m[s.toLowerCase()]=l.jurisdiction_level;};
  add(l.short_title); const ab=(l.title||'').match(/\(([^)]{2,24})\)/); if(ab) add(ab[1]);});return m;})();
// every candidate short title in a free-text reference: each parenthesised
// abbreviation plus the trailing token ("Art. 3 GesG" -> GesG)
const abbrsOf=label=>{const out=[...String(label||'').matchAll(/\(([^)]{2,24})\)/g)].map(m=>m[1]);
  const t=String(label||'').trim().split(/\s+/).pop(); if(t) out.push(t); return out;};
// evidence only, in order: cantonal source, federal source, a title that names
// its own level ("Bundesgesetz …", "Kantonale Verordnung …", "Interkantonale
// Vereinbarung …"), a short title the databank already knows. Never a guess —
// "Verordnung über …" alone stays open, it exists on both levels
function jurOfRef(l){
  const url=l.url||'', label=l.label||l.titel||'';
  if(/rechtsbuch\.sh\.ch/.test(url)||/\bSHR\b/.test(label)||/^kantonale?s?\b/i.test(label)) return 'cantonal';
  if(/(^|\.)admin\.ch/.test(url)||/\bSR\s?\d/.test(label)
     ||/^(bundesgesetz|bundesverfassung|bundesbeschluss|bundesratsbeschluss)\b/i.test(label)) return 'federal';
  if(/^(interkantonale?s?|konkordat)\b/i.test(label)) return 'interkantonal';
  for(const a of abbrsOf(label)){const j=LAWJUR[a.toLowerCase()]; if(j) return j;}
  return null;
}
function svcLaws(dv){
  if(!dv) return [];
  const out=[];
  (dv.recht_kantonal||[]).forEach(l=>{const n=l.ssr||l.ssr_nummer;
    out.push(lawChip(l.titel||'',n,`https://rechtsbuch.sh.ch/app/de/texts_of_law/${n}`,'cantonal'));});
  // the second list mixes titled laws with bare article references ("Art. 3
  // GesG"); an article inherits the level of the titled entry in the SAME list
  // that carries the same abbreviation — that entry's URL is the evidence
  const refs=dv.recht_bund||[], local={};
  refs.forEach(l=>{const j=jurOfRef(l); if(!j) return;
    abbrsOf(l.label||l.titel||'').forEach(a=>{local[a.toLowerCase()]=j;});});
  refs.forEach(l=>{const lb=l.label||l.titel||'';
    const inh=abbrsOf(lb).map(a=>local[a.toLowerCase()]).find(Boolean)||null;
    out.push(lawChip(lb,l.sr,l.url||'#',jurOfRef(l)||inh));});
  return out;
}
// a modeller text the export had to cut at a markup glitch (service.dvsh.dvsh_text_glitch)
const dvCut=(dv,k)=>((dv&&dv.dvsh_text_glitch)||[]).includes(k)?' <span class="muted small">(im DVSH-Text folgen hier Markup-Reste und Angaben eines anderen Feldes — nicht übernommen, Fehler im DVSH-Modell)</span>':'';
function verfahrenSection(s){
  const dv=s.dvsh||{}, sp=s.shep||{};
  // DVSH is the correct version; SHEP fills only what DVSH leaves empty
  // a modeller column can arrive as text instead of a list (double-encoded in
  // the harvest); a bare .length check passes for a string and the array call
  // after it would blank the whole page, so coerce first
  const asArr=v=>Array.isArray(v)?v:(typeof v==='string'&&v.trim()?[v]:[]);
  const pick=(a,b)=>{const x=asArr(a); return x.length?x:asArr(b);};
  const vor=pick(dv.voraussetzungen,sp.voraussetzungen).filter(x=>typeof x==='string');
  const unt=pick(dv.unterlagen,sp.unterlagen).map(u=>typeof u==='string'?{title:u}:u);
  const abl=pick(dv.ablauf,sp.ablauf).map(a=>typeof a==='string'?{title:a}:a);
  if(!vor.length&&!unt.length&&!abl.length&&!dv.kurzbeschreibung) return '';
  return `<details class="card verf" open><summary><b>Das Verfahren</b>
      <span class="muted small">— amtliche Modellierung (DVSH${dv.version?' v'+esc(String(dv.version)):''}${s.dvsh_n>1?' · eine von '+s.dvsh_n+' DVSH-Modellierungen dieses Services':''})</span></summary>
    ${dv.beschreibung?`<div class="dvdesc">${esc(dv.beschreibung)}</div>`:''}
    <div class="dvgrid">
      ${vor.length?`<div><div class="dvsub">Voraussetzungen</div>${vor.map(v=>`<div class="dvl">• ${esc(v)}</div>`).join('')}</div>`:''}
      ${abl.length?`<div><div class="dvsub">Ablauf</div>${abl.map((a,i)=>`<div class="dvl"><b>${a.sort||a.nr||i+1}.</b> ${esc(a.title||a.titel||'')}${(a.description||a.text)?` <span class="muted small">— ${esc(a.description||a.text)}</span>`:''}</div>`).join('')}</div>`:''}
    </div>
    ${unt.length?`<div class="dvsub" style="margin-top:8px">Erforderliche Unterlagen laut Modell (${unt.length})</div>
      ${unt.slice(0,16).map(u=>`<div class="dvl" title="${esc(u.hint||u.detail||'')}">• ${esc(u.title||u.titel||u.name||'')}${(u.hint||u.detail)?' <span class="muted small">ⓘ</span>':''}</div>`).join('')}`:''}
    ${(dv.bearbeitungsdauer||dv.fristen||(dv.dvsh_text_glitch||[]).length)?`<div class="dvmeta">${[['Bearbeitungsdauer',dv.bearbeitungsdauer,'bearbeitungsdauer'],['Fristen',dv.fristen,'fristen']]
        .filter(x=>(x[1]&&String(x[1]).trim()&&String(x[1]).trim()!=='leer')||dvCut(dv,x[2]))
        .map(x=>`<div class="dvm"><span class="dvk">${x[0]}</span> ${x[1]&&String(x[1]).trim()?esc(String(x[1])):'—'}${dvCut(dv,x[2])}</div>`).join('')}</div>`:''}
  </details>`;
}
// the handling strip: how THIS form's data must be treated, glued to its table
function handlingStrip(s,fm){
  const terms=fm.retention||[], dec=fm.retention_decisions||[], emp=fm.disclosures||[];
  const cats=[...new Set((fm.data_fields||[]).filter(d=>d.sensitive).map(d=>d.sensitive))];
  const nb=(fm.data_fields||[]).filter(d=>d.basis_state==='ohne').length;
  let frist;
  if(terms.length) frist=retLine(terms[0]);
  else if(dec.length) frist=`Kantonaler Entscheid: ${esc(String(dec[0].duration_value||''))} ${esc(dec[0].duration_unit||'')}`;
  else frist=`<span class="small">${aufbewahrungStd()}</span>`;
  const seen=new Set();
  const empt=emp.filter(e=>!seen.has(e.empfaenger)&&seen.add(e.empfaenger));
  return `<div class="hstrip">
    <span class="hsl" style="flex-basis:100%;margin:0">So sind die Daten dieses Formulars zu handhaben</span>
    <span class="hs"><span class="hsl">Aufbewahrung</span>${frist}</span>
    <span class="hs"><span class="hsl">Weitergabe</span>${empt.length
      ? empt.slice(0,4).map(e=>`<span class="empchip" title="${esc(artLabel(e.article_no)+' '+(e.short_title||''))}">${esc(e.empfaenger)}${e.mode==='systematisch'?' ↻':''}</span>`).join('')+(empt.length>4?` +${empt.length-4}`:'')
      : `nur nach den allgemeinen Regeln ${guideChip(["174.100","Art. 8","bekanntgabe"])}`}</span>
    ${cats.length?`<span class="hs"><span class="hsl">⛨ zusätzlich</span><span class="badge b-sens senslink" title="besonders schützenswerte Daten dieses Formulars — für sie gelten zusätzliche Regeln (KDSG Art. 5, Leitfaden «besonders schützenswerte Daten»)" data-tipgo="Leitfaden: besonders schützenswerte Daten ›">${cats.map(x=>esc(lab(HSENS,x))).join(', ')}</span></span>`:''}
    ${nb?`<span class="hs"><span class="hsl">ohne Grundlage</span>${stBadge(tonOf('basis','ohne'),pl(nb,'Feld','Felder')+' — nur freiwillig','Weder eine Norm noch die Aufgabe verlangt diese Felder — nur freiwillig erhebbar')}</span>`:''}
  </div>`;
}
// one bounded section per Formular: facts, handling, the data table, drawer.
// `single` renders the old full per-Formular view (drawer open, no border)
// ---------- Standard-Divergenzen: what keeps THIS form out of one standard ----
// labels per art come from DATA.labels.div, the tone per art from DATA.labels.ton_map.div
// (DATA.labels.div_cls carries the same tone as a st-* class): aligning red, a missing
// cantonal decision amber, the databank's own mapping work grey, a final answer green
// several divergences on one unit: red as soon as the Dienststelle can align one of them
const divTon=list=>{const ts=(list||[]).map(i=>tonOf('div',i.art));
  return ts.includes('act')?'act':ts.includes('dec')?'dec':ts.includes('open')||!ts.length?'open':'ok';};
// one key per diverging unit, so the field row can carry the same marker
function divKey(i){return (i.feld||'')+'|'+(i.teilfeld||'');}
function divIndex(fm){
  const ix={}; ((fm.standard_divergenzen||{}).angleichen||[]).forEach(i=>{
    (ix[divKey(i)]=ix[divKey(i)]||[]).push(i);}); return ix;
}
function divChip(list){
  if(!list||!list.length) return '';
  const t=divTon(list);
  const tip=list.map(i=>`${lab(DIV_DE,i.art)} ${tonWords(tonOf('div',i.art))}: hier ${i.hier} — ${i.andere}\n→ ${i.aktion}`).join('\n\n');
  return `<span class="divc st-${t}" title="${esc(tip)}">${SW(t)}⇄ ${list.length>1?list.length+' Divergenzen':esc(lab(DIV_DE,list[0].art))}</span>`;
}
function begChip(b,mini){
  if(!b) return '';
  // the tone of a naming verdict (ton_map.begriff): rename or split red (the Dienststelle
  // changes the Formular), a wrong eCH mapping grey (the databank corrects it)
  // a proposal under reservation carries a second chip: the canton decides the term
  // (ton_map.begriff.vorbehalt, amber) — as on the Begriffe page
  if(b.klasse==='variante'){const t=tonOf('begriff','variante'), tv=tonOf('begriff','vorbehalt');
    const vb=b.vorbehalt?`<span class="begc st-${tv}" title="${esc('Vorschlag unter Vorbehalt — über den einheitlichen Begriff «'+b.vorschlag+'» entscheidet der Kanton (Tab «Begriffe»)\n'+tonWords(tv))}">${mini?'?':SW(tv)+'Vorbehalt'}</span>`:'';
    return `<span class="begc st-${t}" title="${esc(`Gleiche Angabe, einheitlicher Begriff: «${b.vorschlag}»${b.grund?' — '+b.grund:''} (Tab «Begriffe»)\n`+tonWords(t))}">${mini?'✎':SW(t)+'Begriff → «'+esc(b.vorschlag)+'»'}</span>`+vb;}
  if(b.klasse==='pruefen'){const t=tonOf('begriff',b.pruefart||'pruefen');
    return `<span class="begc st-${t}" title="${esc((b.grund||'Die Bezeichnung verspricht mehr oder anderes als das Standard-Element')+'\n'+tonWords(t))}">${mini?'✎?':SW(t)+(b.pruefart==='aufteilen'?'Feld aufteilen':b.pruefart==='zuordnung'?'Zuordnung prüfen':'Bezeichnung prüfen')}</span>`;}
  return '';
}
function divergencePanel(fm){
  const sd=fm.standard_divergenzen; if(!sd) return '';
  const ang=sd.angleichen||[], feh=sd.fehlend||[];
  if(!ang.length&&!feh.length&&!(sd.bezeichnungen||[]).length) return `<div class="card" id="stddiv-${fm.id}"><div class="dvsub">Standard-Divergenzen</div>
    <div class="hstd">${SW('ok')}Keine: jede Angabe dieses Formulars trägt ein eCH-Element und wird gleich verlangt wie auf den übrigen Formularen.</div></div>`;
  const grp={}; ang.forEach(i=>{(grp[i.art]=grp[i.art]||[]).push(i);});
  // the headline number must match the Handlungsbedarf: «anzugleichen» never
  // counts the pflicht_uneinheitlich items, which ask the canton, not this form
  const nAng=sd.n_angleichen!=null?sd.n_angleichen:ang.filter(i=>i.art!=='pflicht_uneinheitlich').length;
  const nUnk=sd.n_pflicht_ungeklaert!=null?sd.n_pflicht_ungeklaert:ang.filter(i=>i.art==='pflicht_uneinheitlich').length;
  const hd=[nAng?`${SW(tonOf('div','pflicht'))}${nAng} anzugleichen`:'',nUnk?`${SW(tonOf('div','pflicht_uneinheitlich'))}${nUnk} ${esc(todoCat('divergenz_offen')[1])}`:'',feh.length?`${pl(sd.n_fehlend,'Punkt','Punkte')} ohne Standard`:''].filter(Boolean);
  let h=`<div class="card" id="stddiv-${fm.id}"><div class="dvsub">Standard-Divergenzen${hd.length?` (${hd.join(' · ')})`:''}</div>
    <div class="hstd muted small">Was dieses Formular davon trennt, Teil EINES kohärenten Datenstandards zu sein. Oben: dieselbe Angabe wird hier anders verlangt als anderswo — das ist anzugleichen oder zu begründen. Unten: für die Angabe gibt es (noch) keinen zitierbaren Standard — das ist eine Lücke, keine Abweichung.</div>`;
  ['pflicht','format','codeliste','pflicht_uneinheitlich'].forEach(art=>{
    const L=grp[art]; if(!L) return;
    const t=tonOf('div',art);
    h+=`<table class="ft dvt"><thead><tr><th><span title="${esc(tonWords(t))}">${SW(t)}</span>${esc(lab(DIV_DE,art))} (${L.length})</th><th>auf diesem Formular</th><th>auf den übrigen Formularen</th><th>Rechtsgrundlage hier</th></tr></thead><tbody>`;
    L.forEach(i=>{h+=`<tr><td><b>${esc(i.feld)}</b>${i.teilfeld?` › ${esc(i.teilfeld)}`:''}
        <div class="mono small muted">${esc(i.standard)} ${esc(i.element)}</div></td>
      <td class="small">${art==='codeliste'
        ?`<span class="dvval st-${t}">${esc(i.hier)}</span>`
        :`<span class="badge st-${t}">${SW(t)}${esc(i.hier)}</span>`}</td>
      <td class="small">${esc(i.andere)}</td>
      <td class="small muted">${esc(i.basis||'')}</td></tr>
      <tr class="dvact"><td colspan="4" class="small">→ ${esc(i.aktion)}</td></tr>`;});
    h+=`</tbody></table>`;
  });
  const bz=sd.bezeichnungen||[];
  const bzBlock=(L,title,hint,col,t)=>L.length?`<div class="dvsub" style="margin-top:10px"><span title="${esc(tonWords(t))}">${SW(t)}</span>${title} (${L.length})</div>
      <div class="small muted">${hint}</div>
      <table class="ft dvt"><thead><tr><th>Datenfeld</th><th>heisst hier</th><th>${col}</th><th>Hinweis</th></tr></thead><tbody>
      ${L.map(i=>`<tr><td><b>${esc(i.feld)}</b>${i.teilfeld?` › ${esc(i.teilfeld)}`:''}<div class="mono small muted">${esc(i.standard)} ${esc(i.element)}</div></td>
        <td class="small">«${esc(i.hier)}»</td>
        <td class="small">${i.klasse==='variante'?`<b>«${esc(i.vorschlag)}»</b>`:esc(i.pruefart==='aufteilen'?'in einzelne Felder':'Zuordnung korrigieren')}</td>
        <td class="small muted">${esc(i.grund||'')}</td></tr>`).join('')}</tbody></table>`:'';
  h+=bzBlock(bz.filter(i=>i.klasse==='variante'),'Umbenennen — gleiche Angabe, anderer Name','Das Feld meint dasselbe wie der einheitliche Begriff, heisst aber anders → im Formular umbenennen (Dienststelle).','einheitlich',tonOf('begriff','variante'));
  h+=bzBlock(bz.filter(i=>i.klasse==='pruefen'&&i.pruefart==='aufteilen'),'Feld bündelt mehrere Daten — aufteilen','Der Standard trennt, was dieses Feld zusammenfasst (z. B. Strasse und Hausnummer) → im Formular in einzelne Felder aufteilen (Dienststelle).','Handlung',tonOf('begriff','aufteilen'));
  h+=bzBlock(bz.filter(i=>i.klasse==='pruefen'&&i.pruefart!=='aufteilen'),'eCH-Zuordnung korrigieren — die Bezeichnung meint eine andere Angabe','Kein Fehler des Formulars: die Databank hat das Feld einem unpassenden eCH-Element zugeordnet → Zuordnung korrigieren (Databank).','Handlung',tonOf('begriff','zuordnung'));
  if(feh.length){
    h+=`<div class="dvsub" style="margin-top:10px">Ohne zitierbaren Standard (${pl(sd.n_fehlend,'Datenpunkt','Datenpunkte')})</div>
      <table class="ft dvt"><thead><tr><th>Art</th><th>Punkte</th><th>Felder</th></tr></thead><tbody>`;
    feh.forEach(i=>{
      // the export names the state (standard_divergenzen.fehlend[].art): no standard or one
      // still in the works — the canton decides; one no longer in force — the databank re-maps
      const t=tonOf('div',i.art), akt=i.aktion||'';
      h+=`<tr><td>${stBadge(t,esc(lab(DIV_DE,i.art)),akt)}
        ${i.standard?`<div class="mono small muted">${esc(i.standard)}${i.status?' · '+esc(i.status):(/^eCH-/.test(i.standard)?' · Status nicht erhoben':'')}</div>`:''}</td>
      <td>${i.n}</td><td class="small">${i.felder.map(esc).join(' · ')}${i.n>i.felder.length?' …':''}</td></tr>
      <tr class="dvact"><td colspan="3" class="small">→ ${esc(akt)}</td></tr>`;});
    h+=`</tbody></table>`;
  }
  return h+`</div>`;
}
function formSection(s,fm,single,sec){
  const hasDF=(fm.data_fields||[]).length;
  let h=`<div class="${single?'':'formsec'}" ${single?'':`id="fsec-${fm.id}"`}>
    <div class="card" style="padding:9px 16px 7px">
      ${single?'':`<div style="float:right"><button class="fmopen srcbtn" data-fid="${fm.id}" title="dieses Formular als eigene Seite öffnen">▣ Formular-Ansicht</button></div>`}
      ${formFacts(fm)}${hasDF?handlingStrip(s,fm):''}</div>`;
  h+= hasDF? viewDataFields([fm],single) : noFieldsCard(fm);
  h+= beilagenPanel([fm]);
  h+= divergencePanel(fm);
  h+= parteiPanel(fm,single&&sec==='part');
  h+= konzeptPanel(fm);
  h+= registerPanel(fm,single&&sec==='reg');
  h+= gestPanel(fm,single&&sec==='gest');
  const extras=blockerPanel([fm])+handlingPanel(s,[fm])+similarPanel([fm]);
  h+=`<details class="hgen" style="margin:0 0 4px" ${single?'open':''}><summary class="dvsub" style="cursor:pointer">Details zu diesem Formular — Digitalisierungs-Hürden, volles Datenhandhabungs-Profil, Duplikat-Radar</summary>${extras}</details>`;
  return h+`</div>`;
}
// a mistyped or stale tab in a shared link: an explicit notice under the
// address as typed — render() is the whitelist, no second list to keep in sync
function viewUnknown(){const m=document.getElementById('main');
  m.innerHTML=pageHead('Unbekannte Seite','Diese Seite gibt es in der Databank nicht («'+esc(String(state.tab))+'») — der Link ist veraltet oder vertippt.')
    +`<div class="nores">Unbekannte Seite — bitte in der Navigation einen Bereich wählen. ${goLink('home','','Zur Übersicht ›','inl')}</div>`;
  wireGo(m);}
function viewFields(){
  const m=document.getElementById('main');
  if(state.service==='all'){
    m.innerHTML=pageHead('Service-Seite',
      'In der Navigation einen Service wählen oder oben suchen: die Seite zeigt je Service seine Formulare, ihre Datenfelder und die Rechtsgrundlage jeder Angabe.',
      'Die Seite erzählt eine Sache: welcher Service, auf welcher Rechtsgrundlage — welche Formulare — welche Daten sie verlangen, mit Rechtsgrundlage und Handhabung je Angabe.',
      'Verfahren & Service-Recht: DVSH-Modell und SHEP-Portal (massgebliche Quellen, nur lesend übernommen). Daten-, Standard- und Regel-Schicht: eigene kuratierte Analyse, quellenbelegt.',
      'Unten der Dokumentationsstand aller Departemente.')+deptOverview();
    m.querySelectorAll('tr[data-sid]').forEach(tr=>tr.onclick=e=>{if(e.target.closest('a')) return; state.service=tr.dataset.sid;render();});
    wireGo(m); return; }
  const s=svcById[state.service];
  // a stale or mistyped shared link (#fields/99999): an empty state, never the
  // previous page under the wrong address
  if(!s){m.innerHTML=pageHead('Service-Seite','Dieser Service ist nicht in der Databank (ID '+esc(String(state.service))+') — der Link ist veraltet oder vertippt.')
    +`<div class="nores">Unbekannter Service — bitte in der Navigation einen Service wählen. ${goLink('fields','','Alle Services ›','inl')} · ${goLink('home','','Zur Übersicht ›','inl')}</div>`;
    wireGo(m); return;}
  const forms=formsByService[s.id]||[];
  const dv=s.dvsh, sp=s.shep;
  // the old per-Formular view, one form as its own page
  // an unknown Formular or segment in the URL falls back to the service page — and says so
  let fBad='';
  if(state.sub&&state.sub.startsWith('form-')){
    const [fidS,sec]=state.sub.slice(5).split('~'), fid=+fidS;
    const fm=forms.find(f=>f.id===fid);
    if(fm){
      // a section the page does not know falls back to the plain Formular-Ansicht
      if(sec&&!['div','gest','part','reg'].includes(sec)) state.sub='form-'+fid;
      m.innerHTML=`<h3 class="view" tabindex="-1">${esc(fm.title)}</h3>
        <p class="hint">Formular-Ansicht · gehört zum Service <a class="simlink" id="backsvc" href="#fields/${encodeURIComponent(s.id)}">${esc(s.name)}</a> · ${esc(s.dienststelle||'')}</p>
        ${fm.kennung?`<p class="hint kennline">${kennTag(fm.kennung,'Dauerhafte Kennung')}</p>`:''}
        ${formSection(s,fm,true,sec)}`;
      document.getElementById('backsvc').onclick=e=>{if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button) return; e.preventDefault(); state.sub='felder';render();};
      m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=()=>{
        state.service=a.dataset.sid;state.sub='felder';render();});
      m.querySelectorAll('.senslink').forEach(b=>b.onclick=goSensGuide);
      wireDivChips(m); wireGo(m);
      if(sec==='div') focusDiv(fid);
      if(sec==='gest') focusGest(fid);
      if(sec==='part') focusPanel('part-'+fid);
      if(sec==='reg') focusPanel('reg-'+fid);
      dmWire(m);
      return;
    }
    fBad=`Formular «${esc(fidS)}» gehört nicht zu diesem Service — gezeigt wird die Service-Seite.`; state.sub='felder';
  }
  if(state.sub!=='gesetze'&&state.sub!=='felder'){fBad=`Ansicht «${esc(String(state.sub))}» ist auf dieser Seite unbekannt — gezeigt wird die Service-Seite.`; state.sub='felder';}
  const laws=svcLaws(dv);
  let h=`<div class="bcrumb"><a id="bc-home">⌂ Übersicht</a><span>›</span>
    <a class="bc-flt" data-f="${esc(s.department||'')}">${esc(s.department||'—')}</a><span>›</span>
    <a class="bc-flt" data-f="${esc(s.dienststelle||'')}">${esc(s.dienststelle||'—')}</a></div>
  <h3 class="view" tabindex="-1">${esc(s.name)}</h3>
  <p class="hint" style="margin-bottom:8px">Service-Seite · ${dv
    ?'Verfahren und Rechtsgrundlage aus dem DVSH-Dienstleistungsmodell (amtlich, nur lesend übernommen)'+(sp?' und dem publizierten SHEP-Portal (Bürgersicht)':'')
    :'für diesen Service liegt keine DVSH-Modellierung in der Databank vor, Verfahren und Service-Recht sind darum nicht belegt'} — darunter die Formulare und ihre Daten mit Rechtsgrundlage, Standard und Handhabung: die eigene, quellenbelegte Schicht der Databank.</p>
  ${forms.length>1?`<div class="fjump"><span class="hsl">Formulare</span>${forms.map(fm=>
    `<button class="fjc" data-fid="${fm.id}">${esc(fm.title.length>44?fm.title.slice(0,42)+'…':fm.title)}</button>`).join('')}</div>`:''}
  ${serviceHead(s,forms)}`;
  if(dv&&dv.kurzbeschreibung) h+=`<div class="zweckline" style="margin:2px 2px 10px">${esc(dv.kurzbeschreibung)}</div>`;
  h+=laws.length?`<div class="svclaws"><span class="hsl">Rechtsgrundlage des Services (DVSH)</span>${laws.join('')}</div>`:'';
  if(!s.dvsh) h+=`<div class="card nodvbox"><span class="badge b-nodv">◇ ${s.in_dvsh?'DVSH-Modellierung nicht in der Databank':'Nicht im DVSH-Modell'}</span>
    <span class="muted small">${s.in_dvsh
      ?'Dieser Service ist mit dem DVSH verknüpft, aber die Modellierung liegt in dieser Databank nicht vor (beim letzten Abzug aus dem DVSH nicht mitgeliefert). Die Rechtsgrundlagen unten stammen aus der eigenen, quellenbelegten Analyse der Databank.'
      :'Dieser Service ist in der Databank erfasst, aber (noch) nicht in der amtlichen DVSH-Modellierung. Die Rechtsgrundlagen unten stammen aus der eigenen, quellenbelegten Analyse der Databank.'}</span></div>`;
  h+=`<div class="seg">
    <button data-sub="felder" class="${state.sub!=='gesetze'?'active':''}">▤ Verfahren, Formulare &amp; Daten</button>
    <button data-sub="gesetze" class="${state.sub==='gesetze'?'active':''}">⚖ Gesetze im Detail</button>
  </div>`;
  if(state.sub==='gesetze'){
    h+=`<div id="hub-tree"></div><div id="hub-info"></div>`;
    m.innerHTML=h;
    viewTree(document.getElementById('hub-tree'));
    viewInfo(document.getElementById('hub-info'));
  } else {
    h+=verfahrenSection(s);
    h+=`<h4 class="hscope">Formulare dieses Services (${forms.length})</h4>`;
    // the channel is read from the DVSH endpoint (eFormular, E-Mail, Telefon,
    // externer Link, vor Ort) — never a guessed «eService»
    if(!forms.length) h+=`<div class="card"><div class="hstd">Kein Formular in der Databank — ${dv
      ?(dv.endpoint_typ?`laut DVSH Kanal: <b>${esc(lab(ENDPOINT_DE,dv.endpoint_typ))}</b>`:'im DVSH ist kein Kanal (Endpoint) hinterlegt')
      :'keine DVSH-Modellierung in der Databank, der Kanal ist nicht belegt'}.</div></div>`;
    forms.forEach(fm=>{h+=formSection(s,fm);});
    m.innerHTML=h;
  }
  if(fBad) m.insertAdjacentHTML('afterbegin',`<div class="nores">${fBad}</div>`);
  m.querySelectorAll('.seg button[data-sub]').forEach(b=>b.onclick=()=>{state.sub=b.dataset.sub;render();});
  m.querySelectorAll('.fmopen[data-fid]').forEach(b=>b.onclick=()=>{state.sub='form-'+b.dataset.fid;render();});
  m.querySelectorAll('.thlink[data-g]').forEach(a=>a.onclick=e=>{if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button) return;
    e.preventDefault(); state.tab='lebenslagen';state.service='all';state.sub='g-'+a.dataset.g;render();});
  const bch=document.getElementById('bc-home');
  if(bch)bch.onclick=()=>{state.service='all';state.sub='felder';render();};
  m.querySelectorAll('.bc-flt').forEach(a=>a.onclick=()=>{
    state.service='all';state.sub='felder';state.filter=a.dataset.f;render();});
  m.querySelectorAll('.fjc[data-fid]').forEach(b=>b.onclick=()=>{
    const t=document.getElementById('fsec-'+b.dataset.fid);
    if(t)t.scrollIntoView({behavior:MOTION});});
  m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=()=>{
    state.service=a.dataset.sid;state.sub='felder';render();});
  // a ⛨ badge explains itself; its box leads to the Leitfaden section on sensitive data
  m.querySelectorAll('.senslink').forEach(b=>b.onclick=goSensGuide);
  wireDivChips(m); wireGo(m); dmWire(m);
}
// the ⇄ / ✎ chips of a Formular jump to its block «Standard-Divergenzen» on the same page
// (their href opens the Formular-Ansicht there, for a new tab or a copied link)
function focusDiv(fid){
  if(comingBack()) return;
  setTimeout(()=>{const t=document.getElementById('stddiv-'+fid); if(!t) return;
    t.scrollIntoView({behavior:MOTION}); focusIn(t); t.classList.add('flash'); setTimeout(()=>t.classList.remove('flash'),1600);},0);
}
function wireDivChips(root){
  root.querySelectorAll('a.hubdiv[data-fid]').forEach(a=>a.onclick=e=>{
    if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button) return;
    const t=document.getElementById('stddiv-'+a.dataset.fid); if(!t) return;
    e.preventDefault(); focusDiv(a.dataset.fid);});
}
// the Leitfaden, at its section on besonders schützenswerte Daten — a canonical address
// (#guide), not the Formular's sub carried along
function goSensGuide(){
  state.tab='guide'; state.service='all'; state.sub='felder'; render();
  const t=[...document.querySelectorAll('.gq')].find(x=>x.textContent.includes('schützenswerte'));
  if(t) t.scrollIntoView({behavior:MOTION});
}

// ---------- Datenhandhabung rendering helpers ----------
// display order of the aspects (their labels come from DATA.labels.aspect); an
// aspect the labels know but this list does not is appended, never dropped
const _ASP=['erhebung','bearbeitung','speicherung','sicherheit','aufbewahrung','bekanntgabe','betroffenenrechte','archivierung','loeschung'];
const ASPECT_ORDER=_ASP.concat(Object.keys(ASPECT).filter(a=>!_ASP.includes(a)));
function ruleCite(r){
  const sr=refNo(r.jurisdiction_level,r.sr_number,r.cantonal_ref);
  return `${jur(r.jurisdiction_level)} <span class="mono">${esc(artLabel(r.article_no))}</span> ${esc(r.short_title||r.law_title)}${sr?' · '+esc(sr):''}`;
}
function ruleItem(r){
  const q=r.quote?`<details class="qd"><summary>${ruleCite(r)}${r.quote_verified?'':' '+stBadge(tonOf('verif','unverifiziert'),'Zitat unverifiziert','Das Zitat ist noch nicht mechanisch gegen das Gesetzes-PDF geprüft')}</summary><blockquote class="quote">«${esc(r.quote)}»</blockquote></details>`:ruleCite(r);
  return `<div class="hrule"><span class="hasp">${esc(lab(ASPECT,r.aspect))}</span>
    <div class="hbody"><div>${esc(r.summary)}${r.sensitive_category?` <span class="badge b-sens">⛨ ${esc(lab(SENS,r.sensitive_category))}</span>`:''}</div>
    <div class="small">${q}</div></div></div>`;
}
function rulesByAspect(list){
  return ASPECT_ORDER.filter(a=>list.some(r=>r.aspect===a))
    .map(a=>list.filter(r=>r.aspect===a).map(ruleItem).join('')).join('');
}
function handlingPanel(s,forms){
  const H=DATA.datenhandhabung||[]; if(!H.length) return '';
  // what is SPECIFIC to this Formular: its laws, its sensitive fields, its gaps
  const lawIds=new Set(), cats=new Set(), catFields={};
  let nFields=0, nNoBasis=0;
  forms.forEach(fm=>(fm.data_fields||[]).forEach(d=>{
    nFields++; if(d.basis_state==='ohne') nNoBasis++;
    (d.legal_basis||[]).forEach(b=>{if(b.law_id!=null)lawIds.add(b.law_id);});
    if(d.sensitive){cats.add(d.sensitive);(catFields[d.sensitive]=catFields[d.sensitive]||[]).push(d.name);}
  }));
  if(!nFields) return '';
  const sekt=H.filter(r=>r.scope==='sektoral'&&lawIds.has(r.law_id));
  const sens=cats.size?H.filter(r=>r.scope==='besonders_schuetzenswert'&&(!r.sensitive_category||cats.has(r.sensitive_category))):[];
  const allg=H.filter(r=>r.scope==='allgemein');
  const KEEP={aufbewahrung:1,loeschung:1,archivierung:1};
  const frist=sekt.filter(r=>KEEP[r.aspect]);
  const geben=sekt.filter(r=>r.aspect==='bekanntgabe');
  const rest=sekt.filter(r=>!KEEP[r.aspect]&&r.aspect!=='bekanntgabe');
  const sektLaws=[...new Set(sekt.map(r=>r.short_title||r.law_title))];

  // profile strip: the one-glance answer to "what is different about THIS form?"
  let strip='';
  cats.forEach(c=>{strip+=`<span class="pfc sens">⛨ ${esc(lab(HSENS,c))} (${pl(catFields[c].length,'Feld','Felder')})</span>`;});
  if(sektLaws.length) strip+=`<span class="pfc law">Spezialnormen: ${esc(sektLaws.join(' · '))}</span>`;
  const hasTerm=forms.some(fm=>(fm.retention||[]).length||(fm.retention_decisions||[]).length);
  strip+=(hasTerm||frist.length)?`<span class="pfc frist">Aufbewahrung: Spezialfrist</span>`
                     :`<span class="pfc std">Aufbewahrung: Regelfrist (Registraturperiode)</span>`;
  if(nNoBasis){const t=tonOf('basis','ohne'); strip+=`<span class="pfc st-${t}" title="${esc('Weder eine Norm noch die Aufgabe verlangt diese Felder\n'+tonWords(t))}">${SW(t)}${pl(nNoBasis,'Feld','Felder')} ohne Grundlage</span>`;}

  const purpose=forms.map(fm=>fm.purpose).filter(Boolean)[0];
  const terms=forms.flatMap(fm=>fm.retention||[]);
  const decisions=forms.flatMap(fm=>fm.retention_decisions||[]);
  const empf=forms.flatMap(fm=>fm.disclosures||[]);
  let h=`<div class="card" id="dhprofil-${forms.map(f=>f.id).join('-')}"><div class="dfhdr"><b>Datenhandhabung — Profil dieses Formulars</b>
    <span class="muted small">— was für DIESE Daten speziell gilt; das für alle identische Grundprogramm ist unten eingeklappt</span></div>
    ${purpose?`<div class="zweckline">Zweck: ${esc(purpose)}</div>`:''}
    <div class="pfstrip">${strip}</div>`;

  // retention: the concrete, computable answer — term, decision, or standard regime
  h+=`<div class="hgrp"><div class="dvsub">Aufbewahrung &amp; Vernichtung</div>`;
  if(terms.length){
    h+=terms.map(t=>`<div class="hstd">${retLine(t)}</div>`).join('');
  } else if(frist.length) h+=rulesByAspect(frist);
  else h+=`<div class="hstd">Keine Spezialfrist für dieses Formular. ${aufbewahrungStd()}</div>`;
  decisions.forEach(d=>{h+=`<div class="hstd">Kantonaler Fristentscheid: <b>${esc(String(d.duration_value||''))} ${esc(d.duration_unit||'')}</b>
    ${esc(fmtTrigger(d.trigger_event))} — ${esc(d.basis||'')} <span class="muted small">(${esc(d.decided_by||'')}, ${esc(fmtDate(d.decided_at))})</span></div>`;});
  h+=`</div>`;

  // disclosure: named recipients (article-backed), then the sectoral rules
  h+=`<div class="hgrp"><div class="dvsub">Weitergabe</div>`;
  if(empf.length){
    const seen=new Set();
    h+=`<div class="hstd">Empfänger laut Gesetz: ${empf.filter(e=>!seen.has(e.empfaenger)&&seen.add(e.empfaenger))
      .map(e=>`<span class="empchip" title="${esc((e.mode==='systematisch'?'systematische Lieferung':'auf Anfrage/Amtshilfe')+' — '+artLabel(e.article_no)+' '+(e.short_title||''))}">${esc(e.empfaenger)}${e.mode==='systematisch'?' ↻':''}</span>`).join('')}
      <span class="muted small">↻ = systematische Lieferpflicht; alle mit Artikel-Beleg</span></div>`;
  }
  if(geben.length) h+=rulesByAspect(geben);
  else h+=`<div class="hstd">Keine Spezialnormen — Bekanntgabe nur nach den allgemeinen Regeln (gesetzliche Grundlage,
    Aufgabenbedarf des Empfängers, Zustimmung, oder selbst veröffentlichte Daten).
    ${guideChip(["174.100","Art. 8","bekanntgabe"])}${guideChip(["174.100","Art. 10","bekanntgabe"])}</div>`;
  h+=`</div>`;

  // sensitive fields, named per category, with the stricter rules they trigger
  if(cats.size){
    h+=`<div class="hgrp"><div class="dvsub">⛨ Besonders schützenswerte Felder dieses Formulars</div>`;
    [...cats].forEach(c=>{
      h+=`<div class="hcat"><span class="badge b-sens">⛨ ${esc(lab(HSENS,c))}</span>
        <span class="small">${catFields[c].slice(0,10).map(esc).join(' · ')}${catFields[c].length>10?' …':''}</span></div>`;
    });
    if(sens.length) h+=rulesByAspect(sens);
    h+=`</div>`;
  }
  if(rest.length) h+=`<div class="hgrp"><div class="dvsub">Weitere Spezialnormen dieses Formulars</div>${rulesByAspect(rest)}</div>`;
  if(nNoBasis) h+=`<div class="hstd over">${SW(tonOf('basis','ohne'))}${nNoBasis} ${nNoBasis===1?'Datenfeld ist':'Datenfelder sind'} ohne Grundlage —
    weder eine Norm noch die Aufgabe verlangt ${nNoBasis===1?'es; es darf':'sie; sie dürfen'} nur freiwillig erhoben werden.</div>`;
  // the addressee decides: the KDSG binds the cantonal organs, the DSG binds
  // Bundesorgane — presenting both as "applies to this form" would be wrong
  const allgK=allg.filter(r=>r.jurisdiction_level==='cantonal');
  const allgB=allg.filter(r=>r.jurisdiction_level!=='cantonal');
  if(allgK.length) h+=`<details class="hgen"><summary class="dvsub" style="cursor:pointer">Allgemeine Regeln des kantonalen Datenschutzrechts — gelten für dieses wie für jedes Formular (${allgK.length}) · erklärt im Tab «Leitfaden»</summary>${rulesByAspect(allgK)}</details>`;
  if(allgB.length) h+=`<details class="hgen"><summary class="dvsub" style="cursor:pointer">Bundesrecht zum Vergleich (${allgB.length}) — richtet sich an Bundesorgane, nicht an die kantonale Verwaltung</summary>
    <div class="hstd muted small">Das DSG und seine Verordnung binden Bundesorgane und Private; für die Organe des Kantons gilt das KDSG (KDSG Art. 3 Abs. 1 i.V.m. Art. 2 Abs. 1 lit. c). Diese Regeln stehen hier als Vergleichsmassstab — auch beim Vollzug von Bundesrecht gilt für diese Dienststelle das KDSG (KDSG Art. 3 Abs. 1), ergänzt durch die Datenschutzbestimmungen des jeweiligen Bundes-Fachgesetzes (oben unter den Spezialnormen); sie sind keine unmittelbare Pflicht dieser Dienststelle.</div>
    ${rulesByAspect(allgB)}</details>`;
  return h+`</div>`;
}
function viewRules(){
  const m=document.getElementById('main');
  const H=DATA.datenhandhabung||[];
  let h=pageHead('Datenhandhabung · Speicherung, Bearbeitung, Bekanntgabe',
    'Alle Regeln für das Speichern, Bearbeiten und Weitergeben von Personendaten — im Wortlaut, geordnet nach Geltungsbereich und Gesetz.',
    'Der vollständige Regelbestand: eine Zeile je (Artikel, Aspekt), gruppiert nach Geltungsbereich und Gesetz.',
    `8 Governance-Gesetze (KDSG/KDSV/ISV/ArchivV, DSG/DSV/BGA/EMBAG) vollständig gelesen plus die Datenhandhabungs-Artikel von ${new Set(H.filter(r=>r.scope==='sektoral').map(r=>r.law_id)).size} Fachgesetzen; jede Regel trägt ein wörtliches Zitat, das der Loader mechanisch gegen das amtliche Gesetzes-PDF geprüft hat.`,
    '«allgemein» gilt für alle Personendaten · «besonders schützenswert» zusätzlich für ⛨-Felder · «sektoral» nur für Formulare, deren Felder das jeweilige Gesetz zitieren («gilt für N Formulare» aufklappen). Adressat beachten: für die Organe des Kantons gilt das KDSG (KDSG Art. 3 Abs. 1 i.V.m. Art. 2 Abs. 1 lit. c); DSG, DSV, BGA und EMBAG binden Bundesorgane und stehen hier als Vergleichsmassstab — auch beim Vollzug von Bundesrecht gilt für die kantonalen Organe das KDSG (KDSG Art. 3 Abs. 1), hinzu treten die Datenschutzbestimmungen des jeweiligen Bundes-Fachgesetzes (Gruppe «sektoral»).');
  if(!H.length){m.innerHTML=h+'<div class="nores">Noch keine Regeln geladen (scripts/load_data_rules.py).</div>';return;}
  const grp=[['allgemein','Allgemeine Regeln — für alle Personendaten (KDSG für die kantonalen Organe; das Bundesrecht DSG/DSV/BGA/EMBAG richtet sich an Bundesorgane und steht als Vergleich)'],
             ['besonders_schuetzenswert','Besonders schützenswerte Personendaten'],
             ['sektoral','Sektorale Spezialnormen — je Fachgesetz']];
  // which forms cite which law — for the 'gilt für N Formulare' back-links
  const formsByLaw={};
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>(d.legal_basis||[]).forEach(b=>{
    if(b.law_id!=null)(formsByLaw[b.law_id]=formsByLaw[b.law_id]||new Set()).add(f);})));
  grp.forEach(([scope,label])=>{
    const list=H.filter(r=>r.scope===scope); if(!list.length) return;
    // one card per law inside the scope, so the source is always visible
    const byLaw={};
    list.forEach(r=>{(byLaw[r.law_id]=byLaw[r.law_id]||[]).push(r);});
    h+=`<h4 class="hscope">${esc(label)} <span class="muted small">· ${pl(list.length,'Regel','Regeln')}</span></h4>`;
    Object.values(byLaw).forEach(rs=>{
      const r0=rs[0];
      const fms=scope==='sektoral'?[...(formsByLaw[r0.law_id]||[])]:[];
      h+=`<div class="card" id="law-${r0.law_id}-${scope}"><div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
        <b>${esc(r0.short_title||r0.law_title)}</b>
        <span class="muted small">${esc(r0.law_title!==r0.short_title?r0.law_title:'')}</span>
        <span class="muted small" style="margin-left:auto">${jur(r0.jurisdiction_level)} ${esc(refNo(r0.jurisdiction_level,r0.sr_number,r0.cantonal_ref))} · ${pl(rs.length,'Regel','Regeln')}</span></div>
        ${W_LAW[r0.law_id]?`<div class="lawimp">${standChip(r0.law_id)} ${wirkLink(r0.law_id)}</div>`:''}
        ${rulesByAspect(rs)}
        ${fms.length?`<details class="lawforms"><summary>gilt für ${pl(fms.length,'Formular','Formulare')} →</summary>
          ${fms.slice(0,40).map(f=>`<div class="small">• <a class="simlink" data-sid="${f.service_id}">${esc(f.title)}</a></div>`).join('')}</details>`:''}</div>`;
    });
  });
  m.innerHTML=h;
  m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=()=>{
    state.service=a.dataset.sid;state.tab='fields';state.sub='felder';render();});
  wireGo(m);
}
// ---------- Leitfaden (plain-language guide over the verified rules) ----------
function guideChip(ref){
  // resolve (sr, article, aspect[, scope]) against the verified rule corpus;
  // build_dashboard.py already refused to build if a ref does not resolve
  const [sr,art,asp,scope]=ref;
  const r=(DATA.datenhandhabung||[]).find(x=>x.sr_number===sr&&x.article_no===art
    &&x.aspect===asp&&(!scope||x.scope===scope));
  if(!r) return '';
  const tip=(r.summary||'')+(r.quote?'\n«'+r.quote+'»':'');
  return `<span class="gchip" data-law="${r.law_id}" data-scope="${esc(r.scope)}" title="${esc(tip)}" data-tipgo="Zur Regel in der Datenhandhabung ›">${esc(r.short_title||r.law_title)} ${esc(artLabel(r.article_no))}</span>`;
}
// the ONE sentence for the default retention regime (no sectoral Frist), computed
// in export_json from the verified cantonal rules and rendered identically here,
// in the dossiers and in the LLM export — with a chip per cited provision
function aufbewahrungStd(){
  const t=(DATA.texte||{}).aufbewahrung_standard;
  if(!t||!t.text) return '<span class="muted">Standardregime nicht exportiert (data.texte.aufbewahrung_standard fehlt).</span>';
  return esc(t.text)+' '+(t.refs||[]).map(guideChip).join('');
}
function viewGuide(){
  const m=document.getElementById('main');
  let h=pageHead('Leitfaden · Was heisst das für den Umgang mit Daten?',
    `Dieselben Regeln in einfacher Sprache: ${nf(GUIDE.length)} Fragen vom Erheben bis zum Vernichten, jede Aussage mit der Regel, auf der sie beruht.`,
    `Die praktischen Antworten hinter den ${nf((DATA.datenhandhabung||[]).length)} Regeln des Tabs «Datenhandhabung», in einfacher Sprache — neun Fragen vom Erheben bis zum Vernichten.`,
    'Kuratierter Text; die Seite wird nur erzeugt, wenn jede zitierte Regel in der Databank steht. Ein Klick, ein Tipp oder Enter auf einen Chip zeigt das wörtliche, PDF-verifizierte Zitat; von dort führt ein Knopf zur Regel in der Datenhandhabung. Violette Kästen sind Einordnung, kein Gesetzeszitat.',
    'Massgeblich bleibt der Gesetzestext. Formular-spezifisches steht im Datenhandhabungs-Profil der jeweiligen Service-Seite.');
  GUIDE.forEach(sec=>{
    h+=`<div class="card gsec"><h4 class="gq">${esc(sec.frage)}</h4>
      <div class="gkurz"><span class="gklabel">Kurz gesagt</span>${esc(sec.kurz)}</div>`;
    (sec.punkte||[]).forEach(p=>{
      h+=`<div class="gpt"><div>${esc(p.text)}</div>
        <div class="gchips">${(p.refs||[]).map(guideChip).join('')}</div></div>`;
    });
    if(sec.praxis) h+=`<div class="gprax"><span class="gplabel">Einordnung — Interpretation der Databank, kein Gesetzeszitat</span>${esc(sec.praxis)}</div>`;
    h+=`</div>`;
  });
  m.innerHTML=h;
  // a chip jumps to the cited law's card in the full rule corpus
  m.querySelectorAll('.gchip').forEach(c=>c.onclick=()=>{
    state.tab='rules';state.service='all';state.sub='felder';render();
    const t=document.getElementById(`law-${c.dataset.law}-${c.dataset.scope}`);
    if(t){t.scrollIntoView({behavior:MOTION});t.classList.add('flash');setTimeout(()=>t.classList.remove('flash'),1600);}
  });
}
// ---------- tree (list + diagram) ----------
function needService(label){
  return `<h3 class="view" tabindex="-1">${label}</h3><div class="nores">Bitte in der Navigation einen einzelnen Service wählen `+
         `(bei ${nf(DATA.services.length)} Services ist die Gesamtansicht zu gross).</div>`;
}
// build the law -> article -> data-field structure for the current selection
function treeModel(){
  // Gesetz -> Artikel -> DATENFELDER via data_field_legal_basis (the retired
  // 2026-06 requirement layer is not exported, so it can never appear here)
  const sids = state.service==='all' ? DATA.services.map(s=>s.id) : [Number(state.service)];
  const laws={};
  sids.forEach(sid=>(formsByService[sid]||[]).forEach(fm=>(fm.data_fields||[]).forEach(d=>{
    (d.legal_basis||[]).forEach(lb=>{
      const lk=(lb.law_short||lb.law_title||'?');
      const L=laws[lk]||(laws[lk]={id:lk,lid:lb.law_id,title:lb.law_title,short:lb.law_short,jur:lb.jurisdiction,sr:lb.sr_number,cref:lb.cantonal_ref,arts:{}});
      const ak=lb.article_no||'?';
      const A=L.arts[ak]||(L.arts[ak]={id:ak,aid:lb.article_id,lid:lb.law_id,no:lb.article_no,heading:lb.article_heading,lc:lb.last_checked,reqs:{}});
      const st=(lb.last_checked==='verified')?'match':(String(lb.last_checked||'').startsWith('Gesetze')?'sourced':'proposed');
      A.reqs[d.name]={dp:d.name,status:st,type:d.data_type};
    });
  })));
  return Object.values(laws).map(L=>({...L,arts:Object.values(L.arts).map(A=>({...A,reqs:Object.values(A.reqs)}))}));
}
function viewTree(into){
  const m=into||document.getElementById('main');
  if(state.service==='all'){ m.innerHTML=needService('Gesetzes-Baum · Gesetz → Artikel → Datenfeld'); return; }
  const model=treeModel();
  let h=`<h3 class="view">Gesetzes-Baum · Gesetz → Artikel → Datenfeld</h3>
  <p class="hint">Beide Darstellungen sind ein- und ausklappbar. Die Ebene (Bund, Kanton, Gemeinde) steht als neutrales Kennzeichen; die Farbe gehört allein der Verifikationsstufe: grün geklärt (verifiziert oder aus dem Gesetzes-PDF), grau noch zu prüfen (Databank).</p>
  <div class="seg">
    <button data-t="list" class="${state.tree==='list'?'active':''}">▤ Liste</button>
    <button data-t="diagram" class="${state.tree==='diagram'?'active':''}">⌗ Diagramm</button>
  </div>`;
  if(!model.length){ m.innerHTML=h+'<div class="nores">Keine Gesetze für die Auswahl.</div>'; return; }
  h+= state.tree==='list' ? `<div class="card tree">${model.map(listLaw).join('')}</div>`
                          : `<div class="card dg">${model.map(dgLaw).join('')}</div>`;
  m.innerHTML=h;
  m.querySelectorAll('.seg button').forEach(b=>b.onclick=()=>{state.tree=b.dataset.t;render();});
  m.querySelectorAll('.ttog').forEach(t=>t.onclick=()=>t.closest('.tgrp').classList.toggle('collapsed'));
  m.querySelectorAll('.dgbox').forEach(b=>b.onclick=(e)=>{e.stopPropagation();b.closest('.dgnode').classList.toggle('collapsed')});
  wireGo(m);
}
// verification level of a citation in its tone (ton_map.verif); an unknown level is grey
const TREE_VERIF={match:'verified',sourced:'quelle_pdf',proposed:'unverifiziert'};
const treeTon=s=>tonOf('verif',TREE_VERIF[s]||s);
function statusBadge(s){return stBadge(treeTon(s),esc(({match:'verifiziert',sourced:'Quelle SHR-PDF',proposed:'unverifiziert'}[s]||s)),'Verifikationsstufe der Zitation');}
function listLaw(L){
  const nr=refNo(L.jur,L.sr,L.cref);
  return `<div class="tgrp"><div class="tline"><span class="ttog">▾</span> ${jur(L.jur)} <b>${esc(L.short||L.title)}</b> <span class="muted small">${esc(L.title)}</span>${nr?' <span class="mono small">'+esc(nr)+'</span>':''} ${standChip(L.lid)} <span class="small">${wirkLink(L.lid)}</span></div>
    <div class="tnode">${L.arts.map(listArt).join('')}</div></div>`;
}
function listArt(A){
  return `<div class="tgrp"><div class="tline"><span class="ttog">▾</span> <span class="mono">${esc(artLabel(A.no))}</span> ${esc(A.heading||'')}${unver(A.lc)} <span class="small">${wirkLink(A.lid,A.aid)}</span></div>
    <div class="tnode">${A.reqs.map(r=>`<div class="tline">• ${esc(r.dp)} ${statusBadge(r.status)} <span class="muted small">${esc(lab(DFTYPE,r.type))}</span></div>`).join('')}</div></div>`;
}
function dgLaw(L){
  const nr=refNo(L.jur,L.sr,L.cref);
  return `<div class="dgnode"><div class="dgbox" style="border-left-color:var(--line)"><span class="ttl">${esc(L.short||L.title)}</span> ${jur(L.jur)} ${standChip(L.lid)}<div class="sub">${esc(L.title)}${nr?' · '+esc(nr):''}</div></div>
    <div class="dgchildren">${L.arts.map(dgArt).join('')}</div></div>`;
}
function dgArt(A){
  return `<div class="dgnode"><div class="dgbox" style="border-left-color:var(--line)"><span class="ttl mono">${esc(artLabel(A.no))}</span><div class="sub">${esc(A.heading||'')}${unver(A.lc)}</div></div>
    <div class="dgchildren">${A.reqs.map(r=>`<div class="dgnode"><div class="dgbox" style="border-left-color:var(--ton-${treeTon(r.status)})"><span class="ttl">${esc(r.dp)}</span> ${statusBadge(r.status)}<div class="sub">${esc(lab(DFTYPE,r.type))}</div></div></div>`).join('')}</div></div>`;
}

// ---------- required information per law ----------
function viewInfo(into){
  const m=into||document.getElementById('main');
  if(state.service==='all'){ m.innerHTML=needService('Geforderte Informationen · pro Gesetz'); return; }
  let h=`<h3 class="view">Geforderte Informationen · pro Gesetz</h3>
  <p class="hint">Welche Datenfelder jedes Gesetz verlangt, mit Artikel-Zitat, Datentyp, Pflicht/optional und erfassendem Formular.</p>`;
  const sids = [Number(state.service)];
  // rows from the CURRENT model: each data field with its article citations
  const byLaw={};
  sids.forEach(sid=>(formsByService[sid]||[]).forEach(fm=>(fm.data_fields||[]).forEach(d=>{
    (d.legal_basis||[]).forEach(lb=>{
      const lk=(lb.law_short||lb.law_title||'?');
      (byLaw[lk]=byLaw[lk]||{lb,rows:[]}).rows.push({
        req:{data_point:d.name,label:d.definition,data_type:d.data_type,condition:d.required?'Pflicht':'optional'},
        lb, cap:[{label:fm.title,st:'formular'}]});
    });
  })));
  const laws=Object.values(byLaw);
  if(!laws.length){m.innerHTML=h+'<div class="nores">Keine Daten für die Auswahl.</div>';return;}
  laws.forEach(({lb,rows})=>{
    h+=`<div class="card"><div style="margin-bottom:10px">${jur(lb.jurisdiction)} <b>${esc(lb.law_title)}</b> ${(n=>n?'<span class="mono small">'+esc(n)+'</span>':'')(refNo(lb.jurisdiction,lb.sr_number,lb.cantonal_ref))}${unver(lb.last_checked)} ${standChip(lb.law_id)} <span class="small">${wirkLink(lb.law_id)}</span></div>
      <table><thead><tr><th>Datenfeld</th><th>Artikel</th><th>Typ</th><th>Pflicht</th><th>Formular</th></tr></thead><tbody>
      ${rows.map(({req,lb,cap})=>`<tr>
        <td><b>${esc(req.data_point)}</b><div class="small muted">${esc(req.label||'')}</div></td>
        <td class="mono small">${esc(artLabel(lb.article_no))}${lb.citation_detail?' '+esc(lb.citation_detail):''}${unver(lb.last_checked)}<div class="nomono">${wirkLink(lb.law_id,lb.article_id)}</div></td>
        <td class="small">${esc(lab(DFTYPE,req.data_type))}</td>
        <td class="small">${esc(req.condition||'—')}</td>
        <td>${cap.length?cap.map(c=>`«${esc(c.label)}»`).join('<br>'):'—'}</td>
      </tr>`).join('')}
      </tbody></table></div>`;
  });
  m.innerHTML=h;
  wireGo(m);
}


// ---------- Verzeichnis der Bearbeitungstätigkeiten (KDSG Art. 17b) ----------
// trigger events are real phrases from DATA.labels.trigger («nach Abschluss der
// Behandlung»), never de-underscored slugs; «unbestimmt» is said in brackets
function fmtTrigger(t){ if(!t) return ''; const s=lab(TRIGGER_DE,t); return t==='unbestimmt'?'('+s+')':s; }
function retLine(t){
  const dur=t.duration_value?`${t.min_or_max?lab(MINMAX_DE,t.min_or_max)+' ':''}${t.duration_value} ${t.duration_unit==='monate'?'Monate':'Jahre'}`:'ohne Zahl';
  const disp=t.disposition?'→ '+lab(DISP_DE,t.disposition):'';
  return `<b>${esc(dur)}</b> ${esc(fmtTrigger(t.trigger_event))} ${disp} <span class="muted small">(${esc(artLabel(t.article_no))} ${esc(t.short_title||'')})</span>`;
}
// DSFA indication is judged ONCE in export_json (form.dsfa_indiziert); one rule for the
// Verzeichnis, the service page and the Formular-Ansicht
function dsfaIndOf(fm){return !!fm.dsfa_indiziert;}
function formStats(fm){
  const dfs=fm.data_fields||[];
  const sens=dfs.filter(d=>d.sensitive).length;
  // the fields of the form by their exported answer to the legal question (d.basis_state):
  // the register must not read "no basis" for a field that IS covered — a task-necessary
  // field (KDSG Art. 4 Abs. 1 lit. b) has a basis, just not an article naming it; only
  // «ohne» is surplus and only «zu_ermitteln» is unresearched; a ⛨ field judged
  // task-necessary without its basis under KDSG Art. 5 (art5_offen) is OPEN, not covered
  const by=k=>dfs.filter(d=>d.basis_state===k).length;
  const lb=by('artikel'), auf=by('aufgabe'), a5=by('art5_offen'), ohne=by('ohne'), offen=by('offen'), todo=by('zu_ermitteln');
  const dsfaInd=dsfaIndOf(fm);
  return {n:dfs.length,sens,lb,auf,a5,ohne,offen,todo,dsfaInd,
    hasZweck:!!fm.purpose,hasEmpf:(fm.disclosures||[]).length>0,
    hasFrist:(fm.retention||[]).length>0||(fm.retention_decisions||[]).length>0};
}
function viewRegister(){
  const m=document.getElementById('main');
  const fms=DATA.forms.filter(f=>(f.data_fields||[]).length);
  const st=fms.map(f=>({f,s:formStats(f)}));
  // «Zweck, Empfänger und Frist erfasst» is the headline figure of the start page
  // (kopfzahlen.verzeichnis.wert); the single parts are plain counts over the forms
  const c={zweck:0,empf:0,frist:0,dsfa:0,voll:((DATA.kopfzahlen||{}).verzeichnis||{}).wert||0};
  st.forEach(({s})=>{if(s.hasZweck)c.zweck++;if(s.hasEmpf)c.empf++;if(s.hasFrist)c.frist++;
    if(s.dsfaInd)c.dsfa++;});
  let h=pageHead('Verzeichnis der Bearbeitungstätigkeiten',
    'Je Formular die Angaben eines Verzeichnisses — Zweck, Datenkategorien, Rechtsgrundlagen, Empfänger, Aufbewahrung —, dazu die DSFA-Triage und eine Übersicht je Dienststelle.',
    'Ein Verzeichnis-Auszug je Formular — verantwortliche Stelle, Zweck, Datenkategorien, Rechtsgrundlagen, Empfänger, Aufbewahrung — plus DSFA-Triage und Übersicht je Dienststelle.',
    'Verantwortliche und Kategorien aus der kuratierten Feld-Schicht; Zwecke kuratiert; Empfänger nur mit Artikel-Beleg; Fristen aus dem zitatverifizierten Fristen-Register. Die DSFA-Spalte ist ein berechneter Vorschlag (Prüfpflicht: KDSG Art. 14b) — entschieden wird von Menschen.',
    'Rechtliche Einordnung: Die Struktur folgt KDSG Art. 17b Abs. 2 (Rechtsgrundlage, Zweck, Mittel, Art, Herkunft, regelmässige Empfänger); das Gesetz nennt sie dort «öffentliche Register über die Datenbearbeitungstätigkeiten». Eine Pflicht, ein solches Register öffentlich zu führen, trifft nach KDSG Art. 17b nur Polizei, Staatsanwaltschaft und Justizvollzug; für alle übrigen Dienststellen ist dieses Verzeichnis ein Steuerungsinstrument der Databank, keine kantonale Rechtspflicht. Fehlende Inhalte stehen als «fehlt» — das ist der Arbeitsvorrat, kein Darstellungsfehler.')+`
  <div class="regstats">
    <span class="rstat">Zweck erfasst <b>${c.zweck}/${st.length}</b></span>
    <span class="rstat">Empfänger belegt <b>${c.empf}/${st.length}</b></span>
    <span class="rstat">Spezialfrist/Entscheid <b>${c.frist}/${st.length}</b></span>
    <span class="rstat" title="Zweck, mindestens ein belegter Empfänger und eine Spezialfrist/ein Fristentscheid sind erfasst — sagt nichts über die Rechtsgrundlagen der Felder">Zweck, Empfänger und Frist erfasst <b>${c.voll}/${st.length}</b></span>
    <span class="rstat" title="${esc('Formulare, bei denen die berechnete Triage eine Datenschutz-Folgenabschätzung nahelegt (KDSG Art. 14b) — entscheiden muss der Kanton\n'+tonWords(tonOf('dsfa','indiziert')))}">${SW(tonOf('dsfa','indiziert'))}DSFA indiziert <b>${c.dsfa}</b></span>
  </div>`;
  // DSFA triage: computed from real sensitive-field density, decided by humans
  const triage=st.filter(x=>x.s.dsfaInd).sort((a,b)=>b.s.sens-a.s.sens);
  if(triage.length){
    h+=`<div class="card"><div class="dvsub">DSFA-Triage — Formulare mit mindestens drei (oder zur Hälfte) besonders schützenswerten Feldern (berechnet; ob eine DSFA nötig ist, ist noch nicht entschieden)</div>
    <div class="tscroll"><table class="ft fit"><thead><tr><th>Formular</th><th>⛨ Felder</th><th>Anteil</th><th>DSFA-Status</th></tr></thead><tbody>`;
    triage.forEach(({f,s})=>{
      h+=`<tr data-sid="${f.service_id}" style="cursor:pointer"><td>${formLink(f.service_id,f.id,esc(f.title))}</td>
        <td>${s.sens}/${s.n}</td><td>${pctTxt(s.sens,s.n)}</td>
        <td>${f.dsfa_status?stBadge(tonOf('dsfa','entschieden'),esc(f.dsfa_status),'DSFA-Entscheid getroffen'):stBadge(tonOf('dsfa','indiziert'),'offen','DSFA indiziert — der Entscheid des Kantons steht aus (KDSG Art. 14b)')}</td></tr>`;});
    h+=`</tbody></table></div></div>`;
  }
  // Übersicht je Dienststelle: where the besonders schützenswerte fields are collected
  const heat={};
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>{
    if(!d.sensitive)return;
    const dn=dstOf(f);
    const e=heat[dn]=heat[dn]||{total:0,cats:{},nb:0,a5:0};
    e.total++; e.cats[d.sensitive]=(e.cats[d.sensitive]||0)+1; if(d.basis_state==='ohne')e.nb++; if(d.basis_state==='art5_offen')e.a5++;}));
  const hrows=Object.entries(heat).sort((a,b)=>b[1].total-a[1].total).slice(0,15);
  if(hrows.length){
    h+=`<div class="card"><div class="dvsub">Übersicht je Dienststelle — besonders schützenswerte Felder</div>
    <div class="tscroll"><table class="ft fit"><thead><tr><th>Dienststelle</th><th>⛨ total</th><th>Kategorien</th><th title="Felder ohne Grundlage (weder Norm noch Aufgabenbedarf) sowie ⛨-Felder, die als aufgabennotwendig gelten, deren Grundlage nach KDSG Art. 5 Abs. 1 aber noch nicht benannt ist">davon ohne benannte Grundlage</th></tr></thead><tbody>`;
    hrows.forEach(([dn,e])=>{
      h+=`<tr><td>${esc(dn)}</td><td><b>${e.total}</b></td>
        <td class="small hy">${Object.entries(e.cats).map(([k,v])=>`${esc(lab(HSENS,k))} ${v}`).join(' · ')}</td>
        <td>${e.nb?stBadge(tonOf('basis','ohne'),'ohne Grundlage '+nf(e.nb),'Felder ohne Grundlage — weder Norm noch Aufgabenbedarf')+' ':''}${e.a5?stBadge(tonOf('basis','art5_offen'),'Art. 5 offen '+nf(e.a5),'aufgabennotwendig, Grundlage nach KDSG Art. 5 Abs. 1 noch nicht benannt — offen'):''}${(e.nb||e.a5)?'':'—'}</td></tr>`;});
    h+=`</tbody></table></div></div>`;
  }
  // the register itself, one row per SERVICE (its forms aggregated)
  const bySvc={};
  st.forEach(({f,s})=>{
    const e=bySvc[f.service_id]=bySvc[f.service_id]||{svc:svcById[f.service_id],forms:0,n:0,sens:0,lb:0,
      auf:0,a5:0,ohne:0,offen:0,todo:0,empf:0,zweck:true,frist:false,purpose:null};
    e.forms++; e.n+=s.n; e.sens+=s.sens; e.lb+=s.lb; e.empf+=(f.disclosures||[]).length;
    e.auf+=s.auf; e.a5+=s.a5; e.ohne+=s.ohne; e.offen+=s.offen; e.todo+=s.todo;
    e.zweck=e.zweck&&s.hasZweck; e.frist=e.frist||s.hasFrist; e.purpose=e.purpose||f.purpose;});
  h+=`<div class="card"><div class="dvsub">Verzeichnis-Auszug je Service — «Grundlagen» zählt Artikel-belegte Felder plus die aufgabennotwendigen (Massstab KDSG Art. 4 Abs. 1 lit. b); ⛨-Felder ohne benannte Grundlage nach KDSG Art. 5 Abs. 1, «offen/zu ermitteln» und «ohne Grundlage» zählen als ungedeckt</div>
    <div class="tscroll"><table class="ft fit"><thead><tr><th>Service</th><th class="wd">Dienststelle</th>
    <th class="wd">Formulare</th><th>Zweck</th><th>Felder</th><th>Grundlagen</th><th>Empfänger</th><th title="Regelfrist = die allgemeine Aufbewahrung (Registraturperiode); Spezialfrist = eine eigene Frist aus dem Fachrecht oder ein Fristentscheid">Frist</th></tr></thead><tbody>`;
  Object.entries(bySvc).forEach(([sid,e])=>{
    const nm=e.svc?e.svc.name:'?';
    h+=`<tr data-sid="${sid}" style="cursor:pointer">
      <td><a class="dlink" href="#fields/${encodeURIComponent(sid)}" data-nav="1">${esc(nm)}</a><div class="small muted nw">${esc((e.svc&&e.svc.dienststelle)||'')} · ${pl(e.forms,'Formular','Formulare')}</div></td>
      <td class="small muted wd hy">${esc((e.svc&&e.svc.dienststelle)||'')}</td>
      <td class="small wd">${e.forms}</td>
      <td>${e.zweck?stBadge('ok','erfasst','Zweck der Bearbeitung festgehalten'+(e.purpose?': «'+e.purpose+'»':'')):stBadge(catTon('zweck'),'fehlt','Der Bearbeitungszweck ist für mindestens ein Formular dieses Services noch nicht festgehalten')}</td>
      <td class="small">${e.n}${e.sens?` <span class="badge b-sens">⛨${e.sens}</span>`:''}</td>
      <td class="small" title="${pl(e.lb,'Feld','Felder')} mit Artikel · ${e.auf} aufgabennotwendig (Massstab KDSG Art. 4 Abs. 1 lit. b) · ${e.a5} ⛨ aufgabennotwendig, Grundlage nach KDSG Art. 5 Abs. 1 noch nicht benannt (offen) · ${e.ohne} ohne Grundlage · ${e.offen} Aufgabenbedarf offen · ${e.todo} noch nicht recherchiert">${e.lb+e.auf}/${e.n}${e.auf?` <span class="muted">(${e.lb}+${e.auf})</span>`:''}${e.ohne?' '+stBadge(tonOf('basis','ohne'),nf(e.ohne),'Felder ohne Grundlage'):''}${e.a5?' '+stBadge(tonOf('basis','art5_offen'),'⛨'+nf(e.a5),'⛨ ohne benannte Grundlage nach KDSG Art. 5 Abs. 1'):''}${e.todo?' '+stBadge(tonOf('basis','zu_ermitteln'),nf(e.todo),'noch nicht recherchiert'):''}</td>
      <td>${e.empf?e.empf:stBadge(catTon('empf'),'fehlt','Keine belegte Bekanntgabe erfasst — entweder gibt es keine, oder sie ist noch nicht mit Artikel dokumentiert')}</td>
      <td class="small nowrap">${e.frist?'<b>Spezialfrist</b>':'Regelfrist'}</td></tr>`;});
  h+=`</tbody></table></div></div>`;
  m.innerHTML=h;
  // a row opens the DATA view of the service, whatever segment was open before
  m.querySelectorAll('tr[data-sid]').forEach(tr=>tr.onclick=e=>{if(e.target.closest('a')) return;
    state.service=tr.dataset.sid;state.tab='fields';state.sub='felder';render();});
  wireGo(m);
}

// ---------- Datenkatalog (canonical attributes, Once-Only, divergences) ----------
function viewKatalog(){
  const m=document.getElementById('main');
  const kat=DATA.attribut_katalog||[];
  const reg=kat.filter(a=>a.register_source);
  // only the instances collected as a NATURAL PERSON's datum can come from the
  // register; the same element also carries business and object addresses
  const regInst=reg.reduce((n,a)=>n+(a.n_register||0),0);
  let h=pageHead(`Datenkatalog · die ${nf(kat.length)} verschiedenen Attribute des Kantons`,
    'Jede Angabe des Kantons einmal: mit welchem eCH- oder eSH-Element sie erfasst ist, wo sie anders verlangt wird und was das Einwohnerregister schon führt.',
    'Eine Zeile je Attribut (kanonisches Attribut = ein eCH- oder eSH-Element), egal auf wie vielen Formularen es erhoben wird — die Stammdaten-Sicht über den ganzen Katalog.',
    'Vollständig abgeleitet aus den eCH/eSH-Zuordnungen der Feld-Schicht, bei jeder Aktualisierung neu berechnet. «Einwohnerregister» markiert Attribute, die zu einem der Personen- und Adressstandards gehören (eCH-0044/0010/0011/0007/0008) UND mindestens einmal als Angabe zu einer natürlichen Person erhoben werden.',
    `Der Kanton fragt registergeführte Personendaten trotzdem ${nf(regInst)} Mal ab — das ist das Once-Only-Potenzial. Gezählt sind nur Erhebungen bei natürlichen Personen: dieselben Elemente tragen auch Betriebs- und Objektadressen, die das Register nicht führt. Divergenzen zeigen, wo dieselbe Angabe uneinheitlich erhoben wird. Zeile aufklappen listet die erhebenden Formulare.`);
  // exchange pipeline: how close is each form to a real eCH payload?
  const withDf=DATA.forms.filter(f=>(f.data_fields||[]).length);
  const online=new Set();
  DATA.services.forEach(s=>{if(s.dvsh&&(s.dvsh.abgabe||[]).some(x=>/Online-Formular/.test(String(x))))online.add(s.id);});
  const full=withDf.filter(f=>f.exchange_pct===100), p80=withDf.filter(f=>f.exchange_pct>=80&&f.exchange_pct<100);
  const pilot=full.filter(f=>online.has(f.service_id));
  h+=`<div class="regstats">
    <span class="rstat" title="${esc('Formulare, deren Datenpunkte alle ein eCH-Element tragen\n'+tonWords(tonOf('ech','element')))}">${SW(tonOf('ech','element'))}Formulare voll eCH-zugeordnet <b>${nf(full.length)}</b></span>
    <span class="rstat">Formulare zu 80–99&nbsp;% zugeordnet <b>${nf(p80.length)}</b></span>
    <span class="rstat" title="Formulare, die voll eCH-zugeordnet sind und laut DVSH schon online eingereicht werden können — ein Teil der voll zugeordneten">voll zugeordnet und online einreichbar <b>${nf(pilot.length)}</b> → Pilotmenge</span>
    <span class="rstat">registerbeziehbare Attribute <b>${reg.length}</b></span>
  </div>`;
  if(pilot.length){
    h+=`<div class="card"><div class="dvsub">Datenaustausch-Pilotliste — voll standardisiert und schon online einreichbar</div>
    ${pilot.map(f=>`<div class="small" style="padding:2px 0">• <a class="simlink" data-sid="${f.service_id}">${esc(f.title)}</a></div>`).join('')}</div>`;
  }
  // divergences are NOT recomputed here: the tables aggregate the per-form
  // standard_divergenzen (computed once in export_json on the atomic unit, incl.
  // Teilfelder), so this page shows the same elements as the Formular pages,
  // the Handlungsbedarf and the dossiers
  const dvAgg={};
  DATA.forms.forEach(f=>(((f.standard_divergenzen||{}).angleichen)||[]).forEach(i=>{
    const el=`${i.standard}·${i.element}`, k=i.art+'|'+el;
    const x=dvAgg[k]=dvAgg[k]||{art:i.art,el,forms:new Set(),n:0,akt:new Set()};
    x.forms.add(f); x.n++; if(i.aktion) x.akt.add(i.aktion);}));
  // «Pflicht uneinheitlich» per datum: the same helper as the card on «Für den Kanton»
  const dvRows=art=>art==='pflicht_uneinheitlich'?pflichtUneinheitlichAgg()
    :Object.values(dvAgg).filter(x=>x.art===art).sort((a,b)=>b.forms.size-a.forms.size||b.n-a.n||a.el.localeCompare(b.el));
  // the action text is the one export_json wrote per item; it is uniform for some
  // arts and element-specific for others (format names the XSD type, pflicht says
  // whether the others demand or leave optional) — never generalise one row's text
  const dvTable=(art,title)=>{const R=dvRows(art); if(!R.length) return '';
    const akts=[...new Set(R.flatMap(x=>[...x.akt]))];
    const cap=akts.length===1?esc(akts[0]):`Handlung je Element: das eCH-Element antippen (${akts.length} Varianten, z. B. «${esc(akts[0]||'')}»)`;
    return `<div class="card"><div class="dvsub">${stBadge(tonOf('div',art),esc(lab(DIV_DE,art)),tonOf('div',art)==='dec'?'Kein Formular ist die Ausnahme — der Kanton legt fest':'Die Dienststelle gleicht das Formular an oder begründet die Abweichung')} ${title} (${pl(R.length,'Element','Elemente')})</div>
      <div class="small muted" style="margin:4px 0 6px">→ ${cap}</div>
      <div class="tscroll"><table class="ft fit"><thead><tr><th>eCH-Element</th><th>Formulare</th><th>Datenpunkte</th><th>Formulare (Auszug)</th></tr></thead><tbody>
      ${R.slice(0,15).map(x=>`<tr><td class="mono small nowrap" title="${esc([...x.akt].join('\n'))}">${esc(x.el)}</td><td>${x.forms.size}</td><td>${x.n}</td>
        <td class="small">${[...x.forms].slice(0,3).map(f=>`<a class="simlink" data-sid="${f.service_id}">${esc(f.title.length>40?f.title.slice(0,38)+'…':f.title)}</a>`).join(' · ')}${x.forms.size>3?` <span class="muted">+${x.forms.size-3}</span>`:''}</td></tr>`).join('')}
      </tbody></table></div>${R.length>15?`<div class="small muted" style="padding:4px 2px">— die 15 häufigsten von ${R.length} Elementen; massgeblich ist der Abschnitt «Standard-Divergenzen» je Formular bzw. der Handlungsbedarf</div>`:''}</div>`;};
  h+=dvTable('pflicht','— dieselbe Angabe ist hier Pflicht, dort optional, gegen eine klare Praxis (≥ 2/3 der übrigen Vorkommen)');
  h+=dvTable('pflicht_uneinheitlich','— die Formulare sind sich uneins: kein Formular ist die Ausnahme, es fehlt eine kantonale Festlegung');
  h+=dvTable('format','— dieselbe Angabe in anderer Form (Datentyp/Format) als ≥ 2/3 der Vorkommen');
  h+=dvTable('codeliste','— eigene Wertelisten statt der offiziellen Codes des Standards');
  // code-list check: the swept XSDs define enumerations (sex 1/2/3, maritalStatus 1..9 ...);
  // a form that offers its own value list must be mapped onto those codes at exchange time
  const CL=DATA.ech_codelists||{}; const clSeen={};
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>{
    if(!(d.ech&&d.ech.element&&d.ech.datatype)) return;
    const cl=CL[d.ech.codelist_key||(d.ech.standard+'|'+d.ech.datatype)]; if(!cl) return;
    const vals=(d.allowed_values||[]).map(String); if(!vals.length) return;
    const codes=new Set(cl.map(c=>c.value));
    const asCode=vals.filter(v=>codes.has(v)).length;
    const key=d.ech.standard+'·'+d.ech.element; const x=clSeen[key]=clSeen[key]||{el:key,dt:d.ech.datatype,n:0,codeOk:0,text:0,forms:new Set(),sample:vals.slice(0,4),cl};
    x.n++; x.forms.add(f); if(asCode===vals.length) x.codeOk++; else x.text++;}));
  const clList=Object.values(clSeen).sort((a,b)=>b.n-a.n);
  h+=`<div class="card"><div class="dvsub">Codelisten-Abgleich — Wertelisten der Formulare gegen die offiziellen Codes aus den eCH-XSDs (${pl(clList.length,'Element','Elemente')} mit Codeliste; XSD-Prüfung ${(()=>{const v=DATA.forms.flatMap(f=>(f.data_fields||[]).map(d=>d.ech&&d.ech.xsd_version)).find(Boolean);return v?'versioniert':'';})()})</div>
    <div class="small muted" style="margin-bottom:6px">«Klartext» heisst: das Formular lässt z. B. «ledig / verheiratet» ankreuzen, der Standard tauscht den Code (1, 2, …) aus — beim Export ist die Werteliste auf die Codes abzubilden; das ist keine Rechtsfrage, aber eine Voraussetzung für den Datenaustausch.</div>
    <div class="tscroll"><table class="ft fit"><thead><tr><th>eCH-Element</th><th class="wd">Typ</th><th>offizielle Codes</th><th>Felder</th><th>Codes verwendet</th><th>Klartext</th><th>Beispielwerte</th></tr></thead><tbody>
    ${clList.slice(0,20).map(x=>`<tr><td class="mono small">${codeBrk(x.el)}<div class="nw muted brk">Typ ${esc(x.dt)}</div></td><td class="mono small wd">${esc(x.dt)}</td><td class="small" title="${esc(x.cl.slice(0,20).map(c=>c.value+(c.doc?' = '+c.doc:'')).join('\n'))}">${x.cl.length}</td><td>${x.n}</td><td>${x.codeOk}</td><td>${x.text?stBadge(tonOf('div','codeliste'),nf(x.text),'Felder mit Klartext statt der offiziellen Codes — beim Austausch auf die Codes abzubilden, oder das Formular bietet die Codes an'):'—'}</td><td class="small muted hy brk">${esc(x.sample.join(' · '))}</td></tr>`).join('')}
    </tbody></table></div>${clList.length?'':'<div class="small muted">Keine Felder mit Werteliste auf einem Element mit Codeliste.</div>'}</div>`;
  // the catalogue itself, most-collected first
  h+=`<div class="card"><div class="tscroll"><table class="ft fit"><thead><tr><th>Attribut<span class="nw"> · eCH-Element / eSH-Entwurf</span></th><th class="wd">eCH-Element / eSH-Entwurf</th>
    <th>Formulare</th><th>Erhebungen</th><th>Register</th><th>⛨</th></tr></thead><tbody>`;
  // which forms collect a given element (for the expandable rows)
  const collectors={};
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>{
    const push=e=>{if(e&&e.element)(collectors[`${e.standard}·${e.element}`]=collectors[`${e.standard}·${e.element}`]||new Set()).add(f);};
    // eSH rows are keyed 'eSH-00xx:element' in the catalogue — index them too,
    // otherwise every eSH row claims collecting forms it can never show
    const pushE=e=>{if(e&&e.code&&e.element)(collectors[`${e.code}:${e.element}`]=collectors[`${e.code}:${e.element}`]||new Set()).add(f);};
    // same atomic rule as the catalogue: a composite is represented by its
    // parts, so its own element is not counted beside them
    const ss=(d.subfields||[]).filter(s=>s&&typeof s==='object');
    if(ss.length){ ss.forEach(s=>{push(s.ech); pushE(s.esh);}); }
    else { push(d.ech); pushE(d.esh); }}));
  kat.slice(0,120).forEach(a=>{
    const el=a.ech_standard?`${a.ech_standard}·${a.ech_element}`:(a.esh_key||'');
    let cats=[]; try{cats=JSON.parse(a.sensitive_categories||'[]')}catch(e){}
    const fms=[...(collectors[el]||[])];
    // an eSH code is the canton's draft, never official eCH: violet, dashed, «Entwurf»
    // (in the wide layout a column of its own, up to 1340 px a line under the attribute)
    const elIn=!a.ech_standard&&a.esh_key?`<span class="eshb" style="margin-left:0" title="Vorschlag für den kantonalen Standard eSH (E-Schaffhausen) — Entwurf, nicht offiziell">${esc(String(a.esh_key).replace(':',' · '))}<span class="ent">Entwurf</span></span>`
      :`<span class="mono small">${codeBrk(el)}</span>${a.ech_standard&&ECH_TITEL[a.ech_standard]?`<div class="small muted">${esc(ECH_TITEL[a.ech_standard])}</div>`:''}`;
    h+=`<tr class="katrow" data-el="${esc(el)}"${fms.length?' aria-expanded="false"':''}><td><b>${esc(a.label)}</b><div class="nw">${elIn}</div></td><td class="wd">${elIn}</td>
      <td${fms.length!==a.n_forms?` title="Katalogwert ${a.n_forms} — gezählt wird die Liste, die diese Zeile aufklappt"`:''}>${fms.length||a.n_forms}</td><td>${a.n_instances}</td>
      <td>${a.register_source?'<span class="regc" title="Once-Only: das Einwohnerregister führt diese Angabe — ein Kennzeichen, keine Bewertung">↺<span class="wd"> Einwohnerregister</span></span>':'—'}</td>
      <td class="hy">${cats.length?`<span class="badge b-sens" title="auf mindestens einem Formular in sensitivem Kontext erhoben">⛨ ${cats.map(x=>esc(lab(HSENS,x))).join(', ')}</span>`:''}</td></tr>
      ${fms.length?`<tr class="katforms" hidden><td colspan="6">${fms.slice(0,30).map(f=>`<a class="simlink small" data-sid="${f.service_id}">• ${esc(f.title)}</a>`).join('<br>')}
        ${fms.length>30?`<div class="muted small">— 30 von ${fms.length} Formularen angezeigt; die ganze Liste steht in data_export.json (forms → data_fields → ech) oder über die Suche nach dem Element</div>`:''}</td></tr>`:''}`;});
  h+=`</tbody></table></div><div class="muted small" style="padding:6px 2px">Die 120 meist-erhobenen von ${nf(kat.length)} Attributen; der ganze Katalog steht in data_export.json (Schlüssel attribut_katalog). Zeile anklicken = erhebende Formulare.</div></div>`;
  m.innerHTML=h;
  m.querySelectorAll('.katrow').forEach(tr=>{const nx=tr.nextElementSibling;
    if(!(nx&&nx.classList.contains('katforms'))) return;
    tr.onclick=()=>{nx.hidden=!nx.hidden; tr.setAttribute('aria-expanded',String(!nx.hidden));};});
  m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=(ev)=>{ev.stopPropagation();
    state.service=a.dataset.sid;state.tab='fields';state.sub='felder';render();});
}
function viewEsh(){
  const m=document.getElementById('main');
  const kat=DATA.esh_katalog||[];
  // live = what the field layer says today (esh_katalog[].n_live, counted in export_json on
  // the atomic unit: a composite is represented by its parts, its own code is not counted
  // beside them)
  const eshLive=kat.reduce((n,k)=>n+(k.n_live||0),0);
  // the data points without an eCH standard in force (kopfzahlen.kein_standard — the amber
  // part of the start page) and what eSH covers of them; the grey and light-green parts
  // are outside eSH's scope
  const ET=((DATA.kopfzahlen||{}).standard_ech||{}).teile||{};
  const nKs=KS.von||0, nE=KS_T.esh||0, nO=KS_T.ohne||0, nW=KS_T.ech_entwurf||0, nOpen=nKs-nE;
  let h=`<div class="band entwurf" role="note"><b>Entwurf</b>Entwurf des Kantons — kein offizieller eCH-Standard. Ein eSH-Code gilt nur dort, wo kein eCH-Standard die Angabe abdeckt.</div>`
    +pageHead('eSH-Katalog · E-Schaffhausen-Standard (Entwurf)',
    `Der Entwurf des Kantons für Daten ohne eCH-Standard: ${pl(kat.length,'eSH-Entwurf','eSH-Entwürfe')}, heute auf ${pl(eshLive,'Datenpunkt','Datenpunkten')} — kein offizieller eCH-Standard.`,
    `Ein kantonaler Entwurf eines Datenstandards für Datenpunkte, die kein eCH-Standard abdeckt — ${pl(kat.length,'Entwurf','Entwürfe')}, abgeleitet aus den realen Formularfeldern. Heute ${eshLive===1?'trägt':'tragen'} <b>${nf(eshLive)}</b> ${plw(eshLive,'Datenpunkt','Datenpunkte')} einen eSH-Code (gezählt je Datenpunkt: ein Teilfeld, oder ein Datenfeld ohne Teile).`,
    `Ein Entwurf des Kantons, von der Databank aus den realen Formularfeldern abgeleitet — nicht offiziell; in der ganzen Databank violett-gestrichelt und als «Entwurf» markiert, damit er nie mit offiziellem eCH verwechselt wird. Regel: eSH überdeckt nie ein eCH-Element — wo eCH zugeordnet wird, fällt der Entwurfscode weg.`,
    `Gedacht als Diskussionsgrundlage für den Kanton. Von ${pl(nKs,'Datenpunkt','Datenpunkten')} ohne geltenden eCH-Standard ${plw(nE,'trägt','tragen')} ${nf(nE)} einen eSH-Entwurf; ${nf(nOpen)} ${plw(nOpen,'ist','sind')} noch offen (${nf(nO)} ohne eCH-Standard, ${nf(nW)} mit eCH-Standard erst im Entwurf). Ausserhalb von eSH liegen ${pl(ET.ok_standard||0,'Datenpunkt','Datenpunkte')}, die auf Standard-Ebene geklärt ${plw(ET.ok_standard||0,'ist','sind')}, und ${nf(ET.open||0)}, die an einem Standard ${plw(ET.open||0,'hängt','hängen')}, der nicht mehr in Kraft ist oder dessen Element noch offen ist — die Databank ordnet sie zu.`);
  if(!kat.length){m.innerHTML=h+'<div class="nores">Noch kein Katalog geladen.</div>';return;}
  kat.forEach(k=>{
    let th=[]; try{th=JSON.parse(k.themen||'[]')}catch(e){}
    h+=`<div class="card" id="esh-${esc(k.code)}"><div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
      <span class="eshb">${esc(k.code)}<span class="ent">Entwurf</span></span><b style="font-size:var(--fs-m)">${esc(k.titel)}</b>
      <span class="muted small" style="margin-left:auto">${pl(k.n_live||0,'Datenpunkt','Datenpunkte')} heute · Status: ${esc(lab(ESH_STATUS,k.status||'entwurf'))}</span></div>
      <div class="dfdef" style="margin-top:6px">${esc(k.beschreibung||'')}</div>
      ${th.length?`<div class="dfchips" style="margin-top:6px">${th.map(t=>`<span class="chip">${esc(t)}</span>`).join('')}</div>`:''}
    </div>`;
  });
  m.innerHTML=h;
}
// ---------- Handlungsbedarf: every open item, grouped by the office that owns it ----------
// The RULES that emit an item live in export_json.py (form.handlungsbedarf,
// computed ONCE for board, service page, dossier, CSV and LLM export); the
// wording per category (label, badge class, Art, meaning) comes from
// DATA.labels.todo_cats / todo_art. 'art' says what KIND of work closes a point:
//   recherche   - the databank has not looked yet (our backlog)
//   entscheid   - only the canton can decide (we never fake a default)
//   bereinigung - the Dienststelle has to change the form or its practice
function todoItems(f){return f.handlungsbedarf||[];}
function viewTodo(){
  const m=document.getElementById('main');
  // the board shows what Dienststellen change (red) and what the canton decides (amber);
  // the databank's own homework (grey) has its page «Recherche der Databank».
  // Filter in the URL: 'alle' · one category · 'wer-act' | 'wer-dec' · 'stufe-N' · the
  // last two joined by '~'; the older 'art-bereinigung' / 'art-entscheid' still work
  const asked=state.sub;
  let wer=null, stufe=null, cat=null, bad=false;
  String(asked||'alle').split('~').forEach(t=>{
    if(!t||t==='alle'||t==='felder') return;
    let x;
    if((x=/^wer-(act|dec)$/.exec(t))) wer=x[1];
    else if(t==='art-bereinigung') wer='act';
    else if(t==='art-entscheid') wer='dec';
    else if((x=/^stufe-(\d+)$/.exec(t))&&STUFEN.some(s=>s.n===Number(x[1]))) stufe=Number(x[1]);
    else if(TODO_BY[t]&&catTon(t)!=='open') cat=t;
    else bad=true;});
  if(cat){wer=null; stufe=null;}
  const subOf=(w,s)=>[w&&'wer-'+w, s&&'stufe-'+s].filter(Boolean).join('~')||'alle';
  state.sub=cat||subOf(wer,stufe);
  const keep=i=>{const t=itemTon(i); if(t==='open') return false;
    if(cat) return i.cat===cat;
    return (!wer||t===wer)&&(!stufe||itemStufe(i)===stufe);};
  // counts: every chip row counts under the OTHER active filter, so a number always
  // says what a click on it will show
  const tot={act:0,dec:0,open:0}, byCat={}, byStufe={}, byWer={act:0,dec:0};
  DATA.forms.forEach(f=>todoItems(f).forEach(i=>{const t=itemTon(i); tot[t]=(tot[t]||0)+i.n;
    if(t==='open') return;
    byCat[i.cat]=(byCat[i.cat]||0)+i.n;
    const s=itemStufe(i);
    if(!wer||t===wer) byStufe[s]=(byStufe[s]||0)+i.n;
    if(!stufe||s===stufe) byWer[t]=(byWer[t]||0)+i.n;}));
  // every form once, its points in the filter, grouped by the owning Dienststelle
  const groups={}; let nForms=0, nItems=0;
  DATA.forms.forEach(f=>{
    const its=todoItems(f).filter(keep).sort(byPrio); if(!its.length) return;
    nForms++;
    const dn=dstOf(f); const g=groups[dn]=groups[dn]||{forms:[],n:0,byTon:{act:0,dec:0,open:0}};
    g.forms.push({f,its});
    its.forEach(i=>{nItems+=i.n; g.n+=i.n; g.byTon[itemTon(i)]+=i.n;});});
  const nVerf=DATA.forms.filter(f=>f.outcome).length;
  // the Schutzstufe gap is corpus-wide, not a property of the current filter —
  // counted over ALL forms of a Dienststelle, fields without a Schutzstufe only
  const dstAll={}; DATA.forms.forEach(f=>{const k=(f.data_fields||[]).filter(x=>!x.schutzstufe).length; if(!k) return;
    const e=dstAll[dstOf(f)]=dstAll[dstOf(f)]||{forms:0,fields:0}; e.forms++; e.fields+=k;});
  const showIsv=!cat&&!stufe&&wer!=='act';
  const actCats=CAT_ORDER.filter(k=>TODO_BY[k]&&catTon(k)!=='open');
  // what one point counts, in the words of DATA.labels.einheit
  const uW=[...new Set(actCats.filter(k=>!formCat(k)).map(k=>UNIT_WORD(catUnitOf(k)[0])))].map(w=>'1 '+w);
  const unitTxt=`1 Punkt = je nach Kategorie ${uW.length>1?uW.slice(0,-1).join(', ')+' oder '+uW[uW.length-1]:uW.join('')}${actCats.some(formCat)?`${uW.length?', ':''}bei Angaben zum ganzen Formular 1 Formular`:''}.`;
  let h=pageHead('Handlungsbedarf · Was Dienststellen ändern und der Kanton entscheidet',
    `${pl(tot.act,'Punkt','Punkte')} kann eine Dienststelle an ihrem Formular selbst ändern, ${nf(tot.dec)} ${plw(tot.dec,'wartet','warten')} auf einen Entscheid des Kantons — je Dienststelle, nach Priorität; die Hausaufgaben der Databank stehen unter «Recherche der Databank».`,
    `Die offenen Punkte, bei denen jemand in der Verwaltung handeln muss — ${actCats.length} Arten: ${actCats.map(k=>'«'+esc(todoCat(k)[1])+'»').join(', ')}, dazu die fehlende Schutzstufe (ISV) —, sortiert nach der Dienststelle mit ihrem Kontakt, soweit im DVSH hinterlegt. ${unitTxt}`,
    'Aus den offenen Punkten der einzelnen Formulare zusammengezählt (der kuratierten Feld-Schicht, dem Verzeichnis, der Online-Prüfung, dem Duplikat-Radar, der Begriffe- und Divergenz-Schicht, der Rechtsmittel-Prüfung und den Verfahren) — die Briefings der Dienststellen, «Für den Kanton», «Recherche der Databank», die Dossiers und die CSV lesen dieselbe Liste. Die Schutzstufe (ISV) fehlt für alle Felder, weil der Kanton sie noch nicht festgelegt hat — sie steht deshalb einmal je Dienststelle, nicht je Formular.',
    'Ein offener Punkt ist eine Lücke — etwas ist noch zu klären, zu entscheiden oder zu belegen. Die Farbe sagt, wer als Nächstes handelt; die Filter zeigen einen Teil nach «wer handelt», Priorität oder Kategorie. Die Zahl auf einem Punkt zählt Datenpunkte, Felder oder Formularpaare; ein Punkt ohne Zahl betrifft das ganze Formular. Die CSV enthält immer alle Punkte, auch die grauen, mit den Spalten «Wer handelt» und «Priorität».');
  const on=b=>b?' on':'';
  const btn=(sub,cls,inner,tip)=>`<button type="button" class="tcat${cls}" data-sub="${sub}"${tip?` title="${esc(tip)}"`:''}>${inner}</button>`;
  h+=`<div class="filt">
    <div class="filtrow"><span class="fl">Wer handelt</span>
      ${btn(subOf(null,stufe),on(!cat&&!wer),`alle <b>${nf(byWer.act+byWer.dec)}</b>`)}
      ${['act','dec'].map(t=>btn(subOf(t,stufe),on(!cat&&wer===t)+(byWer[t]?'':' zero'),`<i class="sw t-${t}"></i>${esc(tonLabel(t))} <b>${nf(byWer[t])}</b>`,tonTip(t))).join('')}
      <a class="tcat out" href="#recherche" data-go="recherche" title="${esc(tonTip('open'))}"><i class="sw t-open"></i>${esc(tonLabel('open'))} <b>${nf(tot.open)}</b> — eigene Seite ›</a></div>
    <div class="filtrow"><span class="fl">Priorität</span>
      ${btn(subOf(wer,null),on(!cat&&!stufe),'alle Stufen')}
      ${STUFEN.map(s=>btn(subOf(wer,s.n),on(!cat&&stufe===s.n)+(byStufe[s.n]?'':' zero'),`${esc(stufeLabel(s.n))} <b>${nf(byStufe[s.n]||0)}</b>`,s.text)).join('')}</div>
    <div class="filtrow top"><span class="fl">Kategorie</span><div class="stgs">${STUFEN.map(s=>{
      const ks=actCats.filter(k=>catStufe(k)===s.n); if(!ks.length) return '';
      return `<span class="stg"><span class="stgl">${esc(String(s.n))} · ${esc(s.name)}</span>${ks.map(k=>{const c=todoCat(k), t=catTon(k);
        return btn(cat===k?'alle':k,on(cat===k)+(byCat[k]?'':' zero'),`<i class="sw t-${t}"></i>${esc(c[1])} <b>${nf(byCat[k]||0)}</b>`,`${tonLabel(t)} · ${catUnit(k,byCat[k]||0)} — ${c[4]}`);}).join('')}</span>`;}).join('')}</div></div>
    <div class="filtrow"><button class="srcbtn" id="todocsv" type="button" title="Die ganze Arbeitsliste als CSV (Semikolon, UTF-8): alle offenen Punkte aller Formulare — auch die grauen der Databank — mit den Spalten «Wer handelt» und «Priorität», unabhängig vom Filter. Die Schutzstufe (ISV), die für alle Felder offen ist, steht nicht darin.">⇩ Alle Punkte als CSV</button></div></div>`;
  h+=`<details class="card todoexpl"><summary><b>Was die Punkte bedeuten und wer sie schliessen kann</b></summary>
    <table class="ft"><thead><tr><th>Punkt</th><th>Wer handelt</th><th>Priorität</th><th>Bedeutung</th></tr></thead><tbody>${actCats.map(k=>{const c=todoCat(k), t=catTon(k);
      return `<tr><td>${tonChip(t,esc(c[1]),null,tonLabel(t))}</td><td class="small">${esc(tonLabel(t))}</td><td class="small nowrap">${esc(stufeLabel(catStufe(k)))}</td><td>${esc(c[4])}</td></tr>`;}).join('')}
    <tr><td>${tonChip('dec','Schutzstufe (ISV) nicht festgelegt',null,tonLabel('dec'))}</td><td class="small">${esc(tonLabel('dec'))}</td><td class="small">alle Datenfelder</td><td>Für kein Datenfeld ist eine ${esc(ISV_TXT)} festgelegt. Das ist eine kantonale Klassifizierungsentscheidung; die Databank setzt bewusst keine Standardwerte.</td></tr></tbody></table>
    <div class="small muted" style="margin-top:6px">Rot = ${esc(tonTip('act'))} · Amber = ${esc(tonTip('dec'))} · Grau = ${esc(tonTip('open'))} Die grauen Punkte stehen unter ${goLink('recherche','','«Recherche der Databank»','inl')}.</div></details>`;
  const filt=cat?'«'+esc(todoCat(cat)[1])+'»':[wer&&'«'+esc(tonLabel(wer))+'»',stufe&&'«'+esc(stufeLabel(stufe))+'»'].filter(Boolean).join(' · ');
  h+=`<div class="regstats"><span class="rstat">Formulare mit Punkten${cat||wer||stufe?' im Filter':''} <b>${nf(nForms)}/${nf(DATA.forms.length)}</b></span>
    <span class="rstat">Dienststellen <b>${nf(Object.keys(groups).length)}</b></span>
    <span class="rstat">Punkte${filt?' '+filt:''} <b>${nf(nItems)}</b></span>
    <span class="rstat" title="Für so viele Formulare ist ein Verfahrens-Ergebnis (Entscheid und Rechtsmittel) modelliert; für die übrigen ist die Rechtsmittelfrage noch nicht erreicht">Verfahren modelliert <b>${nf(nVerf)}/${nf(DATA.forms.length)}</b></span></div>`;
  Object.entries(groups).sort((a,b)=>b[1].n-a[1].n||a[0].localeCompare(b[0],'de')).forEach(([dn,g])=>{
    const du=dstByName[dn];
    const dep=(du&&du.department)||(svcById[g.forms[0].f.service_id]||{}).department||'';
    // the card id slugs the RAW name — older links anchor the same way
    h+=`<div class="card dstcard" id="dst-${dn.replace(/[^A-Za-z0-9]+/g,'-')}"><div class="dsthead"><h4>${dstLink(dn)}</h4>
      <span class="muted small">${esc(dep)}</span>
      <span class="small" style="margin-left:auto">${du&&(du.formulare||[]).length>g.forms.length?`${nf(g.forms.length)} von ${pl(du.formulare.length,'Formular','Formularen')} mit Punkten`:`${pl(g.forms.length,'Formular','Formulare')} mit Punkten`} · ${tonNums(g.byTon,['act','dec'])}</span></div>
      <div class="dstkontakt">${kontaktHtml(kontaktOf(dn))}</div>
      ${showIsv&&(dstAll[dn]||{}).fields?`<div class="dstkontakt dsline" style="margin:2px 0 6px"><i class="sw t-dec"></i><span>Schutzstufe (ISV) für ${pl(dstAll[dn].fields,'Datenfeld','Datenfelder')} in ${pl(dstAll[dn].forms,'Formular','Formularen')} dieser Dienststelle nicht festgelegt — ${esc(tonLabel('dec'))} (gilt für alle Formulare, unabhängig vom Filter)</span></div>`:''}
      <table class="ft"><thead><tr><th>Formular</th><th>Offene Punkte</th></tr></thead><tbody>`;
    g.forms.sort((a,b)=>b.its.reduce((x,i)=>x+i.n,0)-a.its.reduce((x,i)=>x+i.n,0)).forEach(({f,its})=>{
      const svc=svcById[f.service_id];
      h+=`<tr><td><a class="simlink" href="#fields/${encodeURIComponent(f.service_id)}/form-${encodeURIComponent(f.id)}" data-sid="${f.service_id}" data-fid="${f.id}">${esc(f.title)}</a>${svc&&svc.name!==f.title?`<div class="small muted">${esc(svc.name)}</div>`:''}</td>
        <td>${its.map(i=>{const c=todoCat(i.cat), t=itemTon(i);
          return tonChip(t,esc(c[1]),chipN(i),`${tonLabel(t)} · ${stufeLabel(itemStufe(i))}${unitTip(i)} — ${i.detail||c[4]}`,
            ` data-sid="${f.service_id}" data-fid="${f.id}" data-cat="${esc(i.cat)}" data-tipgo="Zur Stelle im Formular ›" tabindex="0"`);}).join(' ')}</td></tr>`;
    });
    h+=`</tbody></table></div>`;
  });
  if(!Object.keys(groups).length) h+='<div class="nores">Keine offenen Punkte in diesem Filter.</div>';
  m.innerHTML=h;
  if(bad) m.insertAdjacentHTML('afterbegin',`<div class="nores">Filter «${esc(String(asked))}» ist auf dieser Seite unbekannt — gezeigt wird ${cat||wer||stufe?'der erkannte Teil':'alles, was Dienststellen und Kanton betrifft'}.</div>`);
  m.querySelectorAll('button.tcat[data-sub]').forEach(c=>c.onclick=()=>{state.sub=c.dataset.sub;render();});
  // a Formular name opens its Formular-Ansicht; a chip opens the segment where the
  // point lives — form-level points the Formular-Ansicht, field-level points the
  // service page scrolled to that Formular's section
  const FORM_LEVEL=new Set(['veraltet','dup','keine-felder','pruefung_faellig']);
  m.querySelectorAll('.simlink[data-fid]').forEach(a=>a.onclick=e=>{
    if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button) return; e.preventDefault();
    state.service=a.dataset.sid;state.tab='fields';state.sub='form-'+a.dataset.fid;render();});
  const openChip=c=>{state.service=c.dataset.sid;state.tab='fields';
    const single=FORM_LEVEL.has(c.dataset.cat), div=!!DIV_SEC(c.dataset.cat);
    // a divergence or naming point opens the Formular at its block «Standard-Divergenzen»
    // (viewFields scrolls to the block itself); a field-level point the service page at
    // the section of that Formular
    state.sub=single?'form-'+c.dataset.fid:div?'form-'+c.dataset.fid+'~div':'felder';render();
    if(single||div) return;
    const t=document.getElementById('fsec-'+c.dataset.fid); if(t){t.scrollIntoView({behavior:MOTION});t.classList.add('flash');setTimeout(()=>t.classList.remove('flash'),1600);}};
  m.querySelectorAll('.tchip[data-fid]').forEach(c=>{c.onclick=()=>openChip(c);});
  wireGo(m);
  const b=document.getElementById('todocsv'); if(b) b.onclick=()=>{
    // the whole list, grey included, Dienststelle by Dienststelle in priority order
    const rows=[];
    DATA.forms.forEach(f=>todoItems(f).forEach(i=>rows.push({dn:dstOf(f),f,i})));
    rows.sort((a,b)=>a.dn.localeCompare(b.dn,'de')||byPrio(a.i,b.i)||String(a.f.title).localeCompare(String(b.f.title),'de'));
    const csv=[['Dienststelle','Departement','Kontakt','Service','Formular','Priorität','Punkt','Wer handelt','Anzahl','Detail']];
    rows.forEach(({dn,f,i})=>{const du=dstByName[dn], svc=svcById[f.service_id];
      csv.push([dn,(du&&du.department)||(svc||{}).department||'',kontaktOf(dn).join(' / '),svc?svc.name:'',f.title,
        stufeLabel(itemStufe(i)),todoCat(i.cat)[1],tonLabel(itemTon(i)),String(i.n),i.detail||'']);});
    const q=v=>'"'+String(v).replace(/"/g,'""')+'"';
    const txt='﻿'+csv.map(r=>r.map(q).join(';')).join('\r\n');
    const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([txt],{type:'text/csv;charset=utf-8'}));
    a.download='handlungsbedarf-alle-punkte.csv'; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),2000);};
}
// ---------- global search over everything the databank holds ----------
let SIDX=null;
function searchIndex(){
  if(SIDX) return SIDX;
  const ix=[]; const lc=s=>(s||'').toString().toLowerCase();
  const formsByLaw={}, formsByArt={};
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>(d.legal_basis||[]).forEach(b=>{
    if(b.law_id==null) return; (formsByLaw[b.law_id]=formsByLaw[b.law_id]||new Set()).add(f);
    (formsByArt[b.law_id+'|'+b.article_no]=formsByArt[b.law_id+'|'+b.article_no]||new Set()).add(f);})));
  const fmLink=f=>({tab:'fields',service:f.service_id,sub:'form-'+f.id,label:f.title});
  DATA.services.forEach(s=>ix.push({t:'Service',label:s.name,sub:[s.dienststelle,s.name_alt?'auch: '+s.name_alt:''].filter(Boolean).join(' · '),
    key:lc(s.name+' '+(s.name_alt||'')+' '+(s.dienststelle||'')),go:{tab:'fields',service:s.id,sub:'felder'}}));
  const recip={}, beil={}, ech={};
  DATA.forms.forEach(f=>{
    const svc=svcById[f.service_id];
    ix.push({t:'Formular',label:f.title,sub:svc?svc.name:'',key:lc(f.title+' '+(f.purpose||'')+' '+(f.kennung||'')),go:fmLink(f)});
    (f.data_fields||[]).forEach(d=>{
      // the key covers the Teilfelder and the eSH codes too: what the sidebar
      // filter finds, the global search must find as well; the hit lands on
      // the Formular's section of the service page, not on the page top
      const ss=(d.subfields||[]).filter(s=>s&&typeof s==='object'&&s.name);
      const key=d.name+' '+(d.definition||'')+' '+(d.ech?d.ech.standard+' '+(d.ech.element||''):'')+' '+(d.esh?d.esh.code+' '+(d.esh.element||''):'')
        +' '+ss.map(s=>s.name+' '+(s.ech?s.ech.standard+' '+(s.ech.element||''):'')+' '+(s.esh?s.esh.code+' '+(s.esh.element||''):'')).join(' ');
      ix.push({t:'Datenfeld',label:d.name,
        sub:f.title+(d.ech&&d.ech.element?' · '+d.ech.standard+' '+d.ech.element:'')+(ss.length?' · Teilfelder: '+ss.slice(0,6).map(s=>s.name).join(', ')+(ss.length>6?' …':''):''),
        key:lc(key),go:{tab:'fields',service:f.service_id,sub:'felder',anchor:'fsec-'+f.id}});
      if(d.ech&&d.ech.standard){const e=ech[d.ech.standard]=ech[d.ech.standard]||{titel:d.ech.standard_titel||'',n:0};e.n++;}
    });
    (f.disclosures||[]).forEach(x=>{const e=recip[x.empfaenger]=recip[x.empfaenger]||{forms:new Set(),arts:new Set()};e.forms.add(f);e.arts.add(`${x.short_title} ${x.article_no}`);});
    (f.beilagen||[]).forEach(b=>{const e=beil[b.bezeichnung]=beil[b.bezeichnung]||{forms:new Set(),halter:b.halter};e.forms.add(f);});
  });
  Object.entries(recip).forEach(([n,e])=>ix.push({t:'Empfänger',label:n,sub:`Bekanntgabe aus ${pl(e.forms.size,'Formular','Formularen')} · ${[...e.arts].slice(0,3).join(', ')}`,key:lc(n),links:[...e.forms].slice(0,6).map(fmLink)}));
  Object.entries(beil).forEach(([n,e])=>ix.push({t:'Beilage',label:n,sub:`verlangt in ${pl(e.forms.size,'Formular','Formularen')}${e.halter?' · Halter: '+lab(HALTER_DE,e.halter):''}`,key:lc(n),links:[...e.forms].slice(0,6).map(fmLink)}));
  Object.entries(ech).forEach(([c,e])=>ix.push({t:'eCH-Standard',label:c,sub:`${e.titel} · ${pl(e.n,'Datenfeld','Datenfelder')}`,key:lc(c+' '+e.titel),go:{tab:'katalog',service:'all',sub:'felder'}}));
  (DATA.esh_katalog||[]).forEach(k=>ix.push({t:'eSH-Entwurf',label:k.code+' — '+k.titel,sub:`${pl(k.n_live||0,'Datenpunkt','Datenpunkte')} · kantonaler Entwurf, nicht offiziell`,
    key:lc(k.code+' '+k.titel+' '+(k.beschreibung||'')),go:{tab:'esh',service:'all',sub:'felder',anchor:'esh-'+k.code}}));
  const ruleLaws=new Set((DATA.datenhandhabung||[]).map(r=>r.law_id));
  const ruleArts=new Set((DATA.datenhandhabung||[]).map(r=>r.law_id+'|'+r.article_no));
  // viewRules renders one card per (law, scope) with id 'law-<id>-<scope>';
  // an anchor without the scope matches nothing, so remember a real scope
  const ruleScope={}; (DATA.datenhandhabung||[]).forEach(r=>{if(!(r.law_id in ruleScope))ruleScope[r.law_id]=r.scope;});
  // placeholder laws («Im Formular zitiert: …», last_checked 'zitiert (unverifiziert)')
  // are no longer exported; the filter keeps them out should a re-run reintroduce them
  (DATA.laws||[]).filter(l=>l.last_checked!=='zitiert (unverifiziert)').forEach(l=>{
    const fms=[...(formsByLaw[l.id]||[])];
    const jl=lab(JUR_DE,l.jurisdiction_level);
    const nr=refNo(l.jurisdiction_level,l.sr_number,l.cantonal_ref);
    const base={sub:`${jl}${nr?' · '+nr:''}${fms.length?' · von Feldern in '+pl(fms.length,'Formular','Formularen')+' zitiert':''}${ruleLaws.has(l.id)?' · Regeln im Tab «Datenhandhabung»':''}${!ruleLaws.has(l.id)&&!fms.length?' · kein Datenfeld zitiert dieses Gesetz, keine Regel im Tab «Datenhandhabung» — kein Sprungziel':''}`,
      go:ruleLaws.has(l.id)?{tab:'rules',service:'all',sub:'felder',anchor:'law-'+l.id+'-'+ruleScope[l.id]}:null,links:fms.slice(0,6).map(f=>({tab:'fields',service:f.service_id,sub:'gesetze',label:f.title}))};
    ix.push(Object.assign({t:'Gesetz',label:(l.short_title?l.short_title+' — ':'')+l.title,key:lc(l.title+' '+(l.short_title||'')+' '+(l.sr_number||'')+' '+(l.cantonal_ref||''))},base));
    (l.articles||[]).forEach(a=>{const fa=[...(formsByArt[l.id+'|'+a.article_no]||[])];
      if(!a.heading&&!fa.length&&!ruleArts.has(l.id+'|'+a.article_no)) return;
      ix.push({t:'Artikel',label:`${artLabel(a.article_no)} ${l.short_title||l.title}${a.heading?' — '+a.heading:''}`,
        sub:`${jl}${nr?' · '+nr:''}${fa.length?' · zitiert in '+pl(fa.length,'Formular','Formularen'):''}${!fa.length&&!base.go?(fms.length?' · dieser Artikel wird von keinem Datenfeld zitiert — Links: Formulare, deren Felder das Gesetz zitieren':' · kein Datenfeld zitiert diesen Artikel — kein Sprungziel'):''}`,key:lc(artLabel(a.article_no)+' '+a.article_no+' '+(a.heading||'')+' '+(l.short_title||'')+' '+l.title),
        go:base.go,links:(fa.length||base.go?fa:fms).slice(0,6).map(f=>({tab:'fields',service:f.service_id,sub:'gesetze',label:f.title}))});});
  });
  (DATA.datenhandhabung||[]).forEach(r=>ix.push({t:'Regel',label:r.summary,sub:`${r.short_title||r.law_title} ${artLabel(r.article_no)} · ${lab(ASPECT,r.aspect)} · ${lab(SCOPE_DE,r.scope)}`,
    key:lc(r.summary+' '+(r.quote||'')+' '+(r.short_title||'')+' '+r.article_no),go:{tab:'rules',service:'all',sub:'felder',anchor:`law-${r.law_id}-${r.scope}`}}));
  (DATA.themenkatalog||[]).filter(t=>t.n_services).forEach(t=>ix.push({t:'Themengruppe',label:t.gruppe,
    sub:`Themengruppe eCH-0049 (Tab «Lebenslagen») · ${lab(KAT_DE,t.katalog)} · ${t.bereich} · ${pl(t.n_services,'Service','Services')}${t.n_ueberschneidungen?' · '+pl(t.n_ueberschneidungen,'Überschneidung','Überschneidungen'):''}`,
    key:lc(t.gruppe+' '+t.bereich+' '+lab(KAT_DE,t.katalog)),go:{tab:'lebenslagen',service:'all',sub:'g-'+t.id}}));
  // a Begriff hit carries its term (prefilled filter) and its card anchor, so it
  // is visible even beyond the list's 60-row cap
  (DATA.begriffe||[]).forEach(b=>ix.push({t:'Begriff',label:b.vorschlag,
    sub:`${b.standard} ${b.element} · ${pl(b.labels.filter(l=>l.klasse==='variante').length,'Bezeichnung','Bezeichnungen')} anzugleichen`,
    key:lc(b.vorschlag+' '+b.labels.map(l=>l.label).join(' ')+' '+b.element),go:{tab:'begriffe',service:'all',sub:'alle',q:b.vorschlag,anchor:'beg-'+b.element_id}}));
  // a Dienststelle hit opens its own page (the briefing); its contact is drawn by the one
  // contact helper (viewSearch)
  DST.forEach(u=>{
    const o=u.offen||{}, nF=(u.formulare||[]).length, k=u.kontakt||[];
    ix.push({t:'Dienststelle',label:u.name,sub:(u.department||'')
      +(nF?` · ${pl(nF,'Formular','Formulare')} · offene Punkte: ${nf(o.act)} ${tonLabel('act')}, ${nf(o.dec)} ${tonLabel('dec')}, ${nf(o.open)} ${tonLabel('open')}`:' · kein Formular in der Databank'),
      kontakt:k, key:lc(u.name+' '+(u.department||'')),go:{tab:'dienststellen',service:'all',sub:u.slug}});});
  // the Gestaltung der Formulare: the page, its groups, its Merkmale and the canton's open decisions
  if(GEST){
    const gg=sub=>({tab:'gestaltung',service:'all',sub});
    ix.push({t:'Gestaltung',label:'Gestaltung der Formulare',sub:GGRP.map(g=>g.label).join(' · '),
      key:lc('Gestaltung der Formulare Erscheinungsbild Aussehen '+GGRP.map(g=>g.label+' '+g.frage).join(' ')),go:gg('felder')});
    GGRP.forEach(g=>ix.push({t:'Gestaltung',label:g.label,sub:g.frage,key:lc('Gestaltung '+g.label+' '+g.frage),go:gg(g.key)}));
    (GEST.merkmale||[]).forEach(x=>ix.push({t:'Gestaltung',label:x.label,sub:`${lab(GL.gruppe,x.gruppe)} · ${x.frage}`,
      key:lc('Gestaltung '+x.label+' '+x.frage+' '+lab(GL.gruppe,x.gruppe)),go:gg('m-'+x.key)}));
    (GEST.entscheide||[]).forEach(e=>ix.push({t:'Gestaltung',label:e.label,sub:'Gestaltung der Formulare · ohne klare Praxis oder Regel — der Kanton legt fest',
      key:lc('Gestaltung Festlegung Kanton Praxis '+e.label),go:gg('e-'+e.key)}));
  }
  // Datenmodell & Once-Only: the pages and their sections, the roles, the concepts, the registers
  const dmg=(tab,sub)=>({tab,service:'all',sub:sub||'felder'});
  if(PAR||KONZ||WIRK){
    ix.push({t:'Datenmodell',label:'Datenmodell',sub:'Wessen Angabe · Eine Angabe — ein Element · Dauerhafte Kennungen · Gesetzesstand · Wirkung einer Änderung',
      key:lc('Datenmodell Parteien Rollen Konzepte Kennungen Exportvertrag JSON Schema Gesetzesstand Fassung Wirkung Änderung'),go:dmg('datenmodell')});
    [['parteien','Wessen Angabe? — Parteien und Rollen','Partei Rolle unklar Stichprobe Zweitprüfung'],['konzepte','Eine Angabe — ein Element','Konzept Vorschlag Element Praxis'],
     ['kennungen','Dauerhafte Kennungen','Kennung Exportvertrag Version JSON Schema'],['gesetzesstand','Gesetzesstand','Fassung Stand neuere Fassung in Kraft'],
     ['wirkung','Wirkung einer Änderung','Gesetz Artikel betrifft Formulare Datenpunkte']].forEach(([k,l,w])=>{
      if((k==='parteien'&&!PAR)||(k==='konzepte'&&!KONZ)||((k==='gesetzesstand'||k==='wirkung')&&!WIRK)) return;
      ix.push({t:'Datenmodell',label:l,sub:'Seite «Datenmodell»',key:lc(l+' '+w),go:dmg('datenmodell',k)});});
  }
  (PAR?PAR.rollen:[]).forEach(r=>{const x=((DM.parteien||{}).rollen||{})[r.code]||{};
    ix.push({t:'Rolle',label:r.label,sub:`${entRolle(r.entitaet)} · ${pl(x.parteien||0,'Partei','Parteien')} in ${pl(x.formulare||0,'Formular','Formularen')} · Vorschlag der Databank — ${r.erklaerung}`,
      key:lc('Rolle Partei '+r.label+' '+r.erklaerung),go:dmg('datenmodell','parteien')});});
  ((KONZ&&KONZ.konzepte)||[]).forEach(k=>ix.push({t:'Konzept',label:k.label,
    sub:`${k.gruppe} · ${pl(k.n_punkte,'Datenpunkt','Datenpunkte')} in ${pl(k.n_formulare,'Formular','Formularen')} · ${(k.mitglieder||[]).slice(0,4).map(e=>e.standard+' '+e.element).join(', ')}${(k.mitglieder||[]).length>4?' …':''}`,
    key:lc('Konzept '+k.label+' '+k.gruppe+' '+(k.mitglieder||[]).map(e=>e.standard+' '+e.element).join(' ')),go:dmg('datenmodell','k-'+k.code)}));
  if(REG){
    ix.push({t:'Register',label:'Was Register schon wissen',sub:'Register, Beilagen, gesparte Zeit (Modellschätzung), offene Rechtsfragen',
      key:lc('Was Register schon wissen Once-Only Register Vorbefüllung vorbefüllbar Beilagen Zeit Zugriff'),go:dmg('onceonly')});
    Object.values(REG_BY).forEach(k=>ix.push({t:'Register',label:k.name,sub:`${lab(DML.register_ebene,k.ebene)} · ${k.inhaber||''} · ${pl((k.zahlen||{}).bestaetigt||0,'Angabe','Angaben')} der Formulare`,
      key:lc('Register '+k.name+' '+(k.inhaber||'')+' '+(k.inhalt||'')+' '+(k.schluessel||'')),go:dmg('onceonly','r-'+k.code)}));
  }
  // the glossary of «Methode & Quellen»: a term is found by its word and by its explanation
  GLOSSAR.forEach(g=>ix.push({t:'Glossar',label:g.wort,sub:g.text,key:lc(g.wort+' '+g.text),
    go:{tab:'methode',service:'all',sub:'felder',anchor:'gl-'+g.id}}));
  // byte-identical entries never appear twice
  const seen=new Set();
  return SIDX=ix.filter(e=>{const k=e.t+'|'+e.label+'|'+(e.sub||'')+'|'+JSON.stringify(e.go||null)+'|'+JSON.stringify(e.links||[])+'|'+JSON.stringify(e.kontakt||null); if(seen.has(k)) return false; seen.add(k); return true;});
}
// highlight BEFORE escaping: split the raw text on the tokens, escape each piece,
// wrap only the matches — a query like «amp» or «lt» can never break an entity
function hl(text,toks){
  const T=toks.filter(Boolean).map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  const s=text==null?'':String(text);
  if(!T.length) return esc(s);
  const re=new RegExp('('+T.join('|')+')','ig');
  return s.split(re).map((p,i)=>i%2?`<mark class="hl">${esc(p)}</mark>`:esc(p)).join('');
}
// the address of a search target, as the hash writes it
function hrefOf(g){
  if(!g) return '';
  const svc=g.tab==='fields'?String(g.service==null?'all':g.service):'all', sub=g.sub||'felder';
  return '#'+g.tab+(svc!=='all'||sub!=='felder'?'/'+encodeURIComponent(svc):'')+(sub!=='felder'?'/'+sub:'');
}
function goTo(g){
  if(!g) return;
  // ids are strings everywhere in state (hash segments, dataset values); a
  // numeric id from the index would never match the sidebar's String(s.id)
  state.tab=g.tab; state.service=g.service==null?'all':String(g.service); state.sub=g.sub||'felder'; state.begq=g.q||'';
  closeNav(); render();
  if(g.anchor){const t=document.getElementById(g.anchor);
    if(t){t.scrollIntoView({behavior:MOTION});t.classList.add('flash');setTimeout(()=>t.classList.remove('flash'),1600);}
    else {const m=document.getElementById('main'); if(m) m.insertAdjacentHTML('afterbegin',`<div class="nores">Der gesuchte Eintrag wird auf dieser Seite nicht dargestellt (Anker «${esc(g.anchor)}» nicht gefunden) — die Seite zeigt den Gesamtbestand.</div>`);}}
}
function viewSearch(){
  const m=document.getElementById('main');
  let q=''; try{q=decodeURIComponent(state.sub||'');}catch(e){q=state.sub||'';}
  if(q==='felder') q='';
  // never rewrite the box while the reader is typing after a space: a debounce
  // render must not strip the trailing blank
  const inp=document.getElementById('gsearch'); if(inp&&inp.value.trim()!==q) inp.value=q;
  const toks=q.toLowerCase().split(/\s+/).filter(t=>t.length>=2);
  let h=pageHead('Suche · Services, Formulare, Datenfelder, Recht, Standards, Dienststellen',
    q?'Treffer für «'+esc(q)+'» — alle Wörter müssen vorkommen, Reihenfolge und Gross-/Kleinschreibung egal.'
     :'Ein Suchfeld über Services, Formulare, Datenfelder, Gesetze, Regeln, Standards und Dienststellen.',
    'Ein Suchfeld über Services, Formulare (auch nach ihrer Kennung), Datenfelder (inkl. Teilfelder), Gesetze und Artikel, Datenhandhabungs-Regeln, Empfänger, Beilagen, Themengruppen (Tab «Lebenslagen»), Begriffe, eCH-Standards, eSH-Entwürfe, Dienststellen, die Rollen, Konzepte und Register und die Begriffe des Glossars.',
    'Durchsucht wird der Export der Databank, wie er in dieser Seite steckt — nichts Externes. Alle Wörter müssen vorkommen (Reihenfolge egal, Gross/Klein egal). Der Datenkatalog (1 Zeile je Attribut) ist nicht separat indexiert; seine Daten sind über die Datenfelder und eCH-Standards erreichbar.',
    'Ein Treffer mit Ziel springt an die Stelle, an der das Objekt in der Databank lebt: Service-Seite (Formular-Abschnitt), Formular-Ansicht, Regel-Karte, Begriffs-Karte, eSH-Karte oder die Seite der Dienststelle; Einträge ohne Ziel sagen es.');
  if(!toks.length){m.innerHTML=h+'<div class="nores">Mindestens ein Wort mit zwei Zeichen eingeben — z. B. «AHV-Nummer», «Art. 17b», «Steuerverwaltung», «Strafregisterauszug», «eCH-0044», «eSH-0001».</div>';return;}
  // rank: whole-word matches (so «17b» prefers Art. 17b over Art. 317bis), then label matches
  const wb=(s,t)=>{const i=s.indexOf(t);return i>=0&&(i===0||!/[a-z0-9äöü]/.test(s[i-1]));};
  const hits=searchIndex().filter(e=>toks.every(t=>e.key.includes(t)))
    .map(e=>{const L=e.label.toLowerCase();return {e,sc:(L.startsWith(toks[0])?2:0)+(toks.every(t=>L.includes(t))?1:0)+(toks.every(t=>wb(e.key,t))?3:0)};})
    .sort((a,b)=>b.sc-a.sc);
  const order=['Glossar','Themengruppe','Service','Formular','Datenfeld','Begriff','Gesetz','Artikel','Regel','Empfänger','Beilage','eCH-Standard','eSH-Entwurf','Dienststelle','Gestaltung','Datenmodell','Rolle','Konzept','Register'];
  const byT={}; hits.forEach(x=>(byT[x.e.t]=byT[x.e.t]||[]).push(x.e));
  h+=`<div class="regstats">${order.filter(t=>byT[t]).map(t=>`<span class="rstat">${esc(t)} <b>${byT[t].length}</b></span>`).join('')}${hits.length?'':'<span class="rstat">keine Treffer</span>'}</div>`;
  if(!hits.length&&toks.length>1) h+=`<div class="nores">Alle Wörter müssen im selben Eintrag vorkommen. Mit einem einzelnen Begriff suchen (${toks.map(t=>`<a class="simlink" data-q="${esc(t)}">${esc(t)}</a>`).join(' · ')}) oder die Schreibweise des Gesetzestexts verwenden — Fristen stehen dort meist als Zahlwort («zehn Jahre»), nicht als Ziffer.</div>`;
  // only the first ten hits of a group are built — a common word start matches thousands;
  // «weitere N anzeigen» builds the rest of that group when the reader asks for it
  const FIRST=10, linkStore=[], groups={};
  const row=(e,t)=>{const li=linkStore.push(e)-1;
    return `<div class="srow"><span class="stype">${esc(t)}</span><div style="flex:1">
        ${e.go?`<a class="slink" data-li="${li}" href="${esc(hrefOf(e.go))}">${hl(e.label,toks)}</a>`:`<div>${hl(e.label,toks)}</div>`}
        ${e.sub?`<div class="small muted">${hl(e.sub,toks)}</div>`:''}
        ${e.kontakt?`<div class="small muted">${kontaktHtml(e.kontakt)}</div>`:''}
        ${(e.links||[]).length?`<div class="small">→ ${e.links.map((g,k)=>`<a class="simlink" data-li="${li}" data-k="${k}" href="${esc(hrefOf(g))}">${esc(g.label)}</a>`).join(' · ')}</div>`:''}</div></div>`;};
  let gi=0;
  order.forEach(t=>{const L=byT[t]; if(!L) return; const id='sg'+(gi++); groups[id]={t,L};
    h+=`<div class="card sres"><div class="dvsub">${esc(t)} · ${nf(L.length)}</div>${L.slice(0,FIRST).map(e=>row(e,t)).join('')}`;
    if(L.length>FIRST) h+=`<a class="simlink small" data-showmore="${id}">weitere ${nf(L.length-FIRST)} anzeigen</a>`;
    h+=`</div>`;});
  m.innerHTML=h;
  m.querySelectorAll('.simlink[data-q]').forEach(a=>a.onclick=()=>{state.sub=encodeURIComponent(a.dataset.q);render();});
  const plain=e=>!(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button);
  const wire=root=>{
    root.querySelectorAll('a.slink').forEach(a=>a.onclick=e=>{if(!plain(e)) return; e.preventDefault(); goTo(linkStore[+a.dataset.li].go);});
    root.querySelectorAll('.simlink[data-k]').forEach(a=>a.onclick=e=>{if(!plain(e)) return; e.preventDefault(); goTo(linkStore[+a.dataset.li].links[+a.dataset.k]);});};
  wire(m);
  m.querySelectorAll('[data-showmore]').forEach(a=>a.onclick=()=>{const g=groups[a.dataset.showmore], card=a.parentElement;
    a.insertAdjacentHTML('beforebegin',g.L.slice(FIRST).map(e=>row(e,g.t)).join(''));
    // the group is marked as shown in full: a return by Back/Forward opens it again
    card.setAttribute('data-shown',a.dataset.showmore); a.remove(); wire(card);});
}
// ---------- Datenfluss: who passes data to whom, from the article-backed disclosures ----------
function viewDatenfluss(){
  const m=document.getElementById('main');
  // edges: (sending Dienststelle, recipient, mode) with the forms and articles behind them
  const edges={}, senders={}, recips={}; let nFormsWith=0;
  DATA.forms.forEach(f=>{const ds=f.disclosures||[]; if(!ds.length) return; nFormsWith++;
    const s=dstOf(f); senders[s]=(senders[s]||0)+ds.length;
    ds.forEach(d=>{const k=s+'|'+d.empfaenger+'|'+(d.mode||''); recips[d.empfaenger]=(recips[d.empfaenger]||0)+1;
      const e=edges[k]=edges[k]||{s,r:d.empfaenger,mode:d.mode,forms:new Set(),arts:new Set()};
      e.forms.add(f); if(d.article_no) e.arts.add(`${d.short_title||''} ${d.article_no}`.trim());});});
  const E=Object.values(edges); const S=Object.entries(senders).sort((a,b)=>b[1]-a[1]).map(x=>x[0]);
  const R=Object.entries(recips).sort((a,b)=>b[1]-a[1]).map(x=>x[0]);
  const nSys=E.filter(e=>e.mode==='systematisch').length, nAnf=E.filter(e=>e.mode==='auf_anfrage').length;
  let h=pageHead('Datenfluss · Wer gibt wem Personendaten weiter',
    'Wer welche Personendaten an wen weitergibt — nur Bekanntgaben, die ein Artikel belegt.',
    'Die belegten Bekanntgaben aus allen Formularen, verdichtet zu Verbindungen: sendende Dienststelle → Empfänger, je mit Modus, Formularen und dem Artikel, der die Weitergabe erlaubt.',
    `Quelle sind die ${nf(DATA.forms.reduce((a,f)=>a+(f.disclosures||[]).length,0))} Empfänger-Einträge des Verzeichnisses (nur mit Artikel-Beleg geladen). ${nFormsWith} von ${DATA.forms.length} Formularen haben dokumentierte Bekanntgaben — für die übrigen ist die Weitergabe noch nicht erfasst, was nicht heisst, dass es keine gibt (siehe Handlungsbedarf).`,
    '«systematisch» = regelmässige Meldung von Gesetzes wegen (z. B. an die Zentrale Ausgleichsstelle); «auf Anfrage» = Amtshilfe auf Ersuchen im Einzelfall. Linienstärke = Anzahl Formulare. Klick auf eine Dienststelle oder einen Empfänger hebt die Verbindungen hervor; Klick auf eine Linie listet die Formulare.');
  h+=`<div class="regstats"><span class="rstat">Dienststellen mit Bekanntgaben <b>${S.length}</b></span>
    <span class="rstat">Empfänger <b>${R.length}</b></span><span class="rstat">Verbindungen <b>${E.length}</b></span>
    <span class="rstat">davon <span class="mkline"></span> systematisch <b>${nSys}</b> · <span class="mkline dash"></span> auf Anfrage <b>${nAnf}</b></span>
    <span class="rstat">Formulare mit belegter Bekanntgabe <b>${nFormsWith}/${DATA.forms.length}</b></span></div>`;
  if(!E.length){m.innerHTML=h+'<div class="nores">Keine belegten Bekanntgaben geladen.</div>';return;}
  // bipartite diagram: senders left, recipients right
  const rowH=22, top=28, W=980, H=top+Math.max(S.length,R.length)*rowH+20, xL=300, xR=W-320;
  const yS=Object.fromEntries(S.map((s,i)=>[s,top+i*rowH+rowH/2])), yR=Object.fromEntries(R.map((r,i)=>[r,top+i*rowH+rowH/2]));
  const short=(t,n)=>t.length>n?t.slice(0,n-1)+'…':t;
  let svg=`<svg class="flowsvg" data-noact viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Datenfluss-Diagramm">
    <text x="${xL}" y="16" text-anchor="end" class="flowhd">Dienststelle (gibt bekannt)</text>
    <text x="${xR}" y="16" class="flowhd">Empfänger</text>`;
  E.forEach((e,i)=>{const y1=yS[e.s], y2=yR[e.r], w=1+Math.log2(e.forms.size);
    svg+=`<path class="fe ${e.mode||'unbekannt'}" data-i="${i}" data-s="${esc(e.s)}" data-r="${esc(e.r)}" d="M${xL+6},${y1} C${(xL+xR)/2},${y1} ${(xL+xR)/2},${y2} ${xR-6},${y2}" stroke-width="${w.toFixed(1)}" fill="none"><title>${esc(e.s)} → ${esc(e.r)} · ${e.mode?lab(MODE_DE,e.mode):'Modus unbekannt'} · ${pl(e.forms.size,'Formular','Formulare')} · ${esc([...e.arts].join(', '))}</title></path>`;});
  S.forEach(s=>{svg+=`<text class="fn" data-s="${esc(s)}" x="${xL}" y="${yS[s]+4}" text-anchor="end"><title>${esc(s)} · ${pl(senders[s],'Bekanntgabe-Eintrag','Bekanntgabe-Einträge')}</title>${esc(short(s,44))}</text>`;});
  R.forEach(r=>{svg+=`<text class="fn" data-r="${esc(r)}" x="${xR}" y="${yR[r]+4}"><title>${esc(r)} · aus ${pl(recips[r],'Formular','Formularen')}</title>${esc(short(r,48))}</text>`;});
  svg+='</svg>';
  h+=`<div class="card"><div class="flowleg"><span><i class="fl sys"></i> systematisch</span><span><i class="fl anf"></i> auf Anfrage</span><span class="muted small">Linienstärke = Anzahl Formulare · Reihenfolge = Anzahl Einträge</span></div>${svg}
    <div id="flowdetail" class="small muted" style="margin-top:8px">Klick auf eine Linie zeigt hier die Formulare und Artikel.</div></div>`;
  // the same information as a sortable-by-eye table
  h+=`<div class="card"><div class="dvsub">Alle Verbindungen — je Dienststelle, Empfänger, Modus</div>
    <div class="tscroll"><table class="ft fit"><thead><tr><th>Dienststelle</th><th>Empfänger</th><th>Modus</th><th>Formulare</th><th>Erlaubnisnorm</th></tr></thead><tbody>`;
  E.slice().sort((a,b)=>a.s.localeCompare(b.s)||b.forms.size-a.forms.size).forEach(e=>{
    h+=`<tr><td>${esc(e.s)}</td><td class="hy">${esc(e.r)}</td><td>${mkBadge(esc(e.mode?lab(MODE_DE,e.mode):'Modus unbekannt'),e.mode==='systematisch'?'regelmässige Meldung von Gesetzes wegen — ein Kennzeichen, keine Bewertung':e.mode==='auf_anfrage'?'Amtshilfe auf Ersuchen im Einzelfall — ein Kennzeichen, keine Bewertung':'',e.mode==='auf_anfrage'?'mk-open':'')}</td>
      <td class="small hy">${[...e.forms].slice(0,4).map(f=>formLink(f.service_id,f.id,esc(short(f.title,50)),'simlink')).join('<br>')}${e.forms.size>4?`<div class="muted">… ${pl(e.forms.size-4,'weiteres','weitere')}</div>`:''}</td>
      <td class="small hy">${esc([...e.arts].join(' · '))||stBadge(catTon('empf'),'ohne Artikel','Für diese Bekanntgabe ist noch kein Artikel dokumentiert')}</td></tr>`;});
  h+=`</tbody></table></div></div>`;
  m.innerHTML=h;
  wireGo(m);
  const svgEl=m.querySelector('.flowsvg'); const det=document.getElementById('flowdetail');
  const focus=(pred)=>{svgEl.querySelectorAll('.fe').forEach(p=>p.classList.toggle('dim',!pred(p)));};
  svgEl.querySelectorAll('.fn').forEach(t=>t.onclick=()=>{const s=t.dataset.s, r=t.dataset.r;
    focus(p=>s?p.dataset.s===s:p.dataset.r===r);
    const list=E.filter(e=>s?e.s===s:e.r===r);
    det.innerHTML=`<b>${esc(s||r)}</b> — ${pl(list.length,'Verbindung','Verbindungen')}: `+list.map(e=>`${esc(s?e.r:e.s)} (${e.mode?lab(MODE_DE,e.mode):'Modus unbekannt'}, ${e.forms.size})`).join(' · ');});
  svgEl.querySelectorAll('.fe').forEach(p=>p.onclick=()=>{const e=E[+p.dataset.i]; focus(q=>q===p);
    det.innerHTML=`<b>${esc(e.s)} → ${esc(e.r)}</b> · ${e.mode?lab(MODE_DE,e.mode):'Modus unbekannt'} · Erlaubnisnorm: ${esc([...e.arts].join(', '))||'—'}<br>`+
      [...e.forms].map(f=>formLink(f.service_id,f.id,esc(f.title),'simlink')).join(' · ');
    wireGo(det);});
  svgEl.onclick=(ev)=>{if(ev.target===svgEl){focus(()=>true);det.textContent='Klick auf eine Linie zeigt hier die Formulare und Artikel.';}};
}
// ---------- Bürgersicht: the Datentresor seen from one (synthetic) person's side ----------
function viewBuerger(){
  const m=document.getElementById('main');
  const B=DATA.buergersicht||{personen:[]}; const P=B.personen||[];
  let h=`<div class="band werk" role="note"><b>Werkstatt · Prototyp</b>Alle Personendaten synthetisch; zeigt, wie der Kanton speichern könnte, nicht den heutigen Stand.`
      +`<span class="small">${esc(B.hinweis||'keine realen Personen')}${B.verschluesselung?' · Verschlüsselung: '+esc(B.verschluesselung):''}</span></div>`
    +pageHead('Bürgersicht · Was der Kanton über eine Person speichern würde',
    'Wie eine Auskunft aussähe, wenn der Kanton jede Angabe einmal speichert und später wiederverwendet — an erfundenen Personen gezeigt.',
    'Die Auskunft, wie sie der Datentresor aus seinen Tabellen beantwortet: je Fall, welche Daten neu erhoben und welche aus früheren Fällen wiederverwendet wurden, mit Erhebungsgrundlage, Löschdatum, Belegen und jeder protokollierten Bekanntgabe.',
    'Quelle ist datentresor.db (View v_auskunft, Once-Only-Ledger, Beleg- und Zugriffsprotokoll) — <b>alle Personen und Werte sind synthetisch erzeugt</b>. Verschlüsselte Werte verlassen den Tresor nicht und erscheinen hier als «verschlüsselt». Gezeigt werden die drei Personen mit den meisten beteiligten Dienststellen.',
    'So sieht Once-Only aus der Sicht der betroffenen Person aus: eine Angabe wird einmal erhoben, spätere Fälle verweisen darauf. Jede Zeile trägt die Grundlage, auf der sie gespeichert wurde — «zu ermitteln» bleibt sichtbar, nicht kaschiert.');
  if(!P.length){m.innerHTML=h+'<div class="nores">Kein Datentresor-Export vorhanden (scripts/build_datentresor.py, dann export_json.py).</div>';return;}
  const asked=state.sub; let pi=parseInt(state.sub,10);
  const badSub=!(pi>=0&&pi<P.length)&&state.sub!=='felder'; if(!(pi>=0&&pi<P.length)) pi=0; state.sub=String(pi);
  h+=`<div class="todocats">${P.map((p,i)=>`<span class="tcat${i===pi?' on':''}" data-pi="${i}">${esc(p.vorname)} ${esc(p.name)} <b>${pl(p.faelle.length,'Fall','Fälle')}</b></span>`).join('')}</div>`;
  const p=P[pi], st=p.statistik||{}; const dsts=new Set(p.faelle.map(f=>f.dienststelle));
  const formOf=id=>DATA.forms.find(f=>f.id===id);
  h+=`<div class="card"><div class="dsthead"><h4>${esc(p.vorname)} ${esc(p.name)}</h4><span class="muted small">geb. ${esc(fmtDate(p.geburtsdatum))} · ${esc(p.plz||'')} ${esc(p.ort||'')} · AHVN13 ${esc(p.ahvn13||'')} (synthetisch)</span></div>
    <div class="regstats"><span class="rstat">Fälle <b>${p.faelle.length}</b></span><span class="rstat">Dienststellen <b>${dsts.size}</b></span>
      <span class="rstat">gespeicherte Datenpunkte <b>${st.datenpunkte||0}</b></span><span class="rstat">davon verschlüsselt <b>${st.verschluesselt||0}</b></span>
      <span class="rstat">mit Artikel <b>${st.mit_artikel||0}</b></span><span class="rstat">mit Einwilligung <b>${st.mit_einwilligung||0}</b></span>
      <span class="rstat">Once-Only wiederverwendet <b>${st.wiederverwendet||0}</b></span></div>
    <div class="small muted">Wiederverwendet = ein späterer Fall hat die Angabe nicht neu erhoben, sondern auf den bestehenden Datenpunkt verwiesen. «mit Artikel» zählt Datenpunkte mit belegter Erhebungsnorm; der Rest ist aufgabennotwendig, per Einwilligung oder noch «zu ermitteln».</div></div>`;
  p.faelle.forEach(f=>{const fm=formOf(f.form_id);
    h+=`<div class="card"><div class="dsthead"><h4>${esc(fmtDate(f.eingereicht))} · ${fm?formLink(fm.service_id,fm.id,esc(f.formular),'simlink'):esc(f.formular)}</h4>
      <span class="muted small">${esc(f.dienststelle||'')} · Entscheid: ${esc(f.entscheid?lab(OUTCOME_DE,f.entscheid):'—')}${f.abgeschlossen?' · abgeschlossen '+esc(fmtDate(f.abgeschlossen)):''}</span></div>
      <div class="small" style="margin:4px 0 8px">neu erhoben <b>${f.neu.length}</b> · wiederverwendet <b>${f.wiederverwendet.length}</b> · Belege <b>${f.belege.length}</b> · Bekanntgaben <b>${f.bekanntgaben.length}</b> · Lesezugriffe protokolliert <b>${f.lesezugriffe}</b></div>`;
    if(f.neu.length){h+=`<details${f===p.faelle[0]?' open':''}><summary class="small">Neu erhobene Datenpunkte (${f.neu.length})</summary><div class="tscroll"><table class="ft fit"><thead><tr><th>Attribut</th><th>Standard</th><th>Wert</th><th>Erhebungsgrundlage</th><th>Löschdatum</th></tr></thead><tbody>`;
      f.neu.forEach(d=>{h+=`<tr><td>${esc(d.attribut)}${d.sensitive?` <span class="badge b-sens" title="besonders schützenswert: ${esc(lab(HSENS,d.sensitive))}">⛨</span>`:''}</td>
        <td class="small">${d.ech_element?`${esc(d.ech_standard)} <span class="brk">${esc(d.ech_element)}</span>${d.ech_datatype?` <span class="edt">⟨${esc(d.ech_datatype)}⟩</span>`:''}`:'<span class="muted">—</span>'}</td>
        <td class="small brk">${d.verschluesselt?'<span class="badge b-sens" title="AES-256-GCM; nur mit dem Schlüssel ausserhalb der DB lesbar">verschlüsselt</span>':esc(d.wert||'')}</td>
        <td class="small hy">${d.einwilligung?mkBadge('Einwilligung','Erhebungsgrundlage: Einwilligung der Person — ein Kennzeichen, keine Bewertung')+' ':''}${esc(d.grundlage||'')}</td><td class="small">${esc(fmtDate(d.loeschdatum))}</td></tr>`;});
      h+=`</tbody></table></div></details>`;}
    if(f.wiederverwendet.length){h+=`<details><summary class="small">Wiederverwendet statt neu erhoben (${f.wiederverwendet.length})</summary><div class="small">${f.wiederverwendet.map(w=>`<div><span class="regc" title="Once-Only: aus einem früheren Fall übernommen">↺</span> <b>${esc(w.attribut)}</b> — erhoben ${esc(fmtDate(w.erhoben_am))} für «${esc(w.herkunft)}» (${esc(w.herkunft_dst||'')})</div>`).join('')}</div></details>`;}
    if(f.belege.length){h+=`<details><summary class="small">Belege (${f.belege.length})</summary><div class="small">${f.belege.map(b=>`<div>${b.art==='pruefvermerk'?'✓ Prüfvermerk':'⎘ Kopie gespeichert'} — ${esc(b.bezeichnung)}${b.halter?' · Halter: '+esc(lab(HALTER_DE,b.halter)):''}${b.geprueft_am?' · geprüft '+esc(fmtDate(b.geprueft_am))+' von '+esc(b.geprueft_von||''):''}${b.loeschdatum?' · Löschung '+esc(fmtDate(b.loeschdatum)):''}</div>`).join('')}</div></details>`;}
    if(f.bekanntgaben.length){h+=`<details><summary class="small">Bekanntgaben (${f.bekanntgaben.length})</summary><div class="small">${f.bekanntgaben.map(b=>`<div>→ <b>${esc(b.wer)}</b> · ${esc(b.zweck||'')} · ${esc(b.grundlage||'')} · ${esc(fmtDate(b.zeitpunkt))}</div>`).join('')}</div></details>`;}
    h+=`</div>`;});
  h+=`<div class="card"><div class="dvsub">Einwilligungen (${p.einwilligungen.length})</div>${p.einwilligungen.length?p.einwilligungen.map(e=>`<div class="small">${esc(fmtDate(e.erteilt_am))} — ${esc(e.gegenstand)}${e.formular?' («'+esc(e.formular)+'»)':''}${e.widerrufen_am?' · widerrufen '+esc(fmtDate(e.widerrufen_am)):''}</div>`).join(''):'<div class="small muted">Keine — alle Datenpunkte dieser Person stützen sich auf eine Norm oder den Aufgabenbedarf.</div>'}</div>`;
  const mx=Math.max(1,...p.loeschkalender.map(k=>k.n));
  h+=`<div class="card"><div class="dvsub">Löschkalender — wann welche Datenpunkte fällig werden (berechnet aus den Aufbewahrungsfristen)</div>
    ${p.loeschkalender.map(k=>`<div class="lkrow"><span class="lky">${esc(k.jahr)}</span><div class="pbar nt" style="max-width:420px"><i style="width:${Math.round(100*k.n/mx)}%"></i></div><span class="small">${k.n}</span></div>`).join('')}
    <div class="small muted" style="margin-top:6px">Ein Datenpunkt wird nie hart gelöscht: der Status wechselt auf «vernichtet» oder «anonymisiert», und dieser Wechsel schreibt selbst einen Protokolleintrag (Trigger im Schema).</div></div>`;
  m.innerHTML=h;
  if(badSub) m.insertAdjacentHTML('afterbegin',`<div class="nores">Person «${esc(asked)}» gibt es in diesem Export nicht — gezeigt wird ${esc(P[0].vorname)} ${esc(P[0].name)}.</div>`);
  m.querySelectorAll('.tcat[data-pi]').forEach(c=>c.onclick=()=>{state.sub=c.dataset.pi;render();});
  wireGo(m);
}
// ---------- Lebenslagen (eCH-0049): what one situation asks of a person ----------
const CIRC=n=>n<=20?String.fromCharCode(0x2460+n-1):'('+n+')';
function themaById(id){return (DATA.themenkatalog||[]).find(t=>String(t.id)===String(id));}
function viewLebenslagen(){
  const m=document.getElementById('main');
  const T=DATA.themenkatalog||[];
  const sub=state.sub&&state.sub!=='felder'?state.sub:'privat';
  if(/^g-\d+$/.test(sub)){ viewLebenslage(+sub.slice(2)); return; }
  const kat=sub==='unternehmen'?'unternehmen':'privat';
  const badSub=sub!=='privat'&&sub!=='unternehmen'; state.sub=kat;
  let h=pageHead('Lebenslagen · die Themengruppen von eCH-0049',
    'Die Services des Kantons nach den Themengruppen von eCH-0049 — so, wie eine Person oder ein Betrieb sie sucht, mit den Daten, die sie verlangen.',
    'Die Services des Kantons, gegliedert nach dem offiziellen Themenkatalog eCH-0049 — so, wie eine Person oder ein Betrieb sie sucht. Der Standard nennt die Einheiten <b>Themengruppen</b>; viele davon sind Lebenslagen (Geburt, Wohnen und Umziehen, Todesfall, Arbeitslosigkeit, Pensionierung, Berufliche Selbständigkeit), andere Themen (Steuern, Energie). Je Themengruppe: welche Services und Dienststellen man trifft, wie viele Datenpunkte verlangt werden, wo sich die Services bei derselben Angabe <b>überschneiden</b>, und was das Einwohnerregister schon weiss.',
    'Katalog: eCH-0049 V4.00 (genehmigt), Beilage 1-1 Privatpersonen und 2-1 Unternehmen; jede Themengruppe ist im amtlichen PDF unter ihrem Themenbereich geprüft. Welcher Service in welche Themengruppe gehört (bis zu drei je Service), ist maschinell vorgeschlagen (siehe «Methode &amp; Quellen») und je Eintrag durch eine zweite, unabhängige Prüfung bestätigt oder mit Grund korrigiert (Korrekturen in quellen/korrekturen/). «Dieselbe Angabe» heisst: gleiches eCH-Element, bei Personen- und Adressdaten dieselbe beurteilte Partei, dieselbe genannte Rolle — Dokumente, Beilagen, Bemerkungen und Felder mit abweichender Zuordnung werden nie gleichgesetzt; im Zweifel wird getrennt gezählt.',
    '<b>Überschneidungen</b> zählen, wie oft ein Service eine Angabe verlangt, die ein anderer Service derselben Themengruppe auch verlangt. Das beschreibt das Angebot, nicht die Last einer einzelnen Person: Services können Alternativen sein, die niemand zusammen durchläuft (z. B. B- und C-Bewilligung). Kachel anklicken für die Einzelheiten.');
  h+=`<div class="todocats">${['privat','unternehmen'].map(k=>`<span class="tcat${k===kat?' on':''}" data-kat="${k}">${esc(lab(KAT_DE,k))} <b>${T.filter(t=>t.katalog===k&&t.n_services).length}</b> Themengruppen mit Services</span>`).join('')}</div>`;
  const byB={}; T.filter(t=>t.katalog===kat).forEach(t=>{(byB[t.bereich]=byB[t.bereich]||[]).push(t);});
  Object.entries(byB).forEach(([b,L])=>{
    const withS=L.filter(t=>t.n_services), without=L.filter(t=>!t.n_services);
    h+=`<h4 class="hscope">${esc(b)} <span class="muted small">· ${withS.length} von ${L.length} Themengruppen mit kantonalen Services</span></h4><div class="llgrid">`;
    withS.sort((a,b)=>b.n_services-a.n_services).forEach(t=>{
      h+=`<button class="lltile" data-g="${t.id}"><span class="lln">${esc(t.gruppe)}</span>
        <span class="lls"><b>${t.n_services}</b> ${plw(t.n_services,'Service','Services')} · <b>${t.n_dienststellen||0}</b> ${plw(t.n_dienststellen,'Dienststelle','Dienststellen')}</span>
        <span class="lls">${t.n_angaben?`<b>${t.n_angaben}</b> ${plw(t.n_angaben,'Datenpunkt','Datenpunkte')}`:'keine Formular-Daten modelliert'}${t.n_ueberschneidungen?` · <span class="llrep">${pl(t.n_ueberschneidungen,'Überschneidung','Überschneidungen')}</span>`:''}</span></button>`;});
    h+=`</div>`;
    if(without.length) h+=`<div class="small muted" style="margin:2px 0 10px">ohne kantonalen Service in der Databank: ${without.map(t=>esc(t.gruppe)).join(' · ')}</div>`;
  });
  const none=DATA.services.filter(sv=>!(sv.themen||[]).length);
  if(none.length) h+=`<details class="card"><summary class="small"><b>${pl(none.length,'Service','Services')} ohne Themengruppe</b> — z. B. rein behördeninterne Verfahren; der Grund steht je Service</summary>
    ${none.map(sv=>`<div class="small">• <a class="simlink" data-sid="${sv.id}">${esc(sv.name)}</a> <span class="muted">— ${esc(sv.themen_grund||'')}</span></div>`).join('')}</details>`;
  m.innerHTML=h;
  if(badSub) m.insertAdjacentHTML('afterbegin',`<div class="nores">Filter «${esc(sub)}» ist auf dieser Seite unbekannt — gezeigt werden die Themengruppen für ${esc(lab(KAT_DE,kat))}.</div>`);
  m.querySelectorAll('.tcat[data-kat]').forEach(c=>c.onclick=()=>{state.sub=c.dataset.kat;render();});
  m.querySelectorAll('.lltile').forEach(b=>b.onclick=()=>{state.sub='g-'+b.dataset.g;render();});
  m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=()=>{state.service=a.dataset.sid;state.tab='fields';state.sub='felder';render();});
}
function viewLebenslage(id){
  const m=document.getElementById('main'); const t=themaById(id);
  if(!t){m.innerHTML='<div class="nores">Unbekannte Themengruppe.</div>';return;}
  const S=(t.services||[]).map(sid=>svcById[sid]).filter(Boolean);
  const num={}; S.forEach((sv,i)=>{num[sv.id]=i+1;});
  let h=`<div class="crumbs"><a class="simlink" id="llback">‹ alle Themengruppen (${esc(lab(KAT_DE,t.katalog))})</a></div>
    <h3 class="view">${esc(t.gruppe)} <span class="muted small">· ${esc(t.bereich)} · eCH-0049 ${esc(lab(KAT_DE,t.katalog))}</span></h3>`;
  const nMod=(t.services_modelliert||[]).length, nOhne=(t.services_ohne_daten||[]).length;
  if(!t.n_services){m.innerHTML=h+'<div class="nores">Kein kantonaler Service in dieser Themengruppe.</div>';
    document.getElementById('llback').onclick=()=>{state.sub=t.katalog;render();};return;}
  h+=`<div class="card llsum">In der Themengruppe <b>${esc(t.gruppe)}</b> ${plw(t.n_services,'steht','stehen')} <b>${t.n_services}</b> ${plw(t.n_services,'Service','Services')} bei <b>${t.n_dienststellen||0}</b> ${plw(t.n_dienststellen||0,'Dienststelle','Dienststellen')}.
    ${nOhne?` Für <b>${nMod}</b> davon sind Formular-Daten modelliert, für ${nOhne} nicht — die Zahlen unten betreffen nur die modellierten.`:''}
    ${t.n_formulare?` ${t.n_formulare===1?'Ihr einziges Formular verlangt':'Ihre '+nf(t.n_formulare)+' Formulare verlangen'} <b>${t.n_angaben}</b> ${plw(t.n_angaben,'Datenpunkt','Datenpunkte')} — ${pl(t.n_pflicht,'als Pflichtfeld','als Pflichtfelder')}${t.n_pflicht_teil?`, dazu ${t.n_pflicht_teil} Teile von Pflicht-Feldgruppen`:''} — und <b>${t.n_beilagen}</b> ${plw(t.n_beilagen,'Beilage','Beilagen')}.
      ${t.n_wiederholt?` <b>${t.n_wiederholt}</b> ${plw(t.n_wiederholt,'Angabe','Angaben')} verlangen mehrere dieser Services: <b>${t.n_ueberschneidungen}</b> ${plw(t.n_ueberschneidungen,'Überschneidung','Überschneidungen')} über das Angebot hinweg — die Services können Alternativen sein, die niemand zusammen durchläuft.`:(nMod>1?' Unter den modellierten Services verlangt keiner eine Angabe, die ein anderer auch verlangt.':'')}
      ${t.n_einwohnerregister?` <b>${t.n_einwohnerregister}</b> ${plw(t.n_einwohnerregister,'Datenpunkt','Datenpunkte')} führt das Einwohnerregister für die betroffenen Personen bereits${(t.register||{}).n_vorbefuellbar_korrigiert!=null?` — davon ${t.register.n_vorbefuellbar_korrigiert===1?'ist':'sind'} <b>${t.register.n_vorbefuellbar_korrigiert}</b> ${plw(t.register.n_vorbefuellbar_korrigiert,'Pflichtangabe','Pflichtangaben')} der einreichenden Person vorbefüllbar`:''}.`:''}${t.n_einwohnerregister_offen?` Für ${pl(t.n_einwohnerregister_offen,'Datenpunkt','Datenpunkte')} zu Personen und Adressen ist noch nicht beurteilt, wessen ${plw(t.n_einwohnerregister_offen,'Angabe sie ist','Angaben sie sind')}.`:''}`:''}</div>`;
  if(t.n_formulare) h+=`<div class="regstats">
    <span class="rstat">Datenpunkte <b>${t.n_angaben}</b></span>
    <span class="rstat" title="Wie oft ein Service eine Angabe verlangt, die ein anderer Service dieser Themengruppe auch verlangt">Überschneidungen <b>${t.n_ueberschneidungen}</b></span>
    <span class="rstat" title="Datenpunkte, die das Einwohnerregister laut zitierter Quelle führt — für wen auch immer (auch Ehepartner/in, Kinder). Vorbefüllbar sind davon nur die Pflichtangaben der einreichenden Person.">im Einwohnerregister geführt <b>${t.n_einwohnerregister}</b>${t.n_einwohnerregister_offen?` · ${t.n_einwohnerregister_offen} nicht beurteilt`:''}</span>
    <span class="rstat" title="Ohne eCH-Element lässt sich nicht erkennen, ob zwei Formulare dasselbe verlangen">ohne eCH-Element <b>${t.n_ohne_standard}</b>${t.n_ohne_standard?` <span class="muted">(${SW(tonOf('ech','kein_standard'))}kein Standard ${t.n_kein_standard} · ${SW(tonOf('ech','element_offen'))}Element offen ${t.n_element_offen} · ${SW(tonOf('ech','ungeprueft'))}ungeprüft ${t.n_ungeprueft})</span>`:''}</span>
    ${(t.n_container+t.n_zuordnung_offen+t.n_partei_offen)?`<span class="rstat" title="Mit Element, aber bewusst nicht verglichen">nicht gleichgesetzt <b>${t.n_container+t.n_zuordnung_offen+t.n_partei_offen}</b> <span class="muted">(Dokument/Beilage/Bemerkung ${t.n_container} · andere Zuordnung ${t.n_zuordnung_offen} · Partei offen ${t.n_partei_offen})</span></span>`:''}
    <span class="rstat">Beilagen <b>${t.n_beilagen}</b>${t.n_beilagen_beziehbar?` · ${t.n_beilagen_beziehbar} bei der Dienststelle beziehbar`:''}</span>
    <span class="rstat">online einreichbar <b>${t.n_online}/${t.n_formulare}</b></span>
    <span class="rstat">mit Unterschrift <b>${t.n_unterschrift}</b></span>
    ${t.n_sensibel?`<span class="rstat">⛨ sensible Felder <b>${t.n_sensibel}</b></span>`:''}</div>`;
  h+=`<div class="card"><div class="dvsub">Die Services dieser Themengruppe</div><div class="tscroll"><table class="ft fit"><thead><tr><th>#</th><th>Service</th><th>Dienststelle</th><th>Formulare</th><th>weitere Themengruppen</th></tr></thead><tbody>
    ${S.map(sv=>{const fs=DATA.forms.filter(f=>f.service_id===sv.id);
      const other=(sv.themen||[]).filter(x=>x.id!==t.id);
      return `<tr><td>${CIRC(num[sv.id])}</td><td class="hy"><a class="simlink" data-sid="${sv.id}">${esc(sv.name)}</a></td>
        <td class="small muted hy">${esc(sv.dienststelle||'')}</td><td class="small">${fs.filter(f=>(f.data_fields||[]).length).length||`<span class="muted">nicht modelliert</span>`}</td>
        <td class="small">${other.map(x=>`<a class="simlink llgo" data-g="${x.id}">${esc(x.gruppe)}</a>`).join(' · ')||'—'}</td></tr>`;}).join('')}
    </tbody></table></div></div>`;
  if((t.wiederholt||[]).length){
    h+=`<div class="card"><div class="dvsub">Überschneidungen — dieselbe Angabe von mehreren Services dieser Themengruppe verlangt</div>
      <div class="small muted" style="margin-bottom:6px">Jede Zeile ist eine Angabe: gleiches eCH-Element, bei Personen- und Adressdaten dieselbe Partei, dieselbe genannte Rolle. Die Nummern sind die Services oben. Wo jemand diese Services tatsächlich nacheinander braucht, würde eine einmalige Angabe — oder die Übernahme aus einem Register — mehrere Formulare entlasten; wo sie Alternativen sind, zeigt die Zeile nur, dass die Formulare dasselbe verlangen.</div>
      <table class="ft"><thead><tr><th>Attribut</th><th>Standard-Element</th><th>verlangt von</th></tr></thead><tbody>
      ${t.wiederholt.map(w=>`<tr><td><b>${esc(w.label||'')}</b></td><td class="mono small">${esc(w.element)}</td>
        <td>${w.services.map(sid=>`<span class="llnum" title="${esc((svcById[sid]||{}).name||'')}">${CIRC(num[sid]||0)}</span>`).join(' ')} <span class="muted small">(${w.services.length})</span></td></tr>`).join('')}
      </tbody></table>${t.n_wiederholt>t.wiederholt.length?`<div class="small muted">— die ${t.wiederholt.length} häufigsten von ${t.n_wiederholt} gezeigt</div>`:''}</div>`;
  }
  m.innerHTML=h;
  document.getElementById('llback').onclick=()=>{state.sub=t.katalog;render();};
  m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=()=>{state.service=a.dataset.sid;state.tab='fields';state.sub='felder';render();});
  m.querySelectorAll('.llgo').forEach(a=>a.onclick=()=>{state.sub='g-'+a.dataset.g;render();});
}
// ---------- Begriffe: one datum, one name ----------
function viewBegriffe(){
  const m=document.getElementById('main');
  const B=DATA.begriffe||[];
  // only the three filters this view knows; anything else (a sub carried over
  // from another tab) falls back instead of matching nothing
  const f=['angleichen','pruefen','alle'].includes(state.sub)?state.sub:'angleichen';
  const asked=state.sub; const badSub=asked&&asked!=='felder'&&asked!==f; state.sub=f;
  // a search hit arrives with its term (state.begq) so the card is on the first page
  const q0=state.begq||''; state.begq='';
  const cnt=k=>B.reduce((n,b)=>n+b.labels.filter(l=>l.klasse===k).length,0);
  const BS=DATA.begriffe_stats||{};
  let h=pageHead('Begriffe · Eine Angabe, ein Name',
    'Wo dieselbe Angabe unter verschiedenen Bezeichnungen erfragt wird — und welcher Begriff einheitlich gelten soll.',
    'Für jede Angabe mit offiziellem eCH-Element, die unter <b>mindestens zwei</b> Bezeichnungen erfragt wird: unter welchen Bezeichnungen die Formulare danach fragen, welcher Begriff einheitlich verwendet werden soll — und welche Abweichungen in Ordnung sind, weil sie sagen, <i>wessen</i> oder <i>welche</i> Angabe gemeint ist.',
    `Vorschlag und Einordnung sind maschinell erarbeitet (siehe ${goLink('methode','','«Methode &amp; Quellen»','inl')}) und je Eintrag durch eine zweite, unabhängige Prüfung bestätigt oder mit Grund korrigiert; korrigierte Einträge tragen in der Begründung den Vermerk «Zweitprüfung:», die Korrekturen liegen in quellen/korrekturen/. Der Vorschlag ist immer eine Bezeichnung, die in den Formularen bereits vorkommt — kein erfundener Begriff. Die Zählungen kommen live aus der Feld-Schicht.`,
    '<b>angleichen</b> = dieselbe Sache, nur anders geschrieben («Nachname», «Familienname») → auf den Vorschlag umbenennen. <b>Rolle — in Ordnung</b> = die Bezeichnung nennt, wessen oder welche Angabe gemeint ist — Partei, Art, Ort oder Zeitraum («Name Arbeitnehmer», «Adresse bisher») → so lassen. <b>Feld aufteilen</b> = das Feld bündelt mehrere Daten, die der Standard trennt («Strasse und Nr», «PLZ und Ort») → im Formular aufteilen. <b>eCH-Zuordnung korrigieren</b> = die Bezeichnung meint eine andere Angabe als das Element → die Databank korrigiert die Zuordnung.');
  h+=`<div class="regstats"><span class="rstat">Daten mit Vorschlag <b>${B.length}</b></span>
    <span class="rstat" title="Verschiedene Bezeichnungen, die auf den einheitlichen Begriff umzubenennen sind — und wie viele Datenpunkte in wie vielen Formularen sie tragen">${SW(tonOf('begriff','variante'))}Bezeichnungen anzugleichen <b>${nf(cnt('variante'))}</b> · ${pl(BEN_T.variante,'Datenpunkt','Datenpunkte')} in ${pl(BEN_F.variante,'Formular','Formularen')}</span>
    <span class="rstat">${SW(tonOf('begriff','rolle'))}Rollen-Bezeichnungen <b>${nf(cnt('rolle'))}</b></span>
    <span class="rstat">${SW(tonOf('begriff','vorbehalt'))}Vorschläge unter Vorbehalt <b>${nf(B.filter(b=>b.vorbehalt).length)}</b></span>
    <span class="rstat" title="Bezeichnungen, die mehrere Daten bündeln — und wie viele Datenpunkte in wie vielen Formularen sie tragen">${SW(tonOf('begriff','aufteilen'))}Feld aufteilen <b>${nf(B.reduce((n,b)=>n+b.labels.filter(l=>l.pruefart==='aufteilen').length,0))}</b> · ${pl(BEN_T.aufteilen,'Datenpunkt','Datenpunkte')} in ${pl(BEN_F.aufteilen,'Formular','Formularen')}</span>
    <span class="rstat" title="Bezeichnungen, deren eCH-Zuordnung die Databank korrigiert — und wie viele Datenpunkte sie tragen">${SW(tonOf('begriff','zuordnung'))}${esc(todoCat('zuordnung')[1])} <b>${nf(B.reduce((n,b)=>n+b.labels.filter(l=>l.pruefart==='zuordnung').length,0))}</b> · ${pl(BEN_T.zuordnung,'Datenpunkt','Datenpunkte')}</span>
    ${BS.n_elemente_eine_bezeichnung?`<span class="rstat" title="Daten, nach denen nur unter einer einzigen Bezeichnung gefragt wird, sind hier nicht geprüft — auch sie können vom einheitlichen Begriff abweichen">nur eine Bezeichnung (nicht geprüft) <b>${nf(BS.n_elemente_eine_bezeichnung)}</b></span>`:''}</div>`;
  h+=`<div class="todocats">${[['angleichen','mit Angleichungsbedarf'],['pruefen','mit Prüfbedarf'],['alle','alle Daten']].map(([k,l])=>`<span class="tcat${k===f?' on':''}" data-f="${k}">${l}</span>`).join('')}
    <input id="begq" class="gsearch" style="margin-left:8px;max-width:260px" placeholder="Bezeichnung filtern …" value="${esc(q0)}"></div><div id="beglist"></div>`;
  m.innerHTML=h;
  if(badSub) m.insertAdjacentHTML('afterbegin',`<div class="nores">Filter «${esc(asked)}» ist auf dieser Seite unbekannt — gezeigt werden die Daten mit Angleichungsbedarf.</div>`);
  const draw=()=>{
    const q=(document.getElementById('begq').value||'').toLowerCase().trim();
    let L=B.filter(b=>f==='alle'||(f==='angleichen'&&b.labels.some(l=>l.klasse==='variante'))||(f==='pruefen'&&b.labels.some(l=>l.klasse==='pruefen')));
    if(q) L=L.filter(b=>(b.vorschlag+' '+b.labels.map(l=>l.label).join(' ')+' '+b.element).toLowerCase().includes(q));
    let o=`<div class="small muted" style="margin:4px 0 8px">${pl(L.length,'Angabe','Angaben')}${L.length>60?' — die ersten 60 gezeigt, Filter eingrenzen':''}</div>`;
    L.slice(0,60).forEach(b=>{
      const g=k=>b.labels.filter(l=>l.klasse===k).sort((x,y)=>y.n-x.n);
      const vor=b.labels.find(l=>l.klasse==='vorschlag');
      // the tone of a label (ton_map.begriff): rename or split red, a role fine green,
      // a wrong eCH mapping grey (the databank's), a proposal under reserve amber (the canton's)
      const T=k=>tonOf('begriff',k);
      const chip=l=>`<span class="bgl st-${T('variante')}" title="${esc(`${l.n}× in ${l.n_formulare} Formular${l.n_formulare===1?'':'en'}${l.grund?' — '+l.grund:''}\n`+tonWords(T('variante')))}">«${esc(l.label)}» <span class="muted">${l.n}×</span></span>`;
      o+=`<div class="card bgcard" id="beg-${esc(String(b.element_id))}"><div class="bghead"><span class="bgvor">«${esc(b.vorschlag)}»</span>
          ${b.vorbehalt?stBadge(T('vorbehalt'),'Vorschlag unter Vorbehalt',b.begruendung||'Vorschlag unter Vorbehalt — über den einheitlichen Begriff entscheidet der Kanton')
            :stBadge(T('vorschlag'),'einheitlicher Begriff','Der Vorschlag ist eine Bezeichnung, die in den Formularen bereits vorkommt — so soll die Angabe überall heissen')}
          ${b.herkunft==='korpus'?mkBadge('Begriff aus anderen Formularen','Die Formulare dieser Angabe verwenden keinen sauberen Begriff; der Vorschlag stammt aus anderen Formularen des Kantons (nie erfunden) — ein Kennzeichen, keine Bewertung'):''}
          <span class="mono small muted">${esc(b.standard)} ${esc(b.element)}${b.datentyp?` ⟨${esc(b.datentyp)}⟩`:''}</span>
          <span class="small muted" style="margin-left:auto">${vor?`Vorschlag ${vor.n}× verwendet`:''}</span></div>
        ${b.begruendung?`<div class="small muted">${esc(b.begruendung)}</div>`:''}
        ${g('variante').length?`<div class="bgrow"><span class="bglab">${SW(T('variante'))}angleichen → «${esc(b.vorschlag)}»</span>${g('variante').map(chip).join('')}</div>`:''}
        ${g('rolle').length?`<div class="bgrow"><span class="bglab">${SW(T('rolle'))}Rolle — in Ordnung</span>${g('rolle').map(l=>`<span class="bgl st-${T('rolle')}" title="${esc(`${l.n}× · Rolle: ${l.rolle||''}\n`+tonWords(T('rolle')))}">«${esc(l.label)}» <span class="muted">${esc(l.rolle||'')}</span></span>`).join('')}</div>`:''}
        ${(()=>{const P=g('pruefen'); if(!P.length) return '';
          const row=(L,lab,t)=>L.length?`<div class="bgrow"><span class="bglab">${SW(t)}${lab}</span>${L.map(l=>`<span class="bgl st-${t}" title="${esc((l.grund||'')+'\n'+tonWords(t))}">«${esc(l.label)}» <span class="muted">${esc(l.grund||'')}</span></span>`).join('')}</div>`:'';
          return row(P.filter(l=>l.pruefart==='aufteilen'),'Feld aufteilen',T('aufteilen'))
            +row(P.filter(l=>l.pruefart==='zuordnung'),'eCH-Zuordnung korrigieren',T('zuordnung'))
            +row(P.filter(l=>!l.pruefart),'prüfen',T('pruefen'));})()}
      </div>`;});
    document.getElementById('beglist').innerHTML=o;
  };
  draw();
  document.getElementById('begq').addEventListener('input',draw);
  m.querySelectorAll('.tcat[data-f]').forEach(c=>c.onclick=()=>{state.sub=c.dataset.f;render();});
  wireGo(m);
}
// ---------- explanations without a mouse ----------
// Every element that carries a title but is not itself a link or a control (badge, chip,
// marker, bar segment, a point of a trend line, a count in a clickable row) becomes
// focusable; a click, a tap, Enter or Space opens a small box with the title text, which a
// polite live region also announces. Esc, Tab or a click elsewhere closes it.
//  * a link or a control keeps its own action — its status is readable without hovering
//    (tone + short label) — and nothing inside it becomes an explanation
//  * inside a clickable row (a table row, a sidebar entry, a toggle) or a <summary>, a
//    titled badge explains itself: its click does not also open the row (data-tip="in");
//    the row keeps its action everywhere else and through the link it carries
//  * a titled chip with an action of its own (⛨ → Leitfaden, a rule chip → Datenhandhabung)
//    explains itself first; the box offers that action as a button (data-tip="self", the
//    button text from data-tipgo)
// Clickable elements that are neither links nor buttons (a row without a link, a sidebar
// toggle, a link without an address, a filter chip) are made reachable by keyboard:
// focusable, Enter acts, Space too except on a link (data-act).
const TIP_CTRL='a,button,input,select,textarea,label,[role="link"]:not([data-act]),[role="button"]:not([data-tip]):not([data-act])';
const _clickable=x=>typeof x.onclick==='function'||x.hasAttribute('data-act');
function tipCtx(el){
  if(el.tagName==='SUMMARY'||el.closest(TIP_CTRL)) return 'ctrl';
  if(_clickable(el)) return 'self';
  for(let x=el.parentElement; x&&x.nodeType===1&&x!==document.body; x=x.parentElement)
    if(x.tagName==='SUMMARY'||_clickable(x)) return 'in';
  return 'plain';
}
function tipText(el){
  const t=el.getAttribute('title');
  if(t) return t;
  const c=[...el.children].find(n=>n.tagName&&n.tagName.toLowerCase()==='title');
  return c?c.textContent:'';
}
function enhanceTips(root){
  if(!root) return;
  const els=[...root.querySelectorAll('[title]:not([data-tip]):not([data-notip])')];
  root.querySelectorAll('g:not([data-tip]):not([data-notip])>title').forEach(t=>els.push(t.parentNode));
  els.forEach(el=>{
    if(el.hasAttribute('data-tip')||el.hasAttribute('data-notip')) return;
    // a list item stays a list item (a list whose items are buttons is no list): its
    // explanation moves to the label inside it, which becomes the button that opens it
    if(el.tagName==='LI'&&el.hasAttribute('title')){
      const lbl=[...el.children].reverse().find(c=>/^(span|b)$/i.test(c.tagName)&&!c.hasAttribute('title')&&!c.hasAttribute('data-tip'));
      if(lbl){lbl.setAttribute('title',el.getAttribute('title')); el.removeAttribute('title'); el.setAttribute('data-notip',''); el=lbl;}}
    const ctx=tipText(el).trim()?tipCtx(el):'ctrl';
    if(ctx==='ctrl'){el.setAttribute('data-notip',''); return;}
    el.setAttribute('data-tip',ctx==='plain'?'':ctx);
    if(!el.hasAttribute('tabindex')) el.setAttribute('tabindex','0');
    // a generic element becomes a button that opens the explanation; a table cell or a
    // list item keeps its own role (the table stays a table), the live region speaks for it
    if(!el.hasAttribute('role')&&/^(span|i|b|div|g|sup|small|em|strong)$/i.test(el.tagName)){
      el.setAttribute('role','button'); el.setAttribute('aria-haspopup','dialog'); el.setAttribute('aria-expanded','false');}
  });
}
// runs after enhanceTips: an element that explains itself (data-tip) keeps Enter for its box
function enhanceActs(root){
  if(!root) return;
  const all=root.getElementsByTagName('*');
  for(let i=0;i<all.length;i++){const x=all[i];
    if(typeof x.onclick!=='function'||x.hasAttribute('data-act')||x.hasAttribute('data-tip')||x.hasAttribute('data-noact')||x.hasAttribute('tabindex')) continue;
    const tag=x.tagName.toLowerCase();
    if(/^(button|input|select|textarea|summary|label|option)$/.test(tag)||(tag==='a'&&x.hasAttribute('href'))) continue;
    // a row whose action a link inside it already carries needs no second stop
    if(x.querySelector('[data-rowlink]')||(tag==='tr'&&x.querySelector('a[href]'))) continue;
    x.setAttribute('data-act',''); x.setAttribute('tabindex','0');
    // a role only where it is true for the whole element: a link without address, a
    // toggle with nothing focusable inside; a row stays a row
    if(!x.hasAttribute('role')&&!/^(tr|td|th|svg)$/.test(tag)){
      if(tag==='a') x.setAttribute('role','link');
      else if(!x.querySelector('a[href],button,[tabindex],[title]')) x.setAttribute('role','button');}
  }
}
let _tipEl=null, _tipPass=false;
const fireClick=el=>el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
function tipClose(refocus){
  const box=document.getElementById('tipbox'); if(box) box.hidden=true;
  const el=_tipEl; _tipEl=null;
  if(el){if(el.hasAttribute('aria-expanded')) el.setAttribute('aria-expanded','false'); if(refocus&&el.isConnected&&el.focus) el.focus({preventScroll:true});}
}
function tipOpen(el,kb){
  const box=document.getElementById('tipbox'); const txt=tipText(el);
  if(!box||!txt) return;
  if(_tipEl===el&&!box.hidden){tipClose(!!kb); return;}   // a second click closes it again
  if(_tipEl&&_tipEl.hasAttribute('aria-expanded')) _tipEl.setAttribute('aria-expanded','false');
  _tipEl=el; box.querySelector('.tipt').textContent=txt;
  box.style.left='0px'; box.style.top='0px';   // measured unconstrained, never at an old position
  // a chip with an action of its own offers it here
  const go=box.querySelector('.tipgo'), act=el.getAttribute('data-tip')==='self';
  if(go){go.hidden=!act; go.textContent=act?(el.getAttribute('data-tipgo')||'Öffnen ›'):'';}
  box.hidden=false;
  if(el.hasAttribute('aria-expanded')) el.setAttribute('aria-expanded','true');
  // below the element, kept inside the window; above it when there is no room below
  const r=el.getBoundingClientRect(), bw=box.offsetWidth, bh=box.offsetHeight;
  const vw=document.documentElement.clientWidth, sx=window.scrollX, sy=window.scrollY;
  const x=Math.max(8,Math.min(r.left,vw-bw-8));
  const y=(r.bottom+bh+10>window.innerHeight&&r.top>bh+10)?r.top-bh-6:r.bottom+6;
  box.style.left=(x+sx)+'px'; box.style.top=(y+sy)+'px';
  // a box that does not fit on the screen (a chip at the lower edge) is brought into view —
  // the reader opened it to read it
  const rb=box.getBoundingClientRect();
  if(rb.top<0||rb.bottom>window.innerHeight) box.scrollIntoView({block:'nearest',behavior:MOTION});
  const live=document.getElementById('tiplive');
  if(live){live.textContent=''; setTimeout(()=>{if(_tipEl===el) live.textContent=txt;},40);}
  // opened by keyboard: the action waits in the box — focus goes there, Esc returns; the box
  // is already in view (and never taller than the window), so the focus itself must not
  // scroll again: a second scroll would push the beginning of the text off the screen
  if(kb&&act&&go) go.focus({preventScroll:true});
}
// the action of the explained chip, run as its own click (past the capture below)
function tipGo(){
  const el=_tipEl; if(!el||!el.isConnected) return;
  tipClose(false);
  _tipPass=true; try{fireClick(el);}finally{_tipPass=false;}
}
// capture phase: a badge inside a clickable row or a <summary>, and a chip with an action
// of its own, explain themselves before the row, the summary or the chip act
document.addEventListener('click',e=>{
  if(_tipPass) return;
  const tg=e.target, t=tg&&tg.closest?tg.closest('[data-tip="in"],[data-tip="self"]'):null;
  if(!t) return;
  // a link or control inside the explained element keeps its own action
  const c=tg.closest(TIP_CTRL); if(c&&t.contains(c)&&c!==t) return;
  e.preventDefault(); e.stopPropagation(); tipOpen(t);
},true);
document.addEventListener('click',e=>{
  if(_tipPass) return;
  const box=document.getElementById('tipbox'), tg=e.target;
  if(box&&tg&&box.contains(tg)){
    if(tg.closest('.tipx')) tipClose(true);
    else if(tg.closest('.tipgo')) tipGo();
    return;}
  const t=tg&&tg.closest?tg.closest('[data-tip]'):null;
  // a link or control inside an explained element keeps its own action
  const c=tg&&tg.closest?tg.closest(TIP_CTRL):null;
  if(t&&!(c&&t.contains(c)&&c!==t)){tipOpen(t); return;}
  if(_tipEl) tipClose(false);
});
document.addEventListener('keydown',e=>{
  const box=document.getElementById('tipbox');
  if(e.key==='Escape'&&_tipEl){e.preventDefault(); tipClose(true); return;}
  // Tab out of the box: back to the explained element, the browser moves on from there
  if(e.key==='Tab'&&_tipEl&&box&&box.contains(document.activeElement)){tipClose(true); return;}
  // Tab moves on from an explained element: its box closes (the browser still moves the focus)
  if(e.key==='Tab'&&_tipEl) tipClose(false);
  if(e.key==='Escape'&&!_tipEl){const l=document.querySelector('.layout');
    if(l&&l.classList.contains('nav-open')){e.preventDefault(); closeNav(); const b=document.querySelector('.navbtn'); if(b) b.focus(); return;}}
  const t=e.target;
  if(!t||!t.hasAttribute||(box&&box.contains(t))) return;
  if((e.key==='Enter'||e.key===' ')&&t.hasAttribute('data-tip')){e.preventDefault(); tipOpen(t,true); return;}
  if(t.hasAttribute('data-act')&&(e.key==='Enter'||(e.key===' '&&t.getAttribute('role')!=='link'))){e.preventDefault(); fireClick(t);}
});
// an inner scroll (the sidebar on small screens) would leave the box behind: close it
window.addEventListener('scroll',e=>{if(_tipEl&&e.target!==document&&!(e.target&&e.target.id==='tipbox')) tipClose(false);},true);
window.addEventListener('resize',()=>{if(_tipEl) tipClose(false);});
// content drawn after render() (Begriffe filter, Datenfluss details, «alle anzeigen»)
try{const mo=new MutationObserver(()=>{const mn=document.getElementById('main'); enhanceTips(mn); enhanceActs(mn); renderLegend();});
  const mn=document.getElementById('main'); if(mn) mo.observe(mn,{childList:true,subtree:true});}catch(e){}
// ==== A NEW PAGE — the places where it must be registered ==============================
//  1. sidebar       a <button class="tab" data-tab="<name>"> in <aside> (HTML above), with the
//                   question it answers as <span class="tabsub">
//  2. view function function view<Name>(): starts with pageHead(title, one sentence, was,
//                   quelle, lesen) — one visible sentence, the rest folded; a wide table
//                   inside <div class="tscroll">; handlers set through .onclick (enhanceActs
//                   then makes them reachable by keyboard); a contact through kontaktHtml();
//                   a new term through GLOSSAR + term(); no scroll call (placeAfterRender)
//  3. render        one line in drawView() below; in NO_SUB when the page reads no
//     dispatch      sub-segment, in DEFAULT_SUB when its default filter has a name, in
//                   pageKey() when a sub-segment opens a page of its own
//  4. search index  its entries in searchIndex() (type, label, key, go) and the type in the
//                   `order` list of viewSearch()
//  5. legend        what the four tones mark on the page: TONEX in renderLegend(); a layer
//                   with words of its own speaks them there instead (Gestaltung: the branch
//                   `gst` on #gestaltung and the block of the panel .gpanel, which lights no
//                   tone of the data standard — DATA.gestaltung.labels)
//                   (Datenmodell & Once-Only: TONEX datenmodell / onceonly — amber the canton's
//                   confirmation or decision, green / grey the edition of a law)
//  6. page check    its route in PAGES of scripts/check_pages.mjs (the check fails when the
//                   navigation offers a page that is not listed there); a bar (.tbar, .minibar)
//                   is summed as it is, a list that states its total is put into a .sumbox —
//                   its numbers (.sumn) must add up to its .sumtot (several columns of one
//                   table: each pair .sumn/.sumtot carries the same data-s); `open: true` there
//                   when the page folds much of its text (details, «weitere …»)
//  7. documents     the list of views in the docstring of scripts/build_dashboard.py
// Figures of the page are computed in scripts/export_json.py (with their sum check) and
// only drawn here; colours and text sizes come from scripts/theme.py.
// ========================================================================================
// tabs that read no sub-segment: an unknown one is dropped and said at the top of the page
const NO_SUB=new Set(['home','methode','katalog','esh','register','datenfluss','rules','guide']);
let _lastRoute=null;
// the view of the current page; an unknown page says so (viewUnknown)
function drawView(){
  if(state.tab==='home') viewHome();
  else if(state.tab==='methode') viewMethode();
  else if(state.tab==='dienststellen') viewDienststellen();
  else if(state.tab==='kanton') viewKanton();
  else if(state.tab==='recherche') viewRecherche();
  else if(state.tab==='rules') viewRules();
  else if(state.tab==='guide') viewGuide();
  else if(state.tab==='register') viewRegister();
  else if(state.tab==='todo') viewTodo();
  else if(state.tab==='search') viewSearch();
  else if(state.tab==='datenfluss') viewDatenfluss();
  else if(state.tab==='lebenslagen') viewLebenslagen();
  else if(state.tab==='begriffe') viewBegriffe();
  else if(state.tab==='buerger') viewBuerger();
  else if(state.tab==='katalog') viewKatalog();
  else if(state.tab==='esh') viewEsh();
  else if(state.tab==='gestaltung') viewGestaltung();
  else if(state.tab==='datenmodell') viewDatenmodell();
  else if(state.tab==='onceonly') viewOnceonly();
  else if(state.tab==='fields') viewFields();
  else viewUnknown();
}
// a view that fails says so in plain words, under the address that was asked for — never
// the previous page under the new address; the other pages keep working
function viewFailed(err){
  const m=document.getElementById('main'); if(!m) return;
  m.innerHTML=`<h3 class="view" tabindex="-1">Seite nicht dargestellt</h3>
    <div class="bootmsg err" role="alert" style="margin:0"><b>Diese Seite konnte nicht dargestellt werden.</b>
    <span>Beim Aufbau der Seite «${esc(hashOfState())}» ist ein Fehler aufgetreten. Die übrigen Seiten sind davon nicht betroffen:
    <a href="#home" data-go="home">zur Übersicht</a> — oder die Seite neu laden.</span>
    <span class="small">Technische Meldung: ${esc(String((err&&err.message)||err||'unbekannt'))}</span></div>`;
  wireGo(m);
  try{console.error(err);}catch(e){}
}
function render(){
  // legacy #tree/#info aliases are normalised in readHash, so the sidebar and
  // the legend are drawn for the real tab on the first paint.
  // The Handlungsbedarf shows red and amber only: a grey (Databank) category or the
  // older «Recherche» filter of the board opens «Recherche der Databank» instead
  if(state.tab==='todo'){const s0=String(state.sub||'');
    if(s0==='art-recherche'){state.tab='recherche';state.sub='felder';}
    else if(TODO_BY[s0]&&catTon(s0)==='open'){state.tab='recherche';state.sub=s0;}}
  // a category named on the wrong worklist opens where it lives: red → Handlungsbedarf,
  // amber → Für den Kanton, grey → Recherche der Databank
  if((state.tab==='kanton'||state.tab==='recherche')&&TODO_BY[state.sub]){const t=catTon(state.sub);
    if(state.tab==='kanton'&&t!=='dec') state.tab=t==='open'?'recherche':'todo';
    else if(state.tab==='recherche'&&t!=='open') state.tab=t==='dec'?'kanton':'todo';}
  let noSub=null;
  if(NO_SUB.has(state.tab)&&state.sub!=='felder'){noSub=state.sub; state.sub='felder';}
  tipClose(false);
  // the place on the page being left is remembered before anything is redrawn
  if(_lastPage!==null&&_entry) _places[_entry]=placeNow();
  renderSidebar();
  try{drawView();}catch(err){viewFailed(err);}
  if(noSub!=null){let t=noSub; try{t=decodeURIComponent(noSub);}catch(e){}
    const m0=document.getElementById('main'); if(m0) m0.insertAdjacentHTML('afterbegin',`<div class="nores">Filter «${esc(t)}» ist auf dieser Seite unbekannt — gezeigt wird die ganze Seite.</div>`);}
  // explanations and keyboard access for what the view drew, then the legend of THIS page
  const mn=document.getElementById('main'); enhanceTips(mn); enhanceActs(mn);
  renderLegend(); enhanceTips(document.querySelector('header'));
  // the page title names the page (browser tab, bookmark, history); after a change of page
  // the focus moves to the page title, which a screen reader then reads — not on the first
  // load, and never away from a field the reader is typing in (that change is announced)
  const h=mn&&mn.querySelector('h3.view');
  // the page title without tag badges (e.g. «Sammelgruppe im DVSH»), which have no separator in the text
  const hc=h?h.cloneNode(true):null; if(hc) hc.querySelectorAll('.sammel,.badge,.tag').forEach(x=>x.remove());
  const SUF='Compliance-Databank Kanton Schaffhausen', ht=hc?hc.textContent.replace(/\s+/g,' ').trim():'';
  document.title=(ht&&ht!==SUF?ht+' — ':'')+SUF;
  const route=state.tab+'/'+state.service+'/'+state.sub;
  if(_lastRoute!==null&&route!==_lastRoute&&h){const ae=document.activeElement;
    if(ae&&/^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName)){const rl=document.getElementById('routelive'); if(rl) rl.textContent=h.textContent.trim();}
    else {if(!h.hasAttribute('tabindex')) h.setAttribute('tabindex','-1'); h.focus({preventScroll:true});}}
  _lastRoute=route;
  writeHash();
  placeAfterRender();
}
// header search: Enter (or a pause in typing) opens the results page
(()=>{const i=document.getElementById('gsearch'); if(!i) return; let t=null;
  const go=()=>{const q=i.value.trim(); if(!q) return; state.tab='search'; state.service='all'; state.sub=encodeURIComponent(q); render();};
  i.addEventListener('keydown',e=>{if(e.key==='Enter'){clearTimeout(t);go();}});
  i.addEventListener('input',()=>{clearTimeout(t); t=setTimeout(()=>{if(i.value.trim().length>=3)go();},450);});})();
_fromUrl=true;
readHash();
render();
placeAfterReload();
window.__cgStarted=true;
</script>
</body>
</html>
"""


# the look comes from scripts/theme.py (one definition for all generated pages)
TEMPLATE = (TEMPLATE.replace("/*THEME*/", THEME.css_root())
            .replace("/*THEME_SWATCH*/", THEME.css_swatch(".sw"))
            .replace("%%FAVICON%%", THEME.favicon()))


def check_guide(conn):
    """Refuse to build if the Leitfaden cites a rule that is not in data_rule —
    the guide must never reference law the databank does not hold."""
    have = set()
    for r in conn.execute("SELECT l.sr_number sr, a.article_no art, dr.aspect, dr.scope "
                          "FROM data_rule dr JOIN article a ON a.id=dr.article_id "
                          "JOIN law l ON l.id=a.law_id"):
        have.add((r["sr"], r["art"], r["aspect"], r["scope"]))
        have.add((r["sr"], r["art"], r["aspect"], None))
    level = {r["sr"]: r["lvl"] for r in conn.execute("SELECT sr_number sr, jurisdiction_level lvl FROM law "
                                                        "WHERE sr_number IS NOT NULL")}
    BUND = ("Bund", "DSG", "DSV", "EMBAG", "BGA", "Bundesorgan")
    bad = []
    for sec in LEITFADEN:
        for p in sec.get("punkte", []):
            refs = p.get("refs", [])
            for ref in refs:
                scope = ref[3] if len(ref) > 3 else None
                if (ref[0], ref[1], ref[2], scope) not in have:
                    bad.append(f"{sec['id']}: {ref[0]} {ref[1]} {ref[2]} {scope or ''}".strip())
            # a bullet resting ONLY on federal rules must say so in its text —
            # DSG/DSV/BGA/EMBAG bind Bundesorgane, not the canton (KDSG Art. 3 Abs. 1)
            if refs and all(level.get(ref[0]) == "federal" for ref in refs) \
                    and not any(w in (p.get("text") or "") for w in BUND):
                bad.append(f"{sec['id']}: Punkt stützt sich nur auf Bundesrecht, nennt den Bund aber nicht — "
                           f"«{(p.get('text') or '')[:60]}…»")
    return bad


# The owner's rule: open points are GAPS — to be clarified, decided or evidenced — never
# «risk» or «Verstoss» (the verbatim law term «erhöhtes Risiko für die Grundrechte» stays).
# Two texts that reach the page from other sources still frame it otherwise; the page shows
# them in gap wording. Once scripts/labels.py (todo_cats «ermitteln») and scripts/leitfaden.py
# («verwenden») carry the same wording, these replacements find nothing and change nothing.
WORDING = [
    # «Over-collection» is explained once, on #methode; everywhere else the plain words
    ('"basis":"Over-collection"', '"basis":"ohne Grundlage"'),
    # «Korpus» is databank jargon: the other forms of the canton
    ("Der Korpus ist bei diesem Datum selbst gespalten — hier ist nicht dieses Formular die Ausnahme",
     "Die Formulare verlangen diese Angabe uneinheitlich — hier ist nicht dieses Formular die Ausnahme"),
    ("im Korpus", "in den Formularen des Kantons"),
    ("Over-collection ist nur, was weder eine Norm ", "Ohne Grundlage ist nur, was weder eine Norm "),
    ("Eine Wissenslücke der Databank, kein festgestellter Verstoss.",
     "Eine Wissenslücke der Databank, kein Befund über die Verwaltung."),
    ("Wer Dritte bearbeiten lässt oder riskante Bearbeitungen plant, hat zusätzliche Pflichten.",
     "Wer Dritte bearbeiten lässt oder eine Bearbeitung plant, die eine Datenschutz-Folgenabschätzung "
     "verlangt, hat zusätzliche Pflichten."),
]


def gap_wording(text):
    for old, new in WORDING:
        text = text.replace(old, new)
    return text


# What the page reads from the export without a fallback of its own: the figures and the
# classifications computed once in export_json.py. An export that lacks one of them is an
# older one — the page would draw empty cards as if nothing were open, so the build stops.
REQUIRED = {
    "": ("labels", "kopfzahlen", "dienststellen_uebersicht", "forms", "services", "laws",
         "zitate", "datenstand", "verlauf", "gestaltung", "parteien", "konzepte", "wirkung", "register",
         "vorbefuellung", "kennungen", "vertrag", "datenmodell"),
    "labels": ("ton", "ton_map", "kontakt"),
    "kopfzahlen": ("standard_ech", "standard_einheitlich", "standard_benannt", "rechtsgrundlage",
                   "verzeichnis", "offene_punkte", "kein_standard", "kategorien"),
    "kopfzahlen.standard_ech": ("wert", "von", "ech", "ech_ton"),
    "kopfzahlen.standard_benannt": ("begriff_felder", "von", "teile", "formulare_begriff", "formulare_teile"),
    "kopfzahlen.verzeichnis": ("wert", "von", "teile"),
    "kopfzahlen.kein_standard": ("von", "teile", "formulare", "codes"),
    # scripts/gestaltung_export.py (the hook in export_json.py)
    "gestaltung": ("stand", "methode", "bestand", "gruppen", "merkmale", "kennzahlen", "entscheide",
                   "dienststellen", "grenzen", "labels"),
    "gestaltung.bestand": ("formulare", "mit_datei", "ohne_datei", "gemessen", "messart", "dienststellen_gemessen",
                           "dienststellen_ohne_formular"),
    "gestaltung.labels": ("urteil", "ton", "ton_zusatz", "urteil_gesamt", "urteil_nomen", "art", "art_erklaerung",
                          "messart", "gruppe", "merkmal", "eformular", "entscheide"),
}


def missing_keys(export):
    """The keys of REQUIRED the export does not have, as dotted paths; and whether its
    Datenfelder carry the stamped classifications (ech_state, basis_state), its forms
    their Dienststelle, their data-standard figures (standard) and their Gestaltung, and
    its services the file name of their dossier."""
    out = []
    for path, keys in REQUIRED.items():
        node = export
        for part in filter(None, path.split(".")):
            node = node.get(part) if isinstance(node, dict) else None
        out += [f"{path + '.' if path else ''}{k}" for k in keys if not isinstance(node, dict) or k not in node]
    forms = export.get("forms") or []
    fields = [d for fm in forms for d in fm.get("data_fields") or []]
    if any("ech_state" not in d or "basis_state" not in d for d in fields):
        out.append("forms[].data_fields[].ech_state / basis_state")
    if any("dienststelle" not in fm for fm in forms):
        out.append("forms[].dienststelle")
    if any("standard" not in fm for fm in forms if fm.get("data_fields")):
        out.append("forms[].standard")
    if any("dossier_slug" not in s for s in export.get("services") or []):
        out.append("services[].dossier_slug")
    if any("gestaltung" not in fm for fm in forms):
        out.append("forms[].gestaltung")
    return out


# the export contract (exportvertrag.json at the root of the repository): build.sh builds this page
# after every export has stamped its version, so the versions the page shows are the published ones
VERTRAG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exportvertrag.json")


def vertrag_kurz():
    """The export contract as the page «Datenmodell» shows it: per published export its version,
    its JSON Schema and since when the version holds, and the rules of the version numbers. Read
    from exportvertrag.json, which build.sh has written before this step (every export stamps its
    version first): a missing or unreadable file stops the build — a page without the contract
    table must not pass as complete."""
    try:
        with open(VERTRAG_PATH, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as ex:
        raise SystemExit(f"ABBRUCH build_dashboard.py: exportvertrag.json fehlt oder ist nicht lesbar ({ex}) — "
                         "erst die Exporte bauen (./build.sh), die ihn schreiben")
    if not isinstance(doc, dict) or not doc.get("exporte"):
        raise SystemExit("ABBRUCH build_dashboard.py: exportvertrag.json nennt keinen Export")
    ex = {n: {"version": v.get("version"), "schema": v.get("schema"), "seit": v.get("seit")}
          for n, v in (doc.get("exporte") or {}).items()}
    return embed(json.dumps({"exporte": ex, "regeln": doc.get("regeln") or {}}, ensure_ascii=False))


def embed(text):
    """JSON text for a <script> block: every «<» is written as \\u003c, so no harvested
    text — an HTML comment, a script tag — can end or swallow the block. JSON.parse (and
    the JavaScript parser, for the Leitfaden literal) read it back unchanged."""
    return text.replace("<", "\\u003c")


def main():
    with open(EXPORT_PATH, encoding="utf-8") as fh:
        data = gap_wording(fh.read())
    missing = missing_keys(json.loads(data))
    if missing:
        print("ABORT — data_export.json fehlt, was die Seite ohne eigene Berechnung liest "
              "(zuerst python3 scripts/export_json.py):")
        for k in missing:
            print("  ", k)
        sys.exit(1)
    conn = connect(DB_PATH)
    bad = check_guide(conn)
    conn.close()
    if bad:
        print("ABORT — Leitfaden zitiert Regeln, die nicht in der Databank sind:")
        for b in bad[:12]:
            print("  ", b)
        sys.exit(1)
    # inline as JSON text inside a <script type=application/json>, and the Leitfaden as a
    # JavaScript literal — both with every «<» escaped (embed)
    safe = embed(data)
    guide = embed(gap_wording(json.dumps(LEITFADEN, ensure_ascii=False)))
    vertrag = vertrag_kurz()
    fill = lambda tpl: tpl.replace("/*DATA*/", safe).replace("/*GUIDE*/", guide).replace("/*VERTRAG*/", vertrag)
    # the page names its own size: measured on the page itself (the two size
    # words change it by a few bytes only, far below the rounding)
    raw = fill(TEMPLATE).encode("utf-8")
    size, net = size_txt(len(raw)), net_size_txt(raw)
    html = fill(TEMPLATE.replace("%%SIZE%%", size).replace("%%NETSIZE%%", net))
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote {DASHBOARD_PATH}  ({len(html.encode('utf-8'))//1024} KB — page says «knapp {size}, "
          f"über das Netz etwa {net}», Leitfaden: {len(LEITFADEN)} Abschnitte)")


if __name__ == "__main__":
    main()
