import json
import tempfile
import unittest
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _read_log(log_path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [acme-team]
---

# Foo

## Purpose

A fixture component used to test component-gate-runner's gates.
"""


PROVENANCE_CHECKER_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "provenance_checker", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)

    class _Key:
        spec_bundle_hash = "sha256:k"
        gate_versions = {"verifier": "v@1"}

    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        "check_provenance",
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        gate_versions=gate_versions,
    )
    verification_report = {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": __OVERALL__,
    }
    license_scan = {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0+abc123456789",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }
    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }
    return {
        "hit": True,
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }
'''


SPEC_BUNDLE_ASSEMBLER_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "spec_bundle_assembler", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:k",
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


GENERATOR_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "generator", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        component_id = bundle["component_id"]
    else:
        component_id = bundle.component_id
    _log("generate", component_id=component_id, model=model)
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:k",
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "simulated failure"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''


VERIFIER_ORCHESTRATOR_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "verifier_orchestrator", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
'''


LICENSE_SCANNER_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "license_scanner", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def scan(component_id, repo_root):
    _log("scan", component_id=component_id)
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0+abc123456789",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    _log("gate_version")
    return "license_scanner@4.0.0+abc123456789"
'''


SECRET_SCANNER_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "secret_scanner", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def scan(repo_root):
    _log("scan")
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    _log("gate_version")
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"
'''


PROVENANCE_TRACKER_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "provenance_tracker", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''


PROVENANCE_WRITER_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "provenance_writer", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''


TEST_AUTHOR_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "test_author", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
    _log("author_test", model=model, seed=seed)
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py", "content": ""},
        "model_call_error": None,
    }
'''


LLM_ENDPOINT_SRC = '''
import json

LOG_PATH = __LOG_PATH__


def _log(func, **kwargs):
    rec = {"module": "llm_endpoint", "func": func}
    rec.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def complete(prompt, model, backend=None, **params):
    _log("complete", model=model)
    return {
        "text": "ok",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
'''


def _build_repo(tmp_path, log_path, overall):
    repo_root = tmp_path / "repo"
    _write(repo_root / "specs" / "components" / "foo" / "component.md", COMPONENT_MD)

    modules = {
        "provenance-checker": (
            "provenance_checker",
            PROVENANCE_CHECKER_SRC.replace("__OVERALL__", json.dumps(overall)),
        ),
        "spec-bundle-assembler": ("spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SRC),
        "generator": ("generator", GENERATOR_SRC),
        "verifier-orchestrator": ("verifier_orchestrator", VERIFIER_ORCHESTRATOR_SRC),
        "license-scanner": ("license_scanner", LICENSE_SCANNER_SRC),
        "secret-scanner": ("secret_scanner", SECRET_SCANNER_SRC),
        "provenance-tracker": ("provenance_tracker", PROVENANCE_TRACKER_SRC),
        "provenance-writer": ("provenance_writer", PROVENANCE_WRITER_SRC),
        "test-author": ("test_author", TEST_AUTHOR_SRC),
        "llm-endpoint": ("llm_endpoint", LLM_ENDPOINT_SRC),
    }
    for slug, (module_name, src) in modules.items():
        content = src.replace("__LOG_PATH__", json.dumps(str(log_path)))
        _write(repo_root / "gen" / slug / (module_name + ".py"), content)

    return repo_root


class ProvenanceHitShortCircuitTest(unittest.TestCase):
    def test_passing_hit_short_circuits_and_skips_other_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            log_path = tmp_path / "invocations.jsonl"
            repo_root = _build_repo(tmp_path, log_path, overall="pass")

            result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

            records = _read_log(log_path)
            modules_called = {r["module"] for r in records}
            self.assertEqual(modules_called, {"provenance_checker"})

            check_calls = [r for r in records if r["func"] == "check_provenance"]
            self.assertEqual(len(check_calls), 1)
            self.assertEqual(check_calls[0]["spec_bundle_hash"], "sha256:k")
            self.assertEqual(check_calls[0]["gate_versions"], {"verifier": "v@1"})

            self.assertIs(_get(result, "provenance_hit"), True)
            self.assertIs(_get(result, "blocked"), False)

            verification = _get(result, "verification")
            self.assertEqual(_get(verification, "component_id"), "comp-foo")
            self.assertEqual(_get(verification, "overall"), "pass")
            self.assertEqual(_get(verification, "criteria"), [])
            self.assertEqual(_get(verification, "requirement_results"), {})

    def test_failing_verification_hit_proceeds_as_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            log_path = tmp_path / "invocations.jsonl"
            repo_root = _build_repo(tmp_path, log_path, overall="fail")

            result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

            records = _read_log(log_path)
            generate_calls = [
                r for r in records if r["module"] == "generator" and r["func"] == "generate"
            ]
            self.assertEqual(len(generate_calls), 1)

            self.assertIs(_get(result, "provenance_hit"), False)


if __name__ == "__main__":
    unittest.main()