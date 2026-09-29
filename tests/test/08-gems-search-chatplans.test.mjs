// Hidden gems, GENRE_ANALYSIS fallback, Algolia search path (fake Algolia), chatbot retrieval plans
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";
const h = app.__hooks;
const rows = makeMovies(3000, 81);

test("[BL-HG-01] Hidden gems: คะแนนคนดู > 7.5 และ (โหวต < 50,000 หรือ popularity < 20) และสุ่มชุดใหม่ทุกครั้ง", async () => {
  await useDb(rows);
  const f = F({ popular: "random" });
  const a = await app.loadDiscovery(null, f);
  const b = await app.loadDiscovery(null, f);
  const ok = m => m.Audience_Average > 7.5 && (m.imdbVotes < 50000 || (m.Popularity > 0 && m.Popularity < 20));
  assert.ok(a.movies.length >= 8);
  assert.ok(a.movies.every(ok), "มีหนังที่ไม่ใช่ hidden gem ปนมา");
  const overlap = a.movies.filter(m => b.movies.some(x => x.id === m.id)).length;
  console.log(`[BL-HG-01] set A=${a.movies.length} set B=${b.movies.length} overlap=${overlap}`);
  assert.ok(overlap < a.movies.length, "สุ่มสองครั้งได้ชุดเดิมทั้งหมด");
});

test("[BL-HG-02] Hidden gems + ฟิลเตอร์ Genre/Year (ไม่มี composite index) → ยังได้ผลที่ผ่านทุกเงื่อนไข", async () => {
  await useDb(rows, { compositeIndex: false });
  const f = F({ popular: "random", genre: "หนังชีวิต", year: "2020s" });
  const r = await app.loadDiscovery(null, f);
  assert.ok(r.movies.length > 0);
  assert.ok(r.movies.every(m => app.passesFilters(m, f) && m.Audience_Average > 7.5));
});

test("[BL-GA-01] อ่าน S.D. ระดับประเภทจาก GENRE_ANALYSIS (มีแคช) และคืน null เมื่อไม่มีประเภทนั้น", async () => {
  const fdb = await useDb(rows, { extraCollections: { GENRE_ANALYSIS: [{ id: "ตลก", Genre_Audience_SD: 0.91, Genre_Critics_SD: "1.37" }] } });
  const g = await app.getGenreSD("ตลก");
  assert.deepEqual(g, { audience: 0.91, critics: 1.37 });
  const reads = fdb.stats.reads;
  await app.getGenreSD("ตลก");
  assert.equal(fdb.stats.reads, reads, "ครั้งที่สองควรมาจากแคช");
  assert.deepEqual(await app.getGenreSD("ไม่มีประเภทนี้"), { audience: null, critics: null });
  assert.deepEqual(await app.getGenreSD(""), { audience: null, critics: null });
});

// ---------- Algolia path with a fake Algolia endpoint ----------
function fakeAlgolia(data) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const body = JSON.parse(init.body);
    calls.push(body);
    const q = String(body.query).toLowerCase();
    const hits = data.filter(m => [m.Title_EN, m.Title_TH].some(t => String(t || "").toLowerCase().includes(q)))
      .map(m => ({ ...m, objectID: m.id, _highlightResult: {} }));
    const per = body.hitsPerPage, page = body.page;
    return { ok: true, json: async () => ({ hits: hits.slice(page * per, (page + 1) * per), nbHits: hits.length, page, nbPages: Math.ceil(hits.length / per) }) };
  };
  return calls;
}

test("[BL-SE-05] Algolia: ค้นคำกลางชื่อได้ ผลที่ชื่อตรงมาก่อนและเรียงตามโหวต, มีฟิลเตอร์ → ไล่หลายหน้าจนได้ผลพอ", async () => {
  await useDb(rows);
  Object.assign(h.algolia, { appId: "APP", searchKey: "KEY", indexName: "IDX" });
  const calls = fakeAlgolia(rows);
  try {
    const r = await app.loadSearch("odyssey", null, F({ search: "odyssey" }));
    assert.ok(r.movies.length > 0 && r.movies.every(m => /odyssey/i.test(m.Title_EN)));
    const v = r.movies.map(m => m.imdbVotes);
    assert.ok(v.every((x, i) => i === 0 || x <= v[i - 1]), "ต้องเรียงโหวตมาก→น้อย");
    const before = calls.length;
    const g = await app.loadSearch("movie", null, F({ search: "movie", genre: "สงคราม", media: "ซีรีส์" }));
    assert.ok(g.movies.every(m => app.passesFilters(m, F({ genre: "สงคราม", media: "ซีรีส์" }))));
    assert.ok(calls.length - before >= 1 && calls.slice(before).every(c => c.hitsPerPage === 100));
  } finally { Object.assign(h.algolia, { appId: "", searchKey: "", indexName: "" }); }
});

