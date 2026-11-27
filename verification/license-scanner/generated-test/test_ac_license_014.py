# hotdocs-criterion: sha256:1157eaf21b61b96052489179854a4d1abd551278268085da8cd48028a24ea06d
"""AC-LICENSE-014 (covers R-LICENSE-005).

gate_version distinguishes evaluated from not-evaluated results and changes
with any change to the corpus bytes, so a cached result is never reused
across such a change.
"""

import hashlib
import json
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


NO_CORPUS_GV = "license_scanner@4.0.0-no-reference-corpus"


FAKE_BODY_LINES = [
    "import dataclasses",
    "import json",
    "import os",
    "",
    "",
    "@dataclasses.dataclass",
    "class CacheKey:",
    "    spec_bundle_hash: str",
    "    gate_inputs_hash: str",
    "    gate_version: str",
    "    model_pin: str",
    "",
    "",
    "@dataclasses.dataclass",
    "class CachedResult:",
    "    gate_type: str",
    "    payload: dict",
    "    stored_at: str",
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
    "class SchemaValidationError(ValueError):",
    "    pass",
    "",
    "",
    "_REQUIRED = ['component_id', 'gate_version', 'similarity_score', 'blocked', 'matches']",
    "",
    "",
    "def _key_str(k):",
    "    return json.dumps([k.spec_bundle_hash, k.gate_inputs_hash, k.gate_version, k.model_pin], default=str)",
    "",
    "",
    "def _log(op, k):",
    "    with open(LOG, 'a') as f:",
    "        f.write(json.dumps({'op': op, 'gate_version': k.gate_version}, default=str) + '\\n')",
    "",
    "",
    "def _load():",
    "    if os.path.exists(STORE):",
    "        with open(STORE) as f:",
    "            return json.load(f)",
    "    return {}",
    "",
    "",
    "def get(cache_key, *, repo_root=None):",
    "    _log('get', cache_key)",
    "    entry = _load().get(_key_str(cache_key))",
    "    if entry is None:",
    "        return Miss()",
    "    return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'], stored_at=entry['stored_at'])",
    "",
    "",
    "def put(cache_key, result, *, repo_root=None):",
    "    if str(cache_key.gate_version).split('@')[0] != result.gate_type:",
    "        raise SchemaValidationError('gate_type mismatch')",
    "    payload = result.payload",
    "    if not isinstance(payload, dict) or any(k not in payload for k in _REQUIRED):",
    "        raise SchemaValidationError('missing payload keys')",
    "    _log('put', cache_key)",
    "    store = _load()",
    "    store[_key_str(cache_key)] = {",
    "        'gate_type': result.gate_type,",
    "        'payload': json.loads(json.dumps(payload, default=str)),",
    "        'stored_at': result.stored_at,",
    "    }",
    "    with open(STORE, 'w') as f:",
    "        json.dump(store, f)",
    "",
]


def make_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "foo.py").write_text(
        "def compute_total(values, factor):\n"
        "    total = 0\n"
        "    for value in values:\n"
        "        total = total + value * factor\n"
        "    return total\n"
        "\n"
        "def describe(name, count):\n"
        "    return name + ' has ' + str(count) + ' items'\n"
    )
    store = tmp_path / "store.json"
    log = tmp_path / "cache_log.jsonl"
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    source = (
        "STORE = " + repr(str(store)) + "\n"
        + "LOG = " + repr(str(log)) + "\n"
        + "\n".join(FAKE_BODY_LINES)
    )
    (cm_dir / "cache_manager.py").write_text(source)

    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)
    return repo_root, log


def read_log(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def write_corpus(path, corpus_version, entries):
    data = {"corpus_version": corpus_version, "block_threshold": 0.70, "entries": entries}
    raw = json.dumps(data, indent=2).encode("utf-8")
    path.write_bytes(raw)
    return "license_scanner@4.0." + str(corpus_version) + "+" + hashlib.sha256(raw).hexdigest()[:12]


ENTRY_A = {
    "reference_id": "ref-001",
    "license_family": "GPL",
    "risk_tier": "high",
    "hashes": ["0" * 64],
}
ENTRY_B = {
    "reference_id": "ref-002",
    "license_family": "MIT",
    "risk_tier": "low",
    "hashes": ["1" * 64],
}


def assert_stored(log, start, gv):
    puts = [e for e in read_log(log)[start:] if e["op"] == "put"]
    assert any(e["gate_version"] == gv for e in puts), (
        "setup scan did not store a result under " + gv + "; log: " + repr(puts)
    )


def assert_fresh_lookup(log, start, gv):
    gets = [e for e in read_log(log)[start:] if e["op"] == "get"]
    assert gets, "scan made no cache lookup through the stand-in cache-manager"
    assert all(e["gate_version"] == gv for e in gets), repr(gets)


def test_not_evaluated_result_not_reused_once_corpus_configured(tmp_path, monkeypatch):
    repo_root, log = make_repo(tmp_path, monkeypatch)

    first = license_scanner.scan("comp-foo", repo_root)
    assert field(first, "gate_version") == NO_CORPUS_GV
    assert field(first, "evaluated") is False
    assert_stored(log, 0, NO_CORPUS_GV)

    corpus = tmp_path / "corpus.json"
    expected_gv = write_corpus(corpus, 0, [ENTRY_A])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    mark = len(read_log(log))
    second = license_scanner.scan("comp-foo", repo_root)
    assert field(second, "cache_hit") is False
    assert field(second, "evaluated") is True
    assert field(second, "reason") is None
    assert field(second, "gate_version") == expected_gv
    assert expected_gv.startswith("license_scanner@4.0.0+")
    assert_fresh_lookup(log, mark, expected_gv)


def test_evaluated_result_not_reused_once_corpus_unset(tmp_path, monkeypatch):
    repo_root, log = make_repo(tmp_path, monkeypatch)

    corpus = tmp_path / "corpus.json"
    evaluated_gv = write_corpus(corpus, 0, [ENTRY_A])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    first = license_scanner.scan("comp-foo", repo_root)
    assert field(first, "evaluated") is True
    assert field(first, "gate_version") == evaluated_gv
    assert_stored(log, 0, evaluated_gv)

    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    mark = len(read_log(log))
    second = license_scanner.scan("comp-foo", repo_root)
    assert field(second, "cache_hit") is False
    assert field(second, "evaluated") is False
    assert field(second, "reason") == "no-reference-corpus"
    assert field(second, "gate_version") == NO_CORPUS_GV
    assert_fresh_lookup(log, mark, NO_CORPUS_GV)


def test_corpus_entry_added_without_version_bump_invalidates_cache(tmp_path, monkeypatch):
    repo_root, log = make_repo(tmp_path, monkeypatch)

    corpus = tmp_path / "corpus.json"
    old_gv = write_corpus(corpus, 2, [ENTRY_A])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    first = license_scanner.scan("comp-foo", repo_root)
    assert field(first, "evaluated") is True
    assert field(first, "gate_version") == old_gv
    assert_stored(log, 0, old_gv)

    new_gv = write_corpus(corpus, 2, [ENTRY_A, ENTRY_B])
    assert new_gv != old_gv

    mark = len(read_log(log))
    second = license_scanner.scan("comp-foo", repo_root)
    assert field(second, "cache_hit") is False
    assert field(second, "evaluated") is True
    assert field(second, "gate_version") == new_gv
    assert_fresh_lookup(log, mark, new_gv)