import concurrent.futures
import csv
import gzip
import json
import os
import statistics
import threading
import time
import requests

# ==========================================
# 1. Config and API Keys
# ==========================================
# API key อ่านจาก Environment Variable — ห้ามพิมพ์ key ลงในไฟล์นี้ (ไฟล์นี้อยู่บน GitHub แบบ public)
#   Windows (Command Prompt):  set TMDB_API_KEY=xxxx  และ  set OMDB_API_KEYS=key1,key2
#   GitHub Actions: ตั้งใน Settings → Secrets and variables → Actions
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")

# OMDb Key Pool: ใส่หลาย key คั่นด้วย comma (key ละ 1,000 ครั้ง/วัน)
OMDB_KEYS = [k.strip() for k in os.getenv("OMDB_API_KEYS", "").split(",") if k.strip()]
current_omdb_key_index = 0
omdb_lock = threading.Lock()
omdb_exhausted = False

# Year Range (Production: 1980 - 2026)
START_YEAR = 1980
END_YEAR = 2026

MIN_IMDB_VOTES = 500
IMDB_FILE = "title.ratings.tsv.gz"

FILE_MOVIES = f"firebase_movies_{START_YEAR}_{END_YEAR}.json"
FILE_GENRE = f"firebase_genre_analysis_{START_YEAR}_{END_YEAR}.json"

# ==========================================
# 2. Setup IMDb Dataset
# ==========================================
imdb_lookup = {}

