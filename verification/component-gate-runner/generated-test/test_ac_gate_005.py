import json
import os
from pathlib import Path

import component_gate_runner


def get_field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def write_module(repo_root, slug, module_name, content):
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(content)


PROVENANCE_CHECKER_MISS = '''
def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    class _Key:
        spec_bundle_hash = "sha256:" + "0" * 64
        gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        }
    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''


SPEC_BUNDLE_ASSEMBLER = '''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "spec": "",
        "interface": "",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
'''


GENERATOR_MODEL_CALL_ERROR = '''
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    bundle_hash = (
        bundle.get("spec_bundle_hash")
        if isinstance(bundle, dict)
        else getattr(bundle, "spec_bundle_hash", None)
    )
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "connection refused"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''


LICENSE_SCANNER_SPY = '''
import json
import os

LOG_PATH = os.environ["TEST_LICENSE_SCANNER_LOG"]


def scan(component_id, repo_root):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"component_id": component_id, "repo_root": str(repo_root)}) + "\\n")
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


SECRET_SCANNER_SPY = '''
import json
import os

LOG_PATH = os.environ["TEST_SECRET_SCANNER_LOG"]


def scan(repo_root):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"repo_root": str(repo_root)}) + "\\n")
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


PROVENANCE_TRACKER_WRITE_ATTEMPT = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''


PROVENANCE_CHECKER_HIT = '''
def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    class _Key:
        spec_bundle_hash = "sha256:" + "0" * 64
        gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        }
    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        },
        "license_scan": {
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
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }
'''


def test_miss_with_model_call_error_calls_both_scanners(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    write_module(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_MISS)
    write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER)
    write_module(repo_root, "generator", "generator", GENERATOR_MODEL_CALL_ERROR)
    write_module(repo_root, "license-scanner", "license_scanner", LICENSE_SCANNER_SPY)
    write_module(repo_root, "secret-scanner", "secret_scanner", SECRET_SCANNER_SPY)
    write_module(repo_root, "provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_WRITE_ATTEMPT)

    license_log = tmp_path / "license_scan.log"
    secret_log = tmp_path / "secret_scan.log"

    old_license_env = os.environ.get("TEST_LICENSE_SCANNER_LOG")
    old_secret_env = os.environ.get("TEST_SECRET_SCANNER_LOG")
    os.environ["TEST_LICENSE_SCANNER_LOG"] = str(license_log)
    os.environ["TEST_SECRET_SCANNER_LOG"] = str(secret_log)
    try:
        result = component_gate_runner.run_component_gates(
            "comp-foo", repo_root, model="claude-sonnet-5",
        )
    finally:
        if old_license_env is None:
            os.environ.pop("TEST_LICENSE_SCANNER_LOG", None)
        else:
            os.environ["TEST_LICENSE_SCANNER_LOG"] = old_license_env
        if old_secret_env is None:
            os.environ.pop("TEST_SECRET_SCANNER_LOG", None)
        else:
            os.environ["TEST_SECRET_SCANNER_LOG"] = old_secret_env

    assert license_log.exists()
    license_calls = [json.loads(line) for line in license_log.read_text().splitlines() if line]
    assert len(license_calls) == 1
    assert license_calls[0]["component_id"] == "comp-foo"
    assert Path(license_calls[0]["repo_root"]) == repo_root

    assert secret_log.exists()
    secret_calls = [json.loads(line) for line in secret_log.read_text().splitlines() if line]
    assert len(secret_calls) == 1
    assert Path(secret_calls[0]["repo_root"]) == repo_root

    license_scan_result = get_field(result, "license_scan")
    secret_scan_result = get_field(result, "secret_scan")
    assert get_field(license_scan_result, "gate_version") == "license_scanner@4.0.0-no-reference-corpus"
    assert get_field(license_scan_result, "evaluated") is False
    assert get_field(license_scan_result, "reason") == "no-reference-corpus"
    assert get_field(secret_scan_result, "scope") == "full"
    assert get_field(secret_scan_result, "gate_version") == "secret_scanner@3.1.0+detect-secrets.1.5.0"
    assert get_field(secret_scan_result, "flagged") is False


def test_short_circuiting_hit_calls_neither_scanner(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    write_module(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_HIT)
    write_module(repo_root, "license-scanner", "license_scanner", LICENSE_SCANNER_SPY)
    write_module(repo_root, "secret-scanner", "secret_scanner", SECRET_SCANNER_SPY)

    license_log = tmp_path / "license_scan.log"
    secret_log = tmp_path / "secret_scan.log"

    old_license_env = os.environ.get("TEST_LICENSE_SCANNER_LOG")
    old_secret_env = os.environ.get("TEST_SECRET_SCANNER_LOG")
    os.environ["TEST_LICENSE_SCANNER_LOG"] = str(license_log)
    os.environ["TEST_SECRET_SCANNER_LOG"] = str(secret_log)
    try:
        result = component_gate_runner.run_component_gates(
            "comp-foo", repo_root, model="claude-sonnet-5",
        )
    finally:
        if old_license_env is None:
            os.environ.pop("TEST_LICENSE_SCANNER_LOG", None)
        else:
            os.environ["TEST_LICENSE_SCANNER_LOG"] = old_license_env
        if old_secret_env is None:
            os.environ.pop("TEST_SECRET_SCANNER_LOG", None)
        else:
            os.environ["TEST_SECRET_SCANNER_LOG"] = old_secret_env

    assert not license_log.exists()
    assert not secret_log.exists()
    assert get_field(result, "provenance_hit") is True