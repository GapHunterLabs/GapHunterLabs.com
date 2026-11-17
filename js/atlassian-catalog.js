// Loads data/atlassian-catalog-data.json, the Atlassian Marketplace
// cross-reference (third platform, 2026-11-17). Deliberately separate from
// js/catalog-shared.js (the JetBrains pipeline's loader) and from
// js/vscode-catalog.js -- different marketplace, different data shape.
// A page that doesn't call GapAtlassian.ready simply never fetches this file.
(function () {
  'use strict';

  var ready = fetch('/data/atlassian-catalog-data.json', { credentials: 'same-origin' })
    .then(function (response) {
      if (!response.ok) throw new Error('Atlassian catalog request failed: ' + response.status);
      return response.json();
    })
    .then(function (data) {
      if (!data || !Array.isArray(data.apps)) throw new Error('Atlassian catalog response is invalid');
      return data;
    });

  // Same reasoning as vscode-catalog.js: mark the rejection as handled here so a
  // blocked/refused request doesn't surface as an uncaught rejection before the
  // consumer (catalog-atlassian.js) attaches its own handler. `ready` still rejects.
  ready.catch(function () {});

  window.GapAtlassian = { ready: ready };
})();
