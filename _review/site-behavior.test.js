/* Behaviour tests for the static site, driven over the Chrome DevTools Protocol (no Playwright needed).

   Needs Node 22+ and any Chromium-based browser. The browser is found in this order:
   BROWSER_PATH, Edge, Chrome, then the Chromium that Playwright downloaded. The script starts its own
   static server and, for the unreachable-data test, blocks /data/*.json from the browser side (an instant
   failure, the one that reaches a script before the code that consumes it has attached), so nothing has to be running.

     node _review/site-behavior.test.js

   Exit code 1 if any test fails. A lighter, faster set than verify_site.py (which uses Playwright and
   covers more): this one is meant for machines that only have Node and a browser. */
const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
const net = require('net');
const { spawn } = require('child_process');

const root = path.resolve(__dirname, '..');
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const PAGE_SIZE = 15;

// ------------------------------------------------------------------------------------ servers
function makeServer() {
  return http.createServer((request, response) => {
    const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    let file = path.resolve(root, pathname.replace(/^\//, ''));
    if (file.startsWith(root) && fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
    if (!file.startsWith(root) || !fs.existsSync(file)) {
      response.writeHead(404);
      response.end('Not found');
      return;
    }
    const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.png': 'image/png', '.woff2': 'font/woff2', '.xml': 'application/xml', '.txt': 'text/plain' };
    response.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(response);
  });
}
const listen = (server) => new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));
const freePort = () => new Promise((resolve) => {
  const s = net.createServer();
  s.listen(0, '127.0.0.1', () => { const { port } = s.address(); s.close(() => resolve(port)); });
});

// ------------------------------------------------------------------------------------ browser
function findBrowser() {
  const candidates = [
    process.env.BROWSER_PATH,
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  ].filter(Boolean);
  for (const c of candidates) if (fs.existsSync(c)) return c;
  const pw = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), '.cache'), process.env.LOCALAPPDATA ? 'ms-playwright' : 'ms-playwright');
  if (fs.existsSync(pw)) {
    const dirs = fs.readdirSync(pw).filter((d) => d.startsWith('chromium-')).sort().reverse();
    for (const d of dirs) {
      for (const rel of ['chrome-win64\\chrome.exe', 'chrome-win\\chrome.exe', 'chrome-linux/chrome', 'chrome-mac/Chromium.app/Contents/MacOS/Chromium']) {
        const f = path.join(pw, d, rel);
        if (fs.existsSync(f)) return f;
      }
    }
  }
  throw new Error('No Chromium-based browser found. Set BROWSER_PATH to msedge.exe, chrome.exe or a Chromium binary.');
}

async function openBrowser() {
  const exe = findBrowser();
  const port = await freePort();
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ghl-browser-'));
  const proc = spawn(exe, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=' + port, '--user-data-dir=' + profile, 'about:blank'], { stdio: 'ignore' });
  proc.on('error', (error) => { throw error; });
  let targets;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const r = await fetch('http://127.0.0.1:' + port + '/json/list');
      targets = await r.json();
      if (targets.length) break;
    } catch {}
    await delay(100);
  }
  const target = targets && (targets.find((t) => t.type === 'page' && t.url === 'about:blank') || targets.find((t) => t.type === 'page'));
  if (!target) throw new Error('Browser debugging target unavailable (' + exe + ')');
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let sequence = 0;
  const pending = new Map();
  const exceptions = [];
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') {
      const d = message.params.exceptionDetails;
      exceptions.push(((d.exception && d.exception.description) || d.text || 'exception').split('\n')[0].slice(0, 160));
    }
    if (!message.id || !pending.has(message.id)) return;
    const handlers = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) handlers.reject(new Error(message.error.message));
    else handlers.resolve(message.result);
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  await send('Runtime.enable');
  await send('Page.enable');
  const evaluate = async (expression) => {
    const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error((result.exceptionDetails.exception && result.exceptionDetails.exception.description) || result.exceptionDetails.text);
    return result.result.value;
  };
  const waitFor = async (expression, what) => {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      if (await evaluate(expression)) return;
      await delay(100);
    }
    throw new Error('Timed out waiting for ' + (what || expression));
  };
  const navigate = async (url) => {
    exceptions.length = 0;
    await send('Page.navigate', { url });
    await delay(150);
    await waitFor("document.readyState === 'complete'", 'load of ' + url);
    await delay(250);
  };
  const viewport = (width, height, mobile) => send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: !!mobile });
  const close = () => { try { socket.close(); } catch {} proc.kill(); };
  return { send, evaluate, waitFor, navigate, viewport, exceptions, close, exe };
}

