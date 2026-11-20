# hotdocs-criterion: sha256:79e7d45c5cb685a6466301b00fbd3c41c475006abfee90f4fe74fb2e2b251059
import hashlib
import json
from pathlib import Path

import pytest

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_BODY = (
    "import dataclasses\n"
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
    "        return 0\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(LOG_PATH, 'a') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log('get')\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    _log('put')\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    import datetime\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
)


FOO_SOURCE = (
    "def compute_total(alpha, beta, gamma, delta):\n"
    "    result = alpha + beta + gamma + delta\n"
    "    values = [alpha, beta, gamma, delta, 42, 7, 99]\n"
    "    for item in values:\n"
    "        result = result + item * 3\n"
    "    return result\n"
    "\n"
    "\n"
    "def another_function(x, y, z):\n"
    "    return compute_total(x, y, z, 12345)\n"
)


def _make_repo(tmp_path, name):
    repo_root = tmp_path / name
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "foo.py").write_text(FOO_SOURCE)
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    log_path = tmp_path / (name + "-cache.log")
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_CACHE_BODY
    (cache_dir / "cache_manager.py").write_text(source)
    return repo_root


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)


def test_no_reference_corpus(tmp_path, monkeypatch):
    repo_root = _make_repo(tmp_path, "repo_unset")
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is False
    assert field(result, "reason") == "no-reference-corpus"
    assert field(result, "similarity_score") is None
    assert field(result, "block_threshold") is None
    assert list(field(result, "matches")) == []
    assert field(result, "blocked") is False
    assert field(result, "gate_version") == "license_scanner@4.0.0-no-reference-corpus"


def test_empty_entries_corpus_is_invalid(tmp_path, monkeypatch):
    repo_root = _make_repo(tmp_path, "repo_empty")
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps({"corpus_version": 1, "block_threshold": 0.7, "entries": []}))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is False
    assert field(result, "reason") == "corpus-invalid"
    assert field(result, "blocked") is True


def test_valid_corpus_no_shared_windows(tmp_path, monkeypatch):
    repo_root = _make_repo(tmp_path, "repo_valid")
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.7,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": [hashlib.sha256(b"definitely-not-a-window").hexdigest()],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus))
    corpus_bytes = corpus_path.read_bytes()
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is True
    assert field(result, "reason") is None
    score = field(result, "similarity_score")
    assert score is not None
    assert isinstance(score, (int, float)) and not isinstance(score, bool)
    assert score == 0.0
    assert field(result, "blocked") is False
    expected = "license_scanner@4.0." + "3" + "+" + hashlib.sha256(corpus_bytes).hexdigest()[:12]
    assert field(result, "gate_version") == expected