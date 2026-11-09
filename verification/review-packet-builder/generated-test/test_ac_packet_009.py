import subprocess
import tempfile
import unittest
from pathlib import Path

import review_packet_builder


PROVENANCE_TRACKER_SRC = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
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
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "P-ZERO-EDIT": {"overall": "pass", "scenarios": []}
                },
            }
        },
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''

EXPECTED_VERIFICATION_REPORT = {
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
}

EXPECTED_CAPABILITY_SCENARIOS = {
    "P-ZERO-EDIT": {"P-ZERO-EDIT": {"overall": "pass", "scenarios": []}}
}


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _run_git(args, cwd):
    subprocess.run(
        ["git"] + list(args),
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _install_provenance_tracker_fake(repo_root):
    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True, exist_ok=True)
    (tracker_dir / "provenance_tracker.py").write_text(PROVENANCE_TRACKER_SRC)


def _make_git_repo_with_commit(repo_root):
    _run_git(["init"], repo_root)
    _run_git(["config", "user.email", "test@example.com"], repo_root)
    _run_git(["config", "user.name", "Test"], repo_root)
    (repo_root / "README.md").write_text("hello\n")
    _run_git(["add", "."], repo_root)
    _run_git(["commit", "-m", "initial"], repo_root)


def _make_git_repo_no_commits(repo_root):
    _run_git(["init"], repo_root)


class TestAcPacket009(unittest.TestCase):
    def test_clean_merge_with_full_hits_still_produces_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _make_git_repo_with_commit(repo_root)
            _install_provenance_tracker_fake(repo_root)

            packet = review_packet_builder.build_review_packet(
                ["comp-foo", "R-FOO-001"], repo_root
            )

            self.assertIsNotNone(packet)

            compliance_flags = _field(packet, "compliance_flags")
            license_scan = _field(compliance_flags, "license_scan")
            secret_scan = _field(compliance_flags, "secret_scan")
            self.assertEqual(license_scan, [])
            self.assertEqual(secret_scan, [])

            residual_risk = _field(packet, "residual_risk")
            self.assertEqual(residual_risk, [])

            provenance_hit_status = _field(packet, "provenance_hit_status")
            self.assertEqual(provenance_hit_status, {"comp-foo": True})

    def test_zero_commit_repo_still_produces_packet_with_empty_git_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _make_git_repo_no_commits(repo_root)
            _install_provenance_tracker_fake(repo_root)

            packet = review_packet_builder.build_review_packet(
                ["comp-foo", "R-FOO-001"], repo_root
            )

            self.assertIsNotNone(packet)

            spec_diff = _field(packet, "spec_diff")
            self.assertFalse(spec_diff)

            exemption_changes = _field(packet, "exemption_changes")
            sealed = _field(exemption_changes, "sealed")
            pinned_overrides = _field(exemption_changes, "pinned_overrides")
            self.assertEqual(sealed, [])
            self.assertEqual(pinned_overrides, [])

    def test_non_git_repo_still_produces_packet_fully_populated_from_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _install_provenance_tracker_fake(repo_root)

            packet = review_packet_builder.build_review_packet(
                ["comp-foo", "R-FOO-001"], repo_root
            )

            self.assertIsNotNone(packet)

            spec_diff = _field(packet, "spec_diff")
            self.assertFalse(spec_diff)

            exemption_changes = _field(packet, "exemption_changes")
            sealed = _field(exemption_changes, "sealed")
            pinned_overrides = _field(exemption_changes, "pinned_overrides")
            self.assertEqual(sealed, [])
            self.assertEqual(pinned_overrides, [])

            changed_requirements = _field(packet, "changed_requirements")
            self.assertEqual(sorted(changed_requirements), ["R-FOO-001"])

            regenerated_components = _field(packet, "regenerated_components")
            self.assertEqual(sorted(regenerated_components), ["comp-foo"])

            verification_results = _field(packet, "verification_results")
            self.assertIsInstance(verification_results, dict)
            self.assertEqual(
                verification_results.get("comp-foo"), EXPECTED_VERIFICATION_REPORT
            )

            compliance_flags = _field(packet, "compliance_flags")
            license_scan = _field(compliance_flags, "license_scan")
            secret_scan = _field(compliance_flags, "secret_scan")
            self.assertEqual(license_scan, [])
            self.assertEqual(secret_scan, [])

            provenance_hit_status = _field(packet, "provenance_hit_status")
            self.assertEqual(provenance_hit_status, {"comp-foo": True})

            capability_scenarios = _field(packet, "capability_scenarios")
            self.assertEqual(capability_scenarios, EXPECTED_CAPABILITY_SCENARIOS)


if __name__ == "__main__":
    unittest.main()