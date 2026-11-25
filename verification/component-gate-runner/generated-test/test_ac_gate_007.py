# hotdocs-criterion: sha256:a8ef5e3f2e3f5036b1586fd7621ea6a235f13829aadd82dd802aeee306b527e3
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_FAKE_CALL_LOG"

OWNERS = ["pipeline-team"]
SOURCE_PATH = "pipeline/foo/"
SOURCE_HASH = "sha256:k"
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"

BUNDLE_HASH = "sha256:" + "a" * 64
GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}
ASSETS = [
    {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": "sha256:" + "b" * 64,
        "versions": {"python": "3.12.4"},
        "lockfile_sha256": None,
    }
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _report(overall):
    if overall == "pass":
        criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "pass"},
        ]
        results = {"R-FOO-001": "pass", "R-FOO-002": "pass"}
    else:
        criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "generated-test",
                "result": "fail",
                "failure_detail": {"message": "result.foo equals 5 failed", "expected": 5, "actual": 3},
                "failure_origin": "implementation",
            },
        ]
        results = {"R-FOO-001": "pass", "R-FOO-002": "fail"}
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": results,
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": ASSETS,
        "overall": overall,
    }


PREAMBLE = [
    "import copy",
    "import json",
    "import os",
    "",
    "def _log(name, payload):",
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:",
    "        fh.write(json.dumps({'name': name, 'payload': payload}, default=repr) + chr(10))",
    "",
    "class _Obj:",
    "    def __init__(self, data):",
    "        self._data = copy.deepcopy(data)",
    "        for k, v in self._data.items():",
    "            setattr(self, k, v)",
    "    def to_dict(self):",
    "        return copy.deepcopy(self._data)",
    "",
]


def _write(repo_root, slug, lines):
    module = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text("\n".join(PREAMBLE + lines) + "\n", encoding="utf-8")


