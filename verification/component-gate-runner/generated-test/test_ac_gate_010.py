"""AC-GATE-010 (Covers: R-GATE-010): the judge closure built by
run_component_gates makes exactly one llm-endpoint complete call whose
prompt carries the bundle's criterion/requirement/interface text and the
gen/<slug>/ source, unwraps a fenced JSON reply, and degrades every bad
reply to a "judge unavailable" fail, never raising."""

import json
import os
import textwrap
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "HOTDOCS_FAKE_LOG_DIR"
MODE_ENV = "HOTDOCS_FAKE_COMPLETE_MODE"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_PROVENANCE_CHECKER = '''
class _Key:
    def __init__(self, **kw):
        self._d = dict(kw)
        for k, v in kw.items():
            setattr(self, k, v)

    def __getitem__(self, k):
        return self._d[k]

    def get(self, k, default=None):
        return self._d.get(k, default)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return _Key(spec_bundle_hash="sha256:abc123", gate_versions=dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    return {
        "hit": False, "sealed": False, "reason": "not_sealed",
        "verification_report": None, "license_scan": None, "secret_scan": None,
        "owners": None, "source_hash": None, "written_at": None,
    }
'''

FAKE_SPEC_BUNDLE_ASSEMBLER = '''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:abc123",
        "spec": "Foo spec",
        "interface": "MARKER_IFACE",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "MARKER_CRIT",
        "requirement_text": "MARKER_REQ",
        "interface": "MARKER_IFACE",
        "glossary": "",
        "dependency_interfaces": {},
    }
'''

FAKE_GENERATOR = '''
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:abc123",
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "cache_hit": False,
        "files": {"foo.py": "MARKER_SOURCE = 1\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

FAKE_VERIFIER = '''
import json
import os

GATE_VERSION = "verifier-orchestrator@2.0.0"


class _Bundle(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class _Report:
    def __init__(self, **kw):
        self._d = dict(kw)
        for k, v in kw.items():
            setattr(self, k, v)

    def __getitem__(self, k):
        return self._d[k]

    def get(self, k, default=None):
        return self._d.get(k, default)

    def to_dict(self):
        return dict(self._d)


def _read(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def verify(component_id, repo_root, judge=None, test_author=None):
    bundle = _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text="MARKER_CRIT",
        requirement_text="MARKER_REQ",
        interface="MARKER_IFACE",
        glossary="",
        dependency_interfaces={},
    )
    outcome = judge(bundle)
    record = {"result": _read(outcome, "result"), "rationale": _read(outcome, "rationale")}
    with open(os.path.join(os.environ["HOTDOCS_FAKE_LOG_DIR"], "judge_outcome.json"), "w") as fh:
        json.dump(record, fh)
    result = "pass" if record["result"] == "pass" else "fail"
    return _Report(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "llm-judge",
                   "result": result, "rationale": record["rationale"]}],
        requirement_results={"R-FOO-001": result},
        interface_drift=False,
        mutation_score=None,
        overall=result,
    )
'''

FAKE_LICENSE_SCANNER = '''
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

FAKE_SECRET_SCANNER = '''
class AllowlistInvalidError(Exception):
    pass


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def _result(scope):
    return {
        "scope": scope,
        "gate_version": "secret_scanner@0.0.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def scan(repo_root):
    return _result("full")


def scan_files(paths, repo_root=None):
    return _result("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

FAKE_PROVENANCE_TRACKER = '''
import os


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    d = os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    os.makedirs(d, exist_ok=True)
    n = len(os.listdir(d))
    attempt_id = "2026-11-15T00:00:00Z-%06d" % n
    with open(os.path.join(d, attempt_id + ".json"), "w") as fh:
        fh.write("{}")
    return {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": None,
    }


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''

FAKE_PROVENANCE_WRITER = '''
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

FAKE_TEST_AUTHOR = '''
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

