#!/usr/bin/env python3
"""Build dashboard.html from data_export.json (convention 9: generated, never edited).

The JSON is inlined into the HTML so the file opens straight from disk via file://
with no server and no fetch (offline by default). Vanilla JS, no framework.

Views:
  * left service filter
  * Abgleich (reconciliation) per service — 3 buckets, honest compliance summary
  * Gesetzes-Baum — list tree AND visual node-diagram (toggle), both collapsible
  * Geforderte Informationen — per-law required-data table

    python3 scripts/build_dashboard.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import EXPORT_PATH, DASHBOARD_PATH

TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kanton Schaffhausen — Compliance Databank</title>
<style>
  :root{
    --bg:#0b1220; --panel:#131c2e; --panel2:#0f1828; --bd:#27344a; --bd2:#1b2638;
    --tx:#e6edf6; --mut:#93a4bd; --mut2:#6b7d97;
    --federal:#818cf8; --cantonal:#2dd4bf; --communal:#fbbf24;
    --match:#22c55e; --proposed:#38bdf8; --gap:#f43f5e; --over:#f59e0b;
    --identity:#2dd4bf; --reason:#a78bfa; --mechanic:#64748b;
    --unver:#fb7185;
  }
  *{box-sizing:border-box}
  body{margin:0;font:13.5px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:var(--bg);color:var(--tx)}
  code,.mono{font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace;font-size:12px}
  header{padding:14px 20px;background:linear-gradient(180deg,#16213a,#0f1828);
         border-bottom:1px solid var(--bd);display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
  header h1{font-size:16px;margin:0;font-weight:650;letter-spacing:.2px}
  header .sub{color:var(--mut);font-size:12px}
  header .stamp{margin-left:auto;color:var(--mut2);font-size:11px;text-align:right}
  .warn{background:#3b1d1d;border:1px solid #7f1d1d;color:#fecaca;padding:6px 12px;
        border-radius:6px;font-size:12px}
  .layout{display:flex;min-height:calc(100vh - 56px)}
  aside{width:280px;flex:0 0 280px;background:var(--panel2);border-right:1px solid var(--bd);
        padding:16px;overflow:auto}
  aside h2{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--mut2);margin:18px 0 8px}
  aside h2:first-child{margin-top:0}
  .svc{padding:8px 10px;border-radius:7px;cursor:pointer;color:var(--mut);margin-bottom:3px;
       border:1px solid transparent;font-size:13px}
  .svc:hover{background:var(--panel);color:var(--tx)}
  .svc.active{background:#1b2a45;color:#fff;border-color:#2c4a73}
  .svc .meta{display:block;font-size:11px;color:var(--mut2)}
  .tab{display:block;width:100%;text-align:left;padding:9px 11px;border-radius:7px;cursor:pointer;
       background:none;border:1px solid transparent;color:var(--mut);font-size:13px;margin-bottom:3px}
  .tab:hover{background:var(--panel);color:var(--tx)}
  .tab.active{background:#10233a;color:#fff;border-color:#244067}
  main{flex:1;padding:22px 26px;overflow:auto;max-width:1300px}
  h3.view{font-size:15px;margin:0 0 4px}
  .hint{color:var(--mut);font-size:12px;margin:0 0 18px}
  .card{background:var(--panel);border:1px solid var(--bd);border-radius:10px;padding:16px 18px;margin-bottom:16px}
  .badge{display:inline-block;padding:1px 7px;border-radius:20px;font-size:10.5px;font-weight:600;
         vertical-align:middle;white-space:nowrap;border:1px solid transparent}
  .b-federal{color:var(--federal);border-color:var(--federal);background:#818cf81a}
  .b-cantonal{color:var(--cantonal);border-color:var(--cantonal);background:#2dd4bf1a}
  .b-communal{color:var(--communal);border-color:var(--communal);background:#fbbf241a}
  .b-match{color:var(--match);border-color:var(--match);background:#22c55e1a}
  .b-proposed{color:var(--proposed);border-color:var(--proposed);background:#38bdf81a}
  .b-legal_gap,.b-gap{color:var(--gap);border-color:var(--gap);background:#f43f5e1a}
  .b-overcollection,.b-over{color:var(--over);border-color:var(--over);background:#f59e0b1a}
  .b-mapped{color:var(--match);border-color:var(--match);background:#22c55e1a}
  .b-identity_part{color:var(--identity);border-color:var(--identity);background:#2dd4bf1a}
  .b-reason_facet{color:var(--reason);border-color:var(--reason);background:#a78bfa1a}
  .b-form_mechanic{color:var(--mechanic);border-color:var(--mechanic);background:#64748b22}
  .b-unver{color:var(--unver);border-color:var(--unver);background:#fb71851a}
  .b-sourced{color:#fcd34d;border-color:#b45309;background:#78350f55}
  .b-confirmed{color:var(--match);border-color:var(--match);background:#22c55e1a}
  .b-auto,.b-proposedm{color:var(--proposed);border-color:var(--proposed);background:#38bdf81a}
  table{border-collapse:collapse;width:100%;font-size:12.5px}
  th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--bd2);vertical-align:top}
  th{color:var(--mut2);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
  tr:hover td{background:#0f1a2c}
  .summary{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:6px}
  .gauge{font-size:30px;font-weight:700}
  .pill{padding:6px 12px;border-radius:8px;background:var(--panel2);border:1px solid var(--bd);min-width:96px}
  .pill .n{font-size:19px;font-weight:700;display:block}
  .pill .l{font-size:10.5px;color:var(--mut2);text-transform:uppercase;letter-spacing:.4px}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .colhead{font-size:12px;color:var(--mut2);text-transform:uppercase;letter-spacing:.6px;margin:0 0 8px}
  .item{border:1px solid var(--bd);border-left-width:3px;border-radius:7px;padding:9px 11px;margin-bottom:8px;background:var(--panel2)}
  .item.match{border-left-color:var(--match)}
  .item.proposed{border-left-color:var(--proposed)}
  .item.legal_gap{border-left-color:var(--gap)}
  .item.overcollection{border-left-color:var(--over)}
  .item .t{font-weight:600}
  .item .d{color:var(--mut);font-size:12px;margin-top:2px}
  .cite{color:var(--mut);font-size:11.5px;margin-top:4px}
  /* list tree */
  .tree{font-size:13px}
  .tnode{margin-left:18px;border-left:1px dashed var(--bd);padding-left:14px}
  .tline{padding:3px 0;cursor:default}
  .ttog{cursor:pointer;user-select:none;color:var(--mut);display:inline-block;width:14px}
  .collapsed > .tnode{display:none}
  /* diagram tree */
  .dg{padding:6px 0}
  .dgnode{margin:6px 0 6px 0}
  .dgbox{display:inline-block;border:1px solid var(--bd);border-left-width:4px;border-radius:8px;
         padding:6px 11px;background:var(--panel);cursor:pointer}
  .dgbox .ttl{font-weight:600}
  .dgbox .sub{color:var(--mut);font-size:11px}
  .dgchildren{margin-left:26px;border-left:2px solid var(--bd2);padding-left:18px;margin-top:2px}
  .dgnode.collapsed > .dgchildren{display:none}
  .muted{color:var(--mut)} .small{font-size:11.5px}
  .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:var(--mut);margin-top:8px}
  .legend span b{font-weight:600}
  .seg{display:inline-flex;border:1px solid var(--bd);border-radius:7px;overflow:hidden;margin-bottom:14px}
  .seg button{background:var(--panel2);border:none;color:var(--mut);padding:7px 14px;cursor:pointer;font-size:12.5px}
  .seg button.active{background:#10233a;color:#fff}
  .nores{color:var(--mut);padding:20px;text-align:center}
  /* department-grouped nav */
  .dept{margin-bottom:4px}
  .dephd{padding:7px 9px;border-radius:7px;cursor:pointer;color:var(--tx);font-weight:600;
         font-size:12.5px;display:flex;align-items:center;gap:6px;background:#10192b}
  .dephd:hover{background:#16223a}
  .dephd .tg{color:var(--mut2);width:10px;display:inline-block}
  .dephd .ct{margin-left:auto;font-weight:500;font-size:11px;color:var(--mut2)}
  .office{margin:2px 0 2px 8px}
  .offhd{padding:5px 8px;border-radius:6px;cursor:pointer;color:var(--mut);font-size:12px;
         display:flex;gap:6px}
  .offhd:hover{color:var(--tx)}
  .offhd .ct{margin-left:auto;font-size:10.5px;color:var(--mut2)}
  .dept.collapsed .office,.office.collapsed .svc{display:none}
  .svc{margin-left:14px}
  /* progress bar */
  .pbar{height:8px;border-radius:5px;background:var(--panel2);border:1px solid var(--bd);
        overflow:hidden;flex:1;min-width:140px;max-width:280px}
  .pbar > i{display:block;height:100%;background:var(--match)}
  /* field table */
  table.ft td{padding:6px 10px}
  table.ft tr.mech td{color:var(--mut2)}
  table.ft tr td:first-child{color:var(--mut2);width:30px;text-align:right}
  .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}
  .d-match{background:var(--match)}.d-proposed{background:var(--proposed)}
  .d-legal_gap{background:var(--gap)}.d-overcollection{background:var(--over)}
  .d-form_mechanic{background:var(--mechanic)}.d-identity_part{background:var(--identity)}
  .d-reason_facet{background:var(--reason)}.d-mapped{background:var(--match)}
  .srcbtn{color:var(--proposed);text-decoration:none;font-size:11.5px}
</style>
</head>
<body>
<header>
  <h1>Kanton Schaffhausen · Compliance Databank</h1>
  <span class="sub">Gesetz → Artikel → Anforderung ↔ Formular</span>
  <span class="warn" id="warn"></span>
  <span class="stamp" id="stamp"></span>
</header>
<div class="layout">
  <aside>
    <h2>Ansicht</h2>
    <button class="tab" data-tab="fields">Felder &amp; Rechtsgrundlagen</button>
    <button class="tab" data-tab="recon">Abgleich (3 Eimer)</button>
    <h2>Dienste nach Departement</h2>
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
    const e={form:fm.title,label:fl.label,section:fl.section,field_type:fl.field_type,
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
  document.getElementById('stamp').textContent = 'erzeugt '+ (DATA.generated_at||'') ;
  document.getElementById('warn').textContent = '⚠ Zitate „UNVERIFIED“ sind NICHT amtlich geprüft';
  const sv = document.getElementById('services'); sv.innerHTML='';
  const fb=el(`<input id="svcfilter" placeholder="Dienst/Amt suchen…" value="${esc(state.filter)}" `+
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
          `${esc(s.name.slice(0,46))}</div>`).join('')+`</div>`;
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
    <td><b>${esc(s.name.slice(0,52))}</b></td><td class="small muted">${esc(s.dienststelle||'')}</td>
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
      body+=`<tr data-sid="${s.id}" style="cursor:pointer"><td><b>${esc(s.name.slice(0,54))}</b></td>
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
function viewFields(){
  const m=document.getElementById('main');
  if(state.service==='all'){ m.innerHTML=deptOverview();
    m.querySelectorAll('tr[data-sid]').forEach(tr=>tr.onclick=()=>{state.service=tr.dataset.sid;render();}); return; }
  const s=svcById[state.service]; const forms=formsByService[s.id]||[];
  const g=grounding(s.id); const pct=g.need?Math.round(100*g.have/g.need):100;
  let h=`<h3 class="view">${esc(s.name)}</h3>
  <p class="hint">${esc(s.department||'')} · ${esc(s.dienststelle||'')} — je Zeile ein Formularfeld und seine Rechtsgrundlage.</p>
  <div class="card"><div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
    <div class="pbar" style="max-width:340px"><i style="width:${pct}%"></i></div>
    <span><b>${g.have}/${g.need}</b> Felder mit Rechtsgrundlage</span>
    ${forms[0]&&forms[0].source_file?`<a class="srcbtn" href="${esc(forms[0].source_file)}" style="margin-left:auto">↗ Quelldatei</a>`:''}</div>
  <table class="ft"><thead><tr><th>#</th><th>Feld</th><th>Abschnitt</th><th>Rechtsgrundlage</th><th>Klasse</th></tr></thead><tbody>`;
  let i=0;
  forms.forEach(fm=>(fm.fields||[]).forEach(fl=>{ i++; const mp=fl.mapping; const cls=mp?mp.classification:'—';
    const req=mp&&mp.requirement_id!=null?reqById[mp.requirement_id]:null; const basis=req?req.legal_basis:[];
    const cell = cls==='form_mechanic' ? '<span class="muted small">— keine nötig</span>'
      : cls==='overcollection' ? '<span class="badge b-over">Over-collection — ohne Grundlage</span>'
      : basis.length ? basis.map(citeStr).join('<br>')
      : '<span class="badge b-unver">zu ermitteln</span>';
    h+=`<tr class="${cls==='form_mechanic'?'mech':''}"><td>${i}</td>
      <td><b>${esc(fl.label)}</b></td><td class="small muted">${esc(fl.section||'')}</td>
      <td>${cell}</td><td><span class="dot d-${cls}"></span><span class="small">${esc(cls)}</span></td></tr>`;
  }));
  h+=`</tbody></table>${i?'':'<div class="nores">keine Felder extrahiert (gescanntes PDF / reine Erklärung)</div>'}</div>`;
  m.innerHTML=h;
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
// build law -> article -> requirement structure for current selection
function treeModel(){
  const sids = state.service==='all' ? DATA.services.map(s=>s.id) : [Number(state.service)];
  const laws={};
  sids.forEach(sid=>serviceReqs(sid).forEach(req=>{
    req.legal_basis.forEach(lb=>{
      const L=laws[lb.law_id]||(laws[lb.law_id]={id:lb.law_id,title:lb.law_title,short:lb.law_short,jur:lb.jurisdiction,sr:lb.sr_number,cref:lb.cantonal_ref,arts:{}});
      const A=L.arts[lb.article_id]||(L.arts[lb.article_id]={id:lb.article_id,no:lb.article_no,heading:lb.article_heading,lc:lb.last_checked,reqs:{}});
      A.reqs[req.requirement_id]={dp:req.data_point,status:req.status,type:req.data_type};
    });
  }));
  return Object.values(laws).map(L=>({...L,arts:Object.values(L.arts).map(A=>({...A,reqs:Object.values(A.reqs)}))}));
}
function viewTree(){
  const m=document.getElementById('main');
  if(state.service==='all'){ m.innerHTML=needService('Gesetzes-Baum · Gesetz → Artikel → Anforderung'); return; }
  const model=treeModel();
  let h=`<h3 class="view">Gesetzes-Baum · Gesetz → Artikel → Anforderung</h3>
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
function statusBadge(s){return `<span class="badge b-${s}">${({match:'Match',proposed:'Vorschlag',legal_gap:'Legal Gap'}[s]||s)}</span>`;}
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
  // gather rows grouped by law
  const byLaw={};
  sids.forEach(sid=>serviceReqs(sid).forEach(req=>{
    const cap=[...req.captured_by_confirmed.map(c=>({...c,st:'confirmed'})),...req.captured_by_proposed.map(c=>({...c,st:'proposed'}))];
    req.legal_basis.forEach(lb=>{
      (byLaw[lb.law_id]=byLaw[lb.law_id]||{lb,rows:[]}).rows.push({req,lb,cap});
    });
  }));
  const laws=Object.values(byLaw);
  if(!laws.length){m.innerHTML=h+'<div class="nores">Keine Daten für die Auswahl.</div>';return;}
  laws.forEach(({lb,rows})=>{
    h+=`<div class="card"><div style="margin-bottom:10px">${jur(lb.jurisdiction)} <b>${esc(lb.law_title)}</b> ${lb.sr_number?'<span class="mono small">SR '+esc(lb.sr_number)+'</span>':''}${unver(lb.last_checked)}</div>
      <table><thead><tr><th>Datenpunkt</th><th>Artikel</th><th>Typ</th><th>Bedingung</th><th>Erfasst durch (Formularfeld)</th></tr></thead><tbody>
      ${rows.map(({req,lb,cap})=>`<tr>
        <td><b>${esc(req.data_point)}</b><div class="small muted">${esc(req.label||'')}</div></td>
        <td class="mono small">${esc(artLabel(lb.article_no))}${lb.citation_detail?' '+esc(lb.citation_detail):''}${unver(lb.last_checked)}</td>
        <td class="small">${esc(req.data_type||'')}</td>
        <td class="small">${esc(req.condition||'—')}</td>
        <td>${cap.length?cap.map(c=>`“${esc(c.label)}” <span class="badge b-${c.st==='confirmed'?'confirmed':'proposedm'}">${c.st}</span>`).join('<br>'):'<span class="badge b-legal_gap">Legal Gap — kein Feld</span>'}</td>
      </tr>`).join('')}
      </tbody></table></div>`;
  });
  m.innerHTML=h;
}

function render(){
  renderSidebar();
  if(state.tab==='fields') viewFields();
  else if(state.tab==='recon') viewRecon();
  else if(state.tab==='tree') viewTree();
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
