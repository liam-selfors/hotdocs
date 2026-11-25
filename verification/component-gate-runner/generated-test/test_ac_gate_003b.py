# hotdocs-criterion: sha256:2378f8e4ca25a03dd0c033e319185799b2211cdf9ee96c1279036f2ae8da1c1a
import json
import os
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_HEADER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, **kwargs):\n"
    "    path = os.environ['GATE_TEST_LOG']\n"
    "    entry = {'call': name, 'args': kwargs}\n"
    "    with open(path, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry, default=repr, sort_keys=True) + '\\n')\n"
    "\n"
)


def _write_fake(repo_root, slug, body):
    module_name = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(COMMON_HEADER + body, encoding="utf-8")


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
             "result": "fail", "failure_origin": "implementation",
             "failure_detail": {"message": "m", "expected": 1, "actual": 2}},
        ],
        "requirement_results": {"R-FOO-001": "fail"},
        "interface_drift": False,
        "mutation_score": 0.5,
        "mutation_error": None,
        "assets": [],
        "overall": "fail",
    }


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:abc123",
        "model": "test-model",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "x = 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def _attempts():
    out = []
    for n in (1, 2, 3):
        out.append({
            "number": n,
            "outcome": "verification_failed",
            "retry_feedback": [] if n == 1 else ["R-FOO-001"],
            "error_category": None,
            "surface_ok": True,
            "overall": "fail",
            "failed_requirements": ["R-FOO-001"],
            "transcript_sha256": None,
            "reauthored_tests": [],
        })
    return out


def _build_fakes(repo_root):
    # provenance-checker
    _write_fake(repo_root, "provenance-checker", (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:abc123'\n"
        "        self.gate_versions = {'compiler': 'c@1', 'generated_test': 'g@1', 'verifier': 'v@1',\n"
        "                              'license_scanner': 'l@1', 'secret_scanner': 's@1', 'generator': 'gen@1+v1'}\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                        'adapter_sha256': None, 'versions': {}, 'lockfile_sha256': None}]\n"
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
        "    _log('check_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None, 'owners': None,\n"
        "            'source_hash': None, 'written_at': None}\n"
    ))

    # spec-bundle-assembler
    _write_fake(repo_root, "spec-bundle-assembler", (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
        "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
        "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
        "            'dependency_interfaces': {}, 'testing': ''}\n"
    ))

    # generation-loop
    _write_fake(repo_root, "generation-loop", (
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "GEN = " + repr(_generation_result()) + "\n"
        "VER = " + repr(_verification_report()) + "\n"
        "ATTEMPTS = " + repr(_attempts()) + "\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model, mode=mode,\n"
        "         max_attempts=max_attempts, retry_feedback=retry_feedback, seed=seed,\n"
        "         allow_unisolated_exec=allow_unisolated_exec)\n"
        "    gen = dict(GEN)\n"
        "    ver = dict(VER)\n"
        "    attempts = [dict(a) for a in ATTEMPTS]\n"
        "    if on_attempt is not None:\n"
        "        for a in attempts:\n"
        "            on_attempt(a, gen, ver)\n"
        "    return {'passed': False, 'stop_reason': 'max_attempts', 'attempts': attempts,\n"
        "            'generation_result': gen, 'verification_report': ver,\n"
        "            'surface_report': {'ok': True, 'findings': []}}\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model, seed=seed)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))

    # provenance-tracker
    _write_fake(repo_root, "provenance-tracker", (
        "import pathlib\n"
        "_COUNTER = [0]\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id, spec_bundle_hash=spec_bundle_hash)\n"
        "    _COUNTER[0] += 1\n"
        "    d = pathlib.Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
        "    d.mkdir(parents=True, exist_ok=True)\n"
        "    aid = '2026-01-01T00:00:0' + str(_COUNTER[0]) + 'Z-fake'\n"
        "    record = {'attempt_id': aid, 'component_id': component_id,\n"
        "              'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "              'generation': {}, 'verification': None}\n"
        "    (d / (aid + '.json')).write_text(json.dumps(record), encoding='utf-8')\n"
        "    return record\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
        "            'secret_scan': None, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    ))

    # license-scanner
    _write_fake(repo_root, "license-scanner", (
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
    ))

    # secret-scanner
    _write_fake(repo_root, "secret-scanner", (
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return {'scope': 'full', 'gate_version': 'secret_scanner@3.1.0',\n"
        "            'flagged': False, 'matches': [], 'allowed': [],\n"
        "            'unused_allowlist_entries': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    return {'scope': 'precommit', 'flagged': False, 'matches': [], 'allowed': [],\n"
        "            'unused_allowlist_entries': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0'\n"
    ))

    # provenance-writer
    _write_fake(repo_root, "provenance-writer", (
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id)\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id)\n"
        "    return None\n"
    ))

    # verifier-orchestrator (not expected on this path; present so no real copy is needed)
    _write_fake(repo_root, "verifier-orchestrator", (
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return " + repr(_verification_report()) + "\n"
    ))


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_gate_003b_run_attempts_called_once_without_retry_feedback(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))

    _build_fakes(repo_root)

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "test-model")

    calls = _read_log(log_path)
    run_calls = [c for c in calls if c["call"] == "run_attempts"]
    assert len(run_calls) == 1, calls
    args = run_calls[0]["args"]
    assert args["retry_feedback"] is None
    assert args["max_attempts"] == 3

    # never makes its own generator/closure calls on this path
    assert not [c for c in calls if c["call"] == "make_closures"]

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"

    attempts = field(result, "attempts")
    assert attempts == _attempts()
    assert len(attempts) == 3
    assert attempts[-1]["outcome"] == "verification_failed"