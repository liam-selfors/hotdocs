# hotdocs-criterion: sha256:91452ccda77c012f03298d5ce91a194faef623c0994ab41be3528363af015c2f
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


def _snapshot(root):
    result = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file():
            result[rel] = p.read_bytes()
        else:
            result[rel] = None
    return result


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    (root / "specs").mkdir(parents=True)
    return root


def test_ac_scaffold_005_creates_component_layout(repo_root):
    result = spec_scaffolder.new_component(
        repo_root, "order-book", depends_on=["comp-ledger"], realizes=["P-TRADING"]
    )

    expected_dir = repo_root / "specs" / "components" / "order-book"
    assert Path(result).resolve() == expected_dir.resolve()
    assert expected_dir.is_dir()

    top_level = {p.name for p in expected_dir.iterdir()}
    assert top_level == {
        "component.md",
        "constraints.md",
        "requirements",
        "acceptance",
        "interface",
    }

    for sub in ("requirements", "acceptance", "interface", "interface/data"):
        d = expected_dir / sub
        assert d.is_dir(), sub
        gitkeep = d / ".gitkeep"
        assert gitkeep.is_file(), sub
        assert gitkeep.read_bytes() == b"", sub

    assert {p.name for p in (expected_dir / "requirements").iterdir()} == {".gitkeep"}
    assert {p.name for p in (expected_dir / "acceptance").iterdir()} == {".gitkeep"}
    assert {p.name for p in (expected_dir / "interface").iterdir()} == {".gitkeep", "data"}
    assert {p.name for p in (expected_dir / "interface" / "data").iterdir()} == {".gitkeep"}

    component_md = (expected_dir / "component.md").read_bytes().decode("utf-8")
    assert component_md == EXPECTED_COMPONENT_MD

    constraints_md = (expected_dir / "constraints.md").read_bytes().decode("utf-8")
    assert constraints_md == EXPECTED_CONSTRAINTS_MD


def test_ac_scaffold_005_refuses_existing_and_invalid_slug(repo_root):
    spec_scaffolder.new_component(
        repo_root, "order-book", depends_on=["comp-ledger"], realizes=["P-TRADING"]
    )
    components = repo_root / "specs" / "components"
    before = _snapshot(repo_root)

    with pytest.raises(FileExistsError):
        spec_scaffolder.new_component(repo_root, "order-book")

    assert _snapshot(repo_root) == before

    with pytest.raises(ValueError):
        spec_scaffolder.new_component(repo_root, "Order_Book")

    assert _snapshot(repo_root) == before
    assert sorted(p.name for p in components.iterdir()) == ["order-book"]