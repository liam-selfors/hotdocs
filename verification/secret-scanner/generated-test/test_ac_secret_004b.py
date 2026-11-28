# hotdocs-criterion: sha256:cbc753185a1e2d6f173d6204bb400ea8b05a00c508ca1cf523f479aff2f2e21c
"""AC-SECRET-004b: a low-risk match that blocks the merge still notifies.

Covers: R-SECRET-004
"""

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
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
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
    "    return {" + repr("entry_count") + ": 0}\n"
)


class _FakeResponse:
    status = 200
    code = 200

    def getcode(self):
        return 200

    def read(self, *args, **kwargs):
        return b""

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_ac_secret_004b_low_tier_blocking_match_notifies(tmp_path, monkeypatch):
    repo_root = tmp_path

    # Planted low-risk-tier finding that blocks the merge.
    target = repo_root / "gen" / "foo" / "h.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "sha = " + '"' + "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b" + '"' + "\n",
        encoding="utf-8",
    )

    # Deterministic cache-manager stand-in: always a miss.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:9/hook")

    calls = []

    def recorder(*args, **kwargs):
        calls.append((args, kwargs))
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", recorder)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", recorder)

    result = secret_scanner.scan(Path(repo_root))

    assert field(result, "flagged") is True

    matches = field(result, "matches")
    ours = [m for m in matches if field(m, "file") == "gen/foo/h.py"]
    assert ours, "expected a match in gen/foo/h.py, got " + repr(matches)
    assert any(field(m, "risk_tier") == "low" for m in ours), repr(ours)

    assert len(calls) == 1, "webhook recorder called " + repr(len(calls)) + " times"