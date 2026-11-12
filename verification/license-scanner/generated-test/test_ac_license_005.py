import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

import license_scanner


POISON_SCORE = 0.987654
POISON_REFERENCE_ID = "ref-poisoned-stale-entry"


def _f(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


FAKE_CACHE_MANAGER_TEMPLATE = '''
import json
import os
from dataclasses import dataclass, asdict, is_dataclass
from datetime import datetime, timezone

_STORE_PATH = {store_path!r}
_LOG_PATH = {log_path!r}


class SchemaValidationError(ValueError):
    pass


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("Miss")

    def __repr__(self):
        return "Miss()"


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


_REQUIRED = {{
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}}


def _attr(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _key_str(cache_key):
    return json.dumps([
        _attr(cache_key, "spec_bundle_hash"),
        _attr(cache_key, "gate_inputs_hash"),
        _attr(cache_key, "gate_version"),
        _attr(cache_key, "model_pin"),
    ])


def _load_store():
    if not os.path.exists(_STORE_PATH):
        return {{}}
    with open(_STORE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_store(store):
    with open(_STORE_PATH, "w", encoding="utf-8") as fh:
        json.dump(store, fh, default=str)


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\\n")


def _to_plain(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    return obj


def get(cache_key, *, repo_root=None):
    store = _load_store()
    k = _key_str(cache_key)
    entry = store.get(k)
    _log({{
        "op": "get",
        "gate_version": _attr(cache_key, "gate_version"),
        "hit": entry is not None,
    }})
    if entry is None:
        return Miss()
    return CachedResult(
        gate_type=entry["gate_type"],
        payload=entry["payload"],
        stored_at=entry["stored_at"],
    )


def put(cache_key, result, *, repo_root=None):
    gate_version = _attr(cache_key, "gate_version")
    gate_type = _attr(result, "gate_type")
    payload = _to_plain(_attr(result, "payload"))
    expected_type = str(gate_version).split("@", 1)[0]
    if gate_type != expected_type or gate_type not in _REQUIRED:
        raise SchemaValidationError("gate_type mismatch")
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload not a dict")
    for key in _REQUIRED[gate_type]:
        if key not in payload:
            raise SchemaValidationError("missing payload key: " + key)
    store = _load_store()
    store[_key_str(cache_key)] = {{
        "gate_version": gate_version,
        "gate_type": gate_type,
        "payload": json.loads(json.dumps(payload, default=str)),
        "stored_at": _attr(result, "stored_at"),
    }}
    _save_store(store)
    _log({{"op": "put", "gate_version": gate_version}})


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": len(_load_store())}}


def main(argv=None):
    return 0
'''


SOURCE_TEXT = '''
def compute_total(items, factor):
    total = 0
    for item in items:
        total = total + item * factor
    return total


def describe_total(items, factor, label):
    value = compute_total(items, factor)
    return label + " " + str(value)
'''


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [alice]
sealed: true
source_path: src/foo
---

# Foo

A synthetic fixture component.
"""


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    control = tmp_path / "control"
    control.mkdir(parents=True)
    store_path = control / "store.json"
    log_path = control / "log.jsonl"

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_TEMPLATE.format(
            store_path=str(store_path), log_path=str(log_path)
        ),
        encoding="utf-8",
    )

    gen_src = repo_root / "gen" / "foo"
    gen_src.mkdir(parents=True)
    (gen_src / "foo.py").write_text(SOURCE_TEXT, encoding="utf-8")

    sealed_src = repo_root / "src" / "foo"
    sealed_src.mkdir(parents=True)
    (sealed_src / "foo.py").write_text(SOURCE_TEXT, encoding="utf-8")

    spec_dir = repo_root / "specs" / "components" / "foo"
    spec_dir.mkdir(parents=True)
    (spec_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    return repo_root, store_path, log_path


def _write_corpus(repo_root, corpus_version, block_threshold=0.70, extra_ref=False):
    entries = [
        {
            "reference_id": "ref-001",
            "license_family": "mit",
            "risk_tier": "low",
            "hashes": ["0" * 64, "1" * 64],
        }
    ]
    if extra_ref:
        entries.append(
            {
                "reference_id": "ref-002",
                "license_family": "bsd",
                "risk_tier": "low",
                "hashes": ["2" * 64],
            }
        )
    corpus = {
        "corpus_version": corpus_version,
        "block_threshold": block_threshold,
        "entries": entries,
    }
    data = json.dumps(corpus, indent=2, sort_keys=True).encode("utf-8")
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_bytes(data)
    return corpus_path, data


def _expected_gate_version(corpus_version, data):
    h = hashlib.sha256(data).hexdigest()[:12]
    return "license_scanner@4.0.%d+%s" % (corpus_version, h)


def _read_log(log_path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _poison_store(store_path, stale_gate_version):
    store = json.loads(store_path.read_text(encoding="utf-8"))
    poisoned_any = False
    for key, entry in store.items():
        if entry.get("gate_version") == stale_gate_version:
            payload = entry["payload"]
            payload["similarity_score"] = POISON_SCORE
            payload["blocked"] = True
            payload["matches"] = [
                {
                    "reference_id": POISON_REFERENCE_ID,
                    "license_family": "gpl-3.0",
                    "risk_tier": "high",
                    "score": POISON_SCORE,
                }
            ]
            payload["gate_version"] = stale_gate_version
            poisoned_any = True
    store_path.write_text(json.dumps(store), encoding="utf-8")
    return poisoned_any


@pytest.fixture
def env(tmp_path, monkeypatch):
    for name in (
        "VAR_LICENSE_CORPUS_PATH",
        "VAR_COMPLIANCE_WEBHOOK_URL",
        "VAR_CACHE_STORE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    repo_root, store_path, log_path = _build_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    return repo_root, store_path, log_path


def _populate_stale_entry(repo_root, store_path, log_path, monkeypatch, corpus_version):
    corpus_path, data = _write_corpus(repo_root, corpus_version)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    old_gv = _expected_gate_version(corpus_version, data)
    assert license_scanner.gate_version(repo_root) == old_gv

    first = license_scanner.scan("comp-foo", repo_root)
    assert _f(first, "evaluated") is True
    assert _f(first, "gate_version") == old_gv

    puts = [r for r in _read_log(log_path) if r["op"] == "put"]
    assert any(r["gate_version"] == old_gv for r in puts), (
        "initial scan must store its result under the old gate_version"
    )
    assert store_path.exists()
    assert _poison_store(store_path, old_gv), "stale cache entry must exist in store"
    return corpus_path, old_gv


def _assert_fresh_scan(result, new_gv, old_gv, log_path):
    assert _f(result, "evaluated") is True
    assert _f(result, "gate_version") == new_gv
    assert _f(result, "gate_version") != old_gv
    assert _f(result, "cache_hit") is False
    assert _f(result, "similarity_score") != POISON_SCORE
    assert _f(result, "blocked") is False
    matches = _f(result, "matches") or []
    for m in matches:
        assert _f(m, "reference_id") != POISON_REFERENCE_ID

    records = _read_log(log_path)
    gets = [r for r in records if r["op"] == "get"]
    puts = [r for r in records if r["op"] == "put"]
    for g in gets:
        assert g["gate_version"] != old_gv, "stale gate_version must not be looked up"
        assert g["hit"] is False, "no cache hit may be reused after corpus change"
    assert any(p["gate_version"] == new_gv for p in puts), (
        "a fresh scan must store its result under the new gate_version"
    )


def test_corpus_version_bump_invalidates_stale_cache_entry(env, monkeypatch):
    repo_root, store_path, log_path = env
    _, old_gv = _populate_stale_entry(
        repo_root, store_path, log_path, monkeypatch, corpus_version=1
    )

    log_path.write_text("", encoding="utf-8")

    corpus_path, data = _write_corpus(repo_root, 2, extra_ref=True)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    new_gv = _expected_gate_version(2, data)
    assert new_gv != old_gv
    assert license_scanner.gate_version(repo_root) == new_gv

    result = license_scanner.scan("comp-foo", repo_root)
    _assert_fresh_scan(result, new_gv, old_gv, log_path)


def test_corpus_bytes_change_without_version_bump_invalidates_stale_cache_entry(
    env, monkeypatch
):
    repo_root, store_path, log_path = env
    _, old_gv = _populate_stale_entry(
        repo_root, store_path, log_path, monkeypatch, corpus_version=3
    )

    log_path.write_text("", encoding="utf-8")

    corpus_path, data = _write_corpus(repo_root, 3, block_threshold=0.75)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    new_gv = _expected_gate_version(3, data)
    assert new_gv != old_gv
    assert new_gv.startswith("license_scanner@4.0.3+")
    assert license_scanner.gate_version(repo_root) == new_gv

    result = license_scanner.scan("comp-foo", repo_root)
    _assert_fresh_scan(result, new_gv, old_gv, log_path)