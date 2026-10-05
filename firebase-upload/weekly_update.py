# อัปเดตข้อมูลหนังใน Firestore แบบเฉพาะส่วนที่เปลี่ยน (รันทุกสัปดาห์ผ่าน GitHub Actions)
#
# ใช้ฟังก์ชันดึงข้อมูลและสูตรคำนวณจาก fetch_movies.py (สคริปต์ดึงข้อมูลชุดแรก) โดยตรง
# ข้อมูลที่ได้จึงหน้าตาเหมือนชุดเดิมทุกฟิลด์ ต่างกันแค่รอบนี้ไม่ดึงใหม่ทั้งฐาน:
#   1) คะแนน/โหวต IMDb ของทุกเรื่อง   — จากไฟล์ฟรีของ IMDb (ไม่ใช้ OMDb)
#   2) Popularity / คะแนน TMDB         — เฉพาะหนัง 3 ปีล่าสุด (ใช้กับหมวด Trending now)
#   3) เรื่องใหม่ที่โหวตเกิน 500         — ดึงครบทุกฟิลด์ จำกัดจำนวนตามโควตา OMDb
#   4) คะแนน RT / Metacritic            — หนังที่ออกฉายไม่เกิน 12 เดือน
#   5) เติมคะแนนนักวิจารณ์              — หนังเก่าที่ยังไม่มี RT/Metacritic (ใช้งบ OMDb ที่เหลือ)
#   5b) ข้อมูลเสริมจาก TMDB             — Genres / ชุดภาพยนตร์ (ภาคต่อ) / ค่ายผลิต ของเรื่องเก่าที่ยังไม่มี
#       แล้วสลับตัวกรองประเภทของหน้าเว็บไปใช้ Genres (META/genres) เมื่อครบทุกเรื่องและมี index แล้ว
#   6) GENRE_ANALYSIS                   — คำนวณใหม่จากข้อมูลทั้งฐาน
#   7) คะแนนจัดอันดับ Audience_Score / Critics_Score (ถ่วงจำนวนโหวต) + เอาเรื่องที่โหวต TMDB < 10 ออก
#   8) Algolia                          — ส่งข้อมูลที่เปลี่ยนเข้าช่องค้นหา (ถ้าตั้ง ALGOLIA_ADMIN_KEY)
# แล้วเขียนลง Firestore เฉพาะเรื่องที่ค่าเปลี่ยนจริง
#
# รันเอง:  python weekly_update.py --dry-run     (คำนวณแต่ไม่เขียนฐานข้อมูล)
# ต้องตั้งค่า: TMDB_API_KEY, OMDB_API_KEYS, GOOGLE_APPLICATION_CREDENTIALS (path ของ serviceAccountKey.json)

import argparse
import concurrent.futures
import csv
import datetime as dt
import gzip
import json
import os
import sys
import threading

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_movies as fm  # noqa: E402

START_YEAR = fm.START_YEAR
MIN_IMDB_VOTES = fm.MIN_IMDB_VOTES
IMDB_TYPES = {"movie", "tvSeries", "tvMiniSeries"}
VOTES_CHANGE = 0.02            # อัปเดตโหวตเมื่อเปลี่ยนเกิน 2%
POPULARITY_CHANGE = 0.10       # อัปเดต Popularity เมื่อเปลี่ยนเกิน 10%
TRENDING_YEARS = 3             # Popularity: ปีปัจจุบันและย้อนหลัง 2 ปี
CRITICS_REFRESH_DAYS = 365     # RT/Metacritic: หนังที่ออกไม่เกิน 1 ปี
MAX_FIND_LOOKUPS = 20000       # จำกัดการแปลงรหัส IMDb → TMDB ต่อรอบ
NEW_SHARE = 0.6                # งบ OMDb สำหรับเรื่องใหม่
REFRESH_SHARE = 0.2            # งบ OMDb สำหรับรีเฟรชหนังที่เพิ่งออก (ที่เหลือใช้เติมคะแนนหนังเก่า)
OMDB_RECHECK_DAYS = 90         # หนังเก่าที่ OMDb ไม่มีคะแนน จะไม่ถามซ้ำภายใน 90 วัน
DRY_RUN_OMDB_CALLS = 20        # dry run เรียก OMDb จริงไม่เกินเท่านี้
OMDB_WORKERS = 15
BATCH_SIZE = 400
MIN_TMDB_VOTES = 10           # เหมือนตอนดึงชุดแรก (TMDB discover ใช้ vote_count.gte=10)
MAX_REMOVE_SHARE = 0.25       # กันพลาด: ถ้าจะลบเกิน 25% ของฐาน ให้ข้ามการลบ
SCORE_MIN_VOTES = 25000       # m ในสูตรคะแนนถ่วงโหวต (แบบ IMDb Top 250)
# เติม Genres / ชุดภาพยนตร์ / ค่ายผลิตให้เรื่องเก่าที่ยังไม่มี ไม่เกินเท่านี้ต่อรอบ (ใช้ TMDB ฟรี, เรียงจากโหวตมากไปน้อย)
# ≈ โควตาเขียน Firestore ฟรีต่อวัน — รันมือครั้งแรกตั้ง env MAX_DETAILS_BACKFILL ให้สูงขึ้นเพื่อเติมทั้งฐานในรอบเดียว
MAX_DETAILS_BACKFILL = int(os.getenv("MAX_DETAILS_BACKFILL") or 20000)
DRY_RUN_DETAILS = 50          # dry run เรียก TMDB เพื่อเติมข้อมูลไม่เกินเท่านี้
FRANCHISE_FIELDS = {"CollectionID", "CollectionName", "Companies"}
# composite index ที่หน้าเว็บต้องใช้เมื่อกรองประเภทด้วย Genres (array-contains) — ต้องตรงกับ firestore.indexes.json
# ชุดตัวกรองที่หน้าเว็บส่งไปพร้อมประเภท × การเรียง (Popular, Loved by audiences/critics, Random discovery ขึ้น/ลง)
# ("Most IMDb votes" ใช้ Popularity เพราะ imdbVotes ในฐานเป็นข้อความ)
GENRE_INDEX_FILTERS = [(), ("Year",), ("MediaType",), ("MediaType", "Year")]
GENRE_INDEX_ORDERS = [("Popularity", "DESCENDING"), ("Audience_Score", "DESCENDING"), ("Critics_Score", "DESCENDING"),
                      ("Audience_Average", "ASCENDING"), ("Audience_Average", "DESCENDING")]
MAX_COMPANIES = 3             # เก็บค่ายผลิต 3 อันดับแรกตามที่ TMDB เรียงมา
WORKERS = 8

# ฟิลด์ที่ต้องอ่านจาก Firestore เพื่อคำนวณ
READ_FIELDS = ["imdbRating", "imdbVotes", "tmdbRating", "Metascore", "TomatoScore", "Critics_Average",
               "Audience_Average", "Movie_Critics_SD", "Movie_Audience_SD", "Overall_SD",
               "Recommended_Trust_Side", "Popularity", "tmdbID", "MediaType", "Released", "Year", "Genre_for_cal",
               "omdbCheckedAt", "tmdbVotes", "Audience_Score", "Critics_Score", "Genres", "CollectionID"]
