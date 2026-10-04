# CineMeter — ชุดทดสอบ Business Logic

ทดสอบโค้ดจริงของเว็บแอป: `extract.mjs` ดึงฟังก์ชันจากไฟล์ HTML แบบคำต่อคำมาเป็นโมดูล แล้วรันเทสต์ด้วย Node.js test runner
ส่วนที่ต่อเน็ต (Firestore / Algolia / Gemini) ถูกแทนด้วยของจำลองใน `helpers/`

## รัน

ต้องมี Node.js 22 ขึ้นไป วางโฟลเดอร์นี้ไว้ข้าง `cinemeter-v7_8.html` และ `cinemeter-v7_9.html`

```bash
cd tests
./run-tests.sh v7_8     # ก่อนแก้: ผ่าน 75/90
./run-tests.sh v7_9     # ส่งมอบ: ผ่าน 90/90
python3 make-v7_9.py ../cinemeter-v7_8.html ../cinemeter-v7_9.html   # สร้าง v7_9 จาก v7_8 ใหม่ (แก้ 9 จุด + ย้าย Gemini key ไป Cloud Function 3 จุด + จัดอันดับแบบถ่วงโหวต 8 จุด)
```

ผลอยู่ใน `results/`: `*-spec.txt` (อ่านง่าย + coverage), `*-junit.xml`, `test-table.md`, ภาพ smoke test

## ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `extract.mjs`, `lib-extract.mjs` | ดึงโค้ดจาก HTML → `cinemeter-logic-<version>.mjs` (+ แผนที่เลขบรรทัด `*-map.txt`) |
| `test/*.test.mjs` | เทสต์ 90 เคส แบ่งกลุ่ม BL / AI / SW / RB / SEC (`09-weighted-rank` = จัดอันดับแบบถ่วงโหวต) |
| `helpers/fake-firestore.mjs` | Firestore จำลอง (เทียบชนิดข้อมูลเข้มงวด, error เมื่อไม่มี composite index) |
| `helpers/dataset.mjs` | ข้อมูลสังเคราะห์รูปแบบเดียวกับ MOVIES |
| `helpers/dom-stub.mjs` | DOM จำลองสำหรับฟังก์ชันที่แตะหน้าจอ |
| `make-v7_9.py` | แพตช์แก้บั๊กที่พบ + เปลี่ยนแชทบอทให้เรียก Gemini ผ่าน Cloud Function + จัดอันดับแบบถ่วงโหวต + กฎ Recommend side จากค่าเฉลี่ย (RULE-02) + ตาราง Trending now เต็มแถว (GRID-01) (แต่ละจุดต้องเจอแค่ครั้งเดียว) |
| `smoke.py` | เปิดทั้งสองเวอร์ชันใน Chromium ตรวจ JavaScript error |
| `build-check-page.mjs`, `check-page/` | สร้างหน้า `cinemeter-live-check.html` และทดสอบหน้านั้นกับบริการจำลอง |
