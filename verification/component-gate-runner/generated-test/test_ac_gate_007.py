import json

import component_gate_runner


def dual_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write_module(repo_root, slug, module_name, source):
    module_dir = repo_root / "gen" / slug
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / (module_name + ".py")).write_text(source)


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = log_path.read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


PROVENANCE_CHECKER_TEMPLATE = '''
import json

LOG_PATH = {log_path!r}


def _log(name, payload=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({{"call": name, "payload": payload}}) + "\\n")


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
    _log("current_sealed_key", {{"component_id": str(component_id)}})
    sealed = {sealed!r}
    if not sealed:
        return None
    return SealedKey(
        owners={owners!r},
        source_path={source_path!r},
        source_hash={source_hash!r},
        verifier_version={verifier_version!r},
    )


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key")
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "0" * 64,
        gate_versions={{
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        }},
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance")
    return {{"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}}
'''


VERIFIER_ORCHESTRATOR_TEMPLATE = '''
import json

LOG_PATH = {log_path!r}


def _log(name, payload=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({{"call": name, "payload": payload}}) + "\\n")


GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    def __init__(self, component_id, criteria, requirement_results, overall):
        self.component_id = component_id
        self.criteria = criteria
        self.requirement_results = requirement_results
        self.interface_drift = False
        self.mutation_score = None
        self.overall = overall

    def to_dict(self):
        return {{
            "component_id": self.component_id,
            "criteria": self.criteria,
            "requirement_results": self.requirement_results,
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }}


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", {{"component_id": str(component_id)}})
    return VerificationReport(
        component_id={component_id!r},
        criteria={criteria!r},
        requirement_results={requirement_results!r},
        overall={overall!r},
    )
'''


LICENSE_SCANNER_TEMPLATE = '''
import json

LOG_PATH = {log_path!r}


def _log(name, payload=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({{"call": name, "payload": payload}}) + "\\n")


def scan(component_id, repo_root):
    _log("license_scan")
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


def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"
'''


SECRET_SCANNER_TEMPLATE = '''
import json

LOG_PATH = {log_path!r}


def _log(name, payload=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({{"call": name, "payload": payload}}) + "\\n")


def scan(repo_root):
    _log("secret_scan")
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


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"
'''


PROVENANCE_WRITER_TEMPLATE = '''
import json

LOG_PATH = {log_path!r}


def _log(name, payload=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({{"call": name, "payload": payload}}) + "\\n")


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance")
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    report = _get(inputs, "verification_report")
    report_overall = _get(report, "overall")
    payload = {{
        "component_id": _get(inputs, "component_id"),
        "owners": _get(inputs, "owners"),
        "source_path": _get(inputs, "source_path"),
        "source_hash": _get(inputs, "source_hash"),
        "verifier_version": _get(inputs, "verifier_version"),
        "verification_report_overall": report_overall,
    }}
    _log("write_sealed_provenance", payload)
    return None
'''


SPEC_BUNDLE_ASSEMBLER_TEMPLATE = '''
import json

LOG_PATH = {log_path!r}


def _log(name, payload=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({{"call": name, "payload": payload}}) + "\\n")


class SpecBundle:
    def __init__(self, component_id, spec_bundle_hash):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.spec = ""
        self.interface = ""
        self.constraints = ""
        self.dependency_interfaces = {{}}
        self.dependency_context = {{}}
        self.dependency_usage = {{}}
        self.vars = {{}}
        self.glossary = ""
        self.hint_code = None


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble")
    return SpecBundle(component_id=component_id, spec_bundle_hash="sha256:" + "0" * 64)


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion")
    return None
'''


GENERATOR_TEMPLATE = '''
import json

LOG_PATH = {log_path!r}


def _log(name, payload=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({{"call": name, "payload": payload}}) + "\\n")


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate")
    return {{
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {{"foo.py": "# generated"}},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }}
'''


PROVENANCE_TRACKER_TEMPLATE = '''
import json

LOG_PATH = {log_path!r}


def _log(name, payload=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({{"call": name, "payload": payload}}) + "\\n")


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record")
    return {{
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result if isinstance(generation_result, dict) else {{}},
        "verification": verification_report if isinstance(verification_report, dict) else None,
    }}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures")
    return []
'''