SCORE_FIELDS = ["Critics_Average", "Audience_Average", "Movie_Critics_SD", "Movie_Audience_SD",
                "Overall_SD", "Recommended_Trust_Side"]


# ---------------------------------------------------------------
# สูตรคะแนน — ยกมาจาก process_single_item() ใน fetch_movies.py
# (ใช้ค่าที่เก็บในฐานข้อมูลแทนค่าที่เพิ่งดึงจาก API)
# ---------------------------------------------------------------
def score_fields(metascore, tomato, imdb_rating, tmdb_rating):
    c_scores_val = []
    if metascore not in (None, "", "N/A"):
        try: c_scores_val.append(float(metascore) / 10.0)
        except (TypeError, ValueError): pass
    if tomato not in (None, "", "N/A"):
        try: c_scores_val.append(float(str(tomato).replace("%", "")) / 10.0)
        except (TypeError, ValueError): pass
    critics_avg = round(sum(c_scores_val) / len(c_scores_val), 2) if c_scores_val else "N/A"

    a_scores_val = []
    if imdb_rating not in (None, "", "N/A"):
        try: a_scores_val.append(float(imdb_rating))
        except (TypeError, ValueError): pass
    if isinstance(tmdb_rating, (int, float)) and not isinstance(tmdb_rating, bool) and tmdb_rating > 0:
        a_scores_val.append(float(tmdb_rating))
    audience_avg = round(sum(a_scores_val) / len(a_scores_val), 2) if a_scores_val else "N/A"

    movie_c_sd = fm.calculate_sd(c_scores_val)
    movie_a_sd = fm.calculate_sd(a_scores_val)
    overall_sd = fm.calculate_sd(c_scores_val + a_scores_val)

    if movie_c_sd == "N/A" or movie_a_sd == "N/A":
        trust_side = "ข้อมูลไม่เพียงพอ"
    elif movie_c_sd < movie_a_sd:
        trust_side = "นักวิจารณ์ (Metascore/Rotten)"
    elif movie_a_sd < movie_c_sd:
        trust_side = "คนดู (IMDb/TMDb)"
    else:
        trust_side = "น่าเชื่อถือเท่ากัน"

    return {"Critics_Average": critics_avg, "Audience_Average": audience_avg, "Movie_Critics_SD": movie_c_sd,
            "Movie_Audience_SD": movie_a_sd, "Overall_SD": overall_sd, "Recommended_Trust_Side": trust_side}


