# hotdocs-criterion: sha256:10eab6a3d63c08d495b6f76e14034ce8ddc41d848909b9978340c37e65fea81e
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32
SPEC_BUNDLE_PARTS = {"spec": "sha256:" + "11" * 32, "dependency_code": "sha256:" + "22" * 32}
GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@4.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
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

SECRET_GATE_VERSION = "secret_scanner@3.1.0+detect-secrets.1.5.0-fake-marker"

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

HIT_SECRET = {
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

MISS_CHECK = {
    "hit": False,
    "reason": "no manifest",
    "verification_report": None,
    "license_scan": None,
    "secret_scan": None,
}

HIT_CHECK = {
    "hit": True,
    "reason": None,
    "verification_report": VERIFICATION_REPORT,
    "license_scan": LICENSE_RESULT,
    "secret_scan": HIT_SECRET,
}

GENERATION_RESULT = {
    "component_id": "comp-foo",
    "spec_bundle_hash": SPEC_BUNDLE_HASH,
    "model": "m",
    "prompt_version": "v12",
    "cache_hit": False,
    "files": {},
    "model_call_error": {"category": "truncated_response", "message": "cut off"},
    "refused": None,
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
            "error_category": "truncated_response",
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


def _header(log_path):
    return (
        "import json\n"
        "import types\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(name, payload):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': name, 'args': payload}, default=str) + '\\n')\n"
        "\n"
    )


def _write(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def _build_fakes(repo_root, log_path, check_result):
    h = _header(log_path)

    _write(
        repo_root,
        "provenance-checker",
        h
        + "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', [component_id, str(repo_root)])\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', [component_id, str(repo_root)])\n"
        "    return types.SimpleNamespace(\n"
        "        spec_bundle_hash=" + repr(SPEC_BUNDLE_HASH) + ",\n"
        "        spec_bundle_parts=" + repr(SPEC_BUNDLE_PARTS) + ",\n"
        "        gate_versions=" + repr(GATE_VERSIONS) + ",\n"
        "        assets=[],\n"
        "        drivers=[],\n"
        "    )\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance', [component_id, spec_bundle_hash, str(repo_root)])\n"
        "    return " + repr(check_result) + "\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', [component_id, str(repo_root)])\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n",
    )

    bundle = {
        "component_id": "comp-foo",
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "spec": "spec",
        "interface": "interface",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
        "spec_bundle_parts": SPEC_BUNDLE_PARTS,
    }
    _write(
        repo_root,
        "spec-bundle-assembler",
        h
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', [component_id, str(repo_root), mode])\n"
        "    return " + repr(bundle) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', [component_id, criterion_id, str(repo_root)])\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
        "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
        "            'dependency_interfaces': {}, 'testing': ''}\n",
    )

    _write(
        repo_root,
        "generation-loop",
        h
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
        "                 on_attempt=None):\n"
        "    _log('run_attempts', [component_id, str(repo_root), model])\n"
        "    return " + repr(LOOP_RESULT) + "\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', [model, seed, str(repo_root)])\n"
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
        "    _log('write_attempt_record', [component_id, spec_bundle_hash, str(repo_root)])\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness', [str(repo_root)])\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
        "            'secret_scan': None, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures', [component_id, str(repo_root)])\n"
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
        "    _log('verify', [component_id, str(repo_root)])\n"
        "    return " + repr(VERIFICATION_REPORT) + "\n",
    )

    _write(
        repo_root,
        "license-scanner",
        h
        + "def scan(component_id, repo_root):\n"
        "    _log('license_scan', [component_id, str(repo_root)])\n"
        "    return " + repr(LICENSE_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(LICENSE_RESULT["gate_version"]) + "\n",
    )

    _write(
        repo_root,
        "secret-scanner",
        h
        + "class SecretScanResult:\n"
        "    def __init__(self):\n"
        "        self.scope = 'full'\n"
        "        self.gate_version = " + repr(SECRET_GATE_VERSION) + "\n"
        "        self.flagged = False\n"
        "        self.matches = []\n"
        "        self.allowed = []\n"
        "        self.unused_allowlist_entries = []\n"
        "        self.notified = False\n"
        "        self.notification_delivery_error = None\n"
        "        self.cache_hit = False\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'scope': self.scope, 'gate_version': self.gate_version,\n"
        "                'flagged': self.flagged, 'matches': list(self.matches),\n"
        "                'allowed': list(self.allowed),\n"
        "                'unused_allowlist_entries': list(self.unused_allowlist_entries),\n"
        "                'notified': self.notified,\n"
        "                'notification_delivery_error': self.notification_delivery_error,\n"
        "                'cache_hit': self.cache_hit}\n"
        "\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan', [str(repo_root)])\n"
        "    return SecretScanResult()\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files', [str(repo_root)])\n"
        "    r = SecretScanResult()\n"
        "    r.scope = 'precommit'\n"
        "    return r\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(SECRET_GATE_VERSION) + "\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
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
        "    _log('write_provenance', [component_id, str(repo_root)])\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', [component_id, str(repo_root)])\n"
        "    return None\n",
    )


def _calls(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_miss_with_generation_failed_runs_both_scanners(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fakes(repo_root, log_path, MISS_CHECK)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log_path)
    names = [c["call"] for c in calls]
    assert "run_attempts" in names

    license_calls = [c for c in calls if c["call"] == "license_scan"]
    secret_calls = [c for c in calls if c["call"] == "secret_scan"]
    assert len(license_calls) == 1
    assert len(secret_calls) == 1
    assert license_calls[0]["args"] == ["comp-foo", str(repo_root)]
    assert secret_calls[0]["args"] == [str(repo_root)]

    license_scan = field(result, "license_scan")
    secret_scan = field(result, "secret_scan")
    assert license_scan == LICENSE_RESULT
    assert field(secret_scan, "gate_version") == SECRET_GATE_VERSION
    assert field(secret_scan, "scope") == "full"
    assert field(result, "provenance_hit") is False


def test_short_circuiting_hit_calls_neither_scanner(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fakes(repo_root, log_path, HIT_CHECK)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log_path)
    names = [c["call"] for c in calls]
    assert "check_provenance" in names
    assert "license_scan" not in names
    assert "secret_scan" not in names
    assert "secret_scan_files" not in names
    assert field(result, "provenance_hit") is True