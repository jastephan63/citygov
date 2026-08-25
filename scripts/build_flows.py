#!/usr/bin/env python3
"""Build flows.html — the guided-flow dashboard (TurboTax principle), separate
from dashboard.html (the compliance view, which stays untouched).

The design and player follow the three hand-built prototypes in
../formflows/prototype-*.html, which are the formatting reference: paper theme,
gold crest topbar, thin progress bar with section name, "Frage N" eyebrow, help
drawer with per-node prose, radio-card choices with [value, label, sub], scan
drop zones, roster chips, autocomplete over canonical Swiss geo data (inlined
from ../formflows/data/ch-geo.js), and a review screen that mimics the official
form (formdoc) with checklist highlights and a Behörden-Ansicht toggle that
reveals the machine field names.

Self-contained: flow JSON + geo data inlined, opens via file://.

    python3 scripts/build_flows.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect

OUT = os.path.join(ROOT, "flows.html")
GEO = os.path.join(os.path.dirname(ROOT), "formflows", "data", "ch-geo.js")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Geführte Formulare — Kanton Schaffhausen</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tabler-icons/2.47.0/iconfont/tabler-icons.min.css">
<style>
:root{
--paper:#FAFAF6;--card:#FFFFFF;--ink:#16150F;--ink-soft:#5C594D;--ink-faint:#8C897C;
--line:#E4E1D6;--line-soft:#EEEBE1;--gold:#F2B705;--gold-deep:#C98E00;--field:#F4F1E7;
--good:#2E7D5B;--good-bg:#E7F2EC;--flag:#C0392B;--flag-bg:#FBEDEB;--radius:14px;--maxw:680px;
}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:'Inter',system-ui,-apple-system,sans-serif;line-height:1.5;-webkit-font-smoothing:antialiased}
.mono{font-family:'Roboto Mono',ui-monospace,monospace}
.topbar{border-bottom:1px solid var(--line);background:var(--card)}
.topbar-inner{max-width:var(--maxw);margin:0 auto;padding:14px 22px;display:flex;align-items:center;gap:12px}
.crest{width:26px;height:30px;flex:none;border-radius:3px;background:var(--gold);position:relative;overflow:hidden;box-shadow:inset 0 0 0 1px rgba(0,0,0,.12)}
.crest::after{content:"";position:absolute;left:50%;top:52%;transform:translate(-50%,-50%);width:14px;height:11px;background:var(--ink);clip-path:polygon(50% 0,100% 38%,82% 100%,18% 100%,0 38%);opacity:.85}
.topbar h1{font-size:14px;margin:0;font-weight:600;letter-spacing:.2px}
.topbar .sub{font-size:11.5px;color:var(--ink-faint);font-weight:500;letter-spacing:.3px;text-transform:uppercase}
.proto-tag{margin-left:auto;font-size:10.5px;font-weight:600;letter-spacing:.6px;text-transform:uppercase;color:var(--gold-deep);border:1px solid var(--gold);border-radius:99px;padding:3px 9px;white-space:nowrap}
.allbtn{margin-left:auto;background:none;border:1px solid var(--line);border-radius:8px;color:var(--ink-soft);font:inherit;font-size:12.5px;font-weight:600;padding:6px 12px;cursor:pointer;white-space:nowrap}
.allbtn:hover{border-color:var(--gold-deep);color:var(--ink)}
.progress-wrap{max-width:var(--maxw);margin:0 auto;padding:0 22px}
.progress{height:4px;background:var(--line-soft);border-radius:99px;margin-top:18px;overflow:hidden}
.progress span{display:block;height:100%;background:var(--gold);width:0;border-radius:99px;transition:width .35s cubic-bezier(.2,.7,.3,1)}
.stepmeta{display:flex;justify-content:space-between;margin-top:8px;font-size:12px;color:var(--ink-faint);font-weight:500}
.stage{max-width:var(--maxw);margin:0 auto;padding:30px 22px 80px}
.screen{animation:rise .32s cubic-bezier(.2,.7,.3,1)}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.screen{animation:none}.progress span{transition:none}}
.eyebrow{font-size:12px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--gold-deep);margin-bottom:10px}
h2.q{font-size:27px;line-height:1.18;letter-spacing:-.4px;margin:0 0 8px;font-weight:700}
.hint{font-size:15px;color:var(--ink-soft);margin:0 0 22px;max-width:52ch}
.field-row{display:flex;gap:14px;flex-wrap:wrap}.field-row>.fc{flex:1 1 200px}.fc{margin-bottom:16px}
label.lbl{display:block;font-size:13.5px;font-weight:600;margin-bottom:7px}
input[type=text],input[type=date],input[type=number],select,textarea{width:100%;font:inherit;font-size:16px;padding:13px 14px;border:1.5px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);transition:border-color .15s,box-shadow .15s}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--gold-deep);box-shadow:0 0 0 3px rgba(242,183,5,.28)}
.choices{display:flex;flex-direction:column;gap:10px}
.choice{display:flex;align-items:center;gap:13px;padding:15px 16px;border:1.5px solid var(--line);border-radius:12px;cursor:pointer;background:var(--card);transition:border-color .15s,background .15s;font-size:16px;font-weight:500}
.choice:hover{border-color:var(--gold-deep)}
.choice .dot{width:20px;height:20px;border-radius:99px;border:2px solid var(--ink-faint);flex:none;position:relative;transition:border-color .15s}
.choice.sel{border-color:var(--ink);background:#FCFAF2}.choice.sel .dot{border-color:var(--ink)}
.choice.sel .dot::after{content:"";position:absolute;inset:3px;border-radius:99px;background:var(--gold-deep)}
.choice .sub{display:block;font-size:12.5px;color:var(--ink-faint);font-weight:500;margin-top:2px}
.choice.multi .dot{border-radius:5px}.choice.multi.sel .dot::after{border-radius:2px}
.scan-drop{border:1.5px dashed var(--gold-deep);border-radius:12px;padding:28px;text-align:center;color:var(--ink-soft);background:var(--field)}
.scan-drop .ic{font-size:30px;color:var(--gold-deep)}
.roster-card{border:1.5px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.chip{display:flex;justify-content:space-between;align-items:center;background:var(--field);border-radius:10px;padding:10px 13px;margin:7px 0;font-size:14.5px;font-weight:500}
.chip button{background:none;border:none;color:var(--ink-faint);cursor:pointer;font-size:16px}
.ac{position:relative}
.ac-list{position:absolute;left:0;right:0;top:calc(100% + 4px);z-index:30;background:var(--card);border:1.5px solid var(--line);border-radius:10px;max-height:230px;overflow:auto;box-shadow:0 8px 20px rgba(0,0,0,.10);display:none}
.ac-list.open{display:block}
.ac-item{padding:10px 13px;cursor:pointer;font-size:15px;display:flex;justify-content:space-between;gap:10px;align-items:center}
.ac-item:hover{background:var(--field)}
.ac-item .code{color:var(--ink-faint);font-size:11.5px;font-family:'Roboto Mono',monospace}
.ac-empty{padding:10px 13px;color:var(--ink-faint);font-size:13.5px}
.nav{display:flex;gap:12px;align-items:center;margin-top:30px}
.btn{font:inherit;font-size:15px;font-weight:600;border-radius:10px;padding:13px 24px;cursor:pointer;border:1.5px solid transparent;transition:transform .08s,background .15s,border-color .15s}
.btn:active{transform:translateY(1px)}.btn-primary{background:var(--ink);color:#fff}.btn-primary:hover{background:#000}
.btn-ghost{background:transparent;color:var(--ink-soft);border-color:var(--line);padding:13px 18px}.btn-ghost:hover{border-color:var(--ink-faint);color:var(--ink)}
.btn-link{background:none;border:none;color:var(--gold-deep);font-weight:600;cursor:pointer;font-size:13.5px;padding:4px 2px}
.nav .spacer{flex:1}.err{color:var(--flag);font-size:13px;font-weight:600;margin-top:10px;min-height:18px}
.whylink{background:none;border:none;color:var(--gold-deep);font-weight:600;cursor:pointer;font-size:13.5px;padding:0;margin:-8px 0 20px;display:inline-flex;align-items:center;gap:6px}
.whylink:hover{text-decoration:underline}
.note-box{font-size:13.5px;color:var(--ink-soft);background:var(--field);border-left:3px solid var(--gold);padding:11px 14px;border-radius:0 8px 8px 0;margin:0 0 22px;max-width:60ch;white-space:pre-wrap}
.rev-head{display:flex;align-items:flex-start;gap:14px;margin-bottom:6px}
.rev-head .check{flex:none;width:40px;height:40px;border-radius:99px;background:var(--good-bg);display:grid;place-items:center;color:var(--good);font-size:20px;font-weight:700}
h2.rev-title{font-size:24px;letter-spacing:-.3px;margin:0;font-weight:700}
.rev-sub{font-size:14.5px;color:var(--ink-soft);margin:6px 0 18px;max-width:52ch}
.checklist{background:var(--flag-bg);border:1px solid #EAC7C2;border-radius:12px;padding:13px 16px;margin-bottom:18px}
.checklist .ttl{font-size:12.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--flag);font-weight:700}
.checklist div{font-size:13.5px;color:var(--ink-soft);margin-top:5px}
.formdoc{border:1px solid var(--line);border-radius:var(--radius);background:var(--card);overflow:hidden}
.formdoc-top{padding:18px 20px;border-bottom:2px solid var(--ink);display:flex;align-items:center;gap:12px}
.formdoc-top .crest{width:22px;height:25px}
.formdoc-top .t{font-size:13px;font-weight:700;letter-spacing:.2px}
.formdoc-top .t span{display:block;font-size:11px;font-weight:500;color:var(--ink-faint);letter-spacing:.4px;text-transform:uppercase}
.formdoc-top .formnr{margin-left:auto;font-size:11px;color:var(--ink-faint)}
.grp{border-top:1px solid var(--line-soft)}.grp:first-of-type{border-top:none}
.grp-h{font-size:11.5px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint);padding:14px 20px 4px}
.rowf{display:flex;align-items:flex-start;gap:12px;padding:9px 20px 13px}.rowf:last-child{padding-bottom:16px}
.rowf .meta{flex:1;min-width:0}
.rowf .flabel{font-size:12px;color:var(--ink-faint);font-weight:500;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rowf .machine{display:none;font-size:10.5px;color:var(--gold-deep);background:var(--field);padding:1px 6px;border-radius:4px}
body.behoerden .rowf .machine{display:inline-block}
.rowf .fval{font-size:16px;font-weight:600;margin-top:3px;word-break:break-word;white-space:pre-wrap}
.rowf .src{font-size:11.5px;color:var(--ink-faint);margin-top:3px;font-style:italic}
.rowf .edit{flex:none;align-self:center;font-size:12.5px;color:var(--gold-deep);font-weight:600;background:none;border:1px solid var(--line);border-radius:8px;padding:6px 11px;cursor:pointer}
.rowf .edit:hover{border-color:var(--gold-deep)}
.toolbar{display:flex;align-items:center;gap:14px;margin:18px 2px 4px;flex-wrap:wrap}
.toggle{display:inline-flex;align-items:center;gap:9px;font-size:13px;font-weight:600;color:var(--ink-soft);cursor:pointer;user-select:none}
.switch{width:38px;height:22px;border-radius:99px;background:var(--line);position:relative;transition:background .18s;flex:none}
.switch::after{content:"";position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:99px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.25);transition:left .18s}
body.behoerden .switch{background:var(--gold-deep)}body.behoerden .switch::after{left:18px}
.toolbar .note{font-size:12.5px;color:var(--ink-faint)}
.submit-row{margin-top:24px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.done-msg{margin-top:18px;background:var(--good-bg);border:1px solid #BFE0CE;color:var(--good);border-radius:12px;padding:16px 18px;font-size:14.5px;font-weight:500;display:none}
.done-msg.show{display:block}
.restart{margin-top:36px;text-align:center}
.help-tab{position:fixed;right:0;top:50%;transform:translateY(-50%);z-index:60;background:var(--gold);color:var(--ink);border:none;border-radius:12px 0 0 12px;padding:14px 9px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:7px;box-shadow:-2px 2px 12px rgba(0,0,0,.14)}
.help-tab i{font-size:20px}
.help-tab .label{writing-mode:vertical-rl;transform:rotate(180deg);font-size:12px;font-weight:600;letter-spacing:.4px}
.help-tab .dot{position:absolute;top:7px;right:7px;width:9px;height:9px;border-radius:50%;background:var(--flag);display:none}
.help-tab.has-why .dot{display:block}
.help-overlay{position:fixed;inset:0;background:rgba(0,0,0,.28);opacity:0;visibility:hidden;transition:opacity .25s;z-index:65}
.help-overlay.open{opacity:1;visibility:visible}
.help-drawer{position:fixed;top:0;right:0;height:100%;width:370px;max-width:88vw;background:var(--card);border-left:1px solid var(--line);box-shadow:-8px 0 30px rgba(0,0,0,.14);transform:translateX(100%);transition:transform .28s cubic-bezier(.2,.7,.3,1);z-index:70;display:flex;flex-direction:column}
.help-drawer.open{transform:translateX(0)}
.help-head{display:flex;align-items:center;gap:10px;padding:18px 20px;border-bottom:1px solid var(--line)}
.help-head i{font-size:22px;color:var(--gold-deep)}
.help-head h3{margin:0;font-size:16px;font-weight:600}
.help-head .x{margin-left:auto;background:none;border:none;cursor:pointer;color:var(--ink-soft);font-size:22px;line-height:1;display:flex}
.help-body{padding:18px 20px;overflow:auto;flex:1}
.help-q{font-size:15px;font-weight:600;margin-bottom:16px;line-height:1.35}
.help-sec{margin-bottom:18px}
.help-h{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--gold-deep);display:flex;align-items:center;gap:7px;margin-bottom:6px}
.help-p{font-size:14px;color:var(--ink-soft);margin:0;line-height:1.6}
.help-foot{padding:14px 20px;border-top:1px solid var(--line);font-size:12.5px;color:var(--ink-faint);display:flex;gap:8px;align-items:flex-start}
.help-foot i{font-size:16px;color:var(--good)}
.fwchip{display:flex;gap:8px;align-items:flex-start;background:#F3EFDF;border:1px solid var(--line);color:var(--ink-soft);
  font-size:13px;font-weight:500;border-radius:9px;padding:9px 12px;margin:-6px 0 16px;max-width:56ch}
.fwchip i{color:var(--gold-deep);font-size:16px;flex:none}
.snote{display:flex;gap:8px;align-items:flex-start;background:#EFEAF6;border:1px solid #D8CCEC;color:#4C3575;
  font-size:13px;font-weight:500;border-radius:9px;padding:9px 12px;margin:-6px 0 16px;max-width:56ch}
.snote i{font-size:16px;flex:none}
.next-steps{margin-top:18px;border:1px solid var(--line);border-radius:12px;background:var(--card);padding:16px 18px;display:none}
.next-steps.show{display:block}
.next-steps .ttl{font-size:12.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--gold-deep);font-weight:700;margin-bottom:8px}
.next-steps ol{margin:0 0 8px;padding-left:20px;font-size:14px;color:var(--ink-soft)}
.next-steps ol li{margin-bottom:5px}
.next-steps .kontakt{font-size:12.5px;color:var(--ink-faint);border-top:1px solid var(--line-soft);padding-top:8px;margin-top:6px}
.stale{display:inline-flex;gap:6px;align-items:center;background:var(--flag-bg);color:var(--flag);border:1px solid #EAC7C2;
  font-size:11.5px;font-weight:600;border-radius:8px;padding:3px 9px;margin-left:8px;vertical-align:middle}
.fchip{display:inline-block;font-size:10.5px;font-weight:600;border-radius:6px;padding:1px 7px;margin-left:5px;vertical-align:middle}
.fchip.frei{background:#F3EFDF;color:var(--gold-deep);border:1px solid var(--line)}
.fchip.sens{background:#EFEAF6;color:#4C3575;border:1px solid #D8CCEC}
/* layout: sidebar + main */
.layout{display:flex;min-height:calc(100vh - 55px)}
aside{width:290px;flex:0 0 290px;background:var(--card);border-right:1px solid var(--line);
  padding:18px 16px;overflow:auto;max-height:calc(100vh - 55px);position:sticky;top:0}
body.playing #side{display:none}   /* only the form sidebar, NOT the help drawer (also an <aside>) */
body.playing .topbar-inner,body.playing .progress-wrap{max-width:var(--maxw)}
.topbar-inner{max-width:1100px}
aside .dep{font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint);margin:18px 0 7px}
aside .dep:first-of-type{margin-top:14px}
.sv{padding:8px 11px;border-radius:9px;cursor:pointer;color:var(--ink-soft);margin-bottom:2px;font-size:13.5px;font-weight:500;border:1.5px solid transparent}
.sv:hover{background:var(--field);color:var(--ink)}
.sv.active{border-color:var(--gold-deep);background:#FCFAF2;color:var(--ink)}
.sv .m{display:block;font-size:11px;color:var(--ink-faint);font-weight:500}
main.stage{flex:1;max-width:none;padding:30px 34px 80px}
body.playing main.stage{max-width:var(--maxw);margin:0 auto;padding:30px 22px 80px}
.detail{max-width:860px}
.dhead{display:flex;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:6px}
.dhead h2{font-size:26px;letter-spacing:-.4px;margin:0;font-weight:700}
.dhead .try{margin-left:auto}
.dfl{border:1px solid var(--line);border-radius:var(--radius);background:var(--card);overflow:hidden;margin-top:18px}
.dfl-h{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:14px;padding:11px 18px;
  font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint);border-bottom:2px solid var(--ink)}
.dfr{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:14px;padding:13px 18px;border-top:1px solid var(--line-soft)}
.dfr:first-of-type{border-top:none}
.dfr .fn{font-size:14.5px;font-weight:600}
.dfr .fdef{font-size:12px;color:var(--ink-faint);margin-top:2px}
.dfr.aus{opacity:.55}
.echb{display:inline-flex;align-items:center;gap:4px;font-size:10.5px;font-weight:600;font-family:'Roboto Mono',monospace;
  background:var(--field);color:var(--gold-deep);border:1px solid var(--line);border-radius:6px;padding:2px 7px;
  text-decoration:none;margin-top:5px;margin-right:4px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.echb:hover{border-color:var(--gold-deep)}
.echb.none{color:var(--ink-faint);font-family:'Inter',sans-serif;font-weight:500}
.echb.warn{color:var(--flag)}
.sfl{margin-top:6px;font-size:12px;color:var(--ink-soft)}
.sfl .sf{display:inline-flex;align-items:center;gap:5px;background:var(--field);border-radius:6px;padding:2px 8px;margin:2px 3px 0 0;font-size:11.5px}
.sfl .sf .se{color:var(--gold-deep);font-family:'Roboto Mono',monospace;font-size:10px}
.qrow{border-left:3px solid var(--gold);background:#FCFAF2;border-radius:0 9px 9px 0;padding:9px 12px;margin-bottom:7px}
.qrow:last-child{margin-bottom:0}
.qrow .qq{font-size:13.5px;font-weight:600}
.qrow .qm{font-size:11px;color:var(--ink-faint);margin-top:2px;display:flex;gap:8px;flex-wrap:wrap}
.qrow .qm .tag{background:var(--field);border-radius:5px;padding:1px 6px;font-weight:600;color:var(--gold-deep)}
.qrow.ausq{border-left-color:var(--line);background:var(--paper);color:var(--ink-faint)}
/* landing */
.land h2{font-size:24px;letter-spacing:-.3px;margin:0 0 6px;font-weight:700}
.land .lead{font-size:15px;color:var(--ink-soft);margin:0 0 24px;max-width:54ch}
.search{position:relative;margin-bottom:22px}
.search input{padding-left:42px}
.search i{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--ink-faint);font-size:18px}
.dep{font-size:11.5px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint);margin:22px 0 10px}
.svcgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.gi{border:1.5px solid var(--line);border-radius:12px;padding:15px 17px;background:var(--card);cursor:pointer;transition:border-color .15s}
.gi:hover{border-color:var(--gold-deep)}
.gi b{display:block;font-size:15px;margin-bottom:3px}
.gi span{font-size:12.5px;color:var(--ink-faint);font-weight:500}
@media (max-width:600px){.svcgrid{grid-template-columns:1fr}.help-drawer{width:100%;max-width:100%}.help-tab{padding:12px 8px}}
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner" id="topInner">
    <div class="crest" aria-hidden="true"></div>
    <div><div class="sub" id="topSub">Kanton Schaffhausen</div><h1 id="topTitle">Geführte Formulare</h1></div>
    <div class="proto-tag" id="protoTag">Prototyp</div>
  </div>
  <div class="progress-wrap" id="progWrap" style="display:none">
    <div class="progress" id="pbar"><span></span></div>
    <div class="stepmeta"><span id="stepName">Start</span><span id="stepCount"></span></div>
  </div>
</header>
<div class="layout" id="layout"><aside id="side"></aside><main class="stage" id="stage">Wird geladen…</main></div>
<button class="help-tab" id="helpTab" onclick="__help.open()" aria-label="Hilfe öffnen" style="display:none"><span class="dot"></span><i class="ti ti-lifebuoy" aria-hidden="true"></i><span class="label">Hilfe</span></button>
<div class="help-overlay" id="helpOverlay" onclick="__help.close()"></div>
<aside class="help-drawer" id="helpDrawer" aria-label="Hilfe zu dieser Seite">
  <div class="help-head"><i class="ti ti-lifebuoy" aria-hidden="true"></i><h3>Hilfe zu dieser Seite</h3><button class="x" onclick="__help.close()" aria-label="Schliessen"><i class="ti ti-x"></i></button></div>
  <div class="help-body" id="helpBody"></div>
  <div class="help-foot"><i class="ti ti-shield-check" aria-hidden="true"></i><span>Ihre Angaben werden erst am Schluss geprüft. Es wird nichts abgeschickt, bevor Sie es bestätigen.</span></div>
</aside>
<script>%%GEO%%</script>
<script>
var FLOWS=%%DATA%%;
var DS={gemeinden:window.CH_GEMEINDEN||[],plz:window.CH_PLZ||[],laender:window.CH_COUNTRIES||[],
        heimat:(window.CH_HEIMAT||(window.CH_GEMEINDEN||[]).concat(window.CH_COUNTRIES||[]))};
(function(){
var F=null,N=[],A={},hist=[],mode="land",editReturn=false,ACOPTS={};
var PROFIL={};try{PROFIL=JSON.parse(localStorage.getItem("ff_profil")||"{}")}catch(e){}
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
function ahv13ok(v){var d=(""+v).replace(/\D/g,"");if(d.length!==13)return false;var s0=0;
  for(var i=0;i<12;i++)s0+=(+d[i])*(i%2===0?1:3);return((10-(s0%10))%10)===(+d[12])}
function esc(s){return(""+(s==null?"":s)).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
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
var SEL=null;
function sidebar(filter){
  var side=document.getElementById("side");var f=(filter||"").toLowerCase();var by={};
  FLOWS.forEach(function(fl){var m=fl.meta;
    if(f&&((m.titel_einfach||"")+" "+(m.titel||"")+" "+(m.amt||"")).toLowerCase().indexOf(f)<0)return;
    var d=m.departement||"Übrige";(by[d]=by[d]||[]).push(fl)});
  var h='<div class="search" style="margin-bottom:4px"><i class="ti ti-search"></i><input type="text" id="q" value="'+esc(filter||"")+'" placeholder="Formular suchen …" oninput="__side.filter(this.value)"></div>';
  Object.keys(by).sort().forEach(function(dep){
    h+='<div class="dep">'+esc(dep)+'</div>';
    by[dep].sort(function(a,b){return(a.meta.titel_einfach||a.meta.titel).localeCompare(b.meta.titel_einfach||b.meta.titel)}).forEach(function(fl){
      h+='<div class="sv'+(SEL&&SEL.meta.form_id===fl.meta.form_id?" active":"")+'" onclick="__side.pick('+fl.meta.form_id+')"><b>'+esc(fl.meta.titel_einfach||fl.meta.titel)+'</b><span class="m">'+esc(fl.meta.amt||"")+' · '+fl.nodes.length+' Schritte</span></div>'});
  });
  side.innerHTML=h;
  var q=document.getElementById("q");if(q&&filter!==undefined){var v=q.value;q.focus();q.setSelectionRange(v.length,v.length)}}
window.__side={filter:function(v){sidebar(v)},pick:function(fid){var fl=null;FLOWS.forEach(function(x){if(x.meta.form_id===fid)fl=x});if(fl)detail(fl)}};
function echBadge(e,status){
  if(e){var lab=e.standard+(e.element?" · "+e.element:" · nur Standard");
    var warn=e.status&&e.status!=="Genehmigt";
    return '<a class="echb'+(warn?" warn":"")+'" href="'+esc(e.url||"#")+'" target="_blank" rel="noreferrer" title="'+esc((e.titel||e.standard)+(e.status?" · Status: "+e.status:""))+'">'+esc(lab)+(warn?" ⚠":"")+'</a>'}
  if(status==="kein_standard")return '<span class="echb none" title="kein eCH-Standard deckt dieses Feld ab">kein eCH-Standard</span>';
  return ""}
function nodesForField(fl,name){var out=[];fl.nodes.forEach(function(n){if((n.field||[]).indexOf(name)>-1)out.push(n)});return out}
function detail(fl){
  SEL=fl;F=null;mode="detail";document.body.classList.remove("playing");
  document.getElementById("progWrap").style.display="none";
  document.getElementById("helpTab").style.display="none";
  document.getElementById("topSub").textContent="Kanton Schaffhausen · "+(fl.meta.amt||"");
  document.getElementById("topTitle").textContent="Geführte Formulare";
  var tag=document.getElementById("protoTag");tag.outerHTML='<div class="proto-tag" id="protoTag">Prototyp</div>';
  sidebar(document.getElementById("q")?document.getElementById("q").value:"");
  var m=fl.meta,h='<div class="screen detail">';
  h+='<div class="eyebrow">'+esc(m.amt||"")+'</div>';
  h+='<div class="dhead"><div><h2>'+esc(m.titel_einfach||m.titel)+(m.veraltet?'<span class="stale" title="Die Quelldatei des Formulars hat sich seit der Flow-Erzeugung geändert – Flow neu generieren"><i class="ti ti-alert-triangle"></i> Formular aktualisiert</span>':"")+'</h2><p class="hint" style="margin:6px 0 0">'+esc(m.intro||"")+'</p></div>';
  h+='<div class="try"><button class="btn btn-primary" onclick="__side.play()"><i class="ti ti-player-play"></i> Ausprobieren</button></div></div>';
  h+='<p class="hint" style="margin-top:10px;font-size:13px">Amtliches Formular: <b>'+esc(m.titel)+'</b>'+(m.quelldatei?' · <a href="'+esc(m.quelldatei)+'" style="color:var(--gold-deep)">Original</a>':"")+' · '+fl.nodes.length+' Schritte</p>';
  h+='<div class="dfl"><div class="dfl-h"><span>Datenfeld & eCH-Standard</span><span>Frage(n) im geführten Ablauf</span></div>';
  var aus={};(fl.ausgelassen||[]).forEach(function(a){aus[a.feld]=a.grund});
  (fl.datenfelder||[]).forEach(function(d){
    var isAus=aus[d.name]!==undefined;
    h+='<div class="dfr'+(isAus?" aus":"")+'"><div><div class="fn">'+esc(d.name)+(d.pflicht?' <span style="color:var(--gold-deep)">*</span>':"")+(d.freiwillig?'<span class="fchip frei" title="keine gesetzliche Grundlage – wird als freiwillige Angabe gestellt">freiwillig</span>':"")+(d.sensibel?'<span class="fchip sens" title="besonders schützenswerte Personendaten">⛨ '+esc(d.sensibel)+'</span>':"")+'</div>';
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
        h+='<div class="qrow"><div class="qq">«'+esc(n.ask||n.text||n.id)+'»</div><div class="qm"><span class="tag">'+esc(n.type)+'</span><span>'+esc(secName2(fl,n.section))+'</span>'+(n.show_if?'<span title="wird nur bei Bedarf gefragt"><i class="ti ti-arrows-split-2"></i> '+esc(n.show_if)+'</span>':"")+'</div>';
        if(n.type==="form"&&(n.fields||[]).length)h+='<div class="qm" style="margin-top:4px">'+n.fields.map(function(f){return esc(f.label)}).join(" · ")+'</div>';
        h+='</div>'})}
    h+='</div></div>'});
  h+='</div></div>';
  document.getElementById("stage").innerHTML=h;window.scrollTo(0,0)}
function secName2(fl,sid){var ss=fl.sections||[];for(var i=0;i<ss.length;i++)if(ss[i][0]===sid)return ss[i][1];return sid}
window.__side.play=function(){if(SEL)startFlow(SEL)};
function landing(){
  if(FLOWS.length){detail(FLOWS[0])}else{document.getElementById("stage").innerHTML="<p class=hint>Keine Flows geladen.</p>";sidebar("")}}
// ---------- flow ----------
function startFlow(fl){
  F=fl;N=fl.nodes;A={};hist=[];mode="flow";editReturn=false;PROV={};document.body.classList.add("playing");
  FREI={};SENS={};(fl.datenfelder||[]).forEach(function(d){if(d.freiwillig)FREI[d.name]=1;if(d.sensibel)SENS[d.name]=d.sensibel});
  EMAPN={};var em=fl.ech_map||{};Object.keys(em).forEach(function(k){EMAPN[normk(k)]=em[k]});
  document.getElementById("progWrap").style.display="";
  document.getElementById("helpTab").style.display="";
  document.getElementById("topSub").textContent="Kanton Schaffhausen · "+(fl.meta.amt||"");
  document.getElementById("topTitle").textContent=fl.meta.titel_einfach||fl.meta.titel;
  var tag=document.getElementById("protoTag");tag.outerHTML='<button class="allbtn" id="protoTag" onclick="__ff.toLanding()"><i class="ti ti-arrow-left"></i> Zur Übersicht</button>';
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
  h+='<div class="note-box" style="white-space:normal">Amtliches Formular: <b>'+esc(m.titel)+'</b>'+(m.quelldatei?' \u00b7 <a href="'+esc(m.quelldatei)+'" style="color:var(--gold-deep)">Original ansehen</a>':"")+(m.stand?' \u00b7 Flow-Stand '+esc(m.stand):"")+'</div>';
  var draft=null;try{draft=JSON.parse(localStorage.getItem(draftKey())||"null")}catch(e){}
  h+='<div class="nav">';
  if(draft&&draft.hist&&draft.hist.length){h+='<button class="btn btn-ghost" onclick="__ff.resume()"><i class="ti ti-player-track-next"></i> Fortsetzen (Schritt '+draft.hist.length+')</button>'}
  h+='<div class="spacer"></div><button class="btn btn-primary" onclick="__ff.begin()">Los geht\u2019s <i class="ti ti-arrow-right"></i></button></div></div>';
  stage.innerHTML=h;
  document.querySelector("#pbar span").style.width="2%";
  document.getElementById("stepName").textContent="Start";
  document.getElementById("stepCount").textContent=N.filter(passes).length+" Schritte"}
function eyebrowFor(n){if(n.type==="note")return"Hinweis";if(n.type==="doc_scan"||n.type==="scan")return"Dokument";
  var vis=N.filter(passes),c=0;for(var j=0;j<vis.length;j++){if(vis[j].type!=="note"&&vis[j].type!=="doc_scan"&&vis[j].type!=="scan"){c++;if(vis[j].id===n.id)break}}return"Frage "+c}
function nodeBadges(n){var h="";var names=n.field||[];
  var alleFrei=names.length&&names.every(function(x){return FREI[x]});
  var sens=null;names.forEach(function(x){if(SENS[x])sens=SENS[x]});
  if(alleFrei)h+='<div class="fwchip"><i class="ti ti-scale"></i> Freiwillige Angabe \u2013 keine gesetzliche Pflicht. Sie k\u00f6nnen diesen Schritt \u00fcberspringen.</div>';
  if(sens)h+='<div class="snote"><i class="ti ti-shield-lock"></i> Besonders sch\u00fctzenswerte Daten ('+esc(sens)+'). Sie werden nur f\u00fcr diesen Antrag verwendet.</div>';
  return h}
function whyHTML(n){var b=nodeBadges(n);if(!n.why&&!n.hilfe)return b;return b+'<button class="whylink" onclick="__help.open()"><i class="ti ti-info-circle" aria-hidden="true"></i> '+(n.why?"Warum fragen wir das?":"Hilfe zu dieser Seite")+'</button>'}
function helpFor(n){var s=n.hilfe||"";
  if(!s){if(n.type==="choice")s="Wählen Sie die zutreffende Antwort. Sie können jederzeit zurückgehen und die Auswahl ändern.";
  else if(n.type==="multiselect")s="Wählen Sie alle zutreffenden Antworten aus und tippen Sie dann auf Weiter.";
  else if(n.type==="doc_scan"||n.type==="scan")s="Fotografieren Sie das Dokument gut lesbar. Ohne Dokument überspringen Sie den Schritt, wo möglich.";
  else if(n.type==="roster")s="Fügen Sie jede Person bzw. jeden Eintrag einzeln hinzu. Falsche Einträge entfernen Sie mit dem ✕.";
  else if(n.type==="form")s="Füllen Sie die Felder aus und tippen Sie auf Weiter. Bei Orten und Ländern wählen Sie einen Vorschlag aus der Liste.";
  else s="Geben Sie Ihre Antwort ein und tippen Sie auf Weiter.";}
  return{steps:s,why:n.why}}
function updateHelp(n){var body=document.getElementById("helpBody"),tab=document.getElementById("helpTab");if(!body)return;
  if(!n){body.innerHTML='<div class="help-q">'+(mode==="review"?"Prüfung Ihrer Angaben":"Geführtes Ausfüllen")+'</div><div class="help-sec"><div class="help-h"><i class="ti ti-list-check"></i> So gehen Sie vor</div><p class="help-p">'+(mode==="review"?"Prüfen Sie jede Zeile in Ruhe. Tippen Sie auf „Ändern“, um etwas zu korrigieren. Erst mit „Absenden“ wird das Formular übermittelt.":"Beantworten Sie die Fragen Schritt für Schritt. Über „Zurück“ ändern Sie frühere Antworten jederzeit.")+'</p></div>';if(tab)tab.classList.remove("has-why");return}
  var hf=helpFor(n),html='<div class="help-q">'+esc(n.ask||n.intro||("Abschnitt: "+(n.section||"")))+'</div>';
  html+='<div class="help-sec"><div class="help-h"><i class="ti ti-list-check"></i> So füllen Sie das aus</div><p class="help-p">'+esc(hf.steps)+'</p></div>';
  if(hf.why)html+='<div class="help-sec"><div class="help-h"><i class="ti ti-info-circle"></i> Warum fragen wir das?</div><p class="help-p">'+esc(hf.why)+'</p></div>';
  body.innerHTML=html;if(tab)tab.classList.toggle("has-why",!!hf.why)}
function isFrei(n){var names=n.field||[];return names.length&&names.every(function(x){return FREI[x]})}
function nav(onclick,label,n){var skip=(n&&(n.optional||isFrei(n)))?'<button class="btn btn-ghost" onclick="__ff.skipNode(\''+n.id+'\')">\u00dcberspringen</button>':"";
  return'<div class="err" id="fferr"></div><div class="nav">'+(hist.length>1?'<button class="btn btn-ghost" onclick="__ff.back()">Zur\u00fcck</button>':"")+'<div class="spacer"></div>'+skip+'<button class="btn btn-primary" onclick="'+onclick+'">'+(label||"Weiter")+'</button></div>'}
function fieldInput(f,val,cls){cls=cls||"ffc";
  if(f.type==="select"){var opts=normOpts(f.options);var o='<select class="'+cls+'" data-k="'+esc(f.key)+'"><option value=""'+(val?"":" selected")+'>– bitte wählen –</option>';
    for(var i=0;i<opts.length;i++)o+='<option value="'+esc(opts[i][0])+'"'+(val===opts[i][0]?" selected":"")+'>'+esc(opts[i][1])+'</option>';return o+'</select>'}
  if(f.type==="autocomplete"){var ds=dsFor(f);ACOPTS[f.key]=ds;var disp=optLabel(ds,val);
    return'<div class="ac" data-k="'+esc(f.key)+'"><input type="text" class="ac-input" autocomplete="off" placeholder="'+esc(f.placeholder||"Tippen zum Suchen …")+'" value="'+esc(val?disp:"")+'" oninput="__ac.f(this,\''+f.key+'\')" onfocus="__ac.open(this,\''+f.key+'\')" onkeydown="__ac.k(event,\''+f.key+'\')"><input type="hidden" class="'+cls+'" data-k="'+esc(f.key)+'" value="'+esc(val||"")+'"><div class="ac-list" id="ac_'+f.key+'"></div></div>'}
  var t=f.type==="date"?"date":(f.type==="number"?"number":"text");
  return'<input class="'+cls+'" data-k="'+esc(f.key)+'" type="'+t+'" value="'+esc(val||"")+'" placeholder="'+esc(f.placeholder||"")+'">'}
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
function renderNode(n){var h="",eb=eyebrowFor(n);updateHelp(n);
  if(n.type==="choice"){var opts=normOpts(n.options);
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n)+'<div class="choices">';
    for(var i=0;i<opts.length;i++){var v=opts[i][0],lab=opts[i][1],sub=opts[i][2];
      h+='<div class="choice'+(A[okey(n)]===v?" sel":"")+'" onclick="__ff.select(\''+n.id+'\',this)" data-v="'+esc(v)+'"><span class="dot"></span><span>'+esc(lab)+(sub?'<span class="sub">'+esc(sub)+'</span>':"")+'</span></div>'}
    h+='</div>'+nav("__ff.choiceNext('"+n.id+"')",null,n)+'</div>';stage.innerHTML=h;updateProgress(n);return}
  if(n.type==="multiselect"){var opts2=normOpts(n.options);var cur=A[okey(n)]||[];
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"Mehrere Antworten möglich.")+'</p>'+whyHTML(n)+'<div class="choices">';
    for(var i2=0;i2<opts2.length;i2++){var v2=opts2[i2][0],l2=opts2[i2][1];
      h+='<div class="choice multi'+(cur.indexOf(v2)>-1?" sel":"")+'" onclick="this.classList.toggle(\'sel\')" data-v="'+esc(v2)+'"><span class="dot"></span><span>'+esc(l2)+'</span></div>'}
    h+='</div>'+nav("__ff.multiNext('"+n.id+"')",null,n)+'</div>';stage.innerHTML=h;updateProgress(n);return}
  if(n.type==="text"||n.type==="number"){var pre=A[okey(n)];var fromProf=false;
    if(pre===undefined){var pv0=profVal(n,null);if(pv0!=null){pre=pv0;fromProf=true;PROV[okey(n)]="profil"}}
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n)+(fromProf?'<div class="fwchip" style="background:var(--field);color:var(--gold-deep)"><i class="ti ti-user-check"></i> Aus Ihrem Profil vorausgef\u00fcllt \u2013 bitte pr\u00fcfen.</div>':"")+'<div class="fc"'+(n.type==="number"?' style="max-width:240px"':"")+'><input id="ffi" type="'+(n.type==="number"?"number":"text")+'" value="'+esc(pre||"")+'" placeholder="'+esc(n.placeholder||"")+'"></div>'+nav("__ff.textNext('"+n.id+"')",null,n)+'</div>';
    stage.innerHTML=h;updateProgress(n);var fi=document.getElementById("ffi");if(fi){fi.addEventListener("keydown",function(e){if(e.key==="Enter")__ff.textNext(n.id)});setTimeout(function(){fi.focus()},50)}return}
  if(n.type==="date"){var pv=A[okey(n)]||"";
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n)+'<div class="fc" style="max-width:240px"><input id="ffi" type="date" value="'+esc(pv)+'"></div>'+nav("__ff.textNext('"+n.id+"')",null,n)+'</div>';
    stage.innerHTML=h;updateProgress(n);return}
  if(n.type==="note"){h='<div class="screen"><div class="eyebrow">Hinweis</div><h2 class="q" style="font-size:22px">'+esc(n.ask||"Gut zu wissen")+'</h2><div class="note-box">'+esc(n.text||"")+'</div>'+nav("__ff.advance('"+n.id+"')","Verstanden")+'</div>';stage.innerHTML=h;updateProgress(n);return}
  if(n.type==="doc_scan"||n.type==="scan"){
    h='<div class="screen"><div class="eyebrow">Dokument</div><h2 class="q">'+esc(n.ask||("Dokument: "+(n.document||"")))+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n);
    h+='<div class="scan-drop" id="ffdrop"><div class="ic"><i class="ti ti-camera" aria-hidden="true"></i></div><div style="margin-top:8px;font-size:14.5px">Foto von: '+esc(n.document||"Dokument")+'</div><button class="btn btn-primary" style="margin-top:14px" onclick="__ff.scan(\''+n.id+'\')">Foto hinzufügen</button></div>';
    h+='<div class="err" id="fferr"></div><div class="nav">'+(hist.length>1?'<button class="btn btn-ghost" onclick="__ff.back()">Zurück</button>':"")+'<div class="spacer"></div>'+(n.optional?'<button class="btn btn-ghost" onclick="__ff.skip(\''+n.id+'\')">Habe ich nicht – überspringen</button>':"")+'</div></div>';
    stage.innerHTML=h;updateProgress(n);return}
  if(n.type==="form"||n.type==="confirm"){
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div>';
    if(n.ask)h+='<h2 class="q">'+esc(n.ask)+'</h2>';else h+='<h2 class="q" style="font-size:22px">'+esc(n.intro||"")+'</h2>';
    if(n.hint)h+='<p class="hint">'+esc(n.hint)+'</p>';
    h+=whyHTML(n)+'<div style="margin-top:10px">';
    var pf={};if(n.prefill)for(var pk in n.prefill){pf[pk]=n.prefill[pk]==="@heute"?new Date().toISOString().slice(0,10):(A[n.prefill[pk]]||"")}
    for(var j=0;j<(n.fields||[]).length;j++){var f=n.fields[j];var val=A[f.key]!==undefined?A[f.key]:(pf[f.key]||"");
      var fromProf=false;
      if(val===""){var pv=profVal(n,f);if(pv!=null){val=pv;fromProf=true;PROV[f.key]="profil"}}
      h+='<div class="fc"><label class="lbl">'+esc(f.label)+(fromProf?' <span style="color:var(--gold-deep);font-weight:600">\u00b7 aus Ihrem Profil</span>':"")+'</label>'+fieldInput(f,val)+'</div>'}
    h+='</div>'+nav("__ff.formNext('"+n.id+"')",n.intro&&!n.ask?"Stimmt so":"Weiter",n)+'</div>';
    stage.innerHTML=h;updateProgress(n);return}
  if(n.type==="roster"){var key=okey(n);if(!A[key])A[key]=[];
    h='<div class="screen"><div class="eyebrow">'+esc(eb)+'</div><h2 class="q">'+esc(n.ask)+'</h2><p class="hint">'+(n.hint?esc(n.hint):"&nbsp;")+'</p>'+whyHTML(n);
    var ifs=n.item_fields||[];
    for(var p=0;p<A[key].length;p++){var per=A[key][p];var vals=[];for(var q=0;q<Math.min(2,ifs.length);q++){var vv=per[ifs[q].key];if(vv)vals.push(vv)}
      h+='<div class="chip"><span>'+esc(vals.join(" ")||"Eintrag "+(p+1))+'</span><button onclick="__ff.rosterRemove(\''+n.id+'\','+p+')" aria-label="Entfernen"><i class="ti ti-x"></i></button></div>'}
    h+='<div class="roster-card">';
    for(var j2=0;j2<ifs.length;j2++){var f2=ifs[j2];h+='<div class="fc"><label class="lbl">'+esc(f2.label)+'</label>'+fieldInput(f2,"","ffr")+'</div>'}
    h+='<button class="btn btn-ghost" onclick="__ff.rosterAdd(\''+n.id+'\')"><i class="ti ti-plus"></i> Hinzufügen</button></div>'+nav("__ff.advance('"+n.id+"')",null,n)+'</div>';
    stage.innerHTML=h;updateProgress(n);return}
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
  var html='<div class="screen"><div class="rev-head"><div class="check"><i class="ti ti-check"></i></div><div><h2 class="rev-title">Bitte prüfen Sie Ihr Formular</h2></div></div>';
  html+='<p class="rev-sub">Wir haben das amtliche Formular <b>'+esc(m.titel)+'</b> aus Ihren Antworten ausgefüllt. Stimmt etwas nicht, tippen Sie auf „Ändern“.</p>';
  var hl=((F.review||{}).highlight)||[];
  if(hl.length){html+='<div class="checklist"><div class="ttl">Bitte besonders prüfen</div>';
    hl.forEach(function(h){var n=byId(h.answer);if(!n||!passes(n))return;var v=A[okey(n)];
      if(n.type==="choice")v=optLabel(n.options,v);if(v===undefined||v==="")v="—";if(Array.isArray(v))v=v.length+" Einträge";
      html+='<div>• '+esc(h.prompt)+' <b style="color:var(--ink)">('+esc(""+v)+')</b></div>'});html+='</div>'}
  html+='<div class="toolbar"><label class="toggle" onclick="__ff.togBeh()"><span class="switch"></span> Behörden-Ansicht (Datenfelder zeigen)</label><span class="note">Zeigt die Datenfelder des Katalogs im Hintergrund.</span></div>';
  html+='<div class="formdoc"><div class="formdoc-top"><div class="crest" aria-hidden="true"></div><div class="t">'+esc(m.titel)+'<span>Kanton Schaffhausen · '+esc(m.amt||"")+'</span></div><div class="formnr mono">'+esc(m.formnr||("Formular #"+m.form_id))+'</div></div>';
  var ss=F.sections&&F.sections.length?F.sections:[];
  if(!ss.length){var seen={};N.forEach(function(n){if(!seen[n.section]){seen[n.section]=1;ss.push([n.section,n.section])}})}
  ss.forEach(function(s){var block="";rows.forEach(function(r){if(r.section!==s[0])return;
    block+='<div class="rowf"><div class="meta"><div class="flabel">'+esc(r.label)+' <span class="machine mono">'+esc(r.machine)+'</span></div><div class="fval">'+esc(r.value)+'</div><div class="src">'+(r.prov==="profil"?"aus Ihrem Profil übernommen":"übernommen aus Ihren Antworten")+'</div></div><button class="edit" onclick="__ff.edit(\''+r.node+'\')">Ändern</button></div>'});
    if(block)html+='<div class="grp"><div class="grp-h">'+esc(s[1])+'</div>'+block+'</div>'});
  html+='</div>';
  html+='<div class="submit-row"><button class="btn btn-ghost" onclick="__ff.back()">Zurück</button><button class="btn btn-ghost" onclick="__ff.exportECH()"><i class="ti ti-download"></i> Daten als eCH-JSON</button><div class="spacer"></div><button class="btn btn-primary" id="submitBtn" onclick="__ff.submit()">Absenden</button></div>';
  html+='<div class="done-msg" id="doneMsg">Im Prototyp wird nichts abgeschickt. In der echten Anwendung ginge das geprüfte Formular jetzt direkt ans '+esc(m.amt||"Amt")+'.</div>';
  var dv=F.dvsh||{};var steps=(dv.ablauf||[]).filter(function(x){return x});
  html+='<div class="next-steps" id="nextSteps"><div class="ttl"><i class="ti ti-route"></i> So geht es weiter</div>';
  if(steps.length){html+='<ol>'+steps.map(function(st2){return'<li>'+esc(typeof st2==="string"?st2:(st2.text||st2.beschreibung||JSON.stringify(st2)))+'</li>'}).join("")+'</ol>'}
  else{html+='<ol><li>Das '+esc(m.amt||"Amt")+' prüft Ihre Angaben.</li><li>Bei Rückfragen werden Sie kontaktiert.</li><li>Sie erhalten den Entscheid bzw. die Bestätigung.</li></ol>'}
  if(dv.kontakt){var ko=dv.kontakt;var kt=typeof ko==="string"?ko:[ko.name,ko.telefon,ko.email,ko.adresse].filter(Boolean).join(" · ");
    if(kt)html+='<div class="kontakt"><i class="ti ti-phone"></i> Kontakt: '+esc(kt)+'</div>'}
  html+='</div>';
  html+='<div class="restart"><button class="btn-link" onclick="__ff.restart()">Von vorne beginnen</button> · <button class="btn-link" onclick="__ff.toLanding()">Zur Übersicht</button></div></div>';
  stage.innerHTML=html;document.body.classList.remove("behoerden");updateProgress(null)}
window.__ff={
begin:function(){mode="flow";var f=nextFrom(0);hist.push(f.id);renderNode(f)},
select:function(id,el){var n=byId(id);A[okey(n)]=el.getAttribute("data-v");
  var cs=stage.querySelectorAll(".choice");for(var i=0;i<cs.length;i++)cs[i].classList.remove("sel");el.classList.add("sel");
  var self=this;setTimeout(function(){self.choiceNext(id)},180)},
choiceNext:function(id){var n=byId(id);if(A[okey(n)]===undefined){document.getElementById("fferr").textContent="Bitte eine Option wählen.";return}this.advance(id)},
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
    if(fd&&fd.pflicht&&!val&&!isFrei(n)){document.getElementById("fferr").textContent="Bitte „"+fd.label+"“ ausfüllen.";return}
    A[k]=val;if(fd)profSave(n,fd,val)}
  this.advance(id)},
rosterAdd:function(id){var n=byId(id);var ins=stage.querySelectorAll(".ffr");var obj={},any=false;
  for(var i=0;i<ins.length;i++){var k=ins[i].getAttribute("data-k");obj[k]=ins[i].value;if(ins[i].value)any=true}
  if(!any){document.getElementById("fferr").textContent="Bitte mindestens ein Feld ausfüllen.";return}
  A[okey(n)].push(obj);renderNode(n)},
rosterRemove:function(id,idx){var n=byId(id);A[okey(n)].splice(idx,1);renderNode(n)},
scan:function(id){var n=byId(id);var d=document.getElementById("ffdrop");
  d.innerHTML='<div style="font-size:14.5px;color:var(--gold-deep)"><i class="ti ti-loader"></i> '+esc(n.document||"Dokument")+' wird gelesen …</div>';
  var self=this;setTimeout(function(){A[okey(n)]="✓ beigelegt";self.advance(id)},900)},
skip:function(id){this.advance(id)},
skipNode:function(id){var n=byId(id);if(A[okey(n)]===undefined)A[okey(n)]="";this.advance(id)},
advance:function(id){saveDraft();if(editReturn){editReturn=false;goReview();return}
  var cur=byId(id||hist[hist.length-1]);var idx=N.indexOf(cur)+1;var nx=nextFrom(idx);
  if(!nx){goReview();return}hist.push(nx.id);renderNode(nx)},
back:function(){if(mode==="review"){mode="flow";renderNode(byId(hist[hist.length-1]));return}
  if(hist.length>1){hist.pop();renderNode(byId(hist[hist.length-1]))}else introScreen()},
edit:function(id){editReturn=true;mode="flow";renderNode(byId(id))},
togBeh:function(){document.body.classList.toggle("behoerden")},
submit:function(){document.getElementById("doneMsg").classList.add("show");
  var ns=document.getElementById("nextSteps");if(ns)ns.classList.add("show");
  clearDraft();var b=document.getElementById("submitBtn");b.disabled=true;b.textContent="Geprüft ✓"},
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
resume:function(){var d=null;try{d=JSON.parse(localStorage.getItem(draftKey())||"null")}catch(e){}
  if(!d){this.begin();return}A=d.A||{};hist=d.hist||[];mode="flow";
  var last=byId(hist[hist.length-1]);if(last)renderNode(last);else this.begin()},
toLanding:function(){var fl=F||SEL;document.body.classList.remove("playing");detail(fl||FLOWS[0])}
};
window.__ac={
render:function(inp,key,clearHidden){var q=(inp.value||"").toLowerCase().trim();var opts=ACOPTS[key]||[];
  var list=document.getElementById("ac_"+key);var wrap=inp.parentNode;
  if(clearHidden)wrap.querySelector("input[type=hidden]").value="";
  var m=[];for(var i=0;i<opts.length&&m.length<8;i++){if((""+opts[i][1]).toLowerCase().indexOf(q)>-1)m.push(opts[i])}
  if(!m.length){list.innerHTML='<div class="ac-empty">Kein Treffer – Sie können den Text auch frei stehen lassen.</div>';list.classList.add("open");
    wrap.querySelector("input[type=hidden]").value=inp.value;return}
  var h="";for(var j=0;j<m.length;j++){h+='<div class="ac-item" onmousedown="__ac.pick(event,\''+key+'\',this)" data-code="'+esc(m[j][0])+'"><span>'+esc(m[j][1])+'</span><span class="code">'+esc(m[j][0])+'</span></div>'}
  list.innerHTML=h;list.classList.add("open")},
f:function(inp,key){this.render(inp,key,true)},
open:function(inp,key){this.render(inp,key,false)},
pick:function(ev,key,el){ev.preventDefault();var wrap=el.parentNode.parentNode;
  wrap.querySelector(".ac-input").value=el.querySelector("span").textContent;
  wrap.querySelector("input[type=hidden]").value=el.querySelector("span").textContent;
  document.getElementById("ac_"+key).classList.remove("open")},
k:function(ev,key){if(ev.key==="Escape")document.getElementById("ac_"+key).classList.remove("open")}
};
document.addEventListener("click",function(e){if(!e.target.closest||!e.target.closest(".ac")){var ls=document.querySelectorAll(".ac-list.open");for(var i=0;i<ls.length;i++)ls[i].classList.remove("open")}});
window.__help={open:function(){document.getElementById("helpDrawer").classList.add("open");document.getElementById("helpOverlay").classList.add("open")},close:function(){document.getElementById("helpDrawer").classList.remove("open");document.getElementById("helpOverlay").classList.remove("open")}};
landing();
})();
</script>
</body>
</html>"""


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
                          d.no_basis, d.ech_status, COALESCE(e.standard, d.ech_standard_code) std, e.name el,
                          st.status sstat, st.url surl, st.title stitle
                          FROM data_field d
                          LEFT JOIN ech_element e ON e.id=d.ech_element_id
                          LEFT JOIN ech_standard st ON st.code=COALESCE(e.standard, d.ech_standard_code)
                          WHERE d.form_id=? ORDER BY d.ord""", [fid]):
        out.append({"name": d["name"], "definition": d["definition"], "typ": d["data_type"],
                    "pflicht": bool(d["required"]), "sensibel": d["sensitive"],
                    "freiwillig": bool(d["no_basis"]),
                    "ech_status": d["ech_status"],
                    "ech": ({"standard": d["std"], "element": d["el"], "status": d["sstat"],
                             "url": d["surl"], "titel": d["stitle"]} if d["std"] else None),
                    "teilfelder": subs.get(d["id"], [])})
    return out


def main():
    c = connect(DB_PATH)
    flows = []
    import hashlib
    try:
        for r in c.execute("""SELECT ff.form_id, ff.flow, ff.form_hash, ff.generated_at,
                              f.source_file, s.id sid, s.dienststelle, s.department FROM formflow ff
                              JOIN form f ON f.id=ff.form_id JOIN service s ON s.id=f.service_id
                              ORDER BY s.department, s.name"""):
            fl = json.loads(r["flow"])
            # DB is the source of truth for office/department — agents sometimes
            # "correct" the spelling (Departement vs Department) and split the sidebar
            fl["meta"]["amt"] = r["dienststelle"] or fl["meta"].get("amt")
            fl["meta"]["departement"] = r["department"] or fl["meta"].get("departement")
            fl["meta"]["stand"] = (r["generated_at"] or "")[:10]
            # staleness: source file changed since the flow was derived?
            stale = False
            if r["source_file"] and os.path.exists(r["source_file"]) and r["form_hash"]:
                cur = hashlib.sha256(open(r["source_file"], "rb").read()).hexdigest()[:16]
                stale = (cur != r["form_hash"])
            fl["meta"]["veraltet"] = stale
            fl["datenfelder"] = datenfelder(c, r["form_id"])
            # eCH map for once-only prefill + standards export. Field level keys
            # are the data-field name -> "eCH-XXXX·element"; subfield level keys
            # are "Feld›Teilfeld".
            em = {}
            for d in fl["datenfelder"]:
                if d.get("ech") and d["ech"].get("element"):
                    em[d["name"]] = d["ech"]["standard"] + "\u00b7" + d["ech"]["element"]
                for sf in (d.get("teilfelder") or []):
                    if sf.get("ech") and sf["ech"].get("element"):
                        em[d["name"] + "\u203a" + sf["name"]] = sf["ech"]["standard"] + "\u00b7" + sf["ech"]["element"]
            fl["ech_map"] = em
            # DVSH: real process steps + contact for the done screen
            dv = c.execute("SELECT ablauf, kontakt FROM dvsh_service WHERE service_id=? LIMIT 1",
                           [r["sid"]]).fetchone()
            if dv:
                try:
                    ab = json.loads(dv["ablauf"]) if dv["ablauf"] else []
                except Exception:
                    ab = []
                try:
                    ko = json.loads(dv["kontakt"]) if dv["kontakt"] else None
                except Exception:
                    ko = dv["kontakt"]
                if ab or ko:
                    fl["dvsh"] = {"ablauf": ab[:8], "kontakt": ko}
            flows.append(fl)
    except Exception as e:
        print("keine formflow-Tabelle?", e)
    c.close()
    geo = ""
    if os.path.exists(GEO):
        geo = open(GEO, encoding="utf-8").read()
    else:
        print("WARN: ch-geo.js nicht gefunden — Autocomplete fällt auf Freitext zurück")
    html = (TEMPLATE
            .replace("%%GEO%%", geo)
            .replace("%%DATA%%", json.dumps(flows, ensure_ascii=False)))
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"wrote {OUT}  ({os.path.getsize(OUT)//1024} KB, {len(flows)} Flows)")


if __name__ == "__main__":
    main()
