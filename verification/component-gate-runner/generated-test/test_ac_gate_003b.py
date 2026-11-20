# hotdocs-criterion: sha256:663567ba4389b25556adbc1b41b619772f1e8e23b13093dad2116679949bb55a
import json
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG_AC_GATE_003B"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@3.5.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}

ASSETS = [
    {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": "sha256:aa",
        "versions": {"python": "3.12.4"},
        "lockfile_sha256": None,
    }
]

ATTEMPTS = [
    {
        "number": 1,
        "outcome": "verification_failed",
        "retry_feedback": [],
        "error_category": None,
        "surface_ok": True,
        "overall": "fail",
        "failed_requirements": ["R-FOO-002"],
        "transcript_sha256": None,
        "reauthored_tests": [],
    },
    {
        "number": 2,
        "outcome": "verification_failed",
        "retry_feedback": ["R-FOO-002"],
        "error_category": None,
        "surface_ok": True,
        "overall": "fail",
        "failed_requirements": ["R-FOO-002"],
        "transcript_sha256": None,
        "reauthored_tests": [],
    },
    {
        "number": 3,
        "outcome": "verification_failed",
        "retry_feedback": ["R-FOO-002"],
        "error_category": None,
        "surface_ok": True,
        "overall": "fail",
        "failed_requirements": ["R-FOO-002"],
        "transcript_sha256": None,
        "reauthored_tests": [],
    },
]

GENERATION_RESULT = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:abc123",
    "model": "m0",
    "prompt_version": "v12",
    "cache_hit": False,
    "files": {"foo.py": "X = 1\n"},
    "model_call_error": None,
    "refused": None,
    "retry_feedback": ["R-FOO-002"],
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {
            "id": "AC-FOO-002",
            "covers": "R-FOO-002",
            "kind": "compiled",
            "result": "fail",
            "failure_detail": {"message": "result.foo equals 5 failed", "expected": 5, "actual": 3},
            "failure_origin": "implementation",
        },
    ],
    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
    "interface_drift": False,
    "mutation_score": 0.5,
    "mutation_error": None,
    "assets": ASSETS,
    "overall": "fail",
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
    "gate_version": "secret_scanner@0.0.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, **data):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as fh:\n"
    "        fh.write(json.dumps(dict(call=name, args=data), default=repr) + '\\n')\n"
    "\n"
)


def _write(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(LOG_HELPER + source)


def _build_fakes(repo_root):
    _write(
        repo_root,
        "provenance-checker",
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:abc123'\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = " + repr(ASSETS) + "\n"
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
        "    return dict(hit=False, reason='no manifest', verification_report=None,\n"
        "                license_scan=None, secret_scan=None)\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return dict(hit=False, sealed=False, reason='not_sealed', verification_report=None,\n"
        "                license_scan=None, secret_scan=None, owners=None, source_hash=None,\n"
        "                written_at=None)\n",
    )
    _write(
        repo_root,
        "spec-bundle-assembler",
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return dict(component_id=component_id, spec_bundle_hash='sha256:abc123',\n"
        "                spec='spec', interface='iface', constraints='',\n"
        "                dependency_interfaces=dict(), dependency_context=dict(),\n"
        "                dependency_usage=dict(), vars=dict(), glossary='', hint_code=None)\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id)\n"
        "    return dict(component_id=component_id, criterion_id=criterion_id, covers='R-FOO-001',\n"
        "                criterion_text='', requirement_text='', interface='', glossary='',\n"
        "                dependency_interfaces=dict(), testing='')\n",
    )
    _write(
        repo_root,
        "generation-loop",
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model, mode=mode,\n"
        "         max_attempts=max_attempts, retry_feedback=retry_feedback, seed=seed,\n"
        "         allow_unisolated_exec=allow_unisolated_exec)\n"
        "    return dict(passed=False, stop_reason='max_attempts',\n"
        "                attempts=" + repr(ATTEMPTS) + ",\n"
        "                generation_result=" + repr(GENERATION_RESULT) + ",\n"
        "                verification_report=" + repr(VERIFICATION_REPORT) + ",\n"
        "                surface_report=dict(ok=True, findings=[]))\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model, seed=seed)\n"
        "    def test_author(bundle):\n"
        "        return dict(model_call_error=None, file=None)\n"
        "    def judge(bundle):\n"
        "        return dict(result='pass', rationale=None)\n"
        "    return (test_author, judge)\n",
    )
    _write(
        repo_root,
        "provenance-tracker",
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id)\n"
        "    return dict(attempt_id='2026-01-01T00:00:00Z-a1b2c3', component_id=component_id,\n"
        "                timestamp='2026-01-01T00:00:00Z', spec_bundle_hash=spec_bundle_hash,\n"
        "                generation=dict(), verification=None)\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return dict(scope='whole-corpus', ready=True, components=dict(), capabilities=dict(),\n"
        "                not_ready_reasons=[])\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures', component_id=component_id)\n"
        "    return []\n",
    )
    _write(
        repo_root,
        "verifier-orchestrator",
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return " + repr(VERIFICATION_REPORT) + "\n",
    )
    _write(
        repo_root,
        "license-scanner",
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return " + repr(LICENSE_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.0-no-reference-corpus'\n",
    )
    _write(
        repo_root,
        "secret-scanner",
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n"
        "\n"
        "def propose(repo_root):\n"
        "    return dict(allowlist=dict(version=1, entries=[]), ineligible=[])\n",
    )
    _write(
        repo_root,
        "provenance-writer",
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
        "    return None\n",
    )


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_ac_gate_003b_run_attempts_called_once_without_retry_feedback(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    _build_fakes(repo_root)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m0")

    calls = _read_log(log_path)
    run_calls = [c for c in calls if c["call"] == "run_attempts"]
    assert len(run_calls) == 1, calls
    args = run_calls[0]["args"]
    assert args["retry_feedback"] is None
    assert args["max_attempts"] == 3
    assert args["component_id"] == "comp-foo"

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"
    assert field(result, "model_call_error") is None
    assert field(result, "provenance_hit") is False
    assert field(result, "attempts") == ATTEMPTS