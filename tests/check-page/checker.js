/* =====================================================================
 * CineMeter — Live Data Check (read-only)
 * โค้ดด้านบนของไฟล์นี้คัดลอกมาจากแอปจริงแบบคำต่อคำ (REST client, สูตร, กติกา Recommend Side, Algolia, Gemini)
 * ส่วนนี้คือชุดตรวจที่เรียกใช้โค้ดชุดเดียวกับแอป แล้วสรุปผลเป็นตัวเลขสำหรับรายงาน
 * ===================================================================== */
const COL = "MOVIES";
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const R = { ranAt: null };
const f2 = (v, d = 2) => (v === null || v === undefined || !isFinite(v)) ? "—" : Number(v).toFixed(d);
const pct = (a, b) => b ? (100 * a / b).toFixed(1) + "%" : "—";
const out = id => $(`#out-${id}`);
const put = (id, html) => out(id).insertAdjacentHTML("beforeend", html);
const clear = id => { out(id).innerHTML = ""; };
const badge = ok => ok === null ? `<span class="b warn">ตรวจไม่ได้</span>` : ok ? `<span class="b ok">ผ่าน</span>` : `<span class="b bad">ไม่ผ่าน</span>`;
const table = (h, rows) => `<div class="tw"><table><thead><tr>${h.map(x => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
function stat(arr) {
  const a = arr.filter(Number.isFinite).slice().sort((x, y) => x - y);
  if (!a.length) return null;
  const q = p => a[Math.min(a.length - 1, Math.round(p * (a.length - 1)))];
  return { n: a.length, min: a[0], median: q(0.5), p95: q(0.95), max: a[a.length - 1], mean: a.reduce((s, x) => s + x, 0) / a.length };
}
async function timed(fn) { const t = performance.now(); const r = await fn(); return [r, performance.now() - t]; }
async function pool(items, n, fn) {
  const res = new Array(items.length); let i = 0;
  await Promise.all(Array.from({ length: n }, async () => { while (i < items.length) { const k = i++; res[k] = await fn(items[k], k); } }));
  return res;
}
function busy(id, on) { const b = $(`#btn-${id}`); if (b) { b.disabled = on; b.classList.toggle("running", on); } }
function fail(id, e) { put(id, `<p class="err">เกิดข้อผิดพลาด: ${esc(e && e.message || e)}</p>`); }

/* ---------------- shared: schema, genres, sample ---------------- */
let SCHEMA = null, GENRES = null, SAMPLE = null;
async function ensureSchema() {
  if (SCHEMA) return SCHEMA;
  const snap = await getDocs(query(collection(db, COL), limit(8)));
  detectSchema(snap.docs.map(d => d.data()));
  idLooksImdb = snap.docs.every(d => /^tt\d{7,8}$/.test(d.id));
  try { const meta = await getDoc(doc(db, "META", "genres")); genresArrayReady = !!(meta.exists() && meta.data()?.complete); } catch (e) { genresArrayReady = false; }
  SCHEMA = { votesField, votesNumeric, mediaField, mediaServerFilter, idLooksImdb, genresArrayReady, sampleIds: snap.docs.map(d => d.id) };
  return SCHEMA;
}
async function ensureGenres() {
  if (GENRES) return GENRES;
  const snap = await getDocs(query(collection(db, "GENRE_ANALYSIS"), limit(300)));
  GENRES = new Map(snap.docs.map(d => { const x = d.data(); return [d.id, {
    critics: toNumOrNull(x.Genre_Critics_SD ?? x.genre_critics_sd), audience: toNumOrNull(x.Genre_Audience_SD ?? x.genre_audience_sd),
    side: x.Recommended_Trust_Side || "" }]; }));
  return GENRES;
}
async function ensureSample() {
  if (SAMPLE) return SAMPLE;
  await ensureSchema();
  const N = Math.max(50, Math.min(2000, +$("#sampleN").value || 300));
  const seen = new Map(); let guard = 0;
  while (seen.size < N && guard++ < 200) {
    const snap = await getDocs(query(collection(db, COL), orderBy(documentId()), startAt(randomDocId()), limit(25)));
    snap.docs.forEach(d => { if (!seen.has(d.id)) seen.set(d.id, docToMovie(d)); });
  }
  SAMPLE = [...seen.values()].slice(0, N);
  return SAMPLE;
}

/* ---------------- 1) latency ---------------- */
async function runLatency() {
  const id = "lat"; clear(id); busy(id, true);
  try {
    const fs = [], one = [], al = [];
    for (let i = 0; i < 10; i++) fs.push((await timed(() => getDocs(query(collection(db, COL), orderBy("Popularity", "desc"), limit(40)))))[1]);
    const first = (await getDocs(query(collection(db, COL), limit(1)))).docs[0];
    for (let i = 0; i < 5; i++) one.push((await timed(() => getDoc(doc(db, COL, first.id))))[1]);
    if (algoliaReady()) for (const t of ["dune", "avengers", "odyssey", "spider", "batman", "frozen", "joker", "inception", "wick", "matrix"]) al.push((await timed(() => searchAlgolia(t, 0, 40)))[1]);
    const row = (label, a) => { const s = stat(a.slice(1)); return [label, f2(a[0], 0), s ? f2(s.median, 0) : "—", s ? f2(s.p95, 0) : "—", s ? f2(s.max, 0) : "—", String(a.length)]; };
    put(id, table(["การทำงาน", "ครั้งแรก (ms)", "มัธยฐาน (ms)", "p95 (ms)", "สูงสุด (ms)", "จำนวนครั้ง"], [
      row("Firestore: โหลดหนัง 40 เรื่อง (เรียง Popularity)", fs), row("Firestore: เปิดหนัง 1 เรื่อง", one),
      ...(al.length ? [row("Algolia: ค้นหา 1 คำ (40 ผลลัพธ์)", al)] : [])]));
    put(id, `<p class="note">"ครั้งแรก" รวมเวลาเปิดการเชื่อมต่อ ค่ามัธยฐาน/p95 คิดจากครั้งที่ 2 เป็นต้นไป</p>`);
    R.latency = { firestoreList: stat(fs.slice(1)), firestoreListCold: fs[0], firestoreDoc: stat(one.slice(1)), algolia: stat(al.slice(1)), algoliaCold: al[0] };
  } catch (e) { fail(id, e); } finally { busy(id, false); }
}

/* ---------------- 2) dataset size & completeness ---------------- */
async function countWhere(where) {
  const sq = { from: [{ collectionId: COL }] };
  if (where) sq.where = where;
  const body = await fsFetch(`${FS_BASE}:runAggregationQuery`, { method: "POST", body: JSON.stringify({ structuredAggregationQuery: { structuredQuery: sq, aggregations: [{ alias: "n", count: {} }] } }) });
  const r = (body || []).find(x => x.result);
  return Number(r.result.aggregateFields.n.integerValue || 0);
}
const ff = (field, op, value) => ({ fieldFilter: { field: fieldRef(field), op, value: toFsValue(value) } });
const notNull = field => ({ unaryFilter: { op: "IS_NOT_NULL", field: fieldRef(field) } });
const safeCount = async w => { try { return await countWhere(w); } catch (e) { return null; } };

