# hotdocs-criterion: sha256:854a02bd9910a3aa1c0b50e6caabb48277bc839b29a35d258c74e63855ee9d5c
import hashlib
import json
import re
from pathlib import Path

import pytest

import license_scanner


FAKE_CACHE_MANAGER_SOURCE = (
    "from dataclasses import dataclass\n"
    "from datetime import datetime, timezone\n"
    "from pathlib import Path\n"
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

COMPONENT_SOURCE = (
    "def alpha_one(x):\n"
    "    return x + 1\n"
    "\n"
    "\n"
    "def beta_two(y, z):\n"
    "    total = y * z + 42\n"
    "    return total - 7\n"
    "\n"
    "\n"
    "class GammaThing:\n"
    "    def method_three(self, value):\n"
    "        result = value + 100\n"
    "        return result * 3\n"
    "\n"
    "    def method_four(self, other):\n"
    "        return other - 5 + 8\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _strip(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    return text


def window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", _strip(text))]
    hashes = set()
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return hashes


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "gen" / "foo").mkdir(parents=True)
    (root / "gen" / "foo" / "foo.py").write_text(COMPONENT_SOURCE, encoding="utf-8")
    (root / "gen" / "cache-manager").mkdir(parents=True)
    (root / "gen" / "cache-manager" / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8"
    )
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.chdir(root)
    return root


def write_corpus(path, hashes, block_threshold=0.70):
    data = {
        "corpus_version": 3,
        "block_threshold": block_threshold,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "medium",
                "hashes": sorted(hashes),
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def unrelated_hashes():
    return {hashlib.sha256(("unrelated-window-" + str(i)).encode("utf-8")).hexdigest() for i in range(5)}


def test_no_overlap_json_not_blocked(repo_root, monkeypatch, capsys):
    corpus = write_corpus(repo_root / "corpus.json", unrelated_hashes())
    assert not (window_hashes(COMPONENT_SOURCE) & unrelated_hashes())
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))
    capsys.readouterr()
    rc = license_scanner.main(["comp-foo", "--repo-root=" + str(repo_root), "--format=json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert field(data, "blocked") is False


def test_no_overlap_text_space_form(repo_root, monkeypatch, capsys):
    corpus = write_corpus(repo_root / "corpus.json", unrelated_hashes())
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))
    capsys.readouterr()
    rc = license_scanner.main(["comp-foo", "--repo-root", str(repo_root), "--format", "text"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "similarity_score" in out


def test_verbatim_copy_blocked(repo_root, monkeypatch, capsys):
    hashes = window_hashes(COMPONENT_SOURCE)
    assert hashes
    corpus = write_corpus(repo_root / "corpus.json", hashes)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))
    rc = license_scanner.main(["comp-foo", "--repo-root=" + str(repo_root), "--format=json"])
    assert rc == 1
    rc_text = license_scanner.main(["comp-foo", "--repo-root=" + str(repo_root), "--format=text"])
    assert rc_text == 1


def test_corpus_unset_not_evaluated(repo_root, monkeypatch, capsys):
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    capsys.readouterr()
    rc_text = license_scanner.main(["comp-foo", "--repo-root=" + str(repo_root), "--format=text"])
    text_out = capsys.readouterr().out
    assert rc_text == 0
    assert "NOT EVALUATED: no-reference-corpus" in text_out

    rc_json = license_scanner.main(["comp-foo", "--repo-root=" + str(repo_root), "--format=json"])
    json_out = capsys.readouterr().out
    assert rc_json == 0
    data = json.loads(json_out)
    assert field(data, "evaluated") is False


def test_corpus_missing_file_unreadable(repo_root, monkeypatch, capsys):
    missing = repo_root / "does-not-exist-corpus.json"
    assert not missing.exists()
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))
    capsys.readouterr()
    rc = license_scanner.main(["comp-foo", "--repo-root=" + str(repo_root), "--format=text"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "NOT EVALUATED: corpus-unreadable" in out


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda root: [],
        lambda root: ["comp-foo", "--repo-root=" + str(root), "--format=bogus"],
        lambda root: ["comp-foo", "--repo-root=" + str(root), "--hotdocs-smoke-unknown"],
        lambda root: ["comp-foo", "--repo-root"],
    ],
    ids=["no-component-id", "bogus-format", "unknown-argument", "repo-root-without-value"],
)
def test_usage_errors_return_2(repo_root, argv_builder):
    rc = license_scanner.main(argv_builder(repo_root))
    assert rc == 2