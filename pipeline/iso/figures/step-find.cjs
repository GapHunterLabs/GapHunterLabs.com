// Home method, step 1 (find the gap): a magnifier over a module, the gap lit under the lens. About 72 px wide.
const { Scene } = require('../kit.cjs');

module.exports = function stepFind(id = 'iso-step-find') {
  const S = new Scene({ id, scale: 14, center: [1.6, 1.6, 0.8] });
  const P = S.p;
  S.shadow(-0.1, -0.1, 3.4, 3.4, 1.05);
  S.box(-0.1, -0.1, -0.25, 3.4, 3.4, 0.2, { gloss: false });
  S.box(0.4, 0.4, -0.05, 2.4, 2.4, 0.35);
  S.box(1.35, 1.35, 0.3, 0.5, 0.5, 0.06, { top: 'var(--iso-accent)', gloss: false });
  S.disc(1.6, 1.6, 1.5, 0.95, 'var(--iso-glass)');
  S.disc(1.6, 1.6, 1.5, 0.95, null, `url(#${P}metal)`, 3.2);
  S.box(2.35, 2.25, 1.32, 1.1, 0.22, 0.18, { gloss: false, top: `url(#${P}metal)` });
  return S.svg();
};
