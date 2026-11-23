// Home key figure, pull requests: an upright card with a check standing on a small plate. About 64 px wide.
const { Scene } = require('../kit.cjs');

module.exports = function statPrs(id = 'iso-stat-prs') {
  const S = new Scene({ id, scale: 14, center: [1.6, 1.6, 1.0] });
  const P = S.p;
  S.shadow(-0.1, -0.1, 3.4, 3.4, 1.05);
  S.box(-0.1, -0.1, -0.25, 3.4, 3.4, 0.2, { gloss: false });
  S.box(0.5, 1.3, -0.05, 2.4, 0.25, 2.6, { gloss: false });
  const K = (u, v) => [0.5 + 2.4 * u, 1.55, -0.05 + 2.6 * v];
  S.face([K(0, 0), K(1, 0), K(1, 1), K(0, 1)], `url(#${P}top)`);
  S.line([K(0.18, 0.72), K(0.82, 0.72)], 'var(--iso-ink)', 1.8, null, 0.8);
  S.line([K(0.22, 0.38), K(0.42, 0.2), K(0.8, 0.52)], 'var(--iso-accent)', 3.0);
  return S.svg();
};
