// Catalog hero: an IDE window standing on a base plate, with plugin modules in front of it; one module is being
// installed into its slot.
const { Scene } = require('../kit.cjs');

module.exports = function catalog(id = 'iso-catalog') {
  const S = new Scene({ id, scale: 40, center: [3.7, 2.7, 1.5] });
  const P = S.p;
  const A = 'var(--iso-accent)', A2 = 'var(--iso-accent-2)', INK = 'var(--iso-ink)';

  S.shadow(-0.4, -0.4, 8.2, 6.4, 1.1);
  S.halo(2.8, 1.4, 1.6, 3.2);
  S.box(-0.4, -0.4, -0.35, 8.2, 6.4, 0.2, { gloss: false });
  S.box(0, 0, -0.15, 7.4, 5.6, 0.15);
  const grid = [];
  for (let i = 0.925; i < 7.4; i += 0.925) grid.push([[i, 0.15, 0], [i, 5.45, 0]]);
  for (let j = 0.93; j < 5.6; j += 0.93) grid.push([[0.15, j, 0], [7.25, j, 0]]);
  S.multiline(grid, 'var(--iso-line)', 0.8, 'iso-texture');
  S.line([[7.4, 0.5, 0], [7.4, 3.2, 0]], A, 1.6, null, 0.9);

  // IDE window: a framed panel on a short stand, screen inset on its front face (the plane l = WL)
  S.shadow(2.4, 0.5, 1.6, 0.7, 1.0);
  S.box(2.5, 0.45, 0, 1.4, 0.5, 0.35);
  const WL = 0.62;
  S.box(0.5, 0.44, 0.35, 5.4, WL - 0.44, 3.4, { gloss: false });
  const W = (u, v) => [0.5 + 5.4 * u, WL, 0.35 + 3.4 * v];
  S.face([W(0, 0), W(1, 0), W(1, 1), W(0, 1)], `url(#${P}bezel)`);
  const [u0, u1, v0, v1] = [0.025, 0.975, 0.05, 0.95];
  const sc = (x, y) => W(u0 + (u1 - u0) * x, v0 + (v1 - v0) * y);
  S.face([sc(0, 0), sc(1, 0), sc(1, 1), sc(0, 1)], `url(#${P}screen)`);
  S.line([sc(0, 0), sc(0, 1), sc(1, 1)], 'var(--iso-recess)', 1.1);
  S.line([sc(1, 1), sc(1, 0), sc(0, 0)], 'var(--iso-edge)', 0.7, null, 0.45);
  // title bar, project tree, editor lines
  S.line([sc(0, 0.88), sc(1, 0.88)], INK, 0.8, null, 0.7);
  S.dot(...sc(0.03, 0.94), 1.6, INK); S.dot(...sc(0.06, 0.94), 1.6, INK); S.dot(...sc(0.09, 0.94), 1.6, A);
  S.line([sc(0.24, 0), sc(0.24, 0.88)], INK, 0.8, null, 0.6);
  const tree = [[0.04, 0.78, 0.14], [0.07, 0.69, 0.12], [0.07, 0.6, 0.1], [0.04, 0.51, 0.15], [0.07, 0.42, 0.11], [0.07, 0.33, 0.13]];
  S.multiline(tree.map(([x, y, len]) => [sc(x, y), sc(x + len, y)]), INK, 1.2, null, 0.85);
  const code = [[0.3, 0.78, 0.38], [0.34, 0.69, 0.46], [0.34, 0.6, 0.3], [0.3, 0.51, 0.52], [0.34, 0.42, 0.26],
                [0.34, 0.33, 0.4], [0.3, 0.24, 0.22], [0.3, 0.15, 0.34]];
  S.multiline(code.map(([x, y, len]) => [sc(x, y), sc(x + len, y)]), INK, 1.3, null, 0.9);
  S.line([sc(0.34, 0.6), sc(0.64, 0.6)], A, 1.5);
  S.line([sc(0.34, 0.565), sc(0.64, 0.565)], A, 0.8, 'iso-fine', 0.6);
  S.face([sc(0, 0), sc(1, 0), sc(1, 1), sc(0, 1)], `url(#${P}gloss)`);
  S.line([W(0, 1), W(1, 1)], 'var(--iso-edge)', 0.9);

  // plugin modules: a socket on each top, traces to the stand
  const module = (r, l, t, accent) => {
    S.box(r, l, t, 1.1, 1.1, 0.55);
    const T = t + 0.551;
    S.line([[r + 0.3, l + 0.3, T], [r + 0.8, l + 0.3, T], [r + 0.8, l + 0.8, T], [r + 0.3, l + 0.8, T], [r + 0.3, l + 0.3, T]],
      accent ? A : INK, accent ? 1.4 : 1, null, accent ? 1 : 0.8);
    S.dot(r + 0.55, l + 1.1, t + 0.27, 1.8, accent ? A : INK);
  };
  S.multiline([[[1.35, 2.5, 0], [1.35, 1.5, 0], [2.5, 1.5, 0]], [[5.5, 2.5, 0], [5.5, 1.5, 0], [3.9, 1.5, 0]]], INK, 0.9, null, 0.55);
  S.line([[2.95, 2.5, 0], [2.95, 0.95, 0]], A2, 1.2, null, 0.8);   // the figure's single turquoise detail
  S.shadow(0.8, 2.6, 1.1, 1.1, 1.0);
  module(0.8, 2.6, 0);
  S.shadow(2.4, 2.6, 1.1, 1.1, 1.0);
  module(2.4, 2.6, 0);
  // the module being installed: an empty slot on the plate and the module above it
  S.line([[4.95, 2.6, 0.01], [6.05, 2.6, 0.01], [6.05, 3.7, 0.01], [4.95, 3.7, 0.01], [4.95, 2.6, 0.01]], A, 1.1, null, 0.75);
  S.shadow(4.95, 2.6, 1.1, 1.1, 0.8);
  S.multiline([[[5.5, 3.15, 0.05], [5.5, 3.15, 0.95]]], A, 0.9, 'iso-fine', 0.6);
  module(4.95, 2.6, 1.0, true);
  S.shadow(1.6, 4.1, 1.1, 1.1, 1.0);
  module(1.6, 4.1, 0);
  S.shadow(3.2, 4.1, 1.1, 1.1, 1.0);
  module(3.2, 4.1, 0);

  return S.svg();
};
