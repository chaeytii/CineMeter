# End-to-end run of cinemeter-live-check.html in headless Chromium with Firestore / Algolia / Gemini
# replaced by an in-process fake (so the page can be verified without the real services).
import json, re, sys, asyncio, functools
from playwright.async_api import async_playwright

DATA = json.load(open(sys.argv[1]))
PAGE = sys.argv[2]
NO_INDEX = "--no-index" in sys.argv

def fs_to_py(v):
    if v is None: return None
    if "stringValue" in v: return v["stringValue"]
    if "integerValue" in v: return int(v["integerValue"])
    if "doubleValue" in v: return float(v["doubleValue"])
    if "booleanValue" in v: return v["booleanValue"]
    if "nullValue" in v: return None
    if "referenceValue" in v: return ("__ref__", v["referenceValue"].split("/")[-1])
    if "arrayValue" in v: return [fs_to_py(x) for x in v["arrayValue"].get("values", [])]
    if "mapValue" in v: return {k: fs_to_py(x) for k, x in v["mapValue"].get("fields", {}).items()}
    raise ValueError(v)

def py_to_fs(v):
    if v is None: return {"nullValue": None}
    if isinstance(v, bool): return {"booleanValue": v}
    if isinstance(v, int): return {"integerValue": str(v)}
    if isinstance(v, float): return {"doubleValue": v}
    if isinstance(v, str): return {"stringValue": v}
    if isinstance(v, list): return {"arrayValue": {"values": [py_to_fs(x) for x in v]}}
    if isinstance(v, dict): return {"mapValue": {"fields": {k: py_to_fs(x) for k, x in v.items()}}}
    return {"stringValue": str(v)}

def rank(v):
    if v is None: return 0
    if isinstance(v, bool): return 1
    if isinstance(v, (int, float)): return 2
    if isinstance(v, str): return 4
    if isinstance(v, list): return 9
    return 10

def cmp(a, b):
    ra, rb = rank(a), rank(b)
    if ra != rb: return -1 if ra < rb else 1
    if a == b: return 0
    return -1 if a < b else 1

MISSING = object()
def get(doc, path):
    path = path.strip("`")
    if path == "__name__": return doc["id"]
    return doc.get(path, MISSING)

def match(doc, flt):
    if "compositeFilter" in flt: return all(match(doc, f) for f in flt["compositeFilter"]["filters"])
    if "unaryFilter" in flt:
        v = get(doc, flt["unaryFilter"]["field"]["fieldPath"])
        return v is not MISSING and v is not None
    f = flt["fieldFilter"]; v = get(doc, f["field"]["fieldPath"])
    if v is MISSING: return False
    val = fs_to_py(f["value"])
    if isinstance(val, tuple): val = val[1]
    op = f["op"]
    if op == "EQUAL": return cmp(v, val) == 0
    if op == "NOT_EQUAL": return v is not None and cmp(v, val) != 0
    if op == "IN": return any(cmp(v, x) == 0 for x in val)
    if op == "ARRAY_CONTAINS": return isinstance(v, list) and any(cmp(x, val) == 0 for x in v)
    same = rank(v) == rank(val)
    if op == "GREATER_THAN_OR_EQUAL": return same and cmp(v, val) >= 0
    if op == "GREATER_THAN": return same and cmp(v, val) > 0
    if op == "LESS_THAN_OR_EQUAL": return same and cmp(v, val) <= 0
    if op == "LESS_THAN": return same and cmp(v, val) < 0
    raise ValueError(op)

def fields_of(flt):
    if not flt: return []
    if "compositeFilter" in flt: return [x for f in flt["compositeFilter"]["filters"] for x in fields_of(f)]
    key = "unaryFilter" if "unaryFilter" in flt else "fieldFilter"
    return [flt[key]["field"]["fieldPath"].strip("`")]

def run_query(sq):
    col = sq["from"][0]["collectionId"]
    docs = [d for d in DATA.get(col, [])]
    where = sq.get("where")
    orders = [(o["field"]["fieldPath"].strip("`"), o.get("direction") == "DESCENDING") for o in sq.get("orderBy", [])]
    of = [f for f, _ in orders if f != "__name__"]
    if NO_INDEX and of and any(f not in of for f in fields_of(where)):
        raise PermissionError("The query requires an index. You can create it here: https://console.firebase.google.com/v1/r/project/movie-858f6/firestore/indexes?create_composite=FAKE")
    if where: docs = [d for d in docs if match(d, where)]
    docs = [d for d in docs if all(get(d, f) is not MISSING for f, _ in orders)]
    def key_cmp(a, b):
        for f, desc in orders:
            c = cmp(get(a, f), get(b, f)) * (-1 if desc else 1)
            if c: return c
        return 0
    docs.sort(key=functools.cmp_to_key(key_cmp))
    def cur_cmp(d, values):
        for (f, desc), v in zip(orders, values):
            val = fs_to_py(v); val = val[1] if isinstance(val, tuple) else val
            c = cmp(get(d, f), val) * (-1 if desc else 1)
            if c: return c
        return 0
    if "startAt" in sq:
        s = sq["startAt"]; docs = [d for d in docs if (cur_cmp(d, s["values"]) >= 0 if s.get("before") else cur_cmp(d, s["values"]) > 0)]
    if "endAt" in sq:
        e = sq["endAt"]; docs = [d for d in docs if (cur_cmp(d, e["values"]) < 0 if e.get("before") else cur_cmp(d, e["values"]) <= 0)]
    if "limit" in sq: docs = docs[: sq["limit"]]
    return col, docs

