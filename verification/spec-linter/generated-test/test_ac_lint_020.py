# hotdocs-criterion: sha256:75bdf2b5cde4a31d7f6283e94e97ec4fcc7023b35b7568aaaf68540ce6f8cbd8
"""AC-LINT-020 (Covers: R-LINT-020).

Given comp-foo's frontmatter declares depends_on_guarantees: [G-BAR-001],
G-BAR-001 exists under comp-bar's interface/guarantees/, and comp-foo's
depends_on list does NOT include comp-bar, when the linter runs, then it
fails with R-LINT-018. A guarantee's owner comes from its file's path,
because guarantee files carry no frontmatter.
"""

import spec_linter

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


PRODUCT = (
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


def component_md(comp_id, title, depends_on_line, extra_lines):
    return (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        + depends_on_line + "\n"
        + extra_lines
        + "realizes: [P-FOO]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes a " + title.lower() + ".\n"
        "\n"
        "## Scope\n"
        "\n"
        "**In scope:** making a " + title.lower() + ". **Out of scope:** everything else.\n"
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


def unit_files(root, slug, upper, func, value):
    base = "specs/components/" + slug + "/"
    write(
        root,
        base + "requirements/R-" + upper + "-001.md",
        "# R-" + upper + "-001\n"
        "\n"
        "**R-" + upper + "-001** — `" + func + "()` MUST return the string `\"" + value + "\"`.\n",
    )
    write(
        root,
        base + "interface/library.md",
        "# Library\n"
        "\n"
        "One module file, `" + slug + ".py`.\n"
        "\n"
        "```\n"
        + func + "() -> str\n"
        "```\n",
    )
    write(
        root,
        base + "acceptance/AC-" + upper + "-001.md",
        "# AC-" + upper + "-001\n"
        "\n"
        "Covers: R-" + upper + "-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When " + func + "() is called\n"
        "Then the result is \"" + value + "\"\n"
        "```\n",
    )
    write(
        root,
        base + "constraints.md",
        "# " + slug + " — Non-Functional Constraints\n"
        "\n"
        "- **Pure.** No I/O.\n",
    )


def build_corpus(root, foo_depends_on):
    write(root, "specs/product/foo.md", PRODUCT)
    write(
        root,
        "specs/components/foo/component.md",
        component_md(
            "comp-foo",
            "Foo",
            "depends_on: " + foo_depends_on,
            "depends_on_guarantees: [G-BAR-001]\n",
        ),
    )
    unit_files(root, "foo", "FOO", "make_foo", "foo")

    write(
        root,
        "specs/components/bar/component.md",
        component_md("comp-bar", "Bar", "depends_on: []", ""),
    )
    unit_files(root, "bar", "BAR", "make_bar", "bar")
    # Guarantee file: no frontmatter at all; owner is known only from its path.
    write(
        root,
        "specs/components/bar/interface/guarantees/G-BAR-001.md",
        "# G-BAR-001\n"
        "\n"
        "**G-BAR-001** — `make_bar()` MUST always return the same string.\n",
    )


def r018_findings(report):
    return [
        f
        for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-018"
    ]


def test_guarantee_of_undeclared_dependency_fails_r_lint_018(tmp_path):
    root = tmp_path / "repo"
    build_corpus(root, "[]")

    report = spec_linter.lint(None, root)

    found = r018_findings(report)
    assert found, "expected an R-LINT-018 finding, got: " + repr(
        [field(f, "rule_id") for f in field(report, "findings")]
    )
    fails = [f for f in found if field(f, "severity") == "fail"]
    assert fails, "R-LINT-018 finding must be fail-severity: " + repr(found)
    assert any(
        field(f, "file") == "specs/components/foo/component.md" for f in fails
    ), repr([field(f, "file") for f in fails])
    assert field(report, "hard_failures") >= 1


def test_guarantee_of_declared_dependency_does_not_fail_r_lint_018(tmp_path):
    # Control: the same guarantee resolves once comp-bar is in depends_on,
    # which is only possible when the owner is derived from the file's path.
    root = tmp_path / "repo"
    build_corpus(root, "[comp-bar]")

    report = spec_linter.lint(None, root)

    found = r018_findings(report)
    assert found == [], "unexpected R-LINT-018 findings: " + repr(found)


def test_cli_exits_1_for_undeclared_guarantee_owner(tmp_path):
    root = tmp_path / "repo"
    build_corpus(root, "[]")

    code = spec_linter.main(["--repo-root=" + str(root), "--format=json"])

    assert code == 1