// -------------------------------------------------------------------------------------- tests
const tests = [];
const test = (name, fn) => tests.push({ name, fn });
const assert = (cond, message) => { if (!cond) throw new Error(message); };
const equal = (actual, wanted, what) => { if (actual !== wanted) throw new Error(what + ': got ' + JSON.stringify(actual) + ', expected ' + JSON.stringify(wanted)); };
const readData = (file) => JSON.parse(fs.readFileSync(path.join(root, 'data', file), 'utf8'));

const visibleCards = "[...document.querySelectorAll('#catalogGrid > *')].filter(e => !e.hidden)";

test('catalog: 146 prerendered cards, 15 visible, pager moves', async ({ b, base }) => {
  const total = readData('catalog-data.json').totalPlugins;
  await b.viewport(1440, 900);
  await b.navigate(base + '/catalog/');
  equal(await b.evaluate("document.querySelectorAll('#catalogGrid > a.plugin-card').length"), total, 'cards in the page');
  equal(await b.evaluate(visibleCards + '.length'), PAGE_SIZE, 'visible cards');
  assert(/Page 1 of \d+/.test(await b.evaluate("document.querySelector('.catalog-pager-status').textContent")), 'pager text on load');
  await b.evaluate("document.querySelector('[data-page-dir=\"1\"]').click()");
  assert(/Page 2 of \d+/.test(await b.evaluate("document.querySelector('.catalog-pager-status').textContent")), 'pager text after next');
  equal(b.exceptions.length, 0, 'JavaScript exceptions: ' + b.exceptions.join(' | '));
});

test('catalog: search, no-results offer, category URL, pricing URL', async ({ b, base }) => {
  await b.navigate(base + '/catalog/');
  await b.evaluate("(()=>{const i=document.getElementById('searchInput');i.value='Mermaid';i.dispatchEvent(new Event('input',{bubbles:true}))})()");
  await delay(300);
  const names = await b.evaluate(visibleCards + ".map(e => e.querySelector('.card-name').textContent)");
  assert(names.length >= 1 && /Mermaid/.test(names[0]), 'Mermaid search: ' + JSON.stringify(names));
  await b.evaluate("(()=>{const i=document.getElementById('searchInput');i.value='zzzzq';i.dispatchEvent(new Event('input',{bubbles:true}))})()");
  await delay(300);
  const miss = await b.evaluate("(()=>{const e=document.getElementById('fieldNoResults');return {hidden:e.hidden,href:e.querySelector('a.miss-cta')&&e.querySelector('a.miss-cta').getAttribute('href')}})()");
  assert(!miss.hidden && /intent=hire/.test(miss.href) && /need=zzzzq/.test(miss.href), 'no-results offer: ' + JSON.stringify(miss));
  await b.navigate(base + '/catalog/?category=security');
  const sec = await b.evaluate(visibleCards + '.map(e => e.dataset.cat)');
  assert(sec.length > 0 && sec.every((c) => c === 'security'), 'category=security: ' + JSON.stringify(sec));
  await b.navigate(base + '/catalog/?pricing=paid');
  const paid = await b.evaluate(visibleCards + '.map(e => e.dataset.pricing)');
  assert(paid.length > 0 && paid.every((p) => p === 'FREEMIUM' || p === 'PAID'), 'pricing=paid: ' + JSON.stringify(paid));
});