def _install_fakes(repo_root, sealed, report):
    license_result = {
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
    secret_result = {
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
    gen_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": BUNDLE_HASH,
        "model": "m",
        "prompt_version": "v11",
        "cache_hit": False,
        "files": {"foo.py": "x = 1"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    attempt = {
        "number": 1,
        "outcome": "passed",
        "retry_feedback": [],
        "error_category": None,
        "surface_ok": True,
        "overall": "pass",
        "failed_requirements": [],
        "transcript_sha256": None,
        "reauthored_tests": [],
    }

    _write(repo_root, "provenance-checker", [
        "SEALED = " + repr(sealed),
        "class SealedKey:",
        "    def __init__(self, owners, source_path, source_hash, verifier_version):",
        "        self.owners = owners",
        "        self.source_path = source_path",
        "        self.source_hash = source_hash",
        "        self.verifier_version = verifier_version",
        "class ProvenanceKey:",
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):",
        "        self.spec_bundle_hash = spec_bundle_hash",
        "        self.gate_versions = gate_versions",
        "        self.assets = assets",
        "def current_sealed_key(component_id, repo_root):",
        "    _log('current_sealed_key', {'component_id': component_id})",
        "    if not SEALED:",
        "        return None",
        "    return SealedKey(" + repr(OWNERS) + ", " + repr(SOURCE_PATH) + ", "
        + repr(SOURCE_HASH) + ", " + repr(VERIFIER_VERSION) + ")",
        "def current_provenance_key(component_id, repo_root):",
        "    _log('current_provenance_key', {'component_id': component_id})",
        "    return ProvenanceKey(" + repr(BUNDLE_HASH) + ", dict(" + repr(GATE_VERSIONS) + "), "
        + repr(ASSETS) + ")",
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):",
        "    _log('check_provenance', {'component_id': component_id, 'spec_bundle_hash': spec_bundle_hash})",
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,",
        "            'license_scan': None, 'secret_scan': None}",
        "def check_sealed_provenance(component_id, repo_root):",
        "    _log('check_sealed_provenance', {'component_id': component_id})",
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,",
        "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,",
        "            'written_at': None}",
    ])

    _write(repo_root, "spec-bundle-assembler", [
        "class SpecBundle:",
        "    def __init__(self, component_id):",
        "        self._fields = {'component_id': component_id, 'spec_bundle_hash': " + repr(BUNDLE_HASH) + ",",
        "            'spec': 'spec', 'interface': 'interface', 'constraints': '',",
        "            'dependency_interfaces': {}, 'dependency_context': {}, 'dependency_usage': {},",
        "            'vars': {}, 'glossary': '', 'hint_code': None}",
        "        for k, v in self._fields.items():",
        "            setattr(self, k, v)",
        "    def __getitem__(self, key):",
        "        return self._fields[key]",
        "    def get(self, key, default=None):",
        "        return self._fields.get(key, default)",
        "    def keys(self):",
        "        return self._fields.keys()",
        "def assemble(component_id, repo_root, mode='cold'):",
        "    _log('assemble', {'component_id': component_id, 'mode': mode})",
        "    return SpecBundle(component_id)",
        "def assemble_criterion(component_id, criterion_id, repo_root):",
        "    _log('assemble_criterion', {'component_id': component_id})",
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',",
        "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',",
        "            'dependency_interfaces': {}, 'testing': ''}",
    ])

    _write(repo_root, "verifier-orchestrator", [
        "GATE_VERSION = 'verifier-orchestrator@2.0.0'",
        "DEFAULT_TEST_TIMEOUT = 300.0",
        "_REPORT = " + repr(report),
        "def verify(component_id, repo_root, judge=None, test_author=None):",
        "    _log('verify', {'component_id': component_id, 'judge_callable': callable(judge),",
        "                    'test_author_callable': callable(test_author)})",
        "    return _Obj(_REPORT)",
        "def main(argv=None):",
        "    return 0",
    ])

    _write(repo_root, "generation-loop", [
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',",
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',",
        "                      'missing_asset', 'malformed_layout')",
        "_GEN = " + repr(gen_result),
        "_REPORT = " + repr(_report("pass")),
        "_ATTEMPT = " + repr(attempt),
        "class AttemptLoopResult:",
        "    def __init__(self, passed, stop_reason, attempts, generation_result, verification_report, surface_report):",
        "        self.passed = passed",
        "        self.stop_reason = stop_reason",
        "        self.attempts = attempts",
        "        self.generation_result = generation_result",
        "        self.verification_report = verification_report",
        "        self.surface_report = surface_report",
        "    def to_dict(self):",
        "        def plain(v):",
        "            return v.to_dict() if hasattr(v, 'to_dict') else v",
        "        return {'passed': self.passed, 'stop_reason': self.stop_reason,",
        "                'attempts': self.attempts, 'generation_result': plain(self.generation_result),",
        "                'verification_report': plain(self.verification_report),",
        "                'surface_report': plain(self.surface_report)}",
        "def make_closures(model, seed, repo_root, llm_backend=None):",
        "    _log('make_closures', {'model': model, 'seed': seed})",
        "    def test_author(bundle):",
        "        return {'model_call_error': None, 'file': None}",
        "    def judge(bundle):",
        "        return {'result': 'pass', 'rationale': None}",
        "    return (test_author, judge)",
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,",
        "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,",
        "                 on_attempt=None):",
        "    _log('run_attempts', {'component_id': component_id, 'model': model})",
        "    gen = _Obj(_GEN)",
        "    rep = _Obj(_REPORT)",
        "    surface = _Obj({'ok': True, 'findings': []})",
        "    att = dict(_ATTEMPT)",
        "    if on_attempt is not None:",
        "        on_attempt(att, gen, rep)",
        "    return AttemptLoopResult(True, 'passed', [att], gen, rep, surface)",
    ])

    _write(repo_root, "provenance-tracker", [
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):",
        "    _log('write_attempt_record', {'component_id': component_id, 'spec_bundle_hash': spec_bundle_hash})",
        "    gen = generation_result.to_dict() if hasattr(generation_result, 'to_dict') else generation_result",
        "    ver = verification_report.to_dict() if hasattr(verification_report, 'to_dict') else verification_report",
        "    return {'attempt_id': '2026-11-25T00:00:00Z-aaaaaa', 'component_id': component_id,",
        "            'timestamp': '2026-11-25T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,",
        "            'generation': gen, 'verification': ver}",
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):",
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},",
        "            'secret_scan': None, 'not_ready_reasons': []}",
        "def last_requirement_failures(component_id, repo_root):",
        "    return []",
    ])

    _write(repo_root, "license-scanner", [
        "_RESULT = " + repr(license_result),
        "def scan(component_id, repo_root):",
        "    _log('license_scan', {'component_id': component_id})",
        "    return dict(_RESULT)",
        "def gate_version(repo_root):",
        "    return _RESULT['gate_version']",
    ])

    _write(repo_root, "secret-scanner", [
        "_RESULT = " + repr(secret_result),
        "class AllowlistInvalidError(Exception):",
        "    pass",
        "def scan(repo_root):",
        "    _log('secret_scan', {})",
        "    return _Obj(_RESULT)",
        "def scan_files(paths, repo_root=None):",
        "    d = dict(_RESULT)",
        "    d['scope'] = 'precommit'",
        "    return _Obj(d)",
        "def gate_version(repo_root):",
        "    return _RESULT['gate_version']",
        "def propose(repo_root):",
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}",
    ])

    _write(repo_root, "provenance-writer", [
        "class InvalidSealedInputError(Exception):",
        "    pass",
        "class MissingInputError(Exception):",
        "    pass",
        "def _plain(v):",
        "    if hasattr(v, 'to_dict') and callable(v.to_dict):",
        "        return v.to_dict()",
        "    return v",
        "def _get(v, name):",
        "    return v[name] if isinstance(v, dict) else getattr(v, name)",
        "def write_provenance(component_id, inputs, repo_root):",
        "    _log('write_provenance', {'component_id': component_id})",
        "def write_sealed_provenance(component_id, inputs, repo_root):",
        "    payload = {'component_id_arg': component_id}",
        "    for k in ('component_id', 'owners', 'source_path', 'source_hash', 'verifier_version', 'verification_report'):",
        "        payload[k] = _plain(_get(inputs, k))",
        "    payload['input_keys'] = sorted(inputs.keys()) if isinstance(inputs, dict) else None",
        "    _log('write_sealed_provenance', payload)",
    ])


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _names(entries):
    return [e["name"] for e in entries]


