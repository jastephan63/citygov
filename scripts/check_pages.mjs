#!/usr/bin/env node
// Automatic page check — the last step of ./build.sh (see scripts/README.md).
//
// Opens the BUILT pages of the repository root in a local headless Chrome and
// fails with one plain message per finding. No npm package: the browser is
// driven over the DevTools protocol through a pipe (no port, no web socket),
// and it cannot reach the network while it runs.
//
//   node scripts/check_pages.mjs                    every check
//   node scripts/check_pages.mjs --only kontrast    one check (several: --only summen,links)
//   node scripts/check_pages.mjs --verbose          every measured value, also where nothing is wrong
//   node scripts/check_pages.mjs --root <dir>       the pages of another directory (a copy, an older build)
//   node scripts/check_pages.mjs --breite 1024      the same checks in a window of 1024 px instead of 1280
//                                                   (the dashboard changes its table layout at 1340 and 700 px)
//
// The checks (the name is what --only takes):
//   syntax    every inline script of dashboard.html and flows.html parses; inlined JSON is valid
//   seiten    every page in PAGES and every document in DOCUMENTS opens: enough text, no start-up
//             error, no «Unbekannte Seite», no error in the console, no request to another host,
//             no data table without a column head (th), also where it is folded;
//             every page the navigation offers is listed in PAGES
//   summen    every bar adds up: segments = legend = the total its card states; every list that
//             states its total (.sumbox: the numbers .sumn and the one .sumtot) adds up to it —
//             a box with several columns pairs them by data-s
//   kontrast  text colour against its background: 4.5:1, large text 3:1 (WCAG 2.1 AA, 1.4.3)
//   links     no link in the browser's default blue
//   schrift   no visible text below 12 px
//   groesse   dashboard.html stays below 95 MiB: GitHub refuses a file over 100 MB, so the push and
//             the website would stop updating; from 50 MiB GitHub only warns (size is no goal)
//   tastatur  whatever reacts to a click can be reached with the Tab key
//
// Not seen by the check: text that CSS draws (::before), text on a picture or gradient
// and the colours of text inside an SVG (both are counted, see --verbose), and whatever
// appears only after a click (an opened explanation, the steps of a guided form).
//
// Exit code: 0 = every check passed, or the check was skipped because no Chrome
// was found (or CHECK_PAGES=skip was set); 1 = at least one finding, or a Chrome
// that was found but did not start (nothing was checked then); 2 = wrong call.
// Chrome is looked up in the usual places; CHROME=/path/to/chrome overrides, and
// CHROME_FLAGS adds start options (for example --no-sandbox inside a container).
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath, pathToFileURL } from 'node:url';

// =====================================================================================
// THE LIST OF PAGES — every page of the dashboard, by its address after the «#»
// (page, or page/service/part as the address bar shows it).
// A NEW PAGE MUST BE ADDED HERE: its route is then walked, its bars are summed, its
// links, text sizes and click targets are checked. The check fails when the navigation
// of the dashboard offers a page that is missing from this list.
//   contrast: true   the text colours of this page are measured as well (check «kontrast»);
//                    set it for a page that brings colours of its own
//   open: true       before anything is measured, every folded part of the page is opened
//                    (<details>) and every «weitere …» / «alle … zeigen» button pressed — for a
//                    page that keeps much of its text folded
// A route that names one Dienststelle or one service must name one that exists; when
// it goes, the check says so and another one is put here.
// =====================================================================================
const PAGES = [
  { route: 'home', contrast: true },
  { route: 'methode' },
  { route: 'dienststellen', contrast: true },
  { route: 'dienststellen/all/abteilung-gewasser-und-materialabbau' },   // one Dienststelle briefing
  { route: 'kanton' },
  { route: 'recherche' },
  { route: 'todo', contrast: true },
  { route: 'katalog' },
  { route: 'begriffe' },
  { route: 'esh' },
  { route: 'datenmodell', contrast: true, open: true },                  // Datenmodell, all of it unfolded (roles, concepts, identifiers, editions)
  { route: 'datenmodell/all/g-270', contrast: true },                    // the change-impact explorer at one law (FamZG, a newer edition in force)
  { route: 'datenmodell/all/a-447', contrast: true },                    // the explorer at one article (its row selected, its Formulare open)
  { route: 'datenmodell/all/k-vorname', contrast: true },                // one concept, opened at its address
  { route: 'onceonly', contrast: true, open: true },                     // Was Register schon wissen, all of it unfolded
  { route: 'gestaltung', contrast: true, open: true },                   // Gestaltung der Formulare, all of it unfolded
  { route: 'gestaltung/all/grenzen', contrast: true },                   // a section address (opens the folded limits)
  // one register at its address: it draws the whole page «Was Register schon wissen» and brings the
  // register into view, so it stands apart from that page (the check compares a page with the one before)
  { route: 'onceonly/all/r-einwohnerregister', contrast: true },
  { route: 'lebenslagen' },
  { route: 'register' },
  { route: 'rules' },
  { route: 'guide' },
  { route: 'datenfluss' },
  { route: 'buerger' },
  { route: 'fields' },
  { route: 'fields/296', contrast: true },                               // one service page
  { route: 'fields/116/form-116~gest', contrast: true, open: true },     // one Formular-Ansicht, its panel «Gestaltung» open
  { route: 'fields/115/form-115~part', contrast: true, open: true },     // a Formular with many parties: its panels «Parteien» and «Was Register schon wissen»
  { route: 'fields/238/form-238~reg', contrast: true },                  // a Formular opened at its panel «Was Register schon wissen»
  { route: 'search/all/zivilstand' },                                    // one search
];

// The other generated documents. «dossier» picks a file from dossiers/ by size: the
// largest shows every block a dossier can have, the smallest is the bare case.
const DOCUMENTS = [
  { file: 'index.html' },
  { file: 'flows.html', contrast: true },
  { file: '404.html', minText: 100 },
  { file: 'dossiers/index.html' },
  { dossier: 'largest', contrast: true },
  { dossier: 'smallest' },
];

const MIN_TEXT = 400;            // characters a page must show at least (an unknown Dienststelle shows about 140)
const CONTRAST_NORMAL = 4.5;     // WCAG 2.1 AA
const CONTRAST_LARGE = 3;        // … for text from 24 px, or from 18.66 px when bold
const TEXT_FLOOR_PX = 12;
const TEXT_FLOOR_EXEMPT = 'sup, sub';   // footnote marks and indices are smaller by nature
const MAX_DASHBOARD_MIB = 95;    // GitHub refuses files over 100 MB; size is otherwise no goal (owner, 2026-10-04)
const WARN_DASHBOARD_MIB = 50;   // GitHub prints a warning on push from here — information only
const VIEWPORT = { width: 1280, height: 900 };   // an office laptop; --breite changes the width
const TIME_LIMIT_S = 100;        // the whole check; it normally takes five to ten seconds
const SHOWN = 8;                 // detail lines per finding without --verbose

const CHECKS = ['syntax', 'seiten', 'summen', 'kontrast', 'links', 'schrift', 'groesse', 'tastatur'];
const ALIAS = { routes: 'seiten', pages: 'seiten', sums: 'summen', contrast: 'kontrast', bluelinks: 'links',
  text: 'schrift', textsize: 'schrift', size: 'groesse', 'grösse': 'groesse', keyboard: 'tastatur' };
const NEEDS_BROWSER = new Set(['seiten', 'summen', 'kontrast', 'links', 'schrift', 'tastatur']);
const SKIPPED = 'Seitenprüfung übersprungen: Node oder Chrome nicht gefunden';

