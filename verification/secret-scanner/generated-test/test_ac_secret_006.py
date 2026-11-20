# hotdocs-criterion: sha256:2ea42f838854681d984a905577e39c69f97131be5b3b1562ca132694ae2af99a
import importlib.metadata
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SECRET_SCANNER_AC006_LOG"
STALE_ENV = "SECRET_SCANNER_AC006_STALE"
STALE_GATE_VERSION = "secret_scanner@0.0.1+detect-secrets.0.0.1"
STALE_RULE_ID = "stale-cached-sentinel"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "import dataclasses\n"
    "import json\n"
    "import os\n"
    "from datetime import datetime, timezone\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
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
    "def _field(value, name):\n"
    "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
    "\n"
    "\n"
    "def _log(op, gate_version):\n"
    "    path = os.environ.get(" + repr(LOG_ENV) + ")\n"
    "    if path:\n"
    "        with open(path, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(json.dumps({'op': op, 'gate_version': gate_version}) + '\\n')\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    gv = _field(cache_key, 'gate_version')\n"
    "    _log('get', gv)\n"
    "    stale = os.environ.get(" + repr(STALE_ENV) + ")\n"
    "    if stale and gv == stale:\n"
    "        payload = {\n"
    "            'scope': 'full',\n"
    "            'gate_version': stale,\n"
    "            'flagged': True,\n"
    "            'matches': [{'rule_id': " + repr(STALE_RULE_ID) + ", 'risk_tier': 'high',\n"
    "                         'file': 'stale.txt', 'line': 1}],\n"
    "            'allowed': [],\n"
    "            'unused_allowlist_entries': [],\n"
    "            'notified': False,\n"
    "            'notification_delivery_error': None,\n"
    "            'cache_hit': False,\n"
    "        }\n"
    "        return CachedResult(gate_type='secret_scanner', payload=payload,\n"
    "                            stored_at='2026-01-01T00:00:00Z')\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    gv = _field(cache_key, 'gate_version')\n"
    "    _log('put', gv)\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
)


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "README.txt").write_text("hello world\n", encoding="utf-8")
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")
    return repo_root


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv(STALE_ENV, raising=False)
    log_path = tmp_path / "cache_manager_calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    def no_network(*args, **kwargs):
        raise AssertionError("urlopen must not be called in this test")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    return log_path


def _expected_gate_version():
    v = importlib.metadata.version("detect-secrets")
    return "secret_scanner@3.1.0+detect-secrets." + v


def test_gate_version_matches_installed_detect_secrets(tmp_path, env):
    repo_root = _make_repo(tmp_path)
    expected = _expected_gate_version()

    result = secret_scanner.scan(repo_root)

    assert field(result, "gate_version") == expected
    assert result.to_dict()["gate_version"] == expected


def test_cached_result_with_different_gate_version_not_reused(tmp_path, env, monkeypatch):
    repo_root = _make_repo(tmp_path)
    monkeypatch.setenv(STALE_ENV, STALE_GATE_VERSION)
    expected = _expected_gate_version()
    assert expected != STALE_GATE_VERSION

    result = secret_scanner.scan(repo_root)

    calls = _read_log(env)
    gets = [c for c in calls if c["op"] == "get"]
    assert gets, "the stand-in cache-manager was never consulted"
    assert all(c["gate_version"] == expected for c in gets)

    assert field(result, "cache_hit") is False
    assert field(result, "gate_version") == expected
    assert field(result, "flagged") is False
    matches = field(result, "matches")
    assert not any(field(m, "rule_id") == STALE_RULE_ID for m in matches)