import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "HOTDOCS_GATE_TEST_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


_LOG_HELPER = '''
import json as _json
import os as _os


def _log(call, **kw):
    path = _os.environ.get("HOTDOCS_GATE_TEST_LOG")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps({"call": call, **kw}, default=str) + "\\n")
'''


PROVENANCE_CHECKER_SRC = _LOG_HELPER + '''

HIT = __HIT__


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
}


def current_sealed_key(component_id, repo_root):
    _log("provenance_checker.current_sealed_key", component_id=component_id, repo_root=str(repo_root))
    return None


def current_provenance_key(component_id, repo_root):
    _log("provenance_checker.current_provenance_key", component_id=component_id, repo_root=str(repo_root))
    return ProvenanceKey("sha256:abc123", dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("provenance_checker.check_provenance", component_id=component_id, repo_root=str(repo_root))
    if HIT:
        return {
            "hit": True,
            "verification_report": {
                "component_id": component_id,
                "criteria": [],
                "requirement_results": {},
                "interface_drift": False,
                "mutation_score": 0.9,
                "overall": "pass",
            },
            "license_scan": {
                "component_id": component_id,
                "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
                "evaluated": True,
                "reason": None,
                "similarity_score": 0.01,
                "block_threshold": 0.7,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
            "secret_scan": {
                "scope": "full",
                "gate_version": "secret_scanner@0.0.0",
                "flagged": False,
                "matches": [],
                "allowed": [],
                "unused_allowlist_entries": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
        }
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("provenance_checker.check_sealed_provenance", component_id=component_id, repo_root=str(repo_root))
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

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]


def assemble(component_id, repo_root, mode="cold"):
    _log("spec_bundle_assembler.assemble", component_id=component_id, repo_root=str(repo_root), mode=mode)
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:abc123",
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        glossary="- **Foo** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("spec_bundle_assembler.assemble_criterion", component_id=component_id, criterion_id=criterion_id)
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


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generator.generate", model=model, repo_root=str(repo_root))
    return GenerationResult(
        component_id=_get(bundle, "component_id"),
        spec_bundle_hash=_get(bundle, "spec_bundle_hash"),
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={},
        model_call_error={"category": "network", "message": "simulated network failure"},
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR_SRC = _LOG_HELPER + '''
import dataclasses

GATE_VERSION = "verifier-orchestrator@2.0.0"


@dataclasses.dataclass
class VerificationReport:
    component_id: str
    criteria: list = dataclasses.field(default_factory=list)
    requirement_results: dict = dataclasses.field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: object = None
    overall: str = "pass"

    def to_dict(self):
        return dataclasses.asdict(self)


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verifier_orchestrator.verify", component_id=component_id, repo_root=str(repo_root))
    return VerificationReport(component_id=component_id, overall="pass")
'''


LICENSE_SCANNER_SRC = _LOG_HELPER + '''

def gate_version(repo_root):
    return "license_scanner@4.0.3+9f2c41ab07de"


def scan(component_id, repo_root):
    _log("license_scanner.scan", component_id=component_id, repo_root=str(repo_root))
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.123,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''


SECRET_SCANNER_SRC = _LOG_HELPER + '''
import dataclasses


class AllowlistInvalidError(Exception):
    pass


@dataclasses.dataclass
class SecretScanResult:
    scope: str = "full"
    gate_version: str = "secret_scanner@3.1.0+detect-secrets.1.5.0"
    flagged: bool = False
    matches: list = dataclasses.field(default_factory=list)
    allowed: list = dataclasses.field(default_factory=list)
    unused_allowlist_entries: list = dataclasses.field(default_factory=list)
    notified: bool = False
    notification_delivery_error: object = None
    cache_hit: bool = False

    def to_dict(self):
        return dataclasses.asdict(self)


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def scan(repo_root):
    _log("secret_scanner.scan", repo_root=str(repo_root))
    return SecretScanResult(
        scope="full",
        gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
        flagged=False,
        matches=[],
        allowed=[{"rule_id": "Keyword", "file": "verification/foo/test_x.py", "line": 7}],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def scan_files(paths, repo_root=None):
    _log("secret_scanner.scan_files", repo_root=str(repo_root))
    return SecretScanResult(scope="precommit", cache_hit=False)


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER_SRC = _LOG_HELPER + '''
import dataclasses
import datetime
import uuid
from pathlib import Path


def _plain(value):
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return dict(vars(value))


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("provenance_tracker.write_attempt_record", component_id=component_id, repo_root=str(repo_root))
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = now + "-" + uuid.uuid4().hex[:6]
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": now,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    out = Path(repo_root) / ".hotdocs" / "attempts" / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / (attempt_id + ".json")).write_text(_json.dumps(record, default=str), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER_SRC = _LOG_HELPER + '''
import dataclasses


