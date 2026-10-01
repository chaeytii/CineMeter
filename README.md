# CineMeter — Check the vibe before you watch

เว็บช่วยเลือกหนัง รวมคะแนนจาก IMDb, TMDB, Rotten Tomatoes และ Metacritic ไว้ในหน้าเดียว
แล้วใช้ค่า S.D. (ความห่างของคะแนนแต่ละแหล่ง) บอกว่าหนังเรื่องนั้นควรเชื่อคะแนนฝั่งนักวิจารณ์หรือฝั่งคนดู

- **เปิดเว็บ:** https://⟨ชื่อผู้ใช้ GitHub⟩.github.io/⟨ชื่อ repo⟩/
- **ผู้จัดทำ:** ⟨ชื่อ-นามสกุล / รหัสนักศึกษา⟩
- **รายวิชา:** ⟨ชื่อวิชา⟩ — โปรเจกต์ Final

## ในนี้มีอะไร

| ไฟล์ / โฟลเดอร์ | คืออะไร |
|---|---|
| `index.html` | ตัวเว็บที่ GitHub Pages เปิด (เหมือน `cinemeter-v7_9.html` ทุกตัวอักษร) |
| `cinemeter-v7_9.html` | เวอร์ชันส่งมอบ แก้จุดผิด 7 จุดที่ชุดทดสอบพบแล้ว และเรียก Gemini ผ่าน Cloud Function (ไม่มี API key ในหน้าเว็บ) |
| `cinemeter-v7_8.html` | เวอร์ชันก่อนแก้ เก็บไว้ให้ชุดทดสอบเทียบก่อน–หลัง |
| `cinemeter-live-check.html` | หน้าตรวจข้อมูลจริง: สุ่มหนังจากฐานข้อมูล คำนวณคะแนนซ้ำ แล้วเทียบกับค่าที่เก็บไว้ (อ่านอย่างเดียว ไม่แก้ข้อมูล) |
| `functions/` | Firebase Cloud Function `gemini`: ตัวกลางที่ถือ Gemini API key ไว้ฝั่ง server แชทบอทบนเว็บเรียกผ่านตัวนี้ (รับเฉพาะเว็บของเรา, จำกัดรุ่นโมเดล/ความยาว/จำนวนครั้งต่อนาที) |
| `firebase.json`, `.firebaserc` | ตั้งค่าให้คำสั่ง `firebase deploy` รู้ว่าจะ deploy `functions/` ขึ้นโปรเจกต์ `movie-858f6` |
| `firebase-upload/` | สคริปต์ข้อมูล: `fetch_movies.py` ดึงข้อมูลหนังทั้งชุด (TMDB + OMDb + IMDb), `import_all_to_firebase.js` เอาขึ้น Firestore, `weekly_update.py` อัปเดตรายสัปดาห์เฉพาะส่วนที่เปลี่ยน |
| `.github/workflows/weekly-update.yml` | ตั้งเวลาให้ GitHub รัน `weekly_update.py` ทุกวันจันทร์ 03:00 (เวลาไทย) |
| `tests/` | ชุดทดสอบอัตโนมัติ 81 ข้อ และผลการทดสอบใน `tests/results/` |

## ผลการทดสอบ

| เวอร์ชัน | ผ่าน | ไม่ผ่าน |
|---|---|---|
| v7_8 (ก่อนแก้) | 73 / 81 | 8 |
| v7_9 (ส่งมอบ) | 81 / 81 | 0 |

รายการทุกข้ออยู่ที่ [`tests/results/test-table.md`](tests/results/test-table.md)

## รันชุดทดสอบซ้ำ

ต้องมี Node.js 22 ขึ้นไป

```bash
cd tests
./run-tests.sh v7_8     # ก่อนแก้: ผ่าน 73/81
./run-tests.sh v7_9     # ส่งมอบ: ผ่าน 81/81
```

## อัปโหลดข้อมูลหนังขึ้น Firestore

วางไฟล์ 3 ไฟล์นี้ไว้ในโฟลเดอร์ `firebase-upload/` (ทั้ง 3 ไฟล์**ห้ามขึ้น GitHub** — `.gitignore` กันไว้แล้ว)
- `serviceAccountKey.json` — กุญแจแอดมินของ Firebase (Firebase Console → Project settings → Service accounts → Generate new private key)
- `firebase_movies_1980_2026.json` และ `firebase_genre_analysis_1980_2026.json` — ข้อมูลที่ได้จากสคริปต์ Python

```bash
cd firebase-upload
npm install
node import_all_to_firebase.js
```

สคริปต์เขียนแบบ merge (เรื่องที่มีอยู่แล้วจะถูกอัปเดต ไม่ถูกลบ) และเขียนทุกเรื่องทุกครั้งที่รัน — ทั้งฐานประมาณ 73,000 writes ต่อรอบ

## อัปเดตข้อมูลอัตโนมัติ (ทุกสัปดาห์)

GitHub Actions รัน `firebase-upload/weekly_update.py` ทุกวันจันทร์ 03:00 เวลาไทย แต่ละรอบ:
1. อัปเดตคะแนน/โหวต IMDb ทุกเรื่องจาก [ไฟล์ฟรีของ IMDb](https://datasets.imdbws.com/) (ไม่ใช้โควตา OMDb)
2. อัปเดต Popularity และคะแนน TMDB ของหนัง 3 ปีล่าสุด (หมวด Trending now)
3. เพิ่มเรื่องใหม่ที่โหวต IMDb เกิน 500 (ปี 1980–ปีปัจจุบัน) เรียงโหวตมากก่อน — เรื่องที่ OMDb ตอบไม่ได้จะไม่ถูกเพิ่ม (ทำต่อรอบหน้า)
4. อัปเดตคะแนน Rotten Tomatoes / Metacritic ของหนังที่ออกฉายไม่เกิน 12 เดือน
5. เติมคะแนนนักวิจารณ์ให้หนังเก่าที่ยังไม่มีทั้ง RT และ Metacritic (เรื่องที่ OMDb ไม่มีคะแนนจริงจะไม่ถูกถามซ้ำภายใน 90 วัน — ดูจากฟิลด์ `omdbCheckedAt`)
6. คำนวณ `GENRE_ANALYSIS` ใหม่ แล้วเขียน Firestore **เฉพาะเรื่องที่ค่าเปลี่ยน**
7. ส่งเรื่องที่เปลี่ยนเข้า **Algolia** (ช่องค้นหา) ด้วย — แทนที่ทั้ง index เมื่อข้อมูลไม่ตรงกัน หรือรอบแรกของทุกเดือน (settings ของ index เดิมถูกเก็บไว้)

**งบ OMDb ต่อรอบ** = `OMDB_DAILY_LIMIT` (ค่าเริ่มต้น 450,000 = 90% ของ plan Standard 500,000 ครั้ง/วัน) แบ่งเป็น เรื่องใหม่ ≤ 60%, รีเฟรชหนังที่เพิ่งออก ≤ 20%, ที่เหลือใช้เติมคะแนนหนังเก่า
ถ้าเปลี่ยน plan: Settings → Secrets and variables → Actions → แท็บ **Variables** → New repository variable ชื่อ `OMDB_DAILY_LIMIT` ใส่ตัวเลขประมาณ 90% ของโควตาต่อวัน (ไม่ต้องแก้โค้ด)
dry run เรียก OMDb จริงไม่เกิน 20 ครั้ง (ไม่กินโควตาของวัน) และแสดงจำนวนเรื่องที่ "จะทำ" ในตารางสรุป

สูตรคะแนนและ S.D. ใช้ฟังก์ชันเดียวกับ `fetch_movies.py` คะแนนที่ไม่มีข้อมูลเก็บเป็น `"N/A"` (รอบแรกจะซ่อมเรื่องที่ import ชุดแรกเขียนเป็น `0` ไว้)

**ตั้งค่าครั้งแรก** — GitHub → repo นี้ → Settings → Secrets and variables → Actions → New repository secret สร้าง 4 ตัว:

| ชื่อ | ค่า |
|---|---|
| `TMDB_API_KEY` | API key ของ TMDB |
| `OMDB_API_KEYS` | OMDb key ทุกตัว คั่นด้วย comma เช่น `key1,key2` |
| `FIREBASE_SERVICE_ACCOUNT` | เปิดไฟล์ `serviceAccountKey.json` ด้วย Notepad แล้วคัดลอก**ทั้งไฟล์**มาวาง |
| `ALGOLIA_ADMIN_KEY` | Algolia dashboard → Settings → API Keys → **Admin API Key** (ไม่ใช่ Search-Only) — ถ้าไม่ตั้ง ระบบจะข้ามการ sync ช่องค้นหา |

**ทดสอบ** — แท็บ Actions → Weekly data update → Run workflow (ติ๊ก Dry run ไว้ = คำนวณอย่างเดียว ไม่เขียนฐานข้อมูล) → เปิดผลดูตารางสรุป ถ้าตัวเลขสมเหตุสมผลค่อยรันอีกครั้งโดยเอาติ๊กออก หลังจากนั้นระบบจะรันเองทุกสัปดาห์

- workflow ที่ตั้งเวลาจะทำงานเฉพาะบน branch `main` และ GitHub จะหยุดตั้งเวลาเองถ้า repo ไม่มีความเคลื่อนไหว 60 วัน (กดเปิดใหม่ได้ในแท็บ Actions)
- รันในเครื่องเอง: `cd firebase-upload && pip install -r requirements.txt` แล้วตั้ง `TMDB_API_KEY`, `OMDB_API_KEYS`, `GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json` และรัน `python weekly_update.py --dry-run`
- ทดสอบโค้ด: `cd firebase-upload && python -m unittest test_weekly_update.py`

## Deploy แชทบอท (Cloud Function)

ทำครั้งแรกครั้งเดียว ต้องมี Node.js 22 และโปรเจกต์ Firebase เป็นแผน Blaze

```bash
npm install -g firebase-tools
firebase login
cd functions && npm install && cd ..
firebase functions:secrets:set GEMINI_API_KEY   # วาง Gemini API key ตอนถูกถาม — key อยู่ใน Google Secret Manager ไม่อยู่ในไฟล์ใด ๆ
firebase deploy --only functions
```

ถ้า URL ที่ได้หลัง deploy ไม่ใช่ `https://asia-southeast1-movie-858f6.cloudfunctions.net/gemini` ให้แก้ค่า `GEMINI_PROXY` ใน `index.html`
เปลี่ยน key ภายหลัง: รัน `firebase functions:secrets:set GEMINI_API_KEY` แล้ว `firebase deploy --only functions` อีกครั้ง
ทดสอบตัวกลาง: `cd functions && npm test`

> ห้ามใส่ API key หรือไฟล์ service account ลงในไฟล์ที่ขึ้น GitHub — `.gitignore` กันไฟล์ `.env` และ `*serviceAccount*.json` ไว้แล้ว

## ระบบที่ใช้

- **Firebase Firestore** — ฐานข้อมูลหนัง 72,759 เรื่อง (ปี 1980–2026)
- **Algolia** — ช่องค้นหา (พิมพ์ผิดหรือพิมพ์ไม่ครบก็ยังเจอ)
- **Google Gemini** — แชทบอทและหมวด "If you like…" (เรียกผ่าน Firebase Cloud Functions)

## แหล่งข้อมูล

- ข้อมูลหนังจาก [TMDB](https://www.themoviedb.org/) และ [OMDb](https://www.omdbapi.com/)
- คะแนน Rotten Tomatoes และ Metacritic ได้มาผ่าน OMDb
- This product uses the TMDB API but is not endorsed or certified by TMDB.
- จัดทำเพื่อการศึกษา ไม่ใช้เชิงพาณิชย์
