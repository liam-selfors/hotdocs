# hotdocs-criterion: sha256:2cb4f0378d6d5e939e9886253fa53943aa971185f405500fe687779b2a926b2f
import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = (
    "import json\n"
    "import os\n"
    "import dataclasses\n"
    "import pathlib\n"
    "\n"
    "def _conv(v):\n"
    "    if v is None or isinstance(v, (bool, int, float, str)):\n"
    "        return v\n"
    "    if isinstance(v, dict):\n"
    "        return dict((str(k), _conv(x)) for k, x in v.items())\n"
    "    if isinstance(v, (list, tuple)):\n"
    "        return [_conv(x) for x in v]\n"
    "    if isinstance(v, pathlib.PurePath):\n"
    "        return str(v)\n"
    "    if hasattr(v, 'to_dict') and callable(getattr(v, 'to_dict')) and not isinstance(v, type):\n"
    "        return _conv(v.to_dict())\n"
    "    if dataclasses.is_dataclass(v) and not isinstance(v, type):\n"
    "        return dict((f.name, _conv(getattr(v, f.name))) for f in dataclasses.fields(v))\n"
    "    if callable(v):\n"
    "        return {'callable_tag': getattr(v, 'tag', None)}\n"
    "    if hasattr(v, '__dict__'):\n"
    "        return dict((k, _conv(x)) for k, x in vars(v).items() if not k.startswith('_') and not callable(x))\n"
    "    return repr(v)\n"
    "\n"
    "def _log(fn, **kw):\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as fh:\n"
    "        fh.write(json.dumps({'fn': fn, 'args': _conv(kw)}) + '\\n')\n"
    "\n"
    "def _cfg():\n"
    "    with open(os.environ['GATE_TEST_CFG']) as fh:\n"
    "        return json.load(fh)\n"
    "\n"
    "def main(argv=None):\n"
    "    return 0\n"
    "\n"
)

PROVENANCE_CHECKER = (
    "class _Key:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id, repo_root=repo_root)\n"
    "    k = _cfg()['key']\n"
    "    return _Key(k['spec_bundle_hash'], dict(k['gate_versions']), list(k['assets']))\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash,\n"
    "         gate_versions=gate_versions, repo_root=repo_root)\n"
    "    return _cfg()['check']\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER = (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, repo_root=repo_root, mode=mode)\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k', 'spec': '',\n"
    "            'interface': '', 'constraints': '', 'dependency_interfaces': {},\n"
    "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
    "            'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id, repo_root=repo_root)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
    "            'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP = (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    test_author.tag = 'test-author-closure'\n"
    "    judge.tag = 'judge-closure'\n"
    "    _log('make_closures', model=model, seed=seed, repo_root=repo_root, llm_backend=llm_backend,\n"
    "         returned=[test_author.tag, judge.tag])\n"
    "    return (test_author, judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
    "                 on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id, repo_root=repo_root, model=model,\n"
    "         mode=mode, max_attempts=max_attempts, retry_feedback=retry_feedback, seed=seed)\n"
    "    return _cfg()['loop']\n"
)

VERIFIER = (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id, repo_root=repo_root, judge=judge,\n"
    "         test_author=test_author)\n"
    "    return _cfg()['verify_report']\n"
)

LICENSE = (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id, repo_root=repo_root)\n"
    "    return _cfg()['license']\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET = (
    "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan', repo_root=repo_root)\n"
    "    return _cfg()['secret']\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files', paths=paths, repo_root=repo_root)\n"
    "    r = dict(_cfg()['secret'])\n"
    "    r['scope'] = 'precommit'\n"
    "    return r\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

WRITER = (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id, inputs=inputs, repo_root=repo_root)\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id, inputs=inputs, repo_root=repo_root)\n"
    "    return None\n"
)

TRACKER = (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id, spec_bundle_hash=spec_bundle_hash,\n"
    "         repo_root=repo_root)\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': _conv(generation_result), 'verification': _conv(verification_report)}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER,
    ("generation-loop", "generation_loop"): GENERATION_LOOP,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER,
    ("license-scanner", "license_scanner"): LICENSE,
    ("secret-scanner", "secret_scanner"): SECRET,
    ("provenance-writer", "provenance_writer"): WRITER,
    ("provenance-tracker", "provenance_tracker"): TRACKER,
}


def _report(overall, mutation_score):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
             "result": "pass" if overall == "pass" else "fail"},
        ],
        "requirement_results": {"R-FOO-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": mutation_score,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:ab", "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "overall": overall,
    }


def _license(blocked):
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
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


