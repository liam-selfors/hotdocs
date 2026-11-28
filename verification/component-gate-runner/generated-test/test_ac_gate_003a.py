# hotdocs-criterion: sha256:fe5a1dca1223334391c91f9743dfa7cd340144edc373d57b5b60474c70e785e6
import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "\n"
    "def _log(name, *args, **kwargs):\n"
    "    entry = {'call': name, 'args': [repr(a) for a in args],\n"
    "             'kwargs': {k: repr(v) for k, v in kwargs.items()}}\n"
    "    with open(LOG, 'a') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
)


ATTEMPTS = [
    {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
     "error_category": None, "surface_ok": True, "overall": "fail",
     "failed_requirements": ["R-FOO-001"], "transcript_sha256": None,
     "reauthored_tests": []},
    {"number": 2, "outcome": "passed", "retry_feedback": ["R-FOO-001"],
     "error_category": None, "surface_ok": True, "overall": "pass",
     "failed_requirements": [], "transcript_sha256": None,
     "reauthored_tests": []},
]

GENERATION_RESULT = {
    "component_id": COMPONENT_ID,
    "spec_bundle_hash": "sha256:abc123",
    "model": "m-test",
    "prompt_version": "v1",
    "cache_hit": False,
    "files": {"foo.py": "x = 1\n"},
    "model_call_error": None,
    "refused": None,
    "retry_feedback": ["R-FOO-001"],
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

VERIFICATION_REPORT = {
    "component_id": COMPONENT_ID,
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "pass",
}

SURFACE_REPORT = {"ok": True, "findings": []}

LICENSE_RESULT = {
    "component_id": COMPONENT_ID,
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

SECRET_RESULT = {
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

VERIFICATION_EMPTY = {
    "component_id": COMPONENT_ID, "criteria": [], "requirement_results": {},
    "interface_drift": False, "mutation_score": None, "mutation_error": None,
    "assets": [], "drivers": [], "overall": "pass",
}


def write_fake(repo_root, slug, log_path, body):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    src = "LOG = " + repr(str(log_path)) + "\n" + LOG_HELPER + body
    (d / (module + ".py")).write_text(src)


def build_fakes(repo_root, log_path):
    write_fake(repo_root, "provenance-checker", log_path, (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:abc123'\n"
        "        self.spec_bundle_parts = {'spec': 'sha256:aa', 'dependency_code': 'sha256:bb'}\n"
        "        self.gate_versions = {'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@1.0.0',\n"
        "            'verifier': 'verifier-orchestrator@2.0.0',\n"
        "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
        "            'secret_scanner': 'secret_scanner@0.0.0',\n"
        "            'generator': 'generator@3.0.0+v11'}\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "            'adapter_sha256': 'sha256:cc', 'versions': {'python': '3.12.4'},\n"
        "            'lockfile_sha256': None}]\n"
        "        self.drivers = []\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id, repo_root)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id, repo_root)\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance', component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id, repo_root)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))
    write_fake(repo_root, "spec-bundle-assembler", log_path, (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id, repo_root=repo_root, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
        "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
        "            'hint_code': None,\n"
        "            'spec_bundle_parts': {'spec': 'sha256:aa', 'dependency_code': 'sha256:bb'}}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id, criterion_id, repo_root)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    ))
    write_fake(repo_root, "generation-loop", log_path, (
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "    'missing_asset', 'malformed_layout')\n"
        "\n"
        "ATTEMPTS = " + repr(ATTEMPTS) + "\n"
        "GENERATION_RESULT = " + repr(GENERATION_RESULT) + "\n"
        "VERIFICATION_REPORT = " + repr(VERIFICATION_REPORT) + "\n"
        "SURFACE_REPORT = " + repr(SURFACE_REPORT) + "\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id, bundle, repo_root, model, mode=mode,\n"
        "         max_attempts=max_attempts, retry_feedback=retry_feedback, seed=seed,\n"
        "         llm_backend=llm_backend, allow_unisolated_exec=allow_unisolated_exec)\n"
        "    return {'passed': True, 'stop_reason': 'passed', 'attempts': ATTEMPTS,\n"
        "            'generation_result': GENERATION_RESULT,\n"
        "            'verification_report': VERIFICATION_REPORT,\n"
        "            'surface_report': SURFACE_REPORT}\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model, seed, repo_root, llm_backend)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))
    write_fake(repo_root, "provenance-tracker", log_path, (
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id, generation_result, verification_report, spec_bundle_hash, repo_root)\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness', repo_root)\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures', component_id, repo_root)\n"
        "    return []\n"
    ))
    write_fake(repo_root, "verifier-orchestrator", log_path, (
        "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "REPORT = " + repr(VERIFICATION_EMPTY) + "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id, repo_root)\n"
        "    return dict(REPORT)\n"
    ))
    write_fake(repo_root, "license-scanner", log_path, (
        "RESULT = " + repr(LICENSE_RESULT) + "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id, repo_root)\n"
        "    return dict(RESULT)\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n"
    ))
    write_fake(repo_root, "secret-scanner", log_path, (
        "RESULT = " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan', repo_root)\n"
        "    return dict(RESULT)\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n"
    ))
    write_fake(repo_root, "provenance-writer", log_path, (
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id, inputs, repo_root)\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id, inputs, repo_root)\n"
        "    return None\n"
    ))


def read_calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_gate_003a_loop_attempts_passed_through(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_fakes(repo_root, log_path)

    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "m-test"
    )

    calls = read_calls(log_path)
    names = [c["call"] for c in calls]
    assert names.count("run_attempts") == 1, names

    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None

    attempts = field(result, "attempts")
    assert list(attempts) == ATTEMPTS
    assert len(attempts) == 2
    assert [field(a, "number") for a in attempts] == [1, 2]
    assert [field(a, "outcome") for a in attempts] == ["verification_failed", "passed"]

    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"