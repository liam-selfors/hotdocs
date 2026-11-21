# hotdocs-criterion: sha256:93442c4938b8900f606567eb652df020c2f0eff06d501ea9ad70bed4227da7b1
import hashlib
import json
import re
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"

IDENTIFIERS = [
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
    "golf", "hotel", "india", "juliet", "kilo", "lima",
    "mike", "november", "oscar", "papa", "quebec", "romeo",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tokens(text):
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]


def _window_hashes(text):
    toks = _tokens(text)
    hashes = []
    for i in range(len(toks) - 9 + 1):
        window = "\x1f".join(toks[i:i + 9])
        h = hashlib.sha256(window.encode("utf-8")).hexdigest()
        if h not in hashes:
            hashes.append(h)
    return hashes


def _source_text():
    # Simple assignments, no comments, so normalization leaves tokens intact.
    lines = []
    for i in range(0, len(IDENTIFIERS), 3):
        a, b, c = IDENTIFIERS[i:i + 3]
        lines.append(a + " = " + b + " + " + c + "\n")
    return "".join(lines)


def _write_fake_cache_manager(repo_root, log_path):
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
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
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "    def __hash__(self):\n"
        "        return 0\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
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
    (d / "cache_manager.py").write_text(src)


def _setup_repo(tmp_path, monkeypatch, entry_hashes, block_threshold):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "gen" / COMPONENT_SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text(_source_text())

    _write_fake_cache_manager(repo_root, tmp_path / "cache_calls.log")

    corpus = {
        "corpus_version": 3,
        "block_threshold": block_threshold,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "low",
                "hashes": entry_hashes,
            }
        ],
    }
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps(corpus))

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)
    return repo_root


def test_sanity_source_has_ten_distinct_windows():
    assert len(_window_hashes(_source_text())) == 10


def test_full_match_above_threshold_is_blocked(tmp_path, monkeypatch):
    hashes = _window_hashes(_source_text())
    repo_root = _setup_repo(tmp_path, monkeypatch, hashes, 0.70)

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert field(result, "evaluated") is True
    score = field(result, "similarity_score")
    threshold = field(result, "block_threshold")
    assert threshold == pytest.approx(0.70)
    assert score >= threshold
    assert score == pytest.approx(1.0)
    assert field(result, "blocked") is True


def test_score_exactly_at_threshold_is_blocked(tmp_path, monkeypatch):
    hashes = _window_hashes(_source_text())
    half = hashes[:5]
    repo_root = _setup_repo(tmp_path, monkeypatch, half, 0.5)

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert field(result, "evaluated") is True
    assert field(result, "similarity_score") == pytest.approx(0.5)
    assert field(result, "block_threshold") == pytest.approx(0.5)
    assert field(result, "blocked") is True


def test_cli_json_reports_blocked_with_exit_1(tmp_path, monkeypatch, capsys):
    hashes = _window_hashes(_source_text())
    repo_root = _setup_repo(tmp_path, monkeypatch, hashes, 0.70)

    code = license_scanner.main(
        [COMPONENT_ID, "--repo-root=" + str(repo_root), "--format=json"]
    )
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    assert doc["evaluated"] is True
    assert doc["blocked"] is True
    assert doc["similarity_score"] >= doc["block_threshold"]


def test_cli_text_reports_blocked_with_exit_1(tmp_path, monkeypatch, capsys):
    hashes = _window_hashes(_source_text())
    repo_root = _setup_repo(tmp_path, monkeypatch, hashes, 0.70)

    code = license_scanner.main([COMPONENT_ID, "--repo-root", str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    assert "blocked" in out.lower()