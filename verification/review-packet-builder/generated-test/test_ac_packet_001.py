# hotdocs-criterion: sha256:f79e8368f2c4124abf0b07612c7cb43e89d92eec8a16e6312115ac73b1fe2bee
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"] + list(args),
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


OLD_LINE = "The foo component stores widgets ORIGINAL_MARKER_7781."
NEW_LINE = "The foo component stores gadgets CHANGED_MARKER_9932."


def _component_md(body_line):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + body_line
        + "\n"
    )


def _verify_report():
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
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
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report,
                "license_scan": {"blocked": False},
                "secret_scan": secret_scan,
            }
        },
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [],
    }


def _write_tracker_stub(repo_root, log_path):
    report = _verify_report()
    source = (
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return " + repr(report) + "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", source)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _git(repo_root, "init")
    _git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo_root, "config", "init.defaultBranch", "main")

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(comp_dir / "component.md", _component_md(OLD_LINE))
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST store things.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen stored\nThen it is kept\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a thing.\n")
    _write_tracker_stub(repo_root, log_path)

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "initial")
    main_sha = _git(repo_root, "rev-parse", "HEAD")

    # Make the default branch discoverable via a remote-tracking ref as well.
    _git(repo_root, "update-ref", "refs/remotes/origin/main", main_sha)
    _git(repo_root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    # The PR: a feature branch changing only this component's component.md.
    _git(repo_root, "checkout", "-b", "feature/change-foo")
    _write(comp_dir / "component.md", _component_md(NEW_LINE))
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "change foo component.md")

    return repo_root


def test_ac_packet_001_spec_diff_contains_component_md_diff(tmp_path):
    repo_root = _build_repo(tmp_path)

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    spec_diff = field(packet, "spec_diff")
    assert isinstance(spec_diff, str)
    assert spec_diff.strip() != ""

    # The diff names the changed file.
    assert "specs/components/foo/component.md" in spec_diff

    # The actual diff text: the added line and the removed line, as
    # unified-diff lines.
    diff_lines = spec_diff.splitlines()
    assert ("+" + NEW_LINE) in diff_lines
    assert ("-" + OLD_LINE) in diff_lines

    # Committed changes are visible (never a bare working-tree-vs-HEAD diff,
    # which would be empty here since everything is committed).
    assert "CHANGED_MARKER_9932" in spec_diff