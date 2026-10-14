"""HDFS access layer with a local-directory mock.

Both back-ends expose the same tiny API so the pipeline code is identical:
    write(path, data) / read(path) / listdir(path) / usage(path)
"""
import os
import time
from common import settings


class LocalStorage:
    """Stands in for HDFS: HDFS paths map to files under MOCK_DIR/hdfs."""
    mode = "local (mock HDFS)"

    def __init__(self):
        self.root = os.path.join(settings.MOCK_DIR, "hdfs")
        os.makedirs(self.root, exist_ok=True)

    def _p(self, path):
        return os.path.join(self.root, path.lstrip("/"))

    def write(self, path, data):
        p = self._p(path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode())

    def read(self, path):
        with open(self._p(path), "rb") as f:
            return f.read()

    def listdir(self, path):
        """Recursive listing of files: [{path, size, mtime}]."""
        out = []
        base = self._p(path)
        for d, _, files in os.walk(base):
            for fn in files:
                fp = os.path.join(d, fn)
                st = os.stat(fp)
                out.append({"path": "/" + os.path.relpath(fp, self.root),
                            "size": st.st_size, "mtime": st.st_mtime})
        return out

    def exists(self, path):
        return os.path.exists(self._p(path))

    def usage(self, path):
        files = self.listdir(path)
        return {"files": len(files), "bytes": sum(f["size"] for f in files)}


class HdfsStorage:
    """Real HDFS through WebHDFS (the NameNode redirects writes to a DataNode)."""
    mode = "hdfs (WebHDFS)"

    def __init__(self):
        from hdfs import InsecureClient
        self.client = InsecureClient(settings.WEBHDFS_URL, user=settings.HDFS_USER, timeout=30)

    def write(self, path, data):
        self.client.write(path, data=data, overwrite=True)

    def read(self, path):
        with self.client.read(path) as r:
            return r.read()

    def listdir(self, path):
        out = []
        try:
            for (dirpath, _), _, files in self.client.walk(path, status=True):
                for name, st in files:
                    out.append({"path": dirpath.rstrip("/") + "/" + name,
                                "size": st["length"], "mtime": st["modificationTime"] / 1000})
        except Exception:
            pass  # path does not exist yet
        return out

    def exists(self, path):
        return self.client.status(path, strict=False) is not None

    def usage(self, path):
        files = self.listdir(path)
        return {"files": len(files), "bytes": sum(f["size"] for f in files)}


def get_storage():
    if settings.STORAGE == "hdfs":
        return HdfsStorage()
    return LocalStorage()


def wait_for_storage(retries=60, delay=3):
    """Block until the NameNode answers (used by services at container start-up)."""
    last = None
    for _ in range(retries):
        try:
            s = get_storage()
            if settings.STORAGE == "hdfs":
                # a probe write only succeeds once a DataNode has registered
                s.write(settings.HDFS_BASE + "/.probe", b"ok")
            return s
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[storage] waiting for HDFS... ({e.__class__.__name__})", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"HDFS unavailable: {last}")