def doc_json(col, d):
    return {"name": f"projects/movie-858f6/databases/(default)/documents/{col}/{d['id']}",
            "fields": {k: py_to_fs(v) for k, v in d.items() if k != "id"}}

STATS = {"runQuery": 0, "agg": 0, "get": 0, "algolia": 0, "gemini": 0}

async def handle(route):
    req = route.request; url = req.url
    try:
        if "firestore.googleapis.com" in url:
            if url.endswith(":runQuery"):
                STATS["runQuery"] += 1
                col, docs = run_query(json.loads(req.post_data)["structuredQuery"])
                body = [{"document": doc_json(col, d), "readTime": "x"} for d in docs] or [{"readTime": "x"}]
                return await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
            if url.endswith(":runAggregationQuery"):
                STATS["agg"] += 1
                sq = json.loads(req.post_data)["structuredAggregationQuery"]["structuredQuery"]
                _, docs = run_query(sq)
                return await route.fulfill(status=200, content_type="application/json", body=json.dumps([{"result": {"aggregateFields": {"n": {"integerValue": str(len(docs))}}}}]))
            m = re.search(r"/documents/([^/]+)/([^/?]+)$", url)
            if m and req.method == "GET":
                STATS["get"] += 1
                from urllib.parse import unquote
                col, did = unquote(m.group(1)), unquote(m.group(2))
                d = next((x for x in DATA.get(col, []) if x["id"] == did), None)
                if not d: return await route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": {"message": "not found"}}))
                return await route.fulfill(status=200, content_type="application/json", body=json.dumps(doc_json(col, d)))
        if "algolia.net" in url:
            STATS["algolia"] += 1
            b = json.loads(req.post_data); q = b["query"].lower().replace("่", "").replace("้", "")
            def hit(m):
                t = (m.get("Title_EN", "") + " " + m.get("Title_TH", "")).lower().replace("-", " ")
                return q.replace("-", " ") in t or (q == "odysey" and "odyssey" in t) or (q == "godfathr" and "godfather" in t) or (q == "wick" and "wick" in t)
            hits = [dict(m, objectID=m["id"]) for m in DATA["MOVIES"] if hit(m)]
            hits.sort(key=lambda m: -m.get("imdbVotes", 0))
            per, page = b.get("hitsPerPage", 20), b.get("page", 0)
            return await route.fulfill(status=200, content_type="application/json", body=json.dumps({"hits": hits[page*per:(page+1)*per], "nbHits": len(hits), "page": page, "nbPages": max(1, -(-len(hits)//max(per, 1)))}))
        if "generativelanguage.googleapis.com" in url:
            STATS["gemini"] += 1
            b = json.loads(req.post_data); text = b["contents"][-1]["parts"][0]["text"]
            cur = re.search(r'"criticsAverage":([\d.]+).*?"audienceAverage":([\d.]+)', text)
            ids = re.findall(r'"id":"(tt\d+)"', text.split("[DATABASE_CANDIDATES]")[1]) if "[DATABASE_CANDIDATES]" in text else []
            if "Zorblax" in text: reply = {"reply": "ไม่มีข้อมูลหนังเรื่องนี้ในฐานข้อมูล CineMeter ครับ", "picks": []}
            elif "ฝั่งไหน" in text: reply = {"reply": "เรื่องนี้ควรเชื่อฝั่งคนดูหรือนักวิจารณ์ตามค่า S.D. ที่ต่ำกว่า ความเห็นตรงกัน", "picks": []}
            elif cur and "คะแนน" in text: reply = {"reply": f"นักวิจารณ์ {cur.group(1)} คนดู {cur.group(2)}", "picks": []}
            elif ids: reply = {"reply": "แนะนำ 3 เรื่องนี้", "picks": ids[:3]}
            else: reply = {"reply": "Method Acting คือเทคนิคการแสดงที่นักแสดงดึงประสบการณ์จริงมาใช้สวมบทบาท", "picks": []}
            return await route.fulfill(status=200, content_type="application/json", body=json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(reply, ensure_ascii=False)}]}}]}))
        if url.startswith("file:") or "fonts.g" in url:
            return await route.continue_() if url.startswith("file:") else await route.abort()
        return await route.abort()
    except PermissionError as e:
        return await route.fulfill(status=400, content_type="application/json", body=json.dumps([{"error": {"code": 400, "message": str(e), "status": "FAILED_PRECONDITION"}}]))

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", handle)
        await pg.goto("file://" + PAGE)
        await pg.fill("#sampleN", "200")
        await pg.click("#btn-all")
        await pg.wait_for_function("!document.querySelector('#btn-all').disabled", timeout=120000)
        await pg.click("#btn-ai")
        await pg.wait_for_function("!document.querySelector('#btn-ai').disabled", timeout=60000)
        summary = await pg.input_value("#summary")
        errs_in_page = await pg.evaluate("[...document.querySelectorAll('.err')].map(e => e.innerText)")
        await pg.screenshot(path=sys.argv[3], full_page=True)
        print("pageerrors:", errors)
        print("section errors:", errs_in_page)
        print("requests:", STATS)
        print(summary)
        await b.close()
asyncio.run(main())
