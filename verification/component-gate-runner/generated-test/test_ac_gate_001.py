# hotdocs-criterion: sha256:d295de24c1f1b0fc88c174eb1467ab9e18084368b6976e1d81dd19849b70756f
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_GATE_TEST_LOG"
DATA_ENV = "HOTDOCS_GATE_TEST_DATA"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(fn, **kwargs):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'fn': fn, 'kwargs': kwargs}, default=repr, sort_keys=True) + '\\n')\n"
    "\n"
    "def _data():\n"
    "    with open(os.environ[" + repr(DATA_ENV) + "], encoding='utf-8') as fh:\n"
    "        return json.load(fh)\n"
    "\n"
)


PROVENANCE_CHECKER = COMMON + (
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('provenance_checker.current_sealed_key', component_id=component_id, repo_root=str(repo_root))\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('provenance_checker.current_provenance_key', component_id=component_id, repo_root=str(repo_root))\n"
    "    return ProvenanceKey('sha256:k', {'verifier': 'v@1'}, [\n"
    "        {'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "         'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "         'lockfile_sha256': None}])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('provenance_checker.check_provenance', component_id=component_id,\n"
    "         spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions,\n"
    "         repo_root=str(repo_root))\n"
    "    d = _data()\n"
    "    return {'hit': True, 'reason': None,\n"
    "            'verification_report': d['hit_verification_report'],\n"
    "            'license_scan': d['hit_license_scan'],\n"
    "            'secret_scan': d['hit_secret_scan']}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('provenance_checker.check_sealed_provenance', component_id=component_id, repo_root=str(repo_root))\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER = COMMON + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('spec_bundle_assembler.assemble', component_id=component_id, repo_root=str(repo_root), mode=mode)\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k',\n"
    "            'spec': 'spec', 'interface': 'interface', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('spec_bundle_assembler.assemble_criterion', component_id=component_id,\n"
    "         criterion_id=criterion_id, repo_root=str(repo_root))\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP = COMMON + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('generation_loop.run_attempts', component_id=component_id, repo_root=str(repo_root),\n"
    "         model=model, mode=mode, max_attempts=max_attempts,\n"
    "         retry_feedback=retry_feedback, seed=seed)\n"
    "    d = _data()\n"
    "    return {\n"
    "        'passed': False,\n"
    "        'stop_reason': 'max_attempts',\n"
    "        'attempts': [{'number': 1, 'outcome': 'verification_failed', 'retry_feedback': [],\n"
    "                      'error_category': None, 'surface_ok': True, 'overall': 'fail',\n"
    "                      'failed_requirements': ['R-FOO-001'], 'transcript_sha256': None,\n"
    "                      'reauthored_tests': []}],\n"
    "        'generation_result': {\n"
    "            'component_id': component_id, 'spec_bundle_hash': 'sha256:k',\n"
    "            'model': model, 'prompt_version': 'v1', 'cache_hit': False,\n"
    "            'files': {'foo.py': 'x = 1\\n'}, 'model_call_error': None, 'refused': None,\n"
    "            'retry_feedback': None, 'mode': 'single', 'transcript_sha256': None,\n"
    "            'turns': 1, 'tool_calls': 0, 'isolation': None},\n"
    "        'verification_report': d['miss_verification_report'],\n"
    "        'surface_report': {'ok': True, 'findings': []},\n"
    "    }\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('generation_loop.make_closures', model=model, seed=seed, repo_root=str(repo_root))\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)


VERIFIER_ORCHESTRATOR = COMMON + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verifier_orchestrator.verify', component_id=component_id, repo_root=str(repo_root))\n"
    "    return _data()['miss_verification_report']\n"
)


LICENSE_SCANNER = COMMON + (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scanner.scan', component_id=component_id, repo_root=str(repo_root))\n"
    "    return _data()['fresh_license_scan']\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    _log('license_scanner.gate_version', repo_root=str(repo_root))\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)


SECRET_SCANNER = COMMON + (
    "def scan(repo_root):\n"
    "    _log('secret_scanner.scan', repo_root=str(repo_root))\n"
    "    return _data()['fresh_secret_scan']\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scanner.scan_files', repo_root=str(repo_root))\n"
    "    r = dict(_data()['fresh_secret_scan'])\n"
    "    r['scope'] = 'precommit'\n"
    "    return r\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    _log('secret_scanner.gate_version', repo_root=str(repo_root))\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "def propose(repo_root):\n"
    "    _log('secret_scanner.propose', repo_root=str(repo_root))\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_TRACKER = COMMON + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('provenance_tracker.write_attempt_record', component_id=component_id,\n"
    "         spec_bundle_hash=spec_bundle_hash, repo_root=str(repo_root))\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-000001', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('provenance_tracker.check_readiness', repo_root=str(repo_root))\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('provenance_tracker.last_requirement_failures', component_id=component_id,\n"
    "         repo_root=str(repo_root))\n"
    "    return []\n"
)


PROVENANCE_WRITER = COMMON + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('provenance_writer.write_provenance', component_id=component_id, repo_root=str(repo_root))\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('provenance_writer.write_sealed_provenance', component_id=component_id,\n"
    "         repo_root=str(repo_root))\n"
    "    return None\n"
)


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generation-loop": GENERATION_LOOP,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-tracker": PROVENANCE_TRACKER,
    "provenance-writer": PROVENANCE_WRITER,
}


def verification_report(overall, marker):
    result = "pass" if overall == "pass" else "fail"
    criterion = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": result}
    if result == "fail":
        criterion["failure_detail"] = {"message": "x failed", "expected": 1, "actual": 2}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": "comp-foo",
        "criteria": [criterion],
        "requirement_results": {"R-FOO-001": result},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + marker, "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "overall": overall,
    }


def license_scan(marker):
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": marker == "hit",
    }


def secret_scan(marker):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": marker == "hit",
    }


def build(tmp_path, monkeypatch, hit_overall):
    repo_root = tmp_path / "repo"
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")
    data = {
        "hit_verification_report": verification_report(hit_overall, "aa"),
        "hit_license_scan": license_scan("hit"),
        "hit_secret_scan": secret_scan("hit"),
        "miss_verification_report": verification_report("fail", "bb"),
        "fresh_license_scan": license_scan("fresh"),
        "fresh_secret_scan": secret_scan("fresh"),
    }
    data_path = tmp_path / "data.json"
    data_path.write_text(json.dumps(data), encoding="utf-8")
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.setenv(DATA_ENV, str(data_path))
    return repo_root, log_path, data


def read_log(log_path):
    lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_passing_hit_short_circuits(tmp_path, monkeypatch):
    repo_root, log_path, data = build(tmp_path, monkeypatch, "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    log = read_log(log_path)
    names = [entry["fn"] for entry in log]
    idx = [i for i, n in enumerate(names) if n == "provenance_checker.check_provenance"]
    assert len(idx) == 1, names
    call = log[idx[0]]["kwargs"]
    assert call["spec_bundle_hash"] == "sha256:k"
    assert call["gate_versions"] == {"verifier": "v@1"}
    assert idx[0] == len(log) - 1, names

    assert field(result, "provenance_hit") is True
    assert field(result, "blocked") is False
    assert field(result, "verification") == data["hit_verification_report"]


def test_failed_hit_proceeds_as_miss(tmp_path, monkeypatch):
    repo_root, log_path, data = build(tmp_path, monkeypatch, "fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    log = read_log(log_path)
    names = [entry["fn"] for entry in log]
    assert names.count("generation_loop.run_attempts") == 1, names
    assert field(result, "provenance_hit") is False