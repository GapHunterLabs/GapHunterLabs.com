// Sponsors hero: modules from three feeders move along a build line, through a build station, and leave as one
// finished package.
const { Scene } = require('../kit.cjs');

module.exports = function sponsors(id = 'iso-sponsors') {
  const S = new Scene({ id, scale: 38, center: [4.4, 2.4, 1.0] });
  const A = 'var(--iso-accent)', A2 = 'var(--iso-accent-2)', INK = 'var(--iso-ink)';

  S.shadow(-0.4, -0.4, 9.6, 5.6, 1.1);
  S.halo(6.4, 2.6, 0.6, 3.0);
  S.box(-0.4, -0.4, -0.35, 9.6, 5.6, 0.2, { gloss: false });
  S.box(0, 0, -0.15, 8.8, 4.8, 0.15);
  const grid = [];
  for (let i = 0.88; i < 8.8; i += 0.88) grid.push([[i, 0.15, 0], [i, 4.65, 0]]);
  for (let j = 0.96; j < 4.8; j += 0.96) grid.push([[0.15, j, 0], [8.65, j, 0]]);
  S.multiline(grid, 'var(--iso-line)', 0.8, 'iso-texture');
  S.line([[8.8, 0.6, 0], [8.8, 3.4, 0]], A, 1.6, null, 0.9);

  // feeders at the back: three small sources, each with a chute down to the line
  const feeders = [0.9, 2.4, 3.9];
  feeders.forEach((r) => {
    S.shadow(r, 0.4, 0.9, 0.7, 1.0);
    S.box(r, 0.4, 0, 0.9, 0.7, 0.9);
    S.multiline([[[r + 0.2, 1.1, 0.25], [r + 0.2, 1.1, 0.65]], [[r + 0.45, 1.1, 0.25], [r + 0.45, 1.1, 0.65]],
                 [[r + 0.7, 1.1, 0.25], [r + 0.7, 1.1, 0.65]]], INK, 0.9, 'iso-fine', 0.7);
    S.line([[r + 0.45, 1.1, 0.02], [r + 0.45, 1.75, 0.02]], INK, 1, null, 0.6);
  });

  // the build line: a long low track with flow chevrons
  S.shadow(0.3, 1.8, 8.2, 1.3, 1.0);
  S.box(0.3, 1.8, 0, 8.2, 1.3, 0.2);
  const T = 0.201, chev = [];
  for (let r = 0.7; r < 8.0; r += 0.9) chev.push([[r, 2.15, T], [r + 0.22, 2.45, T], [r, 2.75, T]]);
  S.multiline(chev, INK, 0.9, 'iso-fine', 0.6);

  // build station, back half (pillar behind the line)
  S.box(5.6, 1.45, 0, 1.3, 0.3, 1.9);
  // modules on the line, before the station
  const mod = (r, h, accent) => {
    S.shadow(r, 2.05, 0.8, 0.8, 0.9);
    S.box(r, 2.05, 0.2, 0.8, 0.8, h);
    S.dot(r + 0.4, 2.85, 0.2 + h / 2, 1.6, accent ? A : INK);
  };
  mod(1.0, 0.5); mod(2.5, 0.5); mod(4.0, 0.5, true);
  // inside the station: the module being built
  mod(5.85, 0.5);
  // station front pillar and beam with its status trace
  S.box(5.6, 3.1, 0, 1.3, 0.3, 1.9);
  S.box(5.6, 1.45, 1.9, 1.3, 1.95, 0.3);
  S.line([[5.75, 3.4, 2.05], [6.75, 3.4, 2.05]], A, 1.6);
  S.line([[6.9, 1.65, 2.05], [6.9, 3.2, 2.05]], A2, 1.2, null, 0.8);   // the figure's single turquoise detail
  // output: the finished package, banded in the accent
  S.shadow(7.35, 1.95, 1.0, 1.0, 1.0);
  S.box(7.35, 1.95, 0.2, 1.0, 1.0, 0.75);
  S.line([[7.35, 2.95, 0.6], [8.35, 2.95, 0.6], [8.35, 1.95, 0.6]], A, 1.6);
  S.line([[7.35, 2.45, 0.951], [8.35, 2.45, 0.951]], A, 1.2, null, 0.85);

  return S.svg();
};
