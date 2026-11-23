// Blog hero: case files. A stack of three case cards, the top one with a heading, text lines and a measurement
// that drops to zero, and an upright calendar card at the back right with one highlighted day.
const { Scene } = require('../kit.cjs');

module.exports = function writing(id = 'iso-writing') {
  const S = new Scene({ id, scale: 40, center: [3.6, 2.8, 0.9] });
  const P = S.p;
  const A = 'var(--iso-accent)', A2 = 'var(--iso-accent-2)', INK = 'var(--iso-ink)';

  S.shadow(-0.4, -0.4, 8.0, 6.4, 1.1);
  S.halo(2.8, 3.0, 0.3, 2.8);
  S.box(-0.4, -0.4, -0.35, 8.0, 6.4, 0.2, { gloss: false });
  S.box(0, 0, -0.15, 7.2, 5.6, 0.15);
  const grid = [];
  for (let i = 0.9; i < 7.2; i += 0.9) grid.push([[i, 0.15, 0], [i, 5.45, 0]]);
  for (let j = 0.93; j < 5.6; j += 0.93) grid.push([[0.15, j, 0], [7.05, j, 0]]);
  S.multiline(grid, 'var(--iso-line)', 0.8, 'iso-texture');
  S.line([[7.2, 2.6, 0], [7.2, 5.0, 0]], A2, 1.2, null, 0.75);        // the figure's single turquoise detail

  // calendar card at the back right: upright, a header band, a 4x3 grid of days, one of them lit
  const K = (u, v) => [4.8 + 2.2 * u, 0.72, 0.9 + 1.7 * v];
  S.shadow(4.8, 0.6, 2.2, 0.3, 1.0);
  S.box(4.8, 0.6, 0.0, 2.2, 0.12, 0.9, { gloss: false });
  S.box(4.8, 0.6, 0.9, 2.2, 0.12, 1.7, { gloss: false });
  S.face([K(0, 0), K(1, 0), K(1, 1), K(0, 1)], `url(#${P}top)`);
  S.face([K(0, 0.8), K(1, 0.8), K(1, 1), K(0, 1)], `url(#${P}metal)`);
  const days = [];
  for (let row = 0; row < 3; row++) {
    for (let col = 0; col < 4; col++) {
      const u = 0.12 + col * 0.22, v = 0.58 - row * 0.2;
      days.push([K(u, v), K(u + 0.1, v)]);
    }
  }
  S.multiline(days, INK, 2.2, 'iso-fine', 0.7);
  S.line([K(0.56, 0.38), K(0.66, 0.38)], A, 3.4);
  S.line([K(0, 1), K(1, 1)], 'var(--iso-edge)', 0.9);

  // the stack of case cards, each a little offset, then the details on the top one
  S.shadow(0.6, 1.4, 4.0, 3.6, 1.0);
  S.box(1.05, 1.75, 0, 3.6, 3.4, 0.1, { gloss: false });
  S.box(0.85, 1.55, 0.1, 3.6, 3.4, 0.1, { gloss: false });
  S.box(0.6, 1.35, 0.2, 3.6, 3.4, 0.12);
  const Z = 0.321;
  S.line([[0.9, 1.7, Z], [2.4, 1.7, Z]], A, 2.0);                     // the area tag
  S.line([[0.9, 2.05, Z], [3.6, 2.05, Z]], INK, 2.2, null, 0.95);      // the title
  S.multiline([[[0.9, 2.45, Z], [3.8, 2.45, Z]], [[0.9, 2.72, Z], [3.2, 2.72, Z]]], INK, 1.1, null, 0.8);
  // the measurement: a bar that drops to a flat line at zero
  S.line([[0.9, 3.15, Z], [3.8, 3.15, Z]], INK, 0.8, null, 0.6);
  S.box(1.0, 3.25, Z, 0.5, 0.5, 0.9);
  S.line([[1.75, 3.5, Z + 0.9], [2.2, 3.5, Z + 0.9], [2.6, 3.5, Z + 0.06], [3.7, 3.5, Z + 0.06]], A, 1.8);
  S.box(3.0, 3.25, Z, 0.5, 0.5, 0.04, { top: A, gloss: false });
  S.line([[0.9, 4.3, Z], [3.0, 4.3, Z]], INK, 0.8, null, 0.6);
  return S.svg();
};
