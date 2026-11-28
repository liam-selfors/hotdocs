# hotdocs-criterion: sha256:e3f247e6d8ad758aa034083757f505ab18c7b5995405dc9eb7831db3ca7c1bea
import subprocess
from pathlib import Path

import decision_drift_detector


GIT_CFG = [
    "-c", "user.name=t",
    "-c", "user.email=t@t",
    "-c", "commit.gpgsign=false",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    return subprocess.run(
        ["git"] + GIT_CFG + list(args),
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def commit_all(repo_root, message):
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", message)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def normalize_path(repo_root, value):
    p = Path(str(value))
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(Path(repo_root).resolve())
        except ValueError:
            pass
    return p.as_posix()


def test_ac_drift_003_impact_reports_dependents_and_all_citations(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")

    # First decision, D1.
    write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D1\n",
    )

    # A live component whose requirement file cites D1.
    comp_dir = repo_root / "specs" / "components" / "foo"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    citing_rel = "specs/components/foo/requirements/R-FOO-001.md"
    write(
        repo_root / citing_rel,
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** - Foo MUST behave as decided in `D1`.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n",
    )
    commit_all(repo_root, "D1 and citing spec")

    # Second decision, D2, superseding D1, committed after the citation.
    write(
        repo_root / "specs" / "decisions" / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Second decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "supersedes: D1\n"
        "---\n"
        "\n"
        "# D2\n",
    )
    commit_all(repo_root, "D2 supersedes D1")

    report = decision_drift_detector.find_decision_impact(repo_root, "D1")

    assert str(field(report, "decision_id")) == "D1"

    dependents = [str(d) for d in field(report, "dependent_decisions")]
    assert "D2" in dependents

    citing = [normalize_path(repo_root, f) for f in field(report, "citing_files")]
    assert citing_rel in citing