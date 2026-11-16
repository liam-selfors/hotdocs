import hashlib
import json
import os
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


# Built by concatenation so this test file itself carries no detectable literal.
SECRET_A = "AKIA" + "ABCDEFGHIJKLMNOP"
SECRET_Z = "AKIA" + "ZZZZYYYYXXXXWWWW"

TEST_X = "verification/foo/test_x.py"
GEN_C = "gen/foo/c.py"
ALLOWLIST = ".secret-allowlist.json"
AWS = "AWS Access Key"


FAKE_CACHE_MANAGER = '''\
from dataclasses import dataclass
from datetime import datetime, timezone


class SchemaValidationError(ValueError):
    pass


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None


def stats(*, repo_root=None):
    return {"entry_count": 0}


def main(argv=None):
    return 0
'''


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _sha1_entry_hash(secret):
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


def _valid_entry():
    return {
        "file": TEST_X,
        "type": AWS,
        "hashed_secret": _sha1_entry_hash(SECRET_A),
        "reason": "planted-fixture",
    }


def _valid_doc():
    return {"version": 1, "entries": [_valid_entry()]}


def _dump(doc):
    return (json.dumps(doc, indent=2) + "\n").encode("utf-8")


def _write_base_repo(root: Path):
    (root / "verification" / "foo").mkdir(parents=True)
    (root / "gen" / "foo").mkdir(parents=True)
    line = 'K = "' + SECRET_A + '"\n'
    (root / TEST_X).write_text(line, encoding="utf-8")
    (root / GEN_C).write_text(line, encoding="utf-8")
    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")