// ---------------------------------------------------------------- command line
const HERE = path.dirname(fileURLToPath(import.meta.url));
const USAGE = `Aufruf: node scripts/check_pages.mjs [--only <prüfung>[,<prüfung>…]] [--verbose] [--root <verzeichnis>] [--breite <px>]
Prüfungen: ${CHECKS.join(', ')}`;
function parseArgs(argv) {
  const o = { only: new Set(), verbose: false, root: path.join(HERE, '..'), breite: null };
  argv = argv.flatMap(a => { const m = /^(--(?:only|root|breite))=(.*)$/.exec(a); return m ? [m[1], m[2]] : [a]; });   // --only=x is --only x
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--verbose' || a === '-v') o.verbose = true;
    else if (a === '--help' || a === '-h') { console.log(USAGE); process.exit(0); }
    else if (a === '--only' || a === '--root' || a === '--breite') {
      const v = argv[++i];
      if (v === undefined) { console.error(`${a} braucht einen Wert.\n${USAGE}`); process.exit(2); }
      if (a === '--root') o.root = v;
      else if (a === '--breite') {
        if (!/^\d{3,4}$/.test(v) || Number(v) < 320) { console.error(`--breite braucht eine Fensterbreite in Pixeln (320 bis 9999), nicht «${v}».\n${USAGE}`); process.exit(2); }
        o.breite = Number(v); VIEWPORT.width = o.breite;
      }
      else for (const n of v.split(',').map(s => s.trim().toLowerCase()).filter(Boolean)) {
        const name = ALIAS[n] || n;
        if (!CHECKS.includes(name)) { console.error(`Unbekannte Prüfung «${n}».\n${USAGE}`); process.exit(2); }
        o.only.add(name);
      }
    } else { console.error(`Unbekannte Option «${a}».\n${USAGE}`); process.exit(2); }
  }
  return o;
}
const OPT = parseArgs(process.argv.slice(2));
const ROOT = path.resolve(OPT.root);
const wanted = name => OPT.only.size === 0 || OPT.only.has(name);

// ---------------------------------------------------------------- results
const findings = new Map(CHECKS.map(c => [c, []]));   // check -> [{text, details}]
const measured = new Map();                           // check -> what was looked at, one line
const notes = new Map(CHECKS.map(c => [c, []]));      // check -> lines shown with --verbose
const fail = (check, text, details = []) => findings.get(check).push({ text, details });
const note = (check, line) => notes.get(check).push(line);
const nf = n => Number(n).toLocaleString('de-CH');
const clean = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
const pl = (n, one, many) => `${nf(n)} ${n === 1 ? one : many}`;
const cut = (s, n) => { s = clean(s); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ---------------------------------------------------------------- Chrome
function findChrome() {
  const env = process.env.CHROME || process.env.CHROME_PATH;
  const isFile = p => { try { return fs.statSync(p).isFile(); } catch { return false; } };
  if (env) return isFile(env) ? env : null;
  const c = [];
  if (process.platform === 'darwin') {
    for (const base of ['/Applications', path.join(os.homedir(), 'Applications')])
      for (const app of ['Google Chrome', 'Chromium', 'Microsoft Edge']) c.push(`${base}/${app}.app/Contents/MacOS/${app}`);
  } else if (process.platform === 'win32') {
    for (const base of [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean))
      c.push(path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe'), path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'));
  } else {
    for (const dir of (process.env.PATH || '').split(path.delimiter).filter(Boolean))
      for (const n of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge']) c.push(path.join(dir, n));
  }
  return c.find(isFile) || null;
}

class LaunchError extends Error {}

// One headless Chrome with one tab, spoken to over --remote-debugging-pipe:
// JSON messages, each ended by a NUL byte, written to fd 3 and read from fd 4.
async function launchChrome(chrome) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'citygov-seitenpruefung-'));
  const args = ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--disable-background-networking', '--disable-component-update', '--disable-sync', '--mute-audio',
    '--host-resolver-rules=MAP * ~NOTFOUND',   // no name resolves: the pages are checked without the network
    `--window-size=${VIEWPORT.width},${VIEWPORT.height}`, `--user-data-dir=${profile}`,
    ...(process.env.CHROME_FLAGS || '').split(/\s+/).filter(Boolean), '--remote-debugging-pipe', 'about:blank'];
  const proc = spawn(chrome, args, { stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'] });
  let dead = null; let seq = 0; const pending = new Map(); const waiters = []; let chunks = [];
  const die = why => { if (dead) return; dead = why; for (const p of pending.values()) p.reject(new Error(why)); pending.clear(); };
  proc.on('error', e => die(`Chrome liess sich nicht starten (${e.code || e.message})`));
  proc.on('exit', code => die(`Chrome hat sich beendet (Code ${code})`));
  proc.stdio[3].on('error', () => {});
  const b = { errors: [], requests: [] };
  const here = pathToFileURL(ROOT).href + '/';
  const short = t => clean(String(t).split(here).join('')).slice(0, 300);
  const onEvent = m => {
    for (let i = waiters.length - 1; i >= 0; i--) if (waiters[i].method === m.method) waiters.splice(i, 1)[0].resolve(m.params);
    const p = m.params || {};
    if (m.method === 'Inspector.targetCrashed') die('die Seite ist im Browser abgestürzt');
    else if (m.method === 'Runtime.exceptionThrown') b.errors.push(short(p.exceptionDetails.exception?.description || p.exceptionDetails.text));
    else if (m.method === 'Runtime.consoleAPICalled' && (p.type === 'error' || p.type === 'assert'))
      b.errors.push(short('console.error: ' + p.args.map(a => a.value ?? a.description ?? '').join(' ')));
    else if (m.method === 'Log.entryAdded' && p.entry.level === 'error') b.errors.push(short(p.entry.text + (p.entry.url ? ' — ' + p.entry.url : '')));
    else if (m.method === 'Network.requestWillBeSent' && /^(https?|wss?|ftp):/i.test(p.request.url)) b.requests.push(p.request.url.slice(0, 200));
  };
  proc.stdio[4].on('data', chunk => {
    let from = 0;
    for (let i = chunk.indexOf(0); i >= 0; i = chunk.indexOf(0, from)) {
      chunks.push(chunk.subarray(from, i)); from = i + 1;
      const m = JSON.parse(Buffer.concat(chunks).toString('utf8')); chunks = [];
      if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result); }
      else if (m.method) onEvent(m);
    }
    if (from < chunk.length) chunks.push(chunk.subarray(from));
  });
  const raw = (method, params, sessionId) => new Promise((resolve, reject) => {
    if (dead) { reject(new Error(dead)); return; }
    const id = ++seq; pending.set(id, { resolve, reject });
    proc.stdio[3].write(JSON.stringify({ id, method, params: params || {}, ...(sessionId ? { sessionId } : {}) }) + '\0');
  });
  let session;
  try {
    const silent = setTimeout(() => die('Chrome antwortet nicht'), 30000);
    const { targetId } = await raw('Target.createTarget', { url: 'about:blank' });
    session = (await raw('Target.attachToTarget', { targetId, flatten: true })).sessionId;
    clearTimeout(silent);
  } catch (e) {
    try { proc.kill('SIGKILL'); } catch {}
    fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
    throw new LaunchError(e.message);
  }
  b.send = (method, params) => raw(method, params, session);
  b.event = (method, ms) => new Promise((resolve, reject) => {
    const w = { method, resolve }; waiters.push(w);
    setTimeout(() => { const i = waiters.indexOf(w); if (i >= 0) { waiters.splice(i, 1); reject(new Error(`${method} blieb aus`)); } }, ms).unref();
  });
  // the value of an expression in the page (promises are awaited); an exception there is thrown here
  b.ev = async expression => {
    const r = await b.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(clean(r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result.value;
  };
  // open a local file and wait until it has loaded and been painted once
  b.open = async file => {
    const loaded = b.event('Page.loadEventFired', 60000);
    loaded.catch(() => {});
    await b.send('Page.navigate', { url: pathToFileURL(file).href });
    await loaded;
    await b.ev('__cp.drawn()');
  };
  b.close = async () => {
    if (!dead) await new Promise(done => {       // ask it to quit, wait at most three seconds
      const t = setTimeout(done, 3000);
      proc.once('exit', () => { clearTimeout(t); done(); });
      raw('Browser.close').catch(() => {});
    });
    try { proc.kill('SIGKILL'); } catch {}
    try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }); } catch {}
  };
  process.on('exit', () => { try { proc.kill('SIGKILL'); } catch {} try { fs.rmSync(profile, { recursive: true, force: true }); } catch {} });
  for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => process.exit(130));
  await b.send('Page.enable'); await b.send('Runtime.enable'); await b.send('Log.enable'); await b.send('Network.enable');
  await b.send('Emulation.setDeviceMetricsOverride', { ...VIEWPORT, deviceScaleFactor: 1, mobile: false });
  await b.send('Emulation.setEmulatedMedia', { media: 'screen', features: [{ name: 'prefers-color-scheme', value: 'light' }, { name: 'prefers-reduced-motion', value: 'reduce' }] });
  await b.send('Page.addScriptToEvaluateOnNewDocument', { source: `(${pageLib})();` });
  return b;
}

