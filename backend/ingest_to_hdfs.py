"""Batch ingestion: archive the historical IMDB corpus and trained model on HDFS.

    /imdb/dataset/IMDB Dataset.csv     <- training corpus (batch layer)
    /imdb/model/*.pkl, metrics.json    <- model artefacts
The streaming layer later adds /imdb/stream/{raw,scored}/dt=.../part-*.jsonl
"""
import os
import sys

from common import settings, storage


def main():
    store = storage.wait_for_storage()
    uploads = [(settings.RAW_CSV, "/dataset"), (settings.MODEL_PATH, "/model"),
               (settings.VECTORIZER_PATH, "/model"), (settings.METRICS_PATH, "/model")]
    for local, dest in uploads:
        if not os.path.exists(local):
            print("skip (missing):", local)
            continue
        target = f"{settings.HDFS_BASE}{dest}/{os.path.basename(local)}"
        with open(local, "rb") as f:
            store.write(target, f.read())
        print(f"uploaded {local} -> {store.mode}:{target}")


if __name__ == "__main__":
    sys.exit(main())
