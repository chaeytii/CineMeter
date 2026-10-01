// Builds cinemeter-live-check.html: app code copied verbatim from the delivered HTML + checker.js + UI shell.
// Usage: node build-check-page.mjs ../cinemeter-v7_9.html ../cinemeter-v7_8.html ../cinemeter-live-check.html
import { readFileSync, writeFileSync } from "node:fs";
import { findDecl, scriptOf } from "./lib-extract.mjs";

const [newPath, oldPath, outPath] = process.argv.slice(2);
const cur = scriptOf(readFileSync(newPath, "utf8"));
const old = scriptOf(readFileSync(oldPath, "utf8"));
const NAMES = ["firebaseConfig", "FS_BASE", "FS_TIMEOUT_MS", "DOC_ID", "db", "documentId", "collection", "doc", "where", "orderBy", "limit",
  "startAt", "startAfter", "endAt", "query", "OP_MAP", "toFsValue", "fromFsValue", "fromFsFields", "fieldRef", "makeSnapshot", "fsFetch",
  "cursorValues", "buildStructuredQuery", "getDocs", "getDoc", "GEMINI_PROXY", "GEMINI_PRIMARY_MODEL", "GEMINI_FALLBACK_MODELS", "ALGOLIA",
  "algoliaReady", "PAGE_SIZE", "ALGOLIA_MAX_FILTER_PAGES", "targetCollection", "collectionResolved", "loadedMovies", "detectValidCollection", "detectGenresArray", "detectLatestYear", "hasClientFilters", "loadSearch", "SD_RULES", "latestYear", "VOTE_KEYS", "POPULARITY_KEYS", "TMDBID_KEYS", "KEYWORD_KEYS", "MEDIATYPE_KEYS",
  "votesField", "mediaField", "mediaServerFilter", "votesNumeric", "hasPopularityField", "hasScoreFields", "VALUE_LABELS", "GENRE_VARIANTS", "GENRE_CANONICAL",
  "genresArrayReady", "THAI_CHAR", "THAI_TONE_MARKS", "idLooksImdb", "toNum", "toNumOrNull", "pickField", "getVotes", "getPopularity",
  "getMediaType", "isSeries", "getKeywords", "getYear", "formatVotes", "getEnglishTitle", "getThaiTitle", "docToMovie", "randomDocId",
  "yearInValues", "genreValues", "canonicalGenre", "legacyGenres", "movieGenres", "GENRE_DISPLAY_TH", "genreLabelTH", "genreDisplay", "genreWhere", "yearsFromFilter", "matchesGenre",
  "matchesMedia", "passesFilters", "detectSchema", "stripThaiTones", "algoliaQuery", "searchAlgolia", "normTitle", "titleMatchTier",
  "sortSearchHits", "decideTrustSide", "GEMINI_URL", "geminiModel", "callGemini", "parseJsonLoose", "CHAT_SYSTEM_PROMPT", "roundOrNull",
  "compactMovie", "buildChatPrompt", "extractReply"];
const decls = NAMES.map(n => findDecl(cur.src, n, cur.offset)).sort((a, b) => a.line - b.line);
const v78 = findDecl(old.src, "decideTrustSide", old.offset);
const appCode = decls.map(d => `// ↓ ${d.name} (${newPath.split("/").pop()} line ${d.line})\n${d.code}`).join("\n\n")
  + `\n\n// ↓ decideTrustSide ของ v7_8 (ก่อนแก้) — ใช้เทียบว่าเวอร์ชันเก่าจะตัดสินต่างกันกี่เรื่อง\n`
  + v78.code.replace("function decideTrustSide(", "function decideTrustSide_v78(");
const checker = readFileSync(new URL("./check-page/checker.js", import.meta.url), "utf8");
const version = newPath.split("/").pop().replace(".html", "");

