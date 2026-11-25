# hotdocs-criterion: sha256:a50e761fe4f2fe08c947c99a5e96ec9db87d045fceaa0cc9f36307d5a7d13147
"""AC-GATE-004: a loop that did not pass is blocked, with block_reason from
the last attempt's outcome (R-GATE-004)."""

from pathlib import Path

import pytest

import component_gate_runner


COMPONENT_ID = "comp-foo"
MODEL = "anthropic:claude-test-model"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_prelude(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(name):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
    )


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@3.5.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}

SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32


PROVENANCE_CHECKER_BODY = (
    "class _Key:\n"
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
    "    return _Key(SPEC_BUNDLE_HASH, dict(GATE_VERSIONS), [\n"
    "        {'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "         'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "         'lockfile_sha256': None}])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance')\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance')\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER_BODY = (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble')\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': SPEC_BUNDLE_HASH,\n"
    "            'spec': 'spec text', 'interface': 'interface text',\n"
    "            'constraints': '', 'dependency_interfaces': {},\n"
    "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {},\n"
    "            'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion')\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {},\n"
    "            'testing': ''}\n"
)

GENERATION_LOOP_BODY = (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "class _Obj:\n"
    "    def __init__(self, data):\n"
    "        self._data = dict(data)\n"
    "        for k, v in data.items():\n"
    "            setattr(self, k, v)\n"
    "    def to_dict(self):\n"
    "        out = {}\n"
    "        for k, v in self._data.items():\n"
    "            out[k] = v.to_dict() if hasattr(v, 'to_dict') else v\n"
    "        return out\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures')\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'skipped', 'rationale': None}\n"
    "    return (test_author, judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    if mode not in ('single', 'agentic') or max_attempts < 1:\n"
    "        raise ValueError('bad arguments')\n"
    "    _log('run_attempts')\n"
    "    gen = _Obj(SCENARIO['generation_result'])\n"
    "    surface = None\n"
    "    if SCENARIO['surface_report'] is not None:\n"
    "        surface = _Obj(SCENARIO['surface_report'])\n"
    "    verif = None\n"
    "    if SCENARIO['verification_report'] is not None:\n"
    "        verif = _Obj(SCENARIO['verification_report'])\n"
    "    attempt = dict(SCENARIO['attempt'])\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, gen, verif)\n"
    "    return _Obj({'passed': False, 'stop_reason': SCENARIO['stop_reason'],\n"
    "                 'attempts': [attempt], 'generation_result': gen,\n"
    "                 'verification_report': verif, 'surface_report': surface})\n"
)

PROVENANCE_TRACKER_BODY = (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record')\n"
    "    return {'attempt_id': '2026-11-25T00:00:00Z-a1b2c3',\n"
    "            'component_id': component_id,\n"
    "            'timestamp': '2026-11-25T00:00:00Z',\n"
    "            'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)

LICENSE_SCANNER_BODY = (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan')\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None,\n"
    "            'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
)

SECRET_SCANNER_BODY = (
    "class SecretScanResult:\n"
    "    def __init__(self):\n"
    "        self.scope = 'full'\n"
    "        self.gate_version = 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "        self.flagged = False\n"
    "        self.matches = []\n"
    "        self.allowed = []\n"
    "        self.unused_allowlist_entries = []\n"
    "        self.notified = False\n"
    "        self.notification_delivery_error = None\n"
    "        self.cache_hit = False\n"
    "    def to_dict(self):\n"
    "        return dict(vars(self))\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan')\n"
    "    return SecretScanResult()\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    r = SecretScanResult()\n"
    "    r.scope = 'precommit'\n"
    "    return r\n"
)

PROVENANCE_WRITER_BODY = (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance')\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance')\n"
    "    return None\n"
)


def _generation_result(files, model_call_error, refused):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model": MODEL,
        "prompt_version": "v12",
        "cache_hit": False,
        "files": files,
        "model_call_error": model_call_error,
        "refused": refused,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def _verification_report(criteria, requirement_results):
    return {
        "component_id": COMPONENT_ID,
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "fail",
    }