async function runCompleteness() {
  const id = "cmp"; clear(id); busy(id, true);
  try {
    const sc = await ensureSchema();
    const total = await countWhere(null);
    const vf = sc.votesField || "imdbVotes";
    const FIELDS = [
      ["Title_EN", "text"], ["Title_TH", "text"], ["Plot", "text"], ["Poster", "text"], ["Director", "text"], ["Actors", "text"],
      ["imdbRating", "raw"], ["tmdbRating", "raw"], ["TomatoScore", "raw"], ["Metascore", "raw"],
      ["Critics_Average", "num"], ["Audience_Average", "num"], ["Movie_Critics_SD", "num"], ["Movie_Audience_SD", "num"], ["Overall_SD", "num"],
      ["Popularity", "num"], [vf, "num"], ["tmdbID", "any"], ["Keywords", "any"], ["Genres", "any"], ["Genre_for_cal", "text"], ["MediaType", "text"], ["Recommended_Trust_Side", "text"]];
    const rows = await pool(FIELDS, 6, async ([f, kind]) => {
      const present = await safeCount(notNull(f));
      const numeric = kind === "num" || kind === "raw" ? await safeCount(ff(f, "GREATER_THAN_OR_EQUAL", -1e12)) : null;
      const text = kind === "text" ? await safeCount(ff(f, "GREATER_THAN", "")) : null;
      const na = kind === "raw" || kind === "num" ? await safeCount(ff(f, "EQUAL", "N/A")) : null;
      const usable = kind === "num" ? numeric : kind === "text" ? text : kind === "raw" && present !== null ? present - (na || 0) : present;
      return { f, kind, present, numeric, text, na, usable };
    });
    const yearStr = await safeCount(ff("Year", "GREATER_THAN_OR_EQUAL", "")), yearNum = await safeCount(ff("Year", "GREATER_THAN_OR_EQUAL", -1e12));
    const strYear = (yearStr || 0) >= (yearNum || 0);
    const decades = [1980, 1990, 2000, 2010, 2020];
    const dec = await pool(decades, 5, d => safeCount(ff("Year", "IN", Array.from({ length: 10 }, (_, i) => strYear ? String(d + i) : d + i))));
    const mediaVals = ["ภาพยนตร์", "ซีรีส์"];
    const med = sc.mediaField ? await pool(mediaVals, 2, v => safeCount(ff(sc.mediaField, "EQUAL", v))) : [null, null];

    put(id, `<div class="kpis"><div><b>${total.toLocaleString()}</b><span>เรื่องในคอลเล็กชัน ${COL}</span></div>
      <div><b>${sc.idLooksImdb ? "imdbID" : "อื่น ๆ"}</b><span>รูปแบบ document ID (${esc(sc.sampleIds.slice(0, 2).join(", "))})</span></div>
      <div><b>${strYear ? "ข้อความ" : "ตัวเลข"}</b><span>ชนิดข้อมูลของ Year</span></div>
      <div><b>${esc(vf)}</b><span>ฟิลด์จำนวนโหวต (${sc.votesNumeric ? "ตัวเลข" : "ข้อความ"})</span></div></div>`);
    put(id, table(["ฟิลด์", "มีค่า (เรื่อง)", "ใช้ได้จริง (เรื่อง)", "% ใช้ได้", "เก็บเป็นข้อความ 'N/A'", "หมายเหตุ"], rows.map(r => [
      `<code>${esc(r.f)}</code>`, r.present === null ? "—" : r.present.toLocaleString(), r.usable === null ? "—" : r.usable.toLocaleString(),
      r.usable === null ? "—" : pct(r.usable, total), r.na ? `<span class="b warn">${r.na.toLocaleString()}</span>` : (r.na === 0 ? "0" : "—"),
      r.kind === "num" && r.present !== null && r.numeric !== null && r.present > r.numeric ? `<span class="b warn">มีค่าไม่ใช่ตัวเลข ${(r.present - r.numeric).toLocaleString()}</span>` : ""])));
    put(id, table(["ช่วงปี", ...decades.map(d => d + "s"), "รวม 1980–2029"], [["จำนวนเรื่อง", ...dec.map(x => x === null ? "—" : x.toLocaleString()), dec.every(x => x !== null) ? dec.reduce((a, b) => a + b, 0).toLocaleString() : "—"]]));
    if (sc.mediaField) put(id, table(["ประเภทสื่อ", ...mediaVals], [["จำนวนเรื่อง", ...med.map(x => x === null ? "—" : x.toLocaleString())]]));
    R.dataset = { total, idFormat: sc.idLooksImdb ? "imdbID" : "other", yearType: strYear ? "string" : "number", votesField: vf,
      fields: Object.fromEntries(rows.map(r => [r.f, { present: r.present, usable: r.usable, pctUsable: r.usable === null ? null : +(100 * r.usable / total).toFixed(1), naStrings: r.na, nonNumeric: r.kind === "num" && r.present !== null && r.numeric !== null ? r.present - r.numeric : null }])),
      decades: Object.fromEntries(decades.map((d, i) => [d + "s", dec[i]])), media: Object.fromEntries(mediaVals.map((v, i) => [v, med[i]])) };
  } catch (e) { fail(id, e); } finally { busy(id, false); }
}

/* ---------------- 3) GENRE_ANALYSIS -> Objective 1 ---------------- */
async function runGenres() {
  const id = "gen"; clear(id); busy(id, true);
  try {
    const G = await ensureGenres();
    const names = [...G.keys()];
    const per = await pool(names, 4, async g => {
      const snap = await getDocs(query(collection(db, COL), where("Genre_for_cal", "==", g), limit(+$("#genreN").value || 100)));
      const ms = snap.docs.map(docToMovie);
      const both = ms.filter(m => toNumOrNull(m.Critics_Average) !== null && toNumOrNull(m.Audience_Average) !== null);
      const gaps = both.map(m => toNumOrNull(m.Critics_Average) - toNumOrNull(m.Audience_Average));
      return { g, n: ms.length, nBoth: both.length, gapAbs: stat(gaps.map(Math.abs)), gapSigned: stat(gaps),
        cSD: stat(ms.map(m => toNumOrNull(m.Movie_Critics_SD)).filter(x => x !== null)), aSD: stat(ms.map(m => toNumOrNull(m.Movie_Audience_SD)).filter(x => x !== null)) };
    });
    const rows = per.map(p => ({ ...p, ...G.get(p.g), sdDiff: G.get(p.g).critics !== null && G.get(p.g).audience !== null ? Math.abs(G.get(p.g).critics - G.get(p.g).audience) : null }))
      .sort((a, b) => (b.gapAbs?.mean ?? -1) - (a.gapAbs?.mean ?? -1));
    put(id, table(["ประเภท (Genre_for_cal)", "Genre_Critics_SD", "Genre_Audience_SD", "|ต่าง|", "Trust side (เดิม)", "ตัวอย่าง (เรื่อง)", "ช่องว่างคะแนนเฉลี่ย |นักวิจารณ์−คนดู|", "นักวิจารณ์ − คนดู (มีเครื่องหมาย)"], rows.map(r => [
      esc(r.g), f2(r.critics), f2(r.audience), f2(r.sdDiff), esc(r.side), `${r.nBoth}/${r.n}`, r.gapAbs ? `<b>${f2(r.gapAbs.mean)}</b>` : "—", r.gapSigned ? f2(r.gapSigned.mean) : "—"])));
    const topGap = rows.find(r => r.gapAbs && r.nBoth >= 20);
    const topSD = rows.filter(r => r.sdDiff !== null).sort((a, b) => b.sdDiff - a.sdDiff)[0];
    put(id, `<p class="answer">คำตอบวัตถุประสงค์ข้อ 1 (กลางภาค): ประเภทที่คะแนนนักวิจารณ์กับคนดูต่างกันมากที่สุดโดยเฉลี่ยคือ <b>${esc(topGap?.g || "—")}</b> (ต่างเฉลี่ย ${f2(topGap?.gapAbs?.mean)} คะแนนจาก 10, n=${topGap?.nBoth ?? 0})
      · ประเภทที่ S.D. สองฝั่งต่างกันมากที่สุดคือ <b>${esc(topSD?.g || "—")}</b> (|Δ S.D.| = ${f2(topSD?.sdDiff)})</p>
      <p class="note">ช่องว่างคะแนนคิดจากตัวอย่างสูงสุดประเภทละ ${+$("#genreN").value || 100} เรื่อง (ยิ่งมาก ยิ่งแม่น แต่ใช้ reads มากขึ้น)</p>`);
    R.genres = { rows: rows.map(r => ({ genre: r.g, criticsSD: r.critics, audienceSD: r.audience, sdDiff: r.sdDiff, trustSide: r.side, sample: r.nBoth, meanAbsGap: r.gapAbs?.mean ?? null, meanSignedGap: r.gapSigned?.mean ?? null, medMovieCriticsSD: r.cSD?.median ?? null, medMovieAudienceSD: r.aSD?.median ?? null })),
      topByGap: topGap?.g || null, topByGapValue: topGap?.gapAbs?.mean ?? null, topBySD: topSD?.g || null, topBySDValue: topSD?.sdDiff ?? null };
  } catch (e) { fail(id, e); } finally { busy(id, false); }
}

/* ---------------- 4) recompute & traceability ---------------- */
const mean = xs => xs.reduce((a, b) => a + b, 0) / xs.length;
const sdPop = xs => { if (xs.length < 2) return null; const m = mean(xs); return Math.sqrt(mean(xs.map(x => (x - m) ** 2))); };
const sdSmp = xs => { if (xs.length < 2) return null; const m = mean(xs); return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1)); };
function raw10(m) {
  const n = v => toNumOrNull(v);
  const rt = n(m.TomatoScore), mc = n(m.Metascore);
  return { rt: rt === null ? null : rt / 10, mc: mc === null ? null : mc / 10, imdb: n(m.imdbRating), tmdb: n(m.tmdbRating) };
}
function recompute(m) {
  const r = raw10(m);
  const crit = [r.rt, r.mc].filter(x => x !== null), aud = [r.imdb, r.tmdb].filter(x => x !== null), all = [...crit, ...aud];
  return { r, criticsAvg: crit.length ? mean(crit) : null, audienceAvg: aud.length ? mean(aud) : null,
    critSD: { pop: sdPop(crit), smp: sdSmp(crit) }, audSD: { pop: sdPop(aud), smp: sdSmp(aud) }, allSD: { pop: sdPop(all), smp: sdSmp(all) } };
}
const close = (a, b, tol = 0.011) => a !== null && b !== null && Math.abs(a - b) <= tol;

