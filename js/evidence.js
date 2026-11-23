/* Evidence hub: the order of the case lists. The page is complete without this script (newest first, as built by
   pipeline/build_evidence.py); the select only shows when the script runs, and it only reorders existing rows. */
(function () {
  'use strict';
  var box = document.querySelector('[data-ee-sort]');
  var select = document.getElementById('eeSort');
  var lists = Array.prototype.slice.call(document.querySelectorAll('ol[data-sortable]'));
  if (!box || !select || !lists.length) return;
  function sort(order) {
    lists.forEach(function (list) {
      var rows = Array.prototype.slice.call(list.children).filter(function (li) { return li.hasAttribute('data-date'); });
      rows.sort(function (a, b) {
        var x = a.getAttribute('data-date'), y = b.getAttribute('data-date');
        return order === 'old' ? (x < y ? -1 : x > y ? 1 : 0) : (x > y ? -1 : x < y ? 1 : 0);
      });
      rows.forEach(function (li) { list.appendChild(li); });
    });
  }
  select.addEventListener('change', function () { sort(select.value === 'old' ? 'old' : 'new'); });
  box.hidden = false;
})();
