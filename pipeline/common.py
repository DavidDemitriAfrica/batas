"""Shared paths, polite HTTP fetching, and the provenance log.

Every downloaded file is recorded in data/provenance.jsonl with its source
URL, checksum, size, and retrieval time, following the convention of the
philippines-internal-migration and street-rank repos.
"""

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
CLEAN = DATA / "clean"
DOCS = ROOT / "docs"
FIGURES = ROOT / "figures"
PROVENANCE = DATA / "provenance.jsonl"

USER_AGENT = "batas/0.1 (research; github.com/DavidDemitriAfrica/batas)"

_LOG_LOCK = threading.Lock()
_SESSION = threading.local()


def log_provenance(record):
    record = dict(record)
    record["retrieved_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _LOG_LOCK:
        PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
        with open(PROVENANCE, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _session():
    s = getattr(_SESSION, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        _SESSION.s = s
    return s


def fetch(url, dest, note="", min_bytes=200, tries=4, pause=0.4, log=True):
    """Download url to dest unless a cached copy exists. Returns the bytes."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size >= min_bytes:
        return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(tries):
        try:
            r = _session().get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            body = r.content
            dest.write_bytes(body)
            if log:
                log_provenance({
                    "file": str(dest.relative_to(ROOT)),
                    "source_url": url,
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "bytes": len(body),
                    "note": note,
                })
            time.sleep(pause)
            return body
        except requests.RequestException as e:  # retry with backoff
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to fetch {url}: {last}")


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1))


def read_json(path):
    return json.loads(Path(path).read_text())
