# hotdocs-criterion: sha256:b578aa57d93d24cd4161e4f3df9de532ddf1165fdd70c6d2c369e8a6ec36f030
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    cmd = [
        "git",
        "-c", "user.name=Test",
        "-c", "user.email=test@example.com",
        "-c", "commit.gpgsign=false",
        "-c", "core.autocrlf=false",
    ] + list(args)
    result = subprocess.run(
        cmd, cwd=str(repo_root), capture_output=True, text=True
    )
    assert result.returncode == 0, (cmd, result.stdout, result.stderr)
    return result.stdout


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ORIGINAL_LINE = "The foo component does the original foo thing."
ADDED_LINE = "The foo component now also does a brand new foo thing."


def component_md(body_lines):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + "\n".join(body_lines)
        + "\n"
    )


def tracker_source():
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
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
            }
        },
        "capabilities": {},
        "secret_scan": secret_scan,
        "not_ready_reasons": [],
    }
    return (
        "REPORT = " + repr(report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def build_repo(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)
    git(repo_root, "init")
    git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo_root, "config", "init.defaultBranch", "main")

    comp_dir = repo_root / "specs" / "components" / "foo"
    write(comp_dir / "component.md", component_md([ORIGINAL_LINE]))
    write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the foo thing.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo happens\n```\n",
    )
    write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        tracker_source(),
    )
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "initial")

    git(repo_root, "checkout", "-b", "feature")
    write(comp_dir / "component.md", component_md([ORIGINAL_LINE, ADDED_LINE]))
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "change foo component.md")


def test_ac_packet_001_spec_diff_contains_component_md_diff(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    spec_diff = field(packet, "spec_diff")
    assert isinstance(spec_diff, str)
    assert spec_diff.strip() != ""
    assert "specs/components/foo/component.md" in spec_diff
    diff_lines = spec_diff.splitlines()
    assert ("+" + ADDED_LINE) in diff_lines, spec_diff