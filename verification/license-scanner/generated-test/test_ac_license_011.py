# hotdocs-criterion: sha256:3b56f54839825a140bdbd504098abf9f26ce1f5964101e82a7e21c3b112f6c42
import hashlib
import json
import re

import pytest

import license_scanner


SOURCE = (
    "def compute_total(alpha, beta, gamma):\n"
    "    result = alpha + beta * gamma\n"
    "    value = result - alpha / beta\n"
    "    other = value + gamma * 42\n"
    "    return other + result + value\n"
    "\n"
    "def helper_function(delta, epsilon):\n"
    "    zeta = delta * epsilon + 7\n"
    "    theta = zeta - delta + epsilon\n"
    "    return theta * zeta\n"
)


FAKE_CACHE_MANAGER = (
    "import datetime\n"
    "from dataclasses import dataclass\n"
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
    hashes = set()
    for i in range(len(tokens) - 9 + 1):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root):
    _write(root / "gen" / "foo" / "foo.py", SOURCE)
    _write(root / "legacy" / "foo" / "foo.py", SOURCE)
    _write(root / "gen" / "cache-manager" / "cache_manager.py", FAKE_CACHE_MANAGER)
    comp = root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(comp / "requirements" / "R-FOO-001.md", "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do foo.\n")
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    return root


def _write_corpus(root, hashes, threshold=0.70):
    corpus = {
        "corpus_version": 1,
        "block_threshold": threshold,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": hashes,
            }
        ],
    }
    path = root / "corpus.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")
    return path


@pytest.fixture
def env(monkeypatch, tmp_path):
    for name in ("VAR_LICENSE_CORPUS_PATH", "VAR_COMPLIANCE_WEBHOOK_URL", "VAR_CACHE_STORE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch


def test_disjoint_corpus_json_and_text(env, tmp_path, capsys):
    root = _build_repo(tmp_path / "repo")
    unrelated = [hashlib.sha256(("unrelated-" + str(i)).encode("utf-8")).hexdigest() for i in range(5)]
    own = set(_window_hashes(SOURCE))
    assert own and not (own & set(unrelated))
    corpus = _write_corpus(root, unrelated)
    env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    capsys.readouterr()
    code = license_scanner.main(["comp-foo", "--repo-root=" + str(root), "--format=json"])
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert field(data, "blocked") is False

    code = license_scanner.main(["comp-foo", "--repo-root", str(root), "--format", "text"])
    out = capsys.readouterr().out
    assert code == 0
    assert "similarity_score" in out


def test_verbatim_corpus_blocks(env, tmp_path, capsys):
    root = _build_repo(tmp_path / "repo")
    corpus = _write_corpus(root, _window_hashes(SOURCE), threshold=0.70)
    env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    code = license_scanner.main(["comp-foo", "--repo-root=" + str(root), "--format=json"])
    capsys.readouterr()
    assert code == 1


def test_no_corpus_not_evaluated_exits_zero(env, tmp_path, capsys):
    root = _build_repo(tmp_path / "repo")

    capsys.readouterr()
    code = license_scanner.main(["comp-foo", "--repo-root=" + str(root), "--format=text"])
    out = capsys.readouterr().out
    assert code == 0
    assert "NOT EVALUATED: no-reference-corpus" in out

    code = license_scanner.main(["comp-foo", "--repo-root=" + str(root), "--format=json"])
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert field(data, "evaluated") is False


def test_missing_corpus_file_unreadable(env, tmp_path, capsys):
    root = _build_repo(tmp_path / "repo")
    env.setenv("VAR_LICENSE_CORPUS_PATH", str(root / "does-not-exist.json"))

    capsys.readouterr()
    code = license_scanner.main(["comp-foo", "--repo-root=" + str(root), "--format=text"])
    out = capsys.readouterr().out
    assert code == 1
    assert "NOT EVALUATED: corpus-unreadable" in out


@pytest.mark.parametrize(
    "argv_suffix",
    [
        None,
        ["comp-foo", "--format=bogus"],
        ["comp-foo", "--hotdocs-smoke-unknown"],
        ["comp-foo", "--repo-root"],
    ],
)
def test_usage_errors_exit_two(env, tmp_path, capsys, argv_suffix):
    root = _build_repo(tmp_path / "repo")
    env.chdir(root)
    argv = [] if argv_suffix is None else list(argv_suffix)
    code = license_scanner.main(argv)
    capsys.readouterr()
    assert code == 2