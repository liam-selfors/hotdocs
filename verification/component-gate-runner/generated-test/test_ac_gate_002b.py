import json

import component_gate_runner


def _write_module(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


PROVENANCE_CHECKER_SRC = '''
class _ProvenanceKey:
    def __init__(self):
        self.spec_bundle_hash = "sha256:" + "0" * 64
        self.gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        }


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return _ProvenanceKey()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''

SPEC_BUNDLE_ASSEMBLER_SRC = '''
import json
import os


def assemble(component_id, repo_root, mode="cold"):
    bundle = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "1" * 64,
        "spec": "spec text",
        "interface": "interface text",
        "constraints": "constraints text",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "glossary text",
        "hint_code": None,
    }
    log_path = os.environ["HOTDOCS_TEST_LOG_PATH"]
    with open(log_path, "a") as f:
        f.write(json.dumps({"call": "assemble", "mode": mode, "bundle": bundle}) + "\\n")
    return bundle
'''

GENERATOR_SRC = '''
import json
import os


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        bundle_plain = bundle
    else:
        bundle_plain = vars(bundle)
    log_path = os.environ["HOTDOCS_TEST_LOG_PATH"]
    with open(log_path, "a") as f:
        f.write(json.dumps({
            "call": "generate",
            "model": model,
            "retry_feedback": retry_feedback,
            "bundle": bundle_plain,
        }) + "\\n")
    return {
        "component_id": bundle_plain.get("component_id"),
        "spec_bundle_hash": bundle_plain.get("spec_bundle_hash"),
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "# generated content"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

VERIFIER_ORCHESTRATOR_SRC = '''
import json
import os

GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    log_path = os.environ["HOTDOCS_TEST_LOG_PATH"]
    with open(log_path, "a") as f:
        f.write(json.dumps({"call": "verify", "component_id": component_id}) + "\\n")
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
def scan(component_id, repo_root):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"
'''

SECRET_SCANNER_SRC = '''
def scan(repo_root):
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
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"
'''

PROVENANCE_TRACKER_SRC = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''

PROVENANCE_WRITER_SRC = '''
def write_provenance(component_id, inputs, repo_root):
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
'''


def test_ac_gate_002b_cold_miss_call_order_and_args(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.log"
    monkeypatch.setenv("HOTDOCS_TEST_LOG_PATH", str(log_path))

    _write_module(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER_SRC)
    _write_module(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER_SRC)
    _write_module(repo_root / "gen" / "generator" / "generator.py", GENERATOR_SRC)
    _write_module(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", VERIFIER_ORCHESTRATOR_SRC)
    _write_module(repo_root / "gen" / "license-scanner" / "license_scanner.py", LICENSE_SCANNER_SRC)
    _write_module(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_SRC)
    _write_module(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", PROVENANCE_TRACKER_SRC)
    _write_module(repo_root / "gen" / "provenance-writer" / "provenance_writer.py", PROVENANCE_WRITER_SRC)

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", retry_feedback=["R-FOO-002"],
    )

    raw_lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    entries = [json.loads(line) for line in raw_lines]

    call_sequence = [e["call"] for e in entries if e["call"] in ("assemble", "generate", "verify")]
    assert call_sequence == ["assemble", "generate", "verify"]

    assemble_entry = next(e for e in entries if e["call"] == "assemble")
    assert assemble_entry["mode"] == "cold"

    generate_entry = next(e for e in entries if e["call"] == "generate")
    assert generate_entry["model"] == "m"
    assert generate_entry["retry_feedback"] == ["R-FOO-002"]
    assert generate_entry["bundle"] == assemble_entry["bundle"]