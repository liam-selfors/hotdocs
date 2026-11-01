import json
import os
import tempfile
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


STALE_GATE_VERSION = "secret_scanner@1.0.0"
FRESH_GATE_VERSION = "secret_scanner@2.0.0"

FAKE_CACHE_MANAGER_SOURCE = r'''
import json
import os

_STALE_GATE_VERSION = "secret_scanner@1.0.0"

_STALE_PAYLOAD = {
    "scope": "full",
    "gate_version": _STALE_GATE_VERSION,
    "flagged": True,
    "matches": [
        {"rule_id": "aws-access-key-id", "risk_tier": "high", "file": "gen/foo/config.py", "line": 1}
    ],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


def _log_path():
    return os.environ["SECRET_SCANNER_TEST_CACHE_LOG"]


def _record(event, cache_key, extra=None):
    entry = {"event": event, "gate_version": cache_key.gate_version}
    if extra is not None:
        entry["payload"] = extra
    with open(_log_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


class CacheKey:
    def __init__(self, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type, payload, stored_at):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    _record("get", cache_key)
    if cache_key.gate_version == _STALE_GATE_VERSION:
        return CachedResult(
            gate_type="secret_scanner",
            payload=dict(_STALE_PAYLOAD),
            stored_at="2020-01-01T00:00:00Z",
        )
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _record("put", cache_key, extra=dict(result.payload))
'''


def test_stale_cache_entry_under_old_gate_version_is_not_reused():
    env_keys = [
        "VAR_SECRET_PATTERNS_PATH",
        "SECRET_SCANNER_TEST_CACHE_LOG",
        "VAR_COMPLIANCE_WEBHOOK_URL",
    ]
    saved_env = {key: os.environ.get(key) for key in env_keys}

    try:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "specs").mkdir(parents=True, exist_ok=True)
            (repo_root / "verification").mkdir(parents=True, exist_ok=True)
            cache_manager_dir = repo_root / "gen" / "cache-manager"
            cache_manager_dir.mkdir(parents=True, exist_ok=True)

            (repo_root / "specs" / "placeholder.txt").write_text(
                "no secrets here\n", encoding="utf-8"
            )
            (repo_root / "verification" / "placeholder.txt").write_text(
                "no secrets here either\n", encoding="utf-8"
            )
            (cache_manager_dir / "cache_manager.py").write_text(
                FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8"
            )

            patterns_path = repo_root / "patterns-db.json"
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
                ),
                encoding="utf-8",
            )

            log_path = repo_root / "cache-invocations.jsonl"
            log_path.write_text("", encoding="utf-8")

            os.environ["VAR_SECRET_PATTERNS_PATH"] = str(patterns_path)
            os.environ["SECRET_SCANNER_TEST_CACHE_LOG"] = str(log_path)
            os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)

            import secret_scanner

            computed_gate_version = secret_scanner.gate_version(repo_root)
            assert computed_gate_version == FRESH_GATE_VERSION

            result = secret_scanner.scan(repo_root)

            assert _get(result, "gate_version") == FRESH_GATE_VERSION
            assert _get(result, "cache_hit") is False
            assert _get(result, "flagged") is False
            matches = _get(result, "matches")
            assert len(matches) == 0

            log_lines = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            get_events = [e for e in log_lines if e["event"] == "get"]
            put_events = [e for e in log_lines if e["event"] == "put"]

            assert len(get_events) >= 1
            assert all(e["gate_version"] != STALE_GATE_VERSION for e in get_events)
            assert any(e["gate_version"] == FRESH_GATE_VERSION for e in get_events)

            fresh_put_events = [
                e for e in put_events if e["gate_version"] == FRESH_GATE_VERSION
            ]
            assert len(fresh_put_events) >= 1
            fresh_payload = fresh_put_events[-1]["payload"]
            assert fresh_payload["gate_version"] == FRESH_GATE_VERSION
            assert fresh_payload["flagged"] is False
            assert fresh_payload["matches"] == []

            assert all(
                e["gate_version"] != STALE_GATE_VERSION for e in put_events
            )

    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value