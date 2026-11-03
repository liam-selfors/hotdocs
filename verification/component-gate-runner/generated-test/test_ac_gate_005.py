import json
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_fake_module(repo_root: Path, slug: str, module_name: str, source: str) -> None:
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(source)


def _read_calls(call_log_path: Path):
    if not call_log_path.exists():
        return []
    return [json.loads(line) for line in call_log_path.read_text().splitlines() if line.strip()]


PROVENANCE_CHECKER_MISS_SRC = """
import json
import os


def _log(fn, args):
    with open(os.environ["GATE_TEST_CALL_LOG"], "a") as f:
        f.write(json.dumps({"module": "provenance_checker", "fn": fn, "args": args}) + "\\n")


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", {"component_id": component_id, "repo_root": str(repo_root)})
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", {"component_id": component_id, "repo_root": str(repo_root)})
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
    _log("check_provenance", {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gate_versions,
        "repo_root": str(repo_root),
    })
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
"""


PROVENANCE_CHECKER_HIT_SRC = """
import json
import os


def _log(fn, args):
    with open(os.environ["GATE_TEST_CALL_LOG"], "a") as f:
        f.write(json.dumps({"module": "provenance_checker", "fn": fn, "args": args}) + "\\n")


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", {"component_id": component_id, "repo_root": str(repo_root)})
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", {"component_id": component_id, "repo_root": str(repo_root)})
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
    _log("check_provenance", {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gate_versions,
        "repo_root": str(repo_root),
    })
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
            "gate_version": "license_scanner@4.0.3",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": True,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": True,
        },
    }
"""


SPEC_BUNDLE_ASSEMBLER_SRC = """
import json
import os


def _log(fn, args):
    with open(os.environ["GATE_TEST_CALL_LOG"], "a") as f:
        f.write(json.dumps({"module": "spec_bundle_assembler", "fn": fn, "args": args}) + "\\n")


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", {"component_id": component_id, "repo_root": str(repo_root), "mode": mode})
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "b" * 64,
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
"""


GENERATOR_MODEL_ERROR_SRC = """
import json
import os


def _log(fn, args):
    with open(os.environ["GATE_TEST_CALL_LOG"], "a") as f:
        f.write(json.dumps({"module": "generator", "fn": fn, "args": args}) + "\\n")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    component_id = _get(bundle, "component_id")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    _log("generate", {
        "component_id": component_id,
        "model": model,
        "retry_feedback": retry_feedback,
        "repo_root": str(repo_root),
    })
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "fake network failure"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


LICENSE_SCANNER_SRC = """
import json
import os


def _log(fn, args):
    with open(os.environ["GATE_TEST_CALL_LOG"], "a") as f:
        f.write(json.dumps({"module": "license_scanner", "fn": fn, "args": args}) + "\\n")


def scan(component_id, repo_root):
    _log("scan", {"component_id": component_id, "repo_root": str(repo_root)})
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "license_scanner@4.0.3"
"""


SECRET_SCANNER_SRC = """
import json
import os
from dataclasses import dataclass


def _log(fn, args):
    with open(os.environ["GATE_TEST_CALL_LOG"], "a") as f:
        f.write(json.dumps({"module": "secret_scanner", "fn": fn, "args": args}) + "\\n")


@dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool
    matches: list
    allowed: list
    unused_allowlist_entries: list
    notified: bool
    notification_delivery_error: object
    cache_hit: bool

    def to_dict(self):
        return {
            "scope": self.scope,
            "gate_version": self.gate_version,
            "flagged": self.flagged,
            "matches": self.matches,
            "allowed": self.allowed,
            "unused_allowlist_entries": self.unused_allowlist_entries,
            "notified": self.notified,
            "notification_delivery_error": self.notification_delivery_error,
            "cache_hit": self.cache_hit,
        }


def scan(repo_root):
    _log("scan", {"repo_root": str(repo_root)})
    return SecretScanResult(
        scope="full",
        gate_version="secret_scanner@3.0.0+detect-secrets.1.5.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def gate_version(repo_root):
    return "secret_scanner@3.0.0+detect-secrets.1.5.0"
"""


PROVENANCE_TRACKER_SRC = """
import json
import os


def _log(fn, args):
    with open(os.environ["GATE_TEST_CALL_LOG"], "a") as f:
        f.write(json.dumps({"module": "provenance_tracker", "fn": fn, "args": args}) + "\\n")


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "repo_root": str(repo_root),
        "has_verification_report": verification_report is not None,
    })
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result if isinstance(generation_result, dict) else {},
        "verification": None,
    }
"""


def test_miss_with_model_call_error_runs_both_scanners_and_carries_results(tmp_path, monkeypatch):
    repo_root = tmp_path
    call_log_path = repo_root / "calls.log"
    monkeypatch.setenv("GATE_TEST_CALL_LOG", str(call_log_path))

    _write_fake_module(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_MISS_SRC)
    _write_fake_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
    _write_fake_module(repo_root, "generator", "generator", GENERATOR_MODEL_ERROR_SRC)
    _write_fake_module(repo_root, "license-scanner", "license_scanner", LICENSE_SCANNER_SRC)
    _write_fake_module(repo_root, "secret-scanner", "secret_scanner", SECRET_SCANNER_SRC)
    _write_fake_module(repo_root, "provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_SRC)

    result = component_gate_runner.run_component_gates(
        component_id="comp-foo",
        repo_root=repo_root,
        model="fake-model",
    )

    assert _get(result, "provenance_hit") is False
    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "model_call_error"

    license_scan = _get(result, "license_scan")
    secret_scan = _get(result, "secret_scan")
    assert _get(license_scan, "component_id") == "comp-foo"
    assert _get(license_scan, "gate_version") == "license_scanner@4.0.3"
    assert _get(license_scan, "evaluated") is True
    assert _get(secret_scan, "scope") == "full"
    assert _get(secret_scan, "gate_version") == "secret_scanner@3.0.0+detect-secrets.1.5.0"
    assert _get(secret_scan, "flagged") is False

    calls = _read_calls(call_log_path)
    license_calls = [c for c in calls if c["module"] == "license_scanner" and c["fn"] == "scan"]
    secret_calls = [c for c in calls if c["module"] == "secret_scanner" and c["fn"] == "scan"]

    assert len(license_calls) == 1
    assert license_calls[0]["args"]["component_id"] == "comp-foo"
    assert license_calls[0]["args"]["repo_root"] == str(repo_root)

    assert len(secret_calls) == 1
    assert secret_calls[0]["args"]["repo_root"] == str(repo_root)


def test_short_circuiting_hit_calls_neither_scanner(tmp_path, monkeypatch):
    repo_root = tmp_path
    call_log_path = repo_root / "calls.log"
    monkeypatch.setenv("GATE_TEST_CALL_LOG", str(call_log_path))

    _write_fake_module(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_HIT_SRC)
    _write_fake_module(repo_root, "license-scanner", "license_scanner", LICENSE_SCANNER_SRC)
    _write_fake_module(repo_root, "secret-scanner", "secret_scanner", SECRET_SCANNER_SRC)

    result = component_gate_runner.run_component_gates(
        component_id="comp-foo",
        repo_root=repo_root,
        model="fake-model",
    )

    assert _get(result, "provenance_hit") is True
    assert _get(result, "blocked") is False

    calls = _read_calls(call_log_path)
    scanner_calls = [c for c in calls if c["module"] in ("license_scanner", "secret_scanner")]
    assert scanner_calls == []