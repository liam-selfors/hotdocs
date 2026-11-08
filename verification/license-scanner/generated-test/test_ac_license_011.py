import hashlib
import json
import re

import license_scanner

FAKE_CACHE_MANAGER_SOURCE = '''
import dataclasses


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None
'''

NOSHARE_SOURCE = (
    "red orange yellow green blue indigo violet black white gray "
    "silver gold bronze copper tin\n"
)

UNRELATED_TEXT = (
    "foxtrot golf hotel india juliet kilo lima mike november oscar "
    "papa quebec romeo sierra tango\n"
)

VERBATIM_SOURCE = (
    "alpha beta gamma delta epsilon zeta eta theta iota kappa "
    "lambda mu nu xi omicron pi\n"
)


def _tokenize(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]


def _window_hashes(text):
    tokens = _tokenize(text)
    hashes = set()
    for i in range(0, len(tokens) - 8):
        window = tokens[i:i + 9]
        joined = "\x1f".join(window)
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return hashes


def _write_fake_cache_manager(repo_root):
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)


def _make_repo(tmp_path, source_text=None):
    if source_text is None:
        source_text = "placeholder alpha beta gamma delta epsilon zeta eta theta\n"
    repo_root = tmp_path / "repo"
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "app.py").write_text(source_text)
    _write_fake_cache_manager(repo_root)
    return repo_root


def _write_corpus(path, entries, corpus_version=1, block_threshold=0.70):
    data = {
        "corpus_version": corpus_version,
        "block_threshold": block_threshold,
        "entries": entries,
    }
    path.write_text(json.dumps(data))


def _get_field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def test_no_shared_kgrams_json_and_text(tmp_path, monkeypatch, capsys):
    repo_root = _make_repo(tmp_path, source_text=NOSHARE_SOURCE)
    corpus_path = tmp_path / "corpus.json"
    _write_corpus(
        corpus_path,
        [
            {
                "reference_id": "ref-unrelated",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": sorted(_window_hashes(UNRELATED_TEXT)),
            }
        ],
    )
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    rc_json = license_scanner.main(
        ["comp-foo", "--repo-root=" + str(repo_root), "--format=json"]
    )
    captured_json = capsys.readouterr()
    assert rc_json == 0
    payload = json.loads(captured_json.out)
    assert _get_field(payload, "blocked") is False

    rc_text = license_scanner.main(
        ["comp-foo", "--repo-root", str(repo_root), "--format", "text"]
    )
    captured_text = capsys.readouterr()
    assert rc_text == 0
    assert "similarity_score" in captured_text.out


def test_verbatim_copy_blocks(tmp_path, monkeypatch, capsys):
    repo_root = _make_repo(tmp_path, source_text=VERBATIM_SOURCE)
    corpus_path = tmp_path / "corpus.json"
    _write_corpus(
        corpus_path,
        [
            {
                "reference_id": "ref-verbatim",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": sorted(_window_hashes(VERBATIM_SOURCE)),
            }
        ],
    )
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    rc = license_scanner.main(
        ["comp-foo", "--repo-root=" + str(repo_root), "--format=json"]
    )
    capsys.readouterr()
    assert rc == 1


def test_no_corpus_env_unset(tmp_path, monkeypatch, capsys):
    repo_root = _make_repo(tmp_path)
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    rc_text = license_scanner.main(
        ["comp-foo", "--repo-root=" + str(repo_root), "--format=text"]
    )
    captured_text = capsys.readouterr()
    assert rc_text == 0
    assert "NOT EVALUATED: no-reference-corpus" in captured_text.out

    rc_json = license_scanner.main(
        ["comp-foo", "--repo-root=" + str(repo_root), "--format=json"]
    )
    captured_json = capsys.readouterr()
    assert rc_json == 0
    payload = json.loads(captured_json.out)
    assert _get_field(payload, "evaluated") is False


def test_corpus_unreadable(tmp_path, monkeypatch, capsys):
    repo_root = _make_repo(tmp_path)
    missing_path = tmp_path / "does-not-exist-corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing_path))

    rc = license_scanner.main(
        ["comp-foo", "--repo-root=" + str(repo_root), "--format=text"]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "NOT EVALUATED: corpus-unreadable" in captured.out


def test_usage_errors(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    rc_no_component = license_scanner.main([])
    capsys.readouterr()
    assert rc_no_component == 2

    rc_bad_format = license_scanner.main(
        ["comp-foo", "--repo-root=" + str(repo_root), "--format=bogus"]
    )
    capsys.readouterr()
    assert rc_bad_format == 2

    rc_unknown_arg = license_scanner.main(
        ["comp-foo", "--repo-root=" + str(repo_root), "--nonexistent-flag"]
    )
    capsys.readouterr()
    assert rc_unknown_arg == 2

    rc_dangling_flag = license_scanner.main(["comp-foo", "--repo-root"])
    capsys.readouterr()
    assert rc_dangling_flag == 2