import contextlib
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

import secret_scanner


SECRET = "AKIAABCDEFGHIJKLMNOP"
SECRET_HASH = hashlib.sha1(SECRET.encode()).hexdigest()


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _valid_entry():
    return {
        "file": "verification/foo/test_x.py",
        "type": "AWS Access Key",
        "hashed_secret": "sha1:" + SECRET_HASH,
        "reason": "planted-fixture",
    }


def _make_repo():
    repo_root = Path(tempfile.mkdtemp(prefix="secret-scan-ac016-"))
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "verification" / "foo").mkdir(parents=True)
    content = 'K = "%s"\n' % SECRET
    (repo_root / "gen" / "foo" / "c.py").write_text(content)
    (repo_root / "verification" / "foo" / "test_x.py").write_text(content)
    return repo_root


def _write_allowlist(repo_root, obj_or_raw):
    path = repo_root / ".secret-allowlist.json"
    if isinstance(obj_or_raw, str):
        path.write_text(obj_or_raw)
    else:
        path.write_text(json.dumps(obj_or_raw))


def _find(matches, rule_id, file, line=None):
    for m in matches:
        if _get(m, "rule_id") == rule_id and _get(m, "file") == file:
            if line is None or _get(m, "line") == line:
                return m
    return None


@contextlib.contextmanager
def _no_webhook_env():
    saved = os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = saved


def _assert_common_invariants(result):
    flagged = _get(result, "flagged")
    matches = _get(result, "matches")
    assert flagged is True

    aws_gen = _find(matches, "AWS Access Key", "gen/foo/c.py", 1)
    assert aws_gen is not None, "expected AWS Access Key match for gen/foo/c.py"

    aws_ver = _find(matches, "AWS Access Key", "verification/foo/test_x.py", 1)
    assert aws_ver is not None, (
        "expected AWS Access Key match for verification/foo/test_x.py"
    )

    invalid = _find(matches, "allowlist-invalid", ".secret-allowlist.json", 1)
    assert invalid is not None, "expected allowlist-invalid match"
    assert _get(invalid, "risk_tier") == "high"


def _build_corruptions():
    cases = []

    cases.append(("not_valid_json", "{this is not json"))

    cases.append((
        "extra_top_level_key",
        {"version": 1, "entries": [_valid_entry()], "extra": "x"},
    ))

    cases.append((
        "version_2",
        {"version": 2, "entries": [_valid_entry()]},
    ))

    entry = _valid_entry()
    entry["note"] = "unexpected"
    cases.append(("entry_extra_key", {"version": 1, "entries": [entry]}))

    entry = _valid_entry()
    del entry["reason"]
    cases.append(("entry_missing_key", {"version": 1, "entries": [entry]}))

    entry = _valid_entry()
    entry["reason"] = "other"
    cases.append(("entry_reason_other", {"version": 1, "entries": [entry]}))

    entry = _valid_entry()
    entry["hashed_secret"] = SECRET_HASH
    cases.append(("entry_hash_no_prefix", {"version": 1, "entries": [entry]}))

    for bad_file in ("../x.py", "/etc/x", "verification/*.py"):
        entry = _valid_entry()
        entry["file"] = bad_file
        label = "entry_bad_file_" + bad_file.replace("/", "_").replace(
            ".", "_"
        ).replace("*", "star")
        cases.append((label, {"version": 1, "entries": [entry]}))

    entry = _valid_entry()
    entry["file"] = "gen/foo/c.py"
    entry["reason"] = "planted-fixture"
    cases.append((
        "planted_fixture_outside_verification_or_specs",
        {"version": 1, "entries": [entry]},
    ))

    entry = _valid_entry()
    entry["reason"] = "public-constant"
    entry["type"] = "AWS Access Key"
    cases.append((
        "public_constant_with_wrong_type",
        {"version": 1, "entries": [entry]},
    ))

    corrupt_entry = _valid_entry()
    corrupt_entry["reason"] = "other"
    second_entry = {
        "file": "specs/bar.py",
        "type": "Hex High Entropy String",
        "hashed_secret": "sha1:" + hashlib.sha1(b"unrelated").hexdigest(),
        "reason": "public-constant",
    }
    cases.append((
        "second_valid_entry_beside_corrupt_one",
        {"version": 1, "entries": [corrupt_entry, second_entry]},
    ))

    return cases


_CASES = _build_corruptions()


@pytest.mark.parametrize(
    "name,allowlist_obj", _CASES, ids=[c[0] for c in _CASES]
)
def test_corrupt_allowlist_invalidates_whole_file(name, allowlist_obj):
    repo_root = _make_repo()
    try:
        with _no_webhook_env():
            _write_allowlist(repo_root, allowlist_obj)
            result = secret_scanner.scan(repo_root)
            _assert_common_invariants(result)
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)


def test_extra_key_with_aws_value_also_flags_allowlist_file_itself():
    repo_root = _make_repo()
    try:
        with _no_webhook_env():
            entry = _valid_entry()
            allowlist_obj = {
                "version": 1,
                "entries": [entry],
                "decoy": "AKIAZZZZYYYYXXXXWWWW",
            }
            _write_allowlist(repo_root, allowlist_obj)
            result = secret_scanner.scan(repo_root)
            _assert_common_invariants(result)

            matches = _get(result, "matches")
            allowlist_self_match = _find(
                matches, "AWS Access Key", ".secret-allowlist.json"
            )
            assert allowlist_self_match is not None, (
                "expected the allowlist file itself to be scanned and "
                "flagged for its own planted AWS-like value"
            )
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)


def test_no_allowlist_file_allows_nothing():
    repo_root = _make_repo()
    try:
        with _no_webhook_env():
            result = secret_scanner.scan(repo_root)

            assert _get(result, "flagged") is True
            matches = _get(result, "matches")
            assert (
                _find(matches, "allowlist-invalid", ".secret-allowlist.json")
                is None
            )
            allowed = _get(result, "allowed", [])
            assert len(allowed) == 0
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)