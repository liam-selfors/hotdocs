import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import review_packet_builder


FAKE_PROVENANCE_TRACKER_SOURCE = """
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
                        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass"
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False}
            }
        },
        "capabilities": {},
        "not_ready_reasons": []
    }


def last_requirement_failures(component_id, repo_root):
    return []
"""

COMPONENT_MD = """---
id: comp-foo
title: Foo
status: ratified
owners: [alice]
last_ratified_commit: 0000000000000000000000000000000000000
sealed: false
---

# Foo

A synthetic component used only to exercise review-packet-builder.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** -- Foo MUST return a constant placeholder value for testing purposes.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001

```gherkin
Given foo
When foo runs
Then foo returns the placeholder value
```
"""

ORIGINAL_GENERATED_CODE = """def foo():
    # OLDLINE_MARKER_8e21cb_1
    return "old-value-1"


def helper_one():
    # OLDLINE_MARKER_8e21cb_2
    return "old-value-2"


def helper_two():
    # OLDLINE_MARKER_8e21cb_3
    return "old-value-3"
"""

CHANGED_GENERATED_CODE = """def foo():
    # NEWLINE_MARKER_4f9a21_1
    return "new-value-1"


def helper_one():
    # NEWLINE_MARKER_4f9a21_2
    return "new-value-2"


def helper_two():
    # NEWLINE_MARKER_4f9a21_3
    return "new-value-3"


def helper_three():
    # NEWLINE_MARKER_4f9a21_4
    return "new-value-4"


def helper_four():
    # NEWLINE_MARKER_4f9a21_5
    return "new-value-5"
"""


def dual_get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def run_git(repo_root, *args):
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True, capture_output=True, text=True,
    )


class BuildReviewPacketExcludesGeneratedCodeDiffTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmpdir)

        run_git(self.repo_root, "init")
        run_git(self.repo_root, "config", "user.email", "test@example.com")
        run_git(self.repo_root, "config", "user.name", "Test")

        tracker_dir = self.repo_root / "gen" / "provenance-tracker"
        tracker_dir.mkdir(parents=True)
        (tracker_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER_SOURCE)

        comp_dir = self.repo_root / "specs" / "components" / "foo"
        (comp_dir / "requirements").mkdir(parents=True)
        (comp_dir / "acceptance").mkdir(parents=True)
        (comp_dir / "component.md").write_text(COMPONENT_MD)
        (comp_dir / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
        (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)

        gen_foo_dir = self.repo_root / "gen" / "foo"
        gen_foo_dir.mkdir(parents=True)
        self.gen_foo_file = gen_foo_dir / "foo.py"
        self.gen_foo_file.write_text(ORIGINAL_GENERATED_CODE)

        run_git(self.repo_root, "add", "-A")
        run_git(self.repo_root, "commit", "-m", "initial commit")

        # Substantial regeneration of comp-foo's generated code.
        self.gen_foo_file.write_text(CHANGED_GENERATED_CODE)
        run_git(self.repo_root, "add", "-A")
        run_git(self.repo_root, "commit", "-m", "regenerate comp-foo substantially")

        diff_proc = subprocess.run(
            ["git", "-C", str(self.repo_root), "diff", "HEAD~1", "HEAD", "--", "gen/foo/foo.py"],
            check=True, capture_output=True, text=True,
        )
        self.generated_code_diff = diff_proc.stdout
        self.assertIn("NEWLINE_MARKER_4f9a21", self.generated_code_diff)
        self.assertIn("OLDLINE_MARKER_8e21cb", self.generated_code_diff)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_packet_contains_no_generated_code_diff_content(self):
        packet = review_packet_builder.build_review_packet(["comp-foo"], self.repo_root)

        field_names = (
            "spec_diff",
            "changed_requirements",
            "regenerated_components",
            "verification_results",
            "compliance_flags",
            "provenance_hit_status",
            "capability_scenarios",
            "exemption_changes",
            "residual_risk",
        )
        fields = {name: dual_get(packet, name) for name in field_names}

        serialized = json.dumps(fields, default=str)

        self.assertNotIn(self.generated_code_diff, serialized)
        self.assertNotIn("NEWLINE_MARKER_4f9a21", serialized)
        self.assertNotIn("OLDLINE_MARKER_8e21cb", serialized)

        checked_diff_line = False
        for line in self.generated_code_diff.splitlines():
            stripped = line.strip()
            if stripped.startswith(("+", "-")) and len(stripped) > 3:
                checked_diff_line = True
                self.assertNotIn(stripped, serialized)
        self.assertTrue(checked_diff_line)


if __name__ == "__main__":
    unittest.main()