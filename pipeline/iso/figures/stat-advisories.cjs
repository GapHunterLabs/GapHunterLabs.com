// Home key figure, advisories closed upstream: a shield with a check on a glass panel over a module. About 64 px wide.
const { Scene } = require('../kit.cjs');

module.exports = function statAdvisories(id = 'iso-stat-advisories') {
  const S = new Scene({ id, scale: 14, center: [1.6, 1.6, 1.0] });
  S.shadow(-0.1, -0.1, 3.4, 3.4, 1.05);
  S.box(-0.1, -0.1, -0.25, 3.4, 3.4, 0.2, { gloss: false });
  S.box(0.4, 0.9, -0.05, 2.6, 1.6, 0.45);
  const g = [[0.6, 1.5, 0.4], [2.8, 1.5, 0.4], [2.8, 1.5, 2.9], [0.6, 1.5, 2.9]];
  S.face(g, 'var(--iso-glass)');
  S.line([...g, g[0]], 'var(--iso-glass-edge)', 1.2);
  const sh = (u, v) => [1.7 + u, 1.5, 1.65 + v];
  S.line([sh(0, 0.85), sh(0.7, 0.62), sh(0.7, 0.05), sh(0, -0.8), sh(-0.7, 0.05), sh(-0.7, 0.62), sh(0, 0.85)], 'var(--iso-accent)', 2.4);
  S.line([sh(-0.3, 0.0), sh(-0.05, -0.25), sh(0.35, 0.3)], 'var(--iso-accent)', 2.4);
  return S.svg();
};
