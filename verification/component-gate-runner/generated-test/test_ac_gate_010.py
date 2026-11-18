# hotdocs-criterion: sha256:b0c0b9d6c57a078703776118106a1cbd294c23423b25b69e5cc8a2d213b836e6
import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE010_LOG_DIR"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    write(Path(repo_root) / "gen" / slug / (module_name + ".py"), source)


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

COMPONENT_MD = (
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
    "Foo doubles a number.\n"
)

REQ = "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"

ACC = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

IFACE = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS = "# Constraints\n\nNone.\n"


FAKE_PROVENANCE_CHECKER = '''
class _Key:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return _Key(
        "sha256:" + "0" * 64,
        {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.1.0",
            "verifier": "verifier-orchestrator@2.2.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
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


FAKE_ASSEMBLER = '''
from dataclasses import dataclass, field


@dataclass
class SpecBundle:
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

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


@dataclass
class CriterionBundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def assemble(component_id, repo_root, mode="cold"):
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        glossary="Foo",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="MARKER_CRIT",
        requirement_text="MARKER_REQ",
        interface="MARKER_IFACE",
        glossary="Foo",
    )
'''


FAKE_GENERATOR = '''
import os
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
    if isinstance(bundle, dict):
        component_id = bundle["component_id"]
        sbh = bundle["spec_bundle_hash"]
    else:
        component_id = bundle.component_id
        sbh = bundle.spec_bundle_hash
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    target = os.path.join(str(repo_root), "gen", slug)
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "foo.py"), "w", encoding="utf-8") as fh:
        fh.write("MARKER_SOURCE = 1\\n")
    return GenerationResult(
        component_id=component_id,
        spec_bundle_hash=sbh,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "MARKER_SOURCE = 1\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


FAKE_VERIFIER = '''
import json
import os
from dataclasses import dataclass

GATE_VERSION = "verifier-orchestrator@2.2.0"


@dataclass
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


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def verify(component_id, repo_root, judge=None, test_author=None):
    log_dir = os.environ["GATE010_LOG_DIR"]
    bundle = {
        "component_id": component_id,
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "MARKER_CRIT",
        "requirement_text": "MARKER_REQ",
        "interface": "MARKER_IFACE",
        "glossary": "Foo",
        "dependency_interfaces": {},
    }
    if judge is None:
        record = {"result": None, "rationale": "no judge given", "error": "judge missing"}
    else:
        try:
            outcome = judge(bundle)
            record = {"result": _get(outcome, "result"), "rationale": _get(outcome, "rationale")}
        except Exception as exc:
            record = {"result": None, "rationale": None, "error": "raised: " + repr(exc)}
    with open(os.path.join(log_dir, "judge_outcome.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh)
    result = record.get("result") if record.get("result") in ("pass", "fail") else "fail"
    criterion = {
        "id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "kind": "llm-judge",
        "result": result,
        "rationale": record.get("rationale"),
    }
    return VerificationReport(
        component_id=component_id,
        criteria=[criterion],
        requirement_results={"R-FOO-001": result},
        interface_drift=False,
        mutation_score=None,
        mutation_error=None,
        overall=result,
    )
'''


FAKE_LICENSE = '''
GV = "license_scanner@4.0.0-no-reference-corpus"


def gate_version(repo_root):
    return GV


def scan(component_id, repo_root):
    return {
        "component_id": component_id,
        "gate_version": GV,
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


FAKE_SECRET = '''
from dataclasses import dataclass, field

GV = "secret_scanner@0.0.0"


class AllowlistInvalidError(Exception):
    pass


@dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool
    matches: list = field(default_factory=list)
    allowed: list = field(default_factory=list)
    unused_allowlist_entries: list = field(default_factory=list)
    notified: bool = False
    notification_delivery_error: object = None
    cache_hit: bool = False

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
    return GV


def scan(repo_root):
    return SecretScanResult(scope="full", gate_version=GV, flagged=False)


def scan_files(paths, repo_root=None):
    return SecretScanResult(scope="precommit", gate_version=GV, flagged=False)


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


FAKE_TRACKER = '''
import json
import os
import uuid


def _plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _plain(value.to_dict())
    if hasattr(value, "__dict__"):
        return {k: _plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return repr(value)


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    d = os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    os.makedirs(d, exist_ok=True)
    ts = "2026-11-17T00:00:00Z"
    attempt_id = ts + "-" + uuid.uuid4().hex[:6]
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": ts,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    with open(os.path.join(d, attempt_id.replace(":", "-") + ".json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh)
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


FAKE_WRITER = '''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
'''


FAKE_TEST_AUTHOR = '''
GATE_VERSION = "generated_test@1.1.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": "network", "message": "not used"},
    }
'''


FAKE_LLM = '''
import json
import os

DEFAULT_TIMEOUT_SECONDS = 600