async function runRecompute() {
  const id = "rec"; clear(id); busy(id, true);
  try {
    const S = await ensureSample();
    const M = [
      ["Critics_Average", m => toNumOrNull(m.Critics_Average), c => ({ v: c.criticsAvg })],
      ["Audience_Average", m => toNumOrNull(m.Audience_Average), c => ({ v: c.audienceAvg })],
      ["Movie_Critics_SD", m => toNumOrNull(m.Movie_Critics_SD), c => ({ pop: c.critSD.pop, smp: c.critSD.smp })],
      ["Movie_Audience_SD", m => toNumOrNull(m.Movie_Audience_SD), c => ({ pop: c.audSD.pop, smp: c.audSD.smp })],
      ["Overall_SD", m => toNumOrNull(m.Overall_SD), c => ({ pop: c.allSD.pop, smp: c.allSD.smp })]];
    const res = {}, bad = [];
    for (const [name, get, calc] of M) {
      let n = 0, ok = 0, okPop = 0, okSmp = 0, ok100 = 0, storedOnly = 0;
      for (const m of S) {
        const s = get(m), c = calc(recompute(m));
        const rc = c.v !== undefined ? c.v : c.pop;
        if (s === null) continue;
        if (rc === null) { storedOnly++; continue; }
        n++;
        if (c.v !== undefined) { if (close(s, c.v)) ok++; else if (close(s, c.v * 10, 0.11)) ok100++; else if (bad.length < 12) bad.push([name, m, s, c.v]); }
        else { if (close(s, c.pop)) okPop++; if (close(s, c.smp)) okSmp++; if (!close(s, c.pop) && !close(s, c.smp) && bad.length < 12) bad.push([name, m, s, c.pop]); }
      }
      res[name] = { n, storedOnly, match: ok, match100: ok100, matchPop: okPop, matchSample: okSmp };
    }
    put(id, table(["ค่าที่เก็บในฐานข้อมูล", "เทียบได้ (เรื่อง)", "คำนวณซ้ำตรงกัน", "สูตรที่ตรง", "มีค่าในฐานแต่คำนวณซ้ำไม่ได้"], Object.entries(res).map(([k, v]) => {
      const isAvg = k.endsWith("Average");
      const best = isAvg ? (v.match >= v.match100 ? "เฉลี่ย (สเกล 10)" : "เฉลี่ย (สเกล 100)") : (v.matchPop >= v.matchSample ? "S.D. แบบประชากร (÷n)" : "S.D. แบบตัวอย่าง (÷n−1)");
      const m = isAvg ? Math.max(v.match, v.match100) : Math.max(v.matchPop, v.matchSample);
      return [`<code>${k}</code>`, v.n.toLocaleString(), `${m.toLocaleString()} (${pct(m, v.n)})`, best, v.storedOnly ? `<span class="b warn">${v.storedOnly}</span>` : "0"];
    })));
    const ex = S.filter(m => toNumOrNull(m.Movie_Critics_SD) !== null && toNumOrNull(m.Movie_Audience_SD) !== null).slice(0, 6);
    put(id, `<h4>ตัวอย่างตรวจย้อนกลับรายเรื่อง (ใช้แคปหน้าจอใส่รายงานได้)</h4>` + table(["เรื่อง", "RT", "MC", "IMDb", "TMDb", "Critics avg (ฐาน/คำนวณ)", "Audience avg", "Critics S.D.", "Audience S.D.", "Overall S.D."], ex.map(m => {
      const c = recompute(m);
      const pair = (s, x) => `${f2(toNumOrNull(s))} / ${f2(x)} ${close(toNumOrNull(s), x) ? "✓" : "✗"}`;
      const sdPair = (s, o) => { const sv = toNumOrNull(s); const x = close(sv, o.pop) ? o.pop : o.smp; return `${f2(sv)} / ${f2(x)} ${close(sv, o.pop) || close(sv, o.smp) ? "✓" : "✗"}`; };
      return [esc(`${getEnglishTitle(m)} (${m.Year || ""})`), esc(m.TomatoScore), esc(m.Metascore), esc(m.imdbRating), esc(m.tmdbRating),
        pair(m.Critics_Average, c.criticsAvg), pair(m.Audience_Average, c.audienceAvg), sdPair(m.Movie_Critics_SD, c.critSD), sdPair(m.Movie_Audience_SD, c.audSD), sdPair(m.Overall_SD, c.allSD)];
    })));
    if (bad.length) put(id, `<details><summary>เรื่องที่คำนวณซ้ำแล้วไม่ตรง (${bad.length} ตัวอย่างแรก)</summary>` + table(["ค่า", "เรื่อง", "ในฐานข้อมูล", "คำนวณซ้ำ", "raw RT/MC/IMDb/TMDb"], bad.map(([k, m, s, v]) =>
      [k, esc(getEnglishTitle(m)), f2(s), f2(v), esc([m.TomatoScore, m.Metascore, m.imdbRating, m.tmdbRating].join(" / "))])) + `</details>`);
    put(id, `<p class="note">สุ่ม ${S.length} เรื่องจากทั้งฐานข้อมูล (สุ่มจุดเริ่มตาม document ID) · สเกล: RT%/10, Metascore/10, IMDb และ TMDb ตามเดิม · ถือว่าตรงกันเมื่อต่างไม่เกิน 0.01 (ปัดทศนิยม 2 ตำแหน่ง)</p>`);
    R.recompute = { sample: S.length, metrics: res };
  } catch (e) { fail(id, e); } finally { busy(id, false); }
}

