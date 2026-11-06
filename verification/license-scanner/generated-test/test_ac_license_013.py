import json
import textwrap
import urllib.request
from pathlib import Path

import pytest

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = _find_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_key(item, key)
            if found is not None:
                return found
    return None


_FAKE_CACHE_MANAGER_SRC = textwrap.dedent(
    """
    from dataclasses import dataclass
    from typing import Any

    @dataclass
    class CacheKey:
        spec_bundle_hash: Any = None
        gate_inputs_hash: Any = None
        gate_version: Any = None
        model_pin: Any = None

    @dataclass
    class CachedResult:
        gate_type: Any = None
        payload: Any = None
        stored_at: Any = None

    class Miss:
        pass

    def get(cache_key, *, repo_root=None):
        return Miss()

    def put(cache_key, result, *, repo_root=None):
        pass
    """
)


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache_manager.py").write_text(_FAKE_CACHE_MANAGER_SRC)
    return repo_root


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b"{}"

    @property
    def status(self):
        return 200


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        data = kwargs.get("data")
        req = args[0] if args else None
        if data is None and len(args) > 1:
            data = args[1]
        if data is None and req is not None and hasattr(req, "data"):
            data = req.data

        payload = None
        raw = data
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except Exception:
                raw = None
        if isinstance(raw, str):
            try:
                payload = json.loads(raw)
            except Exception:
                payload = None

        self.calls.append(payload)
        return _FakeResponse()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)


def test_corpus_unreadable_missing_file(tmp_path, monkeypatch):
    repo_root = _make_repo(tmp_path)
    missing = repo_root / "nonexistent-corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))

    result = license_scanner.scan("comp-foo", repo_root)

    assert _get(result, "evaluated") is False
    assert _get(result, "reason") == "corpus-unreadable"
    assert _get(result, "blocked") is True
    assert _get(result, "similarity_score") is None
    assert _get(result, "gate_version") == "license_scanner@4.0.0-corpus-unreadable"


_VALID_ENTRY = {
    "reference_id": "ref-001",
    "license_family": "GPL",
    "risk_tier": "high",
    "hashes": ["a" * 64],
}

_BASE_CORPUS = {
    "corpus_version": 3,
    "block_threshold": 0.7,
    "entries": [_VALID_ENTRY],
}

_BAD_HASHES_ENTRY = {
    "reference_id": "ref-002",
    "license_family": "GPL",
    "risk_tier": "high",
    "hashes": "not-a-list",
}

_BAD_RISK_ENTRY = {
    "reference_id": "ref-003",
    "license_family": "GPL",
    "risk_tier": "severe",
    "hashes": ["b" * 64],
}

_INVALID_CORPUS_CASES = [
    ("not-valid-json", "{not valid json"),
    ("json-list", json.dumps([_VALID_ENTRY])),
    ("no-entries-list", json.dumps({"corpus_version": 3, "block_threshold": 0.7})),
    ("corpus-version-x", json.dumps({**_BASE_CORPUS, "corpus_version": "x"})),
    ("block-threshold-0", json.dumps({**_BASE_CORPUS, "block_threshold": 0})),
    ("block-threshold-1.5", json.dumps({**_BASE_CORPUS, "block_threshold": 1.5})),
    ("hashes-not-list", json.dumps({**_BASE_CORPUS, "entries": [_BAD_HASHES_ENTRY]})),
    ("risk-tier-severe", json.dumps({**_BASE_CORPUS, "entries": [_BAD_RISK_ENTRY]})),
]


@pytest.mark.parametrize(
    "case_id,content",
    _INVALID_CORPUS_CASES,
    ids=[case[0] for case in _INVALID_CORPUS_CASES],
)
def test_corpus_invalid(tmp_path, monkeypatch, case_id, content):
    repo_root = _make_repo(tmp_path)
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(content)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    assert _get(result, "evaluated") is False, case_id
    assert _get(result, "reason") == "corpus-invalid", case_id
    assert _get(result, "blocked") is True, case_id
    assert _get(result, "gate_version") == "license_scanner@4.0.0-corpus-invalid", case_id


def test_notified_on_corpus_unreadable_with_webhook(tmp_path, monkeypatch):
    repo_root = _make_repo(tmp_path)
    missing = repo_root / "still-missing-corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    recorder = _Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    result = license_scanner.scan("comp-foo", repo_root)

    assert _get(result, "evaluated") is False
    assert _get(result, "reason") == "corpus-unreadable"
    assert _get(result, "blocked") is True
    assert _get(result, "notified") is True

    assert recorder.calls, "expected urlopen to be invoked for notification delivery"

    found_evaluated = None
    found_reason = None
    for payload in recorder.calls:
        if payload is None:
            continue
        ev = _find_key(payload, "evaluated")
        rs = _find_key(payload, "reason")
        if ev is not None or rs is not None:
            found_evaluated = ev
            found_reason = rs
            break

    assert found_evaluated is False
    assert found_reason == "corpus-unreadable"