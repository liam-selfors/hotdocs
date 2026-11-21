# hotdocs-criterion: sha256:04cd083c597ce5b4dae419064d0b5e848acf3c6e9a8a4984a1eda445f1890872
import json
from pathlib import Path

import spec_linter


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

COMPONENT_BODY = (
    "\n"
    "## Purpose\n"
    "\n"
    "Makes a thing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "**In scope:** making a thing. **Out of scope:** everything else.\n"
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

FOO_COMPONENT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "realizes: [P-FOO]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Foo\n"
    + COMPONENT_BODY
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_clean_corpus(root):
    specs = root / "specs"
    write(specs / "product" / "foo.md", PRODUCT_FOO)
    foo = specs / "components" / "foo"
    write(foo / "component.md", FOO_COMPONENT)
    write(
        foo / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n",
    )
    write(
        foo / "interface" / "library.md",
        "# Library\n\nOne module file, `foo.py`.\n\n```\nmake_foo() -> str\n```\n",
    )
    write(
        foo / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven nothing\nWhen make_foo() is called\nThen the result is \"foo\"\n```\n",
    )
    write(
        foo / "constraints.md",
        "# Foo \u2014 Non-Functional Constraints\n\n- **Pure.** No I/O.\n",
    )


def write_sealed_component(root, slug, depends_on):
    comp_dir = root / "specs" / "components" / slug
    upper = slug.upper()
    deps = "[" + ", ".join(depends_on) + "]"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: " + deps + "\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        + COMPONENT_BODY,
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    write(
        comp_dir / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** \u2014 `make()` MUST return the string `\"x\"`.\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nmake() -> str\n```\n",
    )
    write(
        comp_dir / "acceptance" / (acid + ".md"),
        "# " + acid + "\n\nCovers: " + rid + "\nKind: generated-test\n\n"
        "```gherkin\nGiven nothing\nWhen make() is called\nThen the result is \"x\"\n```\n",
    )
    write(
        comp_dir / "constraints.md",
        "# " + slug.capitalize() + " \u2014 Non-Functional Constraints\n\n- **Pure.** No I/O.\n",
    )


def cycle_findings(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-004"
    ]


def names_both(finding):
    text = str(field(finding, "message")) + " " + str(field(finding, "file"))
    return "comp-alpha" in text and "comp-beta" in text


def test_cycle_between_two_components_is_fail_finding_naming_both(tmp_path):
    write_clean_corpus(tmp_path)
    write_sealed_component(tmp_path, "alpha", ["comp-beta"])
    write_sealed_component(tmp_path, "beta", ["comp-alpha"])

    report = spec_linter.lint(None, tmp_path)

    findings = cycle_findings(report)
    assert findings, "expected an R-LINT-004 finding, got: " + repr(field(report, "findings"))
    matching = [
        f for f in findings
        if field(f, "severity") == "fail" and names_both(f)
    ]
    assert matching, "no fail R-LINT-004 finding naming comp-alpha and comp-beta: " + repr(findings)
    for f in matching:
        assert "comp-alpha" in str(field(f, "message"))
        assert "comp-beta" in str(field(f, "message"))
    assert field(report, "hard_failures") >= 1


def test_acyclic_dependency_has_no_cycle_finding(tmp_path):
    write_clean_corpus(tmp_path)
    write_sealed_component(tmp_path, "alpha", ["comp-beta"])
    write_sealed_component(tmp_path, "beta", [])

    report = spec_linter.lint(None, tmp_path)

    assert cycle_findings(report) == []


def test_cli_reports_cycle_and_exits_one(tmp_path, capsys):
    write_clean_corpus(tmp_path)
    write_sealed_component(tmp_path, "alpha", ["comp-beta"])
    write_sealed_component(tmp_path, "beta", ["comp-alpha"])

    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 1
    data = json.loads(out)
    matching = [
        f for f in data["findings"]
        if f["rule_id"] == "R-LINT-004"
        and f["severity"] == "fail"
        and "comp-alpha" in f["message"]
        and "comp-beta" in f["message"]
    ]
    assert matching, "no matching finding in CLI JSON: " + out
    assert data["summary"]["hard_failures"] >= 1