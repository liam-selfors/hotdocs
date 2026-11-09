import json
import os
import subprocess
from pathlib import Path

import review_packet_builder


GIT_AUTHOR_EMAIL = "test-author@example.invalid"
GIT_AUTHOR_NAME = "Test Author"

SEALED_COMPONENT_BEFORE = """---
id: comp-sealed-foo
title: Sealed Foo
status: ratified
owners: [tester]
sealed: false
source_path: legacy/sealed_foo.py
last_ratified_commit: "0000000000000000000000000000000000000abc"
---

# Sealed Foo

A fixture component used to exercise the sealed-transition detection path.
"""

SEALED_COMPONENT_AFTER = SEALED_COMPONENT_BEFORE.replace(
    "sealed: false", "sealed: true"
)

DECISION_BEFORE = """---
id: D900
title: Placeholder Decision
status: ratified
owners: [tester]
last_ratified_commit: "0000000000000000000000000000000000000abc"
---

# D900: Placeholder Decision

Initial decision text for fixture purposes.
"""

ADDED_SPEC_LINE = "This review-packet line was added by the PR under test."

DECISION_AFTER = DECISION_BEFORE + "\n" + ADDED_SPEC_LINE + "\n"

OVERRIDES_JSON = json.dumps({"files": ["pinned_foo.py"]}, indent=2)

FULL_VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": False,
    "components": {
        "comp-foo": {
            "hit": True,
            "verification_report": {
                "component_id": "comp-foo",
                "criteria": [],
                "requirement_results": {"R-FOO-001": "pass"},
                "interface_drift": False,
                "mutation_score": 0.92,
                "overall": "pass",
            },
            "license_scan": {
                "blocked": True,
                "package": "left-pad",
                "license": "GPL-3.0",
                "reason": "copyleft",
            },
            "secret_scan": {
                "flagged": True,
                "file": "config/secrets.env",
                "pattern": "AWS_SECRET_ACCESS_KEY",
            },
        }
    },
    "capabilities": {
        "P-ZERO-EDIT": {
            "hit": True,
            "capability_scenario_report": {
                "P-ZERO-EDIT": {"overall": "pass", "scenarios": []}
            },
        }
    },
    "not_ready_reasons": ["comp-foo: residual risk present"],
}

EMPTY_VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": True,
    "components": {
        "comp-foo": {
            "hit": True,
            "verification_report": {
                "component_id": "comp-foo",
                "criteria": [],
                "requirement_results": {"R-FOO-001": "pass"},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "pass",
            },
            "license_scan": {"blocked": False},
            "secret_scan": {"flagged": False},
        }
    },
    "capabilities": {},
    "not_ready_reasons": [],
}


def _run_git(args, cwd):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = GIT_AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = GIT_AUTHOR_EMAIL
    env["GIT_COMMITTER_NAME"] = GIT_AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = GIT_AUTHOR_EMAIL
    subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_fake_provenance_tracker(repo_root, verify_report):
    module_path = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, "
        "llm_backend=None):\n"
        "    return " + repr(verify_report) + "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    module_path.write_text(source, encoding="utf-8")


def _build_history_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _run_git(["init", "-q"], repo_root)
    _run_git(["config", "user.email", GIT_AUTHOR_EMAIL], repo_root)
    _run_git(["config", "user.name", GIT_AUTHOR_NAME], repo_root)
    _run_git(["config", "commit.gpgsign", "false"], repo_root)

    _write(
        repo_root / "specs" / "components" / "sealed-foo" / "component.md",
        SEALED_COMPONENT_BEFORE,
    )
    _write(repo_root / "specs" / "decisions" / "D900.md", DECISION_BEFORE)
    _run_git(["add", "-A"], repo_root)
    _run_git(["commit", "-q", "-m", "initial corpus"], repo_root)

    _write(
        repo_root / "specs" / "components" / "sealed-foo" / "component.md",
        SEALED_COMPONENT_AFTER,
    )
    _write(repo_root / "specs" / "decisions" / "D900.md", DECISION_AFTER)
    _write(repo_root / "gen" / "pinned-foo" / ".overrides.json", OVERRIDES_JSON)
    _run_git(["add", "-A"], repo_root)
    _run_git(
        ["commit", "-q", "-m", "seal comp-sealed-foo and pin comp-pinned-foo"],
        repo_root,
    )

    _write_fake_provenance_tracker(repo_root, FULL_VERIFY_REPORT)
    return repo_root


