// ทดสอบตัวกลาง Gemini โดยไม่ต่อเน็ต: จำลอง request/response ของ Firebase และ fetch ไปหา Google
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { handleRequest, _hits } = require("./proxy");

function fakeReq({ method = "POST", origin = "https://chaeytii.github.io", path = "/models/gemini-3.1-flash-lite:generateContent", body, ip = "1.1.1.1" } = {}) {
  const b = body === undefined ? { contents: [{ role: "user", parts: [{ text: "hi" }] }], generationConfig: { maxOutputTokens: 300 } } : body;
  return { method, path, body: b, ip, rawBody: Buffer.from(JSON.stringify(b)), get: h => (h.toLowerCase() === "origin" ? origin : undefined) };
}
function fakeRes() {
  const r = { statusCode: 200, headers: {}, payload: undefined };
  r.status = c => { r.statusCode = c; return r; };
  r.set = (k, v) => { r.headers[k] = v; return r; };
  r.type = () => r;
  r.json = o => { r.payload = o; return r; };
  r.send = s => { r.payload = s; return r; };
  return r;
}
function fakeFetch(status = 200, text = '{"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}') {
  const calls = [];
  const fn = async (url, init) => { calls.push({ url, init }); return { status, text: async () => text }; };
  fn.calls = calls;
  return fn;
}
const run = async (req, fetchImpl = fakeFetch()) => { const res = fakeRes(); await handleRequest(req, res, { apiKey: "SECRET", fetchImpl }); return { res, fetchImpl }; };

test("เว็บที่อนุญาต → ส่งต่อไป Gemini พร้อม key ใน header และตอบกลับตามเดิม", async () => {
  _hits.clear();
  const { res, fetchImpl } = await run(fakeReq());
  assert.equal(res.statusCode, 200);
  assert.equal(res.headers["Access-Control-Allow-Origin"], "https://chaeytii.github.io");
  assert.equal(fetchImpl.calls.length, 1);
  assert.equal(fetchImpl.calls[0].url, "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent");
  assert.equal(fetchImpl.calls[0].init.headers["x-goog-api-key"], "SECRET");
  assert.match(res.payload, /"ok"/);
  assert.ok(!res.payload.includes("SECRET"));
});

test("เว็บอื่น → 403 และไม่เรียก Gemini", async () => {
  _hits.clear();
  for (const origin of ["https://evil.example", "https://chaeytii.github.io.evil.com", null, "", "null"]) {
    const { res, fetchImpl } = await run(fakeReq({ origin }));
    assert.equal(res.statusCode, 403, String(origin));
    assert.equal(fetchImpl.calls.length, 0);
  }
});

test("preflight (OPTIONS) จากเว็บที่อนุญาต → 204", async () => {
  const { res } = await run(fakeReq({ method: "OPTIONS" }));
  assert.equal(res.statusCode, 204);
  assert.equal(res.headers["Access-Control-Allow-Methods"], "POST");
});

test("localhost ใช้ทดสอบได้", async () => {
  _hits.clear();
  const { res } = await run(fakeReq({ origin: "http://localhost:5500" }));
  assert.equal(res.statusCode, 200);
});

test("รุ่นที่ไม่อยู่ในรายการ หรือ path แปลก → 400", async () => {
  _hits.clear();
  for (const path of ["/models/gemini-2.5-pro:generateContent", "/models/gemini-2.0-flash:generateContent", "/models/gemini-3.1-flash-lite:streamGenerateContent", "/", "/models/../x:generateContent"]) {
    const { res, fetchImpl } = await run(fakeReq({ path }));
    assert.equal(res.statusCode, 400, path);
    assert.equal(fetchImpl.calls.length, 0);
  }
});

test("ขอ maxOutputTokens เกิน 2048 → ถูกลดเหลือ 2048, ค่าที่น้อยกว่าคงเดิม", async () => {
  _hits.clear();
  let r = await run(fakeReq({ body: { contents: [], generationConfig: { maxOutputTokens: 999999 } } }));
  assert.equal(JSON.parse(r.fetchImpl.calls[0].init.body).generationConfig.maxOutputTokens, 2048);
  r = await run(fakeReq({ body: { contents: [], generationConfig: { maxOutputTokens: 300, temperature: 0.2 } } }));
  const sent = JSON.parse(r.fetchImpl.calls[0].init.body).generationConfig;
  assert.equal(sent.maxOutputTokens, 300);
  assert.equal(sent.temperature, 0.2);
});

test("body ใหญ่เกิน / ไม่มี contents → ปฏิเสธ", async () => {
  _hits.clear();
  let r = await run(fakeReq({ body: { contents: [{ parts: [{ text: "x".repeat(70000) }] }] } }));
  assert.equal(r.res.statusCode, 413);
  r = await run(fakeReq({ body: { foo: 1 } }));
  assert.equal(r.res.statusCode, 400);
});

test("เรียกถี่เกิน 20 ครั้ง/นาทีจาก IP เดียว → 429", async () => {
  _hits.clear();
  const codes = [];
  for (let i = 0; i < 22; i++) codes.push((await run(fakeReq({ ip: "9.9.9.9" }))).res.statusCode);
  assert.deepEqual(codes.slice(0, 20), Array(20).fill(200));
  assert.equal(codes[20], 429);
  assert.equal((await run(fakeReq({ ip: "8.8.8.8" }))).res.statusCode, 200, "IP อื่นไม่โดนด้วย");
});

test("Gemini ตอบ 404 → ส่ง 404 กลับ (หน้าเว็บจะลองรุ่นสำรองต่อ), เน็ตล่ม → 502", async () => {
  _hits.clear();
  let r = await run(fakeReq(), fakeFetch(404, '{"error":{}}'));
  assert.equal(r.res.statusCode, 404);
  r = await run(fakeReq(), async () => { throw new Error("down"); });
  assert.equal(r.res.statusCode, 502);
});
