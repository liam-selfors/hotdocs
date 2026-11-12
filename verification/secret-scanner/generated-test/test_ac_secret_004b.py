import hashlib
import sys
import textwrap
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


_FAKE_CACHE_MANAGER = textwrap.dedent(
    '''
    from dataclasses import dataclass
    from datetime import datetime, timezone


    class SchemaValidationError(ValueError):
        pass


    class Miss:
        def __eq__(self, other):
            return isinstance(other, Miss)

        def __hash__(self):
            return hash("Miss")


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


    _REQUIRED = {
        "generator": ["component_id", "model", "prompt_version", "files"],
        "compiler": ["outputs", "gate_version", "summary"],
        "generated_test": ["component_id", "criterion_id", "model", "file"],
        "llm_judge": ["result", "rationale"],
        "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
        "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
    }


    def get(cache_key, *, repo_root=None):
        return Miss()


    def put(cache_key, result, *, repo_root=None):
        gate_type = result.get("gate_type") if isinstance(result, dict) else getattr(result, "gate_type", None)
        payload = result.get("payload") if isinstance(result, dict) else getattr(result, "payload", None)
        key_version = cache_key.get("gate_version") if isinstance(cache_key, dict) else getattr(cache_key, "gate_version", None)
        if gate_type not in _REQUIRED:
            raise SchemaValidationError("unknown gate type")
        if str(key_version or "").split("@", 1)[0] != gate_type:
            raise SchemaValidationError("gate type mismatch")
        if not isinstance(payload, dict):
            raise SchemaValidationError("payload not a dict")
        for k in _REQUIRED[gate_type]:
            if k not in payload:
                raise SchemaValidationError("missing key")
        return None


    def now_iso():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


    def stats(*, repo_root=None):
        return {"entry_count": 0}
    '''
).lstrip()


class _FakeResponse:
    status = 200
    code = 200

    def read(self, *args, **kwargs):
        return b"{}"

    def getcode(self):
        return 200

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_ac_secret_004b_low_tier_blocking_match_notifies(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Fake cache-manager dependency (flat module shape), always a miss.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(_FAKE_CACHE_MANAGER, encoding="utf-8")

    # Build the hex literal at runtime so this test file itself embeds none.
    hex_value = hashlib.sha256(b"test").hexdigest()[:40]
    assert len(hex_value) == 40

    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "h.py").write_text('sha = "' + hex_value + '"\n', encoding="utf-8")

    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://example.invalid/compliance-hook")
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    calls = []

    def recorder(*args, **kwargs):
        calls.append((args, kwargs))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", recorder)

    result = secret_scanner.scan(repo_root)

    flagged = _field(result, "flagged")
    assert flagged is True, f"expected flagged true, got {flagged!r}"

    matches = _field(result, "matches") or []
    h_matches = [m for m in matches if _field(m, "file") == "gen/foo/h.py"]
    assert h_matches, f"expected a match in gen/foo/h.py, got {matches!r}"
    for m in h_matches:
        assert _field(m, "risk_tier") == "low", f"expected risk_tier low, got {m!r}"

    assert len(calls) == 1, f"expected webhook recorder called once, got {len(calls)} calls"