test('catalog: table view sorts by downloads, then by name', async ({ b, base }) => {
  await b.navigate(base + '/catalog/');
  await b.evaluate("document.querySelector('[data-mode=table]').click()");
  await b.waitFor("document.querySelectorAll('#tbody tr.row').length > 0", 'table rows');
  const rows = () => b.evaluate("[...document.querySelectorAll('#tbody tr.row')].filter(r => !r.hidden).map(r => ({d: +r.dataset.downloads, n: r.dataset.name}))");
  const byDownloads = (await rows()).map((r) => r.d);
  assert(byDownloads.length === PAGE_SIZE && JSON.stringify(byDownloads) === JSON.stringify([...byDownloads].sort((x, y) => y - x)), 'downloads should descend: ' + byDownloads);
  await b.evaluate("document.querySelector(\"thead th[data-key='name']\").click()");
  const names = (await rows()).map((r) => r.n);
  const asc = [...names].sort();
  assert(JSON.stringify(names) === JSON.stringify(asc) || JSON.stringify(names) === JSON.stringify(asc.reverse()), 'names should be sorted: ' + names);
});

test('catalog: platform tabs switch panels and keep the VS Code blue', async ({ b, base }) => {
  await b.navigate(base + '/catalog/');
  const color = (plat) => b.evaluate("getComputedStyle(document.querySelector('.platform-tab[data-platform=\"" + plat + "\"] svg')).color");
  assert((await color('jetbrains')) !== 'rgb(0, 122, 204)', 'JetBrains icon must not be the VS Code blue');
  await b.evaluate("document.querySelector('.platform-tab[data-platform=vscode]').click()");
  await delay(300);
  equal(await b.evaluate("document.querySelector('.platform-tab[data-platform=vscode]').getAttribute('aria-selected')"), 'true', 'VS Code tab selected');
  equal(await color('vscode'), 'rgb(0, 122, 204)', 'VS Code icon color');
  equal(await b.evaluate("document.getElementById('vsxSection').hidden"), false, 'VS Code panel shown');
  equal(await b.evaluate("document.getElementById('jetbrains').hidden"), true, 'JetBrains panel hidden');
});

test('catalog and home keep working when /data/*.json is unreachable', async ({ b, base }) => {
  await b.send('Network.enable');
  await b.send('Network.setBlockedURLs', { urls: ['*/data/*.json'] });
  try {
    await unreachableData({ b, base });
  } finally {
    await b.send('Network.setBlockedURLs', { urls: [] });
  }
});

async function unreachableData({ b, base }) {
  await b.navigate(base + '/catalog/');
  await b.evaluate("(()=>{const i=document.getElementById('searchInput');i.value='Mermaid';i.dispatchEvent(new Event('input',{bubbles:true}))})()");
  await delay(300);
  assert((await b.evaluate(visibleCards + '.length')) >= 1, 'search should work without data');
  equal(b.exceptions.length, 0, 'catalog JavaScript exceptions: ' + b.exceptions.join(' | '));
  await b.navigate(base + '/');
  // 2026-11-08: the hire-oriented home of 2026-11-04 shows 3 investigations and 3 selected tools (was 5 and 4).
  equal(await b.evaluate("document.querySelectorAll('article.inv').length"), 3, 'investigations without data');
  equal(await b.evaluate("document.querySelectorAll('article.tool').length"), 3, 'tools without data');
  equal(b.exceptions.length, 0, 'home JavaScript exceptions: ' + b.exceptions.join(' | '));
}

