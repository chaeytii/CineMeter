// Personalized แบบไม่ต้องล็อกอิน (PERS-01): เบราว์เซอร์จำประเภทหนังที่ผู้ใช้เปิดดู/กดชอบ แล้วทำแถว "For you"
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";

const mv = (id, genres, extra = {}) => ({ id, Genres: genres, Poster: `https://img/${id}.jpg`, ...extra });
const fresh = () => localStorage.clear();

test("[BL-PR-01] ยังไม่เคยเปิดหนัง → ไม่มีแถว For you; เปิด Horror 2 เรื่อง → For you · สยองขวัญ", () => {
  fresh();
  assert.equal(app.forYouRow(), null);
  app.recordTaste(mv("tt1", ["สยองขวัญ"]));
  assert.equal(app.forYouRow(), null, "เปิดเรื่องเดียว (1 แต้ม) ยังไม่ถึงเกณฑ์ 2 แต้ม");
  app.recordTaste(mv("tt2", ["สยองขวัญ", "ลึกลับ"]));
  const row = app.forYouRow();
  assert.deepEqual(row.genres, ["สยองขวัญ"]);
  assert.equal(row.f.genre, "สยองขวัญ");
  assert.equal(row.f.popular, "Audience_Average");
  assert.match(row.title, /^For you · /);
});

test("[BL-PR-02] กดชอบ = +3 และกดซ้ำ = ยกเลิก; เรียงประเภทจากแต้มมากไปน้อย เอา 2 อันดับแรก", () => {
  fresh();
  app.recordTaste(mv("tt1", ["ตลก"]));
  app.recordTaste(mv("tt2", ["ตลก"]));
  app.recordTaste(mv("tt3", ["ตลก"]));                 // ตลก 3
  app.toggleLike(mv("tt4", ["บู๊", "ผจญ"]));            // บู๊ 3, ผจญ 3
  app.recordTaste(mv("tt4", ["บู๊", "ผจญ"]));           // บู๊ 4, ผจญ 4
  let t = app.readTaste();
  assert.deepEqual(app.topGenres(t), ["บู๊", "ผจญ"], "แต้มเท่ากันเรียงตามชื่อ (ลำดับภาษาไทย) ได้ลำดับเดิมทุกครั้ง");
  assert.ok(t.liked.includes("tt4"));
  t = app.toggleLike(mv("tt4", ["บู๊", "ผจญ"]));        // ยกเลิก: บู๊ 1, ผจญ 1
  assert.ok(!t.liked.includes("tt4"));
  assert.deepEqual(app.topGenres(t), ["ตลก"]);
});

test("[BL-PR-03] ประเภทชื่อเดิม (Genre_for_cal) และชื่อเรียกต่างกันนับรวมเป็นประเภทเดียว; หนังที่ไม่มี id ไม่ถูกบันทึก", () => {
  fresh();
  app.recordTaste({ id: "tt1", Genre_for_cal: "โรแมนติก" });
  app.recordTaste(mv("tt2", ["หนังรักโรแมนติก"]));
  assert.deepEqual(app.topGenres(app.readTaste()), ["หนังรักโรแมนติก"]);
  app.recordTaste({ Genres: ["สงคราม"] });
  app.recordTaste(null);
  assert.equal(app.readTaste().genres["สงคราม"], undefined);
});

test("[BL-PR-04] (edge) ข้อมูลใน localStorage เสียหรือผิดรูปแบบ → เริ่มใหม่ ไม่พัง; เปิดเรื่องเดิมซ้ำ seen ไม่ซ้ำ และเก็บไม่เกิน 200 เรื่อง", () => {
  for (const bad of ["{not json", "null", "[]", '{"genres":[1,2]}', '{"genres":"x","seen":5}']) {
    localStorage.setItem(app.TASTE_KEY, bad);
    const t = app.readTaste();
    assert.deepEqual(t, { genres: {}, seen: [], liked: [] }, bad);
    assert.equal(app.forYouRow(), null);
  }
  fresh();
  for (let i = 0; i < 250; i++) app.recordTaste(mv("tt" + i, ["ดราม่า"]));
  app.recordTaste(mv("tt5", ["ดราม่า"]));
  const t = app.readTaste();
  assert.equal(t.seen.length, app.TASTE.seenMax);
  assert.equal(t.seen[0], "tt5");
  assert.equal(new Set(t.seen).size, t.seen.length);
});

test("[BL-PR-05] mixForYou: สลับประเภททีละเรื่อง, ไม่ซ้ำ, ข้ามเรื่องที่เคยเปิดและเรื่องไม่มีโปสเตอร์, ไม่เกินจำนวนที่ขอ", () => {
  const a = [mv("a1", []), mv("a2", []), mv("x", []), mv("a3", [])];
  const b = [mv("b1", []), mv("x", []), { id: "b2", Poster: "" }, mv("b3", [])];
  assert.deepEqual(app.mixForYou([a, b], ["a2"], 10).map(m => m.id), ["a1", "b1", "x", "a3", "b3"]);
  assert.deepEqual(app.mixForYou([a, b], [], 3).map(m => m.id), ["a1", "b1", "a2"]);
  assert.deepEqual(app.mixForYou([], [], 5), []);
});

test("[BL-PR-06] ข้อมูลส่วนตัวอยู่ในเครื่องเท่านั้น: เก็บแค่ชื่อประเภท แต้ม และรหัส IMDb ของหนัง ไม่มีชื่อ อีเมล หรือข้อความ", () => {
  fresh();
  app.recordTaste(mv("tt0110912", ["อาชญากรรม"], { Title: "Pulp Fiction", Plot: "..." }));
  const raw = JSON.parse(localStorage.getItem(app.TASTE_KEY));
  assert.deepEqual(Object.keys(raw).sort(), ["genres", "liked", "seen"]);
  assert.ok(!JSON.stringify(raw).includes("Pulp"));
});

test("[BL-PR-07] แถว For you ใช้ตัวกรองเดิมกับฐานข้อมูล: ทุกเรื่องเป็นประเภทที่ชอบ และไม่มีเรื่องที่เคยเปิด", async () => {
  fresh();
  const rows = makeMovies(1500, 7).map(r => ({ ...r, Poster: r.Poster || `https://img/${r.id}.jpg` }));
  await useDb(rows);
  const horror = rows.filter(r => r.Genre_for_cal === "สยองขวัญ");
  app.recordTaste(horror[0]);
  app.recordTaste(horror[1]);
  const row = app.forYouRow();
  assert.deepEqual(row.genres, ["สยองขวัญ"]);
  const lists = [];
  for (const g of row.genres) lists.push((await app.loadRanked(row.f.popular, null, F({ ...row.f, genre: g }))).movies);
  const out = app.mixForYou(lists, app.readTaste().seen, 18);
  assert.ok(out.length > 0);
  assert.ok(out.every(m => m.Genre_for_cal === "สยองขวัญ"));
  assert.ok(!out.some(m => m.id === horror[0].id || m.id === horror[1].id));
});
