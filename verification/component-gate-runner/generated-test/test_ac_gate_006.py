"""AC-GATE-006 (Covers: R-GATE-006).

On a non-sealed provenance miss whose generation produced files,
run_component_gates invokes provenance-writer's write_provenance once,
after verification, both scans and the attempt record, with
ProvenanceInputs built from the faked dependencies' own results and the
provenance key's gate_versions. On a model_call_error, write_provenance
is never called.
"""

import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"
SLUG = "foo"
GATE_VERSIONS = {"verifier": "v@1"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Shared helper code embedded at the top of every fake dependency module.
# Each fake logs to <repo_root>/test-log/calls.jsonl, so the log location is
# derived from the repo_root argument the fake is handed.
# ---------------------------------------------------------------------------

COMMON = '''
import dataclasses
import json
from pathlib import Path


def _norm(v):
    if not isinstance(v, (dict, list, tuple, str, int, float, bool, type(None))):
        to_dict = getattr(v, "to_dict", None)
        if callable(to_dict):
            v = to_dict()
        elif dataclasses.is_dataclass(v) and not isinstance(v, type):
            v = dataclasses.asdict(v)
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, Path):
        return str(v)
    if hasattr(v, "__dict__"):
        return _norm(vars(v))
    return str(v)


def _log_dir(repo_root):
    d = Path(repo_root) / "test-log"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log(repo_root, call, **data):
    entry = {"call": call}
    entry.update(data)
    with open(_log_dir(repo_root) / "calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\\n")


def _mode(repo_root):
    p = _log_dir(repo_root) / "mode.txt"
    return p.read_text(encoding="utf-8").strip() if p.is_file() else "pass"
'''


PROVENANCE_CHECKER = '''

@dataclasses.dataclass
class ProvenanceKey:
    spec_bundle_hash: str
    gate_versions: dict


@dataclasses.dataclass
class SealedKey:
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str


def current_sealed_key(component_id, repo_root):
    _log(repo_root, "current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log(repo_root, "current_provenance_key", component_id=component_id)
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "ab" * 32,
        gate_versions={"verifier": "v@1"},
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        repo_root,
        "check_provenance",
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        gate_versions=_norm(gate_versions),
    )
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log(repo_root, "check_sealed_provenance", component_id=component_id)
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
    _log(repo_root, "assemble", component_id=component_id, mode=mode)
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log(repo_root, "assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x = 2 When foo(x) is called Then it returns 4",
        requirement_text="foo(x) MUST return 2 * x.",
        interface="foo(x: int) -> int",
        glossary="",
    )
'''


GENERATOR = '''

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


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    sbh = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash")
    if _mode(repo_root) == "error":
        result = GenerationResult(
            component_id=component_id,
            spec_bundle_hash=sbh,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files={},
            model_call_error={"category": "network", "message": "connection refused"},
            refused=None,
            retry_feedback=retry_feedback,
        )
    else:
        files = {"foo.py": "def double(x):\\n    return 2 * x\\n"}
        out = Path(repo_root) / "gen" / "foo"
        out.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            (out / rel).write_text(content, encoding="utf-8")
        result = GenerationResult(
            component_id=component_id,
            spec_bundle_hash=sbh,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files=files,
            model_call_error=None,
            refused=None,
            retry_feedback=retry_feedback,
        )
    _log(repo_root, "generate", result=_norm(result))
    return result
'''


VERIFIER_ORCHESTRATOR = '''

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
    report = VerificationReport(
        component_id=component_id,
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}
        ],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=0.81,
        overall="pass",
    )
    _log(repo_root, "verify", component_id=component_id, result=_norm(report))
    return report
'''


LICENSE_SCANNER = '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    result = {
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
    _log(repo_root, "license_scan", component_id=component_id, result=_norm(result))
    return result
'''


SECRET_SCANNER = '''

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
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def _clean(scope):
    return SecretScanResult(
        scope=scope,
        gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def scan(repo_root):
    result = _clean("full")
    _log(repo_root, "secret_scan", result=_norm(result))
    return result


def scan_files(paths, repo_root=None):
    return _clean("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = '''

def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    attempt_id = "2026-11-15T00:00:00Z-aaaaaa"
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _norm(generation_result),
        "verification": _norm(verification_report),
    }
    d = Path(repo_root) / ".hotdocs" / "attempts" / "foo"
    d.mkdir(parents=True, exist_ok=True)
    (d / (attempt_id.replace(":", "-") + ".json")).write_text(json.dumps(record), encoding="utf-8")
    _log(repo_root, "write_attempt_record", component_id=component_id)
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER = '''

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
    _log(repo_root, "write_provenance", component_id=component_id, inputs=_norm(inputs))
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log(repo_root, "write_sealed_provenance", component_id=component_id, inputs=_norm(inputs))
    return None
'''


TEST_AUTHOR = '''

def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    if repo_root is not None:
        _log(repo_root, "author_test")
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py", "content": "def test_x():\\n    pass\\n"},
        "model_call_error": None,
    }
'''


LLM_ENDPOINT = '''

DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    if backend is not None:
        return backend(prompt, model, **params)
    return {"text": "pass", "model": model, "backend": "fake", "model_call_error": None}


def parse_model(model):
    return (None, model)
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


def _mock_backend(prompt, model, **params):
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}


def _build_repo(root: Path, mode: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for (slug, module_name), body in FAKES.items():
        d = root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{module_name}.py").write_text(COMMON + body, encoding="utf-8")
    comp = root / "specs" / "components" / SLUG
    comp.mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    log_dir = root / "test-log"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "mode.txt").write_text(mode, encoding="utf-8")
    return root


def _read_log(root: Path):
    path = root / "test-log" / "calls.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _index(entries, call):
    idx = [i for i, e in enumerate(entries) if e["call"] == call]
    assert idx, f"expected {call} to have been called; log: {[e['call'] for e in entries]}"
    return idx


def test_write_provenance_called_once_after_scans_and_attempt_record(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", "pass")

    component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "mock-model", seed=0, llm_backend=_mock_backend
    )

    entries = _read_log(repo_root)
    calls = [e["call"] for e in entries]

    wp_idx = [i for i, c in enumerate(calls) if c == "write_provenance"]
    assert len(wp_idx) == 1, f"write_provenance calls: {len(wp_idx)}; log: {calls}"
    wp = wp_idx[0]

    for prior in ("verify", "license_scan", "secret_scan", "write_attempt_record"):
        positions = _index(entries, prior)
        assert max(positions) < wp, f"{prior} must conclude before write_provenance; log: {calls}"

    inputs = entries[wp]["inputs"]
    assert isinstance(inputs, dict)

    assert inputs["gate_versions"] == GATE_VERSIONS
    assert inputs["provenance_hit"] is False
    assert not isinstance(inputs["attempts"], bool)
    assert inputs["attempts"] == 1

    gen_result = entries[_index(entries, "generate")[-1]]["result"]
    ver_result = entries[_index(entries, "verify")[-1]]["result"]
    lic_result = entries[_index(entries, "license_scan")[-1]]["result"]
    sec_result = entries[_index(entries, "secret_scan")[-1]]["result"]

    assert inputs["generation_result"] == gen_result
    assert inputs["verification_report"] == ver_result
    assert inputs["license_scan_result"] == lic_result
    assert inputs["secret_scan_result"] == sec_result


def test_write_provenance_never_called_on_model_call_error(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", "error")

    component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "mock-model", seed=0, llm_backend=_mock_backend
    )

    entries = _read_log(repo_root)
    calls = [e["call"] for e in entries]

    # The generator was reached and returned the model_call_error.
    gen_entries = [e for e in entries if e["call"] == "generate"]
    assert gen_entries, f"generator was never called; log: {calls}"
    assert gen_entries[-1]["result"]["model_call_error"] is not None

    assert "write_provenance" not in calls, f"write_provenance must not be called; log: {calls}"