# hotdocs-criterion: sha256:1f05fa63c152c634354189d392c926a7e7fc0cb0b25ef385cf80b2bc28701caa
import json
import sys
import urllib.request
from pathlib import Path

import secret_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "import json\n"
    "import os\n"
    "from dataclasses import dataclass\n"
    "from pathlib import Path\n"
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
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "def _state():\n"
    "    return Path(os.environ['SS_FAKE_CACHE_STATE'])\n"
    "\n"
    "\n"
    "def _key(k):\n"
    "    names = ('spec_bundle_hash', 'gate_inputs_hash', 'gate_version', 'model_pin')\n"
    "    if isinstance(k, dict):\n"
    "        return [k[n] for n in names]\n"
    "    return [getattr(k, n) for n in names]\n"
    "\n"
    "\n"
    "def _log(name, record):\n"
    "    with open(_state() / name, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(record) + '\\n')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    key = _key(cache_key)\n"
    "    _log('get.log', key)\n"
    "    hits = _state() / 'hits.json'\n"
    "    if hits.is_file():\n"
    "        for entry in json.loads(hits.read_text(encoding='utf-8')):\n"
    "            if entry['key'] == key:\n"
    "                return CachedResult(gate_type='secret_scanner', payload=entry['payload'], stored_at='2026-01-01T00:00:00Z')\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    _log('put.log', {'key': _key(cache_key)})\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    import datetime\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
)


def _read_lines(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_secret_005_cache_hit_returns_cached_result_without_put(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise OSError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)

    repo_root = tmp_path / "repo"
    state = tmp_path / "state"
    repo_root.mkdir()
    state.mkdir()
    monkeypatch.setenv("SS_FAKE_CACHE_STATE", str(state))

    (repo_root / "specs").mkdir()
    (repo_root / "specs" / "README.md").write_text("hello specs\n", encoding="utf-8")
    (repo_root / "src").mkdir()
    (repo_root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    (fake_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")

    # Run 1: miss -> fresh scan, put called; learn the exact full-scan key.
    first = secret_scanner.scan(repo_root)
    assert field(first, "cache_hit") is False
    gets = _read_lines(state / "get.log")
    assert len(gets) >= 1
    key = gets[-1]
    assert key[3] == "none"
    assert key[0].startswith("sha256:")
    assert key[1].startswith("sha256:")
    assert key[2].startswith("secret_scanner@")
    assert len(_read_lines(state / "put.log")) >= 1
    fresh_matches = field(first, "matches")

    # Seed a cached result for that exact key, differing from a fresh scan.
    cached_matches = [
        {"rule_id": "Cached Fake Rule", "risk_tier": "high", "file": "gen/nowhere/cached.py", "line": 99}
    ]
    assert cached_matches != fresh_matches
    payload = {
        "scope": "full",
        "gate_version": key[2],
        "flagged": True,
        "matches": cached_matches,
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    (state / "hits.json").write_text(json.dumps([{"key": key, "payload": payload}]), encoding="utf-8")
    (state / "put.log").unlink()
    (state / "get.log").unlink()

    # Run 2: matching inputs -> cache hit reused.
    second = secret_scanner.scan(repo_root)

    gets2 = _read_lines(state / "get.log")
    assert gets2 and gets2[-1] == key
    assert field(second, "cache_hit") is True
    assert list(field(second, "matches")) == cached_matches
    assert _read_lines(state / "put.log") == []