test('home: hero, profile card, figures, investigations, tools, stack', async ({ b, base }) => {
  const data = readData('catalog-data.json');
  await b.viewport(1440, 900);
  await b.navigate(base + '/');
  // 2026-11-08: expectations moved to the hire-oriented home of 2026-11-04 (PR #27): one lede, four service tabs
  // with one real case each, 3 investigations and 3 selected tools. The old method list and focus badges are gone.
  const facts = await b.evaluate("({h1: document.querySelector('h1.nb-hero-title').textContent.trim().length, lede: document.querySelectorAll('.nb-hero .nb-lede').length, img: document.querySelector('.nb-profile img').naturalWidth, tabs: document.querySelectorAll('.nb-states [role=tab]').length, panels: document.querySelectorAll('.nb-panels [role=tabpanel]').length, inv: document.querySelectorAll('article.inv').length, facts: [...document.querySelectorAll('article.inv')].map(a => a.querySelectorAll('dt').length), tools: [...document.querySelectorAll('article.tool')].map(t => t.querySelectorAll('.tool-badges .badge').length), stack: document.querySelectorAll('#stack .badge-table tr').length, stackImgs: document.querySelectorAll('#stack img').length, impact: document.querySelector('.nb-impact').innerText})");
  assert(facts.h1 > 20 && facts.lede === 1 && facts.img > 0 && facts.tabs === 4 && facts.panels === 4, 'hero: ' + JSON.stringify(facts));
  assert(facts.inv === 3 && facts.facts.every((n) => n === 3), 'investigations: ' + JSON.stringify(facts.facts));
  assert(facts.tools.length === 3 && facts.tools.every((n) => n === 2), 'tool badges: ' + JSON.stringify(facts.tools));
  assert(!/Last 7 days/.test(facts.impact) && /\+[\d,]+ since \d{4}-\d{2}-\d{2}/.test(facts.impact),
    'the downloads figure must say what the gain is measured from: ' + facts.impact.slice(0, 160));
  assert(facts.stack === 4 && facts.stackImgs === 0, 'stack rows ' + facts.stack + ', images ' + facts.stackImgs);
  assert(facts.impact.includes(data.totalDownloads.toLocaleString('en-US')), 'downloads ' + data.totalDownloads + ' not shown in: ' + facts.impact.slice(0, 120));
});

test('Ctrl+K search: open, results, arrow keys, Escape', async ({ b, base }) => {
  await b.viewport(1440, 900);
  await b.navigate(base + '/');
  await b.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'k', ctrlKey: true, bubbles: true}))");
  await b.waitFor("document.querySelector('.ghs-backdrop') && !document.querySelector('.ghs-backdrop').hidden", 'the dialog');
  await b.evaluate("(()=>{const i=document.querySelector('.ghs-input');i.value='openapi';i.dispatchEvent(new Event('input',{bubbles:true}))})()");
  await b.waitFor("document.querySelectorAll('.ghs-item').length >= 2", 'results');
  const first = await b.evaluate("document.querySelector('.ghs-item.is-active .ghs-name').textContent");
  await b.evaluate("document.querySelector('.ghs-input').dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true}))");
  assert((await b.evaluate("document.querySelector('.ghs-item.is-active .ghs-name').textContent")) !== first, 'ArrowDown should move the active result');
  await b.evaluate("document.querySelector('.ghs-input').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))");
  assert(await b.evaluate("document.querySelector('.ghs-backdrop').hidden"), 'Escape should close the dialog');
});

test('contact: each request type has its own form; the counter counts', async ({ b, base }) => {
  await b.navigate(base + '/contact/');
  const titles = new Set();
  const n = await b.evaluate("document.querySelectorAll('.qa-item[data-target]').length");
  assert(n >= 4, 'request types: ' + n);
  for (let i = 0; i < n; i += 1) {
    await b.evaluate("document.querySelectorAll('.qa-item[data-target]')[" + i + "].click()");
    titles.add(await b.evaluate("document.getElementById('cfTitle').textContent"));
    equal(await b.evaluate("document.querySelectorAll('.qa-item.is-active').length"), 1, 'one active type');
  }
  equal(titles.size, n, 'distinct titles');
  await b.evaluate("document.querySelector('.qa-item[data-target=hire]').click()");
  await b.evaluate("(()=>{const t=document.querySelector('#cfFields [name=message]');t.value='hello';t.dispatchEvent(new Event('input',{bubbles:true}))})()");
  assert(/5\s*\/\s*1500/.test(await b.evaluate("document.querySelector('.cf-counter').textContent")), 'counter should read 5/1500');
});

