# hotdocs-criterion: sha256:6eeecb00bae034bad471a3a938d311d317099911a75792d72013adf2b21291be
import urllib.request
from pathlib import Path

import secret_scanner


HEX_VALUE = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SRC = (
    "from dataclasses import dataclass\n"
    "from typing import Any\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    payload = None\n"
    "\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "\n"
    "    def __hash__(self):\n"
    "        return 0\n"
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
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return " + repr("2026-01-01T00:00:00Z") + "\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {" + repr("entry_count") + ": 0}\n"
)


class _FakeResponse:
    status = 200

    def read(self, *args, **kwargs):
        return b""

    def getcode(self):
        return 200

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_ac_secret_004b_blocking_low_tier_match_notifies(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "h.py").write_text(
        "sha = " + repr(HEX_VALUE) + "\n", encoding="utf-8"
    )

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SRC, encoding="utf-8")

    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "https://example.invalid/hook")
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    calls = []

    def recorder(*args, **kwargs):
        calls.append((args, kwargs))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    result = secret_scanner.scan(Path(repo_root))

    assert field(result, "flagged") is True

    matches = field(result, "matches")
    h_matches = [m for m in matches if field(m, "file") == "gen/foo/h.py"]
    assert h_matches, "expected a match in gen/foo/h.py, got " + repr(matches)
    assert any(field(m, "risk_tier") == "low" for m in h_matches), repr(h_matches)

    assert len(calls) == 1, "webhook recorder called " + repr(len(calls)) + " times"