# hotdocs-criterion: sha256:5ee245d5afda5d79681d64c8892ecc1638af66656c56ef8b35946001a4831990
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_file(path, src):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src, encoding="utf-8")


COMMON_HELPERS = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "def _f(value, name):\n"
    "    if isinstance(value, dict):\n"
    "        return value.get(name)\n"
    "    return getattr(value, name, None)\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
)


def _gate_versions_src():
    return repr({
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        "secret_scanner": "secret_scanner@0.0.0",
        "generator": "generator@3.0.0+v11",
    })


def write_provenance_checker(repo_root, log_path):
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        + COMMON_HELPERS
        + "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr("sha256:k") + "\n"
        "        self.gate_versions = " + _gate_versions_src() + "\n"
        "        self.assets = [" + repr({
            "kind": "python", "path": ".",
            "definition_sha256": None, "adapter_sha256": "sha256:aa",
            "versions": {"python": "3.12.4"}, "lockfile_sha256": None,
        }) + "]\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log(['current_sealed_key', component_id])\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log(['current_provenance_key', component_id])\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log(['check_provenance', component_id, spec_bundle_hash])\n"
        "    return " + repr({
            "hit": False, "reason": "no manifest", "verification_report": None,
            "license_scan": None, "secret_scan": None,
        }) + "\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    return " + repr({
            "hit": False, "sealed": False, "reason": "not_sealed",
            "verification_report": None, "license_scan": None, "secret_scan": None,
            "owners": None, "source_hash": None, "written_at": None,
        }) + "\n"
    )
    write_file(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", src)


def write_spec_bundle_assembler(repo_root, log_path):
    bundle = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "spec": "spec",
        "interface": "interface",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        + COMMON_HELPERS
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log(['assemble', component_id, mode])\n"
        "    return dict(" + repr(bundle) + ")\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return " + repr({
            "component_id": "comp-foo", "criterion_id": "AC-FOO-001",
            "covers": "R-FOO-001", "criterion_text": "", "requirement_text": "",
            "interface": "", "glossary": "", "dependency_interfaces": {},
            "testing": "",
        }) + "\n"
    )
    write_file(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", src)


def _generation_result(tag, files, model_call_error):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "model": "claude-sonnet-5",
        "prompt_version": tag,
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


def _verification_report(criterion_id, overall):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": criterion_id, "covers": "R-FOO-001", "kind": "compiled",
             "result": "pass" if overall == "pass" else "fail"},
        ],
        "requirement_results": {"R-FOO-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:aa", "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "overall": overall,
    }


def _attempt(number, outcome, error_category, surface_ok, overall):
    return {
        "number": number, "outcome": outcome, "retry_feedback": [],
        "error_category": error_category, "surface_ok": surface_ok,
        "overall": overall, "failed_requirements": [],
        "transcript_sha256": None, "reauthored_tests": [],
    }


def write_generation_loop(repo_root, log_path, calls):
    # calls: list of (attempt, generation_result, verification_report)
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        + COMMON_HELPERS
        + "CALLS = " + repr(calls) + "\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log(['make_closures'])\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': ''}\n"
        "    return (test_author, judge)\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log(['run_attempts', component_id])\n"
        "    attempts = []\n"
        "    last_g = None\n"
        "    last_r = None\n"
        "    for attempt, g, r in CALLS:\n"
        "        attempts.append(attempt)\n"
        "        last_g = g\n"
        "        last_r = r\n"
        "        if on_attempt is not None:\n"
        "            on_attempt(attempt, g, r)\n"
        "    return {\n"
        "        'passed': True,\n"
        "        'stop_reason': 'passed',\n"
        "        'attempts': attempts,\n"
        "        'generation_result': last_g,\n"
        "        'verification_report': last_r,\n"
        "        'surface_report': {'ok': True, 'findings': []},\n"
        "    }\n"
    )
    write_file(repo_root / "gen" / "generation-loop" / "generation_loop.py", src)