// 2026-11-08: one form per line of business, and the URL parameters that pre-fill them. Unknown or hostile values
// must fall back to a safe default and never become markup.
test('contact: URL parameters pick the form and pre-fill it, and bad values are ignored', async ({ b, base }) => {
  const form = async (query) => {
    await b.navigate(base + '/contact/' + query);
    return b.evaluate("(()=>{const f=n=>{const e=document.querySelector('#cfFields [name='+n+']');return e?e.value:null};" +
      "return {title:document.getElementById('cfTitle').textContent,service:f('service'),plugin:f('plugin'),message:f('message')," +
      "active:[...document.querySelectorAll('.qa-item.is-active')].map(x=>x.dataset.target).join(),injected:!!document.getElementById('pwn')}})()");
  };
  let r = await form('?intent=hire&service=audit');
  equal(r.title, 'Start an engagement', 'hire title');
  equal(r.service, 'Plugin performance audit', 'service=audit pre-selects the audit');
  for (const [key, label] of [['updates', 'Plugin update for new IDE versions'], ['depsec', 'Dependency and CI/CD security review'],
    ['custom', 'Custom plugins and inspections'], ['other', 'Something else']]) {
    equal((await form('?intent=hire&service=' + key)).service, label, 'service=' + key);
  }
  equal((await form('?intent=hire&service=bogus')).service, '', 'an unknown service leaves the choice empty');
  equal((await form('?intent=hire&service=')).service, '', 'an empty service leaves the choice empty');
  r = await form('?intent=hire&plugin=cert-companion');
  equal(r.service, '', 'a plugin page does not pre-select team licenses any more');
  assert(/About the plugin: cert-companion/.test(r.message), 'plugin prefill: ' + r.message);
  r = await form('?intent=license&plugin=openapi-companion');
  equal(r.title, 'Team licenses', 'license title');
  equal(r.plugin, 'openapi-companion', 'license plugin prefill');
  equal(r.active, 'license', 'license quick action active');
  r = await form('?intent=license&plugin=%3Cimg%20id%3Dpwn%20src%3Dx%3E');
  equal(r.plugin, '', 'a malformed slug is ignored');
  assert(!r.injected, 'no markup injected from ?plugin=');
  r = await form('?intent=hire&need=%3Cimg%20id%3Dpwn%20src%3Dx%3E');
  assert(!r.injected, 'no markup injected from ?need=');
  assert(r.message.indexOf('<img') !== -1, 'the search text is kept as plain text');
  equal((await form('?intent=sponsor')).title, 'Company sponsorship', 'sponsor title');
  for (const bad of ['constructor', '__proto__', 'toString', 'HIRE', '']) {
    r = await form('?intent=' + bad);
    equal(r.title, 'Start an engagement', 'intent=' + bad + ' falls back to hire');
    assert(!b.exceptions.length, 'intent=' + bad + ' threw: ' + b.exceptions[0]);
  }
});

test('phone header: the primary action stays visible on one row from 320 to 560 px', async ({ b, base }) => {
  const bad = [];
  for (const w of [320, 360, 390, 430, 560]) {
    await b.viewport(w, 800, true);
    for (const p of ['/', '/services/', '/sponsors/', '/es/', '/es/servicios/']) {
      await b.navigate(base + p);
      const h = await b.evaluate("(()=>{const c=document.querySelector('.gh-header .gh-cta');const r=c.getBoundingClientRect();" +
        "const hd=document.querySelector('.gh-header-inner').getBoundingClientRect();" +
        "const nm=document.querySelector('.gh-brand-name').getBoundingClientRect();" +
        "const tl=document.querySelector('.gh-tools').getBoundingClientRect();" +
        "return {visible:r.width>0&&getComputedStyle(c).display!=='none',right:r.right,top:r.top,headerH:hd.height," +
        "nameW:Math.round(nm.width),nameClear:Math.round(tl.left-nm.right)," +
        "over:document.documentElement.scrollWidth-document.documentElement.clientWidth}})()");
      if (!h.visible) bad.push(w + p + ' CTA hidden');
      if (h.right > w) bad.push(w + p + ' CTA ends at ' + h.right);
      if (h.over > 0) bad.push(w + p + ' overflow +' + h.over);
      if (h.headerH > 72) bad.push(w + p + ' header ' + h.headerH + 'px tall');
      // 2026-11-09: the brand name stays visible on phones (it was hidden below 480px) and clear of the buttons.
      if (h.nameW < 60) bad.push(w + p + ' brand name hidden (' + h.nameW + 'px)');
      if (h.nameClear < 0) bad.push(w + p + ' brand name under the buttons (' + h.nameClear + 'px)');
    }
  }
  await b.viewport(1280, 800, false);
  assert(!bad.length, bad.join('; '));
});

