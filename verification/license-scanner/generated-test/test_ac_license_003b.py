# hotdocs-criterion: sha256:09ea0e7521be46b7b6aa32777ac27bfbe172b454e86f1db696c17049965b8782
import hashlib
import json
import re
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    return text


def _window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", _strip_comments(text))]
    hashes = []
    for i in range(len(tokens) - 9 + 1):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.append(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return hashes


def _write_fake_cache_manager(repo_root, log_path):
    base = repo_root / "gen" / "cache-manager"
    base.mkdir(parents=True, exist_ok=True)
    src = (
        "from dataclasses import dataclass\n"
        "from pathlib import Path\n"
        "import datetime\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
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
        "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return dict(entry_count=0)\n"
    )
    (base / "cache_manager.py").write_text(src, encoding="utf-8")


def _component_source():
    lines = []
    for i in range(40):
        lines.append(
            "def routine_" + str(i) + "(alpha_" + str(i) + ", beta_" + str(i) + "):\n"
            "    gamma_" + str(i) + " = alpha_" + str(i) + " + beta_" + str(i) + " * " + str(i + 100) + "\n"
            "    return gamma_" + str(i) + " - delta_" + str(i) + "\n"
        )
    return "\n".join(lines)


def test_ac_license_003b_high_risk_below_threshold_notifies_without_blocking(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    _write_fake_cache_manager(repo_root, log_path)

    source = _component_source()
    comp_dir = repo_root / "gen" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text(source, encoding="utf-8")

    distinct = sorted(set(_window_hashes(source)))
    assert len(distinct) >= 20
    shared = distinct[: len(distinct) // 2]
    expected_score = len(shared) / len(distinct)
    assert 0.4 <= expected_score < 0.70

    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-high-001",
                "license_family": "gpl-3.0",
                "risk_tier": "high",
                "hashes": shared,
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    # A local, unroutable endpoint: notification is due, delivery fails fast.
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:9/hook")

    result = license_scanner.scan("comp-foo", repo_root)

    assert field(result, "evaluated") is True
    score = field(result, "similarity_score")
    threshold = field(result, "block_threshold")
    assert threshold == 0.70
    assert score < threshold
    assert abs(score - expected_score) < 1e-6

    matches = field(result, "matches")
    assert any(field(m, "risk_tier") == "high" for m in matches)

    assert field(result, "blocked") is False
    assert field(result, "notified") is True