def write_provenance_tracker(repo_root, log_path, raise_error):
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        "RAISE = " + repr(raise_error) + "\n"
        + COMMON_HELPERS
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    g = _f(generation_result, 'prompt_version')\n"
        "    if verification_report is None:\n"
        "        r = None\n"
        "    else:\n"
        "        r = _f(_f(verification_report, 'criteria')[0], 'id')\n"
        "    _log(['write_attempt_record', component_id, g, r, spec_bundle_hash])\n"
        "    if RAISE:\n"
        "        raise RuntimeError('write_attempt_record failed')\n"
        "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
        "    d.mkdir(parents=True, exist_ok=True)\n"
        "    n = len(list(d.iterdir()))\n"
        "    attempt_id = '2026-10-25T14:32:0' + str(n) + 'Z-a1b2c' + str(n)\n"
        "    record = {\n"
        "        'attempt_id': attempt_id,\n"
        "        'component_id': component_id,\n"
        "        'timestamp': '2026-10-25T14:32:01Z',\n"
        "        'spec_bundle_hash': spec_bundle_hash,\n"
        "        'generation': {'prompt_version': g},\n"
        "        'verification': None if r is None else {'criterion': r},\n"
        "    }\n"
        "    (d / (attempt_id + '.json')).write_text(json.dumps(record), encoding='utf-8')\n"
        "    return record\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    write_file(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", src)


def write_scanners(repo_root, log_path):
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
    lsrc = (
        "LOG = " + repr(str(log_path)) + "\n"
        + COMMON_HELPERS
        + "def scan(component_id, repo_root):\n"
        "    _log(['license_scan', component_id])\n"
        "    return dict(" + repr(license_result) + ")\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(license_result["gate_version"]) + "\n"
    )
    write_file(repo_root / "gen" / "license-scanner" / "license_scanner.py", lsrc)
    ssrc = (
        "LOG = " + repr(str(log_path)) + "\n"
        + COMMON_HELPERS
        + "def scan(repo_root):\n"
        "    _log(['secret_scan'])\n"
        "    return dict(" + repr(secret_result) + ")\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    return dict(" + repr(secret_result) + ")\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(secret_result["gate_version"]) + "\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )
    write_file(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", ssrc)


def write_provenance_writer(repo_root, log_path):
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        + COMMON_HELPERS
        + "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log(['write_provenance', component_id])\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log(['write_sealed_provenance', component_id])\n"
        "    return None\n"
    )
    write_file(repo_root / "gen" / "provenance-writer" / "provenance_writer.py", src)


def build_repo(tmp_path, calls, raise_error):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    write_provenance_checker(repo_root, log_path)
    write_spec_bundle_assembler(repo_root, log_path)
    write_generation_loop(repo_root, log_path, calls)
    write_provenance_tracker(repo_root, log_path, raise_error)
    write_scanners(repo_root, log_path)
    write_provenance_writer(repo_root, log_path)
    return repo_root, log_path


def read_log(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_write_attempt_record_called_once_per_attempt_with_key_hash(tmp_path):
    g1 = _generation_result("g1", {}, {"category": "truncated_response", "message": "cut off"})
    g2 = _generation_result("g2", {"foo.py": "x = 1\n"}, None)
    r2 = _verification_report("AC-FOO-002", "pass")
    calls = [
        (_attempt(1, "generation_failed", "truncated_response", None, None), g1, None),
        (_attempt(2, "passed", None, True, "pass"), g2, r2),
    ]
    repo_root, log_path = build_repo(tmp_path, calls, raise_error=False)

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "anthropic:claude-sonnet-5"
    )

    entries = read_log(log_path)
    assert any(e[0] == "run_attempts" for e in entries)
    records = [e for e in entries if e[0] == "write_attempt_record"]
    assert len(records) == 2
    assert records[0] == ["write_attempt_record", "comp-foo", "g1", None, "sha256:k"]
    assert records[1] == ["write_attempt_record", "comp-foo", "g2", "AC-FOO-002", "sha256:k"]


def test_write_attempt_record_exception_does_not_change_result(tmp_path):
    g = _generation_result("g1", {"foo.py": "x = 1\n"}, None)
    r = _verification_report("AC-FOO-001", "pass")
    calls = [
        (_attempt(1, "passed", None, True, "pass"), g, r),
    ]
    repo_root, log_path = build_repo(tmp_path, calls, raise_error=True)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "anthropic:claude-sonnet-5"
    )

    entries = read_log(log_path)
    records = [e for e in entries if e[0] == "write_attempt_record"]
    assert len(records) == 1
    assert field(result, "blocked") is False