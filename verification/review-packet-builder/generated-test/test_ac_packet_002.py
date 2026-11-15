import os
import subprocess
import textwrap
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PROVENANCE_TRACKER_STANDIN = textwrap.dedent(
    '''
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
                            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
                            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
                        ],
                        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
                        "interface_drift": False,
                        "mutation_score": None,
                        "overall": "pass",
                    },
                    "license_scan": {"blocked": False},
                    "secret_scan": {"flagged": False},
                },
            },
            "capabilities": {},
            "not_ready_reasons": [],
        }


    def last_requirement_failures(component_id, repo_root):
        return []
    '''
).lstrip()


COMPONENT_MD = textwrap.dedent(
    """
    ---
    id: comp-foo
    title: Foo
    status: draft
    owners: [test-owner]
    sealed: true
    source_path: legacy/foo/
    ---

    # Foo

    A synthetic fixture component.
    """
).lstrip()


def _build_repo(repo_root: Path):
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q")

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(comp_dir / "component.md", COMPONENT_MD)
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the first thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen the first thing happens\n```\n",
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        PROVENANCE_TRACKER_STANDIN,
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    # The PR: add one new requirement R-FOO-002 (and its criterion).
    _write(
        comp_dir / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — Foo MUST do the second thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen the second thing happens\n```\n",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add R-FOO-002")


def test_changed_requirements_includes_new_requirement(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)

    changed_ids = ["comp-foo", "R-FOO-002", "AC-FOO-002"]
    packet = review_packet_builder.build_review_packet(changed_ids, repo_root)

    changed_requirements = list(field(packet, "changed_requirements"))
    assert "R-FOO-002" in changed_requirements
    # changed_requirements is the R-id-shaped subset of changed_ids only.
    assert "comp-foo" not in changed_requirements
    assert "AC-FOO-002" not in changed_requirements