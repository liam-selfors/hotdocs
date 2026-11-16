import json
import os
from pathlib import Path

import pytest

import component_gate_runner


COMPONENT_ID = "comp-widget"
SLUG = "widget"
LOG_ENV = "GATE_TEST_LOG_DIR"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_LOG = '''
import json as _json
import os as _os
from pathlib import Path as _Path


def _log(name, record):
    log_dir = _Path(_os.environ["GATE_TEST_LOG_DIR"])
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / (name + ".jsonl"), "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(record, default=str) + "\\n")
'''


PROVENANCE_CHECKER = COMMON_LOG + '''

class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", {"component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", {"component_id": component_id})
    return ProvenanceKey(
        "sha256:abc123",
        {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", {"component_id": component_id})
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", {"component_id": component_id})
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


SPEC_BUNDLE_ASSEMBLER = COMMON_LOG + '''

class SpecBundle:
    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )

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


class CriterionBundle:
    _FIELDS = (
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary", "dependency_interfaces",
    )

    def __init__(self, **kw):
        for name in self._FIELDS:
            setattr(self, name, kw.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._FIELDS else default


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", {"component_id": component_id, "mode": mode})
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:abc123",
        spec="Widget spec.",
        interface="widget_fn(x: int) -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", {"component_id": component_id, "criterion_id": criterion_id})
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-WIDGET-001",
        criterion_text="Given x When y Then z",
        requirement_text="R-WIDGET-001",
        interface="widget_fn(x: int) -> int",
        glossary="",
        dependency_interfaces={},
    )
'''


GENERATOR = COMMON_LOG + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


class GenerationResult:
    _FIELDS = (
        "component_id", "spec_bundle_hash", "model", "prompt_version",
        "cache_hit", "files", "model_call_error", "refused", "retry_feedback",
    )

    def __init__(self, **kw):
        for name in self._FIELDS:
            setattr(self, name, kw.get(name))

    def to_dict(self):
        return {name: getattr(self, name) for name in self._FIELDS}

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._FIELDS else default


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        cid = bundle.get("component_id")
        sbh = bundle.get("spec_bundle_hash")
    else:
        cid = getattr(bundle, "component_id", None)
        sbh = getattr(bundle, "spec_bundle_hash", None)
    _log("generate", {
        "component_id": cid,
        "model": model,
        "retry_feedback": retry_feedback,
    })
    return GenerationResult(
        component_id=cid,
        spec_bundle_hash=sbh,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"widget.py": "def widget_fn(x):\\n    return x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR = COMMON_LOG + '''

GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    _FIELDS = (
        "component_id", "criteria", "requirement_results",
        "interface_drift", "mutation_score", "overall",
    )

    def __init__(self, **kw):
        for name in self._FIELDS:
            setattr(self, name, kw.get(name))

    def to_dict(self):
        return {name: getattr(self, name) for name in self._FIELDS}


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", {"component_id": component_id})
    return VerificationReport(
        component_id=component_id,
        criteria=[
            {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001",
             "kind": "compiled", "result": "pass"},
        ],
        requirement_results={"R-WIDGET-001": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        overall="pass",
    )
'''


LICENSE_SCANNER = COMMON_LOG + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("license_scan", {"component_id": component_id})
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


SECRET_SCANNER = COMMON_LOG + '''

class AllowlistInvalidError(Exception):
    pass


class SecretScanResult:
    _FIELDS = (
        "scope", "gate_version", "flagged", "matches", "allowed",
        "unused_allowlist_entries", "notified", "notification_delivery_error",
        "cache_hit",
    )

    def __init__(self, **kw):
        for name in self._FIELDS:
            setattr(self, name, kw.get(name))

    def to_dict(self):
        return {name: getattr(self, name) for name in self._FIELDS}


def _result(scope):
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


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def scan(repo_root):
    _log("secret_scan", {})
    return _result("full")


def scan_files(paths, repo_root=None):
    _log("secret_scan_files", {})
    return _result("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = COMMON_LOG + '''

def _plain(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(vars(value))


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", {"component_id": component_id})
    slug = component_id[5:] if component_id.startswith("comp-") else component_id
    attempts = _Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts.mkdir(parents=True, exist_ok=True)
    n = len(list(attempts.iterdir()))
    attempt_id = "2026-11-15T00:00:00Z-%06d" % n
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    (attempts / (attempt_id + ".json")).write_text(
        _json.dumps(record, default=str), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER = COMMON_LOG + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", {"component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", {"component_id": component_id})
    return None
'''


TEST_AUTHOR = COMMON_LOG + '''

GATE_VERSION = "generated_test@1.0.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", {"model": model, "seed": seed})
    return {
        "component_id": "comp-widget",
        "criterion_id": "AC-WIDGET-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/widget/generated-test/test_ac_widget_001.py",
                 "content": "def test_ok():\\n    assert True\\n"},
        "model_call_error": None,
    }
'''


LLM_ENDPOINT = COMMON_LOG + '''

DEFAULT_TIMEOUT_SECONDS = 600


def complete(prompt, model, *, backend=None, **params):
    _log("complete", {"model": model})
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
id: comp-widget
title: Widget
status: draft
owners: [team-a]
depends_on: []
---

# Widget

## Purpose

Widget returns its input.
"""


def _write_fixture(repo_root: Path):
    comp_dir = repo_root / "specs" / "components" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")


def _read_log(log_dir: Path, name: str):
    path = log_dir / (name + ".jsonl")
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_gate_003a_single_generator_call_passing_candidate(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    _write_fixture(repo_root)
    monkeypatch.setenv(LOG_ENV, str(log_dir))
    monkeypatch.chdir(tmp_path)

    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "mock:model-x"
    )

    # The provenance check ran and was a miss (precondition sanity).
    assert len(_read_log(log_dir, "check_provenance")) == 1

    # generator called exactly once.
    gen_calls = _read_log(log_dir, "generate")
    assert len(gen_calls) == 1, gen_calls

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None

    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"