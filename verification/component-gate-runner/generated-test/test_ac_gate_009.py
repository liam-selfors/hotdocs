import json
import os

import pytest

import component_gate_runner


_PROVENANCE_CHECKER_SRC = r'''
import json
import os


def _log(name, **kwargs):
    with open(os.environ["GATE_LOG"], "a") as f:
        f.write(json.dumps({"name": name, **kwargs}) + "\n")


class _ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return _ProvenanceKey(
        spec_bundle_hash="sha256:" + "0" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        "check_provenance",
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
    )
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''

_SPEC_BUNDLE_ASSEMBLER_SRC = r'''
import json
import os


def _log(name, **kwargs):
    with open(os.environ["GATE_LOG"], "a") as f:
        f.write(json.dumps({"name": name, **kwargs}) + "\n")


def assemble(component_id, repo_root=None, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
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
        "glossary": "glossary text",
        "hint_code": None,
    }
'''

_GENERATOR_SRC = r'''
import json
import os


def _log(name, **kwargs):
    with open(os.environ["GATE_LOG"], "a") as f:
        f.write(json.dumps({"name": name, **kwargs}) + "\n")


def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        component_id = bundle["component_id"]
        spec_bundle_hash = bundle["spec_bundle_hash"]
    else:
        component_id = bundle.component_id
        spec_bundle_hash = bundle.spec_bundle_hash

    _log(
        "generate",
        component_id=component_id,
        model=model,
        retry_feedback=retry_feedback,
    )

    raw_error = os.environ.get("GATE_GEN_MODEL_CALL_ERROR")
    if raw_error:
        return {
            "component_id": component_id,
            "spec_bundle_hash": spec_bundle_hash,
            "model": model,
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {},
            "model_call_error": json.loads(raw_error),
            "refused": None,
            "retry_feedback": retry_feedback,
        }

    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "# generated"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_VERIFIER_ORCHESTRATOR_SRC = r'''
import json
import os


def _log(name, **kwargs):
    with open(os.environ["GATE_LOG"], "a") as f:
        f.write(json.dumps({"name": name, **kwargs}) + "\n")


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
'''

_LICENSE_SCANNER_SRC = r'''
import json
import os


def _log(name, **kwargs):
    with open(os.environ["GATE_LOG"], "a") as f:
        f.write(json.dumps({"name": name, **kwargs}) + "\n")


def scan(component_id, repo_root):
    _log("scan", component_id=component_id)

    if os.environ.get("GATE_LICENSE_NOT_EVALUATED"):
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

    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+000000000000",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''

_SECRET_SCANNER_SRC = r'''
import json
import os


def _log(name, **kwargs):
    with open(os.environ["GATE_LOG"], "a") as f:
        f.write(json.dumps({"name": name, **kwargs}) + "\n")


def scan(repo_root):
    _log("scan", repo_root=str(repo_root))
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

_PROVENANCE_TRACKER_SRC = r'''
import json
import os


def _log(name, **kwargs):
    with open(os.environ["GATE_LOG"], "a") as f:
        f.write(json.dumps({"name": name, **kwargs}) + "\n")


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''

_PROVENANCE_WRITER_SRC = r'''
import json
import os


def _log(name, **kwargs):
    with open(os.environ["GATE_LOG"], "a") as f:
        f.write(json.dumps({"name": name, **kwargs}) + "\n")


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''


def _write_module(repo_root, slug, module_name, content):
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(content)


def _setup_repo(tmp_path):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "Purpose: fixture component for AC-GATE-009.\n"
    )

    _write_module(repo_root, "provenance-checker", "provenance_checker", _PROVENANCE_CHECKER_SRC)
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", _SPEC_BUNDLE_ASSEMBLER_SRC)
    _write_module(repo_root, "generator", "generator", _GENERATOR_SRC)
    _write_module(repo_root, "verifier-orchestrator", "verifier_orchestrator", _VERIFIER_ORCHESTRATOR_SRC)
    _write_module(repo_root, "license-scanner", "license_scanner", _LICENSE_SCANNER_SRC)
    _write_module(repo_root, "secret-scanner", "secret_scanner", _SECRET_SCANNER_SRC)
    _write_module(repo_root, "provenance-tracker", "provenance_tracker", _PROVENANCE_TRACKER_SRC)
    _write_module(repo_root, "provenance-writer", "provenance_writer", _PROVENANCE_WRITER_SRC)

    return repo_root


