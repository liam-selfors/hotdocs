# hotdocs-criterion: sha256:6f6ed5498b444dda9e2dff85b684a5fcdd1dde63a5b526de2943a3cd5c6c5d9f
from pathlib import Path

import pytest

import spec_scaffolder


EXPECTED_COMPONENT_MD = (
    "---\n"
    "id: comp-order-book\n"
    "title: Order Book\n"
    "status: draft\n"
    "owners: [unassigned]\n"
    "depends_on: [comp-ledger]\n"
    "realizes: [P-TRADING]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Order Book\n"
    "\n"
    "## Purpose\n"
    "\n"
    "TODO.\n"
    "\n"
    "## Scope\n"
    "\n"
    "TODO.\n"
    "\n"
    "## Definitions\n"
    "\n"
    "No deltas from `specs/glossary.md`.\n"
    "\n"
    "## Behavior\n"
    "\n"
    "See `requirements/`.\n"
    "\n"
    "## Interfaces\n"
    "\n"
    "See `interface/`.\n"
    "\n"
    "## Data\n"
    "\n"
    "See `interface/data/`.\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "See `acceptance/`.\n"
    "\n"
    "## Non-functional constraints\n"
    "\n"
    "See `constraints.md`.\n"
    "\n"
    "## Open questions\n"
    "\n"
    "None.\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial draft.\n"
)

EXPECTED_CONSTRAINTS_MD = "# Order Book \u2014 Non-Functional Constraints\n\n- TODO.\n"

SUBDIRS = ["requirements", "acceptance", "interface", "interface/data"]


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    return repo_root


def _snapshot(root):
    result = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file():
            result[rel] = p.read_bytes()
        else:
            result[rel] = None
    return result


def test_new_component_creates_layout(tmp_path):
    repo_root = _make_repo(tmp_path)

    result = spec_scaffolder.new_component(
        repo_root, "order-book", depends_on=["comp-ledger"], realizes=["P-TRADING"]
    )

    expected_dir = repo_root / "specs" / "components" / "order-book"
    assert Path(result).resolve() == expected_dir.resolve()
    assert expected_dir.is_dir()

    component_md = expected_dir / "component.md"
    constraints_md = expected_dir / "constraints.md"
    assert component_md.is_file()
    assert constraints_md.is_file()

    for sub in SUBDIRS:
        d = expected_dir / sub
        assert d.is_dir(), sub
        gitkeep = d / ".gitkeep"
        assert gitkeep.is_file(), sub
        assert gitkeep.read_bytes() == b"", sub

    assert component_md.read_text(encoding="utf-8") == EXPECTED_COMPONENT_MD
    assert constraints_md.read_text(encoding="utf-8") == EXPECTED_CONSTRAINTS_MD


def test_new_component_refuses_existing_and_invalid_slug(tmp_path):
    repo_root = _make_repo(tmp_path)
    spec_scaffolder.new_component(
        repo_root, "order-book", depends_on=["comp-ledger"], realizes=["P-TRADING"]
    )
    components = repo_root / "specs" / "components"
    before = _snapshot(components)

    with pytest.raises(FileExistsError):
        spec_scaffolder.new_component(repo_root, "order-book")

    with pytest.raises(ValueError):
        spec_scaffolder.new_component(repo_root, "Order_Book")

    entries = sorted(p.name for p in components.iterdir())
    assert entries == ["order-book"]
    assert _snapshot(components) == before
    assert (
        (components / "order-book" / "component.md").read_text(encoding="utf-8")
        == EXPECTED_COMPONENT_MD
    )