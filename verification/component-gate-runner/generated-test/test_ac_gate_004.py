"""AC-GATE-004 (Covers: R-GATE-004).

A generation attempt that does not yield a passing candidate is blocked,
and the block reason tells a model-call failure apart from a produced
candidate that failed verification.
"""

import json
import textwrap
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-widget"
SLUG = "widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


_COMMON = textwrap.dedent(
    '''
    import json
    import os


    class _AttrDict(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)

        def to_dict(self):
            return dict(self)


    def _log(name, **extra):
        path = os.environ.get("GATE_TEST_LOG")
        if path:
            record = {"call": name}
            record.update(extra)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\\n")
    '''
)


_PROVENANCE_CHECKER = _COMMON + textwrap.dedent(
    '''

    _GATE_VERSIONS = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        "secret_scanner": "secret_scanner@0.0.0",
    }


    def current_sealed_key(component_id, repo_root):
        _log("provenance_checker.current_sealed_key", component_id=component_id)
        return None


    def current_provenance_key(component_id, repo_root):
        _log("provenance_checker.current_provenance_key", component_id=component_id)
        return _AttrDict(
            spec_bundle_hash="sha256:abc123",
            gate_versions=dict(_GATE_VERSIONS),
        )


    def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
        _log("provenance_checker.check_provenance", component_id=component_id)
        return _AttrDict(
            hit=False,
            verification_report=None,
            license_scan=None,
            secret_scan=None,
        )


    def check_sealed_provenance(component_id, repo_root):
        _log("provenance_checker.check_sealed_provenance", component_id=component_id)
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
)


_SPEC_BUNDLE_ASSEMBLER = _COMMON + textwrap.dedent(
    '''

    def assemble(component_id, repo_root, mode="cold"):
        _log("spec_bundle_assembler.assemble", component_id=component_id, mode=mode)
        return _AttrDict(
            component_id=component_id,
            spec_bundle_hash="sha256:abc123",
            spec="Widget spec.",
            interface="widget_double(x: int) -> int",
            constraints="None.",
            dependency_interfaces={},
            dependency_context={},
            dependency_usage={},
            vars={},
            glossary="",
            hint_code=None,
        )


    def assemble_criterion(component_id, criterion_id, repo_root):
        _log("spec_bundle_assembler.assemble_criterion", component_id=component_id)
        return _AttrDict(
            component_id=component_id,
            criterion_id=criterion_id,
            covers="R-WIDGET-001",
            criterion_text="",
            requirement_text="",
            interface="",
            glossary="",
            dependency_interfaces={},
        )
    '''
)


_GENERATOR = _COMMON + textwrap.dedent(
    '''

    GATE_VERSION = "generator@2.0.0"
    PROMPT_VERSION = "v10"


    def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
        _log("generator.generate", model=model)
        component_id = bundle["component_id"] if isinstance(bundle, dict) else bundle.component_id
        mode = os.environ.get("GATE_TEST_MODE", "")
        if mode == "error":
            return _AttrDict(
                component_id=component_id,
                spec_bundle_hash="sha256:abc123",
                model=model,
                prompt_version=PROMPT_VERSION,
                cache_hit=False,
                files={},
                model_call_error={"category": "network", "message": "connection refused"},
                refused=None,
                retry_feedback=retry_feedback,
            )
        return _AttrDict(
            component_id=component_id,
            spec_bundle_hash="sha256:abc123",
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files={"widget.py": "def widget_double(x):\\n    return x + 1\\n"},
            model_call_error=None,
            refused=None,
            retry_feedback=retry_feedback,
        )
    '''
)


_VERIFIER_ORCHESTRATOR = _COMMON + textwrap.dedent(
    '''

    GATE_VERSION = "verifier-orchestrator@2.0.0"


    def verify(component_id, repo_root, judge=None, test_author=None):
        _log("verifier_orchestrator.verify", component_id=component_id)
        return _AttrDict(
            component_id=component_id,
            criteria=[
                {
                    "id": "AC-WIDGET-001",
                    "covers": "R-WIDGET-001",
                    "kind": "compiled",
                    "result": "fail",
                    "failure_detail": {
                        "message": "result equals 4 failed",
                        "expected": 4,
                        "actual": 3,
                    },
                }
            ],
            requirement_results={"R-WIDGET-001": "fail"},
            interface_drift=False,
            mutation_score=0.5,
            overall="fail",
        )
    '''
)


_LICENSE_SCANNER = _COMMON + textwrap.dedent(
    '''

    def gate_version(repo_root):
        return "license_scanner@4.0.0-no-reference-corpus"


    def scan(component_id, repo_root):
        _log("license_scanner.scan", component_id=component_id)
        return _AttrDict(
            component_id=component_id,
            gate_version="license_scanner@4.0.0-no-reference-corpus",
            evaluated=False,
            reason="no-reference-corpus",
            similarity_score=None,
            block_threshold=None,
            blocked=False,
            matches=[],
            notified=False,
            notification_delivery_error=None,
            cache_hit=False,
        )
    '''
)


_SECRET_SCANNER = _COMMON + textwrap.dedent(
    '''

    def _result(scope):
        return _AttrDict(
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
        _log("secret_scanner.scan")
        return _result("full")


    def scan_files(paths, repo_root=None):
        _log("secret_scanner.scan_files")
        return _result("precommit")


    def gate_version(repo_root):
        return "secret_scanner@0.0.0"


    def propose(repo_root):
        return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
    '''
)


_PROVENANCE_TRACKER = _COMMON + textwrap.dedent(
    '''
    from pathlib import Path


    def _plain(value):
        if value is None:
            return None
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return vars(value)


    def write_attempt_record(component_id, generation_result, verification_report,
                             spec_bundle_hash, repo_root):
        _log(
            "provenance_tracker.write_attempt_record",
            component_id=component_id,
            verification_is_none=verification_report is None,
        )
        slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
        directory = Path(repo_root) / ".hotdocs" / "attempts" / slug
        directory.mkdir(parents=True, exist_ok=True)
        index = len(list(directory.iterdir()))
        attempt_id = "2026-11-15T00:00:0%dZ-fake" % index
        record = {
            "attempt_id": attempt_id,
            "component_id": component_id,
            "timestamp": "2026-11-15T00:00:00Z",
            "spec_bundle_hash": spec_bundle_hash,
            "generation": _plain(generation_result),
            "verification": _plain(verification_report),
        }
        (directory / (attempt_id + ".json")).write_text(
            json.dumps(record, default=str), encoding="utf-8"
        )
        return record


    def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        return {
            "scope": "whole-corpus",
            "ready": False,
            "components": {},
            "capabilities": {},
            "not_ready_reasons": [],
        }


    def last_requirement_failures(component_id, repo_root):
        return []
    '''
)


_PROVENANCE_WRITER = _COMMON + textwrap.dedent(
    '''

    class InvalidSealedInputError(Exception):
        pass


    class MissingInputError(Exception):
        pass


    def write_provenance(component_id, inputs, repo_root):
        _log("provenance_writer.write_provenance", component_id=component_id)
        return None


    def write_sealed_provenance(component_id, inputs, repo_root):
        _log("provenance_writer.write_sealed_provenance", component_id=component_id)
        return None
    '''
)


_TEST_AUTHOR = _COMMON + textwrap.dedent(
    '''

    def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
        _log("test_author.author_test", model=model)
        return _AttrDict(
            component_id="comp-widget",
            criterion_id="AC-WIDGET-001",
            model=model,
            seed=seed,
            prompt_version="v1",
            cache_hit=False,
            file={
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": "def test_placeholder():\\n    assert True\\n",
            },
            model_call_error=None,
        )
    '''
)


_LLM_ENDPOINT = _COMMON + textwrap.dedent(
    '''

    DEFAULT_TIMEOUT_SECONDS = 600


    def complete(prompt, model, *, backend=None, **params):
        _log("llm_endpoint.complete", model=model)
        return {
            "text": "pass",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }
    '''
)


_FAKES = {
    "provenance-checker": _PROVENANCE_CHECKER,
    "spec-bundle-assembler": _SPEC_BUNDLE_ASSEMBLER,
    "generator": _GENERATOR,
    "verifier-orchestrator": _VERIFIER_ORCHESTRATOR,
    "license-scanner": _LICENSE_SCANNER,
    "secret-scanner": _SECRET_SCANNER,
    "provenance-tracker": _PROVENANCE_TRACKER,
    "provenance-writer": _PROVENANCE_WRITER,
    "test-author": _TEST_AUTHOR,
    "llm-endpoint": _LLM_ENDPOINT,
}


_COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [team-a]
depends_on: []
---

# Widget

## Purpose

Widget doubles a number.
"""


def _build_repo(repo_root: Path) -> None:
    for slug, source in _FAKES.items():
        module_name = slug.replace("-", "_")
        directory = repo_root / "gen" / slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{module_name}.py").write_text(source, encoding="utf-8")

    component_dir = repo_root / "specs" / "components" / SLUG
    component_dir.mkdir(parents=True, exist_ok=True)
    (component_dir / "component.md").write_text(_COMPONENT_MD, encoding="utf-8")


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mock_backend(prompt, model, **params):
    return {
        "text": "unused",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _run(tmp_path, monkeypatch, mode):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    monkeypatch.setenv("GATE_TEST_MODE", mode)
    monkeypatch.chdir(repo_root)

    result = component_gate_runner.run_component_gates(
        COMPONENT_ID,
        repo_root,
        "mock-model",
        seed=0,
        llm_backend=_mock_backend,
        retry_feedback=None,
    )
    calls = [entry["call"] for entry in _read_log(log_path)]
    return result, calls


def test_model_call_error_blocks_without_calling_verify(tmp_path, monkeypatch):
    result, calls = _run(tmp_path, monkeypatch, "error")

    # The faked dependencies were really used: a provenance miss, then generation.
    assert "provenance_checker.check_provenance" in calls
    assert "generator.generate" in calls

    # Then: verify was never called ...
    assert "verifier_orchestrator.verify" not in calls

    # ... and block_reason is "model_call_error".
    assert field(result, "block_reason") == "model_call_error"
    assert field(result, "blocked") is True
    assert field(result, "provenance_hit") is False
    assert field(result, "verification") is None
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "network"


def test_failed_verification_blocks_with_verification_failed(tmp_path, monkeypatch):
    result, calls = _run(tmp_path, monkeypatch, "fail")

    assert "provenance_checker.check_provenance" in calls
    assert "generator.generate" in calls
    assert calls.count("verifier_orchestrator.verify") == 1

    # Then: block_reason is "verification_failed" and model_call_error is null.
    assert field(result, "block_reason") == "verification_failed"
    assert field(result, "model_call_error") is None
    assert field(result, "blocked") is True
    assert field(result, "provenance_hit") is False
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "fail"