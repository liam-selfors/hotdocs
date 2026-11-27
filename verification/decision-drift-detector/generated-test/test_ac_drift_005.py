# hotdocs-criterion: sha256:897d50899bfae81e73a8213bbbf86ae7b2be1d7783b12b2139e7004258c918c7
"""AC-DRIFT-005: main(argv) implements interface/cli.md (R-DRIFT-005)."""

import json
import subprocess
from pathlib import Path

import pytest

import decision_drift_detector


GIT_FLAGS = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def git(repo_root, *args):
    return subprocess.run(
        ["git"] + GIT_FLAGS + list(args),
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        + "id: D1\n"
        + "title: First decision\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# D1\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Foo does foo, as D1 describes.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        + "\n"
        + "**R-FOO-001** \u2014 The component MUST do foo (`D1`).\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        + "\n"
        + "Covers: R-FOO-001\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given foo\n"
        + "When foo runs\n"
        + "Then it does foo\n"
        + "```\n",
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")
    build_corpus(repo_root)
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial corpus")
    return repo_root


def test_decision_drift_json_on_clean_repo_returns_0_with_empty_entries(repo, capsys):
    rc = decision_drift_detector.main(
        ["decision-drift", "--repo-root=" + str(repo), "--format=json"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    report = json.loads(out)
    assert field(report, "entries") == []


def test_decision_impact_text_returns_0_and_prints_human_readable_report(repo, capsys):
    rc = decision_drift_detector.main(
        ["decision-impact", "D1", "--repo-root=" + str(repo)]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() != ""
    assert "D1" in out


def test_decision_impact_missing_decision_id_returns_2(repo, capsys):
    rc = decision_drift_detector.main(
        ["decision-impact", "--repo-root=" + str(repo)]
    )
    capsys.readouterr()
    assert rc == 2


def test_decision_drift_on_non_git_path_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    not_repo = tmp_path / "not-a-repo"
    not_repo.mkdir()
    build_corpus(not_repo)
    rc = decision_drift_detector.main(
        ["decision-drift", "--repo-root=" + str(not_repo)]
    )
    capsys.readouterr()
    assert rc == 2


def test_decision_drift_defaults_repo_root_to_cwd_git_root(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    rc = decision_drift_detector.main(["decision-drift"])
    capsys.readouterr()
    assert rc == 0


def test_decision_drift_bogus_format_returns_2(repo, capsys):
    rc = decision_drift_detector.main(
        ["decision-drift", "--repo-root=" + str(repo), "--format=bogus"]
    )
    capsys.readouterr()
    assert rc == 2