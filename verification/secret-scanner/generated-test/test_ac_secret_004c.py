import json
import urllib.request

import pytest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_CACHE_MANAGER_MODULE = '''
from dataclasses import dataclass
from typing import Optional


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: Optional[dict]
    stored_at: str


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    pass
'''


def test_clean_scan_has_no_matches_and_notified_is_false(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "gen").mkdir(parents=True)
    (repo_root / "verification").mkdir(parents=True)

    (repo_root / "specs" / "notes.md").write_text(
        "Just an ordinary, benign line of specification text.\n"
    )
    (repo_root / "verification" / "notes.md").write_text(
        "Just an ordinary, benign line of verification text.\n"
    )

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(_CACHE_MANAGER_MODULE)

    patterns_path = tmp_path / "patterns.json"
    patterns_path.write_text(
        json.dumps({"version": "1.0.0", "rules": []})
    )

    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(patterns_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError(
            "urlopen must not be called when no notification is due"
        )

    monkeypatch.setattr(urllib.request, "urlopen", _fail_if_called)

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is False
    assert _get(result, "matches") == []
    assert _get(result, "notified") is False
    assert _get(result, "notification_delivery_error") is None