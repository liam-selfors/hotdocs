"""AC-GATE-003c (Covers: R-GATE-003).

Given a provenance miss and a faked generator returning empty files and
model_call_error {"category": "timeout", "message": "t"}, when
run_component_gates is called, then generator was called exactly once,
blocked is true with block_reason "model_call_error", model_call_error is
that error, and verification is null.
"""

import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_RUNNER_AC_003C_LOG_DIR"

EXPECTED_ERROR = {"category": "timeout", "message": "t"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_LOG_HELPER = '''
import json as _json
import os as _os
from pathlib import Path as _Path


def _log(name, record):
    log_dir = _os.environ.get("GATE_RUNNER_AC_003C_LOG_DIR")
    if not log_dir:
        return
    p = _Path(log_dir) / (name + ".log")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(record, default=str) + "\\n")
'''


PROVENANCE_CHECKER_SRC = COMMON_LOG_HELPER + '''

class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def to_dict(self):
        return {"spec_bundle_hash": self.spec_bundle_hash,
                "gate_versions": dict(self.gate_versions)}


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", {"component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", {"component_id": component_id})
    return ProvenanceKey(
        "sha256:" + "ab" * 32,
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


SPEC_BUNDLE_ASSEMBLER_SRC = COMMON_LOG_HELPER + '''

class _Bundle:
    _FIELDS = ()

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._FIELDS:
            return default
        return getattr(self, key)

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def to_dict(self):
        return {k: getattr(self, k) for k in self._FIELDS}


class SpecBundle(_Bundle):
    _FIELDS = ("component_id", "spec_bundle_hash", "spec", "interface",
               "constraints", "dependency_interfaces", "dependency_context",
               "dependency_usage", "vars", "glossary", "hint_code")

    def __init__(self, component_id, spec_bundle_hash, spec, interface,
                 constraints, dependency_interfaces=None,
                 dependency_context=None, dependency_usage=None, vars=None,
                 glossary="", hint_code=None):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.spec = spec
        self.interface = interface
        self.constraints = constraints
        self.dependency_interfaces = dependency_interfaces or {}
        self.dependency_context = dependency_context or {}
        self.dependency_usage = dependency_usage or {}
        self.vars = vars or {}
        self.glossary = glossary
        self.hint_code = hint_code


class CriterionBundle(_Bundle):
    _FIELDS = ("component_id", "criterion_id", "covers", "criterion_text",
               "requirement_text", "interface", "glossary",
               "dependency_interfaces")

    def __init__(self, component_id, criterion_id, covers, criterion_text,
                 requirement_text, interface, glossary,
                 dependency_interfaces=None):
        self.component_id = component_id
        self.criterion_id = criterion_id
        self.covers = covers
        self.criterion_text = criterion_text
        self.requirement_text = requirement_text
        self.interface = interface
        self.glossary = glossary
        self.dependency_interfaces = dependency_interfaces or {}


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", {"component_id": component_id, "mode": mode})
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        glossary="- **Foo** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", {"component_id": component_id,
                                "criterion_id": criterion_id})
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x = 2 When foo(x) is called Then it returns 4",
        requirement_text="foo(x) MUST return 2 * x.",
        interface="foo(x: int) -> int",
        glossary="- **Foo** - a test term.",
    )
'''


GENERATOR_SRC = COMMON_LOG_HELPER + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


class GenerationResult:
    _FIELDS = ("component_id", "spec_bundle_hash", "model", "prompt_version",
               "cache_hit", "files", "model_call_error", "refused",
               "retry_feedback")

    def __init__(self, component_id, spec_bundle_hash, model, prompt_version,
                 cache_hit, files, model_call_error, refused, retry_feedback):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.model = model
        self.prompt_version = prompt_version
        self.cache_hit = cache_hit
        self.files = files
        self.model_call_error = model_call_error
        self.refused = refused
        self.retry_feedback = retry_feedback

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._FIELDS:
            return default
        return getattr(self, key)

    def to_dict(self):
        return {k: getattr(self, k) for k in self._FIELDS}


def generate(bundle, model, retry_feedback=None, *, repo_root=None,
             llm_backend=None):
    component_id = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    spec_bundle_hash = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash")
    _log("generate", {
        "component_id": component_id,
        "model": model,
        "retry_feedback": retry_feedback,
    })
    return GenerationResult(
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={},
        model_call_error={"category": "timeout", "message": "t"},
        refused=None,
        retry_feedback=list(retry_feedback) if retry_feedback is not None else None,
    )
'''


