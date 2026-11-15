"""AC-GATE-004 (Covers: R-GATE-004).

Scenario 1: a provenance miss and a faked generator returning a
model_call_error -> verify is never called and block_reason is
"model_call_error".

Scenario 2: a provenance miss, one generated file, and verify returning
overall "fail" -> block_reason is "verification_failed" and
model_call_error is null.
"""

import json
from pathlib import Path

import pytest

import component_gate_runner


SLUG = "widget"
COMPONENT_ID = "comp-widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Fake dependency sources. Every fake records its invocations to the file
# named by the GATE_TEST_LOG environment variable (never an in-process list,
# never a literal temporary path embedded in the fake).
# ---------------------------------------------------------------------------

COMMON = '''
import json
import os


def _log(dep, fn):
    path = os.environ["GATE_TEST_LOG"]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"dep": dep, "fn": fn}) + "\\n")


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)
'''


PROVENANCE_CHECKER = COMMON + '''

SPEC_HASH = "sha256:" + "0" * 64

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
        return {
            "spec_bundle_hash": self.spec_bundle_hash,
            "gate_versions": dict(self.gate_versions),
        }


class SealedKey:
    def __init__(self, owners, source_path, source_hash, verifier_version):
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version

    def to_dict(self):
        return {
            "owners": list(self.owners),
            "source_path": self.source_path,
            "source_hash": self.source_hash,
            "verifier_version": self.verifier_version,
        }


def current_sealed_key(component_id, repo_root):
    _log("provenance-checker", "current_sealed_key")
    return None


def current_provenance_key(component_id, repo_root):
    _log("provenance-checker", "current_provenance_key")
    return ProvenanceKey(SPEC_HASH, dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("provenance-checker", "check_provenance")
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("provenance-checker", "check_sealed_provenance")
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


SPEC_BUNDLE_ASSEMBLER = COMMON + '''

SPEC_HASH = "sha256:" + "0" * 64


class _MappingMixin:
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


class SpecBundle(_MappingMixin):
    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )

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


class CriterionBundle(_MappingMixin):
    _FIELDS = (
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary", "dependency_interfaces",
    )

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
    _log("spec-bundle-assembler", "assemble")
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash=SPEC_HASH,
        spec="# Widget\\n\\nWidget doubles a number.",
        interface="# Library\\n\\ndouble(x: int) -> int",
        constraints="None.",
        glossary="- **Widget** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("spec-bundle-assembler", "assemble_criterion")
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-WIDGET-001",
        criterion_text="Given x = 2 When double(x) is called Then it returns 4",
        requirement_text="double(x) MUST return 2 * x.",
        interface="# Library\\n\\ndouble(x: int) -> int",
        glossary="- **Widget** - a test term.",
    )
'''


GENERATOR = COMMON + '''
from pathlib import Path

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


