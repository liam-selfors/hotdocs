import importlib.util
import json
import sys
from pathlib import Path

import pytest

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

REQUIREMENT_MD = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

ACCEPTANCE_NO_KIND_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def write_corpus(repo_root: Path, delete_kind: bool = False) -> None:
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(GLOSSARY, encoding="utf-8")
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD, encoding="utf-8")
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        ACCEPTANCE_NO_KIND_MD if delete_kind else ACCEPTANCE_MD, encoding="utf-8"
    )
    (comp / "interface" / "library.md").write_text(LIBRARY_MD, encoding="utf-8")
    (comp / "constraints.md").write_text(CONSTRAINTS_MD, encoding="utf-8")


def load_spec_linter():
    gen = next(
        p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


def hard_failures(report):
    return report["hard_failures"] if isinstance(report, dict) else report.hard_failures


def make_counting_backend(log_path: Path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        return {
            "text": '{"conflicts": false, "rationale": "ok"}',
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def count_calls(log_path: Path) -> int:
    if not log_path.exists():
        return 0
    return len([ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()])


def test_fail_severity_lint_finding_stops_check_before_any_model_call(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    # Sanity: the corpus is lint-clean before the Kind: line is deleted.
    write_corpus(repo_root, delete_kind=False)
    spec_linter = load_spec_linter()
    assert hard_failures(spec_linter.lint(None, repo_root)) == 0

    # Now delete the Kind: line: a fail-severity lint finding.
    write_corpus(repo_root, delete_kind=True)
    assert hard_failures(spec_linter.lint(None, repo_root)) >= 1

    log_path = tmp_path / "backend_calls.log"
    backend = make_counting_backend(log_path)

    report = spec_reviewer.check(
        ["comp-foo"], repo_root, model="mock", llm_backend=backend
    )

    lint_findings = list(field(report, "lint_findings"))
    severities = [field(f, "severity") for f in lint_findings]
    assert any(s == "fail" for s in severities), lint_findings

    assert list(field(report, "criteria_checked")) == []

    assert count_calls(log_path) == 0


def test_lint_clean_corpus_is_checked(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    write_corpus(repo_root, delete_kind=False)
    spec_linter = load_spec_linter()
    assert hard_failures(spec_linter.lint(None, repo_root)) == 0

    report = spec_reviewer.check(["comp-foo"], repo_root)

    lint_findings = list(field(report, "lint_findings"))
    for f in lint_findings:
        assert field(f, "severity") != "fail", lint_findings

    criteria_checked = list(field(report, "criteria_checked"))
    assert len(criteria_checked) > 0