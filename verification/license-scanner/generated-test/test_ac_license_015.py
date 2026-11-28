# hotdocs-criterion: sha256:3a1bd2099a8e337c7086f6be968da60f36f9992881d3810d2fb608404e2c5302
import hashlib
import json
import re
from pathlib import Path

import pytest

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FOO_PY = (
    "def compute_total(items, factor):\n"
    "    total = 0\n"
    "    for item in items:\n"
    "        value = item * factor\n"
    "        if value > 10:\n"
    "            total = total + value\n"
    "        else:\n"
    "            total = total - 1\n"
    "    return total\n"
    "\n"
    "\n"
    "def scale_values(values, ratio):\n"
    "    result = []\n"
    "    for entry in values:\n"
    "        result.append(entry * ratio + 3)\n"
    "    return result\n"
)


FAKE_CACHE_MANAGER = (
    "from dataclasses import dataclass\n"
    "from datetime import datetime, timezone\n"
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
    "    payload: object\n"
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
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
)


def _tokens(text):
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]


def _window_hashes(text):
    toks = _tokens(text)
    out = set()
    for i in range(len(toks) - 8):
        joined = "\x1f".join(toks[i:i + 9])
        out.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return out


def _prose(n_words, seed):
    vocab = [
        "meadow", "lantern", "harbor", "velvet", "orchard", "glacier",
        "thimble", "sparrow", "copper", "willow", "nebula", "quarry",
    ]
    words = []
    for i in range(n_words):
        words.append(vocab[i % len(vocab)] + seed + str(i))
    return " ".join(words) + "\n"


def _setup_repo(repo_root, monkeypatch):
    # Fake cache-manager that always misses, so every scan is fresh.
    cm = repo_root / "gen" / "cache-manager"
    cm.mkdir(parents=True)
    (cm / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    comp_spec = repo_root / "specs" / "components" / "foo"
    comp_spec.mkdir(parents=True)
    (comp_spec / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n",
        encoding="utf-8",
    )

    foo = repo_root / "gen" / "foo"
    foo.mkdir(parents=True)
    (foo / "foo.py").write_text(FOO_PY, encoding="utf-8")

    hashes = sorted(_window_hashes(FOO_PY))
    assert len(hashes) > 0
    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.7,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "low",
                "hashes": hashes,
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return foo


def test_excluded_files_do_not_change_score(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    foo = _setup_repo(repo_root, monkeypatch)

    before = license_scanner.scan("comp-foo", repo_root)
    assert field(before, "evaluated") is True
    assert abs(field(before, "similarity_score") - 1.0) < 1e-9
    assert field(before, "blocked") is True

    (foo / ".provenance.json").write_text(_prose(3000, "p"), encoding="utf-8")
    (foo / ".overrides.json").write_text("{}", encoding="utf-8")
    (foo / "__pycache__").mkdir()
    (foo / "__pycache__" / "foo.cpython-314.pyc").write_text(
        _prose(3000, "c"), encoding="utf-8"
    )
    (foo / ".cache").mkdir()
    (foo / ".cache" / "x.py").write_text(_prose(3000, "x"), encoding="utf-8")

    after = license_scanner.scan("comp-foo", repo_root)
    assert field(after, "evaluated") is True
    assert field(after, "blocked") is True
    assert abs(field(after, "similarity_score") - 1.0) < 1e-9
    assert field(after, "blocked") == field(before, "blocked")
    assert field(after, "similarity_score") == field(before, "similarity_score")


def test_declared_asset_is_content(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    foo = _setup_repo(repo_root, monkeypatch)

    (foo / "static").mkdir()
    (foo / "static" / "app.js").write_text(_prose(300, "s"), encoding="utf-8")

    result = license_scanner.scan("comp-foo", repo_root)
    assert field(result, "evaluated") is True
    score = field(result, "similarity_score")
    assert score is not None
    assert score < 1.0