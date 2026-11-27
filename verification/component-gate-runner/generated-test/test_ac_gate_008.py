# hotdocs-criterion: sha256:d79f54cb94a0ccf5815530a687e167c891dc07b54a853e1d1db124c8c04d9bb1
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _header(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(name, **kw):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps({'call': name, 'args': kw}, default=repr) + '\\n')\n"
        "\n"
    )


def _write(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source)


def _verification_report(overall):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
             "result": "pass" if overall == "pass" else "fail"},
        ],
        "requirement_results": {"R-FOO-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def _generation_result(files, model_call_error, marker):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "model": marker,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": files,
        "model_call_error": model_call_error,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def _attempt(number, outcome, error_category, surface_ok, overall):
    return {
        "number": number,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": [],
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


def _build_fakes(repo_root, log_path, scripted, loop_result, tracker_raises):
    h = _header(log_path)

    _write(repo_root, "provenance-checker", h + (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:k'\n"
        "        self.spec_bundle_parts = {'spec': 'sha256:s', 'dependency_code': 'sha256:d'}\n"
        "        self.gate_versions = {'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@1.0.0',\n"
        "            'verifier': 'verifier-orchestrator@4.0.0',\n"
        "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
        "            'secret_scanner': 'secret_scanner@3.1.0',\n"
        "            'generator': 'generator@3.0.0+v11'}\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "            'adapter_sha256': 'sha256:a', 'versions': {'python': '3.12.4'},\n"
        "            'lockfile_sha256': None}]\n"
        "        self.drivers = []\n"
        "    def __getitem__(self, name):\n"
        "        return getattr(self, name)\n"
        "    def get(self, name, default=None):\n"
        "        return getattr(self, name, default)\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id, repo_root=str(repo_root))\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id, repo_root=str(repo_root))\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash)\n"
        "    return {'hit': False, 'reason': 'spec_bundle_hash differs',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    _write(repo_root, "spec-bundle-assembler", h + (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k',\n"
        "            'spec': 's', 'interface': 'i', 'constraints': 'c',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
        "            'hint_code': None,\n"
        "            'spec_bundle_parts': {'spec': 'sha256:s', 'dependency_code': 'sha256:d'}}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    ))

    _write(repo_root, "generation-loop", h + (
        "SCRIPTED = " + repr(scripted) + "\n"
        "RESULT = " + repr(loop_result) + "\n"
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "    'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model)\n"
        "    for attempt, gen, rep in SCRIPTED:\n"
        "        on_attempt(attempt, gen, rep)\n"
        "    return RESULT\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))

    tracker_tail = "    raise RuntimeError('tracker exploded')\n" if tracker_raises else (
        "    return {'attempt_id': '2026-01-01T00:00:00Z-abc', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': generation_result, 'verification': verification_report}\n"
    )
    _write(repo_root, "provenance-tracker", h + (
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id,\n"
        "         generation_result=generation_result,\n"
        "         verification_report=verification_report,\n"
        "         spec_bundle_hash=spec_bundle_hash, repo_root=str(repo_root))\n"
    ) + tracker_tail + (
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    ))

    _write(repo_root, "verifier-orchestrator", h + (
        "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return " + repr(_verification_report("pass")) + "\n"
    ))

    _write(repo_root, "license-scanner", h + (
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

    _write(repo_root, "secret-scanner", h + (
        "def _result(scope):\n"
        "    return {'scope': scope, 'gate_version': 'secret_scanner@3.1.0',\n"
        "            'flagged': False, 'matches': [], 'allowed': [],\n"
        "            'unused_allowlist_entries': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return _result('full')\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    return _result('precommit')\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0'\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
        "\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
    ))

    _write(repo_root, "provenance-writer", h + (
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
    ))


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_write_attempt_record_called_once_per_attempt(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    g1 = _generation_result({}, {"category": "truncated_response", "message": "cut off"}, "g1-marker")
    g2 = _generation_result({"foo.py": "x = 1\n"}, None, "g2-marker")
    r2 = _verification_report("pass")
    a1 = _attempt(1, "generation_failed", "truncated_response", None, None)
    a2 = _attempt(2, "passed", None, True, "pass")
    scripted = [(a1, g1, None), (a2, g2, r2)]
    loop_result = {
        "passed": True,
        "stop_reason": "passed",
        "attempts": [a1, a2],
        "generation_result": g2,
        "verification_report": r2,
        "surface_report": {"ok": True, "findings": []},
    }
    _build_fakes(repo_root, log_path, scripted, loop_result, tracker_raises=False)

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = [c for c in _read_log(log_path) if c["call"] == "write_attempt_record"]
    assert len(calls) == 2, calls

    first = calls[0]["args"]
    assert first["component_id"] == "comp-foo"
    assert first["generation_result"] == g1
    assert first["verification_report"] is None
    assert first["spec_bundle_hash"] == "sha256:k"
    assert first["repo_root"] == str(repo_root)

    second = calls[1]["args"]
    assert second["component_id"] == "comp-foo"
    assert second["generation_result"] == g2
    assert second["verification_report"] == r2
    assert second["spec_bundle_hash"] == "sha256:k"
    assert second["repo_root"] == str(repo_root)


def test_write_attempt_record_exception_does_not_change_result(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    g = _generation_result({"foo.py": "x = 1\n"}, None, "g-marker")
    r = _verification_report("pass")
    a = _attempt(1, "passed", None, True, "pass")
    scripted = [(a, g, r)]
    loop_result = {
        "passed": True,
        "stop_reason": "passed",
        "attempts": [a],
        "generation_result": g,
        "verification_report": r,
        "surface_report": {"ok": True, "findings": []},
    }
    _build_fakes(repo_root, log_path, scripted, loop_result, tracker_raises=True)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = [c for c in _read_log(log_path) if c["call"] == "write_attempt_record"]
    assert len(calls) == 1, calls
    assert field(result, "blocked") is False