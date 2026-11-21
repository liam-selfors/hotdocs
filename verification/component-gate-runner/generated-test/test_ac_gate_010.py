# hotdocs-criterion: sha256:403168a8d83d561d46647ca15937f507ad3091d7b57b0589af9d81546ca3ba0d
import json

import pytest

import component_gate_runner


LOG_ENV = "CGR_AC_GATE_010_LOG"

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
        "adapter_sha256": "sha256:ab",
        "versions": {"python": "3.12.4"},
        "lockfile_sha256": None,
    }
]

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": ASSETS,
    "overall": "pass",
}

GENERATION_RESULT = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:ab",
    "model": "m",
    "prompt_version": "v1",
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
        {
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
    ],
    "generation_result": GENERATION_RESULT,
    "verification_report": VERIFICATION_REPORT,
    "surface_report": {"ok": True, "findings": []},
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

SPEC_BUNDLE = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:ab",
    "spec": "",
    "interface": "",
    "constraints": "",
    "dependency_interfaces": {},
    "dependency_context": {},
    "dependency_usage": {},
    "vars": {},
    "glossary": "",
    "hint_code": None,
}

ATTEMPT_RECORD = {
    "attempt_id": "2026-01-01T00:00:00Z-a1b2c3",
    "component_id": "comp-foo",
    "timestamp": "2026-01-01T00:00:00Z",
    "spec_bundle_hash": "sha256:ab",
    "generation": GENERATION_RESULT,
    "verification": VERIFICATION_REPORT,
}

HEADER = (
    "import json\n"
    "import os\n"
    "\n"
    "\n"
    "def _log(fn, **kw):\n"
    "    rec = dict(kw)\n"
    "    rec['fn'] = fn\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as f:\n"
    "        f.write(json.dumps(rec, default=str) + '\\n')\n"
    "\n"
    "\n"
)


def _provenance_checker_src():
    return (
        HEADER
        + "class _Key:\n"
        + "    def __init__(self):\n"
        + "        self.spec_bundle_hash = 'sha256:ab'\n"
        + "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        + "        self.assets = " + repr(ASSETS) + "\n"
        + "\n\n"
        + "def current_sealed_key(component_id, repo_root):\n"
        + "    _log('current_sealed_key', component_id=component_id)\n"
        + "    return None\n"
        + "\n\n"
        + "def current_provenance_key(component_id, repo_root):\n"
        + "    _log('current_provenance_key', component_id=component_id)\n"
        + "    return _Key()\n"
        + "\n\n"
        + "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        + "    _log('check_provenance', component_id=component_id)\n"
        + "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        + "            'license_scan': None, 'secret_scan': None}\n"
        + "\n\n"
        + "def check_sealed_provenance(component_id, repo_root):\n"
        + "    _log('check_sealed_provenance', component_id=component_id)\n"
        + "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        + "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        + "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    )


def _spec_bundle_assembler_src():
    return (
        HEADER
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        + "    _log('assemble', component_id=component_id, mode=mode)\n"
        + "    return dict(" + repr(SPEC_BUNDLE) + ")\n"
        + "\n\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    _log('assemble_criterion', component_id=component_id)\n"
        + "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        + "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
        + "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    )


def _generation_loop_src():
    return (
        HEADER
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        + "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        + "                      'missing_asset', 'malformed_layout')\n"
        + "\n\n"
        + "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        + "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        + "                 allow_unisolated_exec=False, on_attempt=None):\n"
        + "    _log('run_attempts', component_id=component_id, model=model, mode=mode,\n"
        + "         max_attempts=max_attempts, max_attempts_type=type(max_attempts).__name__)\n"
        + "    return " + repr(LOOP_RESULT) + "\n"
        + "\n\n"
        + "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        + "    _log('make_closures', model=model)\n"
        + "    def test_author(bundle):\n"
        + "        return {'model_call_error': None, 'file': None}\n"
        + "    def judge(bundle):\n"
        + "        return {'result': 'pass', 'rationale': None}\n"
        + "    return (test_author, judge)\n"
    )


def _provenance_tracker_src():
    return (
        HEADER
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        + "                         spec_bundle_hash, repo_root):\n"
        + "    _log('write_attempt_record', component_id=component_id)\n"
        + "    return " + repr(ATTEMPT_RECORD) + "\n"
        + "\n\n"
        + "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        + "    _log('check_readiness')\n"
        + "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        + "            'capabilities': {}, 'not_ready_reasons': []}\n"
        + "\n\n"
        + "def last_requirement_failures(component_id, repo_root):\n"
        + "    _log('last_requirement_failures', component_id=component_id)\n"
        + "    return []\n"
    )


