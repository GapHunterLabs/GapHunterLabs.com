// Home method, step 2 (trace the cause): three modules joined by a path; the path to the cause is lit. About 72 px wide.
const { Scene } = require('../kit.cjs');

module.exports = function stepTrace(id = 'iso-step-trace') {
  const S = new Scene({ id, scale: 14, center: [1.6, 1.6, 0.4] });
  const A = 'var(--iso-accent)';
  S.shadow(-0.1, -0.1, 3.4, 3.4, 1.05);
  S.box(-0.1, -0.1, -0.25, 3.4, 3.4, 0.2, { gloss: false });
  S.line([[0.8, 0.8, -0.04], [0.8, 2.5, -0.04], [2.5, 2.5, -0.04]], 'var(--iso-ink)', 1.6, null, 0.6);
  S.line([[0.8, 0.8, -0.04], [2.5, 0.8, -0.04], [2.5, 2.5, -0.04]], A, 2.4);
  S.box(0.3, 0.3, -0.05, 1.0, 1.0, 0.6);
  S.box(2.0, 0.3, -0.05, 1.0, 1.0, 0.45);
  S.box(0.3, 2.0, -0.05, 1.0, 1.0, 0.45);
  S.box(2.0, 2.0, -0.05, 1.0, 1.0, 0.7, { top: A });
  return S.svg();
};
