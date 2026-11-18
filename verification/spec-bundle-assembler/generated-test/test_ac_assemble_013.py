# hotdocs-criterion: sha256:40eb1374a1b846c40d82f38104db119277de67955e50d7696c77ce935af54287
import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n" + "\n" + "- **Foo** — a test term.\n"


def component_md(slug, title, depends_on, purpose):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
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
    return "# " + rid + "\n" + "\n" + "**" + rid + "** — " + text + "\n"


def acceptance_md(acid, rid, given, when, then):
    return (
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + given + "\n"
        + when + "\n"
        + then + "\n"
        + "```\n"
    )


def library_md(signature):
    return "# Library\n" + "\n" + "```\n" + signature + "\n" + "```\n"


CONSTRAINTS = "# Constraints\n" + "\n" + "None.\n"


def build_foo(repo_root):
    root = repo_root / "specs" / "components" / "foo"
    files = {
        "component.md": component_md("foo", "Foo", "[]", "Foo doubles a number."),
        "requirements/R-FOO-001.md": requirement_md(
            "R-FOO-001", "`foo(x)` MUST return `2 * x`."
        ),
        "acceptance/AC-FOO-001.md": acceptance_md(
            "AC-FOO-001",
            "R-FOO-001",
            "Given x = 2",
            "When foo(x) is called",
            "Then it returns 4",
        ),
        "interface/library.md": library_md("foo(x: int) -> int"),
        "constraints.md": CONSTRAINTS,
    }
    for rel, text in files.items():
        write(root / rel, text)
    write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n    return 2 * x\n",
    )
    return root


def build_bar(repo_root):
    root = repo_root / "specs" / "components" / "bar"
    files = {
        "component.md": component_md(
            "bar", "Bar", "[comp-foo]", "Bar quadruples a number."
        ),
        "requirements/R-BAR-001.md": requirement_md(
            "R-BAR-001", "`bar(x)` MUST return `4 * x`."
        ),
        "acceptance/AC-BAR-001.md": acceptance_md(
            "AC-BAR-001",
            "R-BAR-001",
            "Given x = 3",
            "When bar(x) is called",
            "Then it returns 12",
        ),
        "interface/library.md": library_md("bar(x: int) -> int"),
        "constraints.md": CONSTRAINTS,
    }
    for rel, text in files.items():
        write(root / rel, text)
    write(
        repo_root / "legacy" / "bar" / "bar.py",
        "def bar(x):\n    return 4 * x\n",
    )
    return root


def assert_lint_clean(repo_root):
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def test_dependency_interfaces_holds_dependency_interface_only(tmp_path):
    repo_root = tmp_path
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    foo_root = build_foo(repo_root)
    build_bar(repo_root)
    assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-bar", "AC-BAR-001", repo_root
    )
    deps = field(bundle, "dependency_interfaces")
    assert deps is not None
    assert isinstance(deps, Mapping)
    assert "comp-foo" in deps
    value = deps["comp-foo"]
    assert isinstance(value, str)

    interface_files = sorted((foo_root / "interface").rglob("*.md"))
    assert interface_files
    interface_lines = set()
    for f in interface_files:
        text = f.read_text(encoding="utf-8")
        assert text.strip() in value
        for line in text.splitlines():
            if line.strip():
                interface_lines.add(line.strip())

    other_files = [foo_root / "component.md", foo_root / "constraints.md"]
    other_files += sorted((foo_root / "requirements").rglob("*.md"))
    unique_lines = set()
    for f in other_files:
        for line in f.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and s not in interface_lines:
                unique_lines.add(s)
    assert "Foo doubles a number." in unique_lines

    value_lines = {line.strip() for line in value.splitlines()}
    leaked = sorted(unique_lines & value_lines)
    assert leaked == []
    assert "Foo doubles a number." not in value
    assert "MUST return `2 * x`" not in value


def test_dependency_interfaces_empty_mapping_without_depends_on(tmp_path):
    repo_root = tmp_path
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    build_foo(repo_root)
    assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )
    deps = field(bundle, "dependency_interfaces")
    assert deps is not None
    assert isinstance(deps, Mapping)
    assert len(deps) == 0
    assert dict(deps) == {}