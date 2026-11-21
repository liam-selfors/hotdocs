# hotdocs-criterion: sha256:4fbf321136aaf1cc9276f32d71864b6061e14d44a9e625eb1d1e91d55a142629
import spec_linter

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRODUCT_FOO = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo works\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Foo works\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A foo can be made.\n"
    "\n"
    "### CS-FOO-001\n"
    "Covers: P-FOO\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When a foo is made\n"
    "Then it exists\n"
    "```\n"
)


def component_body(title, purpose):
    return (
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose + "\n"
        "\n"
        "## Scope\n"
        "\n"
        "**In scope:** the thing. **Out of scope:** everything else.\n"
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
        "None.\n"
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


def foo_component(depends_on):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: [" + ", ".join(depends_on) + "]\n"
        "depends_on_guarantees: [G-BAR-001]\n"
        "realizes: [P-FOO]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        + component_body("Foo", "Makes a foo.")
    )


BAR_COMPONENT = (
    "---\n"
    "id: comp-bar\n"
    "title: Bar\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/bar/\n"
    "---\n"
    "\n"
    + component_body("Bar", "Makes a bar.")
)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def build_corpus(root, foo_depends_on):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    write(root, "specs/components/foo/component.md", foo_component(foo_depends_on))
    write(
        root,
        "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n",
    )
    write(
        root,
        "specs/components/foo/interface/library.md",
        "# Library\n\nOne module file, `foo.py`.\n\n```\nmake_foo() -> str\n```\n",
    )
    write(
        root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven nothing\nWhen make_foo() is called\nThen the result is \"foo\"\n```\n",
    )
    write(
        root,
        "specs/components/foo/constraints.md",
        "# Foo \u2014 Non-Functional Constraints\n\n- **Pure.** No I/O.\n",
    )

    write(root, "specs/components/bar/component.md", BAR_COMPONENT)
    write(
        root,
        "specs/components/bar/requirements/R-BAR-001.md",
        "# R-BAR-001\n\n**R-BAR-001** \u2014 `make_bar()` MUST return the string `\"bar\"`.\n",
    )
    write(
        root,
        "specs/components/bar/interface/library.md",
        "# Library\n\nOne module file, `bar.py`.\n\n```\nmake_bar() -> str\n```\n",
    )
    write(
        root,
        "specs/components/bar/interface/guarantees/G-BAR-001.md",
        "# G-BAR-001\n\n**G-BAR-001** \u2014 `make_bar()` MUST be idempotent.\n",
    )
    write(
        root,
        "specs/components/bar/acceptance/AC-BAR-001.md",
        "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: generated-test\n\n"
        "```gherkin\nGiven nothing\nWhen make_bar() is called\nThen the result is \"bar\"\n```\n",
    )
    write(
        root,
        "specs/components/bar/constraints.md",
        "# Bar \u2014 Non-Functional Constraints\n\n- **Pure.** No I/O.\n",
    )


def lint_018_findings(root):
    report = spec_linter.lint(None, root)
    findings = list(field(report, "findings"))
    return report, [f for f in findings if field(f, "rule_id") == "R-LINT-018"]


def test_missing_depends_on_for_guarantee_owner_fails_naming_comp_bar(tmp_path):
    root = Path(tmp_path)
    build_corpus(root, [])

    report, findings = lint_018_findings(root)

    matching = [
        f
        for f in findings
        if field(f, "severity") == "fail" and "comp-bar" in str(field(f, "message"))
    ]
    assert matching, (
        "expected a fail-severity R-LINT-018 finding naming comp-bar, got: "
        + repr(findings)
    )
    assert field(report, "hard_failures") >= 1


def test_guarantee_owner_listed_in_depends_on_gives_no_r_lint_018_finding(tmp_path):
    root = Path(tmp_path)
    build_corpus(root, ["comp-bar"])

    _, findings = lint_018_findings(root)

    assert not [f for f in findings if field(f, "severity") == "fail"], repr(findings)