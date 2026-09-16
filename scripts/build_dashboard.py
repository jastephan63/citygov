#!/usr/bin/env python3
"""Build dashboard.html from data_export.json (convention 9: generated, never edited).

The JSON is inlined into the HTML so the file opens straight from disk via file://
with no server and no fetch (offline by default). Vanilla JS, no framework.

Views (2026-09 redesign; state lives in the URL hash, so links are shareable):
  * sidebar: Formulare by department/office or flat A–Z, search also matches
    data-field names
  * Überblick & Methode — landing: methodology box, KPI tiles, documentation state
  * Formular-Seite — the per-Formular hub (Datenfelder & Handhabung, Gesetze,
    Beilagen, Blocker, Duplikat-Radar); the old Gesetzes-Baum/Geforderte
    Informationen tabs live here as segments
  * Datenhandhabung / Leitfaden / Verzeichnis / Datenkatalog / eSH-Katalog
Refuses to build when the Leitfaden cites a rule the databank does not hold.

    python3 scripts/build_dashboard.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, EXPORT_PATH, DASHBOARD_PATH, connect
from leitfaden import LEITFADEN

TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
<title>Kanton Schaffhausen — Compliance Databank</title>
<style>
  /* Kanton Schaffhausen paper theme — same family as the formflows prototypes */
  :root{
    --paper:#FAFAF6; --card:#FFFFFF; --field:#F4F1E7;
    --ink:#16150F; --ink-soft:#5C594D; --ink-faint:#8C897C;
    --line:#E4E1D6; --line-soft:#EEEBE1;
    --gold:#F2B705; --gold-deep:#C98E00;
    --federal:#4553B8; --cantonal:#0C8A7B; --communal:#B26A00;
    --match:#2E7D5B; --proposed:#2C6E91; --gap:#C0392B; --over:#B26A00;
    --identity:#0C8A7B; --reason:#5B3E8F; --mechanic:#8C897C;
    --unver:#B03A5B;
    /* aliases kept for the JS template strings */
    --bg:var(--paper); --panel:var(--card); --panel2:var(--field);
    --bd:var(--line); --bd2:var(--line-soft); --tx:var(--ink);
    --mut:var(--ink-soft); --mut2:var(--ink-faint);
  }
  *{box-sizing:border-box}
  body{margin:0;font:13.5px/1.5 'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:var(--paper);color:var(--ink);-webkit-font-smoothing:antialiased}
  code,.mono{font-family:'Roboto Mono',"SF Mono",ui-monospace,Menlo,Consolas,monospace;font-size:12px}
  header{padding:13px 20px;background:var(--card);border-bottom:1px solid var(--line);
         display:flex;align-items:center;gap:13px;flex-wrap:wrap}
  .crest{width:26px;height:30px;flex:none;border-radius:3px;background:var(--gold);position:relative;
         overflow:hidden;box-shadow:inset 0 0 0 1px rgba(0,0,0,.12)}
  .crest::after{content:"";position:absolute;left:50%;top:52%;transform:translate(-50%,-50%);
         width:14px;height:11px;background:var(--ink);
         clip-path:polygon(50% 0,100% 38%,82% 100%,18% 100%,0 38%);opacity:.85}
  header .htxt .sub{font-size:11px;color:var(--ink-faint);font-weight:600;letter-spacing:.4px;text-transform:uppercase}
  header h1{font-size:15px;margin:0;font-weight:700;letter-spacing:-.2px}
  header .stamp{margin-left:auto;color:var(--ink-faint);font-size:11px;text-align:right}
  .warn{background:#FBEDEB;border:1px solid #EAC7C2;color:#8E2F23;padding:5px 12px;
        border-radius:8px;font-size:12px;font-weight:500}
  .layout{display:flex;min-height:calc(100vh - 57px)}
  aside{width:290px;flex:0 0 290px;background:var(--card);border-right:1px solid var(--line);
        padding:16px;overflow:auto}
  aside h2{font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:var(--ink-faint);margin:18px 0 8px}
  aside h2:first-child{margin-top:0}
  .svc{padding:8px 10px;border-radius:8px;cursor:pointer;color:var(--ink-soft);margin-bottom:3px;
       border:1.5px solid transparent;font-size:13px;line-height:1.35;overflow-wrap:anywhere}
  .svc .svname{white-space:normal}
  .svc:hover{background:var(--field);color:var(--ink)}
  .svc.active{background:#FCFAF2;color:var(--ink);border-color:var(--gold-deep)}
  .svc .meta{display:block;font-size:11px;color:var(--ink-faint)}
  /* sidebar grouping: Departement > Amt > Formulare, both levels collapsible */
  .dept{margin-bottom:4px}
  .dephd{padding:7px 9px;border-radius:8px;cursor:pointer;color:var(--ink);font-weight:700;
         font-size:12.5px;display:flex;align-items:center;gap:6px;background:var(--field)}
  .dephd:hover{background:#EEE9DA}
  .dephd .tg{color:var(--ink-faint);width:10px;display:inline-block}
  .dephd .ct{margin-left:auto;font-weight:500;font-size:11px;color:var(--ink-faint)}
  .office{margin:2px 0 2px 8px}
  .offhd{padding:5px 8px;border-radius:6px;cursor:pointer;color:var(--ink-soft);font-size:12px;
         font-weight:600;display:flex;gap:6px}
  .offhd:hover{color:var(--ink)}
  .offhd .ct{margin-left:auto;font-size:10.5px;color:var(--ink-faint)}
  .dept.collapsed .office,.office.collapsed .svc{display:none}
  .tab{display:block;width:100%;text-align:left;padding:9px 11px;border-radius:8px;cursor:pointer;
       background:none;border:1.5px solid transparent;color:var(--ink-soft);font:inherit;font-size:13px;
       font-weight:500;margin-bottom:3px}
  .tab:hover{background:var(--field);color:var(--ink)}
  .tab.active{background:#FCFAF2;color:var(--ink);border-color:var(--gold-deep);font-weight:600}
  main{flex:1;padding:22px 26px;overflow:auto;max-width:1300px}
  h3.view{font-size:16px;margin:0 0 4px;font-weight:700;letter-spacing:-.2px}
  .hint{color:var(--ink-soft);font-size:12px;margin:0 0 18px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:16px}
  .badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:10.5px;font-weight:600;
         vertical-align:middle;white-space:nowrap;border:1px solid transparent}
  .b-federal{color:var(--federal);border-color:#C7CDEB;background:#EDEFF9}
  .b-cantonal{color:var(--cantonal);border-color:#BCE0DB;background:#E7F4F2}
  .b-communal{color:var(--communal);border-color:#EBD3B3;background:#F9F0E2}
  .b-match,.b-mapped,.b-confirmed{color:var(--match);border-color:#BFDCCB;background:#E7F2EC}
  .b-proposed,.b-auto,.b-proposedm{color:var(--proposed);border-color:#BFD8E6;background:#E8F1F6}
  .b-legal_gap,.b-gap{color:var(--gap);border-color:#EAC7C2;background:#FBEDEB}
  .b-overcollection,.b-over{color:var(--over);border-color:#EBD3B3;background:#F9F0E2}
  .b-identity_part{color:var(--identity);border-color:#BCE0DB;background:#E7F4F2}
  .b-reason_facet{color:var(--reason);border-color:#D6C9EC;background:#F0EAF9}
  .b-form_mechanic{color:var(--mechanic);border-color:var(--line);background:var(--field)}
  .b-unver{color:var(--unver);border-color:#E8C3CE;background:#F9EBEF}
  .b-sourced{color:#8F6400;border-color:#EBD9A8;background:#FBF3DC}
  table{border-collapse:collapse;width:100%;font-size:12.5px}
  th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line-soft);vertical-align:top}
  th{color:var(--ink-faint);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
  tr:hover td{background:#FCFAF2}
  .summary{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:6px}
  .gauge{font-size:30px;font-weight:700}
  .pill{padding:6px 12px;border-radius:10px;background:var(--field);border:1px solid var(--line);min-width:96px}
  .pill .n{font-size:19px;font-weight:700;display:block}
  .pill .l{font-size:10.5px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.4px}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .colhead{font-size:12px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.6px;margin:0 0 8px}
  .item{border:1px solid var(--line);border-left-width:3px;border-radius:8px;padding:9px 11px;
        margin-bottom:8px;background:var(--card)}
  .item.match{border-left-color:var(--match)}
  .item.proposed{border-left-color:var(--proposed)}
  .item.legal_gap{border-left-color:var(--gap)}
  .item.overcollection{border-left-color:var(--over)}
  .item .t{font-weight:600}
  .item .d{color:var(--ink-soft);font-size:12px;margin-top:2px}
  .cite{color:var(--ink-soft);font-size:11.5px;margin-top:4px}
  /* law tree (list) */
  .tree{font-size:13px}
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
  .dgbox .sub{color:var(--ink-soft);font-size:11px}
  .dgchildren{margin-left:26px;border-left:2px solid var(--line-soft);padding-left:18px;margin-top:2px}
  .dgnode.collapsed > .dgchildren{display:none}
  .muted{color:var(--ink-soft)} .small{font-size:11.5px}
  .crumb{color:var(--ink-soft);font-size:12px} .crsep{color:var(--ink-faint);margin:0 5px;font-size:11px}
  .ft td b{font-weight:600}
  .dfhdr{display:flex;align-items:center;gap:8px;margin-bottom:6px;padding-bottom:8px;border-bottom:1px solid var(--line-soft)}
  .dfrow{display:grid;grid-template-columns:1fr auto;gap:14px;padding:12px 2px;border-bottom:1px solid var(--line-soft)}
  .dfrow:last-child{border-bottom:none}
  .tp{display:inline-block;font-size:11px;padding:2px 8px;border-radius:6px;background:var(--field);
      color:var(--ink-soft);border:1px solid var(--line);vertical-align:middle}
  .dfname{font-weight:600;font-size:14px;color:var(--ink)}
  .req{font-size:11px;color:var(--gold-deep);margin-left:6px;font-weight:600} .req .ti{font-size:10px}
  .dfdef{font-size:12.5px;color:var(--ink-soft);margin-top:5px;line-height:1.45}
  .dfchips{margin-top:7px} .chip{display:inline-block;font-size:11.5px;background:var(--field);
      border:1px solid var(--line);border-radius:7px;padding:2px 8px;margin:2px 3px 0 0}
  .dfprov{font-size:11px;color:var(--ink-faint);margin-top:6px} .dfprov .ti{font-size:11px;opacity:.7}
  .dfrg{min-width:150px;max-width:340px;text-align:right}
  .b-sens{background:#F3E9F7;color:#7A2E8F;border:1px solid #DFC7E8;font-size:10.5px;padding:1px 8px;
      border-radius:6px;margin-left:6px;font-weight:600}
  .echb{display:inline-block;margin-left:6px;font-size:10px;padding:1px 7px;border-radius:6px;
    background:#E6F0F7;color:#1B5E82;border:1px solid #C3D9E7;text-decoration:none;vertical-align:middle;
    font-family:'Roboto Mono',ui-monospace,monospace}
  .echb:hover{background:#D8E9F4}
  .echb.so{background:#FBF3DC;color:#8F6400;border-color:#EBD9A8}
  .echb.so:hover{background:#F7ECC9}
  .echb.todo{background:#F9F0E2;color:#B4530A;border-color:#EBD3B3;border-style:dashed}
  .echb.todo:hover{background:#F4E7D0}
  .echn{display:inline-block;margin-left:6px;font-size:10px;padding:1px 7px;border-radius:6px;
    background:var(--field);color:var(--ink-faint);border:1px solid var(--line);vertical-align:middle}
  .eshb{display:inline-block;margin-left:6px;font-size:10px;padding:1px 7px;border-radius:6px;
    background:#EFE9F8;color:#5B3E8F;border:1px dashed #C9B8E8;vertical-align:middle;
    font-family:'Roboto Mono',ui-monospace,monospace}
  .eshb .ent{opacity:.8;font-size:9px;letter-spacing:.4px;text-transform:uppercase;margin-left:4px;
    font-family:'Inter',sans-serif}
  .chip.sub{display:inline-flex;align-items:center;gap:5px;padding-right:3px}
  .sfe{font-size:9.5px;font-family:'Roboto Mono',ui-monospace,monospace;padding:1px 5px;border-radius:4px;
    background:#E6F0F7;color:#1B5E82;text-decoration:none;white-space:nowrap}
  .sfe:hover{background:#D8E9F4}
  .sfe.so{background:#FBF3DC;color:#8F6400}
  .sfe.none{background:var(--field);color:var(--ink-faint)}
  .sfe.esh{background:#EFE9F8;color:#5B3E8F;border:1px dashed #C9B8E8}
  .echdraft{display:inline-block;margin-left:5px;font-size:10px;padding:1px 6px;border-radius:6px;
    background:#FBF3DC;color:#8F6400;border:1px solid #EBD9A8;vertical-align:middle}
  .echdraft.susp{background:#F9F0E2;color:#B4530A;border-color:#EBD3B3}
  .echdraft.rep{background:#FBEDEB;color:#C0392B;border-color:#EAC7C2;font-weight:700}
  .fcheck{display:inline-block;font-size:10.5px;font-weight:600;border-radius:6px;padding:1px 8px;
    margin-left:8px;vertical-align:middle}
  .fcheck.ok{background:#E7F2EC;color:#2E7D5B;border:1px solid #BFDCCB}
  .fcheck.warn{background:#F9F0E2;color:#B26A00;border:1px solid #EBD3B3}
  .fcheck.miss{background:var(--field);color:var(--ink-faint);border:1px solid var(--line)}
  .fcheck.gone{background:#F9EBEF;color:#B03A5B;border:1px solid #E8C3CE}
  .dvsh{border-left:3px solid var(--match)}
  .flinks{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:11px 16px}
  .flabel{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--ink-faint)}
  .flink,.srcbtn{display:inline-block;padding:5px 11px;border-radius:8px;border:1px solid var(--line);
    background:var(--card);color:var(--gold-deep);font-size:12px;font-weight:600;text-decoration:none}
  .flink:hover,.srcbtn:hover{border-color:var(--gold-deep)}
  .qd summary{cursor:pointer;color:var(--gold-deep);font-weight:600}
  .quote{font-size:12px;color:var(--ink-soft);background:var(--field);border-left:3px solid var(--gold);
    padding:8px 12px;border-radius:0 8px 8px 0;margin:6px 0 0}
  /* Datenhandhabung: one rule = aspect chip + duty + verbatim law quote */
  .hrule{display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-top:1px dashed var(--line)}
  .hrule:first-child{border-top:none}
  .hasp{flex:0 0 auto;font-size:10.5px;padding:2px 8px;border-radius:999px;margin-top:1px;
    background:#F4EEDF;border:1px solid var(--gold);color:#6B5A22;font-weight:600;white-space:nowrap}
  .hbody{font-size:12.5px;line-height:1.45}
  .hbody .small{margin-top:2px}
  .hgrp{margin-top:10px}
  .hgen{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}
  .hscope{font-size:13.5px;color:var(--ink-soft);margin:18px 2px 8px;text-transform:uppercase;letter-spacing:.4px}
  /* Leitfaden: question -> plain answer -> grounded bullets with rule chips */
  .gsec{max-width:860px}
  .gq{font-size:16px;margin:2px 0 10px;color:var(--ink)}
  .gkurz{background:var(--field);border-left:3px solid var(--gold);border-radius:0 10px 10px 0;
    padding:10px 14px;font-size:13.5px;line-height:1.55;margin-bottom:6px}
  .gklabel,.gplabel{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.6px;
    color:var(--gold-deep);font-weight:700;margin-bottom:3px}
  .gpt{padding:9px 2px 2px;border-top:1px dashed var(--line);font-size:13px;line-height:1.5}
  .gpt:first-of-type{border-top:none}
  .gchips{margin-top:5px}
  .gchip{display:inline-block;font-size:10.5px;padding:1px 8px;margin:2px 4px 0 0;border-radius:999px;
    background:#F4EEDF;border:1px solid var(--gold);color:#6B5A22;font-weight:600;cursor:pointer}
  .gchip:hover{border-color:var(--gold-deep);background:#FCFAF2}
  .gprax{margin-top:10px;background:#F3EEF7;border:1px solid #D8CCE8;border-radius:10px;
    padding:10px 14px;font-size:12.5px;line-height:1.5;color:#4A3C60}
  .gprax .gplabel{color:#7A5EA8}
  /* per-Formular Datenhandhabung profile */
  .pfstrip{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
  .pfc{font-size:11px;padding:3px 10px;border-radius:999px;font-weight:600;border:1px solid var(--line);background:var(--field);color:var(--ink-soft)}
  .pfc.sens{background:#F9E9E4;border-color:#E5B8A8;color:#A04A2E}
  .pfc.law{background:#E7F2EC;border-color:#BFDCCB;color:#2E7D5B}
  .pfc.frist{background:#F4EEDF;border-color:var(--gold-deep);color:#6B5A22}
  .pfc.over{background:#FBEFEF;border-color:#E3B6B6;color:#A33B3B}
  .hstd{font-size:12.5px;line-height:1.55;color:var(--ink-soft);padding:4px 0}
  .hstd.over{color:#A33B3B;border-top:1px dashed var(--line);margin-top:8px;padding-top:8px}
  .hstd .gchip{cursor:default}
  .hcat{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;padding:3px 0}
  /* redesigned navigation: grouped tabs with question subtitles */
  .tabsub{display:block;font-size:10px;font-weight:400;color:var(--ink-faint);margin-top:1px;line-height:1.3}
  .tab.active .tabsub{color:var(--ink-soft)}
  .legsub{font-size:10px;font-weight:400;text-transform:none;letter-spacing:0}
  /* consistent page header: what / source / how-to-read */
  .pagehead{background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:11px 16px;margin-bottom:14px;font-size:12.5px;line-height:1.55}
  .pagehead>div{margin:3px 0}
  .phl{display:inline-block;min-width:150px;font-size:10px;text-transform:uppercase;
    letter-spacing:.5px;color:var(--gold-deep);font-weight:700;vertical-align:top}
  /* landing page */
  .methodbox{background:var(--field);border-left:3px solid var(--gold);border-radius:0 10px 10px 0;
    padding:10px 14px;font-size:12.5px;line-height:1.6}
  .methodbox>div{margin:4px 0}
  .hometiles{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px}
  .hometile{flex:1 1 130px;background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:10px 8px;cursor:pointer;text-align:center}
  .hometile:hover{border-color:var(--gold-deep)}
  .htn{display:block;font-size:19px;font-weight:700;color:var(--gold-deep)}
  .htl{display:block;font-size:11px;color:var(--ink-soft);margin-top:2px}
  /* form-page hub head */
  .hubhead{padding:10px 16px}
  .hubrow{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:12px}
  .ampel{font-size:15px;line-height:1}
  .a-gruen{color:#2E7D5B}.a-gelb{color:#C98A00}.a-rot{color:#B3372F}
  .hubchan{font-weight:600;color:var(--ink-soft)}
  .hubsig{color:#B3372F;font-weight:600}
  .hubsig.ok{color:#2E7D5B}
  .hubmeta{color:var(--ink-faint)}
  .hubout{margin-top:7px;font-size:12.5px}
  .hubburden{margin-top:5px;font-size:12.5px;color:var(--ink-soft)}
  /* Beilagen */
  .beirow{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;padding:4px 0;
    border-top:1px dashed var(--line);font-size:12.5px}
  .beirow:first-of-type{border-top:none}
  .beiob{font-size:10px;padding:1px 7px;border-radius:999px;font-weight:700;border:1px solid var(--line);color:var(--ink-soft)}
  .beiob.zwingend{background:#F9E9E4;border-color:#E5B8A8;color:#A04A2E}
  .beiob.bedingt{background:#F4EEDF;border-color:var(--gold);color:#6B5A22}
  .beih{margin-left:auto;font-size:11px;color:var(--ink-faint)}
  .beih.f{color:#2E7D5B;font-weight:600}
  .simlink{color:var(--gold-deep);cursor:pointer;text-decoration:none;font-weight:600}
  .simlink:hover{text-decoration:underline}
  .lawforms summary{cursor:pointer;font-size:11.5px;color:var(--gold-deep);font-weight:600;margin-top:6px}
  .flash{outline:2px solid var(--gold-deep);outline-offset:2px}
  .katrow{cursor:pointer}
  .katforms td{background:var(--field);font-size:11.5px;line-height:1.7}
  /* Service-Dossier */
  .svclaws{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 12px;
    background:var(--card);border:1px solid var(--line);border-radius:12px;padding:9px 14px}
  .lawchip{font-size:11.5px;padding:2px 9px;border-radius:999px;border:1px solid var(--gold);
    background:#FCFAF2;color:var(--ink);text-decoration:none;font-weight:600}
  .lawchip:hover{border-color:var(--gold-deep)}
  .hsl{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--gold-deep);
    font-weight:700;margin-right:6px}
  .verf summary{cursor:pointer;padding:2px 0}
  .verf>summary b{font-size:14px}
  .hstrip{display:flex;flex-wrap:wrap;gap:14px;border-top:1px dashed var(--line);
    margin-top:7px;padding-top:7px;font-size:12px;align-items:baseline}
  .hs{display:inline-flex;align-items:baseline;gap:4px;flex-wrap:wrap}
  .formsec{border-left:3px solid var(--gold);padding-left:12px;margin:0 0 22px}
  /* per-field Handhabung line: standard datatype, retention, stricter ⛨ rules */
  .dfhb{font-size:11.5px;color:var(--ink-soft);margin:2px 0 1px;display:flex;gap:5px;
    align-items:baseline;flex-wrap:wrap}
  .edt{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;background:var(--field);
    border:1px solid var(--line);border-radius:6px;padding:0 6px}
  /* Handlungsbedarf board + global search */
  .gsearch{margin-left:auto;min-width:240px;max-width:420px;flex:1;border:1px solid var(--line);border-radius:8px;
    padding:6px 10px;font:inherit;font-size:13px;background:var(--field)}
  .todocats{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 12px;align-items:center}
  .tcat{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:999px;
    padding:3px 10px;font-size:12px;cursor:pointer;background:#fff}
  .tcat.on{border-color:currentColor;box-shadow:0 0 0 1px currentColor inset}
  .tcat b{font-variant-numeric:tabular-nums}
  .todoexpl summary{cursor:pointer}
  .todoexpl td{vertical-align:top;font-size:12.5px}
  .dsthead{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;margin-bottom:4px}
  .dsthead h4{margin:0;font-size:15px}
  .dstkontakt{font-size:12px;color:var(--ink-soft);margin-bottom:4px}
  .tchip{cursor:pointer;margin:2px 4px 2px 0;display:inline-block}
  .tchip b{font-variant-numeric:tabular-nums}
  .sres .srow{display:flex;gap:10px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--line)}
  .sres .srow:last-of-type{border-bottom:0}
  .stype{font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--ink-soft);min-width:84px}
  .slink:hover{text-decoration:underline}
  mark.hl{background:#FFF1B8;color:inherit;padding:0 1px;border-radius:2px}
  /* Rechtsmittel line under the Verfahrens-Ergebnis */
  .hubout.rm{display:flex;flex-wrap:wrap;gap:6px 8px;align-items:baseline}
  .rmlbl{font-weight:600}
  .hubout.rm details.qd summary{font-size:12px}
  .rmcand{margin:2px 0 8px 14px}
  .rmcand summary{font-size:12px;color:var(--ink-soft);cursor:pointer}
  .rmc{margin:6px 0 0 8px}
  .rmc blockquote.quote{margin:2px 0 0}
  /* Datenfluss diagram + Bürgersicht */
  .synth{background:#FBEAEA;border:1px solid #E8B4B4;color:#7A1F1F;border-radius:8px;padding:8px 12px;
    font-weight:600;font-size:13px;margin:0 0 10px}
  .flowsvg{width:100%;height:auto;display:block;font-size:11.5px}
  .flowsvg .flowhd{font-size:11px;font-weight:700;fill:var(--ink-soft);text-transform:uppercase;letter-spacing:.04em}
  .flowsvg .fn{cursor:pointer;fill:#1F2A37}
  .flowsvg .fn:hover{text-decoration:underline}
  .flowsvg .fe{stroke:#8F6400;stroke-opacity:.55;transition:stroke-opacity .15s;cursor:pointer}
  .flowsvg .fe.systematisch{stroke:#1F5A3A}
  .flowsvg .fe.auf_anfrage{stroke-dasharray:5 4}
  .flowsvg .fe:hover{stroke-opacity:1}
  .flowsvg .fe.dim{stroke-opacity:.08}
  .flowleg{display:flex;gap:16px;align-items:center;font-size:12px;margin-bottom:6px}
  .flowleg .fl{display:inline-block;width:26px;height:0;border-top:2px solid #1F5A3A;vertical-align:middle;margin-right:4px}
  .flowleg .fl.anf{border-top:2px dashed #8F6400}
  .lkrow{display:flex;align-items:center;gap:10px;margin:3px 0}
  .lky{font-variant-numeric:tabular-nums;min-width:40px;font-size:12.5px}
  /* once-only: the Einwohnerregister already holds this datum */
  .regc{font-size:10.5px;color:#1F5A3A;background:#E3F2E8;border:1px solid #B9DEC6;
    border-radius:6px;padding:0 6px;white-space:nowrap}
  .chip.sub .regc{margin-left:4px;padding:0 4px}
  /* navigation redesign: browse modes, breadcrumb, Formular quick-jump */
  .navmodes{display:flex;gap:6px;margin:0 0 8px}
  .navmodes button{flex:1;padding:5px 8px;border-radius:8px;border:1px solid var(--line);
    background:var(--card);color:var(--ink-soft);font-size:11.5px;cursor:pointer;font-weight:600}
  .navmodes button.active{border-color:var(--gold-deep);color:var(--ink);background:#FCFAF2}
  .fnav .meta{display:block;font-size:10px;color:var(--ink-faint)}
  .bcrumb{display:flex;gap:8px;align-items:center;font-size:12px;color:var(--ink-faint);margin:0 0 4px}
  .bcrumb a{color:var(--gold-deep);cursor:pointer;font-weight:600}
  .bcrumb a:hover{text-decoration:underline}
  .fjump{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 10px}
  .fjc{font-size:11.5px;padding:3px 10px;border-radius:999px;border:1px solid var(--gold);
    background:#FCFAF2;cursor:pointer;color:var(--ink)}
  .fjc:hover{border-color:var(--gold-deep)}
  /* Verzeichnis + Datenkatalog */
  .regstats{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
  .rstat{font-size:12px;padding:6px 12px;border-radius:10px;background:var(--card);border:1px solid var(--line)}
  .rstat b{color:var(--gold-deep)}
  .rstat.warn{border-color:#E5B8A8;background:#F9E9E4}
  .miss{color:#A33B3B;font-weight:600;font-size:11px}
  .empchip{display:inline-block;font-size:11px;padding:2px 9px;margin:2px 4px 0 0;border-radius:999px;
    background:#E7F2EC;border:1px solid #BFDCCB;color:#2E7D5B;font-weight:600}
  .zweckline{font-size:12.5px;color:var(--ink-soft);margin:-4px 0 10px;font-style:italic}
  .nodv{color:var(--communal);margin-right:4px}
  .esvc{display:inline-block;font-size:10px;background:#E8F1F6;color:#2C6E91;border:1px solid #BFD8E6;
    border-radius:6px;padding:0 6px;margin-left:6px;font-weight:600}
  .b-nodv{background:#F9F0E2;color:#B26A00;border:1px solid #EBD3B3;font-size:10.5px;padding:2px 8px;
    border-radius:6px;white-space:nowrap;font-weight:600}
  .b-dvsh{background:#E7F2EC;color:#2E7D5B;border:1px solid #BFDCCB;font-size:10.5px;padding:2px 8px;
    border-radius:6px;font-weight:700}
  .stale{display:inline-flex;gap:6px;align-items:center;background:#FBEDEB;color:#C0392B;
    border:1px solid #EAC7C2;font-size:11.5px;font-weight:600;border-radius:8px;padding:3px 9px;margin-left:8px}
  .seg{display:inline-flex;border:1.5px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:14px}
  .seg button{border:none;background:var(--card);color:var(--ink-soft);font:inherit;font-size:12.5px;
    font-weight:600;padding:6px 14px;cursor:pointer}
  .seg button.active{background:var(--field);color:var(--ink)}
  .pbar{height:8px;border-radius:5px;background:var(--field);border:1px solid var(--line);
    overflow:hidden;flex:1;min-width:140px;max-width:280px}
  .pbar > i{display:block;height:100%;background:var(--match)}
  .nores{color:var(--ink-faint);padding:30px 0;text-align:center}
  .legend{font-size:11.5px;color:var(--ink-soft);line-height:2}
  input#svcfilter{width:100%;padding:8px 10px;margin-bottom:8px;background:var(--card);
    border:1.5px solid var(--line);border-radius:8px;color:var(--ink);font:inherit;font-size:12.5px}
  input#svcfilter:focus{outline:none;border-color:var(--gold-deep);box-shadow:0 0 0 3px rgba(242,183,5,.25)}
</style>
</head>
<body>
<header>
  <div class="crest" aria-hidden="true"></div>
  <div class="htxt"><div class="sub">Kanton Schaffhausen</div>
    <h1>Compliance-Databank · Formulare, Recht &amp; Standards</h1></div>
  <input id="gsearch" class="gsearch" type="search" placeholder="Suche über alles: Gesetz, Artikel, Datenfeld, Regel, Empfänger, Dienststelle …" title="Volltextsuche über alle Inhalte der Databank — Enter oder kurz warten">
  <span class="warn" id="warn"></span>
  <span class="stamp" id="stamp"></span>
</header>
<div class="layout">
  <aside>
    <h2>Einstieg</h2>
    <button class="tab" data-tab="home">Überblick &amp; Methode<span class="tabsub">Was ist diese Databank, wie arbeitet sie?</span></button>
    <h2>Nachschlagewerke</h2>
    <button class="tab" data-tab="rules">Datenhandhabung<span class="tabsub">Die Regeln im Wortlaut, je Gesetz</span></button>
    <button class="tab" data-tab="guide">Leitfaden<span class="tabsub">Dieselben Regeln in einfacher Sprache</span></button>
    <button class="tab" data-tab="katalog">Datenkatalog<span class="tabsub">Jedes Datum einmal: Standards &amp; Once-Only</span></button>
    <button class="tab" data-tab="datenfluss">Datenfluss<span class="tabsub">Wer gibt wem Daten weiter — belegte Bekanntgaben</span></button>
    <button class="tab" data-tab="esh">eSH-Katalog (Entwurf)<span class="tabsub">Kantonaler Standard-Vorschlag für eCH-Lücken</span></button>
    <h2>Angewandt (Datentresor, synthetisch)</h2>
    <button class="tab" data-tab="buerger">Bürgersicht<span class="tabsub">Was der Kanton über eine Person gespeichert hat</span></button>
    <h2>Steuerung &amp; Lücken</h2>
    <button class="tab" data-tab="register">Verzeichnis der Bearbeitungen<span class="tabsub">Registerstruktur nach KDSG Art. 17b Abs. 2 &amp; DSFA-Triage</span></button>
    <button class="tab" data-tab="todo">Handlungsbedarf<span class="tabsub">Alle offenen Punkte je Dienststelle, mit Kontakt</span></button>
    <h2>Formulare &amp; Dienste</h2>
    <div id="services"></div>
    <h2>Legende <span class="legsub">— Badges dieser Seite</span></h2>
    <div class="legend" id="legend"></div>
  </aside>
  <main id="main"></main>
</div>
<script id="data" type="application/json">/*DATA*/</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const GUIDE = /*GUIDE*/;
const state = {service:'all', tab:'home', sub:'felder', tree:'list', filter:'', open:{}, navmode:'services'};
// shareable links: state lives in location.hash (#tab/serviceId/sub), read at
// startup and on back/forward, written by render()
function readHash(){
  // ALWAYS reset every part: a missing segment means its default, otherwise a
  // stale state.sub survives the browser's Back and the old hash gets
  // re-pushed — the "back button does nothing" loop
  const p=(location.hash||'').replace(/^#/,'').split('/');
  state.tab=p[0]||'home';
  state.service=p[1]||'all';
  state.sub=p[2]||'felder';
}
let _writingHash=false;
function writeHash(){
  const h='#'+state.tab+(state.service!=='all'||state.sub!=='felder'?'/'+state.service:'')+(state.sub!=='felder'?'/'+state.sub:'');
  if(location.hash!==h){_writingHash=true;location.hash=h;}
}
window.addEventListener('hashchange',()=>{
  if(_writingHash){_writingHash=false;return;}
  readHash();render();
});
const DEPT_ORDER=['Baudepartement','Department des Innern','Departement des Innern','Erziehungsdepartement','Finanzdepartement','Volkswirtschaftsdepartement'];
function deptName(s){return (s.department||'(ohne Departement)').trim();}

// ---- indexes + in-browser reconciliation (computed, never stored) ----------
const reqById={}, lawById={}, svcById={};
DATA.requirements.forEach(r=>reqById[r.id]=r);
DATA.laws.forEach(l=>lawById[l.id]=l);
DATA.services.forEach(s=>svcById[s.id]=s);
const reqsByService={}, formsByService={};
DATA.service_requirements.forEach(sr=>{(reqsByService[sr.service_id]=reqsByService[sr.service_id]||[]).push(sr.requirement_id);});
DATA.forms.forEach(f=>{(formsByService[f.service_id]=formsByService[f.service_id]||[]).push(f);});
// department -> office -> services
const deptTree={};
DATA.services.forEach(s=>{const d=deptName(s), o=(s.dienststelle||'(ohne Amt)').trim();
  (deptTree[d]=deptTree[d]||{})[o]=(deptTree[d][o]||[]); deptTree[d][o].push(s);});
function deptKeys(){return Object.keys(deptTree).sort((a,b)=>{
  const ia=DEPT_ORDER.indexOf(a), ib=DEPT_ORDER.indexOf(b);
  return (ia<0?99:ia)-(ib<0?99:ib) || a.localeCompare(b);});}
// documentation state per service, computed on the CURATED data_field layer
// (same numbers as every detail page): a field counts as settled when it has a
// verified basis OR is proven no_basis (over-collection) — both are answers.
function grounding(sid){
  let need=0, have=0;
  (formsByService[sid]||[]).forEach(fm=>(fm.data_fields||[]).forEach(d=>{
    need++;
    if((d.legal_basis||[]).length || d.basis_typ==='aufgabe' || d.basis_typ==='ohne') have++;}));
  return {need,have};
}

const esc = s => (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
// render a full-depth field label 'Section › Group › Leaf' as a breadcrumb:
// ancestors muted, leaf bold, so a sub-field reads standalone.
function fmtPath(p){
  const segs=String(p||'').split('›').map(s=>s.trim()).filter(Boolean);
  if(!segs.length) return '';
  const leaf=segs.pop();
  const pre=segs.map(s=>`<span class="crumb">${esc(s)}</span>`).join('<span class="crsep">›</span>');
  return (pre?pre+'<span class="crsep">›</span>':'')+`<b>${esc(leaf)}</b>`;
}
const el = (h)=>{const d=document.createElement('div');d.innerHTML=h;return d.firstElementChild;};
const jur = j => `<span class="badge b-${j}">${({federal:'Bund',cantonal:'Kanton',communal:'Gemeinde'}[j]||j)}</span>`;
function unver(lc){   // three verification levels
  if(!lc || lc==='UNVERIFIED') return ` <span class="badge b-unver" title="nicht verifiziert, keine Quelle">UNVERIFIED</span>`;
  if(lc==='verified') return ` <span class="badge b-match" title="live gegen Fedlex/Register verifiziert">verifiziert</span>`;
  if(/^Gesetze/.test(lc)) return ` <span class="badge b-sourced" title="aus dem amtlichen SHR-Gesetzes-PDF gelesen; Live-Abgleich noch offen">Quelle ${esc(lc.replace('Gesetze-PDF ',''))}</span>`;
  if(/^zitiert/.test(lc)) return ` <span class="badge b-sourced" title="im Formular zitiert; noch nicht gegen Gesetze/Fedlex verifiziert">zitiert (unverif.)</span>`;
  return ` <span class="badge b-unver">${esc(lc)}</span>`;
}
function artLabel(no){
  if(!no || no==='UNKNOWN') return 'Art. UNBEKANNT';
  return /^(§|Art)/.test(no) ? no : 'Art. '+no;   // Swiss acts use Art. or §
}
function citeStr(lb){
  const art = artLabel(lb.article_no);
  const det = lb.citation_detail ? ' '+lb.citation_detail : '';
  const sr  = lb.sr_number ? ' · SR '+lb.sr_number : (lb.cantonal_ref ? ' · '+lb.cantonal_ref : '');
  return `${jur(lb.jurisdiction)} <span class="mono">${esc(art+det)}</span> ${esc(lb.law_short||lb.law_title)}${esc(sr)}${unver(lb.last_checked)}`;
}

// no explicit article is NOT one thing: needed for the task (KDSG Art. 4 lit. b),
// genuinely surplus, not yet assessed, or not yet researched at all
function basisBadge(d){
  const why=d.basis_begruendung?' — '+esc(d.basis_begruendung):'';
  if(d.basis_typ==='aufgabe') return `<span class="badge b-sourced" title="Keine Norm nennt dieses Feld ausdrücklich, aber die Aufgabe ist ohne dieses Datum nicht erfüllbar — zulässig nach KDSG Art. 4 Abs. 1 lit. b${why}">aufgabennotwendig — keine explizite Norm</span>`;
  if(d.basis_typ==='ohne') return `<span class="badge b-over" title="Weder eine Norm noch die Aufgabe verlangen dieses Feld — nur freiwillig erhebbar (Leitfaden «Erheben»)${why}">Over-collection — weder Norm noch Aufgabenbedarf</span>`;
  if(d.basis_typ==='offen') return `<span class="badge b-unver" title="Keine explizite Norm; ob die Aufgabe das Feld zwingend braucht, ist noch nicht beurteilt">keine explizite Norm — Aufgabenbedarf offen</span>`;
  return `<span class="badge b-unver" title="Noch nicht juristisch ermittelt — heisst NICHT, dass keine Grundlage existiert; hier fehlt Recherche, kein Recht">Rechtsgrundlage zu ermitteln</span>`;
}

// ---------- sidebar (grouped by department) ----------
function renderSidebar(){
  const nForms=DATA.forms.length;
  const nEs=DATA.services.filter(x=>!(formsByService[x.id]||[]).length).length;
  // count the ATOMIC data: a composite's subfields replace it, since each carries its own element
  let dfN=0,dfE=0;
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>{
    const ss=(d.subfields||[]).filter(s=>s&&typeof s==='object'&&s.name);
    if(ss.length){ ss.forEach(s=>{dfN++; if(s.ech) dfE++;}); }
    else { dfN++; if(d.ech) dfE++; }
  }));
  const ech = dfN ? ` · ${dfE}/${dfN} Datenfelder mit eCH-Standard (${Math.round(dfE*100/dfN)} %)` : '';
  document.getElementById('stamp').textContent =
    `${nForms} Formulare · ${nEs} eServices ohne Formular${ech} — erzeugt ${DATA.generated_at||''}`;
  document.getElementById('warn').textContent = '⚠ Zitate „UNVERIFIED“ sind NICHT amtlich geprüft';
  const sv = document.getElementById('services'); sv.innerHTML='';
  const fb=el(`<input id="svcfilter" placeholder="Formular, Amt oder Datenfeld suchen…" value="${esc(state.filter)}" `+
    `style="width:100%;padding:7px 9px;margin-bottom:8px;background:var(--panel);border:1px solid var(--bd);`+
    `border-radius:7px;color:var(--tx);font-size:12.5px">`);
  sv.appendChild(fb);
  fb.oninput=()=>{state.filter=fb.value;(state.navmode==='formulare'?renderFormNav:renderNav)();};
  // two browse modes: by SERVICE (department tree) or by FORMULAR (flat A–Z)
  const modes=el(`<div class="navmodes">
    <button data-nm="services" class="${state.navmode==='services'?'active':''}">nach Service</button>
    <button data-nm="formulare" class="${state.navmode==='formulare'?'active':''}">nach Formular</button></div>`);
  sv.appendChild(modes);
  modes.querySelectorAll('button').forEach(b=>b.onclick=()=>{state.navmode=b.dataset.nm;renderSidebar();});
  const allr=el(`<div class="svc" style="margin-left:0;font-weight:600">▤ Alle Dienste · Übersicht <span class="meta">${DATA.services.length} Dienste, ${deptKeys().length} Departemente</span></div>`);
  if(state.service==='all') allr.classList.add('active');
  allr.onclick=()=>{state.service='all';state.sub='felder';state.tab='fields';render();};
  sv.appendChild(allr);
  const nav=el('<div id="nav"></div>'); sv.appendChild(nav);
  if(state.navmode==='formulare') renderFormNav(); else renderNav();
  document.querySelectorAll('.tab').forEach(b=>{
    b.classList.toggle('active', b.dataset.tab===state.tab);
    b.onclick=()=>{state.tab=b.dataset.tab;render();};
  });
  // context legend: explain only the badges the CURRENT page actually shows
  const LEG = {
    fields: [
      ['b-match','verifiziert — live gegen Fedlex/Rechtsbuch geprüft'],
      ['b-sourced','Quelle SHR-PDF — aus dem amtlichen Gesetzes-PDF gelesen'],
      ['b-unver','UNVERIFIED — noch nicht am Gesetzestext geprüft (Wissenslücke, kein Verstoss)'],
      ['b-sourced','aufgabennotwendig — keine explizite Norm, aber für die Aufgabe nötig (KDSG Art. 4 Abs. 1 lit. b)'],
      ['b-over','Over-collection — weder Norm noch Aufgabenbedarf'],
      ['b-sens','⛨ besonders schützenswert (Art. 5 lit. c DSG)'],
      ['regc','↺ vorbefüllbar — das Einwohnerregister führt dieses Datum bereits (Once-Only)'],
      ['b-dvsh','DVSH — amtliches Dienstleistungsmodell des Kantons (read-only Quelle)'],
      ['b-federal','Bund'],['b-cantonal','Kanton'],['b-communal','Gemeinde'],
    ],
    rules: [['b-sens','⛨ kategorienspezifische Regel'],['b-unver','Zitat unverifiziert'],
            ['b-federal','Bund'],['b-cantonal','Kanton']],
    register: [['b-sens','⛨ besonders schützenswerte Felder'],['b-over','ohne gesetzliche Grundlage'],
               ['b-unver','offen / fehlt']],
    todo: [['b-unver','Wissenslücke oder ausstehender Entscheid'],['b-over','Bereinigung nötig (Over-collection, veraltete Fassung, aufgehobener Standard)'],
           ['b-sens','⛨ DSFA-Entscheid offen']],
    search: [['b-federal','Bund'],['b-cantonal','Kanton'],['b-communal','Gemeinde']],
    datenfluss: [['b-sourced','systematisch — regelmässige Meldung von Gesetzes wegen'],['b-unver','auf Anfrage — Amtshilfe im Einzelfall']],
    buerger: [['b-sens','⛨ besonders schützenswert / verschlüsselt gespeichert'],['b-over','auf Einwilligung gestützt'],['regc','↺ Once-Only wiederverwendet']],
    katalog: [['b-dvsh','Datum liegt im Einwohnerregister'],['b-sens','⛨ in sensitivem Kontext erhoben']],
  };
  const rows=(LEG[state.tab]||[['b-federal','Bund'],['b-cantonal','Kanton']]);
  document.getElementById('legend').innerHTML =
    rows.map(([c,l])=>`<span><span class="badge ${c}">&nbsp;</span> ${l}</span>`).join('');
}
// flat A–Z Formular navigation: one row per Formular, click = Einzelansicht
const formNavIdx=DATA.forms.map(f=>{
  const svc=svcById[f.service_id]||{};
  return {fid:f.id, sid:f.service_id, t:f.title, o:svc.dienststelle||f.publisher_dienststelle||'',
          k:(f.title+' '+(svc.name||'')+' '+(svc.name_alt||'')+' '+(svc.dienststelle||'')).toLowerCase()};
}).sort((a,b)=>a.t.localeCompare(b.t,'de'));
function renderFormNav(){
  const f=state.filter.toLowerCase(); const nav=document.getElementById('nav'); if(!nav)return;
  const hits=formNavIdx.filter(x=>!f||x.k.includes(f)||(f.length>=3&&(fieldIdx[x.sid]||'').includes(f)));
  nav.innerHTML=`<div class="muted small" style="margin:2px 0 6px">${hits.length} Formulare A–Z — Klick öffnet die Formular-Ansicht</div>`+
    (hits.map(x=>`<div class="svc fnav ${state.sub==='form-'+x.fid?'active':''}" data-fid="${x.fid}" data-sid="${x.sid}">
      <span class="svname" title="${esc(x.t)} — ${esc(x.o)}">${esc(x.t)}</span>
      <span class="meta">${esc(x.o)}</span></div>`).join('')||'<div class="nores small">keine Treffer</div>');
  nav.querySelectorAll('.fnav').forEach(e=>e.onclick=()=>{
    state.service=e.dataset.sid;state.tab='fields';state.sub='form-'+e.dataset.fid;render();});
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
      deptHTML+=`<div class="office ${offOpen?'':'collapsed'}"><div class="offhd" data-o="${esc(d+'›'+o)}">`+
        `<span class="tg">${offOpen?'▾':'▸'}</span>${esc(o)}<span class="ct">${svcs.length}</span></div>`+
        svcs.map(s=>`<div class="svc ${String(s.id)===state.service?'active':''}" data-sid="${s.id}">`+
          `${s.in_dvsh?'':'<span class="nodv" title="nicht im DVSH-Modell">◇</span>'}<span class="svname" title="${esc(s.name)}${s.dienststelle?' — '+esc(s.dienststelle):''}">${esc(s.name)}</span>`+
          `${(formsByService[s.id]||[]).length?'':'<span class="esvc" title="Online-/eService ohne herunterladbares Formular">eService</span>'}</div>`).join('')+`</div>`;
    });
    if(!svcMatch) return;
    const open = f || state.open[d];
    h+=`<div class="dept ${open?'':'collapsed'}"><div class="dephd" data-d="${esc(d)}">`+
       `<span class="tg">${open?'▾':'▸'}</span>${esc(d)}<span class="ct">${svcMatch}</span></div>${deptHTML}</div>`;
  });
  nav.innerHTML=h || '<div class="nores small">keine Treffer</div>';
  nav.querySelectorAll('.dephd').forEach(e=>e.onclick=()=>{const d=e.dataset.d;state.open[d]=!state.open[d];renderNav();});
  nav.querySelectorAll('.offhd').forEach(e=>e.onclick=()=>{const k=e.dataset.o;state.open[k]=!state.open[k];renderNav();});
  // a form click ALWAYS opens the form page — on corpus tabs a mere selection
  // change would be invisible and read as a broken click
  nav.querySelectorAll('.svc[data-sid]').forEach(e=>e.onclick=()=>{
    state.service=e.dataset.sid;state.tab='fields';state.sub='felder';render();});
}

// ---------- PRIMARY: fields & legal basis ----------
// consistent page header: what the page shows, where its data comes from,
// and how to read it — pitched at a peer who knows the domain, not a novice
function pageHead(title, was, quelle, lesen){
  return `<h3 class="view">${title}</h3>
  <div class="pagehead">
    <div><span class="phl">Was zeigt diese Seite</span>${was}</div>
    <div><span class="phl">Datenherkunft</span>${quelle}</div>
    ${lesen?`<div><span class="phl">Lesehinweis</span>${lesen}</div>`:''}
  </div>`;
}
// ---------- Überblick & Methode (the landing page) ----------
function viewHome(){
  const m=document.getElementById('main');
  const F=DATA.forms, H=DATA.datenhandhabung||[], K=DATA.attribut_katalog||[];
  let nDf=0,nOver=0,nAuf=0,nSens=0,nEch=0,nPts=0;
  F.forEach(f=>(f.data_fields||[]).forEach(d=>{
    nDf++; if(d.basis_typ==='ohne')nOver++; if(d.basis_typ==='aufgabe')nAuf++; if(d.sensitive)nSens++;
    const ss=(d.subfields||[]).filter(s=>s&&typeof s==='object'&&s.name);
    (ss.length?ss:[d]).forEach(u=>{nPts++;if(u.ech)nEch++;});
  }));
  const tile=(n,l,tab)=>`<button class="hometile" data-go="${tab}"><span class="htn">${n}</span><span class="htl">${l}</span></button>`;
  m.innerHTML=`<h3 class="view">Compliance-Databank Kanton Schaffhausen</h3>
  <div class="card">
    <p style="font-size:13.5px;line-height:1.6;margin:0 0 10px">Diese Databank erfasst pro <b>Formular</b> der kantonalen
    Verwaltung: die <b>Gesetze</b>, die es verlangen (artikelgenau), die <b>Datenfelder</b>, die es erhebt (bis aufs
    atomare Teilfeld), den <b>Standard</b> jedes Datums (eCH, ersatzweise der kantonale Entwurf eSH), die
    <b>Handhabungsregeln</b> (Speichern, Weitergeben, Löschen — mit Wortlaut-Zitat) und den <b>Digitalisierungs-Stand</b>.
    Konsument ist neben Menschen ein LLM-Agent, der Verwaltungsleistungen abwickeln soll — deshalb muss jede Angabe
    <b>präzise, belegt und nie stillschweigend falsch</b> sein.</p>
    <div class="methodbox"><b>Methode — was hier «verifiziert» heisst</b>
      <div>• <b>Proof-Gates:</b> Agenten erarbeiten Zuordnungen, aber Loader lehnen alles ab, was nicht existiert:
      ein Gesetzesartikel muss ingestiert sein, ein eCH-Element muss im offiziellen XSD stehen, ein Regel-Zitat muss
      wörtlich im Gesetzes-PDF vorkommen, eine Frist-Zahl muss im Zitat stehen.</div>
      <div>• <b>Drei Verifikationsstufen</b> an jeder Zitation: <span class="badge b-match">verifiziert</span> (live
      gegen Fedlex/Rechtsbuch) · <span class="badge b-sourced">Quelle SHR-PDF</span> (aus dem amtlichen PDF gelesen) ·
      <span class="badge b-unver">UNVERIFIED</span> (noch ungeprüft — eine Wissenslücke der Databank, kein Befund über
      die Verwaltung).</div>
      <div>• <b>Lücke = Lücke:</b> Fehlendes steht als «fehlt», «kein Standard», «zu ermitteln» offen da. Eine
      geschönte 100%-Anzeige wäre hier ein Defekt.</div>
      <div>• <b>Quellen:</b> das DVSH-Dienstleistungsmodell des Kantons (Source of Truth, strikt read-only
      geharvestet) · das publizierte SHEP-Portal (Bürger-Sicht) · die amtlichen Formulare selbst ·
      Gesetzestexte (Schaffhauser Rechtsbuch SHR, Fedlex) · die eCH-Standards von ech.ch.
      <b>eSH</b> ist unser eigener Entwurf für Daten ohne eCH-Standard — überall als «Entwurf» markiert, nie mit
      offiziellem eCH verwechselbar.</div>
    </div>
  </div>
  <div class="hometiles">
    ${tile(DATA.services.filter(s=>s.dvsh).length,'Services im DVSH modelliert','fields')}
    ${tile(DATA.services.filter(s=>s.shep).length,'auf SHEP publiziert','fields')}
    ${tile(F.length,'Formulare','fields')}
    ${tile(nDf.toLocaleString('de-CH'),'Datenfelder','fields')}
    ${tile(Math.round(100*nEch/nPts)+'%','atomare Punkte mit eCH','katalog')}
    ${tile(H.length,'Regeln, Zitat PDF-verifiziert','rules')}
    ${tile(nOver,'Over-collection (Felder)','register')}
    ${tile(nAuf,'aufgabennotwendig ohne Norm','register')}
    ${tile(nSens,'⛨ sensible Felder','register')}
    ${tile(K.length.toLocaleString('de-CH'),'einzigartige Daten','katalog')}
    ${tile((DATA.esh_katalog||[]).length,'eSH-Entwürfe','esh')}
  </div>
  ${deptOverview()}`;
  m.querySelectorAll('.hometile').forEach(b=>b.onclick=()=>{state.tab=b.dataset.go;render();});
  m.querySelectorAll('tr[data-sid]').forEach(tr=>tr.onclick=()=>{
    state.service=tr.dataset.sid;state.tab='fields';state.sub='felder';render();});
}
function deptOverview(){
  const f=state.filter.toLowerCase();
  let h=`<h3 class="view">Übersicht nach Departement</h3>
  <p class="hint">Dokumentationsstand der Databank, gerechnet auf der kuratierten Datenfeld-Schicht:
  Der Balken zeigt, für wie viele Datenfelder die Rechtsfrage GEKLÄRT ist — belegte Grundlage oder geprüftes
  «keine Grundlage» (Over-collection) zählen beide als Antwort. Ein kurzer Balken heisst «noch nicht ermittelt»,
  nicht «unrechtmässig erhoben». Zeile anklicken öffnet die Formular-Seite.</p>`;
  deptKeys().forEach(d=>{
    const offices=deptTree[d]; let body='',dn=0,dh=0,dsvc=0;
    Object.keys(offices).sort().forEach(o=>offices[o].forEach(s=>{
      if(f && !(s.name+' '+o+' '+d).toLowerCase().includes(f)) return;
      const g=grounding(s.id); dn+=g.need; dh+=g.have; dsvc++;
      const pct=g.need?Math.round(100*g.have/g.need):100;
      body+=`<tr data-sid="${s.id}" style="cursor:pointer"><td><b title="${esc(s.name)}">${esc(s.name)}</b></td>
        <td class="small muted">${esc(o)}</td><td class="small">${g.need}</td>
        <td><div class="pbar" style="display:inline-block;max-width:160px;vertical-align:middle"><i style="width:${pct}%"></i></div> <span class="small muted">${g.have}/${g.need}</span></td></tr>`;
    }));
    if(!body) return;
    const dpct=dn?Math.round(100*dh/dn):100;
    h+=`<div class="card"><div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
      <b style="font-size:14px">${esc(d)}</b> <span class="small muted">${dsvc} Dienste</span>
      <div class="pbar"><i style="width:${dpct}%"></i></div><span class="small muted">${dh}/${dn} Datenfelder geklärt</span></div>
      <table class="ft"><thead><tr><th>Dienst (Formular)</th><th>Amt</th><th>Datenfelder</th><th>Rechtsfrage geklärt</th></tr></thead><tbody>${body}</tbody></table></div>`;
  });
  return h;
}
const DFTYPE={text:'Text',date:'Datum',number:'Zahl',money:'Betrag',boolean:'Ja/Nein',
  enum:'Auswahl',multiselect:'Mehrfachauswahl',composite:'Zusammengesetzt',
  attachment:'Beilage',signature:'Unterschrift'};
// the stricter rules a sensitive category triggers, as tooltip text
const _sensRules={};
(DATA.datenhandhabung||[]).filter(r=>r.scope==='besonders_schuetzenswert').forEach(r=>{
  (_sensRules[r.sensitive_category||'*']=_sensRules[r.sensitive_category||'*']||[]).push(r);});
function sensTip(cat){
  const rs=[...(_sensRules[cat]||[]),...(_sensRules['*']||[])];
  return rs.slice(0,4).map(r=>`• ${r.summary} (${artLabel(r.article_no)} ${r.short_title||''})`).join('\n')
    +(rs.length>4?`\n… und ${rs.length-4} weitere (Tab Datenhandhabung)`:'');
}
function viewDataFields(forms){
  let h='';
  forms.forEach(fm=>{
    const dfs=fm.data_fields||[]; if(!dfs.length) return;
    h+=`<div class="card"><div class="dfhdr"><b>${esc(fm.title)}</b>
      <span class="muted small">— ${dfs.length} Datenfelder${fm.fields?` · aus ${fm.fields.length} Formularfeldern verdichtet`:''}${(()=>{const n=dfs.filter(x=>x.ech).length;return n?` · <b>${n}/${dfs.length}</b> eCH-standardisiert`:'';})()}</span>
      ${(()=>{const ck=fm.check;if(!ck)return'';
        if(ck.status==='aktuell')return`<span class="fcheck ok" title="online geprüft (${esc(ck.quelle||'')}) — unsere Kopie ist die aktuelle Fassung">✓ aktuell${ck.d?' · geprüft '+esc(ck.d):''}</span>`;
        if(ck.status==='veraltet')return`<span class="fcheck warn" style="font-weight:700" title="${esc(ck.note||'')}">⛔ veraltet — neuere Fassung online</span>`;
        if(ck.status==='veraltet_verdacht')return`<span class="fcheck warn" title="${esc(ck.note||'')}${ck.dvsh_neu?' — neu: '+esc(ck.dvsh_neu):''}">⚠ evtl. veraltet</span>`;
        if(ck.status==='nicht_auffindbar')return`<span class="fcheck gone" title="${esc(ck.note||'')} (geprüft ${esc(ck.d||'')}) — Formular wird online nicht mehr angeboten; evtl. ausser Gebrauch oder durch eServices ersetzt">✕ nicht mehr online</span>`;
        if(ck.status==='nicht_gefunden')return`<span class="fcheck miss" title="weder auf sh.ch, im DVSH noch per Websuche auffindbar (geprüft ${esc(ck.d||'')})">? online nicht gefunden</span>`;
        return'';})()}
      ${fm.source_file?`<a class="srcbtn" href="${esc(fm.source_file)}" style="margin-left:auto">↗ Quelldatei</a>`:''}</div>`;
    dfs.forEach(d=>{
      const subs=(d.subfields||[]).map(s=>typeof s==='string'?s:(s&&s.name)||'').filter(Boolean);
      const vals=(d.allowed_values||[]);
      const SENS={gesundheit:'Gesundheit',religion_weltanschauung:'Religion/Weltanschauung',politik:'Politische Ansichten',
        ethnie_herkunft:'Ethnie/Herkunft',genetik_biometrie:'Genetik/Biometrie',strafen_verfahren:'Strafverfahren/Sanktionen',sozialhilfe:'Soziale Hilfe'};
      h+=`<div class="dfrow"><div class="dfmain">
        <div><span class="tp">${esc(DFTYPE[d.data_type]||d.data_type)}</span>
          <span class="dfname">${esc(d.name)}</span>
          ${d.required?'<span class="req"><i class="ti ti-asterisk"></i>Pflicht</span>':'<span class="muted small">optional</span>'}
          ${d.ech?(()=>{const e=d.ech.element, nx=!e&&d.ech.n_elements>0;
            const st=d.ech.status, draft=st&&st!=='Genehmigt';
            const tip=esc(d.ech.standard_titel||'')+(e?` — Element ${esc(e)}`
              :(nx?` — Element noch nicht bestimmt (${d.ech.n_elements} Elemente im Standard)`
                  :' — Standard ohne XSD: kein zitierbares XML-Element'))
              +(st?` · Status: ${esc(st)}${d.ech.reifegrad?', Reifegrad '+esc(d.ech.reifegrad):''}`:'');
            return `<a class="echb${e?'':(nx?' todo':' so')}" href="${esc(d.ech.url)}" target="_blank" rel="noreferrer" title="${tip}">${esc(d.ech.standard)}${e?` · ${esc(e)}`:(nx?' · Element offen':' · nur Standard')}</a>`
              +(d.ech.datatype?(()=>{const cl=(DATA.ech_codelists||{})[d.ech.standard+'|'+d.ech.datatype];
                  const ver=d.ech.xsd_version?` (XSD ${esc(d.ech.xsd_version)})`:'';
                  const codes=cl?`\nOffizielle Codeliste (${cl.length} Werte): `+cl.slice(0,12).map(c=>c.value+(c.doc?' = '+c.doc:'')).join(' · ')+(cl.length>12?' …':''):'';
                  return `<span class="edt${cl?' cl':''}" title="Datentyp gemäss dem offiziellen ${esc(d.ech.standard)}-XSD${ver} — in diesem Typ ist das Datum zu speichern und auszutauschen${esc(codes)}">⟨${esc(d.ech.datatype)}⟩${cl?'<i class="ti ti-list-numbers" style="font-size:10px;margin-left:2px"></i>':''}</span>`;})():'')
              +(d.register?`<span class="regc" title="Once-Only: dieses Datum (eCH-Element ${esc(e||'')}) führt das Einwohnerregister für Einwohnerinnen und Einwohner bereits — statt neu zu erheben: eigene Daten vorbefüllen, Daten Dritter abgleichen (Verhältnismässigkeit, Art. 4 Abs. 2 KDSG). Gilt nur für Daten natürlicher Personen; Betriebs-, Behörden- und Objektadressen tragen die Marke nicht.">↺ vorbefüllbar · Einwohnerregister</span>`:'')
              +(draft?`<span class="echdraft${(st==='Aufgehoben'||st==='Abgelöst')?' rep':(st==='Sistiert'?' susp':'')}" title="${
                  (st==='Aufgehoben'||st==='Abgelöst')?`Dieser eCH-Standard ist ${esc(st).toUpperCase()} — nicht mehr in Kraft, die Zuordnung muss ersetzt werden`
                : st==='Sistiert'?'Dieser eCH-Standard ist SISTIERT (ausgesetzt) — nicht in Kraft, Zuordnung vorläufig'
                : 'Dieser eCH-Standard ist noch nicht genehmigt (in Arbeit) — Zuordnung vorläufig'}">${(st==='Aufgehoben'||st==='Abgelöst')?'⛔':'⚠'} ${esc(st)}</span>`:'');})()
            :(d.ech_status==='kein_standard'?('<span class="echn" title="kein eCH-Standard deckt dieses Feld ab">kein eCH-Standard</span>'+(d.esh?`<span class="eshb" title="Vorschlag für den kantonalen Standard eSH (E-Schaffhausen) — ENTWURF, nicht offiziell: ${esc(d.esh.titel)}">${esc(d.esh.code)} · ${esc(d.esh.element||'')}<span class="ent">Entwurf</span></span>`:'')):'')}
          ${d.sensitive?(()=>{const n=(_sensRules[d.sensitive]||[]).length+(_sensRules['*']||[]).length;
            return `<span class="badge b-sens senslink" title="besonders schützenswert (Art. 5 lit. c DSG) — es gelten zusätzlich:\n${esc(sensTip(d.sensitive))}\nKlick: Leitfaden">⛨ ${esc(SENS[d.sensitive]||d.sensitive)}${n?` · ${n} Zusatzregeln`:''}</span>`;})():''}
          ${d.format?`<span class="muted small">· ${esc(d.format)}</span>`:''}
          ${d.schutzstufe?`<span class="badge b-sourced">Schutzstufe ${esc(d.schutzstufe)}</span>`:''}</div>
        ${d.definition?`<div class="dfdef">${esc(d.definition)}</div>`:''}
        ${subs.length?`<div class="dfchips"><span class="muted small">Teilfelder:</span> ${(d.subfields||[]).slice(0,24).map(s=>{
            const nmv=typeof s==='string'?s:(s&&s.name)||''; if(!nmv) return '';
            const e=s&&s.ech;
            const dr=e&&e.status&&e.status!=='Genehmigt'?((e.status==='Aufgehoben'||e.status==='Abgelöst')?' ⛔':' ⚠'):'';
            if(e&&e.element) return `<span class="chip sub"><b>${esc(nmv)}</b><a class="sfe" href="${esc(e.url)}" target="_blank" rel="noreferrer" title="${esc(e.standard_titel||'')} — ${esc(e.standard)} ${esc(e.element)}${e.datatype?' · wird geführt als '+esc(e.datatype):''}${e.status?' · Status: '+esc(e.status):''}">${esc(e.standard)}·${esc(e.element)}${dr}</a>${s.register?`<span class="regc" title="Once-Only: dieses Teilfeld führt das Einwohnerregister bereits (${esc(e.standard)} ${esc(e.element)}) — vorbefüllbar statt neu erheben">↺</span>`:''}</span>`;
            if(e) return `<span class="chip sub"><b>${esc(nmv)}</b><a class="sfe so" href="${esc(e.url)}" target="_blank" rel="noreferrer" title="${esc(e.standard_titel||'')} — Standard ohne XSD">${esc(e.standard)}</a></span>`;
            if(s&&s.ech_status==='kein_standard') return `<span class="chip sub"><b>${esc(nmv)}</b>${s.esh?`<a class="sfe esh" title="eSH-Entwurf: ${esc(s.esh.titel)}">${esc(s.esh.code.replace('eSH-','eSH'))}·${esc(s.esh.element||'')}</a>`:`<span class="sfe none" title="kein eCH-Standard">kein Std.</span>`}</span>`;
            return `<span class="chip sub"><b>${esc(nmv)}</b></span>`;}).join('')}</div>`
          :(vals.length?`<div class="dfchips"><span class="muted small">Werte:</span> ${vals.slice(0,24).map(v=>`<span class="chip">${esc(String(v))}</span>`).join('')}</div>`:'')}
        ${(d.source_widgets||[]).length?`<div class="dfprov"><i class="ti ti-arrow-back-up"></i> erfasst durch: ${d.source_widgets.slice(0,8).map(w=>esc(String(w))).join(' · ')}</div>`:''}
      </div><div class="dfrg">${(d.legal_basis&&d.legal_basis.length)?d.legal_basis.map(b=>
          b.quote?`<details class="qd"><summary>${citeStr(b)}</summary><blockquote class="quote">«${esc(b.quote)}»</blockquote></details>`
                 :citeStr(b)).join('<br>'):basisBadge(d)}</div></div>`;
    });
    h+=`</div>`;
  });
  return h;
}
function widgetTable(s,forms){
  const g=grounding(s.id); const pct=g.need?Math.round(100*g.have/g.need):100;
  let h=`<div class="card"><div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
    <div class="pbar" style="max-width:340px"><i style="width:${pct}%"></i></div>
    <span><b>${g.have}/${g.need}</b> Felder mit Rechtsgrundlage</span>
    ${forms[0]&&forms[0].source_file?`<a class="srcbtn" href="${esc(forms[0].source_file)}" style="margin-left:auto">↗ Quelldatei</a>`:''}</div>
  <table class="ft"><thead><tr><th>#</th><th>Feld</th><th>Rechtsgrundlage</th><th>Klasse</th></tr></thead><tbody>`;
  // German labels for the auto-draft classifications; raw slug stays as tooltip
  const CLS_DE={mapped:'zugeordnet',identity_part:'Identitätsangabe',reason_facet:'Begründungsangabe',
    form_mechanic:'Formular-Mechanik',overcollection:'ohne gesetzliche Grundlage','—':'—'};
  let i=0;
  forms.forEach(fm=>(fm.fields||[]).forEach(fl=>{ i++; const mp=fl.mapping; const cls=mp?mp.classification:'—';
    const req=mp&&mp.requirement_id!=null?reqById[mp.requirement_id]:null; const basis=req?req.legal_basis:[];
    const cell = cls==='form_mechanic' ? '<span class="muted small">— keine nötig</span>'
      : cls==='overcollection' ? '<span class="badge b-over" title="Geprüft: kein Gesetz verlangt dieses Feld — nur freiwillig erhebbar">Over-collection — ohne Grundlage</span>'
      : basis.length ? basis.map(citeStr).join('<br>')
      : '<span class="badge b-unver" title="Noch nicht juristisch ermittelt — heisst NICHT, dass keine Grundlage existiert; die Databank dokumentiert hier eine Wissenslücke">zu ermitteln</span>';
    h+=`<tr><td>${i}</td>
      <td>${fmtPath(fl.path||fl.label)}</td>
      <td>${cell}</td><td><span class="small" title="${esc(cls)}">${esc(CLS_DE[cls]||cls)}</span></td></tr>`;
  }));
  h+=`</tbody></table>${i?'':'<div class="nores">keine Felder extrahiert (gescanntes PDF / reine Erklärung)</div>'}</div>`;
  return h;
}
const CHAN_DE={online_formular:'Online-Formular',pdf:'PDF-Einreichung',schalter:'Schalter',unbekannt:'Kanal unbekannt'};
const OUTCOME_DE={bewilligung:'Bewilligung',verfuegung:'Verfügung',bestaetigung:'Bestätigung/Ausweis',
  registereintrag:'Registereintrag',auszahlung:'Auszahlung',kein_entscheid:'kein Entscheid (Meldung)',unbekannt:'unbekannt'};
// SERVICE-level head: publication state, Verfahrens-Ergebnis, contact —
// nothing form-specific lives here any more
function serviceHead(s, forms){
  const dv=s.dvsh, sp=s.shep;
  const fm0=forms[0]||{};
  const dst=(DATA.dienststellen||[]).find(x=>x.name===(s.dienststelle||fm0.publisher_dienststelle));
  const out=fm0.outcome;
  return `<div class="card hubhead">
    <div class="hubrow" style="margin-bottom:6px">
      ${dv?`<span class="badge b-dvsh" title="Status im DVSH-Modeller${dv.version?' · Version '+esc(String(dv.version)):''}">DVSH: ${esc(dv.status||'modelliert')}${dv.online?' · online':''}</span>`:'<span class="badge b-nodv">◇ nicht im DVSH modelliert</span>'}
      ${sp?`<a class="badge b-dvsh" style="text-decoration:none" href="https://shep.meetfrida.agency/de/services/${esc(sp.slug)}" target="_blank" rel="noreferrer" title="auf dem SHEP-Portal publiziert · Stand ${esc(sp.updated||'')}">SHEP publiziert ↗</a>`:(dv?'<span class="hubmeta">noch nicht auf SHEP publiziert</span>':'')}
      ${dv&&dv.vollzugsbehoerde?`<span class="hubmeta">Vollzug: ${esc(dv.vollzugsbehoerde)}</span>`:''}
      ${dv&&dv.gebuehren?`<span class="hubmeta">Gebühren: ${esc(String(dv.gebuehren).slice(0,60))}</span>`:''}
      ${dst&&dst.kontakt?`<span class="hubmeta" title="verantwortliche Dienststelle laut DVSH">Kontakt: ${esc(((dstInfo[dst.name]||{}).kontakt||[dst.kontakt]).join(' · '))}</span>`:''}
      <a class="srcbtn" style="margin-left:auto" href="dossiers/${esc((s.slug||s.name).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,80))}.html" target="_blank" rel="noreferrer" title="Ein- bis zweiseitiges Datenschutz-Dossier dieses Services zum Drucken oder als PDF — Daten, Grundlagen, Empfänger, Fristen, Rechtsmittel, offene Punkte (dossiers/-Ordner, aus derselben Databank erzeugt)">⎙ Dossier (Druck/PDF)</a>
    </div>
    ${out&&out.entscheid_art&&out.entscheid_art!=='unbekannt'?`<div class="hubout">Ergebnis des Verfahrens:
      <b>${esc(OUTCOME_DE[out.entscheid_art]||out.entscheid_art)}</b>${out.ergebnis_dokument?` — «${esc(out.ergebnis_dokument)}»`:''}
      <span class="muted small">(aus dem DVSH-Ablauftext abgeleitet)</span></div>`:''}
    ${out?rechtsmittelLine(out):''}
  </div>`;
}
// Rechtsmittel: what a person can do against the decision - sektoral (the cited
// law says it itself) or the VRG's general rule, always labelled which
const RM_DE={einsprache:'Einsprache',rekurs:'Rekurs',beschwerde:'Beschwerde',verwaltungsgerichtsbeschwerde:'Verwaltungsgerichtsbeschwerde',verweis:'Rechtsmittel nach Verweis'};
function rechtsmittelLine(out){
  const r=out.rechtsmittel;
  if(!r){
    if(out.entscheid_art==='registereintrag') return `<div class="hubout rm"><span class="rmlbl">Rechtsmittel:</span> <span class="badge b-unver" title="Registerverfahren richten sich nach Bundesrecht (eigene Rechtsmittelordnung); die allgemeine VRG-Regel wird hier bewusst nicht unterstellt">noch nicht bestimmt — Registerverfahren nach Bundesrecht</span></div>`;
    if(out.entscheid_art==='kein_entscheid') return `<div class="hubout rm"><span class="rmlbl">Rechtsmittel:</span> <span class="muted small">keines — das Verfahren endet ohne anfechtbare Verfügung (Meldung)</span></div>`;
    return '';
  }
  const nr=r.sr_number?(r.jurisdiction_level==='federal'?'SR ':'SHR ')+r.sr_number:(r.cantonal_ref||'');
  const law=(r.short_title||r.law_title||'')+(nr?' ('+nr+')':'');
  const frist=r.frist_tage?`innert <b>${r.frist_tage} Tagen</b>${r.frist_article_no?' ('+esc(artLabel(r.frist_article_no))+')':''}`:'<span class="muted">Frist im Gesetz nicht beziffert</span>';
  const tip=esc((r.quote||'')+(r.frist_quote?'\n\n'+r.frist_quote:'')+(r.hinweis?'\n\n'+r.hinweis:''));
  const what=r.rechtsmittel_art==='verweis'?`Rechtsmittel nach ${esc(r.instanz||'dem verwiesenen Erlass')}`
    :`<b>${esc(RM_DE[r.rechtsmittel_art]||r.rechtsmittel_art)}</b>${r.instanz?' an '+esc(r.instanz):''} ${frist}`;
  const src=r.scope==='allgemein'
    ?`<span class="badge b-unver" title="VRG Art. 1: die allgemeinen Verfahrensregeln gelten nur, soweit nicht abweichende Vorschriften in andern Gesetzen, Dekreten oder Verordnungen bestehen. Für dieses Formular ist im zitierten Fachgesetz keine eigene Rechtsmittelnorm hinterlegt — die allgemeine Regel ist die beste belegte Aussage, nicht die letzte.">allgemeine Regel des VRG — Spezialgesetz vorbehalten</span>`
    :`<span class="badge b-sourced" title="Rechtsmittelnorm aus dem Fachgesetz, das die Datenfelder dieses Formulars zitieren${r.gilt_fuer?' — gilt für: '+esc(r.gilt_fuer):''}">sektoral: ${esc(r.short_title||r.law_title||'')}</span>`;
  const cands=(out.rechtsmittel_kandidaten||[]).filter(k=>!(r.scope==='sektoral'&&k.id===out.rechtsmittel_regel_id));
  const candList=cands.length?`<details class="qd rmcand"><summary>${cands.length} weitere Rechtsmittelnorm${cands.length===1?'':'en'} in den zitierten Gesetzen${r.scope==='allgemein'?' — zu prüfen, ob eine davon vorgeht':''}</summary>
      ${cands.map(k=>`<div class="small rmc"><b>${esc(RM_DE[k.rechtsmittel_art]||k.rechtsmittel_art)}</b>${k.instanz?' an '+esc(k.instanz):''}${k.frist_tage?' · '+k.frist_tage+' Tage':''} — ${esc(artLabel(k.article_no))} ${esc(k.short_title||k.law_title||'')}${k.gilt_fuer?' · gilt für: '+esc(k.gilt_fuer):''}${k.hinweis?' <span class="muted">('+esc(k.hinweis)+')</span>':''}<blockquote class="quote">«${esc(k.quote||'')}»</blockquote></div>`).join('')}</details>`:'';
  return `<div class="hubout rm"><span class="rmlbl">Rechtsmittel:</span> ${what}
    <details class="qd" style="display:inline-block;margin-left:6px"><summary title="${tip}">${esc(artLabel(r.article_no))} ${esc(law)} · Zitat</summary><blockquote class="quote">«${esc(r.quote||'')}»${r.frist_quote?`<br>«${esc(r.frist_quote)}»`:''}</blockquote></details>
    ${src}${out.rechtsmittel_verdikt?`<span class="badge b-match" title="${esc(out.rechtsmittel_verdikt)}">Zuordnung geprüft</span>`:''}</div>${candList}`;
}
// FORM-level facts strip: channel, signature, Ampel, Bürgerlast, currency
function formFacts(fm){
  const bl=fm.blockers||[];
  const amp=bl.length===0?'gruen':(bl.length<=2?'gelb':'rot');
  let checked='';
  if(fm.check&&fm.check.d){
    const days=Math.round((Date.parse(DATA.generated_at||'')-Date.parse(fm.check.d))/864e5);
    checked=`<span class="hubmeta" title="Aktualität online geprüft am ${esc(fm.check.d)}${fm.next_check_due?' · Wiedervorlage '+esc(fm.next_check_due):''}">zuletzt geprüft vor ${days} Tagen</span>`;
  }
  return `<div class="hubrow">
      ${(fm.data_fields||[]).length?`<span class="ampel a-${amp}" title="Digitalisierungs-Blocker: ${bl.length?esc(bl.join(' · ')):'keine'}">●</span>`:''}
      ${fm.dvsh_match&&/konsolidiert|zuordnung/.test(fm.dvsh_match)?`<span class="hubmeta" title="${esc(fm.dvsh_match)}">↳ diesem DVSH-Service zugeordnet</span>`:''}
      <span class="hubchan">${esc(CHAN_DE[fm.submission_channel]||CHAN_DE.unbekannt)}</span>
      ${fm.signature_requirement==='handschriftlich'?`<span class="hubsig" title="${esc(fm.signature_evidence||'')}">✍ Unterschrift nötig</span>`:''}
      ${fm.signature_requirement==='sig_widget'?`<span class="hubsig ok">✓ digitale Signatur möglich</span>`:''}
      ${fm.has_flow?`<span class="hubmeta">geführter Flow (flows.html)</span>`:''}
      ${checked}
    </div>
    ${fm.burden?`<div class="hubburden">Bürgerlast: <b>${fm.burden.inputs}</b> Pflichtangaben
      ${fm.burden.attachments?` · <b>${fm.burden.attachments}</b> Beilagen`:''} · ~<b>${fm.burden.minutes}</b> Min
      ${fm.burden.prefillable?` · <b>${fm.burden.prefillable}</b> aus dem Einwohnerregister vorbefüllbar`:''}
      <span class="muted small" title="Zeitmodell: 0.4 Min je Pflichtangabe, 5 Min je Beilage">ⓘ</span></div>`:''}`;
}
function blockerPanel(forms){
  const fm=forms[0]||{}; const bl=fm.blockers||[];
  if(!(fm.data_fields||[]).length) return '';
  if(!bl.length) return `<div class="card"><div class="dvsub">Digitalisierung</div>
    <div class="hstd">Keine Blocker erkannt — dieses Formular ist ein Kandidat für die durchgängig digitale Abwicklung.</div></div>`;
  const detail={'Unterschrift':fm.signature_evidence?`Beleg: ${fm.signature_evidence}`:'',
    'Quelle nicht befüllbar':fm.parse_error?`PDF nicht maschinell lesbar (${fm.parse_error})`:'flaches PDF ohne AcroForm-Felder',
    'kein Online-Kanal':'kein Online-Formular im DVSH-Abgabekanal',
    'eCH-Abdeckung < 50%':`nur ${fm.exchange_pct}% der atomaren Datenpunkte standardisiert`,
    };
  return `<div class="card"><div class="dvsub">Digitalisierungs-Blocker (${bl.length})</div>
    ${bl.map(b=>`<div class="hstd">✕ <b>${esc(b)}</b><span class="muted small"> — ${esc(detail[b]||'')}</span></div>`).join('')}</div>`;
}
const HALTER_DE={privat:'nur beim Bürger',einwohnerregister:'Einwohnerregister',handelsregister:'Handelsregister',
  betreibungsregister:'Betreibungsregister',strafregister:'Strafregister',steuerverwaltung:'Steuerverwaltung',
  grundbuch:'Grundbuch',kanton_andere:'kantonale Behörde',bund:'Bund',unbekannt:'Halter unbekannt'};
function beilagenPanel(forms){
  const bs=forms.flatMap(fm=>fm.beilagen||[]);
  if(!bs.length) return '';
  const fetch_=bs.filter(b=>b.fetchable).length;
  return `<div class="card"><div class="dvsub">Beilagen (${bs.length})${fetch_?` — <b>${fetch_}</b> könnte der Kanton selbst beim Register beschaffen`:''}</div>
    ${bs.map(b=>`<div class="beirow">
      <span class="beiob ${b.obligatorium||'unbekannt'}">${esc({zwingend:'Pflicht',bedingt:'bedingt',fakultativ:'freiwillig',unbekannt:'?'}[b.obligatorium||'unbekannt'])}</span>
      <span>${esc(b.bezeichnung)}${b.bedingung?` <span class="muted small">(${esc(b.bedingung)})</span>`:''}</span>
      <span class="beih ${b.fetchable?'f':''}" title="${b.fetchable?'staatlich geführt — Once-Only-Kandidat: Abruf statt Papierkopie':''}">${esc(HALTER_DE[b.halter]||b.halter||'')}${b.fetchable?' ↺':''}</span>
      ${b.source==='dvsh'?'<span class="muted small" title="nur im DVSH-Modell verlangt, nicht im Formular selbst — Abgleich-Fund">nur DVSH</span>':''}
    </div>`).join('')}</div>`;
}
function similarPanel(forms){
  const sim=forms.flatMap(fm=>fm.similar||[]);
  if(!sim.length) return '';
  return `<div class="card"><div class="dvsub">Duplikat-Radar — sehr ähnliche Formulare (Feldmengen-Überlappung ≥ 50%)</div>
    ${sim.slice(0,6).map(x=>{
      const svc=DATA.forms.find(f=>f.id===x.form_id);
      return `<div class="hstd">≈ <a class="simlink" data-sid="${svc?svc.service_id:''}">${esc(x.titel)}</a>
      <span class="muted small">Jaccard ${x.jaccard}${x.verdict?' · '+esc(x.verdict):' · unbeurteilt'}</span></div>`;}).join('')}</div>`;
}
// ---------- the Service-Dossier ----------
// One narrative per page: SERVICE (identity, legal basis, Verfahren)
//   -> each FORMULAR -> the DATA it demands (Angaben + Beilagen + Unterschrift)
//   -> per datum its LEGAL BASIS, and the HANDLING rules glued to the table.
// Everything that is not this narrative folds into a Details drawer.
function lawChip(t,n,u,j){
  return `<a class="lawchip" href="${esc(u)}" target="_blank" rel="noreferrer" title="${esc(t)}">${jur(j)} ${esc(n||t)}</a>`;
}
function svcLaws(dv){
  if(!dv) return [];
  const out=[];
  (dv.recht_kantonal||[]).forEach(l=>{const n=l.ssr||l.ssr_nummer;
    out.push(lawChip(l.titel||'',n,`https://rechtsbuch.sh.ch/app/de/texts_of_law/${n}`,'cantonal'));});
  (dv.recht_bund||[]).forEach(l=>out.push(lawChip(l.label||l.titel||'',l.sr,l.url||'#','federal')));
  return out;
}
function verfahrenSection(s){
  const dv=s.dvsh||{}, sp=s.shep||{};
  // DVSH is the correct version; SHEP fills only what DVSH leaves empty
  const vor=(dv.voraussetzungen&&dv.voraussetzungen.length?dv.voraussetzungen:(sp.voraussetzungen||[]))
    .filter(x=>typeof x==='string');
  const unt=(dv.unterlagen&&dv.unterlagen.length?dv.unterlagen:(sp.unterlagen||[]))
    .map(u=>typeof u==='string'?{title:u}:u);
  const abl=(dv.ablauf&&dv.ablauf.length?dv.ablauf:(sp.ablauf||[]))
    .map(a=>typeof a==='string'?{title:a}:a);
  if(!vor.length&&!unt.length&&!abl.length&&!dv.kurzbeschreibung) return '';
  return `<details class="card verf" open><summary><b>Das Verfahren</b>
      <span class="muted small">— amtliche Modellierung (DVSH${dv.version?' v'+esc(String(dv.version)):''})</span></summary>
    ${dv.beschreibung?`<div class="dvdesc">${esc(dv.beschreibung)}</div>`:''}
    <div class="dvgrid">
      ${vor.length?`<div><div class="dvsub">Voraussetzungen</div>${vor.map(v=>`<div class="dvl">• ${esc(v)}</div>`).join('')}</div>`:''}
      ${abl.length?`<div><div class="dvsub">Ablauf</div>${abl.map((a,i)=>`<div class="dvl"><b>${a.sort||a.nr||i+1}.</b> ${esc(a.title||a.titel||'')}${(a.description||a.text)?` <span class="muted small">— ${esc(a.description||a.text)}</span>`:''}</div>`).join('')}</div>`:''}
    </div>
    ${unt.length?`<div class="dvsub" style="margin-top:8px">Erforderliche Unterlagen laut Modell (${unt.length})</div>
      ${unt.slice(0,16).map(u=>`<div class="dvl" title="${esc(u.hint||u.detail||'')}">• ${esc(u.title||u.titel||u.name||'')}${(u.hint||u.detail)?' <span class="muted small">ⓘ</span>':''}</div>`).join('')}`:''}
    ${(dv.bearbeitungsdauer||dv.fristen)?`<div class="dvmeta">${[['Bearbeitungsdauer',dv.bearbeitungsdauer],['Fristen',dv.fristen]]
        .filter(x=>x[1]&&String(x[1]).trim()&&String(x[1]).trim()!=='leer')
        .map(x=>`<div class="dvm"><span class="dvk">${x[0]}</span> ${esc(String(x[1]))}</div>`).join('')}</div>`:''}
  </details>`;
}
// the handling strip: how THIS form's data must be treated, glued to its table
function handlingStrip(s,fm){
  const terms=fm.retention||[], dec=fm.retention_decisions||[], emp=fm.disclosures||[];
  const cats=[...new Set((fm.data_fields||[]).filter(d=>d.sensitive).map(d=>d.sensitive))];
  const nb=(fm.data_fields||[]).filter(d=>d.basis_typ==='ohne').length;
  let frist;
  if(terms.length) frist=retLine(terms[0]);
  else if(dec.length) frist=`Kantonaler Entscheid: ${esc(String(dec[0].duration_value||''))} ${esc(dec[0].duration_unit||'')}`;
  else frist=`Standard: Registraturperiode 10–20 J., dann Staatsarchiv ${guideChip(["172.301","§ 6","aufbewahrung"])}`;
  const seen=new Set();
  const empt=emp.filter(e=>!seen.has(e.empfaenger)&&seen.add(e.empfaenger));
  return `<div class="hstrip">
    <span class="hsl" style="flex-basis:100%;margin:0">So sind die Daten dieses Formulars zu handhaben</span>
    <span class="hs"><span class="hsl">Aufbewahrung</span>${frist}</span>
    <span class="hs"><span class="hsl">Weitergabe</span>${empt.length
      ? empt.slice(0,4).map(e=>`<span class="empchip" title="${esc(artLabel(e.article_no)+' '+(e.short_title||''))}">${esc(e.empfaenger)}${e.mode==='systematisch'?' ↻':''}</span>`).join('')+(empt.length>4?` +${empt.length-4}`:'')
      : `nur nach den allgemeinen Regeln ${guideChip(["174.100","Art. 8","bekanntgabe"])}`}</span>
    ${cats.length?`<span class="hs"><span class="hsl">⛨ zusätzlich</span><span class="badge b-sens senslink" title="besonders schützenswerte Daten — Klick: was zusätzlich gilt">${cats.map(x=>esc(HSENS[x]||x)).join(', ')}</span></span>`:''}
    ${nb?`<span class="hs"><span class="hsl">ohne Grundlage</span><span class="badge b-over">${nb} Feld${nb===1?'':'er'} — nur freiwillig</span></span>`:''}
  </div>`;
}
// one bounded section per Formular: facts, handling, the data table, drawer.
// `single` renders the old full per-Formular view (drawer open, no border)
function formSection(s,fm,single){
  const hasDF=(fm.data_fields||[]).length;
  let h=`<div class="${single?'':'formsec'}" ${single?'':`id="fsec-${fm.id}"`}>
    <div class="card" style="padding:9px 16px 7px">
      ${single?'':`<div style="float:right"><button class="fmopen srcbtn" data-fid="${fm.id}" title="dieses Formular als eigene Seite öffnen (alte Formular-Ansicht)">▣ Einzelansicht</button></div>`}
      ${formFacts(fm)}${hasDF?handlingStrip(s,fm):''}</div>`;
  h+= hasDF? viewDataFields([fm]) : widgetTable(s,[fm]);
  h+= beilagenPanel([fm]);
  const extras=blockerPanel([fm])+handlingPanel(s,[fm])+similarPanel([fm]);
  h+=`<details class="hgen" style="margin:0 0 4px" ${single?'open':''}><summary class="dvsub" style="cursor:pointer">Details zu diesem Formular — Digitalisierungs-Blocker, volles Datenhandhabungs-Profil, Duplikat-Radar</summary>${extras}</details>`;
  return h+`</div>`;
}
function viewFields(){
  const m=document.getElementById('main');
  if(state.service==='all'){
    m.innerHTML=pageHead('Service-Seite',
      'Links einen Service wählen (oder oben suchen). Die Seite erzählt eine Sache: welcher Service, auf welcher Rechtsgrundlage — welche Formulare — welche Daten sie verlangen, mit Rechtsgrundlage und Handhabung je Datum.',
      'Verfahren & Service-Recht: DVSH-Modell und SHEP-Portal (Sources of Truth, read-only). Daten-, Standard- und Regel-Schicht: eigene kuratierte Analyse, quellenbelegt.',
      'Unten der Dokumentationsstand aller Departemente.')+deptOverview();
    m.querySelectorAll('tr[data-sid]').forEach(tr=>tr.onclick=()=>{state.service=tr.dataset.sid;render();}); return; }
  const s=svcById[state.service]; const forms=formsByService[s.id]||[];
  const dv=s.dvsh, sp=s.shep;
  // the old per-Formular view, one form as its own page
  if(state.sub&&state.sub.startsWith('form-')){
    const fid=+state.sub.slice(5);
    const fm=forms.find(f=>f.id===fid);
    if(fm){
      m.innerHTML=`<h3 class="view">${esc(fm.title)}</h3>
        <p class="hint">Formular-Ansicht · gehört zum Service <a class="simlink" id="backsvc">${esc(s.name)}</a> · ${esc(s.dienststelle||'')}</p>
        ${formSection(s,fm,true)}`;
      document.getElementById('backsvc').onclick=()=>{state.sub='felder';render();};
      m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=()=>{
        state.service=a.dataset.sid;state.sub='felder';render();});
      m.querySelectorAll('.senslink').forEach(b=>b.onclick=()=>{
        state.tab='guide';render();
        const t=[...document.querySelectorAll('.gq')].find(x=>x.textContent.includes('schützenswerte'));
        if(t)t.scrollIntoView({behavior:'smooth'});});
      return;
    }
    state.sub='felder';
  }
  const laws=svcLaws(dv);
  let h=`<div class="bcrumb"><a id="bc-home">⌂ Übersicht</a><span>›</span>
    <a class="bc-flt" data-f="${esc(s.department||'')}">${esc(s.department||'—')}</a><span>›</span>
    <a class="bc-flt" data-f="${esc(s.dienststelle||'')}">${esc(s.dienststelle||'—')}</a></div>
  <h3 class="view">${esc(s.name)}</h3>
  ${forms.length>1?`<div class="fjump"><span class="hsl">Formulare</span>${forms.map(fm=>
    `<button class="fjc" data-fid="${fm.id}">${esc(fm.title.length>44?fm.title.slice(0,42)+'…':fm.title)}</button>`).join('')}</div>`:''}
  ${serviceHead(s,forms)}`;
  if(dv&&dv.kurzbeschreibung) h+=`<div class="zweckline" style="margin:2px 2px 10px">${esc(dv.kurzbeschreibung)}</div>`;
  h+=laws.length?`<div class="svclaws"><span class="hsl">Rechtsgrundlage des Services (DVSH)</span>${laws.join('')}</div>`:'';
  if(!s.in_dvsh) h+=`<div class="card nodvbox"><span class="badge b-nodv">◇ Nicht im DVSH-Modell</span>
    <span class="muted small">Dieser Service ist in unserem Katalog erfasst, aber (noch) nicht in der amtlichen DVSH-Modellierung. Die Rechtsgrundlagen unten stammen aus unserer eigenen, quellenbelegten Analyse.</span></div>`;
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
    if(!forms.length) h+=`<div class="card"><div class="hstd">Kein Formular in der Databank — laut DVSH ein reiner Online-/eService${dv&&dv.endpoint_typ?` (${esc(dv.endpoint_typ)})`:''}.</div></div>`;
    forms.forEach(fm=>{h+=formSection(s,fm);});
    m.innerHTML=h;
  }
  m.querySelectorAll('.seg button[data-sub]').forEach(b=>b.onclick=()=>{state.sub=b.dataset.sub;render();});
  m.querySelectorAll('.fmopen[data-fid]').forEach(b=>b.onclick=()=>{state.sub='form-'+b.dataset.fid;render();});
  const bch=document.getElementById('bc-home');
  if(bch)bch.onclick=()=>{state.service='all';state.sub='felder';render();};
  m.querySelectorAll('.bc-flt').forEach(a=>a.onclick=()=>{
    state.service='all';state.sub='felder';state.filter=a.dataset.f;render();});
  m.querySelectorAll('.fjc[data-fid]').forEach(b=>b.onclick=()=>{
    const t=document.getElementById('fsec-'+b.dataset.fid);
    if(t)t.scrollIntoView({behavior:'smooth'});});
  m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=()=>{
    state.service=a.dataset.sid;state.sub='felder';render();});
  // a ⛨ badge jumps to the Leitfaden section on sensitive data
  m.querySelectorAll('.senslink').forEach(b=>b.onclick=()=>{
    state.tab='guide';render();
    const t=[...document.querySelectorAll('.gq')].find(x=>x.textContent.includes('schützenswerte'));
    if(t)t.scrollIntoView({behavior:'smooth'});});
}

// ---------- Datenhandhabung rendering helpers ----------
const ASPECT={erhebung:'Erhebung',bearbeitung:'Bearbeitung',speicherung:'Speicherung',
  sicherheit:'Datensicherheit',aufbewahrung:'Aufbewahrung',bekanntgabe:'Bekanntgabe',
  betroffenenrechte:'Rechte der Betroffenen',archivierung:'Archivierung',loeschung:'Löschung'};
const ASPECT_ORDER=Object.keys(ASPECT);
const HSENS={gesundheit:'Gesundheit',religion_weltanschauung:'Religion/Weltanschauung',
  politik:'Politische Ansichten',sozialhilfe:'Soziale Hilfe',strafen_verfahren:'Strafverfahren/Sanktionen'};
function ruleCite(r){
  const sr=r.sr_number?(r.jurisdiction_level==='federal'?' · SR ':' · SHR ')+r.sr_number:'';
  return `${jur(r.jurisdiction_level)} <span class="mono">${esc(artLabel(r.article_no))}</span> ${esc(r.short_title||r.law_title)}${esc(sr)}`;
}
function ruleItem(r){
  const q=r.quote?`<details class="qd"><summary>${ruleCite(r)}${r.quote_verified?'':' <span class="badge b-unver">Zitat unverifiziert</span>'}</summary><blockquote class="quote">«${esc(r.quote)}»</blockquote></details>`:ruleCite(r);
  return `<div class="hrule"><span class="hasp">${esc(ASPECT[r.aspect]||r.aspect)}</span>
    <div class="hbody"><div>${esc(r.summary)}${r.sensitive_category?` <span class="badge b-sens">⛨ ${esc(r.sensitive_category)}</span>`:''}</div>
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
    nFields++; if(d.basis_typ==='ohne') nNoBasis++;
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
  cats.forEach(c=>{strip+=`<span class="pfc sens">⛨ ${esc(HSENS[c]||c)} (${catFields[c].length} ${catFields[c].length===1?'Feld':'Felder'})</span>`;});
  if(sektLaws.length) strip+=`<span class="pfc law">Spezialnormen: ${esc(sektLaws.join(' · '))}</span>`;
  const hasTerm=forms.some(fm=>(fm.retention||[]).length||(fm.retention_decisions||[]).length);
  strip+=(hasTerm||frist.length)?`<span class="pfc frist">Aufbewahrung: Spezialfrist</span>`
                     :`<span class="pfc std">Aufbewahrung: Standard (Registraturperiode)</span>`;
  if(nNoBasis) strip+=`<span class="pfc over">${nNoBasis} ${nNoBasis===1?'Feld':'Felder'} ohne Grundlage</span>`;

  const purpose=forms.map(fm=>fm.purpose).filter(Boolean)[0];
  const terms=forms.flatMap(fm=>fm.retention||[]);
  const decisions=forms.flatMap(fm=>fm.retention_decisions||[]);
  const empf=forms.flatMap(fm=>fm.disclosures||[]);
  let h=`<div class="card" id="dhprofil"><div class="dfhdr"><b>Datenhandhabung — Profil dieses Formulars</b>
    <span class="muted small">— was für DIESE Daten speziell gilt; das für alle identische Grundprogramm ist unten eingeklappt</span></div>
    ${purpose?`<div class="zweckline">Zweck: ${esc(purpose)}</div>`:''}
    <div class="pfstrip">${strip}</div>`;

  // retention: the concrete, computable answer — term, decision, or standard regime
  h+=`<div class="hgrp"><div class="dvsub">Aufbewahrung &amp; Vernichtung</div>`;
  if(terms.length){
    h+=terms.map(t=>`<div class="hstd">${retLine(t)}</div>`).join('');
  } else if(frist.length) h+=rulesByAspect(frist);
  else h+=`<div class="hstd">Keine Spezialfrist für dieses Formular — es gilt der Standard: aufbewahren, solange die
    Verwaltung die Akten braucht (in der Regel mindestens zehn Jahre, Registraturperioden 10–20 Jahre), danach dem
    Staatsarchiv anbieten. ${guideChip(["172.301","§ 6","aufbewahrung"])}${guideChip(["172.301","§ 5","aufbewahrung"])}${guideChip(["172.301","§ 7","archivierung"])}</div>`;
  decisions.forEach(d=>{h+=`<div class="hstd">Kantonaler Fristentscheid: <b>${esc(String(d.duration_value||''))} ${esc(d.duration_unit||'')}</b>
    ${esc(fmtTrigger(d.trigger_event))} — ${esc(d.basis||'')} <span class="muted small">(${esc(d.decided_by||'')}, ${esc(d.decided_at||'')})</span></div>`;});
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
      h+=`<div class="hcat"><span class="badge b-sens">⛨ ${esc(HSENS[c]||c)}</span>
        <span class="small">${catFields[c].slice(0,10).map(esc).join(' · ')}${catFields[c].length>10?' …':''}</span></div>`;
    });
    if(sens.length) h+=rulesByAspect(sens);
    h+=`</div>`;
  }
  if(rest.length) h+=`<div class="hgrp"><div class="dvsub">Weitere Spezialnormen dieses Formulars</div>${rulesByAspect(rest)}</div>`;
  if(nNoBasis) h+=`<div class="hstd over">⚠ ${nNoBasis} ${nNoBasis===1?'Datenfeld hat':'Datenfelder haben'} keine gesetzliche
    Grundlage (Over-collection) — ${nNoBasis===1?'es darf':'sie dürfen'} nur freiwillig erhoben werden.</div>`;
  if(allg.length) h+=`<details class="hgen"><summary class="dvsub" style="cursor:pointer">Allgemeine Regeln KDSG/DSG — identisch für alle Formulare (${allg.length}) · erklärt im Tab «Leitfaden»</summary>${rulesByAspect(allg)}</details>`;
  return h+`</div>`;
}
function viewRules(){
  const m=document.getElementById('main');
  const H=DATA.datenhandhabung||[];
  let h=pageHead('Datenhandhabung · Speicherung, Bearbeitung, Bekanntgabe',
    'Der vollständige Regel-Korpus: eine Zeile je (Artikel, Aspekt), gruppiert nach Geltungsbereich und Gesetz.',
    '8 Governance-Gesetze (KDSG/KDSV/ISV/ArchivV, DSG/DSV/BGA/EMBAG) vollständig gelesen plus die Datenhandhabungs-Artikel von 41 Fachgesetzen; jede Regel trägt ein wörtliches Zitat, das der Loader mechanisch gegen das amtliche Gesetzes-PDF geprüft hat.',
    '«allgemein» gilt für alle Personendaten · «besonders schützenswert» zusätzlich für ⛨-Felder · «sektoral» nur für Formulare, deren Felder das jeweilige Gesetz zitieren («gilt für N Formulare» aufklappen).');
  if(!H.length){m.innerHTML=h+'<div class="nores">Noch keine Regeln geladen (scripts/load_data_rules.py).</div>';return;}
  const grp=[['allgemein','Allgemeine Regeln — für alle Personendaten'],
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
    h+=`<h4 class="hscope">${esc(label)} <span class="muted small">· ${list.length} Regeln</span></h4>`;
    Object.values(byLaw).forEach(rs=>{
      const r0=rs[0];
      const fms=scope==='sektoral'?[...(formsByLaw[r0.law_id]||[])]:[];
      h+=`<div class="card" id="law-${r0.law_id}-${scope}"><div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
        <b>${esc(r0.short_title||r0.law_title)}</b>
        <span class="muted small">${esc(r0.law_title!==r0.short_title?r0.law_title:'')}</span>
        <span class="muted small" style="margin-left:auto">${jur(r0.jurisdiction_level)} ${r0.sr_number?(r0.jurisdiction_level==='federal'?'SR ':'SHR ')+esc(r0.sr_number):''} · ${rs.length} Regeln</span></div>
        ${rulesByAspect(rs)}
        ${fms.length?`<details class="lawforms"><summary>gilt für ${fms.length} Formular${fms.length===1?'':'e'} →</summary>
          ${fms.slice(0,40).map(f=>`<div class="small">• <a class="simlink" data-sid="${f.service_id}">${esc(f.title)}</a></div>`).join('')}</details>`:''}</div>`;
    });
  });
  m.innerHTML=h;
  m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=()=>{
    state.service=a.dataset.sid;state.tab='fields';state.sub='felder';render();});
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
  return `<span class="gchip" data-law="${r.law_id}" data-scope="${esc(r.scope)}" title="${esc(tip)}">${esc(r.short_title||r.law_title)} ${esc(artLabel(r.article_no))}</span>`;
}
function viewGuide(){
  const m=document.getElementById('main');
  let h=pageHead('Leitfaden · Was heisst das für den Umgang mit Daten?',
    `Die praktischen Antworten hinter den ${(DATA.datenhandhabung||[]).length} Regeln des Datenhandhabung-Tabs, in einfacher Sprache — neun Fragen vom Erheben bis zum Vernichten.`,
    'Kuratierter Text; der Build verweigert sich, sobald eine Aussage eine Regel zitiert, die nicht in der Databank ist. Chips zeigen beim Überfahren das wörtliche, PDF-verifizierte Zitat; Klick springt zur Regel. Violette Kästen sind Einordnung, kein Gesetzeszitat.',
    'Massgeblich bleibt der Gesetzestext. Formular-spezifisches steht im Datenhandhabungs-Profil der jeweiligen Formular-Seite.');
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
    state.tab='rules';render();
    const t=document.getElementById(`law-${c.dataset.law}-${c.dataset.scope}`);
    if(t){t.scrollIntoView({behavior:'smooth'});t.classList.add('flash');setTimeout(()=>t.classList.remove('flash'),1600);}
  });
}
// ---------- tree (list + diagram) ----------
function needService(label){
  return `<h3 class="view">${label}</h3><div class="nores">Bitte links einen einzelnen Dienst wählen `+
         `(bei ${DATA.services.length} Diensten ist die Gesamtansicht zu gross).</div>`;
}
// build the law -> article -> data-field structure for the current selection
function treeModel(){
  // Current model: Gesetz -> Artikel -> DATENFELDER via data_field_legal_basis.
  // (The legacy requirement links are empty for auto-drafted services.)
  const sids = state.service==='all' ? DATA.services.map(s=>s.id) : [Number(state.service)];
  const laws={};
  sids.forEach(sid=>(formsByService[sid]||[]).forEach(fm=>(fm.data_fields||[]).forEach(d=>{
    (d.legal_basis||[]).forEach(lb=>{
      const lk=(lb.law_short||lb.law_title||'?');
      const L=laws[lk]||(laws[lk]={id:lk,title:lb.law_title,short:lb.law_short,jur:lb.jurisdiction,sr:lb.sr_number,cref:lb.cantonal_ref,arts:{}});
      const ak=lb.article_no||'?';
      const A=L.arts[ak]||(L.arts[ak]={id:ak,no:lb.article_no,heading:lb.article_heading,lc:lb.last_checked,reqs:{}});
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
  <p class="hint">Beide Darstellungen sind ein- und ausklappbar. Farbe = Zuständigkeitsebene; Status der Anforderung farbig markiert.</p>
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
}
function statusBadge(s){return `<span class="badge b-${s==='sourced'?'sourced':s}">${({match:'verifiziert',sourced:'Quelle (SHR-PDF)',proposed:'UNVERIFIED',legal_gap:'Legal Gap'}[s]||s)}</span>`;}
function listLaw(L){
  return `<div class="tgrp"><div class="tline"><span class="ttog">▾</span> ${jur(L.jur)} <b>${esc(L.short||L.title)}</b> <span class="muted small">${esc(L.title)}</span>${L.sr?' <span class="mono small">SR '+esc(L.sr)+'</span>':''}</div>
    <div class="tnode">${L.arts.map(listArt).join('')}</div></div>`;
}
function listArt(A){
  return `<div class="tgrp"><div class="tline"><span class="ttog">▾</span> <span class="mono">${esc(artLabel(A.no))}</span> ${esc(A.heading||'')}${unver(A.lc)}</div>
    <div class="tnode">${A.reqs.map(r=>`<div class="tline">• ${esc(r.dp)} ${statusBadge(r.status)} <span class="muted small">${esc(r.type||'')}</span></div>`).join('')}</div></div>`;
}
function dgLaw(L){
  return `<div class="dgnode"><div class="dgbox" style="border-left-color:var(--${L.jur})"><span class="ttl">${esc(L.short||L.title)}</span> ${jur(L.jur)}<div class="sub">${esc(L.title)}${L.sr?' · SR '+esc(L.sr):''}</div></div>
    <div class="dgchildren">${L.arts.map(dgArt).join('')}</div></div>`;
}
function dgArt(A){
  return `<div class="dgnode"><div class="dgbox" style="border-left-color:var(--mechanic)"><span class="ttl mono">${esc(artLabel(A.no))}</span><div class="sub">${esc(A.heading||'')} ${A.lc!=='verified'?'· UNVERIFIED':''}</div></div>
    <div class="dgchildren">${A.reqs.map(r=>`<div class="dgnode"><div class="dgbox" style="border-left-color:var(--${r.status==='legal_gap'?'gap':r.status==='proposed'?'proposed':'match'})"><span class="ttl">${esc(r.dp)}</span> ${statusBadge(r.status)}<div class="sub">${esc(r.type||'')}</div></div></div>`).join('')}</div></div>`;
}

// ---------- required information per law ----------
function viewInfo(into){
  const m=into||document.getElementById('main');
  if(state.service==='all'){ m.innerHTML=needService('Geforderte Informationen · pro Gesetz'); return; }
  let h=`<h3 class="view">Geforderte Informationen · pro Gesetz</h3>
  <p class="hint">Welche Datenpunkte jedes Gesetz verlangt, mit Artikel-Zitat, Datentyp, Bedingung und erfassendem Formularfeld.</p>`;
  const sids = [Number(state.service)];
  // rows from the CURRENT model: each data field with its article citations
  const byLaw={};
  sids.forEach(sid=>(formsByService[sid]||[]).forEach(fm=>(fm.data_fields||[]).forEach(d=>{
    (d.legal_basis||[]).forEach(lb=>{
      const lk=(lb.law_short||lb.law_title||'?');
      (byLaw[lk]=byLaw[lk]||{lb,rows:[]}).rows.push({
        req:{data_point:d.name,label:d.definition,data_type:d.data_type,condition:d.required?null:'optional'},
        lb, cap:[{label:fm.title,st:'formular'}]});
    });
  })));
  const laws=Object.values(byLaw);
  if(!laws.length){m.innerHTML=h+'<div class="nores">Keine Daten für die Auswahl.</div>';return;}
  laws.forEach(({lb,rows})=>{
    h+=`<div class="card"><div style="margin-bottom:10px">${jur(lb.jurisdiction)} <b>${esc(lb.law_title)}</b> ${lb.sr_number?'<span class="mono small">SR '+esc(lb.sr_number)+'</span>':''}${unver(lb.last_checked)}</div>
      <table><thead><tr><th>Datenpunkt</th><th>Artikel</th><th>Typ</th><th>Pflicht</th><th>Formular</th></tr></thead><tbody>
      ${rows.map(({req,lb,cap})=>`<tr>
        <td><b>${esc(req.data_point)}</b><div class="small muted">${esc(req.label||'')}</div></td>
        <td class="mono small">${esc(artLabel(lb.article_no))}${lb.citation_detail?' '+esc(lb.citation_detail):''}${unver(lb.last_checked)}</td>
        <td class="small">${esc(req.data_type||'')}</td>
        <td class="small">${esc(req.condition||'—')}</td>
        <td>${cap.length?cap.map(c=>`“${esc(c.label)}”${c.st==='formular'?'':` <span class="badge b-${c.st==='confirmed'?'confirmed':'proposedm'}">${c.st}</span>`}`).join('<br>'):'—'}</td>
      </tr>`).join('')}
      </tbody></table></div>`;
  });
  m.innerHTML=h;
}


// ---------- Verzeichnis der Bearbeitungstätigkeiten (KDSG Art. 17b) ----------
function fmtTrigger(t){ return t&&t!=='unbestimmt' ? 'nach '+t.replace(/_/g,' ') : ''; }
function retLine(t){
  const dur=t.duration_value?`${t.min_or_max==='min'?'mind. ':t.min_or_max==='max'?'max. ':''}${t.duration_value} ${t.duration_unit==='monate'?'Monate':'Jahre'}`:'ohne Zahl';
  const disp={vernichten:'→ vernichten',anonymisieren:'→ anonymisieren',anbieten_staatsarchiv:'→ Staatsarchiv anbieten',loeschen_vermerken:'→ als gelöscht vermerken'}[t.disposition]||'';
  return `<b>${esc(dur)}</b> ${esc(fmtTrigger(t.trigger_event))} ${disp} <span class="muted small">(${esc(artLabel(t.article_no))} ${esc(t.short_title||'')})</span>`;
}
function formStats(fm){
  const dfs=fm.data_fields||[];
  const sens=dfs.filter(d=>d.sensitive).length;
  const lb=dfs.filter(d=>(d.legal_basis||[]).length).length;
  const dsfaInd=sens>=3||(dfs.length&&sens/dfs.length>=0.5&&sens>=1);
  return {n:dfs.length,sens,lb,dsfaInd,
    hasZweck:!!fm.purpose,hasEmpf:(fm.disclosures||[]).length>0,
    hasFrist:(fm.retention||[]).length>0||(fm.retention_decisions||[]).length>0};
}
function viewRegister(){
  const m=document.getElementById('main');
  const fms=DATA.forms.filter(f=>(f.data_fields||[]).length);
  const st=fms.map(f=>({f,s:formStats(f)}));
  const c={zweck:0,empf:0,frist:0,dsfa:0,voll:0};
  st.forEach(({s})=>{if(s.hasZweck)c.zweck++;if(s.hasEmpf)c.empf++;if(s.hasFrist)c.frist++;
    if(s.dsfaInd)c.dsfa++;if(s.hasZweck&&s.hasEmpf&&s.hasFrist)c.voll++;});
  let h=pageHead('Verzeichnis der Bearbeitungstätigkeiten',
    'Ein Registerauszug je Formular — verantwortliche Stelle, Zweck, Datenkategorien, Rechtsgrundlagen, Empfänger, Aufbewahrung — plus DSFA-Triage und Dienststellen-Risikobild.',
    'Verantwortliche und Kategorien aus der kuratierten Feld-Schicht; Zwecke agent-kuratiert; Empfänger nur mit Artikel-Beleg; Fristen aus dem zitatverifizierten Fristen-Register. Die DSFA-Spalte ist ein BERECHNETER Vorschlag (Prüfpflicht: KDSG Art. 14b) — entschieden wird von Menschen.',
    'Rechtliche Einordnung: Die Struktur folgt KDSG Art. 17b Abs. 2 (Rechtsgrundlage, Zweck, Mittel, Art, Herkunft, regelmässige Empfänger). Eine PFLICHT, ein solches Register öffentlich zu führen, trifft nach Art. 17b nur Polizei, Staatsanwaltschaft und Justizvollzug; für alle übrigen Dienststellen ist dieses Verzeichnis ein Steuerungsinstrument der Databank, keine kantonale Rechtspflicht. Fehlende Inhalte stehen als «fehlt» — das ist der Arbeitsvorrat, kein Darstellungsfehler.')+`
  <div class="regstats">
    <span class="rstat">Zweck erfasst <b>${c.zweck}/${st.length}</b></span>
    <span class="rstat">Empfänger belegt <b>${c.empf}/${st.length}</b></span>
    <span class="rstat">Spezialfrist/Entscheid <b>${c.frist}/${st.length}</b></span>
    <span class="rstat">Register vollständig <b>${c.voll}/${st.length}</b></span>
    <span class="rstat warn">DSFA indiziert <b>${c.dsfa}</b></span>
  </div>`;
  // DSFA triage: computed from real sensitive-field density, decided by humans
  const triage=st.filter(x=>x.s.dsfaInd).sort((a,b)=>b.s.sens-a.s.sens).slice(0,15);
  if(triage.length){
    h+=`<div class="card"><div class="dvsub">DSFA-Triage — Formulare mit hoher Dichte besonders schützenswerter Felder (berechnet; Entscheid ist Sache des Kantons)</div>
    <table class="ft"><thead><tr><th>Formular</th><th>⛨ Felder</th><th>Anteil</th><th>DSFA-Status</th></tr></thead><tbody>`;
    triage.forEach(({f,s})=>{
      h+=`<tr data-sid="${f.service_id}" style="cursor:pointer"><td>${esc(f.title)}</td>
        <td>${s.sens}/${s.n}</td><td>${Math.round(100*s.sens/s.n)}%</td>
        <td>${f.dsfa_status?esc(f.dsfa_status):'<span class="badge b-unver">offen</span>'}</td></tr>`;});
    h+=`</tbody></table></div>`;
  }
  // Dienststellen risk heatmap: who actually holds the sensitive data
  const heat={};
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>{
    if(!d.sensitive)return;
    const svc=svcById[f.service_id]; const dn=(svc&&svc.dienststelle)||f.publisher_dienststelle||'(ohne)';
    const e=heat[dn]=heat[dn]||{total:0,cats:{},nb:0};
    e.total++; e.cats[d.sensitive]=(e.cats[d.sensitive]||0)+1; if(d.basis_typ==='ohne')e.nb++;}));
  const hrows=Object.entries(heat).sort((a,b)=>b[1].total-a[1].total).slice(0,15);
  if(hrows.length){
    h+=`<div class="card"><div class="dvsub">Wer hält die heiklen Daten? — sensible Felder je Dienststelle</div>
    <table class="ft"><thead><tr><th>Dienststelle</th><th>⛨ total</th><th>Kategorien</th><th>davon ohne Grundlage</th></tr></thead><tbody>`;
    hrows.forEach(([dn,e])=>{
      h+=`<tr><td>${esc(dn)}</td><td><b>${e.total}</b></td>
        <td class="small">${Object.entries(e.cats).map(([k,v])=>`${esc(HSENS[k]||k)} ${v}`).join(' · ')}</td>
        <td>${e.nb?`<span class="badge b-over">${e.nb}</span>`:'—'}</td></tr>`;});
    h+=`</tbody></table></div>`;
  }
  // the register itself, one row per SERVICE (its forms aggregated)
  const bySvc={};
  st.forEach(({f,s})=>{
    const e=bySvc[f.service_id]=bySvc[f.service_id]||{svc:svcById[f.service_id],forms:0,n:0,sens:0,lb:0,
      empf:0,zweck:true,frist:false,purpose:null};
    e.forms++; e.n+=s.n; e.sens+=s.sens; e.lb+=s.lb; e.empf+=(f.disclosures||[]).length;
    e.zweck=e.zweck&&s.hasZweck; e.frist=e.frist||s.hasFrist; e.purpose=e.purpose||f.purpose;});
  h+=`<div class="card"><table class="ft"><thead><tr><th>Service</th><th>Dienststelle</th>
    <th>Formulare</th><th>Zweck</th><th>Felder</th><th>Grundlagen</th><th>Empfänger</th><th>Frist</th></tr></thead><tbody>`;
  Object.entries(bySvc).forEach(([sid,e])=>{
    const nm=e.svc?e.svc.name:'?';
    h+=`<tr data-sid="${sid}" style="cursor:pointer">
      <td title="${esc(e.purpose||'')}">${esc(nm.length>64?nm.slice(0,62)+'…':nm)}</td>
      <td class="small muted">${esc((e.svc&&e.svc.dienststelle)||'')}</td>
      <td class="small">${e.forms}</td>
      <td>${e.zweck?'✓':'<span class="miss">fehlt</span>'}</td>
      <td class="small">${e.n}${e.sens?` <span class="badge b-sens">⛨${e.sens}</span>`:''}</td>
      <td class="small">${e.lb}/${e.n}</td>
      <td>${e.empf?e.empf:'<span class="miss">fehlt</span>'}</td>
      <td class="small">${e.frist?'<b>spezial</b>':'Standard'}</td></tr>`;});
  h+=`</tbody></table></div>`;
  m.innerHTML=h;
  m.querySelectorAll('tr[data-sid]').forEach(tr=>tr.onclick=()=>{state.service=tr.dataset.sid;state.tab='fields';render();});
}

// ---------- Datenkatalog (canonical attributes, Once-Only, divergences) ----------
function viewKatalog(){
  const m=document.getElementById('main');
  const kat=DATA.attribut_katalog||[];
  const reg=kat.filter(a=>a.register_source);
  const regInst=reg.reduce((n,a)=>n+a.n_instances,0);
  let h=pageHead(`Datenkatalog · die ${kat.length} einzigartigen Daten des Kantons`,
    'Eine Zeile je Datum (kanonisches Attribut = ein eCH- oder eSH-Element), egal auf wie vielen Formularen es erhoben wird — die Master-Data-Sicht über den ganzen Katalog.',
    'Vollständig abgeleitet aus den eCH/eSH-Zuordnungen der Feld-Schicht; «Einwohnerregister» markiert Attribute, die das Register nach RHG bereits führt.',
    `Der Kanton fragt registergeführte Daten trotzdem ${regInst.toLocaleString('de-CH')} Mal ab — das ist das Once-Only-Potenzial. Divergenzen zeigen, wo dasselbe Datum uneinheitlich erhoben wird. Zeile aufklappen listet die erhebenden Formulare.`);
  // exchange pipeline: how close is each form to a real eCH payload?
  const withDf=DATA.forms.filter(f=>(f.data_fields||[]).length);
  const online=new Set();
  DATA.services.forEach(s=>{if(s.dvsh&&(s.dvsh.abgabe||[]).some(x=>/Online-Formular/.test(String(x))))online.add(s.id);});
  const full=withDf.filter(f=>f.exchange_pct===100), p80=withDf.filter(f=>f.exchange_pct>=80&&f.exchange_pct<100);
  const pilot=full.filter(f=>online.has(f.service_id));
  h+=`<div class="regstats">
    <span class="rstat">voll eCH-gemappt <b>${full.length}</b></span>
    <span class="rstat">80–99% <b>${p80.length}</b></span>
    <span class="rstat">voll gemappt ∧ Online-Kanal <b>${pilot.length}</b> → Pilotmenge</span>
    <span class="rstat">registerbeziehbare Attribute <b>${reg.length}</b></span>
  </div>`;
  if(pilot.length){
    h+=`<div class="card"><div class="dvsub">Exchange-Pilotliste — voll standardisiert UND schon online einreichbar</div>
    ${pilot.map(f=>`<div class="small" style="padding:2px 0">• <a class="simlink" data-sid="${f.service_id}">${esc(f.title)}</a></div>`).join('')}</div>`;
  }
  // divergences computed live over all forms: same element, different requiredness/format
  const byEl={};
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>{
    const e=d.ech&&d.ech.element?`${d.ech.standard}·${d.ech.element}`:null;
    if(!e)return;
    const x=byEl[e]=byEl[e]||{req:0,opt:0,fmts:new Set()};
    d.required?x.req++:x.opt++;
    x.fmts.add((d.data_type||'')+'|'+(d.format||''));}));
  const reqDiv=Object.entries(byEl).filter(([,x])=>x.req&&x.opt).sort((a,b)=>(b[1].req+b[1].opt)-(a[1].req+a[1].opt));
  const fmtDiv=Object.entries(byEl).filter(([,x])=>x.fmts.size>2).sort((a,b)=>b[1].fmts.size-a[1].fmts.size);
  h+=`<div class="card"><div class="dvsub">Pflicht-Divergenz — dasselbe Datum hier Pflicht, dort freiwillig (${reqDiv.length} Elemente; legitim nur bei abweichender Rechtsgrundlage)</div>
    <table class="ft"><thead><tr><th>eCH-Element</th><th>Pflicht</th><th>optional</th></tr></thead><tbody>
    ${reqDiv.slice(0,15).map(([e,x])=>`<tr><td class="mono small">${esc(e)}</td><td>${x.req}</td><td>${x.opt}</td></tr>`).join('')}
    </tbody></table></div>`;
  h+=`<div class="card"><div class="dvsub">Format-Divergenz — dasselbe Datum in mehr als zwei Format-Varianten (${fmtDiv.length} Elemente)</div>
    <table class="ft"><thead><tr><th>eCH-Element</th><th>Varianten</th></tr></thead><tbody>
    ${fmtDiv.slice(0,15).map(([e,x])=>`<tr><td class="mono small">${esc(e)}</td><td>${x.fmts.size}</td></tr>`).join('')}
    </tbody></table></div>`;
  // code-list check: the swept XSDs define enumerations (sex 1/2/3, maritalStatus 1..9 ...);
  // a form that offers its own value list must be mapped onto those codes at exchange time
  const CL=DATA.ech_codelists||{}; const clRows=[]; const clSeen={};
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>{
    if(!(d.ech&&d.ech.element&&d.ech.datatype)) return;
    const cl=CL[d.ech.standard+'|'+d.ech.datatype]; if(!cl) return;
    const vals=(d.allowed_values||[]).map(String); if(!vals.length) return;
    const codes=new Set(cl.map(c=>c.value)), docs=new Set(cl.map(c=>(c.doc||'').toLowerCase()).filter(Boolean));
    const asCode=vals.filter(v=>codes.has(v)).length, asDoc=vals.filter(v=>docs.has(v.toLowerCase())).length;
    const key=d.ech.standard+'·'+d.ech.element; const x=clSeen[key]=clSeen[key]||{el:key,dt:d.ech.datatype,n:0,codeOk:0,text:0,forms:new Set(),sample:vals.slice(0,4),cl};
    x.n++; x.forms.add(f); if(asCode===vals.length) x.codeOk++; else x.text++;}));
  const clList=Object.values(clSeen).sort((a,b)=>b.n-a.n);
  h+=`<div class="card"><div class="dvsub">Codelisten-Abgleich — Wertelisten der Formulare gegen die offiziellen Codes aus den eCH-XSDs (${clList.length} Elemente mit Codeliste; XSD-Sweep ${(()=>{const v=DATA.forms.flatMap(f=>(f.data_fields||[]).map(d=>d.ech&&d.ech.xsd_version)).find(Boolean);return v?'versioniert':'';})()})</div>
    <div class="small muted" style="margin-bottom:6px">«Klartext» heisst: das Formular lässt z. B. «ledig / verheiratet» ankreuzen, der Standard tauscht den Code (1, 2, …) aus — beim Export ist die Wertliste auf die Codes abzubilden; das ist keine Rechtsfrage, aber eine Exchange-Voraussetzung.</div>
    <table class="ft"><thead><tr><th>eCH-Element</th><th>Typ</th><th>offizielle Codes</th><th>Felder</th><th>Codes verwendet</th><th>Klartext</th><th>Beispielwerte</th></tr></thead><tbody>
    ${clList.slice(0,20).map(x=>`<tr><td class="mono small">${esc(x.el)}</td><td class="mono small">${esc(x.dt)}</td><td class="small" title="${esc(x.cl.slice(0,20).map(c=>c.value+(c.doc?' = '+c.doc:'')).join('\n'))}">${x.cl.length}</td><td>${x.n}</td><td>${x.codeOk}</td><td>${x.text?`<span class="badge b-unver">${x.text}</span>`:'—'}</td><td class="small muted">${esc(x.sample.join(' · '))}</td></tr>`).join('')}
    </tbody></table>${clList.length?'':'<div class="small muted">Keine Felder mit Werteliste auf einem Element mit Codeliste.</div>'}</div>`;
  // the catalogue itself, most-collected first
  h+=`<div class="card"><table class="ft"><thead><tr><th>Datum</th><th>Standard-Element</th>
    <th>Formulare</th><th>Erhebungen</th><th>Register</th><th>⛨</th></tr></thead><tbody>`;
  // which forms collect a given element (for the expandable rows)
  const collectors={};
  DATA.forms.forEach(f=>(f.data_fields||[]).forEach(d=>{
    const push=e=>{if(e&&e.element)(collectors[`${e.standard}·${e.element}`]=collectors[`${e.standard}·${e.element}`]||new Set()).add(f);};
    push(d.ech);(d.subfields||[]).forEach(s=>{if(s&&typeof s==='object')push(s.ech);});}));
  kat.slice(0,120).forEach(a=>{
    const el=a.ech_standard?`${a.ech_standard}·${a.ech_element}`:(a.esh_key||'');
    let cats=[]; try{cats=JSON.parse(a.sensitive_categories||'[]')}catch(e){}
    const fms=[...(collectors[el]||[])];
    h+=`<tr class="katrow" data-el="${esc(el)}"><td><b>${esc(a.label)}</b></td><td class="mono small">${esc(el)}</td>
      <td>${a.n_forms}</td><td>${a.n_instances}</td>
      <td>${a.register_source?'<span class="badge b-dvsh">Einwohnerregister</span>':'—'}</td>
      <td>${cats.length?`<span class="badge b-sens" title="auf mindestens einem Formular in sensitivem Kontext erhoben">⛨ ${cats.map(x=>esc(HSENS[x]||x)).join(', ')}</span>`:''}</td></tr>
      ${fms.length?`<tr class="katforms" hidden><td colspan="6">${fms.slice(0,30).map(f=>`<a class="simlink small" data-sid="${f.service_id}">• ${esc(f.title)}</a>`).join('<br>')}</td></tr>`:''}`;});
  h+=`</tbody></table><div class="muted small" style="padding:6px 2px">Die 120 meist-erhobenen von ${kat.length} Attributen; vollständig im LLM-Export. Zeile anklicken = erhebende Formulare.</div></div>`;
  m.innerHTML=h;
  m.querySelectorAll('.katrow').forEach(tr=>tr.onclick=()=>{
    const nx=tr.nextElementSibling;
    if(nx&&nx.classList.contains('katforms')) nx.hidden=!nx.hidden;});
  m.querySelectorAll('.simlink[data-sid]').forEach(a=>a.onclick=(ev)=>{ev.stopPropagation();
    state.service=a.dataset.sid;state.tab='fields';state.sub='felder';render();});
}
function viewEsh(){
  const m=document.getElementById('main');
  const kat=DATA.esh_katalog||[];
  let h=pageHead('eSH-Katalog · E-Schaffhausen-Standard (ENTWURF)',
    `Unser eigener Entwurf eines kantonalen Datenstandards für die ${kat.reduce((n,k)=>n+(k.n_felder||0),0)} Datenpunkte, die kein eCH-Standard abdeckt — 25 Standards, abgeleitet aus den realen Formularfeldern.`,
    'Eigenleistung dieses Projekts, NICHT offiziell; im ganzen Dashboard violett-gestrichelt und als «Entwurf» markiert, damit er nie mit offiziellem eCH verwechselt wird (Konvention 7: eSH überdeckt nie ein eCH-Element).',
    'Gedacht als Diskussionsgrundlage für den Kanton — jeder Code zeigt, wie viele reale Datenpunkte er abdecken würde.');
  if(!kat.length){m.innerHTML=h+'<div class="nores">Noch kein Katalog geladen.</div>';return;}
  kat.forEach(k=>{
    let th=[]; try{th=JSON.parse(k.themen||'[]')}catch(e){}
    h+=`<div class="card"><div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
      <span class="eshb" style="font-size:12px">${esc(k.code)}</span><b style="font-size:14px">${esc(k.titel)}</b>
      <span class="muted small" style="margin-left:auto">${k.n_felder||0} Datenpunkte · Status: ${esc(k.status||'entwurf')}</span></div>
      <div class="dfdef" style="margin-top:6px">${esc(k.beschreibung||'')}</div>
      ${th.length?`<div class="dfchips" style="margin-top:6px">${th.map(t=>`<span class="chip">${esc(t)}</span>`).join('')}</div>`:''}
    </div>`;
  });
  m.innerHTML=h;
}
// ---------- Handlungsbedarf: every open item, grouped by the office that owns it ----------
// One entry per kind of open item. 'art' says what KIND of work closes it:
//   recherche  - the databank has not looked yet (our backlog)
//   entscheid  - only the canton can decide (we never fake a default)
//   bereinigung - the Fachstelle has to change the form or its practice
const TODO_CATS=[
  ['ermitteln','Rechtsgrundlage zu ermitteln','b-unver','recherche',
   'Für das Feld ist noch keine Rechtsgrundlage recherchiert — weder ein Artikel noch ein Befund «aufgabennotwendig». Eine Wissenslücke der Databank, kein festgestellter Verstoss.'],
  ['offen','Aufgabenbedarf offen','b-unver','entscheid',
   'Keine Norm nennt das Feld; ob die gesetzliche Aufgabe es zwingend braucht (KDSG Art. 4 Abs. 1 lit. b), konnte aus dem Formular allein nicht entschieden werden.'],
  ['ohne','Over-collection bereinigen','b-over','bereinigung',
   'Weder eine Norm noch die Aufgabe verlangt das Feld. Optionen: Feld streichen, oder die ausdrückliche Einwilligung der Person einholen (KDSG Art. 4 Abs. 1 lit. c).'],
  ['zweck','Zweck nicht erfasst','b-unver','recherche',
   'Der Bearbeitungszweck — Kernangabe jedes Verzeichnisses (Struktur nach KDSG Art. 17b Abs. 2) — ist für dieses Formular noch nicht festgehalten.'],
  ['empf','Empfänger nicht dokumentiert','b-unver','recherche',
   'Keine belegte Bekanntgabe erfasst. Entweder es gibt keine (dann ist genau das festzuhalten) oder sie ist noch nicht mit Artikel dokumentiert.'],
  ['dsfa','DSFA-Entscheid offen','b-sens','entscheid',
   'Die berechnete Triage zeigt eine hohe Dichte besonders schützenswerter Felder; ob eine Datenschutz-Folgenabschätzung (KDSG Art. 14b) nötig ist, hat der Kanton noch nicht entschieden.'],
  ['ech','eCH-Zuordnung offen','b-unver','recherche',
   'Das Feld ist noch nicht gegen den eCH-Katalog geprüft, oder es ist nur der Standard, nicht das konkrete XML-Element bestimmt.'],
  ['echalt','eCH-Standard nicht in Kraft','b-over','recherche',
   'Der zugeordnete eCH-Standard ist aufgehoben, abgelöst oder sistiert — die Zuordnung ist durch den Nachfolger zu ersetzen.'],
  ['veraltet','Formular-Fassung prüfen','b-over','bereinigung',
   'Die Online-Prüfung meldet eine neuere Fassung, einen Verdacht darauf, oder das Formular wird online nicht mehr angeboten.'],
  ['dup','Duplikat-Verdacht unentschieden','b-unver','entscheid',
   'Ein anderes Formular verlangt einen sehr ähnlichen Feldsatz. Ob die beiden zusammengelegt werden sollen, ist nicht beurteilt.'],
  ['felder','Datenfeld-Schicht fehlt','b-unver','recherche',
   'Für dieses Formular sind noch keine Datenfelder modelliert — alle anderen Prüfungen sind blind.'],
  ['rechtsmittel','Rechtsmittel nicht bestimmt','b-unver','recherche',
   'Das Verfahren endet mit einem anfechtbaren Entscheid, aber weder eine Spezialnorm noch die allgemeine VRG-Regel konnte belegt zugeordnet werden (z. B. Registerverfahren nach Bundesrecht).'],
];
const TODO_ART={recherche:'Recherche (Databank)',entscheid:'Entscheid (Kanton)',bereinigung:'Bereinigung (Fachstelle)'};
const TODO_BY=Object.fromEntries(TODO_CATS.map(c=>[c[0],c]));
const CHECK_DE={veraltet:'neuere Fassung online',veraltet_verdacht:'evtl. veraltet',nicht_auffindbar:'nicht mehr online',nicht_gefunden:'online nicht gefunden'};
function todoItems(f){
  const dfs=f.data_fields||[]; const it=[];
  if(!dfs.length){ it.push({cat:'felder',n:1,detail:'keine Datenfelder modelliert'}); return it; }
  const nE=dfs.filter(d=>!d.basis_typ&&!(d.legal_basis||[]).length).length;
  if(nE) it.push({cat:'ermitteln',n:nE,detail:`${nE} Feld${nE===1?'':'er'} ohne recherchierte Grundlage`});
  const nO=dfs.filter(d=>d.basis_typ==='offen'); if(nO.length) it.push({cat:'offen',n:nO.length,detail:nO.map(d=>d.name).join(' · ')});
  const nX=dfs.filter(d=>d.basis_typ==='ohne'); if(nX.length) it.push({cat:'ohne',n:nX.length,detail:nX.map(d=>d.name).join(' · ')});
  if(!f.purpose) it.push({cat:'zweck',n:1,detail:'Zweck fehlt im Verzeichnis'});
  if(!(f.disclosures||[]).length) it.push({cat:'empf',n:1,detail:'keine belegte Bekanntgabe erfasst'});
  const fs=formStats(f); if(fs.dsfaInd&&!f.dsfa_status) it.push({cat:'dsfa',n:1,detail:`${fs.sens} von ${fs.n} Feldern besonders schützenswert`});
  const eN=dfs.filter(d=>!d.ech_status).length, eS=dfs.filter(d=>d.ech_status==='standard_only').length;
  if(eN+eS) it.push({cat:'ech',n:eN+eS,detail:[eN?`${eN} nicht geprüft`:'',eS?`${eS} Element offen`:''].filter(Boolean).join(', ')});
  const bad=new Set(['Aufgehoben','Abgelöst','Sistiert']); const alt=[];
  dfs.forEach(d=>{if(d.ech&&bad.has(d.ech.status))alt.push(d.name);
    (d.subfields||[]).forEach(s=>{if(s&&s.ech&&bad.has(s.ech.status))alt.push(s.name);});});
  if(alt.length) it.push({cat:'echalt',n:alt.length,detail:alt.join(' · ')});
  if(f.check&&CHECK_DE[f.check.status]) it.push({cat:'veraltet',n:1,detail:CHECK_DE[f.check.status]+(f.check.note?' — '+f.check.note:'')});
  const du=(f.similar||[]).filter(s=>!s.verdict); if(du.length) it.push({cat:'dup',n:du.length,detail:du.map(s=>`${s.titel} (${Math.round(s.jaccard*100)}% gleiche Felder)`).join(' · ')});
  const o=f.outcome; if(o&&o.entscheid_art&&!['kein_entscheid','unbekannt'].includes(o.entscheid_art)&&!o.rechtsmittel_quelle)
    it.push({cat:'rechtsmittel',n:1,detail:(OUTCOME_DE[o.entscheid_art]||o.entscheid_art)+(o.rechtsmittel_verdikt?' — '+o.rechtsmittel_verdikt:'')});
  return it;
}
function dstOf(f){const s=svcById[f.service_id];return (s&&s.dienststelle)||f.publisher_dienststelle||'(ohne Dienststelle)';}
const dstInfo=Object.fromEntries((DATA.dienststellen||[]).map(d=>{
  let k=[]; try{k=JSON.parse(d.kontakt||'[]');}catch(e){k=d.kontakt?[d.kontakt]:[];}
  return [d.name,{department:d.department,kontakt:k}];}));
function viewTodo(){
  const m=document.getElementById('main');
  const cat=(state.sub&&TODO_BY[state.sub])?state.sub:'alle';
  // every form once; its open items; grouped by the owning Dienststelle
  const groups={}; const tot={}; let nForms=0, nItems=0;
  DATA.forms.forEach(f=>{
    const its=todoItems(f).filter(i=>cat==='alle'||i.cat===cat); if(!its.length) return;
    nForms++; its.forEach(i=>{tot[i.cat]=(tot[i.cat]||0)+i.n; nItems+=i.n;});
    const dn=dstOf(f); (groups[dn]=groups[dn]||{forms:[],n:0,fields:0}).forms.push({f,its});
    groups[dn].n+=its.reduce((a,i)=>a+i.n,0); groups[dn].fields+=(f.data_fields||[]).length;});
  const allTot={}; DATA.forms.forEach(f=>todoItems(f).forEach(i=>{allTot[i.cat]=(allTot[i.cat]||0)+i.n;}));
  let h=pageHead('Handlungsbedarf · Offene Punkte je Dienststelle',
    'Alles, was die Databank als offen kennt — Rechtsgrundlagen, Zwecke, Empfänger, DSFA-Entscheide, eCH-Zuordnungen, veraltete Fassungen, Duplikat-Verdachte — sortiert nach der Dienststelle, die es lösen kann, mit deren Kontakt aus dem DVSH.',
    'Berechnet aus der kuratierten Feld-Schicht, dem Verzeichnis, der Online-Prüfung und dem Duplikat-Radar. Die Schutzstufe (ISV) fehlt für ALLE Felder, weil der Kanton sie noch nicht festgelegt hat — sie steht deshalb einmal je Dienststelle, nicht je Formular.',
    'Ein offener Punkt ist eine Lücke im Wissen oder eine ausstehende Entscheidung — kein festgestellter Verstoss. Die Spalte «Art» sagt, wer den Punkt schliessen kann.');
  h+=`<div class="todocats">${TODO_CATS.map(c=>`<span class="tcat${cat===c[0]?' on':''}" data-cat="${c[0]}" title="${esc(c[4])}"><span class="badge ${c[2]}">&nbsp;</span>${esc(c[1])} <b>${allTot[c[0]]||0}</b></span>`).join('')}
    <span class="tcat${cat==='alle'?' on':''}" data-cat="alle">alle Punkte <b>${Object.values(allTot).reduce((a,b)=>a+b,0)}</b></span>
    <button class="srcbtn" id="todocsv" title="Arbeitsliste als CSV (Semikolon, UTF-8) — eine Zeile je Formular und Punkt">⇩ Arbeitsliste (CSV)</button></div>`;
  h+=`<details class="card todoexpl"><summary><b>Was die Punkte bedeuten und wer sie schliessen kann</b></summary>
    <table class="ft"><thead><tr><th>Punkt</th><th>Art</th><th>Bedeutung</th></tr></thead><tbody>${TODO_CATS.map(c=>`<tr><td><span class="badge ${c[2]}">${esc(c[1])}</span></td><td class="small">${esc(TODO_ART[c[3]])}</td><td>${esc(c[4])}</td></tr>`).join('')}
    <tr><td><span class="badge b-unver">Schutzstufe fehlt</span></td><td class="small">Entscheid (Kanton)</td><td>Für kein Datenfeld ist eine ISV-Schutzstufe festgelegt. Das ist eine kantonale Klassifizierungsentscheidung; die Databank setzt bewusst keine Standardwerte.</td></tr></tbody></table>
    <div class="small muted" style="margin-top:6px">Recherche (Databank) = die Databank hat noch nicht nachgeschaut · Entscheid (Kanton) = nur die zuständige Stelle kann das entscheiden · Bereinigung (Fachstelle) = das Formular oder die Praxis muss geändert werden.</div></details>`;
  h+=`<div class="regstats"><span class="rstat">Formulare mit offenen Punkten <b>${nForms}/${DATA.forms.length}</b></span>
    <span class="rstat">Dienststellen <b>${Object.keys(groups).length}</b></span>
    <span class="rstat">Punkte${cat!=='alle'?' («'+esc(TODO_BY[cat][1])+'»)':''} <b>${nItems}</b></span></div>`;
  const csv=[['Dienststelle','Departement','Kontakt','Service','Formular','Punkt','Art','Anzahl','Detail']];
  Object.entries(groups).sort((a,b)=>b[1].n-a[1].n).forEach(([dn,g])=>{
    const info=dstInfo[dn]||{}; const dep=info.department||(svcById[g.forms[0].f.service_id]||{}).department||'';
    h+=`<div class="card dstcard" id="dst-${esc(dn).replace(/[^A-Za-z0-9]+/g,'-')}"><div class="dsthead"><h4>${esc(dn)}</h4>
      <span class="muted small">${esc(dep)}</span>
      <span class="muted small" style="margin-left:auto">${g.forms.length} Formular${g.forms.length===1?'':'e'} · <b>${g.n}</b> Punkte</span></div>
      ${info.kontakt&&info.kontakt.length?`<div class="dstkontakt" title="Kontakt laut DVSH-Dienstleistungsmodell">☏ ${info.kontakt.map(esc).join(' · ')}</div>`:`<div class="dstkontakt muted">Kontakt: nicht im DVSH hinterlegt</div>`}
      ${g.fields?`<div class="dstkontakt muted">Schutzstufe (ISV) für ${g.fields} Datenfelder in ${g.forms.length} Formularen nicht festgelegt — kantonaler Entscheid ausstehend</div>`:''}
      <table class="ft"><thead><tr><th>Formular</th><th>Offene Punkte</th></tr></thead><tbody>`;
    g.forms.sort((a,b)=>b.its.reduce((x,i)=>x+i.n,0)-a.its.reduce((x,i)=>x+i.n,0)).forEach(({f,its})=>{
      const svc=svcById[f.service_id];
      h+=`<tr><td><a class="simlink" data-sid="${f.service_id}" data-fid="${f.id}">${esc(f.title)}</a>${svc&&svc.name!==f.title?`<div class="small muted">${esc(svc.name)}</div>`:''}</td>
        <td>${its.map(i=>{const c=TODO_BY[i.cat];return `<span class="tchip badge ${c[2]}" data-sid="${f.service_id}" data-fid="${f.id}" data-cat="${i.cat}" title="${esc(TODO_ART[c[3]])} — ${esc(i.detail||'')}">${esc(c[1])}${i.n>1?` <b>${i.n}</b>`:''}</span>`;}).join('')}</td></tr>`;
      its.forEach(i=>csv.push([dn,dep,(info.kontakt||[]).join(' / '),svc?svc.name:'',f.title,TODO_BY[i.cat][1],TODO_ART[TODO_BY[i.cat][3]],String(i.n),i.detail||'']));
    });
    h+=`</tbody></table></div>`;
  });
  if(!Object.keys(groups).length) h+='<div class="nores">Keine offenen Punkte dieser Art.</div>';
  m.innerHTML=h;
  m.querySelectorAll('.tcat').forEach(c=>c.onclick=()=>{state.sub=c.dataset.cat;render();});
  // a Formular name opens its Einzelansicht; a chip opens the segment where the point lives
  m.querySelectorAll('.simlink[data-fid]').forEach(a=>a.onclick=()=>{state.service=a.dataset.sid;state.tab='fields';state.sub='form-'+a.dataset.fid;render();});
  m.querySelectorAll('.tchip').forEach(c=>c.onclick=()=>{state.service=c.dataset.sid;state.tab='fields';
    state.sub=(c.dataset.cat==='veraltet'||c.dataset.cat==='dup'||c.dataset.cat==='felder')?'form-'+c.dataset.fid:'felder';render();});
  const b=document.getElementById('todocsv'); if(b) b.onclick=()=>{
    const q=v=>'"'+String(v).replace(/"/g,'""')+'"';
    const txt='﻿'+csv.map(r=>r.map(q).join(';')).join('\r\n');
    const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([txt],{type:'text/csv;charset=utf-8'}));
    a.download='handlungsbedarf'+(cat!=='alle'?'-'+cat:'')+'.csv'; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),2000);};
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
    ix.push({t:'Formular',label:f.title,sub:svc?svc.name:'',key:lc(f.title+' '+(f.purpose||'')),go:fmLink(f)});
    (f.data_fields||[]).forEach(d=>{
      ix.push({t:'Datenfeld',label:d.name,sub:f.title+(d.ech&&d.ech.element?' · '+d.ech.standard+' '+d.ech.element:''),
        key:lc(d.name+' '+(d.definition||'')+' '+(d.ech?d.ech.standard+' '+(d.ech.element||''):'')),go:{tab:'fields',service:f.service_id,sub:'felder'}});
      if(d.ech&&d.ech.standard){const e=ech[d.ech.standard]=ech[d.ech.standard]||{titel:d.ech.standard_titel||'',n:0};e.n++;}
    });
    (f.disclosures||[]).forEach(x=>{const e=recip[x.empfaenger]=recip[x.empfaenger]||{forms:new Set(),arts:new Set()};e.forms.add(f);e.arts.add(`${x.short_title} ${x.article_no}`);});
    (f.beilagen||[]).forEach(b=>{const e=beil[b.bezeichnung]=beil[b.bezeichnung]||{forms:new Set(),halter:b.halter};e.forms.add(f);});
  });
  Object.entries(recip).forEach(([n,e])=>ix.push({t:'Empfänger',label:n,sub:`Bekanntgabe aus ${e.forms.size} Formular${e.forms.size===1?'':'en'} · ${[...e.arts].slice(0,3).join(', ')}`,key:lc(n),links:[...e.forms].slice(0,6).map(fmLink)}));
  Object.entries(beil).forEach(([n,e])=>ix.push({t:'Beilage',label:n,sub:`verlangt in ${e.forms.size} Formular${e.forms.size===1?'':'en'}${e.halter?' · Halter: '+e.halter:''}`,key:lc(n),links:[...e.forms].slice(0,6).map(fmLink)}));
  Object.entries(ech).forEach(([c,e])=>ix.push({t:'eCH-Standard',label:c,sub:`${e.titel} · ${e.n} Felder`,key:lc(c+' '+e.titel),go:{tab:'katalog',service:'all',sub:'felder'}}));
  const ruleLaws=new Set((DATA.datenhandhabung||[]).map(r=>r.law_id));
  const ruleArts=new Set((DATA.datenhandhabung||[]).map(r=>r.law_id+'|'+r.article_no));
  (DATA.laws||[]).forEach(l=>{
    const fms=[...(formsByLaw[l.id]||[])];
    const jl=l.jurisdiction_level==='federal'?'Bund':l.jurisdiction_level==='cantonal'?'Kanton':'Gemeinde';
    const nr=l.sr_number?(l.jurisdiction_level==='federal'?'SR ':'SHR ')+l.sr_number:(l.cantonal_ref||'');
    const base={sub:`${jl}${nr?' · '+nr:''}${fms.length?' · von Feldern in '+fms.length+' Formularen zitiert':''}${ruleLaws.has(l.id)?' · Regeln im Tab Datenhandhabung':''}`,
      go:ruleLaws.has(l.id)?{tab:'rules',service:'all',sub:'felder',anchor:'law-'+l.id}:null,links:fms.slice(0,6).map(f=>({tab:'fields',service:f.service_id,sub:'gesetze',label:f.title}))};
    ix.push(Object.assign({t:'Gesetz',label:(l.short_title?l.short_title+' — ':'')+l.title,key:lc(l.title+' '+(l.short_title||'')+' '+(l.sr_number||'')+' '+(l.cantonal_ref||''))},base));
    (l.articles||[]).forEach(a=>{const fa=[...(formsByArt[l.id+'|'+a.article_no]||[])];
      if(!a.heading&&!fa.length&&!ruleArts.has(l.id+'|'+a.article_no)) return;
      ix.push({t:'Artikel',label:`${artLabel(a.article_no)} ${l.short_title||l.title}${a.heading?' — '+a.heading:''}`,
        sub:`${jl}${nr?' · '+nr:''}${fa.length?' · zitiert in '+fa.length+' Formularen':''}`,key:lc(artLabel(a.article_no)+' '+a.article_no+' '+(a.heading||'')+' '+(l.short_title||'')+' '+l.title),
        go:base.go,links:fa.slice(0,6).map(f=>({tab:'fields',service:f.service_id,sub:'gesetze',label:f.title}))});});
  });
  (DATA.datenhandhabung||[]).forEach(r=>ix.push({t:'Regel',label:r.summary,sub:`${r.short_title||r.law_title} ${artLabel(r.article_no)} · ${ASPECT[r.aspect]||r.aspect} · ${r.scope}`,
    key:lc(r.summary+' '+(r.quote||'')+' '+(r.short_title||'')+' '+r.article_no),go:{tab:'rules',service:'all',sub:'felder',anchor:`law-${r.law_id}-${r.scope}`}}));
  (DATA.dienststellen||[]).forEach(d=>ix.push({t:'Dienststelle',label:d.name,sub:d.department||'',key:lc(d.name+' '+(d.department||'')),go:{tab:'todo',service:'all',sub:'alle',anchor:'dst-'+d.name.replace(/[^A-Za-z0-9]+/g,'-')}}));
  return SIDX=ix;
}
function hl(text,toks){let s=esc(text);toks.forEach(t=>{if(!t)return;s=s.replace(new RegExp('('+t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','ig'),'<mark class="hl">$1</mark>');});return s;}
function goTo(g){state.tab=g.tab;state.service=g.service==null?'all':g.service;state.sub=g.sub||'felder';render();
  if(g.anchor){const t=document.getElementById(g.anchor);if(t){t.scrollIntoView({behavior:'smooth'});t.classList.add('flash');setTimeout(()=>t.classList.remove('flash'),1600);}}}
function viewSearch(){
  const m=document.getElementById('main');
  let q=''; try{q=decodeURIComponent(state.sub||'');}catch(e){q=state.sub||'';}
  if(q==='felder') q='';
  const inp=document.getElementById('gsearch'); if(inp&&inp.value!==q) inp.value=q;
  const toks=q.toLowerCase().split(/\s+/).filter(t=>t.length>=2);
  let h=pageHead('Suche · über alle Inhalte',
    'Ein Suchfeld über Services, Formulare, Datenfelder, Gesetze und Artikel, Datenhandhabungs-Regeln, Empfänger, Beilagen, eCH-Standards und Dienststellen.',
    'Durchsucht wird der Export der Databank, wie er in dieser Seite steckt — nichts Externes. Alle Wörter müssen vorkommen (Reihenfolge egal, Gross/Klein egal).',
    'Ein Treffer springt an die Stelle, an der das Objekt in der Databank lebt: Service-Seite, Einzelansicht, Regel-Karte, Katalog oder Handlungsbedarf.');
  if(!toks.length){m.innerHTML=h+'<div class="nores">Mindestens ein Wort mit zwei Zeichen eingeben — z. B. «AHV-Nummer», «Art. 17b», «Steuerverwaltung», «Aufbewahrung 10 Jahre».</div>';return;}
  // rank: whole-word matches (so «17b» prefers Art. 17b over Art. 317bis), then label matches
  const wb=(s,t)=>{const i=s.indexOf(t);return i>=0&&(i===0||!/[a-z0-9äöü]/.test(s[i-1]));};
  const hits=searchIndex().filter(e=>toks.every(t=>e.key.includes(t)))
    .map(e=>{const L=e.label.toLowerCase();return {e,sc:(L.startsWith(toks[0])?2:0)+(toks.every(t=>L.includes(t))?1:0)+(toks.every(t=>wb(e.key,t))?3:0)};})
    .sort((a,b)=>b.sc-a.sc);
  const order=['Service','Formular','Datenfeld','Gesetz','Artikel','Regel','Empfänger','Beilage','eCH-Standard','Dienststelle'];
  const byT={}; hits.forEach(x=>(byT[x.e.t]=byT[x.e.t]||[]).push(x.e));
  h+=`<div class="regstats">${order.filter(t=>byT[t]).map(t=>`<span class="rstat">${esc(t)} <b>${byT[t].length}</b></span>`).join('')}${hits.length?'':'<span class="rstat">keine Treffer</span>'}</div>`;
  let gi=0; const linkStore=[];
  order.forEach(t=>{const L=byT[t]; if(!L) return; const id='sg'+(gi++);
    h+=`<div class="card sres"><div class="dvsub">${esc(t)} · ${L.length}</div>`;
    L.forEach((e,i)=>{const li=linkStore.push(e)-1;
      h+=`<div class="srow${i>=10?' more':''}" ${i>=10?`data-more="${id}" style="display:none"`:''}><span class="stype">${esc(t)}</span><div style="flex:1">
        <div${e.go?` class="slink" data-li="${li}" style="cursor:pointer"`:''}>${hl(e.label,toks)}</div>
        ${e.sub?`<div class="small muted">${hl(e.sub,toks)}</div>`:''}
        ${(e.links||[]).length?`<div class="small">→ ${e.links.map((g,k)=>`<a class="simlink" data-li="${li}" data-k="${k}">${esc(g.label)}</a>`).join(' · ')}</div>`:''}</div></div>`;});
    if(L.length>10) h+=`<a class="simlink small" data-showmore="${id}">alle ${L.length} anzeigen</a>`;
    h+=`</div>`;});
  m.innerHTML=h;
  m.querySelectorAll('.slink').forEach(a=>a.onclick=()=>goTo(linkStore[+a.dataset.li].go));
  m.querySelectorAll('.simlink[data-k]').forEach(a=>a.onclick=()=>goTo(linkStore[+a.dataset.li].links[+a.dataset.k]));
  m.querySelectorAll('[data-showmore]').forEach(a=>a.onclick=()=>{m.querySelectorAll(`[data-more="${a.dataset.showmore}"]`).forEach(r=>r.style.display='');a.remove();});
}
// ---------- Datenfluss: who passes data to whom, from the article-backed disclosures ----------
const MODE_DE={systematisch:'systematisch',auf_anfrage:'auf Anfrage'};
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
    'Die belegten Bekanntgaben aus allen Formularen, verdichtet zu Verbindungen: sendende Dienststelle → Empfänger, je mit Modus, Formularen und dem Artikel, der die Weitergabe erlaubt.',
    `Quelle sind die ${DATA.forms.reduce((a,f)=>a+(f.disclosures||[]).length,0)} Empfänger-Einträge des Verzeichnisses (nur mit Artikel-Beleg geladen). ${nFormsWith} von ${DATA.forms.length} Formularen haben dokumentierte Bekanntgaben — für die übrigen ist die Weitergabe noch nicht erfasst, was nicht heisst, dass es keine gibt (siehe Handlungsbedarf).`,
    '«systematisch» = regelmässige Meldung von Gesetzes wegen (z. B. an die Zentrale Ausgleichsstelle); «auf Anfrage» = Amtshilfe auf Ersuchen im Einzelfall. Linienstärke = Anzahl Formulare. Klick auf eine Dienststelle oder einen Empfänger hebt die Verbindungen hervor; Klick auf eine Linie listet die Formulare.');
  h+=`<div class="regstats"><span class="rstat">Dienststellen mit Bekanntgaben <b>${S.length}</b></span>
    <span class="rstat">Empfänger <b>${R.length}</b></span><span class="rstat">Verbindungen <b>${E.length}</b></span>
    <span class="rstat">davon systematisch <b>${nSys}</b> · auf Anfrage <b>${nAnf}</b></span>
    <span class="rstat">Formulare mit belegter Bekanntgabe <b>${nFormsWith}/${DATA.forms.length}</b></span></div>`;
  if(!E.length){m.innerHTML=h+'<div class="nores">Keine belegten Bekanntgaben geladen.</div>';return;}
  // bipartite diagram: senders left, recipients right
  const rowH=22, top=28, W=980, H=top+Math.max(S.length,R.length)*rowH+20, xL=300, xR=W-320;
  const yS=Object.fromEntries(S.map((s,i)=>[s,top+i*rowH+rowH/2])), yR=Object.fromEntries(R.map((r,i)=>[r,top+i*rowH+rowH/2]));
  const short=(t,n)=>t.length>n?t.slice(0,n-1)+'…':t;
  let svg=`<svg class="flowsvg" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Datenfluss-Diagramm">
    <text x="${xL}" y="16" text-anchor="end" class="flowhd">Dienststelle (gibt bekannt)</text>
    <text x="${xR}" y="16" class="flowhd">Empfänger</text>`;
  E.forEach((e,i)=>{const y1=yS[e.s], y2=yR[e.r], w=1+Math.log2(e.forms.size);
    svg+=`<path class="fe ${e.mode||'unbekannt'}" data-i="${i}" data-s="${esc(e.s)}" data-r="${esc(e.r)}" d="M${xL+6},${y1} C${(xL+xR)/2},${y1} ${(xL+xR)/2},${y2} ${xR-6},${y2}" stroke-width="${w.toFixed(1)}" fill="none"><title>${esc(e.s)} → ${esc(e.r)} · ${MODE_DE[e.mode]||'Modus unbekannt'} · ${e.forms.size} Formular${e.forms.size===1?'':'e'} · ${esc([...e.arts].join(', '))}</title></path>`;});
  S.forEach(s=>{svg+=`<text class="fn" data-s="${esc(s)}" x="${xL}" y="${yS[s]+4}" text-anchor="end"><title>${esc(s)} · ${senders[s]} Bekanntgabe-Einträge</title>${esc(short(s,44))}</text>`;});
  R.forEach(r=>{svg+=`<text class="fn" data-r="${esc(r)}" x="${xR}" y="${yR[r]+4}"><title>${esc(r)} · aus ${recips[r]} Formularen</title>${esc(short(r,48))}</text>`;});
  svg+='</svg>';
  h+=`<div class="card"><div class="flowleg"><span><i class="fl sys"></i> systematisch</span><span><i class="fl anf"></i> auf Anfrage</span><span class="muted small">Linienstärke = Anzahl Formulare · Reihenfolge = Anzahl Einträge</span></div>${svg}
    <div id="flowdetail" class="small muted" style="margin-top:8px">Klick auf eine Linie zeigt hier die Formulare und Artikel.</div></div>`;
  // the same information as a sortable-by-eye table
  h+=`<div class="card"><div class="dvsub">Alle Verbindungen — je Dienststelle, Empfänger, Modus</div>
    <table class="ft"><thead><tr><th>Dienststelle</th><th>Empfänger</th><th>Modus</th><th>Formulare</th><th>Erlaubnisnorm</th></tr></thead><tbody>`;
  E.slice().sort((a,b)=>a.s.localeCompare(b.s)||b.forms.size-a.forms.size).forEach(e=>{
    h+=`<tr><td>${esc(e.s)}</td><td>${esc(e.r)}</td><td><span class="badge ${e.mode==='systematisch'?'b-sourced':'b-unver'}">${esc(MODE_DE[e.mode]||'unbekannt')}</span></td>
      <td class="small">${[...e.forms].slice(0,4).map(f=>`<a class="simlink" data-sid="${f.service_id}" data-fid="${f.id}">${esc(short(f.title,50))}</a>`).join('<br>')}${e.forms.size>4?`<div class="muted">… ${e.forms.size-4} weitere</div>`:''}</td>
      <td class="small">${esc([...e.arts].join(' · '))||'<span class="miss">ohne Artikel</span>'}</td></tr>`;});
  h+=`</tbody></table></div>`;
  m.innerHTML=h;
  m.querySelectorAll('.simlink[data-fid]').forEach(a=>a.onclick=()=>{state.service=a.dataset.sid;state.tab='fields';state.sub='form-'+a.dataset.fid;render();});
  const svgEl=m.querySelector('.flowsvg'); const det=document.getElementById('flowdetail');
  const focus=(pred)=>{svgEl.querySelectorAll('.fe').forEach(p=>p.classList.toggle('dim',!pred(p)));};
  svgEl.querySelectorAll('.fn').forEach(t=>t.onclick=()=>{const s=t.dataset.s, r=t.dataset.r;
    focus(p=>s?p.dataset.s===s:p.dataset.r===r);
    const list=E.filter(e=>s?e.s===s:e.r===r);
    det.innerHTML=`<b>${esc(s||r)}</b> — ${list.length} Verbindung${list.length===1?'':'en'}: `+list.map(e=>`${esc(s?e.r:e.s)} (${MODE_DE[e.mode]||'?'}, ${e.forms.size})`).join(' · ');});
  svgEl.querySelectorAll('.fe').forEach(p=>p.onclick=()=>{const e=E[+p.dataset.i]; focus(q=>q===p);
    det.innerHTML=`<b>${esc(e.s)} → ${esc(e.r)}</b> · ${MODE_DE[e.mode]||'Modus unbekannt'} · Erlaubnisnorm: ${esc([...e.arts].join(', '))||'—'}<br>`+
      [...e.forms].map(f=>`<a class="simlink" data-sid="${f.service_id}" data-fid="${f.id}">${esc(f.title)}</a>`).join(' · ');
    det.querySelectorAll('.simlink').forEach(a=>a.onclick=()=>{state.service=a.dataset.sid;state.tab='fields';state.sub='form-'+a.dataset.fid;render();});});
  svgEl.onclick=(ev)=>{if(ev.target===svgEl){focus(()=>true);det.textContent='Klick auf eine Linie zeigt hier die Formulare und Artikel.';}};
}
// ---------- Bürgersicht: the Datentresor seen from one (synthetic) person's side ----------
function viewBuerger(){
  const m=document.getElementById('main');
  const B=DATA.buergersicht||{personen:[]}; const P=B.personen||[];
  let h=pageHead('Bürgersicht · Was der Kanton über eine Person gespeichert hat',
    'Die Auskunft, wie sie der Datentresor aus seinen Tabellen beantwortet: je Fall, welche Daten neu erhoben und welche aus früheren Fällen wiederverwendet wurden, mit Erhebungsgrundlage, Löschdatum, Belegen und jeder protokollierten Bekanntgabe.',
    'Quelle ist datentresor.db (View v_auskunft, Once-Only-Ledger, Beleg- und Zugriffsprotokoll) — ALLE PERSONEN UND WERTE SIND SYNTHETISCH ERZEUGT. Verschlüsselte Werte verlassen den Tresor nicht und erscheinen hier als «verschlüsselt». Gezeigt werden die drei Personen mit den meisten beteiligten Dienststellen.',
    'So sieht Once-Only aus der Sicht der betroffenen Person aus: ein Datum wird einmal erhoben, spätere Fälle verweisen darauf. Jede Zeile trägt die Grundlage, auf der sie gespeichert wurde — «zu ermitteln» bleibt sichtbar, nicht kaschiert.');
  h+=`<div class="synth">⚠ Beispiel mit synthetischen Daten — ${esc(B.hinweis||'keine realen Personen')}${B.verschluesselung?' · Verschlüsselung: '+esc(B.verschluesselung):''}</div>`;
  if(!P.length){m.innerHTML=h+'<div class="nores">Kein Datentresor-Export vorhanden (scripts/build_datentresor.py, dann export_json.py).</div>';return;}
  let pi=parseInt(state.sub,10); if(!(pi>=0&&pi<P.length)) pi=0;
  h+=`<div class="todocats">${P.map((p,i)=>`<span class="tcat${i===pi?' on':''}" data-pi="${i}">${esc(p.vorname)} ${esc(p.name)} <b>${p.faelle.length} Fälle</b></span>`).join('')}</div>`;
  const p=P[pi], st=p.statistik||{}; const dsts=new Set(p.faelle.map(f=>f.dienststelle));
  const formOf=id=>DATA.forms.find(f=>f.id===id);
  h+=`<div class="card"><div class="dsthead"><h4>${esc(p.vorname)} ${esc(p.name)}</h4><span class="muted small">geb. ${esc(p.geburtsdatum||'')} · ${esc(p.plz||'')} ${esc(p.ort||'')} · AHVN13 ${esc(p.ahvn13||'')} (synthetisch)</span></div>
    <div class="regstats"><span class="rstat">Fälle <b>${p.faelle.length}</b></span><span class="rstat">Dienststellen <b>${dsts.size}</b></span>
      <span class="rstat">gespeicherte Datenpunkte <b>${st.datenpunkte||0}</b></span><span class="rstat">davon verschlüsselt <b>${st.verschluesselt||0}</b></span>
      <span class="rstat">mit Artikel <b>${st.mit_artikel||0}</b></span><span class="rstat">mit Einwilligung <b>${st.mit_einwilligung||0}</b></span>
      <span class="rstat">Once-Only wiederverwendet <b>${st.wiederverwendet||0}</b></span></div>
    <div class="small muted">Wiederverwendet = ein späterer Fall hat das Datum nicht neu erhoben, sondern auf den bestehenden Datenpunkt verwiesen. «mit Artikel» zählt Datenpunkte mit belegter Erhebungsnorm; der Rest ist aufgabennotwendig, per Einwilligung oder noch «zu ermitteln».</div></div>`;
  p.faelle.forEach(f=>{const fm=formOf(f.form_id);
    h+=`<div class="card"><div class="dsthead"><h4>${esc(f.eingereicht)} · ${fm?`<a class="simlink" data-sid="${fm.service_id}" data-fid="${fm.id}">${esc(f.formular)}</a>`:esc(f.formular)}</h4>
      <span class="muted small">${esc(f.dienststelle||'')} · Entscheid: ${esc(OUTCOME_DE[f.entscheid]||f.entscheid||'—')}${f.abgeschlossen?' · abgeschlossen '+esc(f.abgeschlossen):''}</span></div>
      <div class="small" style="margin:4px 0 8px">neu erhoben <b>${f.neu.length}</b> · wiederverwendet <b>${f.wiederverwendet.length}</b> · Belege <b>${f.belege.length}</b> · Bekanntgaben <b>${f.bekanntgaben.length}</b> · Lesezugriffe protokolliert <b>${f.lesezugriffe}</b></div>`;
    if(f.neu.length){h+=`<details${f===p.faelle[0]?' open':''}><summary class="small">Neu erhobene Datenpunkte (${f.neu.length})</summary><table class="ft"><thead><tr><th>Datum</th><th>Standard</th><th>Wert</th><th>Erhebungsgrundlage</th><th>Löschdatum</th></tr></thead><tbody>`;
      f.neu.forEach(d=>{h+=`<tr><td>${esc(d.attribut)}${d.sensitive?` <span class="badge b-sens" title="besonders schützenswert: ${esc(HSENS[d.sensitive]||d.sensitive)}">⛨</span>`:''}</td>
        <td class="small">${d.ech_element?`${esc(d.ech_standard)} ${esc(d.ech_element)}${d.ech_datatype?` <span class="edt">⟨${esc(d.ech_datatype)}⟩</span>`:''}`:'<span class="muted">—</span>'}</td>
        <td class="small">${d.verschluesselt?'<span class="badge b-sens" title="AES-256-GCM; nur mit dem Schlüssel ausserhalb der DB lesbar">verschlüsselt</span>':esc(d.wert||'')}</td>
        <td class="small">${d.einwilligung?'<span class="badge b-over">Einwilligung</span> ':''}${esc(d.grundlage||'')}</td><td class="small">${esc(d.loeschdatum||'')}</td></tr>`;});
      h+=`</tbody></table></details>`;}
    if(f.wiederverwendet.length){h+=`<details><summary class="small">Wiederverwendet statt neu erhoben (${f.wiederverwendet.length})</summary><div class="small">${f.wiederverwendet.map(w=>`<div>↺ <b>${esc(w.attribut)}</b> — erhoben ${esc(w.erhoben_am)} für «${esc(w.herkunft)}» (${esc(w.herkunft_dst||'')})</div>`).join('')}</div></details>`;}
    if(f.belege.length){h+=`<details><summary class="small">Belege (${f.belege.length})</summary><div class="small">${f.belege.map(b=>`<div>${b.art==='pruefvermerk'?'✓ Prüfvermerk':'⎘ Kopie gespeichert'} — ${esc(b.bezeichnung)}${b.halter?' · Halter: '+esc(HALTER_DE[b.halter]||b.halter):''}${b.geprueft_am?' · geprüft '+esc(b.geprueft_am)+' von '+esc(b.geprueft_von||''):''}${b.loeschdatum?' · Löschung '+esc(b.loeschdatum):''}</div>`).join('')}</div></details>`;}
    if(f.bekanntgaben.length){h+=`<details><summary class="small">Bekanntgaben (${f.bekanntgaben.length})</summary><div class="small">${f.bekanntgaben.map(b=>`<div>→ <b>${esc(b.wer)}</b> · ${esc(b.zweck||'')} · ${esc(b.grundlage||'')} · ${esc(b.zeitpunkt||'')}</div>`).join('')}</div></details>`;}
    h+=`</div>`;});
  h+=`<div class="card"><div class="dvsub">Einwilligungen (${p.einwilligungen.length})</div>${p.einwilligungen.length?p.einwilligungen.map(e=>`<div class="small">${esc(e.erteilt_am)} — ${esc(e.gegenstand)}${e.formular?' («'+esc(e.formular)+'»)':''}${e.widerrufen_am?' · widerrufen '+esc(e.widerrufen_am):''}</div>`).join(''):'<div class="small muted">Keine — alle Datenpunkte dieser Person stützen sich auf eine Norm oder den Aufgabenbedarf.</div>'}</div>`;
  const mx=Math.max(1,...p.loeschkalender.map(k=>k.n));
  h+=`<div class="card"><div class="dvsub">Löschkalender — wann welche Datenpunkte fällig werden (berechnet aus den Aufbewahrungsfristen)</div>
    ${p.loeschkalender.map(k=>`<div class="lkrow"><span class="lky">${esc(k.jahr)}</span><div class="pbar" style="max-width:420px"><i style="width:${Math.round(100*k.n/mx)}%"></i></div><span class="small">${k.n}</span></div>`).join('')}
    <div class="small muted" style="margin-top:6px">Ein Datenpunkt wird nie hart gelöscht: der Status wechselt auf «vernichtet» oder «anonymisiert», und dieser Wechsel schreibt selbst einen Protokolleintrag (Trigger im Schema).</div></div>`;
  m.innerHTML=h;
  m.querySelectorAll('.tcat[data-pi]').forEach(c=>c.onclick=()=>{state.sub=c.dataset.pi;render();});
  m.querySelectorAll('.simlink[data-fid]').forEach(a=>a.onclick=()=>{state.service=a.dataset.sid;state.tab='fields';state.sub='form-'+a.dataset.fid;render();});
}
function render(){
  renderSidebar();
  if(state.tab==='home') viewHome();
  else if(state.tab==='tree'||state.tab==='info'){state.tab='fields';state.sub='gesetze';viewFields();}
  else if(state.tab==='rules') viewRules();
  else if(state.tab==='guide') viewGuide();
  else if(state.tab==='register') viewRegister();
  else if(state.tab==='todo') viewTodo();
  else if(state.tab==='search') viewSearch();
  else if(state.tab==='datenfluss') viewDatenfluss();
  else if(state.tab==='buerger') viewBuerger();
  else if(state.tab==='katalog') viewKatalog();
  else if(state.tab==='esh') viewEsh();
  else viewFields();
  writeHash();
}
// header search: Enter (or a pause in typing) opens the results page
(()=>{const i=document.getElementById('gsearch'); if(!i) return; let t=null;
  const go=()=>{const q=i.value.trim(); if(!q) return; state.tab='search'; state.service='all'; state.sub=encodeURIComponent(q); render();};
  i.addEventListener('keydown',e=>{if(e.key==='Enter'){clearTimeout(t);go();}});
  i.addEventListener('input',()=>{clearTimeout(t); t=setTimeout(()=>{if(i.value.trim().length>=3)go();},450);});})();
readHash();
render();
</script>
</body>
</html>
"""


