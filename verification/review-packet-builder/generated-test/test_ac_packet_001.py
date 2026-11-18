# hotdocs-criterion: sha256:3d7a40232fa926d9fc4494192105892f893b3130e9a280d93c631e565ccf6985
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result.stdout


OLD_LINE = "Original purpose sentence for the foo component."
NEW_LINE = "Revised purpose sentence describing widget handling in foo."


def component_md(body_line):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        + body_line
        + "\n"
    )


def write_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(component_md(OLD_LINE))
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the thing.\n"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does the thing\n```\n"
    )
    (comp / "interface" / "library.md").write_text("# Library\n\n```\nfoo() -> None\n```\n")

    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "mutation_error": None,
        "overall": "pass",
    }
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": verification_report,
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    source = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return " + repr(report) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (tracker_dir / "provenance_tracker.py").write_text(source)


def test_spec_diff_contains_actual_component_md_diff(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")
    git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo_root, "config", "user.name", "Test")
    git(repo_root, "config", "user.email", "test@example.com")
    git(repo_root, "config", "commit.gpgsign", "false")

    write_fixture(repo_root)
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")

    # Make "main" unambiguously the default branch via an origin remote.
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    git(repo_root, "remote", "add", "origin", str(origin))
    git(repo_root, "push", "-q", "origin", "main")
    git(repo_root, "remote", "set-head", "origin", "main")

    # The PR: a feature branch changing one component's component.md.
    git(repo_root, "checkout", "-q", "-b", "feature")
    md = repo_root / "specs" / "components" / "foo" / "component.md"
    md.write_text(component_md(NEW_LINE))
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "change foo component.md")

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)
    spec_diff = field(packet, "spec_diff")

    assert isinstance(spec_diff, str)
    assert spec_diff.strip() != ""
    assert "specs/components/foo/component.md" in spec_diff
    diff_lines = spec_diff.splitlines()
    assert ("+" + NEW_LINE) in diff_lines
    assert ("-" + OLD_LINE) in diff_lines