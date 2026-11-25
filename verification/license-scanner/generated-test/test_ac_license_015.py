# hotdocs-criterion: sha256:7f7b0c334d6ef672934b46e3e5ad81815e86c1c638dd52ed80b1dc45f3a3d64f
import hashlib
import json
import re

import pytest

import license_scanner


FOO_SOURCE = (
    "def add(a, b):\n"
    "    return a + b\n"
    "\n"
    "class Thing:\n"
    "    value = 42\n"
    "\n"
    "    def run(self, x, y, z):\n"
    "        total = x + y + z\n"
    "        scaled = total * self.value\n"
    "        return add(scaled, 7)\n"
    "\n"
    "def main(items):\n"
    "    result = 0\n"
    "    for item in items:\n"
    "        result = add(result, item)\n"
    "    return result\n"
)


FAKE_CACHE_MANAGER = (
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
    "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    return text


def window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", strip_comments(text))]
    hashes = set()
    for i in range(len(tokens) - 9 + 1):
        joined = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return sorted(hashes)


def prose(n_words, seed):
    vocab = [
        "meadow", "river", "lantern", "harbor", "orchard", "pebble", "willow",
        "summit", "canyon", "breeze", "thimble", "marble", "falcon", "garden",
        "copper", "velvet", "glacier", "ember", "quarry", "saddle", "tundra",
    ]
    words = []
    for i in range(n_words):
        words.append(vocab[(i * 7 + seed) % len(vocab)] + "w" + str(i))
    lines = []
    for i in range(0, len(words), 12):
        lines.append(" ".join(words[i:i + 12]))
    return "\n".join(lines) + "\n"


def make_repo(root, monkeypatch, extra_files=None):
    root.mkdir(parents=True, exist_ok=True)
    foo_dir = root / "gen" / "foo"
    foo_dir.mkdir(parents=True, exist_ok=True)
    (foo_dir / "foo.py").write_text(FOO_SOURCE, encoding="utf-8")

    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    hashes = window_hashes(FOO_SOURCE)
    assert len(hashes) > 5
    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-foo",
                "license_family": "GPL",
                "risk_tier": "medium",
                "hashes": hashes,
            }
        ],
    }
    corpus_path = root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    for rel, content in (extra_files or {}).items():
        p = foo_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return root


def add_excluded_files(root):
    foo_dir = root / "gen" / "foo"
    (foo_dir / ".provenance.json").write_text(prose(3000, 1), encoding="utf-8")
    (foo_dir / ".overrides.json").write_text("{}", encoding="utf-8")
    pyc = foo_dir / "__pycache__" / "foo.cpython-314.pyc"
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_text(prose(3000, 2), encoding="utf-8")
    cached = foo_dir / ".cache" / "x.py"
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(prose(3000, 3), encoding="utf-8")


def test_excluded_files_do_not_change_score(tmp_path, monkeypatch):
    root = make_repo(tmp_path / "repo", monkeypatch)

    before = license_scanner.scan("comp-foo", root)
    assert field(before, "evaluated") is True
    assert field(before, "similarity_score") == 1.0
    assert field(before, "blocked") is True

    add_excluded_files(root)

    after = license_scanner.scan("comp-foo", root)
    assert field(after, "evaluated") is True
    assert field(after, "blocked") is True
    assert field(after, "similarity_score") == 1.0


def test_excluded_files_fresh_repo_scores_one(tmp_path, monkeypatch):
    root = make_repo(tmp_path / "repo2", monkeypatch)
    add_excluded_files(root)

    result = license_scanner.scan("comp-foo", root)
    assert field(result, "evaluated") is True
    assert field(result, "blocked") is True
    assert field(result, "similarity_score") == 1.0


def test_declared_asset_is_content(tmp_path, monkeypatch):
    root = make_repo(
        tmp_path / "repo3",
        monkeypatch,
        extra_files={"static/app.js": prose(300, 5)},
    )

    result = license_scanner.scan("comp-foo", root)
    assert field(result, "evaluated") is True
    score = field(result, "similarity_score")
    assert score is not None
    assert score < 1.0