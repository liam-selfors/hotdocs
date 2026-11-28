# hotdocs-criterion: sha256:8a8b832f11ade615908433dbf161393640d595bf6f2a07dcd490056c741dd2e6
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = (
    "import json\n"
    "import dataclasses\n"
    "\n"
    "def _cfg():\n"
    "    with open(_CFG) as f:\n"
    "        return json.load(f)\n"
    "\n"
    "def _j(v):\n"
    "    if v is None or isinstance(v, (bool, int, float, str)):\n"
    "        return v\n"
    "    if isinstance(v, dict):\n"
    "        return {str(k): _j(x) for k, x in v.items()}\n"
    "    if isinstance(v, (list, tuple)):\n"
    "        return [_j(x) for x in v]\n"
    "    if hasattr(v, '__fspath__'):\n"
    "        return str(v)\n"
    "    if callable(v) and not isinstance(v, type) and not hasattr(v, 'to_dict'):\n"
    "        return '<callable ' + str(getattr(v, 'hotdocs_tag', getattr(v, '__name__', '?'))) + '>'\n"
    "    td = getattr(v, 'to_dict', None)\n"
    "    if callable(td):\n"
    "        return _j(td())\n"
    "    if dataclasses.is_dataclass(v) and not isinstance(v, type):\n"
    "        return {f.name: _j(getattr(v, f.name)) for f in dataclasses.fields(v)}\n"
    "    if hasattr(v, '__dict__'):\n"
    "        return {k: _j(x) for k, x in vars(v).items() if not k.startswith('_') and not callable(x)}\n"
    "    return repr(v)\n"
    "\n"
    "def _log(name, **kw):\n"
    "    with open(_LOG, 'a') as f:\n"
    "        f.write(json.dumps({'call': name, 'args': _j(kw)}) + '\\n')\n"
    "\n"
)

PROVENANCE_CHECKER = (
    "class _Obj:\n"
    "    def __init__(self, d):\n"
    "        self.__dict__.update(d)\n"
    "    def __getitem__(self, k):\n"
    "        return self.__dict__[k]\n"
    "    def get(self, k, default=None):\n"
    "        return self.__dict__.get(k, default)\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id, repo_root=str(repo_root))\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id, repo_root=str(repo_root))\n"
    "    c = _cfg()\n"
    "    return _Obj({'spec_bundle_hash': 'sha256:k',\n"
    "                 'spec_bundle_parts': c['spec_bundle_parts'],\n"
    "                 'gate_versions': {'verifier': 'v@1'},\n"
    "                 'assets': [], 'drivers': []})\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
    "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash,\n"
    "         gate_versions=gate_versions, repo_root=str(repo_root), spec_bundle_parts=spec_bundle_parts)\n"
    "    c = _cfg()\n"
    "    return {'hit': False, 'reason': c['reason'], 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER = (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, repo_root=str(repo_root), mode=mode)\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k', 'spec': 's',\n"
    "            'interface': 'i', 'constraints': '', 'dependency_interfaces': {},\n"
    "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
    "            'hint_code': None, 'spec_bundle_parts': {'spec': 'sha256:a', 'dependency_code': 'sha256:b'}}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
    "            'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP = (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
    "                 on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id, repo_root=str(repo_root), model=model,\n"
    "         mode=mode, max_attempts=max_attempts)\n"
    "    return _cfg()['loop_result']\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model, seed=seed, repo_root=str(repo_root))\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    judge.hotdocs_tag = 'JUDGE-TAG'\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    test_author.hotdocs_tag = 'TA-TAG'\n"
    "    return (test_author, judge)\n"
)

PROVENANCE_TRACKER = (
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id)\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': _j(generation_result), 'verification': _j(verification_report)}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness')\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'secret_scan': None, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures')\n"
    "    return []\n"
)

VERIFIER_ORCHESTRATOR = (
    "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id, repo_root=str(repo_root),\n"
    "         judge=getattr(judge, 'hotdocs_tag', None), test_author=getattr(test_author, 'hotdocs_tag', None))\n"
    "    return _cfg()['report']\n"
)

LICENSE_SCANNER = (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id, repo_root=str(repo_root))\n"
    "    return _cfg()['license']\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET_SCANNER = (
    "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan', repo_root=str(repo_root))\n"
    "    return _cfg()['secret']\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files')\n"
    "    r = dict(_cfg()['secret'])\n"
    "    r['scope'] = 'precommit'\n"
    "    return r\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

PROVENANCE_WRITER = (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id, inputs=inputs, repo_root=str(repo_root))\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id, inputs=inputs)\n"
    "    return None\n"
)

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER,
    ("generation-loop", "generation_loop"): GENERATION_LOOP,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_ORCHESTRATOR,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER,
}


