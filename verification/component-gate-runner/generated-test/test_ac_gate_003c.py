from pathlib import Path

import component_gate_runner


def _read(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_fixture_component(repo_root: Path) -> None:
    _write(
        repo_root / "specs/components/foo/component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo Component\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "sealed: false\n"
        "---\n\n"
        "# Foo Component\n\n"
        "## Purpose\n\n"
        "Fixture component for AC-GATE-003c.\n",
    )
    _write(
        repo_root / "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\nFixture requirement for AC-GATE-003c.\n",
    )
    _write(
        repo_root / "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\nFixture acceptance criterion.\n",
    )


def _write_fake(repo_root: Path, slug: str, module_name: str, content: str) -> None:
    _write(repo_root / f"gen/{slug}/{module_name}.py", content)


PROVENANCE_CHECKER_FAKE = r'''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@3.1.0",
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
'''

SPEC_BUNDLE_ASSEMBLER_FAKE = r'''
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "fixture spec",
        "interface": "fixture interface",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
'''

GENERATOR_FAKE = r'''
import os


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    log_path = os.environ["GATE_RUNNER_TEST_CALL_LOG"]
    with open(log_path, "a") as f:
        f.write("called\n")
    if isinstance(bundle, dict):
        component_id = bundle["component_id"]
        spec_bundle_hash = bundle["spec_bundle_hash"]
    else:
        component_id = bundle.component_id
        spec_bundle_hash = bundle.spec_bundle_hash
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "timeout", "message": "t"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

LICENSE_SCANNER_FAKE = r'''
def scan(component_id, repo_root):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''

SECRET_SCANNER_FAKE = r'''
def scan(repo_root):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''

PROVENANCE_TRACKER_FAKE = r'''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''


def test_ac_gate_003c(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture_component(repo_root)

    call_log = tmp_path / "generator_calls.log"
    monkeypatch.setenv("GATE_RUNNER_TEST_CALL_LOG", str(call_log))

    _write_fake(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_FAKE)
    _write_fake(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_FAKE)
    _write_fake(repo_root, "generator", "generator", GENERATOR_FAKE)
    _write_fake(repo_root, "license-scanner", "license_scanner", LICENSE_SCANNER_FAKE)
    _write_fake(repo_root, "secret-scanner", "secret_scanner", SECRET_SCANNER_FAKE)
    _write_fake(repo_root, "provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_FAKE)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, model="fake-model",
    )

    assert call_log.exists()
    calls = call_log.read_text().splitlines()
    assert len(calls) == 1

    assert _read(result, "blocked") is True
    assert _read(result, "block_reason") == "model_call_error"
    assert _read(result, "model_call_error") == {"category": "timeout", "message": "t"}
    assert _read(result, "verification") is None