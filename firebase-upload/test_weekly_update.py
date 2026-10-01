# ทดสอบ weekly_update.py โดยไม่ต่อเน็ต: จำลอง TMDB / OMDb / ไฟล์ IMDb / Firestore
# รัน:  python -m unittest test_weekly_update.py   (ในโฟลเดอร์ firebase-upload)
import datetime as dt
import json
import pathlib
import os
import sys
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_movies as fm  # noqa: E402
import weekly_update as wu  # noqa: E402

TODAY = dt.date(2026, 10, 5)


class FakeStore:
    def __init__(self, movies, genres=None):
        self.movies = {k: dict(v) for k, v in movies.items()}
        self.genres = dict(genres or {})
        self.meta = {}
        self.writes = {}

    def read_movies(self, fields):
        if fields is None:
            return {k: dict(v) for k, v in self.movies.items()}
        return {k: {f: v[f] for f in fields if f in v} for k, v in self.movies.items()}

    def read_genres(self):
        return dict(self.genres)

    def read_doc(self, collection, doc_id):
        return dict(self.meta[doc_id]) if collection == "META" and doc_id in self.meta else None

    def delete(self, collection, doc_ids):
        self.deleted = getattr(self, "deleted", []) + list(doc_ids)
        for k in doc_ids:
            self.movies.pop(k, None)

    def write(self, collection, docs):
        self.writes.setdefault(collection, {}).update({k: dict(v) for k, v in docs.items()})
        if collection == "MOVIES":
            for k, v in docs.items():
                self.movies.setdefault(k, {}).update(v)
        if collection == "META":
            self.meta.update({k: dict(v) for k, v in docs.items()})


class FakeAlgolia:
    """Algolia REST ปลอม: เก็บ index เป็น dict ชื่อ -> {"records": {objectID: record}, "settings": {...}}"""

    def __init__(self, records, settings=None):
        self.indexes = {wu.ALGOLIA_INDEX: {"records": dict(records), "settings": dict(settings or {"searchableAttributes": ["Title_EN"]})}}
        self.calls = []

    def request(self, method, url, headers=None, data=None, timeout=None):
        path = urlparse(url).path
        body = json.loads(data) if data else None
        self.calls.append((method, path, body))
        parts = path.split("/")          # ['', '1', 'indexes', name, action, ...]
        name, action = parts[3], parts[4]
        idx = self.indexes.setdefault(name, {"records": {}, "settings": {}})
        if action == "query":
            hits = [dict(r, objectID=oid) for oid, r in list(idx["records"].items())[:body["hitsPerPage"]]]
            return FakeResponse({"nbHits": len(idx["records"]), "hits": hits})
        if action == "batch":
            for req in body["requests"]:
                if req["action"] == "addObject":
                    idx["records"][req["body"]["objectID"]] = dict(req["body"])
                elif req["action"] == "partialUpdateObject":
                    idx["records"].setdefault(req["objectID"], {}).update(req["body"])
                elif req["action"] == "deleteObject":
                    idx["records"].pop(req["body"]["objectID"], None)
            return FakeResponse({"taskID": len(self.calls)})
        if action == "operation":
            dest = self.indexes.setdefault(body["destination"], {"records": {}, "settings": {}})
            if body["operation"] == "copy":       # copy แบบระบุ scope: คัดลอกเฉพาะส่วนที่ขอ ไม่คัดลอก record
                if "settings" in body.get("scope", []):
                    dest["settings"] = dict(idx["settings"])
            elif body["operation"] == "move":
                self.indexes[body["destination"]] = idx
                del self.indexes[name]
            return FakeResponse({"taskID": len(self.calls)})
        if action == "task":
            return FakeResponse({"status": "published"})
        raise AssertionError(path)


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status
        self.text = json.dumps(data)

    def json(self):
        return self._data


