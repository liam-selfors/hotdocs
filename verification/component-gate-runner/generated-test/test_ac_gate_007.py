import json
from pathlib import Path

import component_gate_runner


LOG_HELPER = r'''
import json
from pathlib import Path


def _log(repo_root, name):
    with open(Path(repo_root) / "call_log.txt", "a") as f:
        f.write(name + "\n")


def _cfg(repo_root):
    with open(Path(repo_root) / "fake_config.json") as f:
        return json.load(f)


def _dget(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
'''


PROVENANCE_CHECKER_SRC = LOG_HELPER + r'''

class SealedKey:
    def __init__(self, owners, source_path, source_hash, verifier_version):
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log(repo_root, "current_sealed_key")
    cfg = _cfg(repo_root)
    sk = cfg.get("sealed_key")
    if sk is None:
        return None
    return SealedKey(**sk)


def current_provenance_key(component_id, repo_root):
    _log(repo_root, "current_provenance_key")
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(repo_root, "check_provenance")
    cfg = _cfg(repo_root)
    if cfg.get("check_provenance_hit", False):
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
                "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
                "evaluated": True,
                "reason": None,
                "similarity_score": 0.0,
                "block_threshold": 0.7,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": True,
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
                "cache_hit": True,
            },
        }
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log(repo_root, "check_sealed_provenance")
    return {
        "hit": False,
        "sealed": False,
        "reason": "not_sealed",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }
'''


SPEC_BUNDLE_ASSEMBLER_SRC = LOG_HELPER + r'''

def assemble(component_id, repo_root, mode="cold"):
    _log(repo_root, "assemble")
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


def assemble_criterion(component_id, criterion_id, repo_root):
    _log(repo_root, "assemble_criterion")
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
    }
'''


GENERATOR_SRC = LOG_HELPER + r'''

def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log(repo_root, "generate")
    component_id = _dget(bundle, "component_id")
    spec_bundle_hash = _dget(bundle, "spec_bundle_hash")
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
'''


VERIFIER_ORCHESTRATOR_SRC = LOG_HELPER + r'''

GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    def __init__(self, component_id, overall, criteria):
        self.component_id = component_id
        self.overall = overall
        self.criteria = criteria
        self.requirement_results = {}
        self.interface_drift = False
        self.mutation_score = None

    def to_dict(self):
        return {
            "component_id": self.component_id,
            "criteria": self.criteria,
            "requirement_results": self.requirement_results,
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }


def verify(component_id, repo_root, judge=None, test_author=None):
    _log(repo_root, "verify")
    cfg = _cfg(repo_root)
    overall = cfg.get("verify_overall", "pass")
    result = "pass" if overall == "pass" else "fail"
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": result},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": result},
    ]
    return VerificationReport(component_id, overall, criteria)
'''


LICENSE_SCANNER_SRC = LOG_HELPER + r'''

def scan(component_id, repo_root):
    _log(repo_root, "license_scan")
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "license_scanner@4.0.3+9f2c41ab07de"
'''


SECRET_SCANNER_SRC = LOG_HELPER + r'''

def scan(repo_root):
    _log(repo_root, "secret_scan")
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


PROVENANCE_TRACKER_SRC = LOG_HELPER + r'''

def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log(repo_root, "write_attempt_record")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": None,
    }
'''


PROVENANCE_WRITER_SRC = LOG_HELPER + r'''

