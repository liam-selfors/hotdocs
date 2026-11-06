import hashlib
import json

import pytest

import secret_scanner


SECRET = "AKIAABCDEFGHIJKLMNOP"
RULE_ID = "AWS Access Key"
TARGET_FILE = "verification/foo/t.py"


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _sha1_hex(value):
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    path.write_bytes(data)


def _allowlist_bytes(entries):
    doc = {"version": 1, "entries": entries}
    return json.dumps(doc, indent=2).encode("utf-8")


def _entry():
    return {
        "file": TARGET_FILE,
        "type": RULE_ID,
        "hashed_secret": "sha1:" + _sha1_hex(SECRET),
        "reason": "planted-fixture",
    }


def _decision_text(decision_id, status, allowlist_sha256_hex):
    lines = [
        "---",
        "id: D{}".format(decision_id),
        "title: Seal secret allowlist revision {}".format(decision_id),
        "status: {}".format(status),
        "owners: [lselfors@gmail.com]",
    ]
    if status == "ratified":
        lines.append(
            "last_ratified_commit: 0000000000000000000000000000000000000000"
        )
    lines.append("allowlist_sha256: sha256:{}".format(allowlist_sha256_hex))
    lines.append("---")
    lines.append("")
    lines.append("Decision body for D{}.".format(decision_id))
    lines.append("")
    return "\n".join(lines)


def _flip_first_char(hex_digest):
    replacement = "0" if hex_digest[0] != "0" else "1"
    return replacement + hex_digest[1:]


def _base_repo(tmp_path):
    repo_root = tmp_path / "repo"
    _write(repo_root / TARGET_FILE, 'K = "{}"\n'.format(SECRET))
    return repo_root


def _finding_matches(matches):
    return [m for m in matches if _get(m, "rule_id") == RULE_ID]


def _invalid_matches(matches):
    return [m for m in matches if _get(m, "rule_id") == "allowlist-invalid"]


@pytest.fixture(autouse=True)
def _no_webhook(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)


def test_sealed_valid_allowlist_suppresses_finding(tmp_path):
    repo_root = _base_repo(tmp_path)
    allowlist_bytes = _allowlist_bytes([_entry()])
    _write(repo_root / ".secret-allowlist.json", allowlist_bytes)
    digest = _sha256_hex(allowlist_bytes)
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        _decision_text(1, "ratified", digest),
    )

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches")
    allowed = _get(result, "allowed")
    assert len(_finding_matches(matches)) == 0
    assert len(_invalid_matches(matches)) == 0
    assert _get(result, "flagged") is False
    allowed_for_file = [
        a
        for a in allowed
        if _get(a, "rule_id") == RULE_ID and _get(a, "file") == TARGET_FILE
    ]
    assert len(allowed_for_file) == 1


def _assert_invalid_and_reported(repo_root):
    result = secret_scanner.scan(repo_root)
    matches = _get(result, "matches")

    assert len(_finding_matches(matches)) == 1

    invalid = _invalid_matches(matches)
    assert len(invalid) == 1
    assert _get(invalid[0], "risk_tier") == "high"
    assert _get(invalid[0], "file") == ".secret-allowlist.json"
    assert _get(invalid[0], "line") == 1

    assert _get(result, "flagged") is True
    assert len(_get(result, "allowed")) == 0


def test_file_changed_by_one_byte_invalidates_seal(tmp_path):
    repo_root = _base_repo(tmp_path)
    allowlist_bytes = _allowlist_bytes([_entry()])
    digest = _sha256_hex(allowlist_bytes)
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        _decision_text(1, "ratified", digest),
    )
    changed_bytes = allowlist_bytes + b" "
    _write(repo_root / ".secret-allowlist.json", changed_bytes)

    _assert_invalid_and_reported(repo_root)


def test_decision_hash_changed_invalidates_seal(tmp_path):
    repo_root = _base_repo(tmp_path)
    allowlist_bytes = _allowlist_bytes([_entry()])
    _write(repo_root / ".secret-allowlist.json", allowlist_bytes)
    real_digest = _sha256_hex(allowlist_bytes)
    wrong_digest = _flip_first_char(real_digest)
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        _decision_text(1, "ratified", wrong_digest),
    )

    _assert_invalid_and_reported(repo_root)


def test_decision_not_ratified_invalidates_seal(tmp_path):
    repo_root = _base_repo(tmp_path)
    allowlist_bytes = _allowlist_bytes([_entry()])
    _write(repo_root / ".secret-allowlist.json", allowlist_bytes)
    digest = _sha256_hex(allowlist_bytes)
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        _decision_text(1, "draft", digest),
    )

    _assert_invalid_and_reported(repo_root)


def test_no_decision_invalidates_seal(tmp_path):
    repo_root = _base_repo(tmp_path)
    allowlist_bytes = _allowlist_bytes([_entry()])
    _write(repo_root / ".secret-allowlist.json", allowlist_bytes)

    _assert_invalid_and_reported(repo_root)


def test_other_ratified_decision_with_different_hash_invalidates_seal(tmp_path):
    repo_root = _base_repo(tmp_path)
    allowlist_bytes = _allowlist_bytes([_entry()])
    _write(repo_root / ".secret-allowlist.json", allowlist_bytes)
    real_digest = _sha256_hex(allowlist_bytes)
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        _decision_text(1, "ratified", real_digest),
    )
    wrong_digest = _flip_first_char(real_digest)
    _write(
        repo_root / "specs" / "decisions" / "D2.md",
        _decision_text(2, "ratified", wrong_digest),
    )

    _assert_invalid_and_reported(repo_root)


def test_empty_allowlist_needs_no_seal(tmp_path):
    repo_root = _base_repo(tmp_path)
    allowlist_bytes = _allowlist_bytes([])
    _write(repo_root / ".secret-allowlist.json", allowlist_bytes)

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches")
    assert len(_finding_matches(matches)) == 1
    assert len(_invalid_matches(matches)) == 0
    assert _get(result, "flagged") is True