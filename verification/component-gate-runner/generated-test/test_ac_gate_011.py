# hotdocs-criterion: sha256:c342fe758ddb9219b788bad722360f3fe008887847b7dc610d5664a3d1296f2b
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = '''
import json
import dataclasses
from pathlib import Path, PurePath

_ROOT = Path(__file__).parents[2]


def _plain(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, PurePath):
        return str(v)
    if isinstance(v, dict):
        return dict((str(k), _plain(x)) for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    td = getattr(v, "to_dict", None)
    if callable(td) and not isinstance(v, type):
        return _plain(td())
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return dict((f.name, _plain(getattr(v, f.name))) for f in dataclasses.fields(v))
    if callable(v):
        return getattr(v, "__name__", repr(v))
    if hasattr(v, "__dict__"):
        return dict((k, _plain(x)) for k, x in vars(v).items() if not k.startswith("_"))
    return repr(v)


def _cfg():
    return json.loads((_ROOT / "fake_config.json").read_text())


def _log(name, **kw):
    with open(_ROOT / "calls.log", "a") as fh:
        fh.write(json.dumps(dict(call=name, args=_plain(kw))) + "\\n")
'''

VERIFICATION_REPORT_CLASS = '''

@dataclasses.dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: object
    mutation_error: object
    assets: list
    overall: str

    def to_dict(self):
        return dict((f.name, getattr(self, f.name)) for f in dataclasses.fields(self))
'''

PROVENANCE_CHECKER = PRELUDE + '''

class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions, assets):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions
        self.assets = assets


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id, repo_root=repo_root)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id, repo_root=repo_root)
    return ProvenanceKey("sha256:k", {"verifier": "v@1"},
                         [{"kind": "python", "path": ".", "definition_sha256": None,
                           "adapter_sha256": "sha256:aa", "versions": {"python": "3.12.4"},
                           "lockfile_sha256": None}])


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id, spec_bundle_hash=spec_bundle_hash,
         gate_versions=gate_versions, repo_root=repo_root)
    return {"hit": False, "reason": _cfg()["reason"], "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id, repo_root=repo_root)
    return {"hit": False, "sealed": False, "reason": "not_sealed", "verification_report": None,
            "license_scan": None, "secret_scan": None, "owners": None,
            "source_hash": None, "written_at": None}
'''

VERIFIER = PRELUDE + VERIFICATION_REPORT_CLASS + '''

GATE_VERSION = "verifier-orchestrator@3.5.0"
DEFAULT_TEST_TIMEOUT = 300.0


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id, repo_root=repo_root,
         judge=getattr(judge, "__name__", repr(judge)),
         test_author=getattr(test_author, "__name__", repr(test_author)))
    overall = _cfg()["verify_overall"]
    return VerificationReport(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
                   "result": "pass" if overall == "pass" else "fail"}],
        requirement_results={"R-FOO-001": "pass" if overall == "pass" else "fail"},
        interface_drift=False, mutation_score=0.9, mutation_error=None, assets=[],
        overall=overall)


def main(argv=None):
    return 0
'''

GENERATION_LOOP = PRELUDE + VERIFICATION_REPORT_CLASS + '''

RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


@dataclasses.dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: dict
    model_call_error: object
    refused: object
    retry_feedback: object
    mode: str
    transcript_sha256: object
    turns: int
    tool_calls: int
    isolation: object

    def to_dict(self):
        return dict((f.name, getattr(self, f.name)) for f in dataclasses.fields(self))


@dataclasses.dataclass
class AttemptLoopResult:
    passed: bool
    stop_reason: str
    attempts: list
    generation_result: object
    verification_report: object
    surface_report: object

    def to_dict(self):
        return _plain(dict((f.name, getattr(self, f.name)) for f in dataclasses.fields(self)))


def fake_test_author(bundle):
    return {"model_call_error": None, "file": None}


def fake_judge(bundle):
    return {"result": "pass", "rationale": None}


def make_closures(model, seed, repo_root, llm_backend=None):
    _log("make_closures", model=model, seed=seed, repo_root=repo_root,
         llm_backend=repr(llm_backend))
    return (fake_test_author, fake_judge)


def run_attempts(component_id, bundle, repo_root, model, *, mode="single", max_attempts=3,
                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,
                 on_attempt=None):
    _log("run_attempts", component_id=component_id, repo_root=repo_root, model=model)
    gen = GenerationResult(
        component_id=component_id, spec_bundle_hash="sha256:k", model=model,
        prompt_version="v12", cache_hit=False, files={"foo.py": "X = 1\\n"},
        model_call_error=None, refused=None, retry_feedback=None, mode="single",
        transcript_sha256=None, turns=1, tool_calls=0, isolation=None)
    rep = VerificationReport(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-777", "covers": "R-FOO-777", "kind": "compiled", "result": "pass"}],
        requirement_results={"R-FOO-777": "pass"}, interface_drift=False,
        mutation_score=0.8, mutation_error=None, assets=[], overall="pass")
    attempt = {"number": 1, "outcome": "passed", "retry_feedback": [],
               "error_category": None, "surface_ok": True, "overall": "pass",
               "failed_requirements": [], "transcript_sha256": None,
               "reauthored_tests": []}
    return AttemptLoopResult(passed=True, stop_reason="passed", attempts=[attempt],
                             generation_result=gen, verification_report=rep,
                             surface_report=None)
'''

