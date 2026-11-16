"""AC-GATE-006 (Covers: R-GATE-006).

On a non-sealed provenance miss whose generation produced files,
run_component_gates invokes provenance-writer's write_provenance exactly
once, after verification, both scans and the attempt record, with a
plain-dict ProvenanceInputs built from the same provenance key and the
faked dependencies' own results. On a model_call_error, write_provenance
is never called.
"""

import json
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG"
MODE_ENV = "GATE_TEST_GEN_MODE"

COMPONENT_ID = "comp-foo"
SLUG = "foo"
SPEC_HASH = "sha256:0123abcd"
GATE_VERSIONS = {"verifier": "v@1"}

GEN_PASS = {
    "component_id": COMPONENT_ID,
    "spec_bundle_hash": SPEC_HASH,
    "model": "mock-model",
    "prompt_version": "v10",
    "cache_hit": False,
    "files": {"foo.py": "def double(x):\n    return 2 * x\n"},
    "model_call_error": None,
    "refused": None,
    "retry_feedback": None,
}

GEN_ERROR = {
    "component_id": COMPONENT_ID,
    "spec_bundle_hash": SPEC_HASH,
    "model": "mock-model",
    "prompt_version": "v10",
    "cache_hit": False,
    "files": {},
    "model_call_error": {"category": "network", "message": "mock network failure"},
    "refused": None,
    "retry_feedback": None,
}

REPORT = {
    "component_id": COMPONENT_ID,
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "overall": "pass",
}

