# hotdocs-criterion: sha256:4dec2bc8e4c5502e2d4a1a427d215bbef68fc948916f2137cfba5b311a094fc9
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    return load_module(path, "spec_linter")


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Foo** \u2014 a test term.\n"
)

COMPONENT = (
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
    "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"
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

CONSTRAINTS = (
    "# Constraints\n"
    "\n"
    "None.\n"
)

RULES = (
    "---\n"
    "id: arch-rules\n"
    "title: Rules\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Rules\n"
    "\n"
    "Foo rounds down.\n"
)


def library_md(implements_path):
    return (
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "Implements: `" + implements_path + "`\n"
    )


def build_fixture(repo_root, implements_path):
    files = {
        "specs/glossary.md": GLOSSARY,
        "specs/components/foo/component.md": COMPONENT,
        "specs/components/foo/requirements/R-FOO-001.md": REQUIREMENT,
        "specs/components/foo/acceptance/AC-FOO-001.md": ACCEPTANCE,
        "specs/components/foo/interface/library.md": library_md(implements_path),
        "specs/components/foo/constraints.md": CONSTRAINTS,
        "specs/architecture/rules.md": RULES,
    }
    for rel, text in files.items():
        p = repo_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def assert_implements_appended(interface, rules_text):
    marker = "\n## Implements: specs/architecture/rules.md\n\n"
    idx = interface.find(marker)
    assert idx != -1, "marker not found in interface: " + repr(interface)
    after = interface[idx + len(marker):]
    # Immediately followed by the file's full text...
    assert after.startswith(rules_text.rstrip()), repr(after)
    # ...and nothing but whitespace after it.
    assert after[len(rules_text.rstrip()):].strip() == "", repr(after)


def test_implements_document_appended_to_both_bundles(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "specs/architecture/rules.md")

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    rules_text = (repo_root / "specs/architecture/rules.md").read_text(encoding="utf-8")

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    assert_implements_appended(field(bundle, "interface"), rules_text)

    cbundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert_implements_appended(field(cbundle, "interface"), rules_text)


def test_missing_implements_path_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "specs/architecture/missing.md")

    precondition_failure = getattr(spec_bundle_assembler, "PreconditionFailure")
    with pytest.raises(precondition_failure):
        spec_bundle_assembler.assemble("comp-foo", repo_root)