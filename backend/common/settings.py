"""Central configuration, driven by environment variables so the same code
runs in Docker (real Kafka + HDFS) and locally (mock Kafka + mock HDFS)."""
import os

ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())

# --- Kafka -----------------------------------------------------------------
# "mock" -> file-backed append-only log (no broker needed)
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "mock")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "movie-reviews")
KAFKA_GROUP = os.environ.get("KAFKA_GROUP", "sentiment-processor")

# --- HDFS ------------------------------------------------------------------
# "hdfs" -> WebHDFS on the NameNode, "local" -> directory standing in for HDFS
STORAGE = os.environ.get("STORAGE", "local")
WEBHDFS_URL = os.environ.get("WEBHDFS_URL", "http://namenode:9870")
HDFS_USER = os.environ.get("HDFS_USER", "root")
HDFS_BASE = os.environ.get("HDFS_BASE", "/imdb")
NAMENODE_UI = os.environ.get("NAMENODE_UI", "http://localhost:9870")

# --- Local state -----------------------------------------------------------
STATE_DIR = os.environ.get("STATE_DIR", os.path.join(ROOT, "state"))
MOCK_DIR = os.environ.get("MOCK_DIR", os.path.join(STATE_DIR, "mock"))
DB_PATH = os.path.join(STATE_DIR, "sentiment.db")
CONTROL_PATH = os.path.join(STATE_DIR, "control.json")
PRODUCER_STATUS_PATH = os.path.join(STATE_DIR, "producer_status.json")

# --- Model / data ----------------------------------------------------------
MODEL_PATH = os.environ.get("MODEL_PATH", os.path.join(ROOT, "model", "best_sentiment_model.pkl"))
VECTORIZER_PATH = os.environ.get(
    "VECTORIZER_PATH", os.path.join(ROOT, "data", "processed", "tfidf_vectorizer.pkl"))
METRICS_PATH = os.environ.get("METRICS_PATH", os.path.join(ROOT, "model", "metrics.json"))
RAW_CSV = os.environ.get("RAW_CSV", os.path.join(ROOT, "data", "raw", "IMDB Dataset.csv"))

# --- Streaming behaviour ---------------------------------------------------
FLUSH_SECONDS = float(os.environ.get("FLUSH_SECONDS", "5"))   # HDFS micro-batch interval
FLUSH_MAX_RECORDS = int(os.environ.get("FLUSH_MAX_RECORDS", "200"))
DEFAULT_RATE = float(os.environ.get("PRODUCER_RATE", "3"))     # reviews / second