LICENSE = {
    "component_id": COMPONENT_ID,
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

SECRET = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


PRELUDE = '''
import copy
import dataclasses
import json
import os
from pathlib import Path


def _log(event, **data):
    record = {"event": event}
    record.update(data)
    with open(os.environ["GATE_TEST_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def _plain(v):
    if v is None or isinstance(v, (bool, str, int, float)):
        return v
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if hasattr(v, "to_dict"):
        return _plain(v.to_dict())
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return _plain(dataclasses.asdict(v))
    if hasattr(v, "__dict__"):
        return _plain(vars(v))
    return repr(v)
'''


def _provenance_checker_src():
    return PRELUDE + '''

GATE_VERSIONS = ''' + repr(GATE_VERSIONS) + '''
SPEC_HASH = ''' + repr(SPEC_HASH) + '''


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return ProvenanceKey(SPEC_HASH, dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash, gate_versions=_plain(gate_versions))
    return {"hit": False, "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {"hit": False, "sealed": False, "reason": "not_sealed",
            "verification_report": None, "license_scan": None,
            "secret_scan": None, "owners": None, "source_hash": None,
            "written_at": None}
'''


def _assembler_src():
    return PRELUDE + '''

SPEC_HASH = ''' + repr(SPEC_HASH) + '''


class SpecBundle:
    FIELDS = ("component_id", "spec_bundle_hash", "spec", "interface",
              "constraints", "dependency_interfaces", "dependency_context",
              "dependency_usage", "vars", "glossary", "hint_code")

    def __init__(self, component_id):
        self.component_id = component_id
        self.spec_bundle_hash = SPEC_HASH
        self.spec = "Foo doubles a number."
        self.interface = "double(x: int) -> int"
        self.constraints = "None."
        self.dependency_interfaces = {}
        self.dependency_context = {}
        self.dependency_usage = {}
        self.vars = {}
        self.glossary = ""
        self.hint_code = None

    def __getitem__(self, key):
        if key not in self.FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default) if key in self.FIELDS else default


class CriterionBundle:
    FIELDS = ("component_id", "criterion_id", "covers", "criterion_text",
              "requirement_text", "interface", "glossary",
              "dependency_interfaces")

    def __init__(self, component_id, criterion_id):
        self.component_id = component_id
        self.criterion_id = criterion_id
        self.covers = "R-FOO-001"
        self.criterion_text = "Given x = 2 When double(x) is called Then it returns 4"
        self.requirement_text = "double(x) MUST return 2 * x."
        self.interface = "double(x: int) -> int"
        self.glossary = ""
        self.dependency_interfaces = {}

    def __getitem__(self, key):
        if key not in self.FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default) if key in self.FIELDS else default


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return SpecBundle(component_id)


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return CriterionBundle(component_id, criterion_id)
'''


def _generator_src():
    return PRELUDE + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"

GEN_PASS = ''' + repr(GEN_PASS) + '''
GEN_ERROR = ''' + repr(GEN_ERROR) + '''


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", model=model)
    if os.environ.get("GATE_TEST_GEN_MODE") == "error":
        return copy.deepcopy(GEN_ERROR)
    return copy.deepcopy(GEN_PASS)
'''


def _verifier_src():
    return PRELUDE + '''

GATE_VERSION = "verifier-orchestrator@2.0.0"

REPORT = ''' + repr(REPORT) + '''


class VerificationReport:
    FIELDS = ("component_id", "criteria", "requirement_results",
              "interface_drift", "mutation_score", "overall")

    def __init__(self, data):
        for key in self.FIELDS:
            setattr(self, key, copy.deepcopy(data[key]))

    def to_dict(self):
        return {key: copy.deepcopy(getattr(self, key)) for key in self.FIELDS}


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return VerificationReport(REPORT)
'''


def _license_src():
    return PRELUDE + '''

LICENSE = ''' + repr(LICENSE) + '''


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
    return copy.deepcopy(LICENSE)


def gate_version(repo_root):
    return LICENSE["gate_version"]
'''


def _secret_src():
    return PRELUDE + '''

SECRET = ''' + repr(SECRET) + '''


class AllowlistInvalidError(Exception):
    pass


class SecretScanResult:
    FIELDS = ("scope", "gate_version", "flagged", "matches", "allowed",
              "unused_allowlist_entries", "notified",
              "notification_delivery_error", "cache_hit")

    def __init__(self, data):
        for key in self.FIELDS:
            setattr(self, key, copy.deepcopy(data[key]))

    def to_dict(self):
        return {key: copy.deepcopy(getattr(self, key)) for key in self.FIELDS}


def scan(repo_root):
    _log("secret_scan")
    return SecretScanResult(SECRET)


def scan_files(paths, repo_root=None):
    data = copy.deepcopy(SECRET)
    data["scope"] = "precommit"
    return SecretScanResult(data)


def gate_version(repo_root):
    return SECRET["gate_version"]


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


def _tracker_src():
    return PRELUDE + '''


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash,
         verification_is_none=verification_report is None)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    attempt_id = "2026-11-15T00:00:00Z-a1b2c3"
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    (attempts_dir / "2026-11-15T00-00-00Z-a1b2c3.json").write_text(
        json.dumps(record), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []


def main(argv):
    return 0
'''


def _writer_src():
    return PRELUDE + '''


class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / "foo"
    files_now = len([p for p in attempts_dir.iterdir()]) if attempts_dir.is_dir() else 0
    _log("write_provenance", component_id=component_id,
         inputs_is_dict=isinstance(inputs, dict),
         attempts_type=(type(inputs.get("attempts")).__name__
                        if isinstance(inputs, dict) else None),
         attempt_files_at_call=files_now,
         inputs=_plain(inputs))
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None


def main(argv):
    return 0
'''


def _test_author_src():
    return PRELUDE + '''

GATE_VERSION = "generated_test@1.0.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model)
    return {"component_id": "comp-foo", "criterion_id": "AC-FOO-001",
            "model": model, "seed": seed, "prompt_version": "v1",
            "cache_hit": False, "file": None,
            "model_call_error": {"category": "network", "message": "unused"}}
'''


def _llm_endpoint_src():
    return PRELUDE + '''

DEFAULT_TIMEOUT_SECONDS = 600


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "mock",
            "model_call_error": None}
'''


FAKES = {
    "provenance-checker": _provenance_checker_src,
    "spec-bundle-assembler": _assembler_src,
    "generator": _generator_src,
    "verifier-orchestrator": _verifier_src,
    "license-scanner": _license_src,
    "secret-scanner": _secret_src,
    "provenance-tracker": _tracker_src,
    "provenance-writer": _writer_src,
    "test-author": _test_author_src,
    "llm-endpoint": _llm_endpoint_src,
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for slug, src in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(src(), encoding="utf-8")
    comp_dir = repo_root / "specs" / "components" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv(MODE_ENV, raising=False)
    return repo_root, log_path


def read_log(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_write_provenance_called_once_after_scans_and_attempt_record(repo):
    repo_root, log_path = repo
    attempts_dir = repo_root / ".hotdocs" / "attempts" / SLUG
    assert not attempts_dir.exists()

    component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "mock-model", seed=0
    )

    events = read_log(log_path)
    names = [e["event"] for e in events]

    writes = [e for e in events if e["event"] == "write_provenance"]
    assert len(writes) == 1, names
    write_idx = names.index("write_provenance")

    for earlier in ("verify", "license_scan", "secret_scan", "write_attempt_record"):
        assert earlier in names, (earlier, names)
        assert names.index(earlier) < write_idx, (earlier, names)
        assert all(i < write_idx for i, n in enumerate(names) if n == earlier), names

    w = writes[0]
    assert w["component_id"] == COMPONENT_ID
    assert w["inputs_is_dict"] is True
    inputs = w["inputs"]

    assert inputs["component_id"] == COMPONENT_ID
    assert inputs["gate_versions"] == {"verifier": "v@1"}
    assert inputs["provenance_hit"] is False
    assert w["attempts_type"] == "int"
    assert inputs["attempts"] == 1
    assert w["attempt_files_at_call"] == 1

    assert inputs["generation_result"] == GEN_PASS
    assert inputs["verification_report"] == REPORT
    assert inputs["license_scan_result"] == LICENSE
    assert inputs["secret_scan_result"] == SECRET


def test_model_call_error_never_writes_provenance(repo, monkeypatch):
    repo_root, log_path = repo
    monkeypatch.setenv(MODE_ENV, "error")

    component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "mock-model", seed=0
    )

    events = read_log(log_path)
    names = [e["event"] for e in events]

    assert "generate" in names, names
    assert "write_provenance" not in names, names