def _verifier_orchestrator_src():
    return (
        HEADER
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        + "DEFAULT_TEST_TIMEOUT = 300.0\n"
        + "\n\n"
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        + "    _log('verify', component_id=component_id)\n"
        + "    return " + repr(VERIFICATION_REPORT) + "\n"
    )


def _license_scanner_src():
    return (
        HEADER
        + "def scan(component_id, repo_root):\n"
        + "    _log('license_scan', component_id=component_id)\n"
        + "    return " + repr(LICENSE_RESULT) + "\n"
        + "\n\n"
        + "def gate_version(repo_root):\n"
        + "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    )


def _secret_scanner_src():
    return (
        HEADER
        + "class AllowlistInvalidError(Exception):\n"
        + "    pass\n"
        + "\n\n"
        + "def scan(repo_root):\n"
        + "    _log('secret_scan')\n"
        + "    return " + repr(SECRET_RESULT) + "\n"
        + "\n\n"
        + "def scan_files(paths, repo_root=None):\n"
        + "    _log('secret_scan_files')\n"
        + "    r = " + repr(SECRET_RESULT) + "\n"
        + "    r['scope'] = 'precommit'\n"
        + "    return r\n"
        + "\n\n"
        + "def gate_version(repo_root):\n"
        + "    return 'secret_scanner@0.0.0'\n"
        + "\n\n"
        + "def propose(repo_root):\n"
        + "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )


def _provenance_writer_src():
    return (
        HEADER
        + "class InvalidSealedInputError(Exception):\n"
        + "    pass\n"
        + "\n\n"
        + "class MissingInputError(Exception):\n"
        + "    pass\n"
        + "\n\n"
        + "def write_provenance(component_id, inputs, repo_root):\n"
        + "    _log('write_provenance', component_id=component_id)\n"
        + "    return None\n"
        + "\n\n"
        + "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        + "    _log('write_sealed_provenance', component_id=component_id)\n"
        + "    return None\n"
    )


FAKES = {
    "provenance-checker": _provenance_checker_src,
    "spec-bundle-assembler": _spec_bundle_assembler_src,
    "generation-loop": _generation_loop_src,
    "provenance-tracker": _provenance_tracker_src,
    "verifier-orchestrator": _verifier_orchestrator_src,
    "license-scanner": _license_scanner_src,
    "secret-scanner": _secret_scanner_src,
    "provenance-writer": _provenance_writer_src,
}

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A fixture component.\n"
)

VALID_TOML = "[generate]\nmax_attempts = 5\nmode = \"agentic\"\n"
TURBO_TOML = "[generate]\nmode = \"turbo\"\n"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD)
    for slug, src in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(src())
    log_path = tmp_path / "calls.log"
    log_path.write_text("")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    return repo_root, log_path


def _calls(log_path, fn):
    out = []
    for line in log_path.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("fn") == fn:
                out.append(rec)
    return out


def test_file_values_reach_run_attempts(repo):
    repo_root, log_path = repo
    (repo_root / "hotdocs.toml").write_text(VALID_TOML)

    component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)]
    )

    calls = _calls(log_path, "run_attempts")
    assert len(calls) == 1
    assert calls[0]["max_attempts"] == 5
    assert calls[0]["max_attempts_type"] == "int"
    assert calls[0]["mode"] == "agentic"


def test_flags_override_file_values(repo):
    repo_root, log_path = repo
    (repo_root / "hotdocs.toml").write_text(VALID_TOML)

    component_gate_runner.main(
        [
            "generate",
            "comp-foo",
            "--model=m",
            "--repo-root=" + str(repo_root),
            "--max-attempts=1",
            "--mode=single",
        ]
    )

    calls = _calls(log_path, "run_attempts")
    assert len(calls) == 1
    assert calls[0]["max_attempts"] == 1
    assert calls[0]["max_attempts_type"] == "int"
    assert calls[0]["mode"] == "single"


@pytest.mark.parametrize(
    "toml_text, extra",
    [
        (TURBO_TOML, []),
        (None, ["--max-attempts=0"]),
        (None, ["--mode=turbo"]),
    ],
    ids=["file-mode-turbo", "flag-max-attempts-0", "flag-mode-turbo"],
)
def test_invalid_values_are_usage_errors(repo, capsys, toml_text, extra):
    repo_root, log_path = repo
    if toml_text is not None:
        (repo_root / "hotdocs.toml").write_text(toml_text)

    rc = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)] + extra
    )

    err = capsys.readouterr().err
    assert rc == 2
    lines = err.splitlines()
    assert lines, "expected a usage error on stderr"
    assert lines[0].startswith("usage error: ")
    assert _calls(log_path, "run_attempts") == []