"""AC-IMPACT-001 (covers R-IMPACT-001).

Given a changed spec id for component comp-foo
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-foo with reason "direct".

Exercised through the documented library entry point
`compute_blast_radius(changed_ids, repo_root) -> BlastRadiusReport`.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

import impact_analyzer


# ---------------------------------------------------------------------------
# Dual dict-or-attribute access helper
# ---------------------------------------------------------------------------

def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


# ---------------------------------------------------------------------------
# Synthetic, lint-clean corpus fixture
# ---------------------------------------------------------------------------

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id: str, title: str, slug: str, depends_on=None) -> str:
    lines = [
        "---",
        f"id: {comp_id}",
        f"title: {title}",
        "status: draft",
        "owners: [test-team]",
    ]
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.extend([
        "sealed: true",
        f"source_path: legacy/{slug}",
        "---",
        "",
        f"# {title}",
        "",
        "## Purpose",
        "",
        f"The {title} component returns its input unchanged, for testing.",
        "",
        "## Rationale",
        "",
        "A minimal synthetic component used only as a test fixture.",
        "",
        "## Scope",
        "",
        "- In scope: returning its input unchanged.",
        "- Out of scope: everything else.",
        "",
        "## Definitions",
        "",
        "None.",
        "",
        "## Behavior",
        "",
        "See `requirements/`.",
        "",
        "## Interfaces",
        "",
        "See `interface/`.",
        "",
        "## Data",
        "",
        "See `interface/data/`.",
        "",
        "## Acceptance criteria",
        "",
        "See `acceptance/`.",
        "",
        "## Non-functional constraints",
        "",
        "See `constraints.md`.",
        "",
        "## Open questions",
        "",
        "## Change log",
        "",
        "- Initial draft.",
        "",
    ])
    return "\n".join(lines)


def _add_component(repo_root: Path, slug: str, upper: str, title: str,
                   depends_on=None) -> None:
    comp_dir = repo_root / "specs" / "components" / slug
    _write(comp_dir / "component.md",
           _component_md(f"comp-{slug}", title, slug, depends_on))
    req_id = f"R-{upper}-001"
    ac_id = f"AC-{upper}-001"
    _write(
        comp_dir / "requirements" / f"{req_id}.md",
        f"# {req_id}\n\n**{req_id}** — The {title} component MUST return "
        f"its input unchanged.\n",
    )
    _write(
        comp_dir / "acceptance" / f"{ac_id}.md",
        f"# {ac_id}\n\nCovers: {req_id}\nKind: generated-test\n\n"
        "```gherkin\n"
        "Given an input value\n"
        f"When the {title} component is called with it\n"
        "Then the same value is returned\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n"
        "- Latency: each call MUST complete within 100 ms. Measured by "
        "timing 100 calls and taking the maximum.\n",
    )
    # sealed source_path target (outside gen/)
    _write(repo_root / "legacy" / slug / "README.txt", "legacy placeholder\n")


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n"
        "- **Widget** — a synthetic term used only by this test fixture.\n",
    )
    (repo_root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "architecture").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "vars").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "decisions").mkdir(parents=True, exist_ok=True)
    _add_component(repo_root, "foo", "FOO", "Foo")
    _add_component(repo_root, "bar", "BAR", "Bar", depends_on=["comp-foo"])


# ---------------------------------------------------------------------------
# Locate the real spec-linter (the tool's own copy) to check the precondition
# ---------------------------------------------------------------------------

def _load_spec_linter():
    existing = sys.modules.get("spec_linter")
    if existing is not None and hasattr(existing, "lint"):
        return existing
    try:
        here = Path(impact_analyzer.__file__).resolve()
    except Exception:
        return None
    for parent in here.parents:
        flat = parent / "gen" / "spec-linter" / "spec_linter.py"
        pkg = parent / "gen" / "spec-linter" / "spec_linter" / "__init__.py"
        for candidate in (flat, pkg):
            if candidate.is_file():
                module_name = "spec_linter"
                spec = importlib.util.spec_from_file_location(
                    module_name, str(candidate)
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module  # register BEFORE exec_module
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    sys.modules.pop(module_name, None)
                    return None
                return module
    return None


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter()
    if spec_linter is None or not hasattr(spec_linter, "lint"):
        # Precondition is still enforced below: a non-lint-clean corpus would
        # yield a non-null precondition_error from the analyzer itself.
        return
    lint = spec_linter.lint
    report = lint(None, repo_root)
    hard = _get(report, "hard_failures")
    findings = _get(report, "findings") or []
    if hard is None:
        hard = sum(1 for f in findings if _get(f, "severity") == "fail")
    failing = [
        (_get(f, "rule_id"), _get(f, "file"), _get(f, "line"), _get(f, "message"))
        for f in findings
        if _get(f, "severity") == "fail"
    ]
    assert hard == 0, f"synthetic fixture is not lint-clean: {failing}"


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def _impacted_entries(report):
    assert report is not None, "compute_blast_radius returned None"
    assert _get(report, "precondition_error") is None, (
        f"unexpected precondition_error: {_get(report, 'precondition_error')!r}"
    )
    impacted = _get(report, "impacted")
    assert impacted is not None, "report has no 'impacted' list"
    return list(impacted)


def _entries_for(impacted, component_id):
    return [e for e in impacted if _get(e, "component_id") == component_id]


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_corpus(root)
    _assert_lint_clean(root)
    return root


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_changed_component_is_impacted_with_reason_direct(repo_root):
    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo_root)
    impacted = _impacted_entries(report)

    foo = _entries_for(impacted, "comp-foo")
    assert len(foo) == 1, (
        f"comp-foo must appear exactly once in impacted, got: {impacted!r}"
    )
    entry = foo[0]
    assert _get(entry, "reason") == "direct", (
        f"comp-foo must be tagged 'direct', got {_get(entry, 'reason')!r}"
    )
    assert _get(entry, "via") is None, (
        f"a 'direct' entry's via must be null, got {_get(entry, 'via')!r}"
    )


def test_component_id_uses_full_comp_prefix_form(repo_root):
    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo_root)
    impacted = _impacted_entries(report)
    ids = [_get(e, "component_id") for e in impacted]
    assert "comp-foo" in ids
    assert "foo" not in ids, f"bare slug must never be reported: {ids!r}"


def test_every_changed_id_is_direct_even_when_also_transitively_reachable(repo_root):
    # comp-bar depends on comp-foo, so it would also be reachable
    # transitively from comp-foo; being named in the changed ids it MUST
    # still be tagged 'direct', and appear only once.
    report = impact_analyzer.compute_blast_radius(
        ["comp-foo", "comp-bar"], repo_root
    )
    impacted = _impacted_entries(report)

    for cid in ("comp-foo", "comp-bar"):
        matches = _entries_for(impacted, cid)
        assert len(matches) == 1, (
            f"{cid} must appear exactly once in impacted, got: {impacted!r}"
        )
        assert _get(matches[0], "reason") == "direct", (
            f"{cid} must be tagged 'direct', got {_get(matches[0], 'reason')!r}"
        )
        assert _get(matches[0], "via") is None


def test_changed_dependent_component_alone_is_direct(repo_root):
    report = impact_analyzer.compute_blast_radius(["comp-bar"], repo_root)
    impacted = _impacted_entries(report)
    bar = _entries_for(impacted, "comp-bar")
    assert len(bar) == 1, f"comp-bar must appear exactly once: {impacted!r}"
    assert _get(bar[0], "reason") == "direct"
    assert _get(bar[0], "via") is None


def test_changed_component_with_dependent_is_still_direct(repo_root):
    # comp-foo has a dependent (comp-bar); comp-foo itself is still 'direct'
    # and not re-tagged with any transitive reason.
    report = impact_analyzer.compute_blast_radius(["comp-foo"], repo_root)
    impacted = _impacted_entries(report)
    foo = _entries_for(impacted, "comp-foo")
    assert [_get(e, "reason") for e in foo] == ["direct"]