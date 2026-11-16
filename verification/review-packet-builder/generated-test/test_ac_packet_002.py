import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


STAND_IN = '''
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


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root: Path):
    _git(repo_root, "init", "-q")

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n\n"
        "# Foo\n\nA synthetic fixture component.\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nfoo() -> int\n```\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo` MUST return an integer.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven nothing\nWhen foo runs\nThen the result is an integer\n```\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo():\n    return 1\n")
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        STAND_IN,
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "base")

    # The PR: add one new requirement R-FOO-002 (and its covering criterion).
    _write(
        comp_dir / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — `foo` MUST return a positive integer.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "```gherkin\nGiven nothing\nWhen foo runs\nThen the result is greater than 0\n```\n",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add R-FOO-002")


def test_ac_packet_002_changed_requirements_includes_new_requirement(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    packet = review_packet_builder.build_review_packet(["R-FOO-002"], repo_root)

    changed_requirements = field(packet, "changed_requirements")
    assert "R-FOO-002" in list(changed_requirements)