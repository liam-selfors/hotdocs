# hotdocs-criterion: sha256:1e2a1494af74eaa520e3ff7df3174ffbbd07bc7ee18f627930a68dd0c526c3a7
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "def _log(entry):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
)


def _write_module(repo_root, slug, body, log_path):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + LOG_HELPER + "\n" + body
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


PROVENANCE_CHECKER = (
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
    "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
    "    return SealedKey(['pipeline-team'], 'legacy/foo/', 'sha256:' + '0' * 64,\n"
    "                     'verifier-orchestrator@2.0.0')\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
    "    return ProvenanceKey('sha256:' + 'a' * 64, {'compiler': 'c@1', 'generated_test': 'g@1',\n"
    "        'verifier': 'v@1', 'license_scanner': 'l@1', 'secret_scanner': 's@1',\n"
    "        'generator': 'gen@1+v1'}, [])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': True, 'reason': 'no manifest',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

GENERATION_LOOP = (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "    'missing_asset', 'malformed_layout')\n"
    "\n"
    "def _sentinel_test_author(bundle):\n"
    "    return {'model_call_error': None, 'file': None}\n"
    "_sentinel_test_author.sentinel_tag = 'SENTINEL_TEST_AUTHOR'\n"
    "\n"
    "def _sentinel_judge(bundle):\n"
    "    return {'result': 'pass', 'rationale': None}\n"
    "_sentinel_judge.sentinel_tag = 'SENTINEL_JUDGE'\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'call': 'make_closures', 'model': model, 'seed': seed,\n"
    "          'seed_type': type(seed).__name__,\n"
    "          'repo_root': str(repo_root), 'llm_backend_is_none': llm_backend is None,\n"
    "          'test_author_id': id(_sentinel_test_author), 'judge_id': id(_sentinel_judge)})\n"
    "    return (_sentinel_test_author, _sentinel_judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log({'call': 'run_attempts', 'component_id': component_id})\n"
    "    return {'passed': False, 'stop_reason': 'max_attempts', 'attempts': [],\n"
    "            'generation_result': None, 'verification_report': None,\n"
    "            'surface_report': None}\n"
)

VERIFIER = (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify', 'component_id': component_id,\n"
    "          'judge_id': id(judge), 'test_author_id': id(test_author),\n"
    "          'judge_tag': getattr(judge, 'sentinel_tag', None),\n"
    "          'test_author_tag': getattr(test_author, 'sentinel_tag', None)})\n"
    "    return {'component_id': component_id,\n"
    "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001',\n"
    "                          'kind': 'compiled', 'result': 'pass'}],\n"
    "            'requirement_results': {'R-FOO-001': 'pass'},\n"
    "            'interface_drift': False, 'mutation_score': None,\n"
    "            'mutation_error': None, 'assets': [], 'overall': 'pass'}\n"
)

LICENSE = (
    "def scan(component_id, repo_root):\n"
    "    _log({'call': 'license_scan', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus', 'similarity_score': None,\n"
    "            'block_threshold': None, 'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET = (
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return {'scope': 'full', 'gate_version': 'secret_scanner@3.1.0', 'flagged': False,\n"
    "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
    "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    return scan(repo_root)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

WRITER = (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_sealed_provenance', 'component_id': component_id})\n"
    "    return None\n"
)

ASSEMBLER = (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'call': 'assemble', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:' + 'a' * 64,\n"
    "            'spec': '', 'interface': '', 'constraints': '', 'dependency_interfaces': {},\n"
    "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {},\n"
    "            'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {}\n"
)

TRACKER = (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record', 'component_id': component_id})\n"
    "    return {'attempt_id': 'x', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': None, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_sealed_component_wires_make_closures_into_verify(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    _write_module(repo_root, "provenance-checker", PROVENANCE_CHECKER, log_path)
    _write_module(repo_root, "generation-loop", GENERATION_LOOP, log_path)
    _write_module(repo_root, "verifier-orchestrator", VERIFIER, log_path)
    _write_module(repo_root, "license-scanner", LICENSE, log_path)
    _write_module(repo_root, "secret-scanner", SECRET, log_path)
    _write_module(repo_root, "provenance-writer", WRITER, log_path)
    _write_module(repo_root, "spec-bundle-assembler", ASSEMBLER, log_path)
    _write_module(repo_root, "provenance-tracker", TRACKER, log_path)

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m", seed=5)

    entries = _read_log(log_path)
    make_calls = [e for e in entries if e["call"] == "make_closures"]
    verify_calls = [e for e in entries if e["call"] == "verify"]

    assert len(make_calls) == 1, entries
    mc = make_calls[0]
    assert mc["model"] == "m"
    assert mc["seed"] == 5
    assert mc["seed_type"] == "int"
    assert mc["repo_root"] == str(repo_root)

    assert len(verify_calls) == 1, entries
    vc = verify_calls[0]
    assert vc["component_id"] == "comp-foo"
    assert vc["test_author_tag"] == "SENTINEL_TEST_AUTHOR"
    assert vc["judge_tag"] == "SENTINEL_JUDGE"
    assert vc["test_author_id"] == mc["test_author_id"]
    assert vc["judge_id"] == mc["judge_id"]

    order = [e["call"] for e in entries]
    assert order.index("make_closures") < order.index("verify")
    assert "run_attempts" not in order