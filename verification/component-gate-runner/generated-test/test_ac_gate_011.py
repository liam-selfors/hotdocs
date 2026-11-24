# hotdocs-criterion: sha256:09a45f1d5c816c8d249bbcfcbb65950f194bf3c80e41cce277e8606aebff9755
import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, **kw):\n"
    "    rec = dict(kw)\n"
    "    rec['call'] = name\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as fh:\n"
    "        fh.write(json.dumps(rec, default=repr) + '\\n')\n"
    "\n"
    "def _f(v, n, d=None):\n"
    "    if isinstance(v, dict):\n"
    "        return v.get(n, d)\n"
    "    return getattr(v, n, d)\n"
    "\n"
    "def _plain(v):\n"
    "    if v is None or isinstance(v, (dict, list, str, int, float, bool)):\n"
    "        return v\n"
    "    if hasattr(v, 'to_dict') and callable(v.to_dict):\n"
    "        return v.to_dict()\n"
    "    if hasattr(v, '__dict__'):\n"
    "        return dict((k, x) for k, x in vars(v).items() if not k.startswith('_'))\n"
    "    return repr(v)\n"
    "\n"
    "def _report(component_id, overall, marker):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': marker, 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass' if overall == 'pass' else 'fail'}],\n"
    "        'requirement_results': {'R-FOO-001': 'pass' if overall == 'pass' else 'fail'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'assets': [],\n"
    "        'overall': overall,\n"
    "    }\n"
    "\n"
)

PROVENANCE_CHECKER = PRELUDE + (
    "class _Key(object):\n"
    "    def __init__(self):\n"
    "        self.spec_bundle_hash = 'sha256:k'\n"
    "        self.gate_versions = {'verifier': 'v@1'}\n"
    "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:a', 'versions': {'python': '3'}, 'lockfile_sha256': None}]\n"
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
    "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash,\n"
    "         gate_versions=gate_versions)\n"
    "    return {'hit': False, 'reason': os.environ['GATE_TEST_REASON'],\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)

GENERATION_LOOP = PRELUDE + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "class AttemptLoopResult(object):\n"
    "    def __init__(self, passed, stop_reason, attempts, generation_result, verification_report, surface_report):\n"
    "        self.passed = passed\n"
    "        self.stop_reason = stop_reason\n"
    "        self.attempts = attempts\n"
    "        self.generation_result = generation_result\n"
    "        self.verification_report = verification_report\n"
    "        self.surface_report = surface_report\n"
    "    def to_dict(self):\n"
    "        return {'passed': self.passed, 'stop_reason': self.stop_reason, 'attempts': self.attempts,\n"
    "                'generation_result': self.generation_result,\n"
    "                'verification_report': self.verification_report,\n"
    "                'surface_report': self.surface_report}\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model, seed=seed, repo_root=str(repo_root))\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    test_author.tag = 'TA-TOKEN'\n"
    "    judge.tag = 'JUDGE-TOKEN'\n"
    "    return (test_author, judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
    "                 on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id, model=model)\n"
    "    gen = {'component_id': component_id, 'spec_bundle_hash': 'sha256:loop', 'model': model,\n"
    "           'prompt_version': 'v1', 'cache_hit': False, 'files': {'foo.py': 'x = 1\\n'},\n"
    "           'model_call_error': None, 'refused': None, 'retry_feedback': None, 'mode': 'single',\n"
    "           'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [], 'error_category': None,\n"
    "               'surface_ok': True, 'overall': 'pass', 'failed_requirements': [],\n"
    "               'transcript_sha256': None, 'reauthored_tests': []}\n"
    "    return AttemptLoopResult(True, 'passed', [attempt], gen,\n"
    "                             _report(component_id, 'pass', 'AC-FOO-LOOP'),\n"
    "                             {'ok': True, 'findings': []})\n"
)

VERIFIER = PRELUDE + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id, repo_root=str(repo_root),\n"
    "         repo_root_type=type(repo_root).__name__,\n"
    "         judge_tag=getattr(judge, 'tag', None), test_author_tag=getattr(test_author, 'tag', None))\n"
    "    return _report(component_id, os.environ['GATE_TEST_OVERALL'], 'AC-FOO-REVERIFY')\n"
)

