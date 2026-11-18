# hotdocs-criterion: sha256:e87f027e7034777fbb55267815d43067beed50473559528124e69fb96a6c770b
import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


FAKE_CACHE_MANAGER = '''\
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


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
    if gate_type not in _REQUIRED:
        raise SchemaValidationError("unknown gate type")
    key_gate_version = cache_key.get("gate_version") if isinstance(cache_key, dict) else getattr(cache_key, "gate_version", "")
    if str(key_gate_version).split("@", 1)[0] != gate_type:
        raise SchemaValidationError("gate type mismatch")
    for name in _REQUIRED[gate_type]:
        present = (name in payload) if isinstance(payload, dict) else hasattr(payload, name)
        if not present:
            raise SchemaValidationError("missing payload key")
    return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


CLEAN_SOURCE = '''\
def add(a, b):
    return a + b


def greet(name):
    return "hello " + name
'''


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _build_repo(root: Path) -> Path:
    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")
    src_dir = root / "gen" / "foo"
    src_dir.mkdir(parents=True)
    (src_dir / "util.py").write_text(CLEAN_SOURCE, encoding="utf-8")
    (root / "README.md").write_text("A small clean repository.\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("webhook_configured", [True, False])
def test_clean_scan_is_not_notified(tmp_path, monkeypatch, webhook_configured):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    repo_root = _build_repo(tmp_path / "repo")
    monkeypatch.chdir(repo_root)

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    if webhook_configured:
        monkeypatch.setenv(
            "VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/compliance-hook"
        )
    else:
        monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))

        class _Resp:
            status = 200

            def read(self):
                return b""

            def getcode(self):
                return 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def close(self):
                pass

        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", fake_urlopen)

    result = secret_scanner.scan(repo_root)

    matches = _field(result, "matches")
    assert matches is not None
    assert list(matches) == [], f"expected a clean scan, got matches: {matches!r}"
    assert _field(result, "flagged") is False

    assert _field(result, "notified") is False
    assert _field(result, "notification_delivery_error") is None
    assert calls == [], "no compliance webhook call may be made for a clean scan"

    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        as_dict = to_dict()
        assert as_dict.get("notified") is False
        assert as_dict.get("notification_delivery_error") is None
        assert as_dict.get("flagged") is False