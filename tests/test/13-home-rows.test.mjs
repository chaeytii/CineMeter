// หน้าแรก (HOME-02): เรื่องเดียวกันไม่ซ้ำหลายแถว และการ์ตูนครอบครัว (เช่น โดราเอมอน) ไม่ไปอยู่แถวหมวดอื่น
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, resetDom } from "../helpers/setup.mjs";

const titlesIn = el => el.children.map(c => (c.innerHTML.match(/alt="([^"]*)"/) || [])[1]);
const show = (id, title, genres, extra = {}) => ({
  id, Title_EN: title, Title_TH: "", Year: "2020", Genre_for_cal: genres[0], Genres: genres, MediaType: "ซีรีส์",
  imdbVotes: 500_000, Popularity: 9_000, imdbRating: "6.0", tmdbRating: 6.0, Audience_Average: 6.0,
  Poster: `https://img.example/${id}.jpg`, ...extra,
});
const doraemon = show("tt0000901", "Doraemon", ["บู๊", "ผจญ", "แอนนิเมชั่น", "ตลก", "จินตนาการ", "นิยายวิทยาศาสตร์", "ครอบครัว"]);
const spiderVerse = show("tt0000902", "Spider-Verse", ["แอนนิเมชั่น", "บู๊", "ผจญ", "นิยายวิทยาศาสตร์"], { MediaType: "ภาพยนตร์" });
const hits = ["Thrones", "Runner", "Squid"].map((t, i) =>
  show(`tt000091${i}`, t, ["บู๊", "ตลก", "นิยายวิทยาศาสตร์", "สยองขวัญ"], { Popularity: 8_000 - i }));

test("[BL-HM-01] การ์ตูนครอบครัวไม่ขึ้นแถวหมวดอื่น แต่ขึ้นแถวแอนิเมชัน/ครอบครัว/แถวไม่ระบุประเภทได้; การ์ตูนผู้ใหญ่ยังอยู่แถวบู๊", () => {
  for (const g of ["บู๊", "ตลก", "นิยายวิทยาศาสตร์", "สยองขวัญ"]) assert.equal(app.familyCartoonOutOfPlace(doraemon, g), true, g);
  for (const g of ["แอนนิเมชั่น", "ครอบครัว", "", undefined]) assert.equal(app.familyCartoonOutOfPlace(doraemon, g), false, String(g));
  assert.equal(app.familyCartoonOutOfPlace(spiderVerse, "บู๊"), false);
  assert.equal(app.familyCartoonOutOfPlace({ id: "x", Genre_for_cal: "ครอบครัว" }, "บู๊"), false, "มีประเภทเดียว ไม่ใช่การ์ตูน");
});

test("[BL-HM-02] (edge) เลือกเรื่องให้แถว: ข้ามเรื่องที่แถวบนแสดงแล้ว เรื่องไม่มีโปสเตอร์ เรื่องซ้ำในรายการ และตัดที่ขนาดแถว", () => {
  const list = [doraemon, hits[0], { ...hits[1], Poster: "" }, hits[0], spiderVerse, hits[2], null];
  assert.deepEqual(app.pickRowMovies(list, new Set([hits[2].id]), 18, "บู๊").map(m => m.Title_EN), ["Thrones", "Spider-Verse"]);
  assert.deepEqual(app.pickRowMovies(list, [], 2, "แอนนิเมชั่น").map(m => m.Title_EN), ["Doraemon", "Thrones"]);
  assert.deepEqual(app.pickRowMovies([], [], 18, "บู๊"), []);
});

test("[BL-HM-03] หน้าแรกโหลดทุกแถวพร้อมกัน: ไม่มีเรื่องซ้ำข้ามแถว โดราเอมอนไม่อยู่แถว Action/Comedy/Sci-Fi และแถวยังเต็ม 18 เรื่อง", async () => {
  resetDom();
  const rows = [...makeMovies(3000, 7, { genresArray: true }), doraemon, spiderVerse, ...hits];
  await useDb(rows, { compositeIndex: true }, { genresComplete: true });
  app.rowState.clear();
  app.homeShown?.clear();
  app.homePending?.clear();
  // ลำดับที่แถวโหลดเสร็จต้องไม่มีผล: เรียกจากล่างขึ้นบน
  await Promise.all([...app.HOME_ROWS].reverse().map(r => app.loadHomeRow(r.key)));

  const byRow = Object.fromEntries(app.HOME_ROWS.map(r => [r.key, titlesIn(document.getElementById("row-" + r.key))]));
  const seen = new Map();
  for (const [key, titles] of Object.entries(byRow))
    for (const t of titles) {
      assert.ok(!seen.has(t), `"${t}" ซ้ำในแถว ${seen.get(t)} และ ${key}`);
      seen.set(t, key);
    }
  for (const key of ["action", "comedy", "scifi"]) assert.ok(!byRow[key].includes("Doraemon"), key);
  assert.ok(byRow.action.includes("Thrones") && byRow.action.includes("Spider-Verse"), byRow.action.join(", "));
  assert.ok(byRow.animation.includes("Doraemon"), byRow.animation.join(", "));
  for (const key of ["action", "comedy", "scifi", "horror"]) assert.equal(byRow[key].length, app.ROW_SIZE, key);
});
