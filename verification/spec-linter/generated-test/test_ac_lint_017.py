# hotdocs-criterion: sha256:b29a77c78500833d6dcc280fb72cfda290f3e997d14a7cdb7e88a650165b1557
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, guarantee_heading):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"

    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Foo** — a thing used by the fixture.\n",
    )

    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo returns results for a fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: foo.\n"
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
        "- Initial draft.\n",
    )

    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The component MUST return results in sorted order.\n",
    )

    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an unsorted input\n"
        "When foo runs\n"
        "Then the results are sorted\n"
        "```\n",
    )

    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )

    _write(
        comp / "interface" / "guarantees" / "G-FOO-001.md",
        "# " + guarantee_heading + "\n"
        "\n"
        "The component MUST return results in sorted order.\n",
    )


def _r_lint_017_fails(report):
    out = []
    for f in field(report, "findings"):
        if str(field(f, "rule_id")) == "R-LINT-017" and str(field(f, "severity")) == "fail":
            out.append(f)
    return out


def test_guarantee_heading_mismatching_filename_is_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, "G-FOO-002")

    report = spec_linter.lint(None, repo_root)

    fails = _r_lint_017_fails(report)
    assert fails, "expected a fail-severity R-LINT-017 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
         for f in field(report, "findings")]
    )
    assert any("G-FOO-001" in str(field(f, "file")) for f in fails)


def test_guarantee_heading_matching_filename_has_no_r_lint_017_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, "G-FOO-001")

    report = spec_linter.lint(None, repo_root)

    fails = [
        f for f in _r_lint_017_fails(report)
        if "G-FOO-001" in str(field(f, "file"))
    ]
    assert fails == [], "unexpected R-LINT-017 failures: " + repr(
        [field(f, "message") for f in fails]
    )