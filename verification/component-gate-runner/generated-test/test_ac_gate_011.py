# hotdocs-criterion: sha256:86c3cc3d062de2e25363e3114fde094a47dab33ae86a545df13207bb5c97baee
import json
from pathlib import Path, PurePath
import collections.abc

import pytest

import component_gate_runner


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def plain(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, collections.abc.Mapping):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, PurePath):
        return str(v)
    if hasattr(v, "to_dict") and callable(getattr(v, "to_dict")):
        return plain(v.to_dict())
    if hasattr(v, "__dict__"):
        return {k: plain(x) for k, x in vars(v).items()
                if not k.startswith("_") and not callable(x)}
    return repr(v)


COMMON = (
    "import json\n"
    "import os\n"
    "import collections.abc\n"
    "from pathlib import PurePath\n"
    "\n"
    "\n"
    "def _plain(v):\n"
    "    if v is None or isinstance(v, (bool, int, float, str)):\n"
    "        return v\n"
    "    if isinstance(v, collections.abc.Mapping):\n"
    "        return {str(k): _plain(x) for k, x in v.items()}\n"
    "    if isinstance(v, (list, tuple)):\n"
    "        return [_plain(x) for x in v]\n"
    "    if isinstance(v, PurePath):\n"
    "        return str(v)\n"
    "    if hasattr(v, 'to_dict') and callable(getattr(v, 'to_dict')):\n"
    "        return _plain(v.to_dict())\n"
    "    if hasattr(v, '__dict__'):\n"
    "        return {k: _plain(x) for k, x in vars(v).items()\n"
    "                if not k.startswith('_') and not callable(x)}\n"
    "    return repr(v)\n"
    "\n"
    "\n"
    "def _cfg():\n"
    "    with open(os.environ['GATE_TEST_CONFIG']) as f:\n"
    "        return json.load(f)\n"
    "\n"
    "\n"
    "def _log(name, **kw):\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as f:\n"
    "        f.write(json.dumps({'call': name, 'args': _plain(kw)}) + '\\n')\n"
    "\n"
    "\n"
)

PROVENANCE_CHECKER = COMMON + (
    "class _Key(object):\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id, repo_root=repo_root)\n"
    "    return _Key('sha256:k', {'verifier': 'v@1'},\n"
    "                [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                  'adapter_sha256': 'sha256:aa', 'versions': {'python': '3.12.4'},\n"
    "                  'lockfile_sha256': None}])\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id=component_id,\n"
    "         spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions,\n"
    "         repo_root=repo_root)\n"
    "    return {'hit': False, 'reason': _cfg()['check_reason'],\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER = COMMON + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, repo_root=repo_root, mode=mode)\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k',\n"
    "            'spec': 'spec', 'interface': 'interface', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id,\n"
    "         criterion_id=criterion_id, repo_root=repo_root)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP = COMMON + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model, seed=seed, repo_root=repo_root,\n"
    "         llm_backend=llm_backend)\n"
    "\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "\n"
    "    test_author.marker = 'test_author-closure'\n"
    "    judge.marker = 'judge-closure'\n"
    "    return (test_author, judge)\n"
    "\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id, repo_root=repo_root,\n"
    "         model=model, mode=mode, max_attempts=max_attempts,\n"
    "         retry_feedback=retry_feedback, seed=seed)\n"
    "    c = _cfg()\n"
    "    return {'passed': True, 'stop_reason': 'passed',\n"
    "            'attempts': c['loop_attempts'],\n"
    "            'generation_result': c['loop_generation_result'],\n"
    "            'verification_report': c['loop_verification_report'],\n"
    "            'surface_report': {'ok': True, 'findings': []}}\n"
)

PROVENANCE_TRACKER = COMMON + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id,\n"
    "         spec_bundle_hash=spec_bundle_hash, repo_root=repo_root)\n"
    "    return {'attempt_id': '2026-10-25T14:32:01Z-a1b2c3', 'component_id': component_id,\n"
    "            'timestamp': '2026-10-25T14:32:01Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': _plain(generation_result),\n"
    "            'verification': _plain(verification_report)}\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness', repo_root=repo_root)\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures', component_id=component_id, repo_root=repo_root)\n"
    "    return []\n"
)

