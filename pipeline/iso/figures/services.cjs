// Services hero: a workbench. A plugin module in the middle, a stacked performance profile (flame graph) at the
// front left and an upright pull-request card with a check at the back right, tethered to the module.
const { Scene } = require('../kit.cjs');

module.exports = function services(id = 'iso-services') {
  const S = new Scene({ id, scale: 40, center: [3.7, 2.9, 1.0] });
  const P = S.p;
  const A = 'var(--iso-accent)', A2 = 'var(--iso-accent-2)', INK = 'var(--iso-ink)';

  S.shadow(-0.4, -0.4, 8.0, 6.4, 1.1);
  S.halo(3.8, 2.4, 0.6, 2.9);
  S.box(-0.4, -0.4, -0.35, 8.0, 6.4, 0.2, { gloss: false });
  S.box(0, 0, -0.15, 7.2, 5.6, 0.15);
  const grid = [];
  for (let i = 0.9; i < 7.2; i += 0.9) grid.push([[i, 0.15, 0], [i, 5.45, 0]]);
  for (let j = 0.93; j < 5.6; j += 0.93) grid.push([[0.15, j, 0], [7.05, j, 0]]);
  S.multiline(grid, 'var(--iso-line)', 0.8, 'iso-texture');
  S.line([[0.4, 5.6, 0], [3.0, 5.6, 0]], A2, 1.2, null, 0.75);        // the figure's single turquoise detail

  // pull-request card at the back right: upright, facing the viewer, three lines and a check
  const K = (u, v) => [4.7 + 2.3 * u, 0.72, 0.95 + 1.6 * v];
  S.shadow(4.7, 0.6, 2.3, 0.3, 1.0);
  S.line([[5.85, 0.72, 0.02], [5.85, 0.72, 0.95]], 'var(--iso-glass-edge)', 0.8, null, 0.8);
  S.box(4.7, 0.6, 0.95, 2.3, 0.12, 1.6, { gloss: false });
  S.face([K(0, 0), K(1, 0), K(1, 1), K(0, 1)], `url(#${P}top)`);
  S.face([K(0, 0), K(1, 0), K(1, 1), K(0, 1)], `url(#${P}gloss)`);
  S.multiline([[K(0.1, 0.8), K(0.7, 0.8)], [K(0.1, 0.6), K(0.86, 0.6)], [K(0.1, 0.44), K(0.6, 0.44)]], INK, 1.4, null, 0.9);
  S.line([K(0.12, 0.2), K(0.2, 0.1), K(0.36, 0.3)], A, 2.6);
  S.line([K(0.46, 0.2), K(0.86, 0.2)], INK, 1.2, null, 0.6);
  S.line([K(0, 1), K(1, 1)], 'var(--iso-edge)', 0.9);

  // trace from the module to the card's foot
  S.line([[4.6, 2.4, 0.02], [5.85, 2.4, 0.02], [5.85, 0.9, 0.02]], A, 1.6, null, 0.9);

  // plugin module: a chip with pins along both visible sides and a recessed die with an accent light
  S.shadow(2.4, 1.6, 2.4, 2.0, 1.05);
  S.box(2.4, 1.6, 0, 2.4, 2.0, 0.5);
  const pins = [];
  for (let k = 0; k < 5; k++) {
    const r = 2.65 + k * 0.45, l = 1.85 + k * 0.38;
    pins.push([[r, 3.6, 0.12], [r, 3.6, 0.36]]);
    pins.push([[4.8, l, 0.12], [4.8, l, 0.36]]);
  }
  S.multiline(pins, 'var(--iso-edge)', 1.2, 'iso-fine', 0.8);
  S.box(3.05, 2.15, 0.5, 1.1, 0.9, 0.08, { gloss: false, top: `url(#${P}screen)` });
  S.dot(3.6, 2.6, 0.6, 3.0, A);

  // performance profile at the front left: stacked frames, widest at the bottom, the hot frame lit
  const frames = [[0.5, 3.0], [0.75, 2.3], [0.75, 1.5], [1.0, 0.8]];
  frames.forEach(([r, w], i) => {
    if (i === 0) S.shadow(r, 3.9, w, 1.0, 1.0);
    S.box(r, 3.9, i * 0.26, w, 1.0, 0.24, i === frames.length - 1 ? { top: A } : {});
  });
  return S.svg();
};
