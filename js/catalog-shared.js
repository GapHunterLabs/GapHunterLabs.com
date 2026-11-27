(function () {
  'use strict';
  var loaderStarted = Date.now();
  var domReady = new Promise(function (resolve) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', resolve, { once: true });
    else resolve();
  });

  function finishLoader(ok, count) {
    var loader = document.getElementById('siteLoader');
    if (!loader) return;
    var status = loader.querySelector('.sl-status');
    if (status) status.textContent = ok ? count + ' plugins loaded' : 'Catalog data unavailable';
    loader.classList.toggle('is-error', !ok);
    var remaining = Math.max(0, 400 - (Date.now() - loaderStarted));
    Promise.all([domReady, new Promise(function (resolve) { setTimeout(resolve, remaining); })]).then(function () {
      setTimeout(function () {
        loader.classList.add('is-done');
        loader.setAttribute('aria-busy', 'false');
        loader.setAttribute('aria-hidden', 'true');
        document.documentElement.classList.remove('boot');
        setTimeout(function () { if (loader.parentNode) loader.remove(); }, 450);
      }, ok ? 80 : 500);
    });
  }

  var ready = fetch('/data/catalog-data.json', { credentials: 'same-origin' })
    .then(function (response) {
      if (!response.ok) throw new Error('Catalog request failed: ' + response.status);
      return response.json();
    })
    .then(function (data) {
      if (!data || !Array.isArray(data.plugins)) throw new Error('Catalog response is invalid');
      var plugins = data.plugins;
  // ---- category model -----------------------------------------------
  // Hand-curated grouping of each plugin's real `niche` string into
  // top-level catalog categories. If a future niche is not mapped, it
  // falls into "Other" rather than breaking the catalog.
  var CAT_BY_KEY = {};
  function tokenColor(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  var CATEGORIES = [
    { key: 'api', label: 'API', colorToken: '--text-dim' },
    { key: 'devops', label: 'DevOps', colorToken: '--text-dim' },
    { key: 'security', label: 'Security', colorToken: '--text-dim' },
    { key: 'data', label: 'Data', colorToken: '--text-dim' },
    { key: 'quality', label: 'Code Quality', colorToken: '--text-dim' },
    { key: 'codegen', label: 'Codegen', colorToken: '--text-dim' },
    { key: 'testing', label: 'Testing', colorToken: '--text-dim' },
    { key: 'editor', label: 'Editor', colorToken: '--text-dim' },
    { key: 'other', label: 'Other', colorToken: '--text-dim' }
  ];
  CATEGORIES.forEach(function (c) {
    c.color = tokenColor(c.colorToken);
    CAT_BY_KEY[c.key] = c;
  });

  // Same stroke icons as the Hunting Field category board -- reused on
  // each plugin card's top-right badge so the board and the grid share
  // one visual language.
  var CAT_ICON_INNER = {
    api: '<path d="M-4.5-6.5v3M-1.5-6.5v3M-6-3.5h7a2 2 0 0 1 2 2v1a2 2 0 0 0 2 2h1M6 6.5v-3M1.5 6.5v-3M6 3.5H-1a2 2 0 0 1-2-2v-1a2 2 0 0 0-2-2h-1" stroke-linecap="round" stroke-linejoin="round"/>',
    devops: '<path d="M-6 0a3 3 0 1 0 6 0 3 3 0 1 1 6 0 3 3 0 1 1-6 0 3 3 0 1 0-6 0Z" stroke-linejoin="round"/>',
    security: '<path d="M0-6.5 5.5-4v4.2C5.5 3.8 2.8 6 0 6.5-2.8 6-5.5 3.8-5.5.2V-4Z" stroke-linejoin="round"/>',
    data: '<path d="M-5-3c0-1.4 2.2-2.5 5-2.5s5 1.1 5 2.5v6c0 1.4-2.2 2.5-5 2.5s-5-1.1-5-2.5Z"/><path d="M-5-3c0 1.4 2.2 2.5 5 2.5s5-1.1 5-2.5"/>',
    quality: '<path d="M0-6.5v13M-5.5-3.5h11M-5.5-3.5 -6.5 0M-5.5-3.5-4.5 0M5.5-3.5 4.5 0M5.5-3.5 6.5 0M-6.5 0a1.5 1.5 0 0 0 3 0M3.5 0a1.5 1.5 0 0 0 3 0M-2.5 6.5h5" stroke-linecap="round" stroke-linejoin="round"/>',
    codegen: '<path d="M-6-2.5-3 0-6 2.5M6-2.5 3 0 6 2.5M.8-6 -1.3-.5h2.6L-.8 6" stroke-linecap="round" stroke-linejoin="round"/>',
    testing: '<path d="M-2-6.5v4.2l-3.3 6.6a1.6 1.6 0 0 0 1.4 2.2h7.8a1.6 1.6 0 0 0 1.4-2.2L1-2.3v-4.2M-3.3-6.5h6.6M-3-1.5h6" stroke-linecap="round" stroke-linejoin="round"/>',
    editor: '<rect x="-6" y="-5" width="12" height="10" rx="1.5"/><path d="M-3.5-2h4M-3.5 0.5h2.5M2-2v2.5" stroke-linecap="round"/>',
    other: '<path d="M0-6.5v13M-6.5 0h13M-4.6-4.6 4.6 4.6M4.6-4.6-4.6 4.6" stroke-linecap="round"/>'
  };
  function catIconHtml(key) {
    var inner = CAT_ICON_INNER[key] || CAT_ICON_INNER.other;
    return '<svg viewBox="-8 -8 16 16" aria-hidden="true">' + inner + '</svg>';
  }

  // Shared line-icon set -- used by both the hero telemetry column
  // (renderStats()) and the Hunting Field plugin cards (pluginCardHtml(),
  // just the download icon) so the same visual language for "this is a
  // count" reads consistently in both places, one definition.
  var ICONS = {
    plugins: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M10 1.5 17.5 6v8L10 18.5 2.5 14V6Z"/><path d="M10 10 17.5 6M10 10v8.5M10 10 2.5 6"/></svg>',
    downloads: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2.5v10M6 9l4 4 4-4M3.5 15.5v2a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-2"/></svg>',
    visitors: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M2 10s2.8-5.5 8-5.5S18 10 18 10s-2.8 5.5-8 5.5S2 10 2 10Z"/><circle cx="10" cy="10" r="2.3"/></svg>',
    reviews: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"><path d="M3 4.5h14a1 1 0 0 1 1 1V13a1 1 0 0 1-1 1H8l-4 3.5V14H3a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"/></svg>',
    rating: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"><path d="M10 2.2 12.4 7.4 18 8.1 13.9 12 15 17.6 10 14.8 5 17.6 6.1 12 2 8.1 7.6 7.4Z"/></svg>',
    github: '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>',
    // The repository copy action uses the same outline style as the
    // other icons. A separate checkmark confirms a successful copy.
    copy: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><rect x="5.5" y="5.5" width="8.5" height="8.5" rx="1.3"/><path d="M10.5 5.5V3.3a1.3 1.3 0 0 0-1.3-1.3H3.3A1.3 1.3 0 0 0 2 3.3v5.9a1.3 1.3 0 0 0 1.3 1.3h2.2"/></svg>',
    copyCheck: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8.5 6.2 12 13 4"/></svg>',
    // JetBrains mark from simple-icons (CC0, same path as pipeline/icons.json, unmodified). Shown only on
    // buttons that open JetBrains Marketplace or a JetBrains plugin page; color via currentColor.
    jetbrains: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><path d="M7.529 8.753h-.705v.941h.706c.376 0 .565-.188.565-.471-.001-.329-.236-.47-.566-.47zm-3.2.282c0-.235-.188-.329-.471-.329h-.705v.706h.659c.329-.047.517-.141.517-.377zm6.212 1.13h.847l-.423-1.083zm-6.588 0h-.847v.706h.847c.329 0 .518-.141.518-.376s-.189-.33-.518-.33zM0 0v24h24V0H0zm8.424 3.012h3.435v.941h-1.176v2.965H9.6V3.953H8.424v-.941zm-.236 0v.894h-2.07v.612H8v.847H6.118v.612h2.118v.941H5.082l-.047-3.906h3.153zm-2.635 7.623c0 .659-.565 1.082-1.459 1.082H2.071V7.812h2.023c.471 0 .847.141 1.082.329.142.141.236.377.236.659 0 .471-.235.706-.612.894.471.141.753.424.753.941zM2.682 5.647c.188.235.376.376.612.376.282 0 .424-.188.424-.565V2.965H4.8v2.494c0 .471-.141.847-.376 1.082s-.612.377-1.083.377c-.706.047-1.082-.236-1.364-.612l.705-.659zm8.377 15.341H2.071v-1.506h8.988v1.506zm.894-9.223l-.282-.706h-1.506l-.282.706h-1.13l.02-.047h-.679l-.8-1.176h-.47v1.176H5.741V7.812h1.835c.612 0 .988.141 1.271.424.235.235.329.518.329.894 0 .612-.329.988-.8 1.224l.605.878 1.465-3.419h1.035l1.647 3.953h-1.175zm2.4-.047h-1.082V7.812h1.082v3.906zm3.953 0h-.941L15.718 9.6v2.165h-1.082V7.812h.988l1.6 2.071V7.812h1.082v3.906zm1.929.047a2.488 2.488 0 0 1-1.835-.612l.612-.706c.376.329.8.471 1.271.471.282 0 .471-.094.471-.282s-.141-.235-.659-.376c-.847-.188-1.459-.424-1.459-1.224 0-.706.565-1.271 1.506-1.271.659 0 1.176.188 1.6.518l-.565.753c-.377-.236-.753-.377-1.083-.377-.282 0-.376.094-.376.235 0 .188.141.235.659.376.894.188 1.459.471 1.459 1.224-.001.8-.612 1.271-1.601 1.271z"/></svg>',
    // 2026-09-11: real VS Code logo mark, same path already used
    // elsewhere on the site (vsx section header, footer "VS Code
    // Marketplace" link) -- reused here so the new "Download for VS
    // Code" dossier button matches those exactly instead of a
    // different approximation.
    vscode: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M23.15 2.587L18.21.21a1.494 1.494 0 0 0-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 0 0-1.276.057L.327 7.261A1 1 0 0 0 .326 8.74L3.899 12 .326 15.26a1 1 0 0 0 .001 1.479L1.65 17.94a.999.999 0 0 0 1.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 0 0 1.704.29l4.942-2.377A1.5 1.5 0 0 0 24 20.06V3.939a1.5 1.5 0 0 0-.85-1.352zm-5.146 14.861L10.826 12l7.178-5.448v10.896z"/></svg>',
    // Atlassian logomark from the official logo package (pipeline/brand/atlassian-mark.svg, path unmodified, its own
    // clip as viewBox). Shown only to say the app is available for Atlassian products; color via currentColor.
    atlassian: '<svg viewBox="7 4 34.6925 34.63" fill="currentColor"><path d="M41.3175 36.5672L25.4402 4.81262C25.1276 4.12502 24.8151 4 24.44 4C24.1275 4 23.7524 4.12502 23.3774 4.75011C21.127 8.31312 20.1269 12.4387 20.1269 16.7518C20.1269 22.7527 23.1898 28.3785 27.6905 37.4423C28.1906 38.4425 28.5656 38.63 29.4407 38.63H40.4423C41.2549 38.63 41.6925 38.3175 41.6925 37.6924C41.6925 37.3798 41.63 37.1923 41.3175 36.5672ZM18.2516 21.565C17.0014 19.6898 16.6264 19.5647 16.3138 19.5647C16.0013 19.5647 15.8138 19.6898 15.2512 20.8149L7.31255 36.6922C7.06251 37.1923 7 37.3798 7 37.6299C7 38.1299 7.43756 38.63 8.3752 38.63H19.5643C20.3144 38.63 20.877 38.0049 21.1895 36.8172C21.5646 35.317 21.6896 34.0043 21.6896 32.4416C21.6896 28.066 19.7518 23.8154 18.2516 21.565Z"/></svg>',
    // Movido aca 2026-09-22 (Fase 2 de SEO): antes vivia como una var local
    // dentro del script del dossier de catalog/index.html (unico
    // consumidor). Ese dossier ya no existe en esa pagina -- solo lo usan
    // las fichas estaticas por plugin, generadas por
    // pipeline/build_plugin_pages.py, que ahora lo lee de aca (self.icons
    // ya se parsea de este archivo) en vez de con una regex aparte.
    calendar: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="14" height="13" rx="1.5"/><path d="M3 8h14M7 2.5v3M13 2.5v3"/></svg>'
  };

  var NICHE_TO_CATEGORY = {
    'Ansible / DevOps': 'devops',
    'React Native Tooling': 'devops',
    'GitLab CI/CD': 'devops',
    'Jenkins CI/CD': 'devops',
    'Git Tooling': 'devops',
    'Nginx Config': 'devops',
    'CMake / Build Tooling': 'devops',
    'Env Config Tooling': 'devops',
    'OpenAPI/Swagger Tooling': 'api',
    'AsyncAPI Tooling': 'api',
    'GraphQL Tooling': 'api',
    'JSON Schema Tooling': 'api',
    'XSD/WSDL Tooling': 'api',
    'API Security': 'security',
    'Certificates / X.509': 'security',
    'JWT / Auth Tooling': 'security',
    'Dependency / SCA Security': 'security',
    'Firestore / Database': 'data',
    'CSV/XLSX Tooling': 'data',
    'Data Format Conversion': 'data',
    'Code Complexity': 'quality',
    'Refactoring Tools': 'quality',
    'Code Review': 'quality',
    'Inline Diagnostics': 'quality',
    'Java/Kotlin Codegen': 'codegen',
    'Codegen': 'codegen',
    'Debugging / Codegen': 'codegen',
    'Load Testing': 'testing',
    'Testing / Codegen': 'testing',
    'Diagrams': 'editor',
    'Editor Theme': 'editor',
    'Editor Productivity': 'editor',
    'JS/TS Tooling': 'editor',
    'Regex Tooling': 'editor',
    // 7 niches added 2026-08-23 -- audited and found missing (fell
    // through to 'other' via the `|| 'other'` fallback below, even
    // though every one of these clearly belongs in an existing
    // category by name alone). All 7 plugins were added 2026-08-19 as
    // part of the plan-B batch, after this map was last updated.
    'Build Tooling / Architecture': 'devops',
    'Code Quality / Feature Flags': 'quality',
    'Code Quality / Logging': 'quality',
    'Code Quality / Security': 'quality',
    'Docker / DevOps': 'devops',
    'Node.js / npm Tooling': 'devops',
    'VCS / Git Workflow': 'devops',
    // 2026-11-26: the two niches corrected in the audit keep the category they had.
    'PHP / Composer Tooling': 'devops',
    'Ruby / Bundler Tooling': 'devops',
    // 23 niches added 2026-08-27 -- 67 of 101 plugins (2/3 of the whole
    // catalog) had their `niche` field stuck at "—" (a placeholder that
    // was never filled in when those plugins were added, mostly the
    // 2026-08-19+ "factory" batches) in catalog_static_metadata.json,
    // so ALL of them fell through the `|| 'other'` fallback below --
    // this is the actual root cause behind the "Other" node in the
    // Hunting Field always looking disproportionately large/"expanded"
    // (user report, 2026-08-27): it wasn't a CSS/animation bug, the
    // These values keep plugins with specific niches in their intended
    // categories rather than falling through to "Other".
    'HTTP Client Reuse': 'devops',
    'Cloud SDK Client Reuse': 'devops',
    'Database Client Reuse': 'devops',
    'Search Client Reuse': 'devops',
    'Messaging Client Reuse': 'devops',
    'Object Mapper Reuse': 'quality',
    'Cache Client Reuse': 'devops',
    'Connection Pool Tuning': 'devops',
    'API Deprecation Tooling': 'api',
    'Spring Framework Pitfalls': 'quality',
    'Distributed Tracing': 'devops',
    'Resilience Tooling': 'devops',
    'API Reliability': 'api',
    'Secrets Detection': 'security',
    'PHP Security': 'security',
    'Ruby Security': 'security',
    'SQL Injection Detection': 'security',
    'PII / Compliance': 'security',
    'Kubernetes Tooling': 'devops',
    'Observability Tooling': 'devops',
    'gRPC Tooling': 'api',
    'Database Performance': 'quality',
    // 13 niches added 2026-09-02 for the 22-plugin batch published and
    // approved that same day (confirmed live via the Marketplace API,
    // sequential ids 33995-34018). Same discipline as the 2026-08-27
    // fix: every one of these 22 plugins got a real niche assigned
    // before this map was touched, so none of them can fall through
    // to 'other' even transiently.
    'Concurrency / Async Bugs': 'quality',
    'Caching Bugs': 'quality',
    'Exception Handling': 'quality',
    'SSRF Detection': 'security',
    'Deserialization Security': 'security',
    'Kafka / Messaging Bugs': 'quality',
    'JPA / ORM Pitfalls': 'quality',
    'Numeric Safety': 'quality',
    'Distributed Locking': 'quality',
    'IAM / Cloud Security': 'security',
    'Kubernetes Security': 'security',
    'AWS Security': 'security',
    'ReDoS Detection': 'security',
    // 9 niches added 2026-09-03 for the 20-plugin batch built that day
    // (Tier 0 through Tier -4 escalation) -- uploaded to Marketplace the
    // same day but pending JetBrains' manual review, added here on
    // purpose so none of the 20 falls through to 'other' even while
    // pending (same discipline as the 2026-08-27/2026-09-02 batches
    // above -- every plugin gets a real niche BEFORE this map is
    // touched, never after).
    'SpEL Injection Detection': 'security',
    'CI/CD Security': 'security',
    'Log Injection Detection': 'security',
    'XPath Injection Detection': 'security',
    'Resource Leak Detection': 'quality',
    'Code Quality / Encapsulation': 'quality',
    'LDAP Injection Detection': 'security',
    'Lucene Injection Detection': 'security',
    'Web Session Security': 'security'
  };

  plugins.forEach(function (p) {
    p.categoryKey = NICHE_TO_CATEGORY[p.niche] || 'other';
  });

  // Hand-written per-plugin "Gap" openings (2026-08-15 request) -- the
  // raw `why` field is real, verified evidence (never touched), but
  // ~25 of the 34 plugins share the exact same boilerplate opening
  // ("Born from real evidence in JetBrains Marketplace reviews, not
  // assumptions:" or the "Ports a pattern that's genuinely popular
  // elsewhere..." variant for the 7 "proven concept" plugins), which
  // reads as templated when you look at more than one card. Every
  // override below keeps 100% of the original facts (competitor name,
  // download counts, %, verbatim complaints) -- only the framing
  // sentence changes, so nothing here is a new claim, just a different
  // way of leading with the same evidence. The ~9 plugins NOT in this
  // map already had a distinct opening (usually a bolded competitor
  // name) and fall through to the raw `why` text unchanged.
  var GAP_OVERRIDES = {
    'ansible-companion': 'Ansible tooling\'s existing incumbents — paid and free alike — draw concrete, repeated complaints in their own JetBrains Marketplace reviews: price, YAML the plugin shouldn\'t be touching, and badly parsed Jinja2. Vault encrypt/decrypt stands out as one of the features users value most in the paid incumbent, and one of the few pieces buildable without an external language server.',
    'react-native-companion': 'React Native Console — the leading paid alternative (~430K downloads, $19-24/year) — has a recent, severe, reproducible complaint on record: "severely impacting IDE performance... frequently becomes unresponsive... thread dumps are required." Older reports add buggy iOS simulator integration and unreliable buttons. Tellingly, the same vendor\'s own free tier is rated higher than their paid one — the problem is implementation quality in the paid extras, not the feature set itself.',
    'api-security-companion': 'The market-leading security scanners carry real, recent problems on record in their own reviews — not assumptions.',
    'cert-companion': 'The leading paid certificate/keystore explorer plugin (308K downloads) has 83% of its reviews sitting at 3 stars or fewer — a documented pattern, not a guess.',
    'spreadsheet-companion': 'The leading paid spreadsheet plugin ($39/year, ~307K downloads) has half its reviews at 3 stars or fewer. Paying users report they can\'t add or delete rows, can\'t copy/paste cells, that the plugin forcibly takes over CSV files with no opt-out, that its license prompt freezes the whole IDE, and that it corrupted XLSX files on save.',
    'nginx-companion': 'The leading nginx plugin\'s paid tier (254K+ downloads) has recent complaints of locking up the IDE "even on non-nginx related edits." Its free tier repeatedly prompts for analytics/tracking consent on every startup, no matter how many times a user declines — and the historical free alternative has been abandoned since 2019.',
    'change-case-companion': 'VS Code has multiple "change case" extensions with millions of combined installs — JetBrains Marketplace had no real equivalent (confirmed by search before building this). Not a competitor-complaint build; a deliberate bet on a pattern already proven popular elsewhere.',
    'env-diff-companion': 'Env-diff/env-sync tooling already exists across other editors and CLI tools — JetBrains Marketplace had no real equivalent (confirmed by search before building this). A deliberate bet on an already-proven pattern, not a competitor-complaint build.',
    'error-lens-companion': 'VS Code\'s Error Lens extension has 10M+ installs and is one of that ecosystem\'s most-used tools — confirmed before building this that JetBrains Marketplace had no equivalent yet.',
    'json-to-code-companion': '"Paste JSON as Code"-style tools are widely used across other editors — JetBrains Marketplace had no real equivalent (confirmed by search before building this).',
    'regex-preview-companion': 'Standalone regex testers are a daily tool for many developers — but JetBrains Marketplace had no real equivalent living directly in the IDE (confirmed by search before building this).',
    'turbo-log-companion': 'VS Code\'s Turbo Console Log has millions of installs — a search before building this turned up zero results for "turbo console log," "turbo log," or "console log" as a code-generation concept anywhere in JetBrains Marketplace.'
  };

  function gapText(p) {
    return GAP_OVERRIDES[p.repo] || p.why || '—';
  }

  // Fase 3 del SuperPlan de SEO (2026-09-23): las 34 demos (33 GIF + 1
  // screenshot PNG) se descargaron de cada repo, se convirtieron
  // (ffmpeg: GIF -> MP4 H.264 + WebM VP9 a 960px/12fps con resample
  // explicito -- varias de estas GIFs solo tienen 2-4 frames reales con
  // delays largos, sin el resample el video perdia la duracion real de
  // la GIF -- mas un poster WebP del primer frame; el PNG solo se
  // reempaqueto a WebP) y se re-alojaron en este mismo repo bajo
  // /media/<slug>/, decision explicita del usuario 2026-09-23: prioriza
  // performance (deja de depender de raw.githubusercontent.com como
  // tercer origen, cada demo pesa un tercio de la GIF original en el
  // camino real de carga) sobre mantener una sola fuente de verdad en
  // el repo de cada plugin. Reemplaza al GIF_URL anterior (URLs
  // externas, sin poster, sin fallback de formato).
  //
  // react-native-companion no tiene mp4/webm -- su fuente siempre fue
  // un screenshot estatico (react-native-companion/poster.webp), no una
  // demo animada.
  //
  // 2026-08-23 audit note (aun vigente): 10 plugins no tienen entrada
  // aca -- review-companion (omision deliberada original) mas 9
  // plugins del batch plan-B 2026-08-19 que nunca tuvieron un asset real
  // que convertir. Antes de agregar sus entradas hace falta un demo real
  // en cada uno de esos 9 repos primero.
  var DEMO_MEDIA = {
    'ansible-companion': { poster: "/media/ansible-companion/poster.webp", mp4: "/media/ansible-companion/demo.mp4", webm: "/media/ansible-companion/demo.webm" },
    'api-security-companion': { poster: "/media/api-security-companion/poster.webp", mp4: "/media/api-security-companion/demo.mp4", webm: "/media/api-security-companion/demo.webm" },
    'asyncapi-companion': { poster: "/media/asyncapi-companion/poster.webp", mp4: "/media/asyncapi-companion/demo.mp4", webm: "/media/asyncapi-companion/demo.webm" },
    'background-readaction-freeze-companion': { poster: "/media/background-readaction-freeze-companion/poster.webp", mp4: "/media/background-readaction-freeze-companion/demo.mp4", webm: "/media/background-readaction-freeze-companion/demo.webm" },
    'bean-copy-companion': { poster: "/media/bean-copy-companion/poster.webp", mp4: "/media/bean-copy-companion/demo.mp4", webm: "/media/bean-copy-companion/demo.webm" },
    'cert-companion': { poster: "/media/cert-companion/poster.webp", mp4: "/media/cert-companion/demo.mp4", webm: "/media/cert-companion/demo.webm" },
    'change-case-companion': { poster: "/media/change-case-companion/poster.webp", mp4: "/media/change-case-companion/demo.mp4", webm: "/media/change-case-companion/demo.webm" },
    'cmake-companion': { poster: "/media/cmake-companion/poster.webp", mp4: "/media/cmake-companion/demo.mp4", webm: "/media/cmake-companion/demo.webm" },
    'dependency-vulnerability-companion': { poster: "/media/dependency-vulnerability-companion/poster.webp", mp4: "/media/dependency-vulnerability-companion/demo.mp4", webm: "/media/dependency-vulnerability-companion/demo.webm" },
    'disposed-project-callback-companion': { poster: "/media/disposed-project-callback-companion/poster.webp", mp4: "/media/disposed-project-callback-companion/demo.mp4", webm: "/media/disposed-project-callback-companion/demo.webm" },
    'dockerfile-layer-size-companion': { poster: "/media/dockerfile-layer-size-companion/poster.webp", mp4: "/media/dockerfile-layer-size-companion/demo.mp4", webm: "/media/dockerfile-layer-size-companion/demo.webm" },
    'env-diff-companion': { poster: "/media/env-diff-companion/poster.webp", mp4: "/media/env-diff-companion/demo.mp4", webm: "/media/env-diff-companion/demo.webm" },
    'env-var-missing-companion': { poster: "/media/env-var-missing-companion/poster.webp", mp4: "/media/env-var-missing-companion/demo.mp4", webm: "/media/env-var-missing-companion/demo.webm" },
    'error-lens-companion': { poster: "/media/error-lens-companion/poster.webp", mp4: "/media/error-lens-companion/demo.mp4", webm: "/media/error-lens-companion/demo.webm" },
    'firestore-companion': { poster: "/media/firestore-companion/poster.webp", mp4: "/media/firestore-companion/demo.mp4", webm: "/media/firestore-companion/demo.webm" },
    'format-converter-companion': { poster: "/media/format-converter-companion/poster.webp", mp4: "/media/format-converter-companion/demo.mp4", webm: "/media/format-converter-companion/demo.webm" },
    'git-hygiene-companion': { poster: "/media/git-hygiene-companion/poster.webp", mp4: "/media/git-hygiene-companion/demo.mp4", webm: "/media/git-hygiene-companion/demo.webm" },
    'gitlab-ci-companion': { poster: "/media/gitlab-ci-companion/poster.webp", mp4: "/media/gitlab-ci-companion/demo.mp4", webm: "/media/gitlab-ci-companion/demo.webm" },
    'graphql-companion': { poster: "/media/graphql-companion/poster.webp", mp4: "/media/graphql-companion/demo.mp4", webm: "/media/graphql-companion/demo.webm" },
    'highlight-companion': { poster: "/media/highlight-companion/poster.webp", mp4: "/media/highlight-companion/demo.mp4", webm: "/media/highlight-companion/demo.webm" },
    'import-cost-companion': { poster: "/media/import-cost-companion/poster.webp", mp4: "/media/import-cost-companion/demo.mp4", webm: "/media/import-cost-companion/demo.webm" },
    'jenkinsfile-companion': { poster: "/media/jenkinsfile-companion/poster.webp", mp4: "/media/jenkinsfile-companion/demo.mp4", webm: "/media/jenkinsfile-companion/demo.webm" },
    'json-schema-companion': { poster: "/media/json-schema-companion/poster.webp", mp4: "/media/json-schema-companion/demo.mp4", webm: "/media/json-schema-companion/demo.webm" },
    'json-to-code-companion': { poster: "/media/json-to-code-companion/poster.webp", mp4: "/media/json-to-code-companion/demo.mp4", webm: "/media/json-to-code-companion/demo.webm" },
    'jwt-companion': { poster: "/media/jwt-companion/poster.webp", mp4: "/media/jwt-companion/demo.mp4", webm: "/media/jwt-companion/demo.webm" },
    'k6-companion': { poster: "/media/k6-companion/poster.webp", mp4: "/media/k6-companion/demo.mp4", webm: "/media/k6-companion/demo.webm" },
    'log-format-string-companion': { poster: "/media/log-format-string-companion/poster.webp", mp4: "/media/log-format-string-companion/demo.mp4", webm: "/media/log-format-string-companion/demo.webm" },
    'lucene-query-injection-companion': { poster: "/media/lucene-query-injection-companion/poster.webp", mp4: "/media/lucene-query-injection-companion/demo.mp4", webm: "/media/lucene-query-injection-companion/demo.webm" },
    'material-companion': { poster: "/media/material-companion/poster.webp", mp4: "/media/material-companion/demo.mp4", webm: "/media/material-companion/demo.webm" },
    'merge-conflict-leftover-companion': { poster: "/media/merge-conflict-leftover-companion/poster.webp", mp4: "/media/merge-conflict-leftover-companion/demo.mp4", webm: "/media/merge-conflict-leftover-companion/demo.webm" },
    'mermaid-companion': { poster: "/media/mermaid-companion/poster.webp", mp4: "/media/mermaid-companion/demo.mp4", webm: "/media/mermaid-companion/demo.webm" },
    'nginx-companion': { poster: "/media/nginx-companion/poster.webp", mp4: "/media/nginx-companion/demo.mp4", webm: "/media/nginx-companion/demo.webm" },
    'openapi-companion': { poster: "/media/openapi-companion/poster.webp", mp4: "/media/openapi-companion/demo.mp4", webm: "/media/openapi-companion/demo.webm" },
    'php-composer-script-companion': { poster: "/media/php-composer-script-companion/poster.webp", mp4: "/media/php-composer-script-companion/demo.mp4", webm: "/media/php-composer-script-companion/demo.webm" },
    'prometheus-metric-naming-companion': { poster: "/media/prometheus-metric-naming-companion/poster.webp", mp4: "/media/prometheus-metric-naming-companion/demo.mp4", webm: "/media/prometheus-metric-naming-companion/demo.webm" },
    'react-native-companion': { poster: "/media/react-native-companion/poster.webp", mp4: "/media/react-native-companion/demo.mp4", webm: "/media/react-native-companion/demo.webm" },
    'refactor-simulator': { poster: "/media/refactor-simulator/poster.webp", mp4: "/media/refactor-simulator/demo.mp4", webm: "/media/refactor-simulator/demo.webm" },
    'regex-preview-companion': { poster: "/media/regex-preview-companion/poster.webp", mp4: "/media/regex-preview-companion/demo.mp4", webm: "/media/regex-preview-companion/demo.webm" },
    'review-companion': { poster: "/media/review-companion/poster.webp", mp4: "/media/review-companion/demo.mp4", webm: "/media/review-companion/demo.webm" },
    'semver-bump-mismatch-companion': { poster: "/media/semver-bump-mismatch-companion/poster.webp", mp4: "/media/semver-bump-mismatch-companion/demo.mp4", webm: "/media/semver-bump-mismatch-companion/demo.webm" },
    'spreadsheet-companion': { poster: "/media/spreadsheet-companion/poster.webp", mp4: "/media/spreadsheet-companion/demo.mp4", webm: "/media/spreadsheet-companion/demo.webm" },
    'sql-concatenation-companion': { poster: "/media/sql-concatenation-companion/poster.webp", mp4: "/media/sql-concatenation-companion/demo.mp4", webm: "/media/sql-concatenation-companion/demo.webm" },
    'test-scaffold-companion': { poster: "/media/test-scaffold-companion/poster.webp", mp4: "/media/test-scaffold-companion/demo.mp4", webm: "/media/test-scaffold-companion/demo.webm" },
    'theme-companion': { poster: "/media/theme-companion/poster.webp", mp4: "/media/theme-companion/demo.mp4", webm: "/media/theme-companion/demo.webm" },
    'turbo-log-companion': { poster: "/media/turbo-log-companion/poster.webp", mp4: "/media/turbo-log-companion/demo.mp4", webm: "/media/turbo-log-companion/demo.webm" },
    'unused-npm-script-companion': { poster: "/media/unused-npm-script-companion/poster.webp", mp4: "/media/unused-npm-script-companion/demo.mp4", webm: "/media/unused-npm-script-companion/demo.webm" },
    'webhook-signature-companion': { poster: "/media/webhook-signature-companion/poster.webp", mp4: "/media/webhook-signature-companion/demo.mp4", webm: "/media/webhook-signature-companion/demo.webm" },
    'xsd-companion': { poster: "/media/xsd-companion/poster.webp", mp4: "/media/xsd-companion/demo.mp4", webm: "/media/xsd-companion/demo.webm" }
  };

  // Real, derivable technical facts (2026-08-15 Facts-panel rework) --
  // never fabricated: platform is parsed straight from the plugin's own
  // pitch (nearly every one starts "IntelliJ... plugin."), Marketplace
  // ID is parsed from its own marketplaceUrl.
  function platformOf(p) {
    var m = (p.pitch || '').match(/^(IntelliJ[^.]*?plugin)\s*[.(]/);
    return m ? m[1] : 'IntelliJ-family';
  }
  function marketplaceId(p) {
    if (!p.marketplaceUrl) return null;
    var m = p.marketplaceUrl.match(/\/plugin\/(\d+)-/);
    return m ? m[1] : null;
  }
  function growthFactLine(p) {
    if (p.growth == null || p.growthFrom == null || p.downloads == null) return 'New listing';
    var arrow = p.growth > 0 ? '▲ +' : p.growth < 0 ? '▼ ' : '';
    return arrow + p.growth.toFixed(1) + '% since ' + p.growthSince + ' (' + p.growthFrom + '→' + p.downloads + ')';
  }

  // ---- shared helpers ---------------------------------------------
  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  // esc() only neutralizes HTML metacharacters -- it does NOT validate a
  // URL's scheme, so on its own `esc(p.marketplaceUrl)` would still render
  // a working `href="javascript:..."` if that field ever arrived malformed.
  // Every dynamic href/src on this page goes
  // through this gate first: only http(s) survives, anything else
  // (javascript:, data:, vbscript:, a bare "//host" scheme-relative link)
  // is replaced with '#' instead of ever reaching the DOM.
  function safeUrl(s) {
    if (s == null) return '#';
    var str = String(s).trim();
    return /^https?:\/\//i.test(str) ? str : '#';
  }

  function mdInline(s) {
    var out = esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Convert complete backtick pairs to code and preserve an unmatched
    // trailing backtick as literal text.
    var parts = out.split('`');
    if (parts.length < 3) return out;
    var rebuilt = parts[0];
    var i = 1;
    for (; i + 1 < parts.length; i += 2) rebuilt += '<code>' + parts[i] + '</code>' + parts[i + 1];
    if (i < parts.length) rebuilt += '`' + parts[i];
    return rebuilt;
  }

  function byRepo(repo) {
    for (var i = 0; i < plugins.length; i++) if (plugins[i].repo === repo) return plugins[i];
    return null;
  }

  function pricingLabel(p, isPending) {
    if (isPending) return { cls: 'pending', text: 'Pending' };
    if (p === 'FREE') return { cls: 'free', text: 'Free' };
    if (p === 'FREEMIUM') return { cls: 'freemium', text: 'Freemium' };
    if (p === 'PAID') return { cls: 'paid', text: 'Paid' };
    // Unknown upstream pricing values remain displayable; every caller
    // escapes this text before inserting it into HTML.
    return { cls: 'free', text: p || '—' };
  }

  // Below this baseline, a percentage badge is more misleading than
  // informative -- 2026-08-23 audit finding: 1->20 downloads reads as
  // "▲ 1900.0%", and six unrelated plugins all show the identical
  // "▲ 300.0%" purely because they all happened to go 2->8. The
  // arithmetic is correct, but the badge visually overstates what's
  // really a handful of raw downloads. Below this floor, show the raw
  // delta instead ("+18") -- still real signal, without implying a
  // growth rate that a tiny sample can't actually support.
  var GROWTH_PERCENT_MIN_BASELINE = 10;

  function growthMarkup(p) {
    var g = p.growth;
    var title = p.growthSince ? ('Since ' + p.growthSince + ': ' + p.growthFrom + ' → ' + p.downloads) : 'No earlier snapshot';
    var titleAttr = ' title="' + esc(title) + '"';
    if (g === null || g === undefined) return '<span class="growth flat"' + titleAttr + '>—</span>';
    if (p.growthFrom != null && p.growthFrom < GROWTH_PERCENT_MIN_BASELINE && p.downloads != null) {
      var delta = p.downloads - p.growthFrom;
      if (delta > 0) return '<span class="growth up"' + titleAttr + '>▲ +' + delta + '</span>';
      if (delta < 0) return '<span class="growth down"' + titleAttr + '>▼ ' + delta + '</span>';
      return '<span class="growth flat"' + titleAttr + '>±0</span>';
    }
    if (g > 0) return '<span class="growth up"' + titleAttr + '>▲ ' + g.toFixed(1) + '%</span>';
    if (g < 0) return '<span class="growth down"' + titleAttr + '>▼ ' + Math.abs(g).toFixed(1) + '%</span>';
    return '<span class="growth flat"' + titleAttr + '>0%</span>';
  }


      var api = {
        data: data,
        plugins: plugins,
        CATEGORIES: CATEGORIES,
        CAT_BY_KEY: CAT_BY_KEY,
        ICONS: ICONS,
        DEMO_MEDIA: DEMO_MEDIA,
        esc: esc,
        safeUrl: safeUrl,
        mdInline: mdInline,
        pricingLabel: pricingLabel,
        growthMarkup: growthMarkup,
        byRepo: byRepo,
        catIconHtml: catIconHtml,
        gapText: gapText,
        platformOf: platformOf,
        marketplaceId: marketplaceId,
        growthFactLine: growthFactLine
      };
      finishLoader(true, plugins.length);
      return api;
    })
    .catch(function (error) {
      finishLoader(false, 0);
      document.dispatchEvent(new CustomEvent('catalogerror', { detail: error }));
      throw error;
    });

  window.GapCatalog = { ready: ready };
})();
