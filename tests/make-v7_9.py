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
    # ไม่ใช่บั๊กจากเทสต์: แถว Loved by audiences / critics เรียงด้วยคะแนนถ่วงจำนวนโหวต (Audience_Score / Critics_Score
    # คำนวณโดย firebase-upload/weekly_update.py) ถ้าข้อมูลยังไม่มีฟิลด์นี้ จะเรียงด้วยค่าเฉลี่ยแบบเดิม
    ("RANK-01 weighted score state",
     "        let hasPopularityField = true;\n",
     "        let hasPopularityField = true;\n"
     "        let hasScoreFields = false;   // ข้อมูลมีคะแนนถ่วงจำนวนโหวต (Audience_Score / Critics_Score) หรือไม่ — ตั้งค่าใน detectSchema\n"),
    ("RANK-01 weighted score detect",
     "            hasPopularityField = samples.some(d => pickField(d, POPULARITY_KEYS) !== undefined);\n",
     "            hasPopularityField = samples.some(d => pickField(d, POPULARITY_KEYS) !== undefined);\n"
     "            hasScoreFields = samples.some(d => typeof d.Audience_Score === \"number\");\n"),
    ("RANK-01 order field (audience)",
     '            if (mode === "Audience_Average") return "Audience_Average";',
     '            // คะแนนเฉลี่ยล้วน ๆ ทำให้หนังที่มีคนโหวตไม่กี่ร้อยแต่ได้ 9+ ขึ้นมาก่อนหนังดัง — ใช้คะแนนถ่วงโหวตถ้ามี\n'
     '            if (mode === "Audience_Average") return hasScoreFields ? "Audience_Score" : "Audience_Average";'),
    ("RANK-01 order field (critics)",
     '            if (mode === "Critics_Average") return "Critics_Average";',
     '            if (mode === "Critics_Average") return hasScoreFields ? "Critics_Score" : "Critics_Average";'),
    ("RANK-01 client sort (audience)",
     "                        (toNum(b.Audience_Average) - toNum(a.Audience_Average)));",
     "                        (toNum(b[rankOrderField(mode)]) - toNum(a[rankOrderField(mode)])));"),
    ("RANK-01 client sort (critics)",
     "                        (toNum(b.Critics_Average) - toNum(a.Critics_Average)));",
     "                        (toNum(b[rankOrderField(mode)]) - toNum(a[rankOrderField(mode)])));"),
    ("RANK-01 score filter",
     '            const scoreField = mode === "Audience_Average" || mode === "Critics_Average" ? mode : null;',
     '            const scoreField = mode === "Audience_Average" || mode === "Critics_Average" ? orderField : null;'),
    ("RANK-01 chatbot top",
     '                        [orderBy("Audience_Average", "desc"), limit(25)],',
     '                        [where(rankOrderField("Audience_Average"), ">=", 0), orderBy(rankOrderField("Audience_Average"), "desc"), limit(25)],'),
    # ไม่ใช่บั๊กจากเทสต์ (ผู้ใช้เห็นจากหน้าเว็บจริง): ตาราง Trending now การ์ดกว้างตายตัว ทางขวาจึงเหลือช่องว่าง
    ("GRID-01 movie grid fills the row",
     "        .movie-grid { display: flex; flex-wrap: wrap; gap: 14px; padding: 6px 0 20px 0; justify-content: flex-start; }\n",
     "        /* ยืดการ์ดให้เต็มแถวพอดีทุกขนาดจอ (เดิมการ์ดกว้างตายตัว 190px ทางขวาจึงเหลือช่องว่าง) */\n"
     "        .movie-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; padding: 6px 0 20px 0; }\n"
     "        .movie-grid .movie-card { height: auto; aspect-ratio: 2 / 3; }\n"
     "        .movie-grid .no-results { grid-column: 1 / -1; }\n"),
    ("GRID-01 movie grid on phones",
     "            .movie-card { flex: 0 0 calc(50% - 7px); height: 250px; }\n",
     "            .movie-card { flex: 0 0 calc(50% - 7px); height: 250px; }\n"
     "            .movie-grid { grid-template-columns: repeat(2, 1fr); }\n"),
    ("GRID-01 trending years label",
     "                title += ` · ${ys[0]}–${ys[ys.length - 1]}`;",
     "                title += ` · ${ys[ys.length - 1]}–${ys[0]}`;   // ปีน้อยไปมาก เช่น 2024–2026 (การ์ดยังเรียงปีใหม่ก่อน)"),
    # ไม่ใช่บั๊กจากเทสต์ (ผู้ใช้เห็นจากหน้าเว็บจริง): S.D. บอกแค่ว่าแหล่งคะแนนในฝั่งเดียวกันเห็นตรงกันแค่ไหน
    # จะสรุปว่าคนดูกับนักวิจารณ์ "เห็นตรงกัน" ต้องดูจากค่าเฉลี่ยสองฝั่ง เช่น Mortal Kombat (2021) นักวิจารณ์ 4.95 คนดู 6.57
    # S.D. 0.78 กับ 0.66 ต่างกันแค่ 0.12 กฎเดิมจึงบอกว่า "ตรงกัน" ทั้งที่ค่าเฉลี่ยห่างกัน 1.62
    ("RULE-02 agreement threshold",
     "            equalTol: 0.15,          // ต่างกันไม่เกินนี้ = ความเห็นตรงกัน\n",
     "            agreeGap: 1.0,           // ค่าเฉลี่ยคนดูกับนักวิจารณ์ห่างกันไม่เกินนี้ (คะแนนเต็ม 10) = ความเห็นตรงกัน\n"
     "            equalTol: 0.15,          // S.D. สองฝั่งต่างกันไม่เกินนี้ = แหล่งคะแนนแต่ละฝั่งน่าเชื่อพอ ๆ กัน\n"),
    ("RULE-02 rule description",
     "         * Recommend Side — ฟันธงสั้น ๆ จากค่า S.D.\n"
     "         *  - SD สองฝั่งใกล้กัน            -> คนดูและนักวิจารณ์ความเห็นตรงกัน\n"
     "         *  - SD นักวิจารณ์ต่ำกว่าชัดเจน   -> เชื่อฝั่งนักวิจารณ์\n"
     "         *  - SD คนดูต่ำกว่าชัดเจน         -> เชื่อฝั่งคนดู\n",
     "         * Recommend Side — ฟันธงสั้น ๆ จากค่าเฉลี่ยและค่า S.D.\n"
     "         *  - ค่าเฉลี่ยสองฝั่งห่างกันไม่เกิน 1.0 -> คนดูและนักวิจารณ์ความเห็นตรงกัน\n"
     "         *  - ห่างเกิน 1.0 และ SD นักวิจารณ์ต่ำกว่าชัดเจน -> เชื่อฝั่งนักวิจารณ์\n"
     "         *  - ห่างเกิน 1.0 และ SD คนดูต่ำกว่าชัดเจน      -> เชื่อฝั่งคนดู\n"
     "         *  - ห่างเกิน 1.0 แต่ SD สองฝั่งใกล้กัน          -> สองฝั่งเห็นต่าง: บอกว่าฝั่งไหนชอบมากกว่า\n"
     "         *  - ไม่มีค่าเฉลี่ยฝั่งใดฝั่งหนึ่ง -> ใช้กฎ SD แบบเดิม (SD ใกล้กัน = ตรงกัน)\n"),
    ("RULE-02 average gap",
     "            let usedGenre = false;\n",
     "            let usedGenre = false;\n"
     "            // ช่องห่างของค่าเฉลี่ยสองฝั่ง ปัดเศษก่อนเทียบ (7.2 - 6.2 ในเครื่องคิดเป็น 1.0000000000000009)\n"
     "            const cAvg = v.criticsAvg ?? null, aAvg = v.audienceAvg ?? null;\n"
     "            const gap = cAvg !== null && aAvg !== null ? Math.round(Math.abs(cAvg - aAvg) * 1e6) / 1e6 : null;\n"
     "            const gapText = gap !== null ? `ค่าเฉลี่ยสองฝั่งห่างกัน ${gap.toFixed(2)} คะแนน` : \"\";\n"
     "            const agree = () => ({ text: \"คนดูและนักวิจารณ์ความเห็นตรงกัน\", tone: \"agree\", note: `${gapText} (ไม่เกิน ${SD_RULES.agreeGap.toFixed(1)})` });\n"
     "            const split = note => ({ text: aAvg > cAvg ? \"สองฝั่งเห็นต่าง: คนดูชอบมากกว่า\" : \"สองฝั่งเห็นต่าง: นักวิจารณ์ชอบมากกว่า\", tone: \"split\", note });\n"),
    ("RULE-02 no S.D. but averages known",
     "            if (critics === null && audience === null) {\n"
     "                return { text: \"ขาดข้อมูลในการตัดสินใจ\", tone: \"muted\", note: \"ไม่มีค่า S.D. ทั้งสองฝั่ง\" };\n",
     "            if (critics === null && audience === null) {\n"
     "                if (gap !== null) return gap <= SD_RULES.agreeGap ? agree() : split(`${gapText} · ไม่มีค่า S.D. ให้เทียบว่าฝั่งไหนน่าเชื่อกว่า`);\n"
     "                return { text: \"ขาดข้อมูลในการตัดสินใจ\", tone: \"muted\", note: \"ไม่มีค่า S.D. ทั้งสองฝั่ง\" };\n"),
    ("RULE-02 close averages agree",
     "            if (critics === null) return { text: \"เชื่อฝั่งคนดู\", tone: \"audience\", note: \"มีเฉพาะข้อมูลฝั่งคนดู\" };\n",
     "            // ค่าเฉลี่ยใกล้กัน = ความเห็นตรงกัน ไม่ว่า S.D. จะเป็นเท่าไร\n"
     "            if (gap !== null && gap <= SD_RULES.agreeGap) return agree();\n"
     "            if (critics === null) return { text: \"เชื่อฝั่งคนดู\", tone: \"audience\", note: \"มีเฉพาะข้อมูลฝั่งคนดู\" };\n"),
    ("RULE-02 note carries the gap",
     "            const note = usedGenre ? \"ฝั่งที่ขาดข้อมูลใช้ค่า S.D. เฉลี่ยของประเภทแทน\" : \"\";\n",
     "            const note = [gapText, usedGenre ? \"ฝั่งที่ขาดข้อมูลใช้ค่า S.D. เฉลี่ยของประเภทแทน\" : \"\"].filter(Boolean).join(\" · \");\n"),
    ("RULE-02 close S.D. but averages apart",
     "            if (diff <= SD_RULES.equalTol) {\n"
     "                return { text: \"คนดูและนักวิจารณ์ความเห็นตรงกัน\", tone: \"agree\", note };\n",
     "            if (diff <= SD_RULES.equalTol) {\n"
     "                // ค่าเฉลี่ยห่างเกินเกณฑ์ แต่แหล่งคะแนนทั้งสองฝั่งน่าเชื่อพอ ๆ กัน -> บอกว่าฝั่งไหนชอบมากกว่า\n"
     "                if (gap !== null) return split(`${note} · S.D. สองฝั่งใกล้กัน น่าเชื่อพอ ๆ กัน เลือกตามสไตล์ที่ชอบ`);\n"
     "                return { text: \"คนดูและนักวิจารณ์ความเห็นตรงกัน\", tone: \"agree\", note };   // ไม่มีค่าเฉลี่ยให้เทียบ\n"),
    ("RULE-02 split colour",
     '            agree: "#e2e8f0", warn: "#fbbf24", muted: "#8892b0"',
     '            agree: "#e2e8f0", warn: "#fbbf24", muted: "#8892b0", split: "#fb923c"'),
    ("RULE-02 detail page passes averages",
     "            const verdict = decideTrustSide({\n"
     "                critics: critSD, audience: audSD, overall: overallSD,\n",
     "            const verdict = decideTrustSide({\n"
     "                critics: critSD, audience: audSD, overall: overallSD,\n"
     "                criticsAvg: toNumOrNull(movie.Critics_Average), audienceAvg: toNumOrNull(movie.Audience_Average),\n"),
    ("RULE-02 chatbot context passes averages",
     "            const verdict = currentDetail.verdict || decideTrustSide({\n"
     "                critics: critSD, audience: audSD, overall: overallSD,\n",
     "            const verdict = currentDetail.verdict || decideTrustSide({\n"
     "                critics: critSD, audience: audSD, overall: overallSD,\n"
     "                criticsAvg: toNumOrNull(movie.Critics_Average), audienceAvg: toNumOrNull(movie.Audience_Average),\n"),
    ("RULE-02 chatbot explains the rule",
     "- S.D. ต่ำ = คะแนนเกาะกลุ่ม ความเห็นตรงกัน เชื่อถือได้ / S.D. สูง = ความเห็นแตก\n",
     "- S.D. ของแต่ละฝั่ง = แหล่งคะแนนในฝั่งเดียวกันให้คะแนนใกล้กันแค่ไหน (ต่ำ = เกาะกลุ่ม เชื่อถือได้ / สูง = แหล่งในฝั่งนั้นเห็นไม่ตรงกัน)\n"
     "- คนดูกับนักวิจารณ์เห็นตรงกันหรือไม่ ดูจากค่าเฉลี่ยสองฝั่ง: ห่างกันไม่เกิน 1.0 = ตรงกัน, ห่างเกิน 1.0 = เห็นต่าง\n"),
    ("RULE-02 chatbot cites averages",
     "- recommendSide.verdict = ข้อสรุปของเว็บว่าควรเชื่อฝั่งไหน ให้อธิบายเหตุผลโดยอ้างตัวเลข S.D. ประกอบ",
     "- recommendSide.verdict = ข้อสรุปของเว็บว่าควรเชื่อฝั่งไหน ให้อธิบายเหตุผลโดยอ้างค่าเฉลี่ยสองฝั่งและตัวเลข S.D. ประกอบ"),
]
for name, old, new in PATCHES:
    n = src.count(old)
    if n != 1:
        sys.exit(f"{name}: expected 1 match, found {n}")
    src = src.replace(old, new)
    print("applied", name)
pathlib.Path(sys.argv[2]).write_text(src, encoding="utf-8")
