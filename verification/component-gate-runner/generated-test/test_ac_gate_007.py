import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = '''
import json
import os


def _log(name, **data):
    rec = {"call": name}
    rec.update(data)
    with open(os.environ["GATE_TEST_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\\n")


def _cfg():
    with open(os.environ["GATE_TEST_CONFIG"], encoding="utf-8") as f:
        return json.load(f)


def _get(v, n):
    return v[n] if isinstance(v, dict) else getattr(v, n)


def _plain(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if hasattr(v, "to_dict"):
        return _plain(v.to_dict())
    try:
        return _plain(vars(v))
    except TypeError:
        return str(v)


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def to_dict(self):
        return dict(self.__dict__)

    def __getitem__(self, k):
        return self.__dict__[k]

    def get(self, k, default=None):
        return self.__dict__.get(k, default)

    def keys(self):
        return self.__dict__.keys()
'''

PROVENANCE_CHECKER = COMMON + '''

def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    if _cfg()["sealed"]:
        return _Obj(
            owners=["pipeline-team"],
            source_path="pipeline/foo/",
            source_hash="sha256:k",
            verifier_version="verifier-orchestrator@2.0.0",
        )
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return _Obj(
        spec_bundle_hash="sha256:abc",
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id)
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {
        "hit": False, "sealed": False, "reason": "not_sealed",
        "verification_report": None, "license_scan": None, "secret_scan": None,
        "owners": None, "source_hash": None, "written_at": None,
    }
'''

SPEC_BUNDLE_ASSEMBLER = COMMON + '''

def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return _Obj(
        component_id=component_id, spec_bundle_hash="sha256:abc", spec="s",
        interface="i", constraints="c", dependency_interfaces={},
        dependency_context={}, dependency_usage={}, vars={}, glossary="",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return _Obj(
        component_id=component_id, criterion_id=criterion_id, covers="R-FOO-001",
        criterion_text="", requirement_text="", interface="", glossary="",
        dependency_interfaces={},
    )
'''

GENERATOR = COMMON + '''
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", model=model)
    return _Obj(
        component_id="comp-foo", spec_bundle_hash="sha256:abc", model=model,
        prompt_version=PROMPT_VERSION, cache_hit=False,
        files={"foo.py": "def double(x):\\n    return 2 * x\\n"},
        model_call_error=None, refused=None, retry_feedback=retry_feedback,
    )
'''

VERIFIER_ORCHESTRATOR = COMMON + '''
GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    def __init__(self, component_id, criteria, requirement_results, interface_drift, mutation_score, overall):
        self.component_id = component_id
        self.criteria = criteria
        self.requirement_results = requirement_results
        self.interface_drift = interface_drift
        self.mutation_score = mutation_score
        self.overall = overall

    def to_dict(self):
        return {
            "component_id": self.component_id,
            "criteria": [dict(c) for c in self.criteria],
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }


def verify(component_id, repo_root, judge=None, test_author=None):
    overall = _cfg()["overall"]
    second = "pass" if overall == "pass" else "fail"
    crit2 = {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": second}
    if second == "fail":
        crit2["failure_detail"] = {"message": "m", "expected": 4, "actual": 3}
    report = VerificationReport(
        component_id=component_id,
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            crit2,
        ],
        requirement_results={"R-FOO-001": "pass", "R-FOO-002": second},
        interface_drift=False,
        mutation_score=None,
        overall=overall,
    )
    _log("verify", component_id=component_id, report=report.to_dict(),
         judge_callable=callable(judge), test_author_callable=callable(test_author))
    return report
'''

LICENSE_SCANNER = COMMON + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False, "reason": "no-reference-corpus",
        "similarity_score": None, "block_threshold": None, "blocked": False,
        "matches": [], "notified": False, "notification_delivery_error": None,
        "cache_hit": False,
    }
'''

SECRET_SCANNER = COMMON + '''

class AllowlistInvalidError(Exception):
    pass


class SecretScanResult:
    def __init__(self, scope):
        self.scope = scope
        self.gate_version = "secret_scanner@0.0.0"
        self.flagged = False
        self.matches = []
        self.allowed = []
        self.unused_allowlist_entries = []
        self.notified = False
        self.notification_delivery_error = None
        self.cache_hit = False

    def to_dict(self):
        return dict(self.__dict__)


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def scan(repo_root):
    _log("secret_scan")
    return SecretScanResult("full")


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    return SecretScanResult("precommit")


