# hotdocs-criterion: sha256:fb222a02a848f7cad7ea880dc516504253ae5e22f9319c81fd4ec123b12a8957
import importlib.util
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


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def make_component(repo_root, slug, prefix, title, depends_on, library_text, data=None):
    comp_dir = repo_root / "specs" / "components" / slug
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
        + title + " doubles a number.\n"
    )
    write(comp_dir / "component.md", component_md)
    rid = "R-" + prefix + "-001"
    acid = "AC-" + prefix + "-001"
    fname = slug.replace("-", "_")
    write(
        comp_dir / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** — `" + fname + "(x)` MUST return `2 * x`.\n",
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
        + "When " + fname + "(x) is called\n"
        + "Then it returns 4\n"
        + "```\n",
    )
    write(comp_dir / "interface" / "library.md", library_text)
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    for name, text in (data or {}).items():
        write(comp_dir / "interface" / "data" / (name + ".md"), text)


FOO_LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"


def bar_library(type_name):
    return "# Library\n\n```\nbar_make(n: int) -> " + type_name + "\n```\n"


BAZ_WIDGET_MARKER = "zqxbazwidgetbodymarker"
QUX_WIDGET_MARKER = "zqxquxwidgetbodymarker"


def baz_widget_md():
    return "# `Widget`\n\nA Widget record. " + BAZ_WIDGET_MARKER + " holds its documented content.\n"


def qux_widget_md():
    return "# `Widget`\n\nAnother Widget record. " + QUX_WIDGET_MARKER + " holds its documented content.\n"


def build_corpus(repo_root, bar_type, owners):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    make_component(repo_root, "foo", "FOO", "Foo", ["comp-bar"], FOO_LIBRARY)
    make_component(repo_root, "bar", "BAR", "Bar", [], bar_library(bar_type))
    if "baz" in owners:
        make_component(
            repo_root, "baz", "BAZ", "Baz", [],
            "# Library\n\n```\nbaz(x: int) -> int\n```\n",
            data={"Widget": baz_widget_md()},
        )
    if "qux" in owners:
        make_component(
            repo_root, "qux", "QUX", "Qux", [],
            "# Library\n\n```\nqux(x: int) -> int\n```\n",
            data={"Widget": qux_widget_md()},
        )
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def bar_entry(repo_root):
    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    deps = field(bundle, "dependency_interfaces")
    assert "comp-bar" in deps
    entry = deps["comp-bar"]
    assert isinstance(entry, str)
    return entry


def test_resolves_foreign_type_labeled_with_real_owner(tmp_path):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, "Widget", ["baz"])
    entry = bar_entry(repo_root)

    own = bar_library("Widget").strip()
    assert own in entry
    assert "bar_make(n: int) -> Widget" in entry

    # Widget's own documented content is appended
    assert BAZ_WIDGET_MARKER in entry
    assert baz_widget_md().strip().splitlines()[-1].strip() in entry

    # clearly labeled as owned by comp-baz: a heading line naming both
    marker_pos = entry.index(BAZ_WIDGET_MARKER)
    before = entry[:marker_pos]
    label_lines = [
        line for line in before.splitlines()
        if line.lstrip().startswith("#") and "Widget" in line and "comp-baz" in line
    ]
    assert label_lines, entry
    # the label comes after comp-bar's own content, not merged in as bar's
    assert entry.index(own) < entry.index(label_lines[-1])


def test_unresolved_name_gets_no_fabricated_section(tmp_path):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, "Gadget", [])
    entry = bar_entry(repo_root)

    own = bar_library("Gadget").strip()
    assert own in entry
    remainder = entry.replace(own, "", 1)
    assert "Gadget" not in remainder
    assert remainder.strip() == ""


def test_ambiguous_name_gets_no_section(tmp_path):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, "Widget", ["baz", "qux"])
    entry = bar_entry(repo_root)

    own = bar_library("Widget").strip()
    assert own in entry
    assert BAZ_WIDGET_MARKER not in entry
    assert QUX_WIDGET_MARKER not in entry
    assert "comp-baz" not in entry
    assert "comp-qux" not in entry
    remainder = entry.replace(own, "", 1)
    assert "Widget" not in remainder
    assert remainder.strip() == ""

    # identical to the entry for the same comp-bar content with no owner at all
    control_root = tmp_path / "control"
    build_corpus(control_root, "Widget", [])
    assert bar_entry(control_root) == entry