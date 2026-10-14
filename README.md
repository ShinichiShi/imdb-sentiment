# Movie Review Sentiment — Streaming Pipeline (Kafka + HDFS + TF-IDF/LogReg)

Near-real-time audience sentiment per movie title.

```
producer ──► Kafka (KRaft) ──► stream processor ──┬──► HDFS  /imdb/stream/{raw,scored}/dt=…/part-*.jsonl
 (IMDB replay)  topic movie-reviews   TF-IDF + LogReg  │
                                                      └──► running avg per title (SQLite) ──► FastAPI ──► dashboard
HDFS also holds the batch layer: /imdb/dataset (50K corpus) and /imdb/model (pickles, metrics.json)
```

| Layer | Tech |
|---|---|
| Ingestion | Kafka 3.7 (single-node KRaft), keyed by movie title, 3 partitions |
| Storage | Hadoop HDFS (NameNode + DataNode), written via WebHDFS |
| Model | scikit-learn TF-IDF (5000 features) + Logistic Regression, random-search tuned (≈89.4% acc, AUC 0.96) |
| Serving | FastAPI + SQLite aggregate store, nginx-served dashboard |
| Packaging | Docker Compose |

## Website (http://localhost:8501)
Home (poster marquee, live rails) · Library (8K searchable posters, detail modal) · Live Dashboard · Analysis (model metrics, word weights, IMDb-vs-live scatter, classifier).

## Poster archive
Put the poster dataset (`<imdb_score>_<imdb_id>.jpg` files) in `archive/poster_downloads/` (git-ignored; mounted into nginx). Titles, years and genres come from IMDb's public `title.basics`/`title.ratings` TSVs:
```bash
python scripts/build_library.py archive/poster_downloads <dir-with-imdb-tsv.gz>   # writes frontend/static/library.json + backend/common/catalog.json
```

## Mocking
- **Movie titles:** the IMDB reviews CSV has none, so the producer assigns reviews to 24 titles from the poster archive ([catalog.json](backend/common/catalog.json)). A title's audience `positivity` is derived from its IMDb score, so live sentiment tracks (but doesn't copy) the real rating.
- **Live stream:** the producer replays the dataset; rate/pause are controlled from the dashboard.
- **No Docker:** `KAFKA_BOOTSTRAP=mock` uses a file-backed log as Kafka, `STORAGE=local` uses a folder as HDFS.

## Run (full stack)
```bash
cd docker && docker compose up --build -d
```
- Dashboard: http://localhost:8501  · API: http://localhost:8000/docs · NameNode UI: http://localhost:9870
- Inspect HDFS: `docker compose exec namenode hdfs dfs -ls -R /imdb`
- Stop: `docker compose down` (add `-v` to wipe HDFS/state)

## Run (mock, no Docker)
```bash
pip install -r backend/requirements.txt
export PROJECT_ROOT=$PWD PYTHONPATH=backend
python -m streaming.producer &  python -m streaming.processor &
uvicorn api:app --app-dir backend --port 8000     # dashboard at http://localhost:8000
```

## Retrain
```bash
python backend/data_processing.py   # STORAGE=hdfs reads the corpus from HDFS
python backend/train_model.py       # writes model/ + model/metrics.json (Neptune optional: NEPTUNE_API_TOKEN)
```

## API
`GET /api/summary` · `/api/movies` · `/api/movies/history?title=` · `/api/recent` · `/api/pipeline` · `POST /api/predict` · `POST /api/control` · `POST /api/reset`

## Start / stop
```bash
cd docker
docker compose up --build -d      # start everything  → http://localhost:8501
docker compose down               # stop (keeps HDFS data + stats)
docker compose down -v            # stop and wipe HDFS data + stats
```
