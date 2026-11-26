# hotdocs-criterion: sha256:c6e3e8d13dae87b749e5e020e8bf177a74b457d7e9e5f1842a8d00bb318d9c88
"""AC-ASSEMBLE-011: dependency_usage is a mechanically-derived usage card per dependency."""

import importlib.util
import inspect
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


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


BAR_DOC_FIRST_LINE = "Return the value stored under key."

BAR_SOURCE = (
    "def bar_get(key: str) -> str:\n"
    "    " + repr(BAR_DOC_FIRST_LINE + "\n\n    Further detail that is not the first line.\n    ") + "\n"
    "    return " + repr("v") + " + key\n"
)


def build_corpus(repo_root):
    files = {}
    files.update(component_files("foo", depends_on="[comp-bar, comp-baz]"))
    files.update(component_files("bar"))
    files.update(component_files("baz"))
    write_fixture(repo_root, files)
    bar_file = repo_root / "legacy" / "bar" / "bar.py"
    bar_file.parent.mkdir(parents=True, exist_ok=True)
    bar_file.write_text(BAR_SOURCE, encoding="utf-8")
    return bar_file


def test_ac_assemble_011_dependency_usage_cards(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bar_file = build_corpus(repo_root)
    assert not (repo_root / "legacy" / "baz").exists()

    lint_clean(repo_root)

    # Expected facts derived the same way the requirement says: via inspect.
    expected_mod = load_module(bar_file, "ac_assemble_011_expected_bar")
    expected_sig = str(inspect.signature(expected_mod.bar_get))
    expected_doc_line = inspect.getdoc(expected_mod.bar_get).splitlines()[0]
    assert expected_doc_line == BAR_DOC_FIRST_LINE

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    usage = field(bundle, "dependency_usage")

    assert "comp-bar" in usage
    bar_card = usage["comp-bar"]
    assert isinstance(bar_card, str)
    assert "bar" in bar_card
    assert "legacy/bar/" in bar_card
    assert "bar_get" in bar_card
    assert expected_sig in bar_card
    assert expected_doc_line in bar_card

    assert "comp-baz" in usage
    assert usage["comp-baz"] == ""