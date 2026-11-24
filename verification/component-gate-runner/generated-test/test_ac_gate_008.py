# hotdocs-criterion: sha256:6ec2d222a2b97daa35469d43c1d92bbac76a1aa9c47e0bff5c119cb3ff44f5cc
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source)


CHECKER_SRC = (
    "class _Key:\n"
    "    def __init__(self):\n"
    "        self.spec_bundle_hash = 'sha256:k'\n"
    "        self.gate_versions = {'compiler': 'criterion-compiler@1.0.0',\n"
    "                              'generated_test': 'generated_test@1.0.0',\n"
    "                              'verifier': 'verifier-orchestrator@2.0.0',\n"
    "                              'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "                              'secret_scanner': 'secret_scanner@0.0.0',\n"
    "                              'generator': 'generator@3.0.0+v11'}\n"
    "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "                        'lockfile_sha256': None}]\n"
    "    def __getitem__(self, name):\n"
    "        return getattr(self, name)\n"
    "    def get(self, name, default=None):\n"
    "        return getattr(self, name, default)\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    return _Key()\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

ASSEMBLER_SRC = (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k',\n"
    "            'spec': 's', 'interface': 'i', 'constraints': 'c',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
    "            'dependency_interfaces': {}, 'testing': ''}\n"
)

LICENSE_SRC = (
    "def scan(component_id, repo_root):\n"
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

SECRET_SRC = (
    "def scan(repo_root):\n"
    "    return {'scope': 'full', 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
    "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
    "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    r = scan(repo_root)\n"
    "    r['scope'] = 'precommit'\n"
    "    return r\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

WRITER_SRC = (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    return None\n"
)

LOOP_COMMON = (
    "import json\n"
    "_KEEP = []\n"
    "\n"
    "def _gen(marker, files, err):\n"
    "    return {'component_id': 'comp-foo', 'spec_bundle_hash': 'sha256:k',\n"
    "            'model': 'test-model', 'prompt_version': marker, 'cache_hit': False,\n"
    "            'files': files, 'model_call_error': err, 'refused': None,\n"
    "            'retry_feedback': None, 'mode': 'single', 'transcript_sha256': None,\n"
    "            'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
    "\n"
    "def _report(marker):\n"
    "    return {'component_id': 'comp-foo',\n"
    "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled',\n"
    "                          'result': 'pass'}],\n"
    "            'requirement_results': {'R-FOO-001': 'pass'}, 'interface_drift': False,\n"
    "            'mutation_score': 0.9, 'mutation_error': None,\n"
    "            'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "                        'lockfile_sha256': None}],\n"
    "            'overall': 'pass', 'marker': marker}\n"
    "\n"
    "def _attempt(number, outcome, error_category, surface_ok, overall, retry_feedback):\n"
    "    return {'number': number, 'outcome': outcome, 'retry_feedback': retry_feedback,\n"
    "            'error_category': error_category, 'surface_ok': surface_ok,\n"
    "            'overall': overall, 'failed_requirements': [], 'transcript_sha256': None,\n"
    "            'reauthored_tests': []}\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
    "\n"
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
)

LOOP_TWO = (
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    g1 = _gen('g1', {}, {'category': 'truncated_response', 'message': 'cut off'})\n"
    "    g2 = _gen('g2', {'foo.py': 'x = 1\\n'}, None)\n"
    "    r2 = _report('r2')\n"
    "    _KEEP.extend([g1, g2, r2])\n"
    "    a1 = _attempt(1, 'generation_failed', 'truncated_response', None, None, [])\n"
    "    a2 = _attempt(2, 'passed', None, True, 'pass', [])\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps({'g1': id(g1), 'g2': id(g2), 'r2': id(r2)}) + '\\n')\n"
    "    on_attempt(a1, g1, None)\n"
    "    on_attempt(a2, g2, r2)\n"
    "    surface = {'ok': True, 'findings': []}\n"
    "    return {'passed': True, 'stop_reason': 'passed', 'attempts': [a1, a2],\n"
    "            'generation_result': g2, 'verification_report': r2,\n"
    "            'surface_report': surface}\n"
)

