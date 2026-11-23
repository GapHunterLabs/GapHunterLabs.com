// Evidence hero: a report on a base plate (text lines and a small bar chart), a magnifier over it and a ticket card
// standing behind, tethered to the report.
const { Scene } = require('../kit.cjs');

module.exports = function evidence(id = 'iso-evidence') {
  const S = new Scene({ id, scale: 40, center: [3.6, 2.8, 1.2] });
  const P = S.p;
  const A = 'var(--iso-accent)', A2 = 'var(--iso-accent-2)', INK = 'var(--iso-ink)';

  S.shadow(-0.4, -0.4, 8.0, 6.4, 1.1);
  S.halo(5.6, 1.6, 1.2, 2.8);
  S.box(-0.4, -0.4, -0.35, 8.0, 6.4, 0.2, { gloss: false });
  S.box(0, 0, -0.15, 7.2, 5.6, 0.15);
  const grid = [];
  for (let i = 0.9; i < 7.2; i += 0.9) grid.push([[i, 0.15, 0], [i, 5.45, 0]]);
  for (let j = 0.93; j < 5.6; j += 0.93) grid.push([[0.15, j, 0], [7.05, j, 0]]);
  S.multiline(grid, 'var(--iso-line)', 0.8, 'iso-texture');
  S.line([[7.2, 0.5, 0], [7.2, 3.0, 0]], A, 1.6, null, 0.9);
  S.line([[3.4, 5.6, 0], [6.4, 5.6, 0]], A2, 1.2, null, 0.75);        // the figure's single turquoise detail

  // ticket card at the back right: thin upright card facing the viewer, a hole, an id line and a status pill
  const K = (u, v) => [4.4 + 2.2 * u, 0.62, 1.05 + 1.5 * v];
  S.shadow(4.4, 0.5, 2.2, 0.3, 1.0);
  S.line([[5.5, 0.62, 0.02], [5.5, 0.62, 1.05]], 'var(--iso-glass-edge)', 0.8, null, 0.8);
  S.box(4.4, 0.5, 1.05, 2.2, 0.12, 1.5, { gloss: false });
  S.face([K(0, 0), K(1, 0), K(1, 1), K(0, 1)], `url(#${P}top)`);
  S.face([K(0, 0), K(1, 0), K(1, 1), K(0, 1)], `url(#${P}gloss)`);
  S.dot(...K(0.1, 0.78), 2.6, 'var(--iso-recess)');
  S.multiline([[K(0.22, 0.78), K(0.62, 0.78)], [K(0.1, 0.52), K(0.82, 0.52)], [K(0.1, 0.36), K(0.66, 0.36)]], INK, 1.4, null, 0.9);
  S.line([K(0.1, 0.16), K(0.38, 0.16)], A, 3.2);
  S.line([K(0, 1), K(1, 1)], 'var(--iso-edge)', 0.9);

  // the report: a thin slab with a heading, text lines and a bar chart in real volume
  S.shadow(0.7, 1.4, 4.0, 4.2, 1.0);
  S.box(0.95, 1.6, 0, 3.8, 4.0, 0.1, { gloss: false });              // a second sheet under the report
  S.box(0.7, 1.4, 0.1, 3.8, 4.0, 0.12);
  const Z = 0.221;
  S.line([[1.0, 1.75, Z], [3.0, 1.75, Z]], INK, 2.2, null, 0.95);
  const text = [];
  for (let k = 0; k < 6; k++) text.push([[1.0, 2.2 + k * 0.32, Z], [k % 3 === 2 ? 2.6 : 3.4, 2.2 + k * 0.32, Z]]);
  S.multiline(text, INK, 1.1, null, 0.8);
  S.line([[1.0, 2.84, Z], [2.3, 2.84, Z]], A, 1.4);
  S.line([[1.0, 4.35, Z], [4.2, 4.35, Z]], INK, 0.8, null, 0.6);
  [[1.1, 0.35], [1.5, 0.6], [1.9, 0.45], [2.3, 0.85]].forEach(([r, h], i) => {
    S.box(r, 4.55, Z, 0.26, 0.4, h, i === 3 ? { top: A } : {});
  });
  S.line([[4.5, 1.4, 0.06], [4.5, 1.0, 0.06], [5.0, 1.0, 0.06], [5.0, 0.62, 0.06]], 'var(--iso-glass-edge)', 0.8, null, 0.8);

  // magnifier over the report: shadow on the paper, glass lens, metal rim and handle
  S.disc(3.0, 3.0, Z, 0.95, `url(#${P}shadow)`);
  S.box(3.65, 3.55, 1.05, 1.6, 0.24, 0.2, { gloss: false, top: `url(#${P}metal)` });
  S.disc(3.0, 3.0, 1.2, 0.9, 'var(--iso-glass)');
  S.disc(3.0, 3.0, 1.16, 0.9, null, `url(#${P}metal)`, 3.2);
  S.disc(3.0, 3.0, 1.22, 0.9, null, 'var(--iso-edge)', 0.8, 0.8);
  S.line([[2.55, 2.55, 1.22], [2.9, 2.45, 1.22]], 'var(--iso-gloss)', 1.4, null, 0.5);
  
  return S.svg();
};
