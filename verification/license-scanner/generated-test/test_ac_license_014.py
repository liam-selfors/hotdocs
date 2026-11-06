import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FAKE_CACHE_MANAGER_SOURCE = """
import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: Any
    payload: Any
    stored_at: Any


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name)


def _key_str(cache_key):
    return "|".join([
        str(_field(cache_key, "spec_bundle_hash")),
        str(_field(cache_key, "gate_inputs_hash")),
        str(_field(cache_key, "gate_version")),
        str(_field(cache_key, "model_pin")),
    ])


def _store_path(repo_root):
    return os.path.join(str(repo_root), ".fake_cache_store.json")


def _calls_path(repo_root):
    return os.path.join(str(repo_root), ".fake_cache_calls.log")


def _load(repo_root):
    path = _store_path(repo_root)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _save(repo_root, data):
    with open(_store_path(repo_root), "w") as f:
        json.dump(data, f)


def get(cache_key, *, repo_root=None):
    with open(_calls_path(repo_root), "a") as f:
        f.write("get " + _key_str(cache_key) + "\\n")
    data = _load(repo_root)
    entry = data.get(_key_str(cache_key))
    if entry is None:
        return CachedResult(gate_type=None, payload=None, stored_at=None)
    return CachedResult(
        gate_type=entry["gate_type"],
        payload=entry["payload"],
        stored_at=entry["stored_at"],
    )


def put(cache_key, result, *, repo_root=None):
    with open(_calls_path(repo_root), "a") as f:
        f.write("put " + _key_str(cache_key) + "\\n")
    data = _load(repo_root)
    data[_key_str(cache_key)] = {
        "gate_type": _field(result, "gate_type"),
        "payload": _field(result, "payload"),
        "stored_at": _field(result, "stored_at"),
    }
    _save(repo_root, data)
"""


def _make_repo_root(tmp_dir):
    repo_root = Path(tmp_dir)
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "foo.py").write_text(
        "def example_function(a, b, c, d, e, f, g, h, i):\n"
        "    return a + b + c + d + e + f + g + h + i\n"
    )
    return repo_root


def _set_corpus_var(path):
    os.environ["VAR_LICENSE_CORPUS_PATH"] = str(path)


def _unset_corpus_var():
    os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)


def _expected_gate_version(corpus_path):
    data = Path(corpus_path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:12]
    version = json.loads(data.decode("utf-8")).get("corpus_version", 0)
    return "license_scanner@4.0.{}+{}".format(version, digest)


def test_corpus_appearing_invalidates_not_evaluated_cache():
    tmp_dir = tempfile.mkdtemp()
    _unset_corpus_var()
    try:
        repo_root = _make_repo_root(tmp_dir)

        first = license_scanner.scan("comp-foo", repo_root)
        assert _get(first, "evaluated") is False
        assert _get(first, "reason") == "no-reference-corpus"
        assert _get(first, "gate_version") == "license_scanner@4.0.0-no-reference-corpus"

        corpus_path = repo_root / "license-corpus.json"
        corpus_data = {
            "corpus_version": 0,
            "block_threshold": 0.70,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": ["0" * 64],
                }
            ],
        }
        corpus_path.write_text(json.dumps(corpus_data))
        expected_gate_version = _expected_gate_version(corpus_path)
        assert expected_gate_version.startswith("license_scanner@4.0.0+")

        _set_corpus_var(corpus_path)
        try:
            second = license_scanner.scan("comp-foo", repo_root)
        finally:
            _unset_corpus_var()

        assert _get(second, "cache_hit") is False
        assert _get(second, "evaluated") is True
        assert _get(second, "gate_version") == expected_gate_version
    finally:
        _unset_corpus_var()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_corpus_disappearing_invalidates_evaluated_cache():
    tmp_dir = tempfile.mkdtemp()
    _unset_corpus_var()
    try:
        repo_root = _make_repo_root(tmp_dir)

        corpus_path = repo_root / "license-corpus.json"
        corpus_data = {
            "corpus_version": 2,
            "block_threshold": 0.70,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": ["1" * 64],
                }
            ],
        }
        corpus_path.write_text(json.dumps(corpus_data))
        expected_gate_version = _expected_gate_version(corpus_path)

        _set_corpus_var(corpus_path)
        try:
            first = license_scanner.scan("comp-foo", repo_root)
        finally:
            _unset_corpus_var()

        assert _get(first, "evaluated") is True
        assert _get(first, "gate_version") == expected_gate_version

        second = license_scanner.scan("comp-foo", repo_root)

        assert _get(second, "cache_hit") is False
        assert _get(second, "evaluated") is False
        assert _get(second, "reason") == "no-reference-corpus"
    finally:
        _unset_corpus_var()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_corpus_content_change_without_version_bump_invalidates_cache():
    tmp_dir = tempfile.mkdtemp()
    _unset_corpus_var()
    try:
        repo_root = _make_repo_root(tmp_dir)

        corpus_path = repo_root / "license-corpus.json"
        corpus_data = {
            "corpus_version": 5,
            "block_threshold": 0.70,
            "entries": [
                {
                    "reference_id": "ref-001",
                    "license_family": "GPL",
                    "risk_tier": "high",
                    "hashes": ["2" * 64],
                }
            ],
        }
        corpus_path.write_text(json.dumps(corpus_data))

        _set_corpus_var(corpus_path)
        try:
            first = license_scanner.scan("comp-foo", repo_root)
            assert _get(first, "evaluated") is True

            corpus_data["entries"].append(
                {
                    "reference_id": "ref-002",
                    "license_family": "MIT",
                    "risk_tier": "low",
                    "hashes": ["3" * 64],
                }
            )
            # corpus_version intentionally left unchanged
            corpus_path.write_text(json.dumps(corpus_data))

            second = license_scanner.scan("comp-foo", repo_root)
        finally:
            _unset_corpus_var()

        assert _get(second, "cache_hit") is False
        assert _get(second, "evaluated") is True
    finally:
        _unset_corpus_var()
        shutil.rmtree(tmp_dir, ignore_errors=True)