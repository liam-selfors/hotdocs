# hotdocs-criterion: sha256:c01b30487dd9a1c93447acbfa52f2db02f321adec7d89fbae0f742dae6236564
"""AC-LINT-021: R-LINT-008 / R-LINT-009 resolved via graph-query-engine's
nodes/edges views.

Fixture:
  - comp-foo has requirement R-FOO-001 and no acceptance file covering it.
  - comp-bar has exactly one requirement, R-BAR-001, covered by AC-BAR-001,
    plus AC-BAR-002 whose Covers: tag names R-BAR-999 (which does not exist).

Expectation: the only R-LINT-008 / R-LINT-009 findings are a fail-severity
R-LINT-008 for R-FOO-001 and a fail-severity R-LINT-009 for AC-BAR-002, and
these agree exactly with what the corpus's own nodes/edges views say.
"""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, slug):
    return (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used to exercise traceability checks.\n"
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


def _requirement(req_id):
    return (
        "# " + req_id + "\n"
        "\n"
        "**" + req_id + "** — The component MUST return zero when called.\n"
    )


def _acceptance(ac_id, covers):
    return (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + covers + "\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given the component is available\n"
        "When it is called\n"
        "Then it returns zero\n"
        "```\n"
    )


def _constraints():
    return "# Constraints\n\nNone.\n"


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )

    foo = specs / "components" / "foo"
    _write(foo / "component.md", _component_md("comp-foo", "Foo", "foo"))
    _write(foo / "requirements" / "R-FOO-001.md", _requirement("R-FOO-001"))
    _write(foo / "constraints.md", _constraints())

    bar = specs / "components" / "bar"
    _write(bar / "component.md", _component_md("comp-bar", "Bar", "bar"))
    _write(bar / "requirements" / "R-BAR-001.md", _requirement("R-BAR-001"))
    _write(bar / "acceptance" / "AC-BAR-001.md", _acceptance("AC-BAR-001", "R-BAR-001"))
    _write(bar / "acceptance" / "AC-BAR-002.md", _acceptance("AC-BAR-002", "R-BAR-999"))
    _write(bar / "constraints.md", _constraints())


def _mentions(finding, ident):
    file_ = field(finding, "file") or ""
    message = field(finding, "message") or ""
    return ident in str(file_) or ident in str(message)


def test_forward_and_backward_traceability_via_nodes_edges(tmp_path):
    repo_root = tmp_path
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    trace = [f for f in findings if field(f, "rule_id") in ("R-LINT-008", "R-LINT-009")]

    lint008 = [f for f in trace if field(f, "rule_id") == "R-LINT-008"]
    lint009 = [f for f in trace if field(f, "rule_id") == "R-LINT-009"]

    assert len(trace) == 2, "expected exactly two R-LINT-008/009 findings, got: " + repr(trace)
    assert len(lint008) == 1, repr(lint008)
    assert len(lint009) == 1, repr(lint009)

    f008 = lint008[0]
    assert field(f008, "severity") == "fail"
    assert _mentions(f008, "R-FOO-001"), repr(f008)
    assert not _mentions(f008, "R-BAR-001"), repr(f008)

    f009 = lint009[0]
    assert field(f009, "severity") == "fail"
    assert _mentions(f009, "AC-BAR-002") or _mentions(f009, "R-BAR-999"), repr(f009)
    assert not _mentions(f009, "AC-BAR-001"), repr(f009)

    # Both must agree with graph-query-engine's own nodes/edges views over
    # the same corpus: the linter's answer is a query over these views.
    corpus = spec_linter.load_corpus(repo_root)
    con = field(corpus, "graph")

    uncovered = sorted(
        row[0]
        for row in con.execute(
            "SELECT id FROM nodes WHERE kind = 'requirement' "
            "AND id NOT IN (SELECT target_id FROM edges WHERE edge_type = 'covers')"
        ).fetchall()
    )
    assert uncovered == ["R-FOO-001"]

    dangling = sorted(
        (row[0], row[1])
        for row in con.execute(
            "SELECT source_id, target_id FROM edges WHERE edge_type = 'covers' "
            "AND target_id NOT IN (SELECT id FROM nodes "
            "WHERE kind IN ('requirement', 'capability'))"
        ).fetchall()
    )
    assert dangling == [("AC-BAR-002", "R-BAR-999")]

    # R-BAR-001 is covered: it must not appear in any R-LINT-008 finding.
    assert all(not _mentions(f, "R-BAR-001") for f in lint008)