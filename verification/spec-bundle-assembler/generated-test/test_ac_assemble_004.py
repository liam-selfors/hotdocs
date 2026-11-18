# hotdocs-criterion: sha256:095a9f01f6c81ad0a87a20e9bd6b0dbabeed69335e14ca7bd6cb4327f5f89d83
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


GLOSSARY_V1 = "# Glossary\n\n- **Foo** — a test term.\n"
GLOSSARY_V2 = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test term, revised for the second assembly.\n"
    "\n"
    "- **Widget** — another test term spanning\n"
    "  two lines of text.\n"
)

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

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    _write(specs / "glossary.md", GLOSSARY_V1)
    comp = specs / "components" / "foo"
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


def _hard_failures(report):
    if isinstance(report, dict):
        summary = report.get("summary") or {}
        return report.get("hard_failures", summary.get("hard_failures"))
    return getattr(report, "hard_failures", None)


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert _hard_failures(report) == 0


def _assert_glossary_matches(bundle, raw: str) -> None:
    glossary = _field(bundle, "glossary")
    assert isinstance(glossary, str)
    # The SpecBundle contract strips each document body; the glossary must be
    # the file's full content, either verbatim or with only outer whitespace
    # stripped — nothing added, nothing dropped.
    assert glossary in (raw, raw.strip()), (
        f"glossary field {glossary!r} does not equal specs/glossary.md "
        f"content {raw!r}"
    )


def test_ac_assemble_004_glossary_equals_current_glossary_content(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    glossary_path = repo_root / "specs" / "glossary.md"

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    _assert_glossary_matches(bundle, glossary_path.read_text(encoding="utf-8"))

    # "Current" content: change the glossary and re-assemble; the bundle must
    # reflect the new file content, not a cached or stale copy.
    _write(glossary_path, GLOSSARY_V2)
    _assert_lint_clean(repo_root)

    bundle2 = spec_bundle_assembler.assemble("comp-foo", repo_root)
    raw2 = glossary_path.read_text(encoding="utf-8")
    _assert_glossary_matches(bundle2, raw2)
    assert "revised for the second assembly" in _field(bundle2, "glossary")
    assert "two lines of text." in _field(bundle2, "glossary")
    assert _field(bundle2, "glossary") != _field(bundle, "glossary")