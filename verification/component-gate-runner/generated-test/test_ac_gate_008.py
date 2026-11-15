import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = r'''
import dataclasses
import json
import os
import uuid
from pathlib import Path


def _ser(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, dict):
        return {str(k): _ser(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_ser(x) for x in v]
    if hasattr(v, "to_dict") and callable(getattr(v, "to_dict")):
        return _ser(v.to_dict())
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return _ser(dataclasses.asdict(v))
    if hasattr(v, "__dict__"):
        return _ser(vars(v))
    return str(v)


def _log(call, **data):
    path = os.environ.get("GATE_TEST_LOG")
    if not path:
        return
    rec = {"call": call}
    for k, x in data.items():
        rec[k] = _ser(x)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)
'''


PROVENANCE_CHECKER = r'''
GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def to_dict(self):
        return {"spec_bundle_hash": self.spec_bundle_hash,
                "gate_versions": dict(self.gate_versions)}


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return ProvenanceKey("sha256:k", dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash)
    return {"hit": False, "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {"hit": False, "sealed": False, "reason": "not_sealed",
            "verification_report": None, "license_scan": None,
            "secret_scan": None, "owners": None, "source_hash": None,
            "written_at": None}
'''


SPEC_BUNDLE_ASSEMBLER = r'''
@dataclasses.dataclass
class SpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]


@dataclasses.dataclass
class CriterionBundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:k",
        spec="Foo doubles a number.",
        interface="# Library\n\ndouble(x: int) -> int",
        constraints="None.",
        glossary="- **Foo** — a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id,
         criterion_id=criterion_id)
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x = 2\nWhen double(x) is called\nThen it returns 4",
        requirement_text="double(x) MUST return 2 * x.",
        interface="# Library\n\ndouble(x: int) -> int",
        glossary="- **Foo** — a test term.",
    )
'''


GENERATOR = r'''
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


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


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    mode = os.environ.get("GATE_TEST_GEN_MODE", "files")
    cid = _get(bundle, "component_id")
    h = _get(bundle, "spec_bundle_hash")
    if mode == "error":
        res = GenerationResult(
            component_id=cid, spec_bundle_hash=h, model=model,
            prompt_version=PROMPT_VERSION, cache_hit=False, files={},
            model_call_error={"category": "network",
                              "message": "fake network failure"},
            refused=None, retry_feedback=retry_feedback,
        )
    else:
        res = GenerationResult(
            component_id=cid, spec_bundle_hash=h, model=model,
            prompt_version=PROMPT_VERSION, cache_hit=False,
            files={"foo.py": "def double(x):\n    return 2 * x\n"},
            model_call_error=None, refused=None,
            retry_feedback=retry_feedback,
        )
    _log("generate", component_id=cid, result=res)
    return res
'''


VERIFIER_ORCHESTRATOR = r'''
GATE_VERSION = "verifier-orchestrator@2.0.0"


@dataclasses.dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: object
    overall: str

    def to_dict(self):
        return dataclasses.asdict(self)


def verify(component_id, repo_root, judge=None, test_author=None):
    overall = os.environ.get("GATE_TEST_VERIFY_OVERALL", "pass")
    result = "pass" if overall == "pass" else "fail"
    crit = {"id": "AC-FOO-001", "covers": "R-FOO-001",
            "kind": "generated-test", "result": result}
    if result == "fail":
        crit["failure_detail"] = {"message": "double(2) equals 4 failed",
                                  "expected": 4, "actual": 3}
    rep = VerificationReport(
        component_id=component_id,
        criteria=[crit],
        requirement_results={"R-FOO-001": result},
        interface_drift=False,
        mutation_score=0.9,
        overall=overall,
    )
    _log("verify", component_id=component_id, report=rep)
    return rep
'''


LICENSE_SCANNER = r'''
def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    res = {
        "component_id": component_id,
        "gate_version": gate_version(repo_root),
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
    _log("license_scan", component_id=component_id)
    return res
'''


