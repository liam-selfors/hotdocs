import json
import re

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_CACHE_MANAGER_TEMPLATE = '''
import dataclasses
import json
import os


STORE_PATH = __STORE_PATH__
LOG_PATH = __LOG_PATH__


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


class Miss:
    pass


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _key_str(cache_key):
    return "|".join([
        str(_field(cache_key, "spec_bundle_hash")),
        str(_field(cache_key, "gate_inputs_hash")),
        str(_field(cache_key, "gate_version")),
        str(_field(cache_key, "model_pin")),
    ])


def _load_store():
    if os.path.exists(STORE_PATH):
        with open(STORE_PATH, "r") as f:
            return json.load(f)
    return {}


def _save_store(store):
    with open(STORE_PATH, "w") as f:
        json.dump(store, f)


def _log(event, cache_key, hit):
    record = {
        "event": event,
        "gate_version": _field(cache_key, "gate_version"),
        "hit": hit,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + chr(10))


def get(cache_key, *, repo_root=None):
    store = _load_store()
    key = _key_str(cache_key)
    entry = store.get(key)
    if entry is None:
        _log("get", cache_key, False)
        return {"gate_type": None, "payload": None, "stored_at": None}
    _log("get", cache_key, True)
    return CachedResult(
        gate_type=entry["gate_type"],
        payload=entry["payload"],
        stored_at=entry["stored_at"],
    )


def put(cache_key, result, *, repo_root=None):
    store = _load_store()
    key = _key_str(cache_key)
    store[key] = {
        "gate_type": _field(result, "gate_type"),
        "payload": _field(result, "payload"),
        "stored_at": _field(result, "stored_at"),
    }
    _save_store(store)
    _log("put", cache_key, None)
'''


def _write_fake_cache_manager(repo_root, store_path, log_path):
    module_dir = repo_root / "gen" / "cache-manager"
    module_dir.mkdir(parents=True, exist_ok=True)
    module_path = module_dir / "cache_manager.py"
    source = _CACHE_MANAGER_TEMPLATE.replace(
        "__STORE_PATH__", json.dumps(str(store_path))
    ).replace(
        "__LOG_PATH__", json.dumps(str(log_path))
    )
    module_path.write_text(source)


def _write_corpus(corpus_path, corpus_version):
    data = {
        "corpus_version": corpus_version,
        "block_threshold": 0.7,
        "entries": [
            {
                "reference_id": "ref-1",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": ["a" * 64],
            }
        ],
    }
    corpus_path.write_text(json.dumps(data))


def _read_log(log_path):
    if not log_path.exists():
        return []
    text = log_path.read_text().strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


_GATE_VERSION_RE = re.compile(r"^license_scanner@4\.0\.(\d+)\+([0-9a-f]{12})$")


def test_corpus_update_invalidates_stale_cached_result(tmp_path, monkeypatch):
    component_dir = tmp_path / "gen" / "foo"
    component_dir.mkdir(parents=True)
    (component_dir / "foo.py").write_text("def add(a, b):\n    return a + b\n")

    store_path = tmp_path / "cache_store.json"
    log_path = tmp_path / "cache_calls.log"
    _write_fake_cache_manager(tmp_path, store_path, log_path)

    corpus_path = tmp_path / "corpus.json"
    _write_corpus(corpus_path, corpus_version=1)

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    # Gherkin's "@1.0.0"/"@2.0.0" are illustrative; R-LICENSE-005's real format is license_scanner@4.0.<V>+<H>.
    result1 = license_scanner.scan("comp-foo", tmp_path)
    assert _get(result1, "evaluated") is True
    assert _get(result1, "cache_hit") is False

    gate_version1 = _get(result1, "gate_version")
    match1 = _GATE_VERSION_RE.match(gate_version1)
    assert match1 is not None
    assert match1.group(1) == "1"

    log_before = _read_log(log_path)
    assert any(
        e["event"] == "put" and e["gate_version"] == gate_version1
        for e in log_before
    )

    _write_corpus(corpus_path, corpus_version=2)

    result2 = license_scanner.scan("comp-foo", tmp_path)
    assert _get(result2, "evaluated") is True
    assert _get(result2, "cache_hit") is False

    gate_version2 = _get(result2, "gate_version")
    match2 = _GATE_VERSION_RE.match(gate_version2)
    assert match2 is not None
    assert match2.group(1) == "2"
    assert gate_version2 != gate_version1

    log_after = _read_log(log_path)
    new_events = log_after[len(log_before):]

    assert any(
        e["event"] == "get" and e["gate_version"] == gate_version2 and e["hit"] is False
        for e in new_events
    )
    assert not any(e["event"] == "get" and e["hit"] is True for e in new_events)
    assert any(
        e["event"] == "put" and e["gate_version"] == gate_version2
        for e in new_events
    )

    result3 = license_scanner.scan("comp-foo", tmp_path)
    assert _get(result3, "gate_version") == gate_version2
    assert _get(result3, "cache_hit") is True