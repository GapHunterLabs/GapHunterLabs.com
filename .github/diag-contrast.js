// Temporary diagnostic: dump exact color-contrast details (fg/bg/ratio) for the
// home page using Puppeteer's bundled Chromium + axe-core. Removed after the fix.
const puppeteer = require("puppeteer");
const axeSource = require("axe-core").source;

(async () => {
  const browser = await puppeteer.launch({
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.goto("http://localhost:8080/", { waitUntil: "load" });
  await new Promise((r) => setTimeout(r, 800)); // let the panel animation settle
  await page.evaluate(axeSource);
  const res = await page.evaluate(async () =>
    await axe.run(document, { runOnly: ["color-contrast"] })
  );
  for (const v of res.violations) {
    for (const n of v.nodes) {
      const d = (n.any[0] || {}).data || {};
      console.log(
        "TARGET " + JSON.stringify(n.target) +
        " | fg=" + d.fgColor + " bg=" + d.bgColor +
        " ratio=" + d.contrastRatio + " expected=" + d.expectedContrastRatio +
        " size=" + d.fontSize + " weight=" + d.fontWeight
      );
    }
  }
  console.log("VIOLATIONS " + res.violations.length);
  await browser.close();
})();
