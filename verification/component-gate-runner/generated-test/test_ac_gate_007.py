import json
import os
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = '''
import json as _json
import os as _os


def _log(name, **kw):
    record = {"call": name}
    record.update(kw)
    with open(_os.environ["GATE_TEST_LOG"], "a", encoding="utf-8") as _f:
        _f.write(_json.dumps(record, default=str) + "\\n")


def _plain(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if hasattr(value, "__dict__"):
        return _plain(vars(value))
    return str(value)
'''


PROVENANCE_CHECKER_SRC = LOG_HELPER + '''
from types import SimpleNamespace


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id, repo_root=str(repo_root))
    if _os.environ.get("GATE_TEST_SEALED") != "1":
        return None
    return SimpleNamespace(
        owners=["pipeline-team"],
        source_path="pipeline/foo/",
        source_hash="sha256:k",
        verifier_version="verifier-orchestrator@2.0.0",
    )


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id, repo_root=str(repo_root))
    return SimpleNamespace(
        spec_bundle_hash="sha256:abc123",
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash, repo_root=str(repo_root))
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id, repo_root=str(repo_root))
    return {
        "hit": False,
        "sealed": True,
        "reason": "manifest_missing",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }
'''


SPEC_BUNDLE_ASSEMBLER_SRC = LOG_HELPER + '''

class SpecBundle:
    _FIELDS = ("component_id", "spec_bundle_hash", "spec", "interface", "constraints",
               "dependency_interfaces", "dependency_context", "dependency_usage",
               "vars", "glossary", "hint_code")

    def __init__(self, **kw):
        for name in self._FIELDS:
            setattr(self, name, kw.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._FIELDS else default

    def keys(self):
        return list(self._FIELDS)

    def to_dict(self):
        return {name: getattr(self, name) for name in self._FIELDS}


class CriterionBundle:
    _FIELDS = ("component_id", "criterion_id", "covers", "criterion_text",
               "requirement_text", "interface", "glossary", "dependency_interfaces")

    def __init__(self, **kw):
        for name in self._FIELDS:
            setattr(self, name, kw.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._FIELDS else default

    def keys(self):
        return list(self._FIELDS)


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, repo_root=str(repo_root), mode=mode)
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:abc123",
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x When y Then z",
        requirement_text="R-FOO-001",
        interface="foo(x: int) -> int",
        glossary="",
        dependency_interfaces={},
    )
'''


GENERATOR_SRC = LOG_HELPER + '''
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


class GenerationResult:
    def __init__(self, component_id, spec_bundle_hash, model, prompt_version, cache_hit,
                 files, model_call_error, refused, retry_feedback):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.model = model
        self.prompt_version = prompt_version
        self.cache_hit = cache_hit
        self.files = files
        self.model_call_error = model_call_error
        self.refused = refused
        self.retry_feedback = retry_feedback

    def to_dict(self):
        return dict(vars(self))


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", model=model, repo_root=str(repo_root))
    component_id = bundle["component_id"] if isinstance(bundle, dict) else bundle.component_id
    sbh = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else bundle.spec_bundle_hash
    return GenerationResult(
        component_id=component_id,
        spec_bundle_hash=sbh,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR_SRC = LOG_HELPER + '''
GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    def __init__(self, component_id, criteria, requirement_results, interface_drift,
                 mutation_score, overall):
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
    _log("verify", component_id=component_id, repo_root=str(repo_root),
         judge_callable=callable(judge), test_author_callable=callable(test_author))
    overall = _os.environ.get("GATE_TEST_OVERALL", "pass")
    if overall == "pass":
        criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ]
        rr = {"R-FOO-001": "pass", "R-FOO-002": "pass"}
    else:
        criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
             "failure_detail": {"message": "foo(2) equals 4 failed", "expected": 4, "actual": 5}},
        ]
        rr = {"R-FOO-001": "pass", "R-FOO-002": "fail"}
    return VerificationReport(
        component_id=component_id,
        criteria=criteria,
        requirement_results=rr,
        interface_drift=False,
        mutation_score=None,
        overall=overall,
    )
'''


LICENSE_SCANNER_SRC = LOG_HELPER + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id, repo_root=str(repo_root))
    return {
        "component_id": component_id,
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
'''


SECRET_SCANNER_SRC = LOG_HELPER + '''

class AllowlistInvalidError(Exception):
    pass


class SecretScanResult:
    def __init__(self, scope, gate_version, flagged, matches, allowed,
                 unused_allowlist_entries, notified, notification_delivery_error, cache_hit):
        self.scope = scope
        self.gate_version = gate_version
        self.flagged = flagged
        self.matches = matches
        self.allowed = allowed
        self.unused_allowlist_entries = unused_allowlist_entries
        self.notified = notified
        self.notification_delivery_error = notification_delivery_error
        self.cache_hit = cache_hit

    def to_dict(self):
        return dict(vars(self))


def _clean(scope):
    return SecretScanResult(
        scope=scope,
        gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def scan(repo_root):
    _log("secret_scan", repo_root=str(repo_root))
    return _clean("full")


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    return _clean("precommit")


def propose(repo_root):
    _log("secret_propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER_SRC = LOG_HELPER + '''
from pathlib import Path as _Path


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash, repo_root=str(repo_root))
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempt_id = "2026-11-15T00:00:00Z-a1b2c3"
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    d = _Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (attempt_id.replace(":", "-") + ".json")).write_text(_json.dumps(record), encoding="utf-8")
    return record


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures")
    return []
