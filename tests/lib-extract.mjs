// JS declaration scanner shared by extract.mjs and build-check-page.mjs
// ---------- minimal JS scanner: finds the end of a declaration ----------
export function scanEnd(code, from, mode) {
  // mode "block": end at matching } of first { ; mode "stmt": end at ; at depth 0
  let depth = 0, i = from, started = false;
  const tmplStack = [];
  let lastSig = "";           // last significant char, for regex detection
  let lastWord = "";
  while (i < code.length) {
    const c = code[i], n = code[i + 1];
    if (c === "/" && n === "/") { i = code.indexOf("\n", i); if (i < 0) i = code.length; continue; }
    if (c === "/" && n === "*") { i = code.indexOf("*/", i + 2) + 2; continue; }
    if (c === '"' || c === "'") {
      i++;
      while (code[i] !== c) { if (code[i] === "\\") i++; i++; }
      i++; lastSig = c; lastWord = ""; continue;
    }
    if (c === "`") {
      i++;
      // template literal (with ${ } nesting)
      let tdepth = 0;
      while (i < code.length) {
        if (code[i] === "\\") { i += 2; continue; }
        if (tdepth === 0 && code[i] === "`") break;
        if (code[i] === "$" && code[i + 1] === "{") {
          // scan the expression recursively until matching }
          const e = scanEnd(code, i + 1, "brace-only");
          i = e; continue;
        }
        i++;
      }
      i++; lastSig = "`"; lastWord = ""; continue;
    }
    if (c === "/") {
      const regexOk = lastSig === "" || "(,=:[!&|?{};+-*%<>~^".includes(lastSig) || ["return", "typeof", "case", "in", "of"].includes(lastWord);
      if (regexOk) {
        i++;
        let inClass = false;
        while (i < code.length) {
          const r = code[i];
          if (r === "\\") { i += 2; continue; }
          if (r === "[") inClass = true;
          else if (r === "]") inClass = false;
          else if (r === "/" && !inClass) break;
          i++;
        }
        i++;
        while (/[a-z]/i.test(code[i])) i++;
        lastSig = "/"; lastWord = ""; continue;
      }
    }
    if (/[A-Za-z_$]/.test(c)) {
      let j = i; while (/[A-Za-z0-9_$]/.test(code[j])) j++;
      lastWord = code.slice(i, j); lastSig = "a"; i = j; continue;
    }
    if (c === "{" || c === "(" || c === "[") { depth++; started = true; }
    if (c === "}" || c === ")" || c === "]") {
      depth--;
      if (mode === "brace-only" && depth === 0) return i + 1;
      if (mode === "block" && depth === 0 && c === "}" && started) return i + 1;
    }
    if (mode === "stmt" && c === ";" && depth === 0) return i + 1;
    if (!/\s/.test(c)) { lastSig = c; lastWord = ""; }
    i++;
  }
  throw new Error("scan ran off the end");
}

export function findDecl(src, name, scriptLineOffset = 0) {
  const patterns = [
    new RegExp(`^[ \\t]*(async\\s+)?function\\s+${name}\\s*\\(`, "m"),
    new RegExp(`^[ \\t]*(const|let)\\s+${name}\\s*=`, "m"),
  ];
  for (const re of patterns) {
    const m = re.exec(src);
    if (!m) continue;
    const at = m.index + m[0].length - m[0].trimStart().length + (m[0].length - m[0].trimStart().length === 0 ? 0 : 0);
    const isFn = /function/.test(m[0]);
    const s = m.index;
    let e;
    if (isFn) e = scanEnd(src, s + m[0].length - 1, "block");
    else e = scanEnd(src, s + m[0].length, "stmt");
    const line = src.slice(0, s).split("\n").length + scriptLineOffset - 1;
    return { name, code: src.slice(s, e).replace(/^[ \t]+/, ""), line };
  }
  throw new Error("not found: " + name);
}


export function scriptOf(html) {
  const start = html.indexOf('<script type="module">');
  const end = html.lastIndexOf("</script>");
  return { src: html.slice(start + '<script type="module">'.length, end), offset: html.slice(0, start).split("\n").length };
}
