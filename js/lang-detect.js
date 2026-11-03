// Browser-language landing redirect.
// A static host (GitHub Pages) can't read Accept-Language server-side, so the
// English root (/) sends visitors whose browser prefers Spanish to /es/.
// Runs before paint (no defer) to avoid a flash of English. Only the home
// redirects; deep links and manual choices are respected.
(function () {
  "use strict";
  var KEY = "ghl-lang";

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function remember(v) {
    try { localStorage.setItem(KEY, v); } catch (e) {}
  }

  // 1) Redirect: only on the English home, and never when EN was chosen.
  var path = location.pathname;
  if (path === "/" || path === "/index.html") {
    var saved = stored();
    if (saved !== "en") {
      var lang = saved;
      if (!lang) {
        var nav = (navigator.languages && navigator.languages[0]) ||
                  navigator.language || "";
        lang = /^es\b/i.test(nav) ? "es" : "en";
      }
      if (lang === "es") {
        location.replace("/es/");
        return;
      }
    }
  }

  // 2) Remember an explicit pick from the language switcher so the redirect
  //    never fights a manual choice. Switcher links carry hreflang="en"/"es".
  function wire() {
    var links = document.querySelectorAll(".gh-lang a[hreflang]");
    for (var i = 0; i < links.length; i++) {
      links[i].addEventListener("click", function (ev) {
        var lg = ev.currentTarget.getAttribute("hreflang");
        if (lg === "en" || lg === "es") remember(lg);
      });
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
