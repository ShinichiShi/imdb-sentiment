"""SQLite serving layer (the 'speed layer' view that the dashboard reads).

Raw + scored reviews live on HDFS; this DB only holds the running aggregates and
a rolling window of recent scored reviews, so the API stays fast.
"""
import os
import sqlite3
import time
from common import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY, ts REAL, title TEXT, text TEXT,
    score REAL, label INTEGER, true_label INTEGER);
CREATE INDEX IF NOT EXISTS idx_reviews_title_ts ON reviews(title, ts);
CREATE TABLE IF NOT EXISTS movie_stats (
    title TEXT PRIMARY KEY, n INTEGER, sum_score REAL, pos INTEGER, last_ts REAL);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


def connect():
    os.makedirs(settings.STATE_DIR, exist_ok=True)
    con = sqlite3.connect(settings.DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def set_meta(con, **kw):
    con.executemany("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                    [(k, str(v)) for k, v in kw.items()])


def get_meta(con):
    return {r["k"]: r["v"] for r in con.execute("SELECT k,v FROM meta")}


def add_scored(con, rows):
    """rows: dicts with id, ts, title, text, score, label, true_label.
    Maintains the running per-title aggregate incrementally (idempotent on id)."""
    for r in rows:
        cur = con.execute(
            "INSERT OR IGNORE INTO reviews VALUES(?,?,?,?,?,?,?)",
            (r["id"], r["ts"], r["title"], r["text"], r["score"], r["label"], r["true_label"]))
        if cur.rowcount:  # new review -> update running aggregate
            con.execute(
                """INSERT INTO movie_stats(title,n,sum_score,pos,last_ts) VALUES(?,?,?,?,?)
                   ON CONFLICT(title) DO UPDATE SET n=n+1, sum_score=sum_score+excluded.sum_score,
                   pos=pos+excluded.pos, last_ts=excluded.last_ts""",
                (r["title"], 1, r["score"], r["label"], r["ts"]))
    # keep the rolling window bounded
    con.execute("DELETE FROM reviews WHERE ts < ? AND true_label >= 0", (time.time() - 6 * 3600,))   # keep user reviews
    con.commit()


def reset(con):
    con.executescript("DELETE FROM reviews; DELETE FROM movie_stats; DELETE FROM meta;")
    con.commit()
