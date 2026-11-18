# hotdocs-criterion: sha256:73ca0db060dcbd18f411cecfea69d4b8932efe91dd053eb35ff337a246696874
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
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 1.0,
    "mutation_error": None,
    "overall": "pass",
}

LICENSE_SCAN = {"blocked": False, "findings": []}
SECRET_SCAN = {"flagged": False, "findings": []}

CAPABILITY_REPORT = {"P-ZERO-EDIT": {"overall": "pass", "scenarios": []}}

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": True,
    "components": {
        "comp-foo": {
            "hit": True,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": LICENSE_SCAN,
            "secret_scan": SECRET_SCAN,
        }
    },
    "capabilities": {
        "P-ZERO-EDIT": {
            "hit": True,
            "capability_scenario_report": CAPABILITY_REPORT,
        }
    },
    "not_ready_reasons": [],
}

CHANGED_IDS = ["comp-foo", "R-FOO-001"]


def write_fixture(repo_root, log_path):
    repo_root.mkdir(parents=True, exist_ok=True)
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "realizes: [P-ZERO-EDIT]\n"
        "---\n"
        "\n"
        "# Foo\n"
    )
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "**R-FOO-001** — Foo MUST do the thing.\n"
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n"
    )
    (comp_dir / "interface" / "library.md").write_text("# Library\n\nfoo() -> None\n")

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import copy\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('check_readiness ' + repr(list(changed_ids) if changed_ids is not None else None) + '\\n')\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (tracker_dir / "provenance_tracker.py").write_text(source)


def git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def assert_empty_spec_diff(packet):
    spec_diff = field(packet, "spec_diff")
    assert not spec_diff, "spec_diff should be empty, got: " + repr(spec_diff)


def assert_empty_exemption_changes(packet):
    ex = field(packet, "exemption_changes")
    if ex is None:
        return
    sealed = field(ex, "sealed")
    pinned = field(ex, "pinned_overrides")
    assert list(sealed) == []
    assert list(pinned) == []


def assert_provenance_fields(packet):
    assert sorted(field(packet, "changed_requirements")) == ["R-FOO-001"]
    assert sorted(field(packet, "regenerated_components")) == ["comp-foo"]

    vr = field(packet, "verification_results")
    assert set(vr.keys()) == {"comp-foo"}
    assert vr["comp-foo"] == VERIFICATION_REPORT

    flags = field(packet, "compliance_flags")
    assert list(field(flags, "license_scan")) == []
    assert list(field(flags, "secret_scan")) == []

    assert dict(field(packet, "provenance_hit_status")) == {"comp-foo": True}

    assert dict(field(packet, "capability_scenarios")) == {"P-ZERO-EDIT": CAPABILITY_REPORT}


def assert_fake_called(log_path):
    assert log_path.is_file(), "provenance-tracker fake was never called"
    lines = [l for l in log_path.read_text().splitlines() if l.strip()]
    assert any(l.startswith("check_readiness") for l in lines)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    # Ensure git never discovers a parent repository above tmp_path.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "tracker.log"
    write_fixture(repo_root, log_path)
    return repo_root, log_path


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


@needs_git
def test_clean_merge_still_produces_packet(isolated):
    repo_root, log_path = isolated
    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    assert_fake_called(log_path)
    assert_provenance_fields(packet)
    residual = field(packet, "residual_risk")
    assert list(residual) == []


@needs_git
def test_zero_commit_repo_still_produces_packet(isolated):
    repo_root, log_path = isolated
    git(repo_root, "init", "-q")

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    assert_fake_called(log_path)
    assert_empty_spec_diff(packet)
    assert_empty_exemption_changes(packet)
    assert_provenance_fields(packet)


def test_non_git_repo_still_produces_packet(isolated):
    repo_root, log_path = isolated
    assert not (repo_root / ".git").exists()

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    assert_fake_called(log_path)
    assert_provenance_fields(packet)
    assert_empty_spec_diff(packet)
    assert_empty_exemption_changes(packet)