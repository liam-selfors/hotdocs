import json
import os
import sys
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_RUNNER_AC002A_LOG"


COMMON = '''import json, os


def _log(record):
    with open(os.environ["GATE_RUNNER_AC002A_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")
'''


PROVENANCE_CHECKER = COMMON + '''

_GATE_VERSIONS = {
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


class SealedKey:
    def __init__(self, owners, source_path, source_hash, verifier_version):
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version


def current_sealed_key(component_id, repo_root):
    _log({"who": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"who": "current_provenance_key", "component_id": component_id})
    return ProvenanceKey("sha256:" + "ab" * 32, dict(_GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({"who": "check_provenance", "component_id": component_id})
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


SPEC_BUNDLE_ASSEMBLER = COMMON + '''

def assemble(component_id, repo_root, mode="cold"):
    _log({"who": "assemble", "component_id": component_id, "mode": mode})
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "Foo doubles a number.",
        "interface": "# Library",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "- **Foo** - a test term.",
        "hint_code": None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "Given x = 2 When doubled Then 4",
        "requirement_text": "doubles",
        "interface": "# Library",
        "glossary": "- **Foo** - a test term.",
        "dependency_interfaces": {},
    }
'''


GENERATOR = COMMON + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log({"who": "generate", "model": model})
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "cache_hit": False,
        "files": {"foo.py": "def double(x):\\n    return 2 * x\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''


VERIFIER_ORCHESTRATOR = COMMON + '''
import dataclasses
import uuid

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


class SentinelBundle:
    def __init__(self, token):
        self.sentinel_token = token

    def __getitem__(self, key):
        if key == "sentinel_token":
            return self.sentinel_token
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def verify(component_id, repo_root, judge=None, test_author=None):
    token = uuid.uuid4().hex
    sentinel = SentinelBundle(token)
    _log({
        "who": "verify",
        "component_id": component_id,
        "has_test_author": test_author is not None,
        "has_judge": judge is not None,
        "sentinel_id": id(sentinel),
        "sentinel_token": token,
    })
    if test_author is not None:
        try:
            test_author(sentinel)
        except Exception as exc:
            _log({"who": "test_author_raised", "error": repr(exc)})
    if judge is not None:
        criterion_bundle = {
            "component_id": component_id,
            "criterion_id": "AC-FOO-002",
            "covers": "R-FOO-002",
            "criterion_text": "Given a thing When judged Then it is fine",
            "requirement_text": "R-FOO-002 text",
            "interface": "# Library",
            "glossary": "- **Foo** - a test term.",
            "dependency_interfaces": {},
        }
        try:
            judge(criterion_bundle)
        except Exception as exc:
            _log({"who": "judge_raised", "error": repr(exc)})
    return VerificationReport(
        component_id=component_id,
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
             "result": "pass",
             "test_authoring": {"model": "m", "seed": 3, "prompt_version": "v1",
                                "cache_hit": False}},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "llm-judge",
             "result": "pass", "rationale": "ok"},
        ],
        requirement_results={"R-FOO-001": "pass", "R-FOO-002": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        overall="pass",
    )
'''


TEST_AUTHOR = COMMON + '''

