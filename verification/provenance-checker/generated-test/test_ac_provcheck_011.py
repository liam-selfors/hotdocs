# hotdocs-criterion: sha256:2cf7eba6056b83692b51da314fb859aa3949a687aa43c779660671393e512a22
import hashlib
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def plant_python_adapter(repo_root):
    src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr({
            "ok": True,
            "reason": "",
            "versions": {"python": "3.12.4", "packages": PK},
            "lockfile_sha256": None,
            "interpreter": "/fake/python",
        }) + "\n"
    )
    write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def plant_verifier(repo_root):
    src = (
        "GATE_VERSION = " + repr("verifier-orchestrator@2.0.0") + "\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    raise RuntimeError(" + repr("verify must not be called") + ")\n"
    )
    write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        src,
    )


def component_md(slug, lines):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Fixture " + slug + "\n"
        + "status: draft\n"
        + "".join(line + "\n" for line in lines)
        + "---\n"
        + "\n"
        + "# Fixture " + slug + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A fixture component.\n"
    )


def plant_component(repo_root, slug, lines):
    write(
        repo_root / "specs" / "components" / slug / "component.md",
        component_md(slug, lines),
    )


def expected_hash(entries):
    h = hashlib.sha256()
    for rel, data in entries:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    plant_python_adapter(root)
    plant_verifier(root)
    plant_component(
        root,
        "foo",
        [
            "owners: [pipeline-team, alice]",
            "sealed: true",
            "source_path: pipeline/foo/",
        ],
    )
    write(root / "pipeline" / "foo" / "a.py", "A=1\n")
    write(root / "pipeline" / "foo" / "sub" / "b.py", "B=2\n")
    return root


def test_sealed_key_fields_and_hash(repo_root):
    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    assert list(field(key, "owners")) == ["pipeline-team", "alice"]
    assert field(key, "source_path") == "pipeline/foo/"
    assert field(key, "verifier_version") == "verifier-orchestrator@2.0.0"
    want = expected_hash([("a.py", b"A=1\n"), ("sub/b.py", b"B=2\n")])
    assert field(key, "source_hash") == want


def test_pycache_and_manifest_excluded_and_content_change_detected(repo_root):
    first = provenance_checker.current_sealed_key("comp-foo", repo_root)
    first_hash = field(first, "source_hash")

    foo = repo_root / "pipeline" / "foo"
    (foo / "__pycache__").mkdir()
    (foo / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01garbage-bytecode")
    (foo / ".sealed-provenance.json").write_bytes(b'{"anything": true}\n')

    second = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert field(second, "source_hash") == first_hash

    (foo / "a.py").write_bytes(b"A=2\n")
    third = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert field(third, "source_hash") != first_hash
    assert field(third, "source_hash") == expected_hash(
        [("a.py", b"A=2\n"), ("sub/b.py", b"B=2\n")]
    )


def test_unsealed_and_missing_component_return_none(repo_root):
    plant_component(
        repo_root,
        "bar",
        [
            "owners: [pipeline-team]",
            "sealed: false",
            "source_path: pipeline/bar/",
        ],
    )
    write(repo_root / "pipeline" / "bar" / "c.py", "C=3\n")
    assert provenance_checker.current_sealed_key("comp-bar", repo_root) is None
    assert not (repo_root / "specs" / "components" / "baz").exists()
    assert provenance_checker.current_sealed_key("comp-baz", repo_root) is None


@pytest.mark.parametrize(
    "slug,lines",
    [
        ("noowners", ["sealed: true", "source_path: pipeline/noowners/"]),
        (
            "badowners",
            ["owners: [Alice]", "sealed: true", "source_path: pipeline/badowners/"],
        ),
        ("nosource", ["owners: [pipeline-team, alice]", "sealed: true"]),
    ],
)
def test_invalid_sealed_frontmatter_raises(repo_root, slug, lines):
    plant_component(repo_root, slug, lines)
    write(repo_root / "pipeline" / slug / "m.py", "M=1\n")
    with pytest.raises(ValueError):
        provenance_checker.current_sealed_key("comp-" + slug, repo_root)