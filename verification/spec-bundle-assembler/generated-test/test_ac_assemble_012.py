import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


PURPOSE_MARKER = "Foo doubles a number using the amberfalcon method."
SCOPE_MARKER = "Scope covers only integers within the copperlantern range."
RATIONALE_MARKER = "Doubling was chosen over tripling because of the velvetquokka incident."
OPEN_QUESTIONS_MARKER = "Should negative inputs be handled by the marbleotter path?"
CHANGE_LOG_MARKER = "Initial draft recorded during the saffronbadger review."


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
    + PURPOSE_MARKER + "\n"
    "\n"
    "## Scope\n"
    "\n"
    + SCOPE_MARKER + "\n"
    "\n"
    "## Rationale\n"
    "\n"
    + RATIONALE_MARKER + "\n"
    "\n"
    "## Open questions\n"
    "\n"
    "- " + OPEN_QUESTIONS_MARKER + "\n"
    "\n"
    "## Change log\n"
    "\n"
    "- " + CHANGE_LOG_MARKER + "\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test term.\n"
)

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
)

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

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "foo(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "None.\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def test_ac_assemble_012_cold_spec_excludes_rationale_open_questions_change_log(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard_failures = _field(report, "hard_failures")
    assert hard_failures == 0, (
        "fixture corpus must be lint-clean; findings: "
        + repr(_field(report, "findings"))
    )

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    spec_text = _field(bundle, "spec")
    assert isinstance(spec_text, str), "SpecBundle.spec must be a string"

    # Purpose and Scope text is retained.
    assert PURPOSE_MARKER in spec_text, "Purpose text missing from spec"
    assert SCOPE_MARKER in spec_text, "Scope text missing from spec"

    # Rationale, Open questions and Change log text is excluded.
    assert RATIONALE_MARKER not in spec_text, "Rationale text leaked into spec"
    assert "velvetquokka" not in spec_text, "Rationale text leaked into spec"
    assert OPEN_QUESTIONS_MARKER not in spec_text, "Open questions text leaked into spec"
    assert "marbleotter" not in spec_text, "Open questions text leaked into spec"
    assert CHANGE_LOG_MARKER not in spec_text, "Change log text leaked into spec"
    assert "saffronbadger" not in spec_text, "Change log text leaked into spec"