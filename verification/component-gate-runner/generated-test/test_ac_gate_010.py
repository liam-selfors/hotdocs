"""AC-GATE-010 (covers R-GATE-010): the judge closure built by
run_component_gates makes exactly one llm-endpoint complete call whose
prompt carries the criterion bundle text and the gen/<slug>/ source, and
unwraps a fenced JSON answer; any unusable answer becomes a
"judge unavailable" fail, never a pass and never raised."""

import json
import os
from pathlib import Path

import pytest

import component_gate_runner


ROOT_ENV = "HOTDOCS_AC_GATE_010_ROOT"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Fake dependency sources
# ---------------------------------------------------------------------------

PROVENANCE_CHECKER_SRC = '''
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
    return None


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        "sha256:" + "ab" * 32,
        {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
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

SPEC_BUNDLE_ASSEMBLER_SRC = '''
from dataclasses import dataclass, field


class _Mapping:
    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


@dataclass
class SpecBundle(_Mapping):
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
class CriterionBundle(_Mapping):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)


def assemble(component_id, repo_root, mode="cold"):
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Foo",
        interface="# Library",
        constraints="None.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="text",
        requirement_text="req",
        interface="# Library",
        glossary="",
    )
'''

GENERATOR_SRC = '''
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


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    return GenerationResult(
        component_id=_get(bundle, "component_id"),
        spec_bundle_hash=_get(bundle, "spec_bundle_hash"),
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "MARKER_SOURCE = 'MARKER_SOURCE'\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''

VERIFIER_SRC = '''
import json
import os
from dataclasses import dataclass, asdict

GATE_VERSION = "verifier-orchestrator@2.0.0"


@dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: object
    overall: str

    def to_dict(self):
        return asdict(self)


def _f(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _plain(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def verify(component_id, repo_root, judge=None, test_author=None):
    log = os.path.join(str(repo_root), "judge_outcomes.jsonl")
    if judge is None:
        rec = {"error": "no judge passed to verify"}
    else:
        try:
            outcome = judge({
                "criterion_text": "MARKER_CRIT",
                "requirement_text": "MARKER_REQ",
                "interface": "MARKER_IFACE",
            })
            rec = {
                "result": _plain(_f(outcome, "result")),
                "rationale": _plain(_f(outcome, "rationale")),
            }
        except Exception as exc:
            rec = {"raised": repr(exc)}
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\\n")
    result = rec.get("result") if rec.get("result") in ("pass", "fail") else "fail"
    return VerificationReport(
        component_id=component_id,
        criteria=[{
            "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "llm-judge",
            "result": result, "rationale": rec.get("rationale"),
        }],
        requirement_results={"R-FOO-001": result},
        interface_drift=False,
        mutation_score=0.9,
        overall="pass",
    )
'''

LICENSE_SCANNER_SRC = '''
def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
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

SECRET_SCANNER_SRC = '''
from dataclasses import dataclass, field, asdict


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
        return asdict(self)


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def scan(repo_root):
    return SecretScanResult(scope="full", gate_version=gate_version(repo_root), flagged=False)


def scan_files(paths, repo_root=None):
    return SecretScanResult(scope="precommit", gate_version=gate_version(repo_root), flagged=False)


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_TRACKER_SRC = '''
import json
import os


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    slug = component_id[5:] if component_id.startswith("comp-") else component_id
    d = os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    os.makedirs(d, exist_ok=True)
    n = len(os.listdir(d))
    attempt_id = "2026-11-15T00:00:0%dZ-fake%02d" % (n % 10, n)
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": None if verification_report is None else {},
    }
    with open(os.path.join(d, attempt_id + ".json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh)
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''

PROVENANCE_WRITER_SRC = '''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


class SealedProvenanceInputs:
    def __init__(self, component_id, owners, source_path, source_hash,
                 verifier_version, verification_report):
        self.component_id = component_id
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version
        self.verification_report = verification_report


def write_provenance(component_id, inputs, repo_root):
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
'''

TEST_AUTHOR_SRC = '''
def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": "network", "message": "fake test-author"},
    }
'''

LLM_ENDPOINT_SRC = '''
import json
import os
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 600

PROVIDERS = {
    "claude-cli": {"default_base_url": None, "default_api_key_env": None,
                   "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "anthropic": {"default_base_url": "https://api.anthropic.com",
                  "default_api_key_env": "ANTHROPIC_API_KEY",
                  "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "openai": {"default_base_url": "https://api.openai.com/v1",
               "default_api_key_env": "OPENAI_API_KEY",
               "needs_base_url": False, "suggested_model": "gpt-6-astra"},
    "openai-compatible": {"default_base_url": None, "default_api_key_env": None,
                          "needs_base_url": True, "suggested_model": ""},
    "gemini": {"default_base_url": "https://generativelanguage.googleapis.com",
               "default_api_key_env": "GEMINI_API_KEY",
               "needs_base_url": False, "suggested_model": "gemini-4-argon"},
    "ollama": {"default_base_url": "http://localhost:11434", "default_api_key_env": None,
               "needs_base_url": False, "suggested_model": "llama3.2"},
}


