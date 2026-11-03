import json
import textwrap
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_component_md(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        textwrap.dedent(
            """\
            ---
            id: comp-foo
            title: Foo
            status: draft
            owners: [team-foo]
            sealed: true
            source_path: fixtures/foo/
            ---

            # Foo

            A fixture component used to exercise component-gate-runner's
            provenance short-circuit behavior.
            """
        ),
        encoding="utf-8",
    )


def _write_module(repo_root: Path, slug: str, module_name: str, source: str) -> None:
    module_dir = repo_root / "gen" / slug
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / f"{module_name}.py").write_text(source, encoding="utf-8")


def _stub_source(log_path: Path, body: str) -> str:
    return f'''
_LOG_PATH = {str(log_path)!r}


def _log(line):
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\\n")


{body}
'''


def _provenance_checker_source(log_path, spec_bundle_hash, gate_versions,
                                verification_report, license_scan, secret_scan):
    return f'''
import json

_LOG_PATH = {str(log_path)!r}


def _log(line):
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\\n")


class _Key:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


_SPEC_BUNDLE_HASH = {spec_bundle_hash!r}
_GATE_VERSIONS = {gate_versions!r}
_VERIFICATION_REPORT = {verification_report!r}
_LICENSE_SCAN = {license_scan!r}
_SECRET_SCAN = {secret_scan!r}


def current_sealed_key(component_id, repo_root):
    _log("provenance_checker:current_sealed_key:" + str(component_id))
    return None


def current_provenance_key(component_id, repo_root):
    _log("provenance_checker:current_provenance_key:" + str(component_id))
    return _Key(_SPEC_BUNDLE_HASH, _GATE_VERSIONS)


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        "provenance_checker:check_provenance:"
        + str(component_id) + ":" + str(spec_bundle_hash) + ":"
        + json.dumps(gate_versions, sort_keys=True)
    )
    return {{
        "hit": True,
        "verification_report": _VERIFICATION_REPORT,
        "license_scan": _LICENSE_SCAN,
        "secret_scan": _SECRET_SCAN,
    }}


def check_sealed_provenance(component_id, repo_root):
    _log("provenance_checker:check_sealed_provenance:" + str(component_id))
    return {{"hit": False, "sealed": False, "reason": "not_sealed"}}
'''


def _spec_bundle_assembler_source(log_path):
    body = '''
def assemble(component_id, repo_root, mode="cold"):
    _log("spec_bundle_assembler:assemble:" + str(component_id))
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:bundle",
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
    _log("spec_bundle_assembler:assemble_criterion:" + str(component_id))
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
    return _stub_source(log_path, body)


def _generator_source(log_path):
    body = '''
def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generator:generate:" + str(_get(bundle, "component_id")))
    return {
        "component_id": _get(bundle, "component_id"),
        "spec_bundle_hash": _get(bundle, "spec_bundle_hash"),
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "mock failure"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''
    return _stub_source(log_path, body)


def _verifier_orchestrator_source(log_path):
    body = '''
GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verifier_orchestrator:verify:" + str(component_id))
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
'''
    return _stub_source(log_path, body)


def _license_scanner_source(log_path):
    body = '''
def scan(component_id, repo_root):
    _log("license_scanner:scan:" + str(component_id))
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3",
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
    _log("license_scanner:gate_version")
    return "license_scanner@4.0.3"
'''
    return _stub_source(log_path, body)


def _secret_scanner_source(log_path):
    body = '''
def scan(repo_root):
    _log("secret_scanner:scan")
    return {
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


def scan_files(paths, repo_root=None):
    _log("secret_scanner:scan_files")
    return {
        "scope": "precommit",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    _log("secret_scanner:gate_version")
    return "secret_scanner@3.0.0+detect-secrets.1.5.0"
'''
    return _stub_source(log_path, body)


def _provenance_tracker_source(log_path):
    body = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("provenance_tracker:write_attempt_record:" + str(component_id))
    return {
        "attempt_id": "2026-01-01T00:00:00Z-stub",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }


def last_requirement_failures(component_id, repo_root):
    _log("provenance_tracker:last_requirement_failures:" + str(component_id))
    return []
'''
    return _stub_source(log_path, body)


def _provenance_writer_source(log_path):
    body = '''
def write_provenance(component_id, inputs, repo_root):
    _log("provenance_writer:write_provenance:" + str(component_id))
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("provenance_writer:write_sealed_provenance:" + str(component_id))
    return None
'''
    return _stub_source(log_path, body)


def _test_author_source(log_path):
    body = '''
def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("test_author:author_test")
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py", "content": ""},
        "model_call_error": None,
    }
