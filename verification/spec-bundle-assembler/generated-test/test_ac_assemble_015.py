# hotdocs-criterion: sha256:201f339d53b8f358852c277266b27cebef189dc057a4267fe43c97473bd6e54c
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen"
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


def make_component(repo_root, slug, depends_on, library_text, data_types=None):
    upper = slug.upper()
    title = slug.capitalize()
    comp_dir = repo_root / "specs" / "components" / slug
    write(
        comp_dir / "component.md",
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
        + title + " doubles a number.\n",
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    write(
        comp_dir / "requirements" / (rid + ".md"),
        "# " + rid + "\n"
        + "\n"
        + "**" + rid + "** \u2014 `" + slug + "(x)` MUST return `2 * x`.\n",
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
        + "When " + slug + "(x) is called\n"
        + "Then it returns 4\n"
        + "```\n",
    )
    write(comp_dir / "interface" / "library.md", library_text)
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    for type_name, type_text in (data_types or {}).items():
        write(comp_dir / "interface" / "data" / (type_name + ".md"), type_text)


def write_glossary(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )


def foo_library():
    return "# Library\n\n```\nfoo(x: int) -> int\n```\n"


def bar_library(type_name):
    return "# Library\n\n```\nbar_make(n: int) -> " + type_name + "\n```\n"


def lint_clean(repo_root):
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def bar_entry(repo_root):
    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    deps = field(bundle, "dependency_interfaces")
    assert "comp-bar" in deps
    return deps["comp-bar"]


def test_resolves_unowned_type_from_other_component_with_label(tmp_path):
    repo_root = tmp_path
    write_glossary(repo_root)
    make_component(repo_root, "foo", ["comp-bar"], foo_library())
    bar_text = bar_library("Widget")
    make_component(repo_root, "bar", [], bar_text)
    widget_marker = "Widget holds a sprocket count of zorblax magnitude."
    make_component(
        repo_root,
        "baz",
        [],
        "# Library\n\n```\nbaz(x: int) -> int\n```\n",
        data_types={"Widget": "# `Widget`\n\n" + widget_marker + "\n"},
    )
    lint_clean(repo_root)

    entry = bar_entry(repo_root)

    own = "bar_make(n: int) -> Widget"
    assert own in entry
    assert widget_marker in entry

    lines = entry.splitlines()
    label_idx = None
    for i, line in enumerate(lines):
        if "Widget" in line and "comp-baz" in line:
            label_idx = i
            break
    assert label_idx is not None, "no heading labels Widget as owned by comp-baz"

    own_idx = next(i for i, line in enumerate(lines) if own in line)
    marker_idx = next(i for i, line in enumerate(lines) if widget_marker in line)
    assert own_idx < label_idx < marker_idx


def test_unresolved_type_name_is_skipped(tmp_path):
    repo_root = tmp_path
    write_glossary(repo_root)
    make_component(repo_root, "foo", ["comp-bar"], foo_library())
    bar_text = bar_library("Gizmo")
    make_component(repo_root, "bar", [], bar_text)
    make_component(repo_root, "baz", [], "# Library\n\n```\nbaz(x: int) -> int\n```\n")
    lint_clean(repo_root)

    entry = bar_entry(repo_root)

    assert entry.strip() == bar_text.strip()
    assert entry.count("Gizmo") == bar_text.count("Gizmo")


def test_ambiguous_type_name_is_skipped(tmp_path):
    repo_root = tmp_path
    write_glossary(repo_root)
    make_component(repo_root, "foo", ["comp-bar"], foo_library())
    bar_text = bar_library("Gadget")
    make_component(repo_root, "bar", [], bar_text)
    marker_one = "Gadget variant one with quibblex flavor."
    marker_two = "Gadget variant two with frobnitz flavor."
    make_component(
        repo_root,
        "qux",
        [],
        "# Library\n\n```\nqux(x: int) -> int\n```\n",
        data_types={"Gadget": "# `Gadget`\n\n" + marker_one + "\n"},
    )
    make_component(
        repo_root,
        "zap",
        [],
        "# Library\n\n```\nzap(x: int) -> int\n```\n",
        data_types={"Gadget": "# `Gadget`\n\n" + marker_two + "\n"},
    )
    lint_clean(repo_root)

    entry = bar_entry(repo_root)

    assert entry.strip() == bar_text.strip()
    assert marker_one not in entry
    assert marker_two not in entry
    assert "comp-qux" not in entry
    assert "comp-zap" not in entry