def _read_log(log_path):
    if not os.path.exists(log_path):
        return []
    with open(log_path) as f:
        return [json.loads(line) for line in f if line.strip()]


def test_generate_json_reports_miss_and_pass(tmp_path, monkeypatch, capsys):
    repo_root = _setup_repo(tmp_path)
    log_path = tmp_path / "gate_log.jsonl"
    monkeypatch.setenv("GATE_LOG", str(log_path))

    exit_code = component_gate_runner.main(
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
    out = capsys.readouterr().out

    assert exit_code == 0
    result = json.loads(out)
    assert result["blocked"] is False

    records = _read_log(log_path)
    generate_calls = [r for r in records if r["name"] == "generate"]
    assert len(generate_calls) == 1
    assert generate_calls[0]["model"] == "m"
    assert generate_calls[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_generate_text_reports_pass(tmp_path, monkeypatch, capsys):
    repo_root = _setup_repo(tmp_path)
    log_path = tmp_path / "gate_log.jsonl"
    monkeypatch.setenv("GATE_LOG", str(log_path))

    exit_code = component_gate_runner.main(
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
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "comp-foo" in out
    assert "passed" in out


def test_generate_model_call_error_text_output(tmp_path, monkeypatch, capsys):
    repo_root = _setup_repo(tmp_path)
    log_path = tmp_path / "gate_log.jsonl"
    monkeypatch.setenv("GATE_LOG", str(log_path))
    monkeypatch.setenv(
        "GATE_GEN_MODEL_CALL_ERROR",
        json.dumps({"category": "empty_response", "message": "no files"}),
    )

    exit_code = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", f"--repo-root={repo_root}"]
    )
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "model_call_error: empty_response: no files" in out


def test_generate_license_scan_not_evaluated_text_output(tmp_path, monkeypatch, capsys):
    repo_root = _setup_repo(tmp_path)
    log_path = tmp_path / "gate_log.jsonl"
    monkeypatch.setenv("GATE_LOG", str(log_path))
    monkeypatch.setenv("GATE_LICENSE_NOT_EVALUATED", "1")

    exit_code = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", f"--repo-root={repo_root}"]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "license_scan not evaluated: no-reference-corpus" in out


def _no_model(repo_root):
    return ["generate", "comp-foo", f"--repo-root={repo_root}"]


def _unknown_component(repo_root):
    return ["generate", "comp-nope", "--model=m", f"--repo-root={repo_root}"]


def _bad_seed(repo_root):
    return ["generate", "comp-foo", "--model=m", "--seed=x", f"--repo-root={repo_root}"]


def _bad_format(repo_root):
    return ["generate", "comp-foo", "--model=m", "--format=bogus", f"--repo-root={repo_root}"]


def _unknown_flag(repo_root):
    return ["generate", "comp-foo", "--model=m", "--bogus=1", f"--repo-root={repo_root}"]


def _wrong_verb(repo_root):
    return ["build", "comp-foo", "--model=m"]


def _dangling_flag(repo_root):
    return ["generate", "comp-foo", f"--repo-root={repo_root}", "--model"]


@pytest.mark.parametrize(
    "build_argv",
    [_no_model, _unknown_component, _bad_seed, _bad_format, _unknown_flag, _wrong_verb, _dangling_flag],
    ids=[
        "no-model",
        "unknown-component",
        "bad-seed",
        "bad-format",
        "unknown-flag",
        "wrong-verb",
        "dangling-flag",
    ],
)
def test_usage_errors_return_2_without_calling_dependencies(tmp_path, monkeypatch, build_argv):
    repo_root = _setup_repo(tmp_path)
    log_path = tmp_path / "gate_log.jsonl"
    monkeypatch.setenv("GATE_LOG", str(log_path))

    exit_code = component_gate_runner.main(build_argv(repo_root))

    assert exit_code == 2
    assert _read_log(log_path) == []