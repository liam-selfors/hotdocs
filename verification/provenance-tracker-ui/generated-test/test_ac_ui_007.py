import json
import shutil
import tempfile
import unittest
from pathlib import Path

import provenance_tracker_ui


FAKE_PROVENANCE_TRACKER_SOURCE = '''
import json

_LOG_PATH = {log_path}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(changed_ids) + "\\n")

    scope = "blast-radius" if changed_ids else "whole-corpus"

    verification_report = {{
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {{}},
        "interface_drift": False,
        "mutation_score": None,
        "overall": "pass",
    }}

    components = {{
        "comp-foo": {{
            "hit": True,
            "verification_report": verification_report,
            "license_scan": {{"blocked": False}},
            "secret_scan": {{"flagged": False}},
        }}
    }}

    return {{
        "scope": scope,
        "ready": True,
        "components": components,
        "capabilities": {{}},
        "not_ready_reasons": [],
    }}


def last_requirement_failures(component_id, repo_root):
    return []
'''


class TestAC_UI_007(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo_root = Path(self.tmp) / "repo"
        self.repo_root.mkdir()
        self.log_path = Path(self.tmp) / "calls.jsonl"

        dep_dir = self.repo_root / "gen" / "provenance-tracker"
        dep_dir.mkdir(parents=True)
        module_path = dep_dir / "provenance_tracker.py"
        module_path.write_text(
            FAKE_PROVENANCE_TRACKER_SOURCE.format(log_path=repr(str(self.log_path)))
        )

        verification_dir = self.repo_root / "verification"
        verification_dir.mkdir(parents=True)
        corpus_graph = {
            "nodes": {
                "comp-foo": {
                    "type": "component",
                    "verification": None,
                    "provenance": None,
                    "size_status": "ok",
                    "sealed": True,
                    "pinned_overrides": [],
                }
            },
            "edges": [],
            "aggregates": {
                "orphan_capability_rate": 0.0,
                "orphan_component_rate": 0.0,
                "orphan_var_rate": 0.0,
            },
        }
        (verification_dir / "corpus-graph.json").write_text(json.dumps(corpus_graph))

        self.out_dir_1 = Path(self.tmp) / "out1"
        self.out_dir_2 = Path(self.tmp) / "out2"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _field(self, value, key):
        return value.get(key) if isinstance(value, dict) else getattr(value, key, None)

    def test_two_scopes_call_check_readiness_fresh_each_time(self):
        snapshot_blast = provenance_tracker_ui.render_tracker_ui(
            self.out_dir_1, self.repo_root, changed_ids=["comp-foo"]
        )
        snapshot_whole = provenance_tracker_ui.render_tracker_ui(
            self.out_dir_2, self.repo_root, changed_ids=None
        )

        self.assertTrue(self.log_path.exists())
        with open(self.log_path, "r") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], ["comp-foo"])
        self.assertIsNone(lines[1])

        self.assertEqual(self._field(snapshot_blast, "scope"), "blast-radius")
        self.assertEqual(self._field(snapshot_whole, "scope"), "whole-corpus")

        html_blast = (self.out_dir_1 / "index.html").read_text()
        html_whole = (self.out_dir_2 / "index.html").read_text()

        self.assertIn("blast-radius", html_blast)
        self.assertIn("comp-foo", html_blast)
        self.assertIn("whole-corpus", html_whole)


if __name__ == "__main__":
    unittest.main()