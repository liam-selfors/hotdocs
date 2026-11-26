# hotdocs-criterion: sha256:45b181148828fb5c1c398fd22c584212703e37c0ca595a29f10e09901a8b7e5e
"""AC-LINT-021: R-LINT-008/R-LINT-009 resolved over graph-query-engine's
nodes/edges views.

Given comp-foo has R-FOO-001 with no covering criterion, and comp-bar has
R-BAR-001 covered by AC-BAR-001 plus AC-BAR-002 covering the nonexistent
R-BAR-999, the linter's only R-LINT-008/R-LINT-009 findings are a fail
R-LINT-008 for R-FOO-001 and a fail R-LINT-009 for AC-BAR-002.
"""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(comp_id, slug):
    return (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + slug.capitalize() + " Component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used for traceability checks.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: fixture behavior.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
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
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


def requirement_md(rid):
    return "**" + rid + "** — The component MUST return a value.\n"


def acceptance_md(ac_id, covers):
    return (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + covers + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a fixture input\n"
        "When the component runs\n"
        "Then it returns a value\n"
        "```\n"
    )


def constraints_md():
    return "# Constraints\n\n- None beyond the defaults; measured by review.\n"


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only in this fixture.\n",
    )

    foo = specs / "components" / "foo"
    write(foo / "component.md", component_md("comp-foo", "foo"))
    write(foo / "requirements" / "R-FOO-001.md", requirement_md("R-FOO-001"))
    write(foo / "constraints.md", constraints_md())
    (foo / "acceptance").mkdir(parents=True, exist_ok=True)

    bar = specs / "components" / "bar"
    write(bar / "component.md", component_md("comp-bar", "bar"))
    write(bar / "requirements" / "R-BAR-001.md", requirement_md("R-BAR-001"))
    write(bar / "acceptance" / "AC-BAR-001.md", acceptance_md("AC-BAR-001", "R-BAR-001"))
    write(bar / "acceptance" / "AC-BAR-002.md", acceptance_md("AC-BAR-002", "R-BAR-999"))
    write(bar / "constraints.md", constraints_md())


def mentions(finding, ident):
    file_value = field(finding, "file") or ""
    message = field(finding, "message") or ""
    return ident in str(file_value) or ident in str(message)


def test_ac_lint_021_traceability_via_nodes_edges(tmp_path):
    repo_root = tmp_path
    build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    trace = [
        f for f in findings if field(f, "rule_id") in ("R-LINT-008", "R-LINT-009")
    ]

    r008 = [f for f in trace if field(f, "rule_id") == "R-LINT-008"]
    r009 = [f for f in trace if field(f, "rule_id") == "R-LINT-009"]

    assert len(trace) == 2, "unexpected traceability findings: " + repr(
        [(field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in trace]
    )

    assert len(r008) == 1, repr([(field(f, "file"), field(f, "message")) for f in r008])
    assert field(r008[0], "severity") == "fail"
    assert mentions(r008[0], "R-FOO-001")
    assert not mentions(r008[0], "R-BAR-001")

    assert len(r009) == 1, repr([(field(f, "file"), field(f, "message")) for f in r009])
    assert field(r009[0], "severity") == "fail"
    assert mentions(r009[0], "AC-BAR-002") or mentions(r009[0], "R-BAR-999")
    assert not mentions(r009[0], "AC-BAR-001")

    assert field(report, "hard_failures") >= 2

    # The findings agree with the nodes/edges views the linter must query.
    corpus = spec_linter.load_corpus(repo_root)
    con = field(corpus, "graph")

    requirements = sorted(
        row[0]
        for row in con.execute(
            "SELECT id FROM nodes WHERE kind = 'requirement'"
        ).fetchall()
    )
    assert "R-FOO-001" in requirements
    assert "R-BAR-001" in requirements

    uncovered = sorted(
        row[0]
        for row in con.execute(
            "SELECT n.id FROM nodes n WHERE n.kind = 'requirement' AND NOT EXISTS ("
            "SELECT 1 FROM edges e WHERE e.edge_type = 'covers' AND e.target_id = n.id)"
        ).fetchall()
    )
    assert uncovered == ["R-FOO-001"]

    dangling = sorted(
        (row[0], row[1])
        for row in con.execute(
            "SELECT e.source_id, e.target_id FROM edges e WHERE e.edge_type = 'covers' "
            "AND NOT EXISTS (SELECT 1 FROM nodes n WHERE n.id = e.target_id "
            "AND n.kind IN ('requirement', 'capability'))"
        ).fetchall()
    )
    assert dangling == [("AC-BAR-002", "R-BAR-999")]