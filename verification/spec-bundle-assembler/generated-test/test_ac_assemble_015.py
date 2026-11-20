# hotdocs-criterion: sha256:538c4f381b78f67d797ba93f16b290607407d9f604939780edabbb294eba0ce1
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def write_component(repo_root, slug, depends_on, library_text, data_files=None):
    title = slug.capitalize()
    upper = slug.upper()
    root = repo_root / "specs" / "components" / slug
    component_md = (
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
        + title + " does one small thing.\n"
    )
    write(root / "component.md", component_md)
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    write(
        root / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** — `" + slug + "(x)` MUST return `2 * x`.\n",
    )
    write(
        root / "acceptance" / (acid + ".md"),
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
    write(root / "interface" / "library.md", library_text)
    for name, text in (data_files or {}).items():
        write(root / "interface" / "data" / (name + ".md"), text)
    write(root / "constraints.md", "# Constraints\n\nNone.\n")


def foo_library():
    return "# Library\n\n```\nfoo(x: int) -> int\n```\n"


def bar_library(type_name):
    return (
        "# Library\n"
        + "\n"
        + "```\n"
        + "bar(w: " + type_name + ") -> int\n"
        + "```\n"
        + "\n"
        + "Returns the size of the given " + type_name + ".\n"
    )


def base_corpus(repo_root, type_name):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    write_component(repo_root, "foo", ["comp-bar"], foo_library())
    lib = bar_library(type_name)
    write_component(repo_root, "bar", [], lib)
    return lib


def heading_lines(text):
    return [line.strip() for line in text.splitlines() if line.lstrip().startswith("#")]


def bar_entry(repo_root):
    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    deps = field(bundle, "dependency_interfaces")
    assert "comp-bar" in deps
    return deps["comp-bar"]


def test_resolved_type_is_appended_labeled_with_real_owner(tmp_path):
    repo_root = tmp_path
    lib = base_corpus(repo_root, "Widget")
    widget_text = "# `Widget`\n\nWidgetmarkerbody describes one widget record with a size.\n"
    write_component(
        repo_root, "baz", [], "# Library\n\n```\nbaz(x: int) -> int\n```\n",
        data_files={"Widget": widget_text},
    )
    lint_clean(repo_root)

    entry = bar_entry(repo_root)

    own = lib.strip()
    assert own in entry
    assert "Widgetmarkerbody" in entry

    labeled = [
        i for i, line in enumerate(entry.splitlines())
        if line.lstrip().startswith("#") and "Widget" in line and "comp-baz" in line
    ]
    assert labeled, "no heading naming Widget and its owner comp-baz"

    lines = entry.splitlines()
    heading_pos = entry.index(lines[labeled[0]])
    assert heading_pos > entry.index(own)
    assert entry.index("Widgetmarkerbody") > heading_pos


def test_unresolved_type_adds_no_section(tmp_path):
    repo_root = tmp_path
    lib = base_corpus(repo_root, "Gizmo")
    lint_clean(repo_root)

    entry = bar_entry(repo_root)

    own = lib.strip()
    assert own in entry
    assert entry.count("Gizmo") == own.count("Gizmo")
    assert heading_lines(entry) == heading_lines(own)


def test_ambiguous_type_adds_no_section(tmp_path):
    repo_root = tmp_path
    lib = base_corpus(repo_root, "Gadget")
    write_component(
        repo_root, "baz", [], "# Library\n\n```\nbaz(x: int) -> int\n```\n",
        data_files={"Gadget": "# `Gadget`\n\nBazgadgetmarker one version of a gadget.\n"},
    )
    write_component(
        repo_root, "qux", [], "# Library\n\n```\nqux(x: int) -> int\n```\n",
        data_files={"Gadget": "# `Gadget`\n\nQuxgadgetmarker another version of a gadget.\n"},
    )
    lint_clean(repo_root)

    entry = bar_entry(repo_root)

    own = lib.strip()
    assert own in entry
    assert "Bazgadgetmarker" not in entry
    assert "Quxgadgetmarker" not in entry
    assert "comp-baz" not in entry
    assert "comp-qux" not in entry
    assert entry.count("Gadget") == own.count("Gadget")
    assert heading_lines(entry) == heading_lines(own)