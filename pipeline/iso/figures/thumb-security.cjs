// Evidence thumbnail, security and dependencies: a dependency tree of three modules and a shield on a glass panel.
const { Scene } = require('../kit.cjs');

module.exports = function thumbSecurity(id = 'iso-thumb-security') {
  const S = new Scene({ id, scale: 16, center: [2.0, 2.0, 1.0] });
  const A = 'var(--iso-accent)', INK = 'var(--iso-ink)';
  S.shadow(-0.2, -0.2, 4.4, 4.4, 1.05);
  S.box(-0.2, -0.2, -0.3, 4.4, 4.4, 0.18, { gloss: false });
  S.box(0, 0, -0.12, 4.0, 4.0, 0.12);
  S.multiline([[[1.0, 1.4, 0], [1.0, 2.6, 0], [2.6, 2.6, 0]], [[1.0, 2.6, 0], [1.0, 3.0, 0]]], INK, 1.2, null, 0.7);
  S.shadow(0.4, 0.5, 1.2, 1.0, 1.0);
  S.box(0.4, 0.5, 0, 1.2, 1.0, 0.7);
  S.shadow(2.4, 2.1, 1.1, 1.1, 1.0);
  S.box(2.4, 2.1, 0, 1.1, 1.1, 0.6);
  S.dot(2.95, 3.2, 0.3, 2.2, A);
  S.shadow(0.45, 2.9, 1.1, 0.9, 1.0);
  S.box(0.45, 2.9, 0, 1.1, 0.9, 0.6);
  // glass panel with a shield, above the root module
  const g = [[0.2, 0.45, 1.05], [1.8, 0.45, 1.05], [1.8, 0.45, 2.55], [0.2, 0.45, 2.55]];
  S.face(g, 'var(--iso-glass)');
  S.line([...g, g[0]], 'var(--iso-glass-edge)', 1);
  const sh = (u, v) => [1.0 + u, 0.45, 1.8 + v];
  S.line([sh(0, 0.5), sh(0.4, 0.38), sh(0.4, 0.02), sh(0, -0.48), sh(-0.4, 0.02), sh(-0.4, 0.38), sh(0, 0.5)], A, 2);
  S.line([sh(-0.17, 0.0), sh(-0.03, -0.14), sh(0.2, 0.17)], A, 2);
  return S.svg();
};