VERIFIER_ORCHESTRATOR = COMMON + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id, repo_root=repo_root,\n"
    "         judge=getattr(judge, 'marker', None),\n"
    "         test_author=getattr(test_author, 'marker', None))\n"
    "    return _cfg()['verify_report']\n"
)

LICENSE_SCANNER = COMMON + (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scanner.scan', component_id=component_id, repo_root=repo_root)\n"
    "    return _cfg()['license_scan']\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET_SCANNER = COMMON + (
    "def scan(repo_root):\n"
    "    _log('secret_scanner.scan', repo_root=repo_root)\n"
    "    return _cfg()['secret_scan']\n"
    "\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scanner.scan_files', repo_root=repo_root)\n"
    "    r = dict(_cfg()['secret_scan'])\n"
    "    r['scope'] = 'precommit'\n"
    "    return r\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "\n"
    "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

PROVENANCE_WRITER = COMMON + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "class SealedProvenanceInputs(object):\n"
    "    def __init__(self, component_id, owners, source_path, source_hash,\n"
    "                 verifier_version, verification_report):\n"
    "        self.component_id = component_id\n"
    "        self.owners = owners\n"
    "        self.source_path = source_path\n"
    "        self.source_hash = source_hash\n"
    "        self.verifier_version = verifier_version\n"
    "        self.verification_report = verification_report\n"
    "\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id, inputs=inputs,\n"
    "         repo_root=repo_root)\n"
    "    return None\n"
    "\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id, inputs=inputs,\n"
    "         repo_root=repo_root)\n"
    "    return None\n"
)

STAND_INS = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER,
    ("generation-loop", "generation_loop"): GENERATION_LOOP,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_ORCHESTRATOR,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER,
}


def verification_report(overall):
    if overall == "pass":
        crit = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
                "result": "pass"}
        rr = {"R-FOO-001": "pass"}
    else:
        crit = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "x failed", "expected": 1, "actual": 2},
                "failure_origin": "implementation"}
        rr = {"R-FOO-001": "fail"}
    return {
        "component_id": "comp-foo",
        "criteria": [crit],
        "requirement_results": rr,
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:aa", "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "overall": overall,
    }


def license_scan(blocked):
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9 if blocked else 0.1,
        "block_threshold": 0.7,
        "blocked": blocked,
        "matches": ([{"reference_id": "ref-1", "license_family": "gpl-3.0",
                      "risk_tier": "high", "score": 0.9}] if blocked else []),
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def secret_scan(flagged):
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


def loop_generation_result():
    return {
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


def loop_attempts():
    return [{"number": 1, "outcome": "passed", "retry_feedback": [],
             "error_category": None, "surface_ok": True, "overall": "pass",
             "failed_requirements": [], "transcript_sha256": None,
             "reauthored_tests": []}]


def setup_repo(tmp_path, monkeypatch, cfg):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for (slug, module), source in STAND_INS.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module + ".py")).write_text(source)

    manifest = {
        "spec_bundle_hash": "sha256:k",
        "model_pin": "m0",
        "prompt_version": "v9",
        "retry_feedback": None,
        "generation": {"mode": "agentic", "generator_version": "g@1",
                       "transcript_sha256": None, "turns": 4, "tool_calls": 7,
                       "isolation": "seatbelt"},
        "attempts": 2,
        "attempt_history": [{"number": 1, "outcome": "passed"}],
        "pipeline_version": "v1",
        "gate_versions": {"verifier": "v@1"},
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-1",
        "verification_report": verification_report("pass"),
        "license_scan": license_scan(False),
        "secret_scan": secret_scan(False),
        "assets": [],
    }
    foo = repo_root / "gen" / "foo"
    foo.mkdir(parents=True, exist_ok=True)
    (foo / ".provenance.json").write_text(json.dumps(manifest, indent=2))

    full_cfg = {
        "loop_generation_result": loop_generation_result(),
        "loop_attempts": loop_attempts(),
        "loop_verification_report": verification_report("pass"),
    }
    full_cfg.update(cfg)
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(full_cfg))
    log_path = tmp_path / "calls.jsonl"
    log_path.write_text("")
    monkeypatch.setenv("GATE_TEST_CONFIG", str(cfg_path))
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    return repo_root, log_path, full_cfg


