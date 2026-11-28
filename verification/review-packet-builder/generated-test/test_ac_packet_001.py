# hotdocs-criterion: sha256:f44c39a396676155d4b4b28bc7dc7f81808b20be6eb765f987311a92484220ba
import os
import subprocess
from pathlib import Path

import review_packet_builder


ADDED_LINE = "This purpose sentence was added by the pull request under review."
COMPONENT_REL = "specs/components/foo/component.md"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "Test Author",
        "GIT_AUTHOR_EMAIL": "author@example.invalid",
        "GIT_COMMITTER_NAME": "Test Author",
        "GIT_COMMITTER_EMAIL": "author@example.invalid",
        "GIT_CONFIG_NOSYSTEM": "1",
    })
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"] + list(args),
        cwd=str(repo),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def component_md(extra_line):
    text = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [foo-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small, well-defined thing.\n"
    )
    if extra_line:
        text += "\n" + extra_line + "\n"
    return text


def write_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "component.md").write_text(component_md(None))
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do its thing.\n"
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does its thing\n```\n"
    )


def write_provenance_tracker_stand_in(repo_root):
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }
    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report,
                "license_scan": {"blocked": False},
                "secret_scan": secret_scan,
            },
        },
        "capabilities": {},
        "secret_scan": secret_scan,
        "not_ready_reasons": [],
    }
    source = (
        "import copy\n"
        "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    target = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source)


def test_ac_packet_001_spec_diff_contains_component_md_diff(tmp_path):
    origin = tmp_path / "origin.git"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    git(tmp_path, "init", "--bare", str(origin))
    git(repo_root, "init")
    git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")

    write_fixture(repo_root)
    write_provenance_tracker_stand_in(repo_root)
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "initial corpus")

    git(repo_root, "remote", "add", "origin", str(origin))
    git(repo_root, "push", "origin", "main")
    git(repo_root, "remote", "set-head", "origin", "main")

    # The PR: a feature branch whose one commit changes foo's component.md.
    git(repo_root, "checkout", "-b", "feature/foo-purpose")
    (repo_root / COMPONENT_REL).write_text(component_md(ADDED_LINE))
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "change foo component.md")

    # Everything is committed: a bare working-tree-vs-HEAD diff would be empty.
    assert git(repo_root, "status", "--porcelain").strip() == ""

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    spec_diff = field(packet, "spec_diff")
    assert isinstance(spec_diff, str)
    assert spec_diff.strip() != ""
    assert "components/foo/component.md" in spec_diff
    assert "+" + ADDED_LINE in spec_diff