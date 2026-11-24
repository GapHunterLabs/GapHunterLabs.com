/* Catalogo: filtra (oculta), ordena (reordena nodos) y pagina el HTML ya pre-renderizado; tambien el topbar y el modo Field/Table.
   Movido desde un <script> inline el 2026-09-24 para poder quitar
   'unsafe-inline' del script-src de la CSP (ver DOCUMENTATION.md). */
(function () {
  'use strict';
  // Fase 2 del SuperPlan de SEO (2026-09-22): la grilla y la tabla ya
  // llegan pre-renderizadas en el HTML crudo -- pipeline/build_catalog_grid.py
  // escribe las 146 tarjetas/filas reales entre los marcadores
  // PRERENDER:*, cada una un <a href="/catalog/<repo>/"> real. Este script
  // NUNCA construye HTML de tarjetas/filas: solo oculta (hidden), reordena
  // (appendChild sobre nodos que ya existen) y pagina sobre esos nodos.
  // Filtrar/ordenar/paginar/buscar ya no dependen de data/catalog-data.json
  // ni de js/catalog-shared.js -- por eso esta pagina no los carga.
  var PAGE_SIZE = 15;
  var sortKey = 'downloads';
  var sortDir = -1; // desc
  var filterText = '';
  var filterPricing = '';
  var mode = 'field';
  var catalogPage = 1;
  // 2026-09-27: la misma logica sirve la version en espanol (/es/catalogo/).
  var ES = document.documentElement.lang === 'es';

  var board = document.querySelector('.cat-board');
  var knownCats = board
    ? Array.prototype.map.call(board.querySelectorAll('[data-cat]'), function (b) { return b.getAttribute('data-cat'); })
    : [];
  var categoryParam = new URLSearchParams(location.search).get('category') || '';
  // 2026-09-27: ?pricing=free|freemium|paid|pending, y "paid" desde la home
  // significa FREEMIUM + PAID ("Paid & Pro", valor PAIDANY del select).
  var pricingParam = (new URLSearchParams(location.search).get('pricing') || '').toUpperCase();
  if (pricingParam === 'PAID' && location.search.indexOf('pricing=paid') !== -1) pricingParam = 'PAIDANY';
  if (['FREE', 'FREEMIUM', 'PAID', 'PAIDANY', 'PENDING'].indexOf(pricingParam) !== -1) filterPricing = pricingParam;
  var filterCategory = knownCats.indexOf(categoryParam) !== -1 ? categoryParam : '';
  // 2026-11-24: the grid can be sorted too (before, only the table headers sorted). ?sort= keeps it in the URL.
  var SORTS = { downloads: ['downloads', -1], rating: ['rating', -1], newest: ['firstPublished', -1], name: ['name', 1] };
  var sortParam = new URLSearchParams(location.search).get('sort') || '';
  if (SORTS[sortParam]) { sortKey = SORTS[sortParam][0]; sortDir = SORTS[sortParam][1]; }

  var gridEl = document.getElementById('catalogGrid');
  var gridPagerHost = document.getElementById('fieldPager');
  var gridCards = gridEl ? Array.prototype.slice.call(gridEl.children) : [];
  var tbody = document.getElementById('tbody');
  // 2026-09-27: la tabla ya no viaja pre-renderizada (duplicaba los 146
  // items de la grilla, ~137 KB). Se arma aqui desde las tarjetas, que ya
  // traen todos los datos en sus atributos data-*; sin JS queda la grilla.
  // 2026-10-27: todo lo que entra a una fila pasa por esc() o se fuerza a numero. Los datos salen del HTML
  // pre-renderizado por el build (no son entrada del usuario), pero esta funcion arma marcado con ellos y no
  // debe depender de que eso siga siendo cierto.
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function buildRowsFromCards() {
    if (!tbody || tbody.children.length || !gridCards.length) return;
    var fmt = function (n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); };
    var numOrDash = function (v) { return v != null && v !== '' && isFinite(v) ? Number(v) : '—'; };
    var priceLabel = { FREE: ES ? 'Gratis' : 'Free', FREEMIUM: 'Freemium', PAID: ES ? 'De pago' : 'Paid' };
    var L = ES ? { dl: 'Descargas', rv: 'Reseñas', rt: 'Valoración', st: 'GitHub ★', pr: 'Precio', pb: 'Publicado' }
               : { dl: 'Downloads', rv: 'Reviews', rt: 'Rating', st: 'GitHub ★', pr: 'Pricing', pb: 'Published' };
    var html = gridCards.map(function (c) {
      var d = c.dataset;
      var attrs = Array.prototype.filter.call(c.attributes, function (a) { return a.name.indexOf('data-') === 0; })
        .map(function (a) { return esc(a.name) + '="' + esc(a.value) + '"'; }).join(' ');
      var name = c.querySelector('.card-name'), niche = c.querySelector('.card-niche');
      var pending = c.hasAttribute('data-pending');
      var price = pending ? '<span class="price-badge price-pending">' + (ES ? 'Pendiente' : 'Pending') + '</span>'
        : '<span class="price-badge price-' + esc((d.pricing || 'FREE').toLowerCase()) + '">' + (priceLabel[d.pricing] || priceLabel.FREE) + '</span>';
      return '<tr class="row" ' + attrs + '>' +
        '<td class="name-cell"><a href="' + esc(c.getAttribute('href')) + '"><div class="plugin-name">' + (name ? esc(name.textContent) : '') + '</div>' +
        '<div class="niche">' + (niche ? esc(niche.textContent) : '') + '</div></a></td>' +
        '<td class="num-cell" data-label="' + L.dl + '">' + (pending ? '—' : fmt(Number(d.downloads) || 0)) + '</td>' +
        '<td class="num-cell tbl-optional" data-label="' + L.rv + '">' + numOrDash(d.reviews) + '</td>' +
        '<td class="num-cell tbl-optional" data-label="' + L.rt + '">' + (d.rating != null ? Number(d.rating).toFixed(2) : '—') + '</td>' +
        '<td class="num-cell" data-label="' + L.st + '">' + numOrDash(d.stars) + '</td>' +
        '<td data-label="' + L.pr + '">' + price + '</td>' +
        '<td class="num-cell" data-label="' + L.pb + '" style="text-align:left">' + esc(d.firstpublished || '—') + '</td></tr>';
    }).join('');
    tbody.innerHTML = html;
  }
  buildRowsFromCards();
  var tableRows = tbody ? Array.prototype.slice.call(tbody.children) : [];
  var noResults = document.getElementById('noResults');
  var tablePagerHost = document.getElementById('tablePager');

  var PREFERS_REDUCED_MOTION = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function numOrNull(str) {
    return (str === undefined || str === '') ? null : parseFloat(str);
  }

  function matches(el) {
    var isPending = el.hasAttribute('data-pending');
    if (filterPricing) {
      if (filterPricing === 'PENDING' && !isPending) return false;
      if (filterPricing === 'PAIDANY') {
        if (['FREEMIUM', 'PAID'].indexOf(el.dataset.pricing || '') === -1) return false;
      } else if (filterPricing !== 'PENDING' && (el.dataset.pricing || '') !== filterPricing) return false;
    }
    if (filterCategory && el.dataset.cat !== filterCategory) return false;
    if (!filterText) return true;
    return (el.dataset.search || '').indexOf(filterText) !== -1;
  }

  // Mismo criterio que el catalogo tenia en JS puro: un valor ausente
  // (null/undefined) siempre queda al final, sin importar la direccion.
  function cmp(a, b) {
    var av, bv;
    if (sortKey === 'name') {
      av = a.dataset.name; bv = b.dataset.name;
    } else if (sortKey === 'pricing') {
      av = a.dataset.pricing || null; bv = b.dataset.pricing || null;
    } else if (sortKey === 'firstPublished') {
      av = a.dataset.firstpublished || null; bv = b.dataset.firstpublished || null;
    } else {
      av = numOrNull(a.dataset[sortKey]); bv = numOrNull(b.dataset[sortKey]);
    }
    var an = (av === null || av === undefined || av === '');
    var bn = (bv === null || bv === undefined || bv === '');
    if (an && bn) return 0;
    if (an) return 1;
    if (bn) return -1;
    if (av < bv) return -1 * sortDir;
    if (av > bv) return 1 * sortDir;
    return 0;
  }

  function pagerHtml(total) {
    var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (pages <= 1) return '';
    return '<nav class="catalog-pager" aria-label="' + (ES ? 'P\u00e1ginas del cat\u00e1logo' : 'Catalog pages') + '">' +
      '<button type="button" class="btn catalog-pager-btn" data-page-dir="-1" aria-label="' + (ES ? 'P\u00e1gina anterior' : 'Previous page') + '"' + (catalogPage <= 1 ? ' disabled' : '') + '>' + (ES ? 'Anterior' : 'Previous') + '</button>' +
      '<span class="catalog-pager-status" aria-live="polite">' + (ES ? 'P\u00e1gina ' + catalogPage + ' de ' + pages : 'Page ' + catalogPage + ' of ' + pages) + '</span>' +
      '<button type="button" class="btn catalog-pager-btn" data-page-dir="1" aria-label="' + (ES ? 'P\u00e1gina siguiente' : 'Next page') + '"' + (catalogPage >= pages ? ' disabled' : '') + '>' + (ES ? 'Siguiente' : 'Next') + '</button>' +
      '</nav>';
  }

  function wirePager(host, total, onChange) {
    if (!host) return;
    host.innerHTML = pagerHtml(total);
    Array.prototype.forEach.call(host.querySelectorAll('[data-page-dir]'), function (btn) {
      btn.addEventListener('click', function () {
        var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
        var dir = parseInt(btn.getAttribute('data-page-dir'), 10);
        catalogPage = Math.min(pages, Math.max(1, catalogPage + dir));
        onChange();
        scrollCatalogIntoView();
      });
    });
  }

  // Filtra (hidden), ordena (reordena los nodos YA existentes con
  // appendChild -- nunca reconstruye innerHTML) y pagina sobre una lista
  // de nodos pre-renderizados. Devuelve cuantos quedaron visibles tras el
  // filtro (antes de paginar), para el mensaje de "sin resultados" y el
  // paginador.
  function applyToNodes(container, allNodes) {
    var visible = allNodes.filter(matches);
    visible.sort(cmp);
    visible.forEach(function (el) { container.appendChild(el); });
    var pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
    if (catalogPage > pages) catalogPage = pages;
    if (catalogPage < 1) catalogPage = 1;
    var start = (catalogPage - 1) * PAGE_SIZE;
    allNodes.forEach(function (el) { el.hidden = true; });
    for (var i = start; i < Math.min(start + PAGE_SIZE, visible.length); i++) visible[i].hidden = false;
    return visible.length;
  }

  // Busqueda sin resultados = demanda expresada: ofrece construirlo.
  function missHtml() {
    var term = (filterText || '').trim();
    var safe = term.replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
    var href = (ES ? '/es/contacto/' : '/contact/') + '?intent=hire' + (term ? '&need=' + encodeURIComponent(term.slice(0, 120)) : '');
    var lead = ES ? (term ? 'Todav\u00eda no hay nada para \u201c' + safe + '\u201d. ' : 'No hay resultados para ese filtro. ')
                  : (term ? 'Nothing here matches \u201c' + safe + '\u201d yet. ' : 'No results for that filter. ');
    return lead + '<a class="miss-cta" href="' + href + '" data-goatcounter-click="cta-search-miss-hire">' +
      (ES ? '\u00bfNecesitas que se construya? Trabaja conmigo \u2192' : 'Need it built? Work with me \u2192') + '</a>';
  }

  function renderGrid() {
    if (!gridEl) return;
    var total = applyToNodes(gridEl, gridCards);
    var noResultsEl = document.getElementById('fieldNoResults');
    if (noResultsEl) {
      noResultsEl.hidden = total !== 0;
      if (total === 0) noResultsEl.innerHTML = missHtml();
    }
    wirePager(gridPagerHost, total, renderGrid);
  }

  function renderTable() {
    if (!tbody) return;
    var total = applyToNodes(tbody, tableRows);
    if (noResults) {
      noResults.style.display = total === 0 ? 'block' : 'none';
      if (total === 0) noResults.innerHTML = missHtml();
    }
    wirePager(tablePagerHost, total, renderTable);
  }

  function updateCategoryBoard() {
    if (!board) return;
    Array.prototype.forEach.call(board.querySelectorAll('.cat-cell'), function (btn) {
      var cat = btn.getAttribute('data-cat') || '';
      var active = cat === '' ? !filterCategory : filterCategory === cat;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function renderAll() {
    updateCategoryBoard();
    document.getElementById('fieldView').style.display = mode === 'field' ? 'grid' : 'none';
    document.getElementById('tableView').style.display = mode === 'table' ? 'block' : 'none';
    if (mode === 'field') renderGrid();
    else renderTable();
  }

  // 2026-10-05: el flujo de scroll vive en js/catalog-scroll.js (mismo
  // criterio para paginar, buscar y filtrar; margen segun el alto real del
  // topbar). Sin ese script, se vuelve al scrollIntoView de antes.
  function resultsEl() {
    return mode === 'table' ? document.getElementById('tableView') : document.getElementById('fieldMain');
  }
  function scrollCatalogIntoView() {
    var target = resultsEl();
    if (!target) return;
    if (window.GHLCatalogScroll) { window.GHLCatalogScroll.toResults(target); return; }
    target.scrollIntoView({ behavior: PREFERS_REDUCED_MOTION ? 'auto' : 'smooth', block: 'start' });
  }
  function revealResults(keep) {
    if (window.GHLCatalogScroll) window.GHLCatalogScroll.reveal(resultsEl(), keep || null);
  }

  function switchMode(newMode, btn) {
    if (newMode === mode) return;
    Array.prototype.forEach.call(document.querySelectorAll('#modeToggle button'), function (b) {
      var isActive = b === btn || b.getAttribute('data-mode') === newMode;
      b.classList.toggle('active', isActive);
      b.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
    mode = newMode;
    catalogPage = 1;
    renderAll();
    revealResults();
  }

  document.getElementById('modeToggle').addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-mode]');
    if (!btn) return;
    switchMode(btn.getAttribute('data-mode'), btn);
  });

  // Control bar compacta en mobile (a pedido explicito 2026-09-10): la
  // lupa expande/colapsa el campo de busqueda, "Filters" abre un popover
  // con los 2 <select> reales -- inerte fuera del breakpoint mobile.
  (function () {
    var controls = document.getElementById('controls');
    var searchToggle = document.getElementById('searchToggle');
    var searchInput = document.getElementById('searchInput');
    var filtersToggle = document.getElementById('filtersToggle');
    var filtersPanel = document.getElementById('filtersPanel');
    if (!controls || !searchToggle || !filtersToggle || !filtersPanel) return;

    function closeFilters() {
      filtersPanel.classList.remove('is-open');
      filtersToggle.setAttribute('aria-expanded', 'false');
    }
    function closeSearch() {
      controls.classList.remove('is-searching');
      searchToggle.setAttribute('aria-expanded', 'false');
    }

    searchToggle.addEventListener('click', function () {
      var opening = !controls.classList.contains('is-searching');
      controls.classList.toggle('is-searching', opening);
      searchToggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
      closeFilters();
      if (opening) searchInput.focus(); else searchInput.blur();
    });
    filtersToggle.addEventListener('click', function () {
      var opening = !filtersPanel.classList.contains('is-open');
      filtersPanel.classList.toggle('is-open', opening);
      filtersToggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
      if (opening) closeSearch();
    });
    document.addEventListener('click', function (e) {
      if (!controls.contains(e.target)) closeFilters();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (controls.classList.contains('is-searching')) closeSearch();
      if (filtersPanel.classList.contains('is-open')) closeFilters();
    });
  })();

  var sortSelect = document.getElementById('sortOrder');
  // The table headers and the sort select show the same order: one function marks both.
  function markSort() {
    Array.prototype.forEach.call(document.querySelectorAll('thead th'), function (t) {
      var on = t.getAttribute('data-key') === sortKey;
      t.classList.toggle('sorted', on);
      var old = t.querySelector('.arrow');
      if (old) old.remove();
      t.setAttribute('aria-sort', on ? (sortDir === 1 ? 'ascending' : 'descending') : 'none');
      if (on) {
        var arrow = document.createElement('span');
        arrow.className = 'arrow';
        arrow.textContent = sortDir === 1 ? '▲' : '▼';
        t.appendChild(arrow);
      }
    });
    if (sortSelect) {
      var match = '';
      Object.keys(SORTS).forEach(function (k) { if (SORTS[k][0] === sortKey && SORTS[k][1] === sortDir) match = k; });
      sortSelect.value = match || sortSelect.value;
    }
  }
  if (sortSelect) {
    sortSelect.addEventListener('change', function (e) {
      var s = SORTS[e.target.value];
      if (!s) return;
      sortKey = s[0]; sortDir = s[1];
      try {
        var url = new URL(location.href);
        if (e.target.value === 'downloads') url.searchParams.delete('sort'); else url.searchParams.set('sort', e.target.value);
        history.replaceState(null, '', url.pathname + url.search + url.hash);
      } catch (err) { /* sin History API: el orden igual funciona */ }
      catalogPage = 1;
      markSort();
      renderAll();
      revealResults(document.getElementById('controls'));
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll('thead th[data-key]'), function (th) {
    var sort = function () {
      var key = th.getAttribute('data-key');
      if (sortKey === key) {
        sortDir *= -1;
      } else {
        sortKey = key;
        sortDir = (key === 'name' || key === 'pricing' || key === 'firstPublished') ? 1 : -1;
      }
      markSort();
      renderAll();
      if (tbody) {
        tbody.classList.remove('just-sorted');
        void tbody.offsetWidth; // fuerza el reflow para reiniciar la animacion CSS
        tbody.classList.add('just-sorted');
      }
    };
    th.addEventListener('click', sort);
    th.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sort(); }
    });
  });

  var searchDebounceTimer = null;
  document.getElementById('searchInput').addEventListener('input', function (e) {
    var val = e.target.value;
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(function () {
      filterText = val.trim().toLowerCase();
      catalogPage = 1;
      renderAll();
      revealResults(document.getElementById('searchInput'));
    }, 120);
  });
  var pricingSelect = document.getElementById('pricingFilter');
  if (pricingSelect && filterPricing) pricingSelect.value = filterPricing;
  pricingSelect.addEventListener('change', function (e) {
    filterPricing = e.target.value;
    try {
      var url = new URL(location.href);
      if (filterPricing) url.searchParams.set('pricing', filterPricing === 'PAIDANY' ? 'paid' : filterPricing.toLowerCase());
      else url.searchParams.delete('pricing');
      history.replaceState(null, '', url.pathname + url.search + url.hash);
    } catch (err) { /* sin History API: el filtro igual funciona */ }
    catalogPage = 1;
    renderAll();
    revealResults(document.getElementById('controls'));
  });
  if (board) {
    board.addEventListener('click', function (e) {
      var btn = e.target.closest('.cat-cell');
      if (!btn || !board.contains(btn)) return;
      var cat = btn.getAttribute('data-cat') || '';
      filterCategory = (!cat || filterCategory === cat) ? '' : cat;
      try {
        var url = new URL(location.href);
        if (filterCategory) url.searchParams.set('category', filterCategory); else url.searchParams.delete('category');
        history.replaceState(null, '', url.pathname + url.search + url.hash);
      } catch (err) { /* sin History API: el filtro igual funciona */ }
      catalogPage = 1;
      renderAll();
      // 2026-10-05: el tablero queda fijo (sticky) en escritorio; si se elige
      // una categoria estando abajo en la lista, los resultados quedaban por
      // encima de la pantalla. Solo se desplaza cuando hace falta.
      revealResults();
    });
  }

  // Toda la fila navega al plugin (el nombre ya es un <a> real -- esto
  // solo extiende el area de click a la fila completa, por comodidad de
  // mouse). Ctrl/Cmd/Shift/click-derecho/click-de-rueda se dejan pasar
  // sin interferir para que abrir en pestaña nueva siga funcionando.
  if (tbody) {
    tbody.addEventListener('click', function (e) {
      if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      if (e.target.closest('a')) return;
      var row = e.target.closest('tr.row');
      if (!row) return;
      var repo = row.getAttribute('data-repo');
      if (repo) location.href = (ES ? '/es/catalogo/' : '/catalog/') + repo + '/';
    });
  }

  markSort();
  renderAll();

  (function initCatalogTopbar() {
    var burger = document.getElementById('topbarBurger');
    var topbar = document.getElementById('topbar');
    if (burger && topbar) {
      burger.addEventListener('click', function () {
        var open = topbar.classList.toggle('nav-open');
        burger.setAttribute('aria-expanded', String(open));
      });
    }
  })();

  // Fade el logo del pie del sidebar cuando el <footer> real entra en
  // viewport (ver comentario en css/shell.css).
  (function () {
    var siteFooter = document.querySelector('.site-footer');
    var sidebarFooter = document.querySelector('.sidebar-footer');
    if (siteFooter && sidebarFooter && 'IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          sidebarFooter.classList.toggle('is-near-footer', entry.isIntersecting);
        });
      }).observe(siteFooter);
    }
  })();
})();
