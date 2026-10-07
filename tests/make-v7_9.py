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
     "            return { key: \"foryou\", forYou: true, genres, title: \"For you\",\n"
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
     "            return `\n"
     "                <section class=\"home-row\" data-row=\"${r.key}\"${r.forYou ? ` data-genres=\"${escapeHtml(r.genres.join(\"|\"))}\"` : \"\"}>\n"
     "                    <div class=\"section-header\">\n"
     "                        <span>${escapeHtml(r.title)}</span>\n"
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
    ('GEN-01 genres comment',
     '         * สร้างโดยสคริปต์ tmdb-genres-migrate.mjs (ดึงประเภทจาก TMDB)\n         * สคริปต์จะเขียน META/genres = { complete: true } เมื่ออัปเดตครบทุกเรื่อง\n',
     '         * firebase-upload/weekly_update.py เติมให้ทุกเรื่องจาก TMDB (ชุดแรกเก็บแค่ประเภทแรกใน Genre_for_cal)\n         * แล้วเขียน META/genres = { complete: true } เมื่อครบทุกเรื่องและ composite index ใน firestore.indexes.json พร้อม\n'),
    ('HOME-02 row helpers',
     '        const rowState = new Map();   // key -> "loading" | "done"\n',
     '        const rowState = new Map();   // key -> "loading" | "done"\n'
     '\n'
     '        // หน้าแรกไม่แสดงเรื่องเดียวกันซ้ำหลายแถว (เรื่องที่มีหลายประเภทและดังมาก เช่น โดราเอมอน เข้าได้แทบทุกแถว)\n'
     '        const homeShown = new Map();     // key -> id ที่แถวนั้นแสดง\n'
     '        const homePending = new Map();   // key -> Promise ของแถวที่กำลังโหลด\n'
     '        const FAMILY_CARTOON = ["แอนนิเมชั่น", "ครอบครัว"];\n'
     '\n'
     '        // การ์ตูนครอบครัว (มีทั้งแอนนิเมชันและครอบครัว) ไม่ขึ้นในแถวหมวดอื่นบนหน้าแรก — ตัวกรองประเภทที่ผู้ใช้เลือกเองยังเจอตามปกติ\n'
     '        function familyCartoonOutOfPlace(m, genre) {\n'
     '            if (!genre || FAMILY_CARTOON.includes(genre)) return false;\n'
     '            const gs = movieGenres(m);\n'
     '            return FAMILY_CARTOON.every(g => gs.includes(g));\n'
     '        }\n'
     '\n'
     '        // เลือกเรื่องให้แถว: ต้องมีโปสเตอร์ ไม่ซ้ำเรื่องที่แถวด้านบนแสดงแล้ว และอยู่ถูกหมวด\n'
     '        function pickRowMovies(list, taken, size, genre) {\n'
     '            const ids = new Set(taken), out = [];\n'
     '            for (const m of list) {\n'
     '                if (!m || !m.Poster || ids.has(m.id) || familyCartoonOutOfPlace(m, genre)) continue;\n'
     '                ids.add(m.id);\n'
     '                out.push(m);\n'
     '                if (out.length >= size) break;\n'
     '            }\n'
     '            return out;\n'
     '        }\n'
     '\n'
     '        // id ที่แถวด้านบนแสดงไปแล้ว — รอแถวด้านบนที่กำลังโหลดก่อน ผลจึงเหมือนเดิมไม่ว่าแถวไหนโหลดเสร็จก่อน (แถว For you ไม่นับ)\n'
     '        async function shownAbove(key) {\n'
     '            const rows = homeRowsNow().filter(r => !r.forYou);\n'
     '            const above = rows.slice(0, Math.max(0, rows.findIndex(r => r.key === key)));\n'
     '            await Promise.all(above.map(r => homePending.get(r.key)).filter(Boolean));\n'
     '            const ids = new Set();\n'
     '            above.forEach(r => (homeShown.get(r.key) || []).forEach(id => ids.add(id)));\n'
     '            return ids;\n'
     '        }\n'),
    ('HOME-02 track pending rows',
     '        async function loadHomeRow(key) {\n            if (rowState.get(key)) return;\n',
     '        function loadHomeRow(key) {\n'
     '            if (rowState.get(key)) return homePending.get(key);\n'
     '            const p = loadHomeRowNow(key);\n'
     '            homePending.set(key, p);\n'
     '            return p;\n'
     '        }\n'
     '\n'
     '        async function loadHomeRowNow(key) {\n'),
    ('HOME-02 For you skips out-of-place cartoons',
     '{ ...f, genre: g })).movies);\n',
     '{ ...f, genre: g })).movies.filter(m => !familyCartoonOutOfPlace(m, g)));\n'),
    ('HOME-02 genre rows skip repeats',
     '                    const res = f.popular === "random" ? await loadDiscovery(null, f) : await loadRanked(f.popular, null, f);\n'
     '                    movies = res.movies.filter(m => m.Poster).slice(0, ROW_SIZE);\n',
     '                    const fetchPage = cursor => f.popular === "random" ? loadDiscovery(cursor, f) : loadRanked(f.popular, cursor, f);\n'
     '                    let res = await fetchPage(null);\n'
     '                    let list = res.movies.slice();\n'
     '                    const taken = await shownAbove(key);\n'
     '                    movies = pickRowMovies(list, taken, ROW_SIZE, f.genre);\n'
     '                    // ข้ามเรื่องซ้ำจนไม่ครบแถว → ดึงหน้าถัดไปอีกไม่เกิน 2 หน้า\n'
     '                    for (let i = 0; i < 2 && movies.length < ROW_SIZE && !res.done && res.cursor; i++) {\n'
     '                        res = await fetchPage(res.cursor);\n'
     '                        list = list.concat(res.movies);\n'
     '                        movies = pickRowMovies(list, taken, ROW_SIZE, f.genre);\n'
     '                    }\n'
     '                    homeShown.set(key, movies.map(m => m.id));\n'),
    ('PERS-02 header comment',
     ' * - ประเภทที่ได้ตั้งแต่ 2 แต้มขึ้นไป 2 อันดับแรก -> แถว "For you" บนหน้าแรก ไม่ซ้ำเรื่องที่เปิดดูแล้ว\n',
     ' * - แถว "For you" บนหน้าแรก = หนังคล้าย 3 เรื่องล่าสุดที่กด ♥ (PERS-02) + หนังจากประเภทที่ได้ตั้งแต่ 2 แต้มขึ้นไป 2 อันดับแรก\n *   ไม่ซ้ำเรื่องที่เปิดดูหรือกดชอบแล้ว และโหลดใหม่ทุกครั้งที่ประวัติเปลี่ยน\n * - แถว "Your likes" = เรื่องที่กด ♥ ไว้ ใหม่สุดก่อน (เก็บแค่รหัสหนังในเครื่อง)\n'),
    ('PERS-02 rows from likes',
     '        function forYouRow(t = readTaste()) {\n            const genres = topGenres(t);\n            if (!genres.length) return null;\n            return { key: "foryou", forYou: true, genres, title: "For you",\n                     f: { genre: genres[0], popular: "Audience_Average" } };\n        }\n',
     '        const FOR_YOU_SEEDS = 3;   // ใช้เรื่องที่กดชอบล่าสุดกี่เรื่องหาหนังคล้ายกัน\n\n        function forYouRow(t = readTaste()) {\n            const genres = topGenres(t);\n            const seeds = t.liked.slice(0, FOR_YOU_SEEDS);\n            if (!genres.length && !seeds.length) return null;\n            // sig เปลี่ยนทุกครั้งที่ประวัติเปลี่ยน -> กลับหน้าแรกแล้วแถวโหลดใหม่ (ตัดเรื่องที่เพิ่งเปิด/กดชอบออก)\n            const sig = [genres.join("|"), seeds.join("|"), t.liked.length, t.seen.length].join("#");\n            return { key: "foryou", forYou: true, personal: true, genres, seeds, sig, title: "For you",\n                     f: { genre: genres[0] || "", popular: "Audience_Average" } };\n        }\n\n        // แถวเรื่องที่กด ♥ ไว้ ใหม่สุดก่อน — ยังไม่เคยกดชอบ = ไม่มีแถว\n        function likedRow(t = readTaste()) {\n            if (!t.liked.length) return null;\n            const ids = t.liked.slice(0, ROW_SIZE);\n            return { key: "liked", liked: true, personal: true, ids, sig: ids.join("|"), title: "Your likes", f: {} };\n        }\n\n        // หนังจากรหัส (เรื่องที่กดชอบเก็บแค่รหัสในเครื่อง) — ข้ามเรื่องที่ไม่พบ อ่านไม่ได้ หรือไม่มีโปสเตอร์ คงลำดับเดิม\n        async function loadMoviesByIds(ids) {\n            const out = await Promise.all(ids.map(async id => {\n                try {\n                    const snap = await getDoc(doc(db, targetCollection, id));\n                    return snap.exists() ? docToMovie(snap) : null;\n                } catch (e) { return null; }\n            }));\n            return out.filter(m => m && m.Poster && m.Poster !== "N/A");\n        }\n\n        // หนังคล้ายเรื่องที่กดชอบ: ใช้ตัวคัดของ More like this (ประเภท ยุค ค่ายผลิต keyword) โดยไม่เรียก AI — จำผลไว้ต่อเรื่อง\n        const similarCache = new Map();\n        function similarToLiked(seed) {\n            if (!similarCache.has(seed.id)) {\n                similarCache.set(seed.id, buildCandidatePool(seed)\n                    .then(pool => keepFamiliar(seed, pool).slice().sort((a, b) => preScore(seed, b) - preScore(seed, a)))\n                    .catch(() => { similarCache.delete(seed.id); return []; }));\n            }\n            return similarCache.get(seed.id);\n        }\n'),
    ('PERS-02 dedupe skips personal rows',
     '(แถว For you ไม่นับ)\n        async function shownAbove(key) {\n            const rows = homeRowsNow().filter(r => !r.forYou);\n',
     '(แถว For you / Your likes ไม่นับ)\n        async function shownAbove(key) {\n            const rows = homeRowsNow().filter(r => !r.personal);\n'),
    ('PERS-02 home rows include likes',
     '            const fy = forYouRow();\n            return fy ? [fy, ...HOME_ROWS] : HOME_ROWS;\n',
     '            const t = readTaste();\n            return [forYouRow(t), likedRow(t), ...HOME_ROWS].filter(Boolean);\n'),
    ('PERS-02 row header',
     '            const link = r.forYou\n',
     '            const link = r.liked ? "" : r.forYou\n'),
    ('PERS-02 row signature attribute',
     '${r.forYou ? ` data-genres="${escapeHtml(r.genres.join("|"))}"` : ""}',
     '${r.personal ? ` data-sig="${escapeHtml(r.sig)}"` : ""}'),
    ('PERS-02 refresh personal rows',
     '            const fy = forYouRow();\n            const cur = wrap.querySelector(\'.home-row[data-row="foryou"]\');\n            const want = fy ? fy.genres.join("|") : "";\n            if (cur && cur.dataset.genres === want) return;\n            if (cur) cur.remove();\n            rowState.delete("foryou");\n            if (!fy) return;\n            wrap.insertAdjacentHTML("afterbegin", homeRowHtml(fy));\n            loadHomeRow("foryou");\n',
     '            const t = readTaste();\n            let anchor = null;   // แถวส่วนตัวเรียงต่อกันบนสุด: For you แล้ว Your likes\n            for (const [key, row] of [["foryou", forYouRow(t)], ["liked", likedRow(t)]]) {\n                const cur = wrap.querySelector(`.home-row[data-row="${key}"]`);\n                if (cur && row && cur.dataset.sig === row.sig) { anchor = cur; continue; }\n                if (cur) cur.remove();\n                rowState.delete(key);\n                if (!row) continue;\n                if (anchor) anchor.insertAdjacentHTML("afterend", homeRowHtml(row));\n                else wrap.insertAdjacentHTML("afterbegin", homeRowHtml(row));\n                anchor = wrap.querySelector(`.home-row[data-row="${key}"]`);\n                loadHomeRow(key);\n            }\n'),
    ('PERS-02 load For you from likes',
     '                    // ดึงหนังที่คนดูชอบในแต่ละประเภทที่ผู้ใช้ชอบ แล้วสลับกันทีละเรื่อง\n                    const lists = [];\n',
     '                    // หนังคล้ายเรื่องที่กดชอบล่าสุด + หนังที่คนดูชอบในประเภทที่ผู้ใช้ชอบ สลับกันทีละเรื่อง\n                    const t = readTaste();\n                    const seeds = await loadMoviesByIds(row.seeds || []);\n                    const lists = await Promise.all(seeds.map(similarToLiked));\n'),
    ('PERS-02 skip seen and liked',
     '                    movies = mixForYou(lists, readTaste().seen, ROW_SIZE);\n                } else {\n',
     '                    movies = mixForYou(lists, [...t.seen, ...t.liked], ROW_SIZE);\n                } else if (row.liked) {\n                    movies = await loadMoviesByIds(row.ids);\n                } else {\n'),
    ('PERS-03 similar to likes by keyword and language',
     '        // หนังคล้ายเรื่องที่กดชอบ: ใช้ตัวคัดของ More like this (ประเภท ยุค ค่ายผลิต keyword) โดยไม่เรียก AI — จำผลไว้ต่อเรื่อง\n        const similarCache = new Map();\n        function similarToLiked(seed) {\n            if (!similarCache.has(seed.id)) {\n                similarCache.set(seed.id, buildCandidatePool(seed)\n                    .then(pool => keepFamiliar(seed, pool).slice().sort((a, b) => preScore(seed, b) - preScore(seed, a)))\n                    .catch(() => { similarCache.delete(seed.id); return []; }));\n            }\n            return similarCache.get(seed.id);\n        }\n',
     '        // หนังคล้ายเรื่องที่กดชอบ (PERS-03): ตัวเลือกจาก More like this + เรื่องภาษาเดียวกัน แล้วจัดอันดับด้วย keyword เป็นหลัก\n        // ไม่ตัดเรื่องโหวตน้อย (คนชอบซีรีส์เฉพาะกลุ่ม เช่น BL ก็ได้เรื่องแนวเดียวกัน) และไม่เรียก AI — จำผลไว้ต่อเรื่อง\n        const LANG_POOL = 80;\n        function getLanguage(m) { return String(m?.Language ?? m?.language ?? "").trim().toLowerCase(); }\n\n        function forYouScore(seed, cand) {\n            const lang = getLanguage(seed);\n            return keywordOverlap(seed, cand) * 3\n                 + (lang && lang === getLanguage(cand) ? 1.2 : 0)\n                 + (isSeries(seed) === isSeries(cand) ? 0.6 : 0)\n                 + genreOverlap(seed, cand) * 0.6\n                 + companyOverlap(seed, cand) * 0.5\n                 + eraCloseness(seed, cand) * 0.4\n                 + Math.min(0.3, Math.log10(getVotes(cand) + 1) / 20);\n        }\n\n        // เรื่องภาษาเดียวกับต้นทาง ดังก่อน (ต้องมี index Language + Popularity; ยังไม่มีก็ดึงแบบไม่เรียง)\n        async function loadSameLanguage(seed) {\n            const field = seed.Language !== undefined ? "Language" : "language";\n            const value = seed[field];\n            if (!getLanguage(seed)) return [];\n            try {\n                const snap = await runQuerySafe(\n                    [where(field, "==", value), orderBy("Popularity", "desc"), limit(LANG_POOL)],\n                    [where(field, "==", value), limit(LANG_POOL)]\n                );\n                return snap.docs.map(docToMovie).filter(m => getLanguage(m) === getLanguage(seed));\n            } catch (e) { reportIndexError(e); return []; }\n        }\n\n        const similarCache = new Map();\n        function similarToLiked(seed) {\n            if (!similarCache.has(seed.id)) {\n                similarCache.set(seed.id, Promise.all([buildCandidatePool(seed), loadSameLanguage(seed)])\n                    .then(([pool, same]) => {\n                        const byId = new Map();\n                        [...pool, ...same].forEach(m => {\n                            if (m && m.id !== seed.id && m.Poster && m.Poster !== "N/A" && !byId.has(m.id)) byId.set(m.id, m);\n                        });\n                        return [...byId.values()].sort((a, b) => forYouScore(seed, b) - forYouScore(seed, a));\n                    })\n                    .catch(() => { similarCache.delete(seed.id); return []; }));\n            }\n            return similarCache.get(seed.id);\n        }\n'),
    ('PERS-03 likes first, genres fill',
     '                    const lists = await Promise.all(seeds.map(similarToLiked));\n                    for (const g of row.genres) lists.push((await loadRanked(f.popular, null, { ...f, genre: g })).movies.filter(m => !familyCartoonOutOfPlace(m, g)));\n                    movies = mixForYou(lists, [...t.seen, ...t.liked], ROW_SIZE);\n',
     '                    // เรื่องคล้ายที่กดชอบขึ้นก่อน หนังจากประเภทที่ชอบใช้เติมเมื่อยังไม่ครบแถว\n                    const skip = [...t.seen, ...t.liked];\n                    const fromLikes = mixForYou(await Promise.all(seeds.map(similarToLiked)), skip, ROW_SIZE);\n                    const genreLists = [];\n                    if (fromLikes.length < ROW_SIZE) {\n                        for (const g of row.genres) genreLists.push((await loadRanked(f.popular, null, { ...f, genre: g })).movies.filter(m => !familyCartoonOutOfPlace(m, g)));\n                    }\n                    movies = fromLikes.concat(mixForYou(genreLists, skip.concat(fromLikes.map(m => m.id)), ROW_SIZE - fromLikes.length));\n'),
    ('PERS-03 header comment',
     ' * - แถว "For you" บนหน้าแรก = หนังคล้าย 3 เรื่องล่าสุดที่กด ♥ (PERS-02) + หนังจากประเภทที่ได้ตั้งแต่ 2 แต้มขึ้นไป 2 อันดับแรก\n',
     ' * - แถว "For you" บนหน้าแรก = หนังคล้าย 3 เรื่องล่าสุดที่กด ♥ (PERS-02/03: keyword + ภาษาเดียวกัน) ขึ้นก่อน\n *   แล้วเติมด้วยหนังจากประเภทที่ได้ตั้งแต่ 2 แต้มขึ้นไป 2 อันดับแรก\n'),
    ('PERS-04 older likes join the seeds',
     '        const FOR_YOU_SEEDS = 3;   // ใช้เรื่องที่กดชอบล่าสุดกี่เรื่องหาหนังคล้ายกัน\n\n        function forYouRow(t = readTaste()) {\n            const genres = topGenres(t);\n            const seeds = t.liked.slice(0, FOR_YOU_SEEDS);\n',
     '        const FOR_YOU_SEEDS = 3;   // ใช้เรื่องที่กดชอบล่าสุดกี่เรื่องหาหนังคล้ายกัน\n        const FOR_YOU_OLDER = 2;   // + สุ่มจากเรื่องที่กดชอบก่อนหน้านั้นอีกกี่เรื่อง ให้แนวที่เคยชอบยังโผล่มาบ้าง (PERS-04)\n        let olderPick = { key: "", ids: [] };   // สุ่มครั้งเดียวต่อการเปิดหน้า แล้วสุ่มใหม่เมื่อรายการที่ชอบเปลี่ยน\n\n        function pickOlderLikes(liked, rand = Math.random) {\n            const key = liked.join("|");\n            if (olderPick.key !== key) {\n                const pool = liked.slice(FOR_YOU_SEEDS);\n                const ids = [];\n                while (ids.length < FOR_YOU_OLDER && pool.length) ids.push(pool.splice(Math.floor(rand() * pool.length), 1)[0]);\n                olderPick = { key, ids };\n            }\n            return olderPick.ids;\n        }\n\n        function forYouRow(t = readTaste()) {\n            const genres = topGenres(t);\n            const seeds = [...t.liked.slice(0, FOR_YOU_SEEDS), ...pickOlderLikes(t.liked)];\n'),
    ('PERS-04 header comment',
     ' * - แถว "For you" บนหน้าแรก = หนังคล้าย 3 เรื่องล่าสุดที่กด ♥ (PERS-02/03: keyword + ภาษาเดียวกัน) ขึ้นก่อน\n',
     ' * - แถว "For you" บนหน้าแรก = หนังคล้าย 3 เรื่องล่าสุดที่กด ♥ + สุ่มอีก 2 เรื่องจากที่เคยกด ♥ ก่อนหน้า (PERS-02/03/04: keyword + ภาษาเดียวกัน) ขึ้นก่อน\n'),
    ('PERS-05 rank For you as one list',
     '            return similarCache.get(seed.id);\n        }\n\n        function syncLikeButton(movie) {\n',
     '            return similarCache.get(seed.id);\n        }\n\n'
     '        // เรียงหนังคล้ายเรื่องที่ชอบรวมเป็นแถวเดียว (PERS-05) แทนการหยิบสลับทีละเรื่องที่ชอบ:\n'
     '        // วัดแต่ละเรื่องกับทุกเรื่องที่ชอบ (คล้ายหลายเรื่อง = ขึ้นก่อน, คะแนนรวมแบบลดหลั่น s1 + s2/2 + s3/4 ...) + คะแนนคนดูเล็กน้อย\n'
     '        // เรื่องที่ชอบเรื่องเดียวกินช่องได้ไม่เกินครึ่งแถว ส่วนเกินต่อท้ายเมื่อแถวยังไม่เต็ม\n'
     '        const FOR_YOU_SEED_CAP = 0.5;\n'
     '        function rankForYou(seeds, lists, seen, size) {\n'
     '            const skip = new Set(seen), pool = new Map();\n'
     '            lists.forEach(list => (list || []).forEach(m => {\n'
     '                if (m && m.Poster && !skip.has(m.id) && !pool.has(m.id)) pool.set(m.id, m);\n'
     '            }));\n'
     '            const scored = [...pool.values()].map(m => {\n'
     '                const s = seeds.map((seed, i) => ({ i, v: forYouScore(seed, m) })).sort((a, b) => b.v - a.v);\n'
     '                const quality = Math.max(0, toNum(m.Audience_Average) - 5) * 0.2;\n'
     '                return { m, from: s.length ? s[0].i : -1, score: s.reduce((sum, x, k) => sum + x.v / 2 ** k, 0) + quality };\n'
     '            }).sort((a, b) => b.score - a.score);\n'
     '            const cap = Math.ceil(size * FOR_YOU_SEED_CAP), used = new Map(), out = [], extra = [];\n'
     '            for (const x of scored) {\n'
     '                const n = used.get(x.from) || 0;\n'
     '                if (n < cap) { used.set(x.from, n + 1); out.push(x.m); } else extra.push(x.m);\n'
     '            }\n'
     '            return out.concat(extra).slice(0, size);\n'
     '        }\n\n'
     '        function syncLikeButton(movie) {\n'),
    ('PERS-05 use rankForYou',
     '                    const fromLikes = mixForYou(await Promise.all(seeds.map(similarToLiked)), skip, ROW_SIZE);\n',
     '                    const fromLikes = rankForYou(seeds, await Promise.all(seeds.map(similarToLiked)), skip, ROW_SIZE);\n'),
    ('PERS-05 header comment',
     '(PERS-02/03/04: keyword + ภาษาเดียวกัน) ขึ้นก่อน\n',
     '(PERS-02/03/04: keyword + ภาษาเดียวกัน) ขึ้นก่อน\n         *   เรียงทั้งแถวด้วยคะแนนรวม: คล้ายหลายเรื่องที่ชอบ + คะแนนคนดู ขึ้นก่อน (PERS-05)\n'),
    ('PERS-06 rare keywords count more',
     '        function forYouScore(seed, cand) {\n            const lang = getLanguage(seed);\n            return keywordOverlap(seed, cand) * 3\n                 + (lang && lang === getLanguage(cand) ? 1.2 : 0)\n                 + (isSeries(seed) === isSeries(cand) ? 0.6 : 0)\n                 + genreOverlap(seed, cand) * 0.6\n                 + companyOverlap(seed, cand) * 0.5\n                 + eraCloseness(seed, cand) * 0.4\n                 + Math.min(0.3, Math.log10(getVotes(cand) + 1) / 20);\n        }\n\n',
     '        // keyword ที่หลายเรื่องมีเหมือนกัน (เช่น "anime", "based on manga") บอกความคล้ายได้น้อย (PERS-06)\n        // น้ำหนัก = ความหายากในกองตัวเลือก (IDF) 0–1: เกือบทุกเรื่องมี → ใกล้ 0, มีแค่ไม่กี่เรื่อง → ใกล้ 1\n        function keywordWeights(movies) {\n            const df = new Map();\n            movies.forEach(m => new Set(getKeywords(m).map(k => k.toLowerCase())).forEach(k => df.set(k, (df.get(k) || 0) + 1)));\n            const n = movies.length;\n            return k => n < 2 ? 1 : Math.log((n + 1) / ((df.get(k) || 0) + 1)) / Math.log(n + 1);\n        }\n\n        function weightedKeywordOverlap(a, b, weight) {\n            const A = new Set(getKeywords(a).map(s => s.toLowerCase()));\n            if (!A.size) return 0;\n            const B = getKeywords(b).map(s => s.toLowerCase());\n            if (!B.length) return 0;\n            const hit = B.filter(k => A.has(k)).reduce((sum, k) => sum + weight(k), 0);\n            return hit / Math.max(3, Math.min(A.size, B.length));\n        }\n\n        const FAMILY_GENRE = "ครอบครัว";\n        function isFamily(m) { return movieGenres(m).includes(FAMILY_GENRE); }\n\n        // weight (ไม่บังคับ) = น้ำหนัก keyword จาก keywordWeights — ใช้ตอนเรียงแถว For you (มีกลุ่มผู้ชมครอบครัว/ทั่วไปตรงกันด้วย)\n        function forYouScore(seed, cand, weight) {\n            const lang = getLanguage(seed);\n            return (weight ? weightedKeywordOverlap(seed, cand, weight) : keywordOverlap(seed, cand)) * 3\n                 + (lang && lang === getLanguage(cand) ? 1.2 : 0)\n                 + (isSeries(seed) === isSeries(cand) ? 0.6 : 0)\n                 + (weight && isFamily(seed) === isFamily(cand) ? 0.6 : 0)\n                 + genreOverlap(seed, cand) * 0.6\n                 + companyOverlap(seed, cand) * 0.5\n                 + eraCloseness(seed, cand) * 0.4\n                 + Math.min(0.3, Math.log10(getVotes(cand) + 1) / 20);\n        }\n\n'),
    ('PERS-06 spread likes, one per franchise',
     '        // เรียงหนังคล้ายเรื่องที่ชอบรวมเป็นแถวเดียว (PERS-05) แทนการหยิบสลับทีละเรื่องที่ชอบ:\n        // วัดแต่ละเรื่องกับทุกเรื่องที่ชอบ (คล้ายหลายเรื่อง = ขึ้นก่อน, คะแนนรวมแบบลดหลั่น s1 + s2/2 + s3/4 ...) + คะแนนคนดูเล็กน้อย\n        // เรื่องที่ชอบเรื่องเดียวกินช่องได้ไม่เกินครึ่งแถว ส่วนเกินต่อท้ายเมื่อแถวยังไม่เต็ม\n        const FOR_YOU_SEED_CAP = 0.5;\n        function rankForYou(seeds, lists, seen, size) {\n            const skip = new Set(seen), pool = new Map();\n            lists.forEach(list => (list || []).forEach(m => {\n                if (m && m.Poster && !skip.has(m.id) && !pool.has(m.id)) pool.set(m.id, m);\n            }));\n            const scored = [...pool.values()].map(m => {\n                const s = seeds.map((seed, i) => ({ i, v: forYouScore(seed, m) })).sort((a, b) => b.v - a.v);\n                const quality = Math.max(0, toNum(m.Audience_Average) - 5) * 0.2;\n                return { m, from: s.length ? s[0].i : -1, score: s.reduce((sum, x, k) => sum + x.v / 2 ** k, 0) + quality };\n            }).sort((a, b) => b.score - a.score);\n            const cap = Math.ceil(size * FOR_YOU_SEED_CAP), used = new Map(), out = [], extra = [];\n            for (const x of scored) {\n                const n = used.get(x.from) || 0;\n                if (n < cap) { used.set(x.from, n + 1); out.push(x.m); } else extra.push(x.m);\n            }\n            return out.concat(extra).slice(0, size);\n        }\n\n',
     '        // เรียงหนังคล้ายเรื่องที่ชอบรวมเป็นแถวเดียว (PERS-05/06):\n        // คะแนน = วัดกับทุกเรื่องที่ชอบ (s1 + s2/2 + s3/4 ...) + คะแนนคนดูเล็กน้อย\n        // เลือกทีละช่อง: เรื่องที่ชอบเรื่องไหนได้ช่องไปแล้ว หนังจากเรื่องนั้นลดคะแนนช่องละ 0.5 → ทุกแนวที่ชอบสลับกันทั้งแถว\n        // ภาคเดียวกัน (Naruto / Naruto: Shippuden) ขึ้นแค่เรื่องเดียว ภาคที่เหลือต่อท้ายเมื่อแถวยังไม่เต็ม\n        const FOR_YOU_SAME_SEED = 0.5;\n        function titleRoot(m) {\n            return String(m.Title_EN || m.Title || "").toLowerCase().split(/[:(–]| - /)[0]\n                .replace(/[^a-z0-9\\u0E00-\\u0E7F ]+/g, " ").replace(/\\s+/g, " ").trim();\n        }\n        function sameFranchise(a, b) {\n            if (sameCollection(a, b)) return true;\n            const x = titleRoot(a), y = titleRoot(b);\n            const [s, l] = x.length <= y.length ? [x, y] : [y, x];\n            return s.length >= 4 && (l === s || l.startsWith(s + " "));\n        }\n        function rankForYou(seeds, lists, seen, size) {\n            const skip = new Set(seen), pool = new Map();\n            lists.forEach(list => (list || []).forEach(m => {\n                if (m && m.Poster && !skip.has(m.id) && !pool.has(m.id)) pool.set(m.id, m);\n            }));\n            const weight = keywordWeights([...pool.values(), ...seeds]);\n            const left = [...pool.values()].map(m => {\n                const s = seeds.map((seed, i) => ({ i, v: forYouScore(seed, m, weight) })).sort((a, b) => b.v - a.v);\n                const quality = Math.max(0, toNum(m.Audience_Average) - 5) * 0.2;\n                return { m, from: s.length ? s[0].i : -1, score: s.reduce((sum, x, k) => sum + x.v / 2 ** k, 0) + quality };\n            }).sort((a, b) => b.score - a.score);\n            const used = new Map(), out = [], extra = [];\n            while (out.length < size && left.length) {\n                const value = x => x.score - FOR_YOU_SAME_SEED * (used.get(x.from) || 0);\n                let best = 0;\n                for (let j = 1; j < left.length; j++) if (value(left[j]) > value(left[best])) best = j;\n                const [x] = left.splice(best, 1);\n                if (out.some(m => sameFranchise(m, x.m))) { extra.push(x.m); continue; }\n                used.set(x.from, (used.get(x.from) || 0) + 1);\n                out.push(x.m);\n            }\n            return out.concat(extra).slice(0, size);\n        }\n\n'),
    ('PERS-06 header comment',
     '         *   เรียงทั้งแถวด้วยคะแนนรวม: คล้ายหลายเรื่องที่ชอบ + คะแนนคนดู ขึ้นก่อน (PERS-05)\n',
     '         *   เรียงทั้งแถวด้วยคะแนนรวม: คล้ายหลายเรื่องที่ชอบ + คะแนนคนดู ขึ้นก่อน (PERS-05)\n         *   ทุกเรื่องที่ชอบได้ช่องสลับกัน, keyword ทั่วไป (anime ฯลฯ) นับน้อย, ภาคเดียวกันขึ้นเรื่องเดียว (PERS-06)\n'),
    ('HERO-PERS state and usePersonalHero',
     '        function isHeroCandidate(m, minVotes, cutoff) {',
     '        // แบนเนอร์หมุนจาก For you 10 เรื่องแรก (HERO-PERS) — ยังไม่มีประวัติ/ล้างประวัติ = หนังดังเหมือนเดิม\n        const HERO_PERSONAL = 10;\n        let heroPersonal = [];   // For you 10 เรื่องแรกที่ใช้อยู่ (ว่าง = ใช้หนังดัง)\n        let heroPopular = [];    // pool หนังดังจาก primeHero\n        function usePersonalHero(movies) {\n            const next = (movies || []).filter(m => m && m.Poster).slice(0, HERO_PERSONAL);\n            const list = next.length >= 2 ? next : [];\n            if (list.map(m => m.id).join("|") === heroPersonal.map(m => m.id).join("|")) return false;\n            heroPersonal = list;\n            heroPool = heroPersonal.length ? heroPersonal : heroPopular;\n            heroQueue = [];\n            if (heroPool.length && typeof window !== "undefined" && window.rerollHero) window.rerollHero();\n            return true;\n        }\n\n        function isHeroCandidate(m, minVotes, cutoff) {'),
    ('HERO-PERS prime keeps popular pool separate',
     '            if (cached && Array.isArray(cached.pool) && cached.pool.length && Date.now() - cached.ts < HERO_CACHE_MS) {\n                heroPool = cached.pool;\n            } else {\n                heroPool = await buildHeroPool();\n                if (heroPool.length) writeStore(HERO_POOL_KEY, { ts: Date.now(), pool: heroPool });\n            }\n',
     '            if (cached && Array.isArray(cached.pool) && cached.pool.length && Date.now() - cached.ts < HERO_CACHE_MS) {\n                heroPopular = cached.pool;\n            } else {\n                heroPopular = await buildHeroPool();\n                if (heroPopular.length) writeStore(HERO_POOL_KEY, { ts: Date.now(), pool: heroPopular });\n            }\n            heroPool = heroPersonal.length ? heroPersonal : heroPopular;   // For you อาจโหลดเสร็จก่อน\n'),
    ('HERO-PERS pick in For you order',
     '            if (!heroQueue.length) {\n                const all = heroPool.map(m => m.id);\n                heroQueue = shuffled(heroPool.length > 1 ? all.filter(id => id !== lastHeroId) : all);\n            }\n            const id = heroQueue.shift();\n            writeStore(HERO_QUEUE_KEY, heroQueue);\n',
     '            if (!heroQueue.length) {\n                const all = heroPool.map(m => m.id);\n                const rest = heroPool.length > 1 ? all.filter(id => id !== lastHeroId) : all;\n                heroQueue = heroPersonal.length ? rest : shuffled(rest);   // For you: เรื่องที่ตรงที่สุดก่อน\n            }\n            const id = heroQueue.shift();\n            if (!heroPersonal.length) writeStore(HERO_QUEUE_KEY, heroQueue);   // ไม่ทับสำรับหนังดังที่เก็บไว้\n'),
    ('HERO-PERS subtitle',
     '            document.getElementById("hero-subtitle").innerText = `Featured spotlight · ${movie.Year || ""}`;',
     '            const label = heroPersonal.some(m => m.id === movie.id) ? "For you" : "Featured spotlight";\n            document.getElementById("hero-subtitle").innerText = `${label} · ${movie.Year || ""}`;'),
    ('HERO-PERS feed from For you row',
     '                    movies = fromLikes.concat(mixForYou(genreLists, skip.concat(fromLikes.map(m => m.id)), ROW_SIZE - fromLikes.length));\n',
     '                    movies = fromLikes.concat(mixForYou(genreLists, skip.concat(fromLikes.map(m => m.id)), ROW_SIZE - fromLikes.length));\n                    usePersonalHero(movies);\n'),
    ('HERO-PERS back to popular without For you',
     '                if (!row) continue;\n                if (anchor) anchor.insertAdjacentHTML("afterend", homeRowHtml(row));',
     '                if (!row) { if (key === "foryou") usePersonalHero([]); continue; }\n                if (anchor) anchor.insertAdjacentHTML("afterend", homeRowHtml(row));'),
    ('HERO-PERS load For you right away',
     '            wrap.querySelectorAll(".home-row").forEach(sec => io.observe(sec));\n        }\n',
     '            wrap.querySelectorAll(".home-row").forEach(sec => io.observe(sec));\n            // แบนเนอร์ใช้ For you ด้วย (HERO-PERS) → โหลดแถวนี้ทันทีไม่ต้องรอเลื่อนลงมา\n            if (wrap.querySelector(\'.home-row[data-row="foryou"]\')) loadHomeRow("foryou");\n        }\n'),
    ('SEARCH-02 prefix helper',
     '        async function loadSearch(term, cursor, f = snapshotFilters()) {',
     '        // ค้นชื่อแบบขึ้นต้นด้วยคำค้นใน Firestore (ไทยหรืออังกฤษ) — ใช้ตอน Algolia ล่ม\n        // และเติมเรื่องที่ไม่อยู่ใน Algolia (แผนฟรีเก็บได้ 50,000 เรื่องที่โหวตมากที่สุด) (SEARCH-02)\n        const SEARCH_PREFIX_EXTRA = 5;\n        async function firestorePrefix(raw, cursor, size, primaryOnly = false) {\n            const col = collection(db, targetCollection);\n            const isThai = /[\\u0E00-\\u0E7F]/.test(raw);\n            const searchFields = primaryOnly ? [isThai ? "Title_TH" : "Title_EN"]   // เติมผล Algolia: อ่าน Firestore ให้น้อยที่สุด\n                : isThai ? ["Title_TH", "Title_th", "title_th", "TitleTH", "Title"] : ["Title_EN", "Title"];\n            const titleCase = raw.toLowerCase().replace(/(^|\\s)\\S/g, c => c.toUpperCase());   // "i feel you" → "I Feel You"\n            const variants = isThai ? [raw] : [...new Set([raw.charAt(0).toUpperCase() + raw.slice(1), titleCase, raw, raw.toUpperCase()])];\n            for (const field of searchFields) {\n                for (const v of variants) {\n                    try {\n                        const parts = [orderBy(field), startAt(v), endAt(v + "\\uf8ff")];\n                        if (cursor && cursor.id) parts.push(startAfter(cursor));\n                        parts.push(limit(size));\n                        const res = await getDocs(query(col, ...parts));\n                        if (res.docs.length) return res;\n                    } catch (e) { }\n                }\n            }\n            return { docs: [] };\n        }\n\n        async function loadSearch(term, cursor, f = snapshotFilters()) {'),
    ('SEARCH-02 merge Firestore prefix into Algolia page 1',
     '                    let movies = [], nbPages = 0, scanned = 0;\n                    do {',
     '                    let movies = [], nbPages = 0, scanned = 0;\n                    // หน้าแรก: ค้นชื่อขึ้นต้นใน Firestore ไปพร้อมกัน เผื่อเรื่องที่ไม่อยู่ใน Algolia\n                    const extraP = page === 0\n                        ? firestorePrefix(raw, null, SEARCH_PREFIX_EXTRA, true).then(s => s.docs.map(docToMovie)).catch(() => [])\n                        : Promise.resolve([]);\n                    do {'),
    ('SEARCH-02 merge results',
     '                    } while (movies.length < PAGE_SIZE && page < nbPages && scanned < maxPages);\n                    return {',
     '                    } while (movies.length < PAGE_SIZE && page < nbPages && scanned < maxPages);\n                    const have = new Set(movies.map(m => m.id));\n                    const extra = (await extraP).filter(m => m.Poster && !have.has(m.id) && passesFilters(m, f));\n                    if (extra.length) movies = sortSearchHits([...extra, ...movies], raw);\n                    return {'),
    ('SEARCH-02 fallback uses helper',
     '            const searchFields = isThai ? ["Title_TH", "Title_th", "title_th", "TitleTH", "Title"] : ["Title_EN", "Title"];\n            const variants = isThai ? [raw] : [raw.charAt(0).toUpperCase() + raw.slice(1), raw, raw.toUpperCase()];\n            let snap = { docs: [] };\n\n            outer:\n            for (const f of searchFields) {\n                for (const v of variants) {\n                    try {\n                        const parts = [orderBy(f), startAt(v), endAt(v + "\\uf8ff")];\n                        if (cursor && cursor.id) parts.push(startAfter(cursor));\n                        parts.push(limit(PAGE_SIZE));\n                        const res = await getDocs(query(col, ...parts));\n                        if (res.docs.length) { snap = res; break outer; }\n                    } catch (e) { }\n                }\n            }\n',
     '            const snap = await firestorePrefix(raw, cursor, PAGE_SIZE);\n'),
    ('SEARCH-02 fallback drops unused locals',
     '            const col = collection(db, targetCollection);\n            const isThai = /[\\u0E00-\\u0E7F]/.test(raw);\n            const lower = raw.toLowerCase();\n',
     '            const lower = raw.toLowerCase();\n'),
    ('SIM-03 niche floor',
     '        const FAMILIAR = { share: 0.2, floor: 5000, keep: 8 };   // ตัดหนังที่โหวตน้อยกว่า 20% ของต้นทาง (ขั้นต่ำ 5,000) ถ้ายังเหลือ ≥ 8 เรื่อง',
     '        // ตัดหนังที่โหวตน้อยกว่า 20% ของต้นทาง (ขั้นต่ำ 5,000) ถ้ายังเหลือ ≥ 8 เรื่อง\n        // ต้นทางโหวตน้อยเอง (ซีรีส์เฉพาะกลุ่ม เช่น BL) → ขั้นต่ำลดเหลือครึ่งหนึ่งของโหวตต้นทาง ไม่ตัดเรื่องแนวเดียวกันทิ้ง (SIM-03)\n        const FAMILIAR = { share: 0.2, floor: 5000, nicheShare: 0.5, keep: 8 };'),
    ('SIM-03 keepFamiliar',
     '            const min = Math.max(FAMILIAR.floor, getVotes(base) * FAMILIAR.share);',
     '            const votes = getVotes(base);\n            const min = Math.max(Math.min(FAMILIAR.floor, votes * FAMILIAR.nicheShare), votes * FAMILIAR.share);'),
    ('SIM-03 preScore weighted',
     '        function preScore(base, cand) {\n            return keywordOverlap(base, cand) * 2.2',
     '        // weight (ไม่บังคับ) = น้ำหนัก keyword ตามความหายากจาก keywordWeights + ภาษาเดียวกันได้คะแนนเพิ่ม (SIM-03)\n        function preScore(base, cand, weight) {\n            const lang = getLanguage(base);\n            return (weight ? weightedKeywordOverlap(base, cand, weight) : keywordOverlap(base, cand)) * 2.2\n                 + (weight && lang && lang === getLanguage(cand) ? 0.8 : 0)'),
    ('SIM-03 fallbackRank weight',
     '        function fallbackRank(base, candidates) {\n            return candidates\n                .map(m => ({ movie: m, score: preScore(base, m) }))',
     '        function fallbackRank(base, candidates, weight) {\n            return candidates\n                .map(m => ({ movie: m, score: preScore(base, m, weight) }))'),
    ('SIM-03 pool helper',
     '        async function fetchSimilarMovies(currentMovie) {',
     '        // ตัวเลือกของ More like this = ตัวคัดเดิม + เรื่องภาษาเดียวกันที่ดัง (ตัวเดียวกับ For you) ไม่รวมภาคในชุดเดียวกัน (SIM-03)\n        async function similarPool(base) {\n            const [pool, same] = await Promise.all([buildCandidatePool(base), loadSameLanguage(base)]);\n            const byId = new Map();\n            [...pool, ...same].forEach(m => {\n                if (m && m.id !== base.id && m.Poster && m.Poster !== "N/A" && !sameCollection(base, m) && !byId.has(m.id)) byId.set(m.id, m);\n            });\n            return [...byId.values()];\n        }\n\n        async function fetchSimilarMovies(currentMovie) {'),
    ('SIM-03 use pool',
     '                let candidates = await buildCandidatePool(currentMovie);\n                if (!candidates.length) {',
     '                let candidates = await similarPool(currentMovie);\n                if (!candidates.length) {'),
    ('SIM-03 weighted shortlist',
     '                candidates = keepFamiliar(currentMovie, candidates);\n\n                const shortlist = candidates\n                    .map(m => ({ m, s: preScore(currentMovie, m) }))',
     '                candidates = keepFamiliar(currentMovie, candidates);\n                const weight = keywordWeights([...candidates, currentMovie]);\n\n                const shortlist = candidates\n                    .map(m => ({ m, s: preScore(currentMovie, m, weight) }))'),
    ('SIM-03 filler weight',
     '                                    .sort((a, b) => preScore(currentMovie, b) - preScore(currentMovie, a));',
     '                                    .sort((a, b) => preScore(currentMovie, b, weight) - preScore(currentMovie, a, weight));'),
    ('SIM-03 fallback weight',
     '                    picks = fallbackRank(currentMovie, candidates);',
     '                    picks = fallbackRank(currentMovie, candidates, weight);'),
    ('CHAT-02 plan prompt + history helpers',
     '        const PLAN_SYSTEM = `คุณคือตัวแปลงคำถามเรื่องหนังให้เป็นแผนค้นฐานข้อมูล\nตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:\n{"mode":"title|genre|top|discovery|similar|current|chat","title":"","genre":"","minVotes":0}\nความหมายของ mode:\n- current  = ถามถึงหนังที่ผู้ใช้กำลังเปิดดูอยู่ (เช่น "เรื่องนี้", "this movie", ขอวิเคราะห์/สรุป/ควรดูไหม) ไม่ต้องค้นเพิ่ม\n- similar  = ขอหนังที่คล้าย/แนวเดียวกับหนังที่กำลังเปิดดูอยู่\n- title    = ถามถึงหนังเรื่องอื่นโดยระบุชื่อ (ใส่ชื่อใน title)\n- genre    = ขอหนังตามแนว\n- top      = ขอหนังคะแนนสูงสุด\n- discovery= ขอหนังดีแต่คนรู้จักน้อย\n- chat     = คำถามความรู้ทั่วไปเกี่ยวกับวงการภาพยนตร์ที่ไม่ต้องใช้ข้อมูลในเว็บ\nถ้า CURRENT_MOVIE เป็น none ห้ามตอบ current หรือ similar\ngenre ให้เลือกจาก: action, drama, scifi, comedy, horror, animation, thriller, adventure, fantasy, crime, romance, mystery, family, war, history, music, documentary, western, reality`;\n\n',
     '        const PLAN_SYSTEM = `คุณคือตัวแปลงคำถามเรื่องหนังให้เป็นแผนค้นฐานข้อมูล\nตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:\n{"mode":"title|genre|keyword|top|discovery|similar|current|chat","title":"","genre":"","keyword":"","language":"","media":"","minVotes":0}\nความหมายของ mode:\n- current  = ถามถึงหนังที่ผู้ใช้กำลังเปิดดูอยู่ (เช่น "เรื่องนี้", "this movie", ขอวิเคราะห์/สรุป/ควรดูไหม) ไม่ต้องค้นเพิ่ม\n- similar  = ขอหนังที่คล้าย/แนวเดียวกับหนังที่กำลังเปิดดูอยู่\n- title    = ถามถึงหนังเรื่องอื่นโดยระบุชื่อ (ใส่ชื่อใน title)\n- genre    = ขอหนังตามแนวกว้าง ๆ (ใส่ genre)\n- keyword  = ขอหนังตามหัวข้อหรือกลุ่มเฉพาะที่ไม่ใช่ประเภทหนัง เช่น ซีรีส์วาย/BL, ซอมบี้, ย้อนเวลา, ซูเปอร์ฮีโร่, ชีวิตมหาวิทยาลัย (ใส่ keyword)\n- top      = ขอหนังคะแนนสูงสุด\n- discovery= ขอหนังดีแต่คนรู้จักน้อย\n- chat     = คำถามความรู้ทั่วไปเกี่ยวกับวงการภาพยนตร์ที่ไม่ต้องใช้ข้อมูลในเว็บ\nช่องเสริม (ใช้กับ genre / keyword / top):\n- keyword  = keyword ภาษาอังกฤษตัวพิมพ์เล็กแบบที่ TMDB ใช้ ใส่ได้หลายคำคั่นด้วย , (ตรงคำใดคำหนึ่งก็พอ) เช่น "boys\' love, gay theme", "zombie", "time travel", "superhero"\n- language = รหัสภาษา ISO 639-1 เมื่อผู้ใช้ระบุประเทศ/ภาษา หรือหัวข้อนั้นมาจากประเทศเดียวเป็นหลัก เช่น ไทย = th, เกาหลี/K-drama = ko, ญี่ปุ่น/อนิเมะ = ja, จีน = zh, ฝรั่ง = en, ซีรีส์วาย/BL ที่ไม่ระบุประเทศ = th; ไม่เกี่ยว = ""\n- media    = "series" เมื่อขอซีรีส์, "movie" เมื่อขอหนัง/ภาพยนตร์, ไม่ระบุ = ""\nบทสนทนาก่อนหน้า (HISTORY):\n- คำถามต่อเนื่อง เช่น "ขออีก", "แบบเกาหลีบ้าง", "แล้วที่เป็นหนังล่ะ" ให้คง mode / genre / keyword / language / media จาก HISTORY แล้วเปลี่ยนเฉพาะส่วนที่ผู้ใช้ขอใหม่\n- "เรื่องแรก", "เรื่องที่สอง" ฯลฯ = เรื่องตามลำดับใน [แนะนำ: ...] ของบอทข้อความล่าสุด ให้ตอบ mode title พร้อมชื่อเรื่องนั้น\n- คำถามที่พูดถึงหนังเรื่องอื่นหรือหัวข้ออื่นชัดเจน ไม่ต้องยึด CURRENT_MOVIE\nถ้า CURRENT_MOVIE เป็น none ห้ามตอบ current หรือ similar\ngenre ให้เลือกจาก: action, drama, scifi, comedy, horror, animation, thriller, adventure, fantasy, crime, romance, mystery, family, war, history, music, documentary, western, reality`;\n\n        // ประวัติแชทที่ส่งให้ขั้นวางแผนค้นหา (CHAT-02): 4 ข้อความล่าสุด ตัดให้สั้น + ชื่อเรื่องที่บอทแนะนำ\n        const PLAN_HISTORY = 4;\n        function planHistoryText(history) {\n            return (history || []).slice(-PLAN_HISTORY).map(h => {\n                const text = String(h.text || "").replace(/\\s+/g, " ").slice(0, 240);\n                const picks = h.picks && h.picks.length ? ` [แนะนำ: ${h.picks.join(", ")}]` : "";\n                return `${h.role === "user" ? "ผู้ใช้" : "บอท"}: ${text}${picks}`;\n            }).join("\\n");\n        }\n\n        // ข้อความของบอทที่เก็บในประวัติ + ชื่อเรื่องบนการ์ดที่แนะนำ (คำถาม "เรื่องที่สอง" จะได้รู้ว่าหมายถึงเรื่องไหน)\n        function modelTurn(reply) {\n            const picks = (reply.movies || []).map(m => `${getEnglishTitle(m)}${m.Year ? ` (${m.Year})` : ""}`);\n            return picks.length ? { role: "model", text: reply.text, picks } : { role: "model", text: reply.text };\n        }\n\n'),
    ('CHAT-02 compactMovie language',
     '                keywords: getKeywords(m).slice(0, 8),\n                plot: m.Plot ? String(m.Plot).slice(0, 180) : null',
     '                language: getLanguage(m) || null,\n                keywords: getKeywords(m).slice(0, 8),\n                plot: m.Plot ? String(m.Plot).slice(0, 180) : null'),
    ('CHAT-02 history shows picks',
     '            history.forEach(h => {\n                const role = h.role === "user" ? "user" : "model";\n                if (!turns.length && role !== "user") return;\n                if (turns.length && turns[turns.length - 1].role === role) {\n                    turns[turns.length - 1].parts[0].text += "\\n" + h.text;\n                } else {\n                    turns.push({ role, parts: [{ text: h.text }] });\n                }\n            });',
     '            history.forEach(h => {\n                const role = h.role === "user" ? "user" : "model";\n                const text = h.picks && h.picks.length ? `${h.text}\\n[แนะนำ: ${h.picks.join(", ")}]` : h.text;\n                if (!turns.length && role !== "user") return;\n                if (turns.length && turns[turns.length - 1].role === role) {\n                    turns[turns.length - 1].parts[0].text += "\\n" + text;\n                } else {\n                    turns.push({ role, parts: [{ text }] });\n                }\n            });'),
    ('CHAT-02 taste retrieval',
     '        async function candidatesFromPlan(plan, currentMovieObj) {',
     '        // ค้นตาม keyword / ภาษา / หนัง-ซีรีส์ ที่ขั้นวางแผนกรอกมา (CHAT-02)\n        // Firestore ค้นใน keyword ไม่ได้ → ดึงเรื่องดังของภาษานั้น (หรือประเภทนั้น / ทั้งฐาน) มา 150 เรื่องแล้วกรองในเครื่อง\n        const CHAT_TASTE_POOL = 150;\n        const CHAT_TASTE_MIN = 5;                    // ตรง keyword น้อยกว่านี้ → ค้นเพิ่มในภาษาด้านล่าง\n        const CHAT_TASTE_LANGS = ["th", "ko", "ja", "zh"];\n        const CHAT_TASTE_PER_LANG = 60;\n        function normKeyword(s) { return String(s || "").toLowerCase().replace(/[^\\p{L}\\p{N}]+/gu, " ").trim(); }\n        function keywordMatcher(raw) {\n            const wants = String(raw || "").split(",").map(normKeyword).filter(Boolean);\n            if (!wants.length) return null;\n            // เทียบทั้งคำ: "bl" ตรงกับ "boys\' love (bl)" แต่ไม่ตรงกับ "blood"\n            return m => getKeywords(m).some(k => {\n                const have = ` ${normKeyword(k)} `;\n                return wants.some(w => have.includes(` ${w} `));\n            });\n        }\n        function mediaWanted(plan) {\n            return plan.media === "series" ? true : plan.media === "movie" ? false : null;\n        }\n\n        async function candidatesByTaste(plan) {\n            const lang = String(plan.language || "").trim().toLowerCase();\n            const genre = GENRE_MAP[plan.genre] || "";\n            const byKeyword = keywordMatcher(plan.keyword);\n            const series = mediaWanted(plan);\n            let snap;\n            if (lang) {\n                snap = await runQuerySafe(\n                    [where("Language", "==", lang), orderBy("Popularity", "desc"), limit(CHAT_TASTE_POOL)],\n                    [where("Language", "==", lang), limit(CHAT_TASTE_POOL)]\n                );\n            } else if (genre) {\n                snap = await runQuerySafe(\n                    [genreWhere(genre), orderBy("Popularity", "desc"), limit(CHAT_TASTE_POOL)],\n                    [genreWhere(genre), limit(CHAT_TASTE_POOL)]\n                );\n            } else {\n                snap = await runQuerySafe([orderBy("Popularity", "desc"), limit(CHAT_TASTE_POOL)], [limit(CHAT_TASTE_POOL)]);\n            }\n            let out = snap.docs.map(docToMovie)\n                .filter(m => (!lang || getLanguage(m) === lang) && (!lang || !genre || matchesGenre(m, genre))\n                    && (series === null || isSeries(m) === series));\n            if (byKeyword) {\n                let hit = out.filter(byKeyword);\n                // ไม่ระบุภาษาและเรื่องดังทั้งฐานตรง keyword น้อย (เช่น BL) → ดูเรื่องดังของภาษาเอเชียที่มีซีรีส์เฉพาะกลุ่มเยอะเพิ่ม\n                if (!lang && hit.length < CHAT_TASTE_MIN) {\n                    const more = await Promise.all(CHAT_TASTE_LANGS.map(l => runQuerySafe(\n                        [where("Language", "==", l), orderBy("Popularity", "desc"), limit(CHAT_TASTE_PER_LANG)],\n                        [where("Language", "==", l), limit(CHAT_TASTE_PER_LANG)]\n                    ).then(r => r.docs.map(docToMovie)).catch(() => [])));\n                    const seen = new Set(hit.map(m => m.id));\n                    more.flat().filter(m => !seen.has(m.id) && byKeyword(m) && (!genre || matchesGenre(m, genre))\n                        && (series === null || isSeries(m) === series)).forEach(m => { seen.add(m.id); hit.push(m); });\n                }\n                out = hit.length ? hit : (lang ? out : []);   // ไม่มีเรื่องตรง keyword: มีภาษา → ใช้เรื่องภาษานั้น, ไม่มี → ไปใช้แผนเดิม\n            }\n            if (plan.mode === "top") out.sort((a, b) => toNum(b.Audience_Average) - toNum(a.Audience_Average));\n            return out;\n        }\n\n        async function candidatesFromPlan(plan, currentMovieObj) {'),
    ('CHAT-02 similar uses More like this pool',
     '                if (plan.mode === "similar" && currentMovieObj) {\n                    const pool = await buildCandidatePool(currentMovieObj);\n                    docs = pool\n                        .map(m => ({ m, s: preScore(currentMovieObj, m) }))',
     '                if (plan.mode === "similar" && currentMovieObj) {\n                    const pool = keepFamiliar(currentMovieObj, await similarPool(currentMovieObj));   // ตัวเดียวกับ More like this (SIM-03)\n                    const weight = keywordWeights([...pool, currentMovieObj]);\n                    docs = pool\n                        .map(m => ({ m, s: preScore(currentMovieObj, m, weight) }))'),
    ('CHAT-02 use taste retrieval',
     '                if (!docs.length && plan.mode === "title" && plan.title) docs = await searchByTitle(plan.title);\n',
     '                if (!docs.length && plan.mode === "title" && plan.title) docs = await searchByTitle(plan.title);\n\n                if (!docs.length && (plan.keyword || plan.language) && ["genre", "keyword", "top"].includes(plan.mode)) {\n                    docs = await candidatesByTaste(plan);\n                }\n'),
    ('CHAT-02 media filter',
     '            if (currentMovieObj) docs = docs.filter(m => m.id !== currentMovieObj.id);\n            if (plan.minVotes) docs = docs.filter(m => getVotes(m) >= toNum(plan.minVotes));',
     '            if (currentMovieObj) docs = docs.filter(m => m.id !== currentMovieObj.id);\n            const series = mediaWanted(plan);\n            if (series !== null && docs.some(m => isSeries(m) === series)) docs = docs.filter(m => isSeries(m) === series);\n            if (plan.minVotes) docs = docs.filter(m => getVotes(m) >= toNum(plan.minVotes));'),
    ('CHAT-02 plan sees history',
     '                    contents: [{ role: "user", parts: [{ text:\n                        `CURRENT_MOVIE: ${currentCtx ? `${currentCtx.title} (${currentCtx.year || "?"})` : "none"}\\nคำถาม: ${userText}` }] }],\n                    json: true, temperature: 0.1, maxTokens: 300',
     '                    contents: [{ role: "user", parts: [{ text:\n                        `CURRENT_MOVIE: ${currentCtx ? `${currentCtx.title} (${currentCtx.year || "?"})` : "none"}\\n` +\n                        `HISTORY:\\n${planHistoryText(history) || "(ไม่มี)"}\\nคำถาม: ${userText}` }] }],\n                    json: true, temperature: 0.1, maxTokens: 400'),
    ('CHAT-02 store picks in history',
     '                chatHistory.push({ role: "model", text: reply.text });',
     '                chatHistory.push(modelTurn(reply));'),
    ('AI-MODELS-01 fallback models still served by Google',
     '        const GEMINI_FALLBACK_MODELS = ["gemini-3.1-flash-lite-preview", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"];',
     '        // Gemini 2.0 ปิดไปแล้ว (1 มิ.ย. 2026) และ 2.5 ตอบ 404 → สำรองด้วยรุ่นที่ยังเปิดและใช้แบบฟรีได้ (AI-MODELS-01)\n        const GEMINI_FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite-preview", "gemini-3.6-flash"];\n        const GEMINI_RETRY_MS = 1000;   // Google ตอบ 500/503 (คนใช้เยอะชั่วคราว) → รอแล้วลองรุ่นเดิมอีกครั้งก่อนเปลี่ยนรุ่น'),
    ('AI-MODELS-01 retry overloaded model, stop on proxy rate limit',
     '            for (const model of models) {\n                try {',
     '            const retried = new Set();\n            for (let i = 0; i < models.length; i++) {\n                const model = models[i];\n                try {'),
    ('AI-MODELS-01 status handling',
     '                    if (!res.ok) {\n                        lastErr = new Error(`${model}: ${res.status}`);\n                        if (res.status === 404 || res.status === 400) continue;\n                        throw lastErr;\n                    }',
     '                    if (!res.ok) {\n                        lastErr = new Error(`${model}: ${res.status}`);\n                        lastErr.status = res.status;\n                        const body = res.status === 429 && res.text ? await res.text().catch(() => "") : "";\n                        // 429 จาก Cloud Function = เกิน 20 ครั้ง/นาที ลองรุ่นอื่นก็โดนเหมือนกัน → หยุดเลย\n                        if (/too many requests/i.test(body)) { lastErr.fatal = true; throw lastErr; }\n                        if ((res.status === 500 || res.status === 503) && !retried.has(model)) {\n                            retried.add(model);\n                            await new Promise(r => setTimeout(r, GEMINI_RETRY_MS));\n                            models.splice(i + 1, 0, model);\n                        }\n                        continue;   // 400/404/429 โควตา/5xx → รุ่นถัดไป (โควตาฟรีนับแยกต่อรุ่น)\n                    }'),
    ('AI-MODELS-01 keep fatal error',
     '                } catch (err) {\n                    lastErr = err;\n                }\n            }\n            throw lastErr || new Error("Gemini request failed");',
     '                } catch (err) {\n                    if (err.fatal) throw err;\n                    lastErr = err;\n                }\n            }\n            throw lastErr || new Error("Gemini request failed");'),
    ('CHAT-03 answer with the site verdict',
     '- recommendSide.verdict = ข้อสรุปของเว็บว่าควรเชื่อฝั่งไหน ให้อธิบายเหตุผลโดยอ้างค่าเฉลี่ยสองฝั่งและตัวเลข S.D. ประกอบ',
     '- recommendSide.verdict = ข้อสรุปของเว็บว่าควรเชื่อฝั่งไหน เมื่อผู้ใช้ถามว่าควรเชื่อฝั่งไหน ให้ตอบตามข้อสรุปนี้เท่านั้น: พูดข้อสรุปตามคำเดิมในประโยคแรก แล้วค่อยอธิบายเหตุผลโดยอ้างค่าเฉลี่ยสองฝั่งและตัวเลข S.D. ประกอบ ห้ามเลือกฝั่งเอง (รวมถึงตอนที่ข้อสรุปเป็น ตรงกัน / เห็นต่าง / เฉพาะกลุ่ม)'),
    ('CHAT-03 rule 8',
     '7. picks = docId ที่อยากแนะนำ ต้องมาจาก DATABASE_CANDIDATES เท่านั้น (สูงสุด 3) ถ้าไม่มีให้เป็น []',
     '7. picks = docId ที่อยากแนะนำ ต้องมาจาก DATABASE_CANDIDATES เท่านั้น (สูงสุด 3) ถ้าไม่มีให้เป็น []\n8. ห้ามแนะนำให้เชื่อฝั่งที่ขัดกับ recommendSide.verdict ของเว็บ แม้ค่าเฉลี่ยฝั่งหนึ่งจะสูงกว่า'),
]
for name, old, new in PATCHES:
    n = src.count(old)
    if n != 1:
        sys.exit(f"{name}: expected 1 match, found {n}")
    src = src.replace(old, new)
    print("applied", name)
pathlib.Path(sys.argv[2]).write_text(src, encoding="utf-8")
