import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup_common_fakes(repo_root, log_path, capture_path):
    gen = repo_root / "gen"

    _write(gen / "provenance-checker" / "provenance_checker.py", '''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey("sha256:" + "0" * 64, {"verifier": "v@1"})


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
''')

    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", '''
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "1" * 64,
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
''')

    log_repr = repr(str(log_path))
    capture_repr = repr(str(capture_path))

    _write(gen / "license-scanner" / "license_scanner.py", f'''
def scan(component_id, repo_root):
    with open({log_repr}, "a") as f:
        f.write("license_scan\\n")
    return {{
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
    }}
''')

    _write(gen / "secret-scanner" / "secret_scanner.py", f'''
def scan(repo_root):
    with open({log_repr}, "a") as f:
        f.write("secret_scan\\n")
    return {{
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }}
''')

    _write(gen / "provenance-tracker" / "provenance_tracker.py", f'''
from pathlib import Path

def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    with open({log_repr}, "a") as f:
        f.write("write_attempt_record\\n")
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (attempts_dir / "attempt-0001.json").write_text("{{}}")
    return {{
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }}
''')

    _write(gen / "provenance-writer" / "provenance_writer.py", f'''
import json


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def write_provenance(component_id, inputs, repo_root):
    with open({log_repr}, "a") as f:
        f.write("write_provenance\\n")
    capture = {{
        "component_id": _get(inputs, "component_id"),
        "generation_result": _get(inputs, "generation_result"),
        "verification_report": _get(inputs, "verification_report"),
        "license_scan_result": _get(inputs, "license_scan_result"),
        "secret_scan_result": _get(inputs, "secret_scan_result"),
        "provenance_hit": _get(inputs, "provenance_hit"),
        "attempts": _get(inputs, "attempts"),
        "gate_versions": _get(inputs, "gate_versions"),
    }}
    with open({capture_repr}, "a") as f:
        f.write(json.dumps(capture) + "\\n")
''')


def _write_generator_success(repo_root):
    gen = repo_root / "gen"
    _write(gen / "generator" / "generator.py", '''
def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    component_id = bundle["component_id"] if isinstance(bundle, dict) else bundle.component_id
    spec_bundle_hash = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else bundle.spec_bundle_hash
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hi')"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
''')


def _write_generator_model_call_error(repo_root):
    gen = repo_root / "gen"
    _write(gen / "generator" / "generator.py", '''
def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    component_id = bundle["component_id"] if isinstance(bundle, dict) else bundle.component_id
    spec_bundle_hash = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else bundle.spec_bundle_hash
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
''')


def _write_verifier_pass(repo_root):
    gen = repo_root / "gen"
    _write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", '''
def verify(component_id, repo_root, judge=None, test_author=None):
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
''')


def test_miss_with_files_writes_provenance_after_scans_and_attempt_record(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "log.txt"
    capture_path = tmp_path / "capture.jsonl"

    _setup_common_fakes(repo_root, log_path, capture_path)
    _write_generator_success(repo_root)
    _write_verifier_pass(repo_root)

    component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "test-model", seed=0,
    )

    assert capture_path.exists()
    capture_lines = capture_path.read_text().splitlines()
    assert len(capture_lines) == 1
    captured = json.loads(capture_lines[0])

    assert captured["gate_versions"] == {"verifier": "v@1"}
    assert captured["provenance_hit"] is False
    assert captured["attempts"] == 1
    assert captured["generation_result"]["files"] == {"foo.py": "print('hi')"}
    assert captured["generation_result"]["model_call_error"] is None
    assert captured["verification_report"]["overall"] == "pass"
    assert captured["license_scan_result"]["evaluated"] is False
    assert captured["license_scan_result"]["reason"] == "no-reference-corpus"
    assert captured["secret_scan_result"]["flagged"] is False

    log_lines = log_path.read_text().splitlines()
    assert "license_scan" in log_lines
    assert "secret_scan" in log_lines
    assert "write_attempt_record" in log_lines
    assert "write_provenance" in log_lines

    write_provenance_index = log_lines.index("write_provenance")
    assert write_provenance_index > log_lines.index("license_scan")
    assert write_provenance_index > log_lines.index("secret_scan")
    assert write_provenance_index > log_lines.index("write_attempt_record")


def test_model_call_error_skips_provenance_write(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "log.txt"
    capture_path = tmp_path / "capture.jsonl"

    _setup_common_fakes(repo_root, log_path, capture_path)
    _write_generator_model_call_error(repo_root)

    component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "test-model", seed=0,
    )

    assert not capture_path.exists()