// 2026-11-09: below 480px the search button leaves the header (room for the brand name) and opens from the menu.
test('phone search: from the open menu below 480 px, from the header above; Ctrl+K never targets a hidden button', async ({ b, base }) => {
  const bad = [];
  try {
    for (const [w, p] of [[320, '/'], [390, '/es/'], [479, '/'], [480, '/'], [1280, '/']]) {
      await b.viewport(w, 800, w < 1001);
      await b.navigate(base + p);
      const s = await b.evaluate("(()=>{const shown=el=>!!el&&el.offsetParent!==null&&getComputedStyle(el).display!=='none';" +
        "return {header:shown(document.querySelector('.gh-tools > .gh-search-btn')),menu:shown(document.querySelector('.gh-nav-search'))}})()");
      const phone = w < 480;
      if (s.header === phone) bad.push(w + p + ' header search ' + (s.header ? 'shown' : 'hidden'));
      if (s.menu) bad.push(w + p + ' menu search shown while the menu is closed');
      if (phone) {
        await b.evaluate("document.getElementById('topbarBurger').click()");
        await delay(150);
        const m = await b.evaluate("(()=>{const el=document.querySelector('.gh-nav-search');return {shown:el.offsetParent!==null," +
          "first:document.getElementById('siteNav').firstElementChild===el,label:el.textContent.trim()}})()");
        if (!m.shown) bad.push(w + p + ' menu search hidden in the open menu');
        if (!m.first) bad.push(w + p + ' menu search is not the first item');
        if (!/^(Search plugins and pages|Buscar plugins y páginas)$/.test(m.label)) bad.push(w + p + ' menu search label ' + m.label);
        await b.evaluate("document.querySelector('.gh-nav-search').click()");
      } else {
        await b.evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true}))");
      }
      let opened = false;
      for (let i = 0; i < 30 && !opened; i++) { await delay(100); opened = await b.evaluate("!!document.getElementById('ghsInput')"); }
      if (!opened) { bad.push(w + p + ' search did not open'); continue; }
      const trig = await b.evaluate("document.querySelectorAll('[data-search-open][aria-expanded=\"true\"]').length + ' trigger(s) expanded'");
      // Escape from the focused field, as a keyboard user would; the check below only means something once the
      // search is really closed (a first version sent Escape to document, the dialog stayed open and the
      // focus was still in its visible input, so the test could not fail).
      await b.evaluate("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))");
      await delay(150);
      const back = await b.evaluate("(()=>{const i=document.getElementById('ghsInput');const a=document.activeElement;" +
        "return {closed:!i||i.offsetParent===null,tag:a&&a.tagName,cls:a&&a.className,visible:!!a&&a.offsetParent!==null}})()");
      if (!back.closed) { bad.push(w + p + ' Escape did not close the search'); continue; }
      if (!back.visible) bad.push(w + p + ' focus went back to a hidden element (' + back.tag + ' ' + back.cls + ', ' + trig + ')');
    }
  } finally {
    await b.viewport(1280, 800, false);
  }
  assert(!bad.length, bad.join('; '));
});