def read_log(log_path):
    lines = [l for l in log_path.read_text().splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def calls_named(log, name):
    return [c for c in log if c["call"] == name]


def indices(log, name):
    return [i for i, c in enumerate(log) if c["call"] == name]


# ---------------------------------------------------------------------------
# Scenario 1: passing re-verification
# ---------------------------------------------------------------------------

def test_environment_differs_passing_reverification(tmp_path, monkeypatch):
    cfg = {
        "check_reason": "environment differs",
        "verify_report": verification_report("pass"),
        "license_scan": license_scan(False),
        "secret_scan": secret_scan(False),
    }
    repo_root, log_path, cfg = setup_repo(tmp_path, monkeypatch, cfg)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    log = read_log(log_path)

    verify_calls = calls_named(log, "verify")
    assert len(verify_calls) == 1, log
    va = verify_calls[0]["args"]
    assert va["component_id"] == "comp-foo"
    assert va["repo_root"] == str(repo_root)
    assert va["judge"] == "judge-closure"
    assert va["test_author"] == "test_author-closure"

    assert calls_named(log, "assemble") == []
    assert calls_named(log, "run_attempts") == []
    assert calls_named(log, "write_attempt_record") == []

    wp_idx = indices(log, "write_provenance")
    assert len(wp_idx) == 1, log
    lic_idx = indices(log, "license_scanner.scan")
    sec_idx = indices(log, "secret_scanner.scan")
    assert lic_idx and sec_idx
    assert wp_idx[0] > max(lic_idx)
    assert wp_idx[0] > max(sec_idx)

    wp = log[wp_idx[0]]["args"]
    assert wp["component_id"] == "comp-foo"
    assert wp["repo_root"] == str(repo_root)
    inputs = wp["inputs"]
    assert inputs["verification_report"] == cfg["verify_report"]
    assert inputs["license_scan_result"] == cfg["license_scan"]
    assert inputs["secret_scan_result"] == cfg["secret_scan"]
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
    assert plain(field(result, "verification")) == cfg["verify_report"]


# ---------------------------------------------------------------------------
# Scenario 2: failing re-verification proceeds as a miss
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "overall,lic_blocked,sec_flagged",
    [("fail", False, False), ("pass", True, False), ("pass", False, True)],
    ids=["verify-fail", "license-blocked", "secret-flagged"],
)
def test_environment_differs_failing_reverification_falls_through(
        tmp_path, monkeypatch, overall, lic_blocked, sec_flagged):
    cfg = {
        "check_reason": "environment differs",
        "verify_report": verification_report(overall),
        "license_scan": license_scan(lic_blocked),
        "secret_scan": secret_scan(sec_flagged),
    }
    repo_root, log_path, cfg = setup_repo(tmp_path, monkeypatch, cfg)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    log = read_log(log_path)

    cp_idx = indices(log, "check_provenance")
    assert len(cp_idx) == 1, log
    tracked = {"verify", "license_scanner.scan", "secret_scanner.scan", "assemble",
               "run_attempts", "write_attempt_record", "write_provenance",
               "write_sealed_provenance"}
    after = [c["call"] for c in log[cp_idx[0] + 1:] if c["call"] in tracked]
    assert after == [
        "verify",
        "license_scanner.scan",
        "secret_scanner.scan",
        "assemble",
        "run_attempts",
        "license_scanner.scan",
        "secret_scanner.scan",
        "write_provenance",
    ], log

    wp_calls = calls_named(log, "write_provenance")
    assert len(wp_calls) == 1
    assert wp_calls[0]["args"]["inputs"]["generation_result"] == cfg["loop_generation_result"]

    assert field(result, "reverified") is False


# ---------------------------------------------------------------------------
# Scenario 3: any other miss reason never re-verifies
# ---------------------------------------------------------------------------

def test_other_miss_reason_does_not_reverify(tmp_path, monkeypatch):
    cfg = {
        "check_reason": "assets differ",
        "verify_report": verification_report("pass"),
        "license_scan": license_scan(False),
        "secret_scan": secret_scan(False),
    }
    repo_root, log_path, cfg = setup_repo(tmp_path, monkeypatch, cfg)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    log = read_log(log_path)

    assert calls_named(log, "verify") == []
    assert len(calls_named(log, "run_attempts")) == 1, log
    assert field(result, "reverified") is False