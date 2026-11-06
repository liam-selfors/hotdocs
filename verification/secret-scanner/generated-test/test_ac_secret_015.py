import hashlib
import json

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


ORIGINAL_SECRET = "AKIAIOSFODNN7EXAMPLE"
CHANGED_SECRET = "AKIAZZZZYYYYXXXXWWWW"
TEST_X_RELPATH = "verification/foo/test_x.py"


def _sha1_entry(secret):
    return "sha1:" + hashlib.sha1(secret.encode()).hexdigest()


def _allowlist_path(repo_root):
    return repo_root / ".secret-allowlist.json"


def _write_allowlist(repo_root, entries):
    path = _allowlist_path(repo_root)
    path.write_bytes(
        json.dumps({"version": 1, "entries": entries}, indent=2).encode()
    )
    return path


def _seal(repo_root, decision_num=195):
    digest = hashlib.sha256(_allowlist_path(repo_root).read_bytes()).hexdigest()
    decisions_dir = repo_root / "specs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (decisions_dir / f"D{decision_num}.md").write_text(
        "---\n"
        f"id: D{decision_num}\n"
        "title: Seal secret allowlist\n"
        "status: ratified\n"
        "owners: [lselfors@gmail.com]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        f"allowlist_sha256: sha256:{digest}\n"
        "---\n"
        "\n"
        "Seals the secret allowlist.\n"
    )


def _baseline(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "verification" / "foo").mkdir(parents=True)
    (repo_root / TEST_X_RELPATH).write_text(f'K = "{ORIGINAL_SECRET}"\n')
    entry = {
        "file": TEST_X_RELPATH,
        "type": "AWS Access Key",
        "hashed_secret": _sha1_entry(ORIGINAL_SECRET),
        "reason": "planted-fixture",
    }
    _write_allowlist(repo_root, [entry])
    _seal(repo_root)
    return repo_root, entry


def test_changed_secret_becomes_unused_and_flagged(tmp_path):
    repo_root, entry = _baseline(tmp_path)
    (repo_root / TEST_X_RELPATH).write_text(f'K = "{CHANGED_SECRET}"\n')
    _seal(repo_root)

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is True
    matches = _get(result, "matches")
    assert any(
        _get(m, "file") == TEST_X_RELPATH and _get(m, "line") == 1
        for m in matches
    )
    assert _get(result, "allowed") == []
    unused = _get(result, "unused_allowlist_entries")
    assert any(
        _get(u, "file") == entry["file"] and _get(u, "type") == entry["type"]
        for u in unused
    )


def test_same_secret_in_new_file_flags_only_that_file(tmp_path):
    repo_root, _entry = _baseline(tmp_path)
    other_relpath = "verification/foo/other.py"
    (repo_root / other_relpath).write_text(f'K = "{ORIGINAL_SECRET}"\n')
    _seal(repo_root)

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches")
    assert len(matches) == 1
    assert _get(matches[0], "file") == other_relpath

    allowed = _get(result, "allowed")
    assert any(
        _get(a, "file") == TEST_X_RELPATH and _get(a, "line") == 1
        for a in allowed
    )


def test_second_new_secret_is_the_only_match(tmp_path):
    repo_root, _entry = _baseline(tmp_path)
    test_x = repo_root / TEST_X_RELPATH
    test_x.write_text(test_x.read_text() + f'J = "{CHANGED_SECRET}"\n')
    _seal(repo_root)

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches")
    assert len(matches) == 1
    assert _get(matches[0], "file") == TEST_X_RELPATH
    assert _get(matches[0], "line") == 2


def test_entry_type_mismatch_unsuppresses_original_finding(tmp_path):
    repo_root, entry = _baseline(tmp_path)
    mismatched_entry = dict(entry)
    mismatched_entry["type"] = "Hex High Entropy String"
    _write_allowlist(repo_root, [mismatched_entry])
    _seal(repo_root)

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is True
    matches = _get(result, "matches")
    assert any(
        _get(m, "file") == TEST_X_RELPATH and _get(m, "line") == 1
        for m in matches
    )