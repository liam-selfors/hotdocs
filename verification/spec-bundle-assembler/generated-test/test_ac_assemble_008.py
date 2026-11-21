# hotdocs-criterion: sha256:3cf7ce435553052170ac0d122cbc87f3559b9017017cfd23f5db780f0e97bd55
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n" + "\n" + "- **Foo** — a test term.\n"

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

REQUIREMENT = "# R-FOO-001\n" + "\n" + "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

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

LIBRARY = "# Library\n" + "\n" + "```\n" + "foo(x: int) -> int\n" + "```\n"

CONSTRAINTS = "# Constraints\n" + "\n" + "None.\n"

HINT_FILES = {
    "foo.py": "def foo(x):\n    return 2 * x\n",
    "sub/notes.txt": "Some hint notes about foo.\n",
}


def build_corpus(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "constraints.md", CONSTRAINTS)


def normalize_hint(hint):
    out = {}
    for key, value in dict(hint).items():
        k = str(key).replace("\\", "/")
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        out[k] = value
    return out


def test_ac_assemble_008_hint_mode_adds_hint_code_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    gen_dir = repo_root / "gen" / "foo"
    for rel, content in HINT_FILES.items():
        write(gen_dir / rel, content)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    cold = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    hint = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="hint")

    # Cold mode carries no hint code.
    assert field(cold, "hint_code") is None

    # Hint mode carries gen/foo/ content keyed by relative path.
    hint_code = field(hint, "hint_code")
    assert hint_code is not None
    normalized = normalize_hint(hint_code)
    for rel, content in HINT_FILES.items():
        assert rel in normalized, (rel, sorted(normalized))
        assert normalized[rel] == content

    # Every other field except spec_bundle_hash matches cold mode.
    for name in (
        "component_id",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
    ):
        assert field(hint, name) == field(cold, name), name

    # The hint code is never merged into the cold bundle's own fields.
    for name in ("spec", "interface", "constraints"):
        assert "return 2 * x" not in field(hint, name)
        assert "Some hint notes about foo." not in field(hint, name)

    # The hash differs, since R-ASSEMBLE-007 hashes mode and gen/ content in hint mode.
    cold_hash = field(cold, "spec_bundle_hash")
    hint_hash = field(hint, "spec_bundle_hash")
    assert isinstance(cold_hash, str) and cold_hash.startswith("sha256:")
    assert isinstance(hint_hash, str) and hint_hash.startswith("sha256:")
    assert hint_hash != cold_hash