# hotdocs-criterion: sha256:20fe861aeb42c2d147e3b44c11d8147222c62e9adfcf67d7b04a36e409d02fa9
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
    "owners: [team-foo]\n"
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
    "- In scope: the thing.\n"
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


def _requirement(rid, text):
    return "# " + rid + "\n\n**" + rid + "** — " + text + "\n"


def _acceptance(acid, rid):
    return (
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo\n"
        "When the thing runs\n"
        "Then it completes\n"
        "```\n"
    )


def _build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(
        _requirement("R-FOO-001", "The foo MUST do the first thing.")
    )
    (comp / "requirements" / "R-FOO-002.md").write_text(
        _requirement("R-FOO-002", "The foo MUST do the second thing.")
    )
    # Only R-FOO-002 is covered; R-FOO-001 has zero covering criteria.
    (comp / "acceptance" / "AC-FOO-002.md").write_text(
        _acceptance("AC-FOO-002", "R-FOO-002")
    )
    (comp / "constraints.md").write_text(
        "# Constraints\n\n- None beyond the defaults.\n"
    )
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Thing** — a thing foo does.\n"
    )


def _names(finding, rid):
    message = str(field(finding, "message") or "")
    file_ = str(field(finding, "file") or "")
    return rid in message or (rid + ".md") in file_


def _check_findings(findings):
    lint8 = [f for f in findings if field(f, "rule_id") == "R-LINT-008"]
    hits = [
        f for f in lint8
        if field(f, "severity") == "fail" and _names(f, "R-FOO-001")
    ]
    assert hits, (
        "expected a fail-severity R-LINT-008 finding naming R-FOO-001, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"),
                 field(f, "message")) for f in findings])
    )
    # The covered requirement is not reported as untraced.
    assert not [f for f in lint8 if _names(f, "R-FOO-002")]


def test_uncovered_requirement_fails_forward_traceability(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    _check_findings(findings)
    assert field(report, "hard_failures") >= 1


def test_uncovered_requirement_fails_via_cli_json(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    data = json.loads(out)
    _check_findings(data["findings"])
    assert data["summary"]["hard_failures"] >= 1