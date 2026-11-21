# hotdocs-criterion: sha256:90467c18bdebb3d480fc6e3d9226447103897be277c3c11b5b43715195f48f61
import hashlib
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def write_component(repo_root, slug, lines):
    text = "---\n" + "\n".join(lines) + "\n---\n\n# " + slug + "\n\n## Purpose\n\nFixture.\n"
    write(Path(repo_root) / "specs" / "components" / slug / "component.md", text)


def plant_python_adapter(repo_root):
    pk = "sha256:" + "a" * 64
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
            "versions": {"python": "3.12.4", "packages": pk},
            "lockfile_sha256": None,
            "interpreter": "/fake/python",
        }) + "\n"
    )
    write(Path(repo_root) / "gen" / "kind-python" / "kind_python.py", src)


def plant_verifier_orchestrator(repo_root):
    src = (
        "GATE_VERSION = " + repr("verifier-orchestrator@2.0.0") + "\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [],\n"
        "        'requirement_results': {},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
    )
    write(
        Path(repo_root) / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        src,
    )


def base_fixture(repo_root):
    repo_root = Path(repo_root)
    plant_python_adapter(repo_root)
    plant_verifier_orchestrator(repo_root)
    write_component(
        repo_root,
        "foo",
        [
            "id: comp-foo",
            "title: Foo",
            "status: draft",
            "owners: [pipeline-team, alice]",
            "sealed: true",
            "source_path: pipeline/foo/",
        ],
    )
    write(repo_root / "pipeline" / "foo" / "a.py", b"A=1\n")
    write(repo_root / "pipeline" / "foo" / "sub" / "b.py", b"B=2\n")
    return repo_root


def expected_hash(entries):
    h = hashlib.sha256()
    for rel, data in entries:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()


def test_sealed_key_fields_and_hash(tmp_path):
    repo_root = base_fixture(tmp_path / "repo")

    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    assert list(field(key, "owners")) == ["pipeline-team", "alice"]
    assert field(key, "source_path") == "pipeline/foo/"
    assert field(key, "verifier_version") == "verifier-orchestrator@2.0.0"

    want = expected_hash([("a.py", b"A=1\n"), ("sub/b.py", b"B=2\n")])
    assert field(key, "source_hash") == want
    first_hash = field(key, "source_hash")

    # __pycache__ and .sealed-provenance.json are excluded.
    write(repo_root / "pipeline" / "foo" / "__pycache__" / "x.pyc", b"\x00\x01junk")
    write(repo_root / "pipeline" / "foo" / ".sealed-provenance.json", "{\"anything\": 1}\n")
    key2 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key2 is not None
    assert field(key2, "source_hash") == first_hash

    # Changing a source file changes the hash.
    write(repo_root / "pipeline" / "foo" / "a.py", b"A=2\n")
    key3 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key3 is not None
    assert field(key3, "source_hash") != first_hash
    assert field(key3, "source_hash") == expected_hash(
        [("a.py", b"A=2\n"), ("sub/b.py", b"B=2\n")]
    )


def test_unsealed_and_missing_component_return_none(tmp_path):
    repo_root = base_fixture(tmp_path / "repo")
    write_component(
        repo_root,
        "bar",
        [
            "id: comp-bar",
            "title: Bar",
            "status: draft",
            "owners: [pipeline-team]",
            "sealed: false",
            "source_path: pipeline/bar/",
        ],
    )
    write(repo_root / "pipeline" / "bar" / "x.py", b"X=1\n")

    assert provenance_checker.current_sealed_key("comp-bar", repo_root) is None
    assert not (repo_root / "specs" / "components" / "baz" / "component.md").exists()
    assert provenance_checker.current_sealed_key("comp-baz", repo_root) is None


@pytest.mark.parametrize(
    "lines",
    [
        # no owners line
        [
            "id: comp-qux",
            "title: Qux",
            "status: draft",
            "sealed: true",
            "source_path: pipeline/qux/",
        ],
        # owners failing the SealedProvenance owners rule
        [
            "id: comp-qux",
            "title: Qux",
            "status: draft",
            "owners: [Alice]",
            "sealed: true",
            "source_path: pipeline/qux/",
        ],
        # no source_path line
        [
            "id: comp-qux",
            "title: Qux",
            "status: draft",
            "owners: [pipeline-team]",
            "sealed: true",
        ],
    ],
    ids=["no-owners", "owners-uppercase", "no-source-path"],
)
def test_invalid_sealed_frontmatter_raises(tmp_path, lines):
    repo_root = base_fixture(tmp_path / "repo")
    write_component(repo_root, "qux", lines)
    write(repo_root / "pipeline" / "qux" / "q.py", b"Q=1\n")

    with pytest.raises(ValueError):
        provenance_checker.current_sealed_key("comp-qux", repo_root)