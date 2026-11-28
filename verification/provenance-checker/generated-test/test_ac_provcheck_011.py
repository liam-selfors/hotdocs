# hotdocs-criterion: sha256:624cb83bf2fbff127b074cc288701334a5a455f24b73fa0a345bee9366b866a0
import hashlib
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


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
        "        'drivers': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
    )
    write(
        Path(repo_root) / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        src,
    )


def write_component(repo_root, slug, frontmatter_lines):
    text = "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n# " + slug + "\n\nA component.\n"
    write(Path(repo_root) / "specs" / "components" / slug / "component.md", text)


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
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


def test_current_sealed_key_fields_and_hash(tmp_path):
    repo_root = make_repo(tmp_path)

    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    assert list(field(key, "owners")) == ["pipeline-team", "alice"]
    assert field(key, "source_path") == "pipeline/foo/"
    assert field(key, "verifier_version") == "verifier-orchestrator@2.0.0"

    want = expected_hash([("a.py", b"A=1\n"), ("sub/b.py", b"B=2\n")])
    first_hash = field(key, "source_hash")
    assert first_hash == want

    # __pycache__ and .sealed-provenance.json are excluded
    write(repo_root / "pipeline" / "foo" / "__pycache__" / "x.pyc", b"\x00\x01garbage")
    write(
        repo_root / "pipeline" / "foo" / ".sealed-provenance.json",
        '{"anything": true}\n',
    )
    key2 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert field(key2, "source_hash") == first_hash

    # a content change changes the hash
    write(repo_root / "pipeline" / "foo" / "a.py", b"A=2\n")
    key3 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert field(key3, "source_hash") != first_hash


def test_current_sealed_key_returns_none_when_not_sealed(tmp_path):
    repo_root = make_repo(tmp_path)
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
    # no component.md at all
    assert provenance_checker.current_sealed_key("comp-missing", repo_root) is None


@pytest.mark.parametrize(
    "slug,lines",
    [
        (
            "noowners",
            [
                "id: comp-noowners",
                "title: No owners",
                "status: draft",
                "sealed: true",
                "source_path: pipeline/noowners/",
            ],
        ),
        (
            "badowners",
            [
                "id: comp-badowners",
                "title: Bad owners",
                "status: draft",
                "owners: [Alice]",
                "sealed: true",
                "source_path: pipeline/badowners/",
            ],
        ),
        (
            "nosource",
            [
                "id: comp-nosource",
                "title: No source path",
                "status: draft",
                "owners: [pipeline-team]",
                "sealed: true",
            ],
        ),
    ],
)
def test_current_sealed_key_invalid_frontmatter_raises(tmp_path, slug, lines):
    repo_root = make_repo(tmp_path)
    write_component(repo_root, slug, lines)
    write(repo_root / "pipeline" / slug / "m.py", b"M=1\n")

    with pytest.raises(ValueError):
        provenance_checker.current_sealed_key("comp-" + slug, repo_root)