def _setup(tmp_path, monkeypatch, sealed, report):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    _install_fakes(repo_root, sealed, report)
    return repo_root, log_path


SEALED_FORBIDDEN = [
    "check_provenance",
    "current_provenance_key",
    "assemble",
    "run_attempts",
    "write_attempt_record",
    "write_provenance",
]


def _assert_sealed_write(entries, expected_report):
    names = _names(entries)
    assert names.count("write_sealed_provenance") == 1
    w_idx = names.index("write_sealed_provenance")
    for n in ("verify", "license_scan", "secret_scan"):
        assert names.count(n) == 1, n
        assert names.index(n) < w_idx, n
    payload = entries[w_idx]["payload"]
    assert payload["component_id_arg"] == "comp-foo"
    assert payload["component_id"] == "comp-foo"
    assert payload["owners"] == OWNERS
    assert payload["source_path"] == SOURCE_PATH
    assert payload["source_hash"] == SOURCE_HASH
    assert payload["verifier_version"] == VERIFIER_VERSION
    assert payload["verification_report"] == expected_report
    if payload["input_keys"] is not None:
        assert set(payload["input_keys"]) == {
            "component_id", "owners", "source_path", "source_hash",
            "verifier_version", "verification_report",
        }


def test_sealed_component_passing_verification(tmp_path, monkeypatch):
    report = _report("pass")
    repo_root, log_path = _setup(tmp_path, monkeypatch, True, report)
    assert not (repo_root / "specs" / "components" / "foo" / "component.md").exists()

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = _read_log(log_path)
    names = _names(entries)
    for n in SEALED_FORBIDDEN:
        assert n not in names, n
    _assert_sealed_write(entries, report)

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(field(result, "verification"), "overall") == "pass"


def test_sealed_component_failing_verification(tmp_path, monkeypatch):
    report = _report("fail")
    repo_root, log_path = _setup(tmp_path, monkeypatch, True, report)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = _read_log(log_path)
    names = _names(entries)
    for n in SEALED_FORBIDDEN:
        assert n not in names, n
    _assert_sealed_write(entries, report)

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"
    assert field(result, "provenance_hit") is False


def test_non_sealed_component_takes_generation_path(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, False, _report("pass"))

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = _read_log(log_path)
    names = _names(entries)
    assert "write_sealed_provenance" not in names
    assert "make_closures" not in names

    expected = [
        "current_provenance_key",
        "check_provenance",
        "assemble",
        "run_attempts",
        "write_attempt_record",
        "license_scan",
        "secret_scan",
        "write_provenance",
    ]
    for n in expected:
        assert names.count(n) == 1, n
    ordered = [n for n in names if n in expected]
    assert ordered == expected