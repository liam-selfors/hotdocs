# hotdocs-criterion: sha256:83fe38ad68fd7cd4497ec734b4a53168eaaee3434ca13d1afb3d0c3f880abdd8
"""AC-SECRET-005: a cache hit on the exact full-scan key is reused verbatim.

Given cache-manager already holds a result for the exact full-scan cache key,
when a full scan runs with matching inputs, the cached result is returned with
cache_hit true and exactly the cached matches (even though a fresh scan of the
current files would find something different), and put is not called.
"""

import json
import sys
from pathlib import Path

import secret_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


CACHED_MATCHES = [
    {
        "rule_id": "AWS Access Key",
        "risk_tier": "high",
        "file": "gen/foo/config.py",
        "line": 12,
    }
]


# Fake cache-manager, flat-module shape. It reads its log/state directory from
# an environment variable so it embeds no temporary-directory path.
FAKE_CACHE_MANAGER = (
    "import json\n"
    "import os\n"
    "from dataclasses import dataclass, asdict\n"
    "from datetime import datetime, timezone\n"
    "from pathlib import Path\n"
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
    "def _dir():\n"
    "    return Path(os.environ['SECRET_TEST_CACHE_LOG_DIR'])\n"
    "\n"
    "\n"
    "def _f(value, name):\n"
    "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
    "\n"
    "\n"
    "def _key_dict(cache_key):\n"
    "    names = ['spec_bundle_hash', 'gate_inputs_hash', 'gate_version', 'model_pin']\n"
    "    return {n: _f(cache_key, n) for n in names}\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(_dir() / 'calls.log', 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    key = _key_dict(cache_key)\n"
    "    _log('get ' + json.dumps(key, sort_keys=True))\n"
    "    stored = _dir() / 'stored_key.json'\n"
    "    if not stored.is_file():\n"
    "        return Miss()\n"
    "    if json.loads(stored.read_text(encoding='utf-8')) != key:\n"
    "        return Miss()\n"
    "    payload = json.loads((_dir() / 'cached_payload.json').read_text(encoding='utf-8'))\n"
    "    payload['gate_version'] = key['gate_version']\n"
    "    return CachedResult(gate_type='secret_scanner', payload=payload,\n"
    "                        stored_at='2026-01-01T00:00:00Z')\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    key = _key_dict(cache_key)\n"
    "    _log('put ' + json.dumps(key, sort_keys=True))\n"
    "    (_dir() / 'stored_key.json').write_text(json.dumps(key, sort_keys=True), encoding='utf-8')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 1 if (_dir() / 'stored_key.json').is_file() else 0}\n"
)


def _build_repo(repo_root: Path):
    (repo_root / "specs" / "components" / "foo").mkdir(parents=True)
    (repo_root / "specs" / "components" / "foo" / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A plain component.\n",
        encoding="utf-8",
    )
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "app.py").write_text(
        "def hello():\n    return 'hello'\n", encoding="utf-8"
    )
    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    (fake_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")


def _read_calls(log_dir: Path):
    log = log_dir / "calls.log"
    if not log.is_file():
        return []
    return [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_cache_hit_on_exact_key_is_reused_without_put(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("SECRET_TEST_CACHE_LOG_DIR", str(log_dir))

    _build_repo(repo_root)

    # Phase 1: no entry yet -> a fresh scan, which puts under the exact key.
    first = secret_scanner.scan(repo_root)
    assert field(first, "cache_hit") is False
    assert list(field(first, "matches")) == []
    first_calls = _read_calls(log_dir)
    assert any(c.startswith("put ") for c in first_calls), first_calls
    stored_key = json.loads((log_dir / "stored_key.json").read_text(encoding="utf-8"))
    assert stored_key["model_pin"] == "none"
    assert stored_key["spec_bundle_hash"].startswith("sha256:")
    assert stored_key["gate_inputs_hash"].startswith("sha256:")

    # The cache now holds, for that exact key, a result that differs from
    # what a fresh scan of the (clean) current files would find.
    cached_payload = {
        "scope": "full",
        "gate_version": stored_key["gate_version"],
        "flagged": True,
        "matches": CACHED_MATCHES,
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    (log_dir / "cached_payload.json").write_text(
        json.dumps(cached_payload), encoding="utf-8"
    )
    (log_dir / "calls.log").write_text("", encoding="utf-8")

    # Phase 2: same inputs -> same key -> hit, reused verbatim, no put.
    second = secret_scanner.scan(repo_root)
    second_calls = _read_calls(log_dir)

    gets = [c for c in second_calls if c.startswith("get ")]
    assert gets, second_calls
    assert json.loads(gets[0][len("get "):]) == stored_key
    assert not any(c.startswith("put ") for c in second_calls), second_calls

    assert field(second, "cache_hit") is True
    assert list(field(second, "matches")) == CACHED_MATCHES
    assert field(second, "flagged") is True
    assert field(second, "scope") == "full"

    as_dict = second.to_dict()
    assert as_dict["cache_hit"] is True
    assert as_dict["matches"] == CACHED_MATCHES