# hotdocs-criterion: sha256:a83fca86350bb69eee7e2867d7857e09d4cdf654d25420c366d91cd0ee508e65
"""AC-SECRET-004c: a clean scan with no match at all reports notified == false."""

import urllib.request
from pathlib import Path

import secret_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "from dataclasses import dataclass\n"
    "from typing import Any\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: Any\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    import datetime\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime("
    + repr("%Y-%m-%dT%H:%M:%SZ")
    + ")\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return " + repr({"entry_count": 0}) + "\n"
)


def _build_clean_repo(repo_root: Path) -> None:
    (repo_root / "README.md").write_text("A clean repository with nothing secret.\n")
    src = repo_root / "src"
    src.mkdir()
    (src / "hello.py").write_text(
        "def greet(name):\n"
        "    return 'hello ' + name\n"
    )
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)


def test_ac_secret_004c_clean_scan_not_notified(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_clean_repo(repo_root)

    monkeypatch.chdir(repo_root)
    # Configure the webhook so "not notified" is due to the clean scan,
    # not merely to an unconfigured webhook.
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:9/compliance-hook")
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("no webhook call expected for a clean scan")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = secret_scanner.scan(repo_root)

    # Precondition: the scan really is clean with no match at all.
    assert list(field(result, "matches")) == []
    assert field(result, "flagged") is False

    # Then: notified is false.
    assert field(result, "notified") is False
    assert field(result, "notification_delivery_error") is None

    as_dict = result.to_dict()
    assert as_dict["notified"] is False