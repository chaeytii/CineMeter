// ภาคต่อ + ค่ายผลิต (SIM-02): แถว "ภาคอื่นในชุดนี้" จาก CollectionID และ If you like… ที่รู้จักค่ายหนัง
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies } from "../helpers/setup.mjs";

const h = app.__hooks;
const titlesIn = el => el.children.map(c => (c.innerHTML.match(/alt="([^"]*)"/) || [])[1]);
const MARVEL = 420, AVENGERS = 86311;

const film = (id, title, year, extra = {}) => ({
  id, Title_EN: title, Title_TH: "", Year: String(year), Released: `${year}-05-01`, Genre_for_cal: "บู๊",
  MediaType: "ภาพยนตร์", imdbVotes: 1_000_000, Popularity: 80, imdbRating: "8.0", tmdbRating: 7.9,
  Audience_Average: 7.95, Poster: `https://img.example/${id}.jpg`, Plot: "Heroes assemble", Keywords: ["superhero", "team"],
  CollectionID: 0, CollectionName: "", Companies: [MARVEL], ...extra,
});
const avengers = [
  film("tt4154796", "Avengers: Endgame", 2019, { CollectionID: AVENGERS, CollectionName: "The Avengers Collection" }),
  film("tt0848228", "The Avengers", 2012, { CollectionID: AVENGERS, CollectionName: "The Avengers Collection" }),
  film("tt4154756", "Avengers: Infinity War", 2018, { CollectionID: AVENGERS, CollectionName: "The Avengers Collection" }),
  film("tt2395427", "Avengers: Age of Ultron", 2015, { CollectionID: AVENGERS, CollectionName: "The Avengers Collection" }),
];
const guardians = film("tt2015381", "Guardians of the Galaxy", 2014, { Genre_for_cal: "ตลก", CollectionID: 284433 });

async function franchiseDb(opts) {
  const rows = [...makeMovies(1200, 11), ...avengers, guardians];
  await useDb(rows, opts);
  h.set("lastOpenedMovie", null);
  return rows;
}

test("[BL-SM-01] เปิด The Avengers → แถวภาคอื่นในชุด เรียงตามปีฉาย เรื่องที่กำลังดูถูกไฮไลต์", async () => {
  await franchiseDb();
  const base = avengers[1];
  await app.renderCollectionRow(base);
  const sec = document.getElementById("collection-section");
  const grid = document.getElementById("collectionGrid");
  assert.equal(sec.style.display, "");
  assert.deepEqual(titlesIn(grid), ["The Avengers", "Avengers: Age of Ultron", "Avengers: Infinity War", "Avengers: Endgame"]);
  assert.ok(grid.children[0].classList.contains("is-current"));
  assert.ok(!grid.children[1].classList.contains("is-current"));
  assert.match(document.getElementById("collection-title").innerText, /The Avengers Collection/);
});

test("[BL-SM-02] (edge) ไม่อยู่ชุดไหน / CollectionID = 0 / ชุดที่มีแค่เรื่องเดียว / ผู้ใช้เปิดเรื่องอื่นระหว่างรอ → ไม่แสดงแถว", async () => {
  await franchiseDb();
  const sec = document.getElementById("collection-section");
  for (const base of [film("tt9000001", "Solo", 2020), { ...film("tt9000002", "Old", 2001), CollectionID: undefined }, guardians]) {
    await app.renderCollectionRow(base);
    assert.equal(sec.style.display, "none", base.Title_EN);
    assert.equal(document.getElementById("collectionGrid").children.length, 0, base.Title_EN);
  }
  h.set("lastOpenedMovie", avengers[0]);           // เปิด Endgame ไปแล้ว ผลของ The Avengers มาช้า
  await app.renderCollectionRow(avengers[1]);
  assert.equal(sec.style.display, "none");
});

test("[BL-SM-03] ค่ายผลิตเดียวกันได้คะแนนเพิ่ม; ข้อมูลค่าย/ชุดที่ผิดรูปแบบไม่นับ", () => {
  const base = film("tt1", "Base", 2012);
  const same = film("tt2", "Same", 2012), other = film("tt3", "Other", 2012, { Companies: [7] });
  assert.equal(app.companyOverlap(base, same), 1);
  assert.equal(app.companyOverlap(base, other), 0);
  assert.ok(app.preScore(base, same) > app.preScore(base, other));
  assert.deepEqual(app.getCompanies({ Companies: [420, "420", null, -1, 2.5, 3] }), [420, 3]);
  assert.deepEqual(app.getCompanies({ Companies: "420" }), []);
  assert.equal(app.sameCollection({ CollectionID: 0 }, { CollectionID: 0 }), false);
  assert.equal(app.sameCollection({ CollectionID: "86311" }, { CollectionID: 86311 }), true);
  assert.equal(app.getCollectionId({ CollectionID: "N/A" }), 0);
});

test("[BL-SM-04] คัดหนังที่คนรู้จัก: ตัดเรื่องที่โหวตน้อยกว่า 20% ของต้นทาง (ขั้นต่ำ 5,000) เฉพาะเมื่อยังเหลือ ≥ 8 เรื่อง", () => {
  const base = { imdbVotes: 1_000_000 };
  const known = Array.from({ length: 9 }, (_, i) => ({ id: "k" + i, imdbVotes: 200_000 + i }));
  const obscure = Array.from({ length: 5 }, (_, i) => ({ id: "o" + i, imdbVotes: 900 + i }));
  assert.deepEqual(app.keepFamiliar(base, [...obscure, ...known]).map(m => m.id), known.map(m => m.id));
  const few = [...obscure, ...known.slice(0, 3)];
  assert.equal(app.keepFamiliar(base, few).length, few.length, "เหลือน้อยเกินไป ใช้รายการเดิม");
  const small = { imdbVotes: 2_000 };                 // หนังต้นทางโหวตน้อย → ใช้ขั้นต่ำ 5,000
  const mixed = [...Array.from({ length: 8 }, (_, i) => ({ id: "m" + i, imdbVotes: 5_000 })), { id: "x", imdbVotes: 4_999 }];
  assert.deepEqual(app.keepFamiliar(small, mixed).map(m => m.id), mixed.slice(0, 8).map(m => m.id));
});

test("[BL-SM-05] If you like…: ดึงหนังค่ายเดียวกันมาเป็นตัวเลือกแม้ต่างประเภท และไม่ซ้ำเรื่องในชุดเดียวกัน", async () => {
  await franchiseDb();
  const pool = await app.buildCandidatePool(avengers[1]);
  const ids = new Set(pool.map(m => m.id));
  assert.ok(ids.has(guardians.id), "Guardians (ประเภทตลก ค่าย Marvel) ต้องอยู่ในตัวเลือก");
  for (const m of avengers) assert.ok(!ids.has(m.id), m.Title_EN);

  let payload = null;
  h.setGemini(async ({ contents }) => {
    payload = JSON.parse(contents[0].parts[0].text);
    return JSON.stringify({ summary: "ทีมฮีโร่", picks: payload.candidates.slice(0, 6).map(c => ({ id: c.id, tag: "t" })) });
  });
  await app.fetchSimilarMovies(avengers[1]);
  const g = payload.candidates.find(c => c.id === guardians.id);
  assert.ok(g, "Guardians ผ่านเข้ารอบ 24 เรื่องที่ส่งให้ AI");
  assert.equal(g.sameStudio, true);
  assert.ok(payload.candidates.filter(c => c.id !== guardians.id).every(c => c.sameStudio === false));
  const shown = titlesIn(document.getElementById("suggestedGrid"));
  assert.ok(!shown.some(t => /Avengers/.test(t)), shown.join(", "));
});

test("[BL-SM-06] ตัวเลือกประเภท+ยุคเดียวกันเรียงจากโหวตมากก่อน; ไม่มี composite index ก็ยังได้ตัวเลือก (fallback)", async () => {
  // หนังบู๊ปี 2012 ที่แทบไม่มีคนรู้จัก 100 เรื่อง รหัสเอกสารมาก่อน — ถ้าไม่เรียงตามโหวต 60 เรื่องแรกจะเป็นกลุ่มนี้ทั้งหมด
  const obscure = Array.from({ length: 100 }, (_, i) => film(`tt00${String(i).padStart(5, "0")}`, `Obscure ${i}`, 2012,
    { imdbVotes: 600 + i, Popularity: 1, Companies: [] }));
  const star = film("tt9999990", "Famous Action", 2013, { Companies: [], Keywords: ["heist"] });
  const rows = [...makeMovies(1200, 11), ...avengers, guardians, ...obscure, star];
  await useDb(rows);
  const base = film("tt9100000", "Base Action", 2012, { Companies: [] });
  const pool = await app.buildCandidatePool(base);
  assert.ok(pool.some(m => m.id === star.id), "เรื่องที่โหวตมากในกลุ่มต้องติดมาด้วย");
  assert.ok(pool.filter(m => m.Title_EN.startsWith("Obscure")).length < 60);

  await useDb(rows, { compositeIndex: false });
  const fallback = await app.buildCandidatePool(base);
  assert.ok(fallback.length >= 8, `fallback=${fallback.length}`);
});
