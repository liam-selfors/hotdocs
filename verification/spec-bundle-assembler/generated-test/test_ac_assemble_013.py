# hotdocs-criterion: sha256:0f20aae439d84c27b9fd358dea87f4b8d03c867d129f87931ab2b4a36ac4f0be
import collections.abc
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


def assert_lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def _lines(text):
    return {line.strip() for line in text.splitlines() if line.strip()}


def test_dependency_interfaces_holds_only_dependency_interface(tmp_path):
    repo_root = tmp_path
    files = {}
    files.update(component_files("foo"))
    foo_interface = (
        "# Library\n\n```\nfoo(x: int) -> int\nfoo_dependency_marker(y: int) -> int\n```\n"
    )
    files["specs/components/foo/interface/library.md"] = foo_interface
    files.update(component_files("baz", depends_on="[comp-foo]"))
    write_fixture(repo_root, files)
    assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-baz", "AC-BAZ-001", repo_root)

    dep = field(bundle, "dependency_interfaces")
    assert dep is not None
    assert isinstance(dep, collections.abc.Mapping)
    assert "comp-foo" in dep
    value = dep["comp-foo"]
    assert isinstance(value, str)

    # Contains the text of each of foo's interface/ files.
    assert foo_interface.strip() in value

    # Contains no line unique to foo's component.md, requirements/ or constraints.md.
    interface_lines = _lines(foo_interface)
    other_text = (
        files["specs/components/foo/component.md"]
        + "\n"
        + files["specs/components/foo/requirements/R-FOO-001.md"]
        + "\n"
        + files["specs/components/foo/constraints.md"]
    )
    unique_lines = _lines(other_text) - interface_lines
    assert unique_lines  # sanity: there is something to check
    value_lines = _lines(value)
    leaked = sorted(unique_lines & value_lines)
    assert leaked == [], "non-interface lines leaked into dependency_interfaces: " + repr(leaked)


def test_dependency_interfaces_empty_mapping_without_depends_on(tmp_path):
    repo_root = tmp_path
    write_fixture(repo_root, component_files("foo"))
    assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    dep = field(bundle, "dependency_interfaces")
    assert dep is not None
    assert isinstance(dep, collections.abc.Mapping)
    assert len(dep) == 0
    assert dict(dep) == {}