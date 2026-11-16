import spec_bundle_assembler

import importlib.util
import sys
from pathlib import Path


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

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

LEGACY_FOO_PY = "def foo(x):\n    return 2 * x\n"

GEN_FILES = {
    "foo.py": "def foo(x):\n    \"\"\"Double x.\"\"\"\n    return 2 * x\n",
    "sub/helper.py": "HELPER_MARKER = 'hint-content-marker-123'\n",
}

COMPARED_FIELDS = [
    "component_id",
    "spec",
    "interface",
    "constraints",
    "dependency_interfaces",
    "dependency_context",
    "dependency_usage",
    "vars",
    "glossary",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "legacy" / "foo" / "foo.py", LEGACY_FOO_PY)
    for rel, text in GEN_FILES.items():
        _write(repo_root / "gen" / "foo" / rel, text)


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


def test_ac_assemble_008_hint_mode_adds_hint_code_and_changes_only_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    cold = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    hint = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="hint")

    # Cold mode carries no hint_code.
    assert field(cold, "hint_code") is None

    # Hint mode carries the gen/foo/ content, keyed by relative path.
    hint_code = field(hint, "hint_code")
    assert hint_code is not None
    assert dict(hint_code) == GEN_FILES

    # Every other field except spec_bundle_hash matches cold mode.
    for name in COMPARED_FIELDS:
        assert field(hint, name) == field(cold, name), (
            f"field {name!r} differs between hint and cold mode"
        )

    # The gen/ content is kept separate, never merged into the cold fields.
    for name in ("spec", "interface", "constraints", "glossary"):
        assert "hint-content-marker-123" not in field(hint, name)

    # spec_bundle_hash differs, since the mode and gen/foo/ are hashed in hint mode.
    cold_hash = field(cold, "spec_bundle_hash")
    hint_hash = field(hint, "spec_bundle_hash")
    assert isinstance(cold_hash, str) and cold_hash
    assert isinstance(hint_hash, str) and hint_hash
    assert hint_hash != cold_hash