# hotdocs-criterion: sha256:f4b55bd19a3fe8c6c63ea08e18068dd21bf17569a5aa98bd6e2486c717667cdc
"""AC-SECRET-001: a full scan checks every text file under repo_root.

It skips only the named directories and files that are not valid UTF-8,
and reports each detect-secrets finding as one match.
"""

import secret_scanner

from pathlib import Path

import pytest


# Built by concatenation so this test file's own source holds no literal key.
AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


FAKE_CACHE_MANAGER_SOURCE = '''\
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


REQUIRED = {
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_type = result["gate_type"] if isinstance(result, dict) else result.gate_type
    payload = result["payload"] if isinstance(result, dict) else result.payload
    for key in REQUIRED.get(gate_type, []):
        if key not in payload:
            raise SchemaValidationError("missing payload key")
    return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(repo_root, rel, content):
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    write(root, "gen/cache-manager/cache_manager.py", FAKE_CACHE_MANAGER_SOURCE)
    assert not (root / ".secret-allowlist.json").exists()
    return root


def key_line():
    return "K = " + repr(AWS_KEY).replace("'", '"') + "\n"


def test_single_key_in_gen_file_is_one_high_match(repo_root):
    write(repo_root, "gen/foo/config.py", key_line())

    result = secret_scanner.scan(repo_root)

    matches = field(result, "matches")
    assert len(matches) == 1
    match = matches[0]
    assert field(match, "rule_id") == "AWS Access Key"
    assert field(match, "risk_tier") == "high"
    assert field(match, "file") == "gen/foo/config.py"
    assert field(match, "line") == 1
    assert field(result, "flagged") is True


def test_key_found_in_every_directory_without_exception(repo_root):
    files = [
        "README.md",
        "notes/n.md",
        "pipeline/p.py",
        "tools/t.py",
        "verification/secret-scanner/generated-test/test_x.py",
    ]
    for rel in files:
        write(repo_root, rel, key_line())

    result = secret_scanner.scan(repo_root)

    matched_files = {field(m, "file") for m in field(result, "matches")}
    for rel in files:
        assert rel in matched_files, rel
    assert field(result, "flagged") is True


def test_skipped_directories_and_non_utf8_files_yield_no_match(repo_root):
    for rel in [
        "gen/foo/__pycache__/x.txt",
        ".git/config",
        ".venv/lib/x.py",
        ".hotdocs/x.json",
        ".pytest_cache/x.txt",
        "node_modules/x.js",
    ]:
        write(repo_root, rel, key_line())
    blob = b"\xff\xfe\x80\x81 " + key_line().encode("ascii") + b"\xc3\x28\xff\n"
    try:
        blob.decode("utf-8")
        raise AssertionError("fixture blob must not be valid UTF-8")
    except UnicodeDecodeError:
        pass
    write(repo_root, "gen/foo/blob.bin", blob)

    result = secret_scanner.scan(repo_root)

    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []


def test_ordinary_lines_with_no_keyword_detector_yield_no_match(repo_root):
    content = (
        "gate_version=GATE_VERSION\n"
        + '{"secret_scanner": "secret_scanner@0.0.0"}\n'
        + "see verification/spec-linter/BOOTSTRAP.md --retry-feedback=R-TRACK-009\n"
    )
    write(repo_root, "gen/foo/ok.py", content)

    result = secret_scanner.scan(repo_root)

    assert field(result, "flagged") is False
    assert list(field(result, "matches")) == []