// ---------------------------------------------------------------- inside the page
// This function runs IN THE PAGE, before the page's own scripts (it is sent as source
// text, so it must not use anything from this file). It leaves one global, __cp.
function pageLib() {
  // which elements get a click listener through addEventListener (el.onclick is visible anyway)
  const clickTargets = new WeakSet();
  const nativeAdd = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (type === 'click' && listener && this && this.nodeType === 1) clickTargets.add(this);
    return nativeAdd.call(this, type, listener, options);
  };

  const clean = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const name = el => {
    const cls = typeof el.className === 'string' ? el.className : (el.className && el.className.baseVal) || '';
    const c = cls.trim().split(/\s+/).filter(Boolean).slice(0, 2);
    return el.tagName.toLowerCase() + (c.length ? '.' + c.join('.') : '');
  };
  const sel = el => (el.parentElement && el.parentElement !== document.body ? name(el.parentElement) + ' > ' : '') + name(el);
  const mainEl = () => document.getElementById('main') || document.querySelector('main') || document.body;
  // the dashboard draws its pages into #main; header, navigation and legend around it are the «frame»
  const zone = el => !document.getElementById('main') || el.closest('#main') ? 'main' : 'frame';

  // rendered at all (not display:none, not visibility:hidden, not inside a closed <details>)
  const shown = el => el.checkVisibility
    ? el.checkVisibility({ visibilityProperty: true, checkVisibilityCSS: true })
    : el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  // inside a box that shows nothing: the «visually hidden» pattern, a collapsed panel
  let clipMemo = new WeakMap();
  const clippedAway = el => {
    if (!el || el === document.documentElement) return false;
    let v = clipMemo.get(el);
    if (v === undefined) {
      const cs = getComputedStyle(el), r = el.getBoundingClientRect();
      v = ((r.width <= 1 || r.height <= 1) && cs.display !== 'inline' && (cs.overflowX !== 'visible' || cs.overflowY !== 'visible'))
        || ((cs.position === 'absolute' || cs.position === 'fixed') && cs.clip !== 'auto')
        || /inset\(\s*(50|100)%/.test(cs.clipPath)
        || clippedAway(el.parentElement);
      clipMemo.set(el, v);
    }
    return v;
  };

  // ---- colours: what is painted under a text, and the text on top of it
  const parseColor = s => {
    let m = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,/]\s*([\d.]+)(%?))?\s*\)$/.exec(s);
    if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : (m[5] ? m[4] / 100 : +m[4])];
    m = /^color\(srgb\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)(?:\s*\/\s*([\d.]+)(%?))?\s*\)$/.exec(s);
    if (m) return [m[1] * 255, m[2] * 255, m[3] * 255, m[4] === undefined ? 1 : (m[5] ? m[4] / 100 : +m[4])];
    return null;
  };
  const over = (top, bot) => {               // «source over», colours with alpha, not premultiplied
    const a = top[3] + bot[3] * (1 - top[3]);
    if (a <= 0) return [0, 0, 0, 0];
    return [0, 1, 2].map(i => (top[i] * top[3] + bot[i] * bot[3] * (1 - top[3])) / a).concat(a);
  };
  const lum = c => {
    const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const hex = c => '#' + [0, 1, 2].map(i => Math.round(c[i]).toString(16).padStart(2, '0')).join('').toUpperCase();
  let layerMemo = new WeakMap();
  const layer = el => {
    let l = layerMemo.get(el);
    if (!l) { const cs = getComputedStyle(el); l = { bg: parseColor(cs.backgroundColor), img: cs.backgroundImage !== 'none', op: parseFloat(cs.opacity) }; layerMemo.set(el, l); }
    return l;
  };
  // what the chain of elements from i downwards paints onto a clear sheet; an element with
  // opacity is painted with everything inside it first and made transparent as a whole
  const paint = (chain, i, text) => {
    const l = layer(chain[i]);
    let sheet = l.bg || [0, 0, 0, 0];
    if (i + 1 < chain.length) sheet = over(paint(chain, i + 1, text), sheet);
    else if (text) sheet = over(text, sheet);
    return l.op < 1 ? [sheet[0], sheet[1], sheet[2], sheet[3] * l.op] : sheet;
  };
  const WHITE = [255, 255, 255, 1];
  const colours = (el, cs) => {
    const chain = []; for (let x = el; x && x.nodeType === 1; x = x.parentElement) chain.unshift(x);
    // a picture or gradient between the text and the first solid colour: not computable
    let op = 1;
    for (let i = chain.length - 1; i >= 0; i--) {
      const l = layer(chain[i]); op *= l.op;
      if (l.img || !l.bg) return null;
      if (l.bg[3] >= 1 && op >= 1) break;
    }
    const fg = parseColor(cs.webkitTextFillColor || cs.color) || parseColor(cs.color);
    if (!fg) return null;
    const under = over(paint(chain, 0, null), WHITE), text = over(paint(chain, 0, fg), WHITE);
    return { fg: hex(text), bg: hex(under), ratio: ratio(text, under) };
  };
  // how much of an element is left after its own and its ancestors' opacity
  let opMemo = new WeakMap();
  const opacity = el => {
    if (!el || el.nodeType !== 1) return 1;
    let v = opMemo.get(el);
    if (v === undefined) { v = layer(el).op * opacity(el.parentElement); opMemo.set(el, v); }
    return v;
  };

  // ---- every visible text node: size and contrast, grouped
  const text = cfg => {
    const out = { nodes: 0, chars: 0, low: [], small: [], lowNodes: 0, lowChars: 0, smallNodes: 0, smallChars: 0, undetermined: 0, inSvg: 0 };
    const low = new Map(), small = new Map(), perEl = new Map();
    clipMemo = new WeakMap(); layerMemo = new WeakMap(); opMemo = new WeakMap();   // styles change from page to page
    const range = document.createRange(), sx = window.scrollX, sy = window.scrollY;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n; (n = walker.nextNode());) {
      const t = n.nodeValue.trim(); if (!t) continue;
      const el = n.parentElement;
      if (!el || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|TITLE|OPTION)$/i.test(el.tagName)) continue;
      let m = perEl.get(el);
      if (!m) {
        m = { hidden: !shown(el) || clippedAway(el) || opacity(el) < 0.05 };
        const cs = m.hidden ? null : getComputedStyle(el), ink = cs && parseColor(cs.webkitTextFillColor || cs.color);
        if (ink && ink[3] < 0.05) m.hidden = true;                      // transparent text is not text to read
        if (!m.hidden) {
          const svg = !!el.closest('svg');
          let px = parseFloat(cs.fontSize);
          if (svg && el.getScreenCTM) { const k = el.getScreenCTM(); if (k) px *= Math.hypot(k.a, k.b); }   // an SVG scales its text with its width
          m.px = Math.round(px * 10) / 10; m.svg = svg;
          m.large = px >= 24 || (px >= 18.66 && (parseInt(cs.fontWeight, 10) || 400) >= 700);
          m.sel = sel(el); m.zone = zone(el);
          m.off = !!el.closest(':disabled, [aria-disabled="true"]');
          m.exempt = !!(cfg.exempt && el.closest(cfg.exempt));
          m.col = svg || !cfg.contrast || m.off ? null : colours(el, cs);
        }
        perEl.set(el, m);
      }
      if (m.hidden) continue;
      range.selectNodeContents(n);
      let seen = false;
      for (const r of range.getClientRects()) if (r.width > 0.5 && r.height > 0.5 && r.right + sx > 0 && r.bottom + sy > 0) { seen = true; break; }
      if (!seen) continue;
      out.nodes++; out.chars += t.length;
      if (m.px < cfg.floor - 0.05 && !m.exempt) {
        out.smallNodes++; out.smallChars += t.length;
        const k = m.zone + '|' + m.sel + '|' + m.px;
        let g = small.get(k); if (!g) small.set(k, g = { zone: m.zone, sel: m.sel, px: m.px, n: 0, chars: 0, sample: t.slice(0, 60) });
        g.n++; g.chars += t.length;
      }
      if (!cfg.contrast) continue;
      if (m.svg) { out.inSvg++; continue; }
      if (m.off) continue;
      if (!m.col) { out.undetermined++; continue; }
      const need = m.large ? cfg.large : cfg.normal;
      if (m.col.ratio < need) {
        out.lowNodes++; out.lowChars += t.length;
        const k = m.zone + '|' + m.col.fg + '|' + m.col.bg + '|' + need;
        let g = low.get(k); if (!g) low.set(k, g = { zone: m.zone, fg: m.col.fg, bg: m.col.bg, need, ratio: m.col.ratio, n: 0, chars: 0, minPx: m.px, maxPx: m.px, sels: {}, sample: t.slice(0, 60) });
        g.n++; g.chars += t.length; g.ratio = Math.min(g.ratio, m.col.ratio); g.minPx = Math.min(g.minPx, m.px); g.maxPx = Math.max(g.maxPx, m.px);
        g.sels[m.sel] = (g.sels[m.sel] || 0) + 1;
      }
    }
    out.low = [...low.values()]; out.small = [...small.values()];
    return out;
  };

  // ---- bars: the segments, the legend under the bar, the totals the card states
  const num = s => { const d = String(s).replace(/[^0-9]/g, ''); return d ? Number(d) : null; };
  const N = "[0-9][0-9'’]*";
  const stated = s => {                       // «8'167 von 11'914 …» -> [8167, 11914]; «3'543» -> [3543]; «69 %» -> []
    const out = [], t = clean(s);
    const lead = new RegExp('^(' + N + ')(?!\\s*%)(?![0-9.,])').exec(t); if (lead) out.push(num(lead[1]));
    const von = new RegExp('\\bvon\\s+(' + N + ')').exec(t); if (von) out.push(num(von[1]));
    return out;
  };
  const bars = () => [...mainEl().querySelectorAll('.tbar, .minibar')].map(bar => {
    const o = { kind: bar.classList.contains('tbar') ? 'tbar' : 'minibar', label: clean(bar.getAttribute('aria-label')), card: '',
      bar: [...bar.children].map(i => Number(i.style.flexGrow) || 0), legend: null, parts: null, totals: [] };
    if (o.kind === 'tbar') {
      const ul = bar.nextElementSibling;
      if (ul && ul.classList.contains('tleg')) o.legend = [...ul.children].map(li => { const b = li.querySelector(':scope > b'); return b ? num(b.textContent) : null; });
      const card = bar.closest('.kz, .card');
      if (card) {
        const l = card.querySelector('.kzl'); if (l) o.card = clean(l.textContent);
        card.querySelectorAll('.kzv, .kzsub').forEach(e => o.totals.push(...stated(e.textContent)));
      }
    } else {
      const p = bar.parentElement, row = bar.closest('tr');
      o.card = clean(row && row.cells[0] ? row.cells[0].innerText.split('\n')[0] : '').slice(0, 60);
      const von = new RegExp('\\bvon\\s+(' + N + ')').exec((p && p.getAttribute('title')) || ''); if (von) o.totals.push(num(von[1]));
      const frac = new RegExp('(' + N + ')\\s*/\\s*(' + N + ')').exec(clean(p && p.textContent)); if (frac) o.totals.push(num(frac[2]));
      const list = /:\s*(.+)$/.exec(o.label);           // «…: geklärt 795, Dienststelle handelt 3, …»
      if (list) { const ns = (list[1].match(new RegExp(N, 'g')) || []).map(num); if (ns.length) o.parts = ns; }
    }
    return o;
  });

  // ---- lists that state their total (.sumbox): its numbers .sumn add up to its one .sumtot; a
  // .sumbox inside another counts for itself; a box with several columns (a table) pairs its
  // numbers and totals by data-s — each column adds up to its own total
  const sums = () => [...mainEl().querySelectorAll('.sumbox')].flatMap(box => {
    const own = e => e.closest('.sumbox') === box, col = e => e.dataset.s || '';
    const tot = [...box.querySelectorAll('.sumtot')].filter(own), parts = [...box.querySelectorAll('.sumn')].filter(own);
    const sec = box.closest('section'), cap = box.querySelector('.gcap, caption, .kzl') || (sec && sec.querySelector('h4')) || box;
    const cols = [...new Set([...tot, ...parts].map(col))];
    return (cols.length ? cols : ['']).map(s => {
      const t = tot.filter(e => col(e) === s);
      return { label: clean(cap.textContent).slice(0, 90 - (s ? s.length + 3 : 0)) + (s ? ` [${s}]` : ''), nTot: t.length,
        total: t.length === 1 ? num(t[0].textContent) : null, parts: parts.filter(e => col(e) === s).map(e => num(e.textContent)) };
    });
  });

  // ---- open: true — every folded part opened, every «weitere …» / «alle … zeigen» pressed (a
  // pressed button may bring new folded parts: a few rounds)
  const unfold = () => {
    const m = mainEl(); let n = 0;
    for (let i = 0; i < 6; i++) {
      const d = [...m.querySelectorAll('details:not([open])')], bt = [...m.querySelectorAll('button[data-showmore], button[data-gx][aria-expanded="false"]')];
      if (!d.length && !bt.length) break;
      d.forEach(x => { x.open = true; }); bt.forEach(x => x.click()); n += d.length + bt.length;
    }
    return n;
  };

  // ---- links in the browser's default colour. A link without a colour rule is blue and
  // turns purple once visited; the computed style always reports the unvisited colour.
  const links = () => {
    const bad = new Map(); let n = 0;
    document.querySelectorAll('a[href]').forEach(a => {
      n++; const c = getComputedStyle(a).color;
      if (c !== 'rgb(0, 0, 238)' && c !== 'rgb(85, 26, 139)') return;
      const z = zone(a), k = z + '|' + sel(a);
      let g = bad.get(k); if (!g) bad.set(k, g = { zone: z, sel: sel(a), n: 0, sample: clean(a.textContent).slice(0, 50) });
      g.n++;
    });
    return { n, bad: [...bad.values()] };
  };

  // ---- click targets a keyboard cannot reach. Fine: a native control, tabindex 0 or more,
  // or an element that holds such a thing (a table row whose link carries the action).
  const tabStop = el => /^\s*\d+\s*$/.test(el.getAttribute('tabindex') || '');
  const reachable = el => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'a' || tag === 'area') return el.hasAttribute('href') || tabStop(el);
    if (/^(button|input|select|textarea|summary|option)$/.test(tag)) return true;
    if (tag === 'label' && el.control) return true;
    return tabStop(el) || el.isContentEditable
      || !!el.querySelector('a[href], button, input, select, textarea, summary, [tabindex]:not([tabindex^="-"])');
  };
  const keyboard = () => {
    const bad = new Map(); let n = 0;
    for (const el of document.body.getElementsByTagName('*')) {
      if (typeof el.onclick !== 'function' && !clickTargets.has(el)) continue;
      if (!shown(el)) continue;
      n++; if (reachable(el)) continue;
      const z = zone(el), k = z + '|' + sel(el);
      let g = bad.get(k); if (!g) bad.set(k, g = { zone: z, sel: sel(el), n: 0, sample: clean(el.textContent).slice(0, 50) });
      g.n++;
    }
    return { n, bad: [...bad.values()] };
  };

  // ---- what the page shows
  const info = () => {
    const m = mainEl(), t = m.innerText || '';
    let h = 0; for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) | 0;
    const boot = document.querySelector('.bootmsg.err') || m.querySelector('[role="alert"]');
    const failed = /[^.!?\n]*konnte nicht (gezeichnet|dargestellt|angezeigt|geladen|gestartet) werden[^.!?\n]*/.exec(t);
    // a text the page quotes verbatim from its source ([data-wortlaut]: the remarks of the measurement
    // of a Formular) may name a placeholder it found, such as «undefined» — that is no program word
    let tw = t; for (const e of m.querySelectorAll('[data-wortlaut]')) { const x = e.innerText; if (x) tw = tw.split(x).join(' '); }
    const word = /(^|[^A-Za-zÀ-ÿ])(undefined|NaN|\[object Object\])($|[^A-Za-zÀ-ÿ])/.exec(tw);
    return { hash: location.hash, title: document.title, chars: clean(t).length, sig: h,
      head: clean((m.querySelector('h3.view, h1, h2') || {}).textContent).slice(0, 80),
      boot: clean(boot ? boot.innerText : failed ? failed[0] : '').slice(0, 300), loading: !!document.getElementById('bootmsg'),
      unknown: /Unbekannte Seite/.test(t), nores: [...m.querySelectorAll('.nores')].map(e => clean(e.innerText).slice(0, 140)),
      word: word ? clean(tw.slice(Math.max(0, word.index - 30), word.index + 40)) : '',
      // a data table (two rows or more) without any header cell: no column has a name for a screen
      // reader — folded tables count too (a closed <details> keeps its table in the page)
      nohead: [...m.querySelectorAll('table')].filter(x => x.rows.length >= 2 && !x.querySelector('th') && x.getAttribute('role') !== 'presentation')
        .map(x => clean(((x.className || '') + ' · ' + (x.rows[0] ? x.rows[0].textContent : ''))).slice(0, 90)),
      tabs: [...document.querySelectorAll('aside [data-tab]')].map(b => b.getAttribute('data-tab')) };
  };

  // ---- painted once, and every fade-in or transition at its end state (a text measured
  // half-way through a fade would look paler than it is)
  const drawn = () => new Promise(resolve => requestAnimationFrame(() => setTimeout(() => {
    for (const a of document.getAnimations()) { try { a.finish(); } catch (e) { /* endless animation */ } }
    resolve(true);
  }, 0)));
  // ---- go to a page of the dashboard and come back when it has been drawn
  const go = hash => new Promise(resolve => {
    if (location.hash === hash) { drawn().then(resolve); return; }
    window.addEventListener('hashchange', () => drawn().then(resolve), { once: true });   // the page's own listener runs first
    setTimeout(() => resolve(false), 10000);
    location.hash = hash;
  });

  window.__cp = { text, bars, sums, unfold, links, keyboard, info, go, drawn };
}

