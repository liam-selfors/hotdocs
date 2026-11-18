# hotdocs-criterion: sha256:095a9f01f6c81ad0a87a20e9bd6b0dbabeed69335e14ca7bd6cb4327f5f89d83
import importlib.util
import sys
from pathlib import Path

import pytest

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


GLOSSARY_V1 = "# Glossary\n\n- **Foo** \u2014 a test term."
GLOSSARY_V2 = (
    "# Glossary\n\n"
    "- **Foo** \u2014 a test term, revised.\n"
    "- **Bar** \u2014 another test term."
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo_root, slug, comp_id, title, upper, depends_on, purpose, func):
    comp_dir = repo_root / "specs" / "components" / slug
    write(
        comp_dir / "component.md",
        "---\n"
        + "id: " + comp_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "depends_on: " + depends_on + "\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n",
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    write(
        comp_dir / "requirements" / (rid + ".md"),
        "# " + rid + "\n"
        + "\n"
        + "**" + rid + "** \u2014 `" + func + "(x)` MUST return `2 * x`.\n",
    )
    write(
        comp_dir / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given x = 2\n"
        + "When " + func + "(x) is called\n"
        + "Then it returns 4\n"
        + "```\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + "```\n"
        + func + "(x: int) -> int\n"
        + "```\n",
    )
    write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        + "\n"
        + "None.\n",
    )


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write(root / "specs" / "glossary.md", GLOSSARY_V1)
    write_component(
        root, "foo", "comp-foo", "Foo", "FOO", "[]",
        "Foo doubles a number.", "foo",
    )
    write_component(
        root, "bar", "comp-bar", "Bar", "BAR", "[comp-foo]",
        "Bar doubles a number using Foo.", "bar",
    )
    return root


def assert_lint_clean(repo_root):
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0


@pytest.mark.parametrize("component_id", ["comp-foo", "comp-bar"])
def test_glossary_field_equals_current_glossary_content(repo_root, component_id):
    assert_lint_clean(repo_root)

    glossary_path = repo_root / "specs" / "glossary.md"

    bundle = spec_bundle_assembler.assemble(component_id, repo_root)
    expected = glossary_path.read_text(encoding="utf-8")
    assert expected == GLOSSARY_V1
    assert field(bundle, "glossary") == expected

    # Change the glossary: the bundle must reflect the *current* content.
    write(glossary_path, GLOSSARY_V2)
    assert_lint_clean(repo_root)

    bundle2 = spec_bundle_assembler.assemble(component_id, repo_root)
    expected2 = glossary_path.read_text(encoding="utf-8")
    assert expected2 == GLOSSARY_V2
    assert field(bundle2, "glossary") == expected2
    assert field(bundle2, "glossary") != GLOSSARY_V1