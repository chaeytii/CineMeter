// Robustness: messy data formats that real imports often contain
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";
const h = app.__hooks;

test("[RB-01] ถ้าคะแนนที่ไม่มีข้อมูลถูกเก็บเป็นข้อความ 'N/A' (ไม่ใช่ลบฟิลด์) → หมวด Loved by critics หน้าแรกต้องยังมีหนัง", async () => {
  const rows = makeMovies(2000, 71).map((m, i) => (i % 5 < 2 ? { ...m, Critics_Average: "N/A" } : m));
  await useDb(rows);
  app.activeFilters.popular = "Critics_Average";
  await app.fetchMovies();
  const loaded = h.get("loadedMovies");
  assert.ok(loaded.length > 0, "หน้าแรกว่าง → ผู้ใช้เห็น 'ไม่พบผลลัพธ์' ทั้งที่มีหนังคะแนนนักวิจารณ์ " +
    rows.filter(m => typeof m.Critics_Average === "number").length + " เรื่อง");
  assert.ok(loaded.every(m => typeof m.Critics_Average === "number"));
});

test("[RB-02] Year เก็บเป็นตัวเลขแทนข้อความ → ฟิลเตอร์ปีฝั่ง client ยังถูกต้อง", () => {
  assert.equal(app.passesFilters({ Year: 2024, Genre_for_cal: "ตลก" }, { genre: "ตลก", year: "2020s", media: "" }), true);
});

test("[RB-03] หนังไม่มีโปสเตอร์/เรื่องย่อ/นักแสดง → การ์ดและ prompt ไม่ error", () => {
  assert.doesNotThrow(() => app.buildCard({ id: "x" }, ""));
  assert.doesNotThrow(() => app.compactMovie({ id: "x" }));
  assert.equal(app.getEnglishTitle({}), "Untitled");
});

test("[RB-04] (Midterm TC1) หนังไม่มี Metascore หรือ RT → ไม่นับเป็น 0: แสดง N/A และ Recommend side ยังตัดสินได้", () => {
  assert.equal(app.toNumOrNull("N/A"), null);
  const r = app.decideTrustSide({ critics: null, audience: 0.3, overall: null, genreCritics: 0.9, genreAudience: 0.7 });
  assert.equal(r.text, "เชื่อฝั่งคนดู");
});
