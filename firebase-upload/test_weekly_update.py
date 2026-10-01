# ทดสอบ weekly_update.py โดยไม่ต่อเน็ต: จำลอง TMDB / OMDb / ไฟล์ IMDb / Firestore
# รัน:  python -m unittest test_weekly_update.py   (ในโฟลเดอร์ firebase-upload)
import datetime as dt
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
        self.writes = {}

    def read_movies(self, fields):
        return {k: {f: v[f] for f in fields if f in v} for k, v in self.movies.items()}

    def read_genres(self):
        return dict(self.genres)

    def write(self, collection, docs):
        self.writes.setdefault(collection, {}).update({k: dict(v) for k, v in docs.items()})


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

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
            return FakeResponse(d if d else {"Response": "False", "Error": "not found"})
        path = u.path.replace("/3/", "", 1)
        if path.startswith("find/"):
            imdb_id = path.split("/")[1]
            for (kind, tid), d in self.tmdb.items():
                if d["external_ids"]["imdb_id"] == imdb_id:
                    return FakeResponse({"movie_results" if kind == "movie" else "tv_results": [{"id": tid}]})
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
         "Year": "2010", "Genre_for_cal": "ดราม่า"}
    d.update(wu.score_fields(meta, rt, imdb_rating, tmdb))
    d.update(extra)
    return d


def ratings_of(**votes_by_id):
    return {i: {"rating": r, "votes_num": v, "votes_str": f"{v:,}"} for i, (r, v) in votes_by_id.items()}


class WeeklyUpdateTest(unittest.TestCase):
    def setUp(self):
        fm.TMDB_API_KEY = "T"
        fm.OMDB_KEYS = ["O1"]
        fm.current_omdb_key_index = 0
        fm.omdb_exhausted = False
        fm.imdb_lookup.clear()

    def run_update(self, store, ratings, eligible, apis, budget=100, dry_run=False):
        fm.imdb_lookup.update(ratings)       # process_single_item() อ่านโหวตจากตรงนี้
        with mock.patch("requests.get", apis.get):
            return wu.run(store, lambda today: (ratings, eligible), TODAY, budget, dry_run=dry_run, log=lambda *a: None)

    def test_unchanged_titles_are_not_written(self):
        store = FakeStore({"tt0000001": existing()})
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
        stats = self.run_update(store, ratings, eligible, apis, budget=3)
        added = set(store.writes["MOVIES"])
        self.assertEqual(added, {"tt1000004", "tt1000003", "tt1000002"}, "ต้องเลือกเรื่องโหวตมากก่อน และไม่เกินโควตา 3")
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


if __name__ == "__main__":
    unittest.main()
