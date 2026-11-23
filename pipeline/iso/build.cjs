// Renders every figure in figures/ to out/<name>.svg and fails if one breaks the budget.
//   node pipeline/iso/build.cjs          (python pipeline/build_iso_figures.py runs it)
// The SVG files in out/ are committed: the page generators inline them, so a rebuild of the site never needs Node.
// pipeline/iso_figures.py applies the same rules again when a page inlines a figure.
const fs = require('fs');
const path = require('path');
const { BUDGET, measure } = require('./kit.cjs');

const OUT = path.join(__dirname, 'out');

function problemsOf(name, svg) {
  const m = measure(svg);
  const problems = [];
  if (m.bytes > BUDGET.bytes) problems.push(`bytes ${m.bytes} > ${BUDGET.bytes}`);
  if (m.nodes > BUDGET.nodes) problems.push(`nodes ${m.nodes} > ${BUDGET.nodes}`);
  if (/<filter\b|\sfilter=|feGaussianBlur|feTurbulence/.test(svg)) problems.push('uses a live filter');
  const ids = [...svg.matchAll(/ id="([^"]+)"/g)].map((x) => x[1]);
  if (ids.some((i) => !i.startsWith('iso-' + name + '-'))) problems.push('an id is missing the figure prefix');
  const hard = svg.replace(/url\(#[^)]+\)/g, '').match(/#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/g) || [];
  // every paint value is a --iso-* variable or a gradient of the figure; a named color ("red") is hard-coded too
  const allowed = /^(var\(--iso-[a-z0-9-]+\)|url\(#[A-Za-z0-9_-]+\)|none|transparent|currentColor)$/;
  const paints = [...svg.matchAll(/\b(?:fill|stroke|color)="([^"]*)"/g), ...svg.matchAll(/(?:stop-color|fill|stroke|color)\s*:\s*([^;"]+)/g)];
  for (const m of paints) if (!allowed.test(m[1].trim())) hard.push(m[1].trim());
  if (hard.length) problems.push('hard-coded colors: ' + hard.slice(0, 3).join(', '));
  const svgTag = (svg.match(/^<svg\b[^>]*>/) || [''])[0];
  if (!/ aria-hidden="true"/.test(svgTag)) problems.push('the <svg> is not aria-hidden="true"');
  const turquoise = (svg.match(/--iso-accent-2\b/g) || []).length;
  if (turquoise > 1) problems.push(`${turquoise} turquoise details (at most 1)`);
  return { ...m, turquoise, problems };
}

function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const report = {};
  let failed = false;
  const files = fs.readdirSync(path.join(__dirname, 'figures')).filter((f) => f.endsWith('.cjs')).sort();
  for (const file of files) {
    const name = path.basename(file, '.cjs');
    const svg = require(path.join(__dirname, 'figures', file))('iso-' + name);
    const r = problemsOf(name, svg);
    report[name] = r;
    if (r.problems.length) failed = true;
    fs.writeFileSync(path.join(OUT, name + '.svg'), svg + '\n');
    console.log(`${name}: ${r.bytes} B, ${r.nodes} nodes${r.problems.length ? '  FAIL: ' + r.problems.join('; ') : '  OK'}`);
  }
  fs.writeFileSync(path.join(OUT, 'budget.json'), JSON.stringify({ budget: BUDGET, figures: report }, null, 1) + '\n');
  return failed ? 1 : 0;
}

module.exports = { problemsOf };
if (require.main === module) process.exit(main());
