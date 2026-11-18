# hotdocs-criterion: sha256:3151255d2b8f70a05e083ac3687d19ca1778d541327e6d090c52f9099bd196ad
"""AC-SECRET-001 (covers R-SECRET-001): full-scan coverage, skips, and match shape."""

import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


KEY_LINE = 'K = "AKIAABCDEFGHIJKLMNOP"\n'
KEY_TEXT = "AKIAABCDEFGHIJKLMNOP"


# A stand-in cache-manager matching comp-cache-manager's documented interface.
# It deliberately embeds no long random-looking literal and no temp path.
CACHE_MANAGER_STANDIN = '''\
from dataclasses import dataclass
from datetime import datetime, timezone


class SchemaValidationError(ValueError):
    pass


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


REQUIRED = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def _read(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_type = _read(result, "gate_type")
    key_version = str(_read(cache_key, "gate_version") or "")
    if gate_type not in REQUIRED:
        raise SchemaValidationError("unknown gate type")
    if key_version.split("@")[0] != gate_type:
        raise SchemaValidationError("gate type mismatch")
    payload = _read(result, "payload")
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload not a dict")
    for name in REQUIRED[gate_type]:
        if name not in payload:
            raise SchemaValidationError("missing payload key")
    return None


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write_text(root: Path, rel: str, content: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_bytes(root: Path, rel: str, content: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _write_text(root, "gen/cache-manager/cache_manager.py", CACHE_MANAGER_STANDIN)
    assert not (root / ".secret-allowlist.json").exists()

    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    def _no_network(*args, **kwargs):
        raise AssertionError("urlopen must not be called without a configured webhook")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    monkeypatch.chdir(root)
    return root


def _matches(result):
    matches = _field(result, "matches")
    assert matches is not None, "result must carry matches"
    return list(matches)


def test_single_key_in_gen_reports_one_high_aws_match(repo_root):
    _write_text(repo_root, "gen/foo/config.py", KEY_LINE)

    result = secret_scanner.scan(repo_root)

    matches = _matches(result)
    assert len(matches) == 1, matches
    match = matches[0]
    assert _field(match, "rule_id") == "AWS Access Key"
    assert _field(match, "risk_tier") == "high"
    assert _field(match, "file") == "gen/foo/config.py"
    assert _field(match, "line") == 1
    assert _field(result, "flagged") is True

    # A match never carries the secret itself.
    if isinstance(match, dict):
        rendered = repr(sorted(match.items(), key=lambda kv: str(kv[0])))
    else:
        rendered = repr(vars(match)) if hasattr(match, "__dict__") else repr(match)
    assert KEY_TEXT not in rendered


def test_key_found_in_every_ordinary_location(repo_root):
    files = [
        "README.md",
        "notes/n.md",
        "pipeline/p.py",
        "tools/t.py",
        "verification/secret-scanner/generated-test/test_x.py",
    ]
    for rel in files:
        _write_text(repo_root, rel, KEY_LINE)

    result = secret_scanner.scan(repo_root)

    matches = _matches(result)
    assert _field(result, "flagged") is True
    matched_files = {_field(m, "file") for m in matches}
    for rel in files:
        assert rel in matched_files, f"no match reported for {rel}: {matches}"
    for rel in files:
        rule_ids = {_field(m, "rule_id") for m in matches if _field(m, "file") == rel}
        assert "AWS Access Key" in rule_ids, (rel, rule_ids)


def test_skipped_directories_and_non_utf8_files(repo_root):
    for rel in [
        "gen/foo/__pycache__/x.txt",
        ".git/config",
        ".venv/lib/x.py",
        ".hotdocs/x.json",
        ".pytest_cache/x.txt",
        "node_modules/x.js",
    ]:
        _write_text(repo_root, rel, KEY_LINE)

    blob = b"\xff\xfe\x80\x81 binary\n" + KEY_LINE.encode("ascii") + b"\xc3\x28\xff\n"
    try:
        blob.decode("utf-8")
        decodes = True
    except UnicodeDecodeError:
        decodes = False
    assert not decodes, "fixture blob must not be valid UTF-8"
    assert KEY_TEXT.encode("ascii") in blob
    _write_bytes(repo_root, "gen/foo/blob.bin", blob)

    result = secret_scanner.scan(repo_root)

    assert _field(result, "flagged") is False
    assert _matches(result) == []


def test_ordinary_identifiers_and_versions_are_not_flagged(repo_root):
    content = (
        "gate_version=GATE_VERSION\n"
        '{"secret_scanner": "secret_scanner@0.0.0"}\n'
        "see verification/spec-linter/BOOTSTRAP.md --retry-feedback=R-TRACK-009\n"
    )
    _write_text(repo_root, "gen/foo/ok.py", content)

    result = secret_scanner.scan(repo_root)

    assert _field(result, "flagged") is False
    assert _matches(result) == []