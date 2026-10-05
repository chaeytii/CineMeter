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
    # ---------- PERS-01: Personalized แบบไม่ต้องล็อกอิน (เบราว์เซอร์จำประเภทที่ชอบเอง) ----------
    ("PERS-01 css",
     "        .row-link:hover { color: #ff6600; }\n",
     "        .row-link:hover { color: #ff6600; }\n"
     "        .row-note { font-size: 12px; color: #8892b0; font-weight: 400; margin-left: 10px; }\n"
     "        .like-btn { margin-top: 12px; background: transparent; border: 1px solid #ff6600; color: #ff6600; border-radius: 999px; padding: 6px 16px; font-size: 14px; cursor: pointer; }\n"
     "        .like-btn[aria-pressed=\"true\"] { background: #ff6600; color: #0a192f; }\n"),
    ("PERS-01 like button",
     '                        <span class="genre-chips" id="d-genre"></span>\n'
     "                    </div>\n",
     '                        <span class="genre-chips" id="d-genre"></span>\n'
     "                    </div>\n"
     '                    <button class="like-btn" id="d-like" type="button" aria-pressed="false" onclick="toggleLikeCurrent()">♡ ชอบเรื่องนี้</button>\n'),
    ("PERS-01 taste store",
     "        function writeStore(key, value) {\n"
     "            try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { }\n"
     "        }\n",
     "        function writeStore(key, value) {\n"
     "            try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { }\n"
     "        }\n"
     "\n"
     "        /* -------------------------------------------------------------\n"
     "         * PERSONALIZED แบบไม่ต้องล็อกอิน (PERS-01)\n"
     "         * เบราว์เซอร์เครื่องนั้นจำเอง (localStorage) ว่าผู้ใช้ชอบหนังประเภทไหน ไม่มีอะไรส่งขึ้นเซิร์ฟเวอร์\n"
     "         * - เปิดหน้ารายละเอียด 1 ครั้ง = ประเภทของเรื่องนั้นได้ +1, กด ♥ = +3 (กดซ้ำ = ยกเลิก -3)\n"
     "         * - ประเภทที่ได้ตั้งแต่ 2 แต้มขึ้นไป 2 อันดับแรก -> แถว \"For you\" บนหน้าแรก ไม่ซ้ำเรื่องที่เปิดดูแล้ว\n"
     "         * - เปลี่ยนเครื่องหรือล้างข้อมูลเบราว์เซอร์ = เริ่มนับใหม่ / กด \"ล้างประวัติ\" ได้ทุกเมื่อ\n"
     "         * ----------------------------------------------------------- */\n"
     "        const TASTE_KEY = \"cinemeter:taste:v1\";\n"
     "        const TASTE = { view: 1, like: 3, minScore: 2, topN: 2, seenMax: 200 };\n"
     "\n"
     "        function readTaste() {\n"
     "            const t = readStore(TASTE_KEY, null);\n"
     "            const ok = t && typeof t === \"object\" && t.genres && typeof t.genres === \"object\" && !Array.isArray(t.genres);\n"
     "            return {\n"
     "                genres: ok ? t.genres : {},\n"
     "                seen: ok && Array.isArray(t.seen) ? t.seen : [],\n"
     "                liked: ok && Array.isArray(t.liked) ? t.liked : []\n"
     "            };\n"
     "        }\n"
     "\n"
     "        function addGenreScore(t, movie, delta) {\n"
     "            [...new Set(movieGenres(movie).map(canonicalGenre))].forEach(g => {\n"
     "                t.genres[g] = Math.max(0, (Number(t.genres[g]) || 0) + delta);\n"
     "                if (!t.genres[g]) delete t.genres[g];\n"
     "            });\n"
     "        }\n"
     "\n"
     "        function recordTaste(movie) {\n"
     "            const t = readTaste();\n"
     "            if (!movie || !movie.id) return t;\n"
     "            addGenreScore(t, movie, TASTE.view);\n"
     "            t.seen = [movie.id, ...t.seen.filter(id => id !== movie.id)].slice(0, TASTE.seenMax);\n"
     "            writeStore(TASTE_KEY, t);\n"
     "            return t;\n"
     "        }\n"
     "\n"
     "        function toggleLike(movie) {\n"
     "            const t = readTaste();\n"
     "            if (!movie || !movie.id) return t;\n"
     "            const liked = t.liked.includes(movie.id);\n"
     "            addGenreScore(t, movie, liked ? -TASTE.like : TASTE.like);\n"
     "            t.liked = liked ? t.liked.filter(id => id !== movie.id) : [movie.id, ...t.liked];\n"
     "            writeStore(TASTE_KEY, t);\n"
     "            return t;\n"
     "        }\n"
     "\n"
     "        // ประเภทที่คะแนนถึงเกณฑ์ เรียงจากมากไปน้อย (เท่ากันเรียงตามชื่อ ให้ผลเหมือนเดิมทุกครั้ง)\n"
     "        function topGenres(t, n = TASTE.topN) {\n"
     "            return Object.entries(t.genres)\n"
     "                .filter(([g, s]) => g && Number(s) >= TASTE.minScore)\n"
     "                .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))\n"
     "                .slice(0, n).map(([g]) => g);\n"
     "        }\n"
     "\n"
     "        // สลับหนังจากแต่ละประเภททีละเรื่อง ตัดเรื่องซ้ำ เรื่องที่เคยเปิด และเรื่องไม่มีโปสเตอร์\n"
     "        function mixForYou(lists, seen, size) {\n"
     "            const skip = new Set(seen), out = [];\n"
     "            const longest = Math.max(0, ...lists.map(l => l.length));\n"
     "            for (let i = 0; i < longest && out.length < size; i++) {\n"
     "                for (const list of lists) {\n"
     "                    const m = list[i];\n"
     "                    if (!m || !m.Poster || skip.has(m.id)) continue;\n"
     "                    skip.add(m.id);\n"
     "                    out.push(m);\n"
     "                    if (out.length >= size) break;\n"
     "                }\n"
     "            }\n"
     "            return out;\n"
     "        }\n"
     "\n"
     "        function forYouRow(t = readTaste()) {\n"
     "            const genres = topGenres(t);\n"
     "            if (!genres.length) return null;\n"
     "            return { key: \"foryou\", forYou: true, genres, title: `For you · ${genres.map(genreLabelTH).join(\", \")}`,\n"
     "                     f: { genre: genres[0], popular: \"Audience_Average\" } };\n"
     "        }\n"
     "\n"
     "        function syncLikeButton(movie) {\n"
     "            const btn = document.getElementById(\"d-like\");\n"
     "            if (!btn || !movie) return;\n"
     "            const on = readTaste().liked.includes(movie.id);\n"
     "            btn.setAttribute(\"aria-pressed\", on ? \"true\" : \"false\");\n"
     "            btn.textContent = on ? \"♥ ชอบแล้ว\" : \"♡ ชอบเรื่องนี้\";\n"
     "        }\n"
     "\n"
     "        window.toggleLikeCurrent = function () {\n"
     "            const movie = currentDetail && currentDetail.movie;\n"
     "            if (!movie) return;\n"
     "            toggleLike(movie);\n"
     "            syncLikeButton(movie);\n"
     "        };\n"
     "\n"
     "        window.clearTaste = function () {\n"
     "            try { localStorage.removeItem(TASTE_KEY); } catch (e) { }\n"
     "            ensureForYouRow();\n"
     "        };\n"),
    ("PERS-01 openRow knows For you",
     "        window.openRow = function (key) {\n"
     "            const row = HOME_ROWS.find(r => r.key === key);\n",
     "        // แถวหน้าแรกตอนนี้ = For you (ถ้ามี) + แถวหมวดตายตัว\n"
     "        function homeRowsNow() {\n"
     "            const fy = forYouRow();\n"
     "            return fy ? [fy, ...HOME_ROWS] : HOME_ROWS;\n"
     "        }\n"
     "\n"
     "        function homeRowHtml(r) {\n"
     "            const link = r.forYou\n"
     "                ? `<span><a class=\"row-link\" onclick=\"openRow('${r.key}')\">ดูทั้งหมด ›</a> <a class=\"row-link\" onclick=\"clearTaste()\">ล้างประวัติ</a></span>`\n"
     "                : `<a class=\"row-link\" onclick=\"openRow('${r.key}')\">ดูทั้งหมด ›</a>`;\n"
     "            const note = r.forYou ? `<span class=\"row-note\">จากเรื่องที่คุณเปิดดูและกดชอบในเครื่องนี้</span>` : \"\";\n"
     "            return `\n"
     "                <section class=\"home-row\" data-row=\"${r.key}\"${r.forYou ? ` data-genres=\"${escapeHtml(r.genres.join(\"|\"))}\"` : \"\"}>\n"
     "                    <div class=\"section-header\">\n"
     "                        <span>${escapeHtml(r.title)}${note}</span>\n"
     "                        ${link}\n"
     "                    </div>\n"
     "                    <div class=\"row-wrap\">\n"
     "                        <button class=\"row-arrow left\" type=\"button\" aria-label=\"เลื่อนซ้าย\" onclick=\"scrollRow('row-${r.key}', -1)\">‹</button>\n"
     "                        <div class=\"movie-row\" id=\"row-${r.key}\"></div>\n"
     "                        <button class=\"row-arrow right\" type=\"button\" aria-label=\"เลื่อนขวา\" onclick=\"scrollRow('row-${r.key}', 1)\">›</button>\n"
     "                    </div>\n"
     "                </section>`;\n"
     "        }\n"
     "\n"
     "        // เพิ่ม/เปลี่ยน/ลบแถว For you ให้ตรงกับประวัติล่าสุด (เรียกตอนกลับหน้าแรก)\n"
     "        function ensureForYouRow() {\n"
     "            const wrap = document.getElementById(\"homeRows\");\n"
     "            if (!wrap || !wrap.childElementCount) return;\n"
     "            const fy = forYouRow();\n"
     "            const cur = wrap.querySelector('.home-row[data-row=\"foryou\"]');\n"
     "            const want = fy ? fy.genres.join(\"|\") : \"\";\n"
     "            if (cur && cur.dataset.genres === want) return;\n"
     "            if (cur) cur.remove();\n"
     "            rowState.delete(\"foryou\");\n"
     "            if (!fy) return;\n"
     "            wrap.insertAdjacentHTML(\"afterbegin\", homeRowHtml(fy));\n"
     "            loadHomeRow(\"foryou\");\n"
     "        }\n"
     "\n"
     "        window.openRow = function (key) {\n"
     "            const row = homeRowsNow().find(r => r.key === key);\n"),
    ("PERS-01 build rows with For you",
     "            wrap.innerHTML = HOME_ROWS.map(r => `\n"
     "                <section class=\"home-row\" data-row=\"${r.key}\">\n"
     "                    <div class=\"section-header\">\n"
     "                        <span>${escapeHtml(r.title)}</span>\n"
     "                        <a class=\"row-link\" onclick=\"openRow('${r.key}')\">ดูทั้งหมด ›</a>\n"
     "                    </div>\n"
     "                    <div class=\"row-wrap\">\n"
     "                        <button class=\"row-arrow left\" type=\"button\" aria-label=\"เลื่อนซ้าย\" onclick=\"scrollRow('row-${r.key}', -1)\">‹</button>\n"
     "                        <div class=\"movie-row\" id=\"row-${r.key}\"></div>\n"
     "                        <button class=\"row-arrow right\" type=\"button\" aria-label=\"เลื่อนขวา\" onclick=\"scrollRow('row-${r.key}', 1)\">›</button>\n"
     "                    </div>\n"
     "                </section>`).join(\"\");\n",
     "            wrap.innerHTML = homeRowsNow().map(homeRowHtml).join(\"\");\n"),
    ("PERS-01 load For you row",
     "            const row = HOME_ROWS.find(r => r.key === key);\n"
     "            const box = document.getElementById(\"row-\" + key);\n",
     "            const row = homeRowsNow().find(r => r.key === key);\n"
     "            const box = document.getElementById(\"row-\" + key);\n"
     "            if (!row || !box) { rowState.set(key, null); return; }\n"),
    ("PERS-01 fetch For you genres",
     "                const res = f.popular === \"random\" ? await loadDiscovery(null, f) : await loadRanked(f.popular, null, f);\n"
     "                const movies = res.movies.filter(m => m.Poster).slice(0, ROW_SIZE);\n",
     "                let movies;\n"
     "                if (row.forYou) {\n"
     "                    // ดึงหนังที่คนดูชอบในแต่ละประเภทที่ผู้ใช้ชอบ แล้วสลับกันทีละเรื่อง\n"
     "                    const lists = [];\n"
     "                    for (const g of row.genres) lists.push((await loadRanked(f.popular, null, { ...f, genre: g })).movies);\n"
     "                    movies = mixForYou(lists, readTaste().seen, ROW_SIZE);\n"
     "                } else {\n"
     "                    const res = f.popular === \"random\" ? await loadDiscovery(null, f) : await loadRanked(f.popular, null, f);\n"
     "                    movies = res.movies.filter(m => m.Poster).slice(0, ROW_SIZE);\n"
     "                }\n"),
    ("PERS-01 record a view",
     "            lastOpenedMovie = movie;\n"
     "            currentDetail = { movie, genreSD: null, verdict: null };\n",
     "            lastOpenedMovie = movie;\n"
     "            currentDetail = { movie, genreSD: null, verdict: null };\n"
     "            recordTaste(movie);\n"
     "            syncLikeButton(movie);\n"),
    ("PERS-01 refresh For you on return",
     "            currentDetail = null;\n"
     "            updateChatContext();\n"
     "            jumpTo(homeScrollY);\n",
     "            currentDetail = null;\n"
     "            updateChatContext();\n"
     "            ensureForYouRow();\n"
     "            jumpTo(homeScrollY);\n"),
    ('SIM-02 css',
     '        .suggested-section { margin-top: 60px; max-width: 1200px; margin-left: auto; margin-right: auto; border-top: 1px solid #233554; padding-top: 40px; }\n',
     '        .suggested-section { margin-top: 60px; max-width: 1200px; margin-left: auto; margin-right: auto; border-top: 1px solid #233554; padding-top: 40px; }\n        .movie-card.is-current { outline: 2px solid #ff6600; outline-offset: -2px; }\n'),
    ('SIM-02 collection section',
     '        <div class="suggested-section">\n            <div class="section-header" id="suggested-title">More like this</div>\n',
     '        <div class="suggested-section" id="collection-section" style="display:none">\n            <div class="section-header" id="collection-title">ภาคอื่นในชุดนี้</div>\n            <p class="suggest-note">เรียงตามปีที่ฉาย จากข้อมูลชุดภาพยนตร์ของ TMDB</p>\n            <div class="row-wrap">\n                <button class="row-arrow left" type="button" aria-label="เลื่อนซ้าย" onclick="scrollRow(\'collectionGrid\', -1)">‹</button>\n                <div class="suggested-grid" id="collectionGrid"></div>\n                <button class="row-arrow right" type="button" aria-label="เลื่อนขวา" onclick="scrollRow(\'collectionGrid\', 1)">›</button>\n            </div>\n        </div>\n\n        <div class="suggested-section">\n            <div class="section-header" id="suggested-title">More like this</div>\n'),
    ('SIM-02 open detail loads collection',
     '            updateChatContext();\n            fetchSimilarMovies(movie);\n',
     '            updateChatContext();\n            renderCollectionRow(movie);\n            fetchSimilarMovies(movie);\n'),
    ('SIM-02 helpers + votes weight',
     '        // คะแนนคัดตัวเลือกก่อนส่งให้ LLM — ยุคสมัยมีน้ำหนักรองจาก keyword\n        function preScore(base, cand) {\n            return keywordOverlap(base, cand) * 2.2\n                 + eraCloseness(base, cand) * 1.6\n                 + genreOverlap(base, cand) * 0.9\n                 + Math.min(0.6, Math.log10(getVotes(cand) + 1) / 10)\n                 + Math.min(0.4, getPopularity(cand) / 500);\n        }\n',
     '        // ชุดภาพยนตร์ (ภาคต่อ) และค่ายผลิต จาก TMDB — weekly_update.py เติมให้ (CollectionID 0 = ไม่อยู่ชุดไหน)\n        const FAMILIAR = { share: 0.2, floor: 5000, keep: 8 };   // ตัดหนังที่โหวตน้อยกว่า 20% ของต้นทาง (ขั้นต่ำ 5,000) ถ้ายังเหลือ ≥ 8 เรื่อง\n\n        function getCollectionId(m) {\n            const v = Number(m?.CollectionID);\n            return Number.isInteger(v) && v > 0 ? v : 0;\n        }\n\n        function getCompanies(m) {\n            return Array.isArray(m?.Companies) ? m.Companies.filter(c => Number.isInteger(c) && c > 0) : [];\n        }\n\n        function sameCollection(a, b) {\n            const c = getCollectionId(a);\n            return c > 0 && c === getCollectionId(b);\n        }\n\n        // 1 = มีค่ายผลิตร่วมกันอย่างน้อยหนึ่งค่าย (เช่น Marvel Studios)\n        function companyOverlap(a, b) {\n            const A = new Set(getCompanies(a));\n            return A.size && getCompanies(b).some(c => A.has(c)) ? 1 : 0;\n        }\n\n        // หนังที่คนรู้จักพอ ๆ กับต้นทาง — ถ้าตัดแล้วเหลือน้อยเกินไปใช้รายการเดิม\n        function keepFamiliar(base, list) {\n            const min = Math.max(FAMILIAR.floor, getVotes(base) * FAMILIAR.share);\n            const ok = list.filter(m => getVotes(m) >= min);\n            return ok.length >= FAMILIAR.keep ? ok : list;\n        }\n\n        // คะแนนคัดตัวเลือกก่อนส่งให้ LLM — ยุคสมัยมีน้ำหนักรองจาก keyword, ค่ายเดียวกันช่วยเล็กน้อย\n        function preScore(base, cand) {\n            return keywordOverlap(base, cand) * 2.2\n                 + eraCloseness(base, cand) * 1.6\n                 + genreOverlap(base, cand) * 0.9\n                 + companyOverlap(base, cand) * 0.8\n                 + Math.min(1, Math.log10(getVotes(cand) + 1) / 6)\n                 + Math.min(0.4, getPopularity(cand) / 500);\n        }\n\n        function sortByRelease(list) {\n            return list.slice().sort((a, b) => (getYear(a) || 9999) - (getYear(b) || 9999)\n                || String(a.Released || "").localeCompare(String(b.Released || "")));\n        }\n\n        // เรื่องทั้งหมดในชุดเดียวกัน (รวมเรื่องที่กำลังดู) เรียงตามปีฉาย — where เท่ากับฟิลด์เดียว ไม่ต้องสร้าง index\n        async function loadCollection(movie) {\n            const cid = getCollectionId(movie);\n            if (!cid) return [];\n            try {\n                const snap = await getDocs(query(collection(db, targetCollection), where("CollectionID", "==", cid), limit(40)));\n                return sortByRelease(snap.docs.map(docToMovie).filter(m => m.Poster && m.Poster !== "N/A"));\n            } catch (e) { reportIndexError(e); return []; }\n        }\n\n        async function renderCollectionRow(movie) {\n            const sec = document.getElementById("collection-section");\n            const grid = document.getElementById("collectionGrid");\n            sec.style.display = "none";\n            grid.innerHTML = "";\n            const list = await loadCollection(movie);\n            if (lastOpenedMovie && lastOpenedMovie !== movie) return;   // ผู้ใช้เปิดเรื่องอื่นไปแล้วระหว่างรอ\n            if (!list.some(m => m.id !== movie.id)) return;\n            document.getElementById("collection-title").innerText =\n                movie.CollectionName ? `ภาคอื่นในชุด ${movie.CollectionName}` : "ภาคอื่นในชุดนี้";\n            list.forEach(m => {\n                const card = buildCard(m, m.id === movie.id ? "กำลังดู" : "");\n                if (m.id === movie.id) card.classList.add("is-current");\n                grid.appendChild(card);\n            });\n            sec.style.display = "";\n        }\n'),
    ('SIM-02 candidate pool',
     '            const pool = new Map();\n            const add = list => list.forEach(m => {\n                if (m.id !== movie.id && m.Poster && !pool.has(m.id)) pool.set(m.id, m);\n            });\n\n            // 1) หมวดเดียวกัน + ยุคใกล้เคียง (±7 ปี)\n            if (baseYear) {\n                const years = [];\n                for (let y = baseYear - ERA_SPAN; y <= baseYear + ERA_SPAN; y++) if (y > 1900) years.push(y);\n                const yearWhere = where("Year", "in", yearInValues(years));\n                try {\n                    const snap = await runQuerySafe(\n                        primaryGenre ? [genreWhere(primaryGenre), yearWhere, limit(60)] : (genre ? [where("Genre_for_cal", "==", genre), yearWhere, limit(60)] : [yearWhere, limit(60)]),\n                        [yearWhere, limit(60)]\n                    );\n                    add(snap.docs.map(docToMovie));\n                } catch (e) { reportIndexError(e); }\n            }\n',
     '            const pool = new Map();\n            // เรื่องในชุดเดียวกันอยู่แถว "ภาคอื่นในชุดนี้" แล้ว ไม่ต้องซ้ำใน If you like…\n            const add = list => list.forEach(m => {\n                if (m.id !== movie.id && m.Poster && !pool.has(m.id) && !sameCollection(movie, m)) pool.set(m.id, m);\n            });\n\n            // 0) ค่ายผลิตเดียวกัน (เช่น Marvel Studios) ที่คนรู้จัก\n            const company = getCompanies(movie)[0];\n            if (company) {\n                try {\n                    const snap = await runQuerySafe(\n                        [where("Companies", "array-contains", company), orderBy("Popularity", "desc"), limit(40)],\n                        [where("Companies", "array-contains", company), limit(40)]\n                    );\n                    add(snap.docs.map(docToMovie));\n                } catch (e) { reportIndexError(e); }\n            }\n\n            // 1) หมวดเดียวกัน + ยุคใกล้เคียง (±7 ปี) — เรียงจากโหวตมากก่อน (ไม่มี index ใช้แบบไม่เรียง)\n            if (baseYear) {\n                const years = [];\n                for (let y = baseYear - ERA_SPAN; y <= baseYear + ERA_SPAN; y++) if (y > 1900) years.push(y);\n                const yearWhere = where("Year", "in", yearInValues(years));\n                const filters = primaryGenre ? [genreWhere(primaryGenre), yearWhere] : (genre ? [where("Genre_for_cal", "==", genre), yearWhere] : [yearWhere]);\n                const byVotes = (votesField && votesNumeric) ? votesField : "Popularity";\n                try {\n                    let snap;\n                    try {\n                        snap = await getDocs(query(collection(db, targetCollection), ...filters, orderBy(byVotes, "desc"), limit(60)));\n                    } catch (e) {\n                        reportIndexError(e);\n                        snap = await runQuerySafe([...filters, limit(60)], [yearWhere, limit(60)]);\n                    }\n                    add(snap.docs.map(docToMovie));\n                } catch (e) { reportIndexError(e); }\n            }\n'),
    ('SIM-02 prompt knows studio',
     'ห้ามแต่งเรื่องหรือ id ที่ไม่มีใน CANDIDATES\n',
     'sameStudio = true คือค่ายผลิตเดียวกับหนังต้นทาง ใช้ประกอบได้ แต่ตัดสินจากโทนเรื่องเป็นหลัก\nห้ามแต่งเรื่องหรือ id ที่ไม่มีใน CANDIDATES\n'),
    ('SIM-02 familiar filter',
     '                    if (near.length >= 8) candidates = near;\n                }\n',
     '                    if (near.length >= 8) candidates = near;\n                }\n                candidates = keepFamiliar(currentMovie, candidates);\n'),
    ('SIM-02 payload studio flag',
     '                            keywords: getKeywords(m).slice(0, 10),\n                            plot: String(m.Plot || "").slice(0, 220)\n',
     '                            keywords: getKeywords(m).slice(0, 10),\n                            sameStudio: companyOverlap(currentMovie, m) === 1,\n                            plot: String(m.Plot || "").slice(0, 220)\n'),
    ('SIM-02 same-era swap also for short lists',
     '                                while (picks.length > 3 && filler.length && picks.filter(p => Math.abs(getYear(p.movie) - baseYear) <= 10).length < 4) {\n',
     '                                while (filler.length && picks.filter(p => Math.abs(getYear(p.movie) - baseYear) <= 10).length < Math.min(4, picks.length)) {\n'),
]
for name, old, new in PATCHES:
    n = src.count(old)
    if n != 1:
        sys.exit(f"{name}: expected 1 match, found {n}")
    src = src.replace(old, new)
    print("applied", name)
pathlib.Path(sys.argv[2]).write_text(src, encoding="utf-8")
