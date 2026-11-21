# hotdocs-criterion: sha256:7da98b09f35d1498ed245d09b3aedf5ded89bd832fb3ed4136778ecb185a577e
import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
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


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"


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


def requirement_md(rid, sentence):
    return "# " + rid + "\n\n**" + rid + "** \u2014 " + sentence + "\n"


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


def library_md(signature):
    return "# Library\n\n```\n" + signature + "\n```\n"


CONSTRAINTS = "# Constraints\n\nNone.\n"

FOO_COMPONENT = component_md("comp-foo", "Foo", "legacy/foo/", "[]", "Foo doubles a number.")
FOO_REQ = requirement_md("R-FOO-001", "`foo(x)` MUST return `2 * x`.")
FOO_AC = acceptance_md("AC-FOO-001", "R-FOO-001", "x = 2", "foo(x) is called", "it returns 4")
FOO_LIB = library_md("foo(x: int) -> int")

BAR_COMPONENT = component_md("comp-bar", "Bar", "legacy/bar/", "[comp-foo]", "Bar triples a number.")
BAR_REQ = requirement_md("R-BAR-001", "`bar(x)` MUST return `3 * x`.")
BAR_AC = acceptance_md("AC-BAR-001", "R-BAR-001", "x = 2", "bar(x) is called", "it returns 6")
BAR_LIB = library_md("bar(x: int) -> int")


def build_foo(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    c = repo_root / "specs" / "components" / "foo"
    write(c / "component.md", FOO_COMPONENT)
    write(c / "requirements" / "R-FOO-001.md", FOO_REQ)
    write(c / "acceptance" / "AC-FOO-001.md", FOO_AC)
    write(c / "interface" / "library.md", FOO_LIB)
    write(c / "constraints.md", CONSTRAINTS)


def build_bar(repo_root):
    c = repo_root / "specs" / "components" / "bar"
    write(c / "component.md", BAR_COMPONENT)
    write(c / "requirements" / "R-BAR-001.md", BAR_REQ)
    write(c / "acceptance" / "AC-BAR-001.md", BAR_AC)
    write(c / "interface" / "library.md", BAR_LIB)
    write(c / "constraints.md", CONSTRAINTS)


def assert_lint_clean(repo_root):
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def body_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def test_dependency_interfaces_holds_only_dependency_interface(tmp_path):
    repo_root = tmp_path / "repo"
    build_foo(repo_root)
    build_bar(repo_root)
    assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-bar", "AC-BAR-001", repo_root)
    deps = field(bundle, "dependency_interfaces")
    assert deps is not None
    assert isinstance(deps, Mapping)
    assert "comp-foo" in deps
    value = deps["comp-foo"]
    assert isinstance(value, str)

    # Contains the text of each of foo's interface/ files.
    assert FOO_LIB.strip() in value
    for line in body_lines(FOO_LIB):
        assert line in value

    # Contains no line unique to foo's component.md, requirements/ or constraints.md.
    interface_lines = set(body_lines(FOO_LIB))
    for source in (FOO_COMPONENT, FOO_REQ, CONSTRAINTS):
        for line in body_lines(source):
            if line in interface_lines:
                continue
            if line == "---":
                continue
            assert line not in value.splitlines() and line not in {
                l.strip() for l in value.splitlines()
            }, "dependency_interfaces leaked line: " + repr(line)

    # Distinctive content of the non-interface docs never appears at all.
    assert "Foo doubles a number." not in value
    assert "MUST return `2 * x`" not in value
    assert "# Constraints" not in value
    assert "source_path: legacy/foo/" not in value


def test_no_depends_on_gives_empty_mapping(tmp_path):
    repo_root = tmp_path / "repo"
    build_foo(repo_root)
    assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    deps = field(bundle, "dependency_interfaces")
    assert deps is not None
    assert isinstance(deps, Mapping)
    assert len(deps) == 0
    assert dict(deps) == {}