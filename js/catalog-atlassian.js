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
  var ATL_ICON = '<svg viewBox="7 4 34.6925 34.63" fill="currentColor" aria-hidden="true"><path d="M41.3175 36.5672L25.4402 4.81262C25.1276 4.12502 24.8151 4 24.44 4C24.1275 4 23.7524 4.12502 23.3774 4.75011C21.127 8.31312 20.1269 12.4387 20.1269 16.7518C20.1269 22.7527 23.1898 28.3785 27.6905 37.4423C28.1906 38.4425 28.5656 38.63 29.4407 38.63H40.4423C41.2549 38.63 41.6925 38.3175 41.6925 37.6924C41.6925 37.3798 41.63 37.1923 41.3175 36.5672ZM18.2516 21.565C17.0014 19.6898 16.6264 19.5647 16.3138 19.5647C16.0013 19.5647 15.8138 19.6898 15.2512 20.8149L7.31255 36.6922C7.06251 37.1923 7 37.3798 7 37.6299C7 38.1299 7.43756 38.63 8.3752 38.63H19.5643C20.3144 38.63 20.877 38.0049 21.1895 36.8172C21.5646 35.317 21.6896 34.0043 21.6896 32.4416C21.6896 28.066 19.7518 23.8154 18.2516 21.565Z"/></svg>';
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
    // The app's own icon when the data declares one; only a same-origin /media/*.png path is accepted,
    // anything else falls back to the Atlassian platform mark.
    function iconHtml(e) {
      if (typeof e.icon === 'string' && /^\/media\/[a-z0-9\/._-]+\.png$/.test(e.icon) && e.icon.indexOf('..') === -1) {
        return '<span class="card-cat card-app-icon" aria-hidden="true"><img src="' + esc(e.icon) +
          '" width="34" height="34" alt="" decoding="async" loading="lazy"></span>';
      }
      return '<span class="card-cat atl-mark" aria-hidden="true">' + ATL_ICON + '</span>';
    }
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
        '<div class="card-header">' + iconHtml(e) +
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
