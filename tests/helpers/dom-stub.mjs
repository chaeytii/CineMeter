// Minimal browser stand-in so DOM-touching app functions can run in Node.
// Elements remember what the app writes to them (innerText, innerHTML, style, hidden, children).
function makeClassList() {
  const s = new Set();
  return {
    add: (...c) => c.forEach(x => s.add(x)),
    remove: (...c) => c.forEach(x => s.delete(x)),
    toggle: (c, force) => { const on = force === undefined ? !s.has(c) : !!force; on ? s.add(c) : s.delete(c); return on; },
    contains: c => s.has(c),
  };
}

function makeEl(tag = "div", id = "") {
  const el = {
    tagName: tag.toUpperCase(), id, children: [], style: { setProperty() {}, removeProperty() {} },
    dataset: {}, classList: makeClassList(), hidden: false, innerText: "", textContent: "", value: "",
    _html: "", parentNode: null, offsetHeight: 60, offsetWidth: 100, clientWidth: 1200, scrollTop: 0, scrollHeight: 0,
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); this.children = []; },
    get childElementCount() { return this.children.length; },
    appendChild(c) { this.children.push(c); c.parentNode = this; return c; },
    insertBefore(c) { this.children.push(c); c.parentNode = this; return c; },
    remove() {}, focus() {}, scrollBy() {}, scrollIntoView() {}, addEventListener() {}, removeEventListener() {},
    setAttribute(k, v) { this[k] = v; }, getAttribute(k) { return this[k]; },
    querySelector() { return makeEl(); }, querySelectorAll() { return []; },
    matches() { return false; },
  };
  el.parentNode = { insertBefore() {}, appendChild() {} };
  return el;
}

const byId = new Map();
export const document = {
  getElementById(id) { if (!byId.has(id)) byId.set(id, makeEl("div", id)); return byId.get(id); },
  createElement: tag => makeEl(tag),
  querySelector: () => makeEl(),
  querySelectorAll: () => [],
  getElementsByClassName: () => [],
  addEventListener() {},
  documentElement: makeEl("html"),
  hidden: false,
};

export function installDom() {
  globalThis.document = document;
  globalThis.window = globalThis;
  globalThis.scrollY = 0;
  globalThis.scrollTo = () => {};
  globalThis.requestAnimationFrame = cb => { cb(); return 0; };
  globalThis.matchMedia = () => ({ matches: false });
  globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
  globalThis.Image = class { set src(_) { setTimeout(() => this.onload && this.onload(), 0); } };
  const mem = new Map();
  globalThis.localStorage = {
    getItem: k => (mem.has(k) ? mem.get(k) : null),
    setItem: (k, v) => mem.set(k, String(v)),
    removeItem: k => mem.delete(k),
    clear: () => mem.clear(),
  };
}

export function resetDom() { byId.clear(); globalThis.localStorage && globalThis.localStorage.clear(); }
