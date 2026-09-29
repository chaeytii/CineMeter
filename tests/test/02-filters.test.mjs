// Multi-filter (Genre + Year + Type) × Sort mode — checked against an independent brute-force oracle
// on a 3,000-title fake Firestore, both WITH and WITHOUT composite indexes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";

const movies = makeMovies(3000, 11);
const moviesG = makeMovies(3000, 12, { genresArray: true });

// ---- independent oracle (does not use the app's filter functions) ----
function oracle(rows, f, mode, { genresArray = false } = {}) {
  const variants = app.GENRE_VARIANTS[f.genre] || [f.genre];
  const canon = app.GENRE_CANONICAL[f.genre] || f.genre;
  const dec = f.year ? +f.year.slice(0, 4) : null;
  return rows.filter(m => {
    if (f.genre) {
      if (genresArray) { if (!(m.Genres || []).includes(canon)) return false; }
      else if (!variants.includes(m.Genre_for_cal)) return false;
    }
    if (dec !== null) { const y = parseInt(m.Year, 10); if (y < dec || y > dec + 9) return false; }
    if (f.media && m.MediaType !== f.media) return false;
    if ((mode === "Audience_Average" || mode === "Critics_Average") && typeof m[mode] !== "number") return false;
    return true;
  }).map(m => m.id);
}

async function loadAll(mode, f) {
  const pages = [];
  let cursor = null;
  for (let i = 0; i < 400; i++) {
    const res = await app.loadRanked(mode, cursor, f);
    pages.push(res.movies);
    if (res.done || !res.cursor) break;
    cursor = res.cursor;
  }
  return pages;
}

const GENRES = ["", "บู๊", "สยองขวัญ", "หนังรักโรแมนติก", "หนังชีวิต", "โรแมนติก", "สงคราม"];
const YEARS = ["", "2020s", "1990s", "1980s"];
const MEDIA = ["", "ภาพยนตร์", "ซีรีส์"];
const MODES = ["votes", "Audience_Average", "Critics_Average"];

for (const compositeIndex of [true, false]) {
  test(`[BL-FL-${compositeIndex ? "01" : "02"}] ทุกชุดฟิลเตอร์ 7×4×3 × การเรียง 3 แบบ (${compositeIndex ? "มี" : "ไม่มี"} composite index): ครบ ไม่ซ้ำ ไม่หลุดเงื่อนไข หน้าแรกไม่ว่าง`, async () => {
    const fdb = await useDb(movies, { compositeIndex });
    const problems = [];
    let scenarios = 0, totalExpected = 0, orderViolations = 0, orderPairs = 0;
    for (const genre of GENRES) for (const year of YEARS) for (const media of MEDIA) for (const mode of MODES) {
      scenarios++;
      app.brokenStrategies.clear();
      const f = F({ genre, year, media, popular: mode });
      const expected = new Set(oracle(movies, f, mode));
      totalExpected += expected.size;
      const pages = await loadAll(mode, f);
      const got = pages.flat().map(m => m.id);
      const gotSet = new Set(got);
      const tag = `${genre || "-"}|${year || "-"}|${media || "-"}|${mode}`;
      if (got.length !== gotSet.size) problems.push(`${tag}: ซ้ำ ${got.length - gotSet.size}`);
      const missing = [...expected].filter(id => !gotSet.has(id));
      const extra = [...gotSet].filter(id => !expected.has(id));
      if (missing.length) problems.push(`${tag}: ขาด ${missing.length}/${expected.size}`);
      if (extra.length) problems.push(`${tag}: เกิน ${extra.length}`);
      if (expected.size && !pages[0].length) problems.push(`${tag}: หน้าแรกว่างทั้งที่มี ${expected.size} เรื่อง`);
      if (mode === "votes") {
        const v = pages.flat().map(m => m.imdbVotes);
        for (let i = 1; i < v.length; i++) { orderPairs++; if (v[i] > v[i - 1]) orderViolations++; }
      }
    }
    test.diagnostic?.(`scenarios=${scenarios} expectedTitles=${totalExpected} queries=${fdb.stats.queries} reads=${fdb.stats.reads} indexErrors=${fdb.stats.indexErrors} votesOrderViolations=${orderViolations}/${orderPairs}`);
    console.log(`[BL-FL-${compositeIndex ? "01" : "02"}] scenarios=${scenarios} expected=${totalExpected} queries=${fdb.stats.queries} reads=${fdb.stats.reads} indexErrors=${fdb.stats.indexErrors} votesOrder=${orderViolations}/${orderPairs}`);
    assert.deepEqual(problems, []);
  });
}