class FakeApis:
    """TMDB + OMDb ปลอม: tmdb = {(kind, id): details}, omdb = {imdbID: {...}}"""

    def __init__(self, tmdb, omdb, discover=None):
        self.tmdb, self.omdb, self.discover = tmdb, omdb, discover or {}
        self.omdb_calls = []

    def get(self, url, params=None, timeout=None, **kw):
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        q.update({k: str(v) for k, v in (params or {}).items()})
        if "omdbapi.com" in u.netloc:
            self.omdb_calls.append(q["i"])
            d = self.omdb.get(q["i"])
            if d == "ERROR":
                return FakeResponse({}, 500)          # OMDb ล่ม / เน็ตหลุด
            return FakeResponse(d if d else {"Response": "False", "Error": "not found"})
        path = u.path.replace("/3/", "", 1)
        if path.startswith("find/"):
            imdb_id = path.split("/")[1]
            for (kind, tid), d in self.tmdb.items():
                if d["external_ids"]["imdb_id"] == imdb_id:
                    return FakeResponse({"movie_results" if kind == "movie" else "tv_results":
                                         [{"id": tid, "vote_count": d.get("vote_count", 0)}]})
            return FakeResponse({"movie_results": [], "tv_results": []})
        if path.startswith("discover/"):
            kind = path.split("/")[1]
            year = int(q.get("primary_release_year") or q.get("first_air_date_year"))
            results = self.discover.get((kind, year), [])
            return FakeResponse({"results": results if q.get("page") == "1" else [], "total_pages": 1})
        kind, tid = path.split("/")
        d = self.tmdb.get((kind, int(tid)))
        return FakeResponse(d if d else {"success": False}, 200 if d else 404)


def tmdb_movie(tid, imdb_id, year="2025", vote=7.0, pop=50.0, genre="ดราม่า"):
    return {"id": tid, "title": f"หนัง {tid}", "original_title": f"Movie {tid}", "release_date": f"{year}-03-01",
            "runtime": 120, "credits": {"crew": [{"job": "Director", "name": "D"}], "cast": [{"name": "A"}]},
            "external_ids": {"imdb_id": imdb_id}, "keywords": {"keywords": [{"name": "space"}]},
            "overview": "เรื่องย่อ", "genres": [{"name": genre}], "production_countries": [{"name": "TH"}],
            "vote_average": vote, "vote_count": 100, "popularity": pop, "poster_path": "/p.jpg", "original_language": "en"}


def omdb(meta="70", rt="80%"):
    ratings = [{"Source": "Rotten Tomatoes", "Value": rt}] if rt != "N/A" else []
    return {"Response": "True", "Title": "Movie", "Plot": "p", "Metascore": meta, "Rated": "PG", "Awards": "N/A", "Ratings": ratings}


def existing(imdb_rating="7.0", votes="10,000", tmdb=7.0, meta="70", rt="80%", **extra):
    d = {"imdbRating": imdb_rating, "imdbVotes": votes, "tmdbRating": tmdb, "Metascore": meta, "TomatoScore": rt,
         "Popularity": 10.0, "tmdbID": extra.pop("tmdbID", 1), "MediaType": "ภาพยนตร์", "Released": "2010-01-01",
         "tmdbVotes": "100",
         "Year": "2010", "Genre_for_cal": "ดราม่า"}
    d.update(wu.score_fields(meta, rt, imdb_rating, tmdb))
    d.update(extra)
    return d


def scored(movies):
    """เติม Audience_Score / Critics_Score ให้เหมือนที่ run() คำนวณ (ใช้กับเทสต์ที่คาดว่าไม่มีอะไรเปลี่ยน)"""
    def prior(f):
        vals = [m[f] for m in movies.values() if isinstance(m.get(f), (int, float))]
        return round(sum(vals) / len(vals), 1) if vals else 0
    pa, pc = prior("Audience_Average"), prior("Critics_Average")
    for m in movies.values():
        v = wu.strict_int(m.get("imdbVotes")) or 0
        m["Audience_Score"] = wu.weighted(m.get("Audience_Average"), v, pa)
        m["Critics_Score"] = wu.weighted(m.get("Critics_Average"), v, pc)
    return movies


def ratings_of(**votes_by_id):
    return {i: {"rating": r, "votes_num": v, "votes_str": f"{v:,}"} for i, (r, v) in votes_by_id.items()}


