# hotdocs-criterion: sha256:a94f77e444f47aed149836648808063842238acf7c1ae0a9542c8a415fcb30d6
"""AC-SECRET-006: gate_version is secret_scanner@3.1.0+detect-secrets.<V>,
and a cached result under a different gate_version is never reused."""

import importlib.metadata
import json
import os
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SECRET_SCANNER_AC006_LOG"
STALE_GATE_VERSION = "secret_scanner@0.0.0+detect-secrets.0.0.0"
STALE_MARKER_RULE = "stale-cached-marker"

STALE_PAYLOAD = {
    "scope": "full",
    "gate_version": STALE_GATE_VERSION,
    "flagged": True,
    "matches": [
        {
            "rule_id": STALE_MARKER_RULE,
            "risk_tier": "high",
            "file": "stale.py",
            "line": 1,
        }
    ],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def expected_gate_version():
    return "secret_scanner@3.1.0+detect-secrets." + importlib.metadata.version(
        "detect-secrets"
    )


def fake_cache_manager_source(hold_stale):
    lines = [
        "import json",
        "import os",
        "from dataclasses import dataclass",
        "from datetime import datetime, timezone",
        "",
        "STALE_GATE_VERSION = " + repr(STALE_GATE_VERSION),
        "STALE_PAYLOAD = " + repr(STALE_PAYLOAD),
        "HOLD_STALE = " + repr(bool(hold_stale)),
        "LOG_ENV = " + repr(LOG_ENV),
        "REQUIRED = {",
        "    'generator': ['component_id', 'model', 'prompt_version', 'files'],",
        "    'compiler': ['outputs', 'gate_version', 'summary'],",
        "    'generated_test': ['component_id', 'criterion_id', 'model', 'file'],",
        "    'llm_judge': ['result', 'rationale'],",
        "    'license_scanner': ['component_id', 'gate_version', 'similarity_score', 'blocked', 'matches'],",
        "    'secret_scanner': ['scope', 'gate_version', 'flagged', 'matches'],",
        "}",
        "",
        "",
        "class SchemaValidationError(ValueError):",
        "    pass",
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
        "def _field(value, name):",
        "    return value[name] if isinstance(value, dict) else getattr(value, name)",
        "",
        "",
        "def _log(entry):",
        "    path = os.environ.get(LOG_ENV)",
        "    if path:",
        "        with open(path, 'a', encoding='utf-8') as fh:",
        "            fh.write(json.dumps(entry) + '\\n')",
        "",
        "",
        "def now_iso():",
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')",
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    gv = _field(cache_key, 'gate_version')",
        "    _log({'op': 'get', 'gate_version': gv})",
        "    # Holds a stale entry under every spec_bundle_hash/gate_inputs_hash,",
        "    # but only under the stale gate_version.",
        "    if HOLD_STALE and gv == STALE_GATE_VERSION:",
        "        return CachedResult(gate_type='secret_scanner', payload=dict(STALE_PAYLOAD), stored_at='2026-01-01T00:00:00Z')",
        "    return Miss()",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    gv = _field(cache_key, 'gate_version')",
        "    gate_type = _field(result, 'gate_type')",
        "    payload = _field(result, 'payload')",
        "    if gate_type not in REQUIRED:",
        "        raise SchemaValidationError('unknown gate_type')",
        "    if str(gv).split('@', 1)[0] != gate_type:",
        "        raise SchemaValidationError('gate_type mismatch')",
        "    for key in REQUIRED[gate_type]:",
        "        if key not in payload:",
        "            raise SchemaValidationError('missing ' + key)",
        "    _log({'op': 'put', 'gate_version': gv, 'payload_gate_version': payload.get('gate_version')})",
        "",
        "",
        "def stats(*, repo_root=None):",
        "    return {'entry_count': 0}",
        "",
    ]
    return "\n".join(lines)


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "README.txt").write_text("hello world\n", encoding="utf-8")
    log_path = tmp_path / "cache_log.jsonl"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    import urllib.request

    def _no_network(*args, **kwargs):
        raise AssertionError("no webhook expected")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    monkeypatch.chdir(repo_root)
    return repo_root, log_path


def write_fake(repo_root, hold_stale):
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(
        fake_cache_manager_source(hold_stale), encoding="utf-8"
    )


def read_log(log_path):
    if not log_path.is_file():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_gate_version_is_exact(env):
    repo_root, _log_path = env
    write_fake(repo_root, hold_stale=False)

    result = secret_scanner.scan(repo_root)

    assert field(result, "gate_version") == expected_gate_version()
    assert result.to_dict()["gate_version"] == expected_gate_version()


def test_stale_gate_version_result_not_reused(env):
    repo_root, log_path = env
    write_fake(repo_root, hold_stale=True)

    result = secret_scanner.scan(repo_root)

    assert field(result, "cache_hit") is False
    assert field(result, "gate_version") == expected_gate_version()
    rule_ids = [field(m, "rule_id") for m in field(result, "matches")]
    assert STALE_MARKER_RULE not in rule_ids
    assert field(result, "flagged") is False

    entries = read_log(log_path)
    gets = [e for e in entries if e["op"] == "get"]
    puts = [e for e in entries if e["op"] == "put"]
    assert gets, "scan should have looked up the cache"
    assert all(e["gate_version"] == expected_gate_version() for e in gets)
    assert puts, "a fresh scan should have stored its result"
    assert all(e["gate_version"] == expected_gate_version() for e in puts)