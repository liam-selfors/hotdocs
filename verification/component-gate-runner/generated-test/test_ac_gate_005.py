# hotdocs-criterion: sha256:c27835ece2c6ac7757b3362fb4e98ec233dbf8597ab405f661ccc234d9e6063d
import json
import os
from pathlib import Path

import component_gate_runner


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

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
                "lockfile_sha256": None}],
    "overall": "pass",
}

HIT_LICENSE = dict(LICENSE_RESULT, gate_version="license_scanner@4.0.0-no-reference-corpus", cache_hit=True)
HIT_SECRET = dict(SECRET_RESULT, cache_hit=True)

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
    "spec_bundle_hash": "sha256:ab",
    "model": "m1",
    "prompt_version": "v12",
    "cache_hit": False,
    "files": {},
    "model_call_error": {"category": "auth", "message": "bad key"},
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

ATTEMPT = {
    "number": 1,
    "outcome": "generation_failed",
    "retry_feedback": [],
    "error_category": "auth",
    "surface_ok": None,
    "overall": None,
    "failed_requirements": [],
    "transcript_sha256": None,
    "reauthored_tests": [],
}

LOOP_RESULT = {
    "passed": False,
    "stop_reason": "not_retried",
    "attempts": [ATTEMPT],
    "generation_result": GENERATION_RESULT,
    "verification_report": None,
    "surface_report": None,
}


HEADER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, **kw):\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as f:\n"
    "        f.write(json.dumps({'fn': name, 'args': kw}, default=str) + '\\n')\n"
    "\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_fake(repo_root, slug, body):
    module = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(HEADER + body)


def build_fakes(repo_root):
    write_fake(repo_root, "provenance-checker", (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr("sha256:ab") + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = " + repr(VERIFICATION_REPORT["assets"]) + "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id, repo_root=str(repo_root))\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id, repo_root=str(repo_root))\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id, repo_root=str(repo_root))\n"
        "    if os.environ.get('GATE_TEST_PROV') == 'hit':\n"
        "        return {'hit': True, 'reason': None,\n"
        "                'verification_report': " + repr(VERIFICATION_REPORT) + ",\n"
        "                'license_scan': " + repr(HIT_LICENSE) + ",\n"
        "                'secret_scan': " + repr(HIT_SECRET) + "}\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id, repo_root=str(repo_root))\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None, 'owners': None,\n"
        "            'source_hash': None, 'written_at': None}\n"
    ))
    write_fake(repo_root, "spec-bundle-assembler", (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, repo_root=str(repo_root), mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:ab', 'spec': 's',\n"
        "            'interface': 'i', 'constraints': 'c', 'dependency_interfaces': {},\n"
        "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {},\n"
        "            'glossary': '', 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
        "            'criterion_text': '', 'requirement_text': '', 'interface': '',\n"
        "            'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    ))
    write_fake(repo_root, "generation-loop", (
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, repo_root=str(repo_root), model=model)\n"
        "    return " + repr(LOOP_RESULT) + "\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model, repo_root=str(repo_root))\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))
    write_fake(repo_root, "provenance-tracker", (
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id, repo_root=str(repo_root))\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-a', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    ))
    write_fake(repo_root, "verifier-orchestrator", (
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id, repo_root=str(repo_root))\n"
        "    return " + repr(VERIFICATION_REPORT) + "\n"
    ))
    write_fake(repo_root, "license-scanner", (
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id, repo_root=str(repo_root))\n"
        "    return " + repr(LICENSE_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(LICENSE_RESULT["gate_version"]) + "\n"
    ))
    write_fake(repo_root, "secret-scanner", (
        "def scan(repo_root):\n"
        "    _log('secret_scan', repo_root=str(repo_root))\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return " + repr(dict(SECRET_RESULT, scope="precommit")) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(SECRET_RESULT["gate_version"]) + "\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
        "\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
    ))
    write_fake(repo_root, "provenance-writer", (
        "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id, repo_root=str(repo_root))\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id, repo_root=str(repo_root))\n"
        "    return None\n"
    ))


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def setup(tmp_path, monkeypatch, prov_mode):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    monkeypatch.setenv("GATE_TEST_PROV", prov_mode)
    build_fakes(repo_root)
    return repo_root, log_path


def test_miss_with_generation_failed_runs_both_scanners(tmp_path, monkeypatch):
    repo_root, log_path = setup(tmp_path, monkeypatch, "miss")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m1")

    calls = read_log(log_path)
    names = [c["fn"] for c in calls]
    assert "run_attempts" in names

    license_calls = [c for c in calls if c["fn"] == "license_scan"]
    secret_calls = [c for c in calls if c["fn"] == "secret_scan"]
    assert len(license_calls) == 1
    assert license_calls[0]["args"]["component_id"] == "comp-foo"
    assert license_calls[0]["args"]["repo_root"] == str(repo_root)
    assert len(secret_calls) == 1
    assert secret_calls[0]["args"]["repo_root"] == str(repo_root)

    assert field(result, "license_scan") == LICENSE_RESULT
    assert field(result, "secret_scan") == SECRET_RESULT
    assert field(result, "provenance_hit") is False


def test_short_circuiting_hit_calls_no_scanner(tmp_path, monkeypatch):
    repo_root, log_path = setup(tmp_path, monkeypatch, "hit")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m1")

    calls = read_log(log_path)
    names = [c["fn"] for c in calls]
    assert "check_provenance" in names
    assert "license_scan" not in names
    assert "secret_scan" not in names
    assert field(result, "provenance_hit") is True