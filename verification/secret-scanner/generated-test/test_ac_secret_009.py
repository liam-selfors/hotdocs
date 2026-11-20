# hotdocs-criterion: sha256:a0048dbb0ff9da9eb1ebc54d510c45b9e9ab8bc6fa306d7387c757c81f1a3ecd
import json
import sys
import urllib.request
from pathlib import Path

import secret_scanner


STORE_ENV = "FAKE_CACHE_MANAGER_STORE"
LOG_ENV = "FAKE_CACHE_MANAGER_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_cache_manager_source():
    lines = [
        "import dataclasses",
        "import datetime",
        "import json",
        "import os",
        "from pathlib import Path",
        "",
        "STORE_ENV = " + repr(STORE_ENV),
        "LOG_ENV = " + repr(LOG_ENV),
        "",
        "REQUIRED = " + repr({
            "generator": ["component_id", "model", "prompt_version", "files"],
            "compiler": ["outputs", "gate_version", "summary"],
            "generated_test": ["component_id", "criterion_id", "model", "file"],
            "llm_judge": ["result", "rationale"],
            "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
            "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
        }),
        "",
        "",
        "class SchemaValidationError(ValueError):",
        "    pass",
        "",
        "",
        "@dataclasses.dataclass",
        "class CacheKey:",
        "    spec_bundle_hash: object = None",
        "    gate_inputs_hash: object = None",
        "    gate_version: object = None",
        "    model_pin: object = None",
        "",
        "",
        "@dataclasses.dataclass",
        "class CachedResult:",
        "    gate_type: object = None",
        "    payload: object = None",
        "    stored_at: object = None",
        "",
        "",
        "class Miss:",
        "    def __eq__(self, other):",
        "        return isinstance(other, Miss)",
        "",
        "    def __hash__(self):",
        "        return 0",
        "",
        "",
        "def _attr(value, name):",
        "    return value[name] if isinstance(value, dict) else getattr(value, name)",
        "",
        "",
        "def _key_text(cache_key):",
        "    data = dict()",
        "    for name in ('spec_bundle_hash', 'gate_inputs_hash', 'gate_version', 'model_pin'):",
        "        data[name] = _attr(cache_key, name)",
        "    return json.dumps(data, sort_keys=True, default=str)",
        "",
        "",
        "def _load():",
        "    path = Path(os.environ[STORE_ENV])",
        "    if not path.is_file():",
        "        return dict()",
        "    return json.loads(path.read_text())",
        "",
        "",
        "def _save(store):",
        "    Path(os.environ[STORE_ENV]).write_text(json.dumps(store, sort_keys=True))",
        "",
        "",
        "def _log(entry):",
        "    with open(os.environ[LOG_ENV], 'a') as handle:",
        "        handle.write(json.dumps(entry, sort_keys=True, default=str) + chr(10))",
        "",
        "",
        "def now_iso():",
        "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')",
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    text = _key_text(cache_key)",
        "    _log({'op': 'get', 'key': text})",
        "    store = _load()",
        "    if text not in store:",
        "        return Miss()",
        "    entry = store[text]",
        "    return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'], stored_at=entry['stored_at'])",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    gate_version = str(_attr(cache_key, 'gate_version'))",
        "    gate_type = _attr(result, 'gate_type')",
        "    if gate_version.split('@')[0] != gate_type or gate_type not in REQUIRED:",
        "        raise SchemaValidationError('gate type mismatch')",
        "    payload = _attr(result, 'payload')",
        "    if hasattr(payload, 'to_dict'):",
        "        payload = payload.to_dict()",
        "    payload = json.loads(json.dumps(payload, default=str))",
        "    if not isinstance(payload, dict):",
        "        raise SchemaValidationError('payload is not a mapping')",
        "    for name in REQUIRED[gate_type]:",
        "        if name not in payload:",
        "            raise SchemaValidationError('missing key ' + name)",
        "    text = _key_text(cache_key)",
        "    store = _load()",
        "    store[text] = {'gate_type': gate_type, 'payload': payload, 'stored_at': _attr(result, 'stored_at')}",
        "    _save(store)",
        "    _log({'op': 'put', 'key': text, 'flagged': payload.get('flagged')})",
        "",
        "",
        "def stats(*, repo_root=None):",
        "    return {'entry_count': len(_load())}",
        "",
    ]
    return "\n".join(lines)


def _read_log(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_ac_secret_009_flagged_result_survives_clean_rescan(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    repo_root = tmp_path / "repo"
    state = tmp_path / "state"
    repo_root.mkdir()
    state.mkdir()

    store_path = state / "store.json"
    log_path = state / "calls.log"
    monkeypatch.setenv(STORE_ENV, str(store_path))
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def fake_urlopen(*args, **kwargs):
        raise AssertionError("webhook must not be called without a configured URL")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(_fake_cache_manager_source())

    target = repo_root / "gen" / "foo" / "c.py"
    target.parent.mkdir(parents=True)
    target.write_text("K = " + repr("AKIAABCDEFGHIJKLMNOP") + "\n")

    first = secret_scanner.scan(repo_root)

    target.write_text("K = " + repr("") + "\n")

    second = secret_scanner.scan(repo_root)

    assert field(first, "flagged") is True
    assert field(second, "flagged") is False
    assert field(first, "cache_hit") is False
    assert field(second, "cache_hit") is False

    puts = [entry for entry in _read_log(log_path) if entry["op"] == "put"]
    assert len(puts) == 2, puts
    first_key = puts[0]["key"]
    second_key = puts[1]["key"]
    assert first_key != second_key
    assert puts[0]["flagged"] is True
    assert puts[1]["flagged"] is False

    store = json.loads(store_path.read_text())
    assert first_key in store
    assert second_key in store
    flagged_entry = store[first_key]
    assert flagged_entry["gate_type"] == "secret_scanner"
    assert field(flagged_entry["payload"], "flagged") is True
    assert len(field(flagged_entry["payload"], "matches")) >= 1
    assert field(store[second_key]["payload"], "flagged") is False