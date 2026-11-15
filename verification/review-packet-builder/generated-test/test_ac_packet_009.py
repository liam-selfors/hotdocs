import review_packet_builder

import json
import shutil
import subprocess
from pathlib import Path

import pytest


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
    "overall": "pass",
}

LICENSE_SCAN = {"blocked": False, "findings": []}
SECRET_SCAN = {"flagged": False, "findings": []}

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
    "capabilities": {},
    "not_ready_reasons": [],
}

CHANGED_IDS = ["comp-foo", "R-FOO-001", "AC-FOO-001"]


def _write_fake_tracker(repo_root: Path, log_path: Path) -> None:
    target = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        f"_LOG = {str(log_path)!r}\n"
        f"_REPORT = {VERIFY_REPORT!r}\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'fn': 'check_readiness',\n"
        "                             'changed_ids': list(changed_ids) if changed_ids is not None else None}) + '\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    target.write_text(source)


def _git(repo_root: Path, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root), check=True, capture_output=True,
    )


@pytest.fixture(autouse=True)
def _isolate_git(monkeypatch, tmp_path):
    # Never let git discover an enclosing repository above the fixture.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(var, raising=False)


def _require_git():
    if shutil.which("git") is None:
        pytest.skip("git not installed")


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def _assert_non_git_fields(packet, log_path: Path):
    assert packet is not None

    assert list(field(packet, "changed_requirements")) == ["R-FOO-001"]
    assert set(field(packet, "regenerated_components")) == {"comp-foo"}

    verification_results = field(packet, "verification_results")
    assert set(verification_results.keys()) == {"comp-foo"}
    assert verification_results["comp-foo"] == VERIFICATION_REPORT

    flags = field(packet, "compliance_flags")
    assert list(field(flags, "license_scan")) == []
    assert list(field(flags, "secret_scan")) == []

    hit_status = field(packet, "provenance_hit_status")
    assert dict(hit_status) == {"comp-foo": True}

    assert dict(field(packet, "capability_scenarios")) == {}

    log = _read_log(log_path)
    assert any(entry["fn"] == "check_readiness" for entry in log), \
        "fake provenance-tracker check_readiness was never invoked"


def _assert_git_fields_empty(packet):
    spec_diff = field(packet, "spec_diff")
    assert spec_diff in ("", None)
    exemption_changes = field(packet, "exemption_changes")
    assert list(field(exemption_changes, "sealed")) == []
    assert list(field(exemption_changes, "pinned_overrides")) == []


def test_clean_merge_still_produces_packet(tmp_path):
    _require_git()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_log.jsonl"
    _git(repo_root, "init", "-q")
    (repo_root / "README.md").write_text("fixture\n")
    _write_fake_tracker(repo_root, log_path)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    _assert_non_git_fields(packet, log_path)
    # Full, clean packet: no residual risk to report, but the packet exists.
    assert list(field(packet, "residual_risk")) == []


def test_zero_commit_repo_produces_packet_with_empty_git_fields(tmp_path):
    _require_git()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_log.jsonl"
    _git(repo_root, "init", "-q")
    _write_fake_tracker(repo_root, log_path)

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    _assert_git_fields_empty(packet)
    _assert_non_git_fields(packet, log_path)


def test_non_git_repo_root_produces_full_packet(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_log.jsonl"
    _write_fake_tracker(repo_root, log_path)
    assert not (repo_root / ".git").exists()

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    _assert_non_git_fields(packet, log_path)
    _assert_git_fields_empty(packet)