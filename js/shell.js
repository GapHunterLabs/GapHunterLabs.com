/* Shell compartido por las paginas secundarias: menu movil del topbar (burger + cierre al elegir un enlace) y fade del logo del sidebar cerca del footer.
   Movido desde un <script> inline el 2026-09-24 para poder quitar
   'unsafe-inline' del script-src de la CSP (ver DOCUMENTATION.md). */
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
