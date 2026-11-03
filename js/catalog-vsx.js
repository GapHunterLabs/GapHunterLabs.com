/* Seccion de extensiones de VS Code del catalogo (lee GapVSCode de vscode-catalog.js).
   2026-09-27: pestana propia, buscador propio y tarjetas con el mismo
   markup que pre-renderiza pipeline/build_catalog_grid.py (si cambia uno,
   cambiar el otro). Paginada: 12 por pagina, con los mismos estilos de
   paginador que la grilla de JetBrains. */
(function () {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  var VS_ICON = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M23.15 2.587L18.21.21a1.494 1.494 0 0 0-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 0 0-1.276.057L.327 7.261A1 1 0 0 0 .326 8.74L3.899 12 .326 15.26a1 1 0 0 0 .001 1.479L1.65 17.94a.999.999 0 0 0 1.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 0 0 1.704.29l4.942-2.377A1.5 1.5 0 0 0 24 20.06V3.939a1.5 1.5 0 0 0-.85-1.352zm-5.146 14.861L10.826 12l7.178-5.448v10.896z"/></svg>';
  var PAGE_SIZE = 12;
  var page = 1;
  var query = '';
  var ES = document.documentElement.lang === 'es';
  var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function thousands(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  GapVSCode.ready.then(function (data) {
    var section = document.getElementById('vsxSection');
    var grid = document.getElementById('vsxGrid');
    var pagerHost = document.getElementById('vsxPager');
    var search = document.getElementById('vsxSearch');
    var empty = document.getElementById('vsxNoResults');
    if (!section || !grid || !data.extensions.length) return;
    var all = data.extensions;

    function filtered() {
      if (!query) return all;
      return all.filter(function (e) {
        return ((e.displayName || '') + ' ' + (e.niche || '') + ' ' + (e.pitch || '')).toLowerCase().indexOf(query) !== -1;
      });
    }
    // 2026-09-27: cada extension tiene su ficha propia en /catalog/vscode/<name>/
    // (la instalacion sigue en VS Code Marketplace, desde esa ficha).
    function cardHtml(e) {
      var n = Number(e.installs) || 0;
      // No aria-label: visible text is the accessible name (WCAG 2.5.3).
      return '<a class="vsx-card" href="' + (ES ? '/es/catalogo/vscode/' : '/catalog/vscode/') + esc(e.name) + '/">' +
        '<div class="card-header"><span class="card-cat vsx-mark" aria-hidden="true">' + VS_ICON + '</span>' +
        '<span class="price-badge price-free">' + (ES ? 'Gratis' : 'Free') + '</span></div>' +
        '<div class="card-top"><div class="card-name">' + esc(e.displayName) + '</div><div class="card-niche">' + esc(e.niche) + '</div></div>' +
        '<p class="card-pitch">' + esc(e.pitch) + '</p>' +
        '<div class="card-metrics"><span class="card-dl-wrap">' + thousands(n) +
        (ES ? (n === 1 ? ' instalación' : ' instalaciones') : (n === 1 ? ' install' : ' installs')) + '</span>' +
        '<span class="card-go">' + (ES ? 'Detalles' : 'Details') + '</span></div></a>';
    }
    function pagerHtml(pages) {
      if (pages <= 1) return '';
      return '<nav class="catalog-pager" aria-label="' + (ES ? 'Páginas de extensiones de VS Code' : 'VS Code extension pages') + '">' +
        '<button type="button" class="btn catalog-pager-btn" data-vsx-dir="-1" aria-label="' + (ES ? 'Página anterior' : 'Previous page') + '"' + (page <= 1 ? ' disabled' : '') + '>' + (ES ? 'Anterior' : 'Previous') + '</button>' +
        '<span class="catalog-pager-status" aria-live="polite">' + (ES ? 'Página ' + page + ' de ' + pages : 'Page ' + page + ' of ' + pages) + '</span>' +
        '<button type="button" class="btn catalog-pager-btn" data-vsx-dir="1" aria-label="' + (ES ? 'Página siguiente' : 'Next page') + '"' + (page >= pages ? ' disabled' : '') + '>' + (ES ? 'Siguiente' : 'Next') + '</button>' +
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
      Array.prototype.forEach.call(pagerHost.querySelectorAll('[data-vsx-dir]'), function (btn) {
        btn.addEventListener('click', function () {
          page += parseInt(btn.getAttribute('data-vsx-dir'), 10);
          render(true);
        });
      });
      // 2026-10-05: mismo flujo que la grilla JetBrains (js/catalog-scroll.js)
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
    console.error('VS Code catalog failed to load', error);
  });
})();
