# hotdocs-criterion: sha256:e80ed4e20086f353708d8b57504214f0b57e898ece05d67abe642766ffbb0ca1
"""AC-LINT-016: a unit file under requirements/ carrying YAML frontmatter
yields a fail-severity finding for rule R-LINT-016."""

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
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does one small thing for testing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the one thing.\n"
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

REQ_BODY = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — The component MUST return the input unchanged.\n"
)

REQ_FRONTMATTER = (
    "---\n"
    "id: R-FOO-001\n"
    "title: Foo requirement\n"
    "status: draft\n"
    "---\n"
    "\n"
)

AC_BODY = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given an input\n"
    "When foo runs\n"
    "Then the output equals the input\n"
    "```\n"
)

CONSTRAINTS = (
    "# Constraints\n"
    "\n"
    "- Runs in under one second, measured by a timer.\n"
)

GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Widget** — a small thing used only in tests.\n"
)


def build_corpus(repo_root: Path, with_frontmatter: bool) -> Path:
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    req_text = (REQ_FRONTMATTER + REQ_BODY) if with_frontmatter else REQ_BODY
    req_path = comp / "requirements" / "R-FOO-001.md"
    req_path.write_text(req_text)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(AC_BODY)
    (comp / "constraints.md").write_text(CONSTRAINTS)
    (specs / "glossary.md").write_text(GLOSSARY)
    return req_path


def lint016_fail_findings(report):
    out = []
    for f in field(report, "findings"):
        if field(f, "rule_id") == "R-LINT-016" and field(f, "severity") == "fail":
            out.append(f)
    return out


def test_requirement_with_frontmatter_fails_r_lint_016(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, with_frontmatter=True)

    report = spec_linter.lint(None, repo_root)

    hits = lint016_fail_findings(report)
    assert hits, "expected a fail-severity R-LINT-016 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "file"))
         for f in field(report, "findings")]
    )
    files = [str(field(f, "file")).replace("\\", "/") for f in hits]
    assert any(p.endswith("requirements/R-FOO-001.md") for p in files), files
    assert field(report, "hard_failures") >= 1


def test_requirement_without_frontmatter_has_no_r_lint_016(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, with_frontmatter=False)

    report = spec_linter.lint(None, repo_root)

    assert not any(
        field(f, "rule_id") == "R-LINT-016" for f in field(report, "findings")
    )


def test_cli_reports_r_lint_016_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, with_frontmatter=True)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    hits = [
        f for f in doc["findings"]
        if f["rule_id"] == "R-LINT-016" and f["severity"] == "fail"
    ]
    assert hits
    assert any(
        str(f["file"]).replace("\\", "/").endswith("requirements/R-FOO-001.md")
        for f in hits
    )