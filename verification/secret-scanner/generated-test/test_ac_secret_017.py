# hotdocs-criterion: sha256:2d5e949391e0380ee75698a3767ff26c4016372a1b580000f91f906fca406c6b
import hashlib
import json
import sys
from pathlib import Path

import pytest

import secret_scanner


T_KEY = "AKIAABCDEFGHIJKLMNOP"
G_HEX = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
C_KEY = "AKIAZZZZYYYYXXXXWWWW"


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _sha1(secret):
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root, include_c=True):
    _write(root / "verification" / "foo" / "t.py", 'K = "%s"\n' % T_KEY)
    _write(root / "gen" / "foo" / "g.py", 'EMPTY = "%s"\n' % G_HEX)
    if include_c:
        _write(root / "gen" / "foo" / "c.py", 'C = "%s"\n' % C_KEY)
    return root


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    import urllib.request

    def _no_network(*args, **kwargs):
        raise AssertionError("propose must not make network calls")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)


def _entries(proposal):
    allowlist = _get(proposal, "allowlist")
    assert allowlist is not None
    entries = _get(allowlist, "entries")
    assert entries is not None
    return list(entries)


def _entry_tuple(entry):
    return (
        _get(entry, "file"),
        _get(entry, "type"),
        _get(entry, "hashed_secret"),
        _get(entry, "reason"),
    )


def _ineligible_tuples(proposal):
    inel = _get(proposal, "ineligible")
    assert inel is not None
    return [
        (_get(i, "file"), _get(i, "line"), _get(i, "rule_id")) for i in inel
    ]


def _check_sorted(entries):
    keys = [
        (_get(e, "file"), _get(e, "type"), _get(e, "hashed_secret"))
        for e in entries
    ]
    assert keys == sorted(keys)


def test_propose_builds_complete_allowlist_without_writing(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")

    proposal = secret_scanner.propose(repo_root)

    entries = _entries(proposal)
    tuples = [_entry_tuple(e) for e in entries]
    assert tuples == [
        ("gen/foo/g.py", "Hex High Entropy String", _sha1(G_HEX), "public-constant"),
        ("verification/foo/t.py", "AWS Access Key", _sha1(T_KEY), "planted-fixture"),
    ]
    _check_sorted(entries)

    allowlist = _get(proposal, "allowlist")
    assert _get(allowlist, "version") == 1

    assert _ineligible_tuples(proposal) == [("gen/foo/c.py", 1, "AWS Access Key")]

    assert not (repo_root / ".secret-allowlist.json").exists()


def test_propose_keeps_existing_sealed_entry_once(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")

    existing = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/t.py",
                "type": "AWS Access Key",
                "hashed_secret": _sha1(T_KEY),
                "reason": "planted-fixture",
            }
        ],
    }
    allowlist_path = repo_root / ".secret-allowlist.json"
    allowlist_bytes = (json.dumps(existing, indent=2) + "\n").encode("utf-8")
    allowlist_path.write_bytes(allowlist_bytes)
    seal = hashlib.sha256(allowlist_bytes).hexdigest()

    _write(
        repo_root / "specs" / "decisions" / "D900.md",
        "---\n"
        "id: D900\n"
        "title: Seal secret allowlist\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: placeholder\n"
        "allowlist_sha256: sha256:" + seal + "\n"
        "---\n"
        "\n"
        "Seals the secret allowlist.\n",
    )

    proposal = secret_scanner.propose(repo_root)

    entries = _entries(proposal)
    matching = [
        e
        for e in entries
        if _get(e, "file") == "verification/foo/t.py"
        and _get(e, "type") == "AWS Access Key"
        and _get(e, "hashed_secret") == _sha1(T_KEY)
    ]
    assert len(matching) == 1
    assert _get(matching[0], "reason") == "planted-fixture"
    _check_sorted(entries)

    assert ("gen/foo/c.py", 1, "AWS Access Key") in _ineligible_tuples(proposal)

    # propose writes nothing: the existing allowlist is untouched
    assert allowlist_path.read_bytes() == allowlist_bytes


def test_propose_raises_on_malformed_allowlist(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")
    (repo_root / ".secret-allowlist.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(secret_scanner.AllowlistInvalidError):
        secret_scanner.propose(repo_root)


def test_propose_raises_on_unsealed_nonempty_allowlist(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")
    existing = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/t.py",
                "type": "AWS Access Key",
                "hashed_secret": _sha1(T_KEY),
                "reason": "planted-fixture",
            }
        ],
    }
    (repo_root / ".secret-allowlist.json").write_text(
        json.dumps(existing, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(secret_scanner.AllowlistInvalidError):
        secret_scanner.propose(repo_root)


def _run_main(argv):
    try:
        rc = secret_scanner.main(argv)
    except SystemExit as exc:
        rc = exc.code
    return rc


def test_main_propose_exit_codes_and_json(tmp_path, capsys):
    repo_root = _build_repo(tmp_path / "repo")

    capsys.readouterr()
    rc = _run_main(["propose", "--repo-root=%s" % repo_root])
    out = capsys.readouterr().out
    assert rc == 1
    data = json.loads(out)
    assert isinstance(data, dict)
    assert "allowlist" in data
    assert "ineligible" in data
    assert len(data["allowlist"]["entries"]) == 2
    assert [
        (i.get("file"), i.get("line"), i.get("rule_id")) for i in data["ineligible"]
    ] == [("gen/foo/c.py", 1, "AWS Access Key")]
    assert not (repo_root / ".secret-allowlist.json").exists()

    (repo_root / "gen" / "foo" / "c.py").unlink()

    rc2 = _run_main(["propose", "--repo-root=%s" % repo_root])
    out2 = capsys.readouterr().out
    assert rc2 == 0
    data2 = json.loads(out2)
    assert "allowlist" in data2
    assert "ineligible" in data2
    assert data2["ineligible"] == []
    assert len(data2["allowlist"]["entries"]) == 2
    assert not (repo_root / ".secret-allowlist.json").exists()