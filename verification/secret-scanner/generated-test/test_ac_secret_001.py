# hotdocs-criterion: sha256:f6047a01af96a6e46a540712569536eb8a9c78c6cf37fc0961287a8e705a7dc7
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


AWS_KEY = "AKIAABCDEFGHIJKLMNOP"
KEY_LINE = "K = " + repr(AWS_KEY) + "\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_cache_manager_stand_in(repo_root):
    lines = [
        "from dataclasses import dataclass",
        "from datetime import datetime, timezone",
        "",
        "",
        "class SchemaValidationError(ValueError):",
        "    pass",
        "",
        "",
        "class Miss:",
        "    def __eq__(self, other):",
        "        return isinstance(other, Miss)",
        "",
        "    def __hash__(self):",
        "        return 0",
        "",
        "",
        "@dataclass",
        "class CacheKey:",
        "    spec_bundle_hash: str",
        "    gate_inputs_hash: str",
        "    gate_version: str",
        "    model_pin: str",
        "",
        "",
        "@dataclass",
        "class CachedResult:",
        "    gate_type: str",
        "    payload: dict",
        "    stored_at: str",
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    return Miss()",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    return None",
        "",
        "",
        "def now_iso():",
        "    return datetime.now(timezone.utc).strftime(" + repr("%Y-%m-%dT%H:%M:%SZ") + ")",
        "",
        "",
        "def stats(*, repo_root=None):",
        "    return {" + repr("entry_count") + ": 0}",
        "",
    ]
    target = repo_root / "gen" / "cache-manager" / "cache_manager.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")


def _write(repo_root, rel, text):
    target = repo_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def fake_urlopen(*args, **kwargs):
        raise OSError("webhook must not be called in this test")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    root = tmp_path / "repo"
    root.mkdir()
    _write_cache_manager_stand_in(root)
    return root


def test_single_key_in_gen_file_is_one_high_match(repo_root):
    _write(repo_root, "gen/foo/config.py", KEY_LINE)

    result = secret_scanner.scan(Path(repo_root))
    matches = field(result, "matches")

    assert len(matches) == 1
    m = matches[0]
    assert field(m, "rule_id") == "AWS Access Key"
    assert field(m, "risk_tier") == "high"
    assert field(m, "file") == "gen/foo/config.py"
    assert field(m, "line") == 1
    assert field(result, "flagged") is True


def test_no_directory_exceptions_for_docs_pipeline_tools_tests(repo_root):
    rels = [
        "README.md",
        "notes/n.md",
        "pipeline/p.py",
        "tools/t.py",
        "verification/secret-scanner/generated-test/test_x.py",
    ]
    for rel in rels:
        _write(repo_root, rel, KEY_LINE)

    result = secret_scanner.scan(Path(repo_root))
    matched_files = {field(m, "file") for m in field(result, "matches")}

    for rel in rels:
        assert rel in matched_files, rel
    assert field(result, "flagged") is True


def test_skipped_directories_and_non_utf8_files(repo_root):
    rels = [
        "gen/foo/__pycache__/x.txt",
        ".git/config",
        ".venv/lib/x.py",
        ".hotdocs/x.json",
        ".pytest_cache/x.txt",
        "node_modules/x.js",
    ]
    for rel in rels:
        _write(repo_root, rel, KEY_LINE)

    blob = repo_root / "gen" / "foo" / "blob.bin"
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"\xff\xfe\x80 " + KEY_LINE.encode("ascii") + b"\xc3\x28\n")
    with pytest.raises(UnicodeDecodeError):
        blob.read_bytes().decode("utf-8")

    result = secret_scanner.scan(Path(repo_root))

    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []


def test_ordinary_text_is_not_flagged(repo_root):
    text = (
        "gate_version=GATE_VERSION\n"
        + '{"secret_scanner": "secret_scanner@0.0.0"}\n'
        + "see verification/spec-linter/BOOTSTRAP.md --retry-feedback=R-TRACK-009\n"
    )
    _write(repo_root, "gen/foo/ok.py", text)

    result = secret_scanner.scan(Path(repo_root))

    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []