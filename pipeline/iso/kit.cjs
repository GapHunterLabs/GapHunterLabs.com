// Isometric figure kit. Geometry and projection come from @elchininet/isometric (build time only);
// the finish (materials, light, shadows) comes from the shared layer below. Output: one static,
// themeable SVG string per figure. Nothing here runs in the browser.
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>');
global.window = dom.window; global.document = dom.window.document;
const { IsometricCanvas, IsometricPath } = require('@elchininet/isometric/node');

const COS30 = Math.cos(Math.PI / 6), SIN30 = 0.5;
const BUDGET = { bytes: 40 * 1024, nodes: 400 };
const PAD = 0.05;   // safety margin around the drawing, as a share of its larger side (scales with every viewport)

const sc = (v, op) => `stop-color:var(${v})` + (op ? `;stop-opacity:${op}` : '');
function defs(p) {
  // Every color reads a --iso-* variable from css/theme.css, so the inline SVG follows the light and dark themes.
  // p = per-figure id prefix: two figures on one page never share ids.
  return '<defs>'
    + `<linearGradient id="${p}top" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="${sc('--iso-top-1')}"/><stop offset=".45" style="${sc('--iso-top-2')}"/><stop offset="1" style="${sc('--iso-top-3')}"/></linearGradient>`
    + `<linearGradient id="${p}left" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="${sc('--iso-left-1')}"/><stop offset="1" style="${sc('--iso-left-2')}"/></linearGradient>`
    + `<linearGradient id="${p}right" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="${sc('--iso-right-1')}"/><stop offset="1" style="${sc('--iso-right-2')}"/></linearGradient>`
    + `<linearGradient id="${p}metal" x1="0" y1="0" x2="1" y2="0"><stop offset="0" style="${sc('--iso-metal-2')}"/><stop offset=".5" style="${sc('--iso-metal-1')}"/><stop offset="1" style="${sc('--iso-metal-2')}"/></linearGradient>`
    + `<linearGradient id="${p}bezel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="${sc('--iso-bezel-1')}"/><stop offset="1" style="${sc('--iso-bezel-2')}"/></linearGradient>`
    + `<linearGradient id="${p}screen" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="${sc('--iso-screen-1')}"/><stop offset="1" style="${sc('--iso-screen-2')}"/></linearGradient>`
    + `<linearGradient id="${p}gloss" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="${sc('--iso-gloss', 'var(--iso-gloss-op)')}"/><stop offset=".42" style="${sc('--iso-gloss', '0')}"/></linearGradient>`
    + `<radialGradient id="${p}shadow"><stop offset="0" style="${sc('--iso-shadow', 'var(--iso-shadow-op)')}"/><stop offset=".55" style="${sc('--iso-shadow', 'calc(var(--iso-shadow-op) * .45)')}"/><stop offset="1" style="${sc('--iso-shadow', '0')}"/></radialGradient>`
    + `<radialGradient id="${p}halo"><stop offset="0" style="${sc('--iso-accent', 'var(--iso-halo-op)')}"/><stop offset=".6" style="${sc('--iso-accent', 'calc(var(--iso-halo-op) * .35)')}"/><stop offset="1" style="${sc('--iso-accent', '0')}"/></radialGradient>`
    + '</defs>';
}

