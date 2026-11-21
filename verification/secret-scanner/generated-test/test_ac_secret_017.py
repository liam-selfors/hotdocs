# hotdocs-criterion: sha256:c8c918231a4529605b806169fdc76fc619c9de5b82187c0595fec0c1ba2848cf
import hashlib
import json
from pathlib import Path

import pytest

import secret_scanner


AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
AWS_KEY_GEN = "AKIA" + "ZZZZYYYYXXXXWWWW"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha1_tag(secret):
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(repo_root, with_c=True):
    write(repo_root / "verification" / "foo" / "t.py", "K = " + repr(AWS_KEY) + "\n")
    write(repo_root / "gen" / "foo" / "g.py", "EMPTY = " + repr(EMPTY_TREE) + "\n")
    if with_c:
        write(repo_root / "gen" / "foo" / "c.py", "C = " + repr(AWS_KEY_GEN) + "\n")


def normalize_entries(entries):
    out = []
    for e in entries:
        out.append(
            {
                "file": field(e, "file"),
                "type": field(e, "type"),
                "hashed_secret": field(e, "hashed_secret"),
                "reason": field(e, "reason"),
            }
        )
    return out


def normalize_ineligible(items):
    out = []
    for i in items:
        out.append(
            {
                "file": field(i, "file"),
                "line": field(i, "line"),
                "rule_id": field(i, "rule_id"),
            }
        )
    return out


EXPECTED_ENTRIES = [
    {
        "file": "gen/foo/g.py",
        "type": "Hex High Entropy String",
        "hashed_secret": sha1_tag(EMPTY_TREE),
        "reason": "public-constant",
    },
    {
        "file": "verification/foo/t.py",
        "type": "AWS Access Key",
        "hashed_secret": sha1_tag(AWS_KEY),
        "reason": "planted-fixture",
    },
]

EXPECTED_INELIGIBLE = [
    {"file": "gen/foo/c.py", "line": 1, "rule_id": "AWS Access Key"},
]


def test_propose_builds_entries_and_ineligible_without_writing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)

    proposal = secret_scanner.propose(repo_root)

    allowlist = field(proposal, "allowlist")
    entries = normalize_entries(field(allowlist, "entries"))
    assert entries == EXPECTED_ENTRIES
    assert [e["file"] for e in entries] == sorted(e["file"] for e in entries)

    ineligible = normalize_ineligible(field(proposal, "ineligible"))
    assert ineligible == EXPECTED_INELIGIBLE

    assert not (repo_root / ".secret-allowlist.json").exists()


def test_propose_keeps_existing_sealed_entry_once(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)

    existing = {
        "version": 1,
        "entries": [
            {
                "file": "verification/foo/t.py",
                "type": "AWS Access Key",
                "hashed_secret": sha1_tag(AWS_KEY),
                "reason": "planted-fixture",
            }
        ],
    }
    allowlist_bytes = (json.dumps(existing, indent=2) + "\n").encode("utf-8")
    allowlist_path = repo_root / ".secret-allowlist.json"
    allowlist_path.write_bytes(allowlist_bytes)
    seal = "sha256:" + hashlib.sha256(allowlist_bytes).hexdigest()

    decision = (
        "---\n"
        + "id: D900\n"
        + "title: Seal the secret allowlist\n"
        + "status: ratified\n"
        + "owners: [security-team]\n"
        + "last_ratified_commit: 0000000\n"
        + "allowlist_sha256: " + seal + "\n"
        + "---\n"
        + "\n"
        + "# D900\n"
        + "\n"
        + "Seals the secret allowlist.\n"
    )
    write(repo_root / "specs" / "decisions" / "D900.md", decision)

    proposal = secret_scanner.propose(repo_root)
    entries = normalize_entries(field(field(proposal, "allowlist"), "entries"))

    matching = [
        e
        for e in entries
        if e["file"] == "verification/foo/t.py"
        and e["type"] == "AWS Access Key"
        and e["hashed_secret"] == sha1_tag(AWS_KEY)
    ]
    assert len(matching) == 1
    assert entries == EXPECTED_ENTRIES
    # propose never writes: the existing file is untouched
    assert allowlist_path.read_bytes() == allowlist_bytes


def test_propose_raises_on_invalid_allowlist(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)
    bad = "{ this is not valid json"
    (repo_root / ".secret-allowlist.json").write_text(bad, encoding="utf-8")

    with pytest.raises(secret_scanner.AllowlistInvalidError):
        secret_scanner.propose(repo_root)

    assert (repo_root / ".secret-allowlist.json").read_text(encoding="utf-8") == bad


def test_main_propose_exit_codes(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)

    capsys.readouterr()
    code = secret_scanner.main(["propose", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    assert "allowlist" in doc
    assert "ineligible" in doc
    assert normalize_entries(doc["allowlist"]["entries"]) == EXPECTED_ENTRIES
    assert normalize_ineligible(doc["ineligible"]) == EXPECTED_INELIGIBLE
    assert not (repo_root / ".secret-allowlist.json").exists()

    (repo_root / "gen" / "foo" / "c.py").unlink()
    code = secret_scanner.main(["propose", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    assert "allowlist" in doc
    assert "ineligible" in doc
    assert doc["ineligible"] == []
    assert not (repo_root / ".secret-allowlist.json").exists()