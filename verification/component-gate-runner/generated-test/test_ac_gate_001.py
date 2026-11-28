# hotdocs-criterion: sha256:e1c168a76d3936a1b9a9dba10b1959345ad4418bad284d1a5b5bf6cc48ec36dc
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VERIFICATION_PASS = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.91,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "pass",
}

LICENSE_UNBLOCKED = {
    "component_id": "comp-foo",
    "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
    "evaluated": True,
    "reason": None,
    "similarity_score": 0.1,
    "block_threshold": 0.7,
    "blocked": False,
    "matches": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": True,
}

SECRET_CLEAN = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": True,
}


LOG_PRELUDE = (
    "import json\n"
    "def _log(name, **kw):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'fn': name, 'args': kw}, default=str) + '\\n')\n"
)


def _module_header(log_path):
    return "LOG = " + repr(str(log_path)) + "\n" + LOG_PRELUDE


PROVENANCE_CHECKER_BODY = (
    "class _Key:\n"
    "    def __init__(self):\n"
    "        self.spec_bundle_hash = 'sha256:k'\n"
    "        self.spec_bundle_parts = {'spec': 'sha256:s', 'dependency_code': 'sha256:d'}\n"
    "        self.gate_versions = {'verifier': 'v@1'}\n"
    "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:a', 'versions': {'python': '3.12.4'},\n"
    "                        'lockfile_sha256': None}]\n"
    "        self.drivers = []\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id, repo_root=repo_root)\n"
    "    return _Key()\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
    "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash,\n"
    "         gate_versions=gate_versions, repo_root=repo_root, spec_bundle_parts=spec_bundle_parts)\n"
    "    return {'hit': True, 'reason': None, 'verification_report': VR,\n"
    "            'license_scan': LS, 'secret_scan': SS}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER_BODY = (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, repo_root=repo_root, mode=mode)\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k', 'spec': 'spec',\n"
    "            'interface': 'iface', 'constraints': '', 'dependency_interfaces': {},\n"
    "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
    "            'hint_code': None,\n"
    "            'spec_bundle_parts': {'spec': 'sha256:s', 'dependency_code': 'sha256:d'}}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id, repo_root=repo_root)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
    "            'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP_BODY = (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
    "                 on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id, repo_root=repo_root, model=model,\n"
    "         mode=mode, max_attempts=max_attempts, retry_feedback=retry_feedback, seed=seed,\n"
    "         allow_unisolated_exec=allow_unisolated_exec)\n"
    "    gen = {'component_id': component_id, 'spec_bundle_hash': 'sha256:k', 'model': model,\n"
    "           'prompt_version': 'v1', 'cache_hit': False, 'files': {},\n"
    "           'model_call_error': {'category': 'network', 'message': 'down'},\n"
    "           'refused': None, 'retry_feedback': None, 'mode': 'single',\n"
    "           'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
    "    return {'passed': False, 'stop_reason': 'not_retried',\n"
    "            'attempts': [{'number': 1, 'outcome': 'model_call_error', 'retry_feedback': [],\n"
    "                          'error_category': 'network', 'surface_ok': None, 'overall': None,\n"
    "                          'failed_requirements': [], 'transcript_sha256': None,\n"
    "                          'reauthored_tests': []}],\n"
    "            'generation_result': gen, 'verification_report': None, 'surface_report': None}\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model, seed=seed, repo_root=repo_root)\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)

PROVENANCE_TRACKER_BODY = (
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id, spec_bundle_hash=spec_bundle_hash, repo_root=repo_root)\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness', repo_root=repo_root)\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'secret_scan': None, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures', component_id=component_id, repo_root=repo_root)\n"
    "    return []\n"
)

VERIFIER_BODY = (
    "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id, repo_root=repo_root)\n"
    "    return dict(VR)\n"
)

LICENSE_BODY = (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id, repo_root=repo_root)\n"
    "    return dict(LS)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    _log('license_gate_version', repo_root=repo_root)\n"
    "    return LS['gate_version']\n"
)

SECRET_BODY = (
    "def scan(repo_root):\n"
    "    _log('secret_scan', repo_root=repo_root)\n"
    "    return dict(SS)\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files', repo_root=repo_root)\n"
    "    return dict(SS)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    _log('secret_gate_version', repo_root=repo_root)\n"
    "    return SS['gate_version']\n"
    "\n"
    "def propose(repo_root):\n"
    "    _log('secret_propose', repo_root=repo_root)\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

WRITER_BODY = (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
)


def _write_fake(repo_root, slug, body, header):
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (slug.replace("-", "_") + ".py")).write_text(header + body, encoding="utf-8")


def _build_repo(tmp_path, hit_overall):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")

    hit_report = dict(VERIFICATION_PASS)
    hit_report["overall"] = hit_overall

    header = (
        _module_header(log_path)
        + "VR = " + repr(hit_report) + "\n"
        + "LS = " + repr(LICENSE_UNBLOCKED) + "\n"
        + "SS = " + repr(SECRET_CLEAN) + "\n"
    )
    _write_fake(repo_root, "provenance-checker", PROVENANCE_CHECKER_BODY, header)
    _write_fake(repo_root, "spec-bundle-assembler", SPEC_BUNDLE_ASSEMBLER_BODY, header)
    _write_fake(repo_root, "generation-loop", GENERATION_LOOP_BODY, header)
    _write_fake(repo_root, "provenance-tracker", PROVENANCE_TRACKER_BODY, header)
    _write_fake(repo_root, "verifier-orchestrator", VERIFIER_BODY, header)
    _write_fake(repo_root, "license-scanner", LICENSE_BODY, header)
    _write_fake(repo_root, "secret-scanner", SECRET_BODY, header)
    _write_fake(repo_root, "provenance-writer", WRITER_BODY, header)
    return repo_root, log_path, hit_report


def _calls(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_passing_hit_short_circuits(tmp_path):
    repo_root, log_path, hit_report = _build_repo(tmp_path, "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log_path)
    names = [c["fn"] for c in calls]
    assert names.count("check_provenance") == 1, names
    idx = names.index("check_provenance")
    assert "current_provenance_key" in names[:idx], names

    cp_args = calls[idx]["args"]
    assert cp_args["component_id"] == "comp-foo"
    assert cp_args["spec_bundle_hash"] == "sha256:k"
    assert cp_args["gate_versions"] == {"verifier": "v@1"}

    assert names[idx + 1:] == [], "dependencies called after check_provenance: " + repr(names[idx + 1:])

    assert field(result, "provenance_hit") is True
    assert field(result, "blocked") is False
    assert field(result, "verification") == hit_report


def test_failed_hit_proceeds_as_miss(tmp_path):
    repo_root, log_path, _ = _build_repo(tmp_path, "fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log_path)
    names = [c["fn"] for c in calls]
    assert names.count("check_provenance") == 1, names
    cp_args = calls[names.index("check_provenance")]["args"]
    assert cp_args["spec_bundle_hash"] == "sha256:k"
    assert cp_args["gate_versions"] == {"verifier": "v@1"}

    assert names.count("run_attempts") == 1, names
    assert field(result, "provenance_hit") is False