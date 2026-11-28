# hotdocs-criterion: sha256:f857aa152f2574819c761472685cadf18bc37cfe84e723c69c02631d87329aca
"""AC-LICENSE-012 (covers R-LICENSE-010): evaluated/reason semantics of LicenseScanResult."""

import hashlib
import json
from pathlib import Path

import pytest

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "import dataclasses\n"
    "import datetime\n"
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
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime("
    + repr("%Y-%m-%dT%H:%M:%SZ")
    + ")\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return dict(entry_count=0)\n"
)

FOO_SOURCE = (
    "def compute_total(values, factor):\n"
    "    result = 0\n"
    "    for value in values:\n"
    "        result = result + value * factor\n"
    "    return result\n"
    "\n"
    "\n"
    "class Accumulator:\n"
    "    def __init__(self, start):\n"
    "        self.total = start\n"
    "\n"
    "    def add(self, amount):\n"
    "        self.total = self.total + amount\n"
    "        return self.total\n"
)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "gen" / "foo").mkdir(parents=True)
    (root / "gen" / "foo" / "foo.py").write_text(FOO_SOURCE, encoding="utf-8")
    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return root


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def test_unset_corpus_is_not_evaluated_and_not_blocked(repo_root):
    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is False
    assert field(result, "reason") == "no-reference-corpus"
    assert field(result, "similarity_score") is None
    assert field(result, "block_threshold") is None
    assert list(field(result, "matches")) == []
    assert field(result, "blocked") is False
    assert field(result, "gate_version") == "license_scanner@4.0.0-no-reference-corpus"


def test_empty_entries_corpus_is_invalid_and_blocks(repo_root, monkeypatch):
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(
        json.dumps({"corpus_version": 2, "block_threshold": 0.7, "entries": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is False
    assert field(result, "reason") == "corpus-invalid"
    assert field(result, "blocked") is True
    assert field(result, "similarity_score") is None
    assert field(result, "block_threshold") is None
    assert list(field(result, "matches")) == []


def test_usable_corpus_with_no_shared_windows_scores_zero(repo_root, monkeypatch):
    unrelated_window = "\x1f".join(
        ["zebra", "quokka", "xylophone", "marmalade", "nebula",
         "obsidian", "pelican", "quasar", "rhubarb"]
    )
    unrelated_hash = hashlib.sha256(unrelated_window.encode("utf-8")).hexdigest()
    corpus = {
        "corpus_version": 7,
        "block_threshold": 0.7,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "low",
                "hashes": [unrelated_hash],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_bytes(json.dumps(corpus).encode("utf-8"))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    expected_h = hashlib.sha256(corpus_path.read_bytes()).hexdigest()[:12]

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is True
    assert field(result, "reason") is None
    score = field(result, "similarity_score")
    assert score is not None
    assert _is_number(score)
    assert score == 0.0
    assert field(result, "blocked") is False
    assert field(result, "gate_version") == "license_scanner@4.0.7+" + expected_h