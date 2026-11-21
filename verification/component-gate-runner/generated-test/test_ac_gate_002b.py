# hotdocs-criterion: sha256:de488808ce9cc1bea4b569ff96db6860492785c5549308a61216849260d8ce4f
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, **kw):\n"
    "    rec = {'call': name}\n"
    "    rec.update(kw)\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as fh:\n"
    "        fh.write(json.dumps(rec) + '\\n')\n"
    "\n"
)


PROVENANCE_CHECKER = LOG_HELPER + (
    "class SealedKey:\n"
    "    def __init__(self, owners, source_path, source_hash, verifier_version):\n"
    "        self.owners = owners\n"
    "        self.source_path = source_path\n"
    "        self.source_hash = source_hash\n"
    "        self.verifier_version = verifier_version\n"
    "\n"
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id, repo_root=str(repo_root))\n"
    "    return SealedKey(['pipeline-team'], 'legacy/foo/', 'sha256:' + '0' * 64,\n"
    "                     'verifier-orchestrator@2.0.0')\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id)\n"
    "    return ProvenanceKey('sha256:' + 'a' * 64, {\n"
    "        'compiler': 'criterion-compiler@1.0.0',\n"
    "        'generated_test': 'generated_test@1.0.0',\n"
    "        'verifier': 'verifier-orchestrator@2.0.0',\n"
    "        'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "        'secret_scanner': 'secret_scanner@0.0.0',\n"
    "        'generator': 'generator@3.0.0+v11'},\n"
    "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "          'adapter_sha256': 'sha256:' + 'b' * 64, 'versions': {'python': '3.12.4'},\n"
    "          'lockfile_sha256': None}])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'sealed': True, 'reason': 'no manifest',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


GENERATION_LOOP = LOG_HELPER + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def _sentinel_test_author(bundle):\n"
    "    return {'model_call_error': None, 'file': None}\n"
    "_sentinel_test_author.sentinel_tag = 'TEST_AUTHOR_SENTINEL'\n"
    "\n"
    "def _sentinel_judge(bundle):\n"
    "    return {'result': 'pass', 'rationale': None}\n"
    "_sentinel_judge.sentinel_tag = 'JUDGE_SENTINEL'\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model, seed=seed, repo_root=str(repo_root),\n"
    "         repo_root_type=type(repo_root).__name__,\n"
    "         llm_backend_is_none=llm_backend is None,\n"
    "         test_author_id=id(_sentinel_test_author), judge_id=id(_sentinel_judge))\n"
    "    return (_sentinel_test_author, _sentinel_judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id)\n"
    "    return {'passed': False, 'stop_reason': 'max_attempts', 'attempts': [],\n"
    "            'generation_result': {'component_id': component_id,\n"
    "                'spec_bundle_hash': 'sha256:' + 'a' * 64, 'model': model,\n"
    "                'prompt_version': 'v1', 'cache_hit': False, 'files': {},\n"
    "                'model_call_error': None, 'refused': 'r', 'retry_feedback': None,\n"
    "                'mode': 'single', 'transcript_sha256': None, 'turns': 1,\n"
    "                'tool_calls': 0, 'isolation': None},\n"
    "            'verification_report': None, 'surface_report': None}\n"
)


VERIFIER = LOG_HELPER + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id, repo_root=str(repo_root),\n"
    "         judge_id=id(judge), test_author_id=id(test_author),\n"
    "         judge_tag=getattr(judge, 'sentinel_tag', None),\n"
    "         test_author_tag=getattr(test_author, 'sentinel_tag', None),\n"
    "         judge_callable=callable(judge), test_author_callable=callable(test_author))\n"
    "    return {'component_id': component_id,\n"
    "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001',\n"
    "                          'kind': 'compiled', 'result': 'pass'}],\n"
    "            'requirement_results': {'R-FOO-001': 'pass'},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:' + 'b' * 64,\n"
    "                        'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}],\n"
    "            'overall': 'pass'}\n"
)


LICENSE_SCANNER = LOG_HELPER + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id)\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
    "            'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
    "            'cache_hit': False}\n"
)


SECRET_SCANNER = LOG_HELPER + (
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan')\n"
    "    return {'scope': 'full', 'gate_version': 'secret_scanner@0.0.0',\n"
    "            'flagged': False, 'matches': [], 'allowed': [],\n"
    "            'unused_allowlist_entries': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    return scan(repo_root)\n"
)


PROVENANCE_WRITER = LOG_HELPER + (
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


SPEC_BUNDLE_ASSEMBLER = LOG_HELPER + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, mode=mode)\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:' + 'a' * 64,\n"
    "            'spec': '', 'interface': '', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {},\n"
    "            'testing': ''}\n"
)


PROVENANCE_TRACKER = LOG_HELPER + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id)\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "generation-loop": GENERATION_LOOP,
    "verifier-orchestrator": VERIFIER,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-writer": PROVENANCE_WRITER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "provenance-tracker": PROVENANCE_TRACKER,
}


def _write_fakes(repo_root):
    for slug, source in FAKES.items():
        module_name = slug.replace("-", "_")
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(source)


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_ac_gate_002b_sealed_closures_wired_from_make_closures(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    _write_fakes(repo_root)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m", seed=5)
    assert result is not None

    calls = _read_log(log_path)
    mc = [c for c in calls if c["call"] == "make_closures"]
    vc = [c for c in calls if c["call"] == "verify"]

    assert len(mc) == 1, calls
    assert mc[0]["model"] == "m"
    assert mc[0]["seed"] == 5
    assert mc[0]["repo_root"] == str(repo_root)
    assert mc[0]["llm_backend_is_none"] is True

    assert len(vc) == 1, calls
    assert vc[0]["component_id"] == "comp-foo"
    assert vc[0]["test_author_id"] == mc[0]["test_author_id"]
    assert vc[0]["judge_id"] == mc[0]["judge_id"]
    assert vc[0]["test_author_tag"] == "TEST_AUTHOR_SENTINEL"
    assert vc[0]["judge_tag"] == "JUDGE_SENTINEL"
    assert vc[0]["test_author_callable"] is True
    assert vc[0]["judge_callable"] is True

    # make_closures precedes verify
    assert calls.index(mc[0]) < calls.index(vc[0])