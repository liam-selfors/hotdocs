import hashlib
import json
import re

import license_scanner


def _tokenize(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r'""".*?"""', "", text, flags=re.DOTALL)
    text = re.sub(r"'''.*?'''", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"#.*", "", text)
    return [tok.lower() for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]


def _window_hashes(text):
    tokens = _tokenize(text)
    hashes = set()
    for i in range(len(tokens) - 8):
        window = tokens[i:i + 9]
        joined = "\x1f".join(window)
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return hashes


FOO_SOURCE = (
    "def foo_bar_baz(alpha, beta, gamma, delta):\n"
    "    result = alpha + beta + gamma + delta\n"
    "    other = result * 2\n"
    "    final = other - 1\n"
    "    return final\n"
)


def _write_component(repo_root, source=FOO_SOURCE):
    comp_dir = repo_root / "gen" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "main.py").write_text(source)


def _write_corpus(path, entries, corpus_version=1, block_threshold=0.70):
    path.write_text(json.dumps({
        "corpus_version": corpus_version,
        "block_threshold": block_threshold,
        "entries": entries,
    }))


def test_no_shared_kgrams_json_and_text(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    _write_component(repo_root)

    corpus_path = tmp_path / "corpus.json"
    _write_corpus(corpus_path, [
        {
            "reference_id": "ref-001",
            "license_family": "GPL",
            "risk_tier": "high",
            "hashes": ["0" * 64, "1" * 64, "2" * 64],
        }
    ])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    rc_json = license_scanner.main(
        ["comp-foo", f"--repo-root={repo_root}", "--format=json"]
    )
    out_json = capsys.readouterr().out
    assert rc_json == 0
    result = json.loads(out_json)
    assert result["blocked"] is False

    rc_text = license_scanner.main(
        ["comp-foo", "--repo-root", str(repo_root), "--format", "text"]
    )
    out_text = capsys.readouterr().out
    assert rc_text == 0
    assert "similarity_score" in out_text


def test_verbatim_match_blocks(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    _write_component(repo_root)

    all_hashes = sorted(_window_hashes(FOO_SOURCE))
    assert all_hashes

    corpus_path = tmp_path / "corpus.json"
    _write_corpus(corpus_path, [
        {
            "reference_id": "ref-002",
            "license_family": "GPL",
            "risk_tier": "high",
            "hashes": all_hashes,
        }
    ], block_threshold=0.70)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    rc = license_scanner.main(
        ["comp-foo", f"--repo-root={repo_root}", "--format=json"]
    )
    assert rc == 1


def test_unset_corpus_not_evaluated(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    _write_component(repo_root)
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    rc_text = license_scanner.main(
        ["comp-foo", f"--repo-root={repo_root}", "--format=text"]
    )
    out_text = capsys.readouterr().out
    assert rc_text == 0
    assert "NOT EVALUATED: no-reference-corpus" in out_text

    rc_json = license_scanner.main(
        ["comp-foo", f"--repo-root={repo_root}", "--format=json"]
    )
    out_json = capsys.readouterr().out
    assert rc_json == 0
    result = json.loads(out_json)
    assert result["evaluated"] is False


def test_missing_corpus_file_unreadable(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    _write_component(repo_root)

    missing_corpus_path = tmp_path / "does_not_exist_corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing_corpus_path))

    rc = license_scanner.main(
        ["comp-foo", f"--repo-root={repo_root}", "--format=text"]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "NOT EVALUATED: corpus-unreadable" in out


def test_usage_error_missing_component_id():
    rc = license_scanner.main([])
    assert rc == 2


def test_usage_error_bad_format(tmp_path):
    repo_root = tmp_path / "repo"
    _write_component(repo_root)
    rc = license_scanner.main(
        ["comp-foo", f"--repo-root={repo_root}", "--format=bogus"]
    )
    assert rc == 2


def test_usage_error_unknown_argument(tmp_path):
    repo_root = tmp_path / "repo"
    _write_component(repo_root)
    rc = license_scanner.main(
        ["comp-foo", f"--repo-root={repo_root}", "--format=text", "--unknown-flag"]
    )
    assert rc == 2


def test_usage_error_repo_root_missing_value():
    rc = license_scanner.main(["comp-foo", "--repo-root"])
    assert rc == 2