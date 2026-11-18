# hotdocs-criterion: sha256:5fc4d0246fbc8b3a64252ef19c136c88bf1b8793832219122ae90606823bf0e4
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Adds two numbers together for its callers.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: addition.\n"
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

# No RFC 2119 keyword anywhere in this requirement's text.
REQ_NO_KEYWORD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 The widget returns the sum of its two inputs.\n"
)

# Control: this requirement does use an RFC 2119 keyword.
REQ_WITH_KEYWORD = (
    "# R-FOO-002\n"
    "\n"
    "**R-FOO-002** \u2014 The widget MUST reject a non-numeric input.\n"
)


def acceptance(ac_id, req_id):
    return (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given two numbers\n"
        "When the widget runs\n"
        "Then it returns a result\n"
        "```\n"
    )


def build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQ_NO_KEYWORD)
    (comp / "requirements" / "R-FOO-002.md").write_text(REQ_WITH_KEYWORD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(acceptance("AC-FOO-001", "R-FOO-001"))
    (comp / "acceptance" / "AC-FOO-002.md").write_text(acceptance("AC-FOO-002", "R-FOO-002"))
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n")
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Widget** \u2014 the thing that adds numbers.\n"
    )


def _lint007(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-007"]


def test_requirement_without_rfc2119_keyword_fails_lint(tmp_path):
    build_fixture(tmp_path)

    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))

    lint007 = _lint007(findings)
    bad = [
        f for f in lint007
        if str(field(f, "file")).replace("\\", "/").endswith(
            "specs/components/foo/requirements/R-FOO-001.md"
        )
    ]
    assert bad, "expected an R-LINT-007 finding for R-FOO-001.md, got: " + repr(findings)
    assert any(field(f, "severity") == "fail" for f in bad), repr(bad)

    # The requirement that does use an RFC 2119 keyword draws no R-LINT-007 failure.
    good = [
        f for f in lint007
        if str(field(f, "file")).replace("\\", "/").endswith(
            "specs/components/foo/requirements/R-FOO-002.md"
        )
        and field(f, "severity") == "fail"
    ]
    assert good == [], repr(good)

    assert field(report, "hard_failures") >= 1


def test_cli_reports_r_lint_007_failure(tmp_path, capsys):
    build_fixture(tmp_path)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 1
    data = json.loads(out)
    findings = data["findings"]
    matching = [
        f for f in findings
        if f["rule_id"] == "R-LINT-007"
        and f["severity"] == "fail"
        and str(f["file"]).replace("\\", "/").endswith(
            "specs/components/foo/requirements/R-FOO-001.md"
        )
    ]
    assert matching, repr(findings)
    assert data["summary"]["hard_failures"] >= 1