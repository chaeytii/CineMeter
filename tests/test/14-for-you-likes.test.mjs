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

test("[BL-PL-07] เมล็ดของ For you = 3 เรื่องล่าสุดที่ชอบ + สุ่ม 2 เรื่องจากที่ชอบก่อนหน้า ไม่ซ้ำกัน สุ่มครั้งเดียวจนกว่ารายการจะเปลี่ยน", () => {
  h.set("olderPick", { key: "", ids: [] });
  const liked = ["n1", "n2", "n3", "o1", "o2", "o3", "o4"];
  const seq = [0.99, 0.0];
  const picked = app.pickOlderLikes(liked, () => seq.shift());
  assert.deepEqual(picked, ["o4", "o1"]);
  assert.deepEqual(app.pickOlderLikes(liked, () => 0.5), ["o4", "o1"], "รายการเดิม ใช้ผลสุ่มเดิม");
  const again = app.pickOlderLikes(["n0", ...liked], () => 0);
  assert.deepEqual(again, ["n3", "o1"], "กดชอบเรื่องใหม่ -> สุ่มใหม่จากเรื่องที่เก่ากว่า 3 เรื่องล่าสุด");
  assert.deepEqual(app.pickOlderLikes(["a", "b", "c"]), [], "ชอบไม่เกิน 3 เรื่อง -> ไม่มีเรื่องเก่าให้สุ่ม");
  assert.deepEqual(app.pickOlderLikes(["a", "b", "c", "d"]), ["d"]);

  localStorage.clear();
  localStorage.setItem(app.TASTE_KEY, JSON.stringify({ genres: { "บู๊": 9 }, seen: [], liked }));
  const seeds = app.forYouRow().seeds;
  assert.deepEqual(seeds.slice(0, 3), ["n1", "n2", "n3"]);
  assert.equal(seeds.length, 5);
  assert.equal(new Set(seeds).size, 5);
  assert.ok(seeds.slice(3).every(id => liked.slice(3).includes(id)));
});

test("[BL-PL-08] กดชอบ Iron Man ไว้ก่อน แล้วกดชอบซีรีส์ BL 3 เรื่อง → For you ยังมีหนังแนว Iron Man ปนกับซีรีส์ BL", async () => {
  localStorage.clear(); resetDom();
  const base = makeMovies(1200, 11).map(r => ({ ...r, Poster: r.Poster || `https://img.example/${r.id}.jpg` }));
  await useDb([...base, ironMan, ...studio, ...thaiBL, ...famousDrama]);
  app.rowState.clear(); app.homePending?.clear(); app.similarCache?.clear();
  h.set("olderPick", { key: "", ids: [] });
  app.toggleLike(ironMan);
  for (const m of thaiBL.slice(0, 3)) app.toggleLike(m);
  assert.deepEqual(app.forYouRow().seeds, [thaiBL[2].id, thaiBL[1].id, thaiBL[0].id, ironMan.id]);
  const shown = await loadRow("foryou");
  assert.ok(thaiBL.slice(3).some(m => shown.includes(m.Title_EN)), shown.join(", "));
  assert.ok(studio.some(m => shown.includes(m.Title_EN)), shown.join(", "));
});

// PERS-05: เรียงทั้งแถวด้วยคะแนนรวม แทนการหยิบสลับทีละเรื่องที่ชอบ
const kwFilm = (id, kw, extra = {}) => film(id, id, { Keywords: kw, Companies: [], Genres: ["ดราม่า"], Genre_for_cal: "ดราม่า", ...extra });

