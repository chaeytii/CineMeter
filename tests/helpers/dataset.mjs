// Deterministic synthetic catalogue shaped like the real MOVIES collection
// (field names/types taken from the app code and the midterm ER diagram).
export function rng(seed) {
  let a = seed >>> 0;
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// 28 real Genre_for_cal values (from GENRE_VARIANTS in the app)
export const RAW_GENRES = ["บู๊", "บู๊, ผจญภัย", "ผจญ", "แอนนิเมชั่น", "ตลก", "อาชญากรรม", "สารคดี", "หนังชีวิต", "ละคร", "ครอบครัว",
  "สำหรับเด็ก", "จินตนาการ", "จิตนิมิตแนววิทยาศาสตร์", "ประวัติศาสตร์", "สยองขวัญ", "ดนตรี", "ลึกลับ", "หนังรักโรแมนติก",
  "นิยายวิทยาศาสตร์", "ระทึกขวัญ", "สงคราม", "สงครามและการเมือง", "หนังคาวบอยตะวันตก", "ภาพยนตร์โทรทัศน์", "เรียลลิตี้",
  "บทสนทนา", "ข่าว"];

const MENU_GENRES = ["บู๊", "ผจญ", "แอนนิเมชั่น", "ตลก", "อาชญากรรม", "สารคดี", "หนังชีวิต", "ครอบครัว", "จินตนาการ", "ประวัติศาสตร์",
  "สยองขวัญ", "ดนตรี", "ลึกลับ", "หนังรักโรแมนติก", "นิยายวิทยาศาสตร์", "ระทึกขวัญ", "สงคราม", "หนังคาวบอยตะวันตก"];

export function makeMovies(n = 3000, seed = 7, opts = {}) {
  const r = rng(seed);
  const pick = a => a[Math.floor(r() * a.length)];
  const round2 = x => Math.round(x * 100) / 100;
  const out = [];
  const ids = new Set();
  for (let i = 0; i < n; i++) {
    let id; do { id = "tt" + String(1000000 + Math.floor(r() * 8999999)); } while (ids.has(id)); ids.add(id);
    // skew toward recent years like the real catalogue
    const year = r() < 0.45 ? 2024 + Math.floor(r() * 3) : 1980 + Math.floor(r() * 44);
    const series = r() < 0.15;
    const imdb = round2(3 + r() * 6.5), tmdb = round2(Math.min(10, Math.max(1, imdb + (r() - 0.5) * 1.6)));
    const rt = r() < 0.75 ? Math.round(Math.min(100, Math.max(0, imdb * 10 + (r() - 0.5) * 40))) : null;
    const mc = r() < 0.7 ? Math.round(Math.min(100, Math.max(0, imdb * 10 + (r() - 0.5) * 30))) : null;
    const critics = [rt, mc].filter(v => v !== null).map(v => v / 10);
    const sdPop = xs => { const m = xs.reduce((a, b) => a + b, 0) / xs.length; return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / xs.length); };
    const all = [...critics, imdb, tmdb];
    const doc = {
      id,
      Title_EN: `Movie ${i} ${pick(["Night", "Road", "Star", "River", "Odyssey", "Echo", "Wick", "Dune"])}`,
      Title_TH: r() < 0.5 ? `หนังเรื่องที่ ${i}` : "",
      Year: opts.numericYear ? year : String(year),
      Genre_for_cal: pick(RAW_GENRES),
      MediaType: series ? "ซีรีส์" : "ภาพยนตร์",
      imdbVotes: Math.floor(Math.exp(r() * 14)),
      Popularity: round2(Math.exp(r() * 6.2) / 2),
      imdbRating: String(imdb),
      tmdbRating: tmdb,
      TomatoScore: rt === null ? "N/A" : rt + "%",
      Metascore: mc === null ? "N/A" : String(mc),
      Audience_Average: round2((imdb + tmdb) / 2),
      Movie_Audience_SD: round2(sdPop([imdb, tmdb])),
      Overall_SD: round2(sdPop(all)),
      Poster: r() < 0.95 ? `https://img.example/${id}.jpg` : "",
      Plot: "A story about " + pick(["family", "revenge", "space", "love", "war", "ghosts"]),
      Keywords: Array.from({ length: 3 + Math.floor(r() * 5) }, () => pick(["revenge", "space", "love", "ghost", "heist", "family", "war", "time travel", "friendship", "survival"])),
      Recommended_Trust_Side: pick(["คนดู", "นักวิจารณ์"]),
    };
    if (critics.length) doc.Critics_Average = round2(critics.reduce((a, b) => a + b, 0) / critics.length);
    if (critics.length === 2) doc.Movie_Critics_SD = round2(sdPop(critics));
    if (opts.genresArray) doc.Genres = [pick(MENU_GENRES), ...(r() < 0.5 ? [pick(MENU_GENRES)] : [])].filter((g, k, a) => a.indexOf(g) === k);
    out.push(doc);
  }
  return out;
}
