// Firestore REST query builder + main fetch flow (race conditions, cache, dedupe, empty state)
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";
const h = app.__hooks;
const { query, collection, where, orderBy, limit, startAfter, db } = app;

test("[SW-RS-01] สร้าง structuredQuery: หลายเงื่อนไขเป็น AND, ค่า Year เป็น string, orderBy ต่อท้าย __name__ ตามทิศเดียวกัน", () => {
  const q = app.buildStructuredQuery(query(collection(db, "MOVIES"),
    where("Year", "in", ["2024", "2025"]), where("Genre_for_cal", "==", "บู๊"), orderBy("Popularity", "desc"), limit(60)));
  assert.equal(q.where.compositeFilter.op, "AND");
  assert.equal(q.where.compositeFilter.filters.length, 2);
  assert.deepEqual(q.where.compositeFilter.filters[0].fieldFilter.value, { arrayValue: { values: [{ stringValue: "2024" }, { stringValue: "2025" }] } });
  assert.deepEqual(q.orderBy.map(o => [o.field.fieldPath, o.direction]), [["Popularity", "DESCENDING"], ["__name__", "DESCENDING"]]);
  assert.equal(q.limit, 60);
});

test("[SW-RS-02] ชื่อฟิลด์ที่มีอักขระพิเศษถูกครอบ backtick, cursor จาก snapshot ใช้ค่าทุกฟิลด์ที่เรียง", () => {
  assert.equal(app.fieldRef("Title_TH").fieldPath, "Title_TH");
  assert.equal(app.fieldRef("Genre for cal").fieldPath, "`Genre for cal`");
  const snap = app.makeSnapshot({ name: "projects/p/databases/(default)/documents/MOVIES/tt1", fields: { Popularity: { doubleValue: 12.5 } } });
  const q = app.buildStructuredQuery(query(collection(db, "MOVIES"), orderBy("Popularity", "desc"), startAfter(snap), limit(5)));
  assert.deepEqual(q.startAt.values, [{ doubleValue: 12.5 }, { referenceValue: snap.name }]);
  assert.equal(q.startAt.before, false);
});

test("[SW-RS-03] แปลงค่า Firestore ไป-กลับครบทุกชนิด (int/double/string/bool/null/array/map)", () => {
  const v = { a: 1, b: 2.5, c: "x", d: true, e: null, f: [1, "y", [2]], g: { h: "ไทย" } };
  assert.deepEqual(app.fromFsValue(app.toFsValue(v)), v);
  assert.deepEqual(app.toFsValue(3), { integerValue: "3" });
});

// ---------------- fetchMovies ----------------
const rows = makeMovies(2500, 61);
const ids = el => el.children.map(c => (c.innerHTML.match(/alt="([^"]*)"/) || [])[1]);

test("[SW-FM-01] กดฟิลเตอร์รัว ๆ (request เก่าช้ากว่า) → จอแสดงผลของฟิลเตอร์ล่าสุดเท่านั้น และปลดสถานะ loading", async () => {
  await useDb(rows, { delayFor: q => q.parts.some(p => p.type === "where" && p.value === "สยองขวัญ") ? 60 : 5 });
  app.activeFilters.popular = "votes";
  app.activeFilters.genre = "สยองขวัญ";
  const p1 = app.fetchMovies();
  app.activeFilters.genre = "ตลก";
  const p2 = app.fetchMovies();
  await Promise.all([p1, p2]);
  const loaded = h.get("loadedMovies");
  assert.ok(loaded.length > 0);
  assert.ok(loaded.every(m => m.Genre_for_cal === "ตลก"), "มีหนังของฟิลเตอร์เก่าปนมา");
  assert.equal(h.get("loading"), false);
  assert.ok(!app.pageCache.has(app.filterKey(F({ genre: "สยองขวัญ", popular: "votes" }))), "ผลเก่าไม่ควรถูกเขียนลงแคช");
});

test("[SW-FM-02] เปลี่ยนฟิลเตอร์ 12 ครั้งติดกันแบบสุ่มหน่วงเวลา → สถานะสุดท้ายตรงกับฟิลเตอร์ครั้งสุดท้ายเสมอ (ทำซ้ำ 20 รอบ)", async () => {
  const combos = [["บู๊", "2020s", ""], ["สยองขวัญ", "", "ซีรีส์"], ["", "1990s", "ภาพยนตร์"], ["ตลก", "", ""], ["หนังชีวิต", "2010s", ""]];
  let seed = 3; const r = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let round = 0; round < 20; round++) {
    await useDb(rows, { delayFor: () => Math.floor(r() * 25) });
    app.activeFilters.popular = "votes";
    const ps = []; let last;
    for (let i = 0; i < 12; i++) {
      last = combos[Math.floor(r() * combos.length)];
      [app.activeFilters.genre, app.activeFilters.year, app.activeFilters.media] = last;
      ps.push(app.fetchMovies());
    }
    await Promise.all(ps);
    const f = F({ genre: last[0], year: last[1], media: last[2], popular: "votes" });
    const loaded = h.get("loadedMovies");
    assert.ok(loaded.every(m => app.passesFilters(m, f)), `round ${round}`);
    assert.equal(h.get("loading"), false);
  }
});

