# hotdocs-criterion: sha256:369e95e16957bb90b4450a22e9030254eb7ffd3d55f4a358b9620d3234acc69a
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


BAR_INTERFACE_MARKER = "bar_iface_marker_kappa"
BAR_PURPOSE_MARKER = "purposemarkerdelta"
BAR_REQUIREMENT_MARKER = "reqmarkerzeta"
BAR_CONSTRAINT_MARKER = "constraintmarkeromega"
BAR_TITLE = "Bartitlemarkersigma"


def build_component(
    repo_root, slug, comp_id, title, depends_on, purpose,
    req_id, req_text, ac_id, given_when_then, iface_sig, constraints_text,
):
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
        "depends_on: " + depends_on + "\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose + "\n",
    )
    write(
        root / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n"
        "\n"
        "**" + req_id + "** \u2014 " + req_text + "\n",
    )
    write(
        root / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + given_when_then +
        "```\n",
    )
    write(
        root / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        + iface_sig + "\n"
        "```\n",
    )
    write(
        root / "constraints.md",
        "# Constraints\n"
        "\n"
        + constraints_text + "\n",
    )


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** \u2014 a test term.\n",
    )
    build_component(
        repo_root,
        "bar",
        "comp-bar",
        BAR_TITLE,
        "[]",
        "Bar triples a number, " + BAR_PURPOSE_MARKER + ".",
        "R-BAR-001",
        "`bar(x)` MUST return `3 * x` for " + BAR_REQUIREMENT_MARKER + ".",
        "AC-BAR-001",
        "Given x = 2\nWhen bar(x) is called\nThen it returns 6\n",
        BAR_INTERFACE_MARKER + "(x: int) -> int",
        "Bar never caches, " + BAR_CONSTRAINT_MARKER + ".",
    )
    build_component(
        repo_root,
        "foo",
        "comp-foo",
        "Foo",
        "[comp-bar]",
        "Foo doubles a number.",
        "R-FOO-001",
        "`foo(x)` MUST return `2 * x`.",
        "AC-FOO-001",
        "Given x = 2\nWhen foo(x) is called\nThen it returns 4\n",
        "foo(x: int) -> int",
        "None.",
    )


def test_dependency_interfaces_contain_only_interface_content(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    dep_ifaces = field(bundle, "dependency_interfaces")
    assert "comp-bar" in dep_ifaces
    bar_text = dep_ifaces["comp-bar"]
    assert isinstance(bar_text, str)

    # Only the dependency's interface/ content is present.
    assert BAR_INTERFACE_MARKER in bar_text

    # Never its component.md (frontmatter, title, Purpose).
    assert BAR_TITLE not in bar_text
    assert BAR_PURPOSE_MARKER not in bar_text
    assert "legacy/bar" not in bar_text
    assert "sealed: true" not in bar_text
    assert "## Purpose" not in bar_text

    # Never its requirements/.
    assert BAR_REQUIREMENT_MARKER not in bar_text
    assert "R-BAR-001" not in bar_text

    # Never its constraints.md.
    assert BAR_CONSTRAINT_MARKER not in bar_text
    assert "# Constraints" not in bar_text

    # Nothing from the dependency leaks into any other dependency entry.
    for key, value in dep_ifaces.items():
        assert BAR_REQUIREMENT_MARKER not in value
        assert BAR_CONSTRAINT_MARKER not in value