const SECTIONS = [
  ["lat", "1. การเชื่อมต่อและความเร็ว", "วัดเวลาตอบของ Firestore (REST) และ Algolia 10 รอบ", "~450 reads"],
  ["cmp", "2. ขนาดและความครบถ้วนของข้อมูล", "นับจำนวนเรื่องทั้งหมดและความครบของแต่ละฟิลด์ด้วย COUNT aggregation (ไม่ต้องดาวน์โหลดทั้งฐานข้อมูล) + ตรวจชนิดข้อมูล", "~4,000 reads"],
  ["gen", "3. ประเภทหนังที่ความเห็นต่างกันมากที่สุด", "อ่าน GENRE_ANALYSIS ทั้งหมด + สุ่มหนังรายประเภทมาคำนวณช่องว่างคะแนนนักวิจารณ์ vs คนดู (ตอบวัตถุประสงค์ข้อ 1)", "~ประเภท × N reads"],
  ["rec", "4. คำนวณซ้ำเพื่อตรวจย้อนกลับ", "สุ่มหนังจากทั้งฐาน แล้วคำนวณคะแนนเฉลี่ยและ S.D. ใหม่จากคะแนนดิบ RT / Metacritic / IMDb / TMDb เทียบกับค่าที่เก็บไว้", "~N reads"],
  ["ver", "5. Recommend side บนข้อมูลจริง", "รันกติกา Recommend side (โค้ดเดียวกับแอป) กับกลุ่มตัวอย่าง: สัดส่วนคำตัดสิน, กรณีเส้นขอบ, การใช้ค่าระดับประเภทแทน", "ใช้ตัวอย่างเดิม"],
  ["fil", "6. ฟิลเตอร์และ index", "ยิงฟิลเตอร์หลายเงื่อนไขกับฐานจริง ตรวจว่าทุกเรื่องผ่านครบ, ตรวจว่ามี composite index หรือยัง, ตรวจหน้าแรกของการเรียงตามคะแนน", "~700 reads"],
  ["alg", "7. การค้นหา Algolia", "9 กรณี: ชื่อเต็ม, พิมพ์บางส่วน, พิมพ์ผิด, คำกลางชื่อ, ภาษาไทย, วรรณยุกต์เกิน, จัดอันดับตามโหวต", "9 searches"],
  ["ai", "8. AI guardrails (Gemini)", "5 คำถามทดสอบกติกากันแต่งข้อมูลของแชทบอท — ใช้โควตา Gemini 5 ครั้ง จึงไม่รวมในปุ่มรันทั้งหมด", "5 Gemini calls"],
];

