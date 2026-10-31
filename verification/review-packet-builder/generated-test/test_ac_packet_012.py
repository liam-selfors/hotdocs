import json
import re
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def _git(repo_root, *args):
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True, text=True)


def _init_repo(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "lselfors@gmail.com")
    _git(repo_root, "config", "user.name", "Test User")


def _commit_all(repo_root, message):
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", message)


def _component_md(component_id, title, sealed, source_path=None):
    lines = [
        "---",
        f"id: {component_id}",
        f"title: {title}",
        "status: draft",
        "owners: [lselfors@gmail.com]",
        f"sealed: {'true' if sealed else 'false'}",
    ]
    if source_path:
        lines.append(f"source_path: {source_path}")
    lines.append("---")
    lines.append("")
    lines.append(f"{title} component body.")
    return "\n".join(lines) + "\n"


def _write_fake_provenance_tracker(repo_root, response=None, raise_usage_error=False):
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    if raise_usage_error:
        body = (
            "class UsageError(Exception):\n"
            "    pass\n\n"
            "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
            "    raise UsageError('model required for fresh capability scenario run')\n"
        )
    else:
        body = (
            "class UsageError(Exception):\n"
            "    pass\n\n"
            "_RESPONSE = " + repr(response) + "\n\n"
            "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
            "    return _RESPONSE\n"
        )
    (dep_dir / "provenance_tracker.py").write_text(body)


def _build_baseline_repo(tmp_path, name):
    repo_root = tmp_path / name
    _init_repo(repo_root)
    (repo_root / "README.md").write_text("baseline fixture repo\n")
    _commit_all(repo_root, "initial commit")
    return repo_root


def _build_repo_with_exemption_history(tmp_path, name):
    repo_root = tmp_path / name
    _init_repo(repo_root)

    sealed_dir = repo_root / "specs" / "components" / "sealed-target"
    sealed_dir.mkdir(parents=True, exist_ok=True)
    (sealed_dir / "component.md").write_text(
        _component_md("comp-sealed-target", "Sealed Target", sealed=False)
    )

    pinned_spec_dir = repo_root / "specs" / "components" / "pinned-target"
    pinned_spec_dir.mkdir(parents=True, exist_ok=True)
    (pinned_spec_dir / "component.md").write_text(
        _component_md("comp-pinned-target", "Pinned Target", sealed=True, source_path="legacy/pinned.py")
    )

    (repo_root / "README.md").write_text("exemption fixture repo\n")
    _commit_all(repo_root, "initial commit: unsealed target, pinned target component")

    (sealed_dir / "component.md").write_text(
        _component_md(
            "comp-sealed-target", "Sealed Target", sealed=True, source_path="legacy/sealed_target.py"
        )
    )
    overrides_dir = repo_root / "gen" / "pinned-target"
    overrides_dir.mkdir(parents=True, exist_ok=True)
    (overrides_dir / ".overrides.json").write_text(
        json.dumps({"pinned_file.py": "manual override reason"}) + "\n"
    )
    _commit_all(repo_root, "seal sealed-target and pin an override for pinned-target")

    return repo_root


def _verification_report(mutation_score, overall, criterion_id="AC-FOO-001", requirement="R-FOO-001"):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": criterion_id,
                "covers": requirement,
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {requirement: "pass"},
        "interface_drift": False,
        "mutation_score": mutation_score,
        "overall": overall,
    }