def make_report(overall):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
             "result": "pass" if overall == "pass" else "fail"},
        ],
        "requirement_results": {"R-FOO-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def make_license(blocked):
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9 if blocked else 0.1,
        "block_threshold": 0.7,
        "blocked": blocked,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def make_secret(flagged):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": flagged,
        "matches": ([{"rule_id": "AWS Access Key", "risk_tier": "high",
                      "file": "gen/foo/config.py", "line": 1}] if flagged else []),
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


LOOP_GEN = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:k",
    "model": "m",
    "prompt_version": "v12",
    "cache_hit": False,
    "files": {"foo.py": "print(1)\n"},
    "model_call_error": None,
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

LOOP_REPORT = make_report("pass")

LOOP_RESULT = {
    "passed": True,
    "stop_reason": "passed",
    "attempts": [
        {"number": 1, "outcome": "passed", "retry_feedback": [], "error_category": None,
         "surface_ok": True, "overall": "pass", "failed_requirements": [],
         "transcript_sha256": None, "reauthored_tests": []},
    ],
    "generation_result": LOOP_GEN,
    "verification_report": LOOP_REPORT,
    "surface_report": {"ok": True, "findings": []},
}

MANIFEST = {
    "model_pin": "m0",
    "prompt_version": "v9",
    "retry_feedback": None,
    "attempts": 2,
    "attempt_history": [{"number": 1, "outcome": "passed"}],
    "generation": {"mode": "agentic", "generator_version": "g@1", "transcript_sha256": None,
                   "turns": 4, "tool_calls": 7, "isolation": "seatbelt"},
}


def setup_repo(tmp_path, reason="environment differs", verify_overall="pass",
               license_blocked=False, secret_flagged=False,
               spec_bundle_parts=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    cfg = tmp_path / "config.json"
    if spec_bundle_parts is None:
        spec_bundle_parts = {"spec": "sha256:a", "dependency_code": "sha256:b"}
    config = {
        "reason": reason,
        "spec_bundle_parts": spec_bundle_parts,
        "report": make_report(verify_overall),
        "license": make_license(license_blocked),
        "secret": make_secret(secret_flagged),
        "loop_result": LOOP_RESULT,
    }
    cfg.write_text(json.dumps(config))
    header = "_LOG = " + repr(str(log)) + "\n" + "_CFG = " + repr(str(cfg)) + "\n"
    for (slug, module), body in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module + ".py")).write_text(header + COMMON + body)
    manifest_dir = repo_root / "gen" / "foo"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / ".provenance.json").write_text(json.dumps(MANIFEST))
    return repo_root, log, config


def read_calls(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def named(calls, name):
    return [c for c in calls if c["call"] == name]


def test_passing_reverification_writes_provenance_from_manifest(tmp_path):
    repo_root, log, config = setup_repo(tmp_path)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = read_calls(log)

    verifies = named(calls, "verify")
    assert len(verifies) == 1
    va = verifies[0]["args"]
    assert va["component_id"] == "comp-foo"
    assert va["repo_root"] == str(repo_root)
    assert va["judge"] == "JUDGE-TAG"
    assert va["test_author"] == "TA-TAG"

    assert named(calls, "assemble") == []
    assert named(calls, "run_attempts") == []
    assert named(calls, "write_attempt_record") == []

    writes = named(calls, "write_provenance")
    assert len(writes) == 1
    names = [c["call"] for c in calls]
    w_idx = names.index("write_provenance")
    assert "license_scan" in names[:w_idx]
    assert "secret_scan" in names[:w_idx]

    inputs = writes[0]["args"]["inputs"]
    assert inputs["verification_report"] == config["report"]
    assert inputs["license_scan_result"] == config["license"]
    assert inputs["secret_scan_result"] == config["secret"]
    assert inputs["attempts"] == 2
    assert inputs["attempt_history"] == [{"number": 1, "outcome": "passed"}]
    assert inputs["provenance_hit"] is False
    assert inputs["gate_versions"] == {"verifier": "v@1"}
    gen = inputs["generation_result"]
    assert gen["files"] == {}
    assert gen["spec_bundle_hash"] == "sha256:k"
    assert gen["model"] == "m0"
    assert gen["prompt_version"] == "v9"
    assert gen["mode"] == "agentic"
    assert gen["turns"] == 4
    assert gen["tool_calls"] == 7
    assert gen["isolation"] == "seatbelt"

    assert field(result, "reverified") is True
    assert field(result, "blocked") is False
    assert field(result, "provenance_hit") is False
    assert list(field(result, "attempts")) == []
    assert field(result, "verification") == config["report"]


def test_flagged_secret_scan_does_not_prevent_reverification(tmp_path):
    repo_root, log, _ = setup_repo(tmp_path, secret_flagged=True)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = read_calls(log)
    assert field(result, "reverified") is True
    assert named(calls, "run_attempts") == []


def test_failing_reverification_proceeds_as_miss(tmp_path):
    repo_root, log, _ = setup_repo(tmp_path, verify_overall="fail", license_blocked=True)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = read_calls(log)
    names = [c["call"] for c in calls]
    cp_idx = names.index("check_provenance")
    after = [n for n in names[cp_idx + 1:] if n != "make_closures"]
    assert after == [
        "verify", "license_scan", "secret_scan", "assemble", "run_attempts",
        "license_scan", "secret_scan", "write_provenance",
    ]
    writes = named(calls, "write_provenance")
    assert len(writes) == 1
    inputs = writes[0]["args"]["inputs"]
    assert inputs["generation_result"] == LOOP_GEN
    assert inputs["generation_result"]["files"] == {"foo.py": "print(1)\n"}
    assert field(result, "reverified") is False


def test_dependency_code_differs_reverifies_with_key_parts(tmp_path):
    parts = {"spec": "s", "dependency_code": "d"}
    repo_root, log, _ = setup_repo(tmp_path, reason="dependency code differs",
                                   spec_bundle_parts=parts)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = read_calls(log)
    assert field(result, "reverified") is True
    assert named(calls, "run_attempts") == []
    writes = named(calls, "write_provenance")
    assert len(writes) == 1
    assert writes[0]["args"]["inputs"]["spec_bundle_parts"] == {"spec": "s", "dependency_code": "d"}


def test_assets_differ_does_not_reverify(tmp_path):
    repo_root, log, _ = setup_repo(tmp_path, reason="assets differ")
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = read_calls(log)
    assert named(calls, "verify") == []
    assert len(named(calls, "run_attempts")) == 1
    assert field(result, "reverified") is False