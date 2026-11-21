# hotdocs-criterion: sha256:6ea3754933007b4478b07052811d3fd1c1fbb8f742e0f5dc40fe10bbcb5c7d21
import json
import os
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"
LOG_ENV = "GATE_FAKE_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GEN_PASS = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:abc",
    "model": "m-test",
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

GEN_FAIL = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:abc",
    "model": "m-test",
    "prompt_version": "v1",
    "cache_hit": False,
    "files": {},
    "model_call_error": {"category": "network", "message": "down"},
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

VER = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
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
            "adapter_sha256": "sha256:00",
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ],
    "overall": "pass",
}

LIC = {
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

SEC = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+fake",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

ATTEMPTS_PASS = [
    {
        "number": 1, "outcome": "verification_failed", "retry_feedback": [],
        "error_category": None, "surface_ok": True, "overall": "fail",
        "failed_requirements": ["R-FOO-001"], "transcript_sha256": None,
        "reauthored_tests": [],
    },
    {
        "number": 2, "outcome": "passed", "retry_feedback": ["R-FOO-001"],
        "error_category": None, "surface_ok": True, "overall": "pass",
        "failed_requirements": [], "transcript_sha256": None,
        "reauthored_tests": [],
    },
]

ATTEMPTS_FAIL = [
    {
        "number": 1, "outcome": "model_call_error", "retry_feedback": [],
        "error_category": "network", "surface_ok": None, "overall": None,
        "failed_requirements": [], "transcript_sha256": None,
        "reauthored_tests": [],
    },
]

LOOP_PASS = {
    "passed": True,
    "stop_reason": "passed",
    "attempts": ATTEMPTS_PASS,
    "generation_result": GEN_PASS,
    "verification_report": VER,
    "surface_report": {"ok": True, "findings": []},
}

LOOP_FAIL = {
    "passed": False,
    "stop_reason": "not_retried",
    "attempts": ATTEMPTS_FAIL,
    "generation_result": GEN_FAIL,
    "verification_report": None,
    "surface_report": None,
}


COMMON = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, **kw):\n"
    "    rec = {'call': name}\n"
    "    rec.update(kw)\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(rec, default=repr) + '\\n')\n"
    "\n"
)


def _write(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(COMMON + source, encoding="utf-8")


def _build_fakes(repo_root, loop_result):
    _write(repo_root, "provenance-checker", (
        "class ProvenanceKey:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:abc'\n"
        "        self.gate_versions = " + repr({"verifier": "v@1"}) + "\n"
        "        self.assets = " + repr([VER["assets"][0]]) + "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id)\n"
        "    return ProvenanceKey()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    _write(repo_root, "spec-bundle-assembler", (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc', 'spec': 's',\n"
        "            'interface': 'i', 'constraints': '', 'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
        "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
        "            'dependency_interfaces': {}, 'testing': ''}\n"
    ))

    _write(repo_root, "generation-loop", (
        "LOOP_RESULT = " + repr(loop_result) + "\n"
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
        "                 on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id)\n"
        "    result = LOOP_RESULT\n"
        "    for entry in result['attempts']:\n"
        "        if on_attempt is not None:\n"
        "            on_attempt(entry, result['generation_result'], result['verification_report'])\n"
        "    return result\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))

    _write(repo_root, "provenance-tracker", (
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id, spec_bundle_hash=spec_bundle_hash)\n"
        "    d = os.path.join(str(repo_root), '.hotdocs', 'attempts', component_id)\n"
        "    os.makedirs(d, exist_ok=True)\n"
        "    n = len(os.listdir(d))\n"
        "    attempt_id = '2026-10-25T14:32:0' + str(n) + 'Z-fake' + str(n)\n"
        "    record = {'attempt_id': attempt_id, 'component_id': component_id,\n"
        "              'timestamp': '2026-10-25T14:32:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "              'generation': json.loads(json.dumps(generation_result, default=repr)),\n"
        "              'verification': json.loads(json.dumps(verification_report, default=repr))}\n"
        "    with open(os.path.join(d, attempt_id + '.json'), 'w', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record))\n"
        "    return record\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {}, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    ))

    _write(repo_root, "verifier-orchestrator", (
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "VER = " + repr(VER) + "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return VER\n"
    ))

    _write(repo_root, "license-scanner", (
        "LIC = " + repr(LIC) + "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return LIC\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return LIC['gate_version']\n"
    ))

    _write(repo_root, "secret-scanner", (
        "SEC = " + repr(SEC) + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return SEC\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return dict(SEC, scope='precommit')\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return SEC['gate_version']\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    ))

    _write(repo_root, "provenance-writer", (
        "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id, inputs=inputs, repo_root=str(repo_root))\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id, inputs=inputs)\n"
        "    return None\n"
    ))


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run(tmp_path, monkeypatch, loop_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    _build_fakes(repo_root, loop_result)
    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m-test")
    return repo_root, _read_log(log_path), result


def test_write_provenance_called_once_after_scans_with_inputs(tmp_path, monkeypatch):
    repo_root, calls, result = _run(tmp_path, monkeypatch, LOOP_PASS)
    names = [c["call"] for c in calls]

    attempts_dir = repo_root / ".hotdocs" / "attempts" / COMPONENT_ID
    assert len(list(attempts_dir.iterdir())) == 2
    assert names.count("write_attempt_record") == 2

    assert names.count("write_provenance") == 1, names
    wp_idx = names.index("write_provenance")
    assert "license_scan" in names and "secret_scan" in names
    assert wp_idx > names.index("license_scan")
    assert wp_idx > names.index("secret_scan")
    assert all(i < wp_idx for i, n in enumerate(names) if n == "write_attempt_record")

    wp = calls[wp_idx]
    assert wp["component_id"] == COMPONENT_ID
    inputs = wp["inputs"]
    assert field(inputs, "gate_versions") == {"verifier": "v@1"}
    assert field(inputs, "provenance_hit") is False
    assert field(inputs, "attempts") == 2
    assert field(inputs, "attempt_history") == ATTEMPTS_PASS
    assert field(inputs, "generation_result") == GEN_PASS
    assert field(inputs, "verification_report") == VER
    assert field(inputs, "license_scan_result") == LIC
    assert field(inputs, "secret_scan_result") == SEC
    assert field(inputs, "component_id") == COMPONENT_ID


def test_write_provenance_not_called_when_last_generation_has_no_files(tmp_path, monkeypatch):
    repo_root, calls, result = _run(tmp_path, monkeypatch, LOOP_FAIL)
    names = [c["call"] for c in calls]

    assert "run_attempts" in names
    assert "write_provenance" not in names, names