class ModelResolutionError(Exception):
    pass


def _root():
    env = os.environ.get("HOTDOCS_AC_GATE_010_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def _response(mode, model):
    if mode == "error":
        return {"text": None, "model": model, "backend": "mock",
                "model_call_error": {"category": "network", "message": "fake failure"}}
    if mode == "notjson":
        text = "not json"
    elif mode == "maybe":
        text = '{"result": "maybe"}'
    else:
        text = '```json\\n{"result": "pass", "rationale": "ok"}\\n```'
    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}


def complete(prompt, model, *, backend=None, **params):
    root = _root()
    mode = (root / "llm_mode.txt").read_text(encoding="utf-8").strip()
    with open(root / "complete_calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"prompt": prompt, "model": model}) + "\\n")
    return _response(mode, model)


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
    return {"provider": provider, "model": name, "base_url": p["default_base_url"],
            "api_key_env": p["default_api_key_env"],
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS}


def resolve_backend_name(model):
    return "anthropic"


def load_config(config_path=None):
    return None


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None):
    return None


def detect_providers(env=None, probe_ollama=True):
    return []


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    return {"ok": True, "error": None}
'''

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER_SRC,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER_SRC,
    ("generator", "generator"): GENERATOR_SRC,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_SRC,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER_SRC,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER_SRC,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER_SRC,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER_SRC,
    ("test-author", "test_author"): TEST_AUTHOR_SRC,
    ("llm-endpoint", "llm_endpoint"): LLM_ENDPOINT_SRC,
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


def _test_backend_response(mode, model):
    # Mirrors the fake llm-endpoint's reply; only used if a backend is consulted.
    if mode == "error":
        return {"text": None, "model": model, "backend": "mock",
                "model_call_error": {"category": "network", "message": "fake failure"}}
    if mode == "notjson":
        text = "not json"
    elif mode == "maybe":
        text = '{"result": "maybe"}'
    else:
        text = '```json\n{"result": "pass", "rationale": "ok"}\n```'
    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}


def _build_repo(repo_root: Path, mode: str):
    for (slug, module_name), src in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{module_name}.py").write_text(src, encoding="utf-8")

    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True, exist_ok=True)
    (foo_dir / "foo.py").write_text("MARKER_SOURCE = 'MARKER_SOURCE'\n", encoding="utf-8")

    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    (repo_root / "llm_mode.txt").write_text(mode, encoding="utf-8")


def _run(repo_root: Path, mode: str):
    def backend(prompt, model, **params):
        return _test_backend_response(mode, model)

    return component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "claude-sonnet-5", seed=0,
        llm_backend=backend, retry_feedback=None,
    )


def _read_jsonl(path: Path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv(ROOT_ENV, str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_judge_prompt_carries_markers_and_fenced_pass_is_unwrapped(repo):
    _build_repo(repo, "fenced")

    result = _run(repo, "fenced")
    assert field(result, "provenance_hit") is False

    calls = _read_jsonl(repo / "complete_calls.jsonl")
    assert len(calls) == 1, f"complete called {len(calls)} times, expected once"
    prompt = calls[0]["prompt"]
    for marker in ("MARKER_SOURCE", "MARKER_CRIT", "MARKER_REQ", "MARKER_IFACE"):
        assert marker in prompt, f"{marker} missing from judge prompt"

    outcomes = _read_jsonl(repo / "judge_outcomes.jsonl")
    assert len(outcomes) == 1, outcomes
    outcome = outcomes[0]
    assert "raised" not in outcome, outcome
    assert outcome["result"] == "pass"
    assert outcome["rationale"] == "ok"


@pytest.mark.parametrize("mode", ["error", "notjson", "maybe"])
def test_unusable_judge_answer_is_judge_unavailable_fail(repo, mode):
    _build_repo(repo, mode)

    _run(repo, mode)

    calls = _read_jsonl(repo / "complete_calls.jsonl")
    assert len(calls) == 1, f"complete called {len(calls)} times, expected once"

    outcomes = _read_jsonl(repo / "judge_outcomes.jsonl")
    assert len(outcomes) == 1, outcomes
    outcome = outcomes[0]
    assert "raised" not in outcome, f"judge raised: {outcome}"
    assert outcome["result"] == "fail"
    assert isinstance(outcome["rationale"], str)
    assert outcome["rationale"].startswith("judge unavailable"), outcome["rationale"]