import json

import pytest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_CACHE_MANAGER_SOURCE = '''
import json
import os


class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,
                 gate_version=None, model_pin=None):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


class Miss:
    payload = None


def _log_path():
    return os.environ.get("SECRET_SCANNER_AC003_CALL_LOG")


def get(cache_key, repo_root=None):
    return Miss()


def put(cache_key, cached_result, repo_root=None):
    log_path = _log_path()
    if not log_path:
        return
    record = {
        "gate_type": getattr(cached_result, "gate_type", None),
        "payload": getattr(cached_result, "payload", None),
    }
    with open(log_path, "a") as handle:
        handle.write(json.dumps(record) + "\\n")
'''


def test_clean_full_scan_still_records_result(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(_CACHE_MANAGER_SOURCE)

    (repo_root / ".secret-allowlist.json").write_text(
        json.dumps({"version": 1, "entries": []})
    )

    src_dir = repo_root / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text(
        "def add(left, right):\n    return left + right\n"
    )

    call_log = tmp_path / "cache_manager_calls.jsonl"
    monkeypatch.setenv("SECRET_SCANNER_AC003_CALL_LOG", str(call_log))

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is False
    matches = _get(result, "matches")
    assert matches == []

    as_dict = result.to_dict()

    for required_key in (
        "scope",
        "gate_version",
        "flagged",
        "matches",
        "allowed",
        "unused_allowlist_entries",
        "notified",
        "notification_delivery_error",
        "cache_hit",
    ):
        assert required_key in as_dict, (
            "a clean SecretScanResult must still carry every field of the "
            "record, not just an absence of flags"
        )

    assert as_dict["scope"] == "full"
    assert as_dict["flagged"] is False
    assert as_dict["matches"] == []
    assert as_dict["gate_version"]
    assert as_dict["notified"] is False

    assert call_log.exists(), (
        "secret_scanner.scan did not forward the clean result onward via "
        "cache-manager's put -- a clean outcome must still be recorded, "
        "never silently dropped"
    )
    lines = [line for line in call_log.read_text().splitlines() if line.strip()]
    assert len(lines) == 1, (
        "expected exactly one put() call recording the fresh, clean scan "
        "result"
    )

    record = json.loads(lines[0])
    assert record["gate_type"] == "secret_scanner"

    payload = record["payload"]
    for required_payload_key in ("scope", "gate_version", "flagged", "matches"):
        assert required_payload_key in payload, (
            "the recorded payload for a clean outcome must still satisfy "
            "the secret_scanner CachedResult payload schema"
        )
    assert payload["flagged"] is False
    assert payload["matches"] == []