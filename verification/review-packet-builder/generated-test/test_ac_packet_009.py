# hotdocs-criterion: sha256:0e16db40c6f7e45aa1f524ee784a645d45b38beec9b14c93c6b0e0f6d386f0f9
import shutil
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "drivers": [],
        "overall": "pass",
    }


def _license_scan():
    return {
        "blocked": False,
        "gate_version": "license_scanner@1.0.0",
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_scan(matches):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": bool(matches),
        "matches": matches,
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _report(top_secret_scan):
    return {
        "scope": "blast-radius",
        "ready": not bool(top_secret_scan and top_secret_scan["flagged"]),
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report("comp-foo"),
                "license_scan": _license_scan(),
                "secret_scan": _secret_scan([]),
            }
        },
        "capabilities": {},
        "secret_scan": top_secret_scan,
        "not_ready_reasons": [],
    }


def _write_fake_tracker(repo_root, report, log_path):
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import copy\n"
        "\n"
        "_REPORT = " + repr(report) + "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (d / "provenance_tracker.py").write_text(src)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root), check=True, capture_output=True,
    )


def _require_git():
    if shutil.which("git") is None:
        pytest.skip("git not available")


def _assert_empty_exemptions(packet):
    ex = field(packet, "exemption_changes")
    assert list(field(ex, "sealed")) == []
    assert list(field(ex, "pinned_overrides")) == []


def test_clean_merge_still_produces_packet(tmp_path):
    _require_git()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    _git(repo_root, "init", "-q")
    (repo_root / "README.md").write_text("hello\n")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "init")
    _write_fake_tracker(repo_root, _report(_secret_scan([])), log)

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    assert packet is not None
    assert log.is_file() and "check_readiness" in log.read_text()
    assert list(field(packet, "changed_requirements")) == ["R-FOO-001"]
    assert dict(field(packet, "provenance_hit_status")) == {"comp-foo": True}
    flags = field(packet, "compliance_flags")
    assert list(field(flags, "license_scan")) == []
    assert list(field(flags, "secret_scan")) == []


def test_zero_commit_repo_produces_packet_with_empty_git_fields(tmp_path):
    _require_git()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    _git(repo_root, "init", "-q")
    _write_fake_tracker(repo_root, _report(_secret_scan([])), log)

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    assert packet is not None
    assert not field(packet, "spec_diff")
    _assert_empty_exemptions(packet)


def test_non_git_repo_produces_full_packet(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert not (repo_root / ".git").exists()
    log = tmp_path / "calls.log"
    match = {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "a/b.py", "line": 3}
    top_scan = _secret_scan([match])
    report = _report(top_scan)
    _write_fake_tracker(repo_root, report, log)

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    assert packet is not None
    assert log.is_file() and "check_readiness" in log.read_text()

    assert list(field(packet, "changed_requirements")) == ["R-FOO-001"]
    assert set(field(packet, "regenerated_components")) == {"comp-foo"}

    vr = field(packet, "verification_results")
    assert set(vr.keys()) == {"comp-foo"}
    comp_vr = vr["comp-foo"]
    assert field(comp_vr, "component_id") == "comp-foo"
    assert field(comp_vr, "overall") == "pass"

    flags = field(packet, "compliance_flags")
    assert list(field(flags, "license_scan")) == []
    secret_entries = list(field(flags, "secret_scan"))
    assert len(secret_entries) == 1
    entry = secret_entries[0]
    assert field(entry, "component_id") is None
    result = field(entry, "result")
    assert field(result, "flagged") is True
    matches = list(field(result, "matches"))
    assert len(matches) == 1
    assert field(matches[0], "file") == "a/b.py"
    assert field(matches[0], "line") == 3

    assert dict(field(packet, "provenance_hit_status")) == {"comp-foo": True}
    assert dict(field(packet, "capability_scenarios")) == {}

    assert not field(packet, "spec_diff")
    _assert_empty_exemptions(packet)