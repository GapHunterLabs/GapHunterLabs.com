// Evaluated in a page by pipeline/critical_css.py (Playwright). Two modes:
//   ["paths", foldPx, []]   the paths ("sheet/rule/rule") of the style rules that apply to an element in the first
//                           foldPx pixels of this render, plus every @font-face and @property;
//   ["emit", 0, paths]      the CSS text of those paths in source order, with their @media/@supports/@layer wrappers,
//                           followed by the @keyframes that the kept rules name.
// Only the site's own stylesheets under /css/ are read; the inline <style id="critical-css"> is skipped.
([mode, fold, wanted]) => {
  // State that depends on the user (hover, focus...) is ignored for matching: "a:hover" is kept when an "a" is on the
  // first screen. Pseudo-elements are matched through their element.
  const DYNAMIC = /:(hover|focus-visible|focus-within|focus|active|visited|target|placeholder-shown|autofill|-webkit-autofill)(?![\w-])/g;
  const PSEUDO_EL = /::?(before|after|placeholder|selection|marker|backdrop|first-line|first-letter|file-selector-button|-webkit-[\w-]+|-moz-[\w-]+)(\([^)]*\))?/g;
  // Anything that starts above the fold counts, including what a rule moves off the top of the screen (the skip link):
  // without that rule it would sit in the flow and push the header down. An element without a box (display: none, a
  // 0x0 sprite, a menu hidden at this width) counts where its closest ancestor with a box is, for the same reason.
  const onFirstScreen = (el) => {
    for (let n = el; n; n = n.parentElement) {
      if (n === document.documentElement || n === document.body) return true;
      const r = n.getBoundingClientRect();
      if (r.width > 0 || r.height > 0) return r.top < fold;
    }
    return false;
  };
  const splitList = (sel) => {
    const out = [];
    let depth = 0, cur = "";
    for (const ch of sel) {
      if (ch === "(" || ch === "[") depth++;
      if (ch === ")" || ch === "]") depth--;
      if (ch === "," && !depth) { out.push(cur); cur = ""; } else cur += ch;
    }
    out.push(cur);
    return out;
  };
  const applies = (selectorText) => {
    for (const part of splitList(selectorText)) {
      const s = part.replace(PSEUDO_EL, "").replace(DYNAMIC, "").replace(/[>+~]\s*$/, "").trim() || "*";
      let nodes;
      try { nodes = document.querySelectorAll(s); } catch (e) { return true; } // cannot test it: keep it
      for (const n of nodes) if (onFirstScreen(n)) return true;
    }
    return false;
  };
  const sheets = [...document.styleSheets].filter((sh) => sh.href && new URL(sh.href).pathname.startsWith("/css/"));
  const isGrouping = (r) => r.cssRules && !(r instanceof CSSKeyframesRule) && !(r instanceof CSSStyleRule);
  const alwaysKept = (r) => r instanceof CSSFontFaceRule || (window.CSSPropertyRule && r instanceof CSSPropertyRule)
    || (window.CSSLayerStatementRule && r instanceof CSSLayerStatementRule);

  if (mode === "paths") {
    const paths = [];
    const walk = (rules, prefix) => {
      [...rules].forEach((r, i) => {
        const p = prefix + "/" + i;
        if (r instanceof CSSStyleRule) { if (applies(r.selectorText)) paths.push(p); }
        else if (alwaysKept(r)) paths.push(p);
        else if (isGrouping(r)) walk(r.cssRules, p);
      });
    };
    sheets.forEach((sh, k) => walk(sh.cssRules, String(k)));
    return { sheets: sheets.map((sh) => new URL(sh.href).pathname), paths };
  }

  const want = new Set(wanted);
  const parents = new Set();
  for (const p of want) {
    const parts = p.split("/");
    for (let i = 2; i < parts.length; i++) parents.add(parts.slice(0, i).join("/"));
  }
  const animations = new Set();
  const emit = (rules, prefix) => {
    let out = "";
    [...rules].forEach((r, i) => {
      const p = prefix + "/" + i;
      if (want.has(p)) {
        out += r.cssText;
        if (r.style) {
          for (const prop of ["animation-name", "animation"]) {
            const v = r.style.getPropertyValue(prop);
            if (v) v.split(/[\s,]+/).forEach((t) => animations.add(t));
          }
        }
      } else if (parents.has(p) && isGrouping(r)) {
        out += r.cssText.slice(0, r.cssText.indexOf("{") + 1) + emit(r.cssRules, p) + "}";
      }
    });
    return out;
  };
  let css = sheets.map((sh, k) => emit(sh.cssRules, String(k))).join("");
  for (const sh of sheets) {
    for (const r of sh.cssRules) if (r instanceof CSSKeyframesRule && animations.has(r.name)) css += r.cssText;
  }
  return css;
}
