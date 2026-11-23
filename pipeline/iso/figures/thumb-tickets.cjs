// Evidence thumbnail, platform tickets: a generic IDE window (no product logo) and a ticket tag in front of it.
const { Scene } = require('../kit.cjs');

module.exports = function thumbTickets(id = 'iso-thumb-tickets') {
  const S = new Scene({ id, scale: 16, center: [2.0, 2.0, 1.2] });
  const P = S.p;
  const A = 'var(--iso-accent)', INK = 'var(--iso-ink)';
  S.shadow(-0.2, -0.2, 4.4, 4.4, 1.05);
  S.box(-0.2, -0.2, -0.3, 4.4, 4.4, 0.18, { gloss: false });
  S.box(0, 0, -0.12, 4.0, 4.0, 0.12);
  // window
  S.shadow(0.3, 0.4, 3.4, 0.4, 1.0);
  S.box(0.3, 0.4, 0.2, 3.4, 0.2, 2.4, { gloss: false });
  const W = (u, v) => [0.3 + 3.4 * u, 0.6, 0.2 + 2.4 * v];
  S.face([W(0, 0), W(1, 0), W(1, 1), W(0, 1)], `url(#${P}screen)`);
  S.line([W(0, 0.85), W(1, 0.85)], INK, 1, null, 0.8);
  S.dot(...W(0.05, 0.93), 1.8, INK); S.dot(...W(0.1, 0.93), 1.8, INK);
  S.line([W(0.27, 0.05), W(0.27, 0.85)], INK, 1, null, 0.7);
  S.multiline([[W(0.06, 0.7), W(0.21, 0.7)], [W(0.06, 0.55), W(0.18, 0.55)], [W(0.06, 0.4), W(0.2, 0.4)],
               [W(0.34, 0.7), W(0.8, 0.7)], [W(0.34, 0.55), W(0.66, 0.55)], [W(0.34, 0.25), W(0.72, 0.25)]], INK, 1.6, null, 0.9);
  S.line([W(0.34, 0.4), W(0.6, 0.4)], A, 2);
  S.face([W(0, 0), W(1, 0), W(1, 1), W(0, 1)], `url(#${P}gloss)`);
  S.line([W(0, 1), W(1, 1)], 'var(--iso-edge)', 1);
  // ticket tag lying in front
  S.shadow(1.6, 2.2, 2.0, 1.3, 1.0);
  S.box(1.6, 2.2, 0, 2.0, 1.3, 0.14);
  S.dot(1.9, 2.85, 0.141, 2.6, 'var(--iso-recess)');
  S.multiline([[[2.2, 2.6, 0.141], [3.3, 2.6, 0.141]], [[2.2, 2.95, 0.141], [3.0, 2.95, 0.141]]], INK, 1.6, null, 0.9);
  S.line([[2.2, 3.25, 0.141], [2.7, 3.25, 0.141]], A, 2.6);
  return S.svg();
};
