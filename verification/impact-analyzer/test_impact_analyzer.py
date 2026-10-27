"""One test per AC-IMPACT-* criterion in
specs/components/impact-analyzer/acceptance/."""

from pathlib import Path

from conftest import (
    FOO_LIBRARY_V1, FOO_LIBRARY_V2, GUARANTEE_TEMPLATE,
    checkout_new_branch, commit_all, init_git_repo, write_baseline,
)
from impact_analyzer import compute_blast_radius


def test_ac_impact_001_direct_inclusion(git_repo):
    report = compute_blast_radius(["comp-bar"], git_repo)
    by_id = {e.component_id: e for e in report.impacted}
    assert by_id["comp-bar"].reason == "direct"
    assert by_id["comp-bar"].via is None


def test_ac_impact_002_internal_change_does_not_propagate(git_repo):
    (git_repo / "specs" / "components" / "bar" / "constraints.md").write_text(
        "# Bar — Non-Functional Constraints\n\n- **Determinism.** Edited, internal only.\n"
    )
    commit_all(git_repo, "internal edit")
    report = compute_blast_radius(["comp-bar"], git_repo)
    ids = {e.component_id: e.reason for e in report.impacted}
    assert ids.get("comp-bar") == "direct"
    assert "comp-foo" not in ids


def test_ac_impact_003_interface_change_propagates(git_repo):
    (git_repo / "specs" / "components" / "bar" / "interface" / "library.md").write_text(
        "# Library\n\n```\nbar_get(key: str) -> str\nbar_set(key: str, value: str) -> None\n```\n"
    )
    commit_all(git_repo, "interface change")
    report = compute_blast_radius(["comp-bar"], git_repo)
    by_id = {e.component_id: e for e in report.impacted}
    assert by_id["comp-foo"].reason == "transitive-interface"
    assert by_id["comp-foo"].via == "comp-bar"


def test_ac_impact_004_var_change_propagates(git_repo):
    (git_repo / "specs" / "vars" / "foo-url.md").write_text(
        "---\nid: VAR-FOO-URL\ntitle: Foo URL\nstatus: draft\nowners: [test-team]\n---\n\n"
        "# VAR-FOO-URL\n\n- **required:** yes\n- **type:** url\n"
        "- **sensitivity:** non-secret\n- **description:** Changed description.\n"
    )
    commit_all(git_repo, "var change")
    report = compute_blast_radius(["VAR-FOO-URL"], git_repo)
    by_id = {e.component_id: e for e in report.impacted}
    assert by_id["comp-foo"].reason == "transitive-var"
    assert by_id["comp-foo"].via == "VAR-FOO-URL"


def test_ac_impact_005_capability_change_propagates(git_repo):
    (git_repo / "specs" / "product" / "test-capability.md").write_text(
        "---\nid: P-TEST\ntitle: Test Capability\nstatus: draft\nowners: [test-team]\n---\n\n"
        "# Test Capability\n\n## Purpose\n\nChanged purpose text.\n\n"
        "### CS-TEST-001\nCovers: P-TEST\nKind: generated-test\n\n"
        "```gherkin\nGiven a thing\nWhen it happens\nThen it works differently\n```\n"
    )
    commit_all(git_repo, "capability change")
    report = compute_blast_radius(["P-TEST"], git_repo)
    ids = {e.component_id: e.reason for e in report.impacted}
    assert ids.get("comp-foo") == "transitive-capability"
    assert ids.get("comp-bar") == "transitive-capability"


def test_ac_impact_006_deterministic(git_repo):
    report1 = compute_blast_radius(["comp-bar"], git_repo)
    report2 = compute_blast_radius(["comp-bar"], git_repo)
    assert report1.to_dict() == report2.to_dict()


def test_ac_impact_007_fails_closed_on_dangling_reference(git_repo):
    baz_dir = git_repo / "specs" / "components" / "baz"
    (baz_dir / "requirements").mkdir(parents=True)
    (baz_dir / "interface" / "data").mkdir(parents=True)
    (baz_dir / "acceptance").mkdir(parents=True)
    (baz_dir / "component.md").write_text(
        "---\nid: comp-baz\ntitle: Baz\nstatus: draft\nowners: [test-team]\n"
        "depends_on: [comp-does-not-exist]\nrealizes: []\nsealed: false\n---\n\n"
        "# Baz\n\n## Purpose\n\nDangling.\n\n## Scope\n\nIn. Out.\n\n"
        "## Definitions\n\nNo deltas.\n\n## Behavior\n\nSee requirements/.\n\n"
        "## Interfaces\n\nSee interface/.\n\n## Data\n\nSee interface/data/.\n\n"
        "## Acceptance criteria\n\nSee acceptance/.\n\n"
        "## Non-functional constraints\n\nSee constraints.md.\n\n"
        "## Open questions\n\n## Change log\n\n- Initial draft.\n"
    )
    (baz_dir / "requirements" / "R-BAZ-001.md").write_text("# R-BAZ-001\n\n**R-BAZ-001** — Baz MUST exist.\n")
    (baz_dir / "interface" / "library.md").write_text("# Library\n\n```\nnoop() -> None\n```\n")
    (baz_dir / "constraints.md").write_text("# Baz — Non-Functional Constraints\n\n- **Determinism.** MUST.\n")
    (baz_dir / "acceptance" / "AC-BAZ-001.md").write_text(
        "# AC-BAZ-001\n\nCovers: R-BAZ-001\nKind: generated-test\n\n```gherkin\nGiven baz\nWhen noop runs\nThen it works\n```\n"
    )
    commit_all(git_repo, "add dangling baz")

    report = compute_blast_radius(["comp-bar"], git_repo)
    assert report.impacted == []
    assert report.precondition_error is not None


