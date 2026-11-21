# hotdocs-criterion: sha256:1d64c142d30508f9087d7a5ec9e509700d79da5222c756b18f58510f684980fd
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "HOTDOCS_TEST_CACHE_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = "\n".join([
    "import json",
    "import os",
    "import time",
    "from dataclasses import dataclass, asdict, is_dataclass",
    "",
    "",
    "class SchemaValidationError(ValueError):",
    "    pass",
    "",
    "",
    "@dataclass",
    "class CacheKey:",
    "    spec_bundle_hash: str",
    "    gate_inputs_hash: str",
    "    gate_version: str",
    "    model_pin: str",
    "",
    "",
    "@dataclass",
    "class CachedResult:",
    "    gate_type: str",
    "    payload: dict",
    "    stored_at: str",
    "",
    "",
    "class Miss:",
    "    def __eq__(self, other):",
    "        return isinstance(other, Miss)",
    "",
    "    def __hash__(self):",
    "        return 0",
    "",
    "",
    "def _log(entry):",
    "    path = os.environ.get(" + repr(LOG_ENV) + ")",
    "    if path:",
    "        with open(path, 'a') as fh:",
    "            fh.write(json.dumps(entry, default=str) + '\\n')",
    "",
    "",
    "def _plain(value):",
    "    if is_dataclass(value) and not isinstance(value, type):",
    "        return asdict(value)",
    "    return value",
    "",
    "",
    "def _read(value, name):",
    "    return value[name] if isinstance(value, dict) else getattr(value, name)",
    "",
    "",
    "def now_iso():",
    "    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())",
    "",
    "",
    "def get(cache_key, *, repo_root=None):",
    "    _log({'call': 'get', 'gate_version': _read(cache_key, 'gate_version')})",
    "    return Miss()",
    "",
    "",
    "def put(cache_key, result, *, repo_root=None):",
    "    gate_version = _read(cache_key, 'gate_version')",
    "    gate_type = _read(result, 'gate_type')",
    "    payload = _plain(_read(result, 'payload'))",
    "    if str(gate_version).split('@')[0] != gate_type:",
    "        raise SchemaValidationError('gate type mismatch')",
    "    if not isinstance(payload, dict):",
    "        raise SchemaValidationError('payload is not a mapping')",
    "    for key in ('scope', 'gate_version', 'flagged', 'matches'):",
    "        if key not in payload:",
    "            raise SchemaValidationError('missing payload key ' + key)",
    "    _log({",
    "        'call': 'put',",
    "        'gate_version': gate_version,",
    "        'gate_type': gate_type,",
    "        'payload': payload,",
    "        'stored_at': _read(result, 'stored_at'),",
    "    })",
    "    return None",
    "",
    "",
    "def stats(*, repo_root=None):",
    "    return {'entry_count': 0}",
    "",
])


@pytest.fixture
def clean_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text("A plain readme with nothing sensitive in it.\n")
    src = repo_root / "src"
    src.mkdir()
    (src / "hello.py").write_text("def greet(name):\n    return 'hello ' + name\n")

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "cache.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    webhook_log = log_dir / "webhook.log"

    def fake_urlopen(*args, **kwargs):
        with open(webhook_log, "a") as fh:
            fh.write("called\n")
        raise AssertionError("webhook must not be called for a clean scan")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return repo_root, log_path, webhook_log


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_clean_full_scan_still_produces_and_records_a_result(clean_repo):
    repo_root, log_path, webhook_log = clean_repo

    result = secret_scanner.scan(repo_root)

    # A result object is always returned, even with zero matches.
    assert result is not None
    assert not isinstance(result, dict)
    assert field(result, "scope") == "full"
    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []
    assert field(result, "cache_hit") is False
    assert field(result, "notified") is False
    assert field(result, "notification_delivery_error") is None
    gate_version = field(result, "gate_version")
    assert isinstance(gate_version, str) and gate_version.startswith("secret_scanner@")

    # The record handed to the provenance manifest is a full, serializable
    # SecretScanResult recording the clean outcome.
    record = result.to_dict()
    assert isinstance(record, dict)
    assert record["scope"] == "full"
    assert record["flagged"] is False
    assert record["matches"] == []
    assert record["gate_version"] == gate_version
    for key in ("allowed", "unused_allowlist_entries", "notified",
                "notification_delivery_error", "cache_hit"):
        assert key in record
    round_tripped = json.loads(json.dumps(record))
    assert round_tripped["flagged"] is False
    assert round_tripped["matches"] == []

    # The clean outcome is persisted, not dropped: a fresh scan puts its result.
    entries = read_log(log_path)
    puts = [e for e in entries if e.get("call") == "put"]
    assert len(puts) >= 1
    put = puts[-1]
    assert put["gate_type"] == "secret_scanner"
    assert str(put["gate_version"]).startswith("secret_scanner@")
    payload = put["payload"]
    assert payload["scope"] == "full"
    assert payload["flagged"] is False
    assert payload["matches"] == []
    assert isinstance(put["stored_at"], str) and put["stored_at"]

    assert not webhook_log.exists()


def test_clean_full_scan_cli_json_prints_the_record(clean_repo, capsys):
    repo_root, log_path, webhook_log = clean_repo

    code = secret_scanner.main(["--repo-root", str(repo_root), "--format=json"])
    out = capsys.readouterr().out

    assert code == 0
    document = json.loads(out)
    assert document["scope"] == "full"
    assert document["flagged"] is False
    assert document["matches"] == []
    assert str(document["gate_version"]).startswith("secret_scanner@")
    assert not webhook_log.exists()