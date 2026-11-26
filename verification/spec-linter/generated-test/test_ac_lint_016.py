# hotdocs-criterion: sha256:dd3247cf4ef2b88286d29578fa7e37a6af74ae2f860347c70870e344aa9dc99c
import importlib.util
import sys
from pathlib import Path

import spec_linter


def _load_spec_linter():
    gen = next(p for p in Path(spec_linter.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


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

REQUIREMENT_BODY = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST do the small thing.\n"
)

REQUIREMENT_FRONTMATTER = (
    "---\n"
    "id: R-FOO-001\n"
    "title: Do the small thing\n"
    "status: draft\n"
    "---\n"
    "\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given foo is ready\n"
    "When foo runs\n"
    "Then foo did the small thing\n"
    "```\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Thing** — a small thing.\n"
)


def _build_repo(repo_root, with_frontmatter):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (specs / "product").mkdir(parents=True)
    (specs / "architecture").mkdir(parents=True)
    (specs / "vars").mkdir(parents=True)
    (specs / "decisions").mkdir(parents=True)
    (specs / "glossary.md").write_text(GLOSSARY_MD)
    (comp / "component.md").write_text(COMPONENT_MD)
    req_text = (REQUIREMENT_FRONTMATTER + REQUIREMENT_BODY) if with_frontmatter else REQUIREMENT_BODY
    (comp / "requirements" / "R-FOO-001.md").write_text(req_text)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)


def _lint016_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-016"]


def test_requirement_with_frontmatter_fails_r_lint_016(tmp_path):
    linter = _load_spec_linter()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, with_frontmatter=True)

    report = linter.lint(None, repo_root)
    hits = _lint016_findings(report)

    fail_hits = [f for f in hits if field(f, "severity") == "fail"]
    assert fail_hits, "expected a fail-severity R-LINT-016 finding, got: " + repr(field(report, "findings"))
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith("requirements/R-FOO-001.md")
        for f in fail_hits
    ), repr(fail_hits)
    assert field(report, "hard_failures") >= 1


def test_requirement_without_frontmatter_has_no_r_lint_016(tmp_path):
    linter = _load_spec_linter()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, with_frontmatter=False)

    report = linter.lint(None, repo_root)
    hits = _lint016_findings(report)
    assert hits == [], repr(hits)