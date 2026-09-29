// In-memory Firestore that evaluates the app's query objects
// (where / orderBy / startAt / startAfter / endAt / limit) with Firestore semantics:
//  - where/orderBy on a missing field excludes the document
//  - type-strict equality ("2020" !== 2020)
//  - implicit __name__ tie-breaker in the direction of the last orderBy
//  - optional "no composite index" mode that throws like Firestore does
const TYPE_RANK = v => v === null ? 0 : typeof v === "boolean" ? 1 : typeof v === "number" ? 2 : typeof v === "string" ? 4 : Array.isArray(v) ? 9 : 10;

export function cmpValues(a, b) {
  const ta = TYPE_RANK(a), tb = TYPE_RANK(b);
  if (ta !== tb) return ta - tb;
  if (a === b) return 0;
  if (ta === 9) { // arrays: element-wise
    for (let i = 0; i < Math.min(a.length, b.length); i++) { const c = cmpValues(a[i], b[i]); if (c) return c; }
    return a.length - b.length;
  }
  return a < b ? -1 : 1;
}

function fieldVal(doc, field) { return field === "__name__" ? doc.id : doc.data[field]; }
function has(doc, field) { return field === "__name__" || Object.prototype.hasOwnProperty.call(doc.data, field); }

function matchWhere(doc, w) {
  if (!has(doc, w.field)) return false;
  const v = fieldVal(doc, w.field);
  switch (w.op) {
    case "==": return cmpValues(v, w.value) === 0;
    case "!=": return cmpValues(v, w.value) !== 0;
    case "in": return w.value.some(x => cmpValues(v, x) === 0);
    case "array-contains": return Array.isArray(v) && v.some(x => cmpValues(x, w.value) === 0);
    case "array-contains-any": return Array.isArray(v) && v.some(x => w.value.some(y => cmpValues(x, y) === 0));
    case ">=": return TYPE_RANK(v) === TYPE_RANK(w.value) && cmpValues(v, w.value) >= 0;
    case ">": return TYPE_RANK(v) === TYPE_RANK(w.value) && cmpValues(v, w.value) > 0;
    case "<=": return TYPE_RANK(v) === TYPE_RANK(w.value) && cmpValues(v, w.value) <= 0;
    case "<": return TYPE_RANK(v) === TYPE_RANK(w.value) && cmpValues(v, w.value) < 0;
    default: throw new Error("op not supported: " + w.op);
  }
}

export function makeFakeDb(rows, { compositeIndex = true, delay = 0, delayFor = null, extraCollections = {} } = {}) {
  const store = { MOVIES: rows.map(r => ({ id: r.id, data: { ...r } })) };
  for (const [name, list] of Object.entries(extraCollections)) store[name] = list.map(r => ({ id: r.id, data: { ...r } }));
  Object.values(store).forEach(list => list.forEach(d => delete d.data.id));
  const stats = { queries: 0, reads: 0, indexErrors: 0, log: [] };

  const snap = (colName, d) => ({
    id: d.id,
    name: `projects/movie-858f6/databases/(default)/documents/${colName}/${d.id}`,
    _fields: {},
    _doc: d,
    exists: () => true,
    data: () => JSON.parse(JSON.stringify(d.data)),
  });

  async function getDocs(q) {
    const colName = q.col.name;
    const list = store[colName] || [];
    const parts = q.parts;
    const wheres = parts.filter(p => p.type === "where");
    const orders = parts.filter(p => p.type === "orderBy").map(o => ({ field: o.field, desc: o.dir === "desc" }));
    const start = parts.filter(p => p.type === "start").pop();
    const end = parts.filter(p => p.type === "end").pop();
    const lim = parts.filter(p => p.type === "limit").pop();
    stats.queries++;

    const wait = typeof delayFor === "function" ? delayFor(q) : delay;
    if (wait) await new Promise(r => setTimeout(r, wait));

    // composite-index rule: filters on field(s) other than the (non-__name__) orderBy field need a composite index
    const orderFields = orders.map(o => o.field).filter(f => f !== "__name__");
    const whereFields = [...new Set(wheres.map(w => w.field))];
    if (!compositeIndex && orderFields.length && whereFields.some(f => !orderFields.includes(f))) {
      stats.indexErrors++;
      throw new Error("FAILED_PRECONDITION: The query requires an index. You can create it here: https://console.firebase.google.com/project/movie-858f6/firestore/indexes?create_composite=fake");
    }

    let docs = list.filter(d => wheres.every(w => matchWhere(d, w)) && orders.every(o => has(d, o.field)));
    const fullOrder = orders.slice();
    if (!fullOrder.length || fullOrder[fullOrder.length - 1].field !== "__name__") {
      fullOrder.push({ field: "__name__", desc: fullOrder.length ? fullOrder[fullOrder.length - 1].desc : false });
    }
    const keyOf = d => fullOrder.map(o => fieldVal(d, o.field));
    const cmpKey = (ka, kb) => {
      for (let i = 0; i < Math.min(ka.length, kb.length); i++) {
        const c = cmpValues(ka[i], kb[i]) * (fullOrder[i].desc ? -1 : 1);
        if (c) return c;
      }
      return 0;
    };
    docs.sort((a, b) => cmpKey(keyOf(a), keyOf(b)));

    const cursorKey = c => (c.values.length === 1 && c.values[0] && c.values[0]._doc)
      ? keyOf(c.values[0]._doc)
      : c.values.map((v, i) => (fullOrder[i] && fullOrder[i].field === "__name__" && v && v._doc) ? v._doc.id : v);
    if (start) {
      const k = cursorKey(start);
      docs = docs.filter(d => { const c = cmpKey(keyOf(d), k); return start.before ? c >= 0 : c > 0; });
    }
    if (end) {
      const k = cursorKey(end);
      docs = docs.filter(d => { const c = cmpKey(keyOf(d), k); return end.before ? c < 0 : c <= 0; });
    }
    if (lim) docs = docs.slice(0, lim.n);
    stats.reads += Math.max(1, docs.length);
    stats.log.push({ col: colName, wheres: wheres.map(w => `${w.field} ${w.op}`), orders: orders.map(o => o.field + (o.desc ? " desc" : "")), n: docs.length });
    const out = docs.map(d => snap(colName, d));
    return { docs: out, size: out.length, empty: out.length === 0 };
  }

  async function getDoc(ref) {
    const [colName, id] = ref.path.split("/");
    const d = (store[colName] || []).find(x => x.id === id);
    stats.reads++;
    return d ? snap(colName, d) : { id, exists: () => false, data: () => undefined };
  }

  return { getDocs, getDoc, stats, store };
}
