import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import review_packet_builder


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo_root), check=True, capture_output=True)


def _src(*lines: str) -> str:
    return "\n".join(lines) + "\n"


class TestAcPacket011(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)
        self._forbidden_log = self.repo_root / "forbidden_calls.log"
        self._env_key = "AC_PACKET_011_FORBIDDEN_LOG"
        self._old_env = os.environ.get(self._env_key)
        os.environ[self._env_key] = str(self._forbidden_log)
        self._build_repo()

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop(self._env_key, None)
        else:
            os.environ[self._env_key] = self._old_env
        self._tmp.cleanup()

    def _build_repo(self):
        repo_root = self.repo_root

        _git(repo_root, "init")
        _git(repo_root, "config", "user.email", "test@example.com")
        _git(repo_root, "config", "user.name", "Test")

        component_md = _src(
            "---",
            "id: comp-foo",
            "title: Foo",
            "status: ratified",
            "owners: [lselfors]",
            "sealed: true",
            "source_path: vendor/foo/foo.py",
            "depends_on: []",
            "last_ratified_commit: abc1234",
            "---",
            "",
            "Foo is a sealed stand-in component used as fixture data for this test.",
        )
        _write(repo_root / "specs/components/foo/component.md", component_md)

        _write(
            repo_root / "specs/components/foo/requirements/R-FOO-001.md",
            _src(
                "# R-FOO-001",
                "",
                "Foo MUST do the one thing it does.",
            ),
        )
        _write(
            repo_root / "specs/components/foo/acceptance/AC-FOO-001.md",
            _src(
                "# AC-FOO-001",
                "",
                "Covers: R-FOO-001",
                "Kind: compiled",
                "",
                "```gherkin",
                "Given foo",
                "When foo runs",
                "Then foo passes",
                "```",
            ),
        )
        _write(
            repo_root / "specs/components/foo/constraints.md",
            "No additional constraints.\n",
        )

        provenance_tracker_src = _src(
            "VERIFICATION_REPORT = {",
            '    "component_id": "comp-foo",',
            '    "criteria": [',
            '        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},',
            "    ],",
            '    "requirement_results": {"R-FOO-001": "pass"},',
            '    "interface_drift": False,',
            '    "mutation_score": 0.92,',
            '    "overall": "pass",',
            "}",
            "",
            "LICENSE_SCAN_RESULT = {",
            '    "blocked": True,',
            '    "license": "GPL-3.0",',
            '    "findings": ["found GPL text"],',
            "}",
            "",
            "SECRET_SCAN_RESULT = {",
            '    "flagged": True,',
            '    "findings": ["aws_key pattern"],',
            "}",
            "",
            "CAPABILITY_SCENARIO_REPORT = {",
            '    "P-ZERO-EDIT": {"overall": "pass", "scenarios": []},',
            "}",
            "",
            "VERIFY_REPORT = {",
            '    "scope": "blast-radius",',
            '    "ready": True,',
            '    "components": {',
            '        "comp-foo": {',
            '            "hit": True,',
            '            "verification_report": VERIFICATION_REPORT,',
            '            "license_scan": LICENSE_SCAN_RESULT,',
            '            "secret_scan": SECRET_SCAN_RESULT,',
            "        },",
            "    },",
            '    "capabilities": {',
            '        "P-ZERO-EDIT": {',
            '            "hit": True,',
            '            "capability_scenario_report": CAPABILITY_SCENARIO_REPORT,',
            "        },",
            "    },",
            '    "not_ready_reasons": [],',
            "}",
            "",
            "",
            "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):",
            "    return VERIFY_REPORT",
            "",
            "",
            "def last_requirement_failures(component_id, repo_root):",
            "    return []",
        )
        _write(
            repo_root / "gen/provenance-tracker/provenance_tracker.py",
            provenance_tracker_src,
        )

        for slug, module_name in [
            ("verifier-orchestrator", "verifier_orchestrator"),
            ("license-scanner", "license_scanner"),
            ("secret-scanner", "secret_scanner"),
            ("capability-scenario-verifier", "capability_scenario_verifier"),
        ]:
            forbidden_src = _src(
                "import os",
                "",
                '_log_path = os.environ.get("AC_PACKET_011_FORBIDDEN_LOG")',
                "if _log_path:",
                '    with open(_log_path, "a") as _f:',
                '        _f.write("{}\\n")'.format(slug),
            )
            _write(
                repo_root / "gen" / slug / (module_name + ".py"),
                forbidden_src,
            )

        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-m", "initial commit")

    @staticmethod
    def _get(value, key, default=None):
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

    def test_populated_entirely_from_provenance_tracker_with_no_other_calls(self):
        packet = review_packet_builder.build_review_packet(["comp-foo"], self.repo_root)

        verification_results = self._get(packet, "verification_results")
        compliance_flags = self._get(packet, "compliance_flags")
        provenance_hit_status = self._get(packet, "provenance_hit_status")
        capability_scenarios = self._get(packet, "capability_scenarios")

        expected_verification_report = {
            "component_id": "comp-foo",
            "criteria": [
                {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "overall": "pass",
        }
        self.assertEqual(
            self._get(verification_results, "comp-foo"),
            expected_verification_report,
        )

        license_entries = self._get(compliance_flags, "license_scan")
        secret_entries = self._get(compliance_flags, "secret_scan")

        self.assertEqual(len(license_entries), 1)
        self.assertEqual(self._get(license_entries[0], "component_id"), "comp-foo")
        self.assertEqual(
            self._get(license_entries[0], "result"),
            {
                "blocked": True,
                "license": "GPL-3.0",
                "findings": ["found GPL text"],
            },
        )

        self.assertEqual(len(secret_entries), 1)
        self.assertEqual(self._get(secret_entries[0], "component_id"), "comp-foo")
        self.assertEqual(
            self._get(secret_entries[0], "result"),
            {"flagged": True, "findings": ["aws_key pattern"]},
        )

        self.assertEqual(self._get(provenance_hit_status, "comp-foo"), True)

        self.assertEqual(
            capability_scenarios,
            {"P-ZERO-EDIT": {"P-ZERO-EDIT": {"overall": "pass", "scenarios": []}}},
        )

        if self._forbidden_log.exists():
            forbidden_calls = self._forbidden_log.read_text()
        else:
            forbidden_calls = ""
        self.assertEqual(
            forbidden_calls,
            "",
            "expected no call into verifier-orchestrator, license-scanner, "
            "secret-scanner, or capability-scenario-verifier",
        )


if __name__ == "__main__":
    unittest.main()