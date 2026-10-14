"""Message bus: Kafka, or a file-backed append-only log for the no-Docker mock."""
import json
import os
import time
from common import settings


# --------------------------------------------------------------------------
# Mock Kafka: one JSON line per message in MOCK_DIR/kafka/<topic>.log.
# Offsets are line numbers; the consumer persists its committed offset.
# --------------------------------------------------------------------------
class MockProducer:
    def __init__(self):
        d = os.path.join(settings.MOCK_DIR, "kafka")
        os.makedirs(d, exist_ok=True)
        self.path = os.path.join(d, settings.KAFKA_TOPIC + ".log")

    def send(self, msg: dict):
        with open(self.path, "a") as f:
            f.write(json.dumps(msg) + "\n")

    def flush(self):
        pass


class MockConsumer:
    def __init__(self):
        d = os.path.join(settings.MOCK_DIR, "kafka")
        os.makedirs(d, exist_ok=True)
        self.path = os.path.join(d, settings.KAFKA_TOPIC + ".log")
        self.offset_path = os.path.join(d, settings.KAFKA_GROUP + ".offset")
        open(self.path, "a").close()
        self.offset = int(open(self.offset_path).read()) if os.path.exists(self.offset_path) else 0
        self.pending = self.offset

    def _lines(self):
        with open(self.path) as f:
            return f.read().splitlines()

    def poll(self, max_records=200, timeout=1.0):
        lines = self._lines()
        batch = lines[self.pending:self.pending + max_records]
        self.pending += len(batch)
        if not batch:
            time.sleep(min(timeout, 0.5))
        return [json.loads(l) for l in batch]

    def commit(self):
        self.offset = self.pending
        with open(self.offset_path, "w") as f:
            f.write(str(self.offset))

    def lag(self):
        return max(0, len(self._lines()) - self.pending)


# --------------------------------------------------------------------------
# Real Kafka (kafka-python)
# --------------------------------------------------------------------------
class KafkaProd:
    def __init__(self):
        from kafka import KafkaProducer
        self.p = _retry(lambda: KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode(),
            key_serializer=lambda k: k.encode(),
            linger_ms=50))

    def send(self, msg: dict):
        # key = movie title -> all reviews of a movie land on the same partition (ordered)
        self.p.send(settings.KAFKA_TOPIC, key=msg["title"], value=msg)

    def flush(self):
        self.p.flush()


class KafkaCons:
    def __init__(self):
        from kafka import KafkaConsumer
        self.c = _retry(lambda: KafkaConsumer(
            settings.KAFKA_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP,
            group_id=settings.KAFKA_GROUP,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda b: json.loads(b.decode())))

    def poll(self, max_records=200, timeout=1.0):
        recs = self.c.poll(timeout_ms=int(timeout * 1000), max_records=max_records)
        return [r.value for batch in recs.values() for r in batch]

    def commit(self):
        self.c.commit()

    def lag(self):
        try:
            parts = self.c.assignment()
            if not parts:
                return 0
            ends = self.c.end_offsets(list(parts))
            return sum(max(0, ends[p] - self.c.position(p)) for p in parts)
        except Exception:  # noqa: BLE001
            return 0


def _retry(fn, tries=60, delay=3):
    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[bus] waiting for Kafka... ({e.__class__.__name__})", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"Kafka unavailable: {last}")


def is_mock():
    return settings.KAFKA_BOOTSTRAP == "mock"


def get_producer():
    return MockProducer() if is_mock() else KafkaProd()


def get_consumer():
    return MockConsumer() if is_mock() else KafkaCons()
