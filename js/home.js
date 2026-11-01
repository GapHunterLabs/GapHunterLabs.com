/* Interactividad de la home: slider destacado (dots/flechas/autoplay/zoom), menu movil y fade del footer.
   Movido desde un <script> inline el 2026-09-24 para poder quitar
   'unsafe-inline' del script-src de la CSP (ver DOCUMENTATION.md). */
(function () {
  'use strict';
  // Fase 2 del SuperPlan de SEO (2026-09-22): el subtitulo del hero, los
  // contadores, los facts, las categorias y el slider de destacados ya
  // llegan pre-renderizados (pipeline/build_home.py, mismos datos que
  // catalog-data.json pero escritos como HTML real en vez de pedidos por
  // fetch). Esta pagina ya no carga js/catalog-shared.js ni depende de
  // GapCatalog -- lo unico que queda en JS es interactividad sobre nodos
  // que ya existen: el slider (dots/flechas/autoplay/zoom) y el burger
  // del topbar.
  var PREFERS_REDUCED_MOTION = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  (function initHeroSlider() {
    var track = document.getElementById('heroSliderTrack');
    var dots = document.getElementById('heroSliderDots');
    var prev = document.getElementById('heroSliderPrev');
    var next = document.getElementById('heroSliderNext');
    if (!track || !dots || !prev || !next) return;
    var slides = Array.prototype.slice.call(track.children);
    var dotEls = Array.prototype.slice.call(dots.children);
    if (!slides.length) return;
    var index = 0, timer;
    // Fase 3 (2026-09-23): el autoplay no corre mientras el slider esta
    // fuera de viewport (nadie lo ve, y setInterval + los reflows de
    // go() seguian corriendo igual mientras el visitante lee mas abajo
    // en la pagina) -- inVisible controla si play() arma el timer o no;
    // el observer llama play()/pause() al cruzar, sin tocar el resto de
    // la logica de abajo.
    var inViewport = true;

    function go(n) {
      index = (n + slides.length) % slides.length;
      track.style.transform = 'translateX(-' + index * 100 + '%)';
      slides.forEach(function (el, i) { el.tabIndex = i === index ? 0 : -1; });
      dotEls.forEach(function (el, i) { el.classList.toggle('is-active', i === index); });
    }
    function play() {
      clearInterval(timer);
      if (!PREFERS_REDUCED_MOTION && inViewport) timer = setInterval(function () { go(index + 1); }, 5500);
    }
    prev.addEventListener('click', function () { go(index - 1); play(); });
    next.addEventListener('click', function () { go(index + 1); play(); });
    dots.addEventListener('click', function (e) {
      var dot = e.target.closest('.hs-dot');
      var i = dot ? dotEls.indexOf(dot) : -1;
      if (i >= 0) { go(i); play(); }
    });
    play();

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        inViewport = entries[0].isIntersecting;
        play();
      }, { threshold: 0 }).observe(track);
    }

    // Zoom que sigue al mouse (a pedido explicito 2026-09-10) -- el
    // origen del scale() (--hs-ox/--hs-oy, default 50%/18% en CSS) se
    // sobreescribe por elemento segun la posicion real del cursor.
    // Delegado en `track` (estable) en vez de por-slide. Throttleado a
    // un update por frame (rAF) desde el 2026-09-23 -- mousemove puede
    // disparar 60-120+ veces/seg con un mouse rapido, y cada disparo
    // sin throttle forzaba un recalculo de estilo; con rAF, varios
    // eventos que llegan en el mismo frame colapsan en un solo write.
    if (!PREFERS_REDUCED_MOTION) {
      var zoomFrame = null, pendingMedia = null, pendingOx = 0, pendingOy = 0;
      function flushZoom() {
        zoomFrame = null;
        pendingMedia.style.setProperty('--hs-ox', pendingOx + '%');
        pendingMedia.style.setProperty('--hs-oy', pendingOy + '%');
      }
      track.addEventListener('mousemove', function (e) {
        var media = e.target.closest('.hs-media');
        if (!media) return;
        var rect = media.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        pendingMedia = media;
        pendingOx = Math.min(100, Math.max(0, (e.clientX - rect.left) / rect.width * 100));
        pendingOy = Math.min(100, Math.max(0, (e.clientY - rect.top) / rect.height * 100));
        if (zoomFrame === null) zoomFrame = requestAnimationFrame(flushZoom);
      });
      track.addEventListener('mouseleave', function () {
        if (zoomFrame !== null) { cancelAnimationFrame(zoomFrame); zoomFrame = null; }
        Array.prototype.forEach.call(track.querySelectorAll('.hs-media'), function (media) {
          media.style.removeProperty('--hs-ox');
          media.style.removeProperty('--hs-oy');
        });
      });
    }
  })();

  // Hero: cuatro areas de trabajo (rendimiento, seguridad, fiabilidad, herramientas).
  // Rotacion automatica; en pausa con el cursor o el foco dentro de la tarjeta, o con el
  // boton de pausa; sin rotacion automatica si el usuario pidio menos movimiento.
  (function initHeroStates() {
    var root = document.getElementById('heroStates');
    if (!root) return;
    var tabs = Array.prototype.slice.call(document.querySelectorAll('.nb-state'));
    var panels = Array.prototype.slice.call(root.querySelectorAll('.nb-panel'));
    var bar = document.getElementById('heroProgress');
    var count = document.getElementById('heroCount');
    var toggle = document.getElementById('heroToggle');
    var DWELL = 8000;
    if (!tabs.length || tabs.length !== panels.length || !bar) return;
    var index = 0, timer = null, userPaused = !!PREFERS_REDUCED_MOTION, hovering = false;
    var track = bar.parentNode;
    track.style.setProperty('--nb-dwell', DWELL + 'ms');

    function running() { return !userPaused && !hovering && !document.hidden; }
    function schedule() {
      clearTimeout(timer);
      track.classList.remove('is-running', 'is-paused', 'is-static');
      void bar.offsetWidth; // reinicia la animacion de la barra
      if (PREFERS_REDUCED_MOTION) { track.classList.add('is-static'); return; }
      track.classList.add('is-running');
      if (!running()) { track.classList.add('is-paused'); return; }
      timer = setTimeout(function () { show(index + 1); }, DWELL);
    }
    function show(i, focusTab) {
      index = (i + panels.length) % panels.length;
      panels.forEach(function (p, n) { p.hidden = n !== index; });
      tabs.forEach(function (t, n) {
        t.setAttribute('aria-selected', String(n === index));
        t.tabIndex = n === index ? 0 : -1;
      });
      if (count) count.textContent = '0' + (index + 1);
      if (focusTab) tabs[index].focus();
      schedule();
    }
    function sync() {
      if (running()) schedule();
      else { clearTimeout(timer); track.classList.add('is-paused'); }
    }

    tabs.forEach(function (t, n) {
      t.addEventListener('click', function () { show(n); });
      t.addEventListener('keydown', function (e) {
        var k = e.key;
        if (k === 'ArrowRight' || k === 'ArrowDown') { e.preventDefault(); show(index + 1, true); }
        else if (k === 'ArrowLeft' || k === 'ArrowUp') { e.preventDefault(); show(index - 1, true); }
        else if (k === 'Home') { e.preventDefault(); show(0, true); }
        else if (k === 'End') { e.preventDefault(); show(panels.length - 1, true); }
      });
    });
    document.getElementById('heroPrev').addEventListener('click', function () { show(index - 1); });
    document.getElementById('heroNext').addEventListener('click', function () { show(index + 1); });
    function reflectToggle() {
      toggle.setAttribute('aria-pressed', String(userPaused));
      toggle.setAttribute('aria-label', userPaused ? 'Resume rotation' : 'Pause rotation');
    }
    toggle.addEventListener('click', function () { userPaused = !userPaused; reflectToggle(); sync(); });
    root.addEventListener('mouseenter', function () { hovering = true; sync(); });
    root.addEventListener('mouseleave', function () { hovering = false; sync(); });
    root.addEventListener('focusin', function () { hovering = true; sync(); });
    root.addEventListener('focusout', function () { hovering = false; sync(); });
    document.addEventListener('visibilitychange', sync);
    reflectToggle();
    show(0);
  })();

  var burger = document.getElementById('topbarBurger'), topbar = document.getElementById('topbar');
  if (burger && topbar) {
    burger.addEventListener('click', function () {
      var open = topbar.classList.toggle('nav-open');
      burger.setAttribute('aria-expanded', String(open));
    });
  }

  // Fade el logo del pie del sidebar cuando el <footer> real entra en
  // viewport (ver comentario en css/shell.css).
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
