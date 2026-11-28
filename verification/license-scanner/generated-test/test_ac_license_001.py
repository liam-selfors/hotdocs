# hotdocs-criterion: sha256:288a03e8b442c913fd292c41385b374affc8905a6836b631cab3040586ca8194
import hashlib
import json
import re
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-foo"
SLUG = "foo"

SOURCE_TEXT = (
    "result = alpha + beta + gamma + delta + epsilon + zeta"
    " + eta + theta + iota + kappa + lam + mu\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def tokenize(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]


def window_hashes(text):
    tokens = tokenize(text)
    out = []
    for i in range(len(tokens) - 9 + 1):
        window = "\x1f".join(tokens[i:i + 9])
        out.append(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return out


FAKE_CACHE_MANAGER = (
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
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
)


def build_repo(tmp_path, monkeypatch, fraction_included):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "gen" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text(SOURCE_TEXT, encoding="utf-8")

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    distinct = sorted(set(window_hashes(SOURCE_TEXT)))
    assert len(distinct) >= 2
    if fraction_included == "all":
        included = list(distinct)
        threshold = 0.70
    else:
        included = distinct[: len(distinct) // 2]
        # Exactly at the threshold.
        threshold = len(included) / len(distinct)

    corpus = {
        "corpus_version": 3,
        "block_threshold": threshold,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "low",
                "hashes": included,
            }
        ],
    }
    corpus_dir = repo_root / "corpus"
    corpus_dir.mkdir()
    corpus_path = corpus_dir / "reference_corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)
    return repo_root, threshold


@pytest.mark.parametrize("fraction_included", ["all", "exactly-at-threshold"])
def test_scan_blocks_at_or_above_threshold(tmp_path, monkeypatch, fraction_included):
    repo_root, threshold = build_repo(tmp_path, monkeypatch, fraction_included)

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert field(result, "evaluated") is True
    score = field(result, "similarity_score")
    block_threshold = field(result, "block_threshold")
    assert block_threshold == pytest.approx(threshold)
    assert score >= block_threshold
    assert field(result, "blocked") is True
    assert len(field(result, "matches")) >= 1


@pytest.mark.parametrize("fraction_included", ["all", "exactly-at-threshold"])
def test_cli_reports_merge_blocked(tmp_path, monkeypatch, capsys, fraction_included):
    repo_root, threshold = build_repo(tmp_path, monkeypatch, fraction_included)

    code = license_scanner.main(
        [COMPONENT_ID, "--repo-root=" + str(repo_root), "--format=json"]
    )
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    assert doc["evaluated"] is True
    assert doc["blocked"] is True
    assert doc["similarity_score"] >= doc["block_threshold"]


def test_cli_text_reports_blocked(tmp_path, monkeypatch, capsys):
    repo_root, _ = build_repo(tmp_path, monkeypatch, "all")

    code = license_scanner.main([COMPONENT_ID, "--repo-root", str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    assert "blocked" in out.lower()