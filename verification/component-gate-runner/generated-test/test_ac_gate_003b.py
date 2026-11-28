# hotdocs-criterion: sha256:d84b1db834a9b061e911223d3813450252863a31dc885e0c020e03765a3703a4
import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source)


def _header(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps(entry) + '\\n')\n"
        "\n"
    )


VERIFICATION_REPORT = {
    "component_id": COMPONENT_ID,
    "criteria": [
        {
            "id": "AC-FOO-001",
            "covers": "R-FOO-001",
            "kind": "compiled",
            "result": "fail",
            "failure_detail": {"message": "x failed", "expected": 1, "actual": 2},
            "failure_origin": "implementation",
        }
    ],
    "requirement_results": {"R-FOO-001": "fail"},
    "interface_drift": False,
    "mutation_score": None,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "fail",
}

GENERATION_RESULT = {
    "component_id": COMPONENT_ID,
    "spec_bundle_hash": "sha256:abc",
    "model": "m1",
    "prompt_version": "v1",
    "cache_hit": False,
    "files": {"foo.py": "x = 1\n"},
    "model_call_error": None,
    "refused": None,
    "retry_feedback": ["R-FOO-001"],
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

SURFACE_REPORT = {"ok": True, "findings": []}


def _attempt(number, retry_feedback):
    return {
        "number": number,
        "outcome": "verification_failed",
        "retry_feedback": retry_feedback,
        "error_category": None,
        "surface_ok": True,
        "overall": "fail",
        "failed_requirements": ["R-FOO-001"],
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


ATTEMPTS = [
    _attempt(1, []),
    _attempt(2, ["R-FOO-001"]),
    _attempt(3, ["R-FOO-001"]),
]

LOOP_RESULT = {
    "passed": False,
    "stop_reason": "max_attempts",
    "attempts": ATTEMPTS,
    "generation_result": GENERATION_RESULT,
    "verification_report": VERIFICATION_REPORT,
    "surface_report": SURFACE_REPORT,
}

LICENSE_SCAN = {
    "component_id": COMPONENT_ID,
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

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}

SPEC_BUNDLE_PARTS = {"spec": "sha256:aaa", "dependency_code": "sha256:bbb"}


def _build_fakes(repo_root, log_path):
    h = _header(log_path)

    _write(
        repo_root,
        "provenance-checker",
        h
        + "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:abc'\n"
        "        self.spec_bundle_parts = " + repr(SPEC_BUNDLE_PARTS) + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None, 'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}]\n"
        "        self.drivers = []\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log({'call': 'current_sealed_key'})\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log({'call': 'current_provenance_key'})\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log({'call': 'check_provenance'})\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log({'call': 'check_sealed_provenance'})\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None, 'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None, 'written_at': None}\n",
    )

    _write(
        repo_root,
        "spec-bundle-assembler",
        h
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log({'call': 'assemble', 'mode': mode})\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc', 'spec': '', 'interface': '', 'constraints': '', 'dependency_interfaces': {}, 'dependency_context': {}, 'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None, 'spec_bundle_parts': "
        + repr(SPEC_BUNDLE_PARTS)
        + "}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log({'call': 'assemble_criterion'})\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '', 'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n",
    )

    _write(
        repo_root,
        "generation-loop",
        h
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response', 'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file', 'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3, retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log({'call': 'run_attempts', 'component_id': component_id, 'model': model, 'mode': mode, 'max_attempts': max_attempts, 'retry_feedback': retry_feedback, 'seed': seed})\n"
        "    return " + repr(LOOP_RESULT) + "\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log({'call': 'make_closures'})\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n",
    )

    _write(
        repo_root,
        "provenance-tracker",
        h
        + "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log({'call': 'write_attempt_record'})\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id, 'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash, 'generation': {}, 'verification': None}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n",
    )

    _write(
        repo_root,
        "verifier-orchestrator",
        h
        + "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log({'call': 'verify'})\n"
        "    return " + repr(VERIFICATION_REPORT) + "\n",
    )

    _write(
        repo_root,
        "license-scanner",
        h
        + "def scan(component_id, repo_root):\n"
        "    _log({'call': 'license_scan'})\n"
        "    return " + repr(LICENSE_SCAN) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.0-no-reference-corpus'\n",
    )

    _write(
        repo_root,
        "secret-scanner",
        h
        + "def scan(repo_root):\n"
        "    _log({'call': 'secret_scan'})\n"
        "    return " + repr(SECRET_SCAN) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n",
    )

    _write(
        repo_root,
        "provenance-writer",
        h
        + "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log({'call': 'write_provenance'})\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log({'call': 'write_sealed_provenance'})\n"
        "    return None\n",
    )


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_gate_003b_run_attempts_called_once_and_blocked(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fakes(repo_root, log_path)

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m1")

    calls = _read_log(log_path)
    run_calls = [c for c in calls if c["call"] == "run_attempts"]
    assert len(run_calls) == 1, calls
    assert run_calls[0]["retry_feedback"] is None
    assert run_calls[0]["max_attempts"] == 3

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"
    assert field(result, "attempts") == ATTEMPTS