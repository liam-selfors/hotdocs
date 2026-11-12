import hashlib
import json
import re
from pathlib import Path

import pytest

import license_scanner


FOO_SOURCE = (
    "def compute_total_value(alpha, beta, gamma):\n"
    "    result_one = alpha + beta\n"
    "    result_two = result_one * gamma\n"
    "    result_three = result_two - alpha\n"
    "    return result_three + beta + gamma\n"
    "\n"
    "\n"
    "def another_helper_function(delta, epsilon):\n"
    "    combined = delta * epsilon\n"
    "    return combined + delta + epsilon\n"
)


FAKE_CACHE_MANAGER = '''
class CacheKey:
    def __init__(self, *, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin

    def __eq__(self, other):
        return isinstance(other, CacheKey) and vars(self) == vars(other)

    def __hash__(self):
        return hash((self.spec_bundle_hash, self.gate_inputs_hash,
                     self.gate_version, self.model_pin))


class CachedResult:
    def __init__(self, *, gate_type, payload, stored_at):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at

    def __eq__(self, other):
        return isinstance(other, CachedResult) and vars(self) == vars(other)


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None


def now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


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
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return hashes


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    foo_dir = repo / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "foo.py").write_text(FOO_SOURCE, encoding="utf-8")
    cm_dir = repo / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")
    return repo


def _write_corpus(path, hashes, block_threshold=0.70):
    corpus = {
        "corpus_version": 1,
        "block_threshold": block_threshold,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "low",
                "hashes": sorted(hashes),
            }
        ],
    }
    path.write_text(json.dumps(corpus), encoding="utf-8")
    return path


def _run(argv, capsys):
    capsys.readouterr()
    try:
        code = license_scanner.main(argv)
    except SystemExit as exc:
        code = exc.code
    out = capsys.readouterr().out
    return code, out


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_clean_corpus_json_and_text(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    unrelated = {hashlib.sha256(b"completely unrelated window").hexdigest()}
    assert not (unrelated & _window_hashes(FOO_SOURCE))
    corpus = _write_corpus(tmp_path / "corpus.json", unrelated)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))
    monkeypatch.chdir(tmp_path)

    code, out = _run(["comp-foo", "--repo-root=" + str(repo), "--format=json"], capsys)
    assert code == 0, out
    data = json.loads(out.strip())
    assert _field(data, "blocked") is False
    assert _field(data, "evaluated") is True

    code, out = _run(["comp-foo", "--repo-root", str(repo), "--format", "text"], capsys)
    assert code == 0, out
    assert "similarity_score" in out


def test_verbatim_copy_blocks(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    hashes = _window_hashes(FOO_SOURCE)
    assert hashes
    corpus = _write_corpus(tmp_path / "corpus.json", hashes, block_threshold=0.70)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))
    monkeypatch.chdir(tmp_path)

    code, out = _run(["comp-foo", "--repo-root=" + str(repo)], capsys)
    assert code == 1, out

    code, out = _run(["comp-foo", "--repo-root=" + str(repo), "--format=json"], capsys)
    assert code == 1, out
    data = json.loads(out.strip())
    assert _field(data, "blocked") is True


def test_no_corpus_not_evaluated_exits_zero(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    code, out = _run(["comp-foo", "--repo-root=" + str(repo), "--format=text"], capsys)
    assert code == 0, out
    assert "NOT EVALUATED: no-reference-corpus" in out

    code, out = _run(["comp-foo", "--repo-root=" + str(repo), "--format=json"], capsys)
    assert code == 0, out
    data = json.loads(out.strip())
    assert _field(data, "evaluated") is False


def test_missing_corpus_file_is_unreadable_and_blocks(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    missing = tmp_path / "does-not-exist" / "corpus.json"
    assert not missing.exists()
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))
    monkeypatch.chdir(tmp_path)

    code, out = _run(["comp-foo", "--repo-root=" + str(repo), "--format=text"], capsys)
    assert code == 1, out
    assert "NOT EVALUATED: corpus-unreadable" in out


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["comp-foo", "--format=bogus"],
        ["comp-foo", "--format", "bogus"],
        ["comp-foo", "--no-such-flag"],
        ["comp-foo", "--repo-root"],
    ],
)
def test_usage_errors_exit_two(tmp_path, monkeypatch, capsys, argv):
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    code, _ = _run(list(argv), capsys)
    assert code == 2