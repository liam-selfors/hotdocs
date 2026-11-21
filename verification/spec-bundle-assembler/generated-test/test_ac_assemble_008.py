# hotdocs-criterion: sha256:ed4ed4b0ec3c199a29e57ca410b1dcdf74bbd2343bae0ccd03f1cc0051517fe5
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test term.\n"
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

REQUIREMENT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
)

ACCEPTANCE = (
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

LIBRARY = (
    "# Library\n"
    "\n"
    "```\n"
    "foo(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS = (
    "# Constraints\n"
    "\n"
    "None.\n"
)

LEGACY_CODE = (
    "def foo(x):\n"
    "    return 2 * x\n"
)

GEN_MAIN = (
    "def foo(x):\n"
    "    # current generated code\n"
    "    return x + x\n"
)

GEN_NESTED = (
    "Some notes kept beside the generated code.\n"
)


def build_corpus(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "constraints.md", CONSTRAINTS)
    write(repo_root / "legacy" / "foo" / "foo.py", LEGACY_CODE)


OTHER_FIELDS = [
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


def test_hint_mode_adds_hint_code_and_only_changes_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    write(repo_root / "gen" / "foo" / "foo.py", GEN_MAIN)
    write(repo_root / "gen" / "foo" / "sub" / "notes.txt", GEN_NESTED)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    cold = spec_bundle_assembler.assemble("comp-foo", repo_root)
    hint = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="hint")

    # Cold mode carries no hint code.
    assert field(cold, "hint_code") is None

    # Hint mode carries the gen/foo/ content keyed by relative path.
    hint_code = field(hint, "hint_code")
    assert hint_code is not None
    normalized = {str(k).replace("\\", "/"): v for k, v in dict(hint_code).items()}
    assert normalized == {
        "foo.py": GEN_MAIN,
        "sub/notes.txt": GEN_NESTED,
    }

    # Every other field except spec_bundle_hash matches cold mode.
    for name in OTHER_FIELDS:
        assert field(hint, name) == field(cold, name), name

    # The hash differs, since hint mode hashes the mode and gen/foo/.
    cold_hash = field(cold, "spec_bundle_hash")
    hint_hash = field(hint, "spec_bundle_hash")
    assert isinstance(cold_hash, str) and cold_hash.startswith("sha256:")
    assert isinstance(hint_hash, str) and hint_hash.startswith("sha256:")
    assert hint_hash != cold_hash