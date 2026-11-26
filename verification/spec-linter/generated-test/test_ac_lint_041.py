# hotdocs-criterion: sha256:9367768377c7610ee5bee77a7173c4d69bac51c0ba181cc521e0202d7b8c3d3b
import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    "Foo returns a greeting for a name.\n"
    "\n"
    "## Rationale\n"
    "\n"
    "Chosen in `D1`.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: greeting.\n"
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

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `greet(name)` MUST return `hello <name>` (`D1`).\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "greet(name: str) -> str\n"
    "```\n"
)

GOOD_ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given the name \"bob\"\n"
    "When greet(\"bob\") runs\n"
    "Then it returns \"hello bob\"\n"
    "```\n"
)

BAD_ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "The greeting for bob is hello bob.\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- greet returns within 1 second, measured by a timed call.\n"
)

DECISION_MD = (
    "---\n"
    "id: D1\n"
    "title: Greeting format\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "---\n"
    "\n"
    "# D1\n"
    "\n"
    "Greetings are `hello <name>`.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Greeting** \u2014 the text `greet` returns.\n"
)


def fake_checker_source(findings):
    return (
        "def check(repo_root):\n"
        "    return [dict(f) for f in " + repr(findings) + "]\n"
    )


def build_clean_corpus(root, warn=False):
    write(root / "specs" / "glossary.md", GLOSSARY_MD)
    write(root / "specs" / "decisions" / "D1.md", DECISION_MD)
    comp = root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", GOOD_ACCEPTANCE_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    citation_findings = []
    if warn:
        citation_findings = [
            {
                "rule_id": "R-CITE-001",
                "severity": "warn",
                "file": "specs/components/foo/requirements/R-FOO-001.md",
                "line": 3,
                "message": "citation D1 may not state this fact",
            }
        ]
    write(
        root / "gen" / "citation-checker" / "citation_checker.py",
        fake_checker_source(citation_findings),
    )
    write(
        root / "gen" / "size-checker" / "size_checker.py",
        fake_checker_source([]),
    )


def run_json(capsys, root, extra=()):
    capsys.readouterr()
    code = spec_linter.main(["--repo-root=" + str(root), "--format=json"] + list(extra))
    out = capsys.readouterr().out
    return code, json.loads(out)


def test_clean_corpus_returns_zero(tmp_path, capsys):
    root = tmp_path / "repo"
    build_clean_corpus(root)
    code, report = run_json(capsys, root)
    assert code == 0
    assert report["summary"]["hard_failures"] == 0


def test_one_warn_edit_strict_changes_exit(tmp_path, capsys):
    root = tmp_path / "repo"
    build_clean_corpus(root, warn=True)
    code, report = run_json(capsys, root)
    assert code == 0
    assert report["summary"]["hard_failures"] == 0
    code_strict, report_strict = run_json(capsys, root, ["--strict"])
    assert code_strict == 1
    assert report_strict["summary"]["hard_failures"] >= 1


def test_one_fail_edit_returns_one_with_lint_010(tmp_path, capsys):
    root = tmp_path / "repo"
    build_clean_corpus(root)
    write(
        root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        BAD_ACCEPTANCE_MD,
    )
    code, report = run_json(capsys, root)
    assert code == 1
    lint_010 = [f for f in report["findings"] if field(f, "rule_id") == "R-LINT-010"]
    assert len(lint_010) == 1


def test_bad_format_is_usage_error(tmp_path, capsys):
    assert spec_linter.main(["--format=xml"]) == 2