test("[BL-PL-09] rankForYou: หนังที่คล้ายเรื่องที่ชอบสองเรื่องขึ้นก่อนหนังที่คล้ายเรื่องเดียว แม้มาจากท้ายรายการ", () => {
  const seedA = kwFilm("sa", ["space", "robot", "war"]);
  const seedB = kwFilm("sb", ["space", "family", "music"]);
  const onlyA = kwFilm("onlyA", ["robot", "war"]);
  const both = kwFilm("both", ["space", "robot", "family"]);
  const onlyB = kwFilm("onlyB", ["family", "music"]);
  // แบบเดิม (สลับทีละเรื่อง) ได้ onlyA, onlyB ก่อน both
  assert.deepEqual(app.mixForYou([[onlyA, both], [onlyB, both]], [], 3).map(m => m.id), ["onlyA", "onlyB", "both"]);
  const out = app.rankForYou([seedA, seedB], [[onlyA, both], [onlyB, both]], [], 3).map(m => m.id);
  assert.equal(out[0], "both", out.join(", "));
  assert.equal(new Set(out).size, 3);
});

test("[BL-PL-10] rankForYou: ความคล้ายเท่ากัน → เรื่องที่คนดูให้คะแนนสูงกว่าขึ้นก่อน", () => {
  const seed = kwFilm("s", ["heist", "crime"]);
  const low = kwFilm("low", ["heist", "crime"], { Audience_Average: 5.5 });
  const high = kwFilm("high", ["heist", "crime"], { Audience_Average: 8.5 });
  assert.deepEqual(app.rankForYou([seed], [[low, high]], [], 2).map(m => m.id), ["high", "low"]);
});

test("[BL-PL-11] (edge) rankForYou: เรื่องที่ชอบแนวหนึ่งคะแนนสูงกว่ามาก อีกแนวยังได้ช่องต้นแถว; แถวไม่เต็ม → ได้ครบ, ข้ามเรื่องที่เคยเปิด/ไม่มีโปสเตอร์", () => {
  const seedA = kwFilm("sa", ["zombie", "virus", "city"]);
  const seedB = kwFilm("sb", ["chef", "food", "paris"]);
  const zs = Array.from({ length: 6 }, (_, i) => kwFilm(`z${i}`, ["zombie", "virus", "city"], { Audience_Average: 9 }));
  const fs = Array.from({ length: 2 }, (_, i) => kwFilm(`f${i}`, ["chef"], { Audience_Average: 5 }));
  const out = app.rankForYou([seedA, seedB], [zs, fs], [], 4).map(m => m.id);
  assert.ok(out.some(id => id.startsWith("f")), out.join(", "));
  assert.equal(out[0][0], "z", "เรื่องที่ตรงกว่ายังขึ้นก่อน");
  const all = app.rankForYou([seedA, seedB], [zs, fs], ["z0"], 20).map(m => m.id);
  assert.equal(all.length, 7, "แถวไม่เต็ม → ได้ทุกเรื่อง (ข้าม z0 ที่เคยเปิด)");
  assert.ok(!all.includes("z0"));
  assert.deepEqual(app.rankForYou([seedA], [[{ ...zs[1], Poster: "" }]], [], 5), []);
  assert.deepEqual(app.rankForYou([], [], [], 5), []);
});

test("[BL-PL-12] keyword ที่เกือบทุกเรื่องมี (เช่น anime) นับน้อยกว่าคำเฉพาะ → หนังที่ตรงคำเฉพาะขึ้นก่อน", () => {
  const seed = kwFilm("dora", ["anime", "time travel", "gadget"]);
  const shonen = Array.from({ length: 8 }, (_, i) => kwFilm(`sh${i}`, ["anime", "ninja", "sword"], { Audience_Average: 8.5 }));
  const timeTravel = kwFilm("tt", ["time travel", "family"], { Audience_Average: 7 });
  const w = app.keywordWeights([...shonen, timeTravel, seed]);
  assert.ok(w("anime") < 0.1, String(w("anime")));
  assert.ok(w("time travel") > 5 * w("anime") && w("time travel") <= 1, String(w("time travel")));
  assert.ok(w("never seen") > w("time travel"), "คำที่ไม่มีในกอง = หายากที่สุด");
  assert.equal(app.rankForYou([seed], [[...shonen, timeTravel]], [], 3)[0].id, "tt");
  assert.equal(app.keywordOverlap(seed, shonen[0]), app.keywordOverlap(seed, timeTravel), "แบบเดิมนับ anime เท่ากับ time travel");
  assert.ok(app.weightedKeywordOverlap(seed, timeTravel, w) > 5 * app.weightedKeywordOverlap(seed, shonen[0], w));
  assert.equal(app.forYouScore(seed, timeTravel), app.forYouScore(seed, shonen[0]), "ไม่ส่ง weight = คะแนนแบบเดิม (similarToLiked ไม่เปลี่ยน)");
});

