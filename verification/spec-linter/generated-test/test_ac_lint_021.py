# hotdocs-criterion: sha256:ed8bedfb38ff96306355f7dbe42a09af1f18d23d9e1f43ee25082fa9ece1b209
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


def component_md(slug, title):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes a " + slug + ".\n"
        "\n"
        "## Scope\n"
        "\n"
        "**In scope:** making a " + slug + ". **Out of scope:** everything else.\n"
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


def requirement_md(rid, func, value):
    return (
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** — `" + func + "()` MUST return the string `\"" + value + "\"`.\n"
    )


def library_md(slug, func):
    return (
        "# Library\n"
        "\n"
        "One module file, `" + slug + ".py`.\n"
        "\n"
        "```\n"
        + func + "() -> str\n"
        "```\n"
    )


def acceptance_md(acid, covers, func, value):
    return (
        "# " + acid + "\n"
        "\n"
        "Covers: " + covers + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When " + func + "() is called\n"
        "Then the result is \"" + value + "\"\n"
        "```\n"
    )


def constraints_md(title):
    return (
        "# " + title + " — Non-Functional Constraints\n"
        "\n"
        "- **Pure.** No I/O.\n"
    )


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_component(root, slug, title, func, value):
    base = "specs/components/" + slug + "/"
    write(root, base + "component.md", component_md(slug, title))
    write(root, base + "interface/library.md", library_md(slug, func))
    write(root, base + "constraints.md", constraints_md(title))


def build_clean(root):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    build_component(root, "foo", "Foo", "make_foo", "foo")
    write(root, "specs/components/foo/requirements/R-FOO-001.md",
          requirement_md("R-FOO-001", "make_foo", "foo"))
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md",
          acceptance_md("AC-FOO-001", "R-FOO-001", "make_foo", "foo"))


def build_scenario(root):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    # comp-foo: R-FOO-001 with no covering acceptance file.
    build_component(root, "foo", "Foo", "make_foo", "foo")
    write(root, "specs/components/foo/requirements/R-FOO-001.md",
          requirement_md("R-FOO-001", "make_foo", "foo"))
    # comp-bar: R-BAR-001 covered by AC-BAR-001; AC-BAR-002 covers R-BAR-999.
    build_component(root, "bar", "Bar", "make_bar", "bar")
    write(root, "specs/components/bar/requirements/R-BAR-001.md",
          requirement_md("R-BAR-001", "make_bar", "bar"))
    write(root, "specs/components/bar/acceptance/AC-BAR-001.md",
          acceptance_md("AC-BAR-001", "R-BAR-001", "make_bar", "bar"))
    write(root, "specs/components/bar/acceptance/AC-BAR-002.md",
          acceptance_md("AC-BAR-002", "R-BAR-999", "make_bar", "bar"))


def traceability_findings(report):
    out = []
    for f in field(report, "findings"):
        if field(f, "rule_id") in ("R-LINT-008", "R-LINT-009"):
            out.append(f)
    return out


def mentions(finding, token):
    text = str(field(finding, "message")) + " " + str(field(finding, "file"))
    return token in text


def test_clean_corpus_has_no_traceability_findings(tmp_path):
    build_clean(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert traceability_findings(report) == []


def test_only_traceability_findings_are_r_foo_001_and_ac_bar_002(tmp_path):
    build_scenario(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    found = traceability_findings(report)

    assert len(found) == 2, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in found
    ]

    fwd = [f for f in found if field(f, "rule_id") == "R-LINT-008"]
    back = [f for f in found if field(f, "rule_id") == "R-LINT-009"]
    assert len(fwd) == 1
    assert len(back) == 1

    f008 = fwd[0]
    assert field(f008, "severity") == "fail"
    assert mentions(f008, "R-FOO-001")
    assert not mentions(f008, "R-BAR-001")

    f009 = back[0]
    assert field(f009, "severity") == "fail"
    assert mentions(f009, "AC-BAR-002")
    assert not mentions(f009, "AC-BAR-001")

    assert field(report, "hard_failures") >= 2