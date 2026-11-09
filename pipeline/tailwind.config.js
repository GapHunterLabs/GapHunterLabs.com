/* Tailwind CLI config for the static site. Compiled by `npm run build:css` into ../css/tw.css.
 * - prefix "tw-": the site already has ~300 hand-written classes; utilities never collide.
 * - preflight off: the existing base.css owns resets.
 * - colors are the CSS tokens of css/theme.css, so light/dark/System keep working without `dark:` variants.
 */
module.exports = {
  prefix: 'tw-',
  content: {
    files: [
      '../**/*.html', '../js/*.js', './*.py',
      '!../node_modules/**', '!./node_modules/**', '!../_review/**',
      // generated copies: their classes come from the .py generators scanned above
      '!../catalog/**', '!../es/**',
    ],
    // 2026-11-09: Tailwind reads the Python generators as if they were markup, so Python text shaped like an
    // arbitrary property, "[name:value]" (a slice such as text[line_start:at], or the "[ctx:gh-nav-link]"
    // translation keys), became CSS rules such as .\[line_start\:at\]{line_start:at}. No page uses those classes;
    // they only made css/tw.css drift. A real arbitrary property on this site would be written tw-[name:value]
    // (none exists today), so that form is kept.
    transform: {
      py: (content) => content.replace(/(?<!tw-)\[[a-z_<][^\]\s"']*:[^\]\s"']*\]/gi, ' '),
    },
  },
  corePlugins: { preflight: false },
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)', surface: 'var(--surface)', 'surface-2': 'var(--surface-2)', 'surface-3': 'var(--surface-3)',
        line: 'var(--border)', 'line-strong': 'var(--border-strong)',
        ink: 'var(--text)', dim: 'var(--text-dim)', faint: 'var(--text-faint)',
        signal: 'var(--signal)', valid: 'var(--valid)', inspect: 'var(--inspect)', bad: 'var(--bad)',
      },
      fontFamily: { sans: 'var(--sans)', mono: 'var(--mono)' },
      borderRadius: { DEFAULT: 'var(--radius)', md: 'var(--radius-md)', lg: 'var(--radius-lg)' },
    },
  },
};
