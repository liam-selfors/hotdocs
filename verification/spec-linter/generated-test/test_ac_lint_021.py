# hotdocs-criterion: sha256:c01b30487dd9a1c93447acbfa52f2db02f321adec7d89fbae0f742dae6236564
"""AC-LINT-021: forward/backward traceability findings over nodes/edges.

comp-foo has R-FOO-001 with no covering acceptance criterion; comp-bar has
R-BAR-001 covered by AC-BAR-001, plus AC-BAR-002 covering the nonexistent
R-BAR-999. The linter's only R-LINT-008/R-LINT-009 findings must be a
fail-severity R-LINT-008 for R-FOO-001 and a fail-severity R-LINT-009 for
AC-BAR-002.
"""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, title):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component used for traceability checks.\n"
        + "\n"
        + "## Scope\n"
        + "\n"
        + "- In scope: fixture behavior.\n"
        + "- Out of scope: everything else.\n"
        + "\n"
        + "## Definitions\n"
        + "\n"
        + "None.\n"
        + "\n"
        + "## Behavior\n"
        + "\n"
        + "See `requirements/`.\n"
        + "\n"
        + "## Interfaces\n"
        + "\n"
        + "See `interface/`.\n"
        + "\n"
        + "## Data\n"
        + "\n"
        + "See `interface/data/`.\n"
        + "\n"
        + "## Acceptance criteria\n"
        + "\n"
        + "See `acceptance/`.\n"
        + "\n"
        + "## Non-functional constraints\n"
        + "\n"
        + "See `constraints.md`.\n"
        + "\n"
        + "## Open questions\n"
        + "\n"
        + "## Change log\n"
        + "\n"
        + "- Initial draft.\n"
    )


def _requirement(rid):
    return (
        "# " + rid + "\n"
        + "\n"
        + "**" + rid + "** — The component MUST return the input unchanged.\n"
    )


def _acceptance(acid, covers):
    return (
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + covers + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given an input value\n"
        + "When the component runs\n"
        + "Then it returns the input unchanged\n"
        + "```\n"
    )


def _constraints():
    return "# Constraints\n\nNone beyond the defaults.\n"


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )

    foo = specs / "components" / "foo"
    _write(foo / "component.md", _component_md("foo", "Foo"))
    _write(foo / "requirements" / "R-FOO-001.md", _requirement("R-FOO-001"))
    _write(foo / "constraints.md", _constraints())

    bar = specs / "components" / "bar"
    _write(bar / "component.md", _component_md("bar", "Bar"))
    _write(bar / "requirements" / "R-BAR-001.md", _requirement("R-BAR-001"))
    _write(bar / "acceptance" / "AC-BAR-001.md", _acceptance("AC-BAR-001", "R-BAR-001"))
    _write(bar / "acceptance" / "AC-BAR-002.md", _acceptance("AC-BAR-002", "R-BAR-999"))
    _write(bar / "constraints.md", _constraints())


def _text_of(finding):
    file_value = field(finding, "file")
    message = field(finding, "message")
    return str(file_value or "") + " " + str(message or "")


def test_traceability_findings_are_exactly_foo_requirement_and_bar_dangling_criterion(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    trace = [f for f in findings if field(f, "rule_id") in ("R-LINT-008", "R-LINT-009")]

    described = [
        (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
        for f in trace
    ]
    assert len(trace) == 2, "expected exactly two traceability findings, got: " + repr(described)

    forward = [f for f in trace if field(f, "rule_id") == "R-LINT-008"]
    backward = [f for f in trace if field(f, "rule_id") == "R-LINT-009"]

    assert len(forward) == 1, "expected one R-LINT-008 finding, got: " + repr(described)
    assert len(backward) == 1, "expected one R-LINT-009 finding, got: " + repr(described)

    fwd = forward[0]
    assert field(fwd, "severity") == "fail"
    fwd_text = _text_of(fwd)
    assert "R-FOO-001" in fwd_text, "R-LINT-008 finding not about R-FOO-001: " + repr(described)
    assert "R-BAR-001" not in fwd_text

    bwd = backward[0]
    assert field(bwd, "severity") == "fail"
    bwd_text = _text_of(bwd)
    assert "AC-BAR-002" in bwd_text, "R-LINT-009 finding not about AC-BAR-002: " + repr(described)
    assert "AC-BAR-001" not in bwd_text

    assert field(report, "hard_failures") >= 2