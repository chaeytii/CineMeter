# อัปเดตข้อมูลหนังใน Firestore แบบเฉพาะส่วนที่เปลี่ยน (รันทุกสัปดาห์ผ่าน GitHub Actions)
#
# ใช้ฟังก์ชันดึงข้อมูลและสูตรคำนวณจาก fetch_movies.py (สคริปต์ดึงข้อมูลชุดแรก) โดยตรง
# ข้อมูลที่ได้จึงหน้าตาเหมือนชุดเดิมทุกฟิลด์ ต่างกันแค่รอบนี้ไม่ดึงใหม่ทั้งฐาน:
#   1) คะแนน/โหวต IMDb ของทุกเรื่อง   — จากไฟล์ฟรีของ IMDb (ไม่ใช้ OMDb)
#   2) Popularity / คะแนน TMDB         — เฉพาะหนัง 3 ปีล่าสุด (ใช้กับหมวด Trending now)
#   3) เรื่องใหม่ที่โหวตเกิน 500         — ดึงครบทุกฟิลด์ จำกัดจำนวนตามโควตา OMDb
#   4) คะแนน RT / Metacritic            — เฉพาะหนังที่ออกฉายไม่เกิน 12 เดือน (ใช้โควตา OMDb ที่เหลือ)
#   5) GENRE_ANALYSIS                   — คำนวณใหม่จากข้อมูลทั้งฐาน
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
MAX_FIND_LOOKUPS = 5000        # จำกัดการแปลงรหัส IMDb → TMDB ต่อรอบ
BATCH_SIZE = 400
WORKERS = 8

# ฟิลด์ที่ต้องอ่านจาก Firestore เพื่อคำนวณ
READ_FIELDS = ["imdbRating", "imdbVotes", "tmdbRating", "Metascore", "TomatoScore", "Critics_Average",
               "Audience_Average", "Movie_Critics_SD", "Movie_Audience_SD", "Overall_SD",
               "Recommended_Trust_Side", "Popularity", "tmdbID", "MediaType", "Released", "Year", "Genre_for_cal"]
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
        return {d.id: d.to_dict() or {} for d in self.db.collection("MOVIES").select(fields).stream()}

    def read_genres(self):
        return {d.id: d.to_dict() or {} for d in self.db.collection("GENRE_ANALYSIS").stream()}

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
    data = tmdb_get(f"find/{imdb_id}", external_source="imdb_id")
    if data.get("movie_results"):
        return data["movie_results"][0]["id"], "movie"
    if data.get("tv_results"):
        return data["tv_results"][0]["id"], "tv"
    return None, None


def omdb_scores(imdb_id):
    data = fm.fetch_omdb_data(imdb_id)
    if not data or data.get("Response") != "True":
        return None
    tomato = "N/A"
    for r in data.get("Ratings", []):
        if r.get("Source") == "Rotten Tomatoes":
            tomato = r.get("Value", "N/A")
            break
    return {"Metascore": data.get("Metascore", "N/A"), "TomatoScore": tomato, "Awards": data.get("Awards", "N/A")}


