# hotdocs-criterion: sha256:8b7bef8f5aa0218e3d8eaa5c77ecaa5fa1db75dfcdf7d836516c85cdf5c4090f
"""AC-SECRET-017 — propose(repo_root) returns a complete allowlist proposal
without writing anything (R-SECRET-013)."""

import hashlib
import json
from pathlib import Path

import pytest

import secret_scanner


AWS_T = "AKIAABCDEFGHIJKLMNOP"
HEX_G = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
AWS_C = "AKIAZZZZYYYYXXXXWWWW"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha1_tag(secret):
    return "sha1:" + hashlib.sha1(secret.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(repo_root, with_c=True):
    write(repo_root / "verification" / "foo" / "t.py", "K = " + repr(AWS_T) + "\n")
    write(repo_root / "gen" / "foo" / "g.py", "EMPTY = " + repr(HEX_G) + "\n")
    if with_c:
        write(repo_root / "gen" / "foo" / "c.py", "C = " + repr(AWS_C) + "\n")


def norm_entry(entry):
    return {
        "file": field(entry, "file"),
        "type": field(entry, "type"),
        "hashed_secret": field(entry, "hashed_secret"),
        "reason": field(entry, "reason"),
    }


def norm_ineligible(item):
    return {
        "file": field(item, "file"),
        "line": field(item, "line"),
        "rule_id": field(item, "rule_id"),
    }


def entries_of(proposal):
    allowlist = field(proposal, "allowlist")
    return list(field(allowlist, "entries"))


def write_sealed_allowlist(repo_root, entries):
    doc = {"version": 1, "entries": entries}
    data = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (repo_root / ".secret-allowlist.json").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    decision = (
        "---\n"
        "id: D900\n"
        "title: Seal the secret allowlist\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "last_ratified_commit: 0000000\n"
        "allowlist_sha256: sha256:" + digest + "\n"
        "---\n"
        "\n"
        "# D900\n"
        "\n"
        "Seals the secret allowlist.\n"
    )
    write(repo_root / "specs" / "decisions" / "D900.md", decision)


EXPECTED_ENTRIES = [
    {
        "file": "gen/foo/g.py",
        "type": "Hex High Entropy String",
        "hashed_secret": sha1_tag(HEX_G),
        "reason": "public-constant",
    },
    {
        "file": "verification/foo/t.py",
        "type": "AWS Access Key",
        "hashed_secret": sha1_tag(AWS_T),
        "reason": "planted-fixture",
    },
]

EXPECTED_INELIGIBLE = [
    {"file": "gen/foo/c.py", "line": 1, "rule_id": "AWS Access Key"},
]


def test_propose_returns_entries_and_ineligible_without_writing(tmp_path):
    build_repo(tmp_path)

    proposal = secret_scanner.propose(tmp_path)

    entries = [norm_entry(e) for e in entries_of(proposal)]
    assert entries == EXPECTED_ENTRIES

    ineligible = [norm_ineligible(i) for i in field(proposal, "ineligible")]
    assert ineligible == EXPECTED_INELIGIBLE

    assert not (tmp_path / ".secret-allowlist.json").exists()


def test_propose_keeps_existing_entry_once(tmp_path):
    build_repo(tmp_path)
    existing = {
        "file": "verification/foo/t.py",
        "type": "AWS Access Key",
        "hashed_secret": sha1_tag(AWS_T),
        "reason": "planted-fixture",
    }
    write_sealed_allowlist(tmp_path, [existing])

    proposal = secret_scanner.propose(tmp_path)

    entries = [norm_entry(e) for e in entries_of(proposal)]
    assert entries.count(existing) == 1
    t_entries = [e for e in entries if e["file"] == "verification/foo/t.py"]
    assert len(t_entries) == 1


@pytest.mark.parametrize("kind", ["malformed", "unsealed"])
def test_propose_raises_on_invalid_allowlist(tmp_path, kind):
    build_repo(tmp_path)
    if kind == "malformed":
        (tmp_path / ".secret-allowlist.json").write_text("{not json", encoding="utf-8")
    else:
        doc = {
            "version": 1,
            "entries": [
                {
                    "file": "verification/foo/t.py",
                    "type": "AWS Access Key",
                    "hashed_secret": sha1_tag(AWS_T),
                    "reason": "planted-fixture",
                }
            ],
        }
        (tmp_path / ".secret-allowlist.json").write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8"
        )

    with pytest.raises(secret_scanner.AllowlistInvalidError):
        secret_scanner.propose(tmp_path)


def test_main_propose_exit_codes(tmp_path, capsys):
    build_repo(tmp_path)

    code = secret_scanner.main(["propose", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    assert set(doc.keys()) == {"allowlist", "ineligible"}
    assert [norm_entry(e) for e in doc["allowlist"]["entries"]] == EXPECTED_ENTRIES
    assert [norm_ineligible(i) for i in doc["ineligible"]] == EXPECTED_INELIGIBLE
    assert not (tmp_path / ".secret-allowlist.json").exists()

    (tmp_path / "gen" / "foo" / "c.py").unlink()

    code = secret_scanner.main(["propose", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    assert set(doc.keys()) == {"allowlist", "ineligible"}
    assert doc["ineligible"] == []