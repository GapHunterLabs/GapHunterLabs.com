// Home key figure, tools in the catalog: four plugin modules on a plate, one of them lit. About 64 px wide.
const { Scene } = require('../kit.cjs');

module.exports = function statTools(id = 'iso-stat-tools') {
  const S = new Scene({ id, scale: 14, center: [1.6, 1.6, 0.4] });
  S.shadow(-0.1, -0.1, 3.4, 3.4, 1.05);
  S.box(-0.1, -0.1, -0.25, 3.4, 3.4, 0.2, { gloss: false });
  [[0.25, 0.25, 0.5], [1.75, 0.25, 0.8], [0.25, 1.75, 0.8], [1.75, 1.75, 0.5]].forEach(([r, l, h], i) => {
    S.box(r, l, -0.05, 1.2, 1.2, h, i === 1 ? { top: 'var(--iso-accent)' } : {});
  });
  return S.svg();
};
