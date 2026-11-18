# hotdocs-criterion: sha256:ad478cd600c38418f76533351c9356f08ef32776a3c67765f47811ea9272f2e5
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "HOTDOCS_GATE_TEST_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = '''import os
import json
import time
import dataclasses


def _log(name):
    p = os.environ.get("HOTDOCS_GATE_TEST_LOG")
    if p:
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(name + "\\n")


def _get(value, name, default=None):
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if callable(getattr(value, "to_dict", None)):
        return _plain(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    return repr(value)


def _slug(component_id):
    return component_id[5:] if component_id.startswith("comp-") else component_id

'''


PROVENANCE_CHECKER = PRELUDE + '''
GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0",
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
    _log("provenance_checker.current_sealed_key")
    return None


def current_provenance_key(component_id, repo_root):
    _log("provenance_checker.current_provenance_key")
    return ProvenanceKey("sha256:abc123", dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("provenance_checker.check_provenance")
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("provenance_checker.check_sealed_provenance")
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


SPEC_BUNDLE_ASSEMBLER = PRELUDE + '''
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
        names = [f.name for f in dataclasses.fields(self)]
        if key not in names:
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
        names = [f.name for f in dataclasses.fields(self)]
        if key not in names:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def assemble(component_id, repo_root=None, mode="cold"):
    _log("spec_bundle_assembler.assemble")
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:abc123",
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        glossary="- **Foo** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root=None):
    _log("spec_bundle_assembler.assemble_criterion")
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


GENERATOR_BODY = '''
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
    _log("generator.generate")
    component_id = _get(bundle, "component_id")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    if CONFIG.get("model_call_error") is not None:
        return GenerationResult(
            component_id=component_id,
            spec_bundle_hash=spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files={},
            model_call_error=dict(CONFIG["model_call_error"]),
            refused=None,
            retry_feedback=retry_feedback,
        )
    return GenerationResult(
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files=dict(CONFIG["files"]),
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_BODY = '''
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
        return {
            "component_id": self.component_id,
            "criteria": [dict(c) for c in self.criteria],
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "mutation_error": self.mutation_error,
            "overall": self.overall,
        }


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verifier_orchestrator.verify")
    criteria = [dict(c) for c in CONFIG["criteria"]]
    requirement_results = {}
    for c in criteria:
        prior = requirement_results.get(c["covers"], "pass")
        requirement_results[c["covers"]] = "pass" if (prior == "pass" and c["result"] == "pass") else "fail"
    return VerificationReport(
        component_id=component_id,
        criteria=criteria,
        requirement_results=requirement_results,
        interface_drift=False,
        mutation_score=None,
        mutation_error=None,
        overall=CONFIG["overall"],
    )
'''


LICENSE_SCANNER = PRELUDE + '''
def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("license_scanner.scan")
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


SECRET_SCANNER = PRELUDE + '''
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
        return {
            "scope": self.scope,
            "gate_version": self.gate_version,
            "flagged": self.flagged,
            "matches": list(self.matches),
            "allowed": list(self.allowed),
            "unused_allowlist_entries": list(self.unused_allowlist_entries),
            "notified": self.notified,
            "notification_delivery_error": self.notification_delivery_error,
            "cache_hit": self.cache_hit,
        }


def gate_version(repo_root):
    return "secret_scanner@3.1.0"


def _clean(scope):
    return SecretScanResult(
        scope=scope,
        gate_version="secret_scanner@3.1.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def scan(repo_root):
    _log("secret_scanner.scan")
    return _clean("full")


def scan_files(paths, repo_root=None):
    _log("secret_scanner.scan_files")
    return _clean("precommit")


def propose(repo_root):
    _log("secret_scanner.propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = PRELUDE + '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("provenance_tracker.write_attempt_record")
    d = os.path.join(str(repo_root), ".hotdocs", "attempts", _slug(component_id))
    os.makedirs(d, exist_ok=True)
    existing = len(os.listdir(d))
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    attempt_id = ts + "-" + str(existing)
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": ts,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    fname = attempt_id.replace(":", "-") + ".json"
    with open(os.path.join(d, fname), "w", encoding="utf-8") as fh:
        json.dump(record, fh)
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("provenance_tracker.check_readiness")
    return {
        "scope": "blast-radius" if changed_ids else "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    _log("provenance_tracker.last_requirement_failures")
    return []
'''


PROVENANCE_WRITER = PRELUDE + '''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_provenance")
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_sealed_provenance")
    return None
'''


TEST_AUTHOR = PRELUDE + '''
GATE_VERSION = "generated_test@1.1.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("test_author.author_test")
    return {
        "component_id": _get(bundle, "component_id"),
        "criterion_id": _get(bundle, "criterion_id"),
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": "network", "message": "fake author unavailable"},
    }
'''


LLM_ENDPOINT = PRELUDE + '''
DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log("llm_endpoint.complete")
    return {
        "text": None,
        "model": model,
        "backend": "fake",
        "model_call_error": {"category": "network", "message": "fake endpoint"},
    }
'''


def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_corpus(repo_root):
    write_file(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    write_file(
        comp / "component.md",
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
    )
    write_file(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    write_file(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write_file(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    write_file(comp / "constraints.md", "# Constraints\n\nNone.\n")


def build_repo(tmp_path, gen_config, verify_config):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_corpus(repo_root)
    gen = repo_root / "gen"
    write_file(gen / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER)
    write_file(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER)
    write_file(
        gen / "generator" / "generator.py",
        PRELUDE + "\nCONFIG = " + repr(gen_config) + "\n" + GENERATOR_BODY,
    )
    write_file(
        gen / "verifier-orchestrator" / "verifier_orchestrator.py",
        PRELUDE + "\nCONFIG = " + repr(verify_config) + "\n" + VERIFIER_BODY,
    )
    write_file(gen / "license-scanner" / "license_scanner.py", LICENSE_SCANNER)
    write_file(gen / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER)
    write_file(gen / "provenance-tracker" / "provenance_tracker.py", PROVENANCE_TRACKER)
    write_file(gen / "provenance-writer" / "provenance_writer.py", PROVENANCE_WRITER)
    write_file(gen / "test-author" / "test_author.py", TEST_AUTHOR)
    write_file(gen / "llm-endpoint" / "llm_endpoint.py", LLM_ENDPOINT)
    return repo_root


def mock_backend(prompt, model, **params):
    return {
        "text": None,
        "model": model,
        "backend": "mock",
        "model_call_error": {"category": "network", "message": "mock backend"},
    }


def read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


GENERATED_FILES = {"foo.py": "def foo(x):\n    return 2 * x\n"}

PASSING_VERIFY = {
    "overall": "pass",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
    ],
}


def fail_criterion(cid, covers, origin):
    return {
        "id": cid,
        "covers": covers,
        "kind": "generated-test",
        "result": "fail",
        "failure_detail": {"message": cid + " failed", "expected": 4, "actual": 3},
        "failure_origin": origin,
    }


def pass_criterion(cid, covers):
    return {"id": cid, "covers": covers, "kind": "generated-test", "result": "pass"}


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(path))
    return path


def run(repo_root):
    return component_gate_runner.run_component_gates(
        "comp-foo", Path(repo_root), "mock-model", seed=0, llm_backend=mock_backend,
    )


def test_model_call_error_never_calls_verify(tmp_path, log_path):
    error = {"category": "network", "message": "connection refused"}
    repo_root = build_repo(tmp_path, {"model_call_error": error}, PASSING_VERIFY)

    result = run(repo_root)

    calls = read_log(log_path)
    assert "generator.generate" in calls
    assert "verifier_orchestrator.verify" not in calls
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "model_call_error"
    mce = field(result, "model_call_error")
    assert mce is not None
    assert field(mce, "category") == "network"
    assert field(mce, "message") == "connection refused"
    assert field(result, "verification") is None


def test_verification_failed_when_verify_fails(tmp_path, log_path):
    verify_config = {
        "overall": "fail",
        "criteria": [fail_criterion("AC-FOO-001", "R-FOO-001", "implementation")],
    }
    repo_root = build_repo(tmp_path, {"files": GENERATED_FILES}, verify_config)

    result = run(repo_root)

    calls = read_log(log_path)
    assert "generator.generate" in calls
    assert "verifier_orchestrator.verify" in calls
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"
    assert field(result, "model_call_error") is None


def test_test_authoring_failed_when_every_fail_has_test_origin(tmp_path, log_path):
    verify_config = {
        "overall": "fail",
        "criteria": [
            fail_criterion("AC-FOO-001", "R-FOO-001", "test"),
            pass_criterion("AC-FOO-002", "R-FOO-002"),
        ],
    }
    repo_root = build_repo(tmp_path, {"files": GENERATED_FILES}, verify_config)

    result = run(repo_root)

    calls = read_log(log_path)
    assert "verifier_orchestrator.verify" in calls
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "test_authoring_failed"


def test_verification_failed_when_any_fail_has_implementation_origin(tmp_path, log_path):
    verify_config = {
        "overall": "fail",
        "criteria": [
            fail_criterion("AC-FOO-001", "R-FOO-001", "test"),
            fail_criterion("AC-FOO-002", "R-FOO-002", "implementation"),
        ],
    }
    repo_root = build_repo(tmp_path, {"files": GENERATED_FILES}, verify_config)

    result = run(repo_root)

    calls = read_log(log_path)
    assert "verifier_orchestrator.verify" in calls
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"