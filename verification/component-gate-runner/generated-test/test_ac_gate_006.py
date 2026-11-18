# hotdocs-criterion: sha256:ec98c42d6687c8f6a77cbb9a956c6f7002570dd3a787a9494c8fcd1a48d5232d
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = r'''
import dataclasses
import json
import os
from pathlib import Path


def _norm(v):
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, Path):
        return str(v)
    if not isinstance(v, type) and callable(getattr(v, "to_dict", None)):
        return _norm(v.to_dict())
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: _norm(getattr(v, f.name)) for f in dataclasses.fields(v)}
    return v


def _log(entry):
    with open(os.environ["GATE_TEST_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(_norm(entry), sort_keys=True, default=repr) + "\n")


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)

'''

PROVENANCE_CHECKER = r'''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log({"call": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"call": "current_provenance_key", "component_id": component_id})
    return ProvenanceKey("sha256:" + "ab" * 32, {"verifier": "v@1"})


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({"call": "check_provenance", "component_id": component_id,
          "spec_bundle_hash": spec_bundle_hash, "gate_versions": gate_versions})
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log({"call": "check_sealed_provenance", "component_id": component_id})
    return {"hit": False, "sealed": False, "reason": "not_sealed", "verification_report": None,
            "license_scan": None, "secret_scan": None, "owners": None, "source_hash": None,
            "written_at": None}
'''

SPEC_BUNDLE_ASSEMBLER = r'''
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
    _log({"call": "assemble", "component_id": component_id, "mode": mode})
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        glossary="- **Foo** - a test term.",
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({"call": "assemble_criterion", "component_id": component_id, "criterion_id": criterion_id})
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

GENERATOR = r'''
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
    cid = _get(bundle, "component_id")
    h = _get(bundle, "spec_bundle_hash")
    if os.environ.get("GATE_TEST_GEN_MODE") == "error":
        result = GenerationResult(
            component_id=cid, spec_bundle_hash=h, model=model, prompt_version=PROMPT_VERSION,
            cache_hit=False, files={},
            model_call_error={"category": "network", "message": "fake network failure"},
            refused=None, retry_feedback=retry_feedback,
        )
    else:
        result = GenerationResult(
            component_id=cid, spec_bundle_hash=h, model=model, prompt_version=PROMPT_VERSION,
            cache_hit=False, files={"foo.py": "def foo(x):\n    return 2 * x\n"},
            model_call_error=None, refused=None, retry_feedback=retry_feedback,
        )
    _log({"call": "generate", "result": result})
    return result
'''

VERIFIER_ORCHESTRATOR = r'''
GATE_VERSION = "verifier-orchestrator@2.2.0"


@dataclasses.dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: object
    mutation_error: object
    overall: str

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}


def verify(component_id, repo_root, judge=None, test_author=None):
    report = VerificationReport(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
                   "result": "pass"}],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=0.91,
        mutation_error=None,
        overall="pass",
    )
    _log({"call": "verify", "component_id": component_id, "result": report})
    return report
'''

LICENSE_SCANNER = r'''
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
    _log({"call": "license_scan", "component_id": component_id, "result": result})
    return result
'''

SECRET_SCANNER = r'''
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
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}


def _result(scope):
    return SecretScanResult(
        scope=scope, gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
        flagged=False, matches=[], allowed=[], unused_allowlist_entries=[],
        notified=False, notification_delivery_error=None, cache_hit=False,
    )


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def scan(repo_root):
    result = _result("full")
    _log({"call": "secret_scan", "result": result})
    return result


def scan_files(paths, repo_root=None):
    return _result("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_TRACKER = r'''
def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    d = Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    attempt_id = "2026-11-17T00:00:00Z-a1b2c3"
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-17T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _norm(generation_result),
        "verification": _norm(verification_report),
    }
    (d / (attempt_id + ".json")).write_text(json.dumps(record, default=repr), encoding="utf-8")
    _log({"call": "write_attempt_record", "component_id": component_id})
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {},
            "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''

PROVENANCE_WRITER = r'''
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
    _log({"call": "write_provenance", "component_id": component_id, "inputs": inputs,
          "inputs_is_dict": isinstance(inputs, dict)})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log({"call": "write_sealed_provenance", "component_id": component_id})
    return None
'''

TEST_AUTHOR = r'''
GATE_VERSION = "generated_test@1.1.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log({"call": "author_test"})
    return {
        "component_id": _get(bundle, "component_id"),
        "criterion_id": _get(bundle, "criterion_id"),
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py",
                 "content": "def test_x():\n    assert True\n"},
        "model_call_error": None,
    }
'''

LLM_ENDPOINT = r'''
DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log({"call": "complete"})
    return {"text": "pass", "model": model, "backend": "fake", "model_call_error": None}


def parse_model(model):
    return (None, model)
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


def build_repo(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
        encoding="utf-8",
    )
    for slug, body in FAKES.items():
        module_name = slug.replace("-", "_")
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(PRELUDE + body, encoding="utf-8")


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fake_backend(prompt, model, **params):
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}


def _setup(tmp_path, monkeypatch, gen_mode):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    monkeypatch.setenv("GATE_TEST_GEN_MODE", gen_mode)
    return repo_root, log_path


def test_write_provenance_called_once_after_scans_and_attempt_record(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, "files")

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock-model", seed=0, llm_backend=fake_backend,
    )
    assert result is not None

    entries = read_log(log_path)
    calls = [e["call"] for e in entries]

    writes = [i for i, c in enumerate(calls) if c == "write_provenance"]
    assert len(writes) == 1, calls
    w = writes[0]

    for name in ("verify", "license_scan", "secret_scan", "write_attempt_record"):
        assert name in calls, (name, calls)
        assert max(i for i, c in enumerate(calls) if c == name) < w, (name, calls)

    write_entry = entries[w]
    inputs = write_entry["inputs"]
    assert write_entry["inputs_is_dict"] is True
    assert write_entry["component_id"] == "comp-foo"

    assert inputs["gate_versions"] == {"verifier": "v@1"}
    assert inputs["provenance_hit"] is False
    assert isinstance(inputs["attempts"], int) and not isinstance(inputs["attempts"], bool)
    assert inputs["attempts"] == 1
    assert inputs["component_id"] == "comp-foo"

    def logged_result(name):
        found = [e for e in entries if e["call"] == name]
        assert len(found) == 1, (name, calls)
        return found[0]["result"]

    assert inputs["generation_result"] == logged_result("generate")
    assert inputs["verification_report"] == logged_result("verify")
    assert inputs["license_scan_result"] == logged_result("license_scan")
    assert inputs["secret_scan_result"] == logged_result("secret_scan")

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "foo"
    assert len(list(attempts_dir.iterdir())) == 1


def test_model_call_error_writes_no_provenance(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, "error")

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock-model", seed=0, llm_backend=fake_backend,
    )
    assert result is not None

    entries = read_log(log_path)
    calls = [e["call"] for e in entries]

    assert "generate" in calls, calls
    gen_entries = [e for e in entries if e["call"] == "generate"]
    assert gen_entries[0]["result"]["model_call_error"] is not None
    assert "write_provenance" not in calls, calls