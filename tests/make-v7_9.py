# Builds cinemeter-v7_9.html = v7_8 + the fixes for bugs found by the test suite.
# Each patch must match exactly once, so the diff stays small and reviewable.
import sys, pathlib

src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
PATCHES = [
    ("BUG-01 SD tolerance float",
     "            const diff = Math.abs(critics - audience);\n            if (diff <= SD_RULES.equalTol) {",
     "            // ปัดเศษทศนิยมก่อนเทียบ: 0.45 - 0.30 ในเครื่องคิดเป็น 0.15000000000000002 จึงหลุดเกณฑ์ 'ไม่เกิน 0.15'\n"
     "            const diff = Math.round(Math.abs(critics - audience) * 1e6) / 1e6;\n            if (diff <= SD_RULES.equalTol) {"),
    ("BUG-02 formatVotes 1000K",
     '            if (n >= 1000000) return (n / 1000000).toFixed(1).replace(/\\.0$/, "") + "M";',
     '            if (n >= 999500) return (n / 1000000).toFixed(1).replace(/\\.0$/, "") + "M";   // 999,500+ ปัดแล้วเป็น 1M ไม่ใช่ 1000K'),
    ("BUG-03 title parentheses",
     "            t = t.replace(/\\s*\\([^)]*\\)/g, ' ').replace(/\\s{2,}/g, ' ').trim();   // ตัดวงเล็บออกทั้งหมด เหลือชื่ออังกฤษล้วน",
     "            // ตัดเฉพาะวงเล็บที่เป็นชื่อไทย และวงเล็บท้ายที่ซ้ำกับชื่ออังกฤษ — คงวงเล็บที่เป็นส่วนหนึ่งของชื่อจริง เช่น \"(500) Days of Summer\"\n"
     "            t = t.replace(/\\s*\\([^()]*[\\u0E00-\\u0E7F][^()]*\\)/g, ' ');\n"
     "            const dup = t.match(/^(.*\\S)\\s*\\(([^()]*)\\)\\s*$/);\n"
     "            if (dup && (!dup[2].trim() || dup[1].trim().toLowerCase() === dup[2].trim().toLowerCase())) t = dup[1];\n"
     "            t = t.replace(/\\s{2,}/g, ' ').trim();"),
    ("BUG-04 Thai title compare",
     '            document.getElementById("d-thai").innerText = thaiTitle && thaiTitle !== titleEN ? thaiTitle : "";',
     '            document.getElementById("d-thai").innerText = thaiTitle && thaiTitle.trim().toLowerCase() !== titleEN.trim().toLowerCase() ? thaiTitle : "";'),
    ("SEC-01 poster attribute (grid card)",
     "                <img src=\"${movie.Poster || 'https://via.placeholder.com/300x450?text=No+Poster'}\"",
     "                <img src=\"${escapeHtml(movie.Poster || 'https://via.placeholder.com/300x450?text=No+Poster')}\""),
    ("SEC-01 poster attribute (chat card)",
     "                    <img src=\"${movie.Poster || 'https://via.placeholder.com/60x90?text=Poster'}\"",
     "                    <img src=\"${escapeHtml(movie.Poster || 'https://via.placeholder.com/60x90?text=Poster')}\""),
    ("BUG-05 score sort skips non-numeric",
     "                keep: m => !scoreField || toNumOrNull(m[scoreField]) !== null,\n                orderParts: [orderBy(orderField, \"desc\")],",
     "                keep: m => !scoreField || toNumOrNull(m[scoreField]) !== null,\n"
     "                // กรองฝั่ง server ให้เหลือเฉพาะค่าที่เป็นตัวเลข (Firestore เทียบชนิดข้อมูลแบบเข้มงวด ค่า \"N/A\" ที่เป็นข้อความจะไม่ถูกดึงมา)\n"
     "                extraWheres: scoreField ? [where(scoreField, \">=\", 0)] : [],\n"
     "                orderParts: [orderBy(orderField, \"desc\")],"),
    ("BUG-06 random start point ignores imdbID format",
     "        function randomDocId() {\n",
     "        let idLooksImdb = false;   // doc ID เป็น imdbID (tt1234567) หรือไม่ — ตั้งค่าใน detectValidCollection\n"
     "        function randomDocId() {\n"
     "            // สุ่มให้อยู่ในรูปแบบเดียวกับ ID จริง: ถ้าสุ่มตัวอักษรทั่วไป จุดเริ่มจะตกก่อน/หลังช่วง \"tt...\" เกือบทุกครั้ง ได้หนังชุดแรกซ้ำเดิม\n"
     "            if (idLooksImdb) return \"tt\" + String(Math.floor(Math.random() * 1e7)).padStart(7, \"0\");\n"),
    ("BUG-06 detect id format",
     "                        detectSchema(snap.docs.map(d => d.data()));\n",
     "                        detectSchema(snap.docs.map(d => d.data()));\n"
     "                        idLooksImdb = snap.docs.every(d => /^tt\\d{7,8}$/.test(d.id));\n"),
    # ไม่ใช่บั๊กจากเทสต์: ย้าย Gemini API key ออกจากหน้าเว็บไปไว้ใน Cloud Function (functions/)
    ("KEY-01 Gemini key via Cloud Function (config)",
     '        const GEMINI_API_KEY = ""; // เอารหัสออกแล้ว (เวอร์ชันเก่า เก็บไว้เทียบผลเทสต์เท่านั้น)',
     "        // แชทบอทเรียก Gemini ผ่าน Firebase Cloud Function (functions/) ซึ่งเก็บ API key ไว้ฝั่ง server — ในหน้าเว็บจึงไม่มี key\n"
     '        const GEMINI_PROXY = "https://asia-southeast1-movie-858f6.cloudfunctions.net/gemini";'),
    ("KEY-01 Gemini key via Cloud Function (url)",
     "const GEMINI_URL = m => `https://generativelanguage.googleapis.com/v1beta/models/${m}:generateContent`;",
     "const GEMINI_URL = m => `${GEMINI_PROXY}/models/${m}:generateContent`;"),
    ("KEY-01 Gemini key via Cloud Function (header)",
     'headers: { "Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY },',
     'headers: { "Content-Type": "application/json" },'),
]
for name, old, new in PATCHES:
    n = src.count(old)
    if n != 1:
        sys.exit(f"{name}: expected 1 match, found {n}")
    src = src.replace(old, new)
    print("applied", name)
pathlib.Path(sys.argv[2]).write_text(src, encoding="utf-8")