SECRET_SCANNER = r'''
class AllowlistInvalidError(Exception):
    pass


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
        return dataclasses.asdict(self)


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def _clean(scope):
    return SecretScanResult(
        scope=scope, gate_version="secret_scanner@0.0.0", flagged=False,
        matches=[], allowed=[], unused_allowlist_entries=[], notified=False,
        notification_delivery_error=None, cache_hit=False,
    )


def scan(repo_root):
    _log("secret_scan")
    return _clean("full")


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    return _clean("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = r'''
def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id,
         generation_result=generation_result,
         verification_report=verification_report,
         verification_is_none=(verification_report is None),
         spec_bundle_hash=spec_bundle_hash)
    if os.environ.get("GATE_TEST_TRACKER_RAISE") == "1":
        raise RuntimeError("fake write_attempt_record failure")
    slug = component_id[5:] if component_id.startswith("comp-") else component_id
    d = Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    ts = "2026-11-15T00:00:00Z"
    attempt_id = ts + "-" + uuid.uuid4().hex[:6]
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": ts,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _ser(generation_result),
        "verification": _ser(verification_report),
    }
    (d / (attempt_id.replace(":", "-") + ".json")).write_text(
        json.dumps(record), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER = r'''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''


TEST_AUTHOR = r'''
def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    cid = _get(bundle, "component_id")
    crit = _get(bundle, "criterion_id")
    _log("author_test", component_id=cid, criterion_id=crit)
    name = "test_" + crit.lower().replace("-", "_") + ".py"
    return {
        "component_id": cid,
        "criterion_id": crit,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/" + name,
                 "content": "def test_placeholder():\n    assert True\n"},
        "model_call_error": None,
    }
'''


LLM_ENDPOINT = r'''
DEFAULT_TIMEOUT_SECONDS = 600


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "mock",
            "model_call_error": None}
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


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""


def _mock_backend(prompt, model, **params):
    return {"text": "pass", "model": model, "backend": "mock",
            "model_call_error": None}


def _setup(tmp_path, monkeypatch, gen_mode, overall, tracker_raise):
    repo = tmp_path / "repo"
    repo.mkdir()
    for slug, body in FAKES.items():
        d = repo / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(
            COMMON + "\n" + body, encoding="utf-8")
    comp_dir = repo / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (repo / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8")

    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("GATE_TEST_LOG", str(log))
    monkeypatch.setenv("GATE_TEST_GEN_MODE", gen_mode)
    monkeypatch.setenv("GATE_TEST_VERIFY_OVERALL", overall)
    monkeypatch.setenv("GATE_TEST_TRACKER_RAISE", "1" if tracker_raise else "0")
    monkeypatch.chdir(tmp_path)
    return repo, log


def _read_log(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _run(repo):
    return component_gate_runner.run_component_gates(
        "comp-foo", repo, "mock-model", seed=0, llm_backend=_mock_backend,
        retry_feedback=None,
    )


def test_write_attempt_record_called_once_after_both_scans(tmp_path, monkeypatch):
    repo, log = _setup(tmp_path, monkeypatch, "files", "fail", False)
    _run(repo)

    entries = _read_log(log)
    calls = [e["call"] for e in entries]

    war_idx = [i for i, c in enumerate(calls) if c == "write_attempt_record"]
    assert len(war_idx) == 1, calls
    w = war_idx[0]

    gen_entries = [e for e in entries if e["call"] == "generate"]
    verify_entries = [e for e in entries if e["call"] == "verify"]
    assert len(gen_entries) == 1, calls
    assert len(verify_entries) == 1, calls
    assert "license_scan" in calls and "secret_scan" in calls, calls

    # after generation, verification, and both scans
    assert calls.index("generate") < w
    assert calls.index("verify") < w
    assert max(i for i, c in enumerate(calls) if c == "license_scan") < w
    assert max(i for i, c in enumerate(calls) if c == "secret_scan") < w

    rec = entries[w]
    assert rec["component_id"] == "comp-foo"
    # the generator's result, in full
    assert rec["generation_result"] == gen_entries[0]["result"]
    assert rec["generation_result"]["files"] == {
        "foo.py": "def double(x):\n    return 2 * x\n"}
    # verify's report, in full
    assert rec["verification_is_none"] is False
    assert rec["verification_report"] == verify_entries[0]["report"]
    assert rec["verification_report"]["overall"] == "fail"
    # the provenance key's spec_bundle_hash
    assert rec["spec_bundle_hash"] == "sha256:k"


def test_write_attempt_record_receives_none_on_model_call_error(tmp_path, monkeypatch):
    repo, log = _setup(tmp_path, monkeypatch, "error", "pass", False)
    _run(repo)

    entries = _read_log(log)
    calls = [e["call"] for e in entries]
    recs = [e for e in entries if e["call"] == "write_attempt_record"]
    assert len(recs) == 1, calls
    rec = recs[0]
    assert rec["verification_is_none"] is True
    assert rec["verification_report"] is None
    assert rec["generation_result"]["model_call_error"] is not None


def test_write_attempt_record_exception_does_not_change_result(tmp_path, monkeypatch):
    repo, log = _setup(tmp_path, monkeypatch, "files", "pass", True)

    result = _run(repo)

    calls = [e["call"] for e in _read_log(log)]
    assert calls.count("write_attempt_record") == 1, calls
    assert field(result, "blocked") is False