LICENSE = PRELUDE + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id)\n"
    "    return {'component_id': component_id, 'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': True, 'reason': None, 'similarity_score': 0.1, 'block_threshold': 0.7,\n"
    "            'blocked': os.environ['GATE_TEST_LBLOCKED'] == '1', 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
)

SECRET = PRELUDE + (
    "def _result(scope):\n"
    "    flagged = os.environ['GATE_TEST_SFLAGGED'] == '1'\n"
    "    matches = [{'rule_id': 'Fake Rule', 'risk_tier': 'low', 'file': 'gen/foo/foo.py', 'line': 1}] if flagged else []\n"
    "    return {'scope': scope, 'gate_version': 'secret_scanner@3.1.0', 'flagged': flagged,\n"
    "            'matches': matches, 'allowed': [], 'unused_allowlist_entries': [], 'notified': False,\n"
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
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0'\n"
    "\n"
    "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

ASSEMBLER = PRELUDE + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, mode=mode)\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k', 'spec': 's',\n"
    "            'interface': 'i', 'constraints': 'c', 'dependency_interfaces': {},\n"
    "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
    "            'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
    "            'dependency_interfaces': {}, 'testing': ''}\n"
)

WRITER = PRELUDE + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    gr = _f(inputs, 'generation_result')\n"
    "    if isinstance(gr, dict):\n"
    "        gen_keys = sorted(gr.keys())\n"
    "    else:\n"
    "        gen_keys = sorted(k for k in vars(gr) if not k.startswith('_'))\n"
    "    rec = {}\n"
    "    for k in ('component_id', 'verification_report', 'license_scan_result', 'secret_scan_result',\n"
    "              'provenance_hit', 'attempts', 'attempt_history', 'gate_versions'):\n"
    "        rec[k] = _plain(_f(inputs, k))\n"
    "    _log('write_provenance', component_id=component_id, inputs=rec,\n"
    "         generation_result=_plain(gr), generation_keys=gen_keys)\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id)\n"
)

TRACKER = PRELUDE + (
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id)\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': _plain(generation_result), 'verification': _plain(verification_report)}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)

FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "generation-loop": GENERATION_LOOP,
    "verifier-orchestrator": VERIFIER,
    "license-scanner": LICENSE,
    "secret-scanner": SECRET,
    "spec-bundle-assembler": ASSEMBLER,
    "provenance-writer": WRITER,
    "provenance-tracker": TRACKER,
}

ATTEMPT_HISTORY = [
    {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
     "error_category": None, "failed_requirements": ["R-FOO-002"], "transcript_sha256": None},
    {"number": 2, "outcome": "passed", "retry_feedback": ["R-FOO-002"],
     "error_category": None, "failed_requirements": [], "transcript_sha256": None},
]

MANIFEST = {
    "spec_bundle_hash": "sha256:k",
    "model_pin": "m0",
    "prompt_version": "v9",
    "retry_feedback": None,
    "generation": {"mode": "agentic", "generator_version": "generator@3.0.0+v9",
                   "transcript_sha256": None, "turns": 4, "tool_calls": 7,
                   "isolation": "seatbelt"},
    "attempts": 2,
    "attempt_history": ATTEMPT_HISTORY,
    "pipeline_version": "v1",
    "gate_versions": {"verifier": "v@0"},
    "provenance_hit": False,
    "generated_at": "2026-01-01T00:00:00Z",
    "verification_run_id": "run-1",
    "verification_report": {"overall": "pass"},
    "license_scan": {"blocked": False},
    "secret_scan": {"flagged": False},
    "assets": [],
}


