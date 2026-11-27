# hotdocs-criterion: sha256:78e7748896caa802b66facf9b0724d7284e125ad3335f2b23fdfd1cdc51743e0
"""AC-LICENSE-006: exactly one LicenseScanResult is produced per component per scan."""

import json
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_cache_manager_source(log_path):
    return (
        "import json\n"
        "from dataclasses import dataclass\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
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
        "        return hash('Miss')\n"
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
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log(json.dumps({'call': 'get'}))\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    payload = result['payload'] if isinstance(result, dict) else getattr(result, 'payload')\n"
        "    cid = payload['component_id'] if isinstance(payload, dict) else getattr(payload, 'component_id')\n"
        "    _log(json.dumps({'call': 'put', 'component_id': cid}))\n"
        "    return None\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 0}\n"
    )


def _component_source():
    return (
        "def add_numbers(first_value, second_value, third_value):\n"
        "    total_sum = first_value + second_value + third_value\n"
        "    result_value = total_sum * 2 + 7 - 3\n"
        "    return result_value\n"
        "\n"
        "\n"
        "def greet(name_of_person, greeting_word, punctuation_mark):\n"
        "    message_text = greeting_word + name_of_person + punctuation_mark\n"
        "    return message_text\n"
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    log_path = tmp_path / "cache_calls.log"

    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        _fake_cache_manager_source(log_path), encoding="utf-8"
    )

    comp_dir = root / "gen" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / (SLUG + ".py")).write_text(_component_source(), encoding="utf-8")

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": ["0" * 64],
            }
        ],
    }
    (root / "corpus.json").write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")
    return root, log_path


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _assert_single_result(result):
    assert result is not None
    # A single structured result, never a collection of results.
    assert not isinstance(result, (list, tuple, set))
    assert field(result, "component_id") == COMPONENT_ID
    # It carries the LicenseScanResult's structured fields.
    for name in (
        "gate_version",
        "evaluated",
        "reason",
        "similarity_score",
        "block_threshold",
        "blocked",
        "matches",
        "notified",
        "notification_delivery_error",
        "cache_hit",
    ):
        field(result, name)


def test_library_scan_produces_exactly_one_result(repo):
    root, log_path = repo
    result = license_scanner.scan(COMPONENT_ID, root)
    _assert_single_result(result)
    assert field(result, "evaluated") is True

    puts = [entry for entry in _read_log(log_path) if entry["call"] == "put"]
    assert len(puts) == 1, puts
    assert puts[0]["component_id"] == COMPONENT_ID


def test_each_scan_produces_exactly_one_result(repo):
    root, log_path = repo
    first = license_scanner.scan(COMPONENT_ID, root)
    second = license_scanner.scan(COMPONENT_ID, root)
    _assert_single_result(first)
    _assert_single_result(second)

    puts = [entry for entry in _read_log(log_path) if entry["call"] == "put"]
    # The fake always misses, so each of the two scans stores exactly one result.
    assert len(puts) == 2, puts
    assert all(entry["component_id"] == COMPONENT_ID for entry in puts)


def test_not_evaluated_scan_still_produces_exactly_one_result(repo, monkeypatch):
    root, _ = repo
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    result = license_scanner.scan(COMPONENT_ID, root)
    _assert_single_result(result)
    assert field(result, "evaluated") is False
    assert field(result, "reason") == "no-reference-corpus"


def test_cli_json_prints_exactly_one_result(repo, capsys):
    root, _ = repo
    code = license_scanner.main(
        [COMPONENT_ID, "--repo-root", str(root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    # Exactly one JSON document: json.loads rejects trailing extra documents.
    document = json.loads(out)
    assert isinstance(document, dict)
    assert document["component_id"] == COMPONENT_ID
    assert "blocked" in document
    assert "similarity_score" in document