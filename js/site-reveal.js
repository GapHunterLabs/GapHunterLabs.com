/*
 * Scroll reveal for Gap Hunter Labs pages.
 *
 * Content below the fold fades in when it reaches the viewport. Content that is
 * already on screen when the page loads is never hidden, so nothing flickers.
 * Without JavaScript, with "reduce motion", or when printing, everything is
 * visible from the start (see the .rv-on rules at the end of css/shell.css).
 *
 * Timing and position are controlled in three places, from widest to narrowest:
 *   1. CONFIG below: site-wide defaults and the selectors that get the effect.
 *   2. data-reveal-* attributes on <body>: defaults for one page.
 *   3. data-reveal-* attributes on an element: that element only.
 *
 * Attributes (levels 2 and 3):
 *   data-reveal            up | down | left | right | fade | none  (none = no effect)
 *   data-reveal-distance   travel in px
 *   data-reveal-duration   duration in ms
 *   data-reveal-delay      delay in ms
 *   data-reveal-easing     any CSS timing function
 *   data-reveal-stagger    extra delay in ms between elements that enter together
 *
 * window.GHReveal exposes the merged config and a refresh() for content added later.
 */
(function () {
  "use strict";

  var CONFIG = {
    direction: "up",          // up | down | left | right | fade
    distance: 12,             // px
    duration: 450,            // ms
    delay: 0,                 // ms
    easing: "cubic-bezier(0.2, 0.6, 0.2, 1)",
    stagger: 60,              // ms between elements that enter in the same frame
    maxStagger: 300,          // ms, cap for long batches
    threshold: 0.12,          // share of the element that must be visible
    rootMargin: "0px 0px -6% 0px",
    // Elements that get the effect. When one target contains another, only the
    // inner one is animated, so a section never fades on top of its own cards.
    targets: [
      ".section-head", ".lab-section-head", ".cv-head",
      ".paid-card", ".offer-card", ".path-card", ".identity-step", ".identity-card",
      ".plugin-card", ".svc-card", ".svc-band", ".hire-band",
      ".ticket-card", ".disclosure", ".decision-figure",
      ".feedback-card", ".contact-form-panel", ".contact-desk",
      ".pb-card", ".fact", ".rel-card",
      ".loop-section", ".founder-section",
      "main section", "main article"
    ],
    // Never animated, even if a target selector matches them.
    exclude: [".gh-header", ".gh-footer", ".gh-page-header", "[data-reveal='none']"]
  };

  var root = document.documentElement;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || !("IntersectionObserver" in window)) {
    window.GHReveal = { config: CONFIG, refresh: function () {} };
    return;
  }

  function num(value, fallback) {
    var n = parseFloat(value);
    return isFinite(n) ? n : fallback;
  }

  function settings(el) {
    var body = document.body ? document.body.dataset : {};
    var own = el.dataset;
    function pick(key, fallback) {
      if (own[key] !== undefined && own[key] !== "") return own[key];
      if (body[key] !== undefined && body[key] !== "") return body[key];
      return fallback;
    }
    return {
      direction: pick("reveal", CONFIG.direction),
      distance: num(pick("revealDistance", CONFIG.distance), CONFIG.distance),
      duration: num(pick("revealDuration", CONFIG.duration), CONFIG.duration),
      delay: num(pick("revealDelay", CONFIG.delay), CONFIG.delay),
      easing: pick("revealEasing", CONFIG.easing),
      stagger: num(pick("revealStagger", CONFIG.stagger), CONFIG.stagger)
    };
  }

  function offset(direction, distance) {
    switch (direction) {
      case "down": return [0, -distance];
      case "left": return [distance, 0];
      case "right": return [-distance, 0];
      case "fade": return [0, 0];
      default: return [0, distance];
    }
  }

  var excluded = CONFIG.exclude.join(",");
  var seen = typeof WeakSet === "function" ? new WeakSet() : null;

  function candidates() {
    var list = [];
    var nodes = document.querySelectorAll(CONFIG.targets.join(","));
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (el.closest(excluded)) continue;
      if (el.dataset.reveal === "none") continue;
      if (seen && seen.has(el)) continue;
      list.push(el);
    }
    // Keep only the innermost targets.
    return list.filter(function (el) {
      for (var j = 0; j < list.length; j++) {
        if (list[j] !== el && el.contains(list[j])) return false;
      }
      return true;
    });
  }

  var observer = new IntersectionObserver(function (entries) {
    var batch = entries.filter(function (e) { return e.isIntersecting; });
    batch.sort(function (a, b) { return a.boundingClientRect.top - b.boundingClientRect.top; });
    batch.forEach(function (entry, i) {
      var el = entry.target;
      var s = settings(el);
      var extra = Math.min(i * s.stagger, CONFIG.maxStagger);
      el.style.setProperty("--rv-delay", (s.delay + extra) + "ms");
      el.classList.add("rv-in");
      observer.unobserve(el);
    });
  }, { threshold: CONFIG.threshold, rootMargin: CONFIG.rootMargin });

  function prepare() {
    var viewport = window.innerHeight || root.clientHeight;
    // Read every position first, then write: reading one element's position right after
    // styling the previous one forces a new layout of the whole page per element.
    var below = candidates().filter(function (el) {
      if (seen) seen.add(el);
      // Already on screen (or above it) when this runs: leave it as it is.
      return el.getBoundingClientRect().top >= viewport;
    });
    below.forEach(function (el) {
      var s = settings(el);
      var xy = offset(s.direction, s.distance);
      el.style.setProperty("--rv-x", xy[0] + "px");
      el.style.setProperty("--rv-y", xy[1] + "px");
      el.style.setProperty("--rv-dur", s.duration + "ms");
      el.style.setProperty("--rv-ease", s.easing);
      // A class, not a data-* attribute: catalog.js copies the cards' data-* attributes
      // to the table rows, and a copied marker would hide rows nobody observes.
      el.classList.add("rv-target");
      observer.observe(el);
    });
  }

  root.classList.add("rv-on");
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", prepare);
  } else {
    prepare();
  }

  window.GHReveal = { config: CONFIG, refresh: prepare };
})();
