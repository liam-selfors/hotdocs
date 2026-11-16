"""AC-PACKET-001 (Covers: R-PACKET-001).

Given a PR changing one component's component.md
When build_review_packet runs
Then spec_diff contains the actual diff text for that file
"""

import subprocess
import textwrap
from pathlib import Path

import pytest

import review_packet_builder


OLD_LINE = "Foo performs the ORIGINAL-BEHAVIOUR-MARKER-7f3a operation."
NEW_LINE = "Foo performs the REVISED-BEHAVIOUR-MARKER-9c1d operation."
UNCHANGED_LINE = "This sentence is unchanged context for the diff."

COMPONENT_REL = "specs/components/foo/component.md"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed: {result.stdout}\n{result.stderr}"
    )
    return result.stdout


def _component_md(body_line):
    return textwrap.dedent(
        f"""\
        ---
        id: comp-foo
        title: Foo
        status: draft
        owners: [test-owner]
        depends_on: []
        sealed: true
        source_path: legacy/foo/
        ---

        # Foo

        {body_line}

        {UNCHANGED_LINE}
        """
    )


VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": True,
    "components": {
        "comp-foo": {
            "hit": True,
            "verification_report": {
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
                "overall": "pass",
            },
            "license_scan": {"blocked": False, "findings": []},
            "secret_scan": {"flagged": False, "findings": []},
        }
    },
    "capabilities": {},
    "not_ready_reasons": [],
}


def _write_provenance_tracker_stand_in(repo_root):
    path = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "_REPORT = " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    import copy\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def _write_base_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)

    (comp_dir / "component.md").write_text(_component_md(OLD_LINE))
    (comp_dir / "constraints.md").write_text("# Constraints\n\nNone.\n")
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do its thing.\n"
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        textwrap.dedent(
            """\
            # AC-FOO-001

            Covers: R-FOO-001
            Kind: compiled

            ```gherkin
            Given foo
            When it runs
            Then it does its thing
            ```
            """
        )
    )
    (comp_dir / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo() -> None\n```\n"
    )

    legacy = repo_root / "legacy" / "foo"
    legacy.mkdir(parents=True)
    (legacy / "foo.py").write_text("def foo():\n    return None\n")

    _write_provenance_tracker_stand_in(repo_root)


@pytest.fixture
def pr_repo(tmp_path):
    origin = tmp_path / "origin.git"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _git(tmp_path, "init", "--bare", str(origin))

    _git(repo_root, "init")
    _git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo_root, "config", "user.name", "Test User")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "commit.gpgsign", "false")
    _git(repo_root, "config", "init.defaultBranch", "main")

    _write_base_fixture(repo_root)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "base: add comp-foo")

    # Make the default branch discoverable via a remote, as in a real PR.
    _git(repo_root, "remote", "add", "origin", str(origin))
    _git(repo_root, "push", "origin", "main")
    _git(repo_root, "fetch", "origin")
    _git(
        repo_root,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
    )

    # The PR: a feature branch changing only comp-foo's component.md.
    _git(repo_root, "checkout", "-b", "feature/change-foo")
    (repo_root / COMPONENT_REL).write_text(_component_md(NEW_LINE))
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "change comp-foo component.md")

    # Sanity: everything is committed, so a working-tree-vs-HEAD diff is empty.
    assert _git(repo_root, "status", "--porcelain").strip() == ""
    assert _git(repo_root, "diff", "HEAD", "--", "specs/").strip() == ""

    return repo_root


def test_spec_diff_contains_actual_diff_for_changed_component_md(pr_repo):
    repo_root = pr_repo

    # Reference diff the test itself computes (merge-base..HEAD over specs/).
    base = _git(repo_root, "merge-base", "HEAD", "main").strip()
    reference = _git(repo_root, "diff", base, "HEAD", "--", "specs/")
    assert f"-{OLD_LINE}" in reference and f"+{NEW_LINE}" in reference

    packet = review_packet_builder.build_review_packet(["comp-foo"], Path(repo_root))

    spec_diff = field(packet, "spec_diff")
    assert isinstance(spec_diff, str)
    assert spec_diff.strip() != ""

    # The diff names the changed file.
    assert "components/foo/component.md" in spec_diff

    # The diff carries the actual removed and added lines of that file.
    assert f"-{OLD_LINE}" in spec_diff
    assert f"+{NEW_LINE}" in spec_diff

    # Unchanged lines are never presented as removed or added.
    assert f"-{UNCHANGED_LINE}" not in spec_diff
    assert f"+{UNCHANGED_LINE}" not in spec_diff

    # Every changed line of the reference diff appears in spec_diff.
    for line in reference.splitlines():
        if (line.startswith("+") or line.startswith("-")) and not (
            line.startswith("+++") or line.startswith("---")
        ):
            assert line in spec_diff, f"missing diff line: {line!r}"