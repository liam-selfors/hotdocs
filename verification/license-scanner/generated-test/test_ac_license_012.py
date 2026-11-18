# hotdocs-criterion: sha256:30f2d2d39d15c51bf6fe0a3f55193b98bbe54e06e1b55d07e2a69c083206d5cf
import hashlib
import json
import textwrap
from pathlib import Path

import pytest

import license_scanner


FAKE_CACHE_MANAGER = textwrap.dedent(
    '''
    from dataclasses import dataclass, field
    from typing import Any


    class SchemaValidationError(ValueError):
        pass


    class Miss:
        def __eq__(self, other):
            return isinstance(other, Miss)

        def __hash__(self):
            return hash("Miss")


    @dataclass
    class CacheKey:
        spec_bundle_hash: str
        gate_inputs_hash: str
        gate_version: str
        model_pin: str


    @dataclass
    class CachedResult:
        gate_type: str
        payload: Any
        stored_at: str


    def get(cache_key, *, repo_root=None):
        return Miss()


    def put(cache_key, result, *, repo_root=None):
        return None


    def now_iso():
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


    def stats(*, repo_root=None):
        return {"entry_count": 0}
    '''
)


FOO_SOURCE = textwrap.dedent(
    '''
    def compute_total(items, multiplier):
        total = 0
        for item in items:
            total = total + item * multiplier
        return total


    def describe_widget(name, color, size, weight):
        label = name + color
        return label, size, weight
    '''
)


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "foo.py").write_text(FOO_SOURCE, encoding="utf-8")
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")
    return repo_root


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for name in (
        "VAR_LICENSE_CORPUS_PATH",
        "VAR_COMPLIANCE_WEBHOOK_URL",
        "VAR_CACHE_STORE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch


def _unrelated_hash() -> str:
    tokens = ["zzqx%d" % i for i in range(9)]
    return hashlib.sha256("\x1f".join(tokens).encode("utf-8")).hexdigest()


def test_unset_corpus_is_not_evaluated_and_not_blocked(clean_env, tmp_path):
    repo_root = _make_repo(tmp_path)
    clean_env.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    result = license_scanner.scan("comp-foo", repo_root)

    assert _field(result, "evaluated") is False
    assert _field(result, "reason") == "no-reference-corpus"
    assert _field(result, "similarity_score") is None
    assert _field(result, "block_threshold") is None
    matches = _field(result, "matches")
    assert matches is not None
    assert list(matches) == []
    assert _field(result, "blocked") is False
    assert _field(result, "gate_version") == "license_scanner@4.0.0-no-reference-corpus"


def test_empty_entries_corpus_is_invalid_and_blocked(clean_env, tmp_path):
    repo_root = _make_repo(tmp_path)
    corpus_path = tmp_path / "corpus_empty.json"
    corpus_path.write_text(
        json.dumps({"corpus_version": 2, "block_threshold": 0.7, "entries": []}),
        encoding="utf-8",
    )
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    assert _field(result, "evaluated") is False
    assert _field(result, "reason") == "corpus-invalid"
    assert _field(result, "blocked") is True
    assert _field(result, "similarity_score") is None
    assert _field(result, "block_threshold") is None
    matches = _field(result, "matches")
    assert matches is not None
    assert list(matches) == []


def test_valid_corpus_with_no_shared_windows_is_evaluated_clean(clean_env, tmp_path):
    repo_root = _make_repo(tmp_path)
    corpus = {
        "corpus_version": 7,
        "block_threshold": 0.7,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "low",
                "hashes": [_unrelated_hash()],
            }
        ],
    }
    corpus_bytes = json.dumps(corpus).encode("utf-8")
    corpus_path = tmp_path / "corpus_valid.json"
    corpus_path.write_bytes(corpus_bytes)
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    assert _field(result, "evaluated") is True
    assert _field(result, "reason") is None
    score = _field(result, "similarity_score")
    assert score is not None
    assert isinstance(score, (int, float)) and not isinstance(score, bool)
    assert score == 0.0
    assert _field(result, "blocked") is False
    expected_digest = hashlib.sha256(corpus_bytes).hexdigest()[:12]
    assert _field(result, "gate_version") == "license_scanner@4.0.7+" + expected_digest