def num_or_na(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else "N/A"


def genre_key(v):
    # เหมือน import_all_to_firebase.js: ใช้เป็นรหัส document ของ GENRE_ANALYSIS
    k = str(v).strip() if v else "Unknown"
    if not k or k.upper() == "N/A":
        k = "Unknown"
    return k.replace("/", "-")


def to_firestore_doc(item):
    """แปลงผลจาก process_single_item() เป็น document แบบเดียวกับ import_all_to_firebase.js
    ต่างกันจุดเดียว: คะแนนที่ไม่มีข้อมูลเก็บเป็น "N/A" ไม่ใช่ 0 (หน้าเว็บจะได้แสดงว่าไม่มีข้อมูล)"""
    s = lambda k: item.get(k) or "N/A"
    return {
        "imdbID": item["imdbID"],
        "Genre_for_cal": genre_key(item.get("Genre_for_cal")),
        "Title_EN": item.get("Title_EN") or "",
        "Title_TH": item.get("Title_TH") or item.get("Title_EN") or "No Title",
        "MediaType": item.get("MediaType") or "ภาพยนตร์",
        "Rated": s("Rated"), "Country": s("Country"), "Language": s("Language"), "Awards": s("Awards"),
        "Year": item.get("Year") or "", "Released": item.get("Released") or "",
        "Runtime": s("Runtime"), "Plot": item.get("Plot") or "",
        "Director": s("Director"), "Actors": s("Actors"), "Poster": s("Poster"),
        "Critics_Average": num_or_na(item.get("Critics_Average")),
        "Metascore": s("Metascore"), "TomatoScore": s("TomatoScore"),
        "tmdbRating": num_or_na(item.get("tmdbRating")),
        "imdbRating": s("imdbRating"),
        "Audience_Average": num_or_na(item.get("Audience_Average")),
        "imdbVotes": item.get("imdbVotes") or "0", "tmdbVotes": item.get("tmdbVotes") or "0",
        "Recommended_Trust_Side": item.get("Recommended_Trust_Side") or "No Data",
        "Movie_Critics_SD": item.get("Movie_Critics_SD", "N/A"),
        "Movie_Audience_SD": item.get("Movie_Audience_SD", "N/A"),
        "Popularity": item.get("Popularity") if isinstance(item.get("Popularity"), (int, float)) else 0,
        "Overall_SD": item.get("Overall_SD", "N/A"),
        "tmdbID": item.get("tmdbID") or "N/A",
        "Keyword": s("Keyword"),
    }


def parse_votes(v):
    try:
        return int(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0


def same_value(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) < 1e-9
    return a == b


# ---------------------------------------------------------------
# Firestore
# ---------------------------------------------------------------
class FirestoreStore:
    def __init__(self, credentials_path):
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(credentials_path))
        self.db = firestore.client()

    def read_movies(self, fields):
        col = self.db.collection("MOVIES")
        query = col.select(fields) if fields else col
        return {d.id: d.to_dict() or {} for d in query.stream()}

    def read_doc(self, collection, doc_id):
        snap = self.db.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def read_genres(self):
        return {d.id: d.to_dict() or {} for d in self.db.collection("GENRE_ANALYSIS").stream()}

    def genres_index_ready(self):
        """ลอง query แบบที่หน้าเว็บใช้หลังสลับไปกรองด้วย Genres ทุกชุด (อ่านชุดละ 1 เรื่อง)
        ยังไม่มี index หรือยังสร้างไม่เสร็จ Firestore จะตอบ FailedPrecondition — ผิดพลาดแบบอื่นก็ถือว่ายังไม่พร้อม
        (ขั้นนี้อยู่ก่อนเขียนฐานข้อมูล ห้ามทำให้ทั้งรอบล้ม)"""
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            where = lambda q, f, op, v: q.where(filter=FieldFilter(f, op, v))
        except ImportError:                                   # google-cloud-firestore รุ่นเก่า
            where = lambda q, f, op, v: q.where(f, op, v)
        sample = {"Year": "2024", "MediaType": "ภาพยนตร์"}
        try:
            for eq in GENRE_INDEX_FILTERS:
                for field, direction in GENRE_INDEX_ORDERS:
                    q = where(self.db.collection("MOVIES"), "Genres", "array_contains", "หนังชีวิต")
                    for f in eq:
                        q = where(q, f, "==", sample[f])
                    list(q.order_by(field, direction=direction).limit(1).stream())
            return True
        except Exception as e:                               # FailedPrecondition = ยังไม่มี index / กำลังสร้าง
            print(f"index ของ Genres ยังไม่พร้อม: {type(e).__name__}: {str(e)[:160]}")
            return False

    def delete(self, collection, doc_ids):
        col = self.db.collection(collection)
        batch, n = self.db.batch(), 0
        for doc_id in doc_ids:
            batch.delete(col.document(doc_id))
            n += 1
            if n >= BATCH_SIZE:
                batch.commit()
                batch, n = self.db.batch(), 0
        if n:
            batch.commit()

    def write(self, collection, docs):
        col = self.db.collection(collection)
        batch, n = self.db.batch(), 0
        for doc_id, data in docs.items():
            batch.set(col.document(doc_id), data, merge=True)
            n += 1
            if n >= BATCH_SIZE:
                batch.commit()
                batch, n = self.db.batch(), 0
        if n:
            batch.commit()


# ---------------------------------------------------------------
# ข้อมูลฟรีของ IMDb
# ---------------------------------------------------------------
def download(url, path):
    if os.path.exists(path):
        return
    tmp = path + ".part"
    with requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
    os.replace(tmp, path)


def load_imdb(cache_dir, today):
    """คืน {imdbID: {rating, votes_num, votes_str}} ทั้งหมด และ {imdbID: ปี} ของเรื่องที่ผ่านเกณฑ์เพิ่มเข้าฐาน"""
    os.makedirs(cache_dir, exist_ok=True)
    stamp = today.isoformat()
    ratings_path = os.path.join(cache_dir, f"title.ratings.{stamp}.tsv.gz")
    basics_path = os.path.join(cache_dir, f"title.basics.{stamp}.tsv.gz")
    download("https://datasets.imdbws.com/title.ratings.tsv.gz", ratings_path)
    # ใช้ตัวโหลดของ fetch_movies.py เพื่อให้รูปแบบตัวเลขตรงกับข้อมูลชุดแรก
    fm.IMDB_FILE = ratings_path
    fm.imdb_lookup.clear()
    fm.setup_imdb_ratings()
    ratings = fm.imdb_lookup

    download("https://datasets.imdbws.com/title.basics.tsv.gz", basics_path)
    eligible = {}
    with gzip.open(basics_path, "rt", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        next(reader)
        for row in reader:
            tconst, ttype, is_adult, start = row[0], row[1], row[4], row[5]
            r = ratings.get(tconst)
            if not r or r["votes_num"] <= MIN_IMDB_VOTES or ttype not in IMDB_TYPES or is_adult == "1":
                continue
            if start.isdigit() and START_YEAR <= int(start) <= today.year:
                eligible[tconst] = int(start)
    return ratings, eligible


# ---------------------------------------------------------------
# TMDB / OMDb
# ---------------------------------------------------------------
def tmdb_get(path, **params):
    params["api_key"] = fm.TMDB_API_KEY
    r = requests.get(f"https://api.themoviedb.org/3/{path}", params=params, timeout=15)
    if r.status_code == 404:
        return {"_not_found": True}       # TMDB ไม่มีเรื่องนี้แล้ว (ต่างจากผิดพลาดชั่วคราวที่ควรลองใหม่รอบหน้า)
    return r.json() if r.status_code == 200 else {}


def discover_recent(year, media_type):
    """Popularity และคะแนนของหนังปีนั้นจาก discover (หน้าละ 20 เรื่อง ไม่ต้องดึงทีละเรื่อง)"""
    year_param = {"primary_release_year": year} if media_type == "movie" else {"first_air_date_year": year}
    out, page = {}, 1
    while page <= 500:
        data = tmdb_get(f"discover/{media_type}", sort_by="popularity.desc", page=page,
                        **{"vote_count.gte": 10}, **year_param)
        results = data.get("results") or []
        for it in results:
            out[it["id"]] = {"popularity": it.get("popularity", 0.0), "vote_average": it.get("vote_average", 0)}
        if not results or page >= data.get("total_pages", 1):
            break
        page += 1
    return out


def find_tmdb(imdb_id):
    """คืน (tmdb id, ประเภท, จำนวนโหวต TMDB)"""
    data = tmdb_get(f"find/{imdb_id}", external_source="imdb_id")
    for key, kind in (("movie_results", "movie"), ("tv_results", "tv")):
        if data.get(key):
            r = data[key][0]
            return r["id"], kind, r.get("vote_count", 0) or 0
    return None, None, 0


def tmdb_details(tmdb_id, kind):
    """รายละเอียดจาก TMDB ในคำขอเดียว (ภาษาไทย เหมือน fetch_movies.py) — คืน None ถ้าดึงไม่ได้
    genres = ทุกประเภทของเรื่อง, collection = ชุดภาพยนตร์ (ภาคต่อ เช่น The Avengers Collection; ซีรีส์ไม่มี),
    companies = รหัสค่ายผลิต 3 อันดับแรก (เช่น Marvel Studios = 420)"""
    data = tmdb_get(f"{kind}/{tmdb_id}", language="th-TH")
    if data.get("_not_found"):
        return {"genres": [], "collection_id": 0, "collection_name": "", "companies": [], "not_found": True}
    if not data or "genres" not in data:
        return None
    coll = data.get("belongs_to_collection") if isinstance(data.get("belongs_to_collection"), dict) else {}
    cid = coll.get("id") if isinstance(coll.get("id"), int) and not isinstance(coll.get("id"), bool) else 0
    companies = [c["id"] for c in data.get("production_companies") or []
                 if isinstance(c, dict) and isinstance(c.get("id"), int) and not isinstance(c.get("id"), bool)]
    return {"genres": [g["name"] for g in data.get("genres") or [] if isinstance(g, dict) and g.get("name")],
            "collection_id": cid, "collection_name": (coll.get("name") or "") if cid else "",
            "companies": companies[:MAX_COMPANIES]}


def first_genre(m):
    """ประเภทแรกที่เก็บไว้แล้ว (Genre_for_cal) ในรูปค่าเมนู — ใช้เมื่อ TMDB ให้รายชื่อประเภทไม่ได้"""
    raw = str(m.get("Genre_for_cal") or "").strip()
    return [] if not raw or raw.upper() == "N/A" or raw == "Unknown" else menu_genres([raw])


def franchise_fields(details):
    """ฟิลด์ชุดภาพยนตร์/ค่ายผลิตที่เก็บใน MOVIES — CollectionID = 0 แปลว่าตรวจแล้วแต่ไม่อยู่ชุดไหน"""
    return {"CollectionID": details["collection_id"], "CollectionName": details["collection_name"],
            "Companies": details["companies"]}


def strict_int(v):
    """แปลง "1,234" / 1234 เป็นตัวเลข — คืน None ถ้าไม่มีค่าหรือแปลงไม่ได้ (ไม่เดาว่าเป็น 0)"""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    t = str(v).replace(",", "").strip()
    return int(t) if t.isdigit() else None


# ประเภทหนังแบบหลายประเภทต่อเรื่อง (ฟิลด์ Genres) — ค่าเมนูเดียวกับ GENRE_VARIANTS ใน index.html
# (ไม่รวมค่าเมนูเก่า "โรแมนติก"/"เพลง" ที่เป็นชื่อแฝง) ถ้าแก้ใน index.html ต้องแก้ที่นี่ด้วย — มีเทสต์เทียบให้
GENRE_VARIANTS = {
    "บู๊": ["บู๊", "บู๊, ผจญภัย"], "ผจญ": ["ผจญ", "บู๊, ผจญภัย"], "แอนนิเมชั่น": ["แอนนิเมชั่น"],
    "ตลก": ["ตลก"], "อาชญากรรม": ["อาชญากรรม"], "สารคดี": ["สารคดี"], "หนังชีวิต": ["หนังชีวิต", "ละคร"],
    "ครอบครัว": ["ครอบครัว", "สำหรับเด็ก"], "จินตนาการ": ["จินตนาการ", "จิตนิมิตแนววิทยาศาสตร์"],
    "ประวัติศาสตร์": ["ประวัติศาสตร์"], "สยองขวัญ": ["สยองขวัญ"], "ดนตรี": ["ดนตรี"], "ลึกลับ": ["ลึกลับ"],
    "หนังรักโรแมนติก": ["หนังรักโรแมนติก"], "นิยายวิทยาศาสตร์": ["นิยายวิทยาศาสตร์", "จิตนิมิตแนววิทยาศาสตร์"],
    "ระทึกขวัญ": ["ระทึกขวัญ"], "สงคราม": ["สงคราม", "สงครามและการเมือง"],
    "หนังคาวบอยตะวันตก": ["หนังคาวบอยตะวันตก"], "ภาพยนตร์โทรทัศน์": ["ภาพยนตร์โทรทัศน์"],
    "เรียลลิตี้": ["เรียลลิตี้"], "บทสนทนา": ["บทสนทนา", "ข่าว"],
}


def menu_genres(tmdb_names):
    """ชื่อประเภทภาษาไทยจาก TMDB → ค่าเมนู (เหมือน legacyGenres() ใน index.html ทีละประเภท)"""
    out = []
    for name in tmdb_names:
        keys = [k for k, variants in GENRE_VARIANTS.items() if name in variants] or [name]
        out += [k for k in keys if k not in out]
    return out


def weighted(avg, votes, prior, m=SCORE_MIN_VOTES):
    """คะแนนถ่วงจำนวนโหวต (สูตรเดียวกับ IMDb Top 250): หนังโหวตน้อยถูกดึงเข้าหาค่ากลางของทั้งฐาน"""
    if not isinstance(avg, (int, float)) or isinstance(avg, bool):
        return "N/A"
    v = max(votes, 0)
    return round(v / (v + m) * avg + m / (v + m) * prior, 2)


def omdb_lookup(imdb_id):
    """คืน (OMDb ตอบกลับไหม, คะแนน) — คะแนนเป็น None ถ้า OMDb ไม่มีข้อมูลเรื่องนี้"""
    data = fm.fetch_omdb_data(imdb_id)
    if data is None:
        return False, None
    if data.get("Response") != "True":
        return True, None
    tomato = "N/A"
    for r in data.get("Ratings", []):
        if r.get("Source") == "Rotten Tomatoes":
            tomato = r.get("Value", "N/A")
            break
    return True, {"Metascore": data.get("Metascore", "N/A"), "TomatoScore": tomato, "Awards": data.get("Awards", "N/A")}



# ---------------------------------------------------------------
# Algolia (ช่องค้นหาบนหน้าเว็บ) — sync ให้ตรงกับ Firestore
# ---------------------------------------------------------------
ALGOLIA_APP_ID = "GZASG6MLUC"                 # ตรงกับ ALGOLIA.appId ใน index.html
ALGOLIA_INDEX = "firebase_movies_1980_2026"   # ตรงกับ ALGOLIA.indexName ใน index.html
ALGOLIA_BATCH = 1000
ALGOLIA_MAX_RECORD_BYTES = 9500               # Algolia แผนฟรีรับ record ละไม่เกิน 10 KB
ALGOLIA_COUNT_TOLERANCE = 0.01
ALGOLIA_MAX_RECORDS = int(os.getenv("ALGOLIA_MAX_RECORDS", "50000"))   # Algolia แผน Build เก็บได้ 50K records


class AlgoliaClient:
    def __init__(self, app_id, admin_key, index, http=requests):
        self.app_id, self.index, self.http = app_id, index, http
        self.headers = {"X-Algolia-Application-Id": app_id, "X-Algolia-API-Key": admin_key,
                        "Content-Type": "application/json"}

    def _call(self, method, path, body=None, read=False):
        host = f"https://{self.app_id}-dsn.algolia.net" if read else f"https://{self.app_id}.algolia.net"
        r = self.http.request(method, host + path, headers=self.headers,
                              data=json.dumps(body, ensure_ascii=False) if body is not None else None, timeout=60)
        if r.status_code >= 300:
            raise RuntimeError(f"Algolia {method} {path}: {r.status_code} {str(r.text)[:200]}")
        return r.json()

    def sample(self, index):
        """คืน (จำนวน record, ตัวอย่าง [(objectID, imdbID)])"""
        data = self._call("POST", f"/1/indexes/{index}/query",
                          {"query": "", "hitsPerPage": 20, "attributesToRetrieve": ["imdbID"]}, read=True)
        return data.get("nbHits", 0), [(h.get("objectID"), h.get("imdbID")) for h in data.get("hits", [])]

    def batch(self, index, requests_):
        return self._call("POST", f"/1/indexes/{index}/batch", {"requests": requests_}).get("taskID")

    def operation(self, index, body):
        return self._call("POST", f"/1/indexes/{index}/operation", body).get("taskID")

    def wait(self, index, task_id, poll=2.0, timeout=1800):
        if task_id is None:
            return
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._call("GET", f"/1/indexes/{index}/task/{task_id}").get("status") == "published":
                return
            time.sleep(poll)
        raise RuntimeError(f"Algolia task {task_id} ไม่เสร็จภายในเวลา")


def algolia_record(doc_id, data):
    rec = dict(data)
    rec["objectID"] = doc_id
    rec.setdefault("imdbID", doc_id)
    for field in ("Plot", "Keyword"):
        if len(json.dumps(rec, ensure_ascii=False).encode("utf-8")) <= ALGOLIA_MAX_RECORD_BYTES:
            break
        if isinstance(rec.get(field), str):
            rec[field] = rec[field][:300]
    return rec


def top_by_votes(docs, cap):
    """เรื่องที่โหวต IMDb มากที่สุด ไม่เกิน cap เรื่อง (Algolia แผนฟรีเก็บได้จำกัด)"""
    ranked = sorted(docs, key=lambda k: -(strict_int(docs[k].get("imdbVotes")) or 0))
    return set(ranked[:cap])


def sync_algolia(client, store, updates, movies, today, log=print, removed=(), cap=None):
    """คืน (โหมด, จำนวน record ที่ส่ง) — ส่งเฉพาะเรื่องที่โหวตมากที่สุดไม่เกิน cap เรื่อง
    แทนที่ทั้ง index ถ้า objectID ไม่ใช่ imdbID / จำนวนต่างเกิน 1% / รอบแรกของเดือน — นอกนั้นอัปเดตเฉพาะเรื่องที่เปลี่ยน"""
    cap = cap or ALGOLIA_MAX_RECORDS
    expected = min(len(movies), cap)
    count, sample = client.sample(client.index)
    ids_ok = bool(sample) and all(oid == iid for oid, iid in sample)
    count_ok = expected and abs(count - expected) / expected <= ALGOLIA_COUNT_TOLERANCE
    if not ids_ok or not count_ok or today.day <= 7:
        reason = "objectID ไม่ใช่ imdbID" if not ids_ok else ("จำนวนไม่ตรง" if not count_ok else "รอบแรกของเดือน")
        log(f"Algolia: แทนที่ทั้ง index ({reason}; Algolia {count:,} / ควรมี {expected:,} จาก Firestore {len(movies):,})")
        tmp = f"{client.index}_tmp"
        client.wait(tmp, client.operation(client.index, {"operation": "copy", "destination": tmp,
                                                         "scope": ["settings", "synonyms", "rules"]}))
        docs = store.read_movies(None)
        keep = top_by_votes(docs, cap)
        items = [(k, v) for k, v in docs.items() if k in keep]
        task = None
        for i in range(0, len(items), ALGOLIA_BATCH):
            task = client.batch(tmp, [{"action": "addObject", "body": algolia_record(k, v)}
                                      for k, v in items[i: i + ALGOLIA_BATCH]])
        client.wait(tmp, task)
        client.wait(client.index, client.operation(tmp, {"operation": "move", "destination": client.index}))
        return "แทนที่ทั้ง index", len(items)

    keep = top_by_votes(movies, cap)
    drop = [k for k in updates if k not in keep] + list(removed)
    log(f"Algolia: อัปเดต {sum(1 for k in updates if k in keep):,} เรื่องที่เปลี่ยน, ลบ {len(drop):,} เรื่อง")
    reqs = [{"action": "partialUpdateObject", "objectID": k, "body": algolia_record(k, v)}
            for k, v in updates.items() if k in keep]
    reqs += [{"action": "deleteObject", "body": {"objectID": k}} for k in drop]
    task = None
    for i in range(0, len(reqs), ALGOLIA_BATCH):
        task = client.batch(client.index, reqs[i: i + ALGOLIA_BATCH])
    client.wait(client.index, task)
    return "อัปเดตทีละเรื่อง", len(reqs)


# ---------------------------------------------------------------
# งานหลัก
# ---------------------------------------------------------------
def run(store, imdb_loader, today, omdb_budget, dry_run=False, log=print, algolia=None):
    stats = {"existing": 0, "imdb_updated": 0, "popularity_updated": 0, "repaired": 0, "added": 0,
             "critics_refreshed": 0, "omdb_calls": 0, "omdb_budget": 0, "tmdb_find_calls": 0, "genres_written": 0,
             "backlog_total": 0, "backlog_left": 0, "new_omdb_failed": 0, "refresh_candidates": 0,
             "backfill_candidates": 0, "backfilled": 0, "backfill_left": 0, "docs_written": 0,
             "algolia_mode": "-", "algolia_records": 0, "new_low_tmdb": 0, "removed_low_tmdb": 0, "scores_written": 0,
             "genres_mode": "-", "genres_filled": 0, "genres_missing": 0, "franchise_filled": 0}

    movies = store.read_movies(READ_FIELDS)
    stats["existing"] = len(movies)
    log(f"Firestore: {len(movies):,} เรื่อง")
    ratings, eligible = imdb_loader(today)
    log(f"IMDb: {len(ratings):,} เรื่อง, ผ่านเกณฑ์ (โหวต > {MIN_IMDB_VOTES}, {START_YEAR}–{today.year}): {len(eligible):,}")

    # เอาเรื่องที่โหวต TMDB ไม่ถึงเกณฑ์ชุดแรกออก (เฉพาะเรื่องที่มีตัวเลขโหวตจริง — ไม่มีข้อมูลไม่ลบ)
    low = [i for i, m in movies.items()
           if strict_int(m.get("tmdbVotes")) is not None and strict_int(m.get("tmdbVotes")) < MIN_TMDB_VOTES]
    removed = []
    if low and len(low) > len(movies) * MAX_REMOVE_SHARE:
        log(f"คำเตือน: เรื่องที่โหวต TMDB < {MIN_TMDB_VOTES} มี {len(low):,} เรื่อง (เกิน {MAX_REMOVE_SHARE:.0%}) — ข้ามการลบเพื่อความปลอดภัย")
    elif low:
        removed = low
        for i in removed:
            movies.pop(i)
        log(f"เอาออก {len(removed):,} เรื่องที่โหวต TMDB < {MIN_TMDB_VOTES}")
    stats["removed_low_tmdb"] = len(removed)

    updates = {}           # imdbID -> ฟิลด์ที่ต้องเขียน
    rescore = set()        # เรื่องที่ต้องคำนวณคะแนนใหม่

    def put(doc_id, fields):
        updates.setdefault(doc_id, {}).update(fields)
        movies[doc_id].update(fields)

    # 1) คะแนน/โหวต IMDb
    for doc_id, m in movies.items():
        r = ratings.get(doc_id)
        if not r:
            continue
        old_votes = parse_votes(m.get("imdbVotes"))
        votes_moved = old_votes == 0 or abs(r["votes_num"] - old_votes) / old_votes > VOTES_CHANGE
        if str(m.get("imdbRating")) != r["rating"] or votes_moved:
            put(doc_id, {"imdbRating": r["rating"], "imdbVotes": r["votes_str"]})
            rescore.add(doc_id)
            stats["imdb_updated"] += 1

    # 2) Popularity / คะแนน TMDB ของหนัง 3 ปีล่าสุด
    by_tmdb = {}
    for doc_id, m in movies.items():
        kind = "tv" if m.get("MediaType") == "ซีรีส์" else "movie"
        if isinstance(m.get("tmdbID"), int):
            by_tmdb[(kind, m["tmdbID"])] = doc_id
    for year in range(today.year - TRENDING_YEARS + 1, today.year + 1):
        for kind in ("movie", "tv"):
            for tmdb_id, info in discover_recent(year, kind).items():
                doc_id = by_tmdb.get((kind, tmdb_id))
                if not doc_id:
                    continue
                m = movies[doc_id]
                fields = {}
                old_pop = m.get("Popularity") if isinstance(m.get("Popularity"), (int, float)) else 0
                new_pop = info["popularity"] or 0
                if new_pop != old_pop and (old_pop == 0 or abs(new_pop - old_pop) / old_pop > POPULARITY_CHANGE):
                    fields["Popularity"] = new_pop
                new_tmdb = round(info["vote_average"], 1) if info["vote_average"] else "N/A"
                if not same_value(m.get("tmdbRating"), new_tmdb):
                    fields["tmdbRating"] = new_tmdb
                    rescore.add(doc_id)
                if fields:
                    put(doc_id, fields)
                    stats["popularity_updated"] += 1

    # ซ่อมข้อมูลชุดแรกที่ import เขียน 0 แทน "ไม่มีข้อมูล"
    for doc_id, m in movies.items():
        expected = score_fields(m.get("Metascore"), m.get("TomatoScore"), m.get("imdbRating"), m.get("tmdbRating"))
        broken = any(m.get(k) == 0 and expected[k] == "N/A" for k in ("Critics_Average", "Audience_Average"))
        if m.get("tmdbRating") == 0:
            put(doc_id, {"tmdbRating": "N/A"})
            broken = True
        if broken:
            rescore.add(doc_id)
            stats["repaired"] += 1

    # งบ OMDb ต่อรอบ: เรื่องใหม่ ≤ 60%, รีเฟรชหนังที่เพิ่งออก ≤ 20%, เติมคะแนนหนังเก่า = ที่เหลือทั้งหมด
    if dry_run:
        omdb_budget = min(omdb_budget, DRY_RUN_OMDB_CALLS)
    stats["omdb_budget"] = omdb_budget
    real_fetch = fm.fetch_omdb_data
    count_lock = threading.Lock()
    omdb_ok = set()            # รหัสที่ OMDb ตอบกลับมาแล้ว (มีหรือไม่มีคะแนนก็ตาม)
    cap = {"limit": 0}         # เพดานสะสมของส่วนที่กำลังทำ

    def counted_fetch(imdb_id):
        with count_lock:
            if stats["omdb_calls"] >= cap["limit"]:
                return None    # เกินงบ: ไม่เรียกจริง
            stats["omdb_calls"] += 1
        data = real_fetch(imdb_id)
        if data is not None:
            with count_lock:
                omdb_ok.add(imdb_id)
        return data
    fm.fetch_omdb_data = counted_fetch
    try:
        # 3) เรื่องใหม่ (เรียงโหวตมากก่อน) — ถ้า OMDb ตอบไม่ได้ ไม่เพิ่ม เก็บไว้รอบหน้า
        backlog = sorted((i for i in eligible if i not in movies), key=lambda i: -ratings[i]["votes_num"])
        stats["backlog_total"] = len(backlog)
        log(f"เรื่องที่ยังไม่มีในฐาน: {len(backlog):,}")
        cap["limit"] = int(omdb_budget * NEW_SHARE)
        new_docs, pos = {}, 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            while (pos < len(backlog) and stats["omdb_calls"] < cap["limit"] and not fm.omdb_exhausted
                   and stats["tmdb_find_calls"] < MAX_FIND_LOOKUPS):
                chunk = backlog[pos: pos + max(1, min(WORKERS * 4, cap["limit"] - stats["omdb_calls"]))]
                pos += len(chunk)
                stats["tmdb_find_calls"] += len(chunk)
                found = list(ex.map(find_tmdb, chunk))
                stats["new_low_tmdb"] += sum(1 for tid, _, votes in found if tid and votes < MIN_TMDB_VOTES)
                jobs = [(tid, kind) for tid, kind, votes in found if tid and votes >= MIN_TMDB_VOTES]
                def process_new(job):
                    item = fm.process_single_item({"id": job[0]}, job[1])
                    if item:
                        item["_details"] = tmdb_details(job[0], job[1])
                    return item
                for item in ex.map(process_new, jobs):
                    if not item or item["imdbID"] in movies or item["imdbID"] in new_docs:
                        continue
                    if item["imdbID"] not in omdb_ok:
                        stats["new_omdb_failed"] += 1
                        continue
                    doc = to_firestore_doc(item)
                    doc["omdbCheckedAt"] = today.isoformat()
                    det = item.get("_details")
                    if det:
                        doc["Genres"] = menu_genres(det["genres"]) if det["genres"] else first_genre(doc)
                        doc.update(franchise_fields(det))
                    new_docs[item["imdbID"]] = doc
        stats["backlog_left"] = len(backlog) - pos + stats["new_omdb_failed"]
        for doc_id, d in new_docs.items():
            updates[doc_id] = d
            movies[doc_id] = dict(d)
        stats["added"] = len(new_docs)

        def check_critics(ids, limit, mark_checked):
            """ถาม OMDb ทีละหลายเรื่องพร้อมกัน คืนจำนวนเรื่องที่คะแนนเปลี่ยน"""
            cap["limit"] = limit
            changed_n = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=OMDB_WORKERS) as ex:
                for i in range(0, len(ids), OMDB_WORKERS * 4):
                    if stats["omdb_calls"] >= cap["limit"] or fm.omdb_exhausted:
                        break
                    chunk = ids[i: i + OMDB_WORKERS * 4]
                    for doc_id, (answered, sc) in zip(chunk, ex.map(omdb_lookup, chunk)):
                        if not answered:
                            continue
                        m = movies[doc_id]
                        fields = {"omdbCheckedAt": today.isoformat()} if mark_checked else {}
                        if sc and (sc["Metascore"] != m.get("Metascore") or sc["TomatoScore"] != m.get("TomatoScore")):
                            fields.update(sc)
                            rescore.add(doc_id)
                            changed_n += 1
                        if fields:
                            put(doc_id, fields)
            return changed_n

        # 4) RT / Metacritic ของหนังที่ออกฉายไม่เกิน 12 เดือน
        cutoff = (today - dt.timedelta(days=CRITICS_REFRESH_DAYS)).isoformat()

        def popularity(i):
            p = movies[i].get("Popularity")
            return p if isinstance(p, (int, float)) else 0
        recent = sorted((i for i, m in movies.items() if i not in new_docs and m.get("MediaType") != "ซีรีส์"
                         and str(m.get("Released") or "") >= cutoff), key=lambda i: -popularity(i))
        stats["refresh_candidates"] = len(recent)
        stats["critics_refreshed"] = check_critics(recent, stats["omdb_calls"] + int(omdb_budget * REFRESH_SHARE), False)

        # 5) เติมคะแนนนักวิจารณ์ให้หนังเก่าที่ยังไม่มีทั้ง Metascore และ RT (ไม่ถามซ้ำภายใน 90 วัน)
        recent_set = set(recent)
        recheck_before = (today - dt.timedelta(days=OMDB_RECHECK_DAYS)).isoformat()
        missing = lambda v: v in (None, "", "N/A")
        backfill = sorted((i for i, m in movies.items() if i not in new_docs and i not in recent_set
                           and missing(m.get("Metascore")) and missing(m.get("TomatoScore"))
                           and str(m.get("omdbCheckedAt") or "") < recheck_before),
                          key=lambda i: -parse_votes(movies[i].get("imdbVotes")))
        stats["backfill_candidates"] = len(backfill)
        before = stats["omdb_calls"]
        stats["backfilled"] = check_critics(backfill, omdb_budget, True)
        stats["backfill_left"] = max(0, len(backfill) - (stats["omdb_calls"] - before))
    finally:
        fm.fetch_omdb_data = real_fetch

    # คำนวณคะแนนใหม่ให้เรื่องที่ตัวเลขต้นทางเปลี่ยน
    for doc_id in rescore:
        if doc_id in new_docs:
            continue
        m = movies[doc_id]
        new = score_fields(m.get("Metascore"), m.get("TomatoScore"), m.get("imdbRating"), m.get("tmdbRating"))
        changed = {k: v for k, v in new.items() if not same_value(m.get(k), v)}
        if changed:
            put(doc_id, changed)

    # เติมข้อมูลจาก TMDB ให้เรื่องเก่า (คำขอเดียวต่อเรื่อง เรียงจากโหวตมากไปน้อย):
    #   Genres — ทุกประเภทของเรื่อง (ชุดแรกเก็บแค่ประเภทแรกใน Genre_for_cal) หน้าเว็บแสดงทันทีที่มี
    #            ส่วนตัวกรองสลับมาใช้ Genres เมื่อครบทุกเรื่องและมี index แล้ว (META/genres ด้านล่าง)
    #   CollectionID / CollectionName / Companies — ใช้ทำแถว "ภาคอื่นในชุดนี้" และ If you like…
    # ไม่มีรหัส TMDB / TMDB ไม่มีเรื่องนี้แล้ว / TMDB ไม่มีประเภท → ใช้ประเภทแรกที่มีอยู่ จะได้ไม่มีเรื่องค้างตลอดไป
    valid_tid = lambda m: isinstance(m.get("tmdbID"), int) and not isinstance(m.get("tmdbID"), bool)
    for doc_id, m in movies.items():
        if doc_id not in new_docs and "Genres" not in m and not valid_tid(m):
            put(doc_id, {"Genres": first_genre(m)})
            stats["genres_filled"] += 1
    need = sorted((i for i, m in movies.items() if i not in new_docs and valid_tid(m)
                   and ("Genres" not in m or "CollectionID" not in m)),
                  key=lambda i: -parse_votes(movies[i].get("imdbVotes")))
    need = need[:DRY_RUN_DETAILS if dry_run else MAX_DETAILS_BACKFILL]
    kinds = {i: ("tv" if movies[i].get("MediaType") == "ซีรีส์" else "movie") for i in need}
    with concurrent.futures.ThreadPoolExecutor(max_workers=OMDB_WORKERS) as ex:
        for doc_id, det in zip(need, ex.map(lambda i: tmdb_details(movies[i]["tmdbID"], kinds[i]), need)):
            if not det:
                continue                  # TMDB ผิดพลาดชั่วคราว — ลองใหม่รอบหน้า
            m, fields = movies[doc_id], {}
            if "Genres" not in m:
                fields["Genres"] = menu_genres(det["genres"]) if det["genres"] else first_genre(m)
                stats["genres_filled"] += 1
            if "CollectionID" not in m:
                fields.update(franchise_fields(det))
                stats["franchise_filled"] += 1
            if fields:
                put(doc_id, fields)

    # คะแนนถ่วงจำนวนโหวต สำหรับแถว Loved by audiences / critics
    # ค่ากลาง (prior) คำนวณครั้งแรกแล้วเก็บไว้ที่ META/ranking — ใช้ค่าเดิมทุกสัปดาห์ ไม่ให้คะแนนทั้งฐานขยับตามกันทุกรอบ
    def prior(field):
        vals = [m[field] for m in movies.values() if isinstance(m.get(field), (int, float)) and not isinstance(m.get(field), bool)]
        return round(sum(vals) / len(vals), 1) if vals else 0
    meta = store.read_doc("META", "ranking") or {}
    prior_aud = meta.get("priorAudience") if isinstance(meta.get("priorAudience"), (int, float)) else prior("Audience_Average")
    prior_crit = meta.get("priorCritics") if isinstance(meta.get("priorCritics"), (int, float)) else prior("Critics_Average")
    meta_update = {} if meta.get("priorAudience") == prior_aud and meta.get("priorCritics") == prior_crit else {
        "ranking": {"priorAudience": prior_aud, "priorCritics": prior_crit, "minVotes": SCORE_MIN_VOTES,
                    "createdAt": today.isoformat()}}
    # สลับตัวกรองประเภทบนหน้าเว็บไปใช้ Genres (META/genres.complete) เมื่อทุกเรื่องมี Genres และ index พร้อมแล้ว
    # ถ้าสลับก่อน index พร้อม ตัวกรองประเภทจะต้องใช้โหมดสำรองที่เรียงผลได้ไม่ครบ จึงตรวจ index ก่อนทุกครั้ง
    genres_meta = store.read_doc("META", "genres") or {}
    stats["genres_missing"] = sum(1 for m in movies.values() if "Genres" not in m)
    if genres_meta.get("complete"):
        stats["genres_mode"] = "ใช้ Genres (META/genres.complete)"
    elif stats["genres_missing"]:
        stats["genres_mode"] = "ใช้ Genre_for_cal — ยังเติม Genres ไม่ครบ"
    elif dry_run:
        stats["genres_mode"] = "ใช้ Genre_for_cal — Genres ครบแล้ว (dry run ไม่สลับ)"
    elif store.genres_index_ready():
        meta_update["genres"] = {"complete": True, "completedAt": today.isoformat()}
        stats["genres_mode"] = "สลับเป็นใช้ Genres รอบนี้ (ครบทุกเรื่องและ index พร้อม)"
    else:
        stats["genres_mode"] = "ใช้ Genre_for_cal — Genres ครบแล้ว รอ index (firebase deploy --only firestore:indexes)"
    if stats["genres_mode"].startswith("ใช้ Genre_for_cal"):
        log(f"ประเภทหนัง: {stats['genres_mode']} (ยังขาด {stats['genres_missing']:,} เรื่อง)")

    for doc_id, m in movies.items():
        votes = strict_int(m.get("imdbVotes")) or 0
        sc = {"Audience_Score": weighted(m.get("Audience_Average"), votes, prior_aud),
              "Critics_Score": weighted(m.get("Critics_Average"), votes, prior_crit)}
        changed = {k: v for k, v in sc.items() if not same_value(m.get(k), v)}
        if changed:
            stats["scores_written"] += 1
            if doc_id in new_docs:
                new_docs[doc_id].update(changed)
            put(doc_id, changed)

    # 6) GENRE_ANALYSIS จากข้อมูลทั้งฐาน (วิธีเดียวกับ fetch_movies.py)
    raw = {}
    for m in movies.values():
        g = genre_key(m.get("Genre_for_cal"))
        if g == "Unknown":
            continue
        bucket = raw.setdefault(g, {"critics": [], "audience": []})
        if isinstance(m.get("Critics_Average"), (int, float)):
            bucket["critics"].append(m["Critics_Average"])
        if isinstance(m.get("Audience_Average"), (int, float)):
            bucket["audience"].append(m["Audience_Average"])
    old_genres = store.read_genres()
    genre_updates = {}
    for g, sc in raw.items():
        doc = {"Genre_for_cal": g, "Genre_Audience_SD": fm.calculate_sd(sc["audience"]),
               "Genre_Critics_SD": fm.calculate_sd(sc["critics"])}
        old = old_genres.get(g, {})
        if any(not same_value(old.get(k), v) for k, v in doc.items()):
            genre_updates[g] = doc
    stats["genres_written"] = len(genre_updates)
    stats["docs_written"] = len(updates)

    if dry_run:
        log("DRY RUN — ไม่ได้เขียนฐานข้อมูล ตัวอย่างการเปลี่ยนแปลง:")
        for doc_id in list(updates)[:5]:
            log(f"  {doc_id}: {json.dumps(updates[doc_id], ensure_ascii=False)[:300]}")
    else:
        store.write("MOVIES", updates)
        if removed:
            store.delete("MOVIES", removed)
        store.write("GENRE_ANALYSIS", genre_updates)
        if meta_update:
            store.write("META", meta_update)
        if algolia:
            # ช่องค้นหาไม่ใช้ชุดภาพยนตร์/ค่ายผลิต — เรื่องที่เปลี่ยนแค่ฟิลด์เหล่านี้ไม่ต้องส่ง Algolia
            searchable = {k: v for k, v in updates.items() if set(v) - FRANCHISE_FIELDS}
            mode, n = sync_algolia(algolia, store, searchable, movies, today, log, removed=removed)
            stats["algolia_mode"], stats["algolia_records"] = mode, n
    return stats


SUMMARY_LABELS = [
    ("existing", "เรื่องในฐานก่อนเริ่ม"),
    ("removed_low_tmdb", f"เอาออก (โหวต TMDB < {MIN_TMDB_VOTES})"),
    ("backlog_total", "เรื่องที่ยังไม่มีในฐาน (โหวต > 500)"), ("added", "เพิ่มเรื่องใหม่"),
    ("new_low_tmdb", f"เรื่องใหม่ที่ข้าม (โหวต TMDB < {MIN_TMDB_VOTES})"),
    ("new_omdb_failed", "เรื่องใหม่ที่ OMDb ตอบไม่ได้ (รอรอบหน้า)"), ("backlog_left", "เรื่องใหม่ที่รอรอบหน้า"),
    ("imdb_updated", "อัปเดตคะแนน/โหวต IMDb"), ("popularity_updated", "อัปเดต Popularity/คะแนน TMDB"),
    ("refresh_candidates", "หนังที่ออกไม่เกิน 12 เดือน (ตรวจ RT/Metacritic)"), ("critics_refreshed", "อัปเดตคะแนน RT/Metacritic"),
    ("backfill_candidates", "หนังเก่าที่ขาดคะแนนนักวิจารณ์"), ("backfilled", "เติมคะแนนนักวิจารณ์ได้"),
    ("backfill_left", "หนังเก่าที่ยังรอตรวจ"), ("repaired", "ซ่อมค่า 0 → N/A"),
    ("scores_written", "อัปเดตคะแนนจัดอันดับ (ถ่วงโหวต)"),
    ("genres_mode", "ประเภทหนังที่หน้าเว็บใช้กรอง"), ("genres_filled", "เติม Genres ให้เรื่องเก่า"), ("genres_missing", "เรื่องที่ยังไม่มี Genres"),
    ("franchise_filled", "เติมชุดภาพยนตร์/ค่ายผลิตให้เรื่องเก่า"),
    ("docs_written", "document ที่เขียน (MOVIES)"), ("genres_written", "document ที่เขียน (GENRE_ANALYSIS)"),
    ("algolia_mode", "Algolia"), ("algolia_records", "record ที่ส่งเข้า Algolia"),
    ("omdb_calls", "เรียก OMDb"), ("omdb_budget", "งบ OMDb รอบนี้"), ("tmdb_find_calls", "แปลงรหัส IMDb → TMDB"),
]


def main():
    ap = argparse.ArgumentParser(description="อัปเดตข้อมูลหนังใน Firestore แบบเฉพาะส่วนที่เปลี่ยน")
    ap.add_argument("--dry-run", action="store_true", help="คำนวณแต่ไม่เขียนฐานข้อมูล")
    ap.add_argument("--omdb-limit", type=int, default=int(os.getenv("OMDB_DAILY_LIMIT") or 0),
                    help="งบ OMDb รวมต่อรอบ (เช่น 450000 สำหรับ plan 500,000/วัน) ถ้าไม่ตั้ง ใช้ 900 ต่อ key")
    ap.add_argument("--omdb-budget-per-key", type=int, default=int(os.getenv("OMDB_BUDGET_PER_KEY", "900")))
    ap.add_argument("--cache-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".imdb_cache"))
    args = ap.parse_args()
    dry_run = args.dry_run or os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

    missing = [n for n in ("TMDB_API_KEY", "OMDB_API_KEYS", "GOOGLE_APPLICATION_CREDENTIALS") if not os.getenv(n)]
    if missing:
        raise SystemExit("ยังไม่ได้ตั้งค่า: " + ", ".join(missing))
    fm.TMDB_API_KEY = os.environ["TMDB_API_KEY"]
    fm.OMDB_KEYS = [k.strip() for k in os.environ["OMDB_API_KEYS"].split(",") if k.strip()]

    store = FirestoreStore(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    budget = args.omdb_limit or args.omdb_budget_per_key * len(fm.OMDB_KEYS)
    algolia = None
    if os.getenv("ALGOLIA_ADMIN_KEY"):
        algolia = AlgoliaClient(os.getenv("ALGOLIA_APP_ID") or ALGOLIA_APP_ID, os.environ["ALGOLIA_ADMIN_KEY"],
                                os.getenv("ALGOLIA_INDEX") or ALGOLIA_INDEX)
    else:
        print("ไม่ได้ตั้ง ALGOLIA_ADMIN_KEY — ข้ามการ sync ช่องค้นหา (Algolia)")
    stats = run(store, lambda today: load_imdb(args.cache_dir, today), dt.date.today(), budget,
                dry_run=dry_run, algolia=algolia)

    lines = [f"## อัปเดตข้อมูลหนัง {'(dry run — ไม่ได้เขียนฐานข้อมูล)' if dry_run else ''}", "", "| รายการ | จำนวน |", "|---|---:|"]
    lines += [f"| {label} | {stats[k]:,} |" if isinstance(stats[k], int) else f"| {label} | {stats[k]} |"
              for k, label in SUMMARY_LABELS]
    print("\n".join(lines))
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
