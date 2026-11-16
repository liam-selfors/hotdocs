import json
import os
from pathlib import Path

import pytest

import component_gate_runner


# ---------------------------------------------------------------------------
# Fake dependency modules, written under <repo_root>/gen/<slug>/<module>.py.
# Each fake appends one JSON line per invocation to the file named by the
# HOTDOCS_TEST_LOG environment variable; behaviour switches are read from
# environment variables at call time.
# ---------------------------------------------------------------------------

COMMON_HEADER = '''
import json
import os


def _field(value, name, default=None):
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _log(event, **data):
    path = os.environ["HOTDOCS_TEST_LOG"]
    rec = {"event": event}
    rec.update(data)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\\n")


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getitem__(self, key):
        return self.__dict__[key]

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def keys(self):
        return self.__dict__.keys()

    def to_dict(self):
        return dict(self.__dict__)
'''

PROVENANCE_CHECKER = COMMON_HEADER + '''

class ProvenanceKey(_Obj):
    pass


class SealedKey(_Obj):
    pass


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return ProvenanceKey(spec_bundle_hash="sha256:k", gate_versions=dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id, spec_bundle_hash=spec_bundle_hash)
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
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

SPEC_BUNDLE_ASSEMBLER = COMMON_HEADER + '''

class SpecBundle(_Obj):
    pass


class CriterionBundle(_Obj):
    pass