PROVIDERS = {
    "claude-cli": {"default_base_url": None, "default_api_key_env": None, "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "anthropic": {"default_base_url": "https://api.anthropic.com", "default_api_key_env": "ANTHROPIC_API_KEY", "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "openai": {"default_base_url": "https://api.openai.com/v1", "default_api_key_env": "OPENAI_API_KEY", "needs_base_url": False, "suggested_model": "gpt-6-astra"},
    "openai-compatible": {"default_base_url": None, "default_api_key_env": None, "needs_base_url": True, "suggested_model": ""},
    "gemini": {"default_base_url": "https://generativelanguage.googleapis.com", "default_api_key_env": "GEMINI_API_KEY", "needs_base_url": False, "suggested_model": "gemini-4-argon"},
    "ollama": {"default_base_url": "http://localhost:11434", "default_api_key_env": None, "needs_base_url": False, "suggested_model": "llama3.2"},
}


class ModelResolutionError(Exception):
    pass


def parse_model(model):
    if ":" in model:
        head, rest = model.split(":", 1)
        if head in PROVIDERS:
            return head, rest
    return None, model


def resolve_provider(model, config=None):
    provider, name = parse_model(model)
    provider = provider or "anthropic"
    p = PROVIDERS[provider]
    return {
        "provider": provider,
        "model": name,
        "base_url": p["default_base_url"],
        "api_key_env": p["default_api_key_env"],
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "auth": None,
    }


def complete(prompt, model, *, backend=None, **params):
    log_dir = os.environ["GATE010_LOG_DIR"]
    with open(os.path.join(log_dir, "complete_calls.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"prompt": prompt, "model": model}) + "\\n")
    with open(os.path.join(log_dir, "mode.txt"), encoding="utf-8") as fh:
        mode = fh.read().strip()
    if mode == "error":
        return {
            "text": None,
            "model": model,
            "backend": "fake",
            "model_call_error": {"category": "network", "message": "backend down"},
        }
    if mode == "not_json":
        text = "not json"
    elif mode == "maybe":
        text = json.dumps({"result": "maybe"})
    else:
        text = "```json\\n" + json.dumps({"result": "pass", "rationale": "ok"}) + "\\n```"
    return {"text": text, "model": model, "backend": "fake", "model_call_error": None}
'''


def build_repo(repo_root, log_dir, mode):
    repo_root = Path(repo_root)
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQ)
    write(comp / "acceptance" / "AC-FOO-001.md", ACC)
    write(comp / "interface" / "library.md", IFACE)
    write(comp / "constraints.md", CONSTRAINTS)

    write(repo_root / "gen" / "foo" / "foo.py", "MARKER_SOURCE = 1\n")

    write_fake(repo_root, "provenance-checker", FAKE_PROVENANCE_CHECKER)
    write_fake(repo_root, "spec-bundle-assembler", FAKE_ASSEMBLER)
    write_fake(repo_root, "generator", FAKE_GENERATOR)
    write_fake(repo_root, "verifier-orchestrator", FAKE_VERIFIER)
    write_fake(repo_root, "license-scanner", FAKE_LICENSE)
    write_fake(repo_root, "secret-scanner", FAKE_SECRET)
    write_fake(repo_root, "provenance-tracker", FAKE_TRACKER)
    write_fake(repo_root, "provenance-writer", FAKE_WRITER)
    write_fake(repo_root, "test-author", FAKE_TEST_AUTHOR)
    write_fake(repo_root, "llm-endpoint", FAKE_LLM)

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    write(Path(log_dir) / "mode.txt", mode)


def read_calls(log_dir):
    path = Path(log_dir) / "complete_calls.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_outcome(log_dir):
    path = Path(log_dir) / "judge_outcome.json"
    assert path.is_file(), "the faked verify never recorded a judge outcome"
    return json.loads(path.read_text(encoding="utf-8"))


def run(tmp_path, monkeypatch, mode):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    build_repo(repo_root, log_dir, mode)
    monkeypatch.setenv(LOG_ENV, str(log_dir))
    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "fake-model", seed=0, llm_backend=None
    )
    return result, log_dir


def test_judge_makes_one_complete_call_with_all_markers_and_unwraps_fence(tmp_path, monkeypatch):
    result, log_dir = run(tmp_path, monkeypatch, "fenced_pass")

    assert field(result, "provenance_hit") is False

    calls = read_calls(log_dir)
    assert len(calls) == 1, calls
    prompt = calls[0]["prompt"]
    for marker in ("MARKER_SOURCE", "MARKER_CRIT", "MARKER_REQ", "MARKER_IFACE"):
        assert marker in prompt, marker

    outcome = read_outcome(log_dir)
    assert "error" not in outcome, outcome
    assert outcome["result"] == "pass"
    assert outcome["rationale"] == "ok"


@pytest.mark.parametrize("mode", ["error", "not_json", "maybe"])
def test_judge_unavailable_is_fail_never_raised(tmp_path, monkeypatch, mode):
    result, log_dir = run(tmp_path, monkeypatch, mode)

    outcome = read_outcome(log_dir)
    assert "error" not in outcome, outcome
    assert outcome["result"] == "fail"
    assert isinstance(outcome["rationale"], str)
    assert outcome["rationale"].startswith("judge unavailable"), outcome["rationale"]