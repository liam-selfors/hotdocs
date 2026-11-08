import json

import license_scanner


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _fake_cache_manager_source(log_path):
    return f'''
import dataclasses
import json


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    pass


_LOG_PATH = {str(log_path)!r}


def _append_log(record):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\\n")


def get(cache_key, *, repo_root=None):
    _append_log({{"op": "get", "gate_version": cache_key.gate_version}})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _append_log({{"op": "put", "gate_type": result.gate_type, "payload": result.payload}})
'''


def _setup_repo(base_dir, log_path):
    repo_root = base_dir / "repo"
    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(
        _fake_cache_manager_source(log_path)
    )
    return repo_root


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_exactly_one_license_scan_result_per_component(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    log_path = tmp_path / "cache_calls.jsonl"
    repo_root = _setup_repo(tmp_path, log_path)

    result = license_scanner.scan("comp-foo", repo_root)

    assert result is not None
    assert not isinstance(result, (list, tuple, set, frozenset))

    assert _field(result, "component_id") == "comp-foo"
    assert _field(result, "evaluated") is False
    assert _field(result, "reason") == "no-reference-corpus"
    assert _field(result, "gate_version") == "license_scanner@4.0.0-no-reference-corpus"
    assert _field(result, "similarity_score") is None
    assert _field(result, "block_threshold") is None
    assert _field(result, "matches") == []
    assert _field(result, "blocked") is False
    assert _field(result, "notified") is False
    assert _field(result, "notification_delivery_error") is None
    assert _field(result, "cache_hit") is False

    records = _read_log(log_path)
    put_records = [r for r in records if r["op"] == "put"]
    assert len(put_records) == 1

    put_record = put_records[0]
    assert put_record["gate_type"] == "license_scanner"
    assert _field(put_record["payload"], "component_id") == "comp-foo"

    log_path2 = tmp_path / "cache_calls_2.jsonl"
    repo_root2 = _setup_repo(tmp_path / "second", log_path2)

    result2 = license_scanner.scan("comp-bar", repo_root2)

    assert result2 is not None
    assert not isinstance(result2, (list, tuple, set, frozenset))
    assert _field(result2, "component_id") == "comp-bar"

    records2 = _read_log(log_path2)
    put_records2 = [r for r in records2 if r["op"] == "put"]
    assert len(put_records2) == 1
    assert _field(put_records2[0]["payload"], "component_id") == "comp-bar"