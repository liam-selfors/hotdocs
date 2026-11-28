# hotdocs-criterion: sha256:2683d158eeef9b252e50955b81bd990441520abcb5789c42daa92407e0f4a4bf
import os
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


CLEAN_LICENSE = {"blocked": False, "matches": []}

CLEAN_SECRET = {
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

FLAGGED_COMPONENT_SECRET = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": True,
    "matches": [
        {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "legacy/foo/x.py", "line": 7}
    ],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

FLAGGED_REPO_SECRET = {
    "flagged": True,
    "matches": [
        {"file": "a/b.py", "line": 3, "rule_id": "AWS Access Key", "risk_tier": "high"}
    ],
}


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }


def _component_result(stored_secret_scan):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(),
        "license_scan": dict(CLEAN_LICENSE),
        "secret_scan": stored_secret_scan,
    }


def _verify_report(component_secret_scan, repo_secret_scan):
    return {
        "scope": "blast-radius",
        "ready": not bool(repo_secret_scan and repo_secret_scan.get("flagged"))
        and not bool(component_secret_scan.get("flagged")),
        "components": {"comp-foo": _component_result(component_secret_scan)},
        "capabilities": {},
        "secret_scan": repo_secret_scan,
        "not_ready_reasons": [],
    }


def _git(repo_root, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root, verify_report):
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
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
        "A fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do its job.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: llm-judge\n\nFoo does its job.\n\nCovers: R-FOO-001\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "VALUE = 1\n")

    source = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return " + repr(verify_report) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", source)

    _git(repo_root, "init")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")


def _compliance_flags(tmp_path, component_secret_scan, repo_secret_scan):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, _verify_report(component_secret_scan, repo_secret_scan))
    packet = review_packet_builder.build_review_packet(["R-FOO-001"], repo_root)
    assert _has_field(packet, "compliance_flags")
    flags = field(packet, "compliance_flags")
    assert flags is not None
    return flags


def test_clean_scans_give_explicit_empty_sections(tmp_path):
    flags = _compliance_flags(tmp_path, dict(CLEAN_SECRET), dict(CLEAN_SECRET))
    assert _has_field(flags, "license_scan")
    assert _has_field(flags, "secret_scan")
    license_scan = field(flags, "license_scan")
    secret_scan = field(flags, "secret_scan")
    assert license_scan is not None
    assert secret_scan is not None
    assert list(license_scan) == []
    assert list(secret_scan) == []


def test_component_stored_secret_scan_is_never_read(tmp_path):
    flags = _compliance_flags(
        tmp_path,
        dict(FLAGGED_COMPONENT_SECRET),
        {"flagged": False, "matches": []},
    )
    secret_scan = field(flags, "secret_scan")
    assert secret_scan is not None
    assert list(secret_scan) == []


def test_flagged_repository_scan_is_single_null_component_entry(tmp_path):
    flags = _compliance_flags(tmp_path, dict(CLEAN_SECRET), dict(FLAGGED_REPO_SECRET))
    secret_scan = list(field(flags, "secret_scan"))
    assert len(secret_scan) == 1
    entry = secret_scan[0]
    if isinstance(entry, dict):
        assert set(entry.keys()) == {"component_id", "result"}
    assert field(entry, "component_id") is None
    assert field(entry, "result") == FLAGGED_REPO_SECRET
    if isinstance(entry, dict):
        assert entry == {"component_id": None, "result": FLAGGED_REPO_SECRET}