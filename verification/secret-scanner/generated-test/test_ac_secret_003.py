import json
import os
import shutil
import tempfile
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FAKE_CACHE_MANAGER_SOURCE = r'''
import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str


def get(cache_key, *, repo_root=None):
    # Always a miss: this test exercises a clean, uncached full scan.
    return None


def put(cache_key, result, *, repo_root=None):
    log_path = os.environ.get("FAKE_CACHE_LOG_PATH")
    if not log_path:
        return

    def _field(obj, name):
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    record = {
        "gate_type": _field(result, "gate_type"),
        "payload": _field(result, "payload"),
        "stored_at": _field(result, "stored_at"),
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")
'''


def test_clean_full_scan_still_records_result_in_cache_write():
    repo_root = Path(tempfile.mkdtemp(prefix="secret_scan_ac003_"))
    log_fd, log_path = tempfile.mkstemp(prefix="cache_put_log_")
    os.close(log_fd)

    patterns_path = repo_root / "patterns.json"

    env_names = ["VAR_SECRET_PATTERNS_PATH", "FAKE_CACHE_LOG_PATH", "VAR_COMPLIANCE_WEBHOOK_URL"]
    saved_env = {name: os.environ.get(name) for name in env_names}

    try:
        os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)
        os.environ["VAR_SECRET_PATTERNS_PATH"] = str(patterns_path)
        os.environ["FAKE_CACHE_LOG_PATH"] = str(log_path)

        (repo_root / "specs").mkdir(parents=True)
        (repo_root / "gen" / "cache-manager").mkdir(parents=True)
        (repo_root / "verification").mkdir(parents=True)

        (repo_root / "specs" / "note.txt").write_text(
            "This is an ordinary specification note with no embedded secrets.\n"
        )
        (repo_root / "verification" / "note.txt").write_text(
            "This is an ordinary verification note with no embedded secrets.\n"
        )
        (repo_root / "gen" / "cache-manager" / "cache_manager.py").write_text(
            FAKE_CACHE_MANAGER_SOURCE
        )

        patterns_path.write_text(
            json.dumps(
                {
                    "version": "2.0.0",
                    "rules": [
                        {
                            "rule_id": "aws-access-key-id",
                            "risk_tier": "high",
                            "pattern": "AKIA[0-9A-Z]{16}",
                        }
                    ],
                }
            )
        )

        result = secret_scanner.scan(repo_root)

        assert result is not None

        scope = _get(result, "scope")
        gate_version = _get(result, "gate_version")
        flagged = _get(result, "flagged")
        matches = _get(result, "matches")
        notified = _get(result, "notified")
        notification_delivery_error = _get(result, "notification_delivery_error")
        cache_hit = _get(result, "cache_hit")

        assert scope == "full"
        assert gate_version == "secret_scanner@2.0.0"
        assert flagged is False
        assert matches == []
        assert notified is False
        assert notification_delivery_error is None
        assert cache_hit is False

        assert os.path.exists(log_path)
        with open(log_path) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        assert len(lines) >= 1, (
            "a clean scan result MUST still be written -- "
            "absence of a flag MUST NOT mean absence of a record"
        )

        put_record = lines[-1]
        assert put_record["gate_type"] == "secret_scanner"

        payload = put_record["payload"]
        assert _get(payload, "scope") == "full"
        assert _get(payload, "gate_version") == "secret_scanner@2.0.0"
        assert _get(payload, "flagged") is False
        assert _get(payload, "matches") == []

        assert put_record["stored_at"]

    finally:
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(repo_root, ignore_errors=True)
        if os.path.exists(log_path):
            os.remove(log_path)