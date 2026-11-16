import review_packet_builder

import json
import os
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


def _fake_source(log_path):
    return (
        "import json\n"
        "\n"
        "_LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(record):\n"
        "    with open(_LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log({'call': 'check_readiness', 'repo_root': str(repo_root),\n"
        "          'changed_ids': list(changed_ids) if changed_ids is not None else None})\n"
        "    return " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log({'call': 'last_requirement_failures', 'component_id': component_id})\n"
        "    return []\n"
    )


def _install_fake(repo_root, log_path):
    target = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_fake_source(log_path), encoding="utf-8")


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _git(repo_root, *args):
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(repo_root.parent)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root),
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


@pytest.fixture(autouse=True)
def _isolate_git(tmp_path, monkeypatch):
    # Never let git discover a repository above the test's own tmp dir.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(var, raising=False)


def _require_git():
    if shutil.which("git") is None:
        pytest.skip("git executable not available")


def _assert_fake_called(log_path):
    calls = _read_log(log_path)
    assert any(c.get("call") == "check_readiness" for c in calls), (
        "provenance-tracker fake check_readiness was never invoked"
    )


def _assert_empty_spec_diff(packet):
    spec_diff = field(packet, "spec_diff")
    assert not spec_diff, f"spec_diff expected empty, got {spec_diff!r}"


def _assert_empty_exemption_changes(packet):
    ex = field(packet, "exemption_changes")
    if not ex:
        return
    sealed = ex.get("sealed", []) if isinstance(ex, dict) else getattr(ex, "sealed", [])
    pinned = (
        ex.get("pinned_overrides", []) if isinstance(ex, dict) else getattr(ex, "pinned_overrides", [])
    )
    assert list(sealed) == [], f"exemption_changes.sealed expected empty, got {sealed!r}"
    assert list(pinned) == [], f"exemption_changes.pinned_overrides expected empty, got {pinned!r}"


def _assert_provenance_fields_correct(packet):
    assert list(field(packet, "changed_requirements")) == ["R-FOO-001"]
    assert sorted(field(packet, "regenerated_components")) == ["comp-foo"]

    vr = dict(field(packet, "verification_results"))
    assert set(vr.keys()) == {"comp-foo"}
    assert vr["comp-foo"] == VERIFICATION_REPORT

    cf = field(packet, "compliance_flags")
    assert list(field(cf, "license_scan")) == []
    assert list(field(cf, "secret_scan")) == []

    phs = dict(field(packet, "provenance_hit_status"))
    assert phs == {"comp-foo": True}

    caps = field(packet, "capability_scenarios")
    assert dict(caps) == {}


def test_clean_merge_still_produces_packet(tmp_path):
    _require_git()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _install_fake(repo_root, log_path)
    (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None, "a packet must be produced even for a fully clean merge"
    _assert_fake_called(log_path)
    _assert_provenance_fields_correct(packet)
    residual = field(packet, "residual_risk")
    assert residual is not None


def test_zero_commit_repo_still_produces_packet(tmp_path):
    _require_git()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _install_fake(repo_root, log_path)
    _git(repo_root, "init", "-q")

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    _assert_fake_called(log_path)
    _assert_empty_spec_diff(packet)
    _assert_empty_exemption_changes(packet)


def test_non_git_repo_root_still_produces_full_packet(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _install_fake(repo_root, log_path)
    assert not (repo_root / ".git").exists()

    packet = review_packet_builder.build_review_packet(list(CHANGED_IDS), repo_root)

    assert packet is not None
    _assert_fake_called(log_path)
    _assert_provenance_fields_correct(packet)
    _assert_empty_spec_diff(packet)
    _assert_empty_exemption_changes(packet)