# hotdocs-criterion: sha256:9efdfb8090058d7526b2a274c24d6f0ea50be7dbc0dc2a479e6d733e6c2e596b
"""AC-SECRET-004 / R-SECRET-004: compliance webhook notification for high-risk matches."""

import urllib.request
from pathlib import Path

import pytest

import secret_scanner


WEBHOOK_URL = "https://compliance.example.invalid/hook"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _aws_key():
    # Built from fragments so this test file itself never holds the full shape.
    return "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"


FAKE_CACHE_MANAGER_SOURCE = (
    "import dataclasses\n"
    "import datetime\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
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
    "    return datetime.datetime.now(datetime.timezone.utc).strftime("
    + repr("%Y-%m-%dT%H:%M:%SZ")
    + ")\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return " + repr({"entry_count": 0}) + "\n"
)


class _FakeResponse:
    status = 200

    def getcode(self):
        return 200

    def read(self, *args, **kwargs):
        return b"ok"

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def recorder(monkeypatch):
    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", fake_urlopen)
    return calls


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)
    (repo_root / "gen" / "foo").mkdir(parents=True)
    return repo_root


def _plant_secret(repo_root):
    target = repo_root / "gen" / "foo" / "config.py"
    target.write_text("aws_access_key_id = " + repr(_aws_key()) + "\n")
    return target


def _url_of(call):
    args, kwargs = call
    target = args[0] if args else kwargs.get("url")
    if isinstance(target, str):
        return target
    return getattr(target, "full_url", None)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_high_risk_match_sends_notification_independent_of_later_clean_scan(
    tmp_path, monkeypatch, recorder
):
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)
    repo_root = _make_repo(tmp_path)
    secret_file = _plant_secret(repo_root)

    result = secret_scanner.scan(repo_root)

    matches = field(result, "matches")
    assert any(m["risk_tier"] == "high" for m in matches), matches
    assert field(result, "flagged") is True
    assert field(result, "notified") is True
    assert len(recorder) == 1, recorder
    assert _url_of(recorder[0]) == WEBHOOK_URL
    assert field(result, "notification_delivery_error") is None

    # A later retry that scans clean never un-notifies the earlier notification.
    secret_file.write_text("value = 1\n")
    retry = secret_scanner.scan(repo_root)

    assert field(retry, "flagged") is False
    assert field(retry, "notified") is False
    assert len(recorder) == 1, recorder
    assert field(result, "notified") is True


def test_no_match_never_notifies(tmp_path, monkeypatch, recorder):
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", WEBHOOK_URL)
    repo_root = _make_repo(tmp_path)
    (repo_root / "gen" / "foo" / "plain.py").write_text("greeting = 'hello world'\n")
    (repo_root / "README.md").write_text("Nothing to see here.\n")

    result = secret_scanner.scan(repo_root)

    assert field(result, "matches") == []
    assert field(result, "flagged") is False
    assert field(result, "notified") is False
    assert recorder == []


def test_unset_webhook_flags_but_never_notifies(tmp_path, monkeypatch, recorder):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    repo_root = _make_repo(tmp_path)
    _plant_secret(repo_root)

    result = secret_scanner.scan(repo_root)

    matches = field(result, "matches")
    assert any(m["risk_tier"] == "high" for m in matches), matches
    assert field(result, "flagged") is True
    assert field(result, "notified") is False
    assert recorder == []