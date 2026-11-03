import hashlib
import json
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _hash_secret(secret: str) -> str:
    return "sha1:" + hashlib.sha1(secret.encode()).hexdigest()


ORIGINAL_KEY = "AKIAIOSFODNN7EXAMPLE"
CHANGED_KEY = "AKIAZZZZYYYYXXXXWWWW"


def _write_base(root: Path) -> Path:
    verif_dir = root / "verification" / "foo"
    verif_dir.mkdir(parents=True)
    test_x = verif_dir / "test_x.py"
    test_x.write_text('K = "%s"\n' % ORIGINAL_KEY)
    allowlist = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/test_x.py",
                "type": "AWS Access Key",
                "hashed_secret": _hash_secret(ORIGINAL_KEY),
                "reason": "planted-fixture",
            }
        ],
    }
    (root / ".secret-allowlist.json").write_text(json.dumps(allowlist))
    return test_x


def test_changed_line_unsuppresses_and_orphans_entry(tmp_path):
    test_x = _write_base(tmp_path)
    test_x.write_text('K = "%s"\n' % CHANGED_KEY)

    result = secret_scanner.scan(tmp_path)

    assert _get(result, "flagged") is True

    matches = _get(result, "matches")
    assert len(matches) == 1
    assert _get(matches[0], "file") == "verification/foo/test_x.py"
    assert _get(matches[0], "line") == 1
    assert _get(matches[0], "rule_id") == "AWS Access Key"

    assert _get(result, "allowed") == []

    unused = _get(result, "unused_allowlist_entries")
    assert len(unused) == 1
    assert _get(unused[0], "file") == "verification/foo/test_x.py"
    assert _get(unused[0], "type") == "AWS Access Key"


def test_duplicate_key_in_new_file_only_new_one_matches(tmp_path):
    _write_base(tmp_path)
    other_file = tmp_path / "verification" / "foo" / "other.py"
    other_file.write_text('OTHER = "%s"\n' % ORIGINAL_KEY)

    result = secret_scanner.scan(tmp_path)

    matches = _get(result, "matches")
    assert len(matches) == 1
    assert _get(matches[0], "file") == "verification/foo/other.py"

    allowed = _get(result, "allowed")
    assert len(allowed) == 1
    assert _get(allowed[0], "file") == "verification/foo/test_x.py"


def test_second_line_added_only_new_line_matches(tmp_path):
    test_x = _write_base(tmp_path)
    with test_x.open("a") as f:
        f.write('J = "%s"\n' % CHANGED_KEY)

    result = secret_scanner.scan(tmp_path)

    matches = _get(result, "matches")
    assert len(matches) == 1
    assert _get(matches[0], "file") == "verification/foo/test_x.py"
    assert _get(matches[0], "line") == 2
    assert _get(matches[0], "rule_id") == "AWS Access Key"


def test_entry_type_changed_unsuppresses_original_finding(tmp_path):
    _write_base(tmp_path)
    allowlist_path = tmp_path / ".secret-allowlist.json"
    data = json.loads(allowlist_path.read_text())
    data["entries"][0]["type"] = "Hex High Entropy String"
    allowlist_path.write_text(json.dumps(data))

    result = secret_scanner.scan(tmp_path)

    assert _get(result, "flagged") is True

    matches = _get(result, "matches")
    found = any(
        _get(m, "file") == "verification/foo/test_x.py" and _get(m, "line") == 1
        for m in matches
    )
    assert found