def propose(repo_root):
    _log("secret_propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_TRACKER = COMMON + '''
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    rec = {
        "attempt_id": "2026-11-15T00:00:00Z-a1b2c3",
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    for name in (slug, component_id):
        d = Path(repo_root) / ".hotdocs" / "attempts" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "2026-11-15T00-00-00Z-a1b2c3.json").write_text(json.dumps(rec, default=str), encoding="utf-8")
    return rec


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures")
    return []
'''

PROVENANCE_WRITER = COMMON + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


_SEALED_KEYS = ["component_id", "owners", "source_path", "source_hash", "verifier_version", "verification_report"]


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)


def write_sealed_provenance(component_id, inputs, repo_root):
    rec = {}
    for k in _SEALED_KEYS:
        try:
            rec[k] = _plain(_get(inputs, k))
        except Exception:
            rec[k] = "<missing>"
    _log("write_sealed_provenance", component_id=component_id, inputs=rec)
'''

TEST_AUTHOR = COMMON + '''

def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model)
    return {
        "component_id": "comp-foo", "criterion_id": "AC-FOO-001", "model": model,
        "seed": seed, "prompt_version": "v1", "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py", "content": ""},
        "model_call_error": None,
    }
'''

LLM_ENDPOINT = COMMON + '''

def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}
'''

FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generator": GENERATOR,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-tracker": PROVENANCE_TRACKER,
    "provenance-writer": PROVENANCE_WRITER,
    "test-author": TEST_AUTHOR,
    "llm-endpoint": LLM_ENDPOINT,
}


def _setup(tmp_path, monkeypatch, sealed, overall):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")
    log = tmp_path / "calls.jsonl"
    log.write_text("", encoding="utf-8")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"sealed": sealed, "overall": overall}), encoding="utf-8")
    monkeypatch.setenv("GATE_TEST_LOG", str(log))
    monkeypatch.setenv("GATE_TEST_CONFIG", str(cfg))
    # no component.md for comp-foo
    assert not (repo_root / "specs" / "components" / "foo" / "component.md").exists()
    return repo_root, log


def _calls(log):
    return [json.loads(line) for line in Path(log).read_text(encoding="utf-8").splitlines() if line.strip()]


def _names(calls):
    return [c["call"] for c in calls]


NON_SEALED_ONLY = [
    "check_provenance",
    "current_provenance_key",
    "assemble",
    "generate",
    "write_attempt_record",
    "write_provenance",
]


def _assert_sealed_write(calls, overall):
    names = _names(calls)
    assert names.count("verify") == 1, names
    assert names.count("license_scan") == 1, names
    assert names.count("secret_scan") == 1, names
    assert names.count("write_sealed_provenance") == 1, names

    w_idx = names.index("write_sealed_provenance")
    assert w_idx > names.index("verify"), names
    assert w_idx > names.index("license_scan"), names
    assert w_idx > names.index("secret_scan"), names

    verify_call = calls[names.index("verify")]
    write_call = calls[w_idx]
    assert write_call["component_id"] == "comp-foo"
    inputs = write_call["inputs"]
    assert inputs["component_id"] == "comp-foo"
    assert inputs["owners"] == ["pipeline-team"]
    assert inputs["source_path"] == "pipeline/foo/"
    assert inputs["source_hash"] == "sha256:k"
    assert inputs["verifier_version"] == "verifier-orchestrator@2.0.0"

    report = inputs["verification_report"]
    assert isinstance(report, dict), report
    expected = verify_call["report"]
    assert report.get("overall") == overall
    assert report.get("overall") == expected["overall"]
    assert report.get("criteria") == expected["criteria"]
    assert len(report.get("criteria")) == 2
    assert report.get("component_id") == expected["component_id"]


def test_sealed_component_passing_verification(tmp_path, monkeypatch):
    repo_root, log = _setup(tmp_path, monkeypatch, sealed=True, overall="pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log)
    names = _names(calls)
    for forbidden in NON_SEALED_ONLY:
        assert forbidden not in names, (forbidden, names)
    assert names.count("current_sealed_key") == 1, names

    _assert_sealed_write(calls, "pass")

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False


def test_sealed_component_failing_verification(tmp_path, monkeypatch):
    repo_root, log = _setup(tmp_path, monkeypatch, sealed=True, overall="fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log)
    names = _names(calls)
    for forbidden in NON_SEALED_ONLY:
        assert forbidden not in names, (forbidden, names)

    _assert_sealed_write(calls, "fail")

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"


def test_non_sealed_component_never_writes_sealed_provenance(tmp_path, monkeypatch):
    repo_root, log = _setup(tmp_path, monkeypatch, sealed=False, overall="pass")

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log)
    names = _names(calls)
    assert "write_sealed_provenance" not in names, names
    for expected in [
        "current_sealed_key",
        "current_provenance_key",
        "check_provenance",
        "assemble",
        "generate",
        "verify",
        "license_scan",
        "secret_scan",
        "write_attempt_record",
        "write_provenance",
    ]:
        assert names.count(expected) == 1, (expected, names)