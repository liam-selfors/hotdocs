# hotdocs-criterion: sha256:1bb7ea9bd9eaf7ebd63bed63438fc5c3fdca8811f08fb75370ed2e7cdbb93f3b
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG_AC_GATE_002A"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMMON = (
    "import json\n"
    "import os\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry, default=repr) + '\\n')\n"
    "\n"
    "\n"
)


PROVENANCE_CHECKER = COMMON + '''
class _ProvenanceKey:
    def __init__(self):
        self.spec_bundle_hash = "sha256:" + "a" * 64
        self.gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.1.0",
            "verifier": "verifier-orchestrator@2.2.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
        }


def current_sealed_key(component_id, repo_root):
    _log({"call": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"call": "current_provenance_key", "component_id": component_id})
    return _ProvenanceKey()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({"call": "check_provenance", "component_id": component_id})
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log({"call": "check_sealed_provenance", "component_id": component_id})
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
    _log({"call": "assemble", "component_id": component_id, "mode": mode})
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "Foo doubles a number.",
        "interface": "foo(x: int) -> int",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "- **Foo** - a test term.",
        "hint_code": None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({"call": "assemble_criterion", "component_id": component_id, "criterion_id": criterion_id})
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "Given x = 2 When foo(x) is called Then it returns 4",
        "requirement_text": "foo(x) MUST return 2 * x.",
        "interface": "foo(x: int) -> int",
        "glossary": "- **Foo** - a test term.",
        "dependency_interfaces": {},
    }
'''


GENERATOR = COMMON + '''
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


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    spec_bundle_hash = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash")
    _log({"call": "generate", "model": model})
    return GenerationResult(
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR = COMMON + '''
import dataclasses

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
            "criteria": list(self.criteria),
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "mutation_error": self.mutation_error,
            "overall": self.overall,
        }


def verify(component_id, repo_root, judge=None, test_author=None):
    sentinel_bundle = {
        "component_id": component_id,
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "Given x = 2 When foo(x) is called Then it returns 4",
        "requirement_text": "foo(x) MUST return 2 * x.",
        "interface": "foo(x: int) -> int",
        "glossary": "- **Foo** - a test term.",
        "dependency_interfaces": {},
        "sentinel": "sentinel-bundle-token",
    }
    judge_bundle = {
        "component_id": component_id,
        "criterion_id": "AC-FOO-002",
        "covers": "R-FOO-002",
        "criterion_text": "Given foo When reviewed Then it reads clearly",
        "requirement_text": "foo SHOULD read clearly.",
        "interface": "foo(x: int) -> int",
        "glossary": "- **Foo** - a test term.",
        "dependency_interfaces": {},
    }
    _log({
        "call": "verify",
        "component_id": component_id,
        "has_judge": judge is not None,
        "has_test_author": test_author is not None,
        "sentinel_id": id(sentinel_bundle),
    })
    if test_author is not None:
        try:
            test_author(sentinel_bundle)
        except Exception as exc:
            _log({"call": "test_author_error", "error": repr(exc)})
    if judge is not None:
        try:
            judge(judge_bundle)
        except Exception as exc:
            _log({"call": "judge_error", "error": repr(exc)})
    return VerificationReport(
        component_id=component_id,
        criteria=[
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "generated-test",
                "result": "pass",
                "test_authoring": {"model": "m", "seed": 3, "prompt_version": "v1", "cache_hit": False},
            },
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "llm-judge",
                "result": "pass",
                "rationale": "ok",
            },
        ],
        requirement_results={"R-FOO-001": "pass", "R-FOO-002": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        mutation_error=None,
        overall="pass",
    )