test("[BL-PL-13] ชอบ 3 แนวต่างกัน → 6 ช่องแรกมีครบทั้ง 3 แนว แม้แนวหนึ่งคะแนนสูงกว่ามาก", () => {
  const seeds = [kwFilm("s1", ["robot", "space"]), kwFilm("s2", ["ghost", "curse"]), kwFilm("s3", ["greek", "voyage"])];
  const strong = Array.from({ length: 10 }, (_, i) => kwFilm(`a${i}`, ["robot", "space"], { Audience_Average: 9 }));
  const ghost = Array.from({ length: 5 }, (_, i) => kwFilm(`g${i}`, ["ghost"], { Audience_Average: 6 }));
  const myth = Array.from({ length: 5 }, (_, i) => kwFilm(`m${i}`, ["voyage"], { Audience_Average: 6 }));
  const first6 = app.rankForYou(seeds, [strong, ghost, myth], [], 18).slice(0, 6).map(m => m.id[0]);
  assert.deepEqual([...new Set(first6)].sort(), ["a", "g", "m"], first6.join(""));
});

test("[BL-PL-14] (edge) ภาคเดียวกันขึ้นเรื่องเดียว: ชื่อหลักเดียวกัน หรือ CollectionID เดียวกัน; ชื่อสั้นไม่ถึง 4 ตัวอักษรไม่นับ; แถวไม่เต็ม → ภาคที่ซ้ำต่อท้าย", () => {
  const t = (title, extra = {}) => ({ Title_EN: title, CollectionID: 0, ...extra });
  assert.ok(app.sameFranchise(t("Naruto"), t("Naruto: Shippuden")));
  assert.ok(app.sameFranchise(t("Bleach: Thousand-Year Blood War"), t("Bleach")));
  assert.ok(app.sameFranchise(t("Hunter x Hunter"), t("Hunter x Hunter")));
  assert.ok(app.sameFranchise(t("Spider-Man"), t("Spider-Man: No Way Home")));
  assert.ok(app.sameFranchise(t("Alien", { CollectionID: 8091 }), t("Prometheus", { CollectionID: 8091 })));
  assert.ok(!app.sameFranchise(t("It"), t("It Follows")), "ชื่อสั้นเกินไป");
  assert.ok(!app.sameFranchise(t("The Odyssey"), t("The Office")));
  assert.ok(!app.sameFranchise(t("Naruto"), t("Narutopia")));
  assert.equal(app.titleRoot(t("Bleach: Thousand-Year Blood War")), "bleach");

  const seed = kwFilm("s", ["ninja", "shinobi"]);
  const naruto = kwFilm("n1", ["ninja", "shinobi"], { Title_EN: "Naruto", Audience_Average: 9 });
  const shippuden = kwFilm("n2", ["ninja", "shinobi"], { Title_EN: "Naruto: Shippuden", Audience_Average: 8.9 });
  const other = kwFilm("o1", ["ninja"], { Title_EN: "Ninja Scroll", Audience_Average: 6 });
  assert.deepEqual(app.rankForYou([seed], [[naruto, shippuden, other]], [], 2).map(m => m.id), ["n1", "o1"]);
  assert.deepEqual(app.rankForYou([seed], [[naruto, shippuden, other]], [], 5).map(m => m.id), ["n1", "o1", "n2"]);
});
