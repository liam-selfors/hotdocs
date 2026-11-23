# hotdocs-criterion: sha256:531972e9d7423d1f0bfa4d47108beca9cbd43937369f83504ba3ab01f69d9733
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
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert not (repo_root / "specs" / "decisions").exists()

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D1"


def test_returns_one_past_largest_exact_decision_file(tmp_path):
    repo_root = tmp_path / "repo"
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
        "# Notes on D3\n\nScratch notes, not a decision record.\n",
        encoding="utf-8",
    )

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D13"