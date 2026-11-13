import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path

import spec_bundle_assembler


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
    "Foo doubles a number.\n"
)

FOO_REQUIREMENT = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

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

FOO_INTERFACE = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

FOO_CONSTRAINTS = "# Constraints\n\nNone.\n"

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
    "Bar quadruples a number.\n"
)

BAR_REQUIREMENT = "# R-BAR-001\n\n**R-BAR-001** — `bar(x)` MUST return `4 * x`.\n"

BAR_ACCEPTANCE = (
    "# AC-BAR-001\n"
    "\n"
    "Covers: R-BAR-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When bar(x) is called\n"
    "Then it returns 8\n"
    "```\n"
)

BAR_INTERFACE = "# Library\n\n```\nbar(x: int) -> int\n```\n"

BAR_CONSTRAINTS = "# Constraints\n\nNone.\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)

    foo = repo_root / "specs" / "components" / "foo"
    _write(foo / "component.md", FOO_COMPONENT)
    _write(foo / "requirements" / "R-FOO-001.md", FOO_REQUIREMENT)
    _write(foo / "acceptance" / "AC-FOO-001.md", FOO_ACCEPTANCE)
    _write(foo / "interface" / "library.md", FOO_INTERFACE)
    _write(foo / "constraints.md", FOO_CONSTRAINTS)

    bar = repo_root / "specs" / "components" / "bar"
    _write(bar / "component.md", BAR_COMPONENT)
    _write(bar / "requirements" / "R-BAR-001.md", BAR_REQUIREMENT)
    _write(bar / "acceptance" / "AC-BAR-001.md", BAR_ACCEPTANCE)
    _write(bar / "interface" / "library.md", BAR_INTERFACE)
    _write(bar / "constraints.md", BAR_CONSTRAINTS)


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


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = (
        report.get("hard_failures")
        if isinstance(report, dict)
        else getattr(report, "hard_failures", None)
    )
    findings = (
        report.get("findings")
        if isinstance(report, dict)
        else getattr(report, "findings", None)
    )
    assert hard == 0, f"fixture is not lint-clean: {findings!r}"


def _has_field(obj, name: str) -> bool:
    if isinstance(obj, dict):
        return name in obj
    return hasattr(obj, name)


def _field(obj, name: str):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _nonblank_lines(text: str) -> set:
    return {line.strip() for line in text.splitlines() if line.strip()}


def test_dependency_interfaces_holds_dependency_interface_only(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-bar", "AC-BAR-001", repo_root
    )

    assert _has_field(bundle, "dependency_interfaces")
    deps = _field(bundle, "dependency_interfaces")
    assert deps is not None
    assert isinstance(deps, Mapping)
    assert "comp-foo" in deps, f"dependency_interfaces keys: {list(deps)!r}"

    value = deps["comp-foo"]
    assert isinstance(value, str)

    # Contains the text of each of comp-foo's interface/ files.
    for line in _nonblank_lines(FOO_INTERFACE):
        assert line in value, f"missing interface line {line!r} in {value!r}"
    assert "foo(x: int) -> int" in value

    # Contains no line unique to comp-foo's component.md, requirements/,
    # or constraints.md.
    interface_lines = _nonblank_lines(FOO_INTERFACE)
    other_lines = (
        _nonblank_lines(FOO_COMPONENT)
        | _nonblank_lines(FOO_REQUIREMENT)
        | _nonblank_lines(FOO_CONSTRAINTS)
    )
    unique_lines = other_lines - interface_lines
    assert unique_lines  # sanity: there is something to check
    value_lines = _nonblank_lines(value)
    leaked = sorted(line for line in unique_lines if line in value_lines)
    assert not leaked, f"non-interface lines leaked into dependency_interfaces: {leaked!r}"

    # Distinctive content checks, by substring as well.
    assert "Foo doubles a number." not in value
    assert "MUST return `2 * x`" not in value
    assert "id: comp-foo" not in value


def test_dependency_interfaces_empty_mapping_without_depends_on(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )

    assert _has_field(bundle, "dependency_interfaces"), (
        "dependency_interfaces must never be absent"
    )
    deps = _field(bundle, "dependency_interfaces")
    assert deps is not None, "dependency_interfaces must never be null"
    assert isinstance(deps, Mapping)
    assert len(deps) == 0
    assert dict(deps) == {}