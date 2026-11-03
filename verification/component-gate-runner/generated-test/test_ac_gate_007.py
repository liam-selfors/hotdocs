import json

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _read_calls(call_log):
    if not call_log.exists():
        return []
    return [line for line in call_log.read_text().splitlines() if line]


PROVENANCE_CHECKER_SEALED_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


class SealedKey:
    def __init__(self, owners, source_path, source_hash, verifier_version):
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key")
    if component_id == "comp-foo":
        return SealedKey(
            owners=["pipeline-team"],
            source_path="pipeline/foo/",
            source_hash="sha256:k",
            verifier_version="verifier-orchestrator@2.0.0",
        )
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key")
    raise AssertionError("current_provenance_key must never be called for a sealed component")


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance")
    raise AssertionError("check_provenance must never be called for a sealed component")
"""


PROVENANCE_CHECKER_UNSEALED_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key")
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key")
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0",
            "secret_scanner": "secret_scanner@3.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance")
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
"""


VERIFIER_ORCHESTRATOR_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)

GATE_VERSION = "verifier-orchestrator@2.0.0"


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


class _Report:
    def __init__(self, overall, criteria):
        self.component_id = "comp-foo"
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
    _log("verify")
    overall = __OVERALL_REPR__
    if overall == "pass":
        criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ]
    else:
        criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail"},
        ]
    return _Report(overall, criteria)
"""


LICENSE_SCANNER_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


def scan(component_id, repo_root):
    _log("license_scan")
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3",
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
    return "license_scanner@4.0.3"
"""


SECRET_SCANNER_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


class _SecretScanResult:
    def __init__(self):
        self.scope = "full"
        self.gate_version = "secret_scanner@3.0.0+detect-secrets.1.5.0"
        self.flagged = False
        self.matches = []
        self.allowed = []
        self.unused_allowlist_entries = []
        self.notified = False
        self.notification_delivery_error = None
        self.cache_hit = False

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
    _log("secret_scan")
    return _SecretScanResult()


def gate_version(repo_root):
    return "secret_scanner@3.0.0+detect-secrets.1.5.0"
"""


PROVENANCE_WRITER_SEALED_TEMPLATE = """
import json
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)
RECORD_PATH = Path(__RECORD_PATH_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance")
    report = _get(inputs, "verification_report")
    record = {
        "component_id": _get(inputs, "component_id"),
        "owners": _get(inputs, "owners"),
        "source_path": _get(inputs, "source_path"),
        "source_hash": _get(inputs, "source_hash"),
        "verifier_version": _get(inputs, "verifier_version"),
        "verification_overall": _get(report, "overall"),
        "verification_criteria": _get(report, "criteria"),
    }
    RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RECORD_PATH, "w") as f:
        json.dump(record, f)


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance")
    raise AssertionError("write_provenance must never be called for a sealed component")
"""


PROVENANCE_WRITER_UNSEALED_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance")
    raise AssertionError("write_sealed_provenance must never be called for a non-sealed component")


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance")
"""


ASSEMBLER_FORBIDDEN_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


def assemble(component_id, repo_root=None, mode="cold"):
    _log("assemble")
    raise AssertionError("assemble must never be called for a sealed component")
"""


ASSEMBLER_OK_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


class _Bundle:
    def __init__(self, component_id, spec_bundle_hash):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash


def assemble(component_id, repo_root=None, mode="cold"):
    _log("assemble")
    return _Bundle(component_id, "sha256:" + "a" * 64)
"""


GENERATOR_FORBIDDEN_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate")
    raise AssertionError("generate must never be called for a sealed component")
"""


GENERATOR_OK_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


class _GenerationResult:
    def __init__(self):
        self.component_id = "comp-foo"
        self.spec_bundle_hash = "sha256:" + "a" * 64
        self.model = "m"
        self.prompt_version = "v1"
        self.cache_hit = False
        self.files = {"foo.py": "print('hi')\\n"}
        self.model_call_error = None
        self.refused = None
        self.retry_feedback = None


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate")
    return _GenerationResult()
"""


TRACKER_FORBIDDEN_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record")
    raise AssertionError("write_attempt_record must never be called for a sealed component")
"""


TRACKER_OK_TEMPLATE = """
from pathlib import Path

CALL_LOG = Path(__CALL_LOG_REPR__)


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\\n")


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record")
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (attempts_dir / "attempt-0001.json").write_text("{}")
    return {
        "attempt_id": "2026-11-02T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-11-02T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": {},
    }
