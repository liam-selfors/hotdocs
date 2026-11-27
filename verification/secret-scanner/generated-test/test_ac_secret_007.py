# hotdocs-criterion: sha256:06499473bced04aeb27f2a42a2822757ba5168a5dea9efbe629af9234d59cf94
"""AC-SECRET-007: any full scan produces exactly one SecretScanResult (R-SECRET-007)."""

import dataclasses
import io
import json
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

import secret_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "import os\n"
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
    "    payload: dict\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    path = os.environ.get('FAKE_CACHE_LOG')\n"
    "    if path:\n"
    "        with open(path, 'a') as fh:\n"
    "            fh.write(line + chr(10))\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log('get')\n"
    "    if os.environ.get('FAKE_CACHE_MODE') == 'hit':\n"
    "        payload = dict(\n"
    "            scope='full',\n"
    "            gate_version=cache_key.gate_version,\n"
    "            flagged=False,\n"
    "            matches=[],\n"
    "            allowed=[],\n"
    "            unused_allowlist_entries=[],\n"
    "            notified=False,\n"
    "            notification_delivery_error=None,\n"
    "            cache_hit=False,\n"
    "        )\n"
    "        return CachedResult(gate_type='secret_scanner', payload=payload, stored_at='2026-01-01T00:00:00Z')\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    _log('put')\n"
    "    return None\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return dict(entry_count=0)\n"
)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True)
    (fake_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)
    (repo_root / "README.md").write_text("A plain readme with nothing secret in it.\n")
    (repo_root / "app.py").write_text("def add(a, b):\n    return a + b\n")

    log_path = tmp_path / "cache_calls.log"
    monkeypatch.setenv("FAKE_CACHE_LOG", str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("no webhook call expected")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    monkeypatch.chdir(tmp_path)
    return repo_root


def _assert_single_result(result):
    assert not isinstance(result, (list, tuple, set, dict))
    assert type(result).__name__ == "SecretScanResult"
    assert dataclasses.is_dataclass(result)
    as_dict = result.to_dict()
    assert isinstance(as_dict, dict)
    assert field(result, "scope") == "full"
    assert as_dict["scope"] == "full"
    assert isinstance(field(result, "flagged"), bool)
    assert isinstance(field(result, "matches"), list)


@pytest.mark.parametrize("mode", ["miss", "hit"])
def test_full_scan_returns_exactly_one_secret_scan_result(repo, monkeypatch, mode):
    monkeypatch.setenv("FAKE_CACHE_MODE", mode)
    result = secret_scanner.scan(repo)
    _assert_single_result(result)


@pytest.mark.parametrize("prefix", [[], ["secret-scan"]])
def test_cli_full_scan_json_prints_exactly_one_result_document(repo, monkeypatch, prefix):
    monkeypatch.setenv("FAKE_CACHE_MODE", "miss")
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = secret_scanner.main(prefix + ["--repo-root", str(repo), "--format=json"])
    assert code in (0, 1)
    text = out.getvalue()
    # json.loads on the full stdout fails if there is more than one document.
    document = json.loads(text)
    assert isinstance(document, dict)
    assert document["scope"] == "full"
    assert "flagged" in document
    assert isinstance(document["matches"], list)
    assert code == (1 if document["flagged"] else 0)