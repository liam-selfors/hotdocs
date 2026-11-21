# hotdocs-criterion: sha256:201765ec71f56a2ed78778f20071e0924ae710579dc19ca25645483d1122d932
from pathlib import Path

import pytest

import spec_scaffolder


def expected_component_md(slug, title, owners, depends_on, realizes, sealed):
    def flow(items):
        return "[" + ", ".join(items) + "]"

    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: " + flow(owners) + "\n"
        "depends_on: " + flow(depends_on) + "\n"
        "realizes: " + flow(realizes) + "\n"
        "sealed: " + ("true" if sealed else "false") + "\n"
        "---\n"
        "\n"
        "# " + title + "\n"
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


def test_ac_scaffold_005(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)

    result = spec_scaffolder.new_component(
        repo_root, "order-book", depends_on=["comp-ledger"], realizes=["P-TRADING"]
    )

    comp_dir = repo_root / "specs" / "components" / "order-book"
    assert Path(result).resolve() == comp_dir.resolve()
    assert comp_dir.is_dir()

    component_md = comp_dir / "component.md"
    constraints_md = comp_dir / "constraints.md"
    assert component_md.is_file()
    assert constraints_md.is_file()

    for sub in ("requirements", "acceptance", "interface", "interface/data"):
        d = comp_dir / sub
        assert d.is_dir(), sub
        keep = d / ".gitkeep"
        assert keep.is_file(), sub
        assert keep.read_bytes() == b"", sub

    expected = expected_component_md(
        "order-book",
        "Order Book",
        ["unassigned"],
        ["comp-ledger"],
        ["P-TRADING"],
        False,
    )
    assert component_md.read_bytes().decode("utf-8") == expected

    expected_constraints = "# Order Book \u2014 Non-Functional Constraints\n\n- TODO.\n"
    assert constraints_md.read_bytes().decode("utf-8") == expected_constraints

    components_root = repo_root / "specs" / "components"
    before_component = component_md.read_bytes()
    before_constraints = constraints_md.read_bytes()

    with pytest.raises(FileExistsError):
        spec_scaffolder.new_component(repo_root, "order-book")

    with pytest.raises(ValueError):
        spec_scaffolder.new_component(repo_root, "Order_Book")

    entries = sorted(p.name for p in components_root.iterdir())
    assert entries == ["order-book"]

    # The existing component was not overwritten by the refused call.
    assert component_md.read_bytes() == before_component
    assert constraints_md.read_bytes() == before_constraints