ASSEMBLER = PRELUDE + '''

def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, repo_root=repo_root, mode=mode)
    return {"component_id": component_id, "spec_bundle_hash": "sha256:k", "spec": "s",
            "interface": "i", "constraints": "c", "dependency_interfaces": {},
            "dependency_context": {}, "dependency_usage": {}, "vars": {},
            "glossary": "", "hint_code": None}


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return {"component_id": component_id, "criterion_id": criterion_id, "covers": "R-FOO-001",
            "criterion_text": "", "requirement_text": "", "interface": "", "glossary": "",
            "dependency_interfaces": {}, "testing": ""}
'''

LICENSE = PRELUDE + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id, repo_root=repo_root)
    return {"component_id": component_id, "gate_version": "license_scanner@4.0.0-no-reference-corpus",
            "evaluated": True, "reason": None, "similarity_score": 0.1, "block_threshold": 0.7,
            "blocked": _cfg()["license_blocked"], "matches": [], "notified": False,
            "notification_delivery_error": None, "cache_hit": False}
'''

SECRET = PRELUDE + '''

@dataclasses.dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool
    matches: list
    allowed: list
    unused_allowlist_entries: list
    notified: bool
    notification_delivery_error: object
    cache_hit: bool

    def to_dict(self):
        return dict((f.name, getattr(self, f.name)) for f in dataclasses.fields(self))


class AllowlistInvalidError(Exception):
    pass


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def _result(scope):
    flagged = _cfg()["secret_flagged"]
    matches = [{"rule_id": "Fake Rule", "risk_tier": "low", "file": "gen/foo/x.py", "line": 1}] if flagged else []
    return SecretScanResult(scope=scope, gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
                            flagged=flagged, matches=matches, allowed=[],
                            unused_allowlist_entries=[], notified=False,
                            notification_delivery_error=None, cache_hit=False)


def scan(repo_root):
    _log("secret_scan", repo_root=repo_root)
    return _result("full")


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    return _result("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

WRITER = PRELUDE + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id, inputs=inputs, repo_root=repo_root)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id, inputs=inputs, repo_root=repo_root)
    return None
'''

TRACKER = PRELUDE + '''

def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    return {"attempt_id": "2026-01-01T00:00:00Z-aaaaaa", "component_id": component_id,
            "timestamp": "2026-01-01T00:00:00Z", "spec_bundle_hash": spec_bundle_hash,
            "generation": _plain(generation_result), "verification": _plain(verification_report)}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {},
            "secret_scan": None, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''

ATTEMPT_HISTORY = [
    {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
     "error_category": None, "failed_requirements": ["R-FOO-002"],
     "transcript_sha256": None},
    {"number": 2, "outcome": "passed", "retry_feedback": ["R-FOO-002"],
     "error_category": None, "failed_requirements": [],
     "transcript_sha256": None},
]

MANIFEST = {
    "spec_bundle_hash": "sha256:old",
    "model_pin": "m0",
    "prompt_version": "v9",
    "retry_feedback": ["R-FOO-002"],
    "generation": {"mode": "agentic", "generator_version": "generator@3.0.0+v11",
                   "turns": 4, "tool_calls": 7, "isolation": "seatbelt"},
    "attempts": 2,
    "attempt_history": ATTEMPT_HISTORY,
    "pipeline_version": "v1",
    "gate_versions": {"verifier": "v@0"},
    "provenance_hit": False,
    "generated_at": "2026-01-01T00:00:00Z",
    "verification_run_id": "run-1",
    "verification_report": {"overall": "pass"},
    "license_scan": {"blocked": False},
    "secret_scan": {"flagged": False},
    "assets": [],
}


def plain(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    td = getattr(v, "to_dict", None)
    if callable(td):
        return plain(td())
    if hasattr(v, "__dict__"):
        return {k: plain(x) for k, x in vars(v).items() if not k.startswith("_")}
    return repr(v)


def setup_repo(repo_root, reason, verify_overall, license_blocked, secret_flagged):
    fakes = {
        "provenance-checker": PROVENANCE_CHECKER,
        "verifier-orchestrator": VERIFIER,
        "generation-loop": GENERATION_LOOP,
        "spec-bundle-assembler": ASSEMBLER,
        "license-scanner": LICENSE,
        "secret-scanner": SECRET,
        "provenance-writer": WRITER,
        "provenance-tracker": TRACKER,
    }
    for slug, source in fakes.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source)
    (repo_root / "fake_config.json").write_text(json.dumps({
        "reason": reason,
        "verify_overall": verify_overall,
        "license_blocked": license_blocked,
        "secret_flagged": secret_flagged,
    }))
    foo = repo_root / "gen" / "foo"
    foo.mkdir(parents=True, exist_ok=True)
    (foo / ".provenance.json").write_text(json.dumps(MANIFEST))
    (foo / "foo.py").write_text("X = 1\n")


