import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


# Literals are assembled at runtime so this test file itself never holds a
# contiguous credential-shaped or high-entropy literal.
AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
UNUSED_AWS_KEY = "AKIA" + "QRSTUVWXYZABCDEF"
# The git empty-tree object id (4b825dc6...4904) is the SHA-1 of "tree 0\0".
EMPTY_TREE = hashlib.sha1(b"tree 0\x00").hexdigest()

PLANTED_REL = "verification/foo/test_x.py"
GEN_REL = "gen/foo/g.py"


FAKE_CACHE_MANAGER = '''
import datetime
from dataclasses import dataclass
from typing import Any


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
    payload: Any
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}


def main(argv=None):
    return 0
'''


def _field(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _sha1_ref(value):
    return "sha1:" + hashlib.sha1(value.encode("utf-8")).hexdigest()


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _make_repo(tmp_path, name="repo"):
    repo_root = tmp_path / name
    repo_root.mkdir(parents=True)
    _write(repo_root / "gen" / "cache-manager" / "cache_manager.py", FAKE_CACHE_MANAGER)
    return repo_root


def _write_sealed_allowlist(repo_root, entries):
    doc = {"version": 1, "entries": entries}
    data = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    (repo_root / ".secret-allowlist.json").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    decision = (
        "---\n"
        "id: D1\n"
        "title: Ratify the allowlist\n"
        "status: ratified\n"
        "owners: [tester]\n"
        "last_ratified_commit: placeholder\n"
        "allowlist_sha256: sha256:" + digest + "\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "Records the hash of the reviewed allowlist.\n"
    )
    _write(repo_root / "specs" / "decisions" / "D1.md", decision)


def _build_first_scenario_repo(tmp_path, name="repo"):
    repo_root = _make_repo(tmp_path, name)
    _write(repo_root / PLANTED_REL, 'K = "' + AWS_KEY + '"\n')
    _write_sealed_allowlist(
        repo_root,
        [
            {
                "file": PLANTED_REL,
                "type": "AWS Access Key",
                "hashed_secret": _sha1_ref(AWS_KEY),
                "reason": "planted-fixture",
            }
        ],
    )
    return repo_root


@pytest.fixture
def recorder(monkeypatch, tmp_path):
    calls = []

    class _Resp:
        status = 200

        def read(self, *a, **k):
            return b""

        def getcode(self):
            return 200

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _record(*args, **kwargs):
        calls.append((args, kwargs))
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", _record)
    if hasattr(secret_scanner, "urlopen"):
        monkeypatch.setattr(secret_scanner, "urlopen", _record)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(elsewhere)
    return calls


def test_exact_entry_suppresses_planted_fixture_without_notification(tmp_path, monkeypatch, recorder):
    repo_root = _build_first_scenario_repo(tmp_path)
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:9/compliance")

    result = secret_scanner.scan(repo_root)

    assert _field(result, "flagged") is False
    matches = _field(result, "matches")
    assert list(matches or []) == []
    allowed = list(_field(result, "allowed") or [])
    assert len(allowed) == 1, allowed
    entry = allowed[0]
    assert _field(entry, "rule_id") == "AWS Access Key"
    assert _field(entry, "file") == PLANTED_REL
    assert _field(entry, "line") == 1
    assert _field(result, "notified") is False
    assert recorder == []


def test_public_constant_entry_suppresses_hex_string(tmp_path, monkeypatch, recorder):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    repo_root = _make_repo(tmp_path)
    _write(repo_root / GEN_REL, 'EMPTY = "' + EMPTY_TREE + '"\n')
    _write_sealed_allowlist(
        repo_root,
        [
            {
                "file": GEN_REL,
                "type": "Hex High Entropy String",
                "hashed_secret": _sha1_ref(EMPTY_TREE),
                "reason": "public-constant",
            }
        ],
    )

    result = secret_scanner.scan(repo_root)

    assert _field(result, "flagged") is False
    allowed = list(_field(result, "allowed") or [])
    assert any(
        _field(a, "rule_id") == "Hex High Entropy String"
        and _field(a, "file") == GEN_REL
        and _field(a, "line") == 1
        for a in allowed
    ), allowed


def test_entry_matching_nothing_is_reported_unused(tmp_path, monkeypatch, recorder):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    repo_root = _make_repo(tmp_path)
    unused_file = "verification/foo/old.py"
    _write_sealed_allowlist(
        repo_root,
        [
            {
                "file": unused_file,
                "type": "AWS Access Key",
                "hashed_secret": _sha1_ref(UNUSED_AWS_KEY),
                "reason": "planted-fixture",
            }
        ],
    )

    result = secret_scanner.scan(repo_root)

    assert _field(result, "flagged") is False
    assert list(_field(result, "allowed") or []) == []
    unused = list(_field(result, "unused_allowlist_entries") or [])
    assert any(
        _field(u, "file") == unused_file and _field(u, "type") == "AWS Access Key"
        for u in unused
    ), unused


def test_scan_files_honors_allowlist_only_with_repo_root(tmp_path, monkeypatch, recorder):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    repo_root = _build_first_scenario_repo(tmp_path)
    planted = repo_root / PLANTED_REL

    with_root = secret_scanner.scan_files([planted], repo_root=repo_root)
    assert _field(with_root, "flagged") is False

    without_root = secret_scanner.scan_files([planted])
    assert _field(without_root, "flagged") is True
    matches = list(_field(without_root, "matches") or [])
    assert any(_field(m, "rule_id") == "AWS Access Key" for m in matches), matches