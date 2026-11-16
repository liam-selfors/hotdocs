import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_RUNNER_TEST_INVOCATION_LOG"

BUNDLE_HASH = "sha256:b0b0b0b0"
KEY_HASH = "sha256:a1a1a1a1"
BUNDLE_SPEC_MARKER = "assembled-bundle-marker-ac-gate-002b"


_LOG_HELPER = '''
import json
import os


def _log(record):
    path = os.environ["GATE_RUNNER_TEST_INVOCATION_LOG"]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def _field(value, name):
    if isinstance(value, dict):
        return value[name]
    return getattr(value, name)
'''


PROVENANCE_CHECKER_SRC = _LOG_HELPER + '''

class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def current_sealed_key(component_id, repo_root):
    _log({"call": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"call": "current_provenance_key", "component_id": component_id})
    return ProvenanceKey(
        "''' + KEY_HASH + '''",
        {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({"call": "check_provenance", "component_id": component_id})
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log({"call": "check_sealed_provenance", "component_id": component_id})
    return {
        "hit": False,
        "sealed": False,
        "reason": "not_sealed",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }
'''


SPEC_BUNDLE_ASSEMBLER_SRC = _LOG_HELPER + '''
import dataclasses


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
    _log({"call": "assemble", "component_id": component_id, "mode": mode})
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="''' + BUNDLE_HASH + '''",
        spec="''' + BUNDLE_SPEC_MARKER + '''",
        interface="# Library",
        constraints="None.",
        glossary="- **Foo** - a test term.",
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({"call": "assemble_criterion", "component_id": component_id,
          "criterion_id": criterion_id})
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x When y Then z",
        requirement_text="R-FOO-001",
        interface="# Library",
        glossary="",
    )
'''


GENERATOR_SRC = _LOG_HELPER + '''
import dataclasses

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

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    if bundle is None:
        bundle_hash = None
        bundle_component = None
        bundle_spec = None
    else:
        bundle_hash = _field(bundle, "spec_bundle_hash")
        bundle_component = _field(bundle, "component_id")
        bundle_spec = _field(bundle, "spec")
    _log({
        "call": "generate",
        "bundle_spec_bundle_hash": bundle_hash,
        "bundle_component_id": bundle_component,
        "bundle_spec": bundle_spec,
        "model": model,
        "retry_feedback": list(retry_feedback) if retry_feedback is not None else None,
    })
    return GenerationResult(
        component_id=bundle_component,
        spec_bundle_hash=bundle_hash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def double(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=list(retry_feedback) if retry_feedback is not None else None,
    )
'''


VERIFIER_ORCHESTRATOR_SRC = _LOG_HELPER + '''
import dataclasses

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
        return {
            "component_id": self.component_id,
            "criteria": [dict(c) for c in self.criteria],
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }


def verify(component_id, repo_root, judge=None, test_author=None):
    _log({
        "call": "verify",
        "component_id": component_id,
        "judge_callable": callable(judge),
        "test_author_callable": callable(test_author),
    })
    return VerificationReport(
        component_id=component_id,
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
             "result": "pass"},
        ],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        overall="pass",
    )
'''


LICENSE_SCANNER_SRC = _LOG_HELPER + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log({"call": "license_scan", "component_id": component_id})
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


SECRET_SCANNER_SRC = _LOG_HELPER + '''
import dataclasses


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
        return {
            "scope": self.scope,
            "gate_version": self.gate_version,
            "flagged": self.flagged,
            "matches": list(self.matches),
            "allowed": list(self.allowed),
            "unused_allowlist_entries": list(self.unused_allowlist_entries),
            "notified": self.notified,
            "notification_delivery_error": self.notification_delivery_error,
            "cache_hit": self.cache_hit,
        }


class AllowlistInvalidError(Exception):
    pass


def _clean(scope):
    return SecretScanResult(
        scope=scope,
        gate_version="secret_scanner@0.0.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def scan(repo_root):
    _log({"call": "secret_scan"})
    return _clean("full")


def scan_files(paths, repo_root=None):
    _log({"call": "secret_scan_files"})
    return _clean("precommit")


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER_SRC = _LOG_HELPER + '''
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log({"call": "write_attempt_record", "component_id": component_id})
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    existing = len([p for p in attempts_dir.iterdir() if p.is_file()])
    attempt_id = "2026-11-15T00:00:0%dZ-fake" % existing
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": None if verification_report is None else {},
    }
    (attempts_dir / (attempt_id + ".json")).write_text(
        json.dumps(record), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER_SRC = _LOG_HELPER + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log({"call": "write_provenance", "component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log({"call": "write_sealed_provenance", "component_id": component_id})
    return None
'''


TEST_AUTHOR_SRC = _LOG_HELPER + '''

def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log({"call": "author_test", "model": model, "seed": seed})
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


LLM_ENDPOINT_SRC = _LOG_HELPER + '''

def complete(prompt, model, *, backend=None, **params):
    _log({"call": "complete", "model": model})
    return {
        "text": "pass",
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }
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


def _write_fakes(repo_root):
    for slug, src in FAKES.items():
        module_name = slug.replace("-", "_")
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(src, encoding="utf-8")


def _read_log(path):
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def test_ac_gate_002b_miss_calls_assemble_generate_verify_in_order(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    _write_fakes(repo_root)

    log_path = tmp_path / "invocations.jsonl"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", retry_feedback=["R-FOO-002"]
    )

    records = _read_log(log_path)
    calls = [r["call"] for r in records]

    # Precondition: this really was a provenance miss on a non-sealed component.
    assert "check_provenance" in calls, calls

    relevant = [c for c in calls if c in ("assemble", "generate", "verify")]
    assert relevant == ["assemble", "generate", "verify"], calls

    assemble_rec = next(r for r in records if r["call"] == "assemble")
    assert assemble_rec["mode"] == "cold"
    assert assemble_rec["component_id"] == "comp-foo"

    generate_rec = next(r for r in records if r["call"] == "generate")
    # generate received the bundle assemble returned (not e.g. the provenance key's hash)
    assert generate_rec["bundle_spec_bundle_hash"] == BUNDLE_HASH
    assert generate_rec["bundle_component_id"] == "comp-foo"
    assert generate_rec["bundle_spec"] == BUNDLE_SPEC_MARKER
    assert generate_rec["model"] == "m"
    assert generate_rec["retry_feedback"] == ["R-FOO-002"]