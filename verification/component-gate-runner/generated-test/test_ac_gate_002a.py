# hotdocs-criterion: sha256:05713d5d196a5d31ff3029518b0bcce9cf88b9f41eb0bc4cf146f3321c43972e
import json
from pathlib import Path

import component_gate_runner


PRELUDE = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, **kw):\n"
    "    entry = dict(kw)\n"
    "    entry['call'] = name\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as f:\n"
    "        f.write(json.dumps(entry, sort_keys=True, default=repr) + '\\n')\n"
    "\n"
)


PROVENANCE_CHECKER = PRELUDE + (
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
    "    _log('current_sealed_key', component_id=component_id, repo_root=str(repo_root))\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id, repo_root=str(repo_root))\n"
    "    return _Key()\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER = PRELUDE + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    bundle = {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:abc123',\n"
    "        'spec': 'spec text',\n"
    "        'interface': 'interface text',\n"
    "        'constraints': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'dependency_context': {},\n"
    "        'dependency_usage': {},\n"
    "        'vars': {},\n"
    "        'glossary': '',\n"
    "        'hint_code': None,\n"
    "        'marker': 'assembled-bundle-marker',\n"
    "    }\n"
    "    _log('assemble', component_id=component_id, repo_root=str(repo_root),\n"
    "         mode=mode, bundle_id=id(bundle))\n"
    "    return bundle\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP = PRELUDE + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model)\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    marker = bundle['marker'] if isinstance(bundle, dict) else getattr(bundle, 'marker', None)\n"
    "    _log('run_attempts', component_id=component_id, bundle_id=id(bundle),\n"
    "         bundle_marker=marker, repo_root=str(repo_root),\n"
    "         repo_root_is_path=isinstance(repo_root, __import__('pathlib').PurePath),\n"
    "         model=model, mode=mode, max_attempts=max_attempts,\n"
    "         max_attempts_type=type(max_attempts).__name__,\n"
    "         retry_feedback=retry_feedback, seed=seed, seed_type=type(seed).__name__,\n"
    "         llm_backend_id=id(llm_backend),\n"
    "         allow_unisolated_exec=allow_unisolated_exec,\n"
    "         on_attempt_callable=callable(on_attempt))\n"
    "    generation_result = {\n"
    "        'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
    "        'model': model, 'prompt_version': 'v1', 'cache_hit': False,\n"
    "        'files': {'foo.py': 'X = 1\\n'}, 'model_call_error': None, 'refused': None,\n"
    "        'retry_feedback': retry_feedback, 'mode': mode, 'transcript_sha256': None,\n"
    "        'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
    "    }\n"
    "    verification_report = {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'}],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False, 'mutation_score': 0.9, 'mutation_error': None,\n"
    "        'assets': [], 'overall': 'pass',\n"
    "    }\n"
    "    return {\n"
    "        'passed': True,\n"
    "        'stop_reason': 'passed',\n"
    "        'attempts': [{'number': 1, 'outcome': 'passed', 'retry_feedback': retry_feedback or [],\n"
    "                      'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "                      'failed_requirements': [], 'transcript_sha256': None,\n"
    "                      'reauthored_tests': []}],\n"
    "        'generation_result': generation_result,\n"
    "        'verification_report': verification_report,\n"
    "        'surface_report': {'ok': True, 'findings': []},\n"
    "    }\n"
)


PROVENANCE_TRACKER = PRELUDE + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id)\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
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


VERIFIER_ORCHESTRATOR = PRELUDE + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id)\n"
    "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [], 'overall': 'pass'}\n"
)


LICENSE_SCANNER = PRELUDE + (
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


SECRET_SCANNER = PRELUDE + (
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
    "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_WRITER = PRELUDE + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id)\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id)\n"
    "    return None\n"
)


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generation-loop": GENERATION_LOOP,
    "provenance-tracker": PROVENANCE_TRACKER,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-writer": PROVENANCE_WRITER,
}


def _write_fakes(repo_root):
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source)


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class _SentinelBackend:
    pass


def test_ac_gate_002a_miss_wires_assemble_then_run_attempts(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fakes(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))

    sentinel = _SentinelBackend()

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", seed=3,
        llm_backend=sentinel, retry_feedback=["R-FOO-002"],
        max_attempts=2, mode="agentic", allow_unisolated_exec=True,
    )
    assert result is not None

    entries = _read_log(log_path)
    names = [e["call"] for e in entries]

    assert "assemble" in names, names
    assert names.count("run_attempts") == 1, names
    assert names.index("assemble") < names.index("run_attempts"), names

    assemble_entry = entries[names.index("assemble")]
    assert assemble_entry["mode"] == "cold"
    assert assemble_entry["component_id"] == "comp-foo"

    ra = entries[names.index("run_attempts")]
    assert ra["component_id"] == "comp-foo"
    assert ra["bundle_marker"] == "assembled-bundle-marker"
    assert ra["bundle_id"] == assemble_entry["bundle_id"]
    assert ra["repo_root"] == str(repo_root)
    assert ra["repo_root_is_path"] is True
    assert ra["model"] == "m"
    assert ra["mode"] == "agentic"
    assert ra["max_attempts"] == 2
    assert ra["max_attempts_type"] == "int"
    assert ra["retry_feedback"] == ["R-FOO-002"]
    assert ra["seed"] == 3
    assert ra["seed_type"] == "int"
    assert ra["llm_backend_id"] == id(sentinel)
    assert ra["allow_unisolated_exec"] is True
    assert ra["on_attempt_callable"] is True