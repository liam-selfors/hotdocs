import json
from pathlib import Path

import pytest

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_component_fixture(repo_root: Path, slug: str = "foo") -> None:
    content = (
        "---\n"
        f"id: comp-{slug}\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "Purpose: test fixture for AC-GATE-009.\n"
    )
    _write(repo_root / "specs" / "components" / slug / "component.md", content)


def _module_header(call_log: Path) -> str:
    return (
        "import json\n\n"
        f"CALL_LOG = {str(call_log)!r}\n\n"
        "def _log(event):\n"
        "    with open(CALL_LOG, 'a') as _f:\n"
        "        _f.write(json.dumps(event) + chr(10))\n\n"
    )


PROVENANCE_CHECKER_BODY = '''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log({"fn": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"fn": "current_provenance_key", "component_id": component_id})
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "0" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@3.1.0",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({"fn": "check_provenance", "component_id": component_id})
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''

ASSEMBLER_BODY = '''
def assemble(component_id, repo_root=None, mode="cold"):
    _log({"fn": "assemble", "component_id": component_id, "mode": mode})
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "spec": "spec text",
        "interface": "interface text",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
'''

GENERATOR_BODY_SUCCESS = '''
def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log({"fn": "generate", "model": model, "retry_feedback": retry_feedback})
    return {
        "component_id": _get(bundle, "component_id"),
        "spec_bundle_hash": _get(bundle, "spec_bundle_hash"),
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print(1)\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

GENERATOR_BODY_ERROR = '''
def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log({"fn": "generate", "model": model, "retry_feedback": retry_feedback})
    return {
        "component_id": _get(bundle, "component_id"),
        "spec_bundle_hash": _get(bundle, "spec_bundle_hash"),
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

VERIFIER_BODY = '''
def verify(component_id, repo_root, judge=None, test_author=None):
    _log({"fn": "verify", "component_id": component_id})
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
'''

LICENSE_BODY = '''
def scan(component_id, repo_root):
    _log({"fn": "license_scan", "component_id": component_id})
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

SECRET_BODY = '''
def scan(repo_root):
    _log({"fn": "secret_scan"})
    return {
        "scope": "full",
        "gate_version": "secret_scanner@fake",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "secret_scanner@fake"
'''

TRACKER_BODY = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log({"fn": "write_attempt_record", "component_id": component_id})
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''

WRITER_BODY = '''
def write_provenance(component_id, inputs, repo_root):
    _log({"fn": "write_provenance", "component_id": component_id})
    return None
'''


def _write_fakes(repo_root: Path, call_log: Path, generation_mode: str = "success") -> None:
    header = _module_header(call_log)

    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        header + PROVENANCE_CHECKER_BODY,
    )
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        header + ASSEMBLER_BODY,
    )

    generator_body = GENERATOR_BODY_SUCCESS if generation_mode == "success" else GENERATOR_BODY_ERROR
    _write(repo_root / "gen" / "generator" / "generator.py", header + generator_body)

    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        header + VERIFIER_BODY,
    )
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        header + LICENSE_BODY,
    )
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        header + SECRET_BODY,
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        header + TRACKER_BODY,
    )
    _write(
        repo_root / "gen" / "provenance-writer" / "provenance_writer.py",
        header + WRITER_BODY,
    )


def _read_log_entries(call_log: Path):
    if not call_log.exists():
        return []
    lines = call_log.read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_generate_json_reports_not_blocked_and_calls_generator_with_model_and_retry_feedback(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component_fixture(repo_root, slug="foo")
    call_log = tmp_path / "call_log.jsonl"
    _write_fakes(repo_root, call_log, generation_mode="success")

    rc = component_gate_runner.main(
        [
            "generate",
            "comp-foo",
            "--model=m",
            "--seed=2",
            "--retry-feedback=R-FOO-001,R-FOO-002",
            f"--repo-root={repo_root}",
            "--format=json",
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out
    result = json.loads(out)
    assert _get(result, "blocked") is False

    generate_calls = [e for e in _read_log_entries(call_log) if e.get("fn") == "generate"]
    assert len(generate_calls) == 1
    assert generate_calls[0]["model"] == "m"
    assert generate_calls[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_generate_text_reports_component_id_and_passed(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component_fixture(repo_root, slug="foo")
    call_log = tmp_path / "call_log.jsonl"
    _write_fakes(repo_root, call_log, generation_mode="success")

    rc = component_gate_runner.main(
        [
            "generate",
            "comp-foo",
            "--model",
            "m",
            "--repo-root",
            str(repo_root),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "comp-foo" in out
    assert "passed" in out


def test_generate_model_call_error_returns_exit_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component_fixture(repo_root, slug="foo")
    call_log = tmp_path / "call_log.jsonl"
    _write_fakes(repo_root, call_log, generation_mode="model_call_error")

    rc = component_gate_runner.main(
        [
            "generate",
            "comp-foo",
            "--model=m",
            f"--repo-root={repo_root}",
        ]
    )

    assert rc == 1


@pytest.fixture
def usage_error_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component_fixture(repo_root, slug="foo")
    call_log = tmp_path / "call_log.jsonl"
    _write_fakes(repo_root, call_log, generation_mode="success")
    return repo_root, call_log


USAGE_ERROR_CASES = [
    lambda repo_root: ["generate", "comp-foo", f"--repo-root={repo_root}"],
    lambda repo_root: ["generate", "comp-nope", "--model=m", f"--repo-root={repo_root}"],
    lambda repo_root: ["generate", "comp-foo", "--model=m", "--seed=x", f"--repo-root={repo_root}"],
    lambda repo_root: ["generate", "comp-foo", "--model=m", f"--repo-root={repo_root}", "--format=bogus"],
    lambda repo_root: ["generate", "comp-foo", "--model=m", f"--repo-root={repo_root}", "--unknown-flag=1"],
    lambda repo_root: ["build", "comp-foo", "--model=m"],
    lambda repo_root: ["generate", "comp-foo", "--repo-root", str(repo_root), "--model"],
]


@pytest.mark.parametrize("make_argv", USAGE_ERROR_CASES)
def test_generate_usage_errors_return_exit_2_without_calling_any_dependency(usage_error_repo, make_argv):
    repo_root, call_log = usage_error_repo
    argv = make_argv(repo_root)

    rc = component_gate_runner.main(argv)

    assert rc == 2
    assert not call_log.exists() or call_log.read_text() == ""