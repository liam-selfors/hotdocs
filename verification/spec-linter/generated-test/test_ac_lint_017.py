# hotdocs-criterion: sha256:a064764a8c68db6f3afbc88a5b13696e67e121a58d77d6a89c459edb92067263
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, guarantee_heading):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing the fixture talks about.\n",
    )
    comp = specs / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small thing for the fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the small thing.\n"
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
        "- Initial draft.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST return the small thing when asked.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given foo is available\n"
        "When it is asked for the small thing\n"
        "Then it returns the small thing\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    guarantee = comp / "interface" / "guarantees" / "G-FOO-001.md"
    write(
        guarantee,
        "# " + guarantee_heading + "\n"
        "\n"
        "**" + guarantee_heading + "** — Foo MUST return the same small thing "
        "for the same request.\n",
    )
    return guarantee


def r_lint_017_fails(report):
    out = []
    for finding in field(report, "findings"):
        if field(finding, "rule_id") == "R-LINT-017" and field(finding, "severity") == "fail":
            out.append(finding)
    return out


def test_guarantee_heading_differs_from_filename_stem_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "G-FOO-002")

    report = spec_linter.lint(None, repo_root)

    fails = r_lint_017_fails(report)
    assert fails, "expected a fail-severity R-LINT-017 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "file")) for f in field(report, "findings")]
    )
    assert any("G-FOO-001" in str(field(f, "file")) for f in fails)
    assert field(report, "hard_failures") >= 1


def test_guarantee_heading_matching_stem_has_no_r_lint_017_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "G-FOO-001")

    report = spec_linter.lint(None, repo_root)

    assert r_lint_017_fails(report) == []