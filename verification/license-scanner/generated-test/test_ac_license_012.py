"""Tests for AC-LICENSE-012 (R-LICENSE-010)."""
import hashlib
import json

import license_scanner

_FOO_SOURCE = (
    "def foo_function_example(a, b, c, d, e, f, g):\n"
    "    return a + b + c + d + e + f + g\n"
)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_gen_foo(repo_root, content=_FOO_SOURCE):
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text(content)


def test_no_reference_corpus_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_gen_foo(repo_root)

    result = license_scanner.scan("comp-foo", repo_root)

    assert _get(result, "evaluated") is False
    assert _get(result, "reason") == "no-reference-corpus"
    assert _get(result, "similarity_score") is None
    assert _get(result, "block_threshold") is None
    assert _get(result, "matches") == []
    assert _get(result, "blocked") is False
    assert _get(result, "gate_version") == "license_scanner@4.0.0-no-reference-corpus"


def test_corpus_invalid_empty_entries(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_gen_foo(repo_root)

    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({
        "corpus_version": 1,
        "block_threshold": 0.7,
        "entries": [],
    }))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    assert _get(result, "evaluated") is False
    assert _get(result, "reason") == "corpus-invalid"
    assert _get(result, "blocked") is True


def test_valid_corpus_zero_similarity(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_gen_foo(repo_root)

    corpus_version = 3
    corpus_data = {
        "corpus_version": corpus_version,
        "block_threshold": 0.7,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": ["a" * 64],
            }
        ],
    }
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps(corpus_data))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-foo", repo_root)

    assert _get(result, "evaluated") is True
    assert _get(result, "reason") is None

    similarity_score = _get(result, "similarity_score")
    assert similarity_score is not None
    assert similarity_score == 0.0

    assert _get(result, "blocked") is False

    corpus_bytes = corpus_path.read_bytes()
    digest_prefix = hashlib.sha256(corpus_bytes).hexdigest()[:12]
    expected_gate_version = (
        f"license_scanner@4.0.{corpus_version}+{digest_prefix}"
    )
    assert _get(result, "gate_version") == expected_gate_version