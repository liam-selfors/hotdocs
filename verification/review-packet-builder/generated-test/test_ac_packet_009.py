# hotdocs-criterion: sha256:5e89313b2d30243296c4f956246e040ca2f4503fa28156ae185d76ee54cb66cc
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-002": "pass"},
    "interface_drift": False,
    "mutation_score": None,
    "mutation_error": None,
    "assets": [],
    "overall": "pass",
}

LICENSE_SCAN = {
    "gate_version": "license_scanner@1.0.0",
    "blocked": False,
    "findings": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

SECRET_SCAN = {
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

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": True,
    "components": {
        "comp-foo": {
            "hit": True,
            "reason": None,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": LICENSE_SCAN,
            "secret_scan": SECRET_SCAN,
        }
    },
    "capabilities": {},
    "secret_scan": SECRET_SCAN,
    "not_ready_reasons": [],
}

CHANGED_IDS = ["comp-foo", "R-FOO-002", "AC-FOO-002"]


def write_corpus(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n# Foo\n"
    )
    (comp / "requirements" / "R-FOO-002.md").write_text(
        "**R-FOO-002** - Foo MUST do the thing.\n"
    )
    (comp / "acceptance" / "AC-FOO-002.md").write_text(
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n"
    )
    (comp / "interface" / "library.md").write_text("# Library\n\nfoo()\n")


def write_fake_tracker(repo_root, log_path):
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write('check_readiness\\n')\n"
        "    return " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (d / "provenance_tracker.py").write_text(src)


def git(repo_root, *args):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    })
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root), check=True, capture_output=True, env=env,
    )


def assert_empty_git_fields(packet):
    spec_diff = field(packet, "spec_diff")
    assert not spec_diff
    ex = field(packet, "exemption_changes")
    if ex:
        assert list(field(ex, "sealed")) == []
        assert list(field(ex, "pinned_overrides")) == []


def assert_tracker_fields(packet):
    assert list(field(packet, "changed_requirements")) == ["R-FOO-002"]
    assert list(field(packet, "regenerated_components")) == ["comp-foo"]
    vr = field(packet, "verification_results")
    assert set(vr.keys()) == {"comp-foo"}
    assert vr["comp-foo"] == VERIFICATION_REPORT
    flags = field(packet, "compliance_flags")
    assert list(field(flags, "license_scan")) == []
    assert list(field(flags, "secret_scan")) == []
    assert dict(field(packet, "provenance_hit_status")) == {"comp-foo": True}
    assert dict(field(packet, "capability_scenarios")) == {}


@pytest.fixture
def isolate_git(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))


def test_clean_merge_still_produces_packet(tmp_path, isolate_git):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker.log"
    write_corpus(repo_root)
    write_fake_tracker(repo_root, log_path)
    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "init")

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    assert log_path.is_file() and log_path.read_text().strip()
    assert_tracker_fields(packet)
    rr = field(packet, "residual_risk")
    assert isinstance(list(rr), list)


def test_zero_commit_repo_produces_packet_with_empty_git_fields(tmp_path, isolate_git):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker.log"
    write_corpus(repo_root)
    write_fake_tracker(repo_root, log_path)
    git(repo_root, "init", "-q")

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    assert_empty_git_fields(packet)
    assert_tracker_fields(packet)


def test_non_git_repo_produces_packet_with_tracker_fields(tmp_path, isolate_git):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker.log"
    write_corpus(repo_root)
    write_fake_tracker(repo_root, log_path)
    assert not (repo_root / ".git").exists()

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    assert log_path.is_file() and log_path.read_text().strip()
    assert_tracker_fields(packet)
    assert_empty_git_fields(packet)