"""Regression tests for `_count_interface_surface` (the R-LINT-012
"interface surface elements" dimension), run against this repository's own
real `interface/` directories rather than synthetic fixtures — deliberately,
since the counting algorithm itself was only designed after surveying the
real, independently-authored files already in the corpus. Hand-verified
expected counts are recorded here as the actual check, not just asserted
blind.

REWRITTEN for D15: a component's interface is now `interface/cli.md` +
`interface/library.md` + one file per `interface/data/*.md`, not a single
`interface.md` with `## CLI`/`## Library`/`## Data: ...` headings —
`_count_interface_surface` takes a `Component` aggregate, not one `Doc`.
"""

from pathlib import Path

from conftest import REPO_ROOT, spec_linter


def _load_component_interface(name: str) -> spec_linter.Component:
    comp_dir = REPO_ROOT / "specs" / "components" / name

    def load(rel: str) -> spec_linter.Doc | None:
        path = comp_dir / rel
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        _, body, _ = spec_linter._parse_frontmatter(text)
        return spec_linter.Doc(
            path=path, rel_path=str(path.relative_to(REPO_ROOT)), doc_id=None,
            frontmatter={}, body=body, doc_type="component-interface-cli", component=name,
        )

    interface_data = {}
    data_dir = comp_dir / "interface" / "data"
    if data_dir.is_dir():
        for p in sorted(data_dir.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            _, body, _ = spec_linter._parse_frontmatter(text)
            interface_data[p.stem] = spec_linter.Doc(
                path=p, rel_path=str(p.relative_to(REPO_ROOT)), doc_id=None,
                frontmatter={}, body=body, doc_type="component-interface-data", component=name,
            )

    return spec_linter.Component(
        name=name, root=None, requirements={},
        interface_cli=load("interface/cli.md"),
        interface_library=load("interface/library.md"),
        interface_data=interface_data,
        interface_guarantees={},
        acceptance={}, constraints=None,
    )


def test_spec_linter_interface_surface_is_three():
    # 1 CLI invocation + 1 Library function + 1 Data file (`LintReport`).
    assert spec_linter._count_interface_surface(_load_component_interface("spec-linter")) == 3


def test_impact_analyzer_interface_surface_is_three():
    # 1 CLI invocation + 1 Library function + 1 Data file (`BlastRadiusReport`).
    assert spec_linter._count_interface_surface(_load_component_interface("impact-analyzer")) == 3


def test_cache_manager_interface_surface_is_six():
    # 2 CLI subcommands (inspect, stats) + 2 Library functions (get, put) +
    # 2 Data files (CacheKey, CachedResult) — the component whose
    # multi-entity blocks is exactly why "one per fenced code block" (an
    # earlier, simpler candidate algorithm) would have undercounted.
    assert spec_linter._count_interface_surface(_load_component_interface("cache-manager")) == 6


def test_criterion_compiler_interface_surface_is_four():
    # 1 CLI invocation (wrapped across two physical lines via a trailing
    # backslash — must be joined, not double-counted) + 2 Library functions
    # (`compile`, and `compile_criterion` added by D75) + 1 Data file
    # (`CompileReport`). The step grammar lives at specs/architecture/
    # step-phrase-grammar.md now (D15), not under this component's
    # interface/ at all, so it was never a candidate for double-counting
    # here even before that move — but it's worth noting the relocation
    # makes that structurally obvious rather than a parsing nicety.
    assert spec_linter._count_interface_surface(_load_component_interface("criterion-compiler")) == 4


def test_all_four_real_components_stay_well_under_the_hard_cap():
    # Sanity check tying this back to D2's actual size-cap table (20 hard
    # fail) — none of the real components specced so far are anywhere near
    # it, which is itself a useful signal that the components are
    # reasonably scoped.
    for component in ("spec-linter", "impact-analyzer", "cache-manager", "criterion-compiler"):
        count = spec_linter._count_interface_surface(_load_component_interface(component))
        assert count <= 20, f"{component}: {count} interface surface elements"