const html = `<!doctype html>
<html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CineMeter Live Check</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#061121;--panel:#0b1a30;--line:#1f3354;--text:#e6edf7;--muted:#8fa3bf;--accent:#ff6600;--ok:#34d399;--bad:#f87171;--warn:#fbbf24}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 Inter,'IBM Plex Sans Thai',system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 16px 80px}
header{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:22px}
h1{margin:0;font-size:26px;letter-spacing:-.01em}h1 span{color:var(--accent)}.sub{color:var(--muted);margin:6px 0 0;max-width:720px}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
label{color:var(--muted);font-size:13px}input[type=number]{width:84px;background:var(--panel);border:1px solid var(--line);color:var(--text);border-radius:8px;padding:6px 8px;font:inherit}
button{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:10px;padding:8px 14px;font:inherit;font-weight:600;cursor:pointer}
button:hover{border-color:var(--accent)}button.primary{background:var(--accent);border-color:var(--accent);color:#fff}button:disabled{opacity:.55;cursor:wait}
button.running::after{content:" …"}
section{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 18px 14px;margin:0 0 16px}
.sh{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}.sh h2{margin:0;font-size:18px}.sh p{margin:4px 0 0;color:var(--muted);font-size:13.5px}
.cost{font-size:12px;color:var(--muted);white-space:nowrap}
.tw{overflow-x:auto;margin-top:12px}table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600;background:#0a1628;position:sticky;top:0}td code,code{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:#cfe0ff}
.b{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:700}.b.ok{background:rgba(52,211,153,.15);color:var(--ok)}.b.bad{background:rgba(248,113,113,.15);color:var(--bad)}.b.warn{background:rgba(251,191,36,.15);color:var(--warn)}
.note{color:var(--muted);font-size:12.5px;margin:10px 0 0}.err{color:var(--bad)}.answer{background:rgba(255,102,0,.1);border-left:3px solid var(--accent);padding:10px 12px;border-radius:6px;margin-top:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-top:12px}.kpis div{background:#0a1628;border:1px solid var(--line);border-radius:10px;padding:10px 12px}.kpis b{display:block;font-size:22px}.kpis span{color:var(--muted);font-size:12.5px}
h4{margin:16px 0 0;font-size:14px}details{margin-top:10px}summary{cursor:pointer;color:var(--muted)}
textarea{width:100%;min-height:220px;background:#0a1628;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:12px;font:12.5px/1.5 ui-monospace,Menlo,monospace}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.foot{color:var(--muted);font-size:12.5px;margin-top:20px}
@media (max-width:640px){h1{font-size:21px}.cost{white-space:normal}}
</style></head><body><div class="wrap">
<header><div><h1>Cine<span>Meter</span> · Live Data Check</h1>
<p class="sub">ตรวจข้อมูลจริงในฐานข้อมูลด้วยโค้ดชุดเดียวกับแอป (${version}) — อ่านอย่างเดียว ไม่เขียน/ลบข้อมูล · เปิดไฟล์นี้วิธีเดียวกับที่เปิดเว็บแอป (โฟลเดอร์เดียวกัน/โฮสต์เดียวกัน)</p></div>
<div class="controls"><label>สุ่มตัวอย่าง <input id="sampleN" type="number" value="300" min="50" max="2000"> เรื่อง</label>
<label>ต่อประเภท <input id="genreN" type="number" value="100" min="20" max="500"> เรื่อง</label>
<button id="resample" type="button">สุ่มตัวอย่างใหม่</button><button id="btn-all" class="primary" type="button">รันทั้งหมด (1–7)</button></div></header>
${SECTIONS.map(([id, h, p, cost]) => `<section><div class="sh"><div><h2>${h}</h2><p>${p}</p></div><div><span class="cost">${cost}</span> <button id="btn-${id}" type="button">รัน</button></div></div><div id="out-${id}"></div></section>`).join("\n")}
<section><div class="sh"><div><h2>สรุปผลสำหรับใส่รายงาน</h2><p>อัปเดตอัตโนมัติหลังรันแต่ละหัวข้อ — คัดลอกไปวางในรายงาน หรือส่งไฟล์ .md / .json กลับมาให้ช่วยสรุปต่อ</p></div></div>
<textarea id="summary" readonly placeholder="ยังไม่ได้รัน"></textarea>
<div class="row"><button id="btn-copy" type="button">คัดลอก Markdown</button><button id="btn-md" type="button">ดาวน์โหลด .md</button><button id="btn-json" type="button">ดาวน์โหลด .json</button></div></section>
<p class="foot">ใช้ Firestore reads รวมประมาณ 8,000–10,000 ครั้งต่อการรันทั้งหมด (โควตาฟรี 50,000/วัน) · หัวข้อ 8 เรียก Gemini ผ่าน Cloud Function เดียวกับเว็บแอป จึงต้องเปิดไฟล์นี้จาก GitHub Pages หรือ http://localhost (เปิดแบบดับเบิลคลิกไฟล์จะถูกปฏิเสธ)</p>
</div>
<script type="module">
const APP_VERSION = ${JSON.stringify(version)};
/* ======== app code — copied verbatim from ${newPath.split("/").pop()} ======== */
${appCode}
/* ======== checker ======== */
${checker}
</script></body></html>`;
writeFileSync(outPath, html);
console.log(`wrote ${outPath} (${(html.length / 1024).toFixed(0)} KB, ${decls.length} app declarations)`);