"""


def _setup_sealed_repo(tmp_path, overall):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    call_log = tmp_path / "calls.log"
    call_log.write_text("")
    record_path = tmp_path / "sealed_record.json"

    call_log_repr = repr(str(call_log))
    record_path_repr = repr(str(record_path))
    overall_repr = repr(overall)

    pc_code = PROVENANCE_CHECKER_SEALED_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", pc_code)

    vo_code = VERIFIER_ORCHESTRATOR_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    vo_code = vo_code.replace("__OVERALL_REPR__", overall_repr)
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", vo_code)

    lic_code = LICENSE_SCANNER_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", lic_code)

    sec_code = SECRET_SCANNER_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", sec_code)

    pw_code = PROVENANCE_WRITER_SEALED_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    pw_code = pw_code.replace("__RECORD_PATH_REPR__", record_path_repr)
    _write(repo_root / "gen" / "provenance-writer" / "provenance_writer.py", pw_code)

    asm_code = ASSEMBLER_FORBIDDEN_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", asm_code)

    gen_code = GENERATOR_FORBIDDEN_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "generator" / "generator.py", gen_code)

    track_code = TRACKER_FORBIDDEN_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", track_code)

    return repo_root, call_log, record_path


def test_sealed_component_pass_writes_sealed_provenance_and_is_not_blocked(tmp_path):
    repo_root, call_log, record_path = _setup_sealed_repo(tmp_path, "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_calls(call_log)

    assert calls.count("check_provenance") == 0
    assert calls.count("current_provenance_key") == 0
    assert calls.count("assemble") == 0
    assert calls.count("generate") == 0
    assert calls.count("write_attempt_record") == 0
    assert calls.count("write_provenance") == 0

    assert calls.count("verify") == 1
    assert calls.count("license_scan") == 1
    assert calls.count("secret_scan") == 1
    assert calls.count("write_sealed_provenance") == 1

    write_index = calls.index("write_sealed_provenance")
    assert calls.index("verify") < write_index
    assert calls.index("license_scan") < write_index
    assert calls.index("secret_scan") < write_index

    assert record_path.exists()
    record = json.loads(record_path.read_text())
    assert record["component_id"] == "comp-foo"
    assert record["owners"] == ["pipeline-team"]
    assert record["source_path"] == "pipeline/foo/"
    assert record["source_hash"] == "sha256:k"
    assert record["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert record["verification_overall"] == "pass"
    assert len(record["verification_criteria"]) == 2

    assert _get(result, "provenance_hit") is False
    assert _get(result, "blocked") is False


def test_sealed_component_verification_failure_blocks_but_still_writes(tmp_path):
    repo_root, call_log, record_path = _setup_sealed_repo(tmp_path, "fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_calls(call_log)
    assert calls.count("write_sealed_provenance") == 1

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "verification_failed"

    record = json.loads(record_path.read_text())
    assert record["verification_overall"] == "fail"


def test_unsealed_component_does_not_write_sealed_provenance(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    call_log = tmp_path / "calls.log"
    call_log.write_text("")

    call_log_repr = repr(str(call_log))

    pc_code = PROVENANCE_CHECKER_UNSEALED_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", pc_code)

    asm_code = ASSEMBLER_OK_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", asm_code)

    gen_code = GENERATOR_OK_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "generator" / "generator.py", gen_code)

    vo_code = VERIFIER_ORCHESTRATOR_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    vo_code = vo_code.replace("__OVERALL_REPR__", repr("pass"))
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", vo_code)

    lic_code = LICENSE_SCANNER_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", lic_code)

    sec_code = SECRET_SCANNER_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", sec_code)

    track_code = TRACKER_OK_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", track_code)

    pw_code = PROVENANCE_WRITER_UNSEALED_TEMPLATE.replace("__CALL_LOG_REPR__", call_log_repr)
    _write(repo_root / "gen" / "provenance-writer" / "provenance_writer.py", pw_code)

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_calls(call_log)
    assert "write_sealed_provenance" not in calls
    assert calls.count("current_sealed_key") == 1
    assert calls.count("current_provenance_key") >= 1
    assert calls.count("check_provenance") >= 1
    assert calls.count("assemble") >= 1
    assert calls.count("generate") >= 1
    assert calls.count("verify") >= 1
    assert calls.count("license_scan") >= 1
    assert calls.count("secret_scan") >= 1
    assert calls.count("write_attempt_record") >= 1
    assert calls.count("write_provenance") >= 1