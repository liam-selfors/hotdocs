# hotdocs-criterion: sha256:487c27662afc8abccc7e0559ad1e2ff538d9e0b11d4e8753655143eb3e3af1aa
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, **kw):\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as f:\n"
    "        f.write(json.dumps({'call': name, 'args': kw}, default=str) + '\\n')\n"
    "\n"
)

PROVENANCE_CHECKER = LOG_HELPER + (
    "class _Key:\n"
    "    def __init__(self):\n"
    "        self.spec_bundle_hash = 'sha256:abc123'\n"
    "        self.gate_versions = {\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.0.0',\n"
    "            'verifier': 'verifier-orchestrator@2.0.0',\n"
    "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'secret_scanner': 'secret_scanner@0.0.0',\n"
    "            'generator': 'generator@3.0.0+v11',\n"
    "        }\n"
    "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "                        'lockfile_sha256': None}]\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id)\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id)\n"
    "    return _Key()\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash)\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER = LOG_HELPER + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, mode=mode)\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
    "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP = LOG_HELPER + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id, model=model, mode=mode,\n"
    "         max_attempts=max_attempts, retry_feedback=retry_feedback, seed=seed)\n"
    "    generation_result = {\n"
    "        'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
    "        'model': model, 'prompt_version': 'v12', 'cache_hit': False,\n"
    "        'files': {}, 'model_call_error': {'category': 'timeout', 'message': 't'},\n"
    "        'refused': None, 'retry_feedback': None, 'mode': 'single',\n"
    "        'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
    "    }\n"
    "    attempts = [{'number': 1, 'outcome': 'generation_failed', 'retry_feedback': [],\n"
    "                 'error_category': 'timeout', 'surface_ok': None, 'overall': None,\n"
    "                 'failed_requirements': [], 'transcript_sha256': None,\n"
    "                 'reauthored_tests': []}]\n"
    "    return {'passed': False, 'stop_reason': 'not_retried', 'attempts': attempts,\n"
    "            'generation_result': generation_result, 'verification_report': None,\n"
    "            'surface_report': None}\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model, seed=seed)\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)

PROVENANCE_TRACKER = LOG_HELPER + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id)\n"
    "    return {'attempt_id': '2026-10-25T14:32:01Z-a1b2c3', 'component_id': component_id,\n"
    "            'timestamp': '2026-10-25T14:32:01Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness')\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures', component_id=component_id)\n"
    "    return []\n"
)

VERIFIER_ORCHESTRATOR = LOG_HELPER + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id)\n"
    "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [], 'overall': 'pass'}\n"
)

LICENSE_SCANNER = LOG_HELPER + (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id)\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
    "            'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
    "            'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET_SCANNER = LOG_HELPER + (
    "def _result(scope):\n"
    "    return {'scope': scope, 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
    "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
    "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan')\n"
    "    return _result('full')\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files')\n"
    "    return _result('precommit')\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

PROVENANCE_WRITER = LOG_HELPER + (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id)\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id)\n"
    "    return None\n"
)

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER,
    ("generation-loop", "generation_loop"): GENERATION_LOOP,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_ORCHESTRATOR,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER,
}


def write_fakes(repo_root):
    for (slug, module_name), source in FAKES.items():
        d = Path(repo_root) / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(source)


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_gate_003c_model_call_error_blocks_with_null_verification(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    write_fakes(repo_root)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m1")

    calls = [entry["call"] for entry in read_log(log_path)]
    assert calls.count("run_attempts") == 1

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "model_call_error"
    assert field(result, "model_call_error") == {"category": "timeout", "message": "t"}
    assert field(result, "verification") is None