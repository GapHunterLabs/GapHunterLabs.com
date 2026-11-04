/* Blog (/writing/): month calendar built from the dates already on the cards (<li data-ev-date>).
   Month and weekday names come from Intl in the page language; every other label is read from the
   translated <p data-cal-t> nodes in the page, so this file holds no English or Spanish text. */
(function () {
  'use strict';
  var root = document.querySelector('[data-cal]');
  if (!root || !window.Intl) return;

  var lang = document.documentElement.lang || 'en';
  var T = function (k) { var n = root.querySelector('[data-cal-t="' + k + '"]'); return n ? n.textContent.trim() : k; };
  var fmt = function (o) { o.timeZone = 'UTC'; return new Intl.DateTimeFormat(lang, o); };
  var fMonth = fmt({ month: 'long', year: 'numeric' });
  var fFull = fmt({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  var fWeek = fmt({ weekday: 'short' });
  var cap = function (s) { return s.charAt(0).toLocaleUpperCase(lang) + s.slice(1); };
  var utc = function (iso) { var p = iso.split('-'); return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])); };
  var iso = function (y, m, d) { return y + '-' + String(m + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0'); };

  // date -> [{ev, title, href}]
  var byDate = {};
  Array.prototype.forEach.call(document.querySelectorAll('.blog-item'), function (card) {
    var t = card.querySelector('.case-title');
    var title = t ? t.textContent.trim() : '';
    Array.prototype.forEach.call(card.querySelectorAll('[data-ev-date]'), function (li) {
      var d = li.getAttribute('data-ev-date');
      (byDate[d] = byDate[d] || []).push({ ev: li.getAttribute('data-ev'), title: title, href: '#' + card.id });
    });
  });
  var dates = Object.keys(byDate).sort();
  if (!dates.length) return;

  var first = utc(dates[0]), last = utc(dates[dates.length - 1]);
  var minM = first.getUTCFullYear() * 12 + first.getUTCMonth();
  var maxM = last.getUTCFullYear() * 12 + last.getUTCMonth();
  var cur = maxM, selected = dates[dates.length - 1];

  var monthEl = root.querySelector('[data-cal-month]');
  var thead = root.querySelector('[data-cal-grid] thead');
  var tbody = root.querySelector('[data-cal-grid] tbody');
  var dayEl = root.querySelector('[data-cal-day]');
  var prev = root.querySelector('[data-cal-prev]');
  var next = root.querySelector('[data-cal-next]');

  // Weekday header, Monday first (2024-01-01 was a Monday).
  var hr = document.createElement('tr');
  for (var w = 0; w < 7; w++) {
    var th = document.createElement('th');
    th.scope = 'col';
    th.textContent = fWeek.format(new Date(Date.UTC(2024, 0, 1 + w)));
    hr.appendChild(th);
  }
  thead.appendChild(hr);

  function countLabel(n) { return n === 1 ? T('one') : n + ' ' + T('many'); }

  function renderMonth() {
    var y = Math.floor(cur / 12), m = cur % 12;
    monthEl.textContent = cap(fMonth.format(new Date(Date.UTC(y, m, 1))));
    prev.disabled = cur <= minM;
    next.disabled = cur >= maxM;
    tbody.textContent = '';
    var lead = (new Date(Date.UTC(y, m, 1)).getUTCDay() + 6) % 7;
    var days = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    var tr = document.createElement('tr');
    for (var i = 0; i < lead; i++) tr.appendChild(document.createElement('td'));
    for (var d = 1; d <= days; d++) {
      var key = iso(y, m, d), td = document.createElement('td'), evs = byDate[key];
      if (evs) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'cal-daybtn';
        b.setAttribute('data-date', key);
        b.setAttribute('aria-pressed', String(key === selected));
        b.setAttribute('aria-label', fFull.format(utc(key)) + ', ' + countLabel(evs.length));
        b.textContent = d;
        if (evs.length > 1) {
          var c = document.createElement('span');
          c.className = 'cal-count';
          c.setAttribute('aria-hidden', 'true');
          c.textContent = evs.length;
          b.appendChild(c);
        }
        td.appendChild(b);
      } else {
        var s = document.createElement('span');
        s.className = 'cal-num';
        s.textContent = d;
        td.appendChild(s);
      }
      tr.appendChild(td);
      if ((lead + d) % 7 === 0) { tbody.appendChild(tr); tr = document.createElement('tr'); }
    }
    if (tr.children.length) {
      while (tr.children.length < 7) tr.appendChild(document.createElement('td'));
      tbody.appendChild(tr);
    }
  }

  function renderDay() {
    dayEl.textContent = '';
    var h = document.createElement('h4');
    h.textContent = cap(fFull.format(utc(selected)));
    dayEl.appendChild(h);
    var evs = byDate[selected];
    if (!evs) {
      var p = document.createElement('p');
      p.textContent = T('none');
      dayEl.appendChild(p);
      return;
    }
    var ul = document.createElement('ul');
    evs.forEach(function (e) {
      var li = document.createElement('li');
      var tag = document.createElement('span');
      tag.className = 'cal-ev';
      tag.textContent = T(e.ev);
      var a = document.createElement('a');
      a.href = e.href;
      a.textContent = e.title;
      li.appendChild(tag);
      li.appendChild(a);
      ul.appendChild(li);
    });
    dayEl.appendChild(ul);
  }

  tbody.addEventListener('click', function (e) {
    var b = e.target.closest('.cal-daybtn');
    if (!b) return;
    selected = b.getAttribute('data-date');
    Array.prototype.forEach.call(tbody.querySelectorAll('.cal-daybtn'), function (x) {
      x.setAttribute('aria-pressed', String(x === b));
    });
    renderDay();
  });
  prev.addEventListener('click', function () { if (cur > minM) { cur--; renderMonth(); } });
  next.addEventListener('click', function () { if (cur < maxM) { cur++; renderMonth(); } });

  root.hidden = false;
  renderMonth();
  renderDay();
})();
