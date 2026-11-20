# hotdocs-criterion: sha256:b1875a48883d6156bd60adafee418988c998dd0198c812c7e386c8db994d12b0
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

import pytest

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


VALID_HASH = "0" * 64

VALID_ENTRY = {
    "reference_id": "ref-001",
    "license_family": "GPL",
    "risk_tier": "high",
    "hashes": [VALID_HASH],
}


def _write_fake_cache_manager(repo_root):
    log_path = repo_root / "cache_calls.log"
    base = repo_root / "gen" / "cache-manager"
    base.mkdir(parents=True, exist_ok=True)
    src = (
        "from dataclasses import dataclass\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "    def __hash__(self):\n"
        "        return 0\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get')\n"
        "    return Miss()\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put')\n"
        "    return None\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 0}\n"
    )
    (base / "cache_manager.py").write_text(src, encoding="utf-8")


def _make_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    _write_fake_cache_manager(root)
    comp_dir = root / "gen" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "foo.py").write_text(
        "def add(a, b):\n"
        "    total = a + b\n"
        "    return total * 2 + 3 - 4 + 5\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    return monkeypatch


def test_missing_corpus_is_unreadable_and_blocks(tmp_path, clean_env):
    repo_root = _make_repo(tmp_path / "repo")
    missing = repo_root / "does-not-exist-corpus.json"
    assert not missing.exists()
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is False
    assert field(result, "reason") == "corpus-unreadable"
    assert field(result, "blocked") is True
    assert field(result, "similarity_score") is None
    assert field(result, "gate_version") == "license_scanner@4.0.0-corpus-unreadable"


INVALID_CORPORA = [
    ("not-json", "{this is not json"),
    ("json-list", json.dumps([VALID_ENTRY])),
    ("no-entries", json.dumps({"corpus_version": 1, "block_threshold": 0.7})),
    ("entries-not-list", json.dumps({"corpus_version": 1, "entries": "nope"})),
    ("version-x", json.dumps({"corpus_version": "x", "entries": [VALID_ENTRY]})),
    ("threshold-0", json.dumps({"block_threshold": 0, "entries": [VALID_ENTRY]})),
    ("threshold-1.5", json.dumps({"block_threshold": 1.5, "entries": [VALID_ENTRY]})),
    (
        "hashes-not-list",
        json.dumps({"entries": [dict(VALID_ENTRY, hashes=VALID_HASH)]}),
    ),
    (
        "risk-tier-severe",
        json.dumps({"entries": [dict(VALID_ENTRY, risk_tier="severe")]}),
    ),
]


@pytest.mark.parametrize(
    "label,content", INVALID_CORPORA, ids=[c[0] for c in INVALID_CORPORA]
)
def test_invalid_corpus_blocks(tmp_path, clean_env, label, content):
    repo_root = _make_repo(tmp_path / ("repo-" + label))
    corpus = repo_root / "corpus.json"
    corpus.write_text(content, encoding="utf-8")
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is False
    assert field(result, "reason") == "corpus-invalid"
    assert field(result, "blocked") is True
    assert field(result, "gate_version") == "license_scanner@4.0.0-corpus-invalid"


class _FakeResponse:
    status = 200

    def read(self, *args, **kwargs):
        return b"{}"

    def getcode(self):
        return 200

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _contains_pair(obj, key, value):
    if isinstance(obj, dict):
        if key in obj and obj[key] == value and type(obj[key]) is type(value):
            return True
        return any(_contains_pair(v, key, value) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_pair(v, key, value) for v in obj)
    return False


def _contains_value(obj, value):
    if isinstance(obj, dict):
        return any(_contains_value(v, value) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_value(v, value) for v in obj)
    return obj == value


def test_unreadable_corpus_notifies_webhook(tmp_path, clean_env):
    repo_root = _make_repo(tmp_path / "repo-notify")
    missing = repo_root / "does-not-exist-corpus.json"
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))
    clean_env.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:9/hook")

    calls = []

    def recorder(req, data=None, *args, **kwargs):
        body = data
        if body is None and hasattr(req, "data"):
            body = req.data
        if body is None:
            body = kwargs.get("data")
        calls.append(body)
        return _FakeResponse()

    clean_env.setattr(urllib.request, "urlopen", recorder)
    if hasattr(license_scanner, "urlopen"):
        clean_env.setattr(license_scanner, "urlopen", recorder)

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "blocked") is True
    assert field(result, "notified") is True
    assert len(calls) >= 1

    found = False
    for body in calls:
        if body is None:
            continue
        if isinstance(body, (bytes, bytearray)):
            text = bytes(body).decode("utf-8")
        else:
            text = str(body)
        try:
            payload = json.loads(text)
        except ValueError:
            payload = None
        if payload is not None:
            if _contains_pair(payload, "evaluated", False) and _contains_value(
                payload, "corpus-unreadable"
            ):
                found = True
                break
        else:
            if "evaluated" in text and "corpus-unreadable" in text:
                found = True
                break
    assert found, "webhook payload lacked evaluated false and the reason: " + repr(calls)