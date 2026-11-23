# hotdocs-criterion: sha256:203d41da42881218dd98d5cb3846884a1287b5eb77b5cae4050cc53229ee017c
import json
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = (
    "import json\n"
    "import os\n"
    "\n"
    "\n"
    "def _conv(v):\n"
    "    if isinstance(v, str):\n"
    "        return v\n"
    "    if isinstance(v, os.PathLike):\n"
    "        return os.fspath(v)\n"
    "    return repr(v)\n"
    "\n"
    "\n"
    "def _log(fn, **params):\n"
    "    rec = {'fn': fn, 'params': dict((k, _conv(v)) for k, v in params.items())}\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as fh:\n"
    "        fh.write(json.dumps(rec) + '\\n')\n"
    "\n"
    "\n"
)


def verification_report(overall):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:abcd",
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": overall,
    }


LICENSE_RESULT = {
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
    "cache_hit": False,
}

SECRET_RESULT = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@3.5.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}

GENERATION_RESULT = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:1234",
    "model": "m1",
    "prompt_version": "v12",
    "cache_hit": False,
    "files": {},
    "model_call_error": None,
    "refused": "no budget",
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

LOOP_RESULT = {
    "passed": False,
    "stop_reason": "not_retried",
    "attempts": [
        {
            "number": 1,
            "outcome": "generation_failed",
            "retry_feedback": [],
            "error_category": None,
            "surface_ok": None,
            "overall": None,
            "failed_requirements": [],
            "transcript_sha256": None,
            "reauthored_tests": [],
        }
    ],
    "generation_result": GENERATION_RESULT,
    "verification_report": None,
    "surface_report": None,
}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_fakes(repo_root, check_result):
    gen = repo_root / "gen"

    write(
        gen / "provenance-checker" / "provenance_checker.py",
        COMMON
        + "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        + "CHECK_RESULT = " + repr(check_result) + "\n"
        + "\n"
        + "class _Key:\n"
        + "    def __init__(self):\n"
        + "        self.spec_bundle_hash = " + repr("sha256:1234") + "\n"
        + "        self.gate_versions = dict(GATE_VERSIONS)\n"
        + "        self.assets = []\n"
        + "\n"
        + "def current_sealed_key(component_id, repo_root):\n"
        + "    _log('provenance_checker.current_sealed_key', component_id=component_id, repo_root=repo_root)\n"
        + "    return None\n"
        + "\n"
        + "def current_provenance_key(component_id, repo_root):\n"
        + "    _log('provenance_checker.current_provenance_key', component_id=component_id, repo_root=repo_root)\n"
        + "    return _Key()\n"
        + "\n"
        + "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        + "    _log('provenance_checker.check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash, repo_root=repo_root)\n"
        + "    return CHECK_RESULT\n"
        + "\n"
        + "def check_sealed_provenance(component_id, repo_root):\n"
        + "    _log('provenance_checker.check_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
        + "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
        + "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None, 'written_at': None}\n",
    )

    write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        COMMON
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        + "    _log('spec_bundle_assembler.assemble', component_id=component_id, repo_root=repo_root, mode=mode)\n"
        + "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:1234', 'spec': 's',\n"
        + "            'interface': 'i', 'constraints': 'c', 'dependency_interfaces': {},\n"
        + "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        + "\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    _log('spec_bundle_assembler.assemble_criterion', component_id=component_id, criterion_id=criterion_id, repo_root=repo_root)\n"
        + "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',\n"
        + "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
        + "            'dependency_interfaces': {}, 'testing': ''}\n",
    )

    write(
        gen / "generation-loop" / "generation_loop.py",
        COMMON
        + "LOOP_RESULT = " + repr(LOOP_RESULT) + "\n"
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        + "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        + "                      'missing_asset', 'malformed_layout')\n"
        + "\n"
        + "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        + "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
        + "                 on_attempt=None):\n"
        + "    _log('generation_loop.run_attempts', component_id=component_id, repo_root=repo_root, model=model)\n"
        + "    return LOOP_RESULT\n"
        + "\n"
        + "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        + "    _log('generation_loop.make_closures', model=model, seed=seed, repo_root=repo_root)\n"
        + "    def test_author(bundle):\n"
        + "        return {'model_call_error': None, 'file': None}\n"
        + "    def judge(bundle):\n"
        + "        return {'result': 'pass', 'rationale': None}\n"
        + "    return (test_author, judge)\n",
    )

    write(
        gen / "provenance-tracker" / "provenance_tracker.py",
        COMMON
        + "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        + "    _log('provenance_tracker.write_attempt_record', component_id=component_id, repo_root=repo_root)\n"
        + "    return {'attempt_id': '2026-10-25T14:32:01Z-a1', 'component_id': component_id,\n"
        + "            'timestamp': '2026-10-25T14:32:01Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        + "            'generation': {}, 'verification': None}\n"
        + "\n"
        + "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        + "    _log('provenance_tracker.check_readiness', repo_root=repo_root)\n"
        + "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {}, 'not_ready_reasons': []}\n"
        + "\n"
        + "def last_requirement_failures(component_id, repo_root):\n"
        + "    _log('provenance_tracker.last_requirement_failures', component_id=component_id, repo_root=repo_root)\n"
        + "    return []\n",
    )

    write(
        gen / "verifier-orchestrator" / "verifier_orchestrator.py",
        COMMON
        + "REPORT = " + repr(verification_report("pass")) + "\n"
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        + "DEFAULT_TEST_TIMEOUT = 300.0\n"
        + "\n"
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        + "    _log('verifier_orchestrator.verify', component_id=component_id, repo_root=repo_root)\n"
        + "    return REPORT\n",
    )

    write(
        gen / "license-scanner" / "license_scanner.py",
        COMMON
        + "RESULT = " + repr(LICENSE_RESULT) + "\n"
        + "\n"
        + "def scan(component_id, repo_root):\n"
        + "    _log('license_scanner.scan', component_id=component_id, repo_root=repo_root)\n"
        + "    return RESULT\n"
        + "\n"
        + "def gate_version(repo_root):\n"
        + "    _log('license_scanner.gate_version', repo_root=repo_root)\n"
        + "    return RESULT['gate_version']\n",
    )

    write(
        gen / "secret-scanner" / "secret_scanner.py",
        COMMON
        + "RESULT = " + repr(SECRET_RESULT) + "\n"
        + "\n"
        + "def scan(repo_root):\n"
        + "    _log('secret_scanner.scan', repo_root=repo_root)\n"
        + "    return RESULT\n"
        + "\n"
        + "def scan_files(paths, repo_root=None):\n"
        + "    _log('secret_scanner.scan_files', repo_root=repo_root)\n"
        + "    out = dict(RESULT)\n"
        + "    out['scope'] = 'precommit'\n"
        + "    return out\n"
        + "\n"
        + "def gate_version(repo_root):\n"
        + "    _log('secret_scanner.gate_version', repo_root=repo_root)\n"
        + "    return RESULT['gate_version']\n"
        + "\n"
        + "def propose(repo_root):\n"
        + "    _log('secret_scanner.propose', repo_root=repo_root)\n"
        + "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )

    write(
        gen / "provenance-writer" / "provenance_writer.py",
        COMMON
        + "def write_provenance(component_id, inputs, repo_root):\n"
        + "    _log('provenance_writer.write_provenance', component_id=component_id, repo_root=repo_root)\n"
        + "    return None\n"
        + "\n"
        + "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        + "    _log('provenance_writer.write_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
        + "    return None\n",
    )


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def setup(tmp_path, monkeypatch, check_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    build_fakes(repo_root, check_result)
    return repo_root, log_path


def test_miss_with_generation_failed_runs_both_scanners(tmp_path, monkeypatch):
    miss = {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
    repo_root, log_path = setup(tmp_path, monkeypatch, miss)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m1")

    calls = read_log(log_path)
    fns = [c["fn"] for c in calls]
    assert "generation_loop.run_attempts" in fns

    license_calls = [c for c in calls if c["fn"] == "license_scanner.scan"]
    assert len(license_calls) == 1
    assert license_calls[0]["params"]["component_id"] == "comp-foo"
    assert license_calls[0]["params"]["repo_root"] == str(repo_root)

    secret_calls = [c for c in calls if c["fn"] == "secret_scanner.scan"]
    assert len(secret_calls) == 1
    assert secret_calls[0]["params"]["repo_root"] == str(repo_root)

    assert field(result, "license_scan") == LICENSE_RESULT
    assert field(result, "secret_scan") == SECRET_RESULT


def test_short_circuiting_hit_calls_neither_scanner(tmp_path, monkeypatch):
    hit = {
        "hit": True,
        "reason": None,
        "verification_report": verification_report("pass"),
        "license_scan": dict(LICENSE_RESULT, gate_version="license_scanner@4.0.0-hit"),
        "secret_scan": dict(SECRET_RESULT, gate_version="secret_scanner@hit"),
    }
    repo_root, log_path = setup(tmp_path, monkeypatch, hit)

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m1")

    calls = read_log(log_path)
    fns = [c["fn"] for c in calls]
    assert "provenance_checker.check_provenance" in fns
    assert "license_scanner.scan" not in fns
    assert "secret_scanner.scan" not in fns