LOOP_ONE = (
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    g = _gen('g1', {'foo.py': 'x = 1\\n'}, None)\n"
    "    r = _report('r1')\n"
    "    _KEEP.extend([g, r])\n"
    "    a1 = _attempt(1, 'passed', None, True, 'pass', [])\n"
    "    on_attempt(a1, g, r)\n"
    "    surface = {'ok': True, 'findings': []}\n"
    "    return {'passed': True, 'stop_reason': 'passed', 'attempts': [a1],\n"
    "            'generation_result': g, 'verification_report': r,\n"
    "            'surface_report': surface}\n"
)

TRACKER_COMMON = (
    "import json\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
    "\n"
    "def _get(v, name):\n"
    "    return v[name] if isinstance(v, dict) else getattr(v, name)\n"
    "\n"
)

TRACKER_LOGGING = (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    entry = {'component_id': component_id,\n"
    "             'gen_id': id(generation_result),\n"
    "             'gen_marker': _get(generation_result, 'prompt_version'),\n"
    "             'report_is_none': verification_report is None,\n"
    "             'report_id': None if verification_report is None else id(verification_report),\n"
    "             'report_marker': None if verification_report is None else _get(verification_report, 'marker'),\n"
    "             'spec_bundle_hash': spec_bundle_hash}\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps(entry) + '\\n')\n"
    "    return {'attempt_id': '2026-11-24T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-11-24T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
)

TRACKER_RAISING = (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write('called\\n')\n"
    "    raise RuntimeError('attempt record write failed')\n"
)


def build_repo(repo_root, loop_body, tracker_body, loop_log, tracker_log):
    write_fake(repo_root, "provenance-checker", CHECKER_SRC)
    write_fake(repo_root, "spec-bundle-assembler", ASSEMBLER_SRC)
    write_fake(repo_root, "license-scanner", LICENSE_SRC)
    write_fake(repo_root, "secret-scanner", SECRET_SRC)
    write_fake(repo_root, "provenance-writer", WRITER_SRC)
    write_fake(
        repo_root,
        "generation-loop",
        "LOG = " + repr(str(loop_log)) + "\n" + LOOP_COMMON + loop_body,
    )
    write_fake(
        repo_root,
        "provenance-tracker",
        "LOG = " + repr(str(tracker_log)) + "\n" + TRACKER_COMMON + tracker_body,
    )


def read_lines(path):
    p = Path(path)
    if not p.exists():
        return []
    return [line for line in p.read_text().splitlines() if line.strip()]


def test_write_attempt_record_called_once_per_attempt(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    loop_log = logs / "loop.log"
    tracker_log = logs / "tracker.log"
    build_repo(repo_root, LOOP_TWO, TRACKER_LOGGING, loop_log, tracker_log)

    component_gate_runner.run_component_gates("comp-foo", repo_root, "test-model")

    loop_lines = read_lines(loop_log)
    assert len(loop_lines) == 1
    ids = json.loads(loop_lines[0])

    calls = [json.loads(line) for line in read_lines(tracker_log)]
    assert len(calls) == 2

    first, second = calls
    assert first["component_id"] == "comp-foo"
    assert first["gen_marker"] == "g1"
    assert first["gen_id"] == ids["g1"]
    assert first["report_is_none"] is True
    assert first["spec_bundle_hash"] == "sha256:k"

    assert second["component_id"] == "comp-foo"
    assert second["gen_marker"] == "g2"
    assert second["gen_id"] == ids["g2"]
    assert second["report_is_none"] is False
    assert second["report_marker"] == "r2"
    assert second["report_id"] == ids["r2"]
    assert second["spec_bundle_hash"] == "sha256:k"


def test_write_attempt_record_exception_does_not_change_result(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    loop_log = logs / "loop.log"
    tracker_log = logs / "tracker.log"
    build_repo(repo_root, LOOP_ONE, TRACKER_RAISING, loop_log, tracker_log)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "test-model")

    assert len(read_lines(tracker_log)) >= 1
    assert field(result, "blocked") is False