// 2026-11-09. Headless Chromium draws no scrollbar, but Chrome on Windows takes about 17 px of the window
// for a classic one while the media queries still see the full window. The pass with "sb" narrows the page by
// 17 px to reproduce that. Wherever the links are shown (no burger), they must be the six labels in order, on one
// row, and at least 8 px clear of the buttons.
test('desktop header: six links in order, on one row, clear of the buttons (EN and ES, with a 17 px scrollbar)', async ({ b, base }) => {
  const LABELS = {
    en: ['Services', 'Evidence', 'Plugins', 'Sponsors', 'Blog', 'Contact'],
    es: ['Servicios', 'Evidencia', 'Herramientas', 'Patrocinio', 'Blog', 'Contacto'],
  };
  const pages = [['/', 'en'], ['/sponsors/', 'en'], ['/es/', 'es'], ['/es/catalogo/', 'es'], ['/es/servicios/', 'es'], ['/es/patrocinadores/', 'es']];
  const bad = [];
  let shownAt = null;
  try {
    for (const w of [961, 1001, 1024, 1280]) {   // 961: the first width with links if the burger ever starts at 960 again
      await b.viewport(w, 800, false);
      for (const [p, lang] of pages) {
        for (const sb of [0, 17]) {
          await b.navigate(base + p);
          const r = await b.evaluate("((sb)=>{if(sb)document.documentElement.style.width='calc(100% - '+sb+'px)';" +
            "const burger=document.querySelector('.gh-burger');if(getComputedStyle(burger).display!=='none')return {burger:true};" +
            "const nav=document.getElementById('siteNav');const items=[...nav.children].filter(el=>el.offsetParent!==null);" +
            "const labels=items.map(el=>((el.matches('a')?el:el.querySelector('button'))||el).textContent.trim());" +
            "const tops=new Set(items.map(el=>Math.round(el.getBoundingClientRect().top)));" +
            "const gap=document.querySelector('.gh-tools').getBoundingClientRect().left-items[items.length-1].getBoundingClientRect().right;" +
            "return {burger:false,labels,rows:tops.size,gap:Math.round(gap)}})(" + sb + ")");
          if (r.burger) continue;
          if (shownAt === null || w < shownAt) shownAt = w;
          const where = w + (sb ? '+sb ' : ' ') + p;
          if (JSON.stringify(r.labels) !== JSON.stringify(LABELS[lang])) bad.push(where + ' labels ' + r.labels.join('|'));
          if (r.rows !== 1) bad.push(where + ' links on ' + r.rows + ' rows');
          if (r.gap < 8) bad.push(where + ' only ' + r.gap + 'px clear of the buttons');
        }
      }
    }
  } finally {
    await b.viewport(1280, 800, false);
  }
  assert(shownAt !== null, 'the header links never showed, even at 1280 px');
  assert(!bad.length, bad.join('; '));
});

test('sponsors: an action above the fold, levels before the empty sponsor wall', async ({ b, base }) => {
  await b.viewport(390, 844, true);
  await b.navigate(base + '/sponsors/');
  let r;
  try {
    r = await b.evaluate("(()=>{const a=document.querySelector('.page-hero .hero-actions a');" +
      "const lvEl=document.getElementById('sec-levels'),nowEl=document.getElementById('sec-now');" +
      "if(!a||!lvEl||!nowEl)return {missing:[!a&&'.page-hero .hero-actions a',!lvEl&&'#sec-levels',!nowEl&&'#sec-now'].filter(Boolean)};" +
      "return {top:a.getBoundingClientRect().top+scrollY,href:a.getAttribute('href')," +
      "levelsFirst:lvEl.getBoundingClientRect().top<nowEl.getBoundingClientRect().top}})()");
  } finally {
    await b.viewport(1280, 800, false);
  }
  assert(!r.missing, 'missing on /sponsors/: ' + (r.missing || []).join(', '));
  assert(r.top < 844, 'first sponsor action at ' + r.top + 'px');
  equal(r.href, '#sec-levels', 'hero action points to the levels');
  assert(r.levelsFirst, 'levels come before the sponsor wall');
});

test('phone (390 px): no horizontal overflow on the main pages; methodology diagram fits', async ({ b, base }) => {
  await b.viewport(390, 844, true);
  const pages = ['/', '/es/', '/catalog/', '/es/catalogo/', '/catalog/openapi-companion/', '/services/', '/engineering-evidence/',
    '/engineering-evidence/jetbrains-platform-tickets/', '/contact/', '/security/', '/methodology/'];
  const bad = [];
  for (const p of pages) {
    await b.navigate(base + p);
    const over = await b.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth');
    if (over > 0) bad.push(p + ' (+' + over + 'px)');
    if (b.exceptions.length) bad.push(p + ' threw: ' + b.exceptions[0]);
  }
  assert(!bad.length, bad.join('; '));
  await b.navigate(base + '/methodology/');
  const w = await b.evaluate("document.querySelector('.decision-diagram').getBoundingClientRect().width");
  assert(w > 0 && w <= 390, 'diagram width ' + w);
});

const pressKey = async (b, key, code, keyCode) => {
  await b.send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode });
  await b.send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode });
};

