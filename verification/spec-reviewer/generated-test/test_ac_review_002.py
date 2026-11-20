# hotdocs-criterion: sha256:8dfa3f9677629ee02d716cc9378c4c984e03f16ad12be6d24dd238dce784d85b
import importlib.util
import sys
from pathlib import Path

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


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

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
)

ACCEPTANCE_CLEAN = (
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

ACCEPTANCE_NO_KIND = (
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

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "foo(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root, acceptance_text):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    write(specs / "glossary.md", GLOSSARY)
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", acceptance_text)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)


def test_fail_lint_finding_stops_check_before_model(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, ACCEPTANCE_NO_KIND)

    calls = []

    def llm_backend(prompt, model, **params):
        calls.append(prompt)
        return {
            "text": '{"conflicts": false, "rationale": "ok"}',
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    report = spec_reviewer.check(["comp-foo"], repo_root, model="mock", llm_backend=llm_backend)

    lint_findings = list(field(report, "lint_findings"))
    severities = [field(f, "severity") for f in lint_findings]
    assert "fail" in severities, lint_findings
    assert list(field(report, "criteria_checked")) == []
    assert len(calls) == 0


def test_lint_clean_corpus_checks_criteria(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, ACCEPTANCE_CLEAN)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    report = spec_reviewer.check(["comp-foo"], repo_root)

    lint_findings = list(field(report, "lint_findings"))
    for f in lint_findings:
        assert field(f, "severity") != "fail", f
    assert len(list(field(report, "criteria_checked"))) > 0