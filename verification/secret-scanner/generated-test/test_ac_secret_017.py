import hashlib
import json
from pathlib import Path

import pytest

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _sha1(secret: str) -> str:
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


K_SECRET = "AKIAABCDEFGHIJKLMNOP"
EMPTY_SECRET = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
C_SECRET = "AKIAZZZZYYYYXXXXWWWW"


def _make_three_file_repo(repo_root: Path) -> None:
    _write(repo_root / "verification" / "foo" / "t.py", 'K = "%s"\n' % K_SECRET)
    _write(repo_root / "gen" / "foo" / "g.py", 'EMPTY = "%s"\n' % EMPTY_SECRET)
    _write(repo_root / "gen" / "foo" / "c.py", 'C = "%s"\n' % C_SECRET)


def test_propose_builds_allowlist_and_ineligible_without_writing(tmp_path):
    repo_root = tmp_path
    _make_three_file_repo(repo_root)

    result = secret_scanner.propose(repo_root)

    allowlist = _get(result, "allowlist")
    entries = _get(allowlist, "entries")
    ineligible = _get(result, "ineligible")

    assert len(entries) == 2

    files = [_get(e, "file") for e in entries]
    assert set(files) == {"verification/foo/t.py", "gen/foo/g.py"}
    assert files == sorted(files)

    by_file = {_get(e, "file"): e for e in entries}

    t_entry = by_file["verification/foo/t.py"]
    assert _get(t_entry, "type") == "AWS Access Key"
    assert _get(t_entry, "reason") == "planted-fixture"
    assert _get(t_entry, "hashed_secret") == _sha1(K_SECRET)

    g_entry = by_file["gen/foo/g.py"]
    assert _get(g_entry, "type") == "Hex High Entropy String"
    assert _get(g_entry, "reason") == "public-constant"
    assert _get(g_entry, "hashed_secret") == _sha1(EMPTY_SECRET)

    assert len(ineligible) == 1
    ie = ineligible[0]
    assert _get(ie, "file") == "gen/foo/c.py"
    assert _get(ie, "line") == 1
    assert _get(ie, "rule_id") == "AWS Access Key"

    assert not (repo_root / ".secret-allowlist.json").exists()


def test_propose_does_not_duplicate_existing_allowlist_entry(tmp_path):
    repo_root = tmp_path
    _write(repo_root / "verification" / "foo" / "t.py", 'K = "%s"\n' % K_SECRET)

    existing_allowlist = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/t.py",
                "type": "AWS Access Key",
                "hashed_secret": _sha1(K_SECRET),
                "reason": "planted-fixture",
            }
        ],
    }
    _write(
        repo_root / ".secret-allowlist.json",
        json.dumps(existing_allowlist),
    )

    result = secret_scanner.propose(repo_root)

    allowlist = _get(result, "allowlist")
    entries = _get(allowlist, "entries")
    ineligible = _get(result, "ineligible")

    matching = [e for e in entries if _get(e, "file") == "verification/foo/t.py"]
    assert len(matching) == 1
    assert _get(matching[0], "hashed_secret") == _sha1(K_SECRET)
    assert len(entries) == 1
    assert ineligible == []


def test_propose_raises_on_invalid_allowlist(tmp_path):
    repo_root = tmp_path
    _write(repo_root / "verification" / "foo" / "t.py", 'K = "%s"\n' % K_SECRET)
    _write(repo_root / ".secret-allowlist.json", "{this is not valid json")

    with pytest.raises(secret_scanner.AllowlistInvalidError):
        secret_scanner.propose(repo_root)


def test_cli_propose_exit_codes_and_json_keys(tmp_path, capsys):
    repo_root = tmp_path
    _make_three_file_repo(repo_root)

    exit_code = secret_scanner.main(["propose", "--repo-root=%s" % repo_root])
    captured = capsys.readouterr()

    assert exit_code == 1

    payload = json.loads(captured.out)
    assert set(payload.keys()) == {"allowlist", "ineligible"}

    (repo_root / "gen" / "foo" / "c.py").unlink()

    exit_code_clean = secret_scanner.main(["propose", "--repo-root=%s" % repo_root])
    assert exit_code_clean == 0