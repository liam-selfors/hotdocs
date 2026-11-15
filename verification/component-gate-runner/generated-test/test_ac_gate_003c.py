import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_TEST_INVOCATION_LOG"

ERROR = {"category": "timeout", "message": "t"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = '''
import json as _json
import os as _os


def _log(record):
    path = _os.environ.get("GATE_TEST_INVOCATION_LOG")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(record) + "\\n")
'''


PROVENANCE_CHECKER = LOG_HELPER + '''

class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log({"fn": "provenance_checker.current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"fn": "provenance_checker.current_provenance_key", "component_id": component_id})
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
    _log({"fn": "provenance_checker.check_provenance", "component_id": component_id})
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log({"fn": "provenance_checker.check_sealed_provenance", "component_id": component_id})
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


SPEC_BUNDLE_ASSEMBLER = LOG_HELPER + '''
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


def assemble(component_id, repo_root, mode="cold"):
    _log({"fn": "spec_bundle_assembler.assemble", "component_id": component_id, "mode": mode})
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
    _log({"fn": "spec_bundle_assembler.assemble_criterion", "component_id": component_id})
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x\\nWhen y\\nThen z",
        requirement_text="R-FOO-001",
        interface="foo(x: int) -> int",
        glossary="",
    )
'''


GENERATOR = LOG_HELPER + '''
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

    def to_dict(self):
        return dataclasses.asdict(self)


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log({
        "fn": "generator.generate",
        "model": model,
        "retry_feedback": retry_feedback,
    })
    return GenerationResult(
        component_id=_get(bundle, "component_id"),
        spec_bundle_hash=_get(bundle, "spec_bundle_hash"),
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={},
        model_call_error={"category": "timeout", "message": "t"},
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR = LOG_HELPER + '''
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
        return dataclasses.asdict(self)


def verify(component_id, repo_root, judge=None, test_author=None):
    _log({"fn": "verifier_orchestrator.verify", "component_id": component_id})
    return VerificationReport(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=None,
        overall="pass",
    )
'''


LICENSE_SCANNER = LOG_HELPER + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log({"fn": "license_scanner.scan", "component_id": component_id})
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


SECRET_SCANNER = LOG_HELPER + '''
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
        return dataclasses.asdict(self)


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
    _log({"fn": "secret_scanner.scan"})
    return _clean("full")


def scan_files(paths, repo_root=None):
    _log({"fn": "secret_scanner.scan_files"})
    return _clean("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = LOG_HELPER + '''
from pathlib import Path as _Path


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log({"fn": "provenance_tracker.write_attempt_record", "component_id": component_id})
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    directory = _Path(repo_root) / ".hotdocs" / "attempts" / slug
    directory.mkdir(parents=True, exist_ok=True)
    index = len(list(directory.iterdir()))
    attempt_id = "2026-11-15T00:00:00Z-%06d" % index
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {
            "component_id": _get(generation_result, "component_id"),
            "files": dict(_get(generation_result, "files") or {}),
            "model_call_error": _get(generation_result, "model_call_error"),
        },
        "verification": None,
    }
    (directory / (attempt_id.replace(":", "-") + ".json")).write_text(_json.dumps(record), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER = LOG_HELPER + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log({"fn": "provenance_writer.write_provenance", "component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log({"fn": "provenance_writer.write_sealed_provenance", "component_id": component_id})
    return None
'''


TEST_AUTHOR = LOG_HELPER + '''

def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log({"fn": "test_author.author_test"})
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": "network", "message": "fake"},
    }
'''


LLM_ENDPOINT = LOG_HELPER + '''

DEFAULT_TIMEOUT_SECONDS = 600


def complete(prompt, model, *, backend=None, **params):
    _log({"fn": "llm_endpoint.complete"})
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


def _write_fixture(repo_root: Path):
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
        encoding="utf-8",
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
        encoding="utf-8",
    )
    (comp_dir / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (comp_dir / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** \u2014 a test term.\n", encoding="utf-8"
    )

    for slug, source in FAKES.items():
        module_name = slug.replace("-", "_")
        target = repo_root / "gen" / slug
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{module_name}.py").write_text(source, encoding="utf-8")


def _read_log(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fake_backend(prompt, model, **params):
    return {"text": "", "model": model, "backend": "mock", "model_call_error": None}


def test_ac_gate_003c_model_call_error_blocks_after_single_generator_call(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    log_path = tmp_path / "invocations.jsonl"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.chdir(tmp_path)

    result = component_gate_runner.run_component_gates(
        "comp-foo",
        repo_root,
        "mock-model",
        seed=0,
        llm_backend=_fake_backend,
        retry_feedback=None,
    )

    records = _read_log(log_path)
    generator_calls = [r for r in records if r["fn"] == "generator.generate"]
    assert len(generator_calls) == 1, f"generator called {len(generator_calls)} times: {records}"

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "model_call_error"

    mce = field(result, "model_call_error")
    assert mce is not None
    if isinstance(mce, dict):
        assert mce == ERROR
    else:
        assert field(mce, "category") == "timeout"
        assert field(mce, "message") == "t"

    assert field(result, "verification") is None