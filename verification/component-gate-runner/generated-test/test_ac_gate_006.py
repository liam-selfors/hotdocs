import json
import os

import component_gate_runner


def _dual_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_module(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    dep_dir = repo_root / "gen" / slug
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / (module_name + ".py")).write_text(source)


_LOG_FUNC_TEMPLATE = '''
import json as _json


def _log(event):
    with open(__LOG_PATH__, "a") as f:
        f.write(_json.dumps(event) + "\\n")
'''

_PROVENANCE_CHECKER_BODY = '''

class _Key(object):
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log({"module": "provenance-checker", "func": "current_sealed_key"})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"module": "provenance-checker", "func": "current_provenance_key"})
    return _Key("sha256:" + "0" * 64, {"verifier": "v@1"})


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({"module": "provenance-checker", "func": "check_provenance"})
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''

_SPEC_BUNDLE_ASSEMBLER_BODY = '''

def assemble(component_id, repo_root=None, mode="cold"):
    _log({"module": "spec-bundle-assembler", "func": "assemble"})
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
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

_GENERATOR_BODY_FILES = '''

def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    _log({"module": "generator", "func": "generate"})
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print(1)"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_GENERATOR_BODY_MODEL_CALL_ERROR = '''

def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    _log({"module": "generator", "func": "generate"})
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_VERIFIER_ORCHESTRATOR_BODY = '''

GATE_VERSION = "verifier-orchestrator@2.0.0"


class _Report(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return dict(self.__dict__)


def verify(component_id, repo_root, judge=None, test_author=None):
    _log({"module": "verifier-orchestrator", "func": "verify"})
    return _Report(
        component_id=component_id,
        criteria=[],
        requirement_results={},
        interface_drift=False,
        mutation_score=1.0,
        overall="pass",
    )
'''

_LICENSE_SCANNER_BODY = '''

def scan(component_id, repo_root):
    _log({"module": "license-scanner", "func": "scan"})
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@1.0.0",
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
    return "license_scanner@1.0.0"
'''

_SECRET_SCANNER_BODY = '''

class _SecretScanResult(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return dict(self.__dict__)


def scan(repo_root):
    _log({"module": "secret-scanner", "func": "scan"})
    return _SecretScanResult(
        scope="full",
        gate_version="secret_scanner@1.0.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def gate_version(repo_root):
    return "secret_scanner@1.0.0"
'''

_PROVENANCE_TRACKER_BODY = '''

import os as _os


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log({"module": "provenance-tracker", "func": "write_attempt_record"})
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = _os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    _os.makedirs(attempts_dir, exist_ok=True)
    with open(_os.path.join(attempts_dir, "attempt-0001.json"), "w") as f:
        f.write("{}")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''

_PROVENANCE_WRITER_BODY = '''

