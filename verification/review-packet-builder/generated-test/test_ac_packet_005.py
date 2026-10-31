import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import review_packet_builder


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestAcPacket005(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="hotdocs-repo-"))
        self.invocation_log = self.repo_root / "invocation.log"

        subprocess.run(["git", "init", "-q"], cwd=self.repo_root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo_root, check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.repo_root, check=True,
        )

        self._write_spec_fixture()
        self._write_fake_provenance_tracker()

        subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "initial"], cwd=self.repo_root, check=True,
        )

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)

    def _write_spec_fixture(self):
        comp_dir = self.repo_root / "specs" / "components" / "foo"
        (comp_dir / "requirements").mkdir(parents=True)
        (comp_dir / "acceptance").mkdir(parents=True)

        (comp_dir / "component.md").write_text(textwrap.dedent("""\
            ---
            id: comp-foo
            title: Foo Component
            status: draft
            owners: [lselfors@gmail.com]
            sealed: true
            source_path: /opt/legacy/foo.py
            ---

            # comp-foo

            A sealed, hand-maintained legacy component used as a fixture.
            """))

        (comp_dir / "requirements" / "R-FOO-001.md").write_text(textwrap.dedent("""\
            **R-FOO-001** — Foo MUST do the one thing it does.
            """))

        (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(textwrap.dedent("""\
            # AC-FOO-001

            Covers: R-FOO-001
            Kind: compiled

            ```gherkin
            Given foo
            When foo runs
            Then foo works
            ```
            """))

    def _write_fake_provenance_tracker(self):
        dep_dir = self.repo_root / "gen" / "provenance-tracker"
        dep_dir.mkdir(parents=True)

        template = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with open(__LOG_PATH__, "a") as f:
        f.write("called\\n")
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {"id": "AC-FOO-001", "covers": "R-FOO-001",
                         "kind": "compiled", "result": "pass"}
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False, "license_ids": ["MIT"]},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
'''
        content = template.replace("__LOG_PATH__", repr(str(self.invocation_log)))
        (dep_dir / "provenance_tracker.py").write_text(content)

    def test_compliance_flags_present_with_both_fields_explicitly_empty(self):
        packet = review_packet_builder.build_review_packet(["comp-foo"], self.repo_root)

        self.assertTrue(
            self.invocation_log.exists(),
            "expected the fake provenance-tracker.check_readiness to have been invoked",
        )
        self.assertIn("called", self.invocation_log.read_text())

        compliance_flags = _get(packet, "compliance_flags")
        self.assertIsNotNone(
            compliance_flags, "compliance_flags must be present, not omitted"
        )

        if isinstance(compliance_flags, dict):
            self.assertIn("license_scan", compliance_flags)
            self.assertIn("secret_scan", compliance_flags)
        else:
            self.assertTrue(hasattr(compliance_flags, "license_scan"))
            self.assertTrue(hasattr(compliance_flags, "secret_scan"))

        license_scan = _get(compliance_flags, "license_scan")
        secret_scan = _get(compliance_flags, "secret_scan")

        self.assertEqual(license_scan, [])
        self.assertEqual(secret_scan, [])


if __name__ == "__main__":
    unittest.main()