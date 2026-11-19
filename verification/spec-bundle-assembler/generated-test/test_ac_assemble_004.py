# hotdocs-criterion: sha256:095a9f01f6c81ad0a87a20e9bd6b0dbabeed69335e14ca7bd6cb4327f5f89d83
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


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
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY_V1 = "# Glossary\n\n- **Foo** \u2014 a test term."
GLOSSARY_V2 = (
    "# Glossary\n\n- **Foo** \u2014 a test term.\n\n"
    "- **Doubling** \u2014 multiplying a number by two."
)


def build_corpus(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY_V1)
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
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
        "Foo doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def test_ac_assemble_004_glossary_equals_current_glossary_file(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    glossary_path = repo_root / "specs" / "glossary.md"

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    expected = glossary_path.read_text(encoding="utf-8")
    assert field(bundle, "glossary") == expected

    # Change the glossary: the bundle must reflect the *current* content.
    write(glossary_path, GLOSSARY_V2)
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle2 = spec_bundle_assembler.assemble("comp-foo", repo_root)
    expected2 = glossary_path.read_text(encoding="utf-8")
    assert field(bundle2, "glossary") == expected2
    assert field(bundle2, "glossary") != expected