def _to_jsonable(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return _to_jsonable(to_dict())
    return _to_jsonable(vars(obj))


def write_provenance(component_id, inputs, repo_root):
    _log(repo_root, "write_provenance")


def write_sealed_provenance(component_id, inputs, repo_root):
    _log(repo_root, "write_sealed_provenance")
    record = {
        "component_id": component_id,
        "owners": _dget(inputs, "owners"),
        "source_path": _dget(inputs, "source_path"),
        "source_hash": _dget(inputs, "source_hash"),
        "verifier_version": _dget(inputs, "verifier_version"),
        "verification_report": _to_jsonable(_dget(inputs, "verification_report")),
    }
    with open(Path(repo_root) / "sealed_calls.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")
'''


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _dep_dir(repo_root, slug):
    return repo_root / "gen" / slug


def _write_fake_modules(repo_root):
    _write(_dep_dir(repo_root, "provenance-checker") / "provenance_checker.py", PROVENANCE_CHECKER_SRC)
    _write(_dep_dir(repo_root, "spec-bundle-assembler") / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER_SRC)
    _write(_dep_dir(repo_root, "generator") / "generator.py", GENERATOR_SRC)
    _write(_dep_dir(repo_root, "verifier-orchestrator") / "verifier_orchestrator.py", VERIFIER_ORCHESTRATOR_SRC)
    _write(_dep_dir(repo_root, "license-scanner") / "license_scanner.py", LICENSE_SCANNER_SRC)
    _write(_dep_dir(repo_root, "secret-scanner") / "secret_scanner.py", SECRET_SCANNER_SRC)
    _write(_dep_dir(repo_root, "provenance-tracker") / "provenance_tracker.py", PROVENANCE_TRACKER_SRC)
    _write(_dep_dir(repo_root, "provenance-writer") / "provenance_writer.py", PROVENANCE_WRITER_SRC)


def _setup_repo(tmp_path, sealed_key, verify_overall="pass", check_provenance_hit=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fake_modules(repo_root)

    config = {
        "sealed_key": sealed_key,
        "verify_overall": verify_overall,
        "check_provenance_hit": check_provenance_hit,
    }
    (repo_root / "fake_config.json").write_text(json.dumps(config))
    (repo_root / "call_log.txt").write_text("")
    return repo_root


def _read_log(repo_root):
    path = repo_root / "call_log.txt"
    if not path.exists():
        return []
    return [line for line in path.read_text().splitlines() if line]


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


SEALED_KEY_FIXTURE = {
    "owners": ["pipeline-team"],
    "source_path": "pipeline/foo/",
    "source_hash": "sha256:k",
    "verifier_version": "verifier-orchestrator@2.0.0",
}


def test_sealed_component_passing_skips_generation_and_writes_sealed_provenance(tmp_path):
    repo_root = _setup_repo(tmp_path, sealed_key=SEALED_KEY_FIXTURE, verify_overall="pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    log = _read_log(repo_root)

    for forbidden in (
        "check_provenance",
        "current_provenance_key",
        "assemble",
        "generate",
        "write_attempt_record",
        "write_provenance",
    ):
        assert forbidden not in log

    assert log.count("verify") == 1
    assert log.count("license_scan") == 1
    assert log.count("secret_scan") == 1
    assert log.count("write_sealed_provenance") == 1

    write_index = log.index("write_sealed_provenance")
    assert write_index > log.index("verify")
    assert write_index > log.index("license_scan")
    assert write_index > log.index("secret_scan")

    sealed_calls_path = repo_root / "sealed_calls.jsonl"
    lines = [line for line in sealed_calls_path.read_text().splitlines() if line]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["component_id"] == "comp-foo"
    assert record["owners"] == ["pipeline-team"]
    assert record["source_path"] == "pipeline/foo/"
    assert record["source_hash"] == "sha256:k"
    assert record["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert record["verification_report"]["overall"] == "pass"
    assert len(record["verification_report"]["criteria"]) == 2

    assert _get(result, "provenance_hit") is False
    assert _get(result, "blocked") is False


def test_sealed_component_failing_verification_still_writes_sealed_provenance(tmp_path):
    repo_root = _setup_repo(tmp_path, sealed_key=SEALED_KEY_FIXTURE, verify_overall="fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "verification_failed"

    log = _read_log(repo_root)
    assert log.count("write_sealed_provenance") == 1

    sealed_calls_path = repo_root / "sealed_calls.jsonl"
    lines = [line for line in sealed_calls_path.read_text().splitlines() if line]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["component_id"] == "comp-foo"
    assert record["owners"] == ["pipeline-team"]
    assert record["source_path"] == "pipeline/foo/"
    assert record["source_hash"] == "sha256:k"
    assert record["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert record["verification_report"]["overall"] == "fail"


def test_non_sealed_component_runs_full_pipeline_and_never_writes_sealed_provenance(tmp_path):
    repo_root = _setup_repo(tmp_path, sealed_key=None, verify_overall="pass", check_provenance_hit=False)

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    log = _read_log(repo_root)

    assert "write_sealed_provenance" not in log

    for expected in (
        "current_provenance_key",
        "check_provenance",
        "assemble",
        "generate",
        "verify",
        "license_scan",
        "secret_scan",
        "write_attempt_record",
        "write_provenance",
    ):
        assert expected in log

    assert not (repo_root / "sealed_calls.jsonl").exists()