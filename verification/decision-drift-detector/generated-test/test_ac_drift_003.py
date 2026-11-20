# hotdocs-criterion: sha256:b741f5edaff00b3caa31eeba0b118477eef66c6f2dd626715837307151207581
import subprocess
from pathlib import Path

import decision_drift_detector


GIT_CFG = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


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


def normalize(repo_root, p):
    p = Path(str(p))
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(Path(repo_root).resolve())
        except ValueError:
            pass
    return p.as_posix()


def test_ac_drift_003_impact_reports_dependent_and_every_citation(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")

    # First decision.
    write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "The first decision.\n",
    )

    # A live spec component whose requirement cites D1.
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
        "Foo does foo things.\n",
    )
    write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST do the thing, as decided in `D1`.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When it runs\n"
        "Then it does the thing\n"
        "```\n",
    )
    commit_all(repo_root, "first decision and citing spec")

    # Superseding decision, created only after the citation was committed.
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
        "# D2\n"
        "\n"
        "Supersedes the first decision.\n",
    )
    commit_all(repo_root, "superseding decision")

    report = decision_drift_detector.find_decision_impact(repo_root, "D1")

    assert field(report, "decision_id") == "D1"

    dependents = [str(d) for d in field(report, "dependent_decisions")]
    assert "D2" in dependents

    citing = {normalize(repo_root, f) for f in field(report, "citing_files")}
    assert "specs/components/foo/requirements/R-FOO-001.md" in citing