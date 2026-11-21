# hotdocs-criterion: sha256:f123f43674a3fcf96cfd498823489a2368769c678d51c91872d1c0d416788c0f
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


GLOSSARY_V1 = "# Glossary\n\n- **Foo** \u2014 a test term."
GLOSSARY_V2 = (
    "# Glossary\n\n- **Foo** \u2014 a test term.\n"
    "- **Widget** \u2014 a second test term, added later."
)


def write_component(repo_root, slug, comp_id, title, upper, depends_on, func):
    root = repo_root / "specs" / "components" / slug
    write(
        root / "component.md",
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "depends_on: [" + depends_on + "]\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + title + " doubles a number.\n",
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    write(
        root / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** \u2014 `" + func + "(x)` MUST return `2 * x`.\n",
    )
    write(
        root / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When " + func + "(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        root / "interface" / "library.md",
        "# Library\n\n```\n" + func + "(x: int) -> int\n```\n",
    )
    write(root / "constraints.md", "# Constraints\n\nNone.\n")


def build_corpus(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY_V1)
    write_component(repo_root, "foo", "comp-foo", "Foo", "FOO", "", "foo")
    write_component(repo_root, "bar", "comp-bar", "Bar", "BAR", "comp-foo", "bar")


def test_glossary_field_equals_current_glossary_content(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    glossary_path = repo_root / "specs" / "glossary.md"

    for comp_id in ("comp-foo", "comp-bar"):
        bundle = spec_bundle_assembler.assemble(comp_id, repo_root)
        expected = glossary_path.read_text(encoding="utf-8")
        assert field(bundle, "glossary") == expected

    # The glossary is read as it is now, not cached from an earlier run.
    write(glossary_path, GLOSSARY_V2)
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    for comp_id in ("comp-foo", "comp-bar"):
        bundle = spec_bundle_assembler.assemble(comp_id, repo_root)
        expected = glossary_path.read_text(encoding="utf-8")
        assert expected == GLOSSARY_V2
        assert field(bundle, "glossary") == expected