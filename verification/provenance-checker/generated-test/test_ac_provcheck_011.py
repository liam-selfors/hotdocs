# hotdocs-criterion: sha256:d77442b184900364d9cd5ed85b63086514d86bd1c8cc45bd4ad7579f91459400
import hashlib
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plant_python_adapter(repo_root):
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
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def _plant_verifier(repo_root):
    report = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }
    src = (
        "GATE_VERSION = " + repr("verifier-orchestrator@2.0.0") + "\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    report = dict(" + repr(report) + ")\n"
        "    report['component_id'] = component_id\n"
        "    return report\n"
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        src,
    )


def _component_md(slug, lines):
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n\n# " + slug + "\n\nA fixture component.\n"


def _base_frontmatter(slug):
    return [
        "id: comp-" + slug,
        "title: " + slug.capitalize() + " Component",
        "status: draft",
    ]


def _expected_hash(entries):
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
    _plant_python_adapter(root)
    _plant_verifier(root)
    lines = _base_frontmatter("foo") + [
        "owners: [pipeline-team, alice]",
        "depends_on: []",
        "sealed: true",
        "source_path: pipeline/foo/",
    ]
    _write(root / "specs" / "components" / "foo" / "component.md", _component_md("foo", lines))
    (root / "pipeline" / "foo" / "sub").mkdir(parents=True)
    (root / "pipeline" / "foo" / "a.py").write_bytes(b"A=1\n")
    (root / "pipeline" / "foo" / "sub" / "b.py").write_bytes(b"B=2\n")
    return root


def test_sealed_key_fields_and_hash(repo_root):
    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None

    assert list(field(key, "owners")) == ["pipeline-team", "alice"]
    assert field(key, "source_path") == "pipeline/foo/"
    assert field(key, "verifier_version") == "verifier-orchestrator@2.0.0"

    expected = _expected_hash([("a.py", b"A=1\n"), ("sub/b.py", b"B=2\n")])
    assert field(key, "source_hash") == expected

    # Excluded files do not change the hash.
    (repo_root / "pipeline" / "foo" / "__pycache__").mkdir()
    (repo_root / "pipeline" / "foo" / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01junk")
    (repo_root / "pipeline" / "foo" / ".sealed-provenance.json").write_text(
        '{"anything": true}', encoding="utf-8"
    )
    key2 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert field(key2, "source_hash") == expected

    # Changing a source file changes the hash.
    (repo_root / "pipeline" / "foo" / "a.py").write_bytes(b"A=2\n")
    key3 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert field(key3, "source_hash") != expected
    assert field(key3, "source_hash") == _expected_hash(
        [("a.py", b"A=2\n"), ("sub/b.py", b"B=2\n")]
    )


def test_not_sealed_or_missing_returns_none(repo_root):
    lines = _base_frontmatter("bar") + [
        "owners: [pipeline-team]",
        "depends_on: []",
        "sealed: false",
        "source_path: pipeline/bar/",
    ]
    _write(repo_root / "specs" / "components" / "bar" / "component.md", _component_md("bar", lines))
    (repo_root / "pipeline" / "bar").mkdir(parents=True)
    (repo_root / "pipeline" / "bar" / "c.py").write_bytes(b"C=3\n")

    assert provenance_checker.current_sealed_key("comp-bar", repo_root) is None
    assert not (repo_root / "specs" / "components" / "baz" / "component.md").exists()
    assert provenance_checker.current_sealed_key("comp-baz", repo_root) is None


@pytest.mark.parametrize(
    "extra_lines",
    [
        # no owners line
        ["depends_on: []", "sealed: true", "source_path: pipeline/foo/"],
        # owners failing the owner pattern
        ["owners: [Alice]", "depends_on: []", "sealed: true", "source_path: pipeline/foo/"],
        # no source_path line
        ["owners: [pipeline-team, alice]", "depends_on: []", "sealed: true"],
    ],
    ids=["no-owners", "owners-uppercase", "no-source-path"],
)
def test_invalid_sealed_frontmatter_raises(repo_root, extra_lines):
    lines = _base_frontmatter("foo") + extra_lines
    _write(repo_root / "specs" / "components" / "foo" / "component.md", _component_md("foo", lines))
    with pytest.raises(ValueError):
        provenance_checker.current_sealed_key("comp-foo", repo_root)