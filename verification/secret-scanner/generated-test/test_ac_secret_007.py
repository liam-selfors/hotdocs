# hotdocs-criterion: sha256:347a4c8232bfbbc9c5ddc125d587ee0a0cde73322447804e1b70d2ffe6810258
"""AC-SECRET-007 (covers R-SECRET-007).

Given any full scan
When it completes
Then exactly one SecretScanResult is produced
"""

import dataclasses
import io
import json
import os
import sys
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SECRET_SCAN_AC007_CACHE_LOG"


FAKE_CACHE_MANAGER = '''\
import dataclasses
import json
import os
from datetime import datetime, timezone

_LOG_ENV = "SECRET_SCAN_AC007_CACHE_LOG"

_REQUIRED = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def _log(record):
    path = os.environ.get(_LOG_ENV)
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\\n")


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0

    def __repr__(self):
        return "Miss()"


class SchemaValidationError(ValueError):
    pass


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def get(cache_key, *, repo_root=None):
    _log({"op": "get", "gate_version": _field(cache_key, "gate_version")})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_type = _field(result, "gate_type")
    payload = _field(result, "payload")
    gate_version = _field(cache_key, "gate_version") or ""
    if gate_type not in _REQUIRED:
        raise SchemaValidationError("unknown gate type")
    if gate_version.split("@", 1)[0] != gate_type:
        raise SchemaValidationError("gate type mismatch")
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a dict")
    missing = [k for k in _REQUIRED[gate_type] if k not in payload]
    if missing:
        raise SchemaValidationError("missing keys")
    _log({"op": "put", "gate_type": gate_type, "payload": payload})


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "hello.py").write_text(
        "def greet(name):\n    return 'hello ' + name\n", encoding="utf-8"
    )
    fake_dir = root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    (fake_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")
    return root


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "cache_calls.jsonl"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    webhook_calls = []

    def fake_urlopen(*args, **kwargs):
        webhook_calls.append((args, kwargs))
        raise urllib.error.URLError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.chdir(root)
    return root, log_path


def _assert_single_result_shape(result):
    assert result is not None, "scan() returned None"
    assert not isinstance(result, (list, tuple, set)), (
        f"scan() must return one SecretScanResult, got a {type(result).__name__}"
    )
    assert not hasattr(result, "__next__"), "scan() must not return an iterator"
    assert isinstance(result, dict) or dataclasses.is_dataclass(result), (
        f"scan() result is neither a dataclass nor a dict: {type(result)!r}"
    )

    if isinstance(result, dict):
        as_dict = result
    else:
        to_dict = getattr(result, "to_dict", None)
        assert callable(to_dict), "SecretScanResult must expose to_dict()"
        as_dict = to_dict()
    assert isinstance(as_dict, dict), "to_dict() must return one JSON object"

    assert _field(result, "scope") == "full"
    flagged = _field(result, "flagged")
    matches = _field(result, "matches")
    assert isinstance(flagged, bool)
    assert isinstance(matches, list)
    assert flagged == bool(matches)
    gate_version = _field(result, "gate_version")
    assert isinstance(gate_version, str) and gate_version.startswith("secret_scanner@")
    assert _field(result, "cache_hit") is False
    for key in ("scope", "gate_version", "flagged", "matches"):
        assert key in as_dict, f"to_dict() missing {key!r}"
    return as_dict


def test_full_scan_returns_exactly_one_result(env):
    root, log_path = env

    result = secret_scanner.scan(root)

    as_dict = _assert_single_result_shape(result)

    records = _read_log(log_path)
    puts = [r for r in records if r.get("op") == "put"]
    gets = [r for r in records if r.get("op") == "get"]

    assert len(gets) <= 1, f"expected at most one cache lookup per scan, got {len(gets)}"
    assert len(puts) == 1, (
        f"a fresh full scan must store exactly one result, got {len(puts)} puts"
    )
    stored = puts[0]
    assert stored.get("gate_type") == "secret_scanner"
    payload = stored.get("payload")
    assert isinstance(payload, dict)
    assert payload.get("scope") == "full"
    assert payload.get("flagged") == as_dict.get("flagged")
    assert payload.get("gate_version") == as_dict.get("gate_version")


def test_each_full_scan_produces_its_own_single_result(env):
    root, log_path = env

    first = secret_scanner.scan(root)
    _assert_single_result_shape(first)
    after_first = [r for r in _read_log(log_path) if r.get("op") == "put"]
    assert len(after_first) == 1

    second = secret_scanner.scan(root)
    _assert_single_result_shape(second)
    after_second = [r for r in _read_log(log_path) if r.get("op") == "put"]
    assert len(after_second) == 2, (
        "each full scan (always a cache miss here) must store exactly one result"
    )


def test_cli_full_scan_prints_exactly_one_json_result(env):
    root, _log_path = env

    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            code = secret_scanner.main(["--repo-root", str(root), "--format=json"])
        except SystemExit as exc:
            code = exc.code
    out = buf.getvalue().strip()

    assert code in (0, 1), f"unexpected exit code {code!r}; output: {out!r}"
    assert out, "json format must print the SecretScanResult"

    decoder = json.JSONDecoder()
    doc, end = decoder.raw_decode(out)
    assert out[end:].strip() == "", (
        "CLI full scan must print exactly one SecretScanResult document"
    )
    assert isinstance(doc, dict), "printed SecretScanResult must be one JSON object"
    assert doc.get("scope") == "full"
    assert isinstance(doc.get("matches"), list)
    assert doc.get("flagged") == bool(doc.get("matches"))
    assert (code == 1) == bool(doc.get("flagged"))