'''


PROVENANCE_WRITER_SRC = LOG_HELPER + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


class SealedProvenanceInputs:
    def __init__(self, component_id, owners, source_path, source_hash,
                 verifier_version, verification_report):
        self.component_id = component_id
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version
        self.verification_report = verification_report


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id, repo_root=str(repo_root))
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log(
        "write_sealed_provenance",
        component_id=component_id,
        repo_root=str(repo_root),
        inputs_component_id=_get(inputs, "component_id"),
        owners=_plain(_get(inputs, "owners")),
        source_path=_get(inputs, "source_path"),
        source_hash=_get(inputs, "source_hash"),
        verifier_version=_get(inputs, "verifier_version"),
        verification_report=_plain(_get(inputs, "verification_report")),
    )
    return None
'''


TEST_AUTHOR_SRC = LOG_HELPER + '''

def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model, seed=seed)
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py",
                 "content": "def test_x():\\n    assert True\\n"},
        "model_call_error": None,
    }
'''


LLM_ENDPOINT_SRC = LOG_HELPER + '''

def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}
'''


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER_SRC,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER_SRC,
    "generator": GENERATOR_SRC,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR_SRC,
    "license-scanner": LICENSE_SCANNER_SRC,
    "secret-scanner": SECRET_SCANNER_SRC,
    "provenance-tracker": PROVENANCE_TRACKER_SRC,
    "provenance-writer": PROVENANCE_WRITER_SRC,
    "test-author": TEST_AUTHOR_SRC,
    "llm-endpoint": LLM_ENDPOINT_SRC,
}


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for slug, src in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(src, encoding="utf-8")
    return repo_root


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _calls(log, name):
    return [r for r in log if r["call"] == name]


def _index(log, name):
    for i, r in enumerate(log):
        if r["call"] == name:
            return i
    raise AssertionError(f"{name} never called")


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = _build_repo(tmp_path)
    log_path = tmp_path / "calls.jsonl"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    monkeypatch.chdir(tmp_path)
    return repo_root, log_path


EXPECTED_PASS_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
    "interface_drift": False,
    "mutation_score": None,
    "overall": "pass",
}


def _assert_sealed_calls(log, repo_root):
    for never in ("check_provenance", "current_provenance_key", "assemble",
                  "generate", "write_attempt_record", "write_provenance"):
        assert _calls(log, never) == [], f"{never} must not be called for a sealed component"

    assert len(_calls(log, "current_sealed_key")) == 1
    assert len(_calls(log, "verify")) == 1
    assert len(_calls(log, "license_scan")) == 1
    assert len(_calls(log, "secret_scan")) == 1

    v = _calls(log, "verify")[0]
    assert v["component_id"] == "comp-foo"
    assert v["judge_callable"] is True
    assert v["test_author_callable"] is True

    lic = _calls(log, "license_scan")[0]
    assert lic["component_id"] == "comp-foo"

    writes = _calls(log, "write_sealed_provenance")
    assert len(writes) == 1
    w_idx = _index(log, "write_sealed_provenance")
    assert w_idx > _index(log, "verify")
    assert w_idx > _index(log, "license_scan")
    assert w_idx > _index(log, "secret_scan")
    assert _index(log, "current_sealed_key") < _index(log, "verify")

    w = writes[0]
    assert w["component_id"] == "comp-foo"
    assert w["inputs_component_id"] == "comp-foo"
    assert w["owners"] == ["pipeline-team"]
    assert w["source_path"] == "pipeline/foo/"
    assert w["source_hash"] == "sha256:k"
    assert w["verifier_version"] == "verifier-orchestrator@2.0.0"
    return w


def test_sealed_component_passing_verification(env, monkeypatch):
    repo_root, log_path = env
    monkeypatch.setenv("GATE_TEST_SEALED", "1")
    monkeypatch.setenv("GATE_TEST_OVERALL", "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    log = _read_log(log_path)
    w = _assert_sealed_calls(log, repo_root)
    assert w["verification_report"] == EXPECTED_PASS_REPORT

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None


def test_sealed_component_failing_verification(env, monkeypatch):
    repo_root, log_path = env
    monkeypatch.setenv("GATE_TEST_SEALED", "1")
    monkeypatch.setenv("GATE_TEST_OVERALL", "fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    log = _read_log(log_path)
    w = _assert_sealed_calls(log, repo_root)
    report = w["verification_report"]
    assert report["overall"] == "fail"
    assert report["component_id"] == "comp-foo"
    assert [c["id"] for c in report["criteria"]] == ["AC-FOO-001", "AC-FOO-002"]
    assert report["criteria"][1]["result"] == "fail"

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"


def test_non_sealed_component_never_writes_sealed_provenance(env, monkeypatch):
    repo_root, log_path = env
    monkeypatch.setenv("GATE_TEST_SEALED", "0")
    monkeypatch.setenv("GATE_TEST_OVERALL", "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    log = _read_log(log_path)
    assert _calls(log, "write_sealed_provenance") == []

    for made in ("current_sealed_key", "current_provenance_key", "check_provenance",
                 "assemble", "generate", "verify", "license_scan", "secret_scan",
                 "write_attempt_record", "write_provenance"):
        assert len(_calls(log, made)) == 1, f"{made} should be called once on a non-sealed component"

    assert _index(log, "current_sealed_key") < _index(log, "current_provenance_key")

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False