import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_RUNNER_TEST_INVOCATION_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


_LOG_HELPER = '''
import json as _json
import os as _os


def _log(name, **data):
    path = _os.environ["GATE_RUNNER_TEST_INVOCATION_LOG"]
    rec = {"call": name}
    rec.update(data)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(rec, default=str) + "\\n")


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    try:
        return value[name]
    except Exception:
        return getattr(value, name, default)
'''


_PROVENANCE_CHECKER = _LOG_HELPER + '''

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

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class SealedKey:
    def __init__(self, owners, source_path, source_hash, verifier_version):
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return ProvenanceKey("sha256:" + "0" * 64, dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash)
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


_SPEC_BUNDLE_ASSEMBLER = _LOG_HELPER + '''
import uuid
from dataclasses import dataclass, field


class _MappingMixin:
    def __getitem__(self, key):
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self.__dataclass_fields__:
            return default
        return getattr(self, key)

    def keys(self):
        return list(self.__dataclass_fields__)

    def __contains__(self, key):
        return key in self.__dataclass_fields__


@dataclass
class SpecBundle(_MappingMixin):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None


@dataclass
class CriterionBundle(_MappingMixin):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)


def assemble(component_id, repo_root, mode="cold"):
    marker = uuid.uuid4().hex
    bundle_hash = "sha256:" + marker + marker
    spec_text = "Foo doubles a number. bundle-marker-" + marker
    _log("assemble", component_id=component_id, mode=mode,
         spec_bundle_hash=bundle_hash, spec=spec_text)
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash=bundle_hash,
        spec=spec_text,
        interface="foo(x: int) -> int",
        constraints="None.",
        glossary="- **Foo** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id,
         criterion_id=criterion_id)
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


_GENERATOR = _LOG_HELPER + '''
from dataclasses import dataclass

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


@dataclass
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
    bundle_hash = _get(bundle, "spec_bundle_hash")
    bundle_spec = _get(bundle, "spec")
    bundle_component_id = _get(bundle, "component_id")
    _log("generate", bundle_hash=bundle_hash, bundle_spec=bundle_spec,
         bundle_component_id=bundle_component_id, model=model,
         retry_feedback=retry_feedback)
    return GenerationResult(
        component_id=bundle_component_id,
        spec_bundle_hash=bundle_hash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "VALUE = 1"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


_VERIFIER_ORCHESTRATOR = _LOG_HELPER + '''
import dataclasses
from dataclasses import dataclass, field

GATE_VERSION = "verifier-orchestrator@2.0.0"


@dataclass
class VerificationReport:
    component_id: str
    criteria: list = field(default_factory=list)
    requirement_results: dict = field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: object = None
    overall: str = "pass"

    def to_dict(self):
        return dataclasses.asdict(self)


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id,
         judge_callable=callable(judge),
         test_author_callable=callable(test_author))
    return VerificationReport(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-001", "covers": "R-FOO-001",
                   "kind": "generated-test", "result": "pass"}],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=None,
        overall="pass",
    )
'''


_LICENSE_SCANNER = _LOG_HELPER + '''

GATE = "license_scanner@4.0.0-no-reference-corpus"


def gate_version(repo_root):
    return GATE


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
    return {
        "component_id": component_id,
        "gate_version": GATE,
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


_SECRET_SCANNER = _LOG_HELPER + '''
import dataclasses
from dataclasses import dataclass, field

GATE = "secret_scanner@0.0.0"


class AllowlistInvalidError(Exception):
    pass


@dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool = False
    matches: list = field(default_factory=list)
    allowed: list = field(default_factory=list)
    unused_allowlist_entries: list = field(default_factory=list)
    notified: bool = False
    notification_delivery_error: object = None
    cache_hit: bool = False

    def to_dict(self):
        return dataclasses.asdict(self)


def gate_version(repo_root):
    return GATE


def scan(repo_root):
    _log("secret_scan")
    return SecretScanResult(scope="full", gate_version=GATE)


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    return SecretScanResult(scope="precommit", gate_version=GATE)


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


_PROVENANCE_TRACKER = _LOG_HELPER + '''
import dataclasses
import uuid
from pathlib import Path


def _plain(value):
    if value is None or isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    return dict(vars(value))


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    slug = component_id[5:] if component_id.startswith("comp-") else component_id
    attempt_id = "2026-11-15T00:00:00Z-" + uuid.uuid4().hex[:6]
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    out_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / (attempt_id.replace(":", "-") + ".json")).write_text(
        _json.dumps(record, default=str), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


_PROVENANCE_WRITER = _LOG_HELPER + '''


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


_TEST_AUTHOR = _LOG_HELPER + '''


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model, seed=seed)
    criterion_id = _get(bundle, "criterion_id") or "AC-FOO-001"
    component_id = _get(bundle, "component_id") or "comp-foo"
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py",
                 "content": "def test_placeholder():\\n    assert True\\n"},
        "model_call_error": None,
    }
