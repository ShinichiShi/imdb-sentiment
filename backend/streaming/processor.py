"""Stream processor: Kafka -> (HDFS raw) -> TF-IDF + LogReg scoring -> (HDFS scored)
-> running per-title aggregates.

Micro-batch loop:
  1. poll Kafka
  2. score every review (P(positive) from logistic regression on TF-IDF)
  3. update running averages in the serving DB
  4. buffer raw + scored records, flush to HDFS as JSONL part files
  5. commit the Kafka offsets (at-least-once; DB insert is idempotent on id)
"""
import json
import time
from datetime import datetime

import joblib

from common import bus, db, settings, storage
from common.textclean import clean_text, display_text


def hdfs_flush(store, buf_raw, buf_scored):
    if not buf_raw:
        return 0
    now = datetime.utcnow()
    part = f"dt={now:%Y-%m-%d}/hr={now:%H}/part-{now:%H%M%S}-{int(time.time()*1000) % 1000:03d}.jsonl"
    store.write(f"{settings.HDFS_BASE}/stream/raw/{part}",
                "\n".join(json.dumps(r) for r in buf_raw) + "\n")
    store.write(f"{settings.HDFS_BASE}/stream/scored/{part}",
                "\n".join(json.dumps(r) for r in buf_scored) + "\n")
    return len(buf_raw)


def main():
    print("[processor] loading model", flush=True)
    model = joblib.load(settings.MODEL_PATH)
    vec = joblib.load(settings.VECTORIZER_PATH)
    store = storage.wait_for_storage()
    consumer = bus.get_consumer()
    con = db.connect()
    print(f"[processor] ready: kafka={settings.KAFKA_BOOTSTRAP} storage={store.mode}", flush=True)

    buf_raw, buf_scored = [], []
    last_flush = time.time()
    consumed = int(db.get_meta(con).get("consumed", 0))
    hdfs_written = int(db.get_meta(con).get("hdfs_records", 0))
    hdfs_err = ""

    while True:
        msgs = consumer.poll(max_records=200, timeout=1.0)
        if msgs:
            probs = model.predict_proba(vec.transform([clean_text(m["review"]) for m in msgs]))[:, 1]
            rows = []
            for m, p in zip(msgs, probs):
                p = float(p)
                label = 1 if p >= 0.5 else 0
                rows.append({"id": m["id"], "ts": m["ts"], "title": m["title"],
                             "text": display_text(m["review"])[:600], "score": p,
                             "label": label, "true_label": m["label"]})
                buf_raw.append(m)
                buf_scored.append({"id": m["id"], "ts": m["ts"], "title": m["title"],
                                   "score": round(p, 4), "label": label})
            db.add_scored(con, rows)
            consumed += len(msgs)

        due = time.time() - last_flush >= settings.FLUSH_SECONDS or len(buf_raw) >= settings.FLUSH_MAX_RECORDS
        if buf_raw and due:
            try:
                hdfs_written += hdfs_flush(store, buf_raw, buf_scored)
                buf_raw, buf_scored, hdfs_err = [], [], ""
                consumer.commit()
            except Exception as e:  # noqa: BLE001  keep records buffered, retry next tick
                hdfs_err = f"{e.__class__.__name__}: {e}"[:200]
                print("[processor] HDFS write failed:", hdfs_err, flush=True)
            last_flush = time.time()
        elif not buf_raw and msgs:
            consumer.commit()

        db.set_meta(con, consumed=consumed, hdfs_records=hdfs_written, hdfs_error=hdfs_err,
                    lag=consumer.lag(), buffered=len(buf_raw), heartbeat=time.time(),
                    storage_mode=store.mode, kafka_mode="mock (file log)" if bus.is_mock()
                    else settings.KAFKA_BOOTSTRAP)
        con.commit()


if __name__ == "__main__":
    main()
