"""AC-GATE-003b (Covers: R-GATE-003).

Given a provenance miss, a faked generator returning one file, and a faked
verify returning overall "fail" with requirement_results
{"R-FOO-001": "pass", "R-FOO-002": "fail"}, when run_component_gates is
called without retry_feedback, then generator was called exactly once, with
retry_feedback None, and blocked is true with block_reason
"verification_failed".
"""

import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "FAKE_GATE_RUNNER_CALL_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_HEADER = '''import json
import os
from pathlib import Path


def _log(call, **kw):
    path = os.environ.get("FAKE_GATE_RUNNER_CALL_LOG")
    if not path:
        return
    rec = {"call": call}
    rec.update(kw)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\\n")
'''


GATE_VERSIONS_LITERAL = '''{
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}'''

SPEC_HASH = "sha256:" + "ab" * 32


PROVENANCE_CHECKER = COMMON_HEADER + '''

SPEC_HASH = "''' + SPEC_HASH + '''"
GATE_VERSIONS = ''' + GATE_VERSIONS_LITERAL + '''


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return ProvenanceKey(SPEC_HASH, dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id)
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
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


SPEC_BUNDLE_ASSEMBLER = COMMON_HEADER + '''
import dataclasses

SPEC_HASH = "''' + SPEC_HASH + '''"


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
        if key not in {f.name for f in dataclasses.fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

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
        if key not in {f.name for f in dataclasses.fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash=SPEC_HASH,
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        glossary="- **Foo** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
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


GENERATOR = COMMON_HEADER + '''
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
    _log("generate", model=model, retry_feedback=retry_feedback)
    return GenerationResult(
        component_id=_get(bundle, "component_id"),
        spec_bundle_hash=_get(bundle, "spec_bundle_hash"),
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR = COMMON_HEADER + '''
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
    _log("verify", component_id=component_id)
    return VerificationReport(
        component_id=component_id,
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "result equals 4 failed", "expected": 4, "actual": 3},
            },
        ],
        requirement_results={"R-FOO-001": "pass", "R-FOO-002": "fail"},
        interface_drift=False,
        mutation_score=0.5,
        overall="fail",
    )
'''


LICENSE_SCANNER = COMMON_HEADER + '''

_GV = "license_scanner@4.0.0-no-reference-corpus"


def gate_version(repo_root):
    return _GV


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
    return {
        "component_id": component_id,
        "gate_version": _GV,
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


SECRET_SCANNER = COMMON_HEADER + '''
import dataclasses

_GV = "secret_scanner@0.0.0"


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
        gate_version=_GV,
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def gate_version(repo_root):
    return _GV


def scan(repo_root):
    _log("secret_scan")
    return _clean("full")


def scan_files(paths, repo_root=None):
    return _clean("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = COMMON_HEADER + '''
import dataclasses
from datetime import datetime, timezone


def _plain(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    return dict(vars(value))


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    ts = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempt_dir.mkdir(parents=True, exist_ok=True)
    n = len(list(attempt_dir.iterdir()))
    attempt_id = ts + "-" + str(n)
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": ts,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    (attempt_dir / (attempt_id.replace(":", "") + ".json")).write_text(
        json.dumps(record, default=str), encoding="utf-8"
    )
    return record


def last_requirement_failures(component_id, repo_root):
    return []


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "whole-corpus" if changed_ids is None else "blast-radius",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }
'''


PROVENANCE_WRITER = COMMON_HEADER + '''


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


TEST_AUTHOR = COMMON_HEADER + '''

GATE_VERSION = "generated_test@1.0.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model, seed=seed)
    cid = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
    comp = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    slug = comp[len("comp-"):] if comp.startswith("comp-") else comp
    return {
        "component_id": comp,
        "criterion_id": cid,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/" + slug + "/generated-test/test_" + cid.lower().replace("-", "_") + ".py",
            "content": "def test_placeholder():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
'''


LLM_ENDPOINT = COMMON_HEADER + '''

DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {
        "text": "pass",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
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
sealed: false
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""


def _write_fixture(repo_root: Path) -> None:
    for slug, source in FAKES.items():
        module_name = slug.replace("-", "_")
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(source, encoding="utf-8")

    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
        encoding="utf-8",
    )
    (comp / "requirements" / "R-FOO-002.md").write_text(
        "# R-FOO-002\n\n**R-FOO-002** — `foo(0)` MUST return `0`.\n",
        encoding="utf-8",
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
        encoding="utf-8",
    )
    (comp / "acceptance" / "AC-FOO-002.md").write_text(
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "```gherkin\nGiven x = 0\nWhen foo(x) is called\nThen it returns 0\n```\n",
        encoding="utf-8",
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def test_ac_gate_003b_single_generator_call_no_feedback_blocks_on_failed_verification(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    log_path = tmp_path / "calls.jsonl"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.chdir(repo_root)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock-model"
    )

    calls = _read_log(log_path)

    # The provenance check ran and missed, so the generation path was taken.
    assert any(c["call"] == "check_provenance" for c in calls), calls

    generate_calls = [c for c in calls if c["call"] == "generate"]
    assert len(generate_calls) == 1, generate_calls
    assert generate_calls[0]["retry_feedback"] is None

    # The produced candidate was verified (one file -> verify runs).
    assert any(c["call"] == "verify" for c in calls), calls

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"
    assert field(result, "provenance_hit") is False
    assert field(result, "model_call_error") is None

    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "fail"