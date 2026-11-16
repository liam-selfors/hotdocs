"""AC-SECRET-003 (covers R-SECRET-003).

Given a full scan with zero matches, when secret-scan completes, then a
SecretScanResult recording the clean outcome is still produced and recorded:
a clean result is never silently dropped. "Absence of a flag MUST NOT mean
absence of a record."

These tests are written only against the documented interface/ contracts:

- `secret_scanner.scan(repo_root)` returns a `SecretScanResult` whose
  `to_dict()` is the JSON shape. That shape is what `ProvenanceInputs`
  carries as `secret_scan_result`, and that field is always populated.
- After a fresh scan, `scan` persists the result's fields through
  `cache-manager`'s `put` as a `CachedResult` with `gate_type`
  `"secret_scanner"`. The `cache-manager` used here is a flat-module fake
  under `<repo_root>/gen/cache-manager/`, and it logs every call to a file
  outside the scanned tree.
- The CLI's `--format=json` prints the `SecretScanResult` and exits 0 when
  the scan is clean.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


CACHE_LOG_ENV = "SECRET_SCAN_TEST_CACHE_LOG"

DOCUMENTED_RESULT_KEYS = (
    "scope",
    "gate_version",
    "flagged",
    "matches",
    "allowed",
    "unused_allowlist_entries",
    "notified",
    "notification_delivery_error",
    "cache_hit",
)

# Fake cache-manager, matching comp-cache-manager's documented interface.
# It lives inside the scanned repo, so it carries no long random-looking
# literal and no temp path. Its log location comes from an environment
# variable.
FAKE_CACHE_MANAGER_SOURCE = '''\
import json
import os
from dataclasses import dataclass, asdict, is_dataclass
from datetime import datetime, timezone


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


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


_SCAN_PAYLOAD_KEYS = ("scope", "gate_version", "flagged", "matches")


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _plain(value):
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    return value


def _log(record):
    target = os.environ.get("SECRET_SCAN_TEST_CACHE_LOG")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\\n")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(cache_key, *, repo_root=None):
    _log({"op": "get", "gate_version": _field(cache_key, "gate_version")})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    key_version = _field(cache_key, "gate_version") or ""
    key_type = str(key_version).split("@")[0]
    gate_type = _field(result, "gate_type")
    payload = _plain(_field(result, "payload"))
    if gate_type != key_type:
        raise SchemaValidationError("gate_type does not match cache key")
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a mapping")
    if gate_type == key_type and key_type.endswith("_scanner") and key_type.startswith("sec"):
        missing = [k for k in _SCAN_PAYLOAD_KEYS if k not in payload]
        if missing:
            raise SchemaValidationError("payload missing keys: " + ",".join(missing))
    _log({
        "op": "put",
        "gate_version": key_version,
        "gate_type": gate_type,
        "payload": payload,
        "stored_at": _field(result, "stored_at"),
    })


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _as_dict(result):
    if isinstance(result, dict):
        return result
    to_dict = getattr(result, "to_dict", None)
    assert callable(to_dict), "SecretScanResult must expose to_dict()"
    data = to_dict()
    assert isinstance(data, dict), "to_dict() must return a dict"
    return data


def _read_log(log_path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


@pytest.fixture
def clean_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text(
        "A small clean repository.\nNothing sensitive lives here.\n",
        encoding="utf-8",
    )
    src_dir = repo_root / "src"
    src_dir.mkdir()
    (src_dir / "greeting.py").write_text(
        "def greet(name):\n    return 'Hello, ' + name\n",
        encoding="utf-8",
    )

    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    (fake_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8"
    )

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    cache_log = log_dir / "cache_calls.jsonl"
    webhook_log = log_dir / "webhook_calls.jsonl"

    monkeypatch.setenv(CACHE_LOG_ENV, str(cache_log))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def fake_urlopen(*args, **kwargs):
        with open(webhook_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"called": True}) + "\n")
        raise OSError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.chdir(repo_root)

    return {
        "repo_root": repo_root,
        "cache_log": cache_log,
        "webhook_log": webhook_log,
    }


def test_clean_full_scan_still_produces_a_recordable_result(clean_repo):
    repo_root = clean_repo["repo_root"]

    result = secret_scanner.scan(repo_root)

    assert result is not None, "a clean scan must still produce a result"
    assert not isinstance(result, dict) or result, "result must not be empty"

    # The clean outcome is recorded on the result object itself.
    assert _get(result, "scope") == "full"
    assert _get(result, "flagged") is False
    assert list(_get(result, "matches") or []) == []
    assert _get(result, "notified") is False
    assert _get(result, "notification_delivery_error") is None
    assert _get(result, "cache_hit") is False
    gate_version = _get(result, "gate_version")
    assert isinstance(gate_version, str) and gate_version

    # to_dict() is the JSON shape, the one ProvenanceInputs carries as
    # secret_scan_result. It must hold every documented field and serialize.
    data = _as_dict(result)
    for key in DOCUMENTED_RESULT_KEYS:
        assert key in data, "SecretScanResult.to_dict() missing %r" % key
    assert data["scope"] == "full"
    assert data["flagged"] is False
    assert data["matches"] == []
    assert data["gate_version"] == gate_version

    # Embed it in a ProvenanceInputs-shaped record and round-trip it through
    # JSON, the way it is recorded in the provenance manifest. The clean
    # outcome must survive intact and must not be absent or null.
    provenance_inputs = {
        "component_id": "comp-example",
        "generation_result": {
            "component_id": "comp-example",
            "spec_bundle_hash": "sha256:example",
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"example.py": "print('hi')\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification_report": None,
        "license_scan_result": None,
        "secret_scan_result": data,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"secret_scanner": gate_version},
    }
    restored = json.loads(json.dumps(provenance_inputs))
    recorded = restored["secret_scan_result"]
    assert recorded is not None
    assert recorded["flagged"] is False
    assert recorded["matches"] == []
    assert recorded["scope"] == "full"
    assert recorded["gate_version"] == gate_version

    # No notification is due for a clean scan with no webhook configured.
    assert not clean_repo["webhook_log"].exists()


def test_clean_full_scan_result_is_persisted_not_dropped(clean_repo):
    repo_root = clean_repo["repo_root"]

    result = secret_scanner.scan(repo_root)
    assert _get(result, "flagged") is False
    assert _get(result, "cache_hit") is False

    records = _read_log(clean_repo["cache_log"])
    puts = [r for r in records if r.get("op") == "put"]
    assert puts, (
        "a clean, fresh full scan must still persist its result record "
        "(cache-manager put was never called)"
    )

    put = puts[-1]
    assert put["gate_type"] == "secret_scanner"
    assert str(put["gate_version"]).startswith("secret_scanner@")
    payload = put["payload"]
    assert isinstance(payload, dict)
    assert payload.get("scope") == "full"
    assert payload.get("flagged") is False
    assert payload.get("matches") == []
    assert payload.get("gate_version") == _get(result, "gate_version")
    stored_at = put.get("stored_at")
    assert isinstance(stored_at, str) and stored_at


def test_cli_json_prints_clean_result_and_exits_zero(clean_repo, capsys):
    repo_root = clean_repo["repo_root"]

    code = secret_scanner.main(
        ["--repo-root=%s" % str(repo_root), "--format=json"]
    )
    out = capsys.readouterr().out

    assert code == 0
    parsed = json.loads(out.strip())
    assert isinstance(parsed, dict)
    for key in DOCUMENTED_RESULT_KEYS:
        assert key in parsed, "printed SecretScanResult missing %r" % key
    assert parsed["scope"] == "full"
    assert parsed["flagged"] is False
    assert parsed["matches"] == []