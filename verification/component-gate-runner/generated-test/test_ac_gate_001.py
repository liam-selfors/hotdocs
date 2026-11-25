# hotdocs-criterion: sha256:baec4994627aba7186c1265ae94dc590a3236d0726f3f449950ad7edcbc1061a
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SHARED = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(fn, **kw):\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as f:\n"
    "        f.write(json.dumps({'fn': fn, 'args': kw}, default=str) + '\\n')\n"
    "\n"
    "def _report(overall):\n"
    "    return {\n"
    "        'component_id': 'comp-foo',\n"
    "        'criteria': [\n"
    "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled',\n"
    "             'result': 'pass' if overall == 'pass' else 'fail'},\n"
    "        ],\n"
    "        'requirement_results': {'R-FOO-001': 'pass' if overall == 'pass' else 'fail'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                    'adapter_sha256': 'sha256:ab', 'versions': {'python': '3.12.4'},\n"
    "                    'lockfile_sha256': None}],\n"
    "        'overall': overall,\n"
    "    }\n"
    "\n"
    "def _license(component_id='comp-foo'):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "        'evaluated': False,\n"
    "        'reason': 'no-reference-corpus',\n"
    "        'similarity_score': None,\n"
    "        'block_threshold': None,\n"
    "        'blocked': False,\n"
    "        'matches': [],\n"
    "        'notified': False,\n"
    "        'notification_delivery_error': None,\n"
    "        'cache_hit': False,\n"
    "    }\n"
    "\n"
    "def _secret():\n"
    "    return {\n"
    "        'scope': 'full',\n"
    "        'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
    "        'flagged': False,\n"
    "        'matches': [],\n"
    "        'allowed': [],\n"
    "        'unused_allowlist_entries': [],\n"
    "        'notified': False,\n"
    "        'notification_delivery_error': None,\n"
    "        'cache_hit': False,\n"
    "    }\n"
    "\n"
)

PROVENANCE_CHECKER = SHARED + (
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id, repo_root=repo_root)\n"
    "    return ProvenanceKey('sha256:k', {'verifier': 'v@1'},\n"
    "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "          'adapter_sha256': 'sha256:ab', 'versions': {'python': '3.12.4'},\n"
    "          'lockfile_sha256': None}])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id=component_id,\n"
    "         spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions,\n"
    "         repo_root=repo_root)\n"
    "    return {\n"
    "        'hit': True,\n"
    "        'reason': None,\n"
    "        'verification_report': _report(os.environ['GATE_TEST_OVERALL']),\n"
    "        'license_scan': _license(component_id),\n"
    "        'secret_scan': _secret(),\n"
    "    }\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER = SHARED + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, repo_root=repo_root, mode=mode)\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:k',\n"
    "        'spec': 'spec',\n"
    "        'interface': 'interface',\n"
    "        'constraints': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'dependency_context': {},\n"
    "        'dependency_usage': {},\n"
    "        'vars': {},\n"
    "        'glossary': '',\n"
    "        'hint_code': None,\n"
    "    }\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id,\n"
    "         criterion_id=criterion_id, repo_root=repo_root)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {},\n"
    "            'testing': ''}\n"
)

GENERATION_LOOP = SHARED + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id, repo_root=repo_root,\n"
    "         model=model, mode=mode, max_attempts=max_attempts,\n"
    "         retry_feedback=retry_feedback, seed=seed)\n"
    "    generation_result = {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:k',\n"
    "        'model': model,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'files': {'foo.py': 'x = 1\\n'},\n"
    "        'model_call_error': None,\n"
    "        'refused': None,\n"
    "        'retry_feedback': retry_feedback,\n"
    "        'mode': 'single',\n"
    "        'transcript_sha256': None,\n"
    "        'turns': 1,\n"
    "        'tool_calls': 0,\n"
    "        'isolation': None,\n"
    "    }\n"
    "    report = _report('pass')\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
    "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, generation_result, report)\n"
    "    return {\n"
    "        'passed': True,\n"
    "        'stop_reason': 'passed',\n"
    "        'attempts': [attempt],\n"
    "        'generation_result': generation_result,\n"
    "        'verification_report': report,\n"
    "        'surface_report': {'ok': True, 'findings': []},\n"
    "    }\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model, seed=seed, repo_root=repo_root)\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)

PROVENANCE_TRACKER = SHARED + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id,\n"
    "         spec_bundle_hash=spec_bundle_hash, repo_root=repo_root)\n"
    "    return {\n"
    "        'attempt_id': '2026-10-25T14:32:01Z-a1b2c3',\n"
    "        'component_id': component_id,\n"
    "        'timestamp': '2026-10-25T14:32:01Z',\n"
    "        'spec_bundle_hash': spec_bundle_hash,\n"
    "        'generation': {},\n"
    "        'verification': None,\n"
    "    }\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness', repo_root=repo_root)\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures', component_id=component_id, repo_root=repo_root)\n"
    "    return []\n"
)

LICENSE_SCANNER = SHARED + (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id, repo_root=repo_root)\n"
    "    return _license(component_id)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    _log('license_gate_version', repo_root=repo_root)\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET_SCANNER = SHARED + (
    "def scan(repo_root):\n"
    "    _log('secret_scan', repo_root=repo_root)\n"
    "    return _secret()\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files', repo_root=repo_root)\n"
    "    return _secret()\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    _log('secret_gate_version', repo_root=repo_root)\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    _log('secret_propose', repo_root=repo_root)\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

PROVENANCE_WRITER = SHARED + (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
)

VERIFIER_ORCHESTRATOR = SHARED + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id, repo_root=repo_root)\n"
    "    return _report('pass')\n"
)

FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generation-loop": GENERATION_LOOP,
    "provenance-tracker": PROVENANCE_TRACKER,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-writer": PROVENANCE_WRITER,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR,
}


def build_repo(repo_root):
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source)


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def expected_namespace():
    ns = {}
    exec(SHARED, ns)
    return ns


def setup(tmp_path, monkeypatch, overall):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    monkeypatch.setenv("GATE_TEST_OVERALL", overall)
    return repo_root, log_path


def test_passing_hit_short_circuits(tmp_path, monkeypatch):
    repo_root, log_path = setup(tmp_path, monkeypatch, "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = read_log(log_path)
    names = [c["fn"] for c in calls]
    assert "check_provenance" in names, names
    idx = names.index("check_provenance")
    cp = calls[idx]["args"]
    assert cp["spec_bundle_hash"] == "sha256:k"
    assert cp["gate_versions"] == {"verifier": "v@1"}
    assert names[idx + 1:] == [], names
    assert names.count("check_provenance") == 1

    assert field(result, "provenance_hit") is True
    assert field(result, "blocked") is False
    ns = expected_namespace()
    assert field(result, "verification") == ns["_report"]("pass")
    assert field(result, "attempts") == []


def test_failed_hit_proceeds_as_miss(tmp_path, monkeypatch):
    repo_root, log_path = setup(tmp_path, monkeypatch, "fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = read_log(log_path)
    names = [c["fn"] for c in calls]
    assert names.count("check_provenance") == 1, names
    assert names.count("run_attempts") == 1, names
    assert field(result, "provenance_hit") is False