// แบนเนอร์ (Hero) หมุนจาก For you 10 เรื่องแรก (HERO-PERS)
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, resetDom } from "../helpers/setup.mjs";

const h = app.__hooks;
const popular = Array.from({ length: 30 }, (_, i) => ({ id: "pop" + i, Poster: "p", Year: "2025", imdbVotes: 90000 + i }));
const ids = list => list.map(m => m.id);

function reset() {
  localStorage.clear();
  h.set("heroPersonal", []); h.set("heroPopular", popular); h.set("heroPool", popular);
  h.set("heroQueue", []); h.set("lastHeroId", null);
}
function show(m) { h.set("lastHeroId", m.id); return m.id; }   // สิ่งที่ setHero() ทำกับเรื่องที่หยิบได้

test("[BL-HF-01] กดชอบแล้วโหลดแถว For you → แบนเนอร์หมุนจาก 10 เรื่องแรกของแถวตามลำดับ วนใหม่โดยไม่ซ้ำเรื่องล่าสุด และไม่ทับสำรับหนังดังที่เก็บไว้", async () => {
  reset(); resetDom();
  const rows = makeMovies(1200, 11).map(r => ({ ...r, Poster: r.Poster || `https://img.example/${r.id}.jpg` }));
  await useDb(rows);
  app.rowState.clear(); app.homePending?.clear(); app.similarCache?.clear();
  reset();
  localStorage.setItem(app.HERO_QUEUE_KEY, JSON.stringify(["pop3", "pop4"]));
  // ตั้งประวัติตรง ๆ (toggleLike จะสั่งโหลดแถวเบื้องหลังซ้อนกับเทสต์ถัดไป)
  localStorage.setItem(app.TASTE_KEY, JSON.stringify({ genres: {}, seen: [], liked: [rows.find(r => r.Genre_for_cal === "สยองขวัญ").id] }));
  await app.loadHomeRow("foryou");
  const shown = [...document.getElementById("row-foryou").children].map(c => (c.innerHTML.match(/alt="([^"]*)"/) || [])[1]);
  const top10 = ids(app.heroPool);
  assert.equal(top10.length, app.HERO_PERSONAL);
  assert.deepEqual(app.heroPool.map(m => m.Title_EN || m.Title), shown.slice(0, 10).map(t => t.replace(/&amp;/g, "&")));
  const seq = Array.from({ length: 12 }, () => show(app.pickHero()));
  assert.deepEqual(seq.slice(0, 10), top10, "เรื่องที่ตรงที่สุดขึ้นก่อน");
  assert.deepEqual(seq.slice(10), top10.slice(0, 2), "ครบแล้ววนใหม่จากเรื่องแรก");
  assert.notEqual(seq[9], seq[10]);
  assert.deepEqual(JSON.parse(localStorage.getItem(app.HERO_QUEUE_KEY)), ["pop3", "pop4"]);
});

test("[BL-HF-02] ยังไม่มีประวัติ → แบนเนอร์ใช้หนังดังเหมือนเดิม; ล้างประวัติแล้ว → กลับเป็นหนังดัง", () => {
  reset();
  assert.ok(ids(popular).includes(show(app.pickHero())));
  const forYou = Array.from({ length: 12 }, (_, i) => ({ id: "fy" + i, Poster: "p" }));
  assert.equal(app.usePersonalHero(forYou), true);
  assert.deepEqual(ids(app.heroPool), ids(forYou.slice(0, 10)));
  assert.equal(app.usePersonalHero([]), true);
  assert.deepEqual(ids(app.heroPool), ids(popular));
  assert.ok(ids(popular).includes(show(app.pickHero())));
});

test("[BL-HF-03] (edge) For you มีเรื่องที่มีโปสเตอร์ไม่ถึง 2 เรื่อง → ใช้หนังดัง; ส่งรายการเดิมซ้ำ → ไม่รีเซ็ตสำรับ", () => {
  reset();
  assert.equal(app.usePersonalHero([{ id: "a", Poster: "p" }, { id: "b", Poster: "" }, null]), false);
  assert.deepEqual(ids(app.heroPool), ids(popular));
  const forYou = [{ id: "x1", Poster: "p" }, { id: "x2", Poster: "p" }, { id: "x3", Poster: "p" }];
  app.usePersonalHero(forYou);
  assert.equal(show(app.pickHero()), "x1");
  assert.equal(app.usePersonalHero(forYou.map(m => ({ ...m }))), false, "รายการเดิม");
  assert.equal(show(app.pickHero()), "x2", "ยังไล่ต่อจากเดิม");
});
