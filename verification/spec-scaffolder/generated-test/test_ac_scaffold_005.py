import os
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

GITKEEP_DIRS = ["requirements", "acceptance", "interface", os.path.join("interface", "data")]


def _snapshot(root: Path):
    snap = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file():
            snap[rel] = p.read_bytes()
        else:
            snap[rel] = None
    return snap


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    (root / "specs").mkdir(parents=True)
    return root


def test_ac_scaffold_005(repo_root):
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

    for d in GITKEEP_DIRS:
        dir_path = expected_dir / d
        assert dir_path.is_dir(), f"missing directory {d}"
        gitkeep = dir_path / ".gitkeep"
        assert gitkeep.is_file(), f"missing .gitkeep in {d}"
        assert gitkeep.read_bytes() == b"", f".gitkeep in {d} is not empty"

    assert component_md.read_text(encoding="utf-8") == EXPECTED_COMPONENT_MD
    assert constraints_md.read_text(encoding="utf-8") == EXPECTED_CONSTRAINTS_MD

    before = _snapshot(repo_root)

    with pytest.raises(FileExistsError):
        spec_scaffolder.new_component(repo_root, "order-book")

    with pytest.raises(ValueError):
        spec_scaffolder.new_component(repo_root, "Order_Book")

    components_dir = repo_root / "specs" / "components"
    entries = sorted(p.name for p in components_dir.iterdir())
    assert entries == ["order-book"]

    # Nothing written by either refused call.
    after = _snapshot(repo_root)
    assert after == before