import json
import shutil
import tempfile
import unittest
from pathlib import Path

import component_gate_runner


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


LLM_ENDPOINT_TEMPLATE = '''import json

RECORD_PATH = RECORD_PATH_PLACEHOLDER
CONFIG_PATH = CONFIG_PATH_PLACEHOLDER


class ModelResponse:
    def __init__(self, text, model, backend, model_call_error):
        self.text = text
        self.model = model
        self.backend = backend
        self.model_call_error = model_call_error


def complete(prompt, model, *, backend=None, **params):
    with open(RECORD_PATH, "a", encoding="utf-8") as f:
        f.write(prompt)
        f.write(chr(31))
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    kind = config["kind"]
    if kind == "pass_fenced":
        text = "```json\\n" + json.dumps({"result": "pass", "rationale": "ok"}) + "\\n```"
        return ModelResponse(text=text, model=model, backend="fake", model_call_error=None)
    if kind == "model_call_error":
        return ModelResponse(
            text=None, model=model, backend="fake",
            model_call_error={"category": "network", "message": "boom"},
        )
    if kind == "not_json":
        return ModelResponse(text="not json", model=model, backend="fake", model_call_error=None)
    if kind == "bad_result":
        return ModelResponse(
            text=json.dumps({"result": "maybe"}), model=model, backend="fake", model_call_error=None,
        )
    raise ValueError("unknown kind: " + kind)
'''

VERIFIER_ORCHESTRATOR_TEMPLATE = '''import json

OUTCOME_PATH = OUTCOME_PATH_PLACEHOLDER

GATE_VERSION = "verifier-orchestrator@2.0.0"


def _read(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def verify(component_id, repo_root, judge=None, test_author=None):
    bundle = {
        "component_id": component_id,
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "kind": "llm-judge",
        "criterion_text": "MARKER_CRIT",
        "requirement_text": "MARKER_REQ",
        "interface": "MARKER_IFACE",
        "glossary": "",
    }
    outcome = judge(bundle)
    result_value = _read(outcome, "result")
    rationale_value = _read(outcome, "rationale")
    with open(OUTCOME_PATH, "w", encoding="utf-8") as f:
        json.dump({"result": result_value, "rationale": rationale_value}, f)
    criterion_result = "pass" if result_value == "pass" else "fail"
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "llm-judge",
                "result": criterion_result,
                "rationale": rationale_value,
            }
        ],
        "requirement_results": {"R-FOO-001": criterion_result},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": criterion_result,
    }
'''

PROVENANCE_CHECKER_SOURCE = '''class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@3.1.0",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''

SPEC_BUNDLE_ASSEMBLER_SOURCE = '''def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "spec text",
        "interface": "interface text",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
'''

GENERATOR_SOURCE = '''def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "# MARKER_SOURCE\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

LICENSE_SCANNER_SOURCE = '''def scan(component_id, repo_root):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "license_scanner@3.1.0"
'''

SECRET_SCANNER_SOURCE = '''def scan(repo_root):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "secret_scanner@2.0.0"
'''

PROVENANCE_TRACKER_SOURCE = '''import os
import json


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id.replace("comp-", "", 1)
    attempts_dir = os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    os.makedirs(attempts_dir, exist_ok=True)
    record = {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
    with open(os.path.join(attempts_dir, "attempt.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, default=str)
    return record
'''

PROVENANCE_WRITER_SOURCE = '''def write_provenance(component_id, inputs, repo_root):
    return None
'''

COMPONENT_MD = '''---
id: comp-foo
title: Foo Fixture
status: draft
owners: [lselfors@gmail.com]
sealed: false
---

Purpose: Fixture component for AC-GATE-010.
'''


def _build_repo(response_kind):
    repo_root = Path(tempfile.mkdtemp(prefix="hotdocs-gate-"))

    _write(repo_root / "specs" / "components" / "foo" / "component.md", COMPONENT_MD)

    _write(repo_root / "gen" / "foo" / "foo.py", "# MARKER_SOURCE\n")

    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER_SOURCE)
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER_SOURCE)
    _write(repo_root / "gen" / "generator" / "generator.py", GENERATOR_SOURCE)
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", LICENSE_SCANNER_SOURCE)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_SOURCE)
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", PROVENANCE_TRACKER_SOURCE)
    _write(repo_root / "gen" / "provenance-writer" / "provenance_writer.py", PROVENANCE_WRITER_SOURCE)

    prompts_path = repo_root / "_prompts.jsonl"
    prompts_path.write_text("", encoding="utf-8")
    config_path = repo_root / "_llm_config.json"
    config_path.write_text(json.dumps({"kind": response_kind}), encoding="utf-8")
    outcome_path = repo_root / "_outcome.json"

    llm_endpoint_source = (
        LLM_ENDPOINT_TEMPLATE
        .replace("RECORD_PATH_PLACEHOLDER", repr(str(prompts_path)))
        .replace("CONFIG_PATH_PLACEHOLDER", repr(str(config_path)))
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", llm_endpoint_source)

    verifier_source = VERIFIER_ORCHESTRATOR_TEMPLATE.replace(
        "OUTCOME_PATH_PLACEHOLDER", repr(str(outcome_path))
    )
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", verifier_source)

    return repo_root, prompts_path, outcome_path


class JudgeClosureTest(unittest.TestCase):
    def test_judge_calls_llm_endpoint_with_all_markers_and_records_pass(self):
        repo_root, prompts_path, outcome_path = _build_repo("pass_fenced")
        self.addCleanup(shutil.rmtree, str(repo_root), True)

        component_gate_runner.run_component_gates(
            "comp-foo", repo_root, model="test-model", seed=0,
        )

        raw_prompts = prompts_path.read_text(encoding="utf-8")
        calls = [p for p in raw_prompts.split(chr(31)) if p]
        self.assertEqual(len(calls), 1)
        prompt = calls[0]
        for marker in ("MARKER_SOURCE", "MARKER_CRIT", "MARKER_REQ", "MARKER_IFACE"):
            self.assertIn(marker, prompt)

        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        self.assertEqual(outcome["result"], "pass")
        self.assertEqual(outcome["rationale"], "ok")

    def test_judge_reports_fail_on_model_call_error(self):
        self._assert_judge_unavailable("model_call_error")

    def test_judge_reports_fail_on_unparseable_text(self):
        self._assert_judge_unavailable("not_json")

    def test_judge_reports_fail_on_bad_result_value(self):
        self._assert_judge_unavailable("bad_result")

    def _assert_judge_unavailable(self, response_kind):
        repo_root, prompts_path, outcome_path = _build_repo(response_kind)
        self.addCleanup(shutil.rmtree, str(repo_root), True)

        component_gate_runner.run_component_gates(
            "comp-foo", repo_root, model="test-model", seed=0,
        )

        raw_prompts = prompts_path.read_text(encoding="utf-8")
        calls = [p for p in raw_prompts.split(chr(31)) if p]
        self.assertEqual(len(calls), 1)

        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        self.assertEqual(outcome["result"], "fail")
        self.assertTrue(outcome["rationale"].startswith("judge unavailable"))


if __name__ == "__main__":
    unittest.main()