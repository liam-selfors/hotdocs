import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import review_packet_builder


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


class TestAcPacket003(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)

        subprocess.run(["git", "init"], cwd=self.repo_root, check=True,
                        capture_output=True)
        subprocess.run(
            ["git", "-c", "user.email=test@example.com",
             "-c", "user.name=Test", "commit", "--allow-empty",
             "-m", "initial commit"],
            cwd=self.repo_root, check=True, capture_output=True,
        )

        tracker_dir = self.repo_root / "gen" / "provenance-tracker"
        tracker_dir.mkdir(parents=True, exist_ok=True)
        tracker_module = tracker_dir / "provenance_tracker.py"
        tracker_module.write_text(textwrap.dedent('''
            def check_readiness(repo_root, changed_ids=None, model=None,
                                 seed=0, llm_backend=None):
                return {
                    "scope": "blast-radius",
                    "ready": True,
                    "components": {
                        "comp-foo": {
                            "hit": True,
                            "verification_report": {
                                "component_id": "comp-foo",
                                "criteria": [],
                                "requirement_results": {},
                                "interface_drift": False,
                                "mutation_score": 1.0,
                                "overall": "pass",
                            },
                            "license_scan": {"blocked": False},
                            "secret_scan": {"flagged": False},
                        },
                        "comp-bar": {
                            "hit": True,
                            "verification_report": {
                                "component_id": "comp-bar",
                                "criteria": [],
                                "requirement_results": {},
                                "interface_drift": False,
                                "mutation_score": 1.0,
                                "overall": "pass",
                            },
                            "license_scan": {"blocked": False},
                            "secret_scan": {"flagged": False},
                        },
                    },
                    "capabilities": {},
                    "not_ready_reasons": [],
                }


            def last_requirement_failures(component_id, repo_root):
                return []
        '''))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_regenerated_components_lists_exactly_the_two_component_ids(self):
        packet = review_packet_builder.build_review_packet(
            ["comp-foo", "comp-bar"], self.repo_root
        )

        regenerated = _get(packet, "regenerated_components")
        self.assertIsNotNone(regenerated)
        self.assertEqual(sorted(regenerated), ["comp-bar", "comp-foo"])


if __name__ == "__main__":
    unittest.main()