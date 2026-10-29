"""AC-ASSEMBLE-013 (covers R-ASSEMBLE-009).

A CriterionBundle's dependency_interfaces carries each depends_on id's
interface/ content (and nothing else of that dependency), and is an empty
mapping, never absent or null, for a component with no depends_on.
"""

from collections.abc import Mapping
from pathlib import Path
import textwrap

import pytest

import spec_bundle_assembler


_MISSING = object()

BAR_INTERFACE_MARKER = "BAR_INTERFACE_MARKER_7f3a"
BAR_COMPONENT_MARKER = "BAR_COMPONENT_MARKER_91c2"
BAR_REQUIREMENT_MARKER = "BAR_REQUIREMENT_MARKER_4d8e"
BAR_CONSTRAINTS_MARKER = "BAR_CONSTRAINTS_MARKER_b06f"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        """
        ---
        id: glossary
        title: Glossary
        status: draft
        owners: [test-owner]
        ---

        # Glossary

        - **Widget** — a synthetic test term.
        """,
    )

    # Dependency component: comp-bar (no depends_on at all).
    bar = repo_root / "specs" / "components" / "bar"
    _write(
        bar / "component.md",
        f"""
        ---
        id: comp-bar
        title: Bar
        status: draft
        owners: [test-owner]
        sealed: true
        source_path: fake/bar_src
        ---

        # Bar

        ## Purpose

        Bar provides widgets. {BAR_COMPONENT_MARKER}
        """,
    )
    _write(
        bar / "requirements" / "R-BAR-001.md",
        f"""
        # R-BAR-001

        **R-BAR-001** — MUST return a widget. {BAR_REQUIREMENT_MARKER}
        """,
    )
    _write(
        bar / "acceptance" / "AC-BAR-001.md",
        """
        # AC-BAR-001

        Covers: R-BAR-001
        Kind: generated-test

        ```gherkin
        Given a bar
        When make_widget is called
        Then a widget is returned
        ```
        """,
    )
    _write(
        bar / "interface" / "library.md",
        f"""
        # Library

        ```
        make_widget(name: str) -> dict
        ```

        Returns `{{"name": ..., "size": ...}}`. {BAR_INTERFACE_MARKER}
        """,
    )
    _write(
        bar / "constraints.md",
        f"""
        # Constraints

        - Bar MUST be fast. {BAR_CONSTRAINTS_MARKER}
        """,
    )

    # Dependent component: comp-foo depends_on comp-bar.
    foo = repo_root / "specs" / "components" / "foo"
    _write(
        foo / "component.md",
        """
        ---
        id: comp-foo
        title: Foo
        status: draft
        owners: [test-owner]
        depends_on: [comp-bar]
        sealed: true
        source_path: fake/foo_src
        ---

        # Foo

        ## Purpose

        Foo consumes widgets from bar.
        """,
    )
    _write(
        foo / "requirements" / "R-FOO-001.md",
        """
        # R-FOO-001

        **R-FOO-001** — MUST count widgets.
        """,
    )
    _write(
        foo / "acceptance" / "AC-FOO-001.md",
        """
        # AC-FOO-001

        Covers: R-FOO-001
        Kind: generated-test

        ```gherkin
        Given a foo
        When count is called
        Then the widget count is returned
        ```
        """,
    )
    _write(
        foo / "interface" / "library.md",
        """
        # Library

        ```
        count() -> int
        ```
        """,
    )
    _write(
        foo / "constraints.md",
        """
        # Constraints

        - Foo MUST be correct.
        """,
    )


def _hard_fail_findings(report):
    findings = report
    if not isinstance(report, (list, tuple)):
        findings = _get(report, "findings", None)
        if findings is None:
            findings = []
    hard = []
    for finding in findings:
        severity = str(
            _get(finding, "severity", None) or _get(finding, "level", None) or ""
        ).lower().replace("_", "-")
        if severity in ("hard-fail", "hard", "error", "fail"):
            hard.append(finding)
    return hard


@pytest.fixture
def repo_root(tmp_path):
    _build_fixture(tmp_path)
    try:
        import spec_linter
    except ImportError:
        spec_linter = None
    if spec_linter is not None:
        report = spec_linter.lint(None, tmp_path)
        assert _hard_fail_findings(report) == [], report
    return tmp_path


def test_dependency_interfaces_contains_only_dependency_interface(repo_root):
    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", "AC-FOO-001", repo_root
    )

    dep_interfaces = _get(bundle, "dependency_interfaces", _MISSING)
    assert dep_interfaces is not _MISSING
    assert dep_interfaces is not None
    assert isinstance(dep_interfaces, Mapping)
    assert set(dep_interfaces.keys()) == {"comp-bar"}

    bar_iface = dep_interfaces["comp-bar"]
    assert isinstance(bar_iface, str)
    assert BAR_INTERFACE_MARKER in bar_iface
    assert "make_widget(name: str) -> dict" in bar_iface

    # Never the dependency's component.md, requirements/, or constraints.md.
    for value in dep_interfaces.values():
        assert BAR_COMPONENT_MARKER not in value
        assert BAR_REQUIREMENT_MARKER not in value
        assert BAR_CONSTRAINTS_MARKER not in value

    # Same content, same rule, as SpecBundle.dependency_interfaces.
    spec_bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    spec_dep_interfaces = _get(spec_bundle, "dependency_interfaces")
    assert spec_dep_interfaces is not None
    assert bar_iface == spec_dep_interfaces["comp-bar"]


def test_dependency_interfaces_empty_mapping_without_depends_on(repo_root):
    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-bar", "AC-BAR-001", repo_root
    )

    dep_interfaces = _get(bundle, "dependency_interfaces", _MISSING)
    assert dep_interfaces is not _MISSING
    assert dep_interfaces is not None
    assert isinstance(dep_interfaces, Mapping)
    assert len(dep_interfaces) == 0