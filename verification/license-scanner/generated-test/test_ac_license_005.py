import hashlib
import json
import re

import pytest

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


def _tokenize(text):
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


def _window_hashes(tokens, window=9):
    hashes = set()
    for i in range(len(tokens) - window + 1):
        joined = "\x1f".join(tokens[i:i + window])
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return hashes


_CACHE_MANAGER_SOURCE = r'''
import json
import os
from dataclasses import dataclass

_STORE = {}


def _log(event, gate_version):
    log_path = os.environ.get("FAKE_CACHE_LOG")
    if log_path:
        with open(log_path, "a") as f:
            f.write(json.dumps({"event": event, "gate_version": gate_version}) + "\n")


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name)


def _key_tuple(cache_key):
    return (
        _field(cache_key, "spec_bundle_hash"),
        _field(cache_key, "gate_inputs_hash"),
        _field(cache_key, "gate_version"),
        _field(cache_key, "model_pin"),
    )


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    key = _key_tuple(cache_key)
    _log("get", key[2])
    if key in _STORE:
        return _STORE[key]
    return Miss()


def put(cache_key, result, *, repo_root=None):
    key = _key_tuple(cache_key)
    _STORE[key] = result
    _log("put", key[2])
'''


def _write_cache_manager_fake(repo_root):
    module_dir = repo_root / "gen" / "cache-manager"
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "cache_manager.py").write_text(_CACHE_MANAGER_SOURCE)


def test_stale_cache_not_reused_after_corpus_gate_version_bump(tmp_path, monkeypatch):
    repo_root = tmp_path

    log_path = repo_root / "cache_calls.jsonl"
    monkeypatch.setenv("FAKE_CACHE_LOG", str(log_path))

    _write_cache_manager_fake(repo_root)

    source_tokens = [
        "alpha", "beta", "gamma", "delta", "epsilon",
        "zeta", "eta", "theta", "iota",
    ]
    source_text = " ".join(source_tokens)
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / "foo.py").write_text(source_text)

    expected_hashes = _window_hashes(_tokenize(source_text))
    assert len(expected_hashes) == 1

    corpus_path = repo_root / "license_corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    corpus_v1 = {"corpus_version": 1, "block_threshold": 0.70, "entries": []}
    corpus_path.write_text(json.dumps(corpus_v1))

    gate_version_v1 = license_scanner.gate_version(repo_root)
    assert gate_version_v1 == "license_scanner@3.1.1"

    result1 = license_scanner.scan("comp-foo", repo_root)
    assert _get(result1, "gate_version") == gate_version_v1
    assert _get(result1, "cache_hit") is False
    assert _get(result1, "similarity_score") == 0.0
    assert _get(result1, "blocked") is False

    corpus_v2 = {
        "corpus_version": 2,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-stale-test",
                "license_family": "gpl-3.0",
                "risk_tier": "high",
                "hashes": sorted(expected_hashes),
            }
        ],
    }
    corpus_path.write_text(json.dumps(corpus_v2))

    gate_version_v2 = license_scanner.gate_version(repo_root)
    assert gate_version_v2 == "license_scanner@3.1.2"
    assert gate_version_v2 != gate_version_v1

    result2 = license_scanner.scan("comp-foo", repo_root)

    assert _get(result2, "gate_version") == gate_version_v2
    assert _get(result2, "cache_hit") is False
    assert _get(result2, "similarity_score") == 1.0
    assert _get(result2, "similarity_score") != _get(result1, "similarity_score")
    assert _get(result2, "blocked") is True

    log_lines = [
        json.loads(line)
        for line in log_path.read_text().splitlines()
        if line.strip()
    ]
    get_calls = [entry for entry in log_lines if entry["event"] == "get"]
    put_calls = [entry for entry in log_lines if entry["event"] == "put"]

    assert len(get_calls) == 2
    assert get_calls[0]["gate_version"] == gate_version_v1
    assert get_calls[1]["gate_version"] == gate_version_v2

    assert len(put_calls) == 2
    assert put_calls[0]["gate_version"] == gate_version_v1
    assert put_calls[1]["gate_version"] == gate_version_v2