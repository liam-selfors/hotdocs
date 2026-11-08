import json
from pathlib import Path

import pytest

import license_scanner


_CACHE_MANAGER_SOURCE = '''
from dataclasses import dataclass
from typing import Any, Optional


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


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None
'''


def _write_cache_manager(repo_root: Path) -> None:
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(_CACHE_MANAGER_SOURCE, encoding="utf-8")


def _write_component_stub(repo_root: Path, component_id: str) -> None:
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    comp_dir = repo_root / "gen" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    module_name = slug.replace("-", "_")
    (comp_dir / f"{module_name}.py").write_text("x = 1\n", encoding="utf-8")


def _get_field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _setup_repo(tmp_path, component_id="comp-foo"):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_cache_manager(repo_root)
    _write_component_stub(repo_root, component_id)
    return repo_root


def test_corpus_unreadable_fails_closed(tmp_path, monkeypatch):
    repo_root = _setup_repo(tmp_path)
    missing_corpus = repo_root / "no-such-corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing_corpus))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    result = license_scanner.scan("comp-foo", repo_root)

    assert _get_field(result, "evaluated") is False
    assert _get_field(result, "reason") == "corpus-unreadable"
    assert _get_field(result, "blocked") is True
    assert _get_field(result, "similarity_score") is None
    assert _get_field(result, "gate_version") == "license_scanner@4.0.0-corpus-unreadable"


_INVALID_CORPORA = {
    "not_json": "this is not valid json {{{",
    "json_list": json.dumps([{"reference_id": "r1", "risk_tier": "high", "hashes": ["abc"]}]),
    "no_entries_key": json.dumps({"corpus_version": 1}),
    "bad_corpus_version": json.dumps({
        "corpus_version": "x",
        "entries": [{"reference_id": "r1", "risk_tier": "high", "hashes": ["abc"]}],
    }),
    "block_threshold_zero": json.dumps({
        "block_threshold": 0,
        "entries": [{"reference_id": "r1", "risk_tier": "high", "hashes": ["abc"]}],
    }),
    "block_threshold_too_high": json.dumps({
        "block_threshold": 1.5,
        "entries": [{"reference_id": "r1", "risk_tier": "high", "hashes": ["abc"]}],
    }),
    "hashes_not_list": json.dumps({
        "entries": [{"reference_id": "r1", "risk_tier": "high", "hashes": "abc"}],
    }),
    "bad_risk_tier": json.dumps({
        "entries": [{"reference_id": "r1", "risk_tier": "severe", "hashes": ["abc"]}],
    }),
}


@pytest.mark.parametrize("case_name", sorted(_INVALID_CORPORA.keys()))
def test_corpus_invalid_fails_closed(tmp_path, monkeypatch, case_name):
    repo_root = _setup_repo(tmp_path)
    corpus_path = repo_root / f"corpus-{case_name}.json"
    corpus_path.write_text(_INVALID_CORPORA[case_name], encoding="utf-8")
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    result = license_scanner.scan("comp-foo", repo_root)

    assert _get_field(result, "evaluated") is False
    assert _get_field(result, "reason") == "corpus-invalid"
    assert _get_field(result, "blocked") is True
    assert _get_field(result, "gate_version") == "license_scanner@4.0.0-corpus-invalid"


def test_notifies_webhook_on_unreadable_corpus_block(tmp_path, monkeypatch):
    repo_root = _setup_repo(tmp_path)
    missing_corpus = repo_root / "no-such-corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing_corpus))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/webhook")

    log_path = tmp_path / "webhook-calls.log"

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"{}"

        def close(self):
            pass

    def _extract_data(args, kwargs):
        data = kwargs.get("data")
        if data is not None:
            return data
        for arg in args:
            candidate = getattr(arg, "data", None)
            if candidate is not None:
                return candidate
            if isinstance(arg, (bytes, bytearray)):
                return arg
        return None

    def _recorder(*args, **kwargs):
        data = _extract_data(args, kwargs)
        with open(log_path, "a", encoding="utf-8") as f:
            if isinstance(data, (bytes, bytearray)):
                f.write(data.decode("utf-8"))
            else:
                f.write(str(data))
            f.write("\n")
        return _FakeResponse()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _recorder)

    result = license_scanner.scan("comp-foo", repo_root)

    assert _get_field(result, "evaluated") is False
    assert _get_field(result, "blocked") is True
    assert _get_field(result, "notified") is True

    assert log_path.exists()
    logged_lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert logged_lines, "expected the recorder to have been invoked with a payload"
    payload = json.loads(logged_lines[0])

    assert _get_field(payload, "evaluated") is False
    assert _get_field(payload, "reason") == "corpus-unreadable"