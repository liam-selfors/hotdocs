# hotdocs-criterion: sha256:ba0dd245fc3466e4c5d0f1897952f5c55ba719edad8b7ea65ced9c5639d4a30c
import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def component_md(comp_id, title, source_path, depends_on, purpose):
    return (
        "---\n"
        + "id: " + comp_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: " + source_path + "\n"
        + "depends_on: " + depends_on + "\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n"
    )


def requirement_md(rid, text):
    return "# " + rid + "\n\n**" + rid + "** — " + text + "\n"


def acceptance_md(acid, rid, given, when, then):
    return (
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given " + given + "\n"
        + "When " + when + "\n"
        + "Then " + then + "\n"
        + "```\n"
    )


FOO_COMPONENT = component_md(
    "comp-foo", "Foo", "legacy/foo/", "[]", "Foo doubles a number."
)
FOO_REQUIREMENT = requirement_md("R-FOO-001", "`foo(x)` MUST return `2 * x`.")
FOO_ACCEPTANCE = acceptance_md(
    "AC-FOO-001", "R-FOO-001", "x = 2", "foo(x) is called", "it returns 4"
)
FOO_LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"
FOO_CONSTRAINTS = "# Constraints\n\nNone.\n"

BAR_COMPONENT = component_md(
    "comp-bar", "Bar", "legacy/bar/", "[comp-foo]", "Bar triples a number."
)
BAR_REQUIREMENT = requirement_md("R-BAR-001", "`bar(x)` MUST return `3 * x`.")
BAR_ACCEPTANCE = acceptance_md(
    "AC-BAR-001", "R-BAR-001", "x = 2", "bar(x) is called", "it returns 6"
)
BAR_LIBRARY = "# Library\n\n```\nbar(x: int) -> int\n```\n"
BAR_CONSTRAINTS = "# Constraints\n\nNone.\n"


def build_foo(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    base = repo_root / "specs" / "components" / "foo"
    write(base / "component.md", FOO_COMPONENT)
    write(base / "requirements" / "R-FOO-001.md", FOO_REQUIREMENT)
    write(base / "acceptance" / "AC-FOO-001.md", FOO_ACCEPTANCE)
    write(base / "interface" / "library.md", FOO_LIBRARY)
    write(base / "constraints.md", FOO_CONSTRAINTS)


def build_bar(repo_root):
    base = repo_root / "specs" / "components" / "bar"
    write(base / "component.md", BAR_COMPONENT)
    write(base / "requirements" / "R-BAR-001.md", BAR_REQUIREMENT)
    write(base / "acceptance" / "AC-BAR-001.md", BAR_ACCEPTANCE)
    write(base / "interface" / "library.md", BAR_LIBRARY)
    write(base / "constraints.md", BAR_CONSTRAINTS)


def test_dependency_interfaces_holds_dependency_interface_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_foo(repo_root)
    build_bar(repo_root)

    spec_linter = load_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble_criterion("comp-bar", "AC-BAR-001", repo_root)
    deps = field(bundle, "dependency_interfaces")
    assert deps is not None
    assert isinstance(deps, Mapping)
    assert "comp-foo" in deps
    value = deps["comp-foo"]
    assert isinstance(value, str)

    # Contains the text of each of the dependency's interface/ files.
    interface_files = [FOO_LIBRARY]
    for text in interface_files:
        assert text.strip() in value

    # Contains no line unique to component.md, requirements/ or constraints.md.
    interface_lines = set()
    for text in interface_files:
        for line in text.splitlines():
            if line.strip():
                interface_lines.add(line.strip())

    value_lines = set(line.strip() for line in value.splitlines() if line.strip())

    for other in (FOO_COMPONENT, FOO_REQUIREMENT, FOO_CONSTRAINTS):
        for line in other.splitlines():
            stripped = line.strip()
            if not stripped or stripped in interface_lines:
                continue
            assert stripped not in value_lines, (
                "dependency_interfaces leaked non-interface line: " + repr(stripped)
            )

    # Distinctive content must not leak even as a substring.
    assert "Foo doubles a number." not in value
    assert "MUST return `2 * x`" not in value
    assert "R-FOO-001" not in value


def test_no_depends_on_gives_empty_mapping(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_foo(repo_root)

    spec_linter = load_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    deps = field(bundle, "dependency_interfaces")
    assert deps is not None
    assert isinstance(deps, Mapping)
    assert len(deps) == 0
    assert dict(deps) == {}