def setup_imdb_ratings():
    if not os.path.exists(IMDB_FILE):
        print("Downloading IMDb ratings database (~7MB)...")
        url = "https://datasets.imdbws.com/title.ratings.tsv.gz"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, stream=True)
        with open(IMDB_FILE, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        print("IMDb database downloaded successfully!")

    print("Loading IMDb data into memory...")
    with gzip.open(IMDB_FILE, "rt", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for row in reader:
            imdb_lookup[row[0]] = {
                "rating": row[1],
                "votes_num": int(row[2]),
                "votes_str": f"{int(row[2]):,}",
            }
    print(f"IMDb data loaded successfully. ({len(imdb_lookup):,} items)\n")

# ==========================================
# 3. Fetch OMDb Data (With Limit Protection)
# ==========================================
def fetch_omdb_data(imdb_id):
    global current_omdb_key_index, omdb_exhausted

    if omdb_exhausted:
        return None

    for _ in range(len(OMDB_KEYS)):
        with omdb_lock:
            active_key = OMDB_KEYS[current_omdb_key_index]

        url = f"http://www.omdbapi.com/?apikey={active_key}&i={imdb_id}"
        try:
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                data = res.json()
                if data.get("Error") == "Request limit reached!":
                    with omdb_lock:
                        current_omdb_key_index += 1
                        if current_omdb_key_index >= len(OMDB_KEYS):
                            omdb_exhausted = True
                            print("\n[Warning] All OMDb keys exhausted. Skipping OMDb fetching...")
                            return None
                    continue
                return data
        except Exception:
            pass
    return None

def calculate_sd(scores_list):
    valid_scores = [s for s in scores_list if isinstance(s, (int, float))]
    if len(valid_scores) >= 2:
        return round(statistics.stdev(valid_scores), 2)
    return "N/A"

# ==========================================
# 4. Process Single Item (Movie / TV)
# ==========================================
def process_single_item(item_summary, media_type="movie"):
    item_id = item_summary["id"]
    endpoint = "movie" if media_type == "movie" else "tv"
    details_url = f"https://api.themoviedb.org/3/{endpoint}/{item_id}?api_key={TMDB_API_KEY}&append_to_response=credits,external_ids,keywords&language=th-TH"

    try:
        res = requests.get(details_url, timeout=10)
        tmdb_data = res.json()
    except Exception:
        return None

    imdb_id = tmdb_data.get("external_ids", {}).get("imdb_id")

    if not imdb_id or imdb_id == "N/A":
        return None

    raw_votes = 0
    imdb_rating_raw = "N/A"
    imdb_votes_str = "N/A"

    if imdb_id in imdb_lookup:
        imdb_rating_raw = imdb_lookup[imdb_id]["rating"]
        raw_votes = imdb_lookup[imdb_id]["votes_num"]
        imdb_votes_str = imdb_lookup[imdb_id]["votes_str"]

    if raw_votes <= MIN_IMDB_VOTES:
        return None

    omdb_title = "N/A"
    omdb_plot = "N/A"
    tomato_raw = "N/A"
    metascore_raw = "N/A"
    rated = "N/A"
    awards = "N/A"

    if not omdb_exhausted:
        omdb_data = fetch_omdb_data(imdb_id)
        if omdb_data and omdb_data.get("Response") == "True":
            omdb_title = omdb_data.get("Title", "N/A")
            omdb_plot = omdb_data.get("Plot", "N/A")
            metascore_raw = omdb_data.get("Metascore", "N/A")
            rated = omdb_data.get("Rated", "N/A")
            awards = omdb_data.get("Awards", "N/A")
            for r in omdb_data.get("Ratings", []):
                if r.get("Source") == "Rotten Tomatoes":
                    tomato_raw = r.get("Value", "N/A")
                    break

    popularity = tmdb_data.get("popularity", 0.0)
    tmdb_id_val = tmdb_data.get("id", "N/A")

    kw_data = tmdb_data.get("keywords", {})
    if media_type == "movie":
        kw_list = kw_data.get("keywords", [])
    else:
        kw_list = kw_data.get("results", [])

    keyword_names = [kw["name"] for kw in kw_list if isinstance(kw, dict) and "name" in kw]
    keyword_string = ", ".join(keyword_names) if keyword_names else "N/A"

    if media_type == "movie":
        title_th = tmdb_data.get("title") or "N/A"
        original_title = tmdb_data.get("original_title") or title_th
        release_date = tmdb_data.get("release_date") or ""
        runtime = f"{tmdb_data.get('runtime')} min" if tmdb_data.get("runtime") else "N/A"
        directors = [c["name"] for c in tmdb_data.get("credits", {}).get("crew", []) if isinstance(c, dict) and c.get("job") == "Director"]
        media_type_th = "ภาพยนตร์"
    else:
        title_th = tmdb_data.get("name") or "N/A"
        original_title = tmdb_data.get("original_name") or title_th
        release_date = tmdb_data.get("first_air_date") or ""
        seasons = tmdb_data.get("number_of_seasons", 1)
        episodes = tmdb_data.get("number_of_episodes", 1)
        runtime = f"{seasons} Seasons ({episodes} Episodes)"
        directors = [c["name"] for c in tmdb_data.get("created_by", [])]
        media_type_th = "ซีรีส์"

    director_string = ", ".join(directors) if directors else "N/A"
    title_en = omdb_title if (omdb_title and omdb_title != "N/A") else original_title
    year_only = release_date.split("-")[0] if release_date else "N/A"

    plot_th = (tmdb_data.get("overview") or "").strip()
    final_plot = plot_th if plot_th else (omdb_plot if omdb_plot != "N/A" else "")

    genres = [g["name"] for g in tmdb_data.get("genres", []) if isinstance(g, dict) and "name" in g]
    genre_for_cal = genres[0] if genres else "N/A"

    # Extract Country properly
    countries = []
    prod_countries = tmdb_data.get("production_countries") or []
    if prod_countries:
        for c in prod_countries:
            if isinstance(c, dict) and "name" in c:
                countries.append(c["name"])
    else:
        origin_c = tmdb_data.get("origin_country") or []
        for c in origin_c:
            if isinstance(c, str):
                countries.append(c)
    country_string = ", ".join(countries) if countries else "N/A"

    c_scores_val = []
    if metascore_raw != "N/A":
        try: c_scores_val.append(float(metascore_raw) / 10.0)
        except: pass
    if tomato_raw != "N/A":
        try: c_scores_val.append(float(tomato_raw.replace("%", "")) / 10.0)
        except: pass
    critics_avg = round(sum(c_scores_val) / len(c_scores_val), 2) if c_scores_val else "N/A"

    a_scores_val = []
    tmdb_vote_avg = tmdb_data.get("vote_average", 0)
    if imdb_rating_raw != "N/A":
        try: a_scores_val.append(float(imdb_rating_raw))
        except: pass
    if tmdb_vote_avg > 0:
        a_scores_val.append(float(tmdb_vote_avg))
    audience_avg = round(sum(a_scores_val) / len(a_scores_val), 2) if a_scores_val else "N/A"

    movie_c_sd = calculate_sd(c_scores_val)
    movie_a_sd = calculate_sd(a_scores_val)
    overall_sd = calculate_sd(c_scores_val + a_scores_val)

    if movie_c_sd == "N/A" or movie_a_sd == "N/A":
        trust_side = "ข้อมูลไม่เพียงพอ"
    elif movie_c_sd < movie_a_sd:
        trust_side = "นักวิจารณ์ (Metascore/Rotten)"
    elif movie_a_sd < movie_c_sd:
        trust_side = "คนดู (IMDb/TMDb)"
    else:
        trust_side = "น่าเชื่อถือเท่ากัน"

    return {
        "imdbID": imdb_id,
        "Genre_for_cal": genre_for_cal,
        "Title_EN": title_en,
        "Title_TH": title_th,
        "MediaType": media_type_th,
        "Rated": rated,
        "Country": country_string,
        "Language": tmdb_data.get("original_language", "N/A"),
        "Awards": awards,
        "Year": year_only,
        "Released": release_date,
        "Runtime": runtime,
        "Plot": final_plot,
        "Director": director_string,
        "Actors": ", ".join([a["name"] for a in tmdb_data.get("credits", {}).get("cast", [])[:3]]),
        "Poster": f"https://image.tmdb.org/t/p/w500{tmdb_data.get('poster_path')}" if tmdb_data.get("poster_path") else "N/A",
        "Critics_Average": critics_avg,
        "Metascore": metascore_raw,
        "TomatoScore": tomato_raw,
        "tmdbRating": round(tmdb_vote_avg, 1) if tmdb_vote_avg else "N/A",
        "imdbRating": imdb_rating_raw,
        "Audience_Average": audience_avg,
        "imdbVotes": imdb_votes_str,
        "tmdbVotes": f"{tmdb_data.get('vote_count', 0):,}",
        "Recommended_Trust_Side": trust_side,
        "Movie_Critics_SD": movie_c_sd,
        "Movie_Audience_SD": movie_a_sd,
        "Popularity": popularity,
        "Overall_SD": overall_sd,
        "tmdbID": tmdb_id_val,
        "Keyword": keyword_string
    }

# ==========================================
# 5. Collect loop per year
# ==========================================
def collect_all_media_for_year(year, media_type):
    collected = []
    current_page = 1
    year_param = f"&primary_release_year={year}" if media_type == "movie" else f"&first_air_date_year={year}"

    while True:
        url = f"https://api.themoviedb.org/3/discover/{media_type}?api_key={TMDB_API_KEY}&sort_by=popularity.desc{year_param}&vote_count.gte=10&page={current_page}"
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
            results = data.get("results", [])
            if not results or current_page > data.get("total_pages", 1) or current_page > 500:
                break
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                futures = [executor.submit(process_single_item, item, media_type) for item in results]
                for f in concurrent.futures.as_completed(futures):
                    if f.result():
                        collected.append(f.result())
            current_page += 1
        except Exception:
            break

    label = "Movies" if media_type == "movie" else "TV Series"
    print(f"  - [{year}] {label}: {len(collected)} items found.")
    return collected

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    if not TMDB_API_KEY:
        raise SystemExit("ยังไม่ได้ตั้งค่า TMDB_API_KEY (ดูวิธีใน README หัวข้อ 'อัปเดตข้อมูลอัตโนมัติ')")
    start_time = time.time()
    setup_imdb_ratings()
    all_movies_table = []

    print(f"=== Start searching from {START_YEAR} to {END_YEAR} ===")
    for yr in range(START_YEAR, END_YEAR + 1):
        print(f"\nProcessing Year: {yr}...")
        movies_yr = collect_all_media_for_year(yr, "movie")
        series_yr = collect_all_media_for_year(yr, "tv")
        all_movies_table.extend(movies_yr + series_yr)
        print(f">> Total items collected so far: {len(all_movies_table)}")

    print("\nProcessing GENRE_ANALYSIS table...")
    genre_raw_scores = {}
    for movie in all_movies_table:
        g_cal = movie["Genre_for_cal"]
        c_avg = movie["Critics_Average"]
        a_avg = movie["Audience_Average"]

        if g_cal not in genre_raw_scores:
            genre_raw_scores[g_cal] = {"critics": [], "audience": []}
        if c_avg != "N/A":
            genre_raw_scores[g_cal]["critics"].append(c_avg)
        if a_avg != "N/A":
            genre_raw_scores[g_cal]["audience"].append(a_avg)

    genre_analysis_table = []
    for g_name, scores in genre_raw_scores.items():
        if g_name == "N/A": continue
        genre_analysis_table.append({
            "Genre_for_cal": g_name,
            "Genre_Audience_SD": calculate_sd(scores["audience"]),
            "Genre_Critics_SD": calculate_sd(scores["critics"]),
        })

    with open(FILE_MOVIES, "w", encoding="utf-8") as f:
        json.dump(all_movies_table, f, indent=4, ensure_ascii=False)
    with open(FILE_GENRE, "w", encoding="utf-8") as f:
        json.dump(genre_analysis_table, f, indent=4, ensure_ascii=False)

    end_time = time.time()
    print(f"\nDone! Exported 2 Collections successfully.")
    print(f"Total Movies/TV Series: {len(all_movies_table)}")
    print(f"Total Genres Processed: {len(genre_analysis_table)}")
    print(f"Time taken: {round((end_time - start_time)/60, 2)} minutes.")


if __name__ == "__main__":
    main()
