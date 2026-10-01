// Loved by audiences / critics: เรียงด้วยคะแนนถ่วงจำนวนโหวต (Audience_Score / Critics_Score จาก weekly_update.py)
import { test } from "node:test";
import assert from "node:assert/strict";
import { app, useDb, makeMovies, F } from "../helpers/setup.mjs";

// สูตรเดียวกับ firebase-upload/weekly_update.py → weighted()
const M = 25000;
const weighted = (avg, votes, prior) => typeof avg === "number" ? Math.round((votes / (votes + M) * avg + M / (votes + M) * prior) * 100) / 100 : "N/A";

function withScores(rows) {
  const mean = f => { const v = rows.map(r => r[f]).filter(x => typeof x === "number"); return Math.round(v.reduce((a, b) => a + b, 0) / v.length * 10) / 10; };
  const pa = mean("Audience_Average"), pc = mean("Critics_Average");
  return rows.map(r => ({ ...r, Audience_Score: weighted(r.Audience_Average, r.imdbVotes, pa), Critics_Score: weighted(r.Critics_Average, r.imdbVotes, pc) }));
}

const base = makeMovies(1500, 91);
const obscure = { ...base[0], id: "tt9999991", Audience_Average: 9.9, Critics_Average: 10, imdbVotes: 600, Recommended_Trust_Side: "คนดู" };
const famous = { ...base[1], id: "tt9999992", Audience_Average: 9.7, Critics_Average: 9.8, imdbVotes: 2500000, Recommended_Trust_Side: "คนดู" };
const rows = withScores([obscure, famous, ...base.slice(2)]);

test("[BL-WR-01] มีคะแนนถ่วงโหวต → Loved by audiences เรียงตาม Audience_Score: หนังดังคะแนนดีมาก่อน หนังโหวต 600 ที่ได้ 9.9 ไม่ขึ้นหน้าแรก", async () => {
  await useDb(rows);
  const r = await app.loadRanked("Audience_Average", null, F({ popular: "Audience_Average" }));
  const ids = r.movies.map(m => m.id);
  assert.ok(ids.includes("tt9999992"), "หนังดังคะแนนดีต้องอยู่หน้าแรก");
  assert.ok(!ids.includes("tt9999991"), "หนังโหวตน้อยคะแนนสูงผิดปกติไม่ควรอยู่หน้าแรก");
  assert.ok(r.movies.every(m => typeof m.Audience_Score === "number"));
});

test("[BL-WR-02] Loved by critics และแผน top ของแชทบอทใช้คะแนนถ่วงโหวตเช่นกัน", async () => {
  await useDb(rows);
  const c = await app.loadRanked("Critics_Average", null, F({ popular: "Critics_Average" }));
  assert.ok(c.movies.some(m => m.id === "tt9999992") && !c.movies.some(m => m.id === "tt9999991"));
  const top = await app.candidatesFromPlan({ mode: "top" }, null);
  assert.ok(top.some(m => m.id === "tt9999992") && !top.some(m => m.id === "tt9999991"));
});
