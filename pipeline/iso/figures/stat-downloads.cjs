// Home key figure, downloads: three bars rising on a small plate, the tallest lit. Drawn for about 64 px wide.
const { Scene } = require('../kit.cjs');

module.exports = function statDownloads(id = 'iso-stat-downloads') {
  const S = new Scene({ id, scale: 14, center: [1.6, 1.6, 0.9] });
  S.shadow(-0.1, -0.1, 3.4, 3.4, 1.05);
  S.box(-0.1, -0.1, -0.25, 3.4, 3.4, 0.2, { gloss: false });
  [[0.3, 0.8], [1.3, 1.5], [2.3, 2.4]].forEach(([r, h], i) => {
    S.box(r, 1.2, -0.05, 0.75, 0.9, h, i === 2 ? { top: 'var(--iso-accent)' } : {});
  });
  return S.svg();
};
