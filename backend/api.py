import json
import os
import time
import uuid

import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from common import bus, db, settings, storage
from common.catalog import BY_TITLE, LIB_BY_ID, LIB_BY_TITLE
from common.textclean import clean_text

app = FastAPI(title="IMDB Streaming Sentiment API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

model_path = settings.MODEL_PATH if os.path.exists(settings.MODEL_PATH) else \
    os.path.join(settings.ROOT, "model", "sentiment_model.pkl")
model = joblib.load(model_path)
vectorizer = joblib.load(settings.VECTORIZER_PATH)
vocab = vectorizer.get_feature_names_out()
_store = None


def store():
    global _store
    if _store is None:
        _store = storage.get_storage()
    return _store


def _json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return default


class ReviewRequest(BaseModel):
    review: str


class UserReview(BaseModel):
    imdb_id: str
    review: str


class Control(BaseModel):
    rate: float = None
    paused: bool = None


def predict(text):
    X = vectorizer.transform([clean_text(text)])
    p = float(model.predict_proba(X)[0, 1])
    # explainability: per-word contribution = tfidf weight * LR coefficient
    row = X.tocoo()
    words = sorted(({"word": vocab[j], "weight": float(v * model.coef_[0][j])}
                    for j, v in zip(row.col, row.data)), key=lambda w: -abs(w["weight"]))[:8]
    return {"sentiment": "positive" if p >= 0.5 else "negative", "score": p, "top_words": words}


@app.post("/api/predict")
@app.post("/predict/")
def predict_sentiment(request: ReviewRequest):
    return predict(request.review)


_producer = None


@app.post("/api/review")
def submit_review(r: UserReview):
    """Score a user-written review immediately and publish it to Kafka so it also
    flows through HDFS and the running per-title average like any streamed review."""
    global _producer
    movie = LIB_BY_ID.get(r.imdb_id)
    text = r.review.strip()
    if not movie:
        raise HTTPException(404, "unknown movie")
    if len(text) < 3 or len(text) > 5000:
        raise HTTPException(400, "review must be 3-5000 characters")
    result = predict(text)
    try:
        if _producer is None:
            _producer = bus.get_producer()
        _producer.send({"id": uuid.uuid4().hex, "ts": time.time(), "title": movie["title"],
                        "review": text, "label": -1})
        _producer.flush()
        result["published"] = True
    except Exception as e:  # noqa: BLE001
        result["published"] = False
        result["error"] = f"{e.__class__.__name__}"
    return result


@app.get("/api/summary")
def summary():
    con = db.connect()
    t = con.execute("SELECT COALESCE(SUM(n),0) n, COALESCE(SUM(sum_score),0) s, COALESCE(SUM(pos),0) p "
                    "FROM movie_stats").fetchone()
    now = time.time()
    last_min = con.execute("SELECT COUNT(*) c FROM reviews WHERE ts > ?", (now - 60,)).fetchone()["c"]
    acc = con.execute("SELECT COUNT(*) c, COALESCE(SUM(label=true_label),0) ok FROM reviews "
                      "WHERE true_label >= 0").fetchone()   # -1 = user-written (no ground truth)
    return {"total": t["n"], "avg_score": t["s"] / t["n"] if t["n"] else None,
            "pos_pct": t["p"] / t["n"] if t["n"] else None, "per_min": last_min,
            "live_accuracy": acc["ok"] / acc["c"] if acc["c"] else None, "movies": con.execute(
                "SELECT COUNT(*) c FROM movie_stats").fetchone()["c"]}


@app.get("/api/movies")
def movies():
    con = db.connect()
    now = time.time()
    out = []
    for r in con.execute("SELECT * FROM movie_stats ORDER BY sum_score*1.0/n DESC"):
        recent = con.execute("SELECT AVG(score) a, COUNT(*) c FROM (SELECT score FROM reviews "
                             "WHERE title=? ORDER BY ts DESC LIMIT 20)", (r["title"],)).fetchone()
        avg = r["sum_score"] / r["n"]
        meta = BY_TITLE.get(r["title"]) or LIB_BY_TITLE.get(r["title"], {})
        out.append({"title": r["title"], "year": meta.get("year"), "poster": meta.get("file"),
                    "imdb_score": meta.get("score"), "imdb_id": meta.get("id"),
                    "genres": meta.get("genres", []), "count": r["n"],
                    "avg_score": avg, "pos_pct": r["pos"] / r["n"],
                    "recent_avg": recent["a"], "trend": (recent["a"] - avg) if recent["a"] is not None else 0,
                    "idle_s": now - r["last_ts"]})
    return out


@app.get("/api/model/words")
def model_words(n: int = 15):
    """Most influential TF-IDF terms: largest positive / negative logistic-regression coefficients."""
    coef = model.coef_[0]
    order = coef.argsort()
    return {"positive": [{"word": vocab[i], "weight": float(coef[i])} for i in order[::-1][:n]],
            "negative": [{"word": vocab[i], "weight": float(coef[i])} for i in order[:n]]}


@app.get("/api/catalog")
def catalog():
    """Titles currently receiving the review stream."""
    return list(BY_TITLE.values())


@app.get("/api/movies/history")
def history(title: str, points: int = 80):
    """Running average sentiment after each review (downsampled)."""
    con = db.connect()
    rows = con.execute("SELECT ts, score FROM reviews WHERE title=? ORDER BY ts", (title,)).fetchall()
    run, series = 0.0, []
    for i, r in enumerate(rows, 1):
        run += r["score"]
        series.append({"ts": r["ts"], "n": i, "avg": run / i})
    if len(series) > points:
        step = len(series) / points
        series = [series[int(i * step)] for i in range(points - 1)] + [series[-1]]
    return series


@app.get("/api/recent")
def recent(limit: int = 25, title: str = None):
    con = db.connect()
    q, args = "SELECT * FROM reviews", []
    if title:
        q += " WHERE title=?"
        args.append(title)
    # user-written reviews (true_label = -1) are pinned above the streamed ones
    q += " ORDER BY (true_label = -1) DESC, ts DESC LIMIT ?"
    args.append(min(limit, 100))
    return [dict(r) for r in con.execute(q, args)]


@app.get("/api/pipeline")
def pipeline():
    con = db.connect()
    m = db.get_meta(con)
    prod = _json(settings.PRODUCER_STATUS_PATH, {})
    ctl = _json(settings.CONTROL_PATH, {"rate": settings.DEFAULT_RATE, "paused": False})
    now = time.time()
    try:
        s = store()
        files = sorted(s.listdir(settings.HDFS_BASE + "/stream"), key=lambda f: -f["mtime"])
        raw = s.usage(settings.HDFS_BASE + "/stream/raw")
        scored = s.usage(settings.HDFS_BASE + "/stream/scored")
        corpus = s.usage(settings.HDFS_BASE + "/dataset")
        hdfs_ok, mode = True, s.mode
    except Exception as e:  # noqa: BLE001
        files, raw, scored, corpus, hdfs_ok, mode = [], {}, {}, {}, False, f"unreachable ({e.__class__.__name__})"
    return {
        "producer": {"sent": prod.get("sent", 0), "alive": now - prod.get("ts", 0) < 10,
                     "rate": ctl.get("rate"), "paused": ctl.get("paused", False)},
        "kafka": {"mode": m.get("kafka_mode", "mock" if bus.is_mock() else settings.KAFKA_BOOTSTRAP),
                  "topic": settings.KAFKA_TOPIC, "group": settings.KAFKA_GROUP,
                  "lag": int(m.get("lag", 0))},
        "processor": {"alive": now - float(m.get("heartbeat", 0)) < 10,
                      "consumed": int(m.get("consumed", 0)), "buffered": int(m.get("buffered", 0))},
        "hdfs": {"ok": hdfs_ok, "mode": mode, "error": m.get("hdfs_error", ""),
                 "records": int(m.get("hdfs_records", 0)), "raw": raw, "scored": scored,
                 "dataset": corpus, "ui": settings.NAMENODE_UI,
                 "recent_files": [{"path": f["path"], "size": f["size"], "mtime": f["mtime"]} for f in files[:8]]},
        "model": _json(settings.METRICS_PATH, {}),
    }


@app.post("/api/control")
def control(c: Control):
    cur = _json(settings.CONTROL_PATH, {"rate": settings.DEFAULT_RATE, "paused": False})
    if c.rate is not None:
        cur["rate"] = max(0.2, min(50.0, c.rate))
    if c.paused is not None:
        cur["paused"] = c.paused
    os.makedirs(settings.STATE_DIR, exist_ok=True)
    with open(settings.CONTROL_PATH, "w") as f:
        json.dump(cur, f)
    return cur


@app.post("/api/reset")
def reset():
    """Clear dashboard aggregates (HDFS data is kept)."""
    con = db.connect()
    db.reset(con)
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True}


# Local/mock mode: serve the dashboard straight from the API (Docker uses nginx instead).
_fe = os.path.join(settings.ROOT, "frontend")
if os.path.isdir(_fe):
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    _posters = os.environ.get("POSTERS_DIR", os.path.join(settings.ROOT, "archive", "poster_downloads"))
    if os.path.isdir(_posters):
        app.mount("/posters", StaticFiles(directory=_posters), name="posters")
    app.mount("/static", StaticFiles(directory=os.path.join(_fe, "static")), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_fe, "index.html"))
