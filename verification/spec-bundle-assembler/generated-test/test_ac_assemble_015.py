# hotdocs-criterion: sha256:d11c5440ca96da2e41046393307dac7d4cd3b38042c3e7fc0287e961ccac9b78
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


def lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def bar_library(type_name):
    return (
        "# Library\n"
        "\n"
        "```\n"
        "make_thing() -> " + type_name + "\n"
        "```\n"
        "\n"
        "Returns one `" + type_name + "`.\n"
    )


def widget_doc(marker):
    return "# `Widget`\n\n" + marker + " a widget has a `size` field.\n"


def heading_lines(text):
    return [line.strip() for line in text.splitlines() if line.lstrip().startswith("#")]


def build(repo_root, type_name, owners_of_widget):
    files = {}
    files.update(component_files("foo", depends_on="[comp-bar]"))
    bar = component_files("bar", purpose="Bar makes things.")
    bar["specs/components/bar/interface/library.md"] = bar_library(type_name)
    files.update(bar)
    for slug, marker in owners_of_widget:
        comp = component_files(slug, purpose=slug.capitalize() + " owns a type.")
        comp["specs/components/" + slug + "/interface/data/Widget.md"] = widget_doc(marker)
        files.update(comp)
    write_fixture(repo_root, files)
    lint_clean(repo_root)
    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    deps = field(bundle, "dependency_interfaces")
    assert "comp-bar" in deps
    return deps["comp-bar"]


def test_resolves_unowned_type_from_other_component(tmp_path):
    marker = "WIDGETMARKERBAZ"
    dep = build(tmp_path, "Widget", [("baz", marker)])

    # comp-bar's own interface content is present.
    assert "make_thing() -> Widget" in dep
    assert "Returns one `Widget`." in dep

    # Widget's own documented content is appended.
    assert marker + " a widget has a `size` field." in dep

    # Clearly labeled as owned by comp-baz, under a heading naming the type.
    marker_pos = dep.index(marker)
    before = dep[:marker_pos]
    labeled = [
        line for line in before.splitlines()
        if line.lstrip().startswith("#") and "Widget" in line and "comp-baz" in line
    ]
    assert labeled, dep
    # Bar's own content comes before the appended type section.
    assert dep.index("make_thing() -> Widget") < marker_pos


def test_unresolved_type_is_skipped(tmp_path):
    dep = build(tmp_path, "Gadget", [])
    own = bar_library("Gadget")

    assert own.strip() in dep
    assert heading_lines(dep) == heading_lines(own)
    assert dep.count("Gadget") == own.count("Gadget")
    assert "owned by" not in dep


def test_ambiguous_type_is_skipped(tmp_path):
    marker_baz = "WIDGETMARKERBAZ"
    marker_qux = "WIDGETMARKERQUX"
    dep = build(tmp_path, "Widget", [("baz", marker_baz), ("qux", marker_qux)])
    own = bar_library("Widget")

    assert own.strip() in dep
    assert marker_baz not in dep
    assert marker_qux not in dep
    assert "comp-baz" not in dep
    assert "comp-qux" not in dep
    assert heading_lines(dep) == heading_lines(own)
    assert dep.count("Widget") == own.count("Widget")