'''


_LLM_ENDPOINT = _LOG_HELPER + '''

DEFAULT_TIMEOUT_SECONDS = 600
PROVIDERS = {}


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "fake",
            "model_call_error": None}


def parse_model(model):
    return (None, model)


def resolve_provider(model, config=None):
    return {"provider": None, "model": model, "base_url": None,
            "api_key_env": None, "timeout_seconds": DEFAULT_TIMEOUT_SECONDS}
'''


_FAKES = {
    "provenance-checker": _PROVENANCE_CHECKER,
    "spec-bundle-assembler": _SPEC_BUNDLE_ASSEMBLER,
    "generator": _GENERATOR,
    "verifier-orchestrator": _VERIFIER_ORCHESTRATOR,
    "license-scanner": _LICENSE_SCANNER,
    "secret-scanner": _SECRET_SCANNER,
    "provenance-tracker": _PROVENANCE_TRACKER,
    "provenance-writer": _PROVENANCE_WRITER,
    "test-author": _TEST_AUTHOR,
    "llm-endpoint": _LLM_ENDPOINT,
}


def _write_fakes(repo_root):
    for slug, source in _FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")


_COMPONENT_MD = """---
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

_GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

_REQUIREMENT = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

_ACCEPTANCE = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

_LIBRARY = """# Library

```
foo(x: int) -> int
```
"""

_CONSTRAINTS = """# Constraints

None.
"""


def _write_fixture(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(_GLOSSARY, encoding="utf-8")
    (comp / "component.md").write_text(_COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(_REQUIREMENT, encoding="utf-8")
    (comp / "acceptance" / "AC-FOO-001.md").write_text(_ACCEPTANCE, encoding="utf-8")
    (comp / "interface" / "library.md").write_text(_LIBRARY, encoding="utf-8")
    (comp / "constraints.md").write_text(_CONSTRAINTS, encoding="utf-8")


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
    _write_fixture(repo_root)
    _write_fakes(repo_root)

    log_path = tmp_path / "invocations.jsonl"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.chdir(tmp_path)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", retry_feedback=["R-FOO-002"]
    )

    records = _read_log(log_path)
    interesting = [r for r in records if r["call"] in ("assemble", "generate", "verify")]
    names = [r["call"] for r in interesting]

    # Order: assemble, then generate, then verify.
    assert names == ["assemble", "generate", "verify"], names

    assemble_rec = interesting[0]
    generate_rec = interesting[1]

    # assemble received mode "cold".
    assert assemble_rec["mode"] == "cold"
    assert assemble_rec["component_id"] == "comp-foo"

    # generate received the assembled bundle (identified by its unique marker).
    assert generate_rec["bundle_hash"] == assemble_rec["spec_bundle_hash"]
    assert generate_rec["bundle_spec"] == assemble_rec["spec"]
    assert generate_rec["bundle_component_id"] == "comp-foo"

    # generate received model "m" and the retry feedback unchanged.
    assert generate_rec["model"] == "m"
    assert generate_rec["retry_feedback"] == ["R-FOO-002"]

    # Sanity: it was a miss, not a short-circuiting hit.
    assert field(result, "provenance_hit") is False