# ---------------------------------------------------------------
# งานหลัก
# ---------------------------------------------------------------
def run(store, imdb_loader, today, omdb_budget, dry_run=False, log=print):
    stats = {"existing": 0, "imdb_updated": 0, "popularity_updated": 0, "repaired": 0, "added": 0,
             "critics_refreshed": 0, "omdb_calls": 0, "tmdb_find_calls": 0, "genres_written": 0,
             "backlog_left": 0, "docs_written": 0}

    movies = store.read_movies(READ_FIELDS)
    stats["existing"] = len(movies)
    log(f"Firestore: {len(movies):,} เรื่อง")
    ratings, eligible = imdb_loader(today)
    log(f"IMDb: {len(ratings):,} เรื่อง, ผ่านเกณฑ์ (โหวต > {MIN_IMDB_VOTES}, {START_YEAR}–{today.year}): {len(eligible):,}")

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

    # 3) เรื่องใหม่ (เรียงโหวตมากก่อน จำกัดตามโควตา OMDb)
    real_fetch = fm.fetch_omdb_data
    count_lock = threading.Lock()

    def counted_fetch(imdb_id):
        with count_lock:
            stats["omdb_calls"] += 1
        return real_fetch(imdb_id)
    fm.fetch_omdb_data = counted_fetch
    try:
        backlog = sorted((i for i in eligible if i not in movies), key=lambda i: -ratings[i]["votes_num"])
        log(f"เรื่องที่ยังไม่มีในฐาน: {len(backlog):,}")
        new_docs, pos = {}, 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            while pos < len(backlog) and stats["omdb_calls"] < omdb_budget and stats["tmdb_find_calls"] < MAX_FIND_LOOKUPS:
                chunk = backlog[pos: pos + max(1, min(WORKERS * 4, omdb_budget - stats["omdb_calls"]))]
                pos += len(chunk)
                stats["tmdb_find_calls"] += len(chunk)
                found = list(ex.map(find_tmdb, chunk))
                jobs = [(tid, kind) for tid, kind in found if tid]
                for item in ex.map(lambda j: fm.process_single_item({"id": j[0]}, j[1]), jobs):
                    if item and item["imdbID"] not in movies and item["imdbID"] not in new_docs:
                        new_docs[item["imdbID"]] = to_firestore_doc(item)
        stats["backlog_left"] = len(backlog) - pos
        for doc_id, d in new_docs.items():
            updates[doc_id] = d
            movies[doc_id] = dict(d)
        stats["added"] = len(new_docs)

        # 4) RT / Metacritic ของหนังที่ออกฉายไม่เกิน 12 เดือน
        cutoff = (today - dt.timedelta(days=CRITICS_REFRESH_DAYS)).isoformat()
        def popularity(i):
            p = movies[i].get("Popularity")
            return p if isinstance(p, (int, float)) else 0
        recent = sorted((i for i, m in movies.items() if i not in new_docs and m.get("MediaType") != "ซีรีส์"
                         and str(m.get("Released") or "") >= cutoff), key=lambda i: -popularity(i))
        for doc_id in recent:
            if stats["omdb_calls"] >= omdb_budget or fm.omdb_exhausted:
                break
            sc = omdb_scores(doc_id)
            if not sc:
                continue
            m = movies[doc_id]
            if sc["Metascore"] != m.get("Metascore") or sc["TomatoScore"] != m.get("TomatoScore"):
                put(doc_id, sc)
                rescore.add(doc_id)
                stats["critics_refreshed"] += 1
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

    # 5) GENRE_ANALYSIS จากข้อมูลทั้งฐาน (วิธีเดียวกับ fetch_movies.py)
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
        store.write("GENRE_ANALYSIS", genre_updates)
    return stats


SUMMARY_LABELS = [
    ("existing", "เรื่องในฐานก่อนเริ่ม"), ("added", "เพิ่มเรื่องใหม่"), ("backlog_left", "เรื่องใหม่ที่รอรอบหน้า"),
    ("imdb_updated", "อัปเดตคะแนน/โหวต IMDb"), ("popularity_updated", "อัปเดต Popularity/คะแนน TMDB"),
    ("critics_refreshed", "อัปเดตคะแนน RT/Metacritic"), ("repaired", "ซ่อมค่า 0 → N/A"),
    ("docs_written", "document ที่เขียน (MOVIES)"), ("genres_written", "document ที่เขียน (GENRE_ANALYSIS)"),
    ("omdb_calls", "เรียก OMDb"), ("tmdb_find_calls", "แปลงรหัส IMDb → TMDB"),
]


def main():
    ap = argparse.ArgumentParser(description="อัปเดตข้อมูลหนังใน Firestore แบบเฉพาะส่วนที่เปลี่ยน")
    ap.add_argument("--dry-run", action="store_true", help="คำนวณแต่ไม่เขียนฐานข้อมูล")
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
    budget = args.omdb_budget_per_key * len(fm.OMDB_KEYS)
    stats = run(store, lambda today: load_imdb(args.cache_dir, today), dt.date.today(), budget, dry_run=dry_run)

    lines = [f"## อัปเดตข้อมูลหนัง {'(dry run — ไม่ได้เขียนฐานข้อมูล)' if dry_run else ''}", "", "| รายการ | จำนวน |", "|---|---:|"]
    lines += [f"| {label} | {stats[k]:,} |" for k, label in SUMMARY_LABELS]
    print("\n".join(lines))
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
