# hotdocs-criterion: sha256:11453dd535e3585cee4f811cd3c15318c54344f22929a888de358b543e209f0b
import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _header(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(fn, **kw):\n"
        "    kw['fn'] = fn\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps(kw, default=repr) + chr(10))\n"
        "\n"
    )


VR_SRC = '''
def _vr(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }
'''

PROVENANCE_CHECKER_SRC = '''
class _Key:
    def __init__(self):
        self.spec_bundle_hash = "sha256:abc"
        self.spec_bundle_parts = {"spec": "sha256:01", "dependency_code": "sha256:02"}
        self.gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
            "generator": "generator@3.0.0+v11",
        }
        self.assets = [{"kind": "python", "path": ".", "definition_sha256": None,
                        "adapter_sha256": "sha256:03", "versions": {"python": "3.12.4"},
                        "lockfile_sha256": None}]
        self.drivers = []


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):
    _log("check_provenance", component_id=component_id)
    return {"hit": False, "reason": "no manifest", "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {"hit": False, "sealed": False, "reason": "not_sealed", "verification_report": None,
            "license_scan": None, "secret_scan": None, "owners": None,
            "source_hash": None, "written_at": None}
'''

SPEC_BUNDLE_ASSEMBLER_SRC = '''
def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:abc",
        "spec": "spec",
        "interface": "interface",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
        "spec_bundle_parts": {"spec": "sha256:01", "dependency_code": "sha256:02"},
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }
'''

GENERATION_LOOP_SRC = VR_SRC + '''

RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


def run_attempts(component_id, bundle, repo_root, model, *, mode="single", max_attempts=3,
                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,
                 on_attempt=None):
    _log("run_attempts", component_id=component_id, model=model, mode=mode,
         max_attempts=max_attempts)
    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:abc",
        "model": model,
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {"foo.py": "X = 1"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    return {
        "passed": True,
        "stop_reason": "passed",
        "attempts": [
            {"number": 1, "outcome": "passed", "retry_feedback": [],
             "error_category": None, "surface_ok": True, "overall": "pass",
             "failed_requirements": [], "transcript_sha256": None,
             "reauthored_tests": []},
        ],
        "generation_result": generation_result,
        "verification_report": _vr(component_id),
        "surface_report": {"ok": True, "findings": []},
    }


def make_closures(model, seed, repo_root, llm_backend=None):
    _log("make_closures", model=model, seed=seed)

    def test_author(bundle):
        return {"model_call_error": None, "file": None}

    def judge(bundle):
        return {"result": "pass", "rationale": None}

    return (test_author, judge)
'''

PROVENANCE_TRACKER_SRC = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    return {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": component_id,
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": None,
    }


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {},
            "secret_scan": None, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures", component_id=component_id)
    return []
'''

VERIFIER_ORCHESTRATOR_SRC = VR_SRC + '''

GATE_VERSION = "verifier-orchestrator@4.0.0"
DEFAULT_TEST_TIMEOUT = 300.0


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return _vr(component_id)
'''

LICENSE_SCANNER_SRC = '''
def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
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

SECRET_SCANNER_SRC = '''
def _result(scope):
    return {
        "scope": scope,
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def scan(repo_root):
    _log("secret_scan")
    return _result("full")


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    return _result("precommit")


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


class AllowlistInvalidError(Exception):
    pass


def propose(repo_root):
    _log("propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_WRITER_SRC = '''
class MissingInputError(Exception):
    pass


class InvalidSealedInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER_SRC,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER_SRC,
    ("generation-loop", "generation_loop"): GENERATION_LOOP_SRC,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER_SRC,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_ORCHESTRATOR_SRC,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER_SRC,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER_SRC,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER_SRC,
}

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A fixture component.\n"
)

VALID_TOML = "[generate]\nmax_attempts = 5\nmode = \"agentic\"\n"


def _build_repo(tmp_path, toml_text):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    header = _header(log_path)
    for (slug, module), body in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (module + ".py")).write_text(header + body)
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD)
    if toml_text is not None:
        (repo_root / "hotdocs.toml").write_text(toml_text)
    return repo_root, log_path


def _calls(log_path, fn):
    if not log_path.exists():
        return []
    out = []
    for line in log_path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("fn") == fn:
            out.append(entry)
    return out


def _argv(repo_root, extra=()):
    return ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)] + list(extra)


def test_file_values_reach_run_attempts(tmp_path, monkeypatch):
    repo_root, log_path = _build_repo(tmp_path, VALID_TOML)
    monkeypatch.chdir(repo_root)
    component_gate_runner.main(_argv(repo_root))
    calls = _calls(log_path, "run_attempts")
    assert len(calls) == 1
    assert calls[0]["max_attempts"] == 5
    assert calls[0]["mode"] == "agentic"


def test_flags_override_file_values(tmp_path, monkeypatch):
    repo_root, log_path = _build_repo(tmp_path, VALID_TOML)
    monkeypatch.chdir(repo_root)
    component_gate_runner.main(_argv(repo_root, ["--max-attempts=1", "--mode=single"]))
    calls = _calls(log_path, "run_attempts")
    assert len(calls) == 1
    assert calls[0]["max_attempts"] == 1
    assert calls[0]["mode"] == "single"


@pytest.mark.parametrize(
    "toml_text, extra",
    [
        ("[generate]\nmode = \"turbo\"\n", []),
        (None, ["--max-attempts=0"]),
        (None, ["--mode=turbo"]),
    ],
    ids=["file-mode-turbo", "flag-max-attempts-0", "flag-mode-turbo"],
)
def test_invalid_values_are_usage_errors(tmp_path, monkeypatch, capsys, toml_text, extra):
    repo_root, log_path = _build_repo(tmp_path, toml_text)
    monkeypatch.chdir(repo_root)
    capsys.readouterr()
    rc = component_gate_runner.main(_argv(repo_root, extra))
    err = capsys.readouterr().err
    assert rc == 2
    lines = err.splitlines()
    assert lines, "expected output on stderr"
    assert lines[0].startswith("usage error: ")
    assert _calls(log_path, "run_attempts") == []