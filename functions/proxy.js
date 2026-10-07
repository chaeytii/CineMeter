// ตัวกลางระหว่างหน้าเว็บกับ Gemini: key อยู่ที่ server เท่านั้น เบราว์เซอร์ไม่เคยเห็น
// แยกออกจาก index.js เพื่อให้ทดสอบด้วย Node ได้โดยไม่ต้อง deploy

// เว็บที่อนุญาตให้เรียก (กันเว็บอื่นเอา Function นี้ไปใช้จากเบราว์เซอร์)
const ALLOWED_ORIGINS = [
  /^https:\/\/chaeytii\.github\.io$/,
  /^http:\/\/localhost(:\d+)?$/,
  /^http:\/\/127\.0\.0\.1(:\d+)?$/,
];

// รุ่นเดียวกับ GEMINI_PRIMARY_MODEL / GEMINI_FALLBACK_MODELS ใน index.html
const ALLOWED_MODELS = new Set([
  "gemini-3.1-flash-lite",
  "gemini-3.1-flash-lite-preview",
  "gemini-3.5-flash-lite",
  "gemini-3.6-flash",
]);

const MAX_OUTPUT_TOKENS = 2048;      // ค่าสูงสุดที่แอปขอจริง (แชทบอท)
const MAX_BODY_BYTES = 60 * 1024;    // prompt ของแอปยาวไม่เกินราว 20 KB
const RATE_LIMIT = 20;               // ครั้งต่อ IP ต่อนาที
const RATE_WINDOW_MS = 60 * 1000;

const hits = new Map();   // ip -> [เวลาที่เรียก]

function allowedOrigin(origin) {
  return !!origin && ALLOWED_ORIGINS.some(re => re.test(origin));
}

function rateLimited(ip, now = Date.now()) {
  const recent = (hits.get(ip) || []).filter(t => now - t < RATE_WINDOW_MS);
  recent.push(now);
  hits.set(ip, recent);
  if (hits.size > 5000) hits.clear();   // กันหน่วยความจำบวม
  return recent.length > RATE_LIMIT;
}

async function handleRequest(req, res, { apiKey, fetchImpl = fetch }) {
  const origin = req.get("origin");
  if (allowedOrigin(origin)) {
    res.set("Access-Control-Allow-Origin", origin);
    res.set("Vary", "Origin");
  }
  if (req.method === "OPTIONS") {
    if (!allowedOrigin(origin)) return res.status(403).json({ error: "origin not allowed" });
    res.set("Access-Control-Allow-Methods", "POST");
    res.set("Access-Control-Allow-Headers", "Content-Type");
    res.set("Access-Control-Max-Age", "3600");
    return res.status(204).send("");
  }
  if (!allowedOrigin(origin)) return res.status(403).json({ error: "origin not allowed" });
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

  // path เหมือน Gemini: /models/{model}:generateContent
  const m = /^\/models\/([a-z0-9.\-]+):generateContent$/.exec(req.path || "");
  if (!m || !ALLOWED_MODELS.has(m[1])) return res.status(400).json({ error: "model not allowed" });

  const raw = req.rawBody ? req.rawBody.length : Buffer.byteLength(JSON.stringify(req.body || {}));
  if (raw > MAX_BODY_BYTES) return res.status(413).json({ error: "request too large" });

  const ip = req.ip || req.get("x-forwarded-for") || "unknown";
  if (rateLimited(ip)) return res.status(429).json({ error: "too many requests" });

  const body = req.body && typeof req.body === "object" ? { ...req.body } : null;
  if (!body || !Array.isArray(body.contents)) return res.status(400).json({ error: "bad request" });
  body.generationConfig = { ...(body.generationConfig || {}) };
  body.generationConfig.maxOutputTokens = Math.min(Number(body.generationConfig.maxOutputTokens) || MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS);

  try {
    const upstream = await fetchImpl(`https://generativelanguage.googleapis.com/v1beta/models/${m[1]}:generateContent`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": apiKey },
      body: JSON.stringify(body),
    });
    // ส่ง status เดิมกลับ เพื่อให้ callGemini() ในหน้าเว็บสลับไปรุ่นสำรองได้เมื่อเจอ 400/404
    const text = await upstream.text();
    return res.status(upstream.status).type("application/json").send(text);
  } catch (err) {
    return res.status(502).json({ error: "gemini unreachable" });
  }
}

module.exports = { handleRequest, allowedOrigin, rateLimited, ALLOWED_MODELS, MAX_OUTPUT_TOKENS, _hits: hits };
