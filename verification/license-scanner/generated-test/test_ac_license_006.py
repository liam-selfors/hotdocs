# hotdocs-criterion: sha256:5c613cdf25b72195b58c25c9741f681a1d18910c339c556f0cef9d8023d59e7a
import hashlib
import json
from pathlib import Path

import pytest

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def window_hash(tokens):
    return hashlib.sha256("\x1f".join(tokens).encode("utf-8")).hexdigest()


SOURCE = (
    "def compute_total(alpha, beta, gamma, delta, epsilon):\n"
    "    result = alpha + beta + gamma + delta + epsilon\n"
    "    return result\n"
)


def write_fake_cache_manager(repo_root, log_path):
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "import json\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REQUIRED = " + repr({
            "generator": ["component_id", "model", "prompt_version", "files"],
            "compiler": ["outputs", "gate_version", "summary"],
            "generated_test": ["component_id", "criterion_id", "model", "file"],
            "llm_judge": ["result", "rationale"],
            "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
            "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
        }) + "\n"
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
        "@dataclasses.dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log({'op': 'get'})\n"
        "    return Miss()\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    gate_type = str(cache_key.gate_version).split('@', 1)[0]\n"
        "    if result.gate_type != gate_type or gate_type not in REQUIRED:\n"
        "        raise SchemaValidationError('gate_type mismatch')\n"
        "    payload = result.payload\n"
        "    for key in REQUIRED[gate_type]:\n"
        "        present = (key in payload) if isinstance(payload, dict) else hasattr(payload, key)\n"
        "        if not present:\n"
        "            raise SchemaValidationError('missing ' + key)\n"
        "    cid = payload['component_id'] if isinstance(payload, dict) else getattr(payload, 'component_id')\n"
        "    _log({'op': 'put', 'component_id': cid})\n"
        "    return None\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 0}\n"
    )
    (d / "cache_manager.py").write_text(src, encoding="utf-8")


def write_component(repo_root, slug):
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (slug.replace("-", "_") + ".py")).write_text(SOURCE, encoding="utf-8")


def write_corpus(repo_root):
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.7,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "low",
                "hashes": [window_hash(["unrelated"] * 9)],
            }
        ],
    }
    path = repo_root / "corpus.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")
    return path


def read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_log.jsonl"
    write_fake_cache_manager(repo_root, log_path)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.chdir(repo_root)
    return repo_root, log_path


def assert_single_result(result, component_id):
    assert result is not None
    assert not isinstance(result, (list, tuple, set))
    assert field(result, "component_id") == component_id
    for name in ("gate_version", "evaluated", "similarity_score", "blocked", "matches"):
        field(result, name)


def test_one_result_per_component_with_usable_corpus(env, monkeypatch):
    repo_root, log_path = env
    corpus = write_corpus(repo_root)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))
    write_component(repo_root, "foo")

    result = license_scanner.scan("comp-foo", repo_root)
    assert_single_result(result, "comp-foo")
    assert field(result, "evaluated") is True

    puts = [e for e in read_log(log_path) if e["op"] == "put"]
    assert len(puts) == 1
    assert puts[0]["component_id"] == "comp-foo"


def test_each_component_gets_exactly_one_result(env, monkeypatch):
    repo_root, log_path = env
    corpus = write_corpus(repo_root)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))
    write_component(repo_root, "foo")
    write_component(repo_root, "bar")

    r_foo = license_scanner.scan("comp-foo", repo_root)
    r_bar = license_scanner.scan("comp-bar", repo_root)
    assert_single_result(r_foo, "comp-foo")
    assert_single_result(r_bar, "comp-bar")

    puts = [e for e in read_log(log_path) if e["op"] == "put"]
    assert sorted(e["component_id"] for e in puts) == ["comp-bar", "comp-foo"]


def test_one_result_when_not_evaluated(env, monkeypatch):
    repo_root, log_path = env
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    write_component(repo_root, "foo")

    result = license_scanner.scan("comp-foo", repo_root)
    assert_single_result(result, "comp-foo")
    assert field(result, "evaluated") is False
    assert field(result, "reason") == "no-reference-corpus"

    puts = [e for e in read_log(log_path) if e["op"] == "put"]
    assert len(puts) <= 1
    for e in puts:
        assert e["component_id"] == "comp-foo"


def test_cli_json_prints_exactly_one_result(env, monkeypatch, capsys):
    repo_root, log_path = env
    corpus = write_corpus(repo_root)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))
    write_component(repo_root, "foo")

    code = license_scanner.main(["comp-foo", "--repo-root", str(repo_root), "--format=json"])
    out = capsys.readouterr().out
    assert code in (0, 1)
    doc = json.loads(out)
    assert isinstance(doc, dict)
    assert doc["component_id"] == "comp-foo"
    assert "blocked" in doc and "similarity_score" in doc

    puts = [e for e in read_log(log_path) if e["op"] == "put"]
    assert len(puts) == 1
    assert puts[0]["component_id"] == "comp-foo"