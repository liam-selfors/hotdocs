import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_GATE_TEST_LOG"
REPORT_ENV = "HOTDOCS_GATE_TEST_HIT_REPORT"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = '''import dataclasses
import json
import os
from pathlib import Path

_MODULE = "@@MODULE@@"


def _log(func, **kwargs):
    path = os.environ["HOTDOCS_GATE_TEST_LOG"]
    record = {"module": _MODULE, "func": func, "args": kwargs}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str, sort_keys=True) + "\\n")


def _plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


class _Mapping:
    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def to_dict(self):
        return dataclasses.asdict(self)


def _license_scan():
    return {
        "component_id": "comp-foo",
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


def _secret_scan():
    return {
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

'''


PROVENANCE_CHECKER = '''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def to_dict(self):
        return {"spec_bundle_hash": self.spec_bundle_hash, "gate_versions": dict(self.gate_versions)}


class SealedKey:
    def __init__(self, owners, source_path, source_hash, verifier_version):
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return ProvenanceKey("sha256:k", {"verifier": "v@1"})


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        "check_provenance",
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        gate_versions=gate_versions,
    )
    return {
        "hit": True,
        "verification_report": json.loads(os.environ["HOTDOCS_GATE_TEST_HIT_REPORT"]),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
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


SPEC_BUNDLE_ASSEMBLER = '''
@dataclasses.dataclass
class SpecBundle(_Mapping):
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


@dataclasses.dataclass
class CriterionBundle(_Mapping):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:k",
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


GENERATOR = '''
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


@dataclasses.dataclass
class GenerationResult(_Mapping):
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
    _log("generate", model=model, retry_feedback=retry_feedback)
    if isinstance(bundle, dict):
        sbh = bundle.get("spec_bundle_hash")
        cid = bundle.get("component_id", "comp-foo")
    else:
        sbh = getattr(bundle, "spec_bundle_hash", None)
        cid = getattr(bundle, "component_id", "comp-foo")
    return GenerationResult(
        component_id=cid,
        spec_bundle_hash=sbh,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={},
        model_call_error={"category": "network", "message": "fake network failure"},
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR = '''
GATE_VERSION = "verifier-orchestrator@2.0.0"


@dataclasses.dataclass
class VerificationReport(_Mapping):
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: object
    overall: str


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return VerificationReport(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        overall="pass",
    )
'''


LICENSE_SCANNER = '''
def scan(component_id, repo_root):
    _log("scan", component_id=component_id)
    return _license_scan()


def gate_version(repo_root):
    _log("gate_version")
    return "license_scanner@4.0.0-no-reference-corpus"
'''


SECRET_SCANNER = '''
class AllowlistInvalidError(Exception):
    pass


@dataclasses.dataclass
class SecretScanResult(_Mapping):
    scope: str
    gate_version: str
    flagged: bool
    matches: list
    allowed: list
    unused_allowlist_entries: list
    notified: bool
    notification_delivery_error: object
    cache_hit: bool


def _result(scope):
    data = _secret_scan()
    data["scope"] = scope
    return SecretScanResult(**data)


def scan(repo_root):
    _log("scan")
    return _result("full")


def scan_files(paths, repo_root=None):
    _log("scan_files")
    return _result("precommit")


def gate_version(repo_root):
    _log("gate_version")
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def propose(repo_root):
    _log("propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id, spec_bundle_hash=spec_bundle_hash)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    stamp = "2026-11-15T00:00:00Z"
    record = {
        "attempt_id": stamp + "-a1b2c3",
        "component_id": component_id,
        "timestamp": stamp,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": None if verification_report is None else _plain(verification_report),
    }
    for name in {slug, component_id}:
        directory = Path(repo_root) / ".hotdocs" / "attempts" / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / (record["attempt_id"].replace(":", "-") + ".json")).write_text(
            json.dumps(record, default=str), encoding="utf-8"
        )
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures", component_id=component_id)
    return []
'''


PROVENANCE_WRITER = '''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


@dataclasses.dataclass
class SealedProvenanceInputs(_Mapping):
    component_id: str
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str
    verification_report: object


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''


TEST_AUTHOR = '''
def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model, seed=seed)
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/foo/generated-test/test_ac_foo_001.py",
            "content": "def test_placeholder():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
'''


LLM_ENDPOINT = '''
def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "fake", "model_call_error": None}
'''


FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER,
    ("generator", "generator"): GENERATOR,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_ORCHESTRATOR,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER,
    ("test-author", "test_author"): TEST_AUTHOR,
    ("llm-endpoint", "llm_endpoint"): LLM_ENDPOINT,
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

GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

LIBRARY_MD = """# Library

```
foo(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""


def hit_report(overall):
    result = "pass" if overall == "pass" else "fail"
    criterion = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": result}
    if result == "fail":
        criterion["failure_detail"] = {"message": "foo(2) equals 4 failed", "expected": 4, "actual": 3}
    return {
        "component_id": "comp-foo",
        "criteria": [criterion],
        "requirement_results": {"R-FOO-001": result},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": overall,
    }


def build_repo(tmp_path, monkeypatch, overall):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD, encoding="utf-8")
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD, encoding="utf-8")
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD, encoding="utf-8")
    (comp_dir / "interface" / "library.md").write_text(LIBRARY_MD, encoding="utf-8")
    (comp_dir / "constraints.md").write_text(CONSTRAINTS_MD, encoding="utf-8")

    for (slug, module_name), body in FAKES.items():
        directory = repo_root / "gen" / slug
        directory.mkdir(parents=True, exist_ok=True)
        source = PRELUDE.replace("@@MODULE@@", module_name) + body
        (directory / (module_name + ".py")).write_text(source, encoding="utf-8")

    log_path = tmp_path / "invocations.log"
    log_path.write_text("", encoding="utf-8")
    report = hit_report(overall)
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.setenv(REPORT_ENV, json.dumps(report))
    monkeypatch.chdir(repo_root)
    return repo_root, log_path, report


def read_log(log_path):
    lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_passing_hit_short_circuits(tmp_path, monkeypatch):
    repo_root, log_path, report = build_repo(tmp_path, monkeypatch, "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = read_log(log_path)

    checks = [e for e in entries if e["module"] == "provenance_checker" and e["func"] == "check_provenance"]
    assert len(checks) == 1, entries
    assert checks[0]["args"]["spec_bundle_hash"] == "sha256:k"
    assert checks[0]["args"]["gate_versions"] == {"verifier": "v@1"}

    other_modules = sorted({e["module"] for e in entries if e["module"] != "provenance_checker"})
    assert other_modules == [], entries
    checker_funcs = {e["func"] for e in entries if e["module"] == "provenance_checker"}
    assert checker_funcs <= {"current_sealed_key", "current_provenance_key", "check_provenance"}, entries

    assert field(result, "provenance_hit") is True
    assert field(result, "blocked") is False
    assert field(result, "verification") == report


def test_failed_hit_proceeds_as_miss(tmp_path, monkeypatch):
    repo_root, log_path, _report = build_repo(tmp_path, monkeypatch, "fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = read_log(log_path)
    generator_calls = [e for e in entries if e["module"] == "generator" and e["func"] == "generate"]
    assert len(generator_calls) == 1, entries

    assert field(result, "provenance_hit") is False