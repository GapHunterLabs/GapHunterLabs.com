// Home method, step 3 (build the fix): a module with a new part slotted in and a check card standing behind it.
// About 72 px wide.
const { Scene } = require('../kit.cjs');

module.exports = function stepFix(id = 'iso-step-fix') {
  const S = new Scene({ id, scale: 14, center: [1.6, 1.6, 0.9] });
  const P = S.p;
  S.shadow(-0.1, -0.1, 3.4, 3.4, 1.05);
  S.box(-0.1, -0.1, -0.25, 3.4, 3.4, 0.2, { gloss: false });
  S.box(0.6, 0.35, -0.05, 2.2, 0.2, 2.2, { gloss: false });
  const K = (u, v) => [0.6 + 2.2 * u, 0.55, -0.05 + 2.2 * v];
  S.face([K(0, 0), K(1, 0), K(1, 1), K(0, 1)], `url(#${P}top)`);
  S.line([K(0.22, 0.55), K(0.42, 0.38), K(0.8, 0.72)], 'var(--iso-accent)', 3.0);
  S.box(0.5, 1.3, -0.05, 2.4, 1.6, 0.45);
  S.box(1.3, 1.75, 0.4, 0.8, 0.7, 0.2, { top: 'var(--iso-accent)', gloss: false });
  return S.svg();
};
