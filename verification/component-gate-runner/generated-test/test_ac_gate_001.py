"""AC-GATE-001 (covers R-GATE-001): a passing, unblocked provenance hit
short-circuits run_component_gates; a hit recording a failed attempt is
treated as a miss and regeneration proceeds."""

import json
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_RUNNER_AC001_INVOCATION_LOG"
OVERALL_ENV = "GATE_RUNNER_AC001_HIT_OVERALL"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Shared header for every faked dependency module: a record type readable as
# both a dict and an object, and a file-based invocation log whose path comes
# from an environment variable (no temp path embedded in the fake's source).
# ---------------------------------------------------------------------------
FAKE_HEADER = '''import json
import os
from pathlib import Path


class _Rec(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def to_dict(self):
        return json.loads(json.dumps(dict(self), default=str))


def _log(func, **kwargs):
    path = os.environ["GATE_RUNNER_AC001_INVOCATION_LOG"]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"module": _MODULE, "func": func, "args": kwargs}, default=str) + "\\n")


def _verification_report(component_id, overall):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": overall},
        ],
        "requirement_results": {"R-FOO-001": overall},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": overall,
    }


def _license_scan(component_id):
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


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''

PROVENANCE_CHECKER = '''
_MODULE = "provenance_checker"


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return _Rec(spec_bundle_hash="sha256:k", gate_versions={"verifier": "v@1"})


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        "check_provenance",
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        gate_versions=dict(gate_versions) if gate_versions is not None else None,
    )
    overall = os.environ.get("GATE_RUNNER_AC001_HIT_OVERALL", "pass")
    return {
        "hit": True,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": _license_scan(component_id),
        "secret_scan": _secret_scan(),
    }


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
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
_MODULE = "spec_bundle_assembler"


def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return _Rec(
        component_id=component_id,
        spec_bundle_hash="sha256:k",
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return _Rec(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x = 2 When foo(x) is called Then it returns 4",
        requirement_text="foo(x) MUST return 2 * x.",
        interface="foo(x: int) -> int",
        glossary="- **Foo** - a test term.",
        dependency_interfaces={},
    )
'''

GENERATOR = '''
_MODULE = "generator"

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", model=model, retry_feedback=retry_feedback)
    component_id = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    return _Rec(
        component_id=component_id,
        spec_bundle_hash="sha256:k",
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
_MODULE = "verifier_orchestrator"

GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return _Rec(_verification_report(component_id, "pass"))
'''

LICENSE_SCANNER = '''
_MODULE = "license_scanner"


def scan(component_id, repo_root):
    _log("scan", component_id=component_id)
    return _Rec(_license_scan(component_id))


def gate_version(repo_root):
    _log("gate_version")
    return "license_scanner@4.0.0-no-reference-corpus"
'''

SECRET_SCANNER = '''
_MODULE = "secret_scanner"


class AllowlistInvalidError(Exception):
    pass


def scan(repo_root):
    _log("scan")
    return _Rec(_secret_scan())


def scan_files(paths, repo_root=None):
    _log("scan_files")
    result = _secret_scan()
    result["scope"] = "precommit"
    return _Rec(result)


def gate_version(repo_root):
    _log("gate_version")
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def propose(repo_root):
    _log("propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_TRACKER = '''
_MODULE = "provenance_tracker"


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id, spec_bundle_hash=spec_bundle_hash)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    directory = Path(repo_root) / ".hotdocs" / "attempts" / slug
    directory.mkdir(parents=True, exist_ok=True)
    count = len(list(directory.iterdir()))
    attempt_id = "2026-11-15T00:00:0%dZ-abc%03d" % (count % 10, count)
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": json.loads(json.dumps(
            generation_result.to_dict() if hasattr(generation_result, "to_dict") else generation_result,
            default=str)),
        "verification": None if verification_report is None else json.loads(json.dumps(
            verification_report.to_dict() if hasattr(verification_report, "to_dict") else verification_report,
            default=str)),
    }
    (directory / (attempt_id + ".json")).write_text(json.dumps(record), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures", component_id=component_id)
    return []
'''

PROVENANCE_WRITER = '''
_MODULE = "provenance_writer"


class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''

TEST_AUTHOR = '''
_MODULE = "test_author"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model, seed=seed)
    return _Rec(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        model=model,
        seed=seed,
        prompt_version="v1",
        cache_hit=False,
        file={"path": "verification/foo/generated-test/test_ac_foo_001.py", "content": "def test_x():\\n    pass\\n"},
        model_call_error=None,
    )
'''

LLM_ENDPOINT = '''
_MODULE = "llm_endpoint"

DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}
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

GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""


def _build_repo(repo_root: Path) -> None:
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD, encoding="utf-8")
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n", encoding="utf-8"
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

    for slug, body in FAKES.items():
        module_name = slug.replace("-", "_")
        directory = repo_root / "gen" / slug
        directory.mkdir(parents=True)
        (directory / f"{module_name}.py").write_text(FAKE_HEADER + body, encoding="utf-8")


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    log_path = tmp_path / "invocations.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    return repo_root, log_path


def test_passing_unblocked_hit_short_circuits(repo, monkeypatch):
    repo_root, log_path = repo
    monkeypatch.setenv(OVERALL_ENV, "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_log(log_path)
    checks = [c for c in calls if c["module"] == "provenance_checker" and c["func"] == "check_provenance"]
    assert len(checks) == 1, calls
    assert checks[0]["args"]["spec_bundle_hash"] == "sha256:k"
    assert checks[0]["args"]["gate_versions"] == {"verifier": "v@1"}

    others = [c for c in calls if c["module"] != "provenance_checker"]
    assert others == [], f"no other dependency may be called on a hit: {others}"

    assert field(result, "provenance_hit") is True
    assert field(result, "blocked") is False

    expected_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }
    verification = field(result, "verification")
    if not isinstance(verification, dict) and hasattr(verification, "to_dict"):
        verification = verification.to_dict()
    assert dict(verification) == expected_report


def test_hit_with_failed_verification_proceeds_as_miss(repo, monkeypatch):
    repo_root, log_path = repo
    monkeypatch.setenv(OVERALL_ENV, "fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_log(log_path)
    generate_calls = [c for c in calls if c["module"] == "generator" and c["func"] == "generate"]
    assert len(generate_calls) == 1, calls

    assert field(result, "provenance_hit") is False