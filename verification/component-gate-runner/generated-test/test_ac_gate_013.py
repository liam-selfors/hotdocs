# hotdocs-criterion: sha256:728abced4ef0d8d708684dcf6c1fe7aac9c4e8a7d5748efd8dc56947c276e356
import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "def _log(fn, **kw):\n"
    "    entry = {'fn': fn}\n"
    "    entry.update(kw)\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps(entry, default=repr) + '\\n')\n"
    "\n"
)


def _prefix(log_path):
    return "import json\nLOG = " + repr(str(log_path)) + "\n" + LOG_HELPER


def _write(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source)


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "pass",
}

LICENSE_SCAN = {
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

SECRET_SCAN = {
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

GENERATION_RESULT = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:k",
    "model": "m",
    "prompt_version": "v9",
    "cache_hit": False,
    "files": {"foo.py": "X = 1\n"},
    "model_call_error": None,
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

LOOP_RESULT = {
    "passed": True,
    "stop_reason": "passed",
    "attempts": [
        {"number": 1, "outcome": "passed", "retry_feedback": [],
         "error_category": None, "surface_ok": True, "overall": "pass",
         "failed_requirements": [], "transcript_sha256": None,
         "reauthored_tests": []}
    ],
    "generation_result": GENERATION_RESULT,
    "verification_report": VERIFICATION_REPORT,
    "surface_report": {"ok": True, "findings": []},
}

SPEC_BUNDLE = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:k",
    "spec": "spec",
    "interface": "iface",
    "constraints": "",
    "dependency_interfaces": {},
    "dependency_context": {},
    "dependency_usage": {},
    "vars": {},
    "glossary": "",
    "hint_code": None,
    "spec_bundle_parts": {"spec": "sha256:s", "dependency_code": "sha256:d"},
}

MANIFEST = {
    "spec_bundle_hash": "sha256:old",
    "spec_bundle_parts": {"spec": "sha256:s", "dependency_code": "sha256:d"},
    "model_pin": "m0",
    "prompt_version": "v9",
    "retry_feedback": None,
    "generation": {"mode": "agentic", "generator_version": "g@1",
                   "transcript_sha256": None, "turns": 4, "tool_calls": 7,
                   "isolation": "seatbelt"},
    "attempts": 2,
    "attempt_history": [{"number": 1, "outcome": "passed"}],
    "pipeline_version": "v1",
    "gate_versions": {"verifier": "v@1"},
    "provenance_hit": False,
    "generated_at": "2026-01-01T00:00:00Z",
    "verification_run_id": "run-1",
    "verification_report": VERIFICATION_REPORT,
    "license_scan": LICENSE_SCAN,
    "secret_scan": SECRET_SCAN,
    "assets": [],
    "drivers": [],
}


def _build(repo_root, log_path, reason):
    p = _prefix(log_path)

    _write(repo_root, "provenance-checker", p + (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:k'\n"
        "        self.spec_bundle_parts = {'spec': 'sha256:s', 'dependency_code': 'sha256:d'}\n"
        "        self.gate_versions = {'verifier': 'v@2'}\n"
        "        self.assets = []\n"
        "        self.drivers = []\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key')\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key')\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance')\n"
        "    return {'hit': False, 'reason': " + repr(reason) + ",\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance')\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    _write(repo_root, "spec-bundle-assembler", p + (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble')\n"
        "    return " + repr(SPEC_BUNDLE) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion')\n"
        "    return {}\n"
    ))

    _write(repo_root, "generation-loop", p + (
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "    'missing_asset', 'malformed_layout')\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts')\n"
        "    return " + repr(LOOP_RESULT) + "\n"
    ))

    _write(repo_root, "verifier-orchestrator", p + (
        "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify')\n"
        "    return " + repr(VERIFICATION_REPORT) + "\n"
    ))

    _write(repo_root, "license-scanner", p + (
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan')\n"
        "    return " + repr(LICENSE_SCAN) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    ))

    _write(repo_root, "secret-scanner", p + (
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return " + repr(SECRET_SCAN) + "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return " + repr(SECRET_SCAN) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    ))

    _write(repo_root, "provenance-writer", p + (
        "def _f(v, n):\n"
        "    return v.get(n) if isinstance(v, dict) else getattr(v, n, None)\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    gr = _f(inputs, 'generation_result')\n"
        "    _log('write_provenance',\n"
        "         spec_bundle_hash=_f(gr, 'spec_bundle_hash'),\n"
        "         gate_versions=_f(inputs, 'gate_versions'))\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance')\n"
        "    return None\n"
    ))

    _write(repo_root, "provenance-tracker", p + (
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record')\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
    ))

    manifest_dir = repo_root / "gen" / "foo"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / ".provenance.json").write_text(json.dumps(MANIFEST))


def _calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def _count(calls, fn):
    return sum(1 for c in calls if c["fn"] == fn)


@pytest.mark.parametrize("reason", ["hash formula differs", "gates differ"])
def test_reverify_reasons_reverify_committed_code(tmp_path, reason):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build(repo_root, log_path, reason)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log_path)
    assert _count(calls, "verify") == 1
    assert _count(calls, "run_attempts") == 0
    assert _count(calls, "assemble") == 0
    writes = [c for c in calls if c["fn"] == "write_provenance"]
    assert len(writes) == 1
    assert writes[0]["spec_bundle_hash"] == "sha256:k"
    assert writes[0]["gate_versions"] == {"verifier": "v@2"}
    assert field(result, "reverified") is True


@pytest.mark.parametrize("reason", ["gate_versions differ", "spec_bundle_hash differs"])
def test_other_reasons_proceed_as_miss(tmp_path, reason):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build(repo_root, log_path, reason)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log_path)
    assert _count(calls, "verify") == 0
    assert _count(calls, "run_attempts") == 1
    assert field(result, "reverified") is False