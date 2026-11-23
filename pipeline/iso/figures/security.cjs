// Security hero: everything runs locally. A workstation inside a glass enclosure, a padlock on the front wall and a
// network cable that ends at the wall (no backend to call).
const { Scene } = require('../kit.cjs');

module.exports = function security(id = 'iso-security') {
  const S = new Scene({ id, scale: 40, center: [3.6, 2.8, 1.3] });
  const P = S.p;
  const A = 'var(--iso-accent)', A2 = 'var(--iso-accent-2)', INK = 'var(--iso-ink)';
  const GL = 'var(--iso-glass)', GE = 'var(--iso-glass-edge)';

  S.shadow(-0.4, -0.4, 8.0, 6.4, 1.1);
  S.halo(3.2, 2.8, 0.8, 3.0);
  S.box(-0.4, -0.4, -0.35, 8.0, 6.4, 0.2, { gloss: false });
  S.box(0, 0, -0.15, 7.2, 5.6, 0.15);
  const grid = [];
  for (let i = 0.9; i < 7.2; i += 0.9) grid.push([[i, 0.15, 0], [i, 5.45, 0]]);
  for (let j = 0.93; j < 5.6; j += 0.93) grid.push([[0.15, j, 0], [7.05, j, 0]]);
  S.multiline(grid, 'var(--iso-line)', 0.8, 'iso-texture');
  S.line([[0.3, 5.6, 0], [2.6, 5.6, 0]], A2, 1.2, null, 0.75);        // the figure's single turquoise detail

  // enclosure: r 0.8..5.4, l 0.8..4.6, height 2.6. Back walls first, then the content, then the front walls.
  const r0 = 0.8, r1 = 5.4, l0 = 0.8, l1 = 4.6, H = 2.6;
  S.face([[r0, l0, 0], [r1, l0, 0], [r1, l0, H], [r0, l0, H]], GL);
  S.face([[r0, l0, 0], [r0, l1, 0], [r0, l1, H], [r0, l0, H]], GL);
  S.multiline([[[r0, l0, 0], [r0, l0, H]], [[r0, l1, H], [r0, l0, H], [r1, l0, H]]], GE, 0.9, null, 0.7);

  // workstation: a slab with a raised screen and code lines
  S.shadow(1.6, 1.6, 3.0, 2.2, 1.0);
  S.box(1.6, 1.6, 0, 3.0, 2.2, 0.35);
  const Z = 0.35;
  S.multiline([[[1.9, 2.3, Z], [3.4, 2.3, Z]], [[1.9, 2.6, Z], [3.9, 2.6, Z]], [[1.9, 2.9, Z], [3.0, 2.9, Z]], [[1.9, 3.2, Z], [3.6, 3.2, Z]]], INK, 1.1, null, 0.8);
  S.line([[1.9, 1.95, Z], [2.9, 1.95, Z]], A, 1.6);
  S.box(1.8, 1.65, Z, 2.6, 0.12, 1.3, { gloss: false });
  const W = (u, v) => [1.95 + 2.3 * u, 1.77, Z + 0.15 + 1.0 * v];
  S.face([W(0, 0), W(1, 0), W(1, 1), W(0, 1)], `url(#${P}screen)`);
  S.face([W(0, 0), W(1, 0), W(1, 1), W(0, 1)], `url(#${P}gloss)`);
  S.multiline([[W(0.08, 0.78), W(0.55, 0.78)], [W(0.08, 0.58), W(0.72, 0.58)], [W(0.08, 0.38), W(0.48, 0.38)]], INK, 1.2, 'iso-fine', 0.85);
  S.line([W(0.08, 0.18), W(0.3, 0.18)], A, 2.2);

  // the network cable: leaves the workstation and stops at the right wall, capped
  S.line([[4.6, 2.9, 0.02], [5.4, 2.9, 0.02]], INK, 1.6, null, 0.8);
  S.box(5.32, 2.75, 0, 0.16, 0.3, 0.22, { gloss: false, top: `url(#${P}metal)` });

  // front walls and edges
  S.face([[r1, l0, 0], [r1, l1, 0], [r1, l1, H], [r1, l0, H]], GL);
  S.face([[r0, l1, 0], [r1, l1, 0], [r1, l1, H], [r0, l1, H]], GL);
  S.face([[r0, l0, H], [r1, l0, H], [r1, l1, H], [r0, l1, H]], GL);
  S.multiline([[[r0, l1, 0], [r0, l1, H], [r1, l1, H], [r1, l0, H]], [[r1, l1, 0], [r1, l1, H]], [[r1, l0, 0], [r1, l0, H]],
               [[r0, l1, 0], [r1, l1, 0], [r1, l0, 0]]], GE, 1, null, 0.9);

  // padlock on the front wall: body in volume, shackle as a half loop above it
  const cx = 3.1, ly = l1 + 0.02;
  S.box(cx - 0.45, ly, 0.7, 0.9, 0.18, 0.7, { top: `url(#${P}metal)` });
  const loop = [];
  for (let k = 0; k <= 12; k++) {
    const a = Math.PI * k / 12;
    loop.push([cx - 0.28 * Math.cos(a) + 0.0, ly + 0.09, 1.4 + 0.42 * Math.sin(a)]);
  }
  S.line(loop, `url(#${P}metal)`, 4.2);
  S.line(loop, 'var(--iso-edge)', 0.8, null, 0.8);
  S.dot(cx, ly + 0.18, 1.0, 2.6, A);
  return S.svg();
};
