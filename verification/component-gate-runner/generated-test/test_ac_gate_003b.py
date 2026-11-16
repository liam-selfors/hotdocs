import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"
SLUG = "foo"
MODEL = "test-model"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PROVENANCE_CHECKER = '''
import json
from pathlib import Path


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def _log(repo_root, name):
    with open(Path(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name}) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log(repo_root, "current_sealed_key")
    return None


def current_provenance_key(component_id, repo_root):
    _log(repo_root, "current_provenance_key")
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
    _log(repo_root, "check_provenance")
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
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
import dataclasses
import json
from pathlib import Path


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
    with open(Path(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": "assemble", "mode": mode}) + "\\n")
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


GENERATOR = '''
import dataclasses
import json
from pathlib import Path

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
    with open(Path(repo_root) / "generator_calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"model": model, "retry_feedback": retry_feedback}) + "\\n")
    with open(Path(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": "generate"}) + "\\n")
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


VERIFIER_ORCHESTRATOR = '''
import dataclasses
import json
from pathlib import Path

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
    with open(Path(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": "verify"}) + "\\n")
    return VerificationReport(
        component_id=component_id,
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
             "failure_detail": {"message": "mismatch", "expected": 4, "actual": 3}},
        ],
        requirement_results={"R-FOO-001": "pass", "R-FOO-002": "fail"},
        interface_drift=False,
        mutation_score=0.5,
        overall="fail",
    )
'''


LICENSE_SCANNER = '''
import json
from pathlib import Path


def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    with open(Path(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": "license_scan"}) + "\\n")
    return {
        "component_id": component_id,
        "gate_version": gate_version(repo_root),
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


SECRET_SCANNER = '''
import dataclasses
import json
from pathlib import Path


class AllowlistInvalidError(Exception):
    pass


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


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


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
    with open(Path(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": "secret_scan"}) + "\\n")
    return _clean("full")


def scan_files(paths, repo_root=None):
    return _clean("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = '''
import dataclasses
import json
from pathlib import Path


def _plain(value):
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return dict(vars(value))


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    directory = Path(repo_root) / ".hotdocs" / "attempts" / slug
    directory.mkdir(parents=True, exist_ok=True)
    existing = len(list(directory.iterdir()))
    attempt_id = "2026-11-15T00:00:00Z-%06d" % existing
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    (directory / (attempt_id + ".json")).write_text(
        json.dumps(record, default=str), encoding="utf-8"
    )
    with open(Path(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": "write_attempt_record"}) + "\\n")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER = '''
import json
from pathlib import Path


class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    with open(Path(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": "write_provenance"}) + "\\n")
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    with open(Path(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": "write_sealed_provenance"}) + "\\n")
    return None
'''


TEST_AUTHOR = '''
def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
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


LLM_ENDPOINT = '''
def complete(prompt, model, *, backend=None, **params):
    return {
        "text": None,
        "model": model,
        "backend": "fake",
        "model_call_error": {"category": "network", "message": "fake"},
    }
'''


FAKES = {
    "provenance-checker": ("provenance_checker", PROVENANCE_CHECKER),
    "spec-bundle-assembler": ("spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER),
    "generator": ("generator", GENERATOR),
    "verifier-orchestrator": ("verifier_orchestrator", VERIFIER_ORCHESTRATOR),
    "license-scanner": ("license_scanner", LICENSE_SCANNER),
    "secret-scanner": ("secret_scanner", SECRET_SCANNER),
    "provenance-tracker": ("provenance_tracker", PROVENANCE_TRACKER),
    "provenance-writer": ("provenance_writer", PROVENANCE_WRITER),
    "test-author": ("test_author", TEST_AUTHOR),
    "llm-endpoint": ("llm_endpoint", LLM_ENDPOINT),
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


def _build_repo(repo_root: Path) -> None:
    for slug, (module_name, source) in FAKES.items():
        directory = repo_root / "gen" / slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{module_name}.py").write_text(source, encoding="utf-8")

    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    comp = repo_root / "specs" / "components" / SLUG
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
        encoding="utf-8",
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
        encoding="utf-8",
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")


def _read_jsonl(path: Path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_gate_003b_single_generator_call_without_retry_feedback_then_blocked(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    generator_calls = _read_jsonl(repo_root / "generator_calls.jsonl")
    assert len(generator_calls) == 1, generator_calls
    assert generator_calls[0]["retry_feedback"] is None

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"