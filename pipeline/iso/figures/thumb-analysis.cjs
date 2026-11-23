// Evidence thumbnail, static analysis: a code sheet with one flagged line and a scanner frame passing over it.
const { Scene } = require('../kit.cjs');

module.exports = function thumbAnalysis(id = 'iso-thumb-analysis') {
  const S = new Scene({ id, scale: 16, center: [2.0, 2.0, 0.8] });
  const A = 'var(--iso-accent)', INK = 'var(--iso-ink)';
  S.shadow(-0.2, -0.2, 4.4, 4.4, 1.05);
  S.box(-0.2, -0.2, -0.3, 4.4, 4.4, 0.18, { gloss: false });
  S.box(0, 0, -0.12, 4.0, 4.0, 0.12);
  // code sheet
  S.shadow(0.4, 0.4, 3.2, 3.2, 1.0);
  S.box(0.4, 0.4, 0, 3.2, 3.2, 0.14);
  const Z = 0.141, lines = [];
  [[0.7, 2.2], [0.9, 2.8], [0.9, 2.1], [0.7, 2.6], [0.9, 2.4], [0.7, 1.9]].forEach(([r0, r1], k) => {
    if (k !== 3) lines.push([[r0, 0.75 + k * 0.45, Z], [r1, 0.75 + k * 0.45, Z]]);
  });
  S.multiline(lines, INK, 1.6, null, 0.85);
  S.line([[0.7, 2.1, Z], [2.6, 2.1, Z]], A, 2);
  const wave = [];
  for (let k = 0; k <= 8; k++) wave.push([0.7 + k * 0.24, 2.27 + (k % 2 ? 0.07 : -0.03), Z]);
  S.line(wave, A, 1.1, null, 0.85);
  // scanner frame: an upright glass band across the sheet
  const g = [[2.9, 0.3, 0.05], [2.9, 3.7, 0.05], [2.9, 3.7, 1.35], [2.9, 0.3, 1.35]];
  S.face(g, 'var(--iso-glass)');
  S.line([...g, g[0]], 'var(--iso-glass-edge)', 1);
  S.line([[2.9, 2.1, 0.7], [2.9, 2.1, 0.2]], A, 1.4, null, 0.8);
  S.box(2.75, 0.15, 1.35, 0.3, 3.7, 0.18, { gloss: false });
  return S.svg();
};
