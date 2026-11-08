import json
import textwrap
from pathlib import Path

import pytest

import component_gate_runner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_jsonl(path: Path):
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _build_repo_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write(repo_root / "gen" / "foo" / "foo.py", "MARKER_SOURCE\n")

    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        textwrap.dedent(
            '''
            class ProvenanceKey:
                def __init__(self, spec_bundle_hash, gate_versions):
                    self.spec_bundle_hash = spec_bundle_hash
                    self.gate_versions = gate_versions

            class ProvenanceCheckResult:
                def __init__(self, hit, verification_report=None, license_scan=None, secret_scan=None):
                    self.hit = hit
                    self.verification_report = verification_report
                    self.license_scan = license_scan
                    self.secret_scan = secret_scan

            def current_sealed_key(component_id, repo_root):
                return None

            def current_provenance_key(component_id, repo_root):
                return ProvenanceKey(
                    spec_bundle_hash="sha256:" + "0" * 64,
                    gate_versions={
                        "compiler": "criterion-compiler@1.0.0",
                        "generated_test": "generated_test@1.0.0",
                        "verifier": "verifier-orchestrator@2.0.0",
                        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
                        "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
                    },
                )

            def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
                return ProvenanceCheckResult(hit=False)
            '''
        ),
    )

    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        textwrap.dedent(
            '''
            class SpecBundle:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)

            def assemble(component_id, repo_root, mode="cold"):
                return SpecBundle(
                    component_id=component_id,
                    spec_bundle_hash="sha256:" + "0" * 64,
                    spec="spec text",
                    interface="interface text",
                    constraints="constraints text",
                    dependency_interfaces={},
                    dependency_context={},
                    dependency_usage={},
                    vars={},
                    glossary="glossary text",
                    hint_code=None,
                )
            '''
        ),
    )

    _write(
        repo_root / "gen" / "generator" / "generator.py",
        textwrap.dedent(
            '''
            class GenerationResult:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)

            def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
                if isinstance(bundle, dict):
                    component_id = bundle.get("component_id")
                else:
                    component_id = getattr(bundle, "component_id", None)
                return GenerationResult(
                    component_id=component_id,
                    spec_bundle_hash="sha256:" + "0" * 64,
                    model=model,
                    prompt_version="v1",
                    cache_hit=False,
                    files={"foo.py": "MARKER_SOURCE\\n"},
                    model_call_error=None,
                    refused=None,
                    retry_feedback=retry_feedback,
                )
            '''
        ),
    )

    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        textwrap.dedent(
            '''
            import json
            import os

            GATE_VERSION = "verifier-orchestrator@2.0.0"

            def verify(component_id, repo_root, judge=None, test_author=None):
                bundle = {
                    "component_id": component_id,
                    "criterion_id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "criterion_text": "MARKER_CRIT",
                    "requirement_text": "MARKER_REQ",
                    "interface": "MARKER_IFACE",
                    "glossary": "glossary text",
                }
                outcome = judge(bundle)
                if isinstance(outcome, dict):
                    result = outcome.get("result")
                    rationale = outcome.get("rationale")
                else:
                    result = getattr(outcome, "result", None)
                    rationale = getattr(outcome, "rationale", None)
                outcomes_log = os.environ["AC_GATE_010_OUTCOMES_LOG"]
                with open(outcomes_log, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"result": result, "rationale": rationale}) + "\\n")
                overall = "pass" if result == "pass" else "fail"
                return {
                    "component_id": component_id,
                    "criteria": [
                        {
                            "id": "AC-FOO-001",
                            "covers": "R-FOO-001",
                            "kind": "llm-judge",
                            "result": overall,
                            "rationale": rationale,
                        },
                    ],
                    "requirement_results": {"R-FOO-001": overall},
                    "interface_drift": False,
                    "mutation_score": 1.0 if overall == "pass" else 0.0,
                    "overall": overall,
                }
            '''
        ),
    )

    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        textwrap.dedent(
            '''
            def scan(component_id, repo_root):
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

            def gate_version(repo_root):
                return "license_scanner@4.0.0-no-reference-corpus"
            '''
        ),
    )

    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        textwrap.dedent(
            '''
            def scan(repo_root):
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

            def gate_version(repo_root):
                return "secret_scanner@3.1.0+detect-secrets.1.5.0"
            '''
        ),
    )

    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        textwrap.dedent(
            '''
            def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
                return {
                    "attempt_id": "2026-01-01T00:00:00Z-abc123",
                    "component_id": component_id,
                    "timestamp": "2026-01-01T00:00:00Z",
                    "spec_bundle_hash": spec_bundle_hash,
                    "generation": {},
                    "verification": {},
                }
            '''
        ),
    )

    _write(
        repo_root / "gen" / "provenance-writer" / "provenance_writer.py",
        textwrap.dedent(
            '''
            def write_provenance(component_id, inputs, repo_root):
                return None
            '''
        ),
    )

    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        textwrap.dedent(
            '''
            import json
            import os

            def complete(prompt, model, *, backend=None, **params):
                calls_log = os.environ["AC_GATE_010_CALLS_LOG"]
                with open(calls_log, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"prompt": prompt, "model": model}) + "\\n")
                mode = os.environ["AC_GATE_010_LLM_MODE"]
                if mode == "pass":
                    text = "```json\\n" + json.dumps({"result": "pass", "rationale": "ok"}) + "\\n```"
                    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}
                if mode == "model_call_error":
                    return {
                        "text": None,
                        "model": model,
                        "backend": "mock",
                        "model_call_error": {"category": "network", "message": "boom"},
                    }
                if mode == "not_json":
                    return {"text": "not json", "model": model, "backend": "mock", "model_call_error": None}
                if mode == "bad_result":
                    text = json.dumps({"result": "maybe"})
                    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}
                raise ValueError("unknown mode: " + mode)
            '''
        ),
    )

    return repo_root


