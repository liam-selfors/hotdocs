import hashlib
import json

import secret_scanner


SECRET = "AKIAABCDEFGHIJKLMNOP"
SECRET_SHA1 = hashlib.sha1(SECRET.encode("utf-8")).hexdigest()


def get_field(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "verification" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    secret_line = f'K = "{SECRET}"\n'
    (repo_root / "verification" / "foo" / "test_x.py").write_text(secret_line)
    (repo_root / "gen" / "foo" / "c.py").write_text(secret_line)
    return repo_root


def valid_entry():
    return {
        "file": "verification/foo/test_x.py",
        "type": "AWS Access Key",
        "hashed_secret": f"sha1:{SECRET_SHA1}",
        "reason": "planted-fixture",
    }


def to_bytes(obj):
    return json.dumps(obj, indent=2, sort_keys=True).encode("utf-8")


def seal_allowlist(repo_root, raw_bytes, decision_num=900):
    allowlist_path = repo_root / ".secret-allowlist.json"
    allowlist_path.write_bytes(raw_bytes)
    digest = hashlib.sha256(raw_bytes).hexdigest()
    decisions_dir = repo_root / "specs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    decision_path = decisions_dir / f"D{decision_num}.md"
    decision_path.write_text(
        "---\n"
        f"id: D{decision_num}\n"
        "title: Seal fixture allowlist\n"
        "status: ratified\n"
        "owners: [tester]\n"
        f"allowlist_sha256: sha256:{digest}\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "Seals the fixture allowlist for AC-SECRET-016.\n"
    )


def run_scenario(tmp_path, raw_bytes):
    repo_root = make_repo(tmp_path)
    seal_allowlist(repo_root, raw_bytes)
    return secret_scanner.scan(repo_root)


def assert_common_invalid(result):
    flagged = get_field(result, "flagged")
    matches = get_field(result, "matches") or []
    assert flagged is True
    aws_files = {
        get_field(m, "file")
        for m in matches
        if get_field(m, "rule_id") == "AWS Access Key"
    }
    assert "gen/foo/c.py" in aws_files
    assert "verification/foo/test_x.py" in aws_files
    invalid_matches = [
        m for m in matches if get_field(m, "rule_id") == "allowlist-invalid"
    ]
    assert len(invalid_matches) == 1
    inv = invalid_matches[0]
    assert get_field(inv, "risk_tier") == "high"
    assert get_field(inv, "file") == ".secret-allowlist.json"
    assert get_field(inv, "line") == 1
    return matches


def test_not_valid_json(tmp_path):
    raw_bytes = b'{"version": 1, "entries": [this is not json]'
    result = run_scenario(tmp_path, raw_bytes)
    assert_common_invalid(result)


def test_top_level_extra_key(tmp_path):
    obj = {"version": 1, "entries": [valid_entry()], "notes": "extra"}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_top_level_version_2(tmp_path):
    obj = {"version": 2, "entries": [valid_entry()]}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_entry_extra_key(tmp_path):
    entry = valid_entry()
    entry["comment"] = "extra"
    obj = {"version": 1, "entries": [entry]}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_entry_missing_key(tmp_path):
    entry = valid_entry()
    del entry["reason"]
    obj = {"version": 1, "entries": [entry]}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_entry_reason_other(tmp_path):
    entry = valid_entry()
    entry["reason"] = "other"
    obj = {"version": 1, "entries": [entry]}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_entry_hashed_secret_missing_prefix(tmp_path):
    entry = valid_entry()
    entry["hashed_secret"] = SECRET_SHA1
    obj = {"version": 1, "entries": [entry]}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_entry_file_is_pattern(tmp_path):
    entry = valid_entry()
    entry["file"] = "verification/*.py"
    obj = {"version": 1, "entries": [entry]}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_entry_planted_fixture_wrong_location(tmp_path):
    entry = {
        "file": "gen/foo/c.py",
        "type": "AWS Access Key",
        "hashed_secret": f"sha1:{SECRET_SHA1}",
        "reason": "planted-fixture",
    }
    obj = {"version": 1, "entries": [entry]}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_entry_public_constant_wrong_type(tmp_path):
    entry = valid_entry()
    entry["reason"] = "public-constant"
    obj = {"version": 1, "entries": [entry]}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_second_valid_entry_beside_corrupt(tmp_path):
    corrupt_entry = valid_entry()
    corrupt_entry["reason"] = "other"
    obj = {"version": 1, "entries": [valid_entry(), corrupt_entry]}
    result = run_scenario(tmp_path, to_bytes(obj))
    assert_common_invalid(result)


def test_extra_key_with_secret_value_allowlist_itself_scanned(tmp_path):
    obj = {
        "version": 1,
        "entries": [valid_entry()],
        "spare": "AKIAZZZZYYYYXXXXWWWW",
    }
    result = run_scenario(tmp_path, to_bytes(obj))
    matches = assert_common_invalid(result)
    allowlist_aws_matches = [
        m
        for m in matches
        if get_field(m, "rule_id") == "AWS Access Key"
        and get_field(m, "file") == ".secret-allowlist.json"
    ]
    assert len(allowlist_aws_matches) == 1


def test_no_allowlist_file_at_all(tmp_path):
    repo_root = make_repo(tmp_path)
    result = secret_scanner.scan(repo_root)
    flagged = get_field(result, "flagged")
    matches = get_field(result, "matches") or []
    allowed = get_field(result, "allowed")
    assert flagged is True
    assert not any(get_field(m, "rule_id") == "allowlist-invalid" for m in matches)
    assert allowed == []