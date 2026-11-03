import hashlib

import pytest

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_component_md(
    repo_root,
    slug="foo",
    owners="owners: [pipeline-team, alice]",
    sealed="sealed: true",
    source_path="source_path: pipeline/foo/",
):
    lines = ["---", "id: comp-foo", "title: Foo", "status: draft"]
    if owners is not None:
        lines.append(owners)
    lines.append(sealed)
    if source_path is not None:
        lines.append(source_path)
    lines.append("---")
    lines.append("")
    lines.append("# Foo")
    lines.append("")
    content = "\n".join(lines) + "\n"
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(content)


def _write_source_files(repo_root, a_content="A=1\n", b_content="B=2\n"):
    src = repo_root / "pipeline" / "foo"
    src.mkdir(parents=True, exist_ok=True)
    (src / "a.py").write_text(a_content)
    sub = src / "sub"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "b.py").write_text(b_content)


def _write_verifier_orchestrator(repo_root, gate_version="verifier-orchestrator@2.0.0"):
    d = repo_root / "gen" / "verifier-orchestrator"
    d.mkdir(parents=True, exist_ok=True)
    (d / "verifier_orchestrator.py").write_text(
        'GATE_VERSION = "%s"\n' % gate_version
    )


def test_sealed_key_fields_and_hash_stability(tmp_path):
    repo_root = tmp_path
    _write_component_md(repo_root)
    _write_source_files(repo_root)
    _write_verifier_orchestrator(repo_root)

    key = provenance_checker.current_sealed_key("comp-foo", repo_root)

    assert _get(key, "owners") == ["pipeline-team", "alice"]
    assert _get(key, "source_path") == "pipeline/foo/"
    assert _get(key, "verifier_version") == "verifier-orchestrator@2.0.0"

    expected_hash = hashlib.sha256(
        b"a.py" + b"\x00" + b"A=1\n" + b"\x00" + b"sub/b.py" + b"\x00" + b"B=2\n" + b"\x00"
    ).hexdigest()
    source_hash = _get(key, "source_hash")
    assert source_hash == "sha256:" + expected_hash

    pycache_dir = repo_root / "pipeline" / "foo" / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "x.pyc").write_bytes(b"\x00\x01\x02")
    (repo_root / "pipeline" / "foo" / ".sealed-provenance.json").write_text("{}")

    key2 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert _get(key2, "source_hash") == source_hash

    (repo_root / "pipeline" / "foo" / "a.py").write_text("A=2\n")
    key3 = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert _get(key3, "source_hash") != source_hash


def test_not_sealed_or_missing_component_returns_none(tmp_path):
    not_sealed_root = tmp_path / "not_sealed"
    not_sealed_root.mkdir()
    _write_component_md(not_sealed_root, sealed="sealed: false")
    _write_source_files(not_sealed_root)
    _write_verifier_orchestrator(not_sealed_root)
    assert provenance_checker.current_sealed_key("comp-foo", not_sealed_root) is None

    missing_root = tmp_path / "missing_component"
    missing_root.mkdir()
    assert provenance_checker.current_sealed_key("comp-foo", missing_root) is None


@pytest.mark.parametrize(
    "case",
    ["no_owners", "invalid_owners", "no_source_path"],
)
def test_invalid_frontmatter_raises_value_error(tmp_path, case):
    repo_root = tmp_path / case
    repo_root.mkdir()

    if case == "no_owners":
        _write_component_md(repo_root, owners=None)
    elif case == "invalid_owners":
        _write_component_md(repo_root, owners="owners: [Alice]")
    else:
        _write_component_md(repo_root, source_path=None)

    _write_source_files(repo_root)
    _write_verifier_orchestrator(repo_root)

    with pytest.raises(ValueError):
        provenance_checker.current_sealed_key("comp-foo", repo_root)