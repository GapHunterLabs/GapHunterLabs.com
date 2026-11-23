// Home hero: laptop + server stack + floating glass panel with a shield, on a graphite base plate.
const { Scene } = require('../kit.cjs');

module.exports = function hero(id = 'iso-hero') {
  const S = new Scene({ id, scale: 42, center: [3.9, 2.9, 1.6] });
  const P = S.p;
  const A = 'var(--iso-accent)', A2 = 'var(--iso-accent-2)', INK = 'var(--iso-ink)';

  // ground shadow and ambient light
  S.shadow(-0.4, -0.4, 8.6, 6.6, 1.12);
  S.halo(5.0, 3.0, 0.2, 3.6);

  // base plate: two-step slab
  S.box(-0.4, -0.4, -0.35, 8.6, 6.6, 0.2, { gloss: false });
  S.box(0, 0, -0.15, 7.8, 5.8, 0.15);
  const grid = [];
  for (let i = 0.97; i < 7.8; i += 0.97) grid.push([[i, 0.15, 0], [i, 5.65, 0]]);
  for (let j = 0.97; j < 5.8; j += 0.97) grid.push([[0.15, j, 0], [7.65, j, 0]]);
  S.multiline(grid, 'var(--iso-line)', 0.8, 'iso-texture');
  S.line([[7.8, 0.6, 0], [7.8, 3.9, 0]], A, 1.6, null, 0.9);          // orange trace, front-right edge
  S.line([[3.4, 5.8, 0], [6.6, 5.8, 0]], A2, 1.2, null, 0.75);        // the figure's single turquoise detail

  // server stack
  S.shadow(0.5, 0.6, 2.2, 2.0, 1.0);
  for (let k = 0; k < 3; k++) {
    const t = k * 0.62;
    S.box(0.5, 0.6, t, 2.2, 2.0, 0.52);
    const vents = [];
    for (let v = 0; v < 6; v++) vents.push([[0.75 + v * 0.18, 2.6, t + 0.14], [0.75 + v * 0.18, 2.6, t + 0.38]]);
    S.multiline(vents, INK, 0.9, null, 0.8);
    S.dot(2.3, 2.6, t + 0.26, 2.1, k === 1 ? A : INK);
    S.dot(2.5, 2.6, t + 0.26, 2.1, INK);
  }

  // laptop base, keyboard and trackpad
  S.shadow(3.3, 1.7, 3.8, 3.0, 1.0);
  S.box(3.3, 1.7, 0, 3.8, 3.0, 0.16);
  const keys = [];
  for (let row = 0; row < 4; row++) for (let col = 0; col < 10; col++) {
    const r0 = 3.6 + col * 0.3, l0 = 2.0 + row * 0.27, z = 0.161;
    keys.push([[r0, l0, z], [r0 + 0.22, l0, z], [r0 + 0.22, l0 + 0.19, z], [r0, l0 + 0.19, z], [r0, l0, z]]);
  }
  S.multiline(keys, INK, 0.6, 'iso-fine', 0.55);
  S.line([[4.4, 3.4, 0.161], [5.9, 3.4, 0.161], [5.9, 4.3, 0.161], [4.4, 4.3, 0.161], [4.4, 3.4, 0.161]], INK, 0.7, 'iso-fine', 0.6);

  // lid: front plane tilted back, with real thickness (top and right edges) and an inset, beveled screen
  const lid = (u, v, back = 0) => [3.3 + 3.8 * u, 1.7 - 0.32 * v - back, 0.16 + 2.39 * v];
  const TH = 0.09;
  S.face([lid(0, 1), lid(1, 1), lid(1, 1, TH), lid(0, 1, TH)], `url(#${P}metal)`);                 // top edge
  S.face([lid(1, 0), lid(1, 0, TH), lid(1, 1, TH), lid(1, 1)], `url(#${P}right)`);                  // right edge
  S.face([lid(0, 0), lid(1, 0), lid(1, 1), lid(0, 1)], `url(#${P}bezel)`);                          // bezel
  const [u0, u1, v0, v1] = [0.035, 0.965, 0.075, 0.95];
  const inset = [lid(u0, v0), lid(u1, v0), lid(u1, v1), lid(u0, v1)];
  S.face(inset, `url(#${P}screen)`);
  S.line([lid(u0, v0), lid(u0, v1), lid(u1, v1)], 'var(--iso-recess)', 1.1);                        // inner shadow: top and left
  S.line([lid(u1, v1), lid(u1, v0), lid(u0, v0)], 'var(--iso-edge)', 0.7, null, 0.45);              // inner light: bottom and right
  S.face(inset, `url(#${P}gloss)`);
  S.line([lid(0, 1), lid(1, 1)], 'var(--iso-edge)', 0.9);
  S.line([lid(0, 0), lid(1, 0)], `url(#${P}metal)`, 1.6);                                            // hinge
  S.dot(...lid(0.5, 0.975), 1.1, INK);                                                               // camera

  // screen content: code lines and a </> glyph
  const sc = (x, y) => lid(u0 + (u1 - u0) * x, v0 + (v1 - v0) * y);
  const code = [[0.05, 0.86, 0.36], [0.1, 0.74, 0.5], [0.1, 0.62, 0.4], [0.05, 0.5, 0.56], [0.1, 0.38, 0.3], [0.05, 0.26, 0.46]];
  S.multiline(code.map(([x, y, len]) => [sc(x, y), sc(x + len, y)]), INK, 1.3, null, 0.9);
  S.line([sc(0.1, 0.62), sc(0.28, 0.62)], A, 1.4);
  S.multiline([[sc(0.74, 0.66), sc(0.68, 0.53), sc(0.74, 0.4)],
               [sc(0.88, 0.66), sc(0.94, 0.53), sc(0.88, 0.4)],
               [sc(0.83, 0.68), sc(0.79, 0.38)]], A, 1.6);

  // floating glass panel with a shield, tethered to the stack
  const gl = [[0.7, 0.4, 2.55], [2.6, 0.4, 2.55], [2.6, 0.4, 4.15], [0.7, 0.4, 4.15]];
  S.face(gl, 'var(--iso-glass)');
  S.line([...gl, gl[0]], 'var(--iso-glass-edge)', 0.8);
  const sh = (u, v) => [1.65 + u, 0.4, 3.35 + v];
  S.line([sh(0, 0.55), sh(0.42, 0.42), sh(0.42, 0.02), sh(0, -0.5), sh(-0.42, 0.02), sh(-0.42, 0.42), sh(0, 0.55)], A, 1.5);
  S.line([sh(-0.17, 0.0), sh(-0.03, -0.14), sh(0.2, 0.17)], A, 1.5);
  S.line([[1.65, 0.4, 2.55], [1.65, 0.9, 1.86]], 'var(--iso-glass-edge)', 0.7, null, 0.7);

  return S.svg();
};
