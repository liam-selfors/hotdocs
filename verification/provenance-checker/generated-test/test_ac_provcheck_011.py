import hashlib

import pytest

import provenance_checker


def _get(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _write_component_md(
    root,
    owners=("pipeline-team", "alice"),
    source_path="pipeline/foo/",
    sealed=True,
    include_owners=True,
    include_source_path=True,
):
    comp_dir = root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: ratified",
        "last_ratified_commit: 0000000000000000000000000000000000000000",
    ]
    if include_owners:
        owners_str = "[" + ", ".join(owners) + "]"
        lines.append(f"owners: {owners_str}")
    lines.append(f"sealed: {'true' if sealed else 'false'}")
    if include_source_path:
        lines.append(f"source_path: {source_path}")
    lines.append("---")
    lines.append("")
    (comp_dir / "component.md").write_text("\n".join(lines))


def _write_source_files(root, a_content="A=1\n", b_content="B=2\n"):
    pf = root / "pipeline" / "foo"
    pf.mkdir(parents=True, exist_ok=True)
    (pf / "a.py").write_text(a_content)
    sub = pf / "sub"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "b.py").write_text(b_content)


def _write_verifier_orchestrator(root):
    d = root / "gen" / "verifier-orchestrator"
    d.mkdir(parents=True, exist_ok=True)
    (d / "verifier_orchestrator.py").write_text(
        'GATE_VERSION = "verifier-orchestrator@2.0.0"\n'
    )


def test_sealed_key_fields_and_hash_stability(tmp_path):
    _write_component_md(tmp_path)
    _write_source_files(tmp_path)
    _write_verifier_orchestrator(tmp_path)

    key = provenance_checker.current_sealed_key("comp-foo", tmp_path)

    owners = _get(key, "owners")
    source_path = _get(key, "source_path")
    verifier_version = _get(key, "verifier_version")
    source_hash = _get(key, "source_hash")

    assert owners == ["pipeline-team", "alice"]
    assert source_path == "pipeline/foo/"
    assert verifier_version == "verifier-orchestrator@2.0.0"

    expected_hash = "sha256:" + hashlib.sha256(
        b"a.py" + b"\x00" + b"A=1\n" + b"\x00"
        + b"sub/b.py" + b"\x00" + b"B=2\n" + b"\x00"
    ).hexdigest()
    assert source_hash == expected_hash

    pycache = tmp_path / "pipeline" / "foo" / "__pycache__"
    pycache.mkdir()
    (pycache / "x.pyc").write_bytes(b"\x00\x01binary-noise")
    (tmp_path / "pipeline" / "foo" / ".sealed-provenance.json").write_text(
        '{"any": "content"}'
    )

    key2 = provenance_checker.current_sealed_key("comp-foo", tmp_path)
    source_hash2 = _get(key2, "source_hash")
    assert source_hash2 == source_hash

    (tmp_path / "pipeline" / "foo" / "a.py").write_text("A=2\n")

    key3 = provenance_checker.current_sealed_key("comp-foo", tmp_path)
    source_hash3 = _get(key3, "source_hash")
    assert source_hash3 != source_hash


def test_not_sealed_returns_none(tmp_path):
    _write_component_md(tmp_path, sealed=False)
    _write_source_files(tmp_path)
    _write_verifier_orchestrator(tmp_path)

    assert provenance_checker.current_sealed_key("comp-foo", tmp_path) is None


def test_missing_component_md_returns_none(tmp_path):
    _write_verifier_orchestrator(tmp_path)

    assert provenance_checker.current_sealed_key("comp-foo", tmp_path) is None


@pytest.mark.parametrize(
    "include_owners, owners, include_source_path",
    [
        (False, (), True),
        (True, ("Alice",), True),
        (True, ("pipeline-team",), False),
    ],
)
def test_invalid_frontmatter_raises_value_error(
    tmp_path, include_owners, owners, include_source_path
):
    _write_component_md(
        tmp_path,
        owners=owners,
        include_owners=include_owners,
        include_source_path=include_source_path,
    )
    _write_source_files(tmp_path)
    _write_verifier_orchestrator(tmp_path)

    with pytest.raises(ValueError):
        provenance_checker.current_sealed_key("comp-foo", tmp_path)