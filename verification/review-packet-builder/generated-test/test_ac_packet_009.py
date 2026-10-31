import subprocess
from pathlib import Path

import review_packet_builder


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_provenance_tracker_fake(repo_root: Path, report: dict) -> Path:
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    module_path = dep_dir / "provenance_tracker.py"
    log_path = repo_root / "provenance_tracker_calls.log"
    source = (
        "_REPORT = {report!r}\n"
        "_LOG_PATH = {log_path!r}\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG_PATH, 'a', encoding='utf-8') as f:\n"
        "        f.write('called\\n')\n"
        "    return _REPORT\n"
    ).format(report=report, log_path=str(log_path))
    module_path.write_text(source, encoding="utf-8")
    return log_path


def _full_hit_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {
                            "id": "AC-FOO-001",
                            "covers": "R-FOO-001",
                            "kind": "compiled",
                            "result": "pass",
                        }
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _git_init(repo_root: Path):
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)


def _git_init_with_commit(repo_root: Path):
    _git_init(repo_root)
    (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            "commit",
            "-m",
            "initial",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )


def test_packet_produced_for_clean_merge_full_hits(tmp_path):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()
    _git_init_with_commit(repo_root)

    log_path = _write_provenance_tracker_fake(repo_root, _full_hit_report())

    packet = review_packet_builder.build_review_packet(["R-FOO-001"], repo_root)

    assert packet is not None
    assert log_path.exists()

    sentinel = object()
    for field in (
        "spec_diff",
        "changed_requirements",
        "regenerated_components",
        "verification_results",
        "compliance_flags",
        "provenance_hit_status",
        "capability_scenarios",
        "exemption_changes",
        "residual_risk",
    ):
        assert _get(packet, field, sentinel) is not sentinel

    compliance = _get(packet, "compliance_flags")
    assert _get(compliance, "license_scan") == []
    assert _get(compliance, "secret_scan") == []

    provenance_hit_status = _get(packet, "provenance_hit_status")
    assert _get(provenance_hit_status, "comp-foo") is True

    verification_results = _get(packet, "verification_results")
    vr_foo = _get(verification_results, "comp-foo")
    assert _get(vr_foo, "overall") == "pass"

    residual_risk = _get(packet, "residual_risk")
    assert residual_risk == []


def test_packet_produced_git_init_zero_commits(tmp_path):
    repo_root = tmp_path / "repo2"
    repo_root.mkdir()
    _git_init(repo_root)

    log_path = _write_provenance_tracker_fake(repo_root, _full_hit_report())

    packet = review_packet_builder.build_review_packet(["R-FOO-001"], repo_root)

    assert packet is not None
    assert log_path.exists()

    spec_diff = _get(packet, "spec_diff")
    assert spec_diff == ""

    exemption_changes = _get(packet, "exemption_changes")
    assert _get(exemption_changes, "sealed") == []
    assert _get(exemption_changes, "pinned_overrides") == []


def test_packet_produced_non_git_repo_fields_from_provenance_tracker(tmp_path):
    repo_root = tmp_path / "repo3"
    repo_root.mkdir()
    # No .git directory at all -- not even git-init'd.

    report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {
                            "id": "AC-FOO-001",
                            "covers": "R-FOO-001",
                            "kind": "compiled",
                            "result": "pass",
                        }
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": True, "findings": ["GPL-3.0"]},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "capability_id": "P-ZERO-EDIT",
                    "scenario_id": "zero-edit-happy-path",
                    "result": "pass",
                },
            }
        },
        "not_ready_reasons": [],
    }

    log_path = _write_provenance_tracker_fake(repo_root, report)

    changed_ids = ["R-FOO-001", "comp-foo", "AC-FOO-002"]
    packet = review_packet_builder.build_review_packet(changed_ids, repo_root)

    assert packet is not None
    assert log_path.exists()

    changed_requirements = _get(packet, "changed_requirements")
    assert set(changed_requirements) == {"R-FOO-001"}

    regenerated_components = _get(packet, "regenerated_components")
    assert set(regenerated_components) == {"comp-foo"}

    verification_results = _get(packet, "verification_results")
    vr_foo = _get(verification_results, "comp-foo")
    assert _get(vr_foo, "overall") == "pass"
    assert _get(vr_foo, "requirement_results") == {"R-FOO-001": "pass"}

    provenance_hit_status = _get(packet, "provenance_hit_status")
    assert _get(provenance_hit_status, "comp-foo") is True

    compliance_flags = _get(packet, "compliance_flags")
    license_entries = _get(compliance_flags, "license_scan")
    assert len(license_entries) == 1
    license_entry = license_entries[0]
    assert _get(license_entry, "component_id") == "comp-foo"
    assert _get(_get(license_entry, "result"), "blocked") is True

    secret_entries = _get(compliance_flags, "secret_scan")
    assert secret_entries == []

    capability_scenarios = _get(packet, "capability_scenarios")
    cap_report = _get(capability_scenarios, "P-ZERO-EDIT")
    assert _get(cap_report, "capability_id") == "P-ZERO-EDIT"
    assert _get(cap_report, "result") == "pass"

    spec_diff = _get(packet, "spec_diff")
    assert spec_diff == ""

    exemption_changes = _get(packet, "exemption_changes")
    assert _get(exemption_changes, "sealed") == []
    assert _get(exemption_changes, "pinned_overrides") == []