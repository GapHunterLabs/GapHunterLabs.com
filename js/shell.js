/* Shell compartido por las paginas secundarias: menu movil del topbar (burger + cierre al elegir un enlace) y fade del logo del sidebar cerca del footer.
   Movido desde un <script> inline el 2026-09-24 para poder quitar
   'unsafe-inline' del script-src de la CSP (ver DOCUMENTATION.md). */
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
/* GHL logo scroll-progress fill: reveals brand colors left-to-right as user scrolls */
(function () {
  var logo = document.querySelector('.gh-logo');
  if (!logo) return;
  logo.innerHTML =
    '<defs><clipPath id="ghl-p"><rect id="ghl-p-r" x="85" y="45" width="0" height="855"/></clipPath></defs>' +
    '<path d="M 511,81 L 847,283 L 725,351 L 508,223 L 296,348 L 296,588 L 463,691 L 342,765 L 173,665 L 172,281 Z" fill="currentColor" opacity="0.18"/>' +
    '<path d="M 846,412 L 844,668 L 518,863 L 393,795 L 724,589 L 721,540 L 567,538 L 568,412 Z" fill="currentColor" opacity="0.18"/>' +
    '<polygon points="569,413 695,413 695,539 569,539" fill="currentColor" opacity="0.18"/>' +
    '<g clip-path="url(#ghl-p)">' +
    '<path d="M 511,81 L 847,283 L 725,351 L 508,223 L 296,348 L 296,588 L 463,691 L 342,765 L 173,665 L 172,281 Z" fill="#0151FC"/>' +
    '<path d="M 846,412 L 844,668 L 518,863 L 393,795 L 724,589 L 721,540 L 567,538 L 568,412 Z" fill="#01B3FD"/>' +
    '<polygon points="569,413 695,413 695,539 569,539" fill="#02F172"/>' +
    '</g>';
  var r = document.getElementById('ghl-p-r');
  if (!r) return;
  function syncLogo() {
    var h = document.documentElement.scrollHeight - window.innerHeight;
    r.setAttribute('width', h > 0 ? ((window.scrollY / h) * 855).toFixed(1) : '0');
  }
  window.addEventListener('scroll', syncLogo, { passive: true });
  syncLogo();
})();
(function () {
  var topbar = document.getElementById('topbar');
  var burger = document.getElementById('topbarBurger');
  if (topbar && burger) {
    burger.addEventListener('click', function () {
      var open = topbar.classList.toggle('nav-open');
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.querySelectorAll('#appSidebar a').forEach(function (link) {
      link.addEventListener('click', function () {
        topbar.classList.remove('nav-open');
        burger.setAttribute('aria-expanded', 'false');
      });
    });
  }
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