def _build_empty_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _run_git(["init", "-q"], repo_root)
    _run_git(["config", "user.email", GIT_AUTHOR_EMAIL], repo_root)
    _run_git(["config", "user.name", GIT_AUTHOR_NAME], repo_root)
    _run_git(["config", "commit.gpgsign", "false"], repo_root)

    _write(
        repo_root / "specs" / "decisions" / "D901.md",
        DECISION_BEFORE.replace("D900", "D901"),
    )
    _run_git(["add", "-A"], repo_root)
    _run_git(["commit", "-q", "-m", "initial corpus"], repo_root)

    _write_fake_provenance_tracker(repo_root, EMPTY_VERIFY_REPORT)
    return repo_root


def _extract_section(markdown, heading):
    lines = markdown.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    assert start is not None, f"heading {heading!r} not found in:\n{markdown}"
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("#"):
            end = j
            break
    return "\n".join(lines[start:end])


def test_markdown_rendering_contains_real_findings(tmp_path, capsys):
    repo_root = _build_history_repo(tmp_path)

    exit_code = review_packet_builder.main(
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            "--repo-root=" + str(repo_root),
        ]
    )

    captured = capsys.readouterr()
    markdown = captured.out

    assert exit_code == 0

    license_section = _extract_section(markdown, "### License Scan")
    assert "left-pad" in license_section
    assert "comp-foo" in license_section

    secret_section = _extract_section(markdown, "### Secret Scan")
    assert (
        "config/secrets.env" in secret_section
        or "AWS_SECRET_ACCESS_KEY" in secret_section
    )
    assert "comp-foo" in secret_section

    residual_section = _extract_section(markdown, "## Residual Risk")
    assert "0.92" in residual_section
    assert "comp-foo" in residual_section
    assert "pass" in residual_section.lower()

    capability_section = _extract_section(markdown, "## Capability Scenarios")
    assert "P-ZERO-EDIT" in capability_section

    exemption_section = _extract_section(markdown, "## Exemption Changes")
    assert "**Sealed:**" in exemption_section
    assert "comp-sealed-foo" in exemption_section
    assert "**Pinned Overrides:**" in exemption_section
    assert "comp-pinned-foo" in exemption_section

    verification_section = _extract_section(markdown, "## Verification Results")
    assert "comp-foo" in verification_section

    assert ADDED_SPEC_LINE in markdown
    assert "R-FOO-001" in markdown
    assert "comp-foo" in markdown

    hit_status_lines = [
        line
        for line in markdown.splitlines()
        if "comp-foo" in line and ("true" in line.lower() or "false" in line.lower())
    ]
    assert hit_status_lines, (
        "expected provenance hit status to reference comp-foo with a boolean "
        "value somewhere in the rendering"
    )


def test_markdown_rendering_empty_sections_show_placeholders(tmp_path, capsys):
    repo_root = _build_empty_repo(tmp_path)

    exit_code = review_packet_builder.main(
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            "--repo-root=" + str(repo_root),
        ]
    )

    captured = capsys.readouterr()
    markdown = captured.out

    assert exit_code == 0

    license_section = _extract_section(markdown, "### License Scan")
    assert license_section.strip() != ""
    assert "left-pad" not in license_section
    assert "blocked" not in license_section.lower() or "true" not in license_section.lower()

    secret_section = _extract_section(markdown, "### Secret Scan")
    assert secret_section.strip() != ""
    assert "config/secrets.env" not in secret_section
    assert "AWS_SECRET_ACCESS_KEY" not in secret_section

    capability_section = _extract_section(markdown, "## Capability Scenarios")
    assert capability_section.strip() != ""
    assert "P-ZERO-EDIT" not in capability_section

    verification_section = _extract_section(markdown, "## Verification Results")
    assert verification_section.strip() != ""
    assert "comp-foo" in verification_section
    assert "pass" in verification_section.lower()