def read_calls(repo_root):
    log = repo_root / "calls.log"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def names(calls):
    return [c["call"] for c in calls]


def after_check(calls):
    idx = names(calls).index("check_provenance")
    return calls[idx + 1:]


def expected_verify_report(overall):
    return {
        "component_id": "comp-foo",
        "criteria": [{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
                      "result": "pass" if overall == "pass" else "fail"}],
        "requirement_results": {"R-FOO-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


def run(repo_root):
    return component_gate_runner.run_component_gates("comp-foo", repo_root, "m")


def test_environment_differs_passing_reverification(tmp_path):
    repo_root = tmp_path
    setup_repo(repo_root, "environment differs", "pass", False, False)
    result = run(repo_root)
    calls = read_calls(repo_root)
    n = names(calls)

    assert "assemble" not in n
    assert "run_attempts" not in n
    assert "write_attempt_record" not in n

    verifies = [c for c in calls if c["call"] == "verify"]
    assert len(verifies) == 1
    v = verifies[0]["args"]
    assert v["component_id"] == "comp-foo"
    assert v["repo_root"] == str(repo_root)
    assert v["judge"] == "fake_judge"
    assert v["test_author"] == "fake_test_author"

    mcs = [c for c in calls if c["call"] == "make_closures"]
    assert len(mcs) == 1
    assert mcs[0]["args"]["model"] == "m"
    assert mcs[0]["args"]["seed"] == 0
    assert mcs[0]["args"]["repo_root"] == str(repo_root)
    assert n.index("make_closures") < n.index("verify")

    wps = [c for c in calls if c["call"] == "write_provenance"]
    assert len(wps) == 1
    wp_idx = n.index("write_provenance")
    assert n.index("license_scan") < wp_idx
    assert n.index("secret_scan") < wp_idx
    assert n.index("verify") < n.index("license_scan")

    inputs = wps[0]["args"]["inputs"]
    assert wps[0]["args"]["component_id"] == "comp-foo"
    assert inputs["component_id"] == "comp-foo"
    assert inputs["verification_report"] == expected_verify_report("pass")
    assert inputs["license_scan_result"]["blocked"] is False
    assert inputs["secret_scan_result"]["flagged"] is False
    assert inputs["attempts"] == 2
    assert inputs["attempt_history"] == ATTEMPT_HISTORY
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
    assert "generator_version" not in gen

    assert field(result, "reverified") is True
    assert field(result, "blocked") is False
    assert field(result, "provenance_hit") is False
    assert list(field(result, "attempts")) == []
    assert plain(field(result, "verification")) == expected_verify_report("pass")


def test_environment_differs_secret_flagged_still_reverified(tmp_path):
    repo_root = tmp_path
    setup_repo(repo_root, "environment differs", "pass", False, True)
    result = run(repo_root)
    n = names(read_calls(repo_root))
    assert field(result, "reverified") is True
    assert "run_attempts" not in n


def _check_fallthrough(repo_root, verify_overall, license_blocked):
    setup_repo(repo_root, "environment differs", verify_overall, license_blocked, False)
    result = run(repo_root)
    calls = read_calls(repo_root)
    seq = [c for c in after_check(calls) if c["call"] != "make_closures"]
    assert names(seq) == [
        "verify", "license_scan", "secret_scan", "assemble", "run_attempts",
        "license_scan", "secret_scan", "write_provenance",
    ]
    wps = [c for c in calls if c["call"] == "write_provenance"]
    assert len(wps) == 1
    gen = wps[0]["args"]["inputs"]["generation_result"]
    assert gen["files"] == {"foo.py": "X = 1\n"}
    assert gen["prompt_version"] == "v12"
    assert field(result, "reverified") is False


def test_environment_differs_verify_fails_falls_through(tmp_path):
    _check_fallthrough(tmp_path, "fail", False)


def test_environment_differs_license_blocked_falls_through(tmp_path):
    _check_fallthrough(tmp_path, "pass", True)


def test_assets_differ_is_plain_miss(tmp_path):
    repo_root = tmp_path
    setup_repo(repo_root, "assets differ", "pass", False, False)
    result = run(repo_root)
    n = names(read_calls(repo_root))
    assert "verify" not in n
    assert n.count("run_attempts") == 1
    assert field(result, "reverified") is False