import pytest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


AWS_KEY = "AKIAABCDEFGHIJKLMNOP"

CACHE_MANAGER_STUB = '''\
import dataclasses


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str = None
    gate_inputs_hash: str = None
    gate_version: str = None
    model_pin: str = None


@dataclasses.dataclass
class CachedResult:
    gate_type: str = None
    payload: object = None
    stored_at: str = None


class _Miss:
    payload = None


def get(cache_key, repo_root=None):
    return _Miss()


def put(cache_key, cached_result, repo_root=None):
    pass
'''


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    cache_manager_dir = tmp_path / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(
        CACHE_MANAGER_STUB, encoding="utf-8"
    )
    return tmp_path


def test_single_match_in_gen(repo_root):
    _write(repo_root / "gen" / "foo" / "config.py", 'K = "%s"\n' % AWS_KEY)

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches")
    assert len(matches) == 1
    match = matches[0]
    assert _get(match, "rule_id") == "AWS Access Key"
    assert _get(match, "risk_tier") == "high"
    assert _get(match, "file") == "gen/foo/config.py"
    assert _get(match, "line") == 1
    assert _get(result, "flagged") is True


def test_whole_repository_scanned_no_exceptions(repo_root):
    files = [
        "README.md",
        "notes/n.md",
        "pipeline/p.py",
        "tools/t.py",
        "verification/secret-scanner/generated-test/test_x.py",
    ]
    for rel in files:
        _write(repo_root / rel, 'secret = "%s"\n' % AWS_KEY)

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches")
    matched_by_file = {}
    for m in matches:
        matched_by_file.setdefault(_get(m, "file"), []).append(m)

    for rel in files:
        assert rel in matched_by_file
        for m in matched_by_file[rel]:
            assert _get(m, "rule_id") == "AWS Access Key"


def test_skip_dirs_and_non_utf8_excluded(repo_root):
    secret_line = 'secret = "%s"\n' % AWS_KEY
    _write(repo_root / "gen" / "foo" / "__pycache__" / "x.txt", secret_line)
    _write(repo_root / ".git" / "config", secret_line)
    _write(repo_root / ".venv" / "lib" / "x.py", secret_line)
    _write(repo_root / ".hotdocs" / "x.json", secret_line)
    _write(repo_root / ".pytest_cache" / "x.txt", secret_line)
    _write(repo_root / "node_modules" / "x.js", secret_line)
    _write_bytes(
        repo_root / "gen" / "foo" / "blob.bin",
        b"\xff\xfe" + AWS_KEY.encode("ascii") + b"\x80\x81",
    )

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is False
    assert _get(result, "matches") == []


def test_benign_lines_not_flagged(repo_root):
    content = (
        "gate_version=GATE_VERSION\n"
        '{"secret_scanner": "secret_scanner@0.0.0"}\n'
        "see verification/spec-linter/BOOTSTRAP.md --retry-feedback=R-TRACK-009\n"
    )
    _write(repo_root / "gen" / "foo" / "ok.py", content)

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is False
    assert _get(result, "matches") == []