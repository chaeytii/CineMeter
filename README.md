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
| `cinemeter-v7_9.html` | เวอร์ชันส่งมอบ แก้จุดผิด 7 จุดที่ชุดทดสอบพบแล้ว |
| `cinemeter-v7_8.html` | เวอร์ชันก่อนแก้ เก็บไว้ให้ชุดทดสอบเทียบก่อน–หลัง |
| `cinemeter-live-check.html` | หน้าตรวจข้อมูลจริง: สุ่มหนังจากฐานข้อมูล คำนวณคะแนนซ้ำ แล้วเทียบกับค่าที่เก็บไว้ (อ่านอย่างเดียว ไม่แก้ข้อมูล) |
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

## ระบบที่ใช้

- **Firebase Firestore** — ฐานข้อมูลหนัง 72,759 เรื่อง (ปี 1980–2026)
- **Algolia** — ช่องค้นหา (พิมพ์ผิดหรือพิมพ์ไม่ครบก็ยังเจอ)
- **Google Gemini** — แชทบอทและหมวด "If you like…"

## แหล่งข้อมูล

- ข้อมูลหนังจาก [TMDB](https://www.themoviedb.org/) และ [OMDb](https://www.omdbapi.com/)
- คะแนน Rotten Tomatoes และ Metacritic ได้มาผ่าน OMDb
- This product uses the TMDB API but is not endorsed or certified by TMDB.
- จัดทำเพื่อการศึกษา ไม่ใช้เชิงพาณิชย์
