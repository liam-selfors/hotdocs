import spec_bundle_assembler

import importlib.util
import sys
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


IFACE_MARKER = "zqinterfacemarker"
PURPOSE_MARKER = "zqpurposemarker"
REQ_MARKER = "zqrequirementmarker"
CONSTRAINT_MARKER = "zqconstraintmarker"


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )

    # Dependency: comp-foo
    foo = repo_root / "specs" / "components" / "foo"
    _write(
        foo / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number " + PURPOSE_MARKER + ".\n",
    )
    _write(
        foo / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x` (" + REQ_MARKER + ").\n",
    )
    _write(
        foo / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        foo / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "Returns double its input " + IFACE_MARKER + ".\n",
    )
    _write(
        foo / "constraints.md",
        "# Constraints\n\nNone (" + CONSTRAINT_MARKER + ").\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")

    # Dependent: comp-bar
    bar = repo_root / "specs" / "components" / "bar"
    _write(
        bar / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/bar/\n"
        "depends_on: [comp-foo]\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Bar quadruples a number.\n",
    )
    _write(
        bar / "requirements" / "R-BAR-001.md",
        "# R-BAR-001\n"
        "\n"
        "**R-BAR-001** — `bar(x)` MUST return `4 * x`.\n",
    )
    _write(
        bar / "acceptance" / "AC-BAR-001.md",
        "# AC-BAR-001\n"
        "\n"
        "Covers: R-BAR-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When bar(x) is called\n"
        "Then it returns 8\n"
        "```\n",
    )
    _write(
        bar / "interface" / "library.md",
        "# Library\n\n```\nbar(x: int) -> int\n```\n",
    )
    _write(bar / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "legacy" / "bar" / "bar.py", "def bar(x):\n    return 4 * x\n")


def test_ac_assemble_002_dependency_interfaces_only_interface(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root)

    dep_ifaces = field(bundle, "dependency_interfaces")
    assert set(dep_ifaces.keys()) == {"comp-foo"}

    foo_iface = dep_ifaces["comp-foo"]
    assert isinstance(foo_iface, str)

    # Contains the dependency's interface/ content.
    assert IFACE_MARKER in foo_iface
    assert "foo(x: int) -> int" in foo_iface

    # Never the dependency's component.md (frontmatter, heading, Purpose).
    assert PURPOSE_MARKER not in foo_iface
    assert "Foo doubles a number" not in foo_iface
    assert "id: comp-foo" not in foo_iface
    assert "source_path" not in foo_iface
    assert "## Purpose" not in foo_iface

    # Never the dependency's requirements/.
    assert REQ_MARKER not in foo_iface
    assert "R-FOO-001" not in foo_iface
    assert "MUST return `2 * x`" not in foo_iface

    # Never the dependency's constraints.md.
    assert CONSTRAINT_MARKER not in foo_iface
    assert "# Constraints" not in foo_iface

    # And none of those internals leak into any dependency_interfaces value.
    for value in dep_ifaces.values():
        for marker in (PURPOSE_MARKER, REQ_MARKER, CONSTRAINT_MARKER):
            assert marker not in value