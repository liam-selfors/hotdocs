import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_AC002A_LOG"


_HEADER = '''import json
import os
from pathlib import Path


class _Rec(dict):
    """A dict that also exposes its keys as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _log(entry):
    path = os.environ.get("GATE_AC002A_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=repr) + "\\n")

'''


_PROVENANCE_CHECKER = _HEADER + '''
_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}


def current_sealed_key(component_id, repo_root):
    _log({"fake": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"fake": "current_provenance_key", "component_id": component_id})
    return _Rec(spec_bundle_hash="sha256:abc123", gate_versions=dict(_GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({"fake": "check_provenance", "component_id": component_id})
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log({"fake": "check_sealed_provenance", "component_id": component_id})
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


_SPEC_BUNDLE_ASSEMBLER = _HEADER + '''
def assemble(component_id, repo_root, mode="cold"):
    _log({"fake": "assemble", "component_id": component_id, "mode": mode})
    return _Rec(
        component_id=component_id,
        spec_bundle_hash="sha256:abc123",
        spec="Foo doubles a number.",
        interface="double(x: int) -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({"fake": "assemble_criterion", "component_id": component_id})
    return _Rec(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x = 2 When double(x) is called Then it returns 4",
        requirement_text="double(x) MUST return 2 * x.",
        interface="double(x: int) -> int",
        glossary="- **Foo** - a test term.",
        dependency_interfaces={},
    )
'''


_GENERATOR = _HEADER + '''
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log({"fake": "generate", "model": model, "backend_id": id(llm_backend)})
    return _Rec(
        component_id="comp-foo",
        spec_bundle_hash="sha256:abc123",
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def double(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


_VERIFIER_ORCHESTRATOR = _HEADER + '''
GATE_VERSION = "verifier-orchestrator@2.0.0"


class SentinelBundle:
    marker = "sentinel-bundle"


def verify(component_id, repo_root, judge=None, test_author=None):
    sentinel = SentinelBundle()
    errors = []
    if test_author is not None:
        try:
            test_author(sentinel)
        except Exception as exc:
            errors.append("test_author: " + repr(exc))
    if judge is not None:
        criterion_bundle = {
            "component_id": component_id,
            "criterion_id": "AC-FOO-002",
            "covers": "R-FOO-002",
            "criterion_text": "Given a number When it is doubled Then the result reads well",
            "requirement_text": "double(x) SHOULD be documented.",
            "interface": "double(x: int) -> int",
            "glossary": "- **Foo** - a test term.",
            "dependency_interfaces": {},
        }
        try:
            judge(criterion_bundle)
        except Exception as exc:
            errors.append("judge: " + repr(exc))
    _log({
        "fake": "verify",
        "component_id": component_id,
        "sentinel_id": id(sentinel),
        "has_judge": judge is not None,
        "has_test_author": test_author is not None,
        "errors": errors,
    })
    return _Rec(
        component_id=component_id,
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        ],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=None,
        overall="pass",
    )
'''


_TEST_AUTHOR = _HEADER + '''
GATE_VERSION = "generated_test@1.0.0"
PROMPT_VERSION = "v1"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log({
        "fake": "author_test",
        "bundle_id": id(bundle),
        "bundle_marker": getattr(bundle, "marker", None),
        "model": model,
        "seed": seed,
        "backend_id": id(llm_backend),
        "backend_name": getattr(llm_backend, "sentinel_name", None),
    })
    return _Rec(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        file={
            "path": "verification/foo/generated-test/test_ac_foo_001.py",
            "content": "def test_placeholder():\\n    assert True\\n",
        },
        model_call_error=None,
    )
'''


_LLM_ENDPOINT = _HEADER + '''
DEFAULT_TIMEOUT_SECONDS = 600
PROVIDERS = {}


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log({
        "fake": "complete",
        "model": model,
        "backend_id": id(backend),
        "backend_name": getattr(backend, "sentinel_name", None),
        "prompt_is_str": isinstance(prompt, str),
    })
    return {
        "text": json.dumps({"result": "pass", "verdict": "pass", "rationale": "ok"}),
        "model": model,
        "backend": "sentinel",
        "model_call_error": None,
    }


def parse_model(model):
    return (None, model)


def resolve_provider(model, config=None):
    return {"provider": None, "model": model, "base_url": None,
            "api_key_env": None, "timeout_seconds": DEFAULT_TIMEOUT_SECONDS}
'''


_LICENSE_SCANNER = _HEADER + '''
def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log({"fake": "license_scan", "component_id": component_id})
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


_SECRET_SCANNER = _HEADER + '''
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
    _log({"fake": "secret_scan"})
    return _result("full")


def scan_files(paths, repo_root=None):
    return _result("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


_PROVENANCE_TRACKER = _HEADER + '''
def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    directory = Path(repo_root) / ".hotdocs" / "attempts" / slug
    directory.mkdir(parents=True, exist_ok=True)
    index = len(list(directory.iterdir())) + 1
    attempt_id = "2026-11-15T00:00:00Z-%03d" % index
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": json.loads(json.dumps(generation_result, default=repr)),
        "verification": json.loads(json.dumps(verification_report, default=repr)),
    }
    (directory / (attempt_id.replace(":", "-") + ".json")).write_text(
        json.dumps(record), encoding="utf-8")
    _log({"fake": "write_attempt_record", "component_id": component_id})
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


_PROVENANCE_WRITER = _HEADER + '''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log({"fake": "write_provenance", "component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log({"fake": "write_sealed_provenance", "component_id": component_id})
    return None
'''


FAKES = {
    "provenance-checker": _PROVENANCE_CHECKER,
    "spec-bundle-assembler": _SPEC_BUNDLE_ASSEMBLER,
    "generator": _GENERATOR,
    "verifier-orchestrator": _VERIFIER_ORCHESTRATOR,
    "test-author": _TEST_AUTHOR,
    "llm-endpoint": _LLM_ENDPOINT,
    "license-scanner": _LICENSE_SCANNER,
    "secret-scanner": _SECRET_SCANNER,
    "provenance-tracker": _PROVENANCE_TRACKER,
    "provenance-writer": _PROVENANCE_WRITER,
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


class SentinelBackend:
    sentinel_name = "sentinel-backend"

    def __call__(self, prompt, model, **params):
        return {
            "text": json.dumps({"result": "pass", "rationale": "ok"}),
            "model": model,
            "backend": "sentinel",
            "model_call_error": None,
        }


def _write_fakes(repo_root: Path):
    for slug, source in FAKES.items():
        module_name = slug.replace("-", "_")
        directory = repo_root / "gen" / slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / (module_name + ".py")).write_text(source, encoding="utf-8")


def _read_log(path: Path):
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def test_ac_gate_002a_closures_capture_model_seed_and_backend(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_dir = repo_root / "specs" / "components" / "foo"
    component_dir.mkdir(parents=True)
    (component_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    _write_fakes(repo_root)

    log_path = tmp_path / "invocations.jsonl"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.chdir(repo_root)

    backend = SentinelBackend()

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", seed=3, llm_backend=backend
    )

    entries = _read_log(log_path)

    generate_calls = [e for e in entries if e["fake"] == "generate"]
    assert generate_calls, "faked generator was never called; log: %r" % entries

    verify_calls = [e for e in entries if e["fake"] == "verify"]
    assert verify_calls, "faked verifier-orchestrator verify was never called; log: %r" % entries
    verify_call = verify_calls[-1]
    assert verify_call["has_test_author"], "verify received no test_author closure"
    assert verify_call["has_judge"], "verify received no judge closure"

    # The faked test-author's author_test received that sentinel bundle,
    # model "m", seed 3, and the sentinel backend.
    author_calls = [e for e in entries if e["fake"] == "author_test"]
    assert author_calls, (
        "faked test-author author_test was never called; verify errors: %r"
        % verify_call.get("errors")
    )
    author_call = author_calls[-1]
    assert author_call["bundle_marker"] == "sentinel-bundle"
    assert author_call["bundle_id"] == verify_call["sentinel_id"]
    assert author_call["model"] == "m"
    assert author_call["seed"] == 3
    assert author_call["backend_id"] == id(backend)
    assert author_call["backend_name"] == "sentinel-backend"

    # The faked llm-endpoint's complete received model "m" and the sentinel backend.
    complete_calls = [e for e in entries if e["fake"] == "complete"]
    assert complete_calls, (
        "faked llm-endpoint complete was never called; verify errors: %r"
        % verify_call.get("errors")
    )
    complete_call = complete_calls[-1]
    assert complete_call["model"] == "m"
    assert complete_call["backend_id"] == id(backend)
    assert complete_call["backend_name"] == "sentinel-backend"