def _build_repo_root(tmp_path, log_path, *, sealed, owners, source_path, source_hash,
                      verifier_version, verify_overall, verify_criteria,
                      verify_requirement_results):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_module(
        repo_root, "provenance-checker", "provenance_checker",
        PROVENANCE_CHECKER_TEMPLATE.format(
            log_path=str(log_path), sealed=sealed, owners=owners,
            source_path=source_path, source_hash=source_hash,
            verifier_version=verifier_version,
        ),
    )
    _write_module(
        repo_root, "verifier-orchestrator", "verifier_orchestrator",
        VERIFIER_ORCHESTRATOR_TEMPLATE.format(
            log_path=str(log_path), component_id="comp-foo",
            criteria=verify_criteria, requirement_results=verify_requirement_results,
            overall=verify_overall,
        ),
    )
    _write_module(
        repo_root, "license-scanner", "license_scanner",
        LICENSE_SCANNER_TEMPLATE.format(log_path=str(log_path)),
    )
    _write_module(
        repo_root, "secret-scanner", "secret_scanner",
        SECRET_SCANNER_TEMPLATE.format(log_path=str(log_path)),
    )
    _write_module(
        repo_root, "provenance-writer", "provenance_writer",
        PROVENANCE_WRITER_TEMPLATE.format(log_path=str(log_path)),
    )
    _write_module(
        repo_root, "spec-bundle-assembler", "spec_bundle_assembler",
        SPEC_BUNDLE_ASSEMBLER_TEMPLATE.format(log_path=str(log_path)),
    )
    _write_module(
        repo_root, "generator", "generator",
        GENERATOR_TEMPLATE.format(log_path=str(log_path)),
    )
    _write_module(
        repo_root, "provenance-tracker", "provenance_tracker",
        PROVENANCE_TRACKER_TEMPLATE.format(log_path=str(log_path)),
    )

    return repo_root


def test_sealed_component_passing_verification_writes_sealed_provenance(tmp_path):
    log_path = tmp_path / "calls.log"
    owners = ["pipeline-team"]
    source_path = "pipeline/foo/"
    source_hash = "sha256:k"
    verifier_version = "verifier-orchestrator@2.0.0"
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
    ]
    requirement_results = {"R-FOO-001": "pass", "R-FOO-002": "pass"}

    repo_root = _build_repo_root(
        tmp_path, log_path, sealed=True, owners=owners, source_path=source_path,
        source_hash=source_hash, verifier_version=verifier_version,
        verify_overall="pass", verify_criteria=criteria,
        verify_requirement_results=requirement_results,
    )

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_log(log_path)
    call_names = [c["call"] for c in calls]

    for forbidden in ("check_provenance", "current_provenance_key", "assemble",
                       "generate", "write_attempt_record", "write_provenance"):
        assert forbidden not in call_names

    assert call_names.count("verify") == 1
    assert call_names.count("license_scan") == 1
    assert call_names.count("secret_scan") == 1
    assert call_names.count("write_sealed_provenance") == 1

    write_index = call_names.index("write_sealed_provenance")
    verify_index = call_names.index("verify")
    license_index = call_names.index("license_scan")
    secret_index = call_names.index("secret_scan")
    assert write_index > verify_index
    assert write_index > license_index
    assert write_index > secret_index

    write_payload = calls[write_index]["payload"]
    assert write_payload["component_id"] == "comp-foo"
    assert write_payload["owners"] == owners
    assert write_payload["source_path"] == source_path
    assert write_payload["source_hash"] == source_hash
    assert write_payload["verifier_version"] == verifier_version
    assert write_payload["verification_report_overall"] == "pass"

    assert dual_get(result, "provenance_hit") is False
    assert dual_get(result, "blocked") is False


def test_sealed_component_failing_verification_blocks_but_still_writes(tmp_path):
    log_path = tmp_path / "calls.log"
    owners = ["pipeline-team"]
    source_path = "pipeline/foo/"
    source_hash = "sha256:k"
    verifier_version = "verifier-orchestrator@2.0.0"
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail"},
    ]
    requirement_results = {"R-FOO-001": "pass", "R-FOO-002": "fail"}

    repo_root = _build_repo_root(
        tmp_path, log_path, sealed=True, owners=owners, source_path=source_path,
        source_hash=source_hash, verifier_version=verifier_version,
        verify_overall="fail", verify_criteria=criteria,
        verify_requirement_results=requirement_results,
    )

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_log(log_path)
    call_names = [c["call"] for c in calls]

    assert call_names.count("write_sealed_provenance") == 1
    matching = [c for c in calls if c["call"] == "write_sealed_provenance"]
    write_payload = matching[0]["payload"]
    assert write_payload["verification_report_overall"] == "fail"

    assert dual_get(result, "blocked") is True
    assert dual_get(result, "block_reason") == "verification_failed"


def test_non_sealed_component_never_calls_write_sealed_provenance(tmp_path):
    log_path = tmp_path / "calls.log"
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ]
    requirement_results = {"R-FOO-001": "pass"}

    repo_root = _build_repo_root(
        tmp_path, log_path, sealed=False, owners=[], source_path="", source_hash="",
        verifier_version="", verify_overall="pass", verify_criteria=criteria,
        verify_requirement_results=requirement_results,
    )

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_log(log_path)
    call_names = [c["call"] for c in calls]

    assert "write_sealed_provenance" not in call_names
    assert call_names.count("current_sealed_key") == 1

    for expected in ("current_provenance_key", "check_provenance", "assemble", "generate",
                      "license_scan", "secret_scan", "write_attempt_record", "write_provenance"):
        assert expected in call_names