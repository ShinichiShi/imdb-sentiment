"""Replays the IMDB dataset as a live stream of reviews onto Kafka.

Each message is {id, ts, title, review, label}. The title is picked from the
mock catalogue (weighted by `buzz`); the review is drawn from the positive or
negative pool according to that title's `positivity`, so every movie develops a
different audience reaction. Rate / pause are controlled from the dashboard via
state/control.json.
"""
import json
import os
import random
import time
import uuid

import pandas as pd

from common import bus, settings
from common.catalog import MOVIES


def read_control():
    try:
        with open(settings.CONTROL_PATH) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {"rate": settings.DEFAULT_RATE, "paused": False}


def write_status(sent, rate, paused):
    tmp = settings.PRODUCER_STATUS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"sent": sent, "rate": rate, "paused": paused, "ts": time.time()}, f)
    os.replace(tmp, settings.PRODUCER_STATUS_PATH)


def main():
    os.makedirs(settings.STATE_DIR, exist_ok=True)
    df = pd.read_csv(settings.RAW_CSV)
    pools = {1: df[df.sentiment == "positive"].review.tolist(),
             0: df[df.sentiment == "negative"].review.tolist()}
    print(f"[producer] loaded {len(df)} reviews", flush=True)
    producer = bus.get_producer()
    weights = [m["buzz"] for m in MOVIES]
    sent = 0
    write_status(sent, 0, False)
    while True:
        ctl = read_control()
        rate, paused = float(ctl.get("rate", settings.DEFAULT_RATE)), bool(ctl.get("paused"))
        if paused or rate <= 0:
            write_status(sent, rate, True)
            time.sleep(0.5)
            continue
        movie = random.choices(MOVIES, weights)[0]
        label = 1 if random.random() < movie["positivity"] else 0
        producer.send({
            "id": uuid.uuid4().hex, "ts": time.time(), "title": movie["title"],
            "review": random.choice(pools[label]), "label": label})
        sent += 1
        if sent % 5 == 0:
            producer.flush()
            write_status(sent, rate, False)
        time.sleep(1.0 / rate)


if __name__ == "__main__":
    main()
