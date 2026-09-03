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
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import EXPORT_PATH, DASHBOARD_PATH

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
    <h2>Ansicht</h2>
    <button class="tab" data-tab="fields">Felder &amp; Rechtsgrundlagen</button>
    <button class="tab" data-tab="tree">Gesetzes-Baum</button>
    <button class="tab" data-tab="info">Geforderte Informationen</button>
    <button class="tab" data-tab="rules">Datenhandhabung</button>
    <button class="tab" data-tab="esh">eSH-Katalog (Entwurf)</button>
    <h2>Formulare &amp; Dienste</h2>
    <div id="services"></div>
    <h2>Legende</h2>
    <div class="legend" id="legend"></div>
  </aside>
  <main id="main"></main>
</div>
<script id="data" type="application/json">/*DATA*/</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const state = {service:'all', tab:'fields', tree:'list', filter:'', open:{}};
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
// per-field grounding: how many fields that NEED a basis actually have one
function grounding(sid){
  let need=0, have=0;
  (formsByService[sid]||[]).forEach(fm=>(fm.fields||[]).forEach(fl=>{
    const m=fl.mapping; if(!m||!['mapped','identity_part','reason_facet'].includes(m.classification))return;
    need++; const r=m.requirement_id!=null?reqById[m.requirement_id]:null;
    if(r&&r.legal_basis&&r.legal_basis.length) have++;}));
  return {need,have};
}
const _recCache={};
function reconcile(sid){
  if(_recCache[sid]) return _recCache[sid];
  const reqIds=reqsByService[sid]||[], forms=formsByService[sid]||[];
  const cap={}, over=[], fieldView=[];
  forms.forEach(fm=>(fm.fields||[]).forEach(fl=>{
    const m=fl.mapping, cls=m?m.classification:null;
    const e={form:fm.title,label:fl.label,path:fl.path||fl.label,section:fl.section,field_type:fl.field_type,
             classification:cls,match_status:m?m.match_status:null,mapped_by:m?m.mapped_by:null,
             requirement_id:m?m.requirement_id:null};
    fieldView.push(e);
    if(!m) return;
    if(cls==='overcollection') over.push(e);
    else if(m.requirement_id!=null){const b=cap[m.requirement_id]=cap[m.requirement_id]||{confirmed:[],proposed:[]};
      (m.match_status==='confirmed'?b.confirmed:b.proposed).push(e);}
  }));
  const reqView=[]; let nMatch=0,nProp=0,nGap=0;
  reqIds.forEach(rid=>{const r=reqById[rid]; if(!r) return; const c=cap[rid]||{confirmed:[],proposed:[]};
    let st; if(c.confirmed.length){st='match';nMatch++;}else if(c.proposed.length){st='proposed';nProp++;}else{st='legal_gap';nGap++;}
    reqView.push(Object.assign({},r,{status:st,captured_by_confirmed:c.confirmed,captured_by_proposed:c.proposed}));});
  const total=reqIds.length;
  const res={requirements:reqView,fields:fieldView,overcollection_fields:over,
    summary:{requirements_total:total,matched:nMatch,proposed:nProp,legal_gaps:nGap,
      overcollection:over.length,compliance_pct:total?Math.round(100*nMatch/total):null,fields_total:fieldView.length}};
  _recCache[sid]=res; return res;
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
  if(/^Gesetze/.test(lc)) return ` <span class="badge b-sourced" title="aus offizieller SHR-PDF gelesen (scripts/extract_law.py); Live-Abgleich offen">Quelle ${esc(lc.replace('Gesetze-PDF ',''))}</span>`;
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
  const fb=el(`<input id="svcfilter" placeholder="Formular/Amt suchen…" value="${esc(state.filter)}" `+
    `style="width:100%;padding:7px 9px;margin-bottom:8px;background:var(--panel);border:1px solid var(--bd);`+
    `border-radius:7px;color:var(--tx);font-size:12.5px">`);
  sv.appendChild(fb);
  fb.oninput=()=>{state.filter=fb.value;renderNav();};
  const allr=el(`<div class="svc" style="margin-left:0;font-weight:600">▤ Alle Dienste · Übersicht <span class="meta">${DATA.services.length} Dienste, ${deptKeys().length} Departemente</span></div>`);
  if(state.service==='all') allr.classList.add('active');
  allr.onclick=()=>{state.service='all';render();};
  sv.appendChild(allr);
  const nav=el('<div id="nav"></div>'); sv.appendChild(nav); renderNav();
  document.querySelectorAll('.tab').forEach(b=>{
    b.classList.toggle('active', b.dataset.tab===state.tab);
    b.onclick=()=>{state.tab=b.dataset.tab;render();};
  });
  document.getElementById('legend').innerHTML = [
    ['b-match','Match (bestätigt)'],['b-proposed','Vorschlag'],['b-legal_gap','Legal Gap'],
    ['b-overcollection','Over-collection'],['b-identity_part','identity_part'],
    ['b-reason_facet','reason_facet'],['b-form_mechanic','form_mechanic'],
    ['b-federal','Bund'],['b-cantonal','Kanton'],['b-communal','Gemeinde']
  ].map(([c,l])=>`<span><span class="badge ${c}">&nbsp;</span> ${l}</span>`).join('');
}
function renderNav(){
  const f=state.filter.toLowerCase(); const nav=document.getElementById('nav'); if(!nav)return;
  let h='';
  deptKeys().forEach(d=>{
    const offices=deptTree[d];
    let svcMatch=0, deptHTML='';
    Object.keys(offices).sort().forEach(o=>{
      const svcs=offices[o].filter(s=>!f || (s.name+' '+o+' '+d).toLowerCase().includes(f));
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
  nav.querySelectorAll('.svc[data-sid]').forEach(e=>e.onclick=()=>{state.service=e.dataset.sid;render();});
}

// ---------- reconciliation ----------
function viewRecon(){
  const m=document.getElementById('main');
  if(state.service==='all'){ m.innerHTML=reconOverview();
    m.querySelectorAll('tr[data-sid]').forEach(tr=>tr.onclick=()=>{state.service=tr.dataset.sid;render();});
    return; }
  const s=svcById[state.service]; const r=reconcile(s.id);
  const sm=r.summary; const form=(formsByService[s.id]||[])[0];
  let h=`<h3 class="view">Abgleich · ${esc(s.name)}</h3>
  <p class="hint">${esc(s.dienststelle||'')} — drei Eimer: <b style="color:var(--match)">Match</b> · <b style="color:var(--gap)">Legal Gap</b> · <b style="color:var(--over)">Over-collection</b>. Vorschläge zählen NICHT als compliant.</p>
  <div class="card"><div class="summary">
    <div class="gauge" style="color:${sm.compliance_pct>=80?'var(--match)':sm.compliance_pct>=50?'var(--over)':'var(--gap)'}">${sm.compliance_pct==null?'–':sm.compliance_pct+'%'}</div>
    <div class="pill"><span class="n">${sm.matched}/${sm.requirements_total}</span><span class="l">Matched</span></div>
    <div class="pill"><span class="n" style="color:var(--proposed)">${sm.proposed}</span><span class="l">Vorschlag</span></div>
    <div class="pill"><span class="n" style="color:var(--gap)">${sm.legal_gaps}</span><span class="l">Legal Gap</span></div>
    <div class="pill"><span class="n" style="color:var(--over)">${sm.overcollection}</span><span class="l">Over-collect.</span></div>
   </div>`;
  if(form && form.title_content_mismatch)
    h+=`<div class="warn" style="display:block;margin:8px 0">⚠ Titel/Inhalt-Mismatch (conv 1): ${esc(form.mismatch_note||'')}</div>`;
  h+=`<div class="cols" style="margin-top:12px">
      <div><div class="colhead">⚖︎ Gesetz verlangt (${r.requirements.length})</div>${r.requirements.map(reqItem).join('')||'<div class="nores">—</div>'}</div>
      <div><div class="colhead">▦ Formular fragt${form?': '+esc(form.title):''} (${r.fields.length})</div>${r.fields.map(fieldItem).join('')||'<div class="nores">keine Felder extrahiert (evtl. flaches PDF)</div>'}</div>
     </div></div>`;
  m.innerHTML=h;
}
function reconOverview(){
  let rows=DATA.services.map(s=>({s,sm:reconcile(s.id).summary}))
    .sort((a,b)=>(b.sm.legal_gaps+b.sm.overcollection)-(a.sm.legal_gaps+a.sm.overcollection));
  const f=state.filter.toLowerCase();
  if(f) rows=rows.filter(x=>(x.s.name+' '+(x.s.dienststelle||'')+' '+(x.s.department||'')).toLowerCase().includes(f));
  return `<h3 class="view">Abgleich · Übersicht aller Dienste (${rows.length})</h3>
  <p class="hint">Auto-Entwürfe — Zeile anklicken für den Detail-Abgleich. Mappings sind <b>proposed</b>, Rechtsgrundlagen grösstenteils <b>UNVERIFIED</b> (juristisch zu prüfen). Sortiert nach Prüfbedarf (Gaps + Over-collection).</p>
  <div class="card"><table><thead><tr><th>Dienst</th><th>Amt</th><th>Anf.</th><th>Match</th><th>Vorschlag</th><th>Gap</th><th>Over</th><th>Felder</th></tr></thead><tbody>
  ${rows.map(({s,sm})=>`<tr data-sid="${s.id}" style="cursor:pointer">
    <td><b title="${esc(s.name)}">${esc(s.name)}</b></td><td class="small muted">${esc(s.dienststelle||'')}</td>
    <td>${sm.requirements_total}</td>
    <td style="color:var(--match)">${sm.matched}</td>
    <td style="color:var(--proposed)">${sm.proposed}</td>
    <td style="color:var(--gap)">${sm.legal_gaps||''}</td>
    <td style="color:var(--over)">${sm.overcollection||''}</td>
    <td class="small">${sm.fields_total}</td></tr>`).join('')}
  </tbody></table></div>`;
}
// ---------- PRIMARY: fields & legal basis ----------
function deptOverview(){
  const f=state.filter.toLowerCase();
  let h=`<h3 class="view">Übersicht nach Departement</h3>
  <p class="hint">Auto-Entwürfe — je Formularfeld eine Anforderung; Rechtsgrundlage meist noch zu ermitteln. Dienst anklicken. Balken = Anteil Felder mit eingetragener Rechtsgrundlage.</p>`;
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
      <div class="pbar"><i style="width:${dpct}%"></i></div><span class="small muted">${dh}/${dn} Felder mit Grundlage</span></div>
      <table class="ft"><thead><tr><th>Dienst (Formular)</th><th>Amt</th><th>Felder</th><th>Rechtsgrundlagen</th></tr></thead><tbody>${body}</tbody></table></div>`;
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
        if(ck.status==='aktuell')return`<span class="fcheck ok" title="online geprüft ${esc(ck.d||'')} (${esc(ck.quelle||'')}) — unsere Kopie ist die aktuelle Fassung">✓ aktuell</span>`;
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
          ${d.sensitive?`<span class="badge b-sens" title="besonders schützenswerte Personendaten (Art. 5 lit. c DSG)">⛨ ${esc(SENS[d.sensitive]||d.sensitive)}</span>`:''}
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
                 :citeStr(b)).join('<br>'):(d.no_basis?'<span class="badge b-over">Over-collection — keine gesetzliche Grundlage</span>':'<span class="badge b-unver">Rechtsgrundlage zu ermitteln</span>')}</div></div>`;
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
  let i=0;
  forms.forEach(fm=>(fm.fields||[]).forEach(fl=>{ i++; const mp=fl.mapping; const cls=mp?mp.classification:'—';
    const req=mp&&mp.requirement_id!=null?reqById[mp.requirement_id]:null; const basis=req?req.legal_basis:[];
    const cell = cls==='form_mechanic' ? '<span class="muted small">— keine nötig</span>'
      : cls==='overcollection' ? '<span class="badge b-over">Over-collection — ohne Grundlage</span>'
      : basis.length ? basis.map(citeStr).join('<br>')
      : '<span class="badge b-unver">zu ermitteln</span>';
    h+=`<tr class="${cls==='form_mechanic'?'mech':''}"><td>${i}</td>
      <td>${fmtPath(fl.path||fl.label)}</td>
      <td>${cell}</td><td><span class="dot d-${cls}"></span><span class="small">${esc(cls)}</span></td></tr>`;
  }));
  h+=`</tbody></table>${i?'':'<div class="nores">keine Felder extrahiert (gescanntes PDF / reine Erklärung)</div>'}</div>`;
  return h;
}
function viewFields(){
  const m=document.getElementById('main');
  if(state.service==='all'){ m.innerHTML=deptOverview();
    m.querySelectorAll('tr[data-sid]').forEach(tr=>tr.onclick=()=>{state.service=tr.dataset.sid;render();}); return; }
  const s=svcById[state.service]; const forms=formsByService[s.id]||[];
  const withDF=forms.filter(fm=>(fm.data_fields||[]).length);
  const rest=forms.filter(fm=>!(fm.data_fields||[]).length);
  let h=`<h3 class="view">${esc(s.name)}</h3>
  <p class="hint">${esc(s.department||'')} · ${esc(s.dienststelle||'')} — ${withDF.length?'die Datenfelder dieses Formulars: Typ, Definition, zulässige Werte und Herkunft.':'je Zeile ein Formularfeld und seine Rechtsgrundlage.'}</p>`;
  h+=formLinks(s,forms);
  if(!s.in_dvsh) h+=`<div class="card nodvbox"><span class="badge b-nodv">◇ Nicht im DVSH-Modell</span>
    <span class="muted small">Dieser Dienst ist in unserem Formular-Katalog erfasst, aber (noch) nicht in der amtlichen DVSH-Modellierung enthalten. Die Rechtsgrundlagen unten stammen aus unserer eigenen, quellenbelegten Analyse.</span></div>`;
  if(s.dvsh) h+=dvshPanel(s.dvsh);
  if(withDF.length) h+=viewDataFields(withDF);
  if(rest.length) h+=widgetTable(s,rest);
  h+=handlingPanel(s,forms);
  m.innerHTML=h;
}
function formLinks(s,forms){
  const f=forms.filter(x=>x.source_file);
  const dv=s.dvsh||{};
  const online=(dv.abgabe||[]).filter(x=>x&&!/^↗|^PDF-Formular$|^Online-Formular$/.test(x));
  const ext=(dv.externe_links||[]);
  if(!f.length && !online.length && !ext.length) return '';
  const btn=(href,label,cls)=>`<a class="flink ${cls||''}" href="${esc(href)}" target="_blank" rel="noreferrer">${esc(label)}</a>`;
  let parts=f.map(x=>btn(x.source_file, '📄 '+(x.source_file.split('/').pop()||'Formular'), 'primary'));
  if(dv.slug) parts.push(btn('https://sh.ch/', '🌐 Amtliche Seite (sh.ch)',''));
  return `<div class="card flinks"><span class="flabel">Formular</span>${parts.join('')}
    ${online.length?`<span class="muted small">· Abgabe: ${esc(online.join(' · '))}</span>`:''}</div>`;
}
function dvshPanel(d){
  const kant=(d.recht_kantonal||[]), bund=(d.recht_bund||[]);
  const law=(t,n,url)=>`<div class="dvl">${esc(t)}${n?` <a class="ssr" href="${url}" target="_blank" rel="noreferrer">${esc(n)}</a>`:''}</div>`;
  const meta=[['Vollzug',d.dienststelle],['Bearbeitungsdauer',d.bearbeitungsdauer],
              ['Fristen',d.fristen],['Gebühren',d.gebuehren]]
    .filter(x=>x[1]&&String(x[1]).trim()&&String(x[1]).trim()!=='leer')
    .map(x=>`<div class="dvm"><span class="dvk">${x[0]}</span> ${esc(String(x[1]))}</div>`).join('');
  return `<div class="card dvsh">
    <div class="dvhdr"><span class="badge b-dvsh">DVSH-Modell</span>
      <b>${esc(d.title||'')}</b><span class="muted small">· amtliche Modellierung${d.version?' '+esc(d.version):''}</span></div>
    ${d.kurzbeschreibung?`<div class="dvdesc">${esc(d.kurzbeschreibung)}</div>`:''}
    <div class="dvgrid">
      <div><div class="dvsub">Rechtsgrundlagen — kantonal</div>
        ${kant.length?kant.map(l=>law(l.titel,l.ssr,l.ssr?`https://rechtsbuch.sh.ch/app/de/texts_of_law/${l.ssr}`:'#')).join(''):'<div class="muted small">keine im Modell</div>'}
      </div>
      <div><div class="dvsub">Rechtsgrundlagen — Bund</div>
        ${bund.length?bund.map(l=>law(l.titel,l.sr,l.sr?`https://www.fedlex.admin.ch/eli/cc/${esc(l.sr)}`:'#')).join(''):'<div class="muted small">keine im Modell</div>'}
      </div>
    </div>
    ${meta?`<div class="dvmeta">${meta}</div>`:''}
  </div>`;
}
function reqItem(r){
  const cap=[...r.captured_by_confirmed,...r.captured_by_proposed];
  return `<div class="item ${r.status}">
    <div class="t">${esc(r.data_point)} <span class="badge b-${r.status}">${({match:'Match',proposed:'Vorschlag',legal_gap:'Legal Gap'}[r.status])}</span>${r.is_composite?' <span class="badge b-identity_part">zusammengesetzt</span>':''}</div>
    <div class="d">${esc(r.label||'')}${r.condition?' · Bedingung: <i>'+esc(r.condition)+'</i>':''} · Typ: ${esc(r.data_type||'?')}</div>
    <div class="cite">${r.legal_basis.map(citeStr).join('<br>')||'<span class="badge b-unver">Rechtsgrundlage zu ermitteln</span>'}</div>
    <div class="d">${r.status==='legal_gap'?'<span style="color:var(--gap)">✗ von keinem Formularfeld erfasst</span>'
        :'erfasst durch: '+cap.map(c=>`“${esc(c.label)}” <span class="badge b-${c.match_status==='confirmed'?'confirmed':'proposedm'}">${c.match_status}</span>`).join(', ')}</div>
  </div>`;
}
function fieldItem(f){
  const cl=f.classification||'—';
  return `<div class="item ${cl==='overcollection'?'overcollection':(f.requirement_id?'match':'')}">
    <div class="t">${esc(f.label)} <span class="badge b-${cl}">${cl}</span>${f.match_status?` <span class="badge b-${f.match_status==='confirmed'?'confirmed':'proposedm'}">${f.match_status}/${f.mapped_by}</span>`:''}</div>
    <div class="d">${esc(f.section||'')} · ${esc(f.field_type||'')}${cl==='overcollection'?' · <span style="color:var(--over)">⚠ keine Rechtsgrundlage (DSG-Risiko)</span>':''}${cl==='form_mechanic'?' · <span class="muted">Formular-Mechanik, keine Anforderung</span>':''}</div>
  </div>`;
}

// ---------- tree (list + diagram) ----------
function serviceReqs(sid){ return reconcile(sid).requirements; }
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
function viewTree(){
  const m=document.getElementById('main');
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
function viewInfo(){
  const m=document.getElementById('main');
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

// ---------- Datenhandhabung (how data may be stored, treated, communicated) ----------
const ASPECT={erhebung:'Erhebung',bearbeitung:'Bearbeitung',speicherung:'Speicherung',
  sicherheit:'Datensicherheit',aufbewahrung:'Aufbewahrung',bekanntgabe:'Bekanntgabe',
  betroffenenrechte:'Rechte der Betroffenen',archivierung:'Archivierung',loeschung:'Löschung'};
const ASPECT_ORDER=Object.keys(ASPECT);
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
  // the laws this service's data actually rests on, and the sensitive kinds it holds
  const lawIds=new Set(), cats=new Set();
  forms.forEach(fm=>(fm.data_fields||[]).forEach(d=>{
    (d.legal_basis||[]).forEach(b=>{if(b.law_id!=null)lawIds.add(b.law_id);});
    if(d.sensitive) cats.add(d.sensitive);
  }));
  const sekt=H.filter(r=>r.scope==='sektoral'&&lawIds.has(r.law_id));
  const sens=cats.size?H.filter(r=>r.scope==='besonders_schuetzenswert'&&(!r.sensitive_category||cats.has(r.sensitive_category))):[];
  const allg=H.filter(r=>r.scope==='allgemein');
  let h=`<div class="card"><div class="dfhdr"><b>Datenhandhabung</b>
    <span class="muted small">— was das Recht über Speicherung, Bearbeitung und Bekanntgabe dieser Daten sagt</span></div>`;
  if(sekt.length) h+=`<div class="hgrp"><div class="dvsub">Sektorale Spezialnormen — aus den Gesetzen dieses Formulars</div>${rulesByAspect(sekt)}</div>`;
  if(sens.length) h+=`<div class="hgrp"><div class="dvsub">⛨ Besonders schützenswerte Personendaten (${[...cats].map(esc).join(', ')})</div>${rulesByAspect(sens)}</div>`;
  if(allg.length) h+=`<details class="hgen"><summary class="dvsub" style="cursor:pointer">Allgemeine Regeln KDSG/DSG — gelten für alle Personendaten (${allg.length})</summary>${rulesByAspect(allg)}</details>`;
  return h+`</div>`;
}
function viewRules(){
  const m=document.getElementById('main');
  const H=DATA.datenhandhabung||[];
  let h=`<h3 class="view">Datenhandhabung · Speicherung, Bearbeitung, Bekanntgabe</h3>
  <p class="hint">Aus den amtlichen Gesetzestexten extrahierte Regeln, wie Personendaten behandelt werden müssen —
  jede Regel mit wörtlichem, gegen das Gesetzes-PDF geprüftem Zitat. «Allgemein» gilt für alle Personendaten,
  «besonders schützenswert» zusätzlich für ⛨-Felder, «sektoral» nur für Formulare, die sich auf das jeweilige Gesetz stützen.</p>`;
  if(!H.length){m.innerHTML=h+'<div class="nores">Noch keine Regeln geladen (scripts/load_data_rules.py).</div>';return;}
  const grp=[['allgemein','Allgemeine Regeln — für alle Personendaten'],
             ['besonders_schuetzenswert','Besonders schützenswerte Personendaten'],
             ['sektoral','Sektorale Spezialnormen — je Fachgesetz']];
  grp.forEach(([scope,label])=>{
    const list=H.filter(r=>r.scope===scope); if(!list.length) return;
    // one card per law inside the scope, so the source is always visible
    const byLaw={};
    list.forEach(r=>{(byLaw[r.law_id]=byLaw[r.law_id]||[]).push(r);});
    h+=`<h4 class="hscope">${esc(label)} <span class="muted small">· ${list.length} Regeln</span></h4>`;
    Object.values(byLaw).forEach(rs=>{
      const r0=rs[0];
      h+=`<div class="card"><div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
        <b>${esc(r0.short_title||r0.law_title)}</b>
        <span class="muted small">${esc(r0.law_title!==r0.short_title?r0.law_title:'')}</span>
        <span class="muted small" style="margin-left:auto">${jur(r0.jurisdiction_level)} ${r0.sr_number?(r0.jurisdiction_level==='federal'?'SR ':'SHR ')+esc(r0.sr_number):''} · ${rs.length} Regeln</span></div>
        ${rulesByAspect(rs)}</div>`;
    });
  });
  m.innerHTML=h;
}
function viewEsh(){
  const m=document.getElementById('main');
  const kat=DATA.esh_katalog||[];
  let h=`<h3 class="view">eSH-Katalog · E-Schaffhausen-Standard (ENTWURF)</h3>
  <p class="hint">Vorschlag für einen kantonalen Datenstandard, der alles abdeckt, was die eCH-Familie nicht abdeckt
  (${kat.reduce((n,k)=>n+(k.n_felder||0),0)} Datenpunkte ohne eCH-Standard). Abgeleitet aus den realen Formularfeldern der Verwaltung —
  <b>nicht offiziell</b>, zur Weiterentwicklung durch den Kanton.</p>`;
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
  if(state.tab==='tree') viewTree();
  else if(state.tab==='info') viewInfo();
  else if(state.tab==='rules') viewRules();
  else if(state.tab==='esh') viewEsh();
  else viewFields();
}
render();
</script>
</body>
</html>
"""


def main():
    with open(EXPORT_PATH, encoding="utf-8") as fh:
        data = fh.read()
    # inline as JSON text inside a <script type=application/json> (escape </ to be safe)
    safe = data.replace("</", "<\\/")
    html = TEMPLATE.replace("/*DATA*/", safe)
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote {DASHBOARD_PATH}  ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
