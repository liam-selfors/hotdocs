import json

import pytest

import component_gate_runner


PROVENANCE_CHECKER_SRC = r"""
import json

LOG_PATH = __LOG_PATH__


def _log(name, **kwargs):
    entry = {"module": "provenance_checker", "func": name}
    entry.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


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
        __SPEC_BUNDLE_HASH__,
        {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id)
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {"hit": False, "sealed": False, "reason": "not_sealed"}
"""


SPEC_BUNDLE_ASSEMBLER_SRC = r"""
import json

LOG_PATH = __LOG_PATH__
SPEC_BUNDLE_HASH = __SPEC_BUNDLE_HASH__


def _log(name, **kwargs):
    entry = {"module": "spec_bundle_assembler", "func": name}
    entry.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def assemble(component_id, repo_root=None, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return {
        "component_id": component_id,
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "spec": "spec text",
        "interface": "interface text",
        "constraints": "constraints text",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "glossary text",
        "hint_code": None,
    }


def assemble_criterion(component_id, criterion_id, repo_root=None):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
    }
"""


GENERATOR_SRC = r"""
import json

LOG_PATH = __LOG_PATH__
FILES = __FILES__
MODEL_CALL_ERROR = __MODEL_CALL_ERROR__


def _log(name, **kwargs):
    entry = {"module": "generator", "func": name}
    entry.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    _log("generate", model=model, retry_feedback=retry_feedback)
    component_id = bundle.get("component_id") if isinstance(bundle, dict) else getattr(bundle, "component_id", None)
    spec_bundle_hash = bundle.get("spec_bundle_hash") if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash", None)
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": FILES,
        "model_call_error": MODEL_CALL_ERROR,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


VERIFIER_ORCHESTRATOR_SRC = r"""
import json

LOG_PATH = __LOG_PATH__
OVERALL = __OVERALL__

GATE_VERSION = "verifier-orchestrator@2.0.0"


def _log(name, **kwargs):
    entry = {"module": "verifier_orchestrator", "func": name}
    entry.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    result = "pass" if OVERALL == "pass" else "fail"
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": result},
        ],
        "requirement_results": {"R-FOO-001": result},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": OVERALL,
    }
"""


LICENSE_SCANNER_SRC = r"""
import json

LOG_PATH = __LOG_PATH__
EVALUATED = __EVALUATED__
REASON = __REASON__