class WeeklyUpdateTest(unittest.TestCase):
    def setUp(self):
        fm.TMDB_API_KEY = "T"
        fm.OMDB_KEYS = ["O1"]
        fm.current_omdb_key_index = 0
        fm.omdb_exhausted = False
        fm.imdb_lookup.clear()

    def run_update(self, store, ratings, eligible, apis, budget=100, dry_run=False, algolia=None, today=TODAY):
        fm.imdb_lookup.update(ratings)       # process_single_item() อ่านโหวตจากตรงนี้
        client = wu.AlgoliaClient("APP", "ADMIN", wu.ALGOLIA_INDEX, http=algolia) if algolia else None
        with mock.patch("requests.get", apis.get):
            return wu.run(store, lambda today: (ratings, eligible), today, budget, dry_run=dry_run,
                          log=lambda *a: None, algolia=client)

    def test_unchanged_titles_are_not_written(self):
        store = FakeStore(scored({"tt0000001": existing()}))
        store.meta["ranking"] = {"priorAudience": 7.0, "priorCritics": 7.5}
        stats = self.run_update(store, ratings_of(tt0000001=("7.0", 10100)), {}, FakeApis({}, {}))
        self.assertEqual(store.writes.get("MOVIES", {}), {})
        self.assertEqual(stats["docs_written"], 0)

    def test_imdb_change_updates_votes_and_recomputes_scores(self):
        store = FakeStore({"tt0000001": existing()})
        self.run_update(store, ratings_of(tt0000001=("8.0", 20000)), {}, FakeApis({}, {}))
        w = store.writes["MOVIES"]["tt0000001"]
        self.assertEqual(w["imdbRating"], "8.0")
        self.assertEqual(w["imdbVotes"], "20,000")
        self.assertEqual(w["Audience_Average"], 7.5)
        self.assertEqual(w["Movie_Audience_SD"], fm.calculate_sd([8.0, 7.0]))

    def test_new_titles_added_by_votes_within_omdb_budget(self):
        tmdb = {("movie", 10 + i): tmdb_movie(10 + i, f"tt100000{i}") for i in range(5)}
        apis = FakeApis(tmdb, {f"tt100000{i}": omdb() for i in range(5)})
        ratings = ratings_of(**{f"tt100000{i}": ("7.5", 1000 + i * 100) for i in range(5)}, tt9999999=("6.0", 400))
        eligible = {f"tt100000{i}": 2025 for i in range(5)}
        store = FakeStore({})
        stats = self.run_update(store, ratings, eligible, apis, budget=5)   # 60% ของ 5 = 3 เรื่อง
        added = set(store.writes["MOVIES"])
        self.assertEqual(added, {"tt1000004", "tt1000003", "tt1000002"}, "ต้องเลือกเรื่องโหวตมากก่อน และไม่เกิน 60% ของงบ")
        self.assertEqual(len(apis.omdb_calls), 3)
        self.assertEqual(stats["backlog_left"], 2)
        doc = store.writes["MOVIES"]["tt1000004"]
        self.assertEqual(doc["Critics_Average"], 7.5)
        self.assertEqual(doc["Genre_for_cal"], "ดราม่า")
        self.assertEqual(doc["imdbVotes"], "1,400")

    def test_missing_scores_are_na_not_zero(self):
        tmdb = {("movie", 20): tmdb_movie(20, "tt2000000", vote=0)}
        apis = FakeApis(tmdb, {"tt2000000": omdb(meta="N/A", rt="N/A")})
        store = FakeStore({})
        self.run_update(store, ratings_of(tt2000000=("6.5", 900)), {"tt2000000": 2025}, apis)
        doc = store.writes["MOVIES"]["tt2000000"]
        self.assertEqual(doc["Critics_Average"], "N/A")
        self.assertEqual(doc["tmdbRating"], "N/A")
        self.assertEqual(doc["Audience_Average"], 6.5)

    def test_new_doc_scores_match_original_formula(self):
        tmdb = {("movie", 30): tmdb_movie(30, "tt3000000", vote=6.4)}
        apis = FakeApis(tmdb, {"tt3000000": omdb(meta="55", rt="91%")})
        store = FakeStore({})
        self.run_update(store, ratings_of(tt3000000=("7.1", 5000)), {"tt3000000": 2025}, apis)
        doc = store.writes["MOVIES"]["tt3000000"]
        expected = wu.score_fields("55", "91%", "7.1", 6.4)
        for k, v in expected.items():
            self.assertEqual(doc[k], v, k)

    def test_dry_run_writes_nothing(self):
        store = FakeStore({"tt0000001": existing()})
        stats = self.run_update(store, ratings_of(tt0000001=("9.0", 50000)), {}, FakeApis({}, {}), dry_run=True)
        self.assertEqual(store.writes, {})
        self.assertEqual(stats["docs_written"], 1)

    def test_repairs_zero_written_by_first_import(self):
        bad = existing(meta="N/A", rt="N/A", tmdb=0)
        bad.update({"Critics_Average": 0, "Movie_Critics_SD": "N/A"})
        store = FakeStore({"tt0000002": bad})
        stats = self.run_update(store, ratings_of(tt0000002=("7.0", 10000)), {}, FakeApis({}, {}))
        w = store.writes["MOVIES"]["tt0000002"]
        self.assertEqual(w["Critics_Average"], "N/A")
        self.assertEqual(w["tmdbRating"], "N/A")
        self.assertEqual(stats["repaired"], 1)

    def test_popularity_and_tmdb_rating_refresh_for_recent_years(self):
        store = FakeStore({"tt0000003": existing(tmdbID=77, Released="2025-05-01", Year="2025")})
        apis = FakeApis({}, {"tt0000003": omdb()}, discover={("movie", 2025): [{"id": 77, "popularity": 99.0, "vote_average": 6.0}]})
        self.run_update(store, ratings_of(tt0000003=("7.0", 10000)), {}, apis, budget=0)
        w = store.writes["MOVIES"]["tt0000003"]
        self.assertEqual(w["Popularity"], 99.0)
        self.assertEqual(w["tmdbRating"], 6.0)
        self.assertEqual(w["Audience_Average"], 6.5)

    def test_recent_movie_critic_scores_refresh(self):
        store = FakeStore({"tt0000004": existing(Released="2026-06-01", Year="2026")})
        apis = FakeApis({}, {"tt0000004": omdb(meta="90", rt="95%")})
        stats = self.run_update(store, ratings_of(tt0000004=("7.0", 10000)), {}, apis)
        w = store.writes["MOVIES"]["tt0000004"]
        self.assertEqual((w["Metascore"], w["TomatoScore"], w["Critics_Average"]), ("90", "95%", 9.25))
        self.assertEqual(stats["critics_refreshed"], 1)

    def test_genre_analysis_written_only_when_changed(self):
        movies = {"tt0000005": existing(), "tt0000006": existing(imdb_rating="9.0", meta="40", rt="60%")}
        store = FakeStore(movies)
        self.run_update(store, ratings_of(tt0000005=("7.0", 10000), tt0000006=("9.0", 10000)), {}, FakeApis({}, {}))
        g = store.writes["GENRE_ANALYSIS"]["ดราม่า"]
        self.assertEqual(g["Genre_Critics_SD"], fm.calculate_sd([7.5, 5.0]))
        store2 = FakeStore(movies, genres={"ดราม่า": g})
        self.run_update(store2, ratings_of(tt0000005=("7.0", 10000), tt0000006=("9.0", 10000)), {}, FakeApis({}, {}))
        self.assertEqual(store2.writes.get("GENRE_ANALYSIS", {}), {})

    def test_new_title_not_added_when_omdb_fails(self):
        tmdb = {("movie", 40): tmdb_movie(40, "tt4000000"), ("movie", 41): tmdb_movie(41, "tt4000001")}
        apis = FakeApis(tmdb, {"tt4000000": "ERROR", "tt4000001": omdb()})
        store = FakeStore({})
        ratings = ratings_of(tt4000000=("7.0", 9000), tt4000001=("7.0", 8000))
        stats = self.run_update(store, ratings, {"tt4000000": 2025, "tt4000001": 2025}, apis)
        self.assertEqual(set(store.writes["MOVIES"]), {"tt4000001"}, "เรื่องที่ OMDb ตอบไม่ได้ต้องไม่ถูกเพิ่มแบบข้อมูลไม่ครบ")
        self.assertEqual(stats["new_omdb_failed"], 1)
        self.assertEqual(stats["backlog_left"], 1, "ต้องเหลือไว้ทำรอบหน้า")

    def test_new_title_not_added_after_budget_runs_out(self):
        # งบ 1 → เรื่องใหม่ได้ int(0.6) = 0 ครั้ง: ต้องไม่เพิ่มเรื่องที่ไม่ได้ถาม OMDb เลย
        tmdb = {("movie", 50): tmdb_movie(50, "tt5000000")}
        store = FakeStore({})
        stats = self.run_update(store, ratings_of(tt5000000=("7.0", 9000)), {"tt5000000": 2025},
                                FakeApis(tmdb, {"tt5000000": omdb()}), budget=1)
        self.assertNotIn("tt5000000", store.writes.get("MOVIES", {}))
        self.assertEqual(stats["added"], 0)

    def test_backfill_fills_missing_critics_for_old_titles(self):
        old = existing(meta="N/A", rt="N/A")
        old.update({"Critics_Average": 0})
        store = FakeStore({"tt0000007": old})
        apis = FakeApis({}, {"tt0000007": omdb(meta="60", rt="70%")})
        stats = self.run_update(store, ratings_of(tt0000007=("7.0", 10000)), {}, apis)
        w = store.writes["MOVIES"]["tt0000007"]
        self.assertEqual((w["Metascore"], w["TomatoScore"], w["Critics_Average"]), ("60", "70%", 6.5))
        self.assertEqual(w["omdbCheckedAt"], TODAY.isoformat())
        self.assertEqual(w["Movie_Critics_SD"], fm.calculate_sd([6.0, 7.0]))
        self.assertEqual(stats["backfilled"], 1)

    def test_backfill_skips_titles_checked_recently_and_marks_no_data(self):
        recent_check = existing(meta="N/A", rt="N/A", omdbCheckedAt=(TODAY - dt.timedelta(days=30)).isoformat())
        never = existing(meta="N/A", rt="N/A")
        store = FakeStore({"tt0000008": recent_check, "tt0000009": never})
        apis = FakeApis({}, {})     # OMDb ไม่มีคะแนนเรื่องไหนเลย
        self.run_update(store, ratings_of(tt0000008=("7.0", 10000), tt0000009=("7.0", 10000)), {}, apis)
        self.assertEqual(apis.omdb_calls, ["tt0000009"], "เรื่องที่เพิ่งตรวจเมื่อ 30 วันก่อนต้องไม่ถูกถามซ้ำ")
        self.assertEqual(store.writes["MOVIES"]["tt0000009"]["omdbCheckedAt"], TODAY.isoformat())

    def test_dry_run_calls_omdb_at_most_20_times(self):
        movies = {f"tt01{i:05d}": existing(meta="N/A", rt="N/A") for i in range(50)}
        apis = FakeApis({}, {})
        store = FakeStore(movies)
        stats = self.run_update(store, ratings_of(**{k: ("7.0", 10000) for k in movies}), {}, apis, budget=450000, dry_run=True)
        self.assertLessEqual(len(apis.omdb_calls), 20)
        self.assertEqual(stats["backfill_candidates"], 50)
        self.assertEqual(store.writes, {})

    def test_budget_split_new_refresh_backfill(self):
        tmdb = {("movie", 100 + i): tmdb_movie(100 + i, f"tt60000{i:02d}") for i in range(20)}
        omdb_data = {f"tt60000{i:02d}": omdb() for i in range(20)}
        movies = {}
        for i in range(10):
            movies[f"tt70000{i:02d}"] = existing(Released="2026-06-01", Year="2026")     # รีเฟรช
            movies[f"tt80000{i:02d}"] = existing(meta="N/A", rt="N/A")                    # เติมคะแนน
        omdb_data.update({k: omdb(meta="88") for k in movies})
        apis = FakeApis(tmdb, omdb_data)
        ratings = ratings_of(**{f"tt60000{i:02d}": ("7.0", 5000 + i) for i in range(20)}, **{k: ("7.0", 10000) for k in movies})
        stats = self.run_update(FakeStore(movies), ratings, {f"tt60000{i:02d}": 2025 for i in range(20)}, apis, budget=10)
        new_calls = [c for c in apis.omdb_calls if c.startswith("tt6")]
        refresh_calls = [c for c in apis.omdb_calls if c.startswith("tt7")]
        backfill_calls = [c for c in apis.omdb_calls if c.startswith("tt8")]
        self.assertEqual((len(new_calls), len(refresh_calls), len(backfill_calls)), (6, 2, 2))
        self.assertEqual(stats["omdb_calls"], 10)

    # ---------------- Algolia ----------------
    def test_algolia_full_replace_when_object_ids_are_not_imdb_ids(self):
        movies = {"tt0000011": existing(), "tt0000012": existing()}
        # ข้อมูลที่อัปโหลดมือ: objectID สุ่ม และคะแนนเก่า
        algolia = FakeAlgolia({"a1b2c3": {"imdbID": "tt0000011", "Critics_Average": 0},
                               "d4e5f6": {"imdbID": "tt0000012", "Critics_Average": 0}})
        store = FakeStore(movies)
        stats = self.run_update(store, ratings_of(tt0000011=("9.0", 30000), tt0000012=("7.0", 10000)), {},
                                FakeApis({}, {}), algolia=algolia, today=dt.date(2026, 10, 12))
        main = algolia.indexes[wu.ALGOLIA_INDEX]
        self.assertEqual(set(main["records"]), {"tt0000011", "tt0000012"}, "ต้องไม่มี record เก่าที่ objectID สุ่มค้างอยู่")
        self.assertEqual(main["records"]["tt0000011"]["imdbRating"], "9.0", "ต้องเป็นข้อมูลล่าสุดหลังเขียน Firestore")
        self.assertEqual(main["settings"], {"searchableAttributes": ["Title_EN"]}, "ต้องเก็บ settings เดิมไว้")
        self.assertNotIn(wu.ALGOLIA_INDEX + "_tmp", algolia.indexes)
        self.assertEqual((stats["algolia_mode"], stats["algolia_records"]), ("แทนที่ทั้ง index", 2))

    def test_algolia_incremental_update_only_changed_docs(self):
        movies = scored({f"tt00001{i:02d}": existing() for i in range(10)})
        algolia = FakeAlgolia({k: dict(v, imdbID=k) for k, v in movies.items()})
        store = FakeStore(movies)
        store.meta["ranking"] = {"priorAudience": 7.0, "priorCritics": 7.5}
        ratings = ratings_of(**{k: ("7.0", 10000) for k in movies})
        ratings["tt0000105"] = {"rating": "8.8", "votes_num": 99000, "votes_str": "99,000"}
        stats = self.run_update(store, ratings, {}, FakeApis({}, {}), algolia=algolia, today=dt.date(2026, 10, 12))
        batches = [b for m, p, b in algolia.calls if p.endswith("/batch")]
        sent = [r["objectID"] for b in batches for r in b["requests"]]
        self.assertEqual(sent, ["tt0000105"])
        self.assertEqual(batches[0]["requests"][0]["action"], "partialUpdateObject")
        self.assertEqual(algolia.indexes[wu.ALGOLIA_INDEX]["records"]["tt0000105"]["imdbRating"], "8.8")
        self.assertEqual(stats["algolia_mode"], "อัปเดตทีละเรื่อง")

    def test_algolia_full_replace_on_first_week_of_month(self):
        movies = {"tt0000013": existing()}
        algolia = FakeAlgolia({"tt0000013": dict(movies["tt0000013"], imdbID="tt0000013")})
        stats = self.run_update(FakeStore(movies), ratings_of(tt0000013=("7.0", 10000)), {}, FakeApis({}, {}),
                                algolia=algolia, today=dt.date(2026, 11, 2))
        self.assertEqual(stats["algolia_mode"], "แทนที่ทั้ง index")

    def test_algolia_not_called_on_dry_run(self):
        algolia = FakeAlgolia({})
        self.run_update(FakeStore({"tt0000014": existing()}), ratings_of(tt0000014=("9.0", 50000)), {},
                        FakeApis({}, {}), dry_run=True, algolia=algolia)
        self.assertEqual(algolia.calls, [])

    def test_algolia_record_is_trimmed_when_too_large(self):
        rec = wu.algolia_record("tt1", {"Plot": "ก" * 6000, "Title_EN": "X"})
        self.assertEqual(rec["objectID"], "tt1")
        self.assertLessEqual(len(json.dumps(rec, ensure_ascii=False).encode("utf-8")), wu.ALGOLIA_MAX_RECORD_BYTES)

    # ---------------- เกณฑ์ TMDB ≥ 10 และคะแนนถ่วงโหวต ----------------
    def test_new_titles_with_few_tmdb_votes_are_skipped(self):
        low = tmdb_movie(90, "tt9000000"); low["vote_count"] = 3
        tmdb = {("movie", 90): low, ("movie", 91): tmdb_movie(91, "tt9000001")}
        apis = FakeApis(tmdb, {"tt9000000": omdb(), "tt9000001": omdb()})
        store = FakeStore({})
        stats = self.run_update(store, ratings_of(tt9000000=("9.9", 700), tt9000001=("7.0", 5000)),
                                {"tt9000000": 2025, "tt9000001": 2025}, apis)
        self.assertEqual(set(store.writes["MOVIES"]), {"tt9000001"})
        self.assertEqual(stats["new_low_tmdb"], 1)
        self.assertNotIn("tt9000000", apis.omdb_calls, "เรื่องที่ไม่ผ่านเกณฑ์ต้องไม่เปลืองโควตา OMDb")

    def test_existing_titles_with_few_tmdb_votes_are_removed(self):
        movies = {f"tt02{i:05d}": existing() for i in range(9)}
        movies["tt0299999"] = existing(tmdbVotes="4")
        movies["tt0288888"] = existing(tmdbVotes="N/A")    # ไม่มีข้อมูล → ห้ามลบ
        del movies["tt0200000"]["tmdbVotes"]                 # ไม่มีฟิลด์ → ห้ามลบ
        algolia = FakeAlgolia({k: dict(v, imdbID=k) for k, v in movies.items()})
        store = FakeStore(movies)
        stats = self.run_update(store, ratings_of(**{k: ("7.0", 10000) for k in movies}), {}, FakeApis({}, {}),
                                algolia=algolia, today=dt.date(2026, 10, 12))
        self.assertEqual(stats["removed_low_tmdb"], 1)
        self.assertNotIn("tt0299999", store.movies)
        self.assertIn("tt0288888", store.movies)
        self.assertIn("tt0200000", store.movies)
        self.assertNotIn("tt0299999", algolia.indexes[wu.ALGOLIA_INDEX]["records"], "ต้องลบออกจาก Algolia ด้วย")

    def test_removal_skipped_when_suspiciously_many(self):
        movies = {f"tt03{i:05d}": existing(tmdbVotes="2") for i in range(4)}
        movies["tt0399999"] = existing()
        store = FakeStore(movies)
        stats = self.run_update(store, ratings_of(**{k: ("7.0", 10000) for k in movies}), {}, FakeApis({}, {}))
        self.assertEqual(stats["removed_low_tmdb"], 0)
        self.assertEqual(len(store.movies), 5)

    def test_weighted_score_puts_well_known_above_obscure(self):
        movies = {
            "tt0400001": existing(imdb_rating="9.8", votes="600", tmdb=9.8),          # โหวตน้อย คะแนนสูงมาก
            "tt0400002": existing(imdb_rating="8.6", votes="1,000,000", tmdb=8.6),    # หนังดังคะแนนดี
            "tt0400003": existing(imdb_rating="6.0", votes="50,000", tmdb=6.0),
        }
        store = FakeStore(movies)
        self.run_update(store, ratings_of(tt0400001=("9.8", 600), tt0400002=("8.6", 1000000), tt0400003=("6.0", 50000)),
                        {}, FakeApis({}, {}))
        sc = {k: store.movies[k]["Audience_Score"] for k in movies}
        self.assertGreater(sc["tt0400002"], sc["tt0400001"])
        self.assertEqual(store.movies["tt0400001"]["Audience_Average"], 9.8, "ค่าที่แสดงบนการ์ดต้องไม่เปลี่ยน")
        self.assertEqual(wu.weighted("N/A", 1000, 7.0), "N/A")
        self.assertIn("priorAudience", store.meta["ranking"], "ค่ากลางต้องถูกเก็บไว้ใช้รอบต่อไป")

    def test_prior_is_reused_so_scores_do_not_churn(self):
        movies = scored({f"tt05{i:05d}": existing() for i in range(10)})
        store = FakeStore(movies)
        store.meta["ranking"] = {"priorAudience": 7.0, "priorCritics": 7.5}
        ratings = ratings_of(**{k: ("7.0", 10000) for k in movies})
        ratings["tt0500003"] = {"rating": "9.9", "votes_num": 10000, "votes_str": "10,000"}   # ค่าเฉลี่ยทั้งฐานขยับ
        self.run_update(store, ratings, {}, FakeApis({}, {}))
        self.assertEqual(set(store.writes["MOVIES"]), {"tt0500003"}, "เรื่องอื่นต้องไม่ถูกเขียนคะแนนใหม่ทั้งฐาน")
        self.assertNotIn("META", store.writes)

    # ---------------- Genres (หลายประเภทต่อเรื่อง) และเพดาน Algolia ----------------
    def test_genre_table_matches_index_html(self):
        import re
        html = pathlib.Path(__file__).resolve().parent.parent.joinpath("index.html").read_text(encoding="utf-8")
        block = html[html.index("const GENRE_VARIANTS = {"): html.index("};", html.index("const GENRE_VARIANTS = {"))]
        pairs = {k: re.findall(r'"([^"]+)"', v) for k, v in re.findall(r'"([^"]+)":\s*\[([^\]]*)\]', block)}
        aliases = set(re.findall(r'"([^"]+)":', html[html.index("const GENRE_CANONICAL"):].split(";")[0]))
        self.assertEqual({k: v for k, v in pairs.items() if k not in aliases}, wu.GENRE_VARIANTS)

    def test_menu_genres_mapping(self):
        self.assertEqual(wu.menu_genres(["บู๊, ผจญภัย", "แอนนิเมชั่น"]), ["บู๊", "ผจญ", "แอนนิเมชั่น"])
        self.assertEqual(wu.menu_genres(["จิตนิมิตแนววิทยาศาสตร์", "ละคร"]), ["จินตนาการ", "นิยายวิทยาศาสตร์", "หนังชีวิต"])
        self.assertEqual(wu.menu_genres(["ประเภทใหม่"]), ["ประเภทใหม่"])

    def test_new_titles_get_genres_array(self):
        d = tmdb_movie(60, "tt6000000"); d["genres"] = [{"name": "แอนนิเมชั่น"}, {"name": "ตลก"}]
        store = FakeStore({})
        self.run_update(store, ratings_of(tt6000000=("7.5", 9000)), {"tt6000000": 2025},
                        FakeApis({("movie", 60): d}, {"tt6000000": omdb()}))
        self.assertEqual(store.writes["MOVIES"]["tt6000000"]["Genres"], ["แอนนิเมชั่น", "ตลก"])

    def test_old_titles_get_genres_only_when_meta_complete(self):
        d = tmdb_movie(70, "tt0000020"); d["genres"] = [{"name": "สยองขวัญ"}]
        for complete in (False, True):
            store = FakeStore({"tt0000020": existing(tmdbID=70)})
            if complete:
                store.meta["genres"] = {"complete": True}
            stats = self.run_update(store, ratings_of(tt0000020=("7.0", 10000)), {}, FakeApis({("movie", 70): d}, {}))
            got = store.movies["tt0000020"].get("Genres")
            self.assertEqual(got, ["สยองขวัญ"] if complete else None, f"complete={complete}")
            self.assertEqual(stats["genres_filled"], 1 if complete else 0)

    def test_algolia_full_replace_respects_record_cap(self):
        movies = {"tt0000031": existing(votes="1,000"), "tt0000032": existing(votes="900,000"), "tt0000033": existing(votes="50,000")}
        algolia = FakeAlgolia({"x1": {"imdbID": "tt0000031"}})
        store = FakeStore(movies)
        client = wu.AlgoliaClient("APP", "ADMIN", wu.ALGOLIA_INDEX, http=algolia)
        mode, n = wu.sync_algolia(client, store, {}, store.read_movies(None), dt.date(2026, 10, 12),
                                  log=lambda *a: None, cap=2)
        self.assertEqual((mode, n), ("แทนที่ทั้ง index", 2))
        self.assertEqual(set(algolia.indexes[wu.ALGOLIA_INDEX]["records"]), {"tt0000032", "tt0000033"},
                         "ต้องเก็บเรื่องที่โหวตมากที่สุด 2 เรื่อง")

    def test_algolia_incremental_drops_titles_outside_cap(self):
        movies = {"tt0000041": existing(votes="900,000"), "tt0000042": existing(votes="800,000"), "tt0000043": existing(votes="1,000")}
        algolia = FakeAlgolia({"tt0000041": {"imdbID": "tt0000041"}, "tt0000042": {"imdbID": "tt0000042"}})
        client = wu.AlgoliaClient("APP", "ADMIN", wu.ALGOLIA_INDEX, http=algolia)
        mode, _ = wu.sync_algolia(client, FakeStore(movies), {"tt0000041": {"imdbRating": "9.1"}, "tt0000043": {"imdbRating": "5.0"}},
                                  movies, dt.date(2026, 10, 12), log=lambda *a: None, cap=2)
        reqs = [r for m, p, b in algolia.calls if p.endswith("/batch") for r in b["requests"]]
        self.assertEqual(mode, "อัปเดตทีละเรื่อง")
        self.assertEqual([(r["action"], r.get("objectID") or r["body"]["objectID"]) for r in reqs],
                         [("partialUpdateObject", "tt0000041"), ("deleteObject", "tt0000043")])


if __name__ == "__main__":
    unittest.main()
