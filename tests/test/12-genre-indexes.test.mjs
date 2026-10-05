// กรองประเภทด้วยรายชื่อประเภททั้งหมด (Genres) — ทุก query ที่หน้าเว็บส่งต้องมี index ใน firestore.indexes.json (GEN-01)
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";

const h = app.__hooks;
const INDEXES = JSON.parse(readFileSync(new URL("../../firestore.indexes.json", import.meta.url), "utf8")).indexes;

// ข้อมูลรูปแบบเดียวกับฐานจริง: Genres หลายประเภท, คะแนนถ่วงโหวต, imdbVotes เป็นข้อความ "1,234"
function realisticRows() {
  return makeMovies(1500, 31, { genresArray: true }).map((m, i) => ({
    ...m,
    imdbVotes: m.imdbVotes.toLocaleString("en-US"),
    Audience_Score: m.Audience_Average,
    ...(typeof m.Critics_Average === "number" ? { Critics_Score: m.Critics_Average } : {}),
    Companies: i % 7 === 0 ? [420] : [i % 50 + 1],
  }));
}

async function runEveryGenreQuery(rows) {
  let shown = 0;
  for (const genre of ["บู๊", "สยองขวัญ"]) for (const year of ["", "2020s"]) for (const media of ["", "ซีรีส์"]) {
    for (const popular of ["popular", "votes", "Audience_Average", "Critics_Average"]) {
      app.brokenStrategies.clear();
      const f = F({ genre, year, media, popular });
      const res = popular === "popular" && !year ? await app.loadTrending(null, f) : await app.loadRanked(popular, null, f);
      shown += res.movies.length;
    }
    app.brokenStrategies.clear();
    shown += (await app.loadDiscovery(null, F({ genre, year, media, popular: "random" }))).movies.length;
  }
  const base = rows.find(m => m.Genres.includes("บู๊") && m.Year === "2025" && m.Companies[0] === 420);
  shown += (await app.buildCandidatePool(base)).length;                         // If you like… (ประเภท + ยุค + ค่าย)
  return shown;
}

test("[BL-GN-01] หลังสลับไปใช้ Genres ทุก query ของตัวกรอง/Trending/Discovery/If you like… มี index ใน firestore.indexes.json", async () => {
  const rows = realisticRows();
  const fdb = await useDb(rows, { indexes: INDEXES }, { genresComplete: true });
  assert.equal(h.get("genresArrayReady"), true);
  assert.equal(h.get("votesNumeric"), false, "imdbVotes ในฐานจริงเป็นข้อความ → Most voted เรียงด้วย Popularity");
  const shown = await runEveryGenreQuery(rows);
  assert.equal(fdb.stats.indexErrors, 0, JSON.stringify(fdb.stats.log.slice(-3)));
  assert.ok(shown > 0);
  assert.ok(fdb.stats.log.some(l => l.wheres.includes("Genres array-contains") && l.orders.includes("Audience_Score desc")));
});

test("[BL-GN-02] (control) ถ้าไม่มี index ของ Genres เลย ตัวจำลองต้องปฏิเสธเหมือน Firestore จริง แต่หน้าเว็บยังแสดงผลได้ด้วยโหมดสำรอง", async () => {
  const rows = realisticRows();
  const fdb = await useDb(rows, { indexes: INDEXES.filter(ix => ix.fields[0].fieldPath !== "Genres") }, { genresComplete: true });
  const shown = await runEveryGenreQuery(rows);
  assert.ok(fdb.stats.indexErrors > 0);
  assert.ok(shown > 0);
});