class Scene {
  // center: the scene point placed at the canvas center (the library's fixed origin).
  constructor({ id, scale, center = [0, 0, 0] }) {
    this.p = id + '-';
    this.s = scale;
    this.c = center;
    this.canvas = new IsometricCanvas({ backgroundColor: 'transparent', scale, width: 1000, height: 1000 });
    this.ox = 500; this.oy = 500;
    this.under = []; this.seq = [];   // painter's order: library faces ({face}) and 2D details ({raw}) in call order
    this.n = 0;
    this.box2d = [Infinity, Infinity, -Infinity, -Infinity];
  }
  grow(x, y, rx = 0, ry = 0) {
    const b = this.box2d;
    b[0] = Math.min(b[0], x - rx); b[1] = Math.min(b[1], y - ry); b[2] = Math.max(b[2], x + rx); b[3] = Math.max(b[3], y + ry);
  }
  proj(r, l, t) {   // same projection the library uses
    r -= this.c[0]; l -= this.c[1]; t -= this.c[2];
    return [this.ox + (r - l) * COS30 * this.s, this.oy + (r + l) * SIN30 * this.s - t * this.s];
  }
  push(str, layer) { (layer === 'under' ? this.under : this.seq).push({ raw: str }); }
  face(points, fill, opts = {}) {
    const id = `${this.p}f${this.n++}`;
    const path = new IsometricPath({ id, fillColor: fill, strokeColor: 'none', strokeWidth: 0, ...(opts.op != null ? { fillOpacity: opts.op } : {}) });
    const [cr, cl, ct] = this.c;
    points.forEach(([r, l, t], i) => {
      this.grow(...this.proj(r, l, t));
      i ? path.lineTo(r - cr, l - cl, t - ct) : path.moveTo(r - cr, l - cl, t - ct);
    });
    this.canvas.addChild(path);
    this.seq.push({ face: id, cls: opts.cls });
  }
  // Box from (r,l,t) with extents w (right), d (left), h (up): three visible faces, gloss and edge light.
  box(r, l, t, w, d, h, mat = {}) {
    const P = this.p, T = t + h;
    const top = [[r, l, T], [r + w, l, T], [r + w, l + d, T], [r, l + d, T]];
    this.face(top, mat.top || `url(#${P}top)`);
    this.face([[r, l + d, t], [r + w, l + d, t], [r + w, l + d, T], [r, l + d, T]], mat.left || `url(#${P}left)`);
    this.face([[r + w, l, t], [r + w, l + d, t], [r + w, l + d, T], [r + w, l, T]], mat.right || `url(#${P}right)`);
    if (mat.gloss !== false) this.face(top, `url(#${P}gloss)`);
    this.line([[r, l + d, T], [r, l, T], [r + w, l, T]], 'var(--iso-edge)', 0.9);              // edges facing the light
    this.line([[r, l + d, T], [r + w, l + d, T], [r + w, l, T]], 'var(--iso-edge)', 0.7, null, 0.55);
    this.line([[r + w, l + d, T], [r + w, l + d, t]], 'var(--iso-edge)', 0.7, null, 0.5);     // front vertical edge
  }
  pathData(segs) {
    return segs.map((pts) => pts.map(([r, l, t], i) => {
      const [x, y] = this.proj(r, l, t); this.grow(x, y);
      return (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
    }).join('')).join('');
  }
  line(pts, stroke, width = 1, cls, opacity = 1) { this.multiline([pts], stroke, width, cls, opacity); }
  multiline(segs, stroke, width, cls, opacity = 1) {   // many segments in ONE path node
    const c = cls ? ` class="${cls}"` : '';
    this.push(`<path${c} d="${this.pathData(segs)}" fill="none" stroke="${stroke}" stroke-width="${width}"${opacity !== 1 ? ` stroke-opacity="${opacity}"` : ''} stroke-linecap="round" stroke-linejoin="round"/>`);
  }
  ellipse(r, l, t, rx, ry, fill, layer) {
    const [x, y] = this.proj(r, l, t);
    this.grow(x, y, rx, ry);
    this.push(`<ellipse cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" rx="${rx.toFixed(1)}" ry="${ry.toFixed(1)}" fill="${fill}"/>`, layer);
  }
  shadow(r, l, w, d, spread = 1.15, layer) {   // contact shadow: projected ellipse + radial gradient, no blur filter
    const rx = ((w + d) / 2) * COS30 * this.s * spread;
    this.ellipse(r + w / 2, l + d / 2, -0.08, rx, rx * 0.5, `url(#${this.p}shadow)`, layer);
  }
  halo(r, l, t, radius) { const rx = radius * this.s; this.ellipse(r, l, t, rx, rx * 0.55, `url(#${this.p}halo)`, 'under'); }
  dot(r, l, t, rad, fill) { this.ellipse(r, l, t, rad, rad * 0.7, fill); }
  // A circle of radius R lying in a horizontal plane at height t: an ellipse whose axes follow the projection.
  disc(r, l, t, R, fill, stroke, width = 1, opacity = 1) {
    const [x, y] = this.proj(r, l, t);
    const rx = R * this.s * Math.SQRT2 * COS30, ry = R * this.s * Math.SQRT2 * SIN30;
    this.grow(x, y, rx, ry);
    const st = stroke ? ` stroke="${stroke}" stroke-width="${width}"${opacity !== 1 ? ` stroke-opacity="${opacity}"` : ''}` : '';
    this.push(`<ellipse cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" rx="${rx.toFixed(1)}" ry="${ry.toFixed(1)}" fill="${fill || 'none'}"${st}/>`);
  }

  svg() {
    const code = this.canvas.getSVGCode();
    const faces = {};
    for (const m of code.matchAll(/<path id="([^"]+)" ([^>]*) d="([^"]+)"><\/path>/g)) {
      const fill = m[2].match(/fill="([^"]+)"/)[1];
      const op = (m[2].match(/fill-opacity="([^"]+)"/) || [])[1];
      faces[m[1]] = { fill, op, d: m[3] };
    }
    const body = this.seq.map((x) => {
      if (!x.face) return x.raw;
      const f = faces[x.face];
      return `<path${x.cls ? ` class="${x.cls}"` : ''} fill="${f.fill}"${f.op && f.op !== '1' ? ` fill-opacity="${f.op}"` : ''} d="${f.d}"/>`;
    }).join('');
    const [x0, y0, x1, y1] = this.box2d;
    const pad = Math.max(x1 - x0, y1 - y0) * PAD;
    const vb = [x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad].map((v) => +v.toFixed(1));
    return `<svg class="iso-figure" viewBox="${vb.join(' ')}" width="${Math.round(vb[2])}" height="${Math.round(vb[3])}" aria-hidden="true" focusable="false">`
      + defs(this.p) + this.under.map((x) => x.raw).join('') + body + '</svg>';
  }
}

function measure(svg) {
  return { bytes: Buffer.byteLength(svg), nodes: (svg.match(/<(?!\/)[a-zA-Z]/g) || []).length,
           blurFilters: (svg.match(/feGaussianBlur/g) || []).length };
}

module.exports = { Scene, BUDGET, measure };
