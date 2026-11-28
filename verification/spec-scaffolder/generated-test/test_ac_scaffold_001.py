# hotdocs-criterion: sha256:cf2b2b9471a706fec9738c40c9cb153074843c445e6e5a65facd13a510a62f6a
from pathlib import Path

import spec_scaffolder


def _decision_text(decision_id):
    return (
        "---\n"
        + "id: " + decision_id + "\n"
        + "title: " + "Decision " + decision_id + "\n"
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
    (repo_root / "specs").mkdir()
    assert not (repo_root / "specs" / "decisions").exists()

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D1"


def test_no_specs_directory_at_all_returns_d1(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D1"


def test_largest_matching_id_plus_one_ignoring_other_files(tmp_path):
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
        "# Notes on D3\n\nScratch notes.\n", encoding="utf-8"
    )

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D13"


def test_largest_matching_id_uses_numeric_not_lexical_order(tmp_path):
    repo_root = tmp_path / "repo"
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)

    for decision_id in ("D7", "D12", "D1"):
        (decisions / (decision_id + ".md")).write_text(
            _decision_text(decision_id), encoding="utf-8"
        )
    (decisions / "README.md").write_text("# Decisions\n", encoding="utf-8")
    (decisions / "D3-notes.md").write_text("# Notes\n", encoding="utf-8")

    result = spec_scaffolder.next_decision_id(Path(str(repo_root)))

    assert result == "D13"
    assert result != "D8"