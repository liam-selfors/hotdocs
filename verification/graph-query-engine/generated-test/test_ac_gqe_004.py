"""AC-GQE-004: component_context extracts a multi-line Purpose section in full.

Covers: R-GQE-004
"""

import json
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


PURPOSE_LINES = [
    "The foo widget turns raw spec text into a normalized widget record.",
    "It runs entirely locally and never touches the network.",
    "This third line proves the section genuinely spans multiple lines.",
]

OTHER_PURPOSE_LINES = [
    "The bar gadget supplies helper records to the foo widget.",
    "It also spans more than one line of prose.",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, purpose_lines, depends_on, realizes, uses_var):
    purpose = "\n".join(purpose_lines)
    return (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        f"depends_on: [{', '.join(depends_on)}]\n"
        f"realizes: [{', '.join(realizes)}]\n"
        f"uses_var: [{', '.join(uses_var)}]\n"
        "depends_on_guarantees: []\n"
        "sealed: true\n"
        f"source_path: legacy/{comp_id[len('comp-'):]}/\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose}\n"
        "\n"
        "## Definitions\n"
        "\n"
        "- **Widget** - a normalized record.\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


def _make_component(repo_root, slug, title, prefix, purpose_lines, depends_on, realizes, uses_var):
    comp_id = f"comp-{slug}"
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        _component_md(comp_id, title, purpose_lines, depends_on, realizes, uses_var),
    )
    _write(
        base / "requirements" / f"R-{prefix}-001.md",
        f"# R-{prefix}-001\n\n**R-{prefix}-001** - The component MUST do its one thing.\n",
    )
    _write(
        base / "acceptance" / f"AC-{prefix}-001.md",
        f"# AC-{prefix}-001\n\n"
        f"Covers: R-{prefix}-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it does its one thing\n"
        "```\n",
    )
    _write(
        base / "interface" / "library.md",
        "# Library\n\n```\ndo_thing() -> None\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNo network access.\n")

    manifest = {
        "component_id": comp_id,
        "spec_bundle_hash": "0" * 64,
        "model": "anthropic:claude-sonnet-5",
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_report": {"passed": True, "results": []},
        "license_scan": {"passed": True, "findings": []},
        "secret_scan": {"passed": True, "findings": []},
        "provenance_hit": False,
    }
    for top in ("gen", "verification"):
        _write(repo_root / top / slug / ".provenance.json", json.dumps(manifest))
    return comp_id


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    _make_component(
        root,
        "foo-widget",
        "Foo Widget",
        "FOO",
        PURPOSE_LINES,
        depends_on=["comp-bar-gadget"],
        realizes=["P-FOO"],
        uses_var=["VAR-FOO"],
    )
    _make_component(
        root,
        "bar-gadget",
        "Bar Gadget",
        "BAR",
        OTHER_PURPOSE_LINES,
        depends_on=["comp-foo-widget"],
        realizes=["P-FOO"],
        uses_var=["VAR-FOO"],
    )

    _write(
        root / "specs" / "vars" / "VAR-FOO.md",
        "---\nid: VAR-FOO\ntitle: Foo Var\nstatus: draft\nowners: [team-a]\n---\n\n"
        "# VAR-FOO\n\nA fake variable.\n",
    )
    _write(
        root / "specs" / "product" / "P-FOO.md",
        "---\nid: P-FOO\ntitle: Foo Capability\nstatus: draft\nowners: [team-a]\n---\n\n"
        "# Foo Capability\n\nA fake product capability.\n",
    )
    _write(
        root / "specs" / "decisions" / "D1.md",
        "---\nid: D1\ntitle: First Decision\nstatus: ratified\nowners: [team-a]\n"
        "last_ratified_commit: abc1234\n---\n\n# D1\n\nA fake decision.\n",
    )
    _write(
        root / "specs" / "decisions" / "D2.md",
        "---\nid: D2\ntitle: Second Decision\nstatus: draft\nowners: [team-a]\n"
        "last_ratified_commit: abc1234\n---\n\n# D2\n\nAnother fake decision.\n",
    )
    _write(root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** - a record.\n")
    return root


@pytest.fixture
def con():
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    yield connection
    connection.close()


def test_ac_gqe_004_multiline_purpose_extracted_in_full(con, repo_root):
    graph_query_engine.load_views(con, repo_root)

    rows = con.execute(
        "SELECT component_id, purpose FROM component_context WHERE component_id = ?",
        ["comp-foo-widget"],
    ).fetchall()

    assert len(rows) == 1, f"expected exactly one row for comp-foo-widget, got {rows!r}"
    component_id, purpose = rows[0]
    assert component_id == "comp-foo-widget"

    assert purpose is not None, "purpose is NULL"
    assert purpose != "", "purpose silently extracted to an empty string"
    assert purpose.strip() != ""

    # The full multi-line text is present, not just one line of it.
    for line in PURPOSE_LINES:
        assert line in purpose, f"missing purpose line {line!r} in {purpose!r}"
    assert "\n" in purpose.strip(), f"purpose is not multi-line: {purpose!r}"
    assert purpose.strip() == "\n".join(PURPOSE_LINES)

    # Nothing from the following section leaked into the Purpose text.
    assert "Definitions" not in purpose
    assert "Widget** - a normalized record" not in purpose


def test_ac_gqe_004_every_multiline_purpose_non_empty(con, repo_root):
    graph_query_engine.load_views(con, repo_root)

    rows = con.execute(
        "SELECT component_id, purpose FROM component_context ORDER BY component_id"
    ).fetchall()
    by_id = {r[0]: r[1] for r in rows}

    assert set(by_id) == {"comp-foo-widget", "comp-bar-gadget"}
    assert len(rows) == 2, f"expected one row per component, got {rows!r}"

    assert by_id["comp-bar-gadget"] is not None
    assert by_id["comp-bar-gadget"].strip() == "\n".join(OTHER_PURPOSE_LINES)
    assert by_id["comp-foo-widget"].strip() == "\n".join(PURPOSE_LINES)