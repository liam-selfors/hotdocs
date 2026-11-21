# hotdocs-criterion: sha256:2d4dc6715b7fda363378627f4a270bc6212557d04706d79a525d0f0f62f2b5f0
import json
from pathlib import Path

import spec_linter


FENCE = "```"

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
    + FENCE + "gherkin\n"
    "Given nothing\n"
    "When a foo is made\n"
    "Then it exists\n"
    + FENCE + "\n"
)

COMPONENT_MD = (
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
    "\n"
    "## Purpose\n"
    "\n"
    "Makes a foo.\n"
    "\n"
    "## Scope\n"
    "\n"
    "**In scope:** making a foo. **Out of scope:** everything else.\n"
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

REQUIREMENT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n"
)

LIBRARY = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    + FENCE + "\n"
    "make_foo() -> str\n"
    + FENCE + "\n"
)

ACCEPTANCE = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    + FENCE + "gherkin\n"
    "Given nothing\n"
    "When make_foo() is called\n"
    "Then the result is \"foo\"\n"
    + FENCE + "\n"
)

CONSTRAINTS = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)

CLI = (
    "# CLI\n"
    "\n"
    + FENCE + "\n"
    "foo make\n"
    + FENCE + "\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_clean_corpus(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    _write(specs / "product" / "foo.md", PRODUCT_FOO)
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    _write(comp / "constraints.md", CONSTRAINTS)


def run_json(capsys, argv):
    capsys.readouterr()
    code = spec_linter.main(argv)
    out = capsys.readouterr().out
    return code, json.loads(out)


def test_clean_corpus_returns_0_with_zero_hard_failures(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    code, report = run_json(
        capsys, ["--repo-root=" + str(repo_root), "--format=json"]
    )
    assert code == 0
    assert field(field(report, "summary"), "hard_failures") == 0


def test_one_warn_edit_returns_0_then_1_with_strict(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    _write(repo_root / "specs" / "components" / "foo" / "interface" / "cli.md", CLI)
    argv = ["--repo-root=" + str(repo_root), "--format=json"]

    code, report = run_json(capsys, list(argv))
    assert code == 0
    assert field(field(report, "summary"), "hard_failures") == 0

    code_strict, report_strict = run_json(capsys, list(argv) + ["--strict"])
    assert code_strict == 1
    assert field(field(report_strict, "summary"), "hard_failures") >= 1


def test_one_fail_edit_returns_1_with_one_r_lint_010_finding(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    ac = repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md"
    text = ac.read_text(encoding="utf-8")
    edited = "".join(
        line for line in text.splitlines(keepends=True)
        if line.strip() != "Kind: generated-test"
    )
    assert edited != text
    ac.write_text(edited, encoding="utf-8")

    code, report = run_json(
        capsys, ["--repo-root=" + str(repo_root), "--format=json"]
    )
    assert code == 1
    findings = field(report, "findings")
    r010 = [f for f in findings if field(f, "rule_id") == "R-LINT-010"]
    assert len(r010) == 1
    assert field(r010[0], "severity") == "fail"


def test_bad_format_returns_2(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    capsys.readouterr()
    code = spec_linter.main(["--format=xml"])
    assert code == 2