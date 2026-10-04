// Trending now (year-by-year, Popularity) + Search ranking
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";

const movies = makeMovies(3000, 21);

function trendingOracle(rows, f) {
  const out = [];
  for (const y of [2026, 2025, 2024]) {
    out.push(...rows
      .filter(m => m.Year === String(y) && m.Popularity >= 10)
      .filter(m => !f.genre || (app.GENRE_VARIANTS[f.genre] || [f.genre]).includes(m.Genre_for_cal))
      .filter(m => !f.media || m.MediaType === f.media)
      .sort((a, b) => (b.Popularity - a.Popularity) || (a.id < b.id ? 1 : -1))
      .map(m => m.id));
  }
  return out;
}

async function loadAllTrending(f) {
  const got = []; let cursor = null;
  for (let i = 0; i < 200; i++) {
    const r = await app.loadTrending(cursor, f);
    got.push(...r.movies.map(m => m.id));
    if (r.done || !r.cursor) break;
    cursor = r.cursor;
  }
  return got;
}

test("[BL-TR-01] Trending now: ไล่ปี 2026→2025→2024, ในแต่ละปีเรียง Popularity มาก→น้อย, ตัด Popularity < 10 — ลำดับตรงกับ oracle ทุกตำแหน่ง", async () => {
  await useDb(movies);
  assert.deepEqual(app.trendingYears(), [2026, 2025, 2024]);
  const f = F({ popular: "popular" });
  assert.equal(app.isTrendingMode(f), true);
  const got = await loadAllTrending(f);
  const exp = trendingOracle(movies, f);
  assert.equal(got.length, exp.length);
  assert.deepEqual(got, exp);
});

test("[BL-TR-02] Trending + Genre + Type (มี composite index) → ลำดับตรงกับ oracle", async () => {
  await useDb(movies, { compositeIndex: true });
  for (const [genre, media] of [["สยองขวัญ", ""], ["บู๊", "ซีรีส์"], ["หนังชีวิต", "ภาพยนตร์"]]) {
    const f = F({ genre, media, popular: "popular" });
    assert.deepEqual(await loadAllTrending(f), trendingOracle(movies, f), `${genre}|${media}`);
  }
});

test("[BL-TR-03] Trending + Genre แต่ไม่มี composite index → ถอยไปเรียง Popularity ทั้งฐานข้อมูล (ผลยังผ่านฟิลเตอร์ครบ)", async () => {
  await useDb(movies, { compositeIndex: false });
  const f = F({ genre: "สยองขวัญ", popular: "popular" });
  const r = await app.loadTrending(null, f);
  assert.ok(r.movies.length > 0);
  assert.ok(r.movies.every(m => app.passesFilters(m, f)));
  const oldOnes = r.movies.filter(m => +m.Year < 2024).length;
  console.log(`[BL-TR-03] fallback page: ${r.movies.length} titles, ${oldOnes} older than 2024 (year window not enforced in fallback)`);
});

test("[BL-TR-04] เลือกปีเอง หรือค้นหาอยู่ → ไม่ใช้โหมดไล่ปี", () => {
  assert.equal(app.isTrendingMode(F({ year: "2010s" })), false);
  assert.equal(app.isTrendingMode(F({ search: "dune" })), false);
  assert.equal(app.isTrendingMode(F({ popular: "votes" })), false);
});

// ---------------- Search ----------------
test("[BL-SE-01] จัดอันดับผลค้นหา: ชื่อตรงคำค้นมาก่อน แล้วเรียง imdbVotes มาก→น้อย", async () => {
  await useDb(movies);
  const hits = [
    { id: "a", Title_EN: "The Odyssey", imdbVotes: 120 },
    { id: "b", Title_EN: "Odyssey 5", imdbVotes: 5000 },
    { id: "c", Title_EN: "Homer's Journey", imdbVotes: 999999 },   // เจอเพราะเรื่องย่อ ไม่ใช่ชื่อ
    { id: "d", Title_EN: "2001: A Space Odyssey", imdbVotes: 750000 },
  ];
  assert.deepEqual(app.sortSearchHits(hits, "odyssey").map(h => h.id), ["d", "b", "a", "c"]);
});

test("[BL-SE-02] ค้นภาษาไทย: ตัดวรรณยุกต์ก่อนเทียบ ('โอดิสซี่' = 'โอดิสซี')", () => {
  assert.equal(app.stripThaiTones("โอดิสซี่"), "โอดิสซี");
  assert.equal(app.titleMatchTier({ Title_TH: "มหากาพย์โอดิสซี" }, "โอดิสซี่"), 1);
  assert.equal(app.normTitle("  Spider-Man:  No Way Home "), "spider man no way home");
});

test("[BL-SE-03] ค้นหา (Firestore fallback เมื่อ Algolia ใช้ไม่ได้): พิมพ์ตัวเล็กก็เจอ ผลขึ้นต้นด้วยคำค้น และผ่านฟิลเตอร์ที่เลือก", async () => {
  await useDb(movies);
  const r = await app.loadSearch("movie 12", null, F({ search: "movie 12" }));
  assert.ok(r.movies.length > 0);
  assert.ok(r.movies.every(m => m.Title_EN.toLowerCase().startsWith("movie 12")));
  const g = await app.loadSearch("movie 1", null, F({ search: "movie 1", media: "ซีรีส์" }));
  assert.ok(g.movies.length > 0 && g.movies.every(m => m.MediaType === "ซีรีส์"));
});

test("[BL-SE-04] ค้นหาคำที่ไม่มีในฐานข้อมูล → ผลว่าง ไม่ error", async () => {
  await useDb(movies);
  const r = await app.loadSearch("zzqxv nothing", null, F({ search: "zzqxv nothing" }));
  assert.equal(r.movies.length, 0);
});

test("[BL-TR-05] หัวข้อ Trending now แสดงช่วงปีจากน้อยไปมาก (2024–2026)", () => {
  const saved = { ...app.activeFilters };
  Object.assign(app.activeFilters, { popular: "popular", genre: "", year: "", media: "" });
  app.__hooks.set("searchQuery", "");
  try {
    app.updateGridHeader();
    assert.match(document.getElementById("grid-header-title").innerText, /Trending now · 2024–2026/);
  } finally { Object.assign(app.activeFilters, saved); }
});
