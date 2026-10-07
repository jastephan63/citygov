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
