import json
from pathlib import Path

import pytest

import corpus_graph_builder
from corpus_graph_builder import cli


def _write_component_a(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "a"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/a/\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "---\n"
        "\n"
        "# Component A\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Does something simple for testing.\n",
        encoding="utf-8",
    )


def _assert_prints_path(printed: str, expected_path: Path, cwd: Path) -> None:
    lines = [line for line in printed.strip().splitlines() if line.strip()]
    assert lines, "expected main() to print the written path"
    printed_path = Path(lines[-1].strip())
    if not printed_path.is_absolute():
        printed_path = cwd / printed_path
    assert printed_path.resolve() == expected_path.resolve()


def test_build_succeeds_with_each_repo_root_form(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component_a(repo_root)

    expected_path = repo_root / "verification" / "corpus-graph.json"
    original_cwd = Path.cwd()

    rc = cli.main(["build", "--repo-root=" + str(repo_root)])
    assert rc == 0
    assert expected_path.is_file()
    data = json.loads(expected_path.read_text(encoding="utf-8"))
    assert "nodes" in data
    assert "edges" in data
    assert "aggregates" in data
    _assert_prints_path(capsys.readouterr().out, expected_path, original_cwd)

    expected_path.unlink()

    rc = cli.main(["build", "--repo-root", str(repo_root)])
    assert rc == 0
    assert expected_path.is_file()
    _assert_prints_path(capsys.readouterr().out, expected_path, original_cwd)

    expected_path.unlink()

    monkeypatch.chdir(repo_root)
    rc = cli.main(["build"])
    assert rc == 0
    assert expected_path.is_file()
    _assert_prints_path(capsys.readouterr().out, expected_path, repo_root)


def test_build_returns_1_on_invalid_provenance_json(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component_a(repo_root)

    verification_a = repo_root / "verification" / "a"
    verification_a.mkdir(parents=True, exist_ok=True)
    (verification_a / ".provenance.json").write_text("{not json", encoding="utf-8")

    rc = cli.main(["build", "--repo-root=" + str(repo_root)])
    assert rc == 1


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["serve"],
        ["build", "--bogus"],
        ["build", "--repo-root"],
    ],
)
def test_usage_errors_return_2_without_raising(argv):
    rc = cli.main(argv)
    assert rc == 2