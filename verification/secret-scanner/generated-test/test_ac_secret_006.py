# hotdocs-criterion: sha256:12d8d9349e172660b8fea85f25c17988f2f431da8df793ad2e0424d87a1db4ad
import importlib.metadata
import json
import os
import textwrap
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SS_AC006_LOG"
STALE_GATE_VERSION = "secret_scanner@0.0.1+detect-secrets.0.0.1"
STALE_MARKER_FILE = "stale/marker.txt"
STALE_RULE_ID = "stale-marker"


FAKE_CACHE_MANAGER_SOURCE = textwrap.dedent(
    '''
    import json
    import os
    from dataclasses import dataclass
    from datetime import datetime, timezone

    STALE_GATE_VERSION = "secret_scanner@0.0.1+detect-secrets.0.0.1"


    class SchemaValidationError(ValueError):
        pass


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

        def __repr__(self):
            return "Miss()"


    REQUIRED = {
        "generator": ["component_id", "model", "prompt_version", "files"],
        "compiler": ["outputs", "gate_version", "summary"],
        "generated_test": ["component_id", "criterion_id", "model", "file"],
        "llm_judge": ["result", "rationale"],
        "license_scanner": [
            "component_id", "gate_version", "similarity_score", "blocked", "matches",
        ],
        "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
    }


    def now_iso():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


    def _field(obj, name):
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)


    def _log(record):
        path = os.environ.get("SS_AC006_LOG")
        if not path:
            return
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\\n")


    def _stale_payload():
        return {
            "scope": "full",
            "gate_version": STALE_GATE_VERSION,
            "flagged": True,
            "matches": [
                {
                    "rule_id": "stale-marker",
                    "risk_tier": "high",
                    "file": "stale/marker.txt",
                    "line": 1,
                }
            ],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }


    def get(cache_key, *, repo_root=None):
        sbh = _field(cache_key, "spec_bundle_hash")
        gih = _field(cache_key, "gate_inputs_hash")
        gv = _field(cache_key, "gate_version")
        _log({
            "op": "get",
            "spec_bundle_hash": sbh,
            "gate_inputs_hash": gih,
            "gate_version": gv,
        })
        # The store holds one entry under whatever spec_bundle_hash and
        # gate_inputs_hash the caller presents, but with a different
        # (stale) gate_version. Exact-key match semantics.
        stored_key = (sbh, gih, STALE_GATE_VERSION)
        if (sbh, gih, gv) == stored_key:
            return CachedResult(
                gate_type="secret_scanner",
                payload=_stale_payload(),
                stored_at=now_iso(),
            )
        return Miss()


    def put(cache_key, result, *, repo_root=None):
        gv = _field(cache_key, "gate_version") or ""
        gate_type = _field(result, "gate_type")
        payload = _field(result, "payload")
        expected_type = gv.split("@", 1)[0]
        if gate_type != expected_type or gate_type not in REQUIRED:
            raise SchemaValidationError("gate type mismatch")
        if not isinstance(payload, dict):
            raise SchemaValidationError("payload is not a mapping")
        for name in REQUIRED[gate_type]:
            if name not in payload:
                raise SchemaValidationError("missing payload key")
        _log({
            "op": "put",
            "gate_version": gv,
            "gate_type": gate_type,
            "payload_gate_version": payload.get("gate_version"),
            "stored_at": _field(result, "stored_at"),
        })


    def stats(*, repo_root=None):
        return {"entry_count": 1}
    '''
).lstrip()


def _f(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _expected_gate_version():
    v = importlib.metadata.version("detect-secrets")
    return "secret_scanner@3.1.0+detect-secrets." + v


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
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text(
        "Plain readme for a test fixture.\n", encoding="utf-8"
    )
    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    (fake_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8"
    )

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "cache_calls.jsonl"

    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    webhook_calls = []

    def _fake_urlopen(*args, **kwargs):
        webhook_calls.append((args, kwargs))
        raise OSError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    return repo_root, log_path


def test_gate_version_is_exact_and_includes_detect_secrets_version(repo):
    repo_root, log_path = repo
    expected = _expected_gate_version()

    result = secret_scanner.scan(repo_root)

    assert _f(result, "scope") == "full"
    assert _f(result, "gate_version") == expected

    records = _read_log(log_path)
    gets = [r for r in records if r.get("op") == "get"]
    assert gets, "scan did not consult the stand-in cache-manager"
    for rec in gets:
        assert rec.get("gate_version") == expected


def test_stored_result_under_different_gate_version_is_not_reused(repo):
    repo_root, log_path = repo
    expected = _expected_gate_version()
    assert expected != STALE_GATE_VERSION

    result = secret_scanner.scan(repo_root)

    # A fresh scan was performed, not the stale stored result.
    assert _f(result, "cache_hit") is False
    assert _f(result, "gate_version") == expected
    assert _f(result, "gate_version") != STALE_GATE_VERSION

    matches = _f(result, "matches") or []
    for m in matches:
        assert _f(m, "file") != STALE_MARKER_FILE
        assert _f(m, "rule_id") != STALE_RULE_ID

    records = _read_log(log_path)
    gets = [r for r in records if r.get("op") == "get"]
    puts = [r for r in records if r.get("op") == "put"]

    assert gets, "scan did not consult the stand-in cache-manager"
    for rec in gets:
        assert rec.get("gate_version") == expected
        assert rec.get("gate_version") != STALE_GATE_VERSION

    assert puts, "no fresh result was stored after the scan"
    for rec in puts:
        assert rec.get("gate_type") == "secret_scanner"
        assert rec.get("gate_version") == expected
        assert rec.get("payload_gate_version") == expected