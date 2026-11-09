import os
import subprocess
import tempfile
from pathlib import Path

import review_packet_builder


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _run_git(args, cwd):
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
        ["git"] + args,
        cwd=cwd,
        check=True,
        capture_output=True,
        env=env,
    )


def _write_provenance_tracker_stand_in(repo_root):
    module_dir = repo_root / "gen" / "provenance-tracker"
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "provenance_tracker.py").write_text(
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {\n"
        '        "scope": "blast-radius",\n'
        '        "ready": True,\n'
        '        "components": {},\n'
        '        "capabilities": {},\n'
        '        "not_ready_reasons": [],\n'
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def _write_foo_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)

    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "owners: [lselfors]\n"
        "sealed: true\n"
        "source_path: src/foo.py\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fake sealed component used as a test fixture.\n"
    )

    (comp_dir / "requirements" / "R-FOO-002.md").write_text(
        "**R-FOO-002** -- The widget MUST do the fake thing.\n"
    )

    (comp_dir / "acceptance" / "AC-FOO-002.md").write_text(
        "Covers: R-FOO-002\n"
        "\n"
        "```gherkin\n"
        "Given a fake widget\n"
        "When it does the fake thing\n"
        "Then it succeeds\n"
        "```\n"
    )


def test_changed_requirements_includes_new_requirement():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        _run_git(["init"], cwd=repo_root)
        (repo_root / "README.md").write_text("initial\n")
        _run_git(["add", "."], cwd=repo_root)
        _run_git(["commit", "-m", "initial commit"], cwd=repo_root)

        _write_provenance_tracker_stand_in(repo_root)
        _write_foo_fixture(repo_root)

        _run_git(["add", "."], cwd=repo_root)
        _run_git(["commit", "-m", "add R-FOO-002"], cwd=repo_root)

        packet = review_packet_builder.build_review_packet(["R-FOO-002"], repo_root)

        changed_requirements = _get(packet, "changed_requirements")
        assert changed_requirements is not None
        assert "R-FOO-002" in changed_requirements