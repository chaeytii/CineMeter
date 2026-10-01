const { initializeApp, cert } = require('firebase-admin/app');
const { getFirestore } = require('firebase-admin/firestore');
const fs = require('fs');
const path = require('path');

// 1. ระบุกุญแจเชื่อมต่อ Firebase
const serviceAccount = require('./serviceAccountKey.json');

// 2. ระบุชื่อไฟล์ข้อมูลที่ได้จาก Python (1980 - 2026)
const GENRE_FILE_PATH = path.join(__dirname, 'firebase_genre_analysis_1980_2026.json');
const MOVIES_FILE_PATH = path.join(__dirname, 'firebase_movies_1980_2026.json');

// ตรวจสอบว่ามีไฟล์อยู่จริงหรือไม่
if (!fs.existsSync(GENRE_FILE_PATH) || !fs.existsSync(MOVIES_FILE_PATH)) {
  console.error("Error: JSON data files not found. Please run the Python script first.");
  process.exit(1);
}

console.log("Reading JSON files into memory...");
const genresData = JSON.parse(fs.readFileSync(GENRE_FILE_PATH, 'utf-8'));
const moviesData = JSON.parse(fs.readFileSync(MOVIES_FILE_PATH, 'utf-8'));

initializeApp({
  credential: cert(serviceAccount)
});

const db = getFirestore();

async function importAllData() {
  console.log("Starting full database import process to Firebase...");
  const startTime = Date.now();

  const genreCollection = db.collection('GENRE_ANALYSIS');
  const movieCollection = db.collection('MOVIES');

  let batch = db.batch();
  let opsCount = 0;

  // ==========================================
  // สเต็ปที่ 1: อัปโหลดตาราง GENRE_ANALYSIS
  // ==========================================
  console.log(`\n[1/2] Importing GENRE_ANALYSIS collection (${genresData.length} categories)...`);
  
  for (let i = 0; i < genresData.length; i++) {
    const item = genresData[i];
    
    let genreKey = item.Genre_for_cal ? String(item.Genre_for_cal).trim() : 'Unknown';
    if (!genreKey || genreKey.toUpperCase() === 'N/A') genreKey = 'Unknown';
    genreKey = genreKey.replace(/\//g, '-'); // ป้องกันเครื่องหมาย / ในชื่อ Document

    const genreRef = genreCollection.doc(genreKey);
    batch.set(genreRef, {
      Genre_for_cal: genreKey,
      Genre_Audience_SD: item.Genre_Audience_SD ?? 'N/A',
      Genre_Critics_SD: item.Genre_Critics_SD ?? 'N/A'
    }, { merge: true });

    opsCount++;

    if (opsCount >= 400) {
      await batch.commit();
      batch = db.batch();
      opsCount = 0;
    }
  }

  // ส่งข้อมูล Genre ที่เหลืออยู่ (ถ้ามี)
  if (opsCount > 0) {
    await batch.commit();
    batch = db.batch();
    opsCount = 0;
  }
  console.log("GENRE_ANALYSIS collection imported successfully.");

  // ==========================================
  // สเต็ปที่ 2: อัปโหลดตาราง MOVIES (ตัวหลัก)
  // ==========================================
  console.log(`\n[2/2] Importing MOVIES collection (${moviesData.length.toLocaleString()} items)...`);
  let totalUploaded = 0;

  for (let i = 0; i < moviesData.length; i++) {
    const item = moviesData[i];

    // ตรวจสอบ Foreign Key ให้ตรงกับตาราง Genre
    let fkGenreKey = item.Genre_for_cal ? String(item.Genre_for_cal).trim() : 'Unknown';
    if (!fkGenreKey || fkGenreKey.toUpperCase() === 'N/A') fkGenreKey = 'Unknown';
    fkGenreKey = fkGenreKey.replace(/\//g, '-');

    // ตรวจสอบ Primary Key (imdbID)
    const rawId = item.imdbID ? String(item.imdbID).trim() : '';
    let movieDocRef;
    if (rawId && rawId.toUpperCase() !== 'N/A' && !rawId.includes('/')) {
      movieDocRef = movieCollection.doc(rawId);
    } else {
      movieDocRef = movieCollection.doc(); 
    }

    // แมปปิ้งข้อมูลตรงตาม ER Diagram
    const movieDocData = {
      imdbID: movieDocRef.id,
      Genre_for_cal: fkGenreKey, // Foreign Key
      Title_EN: item.Title_EN || '',
      Title_TH: item.Title_TH || item.Title_EN || 'No Title',
      MediaType: item.MediaType || 'ภาพยนตร์',
      Rated: item.Rated || 'N/A',
      Country: item.Country || 'N/A',
      Language: item.Language || 'N/A',
      Awards: item.Awards || 'N/A',
      Year: item.Year || '',
      Released: item.Released || '',
      Runtime: item.Runtime || 'N/A',
      Plot: item.Plot || '',
      Director: item.Director || 'N/A',
      Actors: item.Actors || 'N/A',
      Poster: item.Poster || 'N/A',
      Critics_Average: typeof item.Critics_Average === 'number' ? item.Critics_Average : 0,
      Metascore: item.Metascore || 'N/A',
      TomatoScore: item.TomatoScore || 'N/A',
      tmdbRating: typeof item.tmdbRating === 'number' ? item.tmdbRating : 0,
      imdbRating: item.imdbRating || 'N/A',
      Audience_Average: typeof item.Audience_Average === 'number' ? item.Audience_Average : 0,
      imdbVotes: item.imdbVotes || '0',
      tmdbVotes: item.tmdbVotes || '0',
      Recommended_Trust_Side: item.Recommended_Trust_Side || 'No Data',
      Movie_Critics_SD: item.Movie_Critics_SD ?? 'N/A',
      Movie_Audience_SD: item.Movie_Audience_SD ?? 'N/A',
      Popularity: typeof item.Popularity === 'number' ? item.Popularity : 0,
      Overall_SD: item.Overall_SD ?? 'N/A',
      tmdbID: item.tmdbID || 'N/A',
      Keyword: item.Keyword || 'N/A'
    };

    batch.set(movieDocRef, movieDocData, { merge: true });
    opsCount++;
    totalUploaded++;

    // Commit ทุกๆ 400 เรื่อง
    if (opsCount >= 400) {
      await batch.commit();
      batch = db.batch();
      opsCount = 0;
      
      const percent = ((totalUploaded / moviesData.length) * 100).toFixed(1);
      console.log(`Progress: Uploaded ${totalUploaded.toLocaleString()} / ${moviesData.length.toLocaleString()} items (${percent}%)`);
    }
  }

  // ส่งข้อมูลรอบสุดท้าย
  if (opsCount > 0) {
    await batch.commit();
  }

  const durationMinutes = ((Date.now() - startTime) / 1000 / 60).toFixed(2);
  console.log("\n==========================================");
  console.log("Full Import Process Completed 100%!");
  console.log(`Total Movies/Series Uploaded: ${totalUploaded.toLocaleString()} items`);
  console.log(`Total Time Elapsed: ${durationMinutes} minutes`);
  console.log("==========================================");
  process.exit(0);
}

importAllData().catch((error) => {
  console.error("Fatal Error occurred during import:", error);
  process.exit(1);
});