def assemble(component_id, repo_root=None, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return SpecBundle(
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


def assemble_criterion(component_id, criterion_id, repo_root=None):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return CriterionBundle(
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

GENERATOR = COMMON_HEADER + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"

FILES = {"foo.py": "def double(x):\\n    return 2 * x\\n"}


class GenerationResult(_Obj):
    pass


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    mode = os.environ.get("HOTDOCS_FAKE_GEN_MODE", "files")
    _log("generate", model=model, retry_feedback=retry_feedback, mode=mode)
    shash = _field(bundle, "spec_bundle_hash")
    if mode == "error":
        return GenerationResult(
            component_id="comp-foo",
            spec_bundle_hash=shash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files={},
            model_call_error={"category": "network", "message": "fake failure"},
            refused=None,
            retry_feedback=retry_feedback,
        )
    return GenerationResult(
        component_id="comp-foo",
        spec_bundle_hash=shash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files=dict(FILES),
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''

VERIFIER_ORCHESTRATOR = COMMON_HEADER + '''

GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport(_Obj):
    pass


def verify(component_id, repo_root, judge=None, test_author=None):
    overall = os.environ.get("HOTDOCS_FAKE_VERIFY_OVERALL", "pass")
    _log("verify", component_id=component_id, overall=overall)
    criterion = {
        "id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "kind": "generated-test",
        "result": overall,
    }
    if overall == "fail":
        criterion["failure_detail"] = {"message": "returned 3", "expected": 4, "actual": 3}
    return VerificationReport(
        component_id=component_id,
        criteria=[criterion],
        requirement_results={"R-FOO-001": overall},
        interface_drift=False,
        mutation_score=0.37,
        overall=overall,
    )
'''

LICENSE_SCANNER = COMMON_HEADER + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("license_scanner.scan", component_id=component_id)
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

SECRET_SCANNER = COMMON_HEADER + '''

class AllowlistInvalidError(Exception):
    pass


class SecretScanResult(_Obj):
    pass


def _result(scope):
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


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def scan(repo_root):
    _log("secret_scanner.scan")
    return _result("full")


def scan_files(paths, repo_root=None):
    _log("secret_scanner.scan_files")
    return _result("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_TRACKER = COMMON_HEADER + '''
from pathlib import Path

_COUNTER = [0]


def _summary_generation(gr):
    return {
        "component_id": _field(gr, "component_id"),
        "spec_bundle_hash": _field(gr, "spec_bundle_hash"),
        "model": _field(gr, "model"),
        "files": _field(gr, "files"),
        "model_call_error": _field(gr, "model_call_error"),
    }


def _summary_report(vr):
    if vr is None:
        return None
    return {
        "component_id": _field(vr, "component_id"),
        "overall": _field(vr, "overall"),
        "mutation_score": _field(vr, "mutation_score"),
        "requirement_results": _field(vr, "requirement_results"),
        "criteria_ids": [_field(c, "id") for c in (_field(vr, "criteria") or [])],
    }


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log(
        "write_attempt_record",
        component_id=component_id,
        generation=_summary_generation(generation_result),
        verification=_summary_report(verification_report),
        verification_is_none=verification_report is None,
        spec_bundle_hash=spec_bundle_hash,
        repo_root=str(repo_root),
    )
    if os.environ.get("HOTDOCS_FAKE_TRACKER_RAISE") == "1":
        raise RuntimeError("fake attempt-record failure")
    slug = component_id[5:] if component_id.startswith("comp-") else component_id
    _COUNTER[0] += 1
    attempt_id = "2026-11-15T00:00:00Z-" + str(_COUNTER[0])
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _summary_generation(generation_result),
        "verification": _summary_report(verification_report),
    }
    out = Path(repo_root) / ".hotdocs" / "attempts" / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / (attempt_id.replace(":", "-") + ".json")).write_text(
        json.dumps(record, default=str), encoding="utf-8"
    )
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

PROVENANCE_WRITER = COMMON_HEADER + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


class SealedProvenanceInputs(_Obj):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id,
         attempts=_field(inputs, "attempts"))
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''

TEST_AUTHOR = COMMON_HEADER + '''

GATE_VERSION = "generated_test@1.0.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model, seed=seed)
    return {
        "component_id": _field(bundle, "component_id"),
        "criterion_id": _field(bundle, "criterion_id"),
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": "network", "message": "fake"},
    }
'''

LLM_ENDPOINT = COMMON_HEADER + '''

DEFAULT_TIMEOUT_SECONDS = 600


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {
        "text": None,
        "model": model,
        "backend": "fake",
        "model_call_error": {"category": "network", "message": "fake"},
    }
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

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

EXPECTED_FILES = {"foo.py": "def double(x):\n    return 2 * x\n"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _setup(tmp_path, monkeypatch, gen_mode="files", verify_overall="pass", tracker_raise=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")

    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n", encoding="utf-8"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD, encoding="utf-8")
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    (repo_root / ".hotdocs" / "attempts" / "foo").mkdir(parents=True)

    log_path = tmp_path / "invocations.jsonl"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))
    monkeypatch.setenv("HOTDOCS_FAKE_GEN_MODE", gen_mode)
    monkeypatch.setenv("HOTDOCS_FAKE_VERIFY_OVERALL", verify_overall)
    if tracker_raise:
        monkeypatch.setenv("HOTDOCS_FAKE_TRACKER_RAISE", "1")
    else:
        monkeypatch.delenv("HOTDOCS_FAKE_TRACKER_RAISE", raising=False)
    return repo_root, log_path


def _read_log(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _run(repo_root):
    return component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "fake-model", seed=0, llm_backend=None, retry_feedback=None
    )


def test_attempt_record_written_once_after_both_scans_with_full_inputs(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, gen_mode="files", verify_overall="fail")

    _run(repo_root)

    records = _read_log(log_path)
    events = [r["event"] for r in records]

    tracker_idx = [i for i, e in enumerate(events) if e == "write_attempt_record"]
    assert len(tracker_idx) == 1, events
    t = tracker_idx[0]

    assert "license_scanner.scan" in events, events
    assert "secret_scanner.scan" in events, events
    assert "generate" in events, events
    assert "verify" in events, events
    assert t > events.index("license_scanner.scan"), events
    assert t > events.index("secret_scanner.scan"), events
    assert t > events.index("verify"), events
    assert t > events.index("generate"), events

    rec = records[t]
    assert rec["component_id"] == "comp-foo"
    assert rec["spec_bundle_hash"] == "sha256:k"

    gen = rec["generation"]
    assert gen["component_id"] == "comp-foo"
    assert gen["spec_bundle_hash"] == "sha256:k"
    assert gen["model"] == "fake-model"
    assert gen["files"] == EXPECTED_FILES
    assert gen["model_call_error"] is None

    assert rec["verification_is_none"] is False
    ver = rec["verification"]
    assert ver["component_id"] == "comp-foo"
    assert ver["overall"] == "fail"
    assert ver["mutation_score"] == 0.37
    assert ver["requirement_results"] == {"R-FOO-001": "fail"}
    assert ver["criteria_ids"] == ["AC-FOO-001"]


def test_attempt_record_gets_none_report_on_model_call_error(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, gen_mode="error")

    _run(repo_root)

    records = _read_log(log_path)
    tracker = [r for r in records if r["event"] == "write_attempt_record"]
    assert len(tracker) == 1, [r["event"] for r in records]
    rec = tracker[0]
    assert rec["verification_is_none"] is True
    assert rec["verification"] is None
    assert rec["generation"]["model_call_error"] == {
        "category": "network",
        "message": "fake failure",
    }
    assert rec["spec_bundle_hash"] == "sha256:k"


def test_attempt_record_exception_does_not_change_result(tmp_path, monkeypatch):
    repo_root, log_path = _setup(
        tmp_path, monkeypatch, gen_mode="files", verify_overall="pass", tracker_raise=True
    )

    result = _run(repo_root)

    records = _read_log(log_path)
    tracker = [r for r in records if r["event"] == "write_attempt_record"]
    assert len(tracker) == 1, [r["event"] for r in records]

    assert field(result, "blocked") is False