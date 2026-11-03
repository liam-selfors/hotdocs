import json
from pathlib import Path

import component_gate_runner


_PROVENANCE_CHECKER_SRC = r'''
CALL_LOG = __CALL_LOG_PATH__


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\n")


class _Key(object):
    def __init__(self):
        self.spec_bundle_hash = "sha256:" + "a" * 64
        self.gate_versions = {"verifier": "v@1"}


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key")
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key")
    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance")
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}
'''


_SPEC_BUNDLE_ASSEMBLER_SRC = r'''
CALL_LOG = __CALL_LOG_PATH__


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\n")


def assemble(component_id, repo_root=None, mode="cold"):
    _log("assemble")
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
'''


_GENERATOR_SRC = r'''
CALL_LOG = __CALL_LOG_PATH__


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\n")


def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    _log("generate")
    if isinstance(bundle, dict):
        component_id = bundle["component_id"]
    else:
        component_id = bundle.component_id
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "b" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": __FILES__,
        "model_call_error": __MODEL_CALL_ERROR__,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''


_VERIFIER_ORCHESTRATOR_SRC = r'''
CALL_LOG = __CALL_LOG_PATH__

GATE_VERSION = "verifier-orchestrator@2.0.0"


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\n")


class _Report(object):
    def __init__(self):
        self.component_id = "comp-foo"
        self.criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ]
        self.requirement_results = {"R-FOO-001": "pass"}
        self.interface_drift = False
        self.mutation_score = 1.0
        self.overall = "pass"

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
    return _Report()
'''


_LICENSE_SCANNER_SRC = r'''
CALL_LOG = __CALL_LOG_PATH__


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\n")


def scan(component_id, repo_root):
    _log("scan_license")
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
'''


_SECRET_SCANNER_SRC = r'''
CALL_LOG = __CALL_LOG_PATH__


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\n")


class _SecretScanResult(object):
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
        return dict(self.__dict__)


def scan(repo_root):
    _log("scan_secret")
    return _SecretScanResult()


def gate_version(repo_root):
    return "secret_scanner@3.0.0+detect-secrets.1.5.0"
'''


_PROVENANCE_TRACKER_SRC = r'''
import pathlib

CALL_LOG = __CALL_LOG_PATH__


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\n")


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record")
    slug = component_id[len("comp-"):]
    attempts_dir = pathlib.Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (attempts_dir / "attempt-0001.json").write_text("{}")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": {},
    }
'''


_PROVENANCE_WRITER_SRC = r'''
import json

CALL_LOG = __CALL_LOG_PATH__
PROV_RECORD = __PROV_RECORD_PATH__


def _log(name):
    with open(CALL_LOG, "a") as f:
        f.write(name + "\n")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_jsonable(value):
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    return dict(getattr(value, "__dict__", {}))


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance")
    record = {
        "component_id": component_id,
        "gate_versions": _get(inputs, "gate_versions"),
        "provenance_hit": _get(inputs, "provenance_hit"),
        "attempts": _get(inputs, "attempts"),
        "generation_result": _to_jsonable(_get(inputs, "generation_result")),
        "verification_report": _to_jsonable(_get(inputs, "verification_report")),
        "license_scan_result": _to_jsonable(_get(inputs, "license_scan_result")),
        "secret_scan_result": _to_jsonable(_get(inputs, "secret_scan_result")),
    }
    with open(PROV_RECORD, "w") as f:
        json.dump(record, f)
'''


def _write_module(repo_root, slug, module_name, source):
    mod_dir = Path(repo_root) / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / (module_name + ".py")).write_text(source)


def _render(template, call_log, prov_record=None):
    rendered = template.replace("__CALL_LOG_PATH__", repr(str(call_log)))
    if prov_record is not None:
        rendered = rendered.replace("__PROV_RECORD_PATH__", repr(str(prov_record)))
    return rendered


def _setup_common_fakes(repo_root, call_log, prov_record):
    _write_module(repo_root, "provenance-checker", "provenance_checker",
                  _render(_PROVENANCE_CHECKER_SRC, call_log))
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler",
                  _render(_SPEC_BUNDLE_ASSEMBLER_SRC, call_log))
    _write_module(repo_root, "verifier-orchestrator", "verifier_orchestrator",
                  _render(_VERIFIER_ORCHESTRATOR_SRC, call_log))
    _write_module(repo_root, "license-scanner", "license_scanner",
                  _render(_LICENSE_SCANNER_SRC, call_log))
    _write_module(repo_root, "secret-scanner", "secret_scanner",
                  _render(_SECRET_SCANNER_SRC, call_log))
    _write_module(repo_root, "provenance-tracker", "provenance_tracker",
                  _render(_PROVENANCE_TRACKER_SRC, call_log))
    _write_module(repo_root, "provenance-writer", "provenance_writer",
                  _render(_PROVENANCE_WRITER_SRC, call_log, prov_record))


def _write_generator(repo_root, call_log, files, model_call_error):
    source = _GENERATOR_SRC.replace("__CALL_LOG_PATH__", repr(str(call_log)))
    source = source.replace("__FILES__", repr(files))
    source = source.replace("__MODEL_CALL_ERROR__", repr(model_call_error))
    _write_module(repo_root, "generator", "generator", source)


def test_write_provenance_called_after_scans_and_attempt_record_with_expected_inputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    call_log = tmp_path / "call_log.txt"
    call_log.write_text("")
    prov_record = tmp_path / "provenance_record.json"

    _setup_common_fakes(repo_root, call_log, prov_record)
    generated_files = {"foo.py": "print('hi')\n"}
    _write_generator(repo_root, call_log, files=generated_files, model_call_error=None)

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, model="claude-sonnet-5",
    )

    assert prov_record.exists()

    calls = [line for line in call_log.read_text().splitlines() if line]
    assert calls.count("write_provenance") == 1
    write_idx = calls.index("write_provenance")
    for required_before in ("scan_license", "scan_secret", "write_attempt_record"):
        assert required_before in calls
        assert calls.index(required_before) < write_idx

    record = json.loads(prov_record.read_text())
    assert record["gate_versions"] == {"verifier": "v@1"}
    assert record["provenance_hit"] is False
    assert record["attempts"] == 1
    assert record["generation_result"] == {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "b" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": generated_files,
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    assert record["verification_report"] == {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    assert record["license_scan_result"] == {
        "component_id": "comp-foo",
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
    assert record["secret_scan_result"] == {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def test_model_call_error_prevents_write_provenance(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    call_log = tmp_path / "call_log.txt"
    call_log.write_text("")
    prov_record = tmp_path / "provenance_record.json"

    _setup_common_fakes(repo_root, call_log, prov_record)
    _write_generator(
        repo_root, call_log, files={},
        model_call_error={"category": "network", "message": "connection reset"},
    )

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, model="claude-sonnet-5",
    )

    assert not prov_record.exists()
    calls = [line for line in call_log.read_text().splitlines() if line]
    assert "write_provenance" not in calls