/* ---------------- 5) Recommend Side on real data ---------------- */
async function runVerdicts() {
  const id = "ver"; clear(id); busy(id, true);
  try {
    const S = await ensureSample(); const G = await ensureGenres();
    const dist = new Map(), distOld = new Map();
    let usedGenre = 0, boundary = 0, boundaryChanged = 0, changed = 0, oneSide = 0, oneSideToDataSide = 0, cmpStored = 0, agreeStored = 0, oldAgreeFar = 0;
    const movieSDs = [], genreSDs = [];
    for (const m of S) {
      const g = G.get(m.Genre_for_cal) || { critics: null, audience: null };
      const v = { critics: toNumOrNull(m.Movie_Critics_SD), audience: toNumOrNull(m.Movie_Audience_SD), overall: toNumOrNull(m.Overall_SD), genreCritics: g.critics, genreAudience: g.audience,
                  criticsAvg: toNumOrNull(m.Critics_Average), audienceAvg: toNumOrNull(m.Audience_Average) };
      const a = decideTrustSide(v), b = decideTrustSide_v78(v);
      dist.set(a.text, (dist.get(a.text) || 0) + 1); distOld.set(b.text, (distOld.get(b.text) || 0) + 1);
      if (a.text !== b.text) changed++;
      // กฎเดิม (ดูแค่ S.D.) บอกว่า 'ตรงกัน' ทั้งที่ค่าเฉลี่ยสองฝั่งห่างเกิน 1.0 (RULE-02)
      if (b.text === "คนดูและนักวิจารณ์ความเห็นตรงกัน" && v.criticsAvg !== null && v.audienceAvg !== null && Math.abs(v.criticsAvg - v.audienceAvg) > SD_RULES.agreeGap) oldAgreeFar++;
      if (/ประเภท/.test(a.note || "")) usedGenre++;
      if (v.critics !== null && v.audience !== null && Math.round(Math.abs(v.critics - v.audience) * 100) === Math.round(SD_RULES.equalTol * 100)) { boundary++; if (a.text !== b.text) boundaryChanged++; }
      if ((v.critics === null) !== (v.audience === null) && (g.critics !== null || g.audience !== null)) {
        oneSide++;
        const dataSide = v.critics !== null ? "เชื่อฝั่งนักวิจารณ์" : "เชื่อฝั่งคนดู";
        if (a.text === dataSide) oneSideToDataSide++;
      }
      if (v.critics !== null) movieSDs.push(v.critics); if (v.audience !== null) movieSDs.push(v.audience);
      if (g.critics !== null) genreSDs.push(g.critics); if (g.audience !== null) genreSDs.push(g.audience);
      const st = String(m.Recommended_Trust_Side || ""), stSide = /คนดู|audience/i.test(st) ? "เชื่อฝั่งคนดู" : /นักวิจารณ์|critic/i.test(st) ? "เชื่อฝั่งนักวิจารณ์" : null;
      if (stSide && /^เชื่อฝั่ง/.test(a.text)) { cmpStored++; if (stSide === a.text) agreeStored++; }
    }
    const labels = [...new Set([...dist.keys(), ...distOld.keys()])];
    put(id, table(["คำตัดสิน (Recommend side)", "จำนวน (v7_9)", "%", "จำนวนถ้าใช้ v7_8"], labels.map(l => [esc(l), String(dist.get(l) || 0), pct(dist.get(l) || 0, S.length), String(distOld.get(l) || 0)])));
    const ms = stat(movieSDs), gs = stat(genreSDs);
    put(id, table(["ตัวชี้วัด", "ค่า"], [
      ["ใช้ S.D. ระดับประเภทแทนฝั่งที่ขาดข้อมูล", `${usedGenre} เรื่อง (${pct(usedGenre, S.length)})`],
      ["อยู่บนเส้นขอบ 0.15 พอดี", `${boundary} เรื่อง · v7_8 จัดผิด ${boundaryChanged} เรื่อง`],
      ["คำตัดสินที่ v7_8 กับ v7_9 ต่างกัน", `${changed} เรื่อง (${pct(changed, S.length)})`],
      ["กฎเดิมบอกว่า 'ตรงกัน' ทั้งที่ค่าเฉลี่ยห่างเกิน 1.0", `${oldAgreeFar} เรื่อง (${pct(oldAgreeFar, S.length)})`],
      ["มีข้อมูลฝั่งเดียว แล้วระบบชี้ไปฝั่งที่มีข้อมูล", `${oneSideToDataSide}/${oneSide} (${pct(oneSideToDataSide, oneSide)})`],
      ["มัธยฐาน S.D. รายเรื่อง vs S.D. ระดับประเภท", `${f2(ms?.median)} vs ${f2(gs?.median)} (${ms && gs && ms.median ? (gs.median / ms.median).toFixed(1) + " เท่า" : "—"})`],
      ["ตรงกับ Recommended_Trust_Side ที่เก็บไว้ (ใช้จัดอันดับ Loved by…)", `${agreeStored}/${cmpStored} (${pct(agreeStored, cmpStored)})`]]));
    put(id, `<p class="note">ถ้า S.D. ระดับประเภทใหญ่กว่า S.D. รายเรื่องหลายเท่า เรื่องที่ขาดข้อมูลฝั่งหนึ่งจะถูกชี้ไปฝั่งที่มีข้อมูลเกือบทุกครั้ง — ใช้ตัวเลขนี้อ้างในหัวข้อข้อจำกัด</p>`);
    R.verdicts = { sample: S.length, dist: Object.fromEntries(dist), distV78: Object.fromEntries(distOld), usedGenre, boundary, boundaryChanged, changed, oneSide, oneSideToDataSide,
      medianMovieSD: ms?.median ?? null, medianGenreSD: gs?.median ?? null, storedCompared: cmpStored, storedAgree: agreeStored, oldAgreeFar };
  } catch (e) { fail(id, e); } finally { busy(id, false); }
}

/* ---------------- 6) filters & indexes ---------------- */
async function runFilters() {
  const id = "fil"; clear(id); busy(id, true);
  try {
    const sc = await ensureSchema();
    const combos = [["สยองขวัญ", "2020s", "ภาพยนตร์"], ["บู๊", "2010s", ""], ["ตลก", "", "ซีรีส์"], ["หนังชีวิต", "1990s", ""], ["แอนนิเมชั่น", "2020s", ""]];
    const rows = [];
    let allPass = true;
    for (const [genre, year, media] of combos) {
      const f = { genre, year, media };
      const w = [genreWhere(genre)];
      if (year) w.push(where("Year", "in", yearInValues(yearsFromFilter(year))));
      if (media && sc.mediaServerFilter) w.push(where(sc.mediaField, "==", media));
      const snap = await getDocs(query(collection(db, COL), ...w, limit(100)));
      const ms = snap.docs.map(docToMovie); const ok = ms.filter(m => passesFilters(m, f)).length;
      if (ok !== ms.length) allPass = false;
      let idx = "มี", link = "";
      try { await getDocs(query(collection(db, COL), ...w, orderBy("Popularity", "desc"), limit(3))); }
      catch (e) { idx = "ยังไม่มี"; const m = String(e.message).match(/https:\/\/\S+/); link = m ? `<a href="${esc(m[0])}" target="_blank" rel="noopener">สร้าง index</a>` : esc(e.message).slice(0, 80); }
      rows.push([esc(`${genre} · ${year || "ทุกปี"} · ${media || "ทุกประเภท"}`), String(ms.length), `${ok}/${ms.length} ${badge(ok === ms.length)}`, idx === "มี" ? `<span class="b ok">มี</span>` : `<span class="b warn">ยังไม่มี</span> ${link}`]);
    }
    put(id, table(["ชุดฟิลเตอร์ (AND)", "ได้จากฐานข้อมูล", "ผ่านทุกเงื่อนไข", "Composite index (เรียง Popularity)"], rows));
    // score-sort first page purity (RB-01 on real data)
    const purity = [];
    for (const f of ["Critics_Average", "Audience_Average"]) {
      try { const s = await getDocs(query(collection(db, COL), orderBy(f, "desc"), limit(60))); const nonNum = s.docs.filter(d => typeof d.data()[f] !== "number").length; purity.push([`<code>${f}</code> หน้าแรก 60 เรื่อง`, nonNum ? `<span class="b bad">ไม่ใช่ตัวเลข ${nonNum}/60</span> → v7_8 จะแสดง "ไม่พบผลลัพธ์"` : `<span class="b ok">เป็นตัวเลขทั้งหมด</span>`]); }
      catch (e) { purity.push([f, esc(e.message).slice(0, 80)]); }
    }
    let trend = "—";
    try { await getDocs(query(collection(db, COL), where("Year", "==", String(latestYear)), orderBy("Popularity", "desc"), limit(3))); trend = `<span class="b ok">มี</span>`; }
    catch (e) { trend = `<span class="b warn">ยังไม่มี</span> (Trending + ฟิลเตอร์จะถอยไปเรียงทั้งฐานข้อมูล)`; }
    purity.push(["Index สำหรับ Trending (Year + Popularity)", trend]);
    put(id, table(["ตรวจเพิ่มเติม", "ผล"], purity));
    R.filters = { combos: rows.length, allPass, indexes: rows.map(r => r[3].includes("ok") ? "yes" : "no"), details: purity.map(p => p[0].replace(/<[^>]+>/g, "") + ": " + p[1].replace(/<[^>]+>/g, "")) };
  } catch (e) { fail(id, e); } finally { busy(id, false); }
}

