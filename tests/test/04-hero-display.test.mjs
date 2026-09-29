// Hero banner rotation + title/number display rules
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";

const h = app.__hooks;
const pool = Array.from({ length: 60 }, (_, i) => ({ id: "h" + String(i).padStart(2, "0"), Poster: "p", Year: "2025", imdbVotes: 50000 + i }));

function show(m) {           // what setHero() does with the picked movie
  h.set("lastHeroId", m.id);
  localStorage.setItem(app.HERO_STORAGE_KEY, m.id);
}

test("[BL-HR-01] สุ่ม Hero 10,000 ครั้ง: ไม่มีเรื่องเดิมติดกันเลย และทุกเรื่องได้ขึ้นภายใน 2 รอบสำรับ", () => {
  localStorage.clear();
  h.set("heroPool", pool); h.set("heroQueue", []); h.set("lastHeroId", null);
  const seq = [];
  for (let i = 0; i < 10000; i++) { const m = app.pickHero(); seq.push(m.id); show(m); }
  let repeats = 0;
  for (let i = 1; i < seq.length; i++) if (seq[i] === seq[i - 1]) repeats++;
  assert.equal(repeats, 0);
  const W = pool.length * 2;
  for (let s = 0; s + W <= seq.length; s += 97) assert.equal(new Set(seq.slice(s, s + W)).size, pool.length, `window@${s}`);
});

test("[BL-HR-02] รีเฟรชหน้า (อ่านสำรับที่เหลือจาก localStorage): ไม่ได้เรื่องล่าสุดซ้ำ และไม่ซ้ำเรื่องที่แสดงไปแล้วในรอบนี้", () => {
  localStorage.clear();
  h.set("heroPool", pool); h.set("heroQueue", []); h.set("lastHeroId", null);
  const shown = [];
  for (let i = 0; i < 25; i++) { const m = app.pickHero(); shown.push(m.id); show(m); }
  // --- simulate page reload ---
  h.set("heroQueue", app.readStore(app.HERO_QUEUE_KEY, []));
  h.set("lastHeroId", localStorage.getItem(app.HERO_STORAGE_KEY));
  const after = [];
  const remaining = app.__hooks.get("heroQueue").length;
  for (let i = 0; i < remaining; i++) { const m = app.pickHero(); after.push(m.id); show(m); }
  assert.notEqual(after[0], shown[shown.length - 1]);
  assert.equal(after.filter(id => shown.includes(id)).length, 0);
  assert.equal(new Set([...shown, ...after]).size, shown.length + after.length);
});

test("[BL-HR-03] pool ของ Hero: มีโปสเตอร์ ออกใน 5 ปีล่าสุด และโหวต ≥ 20,000 (ผ่อนเกณฑ์เมื่อได้ไม่ถึง 20 เรื่อง)", async () => {
  const rows = makeMovies(3000, 31);
  await useDb(rows);
  const heroPool = await app.buildHeroPool();
  assert.ok(heroPool.length >= 20);
  assert.ok(heroPool.every(m => m.Poster && +m.Year >= 2022 && +m.Year <= 2026 && m.imdbVotes >= 20000));
  console.log(`[BL-HR-03] pool=${heroPool.length} (criteria: poster, 2022–2026, votes ≥ ${app.HERO_MIN_VOTES})`);
});

test("[BL-HR-04] กดฟิลเตอร์กี่ครั้งก็ไม่ทำให้ Hero เปลี่ยน (Hero แยกจากฟิลเตอร์)", async () => {
  await useDb(makeMovies(800, 32));
  h.set("lastHeroId", "HERO-X"); h.set("heroQueue", ["h01", "h02"]);
  for (const g of ["สยองขวัญ", "ตลก", "", "บู๊"]) { app.activeFilters.genre = g; await app.fetchMovies(); }
  assert.equal(h.get("lastHeroId"), "HERO-X");
  assert.deepEqual(h.get("heroQueue"), ["h01", "h02"]);
});

// ---------------- display rules ----------------
const html = readFileSync(new URL(process.env.CINEMETER_HTML || "../../cinemeter-v7_8.html", import.meta.url), "utf8");
const rhs = html.match(/getElementById\("d-thai"\)\.innerText = ([^;]+);/)[1];
const thaiLine = new Function("thaiTitle", "titleEN", `return ${rhs};`);   // verbatim expression from openDetail()

