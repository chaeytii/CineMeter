// For you จากเรื่องที่กดชอบ + แถว Your likes (PERS-02)
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, resetDom } from "../helpers/setup.mjs";

const h = app.__hooks;
const titlesIn = el => el.children.map(c => (c.innerHTML.match(/alt="([^"]*)"/) || [])[1]);
const MARVEL = 420;
const film = (id, title, extra = {}) => ({
  id, Title_EN: title, Title_TH: "", Year: "2012", Released: "2012-05-01", Genre_for_cal: "บู๊", Genres: ["บู๊", "นิยายวิทยาศาสตร์"],
  MediaType: "ภาพยนตร์", imdbVotes: 900_000, Popularity: 60, imdbRating: "6.6", tmdbRating: 6.5, Audience_Average: 6.5,
  Poster: `https://img.example/${id}.jpg`, Keywords: ["superhero", "marvel"], CollectionID: 0, Companies: [MARVEL], ...extra,
});
const ironMan = film("tt0371746", "Iron Man", { Year: "2008" });
const studio = ["Thor", "Black Panther", "Doctor Strange", "Ant-Man"].map((t, i) =>
  film(`tt09${i}0000`, t, { Genre_for_cal: "ตลก", Genres: ["ตลก", "ผจญ"], Year: String(2011 + i) }));

async function setup() {
  localStorage.clear();
  resetDom();
  const base = makeMovies(1200, 11).map(r => ({ ...r, Poster: r.Poster || `https://img.example/${r.id}.jpg` }));
  const rows = [...base, ironMan, ...studio];
  await useDb(rows);
  app.rowState.clear();
  app.homePending?.clear();
  app.similarCache?.clear();
  return rows;
}

async function loadRow(key) {
  app.rowState.delete(key);
  app.homePending?.delete(key);
  await app.loadHomeRow(key);
  return titlesIn(document.getElementById("row-" + key));
}

test("[BL-PL-01] กดชอบ Iron Man → For you เปลี่ยน และมีหนังค่ายเดียวกัน (Marvel) ที่ไม่ได้อยู่ในประเภทที่ชอบ", async () => {
  const rows = await setup();
  const horror = rows.filter(r => r.Genre_for_cal === "สยองขวัญ");
  app.recordTaste(horror[0]);
  app.recordTaste(horror[1]);
  const before = await loadRow("foryou");
  assert.ok(before.length > 0);
  assert.ok(!studio.some(m => before.includes(m.Title_EN)));

  app.toggleLike(ironMan);
  const after = await loadRow("foryou");
  assert.notDeepEqual(after, before);
  const marvel = studio.filter(m => after.includes(m.Title_EN));
  assert.ok(marvel.length >= 2, after.join(", "));
});

test("[BL-PL-02] แถว For you โหลดใหม่ทุกครั้งที่ประวัติเปลี่ยน และไม่มีเรื่องที่เปิดดูหรือกดชอบแล้ว", async () => {
  await setup();
  app.toggleLike(ironMan);
  const s1 = app.forYouRow().sig;
  app.recordTaste(studio[0]);                 // เปิดดู Thor
  const s2 = app.forYouRow().sig;
  app.toggleLike(studio[1]);                  // กดชอบ Black Panther
  const s3 = app.forYouRow().sig;
  assert.ok(s1 !== s2 && s2 !== s3, [s1, s2, s3].join(" / "));
  const shown = await loadRow("foryou");
  for (const m of [ironMan, studio[0], studio[1]]) assert.ok(!shown.includes(m.Title_EN), m.Title_EN);
  assert.ok(shown.length > 0);
  assert.ok(app.homeRowsNow().findIndex(r => r.key === "liked") === 1, "Your likes อยู่ใต้ For you");
});

test("[BL-PL-03] แถว Your likes: ยังไม่เคยกดชอบ = ไม่มีแถว; เรียงใหม่สุดก่อน รวมข้อมูลเก่าที่มีแค่รหัส; ยกเลิกชอบแล้วหาย", async () => {
  await setup();
  assert.equal(app.likedRow(), null);
  assert.ok(!app.homeRowsNow().some(r => r.key === "liked"));
  // ข้อมูลในเครื่องแบบเดิม (PERS-01) เก็บแค่รหัสหนัง
  localStorage.setItem(app.TASTE_KEY, JSON.stringify({ genres: { "บู๊": 3 }, seen: [], liked: [studio[0].id] }));
  app.toggleLike(ironMan);
  app.toggleLike(studio[2]);
  assert.deepEqual(app.likedRow().ids, [studio[2].id, ironMan.id, studio[0].id]);
  assert.deepEqual(await loadRow("liked"), ["Doctor Strange", "Iron Man", "Thor"]);
  app.toggleLike(ironMan);                    // ยกเลิกชอบ
  assert.deepEqual(await loadRow("liked"), ["Doctor Strange", "Thor"]);
});

test("[BL-PL-04] (edge) รหัสที่ไม่มีในฐานข้อมูล / อ่านผิดพลาด → ข้ามเรื่องนั้น แถวยังแสดงได้", async () => {
  await setup();
  const realGetDoc = (await useDb([...makeMovies(1200, 11).map(r => ({ ...r, Poster: r.Poster || `https://img.example/${r.id}.jpg` })), ironMan, ...studio])).getDoc;
  h.setGetDoc(async ref => {
    if (ref.path.endsWith("/tt-broken")) throw new Error("unavailable");
    return realGetDoc(ref);
  });
  localStorage.setItem(app.TASTE_KEY, JSON.stringify({ genres: { "บู๊": 6 }, seen: [], liked: ["tt-missing", "tt-broken", ironMan.id] }));
  assert.deepEqual(await loadRow("liked"), ["Iron Man"]);
  const fy = await loadRow("foryou");
  assert.ok(fy.length >= 10, fy.join(", "));
  assert.ok(studio.some(m => fy.includes(m.Title_EN)), "ยังได้หนังคล้าย Iron Man");
});