def _extract_section(markdown, heading):
    pattern = re.compile(
        r"^#{1,6}\s*" + re.escape(heading) + r"\s*$\n(.*?)(?=^#{1,6}\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    assert match, f"heading {heading!r} not found in markdown:\n{markdown}"
    return match.group(1)


def test_json_format_renders_real_verification_and_residual_risk_with_empty_exemptions(tmp_path, capsys):
    repo_root = _build_baseline_repo(tmp_path, "repo1")
    response = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report(0.92, "pass"),
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
    _write_fake_provenance_tracker(repo_root, response=response)

    argv = [
        "review-packet",
        "build",
        "--changed=R-FOO-001",
        f"--repo-root={repo_root}",
        "--format=json",
    ]
    exit_code = review_packet_builder.main(argv)
    captured = capsys.readouterr()

    assert exit_code == 0
    packet = json.loads(captured.out)

    assert "comp-foo" in packet["verification_results"]
    verification_text = json.dumps(packet["verification_results"]["comp-foo"])
    assert "AC-FOO-001" in verification_text
    assert "0.92" in verification_text

    assert len(packet["residual_risk"]) >= 1
    residual_text = json.dumps(packet["residual_risk"])
    assert "comp-foo" in residual_text
    assert "0.92" in residual_text

    assert packet["exemption_changes"]["sealed"] == []
    assert packet["exemption_changes"]["pinned_overrides"] == []


def test_markdown_format_renders_real_content_under_own_headings(tmp_path, capsys):
    repo_root = _build_repo_with_exemption_history(tmp_path, "repo2")
    response = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report(0.85, "pass"),
                "license_scan": {
                    "blocked": True,
                    "package": "left-pad",
                    "version": "1.3.0",
                    "license": "GPL-3.0",
                    "file": "vendor/left-pad/index.js",
                },
                "secret_scan": {
                    "flagged": True,
                    "file": "config/secrets.env",
                    "secret_type": "aws_access_key_id",
                    "pattern": "AKIA[0-9A-Z]{16}",
                },
            }
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "capability_id": "P-ZERO-EDIT",
                    "scenario_id": "SCN-1",
                    "result": "pass",
                },
            }
        },
        "not_ready_reasons": [],
    }
    _write_fake_provenance_tracker(repo_root, response=response)

    argv = ["review-packet", "build", "--changed=R-FOO-001", f"--repo-root={repo_root}"]
    exit_code = review_packet_builder.main(argv)
    captured = capsys.readouterr()

    assert exit_code == 0
    markdown = captured.out

    license_section = _extract_section(markdown, "License Scan")
    assert "left-pad" in license_section
    assert license_section.strip() not in ("blocked", "- blocked", "**blocked**")

    secret_section = _extract_section(markdown, "Secret Scan")
    assert "aws_access_key_id" in secret_section
    assert secret_section.strip() not in ("flagged", "- flagged", "**flagged**")

    residual_section = _extract_section(markdown, "Residual Risk")
    assert "comp-foo" in residual_section
    assert "0.85" in residual_section

    capability_section = _extract_section(markdown, "Capability Scenarios")
    assert "P-ZERO-EDIT" in capability_section

    exemption_section = _extract_section(markdown, "Exemption Changes")
    assert "**Sealed:**" in exemption_section
    assert "**Pinned Overrides:**" in exemption_section
    assert "comp-sealed-target" in exemption_section
    assert "comp-pinned-target" in exemption_section
    for line in exemption_section.splitlines():
        assert not line.strip().startswith("###")

    verification_section = _extract_section(markdown, "Verification Results")
    assert "comp-foo" in verification_section
    assert "AC-FOO-001" in verification_section


def test_markdown_format_renders_clean_placeholders_when_zero_flags(tmp_path, capsys):
    repo_root = _build_baseline_repo(tmp_path, "repo3")
    response = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report(
                    1.0, "pass", criterion_id="AC-BAR-001", requirement="R-FOO-001"
                ),
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
    _write_fake_provenance_tracker(repo_root, response=response)

    argv = ["review-packet", "build", "--changed=R-FOO-001", f"--repo-root={repo_root}"]
    exit_code = review_packet_builder.main(argv)
    captured = capsys.readouterr()

    assert exit_code == 0
    markdown = captured.out

    license_section = _extract_section(markdown, "License Scan")
    assert license_section.strip() != ""
    assert "left-pad" not in license_section

    secret_section = _extract_section(markdown, "Secret Scan")
    assert secret_section.strip() != ""
    assert "aws_access_key_id" not in secret_section

    capability_section = _extract_section(markdown, "Capability Scenarios")
    assert capability_section.strip() != ""
    assert "P-ZERO-EDIT" not in capability_section

    verification_section = _extract_section(markdown, "Verification Results")
    assert "comp-foo" in verification_section
    assert "AC-BAR-001" in verification_section


def test_missing_changed_returns_usage_error(tmp_path, capsys):
    repo_root = _build_baseline_repo(tmp_path, "repo4")
    response = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    _write_fake_provenance_tracker(repo_root, response=response)

    argv = ["review-packet", "build", f"--repo-root={repo_root}"]
    exit_code = review_packet_builder.main(argv)

    assert exit_code == 2


def test_invalid_format_returns_usage_error(tmp_path, capsys):
    repo_root = _build_baseline_repo(tmp_path, "repo5")
    response = {
        "scope": "blast-radius",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    _write_fake_provenance_tracker(repo_root, response=response)

    argv = [
        "review-packet",
        "build",
        "--changed=R-FOO-001",
        f"--repo-root={repo_root}",
        "--format=bogus",
    ]
    exit_code = review_packet_builder.main(argv)

    assert exit_code == 2


def test_upstream_usage_error_returns_one(tmp_path, capsys):
    repo_root = _build_baseline_repo(tmp_path, "repo6")
    _write_fake_provenance_tracker(repo_root, raise_usage_error=True)

    argv = ["review-packet", "build", "--changed=R-FOO-001", f"--repo-root={repo_root}"]
    exit_code = review_packet_builder.main(argv)

    assert exit_code == 1