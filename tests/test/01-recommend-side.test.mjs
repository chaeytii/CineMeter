// Recommend Side business rules (IT final spec) — decideTrustSide()
import { test } from "node:test";
import assert from "node:assert/strict";
import { app } from "../helpers/setup.mjs";
const { decideTrustSide, toNumOrNull, SD_RULES } = app;

const V = o => ({ critics: null, audience: null, overall: null, genreCritics: null, genreAudience: null, ...o });
const AGREE = "คนดูและนักวิจารณ์ความเห็นตรงกัน", CRIT = "เชื่อฝั่งนักวิจารณ์", AUD = "เชื่อฝั่งคนดู";
const NICHE = "ภาพยนตร์เฉพาะกลุ่ม / ความชอบส่วนบุคคล", NODATA = "ขาดข้อมูลในการตัดสินใจ";

test("[BL-SD-01] SD สองฝั่งใกล้กัน (ต่าง 0.10) → ความเห็นตรงกัน", () => {
  assert.equal(decideTrustSide(V({ critics: 0.30, audience: 0.40, overall: 0.5 })).text, AGREE);
});
test("[BL-SD-02] SD นักวิจารณ์ต่ำกว่าชัดเจน → เชื่อฝั่งนักวิจารณ์", () => {
  assert.equal(decideTrustSide(V({ critics: 0.20, audience: 0.90, overall: 0.8 })).text, CRIT);
});
test("[BL-SD-03] SD คนดูต่ำกว่าชัดเจน → เชื่อฝั่งคนดู", () => {
  assert.equal(decideTrustSide(V({ critics: 1.10, audience: 0.25, overall: 0.9 })).text, AUD);
});
test("[BL-SD-04] ขาด SD นักวิจารณ์ → ใช้ Genre_Critics_SD แทนแล้วเทียบ + แจ้ง note", () => {
  const r = decideTrustSide(V({ audience: 0.40, genreCritics: 0.20, genreAudience: 0.9 }));
  assert.equal(r.text, CRIT);
  assert.match(r.note, /ประเภท/);
});
test("[BL-SD-05] ขาด SD คนดู → ใช้ Genre_Audience_SD แทน", () => {
  const r = decideTrustSide(V({ critics: 0.80, genreAudience: 0.30, genreCritics: 0.9 }));
  assert.equal(r.text, AUD);
  assert.match(r.note, /ประเภท/);
});
test("[BL-SD-06] Overall_SD ≥ 1.50 → ภาพยนตร์เฉพาะกลุ่ม (มีลำดับความสำคัญเหนือการเทียบฝั่ง)", () => {
  const r = decideTrustSide(V({ critics: 0.2, audience: 1.4, overall: 1.5 }));
  assert.equal(r.text, NICHE);
  assert.equal(r.tone, "warn");
});
test("[BL-SD-07] Overall_SD ≥ 1.5 เท่าของ S.D. ประเภท → เฉพาะกลุ่ม แม้ต่ำกว่า 1.50", () => {
  // ref = max(0.6, 0.8) = 0.8 → threshold 1.2
  assert.equal(decideTrustSide(V({ critics: 0.3, audience: 0.9, overall: 1.25, genreCritics: 0.6, genreAudience: 0.8 })).text, NICHE);
});
test("[BL-SD-08] Overall_SD 1.49 และไม่มีค่าประเภท → ไม่ถือว่าเฉพาะกลุ่ม", () => {
  assert.notEqual(decideTrustSide(V({ critics: 0.3, audience: 0.9, overall: 1.49 })).text, NICHE);
});
test("[BL-SD-09] ไม่มีข้อมูล SD เลย → ขาดข้อมูลในการตัดสินใจ", () => {
  const r = decideTrustSide(V({}));
  assert.equal(r.text, NODATA);
  assert.equal(r.tone, "muted");
});
test("[BL-SD-10] มีข้อมูลฝั่งเดียวและไม่มีค่าประเภท → ชี้ไปฝั่งที่มีข้อมูล พร้อม note", () => {
  assert.equal(decideTrustSide(V({ audience: 0.5 })).text, AUD);
  assert.equal(decideTrustSide(V({ critics: 0.5 })).text, CRIT);
});
test("[BL-SD-11] (Midterm TC4) ประเภทที่มีหนังเรื่องเดียว คำนวณ SD ไม่ได้ (null) → ไม่ error และแจ้งขาดข้อมูล", () => {
  assert.doesNotThrow(() => decideTrustSide(V({ genreCritics: null, genreAudience: null })));
  assert.equal(decideTrustSide(V({ genreCritics: null, genreAudience: null })).text, NODATA);
});
test("[BL-SD-12] SD = 0 ทั้งสองฝั่ง ถือเป็นข้อมูลจริง (ไม่ใช่ขาดข้อมูล) → ตรงกัน", () => {
  assert.equal(decideTrustSide(V({ critics: 0, audience: 0, overall: 0 })).text, AGREE);
});
test("[BL-SD-13] แปลงค่าจากฐานข้อมูล: 'N/A', '', null → null ; '0.35' → 0.35 ; 0 → 0", () => {
  assert.equal(toNumOrNull("N/A"), null);
  assert.equal(toNumOrNull(""), null);
  assert.equal(toNumOrNull(null), null);
  assert.equal(toNumOrNull("0.35"), 0.35);
  assert.equal(toNumOrNull(0), 0);
});
test("[BL-SD-14] ขอบเขตพอดี: ต่างกัน 0.15 (0.30 vs 0.45) ต้องนับว่า 'ตรงกัน' ตามกติกา 'ไม่เกิน 0.15'", () => {
  assert.equal(SD_RULES.equalTol, 0.15);
  assert.equal(decideTrustSide(V({ critics: 0.30, audience: 0.45, overall: 0.4 })).text, AGREE);
});
test("[BL-SD-15] ขอบเขตพอดีทุกคู่ค่า 2 ตำแหน่ง (0.00–2.00) ที่ต่างกัน 0.15 ต้องได้ 'ตรงกัน' ทุกคู่", () => {
  const bad = [];
  for (let i = 0; i <= 185; i++) {
    const a = i / 100, b = Number((a + 0.15).toFixed(2));
    for (const [c, u] of [[a, b], [b, a]]) {
      if (decideTrustSide(V({ critics: c, audience: u, overall: 0.4 })).text !== AGREE) bad.push(`${c}/${u}`);
    }
  }
  assert.equal(bad.length, 0, `${bad.length} จาก 372 คู่ถูกจัดผิดฝั่ง เช่น ${bad.slice(0, 6).join(", ")}`);
});
test("[BL-SD-16] Property test 20,000 ชุดสุ่ม: ไม่ throw และผลลัพธ์อยู่ในชุดคำตอบที่กำหนดเท่านั้น (5 ข้อความ)", () => {
  const allowed = new Set([AGREE, CRIT, AUD, NICHE, NODATA]);
  let s = 42; const r = () => ((s = (s * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
  const maybe = () => (r() < 0.2 ? null : Math.round(r() * 250) / 100);
  for (let i = 0; i < 20000; i++) {
    const out = decideTrustSide(V({ critics: maybe(), audience: maybe(), overall: maybe(), genreCritics: maybe(), genreAudience: maybe() }));
    assert.ok(allowed.has(out.text), out.text);
    assert.ok(typeof out.tone === "string");
  }
});

// ---------- RULE-02: เห็นตรงกันหรือไม่ ดูจากค่าเฉลี่ยสองฝั่ง (ห่างไม่เกิน 1.0) แล้วค่อยใช้ S.D. เลือกฝั่ง ----------
const SPLIT_AUD = "สองฝั่งเห็นต่าง: คนดูชอบมากกว่า", SPLIT_CRIT = "สองฝั่งเห็นต่าง: นักวิจารณ์ชอบมากกว่า";

test("[BL-SD-17] (Mortal Kombat 2021) ค่าเฉลี่ยห่าง 1.62 แต่ S.D. ใกล้กัน (0.78 vs 0.66) → สองฝั่งเห็นต่าง ไม่ใช่ 'ตรงกัน'", () => {
  const r = decideTrustSide(V({ critics: 0.78, audience: 0.66, overall: 1.07, criticsAvg: 4.95, audienceAvg: 6.57 }));
  assert.equal(r.text, SPLIT_AUD);
  assert.equal(r.tone, "split");
  assert.match(r.note, /1\.62/);
  assert.equal(decideTrustSide(V({ critics: 0.5, audience: 0.6, overall: 0.9, criticsAvg: 8.0, audienceAvg: 6.5 })).text, SPLIT_CRIT);
});
test("[BL-SD-18] ค่าเฉลี่ยใกล้กัน (ห่าง 0.5) แม้ S.D. ต่างกันมาก (0.20 vs 0.90) → ความเห็นตรงกัน", () => {
  const r = decideTrustSide(V({ critics: 0.20, audience: 0.90, overall: 0.8, criticsAvg: 6.4, audienceAvg: 6.9 }));
  assert.equal(r.text, AGREE);
  assert.match(r.note, /0\.50/);
});
test("[BL-SD-19] ค่าเฉลี่ยห่างเกิน 1.0 → ใช้ S.D. เลือกฝั่งที่แหล่งคะแนนเห็นตรงกันมากกว่า", () => {
  assert.equal(decideTrustSide(V({ critics: 0.20, audience: 0.90, overall: 1.2, criticsAvg: 5.0, audienceAvg: 7.0 })).text, CRIT);
  assert.equal(decideTrustSide(V({ critics: 1.10, audience: 0.25, overall: 1.2, criticsAvg: 5.0, audienceAvg: 7.0 })).text, AUD);
});
test("[BL-SD-20] ขอบเขตพอดี: ค่าเฉลี่ยห่าง 1.00 ทุกคู่ (0.00–9.00) ต้องได้ 'ตรงกัน' และห่าง 1.01 ต้องไม่ใช่", () => {
  assert.equal(SD_RULES.agreeGap, 1.0);
  const bad = [];
  for (let i = 0; i <= 900; i++) {
    const a = i / 100, b = Number((a + 1).toFixed(2));
    for (const [c, u] of [[a, b], [b, a]]) {
      if (decideTrustSide(V({ critics: 0.2, audience: 0.9, overall: 0.8, criticsAvg: c, audienceAvg: u })).text !== AGREE) bad.push(`${c}/${u}`);
    }
  }
  assert.equal(bad.length, 0, `${bad.length} จาก 1,802 คู่ไม่ได้ 'ตรงกัน' เช่น ${bad.slice(0, 6).join(", ")}`);
  assert.notEqual(decideTrustSide(V({ critics: 0.2, audience: 0.9, overall: 0.8, criticsAvg: 6.0, audienceAvg: 7.01 })).text, AGREE);
});
test("[BL-SD-21] Overall_SD สูงผิดปกติยังมาก่อน แม้ค่าเฉลี่ยใกล้กัน → ภาพยนตร์เฉพาะกลุ่ม", () => {
  assert.equal(decideTrustSide(V({ critics: 1.2, audience: 1.3, overall: 1.6, criticsAvg: 6.0, audienceAvg: 6.3 })).text, NICHE);
});
test("[BL-SD-22] Property test 20,000 ชุดสุ่มพร้อมค่าเฉลี่ย: 'ตรงกัน' ก็ต่อเมื่อค่าเฉลี่ยห่างไม่เกิน 1.0 และผลอยู่ในชุดคำตอบ 7 ข้อความ", () => {
  const allowed = new Set([AGREE, CRIT, AUD, NICHE, NODATA, SPLIT_AUD, SPLIT_CRIT]);
  let s = 7; const r = () => ((s = (s * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
  const maybe = (max) => (r() < 0.2 ? null : Math.round(r() * max * 100) / 100);
  for (let i = 0; i < 20000; i++) {
    const v = V({ critics: maybe(2.5), audience: maybe(2.5), overall: maybe(2.5), genreCritics: maybe(2.5), genreAudience: maybe(2.5), criticsAvg: maybe(10), audienceAvg: maybe(10) });
    const out = decideTrustSide(v);
    assert.ok(allowed.has(out.text), out.text);
    if (v.criticsAvg !== null && v.audienceAvg !== null) {
      const gap = Math.round(Math.abs(v.criticsAvg - v.audienceAvg) * 100) / 100;
      if (out.text === AGREE) assert.ok(gap <= 1, `ตรงกันทั้งที่ห่าง ${gap}`);
      if (gap <= 1 && out.text !== NICHE) assert.equal(out.text, AGREE, `ห่าง ${gap} แต่ได้ ${out.text}`);
    }
  }
});
