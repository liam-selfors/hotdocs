"""Regression tests for `_count_interface_surface` (the R-LINT-012
"interface surface elements" dimension), run against this repository's own
real `interface.md` files rather than synthetic fixtures — deliberately,
since the counting algorithm itself was only designed after surveying the
real, independently-authored files already in the corpus. Hand-verified
expected counts are recorded here as the actual check, not just asserted
blind.
"""

from pathlib import Path

from conftest import REPO_ROOT, spec_linter


def _load_interface(component: str) -> spec_linter.Doc:
    path = REPO_ROOT / "specs" / "components" / component / "interface.md"
    text = path.read_text(encoding="utf-8")
    fm, body, _ = spec_linter._parse_frontmatter(text)
    return spec_linter.Doc(
        path=path, rel_path=str(path.relative_to(REPO_ROOT)), doc_id=fm.get("id"),
        frontmatter=fm, body=body, doc_type="component-interface", component=component,
    )


def test_spec_linter_interface_surface_is_three():
    # 1 CLI invocation + 1 Library function + 1 Data: `LintReport` heading.
    assert spec_linter._count_interface_surface(_load_interface("spec-linter")) == 3


def test_impact_analyzer_interface_surface_is_three():
    # 1 CLI invocation + 1 Library function + 1 Data: `BlastRadiusReport`.
    assert spec_linter._count_interface_surface(_load_interface("impact-analyzer")) == 3


def test_cache_manager_interface_surface_is_six():
    # 2 CLI subcommands (inspect, stats) + 2 Library functions (get, put) +
    # 2 Data headings (CacheKey, CachedResult) — the component whose
    # multi-entity blocks is exactly why "one per fenced code block" (an
    # earlier, simpler candidate algorithm) would have undercounted.
    assert spec_linter._count_interface_surface(_load_interface("cache-manager")) == 6


def test_criterion_compiler_interface_surface_is_three():
    # 1 CLI invocation (wrapped across two physical lines via a trailing
    # backslash — must be joined, not double-counted) + 1 Library function +
    # 1 Data: `CompileReport`. The "## The step grammar" section is
    # deliberately not counted — it's reference data, not a callable surface.
    assert spec_linter._count_interface_surface(_load_interface("criterion-compiler")) == 3


def test_all_four_real_components_stay_well_under_the_hard_cap():
    # Sanity check tying this back to D2's actual size-cap table (20 hard
    # fail) — none of the real components specced so far are anywhere near
    # it, which is itself a useful signal that the components are
    # reasonably scoped.
    for component in ("spec-linter", "impact-analyzer", "cache-manager", "criterion-compiler"):
        count = spec_linter._count_interface_surface(_load_interface(component))
        assert count <= 20, f"{component}: {count} interface surface elements"
