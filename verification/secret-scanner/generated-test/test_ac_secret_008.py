import json
from pathlib import Path

import secret_scanner


CACHE_MANAGER_SOURCE = r'''
import os

_LOG_PATH = os.environ.get("FAKE_CACHE_MANAGER_LOG")


def _record(event):
    if _LOG_PATH:
        with open(_LOG_PATH, "a") as f:
            f.write(event + "\n")


_record("loaded")


class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None, gate_version=None, model_pin=None):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


def get(cache_key, *, repo_root=None):
    _record("get")
    return None


def put(cache_key, result, *, repo_root=None):
    _record("put")
    return None
'''


def _write_cache_manager_fake(repo_root: Path) -> None:
    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True, exist_ok=True)
    (cache_manager_dir / "cache_manager.py").write_text(CACHE_MANAGER_SOURCE)


def test_precommit_scopes_to_files_and_skips_cache_manager(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    touched_dir = repo_root / "touched"
    touched_dir.mkdir()
    touched_file = touched_dir / "config.py"
    touched_file.write_text('TOKEN = "SECRET-1234"\n')

    untouched_dir = repo_root / "untouched"
    untouched_dir.mkdir()
    untouched_file = untouched_dir / "other.py"
    untouched_file.write_text('TOKEN = "SECRET-9999"\n')

    patterns_path = repo_root / "patterns.json"
    patterns_path.write_text(json.dumps({
        "version": "1.0.0",
        "rules": [
            {"rule_id": "test-secret", "risk_tier": "high", "pattern": "SECRET-[0-9]{4}"},
        ],
    }))

    cache_log_path = tmp_path / "cache_manager_invocations.log"
    _write_cache_manager_fake(repo_root)

    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(patterns_path))
    monkeypatch.setenv("FAKE_CACHE_MANAGER_LOG", str(cache_log_path))

    exit_code = secret_scanner.main([
        "precommit",
        "--files=touched/config.py",
        "--repo-root=" + str(repo_root),
        "--format=json",
    ])

    out = capsys.readouterr().out
    result = json.loads(out)

    assert result["scope"] == "precommit"
    assert result["flagged"] is True
    assert result["cache_hit"] is False

    matches = result["matches"]
    matched_files = {m["file"] for m in matches}
    assert matched_files == {"touched/config.py"}
    assert all(m["rule_id"] == "test-secret" for m in matches)

    assert exit_code == 1

    assert not cache_log_path.exists(), (
        "cache-manager fake was loaded or invoked during precommit scan, "
        "but R-SECRET-008 requires no cache-manager lookup to be attempted"
    )