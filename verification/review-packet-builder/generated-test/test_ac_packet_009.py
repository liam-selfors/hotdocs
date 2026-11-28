# hotdocs-criterion: sha256:34c0177b26c857b92ef07f7bcde0e89518562e3386a087a1a187427d0f63960d
import os
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def maybe_field(value, name, default):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


@pytest.fixture(autouse=True)
def isolate_git(tmp_path, monkeypatch):
    # Prevent git from discovering any enclosing repository above tmp_path.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 1.0,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "pass",
}

LICENSE_SCAN = {
    "blocked": False,
    "flagged": False,
    "matches": [],
    "gate_version": "license_scanner@1.0.0",
    "cache_hit": False,
}


def secret_scan_result(matches):
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


CLEAN_COMPONENT_SECRET_SCAN = secret_scan_result([])

FLAGGED_TOP_SECRET_SCAN = secret_scan_result(
    [{"rule_id": "AWS Access Key", "risk_tier": "high", "file": "a/b.py", "line": 3}]
)


def make_report(top_secret_scan, ready):
    return {
        "scope": "blast-radius",
        "ready": ready,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": VERIFICATION_REPORT,
                "license_scan": LICENSE_SCAN,
                "secret_scan": CLEAN_COMPONENT_SECRET_SCAN,
            }
        },
        "capabilities": {},
        "secret_scan": top_secret_scan,
        "not_ready_reasons": [] if ready else ["secret scan flagged: a/b.py:3"],
    }


def write_fake_tracker(repo_root, report, log_path):
    target = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "REPORT = " + repr(report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )
    target.write_text(source)


CHANGED_IDS = ["comp-foo", "R-FOO-001", "AC-FOO-001"]


def assert_core_fields(packet, expected_secret_entries):
    assert packet is not None
    assert list(field(packet, "changed_requirements")) == ["R-FOO-001"]
    assert list(field(packet, "regenerated_components")) == ["comp-foo"]

    vr = field(packet, "verification_results")
    assert list(vr.keys()) == ["comp-foo"]
    assert vr["comp-foo"] == VERIFICATION_REPORT

    flags = field(packet, "compliance_flags")
    assert list(field(flags, "license_scan")) == []
    secret = list(field(flags, "secret_scan"))
    assert len(secret) == len(expected_secret_entries)
    for got, want in zip(secret, expected_secret_entries):
        assert field(got, "component_id") == want["component_id"]
        assert field(got, "result") == want["result"]

    assert dict(field(packet, "provenance_hit_status")) == {"comp-foo": True}
    assert dict(field(packet, "capability_scenarios")) == {}


def assert_git_fields_empty(packet):
    assert not field(packet, "spec_diff")
    exemptions = field(packet, "exemption_changes")
    assert list(maybe_field(exemptions, "sealed", [])) == []
    assert list(maybe_field(exemptions, "pinned_overrides", [])) == []


def test_clean_merge_still_produces_packet(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init")
    (repo_root / "README.md").write_text("hello\n")
    git(repo_root, "add", "README.md")
    git(repo_root, "commit", "-m", "initial")

    log_path = tmp_path / "tracker.log"
    write_fake_tracker(repo_root, make_report(CLEAN_COMPONENT_SECRET_SCAN, True), log_path)

    packet = review_packet_builder.build_review_packet(CHANGED_IDS, repo_root)

    assert packet is not None
    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text().splitlines()
    assert_core_fields(packet, [])
    assert list(maybe_field(field(packet, "residual_risk"), "__iter__", None) and field(packet, "residual_risk")) == []


def test_zero_commit_repo_still_produces_packet(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init")

    log_path = tmp_path / "tracker.log"
    write_fake_tracker(repo_root, make_report(CLEAN_COMPONENT_SECRET_SCAN, True), log_path)

    packet = review_packet_builder.build_review_packet(CHANGED_IDS, repo_root)

    assert packet is not None
    assert_git_fields_empty(packet)


def test_non_git_repo_still_produces_full_packet(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert not (repo_root / ".git").exists()

    log_path = tmp_path / "tracker.log"
    write_fake_tracker(repo_root, make_report(FLAGGED_TOP_SECRET_SCAN, False), log_path)

    packet = review_packet_builder.build_review_packet(CHANGED_IDS, repo_root)

    assert packet is not None
    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text().splitlines()
    assert_core_fields(
        packet,
        [{"component_id": None, "result": FLAGGED_TOP_SECRET_SCAN}],
    )
    assert_git_fields_empty(packet)