import json
import sys
from pathlib import Path

import pytest

import component_gate_runner


COMPONENT_ID = "comp-widget"
SLUG = "widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_LOG_HELPER = '''
import json as _json
from pathlib import Path as _Path


def _log(repo_root, name, record):
    d = _Path(repo_root) / "_fake_calls"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / (name + ".log"), "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(record, default=str) + "\\n")
'''


PROVENANCE_CHECKER = _LOG_HELPER + '''

class _Key:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}


def current_sealed_key(component_id, repo_root):
    _log(repo_root, "current_sealed_key", {"component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log(repo_root, "current_provenance_key", {"component_id": component_id})
    return _Key("sha256:abc123", dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(repo_root, "check_provenance", {"component_id": component_id})
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


SPEC_BUNDLE_ASSEMBLER = _LOG_HELPER + '''

class _Bundle:
    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )

    def __init__(self, **kw):
        for k in self._FIELDS:
            setattr(self, k, kw.get(k))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._FIELDS else default

    def keys(self):
        return list(self._FIELDS)


class _CriterionBundle(_Bundle):
    _FIELDS = (
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary", "dependency_interfaces",
    )


def assemble(component_id, repo_root, mode="cold"):
    _log(repo_root, "assemble", {"component_id": component_id, "mode": mode})
    return _Bundle(
        component_id=component_id,
        spec_bundle_hash="sha256:abc123",
        spec="Widget spec.",
        interface="widget_fn(x: int) -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    return _CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-WIDGET-001",
        criterion_text="Given x When y Then z",
        requirement_text="R",
        interface="",
        glossary="",
        dependency_interfaces={},
    )
'''


GENERATOR = _LOG_HELPER + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


class GenerationResult:
    _FIELDS = (
        "component_id", "spec_bundle_hash", "model", "prompt_version",
        "cache_hit", "files", "model_call_error", "refused", "retry_feedback",
    )

    def __init__(self, **kw):
        for k in self._FIELDS:
            setattr(self, k, kw.get(k))

    def to_dict(self):
        return {k: getattr(self, k) for k in self._FIELDS}


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    cid = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    sbh = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash")
    _log(repo_root, "generate", {
        "component_id": cid,
        "model": model,
        "retry_feedback": retry_feedback,
    })
    return GenerationResult(
        component_id=cid,
        spec_bundle_hash=sbh,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"widget.py": "def widget_fn(x):\\n    return x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR = _LOG_HELPER + '''

GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    _FIELDS = (
        "component_id", "criteria", "requirement_results",
        "interface_drift", "mutation_score", "overall",
    )

    def __init__(self, **kw):
        for k in self._FIELDS:
            setattr(self, k, kw.get(k))

    def to_dict(self):
        return {k: getattr(self, k) for k in self._FIELDS}


def verify(component_id, repo_root, judge=None, test_author=None):
    _log(repo_root, "verify", {"component_id": component_id})
    return VerificationReport(
        component_id=component_id,
        criteria=[
            {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001",
             "kind": "compiled", "result": "pass"},
        ],
        requirement_results={"R-WIDGET-001": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        overall="pass",
    )
'''


LICENSE_SCANNER = _LOG_HELPER + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log(repo_root, "license_scan", {"component_id": component_id})
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


SECRET_SCANNER = _LOG_HELPER + '''

class AllowlistInvalidError(Exception):
    pass


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


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def scan(repo_root):
    _log(repo_root, "secret_scan", {})
    return _result("full")


def scan_files(paths, repo_root=None):
    return _result("precommit")


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = _LOG_HELPER + '''

import time as _time


def _plain(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if hasattr(v, "to_dict"):
        return _plain(v.to_dict())
    return _plain(vars(v))


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log(repo_root, "write_attempt_record", {"component_id": component_id})
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    d = _Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    ts = "2026-11-15T00:00:00Z"
    attempt_id = ts + "-" + str(_time.time_ns())
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": ts,
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    (d / (attempt_id.replace(":", "-") + ".json")).write_text(_json.dumps(record))
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_WRITER = _LOG_HELPER + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log(repo_root, "write_provenance", {"component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log(repo_root, "write_sealed_provenance", {"component_id": component_id})
    return None
'''


TEST_AUTHOR = _LOG_HELPER + '''

GATE_VERSION = "generated_test@1.0.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log(repo_root, "author_test", {"model": model})
    return {
        "component_id": "comp-widget",
        "criterion_id": "AC-WIDGET-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/widget/generated-test/test_ac_widget_001.py",
                 "content": "def test_x():\\n    assert True\\n"},
        "model_call_error": None,
    }
'''


LLM_ENDPOINT = '''
def complete(prompt, model, *, backend=None, **params):
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}
'''


CRITERION_COMPILER = '''
GATE_VERSION = "criterion-compiler@1.0.0"
'''


COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [team-a]
depends_on: []
---

# Widget

## Purpose

Widget returns its input.
"""


def _plant_fakes(repo_root: Path) -> None:
    fakes = {
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
        "criterion-compiler": CRITERION_COMPILER,
    }
    for slug, src in fakes.items():
        module_name = slug.replace("-", "_")
        _write(repo_root / "gen" / slug / f"{module_name}.py", src)


def _read_log(repo_root: Path, name: str):
    path = repo_root / "_fake_calls" / f"{name}.log"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _mock_backend(prompt, model, **params):
    return {"text": "", "model": model, "backend": "mock", "model_call_error": None}


def test_ac_gate_003a_single_generator_call_on_miss_yields_passing_result(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write(repo_root / "specs" / "components" / SLUG / "component.md", COMPONENT_MD)
    _plant_fakes(repo_root)

    result = component_gate_runner.run_component_gates(
        COMPONENT_ID,
        repo_root,
        "mock:model",
        seed=0,
        llm_backend=_mock_backend,
        retry_feedback=None,
    )

    # Precondition: it really was a provenance miss path.
    assert len(_read_log(repo_root, "check_provenance")) == 1

    # Generator called exactly once.
    gen_calls = _read_log(repo_root, "generate")
    assert len(gen_calls) == 1, gen_calls
    assert gen_calls[0]["component_id"] == COMPONENT_ID

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None

    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"