test("[SW-FM-03] เลือกฟิลเตอร์เดิมซ้ำภายใน 5 นาที → แสดงจากแคชทันที ไม่ยิง query ใหม่", async () => {
  const fdb = await useDb(rows);
  app.activeFilters.popular = "votes"; app.activeFilters.genre = "บู๊";
  await app.fetchMovies();
  const q = fdb.stats.queries, first = h.get("loadedMovies").map(m => m.id);
  app.activeFilters.genre = "ตลก"; await app.fetchMovies();
  app.activeFilters.genre = "บู๊"; await app.fetchMovies();
  assert.deepEqual(h.get("loadedMovies").map(m => m.id), first);
  assert.equal(fdb.stats.queries, q + 1, "ควรยิงเพิ่มเฉพาะตอนเปลี่ยนเป็น ตลก");
});

test("[SW-FM-04] (Midterm TC5) โหลดหน้าถัดไปหลายครั้ง → ไม่มีหนังซ้ำในรายการ", async () => {
  await useDb(rows);
  app.activeFilters.popular = "Audience_Average";
  await app.fetchMovies();
  for (let i = 0; i < 6; i++) await app.fetchMovies({ append: true });
  const list = h.get("loadedMovies").map(m => m.id);
  assert.ok(list.length > 200);
  assert.equal(new Set(list).size, list.length);
});

test("[SW-FM-05] (Midterm TC7) ข้อมูลหมดแล้ว (exhausted) → กดโหลดเพิ่มไม่ยิง query และปุ่มถูกซ่อน", async () => {
  const fdb = await useDb(makeMovies(90, 62));
  app.activeFilters.popular = "votes";
  await app.fetchMovies();
  for (let i = 0; i < 5 && !h.get("exhausted"); i++) await app.fetchMovies({ append: true });
  assert.equal(h.get("exhausted"), true);
  const q = fdb.stats.queries;
  await app.fetchMovies({ append: true });
  assert.equal(fdb.stats.queries, q);
  assert.equal(document.getElementById("loadMoreBtn").style.display, "none");
});

test("[SW-FM-06] (Midterm TC8) ฟิลเตอร์ไม่พบหนัง → ข้อความ 'ไม่พบผลลัพธ์' ไม่ใช่หน้าว่าง/ error", async () => {
  await useDb(makeMovies(150, 63).map(m => ({ ...m, MediaType: "ภาพยนตร์" })));
  app.activeFilters.popular = "votes"; app.activeFilters.media = "ซีรีส์";
  await app.fetchMovies();
  assert.match(document.getElementById("movieGrid").innerHTML, /ไม่พบผลลัพธ์/);
});

test("[SW-FM-07] ฐานข้อมูลตอบ error → แสดงข้อความโหลดไม่สำเร็จ และปลด loading", async () => {
  await useDb(rows);
  h.setGetDocs(async () => { throw new Error("Firestore timeout"); });
  app.activeFilters.popular = "votes";
  await app.fetchMovies();
  assert.match(document.getElementById("movieGrid").innerHTML, /โหลดข้อมูลไม่สำเร็จ: Firestore timeout/);
  assert.equal(h.get("loading"), false);
});
