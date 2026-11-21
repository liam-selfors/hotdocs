# hotdocs-criterion: sha256:68fb30278f8a78709e9a3f4ed43126b4ff9f960e95e03f61435b6b3e32358573
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

EXPECTED_CONSTRAINTS_MD = (
    "# Order Book \u2014 Non-Functional Constraints\n\n- TODO.\n"
)

EXPECTED_ENTRIES = {
    "component.md",
    "constraints.md",
    "requirements",
    "requirements/.gitkeep",
    "acceptance",
    "acceptance/.gitkeep",
    "interface",
    "interface/.gitkeep",
    "interface/data",
    "interface/data/.gitkeep",
}


def _snapshot(directory):
    result = {}
    for p in sorted(directory.rglob("*")):
        rel = p.relative_to(directory).as_posix()
        result[rel] = p.read_bytes() if p.is_file() else None
    return result


@pytest.fixture
def repo_root(tmp_path):
    (tmp_path / "specs").mkdir()
    return tmp_path


def test_new_component_creates_exact_layout(repo_root):
    result = spec_scaffolder.new_component(
        repo_root, "order-book", depends_on=["comp-ledger"], realizes=["P-TRADING"]
    )
    expected_dir = repo_root / "specs" / "components" / "order-book"
    assert Path(result).resolve() == expected_dir.resolve()
    assert expected_dir.is_dir()

    entries = {p.relative_to(expected_dir).as_posix() for p in expected_dir.rglob("*")}
    assert entries == EXPECTED_ENTRIES

    for d in ("requirements", "acceptance", "interface", "interface/data"):
        assert (expected_dir / d).is_dir()
        gitkeep = expected_dir / d / ".gitkeep"
        assert gitkeep.is_file()
        assert gitkeep.read_bytes() == b""

    component_md = (expected_dir / "component.md").read_bytes().decode("utf-8")
    assert component_md == EXPECTED_COMPONENT_MD

    constraints_md = (expected_dir / "constraints.md").read_bytes().decode("utf-8")
    assert constraints_md == EXPECTED_CONSTRAINTS_MD


def test_new_component_refuses_existing_and_non_kebab(repo_root):
    spec_scaffolder.new_component(
        repo_root, "order-book", depends_on=["comp-ledger"], realizes=["P-TRADING"]
    )
    components = repo_root / "specs" / "components"
    target = components / "order-book"
    before = _snapshot(target)

    with pytest.raises(FileExistsError):
        spec_scaffolder.new_component(repo_root, "order-book")

    with pytest.raises(ValueError):
        spec_scaffolder.new_component(repo_root, "Order_Book")

    assert sorted(p.name for p in components.iterdir()) == ["order-book"]
    assert _snapshot(target) == before