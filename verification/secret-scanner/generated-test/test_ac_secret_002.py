# hotdocs-criterion: sha256:6e6a2418ba61522903b094353c5b5aabb67f65b82c4a8c986ae7a0e85de68ce4
"""AC-SECRET-002: a full scan with at least one match is flagged, and main exits 1."""

import json
from pathlib import Path

import secret_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "from dataclasses import dataclass\n"
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
    "        return hash('Miss')\n"
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
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return " + repr({"entry_count": 0}) + "\n"
)


def _build_repo(repo_root: Path) -> None:
    # Fake cache-manager that always misses, so each call performs a fresh scan.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

    # Planted AWS access key, assembled at runtime so this test file holds no
    # detectable literal.
    planted = "AKIA" + "Q" * 16
    src_dir = repo_root / "gen" / "foo"
    src_dir.mkdir(parents=True)
    (src_dir / "config.py").write_text("aws_key = " + repr(planted) + "\n")


def test_ac_secret_002_flagged_scan_and_main_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("webhook must not be called when no URL is configured")

    monkeypatch.setattr("urllib.request.urlopen", _no_network)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    result = secret_scanner.scan(repo_root)
    assert len(field(result, "matches")) >= 1
    assert field(result, "flagged") is True

    capsys.readouterr()
    code = secret_scanner.main(["--repo-root", str(repo_root), "--format=json"])
    out = capsys.readouterr().out
    doc = json.loads(out)
    assert doc["flagged"] is True
    assert len(doc["matches"]) >= 1
    assert code == 1