GATE_VERSION = "generated_test@1.0.0"
PROMPT_VERSION = "v1"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    token = getattr(bundle, "sentinel_token", None)
    if token is None and isinstance(bundle, dict):
        token = bundle.get("sentinel_token")
    _log({
        "who": "author_test",
        "bundle_id": id(bundle),
        "bundle_token": token,
        "model": model,
        "seed": seed,
        "seed_is_int": isinstance(seed, int) and not isinstance(seed, bool),
        "backend_id": id(llm_backend),
        "backend_is_none": llm_backend is None,
    })
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": PROMPT_VERSION,
        "cache_hit": False,
        "file": {
            "path": "verification/foo/generated-test/test_ac_foo_001.py",
            "content": "def test_placeholder():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
'''


LLM_ENDPOINT = COMMON + '''

DEFAULT_TIMEOUT_SECONDS = 600
PROVIDERS = {}


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log({
        "who": "complete",
        "model": model,
        "backend_id": id(backend),
        "backend_is_none": backend is None,
        "prompt_is_str": isinstance(prompt, str),
    })
    return {
        "text": json.dumps({"result": "pass", "rationale": "ok"}),
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def parse_model(model):
    return (None, model)


def resolve_provider(model, config=None):
    return {"provider": None, "model": model, "base_url": None,
            "api_key_env": None, "timeout_seconds": DEFAULT_TIMEOUT_SECONDS}
'''


LICENSE_SCANNER = COMMON + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log({"who": "license_scan"})
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


SECRET_SCANNER = COMMON + '''
import dataclasses


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
        scope=scope, gate_version="secret_scanner@0.0.0", flagged=False,
        matches=[], allowed=[], unused_allowlist_entries=[], notified=False,
        notification_delivery_error=None, cache_hit=False,
    )


def scan(repo_root):
    _log({"who": "secret_scan"})
    return _clean("full")


def scan_files(paths, repo_root=None):
    return _clean("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = COMMON + '''
import dataclasses
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
    _log({"who": "write_attempt_record"})
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    record = {
        "attempt_id": "2026-11-15T00:00:00Z-a1b2c3",
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    d = Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (record["attempt_id"].replace(":", "-") + ".json")).write_text(
        json.dumps(record, default=str), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER = COMMON + '''
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
    _log({"who": "write_provenance", "inputs_is_dict": isinstance(inputs, dict)})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log({"who": "write_sealed_provenance"})
    return None
'''


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generator": GENERATOR,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR,
    "test-author": TEST_AUTHOR,
    "llm-endpoint": LLM_ENDPOINT,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-tracker": PROVENANCE_TRACKER,
    "provenance-writer": PROVENANCE_WRITER,
}


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)


class SentinelBackend:
    """A callable llm backend stand-in: backend(prompt, model, **params) -> ModelResponse."""

    def __call__(self, prompt, model, **params):
        return {
            "text": json.dumps({"result": "pass", "rationale": "ok"}),
            "model": model,
            "backend": "sentinel",
            "model_call_error": None,
        }


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_repo(repo_root):
    for slug, source in FAKES.items():
        module_name = slug.replace("-", "_")
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{module_name}.py").write_text(source, encoding="utf-8")
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")


def test_ac_gate_002a_closures_capture_model_seed_and_backend(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    log_path = tmp_path / "invocations.jsonl"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    sentinel_backend = SentinelBackend()

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", seed=3, llm_backend=sentinel_backend
    )

    records = _read_log(log_path)

    verify_calls = [r for r in records if r["who"] == "verify"]
    assert len(verify_calls) == 1, f"expected one verify call, log: {records}"
    verify_call = verify_calls[0]
    assert verify_call["has_test_author"] is True
    assert verify_call["has_judge"] is True

    author_calls = [r for r in records if r["who"] == "author_test"]
    assert len(author_calls) == 1, f"expected one author_test call, log: {records}"
    author = author_calls[0]
    # The sentinel bundle the verifier handed test_author reached author_test.
    assert author["bundle_id"] == verify_call["sentinel_id"]
    assert author["bundle_token"] == verify_call["sentinel_token"]
    assert author["model"] == "m"
    assert author["seed"] == 3
    assert author["seed_is_int"] is True
    assert author["backend_is_none"] is False
    assert author["backend_id"] == id(sentinel_backend)

    complete_calls = [r for r in records if r["who"] == "complete"]
    assert len(complete_calls) >= 1, f"expected judge to call complete, log: {records}"
    for call in complete_calls:
        assert call["model"] == "m"
        assert call["backend_is_none"] is False
        assert call["backend_id"] == id(sentinel_backend)