test("[BL-SE-06] Algolia ค้นไทยมีวรรณยุกต์ไม่เจอ → ลองใหม่แบบตัดวรรณยุกต์อัตโนมัติ", async () => {
  await useDb(rows);
  Object.assign(h.algolia, { appId: "APP", searchKey: "KEY", indexName: "IDX" });
  const data = [{ id: "tt1", Title_EN: "The Odyssey", Title_TH: "มหากาพย์โอดิสซี", imdbVotes: 10 }];
  const calls = fakeAlgolia(data);
  try {
    const r = await app.loadSearch("โอดิสซี่", null, F({ search: "โอดิสซี่" }));
    assert.equal(r.movies.length, 1);
    assert.deepEqual(calls.map(c => c.query), ["โอดิสซี่", "โอดิสซี"]);
    assert.equal(calls[0].queryType, "prefixAll");
  } finally { Object.assign(h.algolia, { appId: "", searchKey: "", indexName: "" }); }
});

test("[BL-SE-07] Algolia ล่ม → ถอยไปค้นด้วย Firestore อัตโนมัติ (ผู้ใช้ยังค้นเจอ)", async () => {
  await useDb(rows);
  Object.assign(h.algolia, { appId: "APP", searchKey: "KEY", indexName: "IDX" });
  globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => ({}) });
  try {
    const r = await app.loadSearch("Movie 7", null, F({ search: "Movie 7" }));
    assert.ok(r.movies.length > 0);
  } finally { Object.assign(h.algolia, { appId: "", searchKey: "", indexName: "" }); }
});

// ---------- chatbot retrieval plans ----------
for (const [id, plan, check] of [
  ["AI-CB-08", { mode: "top" }, (ms) => ms.every((m, i) => i === 0 || m.Audience_Average <= ms[i - 1].Audience_Average)],
  ["AI-CB-09", { mode: "title", title: "Movie 12" }, (ms) => ms.every(m => /^Movie 12/.test(m.Title_EN))],
  ["AI-CB-10", { mode: "discovery" }, (ms) => ms.every(m => m.Audience_Average > 7.5)],
  ["AI-CB-11", { mode: "genre", genre: "comedy", minVotes: 1000 }, (ms) => ms.every(m => m.Genre_for_cal === "ตลก" && m.imdbVotes >= 1000)],
]) {
  test(`[${id}] แผนค้นฐานข้อมูลของแชทบอท mode=${plan.mode}: ได้หนังตรงเงื่อนไข ไม่เกิน 20 เรื่อง`, async () => {
    await useDb(rows);
    const ms = await app.candidatesFromPlan(plan, null);
    assert.ok(ms.length > 0 && ms.length <= 20, `n=${ms.length}`);
    assert.ok(check(ms));
  });
}

test("[AI-CB-12] mode=similar ขณะเปิดหนังอยู่ → ไม่แนะนำหนังเรื่องเดิม", async () => {
  await useDb(rows);
  const base = rows.find(m => m.Year === "2025" && m.Poster);
  const ms = await app.candidatesFromPlan({ mode: "similar" }, base);
  assert.ok(ms.length > 0);
  assert.ok(!ms.some(m => m.id === base.id));
});

test("[SW-FM-08] ค้นหาผ่าน fetchMovies: หัวข้อและผลลัพธ์เป็นของคำค้น", async () => {
  await useDb(rows);
  h.set("searchQuery", "Movie 3");
  await app.fetchMovies();
  const loaded = h.get("loadedMovies");
  assert.ok(loaded.length > 0 && loaded.every(m => m.Title_EN.startsWith("Movie 3")));
  assert.match(document.getElementById("grid-header-title").innerText, /Results for “Movie 3”/);
  h.set("searchQuery", "");
});

test("[BL-RN-01] สุ่มหนังจาก documentId (ใช้ตอน AI ออฟไลน์/หาไม่เจอ) ต้องกระจายทั่วฐานข้อมูล ไม่ได้ชุดเดิมซ้ำ", async () => {
  await useDb(rows);                      // doc ID รูปแบบ imdbID: tt1234567 (ตาม ER diagram กลางภาค)
  const firsts = [], empty = [];
  for (let i = 0; i < 300; i++) {
    const out = await app.answerOffline("แนะนำหนังหน่อย");
    if (!out.movies.length) empty.push(i); else firsts.push(out.movies[0].id);
  }
  const distinct = new Set(firsts).size;
  console.log(`[BL-RN-01] 300 random draws → distinct first titles=${distinct}, empty=${empty.length}`);
  assert.ok(distinct >= 100, `ได้หนังเรื่องแรกไม่ซ้ำกันแค่ ${distinct} แบบจากการสุ่ม 300 ครั้ง`);
  assert.ok(empty.length <= 15, `สุ่มแล้วได้ผลว่าง ${empty.length} ครั้ง`);
});
