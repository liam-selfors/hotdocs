# hotdocs-criterion: sha256:4c36b0a57074df469094d0b6e368f75e2db986922e6480a7b726f1b62bb8cba3
from pathlib import Path

import spec_scaffolder


def _decision_text(decision_id):
    return (
        "---\n"
        + "id: " + decision_id + "\n"
        + "title: Decision " + decision_id + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "---\n"
        + "\n"
        + "# " + decision_id + "\n"
        + "\n"
        + "Body.\n"
    )


def test_no_decisions_directory_returns_d1(tmp_path):
    repo_root = Path(tmp_path)
    assert not (repo_root / "specs" / "decisions").exists()

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D1"


def test_largest_exact_decision_file_plus_one_ignoring_others(tmp_path):
    repo_root = Path(tmp_path)
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)

    for decision_id in ("D1", "D7", "D12"):
        (decisions / (decision_id + ".md")).write_text(
            _decision_text(decision_id), encoding="utf-8"
        )
    (decisions / "README.md").write_text(
        "# Decisions\n\nIndex of decision records.\n", encoding="utf-8"
    )
    (decisions / "D3-notes.md").write_text(
        "Notes about D3.\n", encoding="utf-8"
    )

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D13"