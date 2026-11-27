# hotdocs-criterion: sha256:1d02a94180a6c17374e85eef42d97542979f93621490547dcef2b6ca200d8bdf
"""AC-SECRET-004c: a clean scan with no match at all reports notified false."""

import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


WEBHOOK_URL = "http://127.0.0.1:9/compliance-hook"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = "\n".join([
    "from dataclasses import dataclass",
    "import datetime",
    "",
    "",
    "@dataclass",
    "class CacheKey:",
    "    spec_bundle_hash: str",
    "    gate_inputs_hash: str",
    "    gate_version: str",
    "    model_pin: str",
    "",
    "",
    "@dataclass",
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
    "def get(cache_key, *, repo_root=None):",
    "    return Miss()",
    "",
    "",
    "def put(cache_key, result, *, repo_root=None):",
    "    return None",
    "",
    "",
    "def now_iso():",
    "    now = datetime.datetime.now(datetime.timezone.utc)",
    "    return now.strftime('%Y-%m-%dT%H:%M:%SZ')",
    "",
    "",
    "def stats(*, repo_root=None):",
    "    return dict(entry_count=0)",
    "",
])


def _build_clean_repo(repo_root: Path) -> None:
    (repo_root / "README.md").write_text("A plain readme with nothing secret.\n")
    src = repo_root / "src"
    src.mkdir()
    (src / "hello.py").write_text("def greet(name):\n    return 'hello ' + name\n")
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)


@pytest.fixture
def clean_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_clean_repo(repo_root)
    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)

    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("compliance webhook must not be called on a clean scan")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return repo_root, calls


def test_clean_scan_library_reports_not_notified(clean_repo):
    repo_root, calls = clean_repo

    result = secret_scanner.scan(repo_root)

    matches = field(result, "matches")
    assert list(matches) == []
    assert field(result, "flagged") is False
    assert field(result, "notified") is False
    assert field(result, "notification_delivery_error") is None
    assert calls == []

    as_dict = result.to_dict()
    assert as_dict["notified"] is False


def test_clean_scan_cli_json_reports_not_notified(clean_repo, capsys):
    repo_root, calls = clean_repo

    code = secret_scanner.main(["--repo-root=" + str(repo_root), "--format=json"])
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["matches"] == []
    assert payload["flagged"] is False
    assert payload["notified"] is False
    assert calls == []