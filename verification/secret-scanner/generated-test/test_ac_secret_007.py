# hotdocs-criterion: sha256:c773227749a19c5d1b07f83d37eb96e9b9c12bf2b579f35faf226aa23fbf94fa
import dataclasses
import io
import json
import sys
import urllib.request
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import pytest

import secret_scanner


LOG_ENV = "SECRET_SCAN_AC007_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "import dataclasses\n"
    "import os\n"
    "from datetime import datetime, timezone\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    path = os.environ.get(" + repr(LOG_ENV) + ")\n"
    "    if path:\n"
    "        with open(path, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
    "    stored_at: str\n"
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
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "_REQUIRED = " + repr({
        "generator": ["component_id", "model", "prompt_version", "files"],
        "compiler": ["outputs", "gate_version", "summary"],
        "generated_test": ["component_id", "criterion_id", "model", "file"],
        "llm_judge": ["result", "rationale"],
        "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
        "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
    }) + "\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log('get')\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    gate_type = result['gate_type'] if isinstance(result, dict) else result.gate_type\n"
    "    payload = result['payload'] if isinstance(result, dict) else result.payload\n"
    "    key_gv = cache_key['gate_version'] if isinstance(cache_key, dict) else cache_key.gate_version\n"
    "    if gate_type not in _REQUIRED or str(key_gv).split('@')[0] != gate_type:\n"
    "        raise SchemaValidationError('gate type mismatch')\n"
    "    for k in _REQUIRED[gate_type]:\n"
    "        if not isinstance(payload, dict) or k not in payload:\n"
    "            raise SchemaValidationError('missing ' + k)\n"
    "    _log('put ' + str(gate_type))\n"
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


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "gen" / "cache-manager").mkdir(parents=True)
    (repo_root / "gen" / "cache-manager" / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8"
    )
    (repo_root / "src").mkdir()
    (repo_root / "src" / "hello.py").write_text(
        "def hello():\n    return 'hello world'\n", encoding="utf-8"
    )
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("webhook must not be called without a configured URL")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    return repo_root, log_path


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _assert_single_result(result):
    assert result is not None
    assert not isinstance(result, (list, tuple, set, dict))
    assert type(result).__name__ == "SecretScanResult"
    if hasattr(secret_scanner, "SecretScanResult"):
        assert isinstance(result, secret_scanner.SecretScanResult)
    assert dataclasses.is_dataclass(result)
    assert field(result, "scope") == "full"
    matches = field(result, "matches")
    assert isinstance(matches, list)
    assert field(result, "flagged") == (len(matches) > 0)
    as_dict = result.to_dict()
    assert isinstance(as_dict, dict)
    assert as_dict["scope"] == "full"
    json.dumps(as_dict)


def test_full_scan_produces_exactly_one_secret_scan_result(repo):
    repo_root, log_path = repo

    result = secret_scanner.scan(repo_root)

    _assert_single_result(result)

    # A fresh full scan stores exactly one result in the cache.
    puts = [l for l in _read_log(log_path) if l.startswith("put")]
    assert len(puts) == 1
    assert puts[0] == "put secret_scanner"


def test_full_scan_cli_json_prints_exactly_one_result_document(repo):
    repo_root, log_path = repo

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = secret_scanner.main(["--repo-root=" + str(repo_root), "--format=json"])

    assert code in (0, 1)
    text = out.getvalue().strip()
    # json.loads over the entire stdout succeeds only for a single document.
    doc = json.loads(text)
    assert isinstance(doc, dict)
    assert doc["scope"] == "full"
    assert isinstance(doc["matches"], list)
    assert doc["flagged"] == (len(doc["matches"]) > 0)
    assert code == (1 if doc["flagged"] else 0)

    puts = [l for l in _read_log(log_path) if l.startswith("put")]
    assert len(puts) == 1