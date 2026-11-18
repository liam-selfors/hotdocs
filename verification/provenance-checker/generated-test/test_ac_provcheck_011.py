# hotdocs-criterion: sha256:624984df431fdfa04f17fc20aca28b3d675054c083ea9e58900784c05719047b
import hashlib
from pathlib import Path

import pytest

import provenance_checker


GATE = "verifier-orchestrator@2.0.0"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)


def write_fake_verifier(repo_root):
    src = "GATE_VERSION = " + repr(GATE) + "\n"
    write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", src)


def write_component(repo_root, slug, frontmatter_lines):
    text = (
        "---\n"
        + "".join(line + "\n" for line in frontmatter_lines)
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Foo doubles a number.\n"
    )
    write(repo_root / "specs" / "components" / slug / "component.md", text)


def base_lines(slug="foo"):
    return [
        "id: comp-" + slug,
        "title: Foo",
        "status: draft",
    ]


def make_root(tmp_path, name):
    root = tmp_path / name
    root.mkdir(parents=True)
    write_fake_verifier(root)
    return root


def expected_hash(entries):
    h = hashlib.sha256()
    for rel, content in entries:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(content)
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()


def test_sealed_key_fields_and_hash(tmp_path):
    repo_root = make_root(tmp_path, "main")
    write_component(
        repo_root,
        "foo",
        base_lines()
        + [
            "owners: [pipeline-team, alice]",
            "sealed: true",
            "source_path: pipeline/foo/",
            "depends_on: []",
        ],
    )
    write(repo_root / "pipeline" / "foo" / "a.py", b"A=1\n")
    write(repo_root / "pipeline" / "foo" / "sub" / "b.py", b"B=2\n")

    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    assert list(field(key, "owners")) == ["pipeline-team", "alice"]
    assert field(key, "source_path") == "pipeline/foo/"
    assert field(key, "verifier_version") == GATE

    want = expected_hash([("a.py", b"A=1\n"), ("sub/b.py", b"B=2\n")])
    first_hash = field(key, "source_hash")
    assert first_hash == want

    # Excluded entries do not affect the hash.
    write(repo_root / "pipeline" / "foo" / "__pycache__" / "x.pyc", b"\x00\x01garbage")
    write(repo_root / "pipeline" / "foo" / ".sealed-provenance.json", b'{"anything": 1}')

    key2 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key2 is not None
    assert field(key2, "source_hash") == first_hash

    # A content change changes the hash.
    write(repo_root / "pipeline" / "foo" / "a.py", b"A=2\n")
    key3 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key3 is not None
    third_hash = field(key3, "source_hash")
    assert third_hash != first_hash
    assert third_hash == expected_hash([("a.py", b"A=2\n"), ("sub/b.py", b"B=2\n")])


def test_not_sealed_returns_none(tmp_path):
    repo_root = make_root(tmp_path, "unsealed")
    write_component(
        repo_root,
        "bar",
        base_lines("bar")
        + [
            "owners: [pipeline-team]",
            "sealed: false",
            "source_path: pipeline/bar/",
            "depends_on: []",
        ],
    )
    write(repo_root / "pipeline" / "bar" / "a.py", b"A=1\n")
    assert provenance_checker.current_sealed_key("comp-bar", repo_root) is None


def test_missing_component_md_returns_none(tmp_path):
    repo_root = make_root(tmp_path, "missing")
    assert not (repo_root / "specs" / "components" / "baz" / "component.md").exists()
    assert provenance_checker.current_sealed_key("comp-baz", repo_root) is None


@pytest.mark.parametrize(
    "case,lines",
    [
        (
            "no_owners",
            [
                "sealed: true",
                "source_path: pipeline/foo/",
                "depends_on: []",
            ],
        ),
        (
            "bad_owner",
            [
                "owners: [Alice]",
                "sealed: true",
                "source_path: pipeline/foo/",
                "depends_on: []",
            ],
        ),
        (
            "no_source_path",
            [
                "owners: [pipeline-team]",
                "sealed: true",
                "depends_on: []",
            ],
        ),
    ],
)
def test_invalid_sealed_frontmatter_raises(tmp_path, case, lines):
    repo_root = make_root(tmp_path, case)
    write_component(repo_root, "foo", base_lines() + lines)
    write(repo_root / "pipeline" / "foo" / "a.py", b"A=1\n")
    with pytest.raises(ValueError):
        provenance_checker.current_sealed_key("comp-foo", repo_root)