test("[BL-DP-01] ชื่อไทยในหน้า detail: ไม่มีชื่อไทย หรือสะกดเหมือนชื่ออังกฤษ → ซ่อน", () => {
  assert.equal(thaiLine("", "Dune"), "");
  assert.equal(thaiLine("Dune", "Dune"), "");
  assert.equal(thaiLine("ดูน", "Dune"), "ดูน");
});
test("[BL-DP-02] ชื่อไทยต่างกันแค่ตัวพิมพ์/ช่องว่าง ('dune ' vs 'Dune') → ต้องซ่อนเหมือนกัน", () => {
  assert.equal(thaiLine("dune ", "Dune"), "");
  assert.equal(thaiLine("DUNE", "Dune"), "");
});
test("[BL-DP-03] ชื่ออังกฤษ: ตัดวงเล็บชื่อไทย/ชื่อซ้ำออก", () => {
  assert.equal(app.getEnglishTitle({ Title: "Avatar (อวตาร)" }), "Avatar");
  assert.equal(app.getEnglishTitle({ Title: "Avatar (Avatar)" }), "Avatar");
  assert.equal(app.getEnglishTitle({ Title_EN: "Dune: Part Two" }), "Dune: Part Two");
});
test("[BL-DP-04] ชื่ออังกฤษที่มีวงเล็บเป็นส่วนหนึ่งของชื่อจริง ต้องไม่ถูกตัด", () => {
  assert.equal(app.getEnglishTitle({ Title_EN: "(500) Days of Summer" }), "(500) Days of Summer");
  assert.equal(app.getEnglishTitle({ Title_EN: "Birdman or (The Unexpected Virtue of Ignorance)" }), "Birdman or (The Unexpected Virtue of Ignorance)");
});
test("[BL-DP-05] จำนวนโหวต: 999 / 12K / 1M / 1.3M และ 999,999 ต้องแสดง 1M ไม่ใช่ 1000K", () => {
  assert.equal(app.formatVotes(999), "999");
  assert.equal(app.formatVotes(12345), "12K");
  assert.equal(app.formatVotes(1000000), "1M");
  assert.equal(app.formatVotes(1250000), "1.3M");
  assert.equal(app.formatVotes(999999), "1M");
  assert.equal(app.formatVotes(999600), "1M");
});
test("[BL-DP-06] แปลงตัวเลขจากข้อความ: '1,234,567' '85%' 'N/A' และปีของซีรีส์ '2019–2023'", () => {
  assert.equal(app.toNum("1,234,567"), 1234567);
  assert.equal(app.toNum("85%"), 85);
  assert.equal(app.toNum("N/A"), 0);
  assert.equal(app.getYear({ Year: "2019–2023" }), 2019);
  assert.equal(app.getYear({ Year: 2024 }), 2024);
  assert.equal(app.getYear({}), 0);
});
test("[BL-DP-07] Keyword รองรับทั้ง Array และข้อความคั่นด้วย , | / ;", () => {
  assert.deepEqual(app.getKeywords({ Keywords: ["space", " war "] }), ["space", "war"]);
  assert.deepEqual(app.getKeywords({ keywords: "space, war|time travel" }), ["space", "war", "time travel"]);
  assert.deepEqual(app.getKeywords({}), []);
});
test("[SEC-01] การ์ดหนัง: ค่า Poster ที่มีเครื่องหมายคำพูด ต้องไม่หลุดออกจาก attribute (กัน HTML injection)", () => {
  const card = app.buildCard({ id: "x", Title_EN: "T", Poster: 'x.jpg" onload="alert(1)' }, "");
  assert.ok(!/onload="alert\(1\)"/.test(card.innerHTML), card.innerHTML.slice(0, 160));
});
test("[SEC-02] ข้อความชื่อหนังถูก escape ก่อนใส่ HTML", () => {
  const card = app.buildCard({ id: "x", Title_EN: "<img src=x onerror=alert(1)>", Poster: "p.jpg" }, "");
  assert.ok(!card.innerHTML.includes("<img src=x"));
});