'''


TEST_AUTHOR = COMMON + '''
GATE_VERSION = "generated_test@1.1.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        sentinel = bundle.get("sentinel")
        criterion_id = bundle.get("criterion_id")
    else:
        sentinel = getattr(bundle, "sentinel", None)
        criterion_id = getattr(bundle, "criterion_id", None)
    _log({
        "call": "author_test",
        "bundle_id": id(bundle),
        "bundle_sentinel": sentinel,
        "bundle_criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "seed_type": type(seed).__name__,
        "backend_id": id(llm_backend),
        "backend_token": getattr(llm_backend, "token", None),
    })
    return {
        "component_id": "comp-foo",
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/foo/generated-test/test_ac_foo_001.py",
            "content": "def test_ok():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
'''


LLM_ENDPOINT = COMMON + '''
DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def parse_model(model):
    return (None, model)


def complete(prompt, model, *, backend=None, **params):
    _log({
        "call": "complete",
        "prompt_type": type(prompt).__name__,
        "model": model,
        "backend_id": id(backend),
        "backend_token": getattr(backend, "token", None),
    })
    return {
        "text": json.dumps({"result": "pass", "rationale": "ok"}),
        "model": model,
        "backend": "sentinel",
        "model_call_error": None,
    }
'''


LICENSE_SCANNER = COMMON + '''
def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log({"call": "license_scan", "component_id": component_id})
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


class AllowlistInvalidError(Exception):
    pass


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
    _log({"call": "secret_scan"})
    return _clean("full")


def scan_files(paths, repo_root=None):
    return _clean("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = COMMON + '''
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    directory = Path(repo_root) / ".hotdocs" / "attempts" / slug
    directory.mkdir(parents=True, exist_ok=True)
    attempt_id = "2026-11-17T00:00:00Z-a1b2c3"
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-17T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {"component_id": component_id},
        "verification": None if verification_report is None else {"overall": "pass"},
    }
    (directory / (attempt_id + ".json")).write_text(json.dumps(record), encoding="utf-8")
    _log({"call": "write_attempt_record", "component_id": component_id})
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER = COMMON + '''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log({"call": "write_provenance", "component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log({"call": "write_sealed_provenance", "component_id": component_id})
    return None
'''


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    write(
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
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
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
    write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def install_fakes(repo_root):
    fakes = {
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
    for slug, source in fakes.items():
        module_name = slug.replace("-", "_")
        write(repo_root / "gen" / slug / (module_name + ".py"), source)


class SentinelBackend:
    token = "sentinel-backend-token"

    def __call__(self, prompt, model, **params):
        return {
            "text": json.dumps({"result": "pass", "rationale": "ok"}),
            "model": model,
            "backend": "sentinel",
            "model_call_error": None,
        }


def read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_closures_forward_model_seed_and_backend(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    install_fakes(repo_root)

    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    sentinel_backend = SentinelBackend()
    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", seed=3, llm_backend=sentinel_backend
    )

    entries = read_log(log_path)
    errors = [e for e in entries if e["call"] in ("test_author_error", "judge_error")]

    assert field(result, "provenance_hit") is False

    verify_calls = [e for e in entries if e["call"] == "verify"]
    assert len(verify_calls) == 1, entries
    assert verify_calls[0]["has_test_author"] is True
    assert verify_calls[0]["has_judge"] is True

    author_calls = [e for e in entries if e["call"] == "author_test"]
    assert author_calls, ("author_test was never called", errors, entries)
    sentinel_calls = [e for e in author_calls if e["bundle_sentinel"] == "sentinel-bundle-token"]
    assert sentinel_calls, ("author_test never received the sentinel bundle", author_calls, errors)
    call = sentinel_calls[0]
    assert call["bundle_criterion_id"] == "AC-FOO-001"
    assert call["model"] == "m"
    assert call["seed"] == 3
    assert call["seed_type"] == "int"
    assert call["backend_id"] == id(sentinel_backend)
    assert call["backend_token"] == "sentinel-backend-token"

    complete_calls = [e for e in entries if e["call"] == "complete"]
    assert complete_calls, ("llm-endpoint complete was never called", errors, entries)
    for c in complete_calls:
        assert c["model"] == "m"
        assert c["backend_id"] == id(sentinel_backend)
        assert c["backend_token"] == "sentinel-backend-token"