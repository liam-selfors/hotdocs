"""AC-SCAFFOLD-001 (Covers: R-SCAFFOLD-001).

Given a repo_root with no specs/decisions/ directory
When next_decision_id(repo_root) is called
Then it returns "D1"

Given a repo_root whose specs/decisions/ holds D1.md, D7.md, D12.md,
  README.md and D3-notes.md
When next_decision_id(repo_root) is called
Then it returns "D13"
"""

from pathlib import Path

import spec_scaffolder


def _decision_record(decision_id: str) -> str:
    return (
        "---\n"
        f"id: {decision_id}\n"
        f"title: Decision {decision_id}\n"
        "status: draft\n"
        "owners: [unassigned]\n"
        "---\n"
        "\n"
        f"# {decision_id}\n"
        "\n"
        "Body.\n"
    )


def test_no_decisions_directory_returns_d1(tmp_path):
    repo_root = Path(tmp_path)
    assert not (repo_root / "specs" / "decisions").exists()

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D1"


def test_no_decisions_directory_with_specs_present_returns_d1(tmp_path):
    repo_root = Path(tmp_path)
    (repo_root / "specs").mkdir()
    assert not (repo_root / "specs" / "decisions").exists()

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D1"


def test_largest_numbered_record_plus_one_ignoring_other_files(tmp_path):
    repo_root = Path(tmp_path)
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)

    for decision_id in ("D1", "D7", "D12"):
        (decisions / f"{decision_id}.md").write_text(
            _decision_record(decision_id), encoding="utf-8"
        )
    (decisions / "README.md").write_text(
        "# Decisions\n\nIndex of decision records.\n", encoding="utf-8"
    )
    (decisions / "D3-notes.md").write_text(
        "Notes about D3; not a decision record.\n", encoding="utf-8"
    )

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D13"