/* Seccion de apps de Atlassian Marketplace del catalogo (lee GapAtlassian de
   atlassian-catalog.js). 2026-11-17: tercera plataforma, mismo patron que
   catalog-vsx.js -- pestana propia, buscador propio y tarjetas con el mismo
   markup que pre-renderiza pipeline/build_catalog_grid.py (si cambia uno,
   cambiar el otro). Consciente de "pending" (installs=null): nunca muestra
   un numero de instalaciones que no existe todavia. */
(function () {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  var ATL_ICON = '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="6" cy="6" r="2"/><circle cx="14" cy="6" r="2"/><circle cx="10" cy="15" r="2"/><path d="M7.6 7.2 8.5 13.3M12.4 7.2 11.5 13.3"/></svg>';
  var PAGE_SIZE = 12;
  var page = 1;
  var query = '';
  var ES = document.documentElement.lang === 'es';
  var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function thousands(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  GapAtlassian.ready.then(function (data) {
    var section = document.getElementById('atlassianSection');
    var grid = document.getElementById('atlassianGrid');
    var pagerHost = document.getElementById('atlassianPager');
    var search = document.getElementById('atlassianSearch');
    var empty = document.getElementById('atlassianNoResults');
    if (!section || !grid || !data.apps.length) return;
    var all = data.apps;
    var pitchEs = {};
    if (ES) {
      Array.prototype.forEach.call(grid.querySelectorAll('a.atl-card'), function (a) {
        var m = /\/atlassian\/([^/]+)\/$/.exec(a.getAttribute('href') || '');
        var p = a.querySelector('.card-pitch');
        if (m && p) pitchEs[m[1]] = p.textContent;
      });
    }
    function pitchOf(e) { return (ES && pitchEs[e.name]) || e.pitch || ''; }

    function filtered() {
      if (!query) return all;
      return all.filter(function (e) {
        return ((e.displayName || '') + ' ' + (e.niche || '') + ' ' + pitchOf(e)).toLowerCase().indexOf(query) !== -1;
      });
    }
    // 2026-11-17: cada app tiene su ficha propia en /catalog/atlassian/<name>/
    // (la instalacion sigue en Atlassian Marketplace, desde esa ficha, una vez publicada).
    function cardHtml(e) {
      var pending = e.installs === null || e.installs === undefined;
      var n = Number(e.installs) || 0;
      var priceBadge = pending
        ? '<span class="price-badge price-pending">' + (ES ? 'Pendiente' : 'Pending') + '</span>'
        : '<span class="price-badge price-free">' + (ES ? 'Gratis' : 'Free') + '</span>';
      var metrics = pending
        ? (ES ? 'Pendiente de moderación' : 'Pending moderation')
        : thousands(n) + (ES ? (n === 1 ? ' instalación' : ' instalaciones') : (n === 1 ? ' install' : ' installs'));
      // No aria-label: visible text is the accessible name (WCAG 2.5.3).
      return '<a class="vsx-card atl-card" href="' + (ES ? '/es/catalogo/atlassian/' : '/catalog/atlassian/') + esc(e.name) + '/">' +
        '<div class="card-header"><span class="card-cat atl-mark" aria-hidden="true">' + ATL_ICON + '</span>' +
        priceBadge + '</div>' +
        '<div class="card-top"><div class="card-name">' + esc(e.displayName) + '</div><div class="card-niche">' + esc(e.niche) + '</div></div>' +
        '<p class="card-pitch">' + esc(pitchOf(e)) + '</p>' +
        '<div class="card-metrics"><span class="card-dl-wrap">' + metrics + '</span>' +
        '<span class="card-go">' + (ES ? 'Detalles' : 'Details') + '</span></div></a>';
    }
    function pagerHtml(pages) {
      if (pages <= 1) return '';
      return '<nav class="catalog-pager" aria-label="' + (ES ? 'Páginas de apps de Atlassian Marketplace' : 'Atlassian Marketplace app pages') + '">' +
        '<button type="button" class="btn catalog-pager-btn" data-atl-dir="-1" aria-label="' + (ES ? 'Página anterior' : 'Previous page') + '"' + (page <= 1 ? ' disabled' : '') + '>' + (ES ? 'Anterior' : 'Previous') + '</button>' +
        '<span class="catalog-pager-status" aria-live="polite">' + (ES ? 'Página ' + page + ' de ' + pages : 'Page ' + page + ' of ' + pages) + '</span>' +
        '<button type="button" class="btn catalog-pager-btn" data-atl-dir="1" aria-label="' + (ES ? 'Página siguiente' : 'Next page') + '"' + (page >= pages ? ' disabled' : '') + '>' + (ES ? 'Siguiente' : 'Next') + '</button>' +
        '</nav>';
    }
    function render(scroll) {
      var list = filtered();
      var pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
      if (page > pages) page = pages;
      if (page < 1) page = 1;
      var start = (page - 1) * PAGE_SIZE;
      grid.innerHTML = list.slice(start, start + PAGE_SIZE).map(cardHtml).join('');
      if (empty) {
        empty.hidden = list.length !== 0;
        if (!list.length) {
          var term = esc(query);
          empty.innerHTML = (ES ? 'Todavía no hay nada para “' + term + '”. ' : 'Nothing here matches “' + term + '” yet. ') +
            '<a class="miss-cta" href="' + (ES ? '/es/contacto/' : '/contact/') + '?intent=hire&amp;need=' + encodeURIComponent(query.slice(0, 120)) +
            '" data-goatcounter-click="cta-search-miss-hire">' +
            (ES ? '¿Necesitas que se construya? Trabaja conmigo →' : 'Need it built? Work with me →') + '</a>';
        }
      }
      if (!pagerHost) return;
      pagerHost.innerHTML = pagerHtml(pages);
      Array.prototype.forEach.call(pagerHost.querySelectorAll('[data-atl-dir]'), function (btn) {
        btn.addEventListener('click', function () {
          page += parseInt(btn.getAttribute('data-atl-dir'), 10);
          render(true);
        });
      });
      if (scroll) {
        if (window.GHLCatalogScroll) window.GHLCatalogScroll.toResults(grid);
        else section.scrollIntoView({ block: 'start', behavior: reducedMotion ? 'auto' : 'smooth' });
      }
    }
    if (search) {
      var timer;
      search.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
          query = search.value.trim().toLowerCase(); page = 1; render(false);
          if (window.GHLCatalogScroll) window.GHLCatalogScroll.reveal(grid, search);
        }, 120);
      });
    }
    render(false);
  }).catch(function (error) {
    // No es fatal: sin datos, la grilla pre-renderizada sigue visible.
    console.error('Atlassian catalog failed to load', error);
  });
})();
