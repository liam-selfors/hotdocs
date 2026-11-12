"""One test per AC-LINT-* criterion in specs/components/spec-linter/acceptance/.

HAND-AUTHORED BOOTSTRAP — see BOOTSTRAP.md. These are what `criterion-compiler`
would deterministically compile from the Gherkin blocks once it exists; a
human stood in for that compiler exactly once here, by transcribing each
Given/When/Then into pytest by hand. Not a general-purpose test-writing
pattern going forward — this is the explicitly one-time bootstrap exception.

REWRITTEN for D15 (one-file-per-unit component layout): every test that used
to mutate `spec.md`/`interface.md`/`acceptance.md` as shared files now mutates
the specific unit file (`component.md`, one `requirements/R-*.md`, one
`acceptance/AC-*.md`) that actually owns the content being tested.
"""

from conftest import REPO_ROOT, run_lint, has_finding


def _comp(root, name="foo"):
    return root / "specs" / "components" / name


def _patch(path, *replacements):
    """Apply one or more (old, new) text replacements to a file in sequence.
    Centralizes the read -> replace -> write boilerplate every fixture
    mutation below used to repeat on its own (D40)."""
    text = path.read_text()
    for old, new in replacements:
        text = text.replace(old, new)
    path.write_text(text)


def test_ac_lint_001_missing_owners(corpus_root):
    _patch(_comp(corpus_root) / "component.md", ("owners: [test-team]\n", ""))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-001")


