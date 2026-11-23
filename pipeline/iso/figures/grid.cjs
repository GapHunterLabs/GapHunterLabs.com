// Background: a subtle isometric floor grid (one path), drawn behind the home hero and faded out by CSS.
const { Scene } = require('../kit.cjs');

module.exports = function grid(id = 'iso-grid') {
  const S = new Scene({ id, scale: 34, center: [9, 9, 0] });
  const N = 18, lines = [];
  for (let i = 0; i <= N; i++) {
    lines.push([[i, 0, 0], [i, N, 0]]);
    lines.push([[0, i, 0], [N, i, 0]]);
  }
  S.multiline(lines, 'var(--iso-line)', 1);
  // a few cells marked on the floor, in the ink tone: the grid reads as a work surface, not a pattern
  S.multiline([[[11, 3, 0], [12, 3, 0], [12, 4, 0], [11, 4, 0], [11, 3, 0]],
               [[4, 12, 0], [5, 12, 0], [5, 13, 0], [4, 13, 0], [4, 12, 0]]], 'var(--iso-ink)', 1, null, 0.35);
  return S.svg();
};
