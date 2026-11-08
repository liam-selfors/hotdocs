import urllib.request
from pathlib import Path

import pytest

import secret_scanner


CACHE_MANAGER_SOURCE = '''
from dataclasses import dataclass


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


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None
'''


def _write_cache_manager_fake(repo_root: Path) -> None:
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(CACHE_MANAGER_SOURCE)


def _write_secret_file(repo_root: Path) -> None:
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True, exist_ok=True)
    (foo_dir / "h.py").write_text(
        'sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"\n'
    )


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return b""

    def getcode(self):
        return 200


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def test_low_risk_tier_match_that_blocks_merge_still_notifies(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_cache_manager_fake(repo_root)
    _write_secret_file(repo_root)

    monkeypatch.setenv(
        "VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/compliance-webhook"
    )

    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = secret_scanner.scan(repo_root)

    flagged = _field(result, "flagged")
    matches = _field(result, "matches")

    assert flagged is True
    assert matches

    target_matches = [m for m in matches if _field(m, "file") == "gen/foo/h.py"]
    assert target_matches, f"expected a match in gen/foo/h.py, got: {matches}"

    risk_tier = _field(target_matches[0], "risk_tier")
    assert risk_tier == "low"

    assert len(calls) == 1