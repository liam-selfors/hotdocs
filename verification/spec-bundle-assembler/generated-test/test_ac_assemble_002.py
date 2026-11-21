# hotdocs-criterion: sha256:a7f7b5beab8f5c7542f09af64589e1a89f5d89c8d9a81b0a0c1dc09644726d7e
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


def write_component(repo_root, slug, comp_id, title, purpose, depends_on,
                    req_id, req_line, ac_id, iface_sig, constraints_body):
    base = repo_root / "specs" / "components" / slug
    write(
        base / "component.md",
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
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n"
        "\n"
        + req_line + "\n",
    )
    write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When " + slug + "(x) is called\n"
        "Then it returns a number\n"
        "```\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        + iface_sig + "\n"
        "```\n",
    )
    write(
        base / "constraints.md",
        "# Constraints\n"
        "\n"
        + constraints_body + "\n",
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    write_component(
        repo_root, "foo", "comp-foo", "Foo",
        "Foo doubles a number.",
        "[]",
        "R-FOO-001",
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "AC-FOO-001",
        "foo(x: int) -> int",
        "None.",
    )
    write_component(
        repo_root, "bar", "comp-bar", "Bar",
        "Bar adds one to a doubled number.",
        "[comp-foo]",
        "R-BAR-001",
        "**R-BAR-001** — `bar(x)` MUST return `foo(x) + 1`.",
        "AC-BAR-001",
        "bar(x: int) -> int",
        "None.",
    )


def test_dependency_interfaces_contain_only_interface_content(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root)

    dep_ifaces = field(bundle, "dependency_interfaces")
    assert set(dep_ifaces.keys()) == {"comp-foo"}

    foo_iface = dep_ifaces["comp-foo"]
    assert isinstance(foo_iface, str)

    # Contains the dependency's interface/ content.
    assert "# Library" in foo_iface
    assert "foo(x: int) -> int" in foo_iface

    # Never the dependency's component.md (frontmatter or body).
    assert "comp-foo" not in foo_iface
    assert "sealed: true" not in foo_iface
    assert "source_path" not in foo_iface
    assert "owners:" not in foo_iface
    assert "# Foo" not in foo_iface
    assert "## Purpose" not in foo_iface
    assert "Foo doubles a number" not in foo_iface

    # Never the dependency's requirements/.
    assert "R-FOO-001" not in foo_iface
    assert "MUST return" not in foo_iface
    assert "2 * x" not in foo_iface

    # Never the dependency's constraints.md.
    assert "# Constraints" not in foo_iface
    assert "None." not in foo_iface

    # Never the dependency's acceptance/ either.
    assert "AC-FOO-001" not in foo_iface
    assert "Covers:" not in foo_iface