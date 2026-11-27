# hotdocs-criterion: sha256:bda8ea9d4d1f7565ebe3e0110ed518d082f23c2f9bb55403614f7d70d4610a10
import importlib.util
import json
import sys
from pathlib import Path

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

REQ_001 = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

AC_001_HEAD = "# AC-FOO-001\n\nCovers: R-FOO-001\n"
AC_001_KIND = "Kind: generated-test\n"
AC_001_TAIL = (
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"
CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def build_corpus(repo_root, with_kind=True):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (specs / "glossary.md").write_text(GLOSSARY, encoding="utf-8")
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(REQ_001, encoding="utf-8")
    ac = AC_001_HEAD + (AC_001_KIND if with_kind else "") + AC_001_TAIL
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ac, encoding="utf-8")
    (comp / "interface" / "library.md").write_text(LIBRARY_MD, encoding="utf-8")
    (comp / "constraints.md").write_text(CONSTRAINTS_MD, encoding="utf-8")


def load_spec_linter():
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def make_counting_backend():
    calls = []

    def backend(prompt, model, **params):
        calls.append(prompt)
        return {
            "text": json.dumps({"writable": True, "gaps": []}),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend, calls


def test_fail_lint_finding_short_circuits_check(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, with_kind=False)

    backend, calls = make_counting_backend()
    report = spec_reviewer.check(["comp-foo"], repo_root, model="mock", llm_backend=backend)

    lint_findings = list(field(report, "lint_findings"))
    severities = [field(f, "severity") for f in lint_findings]
    assert "fail" in severities, lint_findings
    assert list(field(report, "criteria_checked")) == []
    assert len(calls) == 0


def test_lint_clean_corpus_is_checked(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, with_kind=True)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    report = spec_reviewer.check(["comp-foo"], repo_root)

    lint_findings = list(field(report, "lint_findings"))
    for f in lint_findings:
        assert field(f, "severity") != "fail", f
    assert len(list(field(report, "criteria_checked"))) > 0