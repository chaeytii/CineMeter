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

// ซีรีส์ BL ภาษาไทยโหวตน้อย กับหนัง drama ภาษาอังกฤษที่ดังมาก (ประเภทเดียวกัน ยุคเดียวกัน)
const series = (id, title, lang, kw, votes, extra = {}) => ({
  id, Title_EN: title, Title_TH: "", Year: "2020", Genre_for_cal: "หนังชีวิต", Genres: ["หนังชีวิต"], MediaType: "ซีรีส์",
  Language: lang, Keyword: kw, imdbVotes: votes.toLocaleString("en-US"), Popularity: votes / 1000, imdbRating: "7.5", tmdbRating: 8.0,
  Audience_Average: 7.8, Poster: `https://img.example/${id}.jpg`, CollectionID: 0, Companies: [], ...extra,
});
const BL = "boys' love (bl), romance, university, lgbt, gay theme";
const thaiBL = ["Until We Meet Again", "2gether", "Bad Buddy", "KinnPorsche", "Love in the Air"].map((t, i) =>
  series(`tt80000${i}`, t, "th", BL, 2600 + i * 300));
const famousDrama = ["Big Drama", "Award Drama", "Hospital Drama", "Period Drama"].map((t, i) =>
  series(`tt81000${i}`, t, "en", "hospital, family, friendship", 1_500_000 - i * 1000, { Audience_Average: 8.9, Popularity: 300 }));

test("[BL-PL-05] กดชอบซีรีส์ BL ไทย → For you ขึ้นซีรีส์ BL ไทยก่อน แม้โหวตไม่ถึง 5,000 และหนัง drama ดัง ๆ ไม่แซงขึ้นมา", async () => {
  localStorage.clear(); resetDom();
  const base = makeMovies(1200, 11).map(r => ({ ...r, Poster: r.Poster || `https://img.example/${r.id}.jpg` }));
  await useDb([...base, ...thaiBL, ...famousDrama]);
  app.rowState.clear(); app.homePending?.clear(); app.similarCache?.clear();
  app.toggleLike(thaiBL[0]);
  const shown = await loadRow("foryou");
  const top4 = shown.slice(0, 4);
  assert.deepEqual([...top4].sort(), thaiBL.slice(1).map(m => m.Title_EN).sort(), shown.join(", "));
  assert.ok(app.forYouScore(thaiBL[0], thaiBL[1]) > app.forYouScore(thaiBL[0], famousDrama[0]));
});

test("[BL-PL-06] (edge) ยังไม่ได้ deploy index ภาษา → ยังได้ซีรีส์ภาษาเดียวกัน; เรื่องคล้ายไม่พอ → เติมด้วยหนังจากประเภทที่ชอบจนครบแถว", async () => {
  localStorage.clear(); resetDom();
  const base = makeMovies(1200, 11).map(r => ({ ...r, Poster: r.Poster || `https://img.example/${r.id}.jpg` }));
  await useDb([...base, ...thaiBL, ...famousDrama], { compositeIndex: false });
  app.rowState.clear(); app.homePending?.clear(); app.similarCache?.clear();
  app.toggleLike(thaiBL[0]);
  const shown = await loadRow("foryou");
  assert.ok(thaiBL.slice(1).every(m => shown.includes(m.Title_EN)), shown.join(", "));
  assert.equal(shown.length, app.ROW_SIZE);
  assert.equal(app.getLanguage({ Language: " TH " }), "th");
  assert.equal(app.getLanguage({}), "");
});
