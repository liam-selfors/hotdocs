# hotdocs-criterion: sha256:7fbaa4fb3cb523aaf5c5635bd633b87ff55b0e67a273ebaf92fce40327c788c9
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def component_files(slug, depends_on="[]", extra_frontmatter="", purpose="Foo doubles a number."):
    """The files of one fixture component, keyed by path under repo_root."""
    upper = slug.upper()
    base = f"specs/components/{slug}/"
    return {
        base + "component.md": (
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {slug.capitalize()}\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}/\n"
            f"depends_on: {depends_on}\n"
            + extra_frontmatter +
            "---\n"
            "\n"
            f"# {slug.capitalize()}\n"
            "\n"
            "## Purpose\n"
            "\n"
            f"{purpose}\n"
        ),
        base + f"requirements/R-{upper}-001.md": (
            f"# R-{upper}-001\n"
            "\n"
            f"**R-{upper}-001** — `foo(x)` MUST return `2 * x`.\n"
        ),
        base + f"acceptance/AC-{upper}-001.md": (
            f"# AC-{upper}-001\n"
            "\n"
            f"Covers: R-{upper}-001\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
            "```\n"
        ),
        base + "interface/library.md": "# Library\n\n```\nfoo(x: int) -> int\n```\n",
        base + "constraints.md": "# Constraints\n\nNone.\n",
    }


def write_fixture(repo_root, files):
    files = {"specs/glossary.md": "# Glossary\n\n- **Foo** — a test term.\n", **files}
    for rel, text in files.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


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


# Glossary texts with no leading or trailing whitespace, so the file's
# content and its stripped body are the same string.
GLOSSARY_ONE = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for the fixture corpus.\n"
    "\n"
    "- **Foo** — a test term.\n"
    "- **Widget** — a second test term,\n"
    "  continued on a second line."
)

GLOSSARY_TWO = (
    "# Glossary\n"
    "\n"
    "Revised vocabulary for the fixture corpus.\n"
    "\n"
    "- **Foo** — a test term, reworded.\n"
    "- **Gadget** — a third test term."
)


def test_ac_assemble_004_glossary_is_current_glossary_content(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    files = component_files("foo")
    files["specs/glossary.md"] = GLOSSARY_ONE
    write_fixture(repo_root, files)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    expected = (repo_root / "specs" / "glossary.md").read_text(encoding="utf-8")
    assert expected == GLOSSARY_ONE
    assert field(bundle, "glossary") == expected

    # The glossary is the *current* content: change it and re-assemble.
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_TWO, encoding="utf-8")
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle2 = spec_bundle_assembler.assemble("comp-foo", repo_root)
    expected2 = (repo_root / "specs" / "glossary.md").read_text(encoding="utf-8")
    assert field(bundle2, "glossary") == expected2
    assert field(bundle2, "glossary") != GLOSSARY_ONE


def test_ac_assemble_004_glossary_for_any_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    files = component_files("foo")
    files.update(component_files("baz", depends_on="[comp-foo]"))
    files["specs/glossary.md"] = GLOSSARY_ONE
    write_fixture(repo_root, files)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    expected = (repo_root / "specs" / "glossary.md").read_text(encoding="utf-8")
    for component_id in ("comp-foo", "comp-baz"):
        bundle = spec_bundle_assembler.assemble(component_id, repo_root)
        assert field(bundle, "glossary") == expected
        assert bundle["glossary"] == expected