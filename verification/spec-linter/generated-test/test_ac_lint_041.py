# hotdocs-criterion: sha256:9367768377c7610ee5bee77a7173c4d69bac51c0ba181cc521e0202d7b8c3d3b
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fake_checker_source(findings):
    return (
        "def check(repo_root):\n"
        "    return " + repr(findings) + "\n"
    )


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
    "Foo returns one, so its callers have a constant to rely on.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: returning one.\n"
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
    "**R-FOO-001** \u2014 `foo()` MUST return `1`.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "foo() -> int\n"
    "```\n"
    "\n"
    "Returns `1`.\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- `foo()` returns within 10 ms, measured by timing 100 calls.\n"
)

ACCEPTANCE_CLEAN = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When foo() is called\n"
    "Then it returns 1\n"
    "```\n"
)

ACCEPTANCE_NO_STEPS = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "This criterion states no steps at all.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo** \u2014 the example component's one constant.\n"
)

ONE_WARN = [
    {
        "rule_id": "R-SIZE-003",
        "severity": "warn",
        "file": "specs/components/foo/component.md",
        "line": 1,
        "message": "specs/components/foo/component.md has 9999 words, above the per-file warn threshold of 1000",
    }
]


def build_clean_corpus(repo_root, size_findings=None):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    write(specs / "glossary.md", GLOSSARY_MD)
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_CLEAN)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(
        repo_root / "gen" / "citation-checker" / "citation_checker.py",
        fake_checker_source([]),
    )
    write(
        repo_root / "gen" / "size-checker" / "size_checker.py",
        fake_checker_source(size_findings if size_findings is not None else []),
    )
    return repo_root


def run_json(capsys, argv):
    capsys.readouterr()
    code = spec_linter.main(argv)
    out = capsys.readouterr().out
    return code, out


def test_clean_corpus_returns_zero_with_no_hard_failures(tmp_path, capsys):
    repo_root = build_clean_corpus(tmp_path / "repo")
    code, out = run_json(
        capsys, ["--repo-root=" + str(repo_root), "--format=json"]
    )
    assert code == 0, out
    report = json.loads(out)
    assert report["summary"]["hard_failures"] == 0


def test_one_warn_edit_returns_zero_then_one_with_strict(tmp_path, capsys):
    repo_root = build_clean_corpus(tmp_path / "repo", size_findings=ONE_WARN)
    argv = ["--repo-root=" + str(repo_root), "--format=json"]

    code, out = run_json(capsys, list(argv))
    assert code == 0, out
    report = json.loads(out)
    assert report["summary"]["hard_failures"] == 0
    assert report["summary"]["warnings"] >= 1

    code_strict, out_strict = run_json(capsys, list(argv) + ["--strict"])
    assert code_strict == 1, out_strict
    strict_report = json.loads(out_strict)
    assert strict_report["summary"]["hard_failures"] >= 1


def test_one_fail_edit_returns_one_with_one_r_lint_010_finding(tmp_path, capsys):
    repo_root = build_clean_corpus(tmp_path / "repo")
    write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        ACCEPTANCE_NO_STEPS,
    )
    code, out = run_json(
        capsys, ["--repo-root=" + str(repo_root), "--format=json"]
    )
    assert code == 1, out
    report = json.loads(out)
    lint_010 = [f for f in report["findings"] if field(f, "rule_id") == "R-LINT-010"]
    assert len(lint_010) == 1, report["findings"]
    assert field(lint_010[0], "severity") == "fail"


def test_bad_format_value_returns_two(tmp_path, capsys):
    build_clean_corpus(tmp_path / "repo")
    capsys.readouterr()
    code = spec_linter.main(["--format=xml"])
    assert code == 2