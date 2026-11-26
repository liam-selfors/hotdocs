# hotdocs-criterion: sha256:c6e3b960e629a3788b1601b0e6ed01296118d02202a76529176f56f37a7b2277
"""AC-LINT-010: a criterion missing its Kind: line gets a fail finding for R-LINT-010."""

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
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small thing for testing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the small thing.\n"
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


def requirement(rid):
    return (
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** — Foo MUST do the small thing.\n"
    )


def criterion(ac_id, rid, with_kind):
    text = "# " + ac_id + "\n\nCovers: " + rid + "\n"
    if with_kind:
        text += "Kind: generated-test\n"
    text += (
        "\n"
        "```gherkin\n"
        "Given a foo input\n"
        "When foo runs\n"
        "Then the small thing happens\n"
        "```\n"
    )
    return text


def build_corpus(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (specs / "product").mkdir(parents=True)
    (specs / "architecture").mkdir(parents=True)
    (specs / "vars").mkdir(parents=True)
    (specs / "decisions").mkdir(parents=True)

    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Foo thing** — a small thing used for testing.\n"
    )
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "constraints.md").write_text(
        "# Constraints\n\nNone beyond the defaults.\n"
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo() -> None\n```\n"
    )
    (comp / "requirements" / "R-FOO-001.md").write_text(requirement("R-FOO-001"))
    (comp / "requirements" / "R-FOO-002.md").write_text(requirement("R-FOO-002"))
    # The criterion under test: no Kind: line, but a complete Given/When/Then.
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        criterion("AC-FOO-001", "R-FOO-001", with_kind=False)
    )
    # A control criterion carrying its Kind: line.
    (comp / "acceptance" / "AC-FOO-002.md").write_text(
        criterion("AC-FOO-002", "R-FOO-002", with_kind=True)
    )


def norm(path):
    return str(path).replace("\\", "/")


BAD_FILE = "specs/components/foo/acceptance/AC-FOO-001.md"
GOOD_FILE = "specs/components/foo/acceptance/AC-FOO-002.md"
KIND_MESSAGE = "AC-FOO-001 has no Kind: line (compiled, generated-test or llm-judge)"


def lint010_findings(report):
    return [
        f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-010"
    ]


def test_missing_kind_reports_fail_finding_for_r_lint_010(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = lint010_findings(report)

    bad = [f for f in findings if norm(field(f, "file")) == BAD_FILE]
    assert len(bad) == 1, [
        (field(f, "file"), field(f, "message")) for f in findings
    ]
    finding = bad[0]
    assert field(finding, "severity") == "fail"
    assert field(finding, "line") == 1
    assert field(finding, "message") == KIND_MESSAGE

    # The criterion has a complete Given/When/Then block, so no such finding.
    for f in bad:
        assert "lacks a complete Given/When/Then block" not in field(f, "message")

    # The control criterion with a Kind: line draws no R-LINT-010 finding.
    good = [f for f in findings if norm(field(f, "file")) == GOOD_FILE]
    assert good == []

    assert field(report, "hard_failures") >= 1


def test_missing_kind_cli_json_and_exit_code(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1

    doc = json.loads(out)
    matches = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-010" and norm(f["file"]) == BAD_FILE
    ]
    assert len(matches) == 1
    assert matches[0]["severity"] == "fail"
    assert matches[0]["line"] == 1
    assert matches[0]["message"] == KIND_MESSAGE
    assert doc["summary"]["hard_failures"] >= 1