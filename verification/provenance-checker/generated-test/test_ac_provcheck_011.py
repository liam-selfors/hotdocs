import hashlib
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_VERIFIER = 'GATE_VERSION = "verifier-orchestrator@2.0.0"\n\n\ndef verify(component_id, repo_root, judge=None, test_author=None):\n    raise RuntimeError("verify must not be called by current_sealed_key")\n'


def write_fake_verifier(repo_root: Path) -> None:
    d = repo_root / "gen" / "verifier-orchestrator"
    d.mkdir(parents=True, exist_ok=True)
    (d / "verifier_orchestrator.py").write_text(FAKE_VERIFIER, encoding="utf-8")


def write_component(repo_root: Path, slug: str, extra_lines) -> None:
    d = repo_root / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"id: comp-{slug}",
        f"title: {slug.capitalize()}",
        "status: draft",
    ]
    lines.extend(extra_lines)
    lines.append("depends_on: []")
    lines.append("---")
    lines.append("")
    lines.append(f"# {slug.capitalize()}")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(f"{slug.capitalize()} doubles a number.")
    lines.append("")
    (d / "component.md").write_text("\n".join(lines), encoding="utf-8")


def expected_hash(entries):
    h = hashlib.sha256()
    for rel, content in entries:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(content)
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()


def test_current_sealed_key_sealed_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fake_verifier(repo_root)
    write_component(
        repo_root,
        "foo",
        [
            "owners: [pipeline-team, alice]",
            "sealed: true",
            "source_path: pipeline/foo/",
        ],
    )
    src = repo_root / "pipeline" / "foo"
    (src / "sub").mkdir(parents=True)
    (src / "a.py").write_bytes(b"A=1\n")
    (src / "sub" / "b.py").write_bytes(b"B=2\n")

    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    assert list(field(key, "owners")) == ["pipeline-team", "alice"]
    assert field(key, "source_path") == "pipeline/foo/"
    assert field(key, "verifier_version") == "verifier-orchestrator@2.0.0"

    want = expected_hash([("a.py", b"A=1\n"), ("sub/b.py", b"B=2\n")])
    first_hash = field(key, "source_hash")
    assert first_hash == want

    # Excluded entries do not change the hash.
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01garbage pyc bytes")
    (src / ".sealed-provenance.json").write_text('{"anything": true}\n', encoding="utf-8")

    key2 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key2 is not None
    assert field(key2, "source_hash") == first_hash

    # A content change does change the hash.
    (src / "a.py").write_bytes(b"A=2\n")
    key3 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key3 is not None
    assert field(key3, "source_hash") != first_hash
    assert field(key3, "source_hash") == expected_hash(
        [("a.py", b"A=2\n"), ("sub/b.py", b"B=2\n")]
    )


def test_current_sealed_key_returns_none_when_not_sealed_or_missing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fake_verifier(repo_root)
    write_component(
        repo_root,
        "bar",
        [
            "owners: [team-a]",
            "sealed: false",
            "source_path: legacy/bar/",
        ],
    )
    (repo_root / "legacy" / "bar").mkdir(parents=True)
    (repo_root / "legacy" / "bar" / "bar.py").write_bytes(b"X=1\n")

    assert provenance_checker.current_sealed_key("comp-bar", repo_root) is None
    assert provenance_checker.current_sealed_key("comp-nothere", repo_root) is None


@pytest.mark.parametrize(
    "lines",
    [
        # no owners line
        ["sealed: true", "source_path: legacy/baz/"],
        # owners failing SealedProvenance rules (uppercase)
        ["owners: [Alice]", "sealed: true", "source_path: legacy/baz/"],
        # no source_path line
        ["owners: [team-a]", "sealed: true"],
    ],
    ids=["no-owners", "owners-uppercase", "no-source-path"],
)
def test_current_sealed_key_raises_value_error_on_bad_frontmatter(tmp_path, lines):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fake_verifier(repo_root)
    write_component(repo_root, "baz", lines)
    (repo_root / "legacy" / "baz").mkdir(parents=True)
    (repo_root / "legacy" / "baz" / "baz.py").write_bytes(b"Z=1\n")

    with pytest.raises(ValueError):
        provenance_checker.current_sealed_key("comp-baz", repo_root)