FAKE_LLM_ENDPOINT = '''
import json
import os

DEFAULT_TIMEOUT_SECONDS = 600
PROVIDERS = {}


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    with open(os.path.join(os.environ["HOTDOCS_FAKE_LOG_DIR"], "complete_calls.jsonl"), "a") as fh:
        fh.write(json.dumps({"prompt": prompt, "model": model}) + "\\n")
    mode = os.environ.get("HOTDOCS_FAKE_COMPLETE_MODE", "fence")
    if mode == "error":
        return {"text": None, "model": model, "backend": "mock",
                "model_call_error": {"category": "network", "message": "mock failure"}}
    if mode == "notjson":
        text = "not json"
    elif mode == "maybe":
        text = json.dumps({"result": "maybe"})
    else:
        text = "```json\\n" + json.dumps({"result": "pass", "rationale": "ok"}) + "\\n```"
    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}


def parse_model(model):
    return (None, model)


def resolve_provider(model, config=None):
    return {"provider": None, "model": model, "base_url": None,
            "api_key_env": None, "timeout_seconds": DEFAULT_TIMEOUT_SECONDS}
'''


FAKES = {
    "provenance-checker": FAKE_PROVENANCE_CHECKER,
    "spec-bundle-assembler": FAKE_SPEC_BUNDLE_ASSEMBLER,
    "generator": FAKE_GENERATOR,
    "verifier-orchestrator": FAKE_VERIFIER,
    "license-scanner": FAKE_LICENSE_SCANNER,
    "secret-scanner": FAKE_SECRET_SCANNER,
    "provenance-tracker": FAKE_PROVENANCE_TRACKER,
    "provenance-writer": FAKE_PROVENANCE_WRITER,
    "test-author": FAKE_TEST_AUTHOR,
    "llm-endpoint": FAKE_LLM_ENDPOINT,
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


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(textwrap.dedent(source))

    foo = repo_root / "gen" / "foo"
    foo.mkdir(parents=True)
    (foo / "foo.py").write_text("MARKER_SOURCE = 1\n")

    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir()
    (comp / "interface").mkdir()
    (comp / "component.md").write_text(COMPONENT_MD)
    (repo_root / "specs" / "glossary.md").write_text("# Glossary\n\n- **Foo** — a test term.\n")
    return repo_root


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = _build_repo(tmp_path)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv(LOG_ENV, str(log_dir))
    return repo_root, log_dir


def _complete_calls(log_dir):
    path = log_dir / "complete_calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _outcome(log_dir):
    path = log_dir / "judge_outcome.json"
    assert path.exists(), "faked verify never recorded a judge outcome"
    return json.loads(path.read_text())


def test_judge_makes_one_complete_call_and_unwraps_fenced_pass(env, monkeypatch):
    repo_root, log_dir = env
    monkeypatch.setenv(MODE_ENV, "fence")

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock-model", seed=0
    )
    assert result is not None
    assert field(result, "provenance_hit") is False

    calls = _complete_calls(log_dir)
    assert len(calls) == 1, f"expected exactly one complete call, got {len(calls)}"
    prompt = calls[0]["prompt"]
    for marker in ("MARKER_SOURCE", "MARKER_CRIT", "MARKER_REQ", "MARKER_IFACE"):
        assert marker in prompt, f"{marker} missing from judge prompt"

    outcome = _outcome(log_dir)
    assert outcome["result"] == "pass"
    assert outcome["rationale"] == "ok"


@pytest.mark.parametrize("mode", ["error", "notjson", "maybe"])
def test_judge_degrades_bad_reply_to_unavailable_fail(env, monkeypatch, mode):
    repo_root, log_dir = env
    monkeypatch.setenv(MODE_ENV, mode)

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock-model", seed=0
    )

    calls = _complete_calls(log_dir)
    assert len(calls) == 1

    outcome = _outcome(log_dir)
    assert outcome["result"] == "fail"
    assert isinstance(outcome["rationale"], str)
    assert outcome["rationale"].startswith("judge unavailable"), outcome["rationale"]