def _secret(flagged):
    matches = []
    if flagged:
        matches = [{"rule_id": "AWS Access Key", "risk_tier": "high",
                    "file": "gen/foo/config.py", "line": 1}]
    return {
        "scope": "full",
        "gate_version": "secret_scanner@0.0.0",
        "flagged": flagged,
        "matches": matches,
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

LOOP_RESULT = {
    "passed": True,
    "stop_reason": "passed",
    "attempts": [
        {"number": 1, "outcome": "passed", "retry_feedback": [], "error_category": None,
         "surface_ok": True, "overall": "pass", "failed_requirements": [],
         "transcript_sha256": None, "reauthored_tests": []},
    ],
    "generation_result": LOOP_GEN,
    "verification_report": _report("pass", 0.5),
    "surface_report": {"ok": True, "findings": []},
}

MANIFEST = {
    "spec_bundle_hash": "sha256:k",
    "model_pin": "m0",
    "prompt_version": "v9",
    "retry_feedback": None,
    "generation": {"mode": "agentic", "generator_version": "g@1", "transcript_sha256": None,
                   "turns": 4, "tool_calls": 7, "isolation": "seatbelt"},
    "attempts": 2,
    "attempt_history": [{"number": 1, "outcome": "passed"}],
    "pipeline_version": "v1",
    "gate_versions": {"verifier": "v@1"},
    "provenance_hit": False,
    "generated_at": "2026-01-01T00:00:00Z",
    "verification_run_id": "run-1",
    "verification_report": _report("pass", 0.7),
    "license_scan": _license(False),
    "secret_scan": _secret(False),
    "assets": [],
}


def _run(tmp_path, monkeypatch, reason, verify_overall, lic_blocked, sec_flagged):
    repo_root = tmp_path / "repo"
    for (slug, module), body in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module + ".py")).write_text(PRELUDE + body)
    foo = repo_root / "gen" / "foo"
    foo.mkdir(parents=True, exist_ok=True)
    (foo / ".provenance.json").write_text(json.dumps(MANIFEST, indent=2))

    report = _report(verify_overall, 0.92)
    lic = _license(lic_blocked)
    sec = _secret(sec_flagged)
    cfg = {
        "key": {"spec_bundle_hash": "sha256:k", "gate_versions": {"verifier": "v@1"},
                "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                            "adapter_sha256": "sha256:ab", "versions": {"python": "3.12.4"},
                            "lockfile_sha256": None}]},
        "check": {"hit": False, "reason": reason, "verification_report": None,
                  "license_scan": None, "secret_scan": None},
        "verify_report": report,
        "license": lic,
        "secret": sec,
        "loop": LOOP_RESULT,
    }
    side = tmp_path / "side"
    side.mkdir()
    cfg_path = side / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    log_path = side / "calls.log"
    log_path.write_text("")
    monkeypatch.setenv("GATE_TEST_CFG", str(cfg_path))
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    return repo_root, result, calls, report, lic, sec


def _after_check(calls):
    names = [c["fn"] for c in calls]
    assert names.count("check_provenance") == 1
    i = names.index("check_provenance")
    return calls[i + 1:]


def test_environment_differs_passing_reverification(tmp_path, monkeypatch):
    repo_root, result, calls, report, lic, sec = _run(
        tmp_path, monkeypatch, "environment differs", "pass", False, False)

    after = _after_check(calls)
    names = [c["fn"] for c in after]
    assert names == ["make_closures", "verify", "license_scan", "secret_scan",
                     "write_provenance"], names

    all_names = [c["fn"] for c in calls]
    for never in ("assemble", "run_attempts", "write_attempt_record"):
        assert never not in all_names

    mk = [c for c in calls if c["fn"] == "make_closures"]
    assert len(mk) == 1
    ta_tag, judge_tag = mk[0]["args"]["returned"]

    verifies = [c for c in calls if c["fn"] == "verify"]
    assert len(verifies) == 1
    va = verifies[0]["args"]
    assert va["component_id"] == "comp-foo"
    assert va["repo_root"] == str(repo_root)
    assert va["judge"] == {"callable_tag": judge_tag}
    assert va["test_author"] == {"callable_tag": ta_tag}

    writes = [c for c in calls if c["fn"] == "write_provenance"]
    assert len(writes) == 1
    wa = writes[0]["args"]
    assert wa["component_id"] == "comp-foo"
    assert wa["repo_root"] == str(repo_root)
    inputs = wa["inputs"]
    assert inputs["verification_report"] == report
    assert inputs["license_scan_result"] == lic
    assert inputs["secret_scan_result"] == sec
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
    assert field(result, "attempts") == []
    assert field(result, "verification") == report


@pytest.mark.parametrize(
    "verify_overall,lic_blocked,sec_flagged",
    [("fail", False, False), ("pass", True, False), ("pass", False, True)],
    ids=["verify-fail", "license-blocked", "secret-flagged"],
)
def test_environment_differs_failing_reverification_proceeds_as_miss(
        tmp_path, monkeypatch, verify_overall, lic_blocked, sec_flagged):
    repo_root, result, calls, report, lic, sec = _run(
        tmp_path, monkeypatch, "environment differs", verify_overall, lic_blocked, sec_flagged)

    after = _after_check(calls)
    names = [c["fn"] for c in after if c["fn"] != "make_closures"]
    assert names == ["verify", "license_scan", "secret_scan", "assemble", "run_attempts",
                     "license_scan", "secret_scan", "write_provenance"], names

    writes = [c for c in calls if c["fn"] == "write_provenance"]
    assert len(writes) == 1
    gen = writes[0]["args"]["inputs"]["generation_result"]
    assert gen == LOOP_GEN

    assert field(result, "reverified") is False


def test_assets_differ_does_not_reverify(tmp_path, monkeypatch):
    repo_root, result, calls, report, lic, sec = _run(
        tmp_path, monkeypatch, "assets differ", "pass", False, False)

    names = [c["fn"] for c in calls]
    assert "verify" not in names
    assert names.count("run_attempts") == 1
    assert field(result, "reverified") is False