// ---------------------------------------------------------------- a. syntax
function inlineScripts(html) {
  const out = [], open = /<script\b([^>]*)>/gi, close = /<\/script\s*>/gi;
  for (let m; (m = open.exec(html));) {
    const start = m.index + m[0].length; close.lastIndex = start;
    const end = close.exec(html);
    out.push({ attrs: m[1], start, code: end ? html.slice(start, end.index) : null });
    if (!end) break;
    open.lastIndex = end.index;
  }
  return out;
}
function lineAt(text, index) {            // the line of the file a position is on
  let line = 1;
  for (let i = text.indexOf('\n'); i >= 0 && i < index; i = text.indexOf('\n', i + 1)) line++;
  return line;
}
function checkSyntax() {
  let nJs = 0, nJson = 0;
  for (const rel of ['dashboard.html', 'flows.html']) {
    const file = path.join(ROOT, rel);
    if (!fs.existsSync(file)) { fail('syntax', `${rel} fehlt`); continue; }
    const html = fs.readFileSync(file, 'utf8');
    inlineScripts(html).forEach((s, i) => {
      const line = lineAt(html, s.start);
      const what = `${rel}, Skript ${i + 1} (ab Zeile ${line})`;
      if (s.code === null) { fail('syntax', `${what}: das schliessende </script> fehlt — die Datei ist abgeschnitten`); return; }
      if (/\bsrc\s*=/i.test(s.attrs)) return;
      const typed = /\btype\s*=\s*["']?([^"'\s>]+)/i.exec(s.attrs), type = typed ? typed[1].toLowerCase() : '';
      if (/json$/.test(type)) {
        nJson++;
        try { JSON.parse(s.code); } catch (e) { fail('syntax', `${what}: die eingebetteten Daten sind kein gültiges JSON — ${e.message}`); }
      } else if (type === 'module') {
        nJs++;
        const tmp = path.join(os.tmpdir(), `citygov-check-${process.pid}-${i}.mjs`);
        fs.writeFileSync(tmp, s.code);
        const r = spawnSync(process.execPath, ['--check', tmp], { encoding: 'utf8' });
        fs.rmSync(tmp, { force: true });
        if (r.status !== 0) fail('syntax', `${what}: ${cut((r.stderr || '').split('\n').filter(l => /Error/.test(l))[0] || 'Syntaxfehler', 200)}`);
      } else if (type === '' || /javascript|ecmascript/.test(type)) {
        nJs++;
        try { new vm.Script(s.code, { filename: rel, lineOffset: line - 1 }); }
        catch (e) {
          const at = /:(\d+)$/.exec(String(e.stack).split('\n')[0]);
          fail('syntax', `${what}: ${e.name}: ${e.message}${at ? ` (Zeile ${at[1]} von ${rel})` : ''}`);
        }
      }
    });
  }
  measured.set('syntax', `${pl(nJs, 'Skript', 'Skripte')} und ${pl(nJson, 'Datenblock', 'Datenblöcke')} in dashboard.html und flows.html`);
}

// ---------------------------------------------------------------- g. size
function checkSize() {
  const file = path.join(ROOT, 'dashboard.html');
  if (!fs.existsSync(file)) { fail('groesse', 'dashboard.html fehlt'); return; }
  const mib = fs.statSync(file).size / 1048576;
  measured.set('groesse', `dashboard.html ${mib.toFixed(1)} MiB` + (mib >= WARN_DASHBOARD_MIB
    ? ` — GitHub warnt beim Hochladen ab ${WARN_DASHBOARD_MIB} MiB, lädt die Datei aber hoch` : '')
    + `; die Grenze liegt bei ${MAX_DASHBOARD_MIB} MiB (GitHub nimmt keine Datei über 100 MB an)`);
  if (mib >= MAX_DASHBOARD_MIB) fail('groesse', `dashboard.html ist ${mib.toFixed(1)} MiB gross — GitHub nimmt keine Datei über 100 MB an; ab ${MAX_DASHBOARD_MIB} MiB bricht die Prüfung ab, bevor das Hochladen scheitert`);
}

// ---------------------------------------------------------------- the walk
// What the browser checks collect, per document: «place» is the page of the dashboard
// (or the file name); the frame of the dashboard (header, navigation, legend) is on
// every page and is counted once, as «Rahmen».
const lowBy = new Map(), smallBy = new Map(), linkBy = new Map(), keyBy = new Map();   // document -> Map(key -> group)
const textStats = { nodes: 0, chars: 0, pages: 0, cNodes: 0, cPages: 0, undetermined: 0, inSvg: 0 };
const barStats = { bars: 0, withTotal: 0, pages: 0 };
const sumStats = { lists: 0 };
const linkStats = { pages: 0 }, keyStats = { pages: 0 }, pageStats = { pages: 0, documents: 0 };
const group = (by, doc, key, init) => {
  let m = by.get(doc); if (!m) by.set(doc, m = new Map());
  let g = m.get(key); if (!g) m.set(key, g = { ...init, places: new Map() });
  return g;
};
const place = (g, where, n) => g.places.set(where, where === 'Rahmen' ? Math.max(g.places.get(where) || 0, n) : (g.places.get(where) || 0) + n);
const total = g => [...g.places.values()].reduce((a, b) => a + b, 0);
const places = g => { const p = [...g.places.keys()]; return p.length > 3 ? p.slice(0, 3).join(', ') + ` und ${p.length - 3} weitere` : p.join(', '); };

async function probe(b, doc, where, contrast) {
  const at = x => x.zone === 'frame' ? 'Rahmen' : where;
  if (wanted('links')) {
    const r = await b.ev('__cp.links()');
    linkStats.pages++;
    for (const x of r.bad) place(group(linkBy, doc, x.sel, x), at(x), x.n);
    note('links', `${doc} · ${where}: ${nf(r.n)} Links, ${nf(r.bad.reduce((a, x) => a + x.n, 0))} in Browser-Blau`);
  }
  if (wanted('tastatur')) {
    const r = await b.ev('__cp.keyboard()');
    keyStats.pages++;
    for (const x of r.bad) place(group(keyBy, doc, x.sel, x), at(x), x.n);
    note('tastatur', `${doc} · ${where}: ${nf(r.n)} klickbare Elemente, ${nf(r.bad.reduce((a, x) => a + x.n, 0))} ohne Tastaturzugang`);
  }
  const withContrast = contrast && wanted('kontrast');
  if (wanted('schrift') || withContrast) {
    const r = await b.ev(`__cp.text(${JSON.stringify({ floor: TEXT_FLOOR_PX, exempt: TEXT_FLOOR_EXEMPT, normal: CONTRAST_NORMAL, large: CONTRAST_LARGE, contrast: withContrast })})`);
    textStats.nodes += r.nodes; textStats.chars += r.chars; textStats.pages++;
    if (wanted('schrift')) {
      for (const x of r.small) place(group(smallBy, doc, x.sel + '|' + x.px, x), at(x), x.n);
      note('schrift', `${doc} · ${where}: ${nf(r.nodes)} Textstellen, ${nf(r.smallNodes)} unter ${TEXT_FLOOR_PX} px (${(100 * r.smallChars / Math.max(1, r.chars)).toFixed(1)} % der Zeichen)`);
    }
    if (withContrast) {
      textStats.cNodes += r.nodes; textStats.cPages++; textStats.undetermined += r.undetermined; textStats.inSvg += r.inSvg;
      for (const x of r.low) {
        const g = group(lowBy, doc, x.fg + '|' + x.bg + '|' + x.need, { ...x, sels: {} });
        place(g, at(x), x.n); g.ratio = Math.min(g.ratio, x.ratio); g.minPx = Math.min(g.minPx, x.minPx); g.maxPx = Math.max(g.maxPx, x.maxPx);
        for (const [s, n] of Object.entries(x.sels)) g.sels[s] = Math.max(g.sels[s] || 0, n);
      }
      note('kontrast', `${doc} · ${where}: ${nf(r.nodes)} Textstellen, ${nf(r.lowNodes)} unter dem Mindestkontrast (${(100 * r.lowChars / Math.max(1, r.chars)).toFixed(1)} % der Zeichen)`
        + (r.undetermined ? `, ${nf(r.undetermined)} auf Bild oder Verlauf nicht berechenbar` : '') + (r.inSvg ? `, ${nf(r.inSvg)} in Grafiken nicht gemessen` : ''));
    }
  }
}

function checkBars(doc, where, bars) {
  const sum = a => a.reduce((x, y) => x + (y || 0), 0);
  let n = 0;
  for (const o of bars) {
    const at = `${doc} · ${where}, ${o.card ? `«${cut(o.card, 60)}»` : `Balken «${cut(o.label, 60)}»`}`;
    const b = sum(o.bar);
    barStats.bars++; n++;
    if (o.kind === 'tbar') {
      if (!o.legend) { fail('summen', `${at}: unter dem Balken fehlt die Legende mit den Zahlen`); continue; }
      const l = sum(o.legend);
      if (b !== l) fail('summen', `${at}: der Balken zeigt ${nf(b)}, seine Legende ergibt ${nf(l)}`, [`Balken ${o.bar.map(nf).join(' + ')} · Legende ${o.legend.map(v => v == null ? '?' : nf(v)).join(' + ')}`]);
      if (o.totals.length) {
        barStats.withTotal++;
        if (!o.totals.includes(l)) {
          const t = Math.max(...o.totals);
          fail('summen', `${at}: die Legende ergibt ${nf(l)}, die Karte nennt ${nf(t)} — ${l < t ? `es fehlen ${nf(t - l)}` : `${nf(l - t)} zu viel`}`, [`Legende ${o.legend.map(v => v == null ? '?' : nf(v)).join(' + ')} = ${nf(l)}`]);
        }
      } else if (o.card) fail('summen', `${at}: die Karte nennt kein Total, mit dem sich der Balken vergleichen lässt`);
    } else {
      if (o.totals.length || o.parts) barStats.withTotal++;
      if (o.totals.length && !o.totals.includes(b)) fail('summen', `${at}: der Balken zeigt ${nf(b)}, daneben steht ${o.totals.map(nf).join(' bzw. ')}`, [`Balken ${o.bar.map(nf).join(' + ')}`]);
      if (o.parts && (sum(o.parts) !== b || o.parts.filter(v => v > 0).join() !== o.bar.filter(v => v > 0).join()))
        fail('summen', `${at}: der Balken zeigt ${o.bar.map(nf).join(' + ')}, seine Beschriftung nennt ${o.parts.map(nf).join(', ')}`);
    }
  }
  if (n) barStats.pages++;
  note('summen', `${doc} · ${where}: ${nf(n)} Balken`);
}

function checkSums(doc, where, boxes) {
  for (const o of boxes) {
    const at = `${doc} · ${where}, Liste «${cut(o.label, 60)}»`;
    sumStats.lists++;
    if (o.nTot !== 1) { fail('summen', `${at}: ${o.nTot ? `nennt ${o.nTot} Totale` : 'nennt kein Total'}, mit dem sich ihre Zahlen vergleichen lassen`); continue; }
    if (!o.parts.length) { fail('summen', `${at}: hat keine Zahlen, die sich zum Total ${nf(o.total)} zusammenzählen lassen`); continue; }
    const s = o.parts.reduce((x, y) => x + (y || 0), 0);
    if (s !== o.total) fail('summen', `${at}: die Zahlen ergeben ${nf(s)}, das Total nennt ${nf(o.total)} — ${s < o.total ? `es fehlen ${nf(o.total - s)}` : `${nf(s - o.total)} zu viel`}`, [`${o.parts.map(nf).join(' + ')} = ${nf(s)}`]);
  }
  if (boxes.length) note('summen', `${doc} · ${where}: ${nf(boxes.length)} Listen mit Total`);
}

function checkPage(doc, where, info, minText, errors, requests) {
  const at = `${doc} · ${where}`, why = [];
  if (info.boot) why.push(`zeigt eine Fehlermeldung: ${cut(info.boot, 200)}`);
  else if (info.loading) why.push('die Seite zeigt noch «wird geladen»');
  if (info.unknown) why.push('zeigt «Unbekannte Seite»');
  for (const t of info.nores) if (/unbekannt|nicht gefunden|nicht dargestellt/i.test(t) && !/Unbekannte Seite/.test(t)) why.push(`meldet: ${cut(t, 110)}`);
  if (info.chars < minText) why.push(`zeigt nur ${nf(info.chars)} Zeichen Text (mindestens ${nf(minText)})`);
  if (info.word) why.push(`im Text steht ein Programmwort: «${cut(info.word, 70)}»`);
  for (const t of (info.nohead || []).slice(0, 3)) why.push(`eine Tabelle ohne Spaltenkopf (th): «${cut(t, 90)}»`);
  for (const e of [...new Set(errors)].slice(0, 3)) why.push(`Fehler in der Konsole: ${cut(e, 220)}`);
  if (errors.length > 3) why.push(`… und ${errors.length - 3} weitere Fehler in der Konsole`);
  for (const u of [...new Set(requests)].slice(0, 3)) why.push(`Anfrage an einen fremden Server: ${u}`);
  for (const w of why) fail('seiten', `${at}: ${w}`);
  note('seiten', `${at}: ${nf(info.chars)} Zeichen, «${info.head}»${why.length ? '' : ' — in Ordnung'}`);
}

async function walkDashboard(b) {
  const doc = 'dashboard.html', file = path.join(ROOT, doc);
  if (!fs.existsSync(file)) { if (wanted('seiten')) fail('seiten', `${doc} fehlt`); return 'die Datei fehlt'; }
  await b.open(file);
  let started = await b.ev('window.__cgStarted === true');
  if (!started) {     // give the page's own failure message time to appear (it waits three seconds)
    let why = '';
    for (let i = 0; i < 45 && !why && !started; i++) { await sleep(100); why = await b.ev(`(document.querySelector('.bootmsg.err') || {}).innerText || ''`); started = await b.ev('window.__cgStarted === true'); }
    if (!started) {
      const tech = /Technische Meldung:\s*(.+)$/.exec(clean(why));      // the page's own message ends with the cause
      if (wanted('seiten')) fail('seiten', `${doc} startet nicht${why ? ': ' + cut(tech ? tech[1] : why, 300) : ''}`, [...new Set(b.errors)].slice(0, 3).map(e => `Fehler in der Konsole: ${cut(e, 220)}`));
      return 'die Seite startet nicht';
    }
  }
  const listed = new Set(PAGES.map(p => p.route.split('/')[0]));
  let before = null, tabs = [];
  for (const p of PAGES) {
    // the console is read after the measurements of a page and emptied then: what the start
    // wrote counts for the first page, and a late message is never lost
    const drawn = await b.ev(`__cp.go(${JSON.stringify('#' + p.route)})`);
    const info = await b.ev('__cp.info()');
    tabs = info.tabs;
    if (p.open) { const n = await b.ev('__cp.unfold()'); await sleep(150); note('seiten', `${doc} · ${p.route}: ${nf(n)} gefaltete Teile geöffnet`); }
    if (wanted('summen')) { checkBars(doc, p.route, await b.ev('__cp.bars()')); checkSums(doc, p.route, await b.ev('__cp.sums()')); }
    await probe(b, doc, p.route, !!p.contrast);
    if (wanted('seiten')) {
      pageStats.pages++;
      checkPage(doc, p.route, info, p.minText || MIN_TEXT, b.errors, b.requests);
      if (!drawn) fail('seiten', `${doc} · ${p.route}: die Seite hat auf den Wechsel der Adresse nicht reagiert`);
      else if (info.hash !== '#' + p.route) fail('seiten', `${doc} · ${p.route}: die Adresse wurde zu «${info.hash}» umgeschrieben — die Seite gibt es so nicht (mehr)`);
      if (before !== null && info.sig === before) fail('seiten', `${doc} · ${p.route}: zeigt denselben Inhalt wie die Seite davor — die Ansicht wurde nicht gezeichnet`);
    }
    before = info.hash === '#' + p.route ? info.sig : null;      // a rewritten address is reported once, not twice
    b.errors.length = 0; b.requests.length = 0;
  }
  if (wanted('seiten')) for (const t of [...new Set(tabs)]) if (!listed.has(t))
    fail('seiten', `${doc}: die Navigation bietet die Seite «${t}» an, sie fehlt in der Liste PAGES von scripts/check_pages.mjs`);
  return '';
}

function dossierBySize(which) {
  const dir = path.join(ROOT, 'dossiers');
  let files = [];
  try { files = fs.readdirSync(dir).filter(f => f.endsWith('.html') && f !== 'index.html').map(f => ({ f, size: fs.statSync(path.join(dir, f)).size })); } catch {}
  files.sort((x, y) => x.size - y.size || x.f.localeCompare(y.f));
  if (!files.length) return null;
  return 'dossiers/' + (which === 'largest' ? files[files.length - 1] : files[0]).f;
}

async function walkDocuments(b) {
  const opened = new Set();
  for (const d of DOCUMENTS) {
    const rel = d.file || dossierBySize(d.dossier);
    if (!rel || !fs.existsSync(path.join(ROOT, rel))) { if (wanted('seiten')) fail('seiten', `${rel || 'dossiers/: ein Dossier'} fehlt`); continue; }
    if (opened.has(rel)) continue;      // a single dossier is the largest and the smallest
    opened.add(rel);
    b.errors.length = 0; b.requests.length = 0;
    await b.open(path.join(ROOT, rel));
    const info = await b.ev('__cp.info()');
    if (wanted('summen')) checkBars(rel, 'ganze Seite', await b.ev('__cp.bars()'));
    await probe(b, rel, 'ganze Seite', !!d.contrast);
    if (wanted('seiten')) { pageStats.documents++; checkPage(rel, 'ganze Seite', info, d.minText || MIN_TEXT, b.errors, b.requests); }
  }
}

// ---------------------------------------------------------------- findings of the walk
function reportWalk() {
  const rows = (list, line) => { const all = list.map(line); return OPT.verbose || all.length <= SHOWN ? all : all.slice(0, SHOWN).concat(`… und ${all.length - SHOWN} weitere (alle mit --verbose)`); };
  if (wanted('summen')) measured.set('summen', `${nf(barStats.bars)} Balken auf ${barStats.pages} Seiten, ${nf(barStats.withTotal)} davon mit einem genannten Total; ${nf(sumStats.lists)} Listen mit Total`);
  if (wanted('kontrast')) {
    measured.set('kontrast', `${nf(textStats.cNodes)} Textstellen auf ${textStats.cPages} Seiten gegen ihren Hintergrund gemessen`
      + (textStats.inSvg ? `; ${nf(textStats.inSvg)} in Grafiken nicht gemessen` : '') + (textStats.undetermined ? `; ${nf(textStats.undetermined)} auf Bild oder Verlauf nicht berechenbar` : ''));
    for (const [doc, m] of lowBy) {
      const list = [...m.values()].sort((x, y) => x.ratio - y.ratio);
      fail('kontrast', `${doc}: ${nf(list.length)} Farbpaare unter dem Mindestkontrast, ${nf(list.reduce((a, g) => a + total(g), 0))} Textstellen — das schwächste hat ${list[0].ratio.toFixed(2)}:1`,
        rows(list, g => `${g.ratio.toFixed(2)}:1 statt ${g.need}:1 · ${g.fg} auf ${g.bg} · ${g.minPx === g.maxPx ? g.minPx : g.minPx + '–' + g.maxPx} px · ${pl(total(g), 'Stelle', 'Stellen')} · ${places(g)} · `
          + Object.entries(g.sels).sort((x, y) => y[1] - x[1]).slice(0, OPT.verbose ? 8 : 2).map(([s]) => s).join(' | ') + ` · «${cut(g.sample, 40)}»`));
    }
  }
  if (wanted('schrift')) {
    measured.set('schrift', `${nf(textStats.nodes)} Textstellen auf ${textStats.pages} Seiten gemessen, Untergrenze ${TEXT_FLOOR_PX} px`);
    for (const [doc, m] of smallBy) {
      const list = [...m.values()].sort((x, y) => x.px - y.px || total(y) - total(x));
      const sizes = new Map(); for (const g of list) sizes.set(g.px, (sizes.get(g.px) || 0) + total(g));
      fail('schrift', `${doc}: Text unter ${TEXT_FLOOR_PX} px an ${nf(list.reduce((a, g) => a + total(g), 0))} Stellen (${nf(list.length)} Arten) — die kleinste Schrift misst ${list[0].px} px`,
        [`nach Grösse: ${[...sizes].map(([px, n]) => `${px} px ${nf(n)}×`).join(' · ')}`]
          .concat(rows(list, g => `${g.px} px · ${g.sel} · ${pl(total(g), 'Stelle', 'Stellen')} · ${places(g)} · «${cut(g.sample, 40)}»`)));
    }
  }
  if (wanted('links')) {
    measured.set('links', `die Links von ${linkStats.pages} Seiten` + (linkBy.size ? '' : ': keiner in der Standardfarbe des Browsers'));
    for (const [doc, m] of linkBy) {
      const list = [...m.values()].sort((x, y) => total(y) - total(x));
      fail('links', `${doc}: ${nf(list.reduce((a, g) => a + total(g), 0))} Links in der Standardfarbe des Browsers (blau, nach dem Besuch violett) — ihnen fehlt eine Farbregel`,
        rows(list, g => `${g.sel} · ${pl(total(g), 'Link', 'Links')} · ${places(g)} · «${cut(g.sample, 40)}»`));
    }
  }
  if (wanted('tastatur')) {
    measured.set('tastatur', `die klickbaren Elemente von ${keyStats.pages} Seiten` + (keyBy.size ? '' : ': alle mit der Tabulatortaste erreichbar'));
    for (const [doc, m] of keyBy) {
      const list = [...m.values()].sort((x, y) => total(y) - total(x));
      fail('tastatur', `${doc}: ${nf(list.reduce((a, g) => a + total(g), 0))} klickbare Elemente sind mit der Tastatur nicht erreichbar (kein Schalter, kein Link, kein tabindex)`,
        rows(list, g => `${g.sel} · ${pl(total(g), 'Element', 'Elemente')} · ${places(g)} · «${cut(g.sample, 40)}»`));
    }
  }
  if (wanted('seiten')) measured.set('seiten', `${pageStats.pages} Seiten des Dashboards und ${pageStats.documents} weitere Dokumente geöffnet` + (findings.get('seiten').length ? '' : ', kein Fehler in der Konsole'));
}

// ---------------------------------------------------------------- run
const t0 = Date.now();
if (process.env.CHECK_PAGES === 'skip') { console.log('Seitenprüfung übersprungen: CHECK_PAGES=skip'); process.exit(0); }
const chrome = findChrome();
if (!chrome || Number(process.versions.node.split('.')[0]) < 16) { console.log(SKIPPED); process.exit(0); }
setTimeout(() => { console.error(`Seitenprüfung abgebrochen: nach ${TIME_LIMIT_S} Sekunden nicht fertig.`); process.exit(1); }, TIME_LIMIT_S * 1000).unref();

if (wanted('syntax')) checkSyntax();
if (wanted('groesse')) checkSize();
if (CHECKS.some(c => NEEDS_BROWSER.has(c) && wanted(c))) {
  let b;
  try { b = await launchChrome(chrome); }
  catch (e) {
    if (!(e instanceof LaunchError)) throw e;
    // a Chrome that is there but does not start is a finding, not a skip: no page was checked
    console.error(`Seitenprüfung fehlgeschlagen: ${e.message} — ${chrome} wurde gefunden, startet aber nicht`
      + ' (im Container: CHROME_FLAGS=--no-sandbox; bewusst ohne Prüfung bauen: CHECK_PAGES=skip).');
    process.exit(1);
  }
  try {
    const broken = await walkDashboard(b);
    if (broken) for (const c of CHECKS) if (NEEDS_BROWSER.has(c) && c !== 'seiten' && wanted(c)) fail(c, `dashboard.html nicht prüfbar: ${broken}` + (wanted('seiten') ? '' : ' (Einzelheiten mit --only seiten)'));
    await walkDocuments(b);
  } catch (e) {
    fail(CHECKS.find(c => NEEDS_BROWSER.has(c) && wanted(c)), `Die Prüfung im Browser ist abgebrochen: ${e.message}`);
  } finally { await b.close(); }
  reportWalk();
}

let failed = 0;
for (const c of CHECKS) {
  if (!wanted(c)) continue;
  const f = findings.get(c);
  if (f.length) failed++;
  console.log(`${f.length ? 'FEHLER' : 'ok    '}  ${c.padEnd(9)} ${f.length ? `${f.length} ${f.length === 1 ? 'Befund' : 'Befunde'}` : measured.get(c) || ''}`);
  for (const x of f) { console.log(`    - ${x.text}`); for (const d of x.details) console.log(`        ${d}`); }
  if (OPT.verbose) { if (f.length && measured.get(c)) console.log(`    gemessen: ${measured.get(c)}`); for (const l of notes.get(c)) console.log(`    · ${l}`); }
}
const n = CHECKS.filter(wanted).length, secs = ((Date.now() - t0) / 1000).toFixed(1);
const fenster = OPT.breite ? `, Fenster ${VIEWPORT.width} px` : '';
console.log(failed ? `Seitenprüfung: ${n === 1 ? 'die Prüfung hat Befunde' : `${failed} von ${n} Prüfungen mit Befund`} (${secs} s${fenster}) — Einzelheiten mit --verbose, eine Prüfung allein mit --only <name>`
  : `Seitenprüfung: ${n === 1 ? 'die Prüfung' : `alle ${n} Prüfungen`} bestanden (${secs} s${fenster})`);
// let the output drain when it goes into a pipe, then end — also if something is still open
process.exitCode = failed ? 1 : 0;
setTimeout(() => process.exit(failed ? 1 : 0), 2000).unref();
