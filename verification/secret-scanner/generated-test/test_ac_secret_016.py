import hashlib
import json
import textwrap

import pytest

import secret_scanner


AWS_SECRET = "AKIAABCDEFGHIJKLMNOP"
AWS_SECRET_LITERAL = "AKIAZZZZYYYYXXXXWWWW"


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _sha1_prefixed(secret):
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


def _base_valid_entry():
    return {
        "file": "verification/foo/test_x.py",
        "type": "AWS Access Key",
        "hashed_secret": _sha1_prefixed(AWS_SECRET),
        "reason": "planted-fixture",
    }


def _entries_json(obj):
    return json.dumps(obj, indent=2).encode("utf-8")


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "verification" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "verification" / "foo" / "test_x.py").write_text(
        'K = "%s"\n' % AWS_SECRET, encoding="utf-8"
    )
    (repo_root / "gen" / "foo" / "c.py").write_text(
        'K = "%s"\n' % AWS_SECRET, encoding="utf-8"
    )
    return repo_root


def _write_allowlist_sealed(repo_root, content_bytes):
    allowlist_path = repo_root / ".secret-allowlist.json"
    allowlist_path.write_bytes(content_bytes)
    digest = hashlib.sha256(content_bytes).hexdigest()
    decisions_dir = repo_root / "specs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    decision_path = decisions_dir / "D1.md"
    body = textwrap.dedent(
        """\
        ---
        id: D1
        title: Seal secret allowlist
        status: ratified
        owners: [lselfors@gmail.com]
        last_ratified_commit: %s
        allowlist_sha256: sha256:%s
        ---

        Seals the secret allowlist for AC-SECRET-016 fixtures.
        """
    ) % ("0" * 40, digest)
    decision_path.write_text(body, encoding="utf-8")


def _assert_common(result):
    assert _get(result, "flagged") is True
    matches = _get(result, "matches")

    def _has(rule_id, file_, risk_tier=None, line=None):
        for m in matches:
            if _get(m, "rule_id") != rule_id or _get(m, "file") != file_:
                continue
            if risk_tier is not None and _get(m, "risk_tier") != risk_tier:
                continue
            if line is not None and _get(m, "line") != line:
                continue
            return True
        return False

    assert _has("AWS Access Key", "verification/foo/test_x.py", "high", 1)
    assert _has("AWS Access Key", "gen/foo/c.py", "high", 1)
    assert _has("allowlist-invalid", ".secret-allowlist.json", "high", 1)


CORRUPTIONS = {}


def _reg(name):
    def deco(fn):
        CORRUPTIONS[name] = fn
        return fn

    return deco


@_reg("invalid_json")
def _c_invalid_json():
    return b'{"version": 1, "entries": [ this is not json'


@_reg("top_level_extra_key")
def _c_top_level_extra_key():
    return _entries_json(
        {"version": 1, "entries": [_base_valid_entry()], "extra": "x"}
    )


@_reg("version_2")
def _c_version_2():
    return _entries_json({"version": 2, "entries": [_base_valid_entry()]})


@_reg("entry_extra_key")
def _c_entry_extra_key():
    e = _base_valid_entry()
    e["note"] = "hi"
    return _entries_json({"version": 1, "entries": [e]})


@_reg("entry_missing_key")
def _c_entry_missing_key():
    e = _base_valid_entry()
    del e["reason"]
    return _entries_json({"version": 1, "entries": [e]})


@_reg("entry_reason_other")
def _c_entry_reason_other():
    e = _base_valid_entry()
    e["reason"] = "other"
    return _entries_json({"version": 1, "entries": [e]})


@_reg("entry_hash_no_prefix")
def _c_entry_hash_no_prefix():
    e = _base_valid_entry()
    e["hashed_secret"] = hashlib.sha1(AWS_SECRET.encode("utf-8")).hexdigest()
    return _entries_json({"version": 1, "entries": [e]})


@_reg("entry_file_dotdot")
def _c_entry_file_dotdot():
    e = _base_valid_entry()
    e["file"] = "../x.py"
    return _entries_json({"version": 1, "entries": [e]})


@_reg("entry_file_absolute")
def _c_entry_file_absolute():
    e = _base_valid_entry()
    e["file"] = "/etc/x"
    return _entries_json({"version": 1, "entries": [e]})


@_reg("entry_file_pattern")
def _c_entry_file_pattern():
    e = _base_valid_entry()
    e["file"] = "verification/*.py"
    return _entries_json({"version": 1, "entries": [e]})


@_reg("entry_planted_fixture_wrong_location")
def _c_entry_planted_fixture_wrong_location():
    e = {
        "file": "gen/foo/c.py",
        "type": "AWS Access Key",
        "hashed_secret": _sha1_prefixed(AWS_SECRET),
        "reason": "planted-fixture",
    }
    return _entries_json({"version": 1, "entries": [e]})


@_reg("entry_public_constant_wrong_type")
def _c_entry_public_constant_wrong_type():
    e = _base_valid_entry()
    e["reason"] = "public-constant"
    return _entries_json({"version": 1, "entries": [e]})


@_reg("second_valid_entry_beside_corrupt")
def _c_second_valid_entry_beside_corrupt():
    good = _base_valid_entry()
    corrupt = _base_valid_entry()
    corrupt["file"] = "verification/foo/other.py"
    corrupt["reason"] = "other"
    return _entries_json({"version": 1, "entries": [good, corrupt]})


@pytest.mark.parametrize("name", sorted(CORRUPTIONS))
def test_corrupted_allowlist_invalidates(tmp_path, name):
    repo_root = _make_repo(tmp_path)
    content = CORRUPTIONS[name]()
    _write_allowlist_sealed(repo_root, content)

    result = secret_scanner.scan(repo_root)

    _assert_common(result)


def test_entry_extra_key_with_embedded_secret_scans_allowlist_itself(tmp_path):
    repo_root = _make_repo(tmp_path)
    e = _base_valid_entry()
    e["note"] = AWS_SECRET_LITERAL
    content = _entries_json({"version": 1, "entries": [e]})
    _write_allowlist_sealed(repo_root, content)

    result = secret_scanner.scan(repo_root)

    _assert_common(result)
    matches = _get(result, "matches")
    assert any(
        _get(m, "rule_id") == "AWS Access Key"
        and _get(m, "file") == ".secret-allowlist.json"
        for m in matches
    )


def test_no_allowlist_file_allows_nothing(tmp_path):
    repo_root = _make_repo(tmp_path)

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is True
    matches = _get(result, "matches")
    assert not any(_get(m, "rule_id") == "allowlist-invalid" for m in matches)
    assert _get(result, "allowed") == []