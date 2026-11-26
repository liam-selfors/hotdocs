# hotdocs-criterion: sha256:e35ded98ae95b012b12d918200a3d592182eae43edb2357669fc19dd6320cb91
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing used in tests.\n",
    )
    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Adds numbers for tests.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: adding numbers.\n"
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
    # Requirement with no RFC 2119 keyword at all.
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The foo component returns the sum of its two inputs.\n",
    )
    # Control requirement that does use an RFC 2119 keyword.
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — The foo component MUST reject negative inputs.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given inputs 1 and 2\n"
        "When foo runs\n"
        "Then the result is 3\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given inputs -1 and 2\n"
        "When foo runs\n"
        "Then it is rejected\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n- Latency under 1 ms, measured by a timer.\n",
    )


def test_requirement_without_rfc2119_keyword_fails_r_lint_007(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    r007 = [f for f in findings if field(f, "rule_id") == "R-LINT-007"]
    bad = [
        f
        for f in r007
        if str(field(f, "file")).replace("\\", "/").endswith("R-FOO-001.md")
    ]
    assert bad, "expected an R-LINT-007 finding for R-FOO-001.md, got: " + repr(
        [(field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in findings]
    )
    assert any(field(f, "severity") == "fail" for f in bad)

    good = [
        f
        for f in r007
        if str(field(f, "file")).replace("\\", "/").endswith("R-FOO-002.md")
    ]
    assert not good, "R-FOO-002 uses MUST and must not be flagged: " + repr(
        [field(f, "message") for f in good]
    )

    assert field(report, "hard_failures") >= 1