def _write_allowlist_sealed(root: Path, data: bytes):
    (root / ALLOWLIST).write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    decisions = root / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    (decisions / "D1.md").write_text(
        "---\n"
        "id: D1\n"
        "title: Seal the secret allowlist\n"
        "status: ratified\n"
        "owners: [tester]\n"
        "last_ratified_commit: placeholder\n"
        "allowlist_sha256: sha256:" + digest + "\n"
        "---\n"
        "\n"
        "Records the hash of the current secret allowlist.\n",
        encoding="utf-8",
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    class _Resp:
        status = 200

        def read(self):
            return b""

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(*args, **kwargs):
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    root = tmp_path / "repo"
    root.mkdir()
    _write_base_repo(root)
    monkeypatch.chdir(root)
    return root


def _matches(result):
    return list(_field(result, "matches") or [])


def _allowed(result):
    return list(_field(result, "allowed") or [])


def _has_aws_match(matches, file):
    for m in matches:
        if _field(m, "rule_id") == AWS and _field(m, "file") == file:
            return True
    return False


def _invalid_matches(matches):
    return [m for m in matches if _field(m, "rule_id") == "allowlist-invalid"]


# --- corruptions -------------------------------------------------------------


def _not_json():
    return b'{"version": 1, "entries": [\n'


def _top_level_extra_key():
    doc = _valid_doc()
    doc["extra"] = 1
    return _dump(doc)


def _version_two():
    doc = _valid_doc()
    doc["version"] = 2
    return _dump(doc)


def _entry_extra_key():
    doc = _valid_doc()
    doc["entries"][0]["note"] = "x"
    return _dump(doc)


def _entry_missing_key():
    doc = _valid_doc()
    del doc["entries"][0]["reason"]
    return _dump(doc)


def _reason_other():
    doc = _valid_doc()
    doc["entries"][0]["reason"] = "other"
    return _dump(doc)


def _hash_without_prefix():
    doc = _valid_doc()
    doc["entries"][0]["hashed_secret"] = hashlib.sha1(SECRET_A.encode("utf-8")).hexdigest()
    return _dump(doc)


def _file_dotdot():
    doc = _valid_doc()
    doc["entries"][0]["file"] = "../x.py"
    return _dump(doc)


def _file_absolute():
    doc = _valid_doc()
    doc["entries"][0]["file"] = "/etc/x"
    return _dump(doc)


def _file_pattern():
    doc = _valid_doc()
    doc["entries"][0]["file"] = "verification/*.py"
    return _dump(doc)


def _planted_fixture_outside_verification():
    doc = _valid_doc()
    doc["entries"][0]["file"] = GEN_C
    return _dump(doc)


def _public_constant_for_aws():
    doc = _valid_doc()
    doc["entries"][0]["reason"] = "public-constant"
    return _dump(doc)


def _valid_beside_corrupt():
    doc = _valid_doc()
    doc["entries"].append(
        {
            "file": GEN_C,
            "type": AWS,
            "hashed_secret": _sha1_entry_hash(SECRET_A),
            "reason": "other",
        }
    )
    return _dump(doc)


CORRUPTIONS = [
    ("not-valid-json", _not_json),
    ("top-level-extra-key", _top_level_extra_key),
    ("version-2", _version_two),
    ("entry-extra-key", _entry_extra_key),
    ("entry-missing-key", _entry_missing_key),
    ("reason-other", _reason_other),
    ("hash-without-sha1-prefix", _hash_without_prefix),
    ("file-dotdot", _file_dotdot),
    ("file-absolute", _file_absolute),
    ("file-pattern", _file_pattern),
    ("planted-fixture-under-gen", _planted_fixture_outside_verification),
    ("public-constant-for-aws", _public_constant_for_aws),
    ("valid-entry-beside-corrupt", _valid_beside_corrupt),
]


def _assert_invalid_allowlist_result(result):
    assert _field(result, "flagged") is True
    matches = _matches(result)
    assert _has_aws_match(matches, TEST_X), matches
    assert _has_aws_match(matches, GEN_C), matches
    invalid = _invalid_matches(matches)
    assert len(invalid) == 1, matches
    m = invalid[0]
    assert _field(m, "rule_id") == "allowlist-invalid"
    assert _field(m, "risk_tier") == "high"
    assert _field(m, "file") == ".secret-allowlist.json"
    assert _field(m, "line") == 1
    assert _allowed(result) == []


def test_control_valid_sealed_allowlist_is_honored(repo):
    _write_allowlist_sealed(repo, _dump(_valid_doc()))
    result = secret_scanner.scan(repo)
    matches = _matches(result)
    assert _invalid_matches(matches) == [], matches
    assert _has_aws_match(matches, GEN_C), matches
    assert not _has_aws_match(matches, TEST_X), matches
    allowed = _allowed(result)
    assert any(
        _field(a, "rule_id") == AWS and _field(a, "file") == TEST_X for a in allowed
    ), allowed


@pytest.mark.parametrize("make", [c[1] for c in CORRUPTIONS], ids=[c[0] for c in CORRUPTIONS])
def test_corrupt_allowlist_invalidates_whole_allowlist(repo, make):
    _write_allowlist_sealed(repo, make())
    result = secret_scanner.scan(repo)
    _assert_invalid_allowlist_result(result)


def test_allowlist_itself_is_scanned(repo):
    doc = _valid_doc()
    doc["note"] = SECRET_Z
    _write_allowlist_sealed(repo, _dump(doc))
    result = secret_scanner.scan(repo)
    _assert_invalid_allowlist_result(result)
    matches = _matches(result)
    assert any(
        _field(m, "rule_id") == AWS and _field(m, "file") == ".secret-allowlist.json"
        for m in matches
    ), matches


def test_absent_allowlist_allows_nothing_and_is_not_invalid(repo):
    assert not (repo / ALLOWLIST).exists()
    result = secret_scanner.scan(repo)
    assert _field(result, "flagged") is True
    matches = _matches(result)
    assert _invalid_matches(matches) == [], matches
    assert _allowed(result) == []
    assert _has_aws_match(matches, TEST_X), matches
    assert _has_aws_match(matches, GEN_C), matches