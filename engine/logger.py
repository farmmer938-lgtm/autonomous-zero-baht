import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "data" / "logs"


def _log_path():
    override = os.environ.get("AF_LOG_PATH")
    if override:
        return Path(override)
    # The log file is tracked, so a test run must not append to it.
    if "unittest" in sys.modules:
        return Path(tempfile.gettempdir()) / "af-test-logs" / "run.jsonl"
    return LOG_DIR / "run.jsonl"


def log_event(event, **fields):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=True), flush=True)