def expected_report(overall, marker):
    return {
        "component_id": "comp-foo",
        "criteria": [{"id": marker, "covers": "R-FOO-001", "kind": "compiled",
                      "result": "pass" if overall == "pass" else "fail"}],
        "requirement_results": {"R-FOO-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


def setup_repo(tmp_path, monkeypatch, reason, overall, lblocked, sflagged):
    repo_root = tmp_path / "repo"
    for slug, src in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(src)
    (repo_root / "gen" / "foo").mkdir(parents=True, exist_ok=True)
    (repo_root / "gen" / "foo" / ".provenance.json").write_text(json.dumps(MANIFEST))
    log = tmp_path / "calls.log"
    log.write_text("")
    monkeypatch.setenv("GATE_TEST_LOG", str(log))
    monkeypatch.setenv("GATE_TEST_REASON", reason)
    monkeypatch.setenv("GATE_TEST_OVERALL", overall)
    monkeypatch.setenv("GATE_TEST_LBLOCKED", "1" if lblocked else "0")
    monkeypatch.setenv("GATE_TEST_SFLAGGED", "1" if sflagged else "0")
    return repo_root, log


def read_log(log):
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def names(calls):
    return [c["call"] for c in calls]


def test_environment_differs_passing_reverification(tmp_path, monkeypatch):
    repo_root, log = setup_repo(tmp_path, monkeypatch, "environment differs", "pass", False, False)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = read_log(log)
    n = names(calls)

    verify_calls = [c for c in calls if c["call"] == "verify"]
    assert len(verify_calls) == 1
    vc = verify_calls[0]
    assert vc["component_id"] == "comp-foo"
    assert vc["repo_root"] == str(repo_root)
    assert vc["judge_tag"] == "JUDGE-TOKEN"
    assert vc["test_author_tag"] == "TA-TOKEN"

    assert "assemble" not in n
    assert "run_attempts" not in n
    assert "write_attempt_record" not in n

    wp = [i for i, c in enumerate(calls) if c["call"] == "write_provenance"]
    assert len(wp) == 1
    wp_i = wp[0]
    assert "license_scan" in n[:wp_i]
    assert "secret_scan" in n[:wp_i]

    rec = calls[wp_i]
    inputs = rec["inputs"]
    assert inputs["verification_report"] == expected_report("pass", "AC-FOO-REVERIFY")
    assert field(inputs["license_scan_result"], "blocked") is False
    assert field(inputs["license_scan_result"], "component_id") == "comp-foo"
    assert field(inputs["secret_scan_result"], "flagged") is False
    assert field(inputs["secret_scan_result"], "scope") == "full"
    assert inputs["attempts"] == 2
    assert inputs["attempt_history"] == ATTEMPT_HISTORY
    assert inputs["provenance_hit"] is False
    assert inputs["gate_versions"] == {"verifier": "v@1"}

    gr = rec["generation_result"]
    assert field(gr, "files") == {}
    assert field(gr, "spec_bundle_hash") == "sha256:k"
    assert field(gr, "model") == "m0"
    assert field(gr, "prompt_version") == "v9"
    assert field(gr, "mode") == "agentic"
    assert field(gr, "turns") == 4
    assert field(gr, "tool_calls") == 7
    assert field(gr, "isolation") == "seatbelt"
    assert "generator_version" not in rec["generation_keys"]

    assert field(result, "reverified") is True
    assert field(result, "blocked") is False
    assert field(result, "provenance_hit") is False
    assert field(result, "attempts") == []
    assert field(result, "verification") == expected_report("pass", "AC-FOO-REVERIFY")


@pytest.mark.parametrize(
    "overall,lblocked,sflagged",
    [("fail", False, False), ("pass", True, False), ("pass", False, True)],
)
def test_environment_differs_failing_reverification_proceeds_as_miss(
    tmp_path, monkeypatch, overall, lblocked, sflagged
):
    repo_root, log = setup_repo(tmp_path, monkeypatch, "environment differs", overall, lblocked, sflagged)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = read_log(log)
    n = names(calls)
    assert "check_provenance" in n
    after = n[n.index("check_provenance") + 1:]
    after = [x for x in after if x != "make_closures"]
    assert after == [
        "verify", "license_scan", "secret_scan", "assemble", "run_attempts",
        "license_scan", "secret_scan", "write_provenance",
    ]
    wp = [c for c in calls if c["call"] == "write_provenance"]
    assert len(wp) == 1
    gr = wp[0]["generation_result"]
    assert field(gr, "files") == {"foo.py": "x = 1\n"}
    assert field(gr, "spec_bundle_hash") == "sha256:loop"
    assert field(result, "reverified") is False


def test_assets_differ_does_not_reverify(tmp_path, monkeypatch):
    repo_root, log = setup_repo(tmp_path, monkeypatch, "assets differ", "pass", False, False)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    n = names(read_log(log))
    assert "verify" not in n
    assert n.count("run_attempts") == 1
    assert field(result, "reverified") is False