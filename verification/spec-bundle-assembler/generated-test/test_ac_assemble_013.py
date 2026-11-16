import spec_bundle_assembler

import collections.abc
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


def _assert_lint_clean(repo_root):
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = (
        report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    )
    assert hard == 0, getattr(report, "findings", report)


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


FOO_COMPONENT = (
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
    "Foo doubles a number by way of the zircon-purpose-marker route.\n"
)

FOO_REQUIREMENT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `foo(x)` MUST return `2 * x` per the quartz-requirement-marker rule.\n"
)

FOO_ACCEPTANCE = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

FOO_LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

FOO_CONSTRAINTS = "# Constraints\n\nNone beyond the basalt-constraint-marker.\n"


BAR_COMPONENT = (
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
    "Bar adds one to a doubled number.\n"
)

BAR_REQUIREMENT = (
    "# R-BAR-001\n"
    "\n"
    "**R-BAR-001** — `bar(x)` MUST return `foo(x) + 1`.\n"
)

BAR_ACCEPTANCE = (
    "# AC-BAR-001\n"
    "\n"
    "Covers: R-BAR-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When bar(x) is called\n"
    "Then it returns 5\n"
    "```\n"
)

BAR_LIBRARY = "# Library\n\n```\nbar(x: int) -> int\n```\n"

BAR_CONSTRAINTS = "# Constraints\n\nNone.\n"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_foo(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", FOO_COMPONENT)
    _write(comp / "requirements" / "R-FOO-001.md", FOO_REQUIREMENT)
    _write(comp / "acceptance" / "AC-FOO-001.md", FOO_ACCEPTANCE)
    _write(comp / "interface" / "library.md", FOO_LIBRARY)
    _write(comp / "constraints.md", FOO_CONSTRAINTS)


def _write_bar(repo_root):
    comp = repo_root / "specs" / "components" / "bar"
    _write(comp / "component.md", BAR_COMPONENT)
    _write(comp / "requirements" / "R-BAR-001.md", BAR_REQUIREMENT)
    _write(comp / "acceptance" / "AC-BAR-001.md", BAR_ACCEPTANCE)
    _write(comp / "interface" / "library.md", BAR_LIBRARY)
    _write(comp / "constraints.md", BAR_CONSTRAINTS)


def _write_glossary(repo_root):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)


def _lines(text):
    return {ln.strip() for ln in text.splitlines() if ln.strip()}


def test_dependency_interfaces_holds_only_dependency_interface_text(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_glossary(repo_root)
    _write_foo(repo_root)
    _write_bar(repo_root)

    _assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-bar", "AC-BAR-001", repo_root)

    deps = field(bundle, "dependency_interfaces")
    assert deps is not None
    assert isinstance(deps, collections.abc.Mapping)
    assert "comp-foo" in deps
    value = deps["comp-foo"]
    assert isinstance(value, str)

    # Contains the text of each of the dependency's interface/ files.
    assert FOO_LIBRARY.strip() in value
    assert "foo(x: int) -> int" in value

    # Contains no line unique to its component.md, requirements/ or constraints.md.
    interface_lines = _lines(FOO_LIBRARY)
    excluded_sources = FOO_COMPONENT + "\n" + FOO_REQUIREMENT + "\n" + FOO_CONSTRAINTS
    unique_lines = _lines(excluded_sources) - interface_lines - {"---"}
    value_lines = _lines(value)
    leaked = sorted(unique_lines & value_lines)
    assert leaked == [], f"dependency_interfaces leaked non-interface lines: {leaked}"

    for marker in (
        "zircon-purpose-marker",
        "quartz-requirement-marker",
        "basalt-constraint-marker",
    ):
        assert marker not in value


def test_no_depends_on_gives_empty_mapping(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_glossary(repo_root)
    _write_foo(repo_root)

    _assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    if isinstance(bundle, dict):
        assert "dependency_interfaces" in bundle
    else:
        assert hasattr(bundle, "dependency_interfaces")
    deps = field(bundle, "dependency_interfaces")
    assert deps is not None
    assert isinstance(deps, collections.abc.Mapping)
    assert len(deps) == 0
    assert dict(deps) == {}