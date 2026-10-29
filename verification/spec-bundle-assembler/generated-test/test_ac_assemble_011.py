"""AC-ASSEMBLE-011 — dependency_usage carries a mechanically-derived usage
card for a dependency with real gen/ code, and "" for one without any."""

import re
import sys
import textwrap
from pathlib import Path

import pytest

import spec_bundle_assembler


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def _make_component(repo_root: Path, slug: str, prefix: str, frontmatter_extra: str, purpose: str) -> None:
    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        f"""
        ---
        id: comp-{slug}
        title: {slug.capitalize()} component
        status: draft
        owners: [tester]
        {frontmatter_extra}
        ---

        # {slug.capitalize()} component

        ## Purpose

        {purpose}
        """,
    )
    _write(
        comp_dir / "requirements" / f"R-{prefix}-001.md",
        f"""
        # R-{prefix}-001

        **R-{prefix}-001** — The {slug} component MUST do its one job.
        """,
    )
    _write(
        comp_dir / "acceptance" / f"AC-{prefix}-001.md",
        f"""
        # AC-{prefix}-001

        Covers: R-{prefix}-001
        Kind: generated-test

        ```gherkin
        Given the {slug} component
        When it is used
        Then it does its one job
        ```
        """,
    )
    _write(
        comp_dir / "interface" / "library.md",
        f"""
        # Library

        The {slug} component's public library contract.
        """,
    )
    _write(
        comp_dir / "constraints.md",
        f"""
        # Constraints

        None beyond the defaults for {slug}.
        """,
    )


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    _write(
        root / "specs" / "glossary.md",
        """
        ---
        id: glossary
        title: Glossary
        status: draft
        owners: [tester]
        ---

        # Glossary

        - **Widget** — a synthetic test term.
        """,
    )

    _make_component(
        root,
        "foo",
        "FOO",
        "sealed: true\nsource_path: legacy/foo\ndepends_on: [comp-bar, comp-baz]",
        "Foo exists to exercise dependency usage cards.",
    )
    _make_component(
        root,
        "bar",
        "BAR",
        "sealed: true\nsource_path: gen/bar",
        "Bar provides keyed lookups.",
    )
    _make_component(
        root,
        "baz",
        "BAZ",
        "sealed: true\nsource_path: legacy/baz",
        "Baz is spec-only so far.",
    )

    # comp-bar's real code under gen/bar/ (flat-module shape).
    _write(
        root / "gen" / "bar" / "bar.py",
        '''
        """Bar: keyed lookups."""


        def bar_get(key: str) -> str:
            """Return the value stored under key.

            Further detail that is not part of the first docstring line.
            """
            return "value-for-" + key
        ''',
    )
    # comp-baz deliberately has no gen/ code at all.

    saved = sys.modules.get("bar")
    yield root
    if saved is None:
        sys.modules.pop("bar", None)
    else:
        sys.modules["bar"] = saved


def _is_hard_fail(finding) -> bool:
    for name in ("severity", "level", "kind"):
        val = _get(finding, name)
        if isinstance(val, str):
            norm = val.lower().replace("_", "-")
            if "hard" in norm or norm == "error":
                return True
    hard = _get(finding, "hard_fail")
    return bool(hard)


def _assert_lint_clean(repo_root: Path) -> None:
    try:
        from spec_linter import lint
    except ImportError:
        return
    report = lint(None, repo_root)
    findings = _get(report, "findings")
    if findings is None and isinstance(report, (list, tuple)):
        findings = report
    findings = list(findings or [])
    hard = [f for f in findings if _is_hard_fail(f)]
    assert hard == [], f"fixture is not lint-clean: {hard!r}"


def test_ac_assemble_011_dependency_usage_cards(repo_root):
    _assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    usage = _get(bundle, "dependency_usage")
    assert usage is not None, "bundle has no dependency_usage field"
    assert "comp-bar" in usage
    assert "comp-baz" in usage

    bar_card = usage["comp-bar"]
    assert isinstance(bar_card, str)
    assert bar_card.strip() != ""

    # Real, currently-importable module path for comp-bar's code.
    assert (
        "gen/bar/bar.py" in bar_card
        or "gen/bar" in bar_card
        or re.search(r"(?<![\w\-])bar(?![\w\-])", bar_card)
    ), f"usage card does not name bar's module path: {bar_card!r}"

    # Public symbol with its signature and docstring first line.
    assert "bar_get" in bar_card
    assert re.search(r"key\s*:\s*str", bar_card), bar_card
    assert re.search(r"->\s*str", bar_card), bar_card
    assert "Return the value stored under key." in bar_card
    assert "Further detail that is not part of the first docstring line." not in bar_card

    # Never source text.
    assert '"value-for-" + key' not in bar_card

    # A dependency with no real gen/ code degrades to "", not an error.
    assert usage["comp-baz"] == ""