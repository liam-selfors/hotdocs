import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import review_packet_builder


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


PROVENANCE_TRACKER_STANDIN = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    log_path = __import__("os").environ.get("AC_PACKET_006_LOG")
    if log_path:
        with open(log_path, "a") as f:
            f.write("check_readiness_called\\n")
    return {
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
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-bar": {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-bar: no provenance for current spec state \\u2014 run hotdocs generate comp-bar"
        ],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


class AcPacket006Test(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="ac-packet-006-"))
        self.log_path = Path(tempfile.mkdtemp(prefix="ac-packet-006-log-")) / "invocations.log"
        self._prior_log_env = os.environ.get("AC_PACKET_006_LOG")
        os.environ["AC_PACKET_006_LOG"] = str(self.log_path)

        subprocess.run(
            ["git", "init"], cwd=str(self.repo_root), check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(self.repo_root),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(self.repo_root),
            check=True,
            capture_output=True,
        )
        (self.repo_root / "README.md").write_text("placeholder\n")
        subprocess.run(
            ["git", "add", "."], cwd=str(self.repo_root), check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=str(self.repo_root),
            check=True,
            capture_output=True,
        )

        tracker_dir = self.repo_root / "gen" / "provenance-tracker"
        tracker_dir.mkdir(parents=True, exist_ok=True)
        (tracker_dir / "provenance_tracker.py").write_text(PROVENANCE_TRACKER_STANDIN)

    def tearDown(self):
        if self._prior_log_env is None:
            os.environ.pop("AC_PACKET_006_LOG", None)
        else:
            os.environ["AC_PACKET_006_LOG"] = self._prior_log_env
        shutil.rmtree(self.repo_root, ignore_errors=True)
        shutil.rmtree(self.log_path.parent, ignore_errors=True)

    def test_provenance_hit_status_reflects_hit_and_miss_per_component(self):
        packet = review_packet_builder.build_review_packet(
            ["comp-foo", "comp-bar"], self.repo_root
        )

        self.assertTrue(
            self.log_path.exists(),
            "expected the provenance-tracker stand-in to have been invoked",
        )
        self.assertIn("check_readiness_called", self.log_path.read_text())

        provenance_hit_status = _field(packet, "provenance_hit_status")
        self.assertIsNotNone(provenance_hit_status)

        self.assertIn("comp-foo", provenance_hit_status)
        self.assertIn("comp-bar", provenance_hit_status)
        self.assertIs(provenance_hit_status["comp-foo"], True)
        self.assertIs(provenance_hit_status["comp-bar"], False)


if __name__ == "__main__":
    unittest.main()