VERIFIER_ORCHESTRATOR_SRC = COMMON_LOG_HELPER + '''

GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    _FIELDS = ("component_id", "criteria", "requirement_results",
               "interface_drift", "mutation_score", "overall")

    def __init__(self, component_id, criteria, requirement_results,
                 interface_drift, mutation_score, overall):
        self.component_id = component_id
        self.criteria = criteria
        self.requirement_results = requirement_results
        self.interface_drift = interface_drift
        self.mutation_score = mutation_score
        self.overall = overall

    def to_dict(self):
        return {k: getattr(self, k) for k in self._FIELDS}


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", {"component_id": component_id})
    return VerificationReport(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-001", "covers": "R-FOO-001",
                   "kind": "generated-test", "result": "pass"}],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=1.0,
        overall="pass",
    )
'''


LICENSE_SCANNER_SRC = COMMON_LOG_HELPER + '''

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


SECRET_SCANNER_SRC = COMMON_LOG_HELPER + '''

class SecretScanResult:
    _FIELDS = ("scope", "gate_version", "flagged", "matches", "allowed",
               "unused_allowlist_entries", "notified",
               "notification_delivery_error", "cache_hit")

    def __init__(self, scope, gate_version, flagged, matches, allowed,
                 unused_allowlist_entries, notified,
                 notification_delivery_error, cache_hit):
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
        return {k: getattr(self, k) for k in self._FIELDS}


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


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def scan(repo_root):
    _log("secret_scan", {})
    return _clean("full")


def scan_files(paths, repo_root=None):
    return _clean("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER_SRC = COMMON_LOG_HELPER + '''

import datetime as _dt
import uuid as _uuid


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
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = ts + "-" + _uuid.uuid4().hex[:6]
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": ts,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    d = _Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (attempt_id.replace(":", "-") + ".json")).write_text(
        _json.dumps(record, default=str), encoding="utf-8")
    return record


def last_requirement_failures(component_id, repo_root):
    return []


def check_readiness(repo_root, changed_ids=None, model=None, seed=0,
                    llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}
'''


PROVENANCE_WRITER_SRC = COMMON_LOG_HELPER + '''

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


TEST_AUTHOR_SRC = COMMON_LOG_HELPER + '''

GATE_VERSION = "generated_test@1.0.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", {"model": model, "seed": seed})
    criterion_id = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
    component_id = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": "network", "message": "fake"},
    }
'''


LLM_ENDPOINT_SRC = COMMON_LOG_HELPER + '''

DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log("complete", {"model": model})
    return {
        "text": None,
        "model": model,
        "backend": "fake",
        "model_call_error": {"category": "network", "message": "fake"},
    }
'''


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


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _plant_fakes(repo_root):
    fakes = {
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
    for slug, src in fakes.items():
        module_name = slug.replace("-", "_")
        _write(repo_root / "gen" / slug / (module_name + ".py"), src)


def _read_log(log_dir, name):
    p = log_dir / (name + ".log")
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _as_plain(value):
    if value is None or isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(vars(value))


def test_ac_gate_003c_model_call_error_single_generator_call(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    repo_root.mkdir()
    log_dir.mkdir()
    monkeypatch.setenv(LOG_ENV, str(log_dir))
    monkeypatch.chdir(repo_root)

    _write(repo_root / "specs" / "components" / "foo" / "component.md", COMPONENT_MD)
    _plant_fakes(repo_root)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "fake-model", seed=0,
    )

    # Precondition: this was a provenance miss on a non-sealed component.
    assert len(_read_log(log_dir, "check_provenance")) == 1

    # generator was called exactly once.
    generate_calls = _read_log(log_dir, "generate")
    assert len(generate_calls) == 1, generate_calls

    # blocked is true with block_reason "model_call_error".
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "model_call_error"

    # model_call_error is that error.
    assert _as_plain(field(result, "model_call_error")) == EXPECTED_ERROR

    # verification is null.
    assert field(result, "verification") is None