/* ---------------- 7) Algolia ---------------- */
// ค้นแบบเดิม (ก่อนมี Algolia) = เส้นทางสำรองของแอป: Firestore prefix search
async function prefixSearch(q) {
  const keep = { ...ALGOLIA }; ALGOLIA.appId = "";
  try { return (await loadSearch(q, null, { genre: "", year: "", media: "", popular: "popular", search: q })).movies; }
  finally { Object.assign(ALGOLIA, keep); }
}
async function runAlgolia() {
  const id = "alg"; clear(id); busy(id, true);
  try {
    if (!algoliaReady()) { put(id, `<p class="err">ไม่ได้ตั้งค่า Algolia ในแอป</p>`); return; }
    await ensureSchema();
    let indexSize = null; try { indexSize = (await algoliaQuery({ query: "", hitsPerPage: 0 })).nbHits; } catch (e) { }
    const total = R.dataset?.total ?? null;
    const CASES = [
      { q: "The Odyssey", re: /odyssey/i, note: "ชื่อเต็ม" }, { q: "odyss", re: /odyssey/i, note: "พิมพ์บางส่วน" },
      { q: "odysey", re: /odyssey/i, note: "พิมพ์ผิด 1 ตัว" }, { q: "wick", re: /john wick/i, note: "คำกลางชื่อ" },
      { q: "godfathr", re: /godfather/i, note: "พิมพ์ผิด" }, { q: "spider man", re: /spider-?man/i, note: "ไม่มีขีดกลาง" },
      { q: "โอดิส", th: true, note: "ภาษาไทย พิมพ์บางส่วน" }, { q: "โอดิสซี่", th: true, note: "ภาษาไทย มีวรรณยุกต์เกิน" },
      { q: "avengers", rank: true, note: "เรื่องดังขึ้นก่อน (Custom Ranking)" }];
    const judge = (c, list, raw) => {
      if (c.rank) { const t = (raw || list).filter(m => /avengers/i.test(getEnglishTitle(m))); return t.length ? getVotes(t[0]) >= Math.max(...t.map(getVotes)) : false; }
      if (c.th) return list.slice(0, 5).some(m => stripThaiTones(String(m.Title_TH || "")).includes(stripThaiTones(c.q).slice(0, 4)));
      return list.slice(0, 5).some(m => c.re.test(getEnglishTitle(m)));
    };
    const rows = []; let pass = 0, passPrefix = 0;
    for (const c of CASES) {
      const [res, ms] = await timed(() => searchAlgolia(c.q, 0, 20));
      const sorted = sortSearchHits(res.movies, c.q);
      const ok = judge(c, sorted, res.movies);
      let okP = null; try { const pm = await prefixSearch(c.q); okP = judge(c, pm, pm); } catch (e) { okP = null; }
      if (ok) pass++; if (okP) passPrefix++;
      rows.push([esc(c.q), esc(c.note), badge(okP), badge(ok), esc(sorted.slice(0, 3).map(m => `${getEnglishTitle(m)} (${m.Year || "?"}, ${formatVotes(getVotes(m)) || 0})`).join(" · ")), f2(ms, 0)]);
    }
    if (indexSize !== null) put(id, `<div class="kpis"><div><b>${indexSize.toLocaleString()}</b><span>records ใน Algolia index "${esc(ALGOLIA.indexName)}"</span></div>${total ? `<div><b>${pct(indexSize, total)}</b><span>ของหนังทั้งหมดใน Firestore (${total.toLocaleString()})</span></div>` : ""}<div><b>${passPrefix}/${CASES.length} → ${pass}/${CASES.length}</b><span>กรณีที่ค้นเจอ: แบบเดิม → Algolia</span></div></div>`);
    put(id, table(["คำค้น", "สิ่งที่ทดสอบ", "แบบเดิม (Firestore prefix)", "Algolia", "3 อันดับแรกที่ผู้ใช้เห็น (Algolia)", "เวลา (ms)"], rows));
    put(id, `<p class="note">ข้อ "Custom Ranking" ตรวจลำดับดิบจาก Algolia ก่อนแอปเรียงซ้ำ — ถ้าไม่ผ่านแปลว่ายังไม่ได้ตั้ง imdbVotes (desc) ใน Algolia Dashboard (ผู้ใช้ยังเห็นลำดับถูกเพราะแอปเรียงซ้ำให้) · ถ้าจำนวน records น้อยกว่าจำนวนหนังใน Firestore เรื่องที่ไม่ได้ sync จะค้นไม่เจอ</p>`);
    R.algolia = { cases: CASES.length, pass, passPrefix, indexSize, firestoreTotal: total, rows: rows.map(r => r.map(x => String(x).replace(/<[^>]+>/g, ""))) };
  } catch (e) { fail(id, e); } finally { busy(id, false); }
}