def _attempt(outcome, error_category, surface_ok, overall, failed_requirements):
    return {
        "number": 1,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": failed_requirements,
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


IMPLEMENTATION_FAIL = {
    "id": "AC-FOO-001",
    "covers": "R-FOO-001",
    "kind": "generated-test",
    "result": "fail",
    "failure_detail": {"message": "result.foo equals 5 failed", "expected": 5, "actual": 3},
    "failure_origin": "implementation",
}

TEST_FAIL = {
    "id": "AC-FOO-001",
    "covers": "R-FOO-001",
    "kind": "generated-test",
    "result": "fail",
    "failure_detail": {"message": "no sound test could be authored", "expected": None, "actual": None},
    "failure_origin": "test",
}

FOO_002_PASS = {
    "id": "AC-FOO-002",
    "covers": "R-FOO-002",
    "kind": "compiled",
    "result": "pass",
}

FILES = {"foo.py": "X = 1\n"}


def _scenario(outcome):
    if outcome == "generation_failed":
        return {
            "stop_reason": "not_retried",
            "generation_result": _generation_result(
                {}, {"category": "network", "message": "connection reset"}, None
            ),
            "surface_report": None,
            "verification_report": None,
            "attempt": _attempt("generation_failed", "network", None, None, []),
        }
    if outcome == "surface_failed":
        return {
            "stop_reason": "max_attempts",
            "generation_result": _generation_result(dict(FILES), None, None),
            "surface_report": {
                "ok": False,
                "findings": [{"kind": "import_error", "message": "cannot import foo"}],
            },
            "verification_report": None,
            "attempt": _attempt("surface_failed", None, False, None, []),
        }
    if outcome == "verification_failed":
        return {
            "stop_reason": "max_attempts",
            "generation_result": _generation_result(dict(FILES), None, None),
            "surface_report": {"ok": True, "findings": []},
            "verification_report": _verification_report(
                [dict(IMPLEMENTATION_FAIL)], {"R-FOO-001": "fail"}
            ),
            "attempt": _attempt("verification_failed", None, True, "fail", ["R-FOO-001"]),
        }
    if outcome == "refused":
        return {
            "stop_reason": "refused",
            "generation_result": _generation_result({}, None, "spec bundle refused"),
            "surface_report": None,
            "verification_report": None,
            "attempt": _attempt("refused", None, None, None, []),
        }
    raise AssertionError("unknown outcome " + outcome)


def _test_origin_scenario():
    return {
        "stop_reason": "max_attempts",
        "generation_result": _generation_result(dict(FILES), None, None),
        "surface_report": {"ok": True, "findings": []},
        "verification_report": _verification_report(
            [dict(TEST_FAIL), dict(FOO_002_PASS)],
            {"R-FOO-001": "fail", "R-FOO-002": "pass"},
        ),
        "attempt": _attempt("verification_failed", None, True, "fail", []),
    }


def _build_repo(repo_root, scenario):
    log_path = repo_root / "calls.log"
    prelude = _log_prelude(log_path)
    shared = (
        "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH) + "\n"
        "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        "\n"
    )
    gen = repo_root / "gen"
    _write(gen / "provenance-checker" / "provenance_checker.py",
           prelude + shared + PROVENANCE_CHECKER_BODY)
    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
           prelude + shared + SPEC_BUNDLE_ASSEMBLER_BODY)
    _write(gen / "generation-loop" / "generation_loop.py",
           prelude + "SCENARIO = " + repr(scenario) + "\n\n" + GENERATION_LOOP_BODY)
    _write(gen / "provenance-tracker" / "provenance_tracker.py",
           prelude + PROVENANCE_TRACKER_BODY)
    _write(gen / "license-scanner" / "license_scanner.py",
           prelude + LICENSE_SCANNER_BODY)
    _write(gen / "secret-scanner" / "secret_scanner.py",
           prelude + SECRET_SCANNER_BODY)
    _write(gen / "provenance-writer" / "provenance_writer.py",
           prelude + PROVENANCE_WRITER_BODY)
    return log_path


def _calls(log_path):
    if not log_path.is_file():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize(
    "outcome, reason",
    [
        ("generation_failed", "model_call_error"),
        ("surface_failed", "surface_check_failed"),
        ("verification_failed", "verification_failed"),
        ("refused", "refused"),
    ],
)
def test_block_reason_follows_last_attempt_outcome(tmp_path, outcome, reason):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = _build_repo(repo_root, _scenario(outcome))

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    calls = _calls(log_path)
    assert "check_provenance" in calls
    assert "run_attempts" in calls

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == reason


def test_all_failures_of_test_origin_give_test_authoring_failed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = _build_repo(repo_root, _test_origin_scenario())

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    calls = _calls(log_path)
    assert "check_provenance" in calls
    assert "run_attempts" in calls

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "test_authoring_failed"