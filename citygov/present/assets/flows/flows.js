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
