# hotdocs-criterion: sha256:42db3091a39eb9d91fbc7ba5dc800ce772cf75157ac0d3d0d14a64c8d51b2341
import hashlib
import json
import os
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SECRET_SCAN_AC008_CACHE_LOG"

FIXTURE_SECRET = "AKIAABCDEFGHIJKLMNOP"
LIVE_SECRET = "AKIAZZZZYYYYXXXXWWWW"


CACHE_MANAGER_STANDIN = '''
import json
import os
from dataclasses import dataclass, field
from typing import Any


def _record(name):
    path = os.environ.get("SECRET_SCAN_AC008_CACHE_LOG")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name}) + "\\n")


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str

    def __post_init__(self):
        _record("CacheKey")


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str

    def __post_init__(self):
        _record("CachedResult")


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


def get(cache_key, *, repo_root=None):
    _record("get")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _record("put")
    return None


def now_iso():
    _record("now_iso")
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    _record("stats")
    return {"entry_count": 0}
'''


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _build_repo(repo_root: Path) -> None:
    # Allowlisted fixture file
    fixture = repo_root / "verification" / "foo" / "t.py"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text('K = "' + FIXTURE_SECRET + '"\n', encoding="utf-8")

    # Live, non-allowlisted file
    live = repo_root / "src" / "c.py"
    live.parent.mkdir(parents=True, exist_ok=True)
    live.write_text('C = "' + LIVE_SECRET + '"\n', encoding="utf-8")

    # Allowlist
    allowlist = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/t.py",
                "type": "AWS Access Key",
                "hashed_secret": "sha1:"
                + hashlib.sha1(FIXTURE_SECRET.encode("utf-8")).hexdigest(),
                "reason": "planted-fixture",
            }
        ],
    }
    allowlist_bytes = (json.dumps(allowlist, indent=2) + "\n").encode("utf-8")
    (repo_root / ".secret-allowlist.json").write_bytes(allowlist_bytes)

    # Seal: a decision carrying allowlist_sha256 of the exact allowlist bytes
    seal = hashlib.sha256(allowlist_bytes).hexdigest()
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    (decisions / "D1.md").write_text(
        "---\n"
        "id: D1\n"
        "title: Seal the secret allowlist\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000\n"
        "allowlist_sha256: sha256:" + seal + "\n"
        "---\n"
        "\n"
        "Seals the current `.secret-allowlist.json`.\n",
        encoding="utf-8",
    )

    # Recording cache-manager stand-in (flat module form)
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(CACHE_MANAGER_STANDIN, encoding="utf-8")


def test_ac_secret_008_precommit_scoped_allowlisted_no_cache(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    log_path = tmp_path / "cache_calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    webhook_calls = []

    def _fake_urlopen(*args, **kwargs):
        webhook_calls.append((args, kwargs))
        raise AssertionError("webhook must not be called in this test")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    paths = [
        repo_root / "verification" / "foo" / "t.py",
        repo_root / "src" / "c.py",
    ]

    result = secret_scanner.scan_files(paths, repo_root=repo_root)

    assert _field(result, "scope") == "precommit"

    matches = _field(result, "matches") or []
    match_files = [_field(m, "file") for m in matches]
    assert match_files, "expected at least one match for src/c.py"
    assert all(f == "src/c.py" for f in match_files), match_files

    allowed = _field(result, "allowed") or []
    allowed_files = [_field(a, "file") for a in allowed]
    assert "verification/foo/t.py" in allowed_files, allowed_files

    assert _field(result, "flagged") is True
    assert _field(result, "cache_hit") in (False, None)

    recorded = ""
    if log_path.exists():
        recorded = log_path.read_text(encoding="utf-8").strip()
    assert recorded == "", "cache-manager stand-in recorded calls: " + recorded