def _dget(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _generation_to_dict(gr):
    if gr is None:
        return None
    return {
        "component_id": _dget(gr, "component_id"),
        "spec_bundle_hash": _dget(gr, "spec_bundle_hash"),
        "model": _dget(gr, "model"),
        "prompt_version": _dget(gr, "prompt_version"),
        "cache_hit": _dget(gr, "cache_hit"),
        "files": _dget(gr, "files"),
        "model_call_error": _dget(gr, "model_call_error"),
        "refused": _dget(gr, "refused"),
        "retry_feedback": _dget(gr, "retry_feedback"),
    }


def _verification_to_dict(vr):
    if vr is None:
        return None
    return {
        "component_id": _dget(vr, "component_id"),
        "criteria": _dget(vr, "criteria"),
        "requirement_results": _dget(vr, "requirement_results"),
        "interface_drift": _dget(vr, "interface_drift"),
        "mutation_score": _dget(vr, "mutation_score"),
        "overall": _dget(vr, "overall"),
    }


def _license_to_dict(lr):
    if lr is None:
        return None
    return {
        "component_id": _dget(lr, "component_id"),
        "gate_version": _dget(lr, "gate_version"),
        "evaluated": _dget(lr, "evaluated"),
        "reason": _dget(lr, "reason"),
        "similarity_score": _dget(lr, "similarity_score"),
        "block_threshold": _dget(lr, "block_threshold"),
        "blocked": _dget(lr, "blocked"),
        "matches": _dget(lr, "matches"),
        "notified": _dget(lr, "notified"),
        "notification_delivery_error": _dget(lr, "notification_delivery_error"),
        "cache_hit": _dget(lr, "cache_hit"),
    }


def _secret_to_dict(sr):
    if sr is None:
        return None
    return {
        "scope": _dget(sr, "scope"),
        "gate_version": _dget(sr, "gate_version"),
        "flagged": _dget(sr, "flagged"),
        "matches": _dget(sr, "matches"),
        "allowed": _dget(sr, "allowed"),
        "unused_allowlist_entries": _dget(sr, "unused_allowlist_entries"),
        "notified": _dget(sr, "notified"),
        "notification_delivery_error": _dget(sr, "notification_delivery_error"),
        "cache_hit": _dget(sr, "cache_hit"),
    }


def write_provenance(component_id, inputs, repo_root):
    _log({"module": "provenance-writer", "func": "write_provenance"})
    record = {
        "component_id": _dget(inputs, "component_id"),
        "generation_result": _generation_to_dict(_dget(inputs, "generation_result")),
        "verification_report": _verification_to_dict(_dget(inputs, "verification_report")),
        "license_scan_result": _license_to_dict(_dget(inputs, "license_scan_result")),
        "secret_scan_result": _secret_to_dict(_dget(inputs, "secret_scan_result")),
        "provenance_hit": _dget(inputs, "provenance_hit"),
        "attempts": _dget(inputs, "attempts"),
        "gate_versions": _dget(inputs, "gate_versions"),
    }
    with open(__INPUTS_PATH__, "w") as f:
        _json.dump(record, f)


def write_sealed_provenance(component_id, inputs, repo_root):
    _log({"module": "provenance-writer", "func": "write_sealed_provenance"})
'''


def _build_repo(tmp_path, generator_mode):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = str(tmp_path / "calls.jsonl")
    inputs_path = str(tmp_path / "provenance_inputs.json")

    log_helper = _LOG_FUNC_TEMPLATE.replace("__LOG_PATH__", repr(log_path))

    _write_module(repo_root, "provenance-checker", log_helper + _PROVENANCE_CHECKER_BODY)
    _write_module(repo_root, "spec-bundle-assembler", log_helper + _SPEC_BUNDLE_ASSEMBLER_BODY)

    if generator_mode == "files":
        generator_body = _GENERATOR_BODY_FILES
    else:
        generator_body = _GENERATOR_BODY_MODEL_CALL_ERROR
    _write_module(repo_root, "generator", log_helper + generator_body)

    _write_module(repo_root, "verifier-orchestrator", log_helper + _VERIFIER_ORCHESTRATOR_BODY)
    _write_module(repo_root, "license-scanner", log_helper + _LICENSE_SCANNER_BODY)
    _write_module(repo_root, "secret-scanner", log_helper + _SECRET_SCANNER_BODY)
    _write_module(repo_root, "provenance-tracker", log_helper + _PROVENANCE_TRACKER_BODY)

    writer_source = (log_helper + _PROVENANCE_WRITER_BODY).replace(
        "__INPUTS_PATH__", repr(inputs_path)
    )
    _write_module(repo_root, "provenance-writer", writer_source)

    return repo_root, log_path, inputs_path


def _read_events(log_path):
    if not os.path.exists(log_path):
        return []
    events = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _indices(events, module, func):
    return [i for i, e in enumerate(events) if e["module"] == module and e["func"] == func]


def test_write_provenance_called_once_with_expected_inputs_after_dependencies(tmp_path):
    repo_root, log_path, inputs_path = _build_repo(tmp_path, generator_mode="files")

    component_gate_runner.run_component_gates(
        "comp-foo",
        repo_root,
        "fake-model",
        seed=0,
        llm_backend=None,
        retry_feedback=None,
    )

    events = _read_events(log_path)

    writer_calls = _indices(events, "provenance-writer", "write_provenance")
    assert len(writer_calls) == 1
    writer_index = writer_calls[0]

    license_calls = _indices(events, "license-scanner", "scan")
    secret_calls = _indices(events, "secret-scanner", "scan")
    attempt_calls = _indices(events, "provenance-tracker", "write_attempt_record")

    assert license_calls
    assert secret_calls
    assert attempt_calls

    assert writer_index > max(license_calls)
    assert writer_index > max(secret_calls)
    assert writer_index > max(attempt_calls)

    with open(inputs_path) as f:
        inputs_record = json.load(f)

    assert inputs_record["gate_versions"] == {"verifier": "v@1"}
    assert inputs_record["provenance_hit"] is False
    assert inputs_record["attempts"] == 1

    assert inputs_record["generation_result"] == {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "fake-model",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print(1)"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }

    assert inputs_record["verification_report"] == {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }

    assert inputs_record["license_scan_result"] == {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@1.0.0",
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

    assert inputs_record["secret_scan_result"] == {
        "scope": "full",
        "gate_version": "secret_scanner@1.0.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def test_write_provenance_never_called_on_model_call_error(tmp_path):
    repo_root, log_path, inputs_path = _build_repo(tmp_path, generator_mode="model_call_error")

    component_gate_runner.run_component_gates(
        "comp-foo",
        repo_root,
        "fake-model",
        seed=0,
        llm_backend=None,
        retry_feedback=None,
    )

    events = _read_events(log_path)
    writer_calls = _indices(events, "provenance-writer", "write_provenance")

    assert writer_calls == []
    assert not os.path.exists(inputs_path)