def _log(name, **kwargs):
    entry = {"module": "license_scanner", "func": name}
    entry.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("scan", component_id=component_id)
    if EVALUATED:
        return {
            "component_id": component_id,
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
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
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0-" + REASON,
        "evaluated": False,
        "reason": REASON,
        "similarity_score": None,
        "block_threshold": None,
        "blocked": REASON != "no-reference-corpus",
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
"""


SECRET_SCANNER_SRC = r"""
import json

LOG_PATH = __LOG_PATH__


def _log(name, **kwargs):
    entry = {"module": "secret_scanner", "func": name}
    entry.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def scan(repo_root):
    _log("scan")
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


def scan_files(paths, repo_root=None):
    _log("scan_files")
    return {
        "scope": "precommit",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
"""


PROVENANCE_TRACKER_SRC = r"""
import json

LOG_PATH = __LOG_PATH__


def _log(name, **kwargs):
    entry = {"module": "provenance_tracker", "func": name}
    entry.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    generation = generation_result if isinstance(generation_result, dict) else {}
    verification = verification_report if isinstance(verification_report, dict) else None
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation,
        "verification": verification,
    }
"""


PROVENANCE_WRITER_SRC = r"""
import json

LOG_PATH = __LOG_PATH__


def _log(name, **kwargs):
    entry = {"module": "provenance_writer", "func": name}
    entry.update(kwargs)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
"""


def _build_repo(tmp_path, log_path, *, generate_files=None, model_call_error=None,
                 verify_overall="pass", license_evaluated=True, license_reason=None):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo Component\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: fixtures/foo/\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n\n"
        "# Foo Component\n\n"
        "Purpose: a synthetic fixture component for AC-GATE-009.\n"
    )

    gen_dir = repo_root / "gen"
    spec_bundle_hash = "sha256:" + "0" * 64
    log_repr = repr(str(log_path))
    files = generate_files if generate_files is not None else {}

    def write(slug, module_name, content):
        d = gen_dir / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(content)

    write(
        "provenance-checker", "provenance_checker",
        PROVENANCE_CHECKER_SRC.replace("__LOG_PATH__", log_repr)
        .replace("__SPEC_BUNDLE_HASH__", repr(spec_bundle_hash)),
    )
    write(
        "spec-bundle-assembler", "spec_bundle_assembler",
        SPEC_BUNDLE_ASSEMBLER_SRC.replace("__LOG_PATH__", log_repr)
        .replace("__SPEC_BUNDLE_HASH__", repr(spec_bundle_hash)),
    )
    write(
        "generator", "generator",
        GENERATOR_SRC.replace("__LOG_PATH__", log_repr)
        .replace("__FILES__", repr(files))
        .replace("__MODEL_CALL_ERROR__", repr(model_call_error)),
    )
    write(
        "verifier-orchestrator", "verifier_orchestrator",
        VERIFIER_ORCHESTRATOR_SRC.replace("__LOG_PATH__", log_repr)
        .replace("__OVERALL__", repr(verify_overall)),
    )
    write(
        "license-scanner", "license_scanner",
        LICENSE_SCANNER_SRC.replace("__LOG_PATH__", log_repr)
        .replace("__EVALUATED__", repr(license_evaluated))
        .replace("__REASON__", repr(license_reason)),
    )
    write(
        "secret-scanner", "secret_scanner",
        SECRET_SCANNER_SRC.replace("__LOG_PATH__", log_repr),
    )
    write(
        "provenance-tracker", "provenance_tracker",
        PROVENANCE_TRACKER_SRC.replace("__LOG_PATH__", log_repr),
    )
    write(
        "provenance-writer", "provenance_writer",
        PROVENANCE_WRITER_SRC.replace("__LOG_PATH__", log_repr),
    )

    return repo_root


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_generate_json_output_blocked_false_and_retry_feedback_split(tmp_path, capsys):
    log_path = tmp_path / "log.jsonl"
    repo_root = _build_repo(
        tmp_path, log_path,
        generate_files={"foo.py": "content"},
        verify_overall="pass",
    )

    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--seed=2",
        "--retry-feedback=R-FOO-001,R-FOO-002", f"--repo-root={repo_root}", "--format=json",
    ])
    captured = capsys.readouterr()

    assert rc == 0

    result = json.loads(captured.out)
    blocked = result.get("blocked") if isinstance(result, dict) else getattr(result, "blocked", None)
    assert blocked is False

    entries = _read_log(log_path)
    generate_entries = [e for e in entries if e["module"] == "generator" and e["func"] == "generate"]
    assert len(generate_entries) == 1
    assert generate_entries[0]["model"] == "m"
    assert generate_entries[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_generate_text_output_separate_flag_value_form(tmp_path, capsys):
    log_path = tmp_path / "log.jsonl"
    repo_root = _build_repo(
        tmp_path, log_path,
        generate_files={"foo.py": "content"},
        verify_overall="pass",
    )

    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model", "m", "--repo-root", str(repo_root), "--format", "text",
    ])
    captured = capsys.readouterr()

    assert rc == 0
    assert "comp-foo" in captured.out
    assert "passed" in captured.out


def test_generate_model_call_error_exit_1(tmp_path, capsys):
    log_path = tmp_path / "log.jsonl"
    repo_root = _build_repo(
        tmp_path, log_path,
        generate_files={},
        model_call_error={"category": "empty_response", "message": "no files"},
    )

    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", f"--repo-root={repo_root}",
    ])
    captured = capsys.readouterr()

    assert rc == 1
    assert "model_call_error: empty_response: no files" in captured.out


def test_generate_license_scan_not_evaluated(tmp_path, capsys):
    log_path = tmp_path / "log.jsonl"
    repo_root = _build_repo(
        tmp_path, log_path,
        generate_files={"foo.py": "content"},
        verify_overall="pass",
        license_evaluated=False,
        license_reason="no-reference-corpus",
    )

    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", f"--repo-root={repo_root}",
    ])
    captured = capsys.readouterr()

    assert rc == 0
    assert "license_scan not evaluated: no-reference-corpus" in captured.out


@pytest.mark.parametrize("build_argv", [
    lambda repo_root: ["generate", "comp-foo", f"--repo-root={repo_root}"],
    lambda repo_root: ["generate", "comp-nope", "--model=m", f"--repo-root={repo_root}"],
    lambda repo_root: ["generate", "comp-foo", "--model=m", "--seed=x", f"--repo-root={repo_root}"],
    lambda repo_root: ["generate", "comp-foo", "--model=m", f"--repo-root={repo_root}", "--format=bogus"],
    lambda repo_root: ["generate", "comp-foo", "--model=m", f"--repo-root={repo_root}", "--unknown-flag=1"],
    lambda repo_root: ["build", "comp-foo", "--model=m", f"--repo-root={repo_root}"],
    lambda repo_root: ["generate", "comp-foo", f"--repo-root={repo_root}", "--model"],
])
def test_usage_errors_exit_2_no_dependency_called(tmp_path, build_argv):
    log_path = tmp_path / "log.jsonl"
    repo_root = _build_repo(
        tmp_path, log_path,
        generate_files={"foo.py": "content"},
        verify_overall="pass",
    )

    argv = build_argv(repo_root)
    rc = component_gate_runner.main(argv)

    assert rc == 2
    assert not log_path.exists()