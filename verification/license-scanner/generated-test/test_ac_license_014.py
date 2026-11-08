import hashlib
import json
from pathlib import Path

import pytest

import license_scanner


# A fake cache-manager that matches lookups by gate_version alone: the test
# cannot predict the spec_bundle_hash/gate_inputs_hash/model_pin the real
# license-scanner builds, but gate_version is exactly what R-LICENSE-005 is
# about, so that is the only field this stand-in needs to key on.
CACHE_MANAGER_SOURCE = r'''
import json
from pathlib import Path


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


_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent
_LOG_PATH = _REPO_ROOT / "cache_calls.jsonl"
_SEED_PATH = _REPO_ROOT / "cache_seed.json"


def _log(action, gate_version):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps({"action": action, "gate_version": gate_version}) + "\n")


def _load_store():
    store = {}
    if _SEED_PATH.exists():
        with open(_SEED_PATH) as f:
            raw = json.load(f)
        for gv, entry in raw.items():
            store[gv] = CachedResult(
                gate_type=entry["gate_type"],
                payload=entry["payload"],
                stored_at=entry["stored_at"],
            )
    return store


_STORE = _load_store()


def get(cache_key, *, repo_root=None):
    _log("get", cache_key.gate_version)
    gv = cache_key.gate_version
    if gv in _STORE:
        return _STORE[gv]
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _log("put", cache_key.gate_version)
    _STORE[cache_key.gate_version] = result
'''


def _install_fake_cache_manager(repo_root):
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(CACHE_MANAGER_SOURCE, encoding="utf-8")


def _seed_cache(repo_root, seed):
    seed_path = repo_root / "cache_seed.json"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")


def _read_log(repo_root):
    log_path = repo_root / "cache_calls.jsonl"
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _write_foo_component(repo_root):
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True, exist_ok=True)
    (foo_dir / "foo.py").write_text(
        "def greet(name):\n"
        "    message = 'hello ' + name\n"
        "    return message\n"
        "\n"
        "def farewell(name):\n"
        "    message = 'bye ' + name\n"
        "    return message\n",
        encoding="utf-8",
    )


def _write_corpus(repo_root, filename, corpus_version, entries):
    corpus_obj = {
        "corpus_version": corpus_version,
        "block_threshold": 0.7,
        "entries": entries,
    }
    corpus_path = repo_root / filename
    corpus_bytes = json.dumps(corpus_obj, indent=2).encode("utf-8")
    corpus_path.write_bytes(corpus_bytes)
    return corpus_path, corpus_bytes


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def test_corpus_becomes_available_fresh_result_not_cached_value(tmp_path, monkeypatch):
    repo_root = tmp_path
    _install_fake_cache_manager(repo_root)
    _write_foo_component(repo_root)

    entries = [
        {
            "reference_id": "ref-aaa",
            "license_family": "MIT",
            "risk_tier": "low",
            "hashes": ["0" * 64],
        }
    ]
    corpus_path, corpus_bytes = _write_corpus(repo_root, "corpus.json", 0, entries)
    corpus_hash = hashlib.sha256(corpus_bytes).hexdigest()[:12]
    expected_gate_version = "license_scanner@4.0.0+" + corpus_hash

    stale_payload = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }
    _seed_cache(
        repo_root,
        {
            "license_scanner@4.0.0-no-reference-corpus": {
                "gate_type": "license_scanner",
                "payload": stale_payload,
                "stored_at": "2026-01-01T00:00:00Z",
            }
        },
    )

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    evaluated = _field(result, "evaluated")
    gate_version = _field(result, "gate_version")
    cache_hit = _field(result, "cache_hit")

    assert evaluated is True
    assert gate_version == expected_gate_version
    assert cache_hit is False

    calls = _read_log(repo_root)
    get_calls = [c for c in calls if c["action"] == "get"]
    put_calls = [c for c in calls if c["action"] == "put"]
    assert any(c["gate_version"] == expected_gate_version for c in get_calls)
    assert any(c["gate_version"] == expected_gate_version for c in put_calls)


def test_variable_unset_after_evaluated_cache_entry_not_reused(tmp_path, monkeypatch):
    repo_root = tmp_path
    _install_fake_cache_manager(repo_root)
    _write_foo_component(repo_root)

    entries = [
        {
            "reference_id": "ref-bbb",
            "license_family": "Apache-2.0",
            "risk_tier": "medium",
            "hashes": ["1" * 64],
        }
    ]
    corpus_path, corpus_bytes = _write_corpus(repo_root, "corpus2.json", 0, entries)
    corpus_hash = hashlib.sha256(corpus_bytes).hexdigest()[:12]
    evaluated_gate_version = "license_scanner@4.0.0+" + corpus_hash

    evaluated_payload = {
        "component_id": "comp-foo",
        "gate_version": evaluated_gate_version,
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }
    _seed_cache(
        repo_root,
        {
            evaluated_gate_version: {
                "gate_type": "license_scanner",
                "payload": evaluated_payload,
                "stored_at": "2026-01-01T00:00:00Z",
            }
        },
    )

    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    result = license_scanner.scan("comp-foo", repo_root)

    evaluated = _field(result, "evaluated")
    reason = _field(result, "reason")
    gate_version = _field(result, "gate_version")
    cache_hit = _field(result, "cache_hit")

    assert evaluated is False
    assert reason == "no-reference-corpus"
    assert gate_version == "license_scanner@4.0.0-no-reference-corpus"
    assert cache_hit is False

    calls = _read_log(repo_root)
    get_calls = [c for c in calls if c["action"] == "get"]
    assert any(
        c["gate_version"] == "license_scanner@4.0.0-no-reference-corpus"
        for c in get_calls
    )


def test_corpus_content_change_without_version_bump_not_reused(tmp_path, monkeypatch):
    repo_root = tmp_path
    _install_fake_cache_manager(repo_root)
    _write_foo_component(repo_root)

    initial_entries = [
        {
            "reference_id": "ref-ccc",
            "license_family": "BSD-3-Clause",
            "risk_tier": "low",
            "hashes": ["2" * 64],
        }
    ]
    corpus_path, corpus_bytes = _write_corpus(
        repo_root, "corpus3.json", 2, initial_entries
    )
    initial_hash = hashlib.sha256(corpus_bytes).hexdigest()[:12]
    initial_gate_version = "license_scanner@4.0.2+" + initial_hash

    evaluated_payload = {
        "component_id": "comp-foo",
        "gate_version": initial_gate_version,
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }
    _seed_cache(
        repo_root,
        {
            initial_gate_version: {
                "gate_type": "license_scanner",
                "payload": evaluated_payload,
                "stored_at": "2026-01-01T00:00:00Z",
            }
        },
    )

    updated_entries = initial_entries + [
        {
            "reference_id": "ref-ddd",
            "license_family": "BSD-3-Clause",
            "risk_tier": "low",
            "hashes": ["3" * 64],
        }
    ]
    corpus_path, corpus_bytes = _write_corpus(
        repo_root, "corpus3.json", 2, updated_entries
    )
    updated_hash = hashlib.sha256(corpus_bytes).hexdigest()[:12]
    updated_gate_version = "license_scanner@4.0.2+" + updated_hash
    assert updated_gate_version != initial_gate_version

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    gate_version = _field(result, "gate_version")
    cache_hit = _field(result, "cache_hit")

    assert gate_version == updated_gate_version
    assert cache_hit is False

    calls = _read_log(repo_root)
    get_calls = [c for c in calls if c["action"] == "get"]
    assert any(c["gate_version"] == updated_gate_version for c in get_calls)