test("[BL-FL-03] โหมด Genres แบบ array (หลายประเภทต่อเรื่อง) + Year + Type: ผลตรงกับ oracle", async () => {
  await useDb(moviesG, { compositeIndex: true }, { genresComplete: true });
  assert.equal(app.__hooks.get("genresArrayReady"), true);
  const problems = [];
  for (const genre of ["บู๊", "สยองขวัญ", "โรแมนติก", "หนังรักโรแมนติก", "นิยายวิทยาศาสตร์"]) for (const year of ["", "2020s"]) for (const media of ["", "ซีรีส์"]) {
    app.brokenStrategies.clear();
    const f = F({ genre, year, media, popular: "votes" });
    const expected = new Set(oracle(moviesG, f, "votes", { genresArray: true }));
    const got = new Set((await loadAll("votes", f)).flat().map(m => m.id));
    const diff = [...expected].filter(x => !got.has(x)).length + [...got].filter(x => !expected.has(x)).length;
    if (diff) problems.push(`${genre}|${year}|${media}: ต่าง ${diff}`);
  }
  assert.deepEqual(problems, []);
});

test("[BL-FL-04] (Midterm TC8) ฟิลเตอร์ที่ไม่มีหนังเลย → คืนผลว่างและ done=true ไม่ error", async () => {
  const few = makeMovies(200, 3).map(m => ({ ...m, MediaType: "ภาพยนตร์" }));
  await useDb(few);
  const res = await app.loadRanked("votes", null, F({ genre: "สยองขวัญ", year: "1980s", media: "ซีรีส์", popular: "votes" }));
  assert.equal(res.movies.length, 0);
  assert.equal(res.done, true);
});

test("[BL-FL-05] passesFilters ทำงานแบบ AND: ผ่านครบทุกเงื่อนไขเท่านั้น", () => {
  const m = { Genre_for_cal: "สยองขวัญ", Year: "2024", MediaType: "ภาพยนตร์" };
  assert.equal(app.passesFilters(m, { genre: "สยองขวัญ", year: "2020s", media: "ภาพยนตร์" }), true);
  assert.equal(app.passesFilters(m, { genre: "สยองขวัญ", year: "2010s", media: "ภาพยนตร์" }), false);
  assert.equal(app.passesFilters(m, { genre: "ตลก", year: "2020s", media: "ภาพยนตร์" }), false);
  assert.equal(app.passesFilters(m, { genre: "สยองขวัญ", year: "2020s", media: "ซีรีส์" }), false);
  assert.equal(app.passesFilters({ ...m, Genre_for_cal: "บู๊, ผจญภัย" }, { genre: "ผจญ" }), true, "ซีรีส์ Action & Adventure ต้องอยู่ทั้งหมวดบู๊และผจญภัย");
});

test("[BL-FL-06] (Midterm TC2) Genre_for_cal คำเดียวไม่มี comma → ใช้ค่าเดิมทั้งหมด", () => {
  assert.deepEqual(app.legacyGenres({ Genre_for_cal: "ตลก" }), ["ตลก"]);
  assert.deepEqual(app.legacyGenres({ Genre_for_cal: "บู๊, ผจญภัย" }).sort(), ["บู๊", "ผจญ"].sort());
});