// 2026-11-09: two stacked headings put the catalog search at y = 864 on a 390 x 844 phone.
test('catalog on a phone: search and filters in the first screen, before the panel heading, for the keyboard too', async ({ b, base }) => {
  const measure = "(()=>{const p=[...document.querySelectorAll('.platform-panel')].find(x=>!x.hidden);" +
    "const c=p.querySelector(':scope > .controls'),h=p.querySelector(':scope > .cv-head'),pw=p.getBoundingClientRect().width;" +
    "return {panel:p.id,controlsTop:c.getBoundingClientRect().top+scrollY,controlsBottom:c.getBoundingClientRect().bottom+scrollY," +
    "headTop:h.getBoundingClientRect().top+scrollY," +
    "narrow:[...p.children].filter(k=>getComputedStyle(k).display!=='none'&&k.getBoundingClientRect().height>0&&" +
    "Math.abs(k.getBoundingClientRect().width-pw)>1).map(k=>k.className||k.id)," +
    "over:document.documentElement.scrollWidth-document.documentElement.clientWidth}})()";
  // Tab from the selected tab until the focus is inside the open panel; report where it landed first.
  const firstFocusInPanel = async () => {
    await b.evaluate("document.querySelector('.platform-tab[aria-selected=\"true\"]').focus()");
    for (let i = 0; i < 4; i += 1) {
      await pressKey(b, 'Tab', 'Tab', 9);
      const at = await b.evaluate("(()=>{const a=document.activeElement,p=[...document.querySelectorAll('.platform-panel')].find(x=>!x.hidden);" +
        "if(!p.contains(a)||a===p)return null;return a.closest('.controls')?'controls':a.closest('.cv-head')?'heading':(a.className||a.tagName)})()");
      if (at) return at;
    }
    return 'never entered the panel';
  };
  try {
    await b.viewport(390, 844, true);
    for (const page of ['/catalog/', '/es/catalogo/']) {
      await b.navigate(base + page);
      for (const platform of ['jetbrains', 'vscode']) {
        if (platform === 'vscode') {
          await b.evaluate("document.querySelector('.platform-tab[data-platform=vscode]').click()");
          await delay(300);
        }
        const r = await b.evaluate(measure);
        const where = page + ' ' + r.panel;
        assert(r.controlsTop < r.headTop, where + ': controls at ' + r.controlsTop + ', heading at ' + r.headTop);
        assert(r.controlsBottom <= 844, where + ': controls end at y = ' + r.controlsBottom);
        equal(r.narrow.join(','), '', where + ': children narrower than the panel');
        equal(r.over, 0, where + ': horizontal overflow');
        equal(await firstFocusInPanel(), 'controls', where + ': first focus inside the panel');
      }
    }
    await b.viewport(1280, 800, false);
    await b.navigate(base + '/catalog/');
    const wide = await b.evaluate(measure);
    assert(wide.headTop < wide.controlsTop, 'desktop keeps the heading above the controls');
    equal(await firstFocusInPanel(), 'heading', 'desktop focus order is the markup order');
  } finally {
    await b.viewport(1280, 800, false);
  }
});

// -------------------------------------------------------------------------------------- runner
async function run() {
  const server = makeServer();
  const base = 'http://127.0.0.1:' + (await listen(server));
  let b;
  const results = [];
  try {
    b = await openBrowser();
    console.log('site: ' + base + ' | browser: ' + path.basename(b.exe) + ' | tests: ' + tests.length);
    const only = process.env.ONLY; // optional: run only the tests whose name contains this text
    for (const t of tests) {
      if (only && !t.name.includes(only)) continue;
      const started = Date.now();
      try {
        await t.fn({ b, base });
        results.push({ name: t.name, ok: true });
        console.log('PASS  ' + t.name + ' (' + ((Date.now() - started) / 1000).toFixed(1) + 's)');
      } catch (error) {
        results.push({ name: t.name, ok: false });
        console.log('FAIL  ' + t.name + '\n      ' + String(error.message || error).split('\n')[0]);
      }
    }
  } finally {
    if (b) b.close();
    server.close();
  }
  const failed = results.filter((r) => !r.ok).length;
  console.log('\n' + results.length + ' tests: ' + (results.length - failed) + ' passed, ' + failed + ' failed');
  process.exitCode = failed ? 1 : 0;
}

run().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
  setTimeout(() => process.exit(1), 200);
});
