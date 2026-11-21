# hotdocs-criterion: sha256:099caab45e19fbfeae8648a4ef0d4b478ebf58bd248978dc8538fa7e0ac43035
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


OLD_LINE = "Original purpose line for the foo component."
NEW_LINE = "Revised purpose line introduced by this PR for AC-PACKET-001."
COMPONENT_REL = "specs/components/foo/component.md"


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test Author",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _component_md(purpose_line):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo Component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose_line
        + "\n"
    )


def _verify_report():
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
    }
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report,
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _write_tracker_stand_in(repo_root):
    path = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    path.write_text(source)


def _build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "component.md").write_text(_component_md(OLD_LINE))
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the foo thing.\n"
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo happens\n```\n"
    )
    (comp_dir / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo() -> None\n```\n"
    )
    _write_tracker_stand_in(repo_root)


def test_spec_diff_contains_actual_component_md_diff(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _git(repo_root, "init", "-q")
    _git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")
    _build_fixture(repo_root)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial corpus")

    # Make the default branch discoverable via a remote-tracking ref too.
    _git(repo_root, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(
        repo_root,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
    )

    # The PR: a feature branch changing one component's component.md.
    _git(repo_root, "checkout", "-q", "-b", "feature/foo-change")
    (repo_root / COMPONENT_REL).write_text(_component_md(NEW_LINE))
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "change foo component.md")

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)
    spec_diff = field(packet, "spec_diff")

    assert isinstance(spec_diff, str)
    assert spec_diff.strip() != ""
    # The diff names the changed file.
    assert COMPONENT_REL in spec_diff
    # The diff carries the actual added content of that file.
    assert ("+" + NEW_LINE) in spec_diff

    # Merge-base(HEAD, main) differs from HEAD here, so the diff is
    # merge-base..HEAD: it shows the removed line as well.
    expected = _git(
        repo_root, "diff", "main", "HEAD", "--", "specs/"
    )
    assert ("-" + OLD_LINE) in expected
    assert ("-" + OLD_LINE) in spec_diff