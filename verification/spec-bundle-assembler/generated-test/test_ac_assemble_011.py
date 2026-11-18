# hotdocs-criterion: sha256:f34fde1494ba0278563326b95ecda1d35227fff8ff049ebc3c9f3ea3742b1e3c
import importlib.util
import inspect
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


def _load_spec_linter():
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, title, depends_on, purpose):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n"
    )


def _write_component(repo_root, slug, upper, title, depends_on, purpose,
                     requirement, gherkin, signature):
    comp_dir = repo_root / "specs" / "components" / slug
    _write(comp_dir / "component.md",
           _component_md(slug, title, depends_on, purpose))
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    _write(comp_dir / "requirements" / (rid + ".md"),
           "# " + rid + "\n\n**" + rid + "** — " + requirement + "\n")
    _write(
        comp_dir / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + gherkin
        + "```\n",
    )
    _write(comp_dir / "interface" / "library.md",
           "# Library\n\n```\n" + signature + "\n```\n")
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")


BAR_SOURCE = (
    "def bar_get(key: str) -> str:\n"
    + "    " + repr("Return the stored value for key.\n\n    More detail here.\n    ") + "\n"
    + "    return 'v:' + key\n"
)


def _build_corpus(repo_root):
    _write(repo_root / "specs" / "glossary.md",
           "# Glossary\n\n- **Foo** — a test term.\n")
    _write_component(
        repo_root, "foo", "FOO", "Foo", ["comp-bar", "comp-baz"],
        "Foo doubles a number.",
        "`foo(x)` MUST return `2 * x`.",
        "Given x = 2\nWhen foo(x) is called\nThen it returns 4\n",
        "foo(x: int) -> int",
    )
    _write_component(
        repo_root, "bar", "BAR", "Bar", [],
        "Bar looks up a value by key.",
        "`bar_get(key)` MUST return the value stored for `key`.",
        "Given key = \"a\"\nWhen bar_get(key) is called\nThen it returns the stored value\n",
        "bar_get(key: str) -> str",
    )
    _write_component(
        repo_root, "baz", "BAZ", "Baz", [],
        "Baz triples a number.",
        "`baz(x)` MUST return `3 * x`.",
        "Given x = 2\nWhen baz(x) is called\nThen it returns 6\n",
        "baz(x: int) -> int",
    )
    # comp-bar's real code lives under its sealed source_path.
    _write(repo_root / "legacy" / "bar" / "bar.py", BAR_SOURCE)
    # comp-baz has no real code at all: nothing under legacy/baz/.


def test_ac_assemble_011_dependency_usage_card(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    assert not (repo_root / "legacy" / "baz").exists()
    assert not (repo_root / "gen").exists()

    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    # Independently compute the expected introspected facts.
    bar_mod = load_module(repo_root / "legacy" / "bar" / "bar.py",
                          "ac_assemble_011_bar_expected")
    expected_sig = str(inspect.signature(bar_mod.bar_get))
    expected_doc_first = inspect.getdoc(bar_mod.bar_get).splitlines()[0]
    assert expected_sig == "(key: str) -> str"
    assert expected_doc_first == "Return the stored value for key."

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    usage = field(bundle, "dependency_usage")
    assert "comp-bar" in usage
    bar_card = usage["comp-bar"]
    assert isinstance(bar_card, str)
    assert "bar" in bar_card
    assert "legacy/bar/" in bar_card
    assert "bar_get" in bar_card
    assert expected_sig in bar_card
    assert expected_doc_first in bar_card
    # Only the docstring's first line is carried, never source text.
    assert "More detail here." not in bar_card
    assert "return 'v:' + key" not in bar_card

    assert "comp-baz" in usage
    assert usage["comp-baz"] == ""