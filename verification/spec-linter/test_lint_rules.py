"""One test per AC-LINT-* criterion in specs/components/spec-linter/acceptance.md.

HAND-AUTHORED BOOTSTRAP — see BOOTSTRAP.md. These are what `criterion-compiler`
would deterministically compile from the Gherkin blocks once it exists; a
human stood in for that compiler exactly once here, by transcribing each
Given/When/Then into pytest by hand. Not a general-purpose test-writing
pattern going forward — this is the explicitly one-time bootstrap exception.
"""

from conftest import run_lint, has_finding


def test_ac_lint_001_missing_owners(corpus_root):
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace("owners: [test-team]\n", ""))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-001")


def test_ac_lint_002_ratified_with_open_questions(corpus_root):
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    text = spec.read_text()
    text = text.replace("status: draft", "status: ratified")
    text = text.replace("## Open questions\n", "## Open questions\n\n- Still unresolved.\n")
    spec.write_text(text)
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-002")


def test_ac_lint_003_dangling_depends_on(corpus_root):
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace("depends_on: []", "depends_on: [comp-bar]"))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-003")
    assert any("comp-bar" in f.message for f in report.findings if f.rule_id == "R-LINT-003")


def test_ac_lint_004_dependency_cycle(corpus_root):
    foo_spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    foo_spec.write_text(foo_spec.read_text().replace("depends_on: []", "depends_on: [comp-bar]"))

    bar_dir = corpus_root / "specs" / "components" / "bar"
    bar_dir.mkdir(parents=True)
    (bar_dir / "spec.md").write_text(
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: [comp-foo]\n"
        "realizes: [P-TEST]\n"
        "sealed: false\n"
        "---\n\n# Bar\n\n## Purpose\n\nCycle partner.\n\n## Scope\n\nIn scope: n/a.\n\n"
        "## Definitions\n\nNo deltas.\n\n## Behavior\n\n"
        "- **R-BAR-001** — The component MUST exist.\n\n"
        "## Interfaces\n\nNone.\n\n## Data\n\nNone.\n\n"
        "## Acceptance criteria\n\nNone.\n\n## Non-functional constraints\n\nNone.\n\n"
        "## Open questions\n\n## Change log\n\n- Initial.\n"
    )
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-004")


def test_ac_lint_005_sealed_without_source_path(corpus_root):
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace("sealed: false", "sealed: true"))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-005")


def test_ac_lint_006_non_sealed_zero_realizes(corpus_root):
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace("realizes: [P-TEST]", "realizes: []"))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-006")


def test_ac_lint_007_requirement_without_rfc2119_keyword(corpus_root):
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace(
        "- **R-FOO-001** — The component MUST do the one thing it is specified to do.",
        "- **R-FOO-001** — The component does the one thing it is specified to do.",
    ))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-007")


def test_ac_lint_008_requirement_with_no_covering_criterion(corpus_root):
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace(
        "## Behavior\n\n- **R-FOO-001** — The component MUST do the one thing it is specified to do.\n",
        "## Behavior\n\n- **R-FOO-001** — The component MUST do the one thing it is specified to do.\n"
        "- **R-FOO-002** — The component MUST also do a second thing.\n",
    ))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-008")
    assert any("R-FOO-002" in f.message for f in report.findings if f.rule_id == "R-LINT-008")


def test_ac_lint_009_covers_dangling_reference(corpus_root):
    acc = corpus_root / "specs" / "components" / "foo" / "acceptance.md"
    acc.write_text(acc.read_text().replace("Covers: R-FOO-001", "Covers: R-DOES-NOT-EXIST"))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-009")


def test_ac_lint_010_criterion_missing_kind_tag(corpus_root):
    acc = corpus_root / "specs" / "components" / "foo" / "acceptance.md"
    acc.write_text(acc.read_text().replace("Kind: compiled\n", ""))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-010")


def test_ac_lint_011_near_verbatim_restatement_fails(corpus_root):
    # R-LINT-011 was revised from "does the term name reappear" (too broad —
    # couldn't tell a restatement from a legitimate delta) to "is the local
    # text a near-verbatim copy of the glossary's own definition." This
    # fixture's text is a near-identical restatement of "a thing this corpus
    # talks about" (the glossary's definition of Widget), so it should still
    # fire R-LINT-011.
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace(
        "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
        "## Definitions\n\n- **Widget** — a thing this corpus talks about.\n",
    ))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-011")


def test_ac_lint_011b_genuine_delta_does_not_fail(corpus_root):
    # A low-overlap, genuinely additional nuance must NOT fire R-LINT-011 —
    # that would be exactly the over-broad behavior the rule was revised
    # away from. (It legitimately falls to R-LINT-015 instead, which will
    # report `skipped` with no judge configured — asserted separately below,
    # not here, since R-LINT-011's own correctness is what this test is for.)
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace(
        "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
        "## Definitions\n\n- **Widget** — in Foo specifically, always carries a "
        "serial number assigned at creation time.\n",
    ))
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
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace(
        "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
        "## Definitions\n\n- **Widget** — a totally different meaning than the glossary gives it.\n",
    ))
    report = run_lint(corpus_root)
    assert not has_finding(report, "R-LINT-011")
    assert has_finding(report, "R-LINT-015", severity="skipped")


def test_ac_lint_015_conflict_detected_with_judge_configured(corpus_root):
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace(
        "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
        "## Definitions\n\n- **Widget** — a totally different meaning than the glossary gives it.\n",
    ))

    def mock_judge(term, local_text, glossary_text):
        return (True, f"'{local_text}' contradicts '{glossary_text}' for '{term}'")

    report = run_lint(corpus_root, judge=mock_judge)
    assert has_finding(report, "R-LINT-015", severity="fail")
    finding = next(f for f in report.findings if f.rule_id == "R-LINT-015")
    assert finding.rationale and "contradicts" in finding.rationale


def test_ac_lint_015b_skipped_without_model(corpus_root):
    spec = corpus_root / "specs" / "components" / "foo" / "spec.md"
    spec.write_text(spec.read_text().replace(
        "## Definitions\n\nNo deltas from `specs/glossary.md`.\n",
        "## Definitions\n\n- **Widget** — a totally different meaning than the glossary gives it.\n",
    ))
    report = run_lint(corpus_root)  # no judge
    assert has_finding(report, "R-LINT-015", severity="skipped")
    assert report.hard_failures == 0  # skipped must never count as a failure


def test_ac_lint_012_generated_code_over_hard_cap(corpus_root):
    gen_dir = corpus_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / "big.py").write_text("\n".join(f"x{i} = {i}" for i in range(1600)))
    report = run_lint(corpus_root)
    assert has_finding(report, "R-LINT-012")
    assert any("generated_code_loc" in f.message for f in report.findings if f.rule_id == "R-LINT-012")


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
