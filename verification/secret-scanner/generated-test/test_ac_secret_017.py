import hashlib
import json

import pytest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _build_full_repo(root):
    (root / "verification" / "foo").mkdir(parents=True)
    (root / "verification" / "foo" / "t.py").write_text(
        'K = "AKIAABCDEFGHIJKLMNOP"\n'
    )
    (root / "gen" / "foo").mkdir(parents=True)
    (root / "gen" / "foo" / "g.py").write_text(
        'EMPTY = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"\n'
    )
    (root / "gen" / "foo" / "c.py").write_text(
        'C = "AKIAZZZZYYYYXXXXWWWW"\n'
    )


def test_propose_returns_allowlist_and_ineligible_without_writing(tmp_path):
    _build_full_repo(tmp_path)

    result = secret_scanner.propose(tmp_path)

    allowlist = _get(result, "allowlist")
    entries = _get(allowlist, "entries")
    ineligible = _get(result, "ineligible")

    assert entries is not None
    assert len(entries) == 2

    k_hash = hashlib.sha1(b"AKIAABCDEFGHIJKLMNOP").hexdigest()
    empty_hash = hashlib.sha1(
        b"4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    ).hexdigest()

    entry0, entry1 = entries[0], entries[1]

    assert _get(entry0, "file") == "gen/foo/g.py"
    assert _get(entry0, "type") == "Hex High Entropy String"
    assert _get(entry0, "reason") == "public-constant"
    assert _get(entry0, "hashed_secret") == f"sha1:{empty_hash}"

    assert _get(entry1, "file") == "verification/foo/t.py"
    assert _get(entry1, "type") == "AWS Access Key"
    assert _get(entry1, "reason") == "planted-fixture"
    assert _get(entry1, "hashed_secret") == f"sha1:{k_hash}"

    assert ineligible is not None
    assert len(ineligible) == 1
    ineligible_entry = ineligible[0]
    assert _get(ineligible_entry, "file") == "gen/foo/c.py"
    assert _get(ineligible_entry, "line") == 1
    assert _get(ineligible_entry, "rule_id") == "AWS Access Key"

    assert not (tmp_path / ".secret-allowlist.json").exists()


def test_propose_existing_sealed_entry_appears_once(tmp_path):
    (tmp_path / "verification" / "foo").mkdir(parents=True)
    (tmp_path / "verification" / "foo" / "t.py").write_text(
        'K = "AKIAABCDEFGHIJKLMNOP"\n'
    )

    k_hash = hashlib.sha1(b"AKIAABCDEFGHIJKLMNOP").hexdigest()
    allowlist_doc = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/t.py",
                "type": "AWS Access Key",
                "hashed_secret": f"sha1:{k_hash}",
                "reason": "planted-fixture",
            }
        ],
    }
    allowlist_text = json.dumps(allowlist_doc, indent=2) + "\n"
    (tmp_path / ".secret-allowlist.json").write_text(allowlist_text)

    seal_hash = hashlib.sha256(allowlist_text.encode()).hexdigest()
    (tmp_path / "specs" / "decisions").mkdir(parents=True)
    decision_text = (
        "---\n"
        "id: D900\n"
        "title: Seal allowlist for AC-SECRET-017 fixture\n"
        "status: ratified\n"
        "owners: [lselfors]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        f"allowlist_sha256: sha256:{seal_hash}\n"
        "---\n\n"
        "Seals the allowlist for the AC-SECRET-017 test fixture.\n"
    )
    (tmp_path / "specs" / "decisions" / "D900.md").write_text(decision_text)

    result = secret_scanner.propose(tmp_path)

    allowlist = _get(result, "allowlist")
    entries = _get(allowlist, "entries")

    matching = [e for e in entries if _get(e, "file") == "verification/foo/t.py"]
    assert len(matching) == 1
    assert _get(matching[0], "hashed_secret") == f"sha1:{k_hash}"
    assert _get(matching[0], "reason") == "planted-fixture"


def test_propose_raises_on_invalid_allowlist(tmp_path):
    invalid_doc = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/t.py",
                "type": "AWS Access Key",
                "hashed_secret": "sha1:deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                "reason": "planted-fixture",
            }
        ],
    }
    (tmp_path / ".secret-allowlist.json").write_text(json.dumps(invalid_doc))

    with pytest.raises(secret_scanner.AllowlistInvalidError):
        secret_scanner.propose(tmp_path)


def test_main_propose_cli_exit_codes(tmp_path, capsys):
    _build_full_repo(tmp_path)

    exit_code = secret_scanner.main(["propose", f"--repo-root={tmp_path}"])
    captured = capsys.readouterr()

    assert exit_code == 1
    payload = json.loads(captured.out)
    assert set(payload.keys()) == {"allowlist", "ineligible"}

    (tmp_path / "gen" / "foo" / "c.py").unlink()

    exit_code2 = secret_scanner.main(["propose", f"--repo-root={tmp_path}"])
    capsys.readouterr()

    assert exit_code2 == 0