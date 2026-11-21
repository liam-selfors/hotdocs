# hotdocs-criterion: sha256:c6d39cc747593ea438186dd4c30b7161123283ff8528bcc113fe0b7f994a2714
import importlib.util
import json
import sys
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** - a fixture term.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** - Foo MUST add numbers.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven two numbers\nWhen foo adds them\nThen the sum is returned\n```\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    source = (
        "def add_numbers(first_value, second_value, third_value):\n"
        "    total = first_value + second_value + third_value\n"
        "    result = total * 2 + 17\n"
        "    return result if result > 0 else total\n"
    )
    _write(repo_root / "gen" / "foo" / "foo.py", source)
    _write(repo_root / "legacy" / "foo" / "foo.py", source)

    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.7,
        "entries": [
            {
                "reference_id": "ref-real-001",
                "license_family": "gpl-3.0",
                "risk_tier": "low",
                "hashes": ["0" * 64, "1" * 64],
            }
        ],
    }
    _write(repo_root / "corpus.json", json.dumps(corpus))


def _write_fake_cache_manager(repo_root, log_path, expected_gate_version, cached_payload):
    src = (
        "import json\n"
        "from dataclasses import dataclass\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "EXPECTED_GATE_VERSION = " + repr(expected_gate_version) + "\n"
        "CACHED_PAYLOAD = json.loads(" + repr(json.dumps(cached_payload)) + ")\n"
        "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
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
        "def get(cache_key, *, repo_root=None):\n"
        "    gv = cache_key['gate_version'] if isinstance(cache_key, dict) else cache_key.gate_version\n"
        "    _log({'call': 'get', 'gate_version': gv})\n"
        "    if gv == EXPECTED_GATE_VERSION:\n"
        "        return CachedResult(\n"
        "            gate_type='license_scanner',\n"
        "            payload=dict(CACHED_PAYLOAD),\n"
        "            stored_at='2026-01-01T00:00:00Z',\n"
        "        )\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    gv = cache_key['gate_version'] if isinstance(cache_key, dict) else cache_key.gate_version\n"
        "    _log({'call': 'put', 'gate_version': gv})\n"
        "    return None\n"
    )
    _write(repo_root / "gen" / "cache-manager" / "cache_manager.py", src)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ac_license_004_cache_hit_returns_cached_result_without_rescan(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    expected_gv = license_scanner.gate_version(repo_root)
    assert expected_gv.startswith("license_scanner@4.0.3+")

    cached_payload = {
        "component_id": "comp-foo",
        "gate_version": expected_gv,
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.123,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [
            {
                "reference_id": "ref-cached-marker",
                "license_family": "mit",
                "risk_tier": "low",
                "score": 0.123,
            }
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }

    log_path = tmp_path / "cache_calls.log"
    _write_fake_cache_manager(repo_root, log_path, expected_gv, cached_payload)

    result = license_scanner.scan("comp-foo", repo_root)

    calls = _read_log(log_path)
    get_calls = [c for c in calls if c["call"] == "get"]
    put_calls = [c for c in calls if c["call"] == "put"]

    # The cache was consulted with a key matching the scanner's gate_version.
    assert get_calls, "scan never consulted cache-manager.get"
    assert any(c["gate_version"] == expected_gv for c in get_calls)

    # No rescan: nothing freshly computed was stored.
    assert put_calls == [], "a put was issued, implying a rescan on a cache hit"

    # The cached result is what came back.
    assert field(result, "component_id") == "comp-foo"
    assert field(result, "gate_version") == expected_gv
    assert field(result, "similarity_score") == 0.123
    assert field(result, "blocked") is False
    matches = field(result, "matches")
    assert len(matches) == 1
    assert field(matches[0], "reference_id") == "ref-cached-marker"
    assert field(matches[0], "score") == 0.123
    assert field(result, "cache_hit") is True