class GenerationResult:
    _FIELDS = (
        "component_id", "spec_bundle_hash", "model", "prompt_version",
        "cache_hit", "files", "model_call_error", "refused", "retry_feedback",
    )

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

    def to_dict(self):
        return {k: getattr(self, k) for k in self._FIELDS}


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generator", "generate")
    scenario = os.environ["GATE_TEST_SCENARIO"]
    component_id = _get(bundle, "component_id")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    if scenario == "model_call_error":
        return GenerationResult(
            component_id=component_id,
            spec_bundle_hash=spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files={},
            model_call_error={"category": "network", "message": "connection refused"},
            refused=None,
            retry_feedback=retry_feedback,
        )
    files = {"widget.py": "def double(x):\\n    return 2 * x\\n"}
    if repo_root is not None:
        slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
        out = Path(repo_root) / "gen" / slug
        out.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            (out / rel).write_text(content, encoding="utf-8")
    return GenerationResult(
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files=files,
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR = COMMON + '''

GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    _FIELDS = (
        "component_id", "criteria", "requirement_results", "interface_drift",
        "mutation_score", "overall",
    )

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
    _log("verifier-orchestrator", "verify")
    return VerificationReport(
        component_id=component_id,
        criteria=[
            {
                "id": "AC-WIDGET-001",
                "covers": "R-WIDGET-001",
                "kind": "generated-test",
                "result": "fail",
                "failure_detail": {
                    "message": "double(2) equals 4 failed",
                    "expected": 4,
                    "actual": 3,
                },
            }
        ],
        requirement_results={"R-WIDGET-001": "fail"},
        interface_drift=False,
        mutation_score=0.5,
        overall="fail",
    )
'''


LICENSE_SCANNER = COMMON + '''

_GV = "license_scanner@4.0.0-no-reference-corpus"


def gate_version(repo_root):
    _log("license-scanner", "gate_version")
    return _GV


def scan(component_id, repo_root):
    _log("license-scanner", "scan")
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


SECRET_SCANNER = COMMON + '''

_GV = "secret_scanner@0.0.0"


class AllowlistInvalidError(Exception):
    pass


class SecretScanResult:
    _FIELDS = (
        "scope", "gate_version", "flagged", "matches", "allowed",
        "unused_allowlist_entries", "notified", "notification_delivery_error",
        "cache_hit",
    )

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


def scan(repo_root):
    _log("secret-scanner", "scan")
    return _clean("full")


def scan_files(paths, repo_root=None):
    _log("secret-scanner", "scan_files")
    return _clean("precommit")


def gate_version(repo_root):
    _log("secret-scanner", "gate_version")
    return _GV


def propose(repo_root):
    _log("secret-scanner", "propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = COMMON + '''
import dataclasses
from datetime import datetime, timezone
from pathlib import Path


def _plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if dataclasses.is_dataclass(value):
        return _plain(dataclasses.asdict(value))
    return _plain(vars(value))


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("provenance-tracker", "write_attempt_record")
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    out = Path(repo_root) / ".hotdocs" / "attempts" / slug
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = ts + "-" + format(len(list(out.iterdir())), "06d")
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": ts,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    (out / (attempt_id.replace(":", "-") + ".json")).write_text(
        json.dumps(record), encoding="utf-8"
    )
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("provenance-tracker", "check_readiness")
    return {
        "scope": "blast-radius" if changed_ids else "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    _log("provenance-tracker", "last_requirement_failures")
    return []
'''


PROVENANCE_WRITER = COMMON + '''


class MissingInputError(Exception):
    pass


class InvalidSealedInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("provenance-writer", "write_provenance")
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("provenance-writer", "write_sealed_provenance")
    return None
'''


TEST_AUTHOR = COMMON + '''


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("test-author", "author_test")
    criterion_id = _get(bundle, "criterion_id")
    return {
        "component_id": _get(bundle, "component_id"),
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/widget/generated-test/test_ac_widget_001.py",
            "content": "def test_placeholder():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
'''


LLM_ENDPOINT = COMMON + '''


def complete(prompt, model, *, backend=None, **params):
    _log("llm-endpoint", "complete")
    return {
        "text": "pass",
        "model": model,
        "backend": "fake",
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
id: comp-widget
title: Widget
status: draft
owners: [team-a]
depends_on: []
---

# Widget

## Purpose

Widget doubles a number.
"""

GLOSSARY_MD = """# Glossary

- **Widget** — a test term.
"""

REQUIREMENT_MD = """# R-WIDGET-001

**R-WIDGET-001** — `double(x)` MUST return `2 * x`.
"""

ACCEPTANCE_MD = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: generated-test

```gherkin
Given x = 2
When double(x) is called
Then it returns 4
```
"""

LIBRARY_MD = """# Library

```
double(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""


def _build_repo(repo_root: Path) -> None:
    specs = repo_root / "specs"
    comp = specs / "components" / SLUG
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (specs / "glossary.md").write_text(GLOSSARY_MD, encoding="utf-8")
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-WIDGET-001.md").write_text(REQUIREMENT_MD, encoding="utf-8")
    (comp / "acceptance" / "AC-WIDGET-001.md").write_text(ACCEPTANCE_MD, encoding="utf-8")
    (comp / "interface" / "library.md").write_text(LIBRARY_MD, encoding="utf-8")
    (comp / "constraints.md").write_text(CONSTRAINTS_MD, encoding="utf-8")

    for dep_slug, source in FAKES.items():
        module_name = dep_slug.replace("-", "_")
        dep_dir = repo_root / "gen" / dep_slug
        dep_dir.mkdir(parents=True, exist_ok=True)
        (dep_dir / f"{module_name}.py").write_text(source, encoding="utf-8")


def _read_calls(log_path: Path):
    if not log_path.exists():
        return []
    calls = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entry = json.loads(line)
            calls.append((entry["dep"], entry["fn"]))
    return calls


@pytest.fixture
def setup_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    monkeypatch.chdir(repo_root)
    return repo_root, log_path


def test_model_call_error_blocks_without_calling_verify(setup_repo, monkeypatch):
    repo_root, log_path = setup_repo
    monkeypatch.setenv("GATE_TEST_SCENARIO", "model_call_error")

    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "fake-model", seed=0
    )

    calls = _read_calls(log_path)
    # The faked dependencies were actually used: provenance was a miss and
    # generation was attempted exactly once.
    assert ("provenance-checker", "check_provenance") in calls
    assert calls.count(("generator", "generate")) == 1

    # Then: verify was never called ...
    assert ("verifier-orchestrator", "verify") not in calls

    # ... and block_reason is "model_call_error".
    assert field(result, "block_reason") == "model_call_error"
    assert field(result, "blocked") is True
    assert field(result, "provenance_hit") is False
    assert field(result, "verification") is None
    mce = field(result, "model_call_error")
    assert mce is not None
    assert field(mce, "category") == "network"


def test_verification_failure_blocks_with_verification_failed(setup_repo, monkeypatch):
    repo_root, log_path = setup_repo
    monkeypatch.setenv("GATE_TEST_SCENARIO", "candidate")

    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "fake-model", seed=0
    )

    calls = _read_calls(log_path)
    assert ("provenance-checker", "check_provenance") in calls
    assert calls.count(("generator", "generate")) == 1
    assert calls.count(("verifier-orchestrator", "verify")) == 1

    # Then: block_reason is "verification_failed" and model_call_error is null.
    assert field(result, "block_reason") == "verification_failed"
    assert field(result, "model_call_error") is None
    assert field(result, "blocked") is True
    assert field(result, "provenance_hit") is False
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "fail"