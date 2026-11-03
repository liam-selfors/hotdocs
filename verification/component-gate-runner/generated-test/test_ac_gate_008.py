import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"
SPEC_BUNDLE_HASH = "sha256:k"
GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@3.1.0",
    "secret_scanner": "secret_scanner@0.0.0",
}


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_module(repo_root, slug, module_name, source):
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / (module_name + ".py")).write_text(source)


def _log_path(repo_root):
    return str(repo_root / "calls.log")


def _read_log(repo_root):
    log_file = Path(_log_path(repo_root))
    if not log_file.exists():
        return []
    return [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]


def _build_repo(tmp_path, *, generator_model_call_error, generator_files,
                 verify_overall, write_attempt_raises):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = _log_path(repo_root)

    provenance_checker_src = f'''
import json

SPEC_BUNDLE_HASH = {SPEC_BUNDLE_HASH!r}
GATE_VERSIONS = {GATE_VERSIONS!r}


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def _log(fn, **kwargs):
    with open({log_path!r}, "a") as f:
        f.write(json.dumps({{"module": "provenance_checker", "fn": fn, **kwargs}}) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return ProvenanceKey(SPEC_BUNDLE_HASH, dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id, spec_bundle_hash=spec_bundle_hash)
    return {{"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}}
'''
    _write_module(repo_root, "provenance-checker", "provenance_checker", provenance_checker_src)

    assembler_src = f'''
import json


class SpecBundle:
    def __init__(self, component_id):
        self.component_id = component_id
        self.spec_bundle_hash = {SPEC_BUNDLE_HASH!r}
        self.spec = "spec"
        self.interface = "interface"
        self.constraints = "constraints"
        self.dependency_interfaces = {{}}
        self.dependency_context = {{}}
        self.dependency_usage = {{}}
        self.vars = {{}}
        self.glossary = "glossary"
        self.hint_code = None


def _log(fn, **kwargs):
    with open({log_path!r}, "a") as f:
        f.write(json.dumps({{"module": "spec_bundle_assembler", "fn": fn, **kwargs}}) + "\\n")


def assemble(component_id, repo_root=None, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return SpecBundle(component_id)
'''
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", assembler_src)

    generator_src = f'''
import json

MODEL_CALL_ERROR = {generator_model_call_error!r}
FILES = {generator_files!r}


class GenerationResult:
    def __init__(self, component_id, spec_bundle_hash, files, model_call_error):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.model = "fake-model"
        self.prompt_version = "v1"
        self.cache_hit = False
        self.files = files
        self.model_call_error = model_call_error
        self.refused = None
        self.retry_feedback = None


def _log(fn, **kwargs):
    with open({log_path!r}, "a") as f:
        f.write(json.dumps({{"module": "generator", "fn": fn, **kwargs}}) + "\\n")


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", component_id=getattr(bundle, "component_id", None))
    return GenerationResult(
        getattr(bundle, "component_id", None),
        getattr(bundle, "spec_bundle_hash", None),
        dict(FILES),
        MODEL_CALL_ERROR,
    )
'''
    _write_module(repo_root, "generator", "generator", generator_src)

    verifier_src = f'''
import json

OVERALL = {verify_overall!r}


class VerificationReport:
    def __init__(self, component_id, overall):
        self.component_id = component_id
        self.criteria = []
        self.requirement_results = {{}}
        self.interface_drift = False
        self.mutation_score = 0.0
        self.overall = overall


def _log(fn, **kwargs):
    with open({log_path!r}, "a") as f:
        f.write(json.dumps({{"module": "verifier_orchestrator", "fn": fn, **kwargs}}) + "\\n")


GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return VerificationReport(component_id, OVERALL)
'''
    _write_module(repo_root, "verifier-orchestrator", "verifier_orchestrator", verifier_src)

    license_scanner_src = f'''
import json


def _log(fn, **kwargs):
    with open({log_path!r}, "a") as f:
        f.write(json.dumps({{"module": "license_scanner", "fn": fn, **kwargs}}) + "\\n")


def scan(component_id, repo_root):
    _log("scan", component_id=component_id)
    return {{
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
        "cache_hit": False,
    }}


def gate_version(repo_root):
    return "license_scanner@4.0.3"
'''
    _write_module(repo_root, "license-scanner", "license_scanner", license_scanner_src)

    secret_scanner_src = f'''
import json


def _log(fn, **kwargs):
    with open({log_path!r}, "a") as f:
        f.write(json.dumps({{"module": "secret_scanner", "fn": fn, **kwargs}}) + "\\n")


def scan(repo_root):
    _log("scan")
    return {{
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }}


def gate_version(repo_root):
    return "secret_scanner@3.0.0+detect-secrets.1.5.0"
'''
    _write_module(repo_root, "secret-scanner", "secret_scanner", secret_scanner_src)

    tracker_src = f'''
import json
import os

RAISES = {write_attempt_raises!r}


def _log(fn, **kwargs):
    with open({log_path!r}, "a") as f:
        f.write(json.dumps({{"module": "provenance_tracker", "fn": fn, **kwargs}}) + "\\n")


def _to_plain(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return dict(obj)
    return {{k: getattr(obj, k) for k in vars(obj)}}


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log(
        "write_attempt_record",
        component_id=component_id,
        generation_result=_to_plain(generation_result),
        verification_report=_to_plain(verification_report),
        spec_bundle_hash=spec_bundle_hash,
    )
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    dirs = [
        os.path.join(str(repo_root), ".hotdocs", "attempts", component_id),
        os.path.join(str(repo_root), ".hotdocs", "attempts", slug),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    if RAISES:
        raise RuntimeError("write_attempt_record exploded")
    record = {{
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _to_plain(generation_result),
        "verification": _to_plain(verification_report),
    }}
    for d in dirs:
        with open(os.path.join(d, "attempt-0001.json"), "w") as f:
            f.write(json.dumps(record))
    return record
'''
    _write_module(repo_root, "provenance-tracker", "provenance_tracker", tracker_src)

    provenance_writer_src = f'''
import json


def _log(fn, **kwargs):
    with open({log_path!r}, "a") as f:
        f.write(json.dumps({{"module": "provenance_writer", "fn": fn, **kwargs}}) + "\\n")


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''
    _write_module(repo_root, "provenance-writer", "provenance_writer", provenance_writer_src)

    return repo_root


def test_miss_writes_attempt_record_once_after_scans_with_full_args(tmp_path):
    repo_root = _build_repo(
        tmp_path,
        generator_model_call_error=None,
        generator_files={"foo.py": "print(1)"},
        verify_overall="fail",
        write_attempt_raises=False,
    )

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "fake-model")

    log = _read_log(repo_root)
    write_calls = [e for e in log if e["fn"] == "write_attempt_record"]
    assert len(write_calls) == 1
    call = write_calls[0]

    license_idx = next(
        i for i, e in enumerate(log) if e["fn"] == "scan" and e["module"] == "license_scanner"
    )
    secret_idx = next(
        i for i, e in enumerate(log) if e["fn"] == "scan" and e["module"] == "secret_scanner"
    )
    write_idx = next(i for i, e in enumerate(log) if e["fn"] == "write_attempt_record")
    assert write_idx > license_idx
    assert write_idx > secret_idx

    assert call["component_id"] == "comp-foo"
    assert call["spec_bundle_hash"] == SPEC_BUNDLE_HASH

    gen = call["generation_result"]
    assert gen is not None
    assert gen["files"] == {"foo.py": "print(1)"}
    assert gen["model_call_error"] is None

    ver = call["verification_report"]
    assert ver is not None
    assert ver["overall"] == "fail"

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "verification_failed"


def test_model_call_error_passes_none_verification_report(tmp_path):
    repo_root = _build_repo(
        tmp_path,
        generator_model_call_error={"category": "network", "message": "boom"},
        generator_files={},
        verify_overall="pass",
        write_attempt_raises=False,
    )

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "fake-model")

    log = _read_log(repo_root)
    write_calls = [e for e in log if e["fn"] == "write_attempt_record"]
    assert len(write_calls) == 1
    assert write_calls[0]["verification_report"] is None

    verify_calls = [e for e in log if e["fn"] == "verify"]
    assert len(verify_calls) == 0

    assert _get(result, "block_reason") == "model_call_error"


def test_write_attempt_record_exception_does_not_change_result(tmp_path):
    repo_root = _build_repo(
        tmp_path,
        generator_model_call_error=None,
        generator_files={"foo.py": "print(1)"},
        verify_overall="pass",
        write_attempt_raises=True,
    )

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "fake-model")

    assert _get(result, "blocked") is False
    assert _get(result, "block_reason") is None

    log = _read_log(repo_root)
    write_calls = [e for e in log if e["fn"] == "write_attempt_record"]
    assert len(write_calls) == 1