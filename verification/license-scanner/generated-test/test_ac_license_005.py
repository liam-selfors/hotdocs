# hotdocs-criterion: sha256:6f8e3fa988b5ccc7be7ad1833d159af834ba02f7415bb4c4e9054ad442b1589c
import hashlib
import json
import os
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_TEMPLATE_HEAD = (
    "import dataclasses\n"
    "import json\n"
    "import os\n"
    "from dataclasses import dataclass\n"
    "\n"
)

FAKE_CACHE_TEMPLATE_BODY = (
    "\n"
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "def _key_str(cache_key):\n"
    "    return json.dumps([cache_key.spec_bundle_hash, cache_key.gate_inputs_hash,\n"
    "                       cache_key.gate_version, cache_key.model_pin])\n"
    "\n"
    "\n"
    "def _load():\n"
    "    if os.path.exists(STORE_PATH):\n"
    "        with open(STORE_PATH, 'r', encoding='utf-8') as fh:\n"
    "            return json.load(fh)\n"
    "    return {}\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log('get\\t' + str(cache_key.gate_version))\n"
    "    store = _load()\n"
    "    entry = store.get(_key_str(cache_key))\n"
    "    if entry is None:\n"
    "        return Miss()\n"
    "    return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'],\n"
    "                        stored_at=entry['stored_at'])\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    _log('put\\t' + str(cache_key.gate_version))\n"
    "    gate_type = str(cache_key.gate_version).split('@', 1)[0]\n"
    "    if result.gate_type != gate_type:\n"
    "        raise SchemaValidationError('gate_type mismatch')\n"
    "    payload = result.payload if isinstance(result.payload, dict) else {}\n"
    "    for k in ('component_id', 'gate_version', 'similarity_score', 'blocked', 'matches'):\n"
    "        if k not in payload:\n"
    "            raise SchemaValidationError('missing ' + k)\n"
    "    store = _load()\n"
    "    store[_key_str(cache_key)] = {\n"
    "        'gate_type': result.gate_type,\n"
    "        'payload': json.loads(json.dumps(payload, default=str)),\n"
    "        'stored_at': result.stored_at,\n"
    "    }\n"
    "    with open(STORE_PATH, 'w', encoding='utf-8') as fh:\n"
    "        json.dump(store, fh)\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    raise AssertionError('now_iso must not be used')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': len(_load())}\n"
)


def _write_fake_cache_manager(repo_root, log_path, store_path):
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        FAKE_CACHE_TEMPLATE_HEAD
        + "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "STORE_PATH = " + repr(str(store_path)) + "\n"
        + FAKE_CACHE_TEMPLATE_BODY
    )
    (d / "cache_manager.py").write_text(src, encoding="utf-8")


def _write_component_source(repo_root):
    d = repo_root / "gen" / "foo"
    d.mkdir(parents=True, exist_ok=True)
    (d / "foo.py").write_text(
        "def compute_total(items, factor, offset):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total = total + item * factor + offset\n"
        "    return total\n"
        "\n"
        "\n"
        "def describe(name, value):\n"
        "    return name + ' is ' + str(value)\n",
        encoding="utf-8",
    )


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [ln.split("\t", 1) for ln in log_path.read_text(encoding="utf-8").splitlines() if ln]


def test_ac_license_005_corpus_update_invalidates_cached_result(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    store_path = tmp_path / "cache_store.json"
    _write_fake_cache_manager(repo_root, log_path, store_path)
    _write_component_source(repo_root)

    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    corpus_path = repo_root / "corpus.json"
    corpus_v1 = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {"reference_id": "ref-001", "license_family": "GPL", "risk_tier": "low",
             "hashes": ["0" * 64]},
        ],
    }
    corpus_path.write_text(json.dumps(corpus_v1), encoding="utf-8")
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    v1_bytes = corpus_path.read_bytes()
    old_version = "license_scanner@4.0.1+" + hashlib.sha256(v1_bytes).hexdigest()[:12]
    assert license_scanner.gate_version(repo_root) == old_version

    first = license_scanner.scan("comp-foo", repo_root)
    assert field(first, "gate_version") == old_version
    assert field(first, "evaluated") is True

    calls = _read_log(log_path)
    assert ["put", old_version] in calls, calls
    assert store_path.exists()

    # Mark the cached (now old-version) entries with a stale sentinel payload.
    store = json.loads(store_path.read_text(encoding="utf-8"))
    assert store, "a cached result under the old gate_version must exist"
    sentinel_score = 0.987654
    for entry in store.values():
        entry["payload"]["similarity_score"] = sentinel_score
        entry["payload"]["matches"] = [
            {"reference_id": "stale-ref", "license_family": "stale",
             "risk_tier": "low", "score": sentinel_score}
        ]
    store_path.write_text(json.dumps(store), encoding="utf-8")

    # Update the reference corpus to a new version.
    corpus_v2 = {
        "corpus_version": 2,
        "block_threshold": 0.70,
        "entries": [
            {"reference_id": "ref-001", "license_family": "GPL", "risk_tier": "low",
             "hashes": ["0" * 64]},
            {"reference_id": "ref-002", "license_family": "MIT", "risk_tier": "low",
             "hashes": ["1" * 64]},
        ],
    }
    corpus_path.write_text(json.dumps(corpus_v2), encoding="utf-8")
    v2_bytes = corpus_path.read_bytes()
    new_version = "license_scanner@4.0.2+" + hashlib.sha256(v2_bytes).hexdigest()[:12]
    assert new_version != old_version
    assert license_scanner.gate_version(repo_root) == new_version

    log_path.write_text("", encoding="utf-8")

    second = license_scanner.scan("comp-foo", repo_root)

    assert field(second, "gate_version") == new_version
    assert field(second, "cache_hit") is False
    assert field(second, "evaluated") is True
    assert field(second, "similarity_score") != sentinel_score
    for m in field(second, "matches"):
        assert field(m, "reference_id") != "stale-ref"

    calls = _read_log(log_path)
    gets = [c[1] for c in calls if c[0] == "get"]
    puts = [c[1] for c in calls if c[0] == "put"]
    assert gets, calls
    assert all(v == new_version for v in gets), calls
    assert old_version not in gets
    assert new_version in puts, "a fresh scan must store its result under the new gate_version"