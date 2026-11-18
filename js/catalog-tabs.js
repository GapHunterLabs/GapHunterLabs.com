/* Pestanas de plataforma del catalogo (2026-09-27, tercera plataforma
   2026-11-17): JetBrains IDEs | VS Code | Atlassian. Sin JavaScript las
   secciones se ven una debajo de la otra y las pestanas funcionan como
   anclas. Con JavaScript se muestra una sola y la eleccion queda en la URL
   (?platform=vscode / ?platform=atlassian) para poder compartirla. 'jetbrains'
   es el default implicito: nunca aparece en la URL. Tambien acepta los
   anclas viejas #vsxSection/#vscode y #atlassianSection/#atlassian. */
(function () {
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.platform-tab'));
  if (!tabs.length) return;

  var names = tabs.map(function (tab) { return tab.getAttribute('data-platform'); });

  function panelOf(tab) { return document.getElementById(tab.getAttribute('aria-controls')); }

  function select(name, updateUrl) {
    tabs.forEach(function (tab) {
      var on = tab.getAttribute('data-platform') === name;
      tab.setAttribute('aria-selected', on ? 'true' : 'false');
      tab.tabIndex = on ? 0 : -1;
      var panel = panelOf(tab);
      if (panel) panel.hidden = !on;
    });
    if (!updateUrl) return;
    try {
      var url = new URL(location.href);
      if (name === 'jetbrains') url.searchParams.delete('platform'); else url.searchParams.set('platform', name);
      history.replaceState(null, '', url.pathname + url.search);
    } catch (e) { /* sin History API: la pestana igual cambia */ }
  }

  var params = new URLSearchParams(location.search);
  var fromParam = params.get('platform');
  var fromHash = location.hash === '#vsxSection' || location.hash === '#vscode' ? 'vscode' :
    location.hash === '#atlassianSection' || location.hash === '#atlassian' ? 'atlassian' : null;
  var wanted = (fromParam && names.indexOf(fromParam) !== -1) ? fromParam : fromHash;
  select((wanted && names.indexOf(wanted) !== -1) ? wanted : 'jetbrains', false);

  tabs.forEach(function (tab, i) {
    tab.addEventListener('click', function (e) {
      e.preventDefault();
      select(tab.getAttribute('data-platform'), true);
    });
    tab.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      e.preventDefault();
      var next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
      next.focus();
      select(next.getAttribute('data-platform'), true);
    });
  });
})();