def test_ac_lint_002_ratified_with_open_questions(corpus_root):
    _patch(
        _comp(corpus_root) / "component.md",
        ("status: draft", "status: ratified"),
        ("## Open questions\n", "## Open questions\n\n- Still unresolved.\n"),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-002")


def test_ac_lint_003_dangling_depends_on(corpus_root):
    _patch(_comp(corpus_root) / "component.md", ("depends_on: []", "depends_on: [comp-bar]"))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-003")
    assert any("comp-bar" in f.message for f in report.findings if f.rule_id == "R-LINT-003")


def test_ac_lint_004_dependency_cycle(corpus_root):
    _patch(_comp(corpus_root) / "component.md", ("depends_on: []", "depends_on: [comp-bar]"))

    bar_dir = _comp(corpus_root, "bar")
    (bar_dir / "requirements").mkdir(parents=True)
    (bar_dir / "acceptance").mkdir(parents=True)
    (bar_dir / "component.md").write_text(
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: [comp-foo]\n"
        "realizes: [P-TEST]\n"
        "sealed: false\n"
        "---\n\n# Bar\n\n## Purpose\n\nCycle partner.\n\n## Scope\n\nIn scope: n/a.\n\n"
        "## Definitions\n\nNo deltas.\n\n## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nNone.\n\n## Data\n\nNone.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n## Non-functional constraints\n\nNone.\n\n"
        "## Open questions\n\n## Change log\n\n- Initial.\n"
    )
    (bar_dir / "requirements" / "R-BAR-001.md").write_text(
        "# R-BAR-001\n\n**R-BAR-001** — The component MUST exist.\n"
    )
    (bar_dir / "acceptance" / "AC-BAR-001.md").write_text(
        "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: compiled\n\n"
        "```gherkin\nGiven nothing\nWhen checked\nThen it exists\n```\n"
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-004")


def test_ac_lint_005_sealed_without_source_path(corpus_root):
    _patch(_comp(corpus_root) / "component.md", ("sealed: false", "sealed: true"))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-005")


def test_ac_lint_006_non_sealed_zero_realizes(corpus_root):
    _patch(_comp(corpus_root) / "component.md", ("realizes: [P-TEST]", "realizes: []"))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-006")


def test_ac_lint_007_requirement_without_rfc2119_keyword(corpus_root):
    _patch(
        _comp(corpus_root) / "requirements" / "R-FOO-001.md",
        (
            "**R-FOO-001** — The component MUST do the one thing it is specified to do.",
            "**R-FOO-001** — The component does the one thing it is specified to do.",
        ),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-007")


def test_ac_lint_008_requirement_with_no_covering_criterion(corpus_root):
    req_dir = _comp(corpus_root) / "requirements"
    (req_dir / "R-FOO-002.md").write_text(
        "# R-FOO-002\n\n**R-FOO-002** — The component MUST also do a second thing.\n"
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-008")
    assert any("R-FOO-002" in f.message for f in report.findings if f.rule_id == "R-LINT-008")


def test_ac_lint_009_covers_dangling_reference(corpus_root):
    _patch(
        _comp(corpus_root) / "acceptance" / "AC-FOO-001.md",
        ("Covers: R-FOO-001", "Covers: R-DOES-NOT-EXIST"),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-009")


def test_ac_lint_010_criterion_missing_kind_tag(corpus_root):
    _patch(_comp(corpus_root) / "acceptance" / "AC-FOO-001.md", ("Kind: compiled\n", ""))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-010")


def test_ac_lint_011_near_verbatim_restatement_fails(corpus_root):
    # R-LINT-011 was revised from "does the term name reappear" (too broad —
    # couldn't tell a restatement from a legitimate delta) to "is the local
    # text a near-verbatim copy of the glossary's own definition." This
    # fixture's text is a near-identical restatement of "a thing this corpus
    # talks about" (the glossary's definition of Widget), so it should still
    # fire R-LINT-011.
    _patch(
        _comp(corpus_root) / "component.md",
        (
            "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
            "## Definitions\n\n- **Widget** — a thing this corpus talks about.\n",
        ),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-011")


def test_ac_lint_011b_genuine_delta_does_not_fail(corpus_root):
    # A low-overlap, genuinely additional nuance must NOT fire R-LINT-011 —
    # that would be exactly the over-broad behavior the rule was revised
    # away from. (It legitimately falls to R-LINT-015 instead, which will
    # report `skipped` with no judge configured — asserted separately below,
    # not here, since R-LINT-011's own correctness is what this test is for.)
    _patch(
        _comp(corpus_root) / "component.md",
        (
            "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
            "## Definitions\n\n- **Widget** — in Foo specifically, always carries a "
            "serial number assigned at creation time.\n",
        ),
    )
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-LINT-011")


def test_ac_lint_011_old_fixture_now_routes_to_015_not_011(corpus_root):
    # Regression check: this is literally the old (pre-revision) test's
    # fixture text. Under the old term-reappearance heuristic it
    # (coincidentally correctly, but for the wrong reason) fired R-LINT-011.
    # Under the revised split it has low token-overlap with the glossary
    # definition, so it must NOT fire R-LINT-011 — it's R-LINT-015's job
    # (a semantic conflict, not a structural restatement) and, with no judge
    # configured here, reports skipped rather than silently passing.
    _patch(
        _comp(corpus_root) / "component.md",
        (
            "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
            "## Definitions\n\n- **Widget** — a totally different meaning than the glossary gives it.\n",
        ),
    )
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-LINT-011")
    assert has_finding(report, "R-LINT-015", severity="skipped")


def test_ac_lint_015_conflict_detected_with_judge_configured(corpus_root):
    _patch(
        _comp(corpus_root) / "component.md",
        (
            "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
            "## Definitions\n\n- **Widget** — a totally different meaning than the glossary gives it.\n",
        ),
    )

    def mock_judge(term, local_text, glossary_text):
        return (True, f"'{local_text}' contradicts '{glossary_text}' for '{term}'")

    report = run_lint(corpus_root, judge=mock_judge)
    assert has_finding(report, "R-LINT-015", severity="fail")
    finding = next(f for f in report.findings if f.rule_id == "R-LINT-015")
    assert finding.rationale and "contradicts" in finding.rationale


def test_ac_lint_015b_skipped_without_model(corpus_root):
    _patch(
        _comp(corpus_root) / "component.md",
        (
            "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
            "## Definitions\n\n- **Widget** — a totally different meaning than the glossary gives it.\n",
        ),
    )
    report = run_lint(corpus_root)  # no judge
    assert has_finding(report, "R-LINT-015", severity="skipped")
    assert report.hard_failures == 0  # skipped must never count as a failure


def test_ac_lint_012_generated_code_over_hard_cap(corpus_root):
    gen_dir = corpus_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / "big.py").write_text("\n".join(f"x{i} = {i}" for i in range(1600)))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-SIZE-001")
    assert any("generated_code_loc" in f.message for f in report.findings if f.rule_id == "R-SIZE-001")


def test_ac_lint_022_fires_on_two_crowded_dimensions(corpus_root):
    gen_dir = corpus_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / "big.py").write_text("\n".join(f"x{i} = {i}" for i in range(900)))
    requirement = _comp(corpus_root) / "requirements" / "R-FOO-001.md"
    requirement.write_text(requirement.read_text() + "\n\n" + " ".join(["word"] * 2100))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-SIZE-002", severity="warn")
    finding = next(f for f in report.findings if f.rule_id == "R-SIZE-002")
    assert "generated_code_loc" in finding.message and "component_doc_words" in finding.message


def test_ac_lint_022_does_not_fire_on_one_crowded_dimension(corpus_root):
    gen_dir = corpus_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / "big.py").write_text("\n".join(f"x{i} = {i}" for i in range(900)))
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-SIZE-002", severity="warn")


def test_ac_lint_023_fires_on_long_requirement_file(corpus_root):
    requirement = _comp(corpus_root) / "requirements" / "R-FOO-001.md"
    requirement.write_text(requirement.read_text() + "\n\n" + " ".join(["word"] * 520))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-SIZE-003", severity="fail")
    finding = next(f for f in report.findings if f.rule_id == "R-SIZE-003")
    assert "R-FOO-001" in finding.file


def test_ac_lint_023_does_not_fire_on_short_file(corpus_root):
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-SIZE-003", severity="fail")
    assert not has_finding(report, "R-SIZE-003", severity="warn")


def test_guarantee_count_cap(corpus_root):
    guarantees_dir = _comp(corpus_root) / "interface" / "guarantees"
    guarantees_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 12):
        (guarantees_dir / f"G-FOO-{i:03d}.md").write_text(f"# G-FOO-{i:03d}\n\nSome guarantee text.\n")
    report = run_lint(corpus_root)
    assert has_finding(report, "R-SIZE-001", severity="fail")
    assert any("guarantee_count" in f.message for f in report.findings if f.rule_id == "R-SIZE-001")


def test_acceptance_count_cap(corpus_root):
    acceptance_dir = _comp(corpus_root) / "acceptance"
    for i in range(2, 52):
        (acceptance_dir / f"AC-FOO-{i:03d}.md").write_text(
            f"# AC-FOO-{i:03d}\n\nCovers: R-FOO-001\nKind: compiled\n\n"
            "```gherkin\nGiven a thing\nWhen it happens\nThen it works\n```\n"
        )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-SIZE-001", severity="fail")
    assert any("acceptance_count" in f.message for f in report.findings if f.rule_id == "R-SIZE-001")


def test_ac_lint_013_secret_var_with_default(corpus_root):
    vars_dir = corpus_root / "specs" / "vars"
    vars_dir.mkdir(parents=True)
    (vars_dir / "secret-thing.md").write_text(
        "---\nid: VAR-SECRET-THING\ntitle: Secret Thing\nstatus: draft\n"
        "owners: [test-team]\n---\n\n# VAR-SECRET-THING\n\n"
        "- **required:** yes\n- **type:** secret-ref\n- **sensitivity:** secret\n"
        "- **default:** not-actually-allowed\n"
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-013")


def test_ac_lint_014_duplicate_glossary_without_split_decision(corpus_root):
    (corpus_root / "specs" / "glossary-extra.md").write_text("# Another Glossary\n\n- **Gadget** — also a thing.\n")
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-014")


def test_ac_lint_016_stray_frontmatter_on_unit_file(corpus_root):
    req = _comp(corpus_root) / "requirements" / "R-FOO-001.md"
    req.write_text(
        "---\nid: R-FOO-001\ntitle: should not be here\n---\n\n" + req.read_text()
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-016")


def test_ac_lint_017_guarantee_heading_mismatch(corpus_root):
    guarantees_dir = _comp(corpus_root) / "interface" / "guarantees"
    guarantees_dir.mkdir(parents=True)
    (guarantees_dir / "G-FOO-001.md").write_text(
        "# G-FOO-002\n\n**G-FOO-002** — Calls MUST be idempotent.\n"
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-017")


def test_ac_lint_018_dangling_depends_on_guarantees(corpus_root):
    _patch(
        _comp(corpus_root) / "component.md",
        ("depends_on: []", "depends_on: []\ndepends_on_guarantees: [G-DOES-NOT-EXIST]"),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-018")


def test_ac_lint_018b_guarantee_owner_not_in_depends_on(corpus_root):
    bar_dir = _comp(corpus_root, "bar")
    (bar_dir / "requirements").mkdir(parents=True)
    (bar_dir / "interface" / "guarantees").mkdir(parents=True)
    (bar_dir / "acceptance").mkdir(parents=True)
    (bar_dir / "component.md").write_text(
        "---\nid: comp-bar\ntitle: Bar\nstatus: draft\nowners: [test-team]\n"
        "depends_on: []\nrealizes: [P-TEST]\nsealed: false\n---\n\n# Bar\n\n"
        "## Purpose\n\nGuarantee owner.\n\n## Scope\n\nIn scope: n/a.\n\n"
        "## Definitions\n\nNo deltas.\n\n## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n## Data\n\nNone.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n## Non-functional constraints\n\nNone.\n\n"
        "## Open questions\n\n## Change log\n\n- Initial.\n"
    )
    (bar_dir / "requirements" / "R-BAR-001.md").write_text(
        "# R-BAR-001\n\n**R-BAR-001** — The component MUST exist.\n"
    )
    (bar_dir / "interface" / "guarantees" / "G-BAR-001.md").write_text(
        "# G-BAR-001\n\n**G-BAR-001** — Calls MUST be idempotent.\n"
    )
    (bar_dir / "acceptance" / "AC-BAR-001.md").write_text(
        "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: compiled\n\n"
        "```gherkin\nGiven nothing\nWhen checked\nThen it exists\n```\n"
    )

    # foo references bar's guarantee but never declares bar as a dependency.
    _patch(
        _comp(corpus_root) / "component.md",
        ("depends_on: []", "depends_on: []\ndepends_on_guarantees: [G-BAR-001]"),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-018")
    assert any("comp-bar" in f.message for f in report.findings if f.rule_id == "R-LINT-018")


def test_ac_lint_019_trailing_whitespace(corpus_root):
    req = _comp(corpus_root) / "requirements" / "R-FOO-002.md"
    req.write_text(
        "# R-FOO-002\n\n**R-FOO-002** — The component MUST also do a second thing.  \n"
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-019")


def test_ac_lint_024_purpose_cites_decision(corpus_root):
    _patch(
        _comp(corpus_root) / "component.md",
        (
            "A minimal component for exercising the linter.",
            "A minimal component for exercising the linter, extracted once D30 found a real coupling.",
        ),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-024")


def test_ac_lint_024_clean_purpose_does_not_fire(corpus_root):
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-LINT-024")


def test_ac_lint_025_long_purpose(corpus_root):
    long_purpose = " ".join(["word"] * 160)
    _patch(
        _comp(corpus_root) / "component.md",
        ("A minimal component for exercising the linter.", long_purpose),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-SIZE-004")
    assert not has_finding(report, "R-LINT-024")


def test_ac_lint_025_short_purpose_does_not_fire(corpus_root):
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-SIZE-004")


def test_ac_lint_026_dangling_decision_citation(corpus_root):
    _patch(
        _comp(corpus_root) / "component.md",
        ("In scope: everything. Out of scope: nothing.", "In scope: everything (D500). Out of scope: nothing."),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-CITE-001")


def test_ac_lint_026_frozen_decision_does_not_fire(corpus_root):
    _patch(
        _comp(corpus_root) / "component.md",
        ("In scope: everything. Out of scope: nothing.", "In scope: everything (D5). Out of scope: nothing."),
    )
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-CITE-001")


def test_ac_lint_027_section_reference_resolution(corpus_root):
    arch_dir = corpus_root / "specs" / "architecture"
    arch_dir.mkdir(parents=True)
    (arch_dir / "arch-doc.md").write_text("# Arch Doc\n\n## Query surface\n\nSome views.\n")
    _patch(
        _comp(corpus_root) / "requirements" / "R-FOO-001.md",
        (
            "The component MUST do the one thing it is specified to do.",
            "The component MUST do the one thing `specs/architecture/arch-doc.md`'s "
            '"Query surface" section describes, and the thing '
            '`specs/architecture/arch-doc.md`\'s "Nonexistent Heading" section does not.',
        ),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-CITE-002")
    findings = [f for f in report.findings if f.rule_id == "R-CITE-002"]
    assert len(findings) == 1
    assert "Nonexistent Heading" in findings[0].message


def test_ac_lint_028_glossary_citation_resolution(corpus_root):
    """D86 -- a 'the glossary's "<Term>"' citation must resolve to a
    real bolded entry header in specs/glossary.md."""
    glossary = corpus_root / "specs" / "glossary.md"
    glossary.write_text(
        glossary.read_text(encoding="utf-8")
        + "- **A Real Test Term** — defined for this test.\n",
        encoding="utf-8",
    )
    _patch(
        _comp(corpus_root) / "requirements" / "R-FOO-001.md",
        (
            "The component MUST do the one thing it is specified to do.",
            'The component MUST use the glossary\'s "A Real Test Term" '
            'and never the glossary\'s "A Made Up Term".',
        ),
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-CITE-003")
    findings = [f for f in report.findings if f.rule_id == "R-CITE-003"]
    assert len(findings) == 1
    assert "A Made Up Term" in findings[0].message


def _write_decision(
    root: Path, doc_id: str, status: str = "ratified",
    supersedes: str | None = None, builds_on: list[str] | None = None,
) -> None:
    decisions_dir = root / "specs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = (
        f"---\nid: {doc_id}\ntitle: Test decision {doc_id}\nstatus: {status}\n"
        f"owners: [test-team]\n"
    )
    if supersedes:
        frontmatter += f"supersedes: {supersedes}\n"
    if builds_on:
        frontmatter += f"builds_on: [{', '.join(builds_on)}]\n"
    frontmatter += f"last_ratified_commit: abc1234\n---\n\n# {doc_id}\n\nBody text.\n"
    (decisions_dir / f"{doc_id}.md").write_text(frontmatter, encoding="utf-8")


def test_ac_lint_029_dangling_supersedes_citation(corpus_root):
    """D87 -- supersedes: D<N> must resolve to a real decision file."""
    _write_decision(corpus_root, "D900", supersedes="D999")
    report = run_lint(corpus_root)
    assert has_finding(report, "R-CITE-004")


def test_ac_lint_029_superseded_decision_not_deprecated(corpus_root):
    """supersedes resolving to a still-ratified (not deprecated) decision
    must fire -- supersedes means full replacement."""
    _write_decision(corpus_root, "D900", supersedes="D901")
    _write_decision(corpus_root, "D901", status="ratified")
    report = run_lint(corpus_root)
    findings = [f for f in report.findings if f.rule_id == "R-CITE-004"]
    assert any("D901" in f.message for f in findings)


def test_ac_lint_029_deprecated_with_no_superseder_fires(corpus_root):
    """status: deprecated with no other decision's supersedes naming it
    must fire -- deprecation is never a standalone edit."""
    _write_decision(corpus_root, "D900", status="deprecated")
    report = run_lint(corpus_root)
    assert has_finding(report, "R-CITE-004")


def test_ac_lint_029_consistent_pair_does_not_fire(corpus_root):
    _write_decision(corpus_root, "D900", supersedes="D901")
    _write_decision(corpus_root, "D901", status="deprecated")
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-CITE-004")


def test_ac_lint_029_frozen_range_exempt(corpus_root):
    _write_decision(corpus_root, "D900", supersedes="D5")
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-CITE-004")


def test_ac_lint_030_dangling_builds_on_citation(corpus_root):
    """D91 -- builds_on: D<N> must resolve to a real decision file."""
    _write_decision(corpus_root, "D900", builds_on=["D999"])
    report = run_lint(corpus_root)
    assert has_finding(report, "R-CITE-005")


def test_ac_lint_030_frozen_range_exempt(corpus_root):
    _write_decision(corpus_root, "D900", builds_on=["D5"])
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-CITE-005")


def _add_cli(root):
    iface = _comp(root) / "interface"
    (iface / "cli.md").write_text("# CLI\n\n```\nhotdocs foo [--x=<y>]\n```\n")


def test_ac_lint_031_covered_cli_requirement_passes(corpus_root):
    """D162 -- a CLI cited by a covered requirement draws no finding."""
    _add_cli(corpus_root)
    _patch(_comp(corpus_root) / "requirements" / "R-FOO-001.md",
           ("specified to do.", "specified to do, per `interface/cli.md`."))
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-LINT-031", severity="warn")


def test_ac_lint_031_citing_requirement_without_criterion_warns(corpus_root):
    _add_cli(corpus_root)
    (_comp(corpus_root) / "requirements" / "R-FOO-002.md").write_text(
        "# R-FOO-002\n\n**R-FOO-002** — `main` MUST implement `interface/cli.md`.\n"
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-031", severity="warn")
    assert not has_finding(report, "R-LINT-031", severity="fail")


def test_ac_lint_031_uncited_cli_warns(corpus_root):
    _add_cli(corpus_root)
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-031", severity="warn")
    assert not has_finding(report, "R-LINT-031", severity="fail")


def test_ac_lint_031_no_cli_no_finding(corpus_root):
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-LINT-031", severity="warn")


def _glossary_with(corpus_root, entry):
    glossary = corpus_root / "specs" / "glossary.md"
    glossary.write_text(glossary.read_text(encoding="utf-8") + entry, encoding="utf-8")


def test_ac_lint_028_wrapped_and_punctuated_citations_resolve(corpus_root):
    """Real prose hard-wraps a citation across lines and puts a comma
    inside the closing quote; neither is drift (D176)."""
    _glossary_with(corpus_root, "- **Wrapped Test Term** — defined for this test.\n")
    _patch(
        _comp(corpus_root) / "requirements" / "R-FOO-001.md",
        (
            "The component MUST do the one thing it is specified to do.",
            'The component MUST follow the glossary\'s "Wrapped\n  Test Term," and also the glossary\'s "Wrapped Test Term".',
        ),
    )
    assert not has_finding(run_lint(corpus_root), "R-CITE-003")


def test_ac_lint_028_placeholder_is_not_a_citation(corpus_root):
    _patch(
        _comp(corpus_root) / "requirements" / "R-FOO-001.md",
        (
            "The component MUST do the one thing it is specified to do.",
            'The component MUST do it; a rule cites the glossary\'s "<Term>" as a pattern.',
        ),
    )
    assert not has_finding(run_lint(corpus_root), "R-CITE-003")


def test_ac_lint_028_citation_is_case_exact(corpus_root):
    _glossary_with(corpus_root, "- **Case Test Term** — defined for this test.\n")
    _patch(
        _comp(corpus_root) / "requirements" / "R-FOO-001.md",
        (
            "The component MUST do the one thing it is specified to do.",
            'The component MUST use the glossary\'s "case test term".',
        ),
    )
    assert has_finding(run_lint(corpus_root), "R-CITE-003")


def test_ac_lint_029_prose_quoting_a_field_is_not_supersession(corpus_root):
    """D137 quotes `supersedes: [D17]` in prose; that must not read as a
    supersession (D176)."""
    decisions_dir = corpus_root / "specs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (decisions_dir / "D900.md").write_text(
        "---\nid: D900\ntitle: Quotes a field\nstatus: ratified\nowners: [t]\n"
        "last_ratified_commit: abc1234\n---\n\n# D900\n\nWe cite `supersedes: D901`\n"
        "and, on its own line,\nbuilds_on: [D999]\nas examples.\n",
        encoding="utf-8",
    )
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-CITE-004")
    assert not has_finding(report, "R-CITE-005")


def test_ac_lint_029_030_fire_on_a_mutated_copy_of_the_real_corpus(tmp_path):
    """Zero findings on the real corpus proves nothing unless the rules can
    fire there: copy it, break one thing per rule, expect one finding each."""
    import shutil
    from conftest import REPO_ROOT
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "specs", root / "specs")
    decisions = root / "specs" / "decisions"
    d = decisions / "D50.md"
    d.write_text(d.read_text(encoding="utf-8").replace("owners:", "builds_on: [D9999]\nowners:", 1), encoding="utf-8")
    d = decisions / "D51.md"
    d.write_text(d.read_text(encoding="utf-8").replace("status: ratified", "status: deprecated", 1), encoding="utf-8")
    d = decisions / "D52.md"
    d.write_text(d.read_text(encoding="utf-8").replace("owners:", "supersedes: D53\nowners:", 1), encoding="utf-8")
    report = run_lint(root)
    by_rule = {}
    for f in report.findings:
        by_rule.setdefault(f.rule_id, []).append(f.message)
    assert len(by_rule.get("R-CITE-005", [])) == 1 and "D9999" in by_rule["R-CITE-005"][0]
    msgs = by_rule.get("R-CITE-004", [])
    # Message wording is not specified; each finding names its decisions.
    assert any("D51" in m and "D52" not in m for m in msgs)
    assert any("D52" in m and "D53" in m for m in msgs)
    assert len(msgs) == 2


def test_ac_lint_032_project_component_reusing_a_tool_slug_fails(corpus_root):
    """D199 -- a project's copy of a tool component's slug would shadow the
    tool's own, since loaders try repo_root before the tool root."""
    import shutil
    shutil.copytree(_comp(corpus_root), _comp(corpus_root, "cache-manager"))
    root_md = _comp(corpus_root, "cache-manager") / "component.md"
    root_md.write_text(root_md.read_text().replace("comp-foo", "comp-cache-manager"))
    (corpus_root / ".hotdocs-tool.json").write_text('{"tool_version": "0.1.0"}\n')
    report = run_lint(corpus_root)
    hits = [f for f in report.findings if f.rule_id == "R-LINT-032"]
    assert [f.severity for f in hits] == ["fail"]
    assert "cache-manager" in hits[0].message


def test_ac_lint_032_no_finding_without_a_clash(corpus_root):
    (corpus_root / ".hotdocs-tool.json").write_text('{"tool_version": "0.1.0"}\n')
    assert not has_finding(run_lint(corpus_root), "R-LINT-032")


def test_ac_lint_032_only_projects_made_by_init_are_checked(corpus_root):
    import shutil
    shutil.copytree(_comp(corpus_root), _comp(corpus_root, "cache-manager"))
    assert not has_finding(run_lint(corpus_root), "R-LINT-032")


def test_ac_lint_032_the_tool_itself_is_exempt():
    assert not has_finding(run_lint(REPO_ROOT), "R-LINT-032")
