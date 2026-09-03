#!/usr/bin/env python3
"""Build dashboard.html from data_export.json (convention 9: generated, never edited).

The JSON is inlined into the HTML so the file opens straight from disk via file://
with no server and no fetch (offline by default). Vanilla JS, no framework.

Views:
  * sidebar filter over all Formulare, grouped by department and office
  * Felder & Rechtsgrundlagen — data fields with eCH/eSH badges, DSG flags,
    law quotes, currency check, DVSH panel
  * Gesetzes-Baum — law -> article -> data field, as list tree and node diagram
  * Geforderte Informationen — per-law required-data table
  * eSH-Katalog (Entwurf) — the draft cantonal standard catalogue

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
    <button class="tab" data-tab="esh">eSH-Katalog (Entwurf)<span class="tabsub">Kantonaler Standard-Vorschlag für eCH-Lücken</span></button>
    <h2>Steuerung &amp; Lücken</h2>
    <button class="tab" data-tab="register">Verzeichnis (Art. 17b KDSG)<span class="tabsub">Bearbeitungsverzeichnis &amp; Risiko-Triage</span></button>
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
    if((d.legal_basis||[]).length || d.no_basis) have++;}));
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
      ['b-over','Over-collection — geprüft: KEIN Gesetz verlangt dieses Feld'],
      ['b-sens','⛨ besonders schützenswert (Art. 5 lit. c DSG)'],
      ['b-dvsh','DVSH — amtliches Dienstleistungsmodell des Kantons (read-only Quelle)'],
      ['b-federal','Bund'],['b-cantonal','Kanton'],['b-communal','Gemeinde'],
    ],
    rules: [['b-sens','⛨ kategorienspezifische Regel'],['b-unver','Zitat unverifiziert'],
            ['b-federal','Bund'],['b-cantonal','Kanton']],
    register: [['b-sens','⛨ besonders schützenswerte Felder'],['b-over','ohne gesetzliche Grundlage'],
               ['b-unver','offen / fehlt']],
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
  let nDf=0,nOver=0,nSens=0,nEch=0,nPts=0;
  F.forEach(f=>(f.data_fields||[]).forEach(d=>{
    nDf++; if(d.no_basis)nOver++; if(d.sensitive)nSens++;
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
    ${tile(nOver,'Felder ohne Grundlage','register')}
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
              +(draft?`<span class="echdraft${(st==='Aufgehoben'||st==='Abgelöst')?' rep':(st==='Sistiert'?' susp':'')}" title="${
                  (st==='Aufgehoben'||st==='Abgelöst')?`Dieser eCH-Standard ist ${esc(st).toUpperCase()} — nicht mehr in Kraft, die Zuordnung muss ersetzt werden`
                : st==='Sistiert'?'Dieser eCH-Standard ist SISTIERT (ausgesetzt) — nicht in Kraft, Zuordnung vorläufig'
                : 'Dieser eCH-Standard ist noch nicht genehmigt (in Arbeit) — Zuordnung vorläufig'}">${(st==='Aufgehoben'||st==='Abgelöst')?'⛔':'⚠'} ${esc(st)}</span>`:'');})()
            :(d.ech_status==='kein_standard'?('<span class="echn" title="kein eCH-Standard deckt dieses Feld ab">kein eCH-Standard</span>'+(d.esh?`<span class="eshb" title="Vorschlag für den kantonalen Standard eSH (E-Schaffhausen) — ENTWURF, nicht offiziell: ${esc(d.esh.titel)}">${esc(d.esh.code)} · ${esc(d.esh.element||'')}<span class="ent">Entwurf</span></span>`:'')):'')}
          ${d.sensitive?`<span class="badge b-sens senslink" title="besonders schützenswerte Personendaten (Art. 5 lit. c DSG) — Klick: was zusätzlich gilt (Leitfaden)">⛨ ${esc(SENS[d.sensitive]||d.sensitive)}</span>`:''}
          ${d.format?`<span class="muted small">· ${esc(d.format)}</span>`:''}</div>
        ${d.definition?`<div class="dfdef">${esc(d.definition)}</div>`:''}
        ${subs.length?`<div class="dfchips"><span class="muted small">Teilfelder:</span> ${(d.subfields||[]).slice(0,24).map(s=>{
            const nmv=typeof s==='string'?s:(s&&s.name)||''; if(!nmv) return '';
            const e=s&&s.ech;
            const dr=e&&e.status&&e.status!=='Genehmigt'?((e.status==='Aufgehoben'||e.status==='Abgelöst')?' ⛔':' ⚠'):'';
            if(e&&e.element) return `<span class="chip sub"><b>${esc(nmv)}</b><a class="sfe" href="${esc(e.url)}" target="_blank" rel="noreferrer" title="${esc(e.standard_titel||'')} — ${esc(e.standard)} ${esc(e.element)}${e.status?' · Status: '+esc(e.status):''}">${esc(e.standard)}·${esc(e.element)}${dr}</a></span>`;
            if(e) return `<span class="chip sub"><b>${esc(nmv)}</b><a class="sfe so" href="${esc(e.url)}" target="_blank" rel="noreferrer" title="${esc(e.standard_titel||'')} — Standard ohne XSD">${esc(e.standard)}</a></span>`;
            if(s&&s.ech_status==='kein_standard') return `<span class="chip sub"><b>${esc(nmv)}</b>${s.esh?`<a class="sfe esh" title="eSH-Entwurf: ${esc(s.esh.titel)}">${esc(s.esh.code.replace('eSH-','eSH'))}·${esc(s.esh.element||'')}</a>`:`<span class="sfe none" title="kein eCH-Standard">kein Std.</span>`}</span>`;
            return `<span class="chip sub"><b>${esc(nmv)}</b></span>`;}).join('')}</div>`
          :(vals.length?`<div class="dfchips"><span class="muted small">Werte:</span> ${vals.slice(0,24).map(v=>`<span class="chip">${esc(String(v))}</span>`).join('')}</div>`:'')}
        ${(d.source_widgets||[]).length?`<div class="dfprov"><i class="ti ti-arrow-back-up"></i> erfasst durch: ${d.source_widgets.slice(0,8).map(w=>esc(String(w))).join(' · ')}</div>`:''}
      </div><div class="dfrg">${(d.legal_basis&&d.legal_basis.length)?d.legal_basis.map(b=>
          b.quote?`<details class="qd"><summary>${citeStr(b)}</summary><blockquote class="quote">«${esc(b.quote)}»</blockquote></details>`
                 :citeStr(b)).join('<br>'):(d.no_basis?'<span class="badge b-over" title="Geprüft: kein Gesetz verlangt dieses Feld — es darf nur freiwillig erhoben werden (Leitfaden «Erheben»)">Over-collection — keine gesetzliche Grundlage</span>':'<span class="badge b-unver" title="Noch nicht juristisch ermittelt — heisst NICHT, dass keine Grundlage existiert; hier fehlt Recherche, kein Recht">Rechtsgrundlage zu ermitteln</span>')}</div></div>`;
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
      ${dst&&dst.kontakt?`<span class="hubmeta" title="verantwortliche Dienststelle laut DVSH">Kontakt: ${esc(dst.kontakt)}</span>`:''}
    </div>
    ${out&&out.entscheid_art&&out.entscheid_art!=='unbekannt'?`<div class="hubout">Ergebnis des Verfahrens:
      <b>${esc(OUTCOME_DE[out.entscheid_art]||out.entscheid_art)}</b>${out.ergebnis_dokument?` — «${esc(out.ergebnis_dokument)}»`:''}
      <span class="muted small">(aus dem DVSH-Ablauftext abgeleitet)</span></div>`:''}
  </div>`;
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
    'kein geführter Flow':'noch kein Flow in flows.html'};
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
  const nb=(fm.data_fields||[]).filter(d=>d.no_basis).length;
  let frist;
  if(terms.length) frist=retLine(terms[0]);
  else if(dec.length) frist=`Kantonaler Entscheid: ${esc(String(dec[0].duration_value||''))} ${esc(dec[0].duration_unit||'')}`;
  else frist=`Standard: Registraturperiode 10–20 J., dann Staatsarchiv ${guideChip(["172.301","§ 6","aufbewahrung"])}`;
  const seen=new Set();
  const empt=emp.filter(e=>!seen.has(e.empfaenger)&&seen.add(e.empfaenger));
  return `<div class="hstrip">
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
    nFields++; if(d.no_basis) nNoBasis++;
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
    'Registerauszug nach KDSG Art. 17b je Formular (verantwortliche Stelle, Zweck, Datenkategorien, Rechtsgrundlagen, Empfänger, Aufbewahrung) plus DSFA-Triage und Dienststellen-Risikobild.',
    'Verantwortliche und Kategorien aus der kuratierten Feld-Schicht; Zwecke agent-kuratiert; Empfänger nur mit Artikel-Beleg; Fristen aus dem zitatverifizierten Fristen-Register. Die DSFA-Spalte ist ein BERECHNETER Vorschlag — entschieden wird von Menschen.',
    'Fehlende Pflichtinhalte stehen als «fehlt» — das ist der Arbeitsvorrat, kein Darstellungsfehler.')+`
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
    e.total++; e.cats[d.sensitive]=(e.cats[d.sensitive]||0)+1; if(d.no_basis)e.nb++;}));
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
function render(){
  renderSidebar();
  if(state.tab==='home') viewHome();
  else if(state.tab==='tree'||state.tab==='info'){state.tab='fields';state.sub='gesetze';viewFields();}
  else if(state.tab==='rules') viewRules();
  else if(state.tab==='guide') viewGuide();
  else if(state.tab==='register') viewRegister();
  else if(state.tab==='katalog') viewKatalog();
  else if(state.tab==='esh') viewEsh();
  else viewFields();
  writeHash();
}
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
