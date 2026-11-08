/* Encabezado y pie compartidos (2026-09-27): menus desplegables del
   encabezado, selector de tema System/Light/Dark (encabezado + pie) y
   cierre del menu movil al elegir un enlace. El burger lo siguen
   manejando los scripts de cada pagina (#topbar.nav-open). */
(function () {
  /* Scroll progress bar — created once, appended before body first child */
  var bar = document.createElement('div');
  bar.id = 'nb-scroll-bar';
  bar.setAttribute('aria-hidden', 'true');
  document.body.insertBefore(bar, document.body.firstChild);
  if (!CSS.supports('animation-timeline', 'scroll()')) {
    var update = function () {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.transform = 'scaleX(' + (h > 0 ? window.scrollY / h : 0) + ')';
    };
    window.addEventListener('scroll', update, { passive: true });
    update();
  }
})();
(function () {
  var root = document.documentElement;
  var KEY = 'ghl-theme';

  function currentChoice() {
    var t = root.getAttribute('data-theme');
    return t === 'light' || t === 'dark' ? t : 'system';
  }

  function syncThemeControls() {
    var choice = currentChoice();
    document.querySelectorAll('[data-theme-choice]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', btn.getAttribute('data-theme-choice') === choice ? 'true' : 'false');
    });
  }

  function applyTheme(choice) {
    if (choice === 'light' || choice === 'dark') root.setAttribute('data-theme', choice);
    else root.removeAttribute('data-theme');
    try {
      localStorage.setItem(KEY, choice); // 'system' tambien se guarda: sin clave = primera visita (oscuro)
    } catch (e) { /* sin almacenamiento: vale para esta visita */ }
    syncThemeControls();
  }

  document.querySelectorAll('[data-theme-choice]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      applyTheme(btn.getAttribute('data-theme-choice'));
      closeAllMenus();
    });
  });
  syncThemeControls();

  // ---- menus desplegables (patron disclosure: boton + panel) ----------
  var menus = Array.prototype.slice.call(document.querySelectorAll('.gh-menu'));

  function closeAllMenus(except) {
    menus.forEach(function (menu) {
      if (menu === except) return;
      var toggle = menu.querySelector('[data-menu-toggle]');
      var panel = menu.querySelector('[data-menu]');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
      if (panel) panel.hidden = true;
    });
  }

  menus.forEach(function (menu) {
    var toggle = menu.querySelector('[data-menu-toggle]');
    var panel = menu.querySelector('[data-menu]');
    if (!toggle || !panel) return;
    toggle.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = panel.hidden;
      closeAllMenus(menu);
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) {
        var first = panel.querySelector('button, a');
        if (first) first.focus();
      }
    });
    panel.addEventListener('click', function (e) { e.stopPropagation(); });
  });

  document.addEventListener('click', function () { closeAllMenus(); });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var openMenu = menus.filter(function (m) { var p = m.querySelector('[data-menu]'); return p && !p.hidden; })[0];
    closeAllMenus();
    if (openMenu) {
      var t = openMenu.querySelector('[data-menu-toggle]');
      if (t) t.focus();
    }
    var header = document.getElementById('topbar');
    var burger = document.getElementById('topbarBurger');
    if (header && header.classList.contains('nav-open')) {
      header.classList.remove('nav-open');
      if (burger) { burger.setAttribute('aria-expanded', 'false'); burger.focus(); }
    }
  });

  // ---- menu movil: cerrar al elegir un enlace ------------------------
  var header = document.getElementById('topbar');
  var burger = document.getElementById('topbarBurger');
  document.querySelectorAll('#siteNav a').forEach(function (link) {
    link.addEventListener('click', function () {
      if (header) header.classList.remove('nav-open');
      if (burger) burger.setAttribute('aria-expanded', 'false');
    });
  });

  // ---- buscador del topbar (2026-10-05) --------------------------------
  // site-search.js y el indice se cargan recien al abrir el buscador (clic,
  // Ctrl/Cmd+K o "/"). build_search_index.py escribe la URL con su hash.
  var SEARCH_SRC = /*SEARCH_SRC*/'/js/site-search.js?v=fc30541c'/*ENDSEARCH_SRC*/;
  var searchLoading = false;
  function openSearch(trigger) {
    if (window.GHLSearch) { window.GHLSearch.open(trigger); return; }
    if (searchLoading) return;
    searchLoading = true;
    var s = document.createElement('script');
    s.src = SEARCH_SRC;
    s.async = true;
    s.onload = function () { searchLoading = false; if (window.GHLSearch) window.GHLSearch.open(trigger); };
    s.onerror = function () { searchLoading = false; };
    document.head.appendChild(s);
  }
  var searchButtons = document.querySelectorAll('[data-search-open]');
  searchButtons.forEach(function (btn) {
    btn.addEventListener('click', function (e) { e.preventDefault(); openSearch(btn); });
  });
  document.addEventListener('keydown', function (e) {
    if (!searchButtons.length || e.altKey) return;
    var t = e.target;
    var typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
    var cmdK = (e.key === 'k' || e.key === 'K') && (e.ctrlKey || e.metaKey);
    var slash = e.key === '/' && !typing && !e.ctrlKey && !e.metaKey;
    if (cmdK || slash) { e.preventDefault(); openSearch(searchButtons[0]); }
  });

  // Outbound clicks to JetBrains Marketplace (the macro conversion: leaving the
  // site for a plugin listing). GoatCounter's count.js already tracks links that
  // carry data-goatcounter-click; this covers every other Marketplace link,
  // including plugin detail pages, without double-counting the tagged ones.
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href*="plugins.jetbrains.com"]') : null;
    if (!a || a.hasAttribute('data-goatcounter-click')) return;
    if (!(window.goatcounter && window.goatcounter.count)) return;
    var p = '';
    try { p = new URL(a.href).pathname; } catch (err) { p = ''; }
    var bucket = p.indexOf('/vendor/') === 0 ? 'vendor'
               : p.indexOf('/plugin/') === 0 ? 'plugin' : 'other';
    try { window.goatcounter.count({ path: 'cta-marketplace-' + bucket, event: true }); } catch (err) { /* opcional */ }
  });
})();
