import os
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


ORIGINAL_LINE = "Original description line for foo, as it stood on main."
UPDATED_LINE = "Updated description line for foo, revised in this PR."
COMPONENT_REL = "specs/components/foo/component.md"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(cwd, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Test Author",
            "GIT_COMMITTER_EMAIL": "author@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    cmd = [
        "git",
        "-c", "user.name=Test Author",
        "-c", "user.email=author@example.invalid",
        "-c", "commit.gpgsign=false",
        "-c", "tag.gpgsign=false",
        "-c", "init.defaultBranch=main",
        *args,
    ]
    result = subprocess.run(
        cmd, cwd=str(cwd), env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    return result.stdout


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
        f"{body_line}\n"
        "\n"
        "Another stable paragraph that does not change.\n"
    )


PROVENANCE_TRACKER_STANDIN = '''\
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": None,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo_root(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init")
    git(upstream, "symbolic-ref", "HEAD", "refs/heads/main")

    write(upstream / COMPONENT_REL, component_md(ORIGINAL_LINE))
    write(
        upstream / "specs/components/foo/requirements/R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do the foo thing.\n",
    )
    write(
        upstream / "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo happens\n```\n",
    )
    write(upstream / "specs/components/foo/constraints.md", "No constraints.\n")
    write(
        upstream / "gen/provenance-tracker/provenance_tracker.py",
        PROVENANCE_TRACKER_STANDIN,
    )
    git(upstream, "add", "-A")
    git(upstream, "commit", "-m", "initial corpus")

    repo = tmp_path / "repo"
    git(tmp_path, "clone", str(upstream), str(repo))
    git(repo, "config", "user.name", "Test Author")
    git(repo, "config", "user.email", "author@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")

    # The PR: a feature branch changing exactly one component's component.md.
    git(repo, "checkout", "-b", "feature/change-foo")
    write(repo / COMPONENT_REL, component_md(UPDATED_LINE))
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "change foo component.md")

    # Sanity: the working tree is clean, so a bare working-tree-vs-HEAD
    # diff would be empty.
    assert git(repo, "status", "--porcelain").strip() == ""
    return repo


def test_spec_diff_contains_actual_diff_text_for_changed_component_md(repo_root):
    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    spec_diff = field(packet, "spec_diff")
    assert isinstance(spec_diff, str)
    assert spec_diff.strip() != "", "spec_diff must not be empty for a committed PR change"

    assert COMPONENT_REL in spec_diff, (
        f"spec_diff should name the changed file {COMPONENT_REL!r}; got:\n{spec_diff}"
    )

    lines = spec_diff.splitlines()
    assert ("+" + UPDATED_LINE) in lines, (
        f"spec_diff should contain the added line; got:\n{spec_diff}"
    )
    assert ("-" + ORIGINAL_LINE) in lines, (
        f"spec_diff should contain the removed line (diff vs merge-base with main); got:\n{spec_diff}"
    )