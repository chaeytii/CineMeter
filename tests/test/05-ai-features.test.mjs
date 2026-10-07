// "If you like…" (LLM similarity) + Hybrid RAG chatbot — LLM replaced by a scripted fake
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";

const h = app.__hooks;
const titlesIn = el => el.children.map(c => (c.innerHTML.match(/alt="([^"]*)"/) || [])[1]);

// ---------------- similarity scoring ----------------
test("[AI-SM-01] คะแนนความใกล้เคียง: keyword / ประเภท / ยุคสมัย", () => {
  assert.equal(app.keywordOverlap({ Keywords: ["space", "war", "robot"] }, { Keywords: ["space", "war", "love"] }), 2 / 3);
  assert.equal(app.genreOverlap({ Genres: ["บู๊", "ผจญ", "นิยายวิทยาศาสตร์"] }, { Genres: ["บู๊", "ผจญ"] }), 2 / 3);
  assert.equal(app.eraCloseness({ Year: "2024" }, { Year: "2018" }), 1);          // ≤ 7 ปี = ยุคเดียวกัน
  assert.ok(app.eraCloseness({ Year: "2024" }, { Year: "1990" }) < 0.1);
  const base = { Year: "2024", Keywords: ["space"], Genres: ["นิยายวิทยาศาสตร์"] };
  assert.ok(app.preScore(base, { Year: "2023", Keywords: ["space"], Genres: ["นิยายวิทยาศาสตร์"], imdbVotes: 1000 }) >
            app.preScore(base, { Year: "1985", Keywords: ["space"], Genres: ["นิยายวิทยาศาสตร์"], imdbVotes: 1000 }));
});

async function similarSetup() {
  const rows = makeMovies(1500, 41);
  const fdb = await useDb(rows);
  const base = { ...rows.find(m => m.Year === "2025" && m.Genre_for_cal === "สยองขวัญ" && m.Poster) };
  return { rows, base, fdb };
}

test("[AI-SM-02] LLM ตอบ id ที่ไม่มีจริง → ถูกตัดทิ้ง, ได้ไม่เกิน 6 เรื่อง", async () => {
  const { rows, base } = await similarSetup();
  h.setGemini(async ({ contents }) => {
    const payload = JSON.parse(contents[0].parts[0].text);
    const ids = payload.candidates.map(c => c.id);
    return JSON.stringify({ summary: "โทนหลอนคล้ายกัน", picks: [{ id: "tt0000000", tag: "มั่ว" }, ...ids.slice(0, 7).map(id => ({ id, tag: "x" }))] });
  });
  await app.fetchSimilarMovies(base);
  const grid = document.getElementById("suggestedGrid");
  const shown = titlesIn(grid);
  assert.ok(shown.length > 0 && shown.length <= 6, `shown=${shown.length}`);
  assert.ok(!shown.includes(undefined));
  assert.equal(document.getElementById("suggested-note").innerText, "โทนหลอนคล้ายกัน");
});

test("[AI-SM-03] LLM เลือกหนังต่างยุคมาเกินครึ่ง → ระบบสลับเป็นหนังยุคเดียวกันให้เหลือ ≥ 4 ใน 6 เรื่อง", async () => {
  const { rows, base } = await similarSetup();
  h.setGemini(async ({ contents }) => {
    const payload = JSON.parse(contents[0].parts[0].text);
    const old = payload.candidates.filter(c => Math.abs(+c.year - 2025) > 10).map(c => c.id);
    const recent = payload.candidates.filter(c => Math.abs(+c.year - 2025) <= 10).map(c => c.id);
    return JSON.stringify({ summary: "s", picks: [...old.slice(0, 5), ...recent.slice(0, 1)].map(id => ({ id, tag: "t" })) });
  });
  await app.fetchSimilarMovies(base);
  const shown = titlesIn(document.getElementById("suggestedGrid"));
  const byTitle = new Map(rows.map(m => [app.getEnglishTitle(m), m]));
  const sameEra = shown.filter(t => Math.abs(+byTitle.get(t).Year - 2025) <= 10).length;
  console.log(`[AI-SM-03] shown=${shown.length} sameEra=${sameEra}`);
  assert.ok(sameEra >= Math.min(4, shown.length), `sameEra=${sameEra}/${shown.length}`);
});

test("[AI-SM-04] LLM ใช้ไม่ได้ → ใช้การจัดอันดับสำรอง (keyword/ประเภท/ยุค) และบอกผู้ใช้", async () => {
  const { base } = await similarSetup();
  h.setGemini(async () => { throw new Error("503"); });
  await app.fetchSimilarMovies(base);
  assert.ok(titlesIn(document.getElementById("suggestedGrid")).length > 0);
  assert.match(document.getElementById("suggested-note").innerText, /จัดอันดับจากธีม/);
});

// ---------------- chatbot ----------------
test("[AI-CB-01] Prompt ส่ง Gemini: role สลับ user/model เสมอ เริ่มและจบด้วย user (property test 2,000 ประวัติสุ่ม)", () => {
  let s = 7; const r = () => ((s = (s * 48271) % 2147483647) / 2147483647);
  for (let k = 0; k < 2000; k++) {
    const history = Array.from({ length: Math.floor(r() * 9) }, (_, i) => ({ role: r() < 0.5 ? "user" : "model", text: "m" + i }));
    const { contents } = app.buildChatPrompt({ userText: "q", history });
    assert.equal(contents[0].role, "user");
    assert.equal(contents[contents.length - 1].role, "user");
    for (let i = 1; i < contents.length; i++) assert.notEqual(contents[i].role, contents[i - 1].role);
  }
});

test("[AI-CB-02] ตอบ JSON ขาดท้าย (ยาวจนโดนตัด) → ยังดึงข้อความ reply ออกมาได้", () => {
  assert.equal(app.extractReply('{"reply":"บรรทัด 1\\nบรรทัด 2","pi').reply, "บรรทัด 1\nบรรทัด 2");
  assert.equal(app.extractReply("ข้อความธรรมดา").reply, "ข้อความธรรมดา");
  assert.deepEqual(app.parseJsonLoose('```json\n{"a":1}\n```'), { a: 1 });
});

async function chatSetup() {
  const rows = makeMovies(1200, 51);
  await useDb(rows);
  const calls = [];
  return { rows, calls };
}

test("[AI-CB-03] (Midterm TC9 ฉบับปรับ) บอทแนะนำได้เฉพาะหนังที่อยู่ใน DATABASE_CANDIDATES — id ที่แต่งขึ้นถูกตัด และแสดงไม่เกิน 3 เรื่อง", async () => {
  const { calls } = await chatSetup();
  h.setGemini(async (opts) => {
    calls.push(opts);
    if (calls.length === 1) return '{"mode":"genre","genre":"horror","title":"","minVotes":0}';
    const cand = opts.contents.at(-1).parts[0].text.match(/"id":"(tt\d+)"/g).map(x => x.slice(6, -1));
    return JSON.stringify({ reply: "ลองเรื่องเหล่านี้", picks: ["tt0000001", cand[0], "tt9999999", cand[1], cand[2], cand[3]] });
  });
  const out = await app.answerWithGemini("ขอหนังผีหน่อย", []);
  assert.equal(out.movies.length, 3);
  assert.ok(out.movies.every(m => /^tt/.test(m.id) && m.id !== "tt0000001" && m.id !== "tt9999999"));
  assert.ok(out.movies.every(m => app.matchesGenre(m, "สยองขวัญ")), "ผู้ใช้ขอหนังผี ต้องได้หนังหมวดสยองขวัญ");
});

test("[AI-CB-04] ถามว่า 'เรื่องนี้' ตอนไม่ได้เปิดหนังอยู่ → บังคับเป็นโหมดคุยทั่วไป ไม่แนบหนังมั่ว", async () => {
  const { calls } = await chatSetup();
  h.set("currentDetail", null);
  h.setGemini(async (opts) => { calls.push(opts); return calls.length === 1 ? '{"mode":"current"}' : '{"reply":"ยังไม่ได้เปิดหนังเรื่องไหนครับ","picks":["tt1"]}'; });
  const out = await app.answerWithGemini("เรื่องนี้ดีไหม", []);
  const sent = calls[1].contents.at(-1).parts[0].text;
  assert.match(sent, /\[CURRENT_MOVIE\]\nnone/);
  assert.match(sent, /\[DATABASE_CANDIDATES\]\n\[\]/);
  assert.equal(out.movies.length, 0);
});

test("[AI-CB-05] เปิดหน้าหนังอยู่ → Prompt แนบข้อมูลหนังจริง (คะแนน, S.D., Recommend side) ตัวเลขตรงฐานข้อมูล และระบุเมื่อใช้ค่าเฉลี่ยประเภท", async () => {
  const { rows } = await chatSetup();
  const movie = { ...rows.find(m => m.Critics_Average !== undefined && m.Movie_Critics_SD === undefined) };
  movie.Movie_Critics_SD = undefined;
  document.getElementById("detail-view").style.display = "block";
  h.set("currentDetail", { movie, genreSD: { critics: 0.8123, audience: 0.4 }, verdict: null });
  const ctx = app.getCurrentMovieContext();
  assert.equal(ctx.scores.audienceAverage, Number(movie.Audience_Average.toFixed(2)));
  assert.equal(ctx.scores.criticsAverage, Number(movie.Critics_Average.toFixed(2)));
  assert.equal(ctx.sd.audience, movie.Movie_Audience_SD);
  assert.equal(ctx.sd.critics, 0.81);
  assert.equal(ctx.sd.criticsSource, "genre_average");
  assert.ok(ctx.recommendSide.verdict);
  const { contents } = app.buildChatPrompt({ userText: "วิเคราะห์เรื่องนี้", currentMovie: ctx });
  assert.ok(contents.at(-1).parts[0].text.includes(`"audienceAverage":${ctx.scores.audienceAverage}`));
  document.getElementById("detail-view").style.display = "none";
  h.set("currentDetail", null);
});

test("[AI-CB-06] Gemini ล่ม → โหมดออฟไลน์สรุปจากข้อมูลจริงของหนังที่เปิดอยู่", async () => {
  const { rows } = await chatSetup();
  const movie = rows.find(m => m.Critics_Average !== undefined);
  document.getElementById("detail-view").style.display = "block";
  h.set("currentDetail", { movie, genreSD: { critics: null, audience: null }, verdict: null });
  const out = await app.answerOffline("วิเคราะห์หน่อย");
  assert.match(out.text, new RegExp(String(Number(movie.Audience_Average.toFixed(2)))));
  assert.match(out.text, /Recommend side/);
  document.getElementById("detail-view").style.display = "none";
  h.set("currentDetail", null);
});

test("[AI-CB-07] System prompt มีกติกากันแต่งข้อมูล (ตัวเลขต้องตรงข้อมูล, ระบุเมื่อใช้ความรู้ทั่วไป, picks ต้องมาจากฐานข้อมูล)", () => {
  assert.match(app.CHAT_SYSTEM_PROMPT, /ต้องตรงตามข้อมูลเท่านั้น ห้ามแต่ง/);
  assert.match(app.CHAT_SYSTEM_PROMPT, /ระบุว่าเป็นความรู้ทั่วไป/);
  assert.match(app.CHAT_SYSTEM_PROMPT, /ต้องมาจาก DATABASE_CANDIDATES เท่านั้น/);
});

// ---------------- CHAT-02: คำถามต่อเนื่อง + ค้นตาม keyword / ภาษา / หนัง-ซีรีส์ ----------------
test("[AI-CB-13] คำถามต่อเนื่อง: ขั้นวางแผนค้นหาเห็นบทสนทนาก่อนหน้า (4 ข้อความล่าสุด) และชื่อเรื่องบนการ์ดที่บอทแนะนำไป", async () => {
  await chatSetup();
  h.set("currentDetail", null);
  const turn = app.modelTurn({ text: "ลองดูเรื่องเหล่านี้", movies: [{ Title_EN: "2gether", Year: "2020" }, { Title_EN: "Bad Buddy", Year: "2021" }] });
  assert.deepEqual(turn.picks, ["2gether (2020)", "Bad Buddy (2021)"]);
  assert.equal(app.modelTurn({ text: "สวัสดี", movies: [] }).picks, undefined);
  const history = [
    { role: "user", text: "เก่าสุด ไม่ควรเห็น" }, { role: "model", text: "ตอบเก่า" },
    { role: "user", text: "ขอหนังผี" }, { role: "model", text: "นี่ครับ" },
    { role: "user", text: "แนะนำซีรีส์วายหน่อย" }, turn
  ];
  const calls = [];
  h.setGemini(async (opts) => { calls.push(opts); return calls.length === 1 ? '{"mode":"chat"}' : '{"reply":"ได้เลย","picks":[]}'; });
  await app.answerWithGemini("แบบเกาหลีบ้าง", history);
  const planText = calls[0].contents[0].parts[0].text;
  assert.match(planText, /HISTORY:\nผู้ใช้: ขอหนังผี\nบอท: นี่ครับ\nผู้ใช้: แนะนำซีรีส์วายหน่อย\nบอท: ลองดูเรื่องเหล่านี้ \[แนะนำ: 2gether \(2020\), Bad Buddy \(2021\)\]/);
  assert.ok(!planText.includes("เก่าสุด"), "ส่งแค่ 4 ข้อความล่าสุด");
  assert.match(planText, /คำถาม: แบบเกาหลีบ้าง$/);
  const answerTurns = calls[1].contents.map(c => c.parts[0].text).join("\n");
  assert.match(answerTurns, /\[แนะนำ: 2gether \(2020\), Bad Buddy \(2021\)\]/, "ขั้นตอบเห็นการ์ดที่แนะนำไปด้วย");
  assert.ok(app.planHistoryText([{ role: "user", text: "ก".repeat(500) }]).length < 260, "ตัดข้อความยาว");
  assert.equal(app.planHistoryText([]), "");
  assert.match(app.PLAN_SYSTEM, /"keyword"/);
  assert.match(app.PLAN_SYSTEM, /เรื่องที่สอง/);
});

const blRows = () => {
  const mk = (id, title, lang, kw, media, pop, extra = {}) => ({
    id, Title_EN: title, Title_TH: "", Year: "2022", Released: "2022-03-01", Genre_for_cal: "หนังชีวิต", Genres: ["หนังชีวิต", "หนังรักโรแมนติก"],
    MediaType: media, Language: lang, Keyword: kw, imdbVotes: 3000, Popularity: pop, Audience_Average: 8,
    Poster: `https://img.example/${id}.jpg`, CollectionID: 0, Companies: [], ...extra });
  return {
    thBL: [mk("ttb1", "2gether", "th", "boys' love (bl), university", "ซีรีส์", 3), mk("ttb2", "Bad Buddy", "th", "boys' love (bl), rivalry", "ซีรีส์", 2)],
    thBLMovie: mk("ttb3", "BL Movie", "th", "boys' love (bl)", "ภาพยนตร์", 2.5),
    thOther: mk("ttt1", "Thai Drama", "th", "family, blood feud", "ซีรีส์", 2.8),
    koBL: mk("ttk1", "Semantic Error", "ko", "boys' love (bl), college", "ซีรีส์", 1.5),
    koHorror: mk("ttk2", "Train to Busan", "ko", "zombie", "ภาพยนตร์", 1.2, { Genre_for_cal: "สยองขวัญ", Genres: ["สยองขวัญ"] }),
  };
};

test("[AI-CB-14] ถาม \"ซีรีส์วายไทย\": แผน keyword + ภาษา + ซีรีส์ → ได้เฉพาะซีรีส์ภาษาไทยที่มี keyword BL (เทียบทั้งคำ ไม่ใช่ blood)", async () => {
  const r = blRows();
  await useDb([...makeMovies(800, 5), ...r.thBL, r.thBLMovie, r.thOther, r.koBL, r.koHorror]);
  const ms = await app.candidatesFromPlan({ mode: "keyword", keyword: "boys' love, gay theme", language: "th", media: "series" }, null);
  assert.deepEqual(ms.map(m => m.id).sort(), ["ttb1", "ttb2"]);
  const bl = app.keywordMatcher("bl");
  assert.ok(bl(r.thBL[0]) && !bl(r.thOther), "'bl' ตรงกับ boys' love (bl) แต่ไม่ตรงกับ blood feud");
  assert.ok(app.keywordMatcher("Boys Love")(r.koBL), "ไม่สนตัวพิมพ์และเครื่องหมาย");
  assert.equal(app.keywordMatcher(" , "), null);
  assert.equal(app.compactMovie(r.koBL).language, "ko", "ส่งภาษาของแต่ละเรื่องให้ Gemini");
  const ko = await app.candidatesFromPlan({ mode: "genre", genre: "horror", language: "ko", media: "movie" }, null);
  assert.deepEqual(ko.map(m => m.id), ["ttk2"]);
});

test("[AI-CB-15] (edge) ไม่ระบุภาษาและเรื่องดังไม่ตรง keyword → ค้นเพิ่มในภาษาไทย/เกาหลี/ญี่ปุ่น/จีน; มีภาษาแต่ไม่มีเรื่องตรง → ใช้เรื่องภาษานั้น; ไม่มีทั้งคู่ → กลับไปใช้แผนเดิม; โหมด chat ไม่ค้น", async () => {
  const r = blRows();
  await useDb([...makeMovies(800, 5), ...r.thBL, r.thBLMovie, r.thOther, r.koBL, r.koHorror]);
  const any = await app.candidatesFromPlan({ mode: "keyword", keyword: "boys' love" }, null);
  assert.deepEqual(any.map(m => m.id).sort(), ["ttb1", "ttb2", "ttb3", "ttk1"]);
  const noHitTh = await app.candidatesFromPlan({ mode: "keyword", keyword: "space opera", language: "th" }, null);
  assert.ok(noHitTh.length > 0 && noHitTh.every(m => m.Language === "th"));
  const fallback = await app.candidatesFromPlan({ mode: "genre", genre: "comedy", keyword: "space opera" }, null);
  assert.ok(fallback.length > 0 && fallback.every(m => app.matchesGenre(m, "ตลก")), "ไม่มีเรื่องตรง keyword → ใช้แผนประเภทเดิม");
  const series = await app.candidatesFromPlan({ mode: "genre", genre: "comedy", media: "series" }, null);
  assert.ok(series.length > 0 && series.every(m => app.isSeries(m)), "กรองซีรีส์ในแผนประเภทเดิมด้วย");
  assert.deepEqual(await app.candidatesFromPlan({ mode: "chat", keyword: "boys' love", language: "th" }, null), []);
});
