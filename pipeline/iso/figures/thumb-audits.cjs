// Evidence thumbnail, third-party audits: another vendor's plugin module and a checklist panel standing beside it.
const { Scene } = require('../kit.cjs');

module.exports = function thumbAudits(id = 'iso-thumb-audits') {
  const S = new Scene({ id, scale: 16, center: [2.0, 2.0, 1.0] });
  const P = S.p;
  const A = 'var(--iso-accent)', INK = 'var(--iso-ink)';
  S.shadow(-0.2, -0.2, 4.4, 4.4, 1.05);
  S.box(-0.2, -0.2, -0.3, 4.4, 4.4, 0.18, { gloss: false });
  S.box(0, 0, -0.12, 4.0, 4.0, 0.12);
  // checklist panel at the back
  S.shadow(0.4, 0.4, 2.2, 0.3, 1.0);
  S.box(0.4, 0.4, 0.1, 2.2, 0.14, 2.5, { gloss: false });
  const C = (u, v) => [0.4 + 2.2 * u, 0.54, 0.1 + 2.5 * v];
  S.face([C(0, 0), C(1, 0), C(1, 1), C(0, 1)], `url(#${P}top)`);
  S.line([C(0, 1), C(1, 1)], 'var(--iso-edge)', 1);
  [0.78, 0.55, 0.32].forEach((v, k) => {
    const done = k < 2;
    S.line([C(0.1, v), C(0.16, v - 0.05), C(0.26, v + 0.06)], done ? INK : A, 1.8, null, done ? 0.9 : 1);
    S.line([C(0.36, v), C(0.86, v)], INK, 1.6, null, 0.85);
  });
  // the plugin module under review, with its socket
  S.shadow(1.9, 1.7, 1.6, 1.6, 1.0);
  S.box(1.9, 1.7, 0, 1.6, 1.6, 0.8);
  const T = 0.801;
  S.line([[2.3, 2.1, T], [3.1, 2.1, T], [3.1, 2.9, T], [2.3, 2.9, T], [2.3, 2.1, T]], INK, 1.4, null, 0.85);
  S.dot(2.7, 3.3, 0.4, 2.4, A);
  return S.svg();
};