def test_ac_impact_008_guarantee_change_coarse_default(tmp_path):
    write_baseline(tmp_path, bar_guarantees={"G-BAR-001": GUARANTEE_TEMPLATE.format(gid="G-BAR-001")})
    init_git_repo(tmp_path)
    checkout_new_branch(tmp_path, "feature")
    (tmp_path / "specs" / "components" / "bar" / "interface" / "guarantees" / "G-BAR-001.md").write_text(
        GUARANTEE_TEMPLATE.format(gid="G-BAR-001") + "\nChanged.\n"
    )
    commit_all(tmp_path, "guarantee change")

    report = compute_blast_radius(["comp-bar"], tmp_path)
    by_id = {e.component_id: e for e in report.impacted}
    assert by_id["comp-foo"].reason == "transitive-guarantee"
    assert by_id["comp-foo"].via == "comp-bar"
    assert by_id["comp-foo"].guarantee_ids == ["G-BAR-001"]


def test_ac_impact_008b_narrowed_declaration_excludes_unclaimed_guarantee(tmp_path):
    write_baseline(
        tmp_path,
        bar_guarantees={
            "G-BAR-001": GUARANTEE_TEMPLATE.format(gid="G-BAR-001"),
            "G-BAR-002": GUARANTEE_TEMPLATE.format(gid="G-BAR-002"),
        },
        foo_depends_on_guarantees=["G-BAR-001"],
    )
    init_git_repo(tmp_path)
    checkout_new_branch(tmp_path, "feature")
    (tmp_path / "specs" / "components" / "bar" / "interface" / "guarantees" / "G-BAR-002.md").write_text(
        GUARANTEE_TEMPLATE.format(gid="G-BAR-002") + "\nChanged.\n"
    )
    commit_all(tmp_path, "change unclaimed guarantee")

    report = compute_blast_radius(["comp-bar"], tmp_path)
    ids = {e.component_id for e in report.impacted}
    assert "comp-foo" not in ids


def test_ac_impact_008c_narrowed_declaration_includes_claimed_guarantee(tmp_path):
    write_baseline(
        tmp_path,
        bar_guarantees={
            "G-BAR-001": GUARANTEE_TEMPLATE.format(gid="G-BAR-001"),
            "G-BAR-002": GUARANTEE_TEMPLATE.format(gid="G-BAR-002"),
        },
        foo_depends_on_guarantees=["G-BAR-001"],
    )
    init_git_repo(tmp_path)
    checkout_new_branch(tmp_path, "feature")
    (tmp_path / "specs" / "components" / "bar" / "interface" / "guarantees" / "G-BAR-001.md").write_text(
        GUARANTEE_TEMPLATE.format(gid="G-BAR-001") + "\nChanged.\n"
    )
    commit_all(tmp_path, "change claimed guarantee")

    report = compute_blast_radius(["comp-bar"], tmp_path)
    by_id = {e.component_id: e for e in report.impacted}
    assert by_id["comp-foo"].reason == "transitive-guarantee"
    assert by_id["comp-foo"].guarantee_ids == ["G-BAR-001"]


def test_ac_impact_009_no_precomputed_graph_artifact_required(git_repo):
    assert not list(git_repo.rglob("corpus-graph.json"))
    (git_repo / "specs" / "components" / "bar" / "interface" / "library.md").write_text(
        "# Library\n\n```\nbar_get(key: str) -> str\nbar_delete(key: str) -> None\n```\n"
    )
    commit_all(git_repo, "interface change")
    report = compute_blast_radius(["comp-bar"], git_repo)
    ids = {e.component_id: e.reason for e in report.impacted}
    assert ids.get("comp-foo") == "transitive-interface"
    assert not list(git_repo.rglob("corpus-graph.json"))


def test_ac_impact_010_uses_merge_base_not_head_minus_one(tmp_path):
    """The real change happens between the merge-base (A) and the next
    commit (B); a third commit (C) touches something unrelated. Comparing
    against HEAD~1 (B, already at V2) would wrongly see no change;
    comparing against the merge-base (A, still V1) correctly does."""
    write_baseline(tmp_path)
    init_git_repo(tmp_path)  # commit A, on main
    checkout_new_branch(tmp_path, "feature")

    (tmp_path / "specs" / "components" / "bar" / "interface" / "library.md").write_text(
        "# Library\n\n```\nbar_get(key: str) -> str\nbar_new(key: str) -> None\n```\n"
    )
    commit_all(tmp_path, "commit B: the real interface change")

    (tmp_path / "specs" / "components" / "bar" / "requirements" / "R-BAR-001.md").write_text(
        "# R-BAR-001\n\n**R-BAR-001** — Bar MUST cache things. Clarified wording.\n"
    )
    commit_all(tmp_path, "commit C: unrelated internal edit")

    report = compute_blast_radius(["comp-bar"], tmp_path)
    by_id = {e.component_id: e for e in report.impacted}
    assert by_id["comp-foo"].reason == "transitive-interface"
