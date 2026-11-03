import json
import tempfile
import unittest
from pathlib import Path

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_TEST_AUTHOR_SOURCE = '''
import json

_CALL_LOG = {call_log!r}


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
    with open(_CALL_LOG, "a") as f:
        f.write(json.dumps({{
            "criterion_id": _get(bundle, "criterion_id"),
            "model": model,
        }}) + "\\n")
    return {{
        "model_call_error": None,
        "file": {{
            "path": "verification/capabilities/P-FOO/generated-test/test_cs_foo_001.py",
            "content": "def test_cs_foo_001():\\n    assert False\\n",
        }},
    }}
'''

_LLM_ENDPOINT_SOURCE = '''
def complete(prompt, model, backend=None, **params):
    return {"text": "unused", "model_call_error": None}
'''


class TestAcScenario012(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo_root = Path(self._tmp.name) / "repo"
        self.repo_root.mkdir()
        self.call_log = Path(self._tmp.name) / "author_test_calls.jsonl"

        self._write_capability_spec()
        self._write_realizing_component()
        self._write_fake_test_author()
        self._write_fake_llm_endpoint()

    def _write_capability_spec(self):
        product_dir = self.repo_root / "specs" / "product"
        product_dir.mkdir(parents=True)
        content = (
            "---\n"
            "id: P-FOO\n"
            "title: Foo Capability\n"
            "status: draft\n"
            "owners: [lselfors@gmail.com]\n"
            "---\n"
            "\n"
            "# P-FOO\n"
            "\n"
            "### CS-FOO-001\n"
            "\n"
            "Covers: P-FOO\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given a widget\n"
            "When the widget is used\n"
            "Then it works\n"
            "```\n"
        )
        (product_dir / "foo.md").write_text(content)

    def _write_realizing_component(self):
        comp_dir = self.repo_root / "specs" / "components" / "widget-capability"
        comp_dir.mkdir(parents=True)
        content = (
            "---\n"
            "id: comp-widget-capability\n"
            "title: Widget Capability\n"
            "status: draft\n"
            "owners: [lselfors@gmail.com]\n"
            "realizes: [P-FOO]\n"
            "sealed: true\n"
            "source_path: fake/widget-capability/\n"
            "---\n"
            "\n"
            "# comp-widget-capability\n"
            "\n"
            "Purpose: fixture component realizing P-FOO.\n"
        )
        (comp_dir / "component.md").write_text(content)

    def _write_fake_test_author(self):
        mod_dir = self.repo_root / "gen" / "test-author"
        mod_dir.mkdir(parents=True)
        source = _TEST_AUTHOR_SOURCE.format(call_log=str(self.call_log))
        (mod_dir / "test_author.py").write_text(source)

    def _write_fake_llm_endpoint(self):
        mod_dir = self.repo_root / "gen" / "llm-endpoint"
        mod_dir.mkdir(parents=True)
        (mod_dir / "llm_endpoint.py").write_text(_LLM_ENDPOINT_SOURCE)

    def _call_count(self):
        if not self.call_log.exists():
            return 0
        with open(self.call_log) as f:
            return sum(1 for line in f if line.strip())

    def test_failing_scenario_recorded_then_reused_without_rerun(self):
        result1 = capability_scenario_verifier.run_capability_gates(
            "P-FOO", self.repo_root, model="fake-model", seed=0, llm_backend=None,
        )

        self.assertFalse(_get(result1, "hit"))
        report1 = _get(result1, "capability_scenario_report")
        self.assertIsNotNone(report1)
        entry1 = _get(report1, "P-FOO")
        self.assertIsNotNone(entry1)
        self.assertEqual(_get(entry1, "overall"), "fail")
        scenarios1 = _get(entry1, "scenarios")
        self.assertEqual(len(scenarios1), 1)
        self.assertEqual(_get(scenarios1[0], "result"), "fail")
        self.assertEqual(self._call_count(), 1)

        record_path = (
            self.repo_root
            / "verification"
            / "capabilities"
            / "P-FOO"
            / ".provenance.json"
        )
        self.assertTrue(record_path.is_file())
        with open(record_path) as f:
            record = json.load(f)
        self.assertEqual(record["capability_id"], "P-FOO")
        self.assertEqual(record["gate_version"], capability_scenario_verifier.GATE_VERSION)
        recorded_entry = record["capability_scenario_report"]["P-FOO"]
        self.assertEqual(recorded_entry["overall"], "fail")

        check_result = capability_scenario_verifier.check_capability_provenance(
            "P-FOO", self.repo_root,
        )
        self.assertTrue(_get(check_result, "hit"))
        check_report = _get(check_result, "capability_scenario_report")
        check_entry = _get(check_report, "P-FOO")
        self.assertEqual(_get(check_entry, "overall"), "fail")
        self.assertEqual(self._call_count(), 1)

        result2 = capability_scenario_verifier.run_capability_gates(
            "P-FOO", self.repo_root, model=None,
        )
        self.assertTrue(_get(result2, "hit"))
        report2 = _get(result2, "capability_scenario_report")
        entry2 = _get(report2, "P-FOO")
        self.assertEqual(_get(entry2, "overall"), "fail")
        self.assertEqual(self._call_count(), 1)


if __name__ == "__main__":
    unittest.main()