'''
    return _stub_source(log_path, body)


def _llm_endpoint_source(log_path):
    body = '''
def complete(prompt, model, *, backend=None, **params):
    _log("llm_endpoint:complete")
    return {
        "text": "ok",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
'''
    return _stub_source(log_path, body)


def _setup_repo(tmp_path, verification_report, license_scan, secret_scan):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component_md(repo_root)

    log_path = tmp_path / "invocations.log"

    _write_module(
        repo_root, "provenance-checker", "provenance_checker",
        _provenance_checker_source(
            log_path, "sha256:k", {"verifier": "v@1"},
            verification_report, license_scan, secret_scan,
        ),
    )
    _write_module(
        repo_root, "spec-bundle-assembler", "spec_bundle_assembler",
        _spec_bundle_assembler_source(log_path),
    )
    _write_module(repo_root, "generator", "generator", _generator_source(log_path))
    _write_module(
        repo_root, "verifier-orchestrator", "verifier_orchestrator",
        _verifier_orchestrator_source(log_path),
    )
    _write_module(
        repo_root, "license-scanner", "license_scanner",
        _license_scanner_source(log_path),
    )
    _write_module(
        repo_root, "secret-scanner", "secret_scanner",
        _secret_scanner_source(log_path),
    )
    _write_module(
        repo_root, "provenance-tracker", "provenance_tracker",
        _provenance_tracker_source(log_path),
    )
    _write_module(
        repo_root, "provenance-writer", "provenance_writer",
        _provenance_writer_source(log_path),
    )
    _write_module(repo_root, "test-author", "test_author", _test_author_source(log_path))
    _write_module(repo_root, "llm-endpoint", "llm_endpoint", _llm_endpoint_source(log_path))

    return repo_root, log_path


def _make_license_scan(blocked):
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.7,
        "blocked": blocked,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _make_secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def test_provenance_hit_short_circuits(tmp_path):
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    license_scan = _make_license_scan(blocked=False)
    secret_scan = _make_secret_scan()

    repo_root, log_path = _setup_repo(tmp_path, verification_report, license_scan, secret_scan)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    assert _get(result, "provenance_hit") is True
    assert _get(result, "blocked") is False
    assert _get(result, "verification") == verification_report

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines, "expected provenance-checker to have been called"
    for line in lines:
        assert line.startswith("provenance_checker:"), (
            "no dependency other than provenance-checker must be called on a hit: " + line
        )

    expected_check_call = (
        "provenance_checker:check_provenance:comp-foo:sha256:k:"
        + json.dumps({"verifier": "v@1"}, sort_keys=True)
    )
    assert expected_check_call in lines


def test_non_passing_hit_falls_through_to_generator(tmp_path):
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "fail",
    }
    license_scan = _make_license_scan(blocked=False)
    secret_scan = _make_secret_scan()

    repo_root, log_path = _setup_repo(tmp_path, verification_report, license_scan, secret_scan)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    assert _get(result, "provenance_hit") is False

    lines = log_path.read_text(encoding="utf-8").splitlines()
    generate_calls = [line for line in lines if line.startswith("generator:generate:")]
    assert len(generate_calls) == 1