class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


@dataclasses.dataclass
class SealedProvenanceInputs:
    component_id: str
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str
    verification_report: object


def write_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_provenance", component_id=component_id, repo_root=str(repo_root))
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_sealed_provenance", component_id=component_id, repo_root=str(repo_root))
    return None
'''


TEST_AUTHOR_SRC = _LOG_HELPER + '''
GATE_VERSION = "generated_test@1.0.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("test_author.author_test", model=model, seed=seed, repo_root=str(repo_root))
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": "network", "message": "not available"},
    }
'''


LLM_ENDPOINT_SRC = _LOG_HELPER + '''
DEFAULT_TIMEOUT_SECONDS = 600


def complete(prompt, model, *, backend=None, **params):
    _log("llm_endpoint.complete", model=model)
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}


def parse_model(model):
    return (None, model)


def resolve_provider(model, config=None):
    return {"provider": None, "model": model, "base_url": None, "api_key_env": None,
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS}
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root, hit):
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md",
           "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n")
    _write(comp / "acceptance" / "AC-FOO-001.md",
           "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
           "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n")
    _write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    gen = repo_root / "gen"
    fakes = {
        ("provenance-checker", "provenance_checker"):
            PROVENANCE_CHECKER_SRC.replace("__HIT__", "True" if hit else "False"),
        ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER_SRC,
        ("generator", "generator"): GENERATOR_SRC,
        ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_ORCHESTRATOR_SRC,
        ("license-scanner", "license_scanner"): LICENSE_SCANNER_SRC,
        ("secret-scanner", "secret_scanner"): SECRET_SCANNER_SRC,
        ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER_SRC,
        ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER_SRC,
        ("test-author", "test_author"): TEST_AUTHOR_SRC,
        ("llm-endpoint", "llm_endpoint"): LLM_ENDPOINT_SRC,
    }
    for (slug, module_name), src in fakes.items():
        _write(gen / slug / (module_name + ".py"), src)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def _mock_backend(prompt, model, **params):
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}


def test_miss_with_model_call_error_still_runs_both_scanners(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    _build_repo(repo_root, hit=False)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "test-model", seed=0, llm_backend=_mock_backend, retry_feedback=None,
    )

    calls = _read_log(log_path)
    gen_calls = [c for c in calls if c["call"] == "generator.generate"]
    assert gen_calls, "the faked generator was never invoked; calls: %r" % calls

    license_calls = [c for c in calls if c["call"] == "license_scanner.scan"]
    secret_calls = [c for c in calls if c["call"] == "secret_scanner.scan"]

    assert license_calls, "license-scanner's scan was not called; calls: %r" % calls
    assert any(
        c["component_id"] == "comp-foo" and _same_path(c["repo_root"], repo_root)
        for c in license_calls
    ), license_calls

    assert secret_calls, "secret-scanner's scan was not called; calls: %r" % calls
    assert any(_same_path(c["repo_root"], repo_root) for c in secret_calls), secret_calls

    license_scan = field(result, "license_scan")
    secret_scan = field(result, "secret_scan")
    assert license_scan is not None
    assert secret_scan is not None

    assert field(license_scan, "component_id") == "comp-foo"
    assert field(license_scan, "similarity_score") == 0.123
    assert field(license_scan, "gate_version") == "license_scanner@4.0.3+9f2c41ab07de"
    assert field(license_scan, "evaluated") is True
    assert field(license_scan, "blocked") is False

    assert field(secret_scan, "scope") == "full"
    assert field(secret_scan, "gate_version") == "secret_scanner@3.1.0+detect-secrets.1.5.0"
    assert field(secret_scan, "flagged") is False
    allowed = field(secret_scan, "allowed")
    assert len(allowed) == 1
    assert field(allowed[0], "line") == 7
    assert field(allowed[0], "file") == "verification/foo/test_x.py"


def test_short_circuiting_hit_calls_neither_scanner(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    _build_repo(repo_root, hit=True)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "test-model", seed=0, llm_backend=_mock_backend, retry_feedback=None,
    )

    calls = _read_log(log_path)
    assert any(c["call"] == "provenance_checker.check_provenance" for c in calls), (
        "the faked provenance-checker was never consulted; calls: %r" % calls
    )
    assert field(result, "provenance_hit") is True

    assert not [c for c in calls if c["call"] == "license_scanner.scan"], calls
    assert not [c for c in calls if c["call"] == "secret_scanner.scan"], calls
    assert not [c for c in calls if c["call"] == "secret_scanner.scan_files"], calls