def test_judge_sends_all_markers_and_records_pass(tmp_path, monkeypatch):
    repo_root = _build_repo_root(tmp_path)
    calls_log = tmp_path / "calls.jsonl"
    outcomes_log = tmp_path / "outcomes.jsonl"
    monkeypatch.setenv("AC_GATE_010_CALLS_LOG", str(calls_log))
    monkeypatch.setenv("AC_GATE_010_OUTCOMES_LOG", str(outcomes_log))
    monkeypatch.setenv("AC_GATE_010_LLM_MODE", "pass")

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, model="mock-model",
    )

    assert _get(result, "block_reason") != "model_call_error"

    calls = _read_jsonl(calls_log)
    assert len(calls) == 1
    prompt = calls[0]["prompt"]
    for marker in ("MARKER_SOURCE", "MARKER_CRIT", "MARKER_REQ", "MARKER_IFACE"):
        assert marker in prompt

    outcomes = _read_jsonl(outcomes_log)
    assert len(outcomes) == 1
    assert outcomes[0]["result"] == "pass"
    assert outcomes[0]["rationale"] == "ok"


@pytest.mark.parametrize("mode", ["model_call_error", "not_json", "bad_result"])
def test_judge_reports_fail_when_complete_is_unusable(tmp_path, monkeypatch, mode):
    repo_root = _build_repo_root(tmp_path)
    calls_log = tmp_path / "calls.jsonl"
    outcomes_log = tmp_path / "outcomes.jsonl"
    monkeypatch.setenv("AC_GATE_010_CALLS_LOG", str(calls_log))
    monkeypatch.setenv("AC_GATE_010_OUTCOMES_LOG", str(outcomes_log))
    monkeypatch.setenv("AC_GATE_010_LLM_MODE", mode)

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, model="mock-model",
    )

    outcomes = _read_jsonl(outcomes_log)
    assert len(outcomes) == 1
    assert outcomes[0]["result"] == "fail"
    assert outcomes[0]["rationale"].startswith("judge unavailable")