def check_guide(conn):
    """Refuse to build if the Leitfaden cites a rule that is not in data_rule —
    the guide must never reference law the databank does not hold."""
    have = set()
    for r in conn.execute("SELECT l.sr_number sr, a.article_no art, dr.aspect, dr.scope "
                          "FROM data_rule dr JOIN article a ON a.id=dr.article_id "
                          "JOIN law l ON l.id=a.law_id"):
        have.add((r["sr"], r["art"], r["aspect"], r["scope"]))
        have.add((r["sr"], r["art"], r["aspect"], None))
    bad = []
    for sec in LEITFADEN:
        for p in sec.get("punkte", []):
            for ref in p.get("refs", []):
                scope = ref[3] if len(ref) > 3 else None
                if (ref[0], ref[1], ref[2], scope) not in have:
                    bad.append(f"{sec['id']}: {ref[0]} {ref[1]} {ref[2]} {scope or ''}".strip())
    return bad


def main():
    with open(EXPORT_PATH, encoding="utf-8") as fh:
        data = fh.read()
    conn = connect(DB_PATH)
    bad = check_guide(conn)
    conn.close()
    if bad:
        print("ABORT — Leitfaden zitiert Regeln, die nicht in der Databank sind:")
        for b in bad[:12]:
            print("  ", b)
        sys.exit(1)
    # inline as JSON text inside a <script type=application/json> (escape </ to be safe)
    safe = data.replace("</", "<\\/")
    guide = json.dumps(LEITFADEN, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("/*DATA*/", safe).replace("/*GUIDE*/", guide)
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote {DASHBOARD_PATH}  ({len(html)//1024} KB, Leitfaden: {len(LEITFADEN)} Abschnitte)")


if __name__ == "__main__":
    main()