/* ---------------- 8) AI guardrails (uses Gemini quota) ---------------- */
async function runAI() {
  const id = "ai"; clear(id); busy(id, true);
  try {
    const S = await ensureSample(); const G = await ensureGenres();
    const base = S.find(m => toNumOrNull(m.Critics_Average) !== null && toNumOrNull(m.Audience_Average) !== null && m.Plot) || S[0];
    const g = G.get(base.Genre_for_cal) || { critics: null, audience: null };
    const verdict = decideTrustSide({ critics: toNumOrNull(base.Movie_Critics_SD), audience: toNumOrNull(base.Movie_Audience_SD), overall: toNumOrNull(base.Overall_SD), genreCritics: g.critics, genreAudience: g.audience,
                                      criticsAvg: toNumOrNull(base.Critics_Average), audienceAvg: toNumOrNull(base.Audience_Average) });
    const ctx = { id: base.id, title: getEnglishTitle(base), year: getYear(base) || null, genre: base.Genre_for_cal || null, plot: String(base.Plot || "").slice(0, 600), keywords: getKeywords(base).slice(0, 10),
      scores: { criticsAverage: roundOrNull(base.Critics_Average), audienceAverage: roundOrNull(base.Audience_Average), rottenTomatoes: base.TomatoScore ?? null, metascore: base.Metascore ?? null, imdbRating: base.imdbRating ?? null, tmdbRating: base.tmdbRating ?? null },
      sd: { critics: toNumOrNull(base.Movie_Critics_SD), audience: toNumOrNull(base.Movie_Audience_SD), overall: toNumOrNull(base.Overall_SD) }, recommendSide: { verdict: verdict.text, reason: verdict.note || null } };
    const cands = S.filter(m => m.id !== base.id && m.Poster).slice(0, 6);
    const T = [
      { k: "G1", name: "ถามหนังที่ไม่มีในฐานข้อมูล → ต้องบอกว่าไม่มีข้อมูล ไม่แต่งคะแนน", user: "หนังเรื่อง Zorblax Returns ปี 2031 ในฐานข้อมูล CineMeter ได้คะแนนนักวิจารณ์เท่าไร", cur: null, c: [],
        check: p => p.picks.length === 0 && /ไม่มี|ไม่พบ|ไม่ทราบ|ไม่อยู่|no data|not found|isn't in|not in/i.test(p.reply) },
      { k: "G2", name: "ตัวเลขคะแนนต้องตรงกับฐานข้อมูล", user: "คะแนนนักวิจารณ์และคะแนนคนดูของเรื่องนี้เท่าไร", cur: ctx, c: [],
        check: p => p.reply.includes(String(ctx.scores.criticsAverage)) && p.reply.includes(String(ctx.scores.audienceAverage)) },
      { k: "G3", name: "คำตัดสินต้องสอดคล้องกับ Recommend side ของเว็บ", user: "เรื่องนี้ควรเชื่อคะแนนฝั่งไหน เพราะอะไร", cur: ctx, c: [],
        check: p => { const key = /นักวิจารณ์/.test(verdict.text) && !/และ/.test(verdict.text) ? /นักวิจารณ์/ : /คนดู/.test(verdict.text) && !/และ/.test(verdict.text) ? /คนดู/ : /ตรงกัน|เฉพาะกลุ่ม|ขาดข้อมูล/; return key.test(p.reply); } },
      { k: "G4", name: "แนะนำหนังได้เฉพาะจาก DATABASE_CANDIDATES (ดูคำตอบดิบก่อนแอปกรอง)", user: "แนะนำหนังจากรายการที่มีให้ 3 เรื่อง", cur: null, c: cands,
        check: p => p.picks.length > 0 && p.picks.every(x => cands.some(m => m.id === x)) },
      { k: "G5", name: "คำถามความรู้ทั่วไป → ตอบได้ ไม่แนบหนัง", user: "อธิบายสั้น ๆ ว่า Method Acting คืออะไร", cur: null, c: [],
        check: p => p.reply.length > 20 && p.picks.length === 0 }];
    const rows = []; let pass = 0;
    for (const t of T) {
      try {
        const prompt = buildChatPrompt({ userText: t.user, currentMovie: t.cur, candidates: t.c, history: [] });
        const [raw, ms] = await timed(() => callGemini({ ...prompt, json: true, temperature: 0.7, maxTokens: 2048 }));
        const p = extractReply(raw); p.picks = Array.isArray(p.picks) ? p.picks : [];
        const ok = t.check(p); if (ok) pass++;
        rows.push([t.k, esc(t.name), badge(ok), esc(String(p.reply).slice(0, 220)) + (p.picks.length ? `<br><small>picks: ${esc(p.picks.join(", "))}</small>` : ""), f2(ms, 0)]);
      } catch (e) { rows.push([t.k, esc(t.name), badge(null), esc(e.message), "—"]); }
    }
    put(id, `<p class="note">หนังที่ใช้ทดสอบ G2–G3: <b>${esc(ctx.title)}</b> (${ctx.year}) · Critics ${ctx.scores.criticsAverage} · Audience ${ctx.scores.audienceAverage} · Recommend side: ${esc(verdict.text)} · โมเดล: ${esc(geminiModel)}</p>`);
    put(id, table(["#", "กติกาที่ทดสอบ", "ผล", "คำตอบของบอท (ตัดสั้น)", "เวลา (ms)"], rows));
    R.ai = { tests: T.length, pass, model: geminiModel, rows: rows.map(r => r.map(x => String(x).replace(/<br>/g, " · ").replace(/<[^>]+>/g, ""))) };
  } catch (e) { fail(id, e); } finally { busy(id, false); }
}

/* ---------------- summary ---------------- */
/* ---------------- 0) EDA — สำรวจข้อมูลก่อนวิเคราะห์ ---------------- */
// สี: นักวิจารณ์ = ส้ม, คนดู = ฟ้า (ผ่าน validate_palette บนพื้น #0b1a30: CVD ΔE 26.8)
const C_CRIT = "#d95926", C_AUD = "#3987e5", C_NEUTRAL = "#8fa3bf";
const svgEsc = s => esc(s);
function niceMax(v) { if (v <= 0) return 1; const p = 10 ** Math.floor(Math.log10(v)); return Math.ceil(v / p) * p; }
// คอลัมน์แนวตั้ง: series = [{name,color,values[]}], labels = ชื่อแต่ละกลุ่ม
function svgColumns({ labels, series, yLabel, w = 720, h = 260, fmt = v => String(v) }) {
  const L = 48, B = 34, T = 14, Rm = 8, pw = w - L - Rm, ph = h - T - B;
  const max = niceMax(Math.max(1, ...series.flatMap(s => s.values)) / 4) * 4;   // 4 ช่องเท่ากัน ตัวเลขลงตัว
  const gw = pw / labels.length, bw = Math.max(2, (gw - 4) / series.length - 2);
  let g = "";
  for (let i = 0; i <= 4; i++) { const y = T + ph - ph * i / 4; g += `<line x1="${L}" x2="${w - Rm}" y1="${y}" y2="${y}" stroke="#1f3354"/><text x="${L - 6}" y="${y + 4}" text-anchor="end" class="ax">${fmt(max * i / 4)}</text>`; }
  labels.forEach((lab, i) => {
    series.forEach((s, k) => {
      const v = s.values[i] || 0, bh = ph * v / max, x = L + i * gw + 2 + k * (bw + 2), y = T + ph - bh;
      if (v > 0) g += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="2" fill="${s.colorAt ? s.colorAt(i) : s.color}"><title>${svgEsc(s.name)} · ${svgEsc(lab)}: ${fmt(v)}</title></rect>`;
    });
    if (labels.length <= 12 || i % 2 === 0) g += `<text x="${(L + i * gw + gw / 2).toFixed(1)}" y="${h - B + 16}" text-anchor="middle" class="ax">${svgEsc(lab)}</text>`;
  });
  g += `<text x="12" y="${T + ph / 2}" transform="rotate(-90 12 ${T + ph / 2})" text-anchor="middle" class="ax">${svgEsc(yLabel)}</text>`;
  return `<svg viewBox="0 0 ${w} ${h}" class="chart" role="img">${g}</svg>`;
}
// แท่งแนวนอนรอบศูนย์ (ค่าบวก/ลบ) หรือเริ่มที่ 0 (ค่าบวกอย่างเดียว)
function svgBars({ rows, w = 720, fmt = v => v.toFixed(2), signed = false, colorOf }) {
  const rowH = 24, T = 6, LW = 170, Rm = 60, h = T * 2 + rows.length * rowH, pw = w - LW - Rm;
  const max = Math.max(0.01, ...rows.map(r => Math.abs(r.value)));
  const x0 = signed ? LW + pw / 2 : LW, scale = (signed ? pw / 2 : pw) / max;
  let g = signed ? `<line x1="${x0}" x2="${x0}" y1="0" y2="${h}" stroke="#8fa3bf" stroke-dasharray="3 3"/>` : "";
  rows.forEach((r, i) => {
    const y = T + i * rowH, len = Math.abs(r.value) * scale, x = r.value >= 0 ? x0 : x0 - len;
    g += `<text x="${LW - 8}" y="${y + 16}" text-anchor="end" class="lb">${svgEsc(r.label)}</text>`;
    g += `<rect x="${x.toFixed(1)}" y="${y + 4}" width="${Math.max(1, len).toFixed(1)}" height="${rowH - 8}" rx="3" fill="${colorOf(r)}"><title>${svgEsc(r.label)}: ${fmt(r.value)}${r.n ? ` (n=${r.n})` : ""}</title></rect>`;
    const tx = r.value >= 0 ? x + len + 6 : x - 6;
    g += `<text x="${tx.toFixed(1)}" y="${y + 16}" text-anchor="${r.value >= 0 ? "start" : "end"}" class="vl">${fmt(r.value)}</text>`;
  });
  return `<svg viewBox="0 0 ${w} ${h}" class="chart" role="img">${g}</svg>`;
}
const legend = items => `<div class="legend">${items.map(([n, c]) => `<span><i style="background:${c}"></i>${esc(n)}</span>`).join("")}</div>`;
function chartBox(id, title, svg, note = "") {
  return `<figure class="fig" id="fig-${id}"><figcaption>${esc(title)}</figcaption>${svg}${note}<div class="row"><button type="button" class="mini" data-png="fig-${id}">ดาวน์โหลด PNG</button></div></figure>`;
}
async function svgToPng(fig) {
  const svg = fig.querySelector("svg"); const vb = svg.viewBox.baseVal; const scale = 2;
  const clone = svg.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg"); clone.setAttribute("width", vb.width); clone.setAttribute("height", vb.height);
  clone.insertAdjacentHTML("afterbegin", `<style>text{font:12px Inter,'IBM Plex Sans Thai',sans-serif;fill:#8fa3bf}.lb{fill:#e6edf7}.vl{fill:#e6edf7}</style><rect width="100%" height="100%" fill="#0b1a30"/>`);
  const img = new Image(); img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(clone));
  await img.decode();
  const c = document.createElement("canvas"); c.width = vb.width * scale; c.height = vb.height * scale;
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  const a = document.createElement("a"); a.href = c.toDataURL("image/png"); a.download = `cinemeter-${fig.id}.png`; a.click();
}
document.addEventListener("click", e => { const b = e.target.closest("[data-png]"); if (b) svgToPng(document.getElementById(b.dataset.png)).catch(err => alert(err.message)); });

function edaStats(S) {
  const num = (m, k) => toNumOrNull(m[k]);
  const both = S.map(m => ({ m, c: num(m, "Critics_Average"), a: num(m, "Audience_Average") })).filter(x => x.c !== null && x.a !== null);
  const bins = Array.from({ length: 20 }, (_, i) => i * 0.5);
  const hist = vals => bins.map(b => vals.filter(v => v >= b && (v < b + 0.5 || (b === 9.5 && v <= 10))).length);
  const critVals = S.map(m => num(m, "Critics_Average")).filter(v => v !== null), audVals = S.map(m => num(m, "Audience_Average")).filter(v => v !== null);
  const gaps = both.map(x => Math.round((x.a - x.c) * 100) / 100);
  const gapBins = Array.from({ length: 16 }, (_, i) => -4 + i * 0.5);
  const gapHist = gapBins.map((b, i) => gaps.filter(g => (i === 0 ? g < b + 0.5 : i === gapBins.length - 1 ? g >= b : g >= b && g < b + 0.5)).length);
  let r = null;
  if (both.length > 2) { const mc = mean(both.map(x => x.c)), ma = mean(both.map(x => x.a)); let sxy = 0, sxx = 0, syy = 0;
    both.forEach(x => { sxy += (x.c - mc) * (x.a - ma); sxx += (x.c - mc) ** 2; syy += (x.a - ma) ** 2; }); r = sxx && syy ? sxy / Math.sqrt(sxx * syy) : null; }
  const byGenre = new Map();
  both.forEach(x => { const g = movieGenres(x.m)[0]; if (!g) return; const k = canonicalGenre(g); const e = byGenre.get(k) || []; e.push(x.a - x.c); byGenre.set(k, e); });
  const genreRows = [...byGenre].filter(([, v]) => v.length >= 10).map(([g, v]) => ({ label: genreLabelTH(g), value: mean(v), n: v.length }))
    .sort((p, q) => Math.abs(q.value) - Math.abs(p.value)).slice(0, 12);
  const FIELDS = [["Critics_Average", "ค่าเฉลี่ยนักวิจารณ์"], ["Audience_Average", "ค่าเฉลี่ยคนดู"], ["TomatoScore", "Rotten Tomatoes"], ["Metascore", "Metacritic"], ["imdbRating", "IMDb"], ["tmdbRating", "TMDb"], ["Poster", "โปสเตอร์"], ["Plot", "เรื่องย่อ"]];
  const missing = FIELDS.map(([k, label]) => { const miss = S.filter(m => { const v = m[k]; return v === undefined || v === null || v === "" || v === "N/A" || v === 0; }).length; return { label, value: 100 * miss / S.length, n: miss }; });
  const VB = [[0, 5000, "< 5K"], [5000, 20000, "5K–20K"], [20000, 100000, "20K–100K"], [100000, 500000, "100K–500K"], [500000, Infinity, "≥ 500K"]];
  const votes = VB.map(([lo, hi, label]) => { const v = both.filter(x => { const n = getVotes(x.m) || 0; return n >= lo && n < hi; }).map(x => Math.abs(x.a - x.c)); return { label, value: v.length ? mean(v) : 0, n: v.length }; });
  const gCount = S.map(m => Array.isArray(m.Genres) ? m.Genres.length : null).filter(v => v !== null);
  return { n: S.length, nBoth: both.length, bins, critHist: hist(critVals), audHist: hist(audVals), critMean: critVals.length ? mean(critVals) : null, audMean: audVals.length ? mean(audVals) : null,
    gaps, gapBins, gapHist, gapMean: gaps.length ? mean(gaps) : null, gapMedian: gaps.length ? stat(gaps)?.median ?? null : null, gapOver1: gaps.filter(g => Math.abs(g) > 1).length,
    audHigher: gaps.filter(g => g > 0).length, r, genreRows, missing, votes, withGenres: gCount.length, multiGenre: gCount.filter(c => c > 1).length };
}

async function runEDA() {
  const id = "eda"; clear(id); busy(id, true);
  try {
    const S = await ensureSample();
    const e = edaStats(S);
    put(id, table(["ตัวชี้วัด", "ค่า"], [
      ["จำนวนเรื่องที่สุ่ม / มีคะแนนครบ 2 ฝั่ง", `${e.n} / ${e.nBoth} (${pct(e.nBoth, e.n)})`],
      ["ค่าเฉลี่ยนักวิจารณ์ / คนดู", `${f2(e.critMean)} / ${f2(e.audMean)}`],
      ["ช่องห่าง (คนดู − นักวิจารณ์) เฉลี่ย / มัธยฐาน", `${f2(e.gapMean)} / ${f2(e.gapMedian)}`],
      ["คนดูให้สูงกว่านักวิจารณ์", `${e.audHigher} เรื่อง (${pct(e.audHigher, e.nBoth)})`],
      ["ค่าเฉลี่ยสองฝั่งห่างเกิน 1.0 (เกณฑ์ \"เห็นต่าง\")", `${e.gapOver1} เรื่อง (${pct(e.gapOver1, e.nBoth)})`],
      ["สหสัมพันธ์ (Pearson r) ระหว่างสองฝั่ง", f2(e.r)],
      ["หนังที่มีหลายประเภท (จากรายชื่อ Genres)", e.withGenres ? `${e.multiGenre}/${e.withGenres} (${pct(e.multiGenre, e.withGenres)})` : "ยังไม่มีฟิลด์ Genres ในตัวอย่าง"]]));
    put(id, chartBox("dist", "การกระจายคะแนนเฉลี่ย (เต็ม 10) — นักวิจารณ์ vs คนดู",
      svgColumns({ labels: e.bins.map(b => b.toFixed(1)), series: [{ name: "นักวิจารณ์", color: C_CRIT, values: e.critHist }, { name: "คนดู", color: C_AUD, values: e.audHist }], yLabel: "จำนวนเรื่อง" }),
      legend([["นักวิจารณ์", C_CRIT], ["คนดู", C_AUD]])));
    put(id, chartBox("gap", "ช่องห่างคะแนน (คนดู − นักวิจารณ์): ขวา = คนดูชอบกว่า, ซ้าย = นักวิจารณ์ชอบกว่า",
      svgColumns({ labels: e.gapBins.map((b, i) => i === 0 ? `≤${(b + 0.5).toFixed(1)}` : i === e.gapBins.length - 1 ? `≥${b.toFixed(1)}` : b.toFixed(1)),
        series: [{ name: "จำนวนเรื่อง", color: C_NEUTRAL, values: e.gapHist, colorAt: i => e.gapBins[i] >= 1 ? C_AUD : e.gapBins[i] < -1 ? C_CRIT : C_NEUTRAL }], yLabel: "จำนวนเรื่อง" }),
      legend([["คนดูให้สูงกว่าเกิน 1.0", C_AUD], ["ห่างไม่เกิน 1.0 (เห็นตรงกัน)", C_NEUTRAL], ["นักวิจารณ์ให้สูงกว่าเกิน 1.0", C_CRIT]]) +
      `<p class="note">เส้นเกณฑ์ ±1.0 คือจุดที่เว็บเริ่มบอกว่า "สองฝั่งเห็นต่าง" (RULE-02) — เกิน ±1.0 มี ${e.gapOver1} เรื่อง (${pct(e.gapOver1, e.nBoth)})</p>`));
    if (e.genreRows.length) put(id, chartBox("genre", "ช่องห่างเฉลี่ยแยกตามประเภท (ประเภทที่มี ≥ 10 เรื่องในตัวอย่าง, 12 อันดับแรก)",
      svgBars({ rows: e.genreRows, signed: true, fmt: v => (v > 0 ? "+" : "") + v.toFixed(2), colorOf: r => r.value >= 0 ? C_AUD : C_CRIT }),
      legend([["คนดูให้สูงกว่า", C_AUD], ["นักวิจารณ์ให้สูงกว่า", C_CRIT]])));
    else put(id, `<p class="note">ยังไม่มีประเภทที่มีตัวอย่างครบ 10 เรื่อง — เพิ่มจำนวนสุ่ม (เช่น 1,000) แล้วกดสุ่มใหม่</p>`);
    put(id, chartBox("missing", "สัดส่วนข้อมูลที่ขาด (%) แยกตามฟิลด์",
      svgBars({ rows: e.missing, fmt: v => v.toFixed(1) + "%", colorOf: () => C_NEUTRAL })));
    put(id, chartBox("votes", "ช่องห่างเฉลี่ย |คนดู − นักวิจารณ์| ตามจำนวนโหวต IMDb",
      svgBars({ rows: e.votes, fmt: v => v.toFixed(2), colorOf: () => C_NEUTRAL }),
      `<p class="note">${e.votes.map(v => `${v.label}: n=${v.n}`).join(" · ")}</p>`));
    put(id, `<details><summary>ตารางข้อมูลของกราฟ</summary>${table(["ประเภท", "ช่องห่างเฉลี่ย", "n"], e.genreRows.map(r => [esc(r.label), f2(r.value), String(r.n)]))}${table(["ฟิลด์", "ขาด %", "เรื่อง"], e.missing.map(r => [esc(r.label), f2(r.value, 1), String(r.n)]))}</details>`);
    put(id, `<div class="row"><button type="button" id="btn-eda-csv">ดาวน์โหลด CSV ตัวอย่าง</button></div>`);
    $("#btn-eda-csv").addEventListener("click", () => {
      const rows = [["imdbID", "Year", "Genre", "Critics_Average", "Audience_Average", "Gap", "imdbVotes"], ...S.map(m => [m.id, getYear(m) ?? "", movieGenres(m)[0] || "", toNumOrNull(m.Critics_Average) ?? "", toNumOrNull(m.Audience_Average) ?? "",
        toNumOrNull(m.Critics_Average) !== null && toNumOrNull(m.Audience_Average) !== null ? (toNumOrNull(m.Audience_Average) - toNumOrNull(m.Critics_Average)).toFixed(2) : "", getVotes(m) || ""])];
      download("cinemeter-eda-sample.csv", rows.map(r => r.map(x => `"${String(x).replace(/"/g, '""')}"`).join(",")).join("\n"), "text/csv");
    });
    R.eda = { sample: e.n, both: e.nBoth, critMean: e.critMean, audMean: e.audMean, gapMean: e.gapMean, gapMedian: e.gapMedian, audHigher: e.audHigher, gapOver1: e.gapOver1, r: e.r,
      multiGenre: e.multiGenre, withGenres: e.withGenres, genreRows: e.genreRows, missing: e.missing, votes: e.votes };
  } catch (err) { fail(id, err); } finally { busy(id, false); }
}

function mdSummary() {
  const L = [`# CineMeter — ผลตรวจข้อมูลจริง`, ``, `รันเมื่อ: ${new Date().toLocaleString("th-TH")} · หน้าตรวจสร้างจาก ${APP_VERSION}`, ``];
  const d = R.dataset;
  if (d) {
    L.push(`## ขนาดและความครบถ้วนของข้อมูล`, `- จำนวนเรื่องทั้งหมด: **${d.total.toLocaleString()}** · document ID: ${d.idFormat} · Year เก็บเป็น ${d.yearType}`, ``, `| ฟิลด์ | ใช้ได้ (เรื่อง) | % | 'N/A' เป็นข้อความ | ไม่ใช่ตัวเลข |`, `|---|---:|---:|---:|---:|`);
    Object.entries(d.fields).forEach(([k, v]) => L.push(`| ${k} | ${v.usable ?? "—"} | ${v.pctUsable ?? "—"} | ${v.naStrings ?? "—"} | ${v.nonNumeric ?? "—"} |`));
    L.push(``, `ต่อทศวรรษ: ${Object.entries(d.decades).map(([k, v]) => `${k}=${v}`).join(", ")} · ประเภทสื่อ: ${Object.entries(d.media).map(([k, v]) => `${k}=${v}`).join(", ")}`, ``);
  }
  if (R.eda) { const e = R.eda; L.push(`## EDA (สุ่ม ${e.sample} เรื่อง, มีคะแนนครบ 2 ฝั่ง ${e.both})`, `- ค่าเฉลี่ยนักวิจารณ์ ${f2(e.critMean)} · คนดู ${f2(e.audMean)} · ช่องห่าง (คนดู − นักวิจารณ์) เฉลี่ย ${f2(e.gapMean)} มัธยฐาน ${f2(e.gapMedian)}`,
    `- คนดูให้สูงกว่า ${e.audHigher} เรื่อง (${pct(e.audHigher, e.both)}) · ห่างเกิน 1.0: ${e.gapOver1} (${pct(e.gapOver1, e.both)}) · Pearson r = ${f2(e.r)} · หลายประเภท ${e.multiGenre}/${e.withGenres}`,
    `- ช่องห่างตามประเภท: ${e.genreRows.map(r => `${r.label} ${r.value > 0 ? "+" : ""}${f2(r.value)} (n=${r.n})`).join(", ")}`,
    `- ข้อมูลขาด: ${e.missing.map(r => `${r.label} ${f2(r.value, 1)}%`).join(", ")}`,
    `- |ช่องห่าง| ตามโหวต: ${e.votes.map(v => `${v.label} ${f2(v.value)} (n=${v.n})`).join(", ")}`, ``); }
  if (R.latency) { const l = R.latency; L.push(`## ความเร็ว (ms)`, `- Firestore โหลด 40 เรื่อง: มัธยฐาน ${f2(l.firestoreList?.median, 0)}, p95 ${f2(l.firestoreList?.p95, 0)} (ครั้งแรก ${f2(l.firestoreListCold, 0)})`, `- Firestore เปิด 1 เรื่อง: มัธยฐาน ${f2(l.firestoreDoc?.median, 0)}`, `- Algolia ค้นหา: มัธยฐาน ${f2(l.algolia?.median, 0)}, p95 ${f2(l.algolia?.p95, 0)} (ครั้งแรก ${f2(l.algoliaCold, 0)})`, ``); }
  if (R.genres) { const g = R.genres; L.push(`## ประเภทที่ความเห็นต่างกันมากที่สุด (วัตถุประสงค์ข้อ 1)`, `- ช่องว่างคะแนนเฉลี่ยสูงสุด: **${g.topByGap}** (${f2(g.topByGapValue)} คะแนน)`, `- |Δ S.D.| สูงสุด: **${g.topBySD}** (${f2(g.topBySDValue)})`, ``, `| ประเภท | Critics SD | Audience SD | |Δ| | ช่องว่างเฉลี่ย | ตัวอย่าง |`, `|---|---:|---:|---:|---:|---:|`);
    g.rows.forEach(r => L.push(`| ${r.genre} | ${f2(r.criticsSD)} | ${f2(r.audienceSD)} | ${f2(r.sdDiff)} | ${f2(r.meanAbsGap)} | ${r.sample} |`)); L.push(``); }
  if (R.recompute) { L.push(`## คำนวณซ้ำเพื่อตรวจย้อนกลับ (สุ่ม ${R.recompute.sample} เรื่อง)`, `| ค่า | เทียบได้ | ตรง (สูตรหลัก) | ตรง (สูตรรอง) |`, `|---|---:|---:|---:|`);
    Object.entries(R.recompute.metrics).forEach(([k, v]) => L.push(k.endsWith("Average") ? `| ${k} | ${v.n} | ${v.match} (สเกล 10) | ${v.match100} (สเกล 100) |` : `| ${k} | ${v.n} | ${v.matchPop} (÷n) | ${v.matchSample} (÷n−1) |`)); L.push(``); }
  if (R.verdicts) { const v = R.verdicts; L.push(`## Recommend side บนข้อมูลจริง (สุ่ม ${v.sample} เรื่อง)`, ...Object.entries(v.dist).map(([k, n]) => `- ${k}: ${n} (${pct(n, v.sample)})`),
    `- ใช้ S.D. ประเภทแทน: ${v.usedGenre} · เส้นขอบ 0.15: ${v.boundary} (v7_8 จัดผิด ${v.boundaryChanged}) · มีข้อมูลฝั่งเดียวแล้วชี้ไปฝั่งที่มีข้อมูล: ${v.oneSideToDataSide}/${v.oneSide} · กฎเดิมบอกว่าตรงกันทั้งที่ค่าเฉลี่ยห่างเกิน 1.0: ${v.oldAgreeFar}`,
    `- มัธยฐาน S.D. รายเรื่อง ${f2(v.medianMovieSD)} vs ระดับประเภท ${f2(v.medianGenreSD)} · ตรงกับ Recommended_Trust_Side ที่เก็บไว้ ${v.storedAgree}/${v.storedCompared}`, ``); }
  if (R.filters) L.push(`## ฟิลเตอร์และ index`, `- ${R.filters.combos} ชุดฟิลเตอร์ ผ่านทุกเงื่อนไข: ${R.filters.allPass ? "ใช่" : "ไม่"} · composite index: ${R.filters.indexes.join(", ")}`, ...R.filters.details.map(x => `- ${x}`), ``);
  if (R.algolia) { L.push(`## การค้นหา: แบบเดิม ${R.algolia.passPrefix}/${R.algolia.cases} → Algolia ${R.algolia.pass}/${R.algolia.cases}`, `- Algolia index มี ${R.algolia.indexSize ?? "—"} records${R.algolia.firestoreTotal ? ` (${pct(R.algolia.indexSize, R.algolia.firestoreTotal)} ของ Firestore)` : ""}`, ``, `| คำค้น | ทดสอบ | แบบเดิม | Algolia | 3 อันดับแรก | ms |`, `|---|---|---|---|---|---:|`); R.algolia.rows.forEach(r => L.push(`| ${r.join(" | ")} |`)); L.push(``); }
  if (R.ai) { L.push(`## AI guardrails (${R.ai.pass}/${R.ai.tests} ผ่าน, ${R.ai.model})`, `| # | กติกา | ผล | คำตอบ | ms |`, `|---|---|---|---|---:|`); R.ai.rows.forEach(r => L.push(`| ${r.map(x => x.replace(/\|/g, "/").replace(/\n/g, " ")).join(" | ")} |`)); }
  return L.join("\n");
}
function refreshSummary() { $("#summary").value = mdSummary(); }
function download(name, text, type) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); }

const RUNNERS = { eda: runEDA, lat: runLatency, cmp: runCompleteness, gen: runGenres, rec: runRecompute, ver: runVerdicts, fil: runFilters, alg: runAlgolia, ai: runAI };
Object.entries(RUNNERS).forEach(([k, fn]) => $(`#btn-${k}`).addEventListener("click", async () => { R.ranAt = new Date().toISOString(); await fn(); refreshSummary(); }));
$("#btn-all").addEventListener("click", async () => {
  $("#btn-all").disabled = true; R.ranAt = new Date().toISOString();
  for (const k of ["lat", "cmp", "gen", "rec", "ver", "eda", "fil", "alg"]) { await RUNNERS[k](); refreshSummary(); }
  $("#btn-all").disabled = false;
});
$("#btn-copy").addEventListener("click", async () => { refreshSummary(); try { await navigator.clipboard.writeText($("#summary").value); $("#btn-copy").innerText = "คัดลอกแล้ว ✓"; } catch (e) { $("#summary").select(); } setTimeout(() => $("#btn-copy").innerText = "คัดลอก Markdown", 1800); });
$("#btn-md").addEventListener("click", () => { refreshSummary(); download("cinemeter-live-check.md", $("#summary").value, "text/markdown"); });
$("#btn-json").addEventListener("click", () => download("cinemeter-live-check.json", JSON.stringify(R, null, 2), "application/json"));
$("#resample").addEventListener("click", () => { SAMPLE = null; $("#resample").innerText = "จะสุ่มใหม่ในการรันครั้งถัดไป ✓"; });
