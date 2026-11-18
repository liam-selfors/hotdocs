# hotdocs-criterion: sha256:095a9f01f6c81ad0a87a20e9bd6b0dbabeed69335e14ca7bd6cb4327f5f89d83
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def _assert_lint_clean(repo_root):
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = (
        report["hard_failures"]
        if isinstance(report, dict)
        else report.hard_failures
    )
    assert hard == 0


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

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

# Written with no leading/trailing whitespace so that the file's exact
# content and its stripped body coincide.
GLOSSARY_V1 = "# Glossary\n\n- **Foo** — a test term."

GLOSSARY_V2 = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test term.\n"
    "- **Bar** — another test term, added later."
)


def _build_corpus(repo_root: Path):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)

    (specs / "glossary.md").write_text(GLOSSARY_V1, encoding="utf-8")
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(
        REQUIREMENT_MD, encoding="utf-8"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        ACCEPTANCE_MD, encoding="utf-8"
    )
    (comp / "interface" / "library.md").write_text(LIBRARY_MD, encoding="utf-8")
    (comp / "constraints.md").write_text(CONSTRAINTS_MD, encoding="utf-8")


def test_ac_assemble_004_glossary_equals_current_glossary_file(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    glossary_path = repo_root / "specs" / "glossary.md"

    _assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    expected = glossary_path.read_text(encoding="utf-8")
    assert field(bundle, "glossary") == expected
    assert field(bundle, "glossary") == GLOSSARY_V1

    # The glossary must reflect the *current* file content, not a cached one.
    glossary_path.write_text(GLOSSARY_V2, encoding="utf-8")
    _assert_lint_clean(repo_root)

    bundle2 = spec_bundle_assembler.assemble("comp-foo", repo_root)
    expected2 = glossary_path.read_text(encoding="utf-8")
    assert field(bundle2, "glossary") == expected2
    assert field(bundle2, "glossary") == GLOSSARY_V2
    assert "**Bar**" in field(bundle2, "glossary")