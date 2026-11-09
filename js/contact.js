/* Contact desk: los formularios arman un enlace de "nuevo issue" de GitHub prellenado (sin backend).
   Movido desde un <script> inline el 2026-09-24 para poder quitar
   'unsafe-inline' del script-src de la CSP (ver DOCUMENTATION.md). */
// Contact desk: 3 quick actions (Submit a gap / Report a plugin /
// Partnership) cada uno con su propio set de campos -- "Security
// report" NO es un form, es un link directo a security.html#sec-report
// (esa página ya instruye no abrir un issue público de seguridad, así
// que este form nunca debe generar uno). Sin backend: el submit arma
// un link de "crear issue" en el repo del sitio con los campos
// prellenados en título/cuerpo -- llega por notificación default de
// GitHub a la cuenta que ya opera el repo (contact@gaphunterlabs.com).
(function () {
  var REPO_ISSUES = 'https://github.com/GapHunterLabs/GapHunterLabs.github.io/issues/new';
  // 2026-09-27: bilingue -- la version en espanol (/es/contacto/) usa este
  // mismo script; el idioma sale de <html lang>.
  var ES = document.documentElement.lang === 'es';
  function t(en, es) { return ES ? es : en; }
  var CATEGORY_OPTIONS = ES
    ? ['API', 'DevOps', 'Seguridad', 'Datos', 'Calidad de código', 'Generación de código', 'Pruebas', 'Editor', 'Otra']
    : ['API', 'DevOps', 'Security', 'Data', 'Code Quality', 'Codegen', 'Testing', 'Editor', 'Other'];
  var PLATFORM_OPTIONS = [t('JetBrains (IntelliJ family)', 'JetBrains (familia IntelliJ)'), 'VS Code', t('Other', 'Otra')];
  // 2026-11-08: the "What do you need?" options are the four published services plus a way out. The keys are
  // what a service page passes as ?service= so the visitor does not pick the service twice.
  var SERVICES = [
    ['audit', t('Plugin performance audit', 'Auditoría de rendimiento de un plugin')],
    ['updates', t('Plugin update for new IDE versions', 'Actualización de un plugin para versiones nuevas del IDE')],
    ['depsec', t('Dependency and CI/CD security review', 'Revisión de seguridad de dependencias y CI/CD')],
    ['custom', t('Custom plugins and inspections', 'Plugins e inspecciones a medida')],
    ['other', t('Something else', 'Otra cosa')]
  ];
  var SPONSOR_LEVELS = ['Silver', 'Gold', 'Platinum', t('Not sure yet', 'Aún no lo sé')];
  var SLUG_RE = /^[a-z0-9][a-z0-9-]{0,80}$/;

  var CONFIGS = {
    gap: {
      label: 'gap-report',
      title: t('Submit a gap', 'Proponer una brecha'),
      sub: t('What are you missing? The more detail, the better.', '¿Qué te falta? Cuanto más detalle, mejor.'),
      submitLabel: t('Submit a gap', 'Proponer una brecha'),
      fields: [
        { name: 'category', label: t('Category', 'Categoría'), prompt: t('Select a category', 'Elige una categoría'), type: 'select', options: CATEGORY_OPTIONS, required: true, half: true },
        { name: 'platform', label: t('Platform', 'Plataforma'), prompt: t('Select a platform', 'Elige una plataforma'), type: 'select', options: PLATFORM_OPTIONS, required: true, half: true },
        { name: 'problem', label: t("What's the problem?", '¿Cuál es el problema?'), type: 'textarea', max: 1000, required: true, placeholder: t('Describe the issue, friction or missing capability…', 'Describe el problema, la fricción o la capacidad que falta…') },
        { name: 'existing', label: t('Existing solution', 'Solución existente'), type: 'textarea', max: 500, required: false, placeholder: t('Have you tried any existing tools or workarounds?', '¿Probaste alguna herramienta o solución alternativa?') },
        { name: 'evidence', label: t('Evidence / references', 'Evidencia / referencias'), type: 'textarea', max: 500, required: false, placeholder: t('Links, examples, or relevant documentation…', 'Enlaces, ejemplos o documentación relevante…') }
      ]
    },
    plugin: {
      label: 'plugin-feedback',
      title: t('Report a plugin', 'Reportar un plugin'),
      sub: t('Tell me which plugin and what happened.', 'Cuéntame qué plugin y qué pasó.'),
      submitLabel: t('Report a plugin', 'Reportar un plugin'),
      fields: [
        { name: 'plugin', label: t('Plugin name', 'Nombre del plugin'), type: 'text', required: true, placeholder: t('e.g. GitLab CI Companion', 'p. ej. GitLab CI Companion') },
        { name: 'problem', label: t('What happened?', '¿Qué pasó?'), type: 'textarea', max: 1000, required: true, placeholder: t('Bug, missing feature, or unexpected behavior…', 'Error, función que falta o comportamiento inesperado…') }
      ]
    },
    // 2026-09-27: "hire" y "partnership" son leads privados -- van por
    // correo (mailto:) y NUNCA como issue publico de GitHub.
    hire: {
      label: 'hire',
      mail: true,
      subjectPrefix: t('Engagement: ', 'Encargo: '),
      title: t('Start an engagement', 'Iniciar un encargo'),
      sub: t('Describe the problem or the work. Within 2 business days I reply in writing with the scope, delivery date and price, before any work starts.',
             'Describe el problema o el trabajo. En 2 días hábiles te respondo por escrito con el alcance, la fecha de entrega y el precio, antes de empezar cualquier trabajo.'),
      submitLabel: t('Email me', 'Escríbeme'),
      fields: [
        { name: 'org', label: t('Company or project', 'Empresa o proyecto'), type: 'text', required: true, half: true, placeholder: t('Your company, team or project', 'Tu empresa, equipo o proyecto') },
        { name: 'email', label: t('Your email', 'Tu correo'), type: 'email', required: true, half: true, placeholder: t('So I can reply to you', 'Para poder responderte') },
        { name: 'service', label: t('What do you need?', '¿Qué necesitas?'), prompt: t('Select one', 'Elige una opción'), type: 'select', required: true,
          options: SERVICES.map(function (s) { return s[1]; }) },
        { name: 'target', label: t('Plugin, repository or system', 'Plugin, repositorio o sistema'), type: 'text', required: false, placeholder: t('A name or a URL', 'Un nombre o una URL') },
        { name: 'message', label: t('What you are seeing', 'Qué estás viendo'), type: 'textarea', max: 1500, required: true, placeholder: t('Symptoms, versions, links to tickets or reports, and any deadline…', 'Síntomas, versiones, enlaces a tickets o reportes, y cualquier fecha límite…') }
      ]
    },
    // 2026-11-08: team licenses and company sponsorships had no form of their own (they went through "hire" and
    // "partnership"). Both are private leads, so they go by email like those two.
    license: {
      label: 'license',
      mail: true,
      subjectPrefix: t('Team licenses: ', 'Licencias de equipo: '),
      title: t('Team licenses', 'Licencias de equipo'),
      sub: t('Seats of a paid plugin for your whole team. JetBrains Marketplace sells the licenses and handles quotes, invoices and keys; tell me the plugin and how many seats you need, and I reply personally by email.',
             'Licencias de un plugin de pago para todo tu equipo. JetBrains Marketplace vende las licencias y se encarga de cotizaciones, facturas y claves; dime el plugin y cuántas licencias necesitas, y te respondo personalmente por correo.'),
      submitLabel: t('Send by email', 'Enviar por correo'),
      fields: [
        { name: 'org', label: t('Company or team', 'Empresa o equipo'), type: 'text', required: true, half: true, placeholder: t('Your company or team', 'Tu empresa o equipo') },
        { name: 'email', label: t('Your email', 'Tu correo'), type: 'email', required: true, half: true, placeholder: t('So I can reply to you', 'Para poder responderte') },
        { name: 'plugin', label: t('Plugin', 'Plugin'), type: 'text', required: true, half: true, placeholder: t('e.g. openapi-companion', 'p. ej. openapi-companion') },
        { name: 'seats', label: t('How many people?', '¿Cuántas personas?'), type: 'text', required: false, half: true, placeholder: t('e.g. 12', 'p. ej. 12') },
        { name: 'message', label: t('Anything else', 'Algo más'), type: 'textarea', max: 1000, required: false, placeholder: t('Billing country, renewal date, questions…', 'País de facturación, fecha de renovación, preguntas…') }
      ]
    },
    sponsor: {
      label: 'sponsor',
      mail: true,
      subjectPrefix: t('Sponsorship: ', 'Patrocinio: '),
      title: t('Company sponsorship', 'Patrocinio de empresa'),
      sub: t('Tell me the level you have in mind and whether your company needs an invoice. This goes by email, never as a public issue.',
             'Cuéntame qué nivel tienes en mente y si tu empresa necesita factura. Esto va por correo, nunca como un issue público.'),
      submitLabel: t('Send by email', 'Enviar por correo'),
      fields: [
        { name: 'org', label: t('Company', 'Empresa'), type: 'text', required: true, half: true, placeholder: t('Your company or project', 'Tu empresa o proyecto') },
        { name: 'email', label: t('Your email', 'Tu correo'), type: 'email', required: true, half: true, placeholder: t('So I can reply to you', 'Para poder responderte') },
        { name: 'level', label: t('Level', 'Nivel'), prompt: t('Select one', 'Elige una opción'), type: 'select', required: true, options: SPONSOR_LEVELS },
        { name: 'message', label: t('Anything else', 'Algo más'), type: 'textarea', max: 1000, required: false, placeholder: t('Invoice details, the plugin you care about, questions…', 'Datos de factura, el plugin que te interesa, preguntas…') }
      ]
    },
    partnership: {
      label: 'partnership',
      mail: true,
      subjectPrefix: t('Partnership: ', 'Alianza: '),
      title: t('Partnership', 'Alianzas'),
      sub: t('Tell me about your organization and what you have in mind. This goes by email, never as a public issue.',
             'Cuéntame sobre tu organización y lo que tienes en mente. Esto va por correo, nunca como un issue público.'),
      submitLabel: t('Send by email', 'Enviar por correo'),
      fields: [
        { name: 'org', label: t('Organization', 'Organización'), type: 'text', required: true, half: true, placeholder: t('Your company or project', 'Tu empresa o proyecto') },
        { name: 'email', label: t('Your email', 'Tu correo'), type: 'email', required: true, half: true, placeholder: t('So I can reply to you', 'Para poder responderte') },
        { name: 'message', label: t('Message', 'Mensaje'), type: 'textarea', max: 1000, required: true, placeholder: t('What kind of partnership are you thinking of?', '¿Qué tipo de alianza tienes en mente?') }
      ]
    }
  };
  var CONTACT_EMAIL = 'contact@gaphunterlabs.com';
  // Backend del formulario: Web3Forms (gratis, sin servidor propio). La access
  // key es PUBLICA por diseno (va en el cliente), no es un secreto. Los envios
  // de "hire"/"partnership" van por aqui -> correo a contact@gaphunterlabs.com.
  // "gap"/"plugin" siguen abriendo un issue publico de GitHub a proposito.
  var WEB3FORMS_KEY = 'afb6ebc1-d92b-46b6-ab6c-d78421e309cd';
  var WEB3FORMS_ENDPOINT = 'https://api.web3forms.com/submit';

  var fieldsHost = document.getElementById('cfFields');
  var titleEl = document.getElementById('cfTitle');
  var subEl = document.getElementById('cfSub');
  var submitBtn = document.getElementById('cfSubmit');
  var statusEl = document.getElementById('cfStatus');
  var form = document.getElementById('contactForm');
  var qaItems = document.querySelectorAll('.qa-item[data-target]');
  var currentKey = 'gap';
  if (!fieldsHost || !form) return;

  // 2026-10-27: antes usaba textContent->innerHTML, que NO escapa comillas, y esc() se usa dentro de atributos
  // (placeholder="...", value="..."). Hoy ningun texto fijo las trae, pero bastaba una para romper el atributo.
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function renderFields(key) {
    var cfg = CONFIGS[key];
    var html = '';
    var i = 0;
    while (i < cfg.fields.length) {
      var f = cfg.fields[i];
      if (f.half && cfg.fields[i + 1] && cfg.fields[i + 1].half) {
        html += '<div class="cf-row">' + fieldHtml(f) + fieldHtml(cfg.fields[i + 1]) + '</div>';
        i += 2;
      } else {
        html += fieldHtml(f);
        i += 1;
      }
    }
    fieldsHost.innerHTML = html;
    fieldsHost.querySelectorAll('textarea[data-max]').forEach(wireCounter);
  }

  function fieldHtml(f) {
    var reqMark = f.required ? ' <span class="req">*</span>' : ' <span style="color:var(--text-faint);font-weight:400">' + t('(optional)', '(opcional)') + '</span>';
    var label = '<label for="cf-' + esc(f.name) + '">' + esc(f.label) + reqMark + '</label>';
    var body = '';
    if (f.type === 'select') {
      body = '<select id="cf-' + esc(f.name) + '" name="' + esc(f.name) + '"' + (f.required ? ' required' : '') + '>' +
        '<option value="">' + esc(f.prompt || t('Select one', 'Elige una opción')) + '</option>' +
        f.options.map(function (o) { return '<option value="' + esc(o) + '">' + esc(o) + '</option>'; }).join('') +
        '</select>';
    } else if (f.type === 'textarea') {
      body = '<textarea id="cf-' + esc(f.name) + '" name="' + esc(f.name) + '" data-max="' + Number(f.max) + '" placeholder="' + esc(f.placeholder || '') + '"' + (f.required ? ' required' : '') + '></textarea>' +
        '<span class="cf-counter" data-counter-for="cf-' + esc(f.name) + '">0/' + Number(f.max) + '</span>';
    } else {
      var inputType = f.type === 'email' ? 'email' : 'text';
      var auto = f.type === 'email' ? ' autocomplete="email" inputmode="email"' : '';
      body = '<input type="' + inputType + '" id="cf-' + esc(f.name) + '" name="' + esc(f.name) + '"' + auto + ' placeholder="' + esc(f.placeholder || '') + '"' + (f.required ? ' required' : '') + '>';
    }
    return '<div class="cf-field">' + label + body + '</div>';
  }

  function wireCounter(ta) {
    var max = parseInt(ta.getAttribute('data-max'), 10);
    var counter = fieldsHost.querySelector('[data-counter-for="' + ta.id + '"]');
    if (!counter) return;
    function update() {
      var len = ta.value.length;
      counter.textContent = Math.min(len, max) + '/' + max;
      counter.style.color = len > max ? 'var(--warn, #FFB020)' : '';
    }
    ta.addEventListener('input', update);
    update();
  }

  function activate(key) {
    currentKey = key;
    var cfg = CONFIGS[key];
    titleEl.textContent = cfg.title;
    subEl.textContent = cfg.sub;
    submitBtn.childNodes[0].nodeValue = cfg.submitLabel + ' ';
    renderFields(key);
    qaItems.forEach(function (btn) {
      var on = btn.getAttribute('data-target') === key;
      btn.classList.toggle('is-active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  qaItems.forEach(function (btn) {
    btn.addEventListener('click', function () { activate(btn.getAttribute('data-target')); });
  });

  function track(path) {
    try { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: path, event: true }); } catch (err) { /* opcional */ }
  }

  function copyText(text, btn) {
    function done(ok) {
      if (!btn) return;
      var original = btn.getAttribute('data-label') || btn.textContent;
      btn.setAttribute('data-label', original);
      btn.textContent = ok ? t('Copied', 'Copiado') : t('Select and copy manually', 'Selecciona y copia a mano');
      setTimeout(function () { btn.textContent = original; }, 2000);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
    } else {
      done(false);
    }
  }

  // Respaldo del mailto: en equipos sin cliente de correo el clic puede no
  // hacer nada, asi que el mensaje armado queda visible para copiarlo.
  function showFallback(subject, body) {
    var host = document.getElementById('cfFallback');
    if (!host) return;
    host.innerHTML =
      '<p><strong>' + t('If your mail app didn\u2019t open,', 'Si tu app de correo no se abri\u00f3,') + '</strong> ' +
      t('copy this message and send it to ', 'copia este mensaje y env\u00edalo a ') +
      '<a href="mailto:' + CONTACT_EMAIL + '">' + CONTACT_EMAIL + '</a>.</p>' +
      '<textarea readonly rows="8" aria-label="' + t('Prepared message', 'Mensaje preparado') + '">' + esc(t('Subject: ', 'Asunto: ') + subject + '\n\n' + body) + '</textarea>' +
      '<div class="cf-fallback-actions">' +
      '<button type="button" class="btn" data-copy-kind="email">' + t('Copy email', 'Copiar correo') + '</button>' +
      '<button type="button" class="btn primary" data-copy-kind="message">' + t('Copy message', 'Copiar mensaje') + '</button></div>';
    host.hidden = false;
    host.querySelector('[data-copy-kind="email"]').addEventListener('click', function (ev) { copyText(CONTACT_EMAIL, ev.currentTarget); track('contact-copy-email'); });
    host.querySelector('[data-copy-kind="message"]').addEventListener('click', function (ev) { copyText(t('Subject: ', 'Asunto: ') + subject + '\n\n' + body, ev.currentTarget); track('contact-copy-message'); });
  }

  function setStatus(kind, msg) {
    if (!statusEl) return;
    statusEl.hidden = false;
    statusEl.className = 'cf-status is-' + kind;
    statusEl.textContent = msg;
  }

  // Envio real por backend (Web3Forms) para los formularios de lead
  // (hire/partnership). Sin cliente de correo: POST directo, confirmacion
  // accesible en #cfStatus (role=status aria-live), y si algo falla se cae al
  // respaldo de copiar/pegar hacia el correo.
  function sendViaBackend(cfg, data, subject, body) {
    var payload = new FormData();
    payload.append('access_key', WEB3FORMS_KEY);
    payload.append('subject', subject);
    payload.append('from_name', 'Gap Hunter Labs — ' + cfg.title);
    var email = data.get('email');
    if (email) payload.append('replyto', String(email));
    payload.append('botcheck', '');              // honeypot: un bot lo marca -> Web3Forms lo rechaza
    payload.append('message', body);             // cuerpo legible con todos los campos
    submitBtn.disabled = true;
    setStatus('pending', t('Sending…', 'Enviando…'));
    track('contact-' + cfg.label + '-send');
    fetch(WEB3FORMS_ENDPOINT, { method: 'POST', headers: { 'Accept': 'application/json' }, body: payload })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        submitBtn.disabled = false;
        if (res && res.success) {
          setStatus('ok', t('Thanks — your message reached me. I reply personally by email.',
                            'Gracias — tu mensaje me llegó. Respondo personalmente por correo.'));
          form.reset();
          fieldsHost.querySelectorAll('textarea[data-max]').forEach(function (ta) { ta.dispatchEvent(new Event('input')); });
          track('contact-' + cfg.label + '-ok');
        } else {
          setStatus('error', t('Something went wrong sending the form. You can email me directly:',
                               'Algo falló al enviar el formulario. Puedes escribirme directamente:'));
          showFallback(subject, body);
        }
      })
      .catch(function () {
        submitBtn.disabled = false;
        setStatus('error', t('Could not reach the form service. You can email me directly:',
                             'No se pudo contactar el servicio del formulario. Puedes escribirme directamente:'));
        showFallback(subject, body);
      });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var cfg = CONFIGS[currentKey];
    var data = new FormData(form);
    var titleSeed = data.get(cfg.fields[0].name) || cfg.title;
    if (cfg.mail) {
      var subject = cfg.subjectPrefix + String(titleSeed).slice(0, 80);
      var body = cfg.fields.map(function (f) {
        var v = data.get(f.name);
        return f.label + ':\n' + (v ? String(v) : t('(not provided)', '(sin completar)'));
      }).join('\n\n');
      sendViaBackend(cfg, data, subject, body);
      return;
    }
    var issueTitle = '[' + cfg.label + '] ' + String(titleSeed).slice(0, 80);
    var bodyLines = cfg.fields.map(function (f) {
      var v = data.get(f.name);
      return '**' + f.label + '**\n' + (v ? String(v) : '_(not provided)_');
    });
    var issueBody = bodyLines.join('\n\n');
    var url = REPO_ISSUES + '?title=' + encodeURIComponent(issueTitle) +
      '&body=' + encodeURIComponent(issueBody) +
      '&labels=' + encodeURIComponent(cfg.label);
    track('contact-' + cfg.label + '-send');
    window.open(url, '_blank', 'noopener');
  });

  document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () { copyText(btn.getAttribute('data-copy'), btn); track('contact-copy-email'); });
  });

  // ?intent=hire|license|sponsor|partnership|plugin|gap, with ?service=<key> (a service page), ?plugin=<slug>
  // (a plugin page) or ?need=<text> (a catalog search with no results). Only known values are used: an unknown
  // intent opens "hire", an unknown service or a malformed slug is ignored, and every value is written as text,
  // never as markup.
  var params = new URLSearchParams(window.location.search);
  var intent = params.get('intent');
  var key = intent && Object.prototype.hasOwnProperty.call(CONFIGS, intent) ? intent : 'hire';
  activate(key);
  var slug = params.get('plugin');
  if (slug && !SLUG_RE.test(slug)) slug = null;
  var need = params.get('need');

  function field(name) { return fieldsHost.querySelector('[name="' + name + '"]'); }
  function fill(el, value) { if (el && value) { el.value = value; el.dispatchEvent(new Event('input')); } }

  if (key === 'license' || key === 'plugin') {
    fill(field('plugin'), slug);
  } else if (key === 'hire') {
    var service = params.get('service');
    var match = SERVICES.filter(function (s) { return s[0] === service; })[0];
    if (match) field('service').value = match[1];
    var prefill = slug ? t('About the plugin: ', 'Sobre el plugin: ') + slug + '\n\n'
      : need ? t('I searched the catalog for "', 'Busqué en el catálogo "') + need.slice(0, 120) + t('" and found nothing.\n\n', '" y no encontré nada.\n\n') : '';
    fill(field('message'), prefill);
  }
})();
