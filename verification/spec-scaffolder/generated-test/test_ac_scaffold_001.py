# hotdocs-criterion: sha256:7f893a7c0a002e2b9276bc230fdcfdc684a96819cc9db75f633000f91d94363a
from pathlib import Path

import spec_scaffolder


def _decision_text(n):
    return (
        "---\n"
        + "id: " + "D" + str(n) + "\n"
        + "title: " + "Decision " + str(n) + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "---\n"
        + "\n"
        + "# Decision " + str(n) + "\n"
    )


def test_no_decisions_directory_returns_d1(tmp_path):
    repo_root = Path(tmp_path)
    (repo_root / "specs").mkdir()
    assert not (repo_root / "specs" / "decisions").exists()

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D1"


def test_no_specs_directory_at_all_returns_d1(tmp_path):
    repo_root = Path(tmp_path)

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D1"


def test_largest_matching_id_plus_one_ignoring_other_files(tmp_path):
    repo_root = Path(tmp_path)
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)

    for n in (1, 7, 12):
        (decisions / ("D" + str(n) + ".md")).write_text(_decision_text(n), encoding="utf-8")
    (decisions / "README.md").write_text("# Decisions\n", encoding="utf-8")
    (decisions / "D3-notes.md").write_text("Notes about D3.\n", encoding="utf-8")

    result = spec_scaffolder.next_decision_id(repo_root)

    assert result == "D13"