/* Buscador del topbar (2026-10-05). Indice 100% local (js/search-data.js,
   lo genera pipeline/build_search_index.py), coincidencia tolerante a errores
   de tipeo, sinonimos EN/ES y vista previa del resultado activo. Lo carga
   js/site-chrome.js recien cuando alguien abre el buscador. Patron de
   accesibilidad: dialogo modal + combobox con listbox (aria-activedescendant). */
(function () {
  'use strict';
  var DATA_URL = /*DATA_URL*/'/js/search-data.js?v=b887a114'/*ENDDATA_URL*/;
  var ES = document.documentElement.lang === 'es';
  var LOCALE = ES ? 'es-ES' : 'en-US';
  // 2026-10-19: 'es-ES' leaves 4-digit numbers ungrouped ("1234") while the /es/ pages group them ("1.295").
  // Browsers without useGrouping: 'always' read it as true and keep their default grouping.
  var NUM_OPTS = ES ? { useGrouping: 'always' } : undefined;
  function num(v) { return v.toLocaleString(LOCALE, NUM_OPTS); }
  var T = ES ? {
    dialog: 'Buscar en el sitio', placeholder: 'Busca plugins, extensiones y páginas…', close: 'Cerrar el buscador',
    results: 'Resultados', popular: 'Más usados', pages: 'Páginas', none: 'Sin resultados para «%s».',
    noneHint: 'Prueba con una palabra más corta o explora el catálogo.', browse: 'Explorar el catálogo →',
    open: 'Abrir la página →', market: 'Marketplace ↗', count: '%s resultados', one: '1 resultado',
    hint: '↑↓ para moverte · Enter para abrir · Esc para cerrar', loading: 'Cargando…',
    downloads: '%s descargas', installs: '%s instalaciones',
    type: { p: 'Plugin para JetBrains', v: 'Extensión para VS Code', g: 'Página', c: 'Caso de estudio', k: 'Ticket de JetBrains' },
    price: { FREE: 'Gratis', FREEMIUM: 'Freemium', PAID: 'De pago' }, catalog: '/es/catalogo/'
  } : {
    dialog: 'Search the site', placeholder: 'Search plugins, extensions and pages…', close: 'Close search',
    results: 'Results', popular: 'Most used', pages: 'Pages', none: 'No matches for “%s”.',
    noneHint: 'Try a shorter word, or browse the catalog.', browse: 'Browse the catalog →',
    open: 'Open page →', market: 'Marketplace ↗', count: '%s results', one: '1 result',
    hint: '↑↓ to move · Enter to open · Esc to close', loading: 'Loading…',
    downloads: '%s downloads', installs: '%s installs',
    type: { p: 'JetBrains plugin', v: 'VS Code extension', g: 'Page', c: 'Case study', k: 'JetBrains ticket' },
    price: { FREE: 'Free', FREEMIUM: 'Freemium', PAID: 'Paid' }, catalog: '/catalog/'
  };
  var MAX_RESULTS = 8;

  // ---- texto -----------------------------------------------------------
  function norm(s) {
    return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, ' ').trim();
  }
  function words(s) { return s ? s.split(' ') : []; }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmt(tpl, v) { return tpl.replace('%s', v); }
  function pick(v) { return v && typeof v === 'object' ? (ES ? v.es || v.en : v.en) : v; }

  // Grupos de sinonimos (EN/ES, siglas y variantes): cualquier termino del
  // grupo encuentra a los demas.
  var SYN_GROUPS = [
    ['k8s', 'kubernetes', 'kube'], ['js', 'javascript', 'node', 'nodejs', 'npm'], ['ts', 'typescript'],
    ['db', 'database', 'databases', 'sql', 'jdbc', 'bd', 'datos'], ['secret', 'secrets', 'credential', 'credentials',
    'secreto', 'secretos', 'credenciales', 'password', 'passwords'], ['vuln', 'vulnerability', 'vulnerabilities', 'cve',
    'vulnerabilidad', 'vulnerabilidades'], ['ci', 'cicd', 'pipeline', 'pipelines', 'actions', 'workflow', 'workflows'],
    ['docker', 'dockerfile', 'container', 'containers', 'contenedor'], ['security', 'seguridad', 'secure', 'segura', 'seguro'],
    ['test', 'tests', 'testing', 'prueba', 'pruebas', 'junit'], ['api', 'apis', 'rest', 'openapi', 'swagger'],
    ['log', 'logs', 'logging', 'logger'], ['performance', 'perf', 'rendimiento', 'slow', 'lento'],
    ['free', 'gratis', 'gratuito', 'gratuita'], ['paid', 'pago', 'pro', 'premium'], ['cloud', 'nube', 'aws', 'gcp', 's3'],
    ['injection', 'inyeccion', 'injections'], ['leak', 'leaks', 'fuga', 'fugas'], ['freeze', 'freezes', 'hang',
    'congelamiento', 'bloqueo'], ['jwt', 'token', 'tokens', 'oauth', 'auth'], ['regex', 'regexp', 'regular'],
    ['kafka', 'messaging', 'mensajeria', 'rabbitmq'], ['terraform', 'iac', 'hcl'], ['git', 'vcs', 'commit', 'commits'],
    ['case', 'caso', 'casos', 'study', 'estudio'], ['ticket', 'tickets', 'youtrack', 'bug', 'bugs', 'error', 'errores'],
    ['plugin', 'plugins', 'extension', 'extensions', 'extension', 'extensiones'], ['vscode', 'code'],
    ['jetbrains', 'intellij', 'idea', 'pycharm', 'webstorm'], ['kotlin', 'kt'], ['python', 'py'],
    ['privacy', 'privacidad', 'telemetry', 'telemetria'], ['contact', 'contacto', 'hire', 'contratar']
  ];
  var SYN = {};
  SYN_GROUPS.forEach(function (g) {
    g.forEach(function (w) { SYN[w] = (SYN[w] || []).concat(g.filter(function (x) { return x !== w; })); });
  });
  var PRICE_WORDS = { free: 'FREE', gratis: 'FREE', gratuito: 'FREE', freemium: 'FREEMIUM', paid: 'PAID', pago: 'PAID', pro: 'PAID' };
  var PLATFORM_WORDS = { vscode: 'v', jetbrains: 'p', intellij: 'p' };

  // Distancia de edicion con transposiciones ("ansibel" -> "ansible" = 1).
  function editDistance(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var pp = null, prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i];
      var best = i;
      for (j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        if (pp && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) cur[j] = Math.min(cur[j], pp[j - 2] + 1);
        if (cur[j] < best) best = cur[j];
      }
      if (best > max) return max + 1;
      pp = prev;
      prev = cur;
    }
    return prev[b.length];
  }

  // Puntaje de un termino contra un campo (palabras + texto completo).
  function fieldScore(variants, ws, full, w) {
    var best = 0;
    for (var v = 0; v < variants.length; v++) {
      var q = variants[v], syn = v > 0 ? 0.85 : 1, s = 0;
      if (ws.indexOf(q) !== -1) s = w[0];
      else if (q.length >= 2 && ws.some(function (x) { return x.indexOf(q) === 0; })) s = w[1];
      // fragmento dentro de otra palabra: solo el termino original y desde 4 letras
      // (un sinonimo como "hang" no debe encontrar "changelog")
      else if (v === 0 && q.length >= 4 && full.indexOf(q) !== -1) s = w[2];
      else if (q.length >= 4 && v === 0) {
        var max = q.length >= 8 ? 2 : 1;
        if (ws.some(function (x) { return x.length >= 3 && editDistance(q, x.slice(0, q.length + max), max) <= max; })) s = w[3];
      }
      if (s * syn > best) best = s * syn;
    }
    return best;
  }

  // ---- indice ----------------------------------------------------------
  var INDEX = null;
  function urlFor(it) {
    if (it.t === 'p' || it.t === 'v') return ES ? '/es/catalogo/' + it.u.slice('/catalog/'.length) : it.u;
    return pick(it.u);
  }
  function buildIndex(data) {
    return data.items.map(function (it) {
      var name = pick(it.n), cat = pick(it.c), desc = pick(it.d);
      var tags = [it.k, cat, it.t === 'v' ? 'vscode extension' : it.t === 'p' ? 'jetbrains plugin intellij' : '',
                  it.pr ? T.price[it.pr] + ' ' + it.pr : '', it.t === 'k' ? pick(it.st) + ' ticket' : '',
                  it.t === 'c' ? 'case study caso estudio' : ''].join(' ');
      var nName = norm(name), nSlug = norm(it.s || ''), nTags = norm(tags), nDesc = norm(desc);
      return { it: it, name: name, desc: desc, cat: cat, url: urlFor(it),
               f: { name: [words(nName), nName], slug: [words(nSlug), nSlug], tags: [words(nTags), nTags], desc: [words(nDesc), nDesc] },
               pop: Math.log(1 + (it.dl || 0)) / Math.LN10 };
    });
  }

  function search(query) {
    var qn = norm(query), terms = words(qn);
    var priceFilter = null, platformFilter = null, rest = [];
    terms.forEach(function (t) {
      if (PRICE_WORDS[t] && terms.length > 1) priceFilter = PRICE_WORDS[t];
      else if (PLATFORM_WORDS[t] && terms.length > 1) platformFilter = PLATFORM_WORDS[t];
      else rest.push(t);
    });
    var scored = [];
    INDEX.forEach(function (d) {
      var it = d.it;
      if (priceFilter && it.pr !== priceFilter) return;
      if (platformFilter && it.t !== platformFilter) return;
      var total = 0, matched = 0;
      rest.forEach(function (t) {
        var variants = [t].concat(SYN[t] || []);
        var s = Math.max(fieldScore(variants, d.f.name[0], d.f.name[1], [12, 9, 6, 5]),
                         fieldScore(variants, d.f.slug[0], d.f.slug[1], [9, 7, 5, 4]))
          + 0.8 * fieldScore(variants, d.f.tags[0], d.f.tags[1], [5, 4, 3, 2])
          + 0.5 * fieldScore(variants, d.f.desc[0], d.f.desc[1], [2, 1.5, 1, 0.7]);
        if (s > 0) { matched++; total += s; }
      });
      if (!rest.length) total = 1;
      if (!total) return;
      var all = !rest.length || matched === rest.length;
      var boost = it.t === 'g' ? 1.15 : it.t === 'c' || it.t === 'k' ? 0.9 : 1;
      scored.push({ d: d, score: (all ? total : total * 0.35) * boost + d.pop * 0.6, all: all });
    });
    var strict = scored.filter(function (s) { return s.all; });
    var list = (strict.length ? strict : scored).sort(function (a, b) { return b.score - a.score; });
    return { items: list.slice(0, MAX_RESULTS).map(function (s) { return s.d; }), total: list.length, terms: rest };
  }

  function suggestions() {
    var plugins = INDEX.filter(function (d) { return d.it.t === 'p' || d.it.t === 'v'; })
      .sort(function (a, b) { return (b.it.dl || 0) - (a.it.dl || 0); }).slice(0, 5);
    var pages = INDEX.filter(function (d) { return d.it.t === 'g' && d.url !== (ES ? '/es/' : '/'); }).slice(0, 3);
    return plugins.concat(pages);
  }

  // 2026-10-27: busca sobre el texto ORIGINAL y escapa cada tramo por separado. Antes buscaba sobre el texto ya
  // escapado: escribir "am" o "amp" partia el "&amp;" de "JetBrains & VS Code" en "&<mark>amp</mark>;" y se leia
  // "&amp;" literal; y como aplicaba un termino tras otro, un termino como "ar" podia caer dentro de un "<mark>"
  // anterior. Una sola pasada, con el termino mas largo primero, evita ambas cosas.
  function highlight(text, terms) {
    var src = String(text == null ? '' : text);
    var ts = terms.filter(function (t) { return t.length >= 2; }).sort(function (a, b) { return b.length - a.length; });
    if (!ts.length) return esc(src);
    var rx = new RegExp('(' + ts.map(function (t) { return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|') + ')', 'ig');
    var out = '', last = 0, m;
    while ((m = rx.exec(src)) !== null) {
      out += esc(src.slice(last, m.index)) + '<mark>' + esc(m[0]) + '</mark>';
      last = m.index + m[0].length;
    }
    return out + esc(src.slice(last));
  }

  // ---- interfaz --------------------------------------------------------
  var root, input, list, preview, status, results = [], active = -1, opener = null, lastQuery = '';
  var ICON = '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M12.6 12.6 17 17"/></svg>';

  function build() {
    root = document.createElement('div');
    root.className = 'ghs-backdrop';
    root.hidden = true;
    root.innerHTML =
      '<div class="ghs-dialog" role="dialog" aria-modal="true" aria-label="' + esc(T.dialog) + '">' +
        '<div class="ghs-bar">' + ICON +
          '<input class="ghs-input" id="ghsInput" type="search" role="combobox" aria-autocomplete="list" aria-expanded="true"' +
          ' aria-controls="ghsList" autocomplete="off" spellcheck="false" placeholder="' + esc(T.placeholder) + '">' +
          '<button type="button" class="ghs-close" aria-label="' + esc(T.close) + '">Esc</button>' +
        '</div>' +
        '<div class="ghs-body">' +
          '<ul class="ghs-list" id="ghsList" role="listbox" aria-label="' + esc(T.results) + '"></ul>' +
          '<div class="ghs-preview" aria-live="polite"></div>' +
        '</div>' +
        '<div class="ghs-foot"><span class="ghs-hint">' + esc(T.hint) + '</span><span class="ghs-status" role="status"></span></div>' +
      '</div>';
    document.body.appendChild(root);
    input = root.querySelector('.ghs-input');
    list = root.querySelector('.ghs-list');
    preview = root.querySelector('.ghs-preview');
    status = root.querySelector('.ghs-status');

    var timer;
    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () { render(input.value); }, 60);
    });
    input.addEventListener('keydown', onKey);
    root.querySelector('.ghs-close').addEventListener('click', close);
    root.addEventListener('mousedown', function (e) { if (e.target === root) close(); });
    root.addEventListener('keydown', trapFocus);
    list.addEventListener('mousemove', function (e) {
      var li = e.target.closest('.ghs-item');
      if (li && +li.getAttribute('data-i') !== active) setActive(+li.getAttribute('data-i'));
    });
    list.addEventListener('click', function (e) {
      var li = e.target.closest('.ghs-item');
      if (li) go(+li.getAttribute('data-i'), e.ctrlKey || e.metaKey);
    });
  }

  function itemHtml(d, i, terms) {
    var it = d.it;
    var meta = it.t === 'p' || it.t === 'v'
      ? esc(it.k) + (it.pr ? ' · ' + esc(T.price[it.pr]) : '')
      : esc(String(pick(it.d) == null ? '' : pick(it.d)).slice(0, 110));   // recortar ANTES de escapar: no parte una entidad
    var idx = Number(i) || 0;
    return '<li class="ghs-item ghs-t-' + esc(it.t) + '" id="ghs-opt-' + idx + '" role="option" aria-selected="false" data-i="' + idx + '">' +
      '<span class="ghs-kind">' + esc(T.type[it.t]) + '</span>' +
      '<span class="ghs-name">' + highlight(d.name, terms) + '</span>' +
      '<span class="ghs-meta">' + meta + '</span></li>';
  }

  function render(query) {
    lastQuery = query;
    var q = query.trim(), terms = [];
    if (!q) {
      results = suggestions();
      status.textContent = T.popular;
    } else {
      var r = search(q);
      results = r.items;
      terms = r.terms;
      status.textContent = r.total === 1 ? T.one : fmt(T.count, num(r.total));
    }
    if (!results.length) {
      list.innerHTML = '<li class="ghs-empty" role="presentation"><p>' + esc(fmt(T.none, q)) + '</p><p>' + esc(T.noneHint) +
        '</p><a href="' + T.catalog + '">' + esc(T.browse) + '</a></li>';
      preview.innerHTML = '';
      active = -1;
      input.removeAttribute('aria-activedescendant');
      return;
    }
    list.innerHTML = results.map(function (d, i) { return itemHtml(d, i, terms); }).join('');
    setActive(0);
  }

  function setActive(i) {
    if (!results.length) return;
    active = (i + results.length) % results.length;
    Array.prototype.forEach.call(list.children, function (li, k) {
      var on = k === active;
      li.setAttribute('aria-selected', on ? 'true' : 'false');
      li.classList.toggle('is-active', on);
      if (on && li.scrollIntoView) li.scrollIntoView({ block: 'nearest' });
    });
    input.setAttribute('aria-activedescendant', 'ghs-opt-' + active);
    showPreview(results[active]);
  }

  function showPreview(d) {
    var it = d.it, h = [];
    h.push('<p class="ghs-p-kind">' + esc(T.type[it.t]) + (it.t === 'k' && pick(it.st) ? ' · ' + esc(pick(it.st)) : '') + '</p>');
    h.push('<h3 class="ghs-p-name">' + esc(d.name) + '</h3>');
    if (it.t === 'p' || it.t === 'v') {
      h.push('<p class="ghs-p-chips"><span>' + esc(d.cat) + '</span>' + (it.pr ? '<span class="ghs-price ghs-price-' + esc(it.pr.toLowerCase()) + '">' +
        esc(T.price[it.pr]) + '</span>' : '') + '</p>');
      if (it.k) h.push('<p class="ghs-p-niche">' + esc(it.k) + '</p>');
      h.push('<p class="ghs-p-stat">' + esc(fmt(it.t === 'v' ? T.installs : T.downloads, num(it.dl || 0))) + '</p>');
    }
    h.push('<p class="ghs-p-desc">' + esc(d.desc) + '</p>');
    h.push('<p class="ghs-p-actions"><a class="ghs-btn ghs-btn-primary" href="' + esc(d.url) + '">' + esc(T.open) + '</a>' +
      (it.m ? '<a class="ghs-btn" href="' + esc(it.m) + '" target="_blank" rel="noopener">' + esc(T.market) + '</a>' : '') + '</p>');
    preview.innerHTML = h.join('');
  }

  function go(i, newTab) {
    var d = results[i];
    if (!d) return;
    if (newTab) window.open(d.url, '_blank', 'noopener');
    else location.href = d.url;
  }

  function onKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1); }
    else if (e.key === 'Enter') { e.preventDefault(); go(active, e.ctrlKey || e.metaKey); }
    else if (e.key === 'Escape') { e.preventDefault(); close(); }
  }

  function trapFocus(e) {
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key !== 'Tab') return;
    var f = Array.prototype.filter.call(root.querySelectorAll('input, button, a[href]'), function (el) { return el.offsetParent !== null; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  function open(trigger) {
    opener = trigger || document.activeElement;
    if (!root) build();
    root.hidden = false;
    document.documentElement.classList.add('ghs-open');
    document.querySelectorAll('[data-search-open]').forEach(function (b) { b.setAttribute('aria-expanded', 'true'); });
    input.value = lastQuery;
    if (INDEX) render(lastQuery); else { status.textContent = T.loading; list.innerHTML = ''; }
    input.focus();
    input.select();
  }

  function close() {
    if (!root || root.hidden) return;
    root.hidden = true;
    document.documentElement.classList.remove('ghs-open');
    document.querySelectorAll('[data-search-open]').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
    if (opener && opener.focus) opener.focus();
  }

  function loadData(cb) {
    if (window.GHL_SEARCH) { cb(window.GHL_SEARCH); return; }
    var s = document.createElement('script');
    s.src = DATA_URL;
    s.async = true;
    s.onload = function () { cb(window.GHL_SEARCH); };
    document.head.appendChild(s);
  }

  window.GHLSearch = {
    open: function (trigger) {
      open(trigger);
      if (!INDEX) loadData(function (data) {
        if (!data) return;
        INDEX = buildIndex(data);
        if (!root.hidden) render(input.value);
      });
    }
  };
})();
