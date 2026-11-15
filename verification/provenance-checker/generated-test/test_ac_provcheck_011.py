import hashlib
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)


def _component_md(slug, frontmatter_lines):
    lines = ["---", f"id: comp-{slug}", f"title: {slug.capitalize()}", "status: draft"]
    lines.extend(frontmatter_lines)
    lines.append("depends_on: []")
    lines.append("---")
    body = "\n".join(lines) + "\n\n# " + slug.capitalize() + "\n\n## Purpose\n\nA test component.\n"
    return body


def _plant_verifier(repo_root: Path):
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        'GATE_VERSION = "verifier-orchestrator@2.0.0"\n',
    )


def _build_foo(repo_root: Path):
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        _component_md(
            "foo",
            [
                "owners: [pipeline-team, alice]",
                "sealed: true",
                "source_path: pipeline/foo/",
            ],
        ),
    )
    _write(repo_root / "pipeline" / "foo" / "a.py", "A=1\n")
    _write(repo_root / "pipeline" / "foo" / "sub" / "b.py", "B=2\n")
    _plant_verifier(repo_root)


def _expected_hash(entries):
    h = hashlib.sha256()
    for rel, content in entries:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(content)
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()


def test_sealed_key_fields_and_hash_behaviour(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_foo(repo_root)

    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    assert list(field(key, "owners")) == ["pipeline-team", "alice"]
    assert field(key, "source_path") == "pipeline/foo/"
    assert field(key, "verifier_version") == "verifier-orchestrator@2.0.0"

    expected = _expected_hash([("a.py", b"A=1\n"), ("sub/b.py", b"B=2\n")])
    first_hash = field(key, "source_hash")
    assert first_hash == expected

    # Excluded entries never affect the hash.
    _write(repo_root / "pipeline" / "foo" / "__pycache__" / "x.pyc", b"\x00\x01garbage-bytes")
    _write(repo_root / "pipeline" / "foo" / ".sealed-provenance.json", '{"anything": true}\n')

    key2 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key2 is not None
    assert field(key2, "source_hash") == first_hash

    # A content change changes the hash.
    _write(repo_root / "pipeline" / "foo" / "a.py", "A=2\n")
    key3 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key3 is not None
    assert field(key3, "source_hash") != first_hash
    assert field(key3, "source_hash") == _expected_hash(
        [("a.py", b"A=2\n"), ("sub/b.py", b"B=2\n")]
    )


def test_not_sealed_or_missing_component_returns_none(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_verifier(repo_root)

    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        _component_md(
            "bar",
            [
                "owners: [pipeline-team]",
                "sealed: false",
                "source_path: pipeline/bar/",
            ],
        ),
    )
    _write(repo_root / "pipeline" / "bar" / "bar.py", "X=1\n")

    assert provenance_checker.current_sealed_key("comp-bar", repo_root) is None
    # comp-baz has no component.md at all.
    assert provenance_checker.current_sealed_key("comp-baz", repo_root) is None


@pytest.mark.parametrize(
    "slug,lines",
    [
        ("noowners", ["sealed: true", "source_path: pipeline/noowners/"]),
        (
            "badowners",
            ["owners: [Alice]", "sealed: true", "source_path: pipeline/badowners/"],
        ),
        ("nosrc", ["owners: [pipeline-team]", "sealed: true"]),
    ],
)
def test_invalid_sealed_frontmatter_raises_value_error(tmp_path, slug, lines):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_verifier(repo_root)
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        _component_md(slug, lines),
    )
    _write(repo_root / "pipeline" / slug / "m.py", "M=1\n")

    with pytest.raises(ValueError):
        provenance_checker.current_sealed_key(f"comp-{slug}", repo_root)