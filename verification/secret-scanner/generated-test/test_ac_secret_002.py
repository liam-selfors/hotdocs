"""AC-SECRET-002 (covers R-SECRET-002).

Given a full scan with at least one match
When secret-scan completes
Then flagged is true and the merge is reported as blocked
"""

import contextlib
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SECRET_AC002_FAKE_CACHE_LOG"

# Fake cache-manager, written as a flat module under the temporary repo_root.
# It embeds no long random-looking literal and no temporary-directory path:
# its invocation log location is read from an environment variable.
FAKE_CACHE_MANAGER = '''\
import json
import os
import time
from dataclasses import dataclass
from typing import Any


class SchemaValidationError(ValueError):
    pass


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("cache_manager.Miss")

    def __repr__(self):
        return "Miss()"


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


_REQUIRED = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _log(record):
    path = os.environ.get("''' + LOG_ENV + '''")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def get(cache_key, *, repo_root=None):
    _log({"op": "get", "gate_version": str(_field(cache_key, "gate_version"))})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_type = _field(result, "gate_type")
    payload = _field(result, "payload")
    key_gate_version = str(_field(cache_key, "gate_version") or "")
    key_gate_type = key_gate_version.split("@", 1)[0]
    if gate_type not in _REQUIRED:
        raise SchemaValidationError("unknown gate_type")
    if gate_type != key_gate_type:
        raise SchemaValidationError("gate_type does not match cache key")
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload is not a mapping")
    missing = [k for k in _REQUIRED[gate_type] if k not in payload]
    if missing:
        raise SchemaValidationError("payload missing keys")
    _log({"op": "put", "gate_type": gate_type, "flagged": payload.get("flagged")})
    return None


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _planted_key():
    # Assembled at runtime so this test file itself carries no detectable literal.
    return "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"


def _read_log(log_path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _run_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            rc = secret_scanner.main(argv)
        except SystemExit as exc:
            rc = exc.code
    if rc is None:
        rc = 0
    return rc, buf.getvalue()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    root = tmp_path / "repo"
    root.mkdir()

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "cache_calls.jsonl"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    app_dir = root / "app"
    app_dir.mkdir()
    (app_dir / "settings.py").write_text(
        'AWS_ACCESS_KEY_ID = "' + _planted_key() + '"\n', encoding="utf-8"
    )

    # No compliance webhook configured; and never let a real POST escape.
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    webhook_calls = []

    def _fake_urlopen(*args, **kwargs):
        webhook_calls.append((args, kwargs))
        raise AssertionError("compliance webhook must not be POSTed when unconfigured")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.chdir(root)

    return {"root": root, "log_path": log_path, "webhook_calls": webhook_calls}


def _assert_planted_match(matches):
    assert isinstance(matches, list)
    assert len(matches) >= 1
    files = [_get(m, "file") for m in matches]
    assert "app/settings.py" in files, files


def test_full_scan_with_match_is_flagged(repo):
    result = secret_scanner.scan(repo["root"])

    assert _get(result, "scope") == "full"
    matches = _get(result, "matches")
    _assert_planted_match(matches)
    assert _get(result, "flagged") is True

    # If the fresh result was cached, it was cached as flagged.
    puts = [r for r in _read_log(repo["log_path"]) if r.get("op") == "put"]
    for rec in puts:
        assert rec.get("gate_type") == "secret_scanner"
        assert rec.get("flagged") is True


def test_full_scan_cli_json_reports_merge_blocked(repo):
    rc, out = _run_main(["--repo-root", str(repo["root"]), "--format", "json"])

    # Exit code 1 means flagged: the merge is blocked.
    assert rc == 1, out
    payload = json.loads(out)
    assert _get(payload, "scope") == "full"
    assert _get(payload, "flagged") is True
    _assert_planted_match(_get(payload, "matches"))


def test_full_scan_cli_text_reports_flagged(repo):
    rc, out = _run_main(["secret-scan", "--repo-root=" + str(repo["root"])])

    assert rc == 1, out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines, out
    assert "FLAGGED" in out
    assert not any(ln.strip() == "CLEAN" for ln in lines)
    # One line per match follows the verdict line.
    assert len(lines) >= 2