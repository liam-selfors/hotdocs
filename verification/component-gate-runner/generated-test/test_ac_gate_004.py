# hotdocs-criterion: sha256:561923a9310669c084c6598f552c8aacffbb206e24f52a320651217ca74cc3ad
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "CGR_AC_GATE_004_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_module(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source)


LOG_HELPER = (
    "import os\n"
    "def _log(line):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as fh:\n"
    "        fh.write(line + '\\n')\n"
)


PROVENANCE_CHECKER_SRC = LOG_HELPER + (
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key')\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key')\n"
    "    return ProvenanceKey(\n"
    "        'sha256:' + 'ab' * 32,\n"
    "        {'compiler': 'criterion-compiler@1.0.0', 'generated_test': 'generated_test@1.0.0',\n"
    "         'verifier': 'verifier-orchestrator@2.0.0', 'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "         'secret_scanner': 'secret_scanner@0.0.0', 'generator': 'generator@3.0.0+v11'},\n"
    "        [{'kind': 'python', 'path': '.', 'definition_sha256': None, 'adapter_sha256': None,\n"
    "          'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}],\n"
    "    )\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance')\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance')\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER_SRC = LOG_HELPER + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble')\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:' + 'ab' * 32,\n"
    "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {}, 'dependency_usage': {},\n"
    "            'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion')\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
    "            'dependency_interfaces': {}, 'testing': ''}\n"
)


def generation_loop_src(outcome, criteria):
    return LOG_HELPER + (
        "OUTCOME = " + repr(outcome) + "\n"
        "CRITERIA = " + repr(criteria) + "\n"
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    return (lambda bundle: {'model_call_error': None, 'file': None},\n"
        "            lambda bundle: {'result': 'pass', 'rationale': None})\n"
        "\n"
        "def _gen(component_id, files, model_call_error, refused):\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:' + 'ab' * 32,\n"
        "            'model': 'claude-sonnet-5', 'prompt_version': 'v12', 'cache_hit': False,\n"
        "            'files': files, 'model_call_error': model_call_error, 'refused': refused,\n"
        "            'retry_feedback': None, 'mode': 'single', 'transcript_sha256': None,\n"
        "            'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
        "                 on_attempt=None):\n"
        "    _log('run_attempts')\n"
        "    surface_report = None\n"
        "    report = None\n"
        "    error_category = None\n"
        "    surface_ok = None\n"
        "    overall = None\n"
        "    failed = []\n"
        "    if OUTCOME == 'generation_failed':\n"
        "        gen = _gen(component_id, {}, {'category': 'network', 'message': 'connection reset'}, None)\n"
        "        error_category = 'network'\n"
        "        stop_reason = 'not_retried'\n"
        "    elif OUTCOME == 'refused':\n"
        "        gen = _gen(component_id, {}, None, 'unsafe request')\n"
        "        stop_reason = 'refused'\n"
        "    elif OUTCOME == 'surface_failed':\n"
        "        gen = _gen(component_id, {'foo.py': 'x = 1\\n'}, None, None)\n"
        "        surface_report = {'ok': False, 'findings': [{'kind': 'dependency_name', 'message': 'bar has no fetch_all'}]}\n"
        "        surface_ok = False\n"
        "        stop_reason = 'max_attempts'\n"
        "    else:\n"
        "        gen = _gen(component_id, {'foo.py': 'x = 1\\n'}, None, None)\n"
        "        surface_report = {'ok': True, 'findings': []}\n"
        "        surface_ok = True\n"
        "        rr = {}\n"
        "        for c in CRITERIA:\n"
        "            rr[c['covers']] = c['result']\n"
        "        report = {'component_id': component_id, 'criteria': CRITERIA,\n"
        "                  'requirement_results': rr, 'interface_drift': False,\n"
        "                  'mutation_score': None, 'mutation_error': None,\n"
        "                  'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                              'adapter_sha256': None, 'versions': {'python': '3.12.4'},\n"
        "                              'lockfile_sha256': None}],\n"
        "                  'overall': 'fail'}\n"
        "        overall = 'fail'\n"
        "        failed = sorted(k for k, v in rr.items() if v == 'fail')\n"
        "        stop_reason = 'max_attempts'\n"
        "    attempt = {'number': 1, 'outcome': OUTCOME, 'retry_feedback': [],\n"
        "               'error_category': error_category, 'surface_ok': surface_ok,\n"
        "               'overall': overall, 'failed_requirements': failed,\n"
        "               'transcript_sha256': None, 'reauthored_tests': []}\n"
        "    if on_attempt is not None:\n"
        "        on_attempt(attempt, gen, report)\n"
        "    return {'passed': False, 'stop_reason': stop_reason, 'attempts': [attempt],\n"
        "            'generation_result': gen, 'verification_report': report,\n"
        "            'surface_report': surface_report}\n"
    )


PROVENANCE_TRACKER_SRC = LOG_HELPER + (
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record')\n"
    "    return {'attempt_id': '2026-10-25T14:32:01Z-a1b2c3', 'component_id': component_id,\n"
    "            'timestamp': '2026-10-25T14:32:01Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
)


LICENSE_SCANNER_SRC = LOG_HELPER + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan')\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus', 'similarity_score': None,\n"
    "            'block_threshold': None, 'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
)


SECRET_SCANNER_SRC = LOG_HELPER + (
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def _result(scope):\n"
    "    return {'scope': scope, 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
    "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan')\n"
    "    return _result('full')\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files')\n"
    "    return _result('precommit')\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_WRITER_SRC = LOG_HELPER + (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance')\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance')\n"
    "    return None\n"
)


IMPL_CRITERIA = [
    {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "fail",
     "failure_detail": {"message": "assert 3 == 5", "expected": 5, "actual": 3},
     "failure_origin": "implementation"},
]

TEST_ORIGIN_CRITERIA = [
    {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "fail",
     "failure_detail": {"message": "no sound test could run", "expected": None, "actual": None},
     "failure_origin": "test"},
    {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
]


def build_repo(repo_root, outcome, criteria):
    write_module(repo_root, "provenance-checker", PROVENANCE_CHECKER_SRC)
    write_module(repo_root, "spec-bundle-assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
    write_module(repo_root, "generation-loop", generation_loop_src(outcome, criteria))
    write_module(repo_root, "provenance-tracker", PROVENANCE_TRACKER_SRC)
    write_module(repo_root, "license-scanner", LICENSE_SCANNER_SRC)
    write_module(repo_root, "secret-scanner", SECRET_SCANNER_SRC)
    write_module(repo_root, "provenance-writer", PROVENANCE_WRITER_SRC)


@pytest.mark.parametrize(
    "outcome,criteria,reason",
    [
        ("generation_failed", IMPL_CRITERIA, "model_call_error"),
        ("surface_failed", IMPL_CRITERIA, "surface_check_failed"),
        ("verification_failed", IMPL_CRITERIA, "verification_failed"),
        ("refused", IMPL_CRITERIA, "refused"),
        ("verification_failed", TEST_ORIGIN_CRITERIA, "test_authoring_failed"),
    ],
)
def test_ac_gate_004_block_reason_from_last_attempt(tmp_path, monkeypatch, outcome, criteria, reason):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    build_repo(repo_root, outcome, criteria)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "claude-sonnet-5")

    calls = log_path.read_text().splitlines()
    assert "check_provenance" in calls
    assert "run_attempts" in calls

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == reason
    assert field(result, "provenance_hit") is False

    mce = field(result, "model_call_error")
    if reason == "model_call_error":
        assert field(mce, "category") == "network"
        assert field(mce, "message") == "connection reset"
    else:
        assert mce is None