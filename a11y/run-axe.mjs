// Accessibility gate for the Gap Hunter Labs static site.
//
// Injects the bundled axe-core into a current headless Chromium (managed by
// puppeteer) and checks every funnel page against WCAG 2.1 AA, in both the
// light and dark color schemes. Fails (exit 1) on any violation.
//
// Why a self-contained runner instead of pa11y-ci: pa11y-ci@3 bundles
// axe-core 4.2, whose color-contrast algorithm reports false positives on
// elements rendered with modern CSS (e.g. color-mix tints) that no current
// browser mis-renders. Confirmed 2026-11-02: the same pages are clean under
// axe-core 4.14 in both an old (Chrome 90) and a current (Chrome 156) engine.
// Using @axe-core/cli instead ran into a ChromeDriver/Chrome version mismatch.
// A puppeteer-managed browser removes the separate-driver problem entirely.

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import puppeteer from "puppeteer";
import axe from "axe-core";

const axeSource = axe.source;

const here = dirname(fileURLToPath(import.meta.url));
const BASE = process.env.BASE_URL || "http://localhost:8080";
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const THEMES = ["light", "dark"];

const { paths } = JSON.parse(await readFile(join(here, "urls.json"), "utf8"));

const browser = await puppeteer.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--force-prefers-reduced-motion"],
});

let totalViolations = 0;
const failed = [];

for (const path of paths) {
  const url = BASE + path;
  for (const theme of THEMES) {
    const page = await browser.newPage();
    await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: theme }]);
    await page.goto(url, { waitUntil: "networkidle0", timeout: 60000 });
    // Let scroll-reveal / deferred chrome settle, mirroring the old `wait: 1000`.
    await new Promise((r) => setTimeout(r, 1000));
    await page.evaluate(axeSource);
    const results = await page.evaluate(async (tags) => {
      return await axe.run(document, {
        runOnly: { type: "tag", values: tags },
        resultTypes: ["violations"],
      });
    }, TAGS);
    await page.close();

    const count = results.violations.reduce((a, v) => a + v.nodes.length, 0);
    if (count > 0) {
      totalViolations += count;
      failed.push({ path, theme });
      console.log(`✘ ${path} [${theme}] — ${count} violation node(s)`);
      for (const v of results.violations) {
        console.log(`    ${v.id} (${v.impact}): ${v.help}`);
        for (const n of v.nodes.slice(0, 8)) {
          const d = (n.any[0] && n.any[0].data) || {};
          const extra =
            v.id === "color-contrast"
              ? ` [fg=${d.fgColor} bg=${d.bgColor} ratio=${d.contrastRatio} need=${d.expectedContrastRatio}]`
              : "";
          console.log(`      - ${n.target.join(" ")}${extra}`);
        }
      }
    } else {
      console.log(`✓ ${path} [${theme}]`);
    }
  }
}

await browser.close();

console.log("");
if (totalViolations > 0) {
  console.log(
    `Accessibility gate FAILED: ${totalViolations} violation node(s) across ${failed.length} page/theme combination(s).`
  );
  process.exit(1);
}
console.log(
  `Accessibility gate passed: ${paths.length} pages × ${THEMES.length} themes, 0 WCAG 2.1 AA violations.`
);
